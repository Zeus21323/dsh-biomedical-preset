---
name: glycomics
description: |
  Glycomics data analysis and glycan structure annotation. Covers data-type triage (N-glycan / O-glycan / intact
  glycopeptide / glycan array / lectin array), GlyTouCan accession lookup, GlycoCT and WURCS encodings with the
  official GlycanFormatConverter CLI, WURCS/GlycoCT SPARQL retrieval, LC-MS glycan profile (GU retention calibration,
  m/z and charge state, HexNAc/Hex/Fuc/NeuAc composition inference, oxonium diagnostic ions), intact glycopeptide
  search with the pGlyco series and its official helper scripts, glycan-array archives, and interpretation against
  glycosyltransferase expression. 中文触发词：糖组学、glycomics、糖链、N-糖、O-糖、完整糖肽、GlyTouCan、GlycoCT、
  WURCS、凝集素阵列。
category: omics
tags: glycomics, glycan, glytoucan, glycoct, glycoproteomics
---

# 糖组学：糖谱数据分析与糖链结构注释

本技能只写**官方文档能支撑的内容**。每条可执行命令后附来源 URL；抓取不到的官方内容，
明确写成「官方文档未提供可直接执行的命令」并只保留流程与判据。逐字抓取记录见
`references/official-docs.md`，命名与数据库入口对照见 `references/nomenclature.md`，
排错见 `references/troubleshooting.md`。

## 0. 先读：三条硬约束

1. **糖组学没有统一的峰表标准。** 脂质组有 LIPID MAPS 的层级、代谢组有 MS-DIAL/GNPS 的峰表口径；
   糖链一侧，GC/LC-MS 糖谱、完整糖肽、糖芯片三类数据各有自己的社区惯例，官方层面没有一个
   「糖组学峰表 schema」可以引用。因此本技能把**必须人工核查的环节**单列在 §8，凡不能自动判定的
   结构归属一律回到人工核查，不做自动补全、不做跨样本猜结构。
2. **结构以 accession 为准，不以俗名/缩写为准。** 同一个 `G00051MO` 在 GlyTouCan、
   GlyGen、GlyCosmos 三处应能取到同一串 WURCS/GlycoCT；取不到就说明该结构不属于任何官方库条目，
   必须保留为「未注释组成」而不是硬套名字。
3. **工具能力按官方实际形态描述。** Byonic 与 GlycoWorkbench 都是 GUI 工具：官方可抓到的页面里
   没有命令行参数表（见 §3.4），不要凭印象写它们的命令行调用。

---

## 1. 数据分型与分流（第一步，必须先分类）

五类数据的释放方式、分析口径、可执行工具完全不同，不能混在一个表里做统计。

| 分型 | 样品处理口径 | 观测对象 | 结构分辨率上限 | 官方可执行工具 | 主要风险 |
|---|---|---|---|---|---|
| N-糖（PNGase F 释放） | 酶解释放，完整糖链 | 完整糖链（含组成与连接） | 可到完整结构（isomer 需标定） | GlycanFormatConverter（编码互换）/ GlyTouCan（登记）/ pGlyco3（若走糖肽） | 释放不完全导致高分子量糖链丢失；核心岩藻糖/唾液酸损失 |
| O-糖（化学释放） | 还原性 β-消除类化学释放，无通用酶 | 完整糖链或还原端修饰糖链 | 常只能到组成/部分连接 | 同上 | 释放无化学专一性，「peeling」降解；还原端被改造后与数据库的还原端约定不符 |
| 完整糖肽（intact glycopeptide） | 蛋白酶解，糖链留在肽上 | 肽段 + 糖链联合体 | 位点 + 糖链 | pGlyco3 / pGlyco2 / Byonic | 双维打分与双维 FDR；糖链 FDR 与肽 FDR 不能混算 |
| 糖芯片（glycan array） | 纯糖链点样，测蛋白结合 | 阵列上已知结构的结合信号 | 结构由芯片定义给定，不由质谱推断 | CFG Glycan Array 归档（实验元数据） | 芯片版本不同不可直接比（见 §5） |
| 凝集素阵列（lectin array） | 凝集素点样，测样品糖链结合 | 凝集素结合谱 | 只能到「结合模式」，不到结构 | 无单一官方标准（见 §5） | 特异性矩阵来源不统一，归一化口径决定结论 |

