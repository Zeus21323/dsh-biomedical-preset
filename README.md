# 生物医学模式 · dsh-biomedical-preset

DeepSeek Harness 的 agent 预设（bundle）。它不是"给通用助手加个提示词"，而是一套**自持**的生物医学研究装配：身份与纪律、执行工具、78 个流程技能、51 个数据源 MCP 工具、并发闸、交付通道，全部装在这一个包里，不引用任何外部插件目录。

- 心智模型：**MCP 负责取数据，Skill 负责选方法与执行流程**，persona 负责纪律与判断。
- 已验证：市场索引通过官方 `@deepseek-ai/dsh-plugin-market-index` 校验；`npm pack` 产物 370 文件 / 0.87 MB（packed）/ 3.05 MB（unpacked）；本机预设 `fiberPhase: active`。

---

## 目录

- [安装](#安装)
- [装配结构](#装配结构)
- [技能清单（78）](#技能清单78)
- [MCP 工具清单（51）](#mcp-工具清单51)
- [并发与资源约束](#并发与资源约束)
- [平台要求](#平台要求)
- [仓库结构](#仓库结构)
- [更新与发版](#更新与发版)
- [许可](#许可)

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

`cordis.patch.yml` 共 24 个插件行：

| 层 | 插件行 | 作用 |
|---|---|---|
| 身份 | `persona` | 生物医学研究者 prefix（13 小节工作规范）+ 8 条结论纪律 suffix |
| 身份 | `agent-instructions` | 读取项目 `AGENTS.md`（课题组分析规范走这里） |
| 身份 | `time-context` | 时间锚（"近三年"、随访窗口） |
| 执行 | `tool-pwsh` / `tool-bash` | 按平台二选一，跑 python/R/conda/比对工具 |
| 执行 | `tool-fs`、`tool-fs-search` | 读写脚本、检索大表、grep 参数文件 |
| 执行 | `tool-jobs` | 后台长任务（比对、训练、批量下载） |
| 技能 | `skill-filesystem` | 用户自有技能根（`$DSH_HOME/skills`） |
| 技能 | `bio-skills` | 挂载 `skills/biomedical`（30） |
| 技能 | `bio-core-skills` | 挂载 `skills/science-core`（33） |
| 技能 | `omics-skills` | 挂载 `skills/omics`（15 个组学技能） |
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

## 技能清单（78）

技能分三组挂载：`skills/omics`（15，组学平台与流程）、`skills/biomedical`（30，结构与生信写作）、`skills/science-core`（33，方法学与交付合规）。下表按用途归类，一个技能只出现一次。

### 1. 组学平台（15）

| 技能 | 组学 | 用途 |
|---|---|---|
| `proteomics-quantification` | **蛋白组** | **本项目原创**：MaxQuant / DIA-NN / Spectronaut / FragPipe 输出 → 过滤 → 归一化 → 缺失值 → limma/DEqMS → 富集 → 交付 |
| `metabolomics-profiling` | **代谢组 / 脂质组** | **本项目原创**：峰表 QC 过滤 → PQN 归一化 → PCA/PLS-DA/OPLS-DA（含置换验证）→ 单变量 → 注释置信级 → mummichog 通路 |
| `pyopenms` | 蛋白组 / 代谢组 | 质谱全平台：feature detection、肽段鉴定、蛋白定量；MatchMS 谱相似度与代谢物谱库匹配 |
| `scikit-bio` | **微生物组** | 序列与比对、系统发育、α/β 多样性（UniFrac）、PCoA/PERMANOVA、FASTA/Newick 读写 |
| `scanpy` | 单细胞 | scverse 生态：AnnData、QC、降维聚类、scVelo RNA 速率、scvi-tools 集成（与 `bio-scanpy` 互补，更偏生态与速率） |
| `sc-rna-seq-analysis` | 单细胞 | 17+ 模块全流程：decontX 去污染、双细胞检测、Harmony、自动注释、AUCell、scMetabolism、decoupleR |
| `bulk-rnaseq` | 转录组 | FASTQ → counts → PyDESeq2 → 富集 → 出图（与 `bio-bulk-rnaseq` 同源不同路径：这条走 PyDESeq2 全程） |
| `deeptools` | 表观组 | BAM→bigWig、相关性/PCA/指纹图、TSS 与 peak 热图（与 `bio-deeptools` 同源，供 ChIP/ATAC 覆写） |
| `pysam` | 基因组 | SAM/BAM/CRAM/VCF/BCF/FASTA/FASTQ 读写、区域提取、覆盖度计算 |
| `polars-bio` | 基因组 | 区间运算：overlap / nearest / merge / coverage / complement / subtract，流式读 BED/VCF/BAM |
| `gtars` | 基因组 | 区间工具 Rust 绑定、覆盖度、坐标分块与 tokenization |
| `cellxgene-census` | 单细胞图谱 | CZ CELLxGENE Census 的群体规模切片、元数据与 H5AD 定位 |
| `arboreto` | 转录组 / GRN | GRNBoost2、GENIE3 推断基因调控网络（可分布式） |
| `pathway-enrichment` | 通用下游 | ORA（Enrichr/Fisher/hypergeometric）与 preranked GSEA，所有组学共用 |
| `pathml` | **空间 / 病理组学** | WSI 切块、Macenko/Reinhard 染色归一化、CODEX/Vectra 多重免疫荧光、核分割、组织图 |

### 2. 转录组与单细胞（9）

| 技能 | 用途 |
|---|---|
| `bio-bulk-rnaseq` | bulk RNA-seq 端到端：FASTQ → QC/trim → STAR/Salmon → counts → 差异 → 富集 → 出图 |
| `bio-scanpy` | 单细胞标准流程：QC、归一化、PCA/UMAP/t-SNE、聚类、差异、可视化 |
| `bio-deeptools` | NGS 覆盖与质控：BAM→bigWig、相关性/PCA/指纹图、TSS 与 peak 热图 |
| `pydeseq2` | PyDESeq2 差异表达：公式化设计、Wald 检验、FDR、LFC 收缩 |
| `scvi-tools` | 单细胞概率建模：scVI 批次校正、scANVI 标签转移、贝叶斯差异表达 |
| `scgpt` | 单细胞基础模型：细胞嵌入、零样本/微调注释、基因级表示 |
| `omics-negative-control-calibration` | 负对照与置换校准：回应"碰巧显著"，识别独立/分块/配对设计 |
| `public-omics-study-design-report` | 只有疾病或基因时：选公共数据、设计发现/验证路线、写可追溯报告 |
| `conventional-oncology-hub-gene-research-planner` | 肿瘤 bulk 转录组标志物 + hub 基因研究设计（DEG→预后→PPI→免疫浸润） |

### 3. 结构预测与分子设计（10）

| 技能 | 用途 |
|---|---|
| `alphafold2` | ColabFold 跑 AF2/AF2-Multimer，pLDDT/ipTM/RMSD 评估 |
| `boltz` | Boltz-2：蛋白/核酸/小分子复合物共折叠，可选结合亲和力 |
| `chai1` | Chai-1：单条 FASTA 预测抗体–抗原、蛋白–配体复合物 |
| `openfold3` | OpenFold3：AF3 开放权重复现，蛋白/核酸/配体复合物 |
| `esmfold2` | ESMFold2 全原子共折叠：单序列与 MSA 模式、CCD/SMILES 配体 |
| `fair-esm2` | ESM-2 嵌入：残基/序列级表示、突变效应打分、接触图 |
| `proteinmpnn` | 骨架逆折叠为序列（RFdiffusion 骨架、固定界面残基） |
| `ligandmpnn` | 配体/核酸/金属环境下的口袋重设计、金属配位几何保持 |
| `solublempnn` | 偏可溶表达的逆折叠，减少聚集与包涵体 |
| `diffdock` | DiffDock-L 盲对接：SMILES/SDF → 蛋白口袋排序姿势 |

### 4. 基因组、调控与变异（3）

| 技能 | 用途 |
|---|---|
| `borzoi` | 由 DNA 序列预测全基因组功能轨迹，评估非编码变异的调控效应 |
| `evo2` | 长上下文基因组模型：序列评分、嵌入、生成，跨物种调控区比较 |
| `qtl-colocalization-study-planner` | QTL 共定位研究设计：eQTL/pQTL/sQTL 与 GWAS 位点的因果信号判断 |

### 5. 数据库与知识整合（5）

| 技能 | 用途 |
|---|---|
| `bioservices` | 40+ 生物信息服务统一 Python 接口（UniProt/KEGG/ChEMBL/Reactome…） |
| `gget` | 20+ 数据库的快速 CLI/Python 查询（基因、BLAST、结构、富集） |
| `scientific-database-access` | 基因/变异/表达/药物/通路/结构/临床数据库的查询与结果解释规范 |
| `tooluniverse-metabolomics` | 代谢组：HMDB 220K+ 代谢物、MetaboLights、Metabolomics Workbench |
| `biomedical-knowledge-graph-rag` | 把论文、数据库、内部资料组织成可检索知识图谱或 RAG 问答 |

### 6. 文献与证据（5）

| 技能 | 用途 |
|---|---|
| `literature-review` | 从"奠基性论文是哪篇"到多来源综述；真实来源支撑、避免伪造引文、处理撤稿 |
| `medical-research-literature-reader-pro` | 医学研究原生精读：按方法→数据→统计→结论→局限拆解，给同类研究与审稿准备 |
| `evidence-validation` | 评价论文/数据库结果/实验发现的证据强度、偏倚与可复现性 |
| `literature-evidence-writing` | 系统检索生物医学文献 → 整理证据 → 写带准确引用的科研文本 |
| `indication-dossier` | 治疗适应症档案：人群、流行病学、疾病生物学、标准治疗、监管先例、里程碑试验 |

### 7. 统计、临床与模型审计（6）

| 技能 | 用途 |
|---|---|
| `clinical-statistics-survival` | 临床描述统计、生存分析、回归模型、敏感性分析的设计与检查 |
| `clinical-research-reporting` | 把临床数据与统计结果整理成可复核的研究报告/摘要/结果章节 |
| `clinical-trial-workflows` | 临床试验检索、可行性评估、研究方案框架起草 |
| `exploratory-data-analysis-stat-tests` | 表格数据质量/分布/关联/异常值检查，连续/分类/配对/多组的检验选择 |
| `machine-learning-evaluation` | 预测模型有效性审计：数据泄漏、验证失败、换样本结果不变 |
| `shap` | SHAP 解释生物医学表格模型：加和性、相关特征影响、全局与个体报告 |

### 8. 研究设计与数据识别（3）

| 技能 | 用途 |
|---|---|
| `scientific-problem-hypothesis` | 把宽泛兴趣收束成可检验、可证伪、有价值的科研问题与假设 |
| `experiment-protocol-design` | 只给疾病/基因/研究目标时：设计对照、重复、样本量与验证实验 |
| `nfcore-catalog` | 只有交付文件、只知样本来源时：识别数据类型与处理阶段，匹配分析流程 |

### 9. nf-core 工作流（8）

| 技能 | 用途 |
|---|---|
| `nfcore-fetchngs` | 只有数据库编号时取得测序文件与样本信息 |
| `nfcore-references` | 生成/获取与数据兼容的参考基因组、注释与索引 |
| `nfcore-datasync` | 存储位置之间的复制、同步与整理 |
| `nfcore-demo` | 用小示例认识分析步骤或体检计算环境 |
| `nfcore-seqsubmit` | 整理成公开测序数据库的提交材料（ENA/SRA） |
| `nfcore-provenancereport` | 已有结果但不知用了哪些输入/版本/参数时核查可复现性 |
| `nfcore-deepmodeloptim` | 有训练数据与模型时改预测效果或评估数据增强 |
| `bioinformatics-file-format-conversion` | FASTA/FASTQ/SAM/BAM/CRAM/BIOM/TSV 互转，核对记录数与配对关系 |

### 10. 数据工程与可靠性（6）

| 技能 | 用途 |
|---|---|
| `data-processing-tables` | CSV/TSV/Excel 的清理、合并、核对、汇总 |
| `instrument-data-standardization` | 仪器原始导出 → 统一、可交换、保留元数据的结构 |
| `infrastructure-workflows` | 可复现科研计算环境：容器、工作流编排、运行记录 |
| `bioinformatics-agent-reliability-evaluation` | 比较生信助手、检查自动分析是否编造、建失败基准（BioAgent Failure Atlas） |
| `biomedical-result-drift-audit` | 更新数据库后结果变了：核验运行条件、固定背景重算、比较两版资源影响 |
| `research-data-privacy-deidentification` | 识别并降低个人身份、基因组再识别、敏感元数据风险 |

### 11. 工程与集成（2）

| 技能 | 用途 |
|---|---|
| `api-external-integration` | 科研数据库/实验平台/院内系统的 API 对接：认证、分页、限流、重试、数据映射 |
| `software-engineering-testing` | 编写、重构、验证生物医学分析用的科研软件与命令行工具 |

### 12. 写作与可视化（4）

| 技能 | 用途 |
|---|---|
| `bioinformatics-writer` | 生信请求分流：写稿 / 数据分析 / 其他服务 / 从影像或文献知识图谱写稿 |
| `methods-section-writer` | 把协议与分析流程写成可投稿 Methods，对齐 CONSORT/STROBE/PRISMA/TRIPOD |
| `reporting-guideline-compliance-checker` | 按报告规范核查稿件缺项与弱项（投稿前自查） |
| `scientific-visualization-reporting` | 把结果画清楚：图型顾问、布局验收、三格式导出、图与文一致性 |

### 13. 其他（2）

| 技能 | 用途 |
|---|---|
| `mcp-tool-operations` | 发现已配置的 MCP 工具、选型、排查连接与调用错误 |
| `morning` | 晨间简报渲染为 HTML 或设为工作日循环任务（显式调用才触发） |

### 第三方技能来源

`skills/omics` 下 15 个技能中，`proteomics-quantification` 与 `metabolomics-profiling` 为本项目原创；其余 13 个（`pyopenms`、`scikit-bio`、`scanpy`、`sc-rna-seq-analysis`、`bulk-rnaseq`、`deeptools`、`pysam`、`polars-bio`、`gtars`、`cellxgene-census`、`arboreto`、`pathway-enrichment`、`pathml`）取自公开分发的 skill 集合，原始目录未随附许可文件。

若上游主张权利，删除对应子目录即可，其余能力不受影响（`omics-skills` 是独立 provider，删目录后该组自动少一项，不会破坏装配）。

---

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
| 磁盘 | 包本体约 2.05 MB（未压缩） |
| 权限 | 安装需要 profile 的 Full access 或审批；`plugin_manager` 每个动作都需要审批（无 Full 时） |

---

## 仓库结构

```
cordis.patch.yml        预设装配（23 个插件行）
package.json            包声明：exports / files / engines.dsh
subagent-cap.mjs        子智能体并发闸（tools/execute 作用域）
mcp/biomedical_mcp.py   51 个数据源工具（stdio JSON-RPC，纯标准库）
skills/omics/           15 个组学技能（蛋白组、代谢组、单细胞、微生物组、区间/变异、富集、空间病理）
skills/biomedical/      30 个技能（结构预测、组学、生信写作…）
skills/science-core/    33 个技能（nf-core、临床统计、证据与工作流…）
locale/{en,zh}.json     市场与设置页展示元数据（meta.title / meta.description）
icon.svg                原创图标（双螺旋，632 B）
market/index.json       插件市场索引（format 1）
market/icons/           索引引用的图标目录
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

## 许可

MIT。技能与 MCP 服务随包分发；各技能内部若引用第三方资产（如图件模板、术语表），其原始许可声明保留在对应目录内。
