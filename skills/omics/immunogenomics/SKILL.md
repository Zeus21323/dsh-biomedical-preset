---
name: immunogenomics
description: |
  Immunogenomics workflow reference: TCR/BCR immune repertoire reconstruction (MiXCR, TRUST4),
  MHC class I/II binding prediction (NetMHCpan-4.1, NetMHCIIpan-4.3), HLA typing (OptiType, arcasHLA, HLA*LA),
  neoantigen candidate screening, bulk immune deconvolution (CIBERSORTx, quanTIseq, EPIC, ABIS),
  and CyTOF/flow cytometry preprocessing (CATALYST, FlowSOM). Every command is quoted from official
  documentation with its source URL; where official docs give no runnable command, only the workflow
  and decision criteria are stated. 中文触发词：免疫组学、TCR、BCR、免疫组库、MiXCR、TRUST4、MHC 结合、新抗原、免疫浸润、CIBERSORTx、CyTOF。
category: omics
tags: immunogenomics, tcr, bcr, mhc, neoantigen, deconvolution
---

# 免疫组学（Immunogenomics）

本技能把免疫组学五类分析拆成"可选路线 → 官方命令 → 判据"三段式。**所有命令、参数、默认值均逐字来自官方文档，并在命令后附来源 URL**；官方文档没有可直接执行命令的部分，只写流程与判据，不给自造代码。

## 适用与边界

| 场景 | 入口 |
|---|---|
| 有 TCR/BCR 富集或非富集 RNA-seq，要克隆型表 | 一、免疫组库 |
| 已有 HLA 分型 + 突变/肽段，要结合亲和力 | 二、MHC 结合预测 |
| 有肿瘤 WES/RNA-seq，要候选新抗原 | 二.3 新抗原预测 |
| 有 bulk 表达矩阵，要免疫细胞比例 | 三、免疫浸润解卷积 |
| 有 CyTOF/FCS 原始文件 | 四、CyTOF / 流式 |

三条硬性前提（贯穿全技能）：

1. **先定参考版本再跑流程**。MiXCR 参考库、IMGT/HLA 版本、arcasHLA 参考版本不一致，结果不可跨批次比较（见五、质控）。
2. **免疫组库的"克隆型"是定义出来的，不是测出来的**。克隆型由 `assemblingFeatures`（默认 CDR3）决定，换定义就换数字。
3. **bulk 解卷积输出的是相对比例**，不是绝对细胞数；跨样本比较只在同一 signature matrix、同一方法、同一归一化下成立。

## 快速路由（决策树）

```
输入是什么？
├─ FASTQ/BAM（免疫组库测序或 RNA-seq）
│   ├─ 有 UMI / 10x barcode / 试剂盒方案 ──→ MiXCR（选 preset，`mixcr analyze`）
│   ├─ 非富集 bulk RNA-seq，只要 CDR3 克隆型 ──→ MiXCR rna-seq preset（需组装 contig）
│   └─ 非富集 bulk/scRNA-seq，要 AIRR 表与 barcode 级配对 ──→ TRUST4
├─ 已有 BAM/FASTQ，要 HLA 分型
│   ├─ RNA-seq ──→ arcasHLA（extract → genotype）
│   ├─ WES/WGS（DNA）──→ OptiType
│   └─ WGS/WES + 群体参考图，要 G 组分辨率 ──→ HLA*LA
├─ 已有 HLA 等位 + 肽段/突变
│   ├─ class I ──→ NetMHCpan-4.1
│   └─ class II ──→ NetMHCIIpan-4.3
├─ 已有 bulk 表达矩阵
│   ├─ 要 22 种免疫细胞 + 自定义 signature ──→ CIBERSORTx（需注册登录）
│   ├─ 要 10 种细胞 + "other" 分数，从 FASTQ 起 ──→ quanTIseq
│   ├─ 要 immune/stromal/endothelial/other ──→ EPIC
│   └─ 要 allele-specific（HLA 相关）──→ ABIS
└─ CyTOF/FCS
    ├─ 归一化/去条码/补偿 ──→ CATALYST（preprocessing vignette）
    └─ 聚类/差异 ──→ CATALYST cluster() + FlowSOM，DA/DS 用 diffcyt
```

## 一、免疫组库（TCR/BCR）

### 1.1 两条路线怎么选

| 维度 | bulk RNA-seq 路线 | scRNA-seq 路线 |
|---|---|---|
| 输入 | 非富集 bulk FASTQ/BAM | 10x 5' GEX 或 VDJ 富集 FASTQ/BAM |
| MiXCR preset | `rna-seq`（generic，需 `--assemble-longest-contigs`） | `10x-sc-xcr-vdj`、`10x-sc-5gex` |
| TRUST4 | `-b` BAM 或 `-1/-2` FASTQ，`--ref` 必给 | 同上 + `--barcode`/`--UMI`/`--barcodeWhitelist` |
| 克隆型丰度单位 | reads（或 UMI） | cell barcode 数 / UMI 数 |
| 主要偏差 | 表达量偏倚、3'/5' 偏好 | 细胞捕获效率、环境 RNA |

