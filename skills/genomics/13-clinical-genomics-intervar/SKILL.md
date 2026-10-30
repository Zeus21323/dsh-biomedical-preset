---
name: 13-clinical-genomics-intervar
description: 系统化的ACMG/AMP胚系变异分类，覆盖全部28条证据标准（PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-7），产出五级分类（致病/可能致病/意义不明/可能良性/良性）并附逐条证据溯源。适用于变异解读、VUS重分类、致病性评估。整合ClinVar、gnomAD、计算预测器、文献证据和基因机制上下文。
---
# ACMG 与 AMP 胚系变异分类（增强版）

## 核心原则

每条证据（PS、PM、PP为致病方向；BS、BP为良性方向）贡献加权证据片段。分类基于**所有激活证据的组合**，而非单一发现。不要过度依赖单一证据。

证据强度层级：PVS1（极强）> PS（强）> PM（中等）> PP（支持性）。良性侧：BA1（单独成立）> BS（强）> BP（支持性）。

**两个常见错误**：
1. 看到ClinVar"致病"记录就停止——应核查原始证据与审查状态，不能仅凭二手分类激活PP5/BP6
2. 因单个预测器显示"耐受"就判定良性——预测器不一致时PP3和BP4都不适用，这是中性证据而非良性证据

始终保守应用证据。当证据模糊时，保持该条标准未满足。为每条激活标准引用来源，便于临床医生审核推理。

**关键原则**：
1. **标准驱动** — 引用激活了哪些标准及理由
2. **保守应用** — 证据模糊时不升级标准强度
3. **基因感知** — 根据基因机制（LOF vs 功能获得）调整阈值
4. **群体校准** — 使用祖先特异性gnomAD频率，非仅全球AF
5. **透明化** — 展示每条标准的证据
6. **来源溯源** — 每条标准激活必须引用数据库/工具来源
7. **英语优先查询** — 工具调用始终使用英语术语；以用户语言回复

---

## 何时使用

- "用ACMG标准分类BRCA2 c.5946delT"
- "这个VUS致病吗？NM_000059.4:c.7397T>C"
- "对rs28897743应用ACMG指南"
- "CFTR p.Arg117His的致病性如何？"
- "TP53 R248W的ACMG分类"
- "评级这个变异：NM_000546.6:c.742C>T"

---

## Phase 0: 变异验证与归一化

错误的 HGVS 或转录本会级联影响所有下游标准，所以这一步必须先做、且必须做对。一个转录本选错的变异，会在错误的坐标上取到一套看起来完全正常的频率和预测分数，最终报告却是错的 —— 而且这种错误不会自己暴露出来，因为每一步都"成功了"。因此本阶段的目标不是走流程，而是确认"我手上这个变异，和数据库里那个变异，确实是同一个"。

**三个必须先确认的点**：

1. **转录本对不对**。同一个基因常有多个转录本，同一个基因组坐标在不同转录本上的编码位置不同。临床报告应统一使用 MANE Select，除非该基因有临床专家组指定的其它参考序列。如果用户给的是旧转录本，先转换再继续。
2. **变异描述合不合规**。HGVS 有严格的书写规则，"c.5946delT" 与 "c.5946del" 在某些语境下含义不同（前者暗示了被删除的碱基）。用工具校验而不是人眼判断。
3. **变异类型定没定**。类型决定了后面走哪条路：错义走 Phase 2 的预测器，无义和移码走 Phase 5 的 PVS1，同义走 BP7。类型判错会让整条分析走错分支。

**一个容易踩的坑**：带终止密码子的移码变异，其蛋白描述形如 `p.Ser1982ArgfsTer22`，同时含有移码标记（fs）和终止标记（Ter）。如果按"含有 Ter 就是无义变异"来判断，就会把移码误分类成无义。判断顺序必须是先看 `fs`，再看 `Ter`。本 Skill 调用的工具已修正此顺序，但人工核对时要留意同样的问题。

### 使用的MCP工具

**Variant_Interpretation MCP** (`variantvalidator_gene2transcripts`, `variantvalidator_validate`)：
```python
# 1. 获取 MANE Select 转录本
variantvalidator_gene2transcripts(gene_symbol="BRCA2")

# 2. 验证变异格式并获取基因组坐标
variantvalidator_validate(
    variant_description="NM_000059.4:c.5946delT",
    genome_build="GRCh38",
    select_transcripts="mane_select"
)
```

**记录内容**：
- HGVS 编码坐标、蛋白坐标、基因组坐标
- 变异类型（移码 / 错义 / 无义 / 剪接 / 同义 / 框内插入缺失）
- MANE Select 转录本编号

**接受的输入格式**：
- 编码 HGVS，例如 `NM_000059.4:c.5946delT`
- 蛋白 HGVS，例如 `BRCA2 p.Val600Glu`
- rsID，例如 `rs28897743`
- 基因加变化，例如 `BRCA1 c.68_69del`
- 基因组坐标，例如 `chr13:g.32398489del`

**如果验证失败怎么办**：不要猜测用户的意图然后继续。把工具给出的错误信息原样报告，并说明需要用户提供哪种形式的信息。继续往下做只会产出一份建立在错误坐标上的报告，比直接停下更危险。

---

## Phase 1: 群体频率证据（BA1, BS1, BS2, PM2）

群体等位基因频率（AF）是最强证据之一。任何群体中>5%的变异几乎肯定是良性（BA1 — 单独成立，无需进一步分析）。gnomAD中不存在支持致病性（PM2，ClinGen指导现通常应用为PM2_Supporting）。

