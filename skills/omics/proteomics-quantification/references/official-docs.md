# 官方文档来源清单（逐一抓取确认）

抓取日期：2026-10-29。下表记录本技能每条命令 / 每个列名的来源页面、版本状态与抓取结果。
Bioconductor 包一律下载 **release 分支源码 tarball**，从 `man/*.Rd` 与 `vignettes/*.Rmd` 取逐字 `\usage{}`，
避免 PDF/DOCX 无法解析的问题；正文引用仍给规范 URL。

## 1. MaxQuant / Perseus（Cox Lab，原 coxdocs.org，现址 cox-labs.github.io/coxdocs）

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| X1 | https://cox-labs.github.io/coxdocs/ | Cox Docs 入口（MaxQuant / Perseus / Andromeda 三套文档） | 2025-10-14 发布 | OK |
| X2 | https://cox-labs.github.io/coxdocs/maxquant_instructions.html | MaxQuant 文档目录（含 Output Tables、Glossary、Viewer、Andromeda） | 同上 | OK |
| X3 | https://cox-labs.github.io/coxdocs/output_tables.html | 全部输出表逐列说明：Summary / Evidence / Peptide / Site / **Protein Groups** / All Peptides / msScans / MzRange / msmsScans / msms / AIF msms | 同上 | OK |
| X4 | https://cox-labs.github.io/coxdocs/perseus_instructions.html | Perseus 文档首页（含「Cite」「Learn」、perseus google group 入口） | 同上 | OK |
| X5 | https://cox-labs.github.io/coxdocs/perseus_activities.html | Perseus 全部 activity 索引；5.7 Imputation 下三个 activity | 同上 | OK |
| X6 | https://cox-labs.github.io/coxdocs/replacemissingfromgaussian.html | **Replace missing values from normal distribution**：Width / Down shift / Mode / Columns 四个参数的逐字说明与默认值 | 同上 | OK |

> `https://www.maxquant.org/` 与 `https://www.maxquant.org/maxquant/` 在本环境 TLS 握手失败
> （`基础连接已经关闭: 未能为 SSL/TLS 安全通道建立信任关系`），`http://maxquant.org/` 仅 308 跳转到 https，
> 故一律改用 Cox Lab 的 coxdocs 站点作为 MaxQuant / Perseus 的一手文档来源。

### 1.1 `proteinGroups.txt` 各列在官方文档中的**实际**覆盖情况

这一条很关键：Cox Docs 的 Protein Groups 表**只给了列名，部分列名后面没有描述文字**。逐列核对结果：

| 列名（`proteinGroups.txt`） | 官方文档是否给出描述 | 官方原文 / 说明 |
| --- | --- | --- |
| `Reverse` | **有** | `When marked with '+', this particular protein group contains no protein, made up of at least 50% of the peptides of the leading protein, with a peptide derived from the reversed part of the decoy database. These should be removed for further data analysis. The 50% rule is in place to prevent spurious protein hits to erroneously flag the protein group as reverse.` |
| `Potential contaminant` | **有** | `When marked with '+', this particular protein group was found to be a commonly occurring contaminant. These should be removed for further data analysis.` |
| `Only identified by site` | **有** | `When marked with '+', this particular protein group was identified only by a modification site.` |
| `Q-value` | **有** | `This is the ratio of reverse to forward protein groups.` |
| `Score` | **有** | `Protein score which is derived from peptide posterior error probabilities.` |
| `Peptides` / `Razor + unique peptides` / `Unique peptides` | **有** | `The total number of peptide sequences associated with the protein group (i.e. for all the proteins in the group).` 等 |
| `"Peptides" + exp` / `"Razor + unique peptides" + exp` / `"Unique peptides" + exp` | **有** | `"Number of peptides (distinct peptide sequences) in experiment" + exp` |
| `Sequence coverage [%]` | **有** | `Percentage of the sequence that is covered by the identified peptides of the best protein sequence contained in the group.` |
| `"LFQ intensity" + exp`（含 `LFQ intensity L/M/H`） | **无（描述单元格为空）** | 列名在表中出现，描述为空 → **官方文档未提供列语义**；算法语义见 MaxLFQ 原文（X7） |
| `iBAQ`（含 `iBAQ L/M/H`、`"iBAQ" + exp`） | **无（描述单元格为空）** | 同上 → 语义见 iBAQ 原文（X8） |
| `Intensity <raw>` | **未列出** | Protein Groups 表**没有**裸 `Intensity` 行；`Intensity` 的描述只出现在 msms / evidence / site / All Peptides 表中，原文为 `Summed up eXtracted Ion Current (XIC) of all isotopic clusters associated with the identified AA sequence...` → **Protein Groups 的 `Intensity <raw>` 官方文档未提供列描述** |
| `AVALON`、`MS/MS Count`、`Fraction average`、`Mod. peptide IDs`、`Evidence IDs` | **无（描述为空）** | 同上 |

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| X7 | https://doi.org/10.1074/mcp.M113.031591 | Cox et al. 2014, **MaxLFQ**（"Accurate Proteome-wide Label-free Quantification by Delayed Normalization and Maximal Peptide Ratio Extraction, Termed MaxLFQ", MCP 13:2513-2526）——`LFQ intensity` 的算法定义 | 未抓取正文（DOI 记录取自 X2 参考文献列表） |
| X8 | https://doi.org/10.1038/nature10098 | Schwanhäusser et al. 2011, Nature 473:337-342 —— `iBAQ` 的算法定义（intensity-based absolute quantification） | 未抓取正文（DOI 为通用引用，未在本环境解析） |