> PNGase F 释放与 O-糖化学释放的**官方操作协议**在本环境未取得可读页面（NEB 产品页返回
> Cloudflare 人机校验；glycosciences.de 连接失败）。按硬性规则，**官方文档未提供可直接执行的命令**，
> §1 只写分流判据，具体酶量/缓冲液/时间请以试剂厂商随货说明书为准，本技能不代写。

### 1.1 分流判据（决定后面用哪一节）

- 谱图里出现**完整糖肽的肽段骨架碎片（b/y）与糖链碎片（oxonium、Y 离子）共存** → 走 §4，不要走 §3。
- 只有糖链碎片、没有肽段骨架证据，且样品经酶解释放 → 走 §3。
- 数据是**结合信号（RFU/荧光强度）而不是质荷比** → 走 §5，禁止用质谱口径处理。
- 同一批里既有糖肽又有游离糖链 → 拆成两张表分别统计，禁止合并做差异分析。

---

## 2. 命名、编码与数据库入口

### 2.1 GlyTouCan accession

官方形态：`G` + 5 位数字 + 2 位字母，例如 `G00051MO`、`G00055MO`、`G00047MO`、`G00065MO`、`G66357CN`。

- 官方页面明示 accession **不是按注册顺序的流水号**：
  "Since the accession numbers are randomly generated, they may differ between the production and beta
  environments." — <http://code.glytoucan.org/system/cli/>
- 结构页 URL 形态（官方示例给出）：`https://glytoucan.org/Structures/Glycans/G66357CN`
  — 同上页面「Please be sure to check the production environment for your changes」。
- **任务描述里的「G00000XX 零填充序号」写法不成立**：观测样本与官方说明都表明后缀随环境变化，
  不能按序号推断或按序号排序。请按「G + 5 位数字 + 2 位字母」校验格式，不做序号推理。

按 accession 取结构的官方路径有两条（都可执行）：

1. **SPARQL（推荐，可批量）**：官方 endpoint `https://ts.glytoucan.org/sparql`
   （结构/序列类查询）与 `https://ts.glycosmos.org/sparql`（物种等元数据）。
   `http://code.glytoucan.org/rdf-ontology/sparql-queries/` 原文：
   "Note that the endpoint is different depending on the type of query.  Glycan structures are primarily
   stored in GlyTouCan, while metadata such as species information can be queried from GlyCosmos."
   逐字查询见 `references/nomenclature.md` §5.1–§5.3。
2. **命令行提交/查询（官方已标 DEPRECATED，仅作存量脚本维护）**：
   页面顶部原文 "DEPRECATED — Please use direct REST access from the command line. This was using a
   groovy-specific method of downloading java libraries…"。命令见 `references/nomenclature.md` §2.3，
   引用时必须带 DEPRECATED 标记。

### 2.2 GlycoCT

- 官方仓库：<https://github.com/glycoinfo/GlycoCT>。README 原文："This repository contains the definition of
  the GlycoCT carbohydrate sequence format. The current version of the format can be found here (GlycoCT.pdf)
  and corresponds to version 4 (KIROI) developed by Stephan Herget and Rene Ranzinger in 2007."
- 规范正文是仓库内的 **PDF**（`GlycoCT.pdf`）。本环境不解析 PDF，因此**不逐字引用 GlycoCT 语法规则**；
  只使用官方页面给出的样例串形态（`RES` / `LIN` 两段）：

  ```
  RES
  1b:b-dglc-HEX-1:5
  2s:n-acetyl
  3b:b-dgal-HEX-1:5
  LIN
  1:1d(2+1)2n
  2:1o(4+1)3d
  ```
  — 逐字取自 <http://code.glytoucan.org/system/cli/> 的 GlycoCT 提交示例（官方注明 "note the carriage
  returns are \"\\n\""）。

### 2.3 WURCS

- 官方规范可逐字抓取（wiki）：`WURCS-2.0-Manual` → `WURCS-notations` → `WURCS-components`，
  见 <https://github.com/glycoinfo/WURCS/wiki>。
- 基本格式（原文）：`WURCS=` `<Version>` `/` `<Unit Count>` `/` `<UniqueRES List>` `/` `<RES Sequence>`
  `/` `<LIN List>`；`<Unit Count>` = `<UniqueRES Count>`,`<RES Count>`,`<LIN Count>`；
  连接数不确定时用 `<LIN Count>` `+`。
- `UniqueRES` 为 `[` `ResidueCode` `]`；`ResidueCode` = `BackboneCode` `_` `MOD…`；
  `BackboneCode` = `SkeletonCode` `-` `Anomeric Information`；`SkeletonCode` 每个字符是一个
  `CarbonDescriptor`（六碳糖 = 6 个字符）。
