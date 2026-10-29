# 参数对照表（默认值与说明逐字取自官方文档）

来源缩写见文末「来源索引」。凡官方未给默认值者标注「官方未给默认值」。

## A. `bismark prepare`（旧名 `bismark_genome_preparation`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `<path_to_genome_folder>` | 必填位置参数；`Expects one or more FastA files in the folder (valid file extensions: .fa or .fasta)` | B2 |
| `--path_to_aligner </../../>` | 指向 aligner **安装目录**（非可执行文件）；未给则假设在 `PATH` | B2 |
| `--bowtie2` | `Default: ON` | B2 |
| `--hisat2` | `Default: OFF`；仅推荐 RNA-甲基化 / SLAM 类特殊应用 | B2 |
| `--minimap2/--mm2` | `Default: OFF`；推荐 EM-seq + ONT/PacBio | B2 |
| `--parallel INT` | `e.g. --parallel 4 will use 8 threads in total`（上下链各一套索引） | B2 |
| `--single_fasta` | 与 `--minimap2` 不兼容 | B2 |
| `--genomic_composition` | 生成 `genomic_nucleotide_frequencies.txt` | B2 |
| `--slam` | T→C（正链）/ A→G（反链）转换模式 | B2 |
| `--large-index` | 与 `--minimap2` 不兼容 | B2 |

## B. `bismark`（比对 + methylation call）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `--genome <genome_folder>` | 必填；`The path may also be set as --genome_folder /path/to/genome/folder/` | B3 |
| `-1 <mates1>` / `-2 <mates2>` | 逗号分隔文件列表，file-for-file、read-for-read 对应；**配对关系由它们决定** | B3 |
| `<singles>` | 逗号或空格分隔的 read 文件列表 | B3 |
| `--se/--single_end <list>` | 显式单端模式 | B3 |
| `-N <int>` | 种子错配数；`Default: 0` | B3 |
| `-L <int>` | 种子长度；`Default: the --sensitive preset of Bowtie 2 is used by default, which sets -L to 20` | B3 |
| `--score_min <func>` | `The default is: L,0,-0.2` | B3 |
| `-p NTHREADS` | `default: 1` | B3 |
| `--parallel <int>`（= `--multicore`） | 并行实例数；`Bismark Parallel is resource hungry!` | B3 |
| `--non_directional` | `Default: OFF`；非定向库四链都比 | B3 |
| `--pbat` | `Default: OFF`；仅 PBAT 库 | B3 |
| `--local` | `DEFAULT: OFF`；仅 PBAT/scBS-seq 类应用 | B3 |
| `-o/--output_dir <dir>` | 输出目录；不存在则创建 | B3 |
| `--sam` / `--cram` | 默认输出 BAM；`--cram` 在 Rust 对齐器中不支持 | B3 |
| `-B/--basename <basename>` | 优先于 `--prefix` | B3 |
| `--rg_tag` / `--rg_id` / `--rg_sample` | `Default: OFF` / `SAMPLE` / `SAMPLE` | B3 |
| `--nucleotide_coverage` | 调用 `bismark bam2nuc`，仅 BAM/CRAM | B3 |
| `--paired-end`（aligner 侧） | **官方选项表中不存在**（B3、B10、B1、B11 均无）；配对由 `-1/-2` 指定 | B3 / B10 |

## C. `bismark dedup`（旧名 `deduplicate_bismark`）

| 参数 | 官方说明 | 来源 |
| --- | --- | --- |
| `--bam` | 用法：`bismark dedup --bam [options] <filenames>` | B1 |
| 适用性 | `recommended for whole-genome bisulfite samples, but should not be used for reduced representation libraries such as RRBS, amplicon or target enrichment libraries` | B1 |

