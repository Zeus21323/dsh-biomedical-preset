---
name: economics-cnki-priority
description: Standardize economics research workflows that use browser_use or remote-browser tools for Chinese and international economics literature search. Use when the user asks for economics, finance, political economy, industrial organization, macroeconomics, microeconomics, econometrics, development economics, labor economics, public finance, international trade, Chinese economic policy, or Chinese-language academic literature. Prioritize CNKI and run CNKI with Google Scholar in parallel when useful, then use arXiv as a limited auxiliary source, prioritize journals in the Renmin University of China Core Journal Catalogue for Economics A and B, then consider other top economics journals and highly cited economics papers.
---

# Economics CNKI Priority

Use this skill to standardize economics literature research. It defines source priority, journal screening, and output requirements for economics questions. Browser operation rules come from `browser_use` or the companion remote-browser skill.

## Required Companion Skill

Before using browser tools, read and follow the relevant search and browser-operation rules from:

`browser_use`

Then apply the constraints in this skill.

Read this skill file once per task and keep its routing and search rules in working memory. Do not repeatedly reopen or reread this SKILL.md unless the user asks to inspect or modify it, the task resumes after context loss, or there is a concrete reason to verify a changed file.

Use the lifecycle rules for `mcp_remote_browser_*` tools when available: list devices first, create a task-specific session, inspect tabs before opening duplicate tabs, prefer structured element refs, request approval for sensitive actions, and finalize tabs before ending browser work.

## Research Workflow

1. Classify whether the request is economics-related:
   - Economics and finance: macroeconomics, microeconomics, econometrics, finance, industrial organization, development economics, labor economics, public finance, international trade, regional economics, environmental economics, agricultural economics, political economy, economic history, Chinese economic policy, or empirical economic research.
   - If the request is not economics-related, use the general research workflow from the main standardization skill instead.
2. For economics-related requests, search CNKI first:
   - Start from CNKI and use Chinese keywords, English keywords, author names, theory names, policy names, dataset names, region names, and time periods from the user request.
   - When the task needs faster discovery, citation context, or Chinese + international coverage, run CNKI and Google Scholar searches in parallel when browser/tool capacity allows. CNKI remains the primary source for Chinese economics literature; Google Scholar is a high-priority parallel source for citation trails, international versions, and full-text discovery.
   - If the CNKI search box does not respond to Enter, do not keep retrying Enter or typing into the same field. Navigate directly to a CNKI search results URL with the encoded query, or use CNKI advanced search/navigation controls.
   - Use CNKI advanced search when ordinary keyword search returns noisy or sparse results.
   - Prefer journal articles over non-peer-reviewed web pages when the user asks for academic evidence.
   - Do not over-focus on navigation bars, footers, recommendation panels, service links, author profile links, journal links, AI-reading links, or other page chrome. Focus on useful result metadata and read relevant abstracts carefully.
   - Record title, authors, journal, year, issue, DOI if available, CNKI source URL, keywords, abstract, citation count when visible, and download/access status.
   - CNKI full-text downloads usually require login, institutional subscription, campus IP, or VPN. When the user asks to download CNKI papers, immediately prompt the user to log in to CNKI or enable institution/VPN access before any CNKI full-text download attempt. The prompt must tell the user that an institutional account, campus IP, or VPN is preferred because a personal CNKI account may still fail to download paid/subscription articles. Do not waste attempts trying to download CNKI full text without login/access unless the page clearly marks the item as free/open access.
   - Only download CNKI items that are free/open access or accessible through the user's active login/institution/VPN session. If a CNKI item requires payment, subscription, or unavailable authorization, do not try to bypass access; report the access reason and keep the metadata.
   - If the user does not confirm login/access or does not respond after a reasonable wait, do not keep waiting on CNKI. Continue discovery through Google Scholar, `academic_search_cn`, publisher pages, author pages, institutional repositories, or other legal full-text sources, and clearly state that CNKI full text was not downloaded because login/access was not confirmed.
