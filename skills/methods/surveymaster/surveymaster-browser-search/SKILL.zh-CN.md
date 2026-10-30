---
name: surveymaster-browser-search
version: 0.2.0
description: SurveyMaster Stage 2 browser-use/remote-browser 候选发现的子说明路由。由 surveymaster-literature-library 在浏览器检索前读取。按生物医学/生命科学、经济/社科、工程/计算机领域路由到对应浏览器流程，并要求只输出 browser 候选 JSON。
---

# SurveyMaster 浏览器检索路由

在 Stage 2 候选发现期间使用本子说明。它只定义 browser-use/remote-browser
检索路由；入库、校验、元数据补全和覆盖门禁仍由
`surveymaster-literature-library` 负责。

## 硬契约

- 候选发现只能使用 browser-use/remote-browser。不要用 `PaperSurveyToFile`、
  `PaperSearch`、academic search API、通用 WebSearch、DOI/title lookup API
  OpenAlex/Crossref/Semantic Scholar/CORE/Lens API 端点或其他非浏览器检索
  工具开始、继续、恢复或补充候选发现。通过 browser-use/remote-browser 打开
  API 端点，也不算有效的浏览器发现分支。OpenAlex/Crossref 只能在合并后的
  browser candidates 已经写入后，由下游元数据解析器使用。
- 不要让用户在 browser-use 和 academic-search 之间做选择。不要把
  academic-search 或任何非浏览器检索工具标为推荐。
- 将 browser-use/remote-browser 视为浏览器自动化能力类别，而不是字面工具名要求。
  只要运行时暴露的工具能打开真实网页、导航/搜索、读取页面内容并写出 JSON 候选，
  就属于等价浏览器工具，包括 deferred MCP 工具如 `mcp_remote_browser_*`。
- 如果仅从规划上下文、当前工具列表或缺少快捷入口看起来 browser-use/remote-browser
  不可用，先执行运行时的工具发现/find_tools，搜索 `browser`、`remote-browser`、
  `remote browser`、`browser automation`、`MCP remote browser` 等关键词。若发现
  `mcp_remote_browser_*` 等匹配工具，应激活并使用。只有完成发现后实际调用仍表明
  浏览器服务未启动时，才判定不可用；此时停止并要求用户启用 browser-use/remote-browser。
- 不要调用 `ask_user`、`request_user_input` 或任何选择 UI 来提供 academic-search、
  PaperSearch、PaperSurveyToFile、WebSearch、DOI/title lookup、API 端点检索或其他非浏览器选项。
  如果必须弹 UI，只能询问用户启用 browser-use/remote-browser 或停止 Stage 2；
  不得包含任何“推荐”的 fallback。
- 每个分支必须把 JSON 数组写入
  `$WORK/.cache/scratch/browser_candidates.<branch>.json`。所有分支完成后，
  编排器再合并为 `$WORK/.cache/scratch/browser_candidates.json`。

## 路由

浏览器检索前，根据 `subject`、`topic`、`focus_points` 和种子论文内容判断领域。
然后读取匹配的 reference 文件：

1. 生物医学、医学、临床、药学、遗传学、生物学、公共卫生或生命科学主题：
   - 读取 `references1/SKILL.md`。
   - 优先使用 PubMed 和 Google Scholar 浏览器分支。
2. 经济学、金融、管理、政策、社科经济、中文学术文献或适合知网的主题：
   - 读取 `references2/SKILL.md`。
   - 优先使用 CNKI 和 Google Scholar 浏览器分支。
3. 工程、计算机、软件工程、AI/ML、电子、自动化、材料、通信、机器人或应用工程主题：
   - 读取 `references3/SKILL.md`。
   - 根据需要优先使用 arXiv、Google Scholar、IEEE Xplore、ACM Digital
     Library 和 DBLP 浏览器分支。
4. 混合或交叉主题：
   - 读取所有相关 reference 文件。
   - 对匹配的 focus points 应用对应路线，但所有输出都保持同一候选 JSON 形状。
5. 领域不明确：
   - 使用 Google Scholar 加最接近的专业路线。如果第一轮分支偏题，缩窄 query 后
     继续 browser-use/remote-browser 重试，不要切换到非浏览器检索。

## 通用浏览器流程

- 每个 browser-use/remote-browser 分支都给出具体任务：打开选定站点，检索一个
  关键词短语，只检查排序靠前的结果页，必要时打开最相关的详情页，抽取候选字段，
  并把 JSON 数组保存到分支文件。任务中写明准确输出路径，例如：

  ```text
  $WORK/.cache/scratch/browser_candidates.pubmed_query1.json
  ```

- 如果浏览器工具提供这些动作，页面检查按这个顺序执行：先调用
  `interactive_elements`；如果没有看到标题/结果链接，再调用带字符上限的
  `snapshot` 或 `page_info`；在返回内容里搜索 `Abstract`、`DOI`、`PMID`、
  `arXiv`、`Proceedings`、`Conference`、`Journal`、`PDF`、`篇名`、`作者`、
  `来源` 和用户关键词。
- 忽略导航栏、页脚、作者主页、期刊链接、推荐组件、指标组件、服务链接和无关控件，
  除非它们是打开论文详情页所必需。
- 只检查排序靠前的结果页。每个 query 提取前 10-20 条候选；不要遍历全部搜索结果。
- 保存分支文件前，对明显重复的结果先去重。重复信号包括标题、DOI、PMID、arXiv ID、
  DBLP key、URL 和 author/year。
- 如果站点阻断浏览、出现 CAPTCHA/异常流量、要求登录或没有可用结果，在 Stage 2
  报告记录该分支失败，并继续用 browser-use/remote-browser 调整 query/site 后重试。
  不要切换到 academic-search、PaperSearch、PaperSurveyToFile、WebSearch、
  DOI/title lookup、API 端点检索或其他非浏览器检索工具。

## 候选 JSON 形状

每个 browser 分支必须保存如下 JSON 数组。`abstract_hint` 只能来自页面明确的
Abstract/摘要区域；不要把搜索结果 snippet 冒充摘要。

```json
[
  {
    "title": "Paper title",
    "doi": "10.xxxx/yyyy",
    "url": "https://example.com/paper",
    "year_hint": "2024",
    "venue_hint": "Journal or Conference Name",
    "authors_text": "Author A, Author B",
    "abstract_hint": "Short abstract if available",
    "source": "browser-use"
  }
]
```
