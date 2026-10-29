---
name: lipidomics-annotation
description: |
  Lipidomics annotation and lipid-specific analysis. Covers LIPID MAPS classification and
  shorthand notation (species vs molecular species vs sn-position vs double-bond position),
  MS1 m/z + adduct matching ([M+H]+, [M+Na]+, [M-H]-, [M+HCOO]-), RT/CCS-assisted and
  MS2 fragment matching, annotation confidence levels, the official lipidr Bioconductor
  workflow (read_skyline / as_lipidomics_experiment -> add_sample_annotation ->
  summarize_transitions -> normalize_pqn -> mva -> de_analysis -> lsea ->
  plot_class_enrichment / plot_chain_distribution / plot_trend), why class-aware
  normalization differs from global normalization, LIPID MAPS LMSD REST + SwissLipids
  SPARQL + MS-DIAL / LipidFinder official tooling, and PubChem / ChEMBL entity cross-checks
  through the bundled MCP chemistry tools.
  中文触发词：脂质组、lipidomics、脂质注释、LIPID MAPS、lipidr、PC/PE/TG、碳链双键、脂质异构体
category: omics
tags: lipidomics, lipid-annotation, lipid-maps, lipidr
---

# 脂质组学注释与脂质专用分析

本技能只做两件事：**把 m/z 特征变成有命名、有置信级的脂质**，以及**按脂质特有的层级（类别 / 碳链 / 双键）做差异与趋势分析**。

QC 过滤、缺失填补、PQN/漂移校正的一般原则、PCA/PLS-DA/OPLS-DA 的置换检验要求、单变量检验选择、mummichog 通路富集——这些**不在本技能重复**，走同目录 `metabolomics-profiling` 技能。本技能只补充脂质特有的部分，并在需要时交叉引用它。

## 什么时候用 / 不用

| 输入 | 用本技能 | 说明 |
|---|---|---|
| Skyline 导出的 CSV（靶向脂质组） | ✅ 主路径 | `lipidr` 的原生输入格式 |
| 已注释的脂质矩阵（`Molecule` 列含 `PC 34:1`、`Cer d18:1/C16:0` 等） | ✅ | 用 `as_lipidomics_experiment()` 进入同一流程 |
| 只有 m/z + RT + 强度的峰表，未注释 | ✅ 前半段（注释）+ 后半段（注释后分析） | 注释阶段见第 3 节 |
| 代谢组（非脂质为主）峰表 | ❌ | 用 `metabolomics-profiling` |
| 原始谱图去卷积、峰检测参数调优 | ⚠️ 用 MS-DIAL 官方流程 | 见第 6 节；本技能只给官方入口与参数出处 |
| 脂质-基因/酶通路网络 | ⚠️ 交叉引用 | `pathway-enrichment` |

## 1. 命名体系：先把"你测到的是哪一层的脂质"钉死

这是脂质组最容易出错的地方：**同一个 m/z 可以对应几十个同分异构脂质**，命名写细了就是过度注释，写粗了就丢掉生物学信息。

### 1.1 LIPID MAPS 八类别

LIPID MAPS® 脂质分类系统由**八个类别**构成，每类有自己的亚类层级：

| 缩写 | 英文 | 中文 |
|---|---|---|
| FA | Fatty acyls | 脂肪酸酰类 |
| GL | Glycerolipids | 甘油脂类 |
| GP | Glycerophospholipids | 甘油磷脂类 |
| SP | Sphingolipids | 鞘脂类 |
| ST | Sterol lipids | 甾醇脂类 |
| PR | Prenol lipids | 异戊烯醇脂类 |
| SL | Saccharolipids | 糖脂类 |
| PK | Polyketides | 聚酮类 |

来源：<https://www.lipidmaps.org/resources/education/classification>（原文："The LIPID MAPS® Lipid Classification System is comprised of eight lipid categories, each with its own subclassification hierarchy."）

各类别定义、亚类（如 `GP01` 磷脂酰胆碱、`GP02` 磷脂酰乙醇胺、`GP03` 磷脂酰丝氨酸、`GP04` 磷脂酰甘油、`GP06` 磷脂酰肌醇、`GP10` 磷脂酸、`GP12` 心磷脂）与 `FA01/FA07/FA08` 等编号，见 `references/nomenclature.md`。

### 1.2 结构信息层级（决定你能写到多细）

官方给出**八级**层级，从低到高（原文逐字）：

| 级别 | 官方表述 | 例子 | `/` 与 `_` 的含义 |
|---|---|---|---|
| Species level | "Sum composition, i.e., sum of carbon atoms, DBE and number of additional oxygen atoms" | `FA 18:1;O` | 碳链总和 |
| Molecular species level | "Lipid species with identified fatty acyl/alkyl residues" | `TG 16:0_18:1_18:1` | **下划线 `_`**：链组成已知，**位置未知** |
| *sn*-Position level | "Fatty acyl/alkyl constituents at the glycerol backbone are indicated by a slash" | `TG 16:0/18:1/18:1` | **斜杠 `/`**：sn 位置已知 |
| DB/DBE-position level | "Defined position of double bond(s)/double bond equivalent(s)" | `FA 18:2(9,12);O` | 双键位置已知 |
| Phosphate-position level | "Positions of phosphate group(s)" | `PIP[3']`、`PIP2[4',5']` | 磷酸基位置 |
| Structure defined level | 含官能团（三键 `Y`） | `FA 18:2;OH`、`FA 18:0;Y` | |
| Full structure level | 官能团 + 位置 | `FA 18:2(9Z,11E);13OH` | |
| Complete structure level | 位置 + 立体化学（同 LMSD 俗名） | `FA 18:2(9Z,11E);13OH[S]` = 13S-HODE | |

来源：<https://www.lipidmaps.org/lipid_nomenclature/rules/hierarchy>

**这就是 `PC(32:0)` 与 `PC(16:0/16:0)` 的区别。** `PC 32:0` 是 species level（只知道总碳数 32、总双键 0）；`PC 16:0/16:0` 是 *sn*-position level（两条链分别是 16:0，且 sn-1/sn-2 位置确定）。二者**质量数完全相同**，只有 MS2 或色谱/CCS 才能区分——所以写 `PC(32:0)` 的分析里不可能出现"sn-1 位特异性"这类结论。

