#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "matplotlib==3.10.6"]
# ///
"""Render method-specific exported evidence; does not replace native inference."""

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]
import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(config, out):
    config = Path(config).resolve(); out = Path(out).resolve()
    cfg = json.loads(config.read_text())
    for key in ("dataset", "method", "method_version", "score_definition"):
        if not cfg.get(key): raise ValueError(f"缺少 {key}")
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and out.is_relative_to(parent):
            raise ValueError("输出必须在 Skill Git 仓库外")
    if out.exists(): raise ValueError("输出目录已存在；禁止覆盖")
    out.mkdir(parents=True)
    shutil.copyfile(config, out / "run_config.json")
    plt.rcParams.update({"font.size":7,"axes.titlesize":7,"axes.labelsize":7,"xtick.labelsize":6,"ytick.labelsize":6,
                        "legend.fontsize":6,"legend.title_fontsize":7,"pdf.fonttype":42,"svg.fonttype":"none","axes.spines.top":False,"axes.spines.right":False})
    manifest = dict(status="running", config=cfg, figures=[], inputs={}, visual_review="pending")
    def persist(): (out / "figure_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    def load(key, fields):
        p = Path(cfg[key]); p = p if p.is_absolute() else config.parent / p
        with p.open(encoding="utf-8-sig") as f:
            reader=csv.DictReader(f,delimiter="\t")
            if not set(fields)<=set(reader.fieldnames or []): raise ValueError(f"{key} 缺列 {fields}")
            rows=list(reader)
        if not rows or any(any(r.get(k) in (None, "") for k in fields) for r in rows): raise ValueError(f"{key} 为空或含缺失字段")
        dest=key+".tsv";shutil.copyfile(p,out/dest)
        manifest["inputs"][key]=dict(file=dest,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        return rows
    def numeric(rows, keys, nonnegative=True):
        for r in rows:
            for k in keys:
                r[k]=float(r[k])
                if not math.isfinite(r[k]) or (nonnegative and r[k]<0): raise ValueError(f"无效数值 {k}")
    def save(name, fig, sources, caption):
        files=[]
        try:
            for ax in fig.axes:
                for artist in ax.collections: artist.set_rasterized(False)
            for ext in ("png","pdf","svg"):
                filename=name+"."+ext;save_figure(fig, out/filename,dpi=600);files.append(filename)
            manifest["figures"].append(dict(id=name,status="generated",files=files,source_data=sources,caption=caption,visual_review="pending"))
        finally: plt.close(fig)
        persist()
    def skip(name,reason):manifest["figures"].append(dict(id=name,status="not_applicable",reason=reason))
    persist()
    try:
        draw(cfg,load,numeric,save,skip,out)
        manifest["status"]="generated_pending_visual_review"
    except Exception as e:
        manifest["status"]="failed";manifest["error"]=str(e);persist();raise
    persist()
    (out/"figure_report.md").write_text("\n".join([cfg["dataset"],cfg["score_definition"],"图件需实际视觉与科学复核；成功出图不代表推断已被验证。"]+[f"{f['id']}: {f['status']} — {f.get('caption', f.get('reason',''))}" for f in manifest["figures"]]))

def draw(cfg,load,numeric,save,skip,out):
    rows=load("communications",["sample","source","metabolite","target","score","evidence_level"]);numeric(rows,["score"])
    if len({(r["sample"],r["source"],r["metabolite"],r["target"]) for r in rows})!=len(rows):raise ValueError("重复通讯记录")
    # No averaging across samples: each sample keeps its own evidence and scale.
    samples=sorted({r["sample"] for r in rows});scale=max(r["score"] for r in rows) or 1
    selected=[]
    for si,sample in enumerate(samples):
        top=sorted([r for r in rows if r["sample"]==sample],key=lambda r:(-r["score"],r["metabolite"],r["source"],r["target"]))[:int(cfg.get("top_links",12))];selected.extend(top)
        for page in range(0,len(top),6):
            links=top[page:page+6];fig,ax=plt.subplots(figsize=(183/25.4,130/25.4),layout="constrained")
            for i,r in enumerate(links):
                for x,label in enumerate((r["source"],r["metabolite"],r["target"])):
                    ax.text(x,i,label,ha="center",va="center",bbox=dict(facecolor="white",edgecolor="#bbbbbb",pad=3))
                for x in (0,1):ax.annotate("",xy=(x+.82,i),xytext=(x+.18,i),arrowprops=dict(arrowstyle="->",lw=.5+3*r["score"]/scale,color="#0072B2"),zorder=0)
            ax.set_xlim(-.4,2.4);ax.set_ylim(-.7,len(links)-.3);ax.invert_yaxis();ax.axis("off");ax.set_title(sample+" | sender → metabolite → receiver")
            save(f"metabolite_network_{si+1:02d}_{page//6+1:02d}",fig,["communications.tsv"],"三层候选网络；线宽按原生非负分数映射，所有样本共享尺度；实测/推断证据层级见源表，不能解释为代谢通量。")
        fig,ax=plt.subplots(figsize=(183/25.4,130/25.4),layout="constrained")
        labels=[r["source"]+" → "+r["metabolite"]+" → "+r["target"] for r in top]
        ax.scatter([r["score"] for r in top],range(len(top)),s=18,color="#0072B2");ax.set_yticks(range(len(top)),labels);ax.invert_yaxis();ax.set_xlim(0,scale*1.05);ax.set_xlabel(cfg["score_definition"]);ax.set_title(sample)
        save(f"metabolite_scores_{si+1:02d}",fig,["communications.tsv"],"每个点是一条方法导出的代谢通讯候选，不将细胞或联系数量当生物学重复。")
    (out/"selection.json").write_text(json.dumps(dict(selected=selected,reason="按本样本原生分数选择展示，不是条件差异检验"),ensure_ascii=False))
    if "molecular_evidence" in cfg:
        ev=load("molecular_evidence",["cell_type","metabolite","gene","role","expression"]);numeric(ev,["expression"])
        for page in range(0,len(ev),24):
            sub=ev[page:page+24];fig,ax=plt.subplots(figsize=(183/25.4,140/25.4),layout="constrained")
            labels=[r["cell_type"]+" | "+r["metabolite"]+" | "+r["role"]+" | "+r["gene"] for r in sub]
            ax.barh(labels,[r["expression"] for r in sub],color="#009E73");ax.invert_yaxis();ax.set_xlabel("Expression support")
            save(f"molecular_evidence_{page//24+1:02d}",fig,["molecular_evidence.tsv"],"合成酶、转运体和受体的表达支持；不等同于代谢物实测浓度。")
    else:skip("molecular_evidence","缺少酶/转运体/受体证据表，不能凭代谢物名称编造")

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();render(a.config,a.out)
