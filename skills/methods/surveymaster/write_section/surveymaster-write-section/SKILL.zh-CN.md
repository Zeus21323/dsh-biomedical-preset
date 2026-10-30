---
name: surveymaster-write-section
version: 0.2.0
description: 一次性撰写完整综述正文（abstract/摘要、keywords/关键词和所有章节），输出单个 mainbody.tex。当用户希望起草或重写整篇文献综述正文时使用。
argument-hint: "--output-dir dir [--mode draft|rewrite] [--language zh|en] [--survey-title text] [--core-topic text] [--papers papers.json] [--outline outline.json] [--constraints writing_constraints.json]"
---

## 阶段契约

阶段：4 全文正文起草与重写；导出后修订中的内容重写。

加载者：SurveyMaster 编排器在 Stage 3 大纲确认 gate 通过后加载；或在完成导出后需要内容重写时由 Post-export Revision 加载。

必需输入：
- `$WORK/writing_constraints.json`。
- `$WORK/outline.json`。
- `$WORK/papers.json`。

输出：
- `$WORK/mainbody.tex` — 规范完整正文，包含 `\begin{abstract}`、`\keywords{}`、`\maketitle`、`\tableofcontents` 和所有正文 `\section{}`。不创建 `sections/` 目录；不写入 `abstract.tex` 或 `keywords.tex`。
- `$WORK/figures/<id>.png` — 当 `expected_figures_total > 0` 时，每张图一个文件。

完成条件：
- `$WORK/mainbody.tex` 存在，并包含 `\begin{abstract}`、`\keywords{}` 和至少一个 `\section{}`。
- 当 `expected_figures_total > 0` 时：`mainbody.tex` 中每个 `% FIGURE id=xxx` 注释都有对应的 `$WORK/figures/<id>.png`。

可以加载其他技能：
- `surveymaster-check-and-merge`（仅脚本 — Bash 前先 `SkillLoad`）
- `surveymaster-literature-library`（仅脚本 — Bash 前先 `SkillLoad`）

## 文件写入策略

所有文件写入都使用 `Write`（创建/覆盖）或 `Edit`（补丁）。禁止使用 shell heredoc，因为它们会破坏 LaTeX 和 JSON 中的反斜杠。

## 参数

$ARGUMENTS

- `--output-dir <dir>` — 综述根目录（**必需**）
- `--mode draft|rewrite` — 默认 `draft`；`rewrite` 会读取已有 `mainbody.tex` 并修订
- `--language zh|en` — 默认 `zh`
- `--survey-title <text>`、`--core-topic <text>`
- `--papers <file.json>` — 完整论文文件（可选，但引用需要它）
- `--outline <file.json>` — 完整大纲文件（可选覆盖；默认 `<output-dir>/outline.json`）
- `--constraints <file.json>` — `writing_constraints.json`（可选覆盖）

## Step 1 — 预检

如果 `--output-dir` 缺失或为空，在读取或写入任何文件前中止。

只解析一次路径，并绑定到变量供后续所有 Bash 命令使用。

**前置要求：** 在下面 Bash 块之前，先 `SkillLoad` `surveymaster-check-and-merge` 和 `surveymaster-literature-library`。

```bash
WORK="<output-dir>"
OUTLINE="${OUTLINE_ARG:-$WORK/outline.json}"
CONSTRAINTS="${CONSTRAINTS_ARG:-$WORK/writing_constraints.json}"
PAPERS="${PAPERS_ARG:-$WORK/papers.json}"
SURVEY_LANG=$(python3 -c "import json,sys; d=json.load(open('$CONSTRAINTS')); print(d.get('language','zh'))" 2>/dev/null || echo "zh")
CHECK_SKILL_DIR="<skillDir from SkillLoad(surveymaster-check-and-merge)>"
LIT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-literature-library)>"
```

如果任何必需文件（`$CONSTRAINTS`、`$OUTLINE`）不存在，立即中止。对于 `--mode rewrite`，还要验证 `$WORK/mainbody.tex` 存在。如果 `$CHECK_SKILL_DIR` 或 `$LIT_SKILL_DIR` 为空，中止（先对同级技能调用 `SkillLoad`）。

