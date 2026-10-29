# 排障手册（症状 → 官方判据 → 处置）

原则：处置手段只能来自官方文档。官方只给判据没给命令的部分，本文件只写判据。

来源标签：CK = CNVkit 0.9.8 文档；MA = Manta v1.6.0 User Guide；DL = Delly README；VE/VF = Ensembl VEP 选项页/格式页；AS = AnnotSV 文档。

---

## A. CNVkit

### A1. 覆盖率在某一点之后突然全部变成 0

**官方判据**：CNVkit 只检查文件开头若干 reads 是否按位置排序，之后的乱序 reads 会被**静默忽略**，其后覆盖度为 0；如果 `.bai` 比 BAM 旧，CNVkit 会重建索引，但若索引本身错误则不会被发现，覆盖度会「mysteriously truncated to zero after a certain point」。
**处置**：正规排序 BAM；网络拷贝文件后用 `touch` 把 `.bai` 时间戳更新到 BAM 之后。
**出处**：CK/pipeline#bam-file-preparation

### A2. `fix` 校正过度或不足

**官方判据**：偏倚校正使用参考 .cnn 的 `gc`/`rmask` 列；若参考建时没算这两列，`fix` 会跳过并告警；若建参考后又用不同的偏倚开关跑 `fix`，偏倚会被过度或不足校正。
**处置**：`--no-gc`、`--no-rmask`、`--no-edge` 在 `reference` 与 `fix` 上**一致地开或一致地关**。
**出处**：CK/pipeline#fix

### A3. 参考建不起来 / 参考质量差

**官方判据**：参考应针对每个捕获 panel 单独构建；对照样本应与测试样本同类型（如 FFPE vs 新鲜）与同建库方案；官方基准显示**合并 pooled 参考**略优于逐对 tumor-normal；可用 `cnvkit.py metrics *.cnr -s *.cns` 找出噪声大的样本。
**处置**：先只跑 normal 样本建参考 → `metrics` 剔除差样本 → 重建参考；无对照时用平参考（`reference -o FlatReference.cnn ...`）或从肿瘤样本中挑 CNV 少的建参考（用 `scatter` 看原始 `.cnn`）。
**出处**：CK/pipeline#reference、CK/pipeline#paired-or-pooled-normals、CK/pipeline#with-no-control-samples、CK/quickstart

### A4. 性别判错 / X、Y 出现假增益缺失

**官方判据**：默认相对二倍体 X、单倍体 Y；女性样本对男性参考 → X 约 +1.0、Y 远低于 −3.0；男性样本对女性参考 → X 约 −1.0。`-y` 建参考后，`call`/`export`/`genemetrics` 未加 `-y` 会导致 X 拷贝数错误。低质量肿瘤样本中大量零覆盖 bin 会带偏 segment 均值。
**处置**：`cnvkit.py sex *.cnn *.cnr *.cns` 核查；用 `-x/--sample-sex` 显式指定；`-y` 全链路一致；必要时 `segment --drop-low-coverage` 重跑。
**出处**：CK/sex、CK/reports#sex

### A5. `call --filter ci` 没效果

**官方判据**：`ci`/`sem` 过滤依赖 `.cns` 里已有的 `ci_lo`/`ci_hi`（由 `segmetrics --ci` 写入）。
**处置**：先 `cnvkit.py segmetrics -s Sample.cn{s,r} --ci --pi`，再 `call --filter ci`。
**出处**：CK/germline、CK/reports#segmetrics、CK/pipeline#filtering-segments

### A6. germline 样本的纯合缺失整段消失

**官方判据**：`--drop-low-coverage` 会把 germline 深缺失整段删掉，官方明确 germline 场景**不应使用**。
**处置**：germline 去掉该选项。
**出处**：CK/germline

### A7. 肿瘤样本里出现「超深缺失」的假信号

**官方判据**：log2 < −15 的 bin 基本是零覆盖占位值（占位 −20，参考归一化最大正偏移 5），不是真实观测；肿瘤即使纯合缺失也会有正常细胞 reads。
**处置**：肿瘤场景加 `--drop-low-coverage`。
**出处**：CK/tumor

### A8. `metrics` 输出为空或参数被误解析

**官方判据**：`metrics` 的顺序敏感——`-s` 之后的一切都被当作 segment 数据集。
**处置**：把 `-s` 及其文件放在命令最后。
**出处**：CK/reports#metrics