3. Use Google Scholar and arXiv as high-priority supplementary sources after CNKI:
   - Use Google Scholar early to identify highly cited economics papers, English versions of Chinese topics, related international literature, and citation networks.
   - Google Scholar is a discovery source, not a bulk downloader or stable PDF host. Use it to find title metadata, citation trails, "all versions", and candidate full-text links, then open the real source page such as a publisher, author page, institutional repository, SSRN, NBER, RePEc, CEPR, IZA, or journal page.
   - Do not batch-download PDFs through Google Scholar result links. Process candidate full-text links one paper at a time; after each download, verify HTTP status, content type, and `%PDF-` file header. If Google Scholar or the target source returns CAPTCHA, unusual-traffic, access denied, HTML, login, or paywall content, stop that download path and report the concrete reason.
   - If the query is clearly about Western economics, international economics literature, classic economic theory, English-language empirical work, or non-China-specific research, do not repeatedly try many CNKI keyword combinations. After one focused CNKI pass, move early to `academic_search_cn` and Google Scholar.
   - For economics download tasks, do not use arXiv before the Google Scholar/full-text-discovery path. Use Google Scholar and `academic_search_cn` first to find real source pages, then try publisher pages, author pages, institutional repositories, NBER, SSRN, RePEc, CEPR, IZA, and journal pages.
   - Use arXiv as a fallback download source only after Google Scholar/full-text discovery and the real-source pages fail to provide a downloadable PDF, unless the user explicitly requested arXiv/preprints. arXiv fallback is most suitable for working papers, quantitative methods, econometrics, finance, machine learning in economics, network economics, or recent international research that may not yet be published.
   - When using arXiv as fallback, try at most one or two focused arXiv queries; if results are sparse or off-topic, stop retrying arXiv and report that the required sources did not provide downloadable PDFs.
   - Do not use arXiv as the primary source for ordinary economics literature downloads, Chinese economics topics, microeconomics theory/course topics, or CNKI/Google Scholar download requests. arXiv may supplement methods/working-paper discovery only after CNKI/Google Scholar or other economics sources have been tried.
   - If the user explicitly asks to use CNKI, Google Scholar, or economics literature sources, do not pivot to arXiv just because arXiv returns many PDFs. A large arXiv result count is not a substitute for the requested source route.
   - Treat Google Scholar and arXiv as higher-priority supplementary sources than ordinary web search, news pages, blogs, or unsourced secondary summaries.
   - Do not treat arXiv preprints as peer-reviewed journal evidence unless later publication is verified.
   - Cross-check important Google Scholar/arXiv findings against journal pages, publisher pages, NBER/SSRN/RePEc/CEPR/IZA pages, author homepages, or institutional repositories when possible.
   - OpenAlex, Semantic Scholar, Crossref, Unpaywall, or similar APIs are not the main discovery route for economics literature. Do not start these API searches unless the user explicitly requests them, or unless the CNKI + Google Scholar/`academic_search_cn` route has already been completed and DOI, author, publication, citation, or open-access-link metadata still needs supplementation.
   - If OpenAlex, Semantic Scholar, Crossref, Unpaywall, or similar APIs are used, state that they are metadata/open-access verification tools only. Do not let API results replace the source priority of CNKI, Google Scholar, `academic_search_cn`, publisher pages, author pages, institutional repositories, NBER, SSRN, RePEc, CEPR, IZA, or journal pages.
4. Prioritize the Renmin University of China Core Journal Catalogue for Economics:
   - First screen journals listed in the Renmin University of China core journal catalogue, especially Economics A and Economics B.
   - Prefer Economics A over Economics B when relevance and evidence quality are similar.
   - Do not claim that a journal is in RUC Economics A/B unless the catalogue or a reliable source confirms it.
   - If the catalogue is not accessible or the journal classification cannot be verified, state that the classification was not verified.
5. Then consider other top economics journals and highly cited economics papers:
   - For Chinese-language literature, also consider recognized CSSCI, 北大核心, and influential economics journals when relevant, but keep RUC Economics A/B as the priority when the user specifically wants top Chinese economics literature.
   - For international literature, consider top economics journals and field journals such as AER, QJE, JPE, Econometrica, Review of Economic Studies, Journal of Finance, Review of Financial Studies, Journal of Financial Economics, Journal of Labor Economics, Journal of Development Economics, Journal of International Economics, and other field-appropriate journals.
   - Prefer highly cited papers only when they are relevant to the user's question. Do not rank by citation count alone.
   - Balance citation count with recency, identification strategy, data quality, journal quality, and direct relevance.
