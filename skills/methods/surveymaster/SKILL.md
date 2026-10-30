---
name: surveymaster
description: "Produce, revise, or export an academic literature survey through an end-to-end workflow: intake constraints, build a literature library, generate and confirm an outline, write mainbody.tex, run citation and quality checks, export DOCX/LaTeX/BibTeX deliverables, and attempt optional PDF. Use when the user wants a complete literature survey or review paper rather than an isolated search, outline, or section."
---

## Role

This is the top-level SurveyMaster orchestration skill. It coordinates the
child instruction files and helper scripts in this directory to produce a
complete academic survey and final deliverables.

In DSH, the skill loader registers only this top-level `SKILL.md`
as the `surveymaster` skill. Nested `SKILL.md` files are not registered as
separate loadable skills. Treat the files listed below as child instruction
files: read them lazily from this skill directory immediately before the stage
that needs them, resolve their scripts/assets relative to their own directory,
and follow their stage contracts.

This top-level file defines the required execution order, handoff files,
confirmation gates, and browser-use requirements.

## Child Instruction Files

Read child instruction files lazily, immediately before the stage that needs
them:

1. `surveymaster-identify/SKILL.md`
2. `surveymaster-literature-library/SKILL.md`
3. `surveymaster-generate-outline/SKILL.md`
4. `write_section/surveymaster-write-section/SKILL.md`
5. `surveymaster-finalize/SKILL.md`

Supporting/reference instruction files used by the stages:

- `surveymaster-browser-search/SKILL.md`
- `surveymaster-check-and-merge/SKILL.md`
- `surveymaster-figure-types/SKILL.md`
- `surveymaster-table-types/SKILL.md`
- `surveymaster-export/SKILL.md`

## Required Inputs

Collect or infer the following before starting:

- `topic` — survey topic.
- `subject` — discipline or research field.
- `language` — `zh` or `en`.
- `citation_style` — one supported style, confirmed before Stage 1 completes.
- `output_dir` — survey workspace directory.
- Optional: `target_paper_count`, `focus_points`, `reference_surveys`,
  `year_range`, `extra_requirements`, `total_length_target`, and
  `section_length_policy`.

If `output_dir` is not provided, create or choose a dedicated workspace and use
that path consistently as `$WORK`.

## Workspace Contract

All stages operate on the same `$WORK` directory.

Canonical files:

| Stage | File |
|---|---|
| Stage 1 | `$WORK/writing_constraints.json`, `$WORK/writing_constraints.md` |
| Stage 2 | `$WORK/papers.json` |
| Stage 3 | `$WORK/outline.json`, `$WORK/outline.md` |
| Stage 4 | `$WORK/mainbody.tex`, `$WORK/figures/` |
| Stage 5 | `$WORK/references.bib`, final `.docx`, `.tex`, optional `.pdf` |

Do not duplicate source-of-truth data in prompts when a downstream script can
read the canonical file directly.

## File Write Policy

Use `Write` or `Edit` for file writes performed by the agent. Do not use shell
heredocs for LaTeX or JSON content because backslashes can be corrupted.

Helper scripts may write their own outputs normally.

## Stage 0 — Preflight

Before running child instruction files:

1. Confirm `$WORK` exists or create it.
2. Confirm the current request has `topic`, `subject`, and `language`.
3. If the request provides an unambiguous supported `citation_style`, pass it
   through to Stage 1.
4. If `citation_style` is missing, unsupported, or ambiguous, do not ask from
   this top-level file. Read `surveymaster-identify/SKILL.md` and follow its
   Citation Style gate exactly.

The top-level orchestrator must not duplicate or override the citation-style
option list. Stage 1 owns the supported-style list, the `ask_user` prompt, and
the `citation_style_confirmed` value.

## Stage 1 — Identify Writing Constraints

Read `surveymaster-identify/SKILL.md`.

Goal: create:

