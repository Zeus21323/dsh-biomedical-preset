---
name: epigenomics-peak-calling
description: |
  Epigenomics peak-calling and QC mainline for ChIP-seq, ATAC-seq and CUT&Tag/CUT&RUN: assay triage,
  alignment (bowtie2/BWA), duplicate handling (Picard MarkDuplicates / samtools markdup), MAPQ and ENCODE
  blacklist filtering, peak calling (MACS3/MACS2, SEACR), replicate concordance (IDR, rescue and
  self-consistency ratios), QC metrics (FRiP, TSS enrichment, fragment size, bigWig signal extraction),
  motif analysis (HOMER findMotifsGenome.pl, MEME-ChIP) and peak annotation (ChIPseeker).
  Trigger when user mentions: ChIP-seq, ATAC-seq, CUT&Tag, CUT&RUN, peak calling, MACS2, MACS3, SEACR,
  IDR, FRiP, blacklist, TSS enrichment, 表观遗传, 峰 calling, 表观组。
  中文触发词：ChIP-seq、ATAC-seq、CUT&Tag、peak calling、MACS2、MACS3、SEACR、IDR、FRiP、表观遗传。
category: omics
tags: chip-seq, atac-seq, cut-and-tag, peak-calling, epigenomics
---

# 表观组 peak calling 与质控主线（ChIP-seq / ATAC-seq / CUT&Tag）

本技能的每一条命令、参数名与默认值均逐字取自官方文档，命令块下方给出出处 URL。
凡官方文档未提供可直接执行命令的环节，集中列在 `references/official-docs.md` 的
「官方文档缺失清单」，正文只写流程与判据，不自造脚本。

## 0 使用约定

1. **先分型、后选参数**：ChIP-seq（TF / histone mark）、ATAC-seq、CUT&Tag/CUT&RUN 的 caller 与参数体系不同，见 §1。
2. **命令优先**：官方有命令就用官方命令；官方只有阈值与判据就只抄阈值与判据。
3. **版本口径**：MACS3 官方文档标注版本 3.1.0；deepTools 文档标注 3.5.6；IDR README 安装包为 2.0.4。
   实际执行前用 `--help` 与官方文档比对一次（MACS3 文档本身即提示 `-h` 为完整选项来源）。
4. **不要混用版本语义**：`--shift/--extsize` 是 MACS2 起的语义，旧 `--shiftsize` 已被取代
   （MACS3 文档原文：`this is NOT the legacy --shiftsize option which is replaced by --extsize from MACS version 2`）。

## 1 统一入口分型（决定 narrow / broad / SEACR）

| 数据类型 | 信号形态 | 默认 peak 形态 | 首选 caller | 关键约束 |
| --- | --- | --- | --- | --- |
| ChIP-seq（转录因子） | 点状、sharp | narrowPeak | MACS3 `callpeak`（`-f BAM`/`BAMPE`） | 需要 input/IgG control；重复一致性用 IDR |
| ChIP-seq（组蛋白修饰，broad mark） | 域状、宽 | broadPeak / gappedPeak | MACS3 `callpeak --broad` | 用 `--broad-cutoff`，不是单纯放宽 `-q` |
| ChIP-seq（组蛋白修饰，narrow mark） | 点状 | narrowPeak | MACS3 `callpeak` | 按 ENCODE 的 mark 名单区分 broad/narrow |
| ATAC-seq | 点状 + 开放域 | narrowPeak（+ 可选 broad 区） | MACS3 `callpeak`（`-f BAMPE`，或 ENCODE 的 `-f BED` + shift/extsize） | 通常无 control，用 `--nolambda` 一类的无对照口径；PE 不能用非 0 `--shift` |
| CUT&Tag / CUT&RUN | 极稀疏、背景以 0 为主 | BED 富集区间（无 narrowPeak 语义） | SEACR（`relaxed`/`stringent`） | 需 IgG 对照 bedgraph 或数值阈值；spike-in 归一化后再定 `norm`/`non` |

分型判据（按官方文字）：

- ENCODE 对 narrow/broad 的判据是 mark 名单本身：Broad Marks = H3F3A, H3K27me3, H3K36me3, H3K4me1,
  H3K79me2, H3K79me3, H3K9me1, H3K9me2, H4K20me1；Narrow Marks = H2AFZ, H3ac, H3K27ac, H3K4me2,
  H3K4me3, H3K9ac；H3K9me3 单列为 Exception。
  来源：https://www.encodeproject.org/chip-seq/histone/
- ENCODE 说明 ATAC-seq 的 peak 会「同时像 TF 的窄峰和 histone 的宽域」，因此允许 narrow 与 broad 两套。
  来源：https://www.encodeproject.org/atac-seq/
- MACS3 对 broad 的定义：`--broad` 用两个 cutoff 区分 broader/weaker 与 narrower/stronger 并做嵌套，
  输出 gappedPeak；并明确「若只想要更宽的峰、不关心嵌套结构，直接用更弱的 `-p`/`-q`，不要用 `--broad`」。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html
