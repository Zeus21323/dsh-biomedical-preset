---
name: surveymaster-finalize
version: 0.2.0
description: Coordinate SurveyMaster finalization — citation audit, BibTeX metadata resolution, deterministic checks with compact summary, one LLM fix pass, unified export, and persistence.
argument-hint: "--survey-dir <work-dir> [--language zh|en]"
---

## Stage Contract

Stage: 5 — checks, fix, export, and persistence.

Loaded by: SurveyMaster orchestrator after full-body drafting, or whenever
`mainbody.tex` changes for any reason — content edits, style fixes, constraint
updates, visual asset changes, or language switches. Any operation that writes
`mainbody.tex` makes the existing deliverables stale; `surveymaster-finalize`
is the mandatory gate before the user receives any updated deliverable.

Required inputs:
- `$WORK/writing_constraints.json`
- `$WORK/papers.json`
- `$WORK/outline.json`
- `$WORK/mainbody.tex` (produced by Stage 4 `surveymaster-write-section`)

Input contract:
- `$WORK/mainbody.tex` must be the Stage 4 body fragment beginning with
  `\begin{abstract}` and must not contain `\documentclass`, `\begin{document}`,
  `\bibliography{}`, or hand-written references.
- `$WORK/papers.json` must be the Stage 2 library normalized by
  `bibliography_library.py insert`; it may come from browser-use candidates
  resolved by `discover_and_resolve_papers.py`. Every cited paper must have
  `bib_key`, `title`, `authors`, `year`, and a publication venue (`journal` /
  `booktitle` / `venue`, etc.).
- Every `\cite{key}` in `mainbody.tex` must refer to a `bib_key` present in
  `$WORK/papers.json`. Missing keys are hallucinated citations; do not hide them
  by temporarily adding entries to `papers.json`. Remove or rewrite them during
  the Step 5-B fix pass.
- `$WORK/outline.json` must be the Stage 3 outline normalized by
  `save_outline.py`; it is used for structure checks and fix-pass context.
- `$WORK/writing_constraints.json` remains the source of truth for language,
  citation style, focus points, extra requirements, and venue-style constraints.

Outputs:
- Updated `$WORK/mainbody.tex` (after LLM fix pass)
- `$WORK/references.bib`
- Final DOCX, TeX source, and bibliography deliverables; PDF is
  attempted by default as an optional deliverable

Completion condition:
- Deterministic check pass completed; `$CACHE/check_summary.txt` written.
- LLM has fixed all issues in one pass.
- Unified export has attempted all required formats.
- User-visible deliverables have been saved or updated by the orchestrator.

**Step 5-B (LLM Fix Pass) is MANDATORY and must never be skipped.**
A clean or minimal `check_summary.txt` means the draft is mechanically valid —
it does NOT mean semantic refinement has occurred. Proceed to Step 5-C only
after Step 5-B has completed and `mainbody_fixed.tex` has been promoted to
`mainbody.tex`. Never jump from Step 5-A directly to Step 5-C.

May load other skills:
- `surveymaster-literature-library`
- `surveymaster-check-and-merge`
- `surveymaster-write-section`
- `surveymaster-refine-section` (post-export local polishing only)
- `surveymaster-export`

Load these skills lazily, immediately before the step that needs them.

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use
shell heredocs because they can corrupt LaTeX and JSON backslashes.

## User Interaction Contract

These are the **mandatory** user interaction checkpoints. Stop and wait for user
input at each one; never auto-proceed past them.

1. **Metadata discrepancy (Step 5-A Phase 2):** When `--verify-metadata` reports
   any TITLE_MISMATCH, YEAR_MISMATCH, VENUE_MISMATCH, or AUTHOR_MISMATCH, present
   each discrepancy and **wait for user direction** before modifying any record.

2. **Outline confirmation (Post-export Revision outline change):** Before running
   `surveymaster-write-section` after any outline edit, render the full updated
   outline as a numbered section list (index · title — core_claim) and **ask
   the user to explicitly confirm**. Never rewrite sections on an outline the
   user has not approved in this session.

3. **Duplicate bib keys (Step 5-A Phase 3):** Duplicate keys cannot be
   auto-resolved. Show the duplicates and **wait for the user to fix
   `references.bib`** before continuing.

4. **Total export failure (Step 5-C):** If every requested format fails, stop
   and report to the user before attempting persistence.

Never block on informational messages, word-count results, or WARN-only items.

