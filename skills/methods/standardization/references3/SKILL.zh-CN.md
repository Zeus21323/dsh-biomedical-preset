---
name: engineering-cs-priority
description: 规范使用 browser_use 或 remote-browser 工具进行工程类、计算机科学和软件工程文献检索和研究的流程。当用户询问计算机科学、软件工程、人工智能、机器学习、数据工程、网络安全、计算机网络、分布式系统、数据库、程序设计语言、人机交互、机器人、控制、电子、通信或应用工程技术时使用。优先用 arXiv 做第一轮发现；相关时以 Google Scholar 以及 NeurIPS、ICML、ICLR 会议/官网/OpenReview 页面作为辅助；再用 IEEE Xplore、ACM Digital Library、DBLP、官方标准/规范和源码仓库核验会议/期刊元数据、可复现性、benchmark、数据集和实现证据。
---

# 工程与计算机科学优先检索

使用本 skill 来规范工程类和计算机科学文献研究任务。本 skill 定义来源优先级、会议/期刊筛选、标准/源码核验和输出要求；具体浏览器操作规则来自 `browser_use` 或 remote-browser skill。

## 必须配合使用的 Skill

使用浏览器工具前，先读取并遵循：

`browser_use`

然后再满足本 skill 的相关约束。

每个任务中本 skill 文件读一次后就要记住其中的路由和检索规则。不要反复重新打开或重读这个 SKILL.md，除非用户要求查看或修改该文件、上下文丢失后需要恢复，或有明确理由核验文件已经变化。

如果可用 `mcp_remote_browser_*` 工具，遵循其生命周期规则：先列出设备，创建任务专属 session，打开重复标签页前检查已有标签页，优先使用结构化元素 ref，对敏感操作请求用户批准，并在浏览器工作结束前 finalize tabs。

## 研究流程

1. 先判断用户请求是否属于工程或计算机科学相关问题：
   - 计算机科学和软件工程：人工智能、机器学习、深度学习、自然语言处理、计算机视觉、软件工程、程序设计语言、编译器、数据库、数据挖掘、分布式系统、操作系统、云计算、计算机网络、网络安全、隐私、人机交互、可视化、机器人、嵌入式系统和系统性能。
   - 更广义工程：电子工程、通信、控制、自动化、信号处理、机械工程、土木工程、材料工程、制造、能源系统和应用工程技术。
   - 如果不是工程或计算机科学相关问题，使用主 standardization skill 的通用研究流程。
2. 对工程/计算机科学请求，优先检索 arXiv：
   - 先用 arXiv 做第一轮发现，尤其适合 AI/ML、系统、安全、机器人、信号处理、软件工程和快速发展的工程技术主题。
   - arXiv 初筛后，用 Google Scholar 作为辅助来源查找引用链、高引用论文、作者版本和全文入口。
   - 对 AI/ML 主题，相关时用 NeurIPS、ICML、ICLR proceedings/官网/OpenReview 页面作为高优先级辅助来源，核验会议版本和录用信息。
   - 需要核验同行评审会议/期刊版本时，再使用 IEEE Xplore 和 ACM Digital Library。
   - 使用 DBLP 核验计算机科学文献元数据、会议/期刊名、作者消歧和发表信息。
   - 当 Semantic Scholar、OpenAlex、Crossref、出版社页面、作者主页或机构仓储能改善元数据或访问时，可作为补充来源。
3. 优先考虑会议/期刊质量和相关性：
   - 计算机科学中，相关时优先看顶级或领域合适的同行评审会议/期刊：NeurIPS、ICML、ICLR、ACL、EMNLP、CVPR、ICCV、ECCV、SIGKDD、WWW/The Web Conference、SIGIR、CHI、UIST、ICSE、FSE、ASE、PLDI、POPL、OOPSLA、SIGMOD、VLDB、ICDE、SOSP、OSDI、NSDI、SIGCOMM、USENIX Security、IEEE S&P、ACM CCS、NDSS、SIGGRAPH、ICRA、IROS、RSS，以及 IEEE/ACM Transactions 和 ACM TO* 等强领域期刊。
   - 更广义工程中，优先看 IEEE、ACM、ASME、ASCE、Elsevier、Springer、Wiley、Nature/Science 系列，以及领域合适的学会期刊或会议。
   - 不要只按会议/期刊名排序。综合考虑直接相关性、时效性、方法质量、benchmark 可比性、数据集适配性和可复现性。
