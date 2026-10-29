# 排错：报错 / 症状 → 官方出处 → 处理

每条都给出官方原文要点与 URL。凡官方没有给出处理办法的，如实写明「官方文档未提供对应条目」。

## A. VQSR / 过滤

### A1. `VariantRecalibrator` 报「No data found」
官方原文要点：`--max-gaussians` 设定期望的聚类数；当数据给出的独立聚类更少（小数据集常见）时，工具会报 insufficient data / No data found，「In this case, try decrementing the `--max-gaussians` value.」
处理：逐步下调 `--max-gaussians`（生产流程 INDEL 用 4、SNP 用 6 已是下调后的值）。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering

### A2. `java.lang.NumberFormatException`（VariantFiltration）
官方原文要点：阈值字面量必须匹配 callset `##INFO` 行声明的类型 —— Integer 写整数（`0`），Float 写小数（`0.0`）；不匹配就抛 `java.lang.NumberFormatException`。
处理：先看 VCF header 里该注释的类型，再改字面量。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering

### A3. 过滤表达式写错却没有任何提示
官方原文：「If a filter expression is misspelled, the tool does not give a warning, so be sure to carefully review filter expressions for correctness.」
处理：把表达式与 `##INFO` 注释名逐个比对；建议过滤后统计各 FILTER 标签的记录数做体检。
来源：同上

### A4. 硬过滤后仍有大量明显坏变异（复合表达式失效）
官方原文要点：复合表达式（`&&`/`||`，引用多个属性）中，缺任一属性的记录会被整体判为 PASS，即使它在另一部分满足过滤条件。
处理：改成一条属性一个 `-filter`/`--filter-name`（官方给了「preferable」的对照示例）。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering 、 https://gatk.broadinstitute.org/hc/en-us/articles/360041850471-VariantFiltration

### A5. 小队列跑了 ExcessHet 过滤，结果大面积被标 Filter
官方原文要点：ExcessHet 过滤只适用于「a large number of samples, e.g. hundreds of unrelated samples」；小队列不该触发，近亲样本会抬高 ExcessHet（可用 pedigree 把注释限制在 founders）。
处理：外显子小队列直接跳过 ExcessHet 步骤。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531112--How-to-Filter-variants-either-with-VQSR-or-by-hard-filtering

### A6. VQSR 在外显子项目上效果很差 / 跑不动
官方原文要点：VQSR 不适合「targeted gene panels or exome studies with fewer than 30 exomes」；官方另指出外显子不能用 DP 注释（捕获深度波动极大）；样本不足时可补公共外显子 BAM（重新生成 GVCF 联合分型，**不能直接合并 VCF**）。
处理：≥30 例外显子 → VQSR 且去掉 `-an DP`；<30 例 → 硬过滤。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants 、 https://gatk.broadinstitute.org/hc/en-us/articles/4402736812443-Which-training-sets-arguments-should-I-use-for-running-VQSR

### A7. 用 `InbreedingCoeff` 过滤时工具报找不到注释 / 值为空
官方原文要点：`InbreedingCoeff` 是群体统计量，**至少 10 个样本**才算得出；样本更少或家系样本应把该注释整条去掉。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants 、 https://gatk.broadinstitute.org/hc/en-us/articles/4402736812443-Which-training-sets-arguments-should-I-use-for-running-VQSR

### A8. 低覆盖样本手工过滤怎么看都不对
官方原文要点：覆盖度 <10x 时手工阈值几乎不可能可靠区分真假（原文措辞极强），应改走 VQSR 或重新评估实验设计。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037499012-I-am-unable-to-use-VQSR-recalibration-to-filter-variants

### A9. 外显子 callset 上 `DP` 上限过滤掉一堆真变异
官方原文要点：「for exomes, a straight DP filter shouldn't be used because the relationship between misalignments and depth isn't clear for capture data」。
处理：WES 不用 DP 上限过滤；WGS 的 DP 阈值应设在平均深度的 5–6 个 sigma 处。
来源：同上