- SEACR 的适用前提：CUT&RUN/CUT&Tag 这类「背景被 0 主导」的稀疏数据，且**要求 paired-end 派生的 bedGraph**。
  来源：https://github.com/FredHutch/SEACR

## 2 上游：比对、去重、过滤

### 2.1 比对（bowtie2 / BWA 官方用法）

bowtie2 通用调用式（官方 Usage 行）：

```bash
bowtie2 [options]* -x <bt2-idx> {-1 <m1> -2 <m2> | -U <r> | --interleaved <i> | --sra-acc <acc> | -b <bam>} -S [<sam>]
```
来源：https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml

bowtie2 常用预设与线程（官方 Preset 表原文）：`--very-sensitive` = `-D 20 -R 3 -N 0 -L 20 -i S,1,0.50`；
默认端到端预设为 `--sensitive` = `-D 15 -R 2 -N 0 -L 22 -i S,1,1.15`；线程用 `-p/--threads`。
来源：https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml

BWA（官方 SYNOPSIS 原文）：

```bash
bwa index ref.fa
bwa mem ref.fa read1.fq read2.fq > aln-pe.sam
```
来源：https://bio-bwa.sourceforge.net/bwa.shtml

BWA-MEM 与 Picard 兼容性（官方原文）：BWA-MEM 可能产生 split alignment，
`some tools such as Picard's markDuplicates does not work with split alignments. One may consider to use option -M to flag shorter split hits as secondary.`
来源：https://bio-bwa.sourceforge.net/bwa.shtml

### 2.2 MAPQ 过滤（samtools 官方）

`samtools view -q INT` 语义（官方选项表原文）：`Skip alignments with MAPQ smaller than INT [0]`。
来源：https://www.htslib.org/doc/samtools-view.html

官方 EXAMPLES 中给出的 BAM 输出与 flag 过滤写法：

```bash
samtools view -bo aln.bam aln.sam
samtools view -b -f 128 -F 16 a.bam > a.fwd1.bam
```
来源：https://www.htslib.org/doc/samtools-view.html

### 2.3 去重（samtools markdup 与 Picard MarkDuplicates）

samtools markdup 官方完整链路（原文 EXAMPLES）：

```bash
samtools collate -o namecollate.bam example.bam
samtools fixmate -m namecollate.bam fixmate.bam
samtools sort -o positionsort.bam fixmate.bam
samtools markdup positionsort.bam markdup.bam
```
来源：https://www.htslib.org/doc/samtools-markdup.html

markdup 关键默认值（官方 OPTIONS 原文）：`-l INT` 期望最大读长 `[300]`；`-r` 直接移除重复；
`-d INT` 光学重复距离默认 `0`（不做光学判定），HiSeq 建议 100、NovaSeq 约 2500；`--mode` 默认 `t`（按模板起止）。
来源：https://www.htslib.org/doc/samtools-markdup.html

Picard MarkDuplicates 官方 Usage example 原文：

```bash
java -jar picard.jar MarkDuplicates \
      I=input.bam \
      O=marked_duplicates.bam \
      M=marked_dup_metrics.txt
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/35967618836635-MarkDuplicates-Picard

MarkDuplicates 关键默认值（官方参数表原文）：`REMOVE_DUPLICATES` 默认 `false`；
`OPTICAL_DUPLICATE_PIXEL_DISTANCE` 默认 `100`（patterned flowcell 建议 2500）；`TAGGING_POLICY` 默认 `DontTag`；
`MAX_FILE_HANDLES_FOR_READ_ENDS_MAP` 默认 `8000`；输入必须 coordinate sorted。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/35967618836635-MarkDuplicates-Picard

### 2.4 黑名单过滤（ENCODE blacklist 官方说明）

ENCODE 对 exclusion list 的定位原文：这些区域「have anomalous, unstructured, high signal/read counts …
independent of cell line and type of experiment」，且「tend to have a very high ratio of multi-mapping to unique
mapping reads and high variance in mappability」，因此 `it is recommended to use this exclusion list alongside
mappability filters`。
来源：https://www.encodeproject.org/annotations/ENCSR636HFF/

官方给出的黑名单文件获取命令（nf-core/atacseq usage 文档原文，含 v1/v2/v3 各版本）：

```bash
wget -L https://www.encodeproject.org/files/ENCFF001TDO/@@download/ENCFF001TDO.bed.gz && gunzip ENCFF001TDO.bed.gz && mv ENCFF001TDO.bed hg19-blacklist.v1.bed
wget -L https://raw.githubusercontent.com/Boyle-Lab/Blacklist/master/lists/hg38-blacklist.v2.bed.gz && gunzip hg38-blacklist.v2.bed.gz
wget -L https://www.encodeproject.org/files/ENCFF356LFX/@@download/ENCFF356LFX.bed.gz && gunzip ENCFF356LFX.bed.gz && mv ENCFF356LFX.bed hg38-blacklist.v3.bed
```
来源：https://raw.githubusercontent.com/nf-core/atacseq/master/docs/usage.md

deepTools 侧的黑名单参数（官方原文）：`--blackListFileName, -bl` 传 BED/GTF，
`Currently this works by rejecting genomic chunks that happen to overlap an entry`，并提醒需要相应调整 effective genome size。
来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

### 2.5 PE 数据的 `-f BAMPE`（MACS3 官方说明）

`-f/--format` 官方原文：可选 `ELAND, BED, ELANDMULTI, ELANDEXPORT, SAM, BAM, BOWTIE, BAMPE, BEDPE, FRAG`，
默认 `AUTO`；并且 `MACS3 can't detect BAMPE, BEDPE or FRAG format with AUTO, and you have to implicitly specify the format`。
`BAMPE` 模式下 `MACS3 will use the real fragments inferred from alignment results for reads pileup`。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