## Deliverable Gate (STRICT)

`surveymaster-finalize` is the **only** path that produces or updates
deliverables (`.docx`, `.tex`, and optional `.pdf`). It MUST be run — in full, from Step 5-A
— after any of the following:

- `surveymaster-write-section` completes (draft or rewrite mode)
- `surveymaster-refine-section` completes
- Any direct edit to `mainbody.tex` (inline fix, visual asset insert/remove,
  figure/table content change)
- Any constraint change that affects content (language, citation style, venue
  style, length targets)
- Any paper/library change that causes a cite-key or metadata update

Do not present the user with a `.docx`, `.tex`, or `.pdf` file that was produced
before the most recent `mainbody.tex` write. Stale deliverables must never be
shared as current output.

---

## Mandatory Sub-step Execution Order

Every item below is a HARD GATE. Do not advance past an item until it exits
successfully. This list is the authoritative execution order — use it to verify
you have not skipped any step before calling Step 5-D.

| # | Step | Output | Skip risk |
|---|---|---|---|
| 1 | 5-A Ph1 `cites` audit | `$CACHE/cites_audit.txt` | |
| 2 | 5-A Ph2 steps 1–3 `export-bib` initial | `$WORK/references.bib` | |
| 3 | **5-A Ph2 step 4 `--verify-metadata`** | `$METADATA_REPORT` | ⚠ commonly skipped |
| 4 | 5-A Ph2 step 5 final `export-bib` sync | `$WORK/references.bib` | |
| 5 | 5-A Ph3 `survey_checks.py all` | `$CACHE/check_summary.txt` | |
| 6 | 5-B LLM fix pass | `$CACHE/scratch/mainbody_fixed.tex` | |
| 7 | **5-B `repair-structure` validation** | validates fix | ⚠ commonly skipped |
| 8 | **5-B Rebuild Bibliography** | `$WORK/references.bib` re-synced | ⚠ omission → stale DOCX/TeX/PDF citations |
| 9 | 5-C `export_all.py` | DOCX / TeX required; PDF attempted optional | |
| 10 | **5-C `final_cites.txt`** (bib-only, no `--library`) | `$CACHE/final_cites.txt` | ⚠ commonly skipped |
| 11 | 5-D persist deliverables | saved files | |

---

## Step 5-A — Deterministic Check Pass

Load `surveymaster-literature-library` and `surveymaster-check-and-merge` before
this step.

`$WORK` is the survey output directory; `$CACHE` is `$WORK/.cache/`.

Resolve paths **once** at the top of Step 5-A and reuse across all phases.

**Prerequisite:** `SkillLoad` `surveymaster-check-and-merge` and
`surveymaster-literature-library` before the Bash block below.

```bash
CACHE="$WORK/.cache"
SURVEY_LANG="<language-from---language-argument>"
CHECK_SKILL_DIR="<skillDir from SkillLoad(surveymaster-check-and-merge)>"
LIT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-literature-library)>"
```

Abort if either directory variable is empty or the expected script is missing.

`SURVEY_LANG` must be supplied by the orchestrator from the current user input
(`--language zh|en`). Do not infer it from `writing_constraints.json` or
`outline.json`. If the argument is missing or not one of `zh` / `en`, stop and
ask the orchestrator to reload `surveymaster-finalize` with an explicit language.

### Phase 1 — Citation audit (run first; output feeds Phase 2)

Run `cites` against `mainbody.tex` and `papers.json` only (no `--bib` yet —
`references.bib` does not exist at this point). This is the only standalone
citation audit in Step 5-A; later checks must reuse `$CACHE/cites_audit.txt`
instead of running `cites` again:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" cites \
  --extra-tex "$WORK/mainbody.tex" \
  --library "$WORK/papers.json" \
  --report-unused \
  --report "$CACHE/cites_audit.txt" \
  --warn-only
