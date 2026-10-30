---
name: surveymaster-identify
version: 0.2.0
description: 收集综述写作的初始需求，并生成 Stage 1 写作约束产物。在 SurveyMaster 工作流开始、文献检索之前使用。会在指定综述输出目录下生成 writing_constraints.json 和 writing_constraints.md。
argument-hint: "--topic <text> --subject <discipline> [--language zh|en] [--citation-style gb-t-7714-2015-numeric|gb-t-7714-2015-author-date|ieee|ama|apa|nature|acs|cell|science|elsevier-with-titles|rsc] [--target-paper-count N] [--focus-points text] [--reference-surveys text] [--year-range text] [--extra-requirements text] [--output-format text] [--section-length-policy json] [--total-length-target text] --output-dir <dir>"
---

## 阶段契约

阶段：1 — 需求采集与写作约束。

加载者：当 SurveyMaster 编排器尚无已确认的 `writing_constraints.json`，或 `citation_style_confirmed` 仍为 `false` 时读取。

必需输入：
- 用户主题和学科领域。
- 综述语言，显式给出或推断得到。
- 由编排器解析好的引用格式，可以是用户显式提供，也可以是在调用此说明前已选择。
- 目标论文数量和关注点，显式提供或使用默认值。
- 可选的参考综述、年份范围、输出格式、长度策略和额外要求。
- `$WORK` 输出目录。
- browser-use、remote-browser 或等价的运行时浏览器 MCP 工具，用于种子论文元数据发现，以及后续文献检索准备。

输出：
- `$WORK/writing_constraints.json`，作为结构化事实源。
- `$WORK/writing_constraints.md`，作为面向用户的派生视图。

完成条件：
- `writing_constraints.json` 存在。
- `citation_style_confirmed` 为 `true`。
- `writing_constraints.md` 存在，并且已经作为面向用户的信息摘要展示或报告给调用方。
- 正常 Stage 1 执行期间，browser-use、remote-browser 或等价浏览器 MCP 工具可用。

可以加载其他技能：
- 否。

## 文件写入策略

使用当前运行时提供的文件写入/编辑工具。始终把 `writing_constraints.json` 作为事实源：先创建或修改 JSON，再从 JSON 渲染 `writing_constraints.md`。不要用 shell heredoc 写 JSON、Markdown 或类 LaTeX 内容，因为反斜杠和引号可能被破坏。

## 无脚本 — 由 Agent 直接执行

此阶段**没有辅助脚本，也没有 `scripts/` 目录**。所有操作都由 agent 使用当前会话可用工具直接执行。

文献发现只能使用 browser-use、remote-browser 或等价的运行时浏览器自动化 MCP 工具，例如能打开真实网页、导航/搜索、读取页面内容并抽取元数据的 `mcp_remote_browser_*`。不要使用任何非浏览器检索工具作为替代，包括 `web_fetch`、`academic_search_en`、`WebSearch`、`PaperLookupByDoi` 或 `PaperLookupByTitle`。

正常执行要求 browser-use、remote-browser 或等价浏览器 MCP 工具可用。如果当前没有可见浏览器工具，先执行运行时的工具发现/find_tools，搜索 `browser`、`remote-browser`、`remote browser`、`browser automation`、`MCP remote browser` 等关键词；若发现 `mcp_remote_browser_*` 等匹配工具，应激活并使用。只有完成发现后实际调用仍表明浏览器工具不可用，才在写入任何输出前中止，并提示用户开启 browser-use/remote-browser。

不要尝试运行 `python3 <skill_dir>/scripts/...`；Stage 1 没有此类脚本。

## 目的

为综述工作流生成 Stage 1 写作约束。此说明是需求采集阶段的契约；它不构建文献库、不生成大纲，也不撰写综述正文。

## 输出

在 `<output-dir>` 下创建这些文件：

| 文件 | 作用 | 是否为事实源 |
|---|---|---|
| `writing_constraints.json` | 下游阶段使用的机器可读约束 | 是 |
| `writing_constraints.md` | 面向用户的渲染视图 | 否，派生文件 |

不要创建 `identity.md` 输出产物。如果外部存在 `identity.md` prompt，只把它当作参考文本。

## 必需输入

一次性收集所有缺失的必需字段：

