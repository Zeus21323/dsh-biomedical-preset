---
name: docx-equation-processor
description: "Use this skill when Word .docx work involves math formulas, equations, LaTeX, MathML, OMML, MathType, equation numbering, inline equations, display equations, or academic papers with existing Word equation objects. It protects and edits native Word oMath and oMathPara formulas, converts LaTeX to OMML, inserts numbered equations, and can optionally prepare MathType-compatible output. Use alongside the docx skill for general Word layout; use this skill for all formula-specific handling."
---

# DOCX Equation Processor

Handle equations in Word `.docx` files without corrupting native Word formula XML.

Word formulas are stored as OMML, usually in `<m:oMath>` or `<m:oMathPara>` nodes inside `word/document.xml`. Treat these nodes as structured objects, not plain text. For ordinary document layout, use the `docx` skill. For formulas, use this skill.

## When To Use

- The document contains `<m:oMath>` or `<m:oMathPara>`.
- The user mentions Word equations, formulas, inline formulas, display equations, LaTeX, MathML, OMML, MathType, formula numbering, equation references, or thesis/journal equation formatting.
- A `.docx` must be generated from academic content containing math.
- A `.docx` must be edited while preserving existing formulas.

If this skill is referenced by the `docx` skill but is not installed locally, stop before editing formula-bearing content and tell the user to install or add `docx-equation-processor`.

## Core Rules

1. Never rewrite a paragraph containing OMML as plain text unless you first preserve and restore its equation nodes.
2. Prefer ZIP-level XML edits for formula-heavy documents. `python-docx` can damage or reorder OMML structures.
3. Use OMML as the main output format. MathType conversion is an optional Windows desktop post-process.
4. Preserve existing equation objects by default. Only replace formulas the user explicitly asks to change.
5. Validate by counting OMML nodes before and after edits when formulas should be preserved.

## Bundled Scripts

Scripts are in `scripts/`, adapted from `academic-ref-inserter`'s `academic-formula-inserter`.

| Script | Use |
|---|---|
| `latex_omml_converter.py` | Convert LaTeX to OMML, inspect existing OMML, export rough LaTeX |
| `formula_inserter.py` | Insert LaTeX formulas, batch-convert `$...$` / `$$...$$`, number formulas |
| `formula_numbering.py` | Add sequential equation numbering |
| `build_docx_raw.py` | Build minimal `.docx` at ZIP/XML level to avoid OMML corruption |
| `mathtype_integration.py` | Add `MTDisplayEquation`, `SEQ MTEqn`, and MathType-compatible paragraph XML |
| `convert_omml_to_mathtype.py` | Optional Windows + Word + MathType COM conversion |
| `convert_omml_to_mathtype.vbs` | Optional VBScript version of OMML to MathType conversion |
| `convert_to_mathtype.py` | Optional alternate MathType conversion helper |

Do not use experimental direct OLE container construction as the primary path. Use OMML first, then optional Word/MathType conversion if the user specifically needs MathType OLE objects.


## OMML Schema Safety

Generated equations must be normalized before saving. The bundled scripts now normalize these common invalid structures:

- Nested `<m:oMathPara>` wrappers are collapsed to a single display equation wrapper.
- Paragraph properties `<w:pPr>` are kept as the first child of `<w:p>`.
- Math italic runs use `<m:sty m:val="i"/>`, not `<m:ital/>`.
- Superscripts use `<m:sSup><m:sup>...</m:sup></m:sSup>`, not `<m:lim>`.
- Subscripts use `<m:sSub><m:sub>...</m:sub></m:sSub>`, not `<m:lim>`.
- Combined scripts use `<m:sSubSup>` with both `<m:sub>` and `<m:sup>` children.
- Radicals always include `<m:deg/>`, even when the degree is hidden.
- Formula input is normalized for supported convenience macros such as `\argmax`
  and `\argmin`; conversion stops if a literal LaTeX command remains in OMML.

After insert or batch conversion, the bundled inserter runs a lightweight check for known OMML schema issues and raises an error if they remain. When the docx skill's `scripts/office/validate.py` is available, also run full validation. If validation fails, report the failure instead of claiming success.

Run the same schema check after `number-formulas`; a Word run may contain at
most one `<w:rPr>`, and this must be its first child.

`verify_docx()` is only a structural preflight, not proof that Microsoft Word accepts every construct. Do not claim formulas are MathType OLE objects: OMML is editable in Word, while MathType OLE requires the optional Windows conversion workflow below.

## Workflows

### Inspect Existing Formulas

For a formula-bearing `.docx`, first inspect the ZIP XML:

```bash
unzip -p paper.docx word/document.xml | grep -o "<m:oMath\\|<m:oMathPara" | sort | uniq -c
```

Use this count as a preservation check before and after edits.

### Preserve Formulas While Editing Text

1. Unpack or read `word/document.xml`.
2. Locate paragraphs containing `<m:oMath>` or `<m:oMathPara>`.
3. Avoid whole-paragraph text replacement for those paragraphs.
4. If text around an inline formula must change, edit only adjacent `<w:t>` runs and leave the OMML subtree untouched.
5. Repack and validate the resulting `.docx`.
6. Recount OMML nodes.

### Insert LaTeX As Native Word Equation

Use `formula_inserter.py` for quick insertion:

```bash
python scripts/formula_inserter.py insert-formula paper.docx --latex "E=mc^2" --display --style parentheses --number 1
```

For a new full article, create the base document with the DOCX skill's
`scripts/office/build_article_docx.py`, then use ZIP-level marker conversion.
Use `build_docx_raw.py` only for its narrow, bundled minimal-document example;
do not import its XML constants into a task-local generator.

### Batch Convert LaTeX Markers

```bash
python scripts/formula_inserter.py batch-convert paper.docx --backup
python scripts/formula_inserter.py number-formulas paper.docx --style parentheses
```

`batch-convert` performs ZIP/XML-level replacement in paragraphs and table cells,
preserving paragraph properties such as list numbering. Inline `$...$` markers can
appear with surrounding prose; `$$...$$` must be the only content in its paragraph.
Only `$$...$$` display formulas are eligible for `number-formulas`; inline `$...$`
symbols are never centred or assigned equation numbers.
The command stops on the first unsupported or malformed marker rather than silently
leaving warnings behind. Then run the DOCX skill's full validator. Never treat
`verify_docx()` as a Word-openability verdict.

For a new full-length article, first create the base DOCX with the DOCX skill's
`scripts/office/build_article_docx.py`; then run `batch-convert`. Task-local
scripts may prepare content JSON, but must not copy or reconstruct raw DOCX
package templates such as `DOC_TEMPLATE`, `STYLES_XML`, or `RELS_XML`.

### MathType Compatibility

Use MathType conversion only when the user needs MathType OLE objects and has a Windows desktop with Microsoft Word and MathType installed:

```bash
python scripts/convert_omml_to_mathtype.py paper.docx paper_mathtype.docx
```

In non-Windows or headless environments, produce native OMML and explain that MathType conversion must be run later on a suitable desktop.

## Provenance

The scripts are derived from `fuwenhao12/academic-ref-inserter`'s `academic-formula-inserter`. Verify the upstream license before redistribution.

## Dependencies

Required for bundled Python scripts:

- Python 3.8+
- `python-docx`
- `lxml`
- `latex2mathml`
- `defusedxml` (required by the DOCX validator)

Optional:

- `pandoc` for advanced conversion workflows
- Windows + Microsoft Word + MathType + `pywin32` for COM conversion

If dependencies are missing, do not silently downgrade formulas to images or text. Tell the user which dependency is missing and use a preservation-only workflow when possible.
