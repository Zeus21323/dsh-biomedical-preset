# 生物医学模式 · dsh-biomedical-preset

DeepSeek Harness 的 agent 预设（bundle）。它不是"给通用助手加个提示词"，而是一套**自持**的生物医学研究装配：身份与纪律、执行工具、603 个技能（34 个功能分类，可在设置里逐类开关）、51 个数据源 MCP 工具、并发闸、交付通道，全部装在这一个包里，不引用任何外部插件目录。

- 心智模型：**MCP 负责取数据，Skill 负责选方法与执行流程**，persona 负责纪律与判断。
- 已验证：市场索引通过官方 `@deepseek-ai/dsh-plugin-market-index` 校验；`npm pack` 产物 2222 文件 / 4.9 MB（packed）/ 19.5 MB（unpacked）；本机预设 `fiberPhase: active`。

---

## 目录

- [安装](#安装)
- [装配结构](#装配结构)
- [技能清单（603，34 个功能分类）](#技能清单60334-个功能分类)
- [MCP 工具清单（51）](#mcp-工具清单51)
- [并发与资源约束](#并发与资源约束)
- [平台要求](#平台要求)
- [仓库结构](#仓库结构)
- [更新与发版](#更新与发版)

---

## 安装

### 从插件市场

1. **插件** → **更多** → 启用 **自定义插件市场**；
2. **发现** → **添加索引源**，填入：
   ```
   https://raw.githubusercontent.com/Zeus21323/dsh-biomedical-preset/main/market/index.json
   ```
3. 安装 **Biomedical Mode**；
4. 新建会话时在模式选择器里选「生物医学模式」。

### 从 Git 直接安装

```sh
dsh plugin --profile desktop add git+https://github.com/Zeus21323/dsh-biomedical-preset.git#<40位commit>
```

或让 agent 用 `plugin_manager` 的 `install_bundle` 安装该 spec。Git 条目必须 pin 完整 40 位 commit，tag 与短 SHA 会被索引校验拒绝。

### 本地开发

```sh
git clone https://github.com/Zeus21323/dsh-biomedical-preset
```

用 `plugin_manager` `install_bundle` 指向该目录（`link:` 安装，改文件即时生效）。persona 与 preset composition 在**会话创建时**读取，所以改完要重新激活预设（`set_plugin` 先 false 再 true）并新开会话才生效。

---

## 装配结构

`cordis.patch.yml` 在本包内声明 28 个插件行（22 个启用 + 6 个默认禁用、仅在 picker 故障时手动打开的 `skill-filesystem` 兜底行），另在 profile 里插 2 行（`preset-biomedical` 本预设 + `biomedical-skill-settings` 设置页）：

| 层 | 插件行 | 作用 |
|---|---|---|
| 身份 | `persona` | 生物医学研究者 prefix（13 小节工作规范）+ 8 条结论纪律 suffix |
| 身份 | `agent-instructions` | 读取项目 `AGENTS.md`（课题组分析规范走这里） |
| 身份 | `time-context` | 时间锚（"近三年"、随访窗口） |
| 执行 | `tool-pwsh` / `tool-bash` | 按平台二选一，跑 python/R/conda/比对工具 |
| 执行 | `tool-fs`、`tool-fs-search` | 读写脚本、检索大表、grep 参数文件 |
| 执行 | `tool-jobs` | 后台长任务（比对、训练、批量下载） |
| 技能 | `skill-filesystem` | 用户自有技能根（`$DSH_HOME/skills`） |
| 设置页 | `biomedical-skill-settings` | profile 级行 + `settings/client.js`（`dsh.client`），34 个分类开关写入 `biomedical-skills.json` |
| 技能 | `biomedical-skill-picker` | 单一 provider：603 个技能按 34 个功能分类提供，开关见 `picker/catalog.json` |
| 技能 | `tool-skill` | 技能目录与加载器 |
| 数据 | `bio-mcp` | 拉起 `mcp/biomedical_mcp.py`（51 工具，stdio） |
| 编排 | `command-goal`、`tool-goal` | 长课题目标追踪 |
| 编排 | `planning`（组） | plan-mode，先出研究设计再动手 |
| 编排 | `compaction`（组） | 上下文压缩 + 工具结果裁剪（组学输出动辄上万行） |
| 编排 | `delegation`（组） | `subagent` / `subagent_fork` / `workflow` |
| 并发 | `subagent-cap` | 同一会话最多 3 个子智能体（`tools/execute` 拦截） |
| 编排 | `tool-ask-user` | 只问用户自有决策（物种、队列、终点、期刊） |
| 编排 | `tool-todo` | 多步骤任务拆解 |
| 交付 | `tool-web` | 文献与库 API 抓取（fetch + search） |
| 交付 | `present` | 图表、DOCX 稿、汇报材料的交付卡片 |

---

## 技能清单（603，34 个功能分类）

603 个技能按**用户要达成的任务**分为 34 类（每类 10–38 个），由 `picker` 插件统一提供，映射见 `picker/catalog.json`。分类不按文件格式切分；nf-core 流程按分析任务分散到各领域类。

### 在设置里按类开关

设置页随本包一起安装（`settings/`，在 profile patch 里插一行 `biomedical-skill-settings`）：**设置 → 生物医学技能** 会列出 34 个分类开关和全开/全关按钮。

开关写入 profile 的 `biomedical-skills.json`，`picker` 每次 `list()` 都读它，因此改动对**新会话**立即生效（已开启的会话不重算目录）。也可以直接编辑该文件，例如 `{"proteomics": false}`，缺省视为开启。

### 设置页：按组分节

设置页把这 34 个分类上卷成 **6 个大组**，按组分节显示，组间有分隔线：

| 大组 | 分类数 | 技能数 |
|---|---|---|
| 测序与变异 | 8 | 142 |
| 组学与单细胞 | 10 | 224 |
| 结构与药物 | 5 | 83 |
| 临床与影像 | 4 | 56 |
| 方法与工程 | 5 | 65 |
| 文献与写作 | 2 | 33 |

每组标题行显示「N 个分类 · M 个技能 · 已启用 X」，并带该组的「全开 / 全关」；组内默认只列出前 4 个分类，其余折叠在「还有 N 个分类 · 展开」后面。顶部保留全局「全部开启 / 全部关闭」。

分组定义在设置页 bundle 的 `GROUPS` 常量里；这里没覆盖到的分类会自动落进「其他」组，不会从页面上消失。

### 分类一览

| 分类 | id | 技能数 | 覆盖 |
|---|---|---|---|
| 测序质控与比对 | `sequencing-qc-alignment` | 19 | 把原始测序读段变成可信的比对结果，并回答数据质量、覆盖与污染能不能用。 |
| 基因组组装与比较基因组 | `genome-assembly-comparative` | 20 | 从长读长或混合数据组装并注释基因组，再比较多个基因组的共线性、泛基因组与进化关系。 |
| 变异检测与过滤 | `variant-calling-filtering` | 16 | 从比对结果或读段得到胚系、体细胞或靶向 SNV/Indel，并完成规范化与质控过滤。 |
| 拷贝数变异与结构变异 | `copy-number-structural-variation` | 10 | 检测缺失、重复、倒位、易位、重复扩增与等位失衡，并解释拷贝数与结构层面的改变。 |
| 变异解读与罕见病诊断 | `variant-interpretation-clinical` | 11 | 把变异注释到基因与后果，按 ACMG/AMP 证据分级并支撑罕见病与家系诊断结论。 |
| 群体遗传与 GWAS | `population-genetics-gwas` | 28 | 在人群层面找疾病关联位点、构建遗传评分并推断因果、共定位、精细定位与祖源结构。 |
| 肿瘤基因组与液体活检 | `cancer-genomics-liquid-biopsy` | 28 | 刻画肿瘤体细胞突变、克隆演化与可用标志物，并用 cfDNA/ctDNA 做早筛、监测与残留病判断。 |
| 法医与身份鉴定 | `forensic-identity-genetics` | 10 | 用 SNP、STR、Y 染色体与线粒体标记完成身份、亲缘、混合样本与祖先来源判定。 |
| 临床精准医学与结局分析 | `clinical-precision-medicine` | 10 | 评估生物标志物与预测模型，划分患者亚组，并把证据与结局分析整理成可交接的临床材料。 |
| 医学影像与放射组学 | `medical-imaging-radiomics` | 12 | 处理 CT/MRI/病理等影像数据，做分割、配准、特征提取、模型训练与可信度评估。 |
| 显微成像与细胞表型 | `microscopy-cell-phenotyping` | 17 | 从显微、流式与空间蛋白图像定量细胞形态、分割、计数、追踪并比较组间表型。 |
| 转录组上游与定量 | `transcriptomics-quantification` | 32 | 从 RNA 读段得到表达矩阵，处理链特异性、异构体组装、融合、剪接与 RNA 修饰证据。 |
| 差异表达与功能富集 | `differential-expression-enrichment` | 11 | 在组学矩阵上做组间差异与统计建模，并把结果落到通路、基因集与功能解释。 |
| 单细胞基础分析 | `single-cell-core` | 20 | 完成单细胞数据的质控、双细胞与环境 RNA 清理、降维聚类、注释与对象格式管理。 |
| 单细胞高级与虚拟细胞 | `single-cell-advanced-virtual-cell` | 20 | 在单细胞数据上做轨迹、通讯、扰动预测、多模态与队列复现等机制性推断。 |
| 空间组学分析 | `spatial-omics` | 15 | 利用空间坐标回答组织里谁在哪里、谁挨着谁，并识别空间域、邻域与细胞组成。 |
| 蛋白质组学 | `proteomics` | 21 | 从质谱原始数据到肽段鉴定与蛋白定量，并处理修饰、亲和平台与定量质量。 |
| 代谢组与脂质糖组 | `metabolomics-lipidomics` | 18 | 把质谱、NMR 或电泳信号转成可信的代谢物、脂质与聚糖注释和定量结果。 |
| 表观遗传与 DNA 甲基化 | `epigenomics-methylation` | 31 | 处理 ChIP/ATAC/CUT&RUN、Hi-C 与亚硫酸氢盐数据，识别 peak、染色质状态、三维结构与甲基化差异。 |
| 调控网络与序列模型 | `regulatory-network-sequence-models` | 18 | 推断转录因子调控网络与模块，或用基因组基础模型评估序列变异的调控效应。 |
| 微生物组与宏基因组 | `microbiome-metagenomics` | 38 | 从扩增子或 shotgun 数据得到物种、功能、耐药与菌株结果，并做群落比较与传播分析。 |
| 结构预测与建模 | `structural-biology-modeling` | 18 | 预测或准备蛋白与复合物结构，评估质量、相似性与界面几何并做动力学分析。 |
| 化学信息学与药物设计 | `chemoinformatics-drug-design` | 27 | 围绕小分子做结构标准化、描述符、相似性、对接与筛选、成药性与毒性排序。 |
| 蛋白工程与合成生物学 | `protein-engineering-synbio` | 15 | 设计蛋白序列与骨架、优化表达与可开发性，并把构建放进代谢与自动化实验方案。 |
| 基因编辑与分子克隆 | `gene-editing-cloning` | 13 | 设计 gRNA、供体与筛选文库，评估脱靶与编辑结果，并完成克隆相关的序列层面设计。 |
| 药物基因组学与用药 | `pharmacogenomics-dosing` | 10 | 把基因型转成星等位基因与表型，落到具体药物的剂量、疗效与安全性建议。 |
| 免疫组学与免疫治疗 | `immunology-immuno-oncology` | 17 | 分析受体库、HLA、新抗原与免疫浸润，评估免疫治疗获益与疫苗表位覆盖。 |
| 文献检索与证据合成 | `literature-evidence-synthesis` | 13 | 检索、核验并综合文献与数据库证据，形成可核查的综述、评审与证据强度判断。 |
| 写作与文档交付 | `writing-document-delivery` | 20 | 把分析与文献写成论文、基金、海报或报告，并导出合规的 Word/PDF/PPT 交付件。 |
| 数据工程与统计方法 | `data-engineering-statistics` | 24 | 整理表格与格式、建立统计与机器学习评估、管理隐私与数据交换的工程性任务。 |
| 计算流程与可复现性 | `workflow-reproducibility` | 10 | 搭可复现的分析环境与流程，追溯输入与版本，并审计结果漂移与助手可靠性。 |
| 数据库与接口对接 | `database-api-access` | 11 | 通过 API 或公共库取回基因、变异、结构、组学与文献数据，并核对版本与可用性。 |
| 可视化与图件 | `visualization-figures` | 10 | 把数据与结构做成清晰可发表的图表、轨道、示意图或渲染好的图形交付件。 |
| 研究设计与假设生成 | `research-design-hypothesis` | 10 | 把宽泛兴趣收束成可检验问题，规划数据、对照、样本量与验证路线。 |

### 技能来源

- **上游技能插件（582 个）**：取自本机已安装的 27 个技能插件的发布内容（2026-10-30 版本）。其中 134 个原始占位名（`*-skill-<hash>` 形式）已改写为语义化 kebab 名称；跨插件重名的 9 个只保留一份。
- **自建（21 个）**：`skills/omics`，其中 11 个按官方文档整编（`SKILL.md` + `references/{official-docs,parameters,troubleshooting}.md`，命令均标注官方来源，官方未提供可执行命令处显式标注）。

### 目录成本

603 个技能的 name + description 合计 76 184 字符 ≈ **35k token**，常驻系统提示。用分类开关按需裁剪，例如保留「组学 + 数据工程与统计 + 文献与证据合成 + 写作与文档交付」约 14k token。

### 技能目录的兜底

`picker` 是 preset 里唯一的技能 provider，因此做了三层兜底：

1. **catalog 损坏或缺失** → 自动退化为直接扫描 `skills/*/*/SKILL.md`，603 个技能照常可用（分类标记为 `fallback`），文件修好后下次 `list()` 自动恢复。
2. **设置页把所有分类都关掉** → 同样退化为全量扫描，避免"全关之后技能凭空消失"。
3. **picker 模块本身加载失败**（改坏 JS、依赖解析失败）→ patch 里预置了 6 行 `skill-filesystem` hub，默认 `disabled: true`（零开销）；在插件页逐个打开即可恢复全部技能。启用前先禁用 picker 行，否则同一技能会由两个 provider 各提供一份。

第 1、2 层已实测（catalog 损坏 → 仍返回 603；全关 → 仍返回 603）。第 3 层是给"下次改坏代码"买的保险。

## MCP 工具清单（51）

`mcp/biomedical_mcp.py` 是一个**纯标准库**（`json/sys/time/gzip/io/urllib`）的 stdio JSON-RPC 服务，一个进程承载 22 个数据域，全部直连公开 REST API，不需要 token，也不经过任何网关。工具名形如 `<域>_<动作>`。

### 文献与预印本（7）

| 工具 | 说明 |
|---|---|
| `pubmed_search_articles` | PubMed 检索，返回 PMID/标题/期刊/日期/作者/DOI |
| `pubmed_get_article_metadata` | 按 PMID 取元数据（含 DOI/PMCID） |
| `pubmed_find_related` | 按 PMID 找 PubMed 计算的相关文献 |
| `biorxiv_get_preprint` | 按 DOI 取 bioRxiv/medRxiv 元数据（非同行评议） |
| `biorxiv_recent_preprints` | 按日期区间列预印本 |
| `literature_graph_openalex_search` | OpenAlex 跨学科文献检索 |
| `literature_graph_arxiv_search` | arXiv 检索（返回 Atom XML 片段） |

### 基因组与变异（11）

| 工具 | 说明 |
|---|---|
| `genomes_ensembl_lookup` | 按基因符号或稳定 ID 查注释（位置、biotype、转录本） |
| `genomes_ensembl_sequence` | 取序列：region 取区间，stable_id 取该 ID 序列 |
| `genomes_ensembl_overlap` | 查区间内重叠的基因/转录本等特征 |
| `variants_gnomad_get_variant` | gnomAD v4 群体频率；429 时自动回退 Ensembl 人群频率 |
| `variants_clinvar_search` | ClinVar 检索（NCBI E-utilities） |
| `variants_dbsnp_get` | 按 rsID 取 dbSNP 记录摘要 |
| `human_genetics_variant_phenotypes` | 按 rsID 取变异关联性状与 p 值（Ensembl variation） |
| `rna_rfam_family` | Rfam 家族详情（accession、类型、seed/full 数量） |
| `rna_rfam_search` | Rfam 关键词检索 |
| `regulation_encode_search` | ENCODE 实验检索；站点不可达时用 region 回退 Ensembl 调控区 |
| `regulation_jaspar_matrix` | JASPAR 矩阵详情或按关键词检索 |

### 表达与组学归档（7）

| 工具 | 说明 |
|---|---|
| `expression_gtex_median` | GTEx 某基因各组织中位表达（TPM 降序，需 GENCODE ID） |
| `expression_gtex_tissue_sites` | 列 GTEx 组织位点 |
| `omics_archives_geo_search` | GEO 数据集检索（NCBI gds） |
| `omics_archives_pride_project` | PRIDE 按 accession 取蛋白质组项目 |
| `omics_archives_biostudies_search` | BioStudies / ArrayExpress 检索 |
| `cellguide_cellxgene_collections` | CELLxGENE Discover 列公开数据集集合 |
| `cellguide_search_cell_types` | Cell Ontology 细胞类型检索（CL ID + 描述） |

### 基因、本体与蛋白注释（8）

| 工具 | 说明 |
|---|---|
| `genes_ontologies_mygene_query` | MyGene 批量解析基因符号/ID |
| `genes_ontologies_quickgo_annotations` | QuickGO 取 UniProt 蛋白的 GO 注释 |
| `genes_ontologies_ols_term` | OLS4 本体术语详情 |
| `protein_annotation_interpro_domains` | InterPro 取 UniProt 蛋白结构域架构 |
| `protein_annotation_string_network` | STRING v12 蛋白互作网络 |
| `protein_annotation_hpa_gene` | Human Protein Atlas 按基因名取记录 |
| `biomart_query` | Ensembl BioMart 通用查询（XML over GET，返回 TSV） |
| `biomart_gene_info` | BioMart 按符号取基础注释（Ensembl/Entrez/位置/biotype） |

### 结构与分子（3）

| 工具 | 说明 |
|---|---|
| `structures_pdb_entry` | RCSB PDB 按 PDB ID 取条目摘要 |
| `structures_pdb_search` | RCSB PDB 全文检索 |
| `structures_alphafold_prediction` | AlphaFold DB 取 UniProt 的预测结构链接 |

### 化学与药物（9）

| 工具 | 说明 |
|---|---|
| `chembl_compound_search` | ChEMBL 按名称搜化合物（ID、SMILES、研发阶段） |
| `chembl_get_bioactivity` | 某化合物与靶点的实验活性（IC50/Ki） |
| `chembl_target_search` | 按名称或基因符号搜 ChEMBL 靶点 |
| `chemistry_pubchem_search` | PubChem 按名称/SMILES/InChIKey 解析 CID |
| `chemistry_pubchem_properties` | PubChem 按 CID 取分子属性 |
| `chemistry_rhea_reaction` | Rhea 按反应 ID 取方程式与参与者 |
| `zinc_search_by_structure` | 按 InChIKey/SMILES 查 ZINC；接口下线时回退 PubChem |
| `drug_regulatory_openfda_labels` | openFDA 检索药品说明书 |
| `drug_regulatory_openfda_drugsfda` | openFDA Drugs@FDA 检索申请记录 |

### 临床与肿瘤（6）

| 工具 | 说明 |
|---|---|
| `clinicaltrials_search_trials` | ClinicalTrials.gov v2 试验检索 |
| `clinicaltrials_get_trial` | 按 NCT 号取完整试验记录 |
| `clinical_genomics_civic_search` | CIViC GraphQL 检索癌症证据条目 |
| `clinical_genomics_opentargets_disease_targets` | Open Targets 取疾病关联靶点 |
| `cancer_models_cbioportal_studies` | 列/筛 cBioPortal 研究 |
| `cancer_models_cbioportal_mutations` | 取某研究中某基因的突变（自动解析分子谱） |

### 容错设计

工具对不稳定上游做了降级，并在返回值里说明降级来源：

- gnomAD 429 → Ensembl 人群频率
- ENCODE 不可达 → Ensembl 调控区（传 `region`）
- ZINC 公开 JSON 已下线 → PubChem
- GWAS Catalog 旧 REST 已下线 → Ensembl variation
- 统一 4 次重试、指数退避，覆盖 429/500/502/503/504；默认 45 秒超时

---

## 并发与资源约束

| 约束 | 值 | 机制 |
|---|---|---|
| 每会话同时运行的子智能体 | **3** | `subagent-cap.mjs` 在 `tools/execute` 上按 `exec.agent.id` 分桶计数，超限返回 `ACTIVATION_LIMIT_REACHED` |
| workflow 扇出并发 | **3** | `workflow-ptc.maxConcurrentAgents` |
| 重计算并行 | **1** | persona 纪律（组学流程吃满内存，并行只会一起 OOM） |
| Host 全局子代理池 | 8（未改动） | 其它模式不受影响 |

并发闸只作用于**使用本预设的会话**：`tools/execute` 是 agent-scope 过滤的 waterfall，其它模式的工具调用不会经过它。`spawn_teammate`（Agent Teams）不计入，因为它是 fire-and-return，包裹期覆盖不到实际运行，所以 persona 里直接禁止用它派活。

---

## 平台要求

| 项 | 要求 |
|---|---|
| DSH | `^0.2.1-rc.2`（包内 `engines.dsh`，与市场索引条目一致） |
| Python | 3.x，只用标准库；默认调用 DSH 自带 `dsh-primary-runtime` 的 python |
| 网络 | 出网访问公开 REST API（NCBI/EBI/Ensembl/RCSB/Broad/EMBL 等） |
| 磁盘 | 包本体约 19.5 MB（未压缩；603 个技能的 2209 个文件占绝大部分） |
| 权限 | 安装需要 profile 的 Full access 或审批；`plugin_manager` 每个动作都需要审批（无 Full 时） |

---

## 仓库结构

```
cordis.patch.yml        本包装配：内层 28 个插件行；profile 里插 2 行（预设 + 设置页）
package.json            包声明：dsh.bundle（patch）+ dsh.client（设置页）/ exports / files / engines.dsh
subagent-cap.mjs        子智能体并发闸（tools/execute 作用域，限 3 并发）
picker/                 技能 provider：catalog.json（34 类 x 603 技能）+ index.js
settings/               设置页：index.js（Config + 镜像）/ client.js（settings.section 页面）/ config.mjs
mcp/biomedical_mcp.py   51 个数据源工具（stdio JSON-RPC，纯标准库）
skills/                 6 个域目录 / 603 个技能 / 2209 个文件
  omics/                 21 个（自建，按官方文档整编，带 references）
  genomics/             140 个（基因组/群体遗传/肿瘤/临床基因组/液体活检/法医）
  omics-upstream/       193 个（转录/蛋白/代谢/表观/空间/多组学/单细胞/微生物组）
  structure-drug/        79 个（结构生物学/AI 药物发现/合成生物学/药物基因组/基础模型）
  clinical-imaging/      36 个（精准医学/AI 医学影像/衰老长寿）
  methods/              134 个（基础设施/方法学/网络系统生物学/免疫组学/生物医学科学）
locale/{en,zh}.json     市场展示元数据（meta.title / meta.description）
icon.svg                原创图标（双螺旋，632 B）
market/index.json       插件市场索引（format 1），只列本包一个条目
market/icons/           索引引用的图标目录（biomedical.svg）
README.md               本文件
```

`files` 明确排除 `market/`（发布产物不进 npm 包）；`.gitignore` 排除 `node_modules/`、`__pycache__/`、`.omc/`。

---

## 更新与发版

```sh
cd biomedical-preset
# 1. 改代码 → 提交 → 推送
git add -A && git commit -m "feat: ..." && git push

# 2. 用新的含包 commit 更新索引
#    market/index.json → plugins[0].versions[0].version / source.commit
git add market/index.json && git commit -m "market: bump" && git push
```

注意两点：

- 索引里的 `source.commit` 必须指向**包含完整包**的那个提交（改索引本身的那次提交不能自指）。
- `raw.githubusercontent.com` 有 CDN 缓存，市场端对文档缓存 10 分钟（`cacheTtlMs`），刚推送发现还是旧版属正常；检索时可用 `refresh` 重新拉取，或改用 GitHub Pages 托管索引。

发 npm 也行（包名 `dsh-biomedical-preset` 当前未被占用）：

```sh
npm publish --access public
```

然后把索引条目的 `source` 改成 `{ "type": "npm" }` 并同步 `version`。

---