判据：bulk 数据没有 UMI 时，克隆型丰度以 reads 计，**不能跨样本直接比多样性**，必须先按 reads 降采样（见 1.4）。scRNA-seq 数据要报"有多少细胞带配对链"，而不是只报克隆型数。

### 1.2 MiXCR 官方流程

MiXCR 的 preset 是"预配置步骤的 YAML 列表"，`analyze` 命令一次跑完；同一条流程也可分步执行，**preset 只在 `align` 指定一次，后续步骤自动沿用**：

```bash
mixcr align --preset 10x-vdj-bcr --species hsa \
    sample1_R1.fastq.gz sample1_R2.fastq.gz sample1_result.vdjca
mixcr refineTagsAndSort sample1_result.vdjca sample1_result.refined.vdjca
mixcr assemble sample1_result.refined.vdjca sample1_result.clns
mixcr exportClones sample1_result.clns sample1_result.tsv
```
来源：https://mixcr.com/mixcr/reference/overview-presets/ （原文示例含 `assemblePartial`、`assembleContigs` 两步；完整六步见该页"Presets can be used with mixcr analyze command"一节）

一次跑完（推荐，避免漏步骤）：

```bash
mixcr analyze <preset-name> sample_R1.fastq.gz sample_R2.fastq.gz sample_result
```
来源：https://mixcr.com/mixcr/reference/overview-built-in-presets/

**bulk RNA-seq（非富集 shotgun）**：

```bash
mixcr analyze rna-seq \
    --species hsa \
    --assemble-longest-contigs \
      input_R1.fastq.gz \
      input_R2.fastq.gz \
      result
```
官方说明：`rna-seq` preset 用于 "Non-enriched fragmented (shotgun) RNA-Seq data"，且 **`--species` 与 `--assemble-contigs-by`（或 `--assemble-longest-contigs`）为必填**。若只想保留覆盖某区域的克隆，用 `--assemble-contigs-by VDJRegion` 代替 `--assemble-longest-contigs`。
来源：https://mixcr.com/mixcr/reference/overview-built-in-presets/ （Generic data → RNA-Seq data）

**scRNA-seq（10x）**：`10x-sc-xcr-vdj`（VDJ 富集）与 `10x-sc-5gex`（非富集 5' GEX，从 cDNA 库里挖 TCR/BCR）都**必须给 `--species`**：

```bash
mixcr analyze 10x-sc-xcr-vdj --species hsa sample_R1.fastq.gz sample_R2.fastq.gz sample_result
```
来源：https://mixcr.com/mixcr/reference/overview-built-in-presets/ （10xGenomics 一节）

**物种与建库方案对应关系**（`align` 的 `-s/--species`）：`hsa`(HomoSapiens)、`mmu`(MusMusculus)、`rat`、`spalax`、`alpaca`、`lamaGlama`、`mulatta`、`fascicularis`，或 IMGT 库中的任意物种；参考库用 `-b/--library`，默认 `default`。
来源：https://mixcr.com/mixcr/reference/mixcr-align/

其余官方 preset（与建库方案一一对应）：`milab-human-rna-tcr-umi-multiplex`、`milab-human-rna-ig-umi-multiplex`、`milab-human-dna-tcr-multiplex`、`miltenyi-human-rna-tcr-profiling`、`neb-human-rna-xcr-umi-nebnext`、`cellecta-human-rna-xcr-umi-drivermap-air`、`qiaseq-tcr`、`takara-hsa-bcr`、`takara-mmu-tcr`、`exome-seq`、`generic-amplicon`。完整清单与每个 preset 的必填 mixin 见来源页。
来源：https://mixcr.com/mixcr/reference/overview-built-in-presets/

**无现成 preset 时**用 `generic-amplicon`，官方要求指定 Species / Material type / 左右比对边界：

```bash
mixcr analyze generic-amplicon \
    --species mmu \
    --rna \
    --floating-left-alignment-boundary \
    --floating-right-alignment-boundary C \
      sample_R1.fastq.gz \
      sample_R2.fastq.gz \
      sample_result
```
来源：https://mixcr.com/mixcr/reference/overview-presets/

四步日志与判据（官方章节标题即判据）：
- `align`：产出 `.vdjca` + 报告；报告含 reads 数、比对率、chimera 剔除量。**先看报告再往下走**。
- `refineTagsAndSort`：修 barcode 测序/PCR 错误并排序，"corrects artificial diversity caused by errors in barcodes"。开 `--dont-correct` 则只排序。内存与唯一 barcode 数成正比，极端情况需 32 Gb。
- `assemble`：产出 `.clns`（或 `-a` 的 `.clna`），含质量纠错、聚类纠错、UMI/cell barcode 定向纠错；`assemblingFeatures` 必须覆盖 CDR3。
- `exportClones`：出 TSV，默认列含 `cloneId/cloneCount/cloneFraction/allVHitsWithScore/.../nSeqCDR3/aaSeqCDR3`。
来源：https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/ ；https://mixcr.com/mixcr/reference/mixcr-assemble/ ；https://mixcr.com/mixcr/reference/mixcr-export/

