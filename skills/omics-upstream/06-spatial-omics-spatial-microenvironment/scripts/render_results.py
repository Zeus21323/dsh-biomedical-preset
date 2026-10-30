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
    if cfg.get("coordinate_unit")!="um":raise ValueError("坐标须换算为真实微米，并提供coordinate_unit=um；不能使用UMAP坐标")
    if not cfg.get("spatial_method_definition"):raise ValueError("需说明空间方法、邻近范围和组织可达性规则")
    cells=load("coordinates",["sample","cell","cell_type","x","y"]);numeric(cells,["x","y"],False)
    lookup={(r["sample"],r["cell"]):r for r in cells}
    if len(lookup)!=len(cells):raise ValueError("同一样本内细胞ID重复")
    edges=load("spatial_edges",["sample","source_cell","target_cell","ligand","receptor","score","supported"]);numeric(edges,["score"])
    if len({tuple(r[k] for k in ("sample","source_cell","target_cell","ligand","receptor")) for r in edges})!=len(edges):raise ValueError("重复空间通讯边")
    for r in edges:
        if any((r["sample"],r[k]) not in lookup for k in ("source_cell","target_cell")):raise ValueError("空间边引用未知细胞或其他样本")
        if r["supported"] not in ("TRUE","FALSE"):raise ValueError("supported须为TRUE/FALSE，来自原生空间方法")
    labels=sorted({r["cell_type"] for r in cells});colors=cfg.get("colors",{label:matplotlib.colors.to_hex(plt.get_cmap("tab20")(i%20)) for i,label in enumerate(labels)})
    if not set(labels)<=set(colors):raise ValueError("colors未覆盖所有细胞类型")
    maximum=max([r["score"] for r in edges] or [1]) or 1
    selected=[]
    for si,sample in enumerate(sorted({r["sample"] for r in cells})):
        subset=[r for r in cells if r["sample"]==sample]
        supported=sorted([r for r in edges if r["sample"]==sample and r["supported"]=="TRUE"],key=lambda r:(-r["score"],r["ligand"],r["source_cell"]))
        top=supported[:int(cfg.get("top_edges",40))];selected.extend(top)
        for mode in ("location","communication"):
            fig,ax=plt.subplots(figsize=(183/25.4,140/25.4),layout="constrained")
            for label in labels:
                group=[r for r in subset if r["cell_type"]==label]
                if group:ax.scatter([r["x"] for r in group],[r["y"] for r in group],s=3,color=colors[label],label=label,linewidths=0)
            if mode=="communication":
                for r in top:
                    a=lookup[(sample,r["source_cell"])];b=lookup[(sample,r["target_cell"])];ax.annotate("",xy=(b["x"],b["y"]),xytext=(a["x"],a["y"]),arrowprops=dict(arrowstyle="->",lw=.3+1.7*r["score"]/maximum,color=colors[a["cell_type"]],alpha=.6))
            ax.set_aspect("equal");ax.set_xlabel("x (µm)");ax.set_ylabel("y (µm)");ax.set_title(sample);ax.legend(loc="center left",bbox_to_anchor=(1,.5),frameon=False,markerscale=2)
            save(f"spatial_{mode}_{si+1:02d}",fig,["coordinates.tsv","spatial_edges.tsv"],"保留真实坐标和等比例微米轴。仅连接输入方法已支持的空间边；未重新推断空间显著性或跨组织可达性。")
        if supported:
            top_lr={}
            for r in supported:
                key=(r["ligand"],r["receptor"]);top_lr[key]=top_lr.get(key,0)+r["score"]
            items=sorted(top_lr.items(),key=lambda x:(-x[1],x[0]))[:20]
            fig,ax=plt.subplots(figsize=(89/25.4,130/25.4),layout="constrained");ax.barh([a+"–"+b for (a,b),v in items],[v for k,v in items],color="#0072B2");ax.invert_yaxis();ax.set_xlabel("Sum of supported edge scores")
            save(f"spatial_lr_{si+1:02d}",fig,["spatial_edges.tsv"],"样本内已支持空间边按LR汇总；边数和细胞密度影响总量，不能直接作为供体间效应。")
    (out/"selection.json").write_text(json.dumps(dict(selected=selected,reason="每切片按已支持边的原生分数排序，保留完整源表"),ensure_ascii=False))

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();render(a.config,a.out)
