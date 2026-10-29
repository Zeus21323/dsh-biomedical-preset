# 肺癌 (LUAD) 差异表达 / 预后模型 / PPI Hub基因 / 免疫浸润 / 甲基化 全流程研究方案

> **默认假设**：肺癌亚型以 **LUAD（肺腺癌）** 为主分析队列，LUSC（肺鳞癌）作为平行验证或区分性分析。用户未指定亚型，故选择最常被研究的 LUAD。如用户实际关注其他亚型（SCLC、LUSC、LCNEC 等），需调整数据集选择。

---

## A. 核心科学问题

**核心问题**：在肺腺癌（LUAD）中，哪些差异表达基因能够通过生存筛选和蛋白互作网络压缩为一组核心 hub 基因，并其预后/诊断性能、免疫浸润关联和甲基化调控特征如何支撑其作为候选生物标志物？

**四个具体目标（Specific Aims）**：
1. **差异表达与生存筛选** — 识别 LUAD 肿瘤 vs 正常组织的稳定差异表达基因（DEG），并通过单变量 Cox 回归筛选预后相关基因集
2. **风险模型构建与 Hub 基因压缩** — 基于预后基因构建 LASSO-Cox 风险评分模型，再通过 PPI 网络拓扑分析将签名压缩至 3–5 个核心 hub 基因
3. **免疫浸润与微环境表征** — 评估 hub 基因表达与 22 种免疫细胞浸润分数的相关性，以及免疫检查点基因（PD-L1、CTLA-4 等）的关联
4. **甲基化调控与临床关联** — 分析 hub 基因启动子区 CpG 甲基化水平与表达量的负相关性，以及其对总生存期的独立预后价值

**为什么这个组合是正确的**：LUAD 是数据最丰富的癌种之一（TCGA-LUAD ~500+ 样本，GEO 大量独立队列），bulk RNA-seq 的 DEG→生存→PPI→免疫→甲基化管道已被同领域数十篇文献验证为可行路径。五个维度环环相扣——DEG 提供候选池，生存筛选缩小范围，PPI 提供网络级压缩依据，免疫浸润为 hub 基因提供功能语境，甲基化提供上游调控证据。

---

## B. 四档配置总览

| 维度 |  Lite | **Standard ⭐推荐** | Advanced | Publication+ |
|------|-------|---------------------|----------|--------------|
| **目标** | 2–4 周探索性验证 | 常规生信论文 | 竞争性期刊 | 高影响力投稿 |
| **数据** | TCGA-LUAD 单队列 | TCGA-LUAD + 2 个 GEO 验证队列 | TCGA + GEO×3 + 独立数据库（GEPIA2/Ualcan） | TCGA + GEO×3 + CPTAC 蛋白 + 组织验证 |
| **DEG** | DESeq2 TCGA-LUAD | DESeq2 TCGA-LUAD + limma GEO×2 | 三队列 Meta-DEG + robust rank aggregation | 多队列 Meta-DEG + batch-effect 校正 |
| **生存** | 单变量 KM + Cox 初步筛选 | KM + 单/多变量 Cox + LASSO-Cox 建模 | + 竞争风险模型 + 时间依赖 ROC | + 独立验证队列建模 + bootstrap 验证 |
| **PPI / Hub** | STRING 网络 + Degree Top5 | STRING + MCODE 聚类 + 5 种拓扑算法（Degree/Betweenness/Closeness/MCC/MNC）交集 → 3–5 hub | + 共表达网络 (WGCNA) 关键模块取交集 | + CPTAC 蛋白互作验证 + 分子对接 |
| **预后/诊断评估** | KM 曲线 + 基础 ROC | KM + 多变量 Cox + 诊断 ROC + 列线图 + 校准曲线 | + 决策曲线分析（DCA）+ 时间依赖 ROC | + 跨队列一致性分析 + 亚组分析 |
| **免疫浸润** | CIBERSORT 22 种免疫细胞（TCGA） | CIBERSORT + ESTIMATE + TIMER 验证 + 免疫检查点相关性 | + ssGSEA/TIDE + 免疫亚型关联 | + scRNA-seq 验证（公共数据） |
| **甲基化** | ❌ 无 | 450K/850K 阵列（TCGA LUAD）+ 启动子 CpG-表达相关性 + 甲基化生存 KM | + MEXPRESS 多基因验证 + CpG 岛注释 | + 独立队列甲基化验证 + 功能实验 |
| **临床关联** | 基础分期/年龄关联 | + 多变量分析 + 独立预后因子 | + 亚组交互分析 + 治疗反应预测 | + 真实世界队列关联 |
| **工作量** | 2–4 周 | 8–12 周 | 14–20 周 | 20–30 周 |
| **图表数量** | 6–8 | 12–15 | 16–20 | 20–25 |
| **优势** | 快速产出，概念验证 | 全覆盖，研究完整 | 深度增强，竞争性强 | 最高防御性 |
| **劣势** | 无外部验证，证据弱 | 外部验证仅 GEO | 工作量显著增加 | 需湿实验资源 |