## D. `bismark extract`（旧名 `bismark_methylation_extractor`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `<filenames>` | BAM/SAM/CRAM（旧 `--vanilla` 用于 0.5.x 私有格式） | B4 |
| `-s/--single-end` / `-p/--paired-end` | `If neither -s nor -p is set the type of experiment will be determined automatically` | B4 |
| `--comprehensive` | 合并四种链特异的 call 为按 context 输出；默认 12 文件 → 3 文件 | B4 / B5 |
| `--merge_non_CpG` | context 模式下 2 个文件；默认模式下 8 个文件 | B4 |
| `--no_overlap` | `This option is on by default for paired-end data but can be disabled using --include_overlap. Default: ON` | B4 |
| `--ignore <int>` | 忽略 R1（或单端）5' 端 N bp，如 RRBS 的 MspI 位点 | B4 |
| `--ignore_r2 <int>` | 忽略 R2 5' 端 N bp（端修复偏倚） | B4 |
| `--ignore_3prime <int>` / `--ignore_3prime_r2 <int>` | 忽略 3' 端 N bp | B4 |
| `--report` | `Default: ON` | B4 |
| `--gzip` | 压缩提取文件；`bedGraph` 与 `coverage` 默认写 `.gz` | B4 |
| `--mbias_only` / `--mbias_off` | `Default: OFF` / `Default: OFF` | B4 |
| `--multicore <int>` | 提取并行核数；对 `bismark bedgraph` / `bismark cov2cyt` 无效 | B4 |
| `--bedGraph` | 输出 0-based start / 1-based end 的 bedGraph + coverage | B4 |
| `--zero_based` | `Default: OFF` | B4 |
| `--cutoff [threshold]` | 最低观测次数；`Default: 1` | B4 |
| `--CX/--CX_context` | `Default: OFF (i.e. Default = CpG context only)`；会显著变慢 | B4 |
| `--buffer_size <string>` | `Defaults to 2G`；支持 `50%` / `20G` 等 | B4 |
| `--scaffolds/--gazillion` | 大量 scaffold 时避免文件句柄上限 | B4 |
| `--ample_memory` | 与 `--scaffolds/--gazillion` 不兼容；人类 chr1 双数组约 16 GB | B4 |
| `--cytosine_report` | 需配合 `--genome_folder`；默认 CpG context、1-based、双链全部 C | B4 |
| `--genome_folder <path>` | `Enter the genome folder you wish to use to extract sequences from (full path only) ... Specifying a genome folder path is mandatory.` | B4 |
| `--split_by_chromosome` | 按染色体拆分输出 | B4 |
| `--ffs` | 额外输出 four-/five-/six-nucleotide context（`xxCxxx`） | B4 |

## E. `bismark filter`（旧名 `filter_non_conversion`）

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `[Bismark BAM files]` | 用法：`bismark filter [options] [Bismark BAM files]` | B7 |
| `-s/--single` / `-p/--paired` | 未指定则自动判断库类型 | B7 |
| `--threshold [int]` | `The number of methylated cytosines in non-CG context at which reads or read pairs are filtered out. [Default: 3]` | B7 |
| `--percentage_cutoff [int]` | 按非 CG 甲基化百分比过滤，需配合 `--minimum_count` | B7 |
| `--minimum_count [int]` | `[Default: 5]` | B7 |
| `--consecutive` | `[Default: OFF]` | B7 |
| 适用性警告 | 非 CG 甲基化显著的物种（多数植物）不宜使用 | B7 |

## F. bwa-meth

| 命令 / 参数 | 官方说明 | 来源 |
| --- | --- | --- |
| `bwameth.py index $REF` | `Indexes with BWA-MEM (default)`；生成 `some.c2t.fasta` 与 bwa 索引 | M1 |
| `bwameth.py index-mem2 $REF` | `Indexes with BWA-MEM2` | M1 |
| `--threads <n>` | 官方示例 `--threads 16` | M1 |
| `--reference $REFERENCE` | 必填参考 | M1 |
| `$FQ1 $FQ2` | 单端只给 1 个文件；`Fastqs can be gzipped or not` | M1 |
| 输出 | `bwa-meth now outputs sam to stdout. It is up to the user to convert to bam`（`--prefix`/`--calmd` 已移除） | M1 |
| 内部调用 | `bwa mem -L 25 -pCM -t 15 $REFERENCE.c2t.fa '<python bwameth.py c2t $FQ1 $FQ2'` | M1 |
| 后续计数 | `For tabulation, bias, and plotting, use MethylDackel`；SNP 用 `biscuit` | M1 |

