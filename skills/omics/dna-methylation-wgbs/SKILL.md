---
name: dna-methylation-wgbs
description: |
  DNA methylation analysis skill covering two data tracks: bisulfite sequencing (WGBS / RRBS,
  single-base resolution; upstream Bismark or bwa-meth, downstream methylKit / DSS / bsseq) and
  enrichment-based MeDIP-seq (region-level, no absolute methylation rate). Includes genome
  preparation, alignment, methylation extraction, conversion-efficiency and coverage QC,
  DML/DMR calling, DMR annotation, and DMR-to-RNA-seq association. 中文触发词：WGBS、RRBS、
  DNA 甲基化、亚硫酸氢盐、MeDIP、差异甲基化、DMR、bismark、methylKit
category: omics
tags: dna-methylation, wgbs, rrbs, medip, bismark, methylkit
---

# DNA 甲基化分析（WGBS / RRBS / MeDIP-seq）

本技能只写**官方文档中逐字存在**的命令与参数；每条命令后附来源 URL。凡官方文档未提供可直接
执行命令的环节，明确标注「官方文档未提供可直接执行的命令」，只给流程与判据，不自造代码。

## 0. 先分流：三类数据，三套口径

| 数据类型 | 分辨率 | 上游 | 下游统计 | 能否给绝对甲基化率 |
| --- | --- | --- | --- | --- |
| WGBS（全基因组亚硫酸氢盐） | 单碱基 / 单 CpG | Bismark 或 bwa-meth | methylKit / DSS / bsseq | 能（M/(M+U) per cytosine） |
| RRBS（简化代表性） | 单碱基，但仅 CpG 富集区 | 同上（去重步骤需跳过） | methylKit（官方 vignette 主用途）/ DSS | 能，但仅覆盖区域内 |
| MeDIP-seq（甲基化 DNA 免疫沉淀） | 区域级（enrichment） | 普通 DNA aligner | MEDIPS（官方指定）/ 差异 coverage | 不能，只能得相对富集 |

判据（来自官方文本）：

- methylKit vignette 明确：该包设计用于 bisulfite sequencing（WGBS/RRBS），**不适用于
  affinity-based 方法（如 MIRA-Seq、MeDIP）**，并指引此类数据使用 MEDIPS。
  > 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html
- MEDIPS 官方包说明：`MEDIPS was developed for analyzing data derived from methylated DNA
  immunoprecipitation (MeDIP) experiments followed by sequencing (MeDIP-seq). However, MEDIPS
  provides functionalities for the analysis of any kind of quantitative sequencing data ... including
  calculation of differential coverage between groups of samples and saturation and correlation analysis.`
  > 来源：https://bioconductor.org/packages/release/bioc/html/MEDIPS.html

因此：**MeDIP-seq 不得套用 Bismark 甲基化提取器与单碱基 DML 模型**，见第 5 节。

## 1. 安装（官方命令）

```bash
# Bismark（Rust v3 套件，同时装 aligner）
mamba install -c bioconda -c conda-forge bismark
```
> 来源：https://github.com/FelixKrueger/Bismark （README，Installation）

```r
# R 侧差异甲基化与注释
BiocManager::install(c("methylKit", "DSS", "bsseq", "genomation"))
```
> 来源：https://bioconductor.org/packages/release/bioc/html/MEDIPS.html （BiocManager 安装范式）；
> 各包官方页 https://bioconductor.org/packages/release/bioc/html/methylKit.html 、
> .../DSS.html 、.../bsseq.html 、.../genomation.html

bwa-meth 安装（官方 README 片段）：
```bash
wget https://github.com/brentp/bwa-meth/archive/master.zip
unzip master.zip
cd bwa-meth-master/
sudo python setup.py install
```
> 来源：https://github.com/brentp/bwa-meth （Installation）

## 2. 上游 A：Bismark 官方三步（WGBS / RRBS）

> 命令名对照（官方表格）：`bismark prepare` = 旧 `bismark_genome_preparation`；
> `bismark` / `bismark align` = 旧 `bismark`；`bismark extract` = 旧 `bismark_methylation_extractor`；
> `bismark dedup` = 旧 `deduplicate_bismark`。
> 来源：https://felixkrueger.github.io/Bismark/quick-reference/ （Command reference）

### 2.1 建索引（每个参考基因组只做一次）

