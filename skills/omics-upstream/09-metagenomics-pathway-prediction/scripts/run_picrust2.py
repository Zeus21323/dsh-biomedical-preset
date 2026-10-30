#!/usr/bin/env python3
"""Run an installed PICRUSt2 pipeline and record the exact invocation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequences", required=True, type=Path)
    parser.add_argument("--table", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--executable", default="picrust2_pipeline.py")
    parser.add_argument("--stratified", action="store_true")
    parser.add_argument("--per-sequence-contrib", action="store_true")
    args, extra = parser.parse_known_args()

    executable = shutil.which(args.executable)
    if executable is None:
        parser.error(f"PICRUSt2 executable not found: {args.executable}")
    if not args.sequences.is_file() or not args.table.is_file():
        parser.error("sequence FASTA and feature table must exist")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error(f"output directory must be new or empty: {args.output_dir}")
    if args.threads < 1:
        parser.error("--threads must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    command = [executable, "-s", str(args.sequences), "-i", str(args.table), "-o", str(args.output_dir), "-p", str(args.threads)]
    if args.stratified:
        command.append("--stratified")
    if args.per_sequence_contrib:
        command.append("--per_sequence_contrib")
    command.extend(extra)

    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
    metadata = {
        "status": "completed" if result.returncode == 0 else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "sequences": {"path": str(args.sequences.resolve()), "sha256": sha256(args.sequences)},
            "table": {"path": str(args.table.resolve()), "sha256": sha256(args.table)},
        },
        "output_dir": str(args.output_dir.resolve()),
        "command": command,
        "tool_version": (version.stdout or version.stderr).strip(),
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-4000:],
    }
    (args.output_dir / "picrust2_run.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
