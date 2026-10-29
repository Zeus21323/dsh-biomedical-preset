---
name: proteomics-quantification
description: 蛋白质组定量下游分析——把 MaxQuant / DIA-NN / Spectronaut / FragPipe 的输出转成可统计的蛋白矩阵，做过滤、归一化、缺失值处理、limma/DEqMS 差异分析、富集与交付。当用户给的是 proteinGroups.txt、report.tsv、peptides.txt 这类定量结果（而不是原始 RAW/mzML）时使用；原始谱图处理与肽段鉴定用 pyopenms。
category: omics
tags: proteomics, mass-spectrometry, limma, DEqMS, differential-abundance
---

# 蛋白质组定量分析

> 来源索引：`references/official-docs.md`（逐条官方 URL + 抓取状态）。下文每个命令块后紧跟 `> 来源: <URL>` 行，表格与判据用行内（来源: URL）标注；凡官方文档未提供的列语义或函数名，直接写明「官方文档未提供」。

## 什么时候用这个技能

输入是**定量结果表**，不是原始谱图：

| 上游软件 | 典型文件 | 定量列 |
|---|---|---|
| MaxQuant | `proteinGroups.txt` / `peptides.txt` | `Intensity <raw>`、`LFQ intensity <raw>`、`iBAQ` |
| DIA-NN | `report.tsv`（1.8 及更早）/ `.parquet` 主报告（2.x）、`.pg_matrix.tsv` | `PG.Quantity`（1.8 及更早）、`PG.MaxLFQ` / `PG.TopN`（2.x）、`Precursor.Quantity`、`Q.Value` |
| Spectronaut | `*_Report.tsv` | `PG.Quantity`、`EG.QValue` |
| FragPipe / MSFragger | `combined_protein.tsv` | `[experiment] Intensity`、`[experiment] MaxLFQ Intensity` |
| 已对齐矩阵 | `.csv/.tsv/xlsx` | 一行一蛋白、一列一样本 |

> 来源: MaxQuant `proteinGroups.txt` 列名 — https://cox-labs.github.io/coxdocs/output_tables.html；DIA-NN 输出文件名与列清单 — https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md；FragPipe `combined_protein.tsv` 列名 — https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_outputs.html。Spectronaut 报表列名官方文档未提供（`help.biognosys.ch` 不可达，列语义仅在软件内附手册），仅作输入路由。

原始 RAW/DIA 谱图解析、肽段鉴定、FDR 控制 → 用 `pyopenms`（来源: https://pyopenms.readthedocs.io/en/latest/ ）。本技能从"已有定量表"开始。

## 步骤

### 1. 体检（不跳过）

先回答这几个问题再动手，答案写进 provenance：

```python
import pandas as pd
df = pd.read_csv("proteinGroups.txt", sep="\t", low_memory=False)
print(df.shape)
print([c for c in df.columns if c.startswith("LFQ intensity")])
print(df["Reverse"].value_counts(), df["Potential contaminant"].value_counts())
```
> 来源: `pandas.read_csv` — https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html；`Reverse` / `Potential contaminant` / `Only identified by site` 三个标志的定义 — https://cox-labs.github.io/coxdocs/output_tables.html

- 样本列与实验设计表能否一一对上（列名里的 raw file 名 vs 表型表 ID）；
- 每组生物学重复数（n<3 时差异分析只能用描述性统计，不要报 p 值）；
- 缺失模式：整体缺失率、按组缺失、是否集中在低丰度；
- 强度分布：`log2` 后的中位数是否接近、样本间是否系统性偏移。

### 2. 过滤

按顺序，且都留痕：

1. `Reverse == "+"` → 去掉（诱饵）；
2. `Potential contaminant == "+"` → 去掉（角蛋白、胰蛋白酶等），并在报告里说明去掉了多少；
3. `Only identified by site == "+"` → 去掉；
4. DIA-NN：`Q.Value <= 0.01`（或 `PG.Q.Value <= 0.01`）先筛前体/蛋白组——**主报告默认只到 5% FDR**，要 1% 必须显式 `--qvalue 0.01` 或在报告上再筛；
5. 有效值门槛：至少在 **一组的所有重复** 或 **总样本的 50%** 中有定量（二选一，写清选了哪个）。

