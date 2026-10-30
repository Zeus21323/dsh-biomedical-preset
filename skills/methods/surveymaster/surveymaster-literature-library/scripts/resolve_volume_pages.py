"""Resolve missing volume/pages/number fields in papers.json via OpenAlex + Crossref.

Reads WARN lines from export-bib diagnostics stdout (or --keys list), fetches metadata from
OpenAlex (primary) with automatic fallback to Crossref, patches only missing fields,
and writes the updated library once. DOI metadata fetches use a bounded request
pool; library patching and saving remain sequential in the main process.

With --verify-metadata, also checks title/authors/venue/year consistency between
the local record and the authoritative API response, and reports discrepancies
without modifying those fields.

Usage
-----
  # Pipe export-bib diagnostics directly:
  python3 scripts/bibliography_library.py export-bib \\
      --library papers.json --output /tmp/refs.bib --diagnostics-stdout \\
    | python3 scripts/resolve_volume_pages.py \\
        --library papers.json --dry-run --report-stream stdout

  # Or pass explicit bib_keys:
  python3 scripts/resolve_volume_pages.py \\
      --library papers.json --keys "smith2020,jones2021" --concurrency 4

  # Full resolve + upsert (no dry-run):
  python3 scripts/resolve_volume_pages.py --library papers.json

  # Verify metadata consistency for all records that have a DOI:
  python3 scripts/resolve_volume_pages.py --library papers.json --verify-metadata

  # Verify all DOI records and also resolve volume/pages for WARN keys from stdin:
  python3 scripts/bibliography_library.py export-bib ... --diagnostics-stdout \\
    | python3 scripts/resolve_volume_pages.py \\
        --library papers.json --verify-metadata --report-stream stdout

Exit codes
----------
  0   all targeted keys are in a terminal state (patched / already-filled /
      already-marked-unresolvable) AND no metadata discrepancies. Stop here —
      no further resolver runs will change anything.
  1   one or more keys are still genuinely unresolved this run
      (fetch_error / missing_doi / missing_key, or just-now marked unresolvable).
      Re-running will not change `already_unresolvable` keys; it may only help
      transient `fetch_error` keys.
  2   only metadata discrepancies were reported (verify-metadata mode); all
      volume/pages/number resolution succeeded. Show the discrepancies to the
      user; do not re-run the resolver.
  10  usage / I/O error (missing file, bad argument).

Decision rules for callers
--------------------------
  - Read the `SUMMARY:` line in stderr, not just the exit code.
  - If `newly_unresolvable=0 patched=0 fetch_error=0` and exit != 0, the only
    real signal is metadata or already-unresolvable keys; do not retry.
  - Never shrink batch size to "work around" exit 1. Concurrency is bounded
    by `--concurrency`, not by the number of keys passed via `--keys`.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org"
CONTACT_EMAIL = "science-navigator@bohrium.tech"
HEADERS = {
    "User-Agent": f"SurveyMaster/1.0 (mailto:{CONTACT_EMAIL})",
    "Accept": "application/json",
}

# Exit codes — see module docstring for full semantics.
EXIT_OK = 0
EXIT_HAS_UNRESOLVED = 1
EXIT_METADATA_WARN = 2
EXIT_IO_ERROR = 10


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no httpx required)
# ---------------------------------------------------------------------------

def _get_json(url: str, timeout: int = 10) -> dict | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"  HTTP {e.code}: {url}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  fetch error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

def _fetch_openalex(doi: str, timeout: int = 10) -> dict[str, Any] | None:
    data = _get_json(f"{OPENALEX_BASE}/works/doi:{doi}", timeout=timeout)
    if not data:
        return None
    biblio = data.get("biblio") or {}
    first_page = str(biblio.get("first_page") or "").strip()
    last_page = str(biblio.get("last_page") or "").strip()
    pages = ""
    if first_page and last_page:
        pages = f"{first_page}--{last_page}"
    elif first_page:
        pages = first_page

    # Authors: list of display names from authorships
    authors: list[str] = []
    for a in data.get("authorships") or []:
        name = (a.get("author") or {}).get("display_name") or ""
        if name:
            authors.append(name)

    # Venue/source
    primary = data.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = str(source.get("display_name") or "").strip()

    return {
        "volume": str(biblio.get("volume") or "").strip() or None,
        "number": str(biblio.get("issue") or "").strip() or None,
        "pages": pages or None,
        # metadata fields (for verification only)
        "_title": str(data.get("title") or "").strip() or None,
        "_authors": authors or None,
        "_venue": venue or None,
        "_year": data.get("publication_year"),
    }


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------

def _fetch_crossref(doi: str, timeout: int = 10) -> dict[str, Any] | None:
    data = _get_json(f"{CROSSREF_BASE}/works/{doi}", timeout=timeout)
    if not data:
        return None
    item = data.get("message") or {}
    page = str(item.get("page") or "").strip()
    pages = ""
    if page:
        pages = page.replace("-", "--", 1) if "-" in page else page

    # Title
    titles = item.get("title") or []
    title = titles[0].strip() if titles else None

    # Authors
    authors: list[str] = []
    for a in item.get("author") or []:
        given = str(a.get("given") or "").strip()
        family = str(a.get("family") or "").strip()
        if family:
            authors.append(f"{given} {family}".strip() if given else family)

    # Venue
    container = item.get("container-title") or []
    venue = container[0].strip() if container else None

    # Year
    year = None
    issued = item.get("issued") or {}
    parts = issued.get("date-parts") or []
    if parts and parts[0]:
        year = parts[0][0]

    return {
        "volume": str(item.get("volume") or "").strip() or None,
        "number": str(item.get("issue") or "").strip() or None,
        "pages": pages or None,
        "_title": title,
        "_authors": authors or None,
        "_venue": venue,
        "_year": year,
    }


# ---------------------------------------------------------------------------
# Combined fetch with fallback
# ---------------------------------------------------------------------------

def fetch_biblio(doi: str, timeout: int = 10) -> dict[str, Any] | None:
    """Return {volume, number, pages, _title, _authors, _venue, _year} or None."""
    result = _fetch_openalex(doi, timeout=timeout)
    if result and any(v for k, v in result.items() if not k.startswith("_")):
        return result
    result = _fetch_crossref(doi, timeout=timeout)
    if result and any(v for k, v in result.items() if not k.startswith("_")):
        return result
    # Even if no biblio fields resolved, return metadata fields if available
    if result and any(v for k, v in result.items() if k.startswith("_")):
        return result
    return None


# ---------------------------------------------------------------------------
# Metadata consistency check
# ---------------------------------------------------------------------------

def _normalize_title(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy comparison."""
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _normalize_venue(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def check_metadata_consistency(
    rec: dict[str, Any],
    fetched: dict[str, Any],
    bib_key: str,
) -> list[str]:
    """Return a list of discrepancy strings (empty = all consistent)."""
    issues: list[str] = []

    # Title
    local_title = str(rec.get("title") or "").strip()
    remote_title = str(fetched.get("_title") or "").strip()
    if local_title and remote_title:
        if _normalize_title(local_title) != _normalize_title(remote_title):
            issues.append(
                f"  TITLE_MISMATCH [{bib_key}]\n"
                f"    local:  {local_title}\n"
                f"    remote: {remote_title}"
            )

    # Year
    local_year = str(rec.get("year") or "").strip()
    remote_year = str(fetched.get("_year") or "").strip()
    if local_year and remote_year and local_year != remote_year:
        issues.append(
            f"  YEAR_MISMATCH [{bib_key}]: local={local_year}  remote={remote_year}"
        )

    # Venue (journal / booktitle / proceedings)
    local_venue = ""
    for k in ("venue", "journal", "booktitle", "proceedings"):
        v = str(rec.get(k) or "").strip()
        if v:
            local_venue = v
            break
    remote_venue = str(fetched.get("_venue") or "").strip()
    if local_venue and remote_venue:
        if _normalize_venue(local_venue) != _normalize_venue(remote_venue):
            # Only flag if the overlap is very low (avoid abbreviation false positives)
            local_words = set(_normalize_venue(local_venue).split())
            remote_words = set(_normalize_venue(remote_venue).split())
            if local_words and remote_words:
                overlap = len(local_words & remote_words) / max(len(local_words), len(remote_words))
                if overlap < 0.4:
                    issues.append(
                        f"  VENUE_MISMATCH [{bib_key}]\n"
                        f"    local:  {local_venue}\n"
                        f"    remote: {remote_venue}"
                    )

    # First author family name (light check — full author lists diverge often)
    local_authors = rec.get("authors") or []
    remote_authors = fetched.get("_authors") or []
    if local_authors and remote_authors:
        def _first_family(name: str) -> str:
            parts = name.strip().split()
            return parts[-1].lower() if parts else ""

        local_first = _first_family(
            local_authors[0] if isinstance(local_authors, list) else str(local_authors)
        )
        remote_first = _first_family(remote_authors[0])
        if local_first and remote_first and local_first != remote_first:
            issues.append(
                f"  AUTHOR_MISMATCH [{bib_key}]: "
                f"first author local={local_authors[0] if isinstance(local_authors, list) else local_authors}  "
                f"remote={remote_authors[0]}"
            )

    return issues


# ---------------------------------------------------------------------------
# WARN line parsing
# ---------------------------------------------------------------------------

_WARN_RE = re.compile(
    r"WARN:.*missing volume/pages/number.*?:\s*(.+)",
    re.IGNORECASE,
)
_KEY_RE = re.compile(r"([A-Za-z0-9_\-]+)\(missing_[^)]+\)")
_GROUP_LINE_RE = re.compile(
    r"^\s*missing_(?:volume|pages_and_number)\s*\([^)]*\)\s*:\s*(.+)$",
    re.IGNORECASE,
)
_BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def parse_warn_keys(text: str) -> list[str]:
    """Extract bib_keys from export-bib WARN lines.

    Supports two output formats produced by ``bibliography_library.py``:

    - Flat single-line (legacy):
        ``WARN: ... : key1(missing_volume), key2(missing_pages_and_number), ...``
    - Grouped multi-line (current):
        ``WARN: ... missing volume/pages/number ... :`` header line followed by
        indented ``  missing_volume (N): key1, key2, ...`` or
        ``  missing_volume (N, showing M): key1, key2, ...`` and the
        equivalent ``missing_pages_and_number`` lines.
    """
    keys: list[str] = []
    for line in text.splitlines():
        m = _WARN_RE.search(line)
        if m and m.group(1).strip():
            # Flat format: keys carry ``(missing_xxx)`` suffix on the same line.
            keys.extend(_KEY_RE.findall(m.group(1)))
            continue

        gm = _GROUP_LINE_RE.match(line)
        if gm:
            # Grouped format: comma-separated bare bib_keys after the label.
            for raw in gm.group(1).split(","):
                k = raw.strip()
                if k and _BARE_KEY_RE.match(k):
                    keys.append(k)
    return list(dict.fromkeys(keys))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Library helpers
# ---------------------------------------------------------------------------

def load_library(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "papers" in data:
        return data["papers"]
    raise ValueError(f"Unrecognised library format in {path}")


def save_library(path: Path, lib: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(lib, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_record(rec: dict[str, Any], fetched: dict[str, Any]) -> dict[str, Any]:
    """Merge fetched fields into rec. Returns dict of changed fields (empty = no change).

    volume/number/pages: only filled when missing.
    year: always overwritten with the authoritative API value when available,
          since PaperSearch publication-date data can be inaccurate.
    """
    changes: dict[str, Any] = {}
    for fld in ("volume", "number", "pages"):
        if fetched.get(fld) and not str(rec.get(fld) or "").strip():
            rec[fld] = fetched[fld]
            changes[fld] = fetched[fld]
    remote_year = fetched.get("_year")
    if remote_year is not None:
        local_year = str(rec.get("year") or "").strip()
        remote_year_str = str(remote_year).strip()
        if remote_year_str and local_year != remote_year_str:
            rec["year"] = remote_year_str
            changes["year"] = f"{local_year} → {remote_year_str}"
    return changes


@dataclass(frozen=True)
class ResolveResult:
    bib_key: str
    index: int | None
    doi: str
    fetched: dict[str, Any] | None
    status: str
    message: str
    metadata_issues: list[str] = field(default_factory=list)


FetchBiblio = Callable[[str], dict[str, Any] | None]


def resolve_targets(
    lib: list[dict[str, Any]],
    target_keys: list[str],
    *,
    concurrency: int = 4,
    fetcher: FetchBiblio = fetch_biblio,
    verify_metadata: bool = False,
) -> list[ResolveResult]:
    """Fetch missing biblio fields concurrently without mutating the library."""
    by_key = {str(p.get("bib_key") or ""): i for i, p in enumerate(lib)}
    results: list[ResolveResult | None] = [None] * len(target_keys)
    pending: list[tuple[int, str, int, str]] = []

    for pos, bk in enumerate(target_keys):
        idx = by_key.get(bk)
        if idx is None:
            results[pos] = ResolveResult(bk, None, "", None, "missing_key", "not found in library")
            continue

        if lib[idx].get("unresolvable") is True:
            results[pos] = ResolveResult(
                bk, idx, "", None, "already_unresolvable",
                "previously marked unresolvable; skipping API call",
            )
            continue

        doi = str(lib[idx].get("doi") or "").strip()
        if not doi:
            results[pos] = ResolveResult(bk, idx, "", None, "missing_doi", "no DOI in record — cannot fetch")
            continue

        pending.append((pos, bk, idx, doi))

    if pending:
        max_workers = max(1, int(concurrency or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(fetcher, doi): (pos, bk, idx, doi)
                for pos, bk, idx, doi in pending
            }
            for future in as_completed(future_map):
                pos, bk, idx, doi = future_map[future]
                try:
                    fetched = future.result()
                except Exception as exc:
                    results[pos] = ResolveResult(
                        bk, idx, doi, None, "fetch_error", f"fetch error: {exc}"
                    )
                    continue

                biblio_fields = {k: v for k, v in (fetched or {}).items() if not k.startswith("_")}
                if fetched and any(biblio_fields.values()):
                    meta_issues = (
                        check_metadata_consistency(lib[idx], fetched, bk)
                        if verify_metadata else []
                    )
                    results[pos] = ResolveResult(
                        bk, idx, doi, fetched, "resolved", "resolved",
                        metadata_issues=meta_issues,
                    )
                else:
                    # No biblio fields, but check metadata if requested
                    meta_issues = (
                        check_metadata_consistency(lib[idx], fetched or {}, bk)
                        if verify_metadata and fetched else []
                    )
                    results[pos] = ResolveResult(
                        bk, idx, doi, fetched,
                        "unresolvable", "no biblio data from OpenAlex or Crossref",
                        metadata_issues=meta_issues,
                    )

    return [r for r in results if r is not None]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", required=True, help="Path to papers.json")
    ap.add_argument(
        "--keys",
        default="",
        help="Comma-separated bib_keys to resolve (overrides stdin parsing)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing to library",
    )
    ap.add_argument(
        "--verify-metadata",
        action="store_true",
        dest="verify_metadata",
        help=(
            "For every record with a DOI, fetch from OpenAlex/Crossref and report "
            "discrepancies in title, authors, venue, and year. Does not modify these fields."
        ),
    )
    ap.add_argument(
        "--verify-targets-only",
        action="store_true",
        help="When used with --verify-metadata, verify only the keys selected by --keys/stdin.",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP timeout per request (default: 10s)",
    )
    ap.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Maximum concurrent DOI metadata fetches (default: 4)",
    )
    ap.add_argument(
        "--report-stream",
        choices=("stderr", "stdout"),
        default="stderr",
        help="Where to emit non-fatal INFO/WARN/SUMMARY diagnostics (default: stderr).",
    )
    ns = ap.parse_args()
    report_stream = sys.stdout if ns.report_stream == "stdout" else sys.stderr

    lib_path = Path(ns.library)
    if not lib_path.exists():
        print(f"[E{EXIT_IO_ERROR}] library not found: {lib_path}", file=sys.stderr)
        print("       Fix: check --library path", file=sys.stderr)
        return EXIT_IO_ERROR

    lib = load_library(lib_path)

    # Determine target keys for volume/pages resolution
    if ns.keys.strip():
        target_keys = [k.strip() for k in ns.keys.split(",") if k.strip()]
    else:
        stdin_text = sys.stdin.read() if not sys.stdin.isatty() else ""
        target_keys = parse_warn_keys(stdin_text)

    # For --verify-metadata, default to all DOI records unless explicitly limited.
    if ns.verify_metadata and not ns.verify_targets_only:
        doi_keys = [
            str(p.get("bib_key") or "")
            for p in lib
            if str(p.get("doi") or "").strip() and str(p.get("bib_key") or "").strip()
        ]
        # Merge: verify all DOI records; also resolve volume/pages for WARN keys
        all_keys = list(dict.fromkeys(doi_keys + target_keys))
    else:
        all_keys = target_keys

    if not all_keys:
        print(
            "INFO: RESOLVE_SKIPPED — no WARN keys in diagnostics input and no --keys given; "
            "volume/pages resolution skipped. NO_MISMATCHES.",
            file=report_stream,
        )
        return 0

    print(f"INFO: processing {len(all_keys)} key(s){' (verify-metadata enabled)' if ns.verify_metadata else ''}", file=report_stream)

    by_key = {str(p.get("bib_key") or ""): i for i, p in enumerate(lib)}

    def fetch_with_timeout(doi: str) -> dict[str, Any] | None:
        return fetch_biblio(doi, timeout=ns.timeout)

    n_to_queue = sum(
        1 for bk in all_keys
        if by_key.get(bk) is not None
        and str(lib[by_key[bk]].get("doi") or "").strip()
        and lib[by_key[bk]].get("unresolvable") is not True
    )
    if n_to_queue:
        print(f"INFO: queuing {n_to_queue} key(s) with DOI for fetch", file=report_stream)

    results = resolve_targets(
        lib,
        all_keys,
        concurrency=ns.concurrency,
        fetcher=fetch_with_timeout,
        verify_metadata=ns.verify_metadata,
    )

    unresolved: list[str] = []
    all_metadata_issues: list[str] = []

    n_patched = 0
    n_skip_filled = 0
    n_already_unresolvable = 0
    n_newly_unresolvable = 0
    n_fetch_error = 0
    n_missing_doi = 0
    n_missing_key = 0

    for result in results:
        bk = result.bib_key
        idx = result.index

        if result.metadata_issues:
            all_metadata_issues.extend(result.metadata_issues)

        if result.status == "missing_key":
            print(f"  SKIP {bk}: {result.message}", file=report_stream)
            if bk in target_keys:
                n_missing_key += 1
                unresolved.append(bk)
            continue

        if result.status == "already_unresolvable":
            print(f"  SKIP_UNRESOLVABLE {bk}: {result.message}", file=report_stream)
            if bk in target_keys:
                n_already_unresolvable += 1
            continue

        if result.status == "missing_doi":
            print(f"  SKIP {bk}: {result.message}", file=report_stream)
            if bk in target_keys:
                n_missing_doi += 1
                unresolved.append(bk)
            continue

        if result.status == "fetch_error":
            print(f"  FETCH_ERROR {bk}: {result.message}", file=report_stream)
            if bk in target_keys:
                n_fetch_error += 1
                unresolved.append(bk)
            continue

        if result.status == "unresolvable" or not result.fetched:
            print(f"  UNRESOLVABLE {bk}: {result.message}", file=report_stream)
            if idx is not None and not ns.dry_run and bk in target_keys:
                lib[idx]["unresolvable"] = True
            if bk in target_keys:
                n_newly_unresolvable += 1
                unresolved.append(bk)
            continue

        if idx is None:
            print(f"  UNRESOLVABLE {bk}: missing library index", file=report_stream)
            if bk in target_keys:
                n_newly_unresolvable += 1
                unresolved.append(bk)
            continue

        rec = lib[idx]
        changes = patch_record(rec, result.fetched)
        if changes:
            print(f"  PATCHED {bk}: {changes}", file=report_stream)
            if bk in target_keys:
                n_patched += 1
            if not ns.dry_run:
                lib[idx] = rec
        else:
            if bk in target_keys:
                print(f"  SKIP {bk}: fields already populated", file=report_stream)
                n_skip_filled += 1

    if all_metadata_issues:
        print(
            f"\nMETADATA_CHECK: {len(all_metadata_issues)} discrepancy(ies) found "
            f"(fields not modified — review and correct manually if needed):",
            file=report_stream,
        )
        for issue in all_metadata_issues:
            print(issue, file=report_stream)
    elif ns.verify_metadata:
        print("METADATA_CHECK: all verified records consistent with API data.", file=report_stream)

    if not ns.dry_run and target_keys:
        save_library(lib_path, lib)
        print(f"INFO: library written to {lib_path}", file=report_stream)
    elif ns.dry_run:
        print("INFO: dry-run mode — library not modified", file=report_stream)

    # Machine-readable summary for orchestrator agents: one line, stable key order.
    # When all counts of "actionable failure" (newly_unresolvable, fetch_error,
    # missing_doi, missing_key) are zero, agents must stop retrying.
    print(
        f"SUMMARY: total={len(target_keys)} "
        f"patched={n_patched} "
        f"skip_filled={n_skip_filled} "
        f"skip_already_unresolvable={n_already_unresolvable} "
        f"newly_unresolvable={n_newly_unresolvable} "
        f"fetch_error={n_fetch_error} "
        f"missing_doi={n_missing_doi} "
        f"missing_key={n_missing_key} "
        f"metadata_issues={len(all_metadata_issues)}",
        file=report_stream,
    )

    if unresolved:
        print(
            f"WARN: {len(unresolved)} key(s) still unresolved this run: "
            f"{', '.join(unresolved)}",
            file=report_stream,
        )
        return EXIT_HAS_UNRESOLVED

    if all_metadata_issues:
        return EXIT_METADATA_WARN

    count = len(target_keys) if target_keys else 0
    print(
        f"INFO: all {count} key(s) in terminal state; "
        f"no further resolver runs required.",
        file=report_stream,
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
