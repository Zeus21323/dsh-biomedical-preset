---
name: surveymaster-identify
version: 0.2.0
description: Collect survey intake requirements and produce the Stage 1 writing constraint artifacts. Use at the start of a SurveyMaster workflow before literature search. Emits writing_constraints.json and writing_constraints.md under the chosen survey output directory.
argument-hint: "--topic <text> --subject <discipline> [--language zh|en] [--citation-style gb-t-7714-2015-numeric|gb-t-7714-2015-author-date|ieee|ama|apa|nature|acs|cell|science|elsevier-with-titles|rsc] [--target-paper-count N] [--focus-points text] [--reference-surveys text] [--year-range text] [--extra-requirements text] [--output-format text] [--section-length-policy json] [--total-length-target text] --output-dir <dir>"
---

## Stage Contract

Stage: 1 — Intake and writing constraints.

Loaded by: SurveyMaster orchestrator when no confirmed `writing_constraints.json`
exists, or when `citation_style_confirmed` is still `false`.

Required inputs:
- User topic and discipline.
- Survey language, explicit or inferred.
- Citation style resolved by the orchestrator, either explicitly supplied by the user or selected before this skill is called.
- Target paper count and focus points, explicit or defaulted.
- Optional reference surveys, year range, output format, length policy, and extra requirements.
- `$WORK` output directory.
- Browser-use, remote-browser, or an equivalent runtime-exposed browser MCP tool
  for seed-paper metadata discovery and downstream literature-search readiness.

Outputs:
- `$WORK/writing_constraints.json` as the structured source of truth.
- `$WORK/writing_constraints.md` as the user-facing derived view.

Completion condition:
- `writing_constraints.json` exists.
- `citation_style_confirmed` is `true`.
- `writing_constraints.md` exists and has been shown or reported to the caller
  as the user-facing summary before proceeding to Stage 2.
- Browser-use, remote-browser, or an equivalent browser MCP tool was available
  during normal Stage 1 execution.

May load other skills:
- no.

## File Write Policy

Use the current runtime's file write/edit tools for file writes. Keep
`writing_constraints.json` as the source of truth: mutate or create the JSON
first, then render `writing_constraints.md` from it. Never use shell heredocs
for JSON, Markdown, or LaTeX-like content because backslashes and quoting can be
corrupted.

## No Scripts — Agent Executes Directly

This skill has **no helper scripts and no `scripts/` directory**. All operations
are performed directly by the agent using the tools available in the current
session.

For literature discovery, use only browser-use, remote-browser, or an equivalent
runtime-exposed browser automation MCP tool such as `mcp_remote_browser_*` when
it can open real pages, navigate/search, inspect page content, and extract
metadata. Do not use any non-browser retrieval tool as a substitute, including
`web_fetch`, `academic_search_en`, `WebSearch`, `PaperLookupByDoi`, or
`PaperLookupByTitle`.

Normal execution requires browser-use, remote-browser, or an equivalent browser
MCP tool. If no browser tool is visible, first run the runtime's tool
discovery/find_tools mechanism with queries such as `browser`,
`remote-browser`, `remote browser`, `browser automation`, and `MCP remote
browser`; activate matching tools such as `mcp_remote_browser_*`. If discovery
and actual invocation still show browser tooling is unavailable, abort before
writing outputs and tell the user to enable browser-use/remote-browser.

Do not attempt to run `python3 <skill_dir>/scripts/...` — no such files exist
for Stage 1.

## Purpose

Produce the Stage 1 writing constraints for a survey workflow. This skill is
the contract for the identity/intake stage; it does not search papers, generate
an outline, or write survey prose.

## Outputs

Create these files under `<output-dir>`:

| File | Role | Source of truth? |
|---|---|---|
| `writing_constraints.json` | Machine-readable constraints for downstream skills | Yes |
| `writing_constraints.md` | User-facing rendered view | Derived |

Do not create an `identity.md` output artifact. If an external
`identity.md` prompt exists, treat it as reference text only.

## Required Inputs

Collect all missing required fields in one turn:

