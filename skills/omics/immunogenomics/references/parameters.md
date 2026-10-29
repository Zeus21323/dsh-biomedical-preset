# 参数表（四部分）

所有默认值、取值、语义逐字来自官方文档，行末给来源 URL。标注「官方未给默认值」的，是文档确实没写，不要凭印象填。

---

# 第一部分：免疫组库（TCR/BCR）

## 1.1 MiXCR `align`

| 参数 | 取值 / 默认 | 说明 | 来源 |
|---|---|---|---|
| `-p, --preset <name>` | 官方 preset 名 | 决定本次及所有下游步骤的关键参数；**必须在 align 指定** | https://mixcr.com/mixcr/reference/mixcr-align/ |
| `-s, --species` | `hsa`/HomoSapiens、`mmu`/MusMusculus、`rat`、`spalax`、`alpaca`、`lamaGlama`、`mulatta`、`fascicularis`，或 IMGT 库物种 | 物种 | 同上 |
| `-b, --library` | 默认 `default` | V/D/J/C 参考库；可用外部 IMGT 库 | 同上 |
| `--trimming-quality-threshold` | 由 preset 决定 | 读段修剪质量阈值；`0` 跳过修剪 | 同上 |
| `--trimming-window-size` | 由 preset 决定 | 修剪窗口 | 同上 |
| `--write-all` | 由 preset 决定 | 写入所有 reads 的比对（含失败） | 同上 |
| `--tag-pattern` / `--tag-pattern-file` | 由 preset 决定 | barcode/UMI 模式 | 同上 |
| `--tag-parse-unstranded` | 由 preset 决定 | 双端是否尝试所有 barcode 组合 | 同上 |
| `--tag-max-budget` | 由 preset 决定 | barcode 允许的错配位预算 | 同上 |
| `--read-id-as-cell-tag` | 由 preset 决定 | 同位置 reads 视作同细胞（αβ/重轻链分 mate 测序） | 同上 |
| `--limit-input <n>` | 无 | 限制处理 reads 数（试跑用） | 同上 |
| `--read-buffer` | 4Mb | FASTQ reader 缓冲 | 同上 |
| `--high-compression` | off | 输出更小、慢 10–25% | 同上 |
| `-O <key=value>` | — | 覆盖 aligner 参数（如 `-OallowPartialAlignments=true`） | 同上 |
| `-M <key=value>` | — | 覆盖 preset 参数 | 同上 |
| `-r/--report`、`-j/--json-report` | 无 | 人读 / 机读报告 | 同上 |
| `-t, --threads` | 无 | 线程数 | 同上 |
| `--assemble-clonotypes-by <gene_features>` | CDR3（preset 可改） | 克隆型定义；align 阶段即可设 mixin | 同上 |
| `--split-clones-by` / `--dont-split-clones-by <gene_type>` | 依 preset | 同序列不同基因是否分开（如按 C 分 isotype） | 同上 |

aligner 级 `-O` 默认（节选，官方列全表）：`saveOriginalReads=false`、`allowPartialAlignments=false`、`allowNoCDR3PartAlignments=false`、`allowChimeras=false`、`minSumScore=120`、`maxHits=5`、`vjAlignmentOrder=VThenJ`、`relativeMinVFR3CDR3Score=0.7`、`readsLayout=Opposite`、`relativeMinVScore=0.7`、`alignmentBoundaryTolerance=5`、`minChimeraDetectionScore=120`、`vjOverlapWindow=3`；合并：`mergerParameters.qualityMergingAlgorithm=MaxSubtraction`、`minimalOverlap=17`、`minimalIdentity=0.9`。来源同上。

## 1.2 MiXCR `refineTagsAndSort`

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `--dont-correct` | 由 preset 决定 | 只按 tag 排序，不纠错 | https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/ |
| `-p, --power <d>` | 由 preset 决定 | 纠错彻底度；越小留下越少错误变体（但可能误改真实变体） | 同上 |
| `-s, --substitution-rate` | 由 preset 决定 | 背景替换率 | 同上 |
| `-i, --indel-rate` | 由 preset 决定 | 背景 indel 率 | 同上 |
| `-q, --min-quality` | 由 preset 决定 | tag 的 Phred33 最低质量 | 同上 |
| `--max-substitutions` / `--max-indels` / `--max-errors` | 由 preset 决定 | 搜索上限 | 同上 |
| `--memory-budget` | 4Gb | 内存预算 | 同上 |
| `--set-whitelist <key=value>` | 无 | 例：`--set-whitelist CELL=preset:737K-august-2016`、`--set-whitelist UMI=file:my_umi_whitelist.txt` | 同上 |
| `--reset-whitelist <tag>` | 无 | 取消白名单，改为无引导纠错 | 同上 |

