#!/usr/bin/env python3
"""Create and validate an analysis approval receipt deterministically."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from validate_analysis_approval import (
    find_prd_status,
    resolve,
    sha256,
    validate_approval,
)


def atomic_write_text(path: Path, text: str) -> None:
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
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def set_prd_approved(prd_text: str) -> str:
    status, index, kind = find_prd_status(prd_text)
    if status == "approved":
        return prd_text

    lines = prd_text.splitlines()
    if index is None:
        suffix = "" if not prd_text or prd_text.endswith("\n") else "\n"
        return f"{prd_text}{suffix}\nStatus: approved\n"

    if kind == "table":
        raw = lines[index]
        leading = raw[: len(raw) - len(raw.lstrip())]
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        cells[1] = "approved"
        lines[index] = leading + "| " + " | ".join(cells) + " |"
    else:
        leading = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
        lines[index] = f"{leading}Status: approved"

    ending = "\n" if prd_text.endswith("\n") else ""
    return "\n".join(lines) + ending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--analysis-prd", required=True)
    parser.add_argument("--analysis-inventory", required=True)
    parser.add_argument("--approval-receipt", required=True)
    parser.add_argument(
        "--approval-source",
        required=True,
        choices=("ask_user", "direct_chat"),
    )
    parser.add_argument("--user-approval-text", required=True)
    args = parser.parse_args()

    user_text = args.user_approval_text.strip()
    if not user_text:
        parser.error("--user-approval-text must be non-empty")

    root = Path(args.project_root).expanduser().resolve()
    prd_path = resolve(root, args.analysis_prd)
    inventory_path = resolve(root, args.analysis_inventory)
    receipt_path = resolve(root, args.approval_receipt)

    try:
        prd_text = prd_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        parser.error(f"analysis PRD not found: {prd_path}")
        raise AssertionError from exc

    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        parser.error(f"analysis inventory not found: {inventory_path}")
        raise AssertionError from exc
    except json.JSONDecodeError as exc:
        parser.error(
            f"analysis inventory is invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
        raise AssertionError from exc
    if not isinstance(inventory, (dict, list)):
        parser.error("analysis inventory JSON root must be an object or array")

    approved_prd = set_prd_approved(prd_text)
    if approved_prd != prd_text:
        atomic_write_text(prd_path, approved_prd)

    receipt = {
        "approval_choice": "approved",
        "approval_source": args.approval_source,
        "approved_in_current_conversation": True,
        "user_approval_text": user_text,
        "approved_prd_sha256": sha256(prd_path),
        "approved_inventory_sha256": sha256(inventory_path),
    }
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
    )

    errors = validate_approval(
        root,
        args.analysis_prd,
        args.analysis_inventory,
        args.approval_receipt,
    )
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1

    print(f"ANALYSIS_APPROVAL CREATED {receipt_path}")
    print("ANALYSIS_APPROVAL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
