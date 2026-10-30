---
name: tex-to-docx
description: Convert LaTeX or Markdown manuscripts into validated journal-ready DOCX files, with journal configuration, CSL bibliography formatting, media embedding, and optional numbered-reference bookmarks plus clickable Word REF fields. Use when a user asks to export .tex/.md to Word, apply a journal template or citation style, require numbered references and cross-links, or prepare verified DOCX submission deliverables.
---

# TeX to DOCX

Use this skill to produce DOCX manuscripts from LaTeX or Markdown while keeping
journal adaptation explicit and reproducible.

## Workflow

1. Ask for the target journal or citation/style system.
2. Run `list-profiles` and select a bundled profile when one matches. Treat fields marked
   `fallback` or `not-applicable` as editable submission defaults, not official requirements.
3. Read the target journal Author Guidelines when the bundled profile is publisher-wide,
   style-only, or the user names a more specific journal.
4. Create `journal_config.json` from the selected profile, optionally enriched by a current
   guidelines page or saved guidelines file.
5. Generate `journal_template.docx` from a bundled base template using the resolved profile.
6. Keep manuscript images beside the source tree and reference them with paths relative
   to the TeX/Markdown source; do not rewrite image references as machine-specific
   absolute paths.
7. Run the Pandoc preflight below. Export the manuscript with Pandoc using `--reference-doc journal_template.docx`.
   The bundled script runs Pandoc from the source directory and supplies an explicit
   resource path so relative `\includegraphics` references resolve consistently.
8. Report the selected profile and any fallback/not-applicable fields, plus remaining human
   checks, especially content requirements that a DOCX
   template cannot enforce.
9. Immediately before giving the DOCX to the user, run the final delivery audit below against
   the canonical source. Do not treat an earlier successful export as the final check.

## Main Script

Run:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py --help
```

Common one-step export:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py all \
  --source /path/mainbody.tex \
  --output /path/manuscript.docx \
  --guidelines-url "https://journal.example/forauthors" \
  --journal "Target Journal" \
  --language en \
  --work-dir /path/export_work \
  --bib /path/references.bib \
  --csl china-national-standard-gb-t-7714-2015-numeric.csl \
  --require-numbered-references \
  --line-spacing 1.5 \
  --toc
```

List the bundled journal/style profiles:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py list-profiles
```

Generate a template directly from a bundled profile:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py extract-config \
  --journal-profile nature \
  --output journal_config.json

python3 <skill_dir>/scripts/tex_to_docx.py make-template \
  --config journal_config.json \
  --output journal_template.docx
```

`--journal Nature` and `--csl nature.csl` also auto-select the `nature` profile. Use
`--journal-profile` when deterministic selection is important. Explicit config values override
the bundled profile. A specific journal's current Author Guidelines override publisher-wide
profiles such as ACS, Elsevier, IEEE, and RSC.

Staged export:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py extract-config \
  --guidelines-url "https://journal.example/forauthors" \
  --journal "Target Journal" \
  --language en \
  --output journal_config.json

python3 <skill_dir>/scripts/tex_to_docx.py make-template \
  --config journal_config.json \
  --language en \
  --output journal_template.docx

python3 <skill_dir>/scripts/tex_to_docx.py export \
  --source mainbody.tex \
  --output manuscript.docx \
  --config journal_config.json \
  --reference-docx journal_template.docx \
  --bib references.bib \
  --require-media \
  --toc
