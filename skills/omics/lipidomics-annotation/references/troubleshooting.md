# 排错手册：脂质组注释与 lipidr 工作流

原则：**先判断问题出在"命名"还是"数值"还是"统计设计"**。脂质组 80% 的报错来自命名解析，15% 来自归一化/缺失，5% 来自对比式写错。

---

## 1. 命名解析类

### 1.1 `annotate_lipids()` 返回 `not_matched = TRUE` / `ambig = TRUE`

官方函数的输入契约（逐字）："Lipids should follow the pattern 'class xx:x/yy:y', with class referring to the abbreviated lipid class, xx:x as the composition of the first chain and yy:y as the second chain. Alternatively, lipids can be supplied following the pattern 'class zz:z'"。
来源：<https://www.lipidr.org/reference/annotate_lipids.html>

排查顺序：

1. 用 `non_parsed_molecules()` 把失败清单拉出来（索引：<https://www.lipidr.org/reference/index.html>）。
2. 逐条对照上面两种模式：
   - 有 `/` → 必须是 `class 16:0/18:1` 形态（类别 + 空格 + 链）；
   - 无 `/` → 必须是 `class 34:1` 形态。
3. 修复用 `update_molecule_names()`（官方："Rename molecules in a dataset."）。
4. 确实解析不了的名字用 `remove_non_parsed_molecules()` 剔除，**并在报告里写明剔除了多少个、占比多少**。

不要做的：手写正则去"猜"类别。官方已经有 `class_stub`/`Class` 两列，自造解析只会与官方口径分叉。

### 1.2 MS-DIAL 导出的 `PC 18:0_20:4` 在 lipidr 里解析不了

**原因**：MS-DIAL 的 "chain separated" 写法用下划线（官方表：`PC 38:4` = chain summed，`PC 18:0_20:4` = chain separated，见 <https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>），而 lipidr 官方文档只写了 `'class xx:x/yy:y'` 与 `'class zz:z'` 两种模式。

**处理**：先用 `annotate_lipids()` 实测（不是推断）这些名字落到 `not_matched` 还是被当作 `zz:z` 解析；根据实测结果决定是否 `update_molecule_names()` 换成 `/` 形态。**注意语义**：把 `_` 改成 `/` 会凭空把"位置未知"升级成"sn 位置已知"——如果原数据没有 sn 证据，正确做法是把它降到 species 级（`PC 38:4`），而不是改成 `PC 18:0/20:4`。

### 1.3 醚脂 / 缩醛磷脂前缀被吃掉

`PC(O-34:2)`、`PC(P-36:5)` 这类名字，前缀是结构信息（`O-` = 烷基醚，`P-` = (1Z)-烯基醚，见 <https://www.lipidmaps.org/lipid_nomenclature> 第 13 条）。若解析后 `class_stub` 变成 `PC` 而前缀丢失，`Class` 分组就会把醚脂和酯脂混在一起做 `lsea`，结论直接错。

自查：解析后单独 `table(rowData(d)$class_stub)`，确认 `PCO`/`PCP` 这类 stub 是否存在（lipidr 官方示例数据里就同时存在 `PC(O-34:2)` 与 `PC(P-34:2)`，见 <https://www.lipidr.org/reference/de_analysis.html> 的 `significant_molecules` 输出）。

### 1.4 同位素标记内标名（如 `15:0-18:1(d7) PC`）

官方数据里就存在这种写法，并被正确标为 `istd = TRUE`（`read_skyline` 示例输出第 279 行：`15:0-18:1(d7) PC`，`istd` 列 `TRUE`）。
来源：<https://www.lipidr.org/reference/read_skyline.html>

用途：`normalize_itsd()` 依赖 `istd` 标记来配对类别内标（官方："Lipid classes are normalized using corresponding internal standard(s) of the same lipid class. If no corresponding internal standard is found the average of all measured internal standards is used instead."，<https://www.lipidr.org/reference/normalize_istd.html>）。
**若 `istd` 列全为 FALSE**：说明名字没被识别成内标，此时 `normalize_itsd()` 会退化成"所有内标均值"甚至无可配对——必须先修名字，不要硬跑。

### 1.5 重复脂质名把对象变成"未 summarized"