---

## C. 推荐主方案：Standard

**推荐理由**：

Standard 方案是唯一能够完整体现用户所要求五大维度（DEG、预后模型、PPI hub 基因、免疫浸润、甲基化）的最低门槛配置：

- **Lite** 缺少外部验证队列和甲基化模块，无法同时满足所有五个维度的分析
- **Advanced** 引入了额外的方法层（竞争风险、WGCNA、DCA、scRNA-seq 验证），提高门槛但不改变核心逻辑，适合在 Standard 完成后再升级
- **Publication+** 需要湿实验资源（组织验证、蛋白验证），超出纯计算范畴

Standard 以 TCGA-LUAD 为发现队列，2 个 GEO 独立队列为验证，完整的 DEG→生存→PPI→hub→预后评估→免疫→甲基化的链路，图 12–15 张，适合投递 3–5 分生物信息学期刊。

**对其他配置的说明**：
- **Lite**：适合作为预实验/开题验证，不能作为完整论文
- **Advanced**：如果目标是 IF>6 的期刊，直接选
- **Publication+**：需要合作实验室提供组织样本

---

## C.5. 依赖图 / 证据图

### Standard（推荐方案）

**存在的证据层及依赖关系**：

| 证据层 | 数据来源 | 下游依赖步骤 |
|--------|---------|-------------|
| 肿瘤 vs 正常差异表达 | TCGA-LUAD raw counts | 所有后续步骤的候选基因池 |
| 外部验证 DEG | GEO 队列×2 | 跨队列一致性、稳健性 |
| 生存关联 | TCGA 临床随访 + 外部队列 | LASSO-Cox 模型、hub 基因筛选 |
| PPI 网络拓扑 | STRING 数据库 | hub 基因压缩 |
| 预后模型（列线图） | TCGA 多变量 Cox | 临床可用性评估 |
| 诊断评估（ROC） | TCGA 表达数据 | 诊断效能判定 |
| 免疫浸润（CIBERSORT） | TCGA bulk RNA-seq | 微环境语境化 |
| 免疫检查点关联 | TCGA 表达 + TIMER | 免疫治疗潜力假设 |
| 启动子甲基化 | TCGA 450K/850K 阵列 | 甲基化-表达调控证据 |
| 临床关联 | TCGA 临床注释 | 独立预后因子判定 |

**Absent 模块及禁止的声明**：
- Absent：湿实验验证 → **禁止**：hub 基因功能验证结论、蛋白水平结论
- Absent：scRNA-seq 数据 → **禁止**：细胞类型特异性表达结论
- Absent：独立甲基化队列 → **禁止**：甲基化因果性声明

### Minimal Executable Version

**存在的证据层**：
- DEG (TCGA-LUAD only)
- 单变量 KM 生存筛选
- STRING PPI + Degree top 3 hub
- 基础 KM 预后曲线
- 诊断 ROC 单队列

**Absent 全部模块** → **禁止**：外部验证结论、甲基化结论、免疫浸润结论、多变量 Cox 独立性声明、列线图、校准曲线

---

## D. Step-by-Step 分步工作流

> **Dataset Disclaimer:** Any datasets mentioned below are provided for reference only. Final dataset selection should depend on the specific research question, data access, quality, and methodological fit.

---

### Module 1：数据获取与预处理

| 字段 | 内容 |
|------|------|
| **目标** | 获取 LUAD 多队列 bulk RNA-seq 表达数据、临床随访数据和甲基化阵列数据 |
| **输入** | 无 |
| **工具/数据库** | TCGA（GDC Data Portal）、GEO（NCBI）、UCSC Xena |
| **关键决策** | TCGA-LUAD 作为发现队列（raw counts）；GEO 队列优先选包含 OS 随访的 LUAD 数据集（如 GSE72094、GSE13213）；甲基化数据用 TCGA-LUAD 的 Illumina 450K 平台 |
| **输出** | 三个矩阵：(1) 表达矩阵 (raw counts + normalized); (2) 临床表型表（OS、DFS、分期、年龄、性别、吸烟）; (3) 甲基化 β 值矩阵 |
| **预期结果** | TCGA-LUAD ~500 肿瘤 + ~59 正常样本; GEO 各 ~200–400 肿瘤样本 |
| **潜在问题** | TCGA 正常样本少（只有 59 例配对的癌旁组织），DEG 统计势可能不足 → 补救：用 GTEx 肺正常组织扩大正常对照池 |
| **依赖** | 无前置步骤 |

