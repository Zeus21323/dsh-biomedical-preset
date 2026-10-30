---
name: surveymaster-finalize
version: 0.2.0
description: 协调 SurveyMaster 最终化流程，包括引用审计、BibTeX 元数据解析、确定性检查与紧凑摘要、一次 LLM 修复、统一导出和持久化。
argument-hint: "--survey-dir <work-dir> [--language zh|en]"
---

## 阶段契约

阶段：5 — 检查、修复、导出与持久化。

加载者：SurveyMaster 编排器在全文正文起草完成后加载；或在 `mainbody.tex` 因任何原因发生变化时加载，包括内容编辑、风格修复、约束更新、视觉资产变化或语言切换。任何写入 `mainbody.tex` 的操作都会使已有交付物过期；在用户收到任何更新交付物前，`surveymaster-finalize` 是强制 gate。

必需输入：
- `$WORK/writing_constraints.json`
- `$WORK/papers.json`
- `$WORK/outline.json`
- `$WORK/mainbody.tex`（由 Stage 4 `surveymaster-write-section` 生成）

输入契约：
- `$WORK/mainbody.tex` 必须是 Stage 4 生成的正文片段，从 `\begin{abstract}` 开始，不包含 `\documentclass`、`\begin{document}`、`\bibliography{}` 或手写参考文献。
- `$WORK/papers.json` 必须是 Stage 2 经 `bibliography_library.py insert` 规范化后的文献库；可以来自 browser-use 候选经 `discover_and_resolve_papers.py` 补全后的结果。每条被引用论文必须有 `bib_key`、`title`、`authors`、`year` 和出版场所（`journal` / `booktitle` / `venue` 等）。
- `mainbody.tex` 中所有 `\cite{key}` 必须引用 `$WORK/papers.json` 中存在的 `bib_key`。不存在的 key 是幻觉引用，禁止通过临时向 `papers.json` 添加记录来掩盖；应在 Step 5-B 修复 pass 中删除或改写。
- `$WORK/outline.json` 必须是 Stage 3 经 `save_outline.py` 规范化后的大纲，用于结构检查和修复 pass 上下文。
- `$WORK/writing_constraints.json` 继续作为语言、引用格式、focus points、额外要求和期刊风格约束的事实源。

输出：
- 更新后的 `$WORK/mainbody.tex`（经过 LLM 修复）
- `$WORK/references.bib`
- 最终 Markdown、DOCX、TeX 源文件和 bibliography 交付物；PDF 默认尝试生成，但作为可选交付物

完成条件：
- 确定性检查已完成；`$CACHE/check_summary.txt` 已写入。
- LLM 已在一次 pass 中修复所有问题。
- 统一导出已尝试所有必需格式。
- 编排器已保存或更新用户可见交付物。

**Step 5-B（LLM 修复 pass）是强制步骤，永远不得跳过。**
干净或很少问题的 `check_summary.txt` 只说明草稿机械上有效，并不表示已经完成语义润色。只有在 Step 5-B 完成，并且 `mainbody_fixed.tex` 已提升为 `mainbody.tex` 后，才能进入 Step 5-C。禁止从 Step 5-A 直接跳到 Step 5-C。

可以加载其他技能：
- `surveymaster-literature-library`
- `surveymaster-check-and-merge`
- `surveymaster-write-section`
- `surveymaster-refine-section`（仅导出后局部润色）
- `surveymaster-export`

这些技能按需懒加载，在需要它们的步骤前立即加载。

## 文件写入策略

所有文件写入都使用 `Write`（创建/覆盖）或 `Edit`（补丁）。禁止使用 shell heredoc，因为它们会破坏 LaTeX 和 JSON 中的反斜杠。

## 用户交互契约

以下是**强制**用户交互检查点。每个检查点都必须停止并等待用户输入，不能自动越过。