### 1.3 官方速记规则（逐字要点）

来源：<https://www.lipidmaps.org/lipid_nomenclature>

- 甘油磷脂写成 `Headgroup(sn1/sn2)`，例：`PC(16:0/18:1(9Z))`；"By default, R stereochemistry at the C2 carbon of glycerol and attachment of the headgroup at the _sn3_ position."
- 甘油酯写成 `Headgroup(sn1/sn2/sn3)`，例：`TG(16:0/18:1(9Z)/16:0)`。
- 烷基醚键用 **`O-`** 前缀，例 `DG(O-16:0/18:1(9Z)/0:0)`；(1Z)-烯基醚（缩醛磷脂）用 **`P-`** 前缀，例 `DG(P-14:0/18:1(9Z)/0:0)`。
- 只知总组成时：`TG(52:1)`、`DG(34:2)`，"where the numbers within parentheses refer to the total number of carbons and double bonds of all the chains"。
- 鞘脂速记里的 **`d`** = 1,3-二羟基长链碱，**`t`** = 1,3,4-三羟基长链碱。
- 系统命名用 E/Z（不用 trans/cis）、R/S（不用 α/β、D/L），例外是甘油 `sn`、甾醇母核、糖端基碳。"lyso" 不进系统名，只作为同义词。

### 1.4 命名的三套"方言"及其互换

| 体系 | 形态 | 入口 |
|---|---|---|
| LIPID MAPS shorthand / LMSD 俗名 | `PC 16:0/18:1(9Z)`、`LMGP01010005` | LMSD 与 REST（第 6.1 节） |
| RefMet 标准化名 | 由 LIPID MAPS 官方工具把各式名字归一 | <https://www.lipidmaps.org/resources/tools/lipid_std_form>；带加合物的 m/z 版本：<https://www.lipidmaps.org/resources/tools/lipid_std_mz_form> |
| SwissLipids 标识 | `SWISSLIPID:000056420` + 层级（类别 → species → isomeric subspecies） | <https://www.swisslipids.org/>；SPARQL（第 6.2 节） |
| lipidr 内部名 | `PE 32:0`、`PG 16:0/18:1`、`Cer d18:1/C16:0`、`PC(P-40:3)` | `annotate_lipids()` 解析（第 4 节） |

官方明确推荐：标准化到 LIPID MAPS 命名是"an essential prerequisite for the ability to compare and contrast data across different experiments and studies"（<https://www.lipidmaps.org/resources/tools/nomenclature>）。**跨研究比较前必须先标准化**，否则 `PC(34:1)` / `PC 34:1` / `PC(16:0/18:1)` / `PC 18:1_16:0` 会被当成四个东西。

### 1.5 异构体分辨力：写进结论前必须自查

| 信息 | 拿到它的手段 | 官方依据 |
|---|---|---|
| 类别（PC vs PE） | 头基特征离子（如 PC 的 `m/z 184.07`） | MS-DIAL 置信码 `x20` = "Lipid class"（<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>） |
| 碳链组成（16:0_18:1） | MS2 酰基片段离子 | 置信码 `x10` = "Lipid acyl chain" |
| sn 位置（16:0/18:1） | MS2 + 标准品/RT/CCS；LC-MS/MS 模式下官方注明 "'lipid acyl position resolved' is not officially supported yet" | 置信码 `x00` = "Lipid acyl position"；MS-DIAL 明确 LC-MS/MS 未官方支持 |
| 双键位置（18:1(9Z)） | 需要 Paternò–Büchi / OzID / EAD 等专用裂解，常规 CID 做不到 | LIPID MAPS 层级把 DB-position 单列为一级 |

**判据**：如果你的方法只有 CID-MS2 且无标准品，能诚实写到 *molecular species*（`_`）或 acyl chain 级别；写 `/`（sn 已知）或 `(9Z)`（双键位置已知）必须有对应的证据（标准品 RT、特征诊断离子、或专用裂解），否则就是过度注释。

## 2. 加合物与 m/z：注释的第一道门

### 2.1 官方加合物命名表（MS-DIAL）

| 缩写 | 含义 |
|---|---|
| `[M+H]+` | Proton adduct |
| `[M+Na]+` | Sodium adduct |
| `[M+NH4]+` | Ammonium adduct |
| `[M-H]-` | Proton loss |
| `[M+FA-H]-` = `[M+HCOO]-` | Formate adduct |
| `[M+Hac-H]-` = `[M+CH3COO]-` | Acetate adduct |

来源：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>（"Major adduct abbreviation / Meaning" 表）

### 2.2 各脂质类别的首选加合物（官方表，节选）

同一张表给出"ESI(+) form 1 / form 2 / ESI(-) form 1 / form 2"，**这是判断"该在哪一极找这个脂质"的官方依据**：

| 类别 | 缩写 | ESI(+) | ESI(-) |
|---|---|---|---|
| 磷脂酰胆碱 | PC | `[M+H]+`、`[M+Na]+` | `[M+CH3COO]-` |
| 溶血磷脂酰胆碱 | LPC | `[M+H]+`、`[M+Na]+` | `[M+CH3COO]-` |
| 磷脂酰乙醇胺 | PE | `[M+H]+`、`[M+Na]+` | `[M-H]-` |
| 磷脂酰肌醇 | PI | `[M+NH4]+`、`[M+Na]+` | `[M-H]-` |
| 磷脂酰甘油 | PG | `[M+NH4]+` | `[M-H]-` |
| 磷脂酰丝氨酸 | PS | `[M+H]+`、`[M+Na]+` | `[M-H]-` |
| 心磷脂 | CL | `[M+NH4]+` | `[M-H]-` |
| 三酰甘油 | TG | `[M+NH4]+`、`[M+Na]+` | — |
| 二酰甘油 | DG | `[M+NH4]+` | — |
| 神经酰胺 | Cer | 见原表（抓取时该段被截断） | 见原表 |
| 鞘磷脂 | SM | 见原表 | 见原表 |
| 游离脂肪酸 | FA | — | `[M-H]-` |
| 酰基肉碱 | CAR | `[M]+` | — |

