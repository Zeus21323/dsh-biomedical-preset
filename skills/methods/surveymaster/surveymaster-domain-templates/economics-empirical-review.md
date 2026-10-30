---
name: surveymaster-domain-template-economics-empirical-review
version: 0.2.0
description: Economics and empirical social-science review defaults for SurveyMaster Stage 1 domain constraints.
---

# Economics Empirical-Style Review Template

## Trigger

Apply this template when the topic or subject is clearly economics, finance,
management, accounting, industrial economics, public finance, environmental
economics, corporate finance, supply-chain finance, development economics,
policy evaluation, regional economics, or related social-science empirical
research.

Use this template for surveys/reviews that should read like Chinese
top-journal economics writing: institutionally grounded, mechanism-driven, and
evidence-oriented. Do not make the generated survey claim to run new regressions
unless the user explicitly provides data and asks for an empirical paper.

Do not apply it when the user explicitly requests another target journal,
conference, or venue-specific writing constraint. In that case, follow the
venue-specific discovery path in `surveymaster-identify`.

## Design Intent

This bundled template provides a moderate default structure for economics and
management-style empirical literature reviews. It emphasizes the writing logic
common in high-quality Chinese economics journals: start from an institutional
or policy background, turn the topic into a concrete economics problem,
organize prior work by mechanism and evidence rather than by chronology, and
separate theoretical interpretation from empirical identification.

## Constraint Values

Use:

- `constraint_source`: `{"name": "bundled economics empirical-style review template", "url": null}`
- `venue_style_notes`: "Economics empirical-style review: convert the topic into a concrete economics problem, identify its theoretical nature, organize the review by mechanism rather than by author/year, compare empirical evidence and identification strategies, use functional figures/tables, and close with research gaps plus policy implications. Begin from a Chinese institutional or policy background when relevant. Do not present unsupported causal claims as established facts."

Default constraints:

| Field | zh | en |
|---|---|---|
| body length | 10,000-13,000 chars | 6,000-7,500 words |
| abstract | 250-350 Chinese chars or <=250 English words; research background -> core question -> reviewed evidence/mechanisms -> contribution/implication | <=250 words; background -> core question -> evidence/mechanisms -> contribution/implication |
| required sections | 引言 -> 经济学问题与理论基础 -> 机制分类与文献脉络 -> 数据、变量与识别策略综述 -> 主要经验证据与结论分歧 -> 稳健性、内生性与异质性讨论 -> 研究缺口、未来方向与政策启示 | Introduction -> economics problem and theory -> mechanism-based literature streams -> data, variables, and identification strategies -> empirical evidence and divergent findings -> robustness, endogeneity, and heterogeneity -> gaps, future directions, and policy implications |
| references | 60-100 | 60-100 |
| `target_figure_count` | 1 (unless user specifies) | 1 (unless user specifies) |
| `target_table_count` | 3 (unless user specifies) | 3 (unless user specifies) |
| `figure_color_policy` | ask user; default `low_saturation_color` if unavailable | ask user; default `low_saturation_color` if unavailable |
| Introduction | 1200-1800 chars | 800-1100 words |
| each body section | 1200-2000 chars | 800-1200 words |
| Conclusion and policy implications | 700-1100 chars | 400-700 words |

Recommended structured values:

```json
{
  "total_length_target": {"zh_chars": 12000},
  "section_length_policy": {
    "default_min": {"zh_chars": 1400},
    "overrides": {
      "introduction": {"zh_chars": 1500},
      "regular": {"zh_chars": 1400},
      "conclusion": {"zh_chars": 900},
      "abstract": {"zh_chars": 300}
    }
  },
  "target_figure_count": 1,
  "target_table_count": 3,
  "figure_color_policy": "low_saturation_color"
}
```

Use `en_words` instead of `zh_chars` when `language == "en"`:

```json
{
  "total_length_target": {"en_words": 7000},
  "section_length_policy": {
    "default_min": {"en_words": 950},
    "overrides": {
      "introduction": {"en_words": 950},
      "regular": {"en_words": 950},
      "conclusion": {"en_words": 550},
      "abstract": {"en_words": 220}
    }
  },
  "target_figure_count": 1,
  "target_table_count": 3,
  "figure_color_policy": "low_saturation_color"
}
```

For economics empirical-style surveys, Stage 1 asks the user once whether
mechanism/workflow/review schematic figures should use low-saturation academic
color or black-and-grayscale journal style. The structured value above is only
the fallback when the user has not specified a preference and the preference
gate cannot be completed.

## Writing Pattern