- `topic`
- `subject` (discipline)
- `language` (`zh` / `en`; normally passed explicitly by the orchestrator. If
  absent, detect from the current request only: explicit output-language wording
  wins; otherwise use the dominant language of the full request body; otherwise
  use the dominant language of topic/focus text. Do not inspect existing
  `writing_constraints.json`, `outline.json`, filenames, or prior artifacts.)
- `target_paper_count` (default: `50`)
- `focus_points` (1-5 items)

Optional fields:

- `citation_style` (see "Citation Style" below; normally provided by the orchestrator before first generation)
- `reference_surveys`
- `year_range` (default: last 8 years)
- `extra_requirements`
- `section_length_policy`
- `total_length_target`

No field in the final JSON may be left empty. If a value remains unknown after
search, set an explicit default and record the reason in `assumptions`.

## No Quantity Predictions

Never state or imply a specific count for things that depend on external retrieval
or LLM generation and have not yet been computed. This includes:

- "I will search for N papers" / "会找到约N篇文献"
- "The survey will be N words long" / "预计字数约N字"
- "This will produce N sections" / "将生成N个章节"

Only report counts that come from an already-executed script or completed
retrieval. Use open-ended language for planning: "we'll search for papers
matching your focus points", "the body length will follow the constraints you set".

## Seed Papers

Scan all user-provided input (topic, focus_points, extra_requirements, and any
free-text) for candidate paper references before writing any output file.

**Detection patterns** (recognize any of these forms):
- DOI patterns: `10.\d{4}/...` anywhere in the text
- arXiv IDs: `arXiv:\d{4}.\d{4,5}` or `https://arxiv.org/abs/...`
- Quoted or unquoted title strings long enough to be a paper title (>= 6 words)
- Author + year references: "Smith et al., 2023", "Smith 2023", "Smith and Jones (2022)"
- Natural-language descriptions: "the paper on X published in Nature in 2022", "XX等人2023年的工作"
- Numbered lists or bullet lists of papers the user says they have already found

**Resolution — for each detected reference (call in parallel when possible):**
1. Use browser-use or remote-browser only. Open authoritative metadata pages in the browser and extract metadata from those pages. Do not call `web_fetch`, `academic_search_en`, generic web-search tools, or paper lookup APIs for this step. Follow the runtime's browser-use/remote-browser lifecycle rules. For biomedical/life-science seed papers, prioritize PubMed-style
   metadata pages. For economics/Chinese academic seed papers, prioritize
   CNKI-style metadata pages when access is available. For arXiv identifiers,
   use arXiv metadata pages. For DOI-bearing papers, use publisher, Crossref,
   OpenAlex, PubMed, or other authoritative metadata pages when available.
2. Collect only auditable metadata. Do not download full papers, copy full
   text, or paste long abstracts. Use abstracts only as metadata for relevance
   and downstream planning.
3. Store every detected seed paper in `seed_papers` using the fixed schema
   below. If metadata cannot be resolved, preserve the user-provided title or
   raw reference in `title`, leave unknown fields empty, and add an explanatory
   entry to `assumptions`.
4. Do not create or update `papers.json` in Stage 1. Seed papers are candidate
   inputs for Stage 2, where the literature library owns deduplication,
   validation, bib-key generation, and insertion.

Do not skip detection. If the user provides 10 papers, preserve all 10 in the
fixed `seed_papers` structure, resolving metadata where available.

**Discard policy for user-provided information:**

When a user-provided DOI, title, or other paper reference cannot be reliably
verified, prefer discarding the record over propagating unreliable data:

- If a DOI lookup or browser metadata page returns no result or a clearly
  mismatched title, preserve the user's raw reference in `seed_papers` with
  unknown fields empty and add an `assumptions` note. Do NOT add it to
  `papers.json`.
- If title search returns results but none match the user-provided title (e.g.,
  publication year, venue, or first author differ significantly), do not guess.
  Preserve the raw title and leave unverified fields empty.
- A partial record that is missing author, year, or venue is **not** inserted
  into `papers.json`. It remains only as a Stage 1 seed paper candidate.
- If the user insists a paper is correct but lookup fails consistently,
  ask the user to supply the DOI directly rather than inserting an unverified record.

The principle: **an empty slot in the library is less harmful than a wrong
record.** Downstream citation checks and BibTeX export will flag missing
metadata, which is fixable. A hallucinated or incorrect paper citation is
not fixable after export.