硬件：内存与唯一 barcode 数成正比，极端可达 32Gb；`--dont-correct` 则无此需求。来源同上。

## 1.3 MiXCR `assemble`

| 参数 / `-O` 键 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `-a, --write-alignments` | 由 preset 决定 | 输出 `.clna`（克隆 + 比对），后续可扩 contig | https://mixcr.com/mixcr/reference/mixcr-assemble/ |
| `--cell-level` | 由 preset 决定 | 在细胞级而非分子级组装；无分子 tag 有细胞 tag 时默认启用 | 同上 |
| `-s, --sort-by-sequence` | 由 preset 决定 | 按序列排序（便于 cloneset 重叠分析） | 同上 |
| `--dont-infer-threshold` | off | 关闭 `minRecordsPerConsensus` 自动推断 | 同上 |
| `--split-clones-by` / `--dont-split-clones-by` | 依 preset | 同 `align` | 同上 |
| `--assemble-clonotypes-by <gene_features>` | 依 preset | 可自定义（如 `FR3+CDR3`、`[V5UTR+L1+L2+FR1,FR3+CDR3]`）；**必须覆盖 CDR3** | 同上 |
| `-OassemblingFeatures` | `CDR3` | clonal sequence 定义 | 同上 |
| `-OminimalClonalSequenceLength` | `12` | 最短 clonal sequence | 同上 |
| `-ObadQualityThreshold` | `20` | 低于此质量视为 bad，延后由 mapper 处理 | 同上 |
| `-OmaxBadPointsPercent` | `0.7` | bad 碱基比例上限，超过直接丢弃；设 `0` 则含 1 个 bad 即丢 | 同上 |
| `-OqualityAggregationType` | `Max` | `Max`/`Min`/`Average`/`MiniMax` | 同上 |
| `-OminimalQuality` | `0` | 克隆每位点最低质量，低于则丢该克隆 | 同上 |
| `-OaddReadsCountOnClustering` | `false` | 是否把子克隆计数累加到 head | 同上 |
| `-OmaximalPreClusteringRatio` | `1.0` | 预聚类吸收阈值 | 同上 |
| `-OseparateByV` / `-OseparateByJ` / `-OseparateByC` | 全 `false` | 同序列不同 V/J/C 是否分开（isotype 分析设 `separateByC=true`） | 同上 |
| `-OcloneClusteringParameters.searchDepth` | `2` | 聚类层数（不含 head） | 同上 |
| `-OcloneClusteringParameters.allowedMutationsInNRegions` | `1` | N 区允许错配，超过则不聚类 | 同上 |
| `-OcloneClusteringParameters.searchParameters` | `twoMismatchesOrIndels` | 可选 `oneMismatch` … `fourMismatchesOrIndels` | 同上 |
| `-OcloneClusteringParameters.clusteringFilter.backgroundSubstitutionRate` | `0.002` | 高质量下的错误概率 | 同上 |
| `-OcloneClusteringParameters.clusteringFilter.backgroundIndelRate` | `0.0002` | 同上（indel） | 同上 |
| `-P` 组（预克隆） | 依 `--cell-level` 不同 | `minTagSuffixShare`、`assembler.minRecordsPerConsensus`、`minRecordSharePerConsensus`、`maxConsensuses` 等 | 同上 |

## 1.4 MiXCR `exportClones`

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `-c, --chains <chains>` | 依 preset | 只导某链（如 `TRA`、`IGH`），fraction 重算 | https://mixcr.com/mixcr/reference/mixcr-export/ |
| `-o, --filter-out-of-frames` | 依 preset | 剔除移码 | 同上 |
| `-t, --filter-stops` | 依 preset | 剔除含终止密码子 | 同上 |
| `--export-productive-clones-only` | off | 只导 productive | 同上 |
| `--split-by-tags <Molecule|Cell|Sample>` | 自动推断 | 按 tag 拆表 | 同上 |
| `--impute-germline-on-export` / `--dont-...` | 由 preset 决定 | 未覆盖区用 germline 小写补 / 只导覆盖区 | 同上 |
| `--no-header`、`--drop-default-fields`、`--prepend-columns`、`--not-covered-as-empty` | off | 表头与列控制 | 同上 |

