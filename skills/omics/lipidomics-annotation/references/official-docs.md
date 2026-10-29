# 官方文档清单（抓取状态 + 逐字要点）

本文件记录本技能所有命令/参数/函数名的来源。**每条都标注抓取结果**；抓不到或页面已下线的，明确写出来，不补编。

抓取时间：2026-10-29（Asia/Shanghai）。

---

## A. lipidr（Bioconductor）

### A.1 候选 URL 与实际不一致（重要）

| URL | 状态 | 说明 |
|---|---|---|
| `https://bioconductor.org/packages/release/bioc/vignettes/lipidr/inst/doc/lipidr.html` | **HTTP 404** | 用户给定的候选链接文件名错误。Bioconductor 返回 "Page Not Found"。 |
| `https://bioconductor.org/packages/lipidr/` | 抓取失败（fetch failed） | 换用下列镜像与官方 vignette 源文。 |
| `https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.19/bioc/vignettes/lipidr/inst/doc/workflow.html` | **HTTP 200** | 正确的 vignette 文件名是 **`workflow.html`**；返回 HTML 但正文被工具截断，故关键代码改用官方 `.Rmd` 源文逐字核对。 |
| `https://raw.githubusercontent.com/ahmohamed/lipidr/f5fb8d5421b8341e76f66f545154bae01e0aa62d/vignettes/workflow.Rmd` | **HTTP 200** | 官方 vignette 源文（作者 Ahmed Mohamed, QIMR Berghofer），本技能 4.x 节的全部代码逐字取自此处。 |
| `https://ahmohamed.github.io/lipidr/reference/index.html` | 302 → `https://www.lipidr.org` | 站点已迁移。 |
| `https://www.lipidr.org/reference/index.html` | **HTTP 200** | 官方函数参考索引，版本标注 **2.15.1**。 |

### A.2 官方函数参考页（全部 HTTP 200，逐条抓取）