```bash
bismark prepare --path_to_aligner /usr/bin/bowtie2/ --verbose /data/genomes/homo_sapiens/GRCh37/
```
> 来源：https://felixkrueger.github.io/Bismark/quick-reference/ （Genome preparation）

产物结构（官方给出的目录树）：`Bisulfite_Genome/CT_conversion/`、`Bisulfite_Genome/GA_conversion/`
> 来源：https://felixkrueger.github.io/Bismark/options/genome-preparation/

### 2.2 比对 + 甲基化 call

单端：
```bash
bismark --genome /data/genomes/homo_sapiens/GRCh37/ test_dataset.fastq
```
> 来源：https://felixkrueger.github.io/Bismark/quick-reference/

双端（配对由 `-1` / `-2` 指定）：
```bash
bismark --genome /ref/GRCh38/ -1 R1.fq.gz -2 R2.fq.gz
```
> 来源：https://felixkrueger.github.io/Bismark/ （首页 From genome to methylation calls）

关键官方说明：

- `--genome_folder` 是 `--genome` 的等价写法：`The path to the genome folder can be relative or
  absolute. The path may also be set as --genome_folder /path/to/genome/folder/.`
  > 来源：https://felixkrueger.github.io/Bismark/options/alignment/
- USAGE 原文：`bismark [options] --genome <genome_folder> {-1 <mates1> -2 <mates2> | <singles>}`
  > 来源：https://felixkrueger.github.io/Bismark/options/alignment/
- 关于 `--paired-end`：**当前官方文档（Bismark v3 站点与 v0.25.1 docs 目录）的 aligner 选项表中
  没有 `--paired-end`**；配对关系由 `-1/-2` 决定。`-p/--paired-end` 只出现在**提取器**选项中
  （见 2.4）。官方文档未提供 aligner 侧 `--paired-end` 的可执行定义，故此处不写该参数。

### 2.3 去重（WGBS 推荐，RRBS 禁用）

```bash
bismark dedup --bam R1_bismark_bt2_pe.bam
```
> 来源：https://felixkrueger.github.io/Bismark/ （首页 Step 4 Deduplicate）

官方限制原文：`This step is recommended for whole-genome bisulfite samples, but should not be used
for reduced representation libraries such as RRBS, amplicon or target enrichment libraries.`
> 来源：https://felixkrueger.github.io/Bismark/quick-reference/ （Deduplication）

### 2.4 甲基化提取（含 `--comprehensive` / `--cytosine_report`）

官方典型命令（单端 / 双端）：
```bash
bismark extract --gzip sample_bismark_bt2.bam
bismark extract --gzip sample_bismark_bt2_pe.bam
```
> 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ （III）

官方典型命令（带 bedGraph）：
```bash
bismark extract --gzip --bedGraph --buffer_size 10G sample_bismark_bt2.bam
```
> 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ （III）

官方典型命令（带全基因组胞嘧啶报告，必须给 `--genome_folder`）：
```bash
bismark extract --gzip --bedGraph --buffer_size 10G --cytosine_report --genome_folder /path_to_genome_folder/ sample_bismark_bt2.bam
```
> 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ （III）

`--comprehensive`（在上述任一命令后追加即可，官方说明逐字）：
`Specifying this option will merge all four possible strand-specific methylation info into
context-dependent output files.` 默认输出 12 个链特异文件；加该选项后为 3 个（CpG/CHG/CHH）。
> 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/ 、
> https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ （Context-dependent output files）

输出格式（官方逐字，1-based）：
- 提取器：`<seq-ID> <methylation state*> <chromosome> <start position (= end position)> <methylation call>`
- coverage：`<chromosome> <start position> <end position> <methylation percentage> <count methylated> <count unmethylated>`
- cytosine report：`<chromosome> <position> <strand> <count methylated> <count unmethylated> <C-context> <trinucleotide context>`
> 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/ （OUTPUT）

RRBS 专用官方参数：`--ignore <int>`（去掉 read 5' 端若干 bp，例如 MspI 位点）、`--ignore_r2 <int>`、
`--ignore_3prime <int>`、`--ignore_3prime_r2 <int>`。
> 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/

### 2.5 旧版 Perl 命令名（v0.25.1，等价别名）