### 1.3 TRUST4 官方用法

安装（官方三种）：`make` 源码编译、`conda install -c bioconda trust4`、`docker pull quay.io/biocontainers/trust4:<tag>`。
来源：https://github.com/liulab-dfci/TRUST4

必需参考（`-f` 与 `--ref` 是两件事，别混）：

```bash
perl BuildImgtAnnot.pl Homo_sapien > IMGT+C.fa
perl BuildDatabaseFa.pl reference.fa annotation.gtf bcr_tcr_gene_name.txt > bcrtcr.fa
```
官方说明：`--ref` 为带注释的 IMGT 序列（推荐给）；`-f` 需要"基因坐标 + 序列"——BAM 输入必须用 `BuildDatabaseFa.pl` 生成的 `bcrtcr.fa`（含基因组坐标），FASTQ 输入可直接用 `IMGT+C.fa`。
来源：https://github.com/liulab-dfci/TRUST4 （"Practical notes"一节）

最小可跑示例（BAM 输入，官方 example）：

```bash
./run-trust4 -b example/example.bam -f hg38_bcrtcr.fa --ref human_IMGT+C.fa
```
来源：https://github.com/liulab-dfci/TRUST4 （"Example"一节）

10x 非富集数据（官方给出的典型写法，`--readFormat` 指定 barcode 出现在 read1 前 16 bp）：

```bash
run-trust4 -f hg38_bcrtcr.fa --ref human_IMGT+C.fa \
  -u path_to_10X_fastqs/*_R2_*.fastq.gz \
  --barcode path_to_10X_fastqs/*_R1_*.fastq.gz \
  --readFormat bc:0:15 \
  --barcodeWhitelist cellranger_folder/cellranger-cs/VERSION/lib/python/cellranger/barcodes/737K-august-2016.txt
```
来源：https://github.com/liulab-dfci/TRUST4 （"10X Genomics data and barcode-based single-cell data"一节）

`run-trust4` 参数（逐字，`[OPTIONS]` 全表）：`-b`（BAM）、`-1/-2`（paired FASTQ）、`-u`（single FASTQ）、`-f`（V/D/J/C 坐标+序列）为必需；可选 `--ref`、`-o`、`--od`、`-t`（默认 1）、`-k`（默认 9）、`--barcode`、`--barcodeLevel`（默认 cell）、`--barcodeWhitelist`、`--barcodeTranslate`、`--UMI`、`--readFormat`、`--repseq`、`--contigMinCov`（默认 0）、`--minHitLen`、`--mateIdSuffixLen`、`--skipMateExtension`、`--skipReadRealign`、`--cgeneEnd`（默认 200）、`--abnormalUnmapFlag`、`--assembleWithRef`、`--noExtraction`、`--outputReadAssignment`、`--stage`（0-3）、`--clean`（0/1/2，默认 0）。
来源：https://github.com/liulab-dfci/TRUST4 （"Usage"一节）

输出与判据：
- `trust_cdr3.out`：`consensus_id | index_within_consensus | V_gene | D_gene | J_gene | C_gene | CDR1 | CDR2 | CDR3 | CDR3_score | read_fragment_count | CDR3_germline_similarity | complete_vdj_assembly`
- `CDR3_score` 已除以 100：`1.00` 为最高分，`0.01` 表示 CDR3 为补齐（imputed）序列 → **补齐的 CDR3 不能当真实克隆型做多样性统计**。
- `trust_report.tsv`：`read_count | frequency | CDR3_dna | CDR3_amino_acids | V | D | J | C | consensus_id | consensus_id_complete_vdj`；frequency 对 IG 与 TR 分别归一。
- `trust_airr.tsv` 为 AIRR 格式，下游做 AIRR 兼容分析优先用它。
来源：https://github.com/liulab-dfci/TRUST4 （"Input/Output"一节）

只要 CDR3 汇总表时可单独跑：`perl trust-simplerep.pl trust_cdr3.out > trust_report.out`；只做注释时用 `./annotator -f human_IMGT+C.fa -a input.fa --fasta -t 8 --needReveserComplement --noImpute --outputFormat 1 > annotation.tsv`（注意 `--noImpute`：不做补齐，与新抗原/多样性分析配合更安全）。
来源：https://github.com/liulab-dfci/TRUST4 （"Simple report"、"Annotation only"一节）

### 1.4 克隆型定义与多样性指标

