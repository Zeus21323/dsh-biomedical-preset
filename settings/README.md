# 生物医学技能设置页（`dsh-biomedical-preset` 的 `settings/` 组件）

`dsh-biomedical-preset` 自带的设置页：把 603 个技能按 **34 个功能分类**（6 个大组）放进 DSH 设置页，逐类开关。

它不是一个独立包——`package.json` 的 `dsh.client` 指向本目录的 `client.js`，`cordis.patch.yml` 在 profile 里插一行 `biomedical-skill-settings`（`dsh-biomedical-preset/settings`），两者随预设一起安装。

## 它做什么

| 半 | 职责 |
|---|---|
| Host | 声明 34 个布尔开关的 Config（`config.mjs`），并把实时值镜像到 `<profile>/biomedical-skills.json` |
| Client | 在 **设置 → 生物医学技能** 注册一个页面：分类列表 + 开关 + 全开/全关，通过 `remote.settings` 读写自身 Config |

preset 里的 `picker` provider 每次 `list()` 都读 `biomedical-skills.json`，因此页面上的开关立即影响**新会话**的技能目录（已开的会话不受影响）。

## 页面结构：6 个大组分节

34 个分类上卷成 6 个功能域，按组分节显示（组间有分隔线）：

| 大组 | 分类数 | 技能数 |
|---|---|---|
| 测序与变异 | 8 | 142 |
| 组学与单细胞 | 10 | 224 |
| 结构与药物 | 5 | 83 |
| 临床与影像 | 4 | 56 |
| 方法与工程 | 5 | 65 |
| 文献与写作 | 2 | 33 |

每组标题行：组名 + 「N 个分类 · M 个技能 · 已启用 X」+ 组内「全开 / 全关」；
组内默认只列前 4 个分类（`PREVIEW = 4`），其余折叠在「还有 N 个分类 · 展开」后面，展开后可「收起」；
顶部保留全局「全部开启 / 全部关闭」。

`GROUPS` 未覆盖的分类会自动落入「其他」组，避免新增分类从页面消失。

### 分类（每组内可单独开关）

| 分类 | 数 | 分类 | 数 |
|---|---|---|---|
| 测序质控与比对 | 19 | 基因组组装与比较基因组 | 20 |
| 变异检测与过滤 | 16 | 拷贝数变异与结构变异 | 10 |
| 变异解读与罕见病诊断 | 11 | 群体遗传与 GWAS | 28 |
| 肿瘤基因组与液体活检 | 28 | 法医与身份遗传学 | 10 |
| 临床精准医学 | 10 | 医学影像与放射组学 | 12 |
| 显微成像与细胞表型 | 17 | 转录组定量 | 32 |
| 差异表达与富集 | 11 | 单细胞核心分析 | 20 |
| 单细胞高级与虚拟细胞 | 20 | 空间组学 | 15 |
| 蛋白质组学 | 21 | 代谢组与脂质组 | 18 |
| 表观遗传与甲基化 | 31 | 调控网络与序列模型 | 18 |
| 微生物组与宏基因组 | 38 | 结构生物学与建模 | 18 |
| 化学信息学与药物设计 | 27 | 蛋白工程与合成生物学 | 15 |
| 基因编辑与克隆 | 13 | 药物基因组与给药 | 10 |
| 免疫学与免疫肿瘤 | 17 | 文献与证据合成 | 13 |
| 写作与文档交付 | 20 | 数据工程与统计 | 24 |
| 工作流与可复现 | 10 | 数据库与 API 接入 | 11 |
| 可视化与图件 | 10 | 研究设计与假设 | 10 |

### 实现要点

- 该行的 Config 字段必须带 `.volatile()`：`dsh-settings` 的 `describe()` 用 `volatileForm()` 过滤，全非 volatile 的对象行会被整行跳过，页面就永远看不到它。
- `describe()` 返回 `{ ok, value: { namespaces: [...] } }`，本行的 `ns` 是 patchId（`biomedical-skill-settings`），不是 `include:xxx`。
- 该行的 `schema` 是 schemastery 的 `{ uid, refs }`，没有 JSON Schema 的 `properties`；因此分类显示名与技能数由构建时生成的内嵌常量 `LABELS` 提供。

## 开关存到哪

`<profile>/biomedical-skills.json`，形如 `{ "proteomics": false, "microbiome-metagenomics": true, ... }`，缺省视为开启。直接编辑这个文件同样生效。

## 注意

- 关闭分类只影响**技能目录**（模型可见的技能清单），不会删除任何文件。
- 已开启的会话不会重算技能目录，需要新建会话。
- `config.mjs` 由 preset 的 `picker/catalog.json` 生成；分类变动后需重新生成。
