#!/usr/bin/env python3
"""Snapshot JSON key paths and types before a manuscript script consumes them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def merge_types(values: list[Any]) -> list[str]:
    return sorted({json_type(value) for value in values})


def describe(value: Any, max_depth: int, array_samples: int, depth: int = 0) -> dict:
    record: dict[str, Any] = {"type": json_type(value)}
    if depth >= max_depth:
        record["truncated"] = isinstance(value, (dict, list))
        return record

    if isinstance(value, dict):
        record["keys"] = {
            key: describe(item, max_depth, array_samples, depth + 1)
            for key, item in sorted(value.items())
        }
    elif isinstance(value, list):
        record["length"] = len(value)
        sampled = value[:array_samples]
        record["sampled_item_types"] = merge_types(sampled)
        if sampled:
            if all(isinstance(item, dict) for item in sampled):
                union: dict[str, list[Any]] = {}
                for item in sampled:
                    for key, child in item.items():
                        union.setdefault(key, []).append(child)
                record["item_keys"] = {
                    key: {
                        "observed_types": merge_types(children),
                        "schema": describe(
                            children[0], max_depth, array_samples, depth + 1
                        ),
                    }
                    for key, children in sorted(union.items())
                }
            else:
                record["sample_item_schemas"] = [
                    describe(item, max_depth, array_samples, depth + 1)
                    for item in sampled
                ]
    return record


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, dest="inputs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--array-samples", type=int, default=5)
    args = parser.parse_args()
    if args.max_depth < 1 or args.array_samples < 1:
        parser.error("max-depth and array-samples must be positive")

    files: list[dict[str, Any]] = []
    for raw in args.inputs:
        path = Path(raw).expanduser().resolve()
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            parser.error(f"input not found: {path}")
        try:
            data = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            parser.error(f"invalid JSON input {path}: {exc}")
        files.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(content).hexdigest(),
                "schema": describe(data, args.max_depth, args.array_samples),
            }
        )

    output = Path(args.output).expanduser()
    atomic_write_json(
        output,
        {
            "files": files,
            "contains_values": False,
            "max_depth": args.max_depth,
            "array_samples": args.array_samples,
        },
    )
    print(f"JSON_SCHEMA_SNAPSHOT OK files={len(files)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
