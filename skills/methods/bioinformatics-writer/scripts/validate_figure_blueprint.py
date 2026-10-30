#!/usr/bin/env python3
"""Validate a Bioinformatics Writer figure_blueprint.json file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_FIGURE = ("figure_id", "title", "result_question", "claim", "contract", "panels", "layout")
REQUIRED_PANEL = (
    "label",
    "experiment",
    "evidence_tier",
    "plot_type",
    "input",
    "evidence",
    "statistical_message",
    "output",
)
REQUIRED_CONTRACT = ("core_conclusion", "archetype", "evidence_hierarchy", "reviewer_risks")
REQUIRED_HIERARCHY = ("hero_panel", "primary_evidence", "validation_evidence", "controls_robustness")
REQUIRED_LAYOUT = (
    "render_backend",
    "backend_reason",
    "figure_source",
    "final_width_mm",
    "final_height_mm",
    "panel_slots",
    "preview_output",
    "publication_outputs",
    "qa_output",
)
ARCHETYPES = {
    "quantitative_grid",
    "schematic_led_composite",
    "image_plate_plus_quant",
    "asymmetric_mixed_modality",
}
EVIDENCE_TIERS = {"hero", "primary", "validation", "control"}
EXPERIMENT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate_label_array(value: object, prefix: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{prefix} must be an array")
        return []
    labels: list[str] = []
    for index, item in enumerate(value, start=1):
        if not is_nonempty_string(item):
            errors.append(f"{prefix}[{index}] must be a non-empty string")
        else:
            labels.append(item.strip())
    if len(labels) != len(set(labels)):
        errors.append(f"{prefix} contains duplicate panel labels")
    return labels


def validate_layout(
    figure_id: str,
    layout: object,
    panel_labels: set[str],
    project_root: Path,
    require_figure_source: bool,
    require_publication_outputs: bool,
    errors: list[str],
) -> None:
    if not isinstance(layout, dict):
        errors.append(f"{figure_id}.layout must be an object")
        return

    for key in REQUIRED_LAYOUT:
        if key not in layout:
            errors.append(f"{figure_id}.layout: missing key {key}")

    backend = layout.get("render_backend")
    if backend not in {"python", "r"}:
        errors.append(f"{figure_id}.layout.render_backend must be python or r")
    if not is_nonempty_string(layout.get("backend_reason")):
        errors.append(f"{figure_id}.layout.backend_reason must be a non-empty string")

    raw_source = layout.get("figure_source")
    source_path: Path | None = None
    if not is_nonempty_string(raw_source):
        errors.append(f"{figure_id}.layout.figure_source must be a non-empty string")
    else:
        raw_source = raw_source.strip()
        normalized = Path(raw_source).as_posix()
        if "figures/combined/sources/" not in normalized:
            errors.append(f"{figure_id}.layout.figure_source must be under figures/combined/sources/")
        suffix = Path(raw_source).suffix.lower()
        if backend == "python" and suffix != ".py":
            errors.append(f"{figure_id}.layout.figure_source must end in .py for the python backend")
        if backend == "r" and suffix not in {".r", ".rmd", ".qmd"}:
            errors.append(f"{figure_id}.layout.figure_source must end in .R, .Rmd, or .qmd for the r backend")
        source_path = resolve_path(project_root, raw_source)
        if require_figure_source and not source_path.exists():
            errors.append(f"{figure_id}.layout.figure_source missing on disk: {raw_source}")

    for key in ("final_width_mm", "final_height_mm"):
        if not is_positive_number(layout.get(key)):
            errors.append(f"{figure_id}.layout.{key} must be a positive number")

    slots = layout.get("panel_slots")
    slot_labels: list[str] = []
    occupied: dict[tuple[int, int], str] = {}
    if not isinstance(slots, list) or not slots:
        errors.append(f"{figure_id}.layout.panel_slots must be a non-empty array")
    else:
        for index, slot in enumerate(slots, start=1):
            prefix = f"{figure_id}.layout.panel_slots[{index}]"
            if not isinstance(slot, dict):
                errors.append(f"{prefix} must be an object")
                continue
            label = slot.get("label")
            if not is_nonempty_string(label):
                errors.append(f"{prefix}.label must be a non-empty string")
                continue
            label = label.strip()
            slot_labels.append(label)
            geometry: dict[str, int] = {}
            valid_geometry = True
            for key in ("row", "column", "rowspan", "colspan"):
                value = slot.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    errors.append(f"{prefix}.{key} must be a positive integer")
                    valid_geometry = False
                else:
                    geometry[key] = value
            relative_size = slot.get("relative_size")
            if relative_size is not None and not is_positive_number(relative_size):
                errors.append(f"{prefix}.relative_size must be a positive number when present")
            if valid_geometry:
                for row in range(geometry["row"], geometry["row"] + geometry["rowspan"]):
                    for column in range(geometry["column"], geometry["column"] + geometry["colspan"]):
                        cell = (row, column)
                        if cell in occupied:
                            errors.append(
                                f"{figure_id}.layout.panel_slots overlap at row {row}, column {column}: "
                                f"{occupied[cell]} and {label}"
                            )
                        else:
                            occupied[cell] = label

    if len(slot_labels) != len(set(slot_labels)):
        errors.append(f"{figure_id}.layout.panel_slots contains duplicate labels")
    if set(slot_labels) != panel_labels:
        missing = sorted(panel_labels - set(slot_labels))
        extra = sorted(set(slot_labels) - panel_labels)
        if missing:
            errors.append(f"{figure_id}.layout.panel_slots missing panel labels: {', '.join(missing)}")
        if extra:
            errors.append(f"{figure_id}.layout.panel_slots has unknown labels: {', '.join(extra)}")

    preview = layout.get("preview_output")
    if not is_nonempty_string(preview) or Path(str(preview)).suffix.lower() != ".png":
        errors.append(f"{figure_id}.layout.preview_output must be a PNG path")

    publication_outputs = layout.get("publication_outputs")
    output_paths: list[str] = []
    if not isinstance(publication_outputs, list) or not publication_outputs:
        errors.append(f"{figure_id}.layout.publication_outputs must be a non-empty array")
    else:
        for index, item in enumerate(publication_outputs, start=1):
            if not is_nonempty_string(item):
                errors.append(f"{figure_id}.layout.publication_outputs[{index}] must be a non-empty string")
            else:
                output_paths.append(item.strip())
        suffixes = {Path(item).suffix.lower() for item in output_paths}
        if ".svg" not in suffixes:
            errors.append(f"{figure_id}.layout.publication_outputs must include SVG")
        if ".pdf" not in suffixes:
            errors.append(f"{figure_id}.layout.publication_outputs must include PDF")
        if not suffixes.intersection({".tif", ".tiff"}):
            errors.append(f"{figure_id}.layout.publication_outputs must include TIFF")

    qa_output = layout.get("qa_output")
    if not is_nonempty_string(qa_output) or Path(str(qa_output)).suffix.lower() != ".json":
        errors.append(f"{figure_id}.layout.qa_output must be a JSON path")

    if require_publication_outputs:
        required_paths = []
        if is_nonempty_string(preview):
            required_paths.append(str(preview))
        required_paths.extend(output_paths)
        if is_nonempty_string(qa_output):
            required_paths.append(str(qa_output))
        for raw in required_paths:
            if not resolve_path(project_root, raw).exists():
                errors.append(f"{figure_id}: required figure output missing on disk: {raw}")


def validate(
    data: dict,
    project_root: Path,
    require_inputs: bool,
    require_panel_outputs: bool,
    require_figure_source: bool = False,
    require_publication_outputs: bool = False,
) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    figures = data.get("figures")
    if not isinstance(figures, list) or not figures:
        return ["figures must be a non-empty array"]

    seen_figures: set[str] = set()
    for fig_idx, figure in enumerate(figures, start=1):
        fig_prefix = f"figures[{fig_idx}]"
        if not isinstance(figure, dict):
            errors.append(f"{fig_prefix} must be an object")
            continue

        for key in REQUIRED_FIGURE:
            if key not in figure:
                errors.append(f"{fig_prefix}: missing key {key}")

        figure_id = figure.get("figure_id")
        if not is_nonempty_string(figure_id):
            errors.append(f"{fig_prefix}.figure_id must be a non-empty string")
            figure_id = fig_prefix
        else:
            figure_id = figure_id.strip()
            if figure_id in seen_figures:
                errors.append(f"duplicate figure_id: {figure_id}")
            seen_figures.add(figure_id)

        for key in ("title", "result_question", "claim"):
            if not is_nonempty_string(figure.get(key)):
                errors.append(f"{figure_id}.{key} must be a non-empty string")

        panels = figure.get("panels")
        panel_labels: set[str] = set()
        hero_panels: list[str] = []
        if not isinstance(panels, list) or not panels:
            errors.append(f"{figure_id}.panels must be a non-empty array")
        else:
            for panel_idx, panel in enumerate(panels, start=1):
                prefix = f"{figure_id}.panels[{panel_idx}]"
                if not isinstance(panel, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for key in REQUIRED_PANEL:
                    if key not in panel:
                        errors.append(f"{prefix}: missing key {key}")

                label = panel.get("label")
                if not is_nonempty_string(label):
                    errors.append(f"{prefix}.label must be a non-empty string")
                    label = f"panel-{panel_idx}"
                else:
                    label = label.strip()
                    if label in panel_labels:
                        errors.append(f"{figure_id}: duplicate panel label {label}")
                    panel_labels.add(label)

                experiment = panel.get("experiment")
                if not is_nonempty_string(experiment) or not EXPERIMENT_RE.fullmatch(str(experiment)):
                    errors.append(f"{prefix}.experiment must be a stable lowercase experiment slug")

                tier = panel.get("evidence_tier")
                if tier not in EVIDENCE_TIERS:
                    errors.append(f"{prefix}.evidence_tier must be one of {sorted(EVIDENCE_TIERS)}")
                elif tier == "hero":
                    hero_panels.append(label)

                for key in ("plot_type", "input", "evidence", "statistical_message", "output"):
                    if not is_nonempty_string(panel.get(key)):
                        errors.append(f"{prefix}.{key} must be a non-empty string")

                raw_input = panel.get("input")
                if is_nonempty_string(raw_input) and not resolve_path(project_root, raw_input).exists():
                    message = f"{prefix}.input missing on disk: {raw_input}"
                    (errors if require_inputs else warnings).append(message)

                raw_output = panel.get("output")
                if is_nonempty_string(raw_output):
                    expected = f"figures/experiments/{experiment}/panels/"
                    if is_nonempty_string(experiment) and expected not in Path(raw_output).as_posix():
                        errors.append(f"{prefix}.output must be under {expected}")
                    if require_panel_outputs and not resolve_path(project_root, raw_output).exists():
                        errors.append(f"{prefix}.output image missing on disk: {raw_output}")

        contract = figure.get("contract")
        if not isinstance(contract, dict):
            errors.append(f"{figure_id}.contract must be an object")
        else:
            for key in REQUIRED_CONTRACT:
                if key not in contract:
                    errors.append(f"{figure_id}.contract: missing key {key}")
            if not is_nonempty_string(contract.get("core_conclusion")):
                errors.append(f"{figure_id}.contract.core_conclusion must be a non-empty string")
            archetype = contract.get("archetype")
            if archetype not in ARCHETYPES:
                errors.append(f"{figure_id}.contract.archetype must be one of {sorted(ARCHETYPES)}")
            risks = contract.get("reviewer_risks")
            if not isinstance(risks, list) or not risks or not all(is_nonempty_string(item) for item in risks):
                errors.append(f"{figure_id}.contract.reviewer_risks must be a non-empty string array")

            hierarchy = contract.get("evidence_hierarchy")
            if not isinstance(hierarchy, dict):
                errors.append(f"{figure_id}.contract.evidence_hierarchy must be an object")
            else:
                for key in REQUIRED_HIERARCHY:
                    if key not in hierarchy:
                        errors.append(f"{figure_id}.contract.evidence_hierarchy: missing key {key}")
                hero = hierarchy.get("hero_panel")
                if archetype == "quantitative_grid" and hero is None:
                    if hero_panels:
                        errors.append(f"{figure_id}: hero_panel is null but a panel uses evidence_tier hero")
                else:
                    if not is_nonempty_string(hero) or hero not in panel_labels:
                        errors.append(f"{figure_id}.contract.evidence_hierarchy.hero_panel must name a real panel")
                    if len(hero_panels) != 1:
                        errors.append(f"{figure_id} must contain exactly one panel with evidence_tier hero")
                    elif is_nonempty_string(hero) and hero != hero_panels[0]:
                        errors.append(f"{figure_id}: hierarchy hero_panel must match the panel with evidence_tier hero")
                if len(hero_panels) > 1:
                    errors.append(f"{figure_id} cannot contain more than one panel with evidence_tier hero")
                tier_labels: list[str] = []
                for key in ("primary_evidence", "validation_evidence", "controls_robustness"):
                    tier_labels.extend(
                        validate_label_array(hierarchy.get(key), f"{figure_id}.contract.evidence_hierarchy.{key}", errors)
                    )
                if len(tier_labels) != len(set(tier_labels)):
                    errors.append(f"{figure_id}.contract.evidence_hierarchy assigns a panel to multiple non-hero tiers")
                unknown = sorted(set(tier_labels) - panel_labels)
                if unknown:
                    errors.append(f"{figure_id}.contract.evidence_hierarchy has unknown labels: {', '.join(unknown)}")
                if is_nonempty_string(hero) and hero in tier_labels:
                    errors.append(f"{figure_id}.contract.evidence_hierarchy.hero_panel must not be repeated in another tier")

        validate_layout(
            figure_id,
            figure.get("layout"),
            panel_labels,
            project_root,
            require_figure_source,
            require_publication_outputs,
            errors,
        )

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path, help="Path to figure_blueprint.json")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Base directory for relative file paths")
    parser.add_argument("--allow-missing-inputs", action="store_true", help="Warn instead of failing when panel inputs are absent")
    parser.add_argument("--require-panel-outputs", action="store_true", help="Require every experiment-scoped panel output")
    parser.add_argument("--require-figure-source", action="store_true", help="Require each complete figure source file")
    parser.add_argument(
        "--require-publication-outputs",
        action="store_true",
        help="Require preview PNG, SVG, PDF, TIFF, and QA JSON outputs",
    )
    args = parser.parse_args()

    try:
        data = load_json(args.json_file)
        errors = validate(
            data,
            args.project_root.resolve(),
            not args.allow_missing_inputs,
            args.require_panel_outputs,
            args.require_figure_source,
            args.require_publication_outputs,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"valid: {args.json_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