#### Endpoint formula for DEG:
**DEG = |log2FC| > 1.0 且 adjusted p-value < 0.05** (DESeq2, TCGA-LUAD raw counts)

---

### Module 2：差异表达基因 & 一致性筛选

| 字段 | 内容 |
|------|------|
| **目标** | 识别 LUAD 中稳定且跨队列一致的 DEG |
| **输入** | TCGA raw counts + GEO 独立队列（如 GSE72094、GSE13213 使用 limma） |
| **工具/方法** | **DESeq2**（TCGA raw counts 输入），**limma**（GEO 归一化矩阵输入） |
| **关键决策** | **DESeq2 用于 TCGA 的 raw count 数据**（遵循技能硬规则 1）；**limma 用于 GEO 归一化矩阵**。阈值：|log2FC| > 1.0，FDR < 0.05。跨队列一致性：至少 2/3 队列方向一致的 DEG 保留 |
| **输出** | 跨队列稳定 DEG 列表（预计 500–1500 基因） + 火山图 + 热图 |
| **预期结果** | LUAD 经典 DEG：SPP1、MMP11、COL11A1、TOP2A、CDK1 等上调；AGER、CLDN18、FABP4 等下调 |
| **潜在问题** | TCGA 正常对照少 → **补救**：纳入 GTEx Lung 正常组织（~300 样本）扩展对照池 |
| **依赖** | Module 1 的表达矩阵 |

#### Endpoint formula:
**DEG(TCGA) = DESeq2(TCGA raw counts): |log2FC| > 1, padj < 0.05**
**DEG(GEO) = limma(GEO normalized matrix): |log2FC| > 1, padj < 0.05**
**Stable DEG = DEG(TCGA) ∩ (DEG(GEO1) 同向 或 DEG(GEO2) 同向)**

---

### Module 3：生存分析与预后基因筛选

| 字段 | 内容 |
|------|------|
| **目标** | 从稳定 DEG 中筛选与总生存期（OS）显著相关的基因 |
| **输入** | 稳定 DEG 表达矩阵 + TCGA 临床 OS 数据 |
| **工具/方法** | **survival R 包**：单变量 Cox 回归（p < 0.05）→ KM 曲线（log-rank p < 0.05） |
| **关键决策** | 在 TCGA 中做发现，在外部队列中验证。取交集：至少在 TCGA + 1 个外部验证队列中均显著的基因保留为预后相关基因集 |
| **输出** | 预后相关基因列表（预计 50–150 个）+ KM 生存曲线（森林图） |
| **预期结果** | 典型的 LUAD 预后基因：TOP2A、IL6、SPP1、MMP9、MKI67 等 |
| **潜在问题** | 单一队列假阳性 → **补救**：多队列取交集；使用 bootstrap 验证 |
| **依赖** | Module 2 的稳定 DEG |

#### Endpoint formula:
**Prognostic Genes = Stable DEG ∩ (单变量 Cox p < 0.05 in TCGA) ∩ (单变量 Cox p < 0.05 in ≥1 external cohort)**

---

### Module 4：LASSO-Cox 风险模型构建

| 字段 | 内容 |
|------|------|
| **目标** | 从预后基因中构建精简的风险评分模型 |
| **输入** | 预后基因表达矩阵 + TCGA OS |
| **工具/方法** | **glmnet R 包**：LASSO 回归（10-fold CV 选 λ）→ Cox 比例风险模型 |
| **关键决策** | LASSO 自动收缩变量，最终保留 3–15 个基因。风险评分 = Σ(βᵢ × Exprᵢ)。将 TCGA 患者按中位值分为高危/低危组，KM 验证 |
| **输出** | 风险评分公式 + 高低危组 KM 曲线 + 时间依赖 ROC（1/3/5 年 AUC） |
| **预期结果** | AUC > 0.65 在 TCGA 中发现，> 0.60 在验证集中 |
| **潜在问题** | 过拟合 → **补救**：外部验证队列计算同样评分，检验一致性 |
| **依赖** | Module 3 的预后基因 |

#### Endpoint formula:
**Risk Score = Σ(βᵢ × Exprᵢ)，基因集由 LASSO 的 λ.1se 确定**
**风险分组：以 TCGA 中位 Risk Score 为 cutpoint，外部队列使用相同 cutpoint**

---

### Module 5：PPI 网络构建与 Hub 基因挖掘

