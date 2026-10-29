# Markdown证据报告规范

## 写作与交付

先判断阶段：`plan` 为数据遴选与研究设计，`results` 为包含至少一项实际分析的结果报告。案例中的示意图、预期基因数量、预期 AUC 或参考论文结果都不能充当本项目实际结果。

报告先给问题与结论，再说明数据选择和证据路线。每节按“要回答什么 → 使用哪些数据及方法 → 实际观察 → 如何解释 → 限制与下一步”组织。计划阶段将实际观察替换为预定判定标准和可能的不同结果，使用将来时。结果阶段区分已完成、失败、未运行；仅在相关模块存在时写预后、免疫、空间、网络或药物章节。

结果的关键数字必须能定位到表的行列、图号或日志步骤，包括分析后独立供体数、实际对比、效应与区间、FDR、模型性能及其验证方式。参数、软件和基因集版本写在相应章节，运行记录加入证据清单。正文使用 Markdown 链接或图片引用时，以最终报告目录为基准；脚本只会重定位结构化 `evidence.locator`，不会改写正文内手写链接。

结论逐条关联章节或证据编号，说明观察、推断与尚未验证的部分。报告无显著差异、验证失败和方向冲突；“趋势一致但不显著”不能写为“验证成功”。文献支持生物学解释，不能替代本项目结果文件。外部队列复现与预测、定位、功能实验分别描述，不把模型系统证据升级为临床证实。

脚本渲染完整的比较表和模型已撰写的段落，不自动撰写结论、评估统计功效或判断真实性。输出后人工核对核心数字与原始结果，检查图文对应、链接、跨队列独立性、结论强度及当前研究范围。交付报告、对应清单和被引用的本地结果文件；不以 JSON 替代用户要求的可读 Markdown。

## 清单契约

使用 UTF-8 JSON。下列字段均应提供，未知数值用 `null`，未知文字写“未知”并在限制中说明；不得把未知填成 0。ID 在各自列表内唯一，所有关联使用 ID 而不是标题。

| 字段 | 内容 |
| --- | --- |
| `schema_version` | 固定为整数 `1` |
| `mode` | `plan` 或 `results` |
| `title`, `question` | 具体报告标题、研究问题与目标人群/主要终点 |
| `as_of` | 资料截止日期，`YYYY-MM-DD` |
| `requested_count` | 用户希望选择的数据集数量，未指定则 `null` |
| `route` | 论证路线、为何选择此起点、必要时说明计算和写作顺序差异 |
| `conclusion` | 有证据编号的实际结论或研究方案建议，不由脚本推断 |
| `criteria` | 非空字符串列表：纳排标准、主要对比与优先条件 |
| `search_notes` | 非空字符串列表：来源、日期、查询/过滤、总数/已取数、截断情况 |
| `datasets` | 候选记录列表，可为空，允许同时记录入选、排除和待核验 |
| `evidence` | 元数据、文献和实际结果的出处列表，计划阶段可为空 |
| `sections` | 非空的分阶段论证列表，排列顺序就是报告顺序 |
| `limitations`, `next_steps` | 非空字符串列表：限制、替代解释、缺口与下一步 |

每个 `datasets` 条目：

- `id`, `accession`, `source_url`：本地关联 ID、官方标识、HTTP(S) 来源页面。
- `species`, `system`, `tissue`, `assay`, `platform`：物种、患者/动物/类器官等系统、组织和技术。
- `groups`：疾病与对照定义、组别数量、配对、批次、时间点及统计单位；标明数据库总数、计划子集数或实际纳入数。
- `n_donors`, `n_samples`, `n_cells`：非负整数或 `null`，不能互相替代。
- `data_layer`, `version`, `access`：可用计数/归一化矩阵/原始文件与样本表、参考及发布版本、许可/受控访问/下载方式。
- `decision`：`selected`、`pending`、`excluded`。
- `roles`：从 `cell_localization`、`discovery`、`training`、`external_validation`、`mechanism_support` 中选择的列表；入选至少一个角色。
- `independence`：`confirmed`、`unknown`、`overlap`、`not_applicable`；其含义是相对于本研究其他数据的独立性。
- `overlap_with`：重叠候选的 ID 列表，未知或未发现填 `[]`，空列表并不证明独立。
- `reason`, `limitations`：入选/排除/待核验理由、独立性核验依据、角色适用性、缺失信息和偏倚。

