---
name: surveymaster-write-section
version: 0.2.0
description: Write the complete survey body (abstract/摘要, keywords/关键词, and all sections) in one pass, outputting a single mainbody.tex. Use when the user wants to draft or rewrite the full body of a literature survey.
argument-hint: "--output-dir dir [--mode draft|rewrite] [--language zh|en] [--survey-title text] [--core-topic text] [--papers papers.json] [--outline outline.json] [--constraints writing_constraints.json]"
---

## Stage Contract

Stage: 4 full-body drafting and rewrites; Post-export Revision content rewrites.

Loaded by: SurveyMaster orchestrator after the Stage 3 outline gate is confirmed,
or by Post-export Revision when a completed export needs a content rewrite.

Required inputs:
- `$WORK/writing_constraints.json`.
- `$WORK/outline.json`.
- `$WORK/papers.json`.

Outputs:
- `$WORK/mainbody.tex` — the canonical full body containing `\begin{abstract}`,
  `\keywords{}`, `\maketitle`, `\tableofcontents`, and all body `\section{}`s.
  No `sections/` directory is created; no `abstract.tex` or `keywords.tex` are written.
- `$WORK/figures/<id>.png` — one file per figure when `expected_figures_total > 0`.

Completion condition:
- `$WORK/mainbody.tex` exists and contains `\begin{abstract}`, `\keywords{}`,
  and at least one `\section{}`.
- When `expected_figures_total > 0`: every `% FIGURE id=xxx` annotation in
  `mainbody.tex` has a corresponding `$WORK/figures/<id>.png`.

May load other skills:
- `surveymaster-check-and-merge` (scripts only — `SkillLoad` before Bash)
- `surveymaster-literature-library` (scripts only — `SkillLoad` before Bash)

## File Write Policy

Use `Write` (create/overwrite) or `Edit` (patch) for all file writes. Never use shell heredocs — they corrupt backslashes in LaTeX and JSON.

## Arguments

$ARGUMENTS

- `--output-dir <dir>` — survey root directory (**required**)
- `--mode draft|rewrite` — default `draft`; `rewrite` reads existing `mainbody.tex` and revises it
- `--language zh|en` — default `zh`
- `--survey-title <text>`, `--core-topic <text>`
- `--papers <file.json>` — full papers file (optional but required for citations)
- `--outline <file.json>` — full outline file (optional override; default `<output-dir>/outline.json`)
- `--constraints <file.json>` — `writing_constraints.json` (optional override)

## Step 1 — Preflight

If `--output-dir` is missing or empty, abort before reading or writing any file.

Resolve paths **once** and bind to variables for all subsequent Bash commands.

**Prerequisite:** `SkillLoad` `surveymaster-check-and-merge` and
`surveymaster-literature-library` before the Bash block below.

```bash
WORK="<output-dir>"
OUTLINE="${OUTLINE_ARG:-$WORK/outline.json}"
CONSTRAINTS="${CONSTRAINTS_ARG:-$WORK/writing_constraints.json}"
PAPERS="${PAPERS_ARG:-$WORK/papers.json}"
SURVEY_LANG=$(python3 -c "import json,sys; d=json.load(open('$CONSTRAINTS')); print(d.get('language','zh'))" 2>/dev/null || echo "zh")
CHECK_SKILL_DIR="<skillDir from SkillLoad(surveymaster-check-and-merge)>"
LIT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-literature-library)>"
```

If any required file (`$CONSTRAINTS`, `$OUTLINE`) does not exist, abort immediately. For `--mode rewrite`, also verify `$WORK/mainbody.tex` exists. Abort if `$CHECK_SKILL_DIR` or `$LIT_SKILL_DIR` is empty (call `SkillLoad` for the sibling skills first).

Input contract:
- `$OUTLINE` must be the Stage 3 `outline.json` normalized by
  `save_outline.py`, with a top-level `outline` array. Every writable top-level
  entry must have `index`, `title`, `description`, `core_claim`,
  `length_target`, `paper_ids`, and `key_papers`.
