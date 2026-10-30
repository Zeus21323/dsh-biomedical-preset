---
name: surveymaster-table-types
version: 0.2.0
description: Reference skill for academic table type constraints and LaTeX templates. Loaded by write-section and finalize when generating or inserting tables to select the correct table type and build a compliant table environment.
---

## Role

Passive reference only. This skill does not execute steps — it provides table
type definitions, column structure guidelines, and LaTeX templates that the
calling skill uses to write a compliant `\begin{table}…\end{table}` environment
in `mainbody.tex`.

## Table Type Catalogue

### Economics Journal Table Style — 经济学期刊表格版式

Apply this style only when the survey explicitly uses the economics
empirical-style template. Operationally, this means either
`constraint_source.name` is `bundled economics empirical-style review template`
or `venue_style_notes` explicitly contains `Economics empirical-style review`.
Do not trigger this style from broad keywords such as finance, management,
policy, supply chain, or social science when the economics empirical-style
template was not selected.

This is a **style override**, not a separate content type. It can be used with
literature-summary tables, mechanism tables, variable tables, robustness
summaries, or empirical-evidence tables.

**Visual rules:**
- Use the Chinese economics-journal table convention: heavy top and bottom
  rules, thinner internal horizontal rules, and vertical column separators.
- Do not use colored cells, shaded headers, decorative backgrounds, icons, or
  infographic styling.
- Keep the table compact, black-and-white, and text-centered where appropriate.
- For normal review tables, use substantive column headers such as 研究脉络、
  理论机制、代表文献、数据来源、识别策略、主要结论、局限与拓展方向.
- Regression-style columns `(1)`, `(2)`, `(3)`, `(4)`, `Y` / `N` rows for
  controls or fixed effects, coefficient values, standard errors, and
  significance stars are **not default for reviews**. Use them only when the
  user explicitly asks to reproduce or summarize empirical regression-style
  results from cited papers. Never invent values or stars.

**LaTeX pattern:**

Use vertical separators and explicit rule thickness. Prefer this pattern over
plain `booktabs` for economics empirical-style tables:

```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \renewcommand{\arraystretch}{1.15}
  \begin{tabular}{l|c|c|c|c}
    \noalign{\hrule height 1.2pt}
    变量 & （1） & （2） & （3） & （4） \\
    \hline
    <变量A> & <估计值> & <估计值> & <估计值> & <估计值> \\
             & (<标准误>) & (<标准误>) & (<标准误>) & (<标准误>) \\
    \hline
    控制变量 & Y & Y & Y & Y \\
    企业固定效应 & Y & Y & Y & Y \\
    年份固定效应 & Y & Y & Y & Y \\
    观测值 & <N> & <N> & <N> & <N> \\
    \noalign{\hrule height 1.2pt}
  \end{tabular}
  \vspace{0.3em}
  \parbox{0.95\linewidth}{\footnotesize 注：括号内为稳健标准误；*、**、***分别表示在10%、5%和1%的水平上显著。}
\end{table}
```

If `\noalign{\hrule height 1.2pt}` causes an export failure, use `\hline` as a
fallback while keeping the same vertical separators. Do not switch to decorative
styling.

---

### 1. `performance_comparison` — 性能对比表

**Use when:** summarising key quantitative or qualitative indicators across
different studies, materials, models, or solutions; enabling readers to compare
state-of-the-art results at a glance.

**Typical examples:** 不同 MXene 材料的导电率、比容量对比；各深度学习模型在基准数据集上的精度/速度

**Column structure:**
- First column: entity identifier (material name, model name, paper reference, etc.)
- Middle columns: key performance metrics (2–5 metrics recommended)
- Last column (optional): reference `\cite{key}`
- Use `\cite{}` in data cells where the value comes from a specific paper

**Constraints:**
- Do not fabricate metric values; only include values stated or clearly implied in cited papers
- Use `—` for unavailable data, not blank cells
- Maximum recommended columns: 6; maximum recommended rows: 12

**LaTeX template (zh):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{l<col-spec>}
    \toprule
    方法/材料 & 指标1 & 指标2 & 指标3 & 参考文献 \\
    \midrule
    <实体A> & <值> & <值> & <值> & \cite{<key>} \\
    <实体B> & <值> & <值> & <值> & \cite{<key>} \\
    \bottomrule
  \end{tabular}
\end{table}
```

**LaTeX template (en):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{l<col-spec>}
    \toprule
    Method/Material & Metric 1 & Metric 2 & Metric 3 & Reference \\
    \midrule
    <entity A> & <val> & <val> & <val> & \cite{<key>} \\
    <entity B> & <val> & <val> & <val> & \cite{<key>} \\
    \bottomrule
  \end{tabular}
\end{table}
```

---

### 2. `classification_comparison` — 分类对比表

**Use when:** comparing methods, frameworks, technical approaches, regulatory
systems, or paradigms along categorical dimensions; helping readers map the
conceptual landscape of a field.