使用祖先特异性AF，非仅全球频率。东亚群体8%但全球罕见的变异，在该祖先背景下为良性。BS1阈值依赖疾病患病率和遗传模式 — 常见病默认1%，罕见病0.1%。

### 使用的MCP工具

**Variants MCP** (`get_variant`, `gene_constraint`)：
```python
# 获取per-ancestry频率
get_variant(variant_id="13-32398489-AT-A", dataset="gnomad_r4")

# 获取基因约束指标
gene_constraint(gene_symbol="BRCA2")
# 返回: pLI, LOEUF, mis_z
```

**阈值参考**：
- BA1: AF > 0.05（任何群体）
- BS1: AF > 0.01（常见病）或 > 0.001（罕见病）
- PM2_Supporting: gnomAD中不存在或极低频（< 0.00001）

**基因约束指标**：
- pLI ≥ 0.9 或 LOEUF ≤ 0.35：LOF不耐受
- mis_z > 3.09：missense约束（支持PP2）
- mis_z < 3.09 且仅LOF致病：支持BP1

---

## Phase 2: 计算预测证据（PP3, BP4）

**不要用"多个预测器投票"。** ClinGen SVI 的建议是：使用**经过校准的单一工具、校准阈值和对应的证据强度**（Pejaver et al. 2022, AJHG 109:2163；PMC9748256）。理由有二：

1. 未校准工具的"界值"是开发者自定的分类边界，不是 ACMG 证据强度。例如 M-CAP 的开发者界值 0.025 表示"可能致病"，但按 ACMG 校准它在任何分数都达不到 PP3 —— 把 0.025 或 0.5 当阈值用会产生错误证据。
2. 多个预测器之间高度相关。REVEL 本身就是 SIFT、PolyPhen-2 等 13 个分数的集成，把 REVEL 和 PolyPhen 当作两条独立证据是同一份证据计数两次。累加只会凭空造出强度。

**PP3 与 BP4 互斥**，由主预测器（默认 REVEL）判定，不叠加多个工具的结果。

### 校准阈值（Pejaver et al. 2022）

| 工具 | PP3 支持 | PP3 中等 | PP3 强 | BP4 支持 | BP4 中等 | BP4 强 |
|------|---------|---------|--------|---------|---------|--------|
| REVEL | ≥0.644 | ≥0.773 | ≥0.932 | ≤0.290 | ≤0.183 | ≤0.016 |
| BayesDel (no-AF) | ≥0.13 | ≥0.27 | ≥0.50 | ≤−0.18 | ≤−0.36 | — |
| MutPred2 | ≥0.737 | ≥0.829 | ≥0.932 | ≤0.391 | ≤0.197 | ≤0.010 |
| VEST4 | ≥0.764 | ≥0.861 | ≥0.965 | ≤0.449 | ≤0.302 | — |
| CADD PHRED | ≥25.3 | ≥28.1 | — | ≤22.7 | ≤17.3 | ≤0.15 |
| PrimateAI | ≥0.790 | ≥0.867 | — | ≤0.483 | ≤0.362 | — |

**区间之间的分数是刻意的中性区**：例如 REVEL 0.290–0.644 既不支持致病也不支持良性，此时 PP3 与 BP4 **都不适用** —— 这是中性证据，不是良性证据。

**未校准的工具**（AlphaMissense、MetaRNN、MetaLR、ClinPred、SIFT、PolyPhen-2、M-CAP、MutationTaster、FATHMM、PROVEAN、LRT、DANN、Eigen）**不产生 PP3/BP4 证据**。工具仍会返回它们的分数供人工参考，但不要据此激活标准。特别注意 AlphaMissense 的开发者界值 0.564：Bergquist et al. 2025 (Genet Med 27:101402) 校准后该界值连"支持"级都达不到。

**仅适用于missense变异**。同义变异、无义变异、移码变异、剪接变异的致病性不靠这些打分器判断，应走 Phase 5 的规则，或走 BP7 的同义变异判定。

### 为什么必须用校准阈值

2015 年的 ACMG/AMP 原文只允许预测器作为最低一档的"支持性"证据，并且含糊地要求"多个算法一致"，没有给出数量依据。Pejaver 等人在 2022 年用贝叶斯框架把这个模糊要求量化了：先算出每条证据强度对应的似然比，再用局部阳性预测值把每个工具的原始分数映射到具体的证据强度区间。所谓"局部"是指区间内**任意**一个分数都满足该强度，而不是平均意义上满足 —— 这对临床报告很重要，因为你要为一个具体分数负责，不能拿群体平均来担保。

这套校准揭示了一个反直觉的结论：**打分器的开发者界值几乎都不能直接当 ACMG 阈值用**。开发者的界值是为了在某个数据集上最大化准确率，而 ACMG 要的是"这个分数对应多强的致病证据"，两者不是一回事。所以看到某个工具文档写着"大于 0.5 判为有害"，不能据此激活 PP3；必须查该工具是否进入过 ClinGen 的校准表，以及它的分数落在哪个区间。

### 如何选择校准工具

ClinGen 的建议是**预先指定单一工具**，而不是每次挑一个分数最好看的。理由是这样能控制住整体的假阳性率：如果允许在六个工具里挑一个达到最强证据的，那么只要有一个工具"碰巧"偏高就能拿到强证据，这与校准时的设想不符。