输入契约：
- `$OUTLINE` 必须是 Stage 3 经 `save_outline.py` 规范化后的 `outline.json`，包含顶层 `outline` 数组。每个可写顶层条目必须有 `index`、`title`、`description`、`core_claim`、`length_target`、`paper_ids` 和 `key_papers`。
- `$PAPERS` 必须是 Stage 2 经 `bibliography_library.py insert` 规范化后的 `papers.json`。每条可引用论文必须有 `bib_key`；正文只能通过 `outline.json` 中的 `paper_ids` / `key_papers` 引用这些 key。
- `papers.json` 可来自 browser-use 候选经 `discover_and_resolve_papers.py` 补全后的结果；本技能只依赖规范字段 `bib_key`、`title`、`authors`、`year`、`journal`、`doi`、`url`、`abstract`，不依赖 PaperSearch/PaperSurveyToFile 专有字段。
- 如果 `outline.json` 的 `paper_ids` / `key_papers` 引用了 `$PAPERS` 中不存在的 key，`build-write-context` 会过滤掉这些 key；如果过滤后某个正文 section 没有可用 key，报告警告并优先回到 Stage 3 重新分配论文，而不是在正文中发明引用。

另外从 `outline.json` 读取：
- `expected_figures_total`（缺失时默认 0）
- `expected_tables_total`（缺失时默认 0）

如果 `expected_figures_total > 0`，创建 `$WORK/figures/` 目录：

```bash
mkdir -p "$WORK/figures"
```

## Step 2 — 加载输入

在这里**每个源文件只读取一次**。后续步骤不要再次 Read `outline.json`，只引用内存内容：

- `writing_constraints.json` → 完整加载
- `outline.json` → 完整加载；选择可写顶层条目（排除 `subsection`、`subsubsection`），按整数 `index` 排序（**只读取一次**）
- 不要直接 `Read` 原始 `papers.json`。Step 4 通过 `bibliography_library.py build-write-context` 构建紧凑论文上下文。

## Step 3 — 构建章节规格

对按 index 排序的每个可写顶层条目，提取：

- `section_title`、`section_description`
- 检测 section 类型：introduction（zh: 引言/前言/绪论；en: introduction）、conclusion（zh: 结论/总结/结语/结束语；en: conclusion/conclusions）或 regular
- 从 outline 条目获取 `core_claim` — 缺失或为空则中止
- `length_target`，优先级：
  1. `writing_constraints.section_length_policy.overrides.<type>`
  2. `writing_constraints.section_length_policy.default_min`
  3. 硬默认：zh `1200 chars` / en `900 words`
- 从 outline 条目获取 `paper_ids`；将 `[]` 转成 `"all"` 并给出警告
- 从 outline 条目获取 `planned_figures`（可缺失或为空列表）— `{"type": "<type>"}` 对象列表，表示本节要插入哪些图类型
- 从 outline 条目获取 `planned_tables`（可缺失或为空列表）— `{"type": "<type>"}` 对象列表，表示本节要插入哪些表类型
- `parent_index == index` 的子 subsection 条目，按整数 `index` 排序

## Step 4 — 构建紧凑论文参考

用 literature-library 脚本构建论文上下文；不要在 LLM 上下文中手动过滤或展开 `papers.json`：

```bash
python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" build-write-context \
  --library "$PAPERS" \
  --outline "$OUTLINE" \
  --output "$WORK/.cache/write_paper_context.txt" \
  --abstract-chars 400 \
  --snippet-limit 30 \
  --index-limit 200 \
  --snippet-source key-papers
```

然后只读取一次 `$WORK/.cache/write_paper_context.txt`。文件形状如下：

```text
### Global paper index
[bib_key_a] Title · Year · Venue
[bib_key_b] Title · Year · Venue

### Section citation map
<section_title>: allowed_keys=[k1,k2,...]; key_papers=[k1,k3]

### Key paper evidence snippets
[bib_key_a] <abstract first 400 chars>
```

规则：

- 每篇论文在 `Global paper index` 中最多出现一次。
- Section entries 只列 citation keys；不要对每个 section 重复 title/venue/abstract。
- Abstract snippets 只为选定 keys 出现，并且每个 key 只出现一次。默认最多 30 个 `key_papers`，每个 400 字符。
- 如果某 section 的 `paper_ids` 是 `"all"`，在 section map 中列出全部 allowed keys，但不要重复 global paper index 或 snippets。
- 如果 `papers.json` 缺失，使用 `(no papers available)`。

## Step 5 — 构建语言与引用规则块

对于 `en`：