- `topic`
- `subject`（学科）
- `language`（`zh` / `en`；通常由编排器显式传入。如果缺失，只能从当前请求推断：显式输出语言表述优先；否则使用完整请求正文的主导语言；否则使用 topic/focus 文本的主导语言。不要查看已有 `writing_constraints.json`、`outline.json`、文件名或先前产物。）
- `target_paper_count`（默认：`50`）
- `focus_points`（1-5 项）

可选字段：

- `citation_style`（见“引用格式”；通常由编排器在首次生成前提供）
- `reference_surveys`
- `year_range`（默认：最近 8 年）
- `extra_requirements`
- `section_length_policy`
- `total_length_target`

最终 JSON 中不得留下空字段。如果某个值仍未知，设置明确默认值，并在 `assumptions` 中记录原因。

## 不做数量预测

不要陈述或暗示任何依赖外部检索或 LLM 生成、且尚未计算出的具体数量。这包括：

- “I will search for N papers” / “会找到约 N 篇文献”
- “The survey will be N words long” / “预计字数约 N 字”
- “This will produce N sections” / “将生成 N 个章节”

只能报告来自已执行脚本或已完成检索的数量。规划时使用开放表述，例如“我们会检索匹配关注点的论文”“正文长度会遵循你设置的约束”。

## 种子论文

在写入任何输出文件前，扫描所有用户提供的输入（topic、focus_points、extra_requirements 以及任何自由文本），识别候选论文引用。

**识别模式**（识别以下任意形式）：
- DOI 模式：文本任意位置出现 `10.\d{4}/...`
- arXiv ID：`arXiv:\d{4}.\d{4,5}` 或 `https://arxiv.org/abs/...`
- PMID、CNKI 条目、题名页链接、出版社页面链接等论文线索
- 足够像论文标题的带引号或不带引号标题字符串（>= 6 个词）
- 作者 + 年份引用：“Smith et al., 2023”、“Smith 2023”、“Smith and Jones (2022)”
- 自然语言描述：“the paper on X published in Nature in 2022”、“XX 等人 2023 年的工作”
- 用户表示已经找到的论文编号列表或项目符号列表

**解析 — 对每个识别出的引用执行（可并行时并行调用）：**
1. 只能使用 browser-use 或 remote-browser。通过浏览器打开权威元数据页面，并从页面中提取元数据。不要调用 `web_fetch`、`academic_search_en`、普通 web search 工具或论文 lookup API。遵守运行时 browser-use/remote-browser 生命周期规则。生命科学/医学类种子论文优先使用 PubMed 风格元数据页；经济学/中文学术论文优先使用 CNKI 风格元数据页（如可访问）；arXiv 标识符使用 arXiv 元数据页；带 DOI 的论文优先使用出版社、Crossref、OpenAlex、PubMed 或其他权威元数据页。
2. 只采集可审计元数据。不要下载全文，不复制全文，不粘贴长摘要。摘要只作为相关性判断和下游规划所需元数据。
3. 每个检测到的种子论文都必须按下方固定结构写入 `seed_papers`。如果元数据无法解析，把用户提供的标题或原始引用保存在 `title`，未知字段留空，并在 `assumptions` 中加入解释。
4. Stage 1 不创建也不更新 `papers.json`。种子论文只是 Stage 2 的候选输入；文献库阶段负责去重、校验、bib key 生成和插入。

不要跳过检测。如果用户提供 10 篇论文，必须把 10 篇都保留到固定 `seed_papers` 结构中，并在工具可用时解析元数据。

**用户提供信息的丢弃策略：**

当用户提供的 DOI、标题或其他论文引用无法可靠验证时，宁可保留为空字段的候选记录，也不要传播不可靠元数据：

- 如果 DOI 查询或浏览器元数据页没有返回结果，或返回标题明显不匹配，把用户原始引用保存在 `seed_papers`，未知字段留空，并加入 `assumptions` 说明。不要加入 `papers.json`。
- 如果标题搜索返回结果，但没有任何结果与用户提供标题可靠匹配（例如发表年份、venue 或第一作者差异明显），不要猜测；保留原始标题，未验证字段留空。
- 缺少作者、年份或 venue 的部分记录不得插入 `papers.json`；它只作为 Stage 1 种子论文候选存在。
- 如果用户坚持某篇论文正确但查找持续失败，请用户直接提供 DOI 或更准确标题，而不是插入未验证记录。

原则：**文献库中留空比放入错误记录危害更小。** 下游引用检查和 BibTeX 导出会标记缺失元数据，这可以修复；虚构或错误论文引用在导出后无法修复。

