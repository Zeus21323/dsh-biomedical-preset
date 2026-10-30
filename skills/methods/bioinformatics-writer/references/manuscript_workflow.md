# Manuscript Writing Workflow

Use this reference only for the manuscript-writing route. It applies whether
the analysis is newly run or all experimental outputs already exist.

## Required Sequence

```text
evidence audit -> Results Question Map -> Figure Blueprint -> citation-format selection
-> manuscript plan approval
-> panels/combined figures -> literature context -> manuscript -> preflight -> tex_to_docx
```

Do not omit an earlier step because result files already exist. Reuse verified
outputs; do not rerun or alter completed analyses unless the user separately
approves that work.

## Evidence Audit

Create `evidence_inventory.json` with an `evidence` array before Results Question Map generation. For
each planned claim, record its result table, figure or log, the comparison,
sample size, test, correction method, and status:

```json
{"evidence": [{
  "claim_id": "E1", "claim": "...",
  "source_files": ["results/example.csv"], "comparison": "...",
  "statistics": "...", "status": "verified"
}]}
```

Use `missing` when an expected result does not exist and `inconsistent` when
files conflict. Do not use literature to repair either status.

## Manuscript Plan Gate

After `results_question_map.json` and `figure_blueprint.json` validate, resolve
the target journal and ask citation format/export mode in a separate ask-user interaction.
This must be its own question, not one bullet inside the later manuscript PRD
approval. Prefer `request_user_input` when available. Offer:

1. the verified target-journal style as the recommended choice when available;
2. numeric superscript (for example GB/T 7714 numeric for a generic Chinese manuscript);
3. author-date;
4. bibliography compatibility for a legacy or bibliography-only manuscript
   that has a `.bib` file but does not require body citation links.

If no target journal is selected, recommend numeric superscript for a generic
Chinese biomedical manuscript and a verified journal-appropriate style for an
English manuscript. Do not silently select a default. If the ask-user tool is
unavailable, ask directly in chat and stop until the user answers.

Create `citation_preference.json` from that answer:

```json
{
  "citation_style": "gbt7714_numeric",
  "citation_mode": "numeric",
  "citation_export_mode": "strict_linked",
  "in_text_presentation": "superscript_numeric",
  "csl": "verified CSL path, identifier, or journal-resolution rule",
  "selection_source": "ask_user",
  "user_response": "用户的原始回答",
  "approved_in_current_conversation": true,
  "target_journal": "generic_biomedical"
}
```

Use exactly one export mode:

- `strict_linked`: require real body `\cite{key}` commands. For numeric mode,
  pass `--require-numbered-references` and require clickable Word REF fields.
- `bibliography_compatibility`: require a non-empty `references.bib`, allow no
  body citation commands, do not pass `--require-numbered-references`, and
  require the exporter to report `CITATION_MODE fallback_nocite_all`. Traditional
  `\bibliographystyle{...}` and `\bibliography{references}` commands may
  remain but are not required because `--bib` supplies the bibliography.

Record this field in both `citation_preference.json` and
`manuscript_outline.json`. Do not infer `strict_linked` merely because the CSL
is numeric. The user's selected export mode controls strictness.

Use `selection_source: ask_user` when the tool is available and
`selection_source: direct_chat` only for the documented fallback. Require this
dedicated confirmation even when an earlier user message appears to imply a
format; the earlier choice may be presented as the recommended option, but it
does not waive the question. Never infer this artifact from an existing DOCX,
CSL filename, old project file, or target-journal template.

Only after this citation choice exists, create both artifacts below with
`Status: pending`.

`manuscript_outline.json` must include:

```json
{
  "title": "...",
  "article_type": "original_research",
  "language": "zh|en",
  "approval_status": "pending",
  "target_journal": "...|generic_biomedical",
  "guidelines_source": "URL, local file, or generic template",
  "citation_style": "gbt7714_numeric|journal-specific style",
  "citation_mode": "numeric|author_date",
  "citation_export_mode": "strict_linked|bibliography_compatibility",
  "citation_presentation": "superscript_numeric|inline_numeric|parenthetical_author_date|journal_specific",
  "length_policy": {
    "profile": "biomedical_original_research",
    "unit": "word_equivalents",
    "enforcement": "advisory",
    "minimums": {
      "main_text": 3200,
      "abstract": 180,
      "introduction": 600,
      "methods": 800,
      "methods_subsection": 100,
      "results": 900,
      "results_subsection": 150,
      "discussion": 700,
      "conclusion": 100,
      "figure_legend": 60
    },
    "journal_override": null
  },
  "sections": [
    {
      "section_id": "results_1",
      "section_type": "results",
      "heading": "...",
      "purpose": "...",
      "minimum_word_equivalents": 150,
      "result_question_ids": ["RQ1"],
      "evidence_ids": ["E1"],
      "claims": ["..."],
      "evidence_files": ["results/example.csv"],
      "statistics": ["..."],
      "figure_ids": ["Figure 1"],
      "literature_questions": ["..."],
      "limitations": ["..."]
    }
  ]
}
```