**Intent inference from resolved seed papers:**

After resolving available metadata, inspect the `title`, `abstract`, `journal`,
and any visible keywords of successfully resolved papers to:

- **Verify or refine `subject`:** if the user did not specify `subject` explicitly,
  infer it from the dominant field/venue of the seed papers. Record as
  `(搜索参考)` / `(from seed papers)` in `writing_constraints.md`.
- **Strengthen `focus_points`:** if the user provided fewer than 3 focus_points,
  suggest up to 2 additional ones derived from recurring themes in seed paper
  abstracts. Mark them `（来自候选文献推断）` / `(inferred from seed papers)` in
  `writing_constraints.md` so the user can confirm or reject them.
- **Detect year range:** if `year_range` was not specified, set it to cover the
  earliest seed paper year to the current year. Record as `(from seed papers)`.

**JSON storage** (`seed_papers` array in `writing_constraints.json`):

Every seed paper object must contain exactly these stable fields:

```json
"seed_papers": [
  {
    "title": "Paper title",
    "authors": ["Author A", "Author B"],
    "year": "2024",
    "journal": "Journal Name",
    "doi": "10.xxxx/yyyy",
    "url": "https://example.com/paper",
    "abstract": "..."
  }
]
```

If no seed papers were detected, set `"seed_papers": []`.

Field rules:

- `title`: paper title or, if unresolved, the raw user-provided paper reference.
- `authors`: array of author display names; use `[]` when unknown.
- `year`: string year such as `"2024"`; use `""` when unknown.
- `journal`: stable venue field. It may contain a journal name, conference
  name, preprint server, working-paper series, repository, or `"unpublished"`
  when applicable; use `""` when unknown.
- `doi`: normalized DOI without `https://doi.org/`; use `""` when absent or
  unknown.
- `url`: plain URL string, not a Markdown link; use `""` when unknown.
- `abstract`: abstract text when available from an auditable metadata source;
  use `""` when unknown. Do not store full paper text.

Do not add `bib_key`, `lookup_status`, `source_type`, or other extra fields to
items in `seed_papers`; Stage 2 owns normalized library records and citation
keys.

**Markdown view:** when `seed_papers` is non-empty, add a section to
`writing_constraints.md`:

```
## 候选文献（用户提供）/ Seed Papers (user-provided)
- "MXene surface terminations..." — Smith, Jones (2023), Journal Name, DOI: 10.xxxx/...
- "Some Paper Title the User Typed" — metadata unresolved; preserved from user input
```

Include the number of detected seed papers and note any unresolved metadata in
the assumptions/defaults section.

## Intent Preservation

The intake stage must preserve user intent as operational constraints, not just
summarize the topic.

- If the user specifies a required section structure or exact part names, copy
  those names into `extra_requirements` verbatim and state that downstream
  outline titles should align unless the user later approves changes.
- If the user names required mechanisms, variables, properties, application
  directions, or comparison dimensions, include each named item in
  `focus_points` or `extra_requirements` using the user's wording. Do not merge
  specific items into broad buckets when that would make them disappear later.
- If the user marks priorities among sections or topics, encode that priority
  in `section_length_policy` and mention it in `writing_constraints.md`.
- For broad application lists, preserve every named application as a coverage
  checklist item. Downstream outline and writing skills must be able to check
  whether each item was covered.

## Citation Style

The supported bibliography style names are **only** one of the following:

- `gb-t-7714-2015-numeric`
- `gb-t-7714-2015-author-date`
- `ieee`
- `ama`
- `apa`
- `nature`
- `acs`
- `cell`
- `science`
- `elsevier-with-titles`
- `rsc`

`citation_style` should be resolved by the orchestrator before first invocation.
If the user's initial request does not explicitly name a supported style, the
orchestrator asks the user to choose one before calling this skill. If the user
already named a supported style, the orchestrator maps it to one of the values
above and passes it directly.

Normal first-time generation uses the caller-provided `--citation-style` and
sets `citation_style_confirmed: true` in `writing_constraints.json`.

Compatibility fallback when `--citation-style` is **not** passed:

| `language` | default `citation_style` |
|---|---|
| `zh` | `gb-t-7714-2015-numeric` |
| `en` | `ieee` |