默认导出列（BCR 全长示例，逐字）：`cloneId, cloneCount, cloneFraction, allVHitsWithScore, allDHitsWithScore, allJHitsWithScore, allCHitsWithScore, allVAlignments…, nSeqFR1, minQualFR1, nSeqCDR1, …, nSeqCDR3, minQualCDR3, nSeqFR4, aaSeqFR1…aaSeqFR4, refPoints, targetSequences, targetQualities`。来源同上。

## 1.5 MiXCR `postanalysis`（多样性与重叠）

| 参数 | 取值 / 默认 | 说明 | 来源 |
|---|---|---|---|
| 子命令 | `individual` / `overlap` | 个体指标 / 克隆集重叠 | https://mixcr.com/mixcr/reference/mixcr-postanalysis/ |
| `--default-downsampling` | `count-[read|TAG]-[auto|min|fixed][-<number>]`、`top-[read|TAG]-<number>`、`cumtop-[read|TAG]-<percent>`、`none` | **官方：不下采样无法做统计比较**；auto 用 Q20 与 0.5×Q20 规则 | 同上 |
| `--default-weight-function` | `read` / `umi` / `cell` / `none` | 克隆型权重 | 同上 |
| `--only-productive` | off | 过滤移码与终止 | 同上 |
| `--drop-outliers` | off | 丢弃低于下采样值的样本 | 同上 |
| `--chains` | `TRA,TRD,TRAD,TRG,IGH,IGK,IGL`（可多选） | 限定链 | 同上 |
| `--metadata` / `--group` | 无 | 样本表；`--group` 做隔离组分别分析 | 同上 |
| `--tables` / `--preproc-tables` | `{outputDir}/{outputFileName}.tsv` | 每 chain×metric 一文件 | 同上 |
| `-O<metric>.downsampling/weightFunction/onlyProductive/dropOutliers` | — | 单指标覆盖 | 同上 |

多样性指标（逐字）：`diversity.observed`、`diversity.shannonWiener`、`diversity.chao1`、`diversity.normalizedShannonWienerIndex`、`diversity.inverseSimpsonIndex`、`diversity.giniIndex`、`diversity.d50`、`diversity.efronThisted`。其它 metric 组：`cdr3metrics.cdr3lenNT/cdr3lenAA/ndnLenNT/addedNNT/strength/hydrophobicity/disorder/volume/charge`、`vUsage/jUsage/isotypeUsage/vjUsage`。来源同上。

## 1.6 TRUST4 `run-trust4`

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `-b` | — | BAM 路径（与 `-1/-2`、`-u` 三选一） | https://github.com/liulab-dfci/TRUST4 |
| `-1` `-2` | — | paired FASTQ | 同上 |
| `-u` | — | single FASTQ | 同上 |
| `-f` | 必需 | V/D/J/C 坐标+序列 fasta（BAM 用 `bcrtcr.fa`；FASTQ 可用 `IMGT+C.fa`） | 同上 |
| `--ref` | 不用（**recommended**） | 带注释参考（IMGT+C.fa） | 同上 |
| `-o` | 由文件前缀推断 | 输出前缀 | 同上 |
| `--od` | `./` | 输出目录 | 同上 |
| `-t` | `1` | 线程 | 同上 |
| `-k` | `9` | contig 索引起始 k-mer | 同上 |
| `--barcode` | 不用 | BAM 字段名或 barcode 文件 | 同上 |
| `--barcodeLevel` | `cell` | `cell` / `molecule` | 同上 |
| `--barcodeWhitelist` | 不用 | 白名单路径 | 同上 |
| `--barcodeTranslate` | 不用 | 两列 tsv/csv（新→旧） | 同上 |
| `--UMI` | 不用 | UMI 文件或 BAM 字段 | 同上 |
| `--readFormat` | 不用 | `[r1|r2|bc|um]:start:end:strand`，逗号分隔多段；`hd` 关键字读 header comment | 同上 |
| `--repseq` | 不设 | bulk 非 UMI 的 TCR-seq/BCR-seq 数据 | 同上 |
| `--contigMinCov` | `0` | 低于该覆盖度的 contig 丢弃 | 同上 |
| `--minHitLen` | auto | 有效重叠最短长度 | 同上 |
| `--mateIdSuffixLen` | 不用 | read id mate 后缀长度 | 同上 |
| `--skipMateExtension` | 不设 | 不用 mate 信息延伸（SMART-seq 用） | 同上 |
| `--skipReadRealign` | 不设 | 注释阶段不重比对（省时） | 同上 |
| `--cgeneEnd` | `200` | 跳过 C 基因前 200bp 之后的 reads | 同上 |
| `--abnormalUnmapFlag` | 不设 | BAM 中非 concordant 未比对对的 flag | 同上 |
| `--assembleWithRef` | 不设 | 用 `--ref` 做组装（默认用 `-f`） | 同上 |
| `--noExtraction` | 不设 | 跳过候选 reads 提取 | 同上 |
| `--outputReadAssignment` | 不设 | 输出 `*_assign.out` | 同上 |
| `--stage` | `0` | 0 起始 / 1 组装 / 2 注释 / 3 报告 | 同上 |
| `--clean` | `0` | 0 不清 / 1 清中间 / 2 只留 AIRR | 同上 |

