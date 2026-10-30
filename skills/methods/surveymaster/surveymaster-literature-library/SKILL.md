---
name: surveymaster-literature-library
version: 0.2.0
description: Perform literature-library operations with insert/from-paper-results, silent deduplication, validate, stats, query, compact write-context generation, BibTeX export, filtering, and safe deletion.
argument-hint: "insert|from-paper-results|validate|stats|query|build-write-context|export-bib|filter-year-range|delete-keys [args]"
---

## Stage Contract

Role: Stage 2 literature research and library maintenance; finalization BibTeX
metadata resolution/export when loaded by `surveymaster-finalize`.

Loaded by: SurveyMaster orchestrator after Stage 1 writes confirmed
`writing_constraints.json`, and by Stage 5 immediately before BibTeX export or
metadata repair.

Required inputs:
- `$WORK/writing_constraints.json` for Stage 2. In a custom agent, if `$WORK`
  is not explicitly supplied but a user session workspace exists (for example
  `~/.dsh/sessions/<session_id>/workspace`), use that
  workspace as `$WORK` and read Stage 1 results from
  `$WORK/writing_constraints.json`.
- Literature search or lookup results prepared by the orchestrator.
- `$WORK/papers.json` when updating, validating, querying, or exporting an existing library.

Outputs:
- `$WORK/papers.json` as the canonical literature library.
- Duplicate, validation, stats, query, and BibTeX reports under `$CACHE` or `$WORK`.
- `$WORK/references.bib` during Stage 5 final BibTeX export.

Completion condition:
- Stage 2: `papers.json` exists, validates, and coverage has been reported.
- Stage 5: `references.bib` exists and blocking metadata errors or resolvable warnings have been addressed.

May load other skills:
- no.

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use shell heredocs — they corrupt backslashes in LaTeX and JSON.

## Function

Manage `$WORK/papers.json` as a single source of truth: write/update, validate, query, export, and cleanup.

The library is mutable throughout the whole survey. Initial search, outline planning, and chapter writing must all read/write the same `$WORK/papers.json` instead of keeping paper sets only in prompts.

All metadata inserted from PubMed, Crossref, OpenAlex, publishers, browsers, user uploads, or manual records must be stored as plain text. Strip JATS/HTML/XML markup from title, venue, abstract, and author fields before insertion; examples include `<scp>`, `<sup>`, `<sub>`, and `<i>`. BibTeX export must apply the same cleanup again as a final guard.

## Inputs

- Library path (required; canonical path is `$WORK/papers.json`)
- Subcommand arguments (e.g., keys/year-range/bib output path)
- Optional scan paths (for citation-safety checks before deletion)

## Outputs And Boundaries

- Updated library files, query outputs, BibTeX files, or check reports
- The local scripts do not perform online retrieval. The orchestrator may use
  external search or lookup tools before calling this skill to insert resolved
  structured records.

Canonical scripts:
- `scripts/bibliography_library.py` — manages `$WORK/papers.json` with insert/from-paper-results/validate/stats/query/export.
- `scripts/discover_and_resolve_papers.py` — reads candidate-paper JSON already produced by the agent/browser-use, accepts complete PubMed/PMC/publisher metadata already extracted into candidates, enriches records through Crossref, OpenAlex, and arXiv APIs on a non-blocking basis, then calls `bibliography_library.py insert` to merge records into `$WORK/papers.json`. If OpenAlex is rate-limited, the script skips OpenAlex for the rest of that run and continues with candidate metadata/Crossref/arXiv. This script does not call browser-use; the browser-use plugin must be called by the agent/orchestrator.

`<skill_dir>` in script invocations refers to the directory containing this skill's `SKILL.md` file (the current skill's installation directory, provided by the runtime).

## Stage 2 Orchestration

When this skill is loaded for Stage 2, the orchestrator is responsible for the
online retrieval calls and this skill is responsible for persisting, validating,
deduplicating, querying, and exporting the local library.

Resolve the workspace and Stage 1 result first:

- If the caller explicitly passes `$WORK` or `--library "$WORK/papers.json"`,
  use that directory.
- If `$WORK` is not explicit but the current agent has a user session workspace
  path (for example `~/.dsh/sessions/<session_id>/workspace`),
  use that workspace as `$WORK`. `<username>` and `<session_id>` must not be
  hard-coded; obtain them from runtime context or caller parameters.
- Read Stage 1 results from `$WORK/writing_constraints.json`. If the file
  exists, extract `topic`, `subject`, `focus_points`, `target_paper_count`,
  `year_range`, and `seed_papers` for uploaded-paper understanding, query
  generation, and coverage decisions.
- If `$WORK/writing_constraints.json` is missing, report the missing path. Only
  continue when the caller explicitly provides equivalent topic/focus/target
  constraints; otherwise stop and require Stage 1 first.
- The canonical library path is always `$WORK/papers.json`. If it does not
  exist, create it on the first uploaded-paper or seed-paper insertion with
  `--allow-create`; never write the library into the skill installation
  directory or an arbitrary temporary directory.

Merge user-uploaded paper information into `papers.json` before seed insertion
and keyword search:

- If the user uploaded or supplied paper information in the workspace, the
  orchestrator must first parse it into structured paper records in memory and
  immediately merge those records into `$WORK/papers.json` with `insert`. If the
  runtime must pass `insert --file`, it may use a temporary batch file under
  `$WORK/.cache/scratch/`; that file is command input only, not a workflow
  artifact, and should be deleted or ignored after a successful insert. Each
  structured record must include at least `title`, `authors`, `year`, and a
  publication venue (`journal`, `booktitle`, or `venue`). HTML/PDF/web pages are
  not direct inputs to this script; the orchestrator must first extract metadata
  or resolve DOI/title lookups.
- Insert uploaded papers with `screening_stage: "core"` and
  `core_reason: "user-uploaded paper"`. If only partial metadata is available,
  do not insert records missing title/authors/year/venue; keep them as
  unresolved items and ask for a DOI or title.
- Use `insert` to write uploaded-paper records into `$WORK/papers.json`, then
  run `validate`. This gives later model steps access to normalized uploaded
  paper topics, abstracts, and keywords before generating search queries and
  outlines. Do not maintain a separate `user_uploaded_papers.json` as a source
  of truth.

Run seed insertion after uploaded papers and before keyword search:

- Read `writing_constraints.json` and extract `seed_papers`.
- For every seed paper with `"lookup_status": "resolved"`, insert it with
  `screening_stage: "core"` and `core_reason: "user-provided seed paper"`.
- For every seed paper with `"lookup_status": "unresolved"`, attempt one more
  title lookup. Insert if resolved; otherwise warn and skip. Do not insert a
  record with no metadata.
- After seed insertion, run validation. 

Run browser-use/remote-browser candidate discovery and metadata resolution
after seeds. Stage 2 is browser-only for candidate discovery: do not start,
continue, recover, or supplement candidate discovery with `PaperSurveyToFile`,
`PaperSearch`, academic search APIs, generic WebSearch, DOI/title lookup APIs,
OpenAlex/Crossref/Semantic Scholar/CORE/Lens API endpoints, or other
non-browser retrieval tools. Opening a metadata/API endpoint in
browser-use/remote-browser does not make it a valid browser discovery branch.
OpenAlex/Crossref are reserved for metadata resolution by
`discover_and_resolve_papers.py` after
`$WORK/.cache/scratch/browser_candidates.json` already exists. Treat
browser-use/remote-browser as a browser-automation capability category, not as a
literal tool-name requirement; equivalent runtime-exposed tools include
deferred MCP tools such as `mcp_remote_browser_*` when they can open real pages,
navigate/search, inspect page content, and write candidates. Do not ask the
user to choose between browser-use and academic-search, and never mark
academic-search or any non-browser retrieval tool as recommended. If
browser-use/remote-browser seems unavailable from planning context, a current
tool list, or a missing convenience shortcut, first run the runtime's tool
discovery/find_tools mechanism with queries such as `browser`,
`remote-browser`, `remote browser`, `browser automation`, and `MCP remote
browser`. If matching tools such as `mcp_remote_browser_*` are found, activate
and use them. Only after discovery and an actual invocation failure showing the
browser service is not started may the agent treat browser tooling as
unavailable; then stop and ask the user to enable browser-use/remote-browser
instead of offering a fallback. Do not call
`ask_user`, `request_user_input`, or any choice UI with academic-search,
PaperSearch, PaperSurveyToFile, WebSearch, DOI/title lookup, API endpoint
search, or other non-browser options. If a UI prompt is unavoidable, it may only
ask the user to enable browser-use/remote-browser or stop Stage 2; do not mark
any fallback as recommended.

