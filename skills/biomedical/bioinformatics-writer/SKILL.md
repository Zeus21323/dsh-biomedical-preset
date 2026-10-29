---
name: bioinformatics-writer
description: "Triage and execute bioinformatics requests by first asking whether the user wants manuscript writing, data/experiment analysis, another bioinformatics service, or manuscript writing from medical-imaging, clinical/EHR, or biomedical-literature/knowledge-graph sources; for a knowledge-base route, ask again with model-recommended feasible topics before continuing through the same approval-gated analysis and manuscript workflow. Use automatically for GEO/TCGA/ArrayExpress/local omics data, CT and medical-imaging repositories, EHR and clinical datasets, biomedical literature and knowledge graphs, differential expression, enrichment, immune infiltration, prognosis models, single-cell TME studies, existing-result manuscript writing, bioinformatics result interpretation, figure organization, and verified DOCX delivery through tex_to_docx."
metadata: {"source": "upstream-biomedical-science@0.1.1", "origin": "upstream-plugin"}
---

# Bioinformatics Writer

Use this skill to route bioinformatics requests into analysis, manuscript
writing, or another user-selected outcome, with auditable results and
publication-style figures when applicable.

Core principle:

```text
service route -> optional knowledge-base topic selection -> data or result audit -> Results Question Map -> Figure Blueprint -> manuscript planning approval -> panels -> combined figures -> Results text -> Discussion -> mainbody.tex -> tex_to_docx DOCX export
```

Do not assume that every bioinformatics request requires a manuscript. Route
the request first, then plan and execute only the selected outcome.

## Stage 0. Ask User To Select The Service

On SpeedClaw, call the built-in `ask_user` tool before inspecting data,
planning analyses, or writing text. Do not print these options in chat when
that tool is present. Use this structured question:

```json
{
  "questions": [{
    "header": "服务类型",
    "question": "你这次希望进行哪类工作？",
    "allow_other": false,
    "options": [
      {"label": "生信论文写作", "description": "按证据审计、图表和论文 PRD 流程执行。"},
      {"label": "生信实验/数据分析", "description": "执行已批准的数据分析、图表和结果报告。"},
      {"label": "其他生信需求", "description": "先确认所需交付物，再只执行相关流程。"},
      {"label": "CT/医学影像知识库写作", "description": "基于开放 CT、MRI、X 光、病理或影像标注资源推荐选题并写作。"},
      {"label": "电子病历/临床数据知识库写作", "description": "基于开放或合规可申请的 EHR、ICU、FHIR 等数据源推荐选题并写作。"},
      {"label": "医学文献/知识图谱写作", "description": "基于开放论文、临床试验、药物库、本体或医学知识图谱推荐选题并写作。"}
    ]
  }]
}
```

On a non-SpeedClaw host, prefer `request_user_input` when available, then the
host's structured `ask_user` tool. Use direct chat only when neither exists.

Do not require the user to type `Use $bioinformatics-writer`. This Skill should
trigger implicitly for bioinformatics requests and then perform this routing.
Ask once per conversation unless the user later changes the selected service.

Route the answer as follows:

- **Bioinformatics manuscript writing**: use the complete workflow, including
  evidence audit, Results Question Map, Figure Blueprint, a user-approved
  manuscript plan, manuscript, and requested DOCX export. Existing results do
  not skip any writing-planning or verification gate.
- **Bioinformatics experiment/data analysis**: use the Plan, Implement, Verify,
  and Finish phases for data analysis and figures. Do not draft a manuscript or
  export DOCX unless the user later requests it.
- **Other bioinformatics request**: ask one concise follow-up question for the
  desired deliverable, then use only the relevant portions of this Skill. Do
  not force the complete manuscript workflow.
- **Any knowledge-base writing route**: run Stage 0.5 immediately. After the
  user selects a recommended topic, treat the route as Bioinformatics
  manuscript writing and continue through every normal analysis and manuscript
  approval gate. The topic selection is not analysis-PRD or manuscript-PRD
  approval.

If no structured ask-user tool exists, ask the same question directly in chat
and wait.

## Stage 0.5. Recommend And Select A Knowledge-Base Topic

Run this stage only after the user selects one of the three knowledge-base
writing routes in Stage 0. Read
`references/knowledge_base_writing_routes.md` completely before generating
topics.

Generate 4-6 distinct, feasible topic options for the selected category. Base
them on named sources from the reference, current source availability, access
conditions, and an analysis that can produce traceable local evidence. Each
option description must state the research question, primary source(s), core
method or evaluation, and access status. Do not recommend a topic that depends
on credentialed data without labeling the credential/DUA requirement. Do not
present synthetic EHR findings as real-world clinical evidence.

Immediately call `ask_user` a second time with the generated options. On
SpeedClaw, use one structured question, set a short category-specific header,
set `allow_other: true`, and do not print the menu in chat. On other hosts,
prefer `request_user_input`, then a structured `ask_user`; use direct chat only
when neither exists. The model, not the user, supplies the initial 4-6 options.

