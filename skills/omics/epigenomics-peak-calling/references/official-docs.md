# 官方文档索引与逐条要点

本文件只记录「实际抓取成功并读取」的官方文档，以及从中逐字摘出的要点。抓取时间：2026-10-29。
无法访问或返回 404 的地址单独列在 §2，不作为依据。

## 1 可用官方来源（29 条，其中 #29 为可达但空白的 Q&A 页，只作可达性记录）

| # | URL | 覆盖内容 | 关键原文/取值 |
| --- | --- | --- | --- |
| 1 | https://github.com/macs3-project/MACS | MACS3 总览、安装、变更记录 | `MACS3 3.1.0 requires Python 3.12 or later`；`Windows is not currently supported`；安装 `python -m pip install macs3` |
| 2 | https://macs3-project.github.io/MACS/ | 文档首页与 14 个子命令清单 | 子命令含 `callpeak`、`filterdup`、`predictd`、`pileup`、`hmmratac`、`bdgcmp` 等 |
| 3 | https://macs3-project.github.io/MACS/docs/callpeak.html | `callpeak` 全部选项、示例、输出、cutoff analysis | 见 §1.1 |
| 4 | https://github.com/FredHutch/SEACR | SEACR（原 FansenC/SEACR 已迁至 FredHutch） | 见 §1.2 |
| 5 | https://www.encodeproject.org/atac-seq/ | ATAC-seq 数据标准与处理管线 | 见 §1.3 |
| 6 | https://www.encodeproject.org/chip-seq/transcription_factor/ | TF ChIP-seq 标准与管线 | 见 §1.4 |
| 7 | https://www.encodeproject.org/chip-seq/histone/ | Histone ChIP-seq 标准与管线（broad/narrow mark 名单） | 见 §1.5 |
| 8 | https://www.encodeproject.org/annotations/ENCSR636HFF/ | DAC Exclusion List Regions（黑名单）定义 | 见 §1.6 |
| 9 | https://raw.githubusercontent.com/nf-core/atacseq/master/docs/usage.md | 管线运行方式、黑名单下载命令 | `nextflow run nf-core/atacseq --input ./samplesheet.csv --outdir ./results --genome GRCh37 --read_length 150 -profile docker`；blacklist wget 命令 |
| 10 | https://raw.githubusercontent.com/nf-core/atacseq/master/docs/output.md | 产物结构与 QC 项 | FRiP `*.FRiP_mqc.tsv`；plotFingerprint/plotProfile 产物名；consensus + featureCounts + DESeq2 |
| 11 | https://raw.githubusercontent.com/nf-core/atacseq/master/modules/nf-core/macs2/callpeak/main.nf | MACS2 模块实际参数 | `--gsize $macs2_gsize --format $format --name $prefix --treatment $ipbam $control`；`format = meta.single_end ? 'BAM' : 'BAMPE'` |
| 12 | https://raw.githubusercontent.com/kundajelab/idr/master/README.md | IDR 安装、用法、参数、输出格式 | 见 §1.7 |
| 13 | https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_macs2_atac.py | ENCODE ATAC 的 MACS2 调用 | 见 §1.8 |
| 14 | https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_idr.py | ENCODE 的 IDR 调用与过滤 | 见 §1.9 |
| 15 | https://github.com/ENCODE-DCC/atac-seq-pipeline/tree/master/src | ENCODE ATAC pipeline 全部 wrapper（含 `encode_lib_frip.py`、`encode_task_tss_enrich.py`、`encode_task_fraglen_stat_pe.py`） | 脚本存在性依据 |
| 16 | http://homer.ucsd.edu/homer/ngs/peakMotifs.html | HOMER `findMotifsGenome.pl` | 见 §1.10 |
| 17 | https://meme-suite.org/meme/doc/meme-chip.html | MEME-ChIP 命令行与默认值 | 见 §1.11 |
| 18 | https://deeptools.readthedocs.io/en/develop/content/tools/computeMatrix.html | computeMatrix（3.5.6） | 见 §1.12 |
| 19 | https://deeptools.readthedocs.io/en/develop/content/tools/plotProfile.html | plotProfile | `plotProfile -m matrix.gz`；`--outFileNameData` 导出 profile 数值 |
| 20 | https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html | bamCoverage / bigWig | 见 §1.13 |
| 21 | https://www.htslib.org/doc/samtools-markdup.html | samtools markdup（samtools 1.25） | 见 §1.14 |
| 22 | https://www.htslib.org/doc/samtools-view.html | samtools view（MAPQ、flag 过滤） | `-q INT … Skip alignments with MAPQ smaller than INT [0]` |
| 23 | https://gatk.broadinstitute.org/hc/en-us/articles/35967618836635-MarkDuplicates-Picard | Picard MarkDuplicates（GATK 4.6.2.0 文档） | 见 §1.15 |
| 24 | https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml | Bowtie 2 v2.5.5 手册 | 见 §1.16 |
| 25 | https://bio-bwa.sourceforge.net/bwa.shtml | BWA 手册 | 见 §1.17 |
| 26 | https://bioconductor.org/packages/3.21/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html | ChIPseeker vignette（2025-04-15） | 见 §1.18 |
| 27 | https://raw.githubusercontent.com/YuLab-SMU/ChIPseeker/master/vignettes/ChIPseeker.Rmd | 上条 vignette 的源码 | `annotatePeak(files[[4]], tssRegion=c(-3000, 3000), TxDb=txdb, annoDb="org.Hs.eg.db")` |
| 28 | https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/README.md | ChIPseeker 安装与引用 | `BiocManager::install("ChIPseeker")` |
| 29 | https://macs3-project.github.io/MACS/docs/qa.html | MACS3 Q&A 页 | 页面当前为空（只有导航），不提供参数依据 |