完整表（含 `EtherPC`/`EtherPE`/`OxPC`/`OxPE`/`MGDG`/`DGDG`/`SQDG`/`CL`/`MLCL`/`GM3`/`GD1a` 等）以官方页为准：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>

### 2.3 m/z 检索（可直接执行的官方接口）

LIPID MAPS REST 的 MS 前体离子检索（"moverz"），官方给出的 URL 形态：

```
https://www.lipidmaps.org/rest/moverz/LIPIDS/{mz}/{ion}/{tolerance}/{format}
```

官方示例（逐字）：

```
https://www.lipidmaps.org/rest/moverz/LIPIDS/635.52/M+H/0.5/txt
https://www.lipidmaps.org/rest/moverz/LIPIDS/513.45/M-2H/0.2/txt
```

官方允许的 ion-type 取值（逐字）：

- Positive: `M+H`, `M+2H`, `M+3H`, `M+4H`, `M+NH4`, `M+Ag`, `M+Na`, `M+2Na`, `M+K`, `M+2K`, `M+Li`, `M+2Li`
- Negative: `M-H`, `M-CH3`, `M-2H`, `M-3H`, `M-4H`, `M.Cl`, `M.OAc`
- Neutral: `Neutral`

来源：<https://www.lipidmaps.org/resources/rest>

**注意**：moverz 检索的是 LIPID MAPS 虚拟库 / LMSD 的质量表，**只做 m/z 命中，不做 MS2 打分、不给置信级**。命中的候选必须继续走 2.4 与第 3 节的证据链。

## 3. 注释证据链与置信级

### 3.1 证据链（按证据强度递增）

1. **精确质量 + 加合物** → 得到候选分子式/脂质集合。质量容差要写明（ppm）。数量级参考：moverz 的 tolerance 参数即以此为单位，官方示例用 `0.5`、`0.2`（<https://www.lipidmaps.org/resources/rest>）。
2. **保留时间（RT）** → 排除同分异构中的不合理者。MS-DIAL 的官方口径："RT match should be equal to 0.5 min or less"（脂质组与代谢组项目均同）；GC-MS 项目为 "RT match should be equal to 0.1 min or less"，Kovats RI ≤ 20，Fiehn RI ≤ 2000。来源：<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>
3. **CCS（碰撞截面，离子淌度）** → 与 RT 正交的第三维。官方提供了 CCS 参考库入口：AllCCS <http://allccs.zhulab.cn/>、PNNL CCS database <https://metabolomics.pnnl.gov/ccs/>（链接见 <https://systemsomicslab.github.io/compms/msdial/main.html>）。RT 检索可借 Metabolomics Workbench 的 retention time 检索：<https://www.metabolomicsworkbench.org/data/search_rt_form.php>（同上页链接）。
4. **MS2 碎片匹配** → 决定能否从"类别"走到"酰基链"乃至"sn 位置"。谱库与 in-silico 谱：MS-DIAL 官方 MSTus/LipidBlast 资源（`MSDIAL-TandemMassSpectralAtlas-VS69-Pos.msp` 等，见 <https://systemsomicslab.github.io/compms/msdial/main.html>）；LIPID MAPS 的 in-silico 产物离子预测工具（GP 负离子模式 `/tools/structuredrawing/GP_p_form.php`、GL 正离子模式 `/tools/structuredrawing/GL_p_form.php`，见 <https://www.lipidmaps.org/resources/tools/ms>）。
5. **标准品** → 唯一能到 MSI Level 1 的路径。

### 3.2 置信级：MSI 四级 与 MS-DIAL 脂质专用编码的对应

MSI（Metabolomics Standards Initiative, Chemical Analysis Working Group）的最低报告标准见 Sumner et al., *Metabolomics* 2007, 3(3):211–221，doi:10.1007/s11306-007-0082-2（全文 <https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/>，其中 §2.9 为 metabolite identification）。四级体系为业界通用口径：Level 1 标准品确证（RT + MS/MS 或标准品一致）、Level 2 谱库/文献匹配的暂定注释、Level 3 暂定类别/骨架、Level 4 未知特征。

**操作层面**用 MS-DIAL 的脂质专用编码更可核查。三位码的百位表示"证据强度"，十位表示"解析到的结构层级"（逐字表）：

| Code | RT | CCS | m/z | MS/MS | Resolved method |
|---|---|---|---|---|---|
| 100 | ✅ | ✅ | ✅ | ✅ | Lipid acyl position |
| 110 | ✅ | ✅ | ✅ | ✅ | Lipid acyl chain |
| 120 | ✅ | ✅ | ✅ | ✅ | Lipid class |
| 200 | — | ✅ | ✅ | ✅ | Lipid acyl position |
| 210 / 220 | — | ✅ | ✅ | ✅ | acyl chain / class |
| 300 | ✅ | — | ✅ | ✅ | Lipid acyl position |
| 310 / 320 | ✅ | — | ✅ | ✅ | acyl chain / class |
| 400 | — | — | ✅ | ✅ | Lipid acyl position |
| 410 / 420 | — | — | ✅ | ✅ | acyl chain / class |
| 500 | ✅ | ✅ | ✅ | — | — |
| 510 / 520 | ✅ | ✅ | ✅ | — | — |
| 530 | ✅ | — | ✅ | — | — |
| 999 | Unknown | | | | |

同一页注明：LC-MS/MS 模式下 "'lipid acyl position resolved' is not officially supported yet"；GC-MS 项目的码段为 `340` / `440` / `999`。

来源：<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>

**报告判据**：每条注释必须写清「码值 + 该码前提（RT 是否匹配、CCS 是否匹配、MS2 是否匹配）」，不要只写 "identified"。

## 4. lipidr 官方工作流（Bioconductor vignette 顺序）

> **重要更正（必须读）**：`dim_analysis`、`liplevel_de`、`chain_de` **不存在于 lipidr 官方参考索引**。官方函数名为：多变量 `mva`/`plot_mva`；类别层面 `lsea` + `plot_class_enrichment` + `plot_enrichment(annotation="class")`；碳链/双键层面 `plot_chain_distribution` + `plot_trend` + `plot_enrichment(annotation="length"/"unsat")`。完整函数清单见 <https://www.lipidr.org/reference/index.html>。下文全部使用官方名。

