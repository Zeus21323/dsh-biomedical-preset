"""Resolve browser-discovered paper candidates and insert them into papers.json.

This script does not call browser-use. The agent/orchestrator must call the
browser-use plugin first, write its extracted candidates to JSON, then run this
script to enrich metadata through public DOI/title metadata APIs and merge the
records into the SurveyMaster literature library.

Candidate input shape:
[
  {
    "title": "Paper title",
    "doi": "10.xxxx/yyyy",
    "url": "https://example.com/paper",
    "year_hint": "2024",
    "venue_hint": "Journal or Conference Name",
    "authors_text": "Author A, Author B",
    "abstract_hint": "Short abstract if available",
    "source": "browser-use"
  }
]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org"
ARXIV_BASE = "https://export.arxiv.org/api/query"
CONTACT_EMAIL = "science-navigator@bohrium.tech"
HEADERS = {
    "User-Agent": f"SurveyMaster/1.0 (mailto:{CONTACT_EMAIL})",
    "Accept": "application/json",
}
OPENALEX_DISABLED = False

YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.I)
ARXIV_RE = re.compile(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
CONFERENCE_TYPE_RE = re.compile(
    r"\b("
    r"conference|proceedings|symposium|workshop|congress|meeting|"
    r"AAAI|IJCAI|ICML|NeurIPS|NIPS|ICLR|CVPR|ICCV|ECCV|ACL|EMNLP|NAACL|COLING|"
    r"SIGIR|SIGKDD|KDD|WWW|WSDM|CHI|UbiComp|UIST|SIGGRAPH|"
    r"ICSE|FSE|ASE|ISSTA|PLDI|OOPSLA|POPL|ASPLOS|MICRO|ISCA|"
    r"INFOCOM|SIGCOMM|MobiCom|MobiSys|SenSys|VLDB|SIGMOD|PODS|"
    r"IEEE/CVF|USENIX|ESWC"
    r")\b",
    re.I,
)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"INFO: {msg}", file=sys.stderr)


def get_json(url: str, timeout: int = 15) -> dict[str, Any] | None:
    global OPENALEX_DISABLED
    if OPENALEX_DISABLED and url.startswith(OPENALEX_BASE):
        return None
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429 and url.startswith(OPENALEX_BASE):
            OPENALEX_DISABLED = True
            warn("OpenAlex HTTP 429 rate limit; disabling OpenAlex for the rest of this resolver run")
            return None
        if exc.code != 404:
            warn(f"HTTP {exc.code}: {url}")
        return None
    except Exception as exc:
        warn(f"fetch failed: {exc}")
        return None


def get_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={**HEADERS, "Accept": "application/xml,text/xml,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        warn(f"fetch failed: {exc}")
        return ""


def norm_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_title(value: Any) -> str:
    text = norm_space(value).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def jaccard_title(a: Any, b: Any) -> float:
    aa = set(normalize_title(a).split())
    bb = set(normalize_title(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def normalize_doi(value: Any) -> str:
    text = norm_space(value)
    if not text:
        return ""
    match = DOI_RE.search(text)
    doi = match.group(0) if match else text
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.strip().rstrip(".,);]").lower()


def extract_doi(candidate: dict[str, Any]) -> str:
    for key in ("doi", "url", "title"):
        doi = normalize_doi(candidate.get(key))
        if doi.startswith("10."):
            return doi
    return ""


def extract_arxiv_id(candidate: dict[str, Any]) -> str:
    for key in ("arxiv_id", "url", "doi", "title"):
        match = ARXIV_RE.search(str(candidate.get(key) or ""))
        if match:
            return match.group(1)
    return ""


def parse_year(value: Any) -> str:
    match = YEAR_RE.search(str(value or ""))
    return match.group(0) if match else ""


def split_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [norm_space(v) for v in value if norm_space(v)]
    text = norm_space(value)
    if not text:
        return []
    text = re.sub(r"\s+\bet al\.?$", "", text, flags=re.I)
    parts = re.split(r"\s*(?:;|\band\b|、|，)\s*|\s*,\s*(?=[A-Z][A-Za-z .'-]+(?:,|$))", text)
    authors = [p.strip(" ,;") for p in parts if p.strip(" ,;")]
    if len(authors) == 1 and "," in text:
        authors = [p.strip() for p in text.split(",") if p.strip()]
    return authors


def openalex_abstract(work: dict[str, Any]) -> str:
    inverted = work.get("abstract_inverted_index") or {}
    if not isinstance(inverted, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        if isinstance(idxs, list):
            for idx in idxs:
                try:
                    positions.append((int(idx), str(word)))
                except (TypeError, ValueError):
                    continue
    if not positions:
        return ""
    return " ".join(word for _, word in sorted(positions))


def openalex_record(work: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for item in work.get("authorships") or []:
        name = ((item or {}).get("author") or {}).get("display_name")
        if name:
            authors.append(norm_space(name))
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = norm_space(source.get("display_name") or work.get("host_venue", {}).get("display_name"))
    doi = normalize_doi(work.get("doi"))
    url = norm_space(primary.get("landing_page_url") or work.get("doi") or work.get("id"))
    work_type = norm_space(work.get("type") or work.get("type_crossref"))
    is_conference = bool(CONFERENCE_TYPE_RE.search(work_type) or CONFERENCE_TYPE_RE.search(venue))
    biblio = work.get("biblio") or {}
    first_page = norm_space(biblio.get("first_page")) if isinstance(biblio, dict) else ""
    last_page = norm_space(biblio.get("last_page")) if isinstance(biblio, dict) else ""
    pages = f"{first_page}-{last_page}" if first_page and last_page and first_page != last_page else first_page
    return clean_record({
        "title": norm_space(work.get("title")),
        "authors": authors,
        "year": str(work.get("publication_year") or ""),
        "journal": "" if is_conference else venue,
        "booktitle": venue if is_conference else "",
        "entry_type": "inproceedings" if is_conference else "article",
        "volume": biblio.get("volume") if isinstance(biblio, dict) else "",
        "number": biblio.get("issue") if isinstance(biblio, dict) else "",
        "pages": pages,
        "doi": doi,
        "url": url,
        "abstract": openalex_abstract(work),
    })


def crossref_abstract(value: Any) -> str:
    text = norm_space(value)
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return norm_space(html.unescape(text))


def crossref_record(item: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in item.get("author") or []:
        given = norm_space(author.get("given"))
        family = norm_space(author.get("family"))
        if family:
            authors.append(norm_space(f"{given} {family}" if given else family))
    titles = item.get("title") or []
    containers = item.get("container-title") or []
    issued = item.get("issued") or {}
    parts = issued.get("date-parts") or []
    year = str(parts[0][0]) if parts and parts[0] else ""
    links = item.get("link") or []
    url = norm_space(item.get("URL") or (links[0].get("URL") if links else ""))
    crossref_type = norm_space(item.get("type"))
    venue = norm_space(containers[0] if containers else item.get("publisher"))
    is_conference = bool(CONFERENCE_TYPE_RE.search(crossref_type) or CONFERENCE_TYPE_RE.search(venue))
    return clean_record({
        "title": norm_space(titles[0] if titles else ""),
        "authors": authors,
        "year": year,
        "journal": "" if is_conference else venue,
        "booktitle": venue if is_conference else "",
        "entry_type": "inproceedings" if is_conference else "article",
        "volume": item.get("volume"),
        "number": item.get("issue"),
        "pages": item.get("page") or item.get("article-number"),
        "doi": normalize_doi(item.get("DOI")),
        "url": url,
        "abstract": crossref_abstract(item.get("abstract")),
    })


def resolve_openalex_by_doi(doi: str) -> dict[str, Any] | None:
    if not doi or OPENALEX_DISABLED:
        return None
    quoted = urllib.parse.quote(f"doi:{doi}", safe=":")
    data = get_json(f"{OPENALEX_BASE}/works/{quoted}")
    if data:
        return openalex_record(data)
    return None


def resolve_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    if not doi:
        return None
    data = get_json(f"{CROSSREF_BASE}/works/{urllib.parse.quote(doi, safe='')}")
    item = (data or {}).get("message") or {}
    if item:
        return crossref_record(item)
    return None


def resolve_openalex_by_title(title: str) -> dict[str, Any] | None:
    if not title or OPENALEX_DISABLED:
        return None
    params = urllib.parse.urlencode({"search": title, "per-page": 5})
    data = get_json(f"{OPENALEX_BASE}/works?{params}")
    best: tuple[float, dict[str, Any]] | None = None
    for work in (data or {}).get("results") or []:
        score = jaccard_title(title, work.get("title"))
        if score >= 0.55 and (best is None or score > best[0]):
            best = (score, work)
    return openalex_record(best[1]) if best else None


def resolve_crossref_by_title(title: str) -> dict[str, Any] | None:
    if not title:
        return None
    params = urllib.parse.urlencode({"query.title": title, "rows": 5})
    data = get_json(f"{CROSSREF_BASE}/works?{params}")
    best: tuple[float, dict[str, Any]] | None = None
    for item in ((data or {}).get("message") or {}).get("items") or []:
        titles = item.get("title") or []
        score = jaccard_title(title, titles[0] if titles else "")
        if score >= 0.55 and (best is None or score > best[0]):
            best = (score, item)
    return crossref_record(best[1]) if best else None


def resolve_arxiv(arxiv_id: str) -> dict[str, Any] | None:
    if not arxiv_id:
        return None
    params = urllib.parse.urlencode({"id_list": arxiv_id})
    text = get_text(f"{ARXIV_BASE}?{params}")
    if not text:
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        return None
    authors = []
    for author in entry.findall("a:author", ns):
        name = author.findtext("a:name", default="", namespaces=ns)
        if name:
            authors.append(norm_space(name))
    title = entry.findtext("a:title", default="", namespaces=ns)
    abstract = entry.findtext("a:summary", default="", namespaces=ns)
    published = entry.findtext("a:published", default="", namespaces=ns)
    url = entry.findtext("a:id", default="", namespaces=ns)
    doi = ""
    for link in entry.findall("a:link", ns):
        if link.attrib.get("title") == "doi":
            doi = normalize_doi(link.attrib.get("href"))
    return clean_record({
        "title": title,
        "authors": authors,
        "year": parse_year(published),
        "journal": "arXiv",
        "entry_type": "online",
        "doi": doi,
        "url": url or f"https://arxiv.org/abs/{arxiv_id}",
        "abstract": abstract,
    })


def candidate_fallback(candidate: dict[str, Any]) -> dict[str, Any]:
    venue = candidate.get("journal") or candidate.get("venue") or candidate.get("venue_hint")
    entry_type = candidate.get("entry_type") or candidate.get("type")
    return clean_record({
        "title": candidate.get("title"),
        "authors": split_authors(candidate.get("authors") or candidate.get("authors_text")),
        "year": parse_year(candidate.get("year") or candidate.get("year_hint")),
        "journal": venue,
        "booktitle": candidate.get("booktitle") or candidate.get("conference") or candidate.get("conferenceName"),
        "entry_type": entry_type,
        "doi": extract_doi(candidate),
        "url": candidate.get("url"),
        "abstract": candidate.get("abstract") or candidate.get("abstract_hint"),
    })


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    entry_type = norm_space(record.get("entry_type"))
    journal = norm_space(record.get("journal"))
    booktitle = norm_space(record.get("booktitle"))
    venue = booktitle or journal
    if not entry_type:
        if booktitle or CONFERENCE_TYPE_RE.search(venue):
            entry_type = "inproceedings"
        elif venue.lower() == "arxiv" or (extract_arxiv_id(record) and not venue):
            entry_type = "online"
        else:
            entry_type = "article"
    if entry_type == "inproceedings" and not booktitle:
        booktitle = journal
        journal = ""
    out = {
        "title": norm_space(record.get("title")),
        "authors": [norm_space(a) for a in record.get("authors") or [] if norm_space(a)],
        "year": parse_year(record.get("year")),
        "journal": journal,
        "booktitle": booktitle,
        "entry_type": entry_type,
        "volume": norm_space(record.get("volume")),
        "number": norm_space(record.get("number")),
        "pages": norm_space(record.get("pages")),
        "doi": normalize_doi(record.get("doi")),
        "url": norm_space(record.get("url")),
        "abstract": norm_space(record.get("abstract")),
    }
    return out


def merge_prefer_rich(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if value in ("", None, []):
            continue
        if key == "abstract" and len(str(value)) < len(str(merged.get(key) or "")):
            continue
        if not merged.get(key) or key in {"doi", "url"}:
            merged[key] = value
    return clean_record(merged)


def resolve_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    fallback = candidate_fallback(candidate)
    resolved: dict[str, Any] = fallback if has_required_fields(fallback) and fallback.get("abstract") else {}
    doi = extract_doi(candidate)
    arxiv_id = extract_arxiv_id(candidate)
    title = norm_space(candidate.get("title"))

    if resolved:
        resolver_chain = (
            (arxiv_id, resolve_arxiv),
            (doi, resolve_crossref_by_doi),
            (doi, resolve_openalex_by_doi),
        )
    else:
        resolver_chain = (
            (arxiv_id, resolve_arxiv),
            (doi, resolve_crossref_by_doi),
            (doi, resolve_openalex_by_doi),
            (title, resolve_crossref_by_title),
            (title, resolve_openalex_by_title),
        )

    for resolver_arg, resolver in resolver_chain:
        if not resolver_arg:
            continue
        try:
            fetched = resolver(resolver_arg)
        except Exception as exc:
            warn(f"resolver failed for {title or doi or arxiv_id}: {exc}")
            fetched = None
        if fetched and fetched.get("title"):
            resolved = merge_prefer_rich(resolved, fetched)
        if has_required_fields(resolved) and resolved.get("abstract"):
            break

    record = merge_prefer_rich(resolved, fallback)
    if not has_required_fields(record):
        warn(f"skip incomplete candidate: {title or doi or candidate.get('url')}")
        return None
    return record


def has_required_fields(record: dict[str, Any]) -> bool:
    venue = record.get("journal") or record.get("booktitle")
    return bool(record.get("title") and record.get("authors") and record.get("year") and venue)


def load_candidates(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        for key in ("results", "candidates", "papers"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError("candidate JSON must be a list or an object with results/candidates/papers")
    return [item for item in raw if isinstance(item, dict)]


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    for record in records:
        doi = normalize_doi(record.get("doi"))
        title_key = normalize_title(record.get("title"))
        if doi and doi in seen_doi:
            continue
        if title_key and title_key in seen_title:
            continue
        if doi:
            seen_doi.add(doi)
        if title_key:
            seen_title.add(title_key)
        out.append(record)
    return out


def run_command(argv: list[str], *, input_text: str | None = None) -> int:
    proc = subprocess.run(argv, input=input_text, text=True)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve browser-use candidate papers and insert into papers.json.")
    parser.add_argument("--work", required=True, help="Survey workspace containing writing_constraints.json and papers.json.")
    parser.add_argument("--candidates-json", required=True, help="Browser-use candidate JSON file under the workspace.")
    parser.add_argument("--library", default="", help="Path to papers.json. Defaults to $WORK/papers.json.")
    parser.add_argument("--bibliography-script", required=True, help="Path to bibliography_library.py.")
    parser.add_argument("--output-batch", default="", help="Optional resolved batch output path.")
    parser.add_argument("--target-count", type=int, default=0, help="Stop after resolving this many valid records; 0 means all candidates.")
    parser.add_argument("--require-abstract", action="store_true", help="Skip records without a non-empty abstract.")
    parser.add_argument("--no-insert", action="store_true", help="Write the resolved batch but do not insert into papers.json.")
    ns = parser.parse_args()

    work = Path(ns.work)
    library = Path(ns.library) if ns.library else work / "papers.json"
    candidates_path = Path(ns.candidates_json)
    bibliography_script = Path(ns.bibliography_script)
    output_batch = Path(ns.output_batch) if ns.output_batch else work / ".cache" / "scratch" / "metadata_resolved_batch.json"

    if not candidates_path.exists():
        print(f"ERROR: candidates JSON not found: {candidates_path}", file=sys.stderr)
        return 10
    if not bibliography_script.exists():
        print(f"ERROR: bibliography script not found: {bibliography_script}", file=sys.stderr)
        return 10

    candidates = load_candidates(candidates_path)
    resolved: list[dict[str, Any]] = []
    for candidate in candidates:
        record = resolve_candidate(candidate)
        if not record:
            continue
        if ns.require_abstract and not record.get("abstract"):
            warn(f"skip no abstract: {record.get('title')}")
            continue
        resolved.append(record)
        if ns.target_count and len(resolved) >= ns.target_count:
            break

    resolved = dedupe_records(resolved)
    output_batch.parent.mkdir(parents=True, exist_ok=True)
    output_batch.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")
    info(f"wrote resolved batch: {output_batch} ({len(resolved)} records)")

    if not resolved:
        print("ERROR: no valid records resolved from candidates", file=sys.stderr)
        return 11

    if ns.no_insert:
        return 0

    batch_json = json.dumps(resolved, ensure_ascii=False)
    insert_rc = run_command([
        sys.executable,
        str(bibliography_script),
        "insert",
        "--library",
        str(library),
        "--allow-create",
        "--skip-invalid",
    ], input_text=batch_json)
    if insert_rc != 0:
        return insert_rc

    validate_rc = run_command([
        sys.executable,
        str(bibliography_script),
        "validate",
        "--library",
        str(library),
    ])
    stats_rc = run_command([
        sys.executable,
        str(bibliography_script),
        "stats",
        "--library",
        str(library),
        "--limit",
        "40",
    ])
    return validate_rc or stats_rc


if __name__ == "__main__":
    raise SystemExit(main())
