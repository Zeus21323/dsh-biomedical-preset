---
name: variant-calling-wes-wgs
description: |
  Germline short-variant discovery mainline for human whole-exome (WES) and whole-genome (WGS)
  resequencing: read-group assignment, BWA-MEM2 alignment, sort/mark-duplicates, optional BQSR,
  HaplotypeCaller GVCF, GenomicsDBImport + GenotypeGVCFs joint genotyping, VQSR or hard filtering,
  left-alignment/normalization and VEP annotation, plus WES capture-interval handling and coverage QC.
  Every command is quoted from the GATK / Picard / htslib / bwa-mem2 / Ensembl VEP / mosdepth official
  documentation with its source URL; steps that have no official runnable command are described as
  workflow and criteria only.
  触发场景：全外显子测序、WES 分析、全基因组测序、WGS 重测序、种系变异检测、germline variant calling、
  call variant、SNP/INDEL 检测、GVCF、HaplotypeCaller、GenomicsDBImport、GenotypeGVCFs、联合分型、
  joint calling、VQSR、VariantRecalibrator、ApplyVQSR、硬过滤、VariantFiltration、BQSR、BaseRecalibrator、
  MarkDuplicates、BWA-MEM2、VEP 注释、外显子捕获区间、capture BED、覆盖度 QC、mosdepth、CollectHsMetrics。
category: omics
tags: wes, wgs, gatk, variant-calling, germline
---

# 人 WES / WGS 种系变异检测主线

从 FASTQ / uBAM / 已比对 BAM 走到「已过滤 + 已规范化 + 已注释」的种系 VCF。

## 引用纪律（本技能的第一原则）

1. 下面出现的每条命令都逐字来自官方文档，命令块后紧跟 `来源：` 行给出 URL。
2. 官方文档没有给出可直接执行命令的步骤，只写「官方文档未提供可直接执行的命令」，并只陈述流程、判据、注意事项 —— 不补写任何自造代码。
3. `scripts/` 目录本技能未创建：所需的现成脚本都由上游官方仓库提供（如 mosdepth 的 `scripts/plot-dist.py`、bcftools 的 `plot-vcfstats`、VEP 的 `filter_vep`），直接引用官方路径，不复制、不改写。
4. 本技能只覆盖种系（germline）短变异（SNP/INDEL ≤ 约 200 bp）。体细胞、CNV/SV、线粒体、亲子/家系联合分析不在本技能范围内。

## 何时使用

- 有 WES 或 WGS 的 FASTQ/uBAM/BAM，需要出种系 SNP/INDEL 的 VCF/GVCF。
- 需要判断：这批样本走 VQSR 还是硬过滤（关键门槛是外显子样本数是否 ≥ 30）。
- 需要 WES 的 capture 区间（BED/interval_list）如何进入 `-L`、`-ip`，以及覆盖度/均一性 QC 怎么做。
- 需要给出 `HaplotypeCaller → GVCF → GenomicsDBImport → GenotypeGVCFs` 的队列联合分型路径。
- 需要 VEP 的 `--cache` / `--offline` / `--plugin` 官方用法。

不属于本技能：单细胞、RNA-seq、甲基化、宏基因组、体细胞配对分析。

## 输入与前置

| 输入形态 | 进入点 | 说明（官方依据） |
| --- | --- | --- |
| FASTQ（R1/R2） | 阶段 1 读组 → 阶段 2 比对 | BWA-MEM2 用法与 bwa mem 完全相同（bwa-mem2 README） |
| uBAM（未比对 BAM） | 阶段 1 读组 → 阶段 2 比对 | GATK 生产流程即 uBAM → GVCF（germline 方法文章） |
| 已比对、已排序 BAM | 阶段 3 去重 | MarkDuplicates 要求输入 coordinate sorted（MarkDuplicates 文档） |

参考基因组必备四件套：

```bash
samtools faidx ref.fasta
samtools dict ref.fasta
```
来源：https://www.htslib.org/doc/samtools-faidx.html 、 https://www.htslib.org/doc/samtools-dict.html

```bash
bwa-mem2-2.2.1_x64-linux/bwa-mem2 index ref.fa
```
来源：https://github.com/bwa-mem2/bwa-mem2 （README「Getting Started」）
注意（官方 README 原文要点）：bwa-mem2 自 2020-10-10 起索引结构变更，「you will need to rebuild the index」；人类基因组索引磁盘占用约 10 GB、内存约 10 GB。

已知位点资源（BQSR 掩蔽 / VQSR 训练）：

- 官方资源桶：`gs://gcp-public-data--broad-references/hg38/v0`，浏览器入口 https://console.cloud.google.com/storage/browser/gcp-public-data--broad-references/hg38/v0
  来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035890811-Resource-bundle
- 官方明确的两点限制（同一文章原文要点）：hg38 资源集「provided as-is, and its contents may still be incomplete」；「we are still missing the Hg38 version of the Broad's exome intervals」。→ GRCh38 做 WES 时，capture 区间应取自已用捕获试剂盒厂商，而不是 Broad 的 hg38 外显子列表。
- 已知位点三类资源（known / training / truth）的定义与可自举性：https://gatk.broadinstitute.org/hc/en-us/articles/360035890831-Known-variants-Training-resources-Truth-sets

