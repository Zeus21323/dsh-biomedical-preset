---
name: surveymaster-domain-templates
version: 0.2.0
description: Bundled domain writing templates for SurveyMaster Stage 1. These templates override generic fallback defaults when topic or subject clearly matches a domain and no venue-specific constraints are requested.
---

# SurveyMaster Domain Templates

Use these files during `surveymaster-identify` before applying the generic
Fallback Defaults table. A domain template applies only when the topic or
subject clearly matches its trigger terms and the user has not explicitly
requested a different target journal, conference, or venue-specific writing
constraint.

Current templates:

| Template | File | Applies to |
|---|---|---|
| Biomedical/bioinformatics review | `biomedical-bioinformatics-review.md` | biomedical, life science, clinical, oncology, microbiome, omics, computational biology, bioinformatics, immunology, pharmacology, epidemiology, public health, and related translational biology topics |
| Economics empirical-style review | `economics-empirical-review.md` | economics, finance, management, accounting, industrial economics, public finance, environmental economics, corporate finance, supply-chain finance, development economics, policy evaluation, regional economics, and related empirical social-science topics |

When a template applies:

1. Read the matching template file completely.
2. Use its `constraint_source`, `venue_style_notes`, default constraints, and
   writing-pattern requirements.
3. Preserve user-specified values such as requested length, figure/table counts,
   target venue, citation style, focus points, and special requirements.
4. If multiple templates could apply, choose the most specific template. If no
   specific template is clearly applicable, use the generic fallback defaults in
   `surveymaster-identify/SKILL.md`.