```

Read `$CACHE/cites_audit.txt`. Extract:
- **`used_keys`**: the `used_cite_keys=[...]` line — written to the report file
  only (not stdout). Parse it as a Python list literal to get the set of keys
  confirmed present in `mainbody.tex`.
- **`hallucinated_keys`**: `missing_defined_keys=[...]` — `\cite{}` keys in the
  tex that are absent from `papers.json`. These are hallucinated citations.
- **`uncited_library_keys`**: `unused_library_keys=[...]` — library papers never
  cited. Treat this as an informational coverage signal; do not force all library
  papers into the draft.

Do **not** strip hallucinated keys from the tex here. Pass them to the LLM for
removal in Step 5-B.
Do **not** look up or add hallucinated keys to `papers.json` — inserting a record
for an unverified key circumvents the citation validity chain.

### Phase 2 — Bib metadata resolution + final export (uses `used_keys` from Phase 1)

Only resolve metadata for entries in `used_keys`. Do **not** fetch metadata for
library papers that are not cited.

1. Run BibTeX export against the citations actually present in `mainbody.tex`.
   The script extracts cite keys from the TeX source and excludes uncited library
   records automatically, so callers do not need to build or pass a `--keys`
   argument. Capture compact diagnostics in a shell variable, not a file.
   `--diagnostics-stdout` makes WARN/INFO lines pipeable while real command
   errors still use stderr:
   ```bash
   EXPORT_BIB_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   ```
2. From `$EXPORT_BIB_DIAGNOSTICS`, collect every ERROR record (missing title,
   author, venue, or year). Because the export was limited by `--tex-file`, these
   records are already restricted to papers cited by the draft. Dispatch DOI/title
   lookups for all such records **in parallel**.
3. After all lookups return, reinsert updated metadata and re-run the export once:
   ```bash
   EXPORT_BIB_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   ```
   Repeat only if new ERROR records appeared.
4. **HARD GATE — `--verify-metadata` (mandatory; do not skip).**
   Resolve missing volume/pages and verify metadata consistency in one stdout
   pipeline. Do not write a separate resolver report file:
   ```bash
   METADATA_REPORT="$(
     printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
       python3 "$LIT_SKILL_DIR/scripts/resolve_volume_pages.py" \
         --library "$WORK/papers.json" \
         --verify-metadata \
        --verify-targets-only \
         --report-stream stdout || true
   )"
   ```
   This resolves volume/pages for WARN keys from stdin **and** checks those same
   cited records for TITLE_MISMATCH / YEAR_MISMATCH / VENUE_MISMATCH /
   AUTHOR_MISMATCH in one call.

   **Reading the output:**
   - `RESOLVE_SKIPPED` / `NO_MISMATCHES` in output: no WARN keys were piped in,
     meaning no volume/pages gaps exist. This is a normal exit — proceed
     immediately to step 5. Do NOT retry with different arguments.
   - No MISMATCH lines: metadata is consistent. Proceed immediately.
   - MISMATCH lines present: **include in `$CACHE/check_summary.txt`, present
     each discrepancy to the user, and wait for direction** before modifying.

   After collecting `$METADATA_REPORT`, additionally identify any entry in `used_keys`
   whose `papers.json` record has no `doi` field (null or empty). These entries cannot
   be verified by `--verify-metadata` and are lower-confidence citations. Append a
   `NO_DOI_ENTRIES` line to `$METADATA_REPORT` before passing it downstream:
   ```
   NO_DOI_ENTRIES: [key1, key2, ...]  (cited but unverifiable — no DOI in papers.json)
   ```
   Present this list to the user alongside any MISMATCH warnings. Do not block export
   solely on missing DOI, but the user must see the list before proceeding.
5. Because Step 4 may patch `papers.json`, re-run BibTeX export exactly once so
   `$WORK/references.bib` is synchronized with resolved metadata:
   ```bash
   FINAL_EXPORT_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   METADATA_REPORT="$METADATA_REPORT
   $FINAL_EXPORT_DIAGNOSTICS"
   ```

### Phase 3 — Full check pass (run after `references.bib` exists)

Run the remaining complete check suite in one invocation. Skip `cites` because
Phase 1 already produced `$CACHE/cites_audit.txt`; this avoids duplicating the
same citation analysis and `used_cite_keys` output. Build
`$CACHE/check_summary.txt` in the same process so the LLM does not need to read
`checks_full.txt` or hand-write a summary:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" all \
  --mainbody "$WORK/mainbody.tex" --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --extra-tex "$WORK/mainbody.tex" \
  --library "$WORK/papers.json" \
  --bib "$WORK/references.bib" \
  --skip-cites \
  --report "$CACHE/checks_full.txt" \
  --summary-output "$CACHE/check_summary.txt" \
  --cites-audit "$CACHE/cites_audit.txt" \
  --metadata-stdin \
  --report-only --compact \
  --warn-only <<< "$METADATA_REPORT"
```

