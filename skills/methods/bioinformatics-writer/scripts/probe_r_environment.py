#!/usr/bin/env python3
"""Discover and inspect a reusable local R/RStudio-compatible environment."""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


R_PROBE = r'''
args <- commandArgs(trailingOnly=TRUE)
cat("R_VERSION\t", R.version.string, "\n", sep="")
cat("R_HOME\t", R.home(), "\n", sep="")
for (p in .libPaths()) cat("LIB_PATH\t", p, "\n", sep="")
for (pkg in args) {
  ok <- requireNamespace(pkg, quietly=TRUE)
  version <- if (ok) as.character(utils::packageVersion(pkg)) else ""
  cat("PACKAGE\t", pkg, "\t", if (ok) "true" else "false", "\t", version, "\n", sep="")
}
'''


def candidate_rscripts(explicit: str | None) -> list[str]:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    found = shutil.which("Rscript")
    if found:
        candidates.append(found)
    r_home = os.environ.get("R_HOME")
    if r_home:
        candidates.extend([str(Path(r_home) / "bin" / "Rscript"), str(Path(r_home) / "bin" / "Rscript.exe")])
    patterns = [
        "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        "/usr/local/bin/Rscript",
        "/usr/bin/Rscript",
        "/opt/homebrew/bin/Rscript",
        str(Path.home() / "miniconda3" / "envs" / "*" / "bin" / "Rscript"),
        str(Path.home() / "anaconda3" / "envs" / "*" / "bin" / "Rscript"),
        r"C:\Program Files\R\R-*\bin\Rscript.exe",
        r"C:\Program Files\R\R-*\bin\x64\Rscript.exe",
        str(Path.home() / "AppData" / "Local" / "Programs" / "R" / "R-*" / "bin" / "Rscript.exe"),
    ]
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))
    unique: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        path = str(Path(raw).expanduser())
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen and Path(path).is_file():
            seen.add(key)
            unique.append(path)
    return unique


def inspect_rscript(path: str, packages: list[str], timeout: int) -> dict:
    command = [path, "--vanilla", "-e", R_PROBE, *packages]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"rscript": path, "usable": False, "error": str(exc)}
    record: dict = {
        "rscript": path,
        "usable": completed.returncode == 0,
        "returncode": completed.returncode,
        "r_version": "",
        "r_home": "",
        "library_paths": [],
        "packages": {},
    }
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        if parts[0] == "R_VERSION" and len(parts) >= 2:
            record["r_version"] = parts[1]
        elif parts[0] == "R_HOME" and len(parts) >= 2:
            record["r_home"] = parts[1]
        elif parts[0] == "LIB_PATH" and len(parts) >= 2:
            record["library_paths"].append(parts[1])
        elif parts[0] == "PACKAGE" and len(parts) >= 4:
            record["packages"][parts[1]] = {
                "available": parts[2].lower() == "true",
                "version": parts[3],
            }
    if completed.stderr.strip():
        record["stderr"] = completed.stderr.strip()[-4000:]
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", action="append", default=[], dest="packages")
    parser.add_argument("--rscript", help="Explicit Rscript path to check first")
    parser.add_argument("--output", default="environment/r_environment.json")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    packages = list(dict.fromkeys(item.strip() for item in args.packages if item.strip()))
    candidates = candidate_rscripts(args.rscript)
    inspected = [inspect_rscript(item, packages, args.timeout) for item in candidates]
    usable = [item for item in inspected if item.get("usable")]
    selected = usable[0] if usable else None
    missing = []
    if selected:
        missing = [
            package for package in packages
            if not selected.get("packages", {}).get(package, {}).get("available", False)
        ]
    report = {
        "execution_host_only": True,
        "r_found": bool(usable),
        "selected_rscript": selected.get("rscript") if selected else None,
        "r_version": selected.get("r_version") if selected else None,
        "r_home": selected.get("r_home") if selected else None,
        "library_paths": selected.get("library_paths", []) if selected else [],
        "required_packages": packages,
        "packages": selected.get("packages", {}) if selected else {},
        "missing_packages": missing if selected else packages,
        "r_ready_for_requested_modules": bool(selected) and not missing,
        "candidates": inspected,
    }
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