Save the exact response and every displayed option to
`knowledge_base_topic_selection.json` using the schema in the reference. If
the user enters a custom topic, normalize it to the same schema and ask only
for a missing decision that materially affects feasibility. After selection:

- set the service route to `bioinformatics_manuscript_writing`;
- select the matching knowledge-base blueprint;
- treat the named source plan as an explicit request to search public data;
- continue at Stage 1 without repeating Stage 0 or the generic data-source
  question unless the selected sources are unavailable, incompatible, or
  require credentials the user has not confirmed.

## Session-Scoped Trellis Workflow

This Skill uses a Trellis-style `Plan -> Implement -> Verify -> Finish` loop
only in the current conversation after Stage 0 routing. Read
`references/session_workflow.md` before starting.

- Do not install Trellis, run `trellis init`, or create/read a `.trellis/` directory.
- Keep workflow state in the current conversation and the explicit study artifacts.
- Scientific outputs such as result tables, figures, `analysis_prd.md`, and manuscripts remain normal project deliverables.
- Do not begin analysis until the user approves the final analysis PRD.
- Do not declare completion until verification has passed or all failures are reported.

## Required Workflow

### Stage 1. Confirm Data Input

First identify whether the user provided usable data input.

Acceptable data inputs include:

- a GEO/TCGA/ArrayExpress accession
- a local expression matrix path
- a local clinical/sample metadata path
- a prepared project folder with result tables
- an explicit instruction to search for public datasets
- a completed `knowledge_base_topic_selection.json` with named source
  candidates and `data_source_status: search_requested`

If the user has not provided a dataset, local data path, public-data search
instruction, or completed knowledge-base topic selection, stop and ask:

```text
你希望我使用哪种数据来源？
1. 你提供本地表达矩阵/临床信息文件路径
2. 你指定 GEO/TCGA 等数据集编号
3. 你让我根据研究方向搜索合适的公开数据集
```

On SpeedClaw, use `ask_user` with the three listed data-source choices as
structured options (`allow_other: false`). On other hosts, prefer
`request_user_input`, then structured `ask_user`. Ask directly in chat only
when no structured tool exists. Do not proceed until the data source is clear.
Do not ask this generic question again when Stage 0.5 already produced a viable
named source plan; record that plan as `search_requested` and verify source
access during planning instead.

Output `study_goal.json`:

```json
{
  "study_goal": "...",
  "disease": "...",
  "dataset": "...",
  "comparison": "...",
  "service_route": "bioinformatics_manuscript_writing",
  "knowledge_base_category": null,
  "selected_topic_id": null,
  "knowledge_sources": [],
  "study_type": "prognostic_signature|imaging_knowledge_base|clinical_ehr_knowledge_base|literature_knowledge_graph",
  "selected_blueprint": "prognostic_signature|imaging_knowledge_base|clinical_ehr_knowledge_base|literature_knowledge_graph",
  "secondary_blueprints": [],
  "extension_modules": [],
  "data_source_status": "provided|needs_user_input|search_requested"
}
```

After selecting or inferring the study type, always read
`references/study_type_blueprints.md` and apply its Blueprint Routing Contract.
Load only the matching blueprint as the default plan. For analyses spanning
multiple blueprints, select one primary blueprint plus explicit secondary
blueprints or extensions; never silently force them into one type. Record the
selection in `study_goal.json` and `analysis_prd.md`. User requirements and
usable data override blueprint defaults.

After the essential study facts are confirmed, begin `analysis_prd.md` with
the Goal, Data Source, Comparison Design, Study Type, and unresolved decisions.
Use it as the human-readable source of truth for the approved analysis plan.

### Stage 2. Confirm Analysis Scope

Before analysis, extract analyses already named in the user's instruction and
map them to the selected blueprint(s). Do not ask the user to repeat them. Ask
only about unresolved, material choices, using an ask-user tool when available.
If the user does not specify analyses, generate a conservative default analysis inventory based on the study type.
Then present the proposed analysis inventory to the user for review and explicitly ask for confirmation before continuing.
Do not run Stage 3 until the user confirms the analysis plan is correct.
For non-interactive environments where user confirmation is impossible, mark the workflow as blocked rather than silently continuing.

Output `analysis_inventory.json` with:

- analysis name
- source blueprint or extension module
- scope class: `primary | secondary | extension`
- whether it was explicitly requested by the user or supplied by a blueprint
- purpose
- required inputs
- expected outputs
- statistical method
- figure panels likely supported

Also update `analysis_prd.md` with the complete analysis inventory, expected
deliverables, acceptance criteria, out-of-scope work, risks, and scientific
limitations. Keep `analysis_inventory.json` consistent with the PRD and set
the PRD status to `pending` until the user approves the final planning summary.
Before asking for approval, present the final planning summary with Goal, Data,
In Scope, Out of Scope, Analysis Inventory, Acceptance Criteria, Risks, and
the paths of the planning artifacts. Read
`references/approval_interactions.md` and apply its analysis-gate contract.
Immediately after that summary, call the
available ask-user tool as a dedicated approval interaction. Prefer
`request_user_input` and ask whether to `批准并继续`, `需要修改`, or `暂不批准`;
do not require the user to type a separate approval sentence. If the tool is
unavailable, ask the same approval question directly and wait.

