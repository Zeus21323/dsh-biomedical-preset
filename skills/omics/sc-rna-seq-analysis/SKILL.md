---
name: sc-rna-seq-analysis
description: |
  Single-cell RNA-seq comprehensive analysis pipeline. Covers 17+ analysis modules:
  QC, decontX, doublet detection, normalization, PCA, Harmony, clustering, UMAP (2D/3D),
  cell type annotation (SingleR), marker genes, differential expression, cell proportion,
  nebula plots, circular UMAP, AUCell, gene knockout/overexpression simulation,
  scMetabolism, decoupleR pathway inference. Also supports flow cytometry FCS file parsing
  (flowio integration: extract events as NumPy arrays, read metadata/channels, convert to CSV/DataFrame).
  Trigger when user mentions: scRNA-seq, single-cell analysis, 单细胞分析, 单细胞测序,
  Seurat pipeline, cell clustering, cell type annotation, 细胞聚类, 细胞注释, FCS files, flow cytometry.
---

# Single-Cell RNA-seq Comprehensive Analysis

Complete R-based scRNA-seq analysis pipeline with 15 modules, supporting stage-by-stage execution.

## Quick Start

When the user requests scRNA-seq analysis, first determine what they need:

1. **Full pipeline**: Run all 15 modules from start to finish
2. **Specific stage(s)**: Run only the requested modules
3. **Generate code**: Produce a customized R script they can run themselves

### Required Input Files
- `*.rds` — Raw count matrix (genes x cells) with Ensembl IDs or gene symbols
- `gene.txt` — Gene list of interest (one gene per line)
- `genesymbols.gmt` — (Optional) GMT file for AUCell gene set analysis

### Key Parameters to Confirm
Before generating code, confirm:
- `workDir` — Working directory containing input files
- `input_file` — Path to the RDS file
- Group prefixes — How control/disease cells are identified in cell names

## Pipeline Stages

### Stage 1: Preprocessing & QC (Modules 01-04)
- Data loading, Ensembl→Symbol conversion
- Seurat object creation, basic QC filtering
- decontX ambient RNA removal (per sample)
- Doublet detection: scDblFinder (new) or DoubletFinder (legacy)

### Stage 2: Clustering & Annotation (Modules 05-07)
- Normalization, variable features, scaling
- PCA + Harmony batch correction
- Multi-resolution clustering + clustree
- UMAP (2D & 3D)
- SingleR cell type annotation

### Stage 3: Differential Analysis & Basic Viz (Modules 08-12)
- Marker gene analysis
- Differential expression (disease vs control per cell type)
- Cell proportion analysis
- Individual gene UMAP
- Nebula plots (galaxy visualization)
- Circular UMAP (plot1cell)

### Stage 4: Advanced Analysis (Modules 13-17)
- AUCell gene set activity scoring
- Gene knockout simulation (scTenifoldKnk)
- Gene overexpression simulation (scTenifoldNet)

### Stage 5: Metabolism & Pathway Activity (Modules 18-19)
- scMetabolism metabolic pathway scoring (AUCell + KEGG)
- decoupleR PROGENy pathway activity inference
- Both run as standalone scripts with Seurat v4/v5 compatibility

## Usage Patterns

### Pattern A: Generate Full Script
User says "帮我生成单细胞分析脚本" → Read the template, customize parameters, write to user's workDir.

### Pattern B: Guide Step by Step
User says "帮我做单细胞QC" → Load Stage 1 from template, guide through execution.

### Pattern C: Debug/Fix
User says "注释出错" → Reference troubleshooting guide, diagnose common SingleR/package issues.

## Template Script

The complete parameterized R script is at: `scripts/scRNA_comprehensive_analysis.R`

## Standalone Module Scripts

These scripts run independently (require a processed Seurat RData + cell mapping CSV):

- `scripts/scMetabolism_analysis.R` — scMetabolism metabolic pathway scoring (Module 18)
- `scripts/decoupleR_pathway_analysis.R` — decoupleR PROGENy pathway inference (Module 19)

## Reference Documents

- `references/module-guide.md` — All 19 modules with parameters and expected outputs
- `references/helper-functions.md` — Key helper functions explained
- `references/troubleshooting.md` — Common issues and solutions
- `references/project-customization.md` — How to customize the template for specific projects (NSCLC example)
