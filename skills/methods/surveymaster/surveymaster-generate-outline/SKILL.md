---
name: surveymaster-generate-outline
version: 0.2.0
description: "Generate a structured, hierarchical academic survey outline for a research topic. Use when the user wants to plan or outline a literature survey or review paper. Supports zh and en output. Emits outline.json (script-normalized, including core_claim, length_target, and key_papers) and outline.md (human-readable view)."
argument-hint: "<topic> [--language zh|en] [--papers papers.json] [--constraints writing_constraints.json] [--title preferred-title] [--constraints-text extra-constraints] [--revise-from outline.json]"
---

## Stage Contract

Stage: 3 — outline generation and revision.

Loaded by: SurveyMaster orchestrator after Stage 2 has produced `papers.json`,
or when an already-generated outline must be revised.

Required inputs:
- `$WORK/writing_constraints.json`.
- `$WORK/papers.json`.
- Topic, language, and optional title or extra outline constraints.
- Existing `outline.json` in revision mode.

Outputs:
- `$WORK/outline.json` as the normalized structured outline and single source of truth.
- `$WORK/outline.md` as the user-readable outline view.

Completion condition:
- Both outline files exist.
- `outline.json` contains `core_claim`, `length_target`, and `key_papers` in each relevant entry.
- The orchestrator has saved or updated `outline.md` through the platform's
  user-visible file preview/update mechanism before showing the outline
  approval gate. The file existing on disk in `$WORK` does not substitute for
  this user-visible preview/update step.
- The user has confirmed the outline through the Stage 3 `ask_user` approval
  gate with `allow_other: false`.
- `ask_user` fallback/no-answer/timeout is not confirmation and must not satisfy
  this completion condition.

May load other skills:
- no.

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use shell heredocs — they corrupt backslashes in LaTeX and JSON.

## Dependencies

| File | Purpose |
|------|---------|
| `scripts/save_outline.py` | Normalize the outline and write `outline.json` plus `outline.md` |

No external packages required (stdlib only). Requires `python3` on PATH.

`<skill_dir>` in script invocations refers to the directory containing this skill's `SKILL.md` file (the current skill's installation directory, provided by the runtime).

## Arguments

$ARGUMENTS

- First positional arg (or `--topic`) — **required**
- `--language zh|en` — normally passed explicitly by the orchestrator based on
  the current user request; if absent, detect from the current topic text only:
  CJK-heavy → zh, otherwise → en. Do not infer language from existing
  `writing_constraints.json` or `outline.json`.
- `--papers <file.json>` — optional; informs outline structure and paper assignment
- `--constraints <file.json>` — **strongly recommended**; the
  `writing_constraints.json` produced by Stage 1. Drives section count,
  `total_length_target`, per-section `length_target`, `focus_points`,
  `extra_requirements`, `venue_style_notes`, and `citation_style`.
- `--title <text>` — preferred title hint (you may improve it)
- `--constraints-text <text>` — free-text additional outline constraints
  (merged with `--constraints` file content if both are present)
- `--revise-from <file.json>` — revision mode: skip Step 2 generation and
  re-normalize/re-render the already-mutated outline through Steps 3–4.
  See Step 2 and Step 3 for revision-specific behaviour.

## Fixed output filenames

This skill writes two fixed files under `<output-dir>`:

| Filename | Role |
|----------|------|
| `outline.json`        | Script-normalized outline and source of truth for downstream scripts. Each entry stores structure plus `core_claim`, `length_target`, and `key_papers`. |
| `outline.md`          | Human-readable rich view |

Both filenames are fixed. Do not rename. Downstream skills
(`surveymaster-write-section`, `surveymaster-refine-section`) read the outline
from `outline.json` only.

Both files are written by a single `save_outline.py` invocation — never write
`outline.md` manually.

## Step 1 — Load inputs

Read `--papers` if provided. On file-not-found: report path and continue
without papers.

`papers.json` must be the canonical Stage 2 literature library, including
records produced from browser-use candidates through
`discover_and_resolve_papers.py` / `bibliography_library.py insert`. This skill
depends only on canonical fields, not PaperSearch/PaperSurveyToFile-specific
fields. After loading, build a paper-corpus index:

When `--papers` is provided, verify Stage 2 abstract coverage before generating
the outline:

```bash
python3 <literature_skill_dir>/scripts/bibliography_library.py abstract-coverage \
  --library <papers.json> --min-count 30 --min-chars 300 \
  --output <output-dir>/.cache/abstract_coverage.txt
```

