# 官方文档来源清单（逐一抓取确认）

抓取日期：2026-10-29（Asia/Shanghai）。本文件记录 `SKILL.md` 每条命令/每条事实的来源页面、
抓取通道与抓取状态。凡状态不是 OK 的，正文一律不引用其命令。

抓取通道说明：

- `web_fetch` — 内置抓取工具；`raw.githubusercontent.com` 经此通道**全部失败**
  （`TypeError: fetch failed`），改为下一通道。
- `pwsh/Invoke-WebRequest` — 同一 URL 经此通道成功，故所有 GitHub raw/wiki 内容均由该通道取得。
- `jsdelivr` 镜像 — 跨域重定向不被跟随（`cross-origin redirect ... not followed automatically`），未采用。

---

## 1. GlyTouCan

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| T1 | https://glytoucan.org/ | 站点首页 | **200 但为 SPA 加载壳**：正文只有 `L O A D I N G` 逐字母动画节点，无任何可读文本 |
| T2 | https://glytoucan.org/Documentation | 文档页（任务描述指定的入口） | **200 但同样为 SPA 加载壳**，无正文 |
| T3 | https://glytoucan.org/Structures/Glycans/G00051MO | 结构页 | 200，SPA 壳（可用于确认 URL 形态存在，正文不可读） |
| T4 | http://code.glytoucan.org/system/cli/ | **GlyTouCan Client CLI 文档**（正文主要来源） | **OK，全文可读** |
| T5 | http://code.glytoucan.org/FAQ | 常见问题 | **OK，全文可读** |
| T6 | http://code.glytoucan.org/manual | User Manual | OK（内容很短：只有 Registration / Search / Partner 的栏目索引） |
| T7 | http://code.glytoucan.org/rdf-ontology | RDF/Ontology 入口 | OK（仅栏目索引 + 指向 sparql-queries） |
| T8 | http://code.glytoucan.org/rdf-ontology/sparql-queries/ | **官方 SPARQL 示例**（§2.1 查询来源） | **OK，全文可读** |
| T9 | http://code.glytoucan.org/system/api_list/ | GlyTouCan API List（SOAP contract 形态的功能清单） | **OK，全文可读（19 589 字节）** |
| T10 | https://code.glytoucan.org/api/ | API 首页 | OK（只有一段指向 wiki 的说明） |
| T11 | https://github.com/glytoucan/api/wiki | API wiki | 200，但抓取被 GitHub 导航栏占满（截断），正文未取到 |
| T12 | https://raw.githubusercontent.com/wiki/glytoucan/api/Home.md | 同上（wiki 源） | OK，全文仅 2 行：指向 nexus javadoc |
| T13 | https://raw.githubusercontent.com/glytoucan/databaseSync/master/README.md | 官方脚本仓库 README | OK（列出 `curlRemove.sh`、`curlRemoveBySeq.sh`、`PartnerAddNavi.php`） |
| T14 | https://ts.glytoucan.org/sparql | SPARQL endpoint | **200，返回 OpenLink Virtuoso SPARQL Query Editor**（端点存活） |
| T15 | https://glytoucan.org/api/v2/glycans/G00051MO | 我试探的 REST 路径 | **HTTP 404** — 该路径不是官方端点，`SKILL.md` 未使用 |
| T16 | https://api.glytoucan.org/ 、`/glycans/G00051MO`、`/glycan/G00051MO` | 官方 CLI 页提到的 API host | 三处均 **HTTP 404**（host 存在但无根路由/该路径）；`SKILL.md` 只在引用「生产环境 API_HOSTNAME」时提到该 host，不提供端点 |

### T4 逐字要点（`SKILL.md` §2.1、§2.4 依赖）

- 页面顶部：`DEPRECATED` / "Please use direct REST access from the command line.  This was using a
  groovy-specific method of downloading java libraries, which is unneccessary for interfacing with a REST API."
- "The GTCC was a command line interface to the GlyTouCan Repository API." / "** Please Note ** This library is
  now deprecated.  Please use the simplified REST method to interface with the GTC API.  Simplified bash scripts
  have been added to the same git repository."
- 单条提交：`groovy gtc -u [contributor id] -a [API key] -s '[sequence]'`
- CSV：`groovy gtc -u [contributor id] -a [API key] -c [csvFile]`；TSV：`-t [tsvFile]`
- 输出格式：`-o csv` / `-o tsv`；表头：`-m uafh`（`u`: contributorId, `a`: apiKey, `f`: csvFileName or
  tsvFileName, `h`: header）
