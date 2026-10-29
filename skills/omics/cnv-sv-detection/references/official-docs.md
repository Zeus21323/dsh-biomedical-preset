# 官方文档逐字摘录与来源

本文件只收录**从官方文档抓取并逐字保留**的命令、参数与判据。每条命令后附来源 URL；未标注来源的命令一律不存在于本技能。

抓取时间：2026-10-29（Asia/Shanghai）。
CNVkit 文档版本：0.9.8（页面 revision `b218280e`）。Manta：v1.6.0 userGuide。Delly：main 分支 README。VEP：Ensembl release 116 / jun2026 archive。

---

## 1. CNVkit 0.9.8

### 1.1 安装与快速入门

来源：https://cnvkit.readthedocs.io/en/stable/quickstart.html

```
Download the source code from GitHub:
https://github.com/etal/cnvkit
```

需要从 UCSC 下载：1) 物种参考基因组 FASTA（必需）；2) 基因注释（RefSeq/Ensembl，BED 或 RefFlat 格式，如 `refFlat.txt`，可选）。

官方完整 `batch` 命令（Tumor/Normal）：

```bash
cnvkit.py batch *Tumor.bam --normal *Normal.bam \
    --targets my_baits.bed --fasta hg19.fasta \
    --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_reference.cnn --output-dir example/
```

平参考（无正常样本）：

```bash
cnvkit.py batch *Tumor.bam -n -t my_baits.bed -f hg19.fasta \
    --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_flat_reference.cnn -d example2/
```

加基因名：

```bash
cnvkit.py batch *Tumor.bam -n *Normal.bam -t my_baits.bed -f hg19.fasta \
    --annotate refFlat.txt --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_flat_reference.cnn -d example3/
```

复用参考 + 并行 + 出图：

```bash
cnvkit.py batch *Tumor.bam -r my_reference.cnn -p 0 --scatter --diagram -d example4/
```

官方 BED 选择判据（原文要点）：
- hybrid capture 给 **bait/capture BED**（含目的区域两侧约 50bp），不要给 primary targets；
- WGS 用 `batch --method wgs`，可给「access」文件，不给则由 FASTA 现算；
- TAS 用 `batch --method amplicon` 并给 target BED。

### 1.2 主流程与各子命令

来源：https://cnvkit.readthedocs.io/en/stable/pipeline.html

`batch`（Tumor/Normal + 注释 + access + 参考输出 + 图）：

```bash
cnvkit.py batch *Tumor.bam --normal *Normal.bam \
    --targets my_baits.bed --annotate refFlat.txt \
    --fasta hg19.fasta --access data/access-5kb-mappable.hg19.bed \
    --output-reference my_reference.cnn --output-dir results/ \
    --diagram --scatter
```

复用参考：

```bash
cnvkit.py batch *Tumor.bam -r Reference.cnn -d results/
```

只建参考、不做分析（复用已有 targets/antitargets）：

```bash
cnvkit.py batch -n *Normal.bam --output-reference new_reference.cnn \
    -t my_targets.bed -a my_antitargets.bed \
    -f hg19.fasta -g data/access-5kb-mappable.hg19.bed
```

并行：

```bash
cnvkit.py batch *.bam -r my_reference.cnn -p 8
```

官方给出的「`batch` 等价命令序列」：

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

