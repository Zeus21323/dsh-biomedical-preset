# 参数与默认值（按数据类分列）

所有默认值逐字取自官方文档；「官方未提供」= 该参数在官方文档中不存在或未给默认值。

---

## A. 上游比对 / 预处理（三类数据共用）

### A1. STAR（MeRIP / RIP 主用）

来源：https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `--outSAMtype` | `SAM` | `BAM Unsorted` / `BAM SortedByCoordinate` / `BAM Unsorted SortedByCoordinate` |
| `--outSAMattributes` | `Standard`（= `NH HI AS nM`） | 预设：`None` / `Standard`（NH HI AS nM）/ `All`（NH HI AS nM NM MD jM jI MC ch）；可任意组合排序 |
| `--outFilterMultimapNmax` | `10` | 超过该位点数则不输出任何比对，计入 "mapped to too many loci" |
| `--outFilterMismatchNmax` | `10` | 错配数上限（超限不输出） |
| `--outFilterMismatchNoverLmax` | `0.3` | 错配/比对长度比上限 |
| `--outFilterMismatchNoverReadLmax` | `1.0` | 错配/读长比上限 |
| `--winAnchorMultimapNmax` | `50` | anchor 最大位点数；官方要求 ≥ `--outFilterMultimapNmax` |
| `--alignSJoverhangMin` | `5` | 未注释剪接的最小 overhang |
| `--alignEndsType` | `Local` | reads 末端比对类型 |
| `--quantMode` | `-` | `GeneCounts` 输出 `ReadsPerGene.out.tab`；`TranscriptomeSAM` 输出转录本坐标 BAM |
| `--outReadsUnmapped` | `None` | `Fastx` 输出未比对 reads（eCLIP 重复序列过滤步骤用） |
| `--outMultimapperOrder` | `Old 2.4` | 多重比对输出顺序 |
| `--outSAMprimaryFlag` | `OneBestScore` | 可选 `AllBestScore` |

建索引：`--runMode genomeGenerate` + `--sjdbGTFfile` + `--sjdbOverhang`（手册示例值 100）。

### A2. bowtie2（CLIP 短读/软剪切）

来源：https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml

| 参数 | 默认 | 官方说明 |
|---|---|---|
| 比对模式 | `--end-to-end` | 与 `--local` 互斥 |
| `--local` | 关闭 | 允许两端 soft clip 以最大化比对得分 |
| `--sensitive-local` | local 模式下的默认预设 | `-D 15 -R 2 -N 0 -L 20 -i S,1,0.75` |
| `--score-min` | `L,-0.6,-0.6`（end-to-end）/ `G,20,8`（local） | 最小比对得分函数 |
| `-N` | `0` | seed 允许错配数（0 或 1） |
| `-L` | 由预设决定（end-to-end 22 / local 20） | seed 子串长度 |
| `-X/--maxins` | `500` | 有效双端片段长度上限 |
| `--ma` | `2` | local 模式的匹配加分 |
| `--mp` | `MX=6, MN=2` | 错配罚分上限/下限 |
| `-p/--threads` | 未在手册默认表中给出 | 并行线程数 |

### A3. 去重（umi_tools dedup）

来源：https://umi-tools.readthedocs.io/en/latest/reference/dedup.html

| 参数 | 默认 | 官方说明 |
|---|---|---|
| 用法 | — | `umi_tools dedup --stdin=INFILE --log=LOGFILE > OUTFILE` |
| `--method` | `directional` | 其他：`unique` / `percentile` / `cluster` / `adjacency` |
| `--edit-distance-threshold` | `1` | UMI 连接编辑距离阈值（UMI >14 bp 时才考虑加大） |
| `--multimapping-detection-method` | 未指定（改用最高 MAPQ） | `NH` / `X0` / `XT` |
| `--soft-clip-threshold` | `4` | 3' 端 soft clip ≥ 该值视为剪接 |
| `--mapping-quality` | `0` | 保留的最小 MAPQ |
| `--paired` | 关闭 | 双端输出 |
| `--unmapped-reads` | `discard` | `use` / `output` |
| `--unpaired-reads` | `use` | `discard` / `output` |
| `--chimeric-pairs` | `use` | `discard` / `output` |
| `--in-format` / `--out-format` | `bam` | 可覆盖以处理 CRAM |

### A4. 链特异性判定（RSeQC）

来源：https://rseqc.sourceforge.net/

