# 参数表：ChIP-TF / ChIP-histone / ATAC / CUT&Tag

约定：
- 「官方默认」列一律取自官方文档或官方源码，不写个人偏好值。
- 没有官方默认、只有官方建议（recommendation）的，标 `建议值（官方文字）`，不得当成默认。
- 每个表格末尾给出该表全部参数的来源 URL。

---

## A. ChIP-seq（转录因子，narrow peak）

### A1 peak calling：`macs3 callpeak`

| 参数 | 官方默认 | 说明（官方原文/口径） |
| --- | --- | --- |
| `-t/--treatment` | 无（唯一 REQUIRED） | 多文件 `-t A B C` 会合并 |
| `-c/--control` | 无 | input 或 mock IP；无对照见 `--nolambda` |
| `-f/--format` | `AUTO` | `AUTO` 不能识别 `BAMPE/BEDPE/FRAG`；常用 `BAM` |
| `-g/--gsize` | `hs ~2.9e9` | 预置 `hs 2,913,022,398`(GRCh38)、`mm 2,652,783,500`(GRCm38) |
| `-q/--qvalue` | `0.05` | 与 `-p` 互斥优先级：给了 `-p` 就用 p 值 |
| `-p/--pvalue` | 未设 | 需与 `-q` 二选一 |
| `--keep-dup` | `1` | `auto`/`all`/整数；`FRAG` 下被忽略 |
| `--slocal` / `--llocal` | `1000` / `10000` | 局部 lambda 的两级窗口 |
| `--shift` | `0` | 官方建议 ChIP 保持 0 |
| `--nomodel` / `--extsize` | 关 / 未设 | `--extsize` 仅在 `--nomodel`（或 `--fix-bimodal`）下有效 |
| `--nolambda` | 关 | 无对照时官方推荐开启 |
| `--scale-to` | `small` | 把大数据缩到小数据，官方不建议放大 |
| `--broad` | `False` | TF 场景不开 |
| `--call-summits` | 关 | 同一峰内再找 subpeak |
| `--buffer-size` | `100000` | 染色体多、每染色体 reads 少时可调小 |
| `--cutoff-analysis` | `False` | 输出五列：pscore/qscore/npeaks/lpeaks/avelpeak |
| `--threads` | 依 `MACS3_NUM_THREADS` 或检测 | `--threads 1` 等价串行 |
| `--process-backend` | `auto` | 仅 `auto`/`serial` 可接受 |

来源：https://macs3-project.github.io/MACS/docs/callpeak.html 、 https://macs3-project.github.io/MACS/

### A2 去重与过滤

| 工具/参数 | 官方默认 | 说明 |
| --- | --- | --- |
| `samtools markdup -l` | `300` | 期望最大读长 |
| `samtools markdup -d` | `0` | 光学重复距离；HiSeq 100、NovaSeq 约 2500 |
| `samtools markdup -r` | 关 | 直接移除而非只打标 |
| `samtools markdup --mode` | `t` | 按模板起止；`s` 按序列起止（会多判重复） |
| `samtools view -q` | `0` | MAPQ 下限；常用建议 30（官方无建议值，属工程约定，需在报告中声明） |
| Picard `REMOVE_DUPLICATES` | `false` | 只打标不删 |
| Picard `OPTICAL_DUPLICATE_PIXEL_DISTANCE` | `100` | patterned flowcell 2500 |
| Picard `TAGGING_POLICY` | `DontTag` | 可选 `OpticalOnly`/`All` |

来源：https://www.htslib.org/doc/samtools-markdup.html 、 https://www.htslib.org/doc/samtools-view.html 、
https://gatk.broadinstitute.org/hc/en-us/articles/35967618836635-MarkDuplicates-Picard

### A3 重复一致性与 QC 阈值（ENCODE）

| 指标 | 阈值 |
| --- | --- |
| rescue ratio | `< 2` |
| self-consistency ratio | `< 2` |
| 每重复 usable fragments | `20M`（10–20M low、5–10M insufficient、<5M extremely low） |
| NRF / PBC1 / PBC2 | `>0.9` / `>0.9` / `>10` |
| FRiP | 无定义阈值，仅用于同类实验横向比较 |