6. Ask before downloading highly relevant literature:
   - To improve response speed, do not download papers during the first-pass literature search unless the user explicitly asked for downloads at the start.
   - First identify and summarize the most relevant papers, then ask the user whether they want the full papers downloaded.
   - Only download complete papers after the user gives permission and access is allowed. The default required deliverable is a PDF. Save each downloaded PDF into the workspace and also provide the same PDF in the conversation area through the platform's user-visible file/artifact mechanism.
   - If a paper cannot be downloaded because of access limits, login restrictions, paywalls, missing PDF links, or technical failures, explain the specific reason and keep the bibliographic metadata.
   - When the user explicitly asks to download literature, both destinations are required: workspace file plus conversation-area file/artifact. Do not treat a browser tab, Chrome downloads list entry, source URL, or metadata-only citation as a completed download.
   - If the user asks why papers were not downloaded, asks to download full text/PDF, or the requested deliverable clearly implies paper files, treat it as a download request. Do not stop after writing metadata or a paper list.
   - For CNKI papers, prompt the user to log in to CNKI or enable institution/VPN access immediately before CNKI full-text downloads. The prompt must say: "You should preferably log in with an institutional account or enable campus/VPN access; a personal account may still be unable to download paid articles." Do not try "no-login" CNKI full-text downloads unless the item is visibly free/open access. If the user does not confirm access after a reasonable wait, continue with Google Scholar, `academic_search_cn`, publisher pages, author pages, institutional repositories, NBER, SSRN, RePEc, CEPR, or IZA. Explain that CNKI full text was not downloaded because login/access was not confirmed.
   - CNKI download scope is limited to free/open-access items and items available through the user's active CNKI login, institutional subscription, campus IP, or VPN. Paid/subscription-only/unavailable CNKI files must be reported as not downloadable instead of repeatedly attempted.
   - CNKI batch speed rule: after access is confirmed, speed up by first building a download queue from selected CNKI result/article pages that visibly offer `PDF下载` or an equivalent PDF button. Prefer extracting article URLs and PDF download URLs from the current result page, page DOM, link elements, or already-open article pages. Do not serially open every result detail page only to click `PDF下载` if a PDF link or button target can be extracted from the list/current page. Do not include `CAJ下载` links in the queue. Download in small batches of at most 2 concurrent browser downloads, then verify and move files before starting the next batch.
   - Detail-page fallback: open an individual CNKI detail page only when the result/list page does not expose a usable PDF download target or when PDF entitlement must be confirmed. Reuse existing tabs and close completed detail tabs; do not repeat the slow cycle "return to list, open one detail page, click PDF, close tab" for every paper when batch extraction is possible.
   - For CNKI batches, keep one manifest with title, source URL, clicked button/link type, downloaded filename, final workspace path, and PDF verification status. Stop the batch immediately if any download returns a login page, CAPTCHA, HTML, CAJ/NH/KDH, zero-byte/tiny file, or non-`%PDF-` header; diagnose that item before continuing.
   - CNKI format rule: a downloaded CAJ, NH, KDH, or other CNKI reader-only file is not a completed PDF download. Do not rename CAJ as PDF and do not present it as success. If CNKI only offers CAJ/reader-only formats, report that the source does not provide a PDF, keep the metadata, and continue to Google Scholar/full-text discovery or ask whether the user explicitly accepts CAJ.
   - Browser download location rule: if the browser saves a file to the default downloads folder, immediately locate it, verify it is a PDF by checking the `%PDF-` header, move or copy it into the task workspace, and provide it in the conversation area. A file left only in Chrome downloads is not delivered.
   - Do not navigate the active browser tab to `chrome://downloads` or the downloads history page just to check a paper download. Keep the user on the article/source page. Use browser download events, the download shelf/button, or filesystem checks to locate the downloaded file in the background.
   - PDF verification is mandatory for every downloaded paper: check extension, content type when available, and file header. If the header is not `%PDF-`, stop treating the file as a PDF and report the actual format or first diagnostic bytes.
   - Google Scholar download scope: never treat Google Scholar as the file source. It is only an index for finding real full-text locations. Do not batch-click or batch-download from Google Scholar; inspect one candidate at a time and move to the real host before attempting download.
   - For economics download requests, source order is mandatory unless the user asks otherwise: CNKI metadata/access check first for Chinese economics topics; Google Scholar and `academic_search_cn` for full-text discovery; then publisher/author/institutional/working-paper repositories. arXiv is allowed only as a fallback after Google Scholar/full-text discovery and real-source pages fail, or when the user explicitly requests arXiv/preprints.
   - For economics download requests, OpenAlex, Semantic Scholar, Crossref, Unpaywall, or similar APIs may only fill DOI/bibliographic metadata, locate candidate open-access links, or verify metadata. They must not become a batch-download branch and must not start before CNKI access checks, Google Scholar/`academic_search_cn` full-text discovery, and real-source-page searches.
   - Hard stop for economics downloads: if the current plan says "arXiv found many results, now batch download PDFs" before the required CNKI/Google Scholar/full-text-discovery route has been attempted, the plan is invalid. Stop, discard arXiv as the download source, and resume from the required route.
   - Hard stop for economics downloads: if the current plan says "use OpenAlex/Semantic Scholar to batch-find papers, then use Unpaywall to batch-fetch open-access PDFs" before the required CNKI/Google Scholar/`academic_search_cn`/real-source route has been attempted, the plan is invalid. Stop and resume from the required source route.
   - Do not count arXiv PDFs toward completion for ordinary economics, microeconomics, Chinese economics, CNKI, or Google Scholar download requests unless Google Scholar/full-text discovery and real-source pages were attempted first and failed, or the user explicitly approved arXiv/preprints.