1. **元数据差异（Step 5-A Phase 2）：** 当 `--verify-metadata` 报告任何 TITLE_MISMATCH、YEAR_MISMATCH、VENUE_MISMATCH 或 AUTHOR_MISMATCH 时，展示每项差异，并在修改任何记录前**等待用户指示**。
2. **大纲确认（导出后修订的大纲变更）：** 在任何大纲编辑后运行 `surveymaster-write-section` 前，将完整更新大纲渲染为编号 section 列表（index · title — core_claim），并**要求用户明确确认**。不能基于本会话中用户未批准的大纲重写 sections。
3. **重复 bib keys（Step 5-A Phase 3）：** 重复 keys 不能自动解决。展示重复项，并**等待用户修复 `references.bib`** 后再继续。
4. **全部导出失败（Step 5-C）：** 如果所有请求格式都失败，停止并向用户报告，再考虑持久化。

不要因为信息性消息、字数统计或仅 WARN 项而阻塞。

## 交付物 Gate（严格）

`surveymaster-finalize` 是产生或更新交付物（`.docx`、`.tex`，以及可选 `.pdf`）的**唯一路径**。以下任意情况发生后，必须从 Step 5-A 开始完整运行：

- `surveymaster-write-section` 完成（draft 或 rewrite 模式）
- `surveymaster-refine-section` 完成
- 任何对 `mainbody.tex` 的直接编辑（内联修复、视觉资产插入/移除、图表内容变化）
- 任何影响内容的约束变化（语言、引用格式、期刊风格、长度目标）
- 任何导致 cite-key 或元数据更新的论文/文献库变化

不要把最近一次 `mainbody.tex` 写入之前产生的 `.docx`、`.tex` 或 `.pdf` 作为当前输出展示给用户。过期交付物绝不能作为当前结果分享。

---

## 强制子步骤执行顺序

下面每项都是硬 gate。前一项未成功退出前，不得进入下一项。此列表是权威执行顺序，可用于确认没有跳步。

| # | Step | 输出 | 跳过风险 |
|---|---|---|---|
| 1 | 5-A Ph1 `cites` audit | `$CACHE/cites_audit.txt` | |
| 2 | 5-A Ph2 steps 1-3 初始 `export-bib` | `$WORK/references.bib` | |
| 3 | **5-A Ph2 step 4 `--verify-metadata`** | `$METADATA_REPORT` | ⚠ 常被跳过 |
| 4 | 5-A Ph2 step 5 最终 `export-bib` 同步 | `$WORK/references.bib` | |
| 5 | 5-A Ph3 `survey_checks.py all` | `$CACHE/check_summary.txt` | |
| 6 | 5-B LLM 修复 pass | `$CACHE/scratch/mainbody_fixed.tex` | |
| 7 | **5-B `repair-structure` 验证** | 验证修复 | ⚠ 常被跳过 |
| 8 | **5-B 重建 Bibliography** | 重新同步 `$WORK/references.bib` | ⚠ 省略会导致 DOCX/TeX/PDF 引用过期 |
| 9 | 5-C `export_all.py` | DOCX / TeX 必需；PDF 默认尝试且可选 | |
| 10 | **5-C `final_cites.txt`**（仅 bib，无 `--library`） | `$CACHE/final_cites.txt` | ⚠ 常被跳过 |
| 11 | 5-D 持久化交付物 | 已保存文件 | |

---

## Step 5-A — 确定性检查 Pass

在此步骤前加载 `surveymaster-literature-library` 和 `surveymaster-check-and-merge`。

`$WORK` 是综述输出目录；`$CACHE` 是 `$WORK/.cache/`。

在 Step 5-A 顶部只解析一次路径，并在所有 phases 中复用。

**前置要求：** 在下面 Bash 块之前，先 `SkillLoad` `surveymaster-check-and-merge` 和 `surveymaster-literature-library`。

```bash
CACHE="$WORK/.cache"
SURVEY_LANG="<language-from---language-argument>"
CHECK_SKILL_DIR="<skillDir from SkillLoad(surveymaster-check-and-merge)>"
LIT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-literature-library)>"
```

如果任一目录变量为空，或预期脚本缺失，立即中止。

`SURVEY_LANG` 必须由编排器根据当前用户输入（`--language zh|en`）提供。不要从 `writing_constraints.json` 或 `outline.json` 推断。如果参数缺失或不是 `zh` / `en`，停止并要求编排器用显式语言重新加载 `surveymaster-finalize`。