**根据已解析种子论文推断意图：**

解析可用元数据后，检查成功解析论文的 `title`、`abstract`、`journal` 以及可见关键词，用于：

- **验证或细化 `subject`：** 如果用户未显式指定 `subject`，从种子论文的主导领域/venue 推断，并在 `writing_constraints.md` 中标记为 `（搜索参考）` / `(from seed papers)`。
- **增强 `focus_points`：** 如果用户提供少于 3 个 focus_points，根据种子论文摘要中的重复主题，建议最多 2 个额外关注点，并在 `writing_constraints.md` 中标记为 `（来自候选文献推断）` / `(inferred from seed papers)`。
- **检测年份范围：** 如果未指定 `year_range`，将其设置为最早种子论文年份到当前年份，并标记为 `(from seed papers)`。

**JSON 存储**（`writing_constraints.json` 中的 `seed_papers` 数组）：

每个种子论文对象必须且只包含这些稳定字段：

```json
"seed_papers": [
  {
    "title": "Paper title",
    "authors": ["Author A", "Author B"],
    "year": "2024",
    "journal": "Journal Name",
    "doi": "10.xxxx/yyyy",
    "url": "https://example.com/paper",
    "abstract": "..."
  }
]
```

如果没有检测到种子论文，设置 `"seed_papers": []`。

字段规则：

- `title`：论文标题；如果未解析，则保存用户提供的原始论文引用。
- `authors`：作者显示名数组；未知时使用 `[]`。
- `year`：字符串年份，例如 `"2024"`；未知时使用 `""`。
- `journal`：稳定 venue 字段。它可以是期刊名、会议名、预印本服务器、工作论文系列、仓储库，或适用时的 `"unpublished"`；未知时使用 `""`。字段名固定为 `journal`。
- `doi`：规范化 DOI，不带 `https://doi.org/`；无 DOI 或未知时使用 `""`。
- `url`：纯 URL 字符串，不要写 Markdown 链接；未知时使用 `""`。
- `abstract`：来自可审计元数据来源的摘要；未知时使用 `""`。不要存全文。

不要向 `seed_papers` 条目添加 `bib_key`、`lookup_status`、`source_type` 或其他额外字段；Stage 2 负责规范化文献库记录和引用 key。

**Markdown 视图：** 当 `seed_papers` 非空时，在 `writing_constraints.md` 中加入一节：

```text
## 候选文献（用户提供）/ Seed Papers (user-provided)
- "MXene surface terminations..." — Smith, Jones (2023), Journal Name, DOI: 10.xxxx/...
- "Some Paper Title the User Typed" — 元数据未解析；已按用户输入保留
```

包含检测到的种子论文数量，并在 assumptions/defaults 部分说明未解析元数据。

## 意图保留

需求采集阶段必须把用户意图保留为可执行约束，而不只是概括主题。

- 如果用户指定了必需章节结构或确切部分名称，将这些名称逐字复制到 `extra_requirements`，并说明下游大纲标题应保持一致，除非用户之后批准修改。
- 如果用户点名了必需机制、变量、性质、应用方向或比较维度，将每个命名项用用户原话纳入 `focus_points` 或 `extra_requirements`。不要把具体项目合并进宽泛类别，导致后续消失。
- 如果用户标记了章节或主题优先级，将该优先级编码进 `section_length_policy`，并在 `writing_constraints.md` 中说明。
- 对于宽泛应用列表，将每个命名应用保留为覆盖检查项。下游大纲和写作阶段必须能够检查每个项目是否被覆盖。

## 引用格式

支持的参考文献样式名称只能是以下之一：

- `gb-t-7714-2015-numeric`
- `gb-t-7714-2015-author-date`
- `ieee`
- `ama`
- `apa`
- `nature`
- `acs`
- `cell`
- `science`
- `elsevier-with-titles`
- `rsc`

`citation_style` 应由编排器在首次调用前解析。如果用户初始请求未明确指定受支持样式，编排器会在调用此说明前要求用户选择。如果用户已经指定受支持样式，编排器将其映射到上述值之一并直接传入。

正常首次生成使用调用方提供的 `--citation-style`，并在 `writing_constraints.json` 中设置 `citation_style_confirmed: true`。

当未传入 `--citation-style` 时的兼容回退：