| 页面 | URL | 本技能引用它的哪一点 |
|---|---|---|
| Reference index | <https://www.lipidr.org/reference/index.html> | 分组：Input data / Preprocessing / QC & viz / Univariate / Multivariate / Enrichment / **Lipid-centric analysis** / Object structure / Interactive |
| `read_skyline` | <https://www.lipidr.org/reference/read_skyline.html> | `read_skyline(files)`；返回 LipidomicsExperiment；rowData 列名（`Molecule`、`clean_name`、`ambig`、`not_matched`、`istd`、`class_stub`、`chain1..4`、`l_*`、`s_*`、`total_cl`、`total_cs`、`Class`） |
| `as_lipidomics_experiment` | <https://www.lipidr.org/reference/as_lipidomics_experiment.html> | `as_lipidomics_experiment(df, logged = FALSE, normalized = FALSE)`；首列或 rownames 放脂质名；有重复行才不算 summarized |
| `add_sample_annotation` | <https://www.lipidr.org/reference/add_sample_annotation.html> | `add_sample_annotation(data, annot_file)`；注释文件"CSV file or a data.frame with at least 2 columns, sample names & group(s)" |
| `summarize_transitions` | <https://www.lipidr.org/reference/summarize_transitions.html> | `summarize_transitions(data, method = c("max", "average"))`，默认 `max` |
| `normalize_pqn` | <https://www.lipidr.org/reference/normalize_pqn.html> | `normalize_pqn(data, measure = "Area", exclude = "blank", log = TRUE)`；参考谱="average lipid abundance of all samples (excluding blanks)"；引用 Dieterle 2006 *Anal. Chem.* 78(13):4281-4290 |
| `normalize_istd` | <https://www.lipidr.org/reference/normalize_istd.html> | 类内内标归一化（"corrects lipid class-specific variations"）；缺对应内标时用"average of all measured internal standards" |
| `filter_by_cv` | <https://www.lipidr.org/reference/filter_by_cv.html> | `filter_by_cv(data, cv.cutoff = 20, measure = "Area")` |
| `mva` | <https://www.lipidr.org/reference/mva.html> | `mva(data, measure="Area", method=c("PCA","PCoA","OPLS","OPLS-DA"), group_col=NULL, groups=NULL, ...)`；`plot_mva(mvaresults, components=c(1,2), color_by=NULL, ellipse=TRUE, hotelling=TRUE)`；`plot_mva_loadings(..., top.n=nrow(mvaresults$loadings))`；`top_lipids(mvaresults, top.n=10)`；blank 按 TIC 自动排除；缺失按全样本平均强度填补 |
| `de_analysis` | <https://www.lipidr.org/reference/de_analysis.html> | `de_analysis(data, ..., measure="Area", group_col=NULL)`；`de_design(data, design, ..., coef=NULL, measure="Area")`；`significant_molecules(de.results, p.cutoff=0.05, logFC.cutoff=1)`；`plot_results_volcano(de.results, show.labels=TRUE)`；输入"should be normalized and log2 transformed"；对比式传给 `limma::makeContrasts`；`logFC.cutoff` 在多组比较中被忽略 |
| `lsea` | <https://www.lipidr.org/reference/lsea.html> | `lsea(de.results, rank.by=c("logFC","P.Value","adj.P.Val"), min_size=2, ...)`；`significant_lipidsets(enrich.results, p.cutoff=0.05, size.cutoff=2)`；`plot_class_enrichment(de.results, significant.sets, measure="logFC")`；`plot_enrichment(de.results, significant.sets, annotation=c("class","length","unsat"), measure="logFC")`；`...` 透传 `fgsea::fgsea()` |
| `gen_lipidsets` | <https://www.lipidr.org/reference/gen_lipidsets.html> | `gen_lipidsets(molecules, min_size=2)`；集合命名 `Class_PC` / `total_cl_34` / `total_cs_2` |
| `plot_chain_distribution` | <https://www.lipidr.org/reference/plot_chain_distribution.html> | `plot_chain_distribution(de_results, contrast=NULL, measure="logFC")`；同链属性多分子取均值并标出分子数 |
| `plot_trend` | <https://www.lipidr.org/reference/plot_trend.html> | `plot_trend(de_results, annotation=c("length","unsat"))`；每个对比一条回归线；示例输出显示 `geom_smooth()` method = 'loess'；返回值仅 ggplot |
| `annotate_lipids` | <https://www.lipidr.org/reference/annotate_lipids.html> | `annotate_lipids(molecules, no_match=c("warn","remove","ignore"))`；接受 `'class xx:x/yy:y'` 与 `'class zz:z'` 两种写法；返回 21 列 |
| `non_parsed_molecules` / `remove_non_parsed_molecules` / `update_molecule_names` | 见 index 同名锚点 | 命名解析失败的处理链 |

### A.3 必须在报告里更正的三点

1. **`dim_analysis` 不存在**。官方多变量函数是 `mva()` / `plot_mva()` / `plot_mva_loadings()` / `top_lipids()`。
2. **`liplevel_de` 不存在**。类别层面的差异 = `lsea()` + `significant_lipidsets()` + `plot_class_enrichment()`。
3. **`chain_de` 不存在**。碳链/双键层面的差异 = `plot_chain_distribution()` + `plot_trend()` + `plot_enrichment(annotation="length"/"unsat")`。

检索佐证：对 `"liplevel_de"` / `"chain_de"` 做过独立检索，未命中任何 R 包文档；`lipidr` 官方参考索引（A.2 首行）逐条列出全部导出函数，其中不包含这三个名字。

---

## B. LIPID MAPS

