# 参数对照表（默认值与说明逐字取自官方文档）

来源缩写见文末「来源索引」。凡官方未给默认值者标注「官方未给默认值」；
凡官方没有可访问文本者标注「官方文档未提供」。

## A. XCMS：峰检测（`findChromPeaks` + `CentWaveParam`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `ppm` | `maximal tolerated m/z deviation in consecutive scans in parts per million (ppm) for the initial ROI definition`；默认 `25` | C2 |
| `peakwidth` | `numeric(2) with the expected approximate peak width in chromatographic space. Given as a range (min, max) in seconds.`；默认 `c(20, 50)` | C2 |
| `snthresh` | `signal to noise ratio cutoff`；默认 `10` | C2 |
| `prefilter` | `c(k, I) ... Mass traces are only retained if they contain at least k peaks with intensity >= I.`；默认 `c(3, 100)` | C2 |
| `mzCenterFun` | 默认 `"wMean"`（强度加权 m/z 均值）；可选 `"mean"`、`"apex"` | C2 |
| `integrate` | 默认 `1L` | C2 |
| `mzdiff` | 默认 `-0.001` | C2 |
| `noise` | 默认 `0` | C2 |
| `fitgauss` | 默认 `FALSE` | C2 |
| `firstBaselineCheck` | 默认 `TRUE` | C2 |
| `extendLengthMSW` | 默认 `FALSE` | C2 |
| 官方示例（不是默认值） | `cwp <- CentWaveParam(snthresh = 5, noise = 100, ppm = 10, peakwidth = c(3, 30))` | C2（vignette） |

## B. XCMS：峰分组（`groupChromPeaks` + `PeakDensityParam`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `bw` | `numeric(1) defining the bandwidth (standard deviation ot the smoothing kernel) to be used. This argument is passed to the [stats::density() method.`；默认 `30` | C2 |
| `minFraction` | `minimum fraction of samples in at least one sample group in which the peaks have to be present to be considered as a peak group (feature)`；默认 `0.5` | C2 |
| `minSamples` | `minimum number of samples in at least one sample group in which the peaks have to be detected to be considered a peak group`；默认 `1` | C2 |
| `binSize` | `size of the overlapping slices in m/z dimension`；默认 `0.25` | C2 |
| `ppm` | 默认 `0` | C2 |
| `maxFeatures` | 默认 `50` | C2 |
| `sampleGroups` | 默认 `numeric()`（空 → 全部样本视为一组） | C2 |

> `minFraction` 的官方定义是"**至少一个样本组内**的比例"，看着像可以放宽；
> 但正文明写"≥3 个 pooled QC 且 QC 必须在场"，所以真正决定 QC 是否成簇的是
> `sampleGroups` 有没有把 QC 单独成组，而不是把 `minFraction` 调低。

## C. XCMS：保留时间校正（`adjustRtime` + `PeakGroupsParam`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `minFraction` | 默认 `0.9`（锚点 peak group 至少要在 90% 的样本里出现） | C2 |
| `extraPeaks` | 默认 `1` | C2 |
| `smooth` | 默认 `"loess"`；可选 `"linear"` | C2 |
| `span` | 默认 `0.2`（loess 平滑窗口） | C2 |
| `family` | 默认 `"gaussian"`；可选 `"symmetric"` | C2 |
| `subsetAdjust` | 默认 `c("average", "previous")` | C2 |

> 再次强调：这一组参数做的是 **RT 漂移**校正，不是"强度随进样顺序漂移"的校正。
> 强度漂移校正（QC-RLSC）的方法来源是 R2，XCMS 官方文档不提供该功能。

## D. 归一化 / 漂移校正 / 缩放

| 方法 / 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| PQN（probabilistic quotient normalization） | 以"商分布的最可能稀释因子"归一；原文：`This method is based on the calculation of a most probable dilution factor by looking at the distribution of the quotients of the amplitudes`；原文并否定积分归一化：`integral normalization is a suboptimal method` | R1 |
| QC-RLSC（QC-based robust LOESS signal correction） | 以 pooled QC 在进样顺序上的 LOESS 拟合作为漂移曲线，再回代到所有样本；适用于 `thousands of human samples with data acquired for multiple analytical batches over many months and years` | R2 |
| Pareto scaling | `(x - mean) / sqrt(sd)`；与 autoscaling（除以 sd）、range scaling、vast scaling 并列为可选预处理，原文：`They were found to greatly affect the outcome` | R3 |
| ropls `scaleC` | `mean-centering and pareto scaling ('pareto'), or mean-centering and unit variance scaling ('standard') [default]` → **ropls 默认是 standard，不是 pareto** | O2 |