PE 建库到 BEDPE 的官方转换命令：

```bash
macs3 randsample -i the_BAMPE_file.bam -f BAMPE -p 100 -o the_BEDPE_file.bed
macs3 filterdup -i the_BAMPE_file.bam -f BAMPE --keep-dup all -o the_BEDPE_file.bed
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

## 3 peak calling

### 3.1 MACS3 / MACS2 官方命令（四条标准场景）

```bash
macs3 callpeak -t ChIP.bam -c Control.bam -f BAM -g hs -n test -B -q 0.01
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

```bash
macs3 callpeak -t ChIP.bam -c Control.bam --broad -g hs --broad-cutoff 0.1
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

```bash
macs3 callpeak -f BAMPE -t ATAC.bam -g hs -n test -B -q 0.01
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

```bash
macs3 callpeak -f BAM -t ATAC.bam -g hs -n test -B -q 0.01 --shift -50 --extension 100
```
来源：https://macs3-project.github.io/MACS/docs/callpeak.html
（该条为官方示例「Peak calling on ATAC-seq (focusing on insertion sites, and using single-end mode)」，
原文写的是 `--extension 100`；选项章节文档化的名字是 `--extsize`，见下一条。）

ATAC-seq / DNase 切割位点类数据的 `--nomodel --shift --extsize` 官方组合（原文）：

> To find enriched cutting sites such as some DNAse-Seq datasets … If the wanted smoothing window is 200bps,
> then use `--nomodel --shift -100 --extsize 200`.

来源：https://macs3-project.github.io/MACS/docs/callpeak.html

`--shift`/`--extsize` 官方语义：`--extsize` 仅在 `--nomodel` 开启（或建模失败且 `--fix-bimodal`）时有效，
把 reads 按 5'→3' 延伸到固定长度；`--shift` 在 `--nomodel` 下先平移 5' 端再按 `--extsize` 延伸；
负值向 3'→5' 方向平移。官方默认 `--shift 0`。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

**PE 的关键限制（官方原文）**：`you can't set values other than 0 if the format is BAMPE or BEDPE for paired-end data`。
因此「PE + shift/extsize」这一组合不成立：要么 `-f BAMPE` 且不设 shift，要么先用 `-f BED`（或 tagAlign）
再设 shift/extsize。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

ENCODE ATAC-seq pipeline 实际下发的 MACS2 命令（ENCODE 官方源码，`encode_task_macs2_atac.py`）：

```bash
macs2 callpeak -t {ta} -f BED -n {prefix} -g {gensz} -p {pval_thresh} --shift {shiftsize} --extsize {extsize} --nomodel -B --SPMR --keep-dup all --call-summits
```

其中官方默认：`--pval-thresh` = `0.01`；`--smooth-win` = `150`；`shiftsize = -int(round(float(smooth_win)/2.0))`
即 `-75`；`extsize = smooth_win` 即 `150`；`--cap-num-peak` = `300000`（按 narrowPeak 第 8 列排序后截断）。
来源：https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_macs2_atac.py
（同一目录还提供 `encode_task_macs2_chip.py`、`encode_task_macs2_signal_track_atac.py`：
https://github.com/ENCODE-DCC/atac-seq-pipeline/tree/master/src ）

无对照样本时的官方口径：`--nolambda` → `MACS3 will use the background lambda as local lambda`，
并注明 `It is particularly recommended while calling peaks without control sample`。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

species/effective genome size 官方预置值：`hs: 2,913,022,398 for GRCh38`、`mm: 2,652,783,500 for GRCm38`、
`ce: 100,286,401 for WBcel235`、`dm: 142,573,017 for dm6`。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

MACS3 新版执行相关选项：`--threads N` 设 CPU 预算（`--threads 1` 等价串行）；
`callpeak`/`callvar` 支持 `--process-backend {auto,serial}`。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html 与 https://macs3-project.github.io/MACS/