- 生产环境：`$ export API_HOSTNAME="https://api.glytoucan.org"`；默认走 `http://test.glytoucan.org`
- "Since the accession numbers are randomly generated, they may differ between the production and beta
  environments."
- 样例输出 accession：`G66357CN`、`G00055MO`、`G00051MO`、`G00065MO`、`G00047MO`
- GlycoCT 提交示例（含 `\n` 说明）：`RES\n1b:b-dglc-HEX-1:5\n2s:n-acetyl\n3b:b-dgal-HEX-1:5\nLIN\n1:1d(2+1)2n\n2:1o(4+1)3d\n`
- 注意事项逐字："For some formats, the carriage return characters must be replaced with “\n”." /
  "Since WURCS contains “,” in the sequence, it should be in quotes (usage of quotes is ‘sequence’ not “sequence”.)."

### T5 逐字要点（`SKILL.md` §2.1 限制）

- "Q. What would happen if I don’t have linkage position information? A. The position would be considered
  ambigous. It would be registered as ambiguous and when searching, the similar structures with any linkage
  position will be queried."
- "Q. How are aglycons supported? A. Currently aglycons and glycoconjugates are not supported."
- 提交报 `status:500 Internal Server Error "401 null"` 时的官方解法：到
  `https://glytoucan.org/Users/profile` 点 "Generate API Key"。

### T8 逐字要点（`SKILL.md` §2.1）

- "Note that the endpoint is different depending on the type of query.  Glycan structures are primarily stored in
  GlyTouCan, while metadata such as species information can be queried from GlyCosmos."
- 结构（WURCS）查询用 `FROM <http://rdf.glytoucan.org/core>` + `FROM <http://rdf.glytoucan.org/sequence/wurcs>`，
  谓词 `glytoucan:has_primary_id`、`glycan:has_glycosequence`、`glycan:has_sequence`、
  `glycan:in_carbohydrate_format glycan:carbohydrate_format_wurcs`，endpoint `https://ts.glytoucan.org/sparql`。
- GlycoCT 同理，图名 `.../sequence/glycoct`，格式常量 `glycan:carbohydrate_format_glycoct`。
- 按外部库 ID 反查 accession（GlycomeDB）与按物种（`9606`/`10090`）取 IUPAC-Condensed 的两条查询，
  endpoint 为 `https://ts.glycosmos.org/sparql`。

---

## 2. GlycoCT

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| C1 | https://github.com/glycoinfo/GlycoCT | 仓库页 | 200，但抓取内容被 GitHub 导航栏占满（截断），正文未取到 |
| C2 | https://raw.githubusercontent.com/glycoinfo/GlycoCT/master/README.md | 仓库 README（正文来源） | **OK（经 pwsh），全文可读** |
| C3 | https://api.github.com/repos/glycoinfo/GlycoCT/git/trees/master | 文件树 | **HTTP 404**（默认分支不是 master） |
| C4 | https://api.github.com/repos/glycoinfo/GlycoCT/branches 、`/contents/` | 分支/目录列表 | **HTTP 403**（GitHub API 限流） |
| C5 | 仓库内 `GlycoCT.pdf` | 规范正文 | **未抓取**：PDF 不在可解析范围 |

### C2 逐字要点

- "This repository contains the definition of the GlycoCT carbohydrate sequence format. The current version of the
  format can be found here (GlycoCT.pdf) and corresponds to version 4 (KIROI) developed by Stephan Herget and
  Rene Ranzinger in 2007."
- 引用：Herget S, Ranzinger R, Maass K, Lieth CW. (2008). GlycoCT-a unifying sequence format for carbohydrates.
  Carbohydr Research;343(12):2162-71. PMID:18436199
- 许可：CC BY 4.0

> 结论（硬性规则 1）：GlycoCT 的**语法规则**只存在于 PDF。本技能因此**不逐字引用语法**，只引用
> T4 页面给出的官方样例串（`RES`/`LIN`），并在 `SKILL.md` §2.2 显式标注这一点。

---