4. 核验标准、规范和官方技术来源：
   - 对协议、API、安全标准、文件格式、benchmark 或工程规范，优先看官方标准组织和维护方：IEEE、IETF RFC、ISO/IEC、W3C、WHATWG、NIST、ETSI、3GPP、Khronos、CNCF、Linux Foundation、官方语言/运行时文档和项目治理页面。
   - 关于标准或 API 的 claim，必须尽量用官方规范或文档交叉核验，不要只依赖论文或博客。
   - 相关时记录版本号、发布日期/更新时间、标准编号、RFC 编号、仓库 tag/release 和废弃状态。
5. 检查可复现性和实现证据：
   - 优先关注发布代码、数据集、model card、benchmark 脚本、artifact evaluation badge、复现实验包或实验设置说明清晰的论文。
   - 只有在相关时核验代码仓库。记录仓库 URL、owner、license（若可见）、最新 release/tag、必要时记录 commit/date、stars 只作为弱信号，并判断仓库是否确实对应论文。
   - 对 benchmark claim，核验数据集名称/版本、指标定义、评估划分、baseline 可比性，以及数字来自原论文、leaderboard 还是独立复现。
6. 谨慎使用 arXiv：
   - arXiv 是工程和计算机科学问题的第一轮发现来源，尤其适合 AI/ML 和系统方向，但不能自动当作同行评审证据。
   - 先使用一到两次聚焦的 arXiv 检索；如果结果稀少或偏题，停止重试，改用 Google Scholar、NeurIPS、ICML、ICLR、IEEE、ACM、DBLP、出版社页面或官方仓库。
   - 如果 arXiv 论文已有会议/期刊版本，应优先引用同行评审版本；arXiv 可作为全文入口补充说明。
7. 下载高相关文献前先询问用户：
   - 为了提高响应速度，第一轮文献检索时不要直接下载论文，除非用户一开始就明确要求下载。
   - 先识别并总结最相关的文献，然后询问用户是否需要下载全文。
   - 只有在用户允许且访问权限允许时，才下载完整论文。每个下载文件都要保存到工作区，并通过平台的用户可见文件/产物机制把同一文件提供到对话区。
   - 如果因为访问限制、登录、付费墙、缺少 PDF 链接或技术问题无法下载，说明具体原因，并保留文献元数据。
   - 当用户明确要求下载文献时，两个位置都必须完成：工作区文件和对话区文件/产物。不要把浏览器标签页、来源 URL 或只有元数据的引用当作已完成下载。
8. 进行多源核验：
   - 当标题、作者、会议/期刊、年份、DOI/arXiv ID、引用量、benchmark 数字、代码可用性、标准版本或实现状态影响答案时，必须核验。
   - 重要信息可用 IEEE/ACM/出版社页面、DBLP、Google Scholar、arXiv、官方标准、官方文档、源码仓库和 benchmark/leaderboard 页面交叉检查。
   - 区分来源直接支持的事实和自己的推断。
9. 综合归纳，不要大段粘贴：
   - 不要直接倾倒完整摘要、搜索结果页、README 或 benchmark 表格。
   - 用用户请求的语言总结文献。
   - 尽可能附上来源链接和标识符。

## 检索建议

使用适合工程/计算机科学的检索策略：