- **克隆型定义**：MiXCR 用 `-OassemblingFeatures`（默认 `CDR3`）定义 clonal sequence；`--split-clones-by <gene_type>` 让"同一序列不同基因"不合并，`--dont-split-clones-by` 反向。`-OseparateByV/J/C` 控制同序列不同 V/J/C 是否分开（默认全 false）。
  来源：https://mixcr.com/mixcr/reference/mixcr-assemble/
- **多样性必须先在统一下采样后算**：官方原文 "Downsampling is a required procedure without which it is not possible to make a statistical comparisons between datasets"。下采样三型：`count-<tag>-(auto|min|fixed)[-<number>]`、`top-<tag>-<number>`、`cumtop-<tag>-<percent>`，另有 `none`；weight function 四选一：`read`/`umi`/`cell`/`none`。
- **官方多样性指标名**（`mixcr postanalysis`，逐字）：`diversity.observed`、`diversity.shannonWiener`、`diversity.chao1`、`diversity.normalizedShannonWienerIndex`、`diversity.inverseSimpsonIndex`、`diversity.giniIndex`、`diversity.d50`、`diversity.efronThisted`；另有 CDR3 指标（`cdr3metrics.cdr3lenNT`、`cdr3lenAA`、`ndnLenNT`、`strength`、`hydrophobicity`、`disorder`、`volume`、`charge`）与 segment usage（`vUsage`、`jUsage`、`isotypeUsage`、`vjUsage`）。
- 表格式导出：`mixcr postanalysis individual ... --tables <path.tsv|csv>`，每个 chain/指标单独一个文件：`{dir}/{fileName}.{metric}.{chain}.(tsv|csv)`。
  来源：https://mixcr.com/mixcr/reference/mixcr-postanalysis/

判据：`observed` 受测序深度强烈影响，只在同深度下比；`chao1`/`efronThisted` 是 richness 外推，样本 reads 太少时不稳定；`giniIndex`/`d50` 反映克隆集中度，是"克隆扩增"最稳的读数。

## 二、MHC 结合预测

### 2.1 HLA 分型（三个官方工具，各自输入不同）

**OptiType 1.5.0**（DNA/RNA 短读长，ILP 求解，4-digit）：

```bash
pip install optitype
optitype check-deps
optitype run -i reads_1.fastq -i reads_2.fastq --dna -o results/
optitype run -i sample.fastq --rna -o results/
optitype run -i mapped.bam --dna -o results/
```
依赖：RazerS3 + 至少一个 ILP solver（`glpk`/`cbc`/`cplex`）。输出 `*_result.tsv`（列：`A1 A2 B1 B2 C1 C2 Reads Objective`）与 `*_coverage_plot.pdf`。关键选项：`-b/--beta`（0.0-0.1 纯合检测）、`-e/--enumerate`、`--solver`、`--threads`、`-c/--config`；`optitype init-config -o config.ini` 生成配置（`[ilp] solver=glpk`、`[behavior] unpaired_weight=0`）。
来源：https://github.com/FRED-2/OptiType

**arcasHLA**（RNA-seq 首选，Kallisto + EM，输出 6 位等位）：

```bash
conda install arcas-hla -c bioconda -c conda-forge
./arcasHLA reference --version 3.24.0
./arcasHLA extract sample.bam -o out -t 8 -v
./arcasHLA genotype out/sample.extracted.1.fq.gz out/sample.extracted.2.fq.gz -g A,B,C,DPB1,DQB1,DQA1,DRB1 -o out -t 8 -v
./arcasHLA partial out/test.extracted.1.fq.gz out/test.extracted.2.fq.gz -g A,B,C,DPB1,DQB1,DQA1,DRB1 -G out/test.genotype.json -o out -t 8 -v
```
判据相关默认值：`--min_count 75`（基因最低 reads）、`--zygosity_threshold 0.15`（次等位/主等位比值判杂合）、`--drop_threshold 0.1`、`--drop_iterations`（paired 10 / single 4）、`-p/--population`（默认 `Prior`，可选 `asian_pacific_islander/black/caucasian/hispanic/native_american`）。输出 `sample.genotype.json`、`sample.partial_genotype.json`、`sample.alignment.p`。多 `-G` 前必须先跑 `genotype`。
来源：https://github.com/RabadanLab/arcasHLA

**HLA*LA**（WGS/WES + 群体参考图，G 组分辨率）：

```bash
../bin/HLA-LA --action prepareGraph --PRG_graph_dir ../graphs/PRG_MHC_GRCh38_withIMGT
./HLA-LA.pl --BAM /path/to/indexed.bam --graph PRG_MHC_GRCh38_withIMGT --sampleID [SAMPLE_ID] --maxThreads 7
```
主输出 `../working/[SAMPLE_ID]/hla/R1_bestguess_G.txt`，列为 `Locus / Chromosome / Allele / Q1 / Q2 / AverageCoverage / CoverageFirstDecile / MinimumCoverage / proportionkMersCovered / LocusAvgColumnError`。长读长加 `--longReads ont2d|pacbio`；CRAM 报 `Unable to fetch reference` 时加 `--samtools_T <ref.fa>`；BAM/CRAM 必须已建索引。
来源：https://github.com/DiltheyLab/HLA-LA

