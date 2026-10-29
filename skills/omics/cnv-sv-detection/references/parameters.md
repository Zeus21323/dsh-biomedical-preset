# 参数与默认值速查（全部取自官方文档）

标注「官方原文」的数值即文档逐字给出的默认值/判据；标注「无官方默认」表示官方文档未给默认值，使用时必须显式指定。
来源简写：
- CK = CNVkit 0.9.8 文档（https://cnvkit.readthedocs.io/en/stable/）
- MA = Manta v1.6.0 User Guide（https://raw.githubusercontent.com/Illumina/manta/v1.6.0/docs/userGuide/README.md）
- DL = Delly README（https://raw.githubusercontent.com/dellytools/delly/main/README.md）
- VE = Ensembl VEP 选项页（https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html）
- VF = Ensembl VEP 数据格式页（https://www.ensembl.org/info/docs/tools/vep/vep_formats.html）
- AS = AnnotSV（https://github.com/lgmgeo/AnnotSV）

---

## 1. CNVkit

### 1.1 `target` / `access` / `antitarget` / `autobin`

| 参数 | 官方默认/取值 | 说明与依据 |
| --- | --- | --- |
| target 平均 bin 大小 | **267**（官方原文：default of 267） | 使拆分大外显子后最小 bin 仍约 200bp（外显子平均约 200bp）— CK/pipeline#target |
| `--split` | 无官方默认（开关） | 拆分大区间；与 `--annotate`、`--short-names` 任一使用时会生成新 target BED — CK/pipeline#target |
| `--annotate` | 无官方默认 | 用 refFlat 等给区间贴基因名 — CK/pipeline#target |
| `--short-names` | 无官方默认 | 逗号分隔的多 accession 取覆盖区间最多的那个作为标签 — CK/pipeline#target |
| 降低 bin 大小的前提 | on-target 覆盖度 **≥200x–300x**、读长 100bp | 官方：只有满足此前提才值得把 target bin 降到 100bp — CK/pipeline#bin-size-and-resolution |
| 每 bin 目标 reads | 官方经验值 **200–300 reads/bin** | CK/pipeline#bin-size-and-resolution |
| `access -s` | 示例值 10000 | 忽略短于该长度的不可及区，避免碎片化 antitarget bin — CK/pipeline#access |
| `access -x` | 可重复 | 排除已知不可比对区（如 UCSC ENCODE mapability）— CK/pipeline#access |
| `antitarget -g` | 建议总是给 | 只在 access 区内部署 off-target bin — CK/pipeline#antitarget |
| off-target bin 大小 | 官方「cautious default」偏大，鼓励自行计算 | 建议按「target 平均长度 × on-target 富集倍数」估算，使 on/off bin reads 数接近；可用 `autobin` 快速估计 — CK/pipeline#off-target-bin-size |
| `autobin -b` | 示例 50000（WGS） | CK/pipeline#autobin |
| `autobin -m` | `hybrid`（默认）、`amplicon`、`wgs` | CK/pipeline#batch、CK/nonhybrid |
| access 文件 | 官方随发行提供 `data/access-5kb-mappable.hg19.bed` | CK/pipeline#access |

### 1.2 `reference` / `fix`

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| `-f/--fasta` | 强烈建议给 | 计算每 bin 的 `gc`（GC 比例，忽略 N）与 `rmask`（小写非 N 比例）；不给则无这两列 — CK/pipeline#reference |
| `--no-gc` / `--no-rmask` | 关闭对应校正 | 若建参考时关闭，`fix` 也会跳过并告警；开关必须前后一致 — CK/pipeline#fix |
| `--no-edge` | 关闭 edge（targeting density）校正 | TAS 与 WGS 提速时官方推荐关闭 — CK/nonhybrid、CK/bias |
| 参考样本 | 官方推荐**合并成一个 pooled reference** | 队列同平台时 pooled 略优于逐对 tumor-normal；即使配对正常也存在批次偏倚 — CK/pipeline#paired-or-pooled-normals |
| 参考可用的最低测序深度 | 约 **10x** on-target | 低于此伪 segment 增多，小尺度/亚克隆 CNA 难推断 — CK/pipeline#reference |
| `fix` bin 过滤 | reference log2 < **−5** 丢弃；reference 内 spread > **1.0** 丢弃 | CK/pipeline#fix |
| bin 权重依据 | bin 大小、该 bin 在参考中 log2 偏离 0 的程度、参考中的 spread | CK/pipeline#fix |
| 平参考 | `reference -o FlatReference.cnn -f ... -t ... -a ...` | 无对照/少样本时的三种官方用途 — CK/pipeline#with-no-control-samples |

