# Manuscript Length And Completeness Policy

Use this policy for biomedical original-research manuscripts unless the target
journal provides a documented alternative. Count English tokens as words and
two CJK characters as one word-equivalent.

## Default completeness targets

| Scope | Minimum word-equivalents |
|---|---:|
| Main text: Introduction through Conclusion | 3200 |
| Abstract | 180 |
| Introduction | 600 |
| Methods total | 800 |
| Each substantive Methods subsection | 100 |
| Results total | 900 |
| Each Results subsection | 150 |
| Discussion | 700 |
| Conclusion | 100 |
| Each major figure legend | 60 |

These are default completeness targets, not universal publication requirements.
Set `length_policy.enforcement` in `manuscript_outline.json` to one of:

- `advisory` (default): report every short section/subsection/legend as a
  `WARNING`, but do not block DOCX delivery solely for length;
- `strict`: treat every approved target as an error that blocks delivery.

Use `strict` only when the user explicitly requests hard length gates or the
target journal/article type provides a documented requirement. Missing entire
required sections, a missing abstract, and missing planned figure legends are
structural errors in both modes.

Administrative subsections such as Data Availability, Code Availability,
Ethics Statement, Author Contributions, Funding, and Competing Interests are
exempt from the Methods-subsection minimum. They must still satisfy the target
journal's content requirements.

## Required information density

A Methods subsection must normally identify:

1. input data, samples, groups, or analysis object;
2. preprocessing or inclusion/exclusion rules;
3. software/package and material parameters;
4. statistical test, threshold, correction, or quality-control rule;
5. output used by the next analysis or reported result.

A Results subsection must normally contain:

1. the biological question;
2. the analysis used to answer it;
3. quantitative findings, including sample size and statistics when available;
4. restrained biological interpretation;
5. the mapped figure or table citation;
6. a limitation when the evidence constrains interpretation.

Do not automatically expand text merely because advisory mode reports a short
section. First report the exact section count and deficit. Add material only
when verified evidence supports it; otherwise merge a related subsection,
narrow the claim, mark the limitation, or request missing material from the
user. Never pad with generic background, repeated methods, unsupported
mechanisms, or invented statistics.

## Journal overrides

A strict plan may use lower targets only when `length_policy.journal_override`
contains both:

- `source`: current official Author Guidelines URL or local file;
- `rationale`: the specific limit or article-format reason.

The user must approve the strict or overridden allocation as part of the
current manuscript plan. Advisory plans may use article-appropriate targets
without a journal override because those targets do not block delivery.
