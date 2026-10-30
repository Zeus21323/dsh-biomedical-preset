# ClinicalTrials.gov And PubMed API Contract

Read this reference whenever an approved module retrieves ClinicalTrials.gov or
PubMed records. Do not infer API parameters or JSON fields from memory.

## ClinicalTrials.gov API v2

Use `GET https://clinicaltrials.gov/api/v2/studies`. For condition searches,
`query.cond` is valid. `query.term` is also valid for expert search expressions.
Do not replace a working `query.cond` merely because a combined request returns
400; log the final URL and response body to identify the actual parameter.

Use only token pagination:

```text
response.nextPageToken -> next request pageToken
```

Never send a numeric `page` parameter. Start without `pageToken`, stop when
`nextPageToken` is absent, reject repeated tokens, and retain page-level request
URLs and counts. Use the bundled client instead of hand-writing pagination:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/clinicaltrials_v2_client.py \
  --condition "lung cancer" \
  --page-size 100 \
  --max-studies 250 \
  --raw-output data/clinicaltrials_raw.json \
  --normalized-output data/clinicaltrials_normalized.json \
  --provenance-output data/clinicaltrials_provenance.json
```

The response contract is:

```text
top-level studies: studies[]
pagination token: nextPageToken
completion date: protocolSection.statusModule.completionDateStruct.date
completion date type: protocolSection.statusModule.completionDateStruct.type
```

Date strings may be `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`. Preserve the raw value
and precision. Do not expect separate `year`, `month`, and `day` JSON keys; do
not invent a missing month/day. A missing or invalid completion date does not
justify dropping the entire study.

Before full retrieval, fetch 1-2 studies and verify the top-level keys,
pagination token and every field path used by the approved analysis. For every
filter, save input count, retained count, excluded count and exclusion reason.
If a non-empty API response becomes zero normalized records, block the module
and diagnose the parser; never proceed with an empty cohort.

For HTTP 400, record:

```text
status code
final encoded request URL
complete parameter names (redact secrets only)
first 1000 response-body characters
```

Do not blame one parameter until a minimal request and incremental parameter
tests reproduce the error.

Official references:

- https://clinicaltrials.gov/data-api/api
- https://clinicaltrials.gov/data-api/about-api/study-data-structure

## PubMed E-utilities

Use NCBI E-utilities rather than scraping PubMed HTML. Use `ESearch` to resolve
the query and record count, then retrieve records in bounded `retstart`/`retmax`
batches or with ESearch history (`WebEnv` and `query_key`) plus `EFetch`.
ClinicalTrials.gov `pageToken` rules do not apply to PubMed.

Always send `tool` and `email`. Respect the current NCBI rate limits; use an API
key only when configured by the user/environment and never print it. Set
timeouts, bounded retries and a total deadline from
`references/network_execution_policy.md`. Save the original query, database,
record count, PMIDs, batch boundaries, retrieval time and raw XML/JSON paths.

Official reference:

- https://www.ncbi.nlm.nih.gov/books/NBK25501/

## Cross-source linkage

Link ClinicalTrials.gov and PubMed using explicit NCT identifiers found in
registry references, publication metadata, abstracts or secondary IDs. Preserve
the exact evidence for every NCT-PMID edge. Do not infer a link from similar
titles alone. Report unmatched trials and publications instead of dropping
them.