### 1.3 `segment`

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| `-m/--method` | `cbs`（默认）；`haar`；`hmm`；`hmm-tumor`；`hmm-germline`；`none` | CK/pipeline#segmentation-methods |
| `-t/--threshold` | 无统一默认（传给底层方法的显著性阈值） | WGS 场景官方建议 CBS 用 `1e-6` — CK/nonhybrid |
| `--drop-low-coverage` | 丢弃 log2 < **−15** 的 bin | 零覆盖占位值为 −20，参考归一化最大正偏移 5 — CK/tumor |
| `--drop-outliers` | **默认启用** | 按局部变异丢弃偏离滚动均值的 bin — CK/pipeline#bin-filtering |
| weight=0 的 bin | 分割前丢弃 | CK/pipeline#bin-filtering |
| `-p` | 可并行（HMM 方法除外） | 按染色体臂独立运行 — CK/pipeline#segment |
| `--vcf` + `-i -n -z --min-variant-depth` | 可选 | 先按 log2 分割，再在每个 log2 段内按 SNP 等位频率二次分割 — CK/pipeline#segment |
| `--rscript-path` | 可选 | R/DNAcopy 装在非默认位置时指定 `Rscript` — CK/pipeline#segmentation-methods |

### 1.4 `call`

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| `-m/--method` | `threshold` / `clonal` / `none`；germline 默认即 `threshold` | CK/pipeline#call、CK/germline |
| `-t` 默认阈值 | **−1.1, −0.4, 0.3, 0.7** → 拷贝数 0/1/2/3 | 内阈值 ±0.2/−0.25 对纯度低至 30% 的单拷贝变化敏感；外阈值按 100% 纯度设 — CK/pipeline#calling-methods |
| `--purity` | 无官方默认 | 重标定 log2 到「完全纯肿瘤样本」尺度 — CK/pipeline#transformations |
| `--ploidy` | 默认二倍体常染色体；Y 单倍体；X 依参考性别 | CK/pipeline#transformations |
| `-y/--male-reference/--haploid-x-reference` | 关（默认二倍体 X） | 建参考时用了，`call`/`export`/`genemetrics` 必须同样用 — CK/sex |
| `-x/--sample-sex` | 自动推断 | 与 `-y` 语义不同 — CK/sex |
| `--center` | 无官方默认；可选 `median`、`mode` | 高异倍体样本用 `median`（CK/tumor）；`mode` 见 CK/pipeline#transformations |
| `-v/--vcf` | 可选 | 输出 `baf`、`cn1`、`cn2`（PSCBS 法：总拷贝数 × BAF 后取整）— CK/pipeline#allele-frequencies-and-counts |
| `--filter` | 可组合 `cn` / `ampdel` / `ci` / `sem` | `ampdel` 只留 ≥5 拷贝扩增与 0 拷贝缺失；跨染色体或等位特异拷贝数不同的段不合并 — CK/pipeline#filtering-segments |

### 1.5 报告

| 命令/参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| `metrics` 输出 | segment 数、SD、MAD、IQR、Tukey biweight midvariance | 官方启发式：segment 数 × biweight midvariance，越大越不可靠 — CK/reports#metrics |
| `metrics -s` 的位置 | **必须放在参数最后**（`-s` 之后全部视为 segment 数据集） | CK/reports#metrics |
| `genemetrics -t` | 默认 **0.2** | 纯度不足的体细胞 CNA 需更低阈值 — CK/reports#genemetrics |
| `genemetrics -m/--min-probes` | 默认 **3** | <3 个 bin 的变化不报 — CK/reports#genemetrics |
| `genemetrics -y` | 与建参考一致 | 否则 X 上出现大量伪增益/缺失 — CK/reports#genemetrics |
| `segmetrics --ci` | bootstrap **100 次重采样** | 输出 `ci_lo`/`ci_hi`，供 `call --filter ci` 使用 — CK/reports#segmetrics |
| `segmetrics --pi` | 2.5–97.5 百分位 | 输出 `pi_lo`/`pi_hi` — CK/reports#segmetrics |
| `breaks` | 无参数 | 列：gene、chromosome、location、change、probes_left、probes_right — CK/reports#breaks |
| `sex` 输出 | 样本名、推断性别、X/Y log2 | 示例：`cnv_reference.cnn Female -0.176 -1.061` — CK/reports#sex |