This covers: structure (abstract/keywords/sections/required outline section
titles/forbidden wrappers/`\begin{}\end{}` balance), bib (duplicates/unescaped &),
doi, latex, words. Citation findings come from `$CACHE/cites_audit.txt`.

The command prints compact `CHECK_RESULT ...` and `SUMMARY_RESULT ...` lines and
writes the LLM-readable summary to `$CACHE/check_summary.txt`. The summary file
must contain no raw JSON blobs, no full `.bib` text, and no paper abstracts.

**Hard stop — exit 21 (E_BIB, duplicate bib keys):** Present duplicates to the
user and wait for `references.bib` to be fixed before continuing to Step 5-B.

Do not create `$WORK/summary.json` in the normal path. The compact summary file
is the only check summary artifact consumed by Step 5-B.

---

## Step 5-B — Single LLM Fix Pass

**HARD GATE — do not skip under any condition.**
This step is mandatory regardless of how clean the check_summary looks.
A check_summary with zero flagged issues still requires this pass for semantic
refinement (goals 6–19 below). Never proceed to Step 5-C without writing
`$CACHE/scratch/mainbody_fixed.tex` and promoting it to `$WORK/mainbody.tex`.

Read the following inputs only (two files):
- `$WORK/mainbody.tex` → `{current_mainbody}`
- `$CACHE/check_summary.txt` → `{check_summary}`

Build supporting context from already-loaded JSON (do **not** re-read large files
into the prompt unless already in context):
- `$WORK/outline.json` → `{outlines_text}`:
  `N. <section_title> — <core_claim>` (sorted by integer index)
- `$WORK/writing_constraints.json` → `{survey_title}`, `{focus_points}`,
  `{extra_requirements}`, `{venue_style_notes}`
- `$WORK/papers.json` → `{papers_text}` as a compact subset only:
  include cited keys from `$CACHE/cites_audit.txt`, hallucinated keys from
  `$CACHE/check_summary.txt` if any. Uncited library papers are informational
  only; do not include them solely to force citation or reporting.
  For each record include only `[bib_key] Title · Year · Venue`; include an
  abstract excerpt only when the key is directly involved in a flagged issue.

Do not load the full paper library or full abstracts into the Step 5-B prompt.
If more detail is required for a specific key, query that key only.

Send one LLM pass:

```text
You are an academic writing editor and survey quality reviewer.
Fix all flagged issues and refine the complete survey body in one pass.

## Automated check summary
{check_summary}

## Refinement goals (apply to the entire document)
1. Fix all flagged issues above — structural errors, missing abstract/keywords,
   citation mismatches, language inconsistencies, unescaped LaTeX characters.
   **Preserve `\%` as-is** — every `\%` in the source is an intentional escaped
   percent sign; do NOT remove the backslash, or the compiled PDF will silently
   truncate the rest of that line.
2. Remove every \cite{key} listed in HALLUCINATED CITE KEYS above.
3. Do not force citations for uncited library papers. Do not append any
   `% WARN uncited` block or other uncited-paper report to `mainbody.tex`.
   The UNCITED LIBRARY PAPERS section in `check_summary.txt` is informational
   only and is not a flagged issue. Do not mention it as "needs fixing" and do
   not add citations merely to reduce that list.
4. For entries in METADATA RISKS, soften or qualify the associated claim so it
   does not rely on potentially wrong metadata; keep the cite if metadata looks
   plausible, remove it if the entry may be a wrong match.
5. Fix all BEGIN/END MISMATCHES — add or remove the unmatched environment tag.
5a. FIGURES/TABLES COUNT MISMATCH — do NOT auto-fix by adding or removing
    \begin{figure}/\begin{table} environments. Adding figures requires image
    generation and is handled by the visual asset workflow. Instead, surface the
    mismatch clearly in your response so the user can address it manually. If
    check_summary says figures are missing because expected count is greater
    than actual count, do not create placeholder figure environments in Step
    5-B. Stop before export and report that the visual asset workflow must add
    the figures or the user-confirmed outline expected_figures_total must be
    adjusted.
5b. UNREFERENCED_FIGURE / UNREFERENCED_TABLE — for each label flagged in
    FIGURES/TABLES ISSUES, insert an \autoref{} call into the surrounding prose
    of the same section. The reference must be integrated into an analytical
    sentence, not a standalone introductory line. Do NOT add or remove the
    \begin{figure}/\begin{table} environment itself.
6. Eliminate cross-section redundancy — cut or compress text duplicated elsewhere.
7. Enforce section core claims — cut or rewrite paragraphs drifting from core_claim.
8. Calibrate hedging — replace absolute claims ("X proves", "显而易见") with hedged
   language ("suggests", "evidence indicates", "据报道"). Preserve well-calibrated hedges.
9. Surface conflicts and limitations — acknowledge conflicting findings; note scope limits.
10. Repair coverage gaps — ensure all focus_points are explicitly addressed.
11. Strengthen evidence hierarchy — distinguish consensus, primary studies, theory, experiment.
12. Improve endpoint-data synthesis — make metric, condition, direction of change, and citation explicit.
13. Academic register — remove filler phrases, AI-style meta-commentary
    ("综上所述，本节介绍了…", "In summary, this section has shown…", "Having established X…"),
    and promotional language. Every paragraph opens with a clear topic sentence.
14. Dash usage — do NOT use em dashes in prose, including Unicode `—` and
    LaTeX `--` or `---`; zh: do NOT use Chinese破折号（——、—）for emphasis, transitions,
    or parenthetical explanations. Rewrite these relations with commas,
    semicolons, colons, parentheses, or separate sentences.
15. Quotation marks —
    zh: use “…” (U+201C/U+201D) for emphasis/quoting; English technical terms use \textit{}.
    en: use ``…'' for double quotes, `…' for single quotes; do NOT use ASCII straight quotes " " or ' '.
