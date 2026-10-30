# Study Type Blueprints

Use these only as defaults. User choice and available data override them.

## Blueprint Routing Contract

Apply this contract whenever the Skill creates or revises an analysis plan.

### Selection priority

1. Honor an explicit blueprint or `study_type` named by the user when it is
   compatible with the available data.
2. Otherwise infer the blueprint from the requested analyses and intended
   scientific endpoint, not from disease name alone.
3. If exactly one blueprint matches, record it as both `study_type` and
   `selected_blueprint`.
4. If multiple blueprints match, choose the blueprint for the dominant final
   endpoint as `selected_blueprint`. Record another complete study workflow in
   `secondary_blueprints`; record a bounded supporting analysis in
   `extension_modules`.
5. If the dominant endpoint is genuinely ambiguous and would materially change
   the plan, ask one concise question. Do not choose arbitrarily.

Use these routing signals:

| Requested analysis or endpoint | Blueprint |
|---|---|
| group comparison, PCA, differential expression, DEG enrichment, GSEA/GSVA | `group_comparison_transcriptomics` |
| CIBERSORT, ssGSEA, xCell, ESTIMATE, immune-cell or checkpoint comparison | `immune_infiltration` |
| Cox, LASSO-Cox, risk score, Kaplan-Meier, time-dependent ROC, nomogram | `prognostic_signature` |
| scRNA-seq QC, clustering, annotation, subclusters, trajectory, communication | `single_cell_tme` |
| one candidate gene/pathway/cell type with clinical, pathway, TME, or drug evidence | `mechanism_candidate_gene` |
| spatial domains, spatial mapping, or spatial cell localization | `spatial_transcriptomics` |
| bulk-to-single mapping, deconvolution, or cross-modal integration | `bulk2single` |
| CT/MRI/X-ray/pathology repositories, DICOM cohorts, image-report retrieval, imaging annotation or multimodal imaging evaluation | `imaging_knowledge_base` |
| EHR/ICU/FHIR/clinical notes, temporal cohort retrieval, clinical data quality, interoperability or EHR model evaluation | `clinical_ehr_knowledge_base` |
| PubMed/PMC/Europe PMC, clinical trials, drug databases, biomedical ontologies, evidence graphs or knowledge-graph retrieval | `literature_knowledge_graph` |

### Required records

For one blueprint, write:

```json
{
  "study_type": "prognostic_signature",
  "selected_blueprint": "prognostic_signature",
  "secondary_blueprints": [],
  "extension_modules": []
}
```

For a hybrid request such as differential-expression screening followed by a
prognostic model and immune-infiltration characterization, write:

```json
{
  "study_type": "prognostic_signature",
  "selected_blueprint": "prognostic_signature",
  "secondary_blueprints": ["group_comparison_transcriptomics"],
  "extension_modules": ["immune_infiltration"]
}
```

Apply only the selected sections below. Merge their analyses into one
deduplicated `analysis_inventory.json`. Every inventory item must contain:

```json
{
  "analysis_name": "univariate_cox",
  "source_blueprint": "prognostic_signature",
  "scope_class": "primary",
  "selection_origin": "user_requested|blueprint_default",
  "purpose": "...",
  "required_inputs": [],
  "expected_outputs": [],
  "statistical_method": "...",
  "figure_panels": []
}
```

Preserve all analyses explicitly requested by the user unless they are
infeasible, invalid, duplicative, or conflict with a stated constraint. Explain
every omission in the PRD. Add unrequested blueprint defaults conservatively,
label them `blueprint_default`, and let the user add or remove items at the PRD
approval gate. Never execute the union of every blueprint.

## Group Comparison Transcriptomics

Examples: ER+ vs ER-, tumor vs normal, resistant vs sensitive.

Default analyses:

```text
metadata summary
expression QC
PCA
differential expression
DEG heatmap
GO/KEGG/Reactome enrichment
GSEA or GSVA
candidate gene selection
external validation if available
```

Default figure logic:

```text
Figure 1: dataset overview and global expression pattern
Figure 2: differential expression landscape
Figure 3: pathway enrichment and biological programs
Figure 4: candidate gene or signature characterization
Figure 5: external validation
Figure 6: mechanism model
```

## Immune Infiltration

Default analyses:

```text
CIBERSORT/ssGSEA/xCell/ESTIMATE
group comparison of immune cells
immune correlation heatmap
immune checkpoint expression
immune-related gene correlation
TIDE or therapy response estimate if justified
```

Default figure logic:

```text
Figure 1: cohort and study design
Figure 2: global transcriptomic differences
Figure 3: immune infiltration landscape
Figure 4: immune-related genes/pathways
Figure 5: validation in external cohort
Figure 6: immune mechanism model
```

## Prognostic Signature

Default analyses:

```text
training/validation split
univariate Cox
LASSO or multivariable Cox
risk score construction
Kaplan-Meier survival
time-dependent ROC
risk plot
nomogram
calibration/decision curve if appropriate
immune/drug/pathway associations
external validation
```

Default figure logic:

```text
Figure 1: cohort flow and candidate screening
Figure 2: model construction
Figure 3: survival and ROC validation
Figure 4: nomogram and clinical independence
Figure 5: biological characterization of risk groups
Figure 6: external validation and translational model
```

## Single-cell TME

Default analyses:

```text
QC
UMAP/tSNE clustering
cell type annotation
target subcluster identification
marker genes
cell proportion comparison
pathway scoring
pseudotime if justified
cell-cell communication
CNV inference for malignant cells if relevant
spatial or bulk validation if available
```

Default figure logic:

```text
Figure 1: single-cell atlas and cell annotation
Figure 2: target cell subcluster discovery
Figure 3: clinical/spatial relevance
Figure 4: cell-cell communication
Figure 5: pathway/trajectory/mechanism
Figure 6: validation or intervention model
```

## Mechanism Candidate Gene

Default analyses:

```text
expression comparison
clinical association
survival or diagnostic value
pathway enrichment
immune/TME association
single-cell cell-source validation if available
drug sensitivity or treatment-response association if relevant
literature-supported mechanism hypothesis
```

Default figure logic:

```text
Figure 1: candidate gene discovery and expression
Figure 2: clinical relevance
Figure 3: pathway and TME characterization
Figure 4: upstream/downstream mechanism hypothesis
Figure 5: external or experimental validation
Figure 6: therapeutic/prognostic model
```

## Imaging Knowledge Base

Use for CT, MRI, X-ray, digital pathology or linked image-report studies.

Default analyses:

```text
source, license and collection-version audit
official endpoint smoke test and response-provenance archive
cohort inclusion/exclusion and modality/body-region summary
DICOM patient/study/series counts from a bulk metadata query
DICOM/BIDS metadata harmonization and image-report linkage checks
label, segmentation or annotation quality assessment when available
approved image, text or multimodal representation/retrieval analysis
held-out or cross-collection evaluation when feasible
subgroup, bias, failure-mode and provenance analysis
```

Default figure logic:

```text
Figure 1: source selection, cohort flow and data schema
Figure 2: imaging and metadata characteristics
Figure 3: representation, retrieval or annotation method
Figure 4: primary evaluation results
Figure 5: subgroup, generalization and failure analysis
Figure 6: evidence-grounded workflow and limitations
```

For IDC/TCIA cohort summaries, use IDC MCP/SQL/REST, BigQuery, or `idc-index`
aggregation before considering per-collection TCIA calls. Never run an
unbounded N+1 patient-query loop. Preserve failed/missing collections as data
quality results; do not impute counts from descriptions or model memory.

## Clinical EHR Knowledge Base

Use for structured EHR, ICU, FHIR, clinical-note or temporal clinical-data
studies.

Default analyses:

```text
source, license, credential and cohort-definition audit
schema, coding-system and patient/encounter linkage validation
missingness, plausibility, temporal leakage and data-quality assessment
FHIR or terminology normalization when relevant
approved retrieval, cohorting, prediction or interoperability analysis
calibration, subgroup, transportability and error analysis when feasible
privacy, synthetic-versus-real and clinical-validity limitations
```

Default figure logic:

```text
Figure 1: data source, cohort flow and clinical-data model
Figure 2: cohort and data-quality characteristics
Figure 3: normalization, retrieval or modeling workflow
Figure 4: primary analysis and evaluation
Figure 5: calibration, subgroup or transportability analysis
Figure 6: clinical interpretation, privacy and limitations
```

## Literature Knowledge Graph

Use for literature corpora, trial registries, drug databases, ontologies and
biomedical knowledge graphs.

Default analyses:

```text
source, query, version and article/record-license audit
official API schema, pagination and 1-2 record smoke test
search/retrieval protocol and inclusion/exclusion flow
entity extraction, terminology normalization and cross-source linking
corpus or graph coverage, topology, provenance and conflict assessment
approved retrieval, ranking, graph or evidence-synthesis evaluation
temporal, source-ablation, case-study and error analysis
claim-to-record traceability and non-causal interpretation limits
```

For ClinicalTrials.gov/PubMed evidence studies, apply
`references/clinicaltrials_pubmed_api.md`. Preserve raw and normalized counts at
every step; an unexplained non-empty-to-zero transition blocks analysis.

Default figure logic:

```text
Figure 1: source selection and evidence-flow diagram
Figure 2: corpus, entity and graph characteristics
Figure 3: normalization, linking or retrieval framework
Figure 4: primary evaluation or evidence map
Figure 5: temporal, source-ablation and error analysis
Figure 6: representative traceable cases and limitations
```
