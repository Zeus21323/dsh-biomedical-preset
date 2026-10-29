---
name: metabolomics-profiling
description: 代谢组学分析——非靶向 LC/GC-MS 与靶向定量峰表的 QC 过滤、归一化、变换、PCA/PLS-DA/OPLS-DA（含置换验证）、单变量差异、注释置信级、通路富集与交付。当用户给的是峰表（m/z × 样本）、代谢物定量矩阵或 XCMS/MS-DIAL 输出时使用；原始谱图解卷积与谱库匹配用 pyopenms，代谢物数据库查询用 tooluniverse-metabolomics。
category: omics
tags: metabolomics, lipidomics, pls-da, mummichog, pathway-enrichment
---

# 代谢组学分析

> 来源索引：`references/official-docs.md`（逐条官方 URL + 抓取状态）。下文每个命令块后紧跟 `> 来源: <URL>` 行，表格与判据用行内（来源: URL）标注；凡官方文档未提供的参数默认值或函数名，直接写明「官方文档未提供」。

## 什么时候用这个技能

| 输入 | 说明 |
|---|---|
| 峰表（feature table） | 行=特征（m/z + RT），列=样本；XCMS / MS-DIAL / MZmine / Compound Discoverer 输出 |
| 代谢物矩阵 | 已注释（HMDB/KEGG ID）或靶向绝对定量浓度 |
| 脂质组 | 脂质类别已注释的矩阵（注意类别内与跨类别归一化差异） |

原始谱图去卷积、峰检测参数、谱库匹配 → `pyopenms`。代谢物实体查询（HMDB/MetaboLights/Workbench）→ `tooluniverse-metabolomics` 或本包 MCP 的化学工具。

> 来源: XCMS 峰表/参数 — https://bioconductor.org/packages/release/bioc/vignettes/xcms/inst/doc/xcms-lcms-ms.html ；mzmine 文档 — https://mzmine.github.io/mzmine_documentation/latest/ ；MS-DIAL 官方教程入口 — https://systemsomicslab.github.io/mtbinfo.github.io/ （MS-DIAL 峰检测参数默认值与注释码官方文档未提供可逐字引用的网页，见 `references/official-docs.md` §8）；`pyopenms` — https://pyopenms.readthedocs.io/en/latest/ ；代谢物库入口 — https://hmdb.ca/ （本环境 403）、https://www.genome.jp/kegg/rest/keggapi.html 、https://lipidmaps.org/databases/lmsd

## 步骤

### 1. 体检（QC 样本必须在场）

```python
import pandas as pd, numpy as np
df = pd.read_csv("feature_table.csv", index_col=0)   # 行=特征
meta = pd.read_csv("sample_meta.csv", index_col=0)   # group, batch, injection_order
print(df.shape, meta["group"].value_counts())
qc = meta.index[meta["group"].str.upper().str.contains("QC")]
print("QC 样本数:", len(qc))
```
> 来源: `pandas.read_csv` — https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html ；QC 分组要显式给 XCMS 的 `sampleGroups`（`minFraction` 的官方定义是"至少一个样本组内的比例"，不单独成组则 QC 判据失效）— https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz （`man/groupChromPeaks.Rd`）

必须确认：

- **QC 样本**（pooled QC / 混合样）在同一批里，且数量 ≥ 每批 3 个；
- **注入顺序**（injection order）记录在 metadata 里——LC-MS 的信号漂移基本按顺序走；
- 分组、批次、生物学重复数；
- 缺失率分布（代谢组缺失常见，且常与低丰度/电离抑制相关）。

### 2. QC 过滤

| 规则 | 典型阈值 | 理由 |
|---|---|---|
| QC 样本 RSD（CV） | ≤ 30%（严格 20%） | 高于此的特征在仪器上就不稳定 |
| 特征缺失率 | ≤ 20%（探索性可放宽到 50%） | 缺失过多无法统计 |
| 只在空白里出现 | 剔除 | 污染/背景 |
| 同位素峰、加合物 | 去重（保留单同位素峰） | 避免同一代谢物多次计数 |

过滤顺序与数量必须留痕：`起始 N → QC-RSD 过滤后 → 缺失过滤后 → 去加合物后`。

### 3. 归一化与变换

