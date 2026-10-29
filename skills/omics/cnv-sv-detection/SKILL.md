---
name: cnv-sv-detection
description: |
  Copy-number variation (CNV) and structural variation (SV) detection and annotation for WGS/WES/panel data.
  Covers CNVkit read-depth CNV calling (batch/reference/fix/segment/call, WGS binning and GC correction,
  sex and ploidy handling, BAF-assisted allele-specific calls), Manta germline/somatic/tumor-only SV calling,
  Delly call/merge/filter SV and CNV workflows, GATK-SV single-sample execution, and SV annotation with
  AnnotSV and Ensembl VEP. All commands and defaults are quoted from official documentation.
  中文触发词：拷贝数变异、CNV、结构变异、SV、缺失重复、CNVkit、Manta、Delly。
category: omics
tags: cnv, sv, wgs, wes, cnvkit, manta, delly
---

# 拷贝数变异与结构变异检测（CNV / SV）

本技能只使用**官方文档中逐字可查**的命令与参数。凡是官方文档只给流程、没给可执行命令的部分，本技能只写判据，不自行编写脚本或命令（见文末「官方文档缺口清单」）。

- 全部命令与默认值：`references/official-docs.md`（逐条附来源 URL）
- 参数与默认值速查：`references/parameters.md`
- 常见失败与判据：`references/troubleshooting.md`

## 1. 路线选择

| 数据结构 | 信号类型 | 官方推荐工具 | 依据 |
| --- | --- | --- | --- |
| WES / 靶向捕获（有 off-target reads） | read-depth + BAF | CNVkit 默认 `hybrid` 方法 | pipeline.html |
| WGS | read-depth（全基因组分箱） | CNVkit `batch --method wgs` | nonhybrid.html |
| 靶向扩增子（TAS，无 off-target） | 仅 on-target | CNVkit `batch -m amplicon` | nonhybrid.html |
| WGS/WES 断点型 SV（DEL/DUP/INV/BND/INS） | paired-end + split-read | Manta；Delly | Manta userGuide；Delly README |
| 大队列 germline SV 联合分型 | 位点合并 + 重分型 | Delly `merge` + `-v sites` + `filter` | Delly README |
| 单样本/小样本 SV（临床） | cohort 模型迁移 | GATK-SV single-sample（Terra） | gatk-sv docs |
| SV 注释与 ACMG 分级 | 区间重叠 + 基因/剂量 | AnnotSV；VEP SV 模式 | AnnotSV quickstart/ranking；VEP formats |

判定顺序：先确认**是否有配对正常样本**（决定 germline / somatic / tumor-only），再确认**是否为全基因组**（决定 read-depth 分箱策略），最后确认**是否有可用的 SNV VCF**（决定能否做 BAF 与等位基因特异拷贝数）。

## 2. 输入与前置条件（官方硬性要求）

- BAM/CRAM 必须**坐标排序并建索引**；CNVkit 明确要求 BAM 已排序，且 `.bai` 时间戳需晚于 BAM（`touch` 更新），否则会静默把覆盖率截断为 0（pipeline.html「BAM file preparation」）。
- BAM 建议用 BWA-MEM 比对、标记 secondary、用 SAMBLASTER/SAMBAMBA/Picard MarkDuplicates 标记 PCR 重复，CNVkit 会跳过这些 reads（pipeline.html）。
- Manta 要求每个输入 BAM/CRAM 有 `.bai`/`.crai`/`.csi` 索引，参考 FASTA 有 `.fai`，且**所有输入与参考的染色体名称与顺序一致**；不允许 `SEQ="*"`、不允许 SEQ 含 `=`、不允许 `=`/`X` CIGAR、碱基质量 >70 会被拒绝（Manta userGuide「Input requirements」「Configuration」）。
- Delly 要求每个样本 **sorted、indexed、最好已标重复** 的 BAM/CRAM，以及带索引的参考基因组（Delly README「Running Delly」「FAQ」）。
- 参考基因组 FASTA 必填：CNVkit 用它算 GC 与 RepeatMasker 比例（pipeline.html「reference」）；Manta/Delly 用它做 split-read 与 CRAM 解码。
- 基因注释（refFlat 等）用于给 bin 打基因标签；WGS 下 CNVkit **必须**提供注释库才能给输出打基因名（nonhybrid.html）。