| `language` | 默认 `citation_style` |
|---|---|
| `zh` | `gb-t-7714-2015-numeric` |
| `en` | `ieee` |

该回退只用于旧流程或中断流程。此时写入默认样式，并设置 `citation_style_confirmed: false`；编排器必须先解析引用格式，并以 revise 模式再次调用此说明，才能继续推进。

当编排器在 revise 模式下带显式 `--citation-style` 调用此说明时，将 `citation_style` 设为用户选择，并在 JSON 中设置 `citation_style_confirmed: true`，然后重新渲染 `writing_constraints.md`。如果 revise 模式未显式传入 `--citation-style`，保留已有 `citation_style` 值和已有 `citation_style_confirmed` 标志不变。

## 期刊/会议与风格约束

Stage 1 通常不把 browser-use 工作量花在 venue/style discovery 上。除非用户明确要求目标期刊/会议投稿约束，否则使用回退默认值表，并将 `constraint_source` 设置为：

```json
{"name": "default", "url": null}
```

如果用户提到了目标期刊/会议，但没有明确要求应用该 venue 的投稿约束，把 venue 名称保存在 `extra_requirements` 或 `venue_style_notes` 中，但仍使用回退默认值表。

只有当用户明确要求目标 venue 约束、期刊/会议特定限制或投稿格式要求时，才运行基于浏览器的官方来源发现。此时使用 browser-use 或 remote-browser，核查官方 author guidelines、instructions for authors、review article guide 或 article-type requirement 页面。

**进度报告（中文综述）：** 将此步骤称为“期刊/会议投稿要求搜索”或“目标期刊写作规范搜索”。

仅当用户明确要求 venue-specific constraints 时，按以下可选发现优先级执行：

1. 如果 `extra_requirements` 或用户上下文中指定了目标期刊/会议，核查该 venue 的官方 author guidelines、instructions for authors、review article guide 或 article-type requirements 页面。
2. 如果没有指定目标 venue，但学科明显对应某个常见 venue family，仅在浏览器工具可用且结果可审计时，核查一个权威官方来源。
3. 如果没有找到有用官方来源，停止扩展检索，使用回退默认值表。不要不断扩展到泛化网页。

核查官方来源后，确认其是否包含综述类要求：review、survey、narrative review 或类似文章类型的专用字数限制、章节结构、参考文献数量建议、图表限制等。所有文章类型通用的作者指南不足够；视为无有用结果。

可用时提取具体约束：

- 总词数/字数限制
- 摘要限制和摘要结构
- 必需章节结构
- 参考文献数量建议
- 图/表限制 → 写为 `target_figure_count`（整数）和 `target_table_count`（整数）
- 特殊格式或 venue-specific requirements

`target_figure_count` / `target_table_count` 的解析顺序：
1. 用户在请求中明确说明数量（例如“需要 3 张图” / “include 2 tables”）→ 直接使用。
2. venue guide 指定图表限制 → 从中推导数量。
3. 两者都未指定 → 使用回退默认值（3 张图，2 张表）。

当用户或 venue 值高于默认值时，使用该值。不要把用户意图限制在默认值内。

在 `writing_constraints.json` 中加入 `constraint_source`：

```json
{"name": "<venue-or-source-name>", "url": "<url>"}
```

如果没有找到有用来源，使用：

```json
{"name": "default", "url": null}
```

不要引用本机个人 skill 目录或机器特定路径作为风格来源。只能使用本 skill 包内文件、运行时工具，或浏览器发现的可审计官方来源。

## 回退默认值

如果用户没有明确要求 venue/style constraints，或可选 venue-specific discovery 没有得到可执行约束，应用以下默认值：

| 字段 | zh | en |
|---|---|---|
| 正文长度 | 8,000 字 | 5,000 words |
| 摘要 | <=300 words，三段式结构 | <=300 words，三段式结构 |
| 必需章节 | 引言 -> 方法（可选） -> 主体讨论 -> 结论 | Introduction -> Methods (optional) -> Discussion -> Conclusion |
| 参考文献 | 50-75 | 50-75 |
| `target_figure_count` | 3（用户未指定时默认） | 3（用户未指定时默认） |
| `target_table_count` | 2（用户未指定时默认） | 2（用户未指定时默认） |
| 引言 | 600-1000 字 | 400-600 words |
| 每个正文 section | 1000-1800 字 | 700-1100 words |
| 结论 | 400-600 字 | 200-350 words |
| special_requirements | 无 | none |