## 3. WURCS

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| W1 | https://github.com/glycoinfo/wurcs | 仓库页 | 200，被导航栏截断 |
| W2 | https://raw.githubusercontent.com/glycoinfo/wurcs/master/README.md | README | OK，全文 20 字节：`WURCS Working Group` |
| W3 | https://raw.githubusercontent.com/glycoinfo/wurcs/master/about.md | About WURCS | **OK，全文可读** |
| W4 | https://raw.githubusercontent.com/glycoinfo/wurcs/master/index.md | 工具与数据库总表 | **OK，全文可读（10 996 字节）** |
| W5 | https://api.github.com/repos/glycoinfo/wurcs/git/trees/master | 文件树 | OK（确认 `index.md`、`about.md`、`doc/`、`docs/`、`tools/`、`soft/`） |
| W6 | https://raw.githubusercontent.com/wiki/glycoinfo/WURCS/Home.md | 规范入口 | **OK**（56 字节，指向 Manual/Tips/Examples） |
| W7 | https://raw.githubusercontent.com/wiki/glycoinfo/WURCS/WURCS-2.0-Manual.md | Manual 目录 | **OK**（指向 Theoretical-consideration / About-WURCS / WURCS-notations / WURCS-components / Representations-for-Basic-Structures） |
| W8 | https://raw.githubusercontent.com/wiki/glycoinfo/WURCS/WURCS-notations.md | **WURCS 记法正文** | **OK，全文 12 070 字节** |
| W9 | https://raw.githubusercontent.com/wiki/glycoinfo/WURCS/WURCS-components.md | **组件定义（CarbonDescriptor 等）** | **OK，全文 20 825 字节** |

### W3 逐字要点

"…we have determined that there are two requirements for carbohydrate data representations: 1) a linear notation
which can be used as an URI if needed, 2) a unique notation such that any published glycan structure can be
represented distinctly. This latter requirement includes the possible representation of non-standard monosaccharide
units as a part of the glycan structure, as well as compositions, repeating units and ambiguous structures where
linkages/linkage positions are unidentified."

### W4 逐字要点（工具/数据库索引，`SKILL.md` §2.5 表格来源）

- GlycanFormatConverter：`https://glyconavi.org/Tools/tool/gfc.php`、
  `https://glycosmos.org/glycans/converter`；核心库 `github.com/glycoinfo/GlycanFormatConverter`；
  CLI `gitlab.com/glycoinfo/GlycanFormatConverter-cli`
- GlycanCompositionConverter、compo2wurcsUI（`https://glycosmos.gitlab.io/compo2wurcsui/`）、
  WURCSFramework、MolWURCS、wurcs2pic、SugarDrawer、GlycanBuilder2/2Web、PDB2Glycan、WURCSRDF
- **Glycoworkbench**：仓库 `https://gitlab.com/glycoinfo/glycoworkbench`，描述 "GlycoWorkbench is a software tool
  to assist the manual interpretation of MS data. The tool provides an easy to use graphical interface, a set of
  structural constituents, a collection of fragmentation types, and a broad list of annotation options."
- 数据库：GlyTouCan、GlyCosmos、GlycoNAVI、wwPDB、PubChem、**GlyGen**（"GlyGen is a data integration and
  dissemination project for carbohydrate and glycoconjugate related data…"）、CSDB

### W8 逐字要点（`SKILL.md` §2.3）

- `WURCS=` `<Version>` `/` `<Unit Count>` `/` `<UniqueRES List>` `/` `<RES Sequence>` `/` `<LIN List>`
- `<Unit Count>`: `<UniqueRES Count>`,`<RES Count>`,`<LIN Count>`；`<Uncertain LIN Count>`: `<LIN Count>` `+`
- `<UniqueRES>`: `[` `<ResidueCode>` `]`；`<ResidueCode>`: `<BackboneCode>` `_` `<MOD…>`
- `<BackboneCode>`: `<SkeletonCode>` `-` `<Anomeric Information>`
- `<MOD>`: `<LIP #1>` `-` … `-` `<MAP>`；`<LIP>`: `<Position>` `<Direction>` `<Star Index>`
- "plus `+` indicates that there may potentially be more than LIN Count linkages."

### W9 逐字要点

- `SkeletonCode` 长度 = 主链碳数（"a backbone with six CarbonDescriptors means a hexose"）
- CarbonDescriptor 表（部分）：`o` 醛（末端）、`h` 羟甲基（末端）、`A` 羧基（末端）、`m` 甲基（末端）、
  `O` 酮（非末端）、`1`/`2` 左/右手性羟基碳、`d` 亚甲基（脱氧）、`a` 半缩醛/半缩酮（异头中心）、
  `u`/`U` 醛或半缩醛/酮或半缩酮的合并表示
- `Anomeric Symbol`：α=`a`、β=`b`；`u`/`d` 为绝对立体描述（Haworth 上/下方向）
- 通配：`x`/`X` 表示未知；`<`…`>` 表示未知重复次数，且 "Currently, only one CarbonDescriptor can be in the
  `<` and `>`"

---

