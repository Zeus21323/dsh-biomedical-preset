"""Literature JSON library CLI for SurveyMaster (stdlib only).

Library file format:
  - Prefer a JSON array: [ {paper}, ... ]
  - Also readable: { "papers": [ ... ] } (converted to array on rewrite)

Paper objects should include at least bib_key (or auto-generated), title, author(s),
year, and publication venue (venue / journal / booktitle).

Examples:

  python3 scripts/bibliography_library.py \\
    insert --library "$LIB" --file batch.json --allow-create

  python3 scripts/bibliography_library.py \\
    stats --library "$LIB"

  python3 scripts/bibliography_library.py \\
    export-bib --library "$LIB" --output refs.bib

  python3 scripts/bibliography_library.py \\
    query --library "$LIB" --keys k1,k2 --format simplified --output "$CACHE/query.txt"

  python3 scripts/bibliography_library.py \\
    delete-keys --library "$LIB" --keys k_old --dry-run \\
    --scan-tex /path/work/sections \\
    --merge-warnings-report "$CACHE/del_warnings.txt"

Exit codes:
  0   OK
  1   warning / partial result (non-blocking)
  10  precondition failed (missing file, bad argument, I/O error)
  11  content/structure validation failed
  12  consistency failure
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

_HAS_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_RICH_TEXT_TAG_RE = re.compile(
    r"</?\s*(?:scp|i|italic|em|b|strong|sub|sup|span)\b[^>]*>",
    re.I,
)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9:_-]*\b[^>]*>")
_AUTHOR_PARTICLES = {
    "da",
    "de",
    "del",
    "della",
    "den",
    "der",
    "di",
    "du",
    "la",
    "le",
    "ten",
    "ter",
    "van",
    "von",
}

# Exit codes (shared across all SurveyMaster scripts)
E_WARN = 1       # non-blocking warnings
E_PRECOND = 10   # missing file / bad argument / I/O error
E_STRUCTURE = 11 # content/validation failure
E_CONSIST = 12   # duplicate key / consistency


def _fail(code: int, description: str, fix: str) -> None:
    print(f"[E{code}] {description}", file=sys.stderr)
    print(f"       Fix: {fix}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Serialize
# -----------------------------------------------------------------------------


def load_library(path: Path) -> tuple[list[dict[str, Any]], bool]:
    """Return papers list and whether caller should treat file as absent."""
    if not path.exists():
        return [], True
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw, False
    if isinstance(raw, dict) and isinstance(raw.get("papers"), list):
        return raw["papers"], False
    raise ValueError(f"{path}: expected JSON array or {{'papers': [...]}}.")


def save_library(path: Path, papers: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8")


# -----------------------------------------------------------------------------
# Similarity helpers (assist only)
# -----------------------------------------------------------------------------


def _jaro(sa: str, sb: str) -> float:
    if sa == sb:
        return 1.0
    len1, len2 = len(sa), len(sb)
    if not len1 or not len2:
        return 0.0
    match_distance = max(len1, len2) // 2 - 1
    match_distance = max(0, match_distance)

    m1 = [False] * len1
    m2 = [False] * len2
    matches = 0

    for i in range(len1):
        lo, hi = max(0, i - match_distance), min(i + match_distance + 1, len2)
        for j in range(lo, hi):
            if m2[j] or sa[i] != sb[j]:
                continue
            m1[i] = m2[j] = True
            matches += 1
            break

    if not matches:
        return 0.0

    trans = k = 0
    for i in range(len1):
        if not m1[i]:
            continue
        while not m2[k]:
            k += 1
        if sa[i] != sb[k]:
            trans += 1
        k += 1
    trans //= 2

    return (matches / len1 + matches / len2 + (matches - trans) / matches) / 3


def norm_title(title: Any) -> str:
    return re.sub(r"\s+", " ", str(title or "").lower().strip())


def jaro_winkler_similarity(a: Any, b: Any, *, p: float = 0.1) -> float:
    sa, sb = norm_title(a), norm_title(b)
    j = _jaro(sa, sb)
    prefix = 0
    mx = min(4, len(sa), len(sb))
    for i in range(mx):
        if sa[i] == sb[i]:
            prefix += 1
        else:
            break
    return min(1.0, j + prefix * p * (1 - j))


def norm_doi(doi: Any) -> str:
    s = str(doi or "").strip()
    if not s:
        return ""
    return re.sub(
        r"^https?://(dx\.)?doi\.org/",
        "",
        s,
        flags=re.I,
    ).lower()


def _norm_doi_url(url: Any) -> str:
    return norm_doi(url)


def _is_doi_url_for_doi(url: Any, doi: str) -> bool:
    s = str(url or "").strip()
    return bool(doi and re.match(r"^https?://(dx\.)?doi\.org/", s, flags=re.I) and _norm_doi_url(s) == doi)


def sanitize_rich_text_metadata(value: Any) -> Any:
    """Convert publisher/JATS HTML-ish metadata values to plain text."""
    if isinstance(value, list):
        return [sanitize_rich_text_metadata(v) for v in value]
    if isinstance(value, dict):
        return {k: sanitize_rich_text_metadata(v) for k, v in value.items()}
    if not isinstance(value, str):
        return value

    text = html.unescape(value)
    previous = None
    while previous != text:
        previous = text
        text = _RICH_TEXT_TAG_RE.sub("", text)
    # Drop any remaining simple markup tag from metadata fields. Metadata
    # exported to BibTeX/CSL should be plain text; formatting belongs to styles.
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\b([A-Za-z0-9][A-Za-z0-9.-]*)\s+\+(?=\s|$)", r"\1+", text)
    text = re.sub(r"([A-Za-z0-9])\s+([+\u207a])(?=\s)", r"\1\2", text)
    return text


def _format_author_for_bibtex(name: str) -> str:
    """Return a BibTeX-safe personal name.

    Search APIs often provide English names as ``Family I``.  BibTeX and
    citeproc interpret that as given-name first, which renders as ``I F``.
    Writing it as ``Family, I`` preserves the intended family name.
    """
    s = re.sub(r"\s+", " ", str(sanitize_rich_text_metadata(name) or "")).strip()
    if not s or "," in s or _HAS_CJK_RE.search(s):
        return s
    parts = s.split()
    if len(parts) == 2 and re.fullmatch(r"[A-Z]{1,4}", parts[1]):
        return f"{parts[0]}, {parts[1]}"
    for idx, part in enumerate(parts[1:-1], start=1):
        if part.lower() in _AUTHOR_PARTICLES and idx + 1 < len(parts):
            family = " ".join(parts[idx:])
            given = " ".join(parts[:idx])
            if given and family:
                return f"{family}, {given}"
    return s


def authors_str(p: dict[str, Any]) -> str:
    a = sanitize_rich_text_metadata(p.get("authors") or p.get("author") or "")
    if isinstance(a, list):
        cleaned = [
            _format_author_for_bibtex(re.sub(r"^and\s+", "", str(x).strip(), flags=re.IGNORECASE))
            for x in a
            if str(x).strip()
        ]
        return " and ".join(cleaned)
    # already a string — normalise comma/semicolon separators to BibTeX " and "
    s = str(a).strip()
    if " and " not in s and ("," in s or ";" in s):
        parts = re.split(r"\s*[,;]\s*", s)
        return " and ".join(_format_author_for_bibtex(p.strip()) for p in parts if p.strip())
    if " and " in s:
        return " and ".join(_format_author_for_bibtex(p.strip()) for p in re.split(r"\s+and\s+", s) if p.strip())
    return _format_author_for_bibtex(s)


def venue_str(p: dict[str, Any]) -> str:
    for k in ("venue", "journal", "booktitle", "proceedings", "publisher"):
        v = str(sanitize_rich_text_metadata(p.get(k)) or "").strip()
        if v:
            return v
    return ""


def _paper_key(p: dict[str, Any]) -> str:
    return str(p.get("bib_key") or "").strip()


def _paper_title(p: dict[str, Any]) -> str:
    return str(p.get("title") or p.get("paperTitle") or "(untitled)").strip()


def _paper_year(p: dict[str, Any]) -> str:
    return str(p.get("year") or p.get("publicationYear") or "n.d.").strip()


def _paper_relevance(p: dict[str, Any]) -> float:
    try:
        return float(p.get("relevance_score") or p.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _paper_abstract(p: dict[str, Any]) -> str:
    text = str(p.get("abstract") or p.get("paperAbstract") or p.get("summary") or "").strip()
    return re.sub(r"\s+", " ", text)


def _load_outline_entries(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        entries = raw.get("outline")
        if not isinstance(entries, list):
            entries = raw.get("sections")
        if isinstance(entries, list):
            return [x for x in entries if isinstance(x, dict)]
    raise ValueError(f"{path}: expected outline array or object with outline/sections")


def _outline_order(entry: dict[str, Any], pos: int) -> int:
    try:
        return int(entry.get("index", pos))
    except (TypeError, ValueError):
        return pos


def _is_top_level_section(entry: dict[str, Any]) -> bool:
    entry_type = str(entry.get("type") or "section").strip().lower()
    parent = entry.get("parent_index")
    return entry_type in {"", "section"} and parent in (None, "", 0, "0")


def _normalise_key_list(value: Any) -> list[str]:
    if value in (None, "", "all"):
        return []
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


_FIELD_ALIASES: dict[str, list[str]] = {
    # canonical: [aliases ...]
    "year":      ["publicationYear", "publicationDate", "pub_year", "pub_date",
                  "publishedYear", "date"],
    "authors":   ["authorList", "author_list", "authorNames"],
    "journal":   ["publicationEnName", "journalName", "journal_name",
                  "periodical", "source"],
    "booktitle": ["conference", "conferenceName", "conference_name",
                  "proceedings_name"],
    "abstract":  ["paperAbstract", "paper_abstract", "summary"],
    "doi":       ["paperDoi", "paper_doi"],
    "url":       ["paperUrl", "paper_url", "link", "pdfUrl", "pdf_url"],
    "title":     ["paperTitle", "paper_title"],
}

_YEAR_RE = re.compile(r"\b(\d{4})\b")
_UNUSED_RESULT_FIELDS = frozenset({
    "addFlag",
    "authorDetails",
    "goodFlag",
    "readFlag",
    "usage",
    "pdfFlag",
    "alltext",
})

_ARXIV_URL_RE = re.compile(r"\barxiv\.org/(?:abs|pdf)/|^arxiv:", re.I)
_PREPRINT_VENUE_RE = re.compile(r"^(?:arxiv|bioRxiv|medRxiv|chemRxiv|SSRN)(?:\b|$)", re.I)
_CONFERENCE_VENUE_RE = re.compile(
    r"\b("
    r"proceedings|conference|symposium|workshop|congress|meeting|"
    r"AAAI|IJCAI|ICML|NeurIPS|NIPS|ICLR|CVPR|ICCV|ECCV|ACL|EMNLP|NAACL|COLING|"
    r"SIGIR|SIGKDD|KDD|WWW|WSDM|CHI|UbiComp|UIST|SIGGRAPH|"
    r"ICSE|FSE|ASE|ISSTA|PLDI|OOPSLA|POPL|ASPLOS|MICRO|ISCA|"
    r"INFOCOM|SIGCOMM|MobiCom|MobiSys|SenSys|VLDB|SIGMOD|PODS|"
    r"IEEE/CVF|USENIX"
    r")\b",
    re.I,
)


def _canonical_entry_type(value: Any) -> str:
    typ = str(value or "").strip().lower()
    aliases = {
        "": "",
        "article-journal": "article",
        "journal-article": "article",
        "journal_article": "article",
        "paper-conference": "inproceedings",
        "conference": "inproceedings",
        "conference-paper": "inproceedings",
        "proceedings-article": "inproceedings",
        "webpage": "online",
        "web": "online",
        "post": "online",
        "post-weblog": "online",
        "preprint": "online",
        "archive": "online",
        "eprint": "online",
    }
    return aliases.get(typ, typ)


def infer_entry_type(p: dict[str, Any]) -> str:
    """Infer a BibTeX entry type when metadata did not provide one."""
    explicit = _canonical_entry_type(p.get("entry_type") or p.get("bibtex_type") or p.get("type"))
    urlish = " ".join(str(p.get(k) or "") for k in ("url", "link", "doi", "arxiv_id", "source"))
    venueish = " ".join(
        str(p.get(k) or "") for k in ("journal", "booktitle", "venue", "proceedings", "publisher", "venue_hint")
    )
    if str(p.get("booktitle") or p.get("conference") or p.get("conferenceName") or p.get("proceedings") or "").strip():
        return "inproceedings"
    if _CONFERENCE_VENUE_RE.search(venueish):
        return "inproceedings"
    if _PREPRINT_VENUE_RE.search(venueish):
        return "online"
    if _ARXIV_URL_RE.search(urlish) and not venueish.strip():
        return "online"
    if explicit and explicit not in {"section"}:
        return explicit

    return "article"


def strip_unused_result_fields(p: dict[str, Any]) -> dict[str, Any]:
    """Drop high-volume PaperSearch fields that are not used by the library."""
    out = {k: v for k, v in p.items() if k not in _UNUSED_RESULT_FIELDS}
    if out.get("abstract") and out.get("abstractZh"):
        out.pop("abstractZh", None)
    return out


def normalize_paper_fields(p: dict[str, Any]) -> dict[str, Any]:
    """Map common search-API field aliases to canonical library field names.

    Called on every incoming record before validation so callers do not need
    to manually rename fields from PaperSearch / PaperLookupByDoi results.
    Canonical field already present is never overwritten.
    """
    out = sanitize_rich_text_metadata(strip_unused_result_fields(p))
    for canonical, aliases in _FIELD_ALIASES.items():
        if out.get(canonical):
            continue  # canonical already set
        for alias in aliases:
            val = out.get(alias)
            if val is None or val == "":
                continue
            # For year: if the value is a date string, extract the 4-digit year.
            if canonical == "year":
                m = _YEAR_RE.search(str(val))
                out[canonical] = m.group(1) if m else str(val)
            else:
                out[canonical] = val
            break  # first alias wins; keep alias key for transparency
    if not str(out.get("entry_type") or "").strip():
        out["entry_type"] = infer_entry_type(out)
    elif _canonical_entry_type(out.get("entry_type")) != str(out.get("entry_type")).strip().lower():
        out["entry_type"] = _canonical_entry_type(out.get("entry_type"))
    if out.get("entry_type") == "inproceedings" and not str(out.get("booktitle") or "").strip():
        for source_key in ("conference", "conferenceName", "proceedings", "venue", "journal"):
            val = str(out.get(source_key) or "").strip()
            if val:
                out["booktitle"] = val
                break
    return out


_RICH_TEXT_FIELDS = {"abstract", "paperAbstract", "paper_abstract", "summary"}
_AUTHOR_FIELDS = {"author", "authors"}


def _information_length(value: Any) -> int:
    return len(re.sub(r"\s+", " ", str(value or "")).strip())


def _author_information_length(value: Any) -> int:
    if isinstance(value, list):
        return sum(_information_length(v) for v in value)
    return _information_length(value)


def _is_article_identifier(value: str) -> bool:
    """Return True for article ids that should not be emitted as page ranges."""
    s = str(value or "").strip()
    return bool(s and re.search(r"[A-Za-z]", s))


def merge_record(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge records without replacing rich abstracts with shorter text."""
    merged = dict(existing)
    for k, v in incoming.items():
        if v is None or v == "":
            continue
        if k in _RICH_TEXT_FIELDS and _information_length(v) < _information_length(merged.get(k)):
            continue
        if k in _AUTHOR_FIELDS and _author_information_length(v) < _author_information_length(merged.get(k)):
            continue
        merged[k] = v
    return merged