| 字段 | 内容 |
|------|------|
| **目标** | 通过蛋白互作网络将预后基因压缩为 3–5 个核心 hub 基因 |
| **输入** | 预后基因列表（Module 3 输出的 50–150 基因） |
| **工具/方法** | **STRING** (v12.0, confidence score > 0.4) → **Cytoscape** (v3.9+) + **cytoHubba** 插件 |
| **关键决策** | 五种拓扑算法取交集：Degree、Betweenness Centrality、Closeness Centrality、MCC（Maximal Clique Centrality）、MNC（Maximum Neighborhood Component）。取至少 3/5 算法 Top10 的交集基因为 hub 基因。再用 **MCODE** 聚类识别关键功能模块 |
| **输出** | 3–5 个 hub 基因 + PPI 网络图（节点颜色按 Degree，大小按 Betweenness）+ MCODE 模块 |
| **预期结果** | hub 基因应为网络中的高连接度节点，MCODE 模块与细胞周期/免疫应答等功能相关 |
| **潜在问题** | STRING 包含了预测互作（非全实验验证）→ 声明限制：仅作为网络级压缩依据，非蛋白互作验证 |
| **依赖** | Module 3 的预后基因 |

#### Endpoint formula:
**Hub Genes = Prognostic Genes ∩ (同属于 Degree Top10 ∪ Betweenness Top10 ∪ Closeness Top10 ∪ MCC Top10 ∪ MNC Top10，且至少 3/5 算法确认)**

---

### Module 6：预后与诊断评估

| 字段 | 内容 |
|------|------|
| **目标** | 评估 hub 基因和风险模型对 LUAD 的预后及诊断性能 |
| **输入** | Hub 基因表达 + 风险评分 + 临床变量 |
| **工具/方法** | **survival/survminer**（KM+森林图）; **pROC R 包**（诊断 ROC）; **rms R 包**（列线图+校准曲线） |
| **关键决策** | (1) 诊断 ROC：每个 hub 基因独立 AUC + 联合 AUC; (2) 列线图：风险评分 + 年龄 + 分期 → 预测 1/3/5 年 OS; (3) 森林图确认变量独立性 |
| **输出** | 诊断 ROC 曲线（单基因+联合）; 列线图+校准曲线; 多变量 Cox 森林图 |
| **预期结果** | Hub 基因联合 AUC > 0.85; 列线图 C-index > 0.68 |
| **潜在问题** | 列线图仅内部验证 → **补救**：用外部队列评估相同列线图的 C-index |
| **依赖** | Module 4 的风险评分 + Module 5 的 hub 基因 |

---

### Module 7：免疫浸润分析

| 字段 | 内容 |
|------|------|
| **目标** | 分析 hub 基因表达与肿瘤免疫微环境的关系 |
| **输入** | TCGA-LUAD 表达矩阵 + hub 基因列表 |
| **工具/方法** | **CIBERSORT**（22 种免疫细胞分数）; **ESTIMATE**（免疫/基质评分）; **TIMER 2.0** 数据库验证; 免疫检查点基因相关性分析 |
| **关键决策** | (1) CIBERSORT 推断 TCGA 中每个样本的 22 种免疫细胞比例; (2) 按 hub 基因中位表达分组，比较高低表达组的免疫细胞差异; (3) 计算 hub 基因与 CD274(PD-L1)、CTLA4、PDCD1、LAG3、TIGIT 的 Spearman 相关性 |
| **输出** | 免疫细胞差异箱线图（Wilcoxon）; 免疫评分/基质评分差异; 免疫检查点相关性热图 |
| **预期结果** | 部分 hub 基因高表达可能关联免疫抑制微环境（如 Treg ↑、M2 巨噬细胞 ↑），为免疫治疗提供假设 |
| **潜在问题** | CIBERSORT 是反卷积推断，非实验值 → 声明为"计算推断"，不宣称细胞比例的真实值 |
| **依赖** | Module 1 的表达矩阵 + Module 5 的 hub 基因 |

---

### Module 8：甲基化调控分析

