# VUS 处理与报告措辞、复核周期

来源编号（S-xx）见 `official-docs.md`。本文件区分三类内容并逐条标注：

- **【原文】** = 官方文件明文；
- **【共识建议】** = 官方文件虽未逐字写明、但可由官方规则直接推出的做法；
- **【机构实践】** = 行业内常见做法，**无官方统一规定**，须以本单位 SOP 为准。

## §1 分类术语（【原文】S-01）

五级术语与官方定义：

| 术语 | 官方界定 |
|---|---|
| Pathogenic | 满足 Table 5 的 Pathogenic 组合规则 |
| Likely Pathogenic | 满足 Table 5 的 Likely Pathogenic 组合规则；原文将 "likely" 定义为 **">90% certainty of a variant either being disease-causing or benign"** |
| Uncertain Significance (VUS) | 其他条件均不满足，或良性与致病证据互相矛盾 |
| Likely Benign | 同 Likely Pathogenic 的 >90% 界定 |
| Benign | 满足 Table 5 的 Benign 组合规则 |

报告硬性要求（【原文】S-01）："It is recommended that all assertions of pathogenicity (including
'likely pathogenic') be reported **with respect to a condition and inheritance pattern**"。
即：不允许只写"致病"，必须写"致 XXX 病，常染色体显性遗传"。

同一变异涉及多个疾病时（【原文】S-01 允许、【共识建议】按疾病分别判级）：应为每个疾病—遗传方式
组合各出一份分类，不得合并成一句。

## §2 VUS 的处理

### 2.1 什么情况下必须是 VUS（【原文】S-01 Table 5 脚注）

"Variants should be classified as Uncertain Significance if other criteria are unmet or the criteria
for benign and pathogenic are contradictory."

因此以下情形**不允许**判为 LP / LB：

- 只有 PVS1 单独成立（按 Table 5 原文，PVS1 单独不构成 LP；S-15 的增补条目要求再加 1 条 Supporting）；
- PVS1 + PM2 以外的单条 Moderate（PM2 已降为 Supporting，二者组合即为 S-15 增补的 LP 路径，需明确标注）；
- 仅有 PP3 或仅有 BP4；
- 致病与良性证据同时成立且无法排除其中之一。

### 2.2 不因临床急需而升级（【共识建议】）

Table 5 是**充分条件式**规则：只有满足某条组合才可判 LP 及以上。临床紧迫性、家系表型吻合、
"指南没覆盖但看起来很像"都不构成证据码，因此不能改写分类。需要行动时，正确做法是在报告中写
"VUS + 临床处理建议（如按表型做影像/生化随访、家系成员检测、RNA 或功能研究）"，而不是把 VUS 写成 LP。

### 2.3 VUS 必须写清的三件事（【共识建议】）

1. **缺什么证据**：逐条列出"未满足"的证据码及原因（例如"PS3 未满足：现有测定法未做阳性/阴性对照，
   按 S-08 达不到 Moderate 门槛"）。
2. **什么能改变结论**：列出可解除 VUS 的具体观察（如"若发现第二个家系共分离"、"若 RNA 实验显示
   外显子跳过"、"若 gnomAD 覆盖度确认该位点充分覆盖且仍为 absent"）。
3. **复核安排**：见 §3。

## §3 复核周期

### 3.1 官方依据

【原文】S-01："Clinical laboratories should implement an internal system to track all sequence
variants identified in each gene and clinical assertions when reported."——官方要求的是**持续追踪
与记录**，**未规定统一的时间间隔**。

**因此"每 12 个月复评一次"之类的时间表不是 ACMG/AMP 或 ClinGen 的通用规定。**

### 3.2 触发式重评（【共识建议】）

出现下列任一事件即应重评，不必等固定周期：

| 触发事件 | 需要复查的内容 |
|---|---|
| ClinVar 中该变异出现新的专家面板（VCEP）分类或 review status 升级 | 采用专家分类，并核对对方证据表 |
| 该基因的 CSpec / VCEP 规范更新（阈值下调、排除变异、强度改写） | 全部相关证据码 |
| gnomAD 版本更新或该位点覆盖度数据变化 | BA1 / BS1 / PM2 |
| ClinGen Gene-Disease Validity 等级或遗传方式变更 | PVS1 强度（S-03 Table 1 依赖该等级） |
| 新的功能研究、RNA 研究或病例对照研究发表 | PS3 / BS3 / PS4 / PP1 |
| 家系新增成员或表型修订 | PP1 / BS4 / PP4 / PS2 / PM6 |
| ACMG/AMP 或 SVI 通用建议更新 | 全表 |

### 3.3 固定周期（【机构实践】）

行业常见做法是 **VUS 每 1–3 年主动复查一次、已分类变异在数据源大版本更新时复查**，并写入实验室
SOP 与报告脚注。**这类周期属机构政策，不是官方规定**；写报告时必须标为"本实验室政策"，不得
表述为 ACMG/ClinGen 要求。

### 3.4 记录格式（【机构实践】）

