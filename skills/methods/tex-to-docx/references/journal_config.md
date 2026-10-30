# Journal Config Reference

`journal_config.json` records journal requirements extracted from Author
Guidelines. Extraction is heuristic; verify against the official page before
submission.

Core fields:

- `journal`: target journal name.
- `source`: Author Guidelines URL or local file path.
- `language`: `en` or `zh`.
- `article_type`: article type used for extraction and checking.
- `body`: Word body style preferences.
  - `font`
  - `font_size_pt`
  - `line_spacing`: `single`, `1.5`, or `double`
  - `margin_inches`
- `title`: Word title style preferences.
- `headings`: Word heading style preferences.
- `abstract`:
  - `word_limit`
  - `structured`
  - `recommended_headings`
- `references`:
  - `style`
  - `csl_file`
- `figures`:
  - `min_dpi`
  - `preferred_formats`
- `required_statements`: manuscript statements expected by the journal.
- `notes`: human checks and extraction caveats.
- `journal_profile`: selected bundled profile id.
- `journal_profile_scope`: `journal`, `publisher-template`, `publisher-style`,
  `style-system`, or `reference-standard`.
- `journal_profile_sources`: official source titles and URLs used to build the profile.
- `journal_profile_evidence`: field-level status and caveats.

Evidence status:

- `official`: explicitly stated in an official guide.
- `official-template`: taken from an official publisher template.
- `partial-official`: the content rule is official but Word typography is a fallback.
- `fallback`: readable initial-submission default; verify with the selected journal.
- `not-applicable`: the selected citation/reference standard does not govern this layout field.

Template mapping:

- `body` maps to Word `Normal`, `Body Text`, and `First Paragraph`.
- `title` maps to Word `Title`.
- `headings.heading_1` maps to Word `Heading 1`.
- `headings.heading_2` maps to Word `Heading 2`.
- `caption` maps to Word `Caption`.
- `bibliography` maps to Word `Bibliography`, including an optional hanging indent.
- `font_east_asia` sets the Word `w:eastAsia` font independently from the Latin font.

Profile selection:

```bash
python3 scripts/tex_to_docx.py list-profiles
python3 scripts/tex_to_docx.py extract-config --journal-profile nature --output journal_config.json
```

The script can also match an exact profile alias from `--journal` or a mapped filename from
`--csl`. Use an explicit profile id to avoid ambiguity. User-supplied config values override
profile values; specific current journal guidelines override generic publisher/style profiles.

Do not rely on `journal_template.docx` to enforce content constraints such as
word limits, ethical statements, reporting checklists, or figure upload formats.
Those must be checked separately against this JSON and the official guidelines.