实践中的选择原则：

1. **主预测器固定**。默认用 REVEL（可达 PP3_Strong / BP4_VeryStrong）。若实验室口径要求用其它工具，需在 MCP 配置中统一设置 `VARIANT_INTERPRETATION_PRIMARY_PREDICTOR`，而不是按变异临时挑最有利的那个 —— 后者会抬高假阳性率。
2. **多转录本必须指定目标**。dbNSFP 的分数数组按转录本对齐；未指定目标时不取"第一个值"，避免把其它转录本的分数当成目标转录本的。调用 `predict_variant_effect` 时传 `transcript_id`。
3. **BayesDel 只用 no-AF 子分数**。`bayesdel.add_af` 是另一个模型的输出，不得与 no-AF 混用。
4. **报告里写明用了哪个工具、哪个阈值、什么版本**。审阅者需要能复现这个判定。

### 各强度区间的含义与写法

| 证据 | 强度 | 点数 | 什么时候能用 |
|------|------|------|--------------|
| PP3 | 支持 | +1 | 分数刚过支持线，只够作为一条弱证据 |
| PP3 | 中等 | +2 | 分数明显偏向致病，可与其他中等证据并列 |
| PP3 | 强 | +4 | 分数接近该工具的极端值，属最强单条计算证据 |
| BP4 | 支持 | −1 | 分数刚过良性线 |
| BP4 | 中等 | −2 | 分数明显偏向良性 |

三个上限必须记住：

1. **PP3 最高到"强"，BP4 最高到"中等"**。没有任何预测器能单独给出"极强"级的致病或良性证据。任何声称某个打分器可以单独定案的用法都是错的。
2. **PP3 与 PM1 合计不得超过"强"**。热点结构域证据（PM1）与计算预测证据（PP3）常常反映同一件事 —— 变异落在一个重要区域且改变了重要残基 —— 把它们各自满额相加会重复计数。
3. **PP3 与 BP4 互斥**。校准区间本身是互补的，一个分数不可能同时落进致病区间和良性区间。

### 常见误用

- **把其它工具的高分当作"第二条证据"**。PP3/BP4 只由主预测器决定，其它校准工具的结果供复核用，不叠加。
- **多转录本时取"第一个值"**。分数数组按转录本对齐，必须指定目标转录本；否则可能把其它转录本的分数当成目标转录本的。
- **用未校准工具补齐结论**。例如 REVEL 落在中性区间，就想用 AlphaMissense 的高分来支持致病。AlphaMissense 的开发者界值 0.564 经 Bergquist 等人 2025 年校准后连"支持"级都达不到，不能作为 PP3 依据。
- **把中性区间当成良性**。分数落在致病线和良性线之间时，PP3 和 BP4 都不适用。这是"没有证据"，不是"良性证据"。写成 BP4 会低估致病可能。
- **对非错义变异用这套阈值**。剪接变异请用 SpliceAI，同义变异请用 BP7 的规则，无义和移码请用 PVS1 的规则。
- **忽略基因特异规范**。不少 VCEP 对本基因的预测器使用有额外限制，先查规范再用阈值。

### 在报告中如何表述

推荐把判定过程写清楚，而不是只给结论。例如：

```text
PP3（中等，+2）：REVEL = 0.81，达到 Pejaver 等 2022 年校准的中等级阈值（≥0.773）。
同一变异上 CADD PHRED = 31 亦达支持级，BayesDel 未达阈值；
按 ClinGen 建议采用单一工具 REVEL，不叠加。AlphaMissense = 0.92 未经校准，仅供参考。
```

这样的写法有三个好处：审阅者能核对阈值来源；读者知道为什么只有一条证据而不是三条；换人复核时能复现。

### 使用的MCP工具

**Variant_Interpretation MCP** (`predict_variant_effect`)：
```python
# 获取 REVEL、CADD、AlphaMissense、SIFT、PolyPhen2、MetaRNN 等预测分数
# 同时返回 SpliceAI delta 分数（供 Phase 5 使用）
predict_variant_effect(
    variant_id="NM_000059.4:c.7007G>T",  # 转录本HGVS / rsID / 基因组HGVS 均可
    gene_symbol="BRCA2",                  # 可选，用于多转录本时筛选
    transcript_id="NM_000059.4",          # ⚠️ 多转录本时必须指定目标转录本
                                           # 避免取到其它转录本的分数
)
# 返回：
#   predictors:          {revel: 0.397, cadd: 23.0, alphamissense: 0.101, ...}
#   calibrated_calls:    [{predictor, score, direction, strength}, ...]  # 已达阈值的校准工具
#   uncalibrated_predictors: [alphamissense, sift, ...]  # 仅供参考，不产生证据
#   concordance:         {predictors_evaluated, predictors_meeting_threshold, discordant}
#   acmg_suggestion:     {pp3, bp4, strength, predictor, reasoning, warning?}
#   spliceai:            {DS_AG, DS_AL, DS_DG, DS_DL, max_delta, ...}
```

**工具已按校准阈值完成判定**，`acmg_suggestion` 可直接采用：
- `pp3: true` / `bp4: true` 时，`strength` 给出该证据的强度（Supporting/Moderate/Strong），`predictor` 指明是哪个工具产生的
- `pp3` 与 `bp4` 均为 false 且 `strength` 为 null 时，说明没有任何校准工具达到阈值 —— PP3/BP4 都不适用，**不要**因此激活 BP4
- `warning` 字段存在时表示校准工具之间方向不一致，需人工复核
- 强度上限受 ClinGen 约束：PP3 最高 Strong（+4），BP4 最高 Moderate（−2）

