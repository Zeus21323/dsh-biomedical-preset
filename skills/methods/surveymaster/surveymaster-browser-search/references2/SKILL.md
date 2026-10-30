---
name: surveymaster-browser-search-economics
version: 0.2.0
description: Economics, finance, management, and CNKI-relevant browser-use workflow for SurveyMaster Stage 2. Prefer CNKI plus Google Scholar browser branches and emit SurveyMaster candidate JSON.
---

# Economics / CNKI Browser Search

Use this route for economics, finance, management, policy, social-science
economics, Chinese academic literature, and CNKI-relevant topics.

## Source Priority

1. CNKI is the primary browser source for Chinese economics and China-specific
   policy/social-science literature.
2. Google Scholar may run in parallel as a browser discovery branch for
   international versions, citation trails, highly cited work, and real
   source-page discovery.
3. arXiv is not a default economics branch. Use it only for clearly technical
   quantitative/methodological topics or when the topic itself names arXiv or
   preprints.

Do not use `academic_search_cn`, academic-search, PaperSearch, PaperSurveyToFile,
WebSearch, DOI/title lookup, or any other non-browser retrieval tool.
Do not use OpenAlex, Crossref, Semantic Scholar, CORE, Lens, or any other
metadata/API endpoint as an economics candidate-discovery branch, even if the
endpoint is opened in browser-use/remote-browser. OpenAlex/Crossref are reserved
for `discover_and_resolve_papers.py` after
`$WORK/.cache/scratch/browser_candidates.json` already exists.

## Query Guidance

- CNKI queries should combine Chinese and English topic terms, policy/event
  names, author names, theory names, region names, and time ranges.
- Add empirical-method terms when relevant: `双重差分`, `断点回归`, `工具变量`,
  `面板数据`, `准自然实验`, `机制检验`, `异质性分析`.
- Add dataset/source names when relevant: `中国家庭追踪调查`, `工业企业数据库`,
  `上市公司`, `海关数据库`, `城市面板`, `县域数据`.
- For international context, use English keywords, method names, dataset names,
  and author names in a Google Scholar branch.

## CNKI Branch

- Search CNKI with one focused query per branch.
- If the CNKI search box does not respond to Enter, do not keep pressing Enter
  or retyping into the same input. Navigate directly to a CNKI results URL or
  advanced-search page.
- Inspect top-ranked results and open only the most relevant detail pages.
- Extract `篇名`, `作者`, `来源`, year/date, DOI when visible, abstract/摘要 if
  explicitly present, citation/download indicators when visible, and the CNKI
  detail URL.
- If CNKI indicates the user is not logged in, access is unavailable, or article
  reading/full metadata requires login, stop the CNKI branch immediately. Tell
  the user that reading CNKI literature usually requires logging in, preferably
  through an institutional account, campus network, or VPN, and wait for the
  user to confirm that they have logged in or enabled access before continuing.
  Do not continue in the background, do not substitute Google Scholar for the
  blocked CNKI branch, and do not switch to academic-search, PaperSearch,
  PaperSurveyToFile, WebSearch, DOI/title lookup, or API tools.
- If the user confirms CNKI access is ready, resume the same CNKI branch with
  browser-use/remote-browser and continue extracting candidates.

## Google Scholar Branch

- Use Scholar for discovery signals only: title, authors, year, venue hints,
  cited-by count, versions links, and real source-page links.
- Do not use Scholar snippets as `abstract_hint`.
- Open promising real host pages, such as publisher, author, institutional
  repository, NBER, SSRN, RePEc, CEPR, IZA, or journal pages, when available
  through the browser.
- If Scholar shows CAPTCHA or unusual-traffic pages, record the browser-state
  failure and retry with adjusted browser queries or other accessible source
  pages; do not switch to non-browser search.
- For abstract supplementation, open the real source pages discovered through
  Scholar, such as publisher/journal pages, NBER, SSRN, RePEc, CEPR, IZA,
  author pages, or institutional repositories. Do not use OpenAlex/Crossref API
  responses as the primary abstract source and do not count null/empty API
  abstract fields as a completed supplementation attempt.

## Output

Each branch writes `$WORK/.cache/scratch/browser_candidates.<branch>.json` using
the common SurveyMaster candidate JSON shape from `surveymaster-browser-search`.