# Optionally, with --scatter and --diagram
cnvkit.py scatter Sample.cnr -s Sample.cns -o Sample-scatter.pdf
cnvkit.py diagram Sample.cnr -s Sample.cns -o Sample-diagram.pdf
```

`target`：

```bash
cnvkit.py target my_baits.bed --annotate refFlat.txt --split -o my_targets.bed
```

`access`：

```bash
cnvkit.py access hg19.fa -x excludes.bed -o access-excludes.hg19.bed
cnvkit.py access mm10.fasta -s 10000 -o access-10kb.mm10.bed
```

`antitarget`：

```bash
cnvkit.py antitarget my_targets.bed -g data/access-5kb-mappable.hg19.bed -o my_antitargets.bed
```

`autobin`：

```bash
cnvkit.py autobin *.bam -t my_targets.bed -g access.hg19.bed
cnvkit.py autobin *.bam -m amplicon -t my_targets.bed
cnvkit.py autobin *.bam -m wgs -b 50000 -g access.hg19.bed --annotate refFlat.txt
```

`coverage`：

```bash
cnvkit.py coverage Sample.bam targets.bed -o Sample.targetcoverage.cnn
cnvkit.py coverage Sample.bam antitargets.bed -o Sample.antitargetcoverage.cnn
```

`reference`（有对照 / 平参考）：

```bash
cnvkit.py reference *coverage.cnn -f ucsc.hg19.fa -o Reference.cnn
cnvkit.py reference -o FlatReference.cnn -f ucsc.hg19.fa -t targets.bed -a antitargets.bed
```

`fix`：

```bash
cnvkit.py fix Sample.targetcoverage.cnn Sample.antitargetcoverage.cnn Reference.cnn -o Sample.cnr
```

`segment`：

```bash
cnvkit.py segment Sample.cnr -o Sample.cns
```

`segment` 算法（`-m`）：`cbs`（默认，需 R DNAcopy）、`haar`、`hmm`、`hmm-tumor`、`hmm-germline`（三者实验性，需 pomegranate）、`none`。`-t/--threshold` 传底层方法的显著性阈值。

### 1.3 `call`

来源：https://cnvkit.readthedocs.io/en/stable/pipeline.html#call

```bash
cnvkit.py call Sample.cns -o Sample.call.cns
cnvkit.py call Sample.cns -y -m threshold -t=-1.1,-0.4,0.3,0.7 -o Sample.call.cns
cnvkit.py call Sample.cns -y -m clonal --purity 0.65 -o Sample.call.cns
cnvkit.py call Sample.cns -y -v Sample.vcf -m clonal --purity 0.7 -o Sample.call.cns
cnvkit.py call Sample.cns -y -v Sample.vcf -o Sample.call.cns
cnvkit.py call Sample.cns -v Sample.vcf --purity 0.8 -m none -o Sample.call.cns
cnvkit.py call -m none Sample.cns --center mode
```

默认阈值表（原文表格）：

| If log2 value is up to | Copy number |
| --- | --- |
| -1.1 | 0 |
| -0.4 | 1 |
| 0.3 | 2 |
| 0.7 | 3 |
| … | … |

官方算阈值的两种方式（原文代码，非本技能编写）：

```
>>> import numpy as np
>>> copy_nums = np.arange(5)
>>> print(np.log2((copy_nums+.5) / 2)
[-2.         -0.4150375   0.32192809  0.80735492  1.169925  ]
```

```
> log2( (0:4 + .5) / 2)
[1] -2.0000000 -0.4150375  0.3219281  0.8073549  1.1699250
> purity = 0.6
> ploidy = 4
> log2( (1 - purity) + purity * (0:6 + .5) / ploidy )
[1] -1.0740006 -0.6780719 -0.3677318 -0.1124747  0.1043367  0.2927817  0.4594316
```

过滤选项（原文列表）：整数拷贝数 `cn`（合并相邻同值段）、`ampdel`（仅保留 ≥5 拷贝扩增与 0 拷贝纯合缺失）、`ci`（置信区间跨零）、`sem`（均值标准误）。

### 1.4 WGS / TAS

来源：https://cnvkit.readthedocs.io/en/stable/nonhybrid.html

WGS：

```bash
cnvkit.py batch Sample1.bam Sample2.bam -n Control1.bam Control2.bam \
        -m wgs -f hg19.fasta --annotate refFlat.txt
```

TAS：

```bash
cnvkit.py batch -m amplicon -t targets.bed *.bam
```

TAS 等价命令（官方）：

```bash
cnvkit.py target targets.bed --split -o targets.split.bed
# Create a blank file to substitute for antitargets
touch MT
# For each sample
cnvkit.py coverage Sample.bam targets.split.bed -p 0 -o Sample.targetcoverage.cnn
cnvkit.py reference *.targetcoverage.cnn --no-edge -o ref-tas.cnn
cnvkit.py fix Sample.targetcoverage.cnn MT ref-tas.cnn --no-edge
```

WGS 优化项（原文要点，`batch -m wgs` 除第一条外自动执行）：限制到基因区；`--target-avg-size` 30x 时 ≥1000 bases；`segment -t` 用 `1e-6`（CBS）或改 `hmm`；`-p/--processes`；`--no-edge`。

TAS 注意：**不要**标记重复（MarkDuplicates/rmdup），因为扩增子 reads 本身就是设计上的 PCR 重复。

### 1.5 报告与 QC 命令

来源：https://cnvkit.readthedocs.io/en/stable/reports.html

`breaks`：

```bash
cnvkit.py breaks Sample.cnr Sample.cns
cnvkit.py breaks Sample.cnr Sample.cns | cut -f1 | sort -u > gene-breaks.txt
```

`genemetrics`：

```bash
cnvkit.py genemetrics Sample.cnr
cnvkit.py genemetrics Sample.cnr -s Sample.cns -t 0.4 -m 5 -y
cnvkit.py genemetrics -y Sample.cnr -s Sample.cns | tail -n+2 | cut -f1 | sort > segment-genes.txt
cnvkit.py genemetrics -y Sample.cnr | tail -n+2 | cut -f1 | sort > ratio-genes.txt
comm -12 ratio-genes.txt segment-genes.txt > trusted-genes.txt
```

`sex`：

```bash
cnvkit.py sex *.cnn *.cnr *.cns
cnvkit.py sex -y *.cnn *.cnr *.cns
cnvkit.py sex reference.cnn Sample.targetcoverage.cnn Sample.antitargetcoverage.cnn
```

`metrics`：

```bash
cnvkit.py metrics Sample.cnr -s Sample.cns
cnvkit.py metrics S1.cnr S2.cnr -s S1.cns S2.cns
cnvkit.py metrics *.cnr -s *.cns
cnvkit.py metrics Sample.targetcoverage.cnn Sample.antitargetcoverage.cnn Sample.cnr -s Sample.cns
```

`segmetrics`：

```bash
cnvkit.py segmetrics Sample.cnr -s Sample.cns --iqr
cnvkit.py segmetrics -s Sample.cn{s,r} --ci --pi
```

统计量：`--mean`/`--median`/`--mode`、`--std`、`--mad`、`--iqr`、`--bivar`、`--mse`、`--sem`、`--ci`（bootstrap 100 次重采样，输出 `ci_lo`/`ci_hi`）、`--pi`（2.5–97.5 百分位，输出 `pi_lo`/`pi_hi`）。

### 1.6 性别与倍性

来源：https://cnvkit.readthedocs.io/en/stable/sex.html

- 默认相对二倍体 X、单倍体 Y；男性输入样本的 X 覆盖度被加倍。
- `-y` / `--male-reference` / `--haploid-x-reference` 切到单倍体 X 参考；用 `-y` 建的参考，`call`、`export`、`genemetrics` 必须同样加 `-y`。
- `-x` / `--sample-sex` 覆盖自动性别推断，语义与 `-y` 不同。
- FAQ：女性样本对男性参考 → X 约 +1.0、Y 远低于 −3.0；男性样本对女性参考 → X 约 −1.0，Y 接近 0.0 但更噪。
- 低质量样本性别判断错误时：`segment --drop-low-coverage`（若原来没用）。

### 1.7 BAF

来源：https://cnvkit.readthedocs.io/en/stable/baf.html

- B 等位基因 = normal/control 中观测到的非参考等位基因；肿瘤中频率偏移相对 0.5 计算，并镜像到 0.5 上下。
- 官方例子：二倍体基因组的 3 拷贝片段 log2 = +0.58，杂合 SNP 平均 BAF 为 67% 或 33%（完全克隆）；存在正常细胞污染/肿瘤异质性时趋近 log2 0.0 与 BAF 0.5。
- 使用场景：`call`、`scatter`、`export nexus-ogt` 与 `export theta`。
- VCF 来源：tumor-normal 联合 SNV 调用（MuTect、VarDict、FreeBayes）并已标记体细胞突变；无配对正常时可用 1000 Genomes 常见 SNP 位点。

### 1.8 GC 与其它偏倚校正

来源：https://cnvkit.readthedocs.io/en/stable/bias.html

- `gc` 与 `rmask` 两列在 `reference` 阶段由用户提供的基因组计算；偏倚校正在 `reference` 与 `fix` 中执行。
- 方法是「按偏倚因子排序后取滚动中位数拟合趋势，再从观测 read depth 中减去」；同尺寸 target 很多时先随机打乱探针，避免偏倚估计依赖基因组位置。
- targeting density（shoulder/flank）只对 on-target bins 做校正。
- `--no-gc`、`--no-rmask`、`--no-edge` 必须前后一致，否则会过度/不足校正（pipeline.html#fix）。

### 1.9 tumor / germline 策略

来源：https://cnvkit.readthedocs.io/en/stable/tumor.html 、https://cnvkit.readthedocs.io/en/stable/germline.html

- `--drop-low-coverage`：忽略 log2 归一化覆盖度 < −15 的 bin；零覆盖占位值为 −20，参考归一化最大正向偏移为 5，故 < −15 的 bin 基本是零覆盖假值。该选项在 `batch`（作用于 segmentation）、`segment`、`metrics`、`segmetrics`、`genemetrics` 与异质性分析中可用。
- tumor：`batch` 不直接给整数拷贝数，需在 `call` 用 `--ploidy`/`--purity`；高异倍体可用 `--center median`；有 SNV VCF 时 `call` / `scatter` 加 `-v/--vcf`。
- germline：`call` 可直接用默认 purity/ploidy（哺乳类二倍体正确）；用 `--filter ci`（推荐）或 `sem` 降假阳性，`ci` 需先跑 `segmetrics --ci`；**不要**用 `--drop-low-coverage`。

### 1.10 导出（对接注释工具）

来源：https://cnvkit.readthedocs.io/en/stable/importexport.html#export

```bash
cnvkit.py call Sample.cns -y -o Sample.call.cns
cnvkit.py export bed Sample.call.cns --show all -y -o Sample.bed
cnvkit.py export bed Sample.call.cns -o all-samples.cnv-map.bed
cnvkit.py export vcf Sample.cns -y -x female -i "SampleID" -o Sample.cnv.vcf
cnvkit.py export seg *.cns -o Samples.seg
cnvkit.py export jtv *.cnr -o Samples-JTV.txt
cnvkit.py export cdt *.cnr -o Samples.cdt
```

其它导入：

```bash
cnvkit.py import-picard *.hsmetrics.targetcoverages.tsv *.hsmetrics.antitargetcoverages.csv
cnvkit.py import-picard picard-hsmetrics/ -d cnvkit-from-picard/
cnvkit.py import-theta Sample.cns Sample.BEST.results
cnvkit.py export theta Sample_Tumor.cns reference.cnn -o Sample.theta2.interval_count
cnvkit.py version
```

---

## 2. Manta（v1.6.0 User Guide）

来源：https://raw.githubusercontent.com/Illumina/manta/v1.6.0/docs/userGuide/README.md
（GitHub 页面版：https://github.com/Illumina/Manta/blob/develop/docs/userGuide/README.md）

### 2.1 配置（三种模式）

```bash
${MANTA_INSTALL_PATH}/bin/configManta.py \
--bam NA12878_S1.bam \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}
```

```bash
${MANTA_INSTALL_PATH}/bin/configManta.py \
--bam NA12878_S1.cram \
--bam NA12891_S1.cram \
--bam NA12892_S1.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}
```

```bash
${MANTA_INSTALL_PATH}/bin/configManta.py \
--normalBam HCC1187BL.cram \
--tumorBam HCC1187C.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}
```

```bash
${MANTA_INSTALL_PATH}/bin/configManta.py \
--tumorBam HCC1187C.cram \
--referenceFasta hg19.fa \
--runDir ${MANTA_ANALYSIS_PATH}
```

### 2.2 执行

```bash
${MANTA_ANALYSIS_PATH}/runWorkflow.py -j 8
${MANTA_ANALYSIS_PATH}/runWorkflow.py -h
```

### 2.3 输出文件

`${MANTA_ANALYSIS_PATH}/results/variants`：
- `diploidSV.vcf.gz`（diploid 模型打分；tumor/normal 时仅基于 normal）
- `somaticSV.vcf.gz`（somatic 模型打分，仅当配置时给了 tumor）
- `candidateSV.vcf.gz`（未打分候选；默认含 ≥8bp indel）
- `candidateSmallIndels.vcf.gz`（<50bp 简单 indel 子集）
- tumor-only 额外：`tumorSV.vcf.gz`（去冗余 + 去 <50bp 小 indel，未打分，但含每等位基因的 paired/split read 支持计数与部分 tumor-normal 过滤器）

统计输出：`${MANTA_ANALYSIS_PATH}/results/stats`（`alignmentStatsSummary.txt`、`svLocusGraphStats.tsv`、`svCandidateGenerationStats.tsv`、`svCandidateGenerationStats.xml`）。

### 2.4 `--exome` / `--callRegions`

- `--exome`：为 WES 与其他区域富集分析提供合适设置；当前会关闭所有高深度过滤器（这些过滤器针对 WGS 着丝粒附近参考压缩，靶向分析不能正确套用）。
- `--callRegions`：BED 需 bgzip 压缩 + tabix 索引，只允许一个；VCF 输出被限制在该区间，但 fragment size 分布等统计不受限；**即使指定 callRegions，WES/靶向数据仍必须加 `--exome`**。
- GRCh38 短 contig 拖慢运行时的官方 workaround：给 `--callRegions` 提供仅含主染色体的 BED（官方文档直接给出 chr1–chr22/X/Y/M 的 hg38 坐标表）。

### 2.5 tumor-only 过滤建议（原文）

> "the records could be filtered to only include those with `SAMPLE/PR[1] >= 15 || SAMPLE/SR[1] >= 15`"

并说明 `IMPRECISE` 标志是可靠性的强指示。官方同时说明 split read 计数在 imprecise 调用中不一定可得。

### 2.6 其它配置项（原文）

- `--rna`：RNA-Seq fusion 模式（实验性）；要求恰好一个样本作为 normal 输入（`--bam` 或 `--normalBam`）；输出 `rnaSV.vcf.gz`。
- `--generateEvidenceBam`：产出候选 SV 的证据 reads BAM，位于 `${MANTA_ANALYSIS_PATH}/results/evidence`，命名 `evidence_*.*.bam`，reads 带 `ZM:Z:${MANTA_SV_ID}|${EVIDENCE_TYPE}` 标签（PR/SR/SRM）；官方建议与 `--region` 合用。
- `--outputContig`：在 VCF 的 INFO `CONTIG` 输出组装 contig。
- `--config FILE`：覆盖 `${MANTA_INSTALL_PATH}/bin/configManta.py.ini` 中的高级参数（单次运行用）；`configManta.py --allHelp` 列出开发/调试级参数。
- 高灵敏度：把 `minEdgeObservations` 与 `minCandidateSpanningCount` 改为 2（默认 3）。
- de novo：多个 normal BAM 做联合 diploid 分析 → `$MANTA_INSTALL_FOLDER/libexec/denovo_scoring.py <vcf> <proband> <father> <mother>`。
- 反转记录可用 `$MANTA_INSTALL_FOLDER/libexec/convertInversion.py` 转成单倒位连接（INV3/INV5 语义见原文）。
- BEDPE 转换：官方推荐 https://github.com/ctsa/svtools 的 `vcfToBedpe`。

### 2.7 VCF 关键字段（原文表节选）

INFO：`IMPRECISE`、`SVTYPE`、`SVLEN`、`END`、`CIPOS`、`CIEND`、`CIGAR`、`MATEID`、`EVENT`、`HOMLEN`、`HOMSEQ`、`SVINSLEN`、`SVINSSEQ`、`LEFT_SVINSSEQ`、`RIGHT_SVINSSEQ`、`BND_DEPTH`、`MATE_BND_DEPTH`、`JUNCTION_QUAL`、`SOMATIC`、`SOMATICSCORE`、`JUNCTION_SOMATICSCORE`、`CONTIG`。
FORMAT：`GT`、`FT`、`GQ`、`PL`、`PR`、`SR`。
FILTER：`MinQUAL`(<20)、`MinGQ`(<15)、`MinSomaticScore`(<30)、`Ploidy`、`MaxDepth`(>3×)、`MaxMQ0Frac`(>0.4)、`NoPairSupport`、`SampleFT`、`HomRef`。

---

## 3. Delly

来源：https://raw.githubusercontent.com/dellytools/delly/main/README.md
（GitHub 页面版：https://github.com/dellytools/delly）

### 3.1 短读长 SV 发现

```bash
delly sr -g ref.fa input.bam > delly.vcf
delly sr -g hg38.fa -x human.hg38.excl.tsv -o delly.bcf input.bam
bcftools view delly.bcf > delly.vcf
```

### 3.2 长读长

```bash
delly lr -y ont -o delly.bcf -g hg38.fa input.bam
delly lr -y pb -o delly.bcf -g hg38.fa input.bam
```

### 3.3 somatic

```bash
delly [sr|lr] -o t1.bcf -g hg38.fa tumor1.bam control1.bam
delly filter -f somatic -o t1.somatic.bcf -s samples.tsv t1.bcf
sansa somatic -a pon.bcf t1.bcf
```

`samples.tsv`：tab 分隔，第一列样本 ID（与 VCF 中一致），第二列 `tumor` 或 `control`。tumor-only 与额外 germline 过滤可用 sansa 的 PoN 方案。

### 3.4 germline

```bash
delly [sr|lr] -g hg38.fa -o s1.bcf sample1.bam
delly merge -l -g hg38.fa -o sites.bcf s1.bcf s2.bcf ... sN.bcf
delly [sr|lr] -g hg38.fa -v sites.bcf -o s1.geno.bcf s1.bam
delly [sr|lr] -g hg38.fa -v sites.bcf -o sN.geno.bcf sN.bam
bcftools merge -m id -O b -o merged.bcf s1.geno.bcf s2.geno.bcf ... sN.geno.bcf
delly filter -l --hwe 0.000001 -f germline -o germline.bcf merged.bcf
delly sr -g hg38.fa -x human.hg38.excl.tsv -o delly.bcf sample.bam
```

（短读长去掉 `-l`；`-l` 用于长读长。）

### 3.5 CNV（read-depth）

```bash
delly cnv -g hg38.fa -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
delly cnv -m somatic -g hg38.fa -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
delly cnv -g hg38.fa -x human.GRCh38.map.excl.tsv.gz -c out.cov.gz -o out.bcf -u out.seg.bed input.bam
Rscript R/rd.R out.cov.gz out.seg.bed
bcftools query -i 'FILTER="PASS" && QUAL>200' -f "%CHROM\t%POS\t%INFO/END\t%ID[\t%RDCN]\n" out.bcf > seg.bed
Rscript R/rd.R out.cov.gz seg.bed
```

germline CNV：

```bash
delly cnv -o c1.bcf -g hg38.fa input.bam
delly merge -e -o sites.bcf c1.bcf c2.bcf ... cN.bcf
delly cnv -v sites.bcf -g hg38.fa -o geno1.bcf input.bam
bcftools merge -m id -O b -o merged.bcf geno1.bcf ... genoN.bcf
delly filter -f germline -o germline.bcf merged.bcf
bcftools query -f "%ID[\t%RDCN]\n" germline.bcf > plot.tsv
Rscript R/cnv.R plot.tsv
```

SCNA：

```bash
delly cnv -o tumor.bcf -c tumor.cov.gz -g hg38.fa tumor.bam
delly cnv -v tumor.bcf -o control.bcf -g hg38.fa control.bam
bcftools merge -m id -O b -o tumor_control.bcf tumor.bcf control.bcf
delly filter -p -f somatic -o somatic.bcf -s samples.tsv tumor_control.bcf
bcftools query -s tumor -f "%CHROM\t%POS\t%INFO/END\t%ID[\t%RDCN]\n" somatic.bcf > segmentation.bed
Rscript R/rd.R tumor.cov.gz segmentation.bed
```

官方说明：`delly cnv` 为全基因组 read-depth 方法，带 GC 偏倚与可比对性校正，**WES/靶向数据不支持**；SCNA 请用更灵敏的 somatic 模式；可用排除图谱（短读长推荐）；`-z` 调整最小 CNV 大小、`-p` 设置样本纯度以影响 SCNA 灵敏度。

### 3.6 其它官方命令

```bash
delly asm -y diploid -g hg38.fa s1.h1.bam s1.h2.bam s2.h1.bam s2.h2.bam ...
delly asm -y squashed -g hg38.fa s1.bam s2.bam ...
delly merge -l -v 0 -g hg38.fa -o panel.bcf s1.asm.bcf s2.asm.bcf ... sN.asm.bcf
python scripts/delly2bnd.py -v delly.bcf -r hg38.fa -o delly.bnd.bcf
bcftools view -i '(QUAL>=300) && ( ((SVTYPE=="INS") && (INFO/SVLEN>50)) || (SVTYPE=="BND") || ((INFO/END - POS)>50) )' delly.bcf
delly sr -g example/ref.fa -o sr.bcf example/sr.bam
delly lr -g example/ref.fa -o lr.bcf example/lr.bam
delly cnv -g example/ref.fa -c out.cov.gz -o cnv.bcf example/sr.bam
```

跨染色体易位用 `INFO/CHR2` 表示第二染色体；`scripts/delly2bnd.py` 可转成两记录 breakend 格式。

### 3.7 FAQ 中的官方约束

- 非二倍体：SV 位点发现对任意倍性有效，但**分型模型假设倍性为 2**；CNV 调用允许在命令行设置基线倍性。
- 提速：用 `-x` 排除端粒、着丝粒与未定位 contig；`-q 20`、`-s 15` 更严格过滤 reads；高覆盖数据 `-z 5`。
- 预处理：BAM/CRAM 需排序、建索引、最好标重复。

---

## 4. GATK-SV（仅官方 Terra 执行方式）

来源：https://broadinstitute.github.io/gatk-sv/docs/execution/single/

官方原文要点：
- Single Sample pipeline 的目的：把 cohort 模式的方法用于小数据集或临床场景，靠参考面板上预计算的 calls 与模型参数迁移。
- **执行方式是在 Terra 克隆 single-sample 工作区**，运行工作流 `gatk-sv-single-sample`。
- 输入：`sample_id`（String）、`bam_or_cram_file`（File，GCS 路径）、可选 `case_stripy_file`、`batch`（String）；另有工作区级输入：hg38 参考资源、参考面板数据、docker 镜像集合、`use_stripy`（默认 true）。
- 输出：`final_vcf`（含对照面板基因型 + gnomAD 位点等位基因频率 + 功能元件重叠注释）、`final_vcf_idx`、`final_bed`。

**官方文档未提供可直接执行的本地命令行**；`https://broadinstitute.github.io/gatk-sv/docs/execution/sv-shell/` 返回 HTTP 404（2026-10-29 抓取）。因此本技能不对 GATK-SV 给出任何命令。