## E. ropls：`opls()`

| 参数 / 函数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `opls(x, y = NULL, ...)` | 见 `\usage{}`；`y` 为因子 → (O)PLS-DA，为数值 → (O)PLS | O2 |
| `predI` | `number of components ... to extract; for OPLS, predI is (automatically) set to 1`；默认 `NA` | O2 |
| `orthoI` | `number of orthogonal components (for OPLS only)`；默认 `0`（即 PLS）；OPLS-DA 官方示例 `orthoI = NA`（自动） | O2 |
| `crossvalI` | `number of cross-validation segments (default is 7); The number of samples (rows of 'x') must be at least >= crossvalI` | O2 |
| `permI` | `number of random permutations of response labels to estimate R2Y and Q2Y significance by permutation testing [default is 20 for single response models (without train/test partition), and 0 otherwise]` | O2 |
| `scaleC` | 默认 `"standard"`（mean-centering + unit variance）；Pareto 需显式 `scaleC = "pareto"` | O2 |
| `log10L` | 默认 `FALSE`（是否对数据取 log10） | O2 |
| `subset` | 训练/测试划分的观测索引；**给了 `subset` 时 `permI` 默认变 0**（因为不是 single response model） | O2 |
| `getVipVn(model)` | 取 VIP（OPLS 侧文档写作 VIP4,p，Galindo-Prieto et al. 2014） | O2 |
| `getScoreMN` / `getLoadingMN` | 取得分 / 载荷矩阵 | O2 |
| 官方 OPLS-DA 示例 | `sacurine.oplsda <- opls(sacurine$dataMatrix, genderFc, predI = 1, orthoI = NA)` | O2 |
| 置换次数建议 | `The number of permutations is 20 as a compromise between quality control and computation speed; it can be increased with the permI parameter` | O2（vignette） |

> 正文写"置换检验 ≥200 次"，**不是**官方默认值：官方默认 20，且明说 20 是"质量与速度的折中"。
> 写 ≥200 属于本技能的更严判据，必须在报告里说明"高于 ropls 默认 20"。

## F. mummichog

| 参数 / 函数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| Python 包入口 | `python3 -m mummichog.main -i <peaklist> -j <jobname> -a <annotation.json> -d <outdir>` | G1 |
| 输入要求 | `User supplied features with m/z, rtime, p-value from a statistical test. If no unique feature ID is supplied, row_number will be used as ID.` | G1 |
| 版本状态 | `The last of version 2 is under branch mummichog-2.7. This is version 3 under development.` | G1 |
| MetaboAnalyst `SetPeakEnrichMethod(mSet, method, version)` | `method` 取 `"mum"` / `"gsea"` / `"integ"`；`version` 取 `"v1"`（只用 m/z）或 `"v2"`（m/z + RT） | G3 |
| MetaboAnalyst `SetMummichogPval(mSet, pval)` | 用于划分显著 / 不显著的 m/z 特征；示例取 p 值最小的 10% 分位 | G3 |
| MetaboAnalyst `PerformPSEA(mSet, model, version, , perms)` | 示例 `PerformPSEA(mSet, "hsa_mfn", "current", 3, 100)`；日志出现 `Resampling, 100 permutations to estimate background ...` | G3 |
| MetaboAnalyst 质量精度 | 示例 `UpdateInstrumentParameters(mSet, 15.0, "mixed", "yes", 0.02)`（15 ppm、正负混合、p 阈值 0.02） | G3 |
| 仪器限制 | `only supports the handling of peaks obtained from high-resolution MS instruments such as Orbitrap, or Fourier Transform (FT)-MS instruments` | G3 |
| 输出文件 | `mummichog_pathway_enrichment_mummichog.csv`（含 hits、raw p、EASE score、permutation 校正 p）、`mummichog_matched_compound_all.csv` | G3 |

## G. 统计（Python 侧）

