---
name: surveymaster-browser-search-engineering-cs
version: 0.2.0
description: Engineering, computer-science, and software-engineering browser-use workflow for SurveyMaster Stage 2. Prefer arXiv, Google Scholar, IEEE/ACM, and DBLP browser branches and emit SurveyMaster candidate JSON.
---

# Engineering / Computer Science Browser Search

Use this route for engineering, computer science, software engineering, AI/ML,
data engineering, cybersecurity, networks, systems, databases, programming
languages, HCI, robotics, control, electronics, communications, materials, and
applied engineering topics.

## Source Priority

1. arXiv is a strong first-pass browser source for AI/ML, systems, security,
   robotics, signal processing, software engineering, and fast-moving technical
   topics.
2. Google Scholar may run in parallel as a browser discovery branch for citation
   trails, high-impact work, author versions, and real source-page discovery.
3. IEEE Xplore and ACM Digital Library are preferred browser sources for
   peer-reviewed engineering/CS publication pages when relevant.
4. DBLP is preferred for CS bibliographic verification, venue names, author
   disambiguation, and publication year.

Do not use academic-search, PaperSearch, PaperSurveyToFile, WebSearch, DOI/title
lookup, or any other non-browser retrieval tool.

## Query Guidance

- Concept search: combine method, task, system, dataset, benchmark, and
  application terms.
- Venue search: add conference, journal, or site names when venue quality
  matters, such as `site:dl.acm.org ICSE code review automation` or
  `site:ieeexplore.ieee.org federated learning wireless communication`.
- Reproducibility search: add `code`, `GitHub`, `artifact evaluation`,
  `dataset`, `benchmark`, `leaderboard`, `replication`, or `reproduction` when
  relevant.
- Standards search: add standard IDs, RFC numbers, protocol names, API names,
  or working group names when the topic is standards/specification oriented.

## arXiv Branch

- Search focused technical phrases.
- Extract title, authors, year, arXiv ID, abstract, category, URL, and PDF URL
  when visible.
- If a peer-reviewed version is visible, prefer the peer-reviewed source page as
  the candidate URL and keep arXiv as supporting evidence only when useful.
- Stop after one or two clearly off-topic arXiv query attempts and retry another
  browser source; do not switch to non-browser search.

## Google Scholar Branch

- Use Scholar for citation trails, highly cited papers, author versions, and
  real source-page discovery.
- Do not use Scholar snippets as `abstract_hint`.
- Open promising real host pages, such as publisher, OpenReview, conference,
  author, institutional repository, or project pages, when available.
- If Scholar shows CAPTCHA or unusual-traffic pages, record the browser-state
  failure and retry with adjusted browser queries or other source pages.

## IEEE / ACM / DBLP Branch

- Use IEEE Xplore or ACM Digital Library for peer-reviewed publication pages.
- Use DBLP to verify title, authors, venue, year, and publication version.
- For AI/ML venue checks, use NeurIPS, ICML, ICLR, OpenReview, ACL Anthology,
  CVF, or other official proceedings pages when relevant.
- Extract title, authors, venue, year, DOI, abstract when explicit, source URL,
  code/data links when visible, and benchmark/dataset names when relevant.

## Output

Each branch writes `$WORK/.cache/scratch/browser_candidates.<branch>.json` using
the common SurveyMaster candidate JSON shape from `surveymaster-browser-search`.
