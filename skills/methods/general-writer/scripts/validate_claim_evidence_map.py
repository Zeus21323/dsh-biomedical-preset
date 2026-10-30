#!/usr/bin/env python3
"""Validate a General Writer claim_evidence_map.json file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


STUDY_TYPES = {
    "experimental", "computational", "observational", "empirical", "qualitative",
    "mixed_methods", "review", "theoretical", "methods", "case_study",
}
EVIDENCE_TYPES = {
    "data", "analysis", "experiment", "qualitative", "literature", "artifact",
    "theory", "mixed",
}
VERIFICATION_STATUSES = {"verified", "limited", "inconsistent", "unsupported"}
PRIMARY_EVIDENCE = {"data", "analysis", "experiment", "qualitative", "artifact", "mixed"}
REQUIRED_TOP = ("paper_goal", "study_type", "research_questions")
REQUIRED_RQ = ("id", "question", "answer_scope", "claims")
REQUIRED_CLAIM = (
    "id", "text", "evidence_type", "verification_status", "source_files", "locator",
    "allowed_wording", "caveats", "section",
)


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_json(path: Path) -> dict:
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


def resolve_path(project_root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else project_root / path


def validate(
    data: dict, project_root: Path, require_sources: bool = True
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_TOP:
        if key not in data:
            errors.append(f"missing top-level key: {key}")
    if not nonempty_string(data.get("paper_goal")):
        errors.append("paper_goal must be a non-empty string")

    study_type = data.get("study_type")
    if study_type not in STUDY_TYPES:
        errors.append(f"study_type must be one of: {', '.join(sorted(STUDY_TYPES))}")

    profiles = data.get("discipline_profiles", [])
    if not isinstance(profiles, list) or not all(nonempty_string(x) for x in profiles):
        errors.append("discipline_profiles must be an array of non-empty strings")

    rqs = data.get("research_questions")
    if not isinstance(rqs, list) or not rqs:
        errors.append("research_questions must be a non-empty array")
        return errors, warnings

    seen_rqs: set[str] = set()
    seen_claims: set[str] = set()
    evidence_seen: set[str] = set()

    for rq_index, rq in enumerate(rqs, start=1):
        prefix = f"research_questions[{rq_index}]"
        if not isinstance(rq, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in REQUIRED_RQ:
            if key not in rq:
                errors.append(f"{prefix}: missing key {key}")
        for key in ("id", "question", "answer_scope"):
            if not nonempty_string(rq.get(key)):
                errors.append(f"{prefix}.{key} must be a non-empty string")

        rq_id = rq.get("id")
        if nonempty_string(rq_id):
            if rq_id in seen_rqs:
                errors.append(f"duplicate research-question id: {rq_id}")
            seen_rqs.add(rq_id)

        claims = rq.get("claims")
        if not isinstance(claims, list) or not claims:
            errors.append(f"{prefix}.claims must be a non-empty array")
            continue

        for claim_index, claim in enumerate(claims, start=1):
            cprefix = f"{prefix}.claims[{claim_index}]"
            if not isinstance(claim, dict):
                errors.append(f"{cprefix} must be an object")
                continue
            for key in REQUIRED_CLAIM:
                if key not in claim:
                    errors.append(f"{cprefix}: missing key {key}")
            for key in ("id", "text", "locator", "allowed_wording", "section"):
                if not nonempty_string(claim.get(key)):
                    errors.append(f"{cprefix}.{key} must be a non-empty string")

            claim_id = claim.get("id")
            if nonempty_string(claim_id):
                if claim_id in seen_claims:
                    errors.append(f"duplicate claim id: {claim_id}")
                seen_claims.add(claim_id)

            evidence_type = claim.get("evidence_type")
            if evidence_type not in EVIDENCE_TYPES:
                errors.append(
                    f"{cprefix}.evidence_type must be one of: {', '.join(sorted(EVIDENCE_TYPES))}"
                )
            else:
                evidence_seen.add(evidence_type)

            status = claim.get("verification_status")
            if status not in VERIFICATION_STATUSES:
                errors.append(
                    f"{cprefix}.verification_status must be one of: "
                    f"{', '.join(sorted(VERIFICATION_STATUSES))}"
                )
            elif status == "unsupported":
                errors.append(f"{cprefix} is unsupported and cannot enter polished delivery")
            elif status in {"limited", "inconsistent"}:
                warnings.append(f"{cprefix} has verification_status={status}; preserve caveats")

            sources = claim.get("source_files")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{cprefix}.source_files must be a non-empty array")
            elif not all(nonempty_string(item) for item in sources):
                errors.append(f"{cprefix}.source_files must contain only non-empty strings")
            else:
                for raw in sources:
                    candidate = resolve_path(project_root, raw)
                    if not candidate.exists():
                        message = f"{cprefix}.source_files missing on disk: {raw}"
                        (errors if require_sources else warnings).append(message)

            for key in ("statistics", "prohibited_wording", "caveats"):
                values = claim.get(key, [])
                if not isinstance(values, list) or not all(nonempty_string(x) for x in values):
                    errors.append(f"{cprefix}.{key} must be an array of non-empty strings")

            target = claim.get("table_or_figure")
            if target is not None and not nonempty_string(target):
                errors.append(f"{cprefix}.table_or_figure must be null or a non-empty string")

    if study_type in {
        "experimental", "computational", "observational", "empirical", "qualitative",
        "mixed_methods", "methods", "case_study",
    } and not (evidence_seen & PRIMARY_EVIDENCE):
        errors.append(f"study_type={study_type} requires at least one primary-evidence claim")
    if study_type == "review" and "literature" not in evidence_seen:
        errors.append("study_type=review requires at least one literature claim")
    if study_type == "theoretical" and not (evidence_seen & {"theory", "artifact", "mixed"}):
        errors.append("study_type=theoretical requires theory, artifact, or mixed evidence")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--allow-missing-source-files", action="store_true",
        help="warn instead of failing when a source file does not exist",
    )
    args = parser.parse_args()

    try:
        data = load_json(args.json_file)
        errors, warnings = validate(
            data, args.project_root.resolve(),
            require_sources=not args.allow_missing_source_files,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"valid: {args.json_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