If this command exits non-zero, do not generate `outline.json`. Read the report,
return the orchestrator to Stage 2 for one abstract-supplement retry, and if the
retry still leaves fewer than 30 rich abstracts, ask the user whether to proceed
with the low-abstract library. Do not treat a large total record count as a
substitute for rich abstract coverage.

- Required index key: `bib_key`. `paper_ids` and `key_papers` may reference only
  these `bib_key` values.
- Fields used for section assignment: `title`, `abstract`, `journal`, `year`,
  with optional use of `authors`, `doi`, and `url`.
- If any record lacks `bib_key`, do not invent a temporary key. Report the issue
  and require the orchestrator to return to Stage 2 and normalize `papers.json`
  through `bibliography_library.py insert`.
- Records without `abstract` may still provide weak title/venue-level context,
  but should not be selected as body-section `key_papers` unless no other
  abstract-bearing papers are available for that section.
- Prefer papers with abstracts, high relevance to `focus_points`, recency, and
  stronger venue/journal signals when assigning `key_papers`.

Read `--constraints` if provided. On file-not-found: warn and continue with
defaults (zh `total_length_target = 10000` chars, en `= 7000` words;
`target_paper_count = 50`; no focus_points). The warn message must include:
"Warning: writing_constraints.json not found. length_target, citation_style, and other constraints will use defaults and may not match expectations. Complete Stage 1 first if a full survey is planned."
When loaded, extract:

- `language` (override `--language` if set)
- `focus_points`
- `extra_requirements`
- `venue_style_notes`
- `total_length_target`
- `section_length_policy`
- `citation_style`

## Step 2 — Generate outline (skip if `--revise-from` is set)

If `--revise-from <file.json>` is provided, skip this step entirely: load
that file as the outline input, set `survey_title` / `language` from its
top-level fields (falling back to `--title` / `--language`), and jump to
Step 3. Revision mode assumes the caller has already applied the desired
edits to `outline.json`; this skill only re-normalizes and re-renders.

**zh constraints:**
你是学术综述大纲设计专家。

基础约束：
- 引言与结论不得含子章节；不加摘要章节（摘要在成稿阶段生成）。
- 章节标题不带数字前缀；返回嵌套结构；标题与描述须清晰、学术化。
- 对适合拆分的顶层 section 优先写出 2–4 个 subsection。
- 若输出隐藏思考内容，也使用简体中文。

由 writing_constraints 驱动的约束（若提供）：
- 总字数目标参考 total_length_target；按比例把预算分配到各 section 的
  `length_target`；引言/结论占比可低于正文 section。
- 用户的 focus_points 必须被至少一个 body section 的 core_claim 明确覆盖。
- extra_requirements 与 venue_style_notes 会影响 section 选取与命名。

每个 section 与 subsection 都必须输出：
- `title`
- `description`（3–5 句，足以指导写作）
- `core_claim`（1 句中心论点，必填）
- `length_target`（形如 `{"zh_chars": N}` 或 `{"en_words": N}`）
- `paper_ids`（top-level section：相关 `bib_key` 列表或 `"all"`；
  subsection / subsubsection：`[]`）
- `key_papers`（2–5 个来自文献库的 `bib_key`）

规模下限：除引言和结论外至少规划 5 个正文 section；每个非平凡 section
设 2–4 个 subsection；section description 须足够详细以指导写作。

**en constraints:**
You are an academic survey outline designer.

Base rules:
- Introduction and Conclusion must not have subsections. Do not include
  Abstract in the outline.
- No numeric prefixes in section titles. Prefer nested structure. Titles
  and descriptions must be clear and academic.
- Add 2–4 subsections to any body section that can be meaningfully divided.
- If the model emits hidden reasoning, keep it in English.

**Rules from writing_constraints (when provided):**
- Allocate the `total_length_target` across sections, filling each entry's
  `length_target`; Introduction/Conclusion may be smaller than body sections.
- Every user `focus_point` must be explicitly covered by at least one body
  section's `core_claim`.
- `extra_requirements` and `venue_style_notes` shape section selection and
  naming.

Every section and subsection MUST emit:
- `title`
- `description` (3–5 sentences, enough to guide writing)
- `core_claim` (one sentence, required)
- `length_target` (`{"zh_chars": N}` or `{"en_words": N}`)
- `paper_ids` (top-level section: list of relevant `bib_key`s or `"all"`;
  subsection / subsubsection: `[]`)
