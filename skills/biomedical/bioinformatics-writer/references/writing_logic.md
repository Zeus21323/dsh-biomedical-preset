# Writing Logic

Write manuscript sections only after results are available and the user has
explicitly approved `manuscript_prd.md` and `manuscript_outline.json`. Existing
results do not waive the planning approval. The canonical manuscript source is
LaTeX: `manuscript/mainbody.tex`.

Read `references/manuscript_workflow.md` before planning or drafting. Follow
the approved chapter order, evidence mappings, figure mappings, literature
questions, and target-journal decision. Do not create or materially change a
section, claim, or figure outside that approved plan.

Also require `citation_preference.json` from the separate citation-format
interaction. Do not choose a CSL or in-text citation presentation merely from
an available template when the user has not selected it.

Read `references/manuscript_length_policy.md` before allocating or drafting
sections. Treat targets as advisory unless the approved plan explicitly uses
strict enforcement. Never pad text. If the available evidence cannot support
a complete subsection, merge it with a related subsection or report the
missing evidence instead of writing a thin standalone heading.

## Introduction

Use four paragraphs:

```text
1. disease burden and clinical problem
2. relevant biological background
3. knowledge gap
4. what this study did and found
```

## Results

Each subsection corresponds to one Results question.

Each substantive Results subsection must include quantitative evidence,
statistics when available, and its mapped figure/table. Report an advisory
target deficit without automatically adding prose; satisfy a strict target
only with verified content. A four-sentence skeleton is a logic checklist, not
a complete publishable subsection.

Use this paragraph pattern:

```text
To answer [question], we performed [analysis].
The analysis showed [main statistical finding].
This suggests [biological interpretation].
These findings are shown in Figure X.
```

## Discussion

Use this order:

```text
1. main findings
2. relationship to previous literature
3. biological mechanism
4. clinical/translational significance
5. limitations
6. future directions
```

## Methods

Give every substantive Methods subsection enough detail for reproducibility:
input object and grouping, preprocessing, software/package, critical
parameters, statistics/thresholds, quality control, and downstream output.
Do not leave an analysis under its own heading when it is only one or two
sentences; expand it from verified scripts/logs or merge it with the closest
methodological subsection.

## Three-paper Logic Extract

The common logic from strong biomedical papers:

```text
clinical problem
data-driven discovery
clinical association
biological characterization
functional/computational validation
mechanistic interpretation
translational significance
```

Use this as the manuscript story spine.

## Output Format

Generate:

```text
manuscript/
  mainbody.tex
  references.bib
  supplementary.tex
  figures/
```

`mainbody.tex` should contain title, abstract, keywords, main sections, tables when practical, figure references, and figure legends. Use BibTeX citation keys matching `references.bib`.

When the manuscript has major figures and DOCX is an output, stage each combined preview
PNG under `manuscript/figures/` and insert it in `mainbody.tex` with a literal relative
path, for example:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{figures/Figure1_preview.png}
\caption{Figure 1. ...}
\label{fig:figure1}
\end{figure}
```

Text such as `Figure 1A`, `\ref{fig:figure1}`, and a Figure Legends section are references
or descriptions only; they do not embed an image in DOCX. Keep paths relative to
`mainbody.tex`, verify every referenced file before export, and never replace them with
machine-specific absolute paths.

For DOCX export, use only:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/tex_to_docx/scripts/tex_to_docx.py ...
```

Do not generate DOCX with custom JavaScript, python-docx manuscript builders, or ad hoc Word XML from this skill.
Do not call Pandoc directly. Run the manuscript preflight first, then invoke
the `tex_to_docx` skill and retain its export log. Any unresolved citation or
bibliography warning blocks delivery.
