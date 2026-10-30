---
name: surveymaster-literature-library
version: 0.2.0
description: 执行文献库操作，包括 insert/from-paper-results、静默去重、validate、stats、query、紧凑写作上下文生成、BibTeX 导出、过滤和安全删除。
argument-hint: "insert|from-paper-results|validate|stats|query|build-write-context|export-bib|filter-year-range|delete-keys [args]"
---

## 阶段契约

角色：Stage 2 文献研究与文献库维护；当由 `surveymaster-finalize` 加载时，也负责最终化阶段的 BibTeX 元数据解析/导出。

加载者：SurveyMaster 编排器在 Stage 1 写入并确认 `writing_constraints.json` 后加载；Stage 5 在 BibTeX 导出或元数据修复前立即加载。

必需输入：
- Stage 2 使用 `$WORK/writing_constraints.json`。在自定义 agent 中，如果 `$WORK` 未显式传入，但存在用户会话工作区（例如 `~/.dsh/sessions/<session_id>/workspace`），则将该工作区作为 `$WORK`，并从 `$WORK/writing_constraints.json` 读取 Stage 1 结果。
- 由编排器准备的文献搜索或查找结果。
- 当更新、验证、查询或导出现有文献库时，使用 `$WORK/papers.json`。

输出：
- `$WORK/papers.json`，作为规范文献库。
- 重复项、验证、统计、查询和 BibTeX 报告，写入 `$CACHE` 或 `$WORK`。
- Stage 5 最终 BibTeX 导出时生成 `$WORK/references.bib`。

完成条件：
- Stage 2：`papers.json` 存在、通过验证，并已报告覆盖情况。
- Stage 5：`references.bib` 存在，阻塞性元数据错误或可解析警告已处理。

可以加载其他技能：
- 否。

## 文件写入策略

所有文件写入都使用 `Write`（创建/覆盖）或 `Edit`（补丁）。禁止使用 shell heredoc，因为它们会破坏 LaTeX 和 JSON 中的反斜杠。

## 功能

将 `$WORK/papers.json` 作为唯一事实源进行管理：写入/更新、验证、查询、导出和清理。

整个综述流程中文献库都是可变的。初始搜索、大纲规划和章节写作都必须读写同一个 `$WORK/papers.json`，而不是只把论文集合保存在 prompt 中。

所有来自 PubMed、Crossref、OpenAlex、出版社、浏览器、用户上传或人工记录的元数据，入库后都必须是纯文本。插入前必须清除 title、venue、abstract 和 author 字段中的 JATS/HTML/XML 标记，例如 `<scp>`、`<sup>`、`<sub>` 和 `<i>`。BibTeX 导出前必须再次执行同样清洗作为兜底。

## 输入

- 文献库路径（必需；规范路径为 `$WORK/papers.json`）
- 子命令参数（例如 keys、年份范围、bib 输出路径）
- 可选扫描路径（删除前用于引用安全检查）

## 输出与边界

- 更新后的文献库文件、查询输出、BibTeX 文件或检查报告
- 本地脚本不执行在线检索。编排器可以先使用外部搜索或查找工具，再调用此技能插入已解析的结构化记录。

规范脚本：
- `scripts/bibliography_library.py` — 管理 `$WORK/papers.json`，负责 insert/from-paper-results/validate/stats/query/export。
- `scripts/discover_and_resolve_papers.py` — 读取 agent/browser-use 已生成的候选论文 JSON，使用候选中已抽取的 PubMed/PMC/出版社元数据作为可接受事实源，并用 Crossref、OpenAlex 和 arXiv API 做非阻塞补全，然后调用 `bibliography_library.py insert` 合并进 `$WORK/papers.json`。OpenAlex 限流时脚本会在本轮跳过 OpenAlex 并继续处理候选；此脚本不调用 browser-use，browser-use 插件必须由 agent/编排器调用。

脚本调用中的 `<skill_dir>` 指包含此技能 `SKILL.md` 文件的目录（由运行时提供的当前技能安装目录）。

## Stage 2 编排

当此技能为 Stage 2 加载时，编排器负责在线检索调用；此技能负责持久化、验证、去重、查询和导出本地文献库。