---

## 5. AnnotSV

来源：
- https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/README.md
- https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/share/doc/AnnotSV/quickstart.md
- https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/share/doc/AnnotSV/ranking.md
- https://raw.githubusercontent.com/lgmgeo/AnnotSV/master/share/doc/AnnotSV/annotations.md

安装：

```bash
cd /path/to/install/
git clone https://github.com/lgmgeo/AnnotSV.git

cd /path/to/install/AnnotSV
make PREFIX=. install
make PREFIX=. install-human-annotation
make PREFIX=. install-mouse-annotation
```

环境变量：

```bash
# csh
setenv ANNOTSV /path/to/install/AnnotSV
# bash
export ANNOTSV=/path/to/install/AnnotSV
```

测试/运行：

```bash
cd /path/to/install/AnnotSV/share/doc/AnnotSV/Example/
$ANNOTSV/bin/AnnotSV -SVinputFile test.bed -outputFile ./test.annotated.tsv -svtBEDcol 4
```

分级（ranking.md 原表）：

| Score | Class type | Class |
| --- | --- | --- |
| 0.99 or more points | Pathogenic | Class 5 |
| 0.90 to 0.98 points | Likely pathogenic | Class 4 |
| 0.89 to −0.89 points | Variant of uncertain significance | Class 3 |
| −0.90 to −0.98 points | Likely benign | Class 2 |
| −0.99 or fewer points | Benign | Class 1 |