1. Choose search keywords:
   - If `$WORK/papers.json` exists and is non-empty, read paper `title`,
     `abstract`, `journal`, and `year` and extract 3-5 English keyword phrases
     from those seed papers. Keywords should reflect uploaded/seed-paper topics
     instead of merely restating the broad user topic.
   - If `$WORK/papers.json` is missing or empty, extract 3-5 English keyword
     phrases from `writing_constraints.json` fields `topic`, `subject`, and
     `focus_points`.
   - Each phrase should have 2-5 words and cover different `focus_points` where
     possible. Do not promise a specific number of papers before retrieval.
2. Select search sites from `subject`, `topic`, and `focus_points`, then have
   the agent call browser-use, remote-browser, or an equivalent discovered
   browser MCP tool. Parallel retrieval is allowed and preferred when the
   runtime supports multiple independent browser
   sessions:
   - Biomedical / medicine / clinical / pharmacy / life-science topics: prefer
     PubMed and Google Scholar.
   - Economics / finance / management / socioeconomic topics: prefer CNKI and
     Google Scholar.
   - Engineering / computer science / electronics / mechanical / materials /
     automation topics: prefer arXiv, IEEE Xplore, and Google Scholar.
   - Ambiguous or interdisciplinary topics: use at least Google Scholar, then
     choose the nearest specialized site.
   - Run independent query/site branches in parallel only when they do not share
     the same browser tab/session state. A reasonable default is 2-4 parallel
     branches, capped by the runtime's browser-use/remote-browser limits.
   - Assign each branch a stable name such as `pubmed_query1`,
     `scholar_query1`, `cnki_query2`, or `arxiv_query3`.
   - Before launching browser branches, read
     `surveymaster-browser-search/SKILL.md` and the matching domain reference
     files under `surveymaster-browser-search/references*/SKILL.md`. Those
     child instructions define the browser-use task templates, site-specific
     page handling, and branch-output rules. They are mandatory, not optional.

3. browser-use/remote-browser should extract only the top 10-20 candidates per
   query; normally collect 80-150 candidates first, then let the resolver
   script deduplicate and skip incomplete records. Browser output must be saved
   under the workspace. For parallel branches, each branch writes its own file
   and must not append to a shared file while other branches are running:
   - Do not traverse or read all search results. For each site, inspect only the
     highest-ranked result pages and prioritize papers with higher citation
     counts, download/read popularity, ranking, recency, and keyword relevance.
   - If the page exposes citation count, cited-by count, popularity, recommended
     order, or relevance ranking, prefer candidates with stronger indicators.
     Do not keep clearly low-relevance results or records with no author/year
     and no formal source page merely to fill the quota.

   ```text
   $WORK/.cache/scratch/browser_candidates.json
   ```

   Parallel branch files use:

   ```text
   $WORK/.cache/scratch/browser_candidates.<branch>.json
   ```

   The file must be a JSON array with this shape. `abstract_hint` may only come
   from an explicit Abstract section; do not use search-result snippets as
   abstracts.

   ```json
   [
     {
       "title": "Paper title",
       "doi": "10.xxxx/yyyy",
       "url": "https://example.com/paper",
       "year_hint": "2024",
       "venue_hint": "Journal or Conference Name",
       "authors_text": "Author A, Author B",
       "abstract_hint": "Short abstract if available",
       "source": "browser-use"
     }
   ]
   ```

