# Results Question Map

Generate this after real analysis outputs exist.

Purpose:

```text
analysis output -> biological question -> figure-level claim -> Results subsection
```

## Required Fields

```json
{
  "study_goal": "...",
  "results_questions": [
    {
      "id": "RQ1",
      "question": "...",
      "claim": "...",
      "source_analysis": ["..."],
      "source_files": ["..."],
      "figure": "Figure 1",
      "result_subsection_title": "...",
      "required_panels": ["..."],
      "main_statistics": ["..."],
      "limitations": ["..."]
    }
  ]
}
```

## How To Create Questions

Use the strongest completed analyses. Convert each result into a question:

- metadata/QC/PCA -> do groups differ globally or is the dataset suitable?
- differential expression -> which genes differ between groups?
- enrichment/GSEA/GSVA -> which biological programs are altered?
- immune infiltration -> which immune cells or immune states differ?
- correlation/network -> which genes/cells/pathways may connect the phenotype?
- external validation -> are findings reproducible?
- single-cell/spatial -> which cell types or locations explain the bulk signal?
- functional assays -> is the candidate functionally necessary or sufficient?

Reject a Results question if it has no traceable result file or only weak exploratory evidence.

## Claim Style

Good claim:

```text
ER status is associated with distinct immune infiltration patterns in breast cancer.
```

Bad claim:

```text
CIBERSORT boxplot result.
```

The claim should be biological, not merely a plot description.

