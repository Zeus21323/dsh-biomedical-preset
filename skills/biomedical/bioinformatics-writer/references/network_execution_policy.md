# Network And Long-Running Analysis Policy

Apply this policy after backend routing and before any external API request,
download, or long-running analysis command.

## Contents

- Network preflight
- HTTP limits
- Cache and evidence
- Python compatibility preflight
- Long-running command contract
- Failure handling

## Network preflight

Before bulk retrieval:

1. Verify one small official endpoint response and save it locally.
2. Record source, endpoint, query parameters, retrieval time, release/version,
   access status, response status, row count and local cache path.
3. Confirm that the returned fields support the approved analysis. A collection
   list does not substitute for patient-, study- or series-level records.
4. Prefer one bulk metadata query over per-record or per-collection loops.

For IDC/TCIA, prefer IDC MCP, REST/SQL, BigQuery or `idc-index` aggregation for
collection-level patient/study/series counts. Do not issue an unbounded loop of
TCIA patient calls. If only per-collection calls can supply an approved field,
use a concurrency cap of 4, cache every successful response, and preserve an
explicit missing/failed collection table.

## HTTP limits

Every generated HTTP client must set explicit limits. Use these defaults unless
the approved PRD records a justified alternative:

```text
connect timeout: 10 seconds
read timeout: 30 seconds
maximum attempts: 3
backoff: 2, 4, then 8 seconds
retry: 429, 500, 502, 503, 504 and transport timeouts only
module retrieval deadline: 120 seconds for metadata discovery
```

Do not retry other 4xx responses. Honor `Retry-After` when present. On deadline,
write the failed endpoint, exception, attempts and missing scope to a local JSON
or CSV artifact and stop or continue only the unaffected modules.

## Cache and evidence

Store raw API responses or normalized tables under the project together with a
provenance record containing URL, parameters, retrieval timestamp, source
version, HTTP status and SHA-256. A cache may be reused only when its provenance
is present and its contents support the approved fields. Never fill a missing
patient count, label, sample size or feature from model memory, a prose website
description, or “known database characteristics.”

If an API failure changes the unit of analysis, source, primary endpoint,
sample size, comparison, method or expected claim, mark `analysis_prd.md` as
`revised`, invalidate the approval receipt, present the changed plan, and obtain
approval again. Do not silently replace patient-level analysis with collection
summaries or synthetic values.

## Python compatibility preflight

Before running a generated Python analysis, compile it, probe every required
package/version and verify version-sensitive attributes. Save
`environment/python_environment.json`. For NumPy integration code require
`numpy:trapezoid`; do not generate `np.trapz` for NumPy 2.x environments.

Example:

```bash
python3 -m py_compile analysis.py
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/probe_python_environment.py \
  --output environment/python_environment.json \
  --package numpy \
  --package pandas \
  --require numpy:trapezoid
```

Run a small smoke test with one collection or a bounded sample before the full
job. A failed smoke test blocks the full run.

## Long-running command contract

Do not launch analysis with shell `&`, `nohup`, or an unmanaged background PID.
Run it in the foreground through the bundled supervisor so the host may yield a
session while the child remains bounded:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/run_analysis_supervised.py \
  --project-root . \
  --status environment/analysis_task_status.json \
  --log logs/analysis.log \
  --timeout 900 \
  -- python3 analysis.py
```

Set the timeout from the approved module and data size; never omit it. The
supervisor writes atomic `starting`, `running`, `completed`, `failed`,
`timed_out`, `cancelled`, or `failed_to_start` status and terminates the entire
child process group on timeout.

When the host returns a running session, wait on that session. Do not start new
shell commands that repeatedly run `ps` or `tail`. Poll no more frequently than
10 seconds, use 10/20/30-second backoff, and inspect the log only after a failed
status, timeout, or three unchanged status checks. Do not narrate every
unchanged poll to the user.

## Failure handling

- `completed`: verify outputs and proceed.
- `failed`: inspect the final log once, fix only within approved scope, then run
  one bounded retry.
- `timed_out`: identify the endpoint/module; use a documented approved fallback
  or revise the PRD.
- repeated failure: mark the affected module blocked and continue independent
  modules. Never fabricate substitute results.
