# 排查手册（按失败现象 → 官方依据 → 处理顺序）

原则：先用官方文档能确认的原因排除，再动参数。凡是官方文档没有给出的阈值/默认值，这里不编造。

---

## 1. MeRIP / exomePeak2

### 「`Require one of the argument in txdb, gff, and genome for transcript annotation.`」
官方源码在 `gff`、`txdb`、`genome` 三者全为 `NULL` 时直接 `stop()`。给其中至少一个：
`gff`（GTF/GFF 路径）、`txdb`（TxDb 对象）或 `genome`（UCSC 名，内部 `makeTxDbFromUCSC`）。
来源：https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R

### peak 数异常多 / 背景被当成峰
第一嫌疑是**没做 GC 校正**：官方说明 `genome` 缺失（`= NULL`）时 "will perform peak calling without correcting the PCR amplification bias"。
处理：补 `genome`（或 BSgenome 对象），并打开 `plot_gc = TRUE` 看 bins GC 含量与拟合覆盖度曲线是否合理。
来源：https://bioconductor.uib.no/packages/3.19/bioc/vignettes/exomePeak2/inst/doc/Vignette_V_2.00.Rmd

### 两组差异结果几乎为空
- 检查是否真的进了差异模式：必须同时给 `bam_ip_treated` **和** `bam_input_treated`（只给 IP 侧走的是普通 peak calling）。
- `test_method = "DESeq2"` 时官方明确提示 "a larger p-value cut-off (e.g. 0.001) is often required"，`p_cutoff` 仍用 `1e-10` 会几乎无峰。
来源：同上 R 源码参数文档。

### 内存爆掉
`mode = "full_transcript"` 或 `"whole_genome"` 官方注明 "demand big memory size (> 4GB) for large genomes"。
处理：回到 `mode = "exon"`（默认），或按染色体拆分后合并（拆分属于调度，不是算法参数）。

### 输出目录里找不到结果
默认落在 `save_dir`（`getwd()`）下的 `experiment_name` 子目录（默认 `exomePeak2_output`），且只在 `save_output = TRUE` 时写盘；返回对象本身是 `GRangesList`，统计量在 `mcols()`。
来源：同上。

### peak 的 `log2FC` 整体接近 0
不要先调 `p_cutoff`。先查链方向：`strandness` 默认 `"unstrand"`，若文库是 dUTP/NSR 却按非链特异处理，IP 与 input 的链归属都会错。用 RSeQC `infer_experiment.py` 判定后改写 `strandness`（`1st_strand` / `2nd_strand`）。
来源：https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R ；https://rseqc.sourceforge.net/

---

## 2. RIP / MACS3

### 峰数爆炸、几乎全基因组都是峰
- 缺 input 对照。官方 `-c` 是 "genomic input or mock IP data"；没有对照时官方建议 `--nolambda`（用全局背景 lambda），否则局部 lambda 估计不可靠。
- `-g` 用错物种/装配（`hs` = 2,913,022,398 是 GRCh38 口径）。有效基因组大小偏小会让噪声被显著化。
来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 双端数据峰形怪异
`-f` 默认 `AUTO`，官方明确 "MACS3 can't detect `BAMPE`, `BEDPE` or `FRAG` format with `AUTO`"，必须显式 `-f BAMPE`（或用 `macs3 filterdup -i x.bam -f BAMPE --keep-dup all -o x.bed` 转 BEDPE）。
来源：同上。

### 重复 reads 处理与预期不符
`--keep-dup` 默认 `1`（同坐标同链只留 1 条）；`auto` 用二项分布按 1e-5 估上限；`all` 保留全部。RIP 若 PCR 重复极高，先用 `--keep-dup auto` 看峰数变化，而不是直接 `all` 掩盖问题。
来源：同上。

### 想要更细的子峰
`--call-summits`：官方说明子峰需 "at least 50 bp of nonnegative supporting signal after thresholding"，且子峰与父峰共享边界、只有 score 与 summit 不同。RIP 分辨率本就低，慎用。
来源：同上。

---

## 3. CLIP / CLIPper

### 启动即报 BAM/index 相关错误
官方 `main()` 先 `check_for_index(options.bam)`，再检查路径存在性，不存在直接 `raise IOError`。
处理：`samtools sort` + `samtools index` 后再跑。

