# 常见失败模式与排查顺序

排查顺序固定为：**分型是否搞错 → 输入格式/排序是否符合工具硬要求 → 参数组合是否被官方禁止 → 阈值是否与数据深度不匹配 → 下游判据是否被误用**。
每条给出官方依据；官方没有给处置办法的，标「无官方处置」，只写判据。

---

## 1 分型与 caller 选择错误

### 1.1 组蛋白 broad mark 用窄峰参数
- 现象：peak 数量极多、中位长度短、gappedPeak 缺失，下游 motif 无富集。
- 判据：先按 ENCODE 的 mark 名单确认是否属 Broad Marks（H3K27me3、H3K36me3、H3K4me1、H3K79me2/3、H3K9me1/2、H4K20me1、H3F3A）。
  来源：https://www.encodeproject.org/chip-seq/histone/
- 处置：改用 `--broad` + `--broad-cutoff`，官方命令 `macs3 callpeak -t ChIP.bam -c Control.bam --broad -g hs --broad-cutoff 0.1`。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 1.2 只要「更宽的峰」，却开了 `--broad`
- 官方原文：若只想要更宽的峰、不要嵌套结构，`please simply use -p or -q with weaker cutoff instead of using --broad option`。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 1.3 CUT&Tag/CUT&RUN 用 MACS 系默认参数
- 现象：peak 数量爆炸、短峰碎片化。
- 判据：SEACR 明确定位是「background is dominated by "zeroes"」的稀疏数据；MACS 的泊松局部 lambda 模型不为此类分布设计
  （MACS3 只承诺「任意 DNA enrichment assay」的通用显著性，不承诺稀疏零膨胀背景）。
  来源：https://github.com/FredHutch/SEACR 、 https://macs3-project.github.io/MACS/
- 处置：切到 SEACR；有 IgG 用 `norm|non` 二选一，无 IgG 用数值阈值（如 `0.01`）。

---

## 2 输入格式与排序

### 2.1 `samtools markdup` 报缺 MC/ms tag
- 官方：markdup `relies on the MC and ms tags that fixmate provides`，且输入「has been run through samtools fixmate with the -m option」。
- 处置：按官方链路重跑 `collate -o` → `fixmate -m` → `sort -o` → `markdup`。
  来源：https://www.htslib.org/doc/samtools-markdup.html

### 2.2 Picard MarkDuplicates 报排序错误
- 官方：`INPUT … Must be coordinate sorted`。
- 处置：先 `samtools sort`；若是 BWA-MEM 的 split alignment 导致异常，用 BWA `-M` 把较短 split hit 标为 secondary。
  来源：https://gatk.broadinstitute.org/hc/en-us/articles/35967618836635-MarkDuplicates-Picard 、 https://bio-bwa.sourceforge.net/bwa.shtml

### 2.3 MACS3 把 PE 数据当 SE 处理
- 现象：`AUTO` 下 fragment 分布双峰模型异常、峰偏移。
- 官方：`MACS3 can't detect BAMPE, BEDPE or FRAG format with AUTO`；`BAMPE` 下 `MACS3 will use the real fragments`。
- 处置：显式 `-f BAMPE`；或用官方 `randsample/filterdup` 转 BEDPE。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 2.4 SEACR 报错或峰数异常
- 检查项（官方口径）：R 与 Bedtools 必须在 PATH；输入必须是 **bedgraph**；bedgraph 必须**省略 0 信号区间**；
  必须来自 paired-end（read-pair）而非单端 read 密度。
- v1.3 已修「thresholding 对部分数据集失效」并新增「过滤含零信号的输入行」；版本过旧会表现为阈值异常。
  来源：https://github.com/FredHutch/SEACR

### 2.5 HOMER 报格式错误
- 官方：HOMER peak 文件 ≥5 列，BED ≥6 列，且第 4 列必须是唯一 ID；`-size` 现在是必填参数。
- 若序列被大量丢弃（>`70% N`）：官方建议改用 unmasked genome 再试。
  来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

---

## 3 被官方禁止的参数组合

### 3.1 `-f BAMPE` + 非 0 `--shift`
- 官方原文：`you can't set values other than 0 if the format is BAMPE or BEDPE for paired-end data`。
- 处置：二选一 —— 保留 PE 语义（`-f BAMPE`，不设 shift），或转单端/tagAlign 后 `-f BED --nomodel --shift -X --extsize Y`
  （ENCODE 就是这样做的：`-f BED` + `--shift -75 --extsize 150`）。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html 、
  https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_macs2_atac.py

