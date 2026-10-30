#!/usr/bin/env python3
"""从已核实的表达矩阵和元数据生成注释热图与一致的源表，不执行差异检验。"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

CORE = runpy.run_path(str(Path(__file__).with_name("figure_delivery.py")))
COLORS = runpy.run_path(str(Path(__file__).with_name("scientific_colors.py")))
require = CORE["require"]
read_table = CORE["read_table"]
write_table = CORE["write_table"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique(values, label):
    require(all(isinstance(x, str) and x.strip() for x in values), label + "不能为空")
    require(len(values) == len(set(values)), label + "重复")


def permutation(value, expected, label):
    require(isinstance(value, list), label + "必须为列表")
    unique(value, label)
    require(set(value) == set(expected), label + "须完整且唯一覆盖对应身份")
    return value


def prepare(config):
    import numpy as np
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import pdist

    cfg = json.loads(config.read_text(encoding="utf-8"))
    allowed = {"matrix", "samples", "genes", "expression_layer", "expression_provenance",
               "annotation_source", "selection", "selected_genes", "row_scale", "gene_label",
               "sample_order", "column_order", "cluster_rows", "cluster_cols", "distance",
               "linkage", "annotations", "annotation_colors", "allow_missing", "title",
               "show_title", "color_limits", "width_mm", "height_mm", "dpi", "font",
               "differential_results", "contrast", "analysis_provenance", "palette", "color_registry", "continuous_palette"}
    require(isinstance(cfg, dict) and not set(cfg) - allowed, "未知配置字段或配置不是对象")
    for key in ("matrix", "samples", "genes", "expression_layer", "expression_provenance",
                "annotation_source", "selection"):
        require(isinstance(cfg.get(key), str) and cfg[key].strip(), "缺少非空字段：" + key)
    for key in ("cluster_rows", "allow_missing", "show_title"):
        require(type(cfg.get(key, False)) is bool, key + "必须为布尔值")
    layers = {"vst", "rlog", "log2_normalized", "log2_tpm", "row_zscore"}
    require(cfg["expression_layer"] in layers, "不接受原始计数或未变换TPM；先核实并生成适用的展示表达层")
    scale = cfg.get("row_scale", "zscore")
    require(scale in {"zscore", "none"}, "row_scale须为zscore或none")
    require(cfg["expression_layer"] != "row_zscore" or scale == "none", "输入已为row_zscore，禁止再次标准化")
    paths = {key: (config.parent / cfg[key]).resolve() for key in ("matrix", "samples", "genes")}
    matrix, samples, genes = [read_table(paths[key]) for key in ("matrix", "samples", "genes")]
    require("gene_id" in matrix[0], "矩阵首字段需包含gene_id")
    sample_ids = [x for x in matrix[0] if x != "gene_id"]
    require(len(sample_ids) >= 2, "至少需要两个样本")
    unique(sample_ids, "矩阵样本")
    gene_ids = [r["gene_id"] for r in matrix]
    unique(gene_ids, "矩阵gene_id")
    require({"sample_id", "sample_label", "group"} <= set(samples[0]), "样本表缺少sample_id/sample_label/group")
    unique([r["sample_id"] for r in samples], "样本身份")
    unique([r["sample_label"] for r in samples], "样本显示标签")
    require(all(r["group"].strip() for r in samples), "真实组别不能为空，不能从热图推断")
    require(set(sample_ids) == {r["sample_id"] for r in samples}, "样本表与矩阵样本身份不一致")
    require({"gene_id", "gene_symbol"} <= set(genes[0]), "基因表缺少gene_id/gene_symbol")
    unique([r["gene_id"] for r in genes], "注释gene_id")
    gene_map = {r["gene_id"]: r["gene_symbol"].strip() for r in genes}
    require(set(gene_ids) <= set(gene_map), "注释表未覆盖矩阵基因；无symbol时仍保留ID记录")
    selected = cfg.get("selected_genes")
    require(isinstance(selected, list) and selected, "须提供有依据的selected_genes；不自动挑选Top 30")
    unique(selected, "展示基因")
    require(set(selected) <= set(gene_ids), "展示基因不在矩阵中")
    smap = {r["sample_id"]: r for r in samples}
    order_mode = cfg.get("column_order", "group")
    require(order_mode in {"group", "metadata"}, "column_order须为group或metadata")
    ordered_samples = [r["sample_id"] for r in samples]
    group_order = list(dict.fromkeys(r["group"] for r in samples))
    if order_mode == "group":
        ordered_samples = [s for g in group_order for s in ordered_samples if smap[s]["group"] == g]
    if "sample_order" in cfg:
        ordered_samples = permutation(cfg["sample_order"], sample_ids, "sample_order")
    allow_missing = cfg.get("allow_missing", False)
    def value(text):
        if text.strip().lower() in {"", "na", "nan"}:
            require(allow_missing, "存在缺失值；需显式allow_missing=true并说明来源")
            return np.nan
        n = float(text)
        require(np.isfinite(n), "无穷或非法表达值")
        return n
    all_values = {r["gene_id"]: [value(r[s]) for s in ordered_samples] for r in matrix}
    values = np.array([all_values[g] for g in selected], dtype=float)
    require(np.all(np.isfinite(values).sum(axis=1) >= 2), "展示基因至少需要两个有效值")
    if cfg["expression_layer"] == "row_zscore":
        mean, sd = np.nanmean(values, axis=1), np.nanstd(values, axis=1, ddof=1)
        require(np.allclose(mean, 0, atol=1e-6) and np.allclose(sd, 1, atol=1e-6),
                "row_zscore输入须在这些样本上均值0、样本标准差1；核查计算范围/ddof，不能重复变换")
    if scale == "zscore":
        sd = np.nanstd(values, axis=1, ddof=1)
        require(np.all(sd > 1e-12), "零方差基因不能做行标准化；保留原表并按依据另选或使用原尺度")
        values = (values - np.nanmean(values, axis=1)[:, None]) / sd[:, None]
    distance = cfg.get("distance", "euclidean")
    method = cfg.get("linkage", "average")
    require(distance in {"euclidean", "correlation"}, "仅支持euclidean/correlation距离")
    require(method in {"average", "complete", "single", "ward"}, "不支持的linkage")
    require(method != "ward" or distance == "euclidean", "ward仅适用于euclidean")
    def cluster(v):
        require(np.isfinite(v).all(), "有缺失值时不执行聚类；禁止静默插补")
        d = pdist(v, metric=distance)
        require(np.isfinite(d).all(), "聚类距离无效，检查常数向量与距离定义")
        return linkage(d, method=method, optimal_ordering=True)
    row_linkage = None
    if cfg.get("cluster_rows", False):
        require(len(selected) >= 2, "行聚类至少需要两个基因")
        row_linkage = cluster(values)
        indices = leaves_list(row_linkage).tolist()
        selected, values = [selected[i] for i in indices], values[indices]
    col_cluster = cfg.get("cluster_cols", "none")
    require(col_cluster in {"none", "within_group", "all"}, "cluster_cols须为none/within_group/all")
    require(not ("sample_order" in cfg and col_cluster != "none"), "显式sample_order与列聚类冲突")
    if col_cluster != "none":
        blocks = [list(range(len(ordered_samples)))] if col_cluster == "all" else [
            [i for i, s in enumerate(ordered_samples) if smap[s]["group"] == g] for g in group_order]
        indices = []
        for block in blocks:
            indices.extend([block[i] for i in leaves_list(cluster(values[:, block].T))] if len(block) > 1 else block)
        ordered_samples, values = [ordered_samples[i] for i in indices], values[:, indices]
    label_mode = cfg.get("gene_label", "symbol")
    require(label_mode in {"symbol", "stable_id"}, "gene_label须为symbol或stable_id")
    symbols = [gene_map[g] or g for g in selected]
    labels = [g if label_mode == "stable_id" else
              (f"{symbol} ({g})" if symbols.count(symbol) > 1 else symbol)
              for g, symbol in zip(selected, symbols)]
    unique(labels, "最终基因标签")
    annotations = cfg.get("annotations", ["group"])
    require(isinstance(annotations, list) and "group" in annotations, "annotations必须包含group")
    unique(annotations, "注释字段")
    require(len(annotations) <= 4 and all(a in samples[0] for a in annotations), "注释条最多4条且字段必须存在")
    require(all(smap[s][a].strip() for s in ordered_samples for a in annotations), "注释缺失请显式标记Unknown，不猜测")
    require(len(selected) <= 80 and len(ordered_samples) <= 40, "当前单面板过密；按有依据规则分面并保留全表")
    if "differential_results" in cfg:
        for key in ("contrast", "analysis_provenance"):
            require(isinstance(cfg.get(key), str) and cfg[key].strip(), "差异结果须提供" + key)
        paths["differential_results"] = (config.parent / cfg["differential_results"]).resolve()
        results = read_table(paths["differential_results"])
        require({"gene_id", "log2FC", "pvalue", "padj"} <= set(results[0]), "差异表须包含gene_id/log2FC/pvalue/padj（保留其他列）")
        unique([r["gene_id"] for r in results], "差异结果基因")
        require(set(selected) <= {r["gene_id"] for r in results}, "差异表未覆盖展示基因")
        for r in results:
            for key in ("log2FC", "pvalue", "padj"):
                if r[key].strip().lower() in {"", "na", "nan"}:
                    continue
                n = float(r[key])
                require(np.isfinite(n) and (key == "log2FC" or 0 <= n <= 1), "差异结果数值非法")
    return dict(cfg=cfg, paths=paths, values=values, genes=selected, samples=ordered_samples,
                labels=labels, gene_map=gene_map, sample_map=smap, annotations=annotations,
                row_linkage=row_linkage, scale=scale, distance=distance, linkage=method,
                column_clustering=col_cluster,
                hashes={k: digest(p) for k, p in paths.items()})


def render_into(config, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Rectangle
    import numpy as np
    import scipy
    from scipy.cluster.hierarchy import dendrogram

    state = prepare(config)
    cfg, values = state["cfg"], state["values"]
    genes, samples = state["genes"], state["samples"]
    smap, annotations = state["sample_map"], state["annotations"]
    nrows = len(annotations)
    width = float(cfg.get("width_mm", max(150, 95 + len(samples) * 7)))
    height = float(cfg.get("height_mm", max(110, 50 + len(genes) * 4 + nrows * 8)))
    require(100 <= width <= 400 and 80 <= height <= 450, "画布尺寸超出支持范围，请分面")
    dpi = cfg.get("dpi", 400)
    require(type(dpi) is int and 300 <= dpi <= 600, "dpi须在300–600之间")
    title = cfg.get("title", "")
    require(isinstance(title, str), "title须为字符串")
    require(not cfg.get("show_title", False) or title.strip(), "显示标题时须提供title")
    signed = state["scale"] == "zscore" or cfg["expression_layer"] == "row_zscore"
    lo, hi = (-float(np.nanmax(abs(values))), float(np.nanmax(abs(values)))) if signed else (float(np.nanmin(values)), float(np.nanmax(values)))
    if lo == hi:
        lo, hi = lo - .5, hi + .5
    if "color_limits" in cfg:
        lim = cfg["color_limits"]
        require(isinstance(lim, list) and len(lim) == 2, "color_limits须为两个数值")
        lo, hi = map(float, lim)
        require(np.isfinite([lo, hi]).all() and lo < hi and lo <= np.nanmin(values) and hi >= np.nanmax(values), "色阶须覆盖全部数据，禁止静默截断")
        require(not signed or (lo < 0 < hi and abs(lo + hi) < 1e-9), "z-score色阶须以0对称")
    supplied = cfg.get("annotation_colors", {})
    require(isinstance(supplied, dict) and set(supplied) <= set(annotations), "annotation_colors含未知注释")
    registry = (config.parent / cfg["color_registry"]).resolve() if cfg.get("color_registry") else None
    color_record = COLORS["record"](cfg, config.parent)
    maps = {}
    for a in annotations:
        categories = list(dict.fromkeys(smap[s][a] for s in samples))
        maps[a] = COLORS["mapping"](categories, name=cfg.get("palette", "categorical_clear"),
                                     explicit=supplied.get(a), registry=registry, variable=a)
    rc = {"font.family": cfg.get("font", "DejaVu Sans"), "font.size": 8,
          "pdf.fonttype": 42, "svg.fonttype": "none", "axes.grid": False}
    with plt.rc_context(rc):
        fig = plt.figure(figsize=(width / 25.4, height / 25.4), layout="constrained")
        grid = fig.add_gridspec(nrows + 1, 3, width_ratios=[.12, 1, .32],
                               height_ratios=[.65] * nrows + [max(5, len(genes) * .6)])
        try:
            for i, a in enumerate(annotations):
                ax = fig.add_subplot(grid[i, 1])
                categories = list(maps[a])
                ax.pcolormesh([[categories.index(smap[s][a]) for s in samples]],
                          cmap=ListedColormap(list(maps[a].values())), vmin=-.5, vmax=len(categories)-.5)
                ax.set_xlim(0, len(samples)); ax.set_yticks([.5], [a]); ax.set_xticks([]); ax.tick_params(length=0)
                for spine in ax.spines.values(): spine.set_visible(False)
            legend_items = [(a, v, c) for a in annotations for v, c in maps[a].items()]
            legend_height = max(1.5, .5 * len(legend_items))
            side = grid[:, 2].subgridspec(3, 1, height_ratios=[legend_height, 1.2, max(1, len(genes)*.6-legend_height)])
            legend_ax = fig.add_subplot(side[0]); legend_ax.set_axis_off()
            for i, (a, v, c) in enumerate(legend_items):
                y = 1 - (i+.5) / len(legend_items)
                legend_ax.add_patch(Rectangle((0, y-.08/len(legend_items)), .12, .16/len(legend_items),
                                             transform=legend_ax.transAxes, facecolor=c, edgecolor="none"))
                legend_ax.text(.17, y, f"{a}: {v}", transform=legend_ax.transAxes, va="center", fontsize=7)
            ax = fig.add_subplot(grid[nrows, 1])
            cmap = COLORS["colormap"](signed, cfg.get("continuous_palette"))
            # pcolormesh preserves individually editable vector cells in SVG/PDF.
            mesh = ax.pcolormesh(np.ma.masked_invalid(values), cmap=cmap, vmin=lo, vmax=hi, rasterized=False)
            ax.set_ylim(len(genes), 0); ax.set_xlim(0, len(samples))
            ax.set_yticks(np.arange(len(genes))+.5, state["labels"])
            ax.set_xticks(np.arange(len(samples))+.5, [smap[s]["sample_label"] for s in samples], rotation=45, ha="right")
            ax.tick_params(length=0)
            for spine in ax.spines.values(): spine.set_visible(False)
            for i in range(1, len(samples)):
                if smap[samples[i]]["group"] != smap[samples[i-1]]["group"]:
                    ax.axvline(i, color="white", lw=1.5)
            for r, c in np.argwhere(np.isnan(values)):
                ax.text(c+.5, r+.5, "NA", ha="center", va="center", fontsize=6)
            color_label = "Row z-score" if signed else cfg["expression_layer"]
            color_ax = fig.add_subplot(side[1])
            color_ax.set_box_aspect(.08)
            cb = fig.colorbar(mesh, cax=color_ax, orientation="horizontal")
            cb.set_label(color_label)
            cb.solids.set_rasterized(False)
            if state["row_linkage"] is not None:
                dax = fig.add_subplot(grid[nrows, 0])
                dendrogram(state["row_linkage"], ax=dax, orientation="left", no_labels=True,
                           link_color_func=lambda _: "#555555")
                dax.invert_yaxis(); dax.set_axis_off()
            if cfg.get("show_title", False): fig.suptitle(title)
            out.mkdir(parents=True, exist_ok=False)
            CORE["save_figure"](fig, out / "figure.png", dpi=dpi)
        finally:
            plt.close(fig)
    COLORS["export_mapping"](out / "resolved_colors.tsv", maps)
    require(color_record == COLORS["record"](cfg, config.parent), "配色输入在运行中改变")
    if registry is not None:
        shutil.copyfile(registry, out / "input_color_registry.tsv")
    numeric = lambda n: "NA" if np.isnan(n) else repr(float(n))
    wide, readable, long = [], [], []
    for r, g in enumerate(genes):
        base = {"gene_id": g, "gene_symbol": state["gene_map"][g]}
        require(not set(samples) & set(base), "样本ID与导出固定字段冲突")
        wide.append(dict(base, **{s: numeric(values[r, c]) for c, s in enumerate(samples)}))
        readable.append(dict(base, **{s: "NA" if np.isnan(values[r, c]) else f"{values[r, c]:.3f}" for c, s in enumerate(samples)}))
        for c, s in enumerate(samples):
            long.append(dict(base, sample_id=s, sample_label=smap[s]["sample_label"], group=smap[s]["group"],
                             **{("row_zscore" if signed else "expression_value"): numeric(values[r, c])}))
    write_table(out / "heatmap_matrix.tsv", wide)
    write_table(out / "heatmap_readable.tsv", readable)
    write_table(out / "heatmap_long.tsv", long)
    write_table(out / "sample_metadata.tsv", [smap[s] for s in samples])
    write_table(out / "selected_genes.tsv", [{"gene_id": g, "gene_symbol": state["gene_map"][g],
                "display_label": label, "row_order": i+1} for i, (g, label) in enumerate(zip(genes, state["labels"]))])
    for key, path in state["paths"].items():
        shutil.copyfile(path, out / ("input_" + key + path.suffix))
        require(digest(path) == state["hashes"][key], "输入在运行中发生变化，拒绝交付")
    if "differential_results" in state["paths"]:
        results = read_table(state["paths"]["differential_results"])
        for r in results:
            r["gene_symbol"] = state["gene_map"].get(r["gene_id"], r.get("gene_symbol", ""))
        write_table(out / "differential_results.tsv", results)
    manifest = dict(status="rendered_visual_review_required", created_at=datetime.now(timezone.utc).isoformat(),
                    config=cfg, color_record=color_record, continuous_palette=cfg.get("continuous_palette", "blue_white_pink" if signed else "blue_sequential"), input_sha256=state["hashes"], config_sha256=digest(config),
                    script_sha256=digest(__file__), python=sys.version, numpy=np.__version__,
                    scipy=scipy.__version__, matplotlib=matplotlib.__version__,
                    gene_order=genes, sample_order=samples, annotation_colors=maps,
                    row_scale=state["scale"], zscore_ddof=1 if signed else None,
                    color_limits=[lo, hi], missing_cells=int(np.isnan(values).sum()),
                    row_linkage=state["row_linkage"].tolist() if state["row_linkage"] is not None else None,
                    cluster_cols=state["column_clustering"], distance=state["distance"], linkage=state["linkage"],
                    generated_statistics=False, differential_results="provided" if "differential_results" in cfg else "not_provided")
    CORE["dump"](out / "figure_manifest.json", manifest)
    CORE["dump"](out / "config.json", cfg)
    caption = (f"表达模式热图：{len(genes)}个基因，{len(samples)}个样本列。统计独立单位以原分析设计为准。\n\n"
               f"表达层：{cfg['expression_layer']}；来源/变换：{cfg['expression_provenance']}。"
               f"注释来源：{cfg['annotation_source']}。筛选规则：{cfg['selection']}。\n\n"
               f"绘图处理：{state['scale']}；" + ("行z-score采用样本标准差(ddof=1)，颜色仅表示同一基因在所列样本中的相对值。" if signed else "未做行标准化，颜色表示已声明表达尺度。") +
               f"色阶范围：{lo:.6g}至{hi:.6g}，无截断；缺失单元格{manifest['missing_cells']}个，以灰色NA标记。\n\n"
               f"行聚类：{cfg.get('cluster_rows', False)}；列聚类：{state['column_clustering']}（仅影响顺序，不绘列树）；"
               f"聚类使用实际绘图矩阵，距离{state['distance']}，链接{state['linkage']}。最终顺序见源表及运行记录。\n\n"
               f"比较：{cfg.get('contrast', '未提供差异比较，本图不生成统计检验')}。"
               f"分析记录：{cfg.get('analysis_provenance', '未提供')}。热图不是独立的分组验证，也不提供因果或机制证据。\n\n"
               "heatmap_matrix.tsv和heatmap_long.tsv保留实际作图精度；heatmap_readable.tsv仅显示三位小数。"
               "完整输入和样本映射另行交付；差异结果仅在真实提供时交付，不从z-score推断。\n\n"
               "![热图](figure.png)\n\n[PDF](figure.pdf) · [SVG](figure.svg)\n\n"
               "导出与有限技术检查已完成；最终物理尺寸下的版式、科学解释和目标期刊要求仍需审阅。\n")
    (out / "caption.md").write_text(caption, encoding="utf-8")
    return manifest


def render(config, out):
    config, out = Path(config), Path(out)
    require(not out.exists() and not out.is_symlink(), "输出目录已存在，拒绝覆盖")
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".expression-", dir=out.parent) as folder:
            staged = Path(folder) / "result"
            result = render_into(config, staged)
            require(not out.exists() and not out.is_symlink(), "输出目录被其他运行占用")
            staged.rename(out)
        return result
    except Exception as error:
        fd, name = tempfile.mkstemp(prefix=out.name + "-failure-", suffix=".json", dir=out.parent)
        os.close(fd)
        CORE["dump"](name, dict(status="failed", error=str(error), config=str(config),
                               created_at=datetime.now(timezone.utc).isoformat()))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        render(args.config, args.out_dir)
        print(f"图表已导出，需检查最终预览：{args.out_dir}")
        return 0
    except Exception as error:
        print(f"表达热图失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
