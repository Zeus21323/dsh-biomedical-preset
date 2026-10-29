# 官方文档来源清单（逐一抓取确认）

抓取日期：2026-10-29。下表记录本技能每条命令 / 每个参数 / 每条文献判据的来源、版本状态与抓取结果。
R 包一律下载 **release 分支源码 tarball**，从 `man/*.Rd` 与 `vignettes/*.Rmd` 取逐字 `\usage{}`；
正文引用仍给规范 URL。文献类判据给 PubMed / DOI，不引用二手教程。

## 1. XCMS

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| C1 | https://bioconductor.org/packages/release/bioc/vignettes/xcms/inst/doc/xcms-lcms-ms.html | 官方 vignette「LC-MS/MS data analysis with xcms」（规范 URL） | 4.10.1 | OK（HEAD 200） |
| C2 | https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz | 源码 tarball：`man/findChromPeaks-centWave.Rd`、`man/groupChromPeaks.Rd`、`man/adjustRtime.Rd`、`man/do_adjustRtime_peakGroups.Rd`、`vignettes/xcms-lcms-ms.Rmd` | 4.10.1 | OK |
| C3 | https://bioconductor.org/packages/release/bioc/html/xcms.html | 包页 | 4.10.1 | OK |

### 1.1 逐字 `\usage{}`（取自 C2）

```
CentWaveParam(
  ppm = 25,
  peakwidth = c(20, 50),
  snthresh = 10,
  prefilter = c(3, 100),
  mzCenterFun = "wMean",
  integrate = 1L,
  mzdiff = -0.001,
  fitgauss = FALSE,
  noise = 0,
  verboseColumns = FALSE,
  roiList = list(),
  firstBaselineCheck = TRUE,
  roiScales = numeric(),
  extendLengthMSW = FALSE,
  verboseBetaColumns = FALSE
)

PeakDensityParam(
  sampleGroups = numeric(),
  bw = 30,
  minFraction = 0.5,
  minSamples = 1,
  binSize = 0.25,
  ppm = 0,
  maxFeatures = 50,
  rtCenterFun = c("median", "mean", "wMean")
)

PeakGroupsParam(
  minFraction = 0.9,
  extraPeaks = 1,
  smooth = "loess",
  span = 0.2,
  family = "gaussian",
  peakGroupsMatrix = matrix(nrow = 0, ncol = 0),
  subset = integer(),
  subsetAdjust = c("average", "previous")
)
```

### 1.2 关键参数逐字（取自 C2）

- `ppm`：`numeric(1) defining the maximal tolerated m/z deviation in consecutive scans in parts per million (ppm) for the initial ROI definition.`
- `peakwidth`：`numeric(2) with the expected approximate peak width in chromatographic space. Given as a range (min, max) in seconds.`
- `snthresh`：`numeric(1) defining the signal to noise ratio cutoff.`
- `prefilter`：`numeric(2): c(k, I) specifying the prefilter step for the first analysis step (ROI detection). Mass traces are only retained if they contain at least k peaks with intensity >= I.`
- `bw`（PeakDensityParam）：`numeric(1) defining the bandwidth (standard deviation ot the smoothing kernel) to be used. This argument is passed to the [stats::density() method.`
- `minFraction`（PeakDensityParam）：`numeric(1) defining the minimum fraction of samples in at least one sample group in which the peaks have to be present to be considered as a peak group (feature).`
- `minSamples`（PeakDensityParam）：`numeric(1) with the minimum number of samples in at least one sample group in which the peaks have to be detected to be considered a peak group (feature).`

### 1.3 vignette 里的示例参数（取自 C2 的 `vignettes/xcms-lcms-ms.Rmd`）

```
cwp <- CentWaveParam(snthresh = 5, noise = 100, ppm = 10,
                     peakwidth = c(3, 30))
```

> 注意：这是**官方示例**给某份示例数据的取值，不是"推荐默认值"。包默认是
> `snthresh = 10, noise = 0, ppm = 25, peakwidth = c(20, 50)`，两者不要混。

### 1.4 XCMS 能做什么、不能做什么（重要边界）

XCMS 的 `adjustRtime()` / `PeakGroupsParam`（`smooth="loess"`, `span=0.2`）做的是**保留时间（RT）漂移**校正，
以 peak groups 为锚点；它**不**校正"信号强度随进样顺序漂移"。