4. After all browser-use/remote-browser branches finish, merge branch candidate
   files into `$WORK/.cache/scratch/browser_candidates.json` before metadata
   resolution. Deduplicate conservatively by DOI, arXiv ID, normalized title,
   and URL; keep the richer record when duplicate candidates differ. Do not
   insert branch candidates directly into `papers.json`.
5. After the merged browser-use candidate file is written, immediately run
   metadata resolution and library insertion:

   ```bash
   python3 <skill_dir>/scripts/discover_and_resolve_papers.py \
     --work "$WORK" \
     --candidates-json "$WORK/.cache/scratch/browser_candidates.json" \
     --library "$WORK/papers.json" \
     --bibliography-script "<skill_dir>/scripts/bibliography_library.py"
   ```

   The script reads the candidate JSON. If a candidate already comes from
   PubMed/PMC/publisher pages and includes `title`, `authors`, `year`,
   `journal`/`booktitle`, and an explicit `abstract`, those fields are
   acceptable metadata; API calls only enrich DOI, volume/issue/pages, or
   missing fields. Resolution should prefer arXiv when an arXiv ID is present
   and Crossref DOI/title lookups before OpenAlex. OpenAlex is supplemental:
   on HTTP 429, skip OpenAlex for the rest of that run and continue with
   candidate metadata/Crossref/arXiv instead of stopping Stage 2. After records
   are completed, merge them into `$WORK/papers.json` with
   `bibliography_library.py insert`, then run `validate` and `stats`.
6. If valid records in `$WORK/papers.json` are still below
   `target_paper_count`, generate 1-3 additional queries from uncovered
   `focus_points`, rerun browser-use/remote-browser candidate discovery
   (parallel branches allowed under the same rules), and rerun
   `discover_and_resolve_papers.py`. Do not manually concatenate browser
   candidates into `papers.json`; candidates must pass metadata resolution and
   `insert` validation first.

Browser-only failure handling:

- If a browser-use/remote-browser branch returns no usable candidates, adjust
  the query/site and retry with browser-use/remote-browser.
- If browsing is blocked by access/CAPTCHA/rate limits, report the blocked
  browser state and ask whether to continue trying browser-use/remote-browser,
  narrow scope, or proceed with the existing library. Do not offer academic
  search APIs, PaperSearch, PaperSurveyToFile, WebSearch, DOI/title lookup, or
  any other non-browser tool as a fallback.
- If browser-use/remote-browser is not started, stop and ask the user to enable
  it. The only next action is enabling/retrying browser-use/remote-browser or
  stopping Stage 2.

After insertion, for each focus point, pick the top 3 papers and use
browser-use/remote-browser to supplement abstracts or digests. Do not use web
search, academic-search tools, or OpenAlex/Crossref API responses as the
primary source for supplementation. Open real source pages found during browser
discovery, such as publisher/journal pages, PubMed/PMC, CNKI detail pages,
NBER, SSRN, RePEc, CEPR, IZA, author pages, or institutional repositories.
Keep useful supplements information-rich, roughly 800-1200 characters when
available. Never replace a richer existing abstract with a shorter digest.
Abstract supplementation should use a longer timeout budget than ordinary page
reads: about 25 seconds per supplement request (roughly 10 seconds longer than
the old default) and 4-6 concurrent branches when the runtime allows it; if the
runtime exposes a lower hard concurrency limit, use that limit.

Abstract-supplement timeout handling is a hard rule:

- First count valid records in `$WORK/papers.json` that already have an
  information-rich `abstract` / `summary` / `paperAbstract`. An information-rich
  abstract is normally at least 300 characters; short search snippets, title
  restatements, or one/two-sentence digests do not count as successful.