辅助脚本：`BuildImgtAnnot.pl <Species>`、`BuildDatabaseFa.pl reference.fa annotation.gtf bcr_tcr_gene_name.txt`（人用仓库内 `human_vdjc.list`）、`trust-smartseq.pl -1 list1 -2 list2 -t 8 -f ... --ref ... -o TRUST`、`trust-simplerep.pl trust_cdr3.out`、`annotator -f ... -a input.fa --fasta -t 8 --needReveserComplement --noImpute --outputFormat 1`。来源同上。

`trust_cdr3.out` 字段：`consensus_id, index_within_consensus, V_gene, D_gene, J_gene, C_gene, CDR1, CDR2, CDR3, CDR3_score, read_fragment_count, CDR3_germline_similarity, complete_vdj_assembly`；`CDR3_score` 已 /100（`1.00` 最高，`0.01` = 补齐序列）。来源同上。

---

# 第二部分：MHC 结合预测与 HLA 分型

## 2.1 NetMHCpan-4.1（class I）

| 项 | 官方值 | 来源 |
|---|---|---|
| 输入类型 | `Fasta` / `Peptide` | https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ |
| 字母表 | `A C D E F G H I K L M N P Q R S T V W Y` + `X`(unknown)，区分大小写；其他符号转 `X` | 同上 |
| 序列限制 | ≤500 条/次；每条 ≥8 aa 且 ≤20,000 aa | 同上 |
| 等位限制 | ≤20 个 MHC/次；名单见 `MHC_allele_names.txt` / `allele.list` | 同上 |
| 肽长 | 可选 8/9/10/11/12/13/14mer（可多选，`Fasta` 模式） | 同上 |
| 物种/loci | HLA-A/B/C/E/G 超型，Patr/Mamu/SLA/H-2/Gogo/BoLA/DLA/EQCA | 同上 |
| strong binder 阈值 | `%Rank` 默认 **0.5** | 同上 |
| weak binder 阈值 | `%Rank` 默认 **2** | 同上 |
| 过滤阈值 | 填 `-99` 打印全部 | 同上 |
| 判据 | "Strong binders are defined as having %rank<0.5, and weak binders with %rank<2. We advise to select candidate binders based on %Rank rather than Score" | 同上（Output format） |
| 输出列 | `Pos, HLA, Peptide, Core, Of, Gp, Gl, Ip, Il, Icore, Identity, Score_EL, Rnk_EL, BindLevel` | 同上 |
| standalone | 学术下载入口 / 商业联系 `health-software@dtu.dk`；CLI README 在包内，**公开页无命令** | 同上（PORTABLE VERSION） |

## 2.2 NetMHCIIpan-4.3（class II）