评分依据：`Scoring_Criteria_AnnotSV_v3.4.xlsx`（Table1 loss SV，Table2 gain SV），方法学为 ACMG/ClinGen 联合共识（Riggs et al., 2020）的改编。

注释库：GRCh37 或 GRCh38 由用户指定；部分注释绑定基因名，与 build 无关；可商用的注释源在安装时自动下载。完整参数在 `README.AnnotSV_3.5.7.pdf`（官方 PDF，本技能不复制）。

---

## 6. Ensembl VEP（SV 模式）

### 6.1 支持的 SV 输入与 SVTYPE

来源：https://www.ensembl.org/info/docs/tools/vep/vep_formats.html

支持的输入格式（原表，节选 SV 列）：
- 默认 VEP input：`1 160283 471362 DUP +`
- VCF：`1 7936271 . N N[12:58877476[ . . SVTYPE=BND`
- REST 风格 region：`21:25587759-25587769/DEL`
- HGVS 与 SPDI：不支持 SV

识别为 SV 的条件：默认格式的 allele 串或 VCF 的 `SVTYPE` 必须是下列之一——
`INS`、`INS:ME`、`INS:ME:ALU`、`INS:ME:HERV`、`INS:ME:LINE1`、`INS:ME:SVA`、`DEL`、`DEL:ME`、`DEL:ME:ALU`、`DEL:ME:HERV`、`DEL:ME:LINE1`、`DEL:ME:SVA`、`DUP`、`DUP:TANDEM`、`TDUP`、`INV`、`CNV`（拷贝数可写 `CN0`、`CN=4`、`CN3,CN4,CN6`、`CN=0,CN=2,CN=4`）、`CNV:TR`（需描述串联重复的 INFO 字段）。

