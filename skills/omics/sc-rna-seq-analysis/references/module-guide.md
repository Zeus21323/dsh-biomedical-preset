# Module Guide — 15 Analysis Modules

## Stage 1: Preprocessing & QC

### 01. Data Preprocessing
- **Input**: RDS file with raw count matrix
- **Key steps**: Ensembl→Gene Symbol conversion, group prefix auto-detection
- **Output**: `01.Data_Preprocessing/01_Raw_Combined_Data.rds`, `02_Ensembl_to_GeneSymbol_Mapping.csv`
- **Params**: `min_cells=3`, `min_features=200`

### 02. Quality Control
- **Basic QC**: Filter by nFeature_RNA (≥200), percent.mt (<15%)
- **decontX**: Per-sample ambient RNA removal, contamination threshold 0.3
- **Doublet detection**: scDblFinder per-sample (new default) or DoubletFinder (legacy, controlled by `if(FALSE){...}` block)
- **Output**: `02.Quality_control/01_Quality_Violin_Before_Filter.pdf`, `02_QC_Summary.csv`, `03_decontX_Summary.csv`, `04_scDblFinder_Summary.csv`

### 03. Feature Selection
- **Method**: `vst`, 2000 variable genes
- **Output**: `03.Feature_Selection/01_Variable_Features.pdf`, `02_Variable_Genes_List.csv`

### 04. PCA Analysis
- **n_pcs**: 20 (default), auto elbow detection for downstream
- **Harmony**: Optional batch correction by `sample_id`, theta=2, lambda=1
- **Output**: `04.PCA_Analysis/01_PCA_Plot.pdf`, `04_PCA_Results.csv`, Harmony convergence plot

## Stage 2: Clustering & Annotation

### 05. Clustering Analysis
- **Multi-resolution**: seq(0.1, 1.0, 0.1) with clustree visualization
- **Final resolution**: 0.3 (default)
- **Output**: `05.Clustering_Analysis/01_Clustree_Analysis.pdf`, `02_Cluster_Assignments.txt`

### 06. UMAP Visualization
- **2D UMAP**: Standard UMAP with cluster labels
- **3D UMAP**: Interactive HTML (plotly)
- **Output**: `06.UMAP_Visualization/01_UMAP_Clusters.pdf`, `18.Interactive_3D_UMAP/01_UMAP_Clusters_3D.html`

### 07. Cell Type Annotation (SingleR)
- **Reference**: HumanPrimaryCellAtlasData (celldex)
- **Method**: Cluster-level annotation → mapped to individual cells
- **Output**: `07.Cell_Type_Annotation/01_Auto_Annotation_UMAP.pdf`, `02_Cell_Type_Annotations.csv`, `Cluster_to_CellType_Mapping.csv`
- **Group comparison**: `03_Group_Comparison.pdf` (split by control/Disease)
- **Marker bubble**: `04_Cell_Type_Marker_Bubble.pdf` (top markers per cell type)

## Stage 3: Differential Analysis & Basic Viz

### 08. Marker Gene Analysis
- **FindAllMarkers**: min.pct=0.1, logfc.threshold=1
- **Output**: `08.Marker_Gene_Analysis/01_Significant_Marker_Genes.txt`

### 09. Differential Expression
- **Per cell type**: control vs Disease, min 3 cells per group
- **Output**: `09.Differential_Gene_Analysis/{celltype}_diffGenes.txt`

### 10. Cell Proportion Analysis
- **Stacked barplot**: control vs Disease proportions
- **Output**: `10.Cell_Proportion_Analysis/01_Cell_Type_Proportions.csv`, `02_Cell_Proportion_Barplot.pdf`

### 11. Heatmap Visualization
- **Top 10 markers** per cluster heatmap
- **Output**: `11.Heatmap_Visualization/01_Marker_Genes_Heatmap.pdf`

## Stage 4: Advanced Visualization

### 12. Individual Gene UMAP
- **Per gene**: FeaturePlot, combined UMAP+barplot, group comparison
- **Output**: `14.Individual_Gene_UMAP/Individual_FeaturePlots/`, `Combined_Analysis/`, `Gene_Statistics/`

### 13. Nebula Plots (Galaxy)
- **Black theme** density plot with convex hulls
- **Output**: `15.Nebula_Plots/01_Nebula_Plot_by_Group.pdf`, `02_Nebula_Plot_Single.pdf`

