---
name: standardization
description: Standardize web research workflows that use the update_browser_use remote-browser skill and mcp_remote_browser tools. Use together with browser_use when the user asks for browser-based research, source verification, literature search, multi-source synthesis, biomedical or medical questions, life-science questions, or website investigation. For biomedical, medical, clinical, pharmaceutical, genetics, biology, public-health, or life-science questions, prioritize PubMed and run PubMed with Google Scholar in parallel when useful, then use CNKI, general web search, or secondary sources.
---

# Standardization

Use this skill to standardize research tasks that require the `browser_use` remote browser workflow. This skill defines source selection and research procedure; the browser operation rules come from the remote-browser skill.

## Required Companion Skill

Before using browser tools, first read and follow the relevant search rules from:

`browser_use`

Then satisfy the additional constraints in this skill.

Use the lifecycle rules for `mcp_remote_browser_*` tools: list devices first, create a task-specific session, inspect tabs before opening duplicate tabs, prefer structured element refs, request approval for sensitive actions, and finalize tabs before ending browser work.

## Research Workflow

1. Classify the user's request before searching:
   - Biomedical or life-science: medicine, disease, drug, clinical trial, gene, protein, pathway, organism, epidemiology, public health, biotechnology, diagnostics, medical device, patient care, or laboratory methods.
   - General research: policy, product, company, market, technology, documentation, news, or other non-biomedical topics.
2. For biomedical or life-science requests, search PubMed first:
   - Start at `https://pubmed.ncbi.nlm.nih.gov/`.
   - When the task needs literature discovery, citation context, or broad coverage, run PubMed and Google Scholar searches in parallel when browser/tool capacity allows. PubMed remains the primary source for biomedical evidence; Google Scholar is a high-priority parallel source for citation trails, highly cited papers, full-text discovery, and cross-disciplinary coverage.
   - Build queries with scientific terms, synonyms, abbreviations, and key entities from the user request.
   - Prefer recent reviews, systematic reviews, meta-analyses, clinical guidelines, randomized controlled trials, and high-quality primary literature when relevant.
   - Use article pages, abstracts, publication dates, journal names, PMID/DOI, and linked full text when available.
   - Do not over-focus on navigation bars, footers, recommendation panels, author links, journal links, related-article widgets, metric widgets, sharing links, or other page chrome. Focus on useful article metadata and read relevant abstracts carefully.
   - For faster first-pass research, do not download papers unless the user explicitly asked for downloads at the start. First identify and summarize the most relevant papers, then ask the user whether they want the full papers downloaded.
   - After user permission, download complete papers into the workspace when access is allowed and the paper is highly relevant, and also provide the downloaded paper in the conversation area through the platform's user-visible file/artifact mechanism. If a paper cannot be downloaded, explain the specific reason to the user.
   - When the user explicitly asks to download literature, both destinations are required: save the file under the current workspace and surface the same file in the conversation area. Do not treat a browser tab, source URL, or metadata-only citation as a completed download.
   - Read highly cited papers carefully and prioritize top-journal papers, but do not rank by citations or journal name alone.
   - Only move to Google Scholar, CNKI, publisher pages, clinical guideline sites, regulatory sources, or general web search after checking PubMed, or when PubMed is clearly not suitable.
   - If ordinary PubMed search does not find useful results, use PubMed advanced search and consult PubMed FAQ/user guide pages to support the answer.
3. For non-biomedical requests, choose authoritative primary sources first:
   - Official documentation, standards bodies, government or regulator pages, company pages, original papers, datasets, or source repositories.
   - Use secondary sources only to orient or cross-check. If primary sources are available, do not rely only on secondary sources for factual conclusions.
4. Use multi-source verification for claims that are current, high-impact, controversial, or likely to change:
   - Confirm dates, versions, authors, jurisdictions, and definitions.
   - Separate facts directly supported by sources from inference.
   - State uncertainty clearly when sources disagree or evidence is limited.
