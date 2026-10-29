# 参数对照表（默认值与说明逐字取自官方文档）

来源缩写见文末「来源索引」。凡官方未给默认值者标注「官方未给默认值」；
凡官方连列语义都没写者标注「官方文档未提供」。

## A. 上游定量表：列语义的官方覆盖度

| 列 / 标志 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `Reverse == "+"`（proteinGroups） | `contains no protein, made up of at least 50% of the peptides of the leading protein, with a peptide derived from the reversed part of the decoy database. These should be removed for further data analysis.` | X3 |
| `Potential contaminant == "+"` | `was found to be a commonly occurring contaminant. These should be removed for further data analysis.` | X3 |
| `Only identified by site == "+"` | `was identified only by a modification site.`（官方只给定义，未给"是否剔除"的建议） | X3 |
| `Q-value`（proteinGroups） | `This is the ratio of reverse to forward protein groups.` | X3 |
| `Score`（proteinGroups） | `Protein score which is derived from peptide posterior error probabilities.` | X3 |
| `Peptides` / `Razor + unique peptides` / `Unique peptides` | `The total number of peptide sequences associated with the protein group...` | X3 |
| `"Peptides" + exp` 等按实验展开的列 | `"Number of peptides (distinct peptide sequences) in experiment" + exp` | X3 |
| `LFQ intensity <raw>` | 列名在官方表中出现（`"LFQ intensity" + exp`），**描述为空** → 列语义**官方文档未提供**；算法见 MaxLFQ 原文 | X3 / X7 |
| `iBAQ` / `iBAQ L/M/H` | 列名出现、**描述为空** → 列语义**官方文档未提供**；算法见 iBAQ 原文 | X3 / X8 |
| `Intensity <raw>` | Protein Groups 表**未列出**该列 → **官方文档未提供**该列的 proteinGroups 语义（`Intensity` 的描述只出现在 msms/evidence/site/All Peptides 表） | X3 |
| DIA-NN `Precursor.Quantity` | `MS2-based quantity of the precursor (charged peptide), non-normalised` | N1 |
| DIA-NN `PG.MaxLFQ` | `QuantUMS or MaxLFQ normalised quantity for the protein group, channel-specific`（**2.x 推荐用这个做蛋白层面统计**） | N1 |
| DIA-NN `PG.TopN` | `Normalised protein group quantity calculated using Top N method (default N = 1...)` | N1 |
| DIA-NN `PG.Quantity` | **2.x 官方列清单中不存在**；属 1.8 及更早版本 `report.tsv` 列名 | N1 |
| DIA-NN 主报告文件 | `.parquet`；TSV 只有 `.pg_matrix.tsv` / `.gg_matrix.tsv` / `.unique_genes_matrix.tsv` / `pr_matrix` | N1 |
| DIA-NN 矩阵过滤 | `filtered at 1% FDR, using global q-values for protein groups and both global and run-specific q-values for precursors. Additional 5% run-specific protein-level FDR filter is applied to the protein matrices` | N1 |
| FragPipe `[experiment] Intensity` | `normalized (by default) protein intensity using the razor peptides (from the top-N algorithm)` | F1 |
| FragPipe `[experiment] MaxLFQ Intensity` | `normalized (by default) protein intensity using the razor peptides (from the MaxLFQ method)` | F1 |
| FragPipe `Combined Spectral Count` | `number of PSMs corresponding to the razor peptides` | F1 |
| Spectronaut `PG.Quantity` / `EG.QValue` | **官方文档未提供**（`help.biognosys.ch` 不可达，列语义仅在软件内附手册） | S1 |

## B. DIA-NN 命令行

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `--qvalue [X]` | `specifies the precursor-level q-value filtering threshold for the main report`；**该条未写默认值**；Filtering 小节原文：`The default precursor FDR setting in DIA-NN is 5%` → 主报告默认已按 `Q.Value <= 0.05` 过滤 | N1 |
| `--protein-quant-qvalue [X]` | `default value is 0.01` | N1 |
| `--quant-qvalue [X]` | `default value is 0.01` | N1 |
| `--quant-pep [X]` | `default value is 0.05` | N1 |
| `--top [N]` | `set N for the Top N protein quantification, default N = 1` | N1 |
| `--quant-fr [N]` | `Default value is 6` | N1 |
| `--matrix-spec-q` | 调整蛋白矩阵额外的 5% run-specific 蛋白层面 FDR | N1 |
| `--threads [N]` | `specifies the number of CPU threads to use`（未给默认值） | N1 |

