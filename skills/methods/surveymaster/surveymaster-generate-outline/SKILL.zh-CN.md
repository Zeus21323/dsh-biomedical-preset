---
name: surveymaster-generate-outline
version: 0.2.0
description: 为研究主题生成结构化、层级化的学术综述大纲。当用户希望规划或撰写文献综述/综述论文大纲时使用。支持中文和英文输出。生成经脚本规范化的 outline.json（包含 core_claim、length_target 和 key_papers）以及可读的 outline.md。
argument-hint: "<topic> [--language zh|en] [--papers papers.json] [--constraints writing_constraints.json] [--title preferred-title] [--constraints-text extra-constraints] [--revise-from outline.json]"
---

## 阶段契约

阶段：3 — 大纲生成与修订。

加载者：SurveyMaster 编排器在 Stage 2 生成 `papers.json` 后加载；或在已有大纲需要修订时加载。

必需输入：
- `$WORK/writing_constraints.json`。
- `$WORK/papers.json`。
- 主题、语言，以及可选标题或额外大纲约束。
- 修订模式下需要已有 `outline.json`。

输出：
- `$WORK/outline.json`，作为规范化结构化大纲和唯一事实源。
- `$WORK/outline.md`，作为用户可读的大纲视图。

完成条件：
- 两个大纲文件都存在。
- `outline.json` 中每个相关条目都包含 `core_claim`、`length_target` 和 `key_papers`。
- 编排器在展示大纲确认 gate 前，已经通过平台面向用户的文件预览/更新机制保存或更新 `outline.md`。文件仅存在于 `$WORK` 磁盘目录中不能替代该用户可见的预览/更新步骤。
- 用户已通过 Stage 3 的 `ask_user` 确认 gate 确认大纲，并且该问题设置了 `allow_other: false`。
- `ask_user` fallback、无答案或超时不算确认，不能满足此完成条件。

可以加载其他技能：
- 否。

## 文件写入策略

所有文件写入都使用 `Write`（创建/覆盖）或 `Edit`（补丁）。禁止使用 shell heredoc，因为它们会破坏 LaTeX 和 JSON 中的反斜杠。

## 依赖

| 文件 | 作用 |
|------|------|
| `scripts/save_outline.py` | 规范化大纲，并写入 `outline.json` 与 `outline.md` |

不需要外部包（仅标准库）。要求 PATH 中有 `python3`。

脚本调用中的 `<skill_dir>` 指包含此技能 `SKILL.md` 文件的目录（运行时提供的当前技能安装目录）。

## 参数

$ARGUMENTS

- 第一个位置参数（或 `--topic`）— **必需**
- `--language zh|en` — 通常由编排器根据当前用户请求显式传入；如果缺失，只能从当前 topic 文本推断：CJK 占比高则为 zh，否则为 en。不要从已有 `writing_constraints.json` 或 `outline.json` 推断语言。
- `--papers <file.json>` — 可选；用于影响大纲结构和论文分配
- `--constraints <file.json>` — **强烈建议**；Stage 1 生成的 `writing_constraints.json`。用于驱动 section 数量、`total_length_target`、每节 `length_target`、`focus_points`、`extra_requirements`、`venue_style_notes` 和 `citation_style`
- `--title <text>` — 偏好标题提示（可以优化）
- `--constraints-text <text>` — 自由文本额外大纲约束（如果同时提供 `--constraints` 文件，则与文件内容合并）
- `--revise-from <file.json>` — 修订模式：跳过 Step 2 生成，直接将已经修改过的大纲重新规范化并重新渲染，执行 Step 3-4。修订模式假定调用方已经把期望修改应用到 `outline.json`；此技能只负责重新规范化和渲染。

## 固定输出文件名

此技能在 `<output-dir>` 下写入两个固定文件：

| 文件名 | 作用 |
|---|---|
| `outline.json` | 脚本规范化后的大纲，是下游脚本的事实源。每个条目存储结构字段以及 `core_claim`、`length_target` 和 `key_papers`。 |
| `outline.md` | 面向用户的富文本可读视图 |

两个文件名固定。不要改名。下游技能（`surveymaster-write-section`、`surveymaster-refine-section`）只从 `outline.json` 读取大纲。