### Phase 1 — 引用审计（首先运行；输出供 Phase 2 使用）

只针对 `mainbody.tex` 和 `papers.json` 运行 `cites`（此时不传 `--bib`，因为 `references.bib` 还不存在）。这是 Step 5-A 中唯一独立引用审计；后续检查必须复用 `$CACHE/cites_audit.txt`，而不是再次运行 `cites`：

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" cites \
  --extra-tex "$WORK/mainbody.tex" \
  --library "$WORK/papers.json" \
  --report-unused \
  --report "$CACHE/cites_audit.txt" \
  --warn-only
```

读取 `$CACHE/cites_audit.txt`，提取：
- **`used_keys`**：`used_cite_keys=[...]` 行，只写入 report 文件（不在 stdout）。将其按 Python list literal 解析，得到 `mainbody.tex` 中确认出现的 keys。
- **`hallucinated_keys`**：`missing_defined_keys=[...]`，即 tex 中有但 `papers.json` 中没有的 `\cite{}` keys。这些是幻觉引用。
- **`uncited_library_keys`**：`unused_library_keys=[...]`，文献库中从未被引用的论文。这只是覆盖信号，不强制把所有库论文塞进草稿。

此处不要从 tex 中删除幻觉 keys。将它们交给 Step 5-B 的 LLM 删除。
不要查找或添加幻觉 keys 到 `papers.json`，否则会绕过引用有效性链条。

### Phase 2 — Bib 元数据解析 + 最终导出（使用 Phase 1 的 `used_keys`）

只解析 `used_keys` 中条目的元数据。不要为未引用的 library papers 拉取元数据。

1. 针对 `mainbody.tex` 中实际出现的 citations 运行 BibTeX 导出。脚本会从 TeX 源提取 cite keys，并自动排除未引用的 library records，因此调用方不需要构建或传入 `--keys`。将紧凑诊断捕获到 shell 变量，而不是文件。`--diagnostics-stdout` 让 WARN/INFO 行可管道化，真正命令错误仍走 stderr：
   ```bash
   EXPORT_BIB_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   ```
2. 从 `$EXPORT_BIB_DIAGNOSTICS` 收集每条 ERROR 记录（缺 title、author、venue 或 year）。由于导出由 `--tex-file` 限定，这些记录已经只限于草稿中被引用的论文。并行派发 DOI/title 查找。
3. 所有查找返回后，重新插入更新后的元数据，并再次运行一次导出：
   ```bash
   EXPORT_BIB_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   ```
   只有出现新的 ERROR 记录时才重复。
4. **硬 gate — `--verify-metadata`（强制；不要跳过）。**
   在一个 stdout pipeline 中解析缺失 volume/pages 并验证元数据一致性。不要写单独 resolver report 文件：
   ```bash
   METADATA_REPORT="$(
     printf '%s\n' "$EXPORT_BIB_DIAGNOSTICS" | \
       python3 "$LIT_SKILL_DIR/scripts/resolve_volume_pages.py" \
         --library "$WORK/papers.json" \
         --verify-metadata \
        --verify-targets-only \
         --report-stream stdout || true
   )"
   ```
   这会针对 stdin 中的 WARN keys 解析 volume/pages，并对这些被引用记录检查 TITLE_MISMATCH / YEAR_MISMATCH / VENUE_MISMATCH / AUTHOR_MISMATCH。

   **读取输出：**
   - 输出中有 `RESOLVE_SKIPPED` / `NO_MISMATCHES`：说明没有 WARN keys 输入，也就是没有 volume/pages 缺口。这是正常退出，立即进入 step 5。不要换参数重试。
   - 没有 MISMATCH 行：元数据一致，立即继续。
   - 存在 MISMATCH 行：**纳入 `$CACHE/check_summary.txt`，向用户展示每个差异，并等待指示**后再修改。

   收集 `$METADATA_REPORT` 后，还要额外找出 `used_keys` 中在 `papers.json` 记录里没有 `doi` 字段（null 或空）的条目。这些条目无法由 `--verify-metadata` 验证，属于低置信引用。在 `$METADATA_REPORT` 中追加：
   ```text
   NO_DOI_ENTRIES: [key1, key2, ...]  (cited but unverifiable — no DOI in papers.json)
   ```
   与 MISMATCH 警告一起展示给用户。不要仅因缺 DOI 阻塞导出，但用户必须在继续前看到该列表。
5. 因 Step 4 可能修补了 `papers.json`，再精确运行一次 BibTeX 导出，让 `$WORK/references.bib` 与已解析元数据同步：
   ```bash
   FINAL_EXPORT_DIAGNOSTICS="$(
     python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
       --library "$WORK/papers.json" --output "$WORK/references.bib" \
       --tex-file "$WORK/mainbody.tex" \
       --warn-limit 10 --diagnostics-stdout
   )"
   METADATA_REPORT="$METADATA_REPORT
   $FINAL_EXPORT_DIAGNOSTICS"
   ```

### Phase 3 — 完整检查 Pass（在 `references.bib` 存在后运行）

运行其余完整检查套件。跳过 `cites`，因为 Phase 1 已生成 `$CACHE/cites_audit.txt`；这样避免重复引用分析和 `used_cite_keys` 输出。在同一进程中构建 `$CACHE/check_summary.txt`，这样 LLM 不需要读取 `checks_full.txt` 或手写摘要：

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" all \
  --mainbody "$WORK/mainbody.tex" --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --extra-tex "$WORK/mainbody.tex" \
  --library "$WORK/papers.json" \
  --bib "$WORK/references.bib" \
  --skip-cites \
  --report "$CACHE/checks_full.txt" \
  --summary-output "$CACHE/check_summary.txt" \
  --cites-audit "$CACHE/cites_audit.txt" \
  --metadata-stdin \
  --report-only --compact \
  --warn-only <<< "$METADATA_REPORT"
```

