# 参数 / 官方默认值 / 何时需要改 / 来源

只收录本主线实际会动的参数。默认值均摘自官方工具页参数表（「Default value」列），来源 URL 见每节末。

## 1. AddOrReplaceReadGroups (Picard)

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `RGID` (`-ID`) | null（必填） | 每个测序 lane/文库一个唯一 ID；多 lane 合并前必须唯一 | https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-AddOrReplaceReadGroups-Picard |
| `RGLB` (`-LB`) | null（必填） | 填文库名；BQSR 与去重按文库/read group 分区，填错会串样 | 同上 |
| `RGPL` (`-PL`) | null（必填） | 一般 `ILLUMINA`；平台名会进入 BQSR 的 `default_platform` | 同上 |
| `RGPU` (`-PU`) | null（必填） | 一般填 flowcell.lane.barcode | 同上 |
| `RGSM` (`-SM`) | null（必填） | **必须是样本名**；联合分型里 sample 列即取此值 | 同上 |
| `RGID` 等字符集 | 必须匹配 `'^[ -~]+$'` | 有中文/全角/制表符的样本名必须先规范化 | 同上 |
| `SORT_ORDER` (`-SO`) | 官方未给默认值 | 需要输出即有序时显式指定；否则后续仍需 `samtools sort` | 同上 |

## 2. BWA-MEM2

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `index -p prefix` | 默认前缀 = 输入 fasta 名 | 参考放在共享目录、多人复用时给固定前缀 | https://github.com/bwa-mem2/bwa-mem2 |
| `mem -t <num_threads>` | 官方未给默认值（bwa 默认 1） | 按核数设置；官方性能示例用 `-t 56` | 同上 |
| 索引 | 人类约 10 GB 磁盘 / 约 10 GB 内存 | 升级 bwa-mem2 后索引结构变更，必须 `bwa-mem2 index` 重建 | 同上 |

## 3. MarkDuplicates (Picard)

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `REMOVE_DUPLICATES` | `false` | 保持 `false`：GATK 后续步骤按 flag 忽略重复，删掉会丢信息；只有确定不做重新分析时才 `true` | https://gatk.broadinstitute.org/hc/en-us/articles/360036756891-MarkDuplicates-Picard |
| `OPTICAL_DUPLICATE_PIXEL_DISTANCE` | `100` | **patterned flowcell（NovaSeq/NextSeq 等）改 2500**（官方原文）；其他平台需实测 | 同上 |
| `TAGGING_POLICY` | `DontTag` | 需要区分 PCR/optical 类型时改 `OpticalOnly` 等 | 同上 |
| `VALIDATION_STRINGENCY` | `STRICT` | 旧数据 header 不全可临时 `LENIENT`/`SILENT`（官方说明 SILENT 可提速） | 同上 |
| `CREATE_INDEX` | `false` | 直接产出带索引 BAM 时设 `true` | 同上 |
| `MAX_RECORDS_IN_RAM` | `500000` | 大 BAM 排序溢出时调高（更吃内存、更少文件句柄） | 同上 |
| 输入要求 | 「Must be coordinate sorted」 | 未排序先用 `samtools sort` | 同上 |

samtools 替代路线关键参数（来源 https://www.htslib.org/algorithms/duplicate.html ）：
`-d <distance>`（HiSeq 100 / NovaSeq 2500）、`--mode s`（与 Picard 更接近）、`--include-fails`（含 QCFAIL 读段）、`-S`（二级/补充比对也标重复，二次扫描）、`-l`（默认 300，读长更长要调大）、`-c`（清除旧的重复标记）、`-f stats_file.txt`（统计输出）、`-@ N`（线程）。