两个文件由一次 `save_outline.py` 调用写入，永远不要手动写 `outline.md`。

## Step 1 — 加载输入

如果提供 `--papers`，读取该文件。文件不存在时：报告路径，并在无 papers 的情况下继续。

`papers.json` 必须来自 Stage 2 的规范文献库，可以由 browser-use 候选经 `discover_and_resolve_papers.py` / `bibliography_library.py insert` 生成。此技能只依赖规范字段，不依赖 PaperSearch/PaperSurveyToFile 专有字段。读取后建立论文语料索引：

当提供 `--papers` 时，生成大纲前必须校验 Stage 2 摘要覆盖：

```bash
python3 <literature_skill_dir>/scripts/bibliography_library.py abstract-coverage \
  --library <papers.json> --min-count 30 --min-chars 300 \
  --output <output-dir>/.cache/abstract_coverage.txt
```

如果该命令返回非零，不要生成 `outline.json`。读取报告，要求编排器回到 Stage 2 进行一次摘要补全重试；若重试后仍不足 30，再询问用户是否用当前低摘要文献库继续。不得用总记录数多来替代丰富摘要数量。

- 必需索引键：`bib_key`。`paper_ids` 和 `key_papers` 只能引用这些 `bib_key`。
- 用于分配章节的字段：`title`、`abstract`、`journal`、`year`，可选使用 `authors`、`doi`、`url`。
- 如果某条记录缺少 `bib_key`，不得为其临时发明 key；报告该问题并要求编排器回到 Stage 2，用 `bibliography_library.py insert` 重新规范化 `papers.json`。
- 如果记录缺少 `abstract`，仍可用于标题/venue 层面的弱参考，但不得把它列为某个 body section 的 `key_papers`，除非该 section 没有其他有摘要论文可用。
- 大纲生成时优先把有摘要、与 `focus_points` 高相关、年份较新或期刊/会议更权威的论文分配为 `key_papers`。

如果提供 `--constraints`，读取该文件。文件不存在时：警告并使用默认值（zh：`total_length_target = 10000` 字；en：`= 7000` 词；`target_paper_count = 50`；无 focus_points）。警告消息必须包含：
`Warning: writing_constraints.json not found. length_target, citation_style, and other constraints will use defaults and may not match expectations. Complete Stage 1 first if a full survey is planned.`

加载后提取：

- `language`（如果设置，则覆盖 `--language`）
- `focus_points`
- `extra_requirements`
- `venue_style_notes`
- `total_length_target`
- `section_length_policy`
- `citation_style`

## Step 2 — 生成大纲（设置 `--revise-from` 时跳过）

如果提供 `--revise-from <file.json>`，完全跳过本步骤：加载该文件作为大纲输入，从其顶层字段设置 `survey_title` / `language`（回退到 `--title` / `--language`），然后跳到 Step 3。修订模式假定调用方已经对 `outline.json` 应用了期望编辑；此技能只重新规范化和重新渲染。

**中文约束：**
你是学术综述大纲设计专家。

基础约束：
- 引言与结论不得含子章节；不加摘要章节（摘要在成稿阶段生成）。
- 章节标题不带数字前缀；返回嵌套结构；标题与描述须清晰、学术化。
- 对适合拆分的顶层 section 优先写出 2-4 个 subsection。
- 若输出隐藏思考内容，也使用简体中文。

由 writing_constraints 驱动的约束（若提供）：
- 总字数目标参考 `total_length_target`；按比例把预算分配到各 section 的 `length_target`；引言/结论占比可低于正文 section。
- 用户的 `focus_points` 必须被至少一个 body section 的 `core_claim` 明确覆盖。
- `extra_requirements` 与 `venue_style_notes` 会影响 section 选取与命名。

每个 section 与 subsection 都必须输出：
- `title`
- `description`（3-5 句，足以指导写作）
- `core_claim`（1 句中心论点，必填）
- `length_target`（形如 `{"zh_chars": N}` 或 `{"en_words": N}`）
- `paper_ids`（top-level section：相关 `bib_key` 列表或 `"all"`；subsection / subsubsection：`[]`）
- `key_papers`（2-5 个来自文献库的 `bib_key`）

规模下限：除引言和结论外至少规划 5 个正文 section；每个非平凡 section 设 2-4 个 subsection；section description 须足够详细以指导写作。