This fallback exists only for older or interrupted flows. In that case write
the default style and set `citation_style_confirmed: false`; the orchestrator
must resolve citation style and call this skill again in revise mode before
advancing.

When the orchestrator calls this skill in revise mode with an explicit
`--citation-style`, set `citation_style` to the user's choice and set
`citation_style_confirmed: true` in the JSON, then re-render
`writing_constraints.md`. Without an explicit `--citation-style` in revise mode,
preserve the existing `citation_style` value and the existing
`citation_style_confirmed` flag unchanged.

## Venue And Style Constraints

Stage 1 does not normally spend browser-use work on venue/style discovery.
Unless the user explicitly asks for venue-specific submission constraints, use
the Fallback Defaults table and set:

```json
{"name": "default", "url": null}
```

for `constraint_source`.

If the user names a target venue but does not explicitly ask to apply that
venue's submission constraints, preserve the venue name in `extra_requirements`
or `venue_style_notes`, but still use the Fallback Defaults table.

Only run browser-based official-source discovery when the user explicitly asks
for target-venue constraints, journal/conference-specific limits, or submission
format requirements. In that case, use browser-use, remote-browser, or
equivalent browsing tools to inspect official author guidelines, instructions
for authors, review article guides, or article-type requirement pages.

**Progress reporting (zh surveys):** refer to this step as "期刊/会议投稿要求搜索" or "目标期刊写作规范搜索".

Optional discovery priority when venue-specific constraints are explicitly
requested:

1. If a target venue is named in `extra_requirements` or user context, inspect
   that venue's official author guidelines, instructions for authors, review
   article guide, or article-type requirements page.
2. If no target venue is named, and the subject strongly implies a common venue
   family, inspect one authoritative official source for that family only when
   browser tools are available and the result can be audited.
3. If no useful official source is found, stop discovery and use the Fallback
   Defaults table. Do not keep expanding to generic web pages.

After inspecting an official source, verify that it contains review-specific
requirements: a dedicated word limit, section structure, reference-count
guidance, or figure/table limits for review, survey, narrative review, or
similar article types. A general author guide shared across all article types
is not sufficient; treat it as no useful result.

Extract concrete constraints when available:

- total word/character limit
- abstract limit and abstract structure
- required section structure
- reference count guidance
- figure/table limits → write as `target_figure_count` (integer) and `target_table_count` (integer)
- special formatting or venue-specific requirements

Resolution order for `target_figure_count` / `target_table_count`:
1. User explicitly states a count in the request (e.g. "需要 3 张图" / "include 2 tables") → use that value directly.
2. Venue guide specifies a figure/table limit → derive counts from it.
3. Neither specified → use the Fallback Defaults (3 figures, 2 tables).

When user or venue values are higher than the defaults, use them. Do not cap user intent at the default values.

Add `constraint_source` to `writing_constraints.json`:

```json
{"name": "<venue-or-source-name>", "url": "<url>"}
```

If no useful source is found, use:

```json
{"name": "default", "url": null}
```

Do not reference local personal skill directories or machine-specific paths as
style sources. Only use files bundled inside this skill package, runtime tools,
or auditable browser-discovered official sources.

## Fallback Defaults

If venue/style constraints are not explicitly requested, or optional
venue-specific discovery does not yield actionable constraints, apply these
defaults:

| Field | zh | en |
|---|---|---|
| body length | 8,000 chars | 5,000 words |
| abstract | <=300 words, 3-part structure | <=300 words, 3-part structure |
| required sections | 引言 -> 方法（可选） -> 主体讨论 -> 结论 | Introduction -> Methods (optional) -> Discussion -> Conclusion |
| references | 50-75 | 50-75 |
| `target_figure_count` | 3 (default when user does not specify) | 3 (default when user does not specify) |
| `target_table_count` | 2 (default when user does not specify) | 2 (default when user does not specify) |
| Introduction | 600-1000 chars | 400-600 words |
| each body section | 1000-1800 chars | 700-1100 words |
| Conclusion | 400-600 chars | 200-350 words |
| special_requirements | 无 | none |

## Domain Writing Templates