```
05.recheck.md
- 判读日期 / 判读者 / 复核者
- 证据快照日期：ClinVar 20xx-xx-xx；gnomAD vX.Y；MANE vX
- 下次触发条件：<从 §3.2 勾选>
- 计划主动复查日期：<机构政策>
- 变更历史：日期 / 变更内容 / 分类是否改变 / 依据
```

## §4 报告措辞模板

> **以下为中文写作模板，不是官方措辞。** ClinGen 另提供面向 VCEP 的标准化报告文本（standardized
> text）文档，入口见 `https://clinicalgenome.org/docs/`；如需与 VCEP 报送一致的英文措辞，应取用
> 该文档而非本模板。

### 4.1 结论句

```
检出 [GENE] 基因 [TRANSCRIPT, e.g. NM_000000.0] c.[HGVS] (p.[PROTEIN]) 杂合/纯合/半合子变异，
根据 ACMG/AMP 2015 标准及 ClinGen SVI 建议，分类为【致病 / 可能致病 / 意义未明 / 可能良性 / 良性】，
与 [DISEASE]（[遗传方式]）相关。
```

要点：疾病 + 遗传方式必须出现（S-01 原文要求）；转录本版本必须出现。

### 4.2 证据句（每条一行，含出处）

```
PVS1_Strong：无义变异，位于 [EXON]；按 ClinGen SVI PVS1 决策树，终止密码子不在末外显子亦不在
倒数第二外显子末 50 nt 内，NMD 预测发生；基因—疾病有效性为 Definitive 且 LoF 为已知机制，
截短去除约 [N]% 蛋白 → 维持 Strong。
PP3：REVEL = [SCORE]，落入 ClinGen SVI 校准的 PP3 Supporting 区间 [0.773, 0.932)（Pejaver 2022）。
PM2_Supporting：gnomAD v[X] popmax AF = [AF]（[亚群]），位点覆盖度 >20X；按 ClinGen SVI PM2 v1.0 降为 Supporting。
```

### 4.3 组合句

```
按 ACMG/AMP 2015 Table 5 第 1 条（1 Very Strong + ≥1 Supporting）判为 Pathogenic；
或：按 ClinGen SVI PM2 v1.0 增补的组合规则（1 Very Strong + 1 Supporting → Likely Pathogenic）判为
Likely Pathogenic。所用组合条目：Table 5 §Pathogenic 规则 1(a–d) 中的 [x]。
```

若使用点数法，另起一句写明："以 Tavtigian 2020 点数法复核：累计 [N] 分，落入 [LP/VUS/…] 区间"。

### 4.4 VUS 句

```
该变异目前分类为意义未明（VUS）。已考虑但不成立的证据：PS3（现有功能研究缺乏 [对照/重复]，
未达 ClinGen SVI PS3/BS3 建议的 Moderate 门槛）、PP1（家系中仅 1 例可计数共分离）。
可解除 VUS 的观察包括：[列 2–3 条具体、可执行的观察]。
本实验室将于 [日期] 或出现上述观察时重评（机构政策）。
```

### 4.5 局限性与边界句（建议固定写入）

```
本分类基于 [日期] 可得的公共数据库与文献，随数据更新可能改变。
致病性判读不等同于临床诊断；本结果须结合表型、家系与临床检查综合判断。
```

### 4.6 常见措辞错误（逐条对照）

| 错误写法 | 问题 | 正确写法 |
|---|---|---|
| "未发现致病变异" 用于 VUS 场景 | VUS 不是阴性 | "检出意义未明变异，尚不能确定其致病性" |
| "可能致病" 简写为 "致病" | 跨越分类等级 | 严格按五级术语 |
| "该变异致病" 不写疾病与遗传方式 | 违反 S-01 报告要求 | 写明疾病 + 遗传方式 |
| "多个软件预测有害，支持致病" | 违反"算法不得视为独立证据、PP3 只能计一次" | 给出单一校准分数与区间，标为 PP3 一次 |
| "人群频率 0.001" 未说明人群与版本 | 无法复核 | 写 popmax + 亚群 + gnomAD 版本 + 访问日期 |
| "人群中未见" 未提覆盖度 | 覆盖不足时不能主张 absent | 补覆盖度（通常 >20X，S-14） |
| "按 ACMG 指南判为致病" 而不列证据码 | 不可审阅 | 逐条列证据码及其官方定义出处 |
| 把 BA1 与 BS1、PM2 同时写为满足 | 三者互斥（S-14） | 只保留一个 |

## §5 与外部判读不一致时的处理（【共识建议】）

1. 先对齐**变异本身**：转录本、HGVS、基因组版本、ClinGen Allele Registry CA ID（S-表 3）。
2. 逐条比对证据码：多数不一致来自频率阈值（BA1/BS1 基因特异下调）、PVS1 强度、PP3 工具与区间。
3. 查 ClinGen Evidence Repository 与 CSpec：若该基因有 VCEP 规范，按规范执行，并在报告中注明所依据的
   CSpec 版本。
4. 保留差异记录：对方分类、日期、证据摘要、本实验室结论与理由。S-01 明确鼓励实验室间协作以解决差异。
5. 不因"多数实验室这么判"而改变分类——证据码必须能独立成立。