- `$PAPERS` must be the Stage 2 `papers.json` normalized by
  `bibliography_library.py insert`. Every citable paper must have `bib_key`;
  prose may cite only keys referenced by `outline.json` `paper_ids` /
  `key_papers`.
- `papers.json` may come from browser-use candidates resolved by
  `discover_and_resolve_papers.py`. This skill depends only on canonical fields:
  `bib_key`, `title`, `authors`, `year`, `journal`, `doi`, `url`, and
  `abstract`, not on PaperSearch/PaperSurveyToFile-specific fields.
- If `outline.json` `paper_ids` / `key_papers` references keys missing from
  `$PAPERS`, `build-write-context` filters those keys out. If any body section
  has no usable keys after filtering, warn and preferably return to Stage 3 to
  reassign papers instead of inventing citations in the body.

Additionally read from `outline.json`:
- `expected_figures_total` (default 0 if absent)
- `expected_tables_total` (default 0 if absent)

If `expected_figures_total > 0`, create `$WORK/figures/` directory:
```bash
mkdir -p "$WORK/figures"
```

## Step 2 — Load inputs

Read each source file **exactly once** here. Do NOT Read `outline.json` again in
any later step — reference the in-memory content only:

- `writing_constraints.json` → fully load
- `outline.json` → fully load; select writable top-level entries (excluding
  `subsection`, `subsubsection`), sort by integer `index` (**read exactly once**)
- Do not `Read` raw `papers.json`. Step 4 builds a compact paper context through
  `bibliography_library.py build-write-context`.

## Step 3 — Build section specs

For each writable top-level entry in sorted index order, extract:

- `section_title`, `section_description`
- Detect section type: introduction (zh: 引言/前言/绪论; en: introduction), conclusion (zh: 结论/总结/结语/结束语; en: conclusion/conclusions), or regular
- `core_claim` from the outline entry — abort if missing or empty
- `length_target` from the outline entry or fallback:
  1. `writing_constraints.section_length_policy.overrides.<type>`
  2. `writing_constraints.section_length_policy.default_min`
  3. hard defaults: zh `1200 chars` / en `900 words`
- `paper_ids` from outline entry; translate `[]` to `"all"` with warning
- `planned_figures` from the outline entry (may be absent or empty list) — a list of `{"type": "<type>"}` objects indicating which figure types to insert in this section
- `planned_tables` from the outline entry (may be absent or empty list) — a list of `{"type": "<type>"}` objects indicating which table types to insert in this section
- child subsection entries whose `parent_index == index`, sorted by integer `index`

## Step 4 — Build compact papers reference

Build the paper context with the literature-library script; do not manually
filter or expand `papers.json` in the LLM context:

```bash
python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" build-write-context \
  --library "$PAPERS" \
  --outline "$OUTLINE" \
  --output "$WORK/.cache/write_paper_context.txt" \
  --abstract-chars 400 \
  --snippet-limit 30 \
  --index-limit 200 \
  --snippet-source key-papers
```

Then read `$WORK/.cache/write_paper_context.txt` exactly once. The file has this
shape:

```text
### Global paper index
[bib_key_a] Title · Year · Venue
[bib_key_b] Title · Year · Venue

### Section citation map
<section_title>: allowed_keys=[k1,k2,...]; key_papers=[k1,k3]

### Key paper evidence snippets
[bib_key_a] <abstract first 400 chars>
```

Rules:

- Each paper appears at most once in `Global paper index`.
- Section entries list citation keys only; do not repeat title/venue/abstract per section.
- Abstract snippets appear only for selected keys and only once per key. Default:
  up to 30 `key_papers`, 400 characters each.
- If a section's `paper_ids` is `"all"`, list all allowed keys in the section map,
  but do not duplicate the global paper index or snippets.
If papers.json is missing, use `(no papers available)`.

## Step 5 — Build language and citation rules block

For `en`:

```text
## Output language (STRICT)
- Write the entire document in **English** only.
- Section/subsection headings in \section{}/\subsection{} must be in English.
- Abstract and keywords in English.
- If the model emits hidden reasoning/thinking content, keep that reasoning in English.

## Quotation marks (**STRICT** — en)
- Use LaTeX curly quotation marks: ``text'' for double quotes, `text' for single quotes.
- Do NOT use ASCII straight double-quotes " " or straight single-quotes ' ' in prose.