- `key_papers` (2–5 `bib_key`s from the paper corpus; subsection may be empty)

**No quantity predictions:** Never state a specific count for things not yet
computed (e.g. "this survey will have N sections" or "will cite N papers")
unless the count comes from an already-executed script or a number the user
explicitly specified. Use open-ended language for expected outcomes.

**Scale rules** (adaptive to user request and constraints; no fixed floor):
- Section count and naming priority: ① user's explicit section count/direction in topic > ② `required sections` from writing_constraints > ③ default (nothing specified): 3–5 body sections excluding Introduction and Conclusion.
- Subsection count adapts to parent section's `length_target`:
  - `[zh]` < 800 chars: no subsections or 2 max; ≥ 1200 chars: 2–4 subsections recommended.
  - `[en]` < 500 words: no subsections or 2 max; ≥ 800 words: 2–4 subsections recommended.
  - Do not split into subsections just to meet a count.
- Never expand a user-specified N-part outline into N+1 or more. If critical content cannot fit, use embedded implementation (see Critical-organization below) — do not add sections.
- When the user designates brief vs. focus sections, the focus section's `length_target` must be ≥ 2× the brief section's.

**Title naming rules (mandatory):**

- Top-level body section titles MUST NOT be bare clichés; they must contain a concrete mechanism keyword, research object, or evaluation dimension. Bad examples: "Recent Progress" / "Current Status" / "Methods Overview" / "Related Work" / "Algorithm Survey"

- **Substitution test (applies to all titles):** Before finalizing any title, ask: could this exact wording — with only the topic name swapped — appear in a different paper on the same broad subject? If yes, replace the generic portion with a content-specific term drawn from the section's `core_claim`: a named mechanism, clinical challenge, method, tool, evidence class, or comparison dimension that is unique to this survey. Typical words to replace: "background" / "progress" / "frontiers" / "advances" / "history" / "landscape"

- **Information-density test (applies to all titles):** A reader skimming only the section headings — without reading any descriptions — must be able to anticipate the section's central claim, key trade-off, or distinguishing finding. Titles that convey only a topic area (what the section is *about*) fail; titles that convey a specific angle, constraint, or result (what the section *argues or shows*) pass.

- **Academic register requirement (applies to all titles):** Titles must use plain descriptive noun phrases that name a mechanism, method, result, or trade-off. Do NOT use literary, metaphorical, or rhetorically charged language — these belong in popular-science writing, not academic survey headings.

- Recommended title length:
  - `[zh]` 6–10 characters; shorter acceptable only if a concrete research object is included.
  - `[en]` 4–8 words; shorter acceptable only if a concrete research object is included.

- **Title standard:** all section titles must follow academic conventions — concise, accurate, and sufficiently descriptive of the section's scope and content. No specific title forms are forbidden or required; the standard is that a reader can understand the section's focus from the title alone without ambiguity.

**Critical-organization requirement (mandatory; adaptive to outline scale):**
- **Mandatory content**: the outline MUST cover at least one of: research gap / open debate in the field / evidence-strength comparison across different sources.
- **Placement** (pick one; do not invent extra sections):
  - Body sections ≥ 4: may use a dedicated body section placed before the conclusion.
  - Body sections = 2–3: a dedicated subsection inside a core body section, or fold into the conclusion's `core_claim` and `description`.
  - When the user's conclusion section already names "future directions / bottlenecks / gaps": that section's `core_claim` alone is sufficient.
- **Unifying evaluation framework** (mandatory regardless of section count): the introduction's `core_claim` MUST explicitly describe a framework containing ALL THREE — none may be omitted:
  1. **Framework name** (e.g. `[zh]` "配位强度—空间位阻—给体原子三参数空间" / `[en]` "coordination-strength × steric-hindrance × donor-atom three-parameter space")
  2. **Constituent dimensions / parameters** (explicitly list 2–4 named analytical dimensions)
  3. **Evaluation criteria / comparison baseline** — what is being evaluated (e.g. advantage-validity conditions, applicability boundaries) and what it is compared against (e.g. classical baseline methods, current state-of-the-art). A framework with only dimension names but no criteria or comparison target is non-compliant.

  The framework name must be referenced in the conclusion's `core_claim` and used as an analytical dimension in at least two body sections' `description`s. This applies equally to 4-section and 5-section outlines.