**英文约束：**
你是学术综述大纲设计专家。

基础规则：
- Introduction 和 Conclusion 不能有 subsections。不要在大纲中包含 Abstract。
- 标题不带数字前缀。优先使用嵌套结构。标题和描述必须清晰且学术化。
- 对任何可有意义拆分的 body section 添加 2-4 个 subsections。
- 如果模型输出隐藏推理内容，保持英文。

**由 writing_constraints 驱动的规则（若提供）：**
- 将 `total_length_target` 分配到各 section，填充每个条目的 `length_target`；Introduction/Conclusion 可小于 body sections。
- 每个用户 `focus_point` 必须被至少一个 body section 的 `core_claim` 明确覆盖。
- `extra_requirements` 和 `venue_style_notes` 影响 section 选择与命名。

每个 section 和 subsection 必须输出：
- `title`
- `description`（3-5 句，足以指导写作）
- `core_claim`（一句中心论点，必需）
- `length_target`（`{"zh_chars": N}` 或 `{"en_words": N}`）
- `paper_ids`（top-level section：相关 `bib_key` 列表或 `"all"`；subsection / subsubsection：`[]`）
- `key_papers`（来自论文语料的 2-5 个 `bib_key`；subsection 可以为空）

**不做数量预测：** 不要陈述尚未计算出的具体数量（如“本综述将有 N 个章节”或“将引用 N 篇论文”），除非数量来自已执行脚本或用户明确指定。对预期结果使用开放表述。

**规模规则**（自适应用户请求和约束；无固定下限）：
- section 数量和命名优先级：① 用户在 topic 中明确指定的章节数量/方向 > ② `writing_constraints` 中的 required sections > ③ 默认（未指定）：除 Introduction 和 Conclusion 外 3-5 个 body sections。
- subsection 数量根据父 section 的 `length_target` 自适应：
  - `[zh]` < 800 字：无 subsections 或最多 2 个；>= 1200 字：建议 2-4 个 subsections。
  - `[en]` < 500 词：无 subsections 或最多 2 个；>= 800 词：建议 2-4 个 subsections。
  - 不要为了满足数量而强行拆分。
- 不要把用户指定的 N 部分大纲扩展为 N+1 或更多。如果关键内容无法放入，使用嵌入式组织方式（见 Critical-organization），不要新增 sections。
- 当用户指定 brief 与 focus sections 时，focus section 的 `length_target` 必须至少是 brief section 的 2 倍。

**标题命名规则（强制）：**

- 顶层 body section 标题不能是空泛套话；必须包含具体机制关键词、研究对象或评估维度。反例："Recent Progress" / "Current Status" / "Methods Overview" / "Related Work" / "Algorithm Survey"。
- **替换测试：** 最终确定任何标题前，检查：如果只替换 topic 名称，这个措辞是否能出现在同一宽泛主题下另一篇论文中？如果可以，用来自 section `core_claim` 的内容特异词替换泛化部分，例如命名机制、临床挑战、方法、工具、证据类别或比较维度。
- **信息密度测试：** 读者只扫章节标题、不读描述，也应能预判该节中心论点、关键权衡或区分性发现。只表示“关于什么”的标题不合格；能表示“论证或展示什么”的标题合格。
- **学术语体要求：** 标题必须使用朴素描述性名词短语，命名机制、方法、结果或权衡。不要使用文学化、隐喻化或修辞化语言。
- 推荐标题长度：
  - `[zh]` 6-10 个字；若包含具体研究对象，可更短。
  - `[en]` 4-8 个词；若包含具体研究对象，可更短。
- **标题标准：** 所有 section 标题必须符合学术惯例，简洁、准确，并能充分说明该节范围和内容。没有强制或禁止的具体标题形式；标准是读者能从标题本身无歧义地理解重点。

**关键组织要求（强制，自适应大纲规模）：**
- **必需内容：** 大纲必须至少覆盖以下之一：research gap / field open debate / evidence-strength comparison across sources。
- **放置方式**（任选其一，不要发明额外 sections）：
  - Body sections >= 4：可以在结论前设置一个专门 body section。
  - Body sections = 2-3：放入核心 body section 的专门 subsection，或折入 conclusion 的 `core_claim` 和 `description`。
  - 当用户的 conclusion section 已经命名为 future directions / bottlenecks / gaps 时，该 section 的 `core_claim` 已足够。
