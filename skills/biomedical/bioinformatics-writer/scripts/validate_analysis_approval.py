#!/usr/bin/env python3
"""Validate current-conversation approval for an analysis PRD and inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_RECEIPT_KEYS = (
    "approval_choice",
    "approval_source",
    "approved_in_current_conversation",
    "user_approval_text",
    "approved_prd_sha256",
    "approved_inventory_sha256",
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_markdown(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+", "", value)
    value = re.sub(r"^\s*#{1,6}\s*", "", value)
    return (
        value.replace("`", "")
        .replace("*", "")
        .replace("_", "")
        .replace("~", "")
        .strip()
    )


def _is_status_key(value: str) -> bool:
    normalized = _strip_markdown(value).strip().casefold()
    return normalized in {"status", "状态"}


def _normalize_status_value(value: str) -> str:
    normalized = _strip_markdown(value).strip().casefold()
    normalized = normalized.rstrip(".;；。").strip()
    if normalized in {"approved", "批准", "已批准"}:
        return "approved"
    if normalized in {"pending", "待批准", "待审批"}:
        return "pending"
    if normalized in {"revised", "修改中", "已修订"}:
        return "revised"
    return normalized


def find_prd_status(prd_text: str) -> tuple[str | None, int | None, str | None]:
    """Return normalized status, zero-based line index, and line kind."""
    fallback: tuple[str | None, int | None, str | None] = (None, None, None)
    for index, line in enumerate(prd_text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) >= 2 and _is_status_key(cells[0]):
                status = _normalize_status_value(cells[1])
                if status in {"approved", "pending", "revised"}:
                    return status, index, "table"
                if fallback[1] is None:
                    fallback = (status, index, "table")

        plain = _strip_markdown(line)
        match = re.match(r"^(status|状态)\s*[:：]\s*(.*?)\s*$", plain, re.IGNORECASE)
        if match:
            status = _normalize_status_value(match.group(2))
            if status in {"approved", "pending", "revised"}:
                return status, index, "line"
            if fallback[1] is None:
                fallback = (status, index, "line")
    return fallback


def has_approved_status(prd_text: str) -> bool:
    status, _, _ = find_prd_status(prd_text)
    return status == "approved"


def _load_json(path: Path, label: str, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} not found: {path}")
    except json.JSONDecodeError as exc:
        errors.append(
            f"{label} is not valid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        )
    return None


def validate_approval(
    project_root: Path,
    analysis_prd: str,
    analysis_inventory: str,
    approval_receipt: str,
) -> list[str]:
    root = project_root.expanduser().resolve()
    prd_path = resolve(root, analysis_prd)
    inventory_path = resolve(root, analysis_inventory)
    receipt_path = resolve(root, approval_receipt)
    errors: list[str] = []

    try:
        prd_text = prd_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"analysis PRD not found: {prd_path}")
        prd_text = ""
    if prd_text and not has_approved_status(prd_text):
        status, _, _ = find_prd_status(prd_text)
        rendered = status if status is not None else "missing"
        errors.append(
            "analysis PRD status must resolve to approved "
            f"(found: {rendered}); canonical form is 'Status: approved'"
        )

    _load_json(inventory_path, "analysis inventory", errors)
    receipt = _load_json(receipt_path, "analysis approval receipt", errors)
    if receipt is None:
        return errors
    if not isinstance(receipt, dict):
        errors.append("analysis approval receipt root must be a JSON object")
        return errors

    missing = [key for key in REQUIRED_RECEIPT_KEYS if key not in receipt]
    for key in missing:
        errors.append(f"analysis approval receipt missing required key: {key}")

    if "approval_choice" in receipt and receipt["approval_choice"] != "approved":
        errors.append("analysis approval receipt approval_choice must be approved")
    if "approval_source" in receipt and receipt["approval_source"] not in {
        "ask_user",
        "direct_chat",
    }:
        errors.append(
            "analysis approval receipt approval_source must be ask_user or direct_chat"
        )
    if (
        "approved_in_current_conversation" in receipt
        and receipt["approved_in_current_conversation"] is not True
    ):
        errors.append(
            "analysis approval receipt must record "
            "approved_in_current_conversation=true"
        )
    if "user_approval_text" in receipt and not str(
        receipt["user_approval_text"]
    ).strip():
        errors.append("analysis approval receipt user_approval_text must be non-empty")

    hash_checks = (
        ("approved_prd_sha256", prd_path, "PRD"),
        ("approved_inventory_sha256", inventory_path, "inventory"),
    )
    for key, path, label in hash_checks:
        if key not in receipt:
            continue
        value = receipt[key]
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
            errors.append(
                f"analysis approval receipt {key} must be a 64-character SHA-256"
            )
            continue
        if path.is_file() and value.casefold() != sha256(path):
            errors.append(
                f"analysis approval receipt {key} does not match the current "
                f"{label} SHA-256"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--analysis-prd", required=True)
    parser.add_argument("--analysis-inventory", required=True)
    parser.add_argument("--approval-receipt", required=True)
    args = parser.parse_args()

    errors = validate_approval(
        Path(args.project_root),
        args.analysis_prd,
        args.analysis_inventory,
        args.approval_receipt,
    )
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("ANALYSIS_APPROVAL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
