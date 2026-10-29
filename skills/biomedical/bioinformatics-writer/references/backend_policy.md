# Backend Policy

Use a local-R-first, module-level hybrid policy. “Local” means the machine or
container on which the agent can actually execute commands; an RStudio
installation on a different personal computer is not accessible from a remote
agent unless a remote executor is explicitly configured.

## OmicVerse MCP Backend

Before selecting any R or Python backend, create and validate the complete
`environment/omicverse_mcp_routing.json` required in Stage 3. It must cover
every approved analysis module, not merely a preselected subset. Search the
registered OmicVerse MCP live catalog before selecting R or Python; if no
runtime exists, classify every module using
`references/omicverse_mcp_capability_map.md`, offer installation if any
candidate exists, and repeat live discovery after registration. Use MCP for a
module when a tool supports its approved method, inputs, and dependencies.
This is a module-level priority, not a requirement to use MCP for the whole
study. Do not infer a tool name or assume that the whole OmicVerse Python
library is exposed through MCP. Read `references/omicverse_mcp_backend.md` for
discovery, opt-in local installation, SpeedClaw `install_mcp` registration, and
fallback rules.

When OmicVerse MCP is not registered, offer its local installation only through
the explicit user-selection gate and only if the approved inventory contains a
plausible MCP candidate. If a module has no suitable live tool, the user
declines installation, or installation fails, record the module-specific reason
and then probe the execution host and select the appropriate fallback. Do not
change approved scientific scope silently.

Never treat an MCP mismatch or failure for one module as a failure of the whole
analysis plan. Continue routing every other approved module independently. Stop
only the affected module when it has no scientifically valid fallback, and ask
the user whether to revise the approved scope.

For avoidance of doubt, approved PCA and differential-expression modules are
plausible MCP candidates even in a bulk microarray or bulk RNA-seq plan. Do not
declare MCP inapplicable based on `bulk` or `microarray` alone. Run discovery
or the installation interaction first; decide fallback only from the actual
tool schema, input compatibility, dependencies, and approved method.

## Mandatory Environment Preflight

Before choosing R or Python, derive the required R package names from the
approved analysis inventory and run:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/probe_r_environment.py \
  --package limma \
  --package clusterProfiler \
  --output environment/r_environment.json
```

Use only packages actually required by the approved modules. The probe checks
`PATH`, `R_HOME`, common system/RStudio R locations, and common Conda R
environments. It records the selected absolute `Rscript` path, R version,
`R.home()`, `.libPaths()`, installed-package versions, and missing packages.
This check is read-only and must happen before installing R or choosing a
Python replacement.

Also write `environment/backend_decision.json` with one record per approved
analysis module:

```json
{
  "analysis": "differential_expression",
  "preferred_backend": "R/limma",
  "actual_backend": "R/limma",
  "reason": "existing local package reused",
  "fallback_used": false,
  "rscript": "/absolute/path/to/Rscript",
  "package_versions": {"limma": "3.x"}
}
```

## Default Rule

Use the most reliable mature toolchain for each module, with installed local R
and R packages taking priority for R-native bioinformatics:

```text
Installed local R for statistical bioinformatics and Bioconductor-heavy analysis.
Python for assistance, orchestration, validation, file handling, automation, and Python-native analysis.
```

## R Is Preferred For

- microarray differential expression: `limma`
- RNA-seq differential expression: `DESeq2`, `edgeR`, `limma-voom`
- enrichment: `clusterProfiler`, `ReactomePA`, `fgsea`, `msigdbr`
- survival and prognostic models: `survival`, `survminer`, `timeROC`, `glmnet`
- heatmaps and publication plots: `ComplexHeatmap`, `pheatmap`, `ggplot2`, `patchwork`
- single-cell analysis when the project uses Seurat

Run R through:

```bash
/absolute/path/from/r_environment.json/Rscript analysis.R
```

Do not require the RStudio GUI. Reuse the R interpreter and user package
libraries detected from the same host, including `.libPaths()` used by
RStudio. Do not reinstall an available package, create a new R environment, or
switch to Python merely for convenience.

## Python Is Preferred For

- project orchestration and pipeline glue
- `results_question_map.json` and `figure_blueprint.json` generation/checking
- table cleaning: `pandas`, `numpy`
- machine learning: `scikit-learn`
- Python-native survival workflows: `lifelines`
- single-cell analysis when the project uses Scanpy
- image composition: `Pillow`
- schema validation and report assembly
- calling `tex_to_docx` export scripts

## Selection Rules

1. Probe the execution host before backend selection; never assume R is absent
   because `Rscript` is missing from the current shell `PATH`.
2. If the required R package is installed and usable, use it for the matching
   approved module. This overrides a convenience-based Python preference.
3. Preserve an existing project pipeline when it is already reproducible, but
   do not replace working R-native stages with Python without a scientific reason.
4. Use Python as an auxiliary backend for orchestration and Python-native
   modules, or for only those R modules whose required environment/package is
   unavailable and which have a scientifically equivalent Python method.
5. Do not replace `limma`, `DESeq2`, or another approved statistical model with
   a simpler non-equivalent Python test. If no equivalent fallback exists,
   report the missing dependency and ask whether to install it or revise the PRD.
6. A missing package must not force the entire study to Python. Keep available
   R modules in R and exchange data through documented CSV/TSV/Parquet files.
7. Run the chosen R interpreter by its absolute path. Record R/Python package
   versions, parameters, fallback reasons, and interchange files in
   `environment/backend_decision.json` and the Methods log.
8. If the agent runs remotely, do not claim to reuse RStudio installed on the
   user's separate computer. Report the execution-host boundary explicitly.

## Allowed Python Fallback

For every R-to-Python fallback, record:

- the missing or unusable R interpreter/package;
- the probe evidence from `r_environment.json`;
- the Python package and version;
- why the statistical method is equivalent;
- parameter and output-schema differences;
- whether the approved PRD needs revision.

Silent whole-pipeline fallback to Python is forbidden.
