# Citations, Formatting, And Export

## Citation Integrity

- Maintain one canonical bibliography, preferably `references.bib`.
- Verify title, authors, year, venue, DOI or stable URL, and retraction/correction status when relevant.
- Cite only sources actually inspected or represented by verified metadata.
- Make the cited source support the exact sentence, not merely the broad topic.
- Resolve every citation key and remove accidental uncited bibliography entries when venue rules require it.
- Never create a citation because a sentence appears to need one.
- Write citations only as supported LaTeX commands backed by `references.bib`, for example `\parencite{facione1990,kamysheva2021}`. Never type the rendered `(Author, Year)` or `（作者, 年份）` string into canonical TeX.
- Let citeproc render the bibliography. Never hand-write it with `description`, `enumerate`, `itemize`, `thebibliography`, or `\bibitem`.

Use the supplied venue style as authority. If no style is specified and formatting materially depends on it, ask once or record a conservative explicit assumption.

## LaTeX Contract

- Keep `manuscript/mainbody.tex` canonical.
- Preserve the supplied class, packages, template structure, and anonymity requirements.
- Use semantic sections, native equations, stable labels, and automatic references.
- Keep figures under `manuscript/figures/` with relative paths.
- Avoid unsupported macros and hard-coded table, figure, equation, section, or bibliography numbers.
- Compile or preflight when tools are available; treat missing files, unresolved citations/references, and placeholders as blockers.

## DOCX Contract

Load the available `tex_to_docx` skill at runtime and follow its current workflow. Do not assume a developer-machine absolute path. Run its Pandoc preflight, including its checksum-verified trusted-mirror fallback when configured. Use the supplied journal guidelines or template when available.

Require:

- successful conversion and validation;
- resolved citations, bibliography, and internal cross-references;
- embedded media when the manuscript includes figures;
- editable native equations when equations exist;
- consistent table and typography rules;
- valid DOCX/OOXML structure;
- no unresolved authoring markers.

Do not use an ad hoc whole-paper `python-docx` or JavaScript generator as a fallback. If conversion dependencies are missing, deliver audited LaTeX and report the DOCX blocker.

## Final Inspection

When rendering tools are available, inspect page flow, headings, tables, equations, figure legibility, captions, bibliography separation, headers/footers, and anonymity. A mechanical audit does not replace visual inspection.

Immediately before delivery, run the `tex_to_docx validate-docx` command and `scripts/validate_docx_citation_links.py` against the final DOCX and canonical LaTeX source. Retain both JSON reports. Block delivery on any non-zero exit, missing OMML for source mathematics, invalid package structure, missing embedded source media, or citations without working bibliography hyperlinks/Word REF fields.