### 14. Circular UMAP (plot1cell)
- **Per group**: All cells + control + Disease circular plots
- **Output**: `16.Circular_UMAP/01_Circular_UMAP_All_Cells.pdf`, `02_Circular_UMAP_control.pdf`, `03_Circular_UMAP_Disease.pdf`

### 15. AUCell Analysis
- **Input**: `genesymbols.gmt` in workDir
- **Steps**: Build rankings → calc AUC → explore thresholds → per-group/per-cluster summary
- **Output**: `19.AUCell_Analysis/01-12_*.csv/pdf`, UMAP score plots

### 16. Gene Knockout Simulation
- **Method**: scTenifoldKnk on Disease-group cells only
- **Per gene**: Z-score scatter, top-20 barplot, summary tables
- **Output**: `17.Gene_Knockout_Analysis/Gene_{name}/`

### 17. Gene Overexpression Simulation
- **Method**: scTenifoldNet virtual overexpression (2x default factor)
- **Per gene**: Scatter plot, barplot, summary tables
- **Output**: `20.Gene_Overexpression_Analysis/Gene_{name}/`

## Stage 5: Metabolism & Pathway Activity

### 18. scMetabolism Analysis
- **Script**: `scripts/scMetabolism_analysis.R` (standalone)
- **Method**: scMetabolism with AUCell scoring on KEGG metabolic pathways
- **Prerequisites**: Seurat object with UMAP reduction + Cell-to-CellType mapping CSV
- **Seurat v4/v5 compatible** with automatic layer detection and join
- **Output** (in `01.scMetabolism_Analysis/`):
  - `01_scMetabolism_Score_Matrix.csv` — Raw pathway scores (pathways × cells)
  - `02_scMetabolism_Score_Matrix_RowZscore.csv` — Row Z-scored matrix
  - `04/05/06_Pathway_Score_By_*.csv` — Summaries by cell type, group, and combination
  - `07/08_Heatmap_scMetabolism_*.pdf` — Heatmaps by cell type and cell type+group
  - `10_Dotplot_scMetabolism_TopPathways_By_CellType.pdf` — Dot plot of top variable pathways
  - `11/12_Boxplot_scMetabolism_*.pdf` — Boxplots by cell type and group
  - `13_Differential_scMetabolism_By_Group.csv` — Wilcoxon test (2-group only)
  - `14_UMAP_scMetabolism_TopPathways.pdf` — FeaturePlot per top pathway
  - `16_Seurat_with_scMetabolism.rds` — Seurat object with METABOLISM assay
- **Params**: `metabolism_method="AUCell"`, `metabolism_type="KEGG"`, `top_pathway_n=20`

### 19. decoupleR Pathway Activity Inference
- **Script**: `scripts/decoupleR_pathway_analysis.R` (standalone)
- **Method**: PROGENy pathway network + Multivariate Linear Model (run_mlm)
- **14 pathways**: Androgen, EGFR, Estrogen, Hypoxia, JAK-STAT, MAPK, NFkB, p53, PI3K, TGFb, TNFa, Trail, VEGF, WNT
- **Prerequisites**: Seurat object with UMAP reduction + Cell-to-CellType mapping CSV
- **Output** (in `01.decoupleR_Activity_Inference/`):
  - `01_PROGENy_Network.csv` — Downloaded PROGENy gene-pathway network
  - `06/07/08_通路活性_*.csv` — Summaries by cell type, group, and combination
  - `09/11_*热图.pdf` — Heatmaps
  - `12_通路活性UMAP.pdf` — FeaturePlot per pathway
  - `14/15_*箱线图.pdf` — Boxplots by cell type and group
  - `16_分组通路差异检验.csv` — Wilcoxon test (2-group only)
  - `17_带通路活性的Seurat对象.rds` — Seurat object with pathways assay

## Key Parameters Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| logFCfilter | 1 | logFC threshold for DEG |
| adjPvalFilter | 0.05 | Adjusted p-value cutoff |
| n_variable_features | 2000 | Number of HVGs |
| n_pcs | 20 | Max PCs to compute |
| cluster_resolution | 0.3 | Final clustering resolution |
| percent_mt_max | 15 | Max MT% for QC |
| decontx_contamination_threshold | 0.3 | decontX contamination cutoff |
| harmony_theta | 2 | Harmony diversity penalty |
| harmony_lambda | 1 | Harmony ridge penalty |
