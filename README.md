# 生物医学模式 · dsh-biomedical-preset

DeepSeek Harness 的 agent 预设（bundle）。它不是"给通用助手加个提示词"，而是一套**自持**的生物医学研究装配：身份与纪律、执行工具、603 个流程技能、51 个数据源 MCP 工具、并发闸、交付通道，全部装在这一个包里，不引用任何外部插件目录。

- 心智模型：**MCP 负责取数据，Skill 负责选方法与执行流程**，persona 负责纪律与判断。
- 已验证：市场索引通过官方 `@deepseek-ai/dsh-plugin-market-index` 校验；`npm pack` 产物 2216 文件 / 4.62 MB（packed）/ 18.29 MB（unpacked）；本机预设 `fiberPhase: active`。

---

## 目录

- [安装](#安装)
- [装配结构](#装配结构)
- [技能清单（603）](#技能清单603)
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

`cordis.patch.yml` 共 27 个插件行：

| 层 | 插件行 | 作用 |
|---|---|---|
| 身份 | `persona` | 生物医学研究者 prefix（13 小节工作规范）+ 8 条结论纪律 suffix |
| 身份 | `agent-instructions` | 读取项目 `AGENTS.md`（课题组分析规范走这里） |
| 身份 | `time-context` | 时间锚（"近三年"、随访窗口） |
| 执行 | `tool-pwsh` / `tool-bash` | 按平台二选一，跑 python/R/conda/比对工具 |
| 执行 | `tool-fs`、`tool-fs-search` | 读写脚本、检索大表、grep 参数文件 |
| 执行 | `tool-jobs` | 后台长任务（比对、训练、批量下载） |
| 技能 | `skill-filesystem` | 用户自有技能根（`$DSH_HOME/skills`） |
| 技能 | `omics-skills` | 挂载 `skills/omics`（21 个自建组学技能） |
| 技能 | `upstream-*-skills`（5 组） | 挂载 `skills/upstream-*`（582 个，按域拆分，可单独关闭） |
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

## 技能清单（603）

按来源分 6 组，每组是独立 skill provider，可单独开关。

| provider | 目录 | 数量 | 体积 | 覆盖 |
|---|---|---|---|---|
| `biomedical-omics` | `skills/omics` | 21 | 1.5 MB | 自建：变异检测、CNV/SV、ACMG 分级、表观 peak、DNA 甲基化、RNA 修饰/CLIP、免疫组学、脂质组、糖组、蛋白组定量、代谢组、单细胞、微生物组、空间病理、区间运算 |
| `genomics` | `skills/genomics` | 140 | 2.1 MB | 基因组、群体遗传、肿瘤基因组、临床基因组、液体活检、法医基因组 |
| `omics-upstream` | `skills/omics-upstream` | 193 | 5.7 MB | 转录组、蛋白组、代谢组、表观组、空间组、多组学整合、单细胞与虚拟细胞、微生物组 |
| `structure-drug` | `skills/structure-drug` | 79 | 0.3 MB | 结构生物学、AI 药物发现、合成生物学、药物基因组学、生物基础模型 |
| `clinical-imaging` | `skills/clinical-imaging` | 36 | 0.1 MB | 精准医学、AI 医学影像、衰老与长寿 |
| `methods` | `skills/methods` | 134 | 8.7 MB | 科研基础设施、方法学、网络系统生物学、免疫组学、生物医学科学 |
| **合计** | | **603** | **18.2 MB** | |

`upstream-*` 的 582 个技能取自本机 `~/.dsh/plugins/releases` 下 27 个 upstream 插件（2026-10-30 版本）；其中 134 个原始占位名（`upstream-*-skill-<hash>`）已改写为语义化 kebab 名称，跨插件重名的 9 个只保留一份。

### 技能目录的成本与按需启用

603 个技能的名称与描述会常驻系统提示，实测 **84 044 字符 ≈ 38k token**。技能按 provider 分组，可单独关闭以压缩这一开销：

```
plugin_manager set_plugin target=include:omics-upstream-skills enabled=false
```

关闭后该域技能不再出现在新会话的技能目录中，已加载的技能不受影响。

| 场景 | 建议启用 | 技能数 | 约 token |
|---|---|---|---|
| 全开（默认） | 6 组全部 | 603 | 38k |
| 基因组 / 变异为主 | omics + genomics + methods | 295 | 22k |
| 单细胞 / 组学为主 | omics + omics-upstream + methods | 348 | 24k |
| 结构 / 药物为主 | omics + structure-drug + methods | 234 | 18k |
| 极简 | omics + methods | 155 | 13k |

### 自建组学技能（21，`skills/omics`）

`variant-calling-wes-wgs`、`cnv-sv-detection`、`variant-pathogenicity-acmg`、`epigenomics-peak-calling`、`dna-methylation-wgbs`、`rna-modification-clip`、`immunogenomics`、`lipidomics-annotation`、`glycomics`、`proteomics-quantification`、`metabolomics-profiling`、`pyopenms`、`scanpy`、`sc-rna-seq-analysis`、`scikit-bio`、`pysam`、`polars-bio`、`gtars`、`cellxgene-census`、`arboreto`、`pathml`、`pathway-enrichment`、`tiledbvcf`

其中 11 个为按官方文档整编（每个含 `SKILL.md` + `references/{official-docs,parameters,troubleshooting}.md`，命令均标注官方来源，官方未提供可执行命令处显式标注），其余为引入的第三方技能。

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
skills/omics/                21 个自建组学技能
skills/genomics/       140 个（基因组/群体遗传/肿瘤/临床基因组/液体活检/法医）
skills/omics-upstream/          193 个（转录/蛋白/代谢/表观/空间/多组学/单细胞/微生物组）
skills/structure-drug/  79 个（结构生物学/AI 药物发现/合成生物学/药物基因组/基础模型）
skills/clinical-imaging/ 36 个（精准医学/AI 医学影像/衰老长寿）
skills/methods/        134 个（基础设施/方法学/网络系统生物学/免疫组学/生物医学科学）
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
