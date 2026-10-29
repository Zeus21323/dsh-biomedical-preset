---
name: variant-pathogenicity-acmg
description: |
  Germline variant pathogenicity interpretation under the ACMG/AMP 2015 framework,
  with ClinGen SVI refinements: full PVS1–BP7 evidence-code table, PVS1 decision tree
  with strength downgrades, official criteria-combination rules, BA1/BS1/PM2 frequency
  handling, calibrated PP3/BP4 thresholds, de novo and co-segregation point systems,
  and VUS reporting wording. 中文触发词：ACMG 分级、致病性判读、变异解读、VUS、PVS1、
  临床意义、variant classification、致病性变异、意义未明变异、证据码。
category: omics
tags: acmg, variant-interpretation, clinical-genetics, vus
---

# 变异致病性判读与 ACMG/AMP 分级

基于 ACMG/AMP 2015 原始标准（Richards et al., *Genet Med* 2015;17:405-424）与 ClinGen Sequence
Variant Interpretation (SVI) 工作组的逐条细化建议，对胚系单核苷酸变异与小插入缺失做五级分类：
Pathogenic / Likely Pathogenic / VUS / Likely Benign / Benign。

## 使用边界（先读，避免误用框架）

| 场景 | 本技能是否适用 | 应改用 |
|---|---|---|
| 胚系、Mendelian 疾病的 SNV / 小 indel | 适用 | — |
| 肿瘤体细胞变异 | 不适用 | AMP/ASCO/CAP 体细胞分级（另立规范） |
| 拷贝数变异（CNV）/ 结构变异 | 不适用 | ClinGen CNV 解释技术标准（另立规范） |
| 非编码区 / 深内含子 / 调控区变异 | 部分适用 | Ellingford et al. 2022 非编码区建议（`references/official-docs.md` S-11） |
| 线粒体变异、药物基因组、多基因风险评分 | 不适用 | 各自专门规范 |

ACMG/AMP 2015 原文限定其适用范围为 Mendelian 疾病，并要求"所有致病性断言（包括 likely
pathogenic）都必须连同疾病与遗传方式一起报告"。**本技能输出的是判读建议，不是诊断结论；
最终报告须由具备资质的临床分子遗传学人员签发。**

## Quick Start

收到变异判读请求时，先判断属于哪类任务：

1. **整条变异判读**（给基因 + HGVS + 表型）→ 走下方 7 步工作流，逐证据码落表，最后按组合规则判级。
2. **单证据码核查**（"这个 PVS1 该不该降级"、"REVEL 0.81 算 PP3 吗"）→ 直接查
   `references/criteria-table.md` 对应小节，引用官方出处回答，不自行给阈值。
3. **报告 / VUS 措辞** → 走 `references/reporting.md`。
4. **找数据**（ClinVar 记录、gnomAD 频率、剂量敏感性）→ 走下方"数据来源对接"。

### 必须先确认的输入

- 基因符号 + 参考转录本（RefSeq 或 MANE Select；ACMG/AMP 2015 要求报告中给出转录本）
- 变异的 HGVS 命名（g./c./p.）与基因组坐标、基因组版本（GRCh37 / GRCh38）
- 疾病与遗传方式（同一变异对不同疾病可给出不同分类）
- 患者表型（HPO 词条或表型摘要）——PP4 与 de novo 证据都依赖表型特异性

缺项时用 `[GENE]` `[TRANSCRIPT]` `[HGVS]` `[PHENOTYPE]` `[INHERITANCE]` 占位继续推进，并在结论中列出未确认项。

## 七步判读工作流

### 步骤 1：锚定基因—疾病关系与遗传方式
查 ClinGen Gene-Disease Validity（Definitive/Strong/Moderate/Limited）与遗传方式。PVS1 只在
"LoF 是该基因已知致病机制"时可用；ClinGen SVI PVS1 决策树还要求基因—疾病关系达到
Strong 或 Definitive 才能给到 PVS1 满强度。见 `references/criteria-table.md` §2。

### 步骤 2：选转录本、定变异类型
区分：无义 / 移码 / 经典 ±1,2 剪接 / 起始密码子 / 同义 / 错义 / 框内 indel / 终止密码子丢失 /
外显子级缺失或重复。类型决定后续能用哪些证据码（例如 PVS1 仅用于预测 null 的变异类型）。

### 步骤 3：群体频率（BA1 / BS1 / PM2）
按最高亚群频率（popmax）而非全局频率判断；BA1 有官方 0.05 阈值但允许基因特异性下调与排除列表，
BS1 **无官方数值阈值**，须与疾病发病率/外显率比较。三者互斥。见 `references/criteria-table.md` §3。

### 步骤 4：计算证据（PP3 / BP4）
只用经过校准的工具与区间；ACMG/AMP 2015 明确 PP3/BP4 各只能用一次、不得把多个算法当独立证据。
错义用 Pejaver 2022 的校准区间（如 REVEL）；剪接用 ClinGen SVI Splicing Subgroup 流程。
见 `references/criteria-table.md` §4。

### 步骤 5：功能、共分离、de novo、病例对照
PS3/BS3 按 Brnich 2020 四步框架评定测定法的临床有效性；PS2/PM6 按 SVI de novo 点数表；
PP1/BS4/PP4 按 Biesecker 2024 点数表（上限 +5 分）。见 `references/criteria-table.md` §5。

### 步骤 6：按官方组合规则判级
使用 ACMG/AMP 2015 Table 5 原文规则；SVI 增补的 `1 Very Strong + 1 Supporting → Likely
Pathogenic` 仅在说明来源时使用。也可用 Tavtigian 2020 点数法（PVS1=8、PS=4、PM=2、PP=1、
BA1=−8、BS=−4、BP=−1；Pathogenic ≥10、LP 6–9、VUS 0–5、LB −1–−6、Benign ≤−7）作为等价实现。
见 `references/criteria-table.md` §6。