这覆盖：structure（abstract/keywords/sections/required outline section titles/forbidden wrappers/`\begin{}\end{}` balance）、bib（duplicates/unescaped &）、doi、latex、words。Citation findings 来自 `$CACHE/cites_audit.txt`。

命令打印紧凑 `CHECK_RESULT ...` 和 `SUMMARY_RESULT ...` 行，并将 LLM 可读摘要写入 `$CACHE/check_summary.txt`。摘要文件不得包含原始 JSON blob、完整 `.bib` 文本或论文摘要。

**硬停止 — exit 21（E_BIB，重复 bib keys）：** 向用户展示重复项，等待 `references.bib` 被修复后再继续 Step 5-B。

正常路径不要创建 `$WORK/summary.json`。紧凑摘要文件是 Step 5-B 消费的唯一检查摘要产物。

---

## Step 5-B — 单次 LLM 修复 Pass

**硬 gate — 任何情况下都不要跳过。**
无论 check_summary 多干净，本步骤都强制执行。零问题的 check_summary 也仍需要本 pass 进行语义润色。没有写入 `$CACHE/scratch/mainbody_fixed.tex` 并提升为 `$WORK/mainbody.tex` 前，禁止进入 Step 5-C。

只读取以下两个文件：
- `$WORK/mainbody.tex` → `{current_mainbody}`
- `$CACHE/check_summary.txt` → `{check_summary}`

从已加载 JSON 构建辅助上下文（除非已在上下文中，否则不要重新读取大文件）：
- `$WORK/outline.json` → `{outlines_text}`：`N. <section_title> — <core_claim>`（按整数 index 排序）
- `$WORK/writing_constraints.json` → `{survey_title}`、`{focus_points}`、`{extra_requirements}`、`{venue_style_notes}`
- `$WORK/papers.json` → `{papers_text}`，只含紧凑子集：包括 `$CACHE/cites_audit.txt` 中的 cited keys，以及 `$CACHE/check_summary.txt` 中的 hallucinated keys（如有）。未引用 library papers 仅为信息，不要为了强行引用或报告而包含。
  每条记录只包含 `[bib_key] Title · Year · Venue`；只有当某 key 直接涉及 flagged issue 时，才包含 abstract excerpt。

不要把完整论文库或完整 abstracts 加载进 Step 5-B prompt。若特定 key 需要更多细节，只查询该 key。

