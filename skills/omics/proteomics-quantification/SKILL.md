---
name: proteomics-quantification
description: 蛋白质组定量下游分析——把 MaxQuant / DIA-NN / Spectronaut / FragPipe 的输出转成可统计的蛋白矩阵，做过滤、归一化、缺失值处理、limma/DEqMS 差异分析、富集与交付。当用户给的是 proteinGroups.txt、report.tsv、peptides.txt 这类定量结果（而不是原始 RAW/mzML）时使用；原始谱图处理与肽段鉴定用 pyopenms。
category: omics
tags: proteomics, mass-spectrometry, limma, DEqMS, differential-abundance
---

# 蛋白质组定量分析

## 什么时候用这个技能

输入是**定量结果表**，不是原始谱图：

| 上游软件 | 典型文件 | 定量列 |
|---|---|---|
| MaxQuant | `proteinGroups.txt` / `peptides.txt` | `Intensity <raw>`、`LFQ intensity <raw>`、`iBAQ` |
| DIA-NN | `report.tsv` / `report.pg_matrix.tsv` | `PG.Quantity`、`Precursor.Quantity`、`Q.Value` |
| Spectronaut | `*_Report.tsv` | `PG.Quantity`、`EG.QValue` |
| FragPipe / MSFragger | `combined_protein.tsv` | `Intensity`、`MaxLFQ Intensity` |
| 已对齐矩阵 | `.csv/.tsv/xlsx` | 一行一蛋白、一列一样本 |

原始 RAW/DIA 谱图解析、肽段鉴定、FDR 控制 → 用 `pyopenms`。本技能从"已有定量表"开始。

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

- 样本列与实验设计表能否一一对上（列名里的 raw file 名 vs 表型表 ID）；
- 每组生物学重复数（n<3 时差异分析只能用描述性统计，不要报 p 值）；
- 缺失模式：整体缺失率、按组缺失、是否集中在低丰度；
- 强度分布：`log2` 后的中位数是否接近、样本间是否系统性偏移。

### 2. 过滤

按顺序，且都留痕：

1. `Reverse == "+"` → 去掉（诱饵）；
2. `Potential contaminant == "+"` → 去掉（角蛋白、胰蛋白酶等），并在报告里说明去掉了多少；
3. `Only identified by site == "+"` → 去掉；
4. DIA-NN：`Q.Value <= 0.01`（或 `PG.Q.Value <= 0.01`）先筛前体/蛋白组；
5. 有效值门槛：至少在 **一组的所有重复** 或 **总样本的 50%** 中有定量（二选一，写清选了哪个）。

### 3. 变换与归一化

```python
import numpy as np
mat = df.filter(regex="^LFQ intensity ").set_axis(sample_names, axis=1)
mat = mat.replace(0, np.nan)          # 0 是"未检出"，不是"零丰度"
logmat = np.log2(mat)
```

- MaxQuant 优先 `LFQ intensity`（已做 LFQ 归一化），不要再叠加一次中位数归一化；
- DIA-NN 用 `PG.Quantity`，通常需要 **中位数归一化**；
- 归一化前后各画一次箱线图，确认中位数对齐；偏移没消掉就考虑 `quantile` 或 `median` 中心化；
- **不要**在归一化前填补缺失。

### 4. 缺失值（最容易做错的一步）

先判断机制：低丰度样本缺失多 → MNAR；随机缺失 → MAR。

| 策略 | 何时用 | 做法 |
|---|---|---|
| 不填补 | 每组 n≥3 且缺失 < 20%，差异分析用成对可用值 | limma 直接吃 NA |
| 左移填补（MinProb / Perseus 风格） | MNAR，低丰度缺失 | 从观测分布左移 1.8 SD、宽度 0.3 SD 抽样，**必须固定随机种子** |
| QRILC / KNN | MAR，缺失 < 30% | `imputeLCMD` / `sklearn` KNN(k=10) |
| 直接删特征 | 缺失 > 50% | 删并记录数量 |

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

- **DEqMS**：蛋白差异的方差依赖肽段数，用 `DEqMS` 按 `peptides count` 重新估计先验，比裸 limma 保守，蛋白组首选；
- 无重复：只报 fold change 与描述统计，**不报 p 值**；
- 阈值写成显式条件：`|log2FC| >= 1 且 adj.P.Val < 0.05`，并在报告里给出该阈值下的上下调数量。

### 7. 富集

蛋白 ID → 基因符号（用 `genes_ontologies_mygene_query` MCP 工具批量映射，别手工查），再做：

- ORA：`pathway-enrichment` 技能（GO/KEGG/Reactome，背景集必须是**本次检出到的蛋白**，不是全基因组）；
- GSEA：按 log2FC 或 -log10(p) 排序的全蛋白列表，不要只喂显著子集。

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
| DIA 不筛 q 值 | 低置信前体污染定量 | Q.Value ≤ 0.01 |

## 验收清单

- [ ] 样本列与设计表全部对齐，无误配
- [ ] 过滤各步数量有记录（起始 → 去诱饵 → 去污染 → 有效值门槛）
- [ ] log2 后样本中位数偏差 < 1（否则说明归一化没做对）
- [ ] 缺失处理方式与种子写在 provenance
- [ ] 差异表含 log2FC、t、P.Value、adj.P.Val、肽段数
- [ ] 图能追到脚本与输入矩阵
- [ ] 结论里写明 n、检验方法、FDR 方法、阈值
