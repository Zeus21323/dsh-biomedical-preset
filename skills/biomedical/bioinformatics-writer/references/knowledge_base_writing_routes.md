# Knowledge-Base Writing Routes

Read this file after Stage 0 selects a knowledge-base writing route. Use it to
generate the second `ask_user` topic menu and to seed the ordinary manuscript
workflow. Do not create a separate lightweight writing path.

## Topic-menu contract

Generate 4-6 options from the selected category. Keep the labels concise and
make every description contain:

```text
research question | primary source(s) | core method/evaluation | access status
```

Prefer topics with one primary source and at most two complementary sources.
Include at least three topics that can begin with public, non-credentialed
metadata or files. A credentialed source may appear only when its option says
that account approval, training, or a DUA is required. Never call “publicly
viewable,” “free after registration,” or “code under MIT” equivalent to
unrestricted open data.

When network access is available, use read-only official catalog/API metadata
to confirm that named sources and required modalities still exist before
showing the menu. Do not download large datasets, request credentials, install
software, or run an analysis before the analysis PRD is approved.

Call SpeedClaw `ask_user` immediately after generating the options:

```json
{
  "questions": [{
    "header": "影像选题|病历选题|知识库选题",
    "question": "请选择一个大模型根据开放数据源推荐的可执行选题：",
    "allow_other": true,
    "options": [
      {"label": "<topic label>", "description": "<question | sources | method | access>"}
    ]
  }]
}
```

Do not show a static placeholder as a selectable option. Populate the array
with the 4-6 generated topics. The user may use the Other field for a custom
topic.

## Route A: CT and medical-imaging knowledge bases

Set `selected_blueprint: imaging_knowledge_base`.

Preferred sources:

- NCI Imaging Data Commons and TCIA: CT, MRI, PET, radiography, digital
  pathology, segmentations, clinical metadata, DICOM, public MCP/REST and
  collection-level licenses. Prefer IDC bulk metadata/MCP/SQL or `idc-index`
  aggregation over repeated TCIA per-collection patient calls.
- OpenNeuro: public BIDS neuroimaging datasets; useful for MRI/fMRI/dMRI study
  designs.
- GDC/TCGA: cancer pathology, molecular and clinical metadata; some files are
  controlled.
- MIMIC-CXR: chest radiographs plus reports linked to MIMIC; credentialing,
  CITI training, and a DUA are required.
- CT-RATE: paired chest CT and reports; gated access and dataset-specific terms
  apply.

Good topic families include cohort characterization, metadata harmonization,
image-report retrieval, multimodal representation evaluation, segmentation or
annotation consistency, cross-collection generalization, and bias/error
analysis. Do not propose clinical deployment or diagnostic-performance claims
unless an appropriate labeled cohort and external validation are feasible.

## Route B: EHR and clinical-data knowledge bases

Set `selected_blueprint: clinical_ehr_knowledge_base`.

Preferred sources:

- Synthea: Apache-licensed generator and synthetic FHIR, Bulk FHIR, C-CDA and
  CSV records; suitable for pipeline, interoperability and retrieval tests,
  not real-world clinical-effect claims.
- MIMIC-IV and MIMIC-IV-Note: structured hospital/ICU data and deidentified
  notes; credentialing, CITI training, and a DUA are required.
- eICU-CRD: multicenter ICU data; credentialing and a DUA are required.
- HiRID and AmsterdamUMCdb: ICU data with their respective approval and DUA
  processes.
- ClinicalTrials.gov and openFDA may complement an EHR question but must not
  replace patient-level validation.

Good topic families include FHIR information retrieval, terminology
normalization, temporal cohort retrieval, missingness/data-quality analysis,
clinical-note retrieval, multicenter transportability, calibration/fairness,
and privacy-preserving evaluation. Clearly distinguish synthetic validation
from real-world validation.

## Route C: Biomedical literature and knowledge graphs

Set `selected_blueprint: literature_knowledge_graph`.

Preferred sources:

- PubMed metadata and PMC Open Access full text. Only the PMC OA subset and
  article-level permitted licenses may be used for reusable full text.
- Europe PMC REST: publications, open full text, citations and text-mined
  entities.
- ClinicalTrials.gov: trial design, interventions, status and posted results;
  use the API v2 client and contract in
  `references/clinicaltrials_pubmed_api.md`.
- openFDA, ChEMBL and PubChem: regulatory, drug, compound, target and activity
  data with source-specific caveats.
- OptimusKG: downloadable biomedical graph, Python client, Agent Skill and MCP
  bundle; its integrated upstream sources retain their own licenses.
- Mondo, HPO, MeSH, RxNorm and OLS: disease, phenotype, topic and drug
  normalization.
- GDC: cancer molecular and clinical metadata for evidence triangulation.

Good topic families include systematic evidence mapping, entity-normalized
literature retrieval, disease-drug-gene graph construction, trial-publication
linkage, temporal evidence drift, retrieval-grounded QA evaluation, graph
coverage/conflict analysis, and explainable hypothesis prioritization. Do not
turn database associations into causal or therapeutic claims.

## Selection artifact

Write `knowledge_base_topic_selection.json` after the second ask-user response:

```json
{
  "service_route": "bioinformatics_manuscript_writing",
  "knowledge_base_category": "imaging|clinical_ehr|literature_knowledge_graph",
  "selected_blueprint": "imaging_knowledge_base|clinical_ehr_knowledge_base|literature_knowledge_graph",
  "displayed_topics": [
    {
      "topic_id": "topic_1",
      "label": "...",
      "research_question": "...",
      "primary_sources": ["..."],
      "complementary_sources": [],
      "core_methods": ["..."],
      "evaluation_plan": ["..."],
      "access_status": "open_no_review|open_per_collection_license|credentialed_dua|source_specific_license"
    }
  ],
  "selected_topic_id": "topic_1|custom",
  "exact_user_response": "...",
  "selection_source": "ask_user|direct_chat",
  "selected_in_current_conversation": true,
  "data_source_status": "search_requested"
}
```

Copy the selected topic, blueprint and source plan into `study_goal.json` and
`analysis_prd.md`. `selected_in_current_conversation` records only the topic
choice; it never opens the analysis or manuscript approval gate.