**Transition and progression (mandatory):**
- When a parent section contains ≥3 heterogeneous subsections (covering clearly different sub-problems / mechanisms / method classes), its `core_claim` MUST explicitly establish the logical relationship among those subsections, using one of: "progressive (A is the prerequisite for B, B extends to C)" / "closed-loop (A→B→C forms a complete chain)" / "complementary (A, B, C cover dimensions X, Y, Z respectively)" / "contrastive (A vs B reflects the tradeoff of ...)"
  A bare list-style `core_claim` ("this section discusses A, B, and C") is forbidden.
- The parent section's `description` must additionally state the basis on which subsections are organized (by mechanism type / by temporal evolution / by problem layer / by comparison dimension), not merely paraphrase the subsection titles.

**Evidence-source tagging in descriptions (mandatory):**
- Each body section's `description` MUST end with an evidence-source tag (pick 1–3 labels): "theoretical analysis / numerical demonstration / hardware experiment / review-based judgment / experimental observation / first-principles calculation / literature meta-analysis"
  - Format: "(Evidence source: theoretical analysis + numerical demonstration, with limited hardware-experiment validation)"
- This tag is outline-internal planning metadata. It helps the writing stage judge evidence hierarchy, but it must never be copied or paraphrased into publishable prose as "Evidence source: ..." / "证据来源：..." text.

### Output JSON schema (produce exactly this shape)

```json
{
  "survey_title": "...",
  "language": "zh|en",
  "expected_figures_total": 3,
  "expected_tables_total": 2,
  "sections": [
    {
      "index": 1,
      "title": "...",
      "type": "section",
      "description": "...",
      "core_claim": "...",
      "length_target": {"zh_chars": 1500},
      "paper_ids": "all",
      "key_papers": ["bib_key_a", "bib_key_b"],
      "planned_figures": [
        {"type": "architecture_diagram"}
      ],
      "planned_tables": [
        {"type": "performance_comparison"}
      ],
      "subsections": [
        {
          "index": 2,
          "title": "...",
          "type": "subsection",
          "description": "...",
          "core_claim": "...",
          "length_target": {"zh_chars": 500},
          "paper_ids": [],
          "key_papers": []
        }
      ]
    }
  ]
}
```

**`planned_figures` field rules:**
- Each top-level section may carry an optional `planned_figures` array.
- Each entry contains only `{"type": "<figure_type>"}`. No caption or prompt is specified here — write-section generates those from `core_claim`.
- `type` must be one of: `concept_illustration`, `architecture_diagram`, `workflow_diagram`, `comparison_visual`, `timeline_visual`.
- The total count of `planned_figures` entries across all sections must equal `expected_figures_total`.
- **Introduction first:** assign the first figure to the Introduction section whenever `expected_figures_total ≥ 1`. Preferred types: `architecture_diagram` (research landscape/taxonomy) or `timeline_visual` (development history).
- **Conclusion excluded:** do not assign any figures to the Conclusion section.
- Subsections do not carry `planned_figures`; assign only at the top-level section.

**`planned_tables` field rules:**
- Each top-level section may carry an optional `planned_tables` array.
- Each entry contains only `{"type": "<table_type>"}`. No column spec or caption is specified here — write-section generates those from `core_claim`.
- `type` must be one of: `performance_comparison`, `classification_comparison`, `challenge_strategy_matrix`.
- The total count of `planned_tables` entries across all sections must equal `expected_tables_total`.
- **Introduction and Conclusion excluded:** do not assign any tables to Introduction or Conclusion sections.
- Subsections do not carry `planned_tables`; assign only at the top-level section.

> **Rule Quick-Reference (Mandatory)**:
>
> **User has NOT specified the number of sections** (free-form outline generation):
> - Introduction section `core_claim`: explicitly describe the unified evaluation framework (must include keywords such as "evaluation framework / design space / parameter space").
> - The second-to-last body section: may serve as a standalone "Research Gaps / Controversies" section (title and `core_claim` must contain the corresponding keywords).
>
> **User has specified N sections and their naming direction in the topic** (e.g., a 4-section outline):
> - Strictly follow the user-given number of sections and naming direction; **adding new sections is forbidden**.
> - Introduction section reuses the user-provided name, but the `core_claim` must still explicitly describe the unified evaluation framework.
> - Critical content (research gaps / controversies) is merged into the `core_claim` and `description` of the last user-specified section.
> - Conclusion section title reuses the user-provided name.
> - The `description` of every body section must still end with an "(Evidence source: …)" annotation.
>
> **Shared Requirements**: Append an evidence-source annotation at the end of every body section's `description`; the `core_claim` of any parent section with ≥3 subsections must include one of: progression / closure / complementarity / contrast.
>
> These two scenarios correspond to the rules in the Step 4 self-check. All self-check items must PASS.

