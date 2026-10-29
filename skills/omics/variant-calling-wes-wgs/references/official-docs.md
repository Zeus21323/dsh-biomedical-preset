# 官方文档索引（工具 → URL → 官方安装命令 → 该文档覆盖什么）

抓取方式与时间：2026-10-29。GATK 支持站点正文经其 Zendesk 帮助中心 API（`https://gatk.broadinstitute.org/api/v2/help_center/en-us/articles/<id>.json`）读取，URL 就是下列人类可读页面；其余站点直接抓取页面/仓库原文。

## 1. GATK / Picard

| 工具 | 官方 URL | 官方安装命令（逐字） | 该文档覆盖什么 |
| --- | --- | --- | --- |
| Germline short variant discovery（主线方法） | https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels- | 无（方法文章） | 队列/单样本两条主线的步骤顺序、每步用哪个工具、为什么需要 joint calling、VQSR 的适用边界；表格还列出官方 WDL 参考实现（Prod germline per-sample / joint genotyping、Generic、Intel） |
| HaplotypeCaller | https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller | 无（随 GATK 发布包） | 三份官方用法示例（GVCF、GVCF+AS 注释、bamout）、`-ERC GVCF` 时置信阈值强制为 0、PCR-free 用 `-pcr_indel_model NONE`、建议给 intervals、全部参数与默认值 |
| AddOrReplaceReadGroups (Picard) | https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-AddOrReplaceReadGroups-Picard | 随 Picard jar | `java -jar picard.jar` 形式的用法示例、RG 标签字符集限制、只能整体指派单一 read group 的 caveat、RGID/RGLB/RGPL/RGPU/RGSM 默认 null |
| MarkDuplicates (Picard) | https://gatk.broadinstitute.org/hc/en-us/articles/360036756891-MarkDuplicates-Picard | 随 Picard jar | 用法示例、输入必须 coordinate sorted、`REMOVE_DUPLICATES`/`OPTICAL_DUPLICATE_PIXEL_DISTANCE`/`TAGGING_POLICY`/`VALIDATION_STRINGENCY` 的默认值与语义 |
| BaseRecalibrator | https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator | 随 GATK | 用法示例（多 `--known-sites`）、输出 GATKReport 五张表、全部参数与默认值 |
| Base Quality Score Recalibration (BQSR)（方法文章） | https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR | 无 | BQSR 原理、read-group aware、每 RG 期望 >100M bases、何时该跳过、无已知位点集时的自举流程（三步，无命令）、`-qq` 量化、报告五张表的样例 |
| ApplyBQSR | https://gatk.broadinstitute.org/hc/en-us/articles/360037268511-ApplyBQSR | 随 GATK | 用法示例、必须用同一 BAM 的 table、`--emit-original-quals` |
| GenomicsDBImport | https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport | 随 GATK | 两份用法示例（逐个 `-V`、`--sample-name-map` + `--batch-size` + `--reader-threads`）、sample map 两列格式、五条 caveat（内存、interval、同位点多记录、workspace 必须空、`--tmp-dir`）、`--batch-size 0` / `--reader-threads 1` 默认值 |
| GenotypeGVCFs | https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs | 随 GATK | 两份用法示例（单 GVCF、`gendb://` workspace）、只接受 HaplotypeCaller/CombineGVCFs 的 GVCF、一次只能一个 GVCF、`-stand-call-conf 10.0`、`-G [StandardAnnotation]` |
| VariantRecalibrator | https://gatk.broadinstitute.org/hc/en-us/articles/360036348332-VariantRecalibrator | 随 GATK | 用法示例、`--mode SNP`/`--max-gaussians 8`/`--trust-all-polymorphic false` 默认值、resource 参数语法 `-resource:name,known=,training=,truth=,prior=` |
| ApplyVQSR | https://gatk.broadinstitute.org/hc/en-us/articles/360036431392-ApplyVQSR | 随 GATK | 用法示例、`--mode`/`--truth-sensitivity-filter-level`/`--create-output-variant-index true` 默认值 |
| VariantFiltration | https://gatk.broadinstitute.org/hc/en-us/articles/360041850471-VariantFiltration | 随 GATK | 用法示例、复合表达式（`&&`/`||`）会把缺注释的记录判 PASS 的官方警告、推荐逐条表达式 |
| SelectVariants | https://gatk.broadinstitute.org/hc/en-us/articles/360036883411 （仅经搜索 API 确认 id 与标题，未抓取正文） | 随 GATK | `-select-type SNP|INDEL` 的拆分用法；本技能实际引用的两条拆分命令出自上文 How-to 页 |
| LeftAlignAndTrimVariants | https://gatk.broadinstitute.org/hc/en-us/articles/4405443605531-LeftAlignAndTrimVariants | 随 GATK | 六份用法示例（trim / 不 trim / `--max-indel-length` / `--split-multi-allelics` / `--keep-original-ac` / `--max-leading-bases`）、默认值 200 / 1000 / false |
| CollectHsMetrics (Picard) | https://gatk.broadinstitute.org/hc/en-us/articles/360036714891-CollectHsMetrics-Picard | 随 Picard jar | 用法示例（`BAIT_INTERVALS`/`TARGET_INTERVALS`）、BED→interval_list 需用 BedToIntervalList、`PER_TARGET_COVERAGE`、默认值（NEAR_DISTANCE 250、MQ 20、BQ 20、COVERAGE_CAP 200、CLIP_OVERLAPPING_READS true）、百分比是分数不是百分数 |
| Picard metric definitions | https://broadinstitute.github.io/picard/picard-metric-definitions.html | — | `MEAN_TARGET_COVERAGE`、`MEDIAN_TARGET_COVERAGE`、`PCT_TARGET_BASES_20X/30X`、`FOLD_80_BASE_PENALTY`、`PCT_SELECTED_BASES`、`PCT_USABLE_BASES_ON_TARGET`、`FOLD_ENRICHMENT`、`AT/GC_DROPOUT`、`PERCENT_DUPLICATION`、`ESTIMATED_LIBRARY_SIZE`、`PCT_CHIMERAS` 等指标的文字定义 |
| (How to) Filter variants either with VQSR or by hard-filtering | https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering | 无（How-to） | **本技能过滤阶段的主依据**：ExcessHet 54.69、MakeSitesOnlyVcf、INDEL/SNP 两套 VariantRecalibrator 完整命令、tranche 列表、ApplyVQSR 两步、硬过滤 SNP/INDEL 两套完整命令、`CollectVariantCallingMetrics`、VariantEval、hap.py 建议 |
| Which training sets for VQSR? | https://gatk.broadinstitute.org/hc/en-us/articles/4402736812443-Which-training-sets-arguments-should-I-use-for-running-VQSR | 无 | 每类资源（HapMap/Omni/1000G/dbSNP/Mills/Axiom）的 known/training/truth/prior 语义；**外显子不要用 DP**；外显子 ≥30 样本；`--ts_filter_level 99.5`(SNP)/`99.0`(INDEL)；<30 样本的补样本做法 |
| I am unable to use VQSR | https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants | 无 | 硬过滤的「保底」阈值清单（SNP 6 条、INDEL 5 条含 `SOR > 10.0`、`InbreedingCoeff < -0.8`）；InbreedingCoeff 需 ≥10 样本；外显子不要用 DP；<10x 手工过滤不可靠 |
| Can't use VQSR on non-model organism or small dataset | https://gatk.broadinstitute.org/hc/en-us/articles/360035532412-Can-t-use-VQSR-on-non-model-organism-or-small-dataset | 无 | 同一份保底阈值的另一版本、`<30 exomes` 判定、JEXL 语义（满足表达式即被标 filtered） |
| Intervals and interval lists | https://gatk.broadinstitute.org/hc/en-us/articles/360035531852-Intervals-and-interval-lists | 无 | `-L/-XL/-ip/-ixp` 语义、区间合并/并集规则、四种区间格式与坐标系（interval_list/list 1-based、BED 0-based）、**靶向测序生产流程两侧各加 100 bp padding**、外显子区间应取自试剂盒厂商、WGS 用 blacklist 区间 |
| Resource bundle | https://gatk.broadinstitute.org/hc/en-us/articles/360035890811-Resource-bundle | `gs://gcp-public-data--broad-references`（桶）/ `https://console.cloud.google.com/storage/browser/gcp-public-data--broad-references/hg38/v0` | 资源桶位置、hg38 资源集「provided as-is」且**缺 Broad hg38 外显子区间**、b37 才有 exome bundle、各候选桶用途 |
| Known variants / Training resources / Truth sets | https://gatk.broadinstitute.org/hc/en-us/articles/360035890831-Known-variants-Training-resources-Truth-sets | 无 | known / training / truth 三类资源的定义与可自举性（truth 不可自举）、各工具如何使用它们 |
| The logic of joint calling | https://gatk.broadinstitute.org/hc/en-us/articles/360035890431-The-logic-of-joint-calling-for-germline-short-variants | 无 | 为什么要 joint calling、N+1 问题、平方化基因型矩阵的含义 |
| (How to) Run GATK in a Docker container | https://gatk.broadinstitute.org/hc/en-us/articles/360035889991--How-to-Run-GATK-in-a-Docker-container | `docker pull broadinstitute/gatk:4.1.3.0` / `docker run -it broadinstitute/gatk:4.1.3.0` / `docker run -v ~/my_project:/gatk/my_data -it broadinstitute/gatk:4.1.3.0` | GATK 容器化运行与挂载数据目录 |
| Getting started with GATK4 | https://gatk.broadinstitute.org/hc/en-us/articles/360036194592-Getting-started-with-GATK4 | 下载发布包（jar + 启动脚本），「no installation necessary in the traditional sense」 | GATK4 运行前提、发布包内容、启动脚本用法 |
| (How to) Install all software packages required to follow GATK Best Practices | https://gatk.broadinstitute.org/hc/en-us/articles/360041320571--How-to-Install-all-software-packages-required-to-follow-the-GATK-Best-Practices | 页面内按工具列出安装方式 | Best Practices 全套依赖（含 samtools、bwa、VEP 等）的官方安装入口 |
| Variant Quality Score Recalibration（VQSR 方法文章） | https://gatk.broadinstitute.org/hc/en-us/articles/360035531612-Variant-Quality-Score-Recalibration-VQSR | 无 | VQSR 两段式（建模 + 应用）、VQSLOD/tranche 的概念、与硬过滤的取舍、对样本量的要求 |
| (How to) Consolidate GVCFs for joint calling with GenotypeGVCFs | https://gatk.broadinstitute.org/hc/en-us/articles/360035889971--How-to-Consolidate-GVCFs-for-joint-calling-with-GenotypeGVCFs | 无 | `GenomicsDBImport -L` → `GenotypeGVCFs -V gendb://` 的官方串联示例，以及 `SelectVariants` 的用法示例 |
| (How to) Install and use Conda for GATK4 | https://gatk.broadinstitute.org/hc/en-us/articles/360035889851--How-to-Install-and-use-Conda-for-GATK4 | 页面内给出 conda 安装步骤 | 用 conda 管理 GATK4 环境（本技能未复制其命令，见页面） |
| Hybrid selection（外显子捕获原理） | https://gatk.broadinstitute.org/hc/en-us/articles/360035890911-Hybrid-selection-exome-preparation | 无 | 捕获建库的原理与术语（bait/target/interval_list 的由来），解释为什么 WES 的覆盖均一性与 dup 行为不同于 WGS |
| CalculateContamination（体细胞侧，仅备查） | https://gatk.broadinstitute.org/hc/en-us/articles/360036732531-CalculateContamination | 随 GATK | 基于 pileup 的污染估计；本技能种系主线不采用，污染估计统一用 VerifyBamID2 |