### 3.2 `--extsize` 没配 `--nomodel`
- 官方：`--extsize` 仅在 `--nomodel`（或建模失败且 `--fix-bimodal`）时有效；否则被忽略，表现为「改了参数没变化」。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 3.3 `--broad-cutoff` 没配 `--broad`
- 官方：`This option is not available unless --broad is set`。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 3.4 SEACR 写成 `--control/--norm/--non`
- 官方接口是 5 个位置参数，不存在这些长选项。正确写法见 `parameters.md` §D1。
  来源：https://github.com/FredHutch/SEACR

### 3.5 `bamCoverage --normalizeUsing RPGC` 缺 `--effectiveGenomeSize`
- 官方：`This option requires --effectiveGenomeSize`。
  来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

---

## 4 阈值与深度不匹配

### 4.1 IDR 无峰
- 官方报错原文：`No IDR peaks found. IDR threshold might be too stringent or replicates have very poor concordance.`
- 排查次序：
  1. 输入是否被**预先阈值化**（IDR 官方要求 ranked list 覆盖从高置信到噪声的全谱）；
  2. 是否用了 `--peak-list`（merged/pooled），ENCODE 的调用式即带 `--peak-list`；
  3. `--rank` 选列是否与数据匹配（narrowPeak 默认 `signal.value`，ENCODE 默认 `p.value`）；
  4. 是否该开 `--use-best-multisummit-IDR`（MACS 多 summit 计分不均时的官方绕行）。
  来源：https://raw.githubusercontent.com/kundajelab/idr/master/README.md 、
  https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_idr.py

### 4.2 FRiP 偏低
- 先看是否达 ENCODE ATAC 口径：`>0.3` 理想，`>0.2` 可接受；TF ChIP 的 FRiP 官方**没有**定义阈值，不得当硬门禁。
  来源：https://www.encodeproject.org/atac-seq/ 、 https://www.encodeproject.org/chip-seq/transcription_factor/
- 结构性排查（官方口径）：黑名单是否命中（黑名单区域「high signal/read counts independent of cell type」，
  不剔除会虚高信号但也会污染 peak 集）；`bamCoverage` 的 `--blackListFileName` 只拒绝「重叠 chunk」，
  read 若只是部分重叠仍可能被计入，需在报告中说明这一近似。
  来源：https://www.encodeproject.org/annotations/ENCSR636HFF/ 、
  https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

### 4.3 ATAC peak 数远低/远高
- 参照 ENCODE ATAC 判据：replicated peaks `>150,000`（`>100,000` 可接受）；IDR peaks `>70,000`（`>50,000` 可接受）。
- 若峰数偏高且中位宽度很小：检查是否用了 ENCODE 的 cap（`300000`）与 `--call-summits`（会拆出更多 summit，但峰边界应共享）。
  来源：https://www.encodeproject.org/atac-seq/ 、
  https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_macs2_atac.py

### 4.4 TSS enrichment 落在 Concerning
- 按物种/注释对表判断（hg19 <6、GRCh38 <5、mm9 <5、mm10 <10 为 Concerning）。
- 注意口径差异：deepTools 的 `computeMatrix` + `plotProfile` 只给 TSS 前后信号曲线，**不等于** ENCODE 的 TSS enrichment score；
  数值口径要用 ENCODE 的 `src/encode_task_tss_enrich.py`（官方未给命令行，见 `official-docs.md` §3 第 3 条）。
  来源：https://www.encodeproject.org/atac-seq/ 、
  https://deeptools.readthedocs.io/en/develop/content/tools/computeMatrix.html

### 4.5 fragment size 看不到单核小体峰
- 官方判据：必须有 NFR，且 fragment length distribution 必须出现 mononucleosome peak
  （官方原文 `longer than 147 bp but shorter than 147*2 bp`）。
- 若无：先确认不是单端数据、没有用 `--extendReads` 把片段拉平、没有用 `--minFragmentLength/--maxFragmentLength` 误裁。
  来源：https://www.encodeproject.org/atac-seq/ 、
  https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

---

## 5 下游判据误用

