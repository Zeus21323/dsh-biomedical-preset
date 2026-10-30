---
name: engineering-cs-priority
description: Standardize engineering, computer science, and software engineering research workflows that use browser_use or remote-browser tools. Use when the user asks for computer science, software engineering, artificial intelligence, machine learning, data engineering, cybersecurity, networking, distributed systems, databases, programming languages, HCI, robotics, control, electronics, communications, or applied engineering technology. Prioritize arXiv first for discovery, then use Google Scholar plus NeurIPS, ICML, and ICLR venue checks as auxiliary sources when relevant; use IEEE Xplore, ACM Digital Library, DBLP, official standards/specifications, and source repositories for verification, venue metadata, reproducibility, benchmarks, datasets, and implementation evidence.
---

# Engineering And Computer Science Priority

Use this skill to standardize engineering and computer-science literature research. It defines source priority, venue screening, standards/source-code verification, and output requirements. Browser operation rules come from `browser_use` or the companion remote-browser skill.

## Required Companion Skill

Before using browser tools, read and follow the relevant search and browser-operation rules from:

`browser_use`

Then apply the constraints in this skill.

Read this skill file once per task and keep its routing and search rules in working memory. Do not repeatedly reopen or reread this SKILL.md unless the user asks to inspect or modify it, the task resumes after context loss, or there is a concrete reason to verify a changed file.

Use the lifecycle rules for `mcp_remote_browser_*` tools when available: list devices first, create a task-specific session, inspect tabs before opening duplicate tabs, prefer structured element refs, request approval for sensitive actions, and finalize tabs before ending browser work.

## Research Workflow

1. Classify whether the request is engineering or computer-science related:
   - Computer science and software engineering: AI, machine learning, deep learning, natural language processing, computer vision, software engineering, programming languages, compilers, databases, data mining, distributed systems, operating systems, cloud computing, networking, cybersecurity, privacy, HCI, visualization, robotics, embedded systems, and systems performance.
   - Broader engineering: electrical engineering, communications, control, automation, signal processing, mechanical engineering, civil engineering, materials engineering, manufacturing, energy systems, and applied engineering technology.
   - If the request is not engineering or computer-science related, use the general research workflow from the main standardization skill instead.
2. For engineering/computer-science requests, search arXiv first:
   - Start with arXiv for first-pass discovery, especially for AI/ML, systems, security, robotics, signal-processing, software engineering, and fast-moving engineering topics.
   - Use Google Scholar as an auxiliary source for citation trails, highly cited work, author versions, and full-text discovery after the initial arXiv pass.
   - For AI/ML topics, use NeurIPS, ICML, and ICLR proceedings/openreview pages as high-priority auxiliary venue checks when relevant.
   - Use IEEE Xplore and ACM Digital Library after arXiv/Google Scholar when peer-reviewed engineering or CS conference/journal verification is needed.
   - Use DBLP for computer-science bibliographic verification, venue names, author disambiguation, and publication metadata.
   - Use Semantic Scholar, OpenAlex, Crossref, publisher pages, author homepages, and institutional repositories as supplementary sources when they improve metadata or access.
3. Prioritize venue quality and relevance:
   - For computer science, prefer top or field-appropriate peer-reviewed venues when relevant: NeurIPS, ICML, ICLR, ACL, EMNLP, CVPR, ICCV, ECCV, SIGKDD, WWW/The Web Conference, SIGIR, CHI, UIST, ICSE, FSE, ASE, PLDI, POPL, OOPSLA, SIGMOD, VLDB, ICDE, SOSP, OSDI, NSDI, SIGCOMM, USENIX Security, IEEE S&P, ACM CCS, NDSS, SIGGRAPH, ICRA, IROS, RSS, and strong field journals such as IEEE/ACM Transactions and ACM TO* journals.
   - For broader engineering, prefer IEEE, ACM, ASME, ASCE, Elsevier, Springer, Wiley, Nature/Science family, and field-appropriate society journals or conferences.
   - Do not rank by venue prestige alone. Balance venue quality with direct relevance, recency, method quality, benchmark comparability, dataset suitability, and reproducibility.
4. Verify standards, specifications, and official technical sources:
   - For protocols, APIs, security standards, file formats, benchmarks, or engineering specifications, prefer official standards bodies and maintainers: IEEE, IETF RFCs, ISO/IEC, W3C, WHATWG, NIST, ETSI, 3GPP, Khronos, CNCF, Linux Foundation, official language/runtime docs, and project governance pages.
   - Cross-check claims about standards or APIs against the official specification or documentation, not only papers or blog posts.
   - Record version numbers, publication/update dates, standard IDs, RFC numbers, repository tags/releases, and deprecation status when relevant.
5. Check reproducibility and implementation evidence:
   - Prefer papers with released code, datasets, model cards, benchmark scripts, artifact evaluation badges, replication packages, or documented experimental settings.
   - Verify code repositories only when relevant. Record repository URL, owner, license if visible, latest release/tag, commit/date if needed, stars only as a weak signal, and whether the repository matches the paper.
   - For benchmark claims, verify dataset name/version, metric definition, evaluation split, baseline comparability, and whether numbers come from the original paper, a leaderboard, or an independent reproduction.
6. Use arXiv carefully:
   - arXiv is the first-pass discovery source for engineering and CS questions, especially AI/ML and systems work, but it is not automatically peer-reviewed evidence.
   - Search arXiv with one or two focused queries first. If results are sparse or off-topic, stop retrying and use Google Scholar, NeurIPS, ICML, ICLR, IEEE, ACM, DBLP, publisher pages, or official repositories.
   - When an arXiv paper has a conference/journal version, cite and prefer the peer-reviewed version while noting the arXiv version if it provides full text.