> 即：正文里"按 injection order 做局部回归（QC-RLSC / LOESS）"这一步**不是 XCMS 的功能**，
> 其方法论来源是 Dunn et al. 2011（见 R2）。XCMS 侧对应的是 RT 校正，不要混为一谈。

## 2. 归一化 / 漂移校正 / 缩放的原始文献

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| R1 | https://pubmed.ncbi.nlm.nih.gov/16808434/ | **PQN**：Dieterle F, Ross A, Schlotterbeck G, Senn H. *Probabilistic quotient normalization as robust method to account for dilution of complex biological mixtures. Application in 1H NMR metabonomics.* Anal Chem. 2006;78(13):4281-90. doi:10.1021/ac051632c | OK（PubMed 记录） |
| R2 | https://pubmed.ncbi.nlm.nih.gov/21720319/ | **QC-RLSC / LOESS 漂移校正**：Dunn WB, Broadhurst D, Begley P, et al. *Procedures for large-scale metabolic profiling of serum and plasma using gas chromatography and liquid chromatography coupled to mass spectrometry.* Nat Protoc. 2011;6(7):1060-83. doi:10.1038/nprot.2011.335 | OK（PubMed 记录） |
| R3 | https://pubmed.ncbi.nlm.nih.gov/16762068/ | **Pareto scaling**：van den Berg RA, Hoefsloot HC, Westerhuis JA, Smilde AK, van der Werf MJ. *Centering, scaling, and transformations: improving the biological information content of metabolomics data.* BMC Genomics. 2006;7:142. doi:10.1186/1471-2164-7-142 | OK（PubMed 记录） |

### 2.1 逐字要点

- PQN（R1 摘要）：`This method is based on the calculation of a most probable dilution factor by looking at the distribution of the quotients of the amplitudes` —— 即"商的中位数"作为稀释因子，不是积分归一化。
  同一摘要还明确否定了积分归一化：`it is shown that integral normalization is a suboptimal method for normalizing spectra from metabonomic studies`。
- R2 摘要：`Here we describe the experimental workflow for long-term and large-scale metabolomic studies involving thousands of human samples with data acquired for multiple analytical batches over many months and years.` —— QC-RLSC 的适用场景就是这种跨批次长周期研究。
- R3 摘要：`Different data pretreatment methods, i.e. centering, autoscaling, pareto scaling, range scaling, vast scaling, log transformation, and power transformation, were tested on a real-life metabolomics data set. They were found to greatly affect the outcome` —— Pareto 与 autoscaling 是并列的两种预处理，效果差异显著，不能互换。

> **任务里给出的 PMID 16526488 不是 PQN 论文**：该 PMID 对应 Indiveri 等 2006 年
> *IEEE Trans Neural Netw* 的 VLSI 脉冲神经元论文。PQN 的正确 PMID 是 **16808434**。
> 同理 **21381064** 不是 QC-RLSC 论文（那是一条 LC-MS/MS 测乙酰辅酶 A 的方法学论文），
> QC-RLSC 正确 PMID 是 **21720319**。

## 3. ropls（PCA / PLS-DA / OPLS-DA）

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| O1 | https://bioconductor.org/packages/release/bioc/vignettes/ropls/inst/doc/ropls-vignette.html | 官方 vignette（含 `sacurine` 示例、`permI` 说明） | 1.44.0 | OK（HEAD 200） |
| O2 | https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz | 源码 tarball：`man/opls.Rd`（逐字 `\usage{}` 与参数说明）、`vignettes/ropls-vignette.Rmd` | 1.44.0 | OK |
| O3 | https://bioconductor.org/packages/release/bioc/html/ropls.html | 包页 | 1.44.0 | OK |

### 3.1 逐字 `\usage{}`（取自 O2 的 `man/opls.Rd`）

```
opls(
  x,
  y = NULL,
  predI = NA,
  orthoI = 0,
  algoC = c("default", "nipals", "svd")[1],
  crossvalI = 7,
  log10L = FALSE,
  permI = 20,
  scaleC = c("none", "center", "pareto", "standard")[4],
  subset = NULL,
  plotSubC = NA,
  fig.pdfC = c("none", "interactive", "myfile.pdf")[2],
  ...
)
```

### 3.2 两个关键默认值（逐字）