```bash
bismark_genome_preparation --path_to_bowtie /usr/local/bowtie/ --verbose /path/to/refgenomes/
bismark_methylation_extractor -s --bedGraph reads.fastq_bismark.sam
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html （Input data
> preparation，DSS vignette 给出的官方示例）。注意该示例面向旧版 Bismark（vignette 注明
> `version 0.10.0, commands for newer versions could be different`）。

## 3. 上游 B：bwa-meth 官方用法

```bash
bwameth.py index $REF          # Indexes with BWA-MEM (default)
bwameth.py index-mem2 $REF     # Indexes with BWA-MEM2
```
> 来源：https://github.com/brentp/bwa-meth （usage / Index）
> 官方说明：`If your reference is some.fasta, this will create some.c2t.fasta and all of the bwa
> indexes associated with it.`

```bash
bwameth.py --threads 16 \
     --reference $REFERENCE \
     $FQ1 $FQ2 > some.sam
```
> 来源：https://github.com/brentp/bwa-meth （usage / Align）

口径提醒（官方逐字）：
- `As of 2016-08-18, bwa-meth now outputs sam to stdout. It is up to the user to convert to bam.
  This means that the --prefix and --calmd flags are gone.`
- 计数/甲基化表建议改用其它工具：`For tabulation, bias, and plotting, use MethylDackel`；
  SNP calling 用 `biscuit`。
- 仅支持单端与**定向建库**双端：`This works for single-end reads and for paired-end reads from the
  directional protocol (most common).`
> 来源：https://github.com/brentp/bwa-meth （NOTE / Update 2016 / Intro）

## 4. 甲基化提取后的 QC（转换效率 / 覆盖度 / 非转换率）

### 4.1 转换效率（官方三条路径）

官方原文给的判据：
1. `If you don't have any spike-in controls ... look at the lowest methylation levels you see anywhere
   in your experiment.` 例：`if you see a general methylation of 0.3% in non-CG context over many
   millions of methylation calls, then the bisulfite conversion must have been at least 99.7% efficient.`
2. 特定区域取最低值：`CpG islands ... the mitochondria (chrMT/chrM), or in plants reads aligned to
   the chloroplast sequence`。
3. Spike-in：`unmethylated (e.g. Lambda, phiX, M13) or methylated controls (e.g. in-vitro methylated
   pUC19)`；两种做法官方都认可——`index a spike-in genome and run a separate alignment` 或
   `include the spike-in sequence as an additional 'chromosome' to the genome of interest`。
> 来源：https://felixkrueger.github.io/Bismark/faq/conversion-efficiency/

**官方文档未提供可直接执行的命令**来计算上述 λ/phiX 非转换率（官方只给出上述判据与思路）；
该步骤请按第 2 节命令另行建索引/比对后自行统计，不要引入本技能未声明的脚本。

### 4.2 非转换 read 过滤（有官方命令）

```bash
bismark filter [options] [Bismark BAM files]
```
官方参数：`--threshold [int]`（默认 3）、`--percentage_cutoff [int]`、`--minimum_count [int]`（默认 5）、
`--consecutive`、`-p/--paired`、`-s/--single`。产物：`nonCG_filtered.bam`、`nonCG_removed_seqs.bam`。
官方警告：`this kind of filtering is not advisable - and will introduce biases - if you work with
organisms which exhibit any appreciable levels of non-CG methylation (e.g. most plants).`
> 来源：https://felixkrueger.github.io/Bismark/usage/filtering-non-conversion/

### 4.3 覆盖度 / M-bias（官方产物，无额外命令）

- M-bias 表与图由提取器自动产生：`.M-bias.txt`，列格式
  `<read position> <count methylated> <count unmethylated> <% methylation> <total coverage>`；
  `--ignore` 用于按 M-bias 结论裁掉偏倚区段。
  > 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ （M-bias plot）
- 覆盖度阈值本身官方未给统一数值；methylKit 官方默认 `mincov = 10`
  （`By default methRead requires a minimum coverage of 10 reads per base`），
  `filterByCoverage` 用 `hi.perc=99.9` 去掉 PCR 偏倚高覆盖位点。
  > 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html

## 5. 差异甲基化

### 5.1 methylKit 官方流程（RRBS 主用，WGBS 可用）

```r
library(methylKit)
myobj=methRead(file.list,
           sample.id=list("test1","test2","ctrl1","ctrl2"),
           assembly="hg18",
           treatment=c(1,1,0,0),
           context="CpG",
           mincov = 10
           )