### A9. WGS 结果噪声大、segment 太多、运行太慢

**官方判据**：官方给出 6 条优化：限制到基因区；`--target-avg-size` 在 30x 时 ≥1000bp；`segment -t` 收紧（CBS 用 `1e-6`）或换 `hmm`；`-p/--processes`；升级到最新版本；`--no-edge`。`batch -m wgs` 除第一条外自动执行。
**处置**：按上述逐条实施；WGS 必须给 `--annotate` 才有基因名。
**出处**：CK/nonhybrid#whole-genome-sequencing-wgs

### A10. 靶向扩增子（TAS）覆盖度异常低

**官方判据**：扩增子 reads 按设计本身就是 PCR 重复，若做了 MarkDuplicates/rmdup，剩余覆盖度会低到像没扩增。
**处置**：TAS 数据不要标重复；用 `batch -m amplicon` 或官方等价命令。
**出处**：CK/nonhybrid#targeted-amplicon-sequencing-tas

### A11. 想把 CNVkit 结果直接喂给注释工具却报格式不认

**官方判据**：`.cns` 需先 `call` 得到整数拷贝数，再 `export bed`/`export vcf`；`export bed` 默认只输出与 ploidy 不同的区间（`--show all` 输出全部）；`export vcf` 只对拷贝数≠预期倍性的段建记录。
**处置**：`call` → `export bed/vcf` → 再交 AnnotSV/VEP。
**出处**：CK/importexport#export、CK/calling

---

## B. Manta

### B1. 配置阶段直接报错

**官方判据（输入硬约束）**：所有输入比对文件与参考必须**染色体名称与顺序一致**并已用 samtools 建索引；不允许 `SEQ="*"`、不允许 SEQ 含 `=`、不允许 `=`/`X` CIGAR、碱基质量 >70 的记录被拒；RG 标签被忽略（**每个文件当作一个样本**）；参考需 `.fai`。
**处置**：统一参考与 BAM 的 contig 命名/顺序；重生成或修复 BAM；多 normal 文件会变成多样本联合分析，若只想一个样本就只给一个文件。
**出处**：MA#Input-requirements、MA#Configuration

### B2. WES 数据假阳性多 / 深度过滤误伤

**官方判据**：`--exome` 会**关闭所有高深度过滤器**（这些过滤器是为 WGS 着丝粒附近参考压缩设计的，靶向数据不能正确套用）；**即使给了 `--callRegions`，WES 仍必须加 `--exome`**。
**处置**：WES/靶向一律加 `--exome`；`--callRegions` 只用于限制区间，不替代 `--exome`。
**出处**：MA#ExomeTargeted、MA#Call-regions

### B3. 目标 SV 在结果里完全找不到

**官方判据**：SV 必须先是 `candidateSV.vcf.gz` 中的候选，才可能被打分；候选默认含 ≥8bp indel，Manta 自身打分从 50bp 起，<50bp 的落在 `candidateSmallIndels.vcf.gz` 中交由小变异 caller。
**处置**：先查 `candidateSV.vcf.gz`；若候选都没有，按官方高灵敏模式把 `minEdgeObservations` 与 `minCandidateSpanningCount` 改为 2。
**出处**：MA#Structural-Variant-predictions、MA#High-sensitivity-calling

### B4. tumor-only 结果没法判断可信度

**官方判据**：tumor-only 没有质量打分模型；官方建议用 `SAMPLE/PR[1] >= 15 || SAMPLE/SR[1] >= 15` 这类支持计数过滤，并把 `IMPRECISE` 作为可靠性指示；imprecise 调用可能没有 split read 计数。
**处置**：产出 `tumorSV.vcf.gz`，按 PR/SR 与 IMPRECISE 过滤，并记录阈值。
**出处**：MA#Unpaired-tumor-sample

### B5. GRCh38 上运行时间异常长

**官方判据**：大量 decoy/未定位小 contig 会拖慢；官方建议用 `--callRegions` 提供只含主染色体的 BED（文档直接给出 hg38 chr1–chr22/X/Y/M 坐标表）。
**处置**：构造主染色体 BED（bgzip + tabix）后重跑；WES 记得同时加 `--exome`。
**出处**：MA#Improving-runtime-for-references-with-many-short-contigs