MACS2 与 MACS3 的关系：MACS3 官方文档是当前的命令行权威来源，选项沿革以「from MACS version 2」这类表述出现；
MACS2 的选项名请以本机 `macs2 --help` 与官方 README 的版本记录核对后再执行（官方未逐版本并列两套选项表）。
来源：https://macs3-project.github.io/MACS/

### 3.2 SEACR 官方用法（CUT&Tag / CUT&RUN）

官方 Usage 行（位置参数，非长选项）：

```
bash SEACR_1.3.sh experimental bedgraph [control bedgraph | numeric threshold] ["norm" | "non"] ["relaxed" | "stringent"] output prefix
```
来源：https://github.com/FredHutch/SEACR

字段含义（官方原文摘要）：Field 1 目标 bedgraph（UCSC bedgraph，**省略 0 信号区间**）；Field 2 IgG control bedgraph，
或 0–1 的数值阈值（返回 total signal 最高的前 n 比例）；Field 3 `"norm"` 把 control 归一到 target、`"non"` 跳过，
官方注明 `"norm" is recommended unless experimental and control data are already rigorously normalized to each other (e.g. via spike-in)`；
Field 4 `"relaxed"`（knee 与 peak 之间）或 `"stringent"`（曲线峰值）；Field 5 输出前缀。
来源：https://github.com/FredHutch/SEACR

官方示例三条：

```bash
bash SEACR_1.3.sh target.bedgraph IgG.bedgraph norm stringent output
bash SEACR_1.3.sh target.bedgraph IgG.bedgraph non relaxed output
bash SEACR_1.3.sh target.bedgraph 0.01 non stringent output
```
来源：https://github.com/FredHutch/SEACR

SEACR 输入 bedGraph 的官方制备命令（BAM → read-pair bedGraph）：

```bash
bedtools bamtobed -bedpe -i $sample.bam > $sample.bed
awk '$1==$4 && $6-$2 < 1000 {print $0}' $sample.bed > $sample.clean.bed
cut -f 1,2,6 $sample.clean.bed | sort -k1,1 -k2,2n -k3,3n > $sample.fragments.bed
bedtools genomecov -bg -i $sample.fragments.bed -g my.genome > $sample.fragments.bedgraph
```
来源：https://github.com/FredHutch/SEACR

SEACR 输出为 BED6：`<chr> <start> <end> <total signal> <max signal> <max signal region>`，
文件名为 `<output prefix>.stringent.bed` 或 `<output prefix>.relaxed.bed`。
来源：https://github.com/FredHutch/SEACR

> 校正常见误记：SEACR **没有** `--control` / `--norm` / `--non` 这些开关，官方接口就是上表的 5 个位置参数。

### 3.3 官方管线入口（可选，替代手工拼装）

- nf-core/atacseq：`nextflow run nf-core/atacseq --input ./samplesheet.csv --outdir ./results --genome GRCh37 --read_length 150 -profile docker`；
  该管线默认用 MACS2 `--broad`、`--narrow_peak` 可切窄峰，并对 consensus peak 做 featureCounts 计数与 DESeq2 差异可及性分析。
  来源：https://raw.githubusercontent.com/nf-core/atacseq/master/docs/usage.md 与 https://raw.githubusercontent.com/nf-core/atacseq/master/docs/output.md
- nf-core 的 MACS2 模块按 `meta.single_end` 自动选 `--format BAM` / `--format BAMPE`，并强制传 `--gsize`，即
  `macs2 callpeak ... --gsize $macs2_gsize --format $format --name $prefix --treatment $ipbam $control`。
  来源：https://raw.githubusercontent.com/nf-core/atacseq/master/modules/nf-core/macs2/callpeak/main.nf

## 4 重复一致性与「无重复」处理

### 4.1 IDR 官方命令

IDR 官方 Usage（README 原文）：

```bash
idr --samples ../idr/test/data/peak1 ../idr/test/data/peak2
idr --samples ../idr/test/data/peak1 ../idr/test/data/peak2 --peak-list ../idr/test/data/merged_peaks
```
来源：https://raw.githubusercontent.com/kundajelab/idr/master/README.md

`--input-file-type` 官方取值：`{narrowPeak,broadPeak,bed,gff}`；`--rank` 取值
`signal.value p.value q.value columnIndex`，narrowPeak/broadPeak 默认 `signal.value`；`--idr-threshold` 默认「报告全部」；
`--soft-idr-threshold` 默认 `0.05`（只用于统计，不全量过滤）；`--use-best-multisummit-IDR` 官方注明是为
「peak callers that don't do a good job splitting scores across multi summit peaks (e.g. MACS)」准备的绕行方案。
来源：https://raw.githubusercontent.com/kundajelab/idr/master/README.md

因此带 `--input-file-type narrowPeak` 的显式写法：

```bash
idr --samples rep1.narrowPeak rep2.narrowPeak --input-file-type narrowPeak --output-file idrValues.txt --rank p.value
```
来源：https://raw.githubusercontent.com/kundajelab/idr/master/README.md