## 阶段化流程

### 阶段 0：环境

GATK 4（官方两种方式，任选）：

```bash
docker pull broadinstitute/gatk:4.1.3.0
docker run -it broadinstitute/gatk:4.1.3.0
docker run -v ~/my_project:/gatk/my_data -it broadinstitute/gatk:4.1.3.0
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035889991--How-to-Run-GATK-in-a-Docker-container
官方同时说明：GATK 发布包解压后「There is no installation necessary in the traditional sense」，把含 jar 与启动脚本的目录放好即可（来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036194592-Getting-started-with-GATK4 ）。

Ensembl VEP：

```bash
git clone https://github.com/Ensembl/ensembl-vep.git
cd ensembl-vep
perl INSTALL.pl
perl INSTALL.pl --AUTO ac
perl INSTALL.pl -a p --PLUGINS list
perl INSTALL.pl -a p --PLUGINS all
perl INSTALL.pl -a p --PLUGINS dbNSFP,CADD,G2P
```
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_download.html
官方说明：`--AUTO` 的部件代号为 `a`(API+htslib) `l`(htslib only) `c`(cache) `f`(FASTA) `p`(plugins)；`--CACHEDIR` 改缓存目录后运行 VEP 必须加 `--dir_cache`；`--PLUGINSDIR` 同理对应 `--dir_plugins`。

bwa-mem2（官方推荐预编译二进制）：

```bash
curl -L https://github.com/bwa-mem2/bwa-mem2/releases/download/v2.2.1/bwa-mem2-2.2.1_x64-linux.tar.bz2 \
  | tar jxf -
```
来源：https://github.com/bwa-mem2/bwa-mem2

mosdepth：

```bash
docker pull quay.io/biocontainers/mosdepth:0.3.3--h37c5b7d_2
```
来源：https://github.com/brentp/mosdepth （README「Installation」；官方首选是 releases 静态二进制）

VerifyBamID2（污染估计）：

```bash
conda install -c bioconda verifybamid2
docker pull griffan/verifybamid2
```
来源：https://github.com/Griffan/VerifyBamID （README；可执行文件名是 `VerifyBamID`）

samtools / bcftools：官方文档未提供可直接执行的安装命令，按 htslib 官网 Download 页安装（https://www.htslib.org/download/ ）。

### 阶段 1：读组校正（AddOrReplaceReadGroups）

```bash
java -jar picard.jar AddOrReplaceReadGroups \
      I=input.bam \
      O=output.bam \
      RGID=4 \
      RGLB=lib1 \
      RGPL=ILLUMINA \
      RGPU=unit1 \
      RGSM=20
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-AddOrReplaceReadGroups-Picard
（该页只给出 `java -jar picard.jar` 形式；GATK4 启动脚本形式的同一工具命令官方未在该页给出。）

官方 caveats（原文要点，必须遵守）：
- RG 标签值须匹配 `'^[ -~]+$'`（ASCII 32–126），空格是唯一允许的非打印字符。
- 该工具只能把整个输入文件指派给**一个** read group；若文件本来有多个 RG，原 RG 值会丢失。
- 该页把 RGID/RGLB/RGPL/RGPU/RGSM 的默认值都标为 `null`，即必须显式给出。

为什么必须做：BQSR「is read-group aware」，按 @RG 分区建模；官方期望每个 read group 「more than 100M bases」（来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR ）。

### 阶段 2：比对（BWA-MEM2）

```bash
bwa-mem2-2.2.1_x64-linux/bwa-mem2 mem ref.fa read1.fq read2.fq > out.sam
./bwa-mem2 mem -t <num_threads> <prefix> <reads.fq/fa> > out.sam
```
来源：https://github.com/bwa-mem2/bwa-mem2 （README「Getting Started」/「Usage」）

比对时直接写读组（bwa-mem2 官方声明其用法与 bwa mem 完全一致，读组写法取自 htslib 官方流程）：

```bash
bwa mem -R '@RG\tID:foo\tSM:bar\tLB:library1' <ref.fa> <read1.fa> <read1.fa> > lane.sam
```
来源：https://www.htslib.org/workflow/wgs-call.html
（该页原文强调 SM 必须是样本名、LB 必须是文库名；页内 GATK3 的 IndelRealigner 段属旧流程，不要沿用。）

### 阶段 3：排序与去重

Picard MarkDuplicates（GATK 生态主线）：