版本环境：lipidr 官方参考站当前标注 `2.15.1`（<https://www.lipidr.org/reference/index.html>）。安装（官方 vignette 逐字）：

```r
if (!requireNamespace("BiocManager", quietly=TRUE))
    install.packages("BiocManager")
BiocManager::install("lipidr")
```

来源（vignette 源文）：<https://raw.githubusercontent.com/ahmohamed/lipidr/f5fb8d5421b8341e76f66f545154bae01e0aa62d/vignettes/workflow.Rmd>；Bioconductor 镜像渲染版：<https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.19/bioc/vignettes/lipidr/inst/doc/workflow.html>

> 注：`https://bioconductor.org/packages/release/bioc/vignettes/lipidr/inst/doc/lipidr.html` 返回 **404**；脂质 vignette 的实际文件名是 `workflow.html`。

### 4.1 读入：`read_skyline` 或 `as_lipidomics_experiment`

Skyline 侧要求（官方）：「Integrated peaks should be exported from each Skyline file through File => Export => Report. Selecting `Transition Results` ensures that necessary information is exported from Skyline.」且「`Replicates` should either be exported, or the `Pivot Replicate Name` option must be used.」

```r
datadir = system.file("extdata", package="lipidr")
filelist = list.files(datadir, "data.csv", full.names = TRUE) # all csv files
d = read_skyline(filelist)
```

签名：`read_skyline(files)`，`files` = "Character vector with filepaths to Skyline exported files in CSV format."
来源：<https://www.lipidr.org/reference/read_skyline.html>

非 Skyline 来源（已有矩阵）用：

```r
as_lipidomics_experiment(df, logged = FALSE, normalized = FALSE)
```

签名与要求（官方）："A data.frame or matrix where rows are lipids and columns are samples. Lipid names should be provided in the first column or in rownames of `df`. Measurements should be numeric. The data is considered `summarized` unless at least one lipid is duplicated (has > 1 row)."
来源：<https://www.lipidr.org/reference/as_lipidomics_experiment.html>

### 4.2 样本注释：`add_sample_annotation`

```r
clinical_file = system.file("extdata", "clin.csv", package="lipidr")
d = add_sample_annotation(d, clinical_file)
colData(d)
```

签名：`add_sample_annotation(data, annot_file)`；`annot_file` = "CSV file or a data.frame with at least 2 columns, sample names & group(s)."
来源：<https://www.lipidr.org/reference/add_sample_annotation.html>

子集（官方 vignette 写法，行=脂质、列=样本）：`d[1:10, 1:10]`、`d[, d$group == "QC"]`、`d[rowData(d)$Class %in% c("Cer","PC","LPC"), ]`。

### 4.3 合并多重 transition：`summarize_transitions`

```r
d_summarized = summarize_transitions(d, method = "average")
```

签名：`summarize_transitions(data, method = c("max", "average"))`，默认 `max`。
来源：<https://www.lipidr.org/reference/summarize_transitions.html>

### 4.4 归一化：`normalize_pqn` / `normalize_itsd`

```r
d_normalized = normalize_pqn(d_summarized, measure = "Area", exclude = "blank", log = TRUE)
plot_sample_boxplot(d_normalized)
```

官方机制原文：「The PQN method determines a dilution factor for each sample by comparing the distribution of quotients between samples and a reference spectrum, followed by sample normalization using this dilution factor. The reference spectrum in this method is the average lipid abundance of all samples (excluding blanks).」
签名：`normalize_pqn(data, measure = "Area", exclude = "blank", log = TRUE)`；`exclude = "blank"` 表示自动识别并排除空白。
参考文献（函数页列出）：Dieterle F. et al. (2006) *Anal. Chem.* 78(13):4281-4290.
来源：<https://www.lipidr.org/reference/normalize_pqn.html>

内标归一化（按类别）：

```r
d_normalized_itsd = normalize_itsd(d_summarized, measure = "Area", exclude = "blank", log = TRUE)
```

官方机制原文：「Internal standard normalization corrects lipid class-specific variations between samples. Lipid classes are normalized using corresponding internal standard(s) of the same lipid class. If no corresponding internal standard is found the average of all measured internal standards is used instead.」
来源：vignette 同 4.1；函数页 <https://www.lipidr.org/reference/normalize_istd.html>

### 4.5 多变量：`mva` / `plot_mva` / `plot_mva_loadings` / `top_lipids`

```r
mvaresults = mva(d_normalized, measure="Area", method="PCA")
plot_mva(mvaresults, color_by="group", components = c(1,2))

mvaresults = mva(d_normalized, method = "OPLS-DA", group_col = "Diet", groups=c("HighFat", "Normal"))
plot_mva(mvaresults, color_by="group")
plot_mva_loadings(mvaresults, color_by="Class", top.n=10)
top_lipids(mvaresults, top.n=10)
```

签名：`mva(data, measure = "Area", method = c("PCA","PCoA","OPLS","OPLS-DA"), group_col = NULL, groups = NULL, ...)`；`plot_mva(mvaresults, components = c(1,2), color_by = NULL, ellipse = TRUE, hotelling = TRUE)`；`plot_mva_loadings(mvaresults, components = c(1,2), color_by = NULL, top.n = nrow(mvaresults$loadings))`；`top_lipids(mvaresults, top.n = 10)`。

官方行为：「Blank samples are automatically detected (using TIC) and excluded. Missing data are imputed using average lipid intensity across all samples.」OPLS 需数值型 y，OPLS-DA 需两组。
来源：<https://www.lipidr.org/reference/mva.html>

> **置换检验 / Q² 报告要求不在 lipidr 内**：官方 `mva` 页未提供置换检验接口。若需要 R²Y/Q²/置换 p，按 `metabolomics-profiling` 的验收要求另行实现并在 provenance 说明。**官方文档未提供可直接执行的置换检验命令。**

### 4.6 差异分析：`de_analysis` / `de_design` / `significant_molecules` / `plot_results_volcano`

