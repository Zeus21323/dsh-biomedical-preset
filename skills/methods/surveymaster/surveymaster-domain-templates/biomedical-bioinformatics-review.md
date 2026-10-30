---
name: surveymaster-domain-template-biomedical-bioinformatics-review
version: 0.2.0
description: Biomedical and bioinformatics narrative review defaults for SurveyMaster Stage 1 domain constraints.
---

# Biomedical/Bioinformatics Review Template

## Trigger

Apply this template when the topic or subject is clearly biomedical,
life-science, clinical medicine, oncology, microbiome, genomics,
transcriptomics, proteomics, multi-omics, computational biology,
bioinformatics, biostatistics, public health, epidemiology, pharmacology,
immunology, or related translational biology.

Do not apply it when the user explicitly requests a different target journal,
conference, or venue-specific writing constraint. In that case, follow the
venue-specific discovery path in `surveymaster-identify`.

## Design Intent

This bundled template provides a moderate default structure for biomedical and
bioinformatics narrative reviews. It borrows the mechanism-oriented and
evidence-layered organization common in high-quality biomedical reviews, but it
does not impose full Nature Reviews-scale length, reference, or figure/table
requirements unless the user explicitly requests a comprehensive or
venue-specific review.

## Constraint Values

Use:

- `constraint_source`: `{"name": "bundled biomedical review template", "url": null}`
- `venue_style_notes`: "Biomedical/bioinformatics narrative review style: define disease, biological system, or data modality first; synthesize mechanisms and evidence layers; connect molecular, cellular, computational, or clinical findings to biomarkers, therapy, translation, limitations, and open questions without defaulting to full Nature Reviews-scale requirements."

Default constraints:

| Field | zh | en |
|---|---|---|
| body length | 8,000-10,000 chars | 4,500-6,000 words |
| abstract | 250-350 Chinese chars or <=250 English words; background -> main body -> short conclusion | <=250 words; background -> main body -> short conclusion |
| required sections | 引言 -> 疾病/系统或数据背景 -> 核心机制与证据 -> 应用/转化意义 -> 挑战与未来方向 -> 结论 | Introduction -> disease/system or data background -> core mechanisms and evidence -> applications/translational implications -> challenges and future directions -> conclusions |
| references | 45-80 | 45-80 |
| `target_figure_count` | 2 (unless user specifies) | 2 (unless user specifies) |
| `target_table_count` | 1 (unless user specifies) | 1 (unless user specifies) |
| `figure_color_policy` | `low_saturation_color` | `low_saturation_color` |
| Introduction | 700-1000 chars | 450-650 words |
| each body section | 1000-1700 chars | 650-1000 words |
| Challenges/future directions | 700-1100 chars | 450-700 words |
| Conclusion | 400-700 chars | 200-350 words |

Recommended structured values:

```json
{
  "total_length_target": {"zh_chars": 9000},
  "section_length_policy": {
    "default_min": {"zh_chars": 1200},
    "overrides": {
      "introduction": {"zh_chars": 850},
      "regular": {"zh_chars": 1200},
      "future_directions": {"zh_chars": 850},
      "conclusion": {"zh_chars": 500},
      "abstract": {"zh_chars": 300}
    }
  },
  "target_figure_count": 2,
  "target_table_count": 1,
  "figure_color_policy": "low_saturation_color"
}
```

Use `en_words` instead of `zh_chars` when `language == "en"`:

```json
{
  "total_length_target": {"en_words": 5500},
  "section_length_policy": {
    "default_min": {"en_words": 800},
    "overrides": {
      "introduction": {"en_words": 550},
      "regular": {"en_words": 800},
      "future_directions": {"en_words": 550},
      "conclusion": {"en_words": 280},
      "abstract": {"en_words": 220}
    }
  },
  "target_figure_count": 2,
  "target_table_count": 1,
  "figure_color_policy": "low_saturation_color"
}
```

## Writing Pattern

- Start from disease burden, biological context, or clinical unmet need, then
  narrow to the review's central mechanism or data modality.
- Organize the body around mechanistic axes, evidence layers, or translational
  use cases rather than a simple paper-by-paper chronology.
- Distinguish evidence from human cohorts, animal models, organoids/cell models,
  computational analyses, clinical trials, and meta-analyses.
- Include a figure slot for a mechanistic, evidence-layer, or data-workflow
  schematic. Add a separate clinical/translational workflow figure only when
  the topic and requested scope support it.
- Include at least one table slot comparing mechanisms, biomarkers, datasets,
  therapeutic strategies, or study types.
- Include challenges, limitations, or future directions before the conclusion;
  for shorter articles this can be a combined section rather than a large
  standalone discussion.
- Avoid clinical recommendations beyond the cited evidence. Mark speculative
  or preclinical claims as such.
- For bioinformatics topics, emphasize cohort/data provenance, assay/platform
  differences, reproducibility, validation cohorts, model interpretability, and
  clinical utility.

## Full Review Escalation

Escalate toward a full Nature Reviews-style scale only when the user explicitly
requests a comprehensive review, a high-impact review-article style, or a
specific venue whose official requirements call for it. In that case, use a
larger range such as 10,000-14,000 Chinese chars or 6,000-8,000 English words,
70-120 references, 4 figures, and 2 tables unless the venue or user specifies
otherwise.
