---
name: general-writer
description: Write, revise, structure, or audit evidence-grounded academic papers across disciplines from supplied literature, data, analyses, methods, figures, notes, or existing drafts. Use for 通用论文写作, 学术论文写作, journal or conference manuscripts, theses, review papers, theoretical or methods papers, interdisciplinary studies, Results/Discussion drafting, citation and figure organization, auditable LaTeX production, and verified DOCX export. Route computer-science, bioinformatics, and empirical-economics work through discipline-aware quality gates. Do not fabricate evidence, citations, analyses, novelty, or causal claims.
---

# General Academic Writer

Turn supplied research materials into a defensible manuscript. Treat source artifacts, not a plausible narrative, as the authority.

Use this spine for a full paper:

```text
scope and study type
-> source inventory
-> claim-evidence map
-> manuscript plan and approval
-> evidence-first drafting
-> tables, figures, citations, and cross-references
-> manuscript audit
-> canonical LaTeX
-> verified DOCX when requested
```

For a local request such as revising an abstract or Results section, execute only the relevant stages while preserving the same evidence rules.

## Boundaries

- Start from a user-supplied topic, study, corpus, method, analysis, or draft. Do not silently broaden the research question.
- Do not invent data, sample sizes, metrics, coefficients, p-values, effect sizes, quotations, citations, findings, proofs, mechanisms, or contribution claims.
- Do not perform, rerun, tune, or extend analyses unless the user explicitly includes analysis in scope.
- Distinguish observed results, source-supported context, interpretation, and speculation.
- Use causal language only when the design and identification assumptions support it.
- Preserve negative, null, mixed, failed, and contradictory findings.
- Keep user-provided raw data and source artifacts read-only; write derived artifacts in the working directory.
- Record unresolved evidence gaps as blockers, limitations, or visible draft markers. Never fill them with plausible defaults.

## Route The Request

Classify the request before drafting:

1. **Full manuscript**: require adequate literature plus study-type-appropriate primary evidence.
2. **Partial manuscript work**: require the sources needed for the requested section and deliver a scoped evidence map.
3. **Review or synthesis**: require a defined corpus or authorized literature-search scope; do not imply original empirical findings.
4. **Analysis plus writing**: separate analysis planning/approval from manuscript planning/approval. Do not let approval of one substitute for the other.
5. **Formatting or export only**: preserve scientific content and run citation, reference, media, and structural checks.

Select a `study_type` from:

```text
experimental | computational | observational | empirical | qualitative
mixed_methods | review | theoretical | methods | case_study
```

Read [domain-profiles.md](references/domain-profiles.md) after classification. Apply one primary profile and any explicit secondary profiles. Use the generic profile when no discipline-specific profile fits. If a specialized local skill is available and the request clearly needs its analysis machinery, use it alongside this skill rather than copying its domain-specific assumptions into a different field.

## Conditional References

- Read [evidence-and-claims.md](references/evidence-and-claims.md) before inventorying inputs or creating `claim_evidence_map.json`.
- Read [paper-architecture.md](references/paper-architecture.md) before outlining, drafting, revising, or reviewing prose.
- Read [results-tables-figures.md](references/results-tables-figures.md) before writing Results/Discussion or creating, formatting, interpreting, or checking a table or figure.
- Read [citations-formatting-export.md](references/citations-formatting-export.md) before handling citations, BibTeX, venue formatting, LaTeX, cross-references, or DOCX.
- Read [output-audit.md](references/output-audit.md) before delivery and run the bundled evidence, approval, and manuscript validators for a full LaTeX manuscript.

## Required Workflow

### Stage 1. Inventory Inputs And Constraints

Locate and inspect:

- the research goal, question, hypotheses, method, protocol, model, or existing outline;
- the literature corpus and canonical citation records;
- study-type-appropriate evidence such as datasets, result tables, logs, transcripts, field notes, proofs, simulations, figures, or an existing results draft;
- the venue template, author guidelines, language, article type, word/page limit, anonymity, citation style, and requested output format.

For a full empirical, experimental, computational, observational, qualitative, mixed-methods, methods, or case-study paper, require both literature and primary study evidence. For a review, require a bounded literature corpus and review method. For a theoretical paper, require definitions, assumptions, derivations or proofs, and the literature positioning the contribution. If required evidence is absent, stop full-paper drafting and offer a clearly scoped plan, outline, or partial section instead.

Create:

- `source_inventory.md`: path, type, role, scope, version, status, limitations, and one stable BibTeX key for every citable literature source;
- `writing_constraints.json`: language, study type, discipline profiles, venue, article type, length, citation style, anonymity, LaTeX template, DOCX requirement, and unresolved decisions.

Prefer machine-readable results and primary artifacts over screenshots or prose summaries. Report source conflicts before drafting affected claims.

### Stage 2. Build And Validate The Claim-Evidence Map

Read [evidence-and-claims.md](references/evidence-and-claims.md). Create `claim_evidence_map.json` with stable research-question and claim IDs. For every claim record:

- exact source files and locators;
- evidence type and verification status;
- statistics or qualitative/theoretical support when applicable;
- allowed wording and prohibited overclaiming;
- caveats, intended section, and table/figure target.
- exact `citation_keys` for literature that supports the claim; never store pre-rendered author-year citation text.

Run:

```bash
python3 <skill_dir>/scripts/validate_claim_evidence_map.py \
  claim_evidence_map.json --project-root .
```

Resolve validation failures before planning prose. Literature may support context and interpretation; it may not replace missing primary evidence for a new empirical finding.

### Stage 3. Design And Approve The Manuscript Plan

Read [paper-architecture.md](references/paper-architecture.md). Create:

- `paper_outline.md`: section purpose, reader question, claim IDs, exact BibTeX citation keys, tables/figures, and length budget;
- `manuscript_plan.json`: study type, approved scope, section-to-claim map, planned objects, limitations, and status.

Derive contributions only from evidenced deltas: a demonstrated finding, method, theory, dataset, synthesis, design implication, or reproducibility asset. Remove claims of novelty, superiority, causality, or generality that the map cannot support.

For a full manuscript, present the complete plan and force a structured approval checkpoint before drafting:

1. Call `request_user_input` when that tool is available.
2. Otherwise call the runtime's structured `ask_user` tool when available.
3. Offer three decisions: approve the manuscript plan, request revisions, or cancel full-manuscript drafting.
4. Do not replace the tool call with an ordinary chat question when either structured tool exists.
5. If neither tool exists, ask one concise approval question directly in chat, state that this is a tool-unavailable fallback, and stop without drafting until a later user reply.

Do not infer approval from silence, continuation, a prior analysis approval, an old approval artifact, or the existence of results and figures. If the user requests revisions, set the plan status to `revised`, update it, and invoke the structured approval tool again. If the user cancels, stop the full-manuscript route and offer only explicitly requested partial work.

After explicit approval in the current conversation:

1. Set `manuscript_plan.json.status` to `approved` without changing the approved scientific scope.
2. Compute the SHA-256 of the resulting plan file.
3. Create `manuscript_approval.json` containing the exact approval response, tool/fallback method, approval scope, plan SHA-256, decision, and current-conversation flag:

```json
{
  "approval_scope": "full_manuscript_plan",
  "approval_decision": "approved",
  "approval_text": "Exact user response",
  "approval_method": "request_user_input|ask_user|direct_chat_fallback",
  "plan_sha256": "64 lowercase hexadecimal characters",
  "approved_in_current_conversation": true
}
```

Validate the receipt before Stage 4 or any full-manuscript drafting:

```bash
python3 <skill_dir>/scripts/validate_manuscript_approval.py \
  --plan manuscript_plan.json \
  --approval manuscript_approval.json
```

If the plan changes after approval, validation must fail. Mark it `revised`, call the structured approval tool again, and create a new matching receipt.

### Stage 4. Normalize Tables And Figures

Read [results-tables-figures.md](references/results-tables-figures.md). Build tables and figures from supplied or reproducibly generated evidence.

- Give every object a stable label such as `tab:main_results` or `fig:study_flow`.
- Record source files, producing scripts, transformations, units, sample sizes, uncertainty, tests, and correction methods when applicable.
- Use one scientific question or claim family per main table or figure.
- Do not add fake error bars, missing baselines, decorative quantitative plots, or unsupported conceptual mechanisms.
- Keep editable scripts and object metadata beside generated outputs.
- Make every displayed object appear in the prose and every prose reference resolve to a displayed object.

Apply the selected domain profile. In particular, preserve bioinformatics question-to-figure logic, computer-science comparison scope, and economics variable/specification/sample-flow discipline when those profiles apply.

### Stage 5. Draft In Evidence-First Order

Unless the approved plan requires another order, draft:

1. Results, Evaluation, Findings, or Analysis from verified evidence.
2. Methods, Materials, Research Design, System, or Theory from supplied artifacts.
3. Discussion, limitations, threats to validity, ethics, and reproducibility.
4. Background, literature review, or related work from verified sources.
5. Introduction and contributions after the evidence boundary is stable.
6. Abstract and title last.

Keep method, result, and interpretation distinct. Attach every numerical, comparative, causal, or novelty statement to a claim ID during drafting; keep IDs in comments or the audit trail, not polished prose. Use calibrated wording from the evidence map.

Insert citation commands while generating each paragraph, not in a later cleanup pass. For every literature-supported sentence, read its approved `citation_keys` and emit `\cite{key}` or another template-supported citation command in the same sentence. If the source metadata has no verified BibTeX key, stop and repair `references.bib`; do not substitute an author name and year. After drafting each section, scan that section for rendered forms such as `(Author, 2020)`, `（作者, 2020）`, or `Author（2020）` and replace them with key-backed commands before drafting the next section.

### Stage 6. Build The Canonical Manuscript

