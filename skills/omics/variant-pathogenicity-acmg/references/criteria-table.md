# PVS1–BP7 全表：证据码 / 官方定义 / 前提 / 强度可调范围

来源编号（S-xx）见 `official-docs.md`。所有英文定义均为 ACMG/AMP 2015（S-01）Table 3 / Table 4
原文；强度可调范围一栏只在有官方依据时才写具体等级，其余标为"无官方量化规范"。

## §1 使用约定

**强度层级（S-01）**：致病侧 PVS（very strong）、PS（strong）、PM（moderate）、PP（supporting）；
良性侧 BA1（stand-alone）、BS（strong）、BP（supporting）。原文强调"The numbering within each
category does not convey any differences of weight"——PS1 与 PS4 等重，编号不代表强弱顺序。

**强度修饰码（S-17）**：需要改写强度时用下划线后缀，如 `PVS1_Strong`、`PM2_Supporting`、
`BS4_Supporting`；不得只写"降级"而不标码。

**2015 原文允许的一般性升降级（S-01）**："some criteria listed as one weight can be moved to
another weight using professional judgment… in situations when the data are not as strong as
described, judgment can be used to consider the evidence as fulfilling a lower level"。
但**具体降到哪一级必须来自 SVI 或 VCEP 的成文规范**，不能由判读者临时决定。

**相对致病优势（S-05，经 S-03 转引核对）**：Supporting 2.08:1、Moderate 4.33:1、Strong 18.7:1、
Very Strong 350:1。这是所有强度改写建议的量化基础。

## §2 证据码全表

### 2.1 致病证据 — Very Strong

| 证据码 | 官方定义（S-01 Table 3 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **PVS1** | "Null variant (nonsense, frameshift, canonical +/−1 or 2 splice sites, initiation codon, single or multi-exon deletion) in a gene where loss of function (LOF) is a known mechanism of disease" | 官方 caveats：① Beware of genes where LOF is not a known disease mechanism (e.g. GFAP, MYH7)；② Use caution interpreting LOF variants at the extreme 3′ end of a gene；③ Use caution with splice variants predicted to lead to exon skipping but leave the remainder of the protein intact；④ Use caution in the presence of multiple transcripts。**必须走 §3 决策树** | `PVS1` / `PVS1_Strong` / `PVS1_Moderate` / `PVS1_Supporting`（S-03、S-17）；全基因缺失的特殊情形见 §3.7 |

### 2.2 致病证据 — Strong

| 证据码 | 官方定义（S-01 Table 3 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **PS1** | "Same amino acid change as a previously established pathogenic variant regardless of nucleotide change" | 原文 caveat："Beware of changes that impact splicing rather than at the amino acid/protein level"。S-13 进一步建议：可基于**预测 RNA 剪接效应**与已知致病变异的相似性使用 PS1 | 无 SVI 专项量化规范；按 S-01 一般性判断原则可下调 |
| **PS2** | "De novo (both maternity and paternity confirmed) in a patient with the disease and no family history" | 原文 note："Confirmation of paternity only is insufficient. Egg donation, surrogate motherhood, errors in embryo transfer, etc. can contribute to non-maternity"。表型须与基因一致 | 点数法：`PS2_Supporting` / `PS2_Moderate` / `PS2` / `PS2_VeryStrong`（S-16，见 §7.1） |
| **PS3** | "Well-established in vitro or in vivo functional studies supportive of a damaging effect on the gene or gene product" | 原文 note："Functional studies that have been validated and shown to be reproducible and robust in a clinical diagnostic laboratory setting are considered the most well-established"。S-08 给出四步评定框架；S-13 规定直接测 RNA 剪接的实验应走 PVS1_Strength 而非 PS3 | `PS3_Supporting` / `PS3_Moderate` / `PS3_Strong`（S-08；达到 Moderate 至少需 11 个变异对照） |
| **PS4** | "The prevalence of the variant in affected individuals is significantly increased compared to the prevalence in controls" | Note 1（**唯一的官方数值阈值之一**）："Relative risk (RR) or odds ratio (OR), as obtained from case-control studies, is >5.0 and the confidence interval around the estimate of RR or OR does not include 1.0"；Note 2：极罕见变异病例对照达不到统计显著时，"the prior observation of the variant in multiple unrelated patients with the same phenotype, and its absence in controls, may be used as **moderate** level of evidence" | 可依 Note 2 降为 `PS4_Moderate` / `PS4_Supporting`；升级无官方规范 |

