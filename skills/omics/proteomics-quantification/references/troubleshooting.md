# 故障与判据（全部来自官方文档原文）

每条给出：现象 → 官方给的处置 → 来源。官方文档未覆盖的问题，标注「官方文档未提供」并只给排查方向。

## 1. 上游：表结构对不上

### 1.1 找不到 `PG.Quantity` / `report.tsv`

- DIA-NN 2.x 的主报告是 `.parquet`，TSV 只以矩阵形式出现（`.pg_matrix.tsv`、`.gg_matrix.tsv`、
  `.unique_genes_matrix.tsv`、`pr_matrix`）。蛋白层面的量是 `PG.MaxLFQ`（推荐）与 `PG.TopN`。
  `PG.Quantity` 是 1.8 及更早版本 `report.tsv` 的列名，2.x 官方列清单里没有。
- 官方原文：`The report is in .parquet format`；`DIA-NN generates ready-to-use .pg_matrix.tsv and .unique_genes_matrix.tsv tab-separated tables`。
  > 来源：https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md

### 1.2 `"LFQ intensity" + exp` / `iBAQ` 这些列"查不到定义"

- Cox Docs 的 Protein Groups 表**列了列名但描述为空**，所以不是我们漏看：
  `"LFQ intensity" + exp`、`"iBAQ" + exp`、`iBAQ L/M/H` 的描述单元格都是空的。
  **官方文档未提供这些列的语义**，只能引 MaxLFQ / iBAQ 原文。
- 三个过滤标志才是官方逐字写明"应当剔除"的列：`Reverse`、`Potential contaminant`、`Only identified by site`。
  > 来源：https://cox-labs.github.io/coxdocs/output_tables.html

### 1.3 FragPipe 里找不到 `Intensity` / `MaxLFQ Intensity`

- 官方列名带实验组前缀：`[experiment] Intensity`、`[experiment] MaxLFQ Intensity`、
  `[experiment] MaxLFQ Unique Intensity`、`[experiment] MaxLFQ Total Intensity`。
  按前缀展开即可，不存在裸的 `MaxLFQ Intensity` 单列。
  > 来源：https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_outputs.html

### 1.4 Spectronaut 报表列名无法核对

- 官方帮助站点 `https://help.biognosys.ch/` 在本环境连接失败；列语义仅存在于商业软件安装包内附的
  *Spectronaut User Manual*。**官方文档未提供可直接访问的列说明**，本技能只用它做输入路由。
  > 来源：https://biognosys.com/software/spectronaut/

## 2. 过滤与缺失

### 2.1 log 之后出现 `-inf`

- 表里的 `0` 不是"零丰度"。DIA-NN 官方给了明确语义：
  `A zero quantity should be interpreted as indicating that the analyte concentration is below the limit of reliable quantification. If the data needs to be log-transformed, these zeroes can be replaced with NA values.`
  → 先 `replace(0, NA)` 再 `log2`。
- MaxQuant 侧的 0 语义**官方文档未提供明文**；本技能沿用"DIA-NN 语义 + 保守处理（0 → NaN）"。
  > 来源：https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md

### 2.2 想用 `MQ` 做左移填补，R 报 "could not find function"

- imputeLCMD 2.1 的导出函数只有：`impute.MAR`、`impute.MAR.MNAR`、`impute.MinDet`、`impute.MinProb`、
  `impute.QRILC`、`impute.ZERO`、`impute.wrapper.KNN`、`impute.wrapper.MLE`、`impute.wrapper.SVD`。
  **没有 `impute.MQ`**。Perseus 式"左移 + 宽度抽样"对应 `impute.MinProb(q=0.01, tune.sigma=1)`。
- MSnbase 的 `impute()` 方法名来自 `MsCoreUtils::imputeMethods()`，官方示例给出 `"min"`、`"QRILC"`、
  `"MinDet"`、`"MLE"`、`"knn"`，同样**没有 `"MQ"`**。
  > 来源：https://cran.r-project.org/src/contrib/imputeLCMD_2.1.tar.gz 、
  > https://bioconductor.org/packages/3.23/bioc/src/contrib/MSnbase_2.38.1.tar.gz

### 2.3 Perseus 填补后样本间关系变了

- 官方 `Mode` 默认是 `each expression column separately (default)`，不是整矩阵。
  如果选了 `Total matrix`，所有列共用一个分布，组间差异会被抹平。
- `Down shift` 默认 1.8 SD、`Width` 默认 0.3 SD，都是相对**有效值**的标准差；
  数据没 log 就套这两个默认值会得到荒谬的填补量。
  > 来源：https://cox-labs.github.io/coxdocs/replacemissingfromgaussian.html

### 2.4 有效值门槛不知道定多少

- 官方文档未提供统一门槛。本技能给的是"至少一组全部重复 或 总样本 50%"，写进 provenance 即可，
  **不要**把它写成"官方推荐"。
  > 来源：https://cox-labs.github.io/coxdocs/output_tables.html（只提供列语义，无门槛建议）

## 3. limma / DEqMS

### 3.1 `topTable` 只出来 10 行

- `number` 形参默认 `10`。要全表必须显式 `number = Inf`。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz（`man/toptable.Rd`）

