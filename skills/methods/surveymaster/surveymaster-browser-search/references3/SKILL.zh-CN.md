---
name: surveymaster-browser-search-engineering-cs
version: 0.2.0
description: SurveyMaster Stage 2 的工程、计算机和软件工程 browser-use 流程。优先 arXiv、Google Scholar、IEEE/ACM 和 DBLP 浏览器分支，并输出 SurveyMaster 候选 JSON。
---

# 工程 / 计算机浏览器检索

用于工程、计算机、软件工程、AI/ML、数据工程、网络安全、网络、系统、数据库、程序语言、HCI、机器人、控制、电子、通信、材料和应用工程主题。

## 来源优先级

1. arXiv 是 AI/ML、系统、安全、机器人、信号处理、软件工程和快速发展技术主题的一轮发现浏览器来源。
2. Google Scholar 可作为并行浏览器发现分支，用于引用链、高影响工作、作者版本和真实来源页发现。
3. IEEE Xplore 和 ACM Digital Library 是相关时的同行评审工程/CS 出版页优先浏览器来源。
4. DBLP 优先用于 CS 题录核验、venue 名称、作者消歧和发表年份。

不要使用 academic-search、PaperSearch、PaperSurveyToFile、WebSearch、DOI/title
lookup 或其他非浏览器检索工具。

## Query 建议

- 概念检索：组合方法、任务、系统、数据集、benchmark 和应用场景。
- Venue 检索：当 venue 质量重要时加入会议、期刊或站点名，例如 `site:dl.acm.org ICSE code review automation` 或 `site:ieeexplore.ieee.org federated learning wireless communication`。
- 可复现性检索：相关时加入 `code`、`GitHub`、`artifact evaluation`、`dataset`、`benchmark`、`leaderboard`、`replication` 或 `reproduction`。
- 标准检索：当主题涉及标准/规范时，加入标准编号、RFC 编号、协议名、API 名或工作组名。

## arXiv 分支

- 使用聚焦技术短语检索。
- 抽取标题、作者、年份、arXiv ID、摘要、分类、URL 和可见 PDF URL。
- 如果看到同行评审版本，候选 URL 优先使用同行评审来源页；arXiv 只在有用时作为辅助线索。
- 如果一两次 arXiv query 明显偏题，停止该分支并重试其他浏览器来源；不要切换到非浏览器检索。

## Google Scholar 分支

- Scholar 用于引用链、高引用论文、作者版本和真实来源页发现。
- 不要把 Scholar snippet 当作 `abstract_hint`。
- 打开有价值的真实宿主页面，例如出版社、OpenReview、会议官网、作者主页、机构仓储或项目页。
- 如果 Scholar 出现 CAPTCHA 或异常流量页，记录浏览器状态失败，并用调整后的浏览器 query 或其他来源页重试。

## IEEE / ACM / DBLP 分支

- 用 IEEE Xplore 或 ACM Digital Library 查同行评审出版页。
- 用 DBLP 核验标题、作者、venue、年份和发表版本。
- AI/ML venue 核验相关时，使用 NeurIPS、ICML、ICLR、OpenReview、ACL Anthology、CVF 或其他官方 proceedings 页面。
- 抽取标题、作者、venue、年份、DOI、明确摘要、来源 URL、可见 code/data 链接和相关 benchmark/dataset 名称。

## 输出

每个分支写入 `$WORK/.cache/scratch/browser_candidates.<branch>.json`，使用
`surveymaster-browser-search` 的通用候选 JSON 形状。