def find_title_duplicate_index(
    lib: list[dict[str, Any]], rec: dict[str, Any], threshold: float
) -> int | None:
    if not rec.get("title"):
        return None
    d = norm_doi(rec.get("doi"))
    for ix, other in enumerate(lib):
        if not other.get("title"):
            continue
        same_doi = d and norm_doi(other.get("doi")) == d
        if same_doi:
            continue
        if jaro_winkler_similarity(rec["title"], other["title"]) >= threshold:
            return ix
    return None


def ensure_bib_key(p: dict[str, Any]) -> dict[str, Any]:
    q = dict(p)
    if str(q.get("bib_key") or "").strip():
        return q
    yr = str(q.get("year") or "").strip()
    ys = "".join(filter(str.isdigit, yr))
    yt = ys[-4:] if len(ys) >= 4 else (ys.zfill(4) if ys else "0000")
    auth_src = authors_str(q) or "anon"
    first = auth_src.replace("\\", "").split(",")[0]
    first = re.split(r"\band\b|\\&|,|;", first)[0].strip()
    slug = re.sub(r"[^\w\d]+", "", first.lower())[:20] or "paper"
    q["bib_key"] = slug + yt
    return q


def validate_record(p: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return errors (blocking) and warnings (non-blocking)."""
    errs: list[str] = []
    warns: list[str] = []

    if not str(p.get("title") or "").strip():
        errs.append("missing_title")
    if not authors_str(p):
        errs.append("missing_author")
    if not venue_str(p):
        errs.append("missing_publication_venue")
    yr = str(p.get("year") or "").strip()
    if not yr:
        errs.append("missing_year")
    elif not re.fullmatch(r"\d{4}", yr):
        warns.append("year_not_four_digits")

    if not norm_doi(p.get("doi")):
        warns.append("missing_doi")

    # volume / pages / number — important for journal/conference BibTeX quality.
    # Only warn for entry types where these fields are expected.
    entry_type = str(p.get("entry_type") or "article").strip().lower()
    if entry_type in ("article", "inproceedings", "conference", ""):
        if not str(p.get("volume") or "").strip():
            warns.append("missing_volume")
        if not str(p.get("pages") or "").strip() and not str(p.get("number") or "").strip():
            warns.append("missing_pages_and_number")

    for opt in ("url",):
        if not str(p.get(opt) or "").strip():
            warns.append(f"missing_optional_{opt}")

    return errs, warns


def rich_abstract_text(p: dict[str, Any], min_chars: int = 300) -> str:
    for key in ("abstract", "summary", "paperAbstract"):
        value = p.get(key)
        if isinstance(value, str):
            text = re.sub(r"\s+", " ", value).strip()
            if len(text) >= min_chars:
                return text
    return ""


# LaTeX text-mode special characters that must be escaped inside BibTeX
# *text* field values (title/author/journal/booktitle/venue/volume/number/pages).
# Do NOT apply to doi/url fields — those are rendered via \url{} by the
# bibliography style, which manages catcodes internally.
# $ is not in this map — it is the math-mode delimiter and must be preserved.
_LATEX_FIELD_SPECIALS: dict[str, str] = {
    "&": r"\&",
    "_": r"\_",
    "%": r"\%",
    "#": r"\#",
}


def _escape_bib_field(value: str) -> str:
    """Escape LaTeX-special chars in a BibTeX text field value.

    Applies to plain-text fields (title, author, journal, booktitle, venue,
    volume, number, pages). Do NOT call this on doi/url fields — those are
    rendered via \\url{} in .bst styles which manages catcodes internally.

    Dollar-sign handling:
    - Even count of unescaped ``$`` → treat as paired math-mode delimiters;
      characters inside ``$...$`` are not escaped.
    - Odd count → cannot form valid pairs (e.g. ``$24.5 /$cm$``); all bare
      ``$`` are escaped to ``\\$`` and the whole value is treated as text.
    Already-escaped sequences (e.g. ``\\$``, ``\\_``) are left untouched.
    """
    unescaped_dollar_count = sum(
        1 for i, ch in enumerate(value)
        if ch == "$" and (i == 0 or value[i - 1] != "\\")
    )
    escape_dollar = (unescaped_dollar_count % 2 == 1)

    result: list[str] = []
    in_math = False
    i = 0
    while i < len(value):
        ch = value[i]
        already_escaped = i > 0 and value[i - 1] == "\\"
        if ch == "$" and not already_escaped:
            if escape_dollar:
                result.append(r"\$")
            else:
                in_math = not in_math
                result.append(ch)
        elif ch in _LATEX_FIELD_SPECIALS and not in_math and not already_escaped:
            result.append(_LATEX_FIELD_SPECIALS[ch])
        else:
            result.append(ch)
        i += 1
    return "".join(result)


def _count_unescaped_dollars(s: str, start: int, end: int) -> int:
    """Count bare ``$`` (not preceded by ``\\``) in s[start:end]."""
    return sum(
        1 for j in range(start, end)
        if s[j] == "$" and (j == 0 or s[j - 1] != "\\")
    )


def _escape_raw_bibtex(raw: str) -> str:
    """Escape LaTeX-special chars inside field values of a raw BibTeX entry.

    Only touches characters that appear inside a field value (brace depth
    >= 2, i.e. inside ``field = { ... }``), leaving structural characters
    such as ``@type{key,`` untouched. Skips any occurrence already preceded
    by a backslash to avoid double-escaping (e.g. ``\\_`` stays ``\\_``).

    Dollar-sign handling mirrors _escape_bib_field: for each field value
    (the outermost ``{ ... }`` block), count unescaped ``$``.  Even count →
    math-mode pairs are preserved and their contents not escaped.  Odd count
    → all bare ``$`` in that value are escaped to ``\\$``.
    """
    result: list[str] = []
    i = 0
    depth = 0
    in_math = False
    # escape_dollar is set per top-level field value (depth transition 1→2)
    escape_dollar = False
    field_value_start = -1

    while i < len(raw):
        ch = raw[i]
        if ch == "{":
            depth += 1
            result.append(ch)
            if depth == 2:
                # entering a field value — find matching closing brace to pre-scan
                field_value_start = i + 1
                close = field_value_start
                d = 1
                while close < len(raw) and d > 0:
                    if raw[close] == "{":
                        d += 1
                    elif raw[close] == "}":
                        d -= 1
                    close += 1
                field_value_end = close - 1
                escape_dollar = _count_unescaped_dollars(raw, field_value_start, field_value_end) % 2 == 1
                in_math = False
        elif ch == "}":
            depth = max(depth - 1, 0)
            result.append(ch)
            if depth < 2:
                in_math = False
                escape_dollar = False
        elif ch == "$" and depth >= 2:
            already_escaped = i > 0 and raw[i - 1] == "\\"
            if already_escaped:
                result.append(ch)
            elif escape_dollar:
                result.append(r"\$")
            else:
                in_math = not in_math
                result.append(ch)
        elif ch in _LATEX_FIELD_SPECIALS and depth >= 2 and not in_math:
            if i == 0 or raw[i - 1] != "\\":
                result.append(_LATEX_FIELD_SPECIALS[ch])
            else:
                result.append(ch)
        else:
            result.append(ch)
        i += 1
    return "".join(result)


# Long-URL handling for BibTeX export.
# Some publisher / vendor / preprint URLs (encoded session links, signed
# CDN URLs, etc.) easily exceed several hundred characters and overflow
# BibTeX line wrapping while adding no navigational value when a DOI
# already resolves to the same paper. Above the threshold below the URL
# is replaced with the canonical https://doi.org/<doi> form, or dropped
# entirely if no DOI exists.
_MAX_BIB_URL_LENGTH = 150

_RAW_URL_FIELD_RE = re.compile(
    r"^([ \t]*)url(\s*=\s*)\{([^}]*)\}([ \t]*,?[ \t]*\n?)",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _shorten_long_url(url: str, doi: str, bib_key: str = "") -> str | None:
    """Apply the long-URL policy to a single URL value.

    Returns the URL string that should be written to BibTeX, or ``None``
    to signal the caller to drop the field.

    - DOI resolver URLs that duplicate the DOI field → dropped.
    - ``len(url) <= _MAX_BIB_URL_LENGTH`` → original URL returned unchanged.
    - Otherwise, if a DOI is available → ``https://doi.org/<doi>``.
    - Otherwise → ``None`` (caller drops the url field).
    """
    if _is_doi_url_for_doi(url, doi):
        return None
    if len(url) <= _MAX_BIB_URL_LENGTH:
        return url
    key_label = bib_key or "(unknown_key)"
    if doi:
        print(
            f"INFO {key_label}: url length {len(url)} > {_MAX_BIB_URL_LENGTH}; "
            f"replaced with DOI URL",
            file=sys.stderr,
        )
        return f"https://doi.org/{doi}"
    print(
        f"WARN {key_label}: url length {len(url)} > {_MAX_BIB_URL_LENGTH} and no DOI; "
        f"url field dropped from BibTeX",
        file=sys.stderr,
    )
    return None


def _patch_long_url_in_raw_bibtex(raw: str, doi: str, bib_key: str = "") -> str:
    """Apply the long-URL policy to a pre-built raw BibTeX entry string.

    Operates per-line on ``url = {...}`` field assignments. When the policy
    drops the URL, the entire field line (including indent and trailing
    comma/newline) is removed so the surrounding entry stays well-formed.
    """

    def _replace(match: re.Match) -> str:
        url_val = match.group(3).strip()
        shortened = _shorten_long_url(url_val, doi, bib_key)
        if shortened is None:
            return ""
        if shortened == url_val:
            return match.group(0)
        indent, sep, tail = match.group(1), match.group(2), match.group(4)
        return f"{indent}url{sep}{{{shortened}}}{tail}"

    return _RAW_URL_FIELD_RE.sub(_replace, raw)


def _bohr_metadata_fields(p: dict[str, Any]) -> list[tuple[str, str]]:
    bohr_date = str(p.get("publicationDate") or "").strip()
    pid = str(p.get("paperId") or p.get("paper_id") or "").strip()
    pubid = p.get("publicationId") or p.get("publication_id")
    meta: dict[str, Any] = {}
    if pid:
        meta["paperId"] = pid
    if pubid is not None:
        meta["publicationId"] = pubid
    if p.get("journalLanguage") == "chinese":
        meta["isZhJournal"] = True
    return [
        ("bohrDate", bohr_date),
        ("bohrinternal", json.dumps(meta, ensure_ascii=False)),
    ]


def _strip_raw_bibtex_field(raw: str, field: str) -> str:
    return re.sub(
        rf"\s*{re.escape(field)}\s*=\s*\{{[^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)?\}},?",
        "",
        raw,
        flags=re.IGNORECASE,
    )


def _strip_article_identifier_pages_in_raw(raw: str) -> str:
    match = re.search(r"\bpages\s*=\s*\{([^{}]*)\}", raw, flags=re.IGNORECASE)
    if match and _is_article_identifier(match.group(1)):
        return _strip_raw_bibtex_field(raw, "pages")
    return raw


def _inject_raw_bibtex_fields(raw: str, fields: list[tuple[str, str]]) -> str:
    raw = raw.rstrip()
    if not raw.endswith("}"):
        return raw
    additions = "".join(f"\n  {name} = {{{value}}}," for name, value in fields)
    return raw[:-1].rstrip().rstrip(",") + f",{additions}\n}}"


def _rewrite_raw_bibtex_type(raw: str, entry_type: str) -> str:
    if entry_type not in {"online", "inproceedings"}:
        return raw
    return re.sub(r"^@\w+(\s*\{)", f"@{entry_type}\\1", raw, count=1, flags=re.S)


_RAW_TEXT_FIELDS_TO_SANITIZE = {"title", "journal", "booktitle", "author", "organization", "publisher"}
_RAW_TEXT_FIELD_START_RE = re.compile(
    r"(?i)\b(title|journal|booktitle|author|organization|publisher)\s*=\s*\{"
)


def _sanitize_raw_bibtex_text_fields(raw: str) -> str:
    """Sanitize HTML/JATS markup inside selected raw BibTeX field values."""
    result: list[str] = []
    pos = 0
    while True:
        match = _RAW_TEXT_FIELD_START_RE.search(raw, pos)
        if not match:
            result.append(raw[pos:])
            break
        value_start = match.end()
        depth = 1
        i = value_start
        while i < len(raw) and depth > 0:
            if raw[i] == "{" and (i == 0 or raw[i - 1] != "\\"):
                depth += 1
            elif raw[i] == "}" and (i == 0 or raw[i - 1] != "\\"):
                depth -= 1
            i += 1
        if depth != 0:
            result.append(raw[pos:])
            break
        value_end = i - 1
        result.append(raw[pos:value_start])
        result.append(str(sanitize_rich_text_metadata(raw[value_start:value_end])))
        result.append(raw[value_end:i])
        pos = i
    return "".join(result)


def _clean_bib_text(value: Any) -> str:
    return str(sanitize_rich_text_metadata(value) or "").strip()


def build_minimal_bibtex(p: dict[str, Any]) -> str:
    _bib_key_for_log = str(p.get("bib_key") or "").strip()
    _doi_for_url_policy = norm_doi(p.get("doi"))
    typ = infer_entry_type(p)
    raw = str(p.get("bibtex") or "").strip()
    if raw:
        # Apply URL-length policy BEFORE LaTeX-escaping so length is measured
        # on the original URL characters, not on \_ / \& escape sequences.
        raw = _rewrite_raw_bibtex_type(raw, typ)
        raw = _sanitize_raw_bibtex_text_fields(raw)
        raw = _patch_long_url_in_raw_bibtex(raw, _doi_for_url_policy, _bib_key_for_log)
        raw = _strip_article_identifier_pages_in_raw(raw)
        raw = _escape_raw_bibtex(raw)
        # Strip any existing note field from the pre-built bibtex string
        raw = re.sub(r"\s*note\s*=\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\},?", "", raw)
        for _field_name, _ in _bohr_metadata_fields(p):
            raw = _strip_raw_bibtex_field(raw, _field_name)
        raw = _inject_raw_bibtex_fields(raw, _bohr_metadata_fields(p))
        return raw if raw.endswith("\n") else raw + "\n"

    key = str(p.get("bib_key") or "unknown").strip().replace(" ", "_")
    title = _escape_bib_field(_clean_bib_text(p.get("title")))
    auth = _escape_bib_field(authors_str(p))
    venue = _escape_bib_field(_clean_bib_text(venue_str(p)))
    yr = str(p.get("year") or "").strip() or "????"
    lines = [
        f"@{typ}{{{key},",
        f"  title = {{{{{title}}}}},",
        f"  author = {{{auth}}},",
    ]
    j = _escape_bib_field(_clean_bib_text(p.get("journal")))
    bt = _escape_bib_field(_clean_bib_text(p.get("booktitle")))
    if typ == "inproceedings":
        proceedings = bt or venue or j
        if proceedings:
            lines.append(f"  booktitle = {{{proceedings}}},")
    elif typ == "online":
        organization = venue or j or bt
        if organization:
            lines.append(f"  organization = {{{organization}}},")
    elif j:
        lines.append(f"  journal = {{{j}}},")
    elif bt:
        lines.append(f"  booktitle = {{{bt}}},")
    elif venue:
        lines.append(f"  journal = {{{venue}}},")
    lines.append(f"  year = {{{yr}}},")
    for fld in ("volume", "number", "pages"):
        v = _escape_bib_field(_clean_bib_text(p.get(fld)))
        if fld == "pages" and _is_article_identifier(v):
            continue
        if v:
            lines.append(f"  {fld} = {{{v}}},")
    d = norm_doi(p.get("doi"))
    if d:
        lines.append(f"  doi = {{{d}}},")
    for _field_name, _field_value in _bohr_metadata_fields(p):
        lines.append(f"  {_field_name} = {{{_field_value}}},")
    final_url: str | None = None
    for ukey in ("url", "link"):
        u = str(p.get(ukey) or "").strip()
        if not u:
            continue
        final_url = _shorten_long_url(u, _doi_for_url_policy, _bib_key_for_log)
        if final_url:
            break
    if final_url:
        lines.append(f"  url = {{{final_url}}},")
    lines.append("}\n")
    return "\n".join(lines)


_CITE_RE = re.compile(r"\\(?:cite|citep|citet|citealp|citealt|Citep|Citet)(?:\[[^\]]*\]){0,2}\{(?P<body>[^\}]+)\}")
# Matches standard \bibitem[opt]{key} and apacite's multiline \bibitem [...] {% key} form.
_BBL_BIBITEM_RE = re.compile(r"\\bibitem\s*(?:\[[\s\S]*?\]\s*)?\{\s*(?P<key>[\s\S]*?)\s*\}", re.M)


def _normalize_bbl_key(raw_key: str) -> str:
    return re.sub(r"\s+", "", raw_key.replace("%", "")).strip()


def cite_keys_from_bbl(bbl_path: Path) -> list[str]:
    """Return cite keys in the order they appear in a .bbl file (= final reference list order)."""
    seen: set[str] = set()
    result: list[str] = []
    text = bbl_path.read_text(encoding="utf-8", errors="replace")
    for m in _BBL_BIBITEM_RE.finditer(text):
        k = _normalize_bbl_key(m.group("key"))
        if k and k not in seen:
            seen.add(k)
            result.append(k)
    return result


def cite_keys_in_tree(root: Path) -> set[str]:
    keys: set[str] = set()
    if not root.exists():
        return keys
    for p in root.rglob("*.tex"):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _CITE_RE.finditer(text):
            for part in m.group("body").split(","):
                k = part.strip()
                if k:
                    keys.add(k)
    return keys


def cite_keys_from_tex_file(tex_path: Path) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    for m in _CITE_RE.finditer(text):
        for part in m.group("body").split(","):
            k = part.strip()
            if k and k not in seen:
                seen.add(k)
                result.append(k)
    return result


def _index_maps(lib: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    by_key: dict[str, int] = {}
    by_doi: dict[str, int] = {}
    for i, p in enumerate(lib):
        bk = str(p.get("bib_key") or "").strip()
        if bk:
            by_key[bk] = i
        d = norm_doi(p.get("doi"))
        if d:
            by_doi[d] = i
    return by_key, by_doi


def dedupe_library(lib: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    by_key: dict[str, int] = {}
    by_doi: dict[str, int] = {}

    for rec in lib:
        rec = ensure_bib_key(dict(rec))
        bk = str(rec.get("bib_key") or "").strip()
        d = norm_doi(rec.get("doi"))

        ix: int | None = None
        if bk and bk in by_key:
            ix = by_key[bk]
        elif d and d in by_doi:
            ix = by_doi[d]
        else:
            ix = find_title_duplicate_index(deduped, rec, threshold)

        if ix is None:
            deduped.append(rec)
        else:
            deduped[ix] = ensure_bib_key(merge_record(deduped[ix], rec))

        by_key, by_doi = _index_maps(deduped)

    return deduped


def cmd_insert(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    try:
        lib, absent = load_library(path)
    except (ValueError, json.JSONDecodeError) as exc:
        _fail(E_PRECOND, str(exc), "check library file path and JSON syntax")
        return E_PRECOND

    if absent and not ns.allow_create:
        _fail(E_PRECOND, f"library not found: {path}", "pass --allow-create to start a new JSON array")
        return E_PRECOND

    if ns.file:
        incoming = json.loads(Path(ns.file).read_text(encoding="utf-8"))
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            _fail(E_PRECOND, "no input data", "pass --file <batch.json> or pipe JSON on stdin")
            return E_PRECOND
        incoming = json.loads(raw)

    if isinstance(incoming, dict):
        items = [incoming]
    elif isinstance(incoming, list):
        items = incoming
    else:
        _fail(E_PRECOND, "inserted JSON must be object or array", "check the input format")
        return E_PRECOND

    by_key, by_doi = _index_maps(lib)
    th = float(ns.title_similarity_alert)

    for rec in items:
        rec = ensure_bib_key(normalize_paper_fields(dict(rec)))
        errs, warns = validate_record(rec)
        for w in warns:
            print(f"WARN {rec['bib_key']}: {w}", file=sys.stderr)
        if errs:
            msg = ",".join(errs)
            _fail(E_STRUCTURE, f"{rec['bib_key']}: {msg}",
                  "fix required fields (title, authors, year) before inserting; or pass --skip-invalid")
            if ns.skip_invalid:
                continue
            return E_STRUCTURE

        d = norm_doi(rec.get("doi"))
        bk = str(rec["bib_key"]).strip()

        if bk in by_key:
            print(f"INFO: merge bib_key duplicate {bk}", file=sys.stderr)
            ix = by_key[bk]
            merged = merge_record(lib[ix], rec)
            lib[ix] = ensure_bib_key(merged)
            continue
        if d and d in by_doi:
            print(f"INFO: merge DOI duplicate {d}", file=sys.stderr)
            ix = by_doi[d]
            merged = merge_record(lib[ix], rec)
            lib[ix] = ensure_bib_key(merged)
            continue

        ix = find_title_duplicate_index(lib, rec, th)
        if ix is not None:
            lib[ix] = ensure_bib_key(merge_record(lib[ix], rec))
            by_key, by_doi = _index_maps(lib)
            continue

        lib.append(rec)
        by_key, by_doi = _index_maps(lib)

    lib = dedupe_library(lib, th)
    save_library(path, lib)
    print(f"OK: saved {len(lib)} papers to {path.resolve()}")
    return 0


def cmd_stats(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _abs = load_library(path)
    lines = [
        f"count={len(lib)}",
        f"path={path.resolve()}",
        "core_entries:",
    ]
    for p in sorted(lib, key=lambda x: str(x.get("bib_key") or ""))[: int(ns.limit)]:
        bk = str(p.get("bib_key") or "")
        title = str(p.get("title") or "")[:80]
        ys = str(p.get("year") or "")
        v = venue_str(p)[:40]
        lines.append(f"  - {bk} | {ys} | {v} | {title}")
    if len(lib) > int(ns.limit):
        lines.append(f"  ... {len(lib) - int(ns.limit)} more (--limit)")
    text = "\n".join(lines) + "\n"
    if ns.output:
        Path(ns.output).write_text(text, encoding="utf-8")
        print(f"OK: stats -> {Path(ns.output).resolve()}")
    else:
        print(text, end="")
    return 0


def cmd_abstract_coverage(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)
    min_chars = int(ns.min_chars)
    min_count = int(ns.min_count)
    rich = [p for p in lib if rich_abstract_text(p, min_chars=min_chars)]
    missing = [p for p in lib if not rich_abstract_text(p, min_chars=min_chars)]
    lines = [
        f"path={path.resolve()}",
        f"records={len(lib)}",
        f"rich_abstract_min_chars={min_chars}",
        f"rich_abstract_count={len(rich)}",
        f"missing_or_short_count={len(missing)}",
        "rich_keys=" + ",".join(str(p.get("bib_key") or "") for p in rich if p.get("bib_key")),
    ]
    if missing:
        lines.append(
            "missing_or_short_keys="
            + ",".join(str(p.get("bib_key") or "") for p in missing[: int(ns.limit)] if p.get("bib_key"))
        )
    text = "\n".join(lines) + "\n"
    if ns.output:
        Path(ns.output).write_text(text, encoding="utf-8")
        print(f"OK: abstract coverage -> {Path(ns.output).resolve()}")
    else:
        print(text, end="")
    if len(rich) < min_count and not ns.warn_only:
        _fail(
            E_STRUCTURE,
            f"rich abstract coverage too low: {len(rich)} < {min_count}",
            "retry abstract supplementation once; if still below threshold, ask the user before Stage 3",
        )
        return E_STRUCTURE
    return 0


def _find_keys(lib: list[dict[str, Any]], want: list[str]) -> list[dict[str, Any]]:
    m = {str(p.get("bib_key") or ""): p for p in lib}
    out: list[dict[str, Any]] = []
    for k in want:
        if k in m:
            out.append(m[k])
        else:
            print(f"WARN: missing bib_key in library: {k}", file=sys.stderr)
    return out


def cmd_query(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)
    keys = [k.strip() for k in ns.keys.split(",") if k.strip()]
    recs = _find_keys(lib, keys)
    mode = ns.format.replace("-", "")
    chunks: list[str] = []

    def fmt_detail(p: dict[str, Any]) -> str:
        return json.dumps(p, ensure_ascii=False, indent=2)

    def fmt_simple(p: dict[str, Any]) -> str:
        abstract = str(p.get("abstract") or "")
        if len(abstract) > 500:
            abstract = abstract[:500] + "..."
        return (
            f"bib_key={p.get('bib_key')} year={p.get('year')} "
            f"venue={venue_str(p)[:120]}\ntitle={p.get('title')}\nauthors={authors_str(p)}\n"
            f"doi={norm_doi(p.get('doi'))}\nabstract={abstract}\n---\n"
        )

    for p in recs:
        chunks.append(fmt_detail(p) if mode == "detailed" else fmt_simple(p))
    body = "".join(chunks)
    outp = Path(ns.output) if ns.output else None
    if outp:
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(body, encoding="utf-8")
        print(f"OK: wrote {len(recs)} record(s) to {outp.resolve()}")
    else:
        sys.stdout.write(body)
    return 0


def cmd_build_write_context(ns: argparse.Namespace) -> int:
    """Build compact paper context for one-pass mainbody writing."""
    papers, absent = load_library(Path(ns.library))
    entries = _load_outline_entries(Path(ns.outline))
    sections = [
        entry for pos, entry in enumerate(entries, 1)
        if _is_top_level_section(entry)
    ]
    sections.sort(key=lambda e: _outline_order(e, 0))

    paper_by_key = {_paper_key(p): p for p in papers if _paper_key(p)}
    all_keys = sorted(
        paper_by_key,
        key=lambda k: (-_paper_relevance(paper_by_key[k]), k),
    )

    index_limit = max(0, int(ns.index_limit))
    indexed_keys = all_keys if index_limit == 0 else all_keys[:index_limit]

    section_rows: list[tuple[str, list[str], list[str]]] = []
    snippet_candidates: list[str] = []
    for entry in sections:
        title = str(entry.get("title") or f"section_{entry.get('index', len(section_rows) + 1)}").strip()
        raw_paper_ids = entry.get("paper_ids")
        allowed = _normalise_key_list(raw_paper_ids)
        if not allowed:
            allowed = all_keys
        else:
            allowed = [k for k in allowed if k in paper_by_key]
        key_papers = [k for k in _normalise_key_list(entry.get("key_papers")) if k in paper_by_key]
        section_rows.append((title, allowed, key_papers))
        snippet_candidates.extend(key_papers)

    if ns.snippet_source == "assigned":
        snippet_candidates = [k for _, allowed, _ in section_rows for k in allowed]
    elif ns.snippet_source == "none":
        snippet_candidates = []

    deduped_snippets: list[str] = []
    seen: set[str] = set()
    for key in snippet_candidates:
        if key in seen:
            continue
        seen.add(key)
        deduped_snippets.append(key)
    deduped_snippets.sort(key=lambda k: (-_paper_relevance(paper_by_key[k]), k))
    snippet_limit = max(0, int(ns.snippet_limit))
    if snippet_limit:
        deduped_snippets = deduped_snippets[:snippet_limit]

    abstract_chars = max(0, int(ns.abstract_chars))
    lines: list[str] = []
    lines.append("### Global paper index")
    if absent or not indexed_keys:
        lines.append("(no papers available)")
    else:
        for key in indexed_keys:
            paper = paper_by_key[key]
            lines.append(
                f"[{key}] {_paper_title(paper)} · {_paper_year(paper)} · {venue_str(paper) or 'n/a'}"
            )

    lines.append("")
    lines.append("### Section citation map")
    if not section_rows:
        lines.append("(no writable sections)")
    else:
        for title, allowed, key_papers in section_rows:
            allowed_text = ",".join(allowed) if allowed else ""
            key_text = ",".join(key_papers) if key_papers else ""
            lines.append(f"{title}: allowed_keys=[{allowed_text}]; key_papers=[{key_text}]")

    lines.append("")
    lines.append("### Key paper evidence snippets")
    if not deduped_snippets or abstract_chars == 0:
        lines.append("(no snippets)")
    else:
        for key in deduped_snippets:
            abstract = _paper_abstract(paper_by_key[key])[:abstract_chars]
            if abstract:
                lines.append(f"[{key}] {abstract}")

    output = "\n".join(lines) + "\n"
    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(
            "WRITE_CONTEXT_RESULT "
            f"papers={len(paper_by_key)} sections={len(section_rows)} "
            f"snippets={len(deduped_snippets)} output={out_path}"
        )
    else:
        sys.stdout.write(output)
    return 0


def cmd_export_bib(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)
    diagnostics = sys.stdout if getattr(ns, "diagnostics_stdout", False) else sys.stderr
    if getattr(ns, "bbl_file", "") and Path(ns.bbl_file).exists():
        # Derive cited keys from .bbl (authoritative: final reference list order after bibtex)
        ordered_keys = cite_keys_from_bbl(Path(ns.bbl_file))
        lib_index = {str(p.get("bib_key") or "").strip(): p for p in lib}
        missing_keys = [k for k in ordered_keys if k not in lib_index]
        if missing_keys:
            _fail(E_STRUCTURE,
                  f"{len(missing_keys)} bbl key(s) not found in library: {missing_keys[:10]}{'...' if len(missing_keys) > 10 else ''}",
                  "insert missing papers into papers.json before rebuilding references.bib")
            return E_STRUCTURE
        recs = [lib_index[k] for k in ordered_keys]
        uncited = len(lib) - len(recs)
        if uncited:
            print(f"INFO: {uncited} library entries not cited — excluded from export", file=diagnostics)
    elif getattr(ns, "tex_file", ""):
        tex_path = Path(ns.tex_file)
        if not tex_path.exists():
            _fail(E_PRECOND, f"tex file not found: {tex_path}", "pass an existing --tex-file or omit it")
            return E_PRECOND
        ordered_keys = cite_keys_from_tex_file(tex_path)
        lib_index = {str(p.get("bib_key") or "").strip(): p for p in lib}
        missing_keys = [k for k in ordered_keys if k not in lib_index]
        if missing_keys:
            _fail(E_STRUCTURE,
                  f"{len(missing_keys)} tex cite key(s) not found in library: {missing_keys[:10]}{'...' if len(missing_keys) > 10 else ''}",
                  "insert missing papers into papers.json before exporting references.bib")
            return E_STRUCTURE
        recs = [lib_index[k] for k in ordered_keys]
        uncited = len(lib) - len(recs)
        if uncited:
            print(f"INFO: {uncited} library entries not cited — excluded from export", file=diagnostics)
    elif ns.keys.strip():
        want = [k.strip() for k in ns.keys.split(",") if k.strip()]
        recs = _find_keys(lib, want)
    else:
        recs = lib
        
    # --- Enrich records with paperId/publicationId from paper-results ---
    _paper_results_dir = Path("/bohr-workspace/paper-results")
    if _paper_results_dir.is_dir():
        _doi_map: dict[str, dict[str, Any]] = {}
        _title_map: dict[str, dict[str, Any]] = {}
        for _f in _paper_results_dir.glob("*.json"):
            try:
                _papers = json.loads(_f.read_text(encoding="utf-8"))
                if isinstance(_papers, dict):
                    _papers = _papers.get("papers", [_papers])
                if not isinstance(_papers, list):
                    continue
                for _p in _papers:
                    if not isinstance(_p, dict):
                        continue
                    _pid = str(_p.get("paperId") or "").strip()
                    _pubid = _p.get("publicationId")
                    if not _pid and _pubid is None:
                        continue
                    _meta = {}
                    if _pid:
                        _meta["paperId"] = _pid
                    if _pubid is not None:
                        _meta["publicationId"] = _pubid
                    _d = norm_doi(_p.get("doi"))
                    if _d:
                        _doi_map[_d] = _meta
                    _t = str(_p.get("title") or "").strip().lower()
                    if _t:
                        _title_map[_t] = _meta
            except Exception:
                continue
        # Enrich library records
        for _rec in recs:
            if _rec.get("paperId") or _rec.get("paper_id"):
                continue  # already has paperId
            _d = norm_doi(_rec.get("doi"))
            _matched = _doi_map.get(_d) if _d else None
            if not _matched:
                _t = str(_rec.get("title") or "").strip().lower()
                _matched = _title_map.get(_t)
            if _matched:
                for _k, _v in _matched.items():
                    if _k not in _rec:
                        _rec[_k] = _v
    # --- End enrichment ---

    had_error = False
    missing_volume_keys: list[str] = []
    missing_pages_keys: list[str] = []
    blocking_missing_biblio_keys: list[str] = []
    other_warn_groups: dict[str, list[str]] = {}
    for rec in recs:
        checked = ensure_bib_key(dict(rec))
        errs, warns = validate_record(checked)
        key = str(checked.get("bib_key") or "").strip() or "(unknown_key)"
        has_missing_biblio_warn = False
        for w in warns:
            if w == "missing_volume":
                missing_volume_keys.append(key)
                has_missing_biblio_warn = True
            elif w == "missing_pages_and_number":
                missing_pages_keys.append(key)
                has_missing_biblio_warn = True
            else:
                other_warn_groups.setdefault(w, []).append(key)
        if has_missing_biblio_warn and checked.get("unresolvable") is not True:
            blocking_missing_biblio_keys.append(key)
        if errs:
            print(
                f"ERROR {key}: " + ",".join(errs)
                + "; resolve metadata with DOI/title lookup and update the library before export-bib",
                file=sys.stderr,
            )
            had_error = True
    if missing_volume_keys or missing_pages_keys or other_warn_groups:
        warn_limit = max(0, int(getattr(ns, "warn_limit", 10)))

        def _sample(keys: list[str]) -> str:
            shown = keys[:warn_limit] if warn_limit else []
            suffix = "" if len(keys) <= len(shown) else f" (+{len(keys) - len(shown)} more)"
            return ", ".join(shown) + suffix

        print(
            "WARN: the following records are missing volume/pages/number — "
            "use DOI/title lookup to complete metadata before final export:",
            file=diagnostics,
        )
        if missing_volume_keys:
            print(
                f"  missing_volume ({len(missing_volume_keys)}, showing {min(warn_limit, len(missing_volume_keys))}): "
                + _sample(missing_volume_keys),
                file=diagnostics,
            )
        if missing_pages_keys:
            print(
                f"  missing_pages_and_number ({len(missing_pages_keys)}, showing {min(warn_limit, len(missing_pages_keys))}): "
                + _sample(missing_pages_keys),
                file=diagnostics,
            )
        for warn_name, keys in sorted(other_warn_groups.items()):
            print(
                f"  {warn_name} ({len(keys)}, showing {min(warn_limit, len(keys))}): "
                + _sample(keys),
                file=diagnostics,
            )
    if had_error and not ns.allow_incomplete:
        _fail(E_STRUCTURE, "refusing BibTeX export: selected records have incomplete metadata",
              "run resolve_volume_pages.py to fill missing fields, or pass --allow-incomplete for diagnostic export")
        return E_STRUCTURE
    if blocking_missing_biblio_keys and not ns.allow_incomplete:
        shown = blocking_missing_biblio_keys[:20]
        suffix = "" if len(blocking_missing_biblio_keys) <= len(shown) else f" (+{len(blocking_missing_biblio_keys) - len(shown)} more)"
        _fail(
            E_STRUCTURE,
            "refusing BibTeX export: selected records are missing volume/pages/number metadata: "
            + ", ".join(shown)
            + suffix,
            'run resolve_volume_pages.py and mark truly unresolved records with "unresolvable": true, '
            "or pass --allow-incomplete for diagnostic export",
        )
        return E_STRUCTURE

    body = "".join(build_minimal_bibtex(p) for p in recs)
    outp = Path(ns.output)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(body, encoding="utf-8")
    print(f"OK: BibTeX {len(recs)} entries -> {outp.resolve()}")
    return 0


def cmd_delete_keys(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)
    del_keys = [k.strip() for k in ns.keys.split(",") if k.strip()]

    used: set[str] = set()
    if getattr(ns, "scan_tex", ""):
        roots = [Path(r) for r in ns.scan_tex.split(";") if r.strip()]
        for r in roots:
            used |= cite_keys_in_tree(r)

        blocked = sorted(k for k in del_keys if k in used)
        if blocked and not ns.force:
            msg = f"refusing delete; keys still cited in .tex: {blocked}"
            _fail(E_CONSIST, msg, "remove \\cite{key} from mainbody.tex first, then retry; or pass --force")
            wp = getattr(ns, "warnings_report", "") or ""
            if wp:
                Path(wp).parent.mkdir(parents=True, exist_ok=True)
                Path(wp).write_text(f"[E{E_CONSIST}] {msg}\n", encoding="utf-8")
            return E_CONSIST
        if blocked and ns.force:
            print(
                "WARN: deleting keys that are still cited in .tex (blocked would be): "
                + str(blocked),
                file=sys.stderr,
            )

    before = len(lib)
    keep = [p for p in lib if str(p.get("bib_key") or "").strip() not in set(del_keys)]
    removed = before - len(keep)
    if ns.dry_run:
        print(f"DRY RUN: would delete {removed} of {before} ({del_keys}); not writing.")
        return 0
    save_library(path, keep)
    print(f"OK: removed {removed} entries; remaining {len(keep)} in {path.resolve()}")
    return 0


def cmd_validate(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)
    had_error = False
    warn_groups: dict[str, list[str]] = {}
    error_keys: list[str] = []
    for p in lib:
        bk = str(p.get("bib_key") or "").strip()
        errs, warns = validate_record(p)
        for w in warns:
            warn_groups.setdefault(w, []).append(bk)
        if errs:
            error_keys.append(f"{bk}: " + ",".join(errs))
            had_error = True
    for w_type, keys in sorted(warn_groups.items()):
        print(f"WARN {w_type} ({len(keys)}): {', '.join(keys)}", file=sys.stderr)
    for msg in error_keys:
        print(f"ERROR {msg}", file=sys.stderr)
    if ns.warn_only:
        return 0
    if had_error:
        _fail(E_STRUCTURE, "library has records with invalid/missing required fields",
              "fix title, authors, year fields in papers.json before running export-bib")
        return E_STRUCTURE
    return 0


def cmd_filter_year(ns: argparse.Namespace) -> int:
    path = Path(ns.library)
    lib, _ = load_library(path)

    ymin, ymax = int(ns.min_year), int(ns.max_year)
    filt: list[dict[str, Any]] = []

    for p in lib:
        ys = "".join(filter(str.isdigit, str(p.get("year") or "")))
        if len(ys) < 4:
            print(f"WARN: skip bib_key={p.get('bib_key')} year_unparseable", file=sys.stderr)
            continue
        y = int(ys[-4:])
        if ymin <= y <= ymax:
            filt.append(p)

    outp = Path(ns.output)
    save_library(outp, filt)
    print(f"OK: wrote {len(filt)} of {len(lib)} papers to {outp.resolve()}")
    return 0


def cmd_from_paper_results(ns: argparse.Namespace) -> int:
    """Import PaperSearch result files into the library.

    Prefer explicit --result-file savedPath inputs. Directory import remains
    available as a fallback/debug path when --result-file is omitted.
    """
    path = Path(ns.library)
    result_files = [Path(p) for p in getattr(ns, "result_file", [])]
    results_dir = Path(ns.results_dir) if getattr(ns, "results_dir", "") else None

    try:
        lib, absent = load_library(path)
    except (ValueError, json.JSONDecodeError) as exc:
        _fail(E_PRECOND, str(exc), "check library file path and JSON syntax")
        return E_PRECOND

    if absent and not ns.allow_create:
        _fail(E_PRECOND, f"library not found: {path}", "pass --allow-create to start a new JSON array")
        return E_PRECOND

    if result_files:
        missing = [str(p) for p in result_files if not p.is_file()]
        if missing:
            _fail(E_PRECOND, f"result-file not found: {missing[0]}", "pass the savedPath returned by the search tool")
            return E_PRECOND
        json_files = result_files
    elif results_dir is not None and results_dir.is_dir():
        json_files = sorted(results_dir.glob("*.json"))
    else:
        _fail(E_PRECOND, f"results-dir not found or not a directory: {results_dir}", "check the path")
        return E_PRECOND

    # Collect all candidate records from every *.json file, dedup by paperId
    # Use dict[pid -> index] so we can replace with a richer record if found later.
    seen_paper_ids: dict[str, int] = {}
    candidates: list[dict[str, Any]] = []
    files_read = 0
    for jf in json_files:
        try:
            raw = json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: skip {jf.name}: {exc}", file=sys.stderr)
            continue
        files_read += 1
        items = raw if isinstance(raw, list) else ([raw] if isinstance(raw, dict) else [])
        for item in items:
            if not isinstance(item, dict):
                continue
            item = strip_unused_result_fields(item)
            pid = str(item.get("paperId") or item.get("paper_id") or "").strip()
            if pid and pid in seen_paper_ids:
                # Keep the record with more information (e.g. has abstract vs. not)
                idx = seen_paper_ids[pid]
                if _information_length(item) > _information_length(candidates[idx]):
                    candidates[idx] = item
                continue
            if pid:
                seen_paper_ids[pid] = len(candidates)
            candidates.append(item)

    if not candidates:
        source_label = ", ".join(str(p) for p in result_files) if result_files else str(results_dir)
        print(f"INFO: no records found in {source_label} ({files_read} files scanned)", file=sys.stderr)
        return 0

    # Filter to only paperIds the user explicitly listed (if --paper-ids given)
    if getattr(ns, "paper_ids", ""):
        wanted = {p.strip() for p in ns.paper_ids.split(",") if p.strip()}
        candidates = [
            c for c in candidates
            if str(c.get("paperId") or c.get("paper_id") or "").strip() in wanted
        ]
        if not candidates:
            _fail(E_PRECOND, "none of the requested paperIds found in results-dir",
                  "check --paper-ids matches paperId values in the result files")
            return E_PRECOND

    by_key, by_doi = _index_maps(lib)
    th = float(getattr(ns, "title_similarity_alert", 0.92))
    inserted = merged = skipped = 0

    for rec in candidates:
        rec = ensure_bib_key(normalize_paper_fields(dict(rec)))
        errs, warns = validate_record(rec)
        for w in warns:
            print(f"WARN {rec['bib_key']}: {w}", file=sys.stderr)
        if errs:
            if ns.skip_invalid:
                skipped += 1
                continue
            msg = ",".join(errs)
            _fail(E_STRUCTURE, f"{rec['bib_key']}: {msg}",
                  "fix required fields (title, authors, year) or pass --skip-invalid")
            return E_STRUCTURE

        d = norm_doi(rec.get("doi"))
        bk = str(rec["bib_key"]).strip()

        if bk in by_key:
            ix = by_key[bk]
            lib[ix] = ensure_bib_key(merge_record(lib[ix], rec))
            merged += 1
            continue
        if d and d in by_doi:
            ix = by_doi[d]
            lib[ix] = ensure_bib_key(merge_record(lib[ix], rec))
            merged += 1
            continue

        ix = find_title_duplicate_index(lib, rec, th)
        if ix is not None:
            lib[ix] = ensure_bib_key(merge_record(lib[ix], rec))
            by_key, by_doi = _index_maps(lib)
            merged += 1
            continue

        lib.append(rec)
        by_key, by_doi = _index_maps(lib)
        inserted += 1

    lib = dedupe_library(lib, th)
    save_library(path, lib)
    print(
        f"OK: scanned {files_read} files, {len(candidates)} candidates — "
        f"inserted={inserted} merged={merged} skipped={skipped}; "
        f"library now {len(lib)} papers at {path.resolve()}"
    )

    # ── Post-import summary ──────────────────────────────────────────────────
    if inserted or merged:
        # Year distribution
        year_counts: dict[str, int] = {}
        for p in lib:
            ys = "".join(filter(str.isdigit, str(p.get("year") or "")))
            y = ys[-4:] if len(ys) >= 4 else "unknown"
            year_counts[y] = year_counts.get(y, 0) + 1
        years_sorted = sorted((y for y in year_counts if y != "unknown"), reverse=True)
        year_line = "  " + "  ".join(f"{y}:{year_counts[y]}" for y in years_sorted)
        if "unknown" in year_counts:
            year_line += f"  unknown:{year_counts['unknown']}"

        # All venues sorted by count
        venue_counts: dict[str, int] = {}
        for p in lib:
            v = venue_str(p)
            if v:
                venue_counts[v] = venue_counts.get(v, 0) + 1
        top_venues = sorted(venue_counts.items(), key=lambda x: -x[1])

        # All newly inserted bib_keys (appended during this call)
        new_keys = [str(p.get("bib_key") or "") for p in lib[-inserted:]] if inserted else []

        lines = ["─── Library summary ───────────────────────────────────"]
        lines.append(f"Total papers : {len(lib)}")
        lines.append(f"Year spread  :{year_line}")
        if top_venues:
            lines.append("Top venues   :")
            for v, c in top_venues[:10]:
                lines.append(f"  {c:3d}  {v}")
            if len(top_venues) > 10:
                lines.append(f"  ... {len(top_venues) - 10} more")
        if new_keys:
            lines.append(f"New keys ({len(new_keys)}):")
            for bk in new_keys[:10]:
                lines.append(f"  + {bk}")
            if len(new_keys) > 10:
                lines.append(f"  ... {len(new_keys) - 10} more")
        lines.append("────────────────────────────────────────────────────")
        print("\n".join(lines))

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SurveyMaster literature JSON library.")

    subs = p.add_subparsers(dest="cmd", required=True)

    pi = subs.add_parser("insert", help="Insert or merge paper records.")
    pi.add_argument("--library", "-l", required=True, help="Path to literature JSON file.")
    pi.add_argument(
        "--file",
        "-f",
        default="",
        help="JSON path (object or array). If omitted, read stdin.",
    )
    pi.add_argument(
        "--allow-create",
        action="store_true",
        help="Create new library array if missing.",
    )
    pi.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip records that fail validation instead of exiting 2.",
    )
    pi.add_argument(
        "--title-similarity-alert",
        type=float,
        default=0.92,
        dest="title_similarity_alert",
        help="Jaro-Winkler title threshold for silent merge (default: 0.92).",
    )
    pi.set_defaults(func=cmd_insert)

    ps = subs.add_parser("stats", help="Count and summarize core bibliographic rows.")
    ps.add_argument("--library", "-l", required=True)
    ps.add_argument("--limit", type=int, default=50)
    ps.add_argument("--output", "-o", default="", help="Write stats to file instead of stdout.")
    ps.set_defaults(func=cmd_stats)

    pac = subs.add_parser(
        "abstract-coverage",
        help="Gate Stage 2 completion on information-rich abstract coverage.",
    )
    pac.add_argument("--library", "-l", required=True)
    pac.add_argument("--min-count", type=int, default=30, help="Minimum rich abstracts required to proceed.")
    pac.add_argument("--min-chars", type=int, default=300, help="Minimum characters for an abstract to count as rich.")
    pac.add_argument("--limit", type=int, default=50, help="Maximum missing/short keys shown.")
    pac.add_argument("--output", "-o", default="", help="Write coverage report to file.")
    pac.add_argument("--warn-only", action="store_true", help="Report coverage but exit 0.")
    pac.set_defaults(func=cmd_abstract_coverage)

    pq = subs.add_parser(
        "query",
        help="Fetch records by bib_key comma list; writes to --output recommended.",
    )
    pq.add_argument("--library", "-l", required=True)
    pq.add_argument("--keys", "-k", required=True, help="Comma-separated bib_key list.")
    pq.add_argument(
        "--format",
        choices=("detailed", "simplified"),
        default="simplified",
    )
    pq.add_argument("--output", "-o", default="")
    pq.set_defaults(func=cmd_query)

    pwc = subs.add_parser(
        "build-write-context",
        help="Build compact paper context for one-pass write-section prompts.",
    )
    pwc.add_argument("--library", "-l", required=True, help="Path to papers.json.")
    pwc.add_argument("--outline", required=True, help="Path to outline.json.")
    pwc.add_argument("--output", "-o", default="", help="Write context to file; stdout prints full context when omitted.")
    pwc.add_argument(
        "--abstract-chars",
        type=int,
        default=400,
        help="Max abstract characters per evidence snippet (default: 400; 0 disables snippet text).",
    )
    pwc.add_argument(
        "--snippet-limit",
        type=int,
        default=30,
        help="Max unique evidence snippets, prioritized by relevance (default: 30; 0 means no limit).",
    )
    pwc.add_argument(
        "--index-limit",
        type=int,
        default=200,
        help="Max papers in global index (default: 200; 0 means all).",
    )
    pwc.add_argument(
        "--snippet-source",
        choices=("key-papers", "assigned", "none"),
        default="key-papers",
        help="Which keys receive abstract snippets (default: key-papers).",
    )
    pwc.set_defaults(func=cmd_build_write_context)

    pe = subs.add_parser(
        "export-bib",
        help="Emit BibTeX for all papers or comma-separated keys.",
    )
    pe.add_argument("--library", "-l", required=True)
    pe.add_argument("--keys", "-k", default="", help='Optional "k1,k2"; empty=all.')
    pe.add_argument(
        "--bbl-file",
        default="",
        help="Path to a compiled .bbl file. When provided, only cited keys are exported "
             "in final reference-list order as rendered by BibTeX. Takes precedence over --keys.",
    )
    pe.add_argument(
        "--tex-file",
        default="",
        help="Path to a LaTeX source file. When provided, only keys cited in the file are exported. "
             "Used before PDF compilation; --bbl-file takes precedence.",
    )
    pe.add_argument("--output", "-o", required=True)
    pe.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Allow BibTeX export despite blocking metadata errors (diagnostic use only).",
    )
    pe.add_argument(
        "--warn-limit",
        type=int,
        default=10,
        help="Maximum keys shown per warning group; full data remains in papers.json.",
    )
    pe.add_argument(
        "--diagnostics-stdout",
        action="store_true",
        help="Emit non-fatal WARN/INFO diagnostics to stdout so callers can pipe them.",
    )
    pe.set_defaults(func=cmd_export_bib)

    prv = subs.add_parser("validate", help="Lint all records.")
    prv.add_argument("--library", "-l", required=True)
    prv.add_argument(
        "--warn-only",
        action="store_true",
        help="Print errors but exit 0.",
    )
    prv.set_defaults(func=cmd_validate)

    pfn = subs.add_parser(
        "filter-year-range",
        help="Write a new JSON with papers whose year falls in inclusive range.",
    )
    pfn.add_argument("--library", "-l", required=True)
    pfn.add_argument("--min-year", type=int, required=True)
    pfn.add_argument("--max-year", type=int, required=True)
    pfn.add_argument("--output", "-o", required=True)
    pfn.set_defaults(func=cmd_filter_year)

    pdl = subs.add_parser(
        "delete-keys",
        help="Remove entries by bib_key (checks .tex cites unless --force).",
    )
    pdl.add_argument("--library", "-l", required=True)
    pdl.add_argument("--keys", "-k", required=True)
    pdl.add_argument(
        "--scan-tex",
        default="",
        help="Semicolon-separated roots to scan recursively for cite keys.",
    )
    pdl.add_argument(
        "--dry-run",
        action="store_true",
    )
    pdl.add_argument(
        "--force",
        action="store_true",
        help="Delete even when keys still appear in scanned .tex.",
    )
    pdl.add_argument(
        "--warnings-report",
        default="",
        dest="warnings_report",
        help="On refuse-delete path, write refusal message here.",
    )
    pdl.set_defaults(func=cmd_delete_keys)

    pfpr = subs.add_parser(
        "from-paper-results",
        help="Import PaperSearch/PaperSurveyToFile JSON result files into the library.",
    )
    pfpr.add_argument("--library", "-l", required=True, help="Path to library JSON file.")
    pfpr.add_argument(
        "--result-file",
        action="append",
        default=[],
        help="Specific PaperSearch/PaperSurveyToFile savedPath JSON file to import. May be passed multiple times.",
    )
    pfpr.add_argument(
        "--results-dir", "-r", default="",
        help="Directory containing PaperSearch result *.json files (e.g. /bohr-workspace/paper-results). Used only when --result-file is omitted.",
    )
    pfpr.add_argument(
        "--paper-ids", default="",
        help="Optional comma-separated paperId list. When given, only matching records are inserted.",
    )
    pfpr.add_argument(
        "--allow-create", action="store_true",
        help="Create new library array if missing.",
    )
    pfpr.add_argument(
        "--skip-invalid", action="store_true",
        help="Skip records that fail validation instead of exiting.",
    )
    pfpr.add_argument(
        "--title-similarity-alert", type=float, default=0.92,
        dest="title_similarity_alert",
        help="Jaro-Winkler title threshold for silent merge (default: 0.92).",
    )
    pfpr.set_defaults(func=cmd_from_paper_results)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    func = getattr(ns, "func", None)
    if not func:
        parser.print_help(file=sys.stderr)
        return 1
    try:
        return int(func(ns))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        _fail(E_PRECOND, str(exc), "check file paths, permissions, and JSON syntax")
        return E_PRECOND


if __name__ == "__main__":
    raise SystemExit(main())