### 3.2 `adjust.method` 到底要不要写 `"BH"`

- 形参默认就是 `"BH"`：`A NULL value will result in the default adjustment method, which is "BH".`
  显式写 `"BH"` 等价于默认；不同写法不会改变结果，但**写出来便于方法学描述**。
  > 来源：同上

### 3.3 用 `topTable(fc=)` / `lfc=` 卡 fold change 之后 FDR 变差

- 官方 Note：`the use of fold-change cutoffs is not generally recommended. If the fold changes and p-values are not highly correlated, then the use of a fold change cutoff can increase the false discovery rate above the nominal level.`
  官方建议阈值化用 `treat()` / `topTreat()`。
- 另一条 Note：`the adjusted p-values returned by adjust.method="BH" remain valid as FDR bounds only when the genes remain sorted by p-value. Resorting the table by log-fold-change can increase the false discovery rate above the nominal level`
  → 用 `resort.by="logFC"` 排出来的表，`adj.P.Val` 不再是可以直接当 FDR 界用的量。
  > 来源：同上

### 3.4 `spectraCounteBayes` 报错 / 结果与 limma 一样

- DEqMS 不会自己算肽段数：`fit` 必须带 `$count` 属性（`which stored the peptide or PSM count quantified for the gene`）。
  vignette 的写法是 `fit3$count = psm.count.table[rownames(fit3$coefficients),"count"]` 再 `spectraCounteBayes(fit3)`。
- `fit.method` 默认 `"loess"`（`span = 0.75`）；拟合不好时官方建议用 `VarianceScatterplot` / `Residualplot` 检查，
  再考虑 `"nls"` 或 `"spline"`。
- `outputResult` 的 `sca.adj` 已经是 BH 校正后的值（`sca.P.Value adjusted by BH method`），不要再校正一次。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/DEqMS_1.30.0.tar.gz（`man/spectraCounteBayes.Rd`、`man/outputResult.Rd`）

### 3.5 有批次，先 `removeBatchEffect` 再做检验

- limma 官方文档没有"先 removeBatchEffect 再 topTable"的流程；`removeBatchEffect` 是**可视化/聚类前**的
  去批次工具，不是检验前置步骤。本技能的做法（把 batch 写进 `design`）与官方 `lmFit(object, design, ...)` 的
  设计矩阵模型一致。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz

## 4. 归一化与差异

### 4.1 归一化到底做对没有

- DIA-NN 官方给了一个可直接照做的检查：火山图正负 fold-change 点数应几乎平衡；
  再看 log2FC 直方图，`median` 与 half sample mode（`modeest::hsm()`）都应接近 0。
  如果"大部分蛋白都上调"，就是归一化没做对。
  > 来源：https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md（"Normalisation" 段）

### 4.2 fold change 阈值和 FDR 谁先谁后

- 官方明确：`fold-change cutoffs must be applied after adjusting the p-values via multiple testing correction, not before.`
  > 来源：同上（"Fold-changes" 段）

### 4.3 无重复却报了 p 值

- limma 能跑（`eBayes` 仍会算），但方差无法从数据估计，`adj.P.Val` 没有推断意义。
  本技能的做法是只报 FC 与描述统计。官方文档未就"无重复可否报 p"给出规定。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz（`man/ebayes.Rd` 无重复场景无说明）

### 4.4 `Intensity` 与 `LFQ intensity` 混用

- 官方只保证两列存在，未给"用哪个"的建议。`LFQ intensity` 是 MaxLFQ 算法的产物，
  跨样本可比的前提来自该算法本身（delayed normalization + maximal peptide ratio extraction）。
  **官方文档未提供"混用会怎样"的说明**，本技能按算法语义判为不可比。
  > 来源：https://doi.org/10.1074/mcp.M113.031591

## 5. 富集

### 5.1 富集结果"什么都显著"

- `universe` 留空的官方后果是：`If missing, the all genes listed in the database (eg TERM2GENE table) will be used as background.`
  → 背景 = 全数据库，而不是本次检出蛋白，ORA 的 p 值失去意义。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz（`man/enricher.Rd`）

### 5.2 蛋白 ID 映射手工做

- 官方文档未提供"批量映射"的单一命令；本技能用 mygene.info 的批量查询接口（对应本包 MCP 工具
  `genes_ontologies_mygene_query`）。
  > 来源：https://docs.mygene.info/en/latest/

## 6. 口径交叉检查（提交前自查）

- [ ] 差异表里的 `adj.P.Val` 是用 BH 得到的（limma 默认），且**没有**在按 log2FC 重排后再引用它当 FDR 界。
- [ ] 报告里没有把 `LFQ intensity` / `iBAQ` / `Intensity <raw>` 的语义说成"官方文档已定义"。
- [ ] DIA-NN 侧：写清用的是 `PG.MaxLFQ` 还是 `PG.TopN`，以及是否另外加了 `Q.Value <= 0.01`（默认只到 0.05）。
- [ ] 缺失值填补写清函数名（`impute.MinProb` 而非 `MQ`）、`q`、`tune.sigma`、随机种子。
- [ ] 富集写清 `universe` = 本次检出蛋白集合。
- [ ] DEqMS 结果里 `sca.adj` 只做了一次 BH。