On `批准并继续`, do not hand-write `analysis_approval.json`, guess its keys, or
compute hashes manually. Run the deterministic receipt creator below with the
exact returned answer. It validates the inventory, normalizes common Markdown
status forms to an approved state, computes hashes only after the final PRD is
on disk, writes the schema-conformant receipt atomically, and runs the approval
validator. Only then begin Stage 3. On
`需要修改`, keep or set the PRD to `revised`, collect the requested change,
present the revised summary, and invoke the approval interaction again. On
`暂不批准`, keep the PRD pending and stop. If the plan changes materially,
mark the PRD as `revised` and obtain approval again.

Before Stage 3, require this command to succeed:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/create_analysis_approval.py \
  --project-root . \
  --analysis-prd analysis_prd.md \
  --analysis-inventory analysis_inventory.json \
  --approval-receipt analysis_approval.json \
  --approval-source ask_user \
  --user-approval-text "批准并继续"
```

Substitute the exact tool response for `--user-approval-text`; use
`--approval-source direct_chat` only when no structured ask-user tool exists.
Do not edit the approved PRD or inventory afterward. If either changes,
invalidate the receipt, return the PRD to `revised`, obtain approval again, and
rerun the creator. Read `references/approval_interactions.md` for the canonical
receipt contract. Use `scripts/validate_analysis_approval.py` only to recheck an
existing receipt without rewriting it.

### Stage 3. Run Or Collect Real Analysis Outputs

Run analysis only after Stage 1 and Stage 2 are complete. Before any data
download, R/Python environment probe, dependency installation, or backend
decision, build and validate a **complete per-module OmicVerse MCP routing
table**. This is mandatory for every new PRD, regardless of blueprint, data
modality, or user wording. It replaces all shortcut reasoning such as “this is
bulk, so OmicVerse is not applicable.”

1. Read `references/omicverse_mcp_backend.md` and
   `references/omicverse_mcp_capability_map.md`.
2. For *every* item in the approved `analysis_inventory.json`, search the
   registered live catalog using `ov.search_tools` and inspect candidates with
   `ov.describe_tool`. If no runtime is registered, classify every item against
   the capability map first; if one or more plausible candidates exist, run the
   explicit installation interaction and then repeat live discovery.
3. Write `environment/omicverse_mcp_routing.json` with one `module_routes`
   record for every inventory item. Each record must include `analysis_name`,
   `discovery` (`live_catalog` or `capability_map`), `decision`
   (`omicverse_mcp`, `fallback`, `not_mcp_candidate`, or `blocked`), a concrete
   `reason`, and either `tool_name` for MCP or `actual_backend` for fallback.
4. Run this validator. A non-zero result blocks Stage 3; do not start an
   environment probe merely because the routing table has not been made:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_omicverse_routing.py \
  --inventory analysis_inventory.json \
  --routing environment/omicverse_mcp_routing.json
```

Use MCP for a module only when a suitable registered tool supports that
module's approved method, inputs, and dependencies. A suitable MCP tool takes
priority over R or Python for that module. Do not infer a tool from a similarly
named OmicVerse Python-library function.

**Do not use data modality as a shortcut to skip this check.** In particular,
bulk microarray or bulk RNA-seq is not a reason to say "OmicVerse MCP is not
applicable". If the approved inventory includes `PCA` / `principal component
analysis` or `differential expression` / `DEG`, it contains a current MCP
candidate (`ov.pp.pca` or the P2 `pyDEG` tool respectively). Before any R/Python
environment probe, data download, dependency installation, or backend decision,
the agent must either: (a) search the registered MCP catalog for those tools, or
(b) if no local runtime is registered, invoke the explicit OmicVerse
installation `ask_user` interaction. It may fall back only after the resulting
per-module discovery shows that a tool, input, dependency, or approved method
does not match. The unsupported immune-deconvolution modules in the same plan
do not cancel this required check for PCA and DEG.

If OmicVerse MCP is not registered, offer its explicit installation interaction
only when the approved inventory contains a plausible OmicVerse MCP candidate.
Do not ask to install it, block execution, or route through it for modules
outside the server's known scope. After installation and discovery, make the
same per-module live-catalog decision. For every module that falls back, record
the exact reason (`no_matching_mcp_tool`, `unsupported_input`,
`dependency_unavailable`, or `approved_method_mismatch`) in
`environment/backend_decision.json` before selecting R or Python.

A missing, failed, or unsuitable MCP tool affects only the module being routed.
It must never reject, cancel, or prevent execution of the other approved
modules in the same analysis plan. Continue those modules through their own
MCP-or-fallback decisions. Stop the entire Stage 3 only when the user selects
`取消本次分析`, an approved module has no scientifically valid fallback, or a
separate approval/data-validation gate fails.

For an eligible installation interaction:

1. If a suitable registered OmicVerse MCP tool is already available, write
   `environment/omicverse_mcp_status.json` with `selection:
   install_and_enable`, `status: ready`, and `selection_source: existing_runtime`.
2. Otherwise call SpeedClaw `ask_user` with its three installation choices.
   On `安装并启用`, run the bundled installer, call `install_mcp` with the
   generated descriptor, then use `find_tools` to confirm a relevant OmicVerse
   tool. Write `status: ready` on success or `status: failed` on failure.
   On `不安装，使用现有后端`, write `selection: use_existing_backend`,
   `status: declined`. On `取消本次分析`, write `selection: cancel` and stop.
3. Run this validator for the installation choice. A `failed` result records an
   MCP installation/runtime failure and permits module-level fallback; only a
   cancellation result stops the analysis:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_omicverse_mcp_gate.py \
  --status environment/omicverse_mcp_status.json
```