| 项 | 官方值 | 来源 |
|---|---|---|
| strong binder 阈值 | `%Rank` 默认 **1%** | https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/ |
| weak binder 阈值 | `%Rank` 默认 **5%** | 同上 |
| 输出列 | `Pos, MHC, Peptide, Of, Core, Core_Rel, Inverted, Identity, Score_EL, %Rank_EL, Exp_bind, Score_BA, Affinity(nM), %Rank_BA, BindLevel` | 同上 |
| `Core_Rel` | 集合中选中该 orientation 的网络里、同时选中该 core offset 的比例 | 同上 |
| `Inverted` | 1 = 肽反向结合（集合多数投票），默认仅 HLA-DP 预测反向 | 同上 |
| loci 覆盖 | DR / DQ / DP 三 locus（4.3 的主要更新点） | 同上（摘要） |

## 2.3 OptiType 1.5.0

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `-i, --input` | — | FASTQ 或 BAM，可重复给（双端给两次） | https://github.com/FRED-2/OptiType |
| `-d/--dna` / `-r/--rna` | `--dna` | 数据类型 | 同上 |
| `-o, --outdir` | 必需 | 输出目录 | 同上 |
| `-p, --prefix` | 时间戳 | 输出前缀 | 同上 |
| `-b, --beta` | 文档未给默认数值（范围 0.0–0.1） | 纯合检测参数 | 同上 |
| `-e, --enumerate` | 文档未给默认 | 枚举解的数量 | 同上 |
| `--solver` | `config.ini` 中设定（示例 `glpk`） | `glpk`/`cbc`/`cplex` | 同上 |
| `--razers3` | `config.ini` | RazerS3 路径 | 同上 |
| `--threads` | `[mapping] threads`（示例 4） | 比对线程 | 同上 |
| `-c, --config` | — | config.ini 路径 | 同上 |
| `[behavior] unpaired_weight` | `0` | 非配对 reads 权重（0–1） | 同上 |
| 输出 | `*_result.tsv`（`A1 A2 B1 B2 C1 C2 Reads Objective`）、`*_coverage_plot.pdf` | — | 同上 |

## 2.4 arcasHLA

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `-g, --genes` | 由调用给定 | 逗号分隔，如 `A,B,C,DPB1,DQB1,DQA1,DRB1` | https://github.com/RabadanLab/arcasHLA |
| `-p, --population` | `Prior` | `asian_pacific_islander`/`black`/`caucasian`/`hispanic`/`native_american`/`prior` | 同上 |
| `--min_count` | `75` | 基因最低 reads 数 | 同上 |
| `--tolerance` | `10e-7` | 转录本定量收敛容差 | 同上 |
| `--max_iterations` | `1000` | 迭代上限 | 同上 |
| `--drop_iterations` | paired `10` / single `4` | 丢弃低支持等位前的迭代数 | 同上 |
| `--drop_threshold` | `0.1` | 保留等位所需的最低丰度占比 | 同上 |
| `--zygosity_threshold` | `0.15` | 次/主等位非共享计数比，判杂合 | 同上 |
| `--single` | False | 单端 | 同上 |
| `-l, --avg` / `-s, --std` | `200` / `20` | 单端片段长度与标准差 | 同上 |
| extract 专属 | `--single`、`--unmapped`（推荐：比对器把多重比对标为 unmapped 时）、`--keep_files` | — | 同上 |
| 参考 | `./arcasHLA reference --version 3.24.0` / `--update` | 复现旧结果必须锁版本 | 同上 |

## 2.5 HLA*LA

| 参数 | 说明 | 来源 |
|---|---|---|
| `--BAM <indexed.bam|cram>` | 必须已建索引 | https://github.com/DiltheyLab/HLA-LA |
| `--graph PRG_MHC_GRCh38_withIMGT` | 参考图（B37/B38 通用，不需随 BAM 改） | 同上 |
| `--sampleID <id>` | 每样本唯一；输出到 `../working/<id>/hla/` | 同上 |
| `--maxThreads <n>` | 线程 | 同上 |
| `--workingDir <dir>` | 覆盖工作目录（集群安装建议删除 paths.ini 的 workingDir） | 同上 |
| `--samtools_T <ref.fa>` | CRAM 报 `Unable to fetch reference` 时必需 | 同上 |
| `--longReads ont2d|pacbio` | 长读长，**仍输出 G 组**，实验性 | 同上 |
| `--action prepareGraph --PRG_graph_dir <dir>` | 建图索引，数小时、最多约 40G 内存 | 同上 |
| 输出列 | `Locus, Chromosome, Allele(G 组), Q1, Q2(忽略), AverageCoverage, CoverageFirstDecile, MinimumCoverage, proportionkMersCovered, LocusAvgColumnError` | 同上 |