- If the success count is `>= 30`, stop abstract supplementation and stop
  additional searching; proceed to Stage 3 using those successfully supplemented
  records. Do not keep searching just to satisfy `target_paper_count`.
- If the success count is `< 30`, retry abstract supplementation once, only for
  records that did not succeed. The retry uses the same about-25-second timeout
  and 4-6 concurrency budget. Count successes again after the retry.
- If the retry still leaves fewer than 30 successful records, report the success
  count, failure count, and timeout reason, then ask the user whether to continue
  browser-use/remote-browser searching/supplementing, narrow scope, or proceed
  with the current successful records. Do not automatically create `batch.json`,
  and do not treat abstract supplementation timeout as an `insert` fallback
  condition.
- Abstract supplementation timeout is not candidate-import failure. It must not
  trigger `batch.json`, must not skip `discover_and_resolve_papers.py`, and
  must not directly `insert` search previews or half-resolved candidates into
  `papers.json`.

Before declaring Stage 2 complete or entering Stage 3, run this hard gate:

```bash
python3 <skill_dir>/scripts/bibliography_library.py abstract-coverage \
  --library "$WORK/papers.json" --min-count 30 --min-chars 300 \
  --output "$WORK/.cache/abstract_coverage.txt"
```

If the command exits non-zero, read the report and apply the `<30` rule above:
retry abstract supplementation once; if it still fails, ask the user. Do not use
`validate` or `stats` as a substitute for this gate.

Use `insert` (not `from-paper-results`) for manually assembled supplement records
only when the records come from user-uploaded, user-specified, or manually
confirmed papers and already contain complete metadata. Search-tool output and
half-resolved candidates after abstract timeout are not manually assembled
supplement records.

After the search loop, do not read raw `papers.json` just to report progress.
Run `stats --limit 40` and summarize from its compact stdout plus the import
command result lines. When listing papers in any report, identify papers by
`bib_key`, DOI, or `AuthorYear` style labels — never expose raw `paperId` values
in user-facing output.

If coverage is below target, ask the user whether to proceed, narrow scope,
expand year range, or add papers. Otherwise Stage 2 is complete and the
orchestrator may advance to Stage 3.

## Stage 5 BibTeX Resolution

When loaded by `surveymaster-finalize`, run a dry BibTeX export before any final
export. Resolve missing title, author, venue, or year records through DOI/title
lookup and reinsert updated metadata. Resolve missing volume/pages warnings with
`resolve_volume_pages.py` where possible. Re-export final
`$WORK/references.bib` only after blocking metadata issues are addressed.

## Common Commands

> **Path reminder.** Replace `<skill_dir>` with the `skillDir` returned by
> `SkillLoad` for this skill (e.g. `/data/skills/surveymaster-literature-library`).
> Do not execute a literal `<skill_dir>/...`. If `skillDir` is missing, call
> `SkillLoad` again — do not search filesystem paths.