入选外部验证数据不能同时承担发现或训练，也不能有已知队列重叠。独立性未知时可先保留候选角色，但脚本会明确提示它不能支持独立验证声明。不同物种或模型系统的证据应由作者标为 `mechanism_support`；脚本不根据自然语言自动推断系统是否匹配。

每个 `evidence` 条目提供 `id`, `kind`, `label`, `locator`, `dataset_ids`。`kind` 为 `metadata`、`literature` 或 `result`；`locator` 是 HTTP(S) 地址或相对于清单目录的文件路径，`label` 中写明表、图或日志定位。结果证据至少关联一个已登记数据集；全局背景文献可以关联空列表。脚本验证本地文件存在，不解析数值或联网检查远程内容。外部来源须在写入清单前由作者核验。

每个 `sections` 条目提供：

- `id`, `title`, `text`：章节 ID、标题和已撰写的 Markdown 解读。
- `status`：`planned`、`completed`、`failed`、`not_run`。
- `level`：`hypothesis`、`association`、`localization`、`prediction`、`replication`、`functional`。
- `dataset_ids`, `evidence_ids`：对应数据集与证据 ID 列表。

`completed` 仅在 `results` 中使用，对应的每个数据集都要有该节引用的 `result` 出处。`results` 至少有一节 `completed`；如果所有分析均未运行或失败，输出 `plan` 并记录原因。真实结果、推断和外部复现混在同一节时宜拆节，避免单一证据等级掩盖差异。

## 可运行的合成计划示例

以下 accession 和域名仅用于测试报告生成，不能作为真实可用数据推荐。实际使用时替换为已核验数据；目标为两组但当前仅入选一组，脚本应报告数量缺口。

```json
{
  "schema_version": 1,
  "mode": "plan",
  "title": "示例疾病的细胞来源与人群验证研究方案",
  "question": "候选细胞状态是否与示例疾病相关，并可在独立队列复现？",
  "as_of": "2026-09-07",
  "requested_count": 2,
  "route": "先检查单细胞供体和细胞覆盖，再寻找独立人群验证。",
  "conclusion": "当前仅有合成发现集记录，验证队列尚未落实；不能形成结果结论。",
  "criteria": ["组织及病例定义一致；疾病组间推断需独立供体。"],
  "search_notes": ["合成示例，未联网检索，候选数为1，不涉及分页。"],
  "datasets": [{
    "id": "D1", "accession": "SYNTHETIC-SC-01",
    "source_url": "https://example.org/synthetic-sc-01",
    "species": "Homo sapiens", "system": "合成人体组织元数据",
    "tissue": "示例组织", "assay": "scRNA-seq", "platform": "模拟平台",
    "groups": "虚构病例4名、对照4名，每供体1个样本；计划数量，尚未质控。",
    "n_donors": 8, "n_samples": 8, "n_cells": null,
    "data_layer": "计划取得counts和供体映射", "version": "合成v1",
    "access": "仅作合成示例，无真实下载数据或许可声明",
    "decision": "selected", "roles": ["cell_localization", "discovery"],
    "independence": "unknown", "overlap_with": [],
    "reason": "用于演示发现角色", "limitations": "尚未取得真实数据，无法评估功效。"
  }],
  "evidence": [],
  "sections": [{
    "id": "S1", "title": "细胞状态与疾病关联的计划",
    "status": "planned", "level": "hypothesis",
    "dataset_ids": ["D1"], "evidence_ids": [],
    "text": "先核实供体映射和目标细胞覆盖，再制定供体层模型；允许无差异结果。"
  }],
  "limitations": ["无真实数据；独立验证未落实。"],
  "next_steps": ["检索并核验真实发现与验证队列。"]
}
```

将 JSON 保存为项目的 `study_manifest.json`，按入口命令生成 `report.md`。结果模式需要实际结果出处和已撰写的解读，不能只修改 `mode`。默认拒绝覆盖已有报告，`--overwrite` 也不能覆盖输入清单或被引用的本地证据文件。
