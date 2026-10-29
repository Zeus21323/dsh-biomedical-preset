# Session-Scoped Trellis Workflow

Use this workflow only in the conversation that invoked `bioinformatics-writer`.
It adapts Trellis's brainstorm, implement, check, and finish phases to a
bioinformatics manuscript task without installing Trellis or creating a
`.trellis/` directory.

## Scope and state

- Keep workflow state in the current conversation and in the explicit analysis
  artifacts produced for this study.
- Do not install `@mindfoldhq/trellis`, run `trellis init`, create a Trellis
  journal, or assume that another conversation knows this task's state.
- Scientific outputs remain normal project deliverables: result tables,
  figures, `analysis_prd.md`, `results_question_map.json`,
  `figure_blueprint.json`, `mainbody.tex`, and DOCX files may be written to the
  project.
- Do not commit or perform destructive Git operations unless the user asks.

## Phase 0: Route the request

At the first Skill invocation in a conversation, call SpeedClaw's built-in
`ask_user` tool (or the host's equivalent structured tool) and ask the user to choose:

1. Bioinformatics manuscript writing
2. Bioinformatics experiment/data analysis
3. Another bioinformatics request
4. CT/medical-imaging knowledge-base writing
5. EHR/clinical-data knowledge-base writing
6. Biomedical-literature/knowledge-graph writing

Do this before inspecting data or generating a plan. In SpeedClaw, present
these as structured options, not manually typed choices. Ask directly only if
no structured ask-user tool is available. Store the selection in the current
conversation; do not repeat it unless the user changes goals.

- For manuscript writing, use the complete workflow.
- For experiment/data analysis, stop after verified analysis results, figures,
  and a results report unless the user later requests a manuscript.
- For another request, ask for the intended deliverable and use only the
  applicable parts of the workflow.
- For any knowledge-base writing route, read
  `references/knowledge_base_writing_routes.md`, generate 4-6 source-grounded
  feasible topics, and immediately call ask-user a second time. Persist the
  selected topic in `knowledge_base_topic_selection.json`, map it to the
  matching knowledge-base blueprint, and then use the complete manuscript
  workflow. Topic selection does not approve either downstream PRD.

## Phase 1: Plan (Trellis brainstorm)

Map this phase to Bioinformatics Writer Stages 1 and 2 after routing. Tailor
the PRD and acceptance criteria to the selected service.

### Inspect evidence before asking

Inspect the provided project, data files, metadata, existing scripts, result
tables, figures, and manuscript files first. Ask the user only for decisions
that repository evidence cannot answer. Ask one highest-value question at a
time.

### Confirm the study

Confirm:

- study goal and biological question
- disease or biological context
- data source and local paths/accession
- expression or count matrix
- clinical/sample metadata
- comparison groups and covariates
- study type
- external validation availability

For a knowledge-base route, replace omics-only facts that do not apply with:

- selected topic and knowledge-base category
- named primary and complementary sources
- source release/version, access status and license restrictions
- record, patient, study, series, article or graph entity unit of analysis
- inclusion/exclusion, linkage and evaluation design
- credential/DUA status for any controlled source

After the essential facts are known, read `references/study_type_blueprints.md`,
apply its Blueprint Routing Contract, and create `study_goal.json`. Record one
`selected_blueprint`, plus `secondary_blueprints` and `extension_modules` when
the user's requested analyses cross blueprint boundaries. Do not ask the user
to repeat analyses already present in the instruction.

### Confirm the analysis plan

Build a conservative, deduplicated analysis inventory from the selected
blueprint(s), the user's explicitly requested analyses, and usable inputs. For
each analysis record its source blueprint or extension module, scope class,
selection origin, purpose, inputs, statistical method, expected result files,
likely figure panels, and known limitations. Explicitly separate in-scope,
out-of-scope, optional, and blocked analyses.

Create `analysis_prd.md` as the human-readable source of truth. It must
contain:

- Goal and user value
- Data source and comparison design
- Study type
- Selected primary blueprint, secondary blueprints, and extension modules
- Approved analysis inventory
- Expected result and figure deliverables
- Acceptance criteria
- Out-of-scope work
- Risks, missing inputs, and scientific limitations
- `Status: pending | approved | revised`

Keep blueprint selections and analysis-source fields consistent across
`study_goal.json`, `analysis_inventory.json`, and the PRD.

### Planning gate

Present the final planning summary to the user with Goal, Data, In Scope, Out
of Scope, Analysis Inventory, Acceptance Criteria, Risks, and artifact paths.
Read `references/approval_interactions.md`. Then call the available ask-user
tool with one dedicated approval question and
three choices: `批准并继续`, `需要修改`, and `暂不批准`. The returned tool choice
is the explicit approval; never ask the user to type “同意” afterward. If the
tool is unavailable, ask the same question directly and stop for the reply.

For approval, never hand-write `analysis_approval.json` or its hashes. Run
`scripts/create_analysis_approval.py` with the exact returned answer and
approval source. The creator normalizes the PRD status, computes final hashes,
writes the fixed receipt schema, and invokes the validator. Treat its success
as the required gate before Stage 3. For requested changes, mark the PRD
`revised`, update it, present the changed summary, and invoke ask-user again.
For `暂不批准`, keep it pending and stop.

After creating a receipt, do not modify `analysis_prd.md` or
`analysis_inventory.json`. Any modification invalidates the receipt and
requires a revised PRD, renewed approval, and a new creator run. Read
`references/approval_interactions.md` for the exact command and schema.

Do not run analysis, install analysis dependencies, download large datasets,
or draft Results before the user approves the latest planning summary. If the
plan changes materially after approval, update `analysis_prd.md`, mark it
`revised`, present the changed summary, and obtain approval again.

### Manuscript planning gate

For manuscript writing, including requests based entirely on completed
results, read `references/manuscript_workflow.md`. Audit the existing evidence,
then generate and validate `results_question_map.json` and
`figure_blueprint.json`. Resolve the target journal, call the available
ask-user tool with a separate citation-format question, and save the exact
current-conversation choice to `citation_preference.json`. Do not bundle this
question into manuscript-plan approval or infer a default. Create
`manuscript_outline.json` and
`manuscript_prd.md`, present every chapter's purpose and every Results
claim/evidence/statistic/figure mapping, and call ask-user with the same three
approval choices from `references/approval_interactions.md`. An ask-user approval counts immediately and does not require
a later typed message. Read
`references/manuscript_length_policy.md` and include the target
word-equivalents for every main section and substantive Methods/Results
subsection in the plan presented to the user. Record the enforcement mode;
default to advisory and use strict only when documented or explicitly chosen.

This is a second gate, separate from analysis PRD approval. Before it is
approved, do not generate or compose figures, search literature, draft any
manuscript section, create `mainbody.tex`, or export DOCX. Completed analyses
never waive this gate. A material writing-plan change requires a revised plan
and a new ask-user approval.

## Phase 2: Implement

### OmicVerse MCP gate

Before any environment probe or data download, generate and validate
`environment/omicverse_mcp_routing.json` for every approved inventory item, as
required by Stage 3. This applies to all blueprints and modalities. Use the
live catalog for every module when registered; otherwise compare every module
with `references/omicverse_mcp_capability_map.md`, prompt for installation if
any plausible candidate exists, then repeat live discovery. Do not make a
whole-study judgment such as “bulk is not applicable.”

Use MCP only if it supports a module's approved method, inputs, and
dependencies. For a module with no suitable MCP tool, record the concrete
reason and its R/Python fallback in the routing table, then continue. A failed
MCP call, unavailable dependency, or missing tool is local to that module:
continue the remaining approved modules and stop only the affected one if no
valid scientific fallback exists.

Map this phase to Bioinformatics Writer Stages 3 through 11. Execute only the
approved inventory:

1. Run or collect real analysis outputs.
2. Generate and validate `results_question_map.json`.
3. Generate and validate `figure_blueprint.json`.
4. For manuscript writing, create and obtain approval for
   `manuscript_outline.json` and `manuscript_prd.md`.
5. Generate individual panels before composing figures.
6. Compose multi-panel figures and previews.
7. Draft Results text and figure legends from result files.
8. Add literature context only after findings are computed and the manuscript
   plan is approved.
9. For manuscript writing, generate `manuscript/mainbody.tex` and
   supplementary files.
10. Run manuscript preflight and export DOCX through the existing
    `tex_to_docx` skill only when requested. Never invoke Pandoc directly.

For analysis-only work, replace manuscript generation with a concise analysis
report that points to the verified result tables and figures.

Read before writing. Keep every Results claim traceable to a local result file.
Do not add an unapproved analysis silently, and report material deviations.

### Network and long-running execution gate

Before any external API request, download, Python analysis or long-running
command, read `references/network_execution_policy.md`. Use bulk metadata
queries instead of N+1 collection/record loops, require explicit request and
module deadlines, cache responses with provenance, and run a bounded smoke
test. Save `environment/python_environment.json` for Python modules.

If ClinicalTrials.gov or PubMed is in scope, also read
`references/clinicaltrials_pubmed_api.md`. Use
`scripts/clinicaltrials_v2_client.py` rather than custom ClinicalTrials.gov
pagination/date code. Verify a 1-2 record response before bulk retrieval and
record input/retained/excluded counts at every parsing or filtering step.

Run long commands only through `scripts/run_analysis_supervised.py`; do not use
`nohup`, shell `&`, or repeated `ps`/`tail` polling. Wait on the same host
execution session and use the supervisor status/log artifacts. An external
failure may not be filled from model memory or undocumented “known” values. If
fallback changes the source, unit of analysis, cohort, endpoint, method or
claim, revise and reapprove the analysis PRD before continuing.

### Backend routing

Read `references/backend_policy.md` before implementation. Derive required R
packages from the approved modules and run `scripts/probe_r_environment.py`
before selecting a backend. Preserve `environment/r_environment.json` and
`environment/backend_decision.json`; reuse the detected local R/RStudio package
libraries first. Python may assist module by module only when the required R
capability is unavailable and the substitute is scientifically equivalent.
For approved work that a live OmicVerse MCP tool can perform, read
`references/omicverse_mcp_backend.md`, discover the tool, and call it. If the
local runtime is absent, use its explicit opt-in installation gate. Record the
MCP tool, returned version information, parameters, installation/registration
status, fallback status, and output paths under the experiment directory. If
the user declines, the server cannot be registered, or a required tool remains
unavailable, use the documented fallback or stop with a clear backend-unavailable status.

### Experiment-scoped figure workspace

Store every single-result plot under the experiment or analysis module that
produced it. Use this layout in the current project workspace:

```text
figures/
  experiments/
    <experiment_slug>/
      panels/
      sources/
      metadata/
  combined/
```

Use a stable lowercase slug such as `differential_expression`,
`pathway_enrichment`, `immune_infiltration`, `prognostic_model`, or
`single_cell_annotation`. Every panel in `figure_blueprint.json` must include
the same `experiment` slug and an `output` path under that experiment's
`panels/` directory. Never flatten all single panels into
`figures/panels/`.

Keep the editable R/Python script, notebook, SVG/PDF source, or plot
configuration in `sources/` when available. Write panel metadata in
`metadata/`, including input file, sample subset, statistical test,
multiple-testing correction, main message, and plotting parameters. The user
should be able to adjust one experiment's evidence without regenerating
unrelated experiments.

Before creating Python panels, read `references/publication_figure_guidelines.md`
and use `scripts/publication_figure_utils.py` for the shared style, color
palette, journal-sized canvas, and PNG/PDF/SVG/TIFF export. Use the equivalent
R/ggplot2 settings when the analysis is written in R.

Also read `references/nature_figure_integration.md`. For each major Figure,
select one `render_backend` and create one complete source under
`figures/combined/sources/`. Analysis modules may use different scientific
backends, but the complete Figure source must draw all quantitative panels,
perform the panel-slot layout, add labels and shared legends, and export the
preview, SVG, PDF, TIFF, and QA JSON through the one selected Figure backend.
Do not use the legacy Pillow composer as the default publication renderer.

## Phase 3: Verify (Trellis check)

Verification is mandatory before completion.

### Data and statistical checks

- `environment/r_environment.json` records the execution-host R probe and the
  required package availability before backend selection.
- `environment/backend_decision.json` explains every module backend and any
  R-to-Python fallback; no working installed R-native module was bypassed for
  convenience.
- `environment/python_environment.json` records package versions and required
  capabilities for every Python analysis; generated scripts compile and pass a
  bounded smoke test.
- External requests have explicit timeouts, bounded retries, local response
  artifacts and provenance; no unbounded per-record or per-collection loop ran.
- ClinicalTrials.gov requests contain no numeric `page`, advance only through
  `nextPageToken`/`pageToken`, preserve partial completion dates, and never turn
  a non-empty response into an unexplained empty normalized cohort.
- Every long-running command has `environment/analysis_task_status.json`, a log,
  a total deadline and a terminal supervisor status.
- Input files exist and are readable.
- Sample identifiers align across matrices and metadata.
- Groups and sample counts match the approved PRD.
- Statistical tests and multiple-testing correction are recorded.
- Exclusions, failed analyses, and missing values are documented.
- Every scientific claim is supported by a result table or statistical log.
- No missing API value was replaced by model memory, a prose description,
  synthetic data, or an undocumented cache.

### Structured artifact checks

Run the bundled validators:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_results_question_map.py \
  results_question_map.json --project-root .

python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/validate_figure_blueprint.py \
  figure_blueprint.json --project-root . \
  --require-panel-outputs \
  --require-figure-source \
  --require-publication-outputs

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

Use the absolute script paths when the current working directory differs from
the project containing the files.

### Figure and manuscript checks

- Each Results question maps to a biological claim and a major figure.
- Every major Figure declares its core conclusion, archetype, applicable hero
  panel (or explicit `null` for an equal-rank quantitative grid), evidence
  hierarchy, reviewer risks, final physical dimensions, and a non-overlapping
  slot map.
- Every panel has a real input file, statistical message, label, experiment
  slug, and experiment-scoped output path.
- Each experiment directory contains the panel outputs and, when available,
  editable source and metadata files.
- The one recorded rendering backend produced the complete Figure source,
  preview PNG, editable SVG/PDF, high-resolution TIFF, and QA JSON.
- The SVG/PDF remains readable at final size, text is editable, and no panel,
  label, annotation, or shared legend overlaps.
- Colors are colorblind-safe, axes have units, and error bars state whether
  they are SD, SEM, or CI.
- Results text matches computed outputs and does not turn association into
  causation.
- When a manuscript is in scope, every major figure is embedded in
  `mainbody.tex` with a literal relative `\includegraphics{...}` path.
- When DOCX is in scope, every image target exists below `manuscript/` before
  export and the DOCX contains embedded figures under `word/media/`.
- `manuscript_prd.md` and `manuscript_outline.json` are approved in the current
  conversation, and the manuscript preflight passes.
- `citation_preference.json` records a dedicated ask-user response (or the
  direct-chat fallback when the tool is unavailable) from the current conversation and
  matches the plan's citation style, mode, and presentation.
- The manuscript preflight reports `MANUSCRIPT_LENGTH` and every main section,
  substantive Methods/Results subsection, abstract, and major figure legend
  meets the approved word-equivalent minimum without filler or unsupported text.
- DOCX was produced by `tex_to_docx`; its log contains no unresolved
  citation/reference/bibliography warning. Direct Pandoc output is invalid.

When a check fails, diagnose, fix within the approved scope, rerun the failed
check, and report anything still unresolved. Do not claim success from a
partially checked workflow.

## Phase 4: Finish

Finish only in the current conversation. Do not archive a task, write a
cross-session journal, update a Trellis spec, or promise automatic continuation
in a new conversation.

Report:

### Completed

- analyses performed
- figures generated
- manuscript and DOCX outputs generated

### Deliverables

List exact paths for result tables, JSON artifacts, panels, combined figures,
LaTeX files, bibliography, supplementary files, and DOCX.

### Verification

Report each check as `pass`, `fail`, or `not run`, including the two JSON
validators, data/output traceability, manuscript checks, and DOCX media check.

### Deviations and limitations

List uncompleted approved analyses, changed scope, missing inputs, unresolved
errors, and scientific limitations.