- `$WORK/writing_constraints.json`
- `$WORK/writing_constraints.md`

Pass the topic, subject, language, optional citation style, and optional user
constraints.

This stage:

- preserves user intent as operational constraints;
- records focus points, target paper count, year range, length policy, and
  venue/style notes;
- detects and resolves user-provided seed papers using browser-use or
  remote-browser only;
- records venue/style constraints, using browser-use or remote-browser only
  when the user asks for target journal or venue-specific requirements;
- writes `citation_style`, `citation_style_confirmed`, and
  `figure_color_policy`. For economics empirical-style templates only, Stage 1
  may ask the user once whether generated mechanism/workflow/review schematic
  figures should use low-saturation academic color or black-and-grayscale
  journal style.

Gate:

- Do not proceed unless `writing_constraints.json` exists and
  `citation_style_confirmed` is true.
- Display `writing_constraints.md` as an informational summary.
- Do not ask for a second confirmation of writing constraints.

## Stage 2 — Build Literature Library

Read `surveymaster-literature-library/SKILL.md`.

Goal: create and validate:

- `$WORK/papers.json`

Execution:

1. Insert resolved seed papers from `writing_constraints.json`.
2. Decompose the topic and focus points into 3-5 English search phrases.
3. For Stage 2 candidate discovery, use browser-use or remote-browser only.
   Treat browser-use/remote-browser as a capability category and required
   infrastructure, not as a literal tool-name requirement or an optional search
   backend. It includes any runtime-exposed browser automation tool that can
   open real web pages, navigate/search, inspect page content, and write
   extracted candidates, including deferred MCP tools such as
   `mcp_remote_browser_*`. Do not start, continue, recover, or supplement with
   `PaperSurveyToFile`, `PaperSearch`, academic search APIs, generic WebSearch,
   DOI/title lookup APIs, OpenAlex/Crossref/Semantic Scholar/CORE/Lens API
   endpoints, or any other non-browser retrieval tool. Opening an API endpoint
   in browser-use/remote-browser does not make it a valid browser discovery
   branch. OpenAlex/Crossref may be used only by
   `discover_and_resolve_papers.py` after the merged browser candidate file has
   already been written. Do not ask the user to choose between browser-use and
   academic-search, and never mark academic-search or any non-browser search
   tool as recommended. Have the agent call browser-use, remote-browser, or an
   equivalent discovered browser MCP tool and write candidates to
   `$WORK/.cache/scratch/browser_candidates.json`. When the runtime supports
   multiple browser-use/remote-browser sessions, run independent query/site
   searches in parallel and save each branch under
   `$WORK/.cache/scratch/browser_candidates.<branch>.json`; after all branches
   finish, merge/deduplicate them into
   `$WORK/.cache/scratch/browser_candidates.json`, then resolve and import them
   with:

   ```bash
   python3 <literature_skill_dir>/scripts/discover_and_resolve_papers.py \
     --work "$WORK" \
     --candidates-json "$WORK/.cache/scratch/browser_candidates.json" \
     --library "$WORK/papers.json" \
     --bibliography-script "<literature_skill_dir>/scripts/bibliography_library.py"
   ```

4. If browser-use/remote-browser does not appear available, do not infer final
   unavailability from planning context, a missing convenience shortcut, or the
   absence of a literal tool named `browser-use`. First run the runtime's tool
   discovery/find_tools mechanism with queries such as `browser`,
   `remote-browser`, `remote browser`, `browser automation`, and `MCP remote
   browser`. If tools such as `mcp_remote_browser_*` are discovered, activate
   and use them as browser-use/remote-browser equivalents. Only after discovery
   and an actual invocation failure showing the browser service is not started
   may the agent treat browser tooling as unavailable; then stop Stage 2 and
   ask the user to enable browser-use/remote-browser. Do not offer
   academic-search,
   PaperSearch, PaperSurveyToFile, WebSearch, or DOI/title lookup as a fallback
   or selectable alternative. Do not call `ask_user`, `request_user_input`, or
   any choice UI with non-browser search options; if a UI prompt is unavoidable,
   it may only ask the user to enable browser-use/remote-browser or stop Stage
   2, and it must not include any recommended fallback.