先解析工作区和 Stage 1 结果：

- 如果调用方显式传入 `$WORK` 或 `--library "$WORK/papers.json"`，直接使用该目录。
- 如果未显式传入 `$WORK`，但当前 agent 有用户会话工作区路径（例如 `~/.dsh/sessions/<session_id>/workspace`），将该工作区作为 `$WORK`。`<username>` 和 `<session_id>` 不得硬编码，必须从当前运行上下文或调用方参数取得。
- 从 `$WORK/writing_constraints.json` 读取 Stage 1 结果。若该文件存在，提取 `topic`、`subject`、`focus_points`、`target_paper_count`、`year_range` 和 `seed_papers`，用于用户上传论文理解、关键词生成和覆盖判断。
- 如果 `$WORK/writing_constraints.json` 不存在，报告缺失路径。仅当调用方显式提供了 topic/focus/target 等等价约束时才继续；否则停止并要求先完成 Stage 1。
- 规范文献库路径固定为 `$WORK/papers.json`。如果该文件不存在，在首次插入用户上传论文或种子论文时用 `--allow-create` 创建；不要把文献库写到 skill 安装目录或任意临时目录。

先把用户上传论文信息合并进 `papers.json`，再插入种子论文，最后进行关键词搜索：

- 如果用户在工作区上传或提供了论文信息，编排器应先将其解析为内存中的结构化论文记录，然后立即通过 `insert` 合并进 `$WORK/papers.json`。如果运行环境必须通过文件向 `insert --file` 传参，可以使用 `$WORK/.cache/scratch/` 下的临时批次文件；该文件只是命令输入，不是流程产物，插入成功后应删除或忽略。结构化记录字段至少包含 `title`、`authors`、`year` 和出版场所（`journal` / `booktitle` / `venue` 之一）。HTML/PDF/网页不是本脚本的直接输入，必须先由编排器抽取元数据或用 DOI/title 查找补全。
- 对用户上传论文插入时设置 `screening_stage: "core"` 和 `core_reason: "user-uploaded paper"`；如果只能得到部分元数据，不要插入缺少 title/authors/year/venue 的记录，应保留为待解析项并提示补 DOI 或标题。
- 使用 `insert` 将用户上传论文记录写入 `$WORK/papers.json`，然后运行 `validate`。这一步的目的，是让后续大模型在生成检索 query 和大纲前，可以读取规范文献库中的已上传论文主题、摘要和关键词。不要维护单独的 `user_uploaded_papers.json` 作为事实源。

用户上传论文之后插入种子论文，再进行关键词搜索：

- 读取 `writing_constraints.json` 并提取 `seed_papers`。
- 对每个 `"lookup_status": "resolved"` 的种子论文，插入时设置 `screening_stage: "core"` 和 `core_reason: "user-provided seed paper"`。
- 对每个 `"lookup_status": "unresolved"` 的种子论文，再尝试一次标题查找。若解析成功则插入；否则警告并跳过。不要插入没有元数据的记录。
- 种子论文插入后，运行验证。

种子论文之后运行 browser-use/remote-browser 候选发现与元数据补全循环。
Stage 2 对候选发现是 browser-only：不要用 `PaperSurveyToFile`、`PaperSearch`、
academic search API、通用 WebSearch、DOI/title lookup API、OpenAlex/Crossref/
Semantic Scholar/CORE/Lens API 端点或其他非浏览器检索工具开始、继续、恢复或补充
候选发现。通过 browser-use/remote-browser 打开元数据/API 端点，也不算有效的
浏览器发现分支。OpenAlex/Crossref 只能在
`$WORK/.cache/scratch/browser_candidates.json` 已经生成之后，由
`discover_and_resolve_papers.py` 做元数据解析时使用。将 browser-use/remote-browser
视为浏览器自动化能力类别，而不是字面工具名要求；只要运行时暴露的工具能打开真实网页、
导航/搜索、读取页面内容并写出候选结果，就属于等价浏览器工具，包括 deferred MCP 工具如
`mcp_remote_browser_*`。不要让用户在 browser-use 和 academic-search 之间做选择，
也不要把 academic-search 或任何非浏览器检索工具标为“推荐”。如果仅从规划上下文、
当前工具列表或缺少快捷入口看起来 browser-use/remote-browser 不可用，先执行运行时的
工具发现/find_tools，搜索 `browser`、`remote-browser`、`remote browser`、
`browser automation`、`MCP remote browser` 等关键词。若发现 `mcp_remote_browser_*`
等匹配工具，应激活并使用。只有完成发现后实际调用仍表明浏览器服务未启动时，才判定
浏览器工具不可用；此时停止并要求用户启用 browser-use/remote-browser，不要提供替代
检索工具。不要调用 `ask_user`、
`request_user_input` 或任何选择 UI 来提供 academic-search、PaperSearch、
PaperSurveyToFile、WebSearch、DOI/title lookup、API 端点检索或其他非浏览器选项。
如果必须弹 UI，只能询问用户启用 browser-use/remote-browser 或停止 Stage 2；
不得包含任何“推荐”的 fallback。