## 4. GlycanFormatConverter（官方编码互换工具）

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| F1 | https://github.com/glycoinfo/GlycanFormatConverter | 核心库仓库页 | 200（被导航栏截断） |
| F2 | https://raw.githubusercontent.com/glycoinfo/GlycanFormatConverter/master/README.md | README | **OK** |
| F3 | https://raw.githubusercontent.com/glycoinfo/GlycanFormatConverter/master/RESTRICTIONS.md | **官方限制** | **OK，全文 5 883 字节** |
| F4 | https://gitlab.com/glycoinfo/GlycanFormatConverter-cli/-/raw/master/README.md | **CLI 用法（命令来源）** | **OK，全文 4 634 字节** |
| F5 | https://api.glycosmos.org/glycanformatconverter/ | README 给出的 REST API 入口 | GET 返回 **200 但 0 字节**（推测为 POST 接口）；无请求体文档，未使用 |
| F6 | https://gitlab.com/glycoinfo/GlycanFormatConverter-cli | GitLab 仓库页 | 未单独抓取（用 F4 的 raw 版） |

### F2 逐字要点

- "GlycanFormatConverter is core library of glycan text conversion tools."；最新版本 2.8.2（README 标记）
- API 入口：`https://api.glycosmos.org/glycanformatconverter/`
- 引用：Bioinformatics. 2019 Jul 15;35(14):2434-2440. doi:10.1093/bioinformatics/bty990

### F4 逐字要点（`SKILL.md` §2.4 全部命令来源）

- 构建：`git clone https://gitlab.com/glycoinfo/GlycanFormatConverter-cli.git` →
  `cd GlycanFormatConverter-cli` → `mvn clean compile assembly:single`
- 调用：`java -jar ./target/GlycanFormatConverter-cli.jar -i <FORMAT> -e <FORMAT> -seq <SEQUENCE>`
- `-e/--export`：`IUPAC-Short|IUPAC-Condensed|IUPAC-Extended|GlycoCT|WURCS|GlycanWeb`
- `-i/--import`：`IUPAC-Condensed|IUPAC-Extended|GlycoCT|KCF|LinearCode|WURCS`
- 支持矩阵逐字（行=输入，列=输出）：WURCS 行导出 Extended/Condensed/Short、GlycoCT、GlycanWeb；
  IUPAC-Extended 行导出 Condensed/Short、WURCS、GlycanWeb；IUPAC-Condensed 行导出 Short、WURCS、GlycanWeb；
  KCF / LinearCode / GlycoCT 行均导出 Extended/Condensed/Short、WURCS、GlycanWeb。
  **GlycoCT 列的 GlycoCT 行为空、WURCS 列的 WURCS 行为空。**
- 版本历史：2.10.3.1（2024/05/09）… 0.1.0（2021/04/28）；2.10.2（2024/04/05）起 "Support stdin and file"
- 例 1（WURCS→IUPAC-Extended）与例 2（IUPAC-Extended→WURCS，管道 `| grep WURCS=2.0 | grep -v DEBUG`）逐字见该页。

### F3 逐字要点（`SKILL.md` §2.4 限制）

- IUPAC 输入含以下情形会被当异常并报转换错误：含 repeating units / cyclic units / cross-linked substituent /
  repeating units with cross-linked substituent / cyclic substituent in any monosaccharide /
  monosaccharide fragments / substituent fragments / monosaccharide modifications such as deoxy
- WURCS 通配：`WURCS=2.0/1,1,0/[AOOxxh]/1/`、`WURCS=2.0/1,1,0/[hXxh_2*C_4*OPO/3O/3=O]/1/`、
  `WURCS=2.0/1,1,0/[h21xxh]/1/` → 报 `This SkeletonCode partially contains the wild card (x or X).`
- 单价取代基支持矩阵（O-linked/N-linked/C-linked × Acyl/Ethyl/Methyl/Acethyl/Glycolyl/Sulfate/Formyl/…）

---

## 5. GlycoWorkbench

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| G1 | http://www.glyco-workbench.org/ | **任务描述给出的官方站点** | **DNS 解析失败**：`getaddrinfo ENOTFOUND www.glyco-workbench.org` |
| G2 | https://gitlab.com/glycoinfo/glycoworkbench | 现行官方仓库（W4 指向） | 200，title `glycoinfo / Glycoworkbench · GitLab` |
| G3 | https://gitlab.com/glycoinfo/glycoworkbench/-/raw/master/README.md | README（命令来源） | **OK，全文 2 933 字节** |

### G3 逐字要点

