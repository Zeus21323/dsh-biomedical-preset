#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "matplotlib==3.10.6", "scipy==1.16.1", "pypdf==6.1.1"]
# ///
"""One command: native per-sample inference/reuse, conditional figures and delivery checks."""
from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]

import argparse
import json
import re
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np

from render_communication import check_figure_quality, read_tsv, write_json, write_tsv, sha
from compare_communication import render_comparison
from render_context import render_context


def validate_delivery(root, entries):
    """File/vector preflight, not a claim of visual or scientific acceptance."""
    root = Path(root).resolve()
    failures = []
    for entry in entries:
        if entry["status"] != "generated":
            if entry["status"] == "failed":
                failures.append(f"{entry['id']}: 生成失败")
            continue
        issues = []
        files = entry.get("files", [])
        if {Path(p).suffix for p in files} < {".png", ".pdf", ".svg"}:
            issues.append("缺少 PNG/PDF/SVG")
        for relative in files:
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
                issues.append(f"文件缺失、空文件或超出输出目录: {relative}")
                continue
            if entry.get('width_mm') and entry.get('height_mm'):
                expected=(float(entry['width_mm']),float(entry['height_mm']))
                try:
                    if path.suffix=='.png':
                        import struct
                        with path.open('rb') as stream:header=stream.read(24)
                        if header[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('invalid PNG signature')
                        width,height=struct.unpack('>II',header[16:24])
                        if any(abs(actual-mm/25.4*600)>2 for actual,mm in zip((width,height),expected)):
                            issues.append('PNG实际像素与声明物理尺寸/600dpi不符')
                    elif path.suffix=='.pdf':
                        from pypdf import PdfReader
                        page=PdfReader(path).pages[0]
                        actual=(float(page.mediabox.width)*25.4/72,float(page.mediabox.height)*25.4/72)
                        if any(abs(a-b)>.2 for a,b in zip(actual,expected)):issues.append('PDF页面物理尺寸与声明不符')
                except Exception as error:issues.append('图形尺寸不可验证: '+str(error))
            if path.suffix == ".svg":
                try:
                    node = ET.parse(path).getroot()
                    images = [e for e in node.iter() if e.tag.rsplit("}", 1)[-1] == "image"]
                    allowed_images = set(entry.get("tissue_image_ids", []))
                    if any(not e.attrib.get("id") or e.attrib.get("id") not in allowed_images for e in images):
                        issues.append("SVG 含嵌入位图，需核查可编辑性")
                    if allowed_images and not entry.get("tissue_image_provenance"):
                        issues.append("组织图层缺少图像来源/配准说明")
                    texts = [e for e in node.iter() if e.tag.rsplit("}", 1)[-1] == "text"]
                    if not texts:
                        issues.append("SVG 无可编辑文字")
                    for e in texts:
                        style = e.attrib.get("style", "")
                        sizes = re.findall(r"font-size:\s*([\d.]+)(pt|px)", style)
                        for size, unit in sizes:
                            # svglite's viewBox and font units are both points despite CSS px.
                            if not 4.95 <= float(size) <= 8.05:
                                issues.append(f"SVG 字号待修正: {size}{unit}")
                except ET.ParseError:
                    issues.append("SVG 无法解析")
        src = entry.get("source_data")
        if not src or not (root / src).is_file():
            issues.append("缺少作图源表")
        previous = entry.get("technical_quality", {})
        issues.extend(previous.get("issues", []))
        issues.extend(w for w in entry.get("warnings", []) if any(k in w.lower() for k in ("outside", "overlap", "removed", "missing", "glyph")))
        entry["technical_quality"] = dict(status="needs_revision" if issues else "passed", issues=sorted(set(issues)))
        entry.setdefault("visual_review", "pending")
        if issues:
            failures.append(f"{entry['id']}: " + "; ".join(sorted(set(issues))))
    return failures


def descriptive_comparison(bundles, cfg, out, save):
    """Shared scales for harmonized sample networks; unavailable pairs remain NaN."""
    import matplotlib.pyplot as plt
    if len(bundles) < 2:
        return dict(status="not_applicable", reason="仅一个样本/对象")
    signatures = {b["provenance"].get("comparison_signature") for b in bundles}
    databases = {b["provenance"]["database_sha256"] for b in bundles}
    versions = {b["provenance"]["method_version"] for b in bundles}
    if len(signatures) != 1 or not next(iter(signatures), None) or len(databases) != 1 or len(versions) != 1:
        return dict(status="not_applicable", reason="未核实相同版本、数据库和比较参数；保留各对象独立图，不生成定量比较")
    # Verify machine-readable inference settings in addition to the investigator's signature.
    parameters = [b["provenance"].get("comparison_parameters") for b in bundles]
    if any(not x for x in parameters) or len({json.dumps(x, sort_keys=True) for x in parameters}) != 1:
        return dict(status="not_applicable", reason="原始推断参数未知或不一致，不能依靠手写签名放行定量比较")
    groups = sorted({r[k] for b in bundles for r in b["candidates"] for k in ("source", "target")})
    condition_order = cfg.get("condition_order", sorted({b["provenance"]["config"]["condition"] for b in bundles}))
    available_conditions = {b["provenance"]["config"]["condition"] for b in bundles}
    if set(condition_order) != available_conditions:
        raise ValueError("condition_order 必须完整且无重复地列出条件")
    pair_values = defaultdict(list); samples = []
    for bundle in bundles:
        metadata = bundle["provenance"]["config"]
        tested = {}; counts = defaultdict(float); weights = defaultdict(float)
        for row in bundle["candidates"]:
            if row["tested"] in ("TRUE", "True", True):
                pair = (row["source"], row["target"]); tested[pair] = True
                if row["supported"] in ("TRUE", "True", True):
                    counts[pair] += 1; weights[pair] += float(row["score"])
        for source, target in tested:
            pair_values[(metadata["condition"], source, target)].append((counts[(source, target)], weights[(source, target)]))
            samples.append(dict(sample=metadata["sample"], donor=metadata["donor"], condition=metadata["condition"], source=source,
                                target=target, count=counts[(source, target)], weight=weights[(source, target)]))
    write_tsv(out / "sample_networks.tsv", samples, ["sample", "donor", "condition", "source", "target", "count", "weight"])
    for mi, measure in enumerate(("count", "weight")):
        mats = []
        for condition in condition_order:
            mats.append(np.array([[np.mean([p[mi] for p in pair_values[(condition, s, t)]]) if pair_values[(condition, s, t)] else np.nan
                                   for t in groups] for s in groups]))
        vmax = max([float(np.nanmax(m)) for m in mats if np.isfinite(m).any()] or [1]) or 1
        cmap = plt.get_cmap("cividis").copy(); cmap.set_bad("#dddddd")
        for i, (condition, mat) in enumerate(zip(condition_order, mats)):
            fig, ax = plt.subplots(figsize=(183/25.4, 150/25.4), layout="constrained")
            theta = np.linspace(0, 2*np.pi, len(groups), endpoint=False)
            positions = np.c_[np.cos(theta), np.sin(theta)]
            cell_colors = bundles[0]["provenance"]["config"].get("colors", {})
            for si, (source, start_xy) in enumerate(zip(groups, positions)):
                for ti, end_xy in enumerate(positions):
                    value = mat[si, ti]
                    if not np.isfinite(value) or value <= 0:
                        continue
                    color = cell_colors.get(source, "#777777")
                    if si == ti:
                        # Outward small loop; it represents the actual diagonal entry.
                        tangent = np.array([-start_xy[1], start_xy[0]])
                        a = start_xy + tangent*.04; b = start_xy - tangent*.04
                        connection = "arc3,rad=-2"
                    else:
                        a, b, connection = start_xy, end_xy, "arc3,rad=.1"
                    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", lw=.3+2.7*value/vmax,
                                color=color, alpha=.5, connectionstyle=connection, shrinkA=4, shrinkB=4))
                available = np.isfinite(mat[si]).any() or np.isfinite(mat[:, si]).any()
                ax.scatter(*start_xy, s=35, color=cell_colors.get(source, "#777777") if available else "#dddddd", zorder=3)
                ax.text(*(start_xy*1.18), source, ha="center", va="center", fontsize=6)
            ax.set(xlim=(-1.5, 1.5), ylim=(-1.4, 1.4), aspect="equal"); ax.axis("off"); ax.set_title(f"{condition}: mean {measure}")
            ax.text(.5, .01, f"Maximum edge = {vmax:.3g}; grey nodes: unavailable", transform=ax.transAxes, ha="center", fontsize=6)
            save(f"conditions_network_{measure}_{i+1:02d}", fig, "sample_networks.tsv",
                 "从原生过滤网络按可检验样本等权汇总；所有条件共享节点顺序、颜色和边宽上限。灰节点无可检验样本，数量/强度为描述性比较。")
            # Tile large matrices at fixed type size; preserve global vmin/vmax.
            for start in range(0, len(groups), 16):
                fig, ax = plt.subplots(figsize=(183/25.4, 150/25.4), layout="constrained")
                im = ax.pcolormesh(np.ma.masked_invalid(mat[start:start+16]), cmap=cmap, vmin=0, vmax=vmax)
                ax.set_xticks(np.arange(len(groups))+.5, groups, rotation=60, ha="right")
                ax.set_yticks(np.arange(len(groups[start:start+16]))+.5, groups[start:start+16]); ax.invert_yaxis()
                ax.set_xlabel("Receiver"); ax.set_ylabel("Sender"); ax.set_title(condition)
                fig.colorbar(im, ax=ax, label=f"Mean supported {measure}", shrink=.7)
                save(f"conditions_{measure}_{i+1:02d}_{start//16+1:02d}", fig, "sample_networks.tsv",
                     "条件内样本等权平均；跨条件同色标。灰色表示没有可检验样本；候选筛选范围差异仍会影响数量。描述性比较。")
    return dict(status="generated", statistical_claim="descriptive_only")


