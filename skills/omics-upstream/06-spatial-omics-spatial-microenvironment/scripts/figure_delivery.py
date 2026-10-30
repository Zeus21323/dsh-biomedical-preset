"""论文图件交付内核；由 scripts/sync_figure_delivery.py 分发，勿手工修改副本。"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def read_table(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t" if Path(path).suffix == ".tsv" else ",")
        fields = reader.fieldnames or []
        rows = list(reader)
    require(fields and len(set(fields)) == len(fields), "列名缺失或重复")
    require(rows and all(None not in r and all(v is not None for v in r.values()) for r in rows), "输入表为空或记录列数不一致")
    return rows


def write_table(path, rows):
    require(bool(rows), "不能写出伪造空表")
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader(); writer.writerows(rows)


def check_figure(fig):
    """检查数据图层与文字边界；不将其宣称为完整视觉/科学认证。"""
    import numpy as np
    from matplotlib.text import Text
    from matplotlib import font_manager, ft2font
    require(bool(fig.axes), "Figure没有数据坐标轴")
    data_axes = [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]
    for ax in data_axes:
        if ax.name == "3d":
            # Axes3D interprets additional keyword arguments as grid styling
            # and enables the grid even when visible=False.
            ax.grid(False)
        else:
            ax.grid(False, which="both", axis="both")
        if not ax.axison:  # 原生网络/示意图可由patch组成；不能只凭轴关闭判空。
            require(bool(ax.lines or ax.collections or ax.images or ax.patches or ax.texts), "存在空白面板")
        else:
            require(bool(ax.lines or ax.collections or ax.images or ax.patches), "存在没有数据图层的空坐标框")
        require(np.isfinite(ax.get_xlim()).all() and np.isfinite(ax.get_ylim()).all(), "坐标范围无效")
    # Verify actual glyph coverage; missing Chinese/symbols must not silently become boxes.
    texts=[t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    for text in texts:
        fp=font_manager.findfont(text.get_fontproperties())
        chars=ft2font.FT2Font(fp).get_charmap()
        require(all(ord(c) in chars or c.isspace() for c in text.get_text()), "字体不覆盖标签，请指定支持字符的字体："+text.get_text())
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax in data_axes:
        for labels in (ax.get_xticklabels(),ax.get_yticklabels()):
            boxes=[(t,t.get_window_extent(renderer)) for t in labels if t.get_visible() and t.get_text() and t.get_rotation()==0]
            for (left,a),(right,b) in zip(boxes,boxes[1:]):
                overlap_x=min(a.x1,b.x1)-max(a.x0,b.x0)
                overlap_y=min(a.y1,b.y1)-max(a.y0,b.y0)
                require(not (overlap_x>1 and overlap_y>1), "相邻刻度标签重叠："+left.get_text()+" / "+right.get_text())
    bounds = fig.bbox
    outside=[]
    for text in fig.findobj(Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        box=text.get_window_extent(renderer)
        if box.x0 < bounds.x0-2 or box.y0 < bounds.y0-2 or box.x1 > bounds.x1+2 or box.y1 > bounds.y1+2:
            # 被axes裁剪的内部标签不是画布边界标签；由领域审图检查。
            if not text.get_clip_on(): outside.append(text.get_text())
    require(not outside, "文字超出画布："+"; ".join(outside[:5]))
    return dict(status="limited_checks_passed", axes=len(data_axes), grid="none", visual_review="pending",
                not_verified=["all overlaps", "scientific interpretation", "target journal acceptance"])


def verify_bundle(stem, width_mm, height_mm, dpi):
    """跨语言检查同一成套图件的物理尺寸与可解析性；不冒充语义审图。"""
    import math
    import re
    import xml.etree.ElementTree as ET
    from PIL import Image
    from pypdf import PdfReader
    stem=Path(stem)
    expected=[float(width_mm),float(height_mm)]
    require(all(math.isfinite(v) and v>0 for v in expected) and math.isfinite(float(dpi)) and float(dpi)>=300,
            "共同尺寸/DPI无效")
    files={ext:stem.parent/(stem.name+"."+ext) for ext in ("png","svg","pdf")}
    require(all(p.is_file() and not p.is_symlink() for p in files.values()), "三格式图件缺失或为符号链接")
    with Image.open(files["png"]) as im:
        pixels=im.size
        im.verify()
    require(all(abs(p-v/25.4*float(dpi))<=1.1 for p,v in zip(pixels,expected)), "PNG尺寸与共同配置不一致")
    root=ET.parse(files["svg"]).getroot()
    def length_mm(value):
        match=re.fullmatch(r"\s*([0-9.eE+-]+)\s*(mm|cm|in|pt|px)?\s*",value or "")
        require(match is not None, "SVG缺少明确物理尺寸")
        return float(match.group(1))*{"mm":1,"cm":10,"in":25.4,"pt":25.4/72,"px":25.4/96,None:25.4/96}[match.group(2)]
    svg_mm=[length_mm(root.get(k)) for k in ("width","height")]
    reader=PdfReader(files["pdf"])
    require(len(reader.pages)==1, "独立图件PDF须为一页")
    page=reader.pages[0]
    unit=float(page.get("/UserUnit",1))
    require(int(page.get("/Rotate",0))%360==0, "PDF旋转与共同画布不一致")
    pdf_mm=[float(page.mediabox.width)*unit*25.4/72,float(page.mediabox.height)*unit*25.4/72]
    require(all(abs(float(a)-float(b))<.01 for a,b in zip(page.cropbox,page.mediabox)), "PDF裁切框与共同画布不一致")
    for name,actual in (("SVG",svg_mm),("PDF",pdf_mm)):
        require(all(math.isfinite(a) and abs(a-b)<=.05 for a,b in zip(actual,expected)), name+"尺寸与共同配置不一致")
    return dict(status="passed", width_mm=expected[0],height_mm=expected[1],png_pixels=list(pixels),
                svg_mm=svg_mm,pdf_mm=pdf_mm,
                scope="file parsing and physical geometry only; content, fonts and interpretation require review")


def save_figure(fig, path, **kwargs):
    """显式Figure；每个文件stem成套三格式。旧代码循环调用时只导出一次。"""
    import matplotlib as mpl
    import xml.etree.ElementTree as ET
    from PIL import Image
    if not isinstance(path, (str, os.PathLike)):
        return fig.savefig(path, **kwargs)  # 内部PDF页标签等非正式文件
    path=Path(path)
    stem=path.with_suffix("")
    signature=str(stem.resolve())
    done=getattr(fig, "_delivery_stems", {})
    if signature in done:
        record=done[signature]
        require(all((stem.parent/name).is_file() and digest(stem.parent/name)==value
                    for name,value in record["sha256"].items()), "已导出的图件被改变；不能复用旧成功记录")
        return record
    require(path.parent.is_dir(), "输出父目录不存在")
    targets=[stem.parent/(stem.name+"."+ext) for ext in ("png", "svg", "pdf")]
    require(not any(p.exists() or p.is_symlink() for p in targets), "图件已存在，拒绝覆盖")
    quality=check_figure(fig)
    # check_figure draws once: freeze the resulting axes positions before switching backends.
    # Re-running constrained/tight layout per format can shift panels due to font metrics.
    if fig.get_layout_engine() is not None:
        fig.set_layout_engine("none")
    options=dict(kwargs)
    require(not any(k in options for k in ("png_options","pdf_options","svg_options","png_style","pdf_style","svg_style")),
            "不得为不同格式设置独立样式；使用同一Figure与共同参数")
    options.pop("format",None); options.pop("backend",None)
    dpi=options.pop("dpi",400)
    if dpi == "figure": dpi=400
    require(float(dpi)>=300, "正式PNG至少300 DPI；不要用分辨率替代审图")
    options.update(bbox_inches=None)
    with tempfile.TemporaryDirectory(prefix=".figure-", dir=path.parent) as folder:
        temp=Path(folder)
        with mpl.rc_context({"axes.grid":False,"pdf.fonttype":42,"svg.fonttype":"none","savefig.bbox":None}):
            for ext in ("png","svg","pdf"):
                fig.savefig(temp/("figure."+ext), format=ext, dpi=dpi, **options)
        with Image.open(temp/"figure.png") as im:
            im.verify()
        ET.parse(temp/"figure.svg")
        raw=(temp/"figure.pdf").read_bytes()
        require(raw.startswith(b"%PDF-") and b"%%EOF" in raw[-1024:], "PDF未完整写出")
        consistency=verify_bundle(temp/"figure",float(fig.get_size_inches()[0]*25.4),
                                  float(fig.get_size_inches()[1]*25.4),dpi)
        published=[]
        try:
            for target in targets:
                require(not target.exists(), "输出路径被其他运行占用")
                # hard-link gives no-overwrite semantics on the same filesystem.
                os.link(temp/("figure"+target.suffix),target)
                published.append(target)
        except Exception:
            for target in published: target.unlink()
            raise
    record=dict(files=[p.name for p in targets], sha256={p.name:digest(p) for p in targets},
                width_mm=float(fig.get_size_inches()[0]*25.4),height_mm=float(fig.get_size_inches()[1]*25.4),
                png_dpi=dpi, technical_review=quality, bundle_consistency=consistency,
                rendering_policy="one final Figure; shared style and geometry; format differences limited to encoding", export_status="complete", visual_review="pending",
                matplotlib=mpl.__version__, generated_at=datetime.now(timezone.utc).isoformat())
    from matplotlib import font_manager
    from matplotlib.text import Text
    fonts=sorted({font_manager.findfont(t.get_fontproperties()) for t in fig.findobj(Text) if t.get_visible() and t.get_text()})
    record["fonts"]=[dict(file=Path(p).name,sha256=digest(p)) for p in fonts]
    record["svg_text_policy"]="editable text; target editor needs matching fonts and SVG CSS support"
    dump(stem.parent/(stem.name+".delivery.json"),record)
    done[signature]=record; fig._delivery_stems=done
    return record


def run_cli(work):
    """新QC/PCA入口采用目录级事务；失败只保留独立诊断文件。"""
    parser=argparse.ArgumentParser(description="检查真实输入并生成可复现图件；不改变统计分析")
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    out=args.out_dir.resolve()
    try:
        require(not out.exists() and not args.out_dir.is_symlink(), "输出已存在，拒绝覆盖")
        cfg=json.loads(args.config.read_text(encoding="utf-8"))
        out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".run-",dir=out.parent) as temp:
            stage=Path(temp)/"result";stage.mkdir()
            state=work(cfg,args.config.resolve().parent,stage)
            dump(stage/"input_config.json",cfg)
            dump(stage/"run_record.json",dict(status="complete",config_sha256=digest(args.config),
                 python=sys.version,script_sha256=digest(sys.argv[0]),finished_at=datetime.now(timezone.utc).isoformat(),
                 details=state,visual_review="pending"))
            require(not out.exists(), "输出目录被其他运行占用")
            stage.rename(out)
        print(f"已生成并完成技术检查：{out}；目视审查待完成")
        return 0
    except Exception as error:
        print(f"未完成：{error}",file=sys.stderr)
        if out.parent.exists():
            fd, name=tempfile.mkstemp(prefix=out.name+"-failure-",suffix=".json",dir=out.parent)
            os.close(fd);dump(name,dict(status="failed",error=str(error),config=str(args.config)))
        return 2