### 2.3 致病证据 — Moderate

| 证据码 | 官方定义（S-01 Table 3 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **PM1** | "Located in a mutational hot spot and/or critical and well-established functional domain (e.g. active site of an enzyme) without benign variation" | "without benign variation" 是硬条件：该区域内存在良性变异即不成立。"hot spot"/"critical domain" 的界定属基因特异，需 VCEP 规范 | **无官方量化规范** |
| **PM2** | "Absent from controls (or at extremely low frequency if recessive) (see Table 6) in Exome Sequencing Project, 1000 Genomes or ExAC" | 原文 caveat："Population data for indels may be poorly called by next generation sequencing"。S-15 明确：**降为 Supporting**，理由是该类证据达不到 Moderate 所需的 4.33:1 优势，且 ExAC 中 99% 高质量变异频率 <1%、54% 仅出现一次。S-14 要求 BA1/BS1/PM2 三者互斥 | **固定 `PM2_Supporting`**（S-15）；VCEP 可进一步改写 |
| **PM3** | "For recessive disorders, detected in trans with a pathogenic variant" | Note："This requires testing of parents (or offspring) to determine phase"。S-14 规定 PM3 按"计数先证者"的方法使用（其 Table 7） | 可升级（S-01 举例：多次观察到与致病变异反式 → 可升至 Strong，即 `PM3_Strong`）；计数规则见 S-14 |
| **PM4** | "Protein length changes due to in-frame deletions/insertions in a non-repeat region or stop-loss variants" | 与 PVS1 存在重叠：S-03 明确"PM4 should not be applied for any variant in which PVS1, at any strength level, is also applied" | 去重规则见 S-03；无独立量化规范 |
| **PM5** | "Novel missense change at an amino acid residue where a different missense change determined to be pathogenic has been seen before" | 原文 caveat 同 PS1（警惕剪接效应）；"novel" 指该氨基酸改变本身未见报道 | **无官方量化规范**；VCEP 可改写（例如把 PM5 扩展到截短变异并降为 `PM5_Supporting`，属基因特异规范） |
| **PM6** | "Assumed de novo, but without confirmation of paternity and maternity" | 与 PS2 互斥，只能取其一且取较强者（S-14） | 点数法：`PM6_Supporting` / `PM6` / `PM6_Strong` / `PM6_VeryStrong`（S-16，见 §7.1） |

### 2.4 致病证据 — Supporting

| 证据码 | 官方定义（S-01 Table 3 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **PP1** | "Co-segregation with disease in multiple affected family members in a gene definitively known to cause the disease" | 原文 note："May be used as stronger evidence with increasing segregation data"。S-10 给出按每次减数分裂计点的 Table 3，且 PP1+PP4 合计**上限 +5.0 分** | 点数法 `PP1_Supporting`…（S-10，见 §7.2） |
| **PP2** | "Missense variant in a gene that has a low rate of benign missense variation and where missense variants are a common mechanism of disease" | "low rate of benign missense variation" 无官方数值定义，通常引用基因约束指标（如 missense Z）但**2015 原文未给阈值** | **无官方量化规范** |
| **PP3** | "Multiple lines of computational evidence support a deleterious effect on the gene or gene product (conservation, evolutionary, splicing impact, etc)" | 原文 caveat："As many in silico algorithms use the same or very similar input for their predictions, each algorithm should not be counted as an independent criterion. **PP3 can be used only once in any evaluation of a variant.**"；S-07 已用校准区间取代"多算法共识"；S-03 规定经典 ±1,2 剪接变异不得再用 PP3 剪接预测 | `PP3_Supporting` / `PP3_Moderate` / `PP3_Strong`（S-07，见 §5） |
| **PP4** | "Patient's phenotype or family history is highly specific for a disease with a single genetic etiology" | S-10 指出 PP4 与共分离证据不可分割，须与 PP1 一起计点；表型特异性不足时点数下调 | 点数法（S-10，见 §7.2） |
| **PP5** | "Reputable source recently reports variant as pathogenic but the evidence is not available to the laboratory to perform an independent evaluation" | S-09 为该条的专门澄清短文：强调"reputable source"不等于可替代独立评估，须记录来源、日期与其证据 | **无官方量化规范** |

### 2.5 良性证据 — Stand-alone / Strong

