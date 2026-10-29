# 故障与判据（全部来自官方文档原文）

每条给出：现象 → 官方给的处置 → 来源。官方文档未覆盖的问题，标注「官方文档未提供」并只给排查方向。

## 1. 体检阶段

### 1.1 不知道 QC 样本该按什么分组

- XCMS `PeakDensityParam` 的 `sampleGroups` 默认是 `numeric()`（空），`minFraction` 的官方定义是
  `minimum fraction of samples in at least one sample group in which the peaks have to be present` ——
  不把 QC 单独成组，QC 就只是"又一批样本"，缺失/漂移信息被稀释。
- 正确做法：`sampleGroups` 显式给 QC 与各生物学组，`minFraction` 才会按"组内比例"判定。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz（`man/groupChromPeaks.Rd`）

### 1.2 QC 样本没有进 metadata

- 官方文档未规定 metadata 字段名。本技能要求 `group` / `batch` / `injection_order` 三列必须存在，
  因为 QC-RLSC 的自变量就是进样顺序（R2 的流程前提），缺了就无法做漂移校正。
  > 来源：https://pubmed.ncbi.nlm.nih.gov/21720319/

### 1.3 峰表里 m/z 与 RT 是两列，mummichog 读不进去

- MetaboAnalyst 官方规则：`Feature information must contains both m/z and retention time (RT). They should be pasted a one string with double underscore (__). e.g. m/z 157.0241 and RT 28.64 sec should be formatted as "157.0241__28.64"`。
  > 来源：https://www.metaboanalyst.ca/resources/vignettes/Functional_Analysis_global_metabolomics.html

## 2. 峰检测与对齐

### 2.1 峰太少 / 峰太多，不知道动哪个参数

- `ppm`：只影响 ROI 的 m/z 容差（`maximal tolerated m/z deviation in consecutive scans`）。
- `peakwidth`：`expected approximate peak width ... (min, max) in seconds` —— **单位是秒**，填分钟会全崩。
- `snthresh`：信噪比门槛。官方 vignette 的示例把 `snthresh` 从默认 10 降到 5，同时把 `noise` 提到 100、
  `ppm` 降到 10、`peakwidth` 改成 `c(3, 30)` —— 是**成套改**的，单独调一个常常越调越糟。
- `prefilter = c(k, I)`：`Mass traces are only retained if they contain at least k peaks with intensity >= I`；
  低丰度特征被整条丢掉，多半是这里卡住。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz

### 2.2 组内缺失一堆，特征数掉得厉害

- `minFraction`（默认 0.5）、`minSamples`（默认 1）直接决定"多少个样本里出现才算 feature"。
  `minFraction` 的官方定义是"至少一个样本组内的比例"，所以**QC 组会不会把阈值带偏**取决于 `sampleGroups`。
  > 来源：同上

### 2.3 保留时间漂移校正后峰反而对不上

- `PeakGroupsParam` 用于 RT 校正，`minFraction` 默认 0.9（锚点要在 90% 样本里出现）、`span` 默认 0.2。
  锚点太少就过拟合：把 `minFraction` 调低会引入错误锚点。
- **不要**指望它校正强度漂移：XCMS 官方文档里 `adjustRtime` 只有 RT 维度。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/xcms_4.10.1.tar.gz（`man/adjustRtime.Rd`）

## 3. 归一化与缩放

### 3.1 用了 ropls，结果跟"Dunn 流程"对不上

- ropls `opls()` 的 `scaleC` **默认是 `"standard"`**（mean-centering + unit variance），
  不是代谢组惯例的 Pareto。原文：`... or mean-centering and unit variance scaling ('standard') [default]`。
  要做 Pareto 必须显式 `scaleC = "pareto"`。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz（`man/opls.Rd`）

### 3.2 稀释效应没消掉

- 积分归一化（TIC）在强代谢变化样本上会失真。PQN 原文明确：`it is shown that integral normalization is a
  suboptimal method for normalizing spectra from metabonomic studies`，并给出替代：
  以 `the distribution of the quotients of the amplitudes` 的最可能稀释因子缩放。
  > 来源：https://pubmed.ncbi.nlm.nih.gov/16808434/

### 3.3 信号随进样顺序单向漂移