```r
de_results = de_analysis(
  data=d_normalized,
  HighFat_water - NormalDiet_water,
  measure="Area"
)
head(de_results)
significant_molecules(de_results)
plot_results_volcano(de_results, show.labels = FALSE)
```

签名：`de_analysis(data, ..., measure = "Area", group_col = NULL)`；`de_design(data, design, ..., coef = NULL, measure = "Area")`；`significant_molecules(de.results, p.cutoff = 0.05, logFC.cutoff = 1)`；`plot_results_volcano(de.results, show.labels = TRUE)`。

官方前置条件：「LipidomicsExperiment object, should be normalized and log2 transformed.」对比式 "are passed to `limma::makeContrasts`"；`logFC.cutoff` 在"多组（ANOVA-style）比较"中被忽略；返回值为 limma 的 TopTable。
来源：<https://www.lipidr.org/reference/de_analysis.html>

复杂设计（官方两种写法，逐字）：

```r
# Using formula
de_design(
  data=d_normalized,
  design = ~ group, 
  coef="groupHighFat_water", 
  measure="Area")

# Using design matrix
design = model.matrix(~ group, data=colData(d_normalized))
de_design(
  data=d_normalized,
  design = design,
  coef="groupHighFat_water",
  measure="Area")
```

### 4.7 脂质类别层面的差异：`lsea`（= 请求中"liplevel_de"的官方对应物）

```r
enrich_results = lsea(de_results, rank.by = "logFC")
significant_lipidsets(enrich_results)
plot_class_enrichment(de_results, significant_lipidsets(enrich_results))
```

签名：`lsea(de.results, rank.by = c("logFC","P.Value","adj.P.Val"), min_size = 2, ...)`；`significant_lipidsets(enrich.results, p.cutoff = 0.05, size.cutoff = 2)`；`plot_class_enrichment(de.results, significant.sets, measure = "logFC")`；`plot_enrichment(de.results, significant.sets, annotation = c("class","length","unsat"), measure = "logFC")`。

官方机制：「`lipidr` automatically generates sets of lipids based on lipid class, chain length and saturation. Measured lipids are then ranked by their fold change, or p-value using results from differential analysis.」`...` 透传给 `fgsea::fgsea()`（例：`nperm = 1000`）。返回值为 `fgsea` 结果 data.frame，并带 `de.results` / `rank.by` / `sets` 三个属性。
来源：<https://www.lipidr.org/reference/lsea.html>

集合生成可单独调用：`gen_lipidsets(molecules, min_size = 2)`，返回形如 `$Class_PC`、`$total_cl_34`、`$total_cs_2` 的集合列表。
来源：<https://www.lipidr.org/reference/gen_lipidsets.html>

### 4.8 碳链 / 双键层面的差异（= 请求中"chain_de"的官方对应物）

```r
plot_chain_distribution(de_results)
plot_trend(de_results, "length")
```

- `plot_chain_distribution(de_results, contrast = NULL, measure = "logFC")`：官方描述 "Plot a chart of (log2) fold changes of lipids per class showing chain lengths and unsaturations. If multiple molecules with the same total chain length and unsaturation are present in the dataset, the `measure` is averaged, and the number of molecules is indicated on the plot." 来源：<https://www.lipidr.org/reference/plot_chain_distribution.html>
- `plot_trend(de_results, annotation = c("length","unsat"))`：官方描述 "Fit and plot a regression line of (log2) fold changes and total chain lengths or unsaturations. If multiple comparisons are included, one regression is plotted for each." 实际拟合用 loess（官方示例输出 `geom_smooth()` using method = 'loess'）。来源：<https://www.lipidr.org/reference/plot_trend.html>
- 分布视图：`plot_enrichment(de_results, sig_lipidsets, annotation="class")`、`annotation="length"`、`annotation="unsat"`（<https://www.lipidr.org/reference/lsea.html>）。

> **趋势的统计量**：`plot_trend` 只返回 ggplot 对象，**不返回斜率/置信区间/截距/p 值**。官方文档未提供可直接执行的趋势统计检验命令；若论文需要"碳链越长 logFC 越低"的统计断言，必须在 provenance 里说明用的是外部回归（并给出方法与参数），不可把图当检验。

### 4.9 命名解析与清洗（注释质量的关键函数）

```r
annotate_lipids(lipid_list)
```

官方要求输入 "follow the pattern 'class xx:x/yy:y' ... Alternatively ... 'class zz:z'"，返回列含 `Molecule`、`clean_name`、`ambig`、`not_matched`、`istd`、`class_stub`、`chain1..4`、`l_1..l_4`、`s_1..s_4`、`total_cl`、`total_cs`、`Class`（共 21 列）。`no_match = c("warn","remove","ignore")`。
来源：<https://www.lipidr.org/reference/annotate_lipids.html>

配套：`non_parsed_molecules()` 列出解析失败者、`remove_non_parsed_molecules()` 剔除、`update_molecule_names()` 改名、`filter_by_cv(data, cv.cutoff = 20, measure = "Area")` 按 CV 过滤（<https://www.lipidr.org/reference/filter_by_cv.html>）。参考索引：<https://www.lipidr.org/reference/index.html>

## 5. 脂质专用统计：为什么类别内归一化 ≠ 全局归一化

### 5.1 机制（有官方依据的部分）

- **全局归一化（PQN）**：以"所有样本的平均脂质丰度"为参考谱，估一个**样本级稀释因子**（官方原文见 4.4）。它修正的是**取样量/进样量/基质抑制造成的整体缩放**。
- **类别内归一化（内标）**：官方明确其目的是「corrects **lipid class-specific** variations between samples」，即同一类别用同类别的内标，找不到对应内标时退回"所有内标均值"（官方原文见 4.4）。

**推论（判据，非官方命令）**：若不同脂质类别的提取回收率/离子化效率系统性不同，全局因子吸收不了这种"类别偏移"，只能用类别内内标修正；反过来，类别内归一化**不可**替代全局归一化（它不修样本级总浓度差异）。实践中两者是串联关系而非互斥：先 `summarize_transitions` → 视设计用 `normalize_itsd`（有类别内标时）或 `normalize_pqn`（无内标时）→ `log = TRUE`。