## 1.1 MACS3 `callpeak`（#3）

- 示例 1（TF ChIP）：`macs3 callpeak -t ChIP.bam -c Control.bam -f BAM -g hs -n test -B -q 0.01`
- 示例 2（histone broad）：`macs3 callpeak -t ChIP.bam -c Control.bam --broad -g hs --broad-cutoff 0.1`
- 示例 3（ATAC PE）：`macs3 callpeak -f BAMPE -t ATAC.bam -g hs -n test -B -q 0.01`
- 示例 4（ATAC 插入位点、SE）：`macs3 callpeak -f BAM -t ATAC.bam -g hs -n test -B -q 0.01 --shift -50 --extension 100`
- 示例 5–7（scATAC）：`-f BEDPE` / `-f FRAG` / `-f FRAG … --barcodes barcodes.txt`
- `-t` 是唯一 REQUIRED 参数；多文件 `-t A B C` 会合并。
- `-f` 默认 `AUTO`；`AUTO` 无法识别 `BAMPE/BEDPE/FRAG`，必须显式指定。
- `-g` 预置：`hs: 2,913,022,398 for GRCh38`、`mm: 2,652,783,500 for GRCm38`、`ce: 100,286,401`、`dm: 142,573,017`；默认 `hs ~2.9e9`。
- `-q` 默认 `0.05`；broad mark 可试 `0.01`；`-p` 一旦指定则用 p 值取代 q 值。
- `--broad` 默认 False；`--broad-cutoff` 默认 `0.1`（仅 `--broad` 时可用）。
- `--keep-dup` 默认 `1`；`AUTO` 时按二项分布（p=1e-5）保留；`FRAG` 格式下该选项被忽略。
- `--slocal` 默认 1000、`--llocal` 默认 10000。
- `--shift` 默认 `0`；官方：`you can't set values other than 0 if the format is BAMPE or BEDPE`。
- `--nomodel`/`--extsize` 组合：“If the wanted smoothing window is 200bps, then use `--nomodel --shift -100 --extsize 200`”。
- `--scale-to` 默认 `small`（把大数据缩到小数据；官方提醒放大反而增假阳性）。
- `--buffer-size` 默认 `100000`；`--cutoff-analysis` 默认 False，输出 `NAME_cutoff_analysis.txt`（p-score 0.3→10，步长 0.3）。
- 输出：`NAME_peaks.xls`（**1-based**）、`NAME_peaks.narrowPeak`（BED6+4）、`NAME_summits.bed`、
  `NAME_peaks.broadPeak` / `NAME_peaks.gappedPeak`（`--broad` 时）、`NAME_model.r`、`NAME_treat_pileup.bdg` / `NAME_control_lambda.bdg`（`-B`）。