## C. limma

| 函数 / 参数 | 官方 `\usage{}` 与默认值 | 来源 |
| --- | --- | --- |
| `lmFit(object, design = NULL, ...)` | `lmFit(object, design = NULL, ndups = NULL, spacing = NULL, block = NULL, correlation, weights = NULL, method = "ls", \dots)` | L2 |
| `method` | 默认 `"ls"`；其余取值见 Rd（`"robust"` 走 `mrlm`） | L2 |
| `eBayes(fit, ...)` | `eBayes(fit, proportion = 0.01, stdev.coef.lim = c(0.1,4), trend = FALSE, span = NULL, robust = FALSE, winsor.tail.p = c(0.05,0.1), legacy = NULL)` | L2 |
| `trend` | 默认 `FALSE`（蛋白组方差随丰度变化时通常要开，属本技能判据） | L2 |
| `makeContrasts(...)` | `makeContrasts(\dots, contrasts=NULL, levels)`；`levels` 必填，取自 `design` | L2 |
| `contrasts.fit(...)` | `contrasts.fit(fit, contrasts=NULL, coefficients=NULL)` | L2 |
| `topTable(...)` | `topTable(fit, coef = NULL, number = 10, genelist = fit$genes, adjust.method = "BH", sort.by = "B", resort.by = NULL, p.value = 1, fc = NULL, lfc = NULL, confint = FALSE)` | L2 |
| `number` | **默认 10**（只输出前 10 个）→ 要全表必须 `number = Inf` | L2 |
| `adjust.method` | 形参默认 `"BH"`；原文：`A NULL value will result in the default adjustment method, which is "BH".` | L2 |
| `sort.by` | 默认 `"B"`（按 log-odds 排序）；可选 `"logFC"`、`"AveExpr"`、`"t"`、`"P"/"p"`、`"B"`、`"none"` | L2 |
| `fc` / `lfc` | 可直接给 fold-change 阈值，但官方 Note 明确**不推荐** | L2 |
| `resort.by` | 只改变输出顺序；官方 Note：按 log2FC 重排会破坏 BH 的 FDR 界 | L2 |

## D. DEqMS

| 函数 / 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `spectraCounteBayes(fit, fit.method="loess", coef_col)` | `fit.method` 默认 `"loess"`（`span = 0.75`）；可选 `"nls"`（`y~a+b/x`）、`"spline"`（GCV 选平滑参数）；`coef_col` 不填则对全部系数做 | D2 |
| `fit$count` | **必须手工赋值**：`it should have one additional attribute $count, which stored the peptide or PSM count quantified for the gene` | D2 |
| `VarianceBoxplot(fit, n=, main=, xlab=)` | vignette 用法：`VarianceBoxplot(fit4,n=30,main=...,xlab="PSM count")` | D2 |
| `Residualplot(fit)` | 用于看模型拟合残差 | D2 |
| `outputResult(fit, coef_col=1)` | 默认取第 1 个系数；输出末三列为 `sca.t`、`sca.P.Value`、`sca.adj`（`sca.P.Value adjusted by BH method`） | D2 |

## E. 缺失值填补

| 函数 / 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `impute.MinDet(dataSet.mvs, q = 0.01)` | `q` 默认 `0.01`；以观测分布的低分位数（取代最小值）填补 | I2 |
| `impute.MinProb(dataSet.mvs, q = 0.01, tune.sigma = 1)` | `q = 0.01`、`tune.sigma = 1`；**这就是 Perseus 式"左移 + 按宽度抽样"在 imputeLCMD 中的对应实现** | I2 |
| `impute.QRILC(dataSet.mvs, tune.sigma = 1)` | `tune.sigma = 1`；分位数回归左删失填补 | I2 |
| `impute.wrapper.KNN(...)` | KNN 包装（转调 `impute::impute.knn`） | I2 |
| `impute.MAR.MNAR(...)` / `impute.MAR(...)` | 先判 MAR/MNAR 再分派 | I2 |
| `impute.MQ` | **官方不存在该函数**（NAMESPACE 无此导出，源码检索无命中） | I2 |
| `MSnbase::impute(object, method, ...)` | 方法名由 `MsCoreUtils::imputeMethods()` 给出；示例值：`"min"`、`"QRILC"`、`"MinDet"`、`"MLE"`、`"knn"` | I5 |
| `MSnbase` 的 `MQ` 方法 | **官方文档未提供**该方法名 | I5 |
| Perseus `Width` | `Defines the width of the Gaussian distribution relative to the standard deviation of measured values (default: 0.3).` | X6 |
| Perseus `Down shift` | `Specifies the amount by which the distribution used for the random numbers is shifted downwards (default: 1.8). This is in units of the standard deviation of the valid data.` | X6 |
| Perseus `Mode` | `each expression column separately (default) or on the whole matrix at once ("Total matrix")` | X6 |
| Perseus `Columns` | `default: all expression columns are selected` | X6 |