| 证据码 | 官方定义（S-01 Table 4 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **BA1** | "Allele frequency is above 5% in Exome Sequencing Project, 1000 Genomes, or ExAC" | S-04 修订措辞："Allele frequency is >0.05 in any general continental population dataset of **at least 2,000 observed alleles** and found in a gene **without a gene- or variant-specific BA1 modification**"；附 **9 个排除变异**（频率 >5% 但已有致病证据，如 HFE p.Cys282Tyr、GJB2 p.Val37Ile、BTD p.Asp444His）；提供向 ClinGen 申请新增排除的流程 | 固定 −8 点（S-06）；VCEP 可下调阈值（S-04、S-14） |
| **BS1** | "Allele frequency is greater than expected for disorder (see table 6)" | 依赖疾病发病率/携带率与遗传方式；S-01 Table 6 说明：频率高于该疾病在至少一个亚群中的期望值 → 强良性证据 | **无官方统一数值阈值**（见 §4.2） |
| **BS2** | "Observed in a healthy adult individual for a recessive (homozygous), dominant (heterozygous), or X-linked (hemizygous) disorder with full penetrance expected at an early age" | 三个条件同时成立：健康成人、相应合子状态、**完全外显且早发** | **无官方量化规范** |
| **BS3** | "Well-established in vitro or in vivo functional studies shows no damaging effect on protein function or splicing" | 与 PS3 同一评定框架（S-08）；S-13 规定直接测 RNA 剪接的实验不走 BS3 | `BS3_Supporting` / `BS3_Moderate`（S-08） |
| **BS4** | "Lack of segregation in affected members of a family" | 原文 caveat：表型常见时存在拟表型（"phenocopies… cancer, epilepsy"）；家系中可能存在第二个致病变异（双基因） | 点数法 / 负分（S-10，见 §7.2） |

### 2.6 良性证据 — Supporting

| 证据码 | 官方定义（S-01 Table 4 原文） | 适用前提 / 注意 | 强度可调范围 |
|---|---|---|---|
| **BP1** | "Missense variant in a gene for which primarily truncating variants are known to cause disease" | 与 PP2 互为镜像；需基因层面证据（该基因致病以截短为主） | **无官方量化规范** |
| **BP2** | "Observed in trans with a pathogenic variant for a fully penetrant dominant gene/disorder; or observed in cis with a pathogenic variant in any inheritance pattern" | 相位必须确定（父母/子代检测）；S-14 将 BP2 与 PM3 同列为"等位基因相位"证据，需按 Table 7 计数 | **无官方量化规范** |
| **BP3** | "In-frame deletions/insertions in a repetitive region without a known function" | 需证明该重复区无已知功能 | **无官方量化规范** |
| **BP4** | "Multiple lines of computational evidence suggest no impact on gene or gene product (conservation, evolutionary, splicing impact, etc)" | 原文 caveat：同源算法不得视为独立证据，"**BP4 can be used only once**"；S-07 给出校准区间 | `BP4_Supporting` / `BP4_Moderate` / `BP4_Strong` / `BP4_VeryStrong`（S-07，见 §5） |
| **BP5** | "Variant found in a case with an alternate molecular basis for disease" | 需确证的替代分子病因（另一基因的致病变异等） | **无官方量化规范** |
| **BP6** | "Reputable source recently reports variant as benign but the evidence is not available to the laboratory to perform an independent evaluation" | 同 PP5，S-09 限定用途 | **无官方量化规范** |
| **BP7** | "A synonymous (silent) variant for which splicing prediction algorithms predict no impact to the splice consensus sequence nor the creation of a new splice site AND the nucleotide is not highly conserved" | 两个 AND 条件都要满足；"highly conserved" 无官方阈值。S-13 扩展：BP7 可用于 **RNA 实验证明无剪接影响**（内含子、同义变异；错义变异在排除蛋白功能影响时亦可） | S-13 扩展用法；无量化阈值 |

## §3 PVS1 决策树（S-03，ClinGen SVI PVS1 Working Group）

### 3.0 前置门禁：LoF 是否为该基因的致病机制

S-03 Table 1 原文结构：

| 情形（原文条件） | 结论 |
|---|---|
| 基因临床有效性 **STRONG 或 DEFINITIVE**，且 ≥3 个 LoF 变异在**不使用 PVS1** 的情况下已判为 Pathogenic，且 >10% 的该表型相关变异为 LoF（须跨 >1 个外显子） | 可走 PVS1 流程图，给到满强度 |
| 基因临床有效性 **至少 MODERATE**，且 ≥2 个 LoF 变异已与表型关联（跨 >1 外显子）**AND** 小鼠 null 模型可重现表型 | **降一级**（VeryStrong → Strong） |
| 基因临床有效性 **至少 MODERATE**，且上述两项中**只满足一项** | **降两级**（VeryStrong → Moderate） |
| 没有任何证据表明 LoF 变异导致疾病 | **任何强度都不使用 PVS1** |

