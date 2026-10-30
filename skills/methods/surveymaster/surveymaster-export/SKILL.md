---
name: surveymaster-export
version: 0.2.0
description: Export a finalized SurveyMaster workspace to DOCX, LaTeX source, attempted optional PDF, and bibliography deliverables in one step.
argument-hint: "--survey-dir <work-dir> [--title <text>] [--bib <file.bib>] [--citation-style <name>] [--csl <style-name|file.csl>] [--bib-style <style-name|bst>]"
---

## Stage Contract

Role: unified export during finalization.

Loaded by: `surveymaster-finalize` only after BibTeX resolution, deterministic
checks, and the single fix pass have completed.

PDF engine contract: PDF output is attempted by default, optional by default,
and LaTeX-only. The only permitted PDF path is
`export_all.py` assembling `$WORK/build/<stem>.tex` and compiling it with
`latexmk -xelatex`. Never use HTML-to-PDF tools, browser print-to-PDF,
Pandoc-to-PDF, screenshots, WeasyPrint, wkhtmltopdf, Playwright, Chromium,
Puppeteer, or any other fallback to create `$WORK/<stem>.pdf`. If LaTeX export
fails or `latexmk` is unavailable during the default run, report the
`EXPORT_RESULT pdf ERROR ...` message and continue after required formats
succeed. Stop only when `pdf` is requested as a required format.

Required inputs:
- `$WORK/mainbody.tex`.
- Optional `$WORK/outline.json` and `$WORK/writing_constraints.json`.
- `$WORK/references.bib` when bibliography rendering is required.
- `$WORK/figures/<id>.png` — local image files required by PDF and DOCX export.

Outputs:
- `$WORK/<stem>.docx`.
- `$WORK/<stem>.tex` — assembled LaTeX source copied from the build directory for delivery.
- `$WORK/<stem>.pdf` when the default optional PDF attempt or required PDF export succeeds.
- `$WORK/build/<stem>.tex` — internal assembled LaTeX source used by `tex` export and optional `latexmk`.
- Updated `$WORK/references.bib` when PDF BibTeX rebuild succeeds.

Completion condition:
- The unified export script has attempted DOCX, TeX, and optional PDF
  export by default, fixed
  recoverable in-format issues where supported, retried failed format export
  steps once, and reported a structured result for each requested format.

May load other skills:
- no.

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use
shell heredocs because they can corrupt LaTeX and JSON backslashes.

## Function

Export default final deliverable formats from the checked SurveyMaster workspace
in one script invocation. Do not ask the user which formats to generate and do
not split export across separate skills. PDF is attempted by default as an
optional deliverable; required formats are DOCX and TeX.


Bundled assets are stored inside this skill:

| Directory | Purpose |
|---|---|
| `csl/` | CSL files for DOCX citeproc |
| `docx/` | Pandoc reference DOCX templates (`template-zh.docx`, `template-en.docx`) |
| `latex/` | `SciMasterNoBrand.cls` and bundled `.bst` files |
| `scripts/export_all.py` | Unified export implementation |

Supported bundled style names include `gb-t-7714-2015-numeric`,
`gb-t-7714-2015-author-date`, `ieee`, `ama`, `apa`, `nature`, `acs`, `cell`,
`science`, `elsevier-with-titles`, and `rsc`. APA DOCX export uses the
bundled `csl/apa.csl`; PDF export uses `apacite` via
`\\usepackage[apaciteclassic]{apacite}` and `\\bibliographystyle{apacite}` so
the standard `\\cite{key}` used by SurveyMaster renders as parenthetical APA
citations.

`<skill_dir>` in invocations refers to the directory containing this skill's
`SKILL.md` file. Directory names may include deployment suffixes such as
`surveymaster-export-2`; the script resolves bundled assets by prefix.

## Arguments

$ARGUMENTS

- `--survey-dir <dir>` — survey work directory (`$WORK`) (**required**). Prefer
  an absolute path. The script normalizes this path internally before building
  `$WORK/build`, because relative paths passed through to `latexmk -outdir` can
  create nested build directories and make the PDF log unreachable to diagnostics.
- `--title <text>` — optional title override.
- `--bib <file.bib>` — optional bibliography; normally `$WORK/references.bib`.
- `--citation-style <name>` — explicit style override for all formats. When unset,
  the script resolves the style from workspace metadata. Supported names match
  the bundled list below.