## Step 3 — Save output files

`save_outline.py` normalizes the outline, stores rich fields
(`core_claim`, `length_target`, `key_papers`) directly in `outline.json`, and
renders `outline.md` — all in one invocation. No separate heredoc for Markdown.

Use the `Write` tool to write the generated JSON directly to
`<output-dir>/outline.json`, then invoke the script to normalize that same file
in place and render `outline.md`. The script reads JSON content directly from
`--file`; never pass JSON through `$(cat ...)` or any other shell substitution,
because large or multi-line LLM-generated payloads can exceed `ARG_MAX` or be
corrupted by the shell layer before argparse sees them.

When writing `<output-dir>/outline.json`, write only the JSON object itself:
no Markdown code fence, no explanatory prose, no comments, and no trailing text.
Use ASCII JSON structural characters (`{}`, `[]`, `:`, `,`, `"`) even when the
string values are Chinese. Chinese punctuation is allowed inside quoted string
values only. If normalization reports a JSON syntax error, do not regenerate the
whole outline first; run `save_outline.py` on the same file once, because it can
extract fenced JSON and normalize common fullwidth structural punctuation before
failing with a precise parse location.

1. `Write` → `<output-dir>/outline.json` with the JSON produced in Step 2
2. Run:

```bash
python3 <skill_dir>/scripts/save_outline.py \
  --file <output-dir>/outline.json
```

For **`--revise-from` mode**, write the mutated `outline.json` content back to
`<output-dir>/outline.json` and re-run the same command. Because rich fields
live inside each outline entry, preserving user edits means preserving those
fields in the mutated JSON before invoking the script:

1. `Write` → `<output-dir>/outline.json` with the JSON loaded via `--revise-from`
2. Run:

```bash
python3 <skill_dir>/scripts/save_outline.py \
  --file <output-dir>/outline.json
```

On failure, `outline.json` is left in its pre-normalized form for inspection.
The authoritative outputs are `outline.json` and `outline.md` under
`<output-dir>`.

## Step 4 — Quality self-check (mandatory, structured, with audit trail)

**This step is non-skippable and must produce a structured artifact on
disk. The agent MUST NOT proceed to Step 5 until this artifact exists
and all FAIL items have either been repaired or annotated.**

> **Why this step is strict (read before evaluating):** in past runs the
> outline generator emitted body sections with `key_papers: []` even when
> a paper corpus was provided, and introduction `core_claim` fields that
> lacked an explicit evaluation framework. These are the exact patterns
> this self-check is designed to catch. Treat each check as an actual
> evaluation against the JSON content — not as a self-affirmation. Read
> the title strings and `core_claim` fields back from
> `<output-dir>/outline.json` and apply each rule literally.

### Step 4-A: Run the checklist and write a structured report

Iterate over every checklist item below. For each item, record:
- the item id (1–7);
- a `status` of `PASS` / `FAIL` / `REPAIRED`;
- when `FAIL` or `REPAIRED`, the offending `index` values and a one-line
  explanation of why the item failed;
- when `REPAIRED`, the new title / core_claim / description text after
  the fix.

Write the report to `<output-dir>/.cache/scratch/outline_self_check.json`
using the `Write` tool. Schema:

```json
{
  "outline_path": "<absolute path to outline.json>",
  "language": "zh|en",
  "section_count_body": 4,
  "checks": [
    {
      "id": 1,
      "name": "title_naming_compliance",
      "status": "PASS|FAIL|REPAIRED",
      "violations": [
        {"index": 5, "title": "总结与展望", "reason": "first token is blacklisted '总结与展望'"}
      ],
      "repairs": [
        {"index": 5, "field": "title", "new_value": ""}
      ]
    }
  ],
  "overall_status": "PASS|REPAIRED|WARN",
  "warn_reasons": []
}
```

If you skip writing this file, Step 5 must refuse to display the outline
and instead return an error to the orchestrator.

### Step 4-B: Repair pass (single iteration only)