- 构建：`mvn clean package`
- 运行：`java -XstartOnFirstThread -jar ./target/glycoworkbench2-0.0.2-SNAPSHOT-jar-with-dependencies.jar`
- 兜底启动：`java -jar -Xmx300M eurocarb-glycoworkbench-1.0rc.jar`
- **"The GlycoWorkbench (GWB) manual can be accessed via the Help menu of GWB."**
- "## Web site * TODO:"（即官方站点尚未建立 → 解释了 G1 的 DNS 失败）
- 开发者：Masaaki Mastubara, Issaku Yamada；前版 Alessio Ceroni, Kai Maass, David Damerell
- 要求：Java 8+、maven 3.6+、≥1.3.0 需支持 SWT（Windows/Linux/macOS）

> 结论：GWB 的注释命令**官方文档未提供**（手册内置于 GUI）。`SKILL.md` §3.4 据此只给构建/启动命令。

---

## 6. Byonic（Protein Metrics / Dotmatics）

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| B1 | https://www.proteinmetrics.com/products/byonic/ | 产品页 | **OK，全文可读** |
| B2 | https://www.proteinmetrics.com/products/byonic | 同上（跟随 308 后） | OK |
| B3 | https://support.proteinmetrics.com/hc/en-us | Knowledge Base / Support | 未抓取（列为官方参数文档入口） |

### B1 逐字要点

- "Byonic is a full tandem mass spectrometry (MS/MS) search engine for comprehensive peptide and protein identification"
- Glycopeptide Search 原文："Identify glycopeptides without prior knowledge of glycan masses or glycosylation
  sites." / "Byonic scores and annotates multiple types of glycopeptide fragments to deduce the peptide carrier,
  glycan and modification site."
- 支持碎裂：CID、TOF-TOF、QTOF HCD、ETD/ECD、EThcD

> 结论：官方公开页面**没有命令行参数表**。`SKILL.md` §3.4 只描述能力，不给命令行，并标注
> 「官方文档未提供可直接执行的命令」。

---

## 7. pGlyco 系列（完整糖肽）

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| P1 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/README.md | pGlyco3 README | **OK** |
| P2 | https://api.github.com/repos/pFindStudio/pGlyco3/git/trees/main | 仓库文件树 | OK：`find_oxonium`、`gdb_files`、`glycan_db`、`glycoworkbench_gwp`、`mass_calc`、`scripts`、两个 User-Guide PDF |
| P3 | https://api.github.com/repos/pFindStudio/pGlyco3/contents/{scripts,mass_calc,find_oxonium,glycan_db} | 目录清单 | OK（`scripts/` 4 个脚本、`mass_calc/` 2 个文件、`find_oxonium/` 2 个文件、`glycan_db/generate_multi_site_gdb.py`） |
| P4 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/protein_site_analysis.py | 位点分析脚本 | **OK**（FDR 默认阈值、结果列名来源） |
| P5 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/pGlyco_to_skyline_ssl.py | Skyline 转换 | **OK**（usage 与 `%s-GP-FDR.txt`、`pGlyco.cfg` 键名来源） |
| P6 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/diagnostic-ion-checker.py | 诊断离子 | **OK**（usage 与 oxonium 表来源） |
| P7 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/mass_calc/chem2mass.py | 分子式→质量 | **OK**（usage 来源） |
| P8 | https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/find_oxonium/find_oxonium_ions.py | oxonium 峰型抽取 | **OK**（内部变量配置来源） |
| P9 | https://raw.githubusercontent.com/pFindStudio/pGlyco2/master/README.md | pGlyco2 README | **OK**（`pGlycoFDR.exe`、`gLabel`、`xtract_raw`、`pParse`、mzML 支持、RawFileReader 回退） |
| P10 | `pGlyco3-User-Guide.pdf`（仓库内） | 检索参数手册 | **未抓取**：PDF 不在可解析范围 |

### P1 逐字要点

- "Intact N- and O-glycopeptide search engine"
- license："When using pGlyco3 for the first time, a license applicaiton dialog will show. After filling all the
  reguired items and clicking "copy to clipboard" to copy the form, you can then paste the form on
  http://i.pfind.net/license/pGlyco3 to generate a license."
- 定量："For glycopeptide quantification, please use pGlycoQuant: https://github.com/Power-Quant/pGlycoQuant/releases"

### P4 逐字要点

```
glycan_fdr_thres = 0.01
peptide_fdr_thres = 0.1
```
列名：`GlycanFDR`、`PeptideFDR`、`TotalFDR`、`GlySpec`、`RawName`、`Scan`、`ETDScan`、`Peptide`、`GlySite`、
`Mod`、`Glycan(...)`（脚本以 `name.startswith('Glycan(')` 找该列）、`MonoArea`、`IsotopeArea`、`Proteins`。

### P5 逐字要点

