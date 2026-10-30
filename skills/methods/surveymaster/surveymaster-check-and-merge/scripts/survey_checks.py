"""Lightweight LaTeX / BibTeX checks for SurveyMaster (stdlib only).

Subcommands:
  cites     — compare \\cite keys against papers.json and optional .bib
  bib       — duplicate @entry keys in .bib
  latex     — heuristics: suspicious percent, stray @ in non-comment lines
  words     — rough word/char count for .tex files
  doi       — cross-check .bib DOI fields against papers.json
  repair-structure — repair deterministic TeX noise, then run structure checks
  structure — check mainbody.tex has abstract, keywords, required sections
  all       — run cites, bib, doi, latex, words, figures-tables (pass shared args);
              optionally build compact check_summary.txt
  build-check-summary — build compact check_summary.txt from an all report

Exit codes: 0=ok, 1=warn, 10=E_PRECOND, 11=E_STRUCTURE, 12=E_CONSIST,
            20=E_CITE, 21=E_BIB, 22=E_DOI, 30=E_LATEX.
Stderr format: [E{code}] description\\n       Fix: suggestion
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_CITE_RE = re.compile(r"\\cite\{(?P<body>[^\}]+)\}")
_BIB_ENTRY = re.compile(r"@[A-Za-z]+\s*\{\s*([^,\s]+)\s*,")
_REM_COMMENT = re.compile(r"(?<!\\)%.*$")
_DOI_PREFIX_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.I)

# Exit codes
E_WARN = 1       # non-blocking warnings
E_PRECOND = 10   # missing file / missing dependency / bad argument
E_STRUCTURE = 11 # structural or content validation failure
E_CONSIST = 12   # language mismatch / duplicate keys / consistency
E_CITE = 20      # \cite key missing from bib/library
E_BIB = 21       # BibTeX duplicate key or unescaped &
E_DOI = 22       # DOI mismatch between .bib and library
E_LATEX = 30     # LaTeX character hazard


def _fail(code: int, description: str, fix: str) -> None:
    print(f"[E{code}] {description}", file=sys.stderr)
    print(f"       Fix: {fix}", file=sys.stderr)


def _emit(text: str, report_path: str) -> None:
    """Write text to stdout always; also write to report_path when given."""
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    if report_path:
        rp = Path(report_path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(text, encoding="utf-8")


def _write_report(path: str, text: str) -> None:
    if not path:
        return
    rp = Path(path)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(text, encoding="utf-8")


def _norm_doi(raw: str) -> str:
    return _DOI_PREFIX_RE.sub("", raw.strip()).lower()


def _parse_bib_dois(path: Path) -> dict[str, str | None]:
    """Return {bib_key: raw_doi_or_None} for every entry in a .bib file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    result: dict[str, str | None] = {}
    for m in _BIB_ENTRY.finditer(text):
        key = m.group(1).strip()
        start = m.end()
        nxt = text.find("\n@", start)
        block = text[start: nxt if nxt != -1 else len(text)]
        doi_m = re.search(r"\bdoi\s*=\s*(?:\{([^}]*)\}|\"([^\"]*)\")", block, re.I)
        if doi_m:
            raw = (doi_m.group(1) or doi_m.group(2) or "").strip()
            result[key] = raw if raw else None
        else:
            result[key] = None
    return result