| 函数 / 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `PCA(n_components=None, ...)` | `n_components ... default=None`；`if n_components is not set all components are kept: n_components == min(n_samples, n_features)` | P2 |
| `ttest_ind(a, b, equal_var=...)` | `equal_var=False` → Welch t（不假设等方差） | P3 |
| `mannwhitneyu(x, y, ...)` | 非参数两样本检验 | P4 |
| `multipletests(pvals, alpha=0.05, method='hs')` | **`method` 默认 `'hs'`（Holm-Sidak），不是 BH**；BH 需显式 `method='fdr_bh'`（`fdr_bh : Benjamini/Hochberg (non-negative)`） | P5 |
| `pandas.read_csv(filepath, sep=..., index_col=...)` | 读峰表/元数据表的官方入口 | P1 |

## H. 上游软件（仅输入格式来源）

| 软件 / 参数 | 官方说明 | 来源 |
| --- | --- | --- |
| MS-DIAL `Noise level` 相关默认值 | **官方文档未提供可逐字引用的网页**（教程站正文 JS 渲染、RIKEN 手册页不可达） | U1 / U3 |
| MS-DIAL 定位 | `MS-DIAL - software for untargeted metabolomics and lipidomics` | U2 |
| mzmine `Noise level`（质谱检测） | `Absolute intensity threshold. Data points below this value are not considered. The effective detection threshold is max(noiseLevel, 2 × lowestNonZeroIntensity)` | U5 |
| mzmine 定位 | `mzmine is an open-source and platform-independent software for mass spectrometry (MS) data processing and visualization.` | U4 |

## I. 非官方部分：本技能给出的判据（明确标注，不是官方参数）

| 场景 | 判据 | 说明 |
| --- | --- | --- |
| QC 样本数量 | 每批 ≥3 个 pooled QC | 官方文档未给数量；Dunn 2011 只给"长周期多批次研究必须带 QC"的流程 |
| QC 样本 RSD/CV 阈值 | ≤30%（严格 20%） | 官方文档未给统一数值；属领域惯例 |
| 特征缺失率阈值 | ≤20%（探索性 ≤50%） | 官方文档未给统一数值 |
| 置换检验次数 | ≥200 | ropls 官方默认 20，且明说 20 是折中；≥200 是本技能更严判据 |
| Q² < 0.5 不声称分离 | 本技能判据 | ropls 只提供 Q2Y 数值，不给"多少算能用"的阈值 |
| VIP > 1 只是候选 | 本技能判据 | ropls 只定义 VIP，不给筛选阈值 |
| Hotelling T² / SPE 判离群 | 本技能判据 | ropls/XCMS 官方均未提供离群判定的统一实现 |
| 一级 MS 匹配 5–10 ppm | 本技能判据 | MSI 原文只要求"两种正交数据"，不给 ppm 数字 |
| 二级谱相似度阈值 | 本技能判据 | MSI 原文不给阈值；mzmine 另设余弦分数页，未逐字引用 |

## 来源索引

- C1 https://bioconductor.org/packages/release/bioc/vignettes/xcms/inst/doc/xcms-lcms-ms.html
- C2 https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz
- C3 https://bioconductor.org/packages/release/bioc/html/xcms.html
- R1 https://pubmed.ncbi.nlm.nih.gov/16808434/
- R2 https://pubmed.ncbi.nlm.nih.gov/21720319/
- R3 https://pubmed.ncbi.nlm.nih.gov/16762068/
- O1 https://bioconductor.org/packages/release/bioc/vignettes/ropls/inst/doc/ropls-vignette.html
- O2 https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz
- O3 https://bioconductor.org/packages/release/bioc/html/ropls.html
- G1 https://raw.githubusercontent.com/metabolomics-cloud/mummichog/master/README.md
- G2 https://github.com/metabolomics-cloud/mummichog
- G3 https://www.metaboanalyst.ca/resources/vignettes/Functional_Analysis_global_metabolomics.html
- M1 https://pubmed.ncbi.nlm.nih.gov/24039616/
- M2 https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/
- B1 https://hmdb.ca/
- B3 https://www.genome.jp/kegg/kegg2.html
- B4 https://www.genome.jp/kegg/rest/keggapi.html
- B5 https://lipidmaps.org/databases/lmsd
- P1 https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
- P2 https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html
- P3 https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html
- P4 https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html
- P5 https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
- P6 https://pyopenms.readthedocs.io/en/latest/
- U1 https://systemsomicslab.github.io/mtbinfo.github.io/
- U2 https://raw.githubusercontent.com/systemsomicslab/MsdialWorkbench/master/README.md
- U4 https://mzmine.github.io/mzmine_documentation/latest/
- U5 https://mzmine.github.io/mzmine_documentation/latest/module_docs/featdet_mass_detection/mass-detection-algorithms.html