```bash
java -jar picard.jar MarkDuplicates \
      I=input.bam \
      O=marked_duplicates.bam \
      M=marked_dup_metrics.txt
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036756891-MarkDuplicates-Picard
官方默认值与前提（该页）：输入「Must be coordinate sorted」；`REMOVE_DUPLICATES=false`（只打 flag，不删读段）；`TAGGING_POLICY=DontTag`；`OPTICAL_DUPLICATE_PIXEL_DISTANCE=100`，而「For the patterned flowcell models, 2500 is more appropriate」；`VALIDATION_STRINGENCY=STRICT`；`CREATE_INDEX=false`。

samtools 替代路线（官方四步 + 免中间文件管道）：

```bash
samtools collate -o namecollate.bam example.bam
samtools fixmate -m namecollate.bam fixmate.bam
samtools sort -o positionsort.bam fixmate.bam
samtools markdup positionsort.bam markdup.bam
```
```bash
samtools collate -@ 4 -O -u example.bam | samtools fixmate -@ 4 -m -u - - | samtools sort -@ 4 -u - | samtools markdup -@ 4 - markdup.bam
samtools markdup -@ 4 -f stats_file.txt -S -d 2500 --mode s --include-fails positionsort.bam markdup.bam
```
来源：https://www.htslib.org/algorithms/duplicate.html
（上面第三条命令是官方给出的「与 Picard MarkDuplicates 结果相似」的光学重复设置：`-d 2500 --mode s --include-fails`。官方给出的光学距离建议：HiSeq 100、NovaSeq 2500。）

排序/索引的官方用法：

```bash
samtools sort -O bam -o <lane_sorted.bam> -T </tmp/lane_temp> <lane_fixmate.sam>
samtools index <sample.bam>
```
来源：https://www.htslib.org/workflow/wgs-call.html 、 https://www.htslib.org/doc/samtools-index.html
去重后重建索引（`samtools index marked_duplicates.bam`）—— 排序/索引命令取自上面两条官方文档，本条为按同一命令的常规落地，官方未单独为「去重后」写一句。

### 阶段 4：BQSR（可选）

```bash
gatk BaseRecalibrator \
  -I my_reads.bam \
  -R reference.fasta \
  --known-sites sites_of_variation.vcf \
  --known-sites another/optional/setOfSitesToMask.vcf \
  -O recal_data.table
```
```bash
gatk ApplyBQSR \
  -R reference.fasta \
  -I input.bam \
  --bqsr-recal-file recalibration.table \
  -O output.bam
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator 、 https://gatk.broadinstitute.org/hc/en-us/articles/360037268511-ApplyBQSR
官方约束：`ApplyBQSR` 只能用**同一个** BAM 产生的 table（原文：「You should only run ApplyBQSR with the covariates table created from the input BAM or CRAM file(s).」）；`--emit-original-quals` 可把原始质量写进 OQ。

GRCh38 已知位点集：

- 直接使用资源桶 hg38/v0 中的 dbSNP138、Mills_and_1000G_gold_standard.indels、1000G 高置信 SNP 等文件作为多个 `--known-sites`。官方对「当前最佳已知 indel 集合」的原文是「use both files」，即 1000G phase1 indels 与 Mills_and_1000G gold-standard indels 两个文件都要传（来源：Resource bundle 文的 b37 资源清单；hg38 版本对应 hg38/v0 桶内同名文件）。
- 什么时候可以跳过 BQSR：官方原文「The main case figure where you really might need to skip BQSR is when you have too little data (some small gene panels have that problem)」，以及数据量远低于每 read group 100M bases 时建模不可靠（BQSR 文章）。
- 没有已知位点集时（非模式生物）：官方给出的是**流程**而非命令 —— ① 先在不重校准数据上做一轮变异检测；② 取置信度最高的变异作为「已知位点」VCF 喂给 BaseRecalibrator；③ 用重校准后的数据再做一轮检测；可迭代至收敛。**官方文档未提供可直接执行的命令**，且官方指出这类自举集合「difficult to bootstrap」（Training resources 文对 training set 的说明）。

`-qq` 量化：官方说明默认不量化，`-qq 0` 不量化、`-qq N` 用 N 个 bin 重算（BQSR 文章）。

### 阶段 5：HaplotypeCaller 产出 GVCF

```bash
gatk --java-options "-Xmx4g" HaplotypeCaller  \
  -R Homo_sapiens_assembly38.fasta \
  -I input.bam \
  -O output.g.vcf.gz \
  -ERC GVCF
```
等位基因特异注释版本：
```bash
gatk --java-options "-Xmx4g" HaplotypeCaller  \
  -R Homo_sapiens_assembly38.fasta \
  -I input.bam \
  -O output.g.vcf.gz \
  -ERC GVCF \
  -G Standard \
  -G AS_Standard
```
直接出 VCF（单样本、不做联合分型）：
```bash
gatk --java-options "-Xmx4g" HaplotypeCaller  \
  -R Homo_sapiens_assembly38.fasta \
  -I input.bam \
  -O output.vcf.gz \
  -bamout bamout.bam
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller

官方要点（同页）：
- `-ERC GVCF` / `-ERC BP_RESOLUTION` 模式下 calling 置信阈值被自动设为 0，**命令行无法覆盖**；该阈值要留到 GenotypeGVCFs 阶段设。
- PCR-free 数据要设 `-pcr_indel_model NONE`。
- 「We recommend using a list of intervals to speed up analysis.」
- 输出是未过滤的 raw calls，必须经 VQSR 或硬过滤后使用。

WES：把 capture 区间传给 caller

（**组合说明**：`-R/-I/-O/-ERC GVCF` 与 `-ip` 的取值范围来自 HaplotypeCaller 官方用法示例与参数表；`-L/-ip` 的语义与「靶向测序加 100 bp」来自 Intervals 文章。官方 HaplotypeCaller 页没有给出带 `-L/-ip` 的现成命令。）

```bash
gatk --java-options "-Xmx4g" HaplotypeCaller \
  -R Homo_sapiens_assembly38.fasta \
  -I sample.dedup.bam \
  -L capture_targets.interval_list \
  -ip 100 \
  -ERC GVCF \
  -O sample.g.vcf.gz