filtered.myobj=filterByCoverage(myobj,lo.count=10,lo.perc=NULL,
                                      hi.count=NULL,hi.perc=99.9)

meth=unite(myobj, destrand=FALSE)

myDiff=calculateDiffMeth(meth)

myDiff25p.hyper=getMethylDiff(myDiff,difference=25,qvalue=0.01,type="hyper")
myDiff25p.hypo=getMethylDiff(myDiff,difference=25,qvalue=0.01,type="hypo")
myDiff25p=getMethylDiff(myDiff,difference=25,qvalue=0.01)

diffMethPerChr(myDiff,plot=FALSE,qvalue.cutoff=0.01, meth.cutoff=25)
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html

过离散与检验选择（官方逐字）：
`By default, this overdispersion correction is not applied. This can be achieved by setting
overdispersion="MN". The Chisq-test is used by default only when no overdispersion correction is
applied. If overdispersion correction is applied, the function automatically switches to the F-test.
The Chisq-test can be manually chosen in this case as well, but the F-test only works with
overdispersion correction switched on.`
官方示例（含 covariates）：
```r
my.diffMeth3<-calculateDiffMeth(sim.methylBase,
                                covariates=covariates,
                                overdispersion="MN",test="Chisq",mc.cores=1)
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html
> （Correcting for overdispersion / Accounting for covariates）

覆盖度归一化（官方 FAQ）：`Ideally, you should first filter bases with extreme coverage to account
for PCR bias using filterByCoverage() function, then run normalizeCoverage() function to normalize
coverage between samples.`
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html （FAQ）

区域级（tiling）替代路径：
```r
tiles = tileMethylCounts(myobj_lowCov,win.size=1000,step.size=1000,cov.bases = 10)
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html

### 5.2 DSS 官方流程（`DMLtest` → `callDML` / `callDMR`）

输入格式（官方逐字）：每样本一个文本文件，行= CpG 位点，列为 `chr pos N X`。
```r
library(DSS)
require(bsseq)
BSobj = makeBSseqData( list(dat1.1, dat1.2, dat2.1, dat2.2),
     c("C1","C2", "N1", "N2") )

dmlTest = DMLtest(BSobj, group1=c("C1", "C2"), group2=c("N1", "N2"))
dmlTest.sm = DMLtest(BSobj, group1=c("C1", "C2"), group2=c("N1", "N2"),
                     smoothing=TRUE)

dmls = callDML(dmlTest, p.threshold=0.001)
dmls2 = callDML(dmlTest, delta=0.1, p.threshold=0.001)

dmrs = callDMR(dmlTest, p.threshold=0.01)
dmrs2 = callDMR(dmlTest, delta=0.1, p.threshold=0.05)
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html

官方要点：
- 平滑窗宽默认 500 bp：`We use 500 bp as default`；WGBS 建议平滑：
  `For WGBS data, smoothing is always recommended`；RRBS 仍推荐平滑（FAQ：`Smoothing is always
  recommended, even for RRBS.`）。
- `delta` 语义：`the function will compute the posterior probability that the difference of the
  means is greater than delta`，此时 p 阈值实为 local FDR。
- `callDMR` 结果按 `areaStat` 排序，`areaStat` 无直接生物学含义。
- 无生物学重复时靠平滑充当伪重复；`DSS only takes count data`（不能喂 beta 值）。
- Windows 上 `ncores=1`（FAQ/并行小节）。
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html

### 5.3 bsseq（BSmooth 平滑 + t 统计 + DMR）

官方给出的分析三步（逐字）：`1. Smoothing, using the function BSmooth(). 2. Compute t-statistics,
using the function BSmooth.tstat(). ... 3. Threshold these t-statistics to identify DMRs, using the
function dmrFinder()`。
```r
BS.chr22.1 <- BSmooth(BS.chr22[,"r1"], verbose = TRUE)

BSseq <- read.bismark(bismarkfiles, BACKEND = "HDF5Array", BPPARAM = MulticoreParam(workers = 10))

saveHDF5SummarizedExperiment(BSseq, dir = "./BSseqName.h5")
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/bsseq/inst/doc/bsseq.html