Read [citations-formatting-export.md](references/citations-formatting-export.md). For a full manuscript, generate:

```text
manuscript/
  mainbody.tex
  references.bib
  supplementary.tex       # when applicable
  figures/
  paper_audit.json
  manuscript.docx         # only when requested and export succeeds
  docx_export/
```

Use `manuscript/mainbody.tex` as the source of truth for prose, equations, citations, labels, tables, figures, captions, and legends. Preserve a supplied venue class or template. Build citations in this order:

1. Assign each verified literature record a stable BibTeX key and write its complete metadata to `references.bib`.
2. Put those exact keys in the claim map and outline before prose generation.
3. When writing a supported sentence, emit the citation command at that point, for example `批判性思维……可训练的认知技能和倾向\cite{facione1990,kamysheva2021}。`
4. Never emit the rendered equivalent `（Facione, 1990; Kamysheva, 2021）`; CSL/citeproc, not the agent, renders names, years, punctuation, ordering, and disambiguation.
5. Never build the References section with `description`, `enumerate`, `itemize`, `thebibliography`, or `\bibitem`; let the exporter render it from `references.bib`.

Do not leave citation insertion until after the manuscript is written. If any cited record lacks verified metadata or a stable key, stop that sentence or section rather than inventing or flattening the citation. Use relative figure paths and automatic cross-references; do not hard-code object numbers.

### Stage 7. Audit Before Delivery

Read [output-audit.md](references/output-audit.md). Run:

```bash
python3 <skill_dir>/scripts/validate_claim_evidence_map.py \
  claim_evidence_map.json --project-root .

python3 <skill_dir>/scripts/audit_manuscript.py \
  --tex manuscript/mainbody.tex \
  --bib manuscript/references.bib \
  --evidence-map claim_evidence_map.json \
  --manuscript-plan manuscript_plan.json \
  --approval-receipt manuscript_approval.json \
  --project-root . \
  --report manuscript/paper_audit.json
```

Treat errors as delivery blockers. Fix the manuscript or report the exact gap. Never weaken a validator, remove inconvenient evidence, or alter citations merely to satisfy a count.

### Stage 8. Export DOCX When Requested

Load the available `tex_to_docx` skill at runtime and follow its current instructions; do not assume a developer-machine absolute path. Run its `ensure_pandoc.py` preflight before export. The preflight must select a native executable for the host architecture and may use an explicitly configured, trusted mirror only with the upstream SHA-256 check. Do not build the final paper with an ad hoc Word generator.

Require successful exporter preflight, resolved citations and cross-references, embedded media when figures are planned, native editable equations when equations exist, and valid DOCX structure. If all verified Pandoc sources or another required dependency are unavailable, deliver the audited LaTeX sources and report DOCX as blocked.

Immediately before delivering a DOCX, run `tex_to_docx.py validate-docx` with the final DOCX and canonical `mainbody.tex`, then run:

```bash
python3 <skill_dir>/scripts/validate_docx_citation_links.py \
  --tex manuscript/mainbody.tex \
  --docx manuscript/manuscript.docx \
  --report manuscript/docx_citation_links.json
```

Deliver only when both commands exit zero. This last-mile audit is mandatory even when `export` or `all` already succeeded. If the selected author-year export contains no citation hyperlinks, report DOCX as blocked; do not deliver plain citation text or silently change the requested citation style.

## Deliverables

For a full paper, deliver:

- `source_inventory.md`
- `writing_constraints.json`
- `claim_evidence_map.json`
- `paper_outline.md`
- `manuscript_plan.json`
- `manuscript_approval.json`
- `manuscript/mainbody.tex`
- `manuscript/references.bib`
- applicable tables, figures, scripts, metadata, and supplementary files
- `manuscript/paper_audit.json`
- `manuscript/manuscript.docx` when requested and verified

For partial work, deliver the requested section plus the relevant inventory, claims, sources, and audit status.

## Non-Negotiable Quality Gates

1. Trace every factual, numerical, comparative, causal, and novelty claim to an exact source.
2. Resolve every citation to real metadata, insert its BibTeX-key command during sentence generation, and confirm it supports the sentence; rendered author-year text and hand-written bibliographies are delivery blockers.
3. State the evaluated population, dataset, corpus, time, setting, intervention, model, or theoretical assumptions.
4. Report uncertainty, sample size, run count, statistical test, correction method, or their absence when relevant.
5. Preserve negative, null, mixed, failed, and contradictory evidence.
6. Separate observation from interpretation and association from causation.
7. Match every table/figure reference to an existing object and every object to prose discussion.
8. Keep symbols, constructs, outcomes, treatments, baselines, and units consistent throughout.
9. Include limitations, validity threats, ethics, and reproducibility proportional to the study.
10. Remove identifying content from anonymous submissions.
11. Force a structured `request_user_input` or `ask_user` approval call for a full manuscript plan, record a current-conversation SHA-matched receipt, and validate it before drafting.
12. Deliver Word only from the audited canonical source through `tex_to_docx`.
