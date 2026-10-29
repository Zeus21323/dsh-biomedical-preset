# 规则来源与文献 URL

本文件记录 `variant-pathogenicity-acmg` 技能中每一条规则、阈值、证据码定义的出处。
所有条目均在 2026-10-29 实际访问核对；"访问结果"列写的是本次抓取的真实状态，
不是推断。凡未取得原文的条目，正文中不得引用其具体数值。

## 0. 先说两处路径勘误

| 任务书中给出的候选 | 核对结果 |
|---|---|
| `https://clinicalgenome.org/working-groups/sequence-variant-interpretation/svi-proposals/` | **HTTP 404**。SVI 各条规则的细化文档挂在工作组主页右侧的 *Recommendations supported by SVI* / *Documents* 列表中，入口是 `https://clinicalgenome.org/working-groups/sequence-variant-interpretation/`（HTTP 200）。 |
| `https://pubmed.ncbi.nlm.nih.gov/36653745/`（标注为"PVS1 决策树"） | **PMID 与主题不符**。该 PMID 是 *Mol Med* 2023;29(1):9 的一篇视网膜缺血再灌注 lncRNA 论文，与 PVS1 无关。PVS1 决策树的原始文献是 **Abou Tayoun et al. 2018, PMID 30192042**（见 S-03）。本技能按后者引用。 |

`https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4544753/` 会 302 到 `https://pmc.ncbi.nlm.nih.gov/articles/PMC4544753/`，
自动跳转不被跟随，需直接用后者。

## 1. 核心标准与 SVI 细化文献

