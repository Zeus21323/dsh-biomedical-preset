#!/usr/bin/env python3
"""Install a user-local OmicVerse MCP runtime and emit its server descriptor."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def create_venv(runtime: Path) -> None:
    """Create a venv whose interpreter remains able to resolve libpython on macOS."""
    venv.EnvBuilder(with_pip=True, symlinks=True).create(runtime)


def ensure_runtime(runtime: Path, python: Path) -> None:
    """Create or repair the managed runtime, validating its pip bootstrap."""
    if not python.exists():
        if runtime.exists():
            shutil.rmtree(runtime)
        create_venv(runtime)

    try:
        run([str(python), "-m", "pip", "--version"])
    except subprocess.CalledProcessError:
        # Older runs used copied Python binaries. With the harness's macOS runtime
        # those binaries cannot resolve @rpath/libpython and must be rebuilt.
        if runtime.exists():
            shutil.rmtree(runtime)
        create_venv(runtime)
        run([str(python), "-m", "pip", "--version"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install a per-user OmicVerse MCP environment and write a server descriptor."
    )
    home = Path.home()
    parser.add_argument(
        "--install-root",
        type=Path,
        default=home / ".bioinformatics-writer" / "runtime" / "omicverse",
        help="User-local installation directory.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=home / ".bioinformatics-writer" / "state" / "omicverse",
        help="User-local directory for persisted OmicVerse state.",
    )
    parser.add_argument(
        "--phase",
        default="P0+P0.5+P2",
        help="OmicVerse MCP rollout phase passed to the server.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the descriptor without creating an environment or installing packages.",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 10):
        raise SystemExit("OmicVerse MCP requires Python 3.10 or later.")

    install_root = args.install_root.expanduser().resolve()
    state_dir = args.state_dir.expanduser().resolve()
    runtime = install_root / ".venv"
    python = venv_python(runtime)

    descriptor = {
        "mcpServers": {
            "omicverse": {
                "command": str(python),
                "args": [
                    "-m",
                    "omicverse.mcp",
                    "--phase",
                    args.phase,
                    "--persist-dir",
                    str(state_dir),
                ],
            }
        }
    }
    if args.dry_run:
        print(json.dumps(descriptor, indent=2))
        return

    install_root.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    ensure_runtime(runtime, python)

    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python), "-m", "pip", "install", "--upgrade", "omicverse[mcp]"])
    run([str(python), "-m", "omicverse.mcp", "--help"])

    descriptor_path = install_root / "omicverse_mcp_local.json"
    descriptor_path.write_text(json.dumps(descriptor, indent=2) + "\n", encoding="utf-8")
    print(descriptor_path)


if __name__ == "__main__":
    main()