After completing any eligible interaction, read `references/backend_policy.md`,
derive required R packages only for modules not assigned to OmicVerse MCP, and run
`scripts/probe_r_environment.py`. Save the report as
`environment/r_environment.json` and create the module-level
`environment/backend_decision.json`. This read-only probe is mandatory even
when `Rscript` is not currently on `PATH`; it also checks common RStudio/system
and Conda locations. Reuse a working local R interpreter, its `.libPaths()`, and
installed packages before considering Python.

After backend routing and before any external API call, download, generated
Python analysis, or long-running command, read
`references/network_execution_policy.md` and apply it. Require explicit HTTP
timeouts, bounded retries, a total retrieval deadline, response provenance,
and bulk-query-first access. For IDC/TCIA metadata, prefer IDC MCP/SQL/REST or
`idc-index` aggregation; do not run unbounded per-collection patient queries.

When an approved source includes ClinicalTrials.gov or PubMed, also read
`references/clinicaltrials_pubmed_api.md`. Use the bundled
`scripts/clinicaltrials_v2_client.py` for ClinicalTrials.gov retrieval instead
of generating pagination and date parsing from scratch. Treat `query.cond` as a
valid API v2 parameter, never send numeric `page`, propagate
`nextPageToken` as `pageToken`, and parse completion dates from
`completionDateStruct.date` while preserving year/month/day precision. Log the
final URL and response body before attributing any HTTP 400 to a parameter.
Block the module if a non-empty response normalizes to zero records.

For every Python analysis, save `environment/python_environment.json` with
`scripts/probe_python_environment.py`, compile the script, verify all
version-sensitive attributes, and pass a bounded smoke test before the full
run. Do not use removed NumPy APIs such as `np.trapz` when
`numpy:trapezoid` is available.

Run long analyses with `scripts/run_analysis_supervised.py`; never use shell
`&`, `nohup`, or an unmanaged background process. Let the host yield and wait
on the same execution session. Do not issue repeated `ps`/`tail` commands or
narrate unchanged polls. A timeout or API failure may use only an already
approved, locally evidenced fallback. If it changes source, unit of analysis,
sample size, primary endpoint, method or expected claim, mark the PRD
`revised`, invalidate approval, and obtain approval again. Never substitute
model memory or “known database characteristics” for missing records.

Default backend policy:

- Use the most reliable tool for each analysis module, not one language for the whole study.
- An installed, usable local R package must be used for its matching R-native
  module, including `limma`, `DESeq2`, `edgeR`, `clusterProfiler`, `survival`,
  `glmnet`, `ComplexHeatmap`, and `Seurat`.
- Python is preferred for orchestration, JSON/schema handling, file conversion, image composition, validation scripts, and Python-native workflows such as `scanpy`, `pandas`, `scikit-learn`, `lifelines`, and `Pillow`.
- RStudio is not required for agent execution, but its R interpreter and user
  package libraries on the same execution host should be reused. Run the
  detected `Rscript` by absolute path.
- If a required R package is unavailable, use Python only for the affected
  module and only when the method is scientifically equivalent. Do not silently
  replace an approved R statistical model or move the whole pipeline to Python.
- If no equivalent Python method exists, report the dependency and ask whether
  to install it or revise the approved PRD.

Every Results claim must be traceable to a local file:

- CSV/TSV/RDS/JSON result tables
- generated PNG/PDF/TIFF figures
- external validation tables
- statistical test logs

Treat `environment/r_environment.json` and
`environment/backend_decision.json` as required method-provenance artifacts
whenever experimental analysis is executed. Also require
`environment/python_environment.json` for every Python analysis and
`environment/analysis_task_status.json` plus its log for every supervised
long-running command.

#### Existing-results contract

When the user supplies completed analyses and requests only manuscript writing,
do not rerun, alter, supplement, or silently replace those analyses. Still
perform this stage as an evidence audit before drafting: inspect result tables,
figure files, scripts/logs, sample counts, statistical methods, correction
methods, failed analyses, and missing outputs. Write `evidence_inventory.json`
that records each usable claim, its source file, and its status (`verified`,
`missing`, or `inconsistent`). Treat missing or inconsistent evidence as a
limitation or a blocking issue; never fill it with literature or invented data.