1. 选择检索关键词：
   - 如果 `$WORK/papers.json` 已存在且非空，编排器读取其中论文的 `title`、`abstract`、`journal` 和 `year`，抽取 3-5 个英文关键词短语作为种子检索关键词；关键词应反映已有上传/种子论文的主题，而不是只复述用户大题目。
   - 如果 `$WORK/papers.json` 不存在或为空，则从 `writing_constraints.json` 的 `topic`、`subject` 和 `focus_points` 抽取 3-5 个英文关键词短语。
   - 每个关键词短语 2-5 个词，优先覆盖不同 `focus_points`。不要生成尚未检索出的具体论文数量承诺。
2. 根据 `subject`、`topic` 和 `focus_points` 判断搜索站点，并由 agent 调用 browser-use、remote-browser 或等价的已发现 browser MCP 工具执行搜索。运行环境支持多个独立浏览器会话时，允许并建议并行检索：
   - 生物医学 / 医学 / 临床 / 药学 / 生命科学相关：优先 PubMed 和 Google Scholar。
   - 经济学 / 金融 / 管理 / 社科经济相关：优先 CNKI（知网）和 Google Scholar。
   - 工程 / 计算机 / 电子 / 机械 / 材料 / 自动化相关：优先 arXiv、IEEE Xplore 和 Google Scholar。
   - 领域不明确或交叉学科：至少使用 Google Scholar，再选择最接近的一个专业站点。
   - 只有当多个 query/site 分支不共享同一个浏览器 tab/session 状态时才并行运行。默认并行 2-4 个分支，且不得超过运行环境的 browser-use/remote-browser 限制。
   - 每个分支使用稳定名称，例如 `pubmed_query1`、`scholar_query1`、`cnki_query2` 或 `arxiv_query3`。
   - 启动 browser 分支前，先读取 `surveymaster-browser-search/SKILL.md`，并按领域读取匹配的 `surveymaster-browser-search/references*/SKILL.md`。这些子说明定义 browser-use 任务模板、站点页面处理和分支输出规则，是强制要求，不是可选参考。

3. browser-use/remote-browser 每个 query 提取前 10-20 条候选即可；总候选通常先收集 80-150 条，再由脚本去重和筛掉缺元数据记录。Browser 输出必须保存为工作区文件。并行分支各写自己的文件，不要在多个分支运行时同时 append 到同一个共享文件：
   - 不要遍历或阅读所有搜索结果。对每个站点只查看排序靠前的结果页，优先抽取引用量高、下载/阅读热度高、页面排名靠前、近年发表且与关键词高度相关的论文。
   - 如果页面显示引用次数、被引量、热度、推荐排序或相关度排序，优先保留这些指标更高的结果。不要为了凑数保留明显低相关、无作者/年份、无正式来源页面的结果。

   ```text
   $WORK/.cache/scratch/browser_candidates.json
   ```

   并行分支文件使用：

   ```text
   $WORK/.cache/scratch/browser_candidates.<branch>.json
   ```

   文件内容必须是 JSON 数组，形状如下。`abstract_hint` 只能来自页面明确的 Abstract/摘要区域；不要把搜索结果 snippet 冒充摘要。

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

