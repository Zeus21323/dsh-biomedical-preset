---
name: rna-modification-clip
description: |
  Peak analysis for RNA modification and RNA-protein interaction sequencing: MeRIP-seq/m6A
  (exomePeak2 peak calling and differential methylation), RIP-seq (general peak calling with
  input control) and CLIP-seq/eCLIP (CLIPper peak clusters, crosslink site and motif analysis),
  plus upstream alignment/dedup/rRNA-filtering/strandedness choices and ChIPseeker peak annotation.
  Every command, parameter and default below is quoted from vendor documentation with the source URL.
  中文触发词：MeRIP、m6A、RNA 修饰、RIP-seq、CLIP-seq、eCLIP、exomePeak2、交联位点
category: omics
tags: merip, m6a, rip-seq, clip-seq, epitranscriptomics
---

# RNA 修饰与 RNA-蛋白互作 peak 分析（MeRIP-seq / RIP-seq / CLIP-seq）

三类数据的**实验设计与分辨率不同**，peak 的定义、可用工具、统计口径都不同。第一步永远是分流，
第二步才是 peak calling。本文所有命令、参数名与默认值均逐字取自官方文档，每条命令后附来源 URL；
官方文档没有可直接执行命令的环节，明确标注「官方文档未提供可直接执行的命令」，只给流程与判据。

## 1. 三类数据分流（先判类型，再选工具）

| 数据类型 | 实验 | peak 的含义 | 分辨率 | 主用工具（官方） |
|---|---|---|---|---|
| MeRIP-seq / m6A | IP（anti-m6A 抗体）vs input | 转录本（外显子）坐标上的**修饰富集窗口** | 窗口级（默认 bin 25 bp、step 25 bp） | exomePeak2 `exomePeak2()` |
| RIP-seq | IP（RBP 抗体）vs input | RNA-蛋白互作的**结合区段** | 低（片段级，通常数百 bp） | 官方无专用 caller，用通用 peak caller（MACS3 `callpeak`） |
| CLIP-seq / eCLIP | UV 交联 + IP vs size-matched input | **交联位点**聚成的 peak cluster | 高（单核苷酸级交联位点→cluster） | CLIPper `clipper` |

判据来源：
- MeRIP-seq 由 exomePeak2 官方 vignette 定义（"peak detection and differential methylation analysis for MeRIP-Seq"）——https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd
- CLIP-seq 由 CLIPper 官方 README 定义（"A tool to detect CLIP-seq peaks"）——https://github.com/YeoLab/CLIPper
- RIP-seq 无专用官方工具：MACS 官方 README 自述为通用 peak caller（"as a general peak-caller, MACS can also be applied to any 'DNA enrichment assays'"）——https://github.com/macs3-project/MACS

## 2. 输入与前置

- MeRIP-seq：IP 与 input 的 **BAM**（exomePeak2 官方要求 "alignment results to be stored in BAM format"）+ 转录本注释（GFF/GTF 或 TxDb）+ 基因组（`genome`，用于 GC 偏倚校正）。
- RIP-seq：IP 与 input 的 BAM/BED（MACS3 `-t`/`-c`）。
- CLIP-seq：去重后的单端 BAM（CLIPper `--bam`）+ 内置物种注释（`--species`）。
- 所有 BAM 需按坐标排序并建索引（CLIPper 官方 `check_for_index` 会检查索引；RSeQC 文档要求 "BAM file must be sorted and indexed properly using SAMTools"）。

## 3. 上游：比对、去重、rRNA 去除、链特异性

### 3.1 比对：STAR（MeRIP / RIP）

建索引与比对参数取自 STAR 官方手册（`doc/STARmanual.pdf`）：

```bash
STAR --runMode genomeGenerate --runThreadN 12 \
  --genomeDir star_index \
  --genomeFastaFiles genome.fa \
  --sjdbGTFfile annotation.gtf \
  --sjdbOverhang 100
```
来源：https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf

```bash
STAR --runThreadN 12 --genomeDir star_index \
  --readFilesIn IP_R1.fq.gz IP_R2.fq.gz --readFilesCommand zcat \
  --outSAMtype BAM SortedByCoordinate \
  --outSAMattributes NH HI AS nM \
  --outFileNamePrefix IP.
```
来源：同上手册（`--outSAMtype` 默认 `SAM`，`BAM SortedByCoordinate` 输出 `Aligned.sortedByCoord.out.bam`；`--outSAMattributes` 默认 `Standard`，即 `NH HI AS nM`，手册 5.2.2 节原文 "By default, STAR outputs NH HI AS nM attributes."）。

需要基因级 counts 时加 `--quantMode GeneCounts`（手册：输出 `ReadsPerGene.out.tab`，与 htseq-count 默认口径一致）。默认值 `--quantMode` = `-`（不计数）。

关键默认值（手册）：`--outFilterMultimapNmax 10`、`--outFilterMismatchNmax 10`、`--winAnchorMultimapNmax 50`、`--alignSJoverhangMin 5`、`--alignEndsType Local`。

### 3.2 比对：bowtie2 `--local`（CLIP 短读/软剪切）

```bash
bowtie2 --local --sensitive-local -p 8 \
  -x bt2_index -U CLIP.fq.gz -S CLIP.sam
```
来源：https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml

官方手册原文：`--local` — "In this mode, Bowtie 2 does not require that the entire read align from one end to the other. Rather, some characters may be omitted ("soft clipped") from the ends in order to achieve the greatest possible alignment score."；`--end-to-end` 为默认模式；`--local` 模式下预设默认 `--sensitive-local` = `-D 15 -R 2 -N 0 -L 20 -i S,1,0.75`；`--score-min` 在 local 模式默认 `G,20,8`。

### 3.3 CLIP/eCLIP 官方的比对组合（STAR + 重复序列过滤）

YeoLab 官方 eCLIP 流程描述：先用 STAR 比对重复序列再过滤，再用 STAR 比对基因组，然后去重，最后 CLIPper 出 peak。来源：https://github.com/YeoLab/eclip

```bash
# 官方流程第 1 步：比对重复序列（repeat element STAR index）
STAR --runThreadN 12 --genomeDir repeat_star_index \
  --readFilesIn trim.fq.gz --readFilesCommand zcat \
  --outSAMtype BAM Unsorted \
  --outReadsUnmapped Fastx \
  --outFileNamePrefix rep.
```
来源：https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf（`--outReadsUnmapped` + `Fastx` 输出未比对读段，官方手册 17.x 节）；流程顺序来源：https://github.com/YeoLab/eclip

### 3.4 去重

**MeRIP-seq**：官方 exomePeak2 vignette **未包含去重步骤**，官方文档未提供可直接执行的 MeRIP 去重命令；是否需要去重按文库 UMI 有无判断（判据：无 UMI 的 MeRIP 通常按 PCR 重复比例决定，比例异常高时先查文库复杂度，官方无阈值）。

**CLIP/eCLIP**：官方 eCLIP 流程使用 umi_tools（单端）或仓库内 `barcodecollapsepe.py`（双端）去重（https://github.com/YeoLab/eclip）。umi_tools 官方用法：

```bash
umi_tools dedup --stdin=INFILE --log=LOGFILE > OUTFILE
```
来源：https://umi-tools.readthedocs.io/en/latest/reference/dedup.html

官方默认：`--method` 默认 `directional`（"Identify clusters of connected UMIs ... and umi A counts >= (2\* umi B counts) - 1"）；`--multimapping-detection-method` 支持 `NH/X0/XT`；`--paired` 输出双端；`--soft-clip-threshold` 默认 4。

### 3.5 rRNA 去除

官方无「MeRIP/CLIP 专用 rRNA 去除命令」；可用 SortMeRNA 官方用法（`--ref` 与 `--reads` 为必填项）：

```bash
sortmerna --ref rRNA_db.fasta --reads reads.fq.gz
# 多参考库 / 双端时重复该选项
sortmerna --ref REF_PATH_1 --ref REF_PATH_2 --reads READS_PATH_1 --reads READS_PATH_2
```
来源：https://github.com/sortmerna/sortmerna