> 来源: 第 1–3 条的官方原文均为 `These should be removed for further data analysis`（`Only identified by site` 官方只给定义、未给剔除建议）— https://cox-labs.github.io/coxdocs/output_tables.html；第 4 条 — https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md（`The default precursor FDR setting in DIA-NN is 5%, meaning the main report is filtered already at Q.Value <= 0.05.`）

### 3. 变换与归一化

```python
import numpy as np
mat = df.filter(regex="^LFQ intensity ").set_axis(sample_names, axis=1)
mat = mat.replace(0, np.nan)          # 0 是"未检出"，不是"零丰度"
logmat = np.log2(mat)
```
> 来源: `numpy.log2` — https://numpy.org/doc/stable/reference/generated/numpy.log2.html。注意：`LFQ intensity` / `iBAQ` / `Intensity <raw>` 的列语义**官方文档未提供**（Cox Docs 只列列名、描述单元格为空），算法定义见 MaxLFQ（https://doi.org/10.1074/mcp.M113.031591 ）与 iBAQ（https://doi.org/10.1038/nature10098 ）原文。

- MaxQuant 优先 `LFQ intensity`（已做 LFQ 归一化），不要再叠加一次中位数归一化；
- DIA-NN 用 `PG.MaxLFQ`（2.x）/ `PG.Quantity`（1.8 及更早）；DIA-NN 自身已做归一化（`Normalisation.Factor` 列给出的就是每个前体在本 run 的归一化因子），要在其上再叠加中位数归一化，先确认没有重复缩放（来源: https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md ）；
- 归一化前后各画一次箱线图，确认中位数对齐；偏移没消掉就考虑 `quantile` 或 `median` 中心化；
- **不要**在归一化前填补缺失。

### 4. 缺失值（最容易做错的一步）

先判断机制：低丰度样本缺失多 → MNAR；随机缺失 → MAR。

| 策略 | 何时用 | 做法 |
|---|---|---|
| 不填补 | 每组 n≥3 且缺失 < 20%，差异分析用成对可用值 | limma 直接吃 NA |
| 左移填补（`impute.MinProb` / Perseus 风格） | MNAR，低丰度缺失 | 从观测分布左移 1.8 SD、宽度 0.3 SD 抽样，**必须固定随机种子**（Perseus 官方默认 Width 0.3 / Down shift 1.8 — 来源: https://cox-labs.github.io/coxdocs/replacemissingfromgaussian.html ） |
| QRILC / KNN | MAR，缺失 < 30% | `imputeLCMD::impute.QRILC(tune.sigma = 1)` / `impute.wrapper.KNN`（来源: https://cran.r-project.org/web/packages/imputeLCMD/index.html ） |
| 直接删特征 | 缺失 > 50% | 删并记录数量 |

> 来源: imputeLCMD 的官方导出函数为 `impute.MinDet(q = 0.01)`、`impute.MinProb(q = 0.01, tune.sigma = 1)`、`impute.QRILC(tune.sigma = 1)`、`impute.wrapper.KNN/MLE/SVD`、`impute.MAR`、`impute.MAR.MNAR`、`impute.ZERO`——**没有 `impute.MQ`**；MSnbase 侧 `impute(object, method)` 的方法名来自 `MsCoreUtils::imputeMethods()`（示例 `"min"`、`"QRILC"`、`"MinDet"`、`"MLE"`、`"knn"`），同样没有 `"MQ"`（来源: https://cran.r-project.org/src/contrib/imputeLCMD_2.1.tar.gz 、 https://bioconductor.org/packages/3.23/bioc/src/contrib/MSnbase_2.38.1.tar.gz ）。

禁止：把缺失填 0 再 log（会产生 -inf），或填全局均值（压缩方差、制造假阴性）。

### 5. 批次与协变量

有批次就显式建模：`design <- model.matrix(~ batch + group)`，不要先 `removeBatchEffect` 再做差异分析（会低估方差）。
批次与分组完全混杂时**不能校正**，必须写清"批次效应与分组不可分离，结论受限"。

### 6. 差异分析

R + limma（推荐）：