7. Use multi-source verification:
   - Verify journal category, publication year, citation count, author identity, and policy/event timing when these affect the answer.
   - Cross-check important claims against CNKI, official journal pages, publisher pages, university/library pages, Google Scholar, arXiv, Web of Science, CSSCI/北大核心 lists, NBER, SSRN, RePEc, CEPR, IZA, or other reliable indexes when available.
   - Separate source-supported facts from inference.
8. Synthesize rather than paste:
   - Do not dump full abstracts or search result pages.
   - Summarize the literature in the user's requested language.
   - Cite sources with links and identifiers where possible.

## CNKI Query Guidance

Use CNKI-friendly search strategies:

- Topic search: combine core concept terms, synonyms, and policy/event names, for example `数字经济 AND 企业创新`, `共同富裕 AND 收入分配`, or `产业政策 AND 全要素生产率`.
- Empirical design search: add terms such as `双重差分`, `断点回归`, `工具变量`, `面板数据`, `准自然实验`, `机制检验`, or `异质性分析`.
- Data search: add dataset or source names such as `中国家庭追踪调查`, `工业企业数据库`, `上市公司`, `海关数据库`, `城市面板`, or `县域数据`.
- Journal filtering: filter or manually screen for RUC Economics A/B journals first, then other top or high-impact journals.
- Supplementary international search: after CNKI, search Google Scholar and arXiv with English keywords, author names, dataset names, and methods. Prefer these before ordinary web search.
- Google Scholar handling: use Google Scholar for discovery only. Do not use it as a direct PDF download API; follow its links to the real host and verify each candidate download individually.
- Parallel search: run CNKI + Google Scholar in parallel when useful, especially for topics that need both Chinese economics literature and international citation context.
- Western economics: if the topic is mainly Western/international economics rather than China-specific Chinese literature, do one focused CNKI pass, then move early to `academic_search_cn` and Google Scholar. Do not burn time repeatedly changing CNKI keyword combinations.
- arXiv fallback limit: for economics downloads, use arXiv only after Google Scholar/full-text discovery and real-source pages fail, unless the user explicitly requested arXiv/preprints. Stop after one or two focused failed/off-topic attempts.
- arXiv guardrail: do not satisfy a CNKI/Google Scholar/economics download request by downloading arXiv PDFs just because they are easy to download. If arXiv is used, state which Google Scholar/full-text and real-source routes failed first.
- Invalid plan pattern: "arXiv found N relevant papers, now batch download PDFs" is not acceptable for ordinary economics download tasks. Replace it with CNKI access check, Google Scholar/full-text discovery, and publisher/author/repository lookup.
- API guardrail: OpenAlex, Semantic Scholar, Crossref, Unpaywall, or similar APIs may only verify DOI, bibliographic metadata, citation clues, and open-access links. Do not use "parallel OpenAlex/Semantic Scholar search plus Unpaywall PDF lookup" as the main economics literature search or download plan unless the user explicitly requested those APIs.
- Invalid plan pattern: "CNKI results are poor, so switch to OpenAlex/Semantic Scholar batch search and Unpaywall batch PDF lookup" is not acceptable for ordinary economics tasks. First complete one focused CNKI pass, then use Google Scholar, `academic_search_cn`, and real source pages according to this route.
- Citation sorting: use citation count as a relevance signal, not as the only ranking criterion.