- `permI`：`Integer: number of random permutations of response labels to estimate R2Y and Q2Y significance by permutation testing [default is 20 for single response models (without train/test partition), and 0 otherwise]`
- `scaleC`：`Character: either no centering nor scaling ('none'), mean-centering only ('center'), mean-centering and pareto scaling ('pareto'), or mean-centering and unit variance scaling ('standard') [default]`

> **ropls 默认是 `standard`（unit variance / auto scaling），不是 Pareto。**
> 想按代谢组惯例做 Pareto 缩放，必须显式写 `scaleC = "pareto"`；否则正文说的
> "用 Pareto"在代码里根本没发生。

- vignette 对 `permI` 的解释（O1/O2 的 `.Rmd` 逐字）：`The number of permutations is 20 as a compromise between quality control and computation speed; it can be increased with the permI parameter`

## 4. mummichog（PyPI 包 + MetaboAnalyst 模块）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| G1 | https://raw.githubusercontent.com/metabolomics-cloud/mummichog/master/README.md | 官方仓库 README（Mummichog 3 dev 分支）：输入/输出定义、测试命令 `python3 -m mummichog.main -i ... -j ... -a ... -d .`、v2 已冻结在 `mummichog-2.7` 分支 | OK |
| G2 | https://github.com/metabolomics-cloud/mummichog | 仓库首页（组织迁移说明） | OK（API/raw 可达；HTML 直抓曾失败） |
| G3 | https://www.metaboanalyst.ca/resources/vignettes/Functional_Analysis_global_metabolomics.html | MetaboAnalyst 官方 mummichog 模块 vignette（R 版实现）：输入格式、`SetPeakEnrichMethod` / `SetMummichogPval` / `PerformPSEA`、输出文件名 | OK |
| G4 | https://mummichog.org/ | 原项目站点 | 302 跳到 `shuzhao-li.github.io`（个人主页，无 mummichog 技术页） |

### 4.1 逐字要点

- 包定位（G1）：`Mummichog is a Python program for analyzing data from high throughput, untargeted metabolomics. It leverages the organization of metabolic networks to predict functional activity directly from feature tables, bypassing metabolite identification.`
- 输入（G1）：`User supplied features with m/z, rtime, p-value from a statistical test. If no unique feature ID is supplied, row_number will be used as ID.`
- 版本状态（G1）：`The last of version 2 is under branch mummichog-2.7. This is version 3 under development.`
- 命令行（G1 的 "Test run"）：`python3 -m mummichog.main -i tests/ineurons_ttest_1127.tsv -j testneuron -a tests/empCpds_with_annotations.json -d .`
- MetaboAnalyst 侧（G3）：`SetPeakEnrichMethod` 可选 `"mum"`、`"gsea"`、`"integ"`，版本可选 `"v1"`（只用 m/z）/ `"v2"`（m/z + RT）；`PerformPSEA(mSet, "hsa_mfn", "current", 3, 100)`；输出 `mummichog_pathway_enrichment_mummichog.csv` 与 `mummichog_matched_compound_all.csv`；`Resampling, 100 permutations to estimate background ...`
- 质谱要求（G3）：`Currently, MetaboAnalystR only supports the handling of peaks obtained from high-resolution MS instruments such as Orbitrap, or Fourier Transform (FT)-MS instruments as recommended by the original mummichog implementation.`

## 5. MSI 注释置信级

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| M1 | https://pubmed.ncbi.nlm.nih.gov/24039616/ | Sumner LW, Amberg A, Barrett D, et al. *Proposed minimum reporting standards for chemical analysis (CAWG, MSI).* Metabolomics. 2007;3(3):211-221. doi:10.1007/s11306-007-0082-2 | OK |
| M2 | https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/ | 同文 PMC 全文（PMCID: PMC3772505），四级定义所在段落可逐字引用 | OK |

### 5.1 四级定义（M2 全文逐字）

> `Currently, four levels of metabolite identifications can be found in the published metabolomics literature. They include: Identified compounds (see below). Putatively annotated compounds (e.g. without chemical reference standards, based upon physicochemical properties and/or spectral similarity with public/commercial spectral libraries). Putatively characterized compound classes (e.g. based upon characteristic physicochemical properties of a chemical class of compounds, or by spectral similarity to known compounds of a chemical class). Unknown compounds—although unidentified or unclassified these metabolites can still be differentiated and quantified based upon spectral data. Authors should clearly differentiate and report the level of identification rigor for all metabolites reported.`