- `--csl <style-name|file.csl>` — optional DOCX-only CSL override.
- `--bib-style <style-name|bst>` — optional PDF-only BibTeX override.
- `--skill-dir <dir>` — this skill directory; pass `<skill_dir>`.
- `--language zh|en` — required from the orchestrator; resolved from the current
  user input. Do not rely on the script language fallback for citation style.
- `--formats docx,tex,pdf` — optional subset for diagnostics or explicit
  export; default is `docx,tex,pdf`. `markdown` is not supported.
- `--optional-formats <formats>` — formats whose failure should not fail the
  command. For the default format set, `pdf` is optional by default. When
  `--formats` is supplied explicitly, all requested formats are required unless
  listed here.

Citation style resolution order:

1. `--citation-style` when provided.
2. `$WORK/writing_constraints.json` → `citation_style`.
3. Language fallback: `gb-t-7714-2015-numeric` for `zh`, `science` for `en`.

When step 3 is used, the script prints
`EXPORT_WARNING shared citation_style_fallback: ...`.

Per-format overrides still apply after the resolved style name:

- DOCX uses `--csl` when set, otherwise the resolved style name.
- PDF uses `--bib-style` when set, otherwise the resolved style name.

GBT bilingual `et al.` / `等` handling:

- DOCX: one-step `latex → docx --citeproc` preserves abstract/keyword bold;
  after export, `fix_gbt_bilingual_in_docx()` patches `word/document.xml`
  for in-text Latin-author citations and English bibliography entries only.
  Requires `language = {en-US}` / `{zh-CN}` in `.bib` entries.

## Typical Invocation

```bash
WORK_ABS="$(cd "$WORK" && pwd)"
python3 <skill_dir>/scripts/export_all.py \
  --survey-dir "$WORK_ABS" \
  --bib "$WORK_ABS/references.bib" \
  --skill-dir "<skill_dir>" \
  --language "$SURVEY_LANG"
```

For explicit PDF export, first verify that Python subprocesses can see the same
tools as the shell, especially with TinyTeX or another non-system TeX
distribution:

```bash
python3 -c "import shutil; print('latexmk=', shutil.which('latexmk')); print('xelatex=', shutil.which('xelatex')); print('bibtex=', shutil.which('bibtex')); print('pandoc=', shutil.which('pandoc'))"
```

If any required command prints `None`, fix the environment before export. Put
the TeX distribution's `bin/` directory at the front of `PATH` for the same
process that launches `export_all.py`; for TinyTeX also set `TEXMFVAR` when the
installation requires it.

Before invoking export directly, run the shared structure gate on the final
`mainbody.tex`:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" repair-structure \
  --mainbody "$WORK/mainbody.tex" \
  --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --report "$WORK/.cache/pre_export_structure.txt"
