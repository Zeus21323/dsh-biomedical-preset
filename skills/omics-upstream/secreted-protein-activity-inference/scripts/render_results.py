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
    rows=load("activities",["ligand","aupr_corrected"]);numeric(rows,["aupr_corrected"],False)
    if len({r["ligand"] for r in rows})!=len(rows):raise ValueError("配体活性重复；每个响应程序单独运行")
    rows.sort(key=lambda r:(-r["aupr_corrected"],r["ligand"]));top=rows[:int(cfg.get("top_ligands",12))]
    ligands=[r["ligand"] for r in top]
    (out/"selection.json").write_text(json.dumps(dict(ligands=ligands,reason="当前接收端程序的 corrected AUPR 排名；不是分泌量或通讯概率"),ensure_ascii=False))
    fig,ax=plt.subplots(figsize=(89/25.4,100/25.4),layout="constrained")
    ax.barh(ligands,[r["aupr_corrected"] for r in top],color="#0072B2");ax.invert_yaxis();ax.set_xlabel("Corrected AUPR");ax.set_ylabel("Ligand")
    save("ligand_activity",fig,["activities.tsv"],"当前接收端响应程序的原生配体活性；展示候选按 corrected AUPR 排序，无差异显著性声明。")
    if "target_links" in cfg:
        links=load("target_links",["ligand","target","weight"]);numeric(links,["weight"])
        if len({(r["ligand"],r["target"]) for r in links})!=len(links):raise ValueError("配体-靶基因重复")
        links=[r for r in links if r["ligand"] in ligands]
        targets=sorted({r["target"] for r in links});lookup={(r["ligand"],r["target"]):r["weight"] for r in links}
        if not targets:skip("ligand_targets","选定配体没有已导出的靶基因联系")
        for page in range(0,len(targets),24):
            ts=targets[page:page+24];mat=np.array([[lookup.get((l,t),np.nan) for t in ts] for l in ligands])
            fig,ax=plt.subplots(figsize=(183/25.4,140/25.4),layout="constrained");cmap=plt.get_cmap("viridis").copy();cmap.set_bad("#dddddd")
            im=ax.pcolormesh(np.ma.masked_invalid(mat),cmap=cmap,vmin=0,vmax=max(r["weight"] for r in links) or 1)
            ax.set_xticks(np.arange(len(ts))+.5,ts,rotation=60,ha="right");ax.set_yticks(np.arange(len(ligands))+.5,ligands);ax.invert_yaxis()
            fig.colorbar(im,ax=ax,label="Regulatory potential",shrink=.6)
            save(f"ligand_targets_{page//24+1:02d}",fig,["target_links.tsv","activities.tsv"],"配体-靶基因先验调控潜力；灰色为未导出联系，不视为零。分页共用色标。")
    else:skip("ligand_targets","缺少原生配体-靶基因联系，不用表达热图冒充")
    if "expression_support" in cfg:
        expr=load("expression_support",["cell_type","role","gene","fraction","mean_expression"]);numeric(expr,["fraction","mean_expression"])
        if any(r["fraction"]>1 or r["role"] not in ("sender","receiver") for r in expr):raise ValueError("fraction需0–1，role需sender/receiver")
        keys=[(r["cell_type"],r["role"],r["gene"]) for r in expr]
        if len(set(keys))!=len(keys):raise ValueError("表达证据重复")
        for page in range(0,len(expr),24):
            sub=expr[page:page+24];fig,ax=plt.subplots(figsize=(183/25.4,140/25.4),layout="constrained")
            labels=[r["role"]+" | "+r["cell_type"]+" | "+r["gene"] for r in sub]
            points=ax.scatter([r["mean_expression"] for r in sub],range(len(sub)),s=[50*r["fraction"] for r in sub],color="#0072B2")
            ax.set_yticks(range(len(sub)),labels);ax.invert_yaxis();ax.set_xlabel("Mean expression; point area = expressing fraction")
            save(f"expression_support_{page//24+1:02d}",fig,["expression_support.tsv"],"发送配体/接收受体的表达证据；面积为表达细胞比例，横轴为平均表达。")
    else:skip("expression_support","未提供发送配体/接收受体表达支持表")

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();render(a.config,a.out)
