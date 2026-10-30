---
name: surveymaster-browser-search
version: 0.2.0
description: Child instruction router for SurveyMaster Stage 2 browser-use/remote-browser candidate discovery. Read this from surveymaster-literature-library before browser searching. Routes biomedical/life-science, economics/social-science, and engineering/computer-science topics to domain-specific browser workflows and requires browser-only candidate JSON output.
---

# SurveyMaster Browser Search Router

Use this child instruction file during Stage 2 candidate discovery. It defines
browser-use/remote-browser search routing only; `surveymaster-literature-library`
owns insertion, validation, metadata resolution, and coverage gates.

## Hard Contract

- Candidate discovery is browser-only. Do not start, continue, recover, or
  supplement candidate discovery with `PaperSurveyToFile`, `PaperSearch`,
  academic search APIs, generic WebSearch, DOI/title lookup APIs,
  OpenAlex/Crossref/Semantic Scholar/CORE/Lens API endpoints, or other
  non-browser retrieval tools. Opening an API endpoint in
  browser-use/remote-browser does not make it a valid browser discovery branch.
  OpenAlex/Crossref may be used only by the downstream metadata resolver after
  merged browser candidates have already been written.
- Do not ask the user to choose between browser-use and academic-search. Never
  mark academic-search or any non-browser retrieval tool as recommended.
- Treat browser-use/remote-browser as a browser-automation capability category,
  not as a literal tool-name requirement. Equivalent runtime-exposed browser
  tools include deferred MCP tools such as `mcp_remote_browser_*` when they can
  open real pages, navigate/search, inspect page content, and write JSON
  candidates.
- If browser-use/remote-browser seems unavailable from planning context, a
  current tool list, or a missing convenience shortcut, first run the runtime's
  tool discovery/find_tools mechanism with queries such as `browser`,
  `remote-browser`, `remote browser`, `browser automation`, and `MCP remote
  browser`. If matching tools such as `mcp_remote_browser_*` are found, activate
  and use them. Treat only a post-discovery actual invocation failure showing
  the browser service is not started as unavailable; then stop and ask the user
  to enable browser-use/remote-browser.
- Do not call `ask_user`, `request_user_input`, or any choice UI with
  academic-search, PaperSearch, PaperSurveyToFile, WebSearch, DOI/title lookup,
  API endpoint search, or other non-browser options. If a UI prompt is
  unavoidable, it may only ask the user to enable browser-use/remote-browser or
  stop Stage 2; it must not include any recommended fallback.
- Every branch must write a JSON array to
  `$WORK/.cache/scratch/browser_candidates.<branch>.json`. After all branches
  complete, the orchestrator merges branch files into
  `$WORK/.cache/scratch/browser_candidates.json`.

## Routing

Before browser searching, classify `subject`, `topic`, `focus_points`, and seed
paper content. Then read the matching reference file(s):

1. Biomedical, medical, clinical, pharmaceutical, genetics, biology,
   public-health, or life-science topics:
   - Read `references1/SKILL.md`.
   - Prefer PubMed and Google Scholar browser branches.
2. Economics, finance, management, policy, social-science economics, Chinese
   academic literature, or CNKI-relevant topics:
   - Read `references2/SKILL.md`.
   - Prefer CNKI and Google Scholar browser branches.
3. Engineering, computer science, software engineering, AI/ML, electronics,
   automation, materials, communications, robotics, or applied engineering
   topics:
   - Read `references3/SKILL.md`.
   - Prefer arXiv, Google Scholar, IEEE Xplore, ACM Digital Library, and DBLP
     browser branches as appropriate.
4. Mixed or interdisciplinary topics:
   - Read every relevant reference file.
   - Apply each route to the matching focus points, but keep all outputs in the
     same candidate JSON shape.
5. Ambiguous topics:
   - Use Google Scholar plus the nearest specialized route. If the first
     branch is off-topic, retry with a narrower browser query rather than
     switching to non-browser search.

## Common Browser Workflow

- Give each browser-use/remote-browser branch a concrete task: open the chosen
  site, search one keyword phrase, inspect only top-ranked result pages, open
  the most relevant result detail pages when needed, extract candidate fields,
  and save a JSON array to the branch file. Name the exact output path in the
  task, for example:

  ```text
  $WORK/.cache/scratch/browser_candidates.pubmed_query1.json
  ```

- Use this page-inspection order where the browser tool exposes these actions:
  call `interactive_elements` first; if title/result links are not visible,
  call `snapshot` or `page_info` with a bounded character limit; search the
  returned content for `Abstract`, `DOI`, `PMID`, `arXiv`, `Proceedings`,
  `Conference`, `Journal`, `PDF`, `篇名`, `作者`, `来源`, and the user's
  keywords.
- Ignore navigation bars, footers, author-profile links, journal links,
  recommendation widgets, metrics widgets, service links, and unrelated
  controls unless they are needed to open a paper detail page.
- Inspect only the top-ranked result pages. Extract the top 10-20 candidates
  per query; do not traverse all search results.
- Deduplicate obvious duplicates before saving a branch file. Use title, DOI,
  PMID, arXiv ID, DBLP key, URL, and author/year as duplicate signals.
- If a site blocks browsing, shows CAPTCHA/unusual-traffic warnings, requires
  login, or returns no useful results, record that branch failure in the Stage 2
  report and retry with browser-use/remote-browser using an adjusted query or
  site. Do not switch to academic-search, PaperSearch, PaperSurveyToFile,
  WebSearch, DOI/title lookup, API endpoint search, or other non-browser
  retrieval tools.

## Candidate JSON Shape

Every browser branch must save a JSON array with this shape. `abstract_hint`
may only come from an explicit Abstract section; do not use search-result
snippets as abstracts.

```json
[
  {
    "title": "Paper title",
    "doi": "10.xxxx/yyyy",
    "url": "https://example.com/paper",
    "year_hint": "2024",
    "venue_hint": "Journal or Conference Name",
    "authors_text": "Author A, Author B",
    "abstract_hint": "Short abstract if available",
    "source": "browser-use"
  }
]
```