> 结论：**不要**把 `LFQ intensity` / `iBAQ` / `Intensity <raw>` 的语义说成「Cox Docs 有明确定义」。
> 官方只保证列名存在；语义要引 MaxLFQ / iBAQ 原始文献。三个过滤标志（`Reverse`、`Potential contaminant`、
> `Only identified by site`）才是 Cox Docs 逐字写明「应当剔除」的列。

## 2. DIA-NN

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| N1 | https://raw.githubusercontent.com/vdemichev/DiaNN/master/README.md | 官方 README 全文（227,581 字节）：Installation / Getting started / Output / **Command-line reference** / **Main output reference** / Filtering / Quantification / Normalisation / Troubleshooting | 2.7.0 | OK（全文下载后本地检索） |
| N2 | https://github.com/vdemichev/DiaNN | 仓库首页（release 页、.msi / Linux zip 分发） | 2.7.0 | OK |
| N3 | https://github.com/vdemichev/DiaNN/wiki/Parameters | 旧 Wiki 的参数页 | — | **连接失败**（`TypeError: fetch failed`） |

### 2.1 主报告列（逐字取自 N1「Main output reference」）

- `**Precursor.Quantity** MS2-based quantity of the precursor (charged peptide), non-normalised`
- `**Precursor.Normalised** MS2-based quantity of the precursor (charged peptide), normalised, if normalisation is not disabled`
- `**Q.Value** run-specific precursor q-value`
- `**Global.Q.Value** global precursor q-value`
- `**PG.Q.Value** run-specific q-value for the protein group, channel-specific`
- `**Global.PG.Q.Value** global q-value for the protein group`
- `**PG.TopN** Normalised protein group quantity calculated using Top N method (default N = 1...)`
- `**PG.MaxLFQ** QuantUMS or MaxLFQ normalised quantity for the protein group, channel-specific`
- `**Ms1.Area** non-normalised MS1 peak area` / `**Ms1.Normalised**`

> **重要**：DIA-NN 2.x 的官方列清单里**没有 `PG.Quantity`**。蛋白层面的量是 `PG.TopN`
> （Legacy 模式下）与 `PG.MaxLFQ`（推荐）。`PG.Quantity` 是 1.8 及更早版本 `report.tsv` 的列名，
> 本环境能取到的官方 2.x 文本中检索不到。

### 2.2 主报告格式（逐字取自 N1「Output」）

- `The report is in .parquet format -- a compact compressed tabular format that can be accessed with the R `arrow` or Python `polars` packages`
- `To quickly inspect protein quantities using software such as MS Excel, DIA-NN generates ready-to-use .pg_matrix.tsv and .unique_genes_matrix.tsv tab-separated tables.`
- 矩阵过滤原文：`They are filtered at 1% FDR, using global q-values for protein groups and both global and run-specific q-values for precursors. Additional 5% run-specific protein-level FDR filter is applied to the protein matrices, use --matrix-spec-q to adjust it.`

> 结论：`report.tsv` 同样是 1.8 时代的主报告名；2.x 主报告是 `.parquet`，TSV 只作为
> `.pg_matrix.tsv` / `.gg_matrix.tsv` / `.unique_genes_matrix.tsv` / `pr_matrix` 这类矩阵出现。

### 2.3 q 值相关（逐字取自 N1「Command-line reference」与「Filtering the main report」）