16. Preserve legitimate LaTeX escape sequences — characters such as
    `\_`, `\%`, `\#`, `\$`, `\^{}`, `\~{}`, `\&` in body text or inside
    `\cite{}` keys are intentional LaTeX escapes (e.g. `Supplement\_1`,
    `50\%`, journal names containing `\&`). Do NOT unescape them, drop
    the leading backslash, or "normalize" them to bare characters — that
    will break LaTeX compilation. Only escape bare special chars that
    are still unescaped; never re-touch already-escaped sequences.
17. Citation validity — remove any \cite{key} not present in the papers list below.
18. Abstract and keywords alignment — abstract must faithfully reflect the body;
    keywords must reflect the actual survey scope. zh: \keywords{} uses ；as separators.
    en: \keywords{} uses commas, title case. Do not add \cite{} to the abstract.
19. Length — if any section is significantly below its length_target (< 70%), deepen coverage.
20. Do NOT change \section{} titles, remove \section{} headings, restructure \subsection{}
    headings, or add new citations beyond those in the papers list.
21. Mainbody boundary — `mainbody.tex` is a body fragment, not a standalone
    LaTeX document. The export script adds `\documentclass`, citation packages,
    `\bibliographystyle{...}`, `\begin{document}`, `\bibliography{references}`,
    and `\end{document}`. Do NOT output document wrappers, package declarations,
    bibliography commands, `thebibliography` environments, `\bibitem` entries,
    manually written References / Bibliography / 参考文献 sections, raw BibTeX,
    or formatted reference-list entries.

## Survey context
Survey title: {survey_title}
Outline (section titles + core_claims):
{outlines_text}
User constraints: focus_points={focus_points}; extra_requirements={extra_requirements};
venue_style_notes={venue_style_notes}

## Papers (available evidence; cite only when substantively relevant)
{papers_text}

## Current mainbody.tex
{current_mainbody}

## Output format (STRICT)
Return ONLY the fixed and refined LaTeX starting with \begin{abstract}.
Preserve \keywords{}, \maketitle, \newpage, \tableofcontents, \newpage in their original positions.
Do not output document wrappers, package declarations, bibliography commands,
bibliography environments, \bibitem entries, reference-list sections, raw BibTeX,
formatted reference-list entries, or markdown fences.
Do not force citations for every paper in the available evidence list. Leave
irrelevant or redundant papers uncited.
```

Write LLM output to `$CACHE/scratch/mainbody_fixed.tex`.

### Repairable structure validation

**HARD GATE — do not skip and do not advance to "Save" until this passes.**

Run the shared checker; do not write a temporary validation script:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" repair-structure \
  --mainbody "$CACHE/scratch/mainbody_fixed.tex" \
  --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --report "$CACHE/mainbody_fixed_structure.txt"
```