```text
## Output language (STRICT)
- Write the entire document in **English** only.
- Section/subsection headings in \section{}/\subsection{} must be in English.
- Abstract and keywords in English.
- If the model emits hidden reasoning/thinking content, keep that reasoning in English.

## Quotation marks (**STRICT** — en)
- Use LaTeX curly quotation marks: ``text'' for double quotes, `text' for single quotes.
- Do NOT use ASCII straight double-quotes " " or straight single-quotes ' ' in prose.

## Dash usage (**STRICT** — en)
- Do NOT use em dashes, including both Unicode `—` and LaTeX `--` or `---`, in academic prose.
- Prefer commas, semicolons, colons, parentheses, or separate sentences when clarifying relationships.
- Do not use `--` or `---` as a transition, parenthetical, or emphasis device.

## Citation format (STRICT)
- Always use \cite{key} inline; the bibliography backend handles rendering.
- Use ONLY the \cite{} keys listed in the section citation map.
- Do NOT hand-write bibliography entries, footnotes, numbered references, or author-year citation strings.
- Abstract must NOT contain \cite{} citations.
```

对于 `zh`：

```text
## Output language (STRICT)
- Write the entire document in **Simplified Chinese**.
- Technical terms, proper nouns, paper titles, and standard abbreviations may remain in English.
- Section/subsection headings in \section{}/\subsection{} must be in Chinese.
- Abstract (摘要) and keywords (关键词) in Simplified Chinese.
- If the model emits hidden reasoning/thinking content, use Simplified Chinese.

## Quotation marks (**STRICT** — zh)
- Use Chinese curly quotation marks “ ” for emphasis or quoting in Chinese prose.
- Do NOT use ASCII straight double-quotes " " for Chinese text.
- For English technical terms that require quoting, use \textit{} for italics instead of any quotation marks.

## Dash usage (**STRICT** — zh)
- 不要使用破折号（——、—）表达转折、补充说明或强调。
- 优先使用逗号、分号、冒号、括号，或拆成两个句子来表达解释、递进和转折关系。
- 避免连续多段或多句反复出现破折号；除专有名词或原文题名不可改写外，不使用破折号。