```
来源（参数语义与生产惯例）：https://gatk.broadinstitute.org/hc/en-us/articles/360035531852-Intervals-and-interval-lists
- `-L/--intervals` 指定包含区间；`-ip/--interval-padding` 给包含区间加 padding（bp）；`-XL`、`-ixp` 为排除侧同义参数。
- 官方原文：「When we use intervals in our production pipelines with targeted sequencing, we make sure to give sufficient padding around the targeted sites (100 bp on each side).」——这是 100 bp 的官方出处。
- `--interval-padding` 的**默认值是 0**（HaplotypeCaller 参数表），即不显式给 `-ip` 就不会加 padding。
- 区间格式：Picard `.interval_list`（推荐，带序列字典、1-based）、GATK `.list`、BED（起始 0-based）、VCF 均可 `-L`；区间必须按坐标排序并与字典顺序一致。

### 阶段 6：队列联合分型（GenomicsDBImport + GenotypeGVCFs）

逐个 GVCF：
```bash
gatk --java-options "-Xmx4g -Xms4g" GenomicsDBImport \
  -V data/gvcfs/mother.g.vcf.gz \
  -V data/gvcfs/father.g.vcf.gz \
  -V data/gvcfs/son.g.vcf.gz \
  --genomicsdb-workspace-path my_database \
  --tmp-dir=/path/to/large/tmp \
  -L 20
```
用 sample map（大规模队列）：
```bash
gatk --java-options "-Xmx4g -Xms4g" \
   GenomicsDBImport \
   --genomicsdb-workspace-path my_database \
   --batch-size 50 \
   -L chr1:1000-10000 \
   --sample-name-map cohort.sample_map \
   --tmp-dir=/path/to/large/tmp \
   --reader-threads 5
```
sample map 是两列 tab 分隔（sample_name --tab-- path_to_sample_vcf）。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport

官方 caveats（同页，逐条都会咬人）：
- `-Xmx` 必须比物理内存少几 GB，因为原生 TileDB 还要额外内存。
- 至少给一个 interval。
- 输入 GVCF 不能对同一基因组位置有多条记录。
- `--genomicsdb-workspace-path` 必须指向不存在或空的目录。
- 临时盘可能不够，用 `--tmp-dir` 指到大盘。
- 默认 `--batch-size 0`（不分批，全部样本 reader 同时打开）、`--reader-threads 1`。

```bash
gatk --java-options "-Xmx4g" GenotypeGVCFs \
  -R Homo_sapiens_assembly38.fasta \
  -V gendb://my_database \
  -O output.vcf.gz
```
单样本/合并 GVCF：
```bash
gatk --java-options "-Xmx4g" GenotypeGVCFs \
  -R Homo_sapiens_assembly38.fasta \
  -V input.g.vcf.gz \
  -O output.vcf.gz
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs
官方 caveats：只接受 HaplotypeCaller（或 CombineGVCFs）产生的 GVCF；**一次只能传一个 GVCF**（多文件必须先 import/combine）。默认值：`-stand-call-conf 10.0`、`-G [StandardAnnotation]`、`-D null`。

队列增长的官方说法：GenotypeGVCFs 很快，「can be rerun at any point when samples are added to the cohort」，解决了 N+1 问题（来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels- ）。

### 阶段 7：过滤（两套官方阈值，二选一）

判断规则（官方）：VQSR 需要高质量训练/真值资源，并且**外显子样本数少于 30 个时不适用**；这种情况下改用 VariantFiltration 硬过滤（来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants 、 https://gatk.broadinstitute.org/hc/en-us/articles/360035532412-Can-t-use-VQSR-on-non-model-organism-or-small-dataset ）。

#### 7A 路线一：VQSR（队列 ≥ 30 外显子，或 WGS 大队列）

整套命令逐字取自官方「broad-prod-wgs-germline-snps-indels 1.1.1」流程说明，来源：
https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering

① 大样本队列先按 ExcessHet 硬过滤（官方阈值 54.69，对应 z=-4.5）：
```bash
gatk --java-options "-Xmx3g -Xms3g" VariantFiltration \
    -V cohort.vcf.gz \
    --filter-expression "ExcessHet > 54.69" \
    --filter-name ExcessHet \
    -O cohort_excesshet.vcf.gz
```
② 转 sites-only，加速建模：
```bash
gatk MakeSitesOnlyVcf \
    -I cohort_excesshet.vcf.gz \
    -O cohort_sitesonly.vcf.gz
```
③ INDEL 的 VQSLOD tranche：
```bash
gatk --java-options "-Xmx24g -Xms24g" VariantRecalibrator \
    -V cohort_sitesonly.vcf.gz \
    --trust-all-polymorphic \
    -tranche 100.0 -tranche 99.95 -tranche 99.9 -tranche 99.5 -tranche 99.0 -tranche 97.0 -tranche 96.0 -tranche 95.0 -tranche 94.0 -tranche 93.5 -tranche 93.0 -tranche 92.0 -tranche 91.0 -tranche 90.0 \
    -an FS -an ReadPosRankSum -an MQRankSum -an QD -an SOR -an DP \
    -mode INDEL \
    --max-gaussians 4 \
    -resource:mills,known=false,training=true,truth=true,prior=12:Mills_and_1000G_gold_standard.indels.hg38.vcf.gz \
    -resource:axiomPoly,known=false,training=true,truth=false,prior=10:Axiom_Exome_Plus.genotypes.all_populations.poly.hg38.vcf.gz \
    -resource:dbsnp,known=true,training=false,truth=false,prior=2:Homo_sapiens_assembly38.dbsnp138.vcf \
    -O cohort_indels.recal \
    --tranches-file cohort_indels.tranches
```
④ SNP 的 VQSLOD tranche：
```bash
gatk --java-options "-Xmx3g -Xms3g" VariantRecalibrator \
    -V cohort_sitesonly.vcf.gz \
    --trust-all-polymorphic \
    -tranche 100.0 -tranche 99.95 -tranche 99.9 -tranche 99.8 -tranche 99.6 -tranche 99.5 -tranche 99.4 -tranche 99.3 -tranche 99.0 -tranche 98.0 -tranche 97.0 -tranche 90.0 \
    -an QD -an MQRankSum -an ReadPosRankSum -an FS -an MQ -an SOR -an DP \
    -mode SNP \
    --max-gaussians 6 \
    -resource:hapmap,known=false,training=true,truth=true,prior=15:hapmap_3.3.hg38.vcf.gz \
    -resource:omni,known=false,training=true,truth=true,prior=12:1000G_omni2.5.hg38.vcf.gz \
    -resource:1000G,known=false,training=true,truth=false,prior=10:1000G_phase1.snps.high_confidence.hg38.vcf.gz \
    -resource:dbsnp,known=true,training=false,truth=false,prior=7:Homo_sapiens_assembly38.dbsnp138.vcf \
    -O cohort_snps.recal \
    --tranches-file cohort_snps.tranches
```
⑤ 依次套 INDEL、SNP 的重校准结果：
```bash
gatk --java-options "-Xmx5g -Xms5g" \
    ApplyVQSR \
    -V cohort_excesshet.vcf.gz \
    --recal-file cohort_indels.recal \
    --tranches-file cohort_indels.tranches \
    --truth-sensitivity-filter-level 99.7 \
    --create-output-variant-index true \
    -mode INDEL \
    -O indel.recalibrated.vcf.gz
```
```bash
gatk --java-options "-Xmx5g -Xms5g" \
    ApplyVQSR \
    -V indel.recalibrated.vcf.gz \
    --recal-file ${snps_recalibration} \
    --tranches-file ${snps_tranches} \
    --truth-sensitivity-filter-level 99.7 \
    --create-output-variant-index true \
    -mode SNP \
    -O snp.recalibrated.vcf.gz
```

WES 走 VQSR 时必须改的地方（官方「Which training sets arguments should I use for running VQSR?」，https://gatk.broadinstitute.org/hc/en-us/articles/4402736812443-Which-training-sets-arguments-should-I-use-for-running-VQSR ）：
- **不要用 DP 注释**：官方原文「Depth of coverage (the DP annotation) should not be used when working with exome datasets since there is extreme variation in the depth to which targets are captured」。上面 7A③④ 的命令来自 WGS 生产流程、含 `-an DP`，做 WES 时须去掉。
- `-an InbreedingCoeff` 只在样本数 ≥ 10 时可用，少于 10 个样本要去掉。
- 官方推荐 tranche：SNP `--ts_filter_level 99.5`、INDEL `--ts_filter_level 99.0`（原文命令片段 `--ts_filter_level 99.5 -mode SNP` / `--ts_filter_level 99.0 -mode INDEL`）。
- 外显子样本 < 30 时的官方出路：补样本（如用 1000 Genomes 的 BAM 重新生成 GVCF 一起联合分型，**不能直接拿别人的 VCF**），或对小 callset 试 `--maxGaussians 4`。
- 参数默认值：`VariantRecalibrator --mode SNP`、`--max-gaussians 8`、`--trust-all-polymorphic false`（来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036348332-VariantRecalibrator ）。

#### 7B 路线二：硬过滤（外显子 < 30 例、panel、非模式生物）

