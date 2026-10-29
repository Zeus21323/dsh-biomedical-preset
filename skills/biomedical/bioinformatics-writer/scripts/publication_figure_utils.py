#!/usr/bin/env python3
"""Small publication-figure helpers for Bioinformatics Writer.

Adapted from the publication-style ideas in K-Dense-AI/scientific-agent-skills
(MIT licensed): https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/scientific-visualization

This module deliberately stays narrow: it provides a consistent style, a
colorblind-friendly palette, journal-sized canvases, and multi-format export.
It can be imported by the complete Python figure source declared in
figure_blueprint.json. That source owns panel layout, A/B/C labels, shared
legends, and final publication exports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


OKABE_ITO = (
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",
)

JOURNAL_WIDTH_MM = {
    "nature_single": 89,
    "nature_double": 183,
    "science_single": 55,
    "science_double": 175,
    "cell_single": 85,
    "cell_double": 178,
}


def apply_publication_style(
    *,
    font_size: float = 8,
    palette: Iterable[str] = OKABE_ITO,
) -> None:
    """Apply conservative publication defaults to the current matplotlib session."""

    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "figure.constrained_layout.use": True,
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": font_size,
            "axes.labelsize": font_size + 1,
            "axes.titlesize": font_size + 1,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "xtick.labelsize": max(6, font_size - 1),
            "ytick.labelsize": max(6, font_size - 1),
            "axes.prop_cycle": mpl.cycler(color=list(palette)),
        }
    )


def figure_size_inches(
    journal: str | None = None,
    *,
    height_mm: float = 65,
) -> tuple[float, float]:
    """Return a journal-aware (width, height) size in inches."""

    width_mm = JOURNAL_WIDTH_MM.get(journal or "", 89)
    mm_per_inch = 25.4
    return width_mm / mm_per_inch, height_mm / mm_per_inch


def save_publication_figure(
    fig,
    filename: str | Path,
    *,
    formats: Iterable[str] = ("png", "pdf", "svg"),
    dpi: int = 600,
) -> list[Path]:
    """Save a matplotlib figure in publication and editable formats."""

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    supported = {"png", "pdf", "svg", "eps", "tif", "tiff"}
    for fmt in formats:
        normalized = fmt.lower().lstrip(".")
        if normalized not in supported:
            raise ValueError(f"unsupported figure format: {fmt}")
        output = path.with_suffix(f".{normalized}")
        save_kwargs = {
            "format": normalized,
            "dpi": dpi,
            "bbox_inches": "tight",
            "pad_inches": 0.08,
            "facecolor": "white",
        }
        if normalized in {"tif", "tiff"}:
            save_kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(output, **save_kwargs)
        outputs.append(output)
    return outputs


def check_figure_size(fig, journal: str | None = None, *, tolerance_mm: float = 2.0) -> dict:
    """Check the current figure width against a journal column width."""

    width_mm = float(fig.get_size_inches()[0] * 25.4)
    target_mm = float(JOURNAL_WIDTH_MM.get(journal or "", 89))
    return {
        "journal": journal or "default",
        "width_mm": round(width_mm, 2),
        "target_width_mm": target_mm,
        "within_tolerance": abs(width_mm - target_mm) <= tolerance_mm,
    }


def _self_test() -> None:
    import matplotlib.pyplot as plt

    apply_publication_style()
    fig, ax = plt.subplots(figsize=figure_size_inches("nature_single"))
    ax.plot([0, 1, 2], [0, 1, 0])
    ax.set_xlabel("Example (a.u.)")
    ax.set_ylabel("Signal (a.u.)")
    result = check_figure_size(fig, "nature_single")
    assert result["within_tolerance"], result
    output_dir = Path("/tmp/bioinformatics-writer-figure-utils-test")
    outputs = save_publication_figure(fig, output_dir / "example", formats=("png", "pdf"), dpi=150)
    assert all(path.exists() for path in outputs), outputs
    plt.close(fig)
    print("publication_figure_utils self-test passed")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        _self_test()
    else:
        parser.error("use --self-test or import this module from a plotting script")
