"""Save a survey outline JSON to file (no LLM calls).

Writes two files from a single invocation:
  <output>                   — normalized outline.json (source of truth for scripts)
  <output-parent>/outline.md — human-readable rich view

Usage:
    python3 scripts/save_outline.py \\
        --file <work-dir>/outline.json

    --file: path to a JSON file containing survey_title, language, and the
        sections (or outline) array. The file is normalized in place, and
        outline.md is written beside it. JSON content is read fully before
        output is written, so a parse failure leaves the input file untouched.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Exit codes (shared across all SurveyMaster scripts)
E_WARN = 1
E_PRECOND = 10   # missing file / bad argument / I/O error
E_STRUCTURE = 11 # empty or invalid output


def _fail(code: int, description: str, fix: str) -> None:
    print(f"[E{code}] {description}", file=sys.stderr)
    print(f"       Fix: {fix}", file=sys.stderr)


# ---------------------------------------------------------------------------
# JSON repair helpers
# ---------------------------------------------------------------------------

def _normalize_json_punctuation_outside_strings(text: str) -> str:
    """Normalize common fullwidth JSON structural punctuation outside strings."""
    punctuation_map = {
        "\ufeff": "",
        "｛": "{",
        "｝": "}",
        "［": "[",
        "］": "]",
        "：": ":",
        "，": ",",
    }
    result: list[str] = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            result.append(ch)
            if ch == "\\":
                i += 1
                if i < len(text):
                    result.append(text[i])
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
                result.append(ch)
            else:
                result.append(punctuation_map.get(ch, ch))
        i += 1
    return "".join(result)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json|JSON)?\s*\n(?P<body>[\s\S]*?)\n```\s*$", stripped)
    return fence.group("body").strip() if fence else stripped


def _extract_balanced_json(text: str) -> str:
    """Extract the first balanced JSON object/array from surrounding prose."""
    data = _strip_code_fence(_normalize_json_punctuation_outside_strings(text))
    if not data:
        return data
    if data[0] in "{[":
        return data

    start = min((idx for idx in (data.find("{"), data.find("[")) if idx >= 0), default=-1)
    if start < 0:
        return data

    stack: list[str] = []
    in_string = False
    i = start
    while i < len(data):
        ch = data[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append("}" if ch == "{" else "]")
            elif ch in "}]":
                if not stack or ch != stack[-1]:
                    return data[start:]
                stack.pop()
                if not stack:
                    return data[start:i + 1].strip()
        i += 1
    return data[start:].strip()


def _replace_curly_quotes_in_strings(text: str) -> str:
    """Replace Chinese/typographic curly quotes inside JSON string values.

    LLMs occasionally emit “/” (‘/’) inside JSON string
    values, which breaks json.loads.  We replace them with escaped straight
    double-quotes so the JSON remains syntactically valid.

    Strategy: scan character-by-character tracking whether we are inside a
    JSON string literal.  Only replace “/” (‘/’) when
    inside a string, leaving structural characters untouched.
    """
    OPEN_DOUBLE = '“'   # "
    CLOSE_DOUBLE = '”'  # "
    OPEN_SINGLE = '‘'   # '
    CLOSE_SINGLE = '’'  # '
    CURLY_QUOTES = {OPEN_DOUBLE, CLOSE_DOUBLE, OPEN_SINGLE, CLOSE_SINGLE}

    result = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == '\\':
                # Escaped character — copy both chars and skip
                result.append(ch)
                i += 1
                if i < len(text):
                    result.append(text[i])
                    i += 1
                continue
            if ch == '"':
                in_string = False
                result.append(ch)
                i += 1
                continue
            if ch in CURLY_QUOTES:
                # Replace curly quote with escaped straight double-quote
                result.append('\\"')
                i += 1
                continue
        else:
            if ch == '"':
                in_string = True
        result.append(ch)
        i += 1
    return ''.join(result)


def _try_parse_json(data: str) -> tuple[Any, bool]:
    """Try json.loads; fall back to json_repair if available.

    Returns (parsed_object, was_repaired).
    Raises json.JSONDecodeError if all strategies fail.
    """
    # Step 1: direct parse
    try:
        return json.loads(data), False
    except json.JSONDecodeError:
        pass

    # Step 2: remove code fences/surrounding prose and normalize fullwidth
    # JSON structural punctuation outside string values.
    extracted = _extract_balanced_json(data)
    try:
        obj = json.loads(extracted)
        print(
            "WARNING: input JSON contained code fences, surrounding text, or "
            "fullwidth structural punctuation; auto-normalized before parsing.",
            file=sys.stderr,
        )
        return obj, True
    except json.JSONDecodeError:
        pass

    # Step 3: replace curly quotes inside string values and retry
    cleaned = _replace_curly_quotes_in_strings(extracted)
    try:
        obj = json.loads(cleaned)
        print(
            "WARNING: input JSON contained curly/typographic quotes inside string values; "
            "auto-replaced with straight double-quotes.",
            file=sys.stderr,
        )
        return obj, True
    except json.JSONDecodeError:
        pass

    # Step 4: try json_repair (handles broader malformed JSON)
    try:
        import json_repair  # type: ignore[import]
        obj = json_repair.repair_json(cleaned, return_objects=True)
        if obj:
            print(
                "INFO: input JSON was malformed and was auto-repaired by json_repair.",
                file=sys.stderr,
            )
            return obj, True
    except ImportError:
        pass

    # All strategies failed — re-raise the original error
    json.loads(data)  # will raise JSONDecodeError
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

def normalize_language(value: object, fallback: str = "zh") -> str:
    fb = fallback if fallback in ("zh", "en") else "zh"
    if value is None:
        return fb
    s = str(value).strip().lower()
    if not s:
        return fb
    if s in ("zh", "zh-cn", "zh_cn", "chinese", "中文", "cn") or s.startswith("zh"):
        return "zh"
    if s in ("en", "en-us", "en_us", "english", "英文") or s.startswith("en"):
        return "en"
    return fb


def _as_int(value: object, default: int = -1) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _entry_type_for_level(raw_type: object, level: int) -> str:
    explicit = str(raw_type or "").strip()
    if explicit:
        return explicit
    if level <= 0:
        return "section"
    if level == 1:
        return "subsection"
    return "subsubsection"


# ---------------------------------------------------------------------------
# Input normalisation
# ---------------------------------------------------------------------------

def _build_nested(flat_items: list[dict]) -> list[dict]:
    """Convert a flat list with parent_index references into a nested list with subsections.

    Used when input comes from an existing outline.json (flat format with "outline" key)
    rather than from the model's nested generation format (with "sections" key).
    """
    items_copy = [dict(item) for item in flat_items if isinstance(item, dict)]
    by_index: dict[Any, dict] = {}
    for item in items_copy:
        idx = item.get("index")
        if idx is not None:
            by_index[idx] = item

    roots: list[dict] = []
    for item in items_copy:
        parent = item.get("parent_index")
        if parent is None:
            roots.append(item)
        else:
            parent_item = by_index.get(parent)
            if parent_item is not None:
                parent_item.setdefault("subsections", []).append(item)
            else:
                roots.append(item)  # orphaned → treat as top-level
    return roots


def _extract_section_list(raw: object) -> list:
    """Extract the sections list from various input shapes."""
    if isinstance(raw, dict):
        if "sections" in raw:
            return raw.get("sections") or []
        if "outline" in raw:
            # Flat format from an existing outline.json — rebuild nested structure first.
            flat = raw.get("outline") or []
            return _build_nested(flat) if isinstance(flat, list) else []
        return []
    if isinstance(raw, list):
        return raw
    return []


# ---------------------------------------------------------------------------
# Normalisation + rich-field extraction
# ---------------------------------------------------------------------------

def normalize_outline(raw: object) -> list[dict]:
    """Return normalized flat outline entries.

    Each returned entry contains the structural fields plus rich writing fields:
    core_claim, length_target, and key_papers. This makes outline.json the only
    machine-readable source of truth for downstream writing and checking stages.
    """
    section_list = _extract_section_list(raw)

    flat: list[dict] = []
    next_index = 1
    used_indices: set[int] = set()
    resolved_indices: dict[int, int] = {}

    if not isinstance(section_list, Iterable):
        return flat

    def _next_unused() -> int:
        nonlocal next_index
        while next_index in used_indices:
            next_index += 1
        assigned = next_index
        used_indices.add(assigned)
        next_index += 1
        return assigned

    def _assign_index(raw_index: object) -> int:
        nonlocal next_index
        parsed: int | None = None
        try:
            parsed = int(raw_index)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None and parsed >= 0 and parsed not in used_indices:
            used_indices.add(parsed)
            next_index = max(next_index, parsed + 1)
            resolved_indices[parsed] = parsed
            return parsed
        assigned = _next_unused()
        if parsed is not None and parsed >= 0:
            resolved_indices[parsed] = assigned
        return assigned

    def _append(items: Iterable, parent_index: int | None, level: int) -> None:
        for fallback_idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            entry_index = _assign_index(item.get("index"))
            entry_type = _entry_type_for_level(item.get("type"), level)
            default_title = "Section" if level == 0 else "Subsection"
            row_parent = parent_index
            if row_parent is None:
                raw_p = item.get("parent_index")
                if raw_p is not None:
                    p = _as_int(raw_p, default=-1)
                    row_parent = None if p < 0 else resolved_indices.get(p, p)
            row: dict = {
                "index": entry_index,
                "title": str(item.get("title", "") or f"{default_title} {fallback_idx}").strip(),
                "type": entry_type,
                "description": str(item.get("description", "") or "").strip(),
                "parent_index": row_parent,
            }
            if "paper_ids" in item and item["paper_ids"] is not None:
                row["paper_ids"] = item["paper_ids"]

            if item.get("core_claim"):
                row["core_claim"] = str(item["core_claim"]).strip()
            if item.get("length_target") is not None:
                row["length_target"] = item["length_target"]
            kp = item.get("key_papers")
            row["key_papers"] = kp if isinstance(kp, list) else []
            pf = item.get("planned_figures")
            if isinstance(pf, list) and pf:
                row["planned_figures"] = [
                    {"type": str(f.get("type", "")).strip()}
                    for f in pf
                    if isinstance(f, dict) and f.get("type")
                ]
            pt = item.get("planned_tables")
            if isinstance(pt, list) and pt:
                row["planned_tables"] = [
                    {"type": str(t.get("type", "")).strip()}
                    for t in pt
                    if isinstance(t, dict) and t.get("type")
                ]

            flat.append(row)

            children = item.get("subsections")
            if isinstance(children, list):
                _append(children, entry_index, level + 1)

    _append(section_list, None, 0)
    return flat


def strip_abstract_entries(flat: list[dict]) -> list[dict]:
    return [
        e for e in flat
        if str(e.get("type") or "section").strip().lower() not in ("abstract",)
    ]


def default_paper_ids(flat: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for entry in flat:
        item = dict(entry)
        item.pop("relevant_papers", None)
        typ = str(item.get("type") or "section").strip()
        if "paper_ids" in item and item["paper_ids"] is not None:
            enriched.append(item)
            continue
        if typ in {"subsection", "subsubsection", "abstract"}:
            item["paper_ids"] = []
        else:
            item["paper_ids"] = "all"
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _render_length_target(lt: Any) -> str:
    if not lt:
        return "(not set)"
    if isinstance(lt, dict):
        parts = []
        if "zh_chars" in lt:
            parts.append(f"{lt['zh_chars']} zh chars")
        if "en_words" in lt:
            parts.append(f"{lt['en_words']} en words")
        return ", ".join(parts) if parts else json.dumps(lt)
    return str(lt)


def render_rich_markdown(
    survey_title: str,
    language: str,
    flat: list[dict],
    expected_figures: int = 0,
    expected_tables: int = 0,
) -> str:
    """Render outline.md from rich fields embedded in outline.json entries."""
    total = len(flat)
    lines = [
        f"# {survey_title}",
        "",
        f" > Language: {language} · {total} 部分" if language == "zh" else f"> Language: {language} · {total} sections"
        "",
    ]

    entries_by_parent: dict[int | None, list[dict]] = {}
    for entry in flat:
        parent = entry.get("parent_index")
        try:
            parent_key: int | None = None if parent is None else int(parent)
        except (TypeError, ValueError):
            parent_key = None
        entries_by_parent.setdefault(parent_key, []).append(entry)
    for entries in entries_by_parent.values():
        entries.sort(key=lambda e: int(e.get("index") or 0))

    def render(parent: int | None, prefix: str = "") -> None:
        for pos, entry in enumerate(entries_by_parent.get(parent, []), start=1):
            number = f"{prefix}.{pos}" if prefix else str(pos)
            title_text = str(entry.get("title") or "").strip() or "Untitled"
            description = str(entry.get("description") or "").strip()

            level = min(number.count(".") + 2, 6)
            lines.append(f"{'#' * level} {number}. {title_text}")
            lines.append("")

            core_claim = str(entry.get("core_claim") or "").strip()
            lt_str = _render_length_target(entry.get("length_target"))

            lines.append(f"- **核心**: {core_claim or '(未确定核心论点)'}" if language == "zh" else f"- **Core claim**: {core_claim or '(no core claim)'}" )
            lines.append(f"- **长度目标**: {lt_str}" if language == "zh" else f"- **Length target**: {lt_str}" )
            lines.append(f"- **描述**: {description or '(未确定描述)'}" if language == "zh" else f"- **Description**: {description or '(no description)'}" )

            _fig_type_zh = {
                "concept_illustration": "概念示意图",
                "architecture_diagram": "架构图",
                "workflow_diagram": "流程图",
                "comparison_visual": "对比图",
                "timeline_visual": "时间线图",
            }
            _tbl_type_zh = {
                "performance_comparison": "性能对比表",
                "classification_comparison": "分类对比表",
                "challenge_strategy_matrix": "挑战-策略矩阵",
            }

            planned_figures = entry.get("planned_figures")
            if isinstance(planned_figures, list) and planned_figures:
                if language == "zh":
                    types_str = ", ".join(
                        _fig_type_zh.get(str(f["type"]), str(f["type"]))
                        for f in planned_figures
                        if isinstance(f, dict) and f.get("type")
                    )
                    label = "图"
                else:
                    types_str = ", ".join(
                        str(f["type"]) for f in planned_figures if isinstance(f, dict) and f.get("type")
                    )
                    label = "Figures"
                if types_str:
                    lines.append(f"- **{label}**: {types_str}")

            planned_tables = entry.get("planned_tables")
            if isinstance(planned_tables, list) and planned_tables:
                if language == "zh":
                    types_str = ", ".join(
                        _tbl_type_zh.get(str(t["type"]), str(t["type"]))
                        for t in planned_tables
                        if isinstance(t, dict) and t.get("type")
                    )
                    label = "表"
                else:
                    types_str = ", ".join(
                        str(t["type"]) for t in planned_tables if isinstance(t, dict) and t.get("type")
                    )
                    label = "Tables"
                if types_str:
                    lines.append(f"- **{label}**: {types_str}")

            lines.append("")

            try:
                idx = int(entry.get("index"))
                render(idx, number)
            except (TypeError, ValueError):
                pass

    render(None)

    if expected_figures > 0 or expected_tables > 0:
        lines.append("")
        if language == "zh":
            lines.append("## 图表规划")
            lines.append("")
            lines.append(f"预期：共 {expected_figures} 图、{expected_tables} 表（由写作阶段按节内容决定具体位置）")
        else:
            lines.append("## Visual Assets")
            lines.append("")
            lines.append(f"Expected: {expected_figures} figure(s), {expected_tables} table(s) — exact placement decided during section writing.")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Script logic
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/save_outline.py",
        description=(
            "Normalize outline JSON and write outline.json and outline.md "
            "in a single invocation."
        ),
    )
    parser.add_argument(
        "--file",
        required=True,
        help=(
            "Path to a JSON file containing survey_title, language, and the "
            "sections (or outline) array. The file is normalized in place."
        ),
    )
    parser.add_argument(
        "--language", default="en",
        help="Fallback language if not present in --file content (default: en)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    try:
        data_str = Path(args.file).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        _fail(
            E_PRECOND,
            f"cannot read --file {args.file!r}: {exc}",
            "check that the file path is correct and readable",
        )
        sys.exit(E_PRECOND)

    try:
        raw, _repaired = _try_parse_json(data_str)
    except json.JSONDecodeError as exc:
        _fail(
            E_PRECOND,
            f"--file {args.file!r} content is not valid JSON: {exc}",
            "check JSON syntax; ensure the LLM output is complete and not truncated",
        )
        sys.exit(E_PRECOND)

    if isinstance(raw, dict):
        survey_title = str(raw.get("survey_title") or "").strip()
        language = normalize_language(raw.get("language") or args.language, fallback="zh")
    else:
        survey_title = ""
        language = normalize_language(args.language, fallback="zh")

    flat_raw = normalize_outline(raw)

    flat = default_paper_ids(strip_abstract_entries(flat_raw))

    if not flat:
        _fail(E_STRUCTURE, "normalized outline is empty; refusing to write outline files",
              "check that the LLM output contains a non-empty sections or outline array")
        sys.exit(E_STRUCTURE)

    output_path = Path(args.file)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Warn about missing core_claim (hard error deferred to section-writing stage).
    missing_claims = sorted(
        (str(e["index"]) for e in flat if not e.get("core_claim")),
        key=lambda x: int(x) if x.isdigit() else 0,
    )
    if missing_claims:
        print(
            f"WARNING: core_claim missing for indices {missing_claims}. "
            "Fill these in before section writing.",
            file=sys.stderr,
        )

    # --- Write outline.json ---
    result: dict[str, Any] = {
        "survey_title": survey_title,
        "language": language,
        "outline": flat,
    }
    if isinstance(raw, dict):
        constraints = raw.get("writing_constraints") or raw.get("constraints_summary")
        if constraints:
            result["writing_constraints"] = constraints
        _count_defaults = {"expected_figures_total": 3, "expected_tables_total": 2}
        for key, default in _count_defaults.items():
            v = raw.get(key)
            result[key] = v if isinstance(v, int) and v >= 0 else default
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Write outline.md ---
    md_out = output_dir / "outline.md"
    expected_figures = result.get("expected_figures_total", 0)
    expected_tables = result.get("expected_tables_total", 0)
    md_out.write_text(
        render_rich_markdown(survey_title, language, flat, expected_figures, expected_tables),
        encoding="utf-8",
    )

    n_top = sum(
        1 for e in flat
        if str(e.get("type") or "section").strip().lower()
        not in ("subsection", "subsubsection")
    )
    print(
        f"Saved outline: {len(flat)} entries ({n_top} top-level) "
        f"→ {output_path.resolve()}"
    )
    print(f"  outline.md        → {md_out.resolve()}")


if __name__ == "__main__":
    main()