① 按类型拆分：
```bash
gatk SelectVariants \
    -V cohort.vcf.gz \
    -select-type SNP \
    -O snps.vcf.gz
```
```bash
gatk SelectVariants \
    -V cohort.vcf.gz \
    -select-type INDEL \
    -O indels.vcf.gz
```
② SNP 硬过滤阈值（官方「basic filtering thresholds researchers may find useful to start」）：
```bash
gatk VariantFiltration \
    -V snps.vcf.gz \
    -filter "QD < 2.0" --filter-name "QD2" \
    -filter "QUAL < 30.0" --filter-name "QUAL30" \
    -filter "SOR > 3.0" --filter-name "SOR3" \
    -filter "FS > 60.0" --filter-name "FS60" \
    -filter "MQ < 40.0" --filter-name "MQ40" \
    -filter "MQRankSum < -12.5" --filter-name "MQRankSum-12.5" \
    -filter "ReadPosRankSum < -8.0" --filter-name "ReadPosRankSum-8" \
    -O snps_filtered.vcf.gz
```
③ INDEL 硬过滤阈值：
```bash
gatk VariantFiltration \
    -V indels.vcf.gz \
    -filter "QD < 2.0" --filter-name "QD2" \
    -filter "QUAL < 30.0" --filter-name "QUAL30" \
    -filter "FS > 200.0" --filter-name "FS200" \
    -filter "ReadPosRankSum < -20.0" --filter-name "ReadPosRankSum-20" \
    -O indels_filtered.vcf.gz
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering

官方另一份「无路可走时」的通用阈值（含 INDEL 的 `SOR > 10.0`、`InbreedingCoeff < -0.8`）：
https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants
- SNP：`QD < 2.0`、`MQ < 40.0`、`FS > 60.0`、`SOR > 3.0`、`MQRankSum < -12.5`、`ReadPosRankSum < -8.0`
- INDEL：`QD < 2.0`、`ReadPosRankSum < -20.0`、`InbreedingCoeff < -0.8`、`FS > 200.0`、`SOR > 10.0`
- 官方明确：`InbreedingCoeff` 需要 ≥ 10 个样本；**外显子不要用 DP 上限过滤**；覆盖度 < 10x 时手工阈值几乎不可能可靠区分真假。

硬过滤的三条硬性注意事项（官方原文）：
- 表达式要**一条一个属性**分别给 `-filter`/`--filter-name`；不要写 `||`/`&&` 复合式，否则缺某注释的记录会被整体判 PASS。
- 阈值字面量类型必须与 INFO 定义一致（Integer 写 `2`、Float 写 `2.0`），否则 `java.lang.NumberFormatException`。
- 过滤表达式拼错时工具**不报警**，必须人工复核。

### 阶段 8：规范化（LeftAlignAndTrimVariants / bcftools norm）

```bash
gatk LeftAlignAndTrimVariants \
   -R reference.fasta \
   -V input.vcf \
   -O output.vcf
```
```bash
gatk LeftAlignAndTrimVariants \
   -R reference.fasta \
   -V input.vcf \
   -O output.vcf \
   --split-multi-allelics \
   --dont-trim-alleles \
   --keep-original-ac
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/4405443605531-LeftAlignAndTrimVariants
默认值（同页）：`--max-indel-length 200`、`--max-leading-bases 1000`、`--split-multi-allelics false`、`--dont-trim-alleles false`、`--keep-original-ac false`。

bcftools 路线（**组合说明**：官方 man page 的示例只给出 `bcftools norm [OPTIONS] file.vcf.gz`，下面是把官方 `-f`/`-m`/`-O` 选项拼在一起，路径用占位符）：

```bash
bcftools norm -f [REF_FASTA] -m -any -Oz -o normalized.vcf.gz input.vcf.gz
```
来源：https://samtools.github.io/bcftools/bcftools.html （`norm`）
- `-f, --fasta-ref FILE`：提供参考即**开启左对齐与规范化**（原文：「Supplying this option will turn on left-alignment and normalization」）。
- `-m, --multiallelics -|+[snps|indels|both|any]`：拆分/合并多等位。
- `-c, --check-ref e|w|x|s`：REF 不符时的处理（exit/warn/exclude/set-fix）。
- `-d, --rm-dup snps|indels|both|all|exact`：去重复记录。

### 阶段 9：注释（Ensembl VEP）

最小可用命令（官方默认示例）：

```bash
./vep --cache -i input.txt -o output.txt
```
生产级 VCF 注释（**这是按官方 options 页逐项拼接的命令，不是官方逐字示例**；每个选项的语义与默认值均来自 https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html ，路径一律用占位符）：

```bash
./vep --offline --cache --assembly GRCh38 \
      --dir_cache [VEP_CACHE_DIR] \
      --fasta [REF_FASTA] \
      --vcf --everything --check_existing --af_gnomad --af_gnomade --af_gnomadg \
      --hgvs --symbol --mane --canonical --biotype --numbers \
      --fork [N_FORKS] --buffer_size 5000 --force_overwrite \
      -i normalized.vcf.gz -o annotated.vcf
```
官方逐字示例只有一条：`./vep --cache -i input.txt -o output.txt`。
参数含义（官方原文要点）：
- `--cache` 用本地缓存；`--offline` 完全不连数据库，必须有 cache 或 GFF/GTF；二者与 `--database` 互斥。
- `--dir_cache` 默认 `$HOME/.vep/`；`--dir_plugins` 默认同上；`--dir` 是两者共同基目录。
- `--fasta` 在 `--offline` 下取 HGVS（`--hgvs`）或做参考校验（`--check_ref`）**必需**。
- `--fork` 多进程加速；`--buffer_size` 默认 5000（调低省内存、调高提速）。
- `--everything` 是 `--sift b --polyphen b --ccds --hgvs --symbol --numbers --domains --regulatory --canonical --protein --biotype --af --af_1kg --af_gnomade --af_gnomadg --max_af --pubmed --uniprot --mane --tsl --appris --variant_class --gene_phenotype --mirna` 的合集。
- `--vcf` 把结果写进 INFO/CSQ，`--pick`/`--most_severe`/`--per_gene` 控制每变异保留几行。
- 输出已存在会直接报错，需要 `--force_overwrite`；输入未排序要 `--no_check_variants_order`（会更慢更吃内存）。