- 概念检索：组合方法、任务、系统、数据集、benchmark 和应用场景，例如 `retrieval augmented generation software engineering benchmark`、`distributed consensus Byzantine fault tolerance survey` 或 `graph neural network traffic prediction IEEE`。
- 会议/期刊检索：用户要求顶级研究时加入会议或期刊名，例如 `site:dl.acm.org ICSE code review automation` 或 `site:ieeexplore.ieee.org federated learning wireless communication`。
- 标准检索：加入标准编号、RFC 编号、协议名、API 名或工作组名，例如 `RFC QUIC congestion control`、`IEEE 802.11be standard` 或 `W3C WebGPU specification`。
- 可复现性检索：加入 `code`、`GitHub`、`artifact evaluation`、`dataset`、`benchmark`、`leaderboard`、`replication` 或 `reproduction`。
- arXiv 检索：优先用聚焦技术词检索 arXiv；一次或两次失败/偏题后停止。
- AI/ML 会议检索：用 Google Scholar 以及 NeurIPS、ICML、ICLR proceedings/官网/OpenReview 页面作为辅助，核验会议版本、录用信息、作者版本和引用脉络。
- DBLP 检索：使用精确作者名、论文标题、会议缩写和年份范围核验文献元数据。

## 并行检索建议

使用并行检索来减少等待时间并提高覆盖面，但要保持来源优先级清楚：

- arXiv + Google Scholar：尽可能并行检索，arXiv 作为第一轮发现来源，Google Scholar 作为引用链和全文发现辅助来源。
- arXiv + NeurIPS/ICML/ICLR：AI/ML 主题需要核验会议版本时并行使用。
- IEEE/ACM + Google Scholar：在 arXiv 初筛后或并行使用，用于核验同行评审工程/计算机科学发表页面和引用脉络。
- DBLP + 出版社页面：用于核验计算机科学文献元数据、会议/期刊、作者身份和发表年份。
- 标准/文档 + 文献：当问题涉及协议、API、库、工程规范或实现建议时并行使用。
- 总结前按标题、DOI、arXiv ID、DBLP key、作者/年份、仓库和会议/期刊去重。
- 如果来源结论冲突，要说明冲突，并按 claim 类型选择最权威来源：标准看官方规范，文献元数据看出版社/DBLP，评测数字看 benchmark 页面或原论文，实现状态看仓库。

## 页面处理效率规则

工程和计算机科学页面通常包含大量无关内容，例如导航栏、引用组件、作者主页链接、推荐面板、登录提示、指标面板、README 徽章、issue 列表和自动生成的文档侧栏。不要在这些内容上消耗过多注意力。

提取有用结果时按以下顺序处理：

1. 先调用 `interactive_elements`。
2. 如果 `interactive_elements` 中没有论文标题链接或仓库文件，不要立刻完整分析整个 snapshot。
3. 调用 `snapshot` 或 `page_info`，但如果工具支持，要限制 `max_chars`。
4. 在返回内容里搜索用户关键词、`Abstract`、`DOI`、`arXiv`、`Proceedings`、`Conference`、`Journal`、`PDF`、`Code`、`Dataset`、`Artifacts`、`Benchmark`、`Release` 和 `License`。
5. 认真阅读有用的摘要、方法概述、benchmark 表和仓库元数据。
6. 忽略作者链接、指标链接、推荐链接、服务链接、导航链接、自动生成 API 侧栏和页脚链接，除非它们对当前任务确实必要。
7. 必要时只打开最相关的 1-5 篇论文、规范或仓库。

## 输出标准

提供简洁的研究答案，包含：

- 先给直接答案或技术结论。
- 必要时给一个简短证据表：标题、作者、会议/期刊、年份、来源类型、DOI/arXiv ID、代码/数据可用性、benchmark/数据集和相关性。
- 明确说明使用了工程/计算机科学路由。
- 说明使用了哪些检索，例如 arXiv 优先检索、Google Scholar 辅助检索、NeurIPS/ICML/ICLR 会议核验、IEEE/ACM、DBLP、标准/文档或仓库核验，以及为什么使用。
- 说明 arXiv 结果是预印本还是已有同行评审版本。
- 说明检查了哪些顶级或领域合适会议/期刊，以及会议/期刊元数据是否已核验。
- 输出最贴近用户问题、最相关且质量最高的一组文献。
- 说明重要限制：访问限制、代码未核验、benchmark 细节缺失、引用量可能滞后、标准版本不确定，或不同来源之间存在冲突。
- 最后询问用户是否需要下载最相关文献全文，除非用户已经明确要求下载。