- **统一评估框架**（无论 section 数量多少都必需）：Introduction 的 `core_claim` 必须明确描述一个包含以下三者的框架：
  1. **框架名称**（例如 `[zh]` “配位强度—空间位阻—给体原子三参数空间” / `[en]` “coordination-strength × steric-hindrance × donor-atom three-parameter space”）
  2. **构成维度/参数**（明确列出 2-4 个命名分析维度）
  3. **评价标准/比较基线** — 被评价对象是什么，以及与什么比较（如 advantage-validity conditions、applicability boundaries、classical baseline methods、current state-of-the-art）

  框架名称必须在 conclusion 的 `core_claim` 中被提及，并在至少两个 body sections 的 `description` 中作为分析维度使用。4-section 和 5-section 大纲同样适用。

**过渡与递进（强制）：**
- 当父 section 包含 >=3 个异质 subsections 时，其 `core_claim` 必须明确说明 subsections 之间的逻辑关系，使用以下之一：progressive / closed-loop / complementary / contrastive。禁止空泛列举式 `core_claim`。
- 父 section 的 `description` 还必须说明 subsections 的组织依据（按机制类型/时间演进/问题层级/比较维度），而不只是复述 subsection 标题。

**描述中的证据来源标签（强制）：**
- 每个 body section 的 `description` 必须以 evidence-source 标签结尾（选 1-3 个标签）：`theoretical analysis`、`numerical demonstration`、`hardware experiment`、`review-based judgment`、`experimental observation`、`first-principles calculation`、`literature meta-analysis`。
  - 格式：`(Evidence source: theoretical analysis + numerical demonstration, with limited hardware-experiment validation)`
- 该标签是 outline 内部规划元数据，只用于帮助写作阶段判断证据层级；不得被正文照抄或转写为“证据来源：……”之类的可发表文本。

### 输出 JSON schema（严格生成此形状）

```json
{
  "survey_title": "...",
  "language": "zh|en",
  "expected_figures_total": 3,
  "expected_tables_total": 2,
  "sections": [
    {
      "index": 1,
      "title": "...",
      "type": "section",
      "description": "...",
      "core_claim": "...",
      "length_target": {"zh_chars": 1500},
      "paper_ids": "all",
      "key_papers": ["bib_key_a", "bib_key_b"],
      "planned_figures": [
        {"type": "architecture_diagram"}
      ],
      "planned_tables": [
        {"type": "performance_comparison"}
      ],
      "subsections": [
        {
          "index": 2,
          "title": "...",
          "type": "subsection",
          "description": "...",
          "core_claim": "...",
          "length_target": {"zh_chars": 500},
          "paper_ids": [],
          "key_papers": []
        }
      ]
    }
  ]
}
```

**`planned_figures` 字段规则：**
- 每个顶层 section 可以带可选 `planned_figures` 数组。
- 每个条目只包含 `{"type": "<figure_type>"}`。这里不指定 caption 或 prompt，write-section 会根据 `core_claim` 生成。
- `type` 必须是：`concept_illustration`、`architecture_diagram`、`workflow_diagram`、`comparison_visual`、`timeline_visual`。
- 所有 section 中 `planned_figures` 条目总数必须等于 `expected_figures_total`。
- **Introduction first：** 当 `expected_figures_total >= 1` 时，优先把第一张图分配给 Introduction section。推荐类型：`architecture_diagram`（研究图景/分类体系）或 `timeline_visual`（发展历史）。
- **Conclusion excluded：** 不要给 Conclusion section 分配任何 figures。
- Subsections 不携带 `planned_figures`；只分配给顶层 section。

**`planned_tables` 字段规则：**
- 每个顶层 section 可以带可选 `planned_tables` 数组。
- 每个条目只包含 `{"type": "<table_type>"}`。这里不指定列结构或 caption，write-section 会根据 `core_claim` 生成。
- `type` 必须是：`performance_comparison`、`classification_comparison`、`challenge_strategy_matrix`。
- 所有 section 中 `planned_tables` 条目总数必须等于 `expected_tables_total`。
- **Introduction 和 Conclusion excluded：** 不要给 Introduction 或 Conclusion section 分配任何 tables。
- Subsections 不携带 `planned_tables`；只分配给顶层 section。

