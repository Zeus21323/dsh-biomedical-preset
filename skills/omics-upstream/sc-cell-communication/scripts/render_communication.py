#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "matplotlib==3.10.6"]
# ///
"""从已支持通讯边与可检验细胞对生成描述性图集；不执行通讯推断或差异检验。"""
from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]

import argparse
import csv
import hashlib
import json
import math
import platform
import shutil
import sys
import warnings
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def read_tsv(path, fields):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not set(fields) <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: 缺列 {sorted(set(fields) - set(reader.fieldnames or []))}")
        rows = list(reader)
    for row in rows:
        if None in row or any(not str(row.get(k) or "").strip() for k in fields):
            raise ValueError(f"{path}: 空字段或列数错误")
        for k in fields:
            row[k] = row[k].strip()
    return rows


def write_tsv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_figure_quality(fig):
    """Technical preflight only; visual and biological review remain separate."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width_mm, height_mm = (float(x) * 25.4 for x in fig.get_size_inches())
    problems = []
    if min(abs(width_mm - x) for x in (89, 183)) > .1 or height_mm > 170.1:
        problems.append("物理尺寸不符合本配置的89/183 mm宽、最大170 mm高")
    texts = list(fig.texts)
    for ax in fig.axes:
        texts.extend([ax.title, *ax.texts])
        if ax.axison:
            texts.extend([ax.xaxis.label, ax.yaxis.label, ax.xaxis.offsetText, ax.yaxis.offsetText,
                          *(t for loc, t in zip(ax.get_xticks(), ax.get_xticklabels()) if min(ax.get_xlim()) <= loc <= max(ax.get_xlim())),
                          *(t for loc, t in zip(ax.get_yticks(), ax.get_yticklabels()) if min(ax.get_ylim()) <= loc <= max(ax.get_ylim()))])
        legend = ax.get_legend()
        if legend is not None:
            texts.extend([legend.get_title(), *legend.get_texts()])
    for text in texts:
        if not text.get_visible() or not text.get_text().strip():
            continue
        size = text.get_fontsize()
        if not 5 <= size <= (8 if text.get_gid() == "panel_letter" else 7):
            problems.append(f"字号超范围: {text.get_text()[:50]} ({size:g} pt)")
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > fig.bbox.width + 1 or box.y1 > fig.bbox.height + 1:
            problems.append(f"文字超出画布: {text.get_text()[:50]}")
    problems.extend(str(w.message) for w in caught if "Glyph" in str(w.message) or "constrained_layout" in str(w.message))
    return dict(status="passed" if not problems else "needs_revision", width_mm=width_mm, height_mm=height_mm,
                issues=list(dict.fromkeys(problems)), visual_review="pending")


def compose_summary(out, manifest):
    """Arrange unscaled vector panels; PNG is explicitly a preview, not vector artwork."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib import font_manager
    entries = {f["id"]: f for f in manifest["figures"] if f["status"] == "generated"
               and f.get("technical_quality", {}).get("status") == "passed"}
    def fits(name, max_height):
        q = entries.get(name, {}).get("technical_quality", {})
        return abs(q.get("width_mm", 0) - 89) < .1 and q.get("height_mm", 999) <= max_height + .1
    names = ["network_count", "pathway_chord" if fits("pathway_chord", 89) else "sender_receiver_roles",
             "lr_counts_01", "heatmap_weight"]
    if any(not fits(n, h) for n, h in zip(names, (89, 89, 78, 78))):
        manifest["summary_figure"] = dict(status="not_applicable", reason="当前面板需双栏或更大高度，必须按实际内容另排主图，禁止缩字凑版")
        return
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}svg", width="183mm", height="170mm", viewBox="0 0 183 170")
    ET.SubElement(root, f"{{{ns}}}title").text = f"{manifest['config']['dataset']}: descriptive communication summary"
    ET.SubElement(root, f"{{{ns}}}rect", width="183", height="170", fill="white")
    dpi = 600
    pixels = lambda mm: round(mm / 25.4 * dpi)
    preview = Image.new("RGB", (pixels(183), pixels(170)), "white")
    font = ImageFont.truetype(font_manager.findfont(font_manager.FontProperties(family=manifest["font_family"], weight="bold")), round(8 / 72 * dpi))
    for letter, name, x, y in zip("abcd", names, (0, 94, 0, 94), (0, 0, 92, 92)):
        entry = entries[name]
        height = entry["technical_quality"]["height_mm"]
        node = ET.parse(out / f"{name}.svg").getroot()
        ids = {el.attrib["id"]: f"{letter}_{el.attrib['id']}" for el in node.iter() if "id" in el.attrib}
        for el in node.iter():
            for key, val in list(el.attrib.items()):
                if key == "id":
                    el.set(key, ids[val])
                else:
                    for old, new in ids.items():
                        val = val.replace(f"url(#{old})", f"url(#{new})")
                    if val.startswith("#") and val[1:] in ids:
                        val = "#" + ids[val[1:]]
                    el.set(key, val)
        node.attrib.update(x=str(x), y=str(y), width="89", height=str(height))
        root.append(node)
        ET.SubElement(root, f"{{{ns}}}text", x=str(x + 1), y=str(y + 4),
                      style=f"font: bold 8pt '{manifest['font_family']}'; fill: black").text = letter
        with Image.open(out / f"{name}.png") as panel:
            preview.paste(panel.convert("RGB"), (pixels(x), pixels(y)))
        ImageDraw.Draw(preview).text((pixels(x + 1), pixels(y + .7)), letter, font=font, fill="black")
    ET.ElementTree(root).write(out / "communication_summary.svg", encoding="utf-8", xml_declaration=True)
    import fitz
    # Compose original vector PDF panels directly; do not rasterize SVG or depend on system Cairo.
    combined = fitz.open()
    page = combined.new_page(width=183*72/25.4, height=170*72/25.4)
    for letter, name, x, y in zip("abcd", names, (0,94,0,94), (0,0,92,92)):
        height = entries[name]["technical_quality"]["height_mm"]
        with fitz.open(out / f"{name}.pdf") as panel_pdf:
            page.show_pdf_page(fitz.Rect(x*72/25.4,y*72/25.4,(x+89)*72/25.4,(y+height)*72/25.4),panel_pdf,0)
        page.insert_text(((x+1)*72/25.4,(y+4)*72/25.4),letter,fontsize=8,fontname="hebo")
    combined.save(out / "communication_summary.pdf")
    combined.close()
    with fitz.open(out / "communication_summary.pdf") as pdf:
        if len(pdf) != 1 or abs(pdf[0].rect.width * 25.4 / 72 - 183) > .1:
            raise ValueError("组合PDF页数或物理尺寸不匹配")
        # Inspect the actual PDF rendering; keep vector PDF/SVG as editing originals.
        pdf[0].get_pixmap(dpi=150).save(out / "communication_summary_pdf_preview.png")
    preview.save(out / "communication_summary.png", dpi=(dpi, dpi))
    manifest["summary_figure"] = dict(status="generated", panels=dict(zip("abcd", names)),
                                      files=["communication_summary.svg", "communication_summary.png", "communication_summary.pdf"],
                                      width_mm=183, height_mm=170, text_rescaled=False, visual_review="pending",
                                      note="SVG保留矢量文字和图形；PNG为整版预览；这不是对真实数据的科学验收。")


