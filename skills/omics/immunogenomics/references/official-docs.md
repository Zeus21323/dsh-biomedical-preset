# 官方文档清单与抓取记录

抓取时间：2026-10-29（Asia/Shanghai）。状态列记录实际 HTTP 结果与替代路径，**凡标注"未提供可直接执行命令"的，SKILL.md 中不写自造命令**。

## 0. 抓取异常与替代路径（必须先看）

| 任务书给的 URL | 实际结果 | 采用的可访问官方地址 |
|---|---|---|
| `https://docs.milaboratories.com/mixcr/` | 跨域 301 → `mixcr.com`（`../reference/presets/` 为 404） | `https://mixcr.com/mixcr/reference/`（MkDocs 站点本体） |
| `https://github.com/liulab/TRUST4` | 仓库不存在（GitHub 404 "Page not found"） | `https://github.com/liulab-dfci/TRUST4` |
| `https://icbi-lab.github.io/quanTIseq/` | HTTP 404（`Page not found · GitHub Pages`） | `https://icbi.i-med.ac.at/software/quantiseq/doc/` |
| `https://bioconductor.org/packages/release/bioc/vignettes/CATALYST/inst/doc/CATALYST.html` | HTTP 404；`.../inst/doc/` 目录亦是 404 | `https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html` 与 `.../differential.html` |
| `https://cibersortx.stanford.edu/` | 200，但只有登录框；`about.php` 返回 "You are currently not logged in." | 同上（内容需注册登录，按"官方文档未提供可直接执行的命令"处理） |
| `https://github.com/grst/abis` | 404（仓库路径不成立） | `https://omnideconv.org/immunedeconv/reference/deconvolute_abis.html`（封装层官方文档） |
| `raw.githubusercontent.com` | 间歇 `TypeError: fetch failed`（网络层） | 改用 GitHub 页面正文（`article` 元素）读取 |

## 1. 免疫组库（TCR/BCR）

### 1.1 MiXCR

| 页面 | URL | 状态 | 取到的可执行内容 |
|---|---|---|---|
| Presets（概念 + 分步流程） | https://mixcr.com/mixcr/reference/overview-presets/ | 200 | preset = YAML 步骤列表；`mixcr analyze <preset>` 用法；**六步分步示例**（align → refineTagsAndSort → assemblePartial → assemble → assembleContigs → exportClones）；preset 只需在 align 指定；`generic-amplicon` 的 mixin 示例 |
| Built-in presets（预设全表） | https://mixcr.com/mixcr/reference/overview-built-in-presets/ | 200 | 所有官方 preset 名与必填 mixin；`rna-seq`（必填 `--species` + `--assemble-contigs-by`/`--assemble-longest-contigs`）；`exome-seq`；`10x-sc-xcr-vdj`、`10x-sc-5gex`（必填 `--species`）；试剂盒 preset 全表 |
| `mixcr align` | https://mixcr.com/mixcr/reference/mixcr-align/ | 200 | `--preset`、`-s/--species` 取值表、`-b/--library`、`-O`/`-M`、`--tag-pattern`、`--assemble-clonotypes-by`、`--split-clones-by`、报告参数、硬件建议 |
| `mixcr refineTagsAndSort` | https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/ | 200 | 全部命令行参数与默认行为；`--dont-correct`、`-p/--power`、`-s/--substitution-rate`、`-i/--indel-rate`、`-q/--min-quality`、`--max-substitutions/indels/errors`、`--memory-budget`（4Gb）、`--set-whitelist CELL=preset:737K-august-2016`、32Gb 内存警示 |
| `mixcr assemble` | https://mixcr.com/mixcr/reference/mixcr-assemble/ | 200 | 纠错五阶段说明；`-O` 核心参数默认值（`assemblingFeatures=CDR3`、`minimalClonalSequenceLength=12`、`badQualityThreshold=20`、`maxBadPointsPercent=0.7`、`qualityAggregationType=Max`、`minimalQuality=0`、`addReadsCountOnClustering=false`、`maximalPreClusteringRatio=1.0`、`separateByV/J/C=false`、`cloneClusteringParameters.*`）；`-P` 预克隆参数 |
| `mixcr export` | https://mixcr.com/mixcr/reference/mixcr-export/ | 200 | `mixcr exportClones` 全参数；默认导出列名逐字（`cloneId … cloneFraction … nSeqCDR3 … targetQualities`）；`exportCloneGroups`/`exportAlignments` |
| `mixcr postanalysis` | https://mixcr.com/mixcr/reference/mixcr-postanalysis/ | 200 | 个体/重叠两类分析；**"downsampling is a required procedure"**；下采样三型 + weight 四型；**官方多样性指标名全表**；`--tables` 输出命名规则 |