- 官方提醒：narrowPeak 第 5 列可能超出 UCSC 的 [0,1000]，官方给了 awk 饱和写法。
- `--call-summits`：在同一 peak 内再找 subpeak，官方注明 candidate summit 需 ≥50bp 非负支持信号。
- CPU：`--threads N`；`--process-backend {auto,serial}`（callpeak/callvar）。

## 1.2 SEACR（#4）

- 定位：`Sparse Enrichment Analysis for CUT&RUN`；「intended to call peaks and enriched regions from sparse CUT&RUN or
  chromatin profiling data in which background is dominated by "zeroes"」。
- 依赖：R + Bedtools 在 PATH；**输入必须是 paired-end 派生的 bedGraph**。
- Usage：`bash SEACR_1.3.sh experimental bedgraph [control bedgraph | numeric threshold] ["norm" | "non"] ["relaxed" | "stringent"] output prefix`
- Field 1 需「omits regions containing 0 signal」。
- Field 3 `"norm" is recommended unless experimental and control data are already rigorously normalized to each other (e.g. via spike-in)`。
- 输出 6 列 BED：`<chr> <start> <end> <total signal> <max signal> <max signal region>`；文件名 `.stringent.bed` / `.relaxed.bed`。
- 官方 bedGraph 制备链：`bedtools bamtobed -bedpe` → awk 过滤（`$6-$2 < 1000`）→ `cut -f 1,2,6` 排序 → `bedtools genomecov -bg`。
- 已知版本修复：v1.2 修 `max signal region` 端坐标与新增「信号块内 bedgraph 行数下限」过滤；v1.3 修 thresholding 与零信号行。

## 1.3 ENCODE ATAC-seq（#5）

- Peak 形态：「ATAC-seq data looks both like TF data (narrow peaks of signal) as well as histone data (broader regions of openness)」。
- replicated peak：pooled 上 call，保留「at least 50% overlap with a peak in both replicates」。
- 无重复时：「the same procedure listed below is used on pseudoreplicates obtained by subsampling reads from a single replicate」。
- 取舍建议：replicated 集偏低假阴性，IDR 集偏低假阳性。
- 标准：≥2 生物学重复；SE 25M / PE 50M non-duplicate non-mitochondrial reads；mapping rate >95%（>80% 可接受）；
  IDR `both rescue and self consistency ratios are less than 2`；NRF>0.9、PBC1>0.9、PBC2>3；
  replicated peaks >150,000（>100,000 可接受）；IDR peaks >70,000（>50,000 可接受）；FRiP >0.3（>0.2 可接受）；
  NFR 必须存在、fragment length distribution 必须出现 mononucleosome peak（147–294 bp）。
- TSS enrichment 分档表（hg19/hg38/mm9/mm10）。
- 读长下限 45 bp；只支持 GRCh38 / mm10。

## 1.4 ENCODE TF ChIP-seq（#6）

- 每重复 20M usable fragments；10–20M low、5–10M insufficient、<5M extremely low。
- `The experiment passes if both rescue and self consistency ratios are less than 2.`
- NRF>0.9、PBC1>0.9、PBC2>10。
- FRiP 属「Additional metrics … without defined thresholds」。
- 单重复走 pseudoreplicate IDR：「there are no corresponding optimal and conservative peak sets in the unreplicated case」。
- 读长 ≥50 bp（可低至 25 bp）；只支持 GRCh38 / mm10。

## 1.5 ENCODE Histone ChIP-seq（#7）

- Broad Marks：H3F3A、H3K27me3、H3K36me3、H3K4me1、H3K79me2、H3K79me3、H3K9me1、H3K9me2、H4K20me1。
- Narrow Marks：H2AFZ、H3ac、H3K27ac、H3K4me2、H3K4me3、H3K9ac。Exception：H3K9me3。
- 深度：narrow mark 20M / broad mark 45M usable fragments；H3K9me3 组织与原代细胞 45M total mapped reads。
- 不用 IDR：replicated peaks = 两重复都出现，或出现在两个 pseudoreplicates（「peak sets called on half of the pooled reads,
  chosen at random without replacement」）；unreplicated 用 partition concordance（与两伪重复各 ≥50% 重叠）。