```

Use `--require-media` when the deliverable is expected to contain figures. It rejects a
LaTeX manuscript that only mentions figures in prose or legends without a resolvable
literal `\includegraphics{...}` command. Omit the flag for intentionally text-only
manuscripts.

Use `--require-numbered-references` for a numeric citation style. It requires
at least one real LaTeX citation command, rejects hand-written bibliography
blocks and missing BibTeX keys, requires a numeric CSL, numbers the bibliography,
and converts body `[N]` citations into clickable Word `REF _RefN \h` fields
backed by `_RefN` bookmarks. It fails rather than delivering plain-text or
unnumbered references.

Without `--require-numbered-references`, a numeric CSL enables numbered-reference
and Word REF validation only when the source contains real citation commands. If
the source has a `.bib` file but no `\cite{key}`, export in compatibility mode:
pass `nocite=@*` so the bibliography is still emitted, skip Word REF fields that
cannot be constructed, and print `CITATION_MODE fallback_nocite_all`. Never invent
or batch-insert citations merely to satisfy export. Use the strict flag when missing
body citations must block delivery.

Traditional `\bibliographystyle{...}` and `\bibliography{...}` commands may remain
in a LaTeX source passed with `--bib`; Pandoc/citeproc owns the DOCX bibliography.
Inline `thebibliography`, `\bibitem`, and hand-written References sections remain
forbidden because they can duplicate or bypass citeproc output.

With a selected journal profile, DOCX export preserves the profile's style-specific line
spacing, so body text, captions, and bibliography paragraphs may differ. Passing
`--line-spacing` explicitly is a global override: the exporter rewrites and validates every
document paragraph at that multiplier. Without a profile, the legacy fallback is 1.5 line
spacing. A numeric CSL whose citation layout uses `vertical-align="sup"`
produces superscript reference numbers and superscript Word REF field runs; brackets are
preserved only when the selected CSL includes them.

## Assets

- `assets/docx/template-en.docx` and `assets/docx/template-zh.docx`: base Pandoc
  reference DOCX templates copied from SurveyMaster export.
- `assets/csl/*.csl`: bundled citation styles, including AMA, APA, Nature,
  Science, Cell, IEEE, ACS, RSC, Elsevier, and GB/T 7714.
- `assets/journal_profiles/*.json`: machine-readable journal/style profiles with source URLs,
  verification dates, template values, CSL mappings, and field-level evidence status.

## Dependencies

Required for full DOCX export:

- A native, runnable `pandoc`. The exporter resolves `PANDOC_PATH`, `PATH`, a
  platform-compatible `pypandoc` runtime, then the tex-to-docx managed cache.
- Python packages: `python-docx`, `beautifulsoup4`, `requests`, `pyyaml`.

Before export, run:

```bash
python3 <skill_dir>/scripts/ensure_pandoc.py
```

The helper first accepts an already runnable Pandoc. Otherwise it downloads the
platform-specific archive recorded in `assets/pandoc_releases.json` into a user
cache, verifies the official SHA-256 digest, extracts it, and verifies
`pandoc --version`. It does not require Homebrew and selects the native macOS
arm64 archive on Apple Silicon.

If the official GitHub asset is unreachable, use a trusted organization-controlled mirror:

```bash
python3 <skill_dir>/scripts/ensure_pandoc.py \
  --mirror-url-template 'https://mirror.example/pandoc/{version}/{asset}'
```

The official URL is attempted first, then configured mirrors in order. The mirror must
preserve the upstream asset bytes: the helper rejects a mismatched SHA-256 or a binary
that cannot run on the host. Repeat `--mirror-url-template` for multiple mirrors, or set
newline-separated templates in `TEX_TO_DOCX_PANDOC_MIRRORS`. Never silently install an
x86_64 binary on an arm64 host, recommend Rosetta as the primary fix, or download from an
unverified arbitrary mirror. `pypandoc-binary` is optional, not the only installation path.

If every verified source fails, the script can still extract JSON and generate a reference
DOCX template, but final export must stop with `dependency_not_found` or
`pandoc_download_failed`; do not replace the canonical LaTeX-to-DOCX route with a custom
whole-document Word generator.

For LaTeX sources, the exporter scans literal `\includegraphics{...}` commands before
running Pandoc. It fails with `image_not_found` when a referenced file cannot be resolved
from the source directory, the invocation directory, or a literal `\graphicspath` entry.
Keep DOCX-bound images in a portable format such as PNG or JPEG whenever possible.

## Boundaries

`journal_template.docx` controls Word styling only: fonts, spacing, margins,
headings, captions, bibliography style properties, and related reference-doc
behavior. It does not enforce article content rules.

Always keep `journal_config.json` as the source of truth for:

- abstract type and word limit;
- article structure;
- required statements;
- figure file requirements;
- data/code availability policy;
- reporting guidelines;
- human verification notes.

Do not report every bundled value as an official journal requirement. Read
`journal_profile_evidence` in the generated config. `official` and `official-template` values
are sourced requirements; `fallback` values are readable defaults; `not-applicable` means the
selected standard (for example GB/T 7714) does not govern that Word-layout field.

Read `references/journal_config.md` when editing or extending the JSON schema.

## Validation

Run this after all DOCX generation and post-processing, immediately before delivery:

```bash
python3 <skill_dir>/scripts/tex_to_docx.py validate-docx \
  --docx /path/manuscript.docx \
  --source /path/mainbody.tex \
  --report /path/docx_delivery_audit.json
```

Deliver the DOCX only when this command exits zero and reports `"status": "passed"`.
The audit verifies the DOCX package, non-empty Word content, embedded source images, and
native editable equations. It detects source math conservatively and counts equations by
the OMML namespace URI, never by a literal prefix string. If the source contains math but
the DOCX contains no `{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath`,
stop with `docx_omml_missing`. The exporter also runs this audit automatically, but the agent
must rerun it after all later changes so the audited file is exactly the delivered file.

After creating a DOCX, open it or inspect it as a zip if needed. A valid DOCX
must contain at least `word/document.xml` and should contain `word/styles.xml`.
When the LaTeX source contains literal `\includegraphics` commands, require the DOCX to
contain corresponding main-document image relationships and files under `word/media/`.
The exporter performs this check automatically and fails with `docx_media_missing` if
Pandoc returns a document without the expected embedded images. Textual figure citations,
`\ref{...}`, captions, and Figure Legends do not count as embedded images.
When numbered references are required, also inspect `word/document.xml` for
`_RefN` bookmarks and `REF _RefN \h` fields. A DOCX with formatted bibliography
text but no such fields is invalid.
For superscript numeric styles, every REF instruction run must contain
`w:vertAlign w:val="superscript"`; baseline reference numbers are invalid.
For journal submission, also check generated `journal_config.json` against the
current Author Guidelines page manually.