## Dash usage (**STRICT** — en)
- Do NOT use em dashes, including both Unicode `—` and LaTeX `--` or `---`, in academic prose.
- Prefer commas, semicolons, colons, parentheses, or separate sentences when clarifying relationships.
- Do not use `--` or `---` as a transition, parenthetical, or emphasis device.

## Citation format (STRICT)
- Always use \cite{key} inline; the bibliography backend handles rendering.
- Use ONLY the \cite{} keys listed in the section citation map.
- Do NOT hand-write bibliography entries, footnotes, numbered references, or author-year citation strings.
- Abstract must NOT contain \cite{} citations.
```

For `zh`:

```text
## Output language (STRICT)
- Write the entire document in **Simplified Chinese**.
- Technical terms, proper nouns, paper titles, and standard abbreviations may remain in English.
- Section/subsection headings in \section{}/\subsection{} must be in Chinese.
- Abstract (摘要) and keywords (关键词) in Simplified Chinese.
- If the model emits hidden reasoning/thinking content, use Simplified Chinese.

## Quotation marks (**STRICT** — zh)
- Use Chinese curly quotation marks “ ” for emphasis or quoting in Chinese prose.
- Do NOT use ASCII straight double-quotes " " for Chinese text.
- For English technical terms that require quoting, use \textit{} for italics instead of any quotation marks.

## Dash usage (**STRICT** — zh)
- 不要使用破折号（——、—）表达转折、补充说明或强调。
- 优先使用逗号、分号、冒号、括号，或拆成两个句子来表达解释、递进和转折关系。
- 避免连续多段或多句反复出现破折号；除专有名词或原文题名不可改写外，不使用破折号。