Before applying the Fallback Defaults table, inspect
`../surveymaster-domain-templates/README.md` and load any matching template file
from that directory. Domain templates apply when the topic or subject clearly
matches a bundled domain and the user has not explicitly requested another
target journal, conference, or venue-specific writing constraint.

If a domain template applies, use its `constraint_source`,
`venue_style_notes`, default constraints, and writing-pattern requirements in
place of the generic fallback defaults. Preserve user-specified values such as
requested length, figure/table counts, focus points, citation style, and special
requirements. If no domain template clearly applies, use the generic Fallback
Defaults table above.

## Figure Color Policy

Stage 1 owns the figure color policy. Write the result to
`writing_constraints.json` as:

- `"figure_color_policy": "low_saturation_color"` for ordinary academic
  color figures.
- `"figure_color_policy": "black_and_grayscale"` for black-and-white /
  grayscale figures.

Default behavior:

- For non-economics empirical-style templates, set
  `figure_color_policy: "low_saturation_color"` without asking the user.
- If the user explicitly requests color figures, set
  `figure_color_policy: "low_saturation_color"` without asking.
- If the user explicitly requests black-and-white, grayscale, or a venue
  requirement that figures be black-and-white, set
  `figure_color_policy: "black_and_grayscale"` without asking.
- If the selected template is the economics empirical-style template
  (`constraint_source.name == "bundled economics empirical-style review template"`
  or `venue_style_notes` explicitly contains `Economics empirical-style review`)
  and the user did not explicitly specify figure color, ask once with `ask_user`
  before writing outputs.

Economics empirical-style figure-color gate:

- Use `allow_other: false`.
- For Chinese surveys, ask:
  `本综述中的机制图、流程图和综述示意图需要使用哪种图片风格？`
- For English surveys, ask:
  `Which visual style should mechanism, workflow, and review schematic figures use?`
- Options:
  1. zh: `低饱和彩色学术配色（推荐）` -> `low_saturation_color`
     en: `Low-saturation academic color (recommended)` -> `low_saturation_color`
  2. zh: `黑白灰期刊风格` -> `black_and_grayscale`
     en: `Black-and-grayscale journal style` -> `black_and_grayscale`

If `ask_user` is unavailable, times out, returns no answer, or returns a
fallback/proceed-best-judgment message, default to
`low_saturation_color`, record an `assumptions` entry explaining the fallback,
and continue. This gate is a preference clarification, not a hard workflow
block.

## JSON Schema

`writing_constraints.json` must include at least:

```json
{
  "topic": "...",
  "subject": "...",
  "language": "zh",
  "citation_style": "gb-t-7714-2015-numeric",
  "target_paper_count": 50,
  "focus_points": ["..."],
  "reference_surveys": [],
  "year_range": "last 8 years",
  "extra_requirements": "none",
  "total_length_target": {"zh_chars": 8000},
  "section_length_policy": {
    "default_min": {"zh_chars": 1200},
    "overrides": {
      "introduction": {"zh_chars": 600},
      "regular": {"zh_chars": 1200},
      "conclusion": {"zh_chars": 400},
      "abstract": {"en_words": 250}
    }
  },
  "venue_style_notes": "...",
  "constraint_source": {"name": "default", "url": null},
  "citation_style_confirmed": true,
  "target_figure_count": 0,
  "target_table_count": 0,
  "figure_color_policy": "low_saturation_color",
  "seed_papers": [
    {
      "title": "",
      "authors": [],
      "year": "",
      "journal": "",
      "doi": "",
      "url": "",
      "abstract": ""
    }
  ],
  "assumptions": []
}
```

Use `en_words` instead of `zh_chars` when `language == "en"`.

`citation_style_confirmed` semantics:

- Normal first-time generation: the caller passes `--citation-style`; set
  `citation_style` to that value and set `citation_style_confirmed: true`.
- Compatibility first-time generation without `--citation-style`: use the
  language-aware default from the fallback table above and set
  `citation_style_confirmed: false`.
- Revise-mode call with `--citation-style`: set `citation_style` to that value
  and set `citation_style_confirmed: true`.
- Once `true`, remain `true` across subsequent revise calls unless the revise
  call explicitly mutates `citation_style` again (in which case it stays
  `true`) or explicitly resets it.