判据：**分型结果必须互相校验**。OptiType 只给 class I 的 A/B/C，arcasHLA 给 class II，HLA*LA 给 G 组。若三种方法在同一样本上给不出同一组 A/B/C，先查 BAM 的参考基因组版本与 IMGT 版本，而不是继续做结合预测。

### 2.2 NetMHCpan-4.1 / NetMHCIIpan-4.3

**官方网页服务可执行的输入规则**（逐字）：
- 输入类型：`FASTA`（蛋白序列，服务器自行切肽）或 `PEPTIDE`（直接给肽段）。
- 字母表（区分大小写）：`A C D E F G H I K L M N P Q R S T V W Y` 与 `X`(unknown)；其他符号一律转 `X`。
- 限制：单次 ≤500 条序列；每条 ≤20,000 aa 且 ≥8 aa；**单次 ≤20 个 MHC 等位**。
- class I 肽长可选 8–14mer（可多选）；等位名单以官方 `MHC_allele_names.txt` 为准。
  来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/

**%Rank_EL 阈值语义与官方切点**（逐字）：

> "Strong binders are defined as having %rank<0.5, and weak binders with %rank<2. We advise to select candidate binders based on %Rank rather than Score"

- class I（NetMHCpan-4.1）默认：strong = 0.5%，weak = 2%；可改；`Filtering threshold` 填 `-99` 打印全部预测。
- class II（NetMHCIIpan-4.3）默认：strong = 1%，weak = 5%（官方 "default: 1%" / "default: 5%"）。
- `%Rank` 是"与随机天然肽分布比较的百分位"，官方强调它不受某些分子整体亲和力偏高/偏低的偏倚影响 —— **所以判据用 %Rank，不用 Score/IC50 绝对值**。
  来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ （Output format）；https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/ （ADDITIONAL CONFIGURATION + DESCRIPTION）

**输出列**（class I）：`Pos / HLA / Peptide / Core / Of / Gp / Gl / Ip / Il / Icore / Identity / Score_EL / Rnk_EL / BindLevel`；class II 另有 `Core_Rel`（结合 core 可靠性）、`Inverted`（肽反向结合，1=inverted）、`%Rank_BA`、`Affinity(nM)`、`Exp_bind`。
来源：同上两页 DESCRIPTION 一节

**命令行（standalone）**：官方公开网页**未提供可直接执行的命令**。DTU 页面只说明 NetMHCpan-4.1 有 stand-alone 包（学术用户走下载入口，其他用户联系 `health-software@dtu.dk`），具体 CLI 选项在下载包内的 README 中。因此本技能只写流程与判据：拿到安装包后以包内 README 的输入格式为准，参数语义与上表一致，不要用第三方博客里的参数拼接。
来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ （PORTABLE VERSION 一节）

### 2.3 新抗原预测流程

**先记住结论：新抗原预测没有统一金标准。** 各步骤都有官方工具，但"哪条候选是真新抗原"只能靠 HLA 结合 + 表达 + 加工 + 人工核查共同判断，任何单步打分都不能直接当结论。

官方可执行的部分（每步都用 2.1/2.2 已验证命令）：

| 步骤 | 输入 | 官方工具与命令 | 判据 |
|---|---|---|---|
| 1 体细胞突变 | 肿瘤/正常 BAM | 官方文档未提供（本技能未核验变异 calling 工具官方命令），只要求输出标准 VCF，含 `AD/DP` | 保留 PASS、VAF 阈值需在方法学中写明 |
| 2 肽段生成 | VCF + 转录本 FASTA | 官方文档未提供可直接执行的命令（无官方"突变→肽段"标准工具），只写规则：按突变所在转录本取 SNV/indel 上下文，生成 8–11mer（class I）与 12–20mer（class II）滑窗肽 | 必须同时生成 mutant 与 wild-type 对照肽 |
| 3 HLA 结合 | 肽段 FASTA/PEPTIDE + 等位 | NetMHCpan-4.1（class I）/ NetMHCIIpan-4.3（class II），见 2.2 | class I：`%Rank_EL < 0.5`（strong）/ `< 2`（weak）；class II：`< 1` / `< 5` |
| 4 表达过滤 | 肿瘤 RNA-seq 定量 | 官方文档未提供可直接执行的命令；用已有表达矩阵的 TPM/FPKM 过滤 | 突变所在基因需在肿瘤中表达；阈值写进方法学 |
| 5 人工核查 | 候选表 | — | 检查：等位是否与 2.1 分型一致（不是只跑 A*02:01）；突变坐标与转录本版本是否匹配；是否有 wild-type 同分（自肽风险） |

来源（步骤 3）：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ ；https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/
来源（步骤 1、2、4）：官方文档未提供可直接执行的命令 —— 本技能按要求只写流程与判据，不提供自造代码。