## 3. CNV：read-depth 路线（CNVkit）

### 3.1 一键流程（官方 `batch`）

WES/捕获（Tumor/Normal）：

```bash
cnvkit.py batch *Tumor.bam --normal *Normal.bam \
    --targets my_baits.bed --annotate refFlat.txt \
    --fasta hg19.fasta --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_reference.cnn --output-dir results/ \
    --diagram --scatter
```

来源：https://cnvkit.readthedocs.io/en/stable/pipeline.html#batch

复用已有参考处理新样本：

```bash
cnvkit.py batch *Tumor.bam -r Reference.cnn -d results/
```

来源：同上（pipeline.html#batch）

无正常样本时建「平参考」（`-n` 后不给 BAM）：

```bash
cnvkit.py batch *Tumor.bam -n -t my_baits.bed -f hg19.fasta \
    --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_flat_reference.cnn -d example2/
```

来源：https://cnvkit.readthedocs.io/en/stable/quickstart.html

并行：`-p`（`batch -p 8`；`-p 0` 表示用满可用 CPU）——pipeline.html#batch、quickstart.html。

### 3.2 分步流程（等价于 `batch`，官方给出的等价命令序列）

```bash
cnvkit.py access hg19.fa -o access.hg19.bed
cnvkit.py autobin *.bam -t baits.bed -g access.hg19.bed [--annotate refFlat.txt --short-names]

# For each sample...
cnvkit.py coverage Sample.bam baits.target.bed -o Sample.targetcoverage.cnn
cnvkit.py coverage Sample.bam baits.antitarget.bed -o Sample.antitargetcoverage.cnn

# With all normal samples...
cnvkit.py reference *Normal.{,anti}targetcoverage.cnn --fasta hg19.fa -o my_reference.cnn

# For each tumor sample...
cnvkit.py fix Sample.targetcoverage.cnn Sample.antitargetcoverage.cnn my_reference.cnn -o Sample.cnr
cnvkit.py segment Sample.cnr -o Sample.cns
```

来源：pipeline.html#batch（"The pipeline executed by the `batch` command is equivalent to"）

分步命令各自的官方用法：

```bash
cnvkit.py target my_baits.bed --annotate refFlat.txt --split -o my_targets.bed
cnvkit.py access hg19.fa -x excludes.bed -o access-excludes.hg19.bed
cnvkit.py access mm10.fasta -s 10000 -o access-10kb.mm10.bed
cnvkit.py antitarget my_targets.bed -g data/access-5kb-mappable.hg19.bed -o my_antitargets.bed
cnvkit.py autobin *.bam -t my_targets.bed -g access.hg19.bed
cnvkit.py autobin *.bam -m wgs -b 50000 -g access.hg19.bed --annotate refFlat.txt
cnvkit.py coverage Sample.bam targets.bed -o Sample.targetcoverage.cnn
cnvkit.py reference *coverage.cnn -f ucsc.hg19.fa -o Reference.cnn
cnvkit.py reference -o FlatReference.cnn -f ucsc.hg19.fa -t targets.bed -a antitargets.bed
cnvkit.py fix Sample.targetcoverage.cnn Sample.antitargetcoverage.cnn Reference.cnn -o Sample.cnr
cnvkit.py segment Sample.cnr -o Sample.cns
```

来源：pipeline.html 的 `target` / `access` / `antitarget` / `autobin` / `coverage` / `reference` / `fix` / `segment` 各节。

### 3.3 WGS：binning 与 GC 校正

官方 WGS 一键命令（注释库必填）：

```bash
cnvkit.py batch Sample1.bam Sample2.bam -n Control1.bam Control2.bam \
        -m wgs -f hg19.fasta --annotate refFlat.txt
```