ENCODE ATAC-seq pipeline 实际下发的 IDR 命令（官方源码）：

```bash
idr --samples {peak1} {peak2} --peak-list {peak_pooled} --input-file-type narrowPeak --output-file {idr_out} --rank {rank} --soft-idr-threshold {thresh} --plot --use-best-multisummit-IDR --log-output-file {idr_stdout}
```

官方默认：`--idr-thresh` = `0.1`（写入 `--soft-idr-threshold`）、`--idr-rank` = `p.value`；
随后按 `$12 >= -log10(thresh)` 过滤出 IDR peak（12 列格式）。
来源：https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_idr.py

### 4.2 一致性指标与阈值（ENCODE 官方口径）

- TF ChIP-seq：`replicate concordance is measured by calculating IDR values … The experiment passes if both rescue and self consistency ratios are less than 2.`
  来源：https://www.encodeproject.org/chip-seq/transcription_factor/
- ATAC-seq：同上判据（`both rescue and self consistency ratios are less than 2`），并要求 IDR peak 数 >70,000（>50,000 可接受）。
  来源：https://www.encodeproject.org/atac-seq/
- Histone ChIP-seq：不用 IDR，而用重复/伪重复的「naive overlap」：replicated peaks 是
  `either observed in both replicates, or are observed in two pseudoreplicates`；伪重复是
  `peak sets called on half of the pooled reads, chosen at random without replacement`；
  unreplicated 时 stable peaks 定义为与两个伪重复 peak 各重叠 ≥50%。
  来源：https://www.encodeproject.org/chip-seq/histone/
- ATAC 的 replicated peak / region 口径：对 pooled 数据 call peak 后，
  `we only retain those that have at least 50% overlap with a peak in both replicates`；
  官方明确两套结果的取舍：replicated 集偏「低假阴性」，IDR 集偏「低假阳性」。
  来源：https://www.encodeproject.org/atac-seq/

### 4.3 只有 1 个重复时怎么报

| 场景 | 官方做法 | 需要在报告里写明 |
| --- | --- | --- |
| TF ChIP-seq 单重复 | 官方走「unreplicated」管线：用 reads 随机二分得到 pseudoreplicates，再做 `pseudoreplicated IDR thresholded peaks`；**不产出** optimal/conservative 集 | 声明为 pseudoreplicate IDR，不是生物学重复 IDR；不得引用 `rescue/self-consistency < 2` 作为通过证据 |
| Histone ChIP-seq 单重复 | 官方走 `partition concordance`：relaxed peaks 中与两个伪重复 peak 各 ≥50% 重叠者保留 | 声明为 pseudoreplicated peaks |
| ATAC-seq 单重复 | 官方：`In the absence of replicates, the same procedure listed below is used on pseudoreplicates obtained by subsampling reads from a single replicate` | 同上 |
| 任何类型、无法做伪重复 | 只报单样本 peak，并显式标注「无重复一致性证据」；SEACR 场景可用数值阈值（如 top 1%）代替 IgG 阈值 | 用 `bash SEACR_1.3.sh target.bedgraph 0.01 non stringent output` 时，说明阈值来源是「按 AUC 取前 1%」，不是经验 FDR |

来源（前三行）：https://www.encodeproject.org/chip-seq/transcription_factor/ 、
https://www.encodeproject.org/chip-seq/histone/ 、https://www.encodeproject.org/atac-seq/
来源（SEACR 数值阈值）：https://github.com/FredHutch/SEACR

## 5 质控指标

### 5.1 FRiP（fraction of reads in peaks）

ENCODE 官方阈值（ATAC-seq）：`The fraction of reads in called peak regions (FRiP score) should be >0.3, though values
greater than 0.2 are acceptable.`
来源：https://www.encodeproject.org/atac-seq/

ENCODE 对 TF ChIP-seq 的口径：FRiP 属 `Additional metrics`，`calculated without defined thresholds`，
`useful in comparing similar experiments`（即不得拿固定阈值判生死）。
来源：https://www.encodeproject.org/chip-seq/transcription_factor/

nf-core/atacseq 会把 FRiP 作为 MultiQC 自定义内容输出（`*.FRiP_mqc.tsv`）。
来源：https://raw.githubusercontent.com/nf-core/atacseq/master/docs/output.md

FRiP 的具体计算命令：ENCODE pipeline 提供 `src/encode_lib_frip.py`，但抓取到的官方文档未给出可直接执行的命令行
（见 §9 缺失清单第 5 条）。

### 5.2 TSS enrichment（deepTools 官方命令 + ENCODE 阈值）

先出 bigWig（deepTools 官方 Usage 与 ChIP-seq 示例）：

```bash
bamCoverage -b reads.bam -o coverage.bw
bamCoverage --bam a.bam -o a.SeqDepthNorm.bw --binSize 10 --normalizeUsing RPGC --effectiveGenomeSize 2150570000 --ignoreForNormalization chrX --extendReads
```
来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html
（官方说明：`This option requires --effectiveGenomeSize`；`RPGC = reads per genomic content (1x normalization)`；
默认 `--normalizeUsing None`、`--binSize 50`、`-p 1`。）

