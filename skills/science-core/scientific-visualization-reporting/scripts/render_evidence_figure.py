#!/usr/bin/env python3
"""从已计算的长表生成可编辑图和可追溯图注；不计算或补造统计结论。"""
from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]
COLORS = _delivery_run_path(str(_DeliveryPath(__file__).with_name("scientific_colors.py")))
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def number(value):
    result = float(value)
    require(math.isfinite(result), "绘图数值必须有限，不能自动删除无效值")
    return result


def _render(config, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager, ft2font
    import numpy as np
    cfg = json.loads(config.read_text(encoding="utf-8"))
    allowed = {"table","kind","x","y","title","show_title","xlabel","ylabel","question","caption","unit","source","selection","evidence_level","value","group","lower","upper","interval_method","width_mm","height_mm","dpi","font","colorbar_label","signed","allow_missing","equal_aspect","reference_line","colors","color_limits","publication_style","row_scale","gene_label","sample_order","cluster_rows","cluster_cols","palette","color_registry","color_variable","continuous_palette"}
    require(not set(cfg)-allowed, "未知绘图配置字段：" + str(set(cfg)-allowed))
    for key in ("table", "kind", "x", "y", "xlabel", "ylabel", "question", "caption", "unit", "source", "selection", "evidence_level"):
        require(isinstance(cfg.get(key), str) and cfg[key].strip(), f"缺少非空字段：{key}")
    # Publication figures do not repeat a prose heading inside the panel by default.
    # A title remains an explicit, auditable opt-in for exploratory/QC figures.
    title = cfg.get("title", "")
    require(isinstance(title, str), "title必须是字符串")
    show_title = cfg.get("show_title", False)
    require(type(show_title) is bool, "show_title必须为布尔值")
    if show_title:
        require(title.strip(), "show_title=true时必须提供非空title")
    require(cfg["kind"] in {"point", "heatmap", "scatter", "line"}, "不支持的图形类型")
    require(cfg["evidence_level"] in {"descriptive", "association", "prediction", "experimental"}, "无效证据类型")
    publication_style = cfg.get("publication_style", True)
    require(type(publication_style) is bool, "publication_style必须为布尔值")
    if cfg["kind"] == "heatmap":
        expression_fields = {"row_scale", "gene_label", "cluster_rows", "cluster_cols"}
        require(not expression_fields.intersection(cfg),
                "表达热图配置请使用render_expression_heatmap.py；通用热图不接受无效的标准化/标签/聚类设置")
    require(not out.exists() and not out.is_symlink(), "输出目录已存在，拒绝覆盖")
    path = (config.parent / cfg["table"]).resolve()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t" if path.suffix == ".tsv" else ",")
        columns = reader.fieldnames or []
        require(len(columns) == len(set(columns)), "表头重复")
        rows = list(reader)
    require(rows and all(None not in r and all(v is not None for v in r.values()) for r in rows), "表格为空或列数不一致")
    for key in ("x", "y", "value", "group", "lower", "upper"):
        if key in cfg:
            require(cfg[key] in columns, f"表中缺少配置列：{key}")
    require(("lower" in cfg) == ("upper" in cfg), "上下限须同时提供")
    if "lower" in cfg:
        require(cfg["kind"] == "point" and bool(cfg.get("interval_method")), "区间仅支持点图且需说明计算方法")
    width, height = number(cfg.get("width_mm", 180)), number(cfg.get("height_mm", 110))
    dpi = cfg.get("dpi", 400)
    require(60 <= width <= 300 and 50 <= height <= 350, "图尺寸超出支持范围")
    require(type(dpi) is int and 300 <= dpi <= 600, "PNG分辨率应为300–600 DPI")
    font = cfg.get("font", "DejaVu Sans")
    fp = font_manager.findfont(font_manager.FontProperties(family=font), fallback_to_default=False)
    chars = ft2font.FT2Font(fp).get_charmap()
    text = (title if show_title else "") + "".join(cfg[k] for k in ("xlabel", "ylabel"))
    if cfg["kind"] in {"point", "heatmap"}:
        text += "".join(r[cfg["x"]] for r in rows)
    if cfg["kind"] == "heatmap":
        text += "".join(r[cfg["y"]] for r in rows) + cfg.get("colorbar_label", "")
    if "group" in cfg:
        text += "".join(r[cfg["group"]] for r in rows)
    require(all(ord(c) in chars or c.isspace() for c in text), "字体不覆盖全部标签字符；请指定支持中文/符号的字体")
    plt.rcParams.update({"font.family": font, "font.size": 9, "pdf.fonttype": 42,
                         "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(width / 25.4, height / 25.4), layout="constrained")
    color_record = COLORS["record"](cfg, config.parent)
    resolved_colors = {}
    missing = 0
    try:
        if cfg["kind"] == "heatmap":
            require("value" in cfg, "热图需要value列")
            xs = list(dict.fromkeys(r[cfg["x"]] for r in rows))
            ys = list(dict.fromkeys(r[cfg["y"]] for r in rows))
            if "sample_order" in cfg:
                order = cfg["sample_order"]
                require(isinstance(order, list) and len(order) == len(xs) and set(order) == set(xs),
                        "sample_order须完整且唯一覆盖热图列")
                xs = order
            require(len(xs) <= 40 and len(ys) <= 50, "热图标签太多；先按已声明规则分面或选取并保留全表")
            values = np.full((len(ys), len(xs)), np.nan)
            seen = set()
            for r in rows:
                key = r[cfg["x"]], r[cfg["y"]]
                require(key not in seen, "热图存在重复单元格，不能静默平均")
                seen.add(key)
                values[ys.index(key[1]), xs.index(key[0])] = number(r[cfg["value"]])
            missing = int(np.isnan(values).sum())
            require(not missing or cfg.get("allow_missing") is True, "热图有未提供单元格，需显式允许灰色缺失显示")
            # Expression heatmaps are signed (row z-scores) and use a perceptually
            # readable diverging palette by default; generic heatmaps retain viridis.
            cmap = COLORS["colormap"](cfg.get("signed", False), cfg.get("continuous_palette"))
            if cfg.get("signed") is True:
                bound = float(np.nanmax(np.abs(values))) or 1.0
                if "color_limits" in cfg:
                    lo,hi = [number(x) for x in cfg["color_limits"]]
                    require(lo < 0 < hi and abs(lo+hi)<1e-9 and np.nanmin(values)>=lo and np.nanmax(values)<=hi, "共享发散范围必须对称且覆盖数据")
                    bound = hi
                limits = {"vmin": -bound, "vmax": bound}
            else:
                limits = {}
                if "color_limits" in cfg:
                    lo,hi = [number(x) for x in cfg["color_limits"]]
                    require(lo < hi and np.nanmin(values)>=lo and np.nanmax(values)<=hi, "共享色阶范围不覆盖数据")
                    limits = {"vmin":lo,"vmax":hi}
            cmap = cmap.with_extremes(bad="#cccccc")
            im = ax.imshow(np.ma.masked_invalid(values), cmap=cmap, aspect="auto", **limits)
            # Signed palettes have pale zero values; mark missing cells explicitly, not by color alone.
            for row_index, col_index in np.argwhere(np.isnan(values)):
                ax.text(col_index, row_index, "NA", ha="center", va="center", color="#333333", fontsize=7)
            ax.set_xticks(range(len(xs)), xs, rotation=45, ha="right")
            ax.set_yticks(range(len(ys)), ys)
            fig.colorbar(im, ax=ax, label=cfg.get("colorbar_label", "Value"))
        else:
            groups = list(dict.fromkeys(r[cfg["group"]] for r in rows)) if "group" in cfg else ["all"]
            require(len(groups) <= 8, "分组超过8，请分面并保留完整结果")
            variable = cfg.get("color_variable", cfg.get("group", "group"))
            registry = (config.parent / cfg["color_registry"]).resolve() if cfg.get("color_registry") else None
            resolved_colors[variable] = COLORS["mapping"](
                groups, name=cfg.get("palette", "categorical_strong" if cfg["kind"] in {"line", "scatter"} and len(groups)<=2 else "categorical_clear"),
                explicit=cfg.get("colors"), registry=registry, variable=variable)
            colors = list(resolved_colors[variable].values())
            for i, group in enumerate(groups):
                selected = [r for r in rows if "group" not in cfg or r[cfg["group"]] == group]
                y = np.array([number(r[cfg["y"]]) for r in selected])
                if cfg["kind"] == "point":
                    require(len(groups) == 1, "点估计图每行一个已定义比较；多组请在标签中明确比较身份")
                    x = np.arange(len(selected))
                    require(len(x) <= 40, "点估计标签太多，请分图")
                    error = None
                    if "lower" in cfg:
                        lo = np.array([number(r[cfg["lower"]]) for r in selected])
                        hi = np.array([number(r[cfg["upper"]]) for r in selected])
                        require(np.all(lo <= y) and np.all(y <= hi), "区间不包含点估计")
                        error = [y - lo, hi - y]
                    ax.errorbar(x, y, yerr=error, fmt="o", color=colors[i], capsize=3)
                    ax.set_xticks(x, [r[cfg["x"]] for r in selected], rotation=45, ha="right")
                    ax.set_xlim(-0.5, len(selected) - 0.5)
                else:
                    x = np.array([number(r[cfg["x"]]) for r in selected])
                    if cfg["kind"] == "line":
                        require(len(set(x)) == len(x), "同组折线横坐标重复，请先明确重复单位")
                        order = np.argsort(x)
                        ax.plot(x[order], y[order], marker="o", ms=3, color=colors[i], label=group)
                    else:
                        ax.scatter(x, y, s=12, alpha=0.7, color=colors[i], label=group, rasterized=len(x) > 10000)
            if "group" in cfg:
                ax.legend(frameon=False)
            if cfg.get("equal_aspect") is True:
                ax.set_aspect("equal", adjustable="box")
        ax.set(xlabel=cfg["xlabel"], ylabel=cfg["ylabel"])
        if show_title:
            ax.set_title(title)
        if "reference_line" in cfg:
            ax.axhline(number(cfg["reference_line"]), color="#888888", lw=0.7, ls="--")
        fig.canvas.draw()
        out.mkdir(parents=True, exist_ok=False)
        save_figure(fig, out / "figure.png", dpi=dpi)  # 一次调用成套导出，不按格式重建图形
        shutil.copyfile(path, out / ("plot_data" + path.suffix))
        require(color_record == COLORS["record"](cfg, config.parent), "配色输入在运行中改变")
        if cfg.get("color_registry"):
            shutil.copyfile(config.parent / cfg["color_registry"], out / "input_color_registry.tsv")
        COLORS["export_mapping"](out / "resolved_colors.tsv", resolved_colors)
        manifest = {"status": "rendered_visual_review_required", "config": cfg, "table_sha256": sha(path),
                    "config_sha256": sha(config), "rows": len(rows), "missing_cells": missing,
                    "matplotlib": matplotlib.__version__, "numpy": np.__version__, "font": font,
                    "generated_statistics": False, "color_record": color_record, "resolved_colors": resolved_colors,
                    "continuous_palette": cfg.get("continuous_palette", "blue_white_pink" if cfg.get("signed", False) else "blue_sequential") if cfg["kind"] == "heatmap" else None}
        (out / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        caption_title = title if show_title else "论文级图件（面板内不重复标题）"
        caption = (f"# {caption_title}\n\n问题：{cfg['question']}\n\n{cfg['caption']}\n\n"
                   f"来源：{cfg['source']}\n\n单位：{cfg['unit']}；证据类型：{cfg['evidence_level']}。\n\n"
                   f"选择/展示规则：{cfg['selection']}。行数：{len(rows)}；未提供热图单元格：{missing}。\n\n"
                   f"区间方法：{cfg.get('interval_method', '未提供区间；图不表达统计显著性')}。\n\n"
                   "![图件预览](figure.png)\n\n[矢量PDF](figure.pdf) · [可编辑SVG](figure.svg)\n\n"
                   "需在最终物理尺寸下人工检查标签、图例、裁切和科学表述；导出完成不等于审稿通过。\n")
        (out / "caption.md").write_text(caption, encoding="utf-8")
        return manifest
    finally:
        plt.close(fig)


def render(config, out):
    import tempfile
    import os
    require(not out.exists() and not out.is_symlink(), "输出目录已存在，拒绝覆盖")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".evidence-", dir=out.parent) as folder:
            staged = Path(folder) / "result"
            state = _render(config, staged)
            require(not out.exists(), "输出目录被其他运行占用")
            staged.rename(out)
            return state
    except Exception as error:
        fd, name = tempfile.mkstemp(prefix=out.name+"-failure-", suffix=".json", dir=out.parent)
        os.close(fd)
        Path(name).write_text(json.dumps({"status":"failed","error":str(error)}, ensure_ascii=False), encoding="utf-8")
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        render(a.config, a.out_dir)
        print(f"图件已导出，请检查预览：{a.out_dir}")
        return 0
    except (ValueError, OSError, KeyError, TypeError, ImportError) as e:
        print(f"图件生成失败：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
