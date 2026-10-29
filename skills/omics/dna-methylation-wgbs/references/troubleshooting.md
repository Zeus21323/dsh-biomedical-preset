# 故障与判据（全部来自官方文档原文）

每条给出：现象 → 官方给的处置 → 来源。官方文档未覆盖的问题，标注「官方文档未提供」并只给排查方向。

## 1. 上游：比对率与文库类型

### 1.1 双端亚硫酸氢盐样本比对率低

官方建议逐条（原文要点）：

1. `Run adapter and quality trimming. Usually, a standard run through Trim Galore will do the trick`
2. `Perform a multi-genome alignment (e.g. using FastQ Screen (in --bisulfite mode!))`，可疑基因组至少含
   PhiX、Lambda（spike-in）与实验室内常见物种
3. `Align the data in single-end mode. R1 typically needs to be aliged in default (=directional) mode,
   and R2 required --pbat to align.` —— 用来判断是 R1 还是 R2 拖累配对
4. 放宽打分：`--score_min L,0,-0.2`（默认）→ `--score_min L,0,-0.6`
5. BS 文库片段偏短：`fragment sizes often peaking between 80 and 120bp`；个别建库片段超过默认 500 bp，
   可临时 `-X 1000`
6. 最后手段：`--local` 模式（官方明确列出若干 caveats）
7. 特殊建库/试剂盒：见官方 library-types 页

> 来源：https://felixkrueger.github.io/Bismark/faq/low-mapping/

### 1.2 RRBS 被去重导致位点丢失

- `This step is recommended for whole-genome bisulfite samples, but should not be used for reduced
  representation libraries such as RRBS, amplicon or target enrichment libraries.`
  > 来源：https://felixkrueger.github.io/Bismark/quick-reference/

### 1.3 M-bias：R1 起始 / R2 起始异常高甲基化

- 官方解释：`the first couple of bases in Read 2 of BS-Seq experiments show a severe bias towards
  non-methylation as a result of end-repairing sonicated fragments with unmethylated cytosines`；
  建议用 `--ignore_r2 <int>` 去掉；PBAT 库会在 5' 端出现偏倚，用 `--ignore <int>`。
- 先看 `.M-bias.txt`（列：`<read position> <count methylated> <count unmethylated> <% methylation>
  <total coverage>`）再决定 ignore 长度；`--mbias_only` 可只出 M-bias 不写其他文件。
  > 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ 、
  > https://felixkrueger.github.io/Bismark/options/methylation-extraction/

### 1.4 非 Bismark 比对结果无法提取

- 用 `--allow_discordant` 读取带 `XM`/`XR`/`XG` 标签的其它亚硫酸氢盐 aligner 输出；
  双端输入必须**按 read name 分组**（`samtools collate` 或 `samtools sort -n`）：
  `samtools collate -o sample.namecollated.bam sample.bam` + `bismark extract -p --allow_discordant sample.namecollated.bam`
- 明确被拒：`Paired input declared coordinate-sorted is rejected.`；orphan 比例 >20% 会告警。
  > 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/

### 1.5 CRAM 输出报错

- `Requests CRAM output instead of BAM. Not supported by the Rust aligner in v1 (BAM only) — a --cram
  run is rejected fail-loud`
  > 来源：https://felixkrueger.github.io/Bismark/options/alignment/

### 1.6 bwa-meth 找不到 BAM

- `bwa-meth now outputs sam to stdout. It is up to the user to convert to bam.`（旧 `--prefix` 已移除）
  → 必须自行重定向到 `.sam` 再转 BAM。
- 双端仅支持定向建库：`paired-end reads from the directional protocol (most common)`；非定向/其它协议
  官方未给支持声明。
  > 来源：https://github.com/brentp/bwa-meth

## 2. 甲基化提取

### 2.1 输出文件数量与预期不符

- 默认是 **12 个链特异文件**（`CpG_OT_...`、`CpG_CTOT_...`、`CpG_OB_...`、`CpG_CTOB_...` × 三个 context）。
- 想要 3 个按 context 的文件：加 `--comprehensive`；想要 2 个（CpG / non-CpG）：再加 `--merge_non_CpG`。
  `--merge_non_CpG` 可能产生数亿行。
  > 来源：https://felixkrueger.github.io/Bismark/usage/methylation-extraction/

