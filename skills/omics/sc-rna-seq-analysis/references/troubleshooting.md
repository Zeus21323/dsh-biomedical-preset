# Troubleshooting Guide

## Environment & Package Issues

### "Package 'X' is not installed"
Check BiocManager: `BiocManager::install(c("celda", "scDblFinder", "SingleCellExperiment", "scTenifoldKnk", "scTenifoldNet", "harmony", "plot1cell", "AUCell", "GSEABase"))`

### Seurat v5 Compatibility
Script handles both Seurat v4 and v5:
- v5 uses `layer="counts"` / `layer="data"`
- v4 uses `slot="counts"` / `slot="data"`
- All `GetAssayData()` calls have tryCatch fallbacks

### SingleR Annotation Fails
Common causes:
1. **celldex not installed**: `BiocManager::install("celldex")`
2. **Memory issue**: HumanPrimaryCellAtlasData is large; try reducing cells
3. **Fallback**: Script auto-falls back to `Cluster_N` labels if SingleR errors

## Data Input Issues

### "No group prefixes found in cell names"
Supported formats (auto-detected):
- `control.GSM4774936_AAAC...` (dot-separated)
- `control_GSM4774936_AAAC...` (underscore-separated)
- `Control.` / `Control_` (case-insensitive)
- `Disease.` / `Disease_` / `Treat.` / `Treat_`
- Fallback: `sub("_[^_]+$", "", cell_name)` strips the last underscore-delimited segment

### "sample_id still contains barcodes" after rerunning decontX
Happens when re-running the decontX section interactively without restarting from the beginning. The `extract_sample_id()` function expects GSM-pattern sample IDs. Restart from the script beginning.

### Gene list file issues
- File must exist at `workDir/gene.txt`
- One gene per line, UTF-8 encoding
- Empty lines and whitespace auto-trimmed
- Genes not found in expression matrix are reported and skipped

## DecontX Issues

### decontX fails for some samples
- Script catches errors per sample and preserves raw counts for failed samples
- Cells with failed decontX are kept (not filtered)
- Check `03_decontX_Summary.csv` for per-sample status

### All cells removed by contamination filter
- Try: lower `decontx_contamination_threshold` (default 0.3)
- Or: inspect contamination distribution in `03_decontX_Contamination_Distribution.pdf`

## Doublet Detection Issues

### scDblFinder vs DoubletFinder
- **scDblFinder** (active code): Faster, per-sample, recommended for most use cases
- **DoubletFinder** (legacy, inside `if(FALSE){...}`): Requires PCA+UMAP+clustering per sample, more robust for certain datasets
- To switch: remove the `if(FALSE){...}` wrapper and comment out the scDblFinder block

### Sample with <100 cells
- scDblFinder: skipped, all cells retained as singlet
- DoubletFinder legacy: falls back to scDblFinder if available

## Clustering Issues

### "No PCA dimensions available"
- Check that `n_pcs` (20) ≤ min(ncol-1, nrow-1, n_variable_features)
- If very small dataset: reduce `n_pcs` parameter

### Harmony issues
- Requires ≥2 groups in `harmony_group` column
- If only 1 group: Harmony auto-skipped with warning
- Convergence plot saved to `04.PCA_Analysis/Harmony_Convergence.pdf`

## AUCell Issues

### GMT file not found
- Must be named `genesymbols.gmt` in workDir
- Tab-separated format: `GENESET_NAME\tdescription\tGENE1\tGENE2\t...`

### No gene sets matched
- Check gene symbols match between GMT and expression matrix
- Script auto-intersects each gene set with matrix rownames
- Zero-match gene sets are reported and dropped

### PDF won't open (locked by another program)
- Script auto-detects this and saves with timestamp suffix
- Message: "原PDF可能正在被打开或占用，已另存为：..."

## Knockout/Overexpression Issues

### "细胞数不足" (insufficient cells)
- Minimum 50 cells after filtering for knockout
- Minimum 50 cells per group for differential expression
- Relax constraints: lower `qc_minLSize`, raise `qc_mtThreshold`

### scTenifoldKnk fails
- Falls back to stable workflow: `makeNetworks → tensorDecomposition → strictDirection → manifoldAlignment`
- If native `scTenifoldKnk()` fails, the robust fallback runs automatically
- Check `06_Knockout_Error.txt` in each gene's output directory

### Manifold alignment dimension adjustment
- If <2 positive eigenvalues found, script expands eigendecomposition k
- If still insufficient, d is auto-adjusted to available dimensions
- Message: "Manifold alignment 有效维度不足，自动将 d 从 X 调整为 Y"