## 4. BaseRecalibrator / ApplyBQSR

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--known-sites` | 无（可重复给多次） | 人类 GRCh38 至少 dbSNP + Mills + 1000G gold-standard indels；缺失会让真变异被当错误计入 | https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator |
| `-qq`（引擎级量化） | 默认不量化 | `-qq 0` 不量化；`-qq N` 用 N 个 bin 重算（影响下游 PL 精度与体积） | https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR |
| 每个 read group 的数据量 | 期望 > 100M bases | 远低于此值（小 panel）应跳过 BQSR | 同上 |
| `--bqsr-recal-file` | 无（必填） | 只能配对同一样本同一 BAM 的 table | https://gatk.broadinstitute.org/hc/en-us/articles/360037268511-ApplyBQSR |
| `--emit-original-quals` | 不开启 | 需要追溯原始质量时开启（写入 OQ tag） | 同上 |

## 5. HaplotypeCaller

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `-ERC`（`--emit-ref-confidence`） | 普通 VCF 模式 | 队列联合分型必须 `GVCF`；`BP_RESOLUTION` 更细但体积大 | https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller |
| `--standard-min-confidence-threshold-for-calling` (`-stand-call-conf`) | `30.0` | **`-ERC GVCF` 时被强制为 0 且不可覆盖**，阈值改在 GenotypeGVCFs 设 | 同上 |
| `--interval-padding` (`-ip`) | `0` | **WES 必须显式给**，官方生产流程靶向测序两侧各 100 bp | 同上（默认值）+ https://gatk.broadinstitute.org/hc/en-us/articles/360035531852-Intervals-and-interval-lists |
| `--interval-exclusion-padding` (`-ixp`) | `0` | 用 `-XL` 排除高噪声区间时给 padding | HaplotypeCaller 页（参数表） |
| `--assembly-region-padding` | `100` | 极短读长/极密变异可微调 | 同上 |
| `--native-pair-hmm-threads` | `4` | 按核数调高可显著提速 | 同上 |
| `--base-quality-score-threshold` | `18` | 低于该值的碱基质量被压到 6；极端低质量数据可考虑调整 | 同上 |
| `--dont-use-soft-clipped-bases` | `false` | 捕获数据在 indel 附近软剪切多时可试 `true` | 同上 |
| `-pcr_indel_model` | 默认模型（非 NONE） | **PCR-free 建库必须 `NONE`** | 同上 |
| `-G` | 常规注释集 | 需要等位基因特异注释时加 `-G Standard -G AS_Standard` | 同上 |

## 6. GenomicsDBImport

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--genomicsdb-workspace-path` | null（必填） | 目标目录必须**不存在或为空** | https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport |
| `--batch-size` | `0`（不分批） | 样本多、内存不足时设 50 等；官方提示批次数超过 100 应配合 consolidate | 同上 |
| `--reader-threads` | `1` | 输入在远端/高延迟存储时调高 | 同上 |
| `--tmp-dir` | 系统临时目录 | **必改**到足够大的盘，官方明确临时盘需求可能超预期 | 同上 |
| `--sample-name-map` | null | 样本数多时用 map 文件（两列 tab），可顺带重命名样本 | 同上 |
| `-L` | 无（必填至少一个） | 按染色体/区间分片以并行 | 同上 |
| `-Xmx` | 工具默认 | 官方：必须比物理内存少至少几 GB（TileDB 原生内存） | 同上 |

## 7. GenotypeGVCFs

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `-V` | 无（必填） | 可以是单个 GVCF 或 `gendb://workspace`；**不能一次给多个 GVCF** | https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs |
| `--standard-min-confidence-threshold-for-calling` (`-stand-call-conf`) | `10.0` | 想提高灵敏度/特异度在此调（GVCF 阶段被强制为 0，这里是唯一可设处） | 同上 |
| `--annotation-group` (`-G`) | `[StandardAnnotation]` | 需要 AS 注释时加 `AS_StandardAnnotation` | 同上 |
| `--dbsnp` (`-D`) | null | 需要 rsID 时给 dbSNP VCF | 同上 |

