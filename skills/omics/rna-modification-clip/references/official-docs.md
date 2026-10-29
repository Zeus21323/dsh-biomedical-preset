# 官方文档清单（本次实际抓取，2026-10-29）

原则：SKILL.md 中的每条命令、参数名、默认值都对应下表某个 URL。抓取失败的页面也如实记录，
并说明因此缺了哪部分内容（对应 SKILL.md 中的「官方文档未提供可直接执行的命令」）。

## 1. MeRIP-seq / m6A

| URL | 抓取状态 | 支撑内容 |
|---|---|---|
| https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd | 200（全文） | exomePeak2 vignette 全文：安装、`exomePeak2()` peak calling 示例、差异甲基化示例、Poisson GLM 公式、peak 输出 15 列定义、`exomePeak2_output` 目录行为 |
| https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R | 200（raw 正文） | `exomePeak2()` 完整函数签名与全部默认值：`strandness="unstrand"`、`fragment_length=100`、`bin_size=25`、`step_size=25`、`test_method="Poisson"`、`p_cutoff=1e-10`、`diff_p_cutoff=0.01`、`mode="exon"`、`motif_based=FALSE`、`motif_sequence="DRACH"`、`parallel=1`、`plot_gc=TRUE`、`experiment_name="exomePeak2_output"` |
| https://bioconductor.org/packages/release/bioc/vignettes/exomePeak2/inst/doc/exomePeak2.html | **404** | 任务给出的候选 URL 已失效；改用上方 uib.no 3.19 镜像的 vignette 源文件（同一文档） |
| https://bioconductor.org/packages/release/bioc/html/exomePeak2.html | 超时 | 未取到；不影响内容，因 vignette 与源码已覆盖 |

说明：exomePeak2 官方文档中**没有** `--library-type` 参数（该写法属于 Cufflinks/TopHat 一类工具）；
exomePeak2 的链参数是 `strandness`，取值 `unstrand` / `1st_strand` / `2nd_strand`。这一点已在 SKILL.md 3.6 明示。

## 2. RIP-seq（通用 peak caller）

| URL | 抓取状态 | 支撑内容 |
|---|---|---|
| https://macs3-project.github.io/MACS/docs/callpeak.html | 200（全文） | `macs3 callpeak` 官方示例（含 `-t/-c/-f/-g/-n/-B/-q`）、`-q` 默认 0.05、`-g hs`=2,913,022,398、`--keep-dup` 默认 1、`--nomodel/--extsize`、`--broad/--broad-cutoff` 0.1、`--threads`、输出文件（xls/narrowPeak/summits.bed/bdg）与列定义 |
| https://github.com/macs3-project/MACS | 200（README） | MACS 官方定位："as a general peak-caller, MACS can also be applied to any 'DNA enrichment assays'"——用于说明 RIP-seq 无专用 caller、以通用 caller 替代的正当性 |

## 3. CLIP-seq / eCLIP

| URL | 抓取状态 | 支撑内容 |
|---|---|---|
| https://github.com/YeoLab/CLIPper | 200（README 全文） | 安装（`conda env create -f environment3.yml`、`pip install .`）、最小命令 `clipper -b ... -o ... -s hg19`、`-s` 官方说明 "either hg19 or mm9"、input 归一化在另一仓库 `merge_peaks` |
| https://github.com/YeoLab/clipper/blob/master/clipper/src/main.py | 200（raw 全文） | 全部命令行选项与默认值（`--minreads 3`、`--poisson-cutoff 0.05`、`--FDR 0.05`、`--binomial 0.05`、`--max_gap 15`、`--processors autodetect`、`--plot`、`--save-pickle`、`--timeout`、`--datadir`）以及被硬编码的 `override_options()`；确认**没有** `--threads` |
| https://github.com/YeoLab/eclip/blob/master/cwl/clipper.cwl | 200 | 官方流程中的 CLIPper 调用：`coresMin: 8`、`ramMin: 32000`、默认输出 `<bam>.peakClusters.bed`、`--species` 支持物种列表、`doc` 中的调用示例 |
| https://github.com/YeoLab/eclip | 200（README 全文） | eCLIP 官方 7 步流程（demux → cutadapt → STAR 比重复序列 → STAR 比基因组 → umi_tools/barcodecollapsepe.py 去重 → CLIPper 出 peak → size-matched input 归一）、输出文件命名、narrowPeak 第 5 列 200/1000 的解释、ENCODE 黑名单 `ENCFF039QTN` |
| https://github.com/YeoLab/eclip/blob/master/cwl/ | 200（目录） | `bed_to_narrowpeak.cwl`、`blacklist-remove.cwl`、`overlap_peakfi_with_bam_PE.cwl`、`peakscompress.cwl` 等官方步骤文件的存在性 |
| https://api.github.com/repos/YeoLab/PARalyzer | **404 不存在** | PARalyzer 无 YeoLab 官方仓库；GitHub 搜索 `PARalyzer in:name` 亦无该生物信息学工具仓库。故 SKILL.md 不写 PARalyzer 命令，仅记录"官方文档未能查到" |
| CTK | 未查证到可引用页面 | 同上，不写命令 |

## 4. 上游比对