来源：https://cnvkit.readthedocs.io/en/stable/nonhybrid.html#whole-genome-sequencing-wgs

官方给出的 WGS 提速/提准手段（`batch -m wgs` 除第一条外全部自动执行）：

- 只分析基因区（用 UCSC 导出的 target BED 限制范围）；
- 提高 target 平均 bin 大小 `--target-avg-size`，30x 覆盖度下至少 1000 bases，覆盖度更低则按比例加大；
- 收紧 `segment -t`（CBS 方法 `1e-6` 可能表现良好），或改用 `hmm` 分割；
- 用 `-p/--processes` 用满 CPU；
- 关闭 edge 偏倚校正（`reference`/`fix` 的 `--no-edge`）。

来源：nonhybrid.html#whole-genome-sequencing-wgs

GC 校正机制（官方描述，不是自造参数）：每个 bin 的 GC 比例与 repeat-masked 比例在 `reference` 阶段由基因组序列计算并写入 .cnn 的 `gc`/`rmask` 列；`reference` 与 `fix` 用滚动中位数拟合「观测 read depth vs 偏倚因子」并相减；`--no-gc`/`--no-rmask` 会跳过对应校正，若建参考时跳过了，`fix` 也会跳过（并告警）；这些开关必须前后一致。来源：https://cnvkit.readthedocs.io/en/stable/bias.html 、pipeline.html#reference、pipeline.html#fix

### 3.4 性别与倍性

- 默认参考为**二倍体 X + 单倍体 Y**；若输入样本中有男性（单倍体 X），其 X 覆盖度会被加倍以等价二倍体 X（sex.html#reference-sex-chromosome-ploidy）。
- 需要「单倍体 X 参考」（array CGH 惯例）时用 `-y` / `--male-reference` / `--haploid-x-reference`；用 `-y` 建的参考，必须在 `call`、`export`、`genemetrics` 上同样加 `-y`（sex.html）。
- 样本性别可用 `-x` / `--sample-sex` 覆盖自动推断；`-x` 与 `-y` 语义不同（sex.html）。
- 性别核查命令：

```bash
cnvkit.py sex *.cnn *.cnr *.cns
cnvkit.py sex -y *.cnn *.cnr *.cns
```

来源：https://cnvkit.readthedocs.io/en/stable/reports.html#sex

### 3.5 BAF 辅助（等位基因特异拷贝数 / LOH）

`call` 接受 SNV VCF（`-v/--vcf`），对每个 segment 汇总杂合 SNP 的 BAF 并写入 `baf` 列，再据总拷贝数与 BAF 推断 `cn1`/`cn2`（方法同 PSCBS：总拷贝数 × BAF 后取整）；`cn1 ≠ cn2` 即提示等位基因失衡 / 拷贝数中性 LOH。

```bash
cnvkit.py call Sample.cns -y -v Sample.vcf -m clonal --purity 0.7 -o Sample.call.cns
cnvkit.py call Sample.cns -y -v Sample.vcf -o Sample.call.cns
cnvkit.py call Sample.cns -v Sample.vcf --purity 0.8 -m none -o Sample.call.cns
```

来源：https://cnvkit.readthedocs.io/en/stable/pipeline.html#call 、https://cnvkit.readthedocs.io/en/stable/baf.html

BAF 的适用前提（官方）：VCF 应来自 tumor-normal 联合 SNV 调用（如 MuTect、VarDict、FreeBayes）并已标记体细胞突变以便跳过；无配对正常样本时可用 1000 Genomes 常见 SNP 位点从 tumor-only VCF 中提取可能的 germline SNV（baf.html）。

## 4. SV：断点检测

### 4.1 Manta

三种官方运行模式（配置 → 执行两步）：

```bash
# 单样本 germline（diploid）
${MANTA_INSTALL_PATH}/bin/configManta.py \
--bam NA12878_S1.bam \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}

# 联合 germline（多个 --bam，各自作为一个样本）
${MANTA_INSTALL_PATH}/bin/configManta.py \
--bam NA12878_S1.cram \
--bam NA12891_S1.cram \
--bam NA12892_S1.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}

# 体细胞 tumor/normal
${MANTA_INSTALL_PATH}/bin/configManta.py \
--normalBam HCC1187BL.cram \
--tumorBam HCC1187C.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}

# tumor-only（只给 tumor，不给 normal）
${MANTA_INSTALL_PATH}/bin/configManta.py \
--tumorBam HCC1187C.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}
```