### 报 `Bedtool length is 0; check gene id`
`--gene` 给了不存在的 gene id，或 `--species` 与 BAM 的染色体命名/注释不匹配（用的是 `DATADIR/*AS.STRUCTURE.gff`）。
来源：https://github.com/YeoLab/clipper/blob/master/clipper/src/main.py

### 输出 BED 为空，且伴随 `Nothing here.` 的 tsv
源码在 `filter_peaks_dicts()` 返回字符串时写 `<outfile>.tsv` 内容为 `"Nothing here."`，同时把 BED 写成空/近空。说明过滤阶段把所有峰滤掉了：
先看 `--poisson-cutoff`（默认 0.05）与 `--FDR`（默认 0.05）是否被收得过紧，再看 `--minreads`（默认 3）是否过高、`--threshold` 是否被误用。
来源：同上。

### 跑得极慢或卡在某基因
- 官方提供 `--timeout`（秒）给单个基因设超时，超时会打日志并跳过该基因（"gene %s timed out after %s minutes"）。
- 高表达基因是主因；`--maxgenes` 可先小规模验证。
- `--plot` 会强制 `--debug`（关闭多进程），速度会明显下降——这是官方行为，不是 bug。
来源：同上。

### 想加线程却找不到 `--threads`
CLIPper **没有** `--threads`；用 `--processors`（默认 `autodetect`，即全部核）。eCLIP 官方 CWL 给的是 8 核 / 32 GB。
来源：同上 ；https://github.com/YeoLab/eclip/blob/master/cwl/clipper.cwl

### 换物种后找不到注释数据
`--datadir` 默认指向包内数据目录；官方 CWL 列出的物种为 `ce10 ce11 dm3 hg19 GRCh38 mm9 mm10 GRCh38_pU6 GRCh38_v29 GRCh38_v29e hg19_VSV`。README 的 FAQ 指向 wiki 的 "Supporting additional species" 自行补齐 `*AS.STRUCTURE.gff` 与 `regions/*.bed`。
来源：https://github.com/YeoLab/CLIPper ；https://github.com/YeoLab/eclip/blob/master/cwl/clipper.cwl

### 需要与 input 比较 / 需要交联位点
CLIPper 官方声明 "Currently CLIPper does include input normalization. The input normalization pipeline is in another repository: Merge Peaks"（https://github.com/YeoLab/merge_peaks）；eCLIP 官方流程则用 `overlap_peakfi_with_bam*.pl` + `peakscompress` 做 size-matched input 归一。
CLIPper 输出的是 spline 拟合的 cluster，**官方未定义单核苷酸交联位点**；若必须单碱基分辨率，官方文档未提供可直接执行的命令。
来源：https://github.com/YeoLab/CLIPper ；https://github.com/YeoLab/eclip

---

## 4. motif（HOMER）

### `findMotifsGenome.pl` 报缺少 `-size`
官方明确 "`-size` parameter is now mandatory"。峰宽可变时用 `-size given`。
来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

### 大量序列被丢弃
HOMER 会过滤 ">70% N" 的序列；若丢弃过多，官方建议用未屏蔽（unmasked）基因组重跑，或改用 `-mask` 对照测试。
来源：同上

### RNA 数据 motif logo 出现 T、且已知 motif 匹配很弱
用 `-rna`（只搜正链、U 代 T、自动 `-norevopp`）；但官方同时说明其 RNA motif 库 "only contains miRNAs"，所以 knownResults 里对 splicing/RBP motif 的匹配本来就很有限——这是官方能力边界，不是参数问题。
来源：同上

### 报内存不足
官方提示 `-len` 大于 12 "may cause the program to run out of memory"，缓解方式是减小 `-N`（背景序列数）或缩短 `-size`。
来源：同上

### 想要 RRACH 这类简并序列
HOMER 官方没有「直接以序列字符串富集」的命令；`-find` 需要 HOMER 格式 motif 文件。exomePeak2 侧可用 `motif_sequence`（默认 `"DRACH"`）。若坚持 RRACH，官方文档未提供可直接执行的命令，需自备 motif 矩阵文件。
来源：同上 ；https://github.com/ZW-xjtlu/exomePeak2/blob/master/R/exomePeak2.R

