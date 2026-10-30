#!/usr/bin/env python3
"""Run one MGM CLI operation with explicit paths and a run record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
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


def path_record(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    if path.is_file():
        return {"path": str(path.resolve()), "type": "file", "sha256": sha256(path), "size": path.stat().st_size}
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    total_size = 0
    for item in files:
        relative = item.relative_to(path).as_posix()
        item_size = item.stat().st_size
        total_size += item_size
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(item).encode("ascii"))
        digest.update(b"\0")
    return {
        "path": str(path.resolve()),
        "type": "directory",
        "manifest_sha256": digest.hexdigest(),
        "files": len(files),
        "size": total_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["construct", "pretrain", "train", "finetune", "predict", "generate", "reconstruct"])
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--executable", default="mgm")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--forward-seed", action="store_true", help="Pass --seed to MGM after confirming the installed CLI supports it")
    parser.add_argument("--metadata", type=Path)
    args, extra = parser.parse_known_args()

    executable = shutil.which(args.executable)
    if executable is None:
        parser.error(f"MGM executable not found: {args.executable}")
    if not args.input.is_file():
        parser.error(f"input not found: {args.input}")
    for label, path in (("model", args.model), ("labels", args.labels)):
        if path is not None and not path.exists():
            parser.error(f"{label} not found: {path}")
    if args.mode in {"finetune", "predict", "generate", "reconstruct"} and args.model is None:
        parser.error(f"--model is required for {args.mode}")
    if args.mode in {"train", "finetune", "predict"} and args.labels is None:
        parser.error(f"--labels is required for {args.mode}")
    if args.mode in {"pretrain", "train", "finetune", "generate"} and not args.forward_seed:
        parser.error(f"{args.mode} is stochastic; confirm the installed MGM seed interface and add --forward-seed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, args.mode, "-i", str(args.input), "-o", str(args.output)]
    if args.model:
        command.extend(["-m", str(args.model)])
    if args.labels:
        command.extend(["-l", str(args.labels)])
    if args.forward_seed:
        command.extend(["--seed", str(args.seed)])
    command.extend(extra)

    started = datetime.now(timezone.utc).isoformat()
    environment = os.environ.copy()
    environment.update(
        PYTHONHASHSEED=str(args.seed),
        PL_GLOBAL_SEED=str(args.seed),
        CUBLAS_WORKSPACE_CONFIG=":4096:8",
    )
    result = subprocess.run(command, text=True, capture_output=True, check=False, env=environment)
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
    metadata_path = args.metadata or args.output.with_name(args.output.name + ".mgm_run.json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "status": "completed" if result.returncode == 0 else "failed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "input": path_record(args.input),
        "model": path_record(args.model),
        "labels": path_record(args.labels),
        "output": str(args.output.resolve()),
        "command": command,
        "seed": {"value": args.seed, "forwarded_to_cli": args.forward_seed, "environment": ["PYTHONHASHSEED", "PL_GLOBAL_SEED", "CUBLAS_WORKSPACE_CONFIG"]},
        "tool_version": (version.stdout or version.stderr).strip(),
        "python": platform.python_version(),
        "returncode": result.returncode,
        "stderr_tail": result.stderr[-4000:],
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