- `Anomeric Symbol`：α = `a`，β = `b`，`u`/`d` 为绝对立体描述符（原文："α anomer is represented as
  symbol `a` and β anomer as symbol `b`"；"When an exocyclic atom … is on the left side in cyclic Fischer
  projection, the Anomeric Symbol is `u` … When the exocyclic atom is on the right side … `d`"）。
- 完整 CarbonDescriptor 表与 LIP/GLIP 定义见 `references/nomenclature.md` §4.2–§4.3。

### 2.4 官方编码互换工具：GlycanFormatConverter（可执行）

这是官方唯一给出**命令行参数表**的糖链编码互换工具，替代「自己写转换脚本」。

- 客户端仓库（CLI）：<https://gitlab.com/glycoinfo/GlycanFormatConverter-cli>；
  核心库：<https://github.com/glycoinfo/GlycanFormatConverter>。
- 构建（逐字）：

  ```
  git clone https://gitlab.com/glycoinfo/GlycanFormatConverter-cli.git
  cd GlycanFormatConverter-cli
  mvn clean compile assembly:single
  ```

- 调用（逐字）：

  ```
  java -jar ./target/GlycanFormatConverter-cli.jar -i <FORMAT> -e <FORMAT> -seq <SEQUENCE>
  ```

- 选项（逐字表）：

  | 选项 | 取值 | 说明 |
  |---|---|---|
  | `-i, --import` | `IUPAC-Condensed` \| `IUPAC-Extended` \| `GlycoCT` \| `KCF` \| `LinearCode` \| `WURCS` | 输入格式 |
  | `-e, --export` | `IUPAC-Short` \| `IUPAC-Condensed` \| `IUPAC-Extended` \| `GlycoCT` \| `WURCS` \| `GlycanWeb` | 输出格式 |
  | `-seq, --sequence` | 序列字符串 | 待转换文本 |
  | `-h, --help` | — | 用法 |

- 支持矩阵（逐字）：`WURCS` 输入可导出 IUPAC-Extended/Short/Condensed、GlycoCT、GlycanWeb；
  `IUPAC-Extended` 可导出 Condensed/Short/WURCS/GlycanWeb；`GlycoCT` 输入可导出
  IUPAC-Extended/Short/Condensed、WURCS、GlycanWeb。**注意矩阵中 `GlycoCT` 行的 `GlycoCT` 列与
  `WURCS` 行的 `WURCS` 列为空**，即同格式不互转，需要时先中转一次。
- 例（逐字，WURCS → IUPAC-Extended）：

  ```
  java -jar ./target/GlycanFormatConverter-cli.jar -i WURCS -e IUPAC-Extended -seq 'WURCS=2.0/5,9,8/[a2122h-1x_1-5][a2112h-1b_1-5][a2122h-1b_1-5_2*NCC/3=O][a1221m-1a_1-5][Aad21122h-2a_2-6_5*NCC/3=O]/1-2-3-2-4-5-3-2-5/a4-b1_b3-c1_b6-g1_c4-d1_d2-e1_d6-f2_g4-h1_h6-i2'
  ```
- 官方声明的限制（`RESTRICTIONS.md`，2.6.0 起）：含重复单元、环状单元、交联取代基、单糖片段、
  取代基片段、脱氧等修饰的 IUPAC 输入会被当作异常并报转换错误；WURCS 的 `x`/`X` 通配
  SkeletonCode（如 `WURCS=2.0/1,1,0/[AOOxxh]/1/`）会报
  `This SkeletonCode partially contains the wild card (x or X).`
- REST API 入口（README 原文）：<https://api.glycosmos.org/glycanformatconverter/>。
  README 未给出请求体格式，本技能**不写该接口的请求示例**。

### 2.5 数据库入口