Breakend：`ALT` 可为 `TG[12:58877476[` 之类；单 breakend 可写 `T.`、`.G`；多个逗号分隔如 `A[22:22893780[,A[X:10932343[`；**breakend 仅在 VCF 输入下支持**。

官方 VCF 示例：

```
#CHROM POS ID REF ALT QUAL FILTER INFO
1 160283 dup . <DUP> . . SVTYPE=DUP;END=471362
1 1385015 del . <DEL> . . SVTYPE=DEL;END=1387562
1 7936271 bnd N N[12:58877476[ . . SVTYPE=BND
```

默认格式的 SV 写法：

```
# structural variant: deletion
21:25587759-25587769/DEL
# structural variant: inversion
21:25587759-25587769/INV
```

### 6.2 运行与 SV 专有选项

来源：https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html
（镜像入口：https://asia.ensembl.org/info/docs/tools/vep/index.html ；效果优化说明：https://asia.ensembl.org/info/docs/tools/vep/script/vep_other.html）

官方默认运行：

```
./vep --cache -i input.txt -o output.txt
```

官方并行示例：

```
./vep -i my_input.vcf --fork 4 --offline
```

VCF 输出（`--vcf`）：结果写回 VCF，注释加在 INFO 的 `CSQ` 键，字段以 `|` 分隔，顺序写在 VCF header；可用 `--fields` 选择字段。若输入即 VCF，除新增 CSQ 外文件保持不变。