## Parallel Search Guidance

Use parallel search to reduce latency and improve coverage, but keep the source hierarchy clear:

- CNKI + Google Scholar: run these in parallel for economics literature discovery when possible. Use CNKI for Chinese journal literature, RUC Economics A/B screening, CSSCI/北大核心 context, and China-specific policy literature. Use Google Scholar for citation trails, international versions, English-language papers, full-text discovery, and highly cited work.
- Google Scholar branches must output candidate source pages, not bulk PDF downloads. If they encounter anti-bot/CAPTCHA/unusual-traffic pages, stop that branch and report the restriction.
- CNKI + `academic_search_cn`: run in parallel when the topic is China-specific but needs broader academic indexing or when CNKI navigation is slow.
- Google Scholar + `academic_search_cn`: run in parallel for Western/international economics topics after one focused CNKI pass.
- arXiv is not a main parallel branch by default. For economics download tasks, do not start arXiv as a download branch until Google Scholar/full-text discovery and real-source pages have failed, unless the user explicitly requested arXiv/preprints.
- OpenAlex, Semantic Scholar, Crossref, Unpaywall, or similar APIs are not default parallel search branches. Do not start them alongside CNKI/Google Scholar as main economics discovery sources; use them only after the main route has produced candidate papers and only to supplement DOI, open-access links, citation clues, or metadata.
- Do not run arXiv as the only active branch for economics download tasks unless the user explicitly requested arXiv/preprints. If arXiv returns many PDFs but CNKI/Google Scholar/full-text discovery has not failed yet, ignore arXiv as a download source and continue with the required source route.
- If an arXiv branch finishes first, do not let it decide the deliverable. Wait for or continue the CNKI/Google Scholar/full-text branches, then decide downloads from the required source hierarchy.
- Deduplicate results by title, DOI, working-paper number, author/year, and journal before summarizing.
- If parallel searches disagree, report the disagreement and prefer the most authoritative source for the claim type.

## CNKI Page Handling Efficiency

CNKI result pages often contain large amounts of irrelevant content such as navigation bars, footers, recommendation links, service links, author links, journal links, AI-reading links, and repeated utility links. Avoid spending excessive attention on those parts.

Use this order when extracting article results:

1. Call `interactive_elements` first.
2. If article title links do not appear in `interactive_elements`, do not immediately analyze the full snapshot.
3. If the CNKI search box does not respond to Enter, navigate directly to a CNKI search results URL with the encoded query instead of repeatedly pressing Enter.
4. Call `snapshot` or `page_info`, but limit `max_chars` if the tool supports it.
5. Search within the returned content for the user's keywords, `篇名`, `作者`, `来源`, `下载`, and `HTML阅读`.
6. Read useful abstracts carefully and use them to judge relevance.
7. Ignore author links, journal links, AI-reading links, recommendation links, service links, navigation links, and footer links unless they are directly needed.
8. Open only the most relevant 1-5 articles when necessary.

## Output Standard

Provide a concise research answer with:

- Direct answer or literature conclusion first.
- A short evidence table when useful: title, authors, journal, year, journal category if verified, citation count if visible, method/data, and relevance.
- A clear note that CNKI was searched first. If CNKI was not used, explain why.
- Which parallel searches were used, such as CNKI + Google Scholar or Google Scholar + `academic_search_cn`, and why.
- Whether `academic_search_cn`, Google Scholar, and arXiv were used as supplementary searches. If arXiv was skipped or stopped early, briefly note that arXiv was only auxiliary or not suitable.
- Which RUC Economics A/B journals or papers were checked, and whether the classification was verified.
- Relevant literature closest to the user's question. Selected papers must be the most relevant and highest-quality available.
- A final question asking whether the user wants the most relevant full papers downloaded, unless the user already requested downloads.
- Important limitations: access restrictions, unverifiable journal category, stale citation counts, or disagreement between sources.
