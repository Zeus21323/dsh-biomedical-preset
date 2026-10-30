---
name: surveymaster-browser-search-economics
version: 0.2.0
description: SurveyMaster Stage 2 的经济学、金融、管理和知网相关 browser-use 流程。优先 CNKI 加 Google Scholar 浏览器分支，并输出 SurveyMaster 候选 JSON。
---

# 经济学 / 知网浏览器检索

用于经济学、金融、管理、政策、社科经济、中文学术文献和适合知网的主题。

## 来源优先级

1. CNKI 是中文经济学、中国政策和社科经济文献的主浏览器来源。
2. Google Scholar 可作为并行浏览器发现分支，用于国际版本、引用链、高引用文献和真实来源页发现。
3. arXiv 不是默认经济学分支。只有主题明显是技术性数量方法，或用户主题本身指定 arXiv/预印本时才使用。

不要使用 `academic_search_cn`、academic-search、PaperSearch、PaperSurveyToFile、
WebSearch、DOI/title lookup 或其他非浏览器检索工具。
不要把 OpenAlex、Crossref、Semantic Scholar、CORE、Lens 或其他元数据/API
端点作为经济学候选发现分支，即使这些端点是通过 browser-use/remote-browser
打开的也不可以。OpenAlex/Crossref 只能在
`$WORK/.cache/scratch/browser_candidates.json` 已经生成之后，由
`discover_and_resolve_papers.py` 做元数据补全时使用。

## Query 建议

- CNKI query 应组合中文/英文主题词、政策/事件名、作者名、理论名、地区名和时间范围。
- 相关时加入实证方法词：`双重差分`、`断点回归`、`工具变量`、`面板数据`、`准自然实验`、`机制检验`、`异质性分析`。
- 相关时加入数据集/来源名：`中国家庭追踪调查`、`工业企业数据库`、`上市公司`、`海关数据库`、`城市面板`、`县域数据`。
- 国际脉络用英文关键词、方法名、数据集名和作者名跑 Google Scholar 分支。

## CNKI 分支

- 每个分支用一个聚焦 query 检索知网。
- 如果知网搜索框不响应 Enter，不要反复按 Enter 或在同一输入框重输。改为直接导航到知网结果页 URL 或高级检索页。
- 检查排序靠前的结果，只打开最相关详情页。
- 抽取 `篇名`、`作者`、`来源`、年份/日期、可见 DOI、明确摘要/abstract、可见引用/下载指标和知网详情页 URL。
- 如果知网显示用户未登录、访问不可用，或阅读论文/完整元数据需要登录，立即停止 CNKI 分支。提示用户：阅读知网文献通常需要登录，建议优先使用机构账号、校园网或 VPN；然后等待用户确认已经登录或开启访问权限后再继续。不要在后台继续，不要用 Google Scholar 顶替被阻断的 CNKI 分支，也不要切换到 academic-search、PaperSearch、PaperSurveyToFile、WebSearch、DOI/title lookup 或 API 工具。
- 用户确认知网访问已准备好后，继续用 browser-use/remote-browser 恢复同一个 CNKI 分支并抽取候选。

## Google Scholar 分支

- Scholar 只用于发现信号：标题、作者、年份、venue hint、cited-by、versions 链接和真实来源页链接。
- 不要把 Scholar snippet 当作 `abstract_hint`。
- 通过浏览器打开有价值的真实宿主页面，例如出版社、作者主页、机构仓储、NBER、SSRN、RePEc、CEPR、IZA 或期刊页面。
- 如果 Scholar 出现 CAPTCHA 或异常流量页，记录浏览器状态失败，并用调整后的浏览器 query 或其他可访问来源页重试；不要切换到非浏览器检索。
- 摘要补全时，优先打开 Scholar 发现的真实来源页，例如出版社/期刊页面、NBER、SSRN、RePEc、CEPR、IZA、作者主页或机构仓储。不要把 OpenAlex/Crossref API 返回作为主要摘要来源，也不要把 null/空摘要字段计为一次成功的摘要补全。

## 输出

每个分支写入 `$WORK/.cache/scratch/browser_candidates.<branch>.json`，使用
`surveymaster-browser-search` 的通用候选 JSON 形状。
