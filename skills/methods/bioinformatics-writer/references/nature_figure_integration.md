# Unified Publication Figure Contract

This reference adapts the Figure Contract, default stance, backend fragments,
common layout patterns, and QA contract from Yuan1z0825's `nature-figure`
skill. The adapted text and rules in this file have been changed for the
Bioinformatics Writer workflow. Upstream source:
<https://github.com/Yuan1z0825/nature-skills/tree/main/skills/nature-figure>.
The upstream work is licensed under Apache-2.0; the bundled license is at
`assets/licenses/nature-skills-APACHE-2.0.txt`.

Read this file before creating `figure_blueprint.json`, generating panel
sources, or rendering a combined figure.

## Figure contract

Treat each major figure as one visual scientific argument. Establish this
contract before writing plotting code:

```text
Core conclusion:
Figure archetype:
Target journal/output:
Final width and height:
Rendering backend and reason:
Hero panel:
Primary evidence:
Validation evidence:
Controls/robustness:
Panel map and slots:
Shared legend/direct-label strategy:
Statistics needed:
Source data needed:
Image-integrity notes:
Reviewer risks:
```

Apply these rules:

- Write the core conclusion as one sentence with a scientific verb.
- Give every panel one unique evidentiary job. Remove or merge a panel when
  hiding it would not weaken the argument.
- Separate hero, primary, validation, and control evidence explicitly. A
  `quantitative_grid` may record `hero_panel: null` when no panel should
  dominate; the other archetypes require one hero.
- Allocate visual area according to evidentiary importance; do not make every
  panel the same size merely because a regular grid is convenient.
- Keep one condition/method color mapping across all panels.
- Prefer one shared legend or direct labels over repeated legends.
- Treat sample size, statistics, source data, and image integrity as part of
  the figure contract, not as caption cleanup.

## Archetypes

Choose exactly one archetype for each major figure:

- `quantitative_grid`: numerical comparisons dominate. Use shared axes,
  aligned scales, compact legends, and an optional dominant summary panel.
- `schematic_led_composite`: a workflow, mechanism, cohort, or experimental
  design must be understood first. Give the schematic about 35-60% of the
  figure and place quantitative validation around or below it.
- `image_plate_plus_quant`: microscopy, pathology, spatial imaging, blots, or
  representative images lead. Pair the image plate with scale bars, crops,
  overlays, and linked quantification.
- `asymmetric_mixed_modality`: schematic, raster images, heatmaps, and
  quantitative plots coexist. Let a hero panel span rows or columns and rank
  the remaining panels by evidence value.

## Unified rendering backend

Select one rendering backend per major figure and record it as
`layout.render_backend`.

- Analysis modules may use different scientific backends. Export their
  verified results to traceable tables or image inputs first.
- Once a figure's rendering backend is selected, use it for the complete
  figure source, all data plots belonging to that figure, panel arrangement,
  labels, preview, vector/raster exports, and visual QA.
- Do not use Pillow as the default publication renderer and do not assemble a
  new publication figure from independent screenshots when the selected
  backend can lay it out natively.
- Reuse an explicit user choice. Otherwise select the backend that preserves
  the strongest editable sources and can reproduce all required panel types;
  record the concrete reason in `layout.backend_reason`.
- Stop before rendering when the selected runtime or required plotting/layout
  packages are unavailable. Do not silently cross-render with the other
  backend.

For Python, use matplotlib/seaborn plus `GridSpec` or `subplot_mosaic`. Preserve
editable SVG text (`svg.fonttype = "none"`) and TrueType PDF text
(`pdf.fonttype = 42`).

For R, use ggplot2 plus patchwork/cowplot/ComplexHeatmap as appropriate. Export
with svglite, cairo_pdf, and ragg so text and line art remain publication-ready.

## Layout source and outputs

Create one complete, editable source file for each major figure:

```text
figures/combined/sources/Figure1.py
figures/combined/sources/Figure2.R
```

The source must read the same traceable inputs named by the panel records and
must implement `layout.panel_slots`. It may use native image-reading functions
for microscopy or other inherently raster panels, but quantitative plots
should be drawn from source data in the selected backend rather than pasted as
screenshots.

Generate all of these from that source:

```text
figures/combined/Figure1_preview.png
figures/combined/Figure1.svg
figures/combined/Figure1.pdf
figures/combined/Figure1_600dpi.tiff
figures/combined/Figure1_qa.json
```

The PNG is the manuscript/DOCX preview. SVG/PDF are editable publication
outputs. TIFF is the high-resolution raster fallback.

## Layout patterns

- For a schematic-led figure, let the hero span the full top row and allocate
  about 45-60% of the height to it; place two to four quieter supporting plots
  below.
- For an asymmetric figure, let the central panel span multiple rows or
  columns. Do not normalize unequal scientific importance into equal boxes.
- For image plates, use black only inside image cells; keep the page canvas
  white. Place channel labels, calibrated scale bars, and crop guides directly
  on the images.
- For repeated clinical or subgroup comparisons, use semantically parallel
  columns and one shared legend strip.
- Reserve a dedicated legend slot when a large legend would compress data
  panels.
- Define the figure's visual vocabulary in the first overview/schematic panel
  and reuse its colors, symbols, sample classes, and direction throughout.

## QA contract

Before final delivery, require all of the following:

- A one-sentence core conclusion exists and every panel maps to it.
- The archetype, evidence hierarchy, applicable hero panel, and reviewer risks
  are declared.
- One backend produced the complete figure source, preview, publication
  exports, and visual QA render.
- Final dimensions match the recorded journal contract; use about 89 mm for a
  Nature-family single column or 183 mm for a double column when no more
  specific verified rule exists.
- Body, tick, and legend text remains readable at final size; dense journal
  figures usually use 5-7 pt text, with bold panel labels around 8 pt.
- SVG/PDF text remains editable and fonts are consistent.
- No rainbow color map or red/green-only encoding is used; grayscale remains
  interpretable.
- Every quantitative panel records `n`, replicate definition, center, spread,
  statistical test, correction, exact comparison, and source-data file.
- Every image panel records raw/processed file, crop, brightness/contrast or
  gamma, pseudo-color, scale calibration, stitching, reuse, and linked
  quantification.
- Quantitative plots trace to clean local tables, and exclusions record the
  rule plus before/after counts.
- SVG, PDF, TIFF, preview PNG, complete figure source, and QA notes are present.
- Open the SVG/PDF and inspect the rendered figure at final size; static source
  validation does not replace visual inspection.

Use `scripts/validate_figure_blueprint.py` before rendering and again with
`--require-panel-outputs --require-figure-source --require-publication-outputs`
before accepting the final figure bundle.