执行：

```bash
${MANTA_ANALYSIS_PATH}/runWorkflow.py -j 8
```

来源：https://raw.githubusercontent.com/Illumina/manta/v1.6.0/docs/userGuide/README.md （同 https://github.com/Illumina/Manta/blob/develop/docs/userGuide/README.md）

输出（`${MANTA_ANALYSIS_PATH}/results/variants`）：`diploidSV.vcf.gz`、`somaticSV.vcf.gz`（有 tumor 才产出）、`candidateSV.vcf.gz`（未打分候选，默认含 ≥8bp indel）、`candidateSmallIndels.vcf.gz`（<50bp 的简单 indel）、tumor-only 额外产出 `tumorSV.vcf.gz`（未打分，但含 PR/SR 支持计数 + 部分 tumor-normal 过滤器）。来源同上「Outputs」。

### 4.2 Manta 的 `--exome` 与候选读取

- `--exome`：为 WES 与其他区域富集分析提供合适设置，**目前会关闭所有高深度过滤器**（这些过滤器是为排除 WGS 中着丝粒附近参考压缩而设，靶向数据不能正确套用）。来源：userGuide「Exome/Targeted」。
- 即使指定了 `--callRegions`，WES/靶向数据**仍必须**加 `--exome` 才能获得正确的深度过滤行为。来源：userGuide「Call regions」。
- `--callRegions`：BED 必须 bgzip 压缩 + tabix 建索引，只允许一个 BED；所有 VCF 输出被限制在该区域，但片段长度分布等统计不受限。来源：userGuide「Call regions」。
- 候选读取：SV 必须先出现在 `candidateSV.vcf.gz` 才可能被打分，因此「不在候选 → 不可能出现在结果」；候选最小 indel 默认 8bp，Manta 自身打分从 50bp 起，<50bp 的交由小变异 caller。来源：userGuide「Structural Variant predictions」。
- tumor-only 无质量打分模型，官方建议用等位基因支持计数做过滤，例如仅保留 `SAMPLE/PR[1] >= 15 || SAMPLE/SR[1] >= 15`，并把 `IMPRECISE` 当作可靠性指标。来源：userGuide「Unpaired tumor sample」。
- 高通量靶向/低丰度场景可把配置文件中 `minEdgeObservations` 与 `minCandidateSpanningCount` 从默认 3 改为 2（高灵敏度模式）。来源：userGuide「High sensitivity calling」。

### 4.3 Delly

官方 germline 流程（发现 → 位点合并 → 重分型 → bcftools 合并 → 过滤）：

```bash
delly [sr|lr] -g hg38.fa -o s1.bcf sample1.bam
delly merge -l -g hg38.fa -o sites.bcf s1.bcf s2.bcf ... sN.bcf
delly [sr|lr] -g hg38.fa -v sites.bcf -o s1.geno.bcf s1.bam
delly [sr|lr] -g hg38.fa -v sites.bcf -o sN.geno.bcf sN.bam
bcftools merge -m id -O b -o merged.bcf s1.geno.bcf s2.geno.bcf ... sN.geno.bcf
delly filter -l --hwe 0.000001 -f germline -o germline.bcf merged.bcf
```

短读长建议加排除图谱：

```bash
delly sr -g hg38.fa -x human.hg38.excl.tsv -o delly.bcf sample.bam
```

官方 somatic 流程：

```bash
delly [sr|lr] -o t1.bcf -g hg38.fa tumor1.bam control1.bam
delly filter -f somatic -o t1.somatic.bcf -s samples.tsv t1.bcf
```

`samples.tsv` 为 tab 分隔，第一列样本 ID（与 VCF 一致），第二列 `tumor` 或 `control`。来源：https://raw.githubusercontent.com/dellytools/delly/main/README.md （同 https://github.com/dellytools/delly）