> **规则速查（强制）：**
>
> **用户未指定 section 数量**（自由生成大纲）：
> - Introduction section `core_claim`：明确描述统一评估框架（必须包含 "evaluation framework / design space / parameter space" 等关键词）。
> - 倒数第二个 body section：可作为独立的 "Research Gaps / Controversies" section（标题和 `core_claim` 必须包含相关关键词）。
>
> **用户指定了 N 个 sections 及命名方向**（例如 4-section outline）：
> - 严格遵循用户给定 section 数量和命名方向；**禁止新增 sections**。
> - Introduction section 复用用户提供名称，但 `core_claim` 仍必须明确描述统一评估框架。
> - 关键内容（research gaps / controversies）合并进最后一个用户指定 section 的 `core_claim` 和 `description`。
> - Conclusion section 标题复用用户提供名称。
> - 每个 body section 的 `description` 仍必须以 `(Evidence source: ...)` 注释结尾。
>
> **共同要求：** 每个 body section 的 `description` 末尾追加 evidence-source 注释；任何包含 >=3 个 subsections 的父 section，其 `core_claim` 必须包含 progression / closure / complementarity / contrast 之一。
>
> 这两种场景对应 Step 4 自检规则。所有自检项都必须 PASS。

## Step 3 — 保存输出文件

`save_outline.py` 会规范化大纲，将 `core_claim`、`length_target`、`key_papers` 等 rich fields 直接存入 `outline.json`，并渲染 `outline.md`。全部通过一次调用完成。不要单独用 heredoc 写 Markdown。

使用 `Write` 工具将 Step 2 生成的 JSON 直接写入 `<output-dir>/outline.json`，然后调用脚本对同一个文件原地规范化并渲染 `outline.md`。脚本直接从 `--file` 读取 JSON 内容；不要通过 `$(cat ...)` 或其他 shell 替换传 JSON，因为大型或多行 LLM 输出可能超过 `ARG_MAX`，或在到达 argparse 前被 shell 层破坏。

写入 `<output-dir>/outline.json` 时，只写 JSON 对象本体：不要写 Markdown
代码围栏、解释性文字、注释或尾随说明。JSON 结构字符必须使用 ASCII
字符（`{}`, `[]`, `:`, `,`, `"`），即使字符串值是中文。中文标点只能出现在已经加双引号的字符串值内部。如果规范化报告 JSON 语法错误，不要先整篇重新生成大纲；先对同一个文件重新运行一次 `save_outline.py`，该脚本会在失败前尝试提取代码围栏内 JSON，并规范化常见的全角结构标点，然后给出准确解析位置。

1. `Write` -> `<output-dir>/outline.json`，内容为 Step 2 生成的 JSON
2. 运行：

```bash
python3 <skill_dir>/scripts/save_outline.py \
  --file <output-dir>/outline.json
```

对于 **`--revise-from` 模式**，将修改后的 `outline.json` 内容写回 `<output-dir>/outline.json`，并重新运行同一命令。由于 rich fields 存在于每个 outline entry 中，保留用户编辑意味着在调用脚本前必须保留这些字段：

1. `Write` -> `<output-dir>/outline.json`，内容为通过 `--revise-from` 加载的 JSON
2. 运行：

```bash
python3 <skill_dir>/scripts/save_outline.py \
  --file <output-dir>/outline.json
```

失败时，`outline.json` 保留为规范化前形态，便于检查。权威输出是 `<output-dir>` 下的 `outline.json` 和 `outline.md`。

## Step 4 — 质量自检（强制，结构化，有审计轨迹）

**此步骤不可跳过，且必须在磁盘上生成结构化产物。agent 在该产物存在，并且所有 FAIL 项已被修复或标注前，不得进入 Step 5。**

> **为什么此步骤严格：** 过往运行中，大纲生成器曾在提供论文语料时输出 `key_papers: []` 的 body sections，也曾输出缺少明确 evaluation framework 的 introduction `core_claim`。这些正是此自检要捕捉的模式。每项检查都必须针对 JSON 内容真实评估，而不是自我确认。

### Step 4-A：运行清单并写结构化报告