## 8. VariantRecalibrator / ApplyVQSR

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--mode` | `SNP` | 必须跑两遍：`INDEL` 一遍、`SNP` 一遍 | https://gatk.broadinstitute.org/hc/en-us/articles/360036348332-VariantRecalibrator |
| `--max-gaussians` | `8` | 官方生产流程用 4（INDEL）/6（SNP）；小数据报 `No data found` 时**继续递减** | 同上 + How-to 页 |
| `--trust-all-polymorphic` | `false` | 生产流程开启以提速（前提：训练集记录确实都是多态位点） | 同上 |
| `-tranche` | 无（可多次） | 官方给了 14 档（INDEL）与 12 档（SNP）的具体列表，见 How-to 页 | https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering |
| `-an`（注释集） | 无 | SNP 用 QD/MQRankSum/ReadPosRankSum/FS/MQ/SOR/DP；INDEL 去掉 MQ 类（官方解释：indel 长度与 MAPQ 混杂）；**WES 一律去掉 DP**；样本 <10 去掉 InbreedingCoeff | 同上 + https://gatk.broadinstitute.org/hc/en-us/articles/4402736812443 |
| `-resource:` 的 prior | 按资源给定（HapMap 15、Omni 12、1000G 10、Mills 12、Axiom 10、dbSNP 7 或 2） | 换成自有 truth/training 集时按置信度给（官方建议起步 Q10） | 同上 |
| `ApplyVQSR --truth-sensitivity-filter-level` | null | 官方生产流程 `99.7`；外显子推荐 `99.5`(SNP) / `99.0`(INDEL) | https://gatk.broadinstitute.org/hc/en-us/articles/360036431392-ApplyVQSR + 4402736812443 |
| `ApplyVQSR --create-output-variant-index` | `true` | 不需要索引时可关 | 同上 |
| `ApplyVQSR --mode` | `SNP` | 与 recal 表一致，先 INDEL 后 SNP 依次套用 | 同上 |

## 9. VariantFiltration（硬过滤）

| 参数 | 阈值（官方给的两套） | 何时用 | 来源 |
| --- | --- | --- | --- |
| SNP | How-to 套：`QD < 2.0`、`QUAL < 30.0`、`SOR > 3.0`、`FS > 60.0`、`MQ < 40.0`、`MQRankSum < -12.5`、`ReadPosRankSum < -8.0` | 外显子 <30 例、panel | https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering |
| INDEL | How-to 套：`QD < 2.0`、`QUAL < 30.0`、`FS > 200.0`、`ReadPosRankSum < -20.0` | 同上 | 同上 |
| SNP | FAQ 套：`QD < 2.0`、`MQ < 40.0`、`FS > 60.0`、`SOR > 3.0`、`MQRankSum < -12.5`、`ReadPosRankSum < -8.0`（UG 老 callset 加 `HaplotypeScore > 13.0`） | 无训练资源、非模式生物 | https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants |
| INDEL | FAQ 套：`QD < 2.0`、`ReadPosRankSum < -20.0`、`InbreedingCoeff < -0.8`、`FS > 200.0`、`SOR > 10.0` | 同上；`InbreedingCoeff` 需 ≥10 样本 | 同上 |
| `-filter-name` | 无 | 每个 `-filter` 配一个有意义的名字（会写进 FILTER 列，用 `;` 连接） | How-to 页 |
| 表达式写法 | 官方禁止 `||`/`&&` 复合式 | 一律一条属性一个 `-filter` | How-to 页 + https://gatk.broadinstitute.org/hc/en-us/articles/360041850471-VariantFiltration |
| 字面量类型 | Integer 写 `2`，Float 写 `2.0` | 与 INFO 定义不匹配会抛 `java.lang.NumberFormatException` | How-to 页 |
| DP 上限过滤 | **外显子不用** | 官方说明 capture 数据里深度与错配关联不明确 | FAQ 页 |

## 10. LeftAlignAndTrimVariants / bcftools norm

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--max-indel-length` | `200` | 有长 indel（如 300–500 bp）需要左对齐时调大 | https://gatk.broadinstitute.org/hc/en-us/articles/4405443605531-LeftAlignAndTrimVariants |
| `--max-leading-bases` | `1000` | 重复区 indel 需更长回看窗口时调大（示例 `2000`） | 同上 |
| `--split-multi-allelics` | `false` | 下游工具（VEP `--pick`、某些关联分析）要求双等位时开启 | 同上 |
| `--dont-trim-alleles` | `false` | 需保留原始 allele 表示时开启 | 同上 |
| `--keep-original-ac` | `false` | 拆分多等位后仍要保留原 AC/AF/AN 时开启 | 同上 |
| `bcftools norm -f` | 无 | 提供参考即触发左对齐 + 规范化 | https://samtools.github.io/bcftools/bcftools.html |
| `bcftools norm -m -any` | 无 | 拆分多等位（`-` 拆 / `+` 合） | 同上 |
| `bcftools norm -c e|w|x|s` | 无 | REF 与参考不符时的处置（退出/警告/剔除/改写） | 同上 |
| `bcftools norm -d` | 无 | 去重复记录（`snps|indels|both|all|exact`） | 同上 |

## 11. CollectHsMetrics（WES QC）

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `BAIT_INTERVALS` / `TARGET_INTERVALS` | 无（必填） | 用**捕获试剂盒对应版本**的 interval_list；BED 要先转 interval_list（官方指向 BedToIntervalList） | https://gatk.broadinstitute.org/hc/en-us/articles/360036714891-CollectHsMetrics-Picard |
| `NEAR_DISTANCE` | `250` | 判定 "near bait" 的距离；窄捕获设计可调 | 同上 |
| `MINIMUM_MAPPING_QUALITY` | `20` | 与后续 caller 的 MAPQ 语义对齐 | 同上 |
| `MINIMUM_BASE_QUALITY` | `20` | 同上（影响覆盖度口径） | 同上 |
| `COVERAGE_CAP` | `200` | 理论灵敏度计算的上限；超高深度 panel 调高 | 同上 |
| `CLIP_OVERLAPPING_READS` | `true` | 保持 `true`，否则 overlap 区深度虚高 | 同上 |
| `PER_TARGET_COVERAGE` | null（不输出） | 需要逐靶标深度/GC（如做 CNV 或 drop-out 分析）时给文件名 | 同上 |
| `METRIC_ACCUMULATION_LEVEL` | `[ALL_READS]` | 需要按样本/文库拆分指标时追加 `SAMPLE`/`LIBRARY` | 同上 |

