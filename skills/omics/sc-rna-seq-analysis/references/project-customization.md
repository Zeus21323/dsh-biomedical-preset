# Project Customization Guide

## How to Adapt the Template for a Specific Project

The template script at `scripts/scRNA_comprehensive_analysis.R` is designed to be
customized. Below is a real-world example based on an NSCLC analysis project.

## Example: NSCLC Single-Cell Analysis

### Changes from Template

| Item | Template Value | NSCLC Project Value |
|------|---------------|-------------------|
| `workDir` | `""` (empty, must fill) | `"H:\\常用分析生信\\515.非小细胞肺癌单细胞分析，虚拟过表达+虚拟敲除分析"` |
| `input_file` | `"GSE331114_scRNA_counts.rds"` | `"nsclc_single_cell_matrix.rds"` |
| Project type | PBMC/blood | NSCLC tumor |

### Step-by-Step Customization

1. **Set workDir**: Full path to the project folder containing input files
2. **Set input_file**: Name of the RDS file with raw counts matrix
3. **Prepare gene.txt**: One gene symbol per line, UTF-8 encoded
4. **Prepare genesymbols.gmt** (optional): For AUCell analysis
5. **Verify cell naming**: Ensure cell names contain group prefixes (control./Disease./Treat.)

### Common Project Types

| Tissue Type | Typical Cell Types | Recommended SingleR Ref |
|------------|-------------------|------------------------|
| PBMC/Blood | T cells, B cells, Monocytes, NK | HumanPrimaryCellAtlasData |
| NSCLC/Lung | Epithelial, Fibroblast, Immune | HumanPrimaryCellAtlasData + HPCA |
| Brain | Neurons, Glia, Microglia | BlueprintEncodeData |
| Liver | Hepatocytes, Cholangiocytes, Kupffer | HumanPrimaryCellAtlasData |

### Parameter Adjustments by Project Type

- **Immune-rich samples**: Default parameters work well
- **Tumor samples**: May need higher `cluster_resolution` (0.5-0.8) to separate malignant subclones
- **Small samples (<1000 cells)**: Reduce `n_pcs` to 10, skip Harmony
- **Large samples (>50000 cells)**: Reduce `n_variable_features` to 1000 for speed

### Template vs Instance Pattern

The template file:
- Has `workDir <- ""` (empty string) — requires user to fill in
- Has generic `input_file` name — user renames
- All 15 modules active — user can skip via parameter or comment out sections

When generating an instance for a user:
1. Copy the template
2. Replace `workDir` and `input_file` with user's actual paths
3. Adjust parameters if needed based on tissue/project type
4. Confirm which modules to include
5. Write the customized script to user's workDir