- 用 pooled QC 在进样顺序上拟合 LOESS，再把漂移曲线回代到所有样本（QC-RLSC）。适用场景见 R2：
  `thousands of human samples with data acquired for multiple analytical batches over many months and years`。
  只用生物学样本拟合会把真实组间差异当漂移减掉。
  > 来源：https://pubmed.ncbi.nlm.nih.gov/21720319/

### 3.4 Pareto 与 autoscaling 混着用

- 两者不是同一件事：autoscaling 除以 sd，Pareto 除以 sqrt(sd)。原文把
  `centering, autoscaling, pareto scaling, range scaling, vast scaling, log transformation, and power transformation`
  并列，并指出 `They were found to greatly affect the outcome` —— 换缩放方式等于换结论，必须写进 provenance。
  > 来源：https://pubmed.ncbi.nlm.nih.gov/16762068/

## 4. 多变量分析

### 4.1 置换检验跑不起来 / 结果里没有 p 值

- ropls `permI` 的官方默认：`[default is 20 for single response models (without train/test partition), and 0 otherwise]`
  —— **给了 `subset`（训练/测试划分）时默认不做置换**，所以要显式写 `permI = 200`。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz（`man/opls.Rd`）

### 4.2 置换 20 次就下结论

- 官方对默认值的定位：`The number of permutations is 20 as a compromise between quality control and computation speed;
  it can be increased with the permI parameter`。20 次是"够用即可"，不是"够发表"。
  > 来源：https://bioconductor.org/packages/release/bioc/vignettes/ropls/inst/doc/ropls-vignette.html

### 4.3 OPLS-DA 一定要几个正交成分？

- `orthoI` 默认 `0`（等于 PLS，没有正交成分）；`predI` 对 OPLS 会被自动设为 1。
  官方 OPLS-DA 示例用 `orthoI = NA`（自动选正交成分数）。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/ropls_1.44.0.tar.gz

### 4.4 PCA 出来的图跟别人不一样

- `PCA(n_components=None)` 时官方行为是"保留全部成分"：`if n_components is not set all components are kept:
  n_components == min(n_samples, n_features)`。正文写 `n_components=5` 是显式截断，
  计算分数时用的是 5 个成分，与"默认全保留"的图不可直接比较。
  > 来源：https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html

## 5. 单变量差异

### 5.1 多重检验校正"默认就是 BH"？

- statsmodels `multipletests` 的 `method` **默认是 `'hs'`（Holm-Sidak）**，不是 BH。
  要 BH 必须显式 `method='fdr_bh'`（官方取值表：`fdr_bh : Benjamini/Hochberg (non-negative)`）。
  > 来源：https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html

### 5.2 两组比较到底用 t 还是 Welch

- `scipy.stats.ttest_ind(..., equal_var=False)` 即 Welch t（不假设等方差）；
  方差不齐或样本量不等时必须用它，而不是默认的等方差 t。
  > 来源：https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html

## 6. 注释与置信级

### 6.1 想写"Level 1"，但只有谱库匹配

- MSI 原文的四类是：`Identified compounds`、`Putatively annotated compounds (e.g. without chemical reference
  standards, based upon physicochemical properties and/or spectral similarity with public/commercial spectral libraries)`、
  `Putatively characterized compound classes`、`Unknown compounds`。
  只有谱库匹配、没有标准品 → 属于第二类（putatively annotated），不是 "Identified compounds"。
- Level 1 的官方最低门槛：`A minimum of two independent and orthogonal data relative to an authentic compound
  analyzed under identical experimental conditions ... (e.g. retention time/index and mass spectrum, retention time
  and NMR spectrum, accurate mass and tandem MS)`。
  > 来源：https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/

### 6.2 原文里根本没有 "Level 1/2/3/4" 这个编号

- MSI 原文只写 `four levels of metabolite identifications`，随后按顺序给出四类名称，**没有给数字编号**。
  正文用 "Level N" 时必须说明"按 MSI 四类顺序编号"，不能声称原文用了数字。
  > 来源：同上

### 6.3 MS-DIAL 的注释码对不上