| 字段 | 内容 |
|------|------|
| **目标** | 分析 hub 基因启动子区 CpG 甲基化与基因表达及预后的关联 |
| **输入** | TCGA-LUAD Illumina 450K 甲基化 β 值矩阵 + 表达矩阵 + 临床 OS |
| **工具/方法** | **ChAMP / minfi R 包**（甲基化预处理）; **Spearman 相关性**（CpG-表达）; **MEXPRESS** 数据库验证 |
| **关键决策** | (1) 提取每个 hub 基因启动子区（TSS ± 1500bp）的所有 CpG 探针; (2) Spearman 相关性分析 CpG β 值 vs 基因表达（rho < -0.3 且 p < 0.05）; (3) 以 CpG 中位 β 值分组做 KM 生存分析; (4) 用 **MEXPRESS** 在线工具验证可视化 |
| **输出** | CpG-表达负相关散点图; CpG 甲基化 KM 曲线; MEXPRESS 多基因可视化截图 |
| **预期结果** | 至少 1–2 个 hub 基因的启动子区存在显著负相关 CpG（promoter hypermethylation → reduced expression → 与更好/更差预后关联） |
| **潜在问题** | 甲基化-表达相关性不等于因果调控 → 声明为"关联证据"，不宣称因果关系; 独立甲基化队列验证缺失 → 仅在 TCGA 中做分析 |
| **依赖** | Module 1 的甲基化矩阵 + Module 5 的 hub 基因 |

---

### Module 9：临床关联分析

| 字段 | 内容 |
|------|------|
| **目标** | 评估 hub 基因/风险评分与临床病理特征的关联 |
| **输入** | Hub 基因表达 + 风险评分 + 临床变量 |
| **工具/方法** | **R base** (t-test/Wilcoxon/ANOVA) + 多变量逻辑回归 |
| **关键决策** | (1) 按临床分期、TNM 分期、年龄、性别、吸烟史分组比较 hub 基因表达差异; (2) 多变量 Cox 回归确认风险评分和 hub 基因是否为独立预后因子（校正年龄、分期、性别）; (3) 亚组 KM 分析（早期 vs 晚期、男 vs 女） |
| **输出** | 箱线图（分期 vs 表达）; 多变量 Cox 森林图; 亚组 KM 曲线 |
| **预期结果** | 风险评分是独立于 TNM 分期的预后因子 |
| **潜在问题** | 回顾性数据的选择偏倚 → 声明限制 |
| **依赖** | Module 1 的临床表型数据 + Module 4 的风险评分 + Module 5 的 hub 基因 |

---

## E. 图表与交付物计划

| 图序 | 内容 | 类型 | 所属模块 |
|------|------|------|----------|
| Fig 1 | 研究设计流程图 | 示意图 | M1–M9 |
| Fig 2 | DEG 火山图 + 热图 (TCGA-LUAD) | 可视化 | M2 |
| Fig 3 | 跨队列 DEG 一致性韦恩图 + 交集基因热图 | 可视化 | M2 |
| Fig 4 | 预后基因单变量 Cox 森林图 | 统计图 | M3 |
| Fig 5 | LASSO 系数收缩图 + Cross-Validation | 方法图 | M4 |
| Fig 6 | 风险评分 KM 曲线 (TCGA + 外部队列×2) | 生存图 | M4 |
| Fig 7 | 时间依赖 ROC (1/3/5yr) | 诊断图 | M4 |
| Fig 8 | PPI 网络图 + Hub 基因标注 + MCODE 模块 | 网络图 | M5 |
| Fig 9 | Hub 基因诊断 ROC (单基因+联合) | 诊断图 | M6 |
| Fig 10 | 列线图 + 校准曲线 (1/3/5yr) | 预后图 | M6 |
| Fig 11 | CIBERSORT 免疫浸润差异箱线图 | 免疫图 | M7 |
| Fig 12 | 免疫检查点基因相关性热图 | 免疫图 | M7 |
| Fig 13 | Hub 基因启动子 CpG 甲基化-表达散点图 | 甲基化图 | M8 |
| Fig 14 | CpG 甲基化 KM 生存曲线 | 甲基化图 | M8 |
| Fig 15 | 临床关联多变量 Cox 森林图 + 亚组分析 | 临床图 | M9 |
| Table 1 | 四队列临床基线资料表 | 表格 | M1 |
| Table 2 | Top 20 DEG 列表 + 外部验证统计 | 表格 | M2 |
| Table 3 | Hub 基因五种拓扑算法评分 | 表格 | M5 |
| Table 4 | 多变量 Cox 回归完整结果 | 表格 | M9 |

---

## F. 验证与稳健性

### 证据层级框架

| 证据层级 | 本方案提供的证据 | 不能证明什么 |
|----------|-----------------|------------|
| **关联层** (Association) | DEG 存在、生存相关、免疫浸润关联、甲基化关联 | 不证明因果调控 |
| **预后层** (Prognostic) | 风险评分可分层患者、列线图预测 OS、外部队列一致 | 不直接指示治疗选择 |
| **诊断/转化效用层** (Diagnostic/Translational Utility) | ROC 显示区分肿瘤 vs 正常的能力 | 不可作为筛查工具；无前瞻性验证 |
| **功能支持层** (Functional Support) | PPI 网络拓扑提示功能模块；免疫推断提示微环境语境 | 不证明蛋白互作真实性、不证明免疫机制 |
| **调控支持层** (Regulatory Support) | 甲基化-表达负相关 | 不证明表观遗传因果关系 |