Level 1 的最低要求（同段逐字）：

> `the following minimum standards for level 1, non-novel metabolite identification are proposed. A minimum of two independent and orthogonal data relative to an authentic compound analyzed under identical experimental conditions are proposed as necessary to validate non-novel metabolite identifications (e.g. retention time/index and mass spectrum, retention time and NMR spectrum, accurate mass and tandem MS...)`

> 关键点：原文**不写 "Level 1/2/3/4" 这个编号**，只给四类名称与顺序；编号是后续文献的通行简化。
> 正文引用时必须把"Level N"说明为"按 MSI 四类顺序编号"，不能声称 M2 原文用了数字编号。

## 6. 代谢物数据库检索入口

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| B1 | https://hmdb.ca/ | HMDB 官方站点（检索入口） | **HTTP 403（拒绝访问）** |
| B2 | https://hmdb.ca/downloads | HMDB 批量下载页 | **HTTP 403** |
| B3 | https://www.genome.jp/kegg/kegg2.html | KEGG 数据库总览（PATHWAY / COMPOUND / BRITE 等） | OK |
| B4 | https://www.genome.jp/kegg/rest/keggapi.html | KEGG REST API 手册（可编程取 compound / pathway） | OK |
| B5 | https://lipidmaps.org/databases/lmsd | LIPID MAPS Structure Database（LMSD） | OK |
| B6 | https://www.lipidmaps.org/resources/lipidweb/index.php | LIPID MAPS LipidWeb（类别/命名体系） | OK（页面仅 1.5 KB，为跳转壳） |

> HMDB 在本环境一律 403（UA/风控），因此**不引用 HMDB 的任何具体字段或下载文件名**，
> 只保留官方入口 URL 并标注抓取失败。KEGG / LIPID MAPS 可取到正文。

## 7. 数据处理与统计（Python 侧）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| P1 | https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html | `pandas.read_csv`（`sep`、`index_col` 等） | OK |
| P2 | https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html | `PCA(n_components=None, *, copy=True, whiten=False, svd_solver='auto', ...)`；`n_components`：`default=None ... if n_components is not set all components are kept: n_components == min(n_samples, n_features)` | OK |
| P3 | https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html | Welch t 检验（`equal_var=False`） | OK |
| P4 | https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html | Mann-Whitney U | OK |
| P5 | https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html | `multipletests(pvals, alpha=0.05, method='hs', ...)`；`fdr_bh : Benjamini/Hochberg (non-negative)` | OK |
| P6 | https://pyopenms.readthedocs.io/en/latest/ | pyopenms 文档首页（原始谱图解卷积、谱库匹配） | OK |

### 7.1 逐字要点

- P2：`n_components int, float or 'mle', default=None`；`if n_components is not set all components are kept: n_components == min(n_samples, n_features)`。
  正文写 `PCA(n_components=5)` 属显式指定，与默认行为不同，需在 provenance 里记录。
- P5：`method` 形参**默认是 `'hs'`（Holm-Sidak）**，不是 BH；要 BH 必须显式 `method='fdr_bh'`。
  可选值清单里 `fdr_bh : Benjamini/Hochberg (non-negative)`。

## 8. 上游峰检测软件（只作输入来源，本技能不调用其命令）

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| U1 | https://systemsomicslab.github.io/mtbinfo.github.io/ | MS-DIAL 官方教程站点（MsdialWorkbench README 指明 `See the tutorial page:`） | OK（HEAD 200，页面 4 KB，正文由 JS 渲染，未取到参数正文） |
| U2 | https://raw.githubusercontent.com/systemsomicslab/MsdialWorkbench/master/README.md | MS-DIAL / MS-FINDER 官方仓库 README（定位、构建、LBM 说明） | OK |
| U3 | http://prime.psc.riken.jp/compms/msdial/main.html | RIKEN MS-DIAL 传统手册页 | **308 跳转 → HTTPS 连接被关闭** |
| U4 | https://mzmine.github.io/mzmine_documentation/latest/ | mzmine 官方文档（Home / Getting started / 全部模块） | OK |
| U5 | https://mzmine.github.io/mzmine_documentation/latest/module_docs/featdet_mass_detection/mass-detection-algorithms.html | 质谱检测算法页（Centroid / Exact mass 等） | OK |
| U6 | https://mzmine.github.io/mzmine_documentation/latest/module_docs/lc-ms_featdet/featdet_adap_chromatogram_builder/adap-chromatogram-builder.html | ADAP chromatogram builder 页 | OK |
| U7 | https://mzmine.github.io/mzmine_documentation/latest/module_docs/norm_intensity/norm_intensity.html | Intensity normalizer 页 | OK |
| U8 | https://mzmine.github.io/mzmine_documentation/latest/module_docs/align_join_aligner/join_aligner.html | Join aligner 页 | OK |

