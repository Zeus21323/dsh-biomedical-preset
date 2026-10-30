# 基金申请书 TeX 与 DOCX 导出

## 权威源与目录

Word 交付使用以下最小目录；不要创建 Markdown 中间稿：

```text
deliverables/
  grant-application.tex
  references.bib             # 有引用时
  grant-application.docx
  docx_export/
    journal_config.json
    journal_template.docx
    grant_tex_audit.json
    docx_delivery_audit.json
```

从 `assets/grant-application.tex` 复制起始结构，根据用户提供的指南或模板调整章节。指南中的标题文字和顺序优先，模板仅提供安全的默认层级。

## 标题结构

只允许真实章节进入 Word 标题层级：

```latex
\section*{立项依据}
\subsection*{研究意义}
\subsection*{国内外研究现状}
\section*{研究内容、研究目标及拟解决的关键科学问题}
```

`tex_to_docx/assets/docx/template-zh.docx` 的 Heading 1/2/3 样式已经绑定 `numId=1` 的自动多级编号。TeX 花括号中只写标题文字，严禁写入 `一、`、`1.`、`1.1`、`（一）` 等编号，否则 WPS/Word 会显示 `1. 一、立项依据` 或 `1.1. 1.1 研究意义`。

若正式指南要求中文序号，必须在 `tex_to_docx` 的 reference DOCX/配置中把自动编号格式改成中文序号，并继续保持 TeX 标题无编号。编号只能由 Word 样式或标题文本中的一个来源负责，当前流程固定由 Word 样式负责。

以下内容必须是正文元数据，不是标题：

```latex
\noindent\textbf{项目名称：}面向……的研究\par
\noindent\textbf{项目类别：}国家自然科学基金青年科学基金项目\par
\noindent\textbf{申请代码：}F0601（人工智能基础理论）\par
\noindent\textbf{研究方向：}指令微调、数据质量评估\par
```

不要为了放大或加粗而滥用标题样式；用 `\textbf{}`、普通段落或表格表达封面信息。不要把整份项目名称设为一级标题，除非用户提供的正式模板明确要求如此。

## 导出前校验

从基金 Skill 根目录运行：

```bash
python3 scripts/validate_grant_tex.py \
  /path/deliverables/grant-application.tex \
  --report /path/deliverables/docx_export/grant_tex_audit.json
```

校验失败时先修复 TeX。不得通过关闭校验、删除真实章节或改用 Markdown 绕过。

## 调用 tex_to_docx

在运行时查找并读取 frontmatter `name: tex-to-docx` 对应的 Skill。优先使用当前安装的 Skill；在本开发工作区中，相邻的 `../tex_to_docx` 是可用候选，但不要把该绝对路径写入生成物。

凡生成或修改正式申请书正文，自动运行本节，不询问用户是否需要 Word。只有纯讨论、诊断或只读评审没有产生正文时才跳过。

无文献引用的通用中文基金申请可运行：

```bash
python3 <tex_to_docx_skill_dir>/scripts/ensure_pandoc.py

python3 <tex_to_docx_skill_dir>/scripts/tex_to_docx.py all \
  --source /path/deliverables/grant-application.tex \
  --output /path/deliverables/grant-application.docx \
  --journal-profile gb-t-7714-2015 \
  --journal "中文科研基金申请书" \
  --article-type "基金申请书" \
  --language zh \
  --from-format latex \
  --work-dir /path/deliverables/docx_export
```

有文献时，生成真实 `references.bib`，在 TeX 正文使用 `\cite{key}`，并根据用户或指南要求向 `all` 命令传入 `--bib` 和适用 CSL。不得手写参考文献段落或虚构 BibTeX 元数据。只有确实需要目录时才传 `--toc`；只有 TeX 含有应嵌入图片时才传 `--require-media`。

不要直接运行 Pandoc。`tex_to_docx` 负责 reference DOCX、资源路径、公式、媒体、引用和 DOCX 包校验。

## 最终交付审计

所有后处理完成后重新运行：

```bash
python3 <tex_to_docx_skill_dir>/scripts/tex_to_docx.py validate-docx \
  --docx /path/deliverables/grant-application.docx \
  --source /path/deliverables/grant-application.tex \
  --report /path/deliverables/docx_export/docx_delivery_audit.json

python3 <grant_skill_dir>/scripts/validate_grant_tex.py \
  /path/deliverables/grant-application.tex \
  --docx /path/deliverables/grant-application.docx \
  --report /path/deliverables/docx_export/grant_tex_audit.json
```

这里使用 GB/T profile 只是为了取得可追溯的中文基础版式；它含有 fallback 字段，并不代表基金委官方版式。用户提供的正式申请模板和当年指南始终优先。

最后一个命令直接检查 OOXML，而不是依赖 `python-docx` 的 `paragraph.text`。后者不包含 Word 自动显示的列表编号，无法发现“样式编号 + 手写编号”的重复。若元数据使用 Heading 样式，或已绑定自动编号的标题文本仍以手写编号开头，审计必须失败并回到 TeX 修复。