| 参数 | 默认 | 官方说明 |
|---|---|---|
| 用法 | — | `infer_experiment.py -r <refgene.bed> -i <in.bam>` |
| `-r/--refgene` | 必填 | BED 格式基因模型（12 列） |
| `-s/--sample-size` | `200000` | 采样 reads 数 |
| `-q/--mapq` | `30` | 判定「唯一比对」的最小 MAPQ |

### A5. rRNA 过滤（SortMeRNA）

来源：https://github.com/sortmerna/sortmerna

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `--ref` | 必填 | 参考库；多库可重复该选项 |
| `--reads` | 必填 | 输入 reads；双端可重复该选项 |
| 文件格式 | 自动识别 | fasta/fastq 及其 `.gz`，扩展名可省略 |

### A6. 区间统计 / FRiP（bedtools intersect）

来源：https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html

| 参数 | 默认 | 官方说明 |
|---|---|---|
| 用法 | — | `bedtools intersect [OPTIONS] -a <FILE> -b <FILE1, ...>` |
| `-u` | 关闭 | 只要 A 与 B 有重叠就输出 A 一次 |
| `-v` | 关闭 | 只输出与 B 无重叠的 A |
| `-c` | 关闭 | 每个 A 输出命中 B 的个数（含 0） |
| `-abam` | 关闭 | BAM 作为 A（2.19.0 起可自动识别，无需显式指定） |
| `-bed` | 关闭 | BAM 输入时以 BED 输出 |
| `-split` | 关闭 | 按 CIGAR N / BED12 block 拆分 |
| `-f` / `-F` | `1E-9`（1 bp） | A / B 侧最小重叠比例 |
| `-s` / `-S` | 关闭 | 要求同链 / 反链 |
| `-sorted` | 关闭 | 大文件低内存算法（要求按坐标排序） |

---

## B. MeRIP-seq / m6A（exomePeak2）

来源（签名与默认值）：https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R
来源（流程与输出列）：https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `bam_ip` | `NULL` | IP 样本 BAM 路径向量（必填） |
| `bam_input` | `NULL` | input 样本 BAM 路径向量（必填） |
| `bam_ip_treated` | `NULL` | 干预组 IP（给出即进入差异甲基化模式） |
| `bam_input_treated` | `NULL` | 干预组 input |
| `txdb` | `NULL` | TxDb 注释；与 `gff`、`genome` 至少给一个 |
| `gff` | `NULL` | GFF/GTF 路径（`txdb` 缺失时用 `makeTxDbFromGFF`） |
| `genome` | `NULL` | UCSC 基因组名（如 `"hg19"`，由 `getBSgenome` 取）；为 `NULL` 时不做 GC 偏倚校正 |
| `strandness` | `"unstrand"` | `unstrand` / `1st_strand`（dUTP、NSR、NNSR）/ `2nd_strand`（Ligation、SOLiD） |
| `fragment_length` | `100` | 期望片段长度（bp） |
| `bin_size` | `25` | 滑窗宽度 |
| `step_size` | `25` | 滑窗步长 |
| `test_method` | `"Poisson"` | `Poisson`（Wald 检验）/ `DESeq2`（负二项 + 正则化离散度；官方建议此时 `p_cutoff` 放宽到如 0.001） |
| `p_cutoff` | `1e-10` | peak calling p 值阈值 |
| `diff_p_cutoff` | `0.01` | 差异分析 p 值阈值 |
| `parallel` | `1` | 并行核数 |
| `plot_gc` | `TRUE` | 输出 bins GC 含量 vs 拟合覆盖度诊断图 |
| `save_output` | `TRUE` | 落盘 BED/CSV/RDS |
| `save_dir` | `getwd()` | 输出根目录 |
| `experiment_name` | `"exomePeak2_output"` | 子目录名 |
| `mode` | `"exon"` | `exon` / `full_transcript` / `whole_genome`（后两者大基因组 >4 GB 内存） |
| `motif_based` | `FALSE` | `TRUE` 时用 motif 位点替代滑窗 |
| `motif_sequence` | `"DRACH"` | 仅 `motif_based = TRUE` 时生效 |
| `absolute_diff` | `FALSE` | `TRUE` 时差异检验改为直接比较 IP 组间变化（不做 input 归一） |
| `confounding_factor` | `NULL` | factor 向量或 data.frame，作为 GLM 协变量 |

### B1. peak 输出列（官方定义）

`chr` / `chromStart` / `chromEnd` / `name` / `strand` / `blockCount` / `blockSizes` / `blockStarts` / `geneID` / `RPM.input` / `RPM.IP` / `log2FC` / `pvalue` / `fdr` / `score`