未取用：`mixcr analyze`、`assembleContigs`、`exportAirr`、`qc` 等页面（本次未抓，需要时按同一站点路径补抓，不凭记忆写参数）。

### 1.2 TRUST4

| 页面 | URL | 状态 | 取到的可执行内容 |
|---|---|---|---|
| README（主文档） | https://github.com/liulab-dfci/TRUST4 | 200 | 安装三法；`run-trust4` 完整 `[OPTIONS]` 表（逐字）；`-f` 与 `--ref` 的区别；`BuildImgtAnnot.pl` / `BuildDatabaseFa.pl`；10x 典型命令；`--readFormat` 语法；SMART-seq wrapper；`annotator`；输出文件与字段 |
| 评测脚本仓 | https://github.com/liulab-dfci/TRUST4_manuscript_evaluation | 仅被引用，未抓 | 论文评测，不作为流程依据 |

## 2. MHC 结合预测与 HLA 分型

| 页面 | URL | 状态 | 取到的可执行内容 |
|---|---|---|---|
| NetMHCpan-4.1 | https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ | 200 | 输入类型 FASTA/PEPTIDE；字母表与 `X`；≤500 序列 / ≤20,000 aa / ≥8 aa / ≤20 等位；8–14mer 选择；等位名单 `MHC_allele_names.txt`；**strong 0.5% / weak 2% 默认**；`-99` 打印全部；输出列 14 项；"%Rank rather than Score" 官方建议；standalone 仅给下载入口 |
| NetMHCIIpan-4.3 | https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/ | 200 | 输出列（含 `Core_Rel`、`Inverted`、`%Rank_BA`、`Affinity(nM)`）；**strong 默认 1% / weak 默认 5%**；DP/DQ/DR 三 locus 覆盖说明 |
| OptiType | https://github.com/FRED-2/OptiType | 200 | v1.5.0 全新 CLI（`optitype run`）；依赖 RazerS3 + GLPK/CBC/CPLEX；`check-deps`/`init-config`；`-b beta`、`-e enumerate`、`--solver`；输出 `*_result.tsv` 列名；Docker |
| arcasHLA | https://github.com/RabadanLab/arcasHLA | 200 | conda 安装；`reference --version/--update`；`extract`/`genotype`/`partial`/`merge`；`genotype` 全部默认值（`--min_count 75`、`--zygosity_threshold 0.15`、`--drop_threshold 0.1`、`--drop_iterations` 10/4）；population 取值表；输出 json 结构 |
| HLA*LA | https://github.com/DiltheyLab/HLA-LA | 200 | `HLA-LA.pl --BAM --graph --sampleID --maxThreads`；`--action prepareGraph`；`--samtools_T`（CRAM）；`--longReads ont2d/pacbio`；`R1_bestguess_G.txt` 列定义；G 组分辨率说明 |

**未提供**：NetMHCpan / NetMHCIIpan 的 standalone CLI 参数表。DTU 公开页只给下载入口（学术）/邮箱（商业），CLI README 在包内。→ 按规则只写流程与判据。