4. 所有 browser-use/remote-browser 分支完成后，先把各分支候选文件合并为
   `$WORK/.cache/scratch/browser_candidates.json`，再进行元数据补全。合并时按
   DOI、arXiv ID、规范化标题和 URL 保守去重；重复候选信息不一致时保留信息更丰富的记录。不要把分支候选直接插入 `papers.json`。
5. 合并后的 browser-use 候选文件生成后，立即运行元数据补全与入库脚本：

   ```bash
   python3 <skill_dir>/scripts/discover_and_resolve_papers.py \
     --work "$WORK" \
     --candidates-json "$WORK/.cache/scratch/browser_candidates.json" \
     --library "$WORK/papers.json" \
     --bibliography-script "<skill_dir>/scripts/bibliography_library.py"
   ```

   该脚本会读取候选 JSON。若候选已经来自 PubMed/PMC/出版社页并具备 `title`、`authors`、`year`、`journal`/`booktitle` 和明确 `abstract`，可直接作为有效元数据进入补全流程；API 查询只用于补 DOI、卷期页码或缺失字段。解析顺序应优先使用 arXiv（如有 arXiv ID）和 Crossref DOI/title，OpenAlex 只作为补充来源；OpenAlex 出现 HTTP 429 时，本轮解析必须跳过 OpenAlex 并继续使用候选元数据/Crossref/arXiv，不得停止 Stage 2。补齐记录后，通过 `bibliography_library.py insert` 合并进 `$WORK/papers.json`，随后运行 `validate` 和 `stats`。
6. 如果 `$WORK/papers.json` 中有效记录仍低于 `target_paper_count`，编排器基于缺口 `focus_points` 再生成 1-3 个 query，重复 browser-use/remote-browser 候选发现（仍可按上述规则并行）和 `discover_and_resolve_papers.py` 入库。不要手动把 browser 候选直接拼进 `papers.json`；必须先经过元数据补全和 `insert` 校验。

Browser-only 失败处理：

- 如果某个 browser-use/remote-browser 分支没有返回可用候选，调整 query/site 后继续用 browser-use/remote-browser 重试。
- 如果访问/CAPTCHA/rate limit 阻断浏览，报告浏览器阻断状态，并询问用户是继续尝试 browser-use/remote-browser、缩小范围，还是使用现有文献库继续。不要提供 academic search API、PaperSearch、PaperSurveyToFile、WebSearch、DOI/title lookup 或任何其他非浏览器工具作为 fallback。
- 如果 browser-use/remote-browser 没有启动，停止并要求用户启用它。下一步只能是启用/重试 browser-use/remote-browser，或停止 Stage 2。

入库后，对每个关注点选择 top 3 论文，并用 browser-use/remote-browser 补充摘要或 digest。不要用 web search、academic-search 工具或 OpenAlex/Crossref API 返回作为主要摘要补充来源。应打开浏览器发现到的真实来源页，例如出版社/期刊页面、PubMed/PMC、CNKI 详情页、NBER、SSRN、RePEc、CEPR、IZA、作者主页或机构仓储。可用时，补充信息应信息密集，约 800-1200 字符。不要用更短的 digest 替换已有更丰富的 abstract。摘要补全建议使用比普通页面读取更长的超时预算：每个补全请求约 25 秒（比旧默认增加约 10 秒），并发建议 4-6 个分支；如果运行环境明确限制并发，则使用其上限。

摘要补全超时处理是硬规则：

- 先统计 `$WORK/papers.json` 中已成功拥有信息丰富 `abstract` / `summary` / `paperAbstract` 的有效记录数量。信息丰富的摘要通常应不少于 300 字符；短搜索片段、标题复述或一两句话 digest 不计入成功。
- 如果成功数 `>= 30`，停止摘要补全和继续搜索；使用这批已成功补全的记录进入 Stage 3，不要为了凑 `target_paper_count` 继续检索。
- 如果成功数 `< 30`，只对未成功补全的候选重试一次摘要补全；重试仍使用约 25 秒超时和 4-6 并发。重试后再次统计成功数。
- 重试后若成功数仍 `< 30`，报告成功数、失败数和超时原因，询问用户是继续 browser-use/remote-browser 搜索/补全、缩小范围，还是用当前成功记录继续。不要自动构造 `batch.json` 导入，也不要把摘要补全超时解释为 `insert` fallback 条件。
- 摘要补全超时不是搜索候选导入失败；它不得触发 `batch.json`、不得跳过 `discover_and_resolve_papers.py`，也不得把搜索预览或半成品候选直接 `insert` 进 `papers.json`。

