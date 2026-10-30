---
name: indication-dossier
description: 生成治疗适应症档案，覆盖患者人群、流行病学、疾病生物学、标准治疗、监管先例和里程碑式临床试验。
license: Apache-2.0
---

# 适应症档案

围绕单一适应症生成结构化研究档案，并将适应症视为一个患者人群：他们是谁、面临什么问题、目前如何接受治疗，以及应如何设计临床试验来帮助他们。工作流分为五个阶段，每个阶段都会写入可恢复的 waypoint 文件；第一阶段结束时进行一次简短的身份确认，之后其余阶段连续执行。

## 框架

**将适应症理解为一个患者人群。** 所有内容都从患者视角出发：“这些患者是谁？”而不是“这是什么疾病？”；“如何识别和管理这些患者？”而不是“这种疾病由什么导致？”；人群嵌套关系表述为：“`{child}` 中的所有患者都属于 `{parent}` 患者。”

有些适应症无法映射到 ICD 编码或标准疾病定义：“免疫衰老”是一种生物学状态，不是可计费诊断；“衰老”不是 FDA 接受的适应症；“GLP-1 诱导的肌少症”是医源性人群。必须明确记录这些区别，因为它们会影响监管路径和试验设计。

## 输入

- **`indication`**（必需）——适应症名称，例如“肌少症”或“特发性肺纤维化”。
- **`additional_context`**（可选）——需要重点关注的领域、父级适应症或其他框架信息。
- **`workdir`**（可选）——写入 waypoint 和最终报告的位置。默认为 `./do_not_commit/indication-dossier-<slug>/`。

## 本技能预期使用的工具

| 用途 | 工具 |
| --- | --- |
| ClinicalTrials.gov | `clinical-trials` MCP |
| 文献 | `pubmed` MCP |
| Web | `WebSearch`、`WebFetch`——FDA 指南、治疗指南（NCCN、AASLD、专科协会）、CDC／WHO 流行病学数据 |
| 文档 | 远程 PDF 使用 `WebFetch`；本地 PDF 使用 `Read` |
| 子代理 | 使用 `Agent` 并行收集证据 |

如果列出的 MCP 未连接，请说明这一点，并回退到 `WebSearch`，检索相应的公共底层来源（clinicaltrials.gov、pubmed.ncbi.nlm.nih.gov）。

## 输出布局

```text
<workdir>/
└── waypoints/
    ├── progress.json                 # 循环控制
    ├── meta.json                     # 阶段 1
    ├── epidemiology.json             # 阶段 2
    ├── biology_soc.json              # 阶段 3
    ├── regulatory_trials.json        # 阶段 4
    ├── sources_evaluated.json
    ├── research_output.json          # 阶段 5——结构化输出
    └── indication_dossier_report.md  # 阶段 5——最终交付物
```

所有 waypoint 文件的 schema 都位于 [references/waypoint-schemas.md](references/waypoint-schemas.md)。Waypoint 是可恢复状态。如果工作目录中已存在 waypoint，请读取它们、总结已完成内容，并询问要从哪个阶段恢复。

## 开始之前

读取 [references/00-research-standards.md](references/00-research-standards.md)。该文件规定了所有阶段的来源要求和反臆造规则。然后创建 `<workdir>/waypoints/`。

## 工作流

档案分五个阶段构建。每个阶段结束后，写入对应 waypoint 文件，并输出不超过 200 字的摘要，概述已发现内容和仍不确定的事项，然后直接进入下一阶段。唯一例外是阶段 1：写入 `meta.json` 后，展示解析出的适应症身份，并调用 `ask_user`，提供 **继续**／**修订身份**／**停止** 三个选项，以便在进入成本更高的阶段前发现对适应症名称的误解。如果 `ask_user` 不可用，请说明“将按此解释继续；如需纠正，请立即中断”，然后继续执行。

### 阶段 1——元数据初始化

读取 [references/01-meta-initialization.md](references/01-meta-initialization.md)。解析适应症身份：临床定义、ICD 编码、别名、父级适应症，以及它是否属于公认的诊断实体。快速扫描 ClinicalTrials.gov 试验格局。创建 `waypoints/meta.json`。

### 阶段 2——流行病学研究

读取 [references/02-epidemiology-research.md](references/02-epidemiology-research.md)。刻画患者人群：诊断标准、患病率和发病率、人口统计学特征和风险因素、自然病程。使用并行子代理同时检索 PubMed 和 Web。写入 `waypoints/epidemiology.json`。

### 阶段 3——生物学与标准治疗研究

读取 [references/03-biology-soc-research.md](references/03-biology-soc-research.md)。确定病理生理学、生物标志物、获批疗法、治疗指南和未满足需求。并行使用子代理：PubMed 负责生物学，Web 负责指南，FDA 负责批准信息。写入 `waypoints/biology_soc.json`。

### 阶段 4——监管与临床试验研究

读取 [references/04-regulatory-trials-research.md](references/04-regulatory-trials-research.md)。确定 FDA／EMA 接受的终点、监管先例、典型试验设计参数、里程碑试验和重要失败案例。并行使用子代理：FDA 负责指南和批准信息，ClinicalTrials.gov 负责试验模式，PubMed 负责试验历史综述。写入 `waypoints/regulatory_trials.json`。

### 阶段 5——综合

读取 [references/05-synthesis.md](references/05-synthesis.md) 和 [references/06-writing-style.md](references/06-writing-style.md)。读取四个整合后的 waypoint 文件。按照综合 reference 指定的顺序，以叙事章节形式写入 `waypoints/indication_dossier_report.md`，并根据写作指南添加行内引用；同时写入 `waypoints/research_output.json`。本阶段不得开启新的研究线程。允许有针对性地补充缺口：通过单次获取解决现有 waypoint 字段中的某个具体缺失值，例如批准年份、NCT ID 或申办方管线页面中的图。任何更广泛的问题都应列为缺口，而不是在此阶段展开研究。

## 恢复执行

如果调用时的 `workdir` 已包含 waypoint：列出已完成阶段，即相应 waypoint 文件存在且非空；展示元数据摘要，并询问用户下一步要运行哪个阶段。未经确认，绝不覆盖现有 waypoint。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