Do not use literature search to invent findings. Literature is used later for Introduction and Discussion.

### Stage 4. Generate Results Question Map

Convert analysis outputs into scientific Results questions.

Rule:

```text
one Results question = one Results subsection = one major Figure
```

Read `references/result_question_map.md` when generating this file.

Output `results_question_map.json`.

Validate it:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_results_question_map.py \
  results_question_map.json \
  --project-root .
```

### Stage 5. Generate Figure Blueprint

For each Results question, design one major Figure.

Rules:

- Do not group panels by chart type.
- Group panels by biological claim.
- Each panel must provide one specific piece of evidence for the figure-level claim.
- Each panel must identify its experiment slug, input table/file, statistical
  message, and experiment-scoped output path.
- Establish a Figure Contract with one core conclusion, one declared archetype,
  an evidence hierarchy, an applicable hero panel (or explicit `null` for an
  equal-rank quantitative grid), reviewer risks, final physical dimensions,
  and a non-overlapping panel-slot map.
- Select one `render_backend` (`python` or `r`) per major Figure. Analysis
  modules may have different scientific backends, but the selected figure
  backend must produce the complete layout, labels, preview, publication
  exports, and visual QA for that Figure.

Read `references/figure_logic.md` and
`references/nature_figure_integration.md` when generating figure plans.

Output `figure_blueprint.json`.

Validate it:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_figure_blueprint.py \
  figure_blueprint.json \
  --project-root .
```

### Stage 5.5. Approve The Manuscript Plan

For the manuscript-writing route, read `references/manuscript_workflow.md`.
After validating the Results Question Map and Figure Blueprint, resolve the
target journal and then ask for the citation format as a separate interaction.
Call the available ask-user tool (prefer `request_user_input`) with one
dedicated citation-format question; do not bundle it into the chapter-plan
approval. Offer the verified target-journal style as the recommended choice
when one exists, plus numeric-superscript and author-date alternatives. If no
ask-user tool is available, ask the same question directly and stop. Do not
infer or silently default the citation format.

Write the answer to `citation_preference.json`, including the exact user
response, citation style, citation mode, citation export mode
(`strict_linked` or `bibliography_compatibility`), in-text presentation, CSL
choice or resolution rule, selection source, and
`approved_in_current_conversation: true`. Then create
`manuscript_outline.json` and `manuscript_prd.md`. Present the complete
chapter-by-chapter plan and then call the available ask-user tool as a separate
approval interaction. Read `references/approval_interactions.md` and apply its
manuscript-gate contract with exactly `批准并继续`, `需要修改`, and `暂不批准`. Do not make
the user type an additional approval sentence when the tool returns an
approval. The plan must map
every Results subsection to its claim, evidence files, statistics, figure, and
limitations; it must also state the planned Introduction, Methods, Discussion,
Conclusion, literature questions, target journal, and DOCX requirements.
Read `references/manuscript_length_policy.md`; include the approved target
word-equivalents for the abstract, every main section, every substantive
Methods and Results subsection, each major figure legend, and the whole main
text. Record and present `length_policy.enforcement`; default to `advisory` and
use `strict` only for a documented journal requirement or explicit user choice.

Do not generate panels, compose figures, search literature, draft Results or
other manuscript text, create `mainbody.tex`, or export DOCX while the
manuscript PRD is `pending` or `revised`. Existing completed analyses do not
waive this gate. If the user changes the planned story, sections, figures, or
target journal, revise the manuscript PRD and obtain approval again.

Do not proceed while the approval interaction is unanswered. On
`批准并继续`, set both statuses to `approved` and write
`manuscript_approval.json` containing `approval_choice: approved`, the exact
returned answer, `approval_source: ask_user`, the current plan SHA-256, and
`approved_in_current_conversation: true`; the tool response itself is the
explicit approval. If the ask-user tool is unavailable, ask directly, stop,
and record `approval_source: direct_chat` after the reply. On `需要修改`, mark
the plan `revised`, collect changes, and re-run the approval interaction. On
`暂不批准`, leave it pending and stop. Analysis PRD approval, an old approval
file, or the mere existence of figures never counts.

### Stage 6. Prepare Panel Evidence And Complete Figure Sources

Prepare panel evidence and complete figure sources only after the validated
Figure Blueprint. For manuscript writing, also require the approved manuscript
plan; for analysis-only work, require the approved analysis PRD. Read
`references/publication_figure_guidelines.md` and
`references/nature_figure_integration.md`.

Recommended layout:

```text
figures/
  experiments/
    01_study_overview/
      panels/
        Figure1A_workflow.png
        Figure1B_sample_distribution.png
      sources/
      metadata/
    02_transcriptomic_structure/
      panels/
        Figure1C_PCA.png
      sources/
      metadata/
    03_differential_expression/
      panels/
        Figure1D_volcano.png
      sources/
      metadata/
  combined/
    sources/
```