发送一次 LLM pass，目标是修复所有 flagged issues，并对完整正文做一次学术质量润色。输出必须只包含从 `\begin{abstract}` 开始的修复后 LaTeX 正文，不包含文档 wrapper、package、bibliography 命令、`bibitem`、参考文献列表、原始 BibTeX 或 markdown fences。

修复目标包括但不限于：
- 修复结构、引用、语言、LaTeX 字符问题，并保留合法转义如 `\%`、`\_`、`\&`
- 删除 hallucinated cite keys
- 不强行引用未引用 library papers。`check_summary.txt` 里的
  `UNCITED LIBRARY PAPERS` 是纯信息项，不是待修复问题；不要把它描述成
  “需要修复”，也不要为了减少这个列表而硬塞引用
- 对元数据风险相关 claims 做弱化或限定
- 修复 `\begin{}` / `\end{}` 不匹配
- 图表数量不匹配时，不要在 Step 5-B 自动新增或删除
  `\begin{figure}` / `\begin{table}` 环境。新增图需要走视觉资产工作流：
  生成图片、插入环境、插入 `\autoref{}` 并同步 outline。若
  `check_summary` 显示 expected figure/table 数量大于实际数量，应停止在导出前
  报告需要视觉资产工作流处理，或在用户确认后调整 outline 的 expected_*_total
- 对已存在但未引用的 figure/table，只插入同 section 的融合式 `\autoref{}`；
  不要新增或删除 figure/table 环境本身
- 消除跨节重复
- 强化各 section 的 core_claim
- 校准 hedging
- 暴露冲突与局限
- 修复 focus_points 覆盖缺口
- 区分证据层级
- 明确指标、条件、变化方向和引用
- 移除 filler、AI 风格元评论和宣传语言
- 禁止 em dash / 中文破折号
- 按语言要求使用引号
- 不改 `\section{}` 标题、不删 section、不重构 subsection、不新增 papers list 以外的引用
- 保持 `mainbody.tex` 是正文片段而非独立 LaTeX 文档

将 LLM 输出写入 `$CACHE/scratch/mainbody_fixed.tex`。

### 可修复结构验证

**硬 gate — 不要跳过；通过前不要进入 Save。**

运行共享检查器；不要写临时验证脚本：

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" repair-structure \
  --mainbody "$CACHE/scratch/mainbody_fixed.tex" \
  --lang "$SURVEY_LANG" \
  --outline "$WORK/outline.json" \
  --report "$CACHE/mainbody_fixed_structure.txt"
```

该命令只修复确定性 wrapper/fence 噪声和裸 `%`，然后检查非空 abstract/keywords、`\maketitle`、`\tableofcontents`、必需 outline section titles、修复后的 forbidden wrappers/markdown fences，以及 `\begin{}` / `\end{}` 平衡。失败时，读取 `$CACHE/mainbody_fixed_structure.txt`，针对报告问题再做一次 correction pass，然后重新运行验证。如果仍失败，保留现有 `mainbody.tex` 不变，并报告失败检查项。

**Cite key 审计：** 删除任何不在 `papers.json` 中的 `\cite{key}`。记录为 `WARN: removed cite keys: [k1, k2]`。
修复 pass 期间或之后不要向 `papers.json` 添加 entries；此阶段文献库冻结。如果删除的 cite key 代表真实缺失覆盖，导出后报告给用户手动处理。

### 保存

```bash
cp "$CACHE/scratch/mainbody_fixed.tex" "$WORK/mainbody.tex" && \
rm -f "$CACHE/scratch/mainbody_fixed.tex"
```

### 修复 Pass 后重建 Bibliography

**硬 gate — 未完成此步骤不得进入 Step 5-C。**
省略此步会导致 `references.bib` 与修复后的 `mainbody.tex` 不同步，并造成 DOCX、TeX 和可选 LaTeX 编译 PDF 中引用过期或缺失。

LLM 修复 pass 可能删除无效引用，或保留/添加 papers list 中的有效引用。保存最终 `mainbody.tex` 后，针对当前 TeX 源重新运行 BibTeX 导出，使 `references.bib` 与最终 citation set 完全同步：

```bash
python3 "$LIT_SKILL_DIR/scripts/bibliography_library.py" export-bib \
  --library "$WORK/papers.json" --output "$WORK/references.bib" \
  --tex-file "$WORK/mainbody.tex" \
  --warn-limit 10 --diagnostics-stdout