官方要点：`read.bismark(..., BACKEND = "HDF5Array")` 用于大样本/边界内存；`fisherTests()` 可得
逐位点 Fisher 检验；`The smoothing functions assumes that the underlying BSseq has been ordered`
（先 `orderBSseq()`）；`mc.cores` > 1 在 Windows 不可用。
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/bsseq/inst/doc/bsseq.html

**三套下游的选用判据**（非官方命令，方法学判据）：
- 位点级、样本少、要 Fisher/逻辑回归：methylKit。
- 位点级 + 区域级都要、可容忍无重复：DSS（beta-binomial + 收缩 + Wald）。
- 低覆盖 WGBS、需平滑与 HDF5 扩展：bsseq（BSmooth）。

## 6. 区域与注释

### 6.1 DMR 注释（genomation，methylKit 官方 vignette 给出）

```r
library(genomation)
gene.obj=readTranscriptFeatures(system.file("extdata", "refseq.hg18.bed.txt", 
                                           package = "methylKit"))

annotateWithGeneParts(as(myDiff25p,"GRanges"),gene.obj)

cpg.obj=readFeatureFlank(system.file("extdata", "cpgi.hg18.bed.txt", 
                                        package = "methylKit"),
                           feature.flank.name=c("CpGi","shores"))

diffCpGann=annotateWithFeatureFlank(as(myDiff25p,"GRanges"),
                                    cpg.obj$CpGi,cpg.obj$shores,
                         feature.name="CpGi",flank.name="shores")

promoters=regionCounts(myobj,gene.obj$promoters)

diffAnn=annotateWithGeneParts(as(myDiff25p,"GRanges"),gene.obj)
head(getAssociationWithTSS(diffAnn))
getTargetAnnotationStats(diffAnn,percentage=TRUE,precedence=TRUE)
plotTargetAnnotation(diffAnn,precedence=TRUE,
    main="differential methylation annotation")
getFeatsWithTargetsStats(diffAnn,percentage=TRUE)
```
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html
> （Annotating differentially methylated bases or regions / Regional analysis）

官方默认窗口：promoter = TSS ±1000 bp；CpG island shore = 岛两侧各 2000 bp。
> 来源：同上（FAQ "How do you define promoters and CpG island shores?"）

### 6.2 DSS 结果的注释

官方 FAQ：`DSS doesn't provide this functionality. There are many other tools can do this, for
example, HOMER.` → 即 **官方文档未提供 DSS 侧的注释命令**，需转 6.1 的 genomation 路线。
> 来源：https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html （FAQ）

### 6.3 与 RNA-seq 表达关联

**官方文档未提供可直接执行的命令**（甲基化包与表达分析包之间没有官方桥接函数）。只给流程与判据：

1. 用 5.x 得到 DMR/DML 的 GRanges，并标注基因（6.1）。
2. 判据：只看 promoter（TSS ±1000 bp，官方默认）与 gene body 两类区域，分别统计
   hyper/hypo 与表达上调/下调的列联表；CpG island / shore / shelf 分层汇报。
3. 判据：同一基因的甲基化差值与表达 log2FC 的符号一致性（负相关预期），按 DMR 覆盖的 CpG 数
   加权；无覆盖的基因不得计入。
4. 判据：样本级配对（同一批样本同时有甲基化与表达）才做相关；跨队列只做方向一致性。

## 7. MeDIP-seq（区域级，不同口径）

### 7.1 口径差异（判据）

- MeDIP 是**富集**读数：信号 = 抗体富集强度 × CpG 密度 × 拷贝数，值域为 coverage/peak，
  **不能换算成 0–100% 的绝对甲基化率**，也不能做单碱基 DML。
- 必须做输入对照（input/IgG）归一化与 CpG 密度校正，否则高 CpG 密度区一律"看起来高甲基化"。
- 差异分析的对象是**区域/窗口的 coverage**，不是胞嘧啶计数。

### 7.2 工具：MEDIPS

`MEDIPS was developed for analyzing data derived from methylated DNA immunoprecipitation (MeDIP)
experiments followed by sequencing (MeDIP-seq). However, MEDIPS provides functionalities for the
analysis of any kind of quantitative sequencing data (e.g. ChIP-seq, MBD-seq, CMS-seq and others)
including calculation of differential coverage between groups of samples and saturation and
correlation analysis.`
> 来源：https://bioconductor.org/packages/release/bioc/html/MEDIPS.html