来源：https://www.encodeproject.org/chip-seq/transcription_factor/

### A4 IDR

| 参数 | 官方默认 |
| --- | --- |
| `--input-file-type` | 无默认，需显式给（`narrowPeak` 用于 narrowPeak 输入） |
| `--rank` | narrowPeak/broadPeak `signal.value`；bed `score` |
| `--idr-threshold` | 报告全部 |
| `--soft-idr-threshold` | `0.05` |
| `--peak-merge-method` | signal/score 类 `sum`；p/q 类 `min` |
| `--use-nonoverlapping-peaks` | 关（未在所有重复出现的峰默认丢弃） |
| `--initial-mu/sigma/rho/mix-param` | `0.10 / 1.00 / 0.20 / 0.50` |
| `--max-iter` / `--convergence-eps` | `3000` / `1.00e-06` |

来源：https://raw.githubusercontent.com/kundajelab/idr/master/README.md

---

## B. ChIP-seq（组蛋白修饰，broad / narrow）

### B1 broad peak calling

| 参数 | 官方默认 | 说明 |
| --- | --- | --- |
| `--broad` | `False` | 开启后输出 `broadPeak` + `gappedPeak` |
| `--broad-cutoff` | `0.1` | 仅 `--broad` 可用；`-p` 存在时按 p 值解释，否则按 q 值 |
| `-q/--qvalue` | `0.05` | broad mark 官方建议可试 `0.01` |
| `--max-gap` | 窄峰侧默认 = 读长/片段长；宽峰合并用其 `4 倍` | 官方明确 4 倍关系 |
| `--min-length` | 默认 = 预测片段大小 `d` | 小于片段长基本无效 |

来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### B2 mark 分型（决定 narrow/broad）

| 类别 | mark |
| --- | --- |
| Broad Marks | H3F3A、H3K27me3、H3K36me3、H3K4me1、H3K79me2、H3K79me3、H3K9me1、H3K9me2、H4K20me1 |
| Narrow Marks | H2AFZ、H3ac、H3K27ac、H3K4me2、H3K4me3、H3K9ac |
| Exception | H3K9me3（重复区富集，单独深度口径） |

来源：https://www.encodeproject.org/chip-seq/histone/

### B3 深度与一致性

| 指标 | 阈值 |
| --- | --- |
| narrow mark 每重复 | `20M` usable fragments |
| broad mark 每重复 | `45M` usable fragments |
| H3K9me3（组织/原代细胞） | `45M` total mapped reads |
| NRF / PBC1 / PBC2 | `>0.9` / `>0.9` / `>10` |
| 重复一致性 | 不走 IDR：两重复均出现，或出现在两个 pseudoreplicate；unreplicated 用 ≥50% naive overlap |

来源：https://www.encodeproject.org/chip-seq/histone/

---

## C. ATAC-seq

### C1 两条官方路线（必须二选一，不可混搭）

**路线 1：MACS3 官方 ATAC 示例（PE 直读 BAM）**

```bash
macs3 callpeak -f BAMPE -t ATAC.bam -g hs -n test -B -q 0.01
```
- 硬约束：`-f BAMPE` 时 `--shift` 只能为 0（官方原文 `you can't set values other than 0 if the format is BAMPE or BEDPE`）。

**路线 2：ENCODE 风格（TAGALIGN + 单端语义 + shift/extsize）**

```bash
macs2 callpeak -t {ta} -f BED -n {prefix} -g {gensz} -p {pval_thresh} --shift {shiftsize} --extsize {extsize} --nomodel -B --SPMR --keep-dup all --call-summits
```

| 参数 | 官方默认 / 官方示例值 |
| --- | --- |
| `-f` | `BED`（TAGALIGN 输入） |
| `-p` | `0.01`（`--pval-thresh` 默认） |
| `--smooth-win` → `--extsize` | `150` |
| `--shift` | `-int(round(150/2)) = -75` |
| `--nomodel` | 开启 |
| `-B` / `--SPMR` | 开启 |
| `--keep-dup` | `all` |
| `--call-summits` | 开启 |
| peak 数上限 | `300000`（按第 8 列排序后截断） |
| 内存估计 | `4.0 GB`（用于 `sort -S` 取一半） |