Organize every single-result plot under the experiment that produced it. Use a
stable lowercase `experiment_slug` per analysis (for example,
`differential_expression`, `pathway_enrichment`, `immune_infiltration`, or
`survival_model`). Keep the plot's editable source script or notebook under
that experiment's `sources/` directory whenever one exists, and keep panel
metadata under `metadata/`. At minimum, save the panel PNG plus the input path,
statistical test, correction method, and plotting parameters. Do not put all
panels in one flat directory.

Each panel should have panel metadata:

```json
{
  "panel": "Figure3C",
  "experiment": "immune_infiltration",
  "input_file": "results/immune_group_tests.csv",
  "statistical_test": "Wilcoxon rank-sum test",
  "multiple_testing": "Benjamini-Hochberg FDR",
  "main_message": "...",
  "output": "figures/experiments/immune_infiltration/panels/Figure3C.png"
}
```

For each major Figure, create the one complete editable source declared by
`layout.figure_source`, for example
`figures/combined/sources/Figure3.py` or `Figure3.R`. Use the selected
`layout.render_backend` for every data plot in that Figure, its native layout
system, A/B/C labels, shared legends, preview, vector/raster exports, and visual
QA. Quantitative panels should be drawn from the traceable inputs named in the
blueprint. Raster microscopy/pathology panels may be imported as images with
their integrity metadata and linked quantification.

Do not mix Python and R graphics within one major Figure. Do not use Pillow to
assemble a new publication Figure from independent screenshots. Keep isolated
experiment-scoped panel previews only for evidence audit and tuning; the
complete figure source is the publication source of truth.

### Stage 7. Render Unified Multi-panel Figures

Only render multi-panel figures after the validated Figure Blueprint,
traceable panel inputs, and complete figure source exist. For manuscript
writing, also require the approved manuscript plan; for analysis-only work,
require the approved analysis PRD.

Hard rules:

- Create preview PNG before publication-quality outputs.
- Save images as files and report paths.
- Never print base64 image data or large SVG/XML into the conversation.
- Render the entire Figure through the one selected backend.
- Check raster input dimensions and stop if the final canvas is too large for
  safe processing.
- Preserve editable SVG/PDF text and line art; also generate TIFF and preview
  PNG from the same complete figure source.
- Inspect the SVG/PDF at final physical size and write the QA result to the
  blueprint's `qa_output` path.

Recommended outputs:

```text
figures/combined/
  sources/Figure1.py
  Figure1_preview.png
  Figure1.svg
  Figure1.pdf
  Figure1_600dpi.tiff
  Figure1_qa.json
```

Validate the plan before rendering:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_figure_blueprint.py \
  figure_blueprint.json \
  --project-root .
```

Run each `layout.figure_source` with its recorded Python or R backend. Then
require the complete bundle:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_figure_blueprint.py \
  figure_blueprint.json \
  --project-root . \
  --require-panel-outputs \
  --require-figure-source \
  --require-publication-outputs
```

`scripts/compose_multipanel_figure.py` remains only for compatibility with old
projects. Do not use it as the default renderer for a new Figure.

### Stage 8. Draft Results Text And Figure Legends

Use `results_question_map.json`, `figure_blueprint.json`, panel metadata, and result tables.
For the manuscript-writing route, also read the approved `manuscript_prd.md`
and `manuscript_outline.json`; do not add unapproved Results claims, figures,
or sections.

For the analysis-only route, produce a concise results report and figure
legends, not a full manuscript. For the manuscript-writing route, draft the
publication-style Results section.

Avoid one- or two-sentence standalone Methods or Results subsections. Use
verified study details and quantitative evidence to improve completeness. An
advisory length warning does not authorize automatic expansion; if evidence is
insufficient, merge or narrow the subsection or ask the user for material.
Never pad or invent content.

Results text should follow:

```text
question -> method in one sentence -> statistical finding -> biological interpretation -> figure citation
```

Figure legends should describe every panel, sample size, statistical test, correction method, and abbreviations.

### Stage 9. Literature Context

Use this stage for the manuscript-writing route only after the manuscript plan
is approved, or when an analysis-only user explicitly requests literature
interpretation. Search literature only after the key findings are computed.

Use literature for:

- disease background
- known gene/pathway/cell-type functions
- explanation of concordance or conflict with prior work
- Discussion and limitations

Do not use literature as the source of bioinformatics discoveries.

### Stage 10. Generate LaTeX Manuscript

Run this stage only for the manuscript-writing route or when the user later
requests a manuscript. Skip it for analysis-only work.

Require approved `manuscript_prd.md`, approved `manuscript_outline.json`, and
`evidence_inventory.json` before writing. Before any DOCX export, run:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_manuscript_preflight.py \
  --project-root . \
  --results-map results_question_map.json \
  --figure-blueprint figure_blueprint.json \
  --evidence-inventory evidence_inventory.json \
  --manuscript-plan manuscript_outline.json \
  --manuscript-prd manuscript_prd.md \
  --citation-preference citation_preference.json \
  --approval-receipt manuscript_approval.json \
  --source manuscript/mainbody.tex \
  --bib manuscript/references.bib \
  --require-approved
