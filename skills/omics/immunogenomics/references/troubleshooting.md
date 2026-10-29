# 排查手册（症状 → 原因 → 按官方文档的处理）

原则：先分清是**工具报错**、**参考/版本错配**，还是**判据误用**。三类里只有第一类靠改命令解决；第二类靠锁定版本；第三类是分析逻辑错，改命令没用。

---

## 一、免疫组库（MiXCR / TRUST4）

### 1. `mixcr refineTagsAndSort` 跑到 OOM / 被 OOM killer 杀掉
- 原因（官方）：barcode 纠错的内存与**唯一 barcode 数**成正比，"in the extreme case of millions of unique barcodes MiXCR may require up to 32Gb of RAM"。
- 处理：先加 `--memory-budget`（默认 4Gb）到机器可用内存的合理值；若 barcode 空间本就巨大（10x 全转录组），官方给的另一条路是 `--dont-correct`（只排序，不纠错），此时无该内存需求。
- 来源：https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/

### 2. `mixcr align` 比对率极低（报告里 aligned 比例个位数）
- 先查三件事，顺序不能反：
  1. **preset 是否与建库方案匹配**（官方原文："It is critical to carefully select the most appropriate preset for the data you analyse"）；
  2. `--species` 是否为本物种（`hsa`/`mmu`/…）；
  3. 若为自建/无名试剂盒，是否漏了 `generic-amplicon` 的必填 mixin（Species、Material type、左右比对边界）。
- 常见误配：把 5'RACE 数据套 `10x-sc-xcr-vdj`；把 DNA 多重 PCR 套 RNA preset（C 区基因特征不同）。
- 来源：https://mixcr.com/mixcr/reference/mixcr-align/ ；https://mixcr.com/mixcr/reference/overview-presets/

### 3. `mixcr assemble` 报 "assemblingFeatures must cover CDR3"
- 原因（官方）：`assemblingFeatures` 必须覆盖 CDR3。
- 处理：改用覆盖 CDR3 的定义，如 `FR3+CDR3`，或官方给的 disjoint 写法 `-OassemblingFeatures="[V5UTR+L1+L2+FR1,FR3+CDR3]"`。
- 来源：https://mixcr.com/mixcr/reference/mixcr-assemble/

### 4. 克隆型数量爆炸、多样性高得离谱
- 原因：纠错链被跳过或被关掉。可能是：手工分步时漏了 `refineTagsAndSort`；或者加了 `--dont-correct`；或者 `assemble` 的聚类参数被 `-O` 覆盖成 `oneMismatch` 之类更严格的匹配。
- 处理：确认分步顺序为 align → refineTagsAndSort →（assemblePartial）→ assemble；确认 `-OcloneClusteringParameters.searchParameters` 仍是 `twoMismatchesOrIndels`（默认），`backgroundSubstitutionRate=0.002`、`backgroundIndelRate=0.0002` 未被改写。
- 来源：https://mixcr.com/mixcr/reference/mixcr-assemble/ ；https://mixcr.com/mixcr/reference/mixcr-refineTagsAndSort/

### 5. `mixcr postanalysis` 报不同样本不可比 / 直接拒绝
- 原因（官方）："Downsampling is a required procedure without which it is not possible to make a statistical comparisons between datasets"。样本测序深度差异大时，`auto` 会用 Q20 规则把最小的样本剔掉（`--drop-outliers`）。
- 处理：显式给 `--default-downsampling count-read-min`（或 `top-read-N` / `cumtop-read-P`），并显式给 `--default-weight-function`（`read`/`umi`/`cell`）。若样本读数差一个数量级，接受丢样本，别硬凑。
- 来源：https://mixcr.com/mixcr/reference/mixcr-postanalysis/

### 6. TRUST4 报找不到基因 / 组装出空结果
- 原因：`-f` 与 `--ref` 混用。官方明确：BAM 输入时 `-f` 必须是**含基因组坐标**的 `bcrtcr.fa`（由 `BuildDatabaseFa.pl` 用 reference.fa + GTF 生成）；FASTQ 输入才可直接用 IMGT 的 `IMGT+C.fa` 作 `-f`。
- 处理：按输入类型重建 `-f`；`--ref` 始终给 IMGT 注释文件。
- 来源：https://github.com/liulab-dfci/TRUST4 （Practical notes / Example）