7. Ask before downloading highly relevant literature:
   - To improve response speed, do not download papers during the first-pass literature search unless the user explicitly asked for downloads at the start.
   - First identify and summarize the most relevant papers, then ask the user whether they want the full papers downloaded.
   - Only download complete papers after the user gives permission and access is allowed. Save each downloaded file into the workspace and also provide the same file in the conversation area through the platform's user-visible file/artifact mechanism.
   - If a paper cannot be downloaded because of access limits, login restrictions, paywalls, missing PDF links, or technical failures, explain the specific reason and keep the bibliographic metadata.
   - When the user explicitly asks to download literature, both destinations are required: workspace file plus conversation-area file/artifact. Do not treat a browser tab, source URL, or metadata-only citation as a completed download.
8. Use multi-source verification:
   - Verify title, authors, venue, year, DOI/arXiv ID, citation count, benchmark numbers, code availability, standard version, and implementation status when they affect the answer.
   - Cross-check important claims against IEEE/ACM/publisher pages, DBLP, Google Scholar, arXiv, official standards, documentation, source repositories, and benchmark/leaderboard pages when available.
   - Separate source-supported facts from inference.
9. Synthesize rather than paste:
   - Do not dump full abstracts, search result pages, README files, or benchmark tables.
   - Summarize the literature in the user's requested language.
   - Cite sources with links and identifiers where possible.

## Query Guidance

Use engineering/CS-friendly search strategies:

- Concept search: combine method, task, system, dataset, benchmark, and application terms, for example `retrieval augmented generation software engineering benchmark`, `distributed consensus Byzantine fault tolerance survey`, or `graph neural network traffic prediction IEEE`.
- Venue search: add conference or journal names when the user asks for top work, such as `site:dl.acm.org ICSE code review automation` or `site:ieeexplore.ieee.org federated learning wireless communication`.
- Standards search: add standard IDs, RFC numbers, protocol names, API names, or working-group names, such as `RFC QUIC congestion control`, `IEEE 802.11be standard`, or `W3C WebGPU specification`.
- Reproducibility search: add `code`, `GitHub`, `artifact evaluation`, `dataset`, `benchmark`, `leaderboard`, `replication`, or `reproduction`.
- arXiv search: search arXiv first with focused technical terms and stop after one or two failed/off-topic attempts.
- AI/ML venue search: use Google Scholar plus NeurIPS, ICML, and ICLR proceedings/OpenReview pages as auxiliary checks for venue versions, accepted papers, author versions, and citation context.
- DBLP search: use exact author names, paper titles, venue acronyms, and year ranges for bibliographic verification.

## Parallel Search Guidance

Use parallel search to reduce latency and improve coverage, but keep source hierarchy clear:

- arXiv + Google Scholar: run these in parallel when possible, with arXiv as first-pass discovery and Google Scholar as auxiliary citation/full-text discovery.
- arXiv + NeurIPS/ICML/ICLR: run in parallel for AI/ML topics when venue verification matters.
- IEEE/ACM + Google Scholar: use after or alongside arXiv when peer-reviewed engineering/CS publication pages and citation trails are needed.
- DBLP + publisher pages: use in parallel to verify computer-science metadata, venue, author identity, and publication year.
- Standards/docs + literature: run in parallel when the question concerns protocols, APIs, libraries, engineering specifications, or implementation guidance.
- Deduplicate results by title, DOI, arXiv ID, DBLP key, author/year, repository, and venue before summarizing.
- If sources disagree, report the disagreement and prefer the most authoritative source for the claim type: official specs for standards, publisher/DBLP for bibliographic metadata, benchmark pages or original papers for evaluation numbers, and repositories for implementation status.

## Page Handling Efficiency

Engineering and CS pages often include large amounts of irrelevant content: navigation bars, citation widgets, author profile links, recommendation panels, login prompts, metrics panels, README badges, issue lists, and generated documentation sidebars. Avoid spending excessive attention on those parts.

Use this order when extracting useful results:

1. Call `interactive_elements` first.
2. If article title links or repository files do not appear in `interactive_elements`, do not immediately analyze the full snapshot.
3. Call `snapshot` or `page_info`, but limit `max_chars` if the tool supports it.
4. Search within returned content for the user's keywords, `Abstract`, `DOI`, `arXiv`, `Proceedings`, `Conference`, `Journal`, `PDF`, `Code`, `Dataset`, `Artifacts`, `Benchmark`, `Release`, and `License`.
5. Read useful abstracts, methodology summaries, benchmark tables, and repository metadata carefully.
6. Ignore author links, metrics links, recommendation links, service links, navigation links, generated API sidebars, and footer links unless they are directly needed.
7. Open only the most relevant 1-5 papers, specifications, or repositories when necessary.

## Output Standard

Provide a concise research answer with:

- Direct answer or technical conclusion first.
- A short evidence table when useful: title, authors, venue, year, source type, DOI/arXiv ID, code/data availability, benchmark/dataset, and relevance.
- A clear note that the engineering/CS route was used.
- Which searches were used, such as arXiv first, Google Scholar auxiliary search, NeurIPS/ICML/ICLR venue checks, IEEE/ACM, DBLP, standards/docs, or repository verification, and why.
- Whether arXiv results are preprints or peer-reviewed versions.
- Which top or field-appropriate venues were checked, and whether venue metadata was verified.
- Relevant literature closest to the user's question. Selected papers must be the most relevant and highest-quality available.
- Important limitations: access restrictions, unverified code, missing benchmark details, stale citation counts, standard version uncertainty, or disagreement between sources.
- A final question asking whether the user wants the most relevant full papers downloaded, unless the user already requested downloads.