5. Capture enough bibliographic/source metadata to make the answer auditable:
   - For PubMed: title, authors if needed, journal, year/date, PMID, DOI if available, and URL.
   - For web sources: page title, publisher/organization, URL, visible publication/update date, and access-relevant context.
6. Synthesize rather than paste:
   - Do not dump full page snapshots or long abstracts.
   - Summarize findings in the user's requested language.
   - Cite sources with links and identifiers where possible.

## PubMed Query Guidance

Use PubMed-friendly searches before broad web searches for biomedical tasks:

- Disease or intervention: `condition AND intervention`, then add study type terms such as `systematic review`, `meta-analysis`, `randomized controlled trial`, or `guideline`.
- Gene or protein: include official symbols and common aliases; add organism or disease context when needed.
- Drug or compound: include generic names, brand names when relevant, mechanism terms, adverse effects, or trial phase.
- Diagnostic or biomarker: combine target condition, assay/test name, and terms such as `sensitivity`, `specificity`, `validation`, or `cohort`.
- Recent evidence: use PubMed filters or query terms for publication date only when recency matters.

## PubMed/PMC Open-Access Download Workflow

When the user asks to download biomedical literature, avoid open-ended API retry loops. Use this fixed decision path:

1. Prefer PubMed/PMC via NCBI E-utilities for open-access discovery:
   - Search PubMed with `free full text[filter]` when the user asks for downloadable/open-access papers.
   - Use `esearch.fcgi` with `db=pubmed`, `retmode=json`, and a URL-encoded `term`.
   - Batch PMID-to-PMC mapping with `elink.fcgi` using `dbfrom=pubmed`, `db=pmc`, and comma-separated PMIDs. Do not query one PMID at a time unless there are fewer than five PMIDs or a batch retry is necessary.
   - Once a PMCID is found, try the PMC PDF URL pattern `https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/pdf/`.
2. Use Europe PMC only as a fallback:
   - Use simple queries first, such as `<topic terms> HAS_PMC:Y`, `format=json`, and a modest `pageSize`.
   - If Europe PMC query/filter syntax fails twice, stop trying to repair filters or URL encoding. Switch back to NCBI E-utilities or the PubMed/PMC browser route.
   - Do not repeatedly say "filter syntax has a problem", "URL encoding has a problem", or "use the correct API parameter" after two failed attempts. Report the failure and take the next route.
   - If Europe PMC `Open PDF` or `https://europepmc.org/api/getPdf?pmcid=<PMCID>` returns 404, HTML, a login/error page, or any non-`%PDF-` response, mark the Europe PMC PDF path failed for that PMCID. Do not keep retrying the same endpoint.
   - Do not use NCBI `efetch` XML, Europe PMC XML, JATS XML, HTML full text, abstracts, or metadata as a substitute for an original publisher/PMC PDF. XML/HTML may be saved as supporting full text only when the source clearly allows full-text access/download or the API provides it as an open full-text record; label it clearly.
   - Last-resort converted PDF path: if all real PDF routes fail for an open-access article but permitted full-text XML/HTML is available, ask the user whether a clearly labeled converted PDF is acceptable. If the user already asked for "anything readable as PDF" or explicitly accepts conversion, generate a converted PDF from XML/HTML and label filenames and report text with `converted_from_xml` or `converted_from_html`.
   - Permission gate for XML/HTML full-text use: before downloading, saving, or converting full text, verify that the item is open access and that the full text is provided by PMC/Europe PMC/NCBI or another source that permits full-text access/download. Record the evidence in the manifest, such as PMCID with PMC full text, Europe PMC `isOpenAccess`/license fields, a Creative Commons/license statement, or an official OA full-text endpoint. If the publisher/source forbids full-text download, blocks programmatic retrieval, lacks an open license, or only permits web viewing, do not download or convert the full text; report the restriction and provide metadata/link only.
   - A converted PDF is not an original downloaded paper PDF. Never present XML/HTML-to-PDF output as the publisher/PMC PDF. Keep the original XML/HTML source URL/PMCID in metadata and state that layout, figures, tables, equations, and special characters may be incomplete or normalized.