## F. 富集

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `enricher(gene, ..., universe = NULL, ...)` | `universe` 默认 `NULL`；原文：`background genes. If missing, the all genes listed in the database (eg TERM2GENE table) will be used as background.` | E2 |
| `enrichGO(..., universe, ...)` | 同上 | E2 |
| `enrichKEGG(..., universe, ...)` | 同上 | E2 |
| `pvalueCutoff` / `pAdjustMethod` | 见 `enricher.Rd` 形参表；未在正文改动（本技能只强调 `universe`） | E2 |

## G. 非官方部分：本技能给出的判据（明确标注，不是官方参数）

| 场景 | 判据 | 说明 |
| --- | --- | --- |
| 用 `Intensity` 还是 `LFQ intensity` | 本技能建议 LFQ | 官方只保证两个列名都存在，**未给"用哪个"的建议**；LFQ 的算法语义见 X7 |
| 有效值门槛（一组全重复 或 总样本 50%） | 本技能判据 | 官方文档未提供统一门槛 |
| 0 → NaN | 本技能判据；DIA-NN 侧有官方支持 | DIA-NN 原文：`A zero quantity should be interpreted as indicating that the analyte concentration is below the limit of reliable quantification. If the data needs to be log-transformed, these zeroes can be replaced with NA values.`（N1）；MaxQuant 侧官方未给明文 |
| `|log2FC| >= 1 且 adj.P.Val < 0.05` | 本技能判据 | limma 官方明确不推荐用 fold-change 阈值做筛选（见 C 的 `fc`/`lfc`），正文的写法是"报告阈值"而非"用 limma 内置 fc 参数筛" |
| 置换了多少次（≥200） | 本技能判据 | limma/DEqMS 官方不给置换建议；ropls 侧默认 20（见代谢组技能） |
| 缺失 > 50% 删特征 | 本技能判据 | 官方文档未提供统一门槛 |

## 来源索引

- X1 https://cox-labs.github.io/coxdocs/
- X2 https://cox-labs.github.io/coxdocs/maxquant_instructions.html
- X3 https://cox-labs.github.io/coxdocs/output_tables.html
- X4 https://cox-labs.github.io/coxdocs/perseus_instructions.html
- X5 https://cox-labs.github.io/coxdocs/perseus_activities.html
- X6 https://cox-labs.github.io/coxdocs/replacemissingfromgaussian.html
- X7 https://doi.org/10.1074/mcp.M113.031591
- X8 https://doi.org/10.1038/nature10098
- N1 https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md
- N2 https://github.com/vdemichev/DiaNN
- F1 https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_outputs.html
- S1 https://biognosys.com/software/spectronaut/
- L1 https://bioconductor.org/packages/release/bioc/html/limma.html
- L2 https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz （`man/toptable.Rd`、`man/lmFit.Rd`、`man/ebayes.Rd`、`man/makeContrasts.Rd`、`man/contrasts.fit.Rd`）
- L3 https://bioconductor.org/packages/release/bioc/manuals/limma/man/limma.pdf
- D1 https://bioconductor.org/packages/release/bioc/vignettes/DEqMS/inst/doc/DEqMS-package-vignette.html
- D2 https://bioconductor.org/packages/3.23/bioc/src/contrib/DEqMS_1.30.0.tar.gz
- D3 https://bioconductor.org/packages/release/bioc/html/DEqMS.html
- I1 https://cran.r-project.org/web/packages/imputeLCMD/index.html
- I2 https://cran.r-project.org/src/contrib/imputeLCMD_2.1.tar.gz
- I4 https://bioconductor.org/packages/release/bioc/html/MSnbase.html
- I5 https://bioconductor.org/packages/3.23/bioc/src/contrib/MSnbase_2.38.1.tar.gz
- E1 https://bioconductor.org/packages/release/bioc/html/clusterProfiler.html
- E2 https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz
- E4 https://docs.mygene.info/en/latest/
- T1 https://pyopenms.readthedocs.io/en/latest/
- T2 https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
- T3 https://numpy.org/doc/stable/reference/generated/numpy.log2.html