## B. 联合分型（GenomicsDBImport / GenotypeGVCFs）

### B1. `GenomicsDBImport` 报内存/TileDB 相关怪异错误
官方原文要点：`-Xmx` 必须比物理内存少**至少几 GB**，因为原生 TileDB 库还要额外内存；不给足会「result in confusing error messages」。
处理：下调 `-Xmx`，或用 `--batch-size` 限制同时打开的 reader 数。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036883491-GenomicsDBImport

### B2. `GenomicsDBImport` 中途磁盘写满
官方原文要点：导入过程会用临时盘，「The amount of temporary disk storage required can exceed the space available, especially when specifying a large number of intervals」，用 `--tmp-dir` 指到大盘。
来源：同上

### B3. workspace 已存在导致失败
官方原文要点：`--genomicsdb-workspace-path` 必须指向「a non-existent or empty directory」。
处理：换新路径或先清空（确认无下游依赖后再删）。
来源：同上

### B4. 报输入 GVCF 同一位置有多条记录
官方原文要点：「Input GVCFs cannot contain multiple entries for a single genomic position」。
处理：检查 GVCF 是否被外部工具改写过（如手工 merge/annotate）；用原始 HaplotypeCaller 输出重跑。
来源：同上

### B5. `GenotypeGVCFs` 一次传多个 `-V` 失败
官方原文要点：「Cannot take multiple GVCF files in one command.」
处理：先 `GenomicsDBImport`（或 CombineGVCFs）聚合，再 `-V gendb://workspace`。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037057852-GenotypeGVCFs

### B6. 用第三方「GVCF」喂 GenotypeGVCFs 结果异常
官方原文要点：只接受 HaplotypeCaller（或 CombineGVCFs）产出的 GVCF；别的程序自称 GVCF 的文件缺少「accurate genotype likelihoods for every position」。
来源：同上

### B7. 以为在 GVCF 阶段能提高 calling 阈值
官方原文要点：`-ERC GVCF` / `-ERC BP_RESOLUTION` 下置信阈值被自动置 0，**命令行无法覆盖**，只能在 GenotypeGVCFs 阶段设。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller

### B8. 新增样本后要全部重跑
官方原文要点：GenotypeGVCFs 很快，可在样本加入队列时随时重跑（解决 N+1 问题）；只需为新样本生成 GVCF 并重建 datastore。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035535932-Germline-short-variant-discovery-SNPs-Indels-

## C. 比对 / 去重 / BQSR

### C1. `MarkDuplicates` 报输入未排序
官方原文要点：`INPUT`「Must be coordinate sorted」。
处理：先 `samtools sort`，再去重，然后重建索引。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036756891-MarkDuplicates-Picard

### C2. 去重率异常高（不是数据问题的那种）
官方原文要点（samtools 文档）：「Duplicate marking is not always useful. For example, some amplicon based approaches mean that sequencing starts at the same sites which would mistakenly look like duplication.」
处理：amplicon/低起始量 panel 慎用去重，或在报告里说明去重口径。
来源：https://www.htslib.org/algorithms/duplicate.html

### C3. 用 samtools 路线去重结果与 Picard 对不上
官方原文要点：markdup 默认 `--mode t`（template）；要接近 Picard 用 `--mode s`，并加 `-d 2500 --include-fails -S`（官方给出的等价命令）。
来源：同上

### C4. `AddOrReplaceReadGroups` 之后原有 read group 全没了
官方原文要点：该工具只能把整个文件指派给单一 read group；若文件本来有多个 RG，原值会丢失。
处理：多 lane 数据先分别处理，再在合并时保留各自 RG；不要让一个 BAM 承载多个文库。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037226472-AddOrReplaceReadGroups-Picard