This may fix only deterministic wrapper/fence noise and bare `%`, then checks
non-empty abstract/keywords, `\maketitle`, `\tableofcontents`, required outline
section titles, forbidden wrappers/markdown fences after repair, and
`\begin{}` / `\end{}` balance. If it fails, read
`$CACHE/mainbody_fixed_structure.txt`, run one correction pass with the exact
reported issues, then rerun repairable structure validation. If it still fails,
keep existing `mainbody.tex` unchanged and report which check failed.

**Cite key audit:** strip any `\cite{key}` not in `papers.json`. Log removed keys
as `WARN: removed cite keys: [k1, k2]`.
Do **not** add entries to `papers.json` during or after the fix pass — the library
is frozen at this stage. If a removed cite key represents genuine missing coverage,
report it to the user for manual resolution after export.

### Save

```bash
cp "$CACHE/scratch/mainbody_fixed.tex" "$WORK/mainbody.tex" && \
rm -f "$CACHE/scratch/mainbody_fixed.tex"
```

### Rebuild Bibliography After Fix Pass

**HARD GATE — do not proceed to Step 5-C without completing this.**
Omitting this step leaves `references.bib` out of sync with the fixed
`mainbody.tex` and will cause stale or missing citations in DOCX and
the LaTeX-compiled PDF.

The LLM fix pass may remove invalid citations or keep/add valid citations from
the provided papers list. After saving the final `mainbody.tex`, re-run BibTeX
export against the current TeX source so `references.bib` is synchronized with
the exact final citation set before any format export:

```bash
python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
  --library "$WORK/papers.json" --output "$WORK/references.bib" \
  --tex-file "$WORK/mainbody.tex" \
  --warn-limit 10 --diagnostics-stdout
```

If this command fails with missing cite keys, stop and send the exact failing
keys back through one correction pass; do not run `surveymaster-export` with a
stale or incomplete `references.bib`.

---

## Step 5-C — Unified Export

Load `surveymaster-export` only after structural validation in Step 5-B passes.

**Prerequisite:** `SkillLoad("surveymaster-export")` and bind its returned
`skillDir` before running the script below.

```bash
EXPORT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-export)>"
```

Abort if `EXPORT_SKILL_DIR` is empty, `scripts/export_all.py` is missing, or the
resolved directory name is not `surveymaster-export`. Do not use the legacy
`export_skill` directory for the main Bore_Acdemic flow.

Run the unified export script once (one invocation handles all requested formats):

```bash
WORK_ABS="$(cd "$WORK" && pwd)"
python3 "$EXPORT_SKILL_DIR/scripts/export_all.py" \
  --survey-dir "$WORK_ABS" \
  --bib "$WORK_ABS/references.bib" \
  --skill-dir "$EXPORT_SKILL_DIR" \
  --language "$SURVEY_LANG"
```

Collect all `EXPORT_RESULT` lines and any `EXPORT_WARNING shared` lines. If
`citation_style_fallback` appears, stop and repair constraints or pass
`--citation-style` before retrying export. The LaTeX-backed `surveymaster-export`
script is a required-format gate: DOCX and TeX failures exit
non-zero, clean that format's partial artifacts, and block persistence until the
reported issue is fixed and the unified export succeeds. PDF is attempted by
default but is optional; if it fails with
`EXPORT_WARNING pdf optional_format_failed_nonblocking`, continue persistence
for DOCX, TeX, and `references.bib`, and report PDF as failed/skipped.

DOCX has exactly one valid generation path: the same `export_all.py` invocation
above, through its internal `export_docx()` pipeline. Do not manually call
`pandoc` to create DOCX, do not run `export_all.py --formats tex` and
then synthesize DOCX from `$WORK/build/*.tex`, and do not mark a hand-built DOCX
as a deliverable. `$WORK/build/*.tex` is the TeX/PDF source and may contain
LaTeX-only constructs such as `tabularx`; feeding it directly to Pandoc can
flatten tables, lose TOC/reference post-processing, and bypass DOCX validation.
If DOCX fails, fix the reported input/exporter issue and rerun the unified
export command until the required DOCX result is `OK`.

PDF is LaTeX-only. A valid PDF must come from this same `export_all.py`
invocation and must report `engine=latexmk-xelatex` or
`pdf_engine=latexmk-xelatex`. Do not call or load any HTML-to-PDF skill/tool,
browser print-to-PDF tool, screenshot workflow, Pandoc-to-PDF path, WeasyPrint,
wkhtmltopdf, Playwright, Chromium, Puppeteer, or other fallback. If the user
explicitly requires PDF, rerun with `--formats docx,tex,pdf` after
installing/fixing LaTeX; in that explicit required-PDF mode, PDF failure blocks
completion.