### B6. 中断后想续跑 / 想只重打分

**官方判据**：运行中的 workflow 可随时中断并从断点恢复；`--rescore` 只重跑候选发现与打分，不重跑图构建；`--quiet` 关闭 stderr 日志但日志仍写 `workspace/pyflow.data/logs/pyflow_log.txt`。
**出处**：MA#Execution、MA#Advanced-execution-options

### B7. 需要人工核对某个 SV 的 reads

**官方判据**：`--generateEvidenceBam` 为候选 SV 输出证据 BAM 到 `results/evidence`，reads 带 `ZM:Z:${SV_ID}|${EVIDENCE_TYPE}`（PR/SR/SRM）；官方建议配 `--region` 限制范围。证据 BAM 的 reads 数可能多于 VCF 里的 PR/SR 计数（VCF 计数用更严的判据）。
**出处**：MA#Generating-evidence-bams

---

## C. Delly

### C1. 对 WES/靶向数据跑 `delly cnv` 没有结果

**官方判据**：`delly cnv` 是**全基因组** read-depth 方法，带 GC 与可比对性校正，**不支持 WES/靶向数据**。
**处置**：WES 用 CNVkit；Delly 的 SV（`sr`）仍可用于靶向数据的断点检测（但灵敏度受覆盖度限制，官方未给靶向专用参数）。
**出处**：DL#CNV-calling

### C2. 运行太慢

**官方判据（FAQ）**：短读长应用 `-x` 排除端粒、着丝粒与未定位 contig；`-q 20`、`-s 15` 更严格过滤；高覆盖数据 `-z 5`。
**出处**：DL#FAQ

### C3. `delly filter -f somatic` 无输出或报错

**官方判据**：somatic 过滤需要 tab 分隔的样本描述文件，第一列是 VCF/BCF 中的样本 ID，第二列必须是 `tumor` 或 `control`。
**处置**：核对 `samples.tsv` 的列内容与 VCF 样本名完全一致（大小写、下划线）。
**出处**：DL#Somatic-SV-calling

### C4. 非二倍体物种 / 多倍体样本

**官方判据**：SV 位点发现对任意倍性有效，但**分型模型假设倍性为 2**；CNV 调用允许在命令行设置基线倍性。
**处置**：多倍体样本的 SV 基因型需谨慎解读；CNV 用基线倍性参数。
**出处**：DL#FAQ

### C5. `merge` 参数用错（长读长/短读长/组装）

**官方判据**：`delly merge -l` 用于长读长，短读长**去掉** `-l`；CNV 位点合并用 `-e`；组装来源（无覆盖度）需 `-v 0`。
**出处**：DL#Germline-SV-calling、#Germline-CNV-calling、#Assembly-based

### C6. 跨染色体易位在输出里「只有一条记录」

**官方判据**：Delly 用 `INFO/CHR2` 表示第二条染色体；可用 `scripts/delly2bnd.py -v delly.bcf -r hg38.fa -o delly.bnd.bcf` 转成两记录 breakend 格式。
**出处**：DL#Alternate-alignments-for-genome-graphs

### C7. 组装级别 SV panel 构建失败

**官方判据**：组装无覆盖度，必须 `delly merge -l -v 0 -g hg38.fa -o panel.bcf ...`。
**出处**：DL#Assembly-based-SV-discovery

---

## D. Ensembl VEP（SV）

### D1. SV 输入没被识别为结构变异

**官方判据**：默认格式的 allele 串或 VCF 的 `SVTYPE` 必须属于支持列表（`INS`/`INS:ME...`/`DEL`/`DEL:ME...`/`DUP`/`DUP:TANDEM`/`TDUP`/`INV`/`CNV`/`CNV:TR`）；breakend 仅支持 VCF 输入；VCF 中 `DUP`/`DEL` 需 `END`。
**处置**：核对 `SVTYPE` 字符串与 `END`；breakend 不要用默认格式喂。
**出处**：VF

### D2. 超大 SV 被静默丢弃

**官方判据**：`--max_sv_size` 默认 `10000000`；设 `-1` 关闭该过滤，但官方警告关闭会导致大内存占用与慢运行。
**处置**：按需上调或关闭，并在结果里记录该阈值。
**出处**：VE