- `**--qvalue [X]** specifies the precursor-level q-value filtering threshold for the main report` —— **该条未写默认值**
- `**--protein-quant-qvalue [X]** a hint to DIA-NN indicating the preferred q-value threshold at which precursors will be prioritised for protein quantification, default value is 0.01`
- `**--quant-qvalue [X]** ... default value is 0.01`
- `**--quant-pep [X]** ... default value is 0.05`
- `**--top [N]** set N for the Top N protein quantification, default N = 1`
- `**--quant-fr [N]** ... Default value is 6`
- Filtering 小节：`* **Q.Value** at 0.01 - 0.05. The default precursor FDR setting in DIA-NN is 5%, meaning the main report is filtered already at Q.Value <= 0.05.`
- `* **Global.Q.Value** at 0.01.` / `* **Global.PG.Q.Value** at 0.01.` / `* **PG.Q.Value** at 0.01 to 0.05, typically 0.05 is sufficient.`

> 所以 `Q.Value ≤ 0.01` **不是** DIA-NN 的默认值，而是官方推荐的更严过滤档；默认前体 FDR 是 5%。
> 要 1% 必须显式 `--qvalue 0.01`（或在主报告上再筛 `Q.Value <= 0.01`）。

### 2.4 零值语义（逐字取自 N1「Quantification」）

- `**Zero quantities**. Any of the quantities produced by DIA-NN may be zero. A zero quantity should be interpreted as indicating that the analyte concentration is below the limit of reliable quantification. If the data needs to be log-transformed, these zeroes can be replaced with NA values.`
- 矩阵侧：`Such zero quantities are omitted from protein/gene matrices.`

> 这条给了「0 → NaN」一个官方依据，且限定在 DIA-NN 语境；MaxQuant 的 0 语义，官方文档未提供明文。

### 2.5 归一化与差异分析（逐字取自 N1「Normalisation」「Fold-changes」）

- `**Detecting normalisation errors**. ... For example, the number of points with positive and negative fold-changes on a volcano plot should almost always be balanced. ... It is best to ... Calculate log2 fold-change of each analyte ... Plot the histogram ... Indicate the median and half sample mode (use hsm() function of the modeest R package) on the histogram. Both these values should be close to 0.`
- `**Fold-changes**. ... Important: fold-change cutoffs must be applied after adjusting the p-values via multiple testing correction, not before.`

## 3. FragPipe / MSFragger（Nesvilab）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| F1 | https://fragpipe.nesvilab.org/docs/tutorial_fragpipe_outputs.html | 「Guide to FragPipe results」：psm/ion/peptide/protein/**combined_protein.tsv** 等全部主报表逐列说明 | OK |

### 3.1 `combined_protein.tsv` 列名（逐字取自 F1）

- `**Protein**` / `**Protein ID**` / `**Entry Name**` / `**Gene**` / `**Protein Length**` / `**Coverage**` / `**Organism**` / `**Protein Existence**` / `**Description**` / `**Protein Probability**` / `**Top Peptide Probability**`
- `**Combined Total Peptides** number of peptides (stripped sequences) that can be mapped to the protein...`
- `**Combined Spectral Count** number of PSMs corresponding to the **razor peptides**.`
- `**Combined Unique Spectral Count**` / `**Combined Total Spectral Count**`
- `**[experiment] Spectral Count**` / `**[experiment] Unique Spectral Count**` / `**[experiment] Total Spectral Count**`
- `**[experiment] Intensity** normalized (by default) protein intensity using the **razor peptides** (from the top-N algorithm)`
- `**[experiment] Unique Intensity**` / `**[experiment] Total Intensity**`
- `**[experiment] MaxLFQ Intensity** normalized (by default) protein intensity using the **razor peptides** (from the MaxLFQ method)`
- `**[experiment] MaxLFQ Unique Intensity**` / `**[experiment] MaxLFQ Total Intensity**`
- `**Indistinguishable Proteins** proteins that cannot be distinguished from the selected protein given all sequences/evidence identified in the experiment`

> 注意：官方列名带 **`[experiment]` 前缀**（实验组名），没有裸的 `Intensity` / `MaxLFQ Intensity` 列；
> 交叉核对"每样本一列"时要按前缀展开，不能按字面去找 `Intensity`。