Before repairing a failed PDF export, verify Python subprocess visibility, not only the
interactive shell:

```bash
python3 -c "import shutil; print('latexmk=', shutil.which('latexmk')); print('xelatex=', shutil.which('xelatex')); print('bibtex=', shutil.which('bibtex')); print('pandoc=', shutil.which('pandoc'))"
```

If using TinyTeX or another non-system TeX distribution, ensure its `bin/`
directory is at the front of `PATH` for the same process that launches
`export_all.py`; set `TEXMFVAR` when the installation requires it. Common
TinyTeX packages for Chinese surveys using `SciMasterNoBrand.cls` are `ctex`,
`xecjk`, `fandol`, `xcharter`, `newtx`, `fontspec`, `cjk`, `cjkpunct`, and
`zhnumber`. For domestic China users, use the Tsinghua TUNA CTAN mirror by
default when installing PDF dependencies:

```bash
tlmgr option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet
tlmgr update --self
tlmgr install ctex xecjk fandol xcharter newtx fontspec cjk cjkpunct zhnumber
mktexlsr
```

If `tlmgr update --self` or `tlmgr install` fails because the local TeX Live
year is incompatible with the repository, stop and report the version mismatch
rather than repeatedly retrying against the same source.

If the PDF error is exactly `latex_log_missing`, the expected log file was not
found. Confirm `--survey-dir` is absolute/normalized. Then run
`xelatex -interaction=nonstopmode <stem>.tex` once from `$WORK/build` and read
the first 60 log lines to identify the missing package or font. This is the only
case where manual log inspection is appropriate.

**HARD GATE — BibTeX key consistency check (mandatory after unified export).**
Do not proceed to Step 5-D without completing this.
Use `$CHECK_SKILL_DIR` resolved at the top of Step 5-A. Check against
`references.bib` only; do not pass `--library` here, because library+bib union
can hide cited keys that exist in `papers.json` but were omitted from the final
BibTeX export.

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" cites \
  --extra-tex "$WORK/mainbody.tex" \
  --bib "$WORK/references.bib" \
  --report "$CACHE/final_cites.txt"