（单外显子基因例外，见 S-03 Table 1 脚注。）

### 3.1 NMD 预测

- S-03 原文："NMD is not predicted to occur if the premature termination codon occurs in the 3′ most
  exon or within the 3′-most 50 nucleotides of the penultimate exon"（引 Chang 2007；Lewis 2003）。
- 若 NMD **预测发生** → 满足 PVS1 的前置条件（仍受 §3.0 与生物学相关性约束）。
- 若 NMD **不预测发生** → 进入 §3.3。

### 3.2 外显子/转录本的生物学相关性

- 若该外显子**缺失于其他生物学相关转录本**，或该外显子在一般人群中**富集高频 LoF 变异** → **任何强度都不使用 PVS1**。
- "高频"的具体门槛 S-03 明确交由疾病组设定："The frequency threshold at which a LoF variant in the
  general population is considered to be high is dependent on specific gene and/or disease
  attributes… Each disease group should determine such cutoffs"。**因此本技能不给数值。**

### 3.3 NMD 不预测时的强度

| 条件 | 强度 |
|---|---|
| 有实验或临床证据表明被截短/改变的区域对蛋白功能关键（如该区域下游存在致病变异） | `PVS1_Strong` |
| 无上述证据，需按去除比例判断，且外显子生物学相关性已确认 | 去除 **>10%** 蛋白 → `PVS1_Strong`；去除 **<10%** 蛋白 → `PVS1_Moderate` |

S-03 说明 10% 是 SVI 的共识性经验规则，并明确"empirical data are needed to support and further
refine this generic rule"，疾病组可另行规定。

### 3.4 经典 ±1,2 剪接变异

1. 先检查变异附近 **±20 bp** 是否存在可重建框内剪接的强共识剪接序列；
2. 判断外显子长度能否被 3 整除（可 → 单纯跳过一个外显子仍为框内；不可 → 跳过即移码）；
3. 分别评估"使用隐蔽剪接位点"与"外显子跳过"两种情景；
4. **取所有情景中的最低强度**；
5. 该变异**不得同时使用 PP3 剪接预测**（避免同一预测证据重复计分）。

### 3.5 起始密码子变异

- S-03：功能研究显示起始位点可重启，故"generally does not recommend assigning PVS1 or PVS1_Strong for start loss variants"。
- 若存在使用替代起始密码子的功能转录本 → **任何强度都不用**。
- 若无替代起始：下一个下游框内 ATG 之前已有致病变异报道 → `PVS1_Moderate`；否则 → `PVS1_Supporting`。

### 3.6 外显子缺失

沿用 §3.1–§3.3 的框内/NMD 判断。**全基因缺失**在满足 LoF 机制的基因中默认给 PVS1；S-03 特别说明：
对已知单倍剂量不足基因的全基因缺失，即使按 S-01 组合规则 PVS1 单独不足以判 Pathogenic，
在无冲突证据时判 Pathogenic 是合理的（S-05 贝叶斯表述下单一 Very Strong 的后验概率 0.975 属 Likely pathogenic）。

### 3.7 基因内重复

- 插入位置未知或为串联重复时：若预测移码并触发 NMD，最多给 `PVS1_Strong`（因约 83% 重复为串联，S-03 引 Newman 2015）。
- NMD 不太可能发生或未知 → **不用 PVS1**。
- 重复片段长度不确定 → **不用 PVS1**（无法判断阅读框）。

### 3.8 与 PM4 的去重

S-03：凡已使用 PVS1（任意强度）的变异，**不得再用 PM4**。

## §4 频率阈值：BA1 / BS1 / PM2

### 4.1 BA1（有官方数值，但可被基因特异性下调）

- 2015 原文（S-01 Table 4）："Allele frequency is above 5% in Exome Sequencing Project, 1000 Genomes, or ExAC"。
- SVI 修订（S-04）："Allele frequency is **>0.05** in any general continental population dataset of
  **at least 2,000 observed alleles** and found in a gene **without a gene- or variant-specific BA1
  modification**"。
- S-04 指定用于分析的 6 个 ExAC 大陆人群子集（African、East Asian、European (Non-Finnish)、Latino、
  South Asian；Finnish 因奠基者人群被排除在推荐之外，但仍纳入排除集分析）。