### 2.2 `--cytosine_report` 报错或结果为空

- 缺 `--genome_folder`：官方明确 `Specifying a genome folder path is mandatory.`，且 `full path only`，
  FastA 后缀须为 `.fa` / `.fasta`。
- 只要 CpG 却拿到海量行：默认已是 CpG context；加 `--CX` 才会输出全部 C（人类 >1.1e9 行）。
  > 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/

### 2.3 排序阶段文件句柄耗尽 / 内存爆掉

- 大量 scaffold：`--scaffolds/--gazillion`（不预先按染色体拆文件，改用 UNIX sort）。
- 内存换速度：`--ample_memory`（人类 chr1 双数组约 16 GB），且 `--ample_memory` **不兼容**
  `--scaffolds/--gazillion`；主排序缓冲用 `--buffer_size`（默认 2G）。
  > 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/

### 2.4 `--multicore` 不加速 bedGraph / cytosine report

- `This option has no bearing on the bismark bedgraph or bismark cov2cyt (genome-wide cytosine
  report) processes.`
  > 来源：https://felixkrueger.github.io/Bismark/options/methylation-extraction/

## 3. 转换效率与非转换过滤

### 3.1 判断能否接受当前转换率

- 官方给的量化判据：`if you see a general methylation of 0.3% in non-CG context over many millions
  of methylation calls, then the bisulfite conversion must have been at least 99.7% efficient.`
- 转换率确实偏低时，官方不建议"减差校正"：
  `Simply subtracting the conversion error from the results doesn't seem to be a great option, as in
  our experience different contexts are affected differently`
- 可选处置：用 `bismark consistency` 剔除完全逃逸转换的 reads，或在解释时带上该噪声水平。
  > 来源：https://felixkrueger.github.io/Bismark/faq/conversion-efficiency/

### 3.2 spike-in 反而"更差"

- 官方提醒：`almost more often than not the spike-ins seem to behave in a slightly weird way, e.g.
  the conversion efficiencies appear to be (slighlty) worse than what one sees for methylation in
  non-CG context` → 记录并继续，不要据此推翻主数据。
  > 来源：https://felixkrueger.github.io/Bismark/faq/conversion-efficiency/

### 3.3 `bismark filter` 把真信号删了

- 只适用于非 CG 甲基化本应极低的物种：`not advisable - and will introduce biases - if you work
  with organisms which exhibit any appreciable levels of non-CG methylation (e.g. most plants)`
- 双端 BAM 必须 R1/R2 相邻（按 name 排序）：`samtools sort -n`
  > 来源：https://felixkrueger.github.io/Bismark/usage/filtering-non-conversion/

## 4. methylKit

### 4.1 内存不足

- 改用 `methylDB`（`methRead(..., dbtype="tabix", dbdir="methylDB")`），底层 bgzip + tabix。
- 注意例外：`select`、`[`、`selectByOverlap` 会退回普通对象。
  > 来源：https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html

### 4.2 检验方法不是自己想要的

- 有重复 → 自动 logistic regression；想强制 Fisher → `pool()` 每组汇成一个样本。
- 想启用过离散校正 → `overdispersion="MN"`，此时自动 F 检验；`test="Chisq"` 可手动指定，
  但 `F` 只能在开启校正时使用。
  > 来源：同上（FAQ / Correcting for overdispersion）

### 4.3 `regionCounts` 输出顺序变了

- 官方：区域会先按染色体和坐标排序再查找重叠，故输出顺序可能与输入不同（数据库对象必须有序）。
  需要自定义顺序时用 `select` / `extract` 按索引重排。
  > 来源：同上（FAQ）

### 4.4 无法用 `processBismarkAln` 读取 local alignment / spliced alignment

- 官方：local alignment 不能用 `processBismarkAln()`，须先用 MethylDackel 或 Bismark 提取器生成
  输入文件；HISAT2 的 spliced alignment 亦未完全支持，同样走提取器路线。
  > 来源：同上（FAQ）