def _load_library_dois(path: Path) -> dict[str, str | None]:
    """Return {bib_key: doi_or_None} from papers.json."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    lib: list[dict[str, Any]] = raw if isinstance(raw, list) else raw.get("papers", [])
    return {
        str(p.get("bib_key") or "").strip(): (str(p.get("doi") or "").strip() or None)
        for p in lib
        if str(p.get("bib_key") or "").strip()
    }


def read_tex_files(tex_dirs: list[Path], extra: list[Path]) -> list[Path]:
    files: list[Path] = []
    for d in tex_dirs:
        if d.is_file() and d.suffix == ".tex":
            files.append(d)
            continue
        if d.is_dir():
            files.extend(sorted(d.rglob("*.tex")))
    for p in extra:
        if p.exists() and p.suffix == ".tex":
            files.append(p)
    # de-dup
    seen: set[str] = set()
    out: list[Path] = []
    for f in files:
        k = str(f.resolve())
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def collect_cite_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in _CITE_RE.finditer(text):
            for part in m.group("body").split(","):
                k = part.strip()
                if k:
                    keys.add(k)
    return keys


def load_library_keys(path: Path) -> set[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    lib: list[dict[str, Any]]
    if isinstance(raw, list):
        lib = raw
    elif isinstance(raw, dict) and isinstance(raw.get("papers"), list):
        lib = raw["papers"]
    else:
        raise ValueError(f"{path}: JSON must be paper array or {{papers: [...]}}")
    return {
        str(p.get("bib_key") or "").strip()
        for p in lib
        if str(p.get("bib_key") or "").strip()
    }


def bibtex_keys(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return [m.group(1).strip() for m in _BIB_ENTRY.finditer(text)]


def strip_comments(line: str) -> str:
    return _REM_COMMENT.sub("", line)


def cmd_cites(ns: argparse.Namespace) -> int:
    dirs = [Path(x) for x in ns.tex_dirs.split(";") if x.strip()]
    extra = [Path(x) for x in ns.extra_tex.split(";") if x.strip()]
    tex_files = read_tex_files(dirs, extra)
    if not tex_files:
        _fail(E_PRECOND, "no .tex files found", "pass --extra-tex or --tex-dirs pointing to mainbody.tex")
        return E_PRECOND

    used = collect_cite_keys(tex_files)

    bib_keys_union: set[str] = set()
    if ns.library:
        bib_keys_union |= load_library_keys(Path(ns.library))
    if ns.bib:
        bib_keys_union |= set(bibtex_keys(Path(ns.bib)))

    if not bib_keys_union:
        _fail(E_WARN, "neither --library nor valid --bib provided; cannot validate cite keys", "pass --library papers.json and/or --bib references.bib")

    missing = sorted(k for k in used if bib_keys_union and k not in bib_keys_union)

    leftover = sorted(bib_keys_union - used) if ns.report_unused else []

    lines = [
        f"tex_files={len(tex_files)}",
        f"distinct_cite_keys={len(used)}",
        f"missing_defined_keys={missing}",
        f"possibly_unused_library_or_bib_keys_count={len(leftover)}",
    ]
    if leftover and ns.report_unused:
        lines.append("unused_library_keys=" + str(sorted(leftover)))

    report = "\n".join(lines) + "\n"
    _emit(report, ns.report)
    # used_cite_keys written to report file only (not stdout) — needed by finalize
    # Phase 2 to scope bib metadata resolution; too large for LLM context.
    if ns.report:
        with open(ns.report, "a", encoding="utf-8") as _rf:
            _rf.write(f"used_cite_keys={sorted(used)}\n")

    if missing and not ns.warn_only:
        _fail(E_CITE, f"{len(missing)} \\cite key(s) not found in bib/library: {missing[:10]}{'...' if len(missing) > 10 else ''}",
              "check references.bib and papers.json; re-run surveymaster-finalize BibTeX export step")
        return E_CITE
    return 0


_UNESCAPED_AMP_IN_FIELD = re.compile(
    r"""(?x)
    (?:                    # field-value delimited by { } or " "
        \{  ( [^{}]* )  \}    # brace-delimited value (shallow)
      | "   ( [^"]*  )  "     # quote-delimited value
    )
    """,
)
_BARE_AMP = re.compile(r"(?<!\\)&")


def _find_unescaped_amps_in_bib(text: str) -> list[tuple[int, str]]:
    """Return list of (line_number, line_text) for lines with bare & inside field values."""
    hits: list[tuple[int, str]] = []
    for ln, line in enumerate(text.splitlines(), 1):
        # Skip comment lines and entry-header lines (@article{key,)
        stripped = line.strip()
        if stripped.startswith("%") or re.match(r"@[A-Za-z]+\s*\{", stripped):
            continue
        # Check for bare & in any field-value region on this line
        for m in _UNESCAPED_AMP_IN_FIELD.finditer(line):
            val = m.group(1) or m.group(2) or ""
            if _BARE_AMP.search(val):
                hits.append((ln, line.rstrip()))
                break
    return hits


def cmd_bib(ns: argparse.Namespace) -> int:
    path = Path(ns.bib)
    text = path.read_text(encoding="utf-8", errors="replace")
    keys = bibtex_keys(path)

    # Duplicate key check
    seen: dict[str, int] = {}
    dups: list[str] = []
    for k in keys:
        seen[k] = seen.get(k, 0) + 1
    for k, c in seen.items():
        if c > 1:
            dups.append(f"{k} x{c}")

    # Unescaped & check
    amp_hits = _find_unescaped_amps_in_bib(text)
    amp_lines = [f"  line {ln}: {txt}" for ln, txt in amp_hits]

    lines_out: list[str] = [
        "duplicate_bib_keys=" + (", ".join(dups) if dups else "none"),
    ]
    if amp_hits:
        lines_out.append(
            f"unescaped_ampersand_count={len(amp_hits)} "
            "(bare & in BibTeX field values will break LaTeX compilation; "
            "re-export via bibliography_library.py export-bib to auto-escape)"
        )
        lines_out.extend(amp_lines)
    else:
        lines_out.append("unescaped_ampersand=none")

    msg = "\n".join(lines_out) + "\n"
    _emit(msg, ns.report)

    has_error = bool(dups) or bool(amp_hits)
    if has_error and not ns.warn_only:
        parts = []
        if dups:
            parts.append(f"duplicate keys: {dups}")
        if amp_hits:
            parts.append(f"unescaped & on {len(amp_hits)} line(s)")
        _fail(E_BIB, "; ".join(parts),
              "re-export references.bib via bibliography_library.py export-bib to fix escaping; remove duplicate entries manually")
        return E_BIB
    return 0


def cmd_latex(ns: argparse.Namespace) -> int:
    dirs = [Path(x) for x in ns.tex_dirs.split(";") if x.strip()]
    extra = [Path(x) for x in ns.extra_tex.split(";") if x.strip()]
    tex_files = read_tex_files(dirs, extra)
    issues: list[str] = []
    for p in tex_files:
        for ln, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            raw = line.rstrip("\n")
            # skip blank or pure-comment lines
            if not raw.strip() or raw.lstrip().startswith("%"):
                continue
            # unescaped % — operate on raw line, not strip_comments(line).
            # strip_comments removes % and everything after it, making the
            # search below always miss bare %.  Instead: remove \% then look
            # for any remaining % that is not itself preceded by \.
            rest_pct = re.sub(r"\\%", "", raw)
            if re.search(r"(?<!\\)%", rest_pct):
                issues.append(f"{p}:{ln}: possible_unescaped_percent: {raw[:160]}")
            # stray @ — use strip_comments so @ inside line-comments is ignored
            body = strip_comments(raw)
            at_rest = re.sub(r"\\[@A-Za-z]", "", body)  # strip known \@ and control sequences
            at_rest = re.sub(r"\\(?:begin|end|cite[a-zA-Z*]*|bibitem|bibliography)\s*(\[[^\]]*\])?\{[^}]*\}", "", at_rest)
            if "@" in at_rest:
                issues.append(f"{p}:{ln}: possible_stray_at: {body[:160]}")
    # \\\n\bottomrule — three backslashes before \bottomrule: the stray third
    # backslash corrupts the row-end \\ and distorts \bottomrule length.
    # The correct form is \\\n\bottomrule (two backslashes + newline).
    for p in tex_files:
        tex = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"\\\\\\[ \t]*\n[ \t]*\\bottomrule", tex):
            ln = tex[: m.start()].count("\n") + 1
            issues.append(
                f"{p}:{ln}: TRIPLE_BACKSLASH_BEFORE_BOTTOMRULE: three backslashes before"
                " \\bottomrule — should be \\\\\\\\ (two backslashes)"
            )

    text = "\n".join(issues) if issues else "(no latex heuristic hits)\n"
    _emit(text, ns.report)
    if issues and not ns.warn_only:
        _fail(E_LATEX, f"{len(issues)} LaTeX character hazard(s) found",
              "review the flagged lines; escape % as \\% and @ in non-citation contexts")
        return E_LATEX
    return 0


def cmd_words(ns: argparse.Namespace) -> int:
    dirs = [Path(x) for x in ns.tex_dirs.split(";") if x.strip()]
    extra = [Path(x) for x in ns.extra_tex.split(";") if x.strip()]
    tex_files = read_tex_files(dirs, extra)
    if not tex_files:
        _fail(E_PRECOND, "no .tex files found for word count", "pass --extra-tex or --tex-dirs pointing to mainbody.tex")
        return E_PRECOND

    texcount = shutil.which("texcount")
    if not texcount:
        _fail(E_PRECOND, "texcount not found", "install TeX Live: brew install texlive  or  apt install texlive-extra-utils")
        return E_PRECOND

    def count_texcount(path: Path) -> tuple[int | None, str]:
        res = subprocess.run(
            [texcount, "-1", "-sum", "-merge", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if res.returncode != 0:
            return None, (res.stderr.strip() or "texcount_failed")
        match = re.search(r"-?\d+", res.stdout)
        if not match:
            return None, "texcount_output_unparseable: " + res.stdout.strip()[:120]
        return int(match.group(0)), ""

    total_words = 0
    lines: list[str] = []
    for p in tex_files:
        words, warn = count_texcount(p)
        if words is None:
            _fail(E_PRECOND, f"texcount failed for {p.name}: {warn}", "check TeX Live installation")
            return E_PRECOND
        total_words += words
        line = f"{p.name}: texcount_words={words}"
        if warn:
            line += f" warn={warn}"
        lines.append(line)

    if len(tex_files) == 1:
        summary = f"TOTAL texcount_words={total_words}\n"
    else:
        summary = "\n".join(lines) + f"\nTOTAL texcount_words={total_words}\n"
    _emit(summary, ns.report)
    return 0


def cmd_doi(ns: argparse.Namespace) -> int:
    """Cross-check DOI fields in .bib against papers.json library.

    For each bib entry that has a DOI:
    - if the bib key is in papers.json and papers.json also has a DOI,
      verify both normalise to the same value.
    Exit E_DOI (22) when any mismatch is found (unless --warn-only).
    Exit E_WARN (1) when bib keys are missing from papers.json entirely.
    Bib entries with no DOI field are reported as warnings, never failures.
    """
    bib_path = Path(ns.bib)
    lib_path = Path(ns.library) if ns.library else None

    bib_dois = _parse_bib_dois(bib_path)
    lib_dois: dict[str, str | None] = _load_library_dois(lib_path) if lib_path else {}

    mismatches: list[str] = []
    missing_from_lib: list[str] = []
    no_doi_in_bib: list[str] = []
    no_doi_in_lib: list[str] = []

    for key, bib_doi in bib_dois.items():
        if bib_doi is None:
            no_doi_in_bib.append(key)
            continue
        if key not in lib_dois:
            missing_from_lib.append(key)
            continue
        lib_doi = lib_dois[key]
        if lib_doi is None:
            no_doi_in_lib.append(key)
            continue
        if _norm_doi(bib_doi) != _norm_doi(lib_doi):
            mismatches.append(
                f"{key}: bib={bib_doi!r} vs lib={lib_doi!r}"
            )

    lines: list[str] = [
        f"bib_entries={len(bib_dois)}",
        f"lib_entries={len(lib_dois)}",
    ]
    if mismatches:
        lines.append(f"doi_mismatches={mismatches}")
    if missing_from_lib:
        lines.append(f"bib_keys_not_in_lib={missing_from_lib}")
    if no_doi_in_bib:
        lines.append(f"bib_entries_without_doi={no_doi_in_bib}")
    if no_doi_in_lib:
        lines.append(f"lib_entries_without_doi_for_matched_keys={no_doi_in_lib}")
    report = "\n".join(lines) + "\n"
    _emit(report, ns.report)

    if mismatches and not ns.warn_only:
        _fail(E_DOI, f"{len(mismatches)} DOI mismatch(es) between .bib and papers.json",
              "update the bib_key record in papers.json DOI field, then re-export references.bib")
        return E_DOI
    if missing_from_lib or no_doi_in_bib:
        return E_WARN
    return 0


# CJK Unified Ideographs (4E00-9FFF) + Extension A (3400-4DBF) + Extension B (20000-2A6DF)
_CJK_RE = re.compile("[\u4e00-\u9fff\u3400-\u4dbf\U00020000-\U0002a6df]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _load_outline_section_titles(path: Path) -> list[str]:
    """Return writable top-level section titles from outline.json."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("outline")
    if not isinstance(entries, list):
        entries = raw.get("sections")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected top-level outline or sections array")

    titles: list[tuple[int, str]] = []
    for pos, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            continue
        entry_type = str(entry.get("type") or "section").strip().lower()
        parent = entry.get("parent_index")
        if entry_type not in {"section", ""}:
            continue
        if parent not in (None, "", 0, "0"):
            continue
        title = str(entry.get("title") or "").strip()
        if not title:
            continue
        try:
            order = int(entry.get("index", pos))
        except (TypeError, ValueError):
            order = pos
        titles.append((order, title))
    return [title for _, title in sorted(titles, key=lambda item: item[0])]


