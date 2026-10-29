# OmicVerse MCP Capability Map

Use this file only to decide whether an approved analysis module is a plausible
candidate before a local OmicVerse MCP runtime exists. It is not a substitute
for live discovery: after registration, `ov.list_tools`, `ov.search_tools`, and
`ov.describe_tool` are authoritative.

The bundled installer enables rollout `P0+P0.5+P2`. Its documented candidate
families are:

| Candidate family | Default MCP operations |
| --- | --- |
| Data / AnnData handling | read expression data, inspect AnnData, persist/restore AnnData |
| Preprocessing | QC, cell/gene filtering, log1p, highly variable genes, scaling |
| Representation / clustering | PCA, neighbours, UMAP, Leiden, Louvain |
| Marker analysis | marker discovery/retrieval, COSG |
| Pathway analysis | single-cell pathway enrichment and its plot |
| Visualization | embedding, UMAP, t-SNE, violin, dot plots, marker/rank-gene dot plots, marker heatmaps |
| Annotation and advanced single-cell | pySCSA annotation, MetaCell, cell-type differential analysis, SCENIC |
| Topic analysis | LDA topic modelling |
| Bulk differential expression | P2 `pyDEG` |

Do not use this map to claim support for a similarly named analysis. In
particular, conventional bulk GO/KEGG/Reactome enrichment, GSEA/GSVA,
CIBERSORT, xCell, ESTIMATE, TIDE, survival modelling, WGCNA, and generic bulk
visualization are not default MCP candidates unless the live catalog explicitly
exposes a matching tool. The map must be updated when the installer rollout
phase or OmicVerse version changes.