### 7. TRUST4 结果里 CDR3 一半是补齐的
- 判据（官方）：`trust_cdr3.out` 的 `CDR3_score` 已除以 100，`1.00` 为最高，**`0.01` 表示 imputed CDR3**；`trust_annot.fa` 里 CDR3 的 `score 0.00` 表示 partial CDR3、`1.00` 表示补齐。
- 处理：做多样性/克隆型统计前按 `CDR3_score` 与 `complete_vdj_assembly` 过滤；需要对给定序列做纯注释时用 `annotator --noImpute`。
- 来源：https://github.com/liulab-dfci/TRUST4 （Input/Output、Annotation only）

### 8. 10x 数据 TRUST4 报 barcode 全为 0 / 细胞数异常少
- 原因：`--readFormat` 与试剂盒不匹配，或漏 `--barcodeWhitelist`。
- 处理：官方给的典型组合是 `--readFormat bc:0:15` + CellRanger 的 `737K-august-2016.txt` 白名单；「The exact options depend on your 10X Genomics kit」——换试剂盒就要换 format/白名单，不存在通用值。
- 来源：https://github.com/liulab-dfci/TRUST4 （10X 一节）

---

## 二、MHC 结合预测与 HLA 分型

### 1. NetMHCpan 提交被拒：等位名无效
- 原因：等位写法必须是官方名单里的形式（如 `HLA-A*02:01` / `HLA-A02:01`），且**单次 ≤20 个等位**。
- 处理：从官方 `MHC_allele_names.txt` / `allele.list` 取名字，逐个核对分型结果（arcasHLA 输出是 6 位如 `A*01:01:01`，提交前按名单裁剪成可识别的等位）。
- 来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/

### 2. 同一批肽，换一次提交阈值就"多出一堆强结合"
- 原因：把 `Score`/IC50 当判据，或改了 strong/weak 阈值却没记录。
- 处理（官方判据）：strong = `%Rank<0.5`，weak = `%Rank<2`（class I 默认）；class II 默认 1% / 5%。官方明确"advise to select candidate binders based on %Rank rather than Score"。方法学必须写清用的是哪一档。
- 来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ （Output format）；https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/

### 3. class II 预测结果里 `Inverted = 1` 很多
- 说明（官方）：肽反向结合（集合多数投票决定）。默认只有 HLA-DP 会预测反向；这是 4.3 的正常输出，不是错误。若下游按"正向 core 位置"取突变位点，必须处理 `Inverted`。
- 来源：https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/ （DESCRIPTION）

### 4. OptiType 报缺依赖 / ILP 求解失败
- 原因：`RazerS3` 与 ILP solver 是外部依赖，不能靠 pip 装。
- 处理：`conda install -c bioconda razers3` + GLPK/CBC/CPLEX 之一；先 `optitype check-deps`；用 `optitype init-config -o config.ini` 生成配置后填 `[ilp] solver=` 与 `[mapping] threads=`。
- 来源：https://github.com/FRED-2/OptiType

### 5. OptiType 老教程命令全部失效
- 原因：1.5 起 CLI 重构。官方 Migration 说明：`python OptiTypePipeline.py` → `optitype run`；多文件改为 `-i f1 -i f2`（不再 `-i f1 f2`）；数据随包分发无需设路径。
- 来源：https://github.com/FRED-2/OptiType （Migration from v1.x）

### 6. arcasHLA 分型结果与上次不一致
- 原因：IMGT/HLA 参考版本变了（`reference --update`）。
- 处理：复现旧结果必须锁版本，如 `./arcasHLA reference --version 3.24.0`；重跑前重跑 `genotype`（可用已有的 `sample.alignment.p` 不重新比对）。
- 来源：https://github.com/RabadanLab/arcasHLA

### 7. arcasHLA 只报一对等位（疑似纯合）
- 判据：`--zygosity_threshold` 默认 0.15（次/主等位非共享计数比），`--min_count` 默认 75。低深度样本会被判纯合 → **别直接当纯合下结论**，先看 `--min_count` 是否被 reads 数卡住，必要时用 `partial` 再跑一次看是否有 partial 等位。
- 来源：https://github.com/RabadanLab/arcasHLA

### 8. HLA*LA 报 `cannot find a compatible entry in its internal database`
- 原因：BAM/CRAM 的参考基因组版本不在 HLA*LA 内部数据库里（官方支持多种 B37 与 1000G GRCh38）。
- 处理：换到受支持的参考重比对，或按官方说明提交需求（"adding more references is easy"）。
- 来源：https://github.com/DiltheyLab/HLA-LA