在宣布 Stage 2 完成或进入 Stage 3 前，必须运行硬门禁：

```bash
python3 <skill_dir>/scripts/bibliography_library.py abstract-coverage \
  --library "$WORK/papers.json" --min-count 30 --min-chars 300 \
  --output "$WORK/.cache/abstract_coverage.txt"
```

如果该命令返回非零，读取报告并按上面的 `<30` 规则处理：重试一次摘要补全；重试后仍失败则询问用户。不得只用 `validate` 或 `stats` 代替该门禁。

对于手动组装的补充记录，只有在记录来自用户上传/用户明确提供/人工确认，且已具备完整元数据时，才使用 `insert`。搜索工具输出、摘要补全超时后的半成品候选，不属于手动补充记录。

搜索循环后，不要为了报告进度读取原始 `papers.json`。运行 `stats --limit 40`，并根据其紧凑 stdout 与导入命令结果行进行摘要。在任何报告中列出论文时，用 `bib_key`、DOI 或 `AuthorYear` 样式标签识别论文，绝不要在面向用户的输出中暴露原始 `paperId` 值。

如果覆盖量低于目标，询问用户是继续、缩小范围、扩大年份范围，还是添加论文。否则 Stage 2 完成，编排器可进入 Stage 3。

## Stage 5 BibTeX 解析

当由 `surveymaster-finalize` 加载时，在任何最终导出前运行 dry BibTeX 导出。通过 DOI/title 查找解析缺失 title、author、venue 或 year 的记录，并重新插入更新后的元数据。对于缺失 volume/pages 的警告，在可能时使用 `resolve_volume_pages.py` 解析。只有在阻塞性元数据问题被处理后，才重新导出最终 `$WORK/references.bib`。

## 常用命令

> **路径提醒。** 将 `<skill_dir>` 替换为此技能 `SkillLoad` 返回的 `skillDir`（例如 `/data/skills/surveymaster-literature-library`）。不要执行字面量 `<skill_dir>/...`。如果缺少 `skillDir`，再次调用 `SkillLoad`，不要搜索文件系统路径。