| 页面 | URL | 状态 | 用途 |
|---|---|---|---|
| 分类系统（八类别） | <https://www.lipidmaps.org/resources/education/classification> | HTTP 200 | 八类别定义、亚类层级、引用文献（Fahy 2005 JLR 46:839；Fahy 2009 JLR 50:S9） |
| 脂质命名 | <https://www.lipidmaps.org/lipid_nomenclature> | HTTP 200 | shorthand 速记 13 条规则（sn、`O-`/`P-`、`d`/`t`、E/Z、R/S、lyso） |
| 结构信息层级 | <https://www.lipidmaps.org/lipid_nomenclature/rules/hierarchy> | HTTP 200 | 八级层级（Species → Complete structure），`_` vs `/` 的官方定义 |
| 命名工具 | <https://www.lipidmaps.org/resources/tools/nomenclature> | HTTP 200 | RefMet 标准化（`lipid_std_form`、`lipid_std_mz_form`）、LipidLynxX |
| MS 分析工具 | <https://www.lipidmaps.org/resources/tools/ms> | HTTP 200 | `moverz`/bulk_search/masscalc/Kendrick/GP-GL-SP in-silico MS2 等入口 |
| REST 服务 | <https://www.lipidmaps.org/resources/rest> | HTTP 200 | 三段式 URL 结构、compound 全部 output item、全部示例 URL、`moverz` 的 ion-type 取值 |
| LMSD 总览 | <https://www.lipidmaps.org/databases/lmsd/overview> | 链接存在于站内导航 | 数据库入口 |
| LMSD 分类浏览 | <https://www.lipidmaps.org/databases/lmsd/browse> | 链接存在于站内导航 | 分类树 |
| 分类更新记录 | <https://www.lipidmaps.org/databases/lmsd/classification_updates> | 链接存在（页面标注 2024-02-20 更新） | 版本留痕 |
| LipidBlast / 工具指南 | <https://lipidmaps.org/resources/tools?page=flow_chart> | 链接存在 | 方法选择向导 |

> 尝试过的错误 URL：`https://www.lipidmaps.org/resources/classification.php` → **404**（已并入 education/classification）。
> `https://www.lipidmaps.org/resources/lipid_web` → HTTP 200 但正文为空壳（导航页），不作依据。

### B.1 可直接执行的 LIPID MAPS 命令（逐字）

```
# m/z 前体离子检索（虚拟库 LIPIDS）
https://www.lipidmaps.org/rest/moverz/LIPIDS/635.52/M+H/0.5/txt
https://www.lipidmaps.org/rest/moverz/LIPIDS/513.45/M-2H/0.2/txt

# 化合物字段
https://www.lipidmaps.org/rest/compound/lm_id/LMFA01010001/name
https://www.lipidmaps.org/rest/compound/lm_id/LMFA01010001/all
https://www.lipidmaps.org/rest/compound/lm_id/LMFA01010001/all/txt
https://www.lipidmaps.org/rest/compound/pubchem_cid/985/smiles
https://www.lipidmaps.org/rest/compound/inchi_key/IPCSVZSSVZVIGE-UHFFFAOYSA-N/sys_name
https://www.lipidmaps.org/rest/compound/inchi_key/IPCSVZSSVZVIGE-UHFFFAOYSA-N/physchem
https://www.lipidmaps.org/rest/compound/formula/C20H34O/all
https://www.lipidmaps.org/rest/compound/pubchem_cid/985/classification

# 按缩写 / 链组成 / 批量下载
https://www.lipidmaps.org/rest/compound/abbrev/PC(16:0/20:4(5Z,8Z,11Z,14Z))/structure
https://www.lipidmaps.org/rest/compound/abbrev/PA(38:0)/all/txt
https://www.lipidmaps.org/rest/compound/abbrev_chains/PC(16:0_18:0)/all/txt
https://www.lipidmaps.org/rest/compound/lm_id/LMFA0301/all/download
https://www.lipidmaps.org/rest/compound/lm_id/LMFA03/all/download
https://www.lipidmaps.org/rest/compound/lm_id/LMGP/all/download
https://www.lipidmaps.org/rest/compound/lm_id/LM/all/download

# 基因 / 蛋白上下文
https://www.lipidmaps.org/rest/gene/gene_symbol/acaca/all
https://www.lipidmaps.org/rest/gene/gene_id/31/gene_name
https://www.lipidmaps.org/rest/protein/uniprot_id/Q13085/all
https://www.lipidmaps.org/rest/protein/gene_id/19/all
https://www.lipidmaps.org/rest/protein/refseq_id/NP_005493/mrna_id
```

来源页：<https://www.lipidmaps.org/resources/rest>（"Examples | Example URL" 表，逐字复制）

---

## C. SwissLipids

