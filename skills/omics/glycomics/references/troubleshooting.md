# 糖组学排错手册

按「症状 → 原因 → 处置 → 来源」组织。凡处置涉及命令，命令一律来自官方页面（附 URL）；
官方文档没有给命令的，只给判据，不编命令。

---

## A. 编码与 accession

### A1. 提交结构报 `status:500 Internal Server Error "401 null"`

- **症状**：用 WURCS 首次提交，返回 500 且 message 里带 `401 null`。
- **原因**（官方原文）：profile 里的 API key 为空。
- **处置**（官方原文）："Please check if you have an API key in your Profile page
  (https://glytoucan.org/Users/profile) after logging in. It is possible that this variable is empty. You first
  need to click on “Generate API Key” in the Profile page."
- **来源**：<http://code.glytoucan.org/FAQ>

### A2. 同一结构在测试环境和生产环境 accession 不同

- **症状**：昨天在 beta 拿到 `G000xxMO`，今天在生产环境同一串 WURCS 得到另一个 accession。
- **原因**（官方原文）："Since the accession numbers are randomly generated, they may differ between the
  production and beta environments.  On a regular basis the beta environment data is overwritten by the
  production data in order to synchronize."
- **处置**：固定只在生产环境出 accession；脚本里显式设置
  `export API_HOSTNAME="https://api.glytoucan.org"`（官方 CLI 页命令，注意该 CLI 已 DEPRECATED）。
- **来源**：<http://code.glytoucan.org/system/cli/>

### A3. accession 看起来「不是序号」

- **症状**：以为是 `G000001`、`G000002` 递增，结果拿到 `G66357CN`。
- **原因**：accession 随机生成 + 5 位数字 + 2 位字母后缀，且后缀随环境变化。
- **处置**：按 `G` + 5 位数字 + 2 位字母做格式校验；**禁止**用数字段做排序、区间查询或「推断相邻结构」。
- **来源**：同 A2；实例见 T4 页面样例 `G66357CN` 与 `G00051MO`。

### A4. WURCS 转换报 `This SkeletonCode partially contains the wild card (x or X).`

- **症状**：把含 `x`/`X` 的 WURCS 丢进 GlycanFormatConverter，直接失败。
- **原因**（官方原文）：WURCS 常含结构未完全确定的单糖，用 `x`/`X` 表示；这类串转换器不处理。
  官方给的三个触发例：`WURCS=2.0/1,1,0/[AOOxxh]/1/`、`WURCS=2.0/1,1,0/[hXxh_2*C_4*OPO/3O/3=O]/1/`、
  `WURCS=2.0/1,1,0/[h21xxh]/1/`。
- **处置**：先回到结构层面把模糊位点确证（或明确保留为模糊），**不要**用 `x`→具体糖的替换来「凑过」转换；
  若确实要参与统计，把该结构标为「模糊」，按组成层面统计（见 SKILL.md §6.1）。
- **来源**：<https://github.com/glycoinfo/GlycanFormatConverter/blob/master/RESTRICTIONS.md>

### A5. IUPAC 输入转换报错（含重复单元/环/脱氧等）

- **症状**：`-i IUPAC-Condensed` 报转换异常。
- **原因**（官方限制清单，逐字要点）：含 repeating units、cyclic units、cross-linked substituent、
  repeating units with cross-linked substituent、cyclic substituent in any monosaccharide、
  monosaccharide fragments、substituent fragments、monosaccharide modifications such as deoxy。
- **处置**：改从 WURCS 侧进入（`WURCS→…` 行覆盖更全）；或先把结构简化到无上述特征再转，
  并在报告里记录「该结构经简化转换」。
- **来源**：同上 RESTRICTIONS.md

### A6. 想「把 GlycoCT 转成 GlycoCT 做规范化」，结果没输出

- **症状**：`-i GlycoCT -e GlycoCT` 无有效输出。
- **原因**：官方支持矩阵里 `GlycoCT` 列只有 `WURCS` 行有 ✔，`WURCS` 列只有非 `WURCS` 行有 ✔；
  同格式互转在官方表里是空的。
- **处置**：`GlycoCT → WURCS → GlycoCT` 或 `GlycoCT → IUPAC-Extended → GlycoCT`，并接受一次信息损耗；
  `IUPAC → GlycoCT` 也必须两步（先到 WURCS）。
- **来源**：<https://gitlab.com/glycoinfo/GlycanFormatConverter-cli>

### A7. WURCS 串在 shell 里被截断 / 参数被拆开

- **症状**：命令行只吃进了 `WURCS=2.0/3`。
- **原因**：WURCS 含逗号与方括号；含 `α`/`→` 的 IUPAC 串含特殊字符。
- **处置**（官方 Notes）：WURCS 用单引号（原文 "usage of quotes is ‘sequence’ not “sequence”"）；
  GlycoCT 里的换行必须写成 `\n`，且整串加引号。
- **来源**：<http://code.glytoucan.org/system/cli/>

### A8. `groovy gtc` 第一次执行卡住不动

- **症状**：无输出、CPU 不动，像是挂了。
- **原因**（官方原文）："The first time this is run, groovy will download the dependencies required by the
  client.  This is a few megabytes of libraries (approximately 30MB) and may take some time depending on your
  network connection."
- **处置**：等；或预置 groovy grapes 缓存。若随后出现莫名的编译错误，官方处置是
  "it is easiest to simply move or delete the grapes folder in the local groovy cache folder."
- **来源**：<http://code.glytoucan.org/system/cli/>

### A9. 想用「官方 REST 直连」但找不到端点

- **症状**：`https://api.glytoucan.org/`、`/glycans/G00051MO`、`/glycan/G00051MO` 全部 404；
  `https://glytoucan.org/api/v2/glycans/G00051MO` 也 404。
- **原因**：官方确实建议改 REST（"Please use direct REST access from the command line."），但公开站上
  没有可抓取的端点文档页；`code.glytoucan.org/api/` 只有一段指向 wiki 的说明，
  wiki 的 Home 只有一行指向 nexus javadoc。
- **处置**：批量取结构走 SPARQL（`SKILL.md` §2.1，endpoint `https://ts.glytoucan.org/sparql`），
  这是官方给了逐字 query 的路径；不要凭 404 结果反推端点名。
- **来源**：<http://code.glytoucan.org/system/cli/>、<https://code.glytoucan.org/api/>、
  <https://raw.githubusercontent.com/wiki/glytoucan/api/Home.md>

---

## B. 质谱糖谱

### B1. 组成推断总是差一个氧/一个脱氧糖

- **症状**：同一个峰，一次算成 `Hex5HexNAc4`，一次算成含 `dHex` 的组合。
- **原因**：`Fuc`（dHex）与「Hex 少一个 O」在中性质量上几乎不可仅凭一级质量区分；且电荷态误判会让
  差值系统偏移。
- **处置**：① 先用同位素簇间隔定 `z`；② 用诊断离子交叉验证（`204.087`、`138.055`、`292.103`、`308.098`，
  见 `SKILL.md` §3.3 官方 marker 表）；③ 两个 marker 不同时成立时只报组成并标「不可分辨」。
- **来源**：<https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/diagnostic-ion-checker.py>

### B2. 多电荷糖链被当成「一个很大的糖」

- **症状**：`m/z 900` 附近被判成 `Hex10` 级别的大糖。
- **原因**：带唾液酸的酸性糖链常出现 2–、3– 电荷；把 `m/z` 当 `M+H` 会高估质量。
- **处置**：逐峰看同位素簇间距 ≈ 1/z；对同一色谱峰的所有电荷态求中性质量并取交集后再枚举组成。
  **官方文档未提供可直接执行的去卷积命令**，此步按仪器软件的去卷积输出为准并在方法里记录参数。
- **来源**：官方侧只能核实到质量计算脚本（`mass_calc/chem2mass.py`），去卷积无官方命令行。

### B3. GU 值跨批次对不上

- **症状**：同一结构上个月 GU=7.2，本月 GU=6.8。
- **原因**：GU 绑「柱 + 梯度 + 标记化学」。官方保留性质库把单位分成
  `HPLC`、`UPLC_2-AB`、`UPLC_Procainamide`、`CE`、`RP`、`PGC`，本身就在提示不同体系不可混。
- **处置**：① 每批随行标准梯；② 只与同体系的库记录比对；③ 报告里写全柱型/梯度/标记；
  ④ 跨批不合并 GU（可分组建模）。
- **来源**：<https://glycostore.org/>

### B4. 标准梯高 DP 区没峰，GU 拟合远端失真

- **症状**：GU>10 的区域样品峰有值、标准梯没峰，拟合曲线翘尾。
- **原因**：高聚合度标准品信噪比不足。
- **处置**：只用「标准梯覆盖范围内」的 GU 做定量，范围外的峰标为「GU 外推，仅定性」。
  **官方文档未提供可直接执行的命令**（无官方 GU 拟合工具），此步需人工核查并在方法中声明外推范围。
- **来源**：同 B3。

### B5. GlycoWorkbench 启动即崩 / 双击无反应

- **症状**：jar 双击无窗口，或报 Java 版本/位数错误。
- **原因/处置**（官方 README 逐字要点）：需 Java 8+；"GlycoWorkbench >= 1.3.0, will only run on systems
  that support the SWT library (includes; Windows, Linux and macOS)"；官方给出的排错路径是命令行启动：
  `java -jar -Xmx300M eurocarb-glycoworkbench-1.0rc.jar`，仍失败则把报错邮件给维护者；
  官方另注明 64bit Java 6 的已知问题要求改装 32bit 等价版本。
- **来源**：<https://gitlab.com/glycoinfo/glycoworkbench>

### B6. 找不到 GlycoWorkbench 的命令行注释参数

- **症状**：想批量跑 GWB 的糖链注释，找不到 `--xxx` 参数。
- **原因**（官方 README 原文）："The GlycoWorkbench (GWB) manual can be accessed via the Help menu of GWB."；
  仓库主页 `Web site: TODO:`。
- **处置**：**官方文档未提供可直接执行的命令**。GWB 只能作为 GUI 人工判读工具使用；批量注释请走
  pGlyco（糖肽）或按 §B1–B2 的判据人工判读，不要自造 GWB 命令行。
- **来源**：同上。

### B7. 找不到 Byonic 的命令行调用

- **症状**：想脚本化 Byonic 检索。
- **原因**：官方公开页面只有产品能力描述与 Knowledge Base，没有公开 CLI 参数表。
- **处置**：**官方文档未提供可直接执行的命令**。按官方产品页描述记录方法学即可
  （"Identify glycopeptides without prior knowledge of glycan masses or glycosylation sites."），
  参数以 Knowledge Base 与随软件文档为准。
- **来源**：<https://www.proteinmetrics.com/products/byonic>、<https://support.proteinmetrics.com/hc/en-us>

---

## C. 完整糖肽（pGlyco 系列）

### C1. pGlyco3 首次启动弹出 license 对话框，流程卡在这一步

- **原因/处置**（官方原文）：填完表单后 "clicking "copy to clipboard" to copy the form"，把表单粘贴到
  `http://i.pfind.net/license/pGlyco3` 生成 license；"Please check your spam mailbox as our reply emails are
  sometimes in your spam mailbox."
- **来源**：<https://github.com/pFindStudio/pGlyco3>

### C2. 脚本读结果表时报 KeyError（列名找不到）

- **症状**：自己写的解析代码按固定列名取值失败。
- **原因**：官方脚本对糖链列做了**前缀匹配**而不是硬编码列名：
  `glycan_head = "Glycan"` 然后遍历表头找 `name.startswith('Glycan(')`。
- **处置**：照官方的匹配方式找列；除糖链列外，其余列名为 `GlycanFDR`、`PeptideFDR`、`TotalFDR`、
  `GlySpec`、`RawName`、`Scan`、`ETDScan`、`Peptide`、`GlySite`、`Mod`、`MonoArea`、`IsotopeArea`、`Proteins`。
- **来源**：<https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/protein_site_analysis.py>

### C3. 「FDR 1%」到底指哪个 FDR

- **症状**：报告写「FDR<1%」，审稿人问是糖链还是肽。
- **原因**：pGlyco 输出三列 FDR；官方脚本默认阈值是糖链 0.01、肽 0.1（逐字 `glycan_fdr_thres = 0.01`、
  `peptide_fdr_thres = 0.1`），并另读 `TotalFDR`。
- **处置**：报告里点名维度；不要用「糖链 FDR × 肽 FDR」当总 FDR；需要单一数字时用 `TotalFDR` 并说明。
- **来源**：同上。

### C4. Skyline 导入脚本报错

- **症状**：`pGlyco_to_skyline_ssl.py` 报参数错误或找不到结果文件。
- **原因**：脚本只接受两种输入形态：`pGlyco.cfg`（从里面读 `file=`、`output_dir=`、`pGlyco_type=`，
  再拼 `%s-GP-FDR.txt`），或直接给 `…-GP-FDR.txt` + `raw_folder` 两个参数。
- **处置**（官方 usage 逐字）：

  ```
  python pGlyco_to_skyline_ssl.py C:/output/folder/pGlyco.cfg
  python pGlyco_to_skyline_ssl.py C:/output/folder/pGlycoDB-GP-FDR.txt raw_folder
  ```
- **来源**：<https://raw.githubusercontent.com/pFindStudio/pGlyco3/main/scripts/pGlyco_to_skyline_ssl.py>

### C5. 一个糖肽谱图匹配到多个糖链，比例怎么算

- **症状**：同一 `Scan` 多个 glycan 命中，microheterogeneity 比例算出来不稳定。
- **原因**：按谱图数（PSM 计数）与按 `MonoArea`/`IsotopeArea` 加权得到的是两个不同比例。
- **处置**：先定口径并写进方法：组成层面用 `MonoArea` 加权，鉴定层面用 PSM 计数；两套分开出表，
  不做平均。**此步无官方命令**，属人工核查项（SKILL.md §8 第 8 项）。
- **来源**：列名来自 `protein_site_analysis.py`（同上）。

### C6. `GlySite` 与 `Mod` 冲突

- **症状**：位点号与修饰标注指向不同残基。
- **处置**：以 b/y 离子与糖碎片是否互相印证为准；不能印证时把该糖肽标为「位点不确定」，
  只保留糖链组成，不写位点。**官方未提供自动仲裁命令**。
- **来源**：官方脚本只读取这两个字段，不做仲裁。

### C7. 老机器上 pGlyco2 的 `xtract_raw` 报错

- **原因/处置**（官方 README 原文要点）：2.2.0 起改用 Thermo RawFileReader，"If you need to change back to
  the MSFileReader-based APIs, please rename the xtract_raw_with_msfilereader.exe in the installation folder as
  xtract_raw.exe, and of course you need to install MSFileReader."
- **来源**：<https://raw.githubusercontent.com/pFindStudio/pGlyco2/master/README.md>

### C8. 只有 mzML，能不能跑 pGlyco2

- **可以**：官方 release note 2.2.0 明列 "Supported mzML."（同时该版本修了 `pGlycoFDR.exe` 的除零 bug）。
- **来源**：同上。

---

## D. 芯片与凝集素阵列

### D1. 两批芯片数据直接相比，结论翻转

- **症状**：PA_v4 的数据和 PA_v52 的数据放一起做差异，出现大量「新结合」。
- **原因**：芯片版本不同，点号与糖链布局不同；官方归档把版本作为独立字段
  （`Glycan Array`：`PA_v0…PA_v52`、`GLYCAN_v1…v3`、`BACT_v1`）。
- **处置**：按结构（accession 或 WURCS）对齐后再比；不同版本只在结构层合并，不在点号层合并。
- **来源**：<https://www.functionalglycomics.org/glycan-array>

### D2. 归档里一半实验是 `Inconclusive`

- **原因**：官方归档对每条实验给 `Conclusive` 字段（`Data` / `Inconclusive`）。
- **处置**：`Inconclusive` 不进统计主表，只作背景；主表数量与归档总数（6035 条）对不上时先查这一列。
- **来源**：同上。

### D3. 凝集素「阳性」被写成结构确证

- **原因**：凝集素结合是**结合谱**证据，存在交叉反应；官方层面没有唯一特异性矩阵可引用。
- **处置**：结论写「与某凝集素结合谱一致」，并同时给出「原始强度 / 归一化后 / 矩阵版本与来源」三项；
  **不要**写「检出某结构」。
- **来源**：本环境未取得官方特异性矩阵（ACGG LfDB 404、glycobase.nibrt.ie TLS 失败），
  见 `official-docs.md` §10 O8/O9。

### D4. 归一化后所有凝集素都「显著」

- **原因**：跨凝集素强度不可比（不同凝集素点样量、亲和力差异数量级）。
- **处置**：归一化在**样本内**完成（每个凝集素分别按样本分布标准化），比较只在同一凝集素跨样本之间进行；
  跨凝集素只做排序展示，不做显著性检验。
- **来源**：归一化本身无官方标准（同上），此条为本技能列出的核查判据。

---

## E. 抓到的是网页壳而不是文档

### E1. 打开 glytoucan.org/Documentation 只有转圈的 `LOADING`

- **原因**：主站是 JS 单页应用，抓取工具拿到的是加载骨架（3 018 字节左右），正文由前端渲染。
- **处置**：文档改读 <http://code.glytoucan.org/>（`/manual`、`/FAQ`、`/rdf-ontology/sparql-queries/`、
  `/system/cli/`、`/system/api_list/`），这些是静态页，可逐字引用。
- **来源**：见 `official-docs.md` §1。

### E2. GlyGen / GlyCosmos 页面同样抓不到正文

- **原因**：两者门户也是 SPA；`api.glycosmos.org` 只返回 Wiki.js 外壳（5 435 字节，与路径无关）。
- **处置**：GlyGen 侧用 `https://api.glygen.org/glycan/detail/{ACCESSION}/` 取结构化字段（实测可用，
  但官方未提供端点文档，引用时必须标注）；GlyCosmos 侧只用官方给了逐字 query 的
  `https://ts.glycosmos.org/sparql`。
- **来源**：`official-docs.md` §8、§9。

### E3. `www.glyco-workbench.org` 打不开

- **原因**：该域名 DNS 不存在（`ENOTFOUND`）；官方仓库 README 里 `Web site: TODO:`，即官方站点从未建立。
- **处置**：改用 <https://gitlab.com/glycoinfo/glycoworkbench>。
- **来源**：`official-docs.md` §5。
