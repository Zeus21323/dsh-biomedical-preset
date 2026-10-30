#!/usr/bin/env python3
"""Run an installed BGC-Prophet CLI with explicit inputs and provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWYBXZJUO*")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_protein_fasta(path: Path) -> tuple[int, int]:
    records = 0
    residues = 0
    sequence: list[str] = []

    def check_current() -> None:
        nonlocal residues
        joined = "".join(sequence).upper()
        if not joined:
            raise ValueError(f"empty FASTA record in {path}")
        invalid = set(joined) - AMINO_ACIDS
        if invalid:
            raise ValueError(f"unsupported residues in {path}: {sorted(invalid)}")
        if len(joined) >= 20 and sum(base in "ACGTN" for base in joined) / len(joined) > 0.9:
            raise ValueError(f"input appears to be nucleotide rather than protein FASTA: {path}")
        residues += len(joined)

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if records:
                    check_current()
                records += 1
                sequence = []
            else:
                if records == 0:
                    raise ValueError(f"sequence found before FASTA header: {path}")
                sequence.append(line)
    if records:
        check_current()
    else:
        raise ValueError(f"no FASTA records found: {path}")
    return records, residues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genomes-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--annotator", required=True, type=Path)
    parser.add_argument("--classifier", type=Path)
    parser.add_argument("--executable", default="bgc_prophet")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--classifier-threshold", type=float, default=0.5)
    parser.add_argument("--max-gap", type=int, default=3)
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--name", default="bgc_prophet_run")
    args = parser.parse_args()

    executable = shutil.which(args.executable)
    if executable is None:
        parser.error(f"BGC-Prophet executable not found: {args.executable}")
    if not args.genomes_dir.is_dir():
        parser.error(f"genomes directory not found: {args.genomes_dir}")
    if not args.annotator.is_file():
        parser.error(f"annotator checkpoint not found: {args.annotator}")
    if args.classifier and not args.classifier.is_file():
        parser.error(f"classifier checkpoint not found: {args.classifier}")
    if not 0 < args.threshold < 1 or not 0 < args.classifier_threshold < 1:
        parser.error("thresholds must be between 0 and 1")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error(f"output directory must be new or empty: {args.output_dir}")

    fasta_files = sorted(
        path for path in args.genomes_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".fa", ".faa", ".fasta"}
    )
    if not fasta_files:
        parser.error("no protein FASTA files found")
    input_manifest = []
    for path in fasta_files:
        records, residues = validate_protein_fasta(path)
        input_manifest.append({"path": str(path.resolve()), "sha256": sha256(path), "records": records, "residues": residues})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable, "pipeline",
        "--genomesDir", str(args.genomes_dir),
        "--modelPath", str(args.annotator),
        "--saveIntermediate",
        "--name", args.name,
        "--threshold", str(args.threshold),
        "--max_gap", str(args.max_gap),
        "--min_count", str(args.min_count),
        "--outputPath", str(args.output_dir),
    ]
    if args.classifier:
        command.extend(["--classifierPath", str(args.classifier), "--classify_t", str(args.classifier_threshold)])

    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
    metadata = {
        "status": "completed" if result.returncode == 0 else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "inputs": input_manifest,
        "checkpoints": {
            "annotator": {"path": str(args.annotator.resolve()), "sha256": sha256(args.annotator)},
            "classifier": {"path": str(args.classifier.resolve()), "sha256": sha256(args.classifier)} if args.classifier else None,
        },
        "parameters": {"threshold": args.threshold, "classifier_threshold": args.classifier_threshold, "max_gap": args.max_gap, "min_count": args.min_count, "name": args.name},
        "command": command,
        "tool_version": (version.stdout or version.stderr).strip(),
        "python": platform.python_version(),
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-4000:],
    }
    (args.output_dir / "bgc_prophet_run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