### 每一步验证的依赖与限制

| 步骤 | 验证了什么 | 依赖于 | 如果依赖缺失则不可用 |
|------|-----------|--------|---------------------|
| M2 DEG | 基因表达在肿瘤 vs 正常中差异 | TCGA 正常对照 + GEO 队列 | 无验证队列 → DEG 仅为单队列发现 |
| M3 生存 | 基因表达与预后关联 | 完整 OS 随访 | 随访缺失 → 无法筛选预后基因 |
| M4 LASSO | 多基因联合预后能力 | 外部验证队列 | 无外部验证 → 过拟合风险高 |
| M5 PPI hub | 网络级基因重要性 | STRING 数据库覆盖率 | 覆盖率低 → hub 基因代表性下降 |
| M6 列线图 | 个体化预后预测 | 多队列验证 | 仅内部验证 → 校准高估 |
| M7 免疫 | 免疫微环境推断 | CIBERSORT 算法假设 | 仅为推断，不可替代流式/scRNA |
| M8 甲基化 | 表观遗传关联 | 450K 探针覆盖启动子 | 无启动子探针 → 该基因不可分析 |

---

## G. Minimal Executable Version

**2–4 周可执行的最小版本**（是 Lite 的严格子集）：

| 步骤 | 内容 | 工具 | 输出 |
|------|------|------|------|
| 1 | 从 TCGA-LUAD 下载 raw counts + 临床数据 | TCGA GDC / TCGAbiolinks | 表达矩阵 + 临床表 |
| 2 | DESeq2 DEG（|log2FC|>1, padj<0.05） | DESeq2 R 包 | ~1000 DEG |
| 3 | 单变量 Cox 筛选预后基因（p<0.05） | survival R 包 | ~80 预后基因 |
| 4 | STRING PPI + cytoHubba Degree Top 5 | STRING + Cytoscape | 5 个候选 hub |
| 5 | KM 生存曲线（TCGA） | survminer | 每个 hub 的 KM 图 |
| 6 | 诊断 ROC（单基因 + 联合） | pROC | AUC 值 |

**此版本不包含**：外部验证队列、LASSO-Cox 模型、列线图、免疫浸润、甲基化、多队列生存验证、MCODE 聚类、多算法 hub 筛选。

**Endpoint formula**：DEG ∩ (单变量 Cox p < 0.05 in TCGA only) ∩ (STRING Degree Top5) → 5 hub 基因

**禁止声明**：外部验证、免疫机制、甲基化调控、独立预后、临床应用价值、跨队列普适性。

---

## H. 发表升级路径

以下按优先级排列，从 Standard 升级到 Advanced / Publication+：

| 优先级 | 新增模块 | 升级类型 | 从哪一层引入 | 启用新证据层 |
|--------|---------|---------|-------------|------------|
| 1 | WGCNA 共表达模块 | 稳健性升级 | Advanced | DEG × 共表达双交集的候选基因 |
| 2 | 竞争风险模型（competing risks） | 方法学升级 | Advanced | 排除非肿瘤死亡的混淆 |
| 3 | 决策曲线分析 (DCA) | 转化效用升级 | Advanced | 临床净获益评估 |
| 4 | ssGSEA + TIDE 预测免疫治疗反应 | 免疫深度升级 | Advanced | 免疫亚型 + ICB 反应假设 |
| 5 | MEXPRESS 多基因甲基化-表达联合可视化 | 甲基化升级 | Advanced | 更直观的调控证据 |
| 6 | scRNA-seq 公共数据验证 hub 基因的细胞定位 | 功能深度升级 | Publication+ | 细胞类型特异性表达 |
| 7 | CPTAC 蛋白表达一致性验证 | 蛋白层升级 | Publication+ | 蛋白水平证据 |
| 8 | 组织芯片 IHC 或实时定量 PCR 验证 | 实验验证升级 | Publication+ | 湿实验证据（最高层） |
| 9 | 分子对接（hub 蛋白 vs 候选药物） | 转化升级 | Publication+ | 药物靶向假设 |

---

## I. 参考文献包

> **注意**：学术搜索 API 返回空结果（后端服务不可用），无法在此会话中验证 DOI 和稳定链接。以下提供每个模块的**搜索策略和证据缺口**，替代直接引用。每个模块标注需要什么类型的文献、推荐搜索词、和待验证的信息。待搜索服务恢复后，可据此检索真实文献。