`as_lipidomics_experiment()` 的官方行为："The data is considered `summarized` unless at least one lipid is duplicated (has > 1 row)."
来源：<https://www.lipidr.org/reference/as_lipidomics_experiment.html>

所以同一条脂质出现多行（多 transition、多 adduct、正负模式分开）时，必须先 `summarize_transitions(data, method = "average")`（或 `"max"`，默认 `max`）。否则后续 `normalize_pqn` / `de_analysis` 拿到的是重复行。

> 官方数据里还有 `PE 34:1 NEG` 这种"正负模式分行"的命名（<https://www.lipidr.org/reference/read_skyline.html> 示例）。若同一脂质在两极各测一次，合并前要决定是取均值还是保留两条——这是分析决策，需写入 provenance。

---

## 2. 读入与样本注释类

### 2.1 `read_skyline()` 读不到样本名 / 只有一列

官方导出要求（逐字）：
- "Integrated peaks should be exported from each Skyline file through File => Export => Report. Selecting `Transition Results` ensures that necessary information is exported from Skyline. Otherwise, you should ensure that peak `Area` or `Height` or a similar measure is exported."
- "`Replicates` should either be exported, or the `Pivot Replicate Name` option must be used."

来源：vignette 源文 <https://raw.githubusercontent.com/ahmohamed/lipidr/f5fb8d5421b8341e76f66f545154bae01e0aa62d/vignettes/workflow.Rmd>；Bioconductor 渲染版 <https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.19/bioc/vignettes/lipidr/inst/doc/workflow.html>

→ 先回去改 Skyline 报告模板，不要在 R 里硬拼列名。

### 2.2 非 Skyline 数据（MS-DIAL / MZmine / XCMS 导出的矩阵）

走 `as_lipidomics_experiment(df, logged = FALSE, normalized = FALSE)`：行=脂质、列=样本、脂质名在首列或 rownames、数值型。
来源：<https://www.lipidr.org/reference/as_lipidomics_experiment.html>

`logged` / `normalized` 两个开关是**声明**而非计算：声明错了会让后续 `de_analysis`（要求 "should be normalized and log2 transformed"）在错误前提上运行。用 `is_logged()` / `is_normalized()` 自查（索引：<https://www.lipidr.org/reference/index.html>）。

### 2.3 分组列被当成连续变量

`mva()` 官方示例会给出这类警告（逐字）："The following aesthetics were dropped during statistical transformation: label … Did you forget to specify a `group` aesthetic or to convert a numerical variable into a factor?"（<https://www.lipidr.org/reference/mva.html>）

→ 分组列必须是字符/因子，数值列（如剂量、时间）在 OPLS 里才是 y 变量。

---

## 3. 归一化与缺失类

### 3.1 `normalize_pqn` 的官方警告

官方示例输出（逐字）：`Warning: Area contains missing/non-finite values. Replacing with mimnum detected value.`（原文拼写即为 `mimnum`）
来源：<https://www.lipidr.org/reference/normalize_pqn.html>

含义：缺失值被替换为**最小检出值**。这是有偏的填补（会把缺失压到分布左端）。若缺失率高（>20%），先按 `metabolomics-profiling` 的缺失处理规则决策，再归一化；否则"某组缺失多"会伪装成"某组下调"。填补策略必须写进 provenance。

### 3.2 blank 没被排除

`exclude = "blank"` 是**自动按样本名/分组识别空白**。若你的空白命名不规范（如 `Blank_1` vs `blank`），可能漏识别，导致 PQN 参考谱被污染。
自查：`d$group` 里 blank 的实际取值；必要时改用 `exclude` 传**逻辑向量**（官方支持："logical vector with the same length as samples"，<https://www.lipidr.org/reference/normalize_pqn.html>）。

### 3.3 归一化方法选错（最常见的方法学错误）

| 情形 | 用哪个 | 官方依据 |
|---|---|---|
| 有意设计的内标、且每类都有同类内标 | `normalize_itsd()` | "corrects lipid class-specific variations between samples"（<https://www.lipidr.org/reference/normalize_istd.html>） |
| 没有类别内标 / 内标覆盖不全 | `normalize_pqn()` | 以"average lipid abundance of all samples (excluding blanks)"为参考谱（<https://www.lipidr.org/reference/normalize_pqn.html>） |