SV 相关选项：
- `--check_svs`：检查与输入重叠的已知结构变异；**当前需要数据库访问**，默认未启用，输出字段 `SV`，与 `--offline` 不兼容。
- `--overlaps`：以 VCF 形式报告转录本被 SV 覆盖的比例与长度。
- `--max_sv_size`：限制 VEP 处理的最大 SV 尺寸以降低内存占用，默认 `10000000`；设 `-1` 关闭，官方警告关闭可能造成大内存占用与慢运行。

本技能在 SKILL.md 中给出的 SV 注释命令，只由上述已文档化选项组合而成（`-i/--input_file`、`--format vcf`、`--vcf`、`--cache`、`--assembly`、`--fork`、`-o/--output_file`），未引入任何未文档化参数。

---

## 7. 已知 CNV/SV 数据库（对接用）

### 7.1 ClinVar（已抓取目录清单）

来源：https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/

目录清单（2026-10-29 抓取）：`archive_1.0/`、`archive_2.0/`、`weekly/`、`clinvar.vcf.gz`（191M）、`clinvar.vcf.gz.md5`、`clinvar.vcf.gz.tbi`（597K）、`clinvar_20261025.vcf.gz`、`clinvar_20261025_papu.vcf.gz` 等。

对接判据：下载 `clinvar.vcf.gz` + `.tbi`，按 `CHROM/POS/END` 与自建 CNV/SV 段做区间重叠，取 `CLNSIG` 等临床意义字段（字段名以该 VCF header 为准）。

