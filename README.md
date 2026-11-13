# 生物医学模式 · dsh-biomedical-preset

DeepSeek Harness 的 agent 预设（bundle）。它不是"给通用助手加个提示词"，而是一套**自持**的生物医学研究装配：身份与纪律、执行工具、597 个技能（34 个功能分类，可在设置里逐类开关）、51 个数据源 MCP 工具、并发闸、交付通道，全部装在这一个包里，不引用任何外部插件目录。

- 心智模型：**MCP 负责取数据，Skill 负责选方法与执行流程**，persona 负责纪律与判断。
- 已验证：市场索引通过官方 `@deepseek-ai/dsh-plugin-market-index` 校验；本机预设 `fiberPhase: active`。技能数、各模式技能数与目录成本以 `node tools/gen.mjs --check` 的输出为准（下文表格由它生成）。

---

## 目录

- [安装](#安装)
- [装配结构](#装配结构)
- [技能清单（597，34 个功能分类）](#技能清单59734-个功能分类)
- [13 个模式：先选模式，别全开](#13-个模式先选模式别全开)
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

> **不要在任何文件里写本机绝对路径**（以前 patch 写死了 `C:/Users/<用户名>/…`、`F:/…`，别人装上后 MCP 静默起不来、设置页开关不生效）。现在的做法：
>
> - MCP 的 python 用 DSH 自带的 primary runtime：`!!js "dshHomePath('dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', …)"`（Windows 为 `python.exe`，macOS/Linux 为 `bin/python3`）；
> - 包内文件（MCP 脚本、兜底技能目录）经 `paths.cjs` 按包名解析：`createRequire(<profile 目录>/)('dsh-biomedical-preset/paths')`，与 Loader 加载 `dsh-biomedical-preset/picker` 走同一条解析路径；`link:` 安装解析到开发目录；
> - profile 目录由 `shared/profile.mjs` 定位：`ctx.get('profileContext').dir` → `DSH_PROFILE_DIR` → `$DSH_HOME/profiles/$DSH_PROFILE`；
> - `!!js` 表达式里有 ` : `（三元运算）时必须整体加双引号，否则 YAML 会把它当键值分隔符。
>
> `tools/lint-presets.mjs` 会拒绝任何形如 `X:/`、`/Users/`、`/home/` 的绝对路径。

---

## 装配结构

`cordis.patch.yml` 在本包内声明 28 个插件行（22 个启用 + 6 个默认禁用、仅在 picker 故障时手动打开的 `skill-filesystem` 兜底行），另在 profile 里插 2 行（`preset-biomedical` 本预设 + `biomedical-skill-settings` 设置页）：

| 层 | 插件行 | 作用 |
|---|---|---|
| 身份 | `persona` | prefix（身份、开工方式、汇报口径，各模式不同）+ 共享 suffix `&bio-discipline`（方法—数据适配性裁决、派活格式、隔离与核验、红线、9 条结论纪律；13 个模式共用同一段） |
| 身份 | `agent-instructions` | 读取项目 `AGENTS.md`（课题组分析规范走这里） |
| 身份 | `time-context` | 时间锚（"近三年"、随访窗口） |
| 执行 | `tool-pwsh` / `tool-bash` | 按平台二选一，跑 python/R/conda/比对工具 |
| 执行 | `tool-fs`、`tool-fs-search` | 读写脚本、检索大表、grep 参数文件 |
| 执行 | `tool-jobs` | 后台长任务（比对、训练、批量下载） |
| 技能 | `skill-filesystem` | 用户自有技能根（`$DSH_HOME/skills`） |
| 设置页 | `biomedical-skill-settings` | profile 级行 + `client.js`（`dsh.client`），34 个分类开关写入 `biomedical-skills.json` |
| 会话面板 | `client.js`（同一浏览器半） | 输入框右侧「🧬 技能」按键（`conversation.input.right`）+ 可拖动浮窗（`shell.overlay`），只改本会话 |
| 技能 | `biomedical-skill-picker` | 单一 provider：597 个技能按 34 个功能分类提供（目录列出 445 个，152 个 nf-core 流程经 `nfcore-catalog` 入口加载），开关见 `picker/catalog.json`；同时提供 `skill_scope` 工具 |
| 技能 | `tool-skill` | 技能目录与加载器 |
| 数据 | `bio-mcp` | 拉起 `mcp/biomedical_mcp.py`（51 工具，stdio） |
| 编排 | `command-goal`、`tool-goal` | 长课题目标追踪 |
| 编排 | `planning`（组） | plan-mode，先出研究设计再动手 |
| 编排 | `compaction`（组） | 上下文压缩 + 工具结果裁剪（组学输出动辄上万行） |
| 编排 | `delegation`（组） | `subagent` / `subagent_fork` / `workflow` |
| 并发 | `subagent-cap` | 同一会话最多 3 个子智能体（`tools/execute` 拦截）；子智能体不能再派活（`maxDepth: 1` + 闸内深度检查） |
| 编排 | `tool-ask-user` | 只问用户自有决策（物种、队列、终点、期刊） |
| 编排 | `tool-todo` | 多步骤任务拆解 |
| 交付 | `tool-web` | 文献与库 API 抓取（fetch + search） |
| 交付 | `present` | 图表、DOCX 稿、汇报材料的交付卡片 |

---

### 带浏览器半的包的硬性约束

设置页是 `dsh.client` 声明的浏览器半，下面两条必须**同时**满足，否则启动会失败或设置页静默消失：

1. **profile 里这一行的 `name` 必须是裸包名**（`dsh-biomedical-preset`），不能带子路径。
   `dsh-client-modules` 的 `exactPackageSpecifier()` 只接受不含 `/` 的 specifier：

   ```js
   return specifier.length > 0 && !specifier.includes('/') && !specifier.includes(':')
     ? specifier : void 0;
   ```

   带子路径（`dsh-biomedical-preset/settings`）的 entry 会被判为「not a client package」，
   Client 半永远不加载，设置页那一项**静默消失且不报错**。

2. **`client.js` 里 `__ModuleLoader__.load({ id })` 的 `id` 必须等于 `package.json` 的 `name`**。
   DSH 用包名作为 `WebBootEntry.id`；id 不匹配会让它认为该 bundle 没有注册它要的 id，
   于是重复执行，触发
   `client-modules: duplicate factory registration for "<id>"`，
   最终 `web boot: N entry did not activate` —— 桌面端直接弹「应用无法启动」。

> **两次真实事故（2026-11-02，均已在 2.0.1 / 2.0.2 修复）**
>
> - 合并设置页时把 Loader 行写成 `dsh-biomedical-preset/settings`（违反第 1 条），设置页从侧边栏消失。
> - 改包名后没有同步 `client.js` 的注册 id（违反第 2 条），启动崩溃；用户在那个对话框上点了
>   「禁用第三方插件、备份 profile patch 并重启」，把 profile 里 17 个第三方 bundle 一并关掉。
>
> 自查方法：`node -e` 解析 client.js 取注册 id，与 `package.json` 的 `name` 比对；
> 再确认 Loader 行的 `name` 不含 `/`。

3. **样式只能用 `--dsw-alias-*` 主题变量**，别自造变量名。

   浏览器半能用的颜色 token 只有这 14 个（`cordis_inspect_query` 的 client `Theme.listTokens` 可查）：

   | token | 用途 |
   |---|---|
   | `--dsw-alias-bg-base` / `-bg-layer-1` / `-bg-layer-2` / `-bg-overlay` | 底色 / 抬升面 / 嵌套面 / 浮层 |
   | `--dsw-alias-border-l1` / `-l2` | 弱边框 / 强边框 |
   | `--dsw-alias-label-primary` / `-label-secondary` | 主文字 / 次文字 |
   | `--dsw-alias-brand-primary` | 主色（选中、强调） |
   | `--dsw-alias-state-{error,success,warn,idle}-primary` | 状态色 |
   | `--dsw-specific-sidebar-fill` | 侧栏底色 |

   `--dsh-*` 之类自造名字**不存在**，`var()` 会静默落回兜底值——兜底若写成 `#fff`，深色模式下就是一块白板（2.3.0 开发期间真踩过）。浮窗背景用 `--dsw-alias-bg-overlay`，边框用 `-border-l1/-l2`，强调色用 `-brand-primary`。

## 技能清单（597，34 个功能分类）

597 个技能按**用户要达成的任务**分为 34 类（每类 9–38 个），由 `picker` 插件统一提供，映射见 `picker/catalog.json`。分类不按文件格式切分；nf-core 流程按分析任务分散到各领域类。

## 13 个模式：先选模式，别全开

本包提供 **1 个全量模式 + 12 个专项模式**。专项模式在新建会话时选，只加载一个大类的技能。

### 为什么要分模式

技能目录由模型自己读（`skill` 工具），**常驻每一轮对话**。全量目录 445 条（152 个 nf-core 流程折叠在 `nfcore-catalog` 入口后）≈ **2.2–2.5 万 token**（2.5.0 时 597 条 ≈ 3.3 万），而且近义技能（`sc-clustering-umap` 与 `sc-cell-type-annotation`、`nfcore-rnaseq` 与 `nfcore-smrnaseq`）会互相干扰，候选集越大越容易选错。

专项模式把候选集压到 31–98 个，成本降到 **1 700–5 400 token**，同时命中率明显更高。

### 12 个专项模式

<!-- gen:modes-table 由 tools/gen.mjs 生成，不要手改 -->
| 模式（新建会话时选） | 覆盖的分类 | 技能 | 约 token |
|---|---|---|---|
| **生物医学模式**（全量） | 全部 34 类 | 445（+152 个流程） | 24 700 |
| 测序与变异检出 | 测序质控与比对、变异检测与过滤、拷贝数变异与结构变异 | 29（+17 个流程） | 1 600 |
| 基因组组装与群体遗传 | 基因组组装与比较基因组、群体遗传与 GWAS | 28（+21 个流程） | 1 600 |
| 临床解读与精准医学 | 变异解读与罕见病诊断、临床精准医学与结局分析、药物基因组学与用药 | 30（+2 个流程） | 1 700 |
| 肿瘤与免疫组学 | 肿瘤基因组与液体活检、免疫组学与免疫治疗 | 34（+12 个流程） | 1 900 |
| 转录组与差异表达 | 转录组上游与定量、差异表达与功能富集 | 22（+21 个流程） | 1 200 |
| 单细胞与空间组学 | 单细胞基础分析、单细胞高级与虚拟细胞、空间组学分析 | 43（+13 个流程） | 2 400 |
| 表观遗传与调控 | 表观遗传与 DNA 甲基化、调控网络与序列模型 | 36（+14 个流程） | 2 000 |
| 蛋白组与代谢组 | 蛋白质组学、代谢组与脂质糖组 | 30（+10 个流程） | 1 700 |
| 结构与药物设计 | 结构预测与建模、化学信息学与药物设计、蛋白工程与合成生物学、基因编辑与分子克隆 | 69（+5 个流程） | 3 800 |
| 微生物组与宏基因组 | 微生物组与宏基因组 | 16（+23 个流程） | 900 |
| 影像、细胞表型与法医 | 医学影像与放射组学、显微成像与细胞表型、法医与身份鉴定 | 35（+5 个流程） | 1 900 |
| 文献、写作与工程 | 文献检索与证据合成、写作与文档交付、数据工程与统计方法、计算流程与可复现性、数据库与接口对接、可视化与图件、研究设计与假设生成 | 84（+9 个流程） | 4 700 |
<!-- /gen:modes-table -->

**怎么选**：新建会话时点预设选择器，选最贴近本次分析目标的那一个。一次分析跨两个大类（例如单细胞 + 文献综述），用全量模式再按下面那节关掉无关类。

### 两种模式的开关行为不同

| | 全量模式 | 12 个专项模式 |
|---|---|---|
| 默认加载哪些类 | **由设置页决定**（34 个开关，默认全开） | **固定白名单**（`picker.config.only`），不受设置页影响 |
| 持久细调 | ✅ 设置 → 生物医学技能 | ❌ 要换默认范围请换模式，或改 `cordis.patch.yml` |
| 本会话临时细调 | ✅ 输入框右侧「🧬 技能」浮窗 | ✅ 同样可用（会话覆盖优先于白名单） |
| 适用 | 探索期、跨领域任务 | 目标明确的常规分析 |

> ### 全量模式下的细调
>
> 全量模式默认 34 类全开（目录列出 445 个技能，另 152 个 nf-core 流程经入口加载）。如果只用其中一部分，去**设置 → 生物医学技能**关掉无关的类：
>
> | 保留范围 | 目录常驻 |
> |---|---|
> | 34 类全开（默认） | ≈ 24 700 token |
> | 4 类（如转录组 + 差异表达 + 数据工程 + 文献写作） | ≈ 8 000 token |
> | 1–2 类 | ≈ 1 000–3 000 token |
>
> 不过如果你已经知道要做单个领域，**直接用对应的专项模式更省事**——它开箱就是对的子集，不用手动关一堆开关。
>
> 开关写入 profile 的 `biomedical-skills.json`，对**新会话**生效（目录在会话创建时计算一次，已开启的会话不重算）。专项模式不读这个文件。


### 在设置里按类开关

设置页随本包一起安装（`settings/`，在 profile patch 里插一行 `biomedical-skill-settings`）：**设置 → 生物医学技能** 会列出 34 个分类开关和全开/全关按钮。

开关写入 profile 的 `biomedical-skills.json`，`picker` 每次 `list()` 都读它，因此改动对**新会话**立即生效（已开启的会话不重算目录）。也可以直接编辑该文件，例如 `{"proteomics": false}`，缺省视为开启。

### 会话内浮窗：只改本会话

设置页改的是**默认值**（只对新会话生效）。要在**当前这个会话**里临时缩小或换范围，用输入框右侧的 **「🧬 技能」** 按键：

```
对话输入框左下 …  [🧬 技能]  … 发送
                        ↓
┌ 技能范围 · 本会话                     ↺  ✕ ┐   ← 拖标题栏可移动，位置记在 localStorage
│ 当前 12 类 / 34 类 / 597 技能 / ≈38k token  │
├─────────────────────────────────────────────┤
│ 🧬 测序与变异检出     3 类 · 45 技能   ▸  ● │   ← ▸ 展开细分类，● 三态开关
│ 🧭 基因组组装与群体遗传 2 类 · 48 技能   ▸  ● │
│ …                                           │
├─────────────────────────────────────────────┤
│ 全部开启   全部关闭   恢复默认    已保存，下一步生效 │
└─────────────────────────────────────────────┘
```

- **只在本模式下出现**：入口按键是客户端半（profile 级，所有会话共用一份），所以每次挂载都会问 Host 一次
  `GET /bio-skills/applies?sessionId=…`。Host 用 `agents.get(sessionId)` 找到会话，再用
  `agentPresets.composedPreset(agent.ctx)` 读出它**实际组合的预设 id**，然后看该预设的声明里有没有
  `dsh-biomedical-preset/picker`。是生物医学模式才显示按键；其它模式（standard / ptc / minimal / cordis /
  redteam …）按键不出现，面板若开着会被自动关掉。判定按会话缓存 5 秒，不会每次渲染都打网络。
- 判定不出来（路由 404、会话还没起 agent、读不到预设声明）时一律**不显示**——宁可不出现，也不要在别的模式里冒出来。要排查就直接看那条路由，它会回 `applies / presetId / reason`。
- **刚打开会话时 Host 那边 agent 可能还没起来**（实测 `reason="session has no live agent"`）。这种情况下客户端不当定论：`applies=null` 会每 1.5 秒重试、最多 8 次，等 agent 起来后按键自动出现；只有 `404`（路由不存在，说明插件没启用）和明确的 `false` 才立刻定论。判定结果按会话缓存 5 秒。
- **12 个大类**与 12 个专项模式一一对应，展开后是该大类下的 34 个功能分类，可单独勾选；大类开关是三态（全开／部分／全关）。
- 每行显示「N 类 · M 技能 · ≈X token」，底部汇总当前生效范围，选之前就知道目录成本。
- 三个按钮：`全部开启` / `全部关闭` / `恢复默认`（`恢复默认` 清掉会话覆盖，回到「模式白名单 → 设置页」的默认状态）。`全部关闭`（0 类）表示**本会话不加载本包任何技能**，不会再退回全量。
- 浮窗显示的默认范围按**本会话实际组合的预设**取：picker 行的 `config.preset` 写着所属预设 id，Host 用 `/bio-skills/applies` 同一套判定找到会话的预设，再取那份 picker 的 `only`。判定不了时才退回进程级推断（面板会提示可能不准）。
- **改完下一个 step 就生效**，不用新开会话：`skills.snapshot()` 每步重新查询，写完后 Host 会 `invalidate()` 目录缓存。
- 只影响本包 `skills/` 里的 597 个技能；你自己的 `~/.agents/skills`、`~/.dsh/skills` 里的技能不受影响。
- 会话覆盖存在 Host 进程内存里（按 `sessionId`），**重启 DSH 即清空**，回到模式默认。

优先级：**会话覆盖 > 专项模式白名单（`only`）> 设置页分类开关**。因此专项模式也能临时加开别的类——但那是"这一轮多给点技能"的应急手段，长期还是换模式更干净。

实现（要改这里先看）：

| 半 | 位置 | 职责 |
|---|---|---|
| Host | `picker/index.js` | `GET /bio-skills/get?sessionId=`（返回 34 类 + 此刻 `effective` + `source`）、`POST /bio-skills/set`（`{sessionId, enabled: string[] \| null}`）、`GET /bio-skills/applies?sessionId=`（该会话是不是生物医学模式）、`GET /bio-skills/presets`（13 个预设的 `broken` 诊断）；`sessionOverrides: Map<sessionId, Set<categoryId>>`；用 `agents.currentInitiator()` 取当前会话 |
| Client | `client.js` | `conversation.input.right` 的入口按键（`inject: (sessionId) => ({sessionId})`）+ `shell.overlay` 的浮窗；两者只共享一个模块级 `scopeStore` |

两个实现要点，改动时别踩：

1. 可选服务必须 `ctx.inject(['webServer'], cb)` / `ctx.inject(['agents'], cb)`，**不能用 `ctx.get()`** —— 冷启动时 `apply()` 早于服务注册，`get` 拿到 `undefined`，路由就永远注册不上（实测：热加载 available、冷启动 UNAVAILABLE）。
2. 跨作用域共享状态只能走模块级对象：入口按键是 session 作用域（拿得到 `sessionId`），浮窗是 root 作用域（拿不到），两者靠 `scopeStore` + 订阅重渲染对齐。

### 13 个预设 = 13 份 picker：路由必须进程级共用

`agent-preset-registry` 在**注册预设时**就把每个预设的插件挂进独立 scope，所以启动后同进程里同时活着 **13 份 picker**（1 全量 + 12 专项），每份都会 `ctx.inject(['webServer'])`。而 Host 的 `webserver.register` 对同一 `(kind, path)` **只允许注册一次**：

```js
// dsh-host-webserver
if (table.has(route.path)) throw new Error(`webserver: duplicate ${route.kind} route "${route.path}"`);
```

这个异常若从 `apply()` 冒出，该行会被 `auditRows` 判 failed，**整个预设挂载被拒**（模式卡片显示「加载失败」），且它的 MCP、技能、工具全部不生效。2.3.0 之前**踩了这个坑**：只有第一个挂载的预设能活，其余 12 个专项模式实际起不来（当时进程里只剩 1 个 `biomedical_mcp.py`，正常应是 13 个）。

现在的做法（`picker/index.js`）：

| 机制 | 实现 |
|---|---|
| 进程级共享区 | `globalThis[Symbol.for('dsh.biomedical.picker.v1')]`，模块被加载两次也共用同一份 |
| 路由注册 | 引用计数：`routeRefs` 从 0→1 的实例注册，其余只计数；归零时注销 |
| 注册失败 | `try/catch` 兜住并记 `routeError`，**绝不让它冒进 `apply()`** |
| 会话覆盖 | 存在共享区（不挂在实例上），`invalidate()` 广播给所有实例 |

诊断字段（`GET /bio-skills/get` 直接可查，无需登录）：

```jsonc
{
  "instances": 13,        // 当前活着的 picker 数量；13 = 13 个预设都挂上了
  "routeCollisions": 12,  // 被复用的重复注册次数；12 说明另外 12 份确实在跑
  "source": "profile",    // session | preset | profile
  "effective": ["..."]    // 本会话此刻生效的分类
}
```

还有一条诊断路由 `GET /bio-skills/presets`，把 13 个预设各自的挂载诊断透出来（`agent-preset-registry` 只在 Host 日志里写一行 warn，桌面端看不到）：

```jsonc
{
  "ok": true,
  "instances": 13,
  "presets": [
    { "id": "biomedical", "name": "生物医学模式", "order": 5, "broken": null },
    { "id": "bio-clinical", "name": "临床解读与精准医学", "order": 12, "broken": "…失败的那一行…" }
  ]
}
```

`broken` 非 `null` 就说明该预设挂载被拒（模式卡片会显示「加载失败」）。**排查预设问题先看这条路由**，比猜快得多。

> ### 三个已修的真实故障（都表现为「专项模式加载失败」）
>
> 1. **抢路由**：13 份 picker 都注册 `/bio-skills/get`，第二个起 `webserver: duplicate exact route` → 该行 failed → 整个预设挂载被拒。现在路由进程级共用（引用计数）。
> 2. **必填 config 缺失（真正的元凶）**：12 个专项模式的 `agent-instructions` 与 `tool-fs-search` 两行没写 config，而这两项在各自 schema 里是 `.required()`、**没有默认值**：
>
>    ```
>    agent-instructions: invalid config:
>      - $.maxBytes missing required value (at maxBytes)
>    tool-fs-search: invalid config:
>      - $.sampleOverCapGlobResults missing required value (at sampleOverCapGlobResults)
>    ```
>
>    两行 failed → 整份预设判 failed → 挂载被拒。全量模式两项都写了，所以只有它能用。
>    （最初误判成「省略即走默认值」，是 `/bio-skills/presets` 的 `broken` 原文纠正的。）
> 3. **平台守卫缺失**：12 个专项模式的 `tool-bash` / `tool-pwsh` 漏了 `disabled: !!js process.platform …`。它没有出现在 `broken` 里（说明并未触发失败），但和全量模式不一致——Windows 上会多出一个跑不了的 bash 工具，属一致性修复。
>
> 上面三条现在都由 `tools/lint-presets.mjs` 检查：漏守卫、漏必填 config 都直接报错。

> **注意**：13 份预设各自挂一个 `bio-mcp`，所以启动后会有 **13 个 `biomedical_mcp.py` 进程**（每个约 23 MB，实测）。这属于既定设计（各模式都能直接拿数据工具），不是泄漏；关掉不用的预设才会减少。

### 设置页：按组分节

设置页把这 34 个分类上卷成 **6 个大组**，按组分节显示，组间有分隔线：

<!-- gen:groups-table 由 tools/gen.mjs 生成，不要手改 -->
| 大组 | 分类数 | 技能数 |
|---|---|---|
| 测序与变异 | 8 | 96（+47 个流程） |
| 组学与单细胞 | 10 | 143（+81 个流程） |
| 结构与药物 | 5 | 79（+5 个流程） |
| 临床与影像 | 4 | 47（+10 个流程） |
| 方法与工程 | 5 | 55（+9 个流程） |
| 文献与写作 | 2 | 29 |
<!-- /gen:groups-table -->

每组标题行显示「N 个分类 · M 个技能 · 已启用 X」，并带该组的「全开 / 全关」；组内默认只列出前 4 个分类，其余折叠在「还有 N 个分类 · 展开」后面。顶部保留全局「全部开启 / 全部关闭」。

分组定义在设置页 bundle 的 `GROUPS` 常量里；这里没覆盖到的分类会自动落进「其他」组，不会从页面上消失。

### 分类一览

<!-- gen:categories-table 由 tools/gen.mjs 生成，不要手改 -->
| 分类 | id | 技能数 | 覆盖 |
|---|---|---|---|
| 测序质控与比对 | `sequencing-qc-alignment` | 11（+9 个流程） | 把原始测序读段变成可信的比对结果，并回答数据质量、覆盖与污染能不能用。 |
| 基因组组装与比较基因组 | `genome-assembly-comparative` | 7（+14 个流程） | 从长读长或混合数据组装并注释基因组，再比较多个基因组的共线性、泛基因组与进化关系。 |
| 变异检测与过滤 | `variant-calling-filtering` | 11（+6 个流程） | 从比对结果或读段得到胚系、体细胞或靶向 SNV/Indel，并完成规范化与质控过滤。 |
| 拷贝数变异与结构变异 | `copy-number-structural-variation` | 9（+2 个流程） | 检测缺失、重复、倒位、易位、重复扩增与等位失衡，并解释拷贝数与结构层面的改变。 |
| 变异解读与罕见病诊断 | `variant-interpretation-clinical` | 10（+2 个流程） | 把变异注释到基因与后果，按 ACMG/AMP 证据分级并支撑罕见病与家系诊断结论。 |
| 群体遗传与 GWAS | `population-genetics-gwas` | 22（+7 个流程） | 在人群层面找疾病关联位点、构建遗传评分并推断因果、共定位、精细定位与祖源结构。 |
| 肿瘤基因组与液体活检 | `cancer-genomics-liquid-biopsy` | 22（+7 个流程） | 刻画肿瘤体细胞突变、克隆演化与可用标志物，并用 cfDNA/ctDNA 做早筛、监测与残留病判断。 |
| 法医与身份鉴定 | `forensic-identity-genetics` | 10 | 用 SNP、STR、Y 染色体与线粒体标记完成身份、亲缘、混合样本与祖先来源判定。 |
| 临床精准医学与结局分析 | `clinical-precision-medicine` | 10 | 评估生物标志物与预测模型，划分患者亚组，并把证据与结局分析整理成可交接的临床材料。 |
| 医学影像与放射组学 | `medical-imaging-radiomics` | 12（+1 个流程） | 处理 CT/MRI/病理等影像数据，做分割、配准、特征提取、模型训练与可信度评估。 |
| 显微成像与细胞表型 | `microscopy-cell-phenotyping` | 14（+4 个流程） | 从显微、流式与空间蛋白图像定量细胞形态、分割、计数、追踪并比较组间表型。 |
| 转录组上游与定量 | `transcriptomics-quantification` | 13（+20 个流程） | 从 RNA 读段得到表达矩阵，处理链特异性、异构体组装、融合、剪接与 RNA 修饰证据。 |
| 差异表达与功能富集 | `differential-expression-enrichment` | 10（+1 个流程） | 在组学矩阵上做组间差异与统计建模，并把结果落到通路、基因集与功能解释。 |
| 单细胞基础分析 | `single-cell-core` | 14（+7 个流程） | 完成单细胞数据的质控、双细胞与环境 RNA 清理、降维聚类、注释与对象格式管理。 |
| 单细胞高级与虚拟细胞 | `single-cell-advanced-virtual-cell` | 20 | 在单细胞数据上做轨迹、通讯、扰动预测、多模态与队列复现等机制性推断。 |
| 空间组学分析 | `spatial-omics` | 10（+6 个流程） | 利用空间坐标回答组织里谁在哪里、谁挨着谁，并识别空间域、邻域与细胞组成。 |
| 蛋白质组学 | `proteomics` | 13（+9 个流程） | 从质谱原始数据到肽段鉴定与蛋白定量，并处理修饰、亲和平台与定量质量。 |
| 代谢组与脂质糖组 | `metabolomics-lipidomics` | 18（+1 个流程） | 把质谱、NMR 或电泳信号转成可信的代谢物、脂质与聚糖注释和定量结果。 |
| 表观遗传与 DNA 甲基化 | `epigenomics-methylation` | 20（+12 个流程） | 处理 ChIP/ATAC/CUT&RUN、Hi-C 与亚硫酸氢盐数据，识别 peak、染色质状态、三维结构与甲基化差异。 |
| 调控网络与序列模型 | `regulatory-network-sequence-models` | 17（+2 个流程） | 推断转录因子调控网络与模块，或用基因组基础模型评估序列变异的调控效应。 |
| 微生物组与宏基因组 | `microbiome-metagenomics` | 16（+23 个流程） | 从扩增子或 shotgun 数据得到物种、功能、耐药与菌株结果，并做群落比较与传播分析。 |
| 结构预测与建模 | `structural-biology-modeling` | 18（+1 个流程） | 预测或准备蛋白与复合物结构，评估质量、相似性与界面几何并做动力学分析。 |
| 化学信息学与药物设计 | `chemoinformatics-drug-design` | 27（+1 个流程） | 围绕小分子做结构标准化、描述符、相似性、对接与筛选、成药性与毒性排序。 |
| 蛋白工程与合成生物学 | `protein-engineering-synbio` | 15（+1 个流程） | 设计蛋白序列与骨架、优化表达与可开发性，并把构建放进代谢与自动化实验方案。 |
| 基因编辑与分子克隆 | `gene-editing-cloning` | 12（+2 个流程） | 设计 gRNA、供体与筛选文库，评估脱靶与编辑结果，并完成克隆相关的序列层面设计。 |
| 药物基因组学与用药 | `pharmacogenomics-dosing` | 10 | 把基因型转成星等位基因与表型，落到具体药物的剂量、疗效与安全性建议。 |
| 免疫组学与免疫治疗 | `immunology-immuno-oncology` | 13（+5 个流程） | 分析受体库、HLA、新抗原与免疫浸润，评估免疫治疗获益与疫苗表位覆盖。 |
| 文献检索与证据合成 | `literature-evidence-synthesis` | 12 | 检索、核验并综合文献与数据库证据，形成可核查的综述、评审与证据强度判断。 |
| 写作与文档交付 | `writing-document-delivery` | 17 | 把分析与文献写成论文、基金、海报或报告，并导出合规的 Word/PDF/PPT 交付件。 |
| 数据工程与统计方法 | `data-engineering-statistics` | 23（+2 个流程） | 整理表格与格式、建立统计与机器学习评估、管理隐私与数据交换的工程性任务。 |
| 计算流程与可复现性 | `workflow-reproducibility` | 5（+5 个流程） | 搭可复现的分析环境与流程，追溯输入与版本，并审计结果漂移与助手可靠性。 |
| 数据库与接口对接 | `database-api-access` | 11（+1 个流程） | 通过 API 或公共库取回基因、变异、结构、组学与文献数据，并核对版本与可用性。 |
| 可视化与图件 | `visualization-figures` | 9 | 把数据与结构做成清晰可发表的图表、轨道、示意图或渲染好的图形交付件。 |
| 研究设计与假设生成 | `research-design-hypothesis` | 10（+1 个流程） | 把宽泛兴趣收束成可检验问题，规划数据、对照、样本量与验证路线。 |
<!-- /gen:categories-table -->

### 技能来源

- **上游技能插件（576 个）**：取自本机已安装的 27 个技能插件的发布内容（2026-10-30 版本）。其中 134 个原始占位名（`*-skill-<hash>` 形式）已改写为语义化 kebab 名称；跨插件重名的 9 个只保留一份。
- **2.5.0 移除的 6 个**：`docx` / `pdf` / `xlsx`（许可证为 Anthropic「All rights reserved」，不能随 MIT 包再分发；DSH 自带 `office-docx` / `office-xlsx` / `office-export-pdf` 可替代）、`morning`（晨间简报，与本模式无关）、`pathway-enrichment-analysis`（14 行，完全被 `pathway-enrichment` 覆盖）、`review-paper`（偏人文社科审稿，科研稿件审稿由 `paper-review` 负责）。同时清掉了 23 个评测报告 / 调试脚本 / 中间产物。
- 许可证与来源见 [THIRD_PARTY.md](THIRD_PARTY.md)；`tools/lint-skills.mjs` 会拒绝「保留所有权利」的许可证和开发残留文件。
- **自建（21 个）**：`skills/omics`，其中 11 个按官方文档整编（`SKILL.md` + `references/{official-docs,parameters,troubleshooting}.md`，命令均标注官方来源，官方未提供可执行命令处显式标注）。

### 目录成本

目录实际列出的 445 个技能（nf-core 流程折叠后）的 name + description 合计 **47 399 字符 ≈ 2.2 万 token**（`name` 12 574 + `description` 34 825，单条描述按目录截断 500 字计；2.6.0 起所有描述都不超过 500 字）。2.5.0 时 597 个技能合计 75 703 字符 ≈ 3.4 万 token：折叠 nf-core 和精简 63 条描述共减少 37%。

**这是全开时的成本。** 用分类开关按需裁剪后显著下降：

| 保留范围 | 约 token |
|---|---|
| 全开 34 类 | 35 000 |
| 4 类（组学 + 数据工程与统计 + 文献与证据合成 + 写作与文档交付） | 14 000 |
| 2 类（例如单细胞核心 + 单细胞进阶） | 3 000–5 000 |

### 技能目录的兜底

`picker` 是 preset 里唯一的技能 provider，因此做了三层兜底：

1. **catalog 损坏或缺失** → 自动退化为直接扫描 `skills/*/*/SKILL.md`，597 个技能照常可用（分类标记为 `fallback`），文件修好后下次 `list()` 自动恢复。
2. **启用的分类一个 SKILL.md 都读不到**（skills/ 目录损坏）→ 退化为全量扫描。注意：用户**主动**关掉所有分类（设置页全关、浮窗「全部关闭」）时返回 0 个技能，不再退回全量——以前这里会把"全关"变成"加载全部 603 个"。
3. **picker 模块本身加载失败**（改坏 JS、依赖解析失败）→ patch 里预置了 6 行 `skill-filesystem` hub，默认 `disabled: true`（零开销）；在插件页逐个打开即可恢复全部技能。启用前先禁用 picker 行，否则同一技能会由两个 provider 各提供一份。

第 1 层已实测（catalog 损坏 → 仍返回全部技能）；「全关 → 0 个」由 `scope-test.mjs` 覆盖。第 3 层是给"下次改坏代码"买的保险。

## 让 agent 选准技能与工具

目录越大、近义技能越多，agent 越容易选错。这一节的机制都以「先缩小候选、再让每个候选说清自己」为目标，效果用下文「路由评测」衡量。

### 1. nf-core 流程折叠到一个入口

152 个 `nfcore-*` 流程技能不再逐个列进目录（catalog 条目带 `"via": "nfcore-catalog"`），目录只露出入口 `nfcore-catalog`，全量目录从 597 个降到 445 个（约 2.5 万 token，原来约 3.3 万）。

- 范围内只要有被折叠的流程，入口就会出现在目录里，即使入口自己所在的分类没开（它在「计算流程与可复现性」）。
- 加载入口时，picker 在正文末尾追加一份**按当前技能范围生成**的流程索引：每个流程一行，含说明和 SKILL.md 绝对路径。DSH 的 `skill` 工具只能加载目录里列出的技能，所以索引要求 agent 用文件工具直接打开对应 SKILL.md。
- 代价：这 152 个流程不能再用 `/nfcore-xxx` 直接调用。

### 2. `skill_scope`：agent 自己收窄范围

picker 在每个预设里注册一个模型可调用的工具 `skill_scope`，写入的是和浮窗同一份会话覆盖，下一步起目录按新范围生成。

| 参数 | 作用 |
|---|---|
| `categories` | 保留的分类 id（1–8 个），默认替换当前范围 |
| `add: true` | 在当前范围上追加（专项模式里加开别的领域） |
| `reset: true` | 清除会话覆盖，恢复模式默认 |

全量模式的 persona 要求 agent 理解任务后先调用一次，收窄到 2–4 类；专项模式在任务超出范围时用 `add: true` 加开。DSH 每次目录变化都会追加一份完整新目录，所以 persona 也要求「只在开工时调一次、不要来回切换」。

### 3. MCP 工具按模式裁剪

MCP 服务支持 `--domains`（或环境变量 `BIO_MCP_DOMAINS`）：`tools/list` 只返回这些领域的工具，调用未启用领域的工具会返回可读的错误。领域定义在 `mcp/domains.json`（服务与生成器共用）：

| 领域 | 说明 | 工具前缀 |
|---|---|---|
| `literature` | 文献与预印本 | `pubmed_` `biorxiv_` `literature_graph_` |
| `genome` | 基因组注释与调控 | `genomes_` `biomart_` `rna_rfam_` `regulation_` |
| `variant` | 变异与人群频率 | `variants_` `human_genetics_` |
| `expression` | 表达与组学数据集 | `expression_` `omics_archives_` `cellguide_` |
| `protein` | 基因功能与蛋白注释 | `genes_ontologies_` `protein_annotation_` |
| `structure` | 蛋白结构 | `structures_` |
| `chemistry` | 化合物与药品监管 | `chembl_` `chemistry_` `zinc_` `drug_regulatory_` |
| `clinical` | 临床试验与肿瘤证据 | `clinicaltrials_` `clinical_genomics_` `cancer_models_` |

全量模式启用全部领域；12 个专项模式在 `spec/modes.json` 的 `mcpDomains` 里声明，生成器写进各自的 `--domains`，并检查「模式内技能声明的工具都落在该模式的领域里」，不满足就拒绝生成。容易混淆的工具（PubMed / OpenAlex / arXiv、Ensembl / MyGene / BioMart、gnomAD / dbSNP、PubChem / ChEMBL、ClinVar / CIViC 等）在描述里写明了何时换用哪个。

### 4. 技能声明自己用哪些 MCP 工具

70 个查库型技能在 catalog 条目里声明了 `mcp`（也支持在 SKILL.md frontmatter 写 `mcp: [tool_a, tool_b]`，优先于 catalog）。加载这类技能时，picker 在正文最前面加一行「本技能常用的 MCP 数据工具：…」，agent 不必再从 51 个工具里找。`lint-skills.mjs` 检查声明的工具真实存在。

### 5. 描述规范

目录里模型只看得到名字和描述（截断 500 字），描述就是路由依据。统一格式：**关键名词在前（数据类型、主要工具），写清做什么、什么时候用，以及什么时候换用哪个技能**。这次改写了 63 条：8 条法医类模板句、46 条纯英文描述、9 条超过 500 字（后半段的触发词被截掉）的描述；另外给 13 个容易混淆的技能补了分工说明。`lint-skills.mjs` 强制：

- 描述不能为空、不超过 500 字、必须有中文；
- 不能是「在 X 领域开展“Y”任务时使用」这类模板句；
- 同分类内词面相似度 ≥ 0.4 的两条描述必须互相点名（≥ 0.3 时给出提示）。

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
- 统一 4 次重试、指数退避，覆盖 429/500/502/503/504；单次请求 45 秒超时

### 并发、时限与限速

| 机制 | 行为 |
|---|---|
| 并发执行 | `tools/call` 在线程池里跑（`BIO_MCP_WORKERS`，默认 4），一个慢接口不会堵住后面的请求 |
| 单次调用总时限 | `BIO_MCP_CALL_BUDGET`，默认 100 秒，**包含全部重试与退避**，短于客户端的 `toolCallTimeoutMs: 120000`；超时直接返回可读的错误，不再出现「客户端已超时、服务端还在重试并堵住队列」 |
| 取消 | 收到 `notifications/cancelled` 立即停止重试，且按 MCP 约定不再回响应 |
| NCBI 限速 | E-utilities 进程内限速：无 key 3 次/秒，设 `NCBI_API_KEY` 后 10 次/秒；所有请求带 `tool=dsh-biomedical-mcp`，设 `NCBI_EMAIL` 时带联系邮箱（NCBI 官方要求） |
| 返回体积 | 紧凑 JSON（以前 `indent=2`，空白占三成以上 token） |
| PubMed 摘要 | `pubmed_search_articles` 加 `include_abstract: true` 一并取摘要；`pubmed_get_article_metadata` 默认带摘要。证据分级不用再另外抓网页 |

环境变量都可选，在 `cordis.patch.yml` 全量模式 `bio-mcp` 行的 `config.env`（`dsh-mcp-client` 支持的字典字段）里设置即可，12 个专项模式通过 `*bio-mcp-config` 锚点自动共用；也可以在启动 DSH 前导出。限速是**进程内**的：13 个预设各有一个 MCP 进程，同时在多个模式里密集查 NCBI 仍可能触发 429（会自动退避重试）。

---

## 开发自检

改这两处（`client.js` 的客户端半、`picker/` 的宿主半）之前先知道：历史上两次
「应用无法启动」和一次「12 个模式全是加载失败」都出在这一层。仓库里带了几个
不依赖 DSH、不依赖浏览器、不联网的自检脚本，提交前全部跑一遍：

```sh
node tools/gen.mjs --check     # 生成产物与数据源一致（见下「改技能或模式」）
node tools/lint-skills.mjs     # 技能库：目录 ↔ catalog、重名、许可证、开发残留、描述规范、声明的 MCP 工具存在
python tools/mcp-test.py       # MCP：工具清单、领域过滤、并发、取消、总时限、NCBI 参数、摘要解析（22 项）
node tools/route-eval.mjs --validate  # 路由评测用例：技能 / 工具名有效、34 类都有用例
node tools/scope-test.mjs      # 73 项（含 nf-core 折叠与流程索引、skill_scope、技能附带 MCP 工具、「全部关闭 → 0 个」、嵌套派活被拒）：模块 id、三处 slot 注册、12 大类渲染、
                               # 三态开关、POST 载荷、Esc、拖动、13 实例共用路由、
                               # 引用计数注销、register/inject 抛错时 apply 不炸
node tools/lint-presets.mjs    # 13 个预设结构体检：行数、only 白名单、
                               # 12 专项是否正好覆盖 34 类且不重叠、
                               # tool-bash/tool-pwsh 的平台守卫是否都在、
                               # 每个模式是否挂了共享纪律 suffix、picker 是否写了 preset、
                               # 有没有写死本机绝对路径、persona 点名的技能是否存在
```

### 路由评测：agent 能不能选对技能和工具

改技能描述、删合并技能、调整模式划分之前和之后各跑一次，用数字判断是变好还是变差。

- 用例：`eval/routing/cases.json`，173 条真实请求，覆盖全部 34 类。每条给出「任一命中即算对」的可接受技能（`skills`）与 MCP 工具（`tools`），并带标签：`clear` 表述明确、`lay` 外行表述、`dup` 涉及近义技能、`nfcore` 答案含 nf-core 流程、`mcp` 需要查库、`en` 英文、`vague` 目标宽泛。
- 每条用例跑两种目录：**全量**（597 个技能全部可见）和**专项模式**（只看正确答案所在模式的技能），两者之差就是「先缩小候选」的收益。
- 指标：`skill@1`（首选即正确）、`skill@3`、MRR、编造技能名比例、`tool@3`；另外按分类、按标签汇总，并列出最常见的「正确答案 → 实际首选」混淆对，直接指向该改哪两条描述。

```sh
node tools/route-eval.mjs --router bm25                     # 离线词法基线，不联网
ROUTE_EVAL_API_KEY=sk-... node tools/route-eval.mjs --router llm               # 真实模型（默认 DeepSeek，OpenAI 兼容接口）
ROUTE_EVAL_API_KEY=sk-... node tools/route-eval.mjs --router llm --baseline eval/routing/results/baseline-llm.json
```

`--router llm` 默认请求 `https://api.deepseek.com` 的 `deepseek-chat`，可用 `ROUTE_EVAL_BASE_URL` / `ROUTE_EVAL_MODEL` 换成其它 OpenAI 兼容服务；`--mode full|specialist|both`、`--tag lay`、`--limit 20`、`--concurrency 4` 控制范围。模型回复按「模型 + 提示词」缓存在 `eval/routing/.cache/`（不进仓库），重跑不会重复计费；技能目录作为固定的系统提示放在最前面，DeepSeek 的上下文缓存会让重复部分按缓存价计费。

结果写到 `eval/routing/results/`（只有 `baseline-*.json` 进仓库）。评测与实际行为保持一致：折叠的流程不在目录里、答案是折叠流程时选中入口也算对；专项模式只看得到该模式 MCP 领域内的工具。BM25 建索引时会去掉「X 用 Y」这类点名其他技能的分工子句（它们是写给读者的「不该选我」，词法检索会误当成命中）。

当前离线基线 `baseline-bm25.json`（2.6.0，目录 445 个技能）：全量 skill@1 74.9%、skill@3 85.6%；专项模式 81.4%、94.6%。2.5.0 时（目录 597 个）分别是 74.3% / 86.8% 和 81.4% / 94.0%——目录小了 25%，词法基线基本持平。BM25 的局限要心里有数：

- 它偏乐观：用例是对照目录写的，用词和描述重合度高；`lay` 外行表述只有 50–60%，真实用户的说法更接近这一档；
- 它衡量不了这轮改动最想改善的几件事：跨语言（描述统一成中文后英文提问在词面上匹配不上，模型却能理解）、读懂「何时换用哪个」、先选入口再选流程、`skill_scope` 收窄。

所以真实效果请用 `--router llm --out eval/routing/results/baseline-llm.json` 生成模型基线后提交，之后每次改描述、改目录都和它比。

### 改技能或模式：只改数据源，再跑生成器

以前 13 个预设是 2400 行复制粘贴的 YAML，`client.js` 里 600 条技能说明也是手工同步的——README 里记录的「漏必填 config」「漏平台守卫」两次事故都出在这种复制上。现在：

| 要改什么 | 改哪里 |
|---|---|
| 增删技能、改分类、改技能短说明 | `picker/catalog.json`（每个技能 `name` / `path` / `desc`） |
| 12 个专项模式的名称、说明、排序、包含的分类、浮窗图标颜色 | `spec/modes.json` |
| 设置页的 6 个大组 | `spec/settings-groups.json` |
| 专项模式的 persona 与插件行 | `spec/specialist-preset.yml.tpl`（共享纪律、MCP 配置通过 YAML 锚点引用全量模式，改全量模式即全体生效） |
| 全量模式、共享纪律 suffix | `cordis.patch.yml` 里 `gen:` 标记区间之外的手写部分 |

然后 `node tools/gen.mjs`，它会重写 `cordis.patch.yml` 的专项模式与设置开关、`client.js` 的 `LABELS`/`GROUPS`/`SKILLS`/`SECTIONS`、`settings/config.mjs`、README 的三张表和 locale 里的技能数。标记区间内不要手改，下次生成会被覆盖。

`scope-test.mjs` 用最小 React 替身跑组件、用假 `ctx` 跑 `apply()`、用假
`request/response` 跑 picker 的路由，所以不需要启动 DSH，也不需要浏览器。

## 并发与资源约束

| 约束 | 值 | 机制 |
|---|---|---|
| 每会话同时运行的子智能体 | **3** | `subagent-cap.mjs` 在 `tools/execute` 上按 `exec.agent.id` 分桶计数，超限返回 `ACTIVATION_LIMIT_REACHED` |
| 委派深度 | **1**（只有主智能体能派活） | `tool-subagent` / `tool-subagent-fork` 行设 `maxDepth: 1`，工具层直接拒绝；`subagent-cap` 再按 `delegationDepth` 兜一层，返回 `NESTED_DELEGATION_DENIED`。以前按 agent 分桶计数，子智能体再派活会落进新桶、绕过上限 |
| workflow 扇出并发 | **3** | `workflow-ptc.maxConcurrentAgents` |
| 重计算并行 | **1** | 仅 persona 纪律（组学流程吃满内存，并行只会一起 OOM）。后台任务的并发上限属于全局的 `dsh-jobs-local`（`maxConcurrentJobsPerOwner`），不在预设作用域里，改它会影响所有模式 |
| Host 全局子代理池 | 8（未改动） | 其它模式不受影响 |

并发闸只作用于**使用本预设的会话**：`tools/execute` 是 agent-scope 过滤的 waterfall，其它模式的工具调用不会经过它。`spawn_teammate`（Agent Teams）不计入，因为它是 fire-and-return，包裹期覆盖不到实际运行，所以 persona 里直接禁止用它派活。

---

## 平台要求

| 项 | 要求 |
|---|---|
| DSH | `^0.2.1-rc.2`（包内 `engines.dsh`，与市场索引条目一致） |
| Python | 3.x，只用标准库；默认调用 DSH 自带 `dsh-primary-runtime` 的 python |
| 网络 | 出网访问公开 REST API（NCBI/EBI/Ensembl/RCSB/Broad/EMBL 等） |
| 磁盘 | 包本体约 20 MB（未压缩；597 个技能的 2047 个文件占绝大部分） |
| 权限 | 安装需要 profile 的 Full access 或审批；`plugin_manager` 每个动作都需要审批（无 Full 时） |

---

## 仓库结构

```
cordis.patch.yml        本包装配：内层 28 个插件行；profile 里插 2 行（预设 + 设置页）
package.json            包声明：dsh.bundle（patch）+ dsh.client（设置页）/ exports / files / engines.dsh
subagent-cap.mjs        子智能体并发闸（tools/execute 作用域，限 3 并发）
paths.cjs               包内路径（供 patch 的 !!js 表达式按包名同步解析）
shared/profile.mjs      定位 profile 目录（picker / 设置页共用）
shared/frontmatter.mjs  SKILL.md frontmatter 解析（picker 与评测共用）
shared/mcp-tools.mjs    读取 MCP 工具清单与领域（评测、lint 共用）
picker/                 技能 provider：catalog.json（34 类 x 597 技能，含每个技能的短说明）+ index.js
spec/                   生成器数据源：modes.json（12 个专项模式）、settings-groups.json、specialist-preset.yml.tpl
tools/                  gen.mjs（生成器）、route-eval.mjs（路由评测）与自检：scope-test / lint-presets / lint-skills / mcp-test.py
eval/routing/           路由评测用例（cases.json）与基线结果（results/baseline-*.json）
settings/               设置页 Host 半：index.js（Config + 镜像）/ config.mjs（浏览器半在包根 client.js）
mcp/biomedical_mcp.py   51 个数据源工具（stdio JSON-RPC，纯标准库）
mcp/domains.json        MCP 领域定义（服务的 --domains 与生成器共用）
skills/                 6 个域目录 / 597 个技能 / 2047 个文件
  omics/                 21 个（自建，按官方文档整编，带 references）
  genomics/             140 个（基因组/群体遗传/肿瘤/临床基因组/液体活检/法医）
  omics-upstream/       193 个（转录/蛋白/代谢/表观/空间/多组学/单细胞/微生物组）
  structure-drug/        79 个（结构生物学/AI 药物发现/合成生物学/药物基因组/基础模型）
  clinical-imaging/      36 个（精准医学/AI 医学影像/衰老长寿）
  methods/              128 个（基础设施/方法学/网络系统生物学/免疫组学/生物医学科学）
locale/{en,zh}.json     市场展示元数据（meta.title / meta.description）
icon.svg                原创图标（双螺旋，632 B）
market/index.json       插件市场索引（format 1），只列本包一个条目
market/icons/           索引引用的图标目录（biomedical.svg）
README.md               本文件
THIRD_PARTY.md          第三方技能的许可证与来源
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