判据补充（来自官方文档的硬约束）：
- class I 单次提交 ≤20 个等位 → 6 位分型的患者（A/B/C 各 2）刚好 6 个，class II（DRB1/DQB1/DQA1/DPB1）再 8 个，**分两批提交，别丢等位**。
- 肽长：class I 官方支持 8–14mer；class II 走 NetMHCIIpan 的 15mer 核心逻辑（输出里 `Core` 会给出 9mer 结合核心）。
- 必须同时预测 wild-type 肽：只看 mutant 的 `%Rank_EL` 会把大量自肽当候选。

## 三、免疫浸润解卷积

**统一前提**：bulk 解卷积是"用参考矩阵做线性混合求解"，输出是相对比例（或相对 mRNA 比例），**不是每 mm² 的细胞数**；不同工具、不同 signature matrix、不同归一化之间的数字不可混用。跨样本比较必须在同一工具 + 同一参考 + 同一预处理下完成。

### 3.1 CIBERSORTx（需注册）

- 入口 https://cibersortx.stanford.edu/ ，页面只有 `Home / About / Contact / Register` 与登录框；`about.php` 返回 "You are currently not logged in. Please sign in to access content." → **官方文档未提供可直接执行的命令**，使用流程与输入格式必须登录后查看。
- 申请方式（官方公开页可确认的部分）：在 `register.php` 注册账号并登录；站点声明为非商业使用条款（"Non-Commercial Terms of Use"）。
  来源：https://cibersortx.stanford.edu/ ；https://cibersortx.stanford.edu/about.php
- 因此本技能只写判据：拿到账号后按官方界面顺序走（signature matrix → mixture → 批次校正/`Batch correction` 相关选项），**所有选项以登录后官方页面文案为准**；不要在论文方法里写未核验的参数名。

### 3.2 quanTIseq（官方文档完整，可直接执行）

```bash
bash quanTIseq_pipeline.sh --inputfile=path/to/input_file.txt --outputdir=path/to/outputdir [options]
```
输入文件格式（官方硬要求）：tab 分隔、**无表头**、一行一个样本、三列 = 样本 ID / FASTQ1 / FASTQ2；单端第三列写 `None`；FASTQ 可 gz。用 `--pipelinestart=decon` 时改为基因 TPM（或 microarray）矩阵：第一列基因 symbol、第一行样本 ID、**非 log 尺度**。
来源：https://icbi.i-med.ac.at/software/quantiseq/doc/

关键选项与官方默认值：`--pipelinestart`（`preproc`|`expr`|`decon`，默认 `preproc`）、`--tumor`（默认 FALSE；官方"highly recommend"肿瘤数据设 TRUE，会剔除肿瘤高表达 signature 基因）、`--arrays`（TRUE 时 `--rmgenes` 强制 `none`）、`--method`（`hampel`|`huber`|`bisquare`|`lsei`，默认 `lsei`，官方推荐 lsei；**只有 lsei 会给出 "other" 未表征细胞比例**）、`--mRNAscale`（默认 TRUE，官方强烈建议保持）、`--rmgenes`（`none`|`default`|文件路径；默认 `default`，官方建议 RNA-seq 用 default、microarray 用 none）、`--rawcounts`（默认 FALSE）、`--prefix`（默认 `quanTIseq`）、`--threads`（默认 1，官方注明 kallisto 结果会随线程数轻微变化）、Trimmomatic 相关 `--phred 33 / --adapterSeed 2 / --palindromeClip 30 / --simpleClip 10 / --trimLead 20 / --trimTrail 20 / --minLen 36 / --crop 10000`、kallisto 单端 `--avgFragLen 50 / --sdFragLen 20`。
来源：https://icbi.i-med.ac.at/software/quantiseq/doc/

输出与判据：`prefix_cell_fractions.txt`（样本 × 细胞类型）、`prefix_gene_tpm.txt`、`--rawcounts=TRUE` 时 `prefix_gene_count.txt`。10 类细胞：`B.cells / Macrophages.M1 / Macrophages.M2 / Monocytes / Neutrophils / NK.cells / T.cells.CD4（非 Treg）/ T.cells.CD8 / Tregs / Dendritic.cells` + `Other`；**总 CD4 = T.cells.CD4 + Tregs**（官方注）。
来源：https://icbi.i-med.ac.at/software/quantiseq/doc/ （Table 1）

### 3.3 EPIC

```r
out <- EPIC(bulk = bulkSamplesMatrix)
out <- EPIC(bulk = bulkSamplesMatrix, reference = referenceCellsList)
out <- EPIC(bulk = bulkSamplesMatrix, reference = referenceCellsList, mRNA_cell = mRNA_cell_vector, sigGenes = sigGenes_vector)
```
输入：TPM 或 RPKM 矩阵（官方要求）；输出 list 含 `mRNAProportions` 与 `cellFractions`，以及 goodness-of-fit 的 data.frame。
来源：https://github.com/GfellerLab/EPIC