```bash
# ── 用户上传论文：Stage 2 开始时优先导入 ──
# 编排器先把 HTML/PDF/网页/用户输入解析为结构化论文记录，
# 然后直接创建或更新规范文献库。可用 stdin 传入 JSON 数组：
printf '%s\n' "$USER_UPLOADED_PAPERS_JSON" | \
  python3 <skill_dir>/scripts/bibliography_library.py insert \
    --library "$WORK/papers.json" \
    --allow-create --skip-invalid

python3 <skill_dir>/scripts/bibliography_library.py validate \
  --library "$WORK/papers.json"

# ── browser-use 候选结果：先由 agent 调插件搜索并写入候选 JSON，再补全入库 ──
# 候选文件路径：
# $WORK/.cache/scratch/browser_candidates.json
python3 <skill_dir>/scripts/discover_and_resolve_papers.py \
  --work "$WORK" \
  --candidates-json "$WORK/.cache/scratch/browser_candidates.json" \
  --library "$WORK/papers.json" \
  --bibliography-script "<skill_dir>/scripts/bibliography_library.py"

# ── 回退：手动 insert/merge（仅限非搜索结果、结果文件真正不可用且记录已人工确认完整时） ──
# 禁止把摘要补全超时、browser 候选、搜索工具预览作为 batch.json 导入。
# 1. Write 工具 -> $WORK/.cache/scratch/batch.json（临时；insert 后删除）
# 2. 运行 insert，然后删除 scratch 文件：
python3 <skill_dir>/scripts/bibliography_library.py insert \
  --library "$WORK/papers.json" --file "$WORK/.cache/scratch/batch.json" --allow-create && \
rm -f "$WORK/.cache/scratch/batch.json"

# 每个导入/插入批次后：只做验证；保持 stdout 紧凑
python3 <skill_dir>/scripts/bibliography_library.py validate \
  --library "$WORK/papers.json"

# 搜索循环后的紧凑进度摘要；不要读取原始 papers.json：
python3 <skill_dir>/scripts/bibliography_library.py stats \
  --library "$WORK/papers.json" --limit 40

# 查询特定 keys；只有后续步骤会消费时才写入文件
python3 <skill_dir>/scripts/bibliography_library.py query \
  --library "$WORK/papers.json" --keys k1,k2 --format simplified \
  --output "$CACHE/query.txt"

# 导出 bibtex（仅 Stage 5，在 DOI/title 元数据解析之后）
# 最终 PDF 前导出 — 脚本读取 mainbody.tex、提取 \cite{} keys，
# 并只写入被引用的文献库条目：
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
  --library "$WORK/papers.json" \
  --tex-file "$WORK/mainbody.tex" \
  --output "$WORK/references.bib" --warn-limit 10

# PDF 编译后的最终导出 — 只导出被引用条目，并按参考文献列表顺序：
# （从 export-pdf Step 6 调用，不要手动调用）
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
  --library "$WORK/papers.json" \
  --bbl-file "$WORK/build/<stem>.bbl" \
  --output "$WORK/references.bib" --warn-limit 10

# 年份过滤
python3 <skill_dir>/scripts/bibliography_library.py filter-year-range \
  --library "$WORK/papers.json" --min-year 2018 --max-year 2026 \
  --output "$CACHE/literature_filtered.json"

# 安全删除（默认检查引用）
# STAGE GUARD：只在章节写作开始前（Stage 2-3）调用 delete-keys。
# 如果任何 section .tex 文件已存在，删除被引用 key 会产生孤立 \cite{}
# 并破坏 LaTeX 编译。必须先重写引用相关章节。
python3 <skill_dir>/scripts/bibliography_library.py delete-keys \
  --library "$WORK/papers.json" --keys old1,old2 \
  --scan-tex "$WORK/sections;$WORK" --dry-run
```

## 字段名别名（insert 时自动规范化）

`insert` 命令在验证前会自动将常见字段名映射到规范文献库字段。这个兼容能力只用于人工确认的非搜索记录；它不允许用 `PaperSurveyToFile`、`PaperSearch`、academic search API、`PaperLookupByDoi` 或其他非浏览器检索工具执行 Stage 2 候选发现、恢复或补充。

| 规范字段 | 可接受别名 |
|---|---|
| `year`      | `publicationYear`, `publicationDate`, `pub_year`, `pub_date`, `publishedYear`, `date` |
| `authors`   | `authorList`, `author_list`, `authorNames` |
| `journal`   | `publicationEnName`, `journalName`, `journal_name`, `periodical`, `source` |
| `booktitle` | `conference`, `conferenceName`, `conference_name`, `proceedings_name` |
| `abstract`  | `paperAbstract`, `paper_abstract`, `summary` |
| `doi`       | `paperDoi`, `paper_doi` |
| `url`       | `paperUrl`, `paper_url`, `link`, `pdfUrl`, `pdf_url` |
| `title`     | `paperTitle`, `paper_title` |

对于 `year`，如果值是日期字符串（例如 `"2023-05-12"`），会自动提取 4 位年份。别名 key 会与规范 key 一起保留在存储记录中。

## 摘要保留

`abstract`、`paperAbstract`、`paper_abstract` 和 `summary` 都是信息丰富字段。不要删除它们、不要替换成泛泛的一行摘要，也不要在插入前过度压缩它们。合并重复记录时，如果传入重复记录的 abstract/summary 更短，insert 脚本会保留已有更长的 abstract/summary。后续更新只有在新摘要至少同等信息丰富时，才可以替换已有摘要。

## 约定