> 「类别内 vs 全局归一化的定量对比评估」：**官方文档未提供可直接执行的命令**（lipidr 无 A/B 归一化对比函数，也无 QC-RSD 前后对比接口）。做法只能是用 `filter_by_cv()` / `plot_molecules(d_qc, "cv", measure="Area")` 在两种归一化后各看一遍 QC 的 CV 分布，并把这个判据写进报告。

### 5.2 QC 视图（官方函数）

```r
plot_samples(d, type = "tic", log = TRUE)
plot_molecules(d_qc, "sd", measure = "Retention.Time", log = FALSE)
plot_molecules(d_qc, "cv", measure = "Area")
plot_lipidclass(d, "boxplot")
```

其中 `d_qc = d[, d$group == "QC"]`。来源：vignette（4.1 链接）。这些是"看图判断"，官方未给自动化通过/失败阈值——阈值规则沿用 `metabolomics-profiling`（QC-RSD ≤ 30%，严格 20%）。

### 5.3 碳链长度与不饱和度趋势

三层递进，全部用官方函数：

1. **类别层面富集**：`lsea()` → `significant_lipidsets()` → `plot_class_enrichment()`（哪一类整体偏移）。
2. **链属性层面富集**：`plot_enrichment(..., annotation = "length"/"unsat")`（哪一段碳链长度 / 哪个不饱和度整体偏移）。
3. **逐分子趋势**：`plot_chain_distribution()`（类内每格 logFC + 同链属性分子计数）、`plot_trend()`（logFC ~ total_cl 或 total_cs 的 loess 线）。

解读时必须带上"该格有几个分子"——`plot_chain_distribution` 官方就在图上标注了这个数。一格只有 1–2 个分子的"趋势"不可当结论。

## 6. 数据库与工具（官方入口与参数出处）

### 6.1 LIPID MAPS LMSD / REST

- 数据库总览：<https://www.lipidmaps.org/databases/lmsd/overview>；分类树浏览：<https://www.lipidmaps.org/databases/lmsd/browse>；分类更新记录（2024-02-20）：<https://www.lipidmaps.org/databases/lmsd/classification_updates>
- REST 三段式：`https://www.lipidmaps.org/rest/{context}/{input item}/{input value}/{output item}/{output format}`
  - context：`compound` / `gene` / `protein`
  - compound 的 output item：`formula`、`exactmass`、`inchi_key`、`name`、`sys_name`、`smiles`、`lm_id`、`pubchem_cid`、`hmdb_id`、`kegg_id`、`chebi_id`、`metacyc_id`，或 `all`；`classification` 取分类层级
  - output format：默认 JSON；可选 `txt`、`download`（表格/molfile）
- 官方可直接执行的示例（逐字）：
  ```
  https://www.lipidmaps.org/rest/compound/lm_id/LMFA01010001/name
  https://www.lipidmaps.org/rest/compound/lm_id/LMFA01010001/all
  https://www.lipidmaps.org/rest/compound/pubchem_cid/985/smiles
  https://www.lipidmaps.org/rest/compound/inchi_key/IPCSVZSSVZVIGE-UHFFFAOYSA-N/sys_name
  https://www.lipidmaps.org/rest/compound/inchi_key/IPCSVZSSVZVIGE-UHFFFAOYSA-N/physchem
  https://www.lipidmaps.org/rest/compound/pubchem_cid/985/classification
  https://www.lipidmaps.org/rest/compound/abbrev/PC(16:0/20:4(5Z,8Z,11Z,14Z))/structure
  https://www.lipidmaps.org/rest/compound/abbrev/PA(38:0)/all/txt
  https://www.lipidmaps.org/rest/compound/abbrev_chains/PC(16:0_18:0)/all/txt
  https://www.lipidmaps.org/rest/compound/lm_id/LMGP/all/download
  https://www.lipidmaps.org/rest/compound/lm_id/LM/all/download
  ```
  来源：<https://www.lipidmaps.org/resources/rest>
  > 注意 `abbrev`（`PC(16:0/20:4(...))`，sn 已知）与 `abbrev_chains`（`PC(16:0_18:0)`，链组成已知、位置未知）是**两个不同接口**——正好对应第 1.2 节的两级层级。

- 在线工具（MS 方向）：
  - 精确质量/加合物计算：`/tools/structuredrawing/masscalc.php`
  - 同位素分布：`/tools/ms/iso2d_Ag.php`
  - 虚拟库 / LMSD 前体离子检索：<https://lipidmaps.org/bulk_search>
  - Kendrick mass defect：`/tools/ms/kendrick_form.php`
  - 氧化 GP 链组成检索：<https://lipidmaps.org/resources/tools/ms/gp-ox-search>
  - GP 负离子 MS2 产物离子预测：`/tools/structuredrawing/GP_p_form.php`
  - GL 正离子 MS2 产物离子预测：`/tools/structuredrawing/GL_p_form.php`
  - 糖鞘脂 in-silico MS/MS：`/tools/ms/SP_insilico_form.php`、`/tools/ms/SP_insilico_compare_form.php`
  
  来源：<https://www.lipidmaps.org/resources/tools/ms>

- 命名标准化：<https://www.lipidmaps.org/resources/tools/lipid_std_form>、<https://www.lipidmaps.org/resources/tools/lipid_std_mz_form>（官方说明这两者用 RefMet，见 <https://www.lipidmaps.org/resources/tools/nomenclature>）

- `LipidBlast` 相关：MS-DIAL 页面明确「MS-DIAL internally has the theoretical MS/MS spectra for lipid annotations. Below is the LipidBlast (fork) templates that MS-DIAL partially uses.」，模板下载见 <https://systemsomicslab.github.io/compms/msdial/main.html>（`LipidBlast DBs fork GlyceroLipids VS12.zip`、`SphingoLipids VS7.zip`、`LipidMsmsBinaryDB-VS68-*.lbm2`）。

### 6.2 SwissLipids