- S-04 给出 **9 个 BA1 排除变异**（ClinVar ID 可查）：ACAD9 c.-44_-41dupTAAG、GJB2 c.109G>A、HFE c.187C>G、
  HFE c.845G>A、MEFV c.1105C>T、MEFV c.1223G>A、PIBF1 c.1214G>A、ACADS c.511C>T、BTD c.1330G>C。
- 操作层面（S-14）：默认阈值 5%；**BA1 / BS1 / PM2 三者互斥，只能有一个 "Met"**；许多 VCEP 会按疾病
   Prevalence 与遗传异质性下调该阈值，并维护自己的排除变异表。
- 判级影响：BA1 命中即 Benign，无需再评估其他证据（"stand-alone"）。

### 4.2 BS1（**无统一数值阈值**）

- 2015 原文只有定性表述："Allele frequency is greater than expected for disorder (see table 6)"。
- S-01 Table 6 说明的推理方式：致病变异在一般人群中的频率应低于该显性疾病的群体发病率；隐性病
  致病变异的杂合频率应与携带率一致；"Variants that have an allele frequency greater than expected
  for the disorder in at least one subpopulation (AA or EA) of individuals not known to have the
  disorder can be considered to have strong evidence of benign impact (BS1)"。
- S-14 的操作化写法：查疾病发病率（如 Genetic Testing Registry），"If the variant is found more
  frequently in the population (or at least one subpopulation in ExAC or gnomAD) than the disease
  occurs, this is considered strong evidence of a benign impact"。
- **结论：BS1 的阈值必须由"疾病发病率 ÷ 外显率 × 遗传异质性"逐病推算，原始标准与 SVI 均未给出通用数值。
  不要给"1%"、"0.1%" 之类的通用阈值，除非引用具体 VCEP 的 CSpec。**

### 4.3 PM2（已降级，且与 BA1/BS1 互斥）

- 2015 原文为 Moderate；S-15 降为 `PM2_Supporting`，并给出配套的组合规则增补（见 §6.2）。
- 使用前提：该位点在人群数据库中确实被充分覆盖。S-14：覆盖度"typically >20X"才可主张 absent；
  插入缺失在 NGS 中可能被漏检（S-01 PM2 caveat）。
- 频率读取建议：取**最高亚群频率（popmax）**而非全局频率；关注 95% CI（S-14 说明 VCI 默认显示上下界）。
- 隐性病可用"低于期望携带率"作为残留频率的判据（S-14）。

## §5 计算证据：PP3 / BP4 校准区间（S-07）

### 5.1 校准原理

S-07 用局部阳性预测值（local PPV）把工具分数映射到证据强度，采用的后验概率与似然比门槛
（S-07 Table 1）为：

| 等级 | 后验概率 | 正向似然比 |
|---|---|---|
| PP3 very strong | 0.9811 | 1,124:1 |
| PP3 strong | 0.6073 | 33.53:1 |
| PP3 moderate | 0.2108 | 5.790:1 |
| PP3 supporting | 0.0999 | 2.406:1 |
| BP4 supporting | 0.9812 | 0.4156:1 |
| BP4 moderate | 0.9921 | 0.1727:1 |
| BP4 strong | 0.9986 | 0.0298:1 |
| BP4 very strong | 1.0000 | 0.0009:1 |

（校准所用先验致病概率为 0.0441，来自 gnomAD 集的估计。）

### 5.2 13 个错义预测工具的官方区间（S-07 Table 2 原表）

区间记号：`(` `)` 不含端点，`[` `]` 含端点；"—" 表示该工具在该强度未达到阈值。