### 9. HLA*LA 对 CRAM 报 `Unable to fetch reference #5 ...`
- 处理：加 `--samtools_T <GRCh38_full_analysis_set_plus_decoy_hla.fa>`；并且 CRAM 必须含未比对 reads（HLA reads 常富集在那里）。
- 来源：https://github.com/DiltheyLab/HLA-LA （News 2019-06-10 / CRAM files 一节）

### 10. 新抗原候选表有几百条，无法验证
- 原因：缺 wild-type 对照、缺表达过滤、HLA 分型只覆盖一个等位。
- 处理：按 2.3 的判据重跑——class I 用 6 个等位全提交（≤20/次），class II 8 个等位；同批跑 mutant 与 wild-type；加肿瘤表达过滤；**明确写"新抗原预测无统一金标准"，候选必须人工核查**（等位一致性、转录本版本、自肽风险）。
- 来源：https://services.healthtech.dtu.dk/services/NetMHCpan-4.1/ ；https://services.healthtech.dtu.dk/services/NetMHCIIpan-4.3/

---

## 三、免疫浸润解卷积

### 1. CIBERSORTx 什么都看不到 / 没有命令可用
- 现状（官方公开页）：站点只有 Home/About/Contact/Register 与登录框；`about.php` 返回 "You are currently not logged in. Please sign in to access content."
- 处理：走 `register.php` 注册登录后按官方页面执行；**本技能不提供任何 CIBERSORTx 命令或参数**，方法学里只写登录后官方页面确认过的设置。
- 来源：https://cibersortx.stanford.edu/ ；https://cibersortx.stanford.edu/about.php

### 2. quanTIseq 报输入格式错误
- 原因（官方硬要求）：输入是 **tab 分隔、无表头、每行三列**（样本 ID / FASTQ1 / FASTQ2），单端第三列必须写 `None`；用 `--pipelinestart=decon` 时输入换成 TPM 矩阵（首列基因 symbol，首行样本 ID，**非 log 尺度**）。
- 来源：https://icbi.i-med.ac.at/software/quantiseq/doc/

### 3. quanTIseq 输出里没有 `Other` 列
- 原因：`--method` 不是 `lsei`。官方："The fraction of uncharacterized cells ('other') is computed only by the 'lsei' method"。
- 处理：用默认 `--method=lsei`。
- 来源：https://icbi.i-med.ac.at/software/quantiseq/doc/ （Options）

### 4. 肿瘤样本免疫比例整体偏高/偏低
- 原因：`--tumor` 未开。官方："We highly recommend setting --tumor=TRUE when analyzing tumor data"（会剔除肿瘤高表达 signature 基因）。
- 配套检查：`--rmgenes` 对 RNA-seq 用 `default`、对芯片用 `none`；`--mRNAscale` 保持 TRUE（官方强烈建议）。
- 来源：https://icbi.i-med.ac.at/software/quantiseq/doc/

### 5. 同一批样本两次运行数值不完全一致
- 原因（官方）：kallisto 结果会随 `--threads` 轻微变化。
- 处理：固定 `--threads`，并在方法学里记录。
- 来源：https://icbi.i-med.ac.at/software/quantiseq/doc/

### 6. EPIC 报 `attempt to set 'colnames' on an object with less than two dimensions`
- 原因（官方 FAQ）：`bulk`（或自定义 reference）被传成了 vector 而不是 matrix。
- 处理：`as.matrix()` 后重跑。
- 来源：https://github.com/GfellerLab/EPIC （FAQ）

### 7. EPIC 的细胞比例与"真实比例"差很多（做 benchmark 时）
- 判据（官方 FAQ）：若 bulk 是从 scRNA-seq 重建的 in-silico 样本，真实比例应对比 `mRNAProportions`；真实 bulk（如 FACS 测的比例）才对比 `cellFractions`。用错一列会系统性偏差。
- 来源：https://github.com/GfellerLab/EPIC （FAQ）

### 8. 三个工具（CIBERSORTx / quanTIseq / EPIC）给出的 T 细胞比例互相打架
- 原因：signature matrix、归一化、是否按 mRNA 含量缩放、是否剔肿瘤高表达基因全都不同。这是**方法差异**，不是 bug。
- 处理：一篇论文内只用一种主方法 + 一种做敏感性分析；图里禁止把不同工具绝对值放同一坐标轴比较；报告写"相对比例"。
- 来源：见第三部分各工具官方页

