# OmicVerse MCP Backend

Use OmicVerse through a registered local MCP server. The server dynamically
exposes registered OmicVerse tools, so discover its live catalog rather than
equating the MCP server with a fixed subset of Python-library capabilities.

## When to use it

After the analysis PRD is approved, check every approved analysis module
against the live OmicVerse MCP catalog before selecting its fallback backend.
If a tool supports that module's approved method, input format, and
dependencies, execute that module through MCP. Typical candidates include
single-cell preprocessing, clustering, annotation, marker analysis,
visualization, spatial analysis, bulk-to-single integration, and any other
module returned by tool discovery.

Do not route a module solely because OmicVerse offers a similarly named Python
function. The MCP server exposes only its own live tool set. If no suitable tool
exists, inputs/dependencies are incompatible, or the approved method differs,
record that specific reason and use the normal R/Python fallback for that
module. Do not reject the whole PRD because one module lacks MCP support. A
mixed-backend study is expected: continue independently with the remaining
modules and stop only an affected module that has no scientifically valid
fallback.

### Required bulk candidates

Do not exclude MCP because the study uses bulk microarray or bulk RNA-seq. The
current default rollout includes two explicit candidates that must be checked
when present in the approved inventory:

| Approved module | MCP candidate | Required action |
| --- | --- | --- |
| PCA / principal-component analysis | `ov.pp.pca` | Discover it and verify that the bulk expression matrix can be represented as the required AnnData input with an appropriate preprocessing record. |
| Differential expression / DEG | P2 `pyDEG` | Discover it and verify the count/expression type, group design, and approved differential-expression method. |

If no OmicVerse runtime is registered and either row is present, this is a
plausible MCP candidate: invoke the installation `ask_user` interaction before
probing R/Python or downloading data. Only a recorded failed discovery or
method/input/dependency mismatch permits fallback for that one module. The
absence of MCP tools for CIBERSORT, xCell, ESTIMATE, bulk ssGSEA, or other
immune-deconvolution modules does not permit skipping the required PCA/DEG
check.

## Local opt-in installation gate

When no OmicVerse MCP tool is registered, first decide whether the approved
inventory contains a plausible MCP candidate based on this server's documented
scope. If it does not, skip this section and use ordinary module-level backend
routing. If it does, check whether an existing local runtime can be reloaded.
Only if it cannot, ask exactly once per user profile for this installation
state. On SpeedClaw, call the built-in `ask_user` tool with
the following three structured options and `allow_other: false`; do not print
them as a manual chat question. On other hosts, prefer `request_user_input`,
then structured `ask_user`:

```text
本机尚未启用 OmicVerse MCP。是否为当前用户安装并启用本地生信后端？
1. 安装并启用（推荐）
2. 不安装，使用现有后端
3. 取消本次分析
```

If no structured ask-user tool exists, ask the same question in chat and stop.
Do not install after a timeout, ambiguous answer, or previous refusal. Record
`not_installed`, `declined`, `installing`, `ready`, or `failed` in the
user-profile state file
`~/.bioinformatics-writer/status/omicverse_mcp_status.json` so later projects
and turns do not repeatedly ask. Also record a project-local summary under
`environment/` when an experimental analysis is run.

On `安装并启用`, invoke the bundled installer only after the response is
received:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/install_omicverse_mcp.py
```

The installer creates an application-scoped user environment under
`~/.bioinformatics-writer/runtime/omicverse`, installs `omicverse[mcp]`, runs
the official MCP help check, and writes the generated server descriptor to
`omicverse_mcp_local.json`. It creates the venv with symlinks so a macOS
bundled Python using `@rpath/libpython` keeps resolving its original shared
library; it also rebuilds a previously failed managed venv before retrying.
Never ask the user to provide a Python path or type `command` values.

### SpeedClaw runtime registration

SpeedClaw exposes the deferred built-in tool `install_mcp` for runtime MCP
registration. Do **not** edit `mcp.json` for this path: that file is only read
during Agent startup and has no watcher. After the installer writes
`omicverse_mcp_local.json`, read its `mcpServers.omicverse` object and call
`install_mcp` with the corresponding explicit stdio configuration:

```json
{
  "name": "omicverse",
  "type": "stdio",
  "command": "<descriptor command>",
  "args": ["<descriptor args>"]
}
```

Use `find_tools` first if `install_mcp` is deferred. Do not invent the command
or arguments; copy them from the installer-generated descriptor. `install_mcp`
creates a new client, runs `initialize` and `tools/list`, atomically replaces
any same-named server only after success, updates the Agent Tool Registry, and
persists the server in SpeedClaw's MCP settings index. It does not require an
Agent restart or a new session.

The SpeedClaw App Server endpoint `POST /api/mcp/servers` is an equivalent UI
and integration path, but the skill should use `install_mcp` because it is the
existing in-conversation runtime capability.

After successful registration, MCP tools enter SpeedClaw's deferred tool
catalog by default. Use `find_tools` to search for `omicverse`, then the
approved operation (for example `single-cell QC`, `PCA`, `annotation`, or
`differential expression`). The selected MCP tool becomes available on the
following model request. Record the `install_mcp` result and the discovered
tool names in the project metadata.

If `install_mcp`, initialization, `tools/list`, or discovery fails, retain the
previous MCP connection when present; mark the runtime as `failed` and offer
the documented fallback. Do not ask the user to edit JSON, restart the Agent,
or create a new session.

## MCP execution protocol

1. Read the approved PRD and `analysis_inventory.json`.
2. Inspect the currently registered MCP tools. Use `ov.list_tools` or
   `ov.search_tools` when exposed, then `ov.describe_tool` before a specific
   analysis call. Tool names and schemas are deployment/version-specific; do
   not invent them.
3. Select the narrowest registered tool for the approved operation. If the
   server exposes a generic OmicVerse execution tool, pass a structured
   operation, input path, output directory, parameters, and random seed rather
   than an unstructured request.
4. Give the MCP call an experiment-scoped output directory such as:

   ```text
   results/experiments/single_cell_annotation/
   figures/experiments/single_cell_annotation/
   ```

5. Save the MCP request, tool name, package/version information returned by
   the server, parameters, and output paths to:

   ```text
   results/experiments/<experiment_slug>/omicverse_mcp_run.json
   ```

6. Validate that every declared result table and figure exists before moving
   to Results Question Map or Figure Blueprint generation.

## If OmicVerse MCP remains unavailable

Do not silently pretend the call ran. After the user declines, installation
fails, the host does not register the descriptor, or a required live tool is
absent, report the exact status and offer a fallback for that module in this
order:

1. Scanpy for Python single-cell/spatial work when installed
2. Seurat/R or another project-established backend
3. Stop after the PRD and ask whether the user wants to configure the backend

Record the fallback and reason in `analysis_prd.md` and the experiment's
metadata. Continue all other approved modules. A fallback must not change the
approved scientific scope silently; if the affected module has no valid
fallback, mark only that module blocked and ask whether to revise the scope.

## Output contract

OmicVerse MCP is an executor, not the workflow owner. The calling Skill still
owns:

- data and analysis approval
- experiment-scoped directories
- result provenance
- panel metadata and editable sources
- Results Question Map
- Figure Blueprint
- statistical and scientific verification
- manuscript and DOCX delivery