```
- Exit 0: consistent — proceed to Step 5-D.
- Exit 20 (E_CITE): re-run the Step 5-B post-fix BibTeX export and re-run the
  unified export step once.
- Extra keys in `references.bib` after export: warn the user but do not block
  persistence if all cited keys are present.

## Step 5-D — Persist Deliverables

Only the main orchestrating agent calls `RecordArtifact` or `UpdateFile`. Do not call
them from inside export, check, or helper skills.

**All three deliverables below are mandatory.** Persist each one after a successful
unified export. If any is missing, treat export as incomplete and do not silently
skip it. Persist the root-level TeX source copied by `surveymaster-export`;
`$WORK/build/` remains an internal build directory.

- `$WORK/<stem>.docx`
- `$WORK/<stem>.tex`
- `$WORK/references.bib`

Persist `$WORK/<stem>.pdf` when the `EXPORT_RESULT pdf OK ...` line was
reported. If the default optional PDF attempt fails, do not treat persistence as
incomplete; report PDF as failed/skipped with the `EXPORT_RESULT pdf ERROR ...`
diagnostic.

Use `UpdateFile` for an existing saved deliverable unless the user explicitly
requests a separate version.

**Completion report (mandatory before marking tasks done):**
After all persistence calls complete, output a plain-text completion report as
the final user-facing text in this turn. The report must contain:
1. One or two sentences summarising what was accomplished in this finalization
   run (checks, fix pass, export, persistence).
2. A bullet list of each deliverable by format name and status (saved /
   updated / skipped / failed) — no file paths, no hyperlinks, no
   `[text](...)` format.

Only after this text has been output:
- Mark the current TodoWrite task `completed`.
- Call the platform's `FinalAnswer` tool with `status: "completed"` to
  correctly terminate this turn. Do not omit this call — without it the agent
  may loop or fail to hand control back to the user.

Do not output the completion report before persistence calls finish. Do not
call `FinalAnswer` before the completion report text has been output.

---

## Post-Export Revisions

Post-Export Revision handles user requests after deliverables have already been
produced. It is a routing mode, not a new content-generation capability.

**User interaction requirements in Post-Export Revision:**

- **Any outline change** must be rendered as a numbered section list
  (index · title — core_claim) and **explicitly confirmed by the user** before
  `surveymaster-write-section` runs. Never rewrite sections on an outline the
  user has not approved in the current session.
- **Constraint changes** that affect survey scope or language must be confirmed
  before regenerating content.
- After confirming, proceed with the appropriate route below.

Routes:
- **Export-only change:** run Step 5-A through Step 5-D.
- **Local content or style change:** load `surveymaster-write-section --mode rewrite`
  for a full rewrite, or `surveymaster-refine-section` to polish without structural
  changes. Then run Step 5-A through Step 5-D.
- **Visual asset change** (insert, remove, or regenerate a figure or table):
  1. **Insert figure** at a user-specified location:
     a. Choose a unique `id` in `fig_<snake_case>` form not already in `mainbody.tex`.
     b. Select figure type and build prompt from `surveymaster-figure-types` using the surrounding section's `core_claim`.
     c. Insert the placeholder block into `mainbody.tex` at the target location:
        ```latex
        % FIGURE id=fig_<id> prompt="<prompt>"
        \begin{figure}[H]
          \centering
          \caption{<caption>\label{fig:<id>}}
        \end{figure}
        ```
     d. Insert exactly one `\autoref{fig:<id>}` into the surrounding text.
     e. Call the agent's `image_gen` tool → `$WORK/figures/<id>.png`.
        If generation fails, remove the inserted block and autoref and report the error.
        The local PNG is the required image artifact for DOCX, TeX, and PDF.
     f. In `outline.json`, increment `expected_figures_total` by 1 using `Edit`, then `SkillLoad("surveymaster-generate-outline")` and re-run `python3 <outline_skill_dir>/scripts/save_outline.py --file "$WORK/outline.json"` (where `<outline_skill_dir>` is the returned `skillDir`) to re-normalize and re-render `outline.md`.
  2. **Insert table** at a user-specified location:
     a. Choose a unique `id` in `tab_<snake_case>` form.
     b. Select table type and column structure from `surveymaster-table-types`. For generic non-economics surveys, insert a complete booktabs three-line table (`\toprule`/`\midrule`/`\bottomrule` only; no `\hline`, `\multicolumn`, `\multirow`). For economics empirical-style surveys, use the Economics Journal Table Style instead: heavy top and bottom rules, thinner internal horizontal rules, vertical column separators, compact black-and-white layout, and no `\multicolumn` or `\multirow`.
     c. Insert exactly one `\autoref{tab:<id>}` into the surrounding text.
     d. In `outline.json`, increment `expected_tables_total` by 1 using `Edit`, then re-run `save_outline.py` as above.
  3. **Remove figure or table**: remove the environment block and its `\autoref{}` reference; for figures also decrement `expected_figures_total` in `outline.json` by 1 (minimum 0), then re-run `save_outline.py`. Leave `figures/<id>.png` on disk — orphan PNGs are harmless to export.
  4. **Regenerate a figure**: delete `$WORK/figures/<id>.png`, call the agent's `image_gen` tool with the existing prompt from the `% FIGURE` comment, and wait for the new local file.
  5. After any visual asset change, run Step 5-A through Step 5-D.
  6. **Numbering**: display sequence numbers (图 1, Figure 2, 表 1…) are managed entirely by LaTeX via `\caption{}`+`\label{}`+`\autoref{}`. Never manually rename ids or renumber labels.
- **Constraint change:** update constraints, re-render the derived view, confirm
  with the user if scope or style changed, then run Step 5-A through Step 5-D.
- **Paper/library change:** update `papers.json`, decide whether outline or sections
  need regeneration, then run affected stages and Step 5-A through Step 5-D.
- **Outline change:** update `outline.json` JSON-first,
  render the full updated outline and **present it to the user for explicit
  confirmation**, wait for approval, rewrite `mainbody.tex` with
  `surveymaster-write-section`, then run Step 5-A through Step 5-D.
- **Language change:** return to the orchestrator language-change flow. Re-run
  `surveymaster-identify` with the language resolved from the current user
  request, then re-run `surveymaster-generate-outline` in that language. Present
  the regenerated outline to the user for explicit confirmation, wait for
  approval, delete stale `mainbody.tex`, rewrite with `surveymaster-write-section`
  in the new language, then run the full Stage 5 sequence.

Never machine-translate existing `.tex` files for a language change. Never
delete source-of-truth JSON or `papers.json` unless the user explicitly requests it.