def _clean_tex_text(text: str) -> tuple[str, list[str]]:
    """Remove only deterministic TeX wrapper/fence noise."""
    changed: list[str] = []
    output: list[str] = []
    for ln, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped in {"```", "```latex", "```tex"}:
            changed.append(f"line {ln}: removed markdown fence")
            continue
        if re.match(r"\\(?:documentclass|usepackage)\b", stripped):
            changed.append(f"line {ln}: removed document wrapper command")
            continue
        if stripped in {r"\begin{document}", r"\end{document}"}:
            changed.append(f"line {ln}: removed document environment wrapper")
            continue
        output.append(line.rstrip())

    cleaned = "\n".join(output).strip() + "\n"
    if cleaned != text:
        if not changed:
            changed.append("normalized leading/trailing whitespace or final newline")
    return cleaned, changed


def _fix_percent_text(text: str) -> tuple[str, list[str]]:
    """Escape bare percent signs in non-comment lines."""
    fixed_lines: list[str] = []
    fix_details: list[str] = []

    for ln, line in enumerate(text.splitlines(keepends=True), 1):
        stripped = line.rstrip("\n")
        if stripped.lstrip().startswith("%"):
            fixed_lines.append(line)
            continue
        new_stripped, n = re.subn(r"(?<!\\)%", r"\\%", stripped)
        if n:
            fix_details.append(f"line {ln}: escaped {n} bare percent sign(s)")
        fixed_lines.append(new_stripped + ("\n" if line.endswith("\n") else ""))
    return "".join(fixed_lines), fix_details


def _fix_unclosed_abstract(text: str) -> tuple[str, list[str]]:
    """Close a single unclosed abstract when the next boundary is unambiguous."""
    begin_matches = list(re.finditer(r"\\begin\{abstract\}", text))
    end_matches = list(re.finditer(r"\\end\{abstract\}", text))
    if len(begin_matches) != 1 or end_matches:
        return text, []

    begin_end = begin_matches[0].end()
    boundary_candidates = [
        m.start()
        for pattern in (r"\\keywords\{", r"\\maketitle\b", r"\\tableofcontents\b", r"\\section\{")
        for m in [re.search(pattern, text[begin_end:])]
        if m is not None
    ]
    if not boundary_candidates:
        return text, []

    boundary = begin_end + min(boundary_candidates)
    abstract_body = text[begin_end:boundary].strip()
    if not abstract_body:
        return text, []

    insertion = "\n\\end{abstract}\n"
    fixed = text[:boundary].rstrip() + insertion + text[boundary:].lstrip("\n")
    return fixed, ["inserted missing \\end{abstract} before next metadata/body boundary"]


def _normalize_table_label_prefix(text: str) -> tuple[str, list[str]]:
    """Normalize common LaTeX table label prefix tbl: to SurveyMaster's tab:."""
    fixed, n = re.subn(r"\\(label|(?:auto)?ref)\{tbl:", r"\\\1{tab:", text)
    if not n:
        return text, []
    return fixed, [f"normalized {n} tbl: table label/reference prefix(es) to tab:"]