## Citation format (STRICT) 
- You MUST use \cite{key} inline; the bibliography backend handles rendering.
- FORBIDDEN: "Fehr and Schmidt (1999)", "Rabin 在 1993 年提出", or any other inline author-year string. 
- Use ONLY the \cite{} keys listed in the section citation map.
- Do NOT hand-write bibliography entries, footnotes, numbered references, or author-year citation strings.
- 摘要 must NOT contain \cite{} citations.
```

## Step 6 — 准备具体素材

写作前，从已加载文件中组装具体素材。使用 constraints、outline 和论文库中的已解析值；最终 `mainbody.tex` 中不得包含未解析章节名、缺失 citation-key 标记或占位文本。

创建编号 section block，列出所有 sections。每个条目必须使用 `outline.json` 的实际值，并包含 LaTeX section heading、description、按顺序排列的 subsection titles 或 `(none)`、core claim、length target 和 section type。

创建 Step 4 的紧凑论文上下文：一个 global paper index、一个 section citation map、一个去重后的 key-paper evidence snippet block。

从 `writing_constraints.json` 提取 focus points、extra requirements 和 venue style notes；写作时使用其具体值。

## Step 7 — 写作

**始终要求完整的 mainbody.tex。** 不得输出占位符或部分文档。

一次性将完整综述正文写成单一统一 LaTeX 文档；不要把 sections 当作彼此独立的单元。使用上面解析出的 section、paper 和 constraint 信息，但只输出最终 LaTeX 正文体。

### Mainbody 边界（严格）

`mainbody.tex` 不是独立 LaTeX 文档。它是正文片段，由导出脚本组装成最终交付物。

导出脚本会添加：
- `\documentclass{...}`
- `natbib` / `apacite` 等引用包
- `\bibliographystyle{...}`
- `\begin{document}` 和 `\end{document}`
- 当 `references.bib` 存在时添加 `\bibliography{references}`

因此，`mainbody.tex` **不得**包含：
- `\documentclass`
- `\usepackage`
- `\begin{document}` 或 `\end{document}`
- `\bibliographystyle{...}`
- `\bibliography{...}`
- `\begin{thebibliography}` 或 `\end{thebibliography}`
- `\bibitem`
- 手写的 References / Bibliography / 参考文献 section
- 原始 BibTeX 条目或格式化参考文献列表条目
- 任何 TikZ 或 PGFPlots 内容（`\begin{tikzpicture}`、`\begin{axis}`、`\usetikzlibrary` 等）— 图像只能通过外部图片工具生成

只使用内联 `\cite{key}` 引用。最终导出期间，bibliography backend 会从 `references.bib` 解析这些 keys。

遵循以下要求：

1. 严格按顺序输出这些元素：
   - `\begin{abstract}...\end{abstract}`（zh: 摘要，150-250 words；en: Abstract，150-250 words；不含 `\cite{}` 引用；不使用 `\autoref{}` 或 `\ref{}` 指向图表，摘要不得引用 floats）
   - `\keywords{...}`（zh: 5-8 个关键词，分号 `；` 分隔；en: 5-8 个 Keywords，逗号分隔，Title Case）
   - `\maketitle`
   - `\newpage`
   - `\tableofcontents`
   - `\newpage`
   - 按 section block 顺序输出每个 `\section{}`
2. 不要输出文档 wrapper、package 声明、bibliography 命令、bibliography 环境、`\bibitem`、参考文献列表 section 或 Markdown fences。只输出从 `\begin{abstract}` 开始，到最后一个综述 section 后结束的正文片段。
   **例外：** 当计划有图时，允许且必须使用 `% FIGURE id=xxx prompt="..."` 注释。
3. 使用已加载输入中的 survey title 和 core topic。
4. 遵循 Step 5 选择的语言和引用规则。
5. 按 Step 6 编号 section block 中列出的顺序撰写每个 section。
6. 只使用当前 section 在 Step 4 citation map 中允许的 `\cite{}` keys；不要发明 citation keys。
7. 遵循这些写作要求：
   - **One-pass narrative：** 写作前规划完整叙事弧。每个 section 从其 core_claim 出发承担不同论证角色；同一概念不要在多个 section 反复解释。
   - **Coverage：** 覆盖每个 focus point 和 extra requirement。不要把具体机制、方法或数据集合并成宽泛标签而导致细节消失。
   - **Synthesis：** 比较不同论文之间的机制、边界条件和权衡。按主题或论点组织，而不是每句话列一篇论文。
   - **Evidence hierarchy：** 区分综述层共识、原始研究、理论工作和实验证据。不要让综述引用承载具体定量结论。
   - **No outline metadata leakage：** `outline.json` 中 description 末尾的 `Evidence source` / `证据来源` 标签只是内部写作提示，不得出现在 `mainbody.tex` 正文、摘要、标题、表格或图注中。需要体现证据层级时，用自然学术表述，例如“原始实验研究显示……”“现有综述倾向认为……”，并配合恰当引用。
   - **Quantitative claims：** 指明指标、条件、变化方向和引用。比较冲突数值或解释差异来源。
   - **Hedged language：** 对不确定结论使用 "suggests"、"indicates"、"evidence is mixed" 等谨慎表达。
   - **Citation policy：** 每个非综合性、非常识性陈述都需要 `\cite{}`。关于综述自身组织结构的句子不需要。
   - **Academic register：** 无宣传语言，无 AI 风格空泛过渡或元评论（“综上所述”“本节介绍了”“In summary, this section has shown…”）。每句话都应携带信息。
   - **Dash discipline：** 正文中不要使用 em dash，包括 LaTeX `--` 或 `---`，以及中文破折号——。用标点或句式改写强调、同位解释和松散过渡。
   - **Abstract：** 摘要应忠实总结实际写出的正文，而不是泛泛描述主题。摘要中不使用 `\cite{}`；不使用 `\autoref{}` 或 `\ref{}` 指向图表；不要声称分析了具体数量论文（如“基于160篇文献”），因为摘要写作时引用尚未最终确定，文献库计数可能不同。使用定性表述。
   - **Keywords：** 反映正文实际范围。zh：分号 `；` 分隔；en：逗号分隔，Title Case。
   - **Length：** 每个 section 必须达到其长度目标，通过更深入覆盖扩展，而不是填充废话。
   - **Introduction：** 说明综述目标和论文语料基础；不要发明检索统计。
   - **Conclusion：** 主论点综合 -> 承认局限 -> 从已识别 gaps 提出具体未来方向。不要使用 `\cite{}`。
8. 遵循 `writing_constraints.json` 中的具体 focus points、extra requirements 和 venue style notes。

9. **表格规则**（当 `expected_tables_total > 0` 时适用）：按每个 section outline 条目的 `planned_tables` 列表插入表格。每个 `planned_tables` 条目，在该 section 自然位置写一个完整表格环境。
   - 直接使用 `planned_tables` 中的 `type`（不要重新选择）。加载 `surveymaster-table-types`，根据该 type 模板和 section `core_claim` 构建列结构。有效类型：`performance_comparison`、`classification_comparison`、`challenge_strategy_matrix`。
   - 通用非经济学表格只使用 `\toprule`、`\midrule`、`\bottomrule`；不要使用 `\hline`。
   - 对使用 economics empirical-style template 的综述，必须采用 `surveymaster-table-types` 中的 Economics Journal Table Style：上下粗线、内部细横线、纵向列分隔线、紧凑黑白版式和必要表注。该经济学 override 优先于通用 booktabs-only 规则。
   - 不使用 `\multicolumn` 或 `\multirow`。
   - Label 格式：`tab:<snake_case_id>`。周围正文必须至少有一次 `\autoref{tab:<id>}` 引用。
   - **ID 一致性（严格）：** `\label{tab:<id>}` 和 `\autoref{tab:<id>}` 中的 `<id>` 必须完全一致。只分配一次 id，然后精确复制；任何变体都会造成所有导出格式中的交叉引用断裂。
   - **表格讨论融合（严格）：** 不要创建只为介绍表格而存在的独立单句段落。`\autoref{...}` 引用应融入解释表格内容的分析段落，而不是只宣布其存在。

     包含 `\autoref{...}` 的段落应解释：
     1. 表格总结了什么信息；
     2. 最重要的模式、相似性、差异或趋势；
     3. 支持当前 section 论点的结论或洞察。

     不要假定读者会自己理解表格。周围正文应引导读者看到关键 takeaway。

   - **不要逐行复述表格：** 避免在正文中描述每一行或每个单元格。总结表格体现出的最重要模式、对比和结论。
   - **Caption 格式：** 只写短名词短语（zh: `不同方法性能对比`；en: `Performance comparison of different methods`）。不要在 caption 文本中包含标签编号，LaTeX 会自动插入。Caption 不写完整句子或详细解释。
   - **文内引用格式（严格）：**
     - 只使用 `\autoref{tab:<id>}` 作为完整表格引用；不要在它前面再手写 `表`、`表格`、`Table` 或 `table`。`\autoref{}` 会自动渲染为“表 1”或“Table 1”，手写前缀会导致导出中出现“表 表 1”或“Table Table 1”。
     - zh 合法：`如\autoref{tab:id}所示，`、`\autoref{tab:id}汇总了……`、`……（见\autoref{tab:id}）`
     - en 合法：`As shown in \autoref{tab:id},`、`\autoref{tab:id} summarizes ...`、`... (see \autoref{tab:id}).`
     - zh 禁止：下表、上表、如下表所示、表 \autoref{tab:id}、表格 \autoref{tab:id}
     - en 禁止：the table below, the above table, as shown in the following table, Table \autoref{tab:id}

   ```latex
   \begin{table}[H]
     \centering
     \caption{<caption>\label{tab:<id>}}
     \begin{tabular}{<col-spec>}
       \toprule
       <header row> \\
       \midrule
       <data rows, \cite{} where applicable> \\
       \bottomrule
     \end{tabular}
   \end{table}
   ```

10. **图片规则**（当 `expected_figures_total > 0` 时适用）：按每个 section outline 条目的 `planned_figures` 列表插入图片。每个 `planned_figures` 条目写一个不含 `\includegraphics` 的 `\begin{figure}` 环境，并在紧邻上一行写 `% FIGURE` 注释。
    - `id` 必须在全文唯一；格式：`fig_<snake_case>`。
    - **ID 一致性（严格）：** 一张图只使用一个 `id` 字符串。该字符串必须在四处完全一致：
      1. `% FIGURE id=<id> prompt="..."` 注释
      2. `\caption{}` 内的 `\label{fig:<id>}`
      3. 周围正文中的 `\autoref{fig:<id>}`
      4. `image_gen` 调用写入的本地文件 `figures/<id>.png`
      任何不匹配都会导致导出脚本失败。只分配一次 id，精确复制。
    - Label 格式：`fig:<snake_case>`。周围正文必须至少有一个 `\autoref{fig:<id>}` 引用。
    - 直接使用 `planned_figures` 中的 `type`（不要重新选择）。加载 `surveymaster-figure-types`，用该 type 模板和 section `core_claim` 构建 prompt。
    - 写任何 `% FIGURE` prompt 前，先从 `writing_constraints.json` 读取 `figure_color_policy`。如果它是 `black_and_grayscale`，把 `surveymaster-figure-types` 中的 economics/grayscale override 追加到每个 prompt：plain black-and-white line diagram, white background, black/gray boxes and arrows, no gradients, no saturated colors, no decorative icons, no 3D effects, no shadows, and no pictorial ornamentation。如果它是 `low_saturation_color` 或缺失，使用普通低饱和学术彩色配色。不要因为 economics template、经济学相关关键词或上下文里出现的经济学文件而自行推断为灰阶。
    - **Figure language：** 默认使用**英文** prompt 模板。只有当用户在当前会话中明确要求中文图内标签时，才切换到 zh 模板。
    - **融合讨论（严格）：** 不要创建只为介绍 figure/table 的独立单句段落。`\autoref{...}` 引用应尽量融入讨论同一概念、方法、结果或比较的实质段落。周围正文必须至少包含一次 `\autoref{fig:<id>}`。

      包含 `\autoref{...}` 的段落不应只命名图/表，还应解释：
      1. 图/表展示了什么；
      2. 读者应注意的关键模式、结构、过程或比较；
      3. 它如何支持当前 section 的论点。

    - **Caption 格式：** 只写短名词短语（zh: `MXene典型合成流程`；en: `Typical synthesis process of MXene`）。不要在 caption 文本中包含标签编号。不要写完整句子或详细解释。
    - **文内引用格式（严格）：**
      - 只使用 `\autoref{fig:<id>}` 作为完整图片引用；不要在它前面再手写 `图`、`Figure` 或 `figure`。`\autoref{}` 会自动渲染为“图 1”或“Figure 1”，手写前缀会导致导出中出现“图 图 1”或“Figure Figure 1”。
      - zh 合法：`如\autoref{fig:id}所示，`、`\autoref{fig:id}展示了……`、`……（\autoref{fig:id}）`
      - en 合法：`As shown in \autoref{fig:id},`、`\autoref{fig:id} illustrates ...`、`... (\autoref{fig:id}).`
      - zh 禁止：下图、上图、如下图所示、图 \autoref{fig:id}
      - en 禁止：the figure below, the above figure, as shown in the following figure, Figure \autoref{fig:id}

11. **图表位置规则（严格）：**
    1. **Section ownership：** 每个 figure/table 只属于一个 section。环境必须放在引入和讨论它的 `\section{}` 内。不要放进后续 section 或 subsection。
    2. **Proximity：** 尽量靠近首次引用它的段落。优先顺序：引用段落之后（同页）-> 同 section 后续位置（同页）-> 当前 section 末尾 -> 下一页但在下一 section 前。不要把所有图表都推迟到 section 末尾。
    3. **Reference-first（严格）：** figure/table 环境应紧跟包含首次 `\autoref{}` 引用的段落之后。不要因为 section 有多个 subsections 就把图拖到最后。
    4. **No consecutive floats：** 两个 figure/table 环境之间必须至少有一段正文，不要连续堆放。
    5. **Single-paragraph section：** 将 float 附在该段落末尾。
    6. **永远不要放在所属 `\section{}` 标题之前：** float 必须出现在所属 section 标题之后，并且不早于该 section 第二段。即使只提前一行也是硬违规。
    7. **禁止文档级 overview figure：** 不要把任何 figure 放在 `\tableofcontents` 和第一个 `\section{}` 之间。系统中不存在“整篇综述架构图”这种文档级图；每张图都必须属于具体 section。
    8. **冲突优先级：** Section ownership 第一；Proximity 第二；Reading continuity 第三；Page utilization 第四；Whitespace minimization 最后。

    ```latex
    % FIGURE id=fig_<id> prompt="<generated prompt>"
    \begin{figure}[H]
      \centering
      \caption{<caption>\label{fig:<id>}}
    \end{figure}
    ```

    **Prompt 引号约束（严格）：** `prompt="..."` 的值由正则解析，`"` 会被视为结束分隔符。不要在 prompt 字符串内部使用直双引号 `"`。内部需要引用术语时使用单引号 `'`，例如 `prompt="show 'key component' structure"`。技术上支持转义引号 `\"`，但不建议使用。