| 项 | URL / 值 | 状态 |
|---|---|---|
| 主站 | <https://www.swisslipids.org/> | HTTP 200（SPA；导航含 Browse 脂质类别 / 脂质 analytes、ID Mapping、Downloads、API） |
| SPARQL 端点 | `https://sparql.swisslipids.org/sparql/` | 由官方示例页 "Use at" 字段给出 |
| 官方 SPARQL 示例索引（39 条） | <https://sib-swiss.github.io/sparql-examples/examples/SwissLipids/> | HTTP 200 |
| 示例 14（LIPID MAPS ID → SwissLipids + ChEBI） | <https://sib-swiss.github.io/sparql-examples/examples/SwissLipids/14.html> | HTTP 200，查询语句逐字取用 |
| 其他相关示例 | `/examples/SwissLipids/1.html`（类别与标签）、`/9.html`（LIPID MAPS→SwissLipids）、`/11.html`（HMDB→SwissLipids）、`/13.html`（ChEBI→SwissLipids）、`/15.html`（LipidX→SwissLipids）、`/35.html`（按 sn1 脂肪酸组分筛脂质）、`/7.html`（species→isomeric subspecies） | 均为索引页列出的官方示例 |
| API 文档页 | `https://www.swisslipids.org/api/index.html` | **HTTP 404**（不存在）；API 说明在站点 SPA 的 `#/api` 路由内，未能静态抓取 |

---

## D. MS-DIAL

| 项 | URL | 状态 |
|---|---|---|
| 用户给定候选：`http://prime.psc.riken.jp/compms/msdial/main.html` | — | **fetch failed（不可达）** |
| 现行官方主站 | <https://systemsomicslab.github.io/compms/msdial/main.html> | HTTP 200 |
| 注释置信码（annotation code） | <https://systemsomicslab.github.io/compms/msdial/annotationcode.html> | HTTP 200；含 lipidomics / metabolomics / GC-MS 三套码表与 RT/RI 阈值 |
| 脂质命名与加合物 | <https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html> | HTTP 200；"Major adduct abbreviation"表 + "Lipid subclass nomenclature"大表（含 ESI± 首选加合物） |
| FAQ | <https://systemsomicslab.github.io/compms/msdial/faq.html> | 链接存在于主站导航 |
| Console App 教程 | <https://systemsomicslab.github.io/compms/msdial/consoleapp.html> | 链接存在（MS-DIAL4） |
| MS-DIAL5 教程 | <https://systemsomicslab.github.io/msdial5tutorial/> | 链接存在 |
| MS-DIAL4 教程 | <https://systemsomicslab.github.io/mtbinfo.github.io/MS-DIAL/tutorial> | 链接存在 |
| 源码/发行 | <https://github.com/systemsomicslab/MsdialWorkbench>、`/releases` | 链接存在 |
| 谱库（MSP/模板） | 主页 `#MSP` 段：Zenodo 记录 10951913 / 10952423 / 13261737 / 10953284 | 链接存在（`MSDIAL-TandemMassSpectralAtlas-VS69-Pos.msp` 等） |
| CCS 参考库 | AllCCS <http://allccs.zhulab.cn/>；PNNL <https://metabolomics.pnnl.gov/ccs/> | 主页链接 |

### D.1 官方页给出的阈值（逐字）

- 脂质组 / 代谢组（LC-IM-MS/MS、LC-MS/MS）：「RT match should be equal to 0.5 min or less.」
- GC-MS：「RT match should be equal to 0.1 min or less.」「Kovats RI match should be equal to 20 or less.」「Fiehn RI match should be equal to 2000 or less.」
- LC-MS/MS 脂质组注记：「"lipid acyl position resolved" is not officially supported yet.」

---

## E. LipidFinder