## 3. 免疫浸润解卷积

| 页面 | URL | 状态 | 取到的可执行内容 |
|---|---|---|---|
| CIBERSORTx 首页 | https://cibersortx.stanford.edu/ | 200（登录门） | 工具定位、EcoTyper 关系、Non-Commercial Terms；无任何命令 |
| CIBERSORTx About | https://cibersortx.stanford.edu/about.php | 200（内容被登录拦） | "You are currently not logged in. Please sign in to access content." |
| quanTIseq 文档 | https://icbi.i-med.ac.at/software/quantiseq/doc/ | 200 | 三步流程；`quanTIseq_pipeline.sh` 全参数与默认值；输入文件格式（无表头三列）；10 类细胞 + Other；`T.cells.CD4` 为非 Treg 的官方注；输出文件名；license BSD-3 |
| EPIC | https://github.com/GfellerLab/EPIC | 200 | `EPIC(bulk=, reference=, mRNA_cell=, sigGenes=, mRNA_cell_sub=)`；输入 TPM/RPKM；`mRNAProportions` vs `cellFractions` 的官方 FAQ；web app；学术免费/商业需授权 |
| ABIS（封装层） | https://omnideconv.org/immunedeconv/reference/deconvolute_abis.html | 由检索结果定位（未逐字抓正文） | 仅作为官方入口引用；具体命令未核验 → 只写判据 |

## 4. CyTOF / 流式

| 页面 | URL | 状态 | 取到的可执行内容 |
|---|---|---|---|
| CATALYST 包页 | https://bioconductor.org/packages/release/bioc/html/CATALYST.html | 200（解析到 3.23 / 1.36.0） | 能力定义（bead 归一化、去卷积、bead 补偿）；两个 vignette 标题；引用文献（含 "CyTOF workflow" F1000Research） |
| CATALYST 1. Preprocessing | https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html | 200 | `prepData`（cofactor 5、by_time、arcsinh）；`normCytof(beads="dvs"/"beta", median±5mad)`；`assignPrelim`/`estCutoffs`/`applyCutoffs`/`plotYields`；`computeSpillmat`/`compCytof(method="nnls")` 的完整调用 |
| CATALYST 2. Differential discovery | https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html | 200 | `cluster(sce, features="type", xdim, ydim, maxK, seed)` = FlowSOM + ConsensusClusterPlus；`runDR(dr="UMAP")`；`mergeClusters`；pbMDS/clrDR/plotExprHeatmap；diffcyt DA/DS |
| FlowSOM 包页 | https://bioconductor.org/packages/release/bioc/html/FlowSOM.html | 200 | 版本 2.20.0；`BiocManager::install("FlowSOM")`；vignette PDF/R 链接；被 CATALYST/diffcyt/MetaCyto 依赖 |

**cytofWorkflow**：没有独立的现行官方文档站；其官方载体是 CATALYST 包页引用的 Nowicka et al. 2019（F1000Research）与上述 differential vignette。不引用第三方 fork 的流程脚本。

## 5. 引用规范（写方法学时直接抄）

- MiXCR：preset 名 + MiXCR 版本 + 参考库（`default` 或 IMGT 版本）+ `assemblingFeatures` + 是否 `--split-clones-by`。
- TRUST4：`-f`/`--ref` 各自来源与版本 + `-k` + 是否 `--repseq` + 是否 UMI/barcode 级。
- NetMHCpan/NetMHCIIpan：版本 + 阈值（0.5/2 或 1/5）+ 等位清单来源（分型工具与版本）。
- quanTIseq：`--method`、`--tumor`、`--rmgenes`、`--mRNAscale` 四项取值必须写明。
- EPIC：报的是 `cellFractions` 还是 `mRNAProportions`。
- CATALYST：`beads` 类型、`cofactor`、`method="nnls"`、`xdim×ydim`、`maxK`。