替代路线：RSeQC 官方提供 `GRCh38_rRNA.bed` / `hg19_rRNA.bed` / `mm10_rRNA.bed` 等 rRNA 区间，可用于统计 rRNA 占比（https://rseqc.sourceforge.net/）；把区间与 BAM 求交的官方命令见 3.7 的 `bedtools intersect`。

### 3.6 链特异性

- exomePeak2 用参数 `strandness`（**不是** `--library-type`；exomePeak2 官方文档没有 `--library-type` 参数），取值 `c("unstrand","1st_strand","2nd_strand")`，默认 `"unstrand"`。来源：https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R
- 判定方法（官方命令）：

```bash
infer_experiment.py -r hg19.refseq.bed12 -i sample.bam
```
来源：https://rseqc.sourceforge.net/（`-s` 采样读段数默认 200000，`-q` MAPQ 默认 30）

判据（官方示例）：若 "1++,1--,2+-,2-+" 与 "1+-,1-+,2++,2--" 各约 0.49/0.49 → 非链特异；若一侧 0.94、另一侧 0.05 → 链特异。据此映射到 `strandness`：单端 `++,--` 型对应 `1st_strand`，`+-, -+` 型对应 `2nd_strand`（映射依据 exomePeak2 文档中对 `1st_strand`/`2nd_strand` 的定义）。

### 3.7 计数类操作（FRiP、区间统计）用 bedtools intersect

```bash
bedtools intersect -abam reads.bam -b peaks.bed -u -bed | wc -l
```
来源：https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html
（`-u` "Write original A entry once if any overlaps found in B"；`-bed` "Output BED format when using BAM input"；`-v` 取无重叠；`-c` 每个 A 计数；`-split` 按 CIGAR N 拆分。注意：**FRiP 这一指标本身官方未给出专用命令**，上面是官方选项的组合用法，阈值判据见第 7 节。）

## 4. MeRIP-seq / m6A（exomePeak2）

### 4.1 peak calling（官方 vignette 原样）

```r
library(exomePeak2)
set.seed(1)
GENE_ANNO_GTF = system.file("extdata", "example.gtf", package="exomePeak2")
IP_BAM    = c(IP1.bam, IP2.bam, IP3.bam, IP4.bam)          # 实际写成 system.file(...) 的向量
INPUT_BAM = c(Input1.bam, Input2.bam, Input3.bam)

exomePeak2(bam_ip = IP_BAM,
           bam_input = INPUT_BAM,
           gff = GENE_ANNO_GTF,
           genome = "hg19")
```
来源：https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd

官方说明：`genome` 缺失（`= NULL`）时 "exomPeak2 will perform peak calling without correcting the PCR amplification bias"；结果除返回 `GRangesList` 外，自动在 `exomePeak2_output` 目录导出 **BED / CSV / RDS**。

### 4.2 差异甲基化（两组比较）

```r
exomePeak2(bam_ip = IP_BAM, bam_input = INPUT_BAM,
           bam_ip_treated = TREATED_IP_BAM,
           bam_input_treated = TREATED_INPUT_BAM,
           gff = GENE_ANNO_GTF, genome = "hg19")
```
来源：同上。官方口径：先 pull 两组做 peak calling，再在显著 peak 的 counts 上用交互 Poisson GLM 检验；输出的 `diff.log2FC` 解释为 log( treated 组 IP/input FC ÷ control 组 IP/input FC )。

### 4.3 关键参数（默认值取自官方函数签名）

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `fragment_length` | 100 | 期望片段长度（bp） |
| `bin_size` / `step_size` | 25 / 25 | 滑窗宽度 / 步长 |
| `test_method` | `"Poisson"` | 可选 `"DESeq2"`；用 DESeq2 时官方建议放宽 `p_cutoff`（"e.g. 0.001"） |
| `p_cutoff` | `1e-10` | peak calling 的 p 值阈值（Wald 检验，备择假设 β>0） |
| `diff_p_cutoff` | `0.01` | 差异分析 p 值阈值 |
| `mode` | `"exon"` | 可选 `full_transcript`（含内含子）/ `whole_genome`；后两者大基因组需 >4 GB 内存 |
| `motif_based` | `FALSE` | 为 `TRUE` 时用 motif 位点替代滑窗 |
| `motif_sequence` | `"DRACH"` | `motif_based=TRUE` 时的 motif 序列 |
| `strandness` | `"unstrand"` | `1st_strand` / `2nd_strand` |
| `parallel` | 1 | 并行核数 |
| `plot_gc` | `TRUE` | 输出 GC 偏倚诊断图 |
| `save_dir` / `experiment_name` | `getwd()` / `"exomePeak2_output"` | 输出目录 / 子目录名 |