def render_sensitivity(bundles, out, save):
    """Stricter cell-count filtering of existing scores, without repeating inference."""
    import matplotlib.pyplot as plt
    rows = []
    for b in bundles:
        p = b["provenance"]
        sizes = {r["cell_type"]: int(r["n_cells"]) for r in read_tsv(b["directory"] / "cell_qc.tsv", ["cell_type", "n_cells"])}
        base = int(p["parameters"]["min_cells"])
        for minimum in (base, base*2):
            edges = [r for r in b["candidates"] if r["supported"] in ("TRUE", "True", True)
                     and sizes[r["source"]] >= minimum and sizes[r["target"]] >= minimum]
            rows.append(dict(sample=p["config"]["sample"], condition=p["config"]["condition"], min_cells=minimum,
                             lr_links=len(edges), n_pathways=len({r["pathway"] for r in edges}), total_score=sum(float(r["score"]) for r in edges)))
    if not rows:
        return dict(status="not_applicable", reason="无已推断结果可做过滤敏感性分析")
    write_tsv(out / "cell_count_sensitivity.tsv", rows, ["sample", "condition", "min_cells", "lr_links", "n_pathways", "total_score"])
    fig, ax = plt.subplots(figsize=(183/25.4, 110/25.4), layout="constrained")
    for index, sample in enumerate(dict.fromkeys(r["sample"] for r in rows)):
        selected = [r for r in rows if r["sample"] == sample]
        ax.plot([r["min_cells"] for r in selected], [r["lr_links"] for r in selected], marker="o", lw=.8, ms=3, label=sample)
    ax.set_xlabel("Minimum cells per sender/receiver group"); ax.set_ylabel("Supported source–target–LR links")
    ax.legend(loc="center left", bbox_to_anchor=(1, .5), frameon=False)
    save("cell_count_sensitivity", fig, "cell_count_sensitivity.tsv", "对同一推断结果采用原始与两倍最小细胞数过滤；不重算表达/概率，不代表对推断算法或细胞组成混杂的全部敏感性检查。")
    return dict(status="generated", scope="stricter_cell_count_filter_only")


