# Publication Figure Guidelines

These rules adapt the useful subset of K-Dense-AI's
`scientific-visualization` skill for Bioinformatics Writer. The upstream
project is MIT licensed: <https://github.com/K-Dense-AI/scientific-agent-skills>.

## Use the helper when creating Python figures

```python
from pathlib import Path
import sys

sys.path.insert(0, "/home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts")
from publication_figure_utils import (
    apply_publication_style,
    figure_size_inches,
    save_publication_figure,
)

apply_publication_style()
fig, ax = plt.subplots(figsize=figure_size_inches("nature_single"))
# draw one result panel here
save_publication_figure(
    fig,
    Path("figures/experiments/differential_expression/panels/Figure2A_volcano"),
    formats=("png", "pdf", "svg"),
    dpi=600,
)
```

Use an equivalent R/ggplot2 style when the analysis is written in R; the
directory and metadata rules remain the same.

## Minimum output rules

- Save a PNG preview and, for line art or statistical plots, a PDF or SVG.
- Use 300 DPI minimum for raster output; prefer 600 DPI for line art.
- Prefer vector PDF/SVG over JPEG for plots, heatmaps, and diagrams.
- Use the Okabe-Ito or another colorblind-safe palette.
- Avoid `jet`, rainbow ramps, red/green-only encodings, 3D effects, and chart
  decoration that does not carry data.
- Label axes with units and define whether error bars are SD, SEM, or CI.
- Report sample size and statistical test in the panel metadata or legend.
- Check that labels remain readable at the target journal's final width.
- Keep experiment-scoped panel previews free of A/B/C labels. Add panel labels,
  shared legends, and final layout in the complete figure source declared by
  `figure_blueprint.json`.

## Journal width presets

The bundled helper uses these approximate column widths:

| Preset | Width |
|---|---:|
| `nature_single` | 89 mm |
| `nature_double` | 183 mm |
| `science_single` | 55 mm |
| `science_double` | 175 mm |
| `cell_single` | 85 mm |
| `cell_double` | 178 mm |

If the target journal is unknown, use the default 89 mm single-column width,
record that assumption in panel metadata, and allow the user to change it.

## Relationship to unified figure rendering

The helper can style experiment-scoped previews and can also be imported by a
Python complete-figure source. Read `references/nature_figure_integration.md`.
For every new major Figure, use one Python or R source under
`figures/combined/sources/` to draw the quantitative panels, arrange all slots,
add A/B/C labels and shared legends, and export PNG/SVG/PDF/TIFF from the same
backend. `compose_multipanel_figure.py` is retained only for old projects and
must not be treated as a vector publication renderer.