```
Usage:
python pGlyco_to_skyline_ssl.py C:/output/folder/pGlyco.cfg
or
python pGlyco_to_skyline_ssl.py C:/output/folder/pGlycoDB-GP-FDR.txt raw_folder
```
cfg 键：`file=`、`output_dir=`、`pGlyco_type=`；结果文件 `os.path.join(output_dir, '%s-GP-FDR.txt'%pGlycoType)`。

### P6 逐字要点

```
Usage:
    python diagnostic-ion-checker.py -mgf mgf_containing_folder -marker 204.087,138.055
Output:
    marker-ion.csv in the mgf_containing_folder
```
并给 17 行 marker 表（109.028 … 673.230），`SKILL.md` §3.3 逐字照录。

### P7 逐字要点

```
Usage: python [-f formula] [-ini inifile -formula_pos n -mass_pos m] [-r replacement]
marker 138 formula: python -f C(7)H(7)N(1)O(2) -r N~15N
```

### P8 逐字要点

脚本内配置变量：`scan_txt`、`pf2`、`output`、`max_mz = 300`、`min_rel_inten = 0.1`、`bin_per_Da = 0.1`；
读取 `<pf2>idx` 索引（`struct.unpack('2i')`），按 scan 抽峰。

---

## 8. GlyGen

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| N1 | https://www.glygen.org/ | 首页 | 200，SPA 壳（仅 `meta description` 可读） |
| N2 | https://www.glygen.org/glycan/G00051MO | 结构页 | 200，SPA 壳（2481 字节，无正文） |
| N3 | https://www.glygen.org/datatypes | 数据类型页 | 200，SPA 壳 |
| N4 | https://api.glygen.org/glycan/detail/G00051MO/ | 结构 JSON | **OK（200，77 202 字节）**：返回 `glytoucan.glytoucan_ac`/`glytoucan_url`、`mass`、`number_monosaccharides`、`iupac`、`wurcs`、`glycoct`、`species[]` |
| N5 | https://api.glygen.org/glycan/list/ | 列表接口试探 | **HTTP 500** |

### N1 逐字要点

`<meta name="description" content="GlyGen is a data integration and dissemination project for carbohydrate and
glycoconjugate related data.">`

> 关于 N4：**官方站点未提供该端点的文字文档**（站点为 SPA）。`SKILL.md` §2.5 只把
> `https://api.glygen.org/` 列为入口，并说明 N4 是「实测可用、官方未文档化」的端点，不作为命令依据。

---

## 9. GlyCosmos

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| S1 | https://glycosmos.org/ | 门户 | **超时**（30 s） |
| S2 | https://glycosmos.org/glycans/converter | 转换器页（W4 指向） | 200（33 231 字节）但为 SPA 壳，无可读正文 |
| S3 | https://api.glycosmos.org/ | API 文档站 | 200，但只是 Wiki.js 外壳（5 435 字节），无正文 |
| S4 | https://api.glycosmos.org/glycans/composition 、`/glycans/glytoucan/G00051MO`、`/sparql?...` | 端点试探 | 三者都返回**同一 Wiki.js 外壳页**（非 JSON），说明这些路径不是官方 API 路径 |
| S5 | https://ts.glycosmos.org/sparql | SPARQL endpoint | **200，OpenLink Virtuoso SPARQL Query Editor**（端点存活） |
| S6 | https://glyconavi.org/Tools/tool/gfc.php | W4 列的 GlycanFormatConverter Web | **HTTP 308 Permanent Redirect**（未跟随到正文）；`SKILL.md` 未引用该页作为命令来源 |

---

## 10. 其它糖资源

| # | URL | 内容 | 抓取 |
|---|---|---|---|
| O1 | https://www.functionalglycomics.org/ | CFG 首页 | 200，title `CFG : Home` |
| O2 | https://www.functionalglycomics.org/glycan-array | **CFG Glycan Array 归档** | **OK，全文可读**（6035 条实验、版本与类别选项逐字） |
| O3 | https://www.functionalglycomics.org/static/consortium/Nomenclature.shtml | CFG 命名法页（任务描述关注点） | **HTTP 404** |
| O4 | https://www.functionalglycomics.org/glycomics/nomenclature | 同上（另一路径） | **HTTP 404** |
| O5 | https://www.functionalglycomics.org/nomenclature | 同上（另一路径） | **HTTP 404** |
| O6 | https://glycostore.org/ | GlycoStore 首页 | **OK（部分）**：可读单位词表 `HPLC`、`UPLC_2-AB`、`UPLC_Procainamide`、`CE`、`RP`、`PGC`，栏目 `Retention Times/Units`、`GlycoCT Structure`、`MIRAGE LC` |
| O7 | https://glycostore.org/about | About | **未取到正文**：返回 "One moment, please... Loader Please wait while your request is being verified..." 反爬页 |
| O8 | https://glycobase.nibrt.ie/ | NIBRT GlycoBase | **失败**：`基础连接已经关闭: 发送时发生错误`（TLS 层失败） |
| O9 | https://acgg.asia/lfdb/ | ACGG Lectin Frontier DB | **HTTP 404** |
| O10 | https://glycosciences.de/ | glycosciences.de（任务描述候选） | **两次失败**：一次 `Invoke-WebRequest` 操作超时、一次 `web_fetch` `TypeError: fetch failed` |
| O11 | https://international.neb.com/products/p0704-pngase-f | PNGase F 产品页（PNGase F 释放口径） | **HTTP 403 + Cloudflare 人机校验页**（web_fetch 与 pwsh 均 403） |