| 编号 | 文献 | 标识 | 用途 | 访问结果 |
|---|---|---|---|---|
| S-01 | Richards S, Aziz N, Bale S, et al. Standards and guidelines for the interpretation of sequence variants: a joint consensus recommendation of the ACMG and the AMP. *Genet Med* 2015;17(5):405-424. | PMID 25741868；PMCID PMC4544753；DOI 10.1038/gim.2015.30 | 五级分类术语、PVS1–BP7 全部证据码定义（Table 3/4）、组合判级规则（Table 5）、频率判断示例（Table 6）、`likely` = >90% 把握 | 全文抓到（PMC HTML） |
| S-02 | ClinGen Sequence Variant Interpretation (SVI) Working Group 主页 | `https://clinicalgenome.org/working-groups/sequence-variant-interpretation/` | SVI 全部建议与支持文档的总索引（含未进 PubMed 的 PDF） | HTTP 200，内容抓到 |
| S-03 | Abou Tayoun AN, Pesaran T, DiStefano MT, et al.; ClinGen SVI. Recommendations for interpreting the loss of function PVS1 ACMG/AMP variant criterion. *Hum Mutat* 2018;39(11):1517-1524. | PMID 30192042；PMCID PMC6185798；DOI 10.1002/humu.23626 | **PVS1 决策树**、PVS1 强度降级（PVS1 / _Strong / _Moderate / _Supporting）、NMD 规则、>10%/<10% 蛋白截短、LoF 疾病机制证据表（Table 1）、PM4 去重 | 全文抓到 |
| S-04 | Ghosh R, Harrison SM, Rehm HL, Plon SE, Biesecker LG; ClinGen SVI. Updated recommendation for the benign stand-alone ACMG/AMP criterion. *Hum Mutat* 2018;39(11):1525-1530. | PMID 30311383；PMCID PMC6188666；DOI 10.1002/humu.23642 | **BA1 修订措辞**、≥2000 观测等位基因要求、9 个 BA1 排除变异、基因特异性下调阈值机制 | 全文抓到 |
| S-05 | Tavtigian SV, Greenblatt MS, Harrison SM, et al.; ClinGen SVI. Modeling the ACMG/AMP variant classification guidelines as a Bayesian classification framework. *Genet Med* 2018;20(9):1054-1060. | PMID 29300386；DOI 10.1038/gim.2017.210 | 各强度等级的相对致病优势（Supporting 2.08:1、Moderate 4.33:1、Strong 18.7:1、Very Strong 350:1） | 摘要抓到（数值经 S-03 原文转引核对） |
| S-06 | Tavtigian SV, Harrison SM, Boucher KM, Biesecker LG. Fitting a naturally scaled point system to the ACMG/AMP variant classification guidelines. *Hum Mutat* 2020;41(10):1734-1737. | PMID 32720330；PMCID PMC8011844；DOI 10.1002/humu.24088 | **点数法**：PP=+1、PM=+2、PS=+4、PVS=+8、BP=−1、BS=−4、BA1=−8；阈值 P≥10 / LP 6-9 / VUS 0-5 / LB −1~−6 / B≤−7；后验概率边界表（Table 1、Table 2、Table 3） | 全文抓到 |
| S-07 | Pejaver V, Byrne AB, Feng BJ, et al.; ClinGen SVI. Calibration of computational tools for missense variant pathogenicity classification and ClinGen recommendations for PP3/BP4 criteria. *Am J Hum Genet* 2022;109(12):2163-2177. | PMID 36413997；PMCID PMC9748256；DOI 10.1016/j.ajhg.2022.10.013 | **PP3/BP4 校准区间**（13 个错义预测工具、Table 2）、后验概率/似然比阈值（Table 1） | 全文抓到（Table 2 已抄录） |
| S-08 | Brnich SE, Abou Tayoun AN, Couch FJ, et al.; ClinGen SVI. Recommendations for application of the functional evidence PS3/BS3 criterion using the ACMG/AMP sequence variant interpretation framework. *Genome Med* 2019;12(1):3（2019-12-31 在线） | PMID 31892348；DOI 10.1186/s13073-019-0690-2 | **PS3/BS3**：功能测定的四步评定框架；达到 Moderate 强度至少需要 11 个致病变异 + 良性变异对照 | 摘要抓到（含上述两个结论） |
| S-09 | Biesecker LG, Harrison SM; ClinGen SVI. The ACMG/AMP reputable source criteria for the interpretation of sequence variants. *Genet Med* 2018;20(12):1687-1688. | PMID 29543229；PMCID PMC6709533；DOI 10.1038/gim.2018.42 | **PP5/BP6**（reputable source）的定位与限制 | 题录与摘要抓到（4 页评论性短文） |
| S-10 | Biesecker LG, Byrne AB, Harrison SM, et al.; ClinGen SVI. ClinGen guidance for use of the PP1/BS4 co-segregation and PP4 phenotype specificity criteria for sequence variant pathogenicity classification. *Am J Hum Genet* 2024;111(1):24-38. | PMID 38103548；PMCID PMC10806742；DOI 10.1016/j.ajhg.2023.11.009 | **PP1/BS4/PP4** 点数体系：Table 3 的每次共分离点数（AR affected 2.0/4.0/6.0…、AR unaffected 0.4/0.8/1.2…、AD 1.0/2.0/3.0…、XL-recessive 1.0/2.0/3.0…）、PP1+PP4 合计 **上限 +5.0 分** | 全文抓到（Table 3 已抄录） |
| S-11 | Ellingford JM, Ahn JW, Bagnall RD, et al. Recommendations for clinical interpretation of variants found in non-coding regions of the genome. *Genome Med* 2022;14(1):73. | PMID 35850704；DOI 10.1186/s13073-022-01073-3 | 非编码区变异解读框架（ACMG/AMP 未覆盖部分） | 摘要抓到 |
| S-12 | Collins RL, Glessner JT, Porcu E, et al. A cross-disorder dosage sensitivity map of the human genome. *Cell* 2022;185(16):3041-3055.e25. | PMID 35917817；PMCID PMC9742861；DOI 10.1016/j.cell.2022.06.036 | **基因剂量敏感性**：全基因组 pHaplo / pTriplo 预测（2,987 个 HI 基因、1,559 个 TS 基因） | 摘要抓到 |
| S-13 | Walker LC, de la Hoya M, Wiggins GAR, et al.; ClinGen SVI Splicing Subgroup. Using the ACMG/AMP framework to capture evidence related to predicted and observed impact on splicing. *Am J Hum Genet* 2023;110(7):1046-1067. | PMID 37352859；PMCID PMC10357475；DOI 10.1016/j.ajhg.2023.06.002（预印本 PMID 36865205） | **剪接证据**：PVS1_Strength 用于 RNA 实验结果、BP7 可用于 RNA 显示无剪接影响、PS3/BS3 仅用于不直接反映剪接的功能测定、PS1 可用于预测剪接效应相似性、工具校准方法 | 摘要抓到（正式版与预印本摘要均核对） |

## 2. ClinGen 官方文档（PDF，非 PubMed 索引）

这些文档是本技能里"操作性规则"的主要来源，尤其是 S-14 与 S-15/S-16。