---

## 四、CyTOF / 流式（CATALYST / FlowSOM）

### 1. `normCytof` 报找不到 bead 通道 / 归一化后曲线仍然漂
- 原因：`beads` 类型与实验用的 bead 不符。
- 处理：`"dvs"` = 140/151/153/165/175；`"beta"` = 139/141/159/169/175；其他 bead 给自定义质量数向量。修剪范围用 `trim` 调（默认 median±5mad）。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html

### 2. 去条码后细胞数掉一半
- 原因：`estCutoffs` 的分离阈值过严，或 barcode 方案（如 6-choose-3）与实际标记不符。
- 处理：`plotYields` 看每个 barcode 的得率曲线选阈值，再 `applyCutoffs`；确认 `bc_key` 与实际通道一致。`bc_id == 0` 是未分配事件，需显式剔除而不是当样本。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html

### 3. `computeSpillmat` 报缺单染样本 / 矩阵对角线 ≠ 1
- 原因：单抗体染色对照（`ss_exp`）缺失或不完整；未去条码就做补偿。
- 处理：官方流程是先 `assignPrelim` → `estCutoffs` → `applyCutoffs` 再做 `computeSpillmat`；官方 sanity check 是 `all(diag(sm)==1)` 与 `all(sm>=0 & sm<=1)`。通道无单染对照会在 `plotSpillmat` 里标灰。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html

### 4. 补偿后出现明显负值 / 双轴图仍是斜的
- 处理：`compCytof(..., method="nnls")`；用 `overwrite=FALSE` 保留未补偿数据，逐通道对比 `exprs` vs `compexprs` 直到满意（官方即如此迭代）。
- 来源：同上

### 5. `cluster()` 出来的群无法解释
- 原因（官方机制）：`features="type"` 决定参与聚类的 marker；state marker 混进聚类会让群按激活状态而非细胞类型划分。
- 处理：先在 `rowData$marker_class` 里把 marker 正确标为 `type`/`state`，`cluster(features="type")`；元聚类数用 `maxK` 控制，必要时 `mergeClusters` 手工合并，并用 Delta area plot 定 K。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html

### 6. UMAP 每次跑都不一样
- 处理：`runDR` 前 `set.seed()`（官方示例 `set.seed(1601)`），或给 `cluster(seed=1)`；`cells=` 控制下采样细胞数（官方示例 500）。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html

### 7. 跨批次差异盖过生物学差异
- 判据：先看 `plotCounts`（每样本细胞数）与 `pbMDS`（pseudobulk MDS）；若样本按批次而非分组聚类，就是批次主导。
- 处理：检查每批的 bead 归一化因子、补偿矩阵、去条码阈值是否独立估计；CATALYST 的 `normCytof`/`compCytof` 默认不覆盖原始数据，便于回溯重做。**不要**用聚类后比例直接跨批次比。
- 来源：https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/preprocessing.html ；https://bioconductor.org/packages/3.23/bioc/vignettes/CATALYST/inst/doc/differential.html

### 8. 找不到 cytofWorkflow 的官方脚本
- 现状：`cytofWorkflow` 的现行官方载体是 CATALYST 的两个 vignette（包页 Citation 列 Nowicka et al. 2019 "CyTOF workflow: differential discovery…"）。不存在独立官方站点。
- 处理：按 CATALYST preprocessing + differential 两个 vignette 执行；不要拿第三方 fork 的 cytofWorkflow 脚本当官方流程。
- 来源：https://bioconductor.org/packages/release/bioc/html/CATALYST.html

---

## 五、需要停下来问人的情况

出现下列任一情况，说明**判据层面**出了问题，继续跑只会产生看似合理的错结果：

1. 同一批样本三种 HLA 分型方法给不出一致的 A/B/C。
2. 免疫组库下采样后样本量掉到个位数（无法做组间统计）。
3. 新抗原候选中 wild-type 与 mutant 的 `%Rank_EL` 差异 < 0.1（区分度不足）。
4. 解卷积结果与病理/流式的事实（如 FACS 说 40% CD8，解卷积说 5%）差一个量级。
5. CyTOF 批次效应与分组完全共线（无法分离）。