## Citation format (STRICT) 
- You MUST use \cite{key} inline; the bibliography backend handles rendering.
- FORBIDDEN: "Fehr and Schmidt (1999)", "Rabin 在 1993 年提出", or any other inline author-year string. 
- Use ONLY the \cite{} keys listed in the section citation map.
- Do NOT hand-write bibliography entries, footnotes, numbered references, or author-year citation strings.
- 摘要 must NOT contain \cite{} citations.
```

## Step 6 — Prepare concrete source material

Before writing, assemble concrete source material from the loaded files. Use
resolved values from the constraints, outline, and papers library; the final
`mainbody.tex` must not contain unresolved section names, missing citation-key
markers, or placeholder text.

Create a numbered section block that lists all sections. Each entry must use
actual values from `outline.json` and include the LaTeX section heading,
description, ordered subsection titles or `(none)`, core claim, length target,
and section type.

Create the compact paper context from Step 4: one global paper index, one
section citation map, and one deduplicated key-paper evidence snippet block.

Extract focus points, extra requirements, and venue style notes from
`writing_constraints.json`; use their concrete values while writing.

## Step 7 — Write

**A complete mainbody.tex is always required.** Never output a placeholder or partial document.

Write the complete survey body as a single unified LaTeX document in one pass;
do not treat sections as independent units. Use the resolved section, paper,
and constraint information above, but output only the final LaTeX body.

### Mainbody boundary (STRICT)

`mainbody.tex` is not a standalone LaTeX document. It is a body fragment that
the export script assembles into final deliverables.

The export script will add:
- `\documentclass{...}`
- citation packages such as `natbib` / `apacite`
- `\bibliographystyle{...}`
- `\begin{document}` and `\end{document}`
- `\bibliography{references}` when `references.bib` exists

Therefore, `mainbody.tex` MUST NOT include any of these:
- `\documentclass`
- `\usepackage`
- `\begin{document}` or `\end{document}`
- `\bibliographystyle{...}`
- `\bibliography{...}`
- `\begin{thebibliography}` or `\end{thebibliography}`
- `\bibitem`
- a manually written References / Bibliography / 参考文献 section
- raw BibTeX entries or formatted reference-list entries
- any TikZ or PGFPlots content (`\begin{tikzpicture}`, `\begin{axis}`, `\usetikzlibrary`, etc.) — figures are generated externally via the agent's `image_gen` tool only

Use only inline `\cite{key}` citations. The bibliography backend resolves those
keys from `references.bib` during final export.

Follow these requirements:

1. Output exactly these elements, in this order:
   - `\begin{abstract}...\end{abstract}` (zh: 摘要, 150–250 words; en:
     Abstract, 150–250 words; no `\cite{}` citations; no `\autoref{}` or
     `\ref{}` to figures or tables — abstracts must not reference floats)
   - `\keywords{...}` (zh: 5–8 关键词, semicolons `；` as separators; en:
     5–8 Keywords, commas as separators, title case)
   - `\maketitle`
   - `\newpage`
   - `\tableofcontents`
   - `\newpage`
   - every `\section{}` from the section block, in the listed order
2. Do not output document wrappers, package declarations, bibliography commands,
   bibliography environments, `\bibitem` entries, reference-list sections,
   or markdown fences. Output only the body fragment starting with
   `\begin{abstract}` and ending after the final survey section.
   **Exception:** `% FIGURE id=xxx prompt="..."` annotation comments are allowed
   and required when figures are planned (see item 9 below).
3. Use the resolved survey title and core topic values from the loaded inputs.
4. Follow the selected language and citation rules from Step 5.
5. Write every section from the numbered section block prepared in Step 6, in
   the listed order.
6. Use only the `\cite{}` keys allowed for the current section by the section
   citation map prepared in Step 4; do not invent citation keys.
7. Follow these writing requirements:
   - **One-pass narrative:** plan the full arc before writing. Each section has a distinct argumentative role from its core_claim; no concept should be explained in more than one section.
   - **Coverage:** address every focus point and extra requirement. Do not collapse specific mechanisms, methods, or datasets into broader labels.
   - **Synthesis:** compare mechanisms, boundary conditions, and trade-offs across papers. Group by theme or argument rather than listing one paper per sentence.
   - **Evidence hierarchy:** distinguish review-level consensus, primary studies, theoretical work, and experimental evidence. Do not let a review citation carry a specific quantitative claim.
   - **No outline metadata leakage:** The `Evidence source` / `证据来源` tags at the end of `outline.json` descriptions are internal writing cues only. They must not appear in `mainbody.tex` body text, abstract, headings, tables, captions, or figure prompts. When evidence hierarchy matters, express it as natural academic prose, e.g. "primary experimental studies show..." or "review-level consensus suggests...", with appropriate citations.
   - **Quantitative claims:** name the metric, condition, direction of change, and citation. Compare conflicting values or explain discrepancy sources.
   - **Hedged language:** use "suggests", "indicates", "evidence is mixed" for uncertain claims.
   - **Citation policy:** every non-synthesis, non-common-knowledge statement requires `\cite{}`. Structural sentences about the review's own organization do not.
   - **Academic register:** no promotional language, no AI-style filler transitions or meta-commentary ("综上所述", "本节介绍了", "In summary, this section has shown…"). Every sentence carries information.
   - **Dash discipline:** do not use em dashes, including LaTeX `--` or `---`, or Chinese破折号—— in prose. Rewrite emphasis, apposition, and loose transitions with punctuation or sentence structure instead.
   - **Abstract:** write it to faithfully summarize the body actually written, not a generic topic description. No `\cite{}` in abstract. No `\autoref{}` or `\ref{}` to figures or tables — the abstract must never reference a float. Do NOT claim a specific number of papers analyzed (e.g., "基于160篇文献" or "based on xxx papers") — the abstract is written before citations are finalized, and the library count may differ from the actual cited count. Use qualitative descriptions instead.
   - **Keywords:** reflect the actual scope of the body. zh: semicolons `；` as separators. en: commas, title case.
   - **Length:** each section must meet its length target — expand through deeper coverage, not padding.
   - **Introduction:** state the review aim and paper corpus basis; do not invent search statistics.
   - **Conclusion:** synthesis of main claims → acknowledged limitations → concrete future directions from identified gaps. No `\cite{}`.
8. Follow the concrete focus points, extra requirements, and venue style notes
   from `writing_constraints.json`.
9. **Table rule** (apply when `expected_tables_total > 0`): insert tables
   according to the `planned_tables` list in each section's outline entry.
   For each entry in `planned_tables`, write exactly one complete table
   environment at a natural position in the section.
   - Use the `type` from `planned_tables` directly (do not re-select). Load
     `surveymaster-table-types` to build the column structure using that
     type's template, filled with content from the section's `core_claim`.
     Valid types: `performance_comparison`, `classification_comparison`,
     `challenge_strategy_matrix`.
   - For generic non-economics tables, use only `\toprule`, `\midrule`,
     `\bottomrule` — no `\hline`.
   - For economics empirical-style surveys, use the Economics Journal Table
     Style from `surveymaster-table-types`: heavy top and bottom rules, thinner
     internal horizontal rules, vertical column separators, compact
     black-and-white layout, and optional table notes. This economics override
     supersedes the generic booktabs-only rule.
   - No `\multicolumn` or `\multirow`.
   - Label format: `tab:<snake_case_id>`. The surrounding prose must contain
     at least one `\autoref{tab:<id>}` reference.
   - **ID consistency (STRICT):** the `<id>` in `\label{tab:<id>}` and
     `\autoref{tab:<id>}` must be identical. Assign the id once and copy it
     exactly — any variation causes a broken cross-reference in all export formats.
   - **Integrated table discussion (STRICT):** do not create a standalone one-sentence paragraph whose only purpose is to introduce the table.

     The `\autoref{...}` reference should be integrated into an analytical paragraph that interprets the table content rather than merely announcing its existence.

     The paragraph containing `\autoref{...}` should explain:

     1. what information the table summarizes;
     2. the most important patterns, similarities, differences, or trends;
     3. the conclusion or insight that supports the current section's argument.

     Do not assume readers will interpret the table themselves. The surrounding prose should guide readers toward the key takeaway.

     Poor pattern:\autoref{tab:xxx}汇总了不同MXene材料的性能指标。`

     Preferred pattern:`不同MXene材料在导电率、比容量和循环稳定性方面表现出明显差异。如\autoref{tab:xxx}所示，Ti基MXene通常具有较高的电导率和成熟的制备工艺，而Nb基和Mo基MXene则在特定储能场景中展现出独特优势。这表明材料组成和表面终端基团对其最终性能具有重要影响。`

     For performance_comparison tables, focus on the relative strengths and weaknesses of different methods rather than repeating every value in the table.

     For classification_comparison tables, focus on conceptual differences and applicability.

     For challenge-strategy matrices, focus on the relationship between challenges, current solutions, and future research opportunities.

   - **Do not restate the table row-by-row:** avoid describing every row or every cell in prose. Instead, summarize the most important patterns, contrasts, and conclusions that emerge from the table.

   - **Caption format:** write a short noun phrase only (zh: `不同方法性能对比`；
     en: `Performance comparison of different methods`). Do NOT include the label
     number in the caption text — LaTeX inserts it automatically. Do not write
     complete sentences or detailed explanations in captions.
   - **In-text reference format (STRICT):**
     - Use `\autoref{tab:<id>}` as the complete table reference. Do not write
       `表`, `表格`, `Table`, or `table` before it. `\autoref{}` renders as
       “表 1” or “Table 1”; a hand-written prefix produces duplicated text such
       as “表 表 1” or “Table Table 1” in exports.
     - zh valid: `如\autoref{tab:id}所示，`、`\autoref{tab:id}汇总了……`、`……（见\autoref{tab:id}）`
     - en valid: `As shown in \autoref{tab:id},`、`\autoref{tab:id} summarizes ...`、`... (see \autoref{tab:id}).`
     - FORBIDDEN (zh): 下表、上表、如下表所示、表 \autoref{tab:id}、表格 \autoref{tab:id}
     - FORBIDDEN (en): the table below, the above table, as shown in the following table, Table \autoref{tab:id}

   ```latex
   \begin{table}[H]
     \centering
     \caption{<caption>\label{tab:<id>}}
     \begin{tabular}{<col-spec>}
       \toprule
       <header row> \\
       \midrule
       <data rows, \cite{} where applicable> \\
       \bottomrule
     \end{tabular}
   \end{table}
   ```

