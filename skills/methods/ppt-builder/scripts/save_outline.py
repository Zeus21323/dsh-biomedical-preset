#!/usr/bin/env python3
"""Save a generated PPT markdown outline in the workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_outline(input_path: str) -> str:
    raw = sys.stdin.read() if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
    outline = raw.strip()
    if not outline:
        raise ValueError("outline markdown must not be empty")
    return outline + "\n"


def save_outline(workspace_output_dir: str, outline: str) -> Path:
    output_dir = Path(workspace_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outline_path = output_dir / "outline.md"
    temporary_path = output_dir / ".outline.md.tmp"
    temporary_path.write_text(outline, encoding="utf-8")
    temporary_path.replace(outline_path)
    return outline_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-output-dir",
        required=True,
        help="Workspace output directory that will contain outline.md.",
    )
    parser.add_argument(
        "--input",
        default="-",
        help="Markdown outline file, or - to read UTF-8 markdown from stdin.",
    )
    args = parser.parse_args()

    try:
        outline_path = save_outline(
            args.workspace_output_dir,
            read_outline(args.input),
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {"ok": True, "outline_path": str(outline_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