对于 `--mode rewrite`，还要使用现有正文作为素材：

1. 从 `<output-dir>/mainbody.tex` 加载完整当前正文。
2. 按以下规则重写：
   - 原样保留所有 `\section{}` 标题和现有 subsection 结构。
   - 不引入上方 papers block 中不存在的 `\cite{}` keys。
   - 重写 prose，改善证据综合，修复 hedging，并处理指出的问题。
   - 输出从 `\begin{abstract}` 开始的完整文档。

rewrite 模式下不要摘要或摘录已有正文；必须基于完整加载文件重写。

## Step 8 — 写入并生成图片（单次 LLM 响应）

在**一个响应**中同时发起以下工具调用：

1. `Write` -> `$WORK/.cache/scratch/mainbody.tex`，内容为 Step 7 的完整 LaTeX 输出。
2. 对写入文本中的每一行 `% FIGURE id=<id> prompt="<prompt>"`（如果 `expected_figures_total == 0` 则跳过）：调用 agent 的 `image_gen` 工具，用该 prompt 生成图片并保存到 `$WORK/figures/<id>.png`。

本步骤所有工具调用必须一起发起，不要等待 `Write` 或某个 `image_gen` 调用完成后再发起其他调用。

如果任何 `image_gen` 调用失败：等待所有调用结束后停止，报告失败的 `id` 和错误，不进入 Step 9。