3. Browser fallback:
   - If API calls time out or fail after two focused attempts, use the PubMed website with Free full text / Free PMC article filters, open the PMC article page, and use the visible PDF link.
   - Open only the most relevant 1-5 articles unless the user explicitly asked for a larger set.
4. Completion criteria:
   - A download is complete only when the actual PDF is saved in the workspace and surfaced in the conversation area.
   - If only PMID/DOI/PMCID metadata or a browser tab was obtained, report it as metadata found, not as a downloaded paper.
   - If only XML/HTML full text was obtained, report it as XML/HTML full text found, not as an original downloaded PDF. Converted PDFs may be delivered only under the last-resort converted PDF path and must be labeled as converted.
   - If no PDF is available without login or subscription, state that access is restricted and keep the bibliographic metadata.
5. Anti-busywork failure guard:
   - Do not assume `https://pmc.ncbi.nlm.nih.gov/articles/<PMCID>/pdf/` is a valid PDF URL. First open the PMC article page and extract the real PDF `href` from the page when present.
   - Treat `<meta name="citation_pdf_url" ...>` on a PMC article page as a real PDF candidate even if no visible PDF button appears in `interactive_elements`. Also inspect `<a href*="/pdf/">`, `<link>`, and other PDF-like DOM/link targets, then resolve relative URLs against the article page.
   - If `citation_pdf_url` or another real PDF candidate was found, do not keep searching for a visible PDF button just because `interactive_elements` is noisy or reference links dominate the page. Use the extracted URL as the candidate and proceed to validation/download.
   - If command-line `curl`/script download of a PMC PDF URL returns a small non-PDF response such as about 1.8 KB HTML, do not continue batch curl downloads and do not restart the same "find visible PDF link" loop. Retry that single candidate through the active browser context instead, using the existing article page/session: open the extracted PDF URL in a new tab or trigger an `<a download>` click from the article page, then inspect the final URL and saved bytes.
   - If browser navigation to an extracted PMC PDF URL redirects back to the article page or returns HTML, record that as a concrete PMC/browser access failure for that item. Do not repeatedly reread this skill or repeatedly search the same DOM. Report the final URL/status/content type when available and keep the PMC article HTML URL as free full text.
   - If `efetch` with `rettype=pdf` returns XML or any non-PDF bytes, treat original PDF retrieval as failed for that endpoint. Return to real PDF candidates from PMC/Europe PMC/publisher pages first. Only after real PDF routes fail may the last-resort converted PDF path be used.
   - Converted PDF generation guardrails: use a Unicode-capable font or sanitize unsupported characters with a warning; include title, authors, journal/year, PMID/PMCID/DOI, source URL, permission evidence, and a first-page note saying "Converted from XML/HTML; not publisher PDF"; validate the output opens and starts with `%PDF-`; save both the converted PDF and the permitted XML/HTML source or metadata manifest in the workspace.
   - For batches, first collect PMCID, article URL, extracted PDF candidate URL, and extraction source (`citation_pdf_url`, anchor href, visible button) for each paper. Download only candidates with a PDF URL, validate each saved file, and stop the batch on the first repeated non-PDF pattern.
   - After each PDF download, validate both the response metadata and file bytes: follow redirects, require a PDF-like `Content-Type` when available, require the saved file to start with `%PDF-`, and reject tiny HTML/error responses.
   - If any attempted PDF download returns a non-PDF response under 10 KB (for example 1.8 KB HTML/error pages), stop the batch immediately. Diagnose one failed sample with `file`, the first 500 bytes, and the final redirected URL/status before trying another strategy.
   - If two consecutive PMCID downloads fail with the same non-PDF size or same error signature, do not continue the remaining batch and do not switch APIs blindly. Report the shared failure pattern and move to article-page PDF link extraction or user-visible metadata reporting.
   - If the PMC article page has no PDF link, report "free full text available, PDF link not found" and provide the HTML full-text URL; do not mark it as a downloaded PDF.
   - Do not print repeated progress claims such as "switching API", "fixing URL encoding", or "using the correct filter" after a repeated non-PDF pattern. State the concrete failure reason and stop or switch to a bounded fallback.