- **官方文档未提供**可逐字引用的 MS-DIAL 注释码表：官方教程站正文由 JS 渲染（取到 4 KB 壳页），
  RIKEN 传统手册页 `prime.psc.riken.jp` 在本环境 308 跳转后连接被关闭。
  本技能因此不解释任何 MS-DIAL 注释码，只按 MSI 四类标注。
  > 来源：https://systemsomicslab.github.io/mtbinfo.github.io/ 、https://raw.githubusercontent.com/systemsomicslab/MsdialWorkbench/master/README.md

## 7. 通路富集

### 7.1 未注释特征要不要丢

- 不要丢。mummichog 的定位就是绕开注释：`It leverages the organization of metabolic networks to predict
  functional activity directly from feature tables, bypassing metabolite identification.`
  > 来源：https://raw.githubusercontent.com/metabolomics-cloud/mummichog/master/README.md

### 7.2 mummichog 报错 / 结果为空

- 输入必须是高分辨质谱：`only supports the handling of peaks obtained from high-resolution MS instruments such as
  Orbitrap, or Fourier Transform (FT)-MS instruments`。
- 峰表两列（m/z、p 值）就够；三列加上 t 值或 fold change；要带 RT 必须走 v2
  （`SetPeakEnrichMethod(mSet, "mum", "v2")`），v1 只用 m/z。
- 输出看两个文件：`mummichog_pathway_enrichment_mummichog.csv`（hits、raw p、EASE score、置换校正 p）与
  `mummichog_matched_compound_all.csv`。
  > 来源：https://www.metaboanalyst.ca/resources/vignettes/Functional_Analysis_global_metabolomics.html

### 7.3 Python 包版本踩到开发版

- 官方 README 自己写明：`The last of version 2 is under branch mummichog-2.7. This is version 3 under development.`
  → 复现结论必须固定分支/commit，并在 provenance 里写明用的是 v2.7 还是 v3。
  > 来源：https://raw.githubusercontent.com/metabolomics-cloud/mummichog/master/README.md

### 7.4 背景集用"全数据库"

- 已注释代谢物走 ORA 时，`universe` 留空的后果在 clusterProfiler 官方文档里写得很清楚：
  `If missing, the all genes listed in the database (eg TERM2GENE table) will be used as background.`
  → 背景必须 = 本次检出集。
  > 来源：https://bioconductor.org/packages/3.23/bioc/src/contrib/clusterProfiler_4.20.3.tar.gz（`man/enricher.Rd`）

## 8. 数据库检索

### 8.1 HMDB 打不开

- 本环境 `https://hmdb.ca/`、`/downloads`、`/about`、`/faq` 一律 **HTTP 403**（风控）。
  官方文档未提供镜像入口；本技能只保留官方 URL，不引用其字段或下载文件名。
  > 来源：https://hmdb.ca/（403，抓取失败）

### 8.2 要可编程取 KEGG / 脂质

- KEGG 有官方 REST API：`https://www.genome.jp/kegg/rest/keggapi.html`（compound / pathway / brite 均可查）。
- LIPID MAPS 结构库入口：`https://lipidmaps.org/databases/lmsd`。
  > 来源：https://www.genome.jp/kegg/rest/keggapi.html 、https://lipidmaps.org/databases/lmsd

## 9. 口径交叉检查（提交前自查）

- [ ] QC 样本在 `sampleGroups` 里单独成组，且在 PCA 里成簇。
- [ ] `peakwidth` 的单位是秒；`prefilter` 的 k/I 与 `snthresh` 是一成套改的。
- [ ] 缩放方式写明是 Pareto 还是 standard（ropls 默认 standard）。
- [ ] 漂移校正写明"用 QC 拟合的 LOESS / QC-RLSC"，且说明它校正的是**强度**、不是 RT。
- [ ] 置换检验写明次数；若 >20，注明"高于 ropls 默认 20"。
- [ ] 多变量分析的 `subset` 与 `permI` 关系写清（有 subset 时默认 permI=0）。
- [ ] FDR 写明是 `method='fdr_bh'`（statsmodels 默认是 `'hs'`）。
- [ ] 注释级别按 MSI 四类原名标注，并说明"Level N"是顺序编号而非原文编号。
- [ ] 富集背景集 = 本次检出集；mummichog 版本（v2.7 / v3）写进 provenance。
