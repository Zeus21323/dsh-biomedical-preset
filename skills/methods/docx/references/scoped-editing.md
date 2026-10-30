# Revise the current document without rebuilding it

## Fast path: replace a section body, including formulas

Use this path first for “replace section 3.1 only”. It does not regenerate the
manuscript. Keep the existing section and next-section headings unchanged.

1. Read this reference and run one compact inspection:

```bash
python scripts/office/replace_section.py inspect current.docx
```

2. Write content as JSON, not a new Python/XML program. Use exact unique heading
texts from inspection and an original body paragraph index as the text-format
sample. A display equation needs a standalone native-equation paragraph index
from the same document as its format sample. The old equation and its number
stay unchanged; the new equation copies only paragraph properties and has no number.

```json
{
  "heading": "3.1 融合建模总体框架",
  "next_heading": "3.2 物理先验引导的分层候选库",
  "body_template": 22,
  "equation_template": 27,
  "blocks": [
    {"text": "替换后的第一段。"},
    {"runs": [{"text": "未知关系 "}, {"latex": "\\theta"}, {"text": " 由数据确定。"}]},
    {"latex": "\\theta(z)=\\sum_{j=1}^{p}\\xi_j\\phi_j(z)"},
    {"text": "公式之后的说明。"}
  ]
}
```

The indices above are examples, not constants. Use `text` for ordinary paragraphs,
`runs` for mixed text/native inline math, and a `latex` block for a standalone
unnumbered native equation. Copy the user's supplied wording; don't add needless
inline equations to otherwise ordinary text. New prose copies the sample
paragraph's properties and first text run's formatting. This path replaces the
entire specified body; for preserving mixed emphasis inside partially retained
paragraphs, use the smaller text edit path below instead.

3. Run one command, using a new output path and a new transaction directory:

```bash
python scripts/office/replace_section.py replace current.docx replacement.json \
  revised.docx edits/revision-001 --equation-skill /resolved/installed/equation-skill
```

Resolve the installed `docx-equation-processor` path from the runtime skill entry.
Its `scripts/latex_omml_converter.py` is imported only if the spec contains math;
plain prose needs no equation skill. If its `latex2mathml` dependency is missing,
install that dependency in the permitted task/runtime environment once, or report
the dependency problem. Do not handwrite a substitute OMML converter. Only the
new formulas are converted; no full-document conversion or numbering is run.

The command performs snapshot → bounded replacement → comparison → bundled DOCX
schema validation → commit. Successful output contains the exact output, backup,
transaction and receipt paths plus the restore command and elapsed seconds.
No separate prepare/commit call or custom validation script is needed. Report
those paths so users can find their undo backup. Never bypass a failing check
with a custom “equivalent” verifier or copy the candidate to a final output.

This path refuses ambiguous headings, nested headings/lists, tables, bookmarks,
fields, tracked changes, linked objects and other anchored content inside the
replaced body. A missing standalone equation template also stops display-math
insertion. Explain the unsupported feature and use a separately scoped workflow;
do not silently delete it or rebuild the paper. Supported paragraph templates and
new math are verified deterministically without relaxing outside-scope checks.

For visual QA, check renderer availability before attempting conversion. If
unavailable, report that visual QA was not performed; do not repeatedly retry the
same missing executable. Schema and preservation checks do not prove visual quality.

## Choose and inspect the current baseline

Read the actual file the user is editing, not an earlier MD/TeX draft. Preserve
its content, format and existing numbering unless a requested change requires
otherwise. “Only insert the new 3.1” is not permission to regenerate the paper.
Do not automatically synchronize or overwrite sibling source files.

Create a unique transaction directory outside the skill and the manuscript:

```bash
python scripts/office/edit_guard.py prepare current.docx edits/revision-001
```

This saves the exact original in `before.docx`, its SHA-256, an `inventory.json`
of body blocks and inherited paragraph styles, and the original `numbering.xml`.
Read the inventory and the relevant original XML before choosing the scope.
Indices count **all body children**, including tables; they are not displayed
paragraph/section numbers. Match the heading and surrounding text uniquely.
Keep the section heading and next heading outside the scope for body-only edits.

Resolve heading structure from `pStyle`, its `basedOn` chain, `outlineLvl`, direct
and inherited `numPr`, `numId`/`ilvl`, and `numbering.xml` definitions/overrides.
A first visible heading may be a subsection. A displayed number may be automatic,
literal text, a field, or mixed. Do not add a literal `2.1` to a paragraph already
numbered automatically, promote headings, restart lists, or strip numeric-looking
text globally. Preserve the current scheme; ask only when the target is ambiguous.

## Make a bounded candidate

For a small replacement wholly inside a single `w:t` node:

```bash
python scripts/office/edit_guard.py replace-text edits/revision-001 candidate.docx \
  --index 12 --old 'original wording' --new 'revised wording'
```

This retains the paragraph/run structure, formatting, fields, and other ZIP parts.
It refuses ambiguous or split-run matches instead of flattening a paragraph.
For supported section replacements use the fast path above. For other rich edits,
edit only the selected XML nodes from `before.docx`
in a separate candidate. Copy paragraph/run properties from the appropriate
original paragraphs; preserve existing mixed formatting intentionally. Keep every
other ZIP entry byte-identical. Do not run global formula conversion or numbering.
Use the equation skill only for formulas within the requested scope. Preserve
bookmarks/fields and check affected references; the guard does not prove semantic
reference correctness or visual layout.

## Verify and commit

Ranges are half-open: `--start 12 --end 14` allows original body blocks 12 and 13.

```bash
python scripts/office/edit_guard.py verify edits/revision-001 candidate.docx --start 12 --end 14
python scripts/office/validate.py candidate.docx
python scripts/office/edit_guard.py commit edits/revision-001 candidate.docx \
  --start 12 --end 14 --output revised.docx
```

The guard checks the current source hash, unchanged package parts (including
styles, numbering, headers, footers and relationships), and unchanged body nodes
outside the declared range. Within the range it checks paragraph properties and
refuses newly introduced run-formatting recipes. This is a conservative
content-editing gate, not a general formatting editor. It does not detect every
misapplication of an existing run style; inspect mixed formatting and render the
candidate when layout matters. Do not broaden the scope to make a failed check pass.

If the requested replacement genuinely adds/removes paragraphs, inspect the
new boundaries and use `--allow-paragraph-count-change` on verify and commit.
New paragraphs must reuse paragraph formatting from within the original scope.
Tables, changes to package parts (such as new images), and intentional reformatting
need a separately scoped workflow and appropriate checks; do not claim this guard
validated them. Do not silently fall back to rebuilding the document.

The default delivery above creates a new file and leaves the original intact.
Omit `--output` only when updating the original is requested. Commit re-verifies
the candidate and source, retains `before.docx`, `after.docx` and the receipt, then
replaces the original atomically. Keep Word closed/saved during replacement:
hash checks cannot lock out every simultaneous external writer on every platform.
If source changed or replacement is locked, preserve the candidate and re-read the
current document; never force-delete the destination or discard the user's edits.

Report the actual scope, any necessary related changes, verification and limits.
Keep the transaction for undo; do not clean away original snapshots as temporary
files. Check visual numbering if numbering was part of the requested change.

## Undo means restore

```bash
python scripts/office/edit_guard.py restore edits/revision-001
```

This restores the exact pre-edit bytes to the committed target only if it still
matches the committed version. For a new output file this restores its content to
the baseline and leaves the source untouched. Later user edits block restoration;
retain both versions and resolve the conflict instead of overwriting them.