- 站点：<https://www.swisslipids.org/>（Browse 脂质类别 / 脂质 analytes、ID Mapping、Downloads、API 入口均在左侧导航）
- 官方 SPARQL 端点：**`https://sparql.swisslipids.org/sparql/`**
- 官方示例查询（SIB 维护，逐字，用途=拿 LIPID MAPS ID 反查 SwissLipids/ChEBI）：

```sparql
PREFIX lipidmaps: <https://www.lipidmaps.org/rdf/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>

SELECT ?lipidmaps ?slm ?slmName ?chebi
WHERE {
  #VALUES ?lipidmaps {lipidmaps:LMSP01020001 lipidmaps:LMST01010069 lipidmaps:LMST04030222}
  ?slm rdfs:label ?slmName . 
  ?slm oboInOwl:hasDbXref ?lipidmaps .
  FILTER regex(str(?lipidmaps), "lipidmaps") .
  ?slm owl:equivalentClass ?chebi .
}
ORDER BY ?lipidmaps ?slm ?chebi
```

来源：<https://sib-swiss.github.io/sparql-examples/examples/SwissLipids/14.html>；示例索引（含 HMDB↔SwissLipids、ChEBI↔SwissLipids、LipidX↔SwissLipids、按 sn1 脂肪酸组分筛脂质等 39 条）：<https://sib-swiss.github.io/sparql-examples/examples/SwissLipids/>

### 6.3 MS-DIAL（官方站）

> 候选文档 `http://prime.psc.riken.jp/compms/msdial/main.html` 当前不可达；MS-DIAL 现行官方站为 **<https://systemsomicslab.github.io/compms/msdial/main.html>**。

官方页面给出的关键事实（可用于写方法与判据）：

- 目标与能力：「MS-DIAL was launched as a universal program for untargeted metabolomics that supports multiple instruments (GC/MS, GC/MS/MS, LC/MS, and LC/MS/MS)」；「Common data formats such as netCDF (AIA) and mzML, can also be managed in our project.」；「In silico retention time- and MS/MS database for LC/MS/MS based lipidomics.」
- 脂质组引用：A lipidome atlas in MS-DIAL 4, *Nature Biotechnology* 38, 1159–1163, 2020。
- 脂质命名与加合物规范子页：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>（其脂质类别命名"basically follows the definition of this paper"，指向 *J. Lipid Res.* 61(12):1539）
- 注释置信码子页：<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>
- 谱库模板（MSP / text 格式）：`.msp` 与 `Template for text format based metabolite identification.txt` 等链接均在主页；CCS 参考库：AllCCS、PNNL CCS。
- 支持 MS-DIAL 输出的下游工具（官方列表）：MS-CleanR、MetDNA、GNPS FBMN、MetFamily、LipidMatch。

**官方参数的可引用边界**：MS-DIAL 主页与子页给出的是**概念与阈值口径**（RT ≤ 0.5 min、Kovats RI ≤ 20、Fiehn RI ≤ 2000、置信码规则），**没有给出可复制的命令行**。GUI 的完整参数清单在其 PDF/教程中：MS-DIAL5 教程 <https://systemsomicslab.github.io/msdial5tutorial/>、MS-DIAL4 教程 <https://systemsomicslab.github.io/mtbinfo.github.io/MS-DIAL/tutorial>、FAQ <https://systemsomicslab.github.io/compms/msdial/faq.html>、Console App 教程 <https://systemsomicslab.github.io/compms/msdial/consoleapp.html>。

> **注意**：本技能不代抄 MS-DIAL 各版本 GUI 参数默认值。要写"我们用了 MS-DIAL x.y 的 A/B/C 参数"，必须从上述官方教程/FAQ 对应版本页取，并在 provenance 记录版本号。

### 6.4 LipidFinder

- 官方论文（含 Availability）：Alvarez-Jarreta J. et al. *Bioinformatics* 2021;37(10):1478–1479, doi:10.1093/bioinformatics/btaa856，全文 <https://pmc.ncbi.nlm.nih.gov/articles/PMC8208733/>
- 论文给出的官方入口：「freely available at <https://github.com/ODonnell-Lipidomics/LipidFinder> and <http://lipidmaps.org/resources/tools/lipidfinder>」
- 论文给出的可引用实现事实：Python 实现，"supporting versions 2.7 and 3.3 or newer"；各阶段配置存为 **JSON**；数据文件为 CSV（PeakFilter、Amalgamator）与 XLS/XLSX（MS Search）；「We have produced the user manual in two formats: a PDF file and a Jupyter notebook.」；模块含 artefact filters、isotope deletion、target–decoy FDR、以及"searches three different databases from LIPID MAPS and returns bulk lipid structures only"的 profiling。
- 定位：接在 XCMS 等前处理之后做**去伪影 + 批量结构归档**（"returns lipid bulk structures rather than fully annotated"），正是为了抑制脂质过度注释。

> **官方文档未提供可直接执行的命令**：`lipidmaps.org/resources/tools/lipidfinder` 在本环境多次请求超时/解析失败（`www.dev.lipidmaps.org` 亦不存在），`lipidfinder.github.io` 为 404，仓库 README 直链取得失败；论文正文只给入口与架构，不给 CLI 语法。因此本技能**只写流程与判据**：去伪影（污染/加合物/盐簇/源内碎片/同位素）→ Amplagamate 合并 → MS Search（3 个 LIPID MAPS 库、只回 bulk structure）→ target–decoy FDR。要执行必须按其用户手册（PDF/Jupyter notebook，随仓库发布）操作，并把版本与配置文件写进 provenance。

## 7. 与本包 MCP 化学工具的对接

本预设 `mcp/biomedical_mcp.py` 暴露三个可用于**脂质实体核对**的工具（签名与返回来自源码）：