| 编号 | 文档 | URL | 访问结果 |
|---|---|---|---|
| S-14 | ClinGen Variant Curation SOP v3.2 — Classification Guidance（2025 年 7 月，226 页） | `https://submit.ncbi.nlm.nih.gov/api/2.0/files/o5ekfuov/clingen_variant_curation_sop_v3.2_classification_guidance_july2025.pdf/?format=attachment` | 下载成功、全文抽取成功 |
| S-15 | ClinGen SVI Recommendation for Absence/Rarity (PM2) — Version 1.0，2020-09-04 批准 | `https://clinicalgenome.org/site/assets/files/5182/pm2_-_svi_recommendation_-_approved_sept2020.pdf` | 下载成功、全文抽取成功 |
| S-16 | ClinGen SVI Recommendation for de novo Criteria (PS2/PM6) — Version 1.1，2018-03-18 批准 / 2021-05-05 更新 | `https://www.clinicalgenome.org/site/assets/files/3461/svi_proposal_for_de_novo_criteria_v1_1.pdf` | 下载成功、全文抽取成功 |
| S-17 | ClinGen SVI criteria nomenclature recommendation v1.0（PVS1_Strong 等强度修饰码的命名规范） | `https://www.clinicalgenome.org/site/assets/files/8490/svi_criteria_nomenclature_recommendation_v1_0.pdf` | 本次未单独抓取；URL 引自 S-03 原文正文 |
| S-18 | ClinGen SVI PVS1 Decision Tree（可编辑版支持文档，页面标注 2024-07-12） | 经 `https://clinicalgenome.org/working-groups/sequence-variant-interpretation/` 的 Documents 列表进入 | 列表项已确认存在；可编辑文件本体未抓取，决策树内容以 S-03 正文与 Figure 1 为准 |
| S-19 | ACMG 官网 | `https://www.acmg.net/` | **HTTP 403**（自动化访问被拒）。ACMG 侧内容一律以 S-01 的 *Genet Med* 正式发表版为准 |

## 3. 数据资源与查询路径

| 资源 | 入口 | 说明 |
|---|---|---|
| ClinVar | `https://www.ncbi.nlm.nih.gov/clinvar/` | 分类断言、提交者、review status、ClinVar Variation ID；批量走 NCBI E-utilities `db=clinvar` |
| gnomAD v4 | `https://gnomad.broadinstitute.org/`；API `https://gnomad.broadinstitute.org/api`；下载 `https://gnomad.broadinstitute.org/downloads` | 亚群频率、popmax、覆盖度；S-14 说明 VCI 默认显示 MAF 的 95% CI 上下界，并要求核对覆盖度（通常 >20X）后才可主张"absent" |
| ClinGen Dosage Sensitivity | `https://search.clinicalgenome.org/kb/gene-dosage` | 基因/区域剂量敏感性分类（HI/TS）；全基因组预测分数见 S-12 |
| ClinGen Gene-Disease Validity | `https://search.clinicalgenome.org/kb/gene-validity` | Definitive/Strong/Moderate/Limited；PVS1 强度依赖此等级 |
| ClinGen CSpec Registry | `https://cspec.genome.network/cspec/ui/svi` | 各 VCEP 的基因特异性规则细化（阈值下调、排除变异、强度改写） |
| ClinGen Evidence Repository | `https://erepo.clinicalgenome.org/evrepo/` | VCEP 已完成判读及证据摘要 |
| ClinGen Allele Registry | `https://reg.clinicalgenome.org/` | 变异规范化 ID（CA ID），便于跨库对齐 |
| LOVD | `https://www.lovd.nl/`；共享实例 `https://databases.lovd.nl/shared/genes` | 位点特异性数据库（基因级 LOVD 需从共享实例按基因进入） |
| SpliceAI Lookup | `https://spliceailookup.broadinstitute.org/` | 剪接预测分数查询；阈值与用法按 S-13 校准流程 |
| 本包 MCP：ClinVar 检索 | 工具名 `variants_clinvar_search` | 参数 `query`（PubMed 风格检索式，如 `BRCA1 pathogenic`）、`max_results`（默认 10） |
| 本包 MCP：gnomAD 频率 | 工具名 `variants_gnomad_get_variant` | 参数 `variant_id`（如 `1-55051215-G-GA`）、可选 `rs_id`（gnomAD 限流 429 时回退到 Ensembl 人群频率）、`dataset`（默认 `gnomad_r4`） |

## 4. 引用写法

判读表与报告中每条证据都应能追到具体出处，建议格式：

```
PM2_Supporting — 见 S-15（ClinGen SVI PM2 v1.0, 2020-09-04）；gnomAD v4.1.0 popmax AF = 0.0000（访问 2026-10-29）
PP3 — REVEL = 0.812，落在 S-07 Table 2 的 PP3 Supporting 区间 [0.773, 0.932)
PVS1_Strong — 按 S-03 决策树：NMD 不预测 + 截短区含已知致病变异 → Strong
BA1 不适用 — 该基因有 VCEP 特异性 BA1 下调阈值，见 CSpec（S-表 3）
```

引用 S-01 的规则条文时建议同时给出 Table 号（Table 3 / 4 / 5 / 6），便于审阅者核对原文。

## 5. 已知的不可得项（避免误引用）

- **ACMG 官网**（S-19）自动化访问被拒；不要引用 acmg.net 上的页面作为规则条文出处。
- **PP5/BP6**：S-09 是评论性短文，未给出可量化的使用门槛；本技能只写定性限制。
- **PM1、PP2、PP4 单独使用、PS4 的病例对照统计**：见 `criteria-table.md` §7，属于"原始标准无量化阈值"清单。
- **剪接预测工具的具体分值区间**：S-13 给出校准方法学与原则，本技能未从原文抄录其工具阈值表，
  因此不在此列数值；需要时按 S-13 正文与补充材料取值。