两者**不是二选一的风格偏好**：PQN 修正样本级稀释，内标修正类别级偏移，修的误差源不同。

### 3.4 QC 不过

看三条官方图：`plot_samples(d, type = "tic", log = TRUE)`、`plot_molecules(d_qc, "cv", measure = "Area")`、`plot_lipidclass(d, "boxplot")`。
→ 阈值判据（QC-RSD ≤ 30%，严格 20%）沿用 `metabolomics-profiling`；lipidr 只给 `filter_by_cv(data, cv.cutoff = 20, measure = "Area")` 这个过滤器，**不给"该不该过滤"的判断**。

---

## 4. 差异分析与富集类

### 4.1 `de_analysis` 报对比式解析失败

- 对比式是**交给 `limma::makeContrasts` 的表达式**（官方："These are passed to `limma::makeContrasts`"，<https://www.lipidr.org/reference/de_analysis.html>），所以写法必须是 `A - B` 形式，且 A/B 必须**逐字等于** `colData` 里分组列的取值组合。
- 官方示例的分组值是 `HighFat_water`、`NormalDiet_water`（下划线连接的组合名）。若你的 `group` 列是 `HighFat` 与 `water` 两列，就不会有 `HighFat_water` 这个 level —— 需要先合成一列，或用 `de_design()` 走设计矩阵。

### 4.2 复杂设计（协变量、交互）

用 `de_design()`，官方两种写法（逐字）：

```r
# Using formula
de_design(data=d_normalized, design = ~ group, coef="groupHighFat_water", measure="Area")

# Using design matrix
design = model.matrix(~ group, data=colData(d_normalized))
de_design(data=d_normalized, design = design, coef="groupHighFat_water", measure="Area")
```

官方把更复杂设计的说明指向 limma User Guide 与 edgeR UsersGuide（同页链接）。→ 多因素/交互项**按 limma 官方文档**构造 design，本技能不另造公式。

### 4.3 `significant_molecules()` 一个都没有

三个官方默认值先核对：`p.cutoff = 0.05`、`logFC.cutoff = 1`（即 |log2FC| ≥ 1）。多组（ANOVA-style）比较时 `logFC.cutoff` **被忽略**（官方明示）。若仍为空：

1. 确认输入是 normalized + log2（4.1）；
2. 确认 n（每组生物学重复数），小样本下 `adj.P.Val` 很难过；
3. 不要为了出结果去改 `p.cutoff`——先看 `plot_results_volcano()` 的效应量分布。

### 4.4 `lsea` 的 ties 警告

官方示例输出（逐字）：`Warning: There are ties in the preranked stats (5.78% of the list). The order of those tied genes will be arbitrary, which may produce unexpected results.`
来源：<https://www.lipidr.org/reference/lsea.html>

成因：同分异构/同名脂质在 `logFC` 上完全相等（很常见，因为同类别同链属性的脂质被同一批离子对覆盖）。处理：

- 报告里说明 tie 的比例（官方示例就给百分比）；
- `rank.by` 可换 `P.Value` 或 `adj.P.Val`（官方参数三选一）；
- `...` 会透传给 `fgsea::fgsea()`，置换次数等参数按 fgsea 官方文档设（官方示例用 `nperm = 1000`）。

### 4.5 `significant_lipidsets()` 返回空

两个 cutoff：`p.cutoff = 0.05`、`size.cutoff = 2`；且 `lsea()` 侧还有 `min_size = 2`（"Minimum number of molecules in a set to be included in enrichment"）。
→ 若某类只有 1 个分子被检出，它**永远不会**进入富集。这是正确行为，不是 bug：单分子谈不上"类别整体偏移"。报告里应给出各集合的 size。

### 4.6 把 `plot_trend` 的 loess 线当统计结论

`plot_trend()` 返回 "A ggplot object"，官方未提供斜率/CI/p 值（<https://www.lipidr.org/reference/plot_trend.html>）。
→ 只能作可视化。要写"碳链越长 logFC 越低"这种断言，需另做回归（并说明方法、协变量、是否按类别分层），**不可引用一张 loess 图作为检验结果**。