| 工具 | BP4 Supporting | BP4 Moderate | BP4 Strong | BP4 VeryStrong | PP3 Supporting | PP3 Moderate | PP3 Strong | PP3 VeryStrong |
|---|---|---|---|---|---|---|---|---|
| BayesDel (no AF) | — | — | ≤ −0.36 | (−0.36, −0.18] | [0.13, 0.27) | [0.27, 0.50) | ≥0.50 | — |
| CADD | — | ≤0.15 | (0.15, 17.3] | (17.3, 22.7] | [25.3, 28.1) | ≥28.1 | — | — |
| Evolutionary Action (EA) | — | — | ≤0.069 | (0.069, 0.262] | [0.685, 0.821) | ≥0.821 | — | — |
| FATHMM | — | — | ≥4.69 | [3.32, 4.69) | (−5.04, −4.14] | ≤ −5.04 | — | — |
| GERP++ | — | — | ≤ −4.54 | (−4.54, 2.70] | — | — | — | — |
| MPC | — | — | — | — | [1.360, 1.828) | ≥1.828 | — | — |
| MutPred2 | — | ≤0.010 | (0.010, 0.197] | (0.197, 0.391] | [0.737, 0.829) | [0.829, 0.932) | ≥0.932 | — |
| PhyloP | — | — | ≤0.021 | (0.021, 1.879] | [7.367, 9.741) | ≥9.741 | — | — |
| PolyPhen-2 (HumVar) | — | — | ≤0.009 | (0.009, 0.113] | [0.978, 0.999) | ≥0.999 | — | — |
| PrimateAI | — | — | ≤0.362 | (0.362, 0.483] | [0.790, 0.867) | ≥0.867 | — | — |
| REVEL | ≤0.003 | (0.003, 0.016] | (0.016, 0.183] | (0.183, 0.290] | [0.644, 0.773) | [0.773, 0.932) | ≥0.932 | — |
| SIFT | — | — | ≥0.327 | [0.080, 0.327) | (0, 0.001] | 0 | — | — |
| VEST4 | — | — | ≤0.302 | (0.302, 0.449] | [0.764, 0.861) | [0.861, 0.965) | ≥0.965 | — |

要点（S-07 正文）：

- 只有 REVEL、MutPred2 同时达到 PP3 与 BP4 的 Strong；CADD 达 BP4 Strong；BayesDel、VEST4 达 PP3 Strong。
- 多数工具在 26%–50% 的变异上落在"不确定区"，此时**不给 PP3/BP4**。
- 分数落在两个区间之间（如 REVEL 0.30–0.64）即为不确定区，不得凭"接近阈值"给证据码。
- FATHMM 与 SIFT 原始输出方向相反，S-07 已做变换；使用前须确认分数方向。

### 5.3 使用纪律

1. PP3 与 BP4 **各只能计一次**（S-01）。
2. 不得把"多个算法都阳性"当作升级理由（S-01 caveat）。
3. 经典 ±1,2 剪接变异不得再用 PP3 剪接预测（S-03）。
4. 剪接预测工具（如 SpliceAI）的阈值须按 S-13 的校准流程确定；本技能不提供数值，见 `official-docs.md` §5。
5. 工具版本与分数来源（dbNSFP 版本、预计算 vs 本地运行）要写入证据表。

## §6 组合判级

### 6.1 ACMG/AMP 2015 Table 5 原文

**Pathogenic**

1. 1 Very Strong (PVS1) **AND**
   - ≥1 Strong (PS1–PS4), OR
   - ≥2 Moderate (PM1–PM6), OR
   - 1 Moderate (PM1–PM6) and 1 Supporting (PP1–PP5), OR
   - ≥2 Supporting (PP1–PP5)
2. ≥2 Strong (PS1–PS4), OR
3. 1 Strong (PS1–PS4) **AND**
   - ≥3 Moderate (PM1–PM6), OR
   - 2 Moderate (PM1–PM6) AND ≥2 Supporting (PP1–PP5), OR
   - 1 Moderate (PM1–PM6) AND ≥4 Supporting (PP1–PP5)

**Likely Pathogenic**

1. 1 Very Strong (PVS1) AND 1 Moderate (PM1–PM6), OR
2. 1 Strong (PS1–PS4) AND 1–2 Moderate (PM1–PM6), OR
3. 1 Strong (PS1–PS4) AND ≥2 Supporting (PP1–PP5), OR
4. ≥3 Moderate (PM1–PM6), OR
5. 2 Moderate (PM1–PM6) AND ≥2 Supporting (PP1–PP5), OR
6. 1 Moderate (PM1–PM6) AND ≥4 Supporting (PP1–PP5)

**Benign**

1. 1 Stand-Alone (BA1), OR
2. ≥2 Strong (BS1–BS4)

**Likely Benign**

1. 1 Strong (BS1–BS4) and 1 Supporting (BP1–BP7), OR
2. ≥2 Supporting (BP1–BP7)

**Uncertain Significance**：以上均不满足，或良性与致病证据相互矛盾（S-01 Table 5 脚注原文：
"Variants should be classified as Uncertain Significance if other criteria are unmet or the criteria
for benign and pathogenic are contradictory."）。

### 6.2 SVI 对组合规则的增补（须注明出处再用）