### O2 逐字要点

- 字段：`ID`、`Primary Screen ID`、`Request`、`Sample`、`Description`、`Category`、`Glycan Array`、
  `Investigator`、`Conclusive`
- `Category`（逐字选项）：`C-type Lectin`、`iTypeLectins`、`Other Animal Lectins`、`otherAnimalLectin`、
  `plantLectins`、`Antibodies and Serum samples`、`Pathogens (bacteria, viruses) and Microbial Lectin`、
  `sTypeLectins`、`notClassified`、`cTypeLectins`、`other antiBodies`
- `Glycan Array`（逐字选项）：`PA_v52`、`PA_v51`、`PA_v5`、`PA_v42`、`PA_v41`、`PA_v4`、`PA_v32`、`PA_v31`、
  `PA_v3`、`PA_v21`、`PA_v2`、`PA_v1`、`PA_v0`、`GLYCAN_v3`、`GLYCAN_v2`、`GLYCAN_v1`、`BACT_v1`
- `Conclusive`：`Data` / `Inconclusive`；页面底部 "Showing 1 to 10 of 6035 Results"
- 站点维护方："The CFG website is maintained by the National Center for Functional Glycomics"

---

## 11. 统计

### 11.1 正文（`SKILL.md`）引用的官方 URL

机器提取结果：**28 个 URL 字面量 → 27 个独立官方 URL**（`.../GlycanFormatConverter-cli.git` 与
`.../GlycanFormatConverter-cli` 是同一仓库的 clone 写法，计 1 个）。

| 组 | URL 数 | 明细 |
|---|---|---|
| GlyTouCan code 站 | 3 | `/`（root）、`/system/cli/`、`/rdf-ontology/sparql-queries/` |
| GlyTouCan 主站 / SPARQL | 3 | `glytoucan.org/`、`glytoucan.org/Structures/Glycans/G66357CN`、`ts.glytoucan.org/sparql` |
| GlycoCT | 1 | `github.com/glycoinfo/GlycoCT` |
| WURCS | 1 | `github.com/glycoinfo/WURCS/wiki` |
| GlycanFormatConverter | 3 | `github.com/glycoinfo/GlycanFormatConverter`、`gitlab.com/glycoinfo/GlycanFormatConverter-cli`、`api.glycosmos.org/glycanformatconverter/` |
| GlycoWorkbench | 1 | `gitlab.com/glycoinfo/glycoworkbench` |
| Byonic | 2 | 产品页、Knowledge Base |
| pGlyco | 5 | pGlyco3 仓库、pGlyco2 仓库、pGlycoQuant releases、`i.pfind.net/license/pGlyco3`、`raw…/mass_calc/chem2mass.py` |
| GlyGen | 2 | `www.glygen.org/`、`api.glygen.org/` |
| GlyCosmos | 2 | `glycosmos.org/`、`ts.glycosmos.org/sparql` |
| CFG | 1 | `functionalglycomics.org/glycan-array` |
| GlycoStore | 1 | `glycostore.org/` |
| GlycoNAVI | 1 | `glyconavi.org/` |
| CSDB | 1 | `csdb.glycoscience.ru/` |
| **合计** | **27** | |

> `references/nomenclature.md` 另引用的 URL 都落在这 27 个之内（`sparql-queries`、CLI README 所在仓库、
> RESTRICTIONS 所在仓库、pGlyco 脚本、GlycoStore、CFG、GlyGen API），未新增独立来源。

### 11.2 本文件（`official-docs.md`）记录的 URL 条目

**74 个条目**：T1–T16 共 16、C1–C5 共 5、W1–W9 共 9、F1–F6 共 6、G1–G3 共 3、B1–B3 共 3、
P1–P10 共 10、N1–N5 共 5、S1–S6 共 6、O1–O11 共 11。条目里含同一 URL 的替代抓取通道与探测试探路径，
故条目数大于正文实际引用的 27 个独立 URL。