## 1.6 ENCODE DAC Exclusion List（#8）

- ENCSR636HFF = 「DAC Exclusion List Regions (previously named "DAC Blacklisted Regions")」。
- 定义：`anomalous, unstructured, high signal/read counts … independent of cell line and type of experiment`；
  由 80 个 open chromatin 轨道 + 20 个 ChIP-seq input/control 轨道、约 60 种组织/细胞系确定。
- 特征：`very high ratio of multi-mapping to unique mapping reads and high variance in mappability`，部分与 satellite/centromeric/telomeric 重复重叠。
- 结论：`it is recommended to use this exclusion list alongside mappability filters`。

## 1.7 IDR（#12）

- 安装：`wget https://github.com/kundajelab/idr/archive/2.0.4.zip` → `python3 setup.py install`。
- 用法：`idr --samples peak1 peak2`；`--peak-list` 传 merged/oracle peak 列表。
- 参数：`--input-file-type {narrowPeak,broadPeak,bed,gff}`；`--rank signal.value p.value q.value columnIndex`
  （narrow/broadPeak 默认 `signal.value`）；`--idr-threshold`（默认报告全部）；`--soft-idr-threshold` 默认 `0.05`；
  `--peak-merge-method` 默认 `sum`（signal/score/column）或 `min`（p/q 值）；`--use-best-multisummit-IDR`、
  `--plot`、`--initial-mu 0.10 / --initial-sigma 1.00 / --initial-rho 0.20 / --initial-mix-param 0.50`、
  `--max-iter 3000`、`--convergence-eps 1.00e-06`。
- 输出：模仿输入格式并追加 `localIDR`、`globalIDR`、各重复的 start/end/signal/summit；
  score 列为 IDR 缩放值（原文 `min(int(log2(-125*IDR), 1000)`，例：IDR 0 → 1000、0.05 → 540、1.0 → 0）。
- 峰匹配规则：无 `--peak-list` 时按 overlap 分组后 merge，未在所有重复中出现的峰默认丢弃（除非 `--use-nonoverlapping-peaks`）；
  有 `--peak-list` 时按 summit 距离 > overlap 大小 > 峰分数 依次破平。
- 关键前提：ranked list **不得预先阈值化**。

## 1.8 ENCODE MACS2 for ATAC（#13）

```
macs2 callpeak -t {ta} -f BED -n {prefix} -g {gensz} -p {pval_thresh} --shift {shiftsize} --extsize {extsize} --nomodel -B --SPMR --keep-dup all --call-summits
```
- 默认：`--pval-thresh 0.01`、`--smooth-win 150`、`--cap-num-peak 300000`、`--mem-gb 4.0`。
- `shiftsize = -int(round(float(smooth_win)/2.0))`（win=150 → -75）；`extsize = smooth_win`（150）。
- 后处理：按第 8 列排序 → 重命名 `Peak_N` → 负坐标归零 → 截断到 cap → clip 到染色体边界。
- 输入是 TAGALIGN（`ta`），因此 `-f BED` 而非 `BAMPE`——与「BAMPE 不能设非 0 shift」互洽。

## 1.9 ENCODE IDR（#14）

```
idr --samples {peak1} {peak2} --peak-list {peak_pooled} --input-file-type narrowPeak --output-file {idr_out} --rank {rank} --soft-idr-threshold {thresh} --plot --use-best-multisummit-IDR --log-output-file {idr_stdout}
```
- 默认 `--idr-thresh 0.1`、`--idr-rank p.value`；`--peak-type` 必填，取 `narrowPeak|regionPeak|broadPeak|gappedPeak`（描述注明「NarrowPeak or RegionPeak only」）。
- 之后按 `$12 >= -log10(thresh)` 过滤 12 列输出；再 blacklist filter → bigBed/starch/hammock → FRiP。
- 报错语义：`No IDR peaks found. IDR threshold might be too stringent or replicates have very poor concordance.`

## 1.10 HOMER `findMotifsGenome.pl`（#16）