## Markdown View

Render `writing_constraints.md` from the JSON. It must be concise and readable
for user confirmation, including:

- topic, subject, language
- citation style
- target paper count
- focus points
- year range
- total length target and section length policy
- venue/style notes
- constraint source
- figure color policy
- assumptions/defaults used

The markdown must include a `Constraint source` line. If
`constraint_source.url` is non-null, render it as `[<name>](<url>)`. If
`constraint_source.name == "default"`, render `Default (no specific venue
requirements)`. For bundled templates with no URL, render the source name
plainly, for example `bundled biomedical review template`.

**Preserve user-provided language:** fields that contain user-provided text
(`topic`, `focus_points`, `extra_requirements`, `reference_surveys`, and similar
free-text constraints) MUST be rendered in the user's original wording and
language. Do not translate user-provided English text into Chinese, or Chinese
text into English. Only system-generated headings, labels, provenance markers,
and default-value annotations follow the resolved `language` field.

**Provenance labeling (required):** every value in `writing_constraints.md`
must be tagged with its origin so the user can distinguish facts from
defaults. Use these inline markers immediately after the value:

- `（系统默认）` / `(system default)` — value was not provided by the user and
  is taken from the Fallback Defaults table.
- `（搜索参考）` / `(from search)` — value was found by browser-based metadata
  discovery or optional official venue/source discovery; include the source URL
  in parentheses when available.
- `（用户指定）` / `(user-specified)` — value was explicitly provided by the
  user in this invocation.

**Settings summary:** at the end of `writing_constraints.md`, append a section
`## 关键设置摘要` (zh) or `## Key Settings Summary` (en) that lists the
high-impact fields for the user's information only:

| 字段 (zh) / Field (en) | 当前值 / Current value | 来源 / Origin |
|---|---|---|
| 研究主题 / Topic | `<topic>` | 用户指定 / User-specified |
| 引用格式 / Citation style | `<citation_style>` | 用户指定 / User-specified |
| 目标篇数 / Target paper count | `<N>` | 系统默认/用户指定/搜索参考 |
| 正文总字数 / Body length target | `<value>` | 系统默认/用户指定/搜索参考 |
| 期刊/会议目标 / Target venue | `<venue or "未指定/None">` | — |
| 年份范围 / Year range | `<range>` | 系统默认/用户指定 |
| 图片配色 / Figure color policy | `<figure_color_policy>` | 系统默认/用户指定/用户选择 |

Do NOT include any "请确认" prompt or language requesting user confirmation.
The table is informational only; the orchestrator proceeds to Stage 2 immediately
after saving the generated files.

## Error Handling

**Abort conditions** — stop immediately and return `ERROR: <reason>` before writing any output:
- `--output-dir` missing or not writable.
- `--topic` or `--subject` empty and not derivable from context.
- `--revise-from` path provided but file does not exist.
- Browser-use, remote-browser, and equivalent browser MCP tools are unavailable
  during normal workflow execution after tool discovery and attempted invocation.
- `writing_constraints.json` write fails (file system error).

**Warning-only** — continue with defaults and include a `assumptions` entry explaining the fallback:
- Optional venue/style discovery returns no actionable result → apply Fallback Defaults table; record source as `{"name": "default", "url": null}`.

**Error message format:**
```
ERROR [surveymaster-identify]: <reason>. <remediation hint>.
```
Example: `ERROR [surveymaster-identify]: --revise-from path not found: /work/writing_constraints.json. Run initial generation first.`

Browser-tooling example:
`ERROR [surveymaster-identify]: browser-use or remote-browser is required for SurveyMaster literature discovery but is not available. Enable browser-use/remote-browser tools, then rerun Stage 1.`

## Gate

After writing both files, show `writing_constraints.md` to the caller. The
orchestrating agent (SurveyMaster) is responsible for saving/updating that file
for the user as an informational summary, then proceeding to Stage 2 immediately.
Do NOT ask the user to confirm the writing constraints.

The orchestrator must not ask the user to choose citation style at this point
unless the user explicitly requests a citation-style change.

Citation-style selection happens before the first generation call when the
initial request is missing a supported style or names an unsupported/ambiguous
style. In that pre-generation case, the orchestrator should use the runtime's
interactive user-input mechanism. In DSH, use `ask_user`.