```bash
# ── User-uploaded papers: import first at the start of Stage 2 ──
# The orchestrator first parses HTML/PDF/web pages/user input into structured
# paper records, then directly creates or updates the canonical library.
# A JSON array can be passed through stdin:
printf '%s\n' "$USER_UPLOADED_PAPERS_JSON" | \
  python3 <skill_dir>/scripts/bibliography_library.py insert \
    --library "$WORK/papers.json" \
    --allow-create --skip-invalid

python3 <skill_dir>/scripts/bibliography_library.py validate \
  --library "$WORK/papers.json"

# ── Primary Stage 2 path: browser-use/remote-browser candidates ──
# The agent first searches with browser-use/remote-browser and writes JSON,
# then resolves and imports the candidate records.
# Candidate file:
# $WORK/.cache/scratch/browser_candidates.json
python3 <skill_dir>/scripts/discover_and_resolve_papers.py \
  --work "$WORK" \
  --candidates-json "$WORK/.cache/scratch/browser_candidates.json" \
  --library "$WORK/papers.json" \
  --bibliography-script "<skill_dir>/scripts/bibliography_library.py"

# ── Fallback: manual insert/merge
# Only for non-search results when result files are truly unavailable and the
# records have been manually confirmed as complete.
# Do not import abstract-timeout leftovers, browser candidates, or search-tool
# previews through batch.json.
# 1. Write tool → $WORK/.cache/scratch/batch.json  (temp; deleted after insert)
# 2. Run insert, then delete the scratch file:
python3 <skill_dir>/scripts/bibliography_library.py insert \
  --library "$WORK/papers.json" --file "$WORK/.cache/scratch/batch.json" --allow-create && \
rm -f "$WORK/.cache/scratch/batch.json"

# after every import/insert batch: validation only; keep stdout compact
python3 <skill_dir>/scripts/bibliography_library.py validate \
  --library "$WORK/papers.json"

# Compact progress summary after the search loop; do not read raw papers.json:
python3 <skill_dir>/scripts/bibliography_library.py stats \
  --library "$WORK/papers.json" --limit 40

# query specific keys; write to a file only when another step will consume it
python3 <skill_dir>/scripts/bibliography_library.py query \
  --library "$WORK/papers.json" --keys k1,k2 --format simplified \
  --output "$CACHE/query.txt"

# export bibtex (Stage 5 only, after DOI/title metadata resolution)
# Final pre-PDF export — the script reads mainbody.tex, extracts \cite{} keys,
# and writes only cited library entries:
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
  --library "$WORK/papers.json" \
  --tex-file "$WORK/mainbody.tex" \
  --output "$WORK/references.bib" --warn-limit 10

# Final export after PDF compilation — cited entries only, in reference-list order:
# (run from export-pdf Step 6 using the compiled .bbl; do not call manually)
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
  --library "$WORK/papers.json" \
  --bbl-file "$WORK/build/<stem>.bbl" \
  --output "$WORK/references.bib" --warn-limit 10

# year filter
python3 <skill_dir>/scripts/bibliography_library.py filter-year-range \
  --library "$WORK/papers.json" --min-year 2018 --max-year 2026 \
  --output "$CACHE/literature_filtered.json"

# safe delete (checks citations by default)
# STAGE GUARD: only call delete-keys before section writing begins (Stage 2-3).
# If any section .tex file already exists, deleting a cited key creates orphaned
# \cite{} references and breaks LaTeX compilation. Rewrite citing sections first.
python3 <skill_dir>/scripts/bibliography_library.py delete-keys \
  --library "$WORK/papers.json" --keys old1,old2 \
  --scan-tex "$WORK/sections;$WORK" --dry-run
```

## Field Name Aliases (auto-normalized on insert)

The `insert` command automatically maps common field names to the canonical
library field names before validation. This compatibility is for manually
confirmed non-search records only; it does not permit Stage 2 candidate
discovery, recovery, or supplementation with `PaperSurveyToFile`, `PaperSearch`,
academic search APIs, `PaperLookupByDoi`, or other non-browser retrieval tools.

| Canonical field | Accepted aliases |
|---|---|
| `year`      | `publicationYear`, `publicationDate`, `pub_year`, `pub_date`, `publishedYear`, `date` |
| `authors`   | `authorList`, `author_list`, `authorNames` |
| `journal`   | `publicationEnName`, `journalName`, `journal_name`, `periodical`, `source` |
| `booktitle` | `conference`, `conferenceName`, `conference_name`, `proceedings_name` |
| `abstract`  | `paperAbstract`, `paper_abstract`, `summary` |
| `doi`       | `paperDoi`, `paper_doi` |
| `url`       | `paperUrl`, `paper_url`, `link`, `pdfUrl`, `pdf_url` |
| `title`     | `paperTitle`, `paper_title` |

For `year`, if the value is a date string (e.g. `"2023-05-12"`), the
4-digit year is extracted automatically. Alias keys are preserved in the
stored record alongside the canonical key.

## Abstract Preservation