## G. methylKit

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| `methRead(..., mincov = 10)` | `By default methRead requires a minimum coverage of 10 reads per base` | K |
| `context="CpG"` | 上下文；与 `tileMethylCounts`/`unite` 的 context 必须一致 | K |
| `treatment=c(1,1,0,0)` | 分组向量，顺序须与 `file.list`、`sample.id` 一致 | K |
| `dbtype="tabix"`, `dbdir` | 落盘为 `methylRawListDB`（大样本省内存） | K |
| `filterByCoverage(lo.count, lo.perc, hi.count, hi.perc)` | 官方示例 `lo.count=10, lo.perc=NULL, hi.count=NULL, hi.perc=99.9` | K |
| `normalizeCoverage()` | 官方 FAQ：先 `filterByCoverage()` 再 `normalizeCoverage()` | K |
| `unite(destrand=FALSE)` | `destrand=TRUE` 仅适用于 CpG（双链合并），CpH 会出错 | K |
| `unite(..., min.per.group=1L)` | 放宽"全部样本覆盖"要求 | K |
| `calculateDiffMeth(meth)` | 有重复时自动用 logistic regression；无重复用 Fisher | K |
| `calculateDiffMeth(..., overdispersion="MN")` | 默认**不做**过离散校正；开启后自动切 F 检验 | K |
| `calculateDiffMeth(..., test="Chisq"\|"F")` | 未做校正时默认 Chisq；`F` 仅能在开启过离散校正时使用 | K |
| `calculateDiffMeth(..., covariates=data.frame(...))` | 行顺序须与 `methylBase` 样本顺序一致 | K |
| `calculateDiffMeth(..., mc.cores=2)` | 多核加速 | K |
| `getMethylDiff(difference=25, qvalue=0.01, type="hyper"\|"hypo")` | 官方示例阈值 | K |
| `diffMethPerChr(..., qvalue.cutoff=0.01, meth.cutoff=25)` | 按染色体统计 hyper/hypo 比例 | K |
| `tileMethylCounts(win.size=1000, step.size=1000, cov.bases=10)` | 窗口化；配合较低 `mincov`（示例 `mincov=3`） | K |
| `regionCounts(methylRawList, GRanges)` | 区域汇总；结果顺序按染色体/坐标重排（FAQ 明示） | K |
| `pool()` | 每组汇成一个样本，从而强制走 Fisher | K |

## H. DSS

| 参数 | 官方说明 / 默认值 | 来源 |
| --- | --- | --- |
| 输入列 | `chr pos N X`（染色体、坐标、总 reads、甲基化 reads） | D |
| `makeBSseqData(list(...), c(...))` | 建 `BSseq` 对象（依赖 bsseq） | D |
| `DMLtest(group1=, group2=)` | 默认 `smoothing=FALSE` 的写法与 `smoothing=TRUE` 的写法官方都给出 | D |
| `smoothing` | `We use 500 bp as default`；WGBS 强烈推荐；RRBS 仍推荐 | D |
| `ncores` | 并行核数；Windows 建议 `ncores=1`（依赖 forking） | D |
| `callDML(p.threshold=0.001)` | DML 调用；结果按显著性排序 | D |
| `callDML(delta=0.1, p.threshold=0.001)` | `delta` 时 p 阈值实为 local FDR（`1-posterior probability`） | D |
| `callDMR(p.threshold=0.01)` | DMR 调用；按 `areaStat` 排序 | D |
| `callDMR(delta=0.1, p.threshold=0.05)` | 带效应量阈值的 DMR | D |
| `DMLfit.multiFactor(..., formula=~case+cell+case:cell)` | 一般设计（arcsine link + 广义最小二乘） | D |
| `DMLtest.multiFactor(DMLfit, coef=\|term=\|Contrast=)` | 单参数 Wald / 复合 F 检验 | D |
| `delta`（multifactor） | `delta is NOT supported` | D |
| 低覆盖过滤 | `No. DSS will take care of the coverage depth information.` | D |
| 甲基化率输入 | `No. DSS only takes count data.` | D |