### C5. `AddOrReplaceReadGroups` 报标签非法
官方原文要点：标签值须匹配 `'^[ -~]+$'`（ASCII 32–126），空格是唯一允许的非打印字符。
处理：样本名/文库名去掉中文、全角、制表符。
来源：同上

### C6. BQSR 后质量分数变化很小或报数据不足
官方原文要点：重校准质量取决于每个 bin 的观测碱基数；「We usually expect to see more than 100M bases per read group」；数据太少（小 panel）是官方明确认可跳过 BQSR 的场景。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR

### C7. 拿 A 样本的 recal table 给 B 样本做 ApplyBQSR
官方原文要点：只能用**同一** BAM/CRAM 产生的 covariates table。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037268511-ApplyBQSR

### C8. 没有 dbSNP 等已知位点，BQSR 跑不了
官方给出的是流程而非命令：先不重校准做一轮 calling → 取高置信位点当 known sites → 重校准后再 calling，可迭代。官方同时指出 training set 这类资源「difficult to bootstrap」。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035890531-Base-Quality-Score-Recalibration-BQSR 、 https://gatk.broadinstitute.org/hc/en-us/articles/360035890831-Known-variants-Training-resources-Truth-sets
（**官方文档未提供可直接执行的命令**。）

### C9. bwa-mem2 换版本后比对结果/索引异常
官方 README 要点：2020-10-10 起索引结构改为单一 2bit.64 并压缩后缀数组，「you will need to rebuild the index」；build 索引时内存需求约为参考基因组大小的 28N GB。
来源：https://github.com/bwa-mem2/bwa-mem2

## D. WES 区间与覆盖度 QC

### D1. 加了 `-L` 之后 callset 变了 / 丢了变异
官方原文要点：区间使用不当会引入 artifact —— 区间外的 reads 会被丢弃，而这些 reads 可能本来参与变异判定（例如 lost mates）；GATK 生产流程对靶向测序两侧各留 100 bp padding。
处理：`-ip 100`，并用 interval_list（带序列字典）而非裸坐标。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035531852-Intervals-and-interval-lists

### D2. BED 当 interval_list 用，坐标差 1
官方原文要点：Picard `.interval_list` 与 GATK `.list` 是 1-based，BED 起始是 0-based；引擎靠 `.bed` 后缀识别坐标系。
处理：统一用 `.interval_list`；自造 BED 时注意偏移。
来源：同上

### D3. `-L` 给了区间但 padding 没生效
官方参数表：`--interval-padding` 默认值就是 `0`。
处理：显式 `-ip 100`。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller

### D4. 找不到 GRCh38 的 Broad 外显子区间
官方原文要点：hg38 资源集「provided as-is」且「we are still missing the Hg38 version of the Broad's exome intervals」；b37 才有 `Broad.human.exome.b37.interval_list`。
处理：GRCh38 WES 用捕获试剂盒厂商给的 BED/interval_list。
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360035890811-Resource-bundle

### D5. `CollectHsMetrics` 结果里百分比看着像 0.98 而不是 98
官方原文要点：「Metrics labeled as percentages are actually expressed as fractions!」
来源：https://gatk.broadinstitute.org/hc/en-us/articles/360036714891-CollectHsMetrics-Picard

### D6. 手头只有 BED，`CollectHsMetrics` 要 interval_list
官方原文：可用 Picard 的 BedToInterval 工具转换（该工具页本技能未抓取，**官方在此未给出可直接执行命令**）。
来源：同上

### D7. mosdepth 报 `libhts.so not found` / `could not import: hts_check_EOF`
官方原文：前者把 `LD_LIBRARY_PATH` 指到含 `libhts.so` 的目录（例 `LD_LIBRARY_PATH=~/src/htslib/ mosdepth -h`）；后者说明 htslib 版本太旧，需更新。
来源：https://github.com/brentp/mosdepth