- Usage：`findMotifsGenome.pl <peak/BED file> <genome> <output directory> -size # [options]`
- 示例：`findMotifsGenome.pl ERpeaks.txt hg18 ER_MotifOutput/ -size 200 -mask`
- `-size` 必填；默认 200；支持 `-size given`、`-size -100,50`。
- 建议区域：TF 主 motif 50 bp；TF 主+共富集 200 bp；histone mark 500–1000 bp。
- 默认背景：`50000 or 2x the total number of peaks, which ever is larger`，GC 5% 分箱匹配；`-N <#>` 可改。
- 自定义背景 `-bg`：自动剔除与 target 重叠者（mergePeaks），仍做 GC 归一化；背景少于 target 时建议 `-h`（超几何）。
- 归一化：`-nlen` 默认 3（`-nlen 0` 关闭）；`-olen` 默认 0（关闭）。
- 默认 `-len 8,10,12`、`-S 25`、`-mis 2`、`-p 1`。
- 输入：HOMER peak 文件 ≥5 列，BED ≥6 列（第 4 列为唯一 ID，第 6 列为 strand）。
- `-dumpFasta` 输出 `target.fa` / `background.fa`，官方明确「You can then use them with MEME」。
- 输出：`homerResults.html`、`knownResults.html`、`knownResults.txt`、`homerMotifs.all.motifs`、`motifFindingParameters.txt`。
- 官方判断：TF ChIP 应看到强富集（`<< 1e-50`），否则实验可能失败。
- 局限：默认不返回 motif 位置；要看位置用 `-find <motif file>` 或 `annotatePeaks.pl -m`。

## 1.11 MEME-ChIP（#17）

- Usage：`meme-chip [options] <primary sequence file>`
- 输入偏好：等长、100–500 bp、中心富集；建议 repeat mask 为 `N`。
- 背景：`-neg <file>`（Differential Enrichment 目标函数）；`-order` 默认 2 阶 Markov；`-bfile` 直接给模型。
- 已知 motif：`-db <motif file>`（recommended）。
- 其它默认：`-filter-thresh 0.05`、`-minw 6`/`-maxw 15`、`-meme-nmotifs 3`、`-ccut 100`、
  `-group-thresh 0.05`、`-streme-pvt 0.05`、`-centrimo-ethresh 10`、`-centrimo-score 5`、`-meme-brief 1000`。
- 输出目录默认 `memechip_out`：`meme-chip.html`、`summary.tsv`、`combined.meme`。

## 1.12 computeMatrix / plotProfile（#18, #19）

- `computeMatrix reference-point -S <bigwig file(s)> -R <bed file(s)> -b 1000`
- `computeMatrix scale-regions -S <biwig file(s)> -R <bed file> -b 1000`
- 必需：`-S/--scoreFileName`（大文件为 `bamCoverage`/`bamCompare` 产物）、`-R/--regionsFileName`、`-o/--outFileName`。
- 默认：`reference-point` 的 `-b` 500、`-a` 1500、`--referencePoint TSS`；`scale-regions` 的 `-m` 1000、`-b/-a` 0；`-bs` 10；
  `--sortRegions keep`、`--sortUsing mean`、`--averageTypeBins mean`、`-p 1`。
- 过滤/排序：`--skipZeros`、`--minThreshold`、`--maxThreshold`、`--blackListFileName`。
- `plotProfile -m matrix.gz -out x.png`；`--outFileNameData` 导出 profile 数值；`--plotType {lines,fill,se,std,overlapped_lines,heatmap}`；`--perGroup` 按 region 分组。
- 版本提醒：3.0 起矩阵带样本标签，旧版 plotHeatmap 不能读新矩阵。

## 1.13 bamCoverage（#20）

- Usage：`bamCoverage -b reads.bam -o coverage.bw`
- `--normalizeUsing {RPKM,CPM,BPM,RPGC,None}`，默认 `None`；`RPGC` 必须给 `--effectiveGenomeSize`。
- `--binSize` 默认 50；`-p` 默认 1；`--extendReads` 默认关闭（ChIP 类建议开启）。
- `--blackListFileName` 按「重叠 chunk 整体拒绝」实现。
- ATAC 片段过滤：`--minFragmentLength` / `--maxFragmentLength` 默认 0。
- ChIP 官方示例：`bamCoverage --bam a.bam -o a.SeqDepthNorm.bw --binSize 10 --normalizeUsing RPGC --effectiveGenomeSize 2150570000 --ignoreForNormalization chrX --extendReads`
- 警示：已用 `correctGCbias` 时不得再设 `--ignoreDuplicates`。

