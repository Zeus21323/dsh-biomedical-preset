# Helper Functions Reference

## PC Selection

### `detect_elbow_pc(stdev_values)`
Auto-detect elbow point from PCA standard deviations. Scales x/y to [0,1], computes distance from the line connecting first and last points, returns PC index with max distance.

### `get_pc_selection_info(stdev_values, selection_mode, ...)`
Returns list with:
- `pc_use`: Final PC count to use
- `elbow_pc`: Elbow-detected PC
- `cumulative_pc`: PC at cumulative variance threshold (default 0.90)
- `variance_ratio`, `cumulative_variance`

Auto mode: `pc_use = max(elbow_pc, min(cumulative_pc, elbow_pc + buffer))`, clamped to [auto_min, available_pcs].

## Gene ID Conversion

### `map_ensembl_to_symbol(gene_ids)`
Strips Ensembl version suffixes, maps via EnsDb.Hsapiens.v86 (primary) or org.Hs.eg.db (fallback). Returns data.frame with Ensembl_ID and Gene columns.

### `convert_ensembl_matrix_to_symbols(count_matrix)`
Converts entire count matrix rownames. Collapses duplicated gene symbols by summing counts. Returns list(matrix, mapping).

## Doublet Detection

### `estimate_doublet_rate(capture_cells)`
Linear interpolation from 10x Genomics reference table. Clamps output to [0.004, 0.20].

## Visualization Helpers

### `create_discrete_palette(group_levels)`
Generates 20-color discrete palette, interpolates via colorRampPalette if more groups needed.

### `save_interactive_3d_umap(seurat_obj, group_by, output_file, ...)`
Exports interactive 3D UMAP as self-contained HTML via plotly. Auto-detects group_by from metadata or Idents.

### `get_expression_data_matrix(seurat_obj, assay="RNA")`
Safely gets log-normalized data, tries `layer="data"` (Seurat v5) then `slot="data"`.

### `get_counts_matrix(seurat_obj, assay="RNA", cells=NULL)`
Safely gets raw counts, tries `layer="counts"` (Seurat v5) then `slot="counts"`.

## Cluster-CellType Mapping

### `generate_cluster_maincelltype_plots(seurat_obj, genes, mapping_file, output_dir)`
Reads cluster→celltype CSV, generates:
- DotPlot of all genes by cluster with cell type labels
- Per-gene violin plots with cluster+celltype x-axis

## AUCell Helpers

### `generate_aucell_analysis(seurat_obj, gmt_file, output_dir, ...)`
Complete AUCell workflow:
1. Parse GMT file (handles standard and name+genes formats)
2. Build gene rankings
3. Calculate AUC scores
4. Explore thresholds
5. Generate UMAP score plots
6. Output per-group, per-celltype, per-cluster summaries

### `read_gmt_gene_sets(file_path, gene_universe)`
Smart GMT parser that auto-detects format:
- **Standard GMT**: col1=name, col2=description/URL, col3+=genes
- **Name+Genes**: col1=name, col2+=genes

Detection heuristic: checks if col2 contains spaces, URLs, NA-like values, or has low overlap with gene universe.

## File I/O

### `write_utf8_lines(lines, output_file)`
Writes character vector as UTF-8 text file.

### `write_utf8_csv(x, output_file, row.names=FALSE)`
Writes data.frame as UTF-8 CSV.

## Knockout Simulation

### `run_scTenifoldKnk_robust(countMatrix, gKO, ...)`
Tries native `scTenifoldKnk::scTenifoldKnk()` first. Falls back to stable workflow:
1. `makeNetworks()` → `tensorDecomposition()` → `strictDirection()`
2. Zero out target gene row in KO matrix
3. `safe_manifold_alignment()` with adaptive eigendecomposition
4. `dRegulation()` for differential regulation scores

### `safe_manifold_alignment(X, Y, d=2, nCores=1)`
Robust manifold alignment with adaptive eigenvalue thresholding. Expands eigendecomposition `k` if too few positive eigenvalues found.

### `prepare_knockout_input(count_mat, selected_genes, target_gene, ...)`
Filters genes (min detected cells) and cells (non-zero expression), ensures target gene retained.

## Overexpression Simulation

### `run_scTenifoldOverexpression_safe(countMatrix, gOE, ...)`
Virtual overexpression via network edge amplification (default 2x):
1. Build WT network (same as knockout)
2. Amplify positive outgoing edges of target gene
3. If no positive edges: try incoming edges → fallback to top-correlated genes
4. Manifold alignment + dRegulation