官方 read-depth CNV 流程（`delly cnv` 为全基因组 read-depth 法，带 GC 偏倚与可比对性校正，**不支持 WES/靶向**）：

```bash
delly cnv -g hg38.fa -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
delly cnv -m somatic -g hg38.fa -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
delly cnv -g hg38.fa -x human.GRCh38.map.excl.tsv.gz -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
```

来源：Delly README「CNV calling」「Somatic copy-number alterations (SCNAs)」

### 4.4 GATK-SV（仅官方 Terra 执行方式）

官方文档只描述**在 Terra 工作台克隆 single-sample 工作区并运行 `gatk-sv-single-sample` 工作流**：输入为单个 CRAM/BAM（`sample_id`、`bam_or_cram_file`，可选 `case_stripy_file`、`batch`），需配好 hg38 参考资源、参考面板数据与 docker 镜像；输出 `final_vcf`（含 gnomAD 位点等位基因频率与功能元件重叠注释）、`final_bed`。来源：https://broadinstitute.github.io/gatk-sv/docs/execution/single/

官方文档**未提供**该模式的本地单命令行调用；`/docs/execution/sv-shell/` 在本环境返回 404。本技能因此不对 GATK-SV 给任何自造命令。

## 5. 注释

### 5.1 AnnotSV（SV/CNV 注释 + ACMG 分级）

安装与环境变量（官方）：

```bash
cd /path/to/install/
git clone https://github.com/lgmgeo/AnnotSV.git
cd /path/to/install/AnnotSV
make PREFIX=. install
make PREFIX=. install-human-annotation
make PREFIX=. install-mouse-annotation
export ANNOTSV=/path/to/install/AnnotSV
```

运行（官方示例）：

```bash
$ANNOTSV/bin/AnnotSV -SVinputFile test.bed -outputFile ./test.annotated.tsv -svtBEDcol 4
```

来源：https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/share/doc/AnnotSV/quickstart.md

分级阈值（官方 ranking 文档）：≥0.99 Class 5 Pathogenic；0.90–0.98 Class 4 Likely pathogenic；−0.89–0.89 Class 3 VUS；−0.90–−0.98 Class 2 Likely benign；≤−0.99 Class 1 Benign。评分准则见 `Scoring_Criteria_AnnotSV_v3.4.xlsx`。来源：https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/share/doc/AnnotSV/ranking.md

注释库与基因组版本（官方）：GRCh37 或 GRCh38 由用户指定，部分注释与基因名绑定因而与 build 无关；各注释源在安装时自动下载。来源：.../annotations.md

CNVkit 结果转成 AnnotSV 可读的 VCF/BED（官方 export）：

```bash
cnvkit.py call Sample.cns -y -o Sample.call.cns
cnvkit.py export bed Sample.call.cns --show all -y -o Sample.bed
cnvkit.py export vcf Sample.cns -y -x female -i "SampleID" -o Sample.cnv.vcf
```

来源：https://cnvkit.readthedocs.io/en/stable/importexport.html#export

### 5.2 Ensembl VEP 的 SV 模式

官方支持的 SV 表达方式：默认 VEP 格式（`1 160283 471362 DUP +`）、VCF（`SVTYPE` + `END`）、REST 风格（`21:25587759-25587769/DEL`）；**breakend 只支持 VCF 输入**。可用 SVTYPE 值：`INS`、`INS:ME`、`INS:ME:ALU`、`INS:ME:HERV`、`INS:ME:LINE1`、`INS:ME:SVA`、`DEL`、`DEL:ME`、`DEL:ME:ALU`、`DEL:ME:HERV`、`DEL:ME:LINE1`、`DEL:ME:SVA`、`DUP`、`DUP:TANDEM`、`TDUP`、`INV`、`CNV`（可写 `CN0`、`CN=4`、`CN3,CN4` 等）、`CNV:TR`。来源：https://www.ensembl.org/info/docs/tools/vep/vep_formats.html