```

Do not export if this command fails. In particular, a `mainbody.tex` with
`\begin{abstract}` but no matching `\end{abstract}` cannot be converted to
DOCX because the exporter extracts the abstract with a bounded LaTeX
environment match.

## Execution Model

All scripts in this skill are **synchronous**. No async execution, background
threads, subprocess fire-and-forget, or parallel format export. Format steps
run one at a time in order: docx → tex → pdf. The default run
attempts PDF after the required formats, but PDF failure is non-blocking unless
PDF was explicitly requested as a required format.

## Error Handling Contract

The script prints one structured result per format:

```text
EXPORT_RESULT docx ERROR <reason>
EXPORT_RESULT tex OK <path>
EXPORT_RESULT pdf ERROR <reason>
```

Rules:

- **Required format failure blocks the export immediately.** When a required format
  step fails (after one retry), the script cleans up that format's output
  artifacts, prints its `EXPORT_RESULT … ERROR` line, and exits non-zero.
  Subsequent formats are NOT attempted. No partial deliverables are left on
  disk from the failed format.
- **Default PDF failure is non-blocking.** The default run attempts PDF, but
  treats it as optional. If PDF fails, the script prints
  `EXPORT_RESULT pdf ERROR ...` plus
  `EXPORT_WARNING pdf optional_format_failed_nonblocking`, cleans partial PDF
  artifacts, and still exits `0` if DOCX and TeX succeeded.
- Each failed format export step is retried once. Before retrying, the script
  removes stale output/build artifacts for that format so the second attempt does
  not reuse partial files from the failed attempt. Successful retries are reported
  with an `EXPORT_WARNING <format> retry_after_error: ...` line.
- When `writing_constraints.json` lacks `citation_style`, the script still exports
  using the language fallback but emits `EXPORT_WARNING shared citation_style_fallback`.
  Treat that warning as actionable: pass `--citation-style` or repair constraints.
- Unrecoverable errors include the command stderr or the relevant LaTeX log
  excerpt.
- The script exits `0` when all required requested formats succeed. It exits
  non-zero on required format failure or shared precondition failure.

**LaTeX compile failure — mandatory diagnostic protocol:**

When PDF compilation fails, `export_all.py` already calls `latex_diagnose(log_path)`
internally and returns a structured `ERROR_TYPE=… FIX=… CONTEXT:…` string as the
`EXPORT_RESULT pdf ERROR <message>` payload. Read that output and act on it directly.

Do NOT grep, cat, or tail the `.log` file manually after a compile failure.
The `EXPORT_RESULT` line contains the classified error type and fix hint — one read,
then act. Iterative log-scanning loops are forbidden.

Exception: if the message is exactly `latex_log_missing` rather than a classified
`ERROR_TYPE=...`, the expected log file was not found. Confirm `--survey-dir` is
absolute or normalized, then run `xelatex -interaction=nonstopmode <stem>.tex`
once from `$WORK/build` to force a log file and read the first 60 lines for the
missing package/font. This is the only case where manual log inspection is
appropriate.

Common TinyTeX packages for Chinese surveys using `SciMasterNoBrand.cls`:
`ctex`, `xecjk`, `fandol`, `xcharter`, `newtx`, `fontspec`, `cjk`,
`cjkpunct`, and `zhnumber`. For domestic China users, use the Tsinghua TUNA
CTAN mirror by default when installing PDF dependencies:

```bash
tlmgr option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet
tlmgr update --self
tlmgr install ctex xecjk fandol xcharter newtx fontspec cjk cjkpunct zhnumber
mktexlsr
```

If `tlmgr update --self` or `tlmgr install` fails because the local TeX Live
year is incompatible with the repository, stop and report the version mismatch
rather than repeatedly retrying against the same source.

## Post-export Checks

DOCX:
- DOCX archive opens successfully.
- Body text is not suspiciously short.
- Metadata title is present when Pandoc wrote it.
- No raw LaTeX table syntax or unresolved labels leak into visible text
  (`|L|L|...|`, `\toprule`, `tabularx`, `[tab:...]`, `[fig:...]`).
- If `mainbody.tex` contains a table, the DOCX must contain a real Word table
  (`w:tbl`), not flattened plain paragraphs.
- Abstract/keywords, reference heading, and numeric REF fields must survive the
  DOCX post-processing path when applicable.
- DOCX must be generated by `export_all.py`'s `export_docx()` path. Do not
  synthesize DOCX by calling Pandoc on `$WORK/build/*.tex`; that file is the
  TeX/PDF source and may contain LaTeX-only constructs.

TeX:
- `$WORK/<stem>.tex` exists.
- `$WORK/build/<stem>.tex` exists.
- The generated source contains the assembled document wrapper, body, and
  bibliography command when `--bib` is provided.

PDF:
- `$WORK/build/<stem>.pdf` exists after `latexmk -xelatex`.
- `$WORK/build/<stem>.bbl` exists when `--bib` is provided.
- Fatal LaTeX errors are reported with nearby log context.
- The PDF result or warning includes `pdf_engine=latexmk-xelatex` or
  `engine=latexmk-xelatex`. If not, treat the PDF as invalid and rerun the
  unified export; do not substitute another PDF generator.

## Report

Report per-format result status (OK / ERROR) in plain text. Do NOT
use attachment links, hyperlinks, or any `[text](...)` / `[text](path)`
format — just name the format and its outcome. If any format failed, report it
prominently before declaring the export step complete.

Do not call `RecordArtifact`/`UpdateFile` from this skill. File persistence is the sole
responsibility of the main orchestrating agent.