判据（官方 FAQ）：报"细胞比例"用 `cellFractions`；若 bulk 是**由 scRNA-seq 重建的 in-silico 样本**，应与 `mRNAProportions` 比较（因为重建时未考虑各类细胞 mRNA 含量差异）。`other cells` 是该方法无参考谱的剩余细胞（肿瘤样本里多为癌细胞，但也可能含基质/上皮）。
来源：https://github.com/GfellerLab/EPIC （FAQ）

### 3.4 ABIS

官方原始包文档在本次抓取中未取到入口；可引用的官方文档是 omnideconv/immunedeconv 的封装文档：`deconvolute_abis`（https://omnideconv.org/immunedeconv/reference/deconvolute_abis.html）。**官方文档未提供可直接执行的命令**，因此只写判据：ABIS 为 allele-specific 解卷积，输入需要 HLA 分型（用 2.1 的分型结果），且与 CIBERSORTx/quanTIseq/EPIC 的数字不同源，不能混在一张图里比绝对值。

## 四、CyTOF / 流式

CATALYST 覆盖三件事：bead 归一化、单细胞去条码（debarcoding）、基于 bead 的补偿；随后 FlowSOM 聚类 + ConsensusClusterPlus 元聚类，diffcyt 做 DA/DS。

**预处理（官方 vignette 的完整链条）**：

```r
library(CATALYST)
sce <- prepData(raw_data)                       # FCS/flowSet -> SingleCellExperiment
res <- normCytof(sce, beads = "dvs", k = 50,
  assays = c("counts", "exprs"), overwrite = FALSE)
sce <- prepData(sample_ff)
sce <- assignPrelim(sce, sample_key)            # 6-choose-3 条码方案
sce <- estCutoffs(sce)                          # 分离阈值估计
sce <- applyCutoffs(sce)                        # 应用去条码参数
sce <- prepData(ss_exp)
sce <- assignPrelim(sce, bc_ms, verbose = FALSE)
sce <- applyCutoffs(estCutoffs(sce))
sce <- computeSpillmat(sce)                     # 单染样本 -> 溢出矩阵
sm <- metadata(sce)$spillover_matrix
sce <- prepData(mp_cells)
sce <- compCytof(sce, sm, method = "nnls", overwrite = FALSE)
```
来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html

官方默认值与判据：
- `prepData` 的 `transform` 默认 TRUE，做 arcsinh，`cofactor` 默认 **5**；`by_time` 默认 TRUE（按 `$BTIM` 排序）；非质量通道（如 Time/Event_length）自动移入 `int_colData`。
- `normCytof` 的 `beads`：`"dvs"` = 140/151/153/165/175；`"beta"` = 139/141/159/169/175；也可给自定义质量数向量。默认按 **median±5mad** 修剪 bead 群。归一化结果写入 `normcounts`/`exprs`，**保留原始数据**（`overwrite = FALSE`）。
- 去条码：`assignPrelim` → `estCutoffs`（分离阈值，logistic 拟合加权估计）→ `applyCutoffs`；未分配事件 `bc_id == 0` 要显式剔除。
- 补偿：`computeSpillmat` 需要**单抗体染色对照**（`ss_exp`）；`compCytof(..., method = "nnls")` 结果写 `compcounts`/`compexprs`。
来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html

**聚类与差异**：

```r
sce <- cluster(sce, features = "type", xdim = 10, ydim = 10, maxK = 20, verbose = FALSE, seed = 1)
set.seed(1601)
sce <- runDR(sce, dr = "UMAP", cells = 500, features = "type")
```
官方说明：`cluster` 用 FlowSOM 聚类（K = xdim × ydim）+ ConsensusClusterPlus 元聚类；`features = "type"` 只用 type marker 聚类，state marker 不参与。DA/DS 用 diffcyt（vignette 第 7 节）。
来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html

独立使用 FlowSOM（SOM + MST 可视化）：`BiocManager::install("FlowSOM")`（release 版本 2.20.0），vignette 见 https://bioconductor.org/packages/3.23/bioc/vignettes/FlowSOM/inst/doc/FlowSOM.pdf 。
来源：https://bioconductor.org/packages/release/bioc/html/FlowSOM.html

`cytofWorkflow` 的现行官方载体就是 CATALYST 的两个 vignette（package 页 Citation 列出 Nowicka et al. 2019 "CyTOF workflow: differential discovery in high-throughput high-dimensional cytometry datasets"）；**不再另找第三方 cytofWorkflow 脚本**。
来源：https://bioconductor.org/packages/release/bioc/html/CATALYST.html

## 五、质控与陷阱