## 2. 比对 / 处理 / 统计（htslib 生态）

| 工具 | 官方 URL | 官方安装命令（逐字） | 该文档覆盖什么 |
| --- | --- | --- | --- |
| bwa-mem2 | https://github.com/bwa-mem2/bwa-mem2 | `curl -L https://github.com/bwa-mem2/bwa-mem2/releases/download/v2.2.1/bwa-mem2-2.2.1_x64-linux.tar.bz2 \| tar jxf -` | `index` / `mem` 用法、索引体积（人类 ~10 GB 磁盘 / ~10 GB 内存）、索引结构变更需重建、与 bwa mem 用法完全一致、源码编译方式、LISA/ERT 分支 |
| samtools sort | https://www.htslib.org/doc/samtools-sort.html | 见 https://www.htslib.org/download/ | 排序用法与选项；官方流程里的 `samtools sort -O bam -o out.bam -T /tmp/x in.bam` |
| samtools index | https://www.htslib.org/doc/samtools-index.html | 同上 | `samtools index aln.sam|aln.bam|aln.cram` |
| samtools faidx | https://www.htslib.org/doc/samtools-faidx.html | 同上 | `samtools faidx ref.fasta`（建 .fai）与取子序列 |
| samtools dict | https://www.htslib.org/doc/samtools-dict.html | 同上 | `samtools dict ref.fasta`（建 .dict） |
| Duplicate Marking（算法/流程说明） | https://www.htslib.org/algorithms/duplicate.html | — | PCR/optical duplicate 概念、markdup 的判重键、`fixmate -m` 提供 MC/ms、四步流程与一行管道、**与 Picard 相似结果的光学设置 `-d 2500 --mode s --include-fails`**、HiSeq 100 / NovaSeq 2500 |
| WGS/WES Mapping to Variant Calls（流程） | https://www.htslib.org/workflow/wgs-call.html | — | `bwa mem -R '@RG\tID:foo\tSM:bar\tLB:library1'`、`samtools fixmate`、`samtools sort`、`samtools index`、`bcftools mpileup | bcftools call`、`bcftools stats`、`bcftools filter`（**注意：页内 GATK3 IndelRealigner 段属旧流程**） |
| bcftools（man page） | https://samtools.github.io/bcftools/bcftools.html | 见 https://www.htslib.org/download/ | `norm`（`-f` 触发左对齐+规范化、`-m -`/`-m +`、`-c e|w|x|s`、`-d`）、`stats`（频率/深度/质量分布、per-sample counts、singleton stats）、`filter`、`view`、`index`、通用 `-O b|u|z|v` |