## 4. Spectronaut（Biognosys）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| S1 | https://biognosys.com/software/spectronaut/ | 产品页（功能、版本、许可证入口） | OK |
| S2 | https://help.biognosys.ch/ | 期望的在线帮助/手册站点 | **连接失败**（`请求被中止: 连接被意外关闭`） |
| S3 | `*_Report.tsv` 的列名（`PG.Quantity`、`EG.QValue` 等） | 属商业软件安装包内附的 *Spectronaut User Manual* | **官方文档未提供可直接访问的网页来源** |

> 按本技能硬性规则 2：Spectronaut 的报表列语义，本环境**无法从官方可访问文档取到逐字说明**。
> 正文只保留"输入可以是 Spectronaut 报表"这一条路由，并标注为未验证。

## 5. limma

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| L1 | https://bioconductor.org/packages/release/bioc/html/limma.html | 包页（版本、依赖、Documentation 栏） | 3.68.5 | OK |
| L2 | https://bioconductor.org/packages/3.23/bioc/src/contrib/limma_3.68.5.tar.gz | **官方源码 tarball**：`man/lmFit.Rd`、`man/ebayes.Rd`、`man/makeContrasts.Rd`、`man/contrasts.fit.Rd`、`man/toptable.Rd`（逐字 `\usage{}` 与 Note） | 3.68.5 | OK |
| L3 | https://bioconductor.org/packages/release/bioc/manuals/limma/man/limma.pdf | 参考手册 PDF（同上 Rd 的排版版） | 3.68.5 | 未解析（PDF） |
| L4 | https://bioconductor.org/packages/release/bioc/vignettes/limma/inst/doc/usersguide.pdf | User's Guide（limma 唯一官方教程，PDF） | 3.68.5 | 未解析（PDF） |