def _normalize_legacy_figure_comments(text: str) -> tuple[str, list[str]]:
    """Convert legacy `% FIGURE: id — prompt` comments to canonical format."""
    changes: list[str] = []

    def repl(match: re.Match) -> str:
        fig_id = match.group("id").strip()
        prompt = match.group("prompt").strip().strip('"“”')
        prompt = prompt.replace('"', "'")
        changes.append(f"normalized legacy % FIGURE comment for {fig_id}")
        return f'% FIGURE id={fig_id} prompt="{prompt}"'

    fixed = re.sub(
        r'(?m)^[ \t]*%\s*FIGURE\s*[:：]\s*(?P<id>[A-Za-z0-9_:-]+)\s*(?:[-—–:：]\s*)?(?P<prompt>[^\n]*)$',
        repl,
        text,
    )
    return fixed, changes


def cmd_repair_structure(ns: argparse.Namespace) -> int:
    """Repair deterministic TeX noise in place, then run structure checks."""
    path = Path(ns.mainbody)
    if not path.exists():
        _fail(E_PRECOND, f"file not found: {path}", "check the --mainbody argument")
        return E_PRECOND

    original = path.read_text(encoding="utf-8", errors="replace")
    cleaned, clean_changes = _clean_tex_text(original)
    fixed, percent_changes = _fix_percent_text(cleaned)
    fixed, abstract_changes = _fix_unclosed_abstract(fixed)
    fixed, table_prefix_changes = _normalize_table_label_prefix(fixed)
    fixed, figure_comment_changes = _normalize_legacy_figure_comments(fixed)
    all_changes = [f"clean: {item}" for item in clean_changes] + [
        f"percent: {item}" for item in percent_changes
    ] + [f"abstract: {item}" for item in abstract_changes] + [
        f"table-label: {item}" for item in table_prefix_changes
    ] + [f"figure-comment: {item}" for item in figure_comment_changes]

    repair_lines = [
        "=== repair (auto-fix deterministic formatting only) ===",
        f"repair_changes={len(all_changes)}",
    ]
    repair_lines.extend(all_changes or ["no_changes_needed"])
    if fixed != original:
        path.write_text(fixed, encoding="utf-8")
        repair_lines.append(f"written={path}")

    struct_ns = argparse.Namespace(
        mainbody=str(path),
        lang=ns.lang,
        outline=ns.outline,
        report="",
        warn_only=ns.warn_only,
    )
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = cmd_structure(struct_ns)
    finally:
        sys.stdout = old_stdout

    report = "\n".join(repair_lines) + "\n=== structure ===\n" + buf.getvalue()
    _emit(report, ns.report)
    return rc


def cmd_structure(ns: argparse.Namespace) -> int:
    """Check mainbody.tex has non-empty abstract, keywords (zh or en), and at least one section."""
    mainbody = Path(ns.mainbody)
    if not mainbody.exists():
        _fail(E_PRECOND, f"mainbody.tex not found: {mainbody}",
              "run surveymaster-write-section to generate mainbody.tex first")
        return E_PRECOND

    text = mainbody.read_text(encoding="utf-8", errors="replace")
    lang = (ns.lang or "").strip().lower()
    issues: list[str] = []

    abs_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
    if not abs_m:
        issues.append("MISSING_ABSTRACT: \\begin{abstract}...\\end{abstract} not found")
    elif not abs_m.group(1).strip():
        issues.append("EMPTY_ABSTRACT: \\begin{abstract} environment is empty")
    elif lang == "zh" and not _has_cjk(abs_m.group(1)):
        issues.append("LANG_MISMATCH_ABSTRACT: language=zh but abstract contains no CJK characters")
    # Check \end{abstract} appears before first \section{}
    end_abs = text.find(r"\end{abstract}")
    first_sec = text.find(r"\section{")
    if end_abs != -1 and first_sec != -1 and end_abs > first_sec:
        issues.append("ABSTRACT_NOT_CLOSED: \\end{abstract} appears after first \\section{} — abstract must be closed before body sections begin")
    # Check abstract does not reference figures or tables
    if abs_m and re.search(r"\\(?:auto)?ref\{(?:fig|tab):", abs_m.group(1)):
        issues.append("ABSTRACT_FLOAT_REF: \\autoref{} or \\ref{} to a figure/table found inside \\begin{abstract} — abstracts must not reference floats")

    kw_m = re.search(r"\\keywords\{([^}]*)\}", text)
    if not kw_m:
        issues.append("MISSING_KEYWORDS: \\keywords{} not found")
    elif not kw_m.group(1).strip():
        issues.append("EMPTY_KEYWORDS: \\keywords{} is empty")
    elif lang == "zh" and not _has_cjk(kw_m.group(1)):
        issues.append("LANG_MISMATCH_KEYWORDS: language=zh but keywords contain no CJK characters")

    if not re.search(r"\\section\{", text):
        issues.append("MISSING_SECTIONS: no \\section{} found in mainbody.tex")

    if not re.search(r"\\maketitle\b", text):
        issues.append("MISSING_MAKETITLE: \\maketitle not found in mainbody.tex")

    if not re.search(r"\\tableofcontents\b", text):
        issues.append("MISSING_TOC: \\tableofcontents not found in mainbody.tex")

    forbidden_patterns = [
        ("FORBIDDEN_DOCUMENTCLASS", r"(?m)^\s*\\documentclass\b"),
        ("FORBIDDEN_USEPACKAGE", r"(?m)^\s*\\usepackage\b"),
        ("FORBIDDEN_BEGIN_DOCUMENT", r"(?m)^\s*\\begin\{document\}\s*$"),
        ("FORBIDDEN_END_DOCUMENT", r"(?m)^\s*\\end\{document\}\s*$"),
        ("FORBIDDEN_BIBLIOGRAPHYSTYLE", r"(?m)^\s*\\bibliographystyle\s*\{[^}]*\}"),
        ("FORBIDDEN_BIBLIOGRAPHY", r"(?m)^\s*\\bibliography\s*\{[^}]*\}"),
        ("FORBIDDEN_THEBIBLIOGRAPHY", r"\\begin\{thebibliography\}|\\end\{thebibliography\}"),
        ("FORBIDDEN_BIBITEM", r"\\bibitem\b"),
        ("FORBIDDEN_MARKDOWN_FENCE", r"(?m)^\s*```(?:latex|tex)?\s*$"),
        ("FORBIDDEN_EVIDENCE_SOURCE_TAG", r"(?i)(?:Evidence\s+source|证据来源)\s*[:：]"),
    ]
    for label, pattern in forbidden_patterns:
        if re.search(pattern, text):
            issues.append(f"{label}: generated mainbody.tex must not include document wrappers, bibliography blocks, or markdown fences")

    outline_path = str(getattr(ns, "outline", "") or "").strip()
    if outline_path:
        expected_titles = _load_outline_section_titles(Path(outline_path))
        missing_titles = [
            title for title in expected_titles
            if not re.search(r"\\section\{\s*" + re.escape(title) + r"\s*\}", text)
        ]
        if missing_titles:
            issues.append(f"MISSING_OUTLINE_SECTIONS: section titles absent from mainbody.tex: {missing_titles}")

    # Begin/end environment balance check
    begin_counts: dict[str, int] = {}
    end_counts: dict[str, int] = {}
    for m in re.finditer(r"\\begin\{([\w*]+)\}", text):
        env = m.group(1)
        begin_counts[env] = begin_counts.get(env, 0) + 1
    for m in re.finditer(r"\\end\{([\w*]+)\}", text):
        env = m.group(1)
        end_counts[env] = end_counts.get(env, 0) + 1
    unmatched_envs = []
    for env in sorted(set(begin_counts) | set(end_counts)):
        b = begin_counts.get(env, 0)
        e = end_counts.get(env, 0)
        if b != e:
            unmatched_envs.append(f"\\begin{{{env}}} x{b} vs \\end{{{env}}} x{e}")
    if unmatched_envs:
        issues.append("BEGIN_END_MISMATCH: " + "; ".join(unmatched_envs))

    lines = [f"mainbody={mainbody}", f"issue_count={len(issues)}"] + issues
    report = "\n".join(lines) + "\n"

    _emit(report, ns.report)

    if issues and not ns.warn_only:
        lang_issues = [i for i in issues if "LANG_MISMATCH" in i]
        struct_issues = [i for i in issues if "LANG_MISMATCH" not in i]
        if lang_issues:
            _fail(E_CONSIST, f"language consistency: {'; '.join(lang_issues)}",
                  "re-run surveymaster-write-section or surveymaster-refine-section with correct --language")
        if struct_issues:
            _fail(E_STRUCTURE, f"structure missing: {'; '.join(struct_issues)}",
                  "re-run surveymaster-write-section to regenerate a complete mainbody.tex")
        return E_CONSIST if lang_issues and not struct_issues else E_STRUCTURE
    return 0