### D8. mosdepth 结果与 samtools depth 口径不一致
官方 usage 默认 `-F/--flag 1796`（排除 unmapped/secondary/QC-fail/duplicate），`-Q/--mapq 0`；`-x/--fast-mode` 会跳过 CIGAR 内部操作与 mate overlap 修正。口径不同结果就不同，报告里要写清参数。
来源：同上

## E. VEP 注释

### E1. 输出文件已存在直接失败
官方原文：默认输出存在即报错，用 `--force_overwrite`。
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html

### E2. `--offline` 下没有 HGVS / 参考校验报错
官方原文：`--fasta` 在 offline 模式下取 HGVS（`--hgvs`）与 `--check_ref` 时**必需**；首次使用会建索引，耗时几分钟。
来源：同上

### E3. `--dir_cache` 没生效，VEP 仍去 `$HOME/.vep` 找缓存
官方原文：`INSTALL.pl --CACHEDIR` 改了缓存目录后，运行 VEP 必须显式 `--dir_cache`；插件目录同理由 `--dir_plugins` 指定。
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_download.html

### E4. 输入 VCF 未排序报错
官方原文：默认要求有序；`--no_check_variants_order` 可放行，但会更慢更吃内存。
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html

### E5. 插件编译失败但 VEP 仍然「成功」
官方原文：默认即使插件报问题，VEP 运行仍算成功；`--safe` 让插件告警/编译错误直接失败 —— 流水线里建议开。
来源：同上

### E6. `--plugin` 的参数怎么写
官方 options 页只给 `--plugin [plugin name]`（可重复多次）；具体插件（LoF/dbNSFP/CADD…）的参数、数据文件准备在插件专页。**本技能不臆造插件参数**。
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_plugins.html

### E7. 小数据集里 `--af_esp` 直接报错
官方原文：`--af_esp` 已废弃，自 VEP 107 起会产出 error。
来源：https://asia.ensembl.org/info/docs/tools/vep/script/vep_options.html

## F. 污染估计

### F1. VerifyBamID 结果与预期差很远（污染被低估）
官方原文要点：用 pooled 等位频率会让污染被低估（1000G 上模拟 1%–20% 时 CEU 低估 20%、YRI 40%、FIN 51%、CHS 73%），该工具是 ancestry-agnostic 方法，偏差降到 2–5%。
处理：用官方提供的 `1000g.100k.b38.vcf.gz.dat`（GRCh38，带 chr 前缀）资源，别自造频率面板。
来源：https://github.com/Griffan/VerifyBamID

### F2. GRCh37/GRCh38 混用资源导致跑不出结果
官方原文要点：GRCh37 用**不带 chr 前缀**的 1000G 版参考（`human_g1k_v37.fasta`），GRCh38 用**带 chr 前缀**版本（`GRCh38_full_analysis_set_plus_decoy_hla.fa`）+ `--SVDPrefix ...b38.vcf.gz.dat`。
来源：同上

### F3. 污染数值看哪一列
官方原文：输出 `.selfSM`（格式与 VB1 相同），**`FREEMIX` 即估计的污染比例**；另有 `Ancestry` 文件记录 PC 坐标。
来源：同上

## G. 文档抓取本身

### G1. 直接抓 `gatk.broadinstitute.org` 页面得到 403 / 「Just a moment...」
该站前面是 Cloudflare 托管挑战，普通 HTTP 抓取会被挡（本次抓取即如此）。可改用其帮助中心 API 拿同一篇文章正文：
`https://gatk.broadinstitute.org/api/v2/help_center/en-us/articles/<article_id>.json`（`article.body` 为 HTML，`article.html_url` 为人类可读 URL）。
检索文章 id：`https://gatk.broadinstitute.org/api/v2/help_center/articles/search.json?query=<keyword>`。
说明：这是 Zendesk 帮助中心的标准只读接口，返回内容与页面正文一致；本条属工具链经验，非 GATK 文档条目。
