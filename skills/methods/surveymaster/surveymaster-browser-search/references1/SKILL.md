---
name: surveymaster-browser-search-biomedical
version: 0.2.0
description: Biomedical and life-science browser-use workflow for SurveyMaster Stage 2. Prefer PubMed plus Google Scholar browser branches and emit SurveyMaster candidate JSON.
---

# Biomedical / Life-Science Browser Search

Use this route for biomedical, medical, clinical, pharmaceutical, genetics,
biology, public-health, and life-science topics.

## Source Priority

1. PubMed is the primary browser source for biomedical metadata, abstracts,
   PMID/DOI discovery, study type, and biomedical terminology. When a PubMed
   detail page already provides title/authors/year/journal/DOI/abstract, write
   those fields into the candidate JSON; later metadata APIs should enrich only
   and must not become a blocking dependency.
2. PMC and publisher/journal detail pages are preferred real source pages after
   PubMed, especially for explicit abstracts, article numbers,
   volume/issue/pages, and DOI.
3. Google Scholar may run in parallel as a browser discovery branch for citation
   trails, highly cited papers, full-text/source-page discovery, preprints, and
   cross-disciplinary versions.
4. Scholar is not a final metadata source; open PubMed, PMC,
   publisher/journal pages, or other real source pages before extracting final
   metadata from a promising Scholar result.
5. OpenAlex/Crossref are not browser discovery sources. They may only be used
   by the local resolver after candidate JSON exists, and OpenAlex rate limits
   must not stop Stage 2.

Do not use academic-search, PaperSearch, PaperSurveyToFile, WebSearch, DOI/title
lookup, or any other non-browser retrieval tool.

## Query Guidance

- Combine scientific terms, synonyms, abbreviations, organisms, genes/proteins,
  diseases, interventions/exposures, outcomes, and study-type words.
- Prefer review, systematic review, meta-analysis, clinical guideline,
  randomized trial, cohort, case-control, and high-quality primary-study terms
  when they match the topic.
- Use date terms or filters only when recency matters.

## PubMed Branch

- Start at `https://pubmed.ncbi.nlm.nih.gov/`.
- Search one focused query per branch.
- Inspect top-ranked results and open only the most relevant result detail
  pages.
- Extract title, authors, journal, year/date, PMID, DOI, URL, and explicit
  abstract when available.
- Ignore navigation bars, author profile links, journal links, similar-article
  widgets, metrics, citation tools, sharing links, and footer links unless they
  are needed to open the article detail or full abstract.

## Google Scholar Branch

- Use Scholar as a browser discovery branch, not as an abstract source.
- Extract title, authors, year, venue hints, cited-by count when visible,
  versions links, and real source-page links.
- Do not use Scholar snippets as `abstract_hint`.
- Open promising real host pages when available and extract metadata from those
  pages.
- If Scholar shows CAPTCHA or unusual-traffic pages, record the browser-state
  failure and retry with PubMed or another browser-accessible source page; do
  not switch to non-browser search.

## Output

Each branch writes `$WORK/.cache/scratch/browser_candidates.<branch>.json` using
the common SurveyMaster candidate JSON shape from `surveymaster-browser-search`.