```

Do not export when this check reports an error. In particular, every citation
key must exist in the BibTeX file, every major figure must be embedded from a
relative path, and the manuscript may not claim results absent from the
approved evidence and figure plans.
The preflight must report the approved manuscript length policy. In advisory
mode, short sections, subsections, abstracts, and legends are warnings and do
not by themselves block DOCX delivery. In strict mode they block delivery.
Missing required sections, a missing abstract, or missing planned figure
legends remains a structural error in both modes.

Select manuscript structure by journal or article type.

The primary manuscript output must be LaTeX:

```text
manuscript/
  mainbody.tex
  references.bib
  figures/
  supplementary.tex
```

Keep publication-quality figure outputs under `figures/combined/`. Before writing the
DOCX-bound manuscript, copy each major figure's preview PNG into the self-contained
manuscript staging directory:

```text
figures/combined/Figure1_preview.png -> manuscript/figures/Figure1_preview.png
figures/combined/Figure2_preview.png -> manuscript/figures/Figure2_preview.png
```

Use `mainbody.tex` as the canonical source for the manuscript text, figure references,
tables, citations, embedded figures, and figure legends. When major figures exist and a
DOCX will be delivered, insert every major figure with a literal relative
`\includegraphics` path. A prose reference such as `Figure 1A`, a `\ref{...}`, or a
Figure Legends section does not embed an image and does not satisfy this requirement.
Use the preview PNG for DOCX portability rather than TIFF or PDF:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/Figure1_preview.png}
\caption{Figure 1. Study overview and transcriptomic differences. (A) ... (B) ...}
\label{fig:figure1}
\end{figure}
```

Keep image paths relative to `mainbody.tex`; never rewrite them as machine-specific
absolute paths. Before DOCX export, verify that every literal `\includegraphics{...}`
target exists under `manuscript/`. If major figures exist but `mainbody.tex` has no
`\includegraphics`, stop and fix the manuscript instead of exporting a text-only DOCX.
Do not make a JavaScript DOCX generator or hand-built DOCX writer for final manuscript
export.

Use the article structure and target-journal requirements approved in the
manuscript plan; read `references/writing_logic.md` for section logic.

### Stage 11. Export DOCX With tex_to_docx

Run this stage only when the user requests DOCX delivery. Skip it for
analysis-only work unless the user later expands the scope.

DOCX export is hard-bound to the existing local skill:

```text
/home/ubuntu/speedclaw_skillsurvey/tex_to_docx
```

When the user asks for DOCX export, load and invoke that skill's workflow and
script. Do not invoke `pandoc` directly, use a hand-built DOCX writer, or use
another export method unless the user explicitly overrides this requirement.

Use only the `all` or `export` command documented by the loaded
`tex_to_docx` Skill, with `--bib`, `--require-media` when figures are planned,
and `--toc` when required by the approved plan. For approved numeric
`strict_linked` mode, pass the explicit numeric CSL and
`--require-numbered-references`; this must produce numbered bibliography
entries, `_RefN` bookmarks, and clickable superscript `REF _RefN \h` fields.
For `bibliography_compatibility`, omit `--require-numbered-references`, allow a
`.bib` with no body citation commands, and require
`CITATION_MODE fallback_nocite_all`; do not demand Word REF fields.
Always pass `--line-spacing 1.5` and require the exporter to report
a `LINE_SPACING` record containing `multiplier=1.5` before accepting the DOCX;
additional fields such as `mode=global-override` may appear between them.

Before exporting, check whether `pandoc` is available. If it is missing, report that `tex_to_docx` can still extract `journal_config.json` and create `journal_template.docx`, but final DOCX export requires installing Pandoc.

Use the target journal and guidelines source recorded in the approved
manuscript PRD. If the user has not selected a journal, record a generic
biomedical template explicitly in the plan and report that the result is not
submission-ready. Capture the `tex_to_docx` output in
`manuscript/docx_export/tex_to_docx.log`. A non-zero exit, an unresolved
citation/reference/bibliography warning, missing required media, or a failed
preflight check blocks delivery. Never describe citation warnings as harmless.

After exporting a manuscript that contains `\includegraphics`, require the DOCX archive
to contain embedded files under `word/media/`. Treat a DOCX with no embedded media as a
failed export even when Pandoc exits successfully. The `tex_to_docx` script performs this
check automatically; do not bypass it by removing figure commands or switching to
absolute image paths.

## Non-negotiable Rules

1. Ask for data source when missing.
2. Ask the user to choose analyses or review the proposed default analysis inventory.
3. Do not proceed past Stage 2 without user confirmation.
4. Every Results claim must trace back to a result file.
5. A major Figure must answer a biological Results question.
6. Do not group panels merely by chart type.
7. Build every new major Figure from one complete editable source and one
   rendering backend; keep experiment panels for provenance, not screenshot
   collage composition.