def compose_summaries(root, manifest):
    """Combine native 89×78 mm panels without scaling fonts or rasterizing SVG."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib import font_manager
    ns = "http://www.w3.org/2000/svg"
    ET.register_namespace("", ns)
    summaries = []
    for sample in manifest["samples"]:
        directory = sample.get("directory")
        names = ("main_network", "main_chord", "main_counts", "main_lr_scores")
        entries = {e["id"]: e for e in manifest["figures"]}
        selected = [entries.get(f"{directory}/{name}") for name in names]
        if any(not e or e["status"] != "generated" or e.get("technical_quality", {}).get("status") != "passed" for e in selected):
            summaries.append(dict(sample=sample["sample"], status="not_applicable", reason="没有完整、技术合格的紧凑面板；保留适用独立图"))
            continue
        if any(e.get("width_mm") != 89 or e.get("height_mm") != 78 for e in selected):
            raise ValueError("主图面板尺寸不符，禁止缩放文字拼图")
        canvas = ET.Element(f"{{{ns}}}svg", width="183mm", height="170mm", viewBox="0 0 183 170")
        ET.SubElement(canvas, f"{{{ns}}}title").text = sample["sample"] + ": focused communication"
        ET.SubElement(canvas, f"{{{ns}}}rect", width="183", height="170", fill="white")
        pixels = lambda mm: round(mm / 25.4 * 600)
        preview = Image.new("RGB", (pixels(183), pixels(170)), "white")
        font = ImageFont.truetype(font_manager.findfont(font_manager.FontProperties(family="sans-serif", weight="bold")), round(8/72*600))
        for letter, name, x, y in zip("abcd", names, (0, 94, 0, 94), (5, 5, 90, 90)):
            node = ET.parse(root / directory / f"{name}.svg").getroot()
            remap = {el.attrib["id"]: f"{letter}_{el.attrib['id']}" for el in node.iter() if "id" in el.attrib}
            for el in node.iter():
                for key, value in list(el.attrib.items()):
                    if key == "id":
                        el.set(key, remap[value])
                    else:
                        for old, new in remap.items(): value = value.replace(f"url(#{old})", f"url(#{new})")
                        if value.startswith("#") and value[1:] in remap: value = "#" + remap[value[1:]]
                        el.set(key, value)
            node.attrib.update(x=str(x), y=str(y), width="89", height="78")
            canvas.append(node)
            ET.SubElement(canvas, f"{{{ns}}}text", x=str(x+1), y=str(y-1), style="font: bold 8pt sans-serif; fill: black").text = letter
            with Image.open(root / directory / f"{name}.png") as image:
                preview.paste(image.convert("RGB"), (pixels(x), pixels(y)))
            ImageDraw.Draw(preview).text((pixels(x+1), pixels(y-4)), letter, font=font, fill="black")
        filename = f"{directory}/communication_summary"
        ET.ElementTree(canvas).write(root / f"{filename}.svg", encoding="utf-8", xml_declaration=True)
        preview.save(root / f"{filename}.png", dpi=(600, 600))
        from pypdf import PdfReader, PdfWriter, PageObject, Transformation
        canvas_pdf = PageObject.create_blank_page(width=183/25.4*72, height=170/25.4*72)
        for name, x, y in zip(names, (0, 94, 0, 94), (5, 5, 90, 90)):
            panel = PdfReader(root / directory / f"{name}.pdf").pages[0]
            canvas_pdf.merge_transformed_page(panel, Transformation().translate(x/25.4*72, (170-y-78)/25.4*72))
        # Separate editable vector panel labels, at the same physical positions as SVG.
        import io
        import matplotlib.pyplot as plt
        labels = plt.figure(figsize=(183/25.4, 170/25.4))
        for letter, x, y in zip("abcd", (0, 94, 0, 94), (5, 5, 90, 90)):
            labels.text((x+1)/183, (170-y+1)/170, letter, fontsize=8, weight="bold")
        buffer = io.BytesIO(); labels.savefig(buffer, format="pdf", transparent=True); plt.close(labels); buffer.seek(0)
        canvas_pdf.merge_page(PdfReader(buffer).pages[0])
        writer = PdfWriter(); writer.add_page(canvas_pdf); writer.write(root / f"{filename}.pdf"); writer.close()
        summaries.append(dict(sample=sample["sample"], status="generated", files=[filename+".svg", filename+".png", filename+".pdf"],
                              panel_pdfs=[f"{directory}/{n}.pdf" for n in names], width_mm=183, height_mm=170,
                              text_rescaled=False, visual_review="pending", selection=f"{directory}/main_figure_selection.json"))
    return summaries


def run(config_path, output, rscript):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    cfg = json.loads(config_path.read_text())
    if "methods" in cfg:
        from run_method_workflow import run as run_methods
        return run_methods(config_path, output, rscript)
    samples = cfg.get("samples", [])
    if not samples:
        raise ValueError("配置须含至少一个 samples 条目")
    ids = [s.get("sample") for s in samples]
    if any(not isinstance(s, str) or not s.strip() for s in ids) or len(set(ids)) != len(ids):
        raise ValueError("样本名必须非空且唯一")
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and output.is_relative_to(parent):
            raise ValueError("分析输出必须位于 skill Git 仓库外")
    if output.exists():
        raise ValueError("输出目录已存在；请使用新目录，避免覆盖")
    output.mkdir(parents=True)
    shutil.copyfile(config_path, output / "run_config.json")
    plt.style.use(Path(__file__).resolve().parents[1] / "assets/communication-nature.mplstyle")
    manifest = dict(schema_version=1, status="running", samples=[], figures=[], conditional_panels={}, visual_review="pending",
                    research_question=cfg.get("research_question"), config_sha256=sha(config_path))
    def persist():
        write_json(output / "figure_manifest.json", manifest)
    def save(identifier, fig, source, caption):
        entry = dict(id=identifier, status="failed", source_data=source, caption=caption, files=[], visual_review="pending")
        try:
            entry["technical_quality"] = check_figure_quality(fig)
            for ax in fig.axes:
                for artist in ax.collections:
                    artist.set_rasterized(False)
            for ext in ("png", "pdf", "svg"):
                filename = f"{identifier}.{ext}"
                save_figure(fig, output / filename, dpi=600)
                entry["files"].append(filename)
            entry["status"] = "generated"
        except Exception as exc:
            entry["error"] = str(exc)
        finally:
            plt.close(fig)
        manifest["figures"].append(entry); persist()
    persist()
    bundles = []
    prepared = []
    global_groups = set()
    for i, sample in enumerate(samples):
        scfg = {**cfg.get("defaults", {}), **sample, "dataset": cfg["dataset"], "research_question": cfg["research_question"]}
        for key in ("input", "object"):
            if key in scfg:
                path = Path(scfg[key]); scfg[key] = str(path if path.is_absolute() else config_path.parent / path)
        prepared.append(scfg)
        inspection = output / f"inspect_{i+1:03d}.json"
        write_json(inspection, {**scfg, "inspect_only": True})
        try:
            inspected = subprocess.run([rscript, str(Path(__file__).with_name("run_cellchat.R")), str(inspection), str(output / "unused")],
                                       capture_output=True, text=True, check=True)
            global_groups.update(json.loads(inspected.stdout))
        except Exception as exc:
            # The actual sample run will record a proper failure; never omit it from the design.
            manifest.setdefault("inspection_errors", []).append(dict(sample=sample["sample"], error=str(exc)))
    dark_first = list(range(0, 20, 2)) + list(range(1, 20, 2))
    palette = {g: matplotlib.colors.to_hex(plt.get_cmap("tab20")(dark_first[i])) if len(global_groups) <= 20 else
               matplotlib.colors.to_hex(plt.get_cmap("hsv")(i / len(global_groups))) for i, g in enumerate(sorted(global_groups))}
    write_json(output / "cell_colors.json", palette)
    for i, sample in enumerate(samples):
        scfg = prepared[i]
        if "colors" not in scfg and palette:
            scfg["colors"] = palette
        sample_dir = output / f"sample_{i+1:03d}"
        sample_cfg = output / f"sample_{i+1:03d}.json"
        write_json(sample_cfg, scfg)
        print(f"[{i+1}/{len(samples)}] {sample['sample']}: {scfg.get('mode')}", flush=True)
        try:
            with (output / f"sample_{i+1:03d}.log").open("w") as log:
                result = subprocess.run([rscript, str(Path(__file__).with_name("run_cellchat.R")), str(sample_cfg), str(sample_dir)], stdout=log, stderr=subprocess.STDOUT, check=False)
            state_path = sample_dir / "figure_manifest.json"
            state = json.loads(state_path.read_text()) if state_path.exists() else dict(status="failed", error="R 未产生状态文件；见日志", figures=[])
            manifest["samples"].append(dict(sample=sample["sample"], status=state["status"], returncode=result.returncode, directory=sample_dir.name))
            for entry in state["figures"]:
                entry["id"] = f"{sample_dir.name}/{entry['id']}"
                entry["files"] = [f"{sample_dir.name}/{p}" for p in entry.get("files", [])]
                if entry.get("source_data"):
                    entry["source_data"] = f"{sample_dir.name}/{entry['source_data']}"
                manifest["figures"].append(entry)
            if (sample_dir / "provenance.json").exists():
                bundles.append(dict(directory=sample_dir, provenance=json.loads((sample_dir / "provenance.json").read_text()),
                                    candidates=read_tsv(sample_dir / "candidates.tsv", ["source", "target", "interaction", "ligand", "receptor", "pathway", "score", "tested", "supported"])))
        except Exception as exc:
            manifest["samples"].append(dict(sample=sample["sample"], status="failed", error=str(exc)))
        persist()
    try:
        manifest["conditional_panels"]["condition_networks"] = descriptive_comparison(bundles, cfg, output, save)
    except Exception as exc:
        manifest["conditional_panels"]["condition_networks"] = dict(status="failed", reason=str(exc))
    if cfg.get("comparison"):
        try:
            if len(bundles) != len(samples):
                raise ValueError("部分样本推断失败，不能静默删样本后执行比较")
            manifest["conditional_panels"]["condition_statistics"] = render_comparison(bundles, cfg["comparison"], output, save)
        except Exception as exc:
            manifest["conditional_panels"]["condition_statistics"] = dict(status="failed", reason=str(exc))
    else:
        manifest["conditional_panels"]["condition_statistics"] = dict(status="not_applicable", reason="未指定有效的两条件供体比较设计；保留描述性图")
    try:
        manifest["conditional_panels"]["cell_count_sensitivity"] = render_sensitivity(bundles, output, save)
    except Exception as exc:
        manifest["conditional_panels"]["cell_count_sensitivity"] = dict(status="failed", reason=str(exc))
    manifest["conditional_panels"].update(render_context(cfg.get("context", {}), config_path.parent, output, save))
    failures = validate_delivery(output, manifest["figures"])
    try:
        manifest["summary_figures"] = compose_summaries(output, manifest)
    except Exception as exc:
        manifest["conditional_panels"]["summary_layout"] = dict(status="failed", reason=str(exc))
    failed = any(s["status"] in ("failed", "partial") for s in manifest["samples"]) or any(s["status"] == "failed" for s in manifest["conditional_panels"].values())
    manifest["status"] = "partial" if failed else "needs_visual_revision" if failures else "generated_pending_visual_review"
    manifest["technical_issues"] = failures
    persist()
    lines = [f"# {cfg['dataset']}", "", cfg["research_question"], "", f"状态：{manifest['status']}。", "",
             "通讯推断支持候选假设；技术检查不等于视觉审查或因果验证。缺失输入和失败分别列示。", ""]
    for entry in manifest["figures"]:
        lines.append(f"- {entry['id']}: {entry['status']} — {entry.get('caption', entry.get('reason', entry.get('error', '')))}")
    lines += ["", "条件图："] + [f"- {k}: {v['status']} — {v.get('reason', '')}" for k, v in manifest["conditional_panels"].items()]
    (output / "figure_report.md").write_text("\n".join(lines) + "\n")
    return 2 if failed or failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rscript", default="Rscript")
    args = parser.parse_args()
    try:
        sys.exit(run(args.config, args.out, args.rscript))
    except Exception as exc:
        print(f"细胞通讯执行失败: {exc}", file=sys.stderr)
        sys.exit(1)