5. If browser-use/remote-browser is available but individual searches fail,
   retry with browser-use/remote-browser using adjusted sites, queries, or
   timing. Access/CAPTCHA/rate-limit failures are reported as browser failures;
   they do not authorize non-browser search tools.

6. Manual `batch.json` insertion is not a search fallback and is not available
   for Stage 2 candidate discovery or abstract/digest
   supplementation timeouts. If abstract supplementation times out, first count
   successfully supplemented records with information-rich abstracts. When the
   count is at least 30, stop searching and proceed with those records. When the
   count is below 30, retry supplementation once with an about-25-second timeout
   and 4-6 concurrent branches where supported. If the retry still leaves fewer
   than 30 successful records, ask the user whether to continue
   browser-use/remote-browser searching/supplementing, narrow scope, or proceed.
   Abstract supplementation must use browser-opened source pages such as
   publisher, journal, PubMed/PMC, CNKI detail, NBER, SSRN, RePEc, CEPR, IZA,
   author, or institutional repository pages. Do not use OpenAlex/Crossref API
   responses as the primary abstract source.
   Do not create `batch.json` from search previews, browser candidates,
   non-browser search output, or half-resolved candidates after abstract timeout.

7. Validate after every import:

   ```bash
   python3 <literature_skill_dir>/scripts/bibliography_library.py validate \
     --library "$WORK/papers.json"
   ```

8. Run `stats` for compact reporting. Do not read the entire raw `papers.json`
   solely to report progress.

Gate:

- `papers.json` must exist and validate.
- If coverage is far below `target_paper_count`, ask the user whether to
  proceed, narrow scope, expand year range, or add papers.

## Stage 3 — Generate Outline

Read `surveymaster-generate-outline/SKILL.md`.

Goal: create:

- `$WORK/outline.json`
- `$WORK/outline.md`
- `$WORK/.cache/scratch/outline_self_check.json`

Execution:

1. Generate a structured outline from topic, `writing_constraints.json`, and
   `papers.json`.
2. Write the generated JSON to `$WORK/outline.json`.
3. Normalize and render with:

   ```bash
   python3 <outline_skill_dir>/scripts/save_outline.py \
     --file "$WORK/outline.json"
   ```

4. Run the mandatory outline self-check described by
   `surveymaster-generate-outline`.
5. Save or update `outline.md` through the platform's user-visible file
   preview/update mechanism, then display/preview it for the user.
6. Ask the Stage 3 outline approval gate with `ask_user` and
   `allow_other: false`.

Hard gate:

- Do not proceed to Stage 4 until the user selects `Accept and start writing`
  / `接受，开始写作` in the Stage 3 `ask_user` gate.
- If the user selects `I want changes` / `我要修改`, stop and ask the user to
  provide the requested outline changes in the next message. Do not start
  writing.
- If `ask_user` is unavailable, times out, returns no answer, or returns a
  fallback/proceed-best-judgment message, treat the outline as unconfirmed.
  Stop and wait for explicit user input; do not proceed to Stage 4.
- After receiving requested changes, mutate `outline.json` first, re-run
  `save_outline.py`, re-display/preview the outline, and ask the same
  `ask_user` confirmation gate again.
- Never edit `outline.md` directly as the source of truth.

## Stage 4 — Write Full Body

Read `write_section/surveymaster-write-section/SKILL.md`.

Goal: create:

- `$WORK/mainbody.tex`
- `$WORK/figures/<id>.png` when figures are planned

Execution:

1. Build compact paper context through `surveymaster-literature-library` using
   `build-write-context`.