- **样本级归一化**：总离子流（TIC）/ 中位数 / PQN（probabilistic quotient normalization，代谢组首选，对稀释与总浓度变化稳健）；
- **漂移校正**：按 injection order 做局部回归（LOESS / QC-RLSC），**必须用 QC 样本拟合**，再应用到所有样本；
- **变换**：`log2` 或 `log10`；**缩放用 Pareto**（`(x-mean)/sqrt(sd)`），这是代谢组惯例——auto scaling 会过度放大小峰噪声；
- 靶向绝对定量：不归一化，直接用浓度；只做 log 变换。

> 来源: PQN 原始文献（Dieterle et al. 2006, Anal Chem 78:4281-90）— https://pubmed.ncbi.nlm.nih.gov/16808434/ （原文并否定积分归一化：`integral normalization is a suboptimal method`）；QC-RLSC / LOESS 漂移校正（Dunn et al. 2011, Nat Protoc 6:1060-83）— https://pubmed.ncbi.nlm.nih.gov/21720319/ ；Pareto scaling（van den Berg et al. 2006, BMC Genomics 7:142）— https://pubmed.ncbi.nlm.nih.gov/16762068/ 。注意：**ropls 的 `opls()` 默认 `scaleC = "standard"`（unit variance），不是 Pareto**，要用 Pareto 必须显式 `scaleC = "pareto"`（来源: https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz ）；XCMS 的 `adjustRtime()` 校正的是保留时间，不是强度漂移。

### 4. 多变量分析

```python
from sklearn.decomposition import PCA
import numpy as np
X = pareto_scaled_matrix          # 样本 × 特征
pca = PCA(n_components=5).fit(X)
scores = pca.transform(X)
```
> 来源: `sklearn.decomposition.PCA` — https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html （`n_components` 默认 `None`，即保留 `min(n_samples, n_features)` 个成分；写 `n_components=5` 属显式截断）

- **PCA 先看两件事**：QC 样本是否聚成一簇（不聚 = 分析质量有问题，先停下修前处理）；是否有离群样本（用 Hotelling T² 或 SPE 判断，离群要报告并说明是否剔除）；
- **PLS-DA / OPLS-DA**：可用，但**必须**给置换检验（≥200 次），报告 R²Y、Q²、置换 p；Q² < 0.5 或置换 p > 0.05 就不要声称"分组分离"；
- 两组比较优先 OPLS-DA（正交信号分离），多组用 PLS-DA + VIP；
- VIP > 1 只是候选，不能单独当差异证据。

> 来源: ropls `opls(x, y, predI = NA, orthoI = 0, crossvalI = 7, permI = 20, scaleC = "standard", ...)` — https://bioconductor.org/packages/release/bioc/vignettes/ropls/inst/doc/ropls-vignette.html 。官方对 `permI` 的说明是 `[default is 20 for single response models (without train/test partition), and 0 otherwise]`，vignette 称 20 是"质量与速度的折中"——正文的"≥200 次"**高于**官方默认，属本技能更严判据；给了 `subset`（训练/测试划分）时 `permI` 默认变为 0，必须显式指定。OPLS-DA 官方示例 `opls(dataMatrix, genderFc, predI = 1, orthoI = NA)`。

### 5. 单变量差异

| 检验 | 何时用 |
|---|---|
| Welch t / Mann-Whitney | 两组，按分布与方差选 |
| ANOVA + Tukey / Kruskal-Wallis + Dunn | 多组 |
| 配对检验 | 同一受试者前后、配对设计 |

- 报告 **fold change（原始尺度或 log2）+ p + FDR（BH）**；
- 阈值写成显式条件（如 `|log2FC| ≥ 1 且 FDR < 0.05 且 VIP > 1`），并给出该组合下的数量；
- 小样本（每组 n<5）不要用 FDR 后的 p 当唯一判据，配合效应量与 VIP。

> 来源: Welch t / Mann-Whitney — https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html （`equal_var=False` 即 Welch）、https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html ；BH 校正 — https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html （`multipletests` 的 `method` **默认是 `'hs'`（Holm-Sidak），不是 BH**，写 BH 必须显式 `method='fdr_bh'`）；ANOVA + Tukey — `statsmodels.sandbox.stats.multicomp.pairwise_tukeyhsd`（同上站点）

### 6. 注释与置信级

按 MSI 分级如实标注，不要含糊：

| 级别 | 含义 |
|---|---|
| Level 1 | 标准品对照（保留时间 + 谱图一致） |
| Level 2 | 谱库匹配（谱图一致，无标准品） |
| Level 3 | 候选类别/结构（如"某类磷脂"） |
| Level 4 | 仅分子式或 m/z 特征，未鉴定 |

