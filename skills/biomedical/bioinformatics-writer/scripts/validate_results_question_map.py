#!/usr/bin/env python3
"""Validate a Bioinformatics Writer results_question_map.json file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP = ("study_goal", "results_questions")
REQUIRED_RQ = ("id", "question", "claim", "source_analysis", "source_files", "figure")


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


def validate(data: dict, project_root: Path, require_source_files: bool) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"missing top-level key: {key}")

    if not is_nonempty_string(data.get("study_goal")):
        errors.append("study_goal must be a non-empty string")

    questions = data.get("results_questions")
    if not isinstance(questions, list) or not questions:
        errors.append("results_questions must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    seen_figures: set[str] = set()

    for idx, rq in enumerate(questions, start=1):
        prefix = f"results_questions[{idx}]"
        if not isinstance(rq, dict):
            errors.append(f"{prefix} must be an object")
            continue

        for key in REQUIRED_RQ:
            if key not in rq:
                errors.append(f"{prefix}: missing key {key}")

        rq_id = rq.get("id")
        if not is_nonempty_string(rq_id):
            errors.append(f"{prefix}.id must be a non-empty string")
        elif rq_id in seen_ids:
            errors.append(f"duplicate Results question id: {rq_id}")
        else:
            seen_ids.add(rq_id)

        figure = rq.get("figure")
        if not is_nonempty_string(figure):
            errors.append(f"{prefix}.figure must be a non-empty string")
        elif figure in seen_figures:
            errors.append(f"duplicate figure assignment: {figure}")
        else:
            seen_figures.add(figure)

        for key in ("question", "claim"):
            if not is_nonempty_string(rq.get(key)):
                errors.append(f"{prefix}.{key} must be a non-empty string")

        for key in ("source_analysis", "source_files"):
            value = rq.get(key)
            if not isinstance(value, list) or not value:
                errors.append(f"{prefix}.{key} must be a non-empty array")
            elif not all(is_nonempty_string(item) for item in value):
                errors.append(f"{prefix}.{key} must contain only non-empty strings")

        for raw in rq.get("source_files", []) if isinstance(rq.get("source_files"), list) else []:
            candidate = resolve_path(project_root, raw)
            if not candidate.exists():
                msg = f"{prefix}.source_files missing on disk: {raw}"
                if require_source_files:
                    errors.append(msg)
                else:
                    warnings.append(msg)

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path, help="Path to results_question_map.json")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Base directory for relative source_files")
    parser.add_argument("--allow-missing-source-files", action="store_true", help="Warn instead of failing when source_files do not exist")
    args = parser.parse_args()

    try:
        data = load_json(args.json_file)
        errors = validate(data, args.project_root.resolve(), not args.allow_missing_source_files)
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