| 入口 | URL | 官方可核实内容 |
|---|---|---|
| GlyTouCan | <https://glytoucan.org/> ；代码/文档站 <http://code.glytoucan.org/> | 国际糖链结构库（accession 登记）；站点为 SPA，`/Documentation` 返回的是加载壳，正文需靠 code 站与 wiki |
| GlyCosmos | <https://glycosmos.org/> ；SPARQL `https://ts.glycosmos.org/sparql` | 元数据（物种等）查询端点；官方 query 示例给出该 endpoint |
| GlyGen | <https://www.glygen.org/> ；API `https://api.glygen.org/` | 官方站点描述："GlyGen is a data integration and dissemination project for carbohydrate and glycoconjugate related data." |
| GlycoNAVI | <https://glyconavi.org/> | WURCS 官方工具索引里列出的糖科学门户 |
| CSDB | <http://csdb.glycoscience.ru/> | 天然糖链结构、分类、文献手工整理库 |
| GlycoStore | <https://glycostore.org/> | 保留性质（RT）库，单位集合含 HPLC / UPLC_2-AB / UPLC_Procainamide / CE / RP / PGC，含 GlycoCT Structure 与 MIRAGE LC 栏目 |
| CFG 糖芯片归档 | <https://www.functionalglycomics.org/glycan-array> | 糖芯片实验归档（6035 条实验），芯片版本 PA_v0…PA_v52、GLYCAN_v1…v3、BACT_v1 |

> **任务描述里的「CFG 命名法」需要修正**：现站上未找到 CFG 命名法页面
> （`/static/consortium/Nomenclature.shtml` 与 `/glycomics/nomenclature` 均 404）。官方可抓到的 CFG
> 资源是糖芯片实验归档。GlycanFormatConverter 的 import 列表里有 `LinearCode`，但官方 README 的可抓取
> 文本**没有**把它明确等同 CFG 线性码，此处不作等同断言，按官方格式名为准。

---

## 3. LC-MS 糖谱（游离糖链）

### 3.1 葡萄糖单位（GU）标定

- GU 是**相对保留时间**单位：用葡萄糖同系物梯（glucose homopolymer ladder）做外标，把样品峰保留时间
  插值换算成 GU。它绑定「色谱柱 + 梯度 + 标记化学（如 2-AB、procainamide）」三要素，换任一要素都必须重标。
- 官方层面能核实的是**保留性质库与单位词表**：GlycoStore 的单位栏为
  `HPLC`、`UPLC_2-AB`、`UPLC_Procainamide`、`CE`、`RP`、`PGC`，每条记录带 `GlycoCT Structure`。
  来源：<https://glycostore.org/>。
- **官方文档未提供可直接执行的命令**（没有官方的 GU 换算命令行工具或参数表被本环境抓到）。
  因此 GU 标定按流程执行：① 标准梯随批进样 → ② 用同批标准梯拟合保留时间-GU 曲线 → ③ 只与
  「同柱同梯度同标记」的 GlycoStore 记录比对 → ④ 跨批次不合并 GU。
- **必须人工核查**：标准梯峰识别是否正确（尤其 DP>12 的信噪比）、是否有共洗脱导致插值失真。

### 3.2 m/z 与电荷态

- 糖链在 ESI 下常见多电荷（尤其带唾液酸的酸性糖链），必须先定电荷态再谈组成，否则
  `m/z` 差 1 Da 会被误读成「多一个脱氧/少一个氧」。
- 判据：同位素簇间隔。间隔 ≈ 1/z（z 为电荷数），据此定 z 后再换算中性质量。
- 官方工具侧只有质量计算：pGlyco3 仓库自带 `mass_calc/chem2mass.py`，官方用法原文：

  ```
  python [-f formula] [-ini inifile -formula_pos n -mass_pos m] [-r replacement]
  ```
  官方示例原文：`marker 138 formula: python -f C(7)H(7)N(1)O(2) -r N~15N`
  （来源：<https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/mass_calc/chem2mass.py>）

### 3.3 组成推断（HexNAc / Hex / Fuc / NeuAc）

- 组成推断的建议顺序：先定电荷与中性质量 → 再用单糖残基质量差枚举组合 → 再用**诊断离子**做交叉验证。
- 诊断离子（oxonium ions）官方表（逐字，来自 pGlyco3 仓库
  `scripts/diagnostic-ion-checker.py` 的 usage 注释）：

  | Marker (m/z) | Glyco | Formula w/o proton |
  |---|---|---|
  | 109.028 | Hex fragment | C6H4O2 |
  | 115.039 | Hex fragment | C5H6O3 |
  | 126.055 | HexNAc fragment | C6H7O2N1 |
  | 127.039 | Hex–H2O*2 | C6H6O3 |
  | 138.055 | HexNAc fragment | C7H7O2N1 |
  | 144.066 | HexNAc fragment | C6H9O3N1 |
  | 163.060 | Hex | C6H10O5 |
  | 168.066 | HexNAc–H2O*2 | C8H9O3N1 |
  | 186.076 | HexNAc–H2O | C8H11O4N1 |
  | 204.087 | HexNAc | C8H13O5N1 |
  | 274.092 | NeuAc–H2O | C11H15O7N1 |
  | 290.087 | NeuGc–H2O | C11H15O8N1 |
  | 292.103 | NeuAc | C11H17O8N1 |
  | 308.098 | NeuGc | C11H17O9N1 |
  | 366.140 | Hex+HexNAc | C14H23O10N1 |
  | 657.140 | Hex+HexNAc+NeuAc | C25H40O18N2 |
  | 673.230 | Hex+HexNAc+NeuGc | C25H40O19N2 |