再算 TSS 前后矩阵与 profile：

```bash
computeMatrix reference-point -S <bigwig file(s)> -R <bed file(s)> -b 1000
plotProfile -m matrix.gz
```
来源：https://deeptools.readthedocs.io/en/develop/content/tools/computeMatrix.html 与
https://deeptools.readthedocs.io/en/develop/content/tools/plotProfile.html
（computeMatrix 官方默认：`reference-point` 下 `-b` 500、`-a` 1500、`-bs` 10、`--referencePoint TSS`；
`scale-regions` 下 `-m` 1000、`-b/-a` 0。plotProfile 只接受 computeMatrix 的 `.gz` 矩阵，`-m` + `-o/-out` 为必需参数。）

ENCODE TSS enrichment 判读表（官方原文数值）：

| Annotation | 数值 | 结论 |
| --- | --- | --- |
| hg19 Refseq TSS | < 6 | Concerning |
| hg19 Refseq TSS | 6 – 10 | Acceptable |
| hg19 Refseq TSS | > 10 | Ideal |
| GRCh38 Refseq TSS | < 5 | Concerning |
| GRCh38 Refseq TSS | 5 – 7 | Acceptable |
| GRCh38 Refseq TSS | > 7 | Ideal |
| mm9 GENCODE TSS | < 5 | Concerning |
| mm9 GENCODE TSS | 5 – 7 | Acceptable |
| mm9 GENCODE TSS | > 7 | Ideal |
| mm10 Refseq TSS | < 10 | Concerning |
| mm10 Refseq TSS | 10 – 15 | Acceptable |
| mm10 Refseq TSS | > 15 | Ideal |

来源：https://www.encodeproject.org/atac-seq/

### 5.3 fragment size 分布（ATAC 专用判据）

ENCODE 官方判据原文：`A nucleosome free region (NFR) must be present.`；
`A mononucleosome peak must be present in the fragment length distribution … longer than 147 bp but shorter than 147*2 bp`。
来源：https://www.encodeproject.org/atac-seq/

deepTools 侧可用于按片段长度取舍信号的官方参数：`--minFragmentLength`
（`primarily useful in ATACseq experiments, for filtering mono- or di-nucleosome fragments`，默认 0）与
`--maxFragmentLength`（默认 0）。
来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

fragment size 直方图的具体命令：抓取到的官方文档未提供（见 §9 缺失清单第 2 条），只写判据。

### 5.4 信号轨道（bigWig）与覆盖度 QC

- bigWig：用 §5.2 的 `bamCoverage` 官方命令；官方建议 ChIP-seq 类连续片段数据加 `--extendReads`，
  并提醒 `If you already normalized for GC bias using correctGCBias, you should absolutely NOT set the parameter --ignoreDuplicates!`。
  来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html
- MACS3 的 `-B` 产出 `NAME_treat_pileup.bdg` / `NAME_control_lambda.bdg`，官方只说
  `can be imported to the UCSC genome browser or be converted into even smaller bigWig files`，**未给出转换命令**。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html
- 覆盖度/富集 QC：nf-core/atacseq 用 deepTools `plotFingerprint` 与 `plotProfile`，
  产物为 `*.plotFingerprint.pdf|qcmetrics.txt|raw.txt`、`*.computeMatrix.mat.gz`、`*.plotProfile.pdf|tab`。
  来源：https://raw.githubusercontent.com/nf-core/atacseq/master/docs/output.md

### 5.5 文库复杂度与测序深度（判读用）

- ATAC：每个重复 25M（SE）/50M（PE）non-duplicate、non-mitochondrial aligned reads；
  mapping rate >95%（>80% 可接受）；NRF>0.9、PBC1>0.9、PBC2>3。
  来源：https://www.encodeproject.org/atac-seq/
- TF ChIP：每重复 20M usable fragments（10–20M low、5–10M insufficient、<5M extremely low）；
  NRF>0.9、PBC1>0.9、PBC2>10。
  来源：https://www.encodeproject.org/chip-seq/transcription_factor/
- Histone ChIP：narrow mark 每重复 20M、broad mark 45M usable fragments；H3K9me3 例外，
  组织/原代细胞要求 45M total mapped reads。
  来源：https://www.encodeproject.org/chip-seq/histone/

## 6 motif 分析

### 6.1 HOMER `findMotifsGenome.pl`（官方命令与背景选择）

官方 Usage 原文：`findMotifsGenome.pl <peak/BED file> <genome> <output directory> -size # [options]`，
示例 `findMotifsGenome.pl ERpeaks.txt hg18 ER_MotifOutput/ -size 200 -mask`；
`-size` 为**必填**（`The -size parameter is now mandatory`）。
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