## 领域写作模板

在应用“回退默认值”表之前，检查
`../surveymaster-domain-templates/README.md`，并从该目录加载匹配的模板文件。
当 topic 或 subject 明确匹配某个内置领域，且用户没有明确要求其他目标期刊、
会议或 venue-specific writing constraint 时，使用领域模板。

如果领域模板适用，使用其中的 `constraint_source`、`venue_style_notes`、默认约束
和写作模式要求，替代通用回退默认值。保留用户显式指定的长度、图表数量、
focus points、citation style 和 special requirements。如果没有清晰匹配的领域模板，
使用上面的通用“回退默认值”表。

## 图片配色策略

Stage 1 负责确定图片配色策略，并写入 `writing_constraints.json`：

- `"figure_color_policy": "low_saturation_color"`：普通低饱和学术彩色图。
- `"figure_color_policy": "black_and_grayscale"`：黑白/灰阶图。

默认行为：

- 非 economics empirical-style template，直接设置
  `figure_color_policy: "low_saturation_color"`，不询问用户。
- 如果用户明确要求彩色图，直接设置
  `figure_color_policy: "low_saturation_color"`。
- 如果用户明确要求黑白、灰阶，或 venue 要求黑白图，直接设置
  `figure_color_policy: "black_and_grayscale"`。
- 如果选中 economics empirical-style template
  （`constraint_source.name == "bundled economics empirical-style review template"`
  或 `venue_style_notes` 明确包含 `Economics empirical-style review`），且用户
  没有明确指定图片配色，则在写入输出前用 `ask_user` 询问一次。

经济学 empirical-style 图片配色 gate：

- 使用 `allow_other: false`。
- 中文综述提问：
  `本综述中的机制图、流程图和综述示意图需要使用哪种图片风格？`
- 英文综述提问：
  `Which visual style should mechanism, workflow, and review schematic figures use?`
- 选项：
  1. zh: `低饱和彩色学术配色（推荐）` -> `low_saturation_color`
     en: `Low-saturation academic color (recommended)` -> `low_saturation_color`
  2. zh: `黑白灰期刊风格` -> `black_and_grayscale`
     en: `Black-and-grayscale journal style` -> `black_and_grayscale`

如果 `ask_user` 不可用、超时、无答案，或返回 fallback/proceed-best-judgment
类消息，则默认使用 `low_saturation_color`，在 `assumptions` 中记录该 fallback，
并继续流程。此 gate 是偏好澄清，不是硬阻塞。

## JSON Schema

`writing_constraints.json` 至少必须包含：

```json
{
  "topic": "...",
  "subject": "...",
  "language": "zh",
  "citation_style": "gb-t-7714-2015-numeric",
  "target_paper_count": 50,
  "focus_points": ["..."],
  "reference_surveys": [],
  "year_range": "last 8 years",
  "extra_requirements": "none",
  "total_length_target": {"zh_chars": 8000},
  "section_length_policy": {
    "default_min": {"zh_chars": 1200},
    "overrides": {
      "introduction": {"zh_chars": 600},
      "regular": {"zh_chars": 1200},
      "conclusion": {"zh_chars": 400},
      "abstract": {"en_words": 250}
    }
  },
  "venue_style_notes": "...",
  "constraint_source": {"name": "default", "url": null},
  "citation_style_confirmed": true,
  "target_figure_count": 0,
  "target_table_count": 0,
  "figure_color_policy": "low_saturation_color",
  "seed_papers": [
    {
      "title": "",
      "authors": [],
      "year": "",
      "journal": "",
      "doi": "",
      "url": "",
      "abstract": ""
    }
  ],
  "assumptions": []
}
```

当 `language == "en"` 时，使用 `en_words` 替代 `zh_chars`。

`citation_style_confirmed` 语义：

- 正常首次生成：调用方传入 `--citation-style`；将 `citation_style` 设为该值，并设置 `citation_style_confirmed: true`。
- 兼容首次生成且无 `--citation-style`：使用上表中的语言感知默认值，并设置 `citation_style_confirmed: false`。
- 带 `--citation-style` 的 revise 模式调用：将 `citation_style` 设为该值，并设置 `citation_style_confirmed: true`。
- 一旦为 `true`，后续 revise 调用中保持 `true`，除非 revise 调用再次显式修改 `citation_style`（此时仍保持 `true`）或显式重置。