遍历下面每个检查项。对每项记录：
- item id（1-8）
- `status`：`PASS` / `FAIL` / `REPAIRED`
- 当 `FAIL` 或 `REPAIRED` 时，记录违规的 `index` 值和一行失败原因
- 当 `REPAIRED` 时，记录修复后的新 title / core_claim / description 文本

使用 `Write` 工具将报告写入 `<output-dir>/.cache/scratch/outline_self_check.json`。Schema：

```json
{
  "outline_path": "<absolute path to outline.json>",
  "language": "zh|en",
  "section_count_body": 4,
  "checks": [
    {
      "id": 1,
      "name": "title_naming_compliance",
      "status": "PASS|FAIL|REPAIRED",
      "violations": [
        {"index": 5, "title": "总结与展望", "reason": "first token is blacklisted '总结与展望'"}
      ],
      "repairs": [
        {"index": 5, "field": "title", "new_value": ""}
      ]
    }
  ],
  "overall_status": "PASS|REPAIRED|WARN",
  "warn_reasons": []
}
```

如果跳过写入此文件，Step 5 必须拒绝展示大纲，并向编排器返回错误。

### Step 4-B：修复轮次（仅一次）

对每个 `status: FAIL` 的检查，在内存中生成修复后的 entry，重新运行 `save_outline.py` 持久化编辑，然后只重新评估该检查项。若第二次评估通过，将状态更新为 `REPAIRED`；否则保持 `FAIL`。不要循环超过一次。任何最终仍为 `FAIL` 的项目都会将 `overall_status` 设为 `WARN`，并加入 `warn_reasons`。

### Step 4-C：检查清单（每项都针对 outline 评估）

1. **标题质量检查。** 每个顶层 section 标题必须符合学术惯例：简洁、无歧义，并能让读者仅凭标题理解该节范围。过于模糊的标题 WARN；明显与内容无关的标题 FAIL。
2. **关键组织内容存在。** 至少一个位置包含以下关键词之一：专门 body section 的 `title` 或 `core_claim`、专门 subsection 的 `title` 或 `core_claim`、conclusion section 的 `core_claim` 或 `description`。关键词包括：`研究缺口`/`未解问题`/`争议`/`证据强弱`/`证据强度`/`research gap`/`open question`/`debate`/`evidence-strength`/`evidence strength`。不要求专门 section，嵌入 conclusion 也算。
3. **三部分统一评估框架。** Introduction 的 `core_claim` 必须包含：(a) 框架名称；(b) 2-4 个命名构成维度；(c) 评价标准/比较基线。任一缺失即 FAIL。同一框架名称还必须出现在 conclusion 的 `core_claim`，并出现在至少两个 body sections 的 `description` 中。
4. **异质父 section 的过渡 core_claim。** 每个包含 >=3 个 subsections 的父 section，其 `core_claim` 必须包含：`递进`/`闭环`/`互补`/`对照`/`progressive`/`closed-loop`/`complementary`/`contrastive` 之一。少于 3 个 subsections 的 section 豁免。
5. **证据来源标签。** 每个 body section 的 `description` 必须以包含 `证据来源` 或 `Evidence source` 的括号标签结尾。
6. **section 数量一致性。** 顶层 body sections 数量（不含 Introduction 和 Conclusion）必须等于用户在 topic 中明确指定的数量。如果用户未指定，该项自动 PASS。此失败优先级最高；绝不要为了满足其他检查而改变用户指定数量。
7. **`key_papers` 密度。** 每个顶层 body section（不含 introduction 和 conclusion）的 `key_papers` 至少包含 2 个来自论文语料的条目。Subsections 可以为空。如果未向此技能提供 `--papers`，该项自动 WARN（非 FAIL），且 agent 必须在报告顶层添加 `pending_paper_search` 字段，提示编排器需要回到 Stage 2。
8. **图表字段一致性。** `expected_figures_total`、`expected_tables_total` 必须存在且为非负整数；优先读取 `writing_constraints.json` 中的 `target_figure_count` / `target_table_count`，否则默认 3 图、2 表。`planned_figures` 总数必须等于 `expected_figures_total`，类型必须合法；当 `expected_figures_total >= 1` 时 Introduction 应至少有一张图（缺失为 WARN）。`planned_tables` 总数必须等于 `expected_tables_total`，类型必须合法；Introduction 和 Conclusion 不得携带 `planned_tables`。