## I. bsseq

| 参数 | 官方说明 | 来源 |
| --- | --- | --- |
| `BSseq(chr=, pos=, M=, Cov=, sampleNames=)` | 直接建对象；或 `gr=` 传 `GRanges` | S |
| `orderBSseq(BStmp, seqOrder=)` | 平滑前必须有序：`The smoothing functions assumes that the underlying BSseq has been ordered` | S |
| `chrSelectBSseq(..., order=TRUE)` | 选染色体并可重排 | S |
| `collapseBSseq(BStmp, group=)` | 合并同一生物样本的多列（lane） | S |
| `combine()` | 两对象取样本并集与位点并集 | S |
| `getCoverage(type="Cov"\|"M")` / `getMeth(type="raw"\|"smooth")` | 取覆盖/甲基化；`what="perBase"\|"perRegionTotal"\|"perRegionAverage"` | S |
| `BSmooth(BS.chr22[,"r1"], verbose=TRUE)` | 平滑；参数 `mc.cores`、`parallelBy="sample"\|"chromosome"`、`maxGap` | S |
| `BSmooth.tstat()` → `dmrFinder()` | t 统计与 DMR 阈值化（官方三步流程第 2、3 步） | S |
| `fisherTests()` | 逐位点 Fisher 精确检验 | S |
| `read.bismark(bismarkfiles, BACKEND="HDF5Array", BPPARAM=MulticoreParam(workers=10))` | 直接读 Bismark 输出（HDF5 后端） | S |
| `saveHDF5SummarizedExperiment(BSseq, dir="./BSseqName.h5")` | 落盘为 HDF5 后端 | S |
| `mc.cores > 1` | `not support on MS Windows` | S |
| 内存量级 | 8 样本含平滑值约 1.2 GB RAM；并行会成倍增加 | S |

## J. 非官方部分：本技能给出的判据（明确标注，不是官方参数）

| 场景 | 判据 | 说明 |
| --- | --- | --- |
| 覆盖度门槛 | 官方无统一数值 | methylKit 默认 `mincov=10` 可作起点；WGBS 常另报 ≥1×/≥5×/≥10× 覆盖 CpG 占比 |
| 转换效率验收 | 官方两种判据 | λ/phiX 非转换率；或非 CG 最低甲基化率（人类常可到 99.7% 量级，官方举例） |
| DMR 阈值 | 官方明示无自然阈值 | DSS 原文：`It is very difficulty to select a natural and rigorous threshold for defining DMRs. We recommend users try different thresholds` |
| DMR↔表达 | 官方无桥接命令 | 只做 promoter(TSS±1000) / gene body 分层 + 符号一致性 |

## 来源索引

- B1 https://felixkrueger.github.io/Bismark/quick-reference/
- B2 https://felixkrueger.github.io/Bismark/options/genome-preparation/
- B3 https://felixkrueger.github.io/Bismark/options/alignment/
- B4 https://felixkrueger.github.io/Bismark/options/methylation-extraction/
- B5 https://felixkrueger.github.io/Bismark/usage/methylation-extraction/
- B6 https://felixkrueger.github.io/Bismark/faq/conversion-efficiency/
- B7 https://felixkrueger.github.io/Bismark/usage/filtering-non-conversion/
- B8 https://felixkrueger.github.io/Bismark/
- B10 https://felixkrueger.github.io/Bismark/usage/alignment/
- M1 https://github.com/brentp/bwa-meth
- K https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html
- D https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html
- S https://bioconductor.org/packages/release/bioc/vignettes/bsseq/inst/doc/bsseq.html
- P1 https://bioconductor.org/packages/release/bioc/html/MEDIPS.html