- 官方脚本调用（逐字 usage）：

  ```
  python diagnostic-ion-checker.py -mgf mgf_containing_folder -marker 204.087,138.055
  ```
  输出：`marker-ion.csv in the mgf_containing_folder`（原文）。

- **必须人工核查**：Fuc 与「Hex 差一个 O」这类同量异构成分不能只靠质量分辨；NeuAc 与 NeuGc 的
  区分要 292/308 两个 marker 同时成立；只命中 204.087 而 138.055 缺失时不能断言 HexNAc 数量。

### 3.4 官方工具的实际形态（写作时必须照实说）

- **GlycoWorkbench**：官方仓库 <https://gitlab.com/glycoinfo/glycoworkbench>。README 可执行的只有
  构建与启动：

  ```
  mvn clean package
  java -XstartOnFirstThread -jar ./target/glycoworkbench2-0.0.2-SNAPSHOT-jar-with-dependencies.jar
  ```
  README 原文："The GlycoWorkbench (GWB) manual can be accessed via the Help menu of GWB."，
  且 "Web site: TODO:"。
  → **官方文档未提供可直接执行的注释命令**；GWB 的注释是 GUI 交互，不能写成命令行流水线。
- **Byonic**：官方产品页 <https://www.proteinmetrics.com/products/byonic>。可核实的官方描述：
  "Identify glycopeptides without prior knowledge of glycan masses or glycosylation sites."、
  "Byonic scores and annotates multiple types of glycopeptide fragments to deduce the peptide carrier,
  glycan and modification site."；参数文档在 Knowledge Base
  <https://support.proteinmetrics.com/hc/en-us>。
  → **官方文档未提供可直接执行的命令**（无公开 CLI 参数表可抓取）；不要编造 Byonic 命令行。

---

## 4. 完整糖肽（intact glycopeptide）

### 4.1 官方工具形态

- **pGlyco3**（官方仓库 <https://github.com/pFindStudio/pGlyco3>）：README 原文为
  "Intact N- and O-glycopeptide search engine"；用户手册是仓库内 `pGlyco3-User-Guide.pdf`
  （本环境不解析 PDF）；首次使用需申请 license，README 原文："When using pGlyco3 for the first time,
  a license applicaiton dialog will show… paste the form on http://i.pfind.net/license/pGlyco3 to
  generate a license."；定量转 pGlycoQuant（<https://github.com/Power-Quant/pGlycoQuant/releases>）。
- **pGlyco2**（<https://github.com/pFindStudio/pGlyco2>）：README 列出 `pGlycoFDR.exe`、`gLabel`、
  `xtract_raw`、`pParse` 等组件，并说明 2.2.0 起 `xtract_raw` 改用 Thermo RawFileReader，
  可 "rename the xtract_raw_with_msfilereader.exe in the installation folder as xtract_raw.exe" 回退。
  → 检索主程序参数表在 PDF 手册里，**官方文档未提供可直接执行的命令**；不要写 pGlyco 的检索命令行。

### 4.2 可执行的官方脚本（仓库自带，非本技能编写）

以下 4 个脚本是 pGlyco3 官方仓库文件，命令取自各自文件头的 usage 原文：

| 脚本（仓库路径） | 官方 usage 原文 | 作用 |
|---|---|---|
| `scripts/pGlyco_to_skyline_ssl.py` | `python pGlyco_to_skyline_ssl.py C:/output/folder/pGlyco.cfg` 或 `python pGlyco_to_skyline_ssl.py C:/output/folder/pGlycoDB-GP-FDR.txt raw_folder` | 把 pGlyco 结果转成 Skyline SSL 格式 |
| `scripts/diagnostic-ion-checker.py` | `python diagnostic-ion-checker.py -mgf mgf_containing_folder -marker 204.087,138.055` | 批量检查诊断离子，输出 `marker-ion.csv` |
| `mass_calc/chem2mass.py` | `python [-f formula] [-ini inifile -formula_pos n -mass_pos m] [-r replacement]` | 分子式→质量（含同位素替换） |
| `find_oxonium/find_oxonium_ions.py` | 脚本内以变量配置（`scan_txt`、`pf2`、`output`、`max_mz=300`、`min_rel_inten=0.1`、`bin_per_Da=0.1`） | 从 `.pf2` 抽取指定 scan 的 oxonium 峰型 |