10. **Figure rule** (apply when `expected_figures_total > 0`): insert figures
    according to the `planned_figures` list in each section's outline entry.
    For each entry in `planned_figures`, write exactly one `\begin{figure}`
    environment **without** `\includegraphics`, preceded on the immediately
    preceding line by a `% FIGURE` annotation comment.
    - `id` must be unique across the entire document; format: `fig_<snake_case>`.
    - **ID consistency (STRICT):** one figure uses exactly one `id` string. That
      same string must appear in all five places without any variation:
      1. `% FIGURE id=<id> prompt="..."` — the annotation comment
      2. `\label{fig:<id>}` — inside `\caption{}`
      3. `\autoref{fig:<id>}` — in the surrounding prose
      4. `figures/<id>.png` — the local image file written by the `image_gen` call
      Any mismatch (e.g. `fig_mxene_structure` vs `fig_mxene_struct`) causes the
      export script to fail. Assign the id once, copy it exactly.
    - Label format: `fig:<snake_case>`. The surrounding prose must contain
      at least one `\autoref{fig:<id>}` reference.
    - Use the `type` from `planned_figures` directly (do not re-select). Load
      `surveymaster-figure-types` to build the prompt using that type's template,
      filled with content from the section's `core_claim`.
    - Read `figure_color_policy` from `writing_constraints.json` before writing
      any `% FIGURE` prompt. If it is `black_and_grayscale`, append the
      economics/grayscale override from `surveymaster-figure-types` to every
      prompt: plain black-and-white line diagram, white background, black/gray
      boxes and arrows, no gradients, no saturated colors, no decorative icons,
      no 3D effects, no shadows, and no pictorial ornamentation. If it is
      `low_saturation_color` or missing, use the normal low-saturation academic
      color palette. Do not infer grayscale from the economics template,
      economics-related keywords, or files that happen to be present in context.
    - **Figure language:** use the **English** prompt template by default.
      Switch to the zh template only if the user has explicitly requested
      Chinese figure labels in the current session.
    - **Integrated discussion (STRICT):** do not create a standalone one-sentence paragraph whose only purpose is to