```r
library(limma)
design <- model.matrix(~ 0 + group)
colnames(design) <- levels(factor(group))
fit <- lmFit(logmat, design)
contrast <- makeContrasts(Tumor - Normal, levels = design)
fit2 <- eBayes(contrasts.fit(fit, contrast))
topTable(fit2, number = Inf, adjust.method = "BH")
```
> 来源: limma 3.68.5 官方源码 `man/lmFit.Rd` / `man/makeContrasts.Rd` / `man/contrasts.fit.Rd` / `man/ebayes.Rd` / `man/toptable.Rd` — https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz （`adjust.method` 形参默认即 `"BH"`；`number` 默认 10，故全表须 `number = Inf`；`eBayes` 的 `trend` 默认 `FALSE`）

- **DEqMS**：蛋白差异的方差依赖肽段数，用 `DEqMS` 按 `peptides count` 重新估计先验，比裸 limma 保守，蛋白组首选（做法：`fit$count <- 肽段/PSM 数` → `spectraCounteBayes(fit, fit.method = "loess", coef_col)` → `outputResult(fit, coef_col = 1)`；末三列 `sca.t` / `sca.P.Value` / `sca.adj` 中的 `sca.adj` 已含 BH 校正——来源: https://bioconductor.org/packages/release/bioc/vignettes/DEqMS/inst/doc/DEqMS-package-vignette.html ）；
- 无重复：只报 fold change 与描述统计，**不报 p 值**；
- 阈值写成显式条件：`|log2FC| >= 1 且 adj.P.Val < 0.05`，并在报告里给出该阈值下的上下调数量。

### 7. 富集

蛋白 ID → 基因符号（用 `genes_ontologies_mygene_query` MCP 工具批量映射，别手工查），再做：

- ORA：`pathway-enrichment` 技能（GO/KEGG/Reactome，背景集必须是**本次检出到的蛋白**，不是全基因组）；
- GSEA：按 log2FC 或 -log10(p) 排序的全蛋白列表，不要只喂显著子集。

> 来源: `genes_ontologies_mygene_query` 对应的上游批量注释 API — https://docs.mygene.info/en/latest/ ；背景集留空的官方后果 — https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz （`universe` 原文：`If missing, the all genes listed in the database (eg TERM2GENE table) will be used as background.`）

### 8. 交付

```
analysis/    过滤后矩阵、归一化矩阵、差异表（含全部统计量）
figures/     PCA、缺失热图、样本相关性、volcano、top 差异热图
provenance/  上游软件与版本、搜库参数、过滤阈值、归一化方法、填补方法与种子、R/python 包版本
```

## 常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 用 `Intensity` 而非 `LFQ intensity` | 样本间不可比 | MaxQuant 用 LFQ |
| 0 当零丰度 | log 后 -inf、假差异 | 转 NaN |
| 未剔除 contaminant | 角蛋白占据 top 差异 | 先过滤再分析 |
| 缺失填均值 | 方差被压缩、p 值虚低 | 左移填补或成对可用 |
| `removeBatchEffect` 后再检验 | 方差低估、假阳性 | 写进 design |
| 富集背景用全基因组 | 富集全假阳性 | 背景=本次检出蛋白 |
| DIA 只靠默认 FDR | 默认只到 5%，低置信前体污染定量 | 显式 `--qvalue 0.01` 或再筛 `Q.Value ≤ 0.01` |

> 来源: `Intensity` / `LFQ intensity` 官方只保证列名存在、**未给"用哪个"的建议**，LFQ 的跨样本可比性来自 MaxLFQ 算法 — https://doi.org/10.1074/mcp.M113.031591 ；DIA-NN 默认前体 FDR 5% — https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md ；0 的语义在 DIA-NN 侧有官方说明（`A zero quantity should be interpreted as indicating that the analyte concentration is below the limit of reliable quantification`），MaxQuant 侧官方未给明文。

## 验收清单

- [ ] 样本列与设计表全部对齐，无误配
- [ ] 过滤各步数量有记录（起始 → 去诱饵 → 去污染 → 有效值门槛）
- [ ] log2 后样本中位数偏差 < 1（否则说明归一化没做对）
- [ ] 缺失处理方式与种子写在 provenance
- [ ] 差异表含 log2FC、t、P.Value、adj.P.Val、肽段数
- [ ] 图能追到脚本与输入矩阵
- [ ] 结论里写明 n、检验方法、FDR 方法、阈值
