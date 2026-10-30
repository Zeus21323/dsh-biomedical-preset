#!/usr/bin/env python3
"""Validate a full-manuscript approval receipt against the current plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


APPROVAL_METHODS = {"request_user_input", "ask_user", "direct_chat_fallback"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def validate_approval(plan_path: Path, approval_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    plan = read_json(plan_path)
    receipt = read_json(approval_path)

    if plan.get("status") != "approved":
        errors.append("manuscript plan status must be approved")
    if receipt.get("approval_scope") != "full_manuscript_plan":
        errors.append("approval_scope must be full_manuscript_plan")
    if receipt.get("approval_decision") != "approved":
        errors.append("approval_decision must be approved")
    if receipt.get("approved_in_current_conversation") is not True:
        errors.append("approved_in_current_conversation must be true")

    approval_text = receipt.get("approval_text")
    if not isinstance(approval_text, str) or not approval_text.strip():
        errors.append("approval_text must contain the exact non-empty user response")

    method = receipt.get("approval_method")
    if method not in APPROVAL_METHODS:
        errors.append(
            f"approval_method must be one of: {', '.join(sorted(APPROVAL_METHODS))}"
        )
    elif method == "direct_chat_fallback":
        warnings.append(
            "direct_chat_fallback is valid only when request_user_input and ask_user were unavailable"
        )

    recorded_sha = receipt.get("plan_sha256")
    if not isinstance(recorded_sha, str) or not SHA256_RE.fullmatch(recorded_sha):
        errors.append("plan_sha256 must be 64 lowercase hexadecimal characters")
    else:
        actual_sha = file_sha256(plan_path)
        if recorded_sha != actual_sha:
            errors.append(
                f"plan_sha256 mismatch: receipt={recorded_sha}, current={actual_sha}"
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    args = parser.parse_args()

    try:
        errors, warnings = validate_approval(args.plan.resolve(), args.approval.resolve())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"valid approval: {args.approval}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