For every check with `status: FAIL`, generate the repaired entry/entries
in memory, re-run `save_outline.py` to persist the edits, then re-evaluate
that single check. Update its `status` to
`REPAIRED` (if the second evaluation passes) or keep `FAIL` (if it still
fails). Do **not** loop more than once. Any item that ends in `FAIL`
sets `overall_status` to `WARN` and is added to `warn_reasons`.

### Step 4-C: Checklist (each item evaluated against the outline)

1. **Title quality check.** For every top-level section title, verify that the title follows academic conventions: it must be concise, non-ambiguous, and sufficiently descriptive that a reader can understand the section's scope from the title alone. Titles that are too vague (single generic word with no topic context) are WARN; titles that are clearly unrelated to the section content are FAIL.

2. **Critical-organization presence (any of three locations counts).**
   At least one of the following holds:
   - a dedicated body section's `title` or `core_claim`,
   - a dedicated subsection's `title` or `core_claim`,
   - the conclusion section's `core_claim` or `description`,

   contains one of: `研究缺口`/`未解问题`/`争议`/`证据强弱`/`证据强度`/`research gap`/`open question`/`debate`/`evidence-strength`/`evidence strength`. (Case-insensitive substring match.) The skill does not require a dedicated section — embedded implementation in the conclusion counts.
3. **Unifying evaluation framework with three-part description.** The
   introduction's `core_claim` MUST contain ALL THREE of:
   - **(a) framework name** (a noun phrase explicitly naming the
     framework, e.g. "三参数设计空间" / "problem-algorithm-resource-deployability matrix");
   - **(b) constituent dimensions** (2–4 named analytical dimensions
     enumerated explicitly, e.g. "配位强度、空间位阻、给体原子" or
     "problem complexity, algorithm cost, resource budget, deployability");
   - **(c) evaluation criteria / comparison baseline** (what is being
     evaluated and against what — keywords to look for: `成立条件`/`适用边界`/`经典基线`/`对照对象`/`基准`/`advantage condition`/`applicability boundary`/`classical baseline`/`benchmark`/`comparison target`).

   FAIL if any of (a)/(b)/(c) is missing. The same framework name (as in
   (a)) must also appear in the conclusion's `core_claim` and in at
   least two body sections' `description`. **This rule applies uniformly
   regardless of section count.**
4. **Transition core_claim for heterogeneous parents.** For every parent
   section with ≥3 subsections, its `core_claim` contains one of:
   `递进`/`闭环`/`互补`/`对照`/`progressive`/`closed-loop`/`complementary`/`contrastive`. Bare list-style claims fail this check. **Sections with < 3 subsections are exempt from this check.**
5. **Evidence-source tagging.** Every body section's `description` ends
   with a parenthesized tag containing `证据来源` or `Evidence source`.
6. **Section-count fidelity.** The number of top-level body sections
   (excluding Introduction and Conclusion) must equal the number the
   user explicitly specified in the topic description (count Roman
   numerals or "第 X 部分" enumerations and subtract Introduction +
   Conclusion). If the user did not specify, this check is automatically
   PASS. **Failure here is the highest-priority FAIL** — never expand
   or shrink the user's stated section count to satisfy other checks.
7. **`key_papers` density.** For every top-level body section (excluding
   introduction and conclusion), `key_papers` must contain ≥ 2 entries
   from the paper corpus. Subsections may have empty `key_papers`. If
   `--papers` was not provided to this skill (no paper corpus exists),
   this check is automatically WARN (not FAIL) — and the agent must
   add a top-level `pending_paper_search` field to the report so the
   orchestrator knows Stage 2 needs to be revisited.
8. **`expected_figures_total`, `expected_tables_total`, `planned_figures`, and `planned_tables` consistency.**
   - Both top-level count fields must exist and be non-negative integers. Read from
     `writing_constraints.json` `target_figure_count` / `target_table_count` when
     present; otherwise default to `3` figures and `2` tables. FAIL if either field
     is missing from the output JSON.
   - When `expected_figures_total > 0`: the sum of `planned_figures` entries across
     all top-level sections must equal `expected_figures_total`. FAIL if they diverge.
   - Each `planned_figures` entry `type` must be one of the five valid types
     (`concept_illustration`, `architecture_diagram`, `workflow_diagram`,
     `comparison_visual`, `timeline_visual`). FAIL on any invalid type.
   - Introduction section must have at least one entry in `planned_figures` when
     `expected_figures_total ≥ 1`. WARN (not FAIL) if it is absent.
   - When `expected_tables_total > 0`: the sum of `planned_tables` entries across
     all top-level sections must equal `expected_tables_total`. FAIL if they diverge.
   - Each `planned_tables` entry `type` must be one of the three valid types
     (`performance_comparison`, `classification_comparison`, `challenge_strategy_matrix`).
     FAIL on any invalid type.
   - Introduction and Conclusion sections must NOT carry `planned_tables`. FAIL if present.