**修复范围：** 检查失败时，只针对失败 entries 重新运行 Step 2 生成（使用 `--revise-from`，并在 prompt 中注明失败 indices）。不要重新生成整个大纲，保留通过检查的 entries，以保持用户可见结构稳定。

如果技能内修复会冲突于用户正在进行的修订，跳过修复并发出警告，避免覆盖用户编辑。

## Step 5 — 展示与摘要

**前置条件（硬 gate）：** 在本步骤做任何事前，agent 必须读取 Step 4 写入的 `<output-dir>/.cache/scratch/outline_self_check.json`。如果文件不存在，立即中止并返回错误：`"ERROR: Step 4 self-check artifact missing. Cannot display outline. Re-run from Step 4."`

读取 `<output-dir>/outline.md` 并向用户展示其内容。

然后报告：
- Survey title
- Language
- Section count 和 total entry count
- `outline.json`、`outline.md` 路径
- 任何警告（脚本自动检测的 missing `core_claim`、缺少 `--constraints`、缺少 `--papers`）
- 在 bullets 之后追加 self-check JSON 的绝对路径，方便编排器程序化重读。

**硬停止 — 此技能至此完成。** 编排器不得在用户通过 `ask_user` 明确接受大纲前继续章节写作。下一步必须是：
1. 向用户展示 `outline.md` 内容（已完成）。
2. 通过平台面向用户的文件预览/更新机制保存或更新 `outline.md`。
3. 在调用任何写作技能前询问 Stage 3 确认 gate，并设置 `allow_other: false`：
   - zh question: `以下是本次综述的大纲。是否接受该大纲并开始写作？`
   - en question: `The outline above is ready. Accept it and start writing?`
   - options: `接受，开始写作` / `Accept and start writing`；`我要修改` / `I want changes`。
4. 如果用户选择接受，进入 Stage 4。
5. 如果用户选择修改，停止并要求用户在下一条消息中描述大纲修改要求。不要调用任何写作技能。
6. 如果 `ask_user` 不可用、超时、没有答案，或返回 fallback/proceed-best-judgment 类消息，将大纲视为未确认。停止并等待明确用户输入；不要调用任何写作技能。

展示分配论文时：

- 具体列表：把每篇论文显示为 `bib_key - <exact title>`，带数量，不能省略。
- `"all"`：只显示总数，不逐一列举。
- `[]`：说明 `No papers assigned.`

Subsections 继承父级论文分配；除非用户要求，否则不要单独展示。对每个具体列表 section，自检显示的 bullet 数量等于 `len(paper_ids)`。

## 附录 — 大纲修订纪律

**一致性不变量：** `outline.json` 是唯一结构化大纲事实源。其 `outline` 数组中的每个 entry 同时包含结构字段（`title`、`type`、`description`、`parent_index`、`paper_ids`）和写作 rich fields（`core_claim`、`length_target`、`key_papers`）。

永远不要直接编辑 `outline.md`。修订大纲时，先修改 `outline.json`，然后通过此技能重新运行 `save_outline.py`，规范化 `outline.json` 并重新渲染 `outline.md`。

当用户要求修改大纲时，编排 agent 必须：

1. **修改 JSON，而不是 MD。** 将用户意图转为 `outline.json` 的编辑。常见编辑：
   - 重命名 section -> 更新匹配 `index` 的 `title`
   - 添加/删除 subsection -> 重新生成时编辑嵌套 `subsections` 数组，或在 flat `outline.json` 中增删条目
   - 修改长度目标 -> 更新 entry 的 `length_target`
   - 修改 core claim -> 更新 entry 的 `core_claim`
   - 重新分配 papers -> 更新 `paper_ids`；如果用户指定，也更新 `key_papers`
2. **通过此技能重新规范化。** 使用 `--revise-from <mutated outline.json>` 重新调用 `surveymaster-generate-outline`。该路径跳过 Step 2 生成，但仍运行 `save_outline.py`，以原子方式重写 `outline.json` 和 `outline.md`。
3. **永远不要直接编辑 `outline.md`。** Markdown 是派生视图；直接编辑会在下一次重新生成时丢失。