- 匹配容忍度写清：一级 MS ppm（通常 ≤ 5–10 ppm）、二级谱相似度阈值；
- 未注释特征不要强行命名；用 `mummichog` 做**基于通路的未注释特征富集**（利用 KEGG 网络，不依赖实体注释）。

> 来源: MSI 四级定义原文（Sumner et al. 2007）— https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/ （PMID 24039616）：`Identified compounds`、`Putatively annotated compounds (e.g. without chemical reference standards, based upon physicochemical properties and/or spectral similarity with public/commercial spectral libraries)`、`Putatively characterized compound classes`、`Unknown compounds`；Level 1 的最低门槛是 `A minimum of two independent and orthogonal data relative to an authentic compound analyzed under identical experimental conditions`。**注意：MSI 原文只写"four levels"并按顺序列四类名称，没有给 Level 1/2/3/4 的数字编号**，上表的编号是顺序简化。MS-DIAL 的注释码官方文档未提供可逐字引用的网页。

### 7. 通路富集

- 已注释：代谢物 ID（HMDB/KEGG）→ ORA / GSEA（`pathway-enrichment` 技能）；
- 未注释或注释不足：`mummichog`（p 值自定义阈值、按质量数匹配的通路富集）；
- 背景集用**本次检出到的全部特征/代谢物**，不是全数据库。

> 来源: mummichog 包与版本状态 — https://raw.githubusercontent.com/metabolomics-cloud/mummichog/master/README.md （`python3 -m mummichog.main -i <peaklist> -j <job> -a <annotation.json> -d <outdir>`；v2 冻结在 `mummichog-2.7` 分支，v3 开发中）；MetaboAnalyst mummichog 模块官方 vignette — https://www.metaboanalyst.ca/resources/vignettes/Functional_Analysis_global_metabolomics.html （`SetPeakEnrichMethod(mSet, "mum", "v2")`、`SetMummichogPval`、`PerformPSEA(mSet, "hsa_mfn", "current", 3, 100)`；输入要求高分辨质谱）；背景集留空的官方后果 — https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz （`If missing, the all genes listed in the database ... will be used as background.`）

### 8. 交付

```
analysis/   过滤后峰表、归一化矩阵、PCA/PLS-DA 得分、VIP、差异表（含 FC/p/FDR/VIP/注释级别）
figures/    QC RSD 分布、PCA（含 QC）、置换检验图、volcano、热图、通路富集图
provenance/ 仪器与色谱柱、采集模式（正/负离子）、峰检测软件与版本及参数、归一化与缩放方法、缺失去向、R/python 包版本
```

## 常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| QC 样本不进 PCA | 前处理问题被掩盖 | QC 必须在场且聚簇 |
| 只看 PLS-DA 的 R² | 过拟合，随便分组都能"分开" | 报告 Q² 与置换 p |
| 用 auto scaling | 噪声峰被放大成"标志物" | Pareto scaling |
| 缺失填 0 | 假差异（低丰度组被压成 0） | 按缺失机制处理或删除特征 |
| 不校正注入顺序漂移 | 批次方向成为"生物学差异" | QC-RLSC / LOESS |
| 未注释特征强行命名 | 结论不可核 | 标 Level 3/4 或走 mummichog |
| 靶向数据做 TIC 归一化 | 破坏绝对定量 | 靶向不归一化 |

> 来源: Pareto 与 autoscaling 是并列的两种预处理且 `greatly affect the outcome` — https://pubmed.ncbi.nlm.nih.gov/16762068/ ；ropls 默认 `scaleC = "standard"`（即 auto scaling）— https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz ；QC-RLSC 适用场景 — https://pubmed.ncbi.nlm.nih.gov/21720319/ ；PQN 优于积分归一化 — https://pubmed.ncbi.nlm.nih.gov/16808434/

## 验收清单

- [ ] QC 样本数量与来源（pooled / 混合）写清，且 PCA 中聚簇
- [ ] 过滤各步数量留痕
- [ ] 归一化方法、缩放方法、是否做漂移校正，写在 provenance
- [ ] 多变量分析带置换检验（次数、R²Y、Q²、p）
- [ ] 差异表含 FC、p、FDR、VIP、注释级别
- [ ] 富集背景集 = 本次检出集
- [ ] 图能追到脚本与输入矩阵
- [ ] 结论里写明 n、检验方法、FDR 方法、阈值与置信级