> 这 4 个脚本是官方提供的现成脚本；本技能**不复制其代码**，只引用路径与 usage，
> 需要时直接从官方仓库获取。

### 4.3 双维打分与 FDR

- pGlyco 系列的核心是**糖链与肽段双维打分**，输出**两套 FDR**。官方脚本里可逐字看到列名与默认阈值
  （`scripts/protein_site_analysis.py` 文件头）：

  ```
  glycan_fdr_thres = 0.01
  peptide_fdr_thres = 0.1
  ```
  过滤逻辑逐字：`GlycanFDR` > 阈值则跳过、`PeptideFDR` > 阈值则跳过，并同时读取 `TotalFDR`。

- 结果表列名（同一脚本读取，逐字）：`GlycanFDR`、`PeptideFDR`、`TotalFDR`、`GlySpec`、`RawName`、
  `Scan`、`ETDScan`、`Peptide`、`GlySite`、`Mod`、`Glycan(<...>)`、`MonoArea`、`IsotopeArea`、`Proteins`。
- 输出文件名形态（`pGlyco_to_skyline_ssl.py` 逐字）：`%s-GP-FDR.txt`（`pGlyco_type` 前缀），
  配置文件名 `pGlyco.cfg`，其键包括 `file`、`output_dir`、`pGlyco_type`。
- **规则**：糖链 FDR 与肽 FDR **不能相乘当「总 FDR」用**；`TotalFDR` 是官方给出的合并口径，
  报告里必须写清用了哪一个、阈值多少。
- **必须人工核查**：`GlySite` 与 `Mod` 同时非空时的位点归属；同一 `Scan` 多个 glycan 命中时的
  占比（microheterogeneity）是否按峰面积还是按谱图数统计。

---

## 5. 糖芯片与凝集素阵列

### 5.1 糖芯片（glycan array）

- 官方归档：<https://www.functionalglycomics.org/glycan-array>（CFG Glycan Array Data）。
  页面可核实字段：`ID`、`Primary Screen ID`、`Request`、`Sample`、`Description`、`Category`、
  `Glycan Array`、`Investigator`、`Conclusive`。
- 芯片版本字段（逐字选项）：`PA_v0 … PA_v52`、`GLYCAN_v1 … v3`、`BACT_v1`。
- `Category` 选项含凝集素类别：`C-type Lectin`、`iTypeLectins`、`Other Animal Lectins`、
  `plantLectins`、`Antibodies and Serum samples`、`Pathogens (bacteria, viruses) and Microbial Lectin`、
  `sTypeLectins`、`notClassified`。
- **归一化判据**：① 只在**同一芯片版本、同一 Request**内比较；② 记录 `Conclusive` 字段
  （`Data` / `Inconclusive`），`Inconclusive` 不得进入统计主表；③ 不同版本（如 PA_v4 与 PA_v52）
  的 glycan 点号不可直连，必须按结构（accession/WURCS）对齐后再比。

### 5.2 凝集素阵列

- **官方层面没有统一的结合特异性矩阵标准**：本环境未取得任何官方发布的、可作为唯一引用源的
  凝集素特异性矩阵（ACGG LfDB 探测 404；glycobase.nibrt.ie TLS 连接失败）。
- 因此本技能的处理口径是：**特异性矩阵必须由使用方提供并写明版本与来源**，技能侧只做三件事——
  ① 按凝集素名与批次建立矩阵快照并记录来源；② 归一化在样本内完成（同一凝集素跨样本可比，
  跨凝集素不可比）；③ 报告里同时给「原始强度」「归一化后」「矩阵版本」三项。
- **必须人工核查**：糖链与凝集素的交叉反应（同一凝集素命中多个结构）不能被解释为「结构被确证」，
  只能写成「与该凝集素结合谱一致」。

---

## 6. 统计与解读

### 6.1 组成层面差异

- 统计单位必须是**糖链组成或 accession**，不是峰。同一组成多个峰（isomer）在组成层面合并，
  在结构层面分开，两套结果分别出表。