introduce the figure/table.
      The `\autoref{...}` reference should preferably be integrated into an existing substantive paragraph that discusses the same concept, method, result, or comparison.
      The surrounding prose must contain at least one `\autoref{fig:<id>}` reference.

      The paragraph containing `\autoref{...}` must do more than name the figure/table. It should explain:
      1. what the figure/table shows;
      2. which key pattern, structure, process, or comparison the reader should notice;
      3. how it supports the current section's argument.

      Poor pattern:
      `\autoref{fig:xxx}展示了MXene的典型合成流程。`

      Preferred pattern:
      `MXene通常由MAX相经过选择性刻蚀、洗涤和剥离等步骤制备得到。如\autoref{fig:xxx}所示，该过程的关键在于去除A层元素并逐步形成多层MXene和单层纳米片结构，这也解释了刻蚀条件和剥离方式为何会显著影响材料的层数、表面终端基团和后续性能。`

    - **Caption format:** write a short noun phrase only (zh: `MXene典型合成流程`；
      en: `Typical synthesis process of MXene`). Do NOT include the label number
      in the caption text. Do not write complete sentences or detailed explanations.
    - **In-text reference format (STRICT):**
      - Use `\autoref{fig:<id>}` as the complete figure reference. Do not write
        `图`, `Figure`, or `figure` before it. `\autoref{}` renders as “图 1”
        or “Figure 1”; a hand-written prefix produces duplicated text such as
        “图 图 1” or “Figure Figure 1” in exports.
      - zh valid: `如\autoref{fig:id}所示，`、`\autoref{fig:id}展示了……`、`……（\autoref{fig:id}）`
      - en valid: `As shown in \autoref{fig:id},`、`\autoref{fig:id} illustrates ...`、`... (\autoref{fig:id}).`
      - FORBIDDEN (zh): 下图、上图、如下图所示、图 \autoref{fig:id}
      - FORBIDDEN (en): the figure below, the above figure, as shown in the following figure, Figure \autoref{fig:id}