`--plugin` 用法：
```bash
./vep ... --plugin <plugin_name>
```
官方 options 页只给到 `--plugin [plugin name]`（同一 `--plugin` 可重复多次），并指向插件专页；各插件的具体参数（如 LoF、dbNSFP、CADD 的路径/版本参数）在插件页 https://asia.ensembl.org/info/docs/tools/vep/script/vep_plugins.html ，本技能不臆造插件参数。
插件安装用 `perl INSTALL.pl -a p --PLUGINS <name>`（见阶段 0）。

### 阶段 10：WES 特有 QC（capture 区间、覆盖度、均一性）

CollectHsMetrics（官方要求 bait 与 target 两份 interval_list，来自捕获试剂盒厂商）：

```bash
java -jar picard.jar CollectHsMetrics \
      I=input_reads.bam \
      O=output_hs_metrics.txt \
      R=reference.fasta \
      BAIT_INTERVALS=bait.interval_list \
      TARGET_INTERVALS=target.interval_list
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036714891-CollectHsMetrics-Picard
- BED 需先转 interval_list：官方原文指向「Picard's BedToInterval tool」（同页）；本技能未抓取该工具页，**官方文档未在此提供可直接执行的命令**。
- 默认值（同页）：`NEAR_DISTANCE 250`、`MINIMUM_MAPPING_QUALITY 20`、`MINIMUM_BASE_QUALITY 20`、`COVERAGE_CAP 200`、`CLIP_OVERLAPPING_READS true`、`METRIC_ACCUMULATION_LEVEL [ALL_READS]`；`PER_TARGET_COVERAGE` 默认不输出，需要逐靶标覆盖时显式给文件名。
- 指标定义（官方 metric definitions，https://broadinstitute.github.io/picard/picard-metric-definitions.html ）：
  `MEAN_TARGET_COVERAGE`、`MEDIAN_TARGET_COVERAGE`、`PCT_TARGET_BASES_30X`（≥30x 的靶标碱基比例）、`PCT_TARGET_BASES_20X`、`FOLD_80_BASE_PENALTY`（把 80% 的「非零覆盖」靶标抬到均值所需的多余倍数，即均一性指标）、`PCT_SELECTED_BASES`、`PCT_USABLE_BASES_ON_TARGET`、`FOLD_ENRICHMENT`、`AT_DROPOUT`/`GC_DROPOUT`、`PCT_CHIMERAS`。

mosdepth（逐区间/逐窗口深度）：

```bash
mosdepth --by capture.bed sample-output sample.exome.bam
mosdepth -n --fast-mode --by 500 sample.wgs $sample.wgs.cram
mosdepth -n --quantize 0:1:5:150: $sample.quantized $sample.wgs.bam
```
来源：https://github.com/brentp/mosdepth
- `-b/--by` 收 BED 或窗口 bp；`-n` 不写 per-base（快很多）；`-x --fast-mode` 忽略 CIGAR 内部操作与 mate overlap 修正（官方推荐多数场景）；`-T/--thresholds` 可对每个 `--by` 区间输出「至少 N 个碱基覆盖」的碱基数（如 `-T 1,10,20,30`）。
- 输出 `{prefix}.mosdepth.global.dist.txt`（累积分布，按染色体与 total）、`.mosdepth.summary.txt`、`.regions.bed.gz`（给了 `--by` 时）、`.thresholds.bed.gz`（给了 `--thresholds` 时）。
- 官方提供绘图脚本 `scripts/plot-dist.py`（用法 `python scripts/plot-dist.py *global.dist.txt`，输出 `dist.html`）—— 直接引用官方路径，不复制。

均一性判定：官方只给出 `FOLD_80_BASE_PENALTY`、`PCT_TARGET_BASES_30X` 这类指标的定义，**没有给出统一的通过阈值**；阈值需按项目/试剂盒自定，并在报告里写明所采用的阈值来源（通常来自试剂盒厂商或实验室 SOP）。

### 阶段 11：过滤后评估

```bash
gatk CollectVariantCallingMetrics \
    -I filtered.vcf.gz \
    --DBSNP Homo_sapiens_assembly38.dbsnp138.vcf \
    -SD Homo_sapiens_assembly38.dict \
    -O metrics