`abstract`, `paperAbstract`, `paper_abstract`, and `summary` are information-rich
fields. Do not delete them, replace them with generic one-line summaries, or
over-compress them before insert. When merging duplicate records, the insert
script keeps the longer existing abstract/summary if the incoming duplicate has
shorter text. A later update may replace an abstract only when it is at least as
information-rich as the stored value.

## Conventions

- Library path: `$WORK/papers.json` (where `$WORK` is the survey output directory, e.g. `/bohr-workspace/<uuid>/`)
- `$CACHE` = `$WORK/.cache/`; check/report outputs go to `$CACHE`
- Data shape: JSON array (compatible with `surveymaster-write-section`)
- Prefer file outputs for large results to reduce context pollution
- Keep screening metadata when available: `screening_stage` (`candidate`, `screened`, `core`), `relevance_score`, `venue_tier`, `citation_count`, `language`, and `core_reason`.
- Initial research should prefer pessimistic retrieval: 100-300 candidates, then 40-80 screened papers, then 20-50 core writing papers when topic scope allows.
- During writing, update this same library whenever supplemental searches add papers. Deduplicate and validate before those papers are cited.
- Do not export BibTeX during initial search, outline generation, or section writing. Generate `references.bib` in Stage 5 after cited/selected papers have been resolved by DOI or title lookup.
- `export-bib` refuses records missing critical metadata (title, author, publication venue, or year) unless `--allow-incomplete` is explicitly used for diagnostics. Resolve failures via DOI/title lookup, re-insert/update the library, validate, then export.
- `export-bib` warns when `article` / `inproceedings` records are missing `volume` and/or `pages`/`number`. **Before running `export-bib` for final output, you MUST run `resolve_volume_pages.py` to resolve all WARN keys and confirm that every remaining WARN key has `"unresolvable": true` set in `papers.json`. Skipping this step is not allowed.** Do not use `PaperLookupByDoi` or `PaperLookupByTitle` for this purpose. Once a key is marked `unresolvable=true`, treat it as final: subsequent runs of `resolve_volume_pages.py` will auto-skip it (`SKIP_UNRESOLVABLE`) and the resolver will not retry the API. Do not interpret a repeated WARN line for such keys as a signal to re-run the resolver — verify the flag in `papers.json` and move on.

## Resolving Missing Volume / Pages

Use `scripts/resolve_volume_pages.py` to resolve WARN keys. The script queries OpenAlex (primary) with automatic fallback to Crossref, patches only missing fields, and writes directly back to the library. It uses a bounded request pool for DOI metadata fetches, but applies patches and saves the library sequentially in the main process. It is stdlib-only (no extra dependencies).

With `--verify-metadata`, the script additionally checks title, first author, venue, and year against API data for all records that have a DOI, and reports discrepancies (`TITLE_MISMATCH`, `YEAR_MISMATCH`, `VENUE_MISMATCH`, `AUTHOR_MISMATCH`) without modifying those fields. Run with `--dry-run` to avoid writing any changes while still seeing the full report.

### Step 1 — Collect WARN keys

```bash
# Capture export-bib diagnostics in stdout so they can be piped directly.
EXPORT_BIB_DIAGNOSTICS="$(
  python3 <skill_dir>/scripts/bibliography_library.py export-bib \
    --library "$WORK/papers.json" --tex-file "$WORK/mainbody.tex" --output "$WORK/references.bib" \
    --warn-limit 10 --diagnostics-stdout
)"
```

Use `$EXPORT_BIB_DIAGNOSTICS` as the resolver input. Do not write a separate
diagnostics file unless debugging a failed run. Do not run `grep -i "WARN"` or
treat grep exit code `1` as a command failure; no grep match only means there
were no matching lines.

### Step 2 — Resolve with bounded concurrency

By default, the resolver processes DOI metadata fetches with `--concurrency 4`. Increase it only when the network is stable; lower it for rate limits or flaky APIs. This does not introduce concurrent writes.

**You decide how many keys to process per call.** Do not blindly run all keys at once. Choose a batch based on how many you want to verify, network conditions, or time constraints (5–15 keys per batch is a reasonable default).