## 12. mosdepth

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--by/-b` | 未给（不给则只出全局/逐染色体） | WES 给 capture BED；WGS 给窗口 bp（如 500） | https://github.com/brentp/mosdepth |
| `--no-per-base/-n` | 关闭（会输出 per-base） | 只要汇总/区域深度时开启（明显更快） | 同上 |
| `--fast-mode/-x` | 关闭 | 官方推荐多数场景开启（忽略 CIGAR 内部操作与 mate overlap 修正） | 同上 |
| `--flag/-F` | `1796` | 默认已排除 unmapped/secondary/QC-fail/duplicate；改口径时调整 | 同上 |
| `--mapq/-Q` | `0` | 只想统计高 MAPQ 时设置 | 同上 |
| `--thresholds/-T` | 未给 | 需要「≥N 覆盖的碱基数」时给 `1,10,20,30` 这类列表 | 同上 |
| `--quantize/-q` | 未给 | 需要 callable 区间（如 `0:1:5:150:` + `MOSDEPTH_Q*` 环境变量）时使用 | 同上 |
| `--threads/-t` | `0` | BAM 解压线程，大 BAM 建议 3–4 | 同上 |
| `--fasta/-f` | 空 | 输入 CRAM 时必填 | 同上 |

## 13. Ensembl VEP

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--cache` / `--offline` / `--database` | 都不启用（必须选一个模式） | 生产一律 `--cache` 或 `--offline`；`--database` 适合小文件 | https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html |
| `--assembly` (`-a`) | 用已安装的 assembly（只装一个时自动选） | 同机装 GRCh37+GRCh38 时必须显式指定 | 同上 |
| `--dir_cache` | `$HOME/.vep/` | 缓存放共享盘时必改（且 `INSTALL.pl --CACHEDIR` 要一致） | 同上 |
| `--dir_plugins` | `$HOME/.vep/` | 插件与缓存分目录时 | 同上 |
| `--fasta` (`-fa`) | 不启用 | `--offline` 下要 `--hgvs`/`--check_ref` 时**必需**；`--cache` 下可选（略提速） | 同上 |
| `--buffer_size` | `5000` | 内存紧张调低、追求速度调高 | 同上 |
| `--fork` | 不启用 | 大 VCF 必开（按核数） | 同上 |
| `--vcf` | 不启用（默认 tab 文本） | 需要 VCF 输出（INFO/CSQ）时 | 同上 |
| `--everything` (`-e`) | 不启用 | 想要「全套注释」时的官方快捷；也可按需逐项开 | 同上 |
| `--pick` / `--most_severe` / `--per_gene` | 都不启用（每变异多行） | 需要「一变异一行」时选一个；`--pick_order` 可改优先级 | 同上 |
| `--check_existing` | 不启用 | 需要 rsID/ClinVar 共定位信息时开启 | 同上 |
| `--af_gnomade` / `--af_gnomadg` / `--max_af` | 不启用 | 需要 gnomAD 频率与最大人群频率时（必须配 `--cache`） | 同上 |
| `--force_overwrite` | 不启用（输出存在即报错） | 批量重跑时开启 | 同上 |
| `--no_check_variants_order` | 不启用（要求输入有序） | 输入未排序时只能开它（更慢更吃内存） | 同上 |
| `--plugin` | 不启用 | 需要 LoF/dbNSFP/CADD 等，插件参数见插件页 | 同上（+ https://asia.ensembl.org/info/docs/tools/vep/script/vep_plugins.html ） |
| `--shift_3prime` | `0` | HGVS 需要 3′ 右对齐时设 `1`（`--shift_hgvs` 默认已是 1） | 同上 |

## 14. VerifyBamID2

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `--SVDPrefix` | 无 | GRCh38 用 `1000g.100k.b38.vcf.gz.dat` 前缀；必须与 BAM 的参考版本、chr 前缀一致 | https://github.com/Griffan/VerifyBamID |
| `--UDPath/--BedPath/--MeanPath` | 无 | GRCh37 的等价写法（三件套） | 同上 |
| `--max-depth` | `8000` | 超高深 panel 可下调以省内存 | 同上 |
| `--adjust-MQ` | `40` | BWA 比对官方建议值 50 | 同上 |

## 15. 其他

| 参数 | 官方默认值 | 何时需要改 | 来源 |
| --- | --- | --- | --- |
| `CollectVariantCallingMetrics -I/-D/-SD/-O` | 无 | Ti/Tv 等队列级/样本级指标评估 | https://gatk.broadinstitute.org/hc/en-us/articles/360035531112 |
| `samtools sort -T` | 依系统临时目录 | 大 BAM 指到大盘避免 `/tmp` 撑爆 | https://www.htslib.org/workflow/wgs-call.html |
| `bcftools stats -F/-s` | 未给 | 需要 fasta 与按样本统计时 | https://samtools.github.io/bcftools/bcftools.html |