## 2.6 新抗原流程阈值（可核查部分）

| 步骤 | 阈值/判据 | 来源 |
|---|---|---|
| class I 结合 | `%Rank_EL < 0.5`（strong）/ `< 2`（weak） | NetMHCpan-4.1 页 |
| class II 结合 | `%Rank < 1`（strong）/ `< 5`（weak） | NetMHCIIpan-4.3 页 |
| 等位完整性 | 6 位分型患者 class I 需 6 个等位、class II 需 8 个；单次 ≤20 等位 | NetMHCpan-4.1 页 |
| 变异/肽段/表达 | **官方文档未提供可直接执行的命令** → 只写判据：PASS+VAF、mutant vs wild-type 对照、肿瘤表达过滤 | — |

---

# 第三部分：免疫浸润解卷积

## 3.1 CIBERSORTx

| 项 | 官方公开信息 | 来源 |
|---|---|---|
| 可执行命令 | **官方文档未提供可直接执行的命令**（站点仅 Home/About/Contact/Register 与登录框；About 需登录） | https://cibersortx.stanford.edu/ |
| 申请方式 | `register.php` 注册并登录；站点声明 Non-Commercial Terms of Use | 同上 |
| 定位 | 估计混合细胞群中各细胞类型丰度；EcoTyper 为其扩展 | 同上 |

任何选项名、文件名、参数值都必须登录后按官方页面文案记录；不写未核验参数。

## 3.2 quanTIseq

| 参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `--inputfile` | 必需 | tab 分隔、无表头、三列（sample / fq1 / fq2 或 `None`）；`decon` 模式改为 TPM 矩阵（首列 symbol、首行样本、非 log） | https://icbi.i-med.ac.at/software/quantiseq/doc/ |
| `--outputdir` | 必需 | 不存在则创建 | 同上 |
| `--pipelinestart` | `preproc` | `preproc` / `expr` / `decon` | 同上 |
| `--tumor` | `FALSE` | 肿瘤数据官方"highly recommend"设 `TRUE` | 同上 |
| `--arrays` | `FALSE` | 芯片数据（自动使 `--rmgenes`=`none`） | 同上 |
| `--method` | `lsei` | `hampel`/`huber`/`bisquare`/`lsei`；官方推荐 `lsei`；**只有 lsei 给 "other"** | 同上 |
| `--mRNAscale` | `TRUE` | 按细胞类型 mRNA 含量缩放，官方建议保持 TRUE | 同上 |
| `--rmgenes` | `default` | `none`/`default`/文件路径；RNA-seq 用 default、芯片用 none | 同上 |
| `--totalcells` | 不设 | 细胞密度文件（样本 ID + 每 mm² 总细胞数），用于换算密度 | 同上 |
| `--rawcounts` | `FALSE` | 额外输出 counts | 同上 |
| `--prefix` | `quanTIseq` | 输出前缀 | 同上 |
| `--threads` | `1` | 官方注：kallisto 结果随线程数略有差异 | 同上 |
| `--phred` | `33` | `33`/`64` | 同上 |
| `--adapterSeed` / `--palindromeClip` / `--simpleClip` | `2` / `30` / `10` | Trimmomatic 接头识别 | 同上 |
| `--trimLead` / `--trimTrail` / `--minLen` / `--crop` | `20` / `20` / `36` / `10000` | Trimmomatic 修剪 | 同上 |
| `--avgFragLen` / `--sdFragLen` | `50` / `20` | 单端 kallisto 片段长度 | 同上 |
| 输出 | `prefix_cell_fractions.txt`、`prefix_gene_tpm.txt`、`prefix_gene_count.txt`（需 `--rawcounts=TRUE`） | — | 同上 |
| 细胞类型 | `B.cells, Macrophages.M1, Macrophages.M2, Monocytes, Neutrophils, NK.cells, T.cells.CD4, T.cells.CD8, Tregs, Dendritic.cells, Other`；**总 CD4 = T.cells.CD4 + Tregs** | — | 同上 |

## 3.3 EPIC