其中 `score` = -log10(p)；`log2FC` = IP 相对 input 的 β₁ 估计；差异模式下 `diff.log2FC` = log(处理组 IP/input FC ÷ 对照组 IP/input FC)。

### B2. motif 富集（HOMER）

来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `-size` | `200`（**必填**） | `-size given` 用输入区间原长；`-size -100,50` 取中心偏移窗口 |
| `-len` | `8,10,12` | motif 长度，多值逗号分隔 |
| `-rna` | 关闭 | 只搜正链、输出 RNA logo（U 代 T），自动 `-norevopp`；官方注明 RNA motif 库目前只有 miRNA |
| `-p` | `1` | CPU 数 |
| `-bg` | 自动选取 | 自定义背景区间（自动剔除与 target 重叠部分） |
| `-N` | `max(50k, 2× 输入数)` | 背景序列数 |
| `-nlen` | `3` | 低级寡核苷酸归一化长度（`0` 关闭） |
| `-mask` | 关闭 | 用重复序列屏蔽后的基因组 |
| `-find <motif file>` | — | 只扫描给定 motif 位点，输出到 stdout |
| `-nomotif` / `-noknown` | 关闭 | 跳过 de novo / 已知 motif 富集 |

官方**没有** RRACH 这种简并序列的直接富集命令：`-find` 需要 HOMER 格式 motif 文件；要指定简并 motif 走 exomePeak2 的 `motif_sequence` 传参。

---

## C. RIP-seq（MACS3 `callpeak`，通用 caller）

来源：https://macs3-project.github.io/MACS/docs/callpeak.html

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `-t/--treatment` | 必填 | 可多个文件池化 `-t A B C` |
| `-c/--control` | 无 | "genomic input or mock IP data"；RIP 必须给 |
| `-f/--format` | `AUTO` | `BAM` / `SAM` / `BED` / `BAMPE` / `BEDPE` / `FRAG` / `ELAND` 等；`BAMPE`/`BEDPE`/`FRAG` 无法自动识别 |
| `-g/--gsize` | 无（官方示例用 `hs`） | `hs` 2,913,022,398（GRCh38）/ `mm` 2,652,783,500（GRCm38）/ `ce` 100,286,401 / `dm` 142,573,017 |
| `-n/--name` | 无 | 输出文件前缀 |
| `-q/--qvalue` | `0.05` | q 值阈值（BH 校正 p 值） |
| `-p/--pvalue` | 无 | 指定后改用 p 值 |
| `--keep-dup` | `1` | `auto`（二项分布，p=1e-5）/ `all` / 整数；`FRAG` 格式下忽略 |
| `--buffer-size` | `100000` | 读入缓冲 |
| `--nomodel` | 关闭 | 跳过建模，需配 `--extsize`/`--shift` |
| `--extsize` | 无 | `--nomodel` 时的固定片段延伸长度 |
| `--shift` | `0` | 读段位置整体平移（`BAMPE`/`BEDPE` 下必须为 0） |
| `--slocal` / `--llocal` | `1000` / `10000` | 局部 lambda 的小/大窗口 |
| `--nolambda` | 关闭 | 用全局背景 lambda（无对照时官方推荐） |
| `--min-length` / `--max-gap` | 预测片段大小 / 检测到的读长 | 峰最小长度 / 合并间隔 |
| `--broad` | 关闭 | 宽峰模式（gappedPeak 输出） |
| `--broad-cutoff` | `0.1` | 宽峰阈值（`-p` 时按 p 值解释） |
| `--call-summits` | 关闭 | 在峰内再找子峰（子峰需 ≥50 bp 非负信号支撑） |
| `-B/--bdg` | 关闭 | 输出 `NAME_treat_pileup.bdg` / `NAME_control_lambda.bdg` |
| `--cutoff-analysis` | 关闭 | 输出 `NAME_cutoff_analysis.txt`（pscore/qscore/npeaks/lpeaks/avelpeak） |
| `--threads` | 官方只写可设 CPU 预算 | 3.1.0 起提供；`--threads 1` 为串行 |

### C1. 输出（官方）

`NAME_peaks.xls`（1-based，含峰长/峰顶 pileup/-log10(p)/fold enrichment/-log10(q)）、
`NAME_peaks.narrowPeak`（BED6+4，第 5 列 = `int(-10*log10 p or q)`，第 10 列 = 相对峰顶位置）、
`NAME_summits.bed`、`--broad` 时的 `NAME_peaks.broadPeak`（BED6+3）与 `NAME_peaks.gappedPeak`（BED12+3）、
`NAME_model.r`（`Rscript NAME_model.r` 生成 `NAME_model.pdf`）。