> 计数说明：pGlyco 的 5 个 raw 脚本（`protein_site_analysis.py`、`pGlyco_to_skyline_ssl.py`、
> `diagnostic-ion-checker.py`、`chem2mass.py`、`find_oxonium_ions.py`）各自是一个 URL 条目，但在
> 「独立官方站点」口径下属同一仓库，避免把同一仓库拆成 5 个「官方文档」。

**抓取状态汇总**

- 直接抓取成功且正文可读：**31 个 URL**
- 200 但只是 SPA/JS 外壳、无正文：GlyTouCan 主站（T1、T2、T3）、GlyGen（N1、N2、N3）、
  GlyCosmos（S2、S3、S4）、GitHub 仓库页（C1、W1、F1）、GlyTouCan wiki 页（T11）
- 明确失败/不可用：O3、O4、O5（CFG 命名法 404）、O7（反爬）、O8（TLS）、O9（404）、O10（超时/fetch 失败）、
  O11（403 Cloudflare）、G1（DNS 不存在）、C5/P10（PDF 不可解析）、C3（404）、C4（403）、N5（500）、
  T15/T16（404）、S1（超时）、S6（308）、F5（200 但 0 字节）

**抓取失败清单（供后续复核）**

1. `https://glytoucan.org/` → 200，SPA 加载壳（`L O A D I N G`），无正文
2. `https://glytoucan.org/Documentation` → 200，同上（任务描述指定的文档入口实际不可读）
3. `https://glytoucan.org/Structures/Glycans/G00051MO` → 200，SPA 壳
4. `https://glytoucan.org/api/v2/glycans/G00051MO` → HTTP 404
5. `https://api.glytoucan.org/`、`/glycans/G00051MO`、`/glycan/G00051MO` → HTTP 404（三处）
6. `https://github.com/glytoucan/api/wiki` → 200 但被导航栏占满，正文未取到
7. `https://api.github.com/repos/glycoinfo/GlycoCT/git/trees/master` → HTTP 404
8. `https://api.github.com/repos/glycoinfo/GlycoCT/branches` → HTTP 403
9. `https://api.github.com/repos/glycoinfo/GlycoCT/contents/` → HTTP 403
10. `https://raw.githubusercontent.com/...`（经 `web_fetch`）→ `TypeError: fetch failed`（改 pwsh 成功）
11. `https://cdn.jsdelivr.net/gh/...` → `cross-origin redirect to https://raw.githubusercontent.com is not followed automatically`
12. `https://github.com/glycoinfo/GlycoCT`、`https://github.com/glycoinfo/wurcs`、`https://github.com/glycoinfo/GlycanFormatConverter` → 200 但正文被导航栏截断（改用 raw）
13. `https://www.glygen.org/`、`/glycan/G00051MO`、`/datatypes` → 200，SPA 壳
14. `https://api.glygen.org/glycan/list/` → HTTP 500
15. `https://glycosmos.org/` → 超时
16. `https://glycosmos.org/glycans/converter` → 200，SPA 壳
17. `https://api.glycosmos.org/`、`/glycans/composition` 等 → 200，仅 Wiki.js 外壳
18. `https://api.glycosmos.org/glycanformatconverter/` → 200 但 0 字节（无请求体文档）
19. `https://glyconavi.org/Tools/tool/gfc.php` → HTTP 308
20. `http://www.glyco-workbench.org/` → DNS `ENOTFOUND`
21. `https://glycosciences.de/` → 操作超时 / `TypeError: fetch failed`
22. `https://international.neb.com/products/p0704-pngase-f` → HTTP 403 + Cloudflare
23. `https://glycobase.nibrt.ie/` → TLS 连接失败
24. `https://acgg.asia/lfdb/` → HTTP 404
25. `https://glycostore.org/about` → 反爬验证页
26. `https://www.functionalglycomics.org/static/consortium/Nomenclature.shtml` → HTTP 404
27. `https://www.functionalglycomics.org/glycomics/nomenclature` → HTTP 404
28. `https://www.functionalglycomics.org/nomenclature` → HTTP 404
29. `pGlyco3-User-Guide.pdf`、`GlycoCT.pdf` → PDF 本体未解析（不在可解析范围）

> 上列 29 项中，凡影响「可执行命令」的（G1、O11、O8、O9、C5、P10、S1）已在 `SKILL.md` 对应位置
> 显式标注「官方文档未提供可直接执行的命令」，未用自造脚本替代。
