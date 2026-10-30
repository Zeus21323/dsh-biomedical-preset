---
name: surveymaster-browser-search-biomedical
version: 0.2.0
description: SurveyMaster Stage 2 的生物医学和生命科学 browser-use 流程。优先 PubMed 加 Google Scholar 浏览器分支，并输出 SurveyMaster 候选 JSON。
---

# 生物医学 / 生命科学浏览器检索

用于生物医学、医学、临床、药学、遗传学、生物学、公共卫生和生命科学主题。

## 来源优先级

1. PubMed 是生物医学元数据、摘要、PMID/DOI、研究类型和医学术语的主浏览器来源。PubMed 详情页已经给出 title/authors/year/journal/DOI/abstract 时，应把这些字段完整写入候选 JSON；后续元数据 API 只做补全，不得成为阻塞点。
2. PMC 和出版社/期刊详情页是 PubMed 之后的优先真实来源页，尤其用于读取明确摘要、article number、volume/issue/pages 和 DOI。
3. Google Scholar 可作为并行浏览器发现分支，用于引用链、高引用论文、全文/来源页发现、预印本和跨学科版本。
4. Scholar 不是最终元数据来源；对有价值结果，必须打开 PubMed、PMC、出版社/期刊页或其他真实来源页后再抽取元数据。
5. OpenAlex/Crossref 不属于浏览器发现来源，只能在候选 JSON 已生成后由本地解析脚本做非阻塞补全；OpenAlex 限流不得导致 Stage 2 停止。

不要使用 academic-search、PaperSearch、PaperSurveyToFile、WebSearch、
DOI/title lookup 或其他非浏览器检索工具。

## Query 建议

- 组合科学术语、同义词、缩写、物种、基因/蛋白、疾病、干预/暴露、结局和研究类型词。
- 主题匹配时，优先加入 review、systematic review、meta-analysis、clinical guideline、randomized trial、cohort、case-control 等词。
- 只有时效性重要时，才使用日期词或过滤器。

## PubMed 分支

- 从 `https://pubmed.ncbi.nlm.nih.gov/` 开始。
- 每个分支检索一个聚焦 query。
- 检查排序靠前的结果，只打开最相关的详情页。
- 抽取标题、作者、期刊、年份/日期、PMID、DOI、URL 和明确摘要。
- 忽略导航栏、作者主页、期刊链接、相似文章组件、指标、引用工具、分享链接和页脚，除非它们是打开详情或完整摘要所必需。

## Google Scholar 分支

- Scholar 只作为浏览器发现分支，不作为摘要来源。
- 抽取标题、作者、年份、venue hint、可见 cited-by、versions 链接和真实来源页链接。
- 不要把 Scholar snippet 当作 `abstract_hint`。
- 对有价值结果，打开真实宿主页面并从该页面抽取元数据。
- 如果 Scholar 出现 CAPTCHA 或异常流量页，记录浏览器状态失败，并用 PubMed 或其他可访问来源页重试；不要切换到非浏览器检索。

## 输出

每个分支写入 `$WORK/.cache/scratch/browser_candidates.<branch>.json`，使用
`surveymaster-browser-search` 的通用候选 JSON 形状。
