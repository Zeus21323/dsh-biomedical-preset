"""Create a normal DOCX article from declarative JSON content.

Formula markers stay as `$...$` and `$$...$$` text in this base document.
Convert them afterwards with docx-equation-processor's formula_inserter.py.
"""

import argparse
import io
import json
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from lxml import etree


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _set_font(run, font_name, size=12):
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
    run.font.size = Pt(size)


def _set_style_font(style, east_asia_font, size, bold=False):
    """Set explicit, theme-independent formatting for a paragraph style."""
    style.font.name = "Times New Roman"
    style._element.rPr.rFonts.set(qn("w:eastAsia"), east_asia_font)
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)


def _configure_article_styles(document):
    """Match the former article builder's black, left-aligned chapter styles."""
    normal = document.styles["Normal"]
    _set_style_font(normal, "宋体", 12)

    for style_name, size in (("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 12)):
        style = document.styles[style_name]
        _set_style_font(style, "黑体", size, bold=True)
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        style.paragraph_format.first_line_indent = Pt(0)


def _paragraph(document, text, style=None, indent=True):
    paragraph = document.add_paragraph(style=style)
    if indent:
        paragraph.paragraph_format.first_line_indent = Pt(24)
    run = paragraph.add_run(text)
    _set_font(run, "宋体")
    return paragraph


def build_article(spec):
    document = Document()
    _configure_article_styles(document)

    if spec.get("title"):
        # The original article builder used the same left-aligned chapter style
        # for the document title rather than Word's blue Title theme style.
        paragraph = document.add_paragraph(style="Heading 1")
        run = paragraph.add_run(spec["title"])
        # Apply the Chinese title font directly. This avoids Word substituting
        # a theme or fallback font such as MS Gothic for CJK characters.
        _set_font(run, "黑体", 16)
        run.bold = True

    for block in spec.get("blocks", []):
        block_type = block["type"]
        if block_type == "heading":
            paragraph = document.add_heading(block["text"], level=int(block.get("level", 1)))
            for run in paragraph.runs:
                _set_font(run, "黑体")
        elif block_type == "paragraph":
            _paragraph(document, block["text"], indent=block.get("indent", True))
        elif block_type == "display_math":
            paragraph = _paragraph(document, f"$$ {block['latex']} $$", indent=False)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif block_type in ("bullets", "numbered"):
            style = "List Bullet" if block_type == "bullets" else "List Number"
            for item in block["items"]:
                _paragraph(document, item, style=style, indent=False)
        elif block_type == "table":
            table = document.add_table(rows=1, cols=len(block["columns"]))
            table.style = "Table Grid"
            for cell, value in zip(table.rows[0].cells, block["columns"]):
                cell.text = str(value)
            for row in block["rows"]:
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    cell.text = str(value)
        elif block_type == "blank":
            document.add_paragraph()
        else:
            raise ValueError(f"Unsupported block type: {block_type}")
    return document


def _normalize_settings_zoom(docx_path):
    """Add the schema-required zoom percent omitted by some python-docx versions."""
    with zipfile.ZipFile(docx_path, "r") as source:
        settings = etree.fromstring(source.read("word/settings.xml"))
        zoom = settings.find(f"{{{W_NS}}}zoom")
        if zoom is None or zoom.get(f"{{{W_NS}}}percent") is not None:
            return
        zoom.set(f"{{{W_NS}}}percent", "100")
        updated_settings = etree.tostring(
            settings, xml_declaration=True, encoding="UTF-8", standalone=True
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(
                    item,
                    updated_settings if item.filename == "word/settings.xml" else source.read(item.filename),
                )
    with open(docx_path, "wb") as output:
        output.write(buffer.getvalue())


def main():
    parser = argparse.ArgumentParser(description="Build a base DOCX article from JSON")
    parser.add_argument("content_json")
    parser.add_argument("output_docx")
    args = parser.parse_args()
    try:
        with open(args.content_json, "r", encoding="utf-8") as source:
            spec = json.load(source)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Invalid JSON in {args.content_json} at line {exc.lineno}, column {exc.colno}: "
            f"{exc.msg}. Escape a literal ASCII double quote inside text with a JSON backslash escape, "
            "or use Chinese quotation marks such as “…” inside the string."
        ) from exc
    output = Path(args.output_docx)
    output.parent.mkdir(parents=True, exist_ok=True)
    # This is a new-document builder, never an existing-document editor.
    try:
        with output.open("xb") as destination:
            build_article(spec).save(destination)
    except FileExistsError:
        raise SystemExit(
            f"Refusing to overwrite existing document: {output}. "
            "Use edit_guard.py and edit the current DOCX for revisions, "
            "or choose a new output path for an explicitly requested rebuild."
        )
    _normalize_settings_zoom(output)
    print(f"Created base article: {output}")
    print("Next: batch-convert formula markers, then run validate.py.")


if __name__ == "__main__":
    main()