来源：https://raw.githubusercontent.com/ENCODE-DCC/atac-seq-pipeline/master/src/encode_task_macs2_atac.py

**MACS3 文档中的 ATAC/DNase 通用写法（作为对照，非 ENCODE 口径）**

| 参数 | 官方文字 |
| --- | --- |
| `--nomodel --shift -100 --extsize 200` | 「If the wanted smoothing window is 200bps」 |
| `--shift -50 --extension 100` | 官方示例「ATAC-seq (focusing on insertion sites, and using single-end mode)」 |

来源：https://macs3-project.github.io/MACS/docs/callpeak.html

### C2 QC 阈值（ENCODE ATAC）

| 指标 | 阈值 |
| --- | --- |
| 重复数 | ≥2 生物学重复（EN-TEx 可放宽到 ≥2 技术重复） |
| 深度 | SE `25M` / PE `50M` non-duplicate non-mitochondrial aligned reads |
| mapping rate | `>95%`（`>80%` 可接受） |
| IDR | rescue 与 self-consistency 均 `< 2` |
| NRF / PBC1 / PBC2 | `>0.9` / `>0.9` / `>3` |
| replicated peaks | `>150,000`（`>100,000` 可接受） |
| IDR peaks | `>70,000`（`>50,000` 可接受） |
| FRiP | `>0.3`（`>0.2` 可接受） |
| TSS enrichment | hg19 <6 / 6–10 / >10；GRCh38 <5 / 5–7 / >7；mm9 <5 / 5–7 / >7；mm10 <10 / 10–15 / >15 |
| fragment size | NFR 必须存在；mononucleosome peak（147–294 bp）必须存在 |
| 读长 | ≥45 bp |
| 组装 | 仅 GRCh38 / mm10 |

来源：https://www.encodeproject.org/atac-seq/

### C3 信号与可视化

| 工具/参数 | 官方默认 |
| --- | --- |
| `bamCoverage --binSize` | `50` |
| `bamCoverage --normalizeUsing` | `None`（`RPGC` 需 `--effectiveGenomeSize`） |
| `bamCoverage --extendReads` | 关 |
| `bamCoverage --minFragmentLength/--maxFragmentLength` | `0` / `0` |
| `computeMatrix reference-point` 的 `-b/-a` | `500` / `1500` |
| `computeMatrix` 的 `-bs` | `10` |
| `plotProfile --plotType` | `lines`（官方列出的可选项含 `fill/se/std/overlapped_lines/heatmap`） |

来源：https://deeptools.readthedocs.io/en/develop/content/tools/bamCoverage.html 、
https://deeptools.readthedocs.io/en/develop/content/tools/computeMatrix.html 、
https://deeptools.readthedocs.io/en/develop/content/tools/plotProfile.html

---

## D. CUT&Tag / CUT&RUN

### D1 SEACR（官方位置参数）

| 位次 | 含义 | 取值 |
| --- | --- | --- |
| 1 | 目标 bedgraph | UCSC bedgraph，必须省略 0 信号区间 |
| 2 | 对照或数值阈值 | IgG control bedgraph，或 `0–1` 的 n（取 total signal 前 n 比例） |
| 3 | 归一化 | `"norm"` 或 `"non"`；官方建议 `"norm"`，**除非**已用 spike-in 严格归一 |
| 4 | 阈值模式 | `"relaxed"`（knee 与 peak 之间）或 `"stringent"`（曲线峰） |
| 5 | 输出前缀 | 产出 `<prefix>.relaxed.bed` / `<prefix>.stringent.bed` |

官方示例：

```bash
bash SEACR_1.3.sh target.bedgraph IgG.bedgraph norm stringent output
bash SEACR_1.3.sh target.bedgraph IgG.bedgraph non relaxed output
bash SEACR_1.3.sh target.bedgraph 0.01 non stringent output
```
来源：https://github.com/FredHutch/SEACR

### D2 输入制备（官方命令）