来源：https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R

### 4.4 peak 输出列（官方定义）

`chr`、`chromStart`、`chromEnd`、`name`、`strand`、`blockCount`、`blockSizes`、`blockStarts`、`geneID`、`RPM.input`、`RPM.IP`、`log2FC`、`pvalue`、`fdr`、`score`（`score` = -log10 p）。
来源：https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd

### 4.5 m6A motif 富集

两条官方路线：

1) **exomePeak2 内建位点模式**：`motif_based = TRUE` + `motif_sequence = "DRACH"`（默认），直接用 motif 位点替代滑窗做（差异）修饰检测（来源同上 R 源码）。
2) **HOMER de novo/已知 motif 富集**（官方命令格式）：

```bash
findMotifsGenome.pl m6a_peaks.bed hg38 m6a_motif_out/ -size given -rna -len 6
```
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

官方要点：`-size` 为**必填**（`-size given` 用输入区间原长，默认 200）；`-rna` 只搜正链、输出 RNA logo（U 代替 T），"automatically sets -norevopp"，但官方同时说明其 RNA motif 库"only contains miRNAs"，故 RNA 类 motif 的已知库比对价值有限；`-len` 默认 `8,10,12`；`-p` 指定 CPU 数（默认 1）；`-bg` 指定背景区间；`-find <motif file>` 只扫描指定 motif 位点（需要 HOMER 格式 motif 文件）。

**关于 RRACH**：exomePeak2 官方默认 motif 是 `"DRACH"`；HOMER 官方文档未提供「以 RRACH 这样的简并序列字符串直接做富集」的命令（`-find` 需要 motif 矩阵文件）。若必须用 RRACH，官方文档未提供可直接执行的命令，只能走 exomePeak2 的 `motif_sequence` 传参或自备 motif 矩阵文件后 `-find`。

### 4.6 与表达/翻译关联

官方文档（exomePeak2 / ChIPseeker / CLIPper）**未提供**把 m6A peak 与差异表达、翻译效率直接关联的命令。流程与判据：

1. 基因级表达：STAR `--quantMode GeneCounts` 得 `ReadsPerGene.out.tab`（STAR 官方手册），或本 preset 的 `bulk-rnaseq` 流程；差异分析用该 skill 的 PyDESeq2 路线。
2. 关联口径：把 peak 的 `geneID` 与差异基因表按基因 ID 取交集，比较「有 peak 的基因」与「无 peak 的基因」的 log2FC 分布（判据：分布是否系统性偏移；官方无阈值）。
3. 翻译效率需要 Ribo-seq，本 skill 引用的官方文档均未覆盖，此处不写命令。

## 5. RIP-seq

### 5.1 定位说明

RIP-seq **没有官方专用 peak caller**。官方可直接引用的做法是用通用 peak caller，并以 input（或 mock IP）为对照。MACS 官方 README 明确其定位："MACS can be easily used for ChIP-Seq data alone, or with a control sample with the increase of specificity. Moreover, as a general peak-caller, MACS can also be applied to any 'DNA enrichment assays'"（https://github.com/macs3-project/MACS）。

### 5.2 官方命令（MACS3 `callpeak`，按 TF ChIP-seq 口径，加对照）