VEP 的 SV 输入示例（官方原文）：

```
#CHROM POS ID REF ALT QUAL FILTER INFO
1 160283 dup . <DUP> . . SVTYPE=DUP;END=471362
1 1385015 del . <DEL> . . SVTYPE=DEL;END=1387562
1 7936271 bnd N N[12:58877476[ . . SVTYPE=BND
```

基础运行（官方默认用法 `./vep --cache -i input.txt -o output.txt` 加 VCF 输入输出）：

```bash
./vep -i SAMPLE.sv.vcf --format vcf --vcf --cache --assembly GRCh38 -o SAMPLE.vep.vcf --fork 4
```

来源：https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html （`--input_file/-i`、`--format`、`--vcf`、`--cache`、`--assembly`、`--fork` 各条）

SV 相关专有开关（官方）：`--check_svs`（查已知结构变异是否重叠，**当前需要数据库访问，与 `--offline` 不兼容**，输出字段 `SV`）；`--overlaps`（以 VCF 形式报告转录本被 SV 覆盖的比例与长度）；`--max_sv_size`（默认 `10000000`，`-1` 关闭，官方警告关闭会显著增加内存与运行时间）。来源同上。

## 6. 过滤与质控

- 样本噪声评估：`cnvkit.py metrics *.cnr -s *.cns`，输出 segment 数、SD、MAD、IQR、Tukey biweight midvariance；官方启发式：把「segment 数 × biweight midvariance」相乘，值越大越不可靠，可疑样本再用 bedtools / chanjo / IGV / Picard CollectHsMetrics 查覆盖度。来源：reports.html#metrics
- 逐 segment 统计与置信区间（`call --filter ci` 的前置）：

```bash
cnvkit.py segmetrics Sample.cnr -s Sample.cns --iqr
cnvkit.py segmetrics -s Sample.cn{s,r} --ci --pi
```

`--ci` 用 bootstrap（100 次重采样）给 segment 均值的置信区间，输出 `ci_lo`/`ci_hi`；`--pi` 用 2.5–97.5 百分位给预测区间，输出 `pi_lo`/`pi_hi`。来源：reports.html#segmetrics

- `call --filter`：可组合 `cn`（按整数拷贝数并合并相邻同值段）、`ampdel`（只留 ≥5 拷贝扩增与 0 拷贝纯合缺失）、`ci`（置信区间跨 0）、`sem`（均值标准误）；跨染色体或等位基因拷贝数不同的段不合并。来源：pipeline.html#call「Filtering segments」
- germline 场景：`call` 直接用默认 `--purity/--ploidy`（哺乳动物二倍体默认正确），用 `--filter ci`（推荐）或 `sem` 降假阳性；**不要**用 `--drop-low-coverage`（会把 germline 深缺失整段删掉）。来源：https://cnvkit.readthedocs.io/en/stable/germline.html
- tumor 场景：`--drop-low-coverage` 丢弃 log2 < −15 的 bin（−20 为零覆盖占位值，任何 < −15 的 bin 基本是零覆盖假值，不是真实观测）；高异倍体样本可用 `--center median`。来源：https://cnvkit.readthedocs.io/en/stable/tumor.html
- Delly 提速/降噪（官方 FAQ）：用 `-x` 排除端粒、着丝粒与未定位 contig；`-q 20`、`-s 15` 收紧 reads；高覆盖数据 `-z 5`。来源：Delly README FAQ
- Manta 过滤器含义（官方表的节选判据）：`MinQUAL`（QUAL<20）、`MinGQ`（GQ<15）、`MinSomaticScore`（SOMATICSCORE<30）、`Ploidy`、`MaxDepth`（深度 >3× 近断点染色体中位深度）、`MaxMQ0Frac`（<1000bp 变异断点两侧 MAPQ0 reads 比例 >0.4）、`NoPairSupport`、`SampleFT`、`HomRef`。来源：userGuide「VCF FILTER Fields」

## 7. 验证与解读