## 3. 覆盖度 QC

| 工具 | 官方 URL | 官方安装命令（逐字） | 该文档覆盖什么 |
| --- | --- | --- | --- |
| mosdepth | https://github.com/brentp/mosdepth | `docker pull quay.io/biocontainers/mosdepth:0.3.3--h37c5b7d_2`（官方首选 releases 静态二进制） | 完整 usage（`--by`、`-n`、`-x`、`-T`、`-q`、`-F 1796`、`-Q`、`-m`、`-R`）、外显子示例、WGS 500bp 窗口示例、quantize/callable 示例、输出文件清单、dist 文件三列含义、官方绘图脚本 `scripts/plot-dist.py`、libhts 报错处理 |

## 4. 注释

| 工具 | 官方 URL | 官方安装命令（逐字） | 该文档覆盖什么 |
| --- | --- | --- | --- |
| VEP 运行与全部选项 | https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html | — | `./vep [options]`；默认示例 `./vep --cache -i input.txt -o output.txt`；`--cache/--offline/--database` 三种模式与互斥关系；`--dir/--dir_cache/--dir_plugins`（默认 `$HOME/.vep/`）；`--fasta` 在 offline 下取 HGVS/校验参考是必需；`--vcf/--tab/--json`；`--everything` 的具体展开；`--plugin`（仅给 `[plugin name]`，细节指向插件页）；`--fork`、`--buffer_size 5000`、`--force_overwrite`、`--no_check_variants_order`、`--pick/--most_severe/--per_gene`、`--check_existing`、`--af_gnomad*`、`--shift_3prime` |
| VEP 下载与安装 | https://asia.ensembl.org/info/docs/tools/vep/script/vep_download.html | `git clone https://github.com/Ensembl/ensembl-vep.git` → `perl INSTALL.pl`；免交互 `perl INSTALL.pl --AUTO ac`；插件 `perl INSTALL.pl -a p --PLUGINS dbNSFP,CADD,G2P` | `--AUTO` 部件代号（a/l/c/f/p）、`--CACHE_VERSION`、`--CACHEDIR`、`--DESTDIR`、`--PLUGINSDIR`、`--NO_HTSLIB`、`--PREFER_BIN`、以及「改缓存目录则运行时必须加 `--dir_cache`」 |
| VEP 插件页（未抓取全文，供查具体插件参数） | https://asia.ensembl.org/info/docs/tools/vep/script/vep_plugins.html | `perl INSTALL.pl -a p --PLUGINS <name>` | 各插件（LoF、dbNSFP、CADD、G2P 等）的专用参数与数据准备；本技能只引用不复制 |