Use `ask_user` with `allow_other: false` and the full supported
citation-style list below as explicit options. The `options` array MUST contain
all 11 entries for the resolved survey language; do not shorten the list to
recommended/common styles. The citation-style gate accepts only one of these
listed option labels or canonical style codes. If the returned answer is not in
the supported list, ask the user to choose again from the list; do not map or
accept unsupported free-form citation styles, and do not proceed to Stage 2
until a listed style is selected.

If `ask_user` is unavailable, times out, returns no answer, or returns a
fallback/proceed-best-judgment message, treat the citation style as
unconfirmed. Stop before writing outputs and tell the user that citation style
selection is required. Do not choose a default citation style for a new run.

**for Chinese (zh survey — full supported list, Chinese-first order):**
1. `GB/T 7714 顺序编码制（推荐）` -> `gb-t-7714-2015-numeric`
2. `GB/T 7714 著者-出版年制` -> `gb-t-7714-2015-author-date`
3. `IEEE` -> `ieee`
4. `AMA 11th` -> `ama`
5. `APA 7th` -> `apa`
6. `Nature` -> `nature`
7. `ACS 2022` -> `acs`
8. `Cell` -> `cell`
9. `Science` -> `science`
10. `Elsevier with titles` -> `elsevier-with-titles`
11. `Royal Society of Chemistry` -> `rsc`

**for English (en survey — full supported list, international-first order):**
1. `IEEE (recommended)` -> `ieee`
2. `Nature` -> `nature`
3. `Science` -> `science`
4. `ACS 2022` -> `acs`
5. `APA 7th` -> `apa`
6. `AMA 11th` -> `ama`
7. `Elsevier with titles` -> `elsevier-with-titles`
8. `Cell` -> `cell`
9. `Royal Society of Chemistry` -> `rsc`
10. `GB/T 7714 numeric` -> `gb-t-7714-2015-numeric`
11. `GB/T 7714 author-date` -> `gb-t-7714-2015-author-date`

Use this gate message for Chinese surveys:
`开始生成写作约束前，请先选择参考文献引用格式：`

Use this gate message for English surveys:
`Before generating writing constraints, please select a citation style:`

Stage 2 begins only after `citation_style_confirmed` is `true` in the JSON.
Stage 2 must not begin unless browser-based research tooling was available
during Stage 1.

**Confirmation gate:** Always proceed to Stage 2 without waiting for user
confirmation. Do not pause or ask the user to confirm `writing_constraints.md`
regardless of whether fields carry `（系统默认）` / `(system default)` or
`（搜索参考）` / `(from search)` origins. The only user interactions in Stage 1
are citation-style selection before the first generation call and, only for
economics empirical-style templates without an explicit user preference, the
figure color policy preference gate.

## Revision Discipline

This skill supports two revision flavors. Both must obey JSON-first order:
mutate `writing_constraints.json` first, then re-render `writing_constraints.md`,
then return so the caller can save/update the Markdown and continue according to
the citation-style gate state.

**Citation-style revision** — caller passes `--citation-style <choice>` because
the user selected a missing style during resume or explicitly requested a style
change:

1. Mutate `writing_constraints.json`: set `citation_style` to the new choice
   and set `citation_style_confirmed: true`.
2. Re-render `writing_constraints.md`.
3. Return. The orchestrator saves/updates the rendered Markdown and proceeds
   without a separate writing-constraints confirmation.

**Other-field revision** — caller passes any other revised fields without
`--citation-style`:

1. Mutate `writing_constraints.json`: apply the requested changes; preserve
   `citation_style` and `citation_style_confirmed` exactly as they were.
2. Re-render `writing_constraints.md` from the updated JSON; do not mutate the
   Markdown alone.
3. Return. The orchestrator saves/updates the rendered Markdown and proceeds
   according to the earliest affected workflow stage. It must not re-show
   citation-style selection unless `citation_style_confirmed` is `false` or the
   user explicitly asks to change citation style.

Never edit `writing_constraints.md` alone. Never mutate the JSON in a way that
sets `citation_style_confirmed: true` without an explicit `--citation-style`
argument from the caller.