## Markdown 视图

从 JSON 渲染 `writing_constraints.md`。它必须简洁、易读，包含：

- topic、subject、language
- citation style
- target paper count
- focus points
- year range
- total length target 和 section length policy
- venue/style notes
- constraint source
- figure color policy
- 使用的 assumptions/defaults
- seed papers 摘要（如有）

Markdown 必须包含 `Constraint source` 行。如果 `constraint_source.url` 非空，渲染为 `[<name>](<url>)`。如果 `constraint_source.name == "default"`，渲染为 `Default (no specific venue requirements)`。对于没有 URL 的内置模板，直接渲染来源名称，例如 `bundled biomedical review template`。

**保留用户提供语言：** 包含用户原始文本的字段（`topic`、`focus_points`、`extra_requirements`、`reference_surveys` 及类似自由文本约束）必须用用户原始措辞和语言渲染。不要把用户提供的英文翻译成中文，也不要把中文翻译成英文。只有系统生成的标题、标签、来源标记和默认值注释遵循解析后的 `language` 字段。

**来源标记（必需）：** `writing_constraints.md` 中每个值都必须带来源标记，让用户能区分事实和默认值。使用这些内联标记，紧跟在值后：

- `（系统默认）` / `(system default)` — 值不是用户提供，而是来自回退默认值表。
- `（搜索参考）` / `(from search)` — 值来自基于浏览器的元数据发现，或可选官方 venue/source discovery；有来源 URL 时在括号中包含。
- `（用户指定）` / `(user-specified)` — 值由用户在本次调用中显式提供。

**设置摘要：** 在 `writing_constraints.md` 末尾追加 `## 关键设置摘要`（zh）或 `## Key Settings Summary`（en），列出高影响字段，仅供用户了解：

| 字段 (zh) / Field (en) | 当前值 / Current value | 来源 / Origin |
|---|---|---|
| 研究主题 / Topic | `<topic>` | 用户指定 / User-specified |
| 引用格式 / Citation style | `<citation_style>` | 用户指定 / User-specified |
| 目标篇数 / Target paper count | `<N>` | 系统默认/用户指定/搜索参考 |
| 正文总字数 / Body length target | `<value>` | 系统默认/用户指定/搜索参考 |
| 期刊/会议目标 / Target venue | `<venue or "未指定/None">` | — |
| 年份范围 / Year range | `<range>` | 系统默认/用户指定 |
| 图片配色 / Figure color policy | `<figure_color_policy>` | 系统默认/用户指定/用户选择 |

不要包含任何“请确认”提示或要求用户确认的语言。该表仅为信息展示；编排器在保存生成文件后立即进入 Stage 2。

## 错误处理

**中止条件** — 在写入任何输出前立即停止，并返回 `ERROR: <reason>`：
- `--output-dir` 缺失或不可写。
- `--topic` 或 `--subject` 为空且无法从上下文推导。
- 提供了 `--revise-from` 路径但文件不存在。
- 完成工具发现和尝试调用后，正常工作流执行期间 browser-use、remote-browser 和等价浏览器 MCP 工具均不可用。
- `writing_constraints.json` 写入失败（文件系统错误）。

**仅警告** — 继续使用默认值，并加入 `assumptions` 条目说明回退原因：
- 可选 venue/style discovery 未返回可执行结果 → 应用回退默认值表；记录来源为 `{"name": "default", "url": null}`。

**错误消息格式：**

```text
ERROR [surveymaster-identify]: <reason>. <remediation hint>.
```

示例：`ERROR [surveymaster-identify]: --revise-from path not found: /work/writing_constraints.json. Run initial generation first.`

浏览器工具示例：
`ERROR [surveymaster-identify]: browser-use or remote-browser is required for SurveyMaster literature discovery but is not available. Enable browser-use/remote-browser tools, then rerun Stage 1.`

## Gate

写入两个文件后，向调用方展示 `writing_constraints.md`。编排器负责将该文件保存/更新给用户，作为信息摘要，然后立即进入 Stage 2。不要要求用户确认写作约束。

除非用户明确要求修改引用格式，否则编排器此时不得要求用户选择引用格式。

引用格式选择发生在首次生成调用之前：当初始请求缺少受支持样式，或指定了不受支持/有歧义的样式时，编排器应使用运行时交互式用户输入机制。在 DSH 中，使用 `ask_user`。