**Repair pass scope:** when a check fails, re-run Step 2 generation
**only for the failing entries** (pass `--revise-from` with the failing
entries' indices noted in the prompt). Do not regenerate the entire
outline — preserve passing entries to keep the user-visible structure
stable.

If an in-skill repair would conflict with an active user revision, skip the
repair pass and emit warnings instead — the user is editing manually and should
not be overridden.

## Step 5 — Display and summary

**Pre-condition (hard gate):** before doing anything in this step, the
agent MUST read `<output-dir>/.cache/scratch/outline_self_check.json`
written in Step 4. If the file does not exist, abort and return an
error message: `"ERROR: Step 4 self-check artifact missing. Cannot
display outline. Re-run from Step 4."` Do not proceed.

Read `<output-dir>/outline.md` from disk and display its content to the user.

Then report:
- Survey title
- Language
- Section count and total entry count
- Paths of `outline.json`, `outline.md`
- Any warnings (missing `core_claim` auto-detected by script, `--constraints`
  missing, `--papers` missing)
- After the bullets, append the absolute path of the self-check JSON so
  the orchestrator can re-read it programmatically.

**HARD STOP — this skill is now complete.** The orchestrator (top-level agent)
must NOT proceed to section writing until the user explicitly accepts the
outline through `ask_user`. The required next action is:
1. Display `outline.md` content to the user (already done above).
2. Save or update `outline.md` through the platform's user-visible file
   preview/update mechanism.
3. Ask the Stage 3 confirmation gate with `ask_user`, setting
   `allow_other: false`:
   - zh question: `以下是本次综述的大纲。是否接受该大纲并开始写作？`
   - en question: `The outline above is ready. Accept it and start writing?`
   - options: `接受，开始写作` / `Accept and start writing`; `我要修改` / `I want changes`.
4. If the user selects accept, proceed to Stage 4.
5. If the user selects changes, stop and ask the user to describe the requested
   outline changes in the next message. Do not invoke any writing skill.
6. If `ask_user` is unavailable, times out, returns no answer, or returns a
   fallback/proceed-best-judgment message, treat the outline as unconfirmed.
   Stop and wait for explicit user input; do not invoke any writing skill.

When displaying assigned papers:

- Concrete list: show every paper as `bib_key - <exact title>` with count; no omissions.
- `"all"`: show total count only; do not enumerate.
- `[]`: state `No papers assigned.`

Subsections inherit parent paper assignment; do not show a separate list unless
the user asks. For every concrete-list section, self-check that the displayed
bullet count equals `len(paper_ids)`.

## Appendix — Outline revision discipline

**Consistency invariant:** `outline.json` is the only structured outline source
of truth. Each entry in its `outline` array contains both structural fields
(`title`, `type`, `description`, `parent_index`, `paper_ids`) and rich writing
fields (`core_claim`, `length_target`, `key_papers`).

Never edit `outline.md` directly. To revise the outline, mutate `outline.json`
first, then re-run `save_outline.py` through this skill to normalize
`outline.json` and re-render `outline.md`.

When a user asks to modify the outline, the orchestrating agent must:

1. **Mutate JSON, not MD.** Translate the user's intent into edits on
   `outline.json`. Common mutations:
   - Rename a section → update `title` in the matching `index` of
     `outline.json`.
   - Add / remove a subsection → edit the nested `subsections` array when
     re-generating, or add/remove the flat entry in `outline.json`.
   - Change length target → update the entry's `length_target`.
   - Change core claim → update the entry's `core_claim`.
   - Re-assign papers → update `paper_ids`; update `key_papers` if the user specified them.
2. **Re-normalize via this skill.** Re-invoke `surveymaster-generate-outline`
   with `--revise-from <mutated outline.json>`. That path bypasses Step 2
   generation but still runs `save_outline.py` for normalization and rewrites
   `outline.json` plus `outline.md` atomically.
3. **Never edit `outline.md` directly.** Markdown is a derived view;
   edits there will not survive the next regeneration.