区域大小的官方建议（原文）：TF peak 用 50 bp 抓主 motif、200 bp 同时抓主 motif 与共富集 motif；
histone mark 用 500–1000 bp；要按 peak 原始长度则 `-size given`；需要偏移用 `-size -300,100` 形式。
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

背景选择（官方原文）：
- 默认随机背景：`HOMER selects enough random background regions such that the total number of regions is 50000 or 2x the
  total number of peaks, which ever is larger (to change use "-N <#>")`，并按 GC 含量（5% 分箱）匹配。
- 自定义背景：`-bg <peak/BED file>`，会先用 mergePeaks 剔除与 target 重叠的区域，仍做 GC 归一化；
  当背景序列数少于 target 时，官方建议改用超几何检验 `-h`（默认是二项分布）。
- 序列偏倚归一化：`-nlen`（默认 3，`-nlen 0` 关闭）；masked vs unmasked 官方倾向
  `Usually it's safer to go with the masked version.`
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

motif 长度与数量默认：`-len` 默认 `8,10,12`；`-S` 默认 25；`-mis` 默认 2；`-p` 默认 1。
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

输入建议：MACS3 官方推荐用 `NAME_summits.bed` 做 motif 查找
（`If you want to find the motifs at the binding sites, this file is recommended.`）。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 6.2 MEME-ChIP（官方命令）

官方 Usage 原文：`meme-chip [options] <primary sequence file>`。
来源：https://meme-suite.org/meme/doc/meme-chip.html

关键官方约束与默认值：
- 输入序列 `Ideally the sequences should be all the same length, between 100 and 500 base-pairs long and centrally enriched
  for motifs`；并建议 `repeat mask` 成 `N`。
- 背景：`-neg <file>` 传对照 FASTA（此时 MEME 用 Differential Enrichment 目标函数）；
  `-order` 默认生成 2 阶 Markov 背景；`-bfile` 可直接给背景模型。
- 已知 motif 库：`-db <motif file>`（官方标注 recommended）；不提供则无法报告相似已知 motif。
- 输出：默认目录 `memechip_out`，含 `meme-chip.html`、`summary.tsv`、`combined.meme`。
来源：https://meme-suite.org/meme/doc/meme-chip.html

MEME-ChIP 只吃 FASTA、不吃基因组坐标；官方给的桥接方式是 HOMER 的 `-dumpFasta`
（`the files "target.fa" and "background.fa" will show up in your output directory. You can then use them with MEME`）。
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

## 7 peak 注释与下游关联

### 7.1 ChIPseeker（官方 vignette 命令）

```r
library(ChIPseeker)
library(TxDb.Hsapiens.UCSC.hg19.knownGene)
txdb <- TxDb.Hsapiens.UCSC.hg19.knownGene
peak <- readPeakFile(files[[4]])
peakAnno <- annotatePeak(files[[4]], tssRegion=c(-3000, 3000),
                         TxDb=txdb, annoDb="org.Hs.eg.db")
plotAnnoPie(peakAnno)
plotAnnoBar(peakAnno)
plotDistToTSS(peakAnno, title="Distribution of transcription factor-binding loci\nrelative to TSS")
```
来源：https://bioconductor.org/packages/3.21/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html
（同一 vignette 源码：https://raw.githubusercontent.com/YuLab-SMU/ChIPseeker/master/vignettes/ChIPseeker.Rmd）

官方语义要点：
- `annotatePeak` 默认 TSS 区间为 −3kb/+3kb；输出 `csAnno`，可用 `as.GRanges`/`as.data.frame` 转换后 `write.table`。
- 注释优先级：`Promoter > 5' UTR > 3' UTR > Exon > Intron > Downstream > Intergenic`，可用 `genomicAnnotationPriority` 改。
- `annoDb` 为可选，提供后追加 SYMBOL/GENENAME/ENSEMBL/ENTREZID 等列。
- 安装：`BiocManager::install("ChIPseeker")`。
  来源：https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/README.md

### 7.2 与表达关联

- ChIPseeker vignette 的定位即为「Annotation also create the possibility of integrating expression profile data to
  predict gene expression regulation」；官方给出的多对多映射函数是 `seq2gene`
  （`it consider host gene (exon/intron), promoter region and flanking gene from intergenic region`），
  示例 `seq2gene(peak, tssRegion = c(-1000, 1000), flankDistance = 3000, TxDb=txdb)` 之后接 `enrichPathway()`。
  来源：https://bioconductor.org/packages/3.21/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html
- ATAC 侧的官方管线口径：consensus peak 用 featureCounts 计数矩阵，再做 DESeq2 差异可及性
  （默认 `vst`，`--deseq2_vst false` 可切 `rlog`）；consensus peak 默认取全部样本 peak 的并集，
  可用 `--min_reps_consensus` 收紧为「可重复」集合。
  来源：https://raw.githubusercontent.com/nf-core/atacseq/master/docs/output.md

## 8 产出目录与验收清单

