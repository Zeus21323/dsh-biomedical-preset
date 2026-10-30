---
name: literature-evidence-writing
description: 当用户需要系统检索生物医学文献、整理证据并撰写带准确引用的科研文本时使用。
---

# 文献检索与科学写作

## 检索

把问题拆成对象、干预/暴露、结局和研究设计，补充主题词、旧名、缩写与拼写变体。记录数据库、完整检索式、日期和限制条件，使别人能重复检索。

生物医学或生命科学问题优先使用 PubMed MCP。先用 `search_articles` 获取精简候选；只对入选条目调用 `get_article_metadata`，需要扩展主题时再用 `find_related_articles`。已知引用但缺 PMID 时用 `lookup_article_by_citation`，标识符统一用 `convert_article_ids`。不要把 PubMed 用作纯物理、数学或一般计算机科学的默认数据库。

## 筛选与取证

按题名摘要、全文两阶段执行预先给定的纳排标准，并保留排除理由。去重时同时使用 DOI、PMID、题名和作者年份。提取样本、设计、效应、区间和主要偏倚，不只摘作者结论。

需要 PMC 正文时调用 `get_full_text_article(format="text")`；不得把摘要当作全文证据。需要 PDF 时调用同一工具的 `format="pdf"`，它只返回经 PMC Article Dataset 核验的官方公开地址，不负责下载或入库。没有 `pdf_url` 时保留元数据记录，不改用出版商、聚合站或绕过权限的地址。

## SpeedClaw 文献库闭环

用户明确选定论文并要求入库后，按原子步骤执行：

1. 用 `literature_check_duplicates` 按 DOI 和题名查重；已有记录则复用 `paper_id`。
2. 新记录用 `literature_import_candidate` 写入 PubMed 元数据，并保留 PMID、PMCID 在 `source_ref` 中。
3. 用户同时要求 PDF 时，用 `get_full_text_article(format="pdf")` 获得 `pdf_url`，再用裸 `exec` 下载到本地文件。
4. 调用 `literature_upload_pdf`，把该本地 PDF 复制进托管文献库、绑定论文并进入全文准备队列。

MCP 是只读来源层；`exec` 只负责本地下载；文献库写入只由 `literature_*` 工具完成。不要增加 PMC 专用下载工具，也不要把仅返回的候选地址描述为已经下载或入库。

## 写作

每个关键事实紧邻真正支持它的文献；优先引用原始研究，综述用于背景。预印本、会议摘要和数据库记录要标明性质。多篇结果冲突时说明人群、测量或设计差异，不用多数票掩盖冲突。

不得编造文献、DOI、数字或引语。交付正文时同时给检索截止日期、筛选记录和证据表。

## 多库检索与导出

生物医学主题优先组合 PubMed、Crossref 和适用的预印本来源；跨学科问题可补充 Semantic Scholar。为每个数据库保留实际执行的查询式，不把一个数据库的语法原样发送到另一个数据库。API 限速时采用有上限的退避；连续失败后停止并说明缺失来源。

结果以 DOI、PMID、规范化题名和作者年份联合去重，保留预印本与正式发表版本的关联。按用户用途输出 Markdown、CSV、JSON、BibTeX 或 RIS；每条记录应保留来源库、稳定标识、文献类型和检索日期。