- 差异分析前先定「组成向量」：以 HexNAc/Hex/Fuc/NeuAc/NeuGc 计数为列，做对数比或比例变换，
  再做组间检验；不要把原始强度直接做 t 检验（强度受上样量与离子化效率双重影响）。

### 6.2 与糖基转移酶表达的关联

- 逻辑链：结构层面观察到「某连接/某分支增加」→ 找对应糖基转移酶 → 在配对的转录组/蛋白组里
  查该酶的表达 → 一致性判断。
- 酶与结构的对应关系**不是一对一**（同一酶可作用于多种底物，同一连接可由多酶完成），
  所以关联只能作为**假设生成**，不能写成因果。
- 可用 MCP 取酶的身份与注释：`genes_ontologies_mygene_query`（符号→ID）、
  `genes_ontologies_quickgo_annotations`（GO 注释），见 §7。
- **必须人工核查**：酶表达变化与结构变化方向是否一致；是否被糖核苷酸供体水平（而非酶表达）
  解释；样本是否有炎症/肝功等混杂。

### 6.3 IgG 糖型特例

IgG 是糖组学里最容易做错的一类，单列规则：

- IgG 的 N-糖主要挂在 Fc 的保守位点，**糖型分布是群体性比例**（如无半乳糖/单半乳糖/双半乳糖、
  岩藻糖化与否、唾液酸化与否），因此报「比例」而不是「某结构的有无」。
- 位点信息在此类数据里通常是**已知且固定**的，不需要也不应该用糖肽位点打分去「发现」位点；
  反过来，若流程把 IgG 当未知糖蛋白做 de novo 位点定位，结果不可信。
- IgG 糖型与炎症/衰老等状态的关联在文献里大量存在，但**本技能不引用任何未在本次核实的文献数字**；
  解读时只写「与已报道方向一致/不一致」，具体效应量以所引原文为准。
- **必须人工核查**：是否混入血清其他糖蛋白（转铁蛋白、IgA）导致糖型比例失真；是否做了
  IgG 亲和富集；Fc 与 Fab 糖型的区分（Fab 糖型会污染 Fc 比例）。

---

## 7. MCP 对接（本包内置，能力有限，只作辅证）

本包 `mcp/biomedical_mcp.py` 注册的工具里，与糖组学**能搭上边**的只有下面这些；没有一个糖链专用工具。

| 工具 | 参数（官方 schema） | 在糖组学里的用法 | 局限 |
|---|---|---|---|
| `chemistry_pubchem_search` | `query`(必填)、`namespace`（`name`/`smiles`/`inchikey`）、`max_results`（默认 10） | 用单糖/糖衍生物名或 InChIKey 取 PubChem CID，作为跨库锚点 | 只回 CID，不回属性；糖链（多残基）在 PubChem 命名空间里通常无整链条目，只能查单糖/糖苷 |
| `chemistry_pubchem_properties` | `cid`(必填) | 取 `MolecularFormula` 等，用于手算单糖残基质量差 | 单糖条目多，整链无条目 |
| `genes_ontologies_ols_term` | `ontology`(必填，如 `go`/`cl`/`efo`)、`term_id`(必填，如 `GO:0006915`) | 查糖基转移酶相关 GO 术语的定义与层级 | 官方示例只给了 go/cl/efo；糖链本体在该参数下的可用性未验证，需按实际返回核查 |
| `genes_ontologies_mygene_query` | `terms`(必填，逗号分隔)、`species`、`fields`、`max_results` | 糖基转移酶基因符号→Entrez/Ensembl | 只做 ID 解析 |
| `genes_ontologies_quickgo_annotations` | `uniprot`(必填)、`aspect`、`max_results`（默认 50） | 取酶的 GO 注释，支撑 §6.2 的关联假设 | 注释是历史累积，不代表当前样本 |
| `omics_archives_geo_search` / `omics_archives_pride_project` | `term` / `accession` | 找公开糖组/糖蛋白组数据集 | 只做检索 |

**明确写清**：MCP 侧没有任何工具能直接做「糖链结构注释」或「GlyTouCan accession 解析」；
结构注释必须走 §2 的官方 SPARQL / 官方转换器，MCP 只提供化学与基因层面的旁证。

---

## 8. 因为没有统一峰表标准，这些环节必须人工核查

