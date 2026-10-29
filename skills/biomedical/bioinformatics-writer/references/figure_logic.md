# Figure Logic

Read `references/nature_figure_integration.md` with this file. Major figures
must follow this scientific and visual contract:

```text
one Results question -> one major Figure -> one core conclusion -> multiple evidence panels -> one unified rendering backend
```

Do not group panels by chart type. Group panels by biological claim, assign an
evidence hierarchy, and allocate visual area according to scientific
importance.

## Panel roles

Use complementary evidence:

- overview: workflow, cohort, sample grouping
- discovery: volcano, heatmap, UMAP, differential table summary
- association: clinical feature, survival, ROC, stage, treatment response
- characterization: enrichment, pathway score, immune infiltration, cell source
- mechanism: ligand-receptor, pathway activation, transcription factor, model
- validation: external cohort, protein/IHC, qPCR, cell assay, animal model
- intervention: knockdown, inhibitor, rescue, combination treatment

Also assign each panel one `evidence_tier`: `hero`, `primary`, `validation`, or
`control`. Require one hero for schematic-led, image-led, and asymmetric
figures. A `quantitative_grid` may set `hero_panel` to `null` and use no hero
when the evidence is genuinely equal in rank.

## Figure blueprint

```json
{
  "figure_id": "Figure 3",
  "title": "...",
  "result_question": "...",
  "claim": "...",
  "contract": {
    "core_conclusion": "Treatment X reduces Y by restoring Z.",
    "archetype": "asymmetric_mixed_modality",
    "evidence_hierarchy": {
      "hero_panel": "C",
      "primary_evidence": ["A", "B"],
      "validation_evidence": ["D"],
      "controls_robustness": ["E"]
    },
    "reviewer_risks": ["The representative image must be linked to quantification."],
    "image_integrity_notes": []
  },
  "panels": [
    {
      "label": "A",
      "experiment": "differential_expression",
      "evidence_tier": "primary",
      "title": "...",
      "plot_type": "volcano_plot",
      "input": "results/differential_expression.csv",
      "evidence": "...",
      "statistical_message": "...",
      "output": "figures/experiments/differential_expression/panels/Figure3A.png"
    }
  ],
  "layout": {
    "render_backend": "python",
    "backend_reason": "All quantitative inputs are tables and the complete layout requires GridSpec.",
    "figure_source": "figures/combined/sources/Figure3.py",
    "final_width_mm": 183,
    "final_height_mm": 150,
    "shared_legend": true,
    "style_map": {
      "control": "#4E79A7",
      "case": "#E15759"
    },
    "panel_slots": [
      {"label": "A", "row": 1, "column": 1, "rowspan": 1, "colspan": 1},
      {"label": "B", "row": 2, "column": 1, "rowspan": 1, "colspan": 1},
      {"label": "C", "row": 1, "column": 2, "rowspan": 2, "colspan": 2},
      {"label": "D", "row": 3, "column": 1, "rowspan": 1, "colspan": 2},
      {"label": "E", "row": 3, "column": 3, "rowspan": 1, "colspan": 1}
    ],
    "preview_output": "figures/combined/Figure3_preview.png",
    "publication_outputs": [
      "figures/combined/Figure3.svg",
      "figures/combined/Figure3.pdf",
      "figures/combined/Figure3_600dpi.tiff"
    ],
    "qa_output": "figures/combined/Figure3_qa.json"
  }
}
```

## Backend contract

Select one `render_backend` per major figure. Analysis modules may have used
different scientific backends, but the complete figure must be rendered,
arranged, labeled, previewed, exported, and visually checked through the one
backend recorded in its blueprint.

Use Python with matplotlib/seaborn plus GridSpec or subplot_mosaic, or R with
ggplot2 plus patchwork/cowplot/ComplexHeatmap. Create the complete editable
source at `figures/combined/sources/<Figure>.<py|R>` and generate the preview,
SVG, PDF, TIFF, and QA JSON from that source.

`scripts/compose_multipanel_figure.py` is a legacy compatibility preview tool.
Do not use it as the default renderer for new publication figures because it
cannot preserve a unified native layout or vector output.

## Experiment-scoped evidence workspace

Keep panel evidence and experiment-specific assets here:

```text
figures/
  experiments/
    <experiment_slug>/
      panels/
      sources/
      metadata/
  combined/
    sources/
```

Every panel must retain its experiment slug, traceable input, statistical
message, and experiment-scoped output path. Preserve panel metadata even when
the complete figure source redraws the quantitative panel from its table.

## Common figure progression

For transcriptomics plus immune infiltration:

```text
Figure 1: study design, cohort, QC, global expression structure
Figure 2: differential expression and key genes
Figure 3: functional enrichment and pathway activity
Figure 4: immune infiltration landscape
Figure 5: candidate gene/cell/pathway validation
Figure 6: proposed mechanism model
```

For high-mechanism papers:

```text
Figure 1: data-driven discovery
Figure 2: clinical relevance
Figure 3: functional validation
Figure 4: cell-cell interaction or receptor mechanism
Figure 5: downstream signaling
Figure 6: microenvironment remodeling
Figure 7: external/experimental validation
Figure 8: therapeutic intervention or final model
```

## Safety and verification

- Record the dimensions of raster inputs before rendering.
- Stop and redesign when a raster canvas would exceed 12,000 px in either
  dimension or 120 million pixels total.
- Require one non-overlapping slot for every panel.
- Require SVG, PDF, TIFF, preview PNG, complete figure source, and QA JSON.
- Inspect the SVG/PDF at final physical dimensions and verify selectable text,
  readable labels, consistent condition colors, non-overlapping annotations,
  and a correct shared legend.