- MS-DIAL 定位（U2）：`MS-DIAL - software for untargeted metabolomics and lipidomics. The program supports data processings for any type of chromatography / scan type mass spectrometry data`
- MS-DIAL 使用入口（U2）：`See the tutorial page: https://systemsomicslab.github.io/mtbinfo.github.io/`
- mzmine 定位（U4）：`mzmine is an open-source and platform-independent software for mass spectrometry (MS) data processing and visualization.`
- mzmine 质谱检测的 `Noise level`（U5 逐字）：`Absolute intensity threshold. Data points below this value are not considered. The effective detection threshold is max(noiseLevel, 2 × lowestNonZeroIntensity) — this automatically rejects peaks sitting at the spectral noise floor even when the noise level is set to zero.`

> 按硬性规则 2：MS-DIAL 的峰检测参数默认值、注释码（annotation codes）在官方可访问文本中
> **未提供可逐字引用的网页**（教程站正文由 JS 渲染、RIKEN 手册页不可达），因此本技能
> **不写任何 MS-DIAL 参数默认值**，只保留"输入可能是 MS-DIAL 导出峰表"这一条路由。

## 9. 统计

| 口径 | 数量 | 说明 |
| --- | --- | --- |
| SKILL.md 正文引用的独立 URL | **22** | 去重后；每个命令块后跟 `> 来源:` 行，判据行内标（来源: URL） |
| `references/official-docs.md` 收录的独立 URL | **45** | 含下表失败清单里的目标 |
| `references/` 三文件合计（去重） | **45** | parameters.md / troubleshooting.md 全部落在 official-docs.md 已收录的集合内 |

**抓取状态**：除下方失败清单外，其余目标均取到可引用的逐字内容。其中
XCMS / ropls 的参数默认值取自 **Bioconductor 官方源码 tarball 的 `man/*.Rd`**；
PQN / QC-RLSC / Pareto / MSI 取自 **PubMed 记录与 PMC 全文**（MSI 四级定义是 PMC 全文逐字摘录）；
mummichog 取自 **仓库 raw README** 与 **MetaboAnalyst 官方 vignette**；
Python 侧取自 **官方 API 文档**。MS-DIAL 参数与注释码、HMDB 字段**未取到任何官方文本**，
按硬性规则 2 明确标注「官方文档未提供」。

**失败或不可读的目标清单**（供后续复核，共 14 项）：

1. `https://hmdb.ca/` → HTTP 403
2. `https://hmdb.ca/downloads` → HTTP 403
3. `https://hmdb.ca/about` → HTTP 403
4. `https://hmdb.ca/faq` → HTTP 403
5. `http://prime.psc.riken.jp/compms/msdial/main.html` → 308 → `基础连接已经关闭: 连接被意外关闭`
6. `https://msdial.readthedocs.io/en/latest/` → HTTP 404（该 readthedocs 项目不存在）
7. `https://www.metaboanalyst.ca/docs/` → HTTP 404
8. `https://doc.metaboanalyst.ca/` → 连接失败
9. `https://www.metaboanalyst.ca/MetaboAnalyst/resources/help.xhtml` → HTTP 404
10. `https://mummichog.org/` → 302 跳转到个人主页（无技术内容）
11. `https://raw.githubusercontent.com/shuzhao-li-lab/mummichog3/master/README.md` → HTTP 404
12. `https://raw.githubusercontent.com/shuzhao-li/mummichog.org/master/docs/index.md` → HTTP 404
13. `https://github.com/shuzhao-li-lab/mummichog` → 连接被意外关闭
14. `https://www.lipidmaps.org/resources/lipidweb/index.php` → 200 但仅 1.5 KB 跳转壳