### 7.2 gnomAD-SV（官方页面，未能逐字抓取）

官方入口：https://gnomad.broadinstitute.org/downloads 、SV 说明：https://gnomad.broadinstitute.org/help/sv-overview

**官方文档未提供可直接执行的命令**（页面为前端动态渲染，本次抓取仅得到站点标题）。对接判据：在官方 Downloads 的 Structural variants 区块取得 SV VCF，按 `SVTYPE`+`END` 与自建 SV 做重叠，用群体等位基因频率判断罕见/常见；频率阈值需按项目设定。

### 7.3 DGV（官方页面，抓取失败）

官方入口：http://dgv.tcag.ca/dgv/app/downloads

**官方文档未提供可直接执行的命令**（本次抓取失败）。对接判据：下载对应 build（GRCh38/hg38）的 DGV CNV 区间文件，与自建 CNV 段做区间重叠；落在 DGV 常见多态区间内的 CNV 降级为「可能良性」，仅作解读参考，不改变 calling 结果。

---

## 8. 官方随附脚本清单（本技能不复制代码，直接调用）

| 工具 | 脚本 | 用途 | 来源 |
| --- | --- | --- | --- |
| CNVkit | `guess_baits.py` | 由 BAM 覆盖度反推捕获区间（guided/unguided 两模式） | https://cnvkit.readthedocs.io/en/stable/scripts.html |
| CNVkit | `cnv_annotate.py` | 用 refFlat/BED/GFF 更新 .cnn/.cnr 的 gene 列 | 同上 |
| CNVkit | `cnv_updater.py` | 旧版 .cnn/.cnr/.cns 补 `depth` 列 | 同上 |
| CNVkit | `cnv_ztest.py` | 逐 bin 非中性检验，输出 `ztest` 列 | 同上 |
| CNVkit | `reference2targets.py` | 从参考 .cnn 反推 target/antitarget BED | 同上 |
| CNVkit | `skg_convert.py` | BED/RefFlat 等表格格式互转 | 同上 |
| CNVkit | `cnv_expression_correlate.py` | 拷贝数与 mRNA 表达相关性表 | 同上 |
| Manta | `libexec/convertInversion.py` | 把 breakend 式反转整理为单倒位连接（INV3/INV5） | Manta userGuide |
| Manta | `libexec/denovo_scoring.py` | 三人组 de novo SV 打分（`denovo_scoring.py <vcf> <proband> <father> <mother>`） | Manta userGuide |
| Delly | `scripts/delly2bnd.py` | 跨染色体易位转两记录 breakend | Delly README |
| Delly | `R/rd.R`、`R/cnv.R` | read-depth / CNV 分布绘图 | Delly README |

官方 CNVkit 脚本用法示例（原文）：

```bash
guess_baits.py Sample1.bam Sample2.bam -t ucsc-exons.bed -o baits.bed
guess_baits.py -g access.hg19.bed Sample1.bam Sample2.bam -o baits.bed
```