_FIGURE_ENV_COUNT_RE = re.compile(r"\\begin\{figure\}", re.MULTILINE)
_TABLE_ENV_COUNT_RE = re.compile(r"\\begin\{table\}", re.MULTILINE)


_FIG_LABEL_RE = re.compile(r"\\label\{(fig:[^}]+)\}")
_FIG_AUTOREF_RE = re.compile(r"\\(?:auto)?ref\{(fig:[^}]+)\}")
_TAB_LABEL_RE = re.compile(r"\\label\{(tab:[^}]+)\}")
_TAB_AUTOREF_RE = re.compile(r"\\(?:auto)?ref\{(tab:[^}]+)\}")


def cmd_figures_tables(ns: argparse.Namespace) -> int:
    """Compare actual figure/table counts in mainbody.tex against expected totals,
    and check that every figure/table label has at least one \\autoref{} in the body.

    Reads expected_figures_total and expected_tables_total from outline.json.
    Reports WARN when the absolute difference exceeds 1.
    Reports UNREFERENCED_FIGURE / UNREFERENCED_TABLE for each label with no \\autoref{}.
    Exit 0 when counts match and all floats are referenced; E_WARN (1) otherwise.
    """
    mainbody = Path(ns.mainbody)
    outline = Path(ns.outline) if ns.outline else None

    if not mainbody.exists():
        _fail(E_PRECOND, f"mainbody.tex not found: {mainbody}", "pass --mainbody pointing to mainbody.tex")
        return E_PRECOND

    tex = mainbody.read_text(encoding="utf-8", errors="replace")
    # Count only labels that also have at least one \autoref{} — unreferenced
    # floats are separately flagged as UNREFERENCED_FIGURE/TABLE and would be
    # removed before export, so they must not inflate the actual count here.
    _fig_refs = set(_FIG_AUTOREF_RE.findall(tex))
    _tab_refs = set(_TAB_AUTOREF_RE.findall(tex))
    actual_figures = len(set(_FIG_LABEL_RE.findall(tex)) & _fig_refs)
    actual_tables = len(set(_TAB_LABEL_RE.findall(tex)) & _tab_refs)

    expected_figures: int | None = None
    expected_tables: int | None = None
    if outline and outline.exists():
        try:
            data = json.loads(outline.read_text(encoding="utf-8"))
            v = data.get("expected_figures_total")
            if isinstance(v, int):
                expected_figures = v
            v = data.get("expected_tables_total")
            if isinstance(v, int):
                expected_tables = v
        except (json.JSONDecodeError, OSError):
            pass

    lines: list[str] = []
    rc = 0

    def _check(label: str, actual: int, expected: int | None) -> None:
        nonlocal rc
        if expected is None:
            lines.append(f"{label}: actual={actual} expected=unknown")
            return
        if actual == expected:
            lines.append(f"{label}: actual={actual} expected={expected} diff=0 status=ok")
        elif actual < expected:
            missing = expected - actual
            lines.append(
                f"{label}: actual={actual} expected={expected} diff=-{missing} status=ERROR_MISSING"
                f" — {missing} {label} missing; writing is incomplete"
            )
            rc = E_STRUCTURE
        else:
            extra = actual - expected
            lines.append(
                f"{label}: actual={actual} expected={expected} diff=+{extra} status=WARN_EXTRA"
                f" — {extra} unexpected extra {label}"
            )
            rc = max(rc, E_WARN)

    _check("figures", actual_figures, expected_figures)
    _check("tables", actual_tables, expected_tables)

    # Check: no figure before first \section{}
    _first_sec_m = re.search(r"\\section\{", tex)
    if _first_sec_m:
        _first_sec_pos = _first_sec_m.start()
        for _fm in re.finditer(r"\\begin\{figure\}", tex):
            if _fm.start() < _first_sec_pos:
                _preceding = tex[max(0, _fm.start() - 200):_fm.start()]
                _id_m = re.search(r"% FIGURE\s+id=(\S+)", _preceding)
                _fig_id = _id_m.group(1) if _id_m else "(unknown)"
                lines.append(
                    f"FIGURE_BEFORE_FIRST_SECTION: id={_fig_id} — \\begin{{figure}} appears"
                    " before first \\section{} heading; move inside the owning section body"
                )
                rc = E_WARN

    # Reference coverage: every label must have at least one \autoref{} in the body
    fig_labels = set(_FIG_LABEL_RE.findall(tex))
    fig_refs = set(_FIG_AUTOREF_RE.findall(tex))
    for lbl in fig_labels:
        if lbl not in fig_refs:
            lines.append(
                f"UNREFERENCED_FIGURE: \\label{{{lbl}}} has no \\autoref{{{lbl}}} in mainbody.tex"
                " — every figure must be referenced in the body prose"
            )
            rc = E_STRUCTURE

    tab_labels = set(_TAB_LABEL_RE.findall(tex))
    tab_refs = set(_TAB_AUTOREF_RE.findall(tex))
    for lbl in tab_labels:
        if lbl not in tab_refs:
            lines.append(
                f"UNREFERENCED_TABLE: \\label{{{lbl}}} has no \\autoref{{{lbl}}} in mainbody.tex"
                " — every table must be referenced in the body prose"
            )
            rc = E_STRUCTURE

    _emit("\n".join(lines) + "\n", ns.report)
    return rc