Read `references/manuscript_length_policy.md` before allocating chapter
lengths. Every section object must include `minimum_word_equivalents`. Record
`length_policy.enforcement`, defaulting to `advisory`; use `strict` only from a
documented journal rule or an explicit user choice. Present the targets and
enforcement mode during plan approval; do not hide them in JSON.

When Methods is represented by one consolidated section object, add a
`subsections` array whose items each contain `heading` and
`minimum_word_equivalents`. The subsection allocations must add up to at least
the Methods section allocation. Administrative statements may use shorter
allocations; substantive analysis subsections may not.

`manuscript_prd.md` must state the study question, data provenance, article
type, target journal, chapter sequence, every Results claim/evidence/figure
mapping, planned literature use, out-of-scope analyses, limitations, DOCX
requirements, the separately approved citation choice, and `Status: pending`.

Present the full chapter plan to the user in this order:

1. Title, study question, data sources, and target journal.
2. Introduction and Methods scope.
3. Each Results subsection: question, claim, source tables, statistics, figure
   panels, and limitation.
4. Discussion logic: supported interpretation, conflicting evidence to check,
   limitations, and future work.
5. Conclusion, supplementary material, and DOCX deliverables.
6. Target word-equivalents for the abstract, every main section, each Methods
   and Results subsection, and the complete main text, plus whether enforcement
   is `advisory` or `strict`.

Immediately after presenting the plan, call the available ask-user tool with a
dedicated approval question. Read and follow
`references/approval_interactions.md`; use exactly:

- `批准并继续` (recommended when the displayed plan is correct);
- `需要修改`;
- `暂不批准`.

Do not require the user to type “同意” after clicking an option. If the tool is
unavailable, ask the same question directly and stop for a reply. On approval,
set both statuses to `approved`, retain the user-approved plan, and create:

```json
{
  "approval_choice": "approved",
  "approval_source": "ask_user",
  "approved_plan_sha256": "...",
  "user_approval_text": "批准并继续",
  "approved_in_current_conversation": true
}
```

Use `approval_source: direct_chat` only for the documented fallback. On
`需要修改`, set `revised`, collect and apply the requested changes, present the
new plan, and invoke ask-user again. On `暂不批准`, keep the plan pending and
stop. A material change to a section, claim, figure, citation format, or
journal requires `revised` status and a new approval. The preflight rejects a
receipt whose hash does not match the current plan or whose approval source and
choice do not prove a current-conversation approval.
The preflight also rejects a missing citation-preference receipt or a mismatch
between that receipt and the manuscript plan.

## Drafting And Export Rules

- Draft only claims marked `verified` in `evidence_inventory.json`.
- Keep every Results subsection mapped to an approved RQ and Figure Blueprint
  item. Describe uncompleted analyses only as limitations, never as results.
- Create and validate `references.bib` before writing `mainbody.tex`; inspect
  source JSON/table keys before the writing script reads them. Every citation
  key that appears in TeX must resolve in that file; placeholders block export.
- Before a writing script reads any JSON result, run
  `scripts/inspect_json_schema.py` and save `manuscript/source_schema.json`.
  Use only keys present in that snapshot; do not guess or rename result keys.
- Never write inline `thebibliography`, `\bibitem`, a manual References section,
  or formatted reference entries into `mainbody.tex`, even temporarily.
- In `strict_linked`, write real body `\cite{key}` commands from the first draft.
  In `bibliography_compatibility`, allow zero body citations and optionally keep
  traditional `\bibliographystyle{...}` / `\bibliography{references}` commands.

Use this command before generating `mainbody.tex` from JSON results:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/inspect_json_schema.py \
  --input results/analysis_results.json \
  --output manuscript/source_schema.json
```
- Use literal relative `\includegraphics{...}` paths for every approved major
  figure, with files staged under `manuscript/figures/`.
- Run `validate_manuscript_preflight.py` after drafting and before DOCX export.
- In advisory mode, report a short section or subsection without failing
  preflight or automatically expanding it. In strict mode, treat it as a
  failed preflight. Add text only from verified study details and evidence;
  otherwise merge, narrow, or ask the user for missing material.
- Load `tex_to_docx` and use only its `tex_to_docx.py all` or `export`
  commands. Direct `pandoc` calls are forbidden. Use `--require-media` for a
  manuscript with figures and retain `tex_to_docx.log`.
- For numeric `strict_linked` mode, pass a numeric CSL plus
  `--require-numbered-references` and verify the DOCX contains `[N]`
  bibliography labels, `_RefN` bookmarks, and superscript `REF _RefN \h`
  fields. For `bibliography_compatibility`, omit the strict flag and require
  `CITATION_MODE fallback_nocite_all`. Pass `--line-spacing 1.5` in both modes.
- A citation/reference/bibliography warning, failed preflight, non-zero export,
  missing embedded DOCX media, or mismatch between a figure plan and manuscript
  blocks delivery.
