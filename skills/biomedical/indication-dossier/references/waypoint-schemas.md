# Waypoint 文件 schema

以下 schema 定义每个 `<workdir>/waypoints/*.json` 文件的结构。各阶段 reference 文件会指向这里的输出格式。

## `progress.json`——循环控制

```json
{
  "complete": false,
  "output_file": null,
  "current_phase": "meta_initialization",
  "iteration_notes": "What was accomplished this iteration"
}
```

完成时：

```json
{
  "complete": true,
  "output_file": "indication_dossier_report.md",
  "current_phase": "synthesis"
}
```

## `meta.json`——适应症身份，由 `meta_initialization` 阶段写入

```json
{
  "indication_name": "...",
  "parent_indication": "... or null",
  "definition": "...",
  "icd_codes": ["K70", "..."],
  "aliases": ["..."],
  "is_standard_diagnosis": true,
  "notes": "Any caveats about this indication's status (not ICD-coded, novel, etc.)"
}
```

## `epidemiology.json`——第 1 节数据

```json
{
  "subsections": {
    "diagnostic_criteria": {"content": "...", "sources": [...], "coverage": "covered|partial|missing"},
    "prevalence_incidence": {"content": "...", "sources": [...], "coverage": "..."},
    "demographics": {"content": "...", "sources": [...], "coverage": "..."},
    "natural_history": {"content": "...", "sources": [...], "coverage": "..."}
  },
  "gaps": ["unfillable gaps documented here"]
}
```

## `biology_soc.json`——第 2–3 节数据

```json
{
  "subsections": {
    "pathophysiology": {"content": "...", "sources": [...], "coverage": "..."},
    "biomarkers": {"content": "...", "sources": [...], "coverage": "..."},
    "approved_therapies": {"content": "...", "sources": [...], "coverage": "..."},
    "treatment_guidelines": {"content": "...", "sources": [...], "coverage": "..."},
    "unmet_need": {"content": "...", "sources": [...], "coverage": "..."}
  },
  "gaps": [...]
}
```

## `regulatory_trials.json`——第 4–5 节数据

```json
{
  "subsections": {
    "accepted_endpoints": {"content": "...", "sources": [...], "coverage": "..."},
    "fda_guidance": {"content": "...", "sources": [...], "coverage": "..."},
    "trial_parameters": {"content": "...", "sources": [...], "coverage": "..."},
    "landmark_trials": {"content": "...", "sources": [...], "coverage": "..."},
    "notable_failures": {"content": "...", "sources": [...], "coverage": "..."}
  },
  "trial_landscape": {
    "total_trials": 0,
    "by_phase": {"Phase 1": 0, "Phase 2": 0, "Phase 3": 0, "Phase 4": 0},
    "by_status": {"Recruiting": 0, "Completed": 0, "...": 0}
  },
  "gaps": [...]
}
```

## `sources_evaluated.json`——查阅过的全部来源

```json
{
  "sources": [
    {"url": "...", "source_type": "...", "date_accessed": "...", "result": "success|failed|partial"}
  ]
}
```

## `indication_dossier_report.md`／`research_output.json`

最终 Markdown 报告和整合后的结构化输出都写入 `waypoints/`。`research_output.json` 的结构参见 [references/05-synthesis.md](05-synthesis.md)。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