11. **Figure and table placement rules (STRICT):**
    1. **Section ownership:** every figure and table belongs to exactly one section.
       Place the environment within the `\section{}` that introduces and discusses it.
       Never place a figure or table inside a subsequent section or subsection.
    2. **Proximity:** place the environment as close as possible to the paragraph
       that first references it. Preferred placement order:
       - after the referencing paragraph (same page)
       - later in the same section (same page)
       - at the end of the current section
       - on the next page, before the next section begins
       Do not defer all figures/tables to the end of a section. The export script
       enforces a `\FloatBarrier` before every `\section{}`, so any pending float
       is flushed before the next section heading — the section heading is delayed,
       not the figure.
    3. **Reference-first (STRICT):** place the environment immediately after the
       paragraph that contains the first `\autoref{}` reference. Do not defer the
       float to the end of a subsection or the end of the section when the first
       reference appears earlier in the section. Even if the section has multiple
       subsections, the figure must follow its first `\autoref{}` — it must not
       trail after the final subsection simply to batch all floats together.
       Placing slightly before the reference is acceptable only when the surrounding
       text explains the figure shortly afterward — **but only within the same
       section body, never before the `\section{}` heading that owns the figure.**
    4. **No consecutive floats:** do not place two figure or table environments
       back-to-back without at least one paragraph of body text between them.
    5. **Single-paragraph section:** append the float at the end of that paragraph.
    6. **Never before the owning `\section{}` heading:** a float must appear
       *after* the `\section{}` heading of the section that owns it and no earlier
       than the second paragraph of that section. Placing a float before its
       owning `\section{}` heading (even one line before) is a hard violation —
       it is not overridden by rule 3.

       **Common violation to avoid:** if a figure belongs to the introduction
       (`\section{引言}` / `\section{Introduction}`) and its first `\autoref{}`
       appears in the introduction body, the `% FIGURE` block must be placed
       inside the introduction body — not immediately before the
       `\section{引言}` heading. Placing it before the `\section{}` line
       silently moves the figure above the section title in the compiled PDF.

       Bad pattern:
       ```latex
       % FIGURE id=fig_overview prompt="..."
       \begin{figure}[H]...
       \end{figure}
       \section{引言}
       ```

       Required pattern:
       ```latex
       \section{引言}
       <first paragraph of introduction>
       % FIGURE id=fig_overview prompt="..."
       \begin{figure}[H]...
       \end{figure}
       <next paragraph or subsection>
       ```
    7. **No document-level overview figure (STRICT):** do not place any figure
       between `\tableofcontents` and the first `\section{}` heading, regardless
       of figure type, `figure_type` value, or academic convention. There is no
       such thing as a "whole-survey architecture figure" in this system. Every
       figure belongs to a specific section and must appear inside that section's
       body. Any generalised knowledge about journal overview figures or
       schematic summaries placed before the introduction does NOT apply here
       and must be ignored.
    8. **Conflict priority order** (when constraints clash):
       - Section ownership first — never let a float drift into the next section.
       - Proximity second — minimize distance between discussion and float.
       - Reading continuity third — do not interrupt a paragraph mid-sentence.
       - Page utilization fourth — moderate whitespace is acceptable.
       - Whitespace minimization last — do not sacrifice section ownership to
         reduce blank space.

    ```latex
    % FIGURE id=fig_<id> prompt="<generated prompt>"
    \begin{figure}[H]
      \centering
      \caption{<caption>\label{fig:<id>}}
    \end{figure}
    ```

    **Prompt quoting constraint (STRICT):** the `prompt="..."` value is parsed
    by a regex that treats `"` as the closing delimiter. Do NOT use straight
    double-quote characters `"` inside the prompt string. Use single quotes `'`
    for any quoted term inside the prompt (e.g. `prompt="show 'key component'
    structure"`). Escaped quotes `\"` are technically supported but discouraged.