8. Do not embed image binaries in chat.
9. Use literature for interpretation, not invention.
10. Draft a manuscript only for the manuscript-writing route or after an explicit later request, and only after Results Question Map, Figure Blueprint, and manuscript-plan approval exist.
11. Write manuscript source as `manuscript/mainbody.tex`.
12. Export DOCX only through `/home/ubuntu/speedclaw_skillsurvey/tex_to_docx`.
13. The current conversation must explicitly approve `analysis_prd.md` before Stage 3 begins.
14. Finish with exact deliverable paths, verification status (`pass`, `fail`, or `not run`), deviations, and limitations.
15. On first invocation, use ask-user to route the request to manuscript writing, experiment/data analysis, another bioinformatics service, or one of the three knowledge-base writing routes.
16. For each approved module, search the live OmicVerse MCP catalog first. Use MCP only when it supports that module's approved method, inputs, and dependencies; then it is the required backend for that module. Never treat the whole OmicVerse Python library as MCP-exposed.
17. Offer the one explicit OmicVerse installation interaction only when the approved inventory contains a plausible MCP candidate and no live local runtime is available. For every module without a suitable MCP tool, record the concrete mismatch before selecting R/Python; do not block unrelated modules or force them through MCP.
18. Treat approved PCA and DEG as explicit OmicVerse MCP candidates even for bulk microarray or bulk RNA-seq. Never declare MCP inapplicable merely because the study is bulk; first run catalog discovery or the installation ask-user interaction, then make the module-level compatibility decision.
19. Always select, record, and load the applicable blueprint before creating the analysis inventory; every inventory item must identify its blueprint or extension-module source.
20. For manuscript writing, the current conversation must explicitly approve `manuscript_prd.md` and `manuscript_outline.json` before Stage 6 or later begins, even when all experiments are already complete.
21. Use only `tex_to_docx` for DOCX delivery. A direct Pandoc invocation, unresolved citation/reference warning, failed preflight check, or missing embedded media is a failed export.
22. Never accept analysis PRD approval as manuscript approval. Require a matching current-plan SHA-256 in `manuscript_approval.json`; require numbered Word reference fields only for approved numeric `strict_linked` mode, not for `bibliography_compatibility`.
23. Require an approved manuscript length policy with explicit enforcement.
    Default to advisory warnings; use strict blocking only for a documented
    journal rule or explicit user choice. Never react to a warning with blind
    expansion or satisfy a target with repetition, filler, or unsupported claims.
24. Before creating the manuscript PRD, ask citation format in a dedicated
    ask-user interaction and record the current-conversation answer in
    `citation_preference.json`; do this even when an earlier message appears to
    imply a format, and never infer it from a template or silently choose it.
25. Present each complete analysis or manuscript PRD and then call ask-user for
    approval with `批准并继续`, `需要修改`, and `暂不批准`; an ask-user approval
    is sufficient and must not be followed by a request to type “同意”.
26. Before any experiment backend choice, probe the execution host for existing
    R/RStudio-compatible interpreters and installed packages; reuse them first,
    and allow only documented module-level, scientifically equivalent Python
    assistance when the required R capability is unavailable.
27. After any of the three knowledge-base writing choices, call ask-user a
    second time with 4-6 model-generated, source-grounded topics. Persist the
    selection, then enter the ordinary manuscript workflow; never treat topic
    selection as approval of either PRD.
28. Never hand-write analysis approval hashes or receipt keys. After approval,
    use `scripts/create_analysis_approval.py`; any later PRD or inventory edit
    invalidates the receipt and requires renewed approval.
29. Before external data access or generated Python execution, apply
    `references/network_execution_policy.md`: explicit timeouts, bounded
    retries, bulk-query-first retrieval, provenance caches and compatibility
    checks are mandatory.
30. Never launch an unmanaged background analysis or repeatedly poll with new
    shell commands. Use `scripts/run_analysis_supervised.py`, wait on the same
    session, and enforce a total timeout.
31. Never replace failed patient/study/record retrieval with remembered,
    synthetic or “known” values. A material fallback revises the PRD and
    requires renewed approval.
32. For ClinicalTrials.gov/PubMed work, read
    `references/clinicaltrials_pubmed_api.md`; use the bundled ClinicalTrials.gov
    v2 client, token pagination and precision-preserving date parsing. Never
    continue when successful retrieval unexpectedly normalizes to zero records.
33. Record `citation_export_mode` explicitly. Generate the first manuscript
    draft directly in that mode: real `\cite` for `strict_linked`, or a
    non-empty `.bib` with optional traditional bibliography commands for
    `bibliography_compatibility`. Never generate inline `thebibliography` or
    `\bibitem` as an intermediate draft.
34. Before manuscript code reads JSON results, run
    `scripts/inspect_json_schema.py`, save `manuscript/source_schema.json`, and
    use only observed keys. Never guess analysis-result field names.
35. Every Figure Blueprint must declare a Figure Contract, one archetype, an
    applicable hero panel (or explicit `null` for an equal-rank quantitative
    grid), a non-overlapping slot map, final physical dimensions, reviewer
    risks, and one rendering backend.
36. Require the selected backend to generate the Figure's complete source,
    preview PNG, editable SVG/PDF, TIFF, and QA JSON. Pillow composition is
    legacy compatibility only and is not a publication renderer.