| 步骤 | 命令 |
| --- | --- |
| BAM → read-pair BED | `bedtools bamtobed -bedpe -i $sample.bam > $sample.bed` |
| 过滤跨染色体/超长 | `awk '$1==$4 && $6-$2 < 1000 {print $0}' $sample.bed > $sample.clean.bed` |
| 取 5'/3' 端点 BED3 | `cut -f 1,2,6 $sample.clean.bed \| sort -k1,1 -k2,2n -k3,3n > $sample.fragments.bed` |
| BED → bedGraph | `bedtools genomecov -bg -i $sample.fragments.bed -g my.genome > $sample.fragments.bedgraph` |

来源：https://github.com/FredHutch/SEACR

### D3 替代口径（官方支持的两种「无 IgG」处理）

| 场景 | 做法 | 来源 |
| --- | --- | --- |
| 有 spike-in 且已严格归一 | SEACR 用 `"non"` | https://github.com/FredHutch/SEACR |
| 无 IgG 无 spike-in | SEACR 用数值阈值，如 `0.01`（按 AUC 取前 1%） | https://github.com/FredHutch/SEACR |
| 若坚持用 MACS 系 | MACS3 `--nolambda`（官方：无对照样本时特别推荐） | https://macs3-project.github.io/MACS/docs/callpeak.html |
| CUT&Tag 专属参数体系 | 官方文档未提供 | 见 `official-docs.md` §3 第 1 条 |

### D4 深度与一致性

官方 SEACR README 与 ENCODE 三个 standards 页均未给 CUT&Tag/CUT&RUN 的深度与 IDR 阈值。
可复用的官方判据只有：SEACR 的阈值来自「target 与 control 的 signal 分布比较」（`relaxed`/`stringent` 的曲线位置），
以及 spike-in 归一化后 `"norm"` 可关。其余（每样本最少 fragments、重复一致性指标）无官方阈值，报告中必须显式声明为「无官方阈值」。

---

## E. motif 与注释（四类共用）

### E1 HOMER

| 参数 | 官方默认 |
| --- | --- |
| `-size` | `200`（必填；可 `given` 或 `-100,50` 形式） |
| `-len` | `8,10,12` |
| `-S`（每个长度找多少 motif） | `25` |
| `-mis` | `2` |
| `-N`（背景序列数） | `max(50000, 2×输入峰数)` |
| `-nlen` | `3`（`0` 关闭） |
| `-olen` | `0`（关闭） |
| `-p` | `1` |
| `-bg` | 未设（自动随机 + GC 匹配） |
| `-h`（超几何） | 关（默认二项分布） |

来源：http://homer.ucsd.edu/homer/ngs/peakMotifs.html

### E2 MEME-ChIP

| 参数 | 官方默认 |
| --- | --- |
| 输入长度 | 建议 100–500 bp、等长、中心富集 |
| `-neg` | 未设（MEME 用 Classic 目标函数） |
| `-order` | 2 阶 Markov 背景 |
| `-db` | 未设（无法报相似已知 motif） |
| `-filter-thresh` | `0.05` |
| `-minw` / `-maxw` | `6` / `15` |
| `-meme-nmotifs` | `3` |
| `-ccut` | `100` |
| `-group-thresh` | `0.05` |
| `-streme-pvt` | `0.05` |
| `-centrimo-ethresh` | `10` |
| `-meme-brief` | `1000` |

来源：https://meme-suite.org/meme/doc/meme-chip.html

### E3 ChIPseeker

| 参数 | 官方默认 |
| --- | --- |
| `tssRegion` | `c(-3000, 3000)` |
| `TxDb` | 无默认，需显式给（如 `TxDb.Hsapiens.UCSC.hg19.knownGene`） |
| `annoDb` | 可选（给了才追加 SYMBOL/GENENAME/ENSEMBL/ENTREZID） |
| 注释优先级 | Promoter > 5' UTR > 3' UTR > Exon > Intron > Downstream > Intergenic |
| `nShuffle`（enrichPeakOverlap） | 示例值 50；官方提示实际用 ≥1000 |

来源：https://bioconductor.org/packages/3.21/bioc/vignettes/ChIPseeker/inst/doc/ChIPseeker.html