1. **覆盖度是否支撑结论**：CNVkit 官方给出可靠性下界——通常可稳定检出较大 CNA 到约 10x on-target 覆盖度，低于此会增多伪 segment，小尺度/亚克隆 CNA 难以推断（pipeline.html#reference）。WGS 30x 建议 bin ≥1000bp（nonhybrid.html）。
2. **性别是否一致**：用 `cnvkit.py sex` 检查「参考 sex + 样本 X/Y log2」；女性样本对男性参考会出现 X ≈ +1、Y 深度丢失，男性样本对女性参考会出现 X ≈ −1（sex.html#faq）。性别判错会直接毁掉 X/Y 上的 CN 判定。
3. **倍性/纯度是否已知**：`call -m clonal` 需要正确 `--purity`/`--ploidy`；`-m threshold` 默认阈值（−1.1/−0.4/0.3/0.7）在纯度 ≥30% 的肿瘤里「相对安全」，外侧阈值按 100% 纯度设定（pipeline.html#call「Calling methods」）。
4. **与已知数据库对接**：
   - ClinVar：NCBI 官方 FTP 提供 GRCh38 的 VCF 与 tabix 索引（`clinvar.vcf.gz`、`clinvar.vcf.gz.tbi`），可直接按坐标与 `SVTYPE/END` 做区间重叠比对。来源：https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/ （本次抓取的目录清单：`clinvar.vcf.gz 191M`、`clinvar.vcf.gz.tbi 597K`、`weekly/`、`archive_2.0/`）。
   - gnomAD-SV：官方入口 https://gnomad.broadinstitute.org/downloads 与 SV 说明页 https://gnomad.broadinstitute.org/help/sv-overview 。**官方页面为动态渲染，本次未取得可逐字引用的文件名与命令行** → 只写判据：从官方 Downloads 的 Structural variants 区域取 VCF，用 `SVTYPE`+`END` 做重叠与频率比对，注释频率后再判断罕见/常见（见文末缺口清单）。
   - DGV：官方入口 http://dgv.tcag.ca/dgv/app/downloads 。本次抓取失败 → 只写判据：按 GRCh38 下载 DGV 的 CNV 区间文件，与自建 CNV 段做区间重叠，落在 DGV 常见多态区间内的 CNV 降级为可能良性（见文末缺口清单）。
5. **交叉验证**：read-depth 段与断点型 SV 应互相印证（同一缺失在 CNVkit 段与 Manta `DEL` 应位置一致）；CNVkit 的 `breaks` 可列出断点所在基因，用于「非平衡融合/重排」线索（reports.html#breaks）。

## 8. 产出目录（建议的最小可交付结构）

```
<PROJECT>/
├─ 00_input/            # BAM/CRAM + index、FASTA + .fai、target BED、refFlat、可选 SNV VCF
├─ 01_cnvkit/
│  ├─ coverage/         # *.targetcoverage.cnn / *.antitargetcoverage.cnn
│  ├─ reference.cnn
│  ├─ *.cnr             # fix 输出
│  ├─ *.cns             # segment 输出
│  ├─ *.call.cns        # call 输出（含 cn / baf / cn1 / cn2）
│  └─ reports/          # metrics.tsv、segmetrics.cns、sex.tsv、breaks.tsv、genemetrics.tsv
├─ 02_manta/<SAMPLE>/   # runWorkflow.py 工作目录：results/variants/*.vcf.gz、results/stats/
├─ 03_delly/            # *.bcf（sr/cnv）、sites.bcf、*.geno.bcf、merged.bcf、somatic/germline.bcf
├─ 04_annot/            # AnnotSV *.annotated.tsv、VEP *.vep.vcf
└─ 05_qc/               # sex.tsv、metrics.tsv、覆盖度核查记录、已知库比对结果
```

`scripts/` 目录本技能**不创建**：官方脚本已随各工具分发，直接调用即可（清单见 `references/official-docs.md` 末节）。

## 9. 验收清单