使用 `ask_user`，设置 `allow_other: false`，并把下方完整支持的引用格式列表作为显式选项列出。`options` 数组必须包含对应综述语言下的全部 11 个条目；不要缩短为推荐/常见样式列表。引用格式 gate 只接受这些列表选项标签或规范样式代码。如果返回答案不在支持列表中，要求用户重新从列表中选择；不要映射或接受未支持的自由输入引用格式，并且在用户选择列表内样式前不要进入 Stage 2。

如果 `ask_user` 不可用、超时、没有答案，或返回 fallback/proceed-best-judgment 类消息，将引用格式视为未确认。必须在写入输出前停止，并提示用户必须先选择引用格式。新流程不得自行选择默认引用格式。

**中文综述（zh — 完整支持列表，中文优先顺序）：**
1. `GB/T 7714 顺序编码制（推荐）` -> `gb-t-7714-2015-numeric`
2. `GB/T 7714 著者-出版年制` -> `gb-t-7714-2015-author-date`
3. `IEEE` -> `ieee`
4. `AMA 11th` -> `ama`
5. `APA 7th` -> `apa`
6. `Nature` -> `nature`
7. `ACS 2022` -> `acs`
8. `Cell` -> `cell`
9. `Science` -> `science`
10. `Elsevier with titles` -> `elsevier-with-titles`
11. `Royal Society of Chemistry` -> `rsc`

**英文综述（en — 完整支持列表，国际优先顺序）：**
1. `IEEE (recommended)` -> `ieee`
2. `Nature` -> `nature`
3. `Science` -> `science`
4. `ACS 2022` -> `acs`
5. `APA 7th` -> `apa`
6. `AMA 11th` -> `ama`
7. `Elsevier with titles` -> `elsevier-with-titles`
8. `Cell` -> `cell`
9. `Royal Society of Chemistry` -> `rsc`
10. `GB/T 7714 numeric` -> `gb-t-7714-2015-numeric`
11. `GB/T 7714 author-date` -> `gb-t-7714-2015-author-date`

中文综述使用此 gate 消息：
`开始生成写作约束前，请先选择参考文献引用格式：`

英文综述使用此 gate 消息：
`Before generating writing constraints, please select a citation style:`

只有当 JSON 中 `citation_style_confirmed` 为 `true` 时，Stage 2 才开始。Stage 2 还要求 Stage 1 执行期间 browser-use 或 remote-browser 可用。

**确认 gate：** 始终继续进入 Stage 2，不等待用户确认。无论字段带有 `（系统默认）` / `(system default)` 还是 `（搜索参考）` / `(from search)` 来源，都不要暂停或要求用户确认 `writing_constraints.md`。Stage 1 中的用户交互只允许两类：首次生成调用前的引用格式选择；以及仅当 economics empirical-style template 命中且用户未明确偏好时，用于确定 `figure_color_policy` 的图片配色偏好 gate。

## 修订纪律

此说明支持两类修订。两者都必须遵守 JSON-first 顺序：先修改 `writing_constraints.json`，再重新渲染 `writing_constraints.md`，然后返回，让调用方保存/更新 Markdown，并根据引用格式 gate 状态继续。

**引用格式修订** — 因为用户在恢复流程中选择了缺失样式，或明确要求修改样式，调用方传入 `--citation-style <choice>`：

1. 修改 `writing_constraints.json`：将 `citation_style` 设为新选择，并设置 `citation_style_confirmed: true`。
2. 重新渲染 `writing_constraints.md`。
3. 返回。编排器保存/更新渲染后的 Markdown，并继续推进，不再单独进行写作约束确认。

**其他字段修订** — 调用方传入其他修订字段，但不传 `--citation-style`：

1. 修改 `writing_constraints.json`：应用请求的变更；原样保留 `citation_style` 和 `citation_style_confirmed`。
2. 从更新后的 JSON 重新渲染 `writing_constraints.md`；不要单独修改 Markdown。
3. 返回。编排器保存/更新渲染后的 Markdown，并按最早受影响的工作流阶段继续。除非 `citation_style_confirmed` 为 `false` 或用户明确要求修改引用格式，否则不得重新展示引用格式选择。

永远不要只编辑 `writing_constraints.md`。永远不要在没有调用方显式 `--citation-style` 参数的情况下，把 JSON 的 `citation_style_confirmed` 设为 `true`。