---

## 5. 注释（ChIPseeker）

### `annotatePeak` 报 TxDb 与 BED 的染色体不匹配
常见于 BED 用 Ensembl 命名（`1`）而 TxDb 是 UCSC（`chr1`）。官方给出反向情形（EnsDb 用于 UCSC 命名的 BED）的解法是 `seqlevelsStyle(edb) <- "UCSC"`；反之同理需统一命名。基因组建错（hg19 注释配 hg38 BED）会得到看似正常但全错的注释，务必核对。
来源：https://raw.githubusercontent.com/GuangchuangYu/ChIPseeker/master/vignettes/ChIPseeker.Rmd

### 注释结果里大量 `Promoter`
`tssRegion` 默认 -3kb~+3kb 且优先级最高（Promoter > 5'UTR > 3'UTR > Exon > Intron > Downstream > Intergenic）。若要突出 UTR/CDS 分布，收紧 `tssRegion` 或用 `genomicAnnotationPriority` 改优先级。
来源：同上

### 想做多组比较
`annotatePeak` 需 `verbose = FALSE` 才能安静地批量跑（官方示例即如此），否则每次输出大量信息。
来源：同上

---

## 6. 区间统计 / FRiP（bedtools）

### `-sorted` 报错
`-sorted` 要求输入**按染色体分组且组内按坐标排序**；跨文件染色体顺序不一致时用 `-g <genome file>` 指定期望顺序。
来源：https://bedtools.readthedocs.io/en/latest/content/tools/intersect.html

### FRiP 算出来 >1 或异常低
- 分子分母口径不一致：分子用 `-u` 只计有重叠的 reads（去重后的 BAM），分母必须是同一份 BAM 的有效比对 reads（`samtools view -c -F 4` 之外还要考虑去重前后）。
- 注意 `-abam` 在 2.19.0 起已可由 `-a` 自动识别；老脚本混用 `-abam` 与显式 `-a` 会报错。
- **官方未定义 FRiP 公式与阈值**，报告里必须写明自己的口径，否则无法复现。

---

## 7. 上游 / 通用

### `infer_experiment.py` 报 BED 格式错误
`-r` 需要 **12 列 BED**（gene model），不是 BED6。RSeQC 官方在页面提供 hg19/hg38/mm10/mm9 的 BED 下载。
来源：https://rseqc.sourceforge.net/

### 链特异性结论模棱两可（两方向各 ~50%）
官方判读示例：两侧各约 0.49/0.49 → 非链特异。若你的数据两侧都接近 0.45–0.5，就是非链特异，应把 exomePeak2 的 `strandness` 设为 `"unstrand"`，而不是猜一个链方向。
来源：https://rseqc.sourceforge.net/

### `umi_tools dedup` 说找不到 UMI
默认 `--extract-umi-method=read_id`，即 UMI 必须是 read name 末尾以下划线分隔的词。若 UMI 在 tag 里：`--extract-umi-method=tag --umi-tag=UM`；分隔符不同：`--umi-separator=<sep>`。
来源：https://umi-tools.readthedocs.io/en/latest/reference/dedup.html

### SortMeRNA 起不来 / 找不到索引
官方最小用法要求 `--ref` 与 `--reads` 同时给；多处引用时重复 `--ref`（或用 `--ref` 指向目录）。归档文件与相对路径均支持，格式自动识别。
来源：https://github.com/sortmerna/sortmerna

### STAR 输出里找不到需要的 tag（如 MD）
`--outSAMattributes` 默认 `Standard` = `NH HI AS nM`；要 MD/NM/jM/jI/MC/ch 用 `All`，或显式列出（官方：tags 可任意组合、顺序即输出顺序）。
来源：https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf

### STAR 比对率低
先区分是「多重比对过多」还是「错配超限」：`Log.final.out` 会分别计入 "mapped to too many loci" 等类别。相关默认值：`--outFilterMultimapNmax 10`、`--outFilterMismatchNmax 10`、`--winAnchorMultimapNmax 50`（官方要求 ≥ `--outFilterMultimapNmax`）。
来源：同上