### 1.6 导出

| 命令/参数 | 官方说明 | 依据 |
| --- | --- | --- |
| `export bed` | 默认只输出拷贝数≠ploidy（默认 2）的区间；`--show all` 输出全部 | CK/importexport#bed |
| `export vcf` | 只对拷贝数≠预期倍性的段建记录；`-x` 指定性别，`-i` 指定样本 ID | CK/importexport#vcf |
| `export seg` / `cdt` / `jtv` | 多样本批量导出 | CK/importexport |
| `export theta` | 生成 THetA2 的 `.interval_count`；给 `-v` 时额外产出 tumor/normal 的 SNP 计数文件 | CK/importexport#theta |

---

## 2. Manta

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| 配置入口 | `${MANTA_INSTALL_PATH}/bin/configManta.py` | MA#Configuration |
| 运行入口 | `${MANTA_ANALYSIS_PATH}/runWorkflow.py` | MA#Execution |
| `--bam` | 可重复；多个即「联合 diploid 多样本分析」，每个文件一个样本 | MA#Germline-configuration-examples |
| `--normalBam` / `--tumorBam` | 配对即 somatic 减除分析 | MA#Somatic-configuration-examples |
| 只给 `--tumorBam` | tumor-only 模式（无打分模型） | MA#Unpaired-tumor-sample |
| `--referenceFasta` | 必填；须与比对所用参考一致且有 `.fai` | MA#Input-requirements |
| `--runDir` | 必填；生成 `runWorkflow.py` | MA#Configuration |
| `-j`（runWorkflow） | 示例 8 | MA#Execution |
| `--exome` | 开关；关闭所有高深度过滤器 | MA#ExomeTargeted |
| `--callRegions` | 单个 bgzip+tabix 的 BED；不替代 `--exome` | MA#Call-regions |
| `--rna` | 开关；实验性；要求恰好一个 normal 输入 | MA#RNA-Seq |
| `--generateEvidenceBam` | 开关；建议配 `--region` | MA#Generating-evidence-bams |
| `--outputContig` | 开关；INFO 增加 `CONTIG` | MA#Output-assembled-contigs |
| `--config` | 指定自定义 `configManta.py.ini` | MA#Advanced-configuration-options |
| `--allHelp` | 列出开发/调试级参数 | MA#Advanced-configuration-options |
| 最小 indel 尺寸 | **8**（默认可配置下限） | MA#Detected-variant-classes |
| Manta 自身打分起点 | **50bp** | MA#Structural-Variant-predictions |
| `minEdgeObservations` | **3**（官方高灵敏建议改 **2**） | MA#High-sensitivity-calling |
| `minCandidateSpanningCount` | **3**（官方高灵敏建议改 **2**） | MA#High-sensitivity-calling |
| tumor-only 过滤示例 | `SAMPLE/PR[1] >= 15 || SAMPLE/SR[1] >= 15` | MA#Unpaired-tumor-sample |
| 内存经验值 | germline **<1Gb/core**；cancer/FFPE/高度重排 **<2Gb/core** | MA#Runtime-hardware-requirements |
| 性能基准 | NA12878 50x WGS，20 物理核 **<20 分钟**，峰值 RSS **2.35 Gb** | MA#Runtime-hardware-requirements |
| I/O 估算 | 约 **1.1 次**输入比对文件读取 | MA#Runtime-hardware-requirements |

---