| 项 | URL / 值 | 状态 |
|---|---|---|
| 用户给定候选：`https://lipidfinder.github.io/` | — | **HTTP 404**（"There isn't a GitHub Pages site here."） |
| 官方工具页（论文给出） | `http://lipidmaps.org/resources/tools/lipidfinder` | **fetch failed（超时）** |
| 搜索命中的旧域 | `https://www.dev.lipidmaps.org/resources/tools/lipidfinder/` | **DNS 不存在（getaddrinfo ENOTFOUND）** |
| 官方论文（含 Availability） | <https://pmc.ncbi.nlm.nih.gov/articles/PMC8208733/> | HTTP 200；doi:10.1093/bioinformatics/btaa856 |
| 官方代码库（论文给出） | <https://github.com/ODonnell-Lipidomics/LipidFinder> | 页面抓取失败；`raw.githubusercontent.com/.../master/README.md` 亦失败 |
| 前作 | Fahy E. et al. (2019) *Bioinformatics* 35:685–687, doi:10.1093/bioinformatics/bty679 | 论文参考文献 |

**结论**：LipidFinder 的**命令行语法在本环境不可得**。可按官方论文引用的实现事实只有：Python 2.7 / 3.3+、JSON 配置、CSV（PeakFilter、Amalgamator）与 XLS/XLSX（MS Search）、PDF + Jupyter 用户手册、模块构成（去伪影 / 同位素删除 / target–decoy FDR / 三库 bulk structure profiling）。故本技能对该工具**只写流程与判据**。

---

## F. MSI 报告标准

| 项 | 值 | 校验方式 |
|---|---|---|
| 文献 | Sumner L.W. et al. "Proposed minimum reporting standards for chemical analysis Chemical Analysis Working Group (CAWG) Metabolomics Standards Initiative (MSI)", *Metabolomics* 2007;3(3):211–221 | Europe PMC REST 检索 `DOI:"10.1007/s11306-007-0082-2"` → hitCount=1，PMID 24039616，PMCID PMC3772505 |
| DOI | 10.1007/s11306-007-0082-2 | 同上 |
| 全文 | <https://pmc.ncbi.nlm.nih.gov/articles/PMC3772505/> | HTTP 200 |
| 与本技能相关的章节 | §2.9 "Proposed minimum metadata relative to metabolite identification" | 抓取时该节在截断处之前，正文可确认其存在与主题；四级（Level 1–4）的具体措辞未逐字取到，故 SKILL.md 用通行口径描述并标注为"业界通用口径"，同时给出**可核查的替代物**——MS-DIAL 三位注释码（D.1） |

---

## G. 本包 MCP 工具（源码依据，非外部文档）

| 工具 | 源码位置 | 实现细节（逐字） |
|---|---|---|
| `chemistry_pubchem_search` | `mcp/biomedical_mcp.py` L845–847（注册）、L640–646（实现） | 请求 `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/{namespace}/{query}/cids/JSON`；返回 `{query, cids, note}` |
| `chemistry_pubchem_properties` | 同文件 L848–849、L649–654 | 请求 `.../compound/cid/{cid}/property/MolecularFormula,MolecularWeight,IsomericSMILES,IUPACName/JSON`；返回首行属性 |
| `chembl_compound_search` | 同文件 L742–743、L200 起 | 按名称搜 ChEMBL，返回 ChEMBL ID / SMILES / 研发阶段 |

---

## H. 汇总：本技能引用的官方 URL 数

- lipidr：1 个索引页 + 14 个函数/文档页 + 1 个 vignette 源文 + 1 个 Bioconductor 镜像 = **17**
- LIPID MAPS：**9**（classification、nomenclature、hierarchy、tools/nomenclature、tools/ms、rest、lmsd/overview、lmsd/browse、classification_updates）+ 1 个 flow_chart = 10
- SwissLipids：**3**（主站、示例索引、示例 14）+ 端点 1 = 4
- MS-DIAL：**3** 已抓取（main、annotationcode、lipidnomenclature）+ 4 个引用页（faq、consoleapp、msdial5tutorial、MS-DIAL4 tutorial）= 7
- LipidFinder：**2**（PMC 论文、GitHub 仓库）+ 1 个不可达工具页 = 3
- MSI：**2**（PMC 全文、DOI）
- 合计唯一外部官方 URL：**约 30 个**（其中 4 个确认为不可用：bioc 的 `lipidr.html`、`swisslipids.org/api/index.html`、`lipidfinder.github.io`、`prime.psc.riken.jp`）