For `--mode rewrite`, also use the existing body as source material:

1. Load the complete current `mainbody.tex` content from `<output-dir>/mainbody.tex`.
2. Rewrite that content using these rules:
   - Preserve all `\section{}` titles verbatim and the existing subsection structure.
   - Do not introduce `\cite{}` keys absent from the papers block above.
   - Rewrite prose, improve evidence synthesis, fix hedging, and address any noted issues.
   - Output the complete document starting from `\begin{abstract}`.

Do not summarize or excerpt the existing body in rewrite mode; rewrite against
the complete loaded file content.

## Step 8 — Write and generate figures (single LLM response)

In **one response**, issue the following tool calls simultaneously:

1. `Write` → `$WORK/.cache/scratch/mainbody.tex` with the full LaTeX output from Step 7.
2. For each `% FIGURE id=<id> prompt="<prompt>"` line in the written text
   (skip if `expected_figures_total == 0`): call the agent's `image_gen` tool
   with that prompt, saving the result to `$WORK/figures/<id>.png`.

All tool calls in this step are issued together — do not wait for `Write` or any
`image_gen` call to complete before issuing the others.

If any `image_gen` call fails: stop
after all calls resolve, report which `id` failed and the error, and do not
proceed to Step 9.

## Step 9 — Validate and promote

Run repair + validation, then promote to final location on success:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" repair-structure \
  --mainbody "$WORK/.cache/scratch/mainbody.tex" \
  --lang "$SURVEY_LANG" \
  --outline "$OUTLINE" \
  --report "$WORK/.cache/write_section_structure.txt" && \
cp "$WORK/.cache/scratch/mainbody.tex" "$WORK/mainbody.tex" && \
rm -f "$WORK/.cache/scratch/mainbody.tex"
```

`repair-structure` is the only promotion gate for `mainbody.tex`. It may apply
deterministic fixes, including closing a single unclosed `\begin{abstract}` when
the next boundary (`\keywords{}`, `\maketitle`, `\tableofcontents`, or
`\section{}`) is unambiguous. If it still reports `MISSING_ABSTRACT`,
`ABSTRACT_NOT_CLOSED`, or `BEGIN_END_MISMATCH`, do not copy the scratch file to
`$WORK/mainbody.tex`, do not proceed to finalize/export, and do not attempt to
hand-edit only the report. Regenerate the complete body from Step 8 or repair
the scratch TeX until this command exits successfully.

If the `&&` chain fails at `repair-structure`, keep the scratch file, read
`$WORK/.cache/write_section_structure.txt`, report the exact failing items, and stop.
On copy failure, leave scratch file in place for inspection.

## Step 10 — Report

Run the figures-tables check to detect count mismatches and unreferenced floats:

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" figures-tables \
  --mainbody "$WORK/mainbody.tex" \
  --outline "$OUTLINE" \
  --report "$WORK/.cache/figures_tables_check.txt"
```

Read `$WORK/.cache/figures_tables_check.txt`. If the command exits non-zero,
stop immediately: keep `mainbody.tex`, report the exact `ERROR_MISSING`,
`UNREFERENCED_FIGURE`, or `UNREFERENCED_TABLE` lines, and repair the relevant
section before finalization/export. Do not downgrade these issues to warnings;
missing `\autoref{}` references make downstream exports miscount figures/tables.

Report:
- mode (`draft` / `rewrite`)
- total paper count used across all sections
- section count
- table count (actual `\begin{table}` in mainbody.tex) vs `expected_tables_total`
- figure count (actual `% FIGURE` annotations) vs `expected_figures_total`, and generation status
- unreferenced figures/tables found in figures-tables check (if any)
- output files: `mainbody.tex`, `figures/` (if applicable)
- warnings for non-fatal conditions (missing `papers.json`, translated `[]` paper assignments)

After delivering the report, call the platform's `FinalAnswer` tool with
`status: "completed"` to correctly terminate this turn. Do not omit this call —
without it the agent may loop or fail to hand control back to the user.