### 5.1 单重复却引用 `rescue / self-consistency < 2`
- 官方：单重复走 pseudoreplicate 路线，且明确「there are no corresponding optimal and conservative peak sets in the unreplicated case」。
- 结论写法：声明「pseudoreplicate IDR / pseudoreplicated peaks」，不得声称通过重复一致性标准。
  来源：https://www.encodeproject.org/chip-seq/transcription_factor/ 、
  https://www.encodeproject.org/chip-seq/histone/ 、 https://www.encodeproject.org/atac-seq/

### 5.2 histone 数据套用 IDR 阈值
- 官方 histone 管线不用 IDR，用 replicated peaks / partition concordance。
  来源：https://www.encodeproject.org/chip-seq/histone/

### 5.3 motif 结果「不显著」就换工具
- HOMER 官方判断：TF ChIP 应出现强富集（`<< 1e-50`），否则「there is a strong possibility that the experiment may have failed」。
  即先怀疑实验/peak 质量，再怀疑工具。
  来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

### 5.4 HOMER 背景没设对
- 默认背景是 `max(50000, 2×峰数)` 的 GC 匹配随机区；要比「某细胞类型特异 vs 另一细胞类型特异」，必须用 `-bg`；
  且当背景序列少于 target 时，官方建议改 `-h`（超几何）而非默认二项分布。
  来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

### 5.5 MEME-ChIP 输入长度不齐
- 官方：`When this option is used, the primary and control sequences should all be the same length; otherwise CentriMo E-values will be inaccurate.`
  来源：https://meme-suite.org/meme/doc/meme-chip.html

### 5.6 deepTools 矩阵版本不兼容
- 官方：`As of version 3.0, computeMatrix produces output with labels present for each sample. Matrices produced with that or later versions can not be used with older versions of plotHeatmap`。
  处置：统一 deepTools 版本。
  来源：https://deeptools.readthedocs.io/en/develop/content/tools/computeMatrix.html

### 5.7 HOMER 报内存不足（长 motif）
- 官方：`values greater 12 may cause the program to run out of memory - in these cases decrease the number of sequences analyzed (-N), or try analyzing shorter sequence regions (i.e. -size 100)`。
  来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

---

## 6 运行环境类

### 6.1 MACS3 进程池异常 / 在 notebook 里跑
- 官方：`Peak calling defaults to the auto process backend`，只在「main Python thread、无其他 Python 线程、非 daemon、fork 可用」时 fork；
  嵌入应用与 notebook `should select serial when they cannot establish that their host is safe to fork`。
- 处置：`--process-backend serial` 或 `--threads 1`（后者为全局 CPU 预算语义，二者解决的问题不同）。
  来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### 6.2 MACS3 装不上
- 官方：MACS3 3.1.0 需 Python ≥3.12，且 `Windows is not currently supported`；建议虚拟环境 `python -m pip install macs3`。
  来源：https://github.com/macs3-project/MACS

### 6.3 bowtie2 把不一致配对比对也报出来
- 官方：默认同时搜 concordant 与 discordant；可用 `--no-discordant` 关闭。
  来源：https://bowtie-bio.sourceforge.net/bowtie2/manual.shtml

### 6.4 黑名单过滤后 effective genome size 没跟着改
- 官方提醒：使用 `--blackListFileName` 后「you should adjust the effective genome size, if relevant」。
  来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html

---

## 7 无官方处置办法的项（只写判据）

| 问题 | 官方文档状态 | 报告里怎么写 |
| --- | --- | --- |
| CUT&Tag spike-in 归一化因子怎么算 | 无官方命令 | 写清 spike-in 物种、比对比例、是否因此关闭 SEACR 的 `norm` |
| ATAC fragment size 直方图的官方命令 | 无 | 只报「NFR 是否出现 / mononucleosome 峰是否出现」+ 你实际用的绘图工具名 |
| FRiP 的官方单行命令 | 无（只有 `encode_lib_frip.py`） | 写明 FRiP 定义与计数边界（是否含黑名单过滤后的 reads） |
| MACS3 bedGraph → bigWig 的官方命令 | 无 | 改用 `bamCoverage` 出 bigWig，并注明未从 bdg 转换 |
| peak 丰度与 RNA 表达的联合建模 | 无 | 只做 consensus peak 计数 + DESeq2 / 或 seq2gene 映射 + 富集，写明未做联合建模 |