> 本环境 `raw.githubusercontent.com/Bioconductor/limma/...`（man/*.Rd）返回 404，故改用 Bioconductor
> 官方源码 tarball 取 Rd；内容与 L1/L3 发布版一一对应。

### 5.1 逐字 `\usage{}`（取自 L2）

```
lmFit(object, design = NULL, ndups = NULL, spacing = NULL, block = NULL, correlation,
      weights = NULL, method = "ls", \dots)

eBayes(fit, proportion = 0.01, stdev.coef.lim = c(0.1,4),
       trend = FALSE, span = NULL,
       robust = FALSE, winsor.tail.p = c(0.05,0.1), legacy = NULL)

makeContrasts(\dots, contrasts=NULL, levels)

contrasts.fit(fit, contrasts=NULL, coefficients=NULL)

topTable(fit, coef = NULL, number = 10, genelist = fit$genes,
         adjust.method = "BH", sort.by = "B", resort.by = NULL,
         p.value = 1, fc = NULL, lfc = NULL, confint = FALSE)
```

### 5.2 `adjust.method` 的默认值（`man/toptable.Rd` 逐字）

- `\item{adjust.method}{method used to adjust the p-values for multiple testing. Options, in increasing conservatism, include "none", "BH", "BY" and "holm". See \link{p.adjust} for the complete list of options. **A NULL value will result in the default adjustment method, which is "BH".**}`
- details 段：`The "BH" method, which controls the expected false discovery rate (FDR) below the specified value, is the default adjustment method because it is the most likely to be appropriate for microarray studies.`

> 即：`adjust.method` 形参默认就是 `"BH"`；显式写 `"BH"` 只是把默认值写死，两者等价。

### 5.3 `topTable` 的两个官方警告（`man/toptable.Rd` 的 Note，逐字）

- `Although \code{topTable} enables users to set both p-value and fold-change cutoffs, the use of fold-change cutoffs is not generally recommended. If the fold changes and p-values are not highly correlated, then the use of a fold change cutoff can increase the false discovery rate above the nominal level.`
- `In general, the adjusted p-values returned by \code{adjust.method="BH"} remain valid as FDR bounds only when the genes remain sorted by p-value. Resorting the table by log-fold-change can increase the false discovery rate above the nominal level for genes at the top of resorted table.`

## 6. DEqMS

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| D1 | https://bioconductor.org/packages/release/bioc/vignettes/DEqMS/inst/doc/DEqMS-package-vignette.html | 官方 vignette（规范 URL；注意文件名是 `DEqMS-package-vignette.html`，不是 `DEqMS.html`） | 1.30.0 | OK |
| D2 | https://bioconductor.org/packages/3.23/bioc/src/contrib/DEqMS_1.30.0.tar.gz | 源码 tarball：`man/spectraCounteBayes.Rd`、`man/outputResult.Rd`、`vignettes/DEqMS-package-vignette.Rmd` | 1.30.0 | OK |
| D3 | https://bioconductor.org/packages/release/bioc/html/DEqMS.html | 包页 | 1.30.0 | OK |

### 6.1 逐字 `\usage{}`（取自 D2）

```
spectraCounteBayes(fit, fit.method="loess", coef_col)

outputResult(fit, coef_col=1)
```

- `fit.method`：`the method used to fit variance against the number of peptides/PSM count quantified. Two available methods: "loess","nls" and "spline". default "loess"."loess" uses loess and span = 0.75, "nls" uses a explicit formula y~a+b/x. "spline" uses smooth.spline and "generalized cross-validation" for smoothing parameter computation. ... In most of time, "loess" is sufficient.`
- `fit`：`an list object produced by Limma eBayes function, it should have one additional attribute $count, which stored the peptide or PSM count quantified for the gene in label-free or isobaric labelled data.`
- `outputResult` 返回值：`a data frame object with the last three columns being: sca.t - Peptide or Spectra Count Adjusted posterior t-value; sca.P.Value - Adjusted posterior p-value; **sca.adj - sca.P.Value adjusted by BH method**`
- vignette 逐字用法（D2 的 `.Rmd`）：`fit3$count = psm.count.table[rownames(fit3$coefficients),"count"]` → `fit4 = spectraCounteBayes(fit3)` → `DEqMS.results = outputResult(fit4,coef_col = 1)`；并配 `VarianceBoxplot(fit4,n=30,main=...,xlab="PSM count")`。

> 注意：`fit$count` 是**必须手工挂上去**的，DEqMS 不会自己算；这也是正文"按肽段数重估先验"的实际含义。

## 7. 缺失值填补：imputeLCMD / MSnbase

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| I1 | https://cran.r-project.org/web/packages/imputeLCMD/index.html | CRAN 包页 | 2.1 | OK |
| I2 | https://cran.r-project.org/src/contrib/imputeLCMD_2.1.tar.gz | 源码 tarball：`man/impute.MinDet.Rd`、`man/impute.MinProb.Rd`、`man/impute.QRILC.Rd`、`NAMESPACE` | 2.1 | OK |
| I3 | https://cran.r-project.org/web/packages/imputeLCMD/imputeLCMD.pdf | 参考手册 PDF | 2.1 | 未解析（PDF） |
| I4 | https://bioconductor.org/packages/release/bioc/html/MSnbase.html | MSnbase 包页 | 2.38.1 | OK |
| I5 | https://bioconductor.org/packages/3.23/bioc/src/contrib/MSnbase_2.38.1.tar.gz | 源码 tarball：`man/impute.Rd` | 2.38.1 | OK |

### 7.1 imputeLCMD 的**真实**函数名（取自 I2 的 `NAMESPACE` 与 man）

```
export(impute.MAR)
export(impute.MAR.MNAR)
export(impute.MinDet)
export(impute.MinProb)
export(impute.QRILC)
export(impute.ZERO)
export(impute.wrapper.KNN)
export(impute.wrapper.MLE)
export(impute.wrapper.SVD)
```

逐字 `\usage{}`：

```
impute.MinDet(dataSet.mvs, q = 0.01)
impute.MinProb(dataSet.mvs, q = 0.01, tune.sigma = 1)
impute.QRILC(dataSet.mvs, tune.sigma = 1)
```

> **imputeLCMD 2.1 没有 `impute.MQ`，也没有任何名为 `MQ` 的导出函数**（`R/` 目录全文检索 `impute.MQ`
> 与 `"MQ"` 均无命中）。"左移 + 抽样"在 imputeLCMD 里的对应物是 `impute.MinProb`（`tune.sigma` 控制宽度），
> 不是 `MQ`。

### 7.2 MSnbase

- `\S4method{impute}{MSnSet}(object, method, \dots)`
- `\item{method}{\code{character(1)} defining the imputation method. See \code{MsCoreUtils::imputeMethods()} for available ones. See \code{\link[MsCoreUtils:impute_matrix]{MsCoreUtils::impute_matrix()}} for details.}`
- 示例中出现的 method 取值：`"min"`、`"QRILC"`、`"MinDet"`、`"MLE"`、`"knn"`。

> 即 MSnbase 的 `MinDet`/`QRILC` 是**转调 MsCoreUtils**，函数名与本包无关；
> MSnbase 自己**没有** `MQ` 方法名。

## 8. 富集与 ID 映射

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| E1 | https://bioconductor.org/packages/release/bioc/html/clusterProfiler.html | clusterProfiler 包页 | 4.20.3 | OK |
| E2 | https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz | 源码 tarball：`man/enricher.Rd` / `man/enrichGO.Rd` / `man/enrichKEGG.Rd` 的 `universe` 逐字说明 | 4.20.3 | OK |
| E3 | https://bioconductor.org/packages/release/bioc/vignettes/clusterProfiler/inst/doc/clusterProfiler.html | 官方 vignette（本环境取到的 HTML 仅 7.5 KB，为脚本壳，未取到正文） | 4.20.3 | 部分（未取到正文） |
| E4 | https://docs.mygene.info/en/latest/ | mygene.info 官方文档（本包 MCP 工具 `genes_ontologies_mygene_query` 对应的上游 API） | — | OK |

`universe` 逐字（E2，`enricher.Rd` / `enrichGO.Rd` / `enrichKEGG.Rd` 同文）：

> `\item{universe}{background genes. If missing, the all genes listed in the database (eg TERM2GENE table) will be used as background.}`

> 这条是正文"背景集必须是本次检出到的蛋白、不能留空"的官方依据：留空 = 用数据库全部基因当背景。

## 9. 其他工具（仅路由用，本技能不直接调用）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| T1 | https://pyopenms.readthedocs.io/en/latest/ | pyopenms 文档首页（原始 RAW/DIA 谱图解析、肽段鉴定） | OK |
| T2 | https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html | `pandas.read_csv`（`sep`、`low_memory` 等） | OK |
| T3 | https://numpy.org/doc/stable/reference/generated/numpy.log2.html | `numpy.log2` | OK |

## 10. 统计

| 口径 | 数量 | 说明 |
| --- | --- | --- |
| SKILL.md 正文引用的独立 URL | **16** | 去重后；每条命令块 / 表格后有 `> 来源:` 或行内（来源: URL） |
| `references/official-docs.md` 收录的独立 URL | **45** | 含下表失败清单里的目标 |
| `references/` 三文件合计（去重） | **45** | parameters.md / troubleshooting.md 全部落在 official-docs.md 已收录的集合内 |

**抓取状态**：除下方「失败或不可读的目标清单」列出的目标外，其余目标均取到可引用的逐字内容。
其中 limma / MSnbase / clusterProfiler / DEqMS 的函数签名与参数说明一律取自 **Bioconductor 官方源码 tarball 的
`man/*.Rd`**（PDF 参考手册与 HTML vignette 未解析）；imputeLCMD 取自 **CRAN 源码 tarball**；
DIA-NN 取自 **raw README 全文**；FragPipe 取自官方 results guide 页。
Spectronaut 的报表列语义**未取到任何官方文本**，按硬性规则 2 在正文与 references 里明确标注。

**失败或不可读的目标清单**（供后续复核，共 15 项）：

1. `https://www.maxquant.org/` → TLS 信任失败
2. `https://www.maxquant.org/maxquant/` → TLS 信任失败
3. `http://maxquant.org/` → 308 永久跳转到 https（跳转后仍 TLS 失败）
4. `https://coxdocs.org/doku.php?id=maxquant:start` → 超时
5. `http://www.coxdocs.org/doku.php?id=perseus:start` → 超时
6. `https://github.com/vdemichev/DiaNN/wiki/Parameters` → `TypeError: fetch failed`
7. `https://github.com/vdemichev/DiaNN`（HTML 页面直抓） → `TypeError: fetch failed`（raw README 成功）
8. `https://raw.githubusercontent.com/Bioconductor/limma/master/man/topTable.Rd` → HTTP 404
9. `https://api.github.com/repos/Bioconductor/limma` → HTTP 404（该镜像路径不存在）
10. `https://bioconductor.org/packages/release/bioc/vignettes/DEqMS/inst/doc/DEqMS.html` → HTTP 404（真实文件名是 `DEqMS-package-vignette.html`）
11. `https://rdrr.io/bioc/limma/man/topTable.html` → HTTP 404
12. `https://www.rdocumentation.org/packages/limma/versions/3.62.0/topics/topTable` → HTTP 404
13. `https://help.biognosys.ch/` → 连接被意外关闭（Spectronaut 手册）
14. `https://bioconductor.org/packages/3.23/bioc/src/contrib/MsCoreUtils_1.22.0.tar.gz` → 下载失败（版本号猜测错误，未继续尝试）
15. `https://prime.psc.riken.jp/compms/msdial/main.html` → 308/连接关闭（与代谢组技能共用，见该技能 references）
