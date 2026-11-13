---
name: ppt-reader
description: 读取 PPT：解析本地 PPTX/POTX，提取每页文字、表格和演讲者备注，有 Office 工具时可渲染页面。制作新的 PPT 用 ppt-builder。
when_to_use: User uploads, names, or asks questions about a PPTX/POTX file; asks to summarize, search, extract, review, or understand a presentation.
---

# PPT Reader

Use this skill for presentation-reading requests. A PPTX/POTX is an OOXML ZIP package.

## Default text workflow

Use MarkItDown by default. It is a Python package, so install it automatically when it is missing; do not ask the user to install it manually.

Resolve `PYTHON` in this order: `$SKILL_PYTHON`, then `python3`, then `python`. Keep the package in this skill's private `.venv`, never in the user's system Python:

```bash
PYTHON="${SKILL_PYTHON:-python3}"
if [ ! -x "$SKILL_DIR/.venv/bin/markitdown" ]; then
  "$PYTHON" -m venv "$SKILL_DIR/.venv"
  "$SKILL_DIR/.venv/bin/python" -m pip install --disable-pip-version-check "markitdown[pptx]"
fi
"$SKILL_DIR/.venv/bin/markitdown" presentation.pptx
```

Use the extracted Markdown to answer questions, and retain slide-number markers when they are present. If the MarkItDown download or conversion fails, continue with the bundled standard-library fallback instead of failing the request:

```bash
"${SKILL_PYTHON:-python3}" "$SKILL_DIR/scripts/read_pptx.py" presentation.pptx
```

The fallback extracts ordered slide text, table cells, and speaker notes without non-standard Python packages. It does not understand pictures, charts, SmartArt, or visual layout.

## Visual workflow

Check first:

```bash
command -v soffice
command -v pdftoppm
```

Only if both commands exist, render for visual inspection:

```bash
soffice --headless --convert-to pdf --outdir ./pptx-render presentation.pptx
pdftoppm -png -r 144 ./pptx-render/presentation.pdf ./pptx-render/slide
```

If either command is absent, clearly state that text was extracted but visual inspection was skipped. Do not require LibreOffice or Poppler for ordinary text questions.

## Limits

- `.ppt` is the legacy binary format; ask for a `.pptx` export.
- Do not claim that a chart, screenshot, or diagram says something based only on text extraction. Render slides first when visual evidence matters.
