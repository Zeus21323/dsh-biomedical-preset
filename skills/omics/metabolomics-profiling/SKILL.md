---
name: metabolomics-profiling
description: 代谢组学分析——非靶向 LC/GC-MS 与靶向定量峰表的 QC 过滤、归一化、变换、PCA/PLS-DA/OPLS-DA（含置换验证）、单变量差异、注释置信级、通路富集与交付。当用户给的是峰表（m/z × 样本）、代谢物定量矩阵或 XCMS/MS-DIAL 输出时使用；原始谱图解卷积与谱库匹配用 pyopenms，代谢物数据库查询用 tooluniverse-metabolomics。
category: omics
tags: metabolomics, lipidomics, pls-da, mummichog, pathway-enrichment
---

# 代谢组学分析

## 什么时候用这个技能

| 输入 | 说明 |
|---|---|
| 峰表（feature table） | 行=特征（m/z + RT），列=样本；XCMS / MS-DIAL / MZmine / Compound Discoverer 输出 |
| 代谢物矩阵 | 已注释（HMDB/KEGG ID）或靶向绝对定量浓度 |
| 脂质组 | 脂质类别已注释的矩阵（注意类别内与跨类别归一化差异） |

原始谱图去卷积、峰检测参数、谱库匹配 → `pyopenms`。代谢物实体查询（HMDB/MetaboLights/Workbench）→ `tooluniverse-metabolomics` 或本包 MCP 的化学工具。

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

### 4. 多变量分析

```python
from sklearn.decomposition import PCA
import numpy as np
X = pareto_scaled_matrix          # 样本 × 特征
pca = PCA(n_components=5).fit(X)
scores = pca.transform(X)
```

- **PCA 先看两件事**：QC 样本是否聚成一簇（不聚 = 分析质量有问题，先停下修前处理）；是否有离群样本（用 Hotelling T² 或 SPE 判断，离群要报告并说明是否剔除）；
- **PLS-DA / OPLS-DA**：可用，但**必须**给置换检验（≥200 次），报告 R²Y、Q²、置换 p；Q² < 0.5 或置换 p > 0.05 就不要声称"分组分离"；
- 两组比较优先 OPLS-DA（正交信号分离），多组用 PLS-DA + VIP；
- VIP > 1 只是候选，不能单独当差异证据。

### 5. 单变量差异

| 检验 | 何时用 |
|---|---|
| Welch t / Mann-Whitney | 两组，按分布与方差选 |
| ANOVA + Tukey / Kruskal-Wallis + Dunn | 多组 |
| 配对检验 | 同一受试者前后、配对设计 |

- 报告 **fold change（原始尺度或 log2）+ p + FDR（BH）**；
- 阈值写成显式条件（如 `|log2FC| ≥ 1 且 FDR < 0.05 且 VIP > 1`），并给出该组合下的数量；
- 小样本（每组 n<5）不要用 FDR 后的 p 当唯一判据，配合效应量与 VIP。

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

### 7. 通路富集

- 已注释：代谢物 ID（HMDB/KEGG）→ ORA / GSEA（`pathway-enrichment` 技能）；
- 未注释或注释不足：`mummichog`（p 值自定义阈值、按质量数匹配的通路富集）；
- 背景集用**本次检出到的全部特征/代谢物**，不是全数据库。

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

## 验收清单

- [ ] QC 样本数量与来源（pooled / 混合）写清，且 PCA 中聚簇
- [ ] 过滤各步数量留痕
- [ ] 归一化方法、缩放方法、是否做漂移校正，写在 provenance
- [ ] 多变量分析带置换检验（次数、R²Y、Q²、p）
- [ ] 差异表含 FC、p、FDR、VIP、注释级别
- [ ] 富集背景集 = 本次检出集
- [ ] 图能追到脚本与输入矩阵
- [ ] 结论里写明 n、检验方法、FDR 方法、阈值与置信级