---

## D. CLIP-seq / eCLIP（CLIPper）

来源（README）：https://github.com/YeoLab/CLIPper
来源（全部选项与默认值）：https://github.com/YeoLab/clipper/blob/master/clipper/src/main.py
来源（官方流程调用与资源）：https://github.com/YeoLab/eclip/blob/master/cwl/clipper.cwl

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `--bam`/`-b` | 必填 | 需已建索引（源码 `check_for_index`） |
| `--species`/`-s` | 必填 | README：`hg19` 或 `mm9`；CWL 列出 `ce10 ce11 dm3 hg19 GRCh38 mm9 mm10 GRCh38_pU6 GRCh38_v29 GRCh38_v29e hg19_VSV` |
| `--outfile`/`-o` | `fitted_clusters` | 输出 BED；eCLIP 流程默认 `<bam>.peakClusters.bed` |
| `--gene`/`-g` | 无 | 指定基因（`action="append"`） |
| `--minreads` | `3` | 开始拟合所需最小 reads |
| `--poisson-cutoff` | `0.05` | Poisson 检验 p 值阈值 |
| `--FDR` | `0.05` | 峰高估计 FDR |
| `--binomial` | `0.05` | 二项分布定阈值的显著性 |
| `--threshold` | 无 | 跳过 FDR，直接给阈值 |
| `--disable_global_cutoff` | 全局 cutoff 默认**开启** | 关闭转录组水平 cutoff |
| `--maxgenes` | 无 | 只跑前 N 个基因（测试用） |
| `--processors` | `autodetect` | "Number of processors to use. Default: All processors on machine"（**没有 `--threads`**） |
| `--plot`/`-p` | off | 输出拟合图；会强制 `--debug`（串行） |
| `--verbose`/`-v`、`--quiet`/`-q` | off | 源码标注 TODO unused |
| `--save-pickle` | off | 保存中间对象 |
| `--debug` | off | 关闭多进程以获得正确 traceback |
| `--max_gap` | `15` | 判定新 section 的最大 read 间隔 |
| `--timeout` | 无 | 单基因超时（秒） |
| `--datadir` | 包内 `data_dir()` | 存放 `*AS.STRUCTURE.gff` 与 `regions/*.bed` |

### D1. 源码中硬编码（`override_options()`）

`premRNA=True`、`gtfFile=None`、`method="binomial"`、`SloP=True`（super-local p 值，1 kb 窗口）、
`bonferroni_correct=True`、`algorithm="spline"`、`reverse_strand=False`、`max_width=75`、`min_width=50`。
这些在命令行上不可调（对应选项已被注释掉）。

### D2. 官方流程资源与输出

`coresMin: 8`、`ramMin: 32000`（人数据）；输出 `*.peakClusters.bed` → `bed_to_narrowpeak.cwl` 转 narrowPeak → `blacklist-remove.cwl` 去 ENCODE 黑名单。
narrowPeak 第 5 列：`1000` = 显著，`200` = 不显著（官方 README FAQ）。

---

## E. 下游注释（ChIPseeker）

来源：https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/vignettes/ChIPseeker.Rmd

| 参数 | 默认 | 官方说明 |
|---|---|---|
| `readPeakFile(file)` | — | 读 BED/GFF 为 GRanges |
| `annotatePeak(peak, tssRegion, TxDb, annoDb)` | `tssRegion` 默认 -3kb~+3kb | `annoDb` 可选，给则追加 SYMBOL/GENENAME/ENSEMBL/ENTREZID |
| `genomicAnnotationPriority` | Promoter > 5'UTR > 3'UTR > Exon > Intron > Downstream > Intergenic | 可自定义优先级 |
| `getTagMatrix(..., upstream, downstream, type, by, nbin)` | `nbin` 无默认（binning 时需给，如 800） | `type` = `start_site` / `end_site` / `body`；`by` = `gene` / `transcript` / `exon` / `intron` / `5UTR` / `3UTR` |
| `plotAvgProf(tagMatrix, xlim, conf, resample)` | `conf`/`resample` 需显式给（官方示例 0.95 / 1000） | 平均 profile |
| `enrichPeakOverlap(..., nShuffle)` | 官方示例给 50（并建议 ≥1000） | peak 重叠显著性 |
