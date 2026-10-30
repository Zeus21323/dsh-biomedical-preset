---
name: standardization
description: 标准化浏览器研究流程的强制入口路由 skill。当用户要求浏览器研究、来源核验、文献检索、多源综合、生物医学或医学研究、生命科学研究、经济学研究、金融学研究、工程类研究、计算机科学研究、软件工程研究、中文学术文献、知网检索、PubMed 检索、Google Scholar 检索、arXiv 检索、IEEE/ACM 检索或网站调查时使用。加载本 skill 时必须先判断用户问题属于生医/生命科学领域、经济学/金融学领域，还是工程/计算机科学领域，再严格读取并遵守 references1、references2 或 references3 下对应的 SKILL.md。
---

# Standardization 入口路由

使用本文件作为入口。不要把它当作完整研究流程。

在搜索、浏览、下载或回答之前，必须先判断用户问题属于生物医学/生命科学领域、经济学/金融学领域，还是工程/计算机科学领域。然后读取匹配的 reference skill，并严格遵守其中规则。读取 reference skill 是强制步骤，不是可选步骤。

## 路由规则

1. 生物医学、医学、临床、药物、遗传学、生物学、公共卫生或生命科学相关问题：
   - 读取 `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references1/SKILL.md`。
   - 严格遵循其中 PubMed 优先流程、文献下载规则、来源优先级规则和 browser_use 约束。
2. 经济学、金融学、政治经济学、产业经济学、宏观经济学、微观经济学、计量经济学、发展经济学、劳动经济学、财政学、国际贸易、中国经济政策或中文经济学文献相关问题：
   - 读取 `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references2/SKILL.md`。
   - 严格遵循其中知网优先流程、Google Scholar/arXiv 高优先级补充检索规则、中国人民大学经济学 A/B 期刊优先规则，以及高引用/顶刊筛选规则。
3. 工程类、计算机科学、软件工程、人工智能、机器学习、数据工程、网络安全、计算机网络、系统、数据库、程序设计语言、人机交互、机器人、控制、电子、通信或应用工程技术相关问题：
   - 读取 `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references3/SKILL.md`。
   - 严格遵循其中 IEEE/ACM/Google Scholar/arXiv/DBLP 检索流程、会议/期刊优先级规则、标准/规范/源码核验规则，以及可复现性筛选规则。
4. 同时涉及生物医学、经济学和工程类中多个领域的问题：
   - 读取所有相关 reference skill。
   - 对每个子问题分别应用来源优先级：生物医学论断先 PubMed；中文经济学论断先知网；工程类论断优先 IEEE/ACM/Google Scholar/arXiv/DBLP，并结合标准/规范和源码仓库核验。
5. 其他浏览器研究问题：
   - 使用 `browser_use` 或 remote-browser skill 的通用浏览器生命周期规则。
   - 优先使用权威一手来源，进行多源核验，输出简洁综合结论和可追溯来源元数据。

## 通用浏览器规则

浏览器工作前，先读取并遵循 `browser_use` 或 remote-browser skill 的相关规则。

如果可用 `mcp_remote_browser_*` 工具：

1. 先列出设备。
2. 创建任务专属 session。
3. 打开重复标签页前检查已有标签页。
4. 优先使用结构化元素 ref，不优先使用 selector 或坐标。
5. 敏感操作前请求用户批准。
6. 浏览器工作结束前 finalize tabs。

## 输出标准

始终说明本次使用了哪个路由：

- `references1`：生物医学 / PubMed 优先路由。
- `references2`：经济学 / 知网优先路由。
- `references3`：工程 / 计算机科学路由。
- `mixed`：使用两个或多个 reference skill 的混合路由。
- `general`：其他研究路由。

附来源链接和足够元数据，保证答案可追溯。如果没有使用预期的优先来源，说明原因。