## 1.14 samtools markdup（#21）

- 前提：需先 `samtools fixmate -m`（依赖 MC 与 ms tag）；输入必须 coordinate sorted。
- 链路：`collate -o` → `fixmate -m` → `sort -o` → `markdup`。
- 默认：`-l` 300；`-d` 0（不找光学重复，HiSeq 100 / NovaSeq 约 2500）；`--mode t`；
  `--no-multi-dup`、`--include-fails`、`--use-read-groups`、`--barcode-tag`、`--read-coords` 等为可选。
- `-s` 打印统计（READ/WRITTEN/EXCLUDED/EXAMINED/PAIRED/SINGLE/DUPLICATE …/ESTIMATED LIBRARY SIZE）。
- 排除对象：secondary、supplementary、unmapped，默认还包括 QC failed。

## 1.15 Picard MarkDuplicates（#23）

- Usage：`java -jar picard.jar MarkDuplicates I=input.bam O=marked_duplicates.bam M=marked_dup_metrics.txt`
- 输入 `Must be coordinate sorted`；重复标记 flag 为 `0x0400`（1024）。
- 默认：`REMOVE_DUPLICATES false`、`REMOVE_SEQUENCING_DUPLICATES false`、`TAGGING_POLICY DontTag`、
  `OPTICAL_DUPLICATE_PIXEL_DISTANCE 100`（patterned flowcell 2500）、`MAX_FILE_HANDLES_FOR_READ_ENDS_MAP 8000`、
  `DUPLICATE_SCORING_STRATEGY SUM_OF_BASE_QUALITIES`、`CLEAR_DT true`。
- 选原始 read 的依据是碱基质量和（非序列一致）。
- 输出 DT tag 可选（LB/SQ）；`READ_NAME_REGEX=null` 可关闭光学重复检测（但文库规模估计会不准）。

## 1.16 Bowtie 2（#24）

- Usage：`bowtie2 [options]* -x <bt2-idx> {-1 <m1> -2 <m2> | -U <r> | --interleaved <i> | --sra-acc <acc> | -b <bam>} -S [<sam>]`
- 预设（end-to-end）：`--very-fast`= `-D 5 -R 1 -N 0 -L 22 -i S,0,2.50`；`--fast`；`--sensitive`= `-D 15 -R 2 -N 0 -L 22 -i S,1,1.15`（默认）；`--very-sensitive`= `-D 20 -R 3 -N 0 -L 20 -i S,1,0.50`。
- local 预设：`--very-fast-local` / `--fast-local` / `--sensitive-local` / `--very-sensitive-local`。
- `-p/--threads` 控制线程；`--no-discordant` 关闭不一致配对搜索（默认同时搜 concordant 与 discordant）。
- 默认 `-X/--maxins 500`、`-I/--minins 0`、`--fr`。

## 1.17 BWA（#25）

- `bwa index ref.fa`；`bwa mem ref.fa read1.fq read2.fq > aln-pe.sam`；单端 `bwa mem ref.fa reads.fq > aln-se.sam`。
- `-t INT` 线程（默认 1）；`-R STR` 完整 read group 行（如 `'@RG\tID:foo\tSM:bar'`）；`-T INT` 输出分数下限（默认 30）。
- `-M`：把较短的 split hit 标为 secondary，`for Picard compatibility`。
- BWA-MEM 本地比对可能产生 split alignment，`some tools such as Picard's markDuplicates does not work with split alignments`。

## 1.18 ChIPseeker（#26, #27, #28）

- 加载：`readPeakFile()`；`getPromoters(TxDb=txdb, upstream=3000, downstream=3000)` + `getTagMatrix()` + `plotAvgProf()` / `tagHeatmap()`。
- 注释：`annotatePeak(files[[4]], tssRegion=c(-3000, 3000), TxDb=txdb, annoDb="org.Hs.eg.db")`；
  TSS 默认 −3kb/+3kb；输出 `csAnno`，可用 `as.GRanges` / `as.data.frame`。