```bash
# Resolve selected keys with the default request pool:
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021,lee2019"

# Tune the request pool when needed:
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021,lee2019" \
    --concurrency 2

# Dry-run first to preview what would change:
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021" --dry-run

# During finalization, verify only the cited WARN keys selected from export-bib:
printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
  python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" \
    --verify-metadata --verify-targets-only \
    --report-stream stdout
```

After each batch, review the PATCHED / UNRESOLVABLE output. Then decide whether to continue with the next batch or stop.

### Step 3 — Interpret the output, then decide whether to stop

**Do NOT retry based on exit code alone.** The exit code is overloaded; emit the
compact report to stdout and inspect the `SUMMARY:` line:

```bash
METADATA_REPORT="$(
  printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
    python3 <skill_dir>/scripts/resolve_volume_pages.py \
      --library "$WORK/papers.json" \
      --keys "k1,k2,k3" \
      --report-stream stdout || true
)"
```

#### Exit-code semantics

| Exit | Meaning                                                            | Action            |
|------|--------------------------------------------------------------------|-------------------|
| `0`  | All targeted keys are now in a terminal state (patched / already-filled / already-marked-unresolvable) AND no metadata discrepancies. | **Stop. Done.**   |
| `1`  | At least one key is still genuinely unresolved (new `UNRESOLVABLE` this run). | See decision tree below. |
| `2`  | Only metadata discrepancies (`TITLE_MISMATCH` etc.) reported. Volume/pages are fine. | Report to user; do not retry the resolver. |
| `10` | I/O error (library path wrong, JSON corrupt). | Fix path / library; not a network issue. |

#### Per-key report decoder

| report line                                              | Meaning                                | Action for this key      |
|---------------------------------------------------------|----------------------------------------|--------------------------|
| `PATCHED <key>: {...}`                                  | Filled fields this run                 | Done                     |
| `SKIP <key>: fields already populated`                  | Was already complete                   | Done                     |
| `SKIP_UNRESOLVABLE <key>: ...`                          | Previously marked `unresolvable=true`  | Done — never retry       |
| `UNRESOLVABLE <key>: no biblio data from OpenAlex or Crossref` | API has no data; just got marked `unresolvable=true` | Done — accept and move on |
| `SKIP <key>: no DOI in record — cannot fetch`           | Record has no DOI                      | Manually add DOI or accept gap |
| `SKIP <key>: not found in library`                      | Wrong bib_key spelling                 | Fix the key string       |

#### Decision tree for exit code 1

1. Look at the `SUMMARY: ...` line. If `patched=0` AND `newly_unresolvable=0`
   AND there were no `fetch_error` lines, **stop immediately** — nothing
   actionable will change by re-running.
2. If you see `fetch_error <key>: ...` lines with network-like messages
   (timeout, connection reset), retry **at most once** with the same keys
   and the same `--concurrency`. Do not shrink the batch size — concurrency
   is fixed by `--concurrency`, not by the number of keys you pass.
3. If retry still shows the same `UNRESOLVABLE` keys, the records are now
   marked `unresolvable=true` and will be auto-skipped next time. Move on.

#### Confirming with export-bib

After all keys are in a terminal state, re-run export-bib **once** to
confirm the WARN list is either empty or only contains records already
marked `unresolvable=true` in `papers.json`:

```bash
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
    --library "$WORK/papers.json" --tex-file "$WORK/mainbody.tex" --output "$WORK/references.bib" \
    --warn-limit 10 --diagnostics-stdout
```

If the same keys keep appearing in the WARN list but `papers.json` shows
`"unresolvable": true` for each of them, that is the final state. Proceed
to the next step; do not re-run `resolve_volume_pages.py`.

#### Forbidden anti-patterns

- Shrinking batch size (10 → 5 → 2 → 1) hoping it helps — concurrency is
  bounded by `--concurrency`, not by `--keys` length.
- Re-running with the same keys more than 2 times in a row.
- Reading exit code without reading stderr.