**Typical examples:** 不同强化学习算法的适用场景、优缺点；各国 AI 监管框架对比；监督/无监督/自监督学习方法对比

**Column structure:**
- First column: category or method name
- Middle columns: categorical dimensions (e.g. applicable scenario, key advantage, key limitation, representative work)
- Avoid numeric metrics in this table type — those belong in `performance_comparison`

**Constraints:**
- Cell content should be concise phrases, not full sentences
- If a dimension does not apply to an entry, use `—`
- Maximum recommended columns: 5; maximum recommended rows: 10

**LaTeX template (zh):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{l<col-spec>}
    \toprule
    方法/类别 & 适用场景 & 主要优势 & 主要局限 & 代表工作 \\
    \midrule
    <方法A> & <场景> & <优势> & <局限> & \cite{<key>} \\
    <方法B> & <场景> & <优势> & <局限> & \cite{<key>} \\
    \bottomrule
  \end{tabular}
\end{table}
```

**LaTeX template (en):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{l<col-spec>}
    \toprule
    Method/Category & Scenario & Advantage & Limitation & Reference \\
    \midrule
    <method A> & <scenario> & <advantage> & <limitation> & \cite{<key>} \\
    <method B> & <scenario> & <advantage> & <limitation> & \cite{<key>} \\
    \bottomrule
  \end{tabular}
\end{table}
```

---

### 3. `challenge_strategy_matrix` — 挑战-应对策略矩阵

**Use when:** structurally presenting field challenges, associated problems, and
corresponding solutions, mitigation strategies, or future research directions;
useful in conclusion or discussion sections.

**Typical examples:** MXene 规模化制备面临的挑战与解决方案；大模型幻觉问题的成因与应对策略；跨域迁移学习的挑战与未来方向

**Column structure (recommended):**

1. 挑战/问题 (Challenge)
2. 具体表现（Manifestation / Impact / Cause）
3. 当前应对策略 (Current strategies)
4. 未来研究方向 (Future directions)

**Constraints:**
- Each row represents one independent challenge; do not merge rows
- Cell content should be concise actionable phrases
- The "Current strategies" and "Future directions" cells may cite supporting papers with `\cite{}`
- Maximum recommended rows: 8

**LaTeX template (zh):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{llll}
    \toprule
    挑战 & 具体表现 & 当前策略 & 未来方向 \\
    \midrule
    <挑战A> & <表现> & <策略> \cite{<key>} & <方向> \\
    <挑战B> & <表现> & <策略> & <方向> \\
    \bottomrule
  \end{tabular}
\end{table}
```

**LaTeX template (en):**
```latex
\begin{table}[htbp]
  \centering
  \caption{<caption>\label{tab:<id>}}
  \begin{tabular}{llll}
    \toprule
    Challenge & Manifestation & Current strategies & Future directions \\
    \midrule
    <challenge A> & <manifestation> & <strategy> \cite{<key>} & <direction> \\
    <challenge B> & <manifestation> & <strategy> & <direction> \\
    \bottomrule
  \end{tabular}
\end{table}
```

---

## Type Selection Guide


1. Does the table present challenges, limitations, risks, bottlenecks, corresponding strategies, or future directions?→ `challenge_strategy_matrix`
2. Does the table compare quantitative metrics, benchmark results, experimental measurements, or performance indicators across entities?→ `performance_comparison`
3. Does the table compare methods, frameworks, categories, paradigms, regulatory systems, or other qualitative properties?→ `classification_comparison`

When multiple types could apply, choose the one that best matches the section's
`core_claim`. For a table that mixes metrics and categories heavily, prefer
`classification_comparison` and note any numeric values as qualitative ranges
(e.g. "高/中/低").

## Universal Constraints (all table types)

- For generic science/engineering tables, use only `\toprule`, `\midrule`,
  `\bottomrule` from the `booktabs` package; no `\hline`.
- For economics empirical-style tables, use the Economics Journal Table Style
  above instead: heavy outer horizontal rules, thin internal horizontal rules,
  and vertical column separators.
- No `\multicolumn` or `\multirow`
- The `\caption{}` must contain `\label{tab:<id>}` inline
- The surrounding prose must contain at least one `\autoref{tab:<id>}` reference
- Column alignment: first column `l`; metric columns `c` or `r`; text columns `l`
- Avoid fixed-width columns by default.If the table would overflow due to long text content, controlled-width columns may be used according to the export format.

## Table Size Control

Avoid oversized tables.

Recommended limits:
- Maximum columns: 6
- Maximum rows: 12
If the content exceeds these limits:
- reduce dimensions;
- split the table;
- summarize less important entries;
- convert to narrative text.
Do not generate tables that are difficult to read on a standard page.

## Usage

Select the type using the guide above, choose columns from the matching template, fill data cells using only values from cited papers with `\cite{}` where applicable. The type name does not appear in LaTeX output.