```

如果此命令因 missing cite keys 失败，停止并将确切 failing keys 送回一次 correction pass；不要用过期或不完整的 `references.bib` 运行 `surveymaster-export`。

---

## Step 5-C — 统一导出

只有在 Step 5-B 结构验证通过后，才加载 `surveymaster-export`。

**前置要求：** 先 `SkillLoad("surveymaster-export")`，并绑定其返回的 `skillDir`：

```bash
EXPORT_SKILL_DIR="<skillDir from SkillLoad(surveymaster-export)>"
```

如果 `EXPORT_SKILL_DIR` 为空、`scripts/export_all.py` 缺失，或解析出的目录名不是
`surveymaster-export`，立即中止。Bore_Acdemic 主流程不要使用旧版 `export_skill`
目录。

运行一次统一导出脚本（一次调用处理所有请求格式）：

```bash
WORK_ABS="$(cd "$WORK" && pwd)"
python3 "$EXPORT_SKILL_DIR/scripts/export_all.py" \
  --survey-dir "$WORK_ABS" \
  --bib "$WORK_ABS/references.bib" \
  --skill-dir "$EXPORT_SKILL_DIR" \
  --language "$SURVEY_LANG"
```

收集所有 `EXPORT_RESULT` 行和任何 `EXPORT_WARNING shared` 行。如果出现 `citation_style_fallback`，停止并修复 constraints 或传入 `--citation-style` 后再重试导出。LaTeX 版 `surveymaster-export` 是必需格式 gate：DOCX、TeX 失败会以非零状态退出、清理该格式的部分产物，并阻止持久化，直到修复 `EXPORT_RESULT` 报告的问题并重新完成统一导出。PDF 默认尝试生成，但属于可选格式；如果出现 `EXPORT_WARNING pdf optional_format_failed_nonblocking`，继续持久化 DOCX、TeX 和 `references.bib`，并把 PDF 报告为 failed/skipped。

DOCX 只有一条有效生成路径：上面的同一次 `export_all.py` 调用，并且必须经过脚本内部的 `export_docx()` 流程。不要手动调用 `pandoc` 生成 DOCX，不要先运行 `export_all.py --formats tex` 再从 `$WORK/build/*.tex` 合成 DOCX，也不要把手工生成的 DOCX 标记为交付物。`$WORK/build/*.tex` 是 TeX/PDF 源，可能包含 `tabularx` 等仅 LaTeX 支持的结构；直接喂给 Pandoc 会把表格压成普通段落、丢失目录/交叉引用后处理，并绕过 DOCX 校验。如果 DOCX 失败，只能修复报告的输入或 exporter 问题，然后重跑统一导出，直到必需的 DOCX 结果为 `OK`。

PDF 只能走 LaTeX。有效 PDF 必须由同一次 `export_all.py` 调用产生，并且结果或 warning 中必须包含 `engine=latexmk-xelatex` 或 `pdf_engine=latexmk-xelatex`。不要调用或加载任何 HTML-to-PDF skill/tool、浏览器打印 PDF、截图流程、Pandoc-to-PDF、WeasyPrint、wkhtmltopdf、Playwright、Chromium、Puppeteer 或其他替代路径。如果用户明确要求 PDF 必须成功，在安装/修复 LaTeX 后，用 `--formats docx,tex,pdf` 重跑；在这种显式必需 PDF 模式下，PDF 失败会阻塞完成。

修复 PDF 失败前，检查 Python subprocess 可见的工具，而不只检查交互式 shell：

```bash
python3 -c "import shutil; print('latexmk=', shutil.which('latexmk')); print('xelatex=', shutil.which('xelatex')); print('bibtex=', shutil.which('bibtex')); print('pandoc=', shutil.which('pandoc'))"
```

如果使用 TinyTeX 或非系统 TeX 发行版，确保它的 `bin/` 目录在启动 `export_all.py` 的同一个进程的 `PATH` 最前面；安装需要时设置 `TEXMFVAR`。中文综述使用 `SciMasterNoBrand.cls` 时，TinyTeX 常见依赖包包括 `ctex`、`xecjk`、`fandol`、`xcharter`、`newtx`、`fontspec`、`cjk`、`cjkpunct` 和 `zhnumber`。面向国内用户安装 PDF 依赖时，默认使用清华 TUNA CTAN 镜像：

```bash
tlmgr option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet
tlmgr update --self
tlmgr install ctex xecjk fandol xcharter newtx fontspec cjk cjkpunct zhnumber
mktexlsr
```

如果 `tlmgr update --self` 或 `tlmgr install` 因本地 TeX Live 年份与仓库不兼容而失败，停止并报告版本不匹配，不要对同一个源反复重试。

如果 PDF 错误恰好是 `latex_log_missing`，说明预期日志文件没有找到。先确认 `--survey-dir` 是绝对路径或已被规范化；然后在 `$WORK/build` 中手动运行一次 `xelatex -interaction=nonstopmode <stem>.tex` 生成日志，并读取前 60 行定位缺失 package 或 font。这是唯一允许手动查看日志的例外情况。

**硬 gate — BibTeX key 一致性检查（统一导出后强制）。**
完成前不得进入 Step 5-D。使用 Step 5-A 顶部解析的 `$CHECK_SKILL_DIR`。只检查 `references.bib`，不要传 `--library`，因为 library+bib union 会掩盖存在于 `papers.json` 但被最终 BibTeX 导出遗漏的 cited keys。

```bash
python3 "$CHECK_SKILL_DIR/scripts/survey_checks.py" cites \
  --extra-tex "$WORK/mainbody.tex" \
  --bib "$WORK/references.bib" \
  --report "$CACHE/final_cites.txt"
```

- Exit 0：一致，进入 Step 5-D。
- Exit 20（E_CITE）：重新运行 Step 5-B 后的 BibTeX 导出，再重跑一次统一导出。
- 导出后 `references.bib` 中存在额外 keys：警告用户，但只要所有 cited keys 都存在，就不阻塞持久化。

## Step 5-D — 持久化交付物

只有主编排 agent 调用 `RecordArtifact` 或 `UpdateFile`。不要在 export、check 或 helper skills 内调用。

**下面三类交付物都必需。** 统一导出成功后持久化每一个文件；如果任意文件缺失，视为导出未完成，不要静默跳过。持久化 `surveymaster-export` 复制到工作区根目录的 TeX 源文件；`$WORK/build/` 仍是内部构建目录。

- `$WORK/<stem>.docx`
- `$WORK/<stem>.tex`
- `$WORK/references.bib`

当出现 `EXPORT_RESULT pdf OK ...` 时，持久化 `$WORK/<stem>.pdf`。如果默认可选 PDF 尝试失败，不要把持久化视为未完成；用 `EXPORT_RESULT pdf ERROR ...` 诊断将 PDF 报告为 failed/skipped。

除非用户明确请求单独版本，否则已有已保存交付物使用 `UpdateFile`。

**完成报告（标记任务完成前强制）：**
所有持久化调用完成后，输出本轮最后面向用户的纯文本完成报告。报告必须包含：
1. 一两句话概述本次最终化完成了什么（检查、修复 pass、导出、持久化）。
2. 按格式列出每个交付物及状态（saved / updated / skipped / failed）— 不要包含文件路径、超链接或 `[text](...)` 格式。

只有该文本输出后，才能：
- 将当前 TodoWrite 任务标记为 `completed`。
- 调用平台 `FinalAnswer` 工具并设置 `status: "completed"`，正确结束本轮。不要省略，否则 agent 可能循环或无法交还控制权。

不要在持久化完成前输出完成报告。不要在完成报告前调用 `FinalAnswer`。

---

## 导出后修订

Post-Export Revision 处理交付物已经生成后的用户请求。它是一种路由模式，不是新的内容生成能力。

**导出后修订中的用户交互要求：**

- **任何大纲变更** 都必须渲染为编号 section 列表（index · title — core_claim），并在运行 `surveymaster-write-section` 前**由用户明确确认**。不能基于当前会话中用户未批准的大纲重写 sections。
- **影响综述范围或语言的约束变更** 必须在重新生成内容前确认。
- 确认后，按以下合适路径继续。

路径：
- **仅导出变化：** 运行 Step 5-A 到 Step 5-D。
- **局部内容或风格变化：** 加载 `surveymaster-write-section --mode rewrite` 做全文重写，或 `surveymaster-refine-section` 在不改变结构的情况下润色。然后运行 Step 5-A 到 Step 5-D。
- **视觉资产变化**（插入、移除或重新生成 figure/table）：
  1. **插入 figure** 到用户指定位置：
     a. 选择全文唯一 `fig_<snake_case>` id。
     b. 从 `surveymaster-figure-types` 选择 figure type，并用周围 section 的 `core_claim` 构建 prompt。
     c. 将占位块插入 `mainbody.tex` 的目标位置。
     d. 在周围文本中插入且仅插入一个 `\autoref{fig:<id>}`。
     e. 调用 agent 的 `image_gen` 工具生成 `$WORK/figures/<id>.png`。失败则移除插入块和 autoref 并报告错误。本地 PNG 是 DOCX、TeX 和 PDF 使用的必需图片资产。
     f. 在 `outline.json` 中将 `expected_figures_total` 加 1，然后 `SkillLoad("surveymaster-generate-outline")` 并重新运行 `save_outline.py --file "$WORK/outline.json"`，重新规范化并渲染 `outline.md`。
  2. **插入 table** 到用户指定位置：
     a. 选择唯一 `tab_<snake_case>` id。
     b. 从 `surveymaster-table-types` 选择 table type 和列结构。通用非经济学综述插入完整 booktabs 三线表（只用 `\toprule`/`\midrule`/`\bottomrule`；不用 `\hline`、`\multicolumn`、`\multirow`）。经济学 empirical-style 综述改用 Economics Journal Table Style：上下粗线、内部细横线、纵向列分隔线、紧凑黑白版式，且不使用 `\multicolumn` 或 `\multirow`。
     c. 在周围文本中插入且仅插入一个 `\autoref{tab:<id>}`。
     d. 在 `outline.json` 中将 `expected_tables_total` 加 1，并如上重新运行 `save_outline.py`。
  3. **移除 figure/table**：移除环境块及其 `\autoref{}` 引用；对 figures，还要在 `outline.json` 中将 `expected_figures_total` 减 1（最小 0），然后重新运行 `save_outline.py`。磁盘上的 `figures/<id>.png` 可以保留，孤立 PNG 不影响导出。
  4. **重新生成 figure**：删除 `$WORK/figures/<id>.png`，用 `% FIGURE` 注释中的现有 prompt 调用 agent 的 `image_gen` 工具，等待新的本地文件。
  5. 任何视觉资产变化后，运行 Step 5-A 到 Step 5-D。
  6. **编号：** 展示序号（图 1、Figure 2、表 1 等）完全由 LaTeX 通过 `\caption{}` + `\label{}` + `\autoref{}` 管理。永远不要手动重命名 ids 或重新编号 labels。
- **约束变化：** 更新 constraints，重新渲染派生视图；如果范围或风格变化，先与用户确认；然后运行 Step 5-A 到 Step 5-D。
- **论文/文献库变化：** 更新 `papers.json`，判断是否需要重新生成大纲或 sections，然后运行受影响阶段和 Step 5-A 到 Step 5-D。
- **大纲变化：** JSON-first 更新 `outline.json`，渲染完整更新大纲并**展示给用户明确确认**，等待批准后，用 `surveymaster-write-section` 重写 `mainbody.tex`，再运行 Step 5-A 到 Step 5-D。
- **语言变化：** 回到编排器语言变更流程。根据当前用户请求解析语言，重新运行 `surveymaster-identify`，再用该语言重新运行 `surveymaster-generate-outline`。向用户展示重新生成的大纲并等待明确确认，删除过期 `mainbody.tex`，用新语言运行 `surveymaster-write-section` 重写，然后运行完整 Stage 5。

语言变化时，永远不要机器翻译已有 `.tex` 文件。除非用户明确要求，否则不要删除 source-of-truth JSON 或 `papers.json`。
