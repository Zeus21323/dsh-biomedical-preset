#!/usr/bin/env python3
"""Fetch and normalize ClinicalTrials.gov API v2 studies safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


DEFAULT_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
PARTIAL_DATE_RE = re.compile(
    r"^(?P<year>\d{4})(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?$"
)


class ClinicalTrialsAPIError(RuntimeError):
    """Raised when the API request or response contract is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, payload: Any) -> None:
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
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_partial_date(raw: str) -> dict[str, Any]:
    """Parse YYYY, YYYY-MM, or YYYY-MM-DD without inventing precision."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("date must be a non-empty string")
    value = raw.strip()
    match = PARTIAL_DATE_RE.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported date format: {value}")

    year = int(match.group("year"))
    month = int(match.group("month")) if match.group("month") else None
    day = int(match.group("day")) if match.group("day") else None
    if month is not None and not 1 <= month <= 12:
        raise ValueError(f"invalid month in date: {value}")
    if day is not None:
        date(year, month, day)

    precision = "day" if day is not None else "month" if month is not None else "year"
    return {
        "raw": value,
        "year": year,
        "month": month,
        "day": day,
        "precision": precision,
    }


def normalize_date_struct(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return {"raw": value, "precision": "invalid", "type": None, "error": "not an object"}
    raw = value.get("date")
    if raw is None:
        return {
            "raw": None,
            "precision": "invalid",
            "type": value.get("type"),
            "error": "missing date",
        }
    try:
        parsed = parse_partial_date(raw)
    except ValueError as exc:
        return {
            "raw": raw,
            "precision": "invalid",
            "type": value.get("type"),
            "error": str(exc),
        }
    parsed["type"] = value.get("type")
    parsed["error"] = None
    return parsed


def _module(study: dict, name: str) -> dict:
    protocol = study.get("protocolSection")
    if not isinstance(protocol, dict):
        return {}
    value = protocol.get(name)
    return value if isinstance(value, dict) else {}


def normalize_study(study: dict) -> dict[str, Any]:
    identification = _module(study, "identificationModule")
    status = _module(study, "statusModule")
    design = _module(study, "designModule")
    conditions = _module(study, "conditionsModule")
    enrollment = design.get("enrollmentInfo")
    if not isinstance(enrollment, dict):
        enrollment = {}

    return {
        "nct_id": identification.get("nctId"),
        "brief_title": identification.get("briefTitle"),
        "official_title": identification.get("officialTitle"),
        "conditions": conditions.get("conditions", []),
        "overall_status": status.get("overallStatus"),
        "study_type": design.get("studyType"),
        "phases": design.get("phases", []),
        "enrollment_count": enrollment.get("count"),
        "enrollment_type": enrollment.get("type"),
        "start_date": normalize_date_struct(status.get("startDateStruct")),
        "primary_completion_date": normalize_date_struct(
            status.get("primaryCompletionDateStruct")
        ),
        "completion_date": normalize_date_struct(status.get("completionDateStruct")),
        "study_first_submit_date": status.get("studyFirstSubmitDate"),
        "last_update_submit_date": status.get("studyLastUpdateSubmitDate"),
    }


def request_page(
    session: requests.Session,
    base_url: str,
    params: dict[str, Any],
    connect_timeout: float,
    read_timeout: float,
    attempts: int,
    deadline: float,
) -> tuple[dict, str]:
    if "page" in params:
        raise ClinicalTrialsAPIError(
            "ClinicalTrials.gov API v2 does not support 'page'; use pageToken"
        )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        if time.monotonic() >= deadline:
            raise ClinicalTrialsAPIError("ClinicalTrials.gov retrieval deadline exceeded")
        try:
            response = session.get(
                base_url,
                params=params,
                timeout=(connect_timeout, read_timeout),
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt == attempts:
                break
        else:
            if response.status_code == 200:
                try:
                    payload = response.json()
                except requests.JSONDecodeError as exc:
                    raise ClinicalTrialsAPIError(
                        f"API returned invalid JSON url={response.url}: {exc}"
                    ) from exc
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("studies"), list
                ):
                    raise ClinicalTrialsAPIError(
                        f"API response missing studies array url={response.url}"
                    )
                return payload, response.url

            body = response.text[:1000].replace("\n", " ")
            error = ClinicalTrialsAPIError(
                f"HTTP {response.status_code} url={response.url} body={body}"
            )
            if response.status_code not in RETRYABLE_STATUS:
                raise error
            last_error = error
            if attempt == attempts:
                break

        delay = min(2 ** attempt, max(0.0, deadline - time.monotonic()))
        if delay > 0:
            time.sleep(delay)

    raise ClinicalTrialsAPIError(
        f"request failed after {attempts} attempts: {last_error}"
    ) from last_error


def fetch_studies(
    session: requests.Session,
    base_url: str,
    query_key: str,
    query_value: str,
    page_size: int,
    max_studies: int,
    connect_timeout: float,
    read_timeout: float,
    attempts: int,
    total_deadline_seconds: float,
) -> tuple[list[dict], dict[str, Any]]:
    if query_key not in {"query.cond", "query.term"}:
        raise ValueError("query_key must be query.cond or query.term")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    if max_studies < 1:
        raise ValueError("max_studies must be positive")

    deadline = time.monotonic() + total_deadline_seconds
    params: dict[str, Any] = {
        query_key: query_value,
        "pageSize": min(page_size, max_studies),
        "format": "json",
        "countTotal": "true",
    }
    studies: list[dict] = []
    page_records: list[dict[str, Any]] = []
    seen_tokens: set[str] = set()
    total_count: int | None = None

    while len(studies) < max_studies:
        payload, request_url = request_page(
            session,
            base_url,
            params,
            connect_timeout,
            read_timeout,
            attempts,
            deadline,
        )
        page_studies = payload["studies"]
        if total_count is None and isinstance(payload.get("totalCount"), int):
            total_count = payload["totalCount"]
        remaining = max_studies - len(studies)
        studies.extend(page_studies[:remaining])
        token = payload.get("nextPageToken")
        page_records.append(
            {
                "request_url": request_url,
                "returned_studies": len(page_studies),
                "accepted_studies": min(len(page_studies), remaining),
                "has_next_page_token": bool(token),
            }
        )
        if not token or len(studies) >= max_studies:
            break
        if not isinstance(token, str) or token in seen_tokens:
            raise ClinicalTrialsAPIError("invalid or repeated nextPageToken")
        seen_tokens.add(token)
        params["pageToken"] = token
        params["countTotal"] = "false"

    return studies, {
        "query_key": query_key,
        "query_value": query_value,
        "page_size": page_size,
        "max_studies": max_studies,
        "retrieved_studies": len(studies),
        "reported_total_count": total_count,
        "pages": page_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--condition")
    query.add_argument("--query-term")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-studies", type=int, default=250)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--read-timeout", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--deadline", type=float, default=120.0)
    parser.add_argument("--raw-output", required=True)
    parser.add_argument("--normalized-output", required=True)
    parser.add_argument("--provenance-output", required=True)
    args = parser.parse_args()

    if args.attempts < 1 or args.deadline <= 0:
        parser.error("attempts and deadline must be positive")
    query_key = "query.cond" if args.condition is not None else "query.term"
    query_value = args.condition if args.condition is not None else args.query_term

    try:
        studies, provenance = fetch_studies(
            requests.Session(),
            args.base_url,
            query_key,
            query_value,
            args.page_size,
            args.max_studies,
            args.connect_timeout,
            args.read_timeout,
            args.attempts,
            args.deadline,
        )
    except (ClinicalTrialsAPIError, ValueError) as exc:
        print(f"CLINICALTRIALS_API ERROR {exc}", file=sys.stderr)
        return 1

    normalized = [normalize_study(item) for item in studies]
    if studies and not normalized:
        print(
            "CLINICALTRIALS_API ERROR non-empty API response normalized to zero records",
            file=sys.stderr,
        )
        return 1

    raw_path = Path(args.raw_output).expanduser()
    normalized_path = Path(args.normalized_output).expanduser()
    provenance_path = Path(args.provenance_output).expanduser()
    atomic_write_json(raw_path, {"studies": studies})
    atomic_write_json(normalized_path, {"studies": normalized})

    completion_missing = sum(item["completion_date"] is None for item in normalized)
    completion_invalid = sum(
        item["completion_date"] is not None
        and item["completion_date"].get("precision") == "invalid"
        for item in normalized
    )
    provenance.update(
        {
            "source": "ClinicalTrials.gov API v2",
            "base_url": args.base_url,
            "retrieved_at": utc_now(),
            "raw_output": str(raw_path),
            "raw_sha256": file_sha256(raw_path),
            "normalized_output": str(normalized_path),
            "normalized_sha256": file_sha256(normalized_path),
            "normalized_studies": len(normalized),
            "completion_date_missing": completion_missing,
            "completion_date_invalid": completion_invalid,
        }
    )
    atomic_write_json(provenance_path, provenance)
    print(
        f"CLINICALTRIALS_API OK retrieved={len(studies)} normalized={len(normalized)} "
        f"pages={len(provenance['pages'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