- 文献库路径：`$WORK/papers.json`（其中 `$WORK` 是综述输出目录，例如 `/bohr-workspace/<uuid>/`）
- `$CACHE` = `$WORK/.cache/`；检查/报告输出写到 `$CACHE`
- 数据形状：JSON 数组（兼容 `surveymaster-write-section`）
- 大结果优先写文件，减少上下文污染
- 有筛选元数据时保留：`screening_stage`（`candidate`、`screened`、`core`）、`relevance_score`、`venue_tier`、`citation_count`、`language` 和 `core_reason`
- 初始研究应偏向悲观检索：先 100-300 篇候选，再 40-80 篇筛选论文，主题范围允许时再得到 20-50 篇核心写作论文
- 写作过程中，如果补充搜索添加论文，也要更新同一个文献库。在引用这些论文前完成去重和验证
- 初始搜索、大纲生成或章节写作期间不要导出 BibTeX。Stage 5 中，在被引用/选定论文通过 DOI 或标题查找解析后，再生成 `references.bib`
- `export-bib` 会拒绝缺少关键元数据（title、author、publication venue 或 year）的记录，除非为了诊断显式使用 `--allow-incomplete`。通过 DOI/title 查找解析失败项，重新插入/更新文献库，验证后再导出
- 当 `article` / `inproceedings` 记录缺少 `volume` 和/或 `pages`/`number` 时，`export-bib` 会警告。**在为最终输出运行 `export-bib` 前，必须运行 `resolve_volume_pages.py` 解析所有 WARN keys，并确认剩余每个 WARN key 都已在 `papers.json` 中设置 `"unresolvable": true`。禁止跳过此步骤。** 不要为此目的使用 `PaperLookupByDoi` 或 `PaperLookupByTitle`。一旦某个 key 标记为 `unresolvable=true`，就将其视为最终状态：后续运行 `resolve_volume_pages.py` 会自动跳过它（`SKIP_UNRESOLVABLE`），解析器不会重试 API。不要把这些 key 反复出现的 WARN 行理解为需要再次运行解析器；应检查 `papers.json` 中的标记并继续。

## 解析缺失的 Volume / Pages

使用 `scripts/resolve_volume_pages.py` 解析 WARN keys。该脚本查询 OpenAlex（主）并自动回退到 Crossref，只补充缺失字段，并直接写回文献库。它使用有界请求池获取 DOI 元数据，但补丁应用和保存文献库在主进程中顺序执行。它只依赖标准库（无额外依赖）。

使用 `--verify-metadata` 时，脚本还会对所有有 DOI 的记录，根据 API 数据检查 title、first author、venue 和 year，并报告差异（`TITLE_MISMATCH`、`YEAR_MISMATCH`、`VENUE_MISMATCH`、`AUTHOR_MISMATCH`），但不修改这些字段。使用 `--dry-run` 可以在不写入任何更改的情况下查看完整报告。

### Step 1 — 收集 WARN keys

```bash
# 将 export-bib 诊断捕获到 stdout，便于直接传给解析器。
EXPORT_BIB_DIAGNOSTICS="$(
  python3 <skill_dir>/scripts/bibliography_library.py export-bib \
    --library "$WORK/papers.json" --tex-file "$WORK/mainbody.tex" --output "$WORK/references.bib" \
    --warn-limit 10 --diagnostics-stdout
)"
```

将 `$EXPORT_BIB_DIAGNOSTICS` 作为解析器输入。除非调试失败运行，不要另写诊断文件。不要运行 `grep -i "WARN"`，也不要把 grep 退出码 `1` 当成命令失败；没有 grep 匹配只表示没有匹配行。

### Step 2 — 使用有界并发解析

默认情况下，解析器使用 `--concurrency 4` 处理 DOI 元数据请求。只有网络稳定时才提高；遇到速率限制或 API 不稳定时降低。此设置不会引入并发写入。

**由你决定每次处理多少 keys。** 不要盲目一次性跑全部 keys。根据想验证的数量、网络情况或时间限制选择批次（每批 5-15 个 keys 是合理默认值）。