def cmd_fix_percent(ns: argparse.Namespace) -> int:
    """In-place escape bare % as \\% in non-comment lines of a .tex file.

    Skips lines whose non-whitespace content starts with % (pure comment lines).
    Writes the file back only when changes are made.
    """
    path = Path(ns.file)
    if not path.exists():
        _fail(E_PRECOND, f"file not found: {path}", "check the --file argument")
        return E_PRECOND

    original = path.read_text(encoding="utf-8", errors="replace")
    fixed, fix_details = _fix_percent_text(original)
    fix_count = len(fix_details)

    summary_lines = [f"fix_percent_replacements={fix_count}"]
    if fix_details:
        summary_lines.extend(fix_details)
        if not ns.dry_run:
            path.write_text(fixed, encoding="utf-8")
            summary_lines.append(f"written={path}")
        else:
            summary_lines.append("dry_run=true (no file written)")
    else:
        summary_lines.append("no_changes_needed")

    _emit("\n".join(summary_lines) + "\n", ns.report)
    return 0


def cmd_build_check_summary(ns: argparse.Namespace) -> int:
    """Read cites_audit.txt + checks_full.txt and write a compact check_summary.txt."""

    # ── helpers ────────────────────────────────────────────────────────────────

    def _read_file(path: str, label: str) -> str | None:
        if not path:
            print(f"WARNING: --{label} not provided; section will show 'none'", file=sys.stderr)
            return None
        p = Path(path)
        if not p.exists():
            print(f"WARNING: {label} file not found: {p}; section will show 'none'", file=sys.stderr)
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def _parse_py_list(value: str) -> list[str]:
        """Parse a Python repr list like "['a', 'b']" into a list of strings."""
        value = value.strip()
        if not value or value in ("[]", ""):
            return []
        # Remove surrounding brackets
        inner = re.sub(r"^\[|\]$", "", value).strip()
        if not inner:
            return []
        # Split on ', ' boundaries (handles simple string lists)
        items = re.findall(r"'([^']*)'", inner)
        if not items:
            # Fallback: comma split
            items = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
        return items

    def _extract_checks_sections(text: str) -> dict[str, str]:
        """Split checks_full.txt into named sections by '=== name (exit N) ===' headers."""
        sections: dict[str, str] = {}
        header_re = re.compile(r"^=== (\S+) \(exit \d+\) ===\s*$", re.M)
        matches = list(header_re.finditer(text))
        for i, m in enumerate(matches):
            name = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[name] = text[start:end]
        return sections

    # ── read inputs ────────────────────────────────────────────────────────────

    cites_text = _read_file(getattr(ns, "cites_audit", ""), "cites-audit")
    checks_text = _read_file(ns.checks_full, "checks-full")
    checks_sections = _extract_checks_sections(checks_text) if checks_text is not None else {}
    if cites_text is None:
        cites_text = checks_sections.get("cites")
    metadata_text = sys.stdin.read() if getattr(ns, "metadata_stdin", False) else ""

    # ── HALLUCINATED CITE KEYS ─────────────────────────────────────────────────

    hallucinated = "none"
    if cites_text is not None:
        for line in cites_text.splitlines():
            if line.startswith("missing_defined_keys="):
                raw = line[len("missing_defined_keys="):]
                items = _parse_py_list(raw)
                hallucinated = "\n".join(items) if items else "none"
                break

    # ── UNCITED LIBRARY PAPERS (informational only) ────────────────────────────

    uncited = "none"
    if cites_text is not None:
        for line in cites_text.splitlines():
            if line.startswith("unused_library_keys="):
                raw = line[len("unused_library_keys="):]
                items = _parse_py_list(raw)
                uncited = "\n".join(items) if items else "none"
                break

    # ── METADATA RISKS (WARN lines from cites section of checks_full) ──────────

    metadata_risks = "none"
    metadata_lines: list[str] = []
    if checks_text is not None:
        cites_section = checks_sections.get("cites", "")
        metadata_lines.extend(ln for ln in cites_section.splitlines() if ln.startswith("WARN:"))
    if metadata_text:
        metadata_patterns = (
            "TITLE_MISMATCH",
            "YEAR_MISMATCH",
            "VENUE_MISMATCH",
            "AUTHOR_MISMATCH",
            "METADATA_CHECK:",
            "SUMMARY:",
            "ERROR ",
            "WARN:",
        )
        metadata_lines.extend(
            ln.strip()
            for ln in metadata_text.splitlines()
            if ln.strip().startswith(metadata_patterns)
        )
    if metadata_lines:
        metadata_risks = "\n".join(metadata_lines)

    # ── STRUCTURE ISSUES ───────────────────────────────────────────────────────

    structure_issues = "none"
    begin_end_mismatches = "none"
    if checks_text is not None:
        struct_section = checks_sections.get("structure", "")
        issue_lines = []
        bem_lines = []
        for ln in struct_section.splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            # Count/header lines — skip
            if re.match(r"^(mainbody=|issue_count=)", stripped):
                continue
            if stripped.startswith("BEGIN_END_MISMATCH"):
                bem_lines.append(stripped)
            else:
                issue_lines.append(stripped)
        structure_issues = "\n".join(issue_lines) if issue_lines else "none"
        begin_end_mismatches = "\n".join(bem_lines) if bem_lines else "none"

    # ── BIB ISSUES ─────────────────────────────────────────────────────────────

    bib_issues = "none"
    has_dup_bib = False
    if checks_text is not None:
        bib_section = checks_sections.get("bib", "")
        bib_lines = []
        for ln in bib_section.splitlines():
            stripped = ln.strip()
            if not stripped:
                continue
            if stripped.startswith("duplicate_bib_keys=") or stripped.startswith("unescaped_ampersand"):
                bib_lines.append(stripped)
            # Include continuation lines for ampersand (e.g. "  line N: ...")
            elif bib_lines and bib_lines[-1].startswith("unescaped_ampersand"):
                bib_lines.append(stripped)
        bib_issues = "\n".join(bib_lines) if bib_lines else "none"
        # Check for actual duplicates
        for ln in bib_lines:
            if ln.startswith("duplicate_bib_keys="):
                val = ln[len("duplicate_bib_keys="):].strip()
                if val and val != "none":
                    has_dup_bib = True

    # ── LATEX HAZARDS ──────────────────────────────────────────────────────────

    latex_hazards = "none"
    if checks_text is not None:
        latex_section = checks_sections.get("latex", "")
        latex_lines = [
            ln for ln in latex_section.splitlines()
            if ln.strip() and ln.strip() != "(no latex heuristic hits)"
        ]
        latex_hazards = "\n".join(latex_lines) if latex_lines else "none"

    # ── WORD COUNT ─────────────────────────────────────────────────────────────

    word_count = "none"
    if checks_text is not None:
        words_section = checks_sections.get("words", "")
        for ln in words_section.splitlines():
            if ln.strip().startswith("TOTAL"):
                word_count = ln.strip()
                break

    # ── FIGURES / TABLES COUNT MISMATCH & UNREFERENCED FLOATS ─────────────────

    figures_tables_issues = "none"
    if checks_text is not None:
        ft_section = checks_sections.get("figures-tables", "")
        ft_issue_lines = [
            ln.strip()
            for ln in ft_section.splitlines()
            if ln.strip() and (
                "WARN" in ln
                or "ERROR_MISSING" in ln
                or "UNREFERENCED_" in ln
                or "FIGURE_BEFORE_FIRST_SECTION" in ln
            )
        ]
        if ft_issue_lines:
            figures_tables_issues = "\n".join(ft_issue_lines)

    # ── assemble output ────────────────────────────────────────────────────────

    output = (
        "=== HALLUCINATED CITE KEYS ===\n"
        "Keys used in \\cite{} but absent from papers.json — must be removed:\n"
        f"{hallucinated}\n"
        "\n"
        "=== UNCITED LIBRARY PAPERS ===\n"
        "Informational only: papers in papers.json that are not cited in mainbody.tex.\n"
        "Do NOT treat these as fix-pass issues; do NOT add citations merely to use them:\n"
        f"{uncited}\n"
        "\n"
        "=== METADATA RISKS ===\n"
        "Cited entries with unresolvable or partially missing metadata (author/year/venue):\n"
        f"{metadata_risks}\n"
        "\n"
        "=== STRUCTURE ISSUES ===\n"
        f"{structure_issues}\n"
        "\n"
        "=== BEGIN/END MISMATCHES ===\n"
        f"{begin_end_mismatches}\n"
        "\n"
        "=== BIB ISSUES ===\n"
        "duplicate_bib_keys and unescaped_ampersand lines:\n"
        f"{bib_issues}\n"
        "\n"
        "=== LATEX HAZARDS ===\n"
        f"{latex_hazards}\n"
        "\n"
        "=== FIGURES/TABLES ISSUES ===\n"
        "COUNT MISMATCH: actual figure/table count diverges from writing plan (diff > 1) — "
        "do NOT auto-add or remove environments in Step 5-B; report this for the visual "
        "asset workflow or update expected_*_total only after user-confirmed plan changes.\n"
        "UNREFERENCED_FIGURE / UNREFERENCED_TABLE: a \\label{} exists but no \\autoref{} "
        "references it in the body — add an \\autoref{} call in the surrounding prose:\n"
        f"{figures_tables_issues}\n"
        "\n"
        "=== WORD COUNT ===\n"
        f"{word_count}\n"
    )

    _write_report(ns.output, output)
    issue_count = sum(1 for value in (
        hallucinated,
        metadata_risks,
        structure_issues,
        begin_end_mismatches,
        bib_issues,
        latex_hazards,
        figures_tables_issues,
    ) if value != "none")
    print(
        f"SUMMARY_RESULT status={'fail' if has_dup_bib else 'ok'} "
        f"issues={issue_count} output={ns.output}"
    )

    if has_dup_bib:
        print(
            "E_BIB: duplicate_bib_keys found — user must fix before continuing",
            file=sys.stderr,
        )
        return E_BIB
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SurveyMaster survey_checks")
    subs = p.add_subparsers(dest="cmd", required=True)

    def add_tex_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--tex-dirs",
            default="",
            help="Semicolon-separated dirs (or single .tex) to scan recursively.",
        )
        sp.add_argument(
            "--extra-tex",
            default="",
            help="Extra .tex files semicolon-separated.",
        )
        sp.add_argument("--report", "-o", default="")
        sp.add_argument("--warn-only", action="store_true")

    pc = subs.add_parser("cites", help="Find cite keys missing from library/bib.")
    add_tex_args(pc)
    pc.add_argument("--library", default="", help="literature.json (paper array).")
    pc.add_argument("--bib", default="", help="references.bib")
    pc.add_argument(
        "--report-unused",
        action="store_true",
        help="List keys in library/bib not referenced (sample).",
    )
    pc.set_defaults(func=cmd_cites)

    pb = subs.add_parser("bib", help="Detect duplicate BibTeX entry keys.")
    pb.add_argument("--bib", required=True)
    pb.add_argument("--report", "-o", default="")
    pb.add_argument("--warn-only", action="store_true")
    pb.set_defaults(func=cmd_bib)

    pd_ = subs.add_parser("doi", help="Cross-check .bib DOI fields against papers.json.")
    pd_.add_argument("--bib", required=True)
    pd_.add_argument("--library", default="", help="papers.json path.")
    pd_.add_argument("--report", "-o", default="")
    pd_.add_argument("--warn-only", action="store_true")
    pd_.set_defaults(func=cmd_doi)

    pl = subs.add_parser("latex", help="Heuristic LaTeX hazard scan.")
    add_tex_args(pl)
    pl.set_defaults(func=cmd_latex)

    pw = subs.add_parser("words", help="Rough word count per tex + total.")
    add_tex_args(pw)
    pw.set_defaults(func=cmd_words)

    def cmd_all(ns: argparse.Namespace) -> int:
        """Run all checks and write a single unified report.

        Includes: structure, cites, bib, doi, latex, words.
        Each section is prefixed with a header line for easy parsing.
        Use --report-only/--compact to keep stdout to one summary line.
        """
        rc = 0
        sections: list[str] = []

        def capture(name: str, fn, sub_ns: argparse.Namespace) -> int:
            """Run fn(sub_ns) capturing stdout into a section block."""
            buf = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = buf
            try:
                code = fn(sub_ns)
            finally:
                sys.stdout = old_stdout
            out = buf.getvalue()
            sections.append(f"=== {name} (exit {code}) ===\n{out}")
            return code

        if ns.mainbody:
            ns_s = argparse.Namespace(
                mainbody=ns.mainbody,
                lang=ns.lang,
                outline=ns.outline,
                report="",
                warn_only=ns.warn_only,
            )
            rc = max(rc, capture("structure", cmd_structure, ns_s))

        if not ns.skip_cites:
            ns_c = argparse.Namespace(
                tex_dirs=ns.tex_dirs,
                extra_tex=ns.extra_tex,
                library=ns.library,
                bib=ns.bib,
                report="",
                report_unused=ns.report_unused,
                warn_only=ns.warn_only,
            )
            rc = max(rc, capture("cites", cmd_cites, ns_c))

        if ns.bib:
            ns_b = argparse.Namespace(bib=ns.bib, report="", warn_only=ns.warn_only)
            rc = max(rc, capture("bib", cmd_bib, ns_b))

            ns_d = argparse.Namespace(
                bib=ns.bib,
                library=ns.library,
                report="",
                warn_only=ns.warn_only,
            )
            rc = max(rc, capture("doi", cmd_doi, ns_d))

        ns_l = argparse.Namespace(
            tex_dirs=ns.tex_dirs,
            extra_tex=ns.extra_tex,
            report="",
            warn_only=ns.warn_only,
        )
        rc = max(rc, capture("latex", cmd_latex, ns_l))

        ns_w = argparse.Namespace(
            tex_dirs=ns.tex_dirs,
            extra_tex=ns.extra_tex,
            report="",
            warn_only=False,
        )
        rc = max(rc, capture("words", cmd_words, ns_w))

        if ns.mainbody and ns.outline:
            ns_ft = argparse.Namespace(
                mainbody=ns.mainbody,
                outline=ns.outline,
                report="",
            )
            rc = max(rc, capture("figures-tables", cmd_figures_tables, ns_ft))

        combined = "\n".join(sections)
        summary_rc = 0

        def maybe_build_summary() -> int:
            if not ns.summary_output:
                return 0
            if not ns.report:
                _fail(E_PRECOND, "--summary-output requires --report",
                      "pass --report so all-check sections can be summarized")
                return E_PRECOND
            old_stdin = sys.stdin
            if ns.metadata_stdin:
                sys.stdin = io.StringIO(sys.stdin.read())
            try:
                summary_ns = argparse.Namespace(
                    checks_full=ns.report,
                    cites_audit=ns.cites_audit,
                    metadata_stdin=ns.metadata_stdin,
                    output=ns.summary_output,
                )
                return cmd_build_check_summary(summary_ns)
            finally:
                sys.stdin = old_stdin

        if ns.report_only:
            _write_report(ns.report, combined)
            status = "ok" if rc == 0 else ("warn" if ns.warn_only else "fail")
            print(f"CHECK_RESULT status={status} code={rc} report={ns.report}")
        elif ns.compact:
            _write_report(ns.report, combined)
            status = "ok" if rc == 0 else ("warn" if ns.warn_only else "fail")
            print(f"CHECK_RESULT status={status} code={rc} report={ns.report}")
        else:
            _emit(combined, ns.report)
        summary_rc = maybe_build_summary()
        return max(rc, summary_rc)

    pa = subs.add_parser(
        "all",
        help="Run structure, cites, bib, doi, latex, words, figures-tables — write one unified report.",
    )
    add_tex_args(pa)
    pa.add_argument("--mainbody", "--tex", dest="mainbody", default="", help="Path to mainbody.tex (enables structure check).")
    pa.add_argument("--lang", default="", help="Survey language zh|en (for structure check).")
    pa.add_argument("--outline", default="", help="Optional outline.json for required section title checks.")
    pa.add_argument("--library", default="")
    pa.add_argument("--bib", default="")
    pa.add_argument("--report-unused", action="store_true")
    pa.add_argument("--skip-cites", action="store_true", help="Skip cites; useful when a prior cites report is already available.")
    pa.add_argument("--compact", action="store_true", help="Print one summary line instead of the full report.")
    pa.add_argument("--report-only", action="store_true", help="Write the full report to --report and keep stdout compact.")
    pa.add_argument("--summary-output", default="", help="Also write compact check_summary.txt after the all report.")
    pa.add_argument("--cites-audit", default="", help="Optional prior cites report used when building --summary-output.")
    pa.add_argument("--metadata-stdin", action="store_true", help="Read compact metadata diagnostics from stdin for --summary-output.")
    pa.set_defaults(func=cmd_all)

    pcs = subs.add_parser(
        "build-check-summary",
        help="Build compact LLM-readable check_summary.txt from a full checks report.",
    )
    pcs.add_argument("--checks-full", required=True, help="Path to survey_checks.py all report.")
    pcs.add_argument("--cites-audit", default="", help="Optional older cites report; checks-full is used when omitted.")
    pcs.add_argument("--metadata-stdin", action="store_true", help="Read compact metadata diagnostics from stdin.")
    pcs.add_argument("--output", required=True, help="Path to write check_summary.txt.")
    pcs.set_defaults(func=cmd_build_check_summary)

    prs = subs.add_parser(
        "repair-structure",
        help="Repair deterministic TeX noise in place, then check structure.",
    )
    prs.add_argument("--mainbody", "--tex", dest="mainbody", required=True, help="Path to mainbody.tex")
    prs.add_argument("--lang", default="", help="Survey language (zh|en); enables language-consistency checks")
    prs.add_argument("--outline", default="", help="Optional outline.json for required section title checks.")
    prs.add_argument("--report", "-o", default="")
    prs.add_argument("--warn-only", action="store_true")
    prs.set_defaults(func=cmd_repair_structure)

    pfp = subs.add_parser("fix-percent", help="In-place escape bare %% as \\%% in non-comment lines.")
    pfp.add_argument("--file", required=True, help="Path to .tex file to fix in place.")
    pfp.add_argument("--dry-run", action="store_true", help="Report changes but do not write.")
    pfp.add_argument("--report", "-o", default="")
    pfp.set_defaults(func=cmd_fix_percent)

    ps = subs.add_parser("structure", help="Check mainbody.tex has abstract, keywords, and sections.")
    ps.add_argument("--mainbody", "--tex", dest="mainbody", required=True, help="Path to mainbody.tex")
    ps.add_argument("--lang", default="", help="Survey language (zh|en); enables language-consistency checks")
    ps.add_argument("--outline", default="", help="Optional outline.json for required section title checks.")
    ps.add_argument("--report", "-o", default="")
    ps.add_argument("--warn-only", action="store_true")
    ps.set_defaults(func=cmd_structure)

    pft = subs.add_parser("figures-tables", help="Compare actual figure/table counts against expected_*_total in outline.json.")
    pft.add_argument("--mainbody", "--tex", dest="mainbody", required=True, help="Path to mainbody.tex")
    pft.add_argument("--outline", default="", help="Path to outline.json (provides expected counts).")
    pft.add_argument("--report", "-o", default="")
    pft.set_defaults(func=cmd_figures_tables)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    ns = p.parse_args(argv)
    try:
        return int(ns.func(ns))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _fail(E_PRECOND, str(exc), "check file paths and permissions")
        return E_PRECOND


if __name__ == "__main__":
    raise SystemExit(main())