---

## 5. 注释质量类（最容易被审稿人打的地方）

### 5.1 过度注释（over-annotation）

官方立场（LipidFinder 论文，逐字）："A significant issue in identification is over-annotation where MS is used to assign a fully annotated structure. This has led to major mistakes in structural assignment … This problem is unique to lipids due to the large numbers of isobaric ions."
来源：<https://pmc.ncbi.nlm.nih.gov/articles/PMC8208733/>

自查三问：
1. 我的方法有标准品吗？没有 → 最高只能到 Level 2 / 置信码 `x00` 以下。
2. 我给的是 `/` 还是 `_`？给 `/` 必须有 sn 证据。
3. 我给到 `(9Z)` 了吗？常规 CID 拿不到双键位置——需要专用裂解技术。

MS-DIAL 官方还明确：LC-MS/MS 脂质组模式下 "'lipid acyl position resolved' is not officially supported yet"（<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>）。所以"sn 位置已解析"这种表述，在纯 LC-MS/MS 数据上很难站住。

### 5.2 加合物指派错误

症状：正负模式给出的"同一脂质"质量对不上；或某类别在某一极"消失"。
做法：
1. 对照官方 adduct 表确认该类别在该极性下**应该**出现什么加合物（`references/nomenclature.md` 第 3.3 节）；
2. 用 LIPID MAPS `masscalc` 复算候选加合物的理论 m/z（<https://www.lipidmaps.org/resources/tools/ms>，工具路径 `/tools/structuredrawing/masscalc.php`）；
3. 或用 `moverz` 用**候选加合物**逐一检索，看哪个加合物能命中合理候选（<https://www.lipidmaps.org/resources/rest>）。

不要凭"常见加合物"经验直接定：PC 在负离子下常见的是乙酸根加合物 `[M+CH3COO]-`，而 PE/PI/PG/PS 是 `[M-H]-`（官方表，见 nomenclature 3.3）。

### 5.3 保留时间漂移被当成生物学差异

- 只看 RT ≤ 0.5 min 的官方口径（<https://systemsomicslab.github.io/compms/msdial/annotationcode.html>）做匹配；
- 漂移校正与 injection-order 检查走 `metabolomics-profiling`（QC-RLSC/LOESS 必须用 QC 拟合）；
- lipidr 侧可用 `plot_molecules(d_qc, "sd", measure = "Retention.Time", log = FALSE)` 看 RT 的标准差分布（vignette 官方调用）。

### 5.4 MCP 核对不上（PubChem 无命中）

- 缩写名（`PC 34:1`）在 PubChem 命名空间常无命中 → 改用 InChIKey（`namespace = "inchikey"`）或 `MolecularFormula` 检索；
- `chemistry_pubchem_properties` 的 `MolecularWeight` 是**平均分子量**，不可与高分辨精确质量直接比；
- ChEMBL 对结构脂质同系物几乎无条目，别拿"ChEMBL 查不到"当作否定注释的证据。

（工具签名见 `mcp/biomedical_mcp.py` L640–654 与 L742–743。）

---

## 6. 不要做的事

| 反模式 | 为什么 | 正确做法 |
|---|---|---|
| 用 `dim_analysis` / `liplevel_de` / `chain_de` | 这三个函数在 lipidr 官方参考索引中不存在，检索也无任何包提供 | `mva` / `lsea`+`plot_class_enrichment` / `plot_chain_distribution`+`plot_trend` |
| 从 MS-DIAL `_` 名直接改成 `/` 名 | 把"位置未知"伪造成"位置已知" | 降级到 species 级，或提供 sn 证据 |
| 手写正则解析脂质名 | 与官方 `annotate_lipids` 口径分叉，跨研究不可比 | 官方函数 + `not_matched` 留痕 |
| 拿 `plot_trend` 的 loess 线当检验 | 官方不返回统计量 | 另做回归并单列方法 |
| 拿 PubChem 命中去覆盖脂质注释 | MCP 工具是实体核对，不是注释器 | 只用于分子式/质量自洽校验 |
| 用 `filter_by_cv` 之后不报剔除数量 | 结论不可核 | 起始 N → CV 过滤后 N → 缺失过滤后 N |
