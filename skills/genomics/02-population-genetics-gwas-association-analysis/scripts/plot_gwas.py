#!/usr/bin/env python3
"""从全量有效统计生成曼哈顿/QQ与可追溯图件；不重估GWAS。"""
from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]
import argparse
import csv
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
import sys

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--input",type=Path,required=True)
    a.add_argument("--out",type=Path,required=True)
    a.add_argument("--title",required=True)
    a.add_argument("--threshold",type=float,required=True)
    a.add_argument("--font",default="DejaVu Sans")
    x=a.parse_args()
    if not math.isfinite(x.threshold) or not 0<x.threshold<1:
        raise ValueError("threshold须为0到1之间的预设阈值")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, ft2font
    import numpy as np
    fp=font_manager.findfont(font_manager.FontProperties(family=x.font),fallback_to_default=False)
    available=ft2font.FT2Font(fp).get_charmap()
    if any(ord(c) not in available and not c.isspace() for c in x.title):
        raise ValueError("字体不覆盖标题字符，请指定合适字体")
    plt.rcParams.update({"font.family":x.font,"font.size":8,"axes.titlesize":10,
                         "pdf.fonttype":42,"ps.fonttype":42,"svg.fonttype":"none",
                         "axes.spines.top":False,"axes.spines.right":False})
    chromosomes=[str(i) for i in range(1,23)]+["X","Y","MT"]
    points=[]
    op=gzip.open if x.input.suffix==".gz" else open
    with op(x.input,"rt",encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t"); cols=r.fieldnames or []
        if not {"CHR","POS"}<=set(cols) or not ({"P","MLOG10P"}&set(cols)):
            raise ValueError("需要CHR POS与P或MLOG10P")
        if len(cols)!=len(set(cols)): raise ValueError("表头重复")
        seen=set()
        for row in r:
            if None in row or any(v is None for v in row.values()): raise ValueError("列数不一致")
            chrom=row["CHR"].removeprefix("chr").upper()
            if chrom not in chromosomes: raise ValueError("不支持的染色体："+chrom)
            pos=float(row["POS"])
            if not math.isfinite(pos) or pos<=0 or pos!=int(pos): raise ValueError("坐标非法")
            if "MLOG10P" in cols:
                ml=float(row["MLOG10P"])
            else:
                pv=float(row["P"])
                if not math.isfinite(pv) or not 0<pv<=1: raise ValueError("P须在0到1；下溢用原MLOG10P")
                ml=-math.log10(pv)
            if not math.isfinite(ml) or ml<0: raise ValueError("MLOG10P非法")
            if "SNP" in cols:
                if not row["SNP"] or row["SNP"] in seen: raise ValueError("SNP为空/重复；先规范多等位与多模型行")
                seen.add(row["SNP"])
            points.append((chrom,int(pos),ml,row.get("SNP","")))
    if not points: raise ValueError("无数据")
    out=x.out.resolve()
    if out.exists(): raise ValueError("输出已存在")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("图和作图数据不能写入源码仓库")
            break
    order={c:i for i,c in enumerate(chromosomes)}
    points.sort(key=lambda r:(order[r[0]],r[1],r[3]))
    fig,axes=plt.subplots(1,2,figsize=(180/25.4,100/25.4),gridspec_kw={"width_ratios":[2.4,1]},layout="constrained")
    offset=0; ticks=[]; labels=[];colors=["#0072B2","#56B4E9"]
    for i,chrom in enumerate(chromosomes):
        group=[r for r in points if r[0]==chrom]
        if not group: continue
        pos=np.asarray([r[1] for r in group]); ml=np.asarray([r[2] for r in group])
        xx=pos+offset
        axes[0].scatter(xx,ml,s=3,c=colors[i%2],linewidths=0,rasterized=True)
        hit=ml>=-math.log10(x.threshold)
        if hit.any(): axes[0].scatter(xx[hit],ml[hit],s=5,c="#D55E00",linewidths=0,rasterized=True)
        ticks.append(float((xx.min()+xx.max())/2));labels.append(chrom)
        offset=float(xx.max())+1e6
    axes[0].axhline(-math.log10(x.threshold),color="#777777",ls="--",lw=.7)
    axes[0].set(xticks=ticks,xticklabels=labels,xlabel="Chromosome",ylabel="-log10 P",title="Genome-wide associations")
    axes[0].tick_params(axis="x",labelsize=6)
    obs=np.sort(np.asarray([r[2] for r in points]))[::-1]
    exp=-np.log10((np.arange(len(obs))+.5)/len(obs))
    axes[1].scatter(exp,obs,s=4,c="#0072B2",linewidths=0,rasterized=True)
    bound=max(float(exp.max()),float(obs.max()),1)
    axes[1].plot([0,bound],[0,bound],color="#777777",ls="--",lw=.7)
    axes[1].set(xlabel="Expected -log10 P",ylabel="Observed -log10 P",title="QQ (all supplied tests)")
    fig.suptitle(x.title)
    fig.canvas.draw()
    out.mkdir(parents=True,exist_ok=False)
    try:
        for ext in ("pdf","svg","png"):
            save_figure(fig, out/("gwas."+ext),dpi=600,metadata=None)
        plt.close(fig)
        with (out/"plot_data.tsv").open("w",encoding="utf-8",newline="") as f:
            w=csv.writer(f,delimiter="\t");w.writerow(["CHR","POS","MLOG10P","SNP"]);w.writerows(points)
        with x.input.open("rb") as f: sha=hashlib.file_digest(f,"sha256").hexdigest()
        metadata={"input_sha256":sha,"n_tests":len(points),"threshold":x.threshold,"title":x.title,
                  "font":x.font,"dpi":600,"width_mm":180,"height_mm":100,"matplotlib":matplotlib.__version__,
                  "qq_data":"all supplied rows; caller must verify complete coverage",
                  "science_status":"plotting_only"}
        (out/"figure.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        caption=(f"# 图注草稿\n\n{x.title}；输入有效检验 {len(points)} 个，预设阈值 {x.threshold:g}。"
                 "QQ使用提供的全部检验；应核实不是显著子集。密集点在矢量文件中栅格化，轴/文字保留可编辑。"
                 "\n\n按真实记录补充表型单位、N、祖源、模型、协变量、参考build及多重检验范围。"
                 "未提供的信息不能编造。打开图片复核字体、裁切、坐标、异常峰和QQ偏离；不得由图单独断言因果或校准通过。\n")
        (out/"captions.md").write_text(caption,encoding="utf-8")
        links=" ".join(f'<a href="gwas.{ext}">{ext.upper()}</a>' for ext in ("pdf","svg","png"))
        page='<!doctype html><html lang="zh"><meta charset="utf-8"><title>'+html.escape(x.title)+'</title><style>body{font:16px sans-serif;max-width:1100px;margin:2rem auto;padding:1rem}img{width:100%}pre{white-space:pre-wrap}</style><h1>'+html.escape(x.title)+'</h1><img src="gwas.png" alt="Manhattan and QQ"><p>'+links+' <a href="plot_data.tsv">作图数据</a></p><pre>'+html.escape(caption)+'</pre></html>'
        (out/"report.html").write_text(page,encoding="utf-8")
    except Exception as e:
        (out/"FAILED.txt").write_text(str(e),encoding="utf-8");raise
    print("图件已生成；请打开图片复核并补充真实研究图注。")

if __name__=="__main__":
    try: main()
    except (OSError,ValueError,KeyError,TypeError,ImportError) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)