- 注释优先级：Promoter > 5' UTR > 3' UTR > Exon > Intron > Downstream > Intergenic（可用 `genomicAnnotationPriority` 改）。
- 可视化：`plotAnnoPie`、`plotAnnoBar`、`vennpie`、`upsetplot`、`plotDistToTSS`。
- 多对多映射：`seq2gene(peak, tssRegion = c(-1000, 1000), flankDistance = 3000, TxDb=txdb)`。
- 重叠显著性：`enrichPeakOverlap(queryPeak=..., targetPeak=..., TxDb=txdb, pAdjustMethod="BH", nShuffle=50, chainFile=NULL, mc.cores=1, verbose=FALSE)`
  （官方提示实际用 `nShuffle` ≥1000）。
- 安装：`BiocManager::install("ChIPseeker")`。

## 2 抓取失败或不可用的地址

| URL | 状态 | 处理 |
| --- | --- | --- |
| https://macs2.readthedocs.io/en/latest/usage.html | 404（Read the Docs: Project not found） | 不引用 MACS2 独立文档；MACS2 选项以 MACS3 官方文档 + 本机 `--help` 为准 |
| https://github.com/FansenC/SEACR（及 raw README） | fetch failed / 仓库 404 | 改用当前官方仓库 https://github.com/FredHutch/SEACR |
| https://github.com/nf-core/chipseq/blob/master/docs/usage.md | 未抓取（本轮未读取） | 正文不引用 nf-core/chipseq 参数，仅引用已读取的 nf-core/atacseq 文档 |
| https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/docs/tutorial.md | 404 | 改用 `src/encode_task_macs2_atac.py` 与 `src/encode_task_idr.py` 源码作为官方依据 |
| https://www.encodeproject.org/annotations/ENCSR636HFF/ 的文件下载区 | 页面可达但「No files to display」 | 黑名单文件下载命令改引 nf-core/atacseq usage 文档（其中给的是 ENCODE file accession 直链） |
| https://bioconductor.org/packages/release/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html | 多次超时 | 改用 3.21 版本路径与 GitHub vignette 源码（同源同内容） |

## 3 官方文档缺失清单（只写流程与判据，不自造脚本）

1. **CUT&Tag 专属 caller 文档缺失**：SEACR 官方只覆盖 CUT&RUN 语义的稀疏数据；CUT&Tag 的 spike-in 归一化因子计算没有任何官方命令，
   只能写流程：先算 spike-in 比对比例 → 决定是否需要 scale → 再决定 SEACR 的 `norm`/`non`。
2. **ATAC fragment size 直方图**：官方给判据（NFR 必须存在；mononucleosome peak 147–294 bp 必须存在）与
   `bamCoverage --minFragmentLength/--maxFragmentLength`，但未给绘制直方图的命令。
3. **TSS enrichment 数值口径**：ENCODE 给阈值表与脚本 `src/encode_task_tss_enrich.py`，抓取文档未给单行命令；
   deepTools 只能出 profile 图（`computeMatrix` + `plotProfile`），不等于 ENCODE 的 TSS enrichment score。
4. **MACS3 bedGraph → bigWig**：`callpeak` 文档只说 `can be imported to the UCSC genome browser or be converted into even smaller bigWig files`，
   未给 `bedGraphToBigWig` 形式的命令。可执行路径是用 `bamCoverage` 直接从 BAM 出 bigWig。
5. **FRiP 逐样本计算命令**：ENCODE 仅有 `src/encode_lib_frip.py`；抓取文档未给命令行。可写口径（对有 peak 的 read 计数 / 总 mapped read），
   不自造脚本。
6. **MACS3 示例命名不一致**：示例 4 写 `--extension 100`，选项章节只文档化 `--extsize`；以本机 `macs3 callpeak -h` 为准。
7. **SEACR 无 `--control/--norm/--non` 开关**：官方接口是 5 个位置参数，误用长选项会直接报参数错误。
8. **MEME-ChIP 不接受基因组坐标**：需先取 FASTA；官方给出的桥接是 HOMER `-dumpFasta`（输出 `target.fa`/`background.fa`）。
9. **peak 与表达的统计关联模型**：官方文档只到「consensus peak 计数矩阵 + DESeq2」与「seq2gene 映射 + 富集」，
   没有把 peak 丰度与 RNA 表达做联合建模的官方命令。