## Step 9 — 验证并提升为正式文件

运行修复 + 验证，成功后提升到最终位置：

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" repair-structure \
  --mainbody "$WORK/.cache/scratch/mainbody.tex" \
  --lang "$SURVEY_LANG" \
  --outline "$OUTLINE" \
  --report "$WORK/.cache/write_section_structure.txt" && \
cp "$WORK/.cache/scratch/mainbody.tex" "$WORK/mainbody.tex" && \
rm -f "$WORK/.cache/scratch/mainbody.tex"
```

`repair-structure` 是 `mainbody.tex` 提升为正式文件的唯一门禁。它可以执行确定性修复，包括当只有一个未闭合的 `\begin{abstract}`，且下一个边界（`\keywords{}`、`\maketitle`、`\tableofcontents` 或 `\section{}`）明确时，自动补入 `\end{abstract}`。如果它仍报告 `MISSING_ABSTRACT`、`ABSTRACT_NOT_CLOSED` 或 `BEGIN_END_MISMATCH`，不要把 scratch 文件复制到 `$WORK/mainbody.tex`，不要进入 finalize/export，也不要只手工修改报告。必须从 Step 8 重新生成完整正文，或修复 scratch TeX，直到该命令成功退出。

如果 `&&` 链在 `repair-structure` 失败，保留 scratch 文件，读取 `$WORK/.cache/write_section_structure.txt`，报告确切失败项并停止。复制失败时，保留 scratch 文件供检查。

## Step 10 — 报告

运行 figures-tables 检查，发现数量不匹配和未引用 floats：

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" figures-tables \
  --mainbody "$WORK/mainbody.tex" \
  --outline "$OUTLINE" \
  --report "$WORK/.cache/figures_tables_check.txt"
```

读取 `$WORK/.cache/figures_tables_check.txt`。如果命令非零退出，立即停止：保留 `mainbody.tex`，报告具体的 `ERROR_MISSING`、`UNREFERENCED_FIGURE` 或 `UNREFERENCED_TABLE` 行，并先修复相关 section 后再进入定稿/导出。不要把这些问题降级为 warning；缺少 `\autoref{}` 会导致后续导出误判图表数量。

报告：
- mode（`draft` / `rewrite`）
- 所有 sections 使用的总论文数
- section 数量
- table 数量（`mainbody.tex` 中实际 `\begin{table}`）与 `expected_tables_total` 对比
- figure 数量（实际 `% FIGURE` 注释）与 `expected_figures_total` 对比，以及生成状态
- figures-tables 检查发现的未引用 figures/tables（如有）
- 输出文件：`mainbody.tex`、`figures/`（如适用）
- 非致命条件警告（缺少 `papers.json`、将 `[]` paper assignments 转成 `"all"` 等）

提交报告后，调用平台 `FinalAnswer` 工具并设置 `status: "completed"`，正确结束本轮。不要省略，否则 agent 可能循环或无法把控制权交还用户。
