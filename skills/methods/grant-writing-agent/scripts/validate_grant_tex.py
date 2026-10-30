#!/usr/bin/env python3
"""Validate grant TeX headings and final DOCX numbering semantics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


HEADING_RE = re.compile(
    r"\\(?P<command>section|subsection|subsubsection)(?P<star>\*)?\s*\{(?P<title>[^{}]*)\}"
)
MARKDOWN_HEADING_RE = re.compile(r"(?m)^\s*#{1,6}\s+\S")
METADATA_RE = re.compile(
    r"^(?:项目名称|项目类别|申报类别|申报年度|申请代码|学科代码|研究方向|"
    r"申请人|负责人|依托单位|研究期限|关键词)\s*[：:]?"
)
MANUAL_NUMBER_RE = re.compile(
    r"^\s*(?:"
    r"\d+(?:\.\d+)+(?:[.、．])?"
    r"|\d+[.、．]"
    r"|[一二三四五六七八九十百]+[、.．]"
    r"|[（(][一二三四五六七八九十百]+[）)]"
    r"|第[一二三四五六七八九十百]+[章节部分]"
    r")\s*"
)
LEVELS = {"section": 1, "subsection": 2, "subsubsection": 3}
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}


def w_attr(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def strip_comments(text: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in text.splitlines())


def audit_docx(path: Path) -> dict[str, object]:
    errors: list[dict[str, object]] = []
    headings: list[dict[str, object]] = []
    if not path.is_file():
        return {
            "path": str(path.resolve()),
            "headings": headings,
            "errors": [{"code": "docx_not_found", "message": f"DOCX 不存在：{path}"}],
        }

    try:
        with ZipFile(path) as archive:
            styles_root = ET.fromstring(archive.read("word/styles.xml"))
            document_root = ET.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        return {
            "path": str(path.resolve()),
            "headings": headings,
            "errors": [{"code": "docx_invalid", "message": f"无法读取 DOCX OOXML：{exc}"}],
        }

    styles: dict[str, dict[str, object]] = {}
    for style in styles_root.findall(".//w:style", NS):
        if style.get(w_attr("type")) != "paragraph":
            continue
        style_id = style.get(w_attr("styleId"), "")
        name_node = style.find("w:name", NS)
        name = name_node.get(w_attr("val"), "") if name_node is not None else ""
        num_node = style.find("w:pPr/w:numPr/w:numId", NS)
        level_node = style.find("w:pPr/w:numPr/w:ilvl", NS)
        outline_node = style.find("w:pPr/w:outlineLvl", NS)
        styles[style_id] = {
            "name": name,
            "num_id": num_node.get(w_attr("val")) if num_node is not None else None,
            "level": level_node.get(w_attr("val")) if level_node is not None else None,
            "outline_level": (
                outline_node.get(w_attr("val")) if outline_node is not None else None
            ),
        }

    for index, paragraph in enumerate(document_root.findall(".//w:p", NS), start=1):
        style_node = paragraph.find("w:pPr/w:pStyle", NS)
        if style_node is None:
            continue
        style_id = style_node.get(w_attr("val"), "")
        style = styles.get(style_id, {})
        style_name = str(style.get("name", ""))
        is_heading = style_name.lower().startswith("heading") or style.get(
            "outline_level"
        ) not in (None, "", "9")
        if not is_heading:
            continue
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        direct_num_node = paragraph.find("w:pPr/w:numPr/w:numId", NS)
        direct_num_id = (
            direct_num_node.get(w_attr("val")) if direct_num_node is not None else None
        )
        effective_num_id = direct_num_id or style.get("num_id")
        automatic_numbering = effective_num_id not in (None, "", "0")
        heading = {
            "paragraph": index,
            "style_id": style_id,
            "style_name": style_name,
            "automatic_numbering": automatic_numbering,
            "num_id": effective_num_id,
            "level": style.get("level"),
            "text": text,
        }
        headings.append(heading)

        if METADATA_RE.match(text):
            errors.append(
                {
                    "code": "docx_metadata_used_as_heading",
                    "paragraph": index,
                    "message": f"DOCX 中“{text}”使用了标题样式。",
                }
            )
        if automatic_numbering and MANUAL_NUMBER_RE.match(text):
            errors.append(
                {
                    "code": "docx_heading_double_number",
                    "paragraph": index,
                    "message": (
                        f"DOCX 标题“{text}”已绑定自动编号 numId={effective_num_id}，"
                        "标题文本不得再包含手写编号。"
                    ),
                }
            )

    return {"path": str(path.resolve()), "headings": headings, "errors": errors}


def audit(path: Path, docx_path: Path | None = None) -> dict[str, object]:
    text = strip_comments(path.read_text(encoding="utf-8"))
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    if "\\documentclass" not in text:
        errors.append({"code": "documentclass_missing", "message": "缺少 \\documentclass。"})
    if MARKDOWN_HEADING_RE.search(text):
        errors.append({"code": "markdown_heading_found", "message": "TeX 中出现 Markdown 标题。"})

    headings = []
    previous_level = 0
    for match in HEADING_RE.finditer(text):
        command = match.group("command")
        title = re.sub(r"\s+", " ", match.group("title")).strip()
        line = text.count("\n", 0, match.start()) + 1
        level = LEVELS[command]
        headings.append({"line": line, "level": level, "command": command, "title": title})

        if not match.group("star"):
            errors.append(
                {
                    "code": "automatic_heading_numbering_forbidden",
                    "line": line,
                    "message": f"{command} 必须加星号，避免与标题内的指南编号叠加。",
                }
            )
        if METADATA_RE.match(title):
            errors.append(
                {
                    "code": "metadata_used_as_heading",
                    "line": line,
                    "message": f"“{title}”是项目元数据，必须改为正文段落。",
                }
            )
        if MANUAL_NUMBER_RE.match(title):
            errors.append(
                {
                    "code": "manual_heading_number",
                    "line": line,
                    "message": f"“{title}”含手写编号；Word 标题样式会自动编号。",
                }
            )
        if previous_level and level > previous_level + 1:
            errors.append(
                {
                    "code": "heading_level_jump",
                    "line": line,
                    "message": f"标题层级从 {previous_level} 跳到 {level}。",
                }
            )
        previous_level = level

    if not headings:
        warnings.append({"code": "no_headings", "message": "未找到任何申请书章节标题。"})

    docx_result = audit_docx(docx_path) if docx_path is not None else None
    if docx_result is not None:
        errors.extend(docx_result["errors"])

    return {
        "status": "passed" if not errors else "failed",
        "source": str(path.resolve()),
        "heading_count": len(headings),
        "headings": headings,
        "docx": docx_result,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Canonical grant-application.tex")
    parser.add_argument("--docx", type=Path, help="Final DOCX to audit for duplicate numbering")
    parser.add_argument("--report", type=Path, help="Optional JSON audit report")
    args = parser.parse_args()

    if args.source.suffix.lower() != ".tex":
        parser.error("source must be a .tex file; Markdown is not a DOCX source")
    if not args.source.is_file():
        parser.error(f"source not found: {args.source}")

    result = audit(args.source, args.docx)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
