---
name: surveymaster-check-and-merge
version: 0.2.0
description: Run mechanical checks on mainbody.tex, including structure, citation/BibTeX/DOI/LaTeX checks, word count, and compact check-summary generation. Use from finalize or standalone after mainbody.tex and references.bib exist.
argument-hint: "survey_checks.py all [--report-only --compact] [--skip-cites --cites-audit file --summary-output file --metadata-stdin] | build-check-summary [args] | cites|bib|doi|latex|words|structure|repair-structure"
---

## Stage Contract

Role: finalization mechanical checks on `mainbody.tex`.

Loaded by: `surveymaster-finalize` after `references.bib` exists and `mainbody.tex`
has been produced by `surveymaster-write-section` or a post-export rewrite.

Required inputs:
- `$WORK/mainbody.tex`.
- `$WORK/outline.json`.
- `$WORK/papers.json`.
- `$WORK/references.bib`.
- `$WORK/writing_constraints.json` (optional; used for context only, not for inferring the requested language).

Outputs:
- Check reports under `$CACHE`.

Completion condition:
- Structure, citation, BibTeX, LaTeX, DOI, and word-count checks have completed.
- No blocking failures remain unresolved.

May load other skills:
- no.

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use shell heredocs — they corrupt backslashes in LaTeX and JSON.

## Function

Run **structure check → full-body checks** against `$WORK/mainbody.tex` and
`$WORK/references.bib`. There is no merge step — `mainbody.tex` is the canonical
output of Stage 4 and contains abstract (摘要/Abstract), keywords (关键词/Keywords),
and all body sections.

All check commands listed below are **required**.

`$WORK` is the survey output directory; `$CACHE` is `$WORK/.cache/` (ephemeral check/report outputs only).

Canonical scripts:
- `scripts/survey_checks.py`

`<skill_dir>` in script invocations refers to the directory containing this skill's `SKILL.md` file.

## Error Handling

**Script exit codes (survey_checks.py):**

| Code | Name | Meaning | Action |
|---|---|---|---|
| `0` | OK | Clean | Continue |
| `1` | WARN | Non-critical warnings | Show warnings; continue |
| `10` | E_PRECOND | Missing file / bad argument | Stop; fix inputs |
| `11` | E_STRUCTURE | Missing abstract/keywords/sections | Stop; rewrite mainbody.tex |
| `12` | E_CONSIST | Language mismatch or structural inconsistency | Stop; fix language/structure |
| `20` | E_CITE | \\cite keys missing from .bib / papers.json | Stop; repair bibliography |
| `21` | E_BIB | Duplicate .bib keys or unescaped `&` | Stop; fix references.bib |
| `22` | E_DOI | DOI mismatch between .bib and papers.json | Stop; reconcile DOI |
| `30` | E_LATEX | Unescaped LaTeX special characters | Stop; fix mainbody.tex |

Stderr format: `[E{code}] description\n       Fix: suggestion`

**Abort on any code ≥ 10.** Codes 10–30 are all hard failures — stop, read the stderr message, and resolve before continuing.

**Warning-only (exit code 1 or heuristic warnings):**
- LaTeX special-character heuristics: show with file:line; user decides whether to fix.
- Word-count results: informational; never block progress.

## Check Modes

Resolve `$SURVEY_LANG` from the explicit language passed by the orchestrator
(`zh` / `en`). Do not infer it from `writing_constraints.json` or `outline.json`,
and do not default to `zh` when the argument is missing. If no explicit language
is available, stop and ask the orchestrator to provide one.

Use exactly one mode:

- **Standalone mode:** this skill is invoked directly and no prior citation audit
  exists. Run `all` with `cites` enabled and write `$CACHE/all_issues.txt`.
- **Finalize mode:** `surveymaster-finalize` already ran `cites` once before
  BibTeX export. Run `all --skip-cites` with `--cites-audit` and
  `--summary-output`; do not repeat citation analysis.

### Standalone Mode

Run all checks in one `all` invocation — do not call individual subcommands separately:

```bash
python3 <skill_dir>/scripts/survey_checks.py all \
  --mainbody "$WORK/mainbody.tex" --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --extra-tex "$WORK/mainbody.tex" \
  --library "$WORK/papers.json" \
  --bib "$WORK/references.bib" \
  --report-unused \
  --report "$CACHE/all_issues.txt" \
  --report-only --compact \
  --warn-only
```

This single invocation covers: structure (abstract/keywords, `\maketitle`,
`\tableofcontents`, outline section titles, forbidden wrappers/fences, and
`\begin{}\end{}` balance), cites, bib, doi, latex, words. Results are written
to `$CACHE/all_issues.txt` (sections prefixed with `=== <name> (exit N) ===`)
while stdout stays to one `CHECK_RESULT ...` line.

### Finalize Mode

Use this mode only when a prior `$CACHE/cites_audit.txt` exists. The command
writes the full report and compact summary without a separate
`build-check-summary` command:

```bash
python3 "<skill_dir>/scripts/survey_checks.py" all \
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

**Key output fields from the `cites` section in `$CACHE/all_issues.txt`:**
- `distinct_cite_keys=N` — count of unique cite keys found in tex.
- `missing_defined_keys=[...]` — keys in `\cite{}` absent from papers.json (hallucinations).
- `unused_library_keys=[...]` — library keys never cited (coverage gap, only with `--report-unused`).
- `used_cite_keys=[...]` — full list of all confirmed cite keys; written to the report file only, not stdout.

**Key output from the `structure` section:**
- `MISSING_OUTLINE_SECTIONS: ...` — one or more top-level outline section titles are absent from `mainbody.tex`.
- `FORBIDDEN_*` — document wrappers or markdown fences remain and should be cleaned before export.
- `BEGIN_END_MISMATCH: ...` — unbalanced `\begin{env}` / `\end{env}` pairs.

**Evaluate results from `$CACHE/all_issues.txt`:**

- **structure exit 11 or 12:** structure or language issues. Show to the orchestrator.
  `BEGIN_END_MISMATCH` lines are informational for the LLM fix pass; they do not block
  export on their own.
- **cites exit 20:** cite keys missing. Show missing keys, stop. Do not proceed to export.
  - Key exists in `papers.json` but absent from `references.bib`: re-run Stage 5-A BibTeX export.
  - Key does not exist in `papers.json`: treat as hallucinated. **Do NOT look up or insert
    this key into `papers.json`.** Report all hallucinated keys to the user. The LLM fix
    pass in Step 5-B will remove these `\cite{}` calls from the draft. If hallucinated keys
    are too numerous or affect a core section, invoke `surveymaster-write-section --mode rewrite`
    for the affected sections after the fix pass — do not do so before.
- **bib exit 21:** duplicate keys. Show duplicates, stop. Wait for user to fix `references.bib`.
- **doi exit 22:** DOI mismatches. Show `doi_mismatches` lines, stop.
- **doi exit 1:** informational warnings (keys without DOI); continue.
- **latex:** show heuristic hits as warnings; never block progress.
- **words:** only authoritative metric is `texcount_words` TOTAL. If `texcount` is not
  installed, report the error and ask the user to install TeX Live.

Do not create `$WORK/summary.json` in the normal path. Use `$CACHE/all_issues.txt`
or `survey_checks.py all --summary-output` when a compact summary is needed.
`build-check-summary` remains available for older split-step flows.