| # | 环节 | 为什么必须人工 | 核查动作 |
|---|---|---|---|
| 1 | 电荷态判定 | 多电荷糖链的 m/z 差可伪装成组成差 | 逐峰看同位素簇间隔，记录 z |
| 2 | 组成枚举的唯一性 | 同质量多组成本身就是常态 | 列出所有候选组成，标「不可分辨」 |
| 3 | isomer 归属 | 质量相同、连接不同，MS2 才能分 | 无诊断离子支撑时只报组成 |
| 4 | 岩藻糖/脱氧糖区分 | 与 Hex−O 同量 | 交叉验证 marker，必要时标「待定」 |
| 5 | 唾液酸种类（NeuAc/NeuGc） | 292 与 308 需同时成立 | 两 marker 都查 |
| 6 | 还原端约定 | 化学释放会改还原端 | 与数据库条目还原端形态对齐后再比对 |
| 7 | GU 跨批可比性 | GU 绑柱/梯度/标记 | 只在同柱同梯度同标记内比 |
| 8 | 糖肽位点归属 | `GlySite`+`Mod` 可能多解 | 逐谱图看 b/y 与糖碎片是否指向同一位点 |
| 9 | 双维 FDR 口径 | 糖链 FDR、肽 FDR、TotalFDR 三者不同 | 报告写明用哪个、阈值多少 |
| 10 | 芯片版本对齐 | 点号跨版本不可比 | 按 accession/WURCS 对齐 |
| 11 | 凝集素交叉反应 | 特异性矩阵非唯一官方源 | 记录矩阵来源与版本，结论写「一致」不写「确证」 |
| 12 | accession 有效性 | 结构必须能在官方库取到 | 用 §2.1 的 SPARQL 反查一次 |

---

## 9. 产出目录（建议）

```
glycomics_run/
├─ 00_meta/
│   ├─ sample_sheet.tsv            # 样本、分型（N/O/糖肽/芯片/凝集素）、批次
│   └─ method_snapshot.md          # 柱/梯度/标记/酶/仪器参数快照（GU 与芯片对齐的依据）
├─ 01_release/                     # 释放与酶解记录（按 §1 分型分文件）
├─ 02_ms_profile/
│   ├─ peaks_charge_annotated.tsv  # m/z、z、中性质量、候选组成
│   ├─ marker_ions.csv             # 官方 diagnostic-ion-checker 输出
│   └─ gu_calibration.tsv          # 标准梯拟合结果 + 适用范围
├─ 03_structure/
│   ├─ compositions.tsv            # 组成向量（统计单位）
│   ├─ glycans.glycoct / .wurcs    # 每结构的两种编码
│   └─ accession_map.tsv           # 本地结构 → GlyTouCan accession（含未命中标记）
├─ 04_glycopeptide/
│   ├─ pGlyco3.cfg                 # 官方配置快照
│   ├─ *-GP-FDR.txt                # 官方输出
│   └─ skyline_ssl/                # pGlyco_to_skyline_ssl.py 输出
├─ 05_array/
│   ├─ array_meta.tsv              # 芯片版本 / Request / Conclusive
│   └─ lectin_matrix_source.md     # 特异性矩阵来源与版本
├─ 06_stats/
│   ├─ composition_diff.tsv
│   └─ enzyme_link_hypotheses.tsv
└─ 07_report/
    ├─ manual_review_log.tsv       # §8 十二项逐条结论
    └─ provenance.md               # 引用到的官方 URL 清单
```

## 10. 验收清单

- [ ] 每条命令都能在 `references/official-docs.md` 找到对应官方 URL 与抓取状态
- [ ] 没有出现未经官方文档支撑的 Byonic / pGlyco 检索命令行
- [ ] GlycoCT 语法规则没有被「补写」（PDF 未解析，只引用官方样例串）
- [ ] 每个 accession 的格式是 `G`+5 位数字+2 位字母，且经 SPARQL 反查存在
- [ ] 结构同时存了 GlycoCT 与 WURCS 两份编码，转换走了官方 GlycanFormatConverter
- [ ] 统计单位写明是「组成」还是「accession」，两套结果分开出表
- [ ] 糖链 FDR / 肽 FDR / TotalFDR 口径在报告里点名
- [ ] GU 只在与标准梯同柱同梯度同标记的范围内使用
- [ ] 芯片结果记录了版本与 `Conclusive`，`Inconclusive` 未进主表
- [ ] 凝集素结论写成「结合谱一致」，没有写成结构确证
- [ ] `manual_review_log.tsv` 覆盖 §8 全部 12 项
- [ ] 所有 `官方文档未提供可直接执行的命令` 的位置都显式标注，未用自造脚本替代