```bash
# 用默认请求池解析选定 keys：
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021,lee2019"

# 需要时调整请求池：
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021,lee2019" \
    --concurrency 2

# 先 dry-run 预览会修改什么：
python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" --keys "smith2020,jones2021" --dry-run

# 最终化期间，只验证从 export-bib 中选出的被引用 WARN keys：
printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
  python3 <skill_dir>/scripts/resolve_volume_pages.py \
    --library "$WORK/papers.json" \
    --verify-metadata --verify-targets-only \
    --report-stream stdout
```

每个批次后，查看 PATCHED / UNRESOLVABLE 输出。然后决定是否继续下一批，或停止。

### Step 3 — 解读输出，然后决定是否停止

**不要只根据退出码重试。** 退出码含义复合；将紧凑报告输出到 stdout，并检查 `SUMMARY:` 行：

```bash
METADATA_REPORT="$(
  printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
    python3 <skill_dir>/scripts/resolve_volume_pages.py \
      --library "$WORK/papers.json" \
      --keys "k1,k2,k3" \
      --report-stream stdout || true
)"
```

#### 退出码语义

| 退出码 | 含义 | 动作 |
|------|------|------|
| `0`  | 所有目标 keys 都进入终态（patched / already-filled / already-marked-unresolvable），且没有元数据差异。 | **停止。完成。** |
| `1`  | 至少一个 key 仍真正未解析（本次新出现 `UNRESOLVABLE`）。 | 查看下方决策树。 |
| `2`  | 只报告元数据差异（`TITLE_MISMATCH` 等）。Volume/pages 没问题。 | 向用户报告；不要重试解析器。 |
| `10` | I/O 错误（文献库路径错误、JSON 损坏）。 | 修复路径/文献库；这不是网络问题。 |

#### 单 key 报告解码

| 报告行 | 含义 | 对该 key 的动作 |
|---|---|---|
| `PATCHED <key>: {...}` | 本次填充了字段 | 完成 |
| `SKIP <key>: fields already populated` | 已经完整 | 完成 |
| `SKIP_UNRESOLVABLE <key>: ...` | 之前已标记 `unresolvable=true` | 完成，永不重试 |
| `UNRESOLVABLE <key>: no biblio data from OpenAlex or Crossref` | API 无数据；刚标记 `unresolvable=true` | 完成，接受并继续 |
| `SKIP <key>: no DOI in record — cannot fetch` | 记录没有 DOI | 手动添加 DOI 或接受缺口 |
| `SKIP <key>: not found in library` | bib_key 拼写错误 | 修正 key 字符串 |

#### 退出码 1 的决策树

1. 查看 `SUMMARY: ...` 行。如果 `patched=0` 且 `newly_unresolvable=0`，并且没有 `fetch_error` 行，**立即停止**，重复运行不会产生可执行变化。
2. 如果看到带网络类消息的 `fetch_error <key>: ...` 行（timeout、connection reset），用相同 keys 和相同 `--concurrency` 最多重试一次。不要缩小批大小；并发由 `--concurrency` 控制，不由传入 keys 数量控制。
3. 如果重试后仍显示相同 `UNRESOLVABLE` keys，这些记录现在已标记 `unresolvable=true`，下次会自动跳过。继续后续步骤。

#### 用 export-bib 确认

所有 keys 都进入终态后，重新运行一次 export-bib，确认 WARN 列表为空，或只包含已经在 `papers.json` 中标记为 `unresolvable=true` 的记录：

```bash
python3 <skill_dir>/scripts/bibliography_library.py export-bib \
    --library "$WORK/papers.json" --tex-file "$WORK/mainbody.tex" --output "$WORK/references.bib" \
    --warn-limit 10 --diagnostics-stdout
```

如果相同 keys 持续出现在 WARN 列表中，但 `papers.json` 显示每个 key 都有 `"unresolvable": true`，这就是最终状态。进入下一步，不要重新运行 `resolve_volume_pages.py`。

#### 禁止的反模式

- 为了“可能有帮助”而缩小批大小（10 -> 5 -> 2 -> 1）；并发由 `--concurrency` 限制，不由 `--keys` 长度限制。
- 连续用相同 keys 重跑超过 2 次。
- 只读退出码，不读 stderr。