建议目录（自定约定，非官方要求）：

```
results/
├─ 01_align/            # bam、flagstat/idxstats/stats
├─ 02_dedup/            # markdup bam + duplication metrics
├─ 03_filtered/         # MAPQ + blacklist 过滤后的 bam（供 peak calling）
├─ 04_peaks/
│  ├─ macs3/            # *_peaks.narrowPeak|broadPeak|gappedPeak、*_summits.bed、*_peaks.xls
│  ├─ seacr/            # *.relaxed.bed | *.stringent.bed（CUT&Tag/CUT&RUN）
│  └─ idr/              # idrValues.txt、idr 过滤后的 narrowPeak、诊断 png
├─ 05_qc/               # FRiP、TSS enrichment、fragment size、plotFingerprint
├─ 06_signal/           # *.bw（bamCoverage）
├─ 07_motif/            # homerResults.html、knownResults.txt、memechip_out/
└─ 08_annot/            # annotatePeak 表、plotAnnoPie/Bar、plotDistToTSS
```

验收清单（每条都能追溯到官方来源）：

1. **比对**：给出 `samtools flagstat/idxstats/stats`；mapping rate 与深度按 §5.5 的对应数据类型判读。
2. **去重**：输出 MarkDuplicates 的 `M=` 指标文件或 `samtools markdup -s` 统计；PE 数据说明是否用 `-M`（BWA split hit）或先 `fixmate -m`。
3. **过滤**：声明 MAPQ 阈值（`samtools view -q`）与所用 blacklist 版本（v1/v2/v3 之一），并说明黑名单是按「拒绝重叠 chunk」还是先 intersect 再剔除。
4. **peak 文件**：narrow 场景产出 `narrowPeak` + `summits.bed`；broad 场景产出 `broadPeak` + `gappedPeak`；
   CUT&Tag/CUT&RUN 产出 SEACR BED6 并注明 `relaxed`/`stringent` 与阈值来源。
5. **参数留痕**：peak calling 命令原样落盘（含 `-g` 数值、`-q`/`-p`、`--broad-cutoff`、`--nomodel/--shift/--extsize` 是否使用；
   ATAC 若用 `-f BAMPE` 必须**没有**非 0 `--shift`）。
6. **重复一致性**：报 IDR 的 rescue ratio 与 self-consistency ratio，或 histone 的 overlap 比例；单重复场景按 §4.3 措辞声明。
7. **QC 数字**：FRiP（ATAC 阈值 >0.3，>0.2 可接受）、TSS enrichment（按物种/注释对表）、
   fragment size 是否有 NFR 与单核小体峰、peak 数（ATAC replicated >150,000 / IDR >70,000）。
8. **信号**：每个样本/条件一份 bigWig，注明 `--normalizeUsing` 与 `--effectiveGenomeSize` 取值。
9. **motif**：HOMER 的 `knownResults.txt` 与 `homerResults.html`；注明 `-size`、`-bg`、`-N`、`-mask` 是否启用；
   MEME-ChIP 若使用，注明 FASTA 来源（如 HOMER `-dumpFasta`）与 `-neg` 是否给定。
10. **注释**：`annotatePeak` 的 `tssRegion`、TxDb 版本、`annoDb`；产出注释分布图与 nearest-gene 表。

## 9 官方文档缺失清单（这些部分只写流程与判据）

详见 `references/official-docs.md`。摘录：

1. CUT&Tag（相对 CUT&RUN）没有独立官方 peak caller 文档；SEACR README 只针对 CUT&RUN/CUT&Tag 类稀疏数据给通用用法，spike-in 归一化因子的计算未见官方命令。
2. ATAC fragment size 直方图：官方给判据（NFR + mononucleosome 必需）与 deepTools 的 `--min/maxFragmentLength`，未给绘图命令。
3. TSS enrichment 的**数值**口径：ENCODE 给阈值与 pipeline 脚本（`src/encode_task_tss_enrich.py`），未给单行可执行命令；deepTools 只覆盖 profile 图。
4. MACS3 bedGraph → bigWig：官方只说可转，未给 `bedGraphToBigWig` 形式的命令。
5. FRiP 的逐样本计算命令：ENCODE 仅有 `src/encode_lib_frip.py`，抓取文档未给命令行。
6. MACS3 文档示例 `--extension` 与选项章节 `--extsize` 命名不一致，以本机 `--help` 为准。
7. SEACR 的 `--control/--norm/--non` 开关不存在，官方接口为 5 个位置参数。
8. MEME-ChIP 不接受基因组坐标，需先得到 FASTA（HOMER `-dumpFasta` 为官方给出的导出途径）。

## 参考文件

- `references/official-docs.md` — 全部官方 URL、逐条要点原文与缺失清单
- `references/parameters.md` — ChIP-TF / ChIP-histone / ATAC / CUT&Tag 四类参数与官方默认值
- `references/troubleshooting.md` — 常见失败模式与排查顺序
