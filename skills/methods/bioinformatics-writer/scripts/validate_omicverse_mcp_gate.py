#!/usr/bin/env python3
"""Reject Stage 3 execution until the OmicVerse backend choice is recorded."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VALID_SELECTIONS = {"install_and_enable", "use_existing_backend", "cancel"}
VALID_STATUSES = {"ready", "declined", "failed"}


def fail(message: str, code: int = 1) -> None:
    print(f"OMICVERSE_MCP_GATE: {message}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True, type=Path)
    args = parser.parse_args()

    if not args.status.is_file():
        fail(f"missing required status receipt: {args.status}")
    try:
        receipt = json.loads(args.status.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"invalid status receipt: {exc}")

    selection = receipt.get("selection")
    status = receipt.get("status")
    source = receipt.get("selection_source")
    if selection not in VALID_SELECTIONS:
        fail("selection must be install_and_enable, use_existing_backend, or cancel")
    if source not in {"ask_user", "direct_chat", "existing_runtime"}:
        fail("selection_source must be ask_user, direct_chat, or existing_runtime")
    if selection == "cancel":
        fail("user cancelled this analysis; do not enter Stage 3", code=2)
    if status not in VALID_STATUSES:
        fail("status must be ready, declined, or failed")
    if selection == "install_and_enable" and status == "declined":
        fail("install selection cannot have declined status")
    if source == "existing_runtime" and (selection != "install_and_enable" or status != "ready"):
        fail("existing_runtime requires install_and_enable selection and ready status")
    if selection == "use_existing_backend" and status != "declined":
        fail("existing-backend selection must have declined status")
    print(f"OMICVERSE_MCP_GATE: pass ({selection}, {status})")


if __name__ == "__main__":
    main()