2. Write a single complete `mainbody.tex` body fragment in one pass.
3. Do not create separate section files.
4. Ensure `mainbody.tex` starts with `\begin{abstract}` and contains:
   - `\keywords{}`
   - `\maketitle`
   - `\tableofcontents`
   - all required `\section{}` entries
5. Do not include LaTeX wrappers such as `\documentclass`, `\usepackage`,
   `\begin{document}`, `\end{document}`, bibliography commands, or manual
   reference lists.
6. Use only `\cite{key}` keys allowed by the compact citation map.
7. If figures are planned, read `surveymaster-figure-types/SKILL.md` to build
   `% FIGURE` prompts, call the agent's `image_gen` tool to generate matching
   `$WORK/figures/<id>.png` files.
8. If tables are planned, read `surveymaster-table-types/SKILL.md` to build
   compliant domain-specific tables.
9. Validate and promote the scratch `mainbody.tex` using
   `surveymaster-check-and-merge/scripts/survey_checks.py repair-structure`.

Gate:

- `mainbody.tex` must exist and pass structure validation.
- Figure/table count warnings may be reported, but unresolved fatal structure
  errors must be fixed before Stage 5.

## Stage 5 — Finalize And Export

Read `surveymaster-finalize/SKILL.md`.

Goal: produce and persist final deliverables:

- `$WORK/references.bib`
- `$WORK/<stem>.docx`
- `$WORK/<stem>.tex`
- `$WORK/<stem>.pdf` when the default optional PDF attempt succeeds

Execution order is owned by `surveymaster-finalize/SKILL.md` and must not be
reordered:

1. Citation audit.
2. Initial BibTeX export from `mainbody.tex` and `papers.json`.
3. Metadata verification and volume/pages resolution.
4. Final BibTeX sync.
5. Full deterministic checks.
6. Mandatory single LLM fix pass.
7. Structure validation of fixed body.
8. Rebuild `references.bib` after fix pass.
9. Unified export through `surveymaster-export/SKILL.md`.

PDF is attempted by default as an optional deliverable, and is not a fallback
artifact. The only valid PDF is produced by
`surveymaster-export/scripts/export_all.py` through `latexmk -xelatex` and is
reported with `engine=latexmk-xelatex` or `pdf_engine=latexmk-xelatex`. Do not
use HTML-to-PDF, browser print-to-PDF, screenshots, Pandoc-to-PDF, or any
separate PDF conversion skill/tool for this workflow.
10. Final cite consistency check against `references.bib`.
11. Persist all required deliverables, and persist PDF only when it succeeds.

Important:

- `references.bib` is generated in Stage 5 by
  `surveymaster-literature-library/scripts/bibliography_library.py export-bib`.
- It is first created during Step 5-A Phase 2.
- It is rebuilt after the Step 5-B fix pass so it matches the final
  `mainbody.tex` citation set.
- Do not run export with a stale `references.bib`.

## Post-Export Revision Routing

Any change after export makes previous deliverables stale.

Route requests as follows:

- Export-only change: rerun Stage 5.
- Local content/style change: run Stage 4 in rewrite mode or a refinement skill,
  then Stage 5.
- Figure/table insertion/removal/regeneration: edit `mainbody.tex` and
  `outline.json` consistently, regenerate local image assets when needed, re-run
  `save_outline.py`, then Stage 5.
- Paper/library change: update `papers.json`, validate, decide whether Stage 3
  or Stage 4 must be rerun, then Stage 5.
- Outline change: mutate `outline.json`, re-render `outline.md`, get explicit
  user confirmation, rerun Stage 4, then Stage 5.
- Language change: rerun Stage 1, Stage 3, get outline confirmation, rerun
  Stage 4, then Stage 5. Never machine-translate existing `.tex` files.

## Reporting

At each gate, report concise status and the next required action.

Final response after Stage 5 must include:

- what was completed;
- deliverable status by format;
- any failed or skipped formats;
- any user-actionable warnings.

Do not present stale deliverables as current.