### I1. 癌症 / 生物学背景参考

**搜索策略**：
- 查询词：`"lung adenocarcinoma molecular pathology review"`、`"LUAD genomic landscape TCGA 2024"`
- 目标期刊：Nature Reviews Cancer, Cancer Discovery, Cell, Lancet Oncology
- 所需类型：2 篇 LUAD 分子病理综述 + 1 篇中国肺癌流行病学 + 1 篇 TCGA LUAD 标志性论文

| 条目 | 类型 | 为何需要 | 证据缺口 |
|------|------|---------|---------|
| LUAD 分子分型与基因组特征综述 | Review | 为研究提供癌症生物学背景 | 无已验证的 DOI；推荐检索 Cancer Discovery 2014 LUAD 标志性论文 |
| 中国肺癌流行病学数据 | Original | 说明临床需求和疾病负担 | 推荐：中国国家癌症中心年度报告；NCCR 数据 |
| TCGA LUAD 多组学标志性论文 | Resource | 为本研究的 TCGA 数据使用提供依据 | 推荐：TCGA LUAD 2014 Nature 论文 (doi:10.1038/nature13385) |
| 肺癌生物标志物转化研究综述 | Review | 确立预后模型→生物标志物的研究范式 | 无已验证的 DOI |

### I2. 方法学论证参考

**搜索策略**：
- DEG：`"DESeq2 differential expression RNA-seq"` → Love et al. 2014 Genome Biology (doi:10.1186/s13059-014-0550-8)
- 生存：`"survival analysis Cox regression bioinformatics cancer"` → 需要查找方法学综述
- PPI：`"STRING protein-protein interaction network bioinformatics"` → Szklarczyk et al. 2023 NAR (doi:10.1093/nar/gkac1000)
- 免疫：`"CIBERSORT immune infiltration deconvolution"` → Newman et al. 2015 Nature Methods (doi:10.1038/nmeth.3337)
- 甲基化：`"ChAMP methylation array analysis"` → 需要查找 Moris et al. Bioconductor documentation

| 模块 | 需要参考文献 | 状态 |
|------|------------|------|
| DESeq2 DEG | Love MI, Huber W, Anders S. "Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2." Genome Biology, 2014 | 方法学论文，已稳定超过 10 年；DOI 可获取于 Bioconductor |
| STRING PPI | Szklarczyk D, et al. "STRING v12." NAR, 2023 | 数据库论文；DOI 可在 NAR 网站验证 |
| CIBERSORT | Newman AM, et al. "Robust enumeration of cell subsets from tissue expression profiles." Nature Methods, 2015 | 方法学论文；DOI 可在 Nature Methods 验证 |
| LASSO-Cox | Tibshirani R. "The lasso method for variable selection in the Cox model." Statistics in Medicine, 1997 | 方法学论文 |
| limma | Ritchie ME, et al. "limma powers differential expression analyses for RNA-sequencing and microarray studies." NAR, 2015 | 方法学论文 |
| TCGA LUAD | TCGA Research Network. "Comprehensive molecular profiling of LUAD." Nature, 2014 | 数据集论文 |

### I3. 同类研究先例

**搜索策略**：
- 查询词：`"LUAD prognostic signature hub gene TCGA GEO immune infiltration methylation"`
- 相似研究的常见特征：DEG → Cox → LASSO → PPI → hub → 免疫浸润 → 预后列线图

| 研究模式 | 癌症 | 关键模块 | 证据缺口 |
|---------|------|---------|---------|
| DEG → PPI → hub → 预后 + 免疫 | 多种癌种 | DEG + PPI + 免疫 | 无已验证的具体 DOI；PubMed 搜索 `"LUAD"[Title] AND "hub"[Title] AND "prognostic"[Title]` 可找到 50+ 类似论文 |
| LASSO-Cox 签名 + 列线图 | LUAD | 签名 + 列线图 | 同上类搜索 |
| 甲基化 + 表达 + 预后 | LUAD | 甲基化调控 | 查询词：`"LUAD methylation prognostic signature TCGA"` |

### I4. 证据缺口说明

| 缺口 | 描述 | 替代策略 |
|------|------|---------|
| ❌ 学术搜索 API 不可用 | speedai 学术搜索在此会话返回空 | 手工通过 PubMed / Google Scholar / Web of Science 检索上述搜索策略 |
| ❌ 未进入湿实验验证 | 本方案不包含功能实验 | 在 Discussion 中明确声明所有 hub 基因为计算筛选，需实验验证 |
| ❌ 中国 LUAD 人群特异性 | TCGA 以白种人为主 | 若有中国 LUAD 数据集（如 Oriental 队列），纳入验证或讨论中说明人群差异 |
| ❌ 单细胞分辨率缺失 | Standard 方案不含 scRNA-seq | 注明 CIBERSORT 为反卷积推断，非单细胞验证 |