```bash
macs3 callpeak -t RIP.bam -c INPUT.bam -f BAM -g hs -n rip -B -q 0.01
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html（官方 "Peak calling for regular TF ChIP-seq" 示例，把 `-t/-c` 换成 RIP/input）

官方默认与要点：
- `-q` 默认 0.05（q-value 由 BH 校正的 p 值得到）；`-p` 则改用 p 值。
- `-g hs` 对应有效基因组 2,913,022,398（GRCh38）；`mm` 2,652,783,500（GRCm38）。
- `--keep-dup` 默认 1（同坐标同链只留 1 条）；`auto` 用二项分布按 1e-5 估上限。
- 无对照或想跳过建模时用 `--nolambda`、`--nomodel` + `--extsize`。
- 输出：`NAME_peaks.xls`（1-based）、`NAME_peaks.narrowPeak`（BED6+4）、`NAME_summits.bed`、`-B` 时 `NAME_treat_pileup.bdg` / `NAME_control_lambda.bdg`。
- `--broad` + `--broad-cutoff`（默认 0.1）用于宽峰。
- `--threads N` 设定 CPU 预算（MACS3 3.1.0 起）。

### 5.3 RIP 口径注意事项（判据，非命令）

- **必须有输入对照**：MACS 官方说明 `-c` 是 "genomic input or mock IP data"，RIP 的解释完全依赖 input 归一。
- **分辨率低**：峰宽通常远大于 CLIP cluster，不要用 CLIP 的单核苷酸交联位点标准去要求 RIP；官方文档未给 RIP 专属峰宽阈值，按 `--min-length`/`--max-gap`（默认分别为预测片段大小与读长）调节。
- RIP 无交联，峰内不必然含 motif，`findMotifsGenome.pl` 的显著性判据（官方："Enrichment p-values ... should be very very significant (i.e. << 1e-50)"）是针对高质量 ChIP/CLIP 数据的，RIP 数据达不到该量级不构成流程错误。

## 6. CLIP-seq / eCLIP（CLIPper）

### 6.1 安装与最小命令（官方 README）

```bash
cd clipper
conda env create -f environment3.yml
conda activate clipper3
pip install .