### D3. 想加 `--check_svs` 但用了 `--offline`

**官方判据**：`--check_svs` **当前需要数据库访问**，与 `--offline` 不兼容；输出字段 `SV`。
**处置**：要查已知 SV 时改用 `--database`（联网）；要完全离线则不启用该选项。
**出处**：VE

### D4. 需要「转录本被覆盖多少」这种定量证据

**官方判据**：`--overlaps` 以 VCF 形式报告转录本被 SV 覆盖的比例与长度。
**出处**：VE

---

## E. AnnotSV

### E1. 不知道 SV 类型列在哪、BED 怎么准备

**官方判据**：`-svtBEDcol` 指定 SV type 所在列（官方示例为第 4 列）；`-SVinputFile` 给 BED（也可给 VCF，官方 README 有说明，完整参数见 PDF）。
**处置**：先确认 BED 列结构，再设 `-svtBEDcol`；CNVkit 结果先用 `export bed` 输出绝对拷贝数区间。
**出处**：AS/quickstart.md、CK/importexport#export

### E2. 分级结果怎么读

**官方判据**：≥0.99 = Class 5 Pathogenic；0.90–0.98 = Class 4；−0.89–0.89 = Class 3 VUS；−0.90–−0.98 = Class 2；≤−0.99 = Class 1 Benign。
**处置**：按表映射；判定细节查官方 `Scoring_Criteria_AnnotSV_v3.4.xlsx`（Table1 loss、Table2 gain）。
**出处**：AS/ranking.md

---

## F. 解读层的通用判据（不是报错，但最容易出错）

1. **先证覆盖度再证 CNV**：CNVkit 官方给的下界是约 10x on-target 才可靠检出较大 CNA（CK/pipeline#reference）；WGS 30x 建议 bin ≥1000bp（CK/nonhybrid）。
2. **先证性别再证 X/Y**：`cnvkit.py sex` 结果与样本登记表不一致时，X/Y 上的所有 CN 结论作废（CK/sex#faq）。
3. **先证纯度/倍性再证绝对拷贝数**：`-m clonal` 依赖正确 `--purity`/`--ploidy`；默认 threshold 的外阈值按 100% 纯度设定，因此 0 拷贝/4+ 拷贝只在证据很强时才给出（CK/pipeline#calling-methods）。
4. **read-depth 与断点互相印证**：同一位点 CNVkit 段与 Manta `DEL`/`DUP` 应位置一致；不一致时要查 `--exome`、`--drop-low-coverage`、mappability 与参考批次（CK/tumor、MA#Known-Limitations）。
5. **已知库比对只用于解读分级**：ClinVar 用官方 FTP 的 VCF + `.tbi` 做区间重叠（https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/）；gnomAD-SV 与 DGV 的官方页面本次未能取得可逐字引用的文件/命令，只按「区间重叠 + 群体频率」判据处理，不改变 calling 结果。
6. **Manta 的「DEL」不等于 CNV 缺失**：官方明确 Manta 只分类 novel DNA adjacency，不检验深度/BAF，因此标注为 deletion 的是「删除型断点模式的染色体内易位」，需与 read-depth 结果合并判断（MA#Known-Limitations）。

---

## G. 诊断顺序（建议固定流程）

1. 输入合法性：BAM 排序/索引/重复标记、FASTA+`.fai`、contig 命名一致（CK/pipeline、MA#Input-requirements、DL#FAQ）。
2. 参考一致性：pooled vs flat、`--no-*` 开关一致、`-y` 全链路一致（CK/pipeline#fix、CK/sex）。
3. 噪声评估：`metrics`、`segmetrics`、`sex`（CK/reports）。
4. calling 策略：germline（默认 purity/ploidy + `--filter ci`）vs tumor（`--purity/--ploidy` + `--drop-low-coverage`）（CK/germline、CK/tumor）。
5. 断点检测：Manta（`--exome` 判据、tumor-only 的 PR/SR 过滤）与 Delly（`merge`+`-v`+`filter`）分工（MA、DL）。
6. 注释：CNVkit `call`+`export` → AnnotSV；SV VCF → VEP（`SVTYPE`/`END` 合规）（CK/importexport、AS、VF）。
7. 解读：覆盖度、性别、纯度、已知库四级证据齐全后才下结论（见 F 节）。