def load_inputs(config_path):
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    required = ("dataset", "condition", "method", "method_version", "database", "score_name",
                "score_semantics", "selection_rule", "analysis_unit", "edges", "tested_pairs")
    for key in required:
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise ValueError(f"config 缺少非空字符串: {key}")
    if cfg["score_semantics"] != "nonnegative_additive_strength":
        raise ValueError("仅支持非负可加、越大越强的分数；rank/P 值/差异分数应使用原生图")
    if cfg["analysis_unit"] not in {"donor", "pooled"}:
        raise ValueError("analysis_unit 必须为 donor 或 pooled")
    for key, default in (("top_pathways", 3), ("top_lr", 20), ("max_chord_links", 24)):
        cfg.setdefault(key, default)
        if type(cfg[key]) is not int or not 1 <= cfg[key] <= 100:
            raise ValueError(f"{key} 必须是 1–100 的整数")
    paths = {k: (config_path.parent / cfg[k]).resolve() for k in ("edges", "tested_pairs")}
    pairs = read_tsv(paths["tested_pairs"], ("sample", "donor", "source", "target"))
    edges = read_tsv(paths["edges"], ("sample", "source", "target", "interaction", "ligand", "receptor", "pathway", "score"))
    if not pairs:
        raise ValueError("没有可检验细胞对，不能将缺失补零")
    sample_donor, donor_sample, pair_keys = {}, {}, set()
    for row in pairs:
        sample, donor = row["sample"], row["donor"]
        if sample in sample_donor and sample_donor[sample] != donor:
            raise ValueError("同一 sample 对应多个 donor")
        if donor in donor_sample and donor_sample[donor] != sample:
            raise ValueError("重复 donor 被作为独立 sample；请先按研究设计汇总")
        sample_donor[sample], donor_sample[donor] = donor, sample
        key = sample, row["source"], row["target"]
        if key in pair_keys:
            raise ValueError(f"重复可检验细胞对: {key}")
        pair_keys.add(key)
    if cfg["analysis_unit"] == "pooled" and len(sample_donor) != 1:
        raise ValueError("pooled 模式只接受一个池化 sample")
    seen, annotations = set(), {}
    for row in edges:
        key = row["sample"], row["source"], row["target"]
        if key not in pair_keys:
            raise ValueError(f"通讯边不在可检验范围: {key}")
        unique = (*key, row["interaction"])
        if unique in seen:
            raise ValueError(f"重复 LR 边: {unique}")
        seen.add(unique)
        annotation = row["ligand"], row["receptor"], row["pathway"]
        if row["interaction"] in annotations and annotations[row["interaction"]] != annotation:
            raise ValueError(f"同一 interaction 的复合体/通路映射不一致: {row['interaction']}")
        annotations[row["interaction"]] = annotation
        row["score"] = float(row["score"])
        if not math.isfinite(row["score"]) or row["score"] < 0:
            raise ValueError("score 必须有限且非负")
    cells = sorted({r[k] for r in pairs for k in ("source", "target")})
    for key in ("focus_sources", "focus_targets"):
        cfg.setdefault(key, [])
        if not isinstance(cfg[key], list) or any(not isinstance(x, str) for x in cfg[key]):
            raise ValueError(f"{key} 必须为细胞标签列表")
        if len(set(cfg[key])) != len(cfg[key]) or set(cfg[key]) - set(cells):
            raise ValueError(f"{key} 有重复或不存在的标签")
    cfg.setdefault("cell_order", cells)
    if not isinstance(cfg["cell_order"], list) or sorted(cfg["cell_order"]) != cells:
        raise ValueError("cell_order 必须恰好包含所有细胞标签一次")
    return cfg, edges, pairs, paths