---

## J. 自我批评性风险审查

### 1. 最强的部分

**多队列独立验证（TCGA + 2 个 GEO 队列）** 是本方案最可靠的证据层。三个独立数据集的一致 DEG 方向、一致生存关联和一致预后方向，大幅降低了单一平台的假阳性风险。这是方案的"锚点"——即使后续的 PPI hub 压缩或免疫推断存在争议，DEG 和生存发现仍有独立价值。

### 2. 假设依赖最强的部分

**CIBERSORT 免疫反卷积推断** 依赖 LM22 参考矩阵和细胞类型相对比例假设。如果 LUAD 肿瘤中存在大量未知细胞类型（如 CAF 亚群、新型免疫亚型），这些细胞的转录信号可能被错误归入已知 22 种免疫类别。此模块的正确性完全取决于反卷积算法的假设是否成立。

### 3. 最可能的假阳性来源

**PPI 网络中的预测互作边**。STRING 数据库包含大量基于共表达和文本挖掘的预测互作（非全由实验验证），这些"噪音边"可能使某些基因在网络中获得高拓扑得分（Degree/ Betweenness），但在真实的蛋白水平并无对应互作。三算法交集可部分缓解，但不能消除。

### 4. 最容易过度解读的结果

**甲基化-表达负相关关系**。即使 rho < -0.5 且 p < 10⁻⁶，这些关联仍然是观察性的、由单个平台的探针覆盖决定的。容易被解读为"表观遗传调控"，但实际上：
- 可能仅仅是共线性（同一探针覆盖区域的遗传多态性）
- 因果关系方向不确定（甲基化导致表达下降？还是低表达导致表观改变？）
- 缺少独立验证队列

**语言护栏**：使用"甲基化与表达呈现显著负相关(promoter CpG methylation is inversely correlated with gene expression)"而非"甲基化调控表达(regulates/silences expression)"。

### 5. 可能的审稿人批评

| 批评 | 预期来源 | 预留回应策略 |
|------|---------|------------|
| "TCGA 正常对照只有 59 例，DEG 稳健性不足" | 统计/生信审稿人 | 已用 GTEx 扩展对照池 + GEO 队列独立验证 |
| "CIBERSORT 推断不等于实际细胞比例" | 免疫学审稿人 | 结果中已注明"CiberSort-computed infiltration levels"，不宣称实际比例 |
| "无功能实验验证" | 实验学审稿人 | 在 Limitations 中明确声明，同时强调多队列计算验证的稳健性 |
| "甲基化 450K 与 850K 批次效应" | 方法学审稿人 | 若跨平台分析，使用 Combat 或 Seurat 的批次校正 |
| "hub 基因只来自一个 PPI 数据库" | 方法学审稿人 | 补充使用 BioGRID 或 IntAct 作为独立 PPI 数据库的一致性验证 |
| "LASSO 未与 Random Forest / Elastic Net 比较" | 方法学审稿人 | 可补充 RF + Elastic Net 的灵敏度分析作为 supplementary |

### 6. 特征崩溃时的降级方案

| 如果... | 降级到... |
|---------|----------|
| 外部验证队列中 DEG 方向不一致 | 报告为单队列发现（TCGA only）并标注为探索性研究 |
| LASSO 选择基因数 > 15 或 < 3 | 使用 Elastic Net（α = 0.5）替代纯 LASSO |
| Hub 基因交集为空（五算法无一致） | 降级为 Degree + MCC 二算法交集，或取中位数排名综合得分 |
| 甲基化分析中所有 hub 基因均无显著启动子 CpG | 移除此模块并修订论文为纯预后+免疫研究（4 维度） |
| 列线图 C-index 外部验证 < 0.60 | 撤回列线图模块，仅报告 KM 和多变量 Cox |
| 免疫检查点相关性均不显著 | 移除此分析或报告为此方向的阴性发现 |

---

> ⚠ **Disclaimer**: This plan is for computational / translational research design only. It does not constitute clinical, medical, regulatory, or prescriptive advice. All biomarker and mechanism claims require experimental and/or clinical validation before application.

---

*方案生成时间：2025-07*
*技能版本：conventional-oncology-hub-gene-research-planner v1.0*
*默认癌症背景：LUAD (Lung Adenocarcinoma)*