## 5. 污染估计

| 工具 | 官方 URL | 官方安装命令（逐字） | 该文档覆盖什么 |
| --- | --- | --- | --- |
| VerifyBamID2 | https://github.com/Griffan/VerifyBamID | `conda install -c bioconda verifybamid2`；`docker pull griffan/verifybamid2` | GRCh37（`--UDPath/--BedPath/--MeanPath`，无 chr 前缀）与 GRCh38（`--SVDPrefix`，带 chr 前缀，参考 `GRCh38_full_analysis_set_plus_decoy_hla.fa`）两套官方命令；`.selfSM` 的 **FREEMIX** = 污染比例；`Ancestry` 文件；`--RefVCF` 构造 SVD 资源；`--max-depth 8000`、`--adjust-MQ 40` 等参数 |

## 6. 官方现成脚本（本技能不复制，直接引用）

| 脚本 | 官方位置 | 用途 |
| --- | --- | --- |
| `scripts/plot-dist.py` | https://github.com/brentp/mosdepth | 用 `*global.dist.txt` 画累积深度分布，输出 `dist.html` |
| `plot-vcfstats` | 随 bcftools 发布（用法见 https://www.htslib.org/workflow/wgs-call.html ） | 把 `bcftools stats` 输出画成图 |
| `filter_vep` | 随 Ensembl VEP 发布（见 VEP options 页「filtering results」链接） | 注释后过滤 |
| `INSTALL.pl` | https://github.com/Ensembl/ensembl-vep | VEP 组件/缓存/插件安装 |