| 增补条目 | 依据 | 说明 |
|---|---|---|
| `1 Very Strong + 1 Supporting → Likely Pathogenic` | S-15（PM2 v1.0） | 因 PM2 降为 Supporting 而新增；S-15 给出贝叶斯依据：1 VS + 1 Supporting 的后验概率 0.988，落在 LP 区间 0.90–0.99。S-14 的组合规则清单已收录该条（写作 "1 very strong AND 1 supporting*"） |

**除该条外，不要自行发明组合规则。** 其他一切组合仍按 §6.1 原文执行。

### 6.3 等价实现：点数法（S-06）

| 证据强度 | 致病侧点数 | 良性侧点数 |
|---|---|---|
| Very Strong (PVS1 / BA1) | +8 | −8 |
| Strong (PS1–4 / BS1–4) | +4 | −4 |
| Moderate (PM1–6) | +2 | −2（S-06 注明 2015 未设良性 moderate，但体系可容纳） |
| Supporting (PP1–5 / BP1–7) | +1 | −1 |
| Indeterminate | 0 | 0 |

分类阈值（S-06 Table 3）：**Pathogenic ≥10；Likely Pathogenic 6–9；VUS 0–5；Likely Benign −1 ~ −6；Benign ≤ −7**。

对应的后验概率边界（S-06 Table 1）：Pathogenic PP > 0.99；LP 0.99 ≥ PP > 0.90；Uncertain
0.10 ≤ PP ≤ 0.90；LB 0.001 ≤ PP < 0.10；Benign PP < 0.001。

使用时须同时说明：点数法与 §6.1 的定性规则在绝大多数组合上一致，但边界情形（例如 5 分）会落到 VUS，
而定性规则下可能已满足某条组合；两者冲突时以所用规范的明文为准，并在报告中写明采用了哪一套。

## §7 de novo、共分离、功能证据的强度要求

### 7.1 PS2 / PM6 点数表（S-16，Version 1.1）

每个先证者按"表型一致性 × 亲缘关系是否确认"计点：

| 表型一致性 | de novo 且亲缘关系已确认 | de novo 但亲缘关系未确认 |
|---|---|---|
| 表型对基因高度特异 | 2 | 1 |
| 表型与基因一致但不高度特异 | 1 | 0.5 |
| 表型与基因一致但不高度特异、且遗传异质性高 | 0.5 | 0.25 |
| 表型与基因不一致 | 0 | 0 |

（注：高度异质性情形"Maximum allowable value of 1 may contribute to overall score"。）

累计点数 → 强度：

| 强度 | Supporting | Moderate | Strong | Very Strong |
|---|---|---|---|---|
| 累计点数门槛 | 0.5 | 1 | 2 | 4 |
| 对应码 | `PS2_Supporting` / `PM6_Supporting` | `PS2_Moderate` / `PM6` | `PS2` / `PM6_Strong` | `PS2_VeryStrong` / `PM6_VeryStrong` |

其他官方要点（S-16、S-14）：

- 父母未做亲缘或变异检测 → **不计点**。
- PS2 与 PM6 互斥，只取较强者（S-14）。
- X 连锁：变异在无症状携带者母亲中 de novo 且家系史一致 → 仍可适用 de novo 证据。
- 常染色体隐性：若未找到第二个致病/可能致病变异 → **强度降一级**。
- 生殖腺嵌合（多个患病同胞、双亲均阴性）：须确认亲缘关系才可用 de novo 证据。
- 注意：这些"点"与 §6.3 的分类点数**不是同一套**（S-16 原文脚注已声明）。

### 7.2 PP1 / BS4 / PP4 点数表（S-10）

每次可计数的共分离（Table 3 原表）：

| 情形 | 1 例 | 2 例 | 3 例 | 4 例 | 5 例 |
|---|---|---|---|---|---|
| 常染色体隐性 — 患病同胞 | 2.0 | 4.0 | 6.0 | 8.0 | 10.0 |
| 常染色体隐性 — 未患病同胞 | 0.4 | 0.8 | 1.2 | 1.6 | 2.0（>5 例每例 +0.4） |
| 常染色体显性 — 患病与未患病 | 1.0 | 2.0 | 3.0 | 4.0 | 5.0 |
| X 连锁隐性 — 男性患病与未患病 | 1.0 | 2.0 | 3.0 | 4.0 | 5.0 |

官方脚注要点：