| URL | 抓取状态 | 支撑内容 |
|---|---|---|
| https://raw.githubusercontent.com/alexdobin/STAR/master/doc/STARmanual.pdf | 200（PDF，239 KB，已本地抽取文本 63 页） | `--outSAMattributes` 默认 `Standard`（= `NH HI AS nM`，5.2.2 节原文 "By default, STAR outputs NH HI AS nM attributes."）、`--outSAMtype` 默认 `SAM`、`--outFilterMultimapNmax 10`、`--outFilterMismatchNmax 10`、`--winAnchorMultimapNmax 50`、`--alignSJoverhangMin 5`、`--alignEndsType Local`、`--quantMode GeneCounts` 输出 `ReadsPerGene.out.tab`、`--outReadsUnmapped Fastx` |
| https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf | 200（引用入口） | 上面 PDF 的 GitHub 页面地址；注意以 `application/octet-stream` 返回，浏览器/抓取器可能无法直接解析，需下载后抽取文本 |
| https://raw.githubusercontent.com/alexdobin/STAR/master/README.md | 200 | 仅编译与硬件要求；**不含**参数细节，参数细节一律以手册 PDF 为准 |
| https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml | 200（长文，已截取关键段） | `--local` 定义原文、`--end-to-end` 为默认、`--sensitive-local`=`-D 15 -R 2 -N 0 -L 20 -i S,1,0.75`、local 模式 `--score-min` 默认 `G,20,8`、`-p/--threads`、`-X/--maxins` 默认 500 |
| https://raw.githubusercontent.com/sortmerna/sortmerna/master/README.md | 200（全文） | rRNA 过滤官方用法：`sortmerna --ref REF_PATH --reads READS_PATH`，多库/双端重复 `--ref`/`--reads`；`--ref` 与 `--reads` 为唯一必填项 |
| https://sortmerna.readthedocs.io/en/latest/manual.html | **404** | Read the Docs 上该页不存在；改用上面的 GitHub README（同一官方来源） |
| https://umi-tools.readthedocs.io/en/latest/reference/dedup.html | 200（全文） | `umi_tools dedup --stdin=INFILE --log=LOGFILE > OUTFILE`、`--method` 默认 `directional`、`--multimapping-detection-method=NH/X0/XT`、`--paired`、`--soft-clip-threshold` 默认 4、`--edit-distance-threshold` 默认 1 |
| https://rseqc.sourceforge.net/ | 200（长文） | `infer_experiment.py -r <bed12> -i <bam>`（`-s` 默认 200000，`-q` 默认 30）及官方给出的链特异性判读示例；`read_duplication.py`；`GRCh38_rRNA.bed`/`hg19_rRNA.bed`/`mm10_rRNA.bed` 下载地址 |
| https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html | 200（全文） | `bedtools intersect` 全部选项：`-u`、`-v`、`-c`、`-abam`、`-bed`、`-split`、`-sorted`、`-f/-F/-r/-s`；用于 FRiP 与区间交集统计 |

## 5. 下游注释

| URL | 抓取状态 | 支撑内容 |
|---|---|---|
| https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/vignettes/ChIPseeker.Rmd | 200（全文） | `readPeakFile`、`annotatePeak(peak, tssRegion=c(-3000,3000), TxDb=txdb, annoDb="org.Hs.eg.db")`、`plotAnnoPie/plotAnnoBar/plotDistToTSS`、`peakAnnoList <- lapply(files, annotatePeak, ...)`、TxDb 包清单与 `makeTxDbFromUCSC`/`makeTxDbFromBiomart`、EnsDb + `seqlevelsStyle(edb) <- "UCSC"`、注释优先级（Promoter > 5'UTR > 3'UTR > Exon > Intron > Downstream > Intergenic）、`seq2gene` |
| https://bioconductor.uib.no/packages/3.19/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html | 200（渲染版，截断） | 与 Rmd 同源；渲染版可核对 `annotatePeak` 输出示例 |
| https://bioconductor.org/packages/release/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html | 超时 | 未取到；改用 uib.no 镜像 + 作者仓库 Rmd |
| http://homer.ucsd.edu/homer/ngs/peakMotifs.html | 200（全文） | `findMotifsGenome.pl <pos file> <genome> <output dir> -size #`、`-size` 必填与 `-size given`、`-rna`（并自动 `-norevopp`，官方自述 RNA motif 库只有 miRNA）、`-len` 默认 8,10,12、`-p` 默认 1、`-bg`、`-N`、`-nlen`、`-find <motif file>` 与 `annotatePeaks.pl -m` 输出列格式、输出文件清单（homerResults/knownResults/motifFindingParameters.txt 等） |

## 6. 明确「不存在 / 查不到」的候选

| 候选 | 结果 | 影响 |
|---|---|---|
| https://github.com/nf-core/m6a | **404**（`api.github.com/repos/nf-core/m6a` 亦 404） | 无 m6A 专用 nf-core 流程可引用；MeRIP 一律走 exomePeak2 官方 vignette |
| https://github.com/YeoLab/PARalyzer | **404** | 不写 PARalyzer 命令 |
| CTK | 未查证到官方页面 | 不写 CTK 命令 |
| exomePeak2 `--library-type` | 官方文档无此参数 | 链参数为 `strandness` |
| CLIPper `--threads` | 官方文档无此参数 | 并行度为 `--processors`（默认 `autodetect`） |
| FRiP 专用命令 | 三个工具官方文档均无 | 用 `bedtools intersect` 官方选项组合，并标注口径与判据 |
| m6A peak ↔ 差异表达/翻译效率关联 | 官方文档无 | 只写流程与判据，不写自造脚本 |
| peak ↔ 可变剪接事件关联 | 官方文档无 | 只写流程与判据，剪接工具命令需另行查证后再补 |

## 7. 复现说明

- STAR 手册为 PDF，本轮用本地 PDF 文本抽取（PyMuPDF）核对参数，抽取产物仅用于查证，未纳入 skill。
- 所有引用均为上游官方站点或官方代码仓库；第三方 skill/博客内容均未采信。