## Parallel Search Guidance

Use parallel search to reduce latency and improve coverage, but keep the evidence hierarchy clear:

- PubMed + Google Scholar: run these in parallel for biomedical literature discovery when possible. Use PubMed for biomedical indexing, abstracts, MeSH-like biomedical terminology, PMID/DOI metadata, and study-type filtering. Use Google Scholar for citation counts, highly cited papers, full-text discovery, preprints, and cross-disciplinary or publisher-hosted versions.
- PubMed + guideline/regulatory sources: run in parallel when the user asks about clinical practice, safety, diagnosis, treatment, or policy. Prefer official guideline/regulatory sources for recommendations and PubMed for literature evidence.
- PubMed + CNKI: run in parallel only when the biomedical question has an explicit Chinese-language, China-specific, or Chinese clinical literature component.
- Do not let parallel search create duplicate work. Deduplicate by title, DOI, PMID, trial identifier, and author/year before summarizing.
- If parallel searches disagree, report the disagreement and prefer the most authoritative source for the claim type.

When the user asks a clinical or medical-advice-like question, treat the answer as informational research. Do not present a diagnosis or treatment instruction as personal medical advice.

## PubMed Page Handling Efficiency

PubMed and publisher pages can contain large amounts of irrelevant content such as navigation bars, footers, recommendation panels, author profile links, journal links, related-article widgets, metrics, citation tools, sharing links, and service links. Avoid spending excessive attention on those parts.

Use this order when extracting article results:

1. Call `interactive_elements` first.
2. If article title links or article controls do not appear in `interactive_elements`, do not immediately analyze the full snapshot.
3. Call `snapshot` or `page_info`, but limit `max_chars` if the tool supports it.
4. Search within the returned content for the user's keywords, article titles, `Abstract`, `PMID`, `DOI`, `Journal`, `Free full text`, `Full text links`, and `Similar articles`.
5. Read useful abstracts carefully and use them to judge relevance, study type, population/model, intervention/exposure, outcome, method, and limitations.
6. Ignore author links, journal links, metrics links, recommendation links, service links, navigation links, and footer links unless they are directly needed.
7. Open only the most relevant 1-5 articles when necessary.

## Browser Operation Pattern

Use this pattern with the remote-browser skill:

1. `mcp_remote_browser_list_devices`
2. Create or reuse one task-specific `session_id`.
3. `mcp_remote_browser_name_session`
4. `mcp_remote_browser_user_tabs` to avoid duplicate tabs.
5. Open or claim the target tab.
6. Search, inspect results, open source pages, and collect source metadata.
7. Use screenshots or exported pages only when visual evidence or a user-requested artifact is needed.
8. Run `mcp_remote_browser_finalize_tabs` before finishing.

For simple linear searches, prefer `mcp_remote_browser_run_action_plan` with allowlisted actions. For exploratory research, use individual structured tools step by step so every decision is based on observed page state.

## Output Standard

Provide a concise research answer with:

- Direct answer or conclusion first.
- Key evidence grouped by source type or theme.
- Source links and identifiers.
- Important limitations, conflicts, or date-sensitive caveats.
- Which parallel searches were used, such as PubMed + Google Scholar, and why.
- Relevant literature. The listed papers must be the closest matches to the user's question.
- A final question asking whether the user wants the most relevant full papers downloaded, unless the user already requested downloads.

For biomedical answers, explicitly indicate whether PubMed was searched first. If PubMed was not used, explain why PubMed was not applicable or unavailable.