**数据来源**（均为公开免费接口，无需 API key）：
- myvariant.info — REVEL、CADD、AlphaMissense、SIFT、PolyPhen2、MetaRNN 等
- Ensembl VEP REST — SpliceAI 四个 delta 分数

**变异身份校验**：工具会校验 myvariant 返回的记录确实属于请求的变异（基因一致、编码 HGVS 一致）。若返回的是其它基因或其它转录本的记录，`errors` 会说明原因且**不给出预测分数** —— 此时不要改用其它工具补足，应报告该变异无法评估 PP3/BP4。


**Variant_Interpretation MCP** (`esm_explain_variant_mechanism`)：
```python
# 机制解释：需要在已核实端点配置 ESM 凭据后使用
esm_explain_variant_mechanism(
    sequence="MTEYKLVVV...",   # 完整蛋白序列（标准氨基酸单字母）
    position=12,                # 1-based 位置
    ref_aa="G",                 # 必须与序列该位置的实际残基一致
    alt_aa="V",
)
```

**返回与用法**：

- `status`：`ok` 或 `failed`。**`failed` 时不得当作"分析成功"**，`error_kind` 会说明原因（`not_configured` 未配凭据 / `endpoint_not_verified` 端点未核实 / `invalid_input` 输入不自洽 / `permission_denied` 无权限 / `rate_limited` 限流或额度不足 / `request_failed` 超时或网络失败 / `invalid_response` 返回结构异常）。这类情况在报告中写"未评估"，不要补一个 0。
- `variant_effect`：`masked_marginal_llr`（掩码边际对数似然比）与 `ref_rank_of_20`。这是**计算推断**，反映该突变在蛋白语言模型下的合理性变化，不是致病性判定。
- `reference_context_features`：参考序列在 ESM Atlas 中覆盖该位置的 SAE 特征（`label`、`description`、激活值），用于机制叙述。序列未收录于 Atlas 时该列表为空，`atlas.note` 会说明，**不要杜撰特征描述**。
- `sae_comparison.available`：当前为 `false`。本实现尚未请求 ESMC SAE 激活并比较参考与突变序列；这是本实现的限制，不是托管 API 的能力限制。官方 ESMC logits 支持 SAE 特征，见 [Biohub 文档](https://docs.biohub.ai/api/protein/models/logits)。
- `caveats`：注明本结果是计算推断，不构成实验机制证据。

**关键约束**：ESM 结果**不改变** PP3/BP4 的证据强度（那由 ClinGen 校准阈值决定），也不能作为 PS3/BS3 的功能证据。只有真正做过功能实验的数据才能激活 PS3/BS3。工具会校验序列长度、位置范围与 `ref_aa` 是否与序列实际残基一致；不一致时直接失败而不发请求。

**未核实端点的保护**：服务只向已核实的官方端点发送凭据。若 `ESM_URL` 被改为清单外的地址，调用会返回 `endpoint_not_verified` 且不发请求。

**预测器整合**：
- **主预测器**（固定为 REVEL，可用 `VARIANT_INTERPRETATION_PRIMARY_PREDICTOR` 按实验室口径统一更换）决定 PP3/BP4
- 其余校准工具（BayesDel no-AF、MutPred2、VEST4、CADD、PrimateAI）的判定一并返回供人工复核，但**不计入证据**
- SpliceAI delta scores（Phase 5 使用）
- 未校准工具的原始分数（仅供参考，不产生证据）

**机制补充说明**：
PP3/BP4的校准强度告诉你变异**是否**有害，但不解释**如何**有害。对于需要机制解释的VUS解读报告（临床医生问"为什么有害？"），可以调用 `esm_explain_variant_mechanism`：它用 ESM3 掩码边际打分给出该突变在蛋白语言模型下的合理性变化，并从 ESM Atlas 取参考序列在该位置附近的 SAE 特征描述，把"PP3满足（REVEL 0.81）"补成"PP3满足 — 该位置属于 X 结构域特征区，突变为丙氨酸后模型合理性显著下降"。

三个必须守住的边界：

1. **这是计算推断，不是实验证据**。它不能激活 PS3/BS3 —— 那需要真正的功能实验数据。
2. **它不改变 PP3 的强度**。PP3 强度只由 ClinGen 校准阈值决定。
3. **SAE 特征只描述参考序列，不做突变前后对比**。当前代码没有实现 ESMC SAE 激活差异计算。报告里不要把"参考序列有某特征"写成"突变导致该特征丢失"。

仅限错义变异。工具返回 `status: failed` 时按"未评估"处理，不要补零或改用其它工具凑出结论。

---

## Phase 3: 临床数据库证据（PS1, PM5, PP5, BP6）

ClinVar汇总临床实验室分类。推理逻辑：如果相同氨基酸变化（不同核苷酸）已确立致病，这是强证据（PS1），因为机制是氨基酸改变。如果同一残基不同致病missense，这是中等证据（PM5） — 该残基功能上重要。

**注意：ClinGen SVI 工作组建议停止使用 PP5/BP6**。这些证据依赖 ClinVar 中其他实验室的分类，而非原始证据。应评估 ClinVar 记录中引用的原始证据（功能研究、分离数据、家系共分离等），并应用相应的 ACMG 证据代码（如 PS3/BS3 用于功能研究，PP1/BS4 用于共分离）。参考：[ClinGen SVI recommendation (PMC6709533)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6709533/)

**如果必须使用 PP5/BP6（仅用于历史对比）**：
- PP5 适用条件：ClinVar 显示致病且 ≥2 星审查（提供标准，多个提交者）
- ClinVar 冲突解读意味着 PP5 和 BP6 都不应应用
- 按一致提交者数量加权
- 现代实践中应降级为支持性证据

### 使用的MCP工具

**Variants MCP** (`clinvar_search`, `clinvar_get_records`)：
```python
# 搜索ClinVar记录
clinvar_search(query="BRCA2 c.5946delT", max_records=50)

# 获取详细信息（批量获取 VCV/RCV/variation ID）
clinvar_get_records(accessions=["VCV000012345", "RCV000067890"])
```

**Clinical_Genomics MCP** (`clingen_gene_validity`, `clingen_actionability`, `civic_search_variants`)：
```python
# ClinGen 基因-疾病有效性（PM1/PP2/BP1 的机制前提）
clingen_gene_validity(gene="BRCA2")
# 返回该基因-疾病关系的有效性分级与 LOF 是否为已知机制

clingen_actionability(gene="BRCA2", context="both")

# CIViC 临床证据
civic_search_variants(query="BRCA2 c.5946delT")
```

**ClinVar审查星级**：
- 0星：无提交标准
- 1星：单个提交者，提供标准
- 2星：多个提交者，提供标准
- 3星+：专家组审查

---

## Phase 4: 功能结构域与蛋白分析（PM1, PP2, BP1）

已确立功能结构域中的变异（已知致病变异富集）更可能致病。**PM1（中等致病）**要求变异位于hotspot结构域且良性变异率低 — 使用InterPro结构域架构和UniProt活性/结合位点评估。

**PP2和BP1互斥**：
- **PP2（支持致病）**：missense变异位于已知missense致病机制基因且良性missense率低（mis_z > 3.09）
- **BP1（支持良性）**：missense变异位于仅截短变异致病基因（LOF-only机制） — 此类基因的missense不太可能致病

### 使用的MCP工具

**Protein_Annotation MCP** (`get_domain_architecture`, `get_interpro_entry`)：
```python
# InterPro/UniProt 结构域架构（PM1 hotspot 判定）
get_domain_architecture(accessions=["P51587"])
get_interpro_entry(accession="IPR015525")
```

**Structures&Interactions MCP** (`alphafold_check_coverage`)：
```python
# AlphaFold 结构覆盖度（pLDDT 高 = 结构化区域）
alphafold_check_coverage(accessions=["P51587"])
```

**Variants MCP** (`gene_constraint`)：
```python
# 基因约束指标（用于PP2/BP1判定）
gene_constraint(gene_symbol="BRCA2")
# 返回: pLI, LOEUF, mis_z
# mis_z > 3.09: 应用PP2
# mis_z < 3.09 且pLI > 0.9: 应用BP1（仅LOF基因）
```

---

## Phase 5: LOF与剪接影响评估（PVS1）

**PVS1是最强单一致病标准**。基因中null变异（nonsense/frameshift/canonical splice/起始密码子）且LOF为已确立机制可激活PVS1，但完整强度取决于上下文。

### PVS1全强度条件

1. null变异类型确认
2. LOF为已知机制
3. **不在**末位外显子或倒数第二外显子末50bp
4. **无** rescue转录本存在

### 降级规则

- **PVS1_Moderate**：末位外显子或NMD逃逸可能
- **PVS1_Supporting**：可能有rescue转录本或SpliceAI ≥ 0.5但非canonical剪接位点
- **不满足**：LOF机制不确定

### 使用的MCP工具

**第一步：确认LOF是致病机制**（Clinical_Genomics MCP）。这是PVS1的前提，不能用pLI/LOEUF代替：
```python
clingen_dosage_sensitivity(gene="BRCA2")
# haploinsufficiency = 3 → lof_mechanism="established"
clingen_gene_validity(gene="BRCA2")
# 确认基因-疾病关系有效，并查看机制描述
```
- 单倍剂量不足评分为3，或有多个已报道的致病LOF变异：记为“已确认”，并写明依据来源
- 致病机制为功能获得或显性负效应：记为“非LOF机制”
- 无法确认（评分为0、1、2、30、40，没有策展记录，或证据不足）：保持默认的“未确认”。此时工具不给PVS1，报告中写明“LOF机制未确认，PVS1未应用”；工具给出的可能强度只供人工复核参考

**第二步：变异层面分级**（Variant_Interpretation MCP）：
```python
autopvs1_classify(
    gene="BRCA2",
    transcript="NM_000059.4",
    variant_type="frameshift",  # nonsense/frameshift/canonical_splice/initiation_codon
    exon_number=10,
    total_exons=27,
    nmd_escape=False,
    rescue_transcript=False,
    pli=1.0,                    # 来自 Phase 4 的基因约束查询，仅作参考
    loeuf=0.15,
    lof_mechanism="established",
    lof_mechanism_source="ClinGen HI 3",
)
# 机制未确认时，结果另含“可能强度”和“需要补充的操作”两项，均不可直接采用
```

基因约束指标复用 Phase 4 的查询结果。它只反映人群中的选择压力，既不能确认也不能否定LOF致病机制；隐性病基因（如囊性纤维化相关基因）的约束值常常很低，但LOF仍然是致病机制，因此不能因约束低而放弃PVS1，也不能因约束高而直接给出PVS1。

**当前辅助分级分支**：本实现不能替代完整的 [Abou Tayoun et al. 2018 决策树（PMID 30192042）](https://pubmed.ncbi.nlm.nih.gov/30192042/) 或基因特异 VCEP 规范。

1. **起始密码子丢失**：当前策略返回 PVS1_Moderate 或经 rescue 因素进一步降级的候选结果，不直接给全强度。原文还要求评估替代功能性转录本、下游起始位点与其上游已知致病变异；补齐这些依据前，不自动采用候选强度。
2. **经典剪接位点**：保留读框 → PVS1_Moderate；破坏读框 → 等同 null，继续走 NMD 分支。未提供读框信息时取 PVS1_Moderate。
3. **NMD 逃逸与截去区域**：末位外显子本身就意味着逃逸 NMD（不重复计数）。逃逸时按截去区域是否含关键功能域、是否 >10% 蛋白质判断（PVS1_Strong 或 PVS1_Moderate）；两项都未提供时保守取 PVS1_Moderate。
4. **Rescue transcript**：在上述结果基础上降一档。

工具的额外参数 `removes_critical_region`、`truncation_fraction`、`alternative_start_codon`、`in_frame` 对应上述分支；未提供时按保守方向判定，并在 `reasoning` 中说明缺失的信息。

**剪接预测**（同一工具，复用 Phase 2 的调用结果）：
```python
predict_variant_effect(
    variant_id="NM_000059.4:c.7977+100A>G",
    gene_symbol="BRCA2",
)
# 返回 spliceai 字段：{DS_AG, DS_AL, DS_DG, DS_DL, DP_AG, DP_AL, DP_DG, DP_DL, max_delta}
# 工具同时给出：
#   bp7_suggestion   — 同义变异且 max_delta < 0.1 时自动判定
#   splice_impact    — max_delta >= 0.5 时提示可能的剪接影响
```

**判读阈值**：
- `max_delta`（四个 DS 值取最大）≥ 0.5：提示预测的剪接影响，不能仅凭该分数激活 PVS1；需评估实际转录本后果、LOF 机制及适用的剪接规范。
- 四个 DS 分量齐备且 `max_delta` < 0.1：未预测到明显剪接影响；仅在满足同义变异等适用条件时评估 BP7，不能表述为实验确认无影响。
- canonical splice sites：c.位置+1/+2 (donor) 或 c.位置-1/-2 (acceptor)

**起始密码子变异的保守判定**：
起始密码子（ATG）缺失或改变时，按**保守策略**判定为 **PVS1_Moderate** 而非 PVS1，即使无证据显示存在替代起始密码子。理由：
1. 部分基因存在下游替代起始密码子，可产生功能性截短蛋白
2. 某些转录本的注释起始密码子可能不是生物学真实起始位点
3. 5' UTR 区域的翻译起始复杂性高于简单的 ATG 识别模型

以上是当前实现的有限参数策略，不等于 ClinGen 原文的完整起始丢失规则。若替代功能性转录本可保留功能，通用指南可能要求不应用 PVS1；其它情形还需下游起始位点及其上游致病变异证据。候选结果必须按病种和基因规范复核后才能采用。

**注意**：SpliceAI 需要转录本级 HGVS（带 NM_ 或 ENST 前缀）。若传入 rsID 或基因组 HGVS，工具会尝试用 myvariant 返回的 Ensembl 转录本自动构造查询；若无法构造，`errors` 字段会说明原因，此时剪接证据应标记为**未评估**。

**"未评估"不等于"无影响"，这个区别关系到结论对错。** 剪接证据缺失时，不能默认该变异没有剪接影响。差别在于：一个同义变异如果 SpliceAI 给出低分，可以据此应用 BP7；但如果 SpliceAI 根本没跑出结果，就没有依据说它无害，此时 BP7 不适用，而该变异可能仍有未被识别的剪接效应。本 Skill 调用的工具在下列情况都会拒绝给出剪接判定，并说明原因：

1. **VEP 没有返回任何转录本**，或返回的转录本都不属于目标基因 —— 例如指定了 BRCA2 却只返回了别的基因的转录本。这时不能借用其它基因的分数。
2. **SpliceAI 的分数字段全部缺失**。这不是"四个 delta 都等于零"，而是"SpliceAI 没有提供预测"。把缺失当零会凭空造出"无剪接影响"的结论并错误激活 BP7。
3. **只返回了部分 delta 分量**。此时 BP7 返回 `false`、`status: not_evaluated`，并列出缺失分量；不能把部分低分当成四个分量均低。

**判断顺序也很重要**：先确认剪接证据是否评估过，再决定是否应用 BP7。顺序颠倒会得到一个看似合理、实则无依据的良性判定。

---

## Phase 6: 文献与功能证据（PS3, BS3, PP1, PP4）

设计良好的功能检测显示LOF（PS3）或正常功能（BS3）可决定性改变分类。PS3/BS3可因检测严谨性不足降级（如PS3_Supporting）。并非所有功能检测合格 — ClinGen基因特异性指导定义有效检测。

**PP1（共分离）**：≥7个信息性减数分裂时升级为PP1_Strong
**PP4**：患者表型高度特异于基因疾病时适用

### 使用的MCP工具

**PubMed MCP** (`search_articles`, `get_full_text_article`)：
```python
# 功能检测文献
search_articles(
    query="BRCA2 c.5946delT functional assay",
    max_results=10
)

# 共分离文献
search_articles(
    query="BRCA2 c.5946delT segregation family",
    max_results=5
)

# 获取全文（用于详细证据提取）
get_full_text_article(article_id="12345678")
```

### 无法自动评估的标准

需要临床数据的标准（PS2, PS4, PM3, PM6, BS4, BP2, BP5）**无法自动评估**。记录为"未评估"，除非用户提供临床背景。

**可部分评估**：
- PM4（非重复区蛋白长度变化）和BP3（重复区in-frame indel）— 从变异类型判断
- BP7（同义变异，无剪接影响）— 通过 SpliceAI 四个 DS 分量**齐备**且最大 < 0.1 评估。只返回部分分量时不给 BP7（缺失的分量可能正是高分的那一个），记为"未评估"。

---

## 分类算法

按应用强度（升级/降级后）组合证据：

**使用这些组合规则之前，先把每条证据的强度定下来。** 组合规则本身只是算术，出错往往出在把某条证据的强度定高了。三件事最容易出错：把支持性证据当中等证据用；同一份事实在两条标准里各算一次；以及忽略 ClinGen 对本基因的降级规定。定强度时如果犹豫，选低的那一档 —— 低估强度只是让分类更保守，高估强度会直接改变结论。

**为什么组合规则长这样。** 这套规则来自 2015 年 ACMG/AMP 原文的贝叶斯解释：每一条证据对应一个似然比，"致病"要求后验概率达到约 99%，"可能致病"要求约 90%。原文没有写成概率，而是给了一张组合表，表里的每一条都等价于某个概率阈值。所以"PVS1 + 1 个中等"够"可能致病"、"PVS1 + 2 个中等"才够"致病"这类不对称，不是任意规定的，而是概率换算的结果。理解这一点有助于处理规则没覆盖的组合：如果某个组合不在表里，可以按它对应的总似然比去判断，而不是硬套最接近的一条。

### 致病（Pathogenic）

1. PVS1 + ≥1 强
2. PVS1 + ≥2 中等
3. PVS1 + 1 中等 + 1 支持
4. PVS1 + ≥2 支持
5. ≥2 强
6. 1 强 + ≥3 中等
7. 1 强 + 2 中等 + ≥2 支持
8. 1 强 + 1 中等 + ≥4 支持

### 可能致病（Likely Pathogenic）

1. PVS1 + 1 中等
2. 1 强 + 1 至 2 个中等
3. 1 强 + ≥2 支持
4. ≥3 中等
5. 2 中等 + ≥2 支持
6. 1 中等 + ≥4 支持

### 良性（Benign）

1. BA1 单独成立
2. ≥2 条强良性证据

### 可能良性（Likely Benign）

1. 1 强良性 + 1 支持良性
2. ≥2 条支持良性证据

### 意义不明（VUS）

标准不满足上述任何阈值，**或**致病与良性证据并存且无法调和。

**"冲突"与"证据不足"要区分开。** 两者都归为 VUS，但含义完全不同：证据不足说明现有数据不够，需要补充功能实验、家系或病例数据；证据冲突则说明已有数据内部矛盾，可能是数据质量问题（例如某个频率估计不可靠），也可能是这个变异确实处于中间状态。报告里写清楚是哪一种，后续处理方式不一样 —— 前者是"继续收集"，后者是"查证矛盾来源"。VUS 不是终点，报告里应给出再评估的触发条件，例如"若出现功能实验数据，按 PS3 重新评估"。

---

## 输出格式

```markdown
# ACMG变异分类报告

## 变异：[HGVS]
- **基因**：[符号] | **转录本**：[MANE Select] | **蛋白**：[p.notation] | **类型**：[变异类型]

## 分类：[致病 / 可能致病 / 意义不明 / 可能良性 / 良性]

## 证据总结

### 满足的致病标准
| 标准 | 强度 | 证据 | 来源 |
|------|------|------|------|
| PVS1 | Very Strong | Frameshift in LOF-intolerant gene | Variant_Interpretation MCP + gnomAD |
| PM2 | Supporting | Absent from gnomAD | Variants MCP (gnomAD r4) |

### 满足的良性标准
| 标准 | 强度 | 证据 | 来源 |
|------|------|------|------|
| （无） | | | |

### 关键未满足标准（附理由）
- PP3: 预测器不一致（REVEL 0.45, CADD 22）

### 未评估标准（及原因）
- PS2, PS4, PM3, PM6, BS4, BP2, BP5: 需要临床数据（患者表型、家族共分离、反式变异等）
- PS3/BS3: 未找到该变异的功能实验文献
- PP1/BS4: 缺乏家系共分离数据

**重要**：未评估的标准保持"未评估"状态，**不编造证据**，不补零分，不用"可能"或"推测"填充。缺失证据是正常的临床现实，应如实报告。

## 详细证据

**群体频率**：
- gnomAD AF: 0 / 0（不存在于任何群体）
- 基因约束：pLI=1.0, LOEUF=0.15, mis_z=5.2

**计算预测**：
- 主预测器 REVEL: 0.78 → 达 PP3_Moderate 阈值（≥0.773）
- 其它校准工具（供复核）：CADD 26 → PP3_Supporting（≥25.3），MutPred2 0.82 → PP3_Moderate
- 未校准工具（仅供参考）：AlphaMissense 0.85
- **证据判定：PP3_Moderate**（只由主预测器决定）

**临床数据库**：
- ClinVar: Pathogenic (2星审查, 5个一致提交者)
  - **不使用 PP5**：遵循 ClinGen SVI 建议，评估 ClinVar 记录引用的原始证据
  - 若记录引用功能研究，应作为 PS3/BS3 评估
- CIViC: 1条证据（BRCA2 LOF与乳腺癌关联）

**结构域**：
- InterPro: 位于DNA修复结构域（IPR015525）
- AlphaFold pLDDT: 92（高置信度结构化区域）

**剪接**：
- SpliceAI: AG=0.01, AL=0.02, DG=0.03, DL=0.02（无剪接影响）

**文献**：
- PMID 12345678: 功能检测显示同源重组缺陷（PS3）

**ESM 机制解释**：
- 状态: 未评估（ESM_API_KEY 未配置或端点未验证）
- **重要**：ESM 失败时保持"未评估"，不编造分数或改用其它工具补足

## 分类逻辑
应用规则：PVS1 + PS3 + PM2_Supporting = 致病（P规则1）

## 局限性
### 未评估标准（需要额外数据）
- **PS2, PS4, PM3, PM6, BS4, BP2, BP5**: 需要临床数据（患者表型特异性、家族共分离、反式变异、病例对照统计）
- **PP1/BS4**: 缺乏家系共分离数据
- **PS3/BS3**: 需要该变异的功能实验文献（若 ClinVar 引用了功能研究，应提取为 PS3）

### 数据可获得性说明
- 群体频率、计算预测、结构域、剪接预测均可自动评估
- 功能实验、共分离、临床表型需要人工提供或文献查证
- **未评估不等于不存在**：缺失证据如实报告，不编造或补零
```

---

## 常见模式

### 模式1：已知致病frameshift
**输入**："分类BRCA2 c.5946delT"

Phase 0（验证）→ Phase 1（gnomAD不存在, PM2_Supporting）→ Phase 3（ClinVar致病，按 SVI 建议改用其引用的原始证据）→ Phase 4（DNA修复结构域, PM1）→ Phase 5（frameshift + LOF基因, PVS1）→ Phase 6（文献PS3）

**结果**：**致病**（PVS1 + PS3 + PM1 + PM2_Supporting）

### 模式2：Missense VUS
**输入**："BRCA1 p.Arg1699Gln致病吗？"

Phase 0 → Phase 1（罕见, PM2_Supporting）→ Phase 2（REVEL 0.82, CADD 26, PP3）→ Phase 3（ClinVar VUS）→ Phase 4（BRCT结构域, PM1）→ Phase 6（活性降低, PS3_Moderate）

**结果**：**可能致病**（PS3_Moderate + PM1 + PM2_Supporting + PP3）

### 模式3：常见良性变异
**输入**："rs1800497的ACMG分类"

Phase 1（gnomAD AF=0.21, BA1）→ 短路

**结果**：**良性**（BA1单独成立）

### 模式4：深内含子变异
**输入**："分类NM_000059.4:c.7977+100A>G"

Phase 1（检查AF）→ Phase 5（SpliceAI < 0.1）

**结果**：**可能良性**或VUS（取决于频率）

---

## MCP工具总览

| MCP Server | 工具 | 用途 |
|------------|------|------|
| Variant_Interpretation | `variantvalidator_gene2transcripts` | 获取MANE Select转录本 |
| Variant_Interpretation | `variantvalidator_validate` | 验证HGVS格式 |
| Variants | `get_variant` | Per-ancestry群体频率 |
| Variants | `gene_constraint` | pLI, LOEUF, mis_z约束指标 |
| Variants | `clinvar_search` | ClinVar记录搜索 |
| Variants | `clinvar_get_records` | ClinVar批量获取（VCV/RCV） |
| Clinical_Genomics | `clingen_gene_validity`, `clingen_actionability` | ClinGen 基因-疾病有效性、可干预性 |
| Clinical_Genomics | `civic_search_variants`, `civic_get_variant` | CIViC 临床证据 |
| Protein_Annotation | `get_domain_architecture`, `get_interpro_entry` | InterPro 结构域架构 |
| Protein_Annotation | `get_protein_atlas_gene` | 蛋白表达与亚细胞定位 |
| Structures&Interactions | `alphafold_check_coverage` | AlphaFold 结构覆盖度与 pLDDT |
| Structures&Interactions | `pdb_get_structures`, `intact_get_interactor` | 实验结构与相互作用 |
| Variant_Interpretation | `predict_variant_effect` | 主预测器 PP3/BP4、SpliceAI |
| Variant_Interpretation | `autopvs1_classify` | PVS1 决策树分级 |
| Variant_Interpretation | `esm_explain_variant_mechanism` | ESM 机制解释（需配凭据） |
| PubMed | `search_articles` | 文献检索 |
| PubMed | `get_full_text_article` | 全文获取 |

---

## 注意事项

1. **始终英语查询工具** — MCP工具参数必须使用英语（基因名、疾病名）；以用户语言回复结果
2. **保守应用** — 证据模糊时保持标准未满足
3. **逐条溯源** — 每条激活标准必须注明数据来源与时间戳
4. **队列去重** — Phase 6文献证据需要去重家系/队列避免重复计数
5. **五次重复验证** — 文献证据LLM抽取建议五次重复取稳定值

最终分类需由具备资质的临床实验室或专业人员审核；本Skill不替代诊断与遗传咨询。