| 参数 | 说明 | 来源 |
|---|---|---|
| `bulk=` | TPM 或 RPKM 矩阵（必需） | https://github.com/GfellerLab/EPIC |
| `reference=` | 自定义参考细胞谱 list | 同上 |
| `mRNA_cell=` / `mRNA_cell_sub=` | 每细胞 mRNA 量（覆盖默认） | 同上 |
| `sigGenes=` | 自定义 signature 基因 | 同上 |
| 输出 | list：`mRNAProportions`、`cellFractions` + goodness-of-fit data.frame | 同上 |
| 判据 | 报细胞比例用 `cellFractions`；in-silico（scRNA-seq 重建）bulk 用 `mRNAProportions` | 同上（FAQ） |
| `other cells` | 无参考谱的剩余细胞（肿瘤多为癌细胞，也可能含基质/上皮） | 同上（FAQ） |
| 许可 | 学术非商业免费；商业用途需另行授权 | 同上（License） |

## 3.4 ABIS

| 项 | 内容 | 来源 |
|---|---|---|
| 可执行命令 | **官方文档未提供可直接执行的命令**（原包文档入口未取到） | — |
| 官方封装文档入口 | `deconvolute_abis` | https://omnideconv.org/immunedeconv/reference/deconvolute_abis.html |
| 判据 | allele-specific 解卷积，需 HLA 分型输入；结果与 CIBERSORTx/quanTIseq/EPIC 不同源，禁止混图比绝对值 | — |

---

# 第四部分：CyTOF / 流式（CATALYST + FlowSOM）

| 函数/参数 | 默认 | 说明 | 来源 |
|---|---|---|---|
| `prepData(x)` | — | FCS/flowSet/flowFrame → SCE；非质量通道移入 `int_colData` | https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html |
| `transform` | `TRUE` | arcsinh 变换后存 `exprs` | 同上 |
| `cofactor` | `5` | arcsinh 的 cofactor | 同上 |
| `by_time` | `TRUE` | 按 `$BTIM` 排序拼接 | 同上 |
| `normCytof(x, beads=, k=, assays=, overwrite=)` | `beads="dvs"`, `k=50`, `overwrite=FALSE` | bead 归一化；结果写 `normcounts`/`exprs` | 同上 |
| `beads` | `"dvs"`=140/151/153/165/175；`"beta"`=139/141/159/169/175；或自定义质量向量 | bead 通道选择 | 同上 |
| bead 修剪 | `median±5mad` | 低/高信号剔除，`trim` 可调 | 同上 |
| `assignPrelim(x, bc_key)` | — | 初步 barcode 分配，delta 计算 | 同上 |
| `estCutoffs(x)` | — | logistic 拟合加权估计分离阈值（`metadata(sce)$sep_cutoffs`） | 同上 |
| `applyCutoffs(x)` | — | 应用阈值；未分配为 `bc_id == 0` | 同上 |
| `computeSpillmat(x)` | — | 单抗体染色样本 → 溢出矩阵 `metadata(sce)$spillover_matrix` | 同上 |
| `compCytof(x, sm, method=, overwrite=)` | `method="nnls"`，官方示例 `overwrite=FALSE` | 补偿；结果写 `compcounts`/`compexprs` | 同上 |
| `cluster(x, features=, xdim=, ydim=, maxK=, seed=)` | 官方示例 `features="type"`, `xdim=10`, `ydim=10`, `maxK=20`, `seed=1` | FlowSOM 聚类（K=xdim×ydim）+ ConsensusClusterPlus 元聚类；写 `cluster_id` | https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html |
| `runDR(x, dr=, cells=, features=)` | 官方示例 `dr="UMAP"`, `cells=500`, `features="type"` | 降维；先 `set.seed()` 保证可复现 | 同上 |
| `mergeClusters` | — | 手工合并 cluster | 同上 |
| DA/DS | diffcyt（vignette 第 7 节） | 差异丰度/差异状态 | 同上 |
| `sce2fcs(x, split_by=)` | — | 按 barcode 拆回 flowSet 导出 FCS | 同上 |
| FlowSOM 安装 | `BiocManager::install("FlowSOM")`，release 2.20.0 | SOM + MST 可视化 | https://bioconductor.org/packages/release/bioc/html/FlowSOM.html |

判据：`features="type"` 决定参与聚类的 marker，**state marker 不能进聚类**（否则差异状态分析自证）；`normCytof(overwrite=FALSE)` 与 `compCytof(overwrite=FALSE)` 必须保留原始数据，否则批次回溯不可行。