- [ ] 输入 BAM/CRAM 已排序+索引，`.bai` 不早于 BAM（pipeline.html 要求）；Manta 输入的染色体命名与参考完全一致。
- [ ] CNVkit 参考与测试样本同平台、同建库方式；WES 用捕获 baits BED（不是 primary targets），WGS 用 `-m wgs` + `--annotate`。
- [ ] `reference` 与 `fix` 的 `--no-gc/--no-rmask/--no-edge` 开关前后一致（pipeline.html#fix）。
- [ ] `-y` 一旦用于建参考，`call`/`export`/`genemetrics` 全部带 `-y`。
- [ ] germline 未使用 `--drop-low-coverage`；tumor 若使用则记录理由。
- [ ] `call --filter ci` 之前已跑过 `segmetrics --ci`。
- [ ] Manta 至少产出 `candidateSV.vcf.gz`，并在 `diploidSV`/`somaticSV`/`tumorSV` 中核对目标变异；WES 加了 `--exome`。
- [ ] Delly 未对 WES 数据使用 `delly cnv`；germline 走了 `merge` → `-v sites` 重分型 → `bcftools merge` → `filter -f germline`。
- [ ] SV VCF 的 `SVTYPE` 取值在 VEP 支持列表内，且带 `END`；AnnotSV 的 `-svtBEDcol` 与被注释的 BED 列号对应。
- [ ] 性别核查（`cnvkit.py sex`）结果与样本登记表一致。
- [ ] 每条 CNV/SV 结论都能追到：原始命令、参数来源 URL、覆盖度证据、已知库比对结果。

## 10. 官方文档缺口清单（本技能只写流程，不写命令）

| 主题 | 官方状态 | 处理方式 |
| --- | --- | --- |
| GATK-SV 本地命令行（single-sample / SV-Shell） | 官方只给 Terra 工作区运行方式；`/docs/execution/sv-shell/` 返回 404 | 只写工作流输入/输出与判据，不给命令 |
| gnomAD-SV 下载文件名与筛选命令 | 官方页面动态渲染，本次未取得可引用文本 | 只写「从官方 Downloads 取 SV VCF + 按 SVTYPE/END 重叠」判据 |
| DGV 下载与重叠步骤 | 官方页面本次抓取失败 | 只写判据（区间重叠 + 常见多态降级） |
| AnnotSV 除 `-SVinputFile/-outputFile/-svtBEDcol` 外的完整参数表 | quickstart 只给最小示例，完整参数在 README.AnnotSV_3.5.7.pdf | 只写已验证的三个参数，其余标注「见官方 PDF」 |
| CNVkit 的 `tutorial.html` | 该 URL 返回 404，官方教程页为 `quickstart.html` | 以 quickstart.html 为准 |

## 11. 参考文件

- `references/official-docs.md` — 全部官方命令逐字摘录 + 每条来源 URL + 官方随附脚本清单
- `references/parameters.md` — 参数与默认值速查（含官方给出的数值判据）
- `references/troubleshooting.md` — 常见失败现象 → 官方判据 → 出处

## 12. 来源总表

CNVkit 0.9.8 官方文档：quickstart / pipeline / nonhybrid / reports / sex / baf / bias / tumor / germline / calling / importexport / scripts 页（https://cnvkit.readthedocs.io/en/stable/）。
Manta v1.6.0 User Guide：https://raw.githubusercontent.com/Illumina/manta/v1.6.0/docs/userGuide/README.md
Delly README（main）：https://raw.githubusercontent.com/dellytools/delly/main/README.md
GATK-SV 官方文档：https://broadinstitute.github.io/gatk-sv/docs/execution/single/
AnnotSV：https://github.com/lgmgeo/AnnotSV （share/doc/AnnotSV/quickstart.md、ranking.md、annotations.md）
Ensembl VEP：https://www.ensembl.org/info/docs/tools/vep/vep_formats.html 、https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html （镜像入口 https://asia.ensembl.org/info/docs/tools/vep/index.html）
ClinVar：https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/
gnomAD：https://gnomad.broadinstitute.org/downloads 、https://gnomad.broadinstitute.org/help/sv-overview
DGV：http://dgv.tcag.ca/dgv/app/downloads