**官方文档未提供可直接执行的命令**：MEDIPS 的 vignette 仅以 PDF / R Script 形式发布
（`MEDIPS.pdf`、`MEDIPS.R`，见官方包页 Documentation 栏），本次抓取无法取得可解析文本，
故本技能不写 `MEDIPS.createSet` / `MEDIPS.meth` 等调用。落地方式：在 R 内执行
`browseVignettes("MEDIPS")` 取官方 vignette 后按原文执行。
> 来源：https://bioconductor.org/packages/release/bioc/html/MEDIPS.html （Documentation：
> `MEDIPS | PDF | R Script`；`browseVignettes("MEDIPS")`）

MeDIP 侧的流程与判据（无官方命令，仅流程）：
1. 比对（普通 DNA aligner，非亚硫酸氢盐模式）→ 去重 → input 对照。
2. 窗口计数（固定窗或 CpG 岛注释窗）→ CpG 密度/GC 校正 → 样本间归一化。
3. 饱和度和样本相关性检查（MEDIPS 官方描述的 `saturation and correlation analysis`）。
4. 组间差异 coverage（官方描述的 `calculation of differential coverage between groups of samples`）。
5. 区域注释同 6.1（genomation），但报告措辞须为"差异富集区"，不得写"差异甲基化率"。

## 8. 建议产出目录（本技能约定，非官方）

```
results/
├─ 01_align/            # *_bismark_bt2*.bam, *_SE_report.txt / *_PE_report.txt
├─ 02_dedup/            # WGBS: *_deduplicated.bam；RRBS 跳过
├─ 03_extract/          # CpG_context_*.txt.gz / *.bam.bedGraph.gz / *.bam.bismark.cov.gz / *.CpG_report.txt.gz
├─ 04_qc/               # *.M-bias.txt, *_splitting_report.txt, 非转换率汇总
├─ 05_dml_dmr/          # methylKit / DSS / bsseq 结果表（DML、DMR、areaStat）
├─ 06_annotation/       # promoter/exon/intron/CpGi 注释表、TSS 距离
└─ 07_medip/            # MeDIP: 窗口 coverage、差异富集区（与 05 严格分栏）
```

## 9. 验收清单

上游：
- [ ] 基因组索引存在 `Bisulfite_Genome/CT_conversion/` 与 `GA_conversion/`
- [ ] 每个样本有 `*_SE_report.txt` 或 `*_PE_report.txt`，mapping efficiency 有记录
- [ ] WGBS 做了 `bismark dedup`，RRBS 明确未做
- [ ] 提取用 `--comprehensive`（或明确声明保留 12 个链特异文件）并保留 `.M-bias.txt`
- [ ] `--cytosine_report` 一定带 `--genome_folder`，并确认坐标体系（1-based 默认）

QC：
- [ ] 转换效率有书面数值：λ/phiX 非转换率，或非 CG 最低甲基化率（官方两种判据之一）
- [ ] 每样本 CpG 覆盖度分布 + 覆盖 CpG 数（≥1×、≥5×、≥10× 三档）
- [ ] M-bias 图已查看，必要时用 `--ignore` / `--ignore_r2` 并在方法学中声明

下游：
- [ ] 覆盖度过滤参数书面化（methylKit: `lo.count`/`hi.perc`；DSS: 官方不建议滤低覆盖）
- [ ] 检验选择说明：`overdispersion="MN"` 与 `test="Chisq"\|"F"` 的组合已写明理由
- [ ] DMR 调用阈值（`difference`/`qvalue`；`p.threshold`/`delta`）写入方法学
- [ ] DMR 注释层级：promoter / exon / intron / intergenic + CpGi / shore
- [ ] MeDIP 数据未混入单碱基 DML 表；报告中措辞为"差异富集"

## 10. 参考文档

- `references/official-docs.md` — 全部官方 URL、版本、抓取状态、不可访问清单
- `references/parameters.md` — 参数逐条对照表（含默认值与出处）
- `references/troubleshooting.md` — 官方文档中已有的故障与判据

> 说明：本技能不提供 `scripts/` 目录。Bismark / bwa-meth / methylKit / DSS / bsseq / MEDIPS
> 均已自带官方 CLI 或 R 函数，官方文档未随附需要本技能转发的独立脚本。
