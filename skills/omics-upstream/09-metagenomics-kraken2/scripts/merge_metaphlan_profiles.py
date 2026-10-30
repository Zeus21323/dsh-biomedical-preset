#!/usr/bin/env python3
"""Merge MetaPhlAn profiles by taxon identifier with version checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_profile(path: Path, gtdb: bool) -> tuple[str, dict[str, float]]:
    header_lines: list[str] = []
    data_lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if raw.startswith("#") and not data_lines:
                header_lines.append(raw.rstrip("\n"))
            elif raw.strip():
                data_lines.append(raw)
    if not header_lines:
        raise ValueError(f"MetaPhlAn header missing: {path}")
    if not data_lines:
        raise ValueError(f"profile has no data rows: {path}")

    names = header_lines[-1].lstrip("#").strip().split("\t")
    value_index = 1 if gtdb else 2
    if len(names) <= value_index:
        raise ValueError(f"profile header has too few columns: {path}")
    values: dict[str, float] = {}
    reader = csv.reader(data_lines, delimiter="\t")
    for row in reader:
        if len(row) <= value_index:
            raise ValueError(f"malformed profile row in {path}: {row}")
        taxon = row[0]
        if taxon in values:
            raise ValueError(f"duplicate taxon in {path}: {taxon}")
        values[taxon] = float(row[value_index])
    return header_lines[0], values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--gtdb-profiles", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        parser.error(f"output exists: {args.output}")
    for path in args.inputs:
        if not path.is_file():
            parser.error(f"input not found: {path}")

    sample_names = [path.stem.removesuffix("_profile") for path in args.inputs]
    if len(set(sample_names)) != len(sample_names):
        parser.error("input file names produce duplicate sample IDs")

    versions: set[str] = set()
    profiles: list[dict[str, float]] = []
    for path in args.inputs:
        version, values = read_profile(path, args.gtdb_profiles)
        versions.add(version)
        profiles.append(values)
    if len(versions) != 1:
        parser.error(f"profiles use different MetaPhlAn versions: {sorted(versions)}")

    taxa = sorted(set().union(*(profile.keys() for profile in profiles)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(next(iter(versions)) + "\n")
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["clade_name", *sample_names])
        for taxon in taxa:
            writer.writerow([taxon, *(profile.get(taxon, 0.0) for profile in profiles)])

    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metaphlan_header": next(iter(versions)),
        "inputs": [{"path": str(path.resolve()), "sample_id": sample, "sha256": sha256(path)} for path, sample in zip(args.inputs, sample_names)],
        "output": {"path": str(args.output.resolve()), "sha256": sha256(args.output), "taxa": len(taxa), "samples": len(sample_names)},
        "missing_taxa_filled_with": 0,
    }
    args.output.with_name(args.output.name + ".merge.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