- 仅当疾病**完全外显**时才计入未患病个体；**父母不计入**（用于确定相位）。
- 点数记在**等位基因**上；同一等位基因上有多个变异时须按变异数均分。
- **"Capped at +5.0 points for all locus evidence (PP1 and PP4) above +5.0 points per allele"**——即 PP1 与 PP4 合计上限 +5.0 分。
- PP4 的点数来自"该表型下检出致病变异的诊断产出率"（S-10 Table 2 的百分比→点数映射），且与基因座
  特异性绑定：表型不特异、表型采集不全、或患者年龄过小都会降低 PP4 点数。
- 对位点异质性疾病，"一个位点的阴性证据构成其他位点的阳性证据"（S-10 摘要与正文）。

### 7.3 PS3 / BS3 的功能证据要求（S-08）

四步框架（S-08 原文）：

1. 明确疾病机制；
2. 评估该领域**一般类别**测定法的适用性；
3. 评估**具体某项**测定法的有效性（对照、重复性、盲法、动态范围等）；
4. 把结果应用到具体变异判读。

量化门槛（S-08 结果）："a minimum of **11 total pathogenic and benign variant controls** are
required to reach moderate-level evidence in the absence of rigorous statistical analysis"。

S-13 补充的分工：PS3/BS3 只用于**不直接反映 RNA 剪接**的功能测定；直接测 RNA 的实验走 `PVS1_Strength`
（LoF 型结果）或 BP7（无剪接影响）。

### 7.4 PS4 的病例对照阈值

见 §2.2：RR/OR >5.0 且 95% CI 不含 1.0 是**官方唯一给出的病例对照数值门槛**；达不到时按 Note 2
降为 moderate 级别的"多例同表型患者 + 对照缺失"证据。

## §8 "官方无量化阈值"清单（不得自行填数）

以下条目在 ACMG/AMP 2015 原始标准与已发布的 SVI 通用建议中**均无通用数值阈值**。使用时只能：
① 写"无统一阈值，需按疾病外显率与人群设定/按基因特异性规范处理"；或 ② 引用具体 VCEP 的 CSpec 数值。

| 条目 | 缺什么 | 处理方式 |
|---|---|---|
| BS1 | 通用 MAF 阈值 | 按疾病发病率 ÷ 外显率 × 遗传异质性逐病推算（§4.2） |
| PM1 | "hot spot"/"critical domain" 的界定与最小区域大小 | 依赖基因特异知识 / VCEP CSpec |
| PP2 | "low rate of benign missense variation" 的指标与阈值 | 依赖基因约束数据与 VCEP 规范 |
| PM5 | 是否要求"同一密码子"、"novel" 的判定边界 | 依赖 VCEP 规范 |
| PP4（单独使用） | 表型特异性的量化 | 按 S-10 点数表，且与 PP1 合计上限 +5 |
| PP5 / BP6 | "reputable source" 的等级门槛 | 按 S-09 记录来源与日期，不量化 |
| BP1 / BP3 / BP5 | 基因层面或区域层面的判定边界 | 依赖基因/区域证据 |
| BP7 的 "highly conserved" | 保守性阈值 | 用公认保守性指标并写明所用指标与版本 |
| PVS1 中"高频 LoF 变异" | 频率门槛 | S-03 明确交由疾病组设定（§3.2） |
| 剪接预测工具分值区间 | 工具阈值 | 按 S-13 校准流程与原文附表（§5.3） |
| VUS 复核周期 | 时间间隔 | 见 `reporting.md` §3（属机构实践） |
| 数据库"最近"的时限（PP5/BP6） | 时间窗口 | 报告中写明检索日期即可，不设硬性期限 |

## §9 判读落表模板（`02.evidence.tsv` 列定义）

| 列 | 含义 | 示例 |
|---|---|---|
| code | 证据码（含强度修饰） | `PVS1_Strong` |
| met | 是否满足（Met / Not met / N/A） | `Met` |
| definition_source | 定义出处 | `S-01 Table 3` |
| strength_source | 强度改写出处（若改写过） | `S-03 §NMD/10% 规则` |
| evidence_summary | 一句话依据 | `PTC 位于倒数第二外显子末 50nt 内，NMD 不预测；截短去除 42% 蛋白` |
| data_source | 数据/文献来源与版本 | `ClinVar 2026-10-29 快照；PMID xxxxxxxx` |
| note | 未满足原因或待补数据 | `需 RNA 实验确认剪接效应` |

填表纪律：`met = Not met` 的行也要保留，报告需展示"考虑过但未成立"的证据，这是复核与差异解决的依据。