## 3. Delly

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| 子命令 | `sr`（短读长）、`lr`（长读长）、`asm`（组装）、`cnv`（read-depth）、`merge`、`filter` | DL |
| `-g` | 参考 FASTA（需索引） | DL#Running-Delly |
| `-x` | 排除图谱；短读长推荐 | DL |
| `-o` | 输出 BCF/VCF | DL |
| `-v` | 传入位点列表做重分型 | DL#Germline-SV-calling |
| `-y`（lr/asm） | `ont` / `pb`；`diploid` / `squashed` | DL#Long-read、#Assembly-based |
| `delly merge -l` | 长读长时加；短读长去掉 | DL#Germline-SV-calling |
| `delly merge -e` | CNV 位点合并用 | DL#Germline-CNV-calling |
| `delly merge -v 0` | 组装来源（无覆盖度）时用 | DL#Assembly-based |
| `delly filter -f` | `somatic` / `germline` | DL |
| `delly filter -s` | tab 分隔样本表：列1 样本 ID，列2 `tumor`/`control` | DL#Somatic-SV-calling |
| `delly filter --hwe` | 示例 `0.000001`（germline，长读长示例） | DL#Germline-SV-calling |
| `delly filter -p` | SCNA 的 somatic 过滤示例中启用 | DL#Somatic-copy-number-alterations |
| `-q` | 官方提速建议 **20** | DL#FAQ |
| `-s`（reads 过滤） | 官方提速建议 **15** | DL#FAQ |
| `-z`（最小 CNV 大小） | 高覆盖建议 **5** | DL#FAQ |
| `-p`（样本纯度，cnv） | 无官方默认；影响 SCNA 灵敏度 | DL#Somatic-copy-number-alterations |
| 基线倍性（cnv） | 可在命令行设置（官方未给参数名默认值） | DL#FAQ |
| `-c` / `-u` | 输出 `.cov.gz` read-depth profile / `.seg.bed` 分割 | DL#CNV-calling |
| 分型模型倍性 | 固定 **2**（SV 分型）；CNV 可设基线倍性 | DL#FAQ |
| 覆盖度输出 | `bcftools query ... %ID[\t%RDCN]` 取拷贝数 | DL#CNV-calling |

---

## 4. Ensembl VEP（SV）

| 参数 | 官方默认/取值 | 依据 |
| --- | --- | --- |
| 输入 | `-i/--input_file`；可 gzip；未给则读 STDIN | VE |
| `--format` | `ensembl` / `vcf` / `hgvs` / `id` / `region` / `spdi`；默认自动识别 | VE |
| 输出 | `-o/--output_file`；默认 `variant_effect_output.txt`；写 `STDOUT` 会强制 quiet | VE |
| `--vcf` | 输出 VCF，注释写入 INFO 的 `CSQ`，字段以 `|` 分隔 | VE |
| `--cache` / `--offline` | 用本地 cache；`--offline` 完全不连库 | VE |
| `--assembly` | 多套 cache 并存时必填 | VE |
| `--fork` | 无默认；官方建议 **4** | VE |
| `--max_sv_size` | 默认 **10000000**；`-1` 关闭 | VE |
| `--check_svs` | 默认关；**需数据库访问**；与 `--offline` 不兼容；输出字段 `SV` | VE |
| `--overlaps` | 默认关；报告转录本被 SV 覆盖的比例与长度 | VE |
| 支持的 SVTYPE | `INS`/`INS:ME(:ALU|:HERV|:LINE1|:SVA)`、`DEL`/`DEL:ME(:...)`、`DUP`、`DUP:TANDEM`、`TDUP`、`INV`、`CNV`（`CN0`、`CN=4` 等）、`CNV:TR` | VF |
| Breakend | 仅 VCF 输入；`TG[12:58877476[`、`T.`、`.G`、逗号分隔多 ALT | VF |
| SV 必需 INFO | VCF 中需 `SVTYPE`（DUP/DEL 还需 `END`） | VF 示例 |

---

## 5. AnnotSV

| 参数 | 官方取值 | 依据 |
| --- | --- | --- |
| `-SVinputFile` | 官方示例 `test.bed` | AS/quickstart.md |
| `-outputFile` | 官方示例 `./test.annotated.tsv` | AS/quickstart.md |
| `-svtBEDCOL` | 官方示例 `-svtBEDcol 4`（SV type 所在列） | AS/quickstart.md |
| 安装 | `make PREFIX=. install`、`make PREFIX=. install-human-annotation`、`make PREFIX=. install-mouse-annotation` | AS/quickstart.md |
| 环境变量 | `export ANNOTSV=/path/to/install/AnnotSV`（csh: `setenv`） | AS/quickstart.md |
| 基因组版本 | GRCh37 或 GRCh38，用户指定 | AS/annotations.md |
| 分级阈值 | ≥0.99 C5；0.90–0.98 C4；−0.89–0.89 C3；−0.90–−0.98 C2；≤−0.99 C1 | AS/ranking.md |
| 其余参数 | **官方 quickstart 未列**，完整参数见 `README.AnnotSV_3.5.7.pdf` | AS |

---

## 6. 官方缺失（不设默认值）

- GATK-SV：无本地命令行参数可引用（只有 Terra 输入/输出名）。
- gnomAD-SV / DGV：无官方可引用命令行与文件路径（页面动态渲染/抓取失败）。
- CNVkit `tutorial.html`：不存在（404），以 `quickstart.html` 为准。