```
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering
官方：summary 给队列级、detail 给每样本级指标（指标定义见 Picard metric definitions）。同页另给 VariantEval（GATK3 形式）与 hap.py 的建议；GATK4 下 VariantEval 当时仍是 beta。

bcftools 侧统计：

```bash
bcftools stats -F <ref.fa> -s - <study.vcf.gz> > <study.vcf.gz.stats>
plot-vcfstats -p plots/ <study.vcf.gz.stats>
bcftools filter -O z -o <study_filtered..vcf.gz> -s LOWQUAL -i'%QUAL>10' <study.vcf.gz>
```
来源：https://www.htslib.org/workflow/wgs-call.html

## QC 指标清单

| 指标 | 官方取值位置 | 备注 |
| --- | --- | --- |
| 目标区平均深度 / ≥30x 比例 | `CollectHsMetrics` 的 `MEAN_TARGET_COVERAGE`、`PCT_TARGET_BASES_30X` | 定义见 Picard metric definitions |
| 均一性 | `FOLD_80_BASE_PENALTY` | 官方未给阈值 |
| 逐区间/累积深度分布 | `mosdepth` 的 `.regions.bed.gz` / `.mosdepth.global.dist.txt` | 官方格式说明见 mosdepth README |
| dup rate、文库复杂度 | `MarkDuplicates` 的 `PERCENT_DUPLICATION`、`ESTIMATED_LIBRARY_SIZE` | 指标定义见 Picard metric definitions |
| Ti/Tv | `CollectVariantCallingMetrics` 汇总指标 | 命令见阶段 11，指标说明指向 Picard metric definitions |
| 变异计数/样本级基因型计数、单例统计 | `bcftools stats`（官方描述含 per-sample counts、singleton stats、depth distribution） | 官方未给通过阈值 |
| 污染 | VerifyBamID2 的 `.selfSM` 中 `FREEMIX` | 官方原文：「the key information FREEMIX indicates the estimated contamination level」 |
| 碱基质量改善 | BQSR 的 comparison 报告 | 官方称可选但强烈推荐（BQSR 文章） |

VerifyBamID2（GRCh38，带 chr 前缀的 1000G 版本）：

```bash
$(VERIFY_BAM_ID_HOME)/bin/VerifyBamID \
  --SVDPrefix $(VERIFY_BAM_ID_HOME)/resource/1000g.100k.b38.vcf.gz.dat \
  --Reference [/path/to//GRCh38_full_analysis_set_plus_decoy_hla.fa] \
  --BamFile [/path/to/bam/or/cram/file] 
```
来源：https://github.com/Griffan/VerifyBamID
（GRCh37 版本用 `--UDPath/--BedPath/--MeanPath` 三件套 + 不带 chr 前缀的 `human_g1k_v37.fasta`，同页给出。输出侧另有 `Ancestry` 文件记录 PC 坐标。）

## 参数速查（详见 references/parameters.md）

最常改的六个：`--known-sites`（BQSR 资源集）、`-L/-ip`（WES capture 区间与 padding）、`-ERC GVCF`、`--max-gaussians`、`--truth-sensitivity-filter-level`、VEP 的 `--assembly/--dir_cache/--fasta/--fork`。

默认值里最容易踩的三个：`HaplotypeCaller --interval-padding 0`、`MarkDuplicates OPTICAL_DUPLICATE_PIXEL_DISTANCE 100`（patterned flowcell 应为 2500）、`GenotypeGVCFs -stand-call-conf 10.0`。

## 产出目录（本技能约定，非官方要求）

```
<project>/
├─ 00_ref/                    ref.fa, ref.fa.fai, ref.dict, bwa-mem2 index, capture.interval_list
├─ 01_fastq/                  原始 FASTQ
├─ 02_rg/                     *.rg.bam（AddOrReplaceReadGroups）
├─ 03_align/                  *.sorted.bam, *.sorted.bam.bai
├─ 04_dedup/                  *.dedup.bam, *.dup_metrics.txt
├─ 05_bqsr/                   *.recal.table, *.recal.bam
├─ 06_gvcf/                   *.g.vcf.gz (+ .tbi)
├─ 07_genomicsdb/             workspace 目录
├─ 08_raw_vcf/                cohort.vcf.gz（GenotypeGVCFs 输出）
├─ 09_filter/                 *.recal/.tranches 或 *_filtered.vcf.gz
├─ 10_norm/                   normalized.vcf.gz
├─ 11_annot/                  annotated.vcf(.gz) + vep 摘要 html
└─ 12_qc/                     hs_metrics.txt, mosdepth.*, *.selfSM, variant_metrics.*, *.stats
```

## 验收清单

- [ ] ref.fa 有 `.fai` 与 `.dict`，且 dict 的 contig 名与 BAM/VCF 完全一致（`chr` 前缀是否统一）。
- [ ] 每个 BAM 都有且只有一个 read group，`SM` 是样本名、`LB` 是文库名（否则 BQSR 与联合分型会串样）。
- [ ] 去重发生在排序之后（`MarkDuplicates` 输入 coordinate sorted），去重后索引已重建。
- [ ] BQSR 的 table 与 BAM 一一对应；跳过的样本有书面理由。
- [ ] GVCF 由 HaplotypeCaller 产生；GenomicsDBImport 每个 interval/workspace 目录为空原状。
- [ ] 过滤路线与样本量匹配：外显子 ≥30 可 VQSR 且去掉 `-an DP`；<30 走硬过滤并写明阈值来源。
- [ ] 规范化后 REF 与参考一致（bcftools `-c` 或 VEP `--check_ref` 可查）。
- [ ] 注释用到的 VEP cache 版本、FASTA、插件版本都记进方法学。
- [ ] QC 表齐全：平均深度、≥30x 比例、FOLD_80、dup rate、Ti/Tv、样本级 het/hom、FREEMIX。

## 参考文件

- `references/official-docs.md` —— 每个工具的官方 URL、官方安装命令、该文档覆盖什么。
- `references/parameters.md` —— 参数 / 官方默认值 / 何时需要改 / 来源 URL。
- `references/troubleshooting.md` —— 常见报错与官方 FAQ/issue 的对应。
