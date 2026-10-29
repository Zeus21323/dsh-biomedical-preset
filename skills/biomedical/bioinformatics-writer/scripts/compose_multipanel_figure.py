#!/usr/bin/env python3
"""Legacy raster-grid preview composer for pre-unified figure projects.

New publication figures must use the single Python/R complete-figure source
declared by figure_blueprint.json. This script is retained only for backwards
compatibility and does not preserve vector panel content.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - dependency message path
    raise SystemExit("dependency_not_found: Pillow. Install with `pip install pillow`.") from exc


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def parse_grid(value: str | None, panel_count: int) -> tuple[int, int]:
    if value:
        match = re.fullmatch(r"\s*(\d+)\s*x\s*(\d+)\s*", value.lower())
        if match:
            rows, cols = int(match.group(1)), int(match.group(2))
            if rows > 0 and cols > 0 and rows * cols >= panel_count:
                return rows, cols
    cols = math.ceil(math.sqrt(panel_count))
    rows = math.ceil(panel_count / cols)
    return rows, cols


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def as_rgb_white(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, "white")
        converted = image.convert("RGBA")
        background.paste(converted, mask=converted.getchannel("A"))
        return background
    return image.convert("RGB")


def resize_to_max_width(image: Image.Image, max_width: int | None) -> Image.Image:
    if not max_width or image.width <= max_width:
        return image
    ratio = max_width / image.width
    new_size = (max_width, max(1, round(image.height * ratio)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def find_panel_image(project_root: Path, panel: dict) -> Path:
    for key in ("output", "image", "file"):
        raw = panel.get(key)
        if isinstance(raw, str) and raw.strip():
            path = resolve_path(project_root, raw)
            if path.suffix.lower() in IMAGE_SUFFIXES:
                return path
    raw_input = panel.get("input")
    if isinstance(raw_input, str) and raw_input.strip():
        path = resolve_path(project_root, raw_input)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            return path
    raise ValueError(f"panel {panel.get('label', '?')} has no image path; set panel.output after generating panels")


def choose_outputs(project_root: Path, figure: dict, output_override: str | None) -> list[Path]:
    layout = figure.get("layout") or {}
    outputs: list[str] = []
    if output_override:
        outputs.append(output_override)
    else:
        preview = layout.get("preview_output")
        if isinstance(preview, str) and preview.strip():
            outputs.append(preview)
        publication_outputs = layout.get("publication_outputs")
        if isinstance(publication_outputs, list):
            outputs.extend(item for item in publication_outputs if isinstance(item, str) and item.strip())
    if not outputs:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(figure.get("figure_id", "Figure")))
        outputs.append(f"figures/combined/{safe_id}_preview.png")
    return [resolve_path(project_root, raw) for raw in outputs]


def draw_label(image: Image.Image, label: str, font_size: int, margin: int) -> None:
    draw = ImageDraw.Draw(image)
    font = load_font(font_size)
    text = label.strip()
    if not text:
        return
    bbox = draw.textbbox((0, 0), text, font=font)
    pad_x = max(8, font_size // 4)
    pad_y = max(6, font_size // 6)
    x, y = margin, margin
    rect = (x - pad_x, y - pad_y, x + (bbox[2] - bbox[0]) + pad_x, y + (bbox[3] - bbox[1]) + pad_y)
    draw.rectangle(rect, fill="white")
    draw.text((x, y), text, fill="black", font=font)


def compose_figure(
    figure: dict,
    project_root: Path,
    max_total_pixels: int,
    max_dimension: int,
    gap: int,
    label_size: int,
    label_margin: int,
) -> Image.Image:
    panels = figure.get("panels")
    if not isinstance(panels, list) or not panels:
        raise ValueError(f"{figure.get('figure_id', 'figure')}: panels must be a non-empty array")

    layout = figure.get("layout") or {}
    max_panel_width = layout.get("max_panel_width_px")
    if not isinstance(max_panel_width, int) or max_panel_width <= 0:
        max_panel_width = None

    loaded: list[tuple[str, Image.Image, Path]] = []
    for panel in panels:
        path = find_panel_image(project_root, panel)
        if not path.exists():
            raise FileNotFoundError(f"panel image not found for {panel.get('label', '?')}: {path}")
        with Image.open(path) as original:
            image = as_rgb_white(original)
        image = resize_to_max_width(image, max_panel_width)
        label = str(panel.get("label", "")).strip()
        draw_label(image, label, label_size, label_margin)
        loaded.append((label, image, path))
        print(f"panel {label or '?'}: {path} -> {image.width}x{image.height}")

    rows, cols = parse_grid(layout.get("preferred_grid"), len(loaded))
    col_widths = [0] * cols
    row_heights = [0] * rows
    for idx, (_, image, _) in enumerate(loaded):
        row, col = divmod(idx, cols)
        col_widths[col] = max(col_widths[col], image.width)
        row_heights[row] = max(row_heights[row], image.height)

    canvas_width = sum(col_widths) + gap * (cols + 1)
    canvas_height = sum(row_heights) + gap * (rows + 1)
    total_pixels = canvas_width * canvas_height
    print(f"canvas: {canvas_width}x{canvas_height} ({total_pixels} pixels), grid {rows}x{cols}")

    if canvas_width > max_dimension or canvas_height > max_dimension:
        raise ValueError(f"canvas dimension too large: {canvas_width}x{canvas_height}; limit is {max_dimension}")
    if total_pixels > max_total_pixels:
        raise ValueError(f"canvas too large: {total_pixels} pixels; limit is {max_total_pixels}")

    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    y = gap
    idx = 0
    for row in range(rows):
        x = gap
        for col in range(cols):
            if idx >= len(loaded):
                break
            _, image, _ = loaded[idx]
            x_offset = x + (col_widths[col] - image.width) // 2
            y_offset = y + (row_heights[row] - image.height) // 2
            canvas.paste(image, (x_offset, y_offset))
            x += col_widths[col] + gap
            idx += 1
        y += row_heights[row] + gap

    return canvas


def iter_figures(data: dict, figure_id: str | None) -> Iterable[dict]:
    figures = data.get("figures")
    if not isinstance(figures, list):
        raise ValueError("figure_blueprint.json must contain a figures array")
    for figure in figures:
        if figure_id is None or figure.get("figure_id") == figure_id:
            yield figure


def save_outputs(image: Image.Image, outputs: list[Path], dpi: int) -> None:
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        suffix = output.suffix.lower()
        if suffix in {".tif", ".tiff"}:
            image.save(output, compression="tiff_lzw", dpi=(dpi, dpi))
        elif suffix == ".pdf":
            image.save(output, "PDF", resolution=dpi)
        else:
            image.save(output, optimize=False, compress_level=1, dpi=(dpi, dpi))
        print(f"saved: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", type=Path, help="Path to figure_blueprint.json")
    parser.add_argument("--figure", help="Compose only this figure_id, e.g. 'Figure 3'")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Base directory for relative paths")
    parser.add_argument("--output", help="Override output path for a single figure")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--gap", type=int, default=40)
    parser.add_argument("--label-size", type=int, default=48)
    parser.add_argument("--label-margin", type=int, default=18)
    parser.add_argument("--max-total-pixels", type=int, default=120_000_000)
    parser.add_argument("--max-dimension", type=int, default=12_000)
    args = parser.parse_args()

    print(
        "warning: legacy raster composer; use layout.figure_source and the recorded render_backend for new publication figures",
        file=sys.stderr,
    )

    project_root = args.project_root.resolve()
    try:
        data = load_json(args.blueprint)
        selected = list(iter_figures(data, args.figure))
        if not selected:
            raise ValueError(f"figure not found: {args.figure}")
        if args.output and len(selected) != 1:
            raise ValueError("--output can only be used when composing one figure")
        for figure in selected:
            print(f"composing {figure.get('figure_id', 'figure')}")
            image = compose_figure(
                figure=figure,
                project_root=project_root,
                max_total_pixels=args.max_total_pixels,
                max_dimension=args.max_dimension,
                gap=args.gap,
                label_size=args.label_size,
                label_margin=args.label_margin,
            )
            outputs = choose_outputs(project_root, figure, args.output)
            save_outputs(image, outputs, args.dpi)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