### 步骤 7：写结论与证据表
输出分类 + 每条证据码的判定依据 + 数据集版本与访问日期 + 未满足/缺失证据 + VUS 的复核安排。
措辞模板见 `references/reporting.md`。

## 数据来源对接

| 需求 | 资源 | 路径 / 本包工具 |
|---|---|---|
| 已有分类、提交者、审阅等级 | ClinVar | `https://www.ncbi.nlm.nih.gov/clinvar/`；本包 MCP `variants_clinvar_search`（参数 `query`，如 `BRCA1 pathogenic`） |
| 群体频率、亚群频率、覆盖度 | gnomAD v4 | `https://gnomad.broadinstitute.org/`；本包 MCP `variants_gnomad_get_variant`（参数 `variant_id`，如 `1-55051215-G-GA`，`dataset` 默认 `gnomad_r4`） |
| 基因剂量敏感性（HI/TS） | ClinGen Dosage Sensitivity | `https://search.clinicalgenome.org/kb/gene-dosage`；全基因组 pHaplo/pTriplo 预测见 Collins et al. 2022（`references/official-docs.md` S-12） |
| 基因—疾病有效性、遗传方式 | ClinGen Gene-Disease Validity | `https://search.clinicalgenome.org/kb/gene-validity` |
| 位点特异性数据库 | LOVD | 总入口 `https://www.lovd.nl/`；共享实例检索 `https://databases.lovd.nl/shared/genes` |
| VCEP 规则细化（CSpec） | ClinGen CSpec Registry | `https://cspec.genome.network/cspec/ui/svi` |
| 专家判读结论与证据 | ClinGen Evidence Repository | `https://erepo.clinicalgenome.org/evrepo/` |
| 变异规范化 ID | ClinGen Allele Registry | `https://reg.clinicalgenome.org/` |
| 剪接预测 | SpliceAI Lookup | `https://spliceailookup.broadinstitute.org/` |

引用任何一条记录时都要写清版本与访问日期（gnomAD release、ClinVar 快照日期、MANE 版本），
因为分类会随数据更新而变化。

## 三条最常被违反的硬规则

1. **不要给原始文献里不存在的阈值。** BS1、PS4 之外的大多数规则在 2015 原文里只有定性表述；
   `references/criteria-table.md` §7 列出了"官方无量化阈值"的完整清单，遇到清单内的规则只能
   写"无统一阈值，须按疾病外显率/基因特异性规范处理"，或引用对应 VCEP 的 CSpec。
2. **PVS1 不是自动满强度。** 必须按 ClinGen SVI PVS1 决策树判断 NMD、外显子生物学相关性、
   蛋白截短比例（>10% / <10%）与基因—疾病证据强度。
3. **PM2 不得单独支撑致病结论。** SVI 已将其降为 Supporting，且 BA1/BS1/PM2 三者互斥。

## 目录结构

```
variant-pathogenicity-acmg/
├─ SKILL.md                     本文件：工作流、边界、数据对接
├─ references/
│  ├─ official-docs.md          全部规则来源、文献标识、URL 与访问核对结果
│  ├─ criteria-table.md         PVS1–BP7 全表、PVS1 决策树、组合规则、校准阈值
│  └─ reporting.md              VUS 处理、报告措辞、复核周期
└─ (无 scripts/)
```

**关于 `scripts/`：** 本技能不提供自建脚本。判级组合与点数换算逻辑已在
`references/criteria-table.md` 中以官方原文表格形式给出；ClinGen 官方提供的是 PDF 表格与
CSpec 在线工具（见 `official-docs.md`），没有需要随技能分发的官方可执行评分脚本。若用户需要
批量化，应由使用者基于本技能的规则表自行实现，并对实现结果做人工复核。

## 产出目录与验收清单

建议的判读工作目录（每个变异一份）：

```
interpretation/[GENE]_[c.HGVS]/
├─ 01.input.md             基因、转录本、HGVS、坐标、疾病、遗传方式、表型
├─ 02.evidence.tsv         证据码 / 判定 / 依据摘要 / 数据来源与版本 / 文献 ID
├─ 03.classification.md    分类结论 + 命中的组合规则（引 Table 5 条目号）
├─ 04.report.md            报告正文（措辞见 references/reporting.md）
└─ 05.recheck.md           VUS 或证据薄弱时的复核触发条件
```

验收清单（逐项勾选后才可交付）：

- [ ] 转录本（含版本）与基因组版本已写明
- [ ] 疾病与遗传方式已写明；跨疾病分别判级
- [ ] 每条证据码都能指回官方定义（`criteria-table.md` 行号/小节）与数据来源
- [ ] 频率用的是最高亚群频率，且注明 gnomAD 版本与访问日期
- [ ] PVS1 若使用，已判定 NMD 预测、外显子相关性、截短比例、基因—疾病证据等级
- [ ] PP3/BP4 使用的是校准区间，且各自只计一次
- [ ] 组合判级引用了 Table 5 原文条目；若用了 SVI 增补条目，已注明出处
- [ ] 未满足的证据码与缺失数据单独列出
- [ ] 分类为 VUS 时，已写明"不因临床急需而升级"与复核触发条件
- [ ] 全篇无自造阈值；无法量化处已标注"官方无量化阈值"

## 相关文件

- `references/official-docs.md` — 规则来源与文献 URL，含本次核对的访问结果与一处候选 PMID 勘误
- `references/criteria-table.md` — PVS1–BP7 全表：证据码 / 官方定义 / 前提 / 强度可调范围
- `references/reporting.md` — VUS 与报告措辞、复核周期