def summarize(cfg, edges, pairs):
    eligible, by_sample = defaultdict(list), defaultdict(list)
    for r in pairs:
        eligible[r["source"], r["target"]].append(r["sample"])
    for r in edges:
        by_sample[r["sample"], r["source"], r["target"]].append(r)
    sample_rows, pair_rows = [], []
    for (source, target), samples in sorted(eligible.items()):
        current = []
        for sample in sorted(samples):
            rows = by_sample[sample, source, target]
            record = dict(sample=sample, source=source, target=target, count=len(rows),
                          weight=sum(r["score"] for r in rows))
            sample_rows.append(record)
            current.append(record)
        pair_rows.append(dict(source=source, target=target, n_tested=len(samples),
                              count=sum(r["count"] for r in current) / len(samples),
                              weight=sum(r["weight"] for r in current) / len(samples)))
    for metric in ("count", "weight"):
        if any(not math.isfinite(r[metric]) for r in pair_rows):
            raise ValueError("聚合分数溢出")
    outgoing = defaultdict(float)
    for r in pair_rows:
        outgoing[r["source"]] += r["count"]
    sources = cfg["focus_sources"] or sorted(outgoing, key=lambda c: (-outgoing[c], c))[:1]
    targets = cfg["focus_targets"] or cfg["cell_order"]
    ranks = {}
    for kind in ("interaction", "pathway"):
        grouped = defaultdict(list)
        for row in edges:
            grouped[row["source"], row["target"], row[kind]].append(row)
        records = []
        for (source, target, name), rows in grouped.items():
            n = len(eligible[source, target])
            supported = len({r["sample"] for r in rows})
            records.append(dict(source=source, target=target, name=name, n_tested=n,
                                n_supported=supported, support=supported / n,
                                mean_filtered_score=sum(r["score"] for r in rows) / n))
        records.sort(key=lambda r: (-r["support"], -r["mean_filtered_score"], r["source"], r["target"], r["name"]))
        ranks[kind] = records
    selected = {}
    for kind, cap in (("interaction", cfg["top_lr"]), ("pathway", cfg["top_pathways"])):
        names = [r["name"] for r in ranks[kind] if r["source"] in sources and r["target"] in targets
                 and not (kind == "pathway" and r["name"] == "Unassigned")]
        selected[kind] = list(dict.fromkeys(names))[:cap]
    return dict(pairs=pair_rows, samples=sample_rows, ranks=ranks, sources=sources, targets=targets, selected=selected)