clipper -h
clipper -b YOUR_BAM_FILE.bam -o YOUR_OUT_FILE.bed -s hg19
```
来源：https://github.com/YeoLab/CLIPper

注意：**CLIPper 没有 `--threads` 参数**；并行度用 `--processors`（dest `np`），官方帮助原文 "Number of processors to use. Default: All processors on machine"，默认值 `autodetect`。来源：https://github.com/YeoLab/clipper/blob/master/clipper/src/main.py

### 6.2 官方参数（逐字取自 `clipper/src/main.py`）

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `--bam`/`-b` | 必填 | "A bam file to call peaks on" |
| `--species`/`-s` | 必填 | 官方 README："either hg19 or mm9"；官方 CWL 列出：`ce10 ce11 dm3 hg19 GRCh38 mm9 mm10 GRCh38_pU6 GRCh38_v29 GRCh38_v29e hg19_VSV` |
| `--outfile`/`-o` | `fitted_clusters` | 输出 BED 文件名 |
| `--gene`/`-g` | 无 | 只跑指定基因（可重复） |
| `--minreads` | 3 | 起始拟合所需最小 reads |
| `--poisson-cutoff` | 0.05 | Poisson 检验 p 值阈值 |
| `--FDR` | 0.05 | 峰高估计的 FDR 阈值 |
| `--binomial` | 0.05 | 用二项分布定峰高阈值的显著性 |
| `--threshold` | 无 | 跳过 FDR 计算，直接给阈值 |
| `--max_gap` | 15 | 判定新 section 的最大 read 间隔 |
| `--disable_global_cutoff` | 默认开启全局 cutoff | 关闭转录组水平 cutoff |
| `--processors` | `autodetect` | 进程数（全部核） |
| `--plot`/`-p` | off | 输出拟合图（会自动 `--debug`） |
| `--save-pickle` | off | 保存分析中间对象 |
| `--timeout` | 无 | 单基因超时（秒） |
| `--datadir` | 包内数据目录 | `DATADIR/*AS.STRUCTURE.gff` 与 `DATADIR/regions/*.bed` |

内部固定（`override_options()`，官方源码）：`premRNA=True`、`method="binomial"`、`SloP=True`、`bonferroni_correct=True`、`algorithm="spline"`、`max_width=75`、`min_width=50`。
来源：https://github.com/YeoLab/clipper/blob/master/clipper/src/main.py

### 6.3 官方流程中的调用（eCLIP CWL）

- 资源：`coresMin: 8`、`ramMin: 32000`；镜像 `brianyee/clipper:5d865bb`；默认输出名为 `<bam>.peakClusters.bed`。
- 调用示例（官方 `doc` 字段原文）：`clipper --bam CLIP-seq_reads.srt.bam --species hg19 --outfile CLIP-seq_reads.srt.peaks.bed`
来源：https://github.com/YeoLab/eclip/blob/master/cwl/clipper.cwl

### 6.4 peak 输出格式

- CLIPper `-o` 输出 **BED**（官方 README 的 `-o YOUR_OUT_FILE.bed`）；eCLIP 流程命名为 `*.peakClusters.bed`，随后用 `bed_to_narrowpeak.cwl` 转 narrowPeak（来源：https://github.com/YeoLab/eclip/blob/master/cwl/ 目录下的 `bed_to_narrowpeak.cwl`；eCLIP 官方 README 输出表亦列出 `*.blacklist-removed.narrowPeak`）。
- 官方 README 未给出 `peakClusters.bed` 的列定义；仓库内提供标准输出样例 `clipper/test/data/peak_results.BED` 可用于核对列数（https://github.com/YeoLab/clipper/tree/master/clipper/test/data）。
- eCLIP 官方对 narrowPeak 第 5 列的解释："The scores in the 5th column are almost always equal to 1000 or 200 ... 200/1000 flags each peak as significant (1000) or not (200)"（https://github.com/YeoLab/eclip）。

### 6.5 交联位点定义

- CLIPper 的模型是"用拟合平滑样条定义结合 cluster"（官方 `description`："CLIP peakfinder that uses fitted smoothing splines to define clusters of binding"）。**官方文档未定义单核苷酸交联位点**（未提供 crosslink site 输出命令与位点定义）。
- eCLIP 官方流程给出的是：去重后 BAM → CLIPper peak cluster → 与 size-matched input 归一算 fold-change（官方 README 第 7 步用 `overlap_peakfi_with_bam_PE.pl` 与 `compress_l2foldenrpeakfi_for_replicate_overlapping_bedformat.pl`）。这些脚本属于该仓库，不在本 skill 内重写，需直接使用仓库文件：https://github.com/YeoLab/eclip
- 若分析需要真正的单碱基交联位点，官方文档未提供可直接执行的命令；只能以 CLIPper cluster 加 `--poisson-cutoff`/`--FDR` 收紧，并在报告中说明分辨率为 cluster 级。

### 6.6 交联区 motif（HOMER 官方）

```bash
findMotifsGenome.pl clip_clusters.bed hg38 clip_motif_out/ -size given -rna -len 6,8
```
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

取具体 motif 位点（官方两种方式）：

```bash
findMotifsGenome.pl clip_clusters.bed hg38 clip_motif_out/ -find motif1.motif > motif_instances.txt
annotatePeaks.pl clip_clusters.bed hg38 -m motif1.motif > annotated_with_motif.txt
```
来源：同上（`-find` 输出列：Region ID / 距中心偏移 / 位点序列 / motif 名 / 链 / motif score；`annotatePeaks.pl -m` 输出第 21 列为 motif 实例，格式 `<distance>(<sequence>,<strand>,<conservation>)`）。

### 6.7 PARalyzer / CTK

- `https://github.com/YeoLab/PARalyzer` 返回 404（仓库不存在），GitHub 搜索亦无 YeoLab 的 PARalyzer 仓库（https://api.github.com/repos/YeoLab/PARalyzer）。**PARalyzer 的官方文档未能查到**，故本 skill 不写 PARalyzer 命令。
- CTK 的官方文档本次未查证到可引用页面，同样不写命令。
- 结论：CLIP peak calling 只用可查证的 CLIPper；如需 PARalyzer/CTK，必须先补齐官方文档再使用。

## 7. 质控（QC）

### 7.1 IP 富集效率

官方未提供统一的「IP 富集效率」计算命令。可用官方字段直接读：
- exomePeak2 输出列 `RPM.input` / `RPM.IP` / `log2FC`（官方定义见 4.4）即为每个 peak 的 IP/input 富集度量，来源：exomePeak2 vignette。
- 判据：整体 `log2FC` 分布应明显右偏（IP > input）；若大量 peak `log2FC` ≈ 0，说明 IP 失败或建库/比对链方向错误，先查 3.6 的链特异性，不要先调 `p_cutoff`。官方文档未给数值阈值。

### 7.2 FRiP（Fraction of Reads in Peaks）

**官方文档未提供 FRiP 专用命令**（exomePeak2、CLIPper、MACS3 文档均无该指标）。用 bedtools 官方选项组合统计（命令见 3.7），口径：落在 peak 内的 reads ÷ 有效比对 reads。判据（业界常用量级，此处仅作排查方向）：CLIP/eCLIP 的 FRiP 通常明显高于 RIP；若 FRiP 极低而 peak 数很多，优先怀疑黑名单/重复区未过滤（eCLIP 官方提供 ENCODE 黑名单 `ENCFF039QTN`，见 https://github.com/YeoLab/eclip），而不是继续放宽阈值。

### 7.3 链特异性

命令与判据见 3.6（RSeQC `infer_experiment.py`）。链方向错了会把一半 reads 丢进「无法判定」，peak 数骤降。

### 7.4 peak 在转录本上的分布（5'UTR / CDS / 3'UTR）

用 ChIPseeker 官方 `annotatePeak` 输出 `annotation` 列后 `plotAnnoBar` / `plotDistToTSS` 统计（命令见 8.1）。官方注释优先级：Promoter > 5' UTR > 3' UTR > Exon > Intron > Downstream > Intergenic（https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/vignettes/ChIPseeker.Rmd）。
- 判据：m6A 通常富集在 3'UTR 与 CDS 附近、TSS 附近偏少；CLIP cluster 的分布取决于 RBP 类型（无通用阈值）；若 5'UTR/启动子异常高，先查 rRNA/重复区污染与链方向。

## 8. 下游：peak 注释与关联

### 8.1 peak 注释（ChIPseeker 官方 vignette）

```r
library(ChIPseeker)
library(TxDb.Hsapiens.UCSC.hg19.knownGene)
library(org.Hs.eg.db)
txdb <- TxDb.Hsapiens.UCSC.hg19.knownGene

peak <- readPeakFile("m6a_peaks.bed")
peakAnno <- annotatePeak(peak, tssRegion = c(-3000, 3000),
                         TxDb = txdb, annoDb = "org.Hs.eg.db")

plotAnnoPie(peakAnno)
plotAnnoBar(peakAnno)
plotDistToTSS(peakAnno)
```
来源：https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/vignettes/ChIPseeker.Rmd（渲染版：https://bioconductor.uib.no/packages/3.19/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html）

官方要点：TSS 默认 -3kb~+3kb；`as.data.frame(peakAnno)` 可 `write.table` 导出；`annoDb` 提供时追加 SYMBOL/GENENAME/ENSEMBL/ENTREZID；TxDb 可选 `TxDb.Hsapiens.UCSC.hg38.knownGene`、`TxDb.Mmusculus.UCSC.mm10.knownGene` 等，或用 `makeTxDbFromUCSC`/`makeTxDbFromBiomart` 自建；用 EnsDb 时需 `seqlevelsStyle(edb) <- "UCSC"`。

多组比较：`peakAnnoList <- lapply(files, annotatePeak, TxDb=txdb, tssRegion=c(-3000,3000), verbose=FALSE)` 后 `plotAnnoBar(peakAnnoList)` / `plotDistToTSS(peakAnnoList)`。

### 8.2 与差异表达关联

见 4.6：官方文档未提供关联命令，按「peak 的 geneID ↔ 差异基因表」取交集并比较 log2FC 分布（表达侧用 `--quantMode GeneCounts` + 本 preset 的 `bulk-rnaseq`）。

### 8.3 与可变剪接关联

本 skill 抓取到的官方文档（exomePeak2 / CLIPper / ChIPseeker / HOMER / MACS3 / STAR / bowtie2 / bedtools / RSeQC / umi_tools / SortMeRNA）**均未提供**「peak 与可变剪接事件关联」的命令。流程与判据：
1. 剪接事件定量：需要剪接分析工具（其官方文档需另行查证，本 skill 不写命令）。
2. 关联口径：位于剪接位点 ± 窗口内的 CLIP cluster（`bedtools intersect` 官方选项与剪接位点区间求交，命令见 3.7）与差异剪接事件取交集，报告交集比例；窗口大小官方无推荐值，需在方法学中显式声明。
3. RBP 类型判据：调节剪接的 RBP 其 cluster 应显著富集在剪接位点邻近的内含子区；若富集在 3'UTR，更可能是稳定性/翻译调控而非剪接。

## 9. 产出目录

```
<project>/
├─ 00_qc/                       # infer_experiment.py 输出、rRNA 占比、去重前后计数
├─ 01_align/                    # STAR / bowtie2 的 BAM、Log.final.out
├─ 02_peaks/
│  ├─ merip/                    # exomePeak2_output/{peaks.bed,peaks.csv,peaks.rds}
│  ├─ rip/                      # macs3: rip_peaks.xls / .narrowPeak / .summits.bed / _treat_pileup.bdg
│  └─ clip/                     # clipper: *.peakClusters.bed（必要时 narrowPeak）
├─ 03_motif/                    # findMotifsGenome.pl: homerResults.html, knownResults.txt, *.motif
├─ 04_annotation/               # annotatePeak: peakAnno.tsv, plotAnnoBar/plotDistToTSS
└─ 05_report/                   # 方法学参数表（逐条带官方 URL）、QC 汇总、版本清单
```

## 10. 验收清单

- [ ] 数据流型已判定（MeRIP / RIP / CLIP），且使用的工具与其官方定位一致（RIP 用了通用 caller 并显式说明）。
- [ ] BAM 已按坐标排序并建索引；CLIP 的 BAM 已去重（umi_tools 或官方 eCLIP 脚本）。
- [ ] 链方向已用 `infer_experiment.py` 判定，并与 exomePeak2 `strandness` 取值对应一致。
- [ ] MeRIP：`exomePeak2()` 记录了 `genome`（GC 校正是否启用）、`p_cutoff`、`mode`、`strandness`；输出含 BED/CSV/RDS 三件。
- [ ] m6A motif：`motif_based`/`motif_sequence`（默认 DRACH）或 HOMER `-size given -rna` 之一，且报告写明 `-rna` 的已知库限制。
- [ ] RIP：`-c` input 对照存在；`-g` 与物种匹配；`--keep-dup` 取值记录在案。
- [ ] CLIP：`--species` 在官方支持列表内；`--processors`/`--poisson-cutoff`/`--FDR`/`--minreads` 全部记录；未误用不存在的 `--threads`。
- [ ] 质控四项齐备：IP 富集（`RPM.IP`/`RPM.input`/`log2FC`）、FRiP、链特异性、peak 转录本分布。
- [ ] peak 注释走 ChIPseeker `annotatePeak` + `plotAnnoBar`/`plotDistToTSS`，TxDb 版本与基因组一致。
- [ ] 报告中每条命令都能追到第 11 节的官方 URL。
- [ ] 凡官方文档缺失处，报告写的是「官方文档未提供可直接执行的命令」+ 流程/判据，没有自造脚本。

## 11. 参考文件

- `references/official-docs.md` — 本次实际抓取的官方文档清单（含抓取状态、每个页面支撑哪些命令）
- `references/parameters.md` — 按 MeRIP / RIP / CLIP 三类分列的参数与默认值表
- `references/troubleshooting.md` — 常见失败模式与排查顺序

本 skill **不含 `scripts/`**：所引用工具均自带官方脚本/CWL（exomePeak2 的 R 函数、CLIPper 的 `clipper` 命令、eCLIP 仓库的 `*.pl` 与 CWL），无需也不应另写脚本。