| 工具 | 参数 | 返回 | 对脂质注释的用途 | 局限 |
|---|---|---|---|---|
| `chemistry_pubchem_search` | `query`(必填)、`namespace`（`name`/`smiles`/`inchikey`）、`max_results`（默认 10） | `{query, cids[], note}` | 由脂质俗名/缩写或 InChIKey 解析 PubChem CID，作为跨库锚点 | 只回 CID 列表，不回属性；缩写名（如 `PC 34:1`）在 PubChem 命名空间里常常无命中或命中混合物条目 |
| `chemistry_pubchem_properties` | `cid`(int，必填) | `MolecularFormula`、`MolecularWeight`、`IsomericSMILES`、`IUPACName` | 用分子式/分子量**反查精确质量**是否与观测 m/z + 加合物自洽；用 IsomericSMILES 判断该 CID 是否带立体/双键位置信息 | 只有 4 个字段；无 adduct 计算、无 CCS、无谱图；IsomericSMILES 存在 ≠ 你的 MS 能分辨该异构体 |
| `chembl_compound_search` | `name`(必填)、`max_results`（默认 5） | ChEMBL ID、SMILES、研发阶段 | 核对**具名脂质药物/介质**（如前列腺素类、胆汁酸类、特殊脂肪酸衍生物）的身份与研发阶段 | 覆盖的是类药物小分子，绝大多数结构脂质（PC/PE/TG/Cer 同系物）在 ChEMBL 无条目；不适用于脂质组通量注释 |

**使用原则**：

1. 这三个工具是**实体核对（identity check）**，不是注释器。它们替代不了第 3 节的证据链，也给不了置信级。
2. 推荐用法：`chemistry_pubchem_search` 取 CID → `chemistry_pubchem_properties` 取 `MolecularFormula` → 用 LIPID MAPS `masscalc` 或 `moverz`（第 2.3 节）算该分子式在目标加合物下的理论 m/z → 与观测值比 ppm。**这一步把"名字"和"质量"锁在一起**，能抓出命名/加合物错配。
3. 明确不做的：不拿 PubChem 命中去覆盖 LIPID MAPS/MS-DIAL 的脂质注释；不把 `MolecularWeight`（平均分子量）当精确质量用——精确质量必须用单同位素质量。

## 8. 产出目录

```
annotation/     注释表：feature_id, mz, rt, ccs, adduct, ion_mode, candidate_name,
                 lipid_class, chain1/2/3, total_cl, total_cs, level_code, evidence
                 (rt_matched/ccs_matched/ms2_matched), library, library_version
analysis/       归一化矩阵（log2）、mva 结果、de_results（含 logFC/P/adj.P）、
                 lsea 结果（set, size, ES, NES, pval, padj）、significant_lipidsets
figures/        plot_samples(tic)、plot_molecules(cv/sd)、plot_lipidclass、
                 plot_mva / plot_mva_loadings、plot_results_volcano、
                 plot_class_enrichment、plot_enrichment(length/unsat)、
                 plot_chain_distribution、plot_trend
provenance/     仪器与色谱柱、离子模式、峰检测软件+版本+参数、
                 lipidr 版本与 R/Bioconductor 版本、limma/fgsea 版本、
                 谱库名称+版本（如 MSDIAL-TandemMassSpectralAtlas-VS69）、
                 命名标准化工具与日期、归一化选择理由、缺失处理方式
```

## 9. 验收清单

- [ ] 每条注释都标了**结构层级**（species / molecular species / sn-position / DB-position），`_` 与 `/` 未混用
- [ ] 每条注释都标了**置信级**（MSI Level 或 MS-DIAL 三位码），并写明该级的前提（RT/CCS/MS2 是否匹配）
- [ ] 加合物明确（`[M+H]+`/`[M+Na]+`/`[M-H]-`/`[M+HCOO]-`…），且与类别一致（对照官方 adduct 表）
- [ ] 质量容差以 ppm 写明；RT 容差以 min 写明（脂质参考值 ≤ 0.5 min）
- [ ] 命名已标准化（LIPID MAPS / RefMet），跨研究可比
- [ ] `annotate_lipids()` 的 `not_matched`/`ambig` 分子有处理记录（`non_parsed_molecules()` 留痕）
- [ ] 归一化方法写明是 `normalize_pqn` 还是 `normalize_itsd`，以及**为什么**（有无类别内内标）
- [ ] `de_analysis` 输入确为 normalized + log2（官方前置条件）
- [ ] 类别/链层面结论来自 `lsea` + `significant_lipidsets`（给 padj、set size），不是靠肉眼扫 volcano
- [ ] `plot_chain_distribution` 的结论带"该格分子数"
- [ ] `plot_trend` 只当可视化；如做趋势统计检验，方法与参数单列
- [ ] 未使用 `dim_analysis`/`liplevel_de`/`chain_de`（不存在）
- [ ] provenance 含 lipidr/limma/fgsea 版本、谱库版本、命名工具与日期

## 10. 明确标注「官方文档未提供可直接执行的命令」的部分

| 事项 | 官方给了什么 | 缺什么 |
|---|---|---|
| 类别内归一化 vs 全局归一化的定量对比 | `normalize_pqn` / `normalize_itsd` 的机制说明 | 无 A/B 对比函数、无 QC-CV 前后比较接口 → 用 `plot_molecules(cv)` 人工判读 |
| 碳链/不饱和度趋势的统计检验 | `plot_trend` 的 loess 曲线 | 不返回斜率/CI/p → 需外部回归并单列 |
| 置换检验（OPLS-DA 的 R²Y/Q²/perm p） | `mva` 支持 OPLS/OPLS-DA | 无置换检验接口 |
| MS-DIAL GUI 参数默认值 | 阈值口径（RT ≤ 0.5 min 等）+ 教程/FAQ 链接 | 无可复制命令行；须按版本教程取参数 |
| LipidFinder 命令行 | 论文给入口、架构、JSON 配置、PDF/Jupyter 手册 | CLI 语法不可得（站点超时、GitHub Pages 404） |
| 双键位置 / sn 位置的判定阈值 | LIPID MAPS 层级定义 + MS-DIAL 置信码 `x00` | 无自动化判定规则；LC-MS/MS 下 MS-DIAL 明示"not officially supported yet" |

## 参考文档

- `references/official-docs.md` — 全部官方 URL、抓取状态、逐字要点与"哪里没有命令"
- `references/nomenclature.md` — LIPID MAPS 类别/亚类表、八级层级、加合物表、四套命名对照、各库检索入口
- `references/troubleshooting.md` — 命名解析失败、缺失值警告、blank 识别、对比式写错、lsea 报 ties、过度注释等