def render(cfg, data, out, manifest):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.patches import FancyArrowPatch, PathPatch, Wedge
    from matplotlib.path import Path as MPath
    from matplotlib.colors import is_color_like
    from matplotlib import font_manager

    style_path = Path(__file__).resolve().parent.parent / "assets/communication-nature.mplstyle"
    plt.style.use(style_path)
    manifest["figure_style"] = dict(name="communication-nature", sha256=sha(style_path),
                                    source="Nature figure guide; project-owned preset")
    shutil.copyfile(style_path, out / "communication-nature.mplstyle")
    family = cfg.get("font_family")
    if family is not None:
        if not isinstance(family, str):
            raise ValueError("font_family 必须为字体名称")
        font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
    else:
        available = {f.name for f in font_manager.fontManager.ttflist}
        labels = " ".join([cfg["dataset"], cfg["condition"], *cfg["cell_order"]])
        needs_cjk = any("\u3400" <= c <= "\u9fff" for c in labels)
        candidates = ("Noto Sans CJK SC", "PingFang SC", "Heiti SC", "Arial Unicode MS") if needs_cjk else ("Arial", "Helvetica", "DejaVu Sans")
        family = next((f for f in candidates if f in available), "DejaVu Sans")
    plt.rcParams["font.family"] = [family, "DejaVu Sans"]
    manifest["font_family"] = family
    cells = cfg["cell_order"]
    supplied = cfg.get("colors", {})
    if not isinstance(supplied, dict) or set(supplied) - set(cells) or any(not is_color_like(v) for v in supplied.values()):
        raise ValueError("colors 必须是实际细胞标签到有效颜色的映射")
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#333333", "#999933"]
    colors = {c: supplied.get(c, palette[i % len(palette)]) for i, c in enumerate(cells)}
    manifest["colors"] = colors
    manifest["environment"] = dict(python=platform.python_version(), numpy=np.__version__, matplotlib=matplotlib.__version__)
    actual = {k: max((r[k] for r in data["pairs"]), default=0) for k in ("count", "weight")}
    actual.update({k: max((r["mean_filtered_score"] for r in data["ranks"][kind]), default=0)
                   for k, kind in (("lr", "interaction"), ("pathway", "pathway"))})
    scales = cfg.get("scales", {})
    if not isinstance(scales, dict) or set(scales) - set(actual):
        raise ValueError("scales 只接受 count/weight/lr/pathway")
    for key, value in scales.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0 or value < actual[key]:
            raise ValueError(f"{key} 尺度无效或会截断数据")
    limits = {key: scales.get(key, value or 1) for key, value in actual.items()}
    manifest["scales"] = limits
    manifest["notes"] += ["网络节点等大，颜色为细胞类型；箭头为发送到接收。",
                           "数量/强度按可检验样本等权平均；缺失细胞对不补零。",
                           "气泡面积为支持样本比例，颜色为平均过滤后分数；不是 P 值。",
                           "角色为聚合入向/出向分数；弦图按自身总量布局，带宽不能跨图直接比绝对量。"]

    def emit(name, rows, draw, caption):
        entry = dict(id=name, status="failed", caption=caption, files=[], source=f"{name}.tsv")
        manifest["figures"].append(entry)
        if rows:
            write_tsv(out / entry["source"], rows, list(rows[0]))
        else:
            entry.update(status="not_applicable", reason="焦点范围无支持结果", source=None)
            return
        fig = None
        try:
            fig = draw()
            # Colorbars may rasterize themselves by default; retain editable geometry.
            for artist in fig.findobj():
                if hasattr(artist, "get_rasterized") and artist.get_rasterized():
                    artist.set_rasterized(False)
            entry["technical_quality"] = check_figure_quality(fig)
            entry["visual_review"] = "pending"
            for ext in ("png", "pdf", "svg"):
                path = out / f"{name}.{ext}"
                # No tight crop: preserve the declared physical print dimensions.
                save_figure(fig, path, dpi=600, bbox_inches=None, facecolor="white")
                entry["files"].append(path.name)
            entry["status"] = "generated"
        except Exception as error:
            entry["reason"] = str(error)
        finally:
            if fig is not None:
                plt.close(fig)
            plt.close("all")

    def circle(rows, metric, title, vmax):
        labels = [c for c in cells if any(c in (r["source"], r["target"]) for r in rows)]
        # Larger networks use a ranked subset; full data and retained nodes stay traceable.
        if len(labels) > 18:
            totals = {c: sum(r[metric] for r in rows if c in (r["source"], r["target"])) for c in labels}
            keep = set(sorted(labels, key=lambda c: (-totals[c], c))[:18])
            labels = [c for c in labels if c in keep]
            title += " (top 18)"
        fig, ax = plt.subplots(figsize=(89 / 25.4, 83 / 25.4), layout="constrained")
        theta = np.linspace(math.pi / 2, math.pi / 2 + 2 * math.pi, len(labels), endpoint=False)
        pos = {c: np.array([math.cos(t), math.sin(t)]) for c, t in zip(labels, theta)}
        for r in rows:
            a, b, value = r["source"], r["target"], r[metric]
            if value <= 0 or a not in pos or b not in pos:
                continue
            p, q = pos[a], pos[b]
            if a == b:
                tangent = np.array([-p[1], p[0]]) * 0.12
                start, end, rad = p + tangent, p - tangent, 1.4
            else:
                start, end, rad = p, q, 0.16
            ax.add_patch(FancyArrowPatch(start, end, connectionstyle=f"arc3,rad={rad}",
                                         arrowstyle="-|>", mutation_scale=6, shrinkA=4, shrinkB=4,
                                         linewidth=0.25 + 0.75 * value / vmax, color=colors[a], alpha=0.8))
        for c, p in pos.items():
            ax.scatter(*p, s=30, color=colors[c], edgecolor="white", zorder=3)
            ax.text(*(p * 1.22), c, ha="center", va="center", fontsize=6)
        ax.set(xlim=(-1.45, 1.45), ylim=(-1.42, 1.42), aspect="equal", title=title)
        handles = [plt.Line2D([], [], color="#666666", lw=.25 + .75 * f, label=f"{vmax * f:.2g}") for f in (.25, .5, 1)]
        ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, -.03), ncol=3,
                  title="Edge value", handlelength=1.4, columnspacing=.8, borderaxespad=0)
        ax.axis("off")
        return fig

    def heatmap(metric):
        matrix = np.full((len(cells), len(cells)), np.nan)
        for r in data["pairs"]:
            matrix[cells.index(r["source"]), cells.index(r["target"])] = r[metric]
        width = 89 if len(cells) <= 10 else 183
        fig, ax = plt.subplots(figsize=(width / 25.4, min(170, max(74, len(cells) * 4.5)) / 25.4), layout="constrained")
        cmap = plt.get_cmap("cividis").copy()
        cmap.set_bad("#dedede")
        im = ax.pcolormesh(np.arange(len(cells) + 1) - .5, np.arange(len(cells) + 1) - .5,
                           matrix, cmap=cmap, vmin=0, vmax=limits[metric], shading="flat", rasterized=False)
        ax.invert_yaxis()
        ax.set_aspect("equal")
        ax.set(xticks=range(len(cells)), yticks=range(len(cells)), xticklabels=cells, yticklabels=cells,
               xlabel="Receiver", ylabel="Sender", title=f"Mean supported {metric}")
        plt.setp(ax.get_xticklabels(), rotation=60, ha="right")
        fig.colorbar(im, ax=ax, label="LR count" if metric == "count" else "Filtered score", shrink=.7, fraction=.05, pad=.04)
        return fig

    for metric in ("count", "weight"):
        emit(f"network_{metric}", data["pairs"], lambda m=metric: circle(data["pairs"], m, f"Mean supported {m}", limits[m]),
             f"每细胞对可检验样本内的平均 {metric}；大于18群时网络只显示按连接值排名前18群。")
        emit(f"heatmap_{metric}", data["pairs"], lambda m=metric: heatmap(m), "行发送、列接收；灰色未检验，颜色尺度见 manifest。")
    focused = [r for r in data["pairs"] if r["source"] in data["sources"] and r["target"] in data["targets"]]
    emit("focus_sender_network", focused, lambda: circle(focused, "count", "Focus sender interactions", limits["count"]),
         "焦点发送者数量网络；范围及自动/用户焦点见 selection.json。")

    lr = [r for r in data["ranks"]["interaction"] if r["name"] in data["selected"]["interaction"]
          and r["source"] in data["sources"] and r["target"] in data["targets"]]
    pair_order = list(dict.fromkeys((r["source"], r["target"]) for r in lr))

    def bubble(rows, pairs_page):
        names = data["selected"]["interaction"]
        width = 89 if len(pairs_page) <= 4 else 183
        fig, ax = plt.subplots(figsize=(width / 25.4, min(170, 36 + max(3, len(names)) * 4.2) / 25.4), layout="constrained")
        im = ax.scatter([pairs_page.index((r["source"], r["target"])) for r in rows],
                        [names.index(r["name"]) for r in rows], s=[32 * r["support"] for r in rows],
                        c=[r["mean_filtered_score"] for r in rows], vmin=0, vmax=limits["lr"], cmap="viridis")
        ax.set(xticks=range(len(pairs_page)), xticklabels=[f"{a} → {b}" for a, b in pairs_page],
               yticks=range(len(names)), yticklabels=names, title="Ligand–receptor candidates",
               xlim=(-.5, len(pairs_page) - .5), ylim=(len(names) - .5, -.5))
        plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
        fig.colorbar(im, ax=ax, label="Mean filtered score", shrink=.8, fraction=.025, pad=.025)
        handles = [ax.scatter([], [], s=32 * s, color="#888888", label=f"{s:.0%}") for s in (.25, .5, 1)]
        ax.legend(handles=handles, title="Sample support", loc="center left", bbox_to_anchor=(1.2, .5), frameon=False)
        return fig

    if not pair_order:
        emit("lr_bubble", [], lambda: None, "焦点无可绘制 LR。")
    for i in range(0, len(pair_order), 12):
        page = pair_order[i:i + 12]
        rows = [r for r in lr if (r["source"], r["target"]) in page]
        emit(f"lr_bubble_{i // 12 + 1:02}", rows, lambda rr=rows, pp=page: bubble(rr, pp),
             "气泡面积为支持/可检验样本比例，颜色为平均过滤后强度；未画气泡不代表全部已检验。")

    roles = [dict(cell=c, outgoing=sum(r["weight"] for r in data["pairs"] if r["source"] == c),
                  incoming=sum(r["weight"] for r in data["pairs"] if r["target"] == c)) for c in cells]

    def role_plot():
        fig, ax = plt.subplots(figsize=(89 / 25.4, 78 / 25.4), layout="constrained")
        for r in roles:
            ax.scatter(r["outgoing"], r["incoming"], color=colors[r["cell"]], s=24)
            ax.annotate(r["cell"], (r["outgoing"], r["incoming"]), xytext=(4, 4), textcoords="offset points", fontsize=6)
        ax.margins(.3)
        ax.set(xlabel="Outgoing score", ylabel="Incoming score", title="Sender–receiver roles")
        return fig
    emit("sender_receiver_roles", roles, role_plot, "每细胞对平均过滤后分数的入向/出向求和；不是原生centrality或统计检验。")

    count_rows = [r for r in data["samples"] if r["source"] in data["sources"] and r["target"] in data["targets"]]
    count_pairs = [(r["source"], r["target"]) for r in focused]

    def count_plot(rows, page):
        width = 89 if len(page) <= 4 else 183
        fig, ax = plt.subplots(figsize=(width / 25.4, 78 / 25.4), layout="constrained")
        for i, (a, b) in enumerate(page):
            vals = [r["count"] for r in rows if r["source"] == a and r["target"] == b]
            ax.bar(i, np.mean(vals), color=colors[a], alpha=.75, width=.6)
            offsets = np.linspace(-.18, .18, len(vals)) if len(vals) > 1 else [0]
            ax.scatter(i + np.array(offsets), vals, s=7, color="#333333", zorder=3)
        ax.set(xticks=range(len(page)), xticklabels=[f"{a} → {b}" for a, b in page],
               ylabel="Supported LR count", title="Interactions by cell pair")
        ymax = max(1, max(r["count"] for r in rows))
        ax.set_ylim(-.04 * ymax, 1.12 * ymax)
        plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
        return fig
    for i in range(0, len(count_pairs), 12):
        page = count_pairs[i:i + 12]
        rows = [r for r in count_rows if (r["source"], r["target"]) in page]
        emit(f"lr_counts_{i // 12 + 1:02}", rows, lambda rr=rows, pp=page: count_plot(rr, pp),
             "柱为可检验独立样本平均支持LR数；点为样本，不提供差异P值。")
    if not count_pairs:
        emit("lr_counts", [], lambda: None, "焦点范围没有可检验细胞对。")

    if not data["selected"]["pathway"]:
        emit("pathway_network", [], lambda: None, "焦点无已映射通路的支持边；不能推测通路归属。")
    for i, pathway in enumerate(data["selected"]["pathway"]):
        rows = [r for r in data["ranks"]["pathway"] if r["name"] == pathway
                and r["source"] in data["sources"] and r["target"] in data["targets"]]
        emit(f"pathway_network_{i + 1:02}", rows,
             lambda rr=rows, p=pathway: circle(rr, "mean_filtered_score", p, limits["pathway"]),
             f"通路 {pathway}，焦点范围内已支持LR的平均分数之和；所有通路网络共用尺度。")

    chord_rows = [dict(source=r["source"], target=r["target"], pathway=r["name"], weight=r["mean_filtered_score"])
                  for r in data["ranks"]["pathway"] if r["name"] in data["selected"]["pathway"]
                  and r["source"] in data["sources"] and r["target"] in data["targets"] and r["mean_filtered_score"] > 0]
    chord_rows.sort(key=lambda r: (-r["weight"], r["source"], r["target"], r["pathway"]))
    omitted = max(0, len(chord_rows) - cfg["max_chord_links"])
    chord_rows = chord_rows[:cfg["max_chord_links"]]

    def chord():
        # Separate sending (cell, pathway) sectors and receiving cell sectors.
        links = [(("send", r["source"], r["pathway"]), ("receive", r["target"], ""), r) for r in chord_rows]
        sectors = sorted({a for a, _, _ in links}) + sorted({b for _, b, _ in links})
        totals = {s: sum(r["weight"] for a, b, r in links if s == a or s == b) for s in sectors}
        gap = min(.045, math.pi / len(sectors))
        unit = (2 * math.pi - gap * len(sectors)) / sum(totals.values())
        cursor, ranges, start = {}, {}, math.pi / 2
        width = 89 if len(sectors) <= 6 else 183
        fig, ax = plt.subplots(figsize=(width / 25.4, min(width, 155) / 25.4), layout="constrained")
        for sector in sectors:
            end = start + totals[sector] * unit
            ranges[sector], cursor[sector] = (start, end), start
            ax.add_patch(Wedge((0, 0), 1.04, math.degrees(start), math.degrees(end), width=.07, facecolor=colors[sector[1]], edgecolor="white"))
            mid = (start + end) / 2
            label = f"{sector[1]}\n{sector[2]}" if sector[0] == "send" else f"{sector[1]}\nreceiver"
            ax.text(1.12 * math.cos(mid), 1.12 * math.sin(mid), label, fontsize=6,
                    ha="left" if math.cos(mid) > .1 else "right" if math.cos(mid) < -.1 else "center", va="center")
            start = end + gap
        for a, b, r in links:
            span = r["weight"] * unit
            a0, b0 = cursor[a], cursor[b]
            a1, b1 = a0 + span, b0 + span
            arc_a = [(math.cos(t), math.sin(t)) for t in np.linspace(a0, a1, 12)]
            arc_b = [(math.cos(t), math.sin(t)) for t in np.linspace(b0, b1, 12)]
            verts = arc_a + [(0, 0), arc_b[0]] + arc_b[1:] + [(0, 0), arc_a[0], arc_a[0]]
            codes = [MPath.MOVETO] + [MPath.LINETO] * 11 + [MPath.CURVE3] * 2 + [MPath.LINETO] * 11 + [MPath.CURVE3] * 2 + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), facecolor=colors[a[1]], edgecolor="white", linewidth=.25, alpha=.5))
            cursor[a], cursor[b] = a1, b1
        ax.set(xlim=(-1.6, 1.6), ylim=(-1.35, 1.35), aspect="equal", title="Sender–pathway–receiver")
        ax.axis("off")
        return fig
    emit("pathway_chord", chord_rows, chord, f"发送群|通路→接收群；带宽为平均过滤后强度；截去{omitted}条低权重联系；所画联系见源表。")