- Treat the survey as a reconstruction of how an economics problem has been
  proposed, explained, tested, revised, and extended. Do not write it as a
  chronological bibliography.
- Follow this execution order when planning and drafting:
  1. Convert the topic into an economics problem.
  2. Identify the theoretical nature of the problem, such as financing
     constraints, resource allocation, incentives, information asymmetry, market
     power, externality, public goods, risk spillover, or institutional
     governance.
  3. Build the baseline theoretical framework.
  4. Group the literature by mechanism, not by author/year.
  5. Compare why findings differ across samples, data sources, variable
     measurement, identification strategies, institutional settings, and time
     periods.
  6. Synthesize contributions and unresolved gaps.
  7. Plan a literature classification table and, when mechanisms are complex, a
     mechanism/framework figure.
  8. Draft in the order: problem statement -> theory -> mechanism streams ->
     evidence comparison -> gaps/future directions -> policy implications.
- Start with a real institutional, policy, or market background, then narrow to
  a concrete economic puzzle rather than opening with broad slogans.
- State why the question matters for theory, identification, and policy. Avoid
  treating policy importance alone as the contribution.
- Use a "现有文献认为...然而..." / "existing studies show...however..."
  structure to locate the literature gap.
- Build a causal or mechanism framework before summarizing evidence. For
  economics topics, mechanisms often include information asymmetry, financing
  constraints, market power, resource misallocation, incentives, risk spillover,
  policy enforcement, and institutional frictions.
- When the survey discusses empirical papers, separate: data source, sample,
  key variables, identification strategy, main coefficient interpretation,
  robustness/endogeneity checks, mechanism tests, heterogeneity, and extensions.
- Prefer section titles that describe analytical function, not decorative
  phrases. Examples: "理论机制与研究假说", "识别策略与变量构造",
  "基准证据与稳健性", "机制检验", "异质性与进一步分析".
- Include one conceptual framework figure when useful, especially to show a
  policy shock, mediating channels, and outcome variables.
- Include tables for: literature comparison, variable/measure comparison, and
  empirical strategy or finding synthesis.
- Use economics-journal table formatting: heavy top and bottom rules, thinner
  internal horizontal rules, vertical column separators, compact black-and-white
  layout, and optional table notes for standard errors/significance conventions.
- For reviews, prefer "命题/分析框架/proposition/framework" language over
  "研究假说/hypothesis" unless the user explicitly wants an empirical paper.
- A strong economics review usually has at least one table. Use figures only
  when they clarify theory, mechanisms, timelines, or evidence structure; do
  not add decorative figures.
- Economics figures must be plain black-and-white line diagrams: white
  background, black/gray boxes and arrows, no gradients, no saturated colors,
  no decorative icons, no 3D effects, and no pictorial ornamentation.
- Discuss endogeneity explicitly. Typical concerns include omitted variables,
  reverse causality, policy timing, sample selection, measurement error, and
  concurrent shocks.
- For policy-evaluation topics, discuss parallel-trend logic, DID/DDD/event
  study designs, treatment and control definitions, placebo tests, alternative
  variable construction, fixed effects, clustering, and robustness.
- Keep the tone restrained and evidentiary. Use "表明", "可能", "支持",
  "进一步验证" rather than overstating causal certainty when evidence is
  correlational or literature-based.
- End with policy implications that follow directly from the reviewed evidence,
  then identify unresolved issues and future research directions.

## Review-Oriented Section Logic

When the agent builds the outline for an economics review, prefer this logical
sequence unless the user supplies a different section plan:

1. **引言 / Introduction**: institutional background, core economics puzzle,
   review contribution, and the organizing framework.
2. **经济学问题与理论基础 / Economics problem and theory**: translate the topic
   into a theoretical category and introduce the classical baseline.
3. **机制分类与文献脉络 / Mechanism-based streams**: organize literature by
   mechanisms such as financing constraints, incentives, information, market
   power, resource allocation, supply-chain transmission, policy enforcement,
   or risk spillover.
4. **数据、变量与识别策略 / Data, variables, and identification**: compare common
   datasets, core variable construction, empirical strategies, and research
   design limitations.
5. **经验证据与分歧 / Evidence and divergent findings**: synthesize main
   findings, explain conflicting conclusions, and connect differences to data,
   measurement, sample period, institutional context, and identification.
6. **稳健性、内生性与异质性 / Robustness, endogeneity, and heterogeneity**:
   summarize how the literature handles causal concerns and subgroup
   differences.
7. **研究缺口与政策启示 / Gaps and implications**: state concrete unresolved
   questions, future research directions, and policy implications supported by
   the reviewed evidence.