1. **克隆型过度多样性（PCR 偏好）**：barcode/UMI 的测序与 PCR 错误会造出大量"只差 1–2 个碱基"的低频克隆型。MiXCR 的处理链是 `refineTagsAndSort`（barcode 纠错）+ `assemble`（质量纠错 → 映射 → 聚类，`cloneClusteringParameters.searchParameters=twoMismatchesOrIndels`、`backgroundSubstitutionRate=0.002`）。**不开纠错就报多样性 = 报测序错误率**。来源：https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/ ；https://mixcr.com/mixcr/reference/mixcr-assemble/
2. **补齐序列污染**：TRUST4 的 `CDR3_score = 0.01` 表示 imputed；MiXCR `--impute-germline-on-export` 会用 lowercase 补未覆盖区。多样性统计前要么剔除，要么统一策略。来源：https://github.com/liulab-dfci/TRUST4 ；https://mixcr.com/mixcr/reference/mixcr-export/
3. **MHC 预测的等位覆盖**：官方限单次 ≤20 等位，且 class I 只覆盖 HLA-A/B/C/E（及部分物种）；**只跑 A*02:01 是最常见的致命错误**。class II 的 DP/DQ 覆盖在 NetMHCIIpan-4.3 才补齐（官方摘要明确 DR 之外的 DQ/DP 数据缺口）。来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ ；https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/
4. **解卷积的参考矩阵依赖**：quanTIseq 的 `--rmgenes default` 与 `--tumor TRUE` 会改 signature；EPIC 的 `mRNA_cell` 决定 mRNA 比例 vs 细胞比例；CIBERSORTx 的 signature 可自定义。**换参考 = 换一把尺，数字不可跨研究直接比**。来源：见第三部分各工具页
5. **CyTOF 的 batch 效应**：不同批次 bead 归一化因子、补偿矩阵、去条码阈值都不同。CATALYST 的 `normCytof` 保留原始数据、`compCytof(overwrite = FALSE)` 保留未补偿数据，就是为了能回溯；**跨批次比较前先看 `plotCounts`/`pbMDS`**。来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html
6. **新抗原"假阳性瀑布"**：不做 wild-type 对照、不做表达过滤、不核对 HLA 分型，候选表会膨胀到几百条。见 2.3 判据。

## 产出目录（建议）

```
immunogenomics_run/
├─ 00_meta/            # 样本表、参考版本记录（MiXCR preset、IMGT 版本、HLA 分型工具版本）
├─ 01_repertoire/
│   ├─ mixcr/          # *.vdjca *.clns *.tsv + align/assemble 报告
│   ├─ trust4/         # trust_cdr3.out trust_report.tsv trust_airr.tsv
│   └─ diversity/      # postanalysis --tables 输出（每 metric 一文件）
├─ 02_hla/             # optitype *_result.tsv / arcasHLA *.genotype.json / HLA-LA R1_bestguess_G.txt
├─ 03_mhc_binding/     # NetMHCpan/NetMHCIIpan 输出表 + 阈值记录（0.5/2 或 1/5）
├─ 04_neoantigen/      # 候选表 + wild-type 对照 + 人工核查记录
├─ 05_deconvolution/   # quantiseq cell_fractions / EPIC out.rds / CIBERSORTx 导出
└─ 06_cytof/           # SCE .rds（含 normcounts/compexprs）、cluster 结果、diffcyt 结果
```

## 验收清单

- [ ] 每个工具版本、参考库版本、preset 名称都写进 `00_meta`（MiXCR preset + species；IMGT/HLA 版本；arcasHLA 参考版本）
- [ ] 免疫组库：`align` 报告已查看，比对率/chimera 量无异常；纠错步骤未被 `--dont-correct` 误关
- [ ] 克隆型定义（`assemblingFeatures`、是否 split by V/J/C）在方法学中写明
- [ ] 多样性指标在**统一下采样**后计算，下采样类型（count/top/cumtop）与 weight function（read/umi/cell）已记录
- [ ] HLA 分型至少两种方法交叉验证，class I 与 class II 都覆盖
- [ ] MHC 预测：提交的等位数 = 分型结果，未漏等位；阈值用 %Rank_EL（0.5/2 或 1/5），未用 Score/IC50 绝对值下结论
- [ ] 新抗原：有 wild-type 对照、有表达过滤、有"无统一金标准"的人工核查记录
- [ ] 解卷积：同一分析内 signature/方法/归一化唯一；报告写"相对比例"而非绝对细胞数
- [ ] CyTOF：归一化、去条码阈值、补偿矩阵三件套齐全；原始数据未被覆盖
- [ ] 所有命令可回溯到 `references/official-docs.md` 中的官方 URL

## 参考文件

- `references/official-docs.md` — 官方文档清单、抓取状态、每条命令的出处
- `references/parameters.md` — 四部分参数表（免疫组库 / MHC 预测 / 解卷积 / CyTOF）
- `references/troubleshooting.md` — 报错与判据偏离的排查路径

> 本技能不提供 `scripts/`。上述工具均为官方发行版（conda/pip/源码/MiXCR 二进制），没有官方配套的"一键脚本"；按规则不自造脚本。