def execute(config_path, out_dir):
    cfg, edges, pairs, paths = load_inputs(config_path)
    data = summarize(cfg, edges, pairs)
    out = Path(out_dir).resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("输出目录必须不存在或为空，禁止覆盖历史结果")
    out.mkdir(parents=True, exist_ok=True)
    manifest = dict(status="running", config=cfg, input_sha256={k: sha(p) for k, p in paths.items()},
                    config_sha256=sha(config_path), script_sha256=sha(__file__), figures=[], conditional_panels={}, notes=[])
    if len({r["donor"] for r in pairs}) < 2:
        manifest["notes"].append("只有一个分析单位：结果仅作描述，不能推断供体重复性或组间差异。")
    shutil.copyfile(paths["edges"], out / "input_edges.tsv")
    shutil.copyfile(paths["tested_pairs"], out / "input_tested_pairs.tsv")
    write_json(out / "run_config.json", {**cfg, "edges": "input_edges.tsv", "tested_pairs": "input_tested_pairs.tsv"})
    write_tsv(out / "pair_summary.tsv", data["pairs"], ["source", "target", "n_tested", "count", "weight"])
    write_tsv(out / "sample_counts.tsv", data["samples"], ["sample", "source", "target", "count", "weight"])
    for kind, records in data["ranks"].items():
        write_tsv(out / f"{kind}_ranking.tsv", records,
                  ["source", "target", "name", "n_tested", "n_supported", "support", "mean_filtered_score"])
    write_json(out / "selection.json", dict(sources=data["sources"], targets=data["targets"], selected=data["selected"],
               source_reason="user" if cfg["focus_sources"] else "highest outgoing mean supported LR count; exploratory",
               rank_rule="support fraction descending, mean filtered score descending; lexical tie-break"))
    try:
        if not edges:
            manifest["status"] = "no_supported_edges"
            manifest["notes"].append("选择规则下无支持边；保留空结果，不降低阈值凑图。")
            for name in ("network_count", "network_weight", "heatmap_count", "heatmap_weight", "focus_sender_network",
                         "lr_bubble", "sender_receiver_roles", "lr_counts", "pathway_network", "pathway_chord"):
                manifest["figures"].append(dict(id=name, status="not_applicable", reason="没有通过上游选择规则的通讯边"))
        else:
            render(cfg, data, out, manifest)
            compose_summary(out, manifest)
            failed = any(f["status"] == "failed" for f in manifest["figures"])
            needs_revision = any(f.get("technical_quality", {}).get("status") == "needs_revision" for f in manifest["figures"])
            manifest["status"] = "partial" if failed else "needs_visual_revision" if needs_revision else "core_figures_generated"
    except Exception as error:
        manifest.update(status="partial", error=str(error))
    write_json(out / "figure_manifest.json", manifest)
    lines = [f"# {cfg['dataset']} / {cfg['condition']} 通讯核心图集", "", f"状态：{manifest['status']}", "",
             f"方法：{cfg['method']} {cfg['method_version']}；数据库：{cfg['database']}", "",
             f"选择规则：{cfg['selection_rule']}", "", "这是描述性图集；条件统计、UMAP、功能评分与临床关联仍需按任务输入处理。", ""]
    lines.extend(f"- {note}" for note in manifest["notes"])
    lines.extend(["", "风格与文件生成不等于投稿质量合格：技术检查和实际视觉审查分别记录。"])
    if manifest.get("summary_figure", {}).get("status") == "generated":
        lines.extend(["", "## 整版预览", "", "[可编辑矢量整版](communication_summary.svg) · [PDF整版](communication_summary.pdf)", "", "![整版预览](communication_summary.png)"])
    for fig in manifest["figures"]:
        lines.extend(["", f"## {fig['id']} — {fig['status']}", "", fig.get("caption", fig.get("reason", ""))])
        if fig.get("reason") and fig["status"] == "failed":
            lines.append(f"失败：{fig['reason']}")
        if fig.get("technical_quality"):
            lines.append(f"技术检查：{fig['technical_quality']['status']}；视觉检查：{fig.get('visual_review', 'pending')}")
            lines.extend(f"- {issue}" for issue in fig["technical_quality"]["issues"])
        if fig["status"] == "generated":
            lines.extend(["", f"![{fig['id']}]({fig['id']}.png)"])
    (out / "figure_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = execute(args.config, args.out_dir)
        print(json.dumps({"status": manifest["status"], "out_dir": str(args.out_dir.resolve())}, ensure_ascii=False))
        return 1 if manifest["status"] in {"partial", "needs_visual_revision"} else 0
    except (ValueError, OSError) as error:
        print(f"输入/执行错误：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