### 4.5 拿 MeDIP / 芯片数据套 methylKit

- 官方：`The package methylKit is designed for analysing methylation data from bisulfite sequencing
  (such as WGBS or RRBS) and as such not designed for affinity based method (like MIRA-Seq, MeDIP)`，
  并指引 MEDIPS；芯片数据 `not officially supported`。
  > 来源：同上（FAQ）

## 5. DSS

| 现象 | 官方处置 | 来源 |
| --- | --- | --- |
| Windows 上并行结果异常/失败 | `we suggest to use ncores=1 on Windows`（依赖 forking） | D |
| 预处理时滤掉了低覆盖 CpG | `No. DSS will take care of the coverage depth information.` | D |
| 输入用 beta 值/甲基化率 | `No. DSS only takes count data.` | D |
| 多因子设计想用 `delta` | `delta is NOT supported`（系数不是甲基化率差） | D |
| DMR 表没有 FDR 列 | 官方解释：区域级 FDR 难以从位点级 p 值可靠估计，故不报 | D |
| 不知道 `areaStat` 什么意思 | `sum of the test statistics of all CpG sites within a DMR`，无直接生物学含义，仅用于排序 | D |
| 想要 DMR 附近基因 | `DSS doesn't provide this functionality ... for example, HOMER.`（或转 genomation） | D |
| RRBS 要不要平滑 | `Smoothing is always recommended, even for RRBS.` | D |
| DMR 阈值怎么定 | `It is very difficulty to select a natural and rigorous threshold ... try different thresholds` | D |

> D = https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html

## 6. bsseq

| 现象 | 官方处置 | 来源 |
| --- | --- | --- |
| `BSmooth()` 报错或结果异常 | 先 `orderBSseq()`：平滑函数假定对象已排序 | S |
| Windows 上 `mc.cores>1` 失败 | `setting mc.cores to a value greater than 1 is not support on MS Windows` | S |
| 全基因组样本内存不足 | HDF5 后端：`read.bismark(..., BACKEND="HDF5Array")` / `saveHDF5SummarizedExperiment()`；或按染色体/样本分块 | S |
| capture BS-seq 平滑后无意义 | 官方：BSmooth 依赖较大区域内的平滑，`may not be useful for a standard capture bisulfite sequencing experiment` | S |
| 想逐位点检验 | `fisherTests()` / `binomialGoodnessOfFit()` / `poissonGoodnessOfFit()` | S |

> S = https://bioconductor.org/packages/release/bioc/vignettes/bsseq/inst/doc/bsseq.html

## 7. MeDIP-seq

| 现象 | 处置 |
| --- | --- |
| 想找 MEDIPS 的可执行命令 | 官方 vignette 仅以 PDF / R Script 发布，本技能无法取得可解析文本；在 R 内执行 `browseVignettes("MEDIPS")` 取原文。**官方文档未提供（本环境）可直接执行的命令** |
| 用单碱基 DML 模型分析 MeDIP | 方向性错误：MeDIP 是富集读数，官方把 MEDIPS 定位为 `calculation of differential coverage between groups of samples`（区域/覆盖度层面） |
| 高 CpG 密度区一律"高甲基化" | 需 CpG 密度 / GC 校正与 input 对照（本技能判据，非官方命令） |

> 来源：https://bioconductor.org/packages/release/bioc/html/MEDIPS.html

## 8. 口径交叉检查（提交前自查）

- [ ] 同一张结果表里没有混入"甲基化率"（0–100%）与"富集 coverage"两种量纲。
- [ ] WGBS/RRBS 的坐标体系一致（Bismark 默认 1-based；`--zero_based` 才 0-based）。
- [ ] 所有 DMR 表都写明：检验方法、是否过离散校正、效应的定义（`difference` / `delta` / `areaStat`）。
- [ ] 若做过 `--ignore*` 或 `bismark filter`，方法学里写明并说明其对覆盖度的影响。
- [ ] MeDIP 部分报告用词为"差异富集区"，不写"差异甲基化率"。
