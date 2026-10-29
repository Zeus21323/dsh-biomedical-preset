#!/usr/bin/env python3
"""Validate Bioinformatics Writer manuscript planning and export inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


DEFAULT_LENGTH_MINIMUMS = {
    "main_text": 3200,
    "abstract": 180,
    "introduction": 600,
    "methods": 800,
    "methods_subsection": 100,
    "results": 900,
    "results_subsection": 150,
    "discussion": 700,
    "conclusion": 100,
    "figure_legend": 60,
}

SECTION_ALIASES = {
    "introduction": ("introduction", "background", "引言", "前言"),
    "methods": (
        "methods", "materials and methods", "methodology", "experimental procedures",
        "study methods", "方法", "材料与方法", "实验方法",
    ),
    "results": ("results", "result", "findings", "结果", "主要结果"),
    "discussion": ("discussion", "讨论"),
    "conclusion": (
        "conclusion", "conclusions", "summary", "summary and outlook",
        "concluding remarks", "结论", "总结", "总结与展望",
    ),
}

COMBINED_SECTION_ALIASES = {
    "results and discussion": ("results", "discussion"),
    "results discussion": ("results", "discussion"),
    "结果与讨论": ("results", "discussion"),
    "discussion and conclusions": ("discussion", "conclusion"),
    "discussion conclusions": ("discussion", "conclusion"),
    "讨论与结论": ("discussion", "conclusion"),
}

ABSTRACT_ALIASES = {"abstract", "summary", "摘要"}

ADMINISTRATIVE_SUBSECTIONS = {
    "data availability", "code availability", "ethics statement", "ethical approval",
    "author contributions", "funding", "competing interests", "conflict of interest",
    "数据可用性", "代码可用性", "伦理声明", "作者贡献", "基金资助", "利益冲突",
}


def load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{label} not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(nonempty(item) for item in value):
        return None
    return [str(item).strip() for item in value]


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return float(value)


def length_enforcement(plan: dict) -> str:
    policy = plan.get("length_policy")
    if not isinstance(policy, dict):
        return "advisory"
    return str(policy.get("enforcement", "advisory")).strip().lower()


def length_policy_minimums(plan: dict) -> tuple[dict[str, float], list[str]]:
    errors: list[str] = []
    policy = plan.get("length_policy")
    if not isinstance(policy, dict):
        return dict(DEFAULT_LENGTH_MINIMUMS), ["manuscript plan missing length_policy object"]
    if str(policy.get("unit", "")).strip().lower() != "word_equivalents":
        errors.append("length_policy.unit must be word_equivalents")
    enforcement = length_enforcement(plan)
    if enforcement not in {"advisory", "strict"}:
        errors.append("length_policy.enforcement must be advisory or strict")
    supplied = policy.get("minimums")
    if not isinstance(supplied, dict):
        return dict(DEFAULT_LENGTH_MINIMUMS), errors + ["length_policy.minimums must be an object"]

    resolved: dict[str, float] = {}
    lower_than_default: list[str] = []
    for key, default in DEFAULT_LENGTH_MINIMUMS.items():
        value = positive_number(supplied.get(key))
        if value is None:
            errors.append(f"length_policy.minimums.{key} must be a positive number")
            value = float(default)
        resolved[key] = value
        if value < default:
            lower_than_default.append(key)

    if lower_than_default and enforcement == "strict":
        override = policy.get("journal_override")
        if not isinstance(override, dict) or not nonempty(override.get("source")) or not nonempty(override.get("rationale")):
            errors.append(
                "length minimums below the biomedical default require journal_override.source and journal_override.rationale: "
                + ", ".join(lower_than_default)
            )
    return resolved, errors


def validate_plan(
    root: Path, plan: dict, results_map: dict, figure_blueprint: dict,
    evidence_inventory: dict, require_approved: bool
) -> list[str]:
    errors: list[str] = []
    for field in (
        "title", "article_type", "language", "target_journal", "guidelines_source",
        "citation_style", "citation_mode", "citation_export_mode",
        "citation_presentation",
    ):
        if not nonempty(plan.get(field)):
            errors.append(f"manuscript plan missing non-empty {field}")

    status = str(plan.get("approval_status", "")).strip().lower()
    if status not in {"pending", "approved", "revised"}:
        errors.append("manuscript plan approval_status must be pending, approved, or revised")
    if require_approved and status != "approved":
        errors.append(f"manuscript plan is not approved: {status or 'missing'}")
    if str(plan.get("citation_mode", "")).strip().lower() not in {"numeric", "author_date"}:
        errors.append("manuscript plan citation_mode must be numeric or author_date")
    if str(plan.get("citation_export_mode", "")).strip().lower() not in {
        "strict_linked",
        "bibliography_compatibility",
    }:
        errors.append(
            "manuscript plan citation_export_mode must be strict_linked or "
            "bibliography_compatibility"
        )
    length_minimums, length_errors = length_policy_minimums(plan)
    errors.extend(length_errors)
    strict_length = length_enforcement(plan) == "strict"

    questions = results_map.get("results_questions")
    if not isinstance(questions, list) or not questions:
        errors.append("results map has no results_questions")
        questions = []
    rq_ids = {str(item.get("id", "")).strip() for item in questions if isinstance(item, dict)}
    rq_ids.discard("")

    figures = figure_blueprint.get("figures")
    if not isinstance(figures, list) or not figures:
        errors.append("figure blueprint has no figures")
        figures = []
    figure_ids = {
        str(item.get("figure_id", "")).strip() for item in figures if isinstance(item, dict)
    }
    figure_ids.discard("")

    evidence_items = evidence_inventory.get("evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        errors.append("evidence inventory has no evidence records")
        evidence_items = []
    evidence_by_id: dict[str, dict] = {}
    for index, item in enumerate(evidence_items, start=1):
        if not isinstance(item, dict) or not nonempty(item.get("claim_id")):
            errors.append(f"evidence[{index}] missing claim_id")
            continue
        claim_id = str(item["claim_id"]).strip()
        evidence_by_id[claim_id] = item
        sources = string_list(item.get("source_files"))
        if sources is None or not sources:
            errors.append(f"evidence {claim_id} requires source_files")
        else:
            for raw in sources:
                if not resolve(root, raw).is_file():
                    errors.append(f"evidence {claim_id} source file missing: {raw}")
        if str(item.get("status", "")).strip().lower() not in {"verified", "missing", "inconsistent"}:
            errors.append(f"evidence {claim_id} has invalid status")

    sections = plan.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("manuscript plan has no sections")
        return errors

    section_types: set[str] = set()
    allocated_lengths: Counter[str] = Counter()
    methods_sections_without_breakdown: list[str] = []
    mapped_rqs: list[str] = []
    mapped_figures: list[str] = []
    for index, section in enumerate(sections, start=1):
        prefix = f"sections[{index}]"
        if not isinstance(section, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in ("section_id", "heading", "purpose"):
            if not nonempty(section.get(field)):
                errors.append(f"{prefix} missing non-empty {field}")
        section_id = str(section.get("section_id", "")).strip().lower()
        section_type = str(section.get("section_type", "")).strip().lower()
        if not section_type:
            section_type = section_id.split("_", 1)[0].split("-", 1)[0]
        section_types.add(section_type)
        minimum_length = positive_number(section.get("minimum_word_equivalents"))
        if minimum_length is None:
            errors.append(f"{prefix}.minimum_word_equivalents must be a positive number")
            minimum_length = 0
        allocated_lengths[section_type] += minimum_length
        if strict_length and section_type == "methods" and minimum_length < length_minimums["methods_subsection"]:
            errors.append(
                f"{prefix} Methods allocation {minimum_length:g} is below methods_subsection minimum "
                f"{length_minimums['methods_subsection']:g}"
            )
        if section_type == "methods":
            subsections = section.get("subsections")
            if subsections is None:
                methods_sections_without_breakdown.append(prefix)
            elif not isinstance(subsections, list) or not subsections:
                errors.append(f"{prefix}.subsections must be a non-empty array for a consolidated Methods section")
            else:
                subsection_total = 0.0
                for sub_index, subsection in enumerate(subsections, start=1):
                    sub_prefix = f"{prefix}.subsections[{sub_index}]"
                    if not isinstance(subsection, dict) or not nonempty(subsection.get("heading")):
                        errors.append(f"{sub_prefix} must contain a non-empty heading")
                        continue
                    sub_length = positive_number(subsection.get("minimum_word_equivalents"))
                    if sub_length is None:
                        errors.append(f"{sub_prefix}.minimum_word_equivalents must be a positive number")
                        continue
                    subsection_total += sub_length
                    normalized = str(subsection["heading"]).strip().casefold()
                    if (
                        strict_length
                        and normalized not in ADMINISTRATIVE_SUBSECTIONS
                        and sub_length < length_minimums["methods_subsection"]
                    ):
                        errors.append(
                            f"{sub_prefix} allocation {sub_length:g} is below methods_subsection minimum "
                            f"{length_minimums['methods_subsection']:g}"
                        )
                if subsection_total < minimum_length:
                    errors.append(
                        f"{prefix} Methods subsection allocation {subsection_total:g} is below section allocation "
                        f"{minimum_length:g}"
                    )
        if strict_length and section_type == "results" and minimum_length < length_minimums["results_subsection"]:
            errors.append(
                f"{prefix} Results allocation {minimum_length:g} is below results_subsection minimum "
                f"{length_minimums['results_subsection']:g}"
            )

        section_rqs = string_list(section.get("result_question_ids", []))
        section_figures = string_list(section.get("figure_ids", []))
        section_evidence_ids = string_list(section.get("evidence_ids", []))
        evidence = string_list(section.get("evidence_files", []))
        if section_rqs is None:
            errors.append(f"{prefix}.result_question_ids must be a string array")
            section_rqs = []
        if section_figures is None:
            errors.append(f"{prefix}.figure_ids must be a string array")
            section_figures = []
        if section_evidence_ids is None:
            errors.append(f"{prefix}.evidence_ids must be a string array")
            section_evidence_ids = []
        if evidence is None:
            errors.append(f"{prefix}.evidence_files must be a string array")
            evidence = []

        mapped_rqs.extend(section_rqs)
        mapped_figures.extend(section_figures)
        for raw in evidence:
            if not resolve(root, raw).is_file():
                errors.append(f"{prefix} evidence file missing: {raw}")
        if section_type == "results":
            for field in ("claims", "statistics", "limitations"):
                if string_list(section.get(field)) is None:
                    errors.append(f"{prefix}.{field} must be a non-empty string array")
            if not section_rqs or not section_figures or not evidence or not section_evidence_ids:
                errors.append(f"{prefix} Results section requires RQ, figure, and evidence mappings")
            for claim_id in section_evidence_ids:
                item = evidence_by_id.get(claim_id)
                if item is None:
                    errors.append(f"{prefix} references unknown evidence id: {claim_id}")
                elif str(item.get("status", "")).strip().lower() != "verified":
                    errors.append(f"{prefix} uses evidence {claim_id} with non-verified status")

    required_types = {"introduction", "methods", "results", "discussion", "conclusion"}
    missing_types = sorted(required_types - section_types)
    if missing_types:
        errors.append("manuscript plan missing section types: " + ", ".join(missing_types))
    if len(methods_sections_without_breakdown) == 1 and allocated_lengths["methods"] >= length_minimums["methods"]:
        errors.append(
            f"{methods_sections_without_breakdown[0]} is a consolidated Methods section and must list every substantive subsection with its minimum_word_equivalents"
        )
    if strict_length:
        for section_type in sorted(required_types):
            required = length_minimums[section_type]
            actual = allocated_lengths[section_type]
            if actual < required:
                errors.append(
                    f"planned {section_type} allocation {actual:g} is below required {required:g} word-equivalents"
                )
        main_allocated = sum(allocated_lengths[item] for item in required_types)
        if main_allocated < length_minimums["main_text"]:
            errors.append(
                f"planned main-text allocation {main_allocated:g} is below required "
                f"{length_minimums['main_text']:g} word-equivalents"
            )

    rq_counts = Counter(mapped_rqs)
    for rq_id in sorted(rq_ids):
        if rq_counts[rq_id] != 1:
            errors.append(f"result question {rq_id} must map to exactly one section; found {rq_counts[rq_id]}")
    unknown_rqs = sorted(set(mapped_rqs) - rq_ids)
    if unknown_rqs:
        errors.append("manuscript plan references unknown result questions: " + ", ".join(unknown_rqs))

    for figure_id in sorted(figure_ids):
        if figure_id not in mapped_figures:
            errors.append(f"figure {figure_id} is not mapped in manuscript plan")
    unknown_figures = sorted(set(mapped_figures) - figure_ids)
    if unknown_figures:
        errors.append("manuscript plan references unknown figures: " + ", ".join(unknown_figures))
    return errors


def validate_citation_preference(path: Path, plan: dict, require_approved: bool) -> list[str]:
    try:
        preference = load_json(path, "citation preference")
    except ValueError as exc:
        return [str(exc)]

    errors: list[str] = []
    for field in (
        "citation_style", "citation_mode", "citation_export_mode",
        "in_text_presentation", "csl",
        "selection_source", "user_response", "target_journal",
    ):
        if not nonempty(preference.get(field)):
            errors.append(f"citation preference missing non-empty {field}")

    mode = str(preference.get("citation_mode", "")).strip().lower()
    if mode not in {"numeric", "author_date"}:
        errors.append("citation preference citation_mode must be numeric or author_date")
    export_mode = str(preference.get("citation_export_mode", "")).strip().lower()
    if export_mode not in {"strict_linked", "bibliography_compatibility"}:
        errors.append(
            "citation preference citation_export_mode must be strict_linked or "
            "bibliography_compatibility"
        )
    source = str(preference.get("selection_source", "")).strip().lower()
    if source not in {"ask_user", "direct_chat"}:
        errors.append(
            "citation preference selection_source must be ask_user or direct_chat"
        )
    if require_approved and preference.get("approved_in_current_conversation") is not True:
        errors.append("citation preference was not approved in the current conversation")

    comparisons = (
        ("citation_style", "citation_style"),
        ("citation_mode", "citation_mode"),
        ("citation_export_mode", "citation_export_mode"),
        ("in_text_presentation", "citation_presentation"),
        ("target_journal", "target_journal"),
    )
    for preference_key, plan_key in comparisons:
        selected = str(preference.get(preference_key, "")).strip().casefold()
        planned = str(plan.get(plan_key, "")).strip().casefold()
        if selected and planned and selected != planned:
            errors.append(
                f"citation preference {preference_key} does not match manuscript plan {plan_key}"
            )
    return errors


def validate_prd(path: Path, require_approved: bool) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"manuscript PRD not found: {path}"]
    match = re.search(r"(?im)^\s*\**status\s*:\**\s*(pending|approved|revised)\b", text)
    if not match:
        return ["manuscript PRD must contain Status: pending|approved|revised"]
    status = match.group(1).lower()
    if require_approved and status != "approved":
        return [f"manuscript PRD is not approved: {status}"]
    return []


def validate_approval_receipt(path: Path, plan_path: Path) -> list[str]:
    try:
        receipt = load_json(path, "manuscript approval receipt")
    except ValueError as exc:
        return [str(exc)]
    expected = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    errors: list[str] = []
    if receipt.get("approved_plan_sha256") != expected:
        errors.append("manuscript approval receipt does not match the current plan SHA-256")
    if receipt.get("approved_in_current_conversation") is not True:
        errors.append("manuscript approval receipt must record approved_in_current_conversation=true")
    if not nonempty(receipt.get("user_approval_text")):
        errors.append("manuscript approval receipt missing user_approval_text")
    if str(receipt.get("approval_choice", "")).strip().lower() != "approved":
        errors.append("manuscript approval receipt approval_choice must be approved")
    if str(receipt.get("approval_source", "")).strip().lower() not in {"ask_user", "direct_chat"}:
        errors.append("manuscript approval receipt approval_source must be ask_user or direct_chat")
    return errors


def bib_keys(text: str) -> set[str]:
    return {match.strip() for match in re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", text)}


def citation_keys(text: str) -> set[str]:
    pattern = re.compile(
        r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?"
        r"(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
    )
    keys: set[str] = set()
    for group in pattern.findall(text):
        keys.update(key.strip() for key in group.split(",") if key.strip())
    return keys


def strip_latex_comments(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        cut = None
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        cleaned.append(line if cut is None else line[:cut])
    return "\n".join(cleaned)


def plain_latex_text(text: str) -> str:
    text = strip_latex_comments(text)
    text = re.sub(r"\\begin\{[^}]+\}|\\end\{[^}]+\}", " ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection)\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
    text = re.sub(
        r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^\]]*\]){0,2}\{[^}]*\}",
        " ", text,
    )
    text = re.sub(r"\\(?:label|ref|eqref|pageref|includegraphics|url|href)\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", text)
    text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(?:equation|align)\*?\}.*?\\end\{(?:equation|align)\*?\}", " ", text, flags=re.S)
    text = re.sub(r"\$[^$]*\$", " ", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = text.replace("~", " ").replace("\\&", " and ")
    text = re.sub(r"[{}\\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def word_equivalents(text: str) -> int:
    plain = plain_latex_text(text)
    latin = re.findall(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)*\b|\b\d+(?:\.\d+)?\b", plain)
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", plain))
    return len(latin) + (cjk_count + 1) // 2


def command_arguments(text: str, command: str) -> list[tuple[int, int, str]]:
    pattern = re.compile(rf"\\{re.escape(command)}\*?(?:\[[^\]]*\])?\s*\{{")
    found: list[tuple[int, int, str]] = []
    for match in pattern.finditer(text):
        opening = match.end() - 1
        depth = 0
        for cursor in range(opening, len(text)):
            if text[cursor] == "{" and (cursor == 0 or text[cursor - 1] != "\\"):
                depth += 1
            elif text[cursor] == "}" and (cursor == 0 or text[cursor - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    found.append((match.start(), cursor + 1, text[opening + 1:cursor]))
                    break
    return found


def normalized_heading(heading: str) -> str:
    return re.sub(
        r"[^a-z\u3400-\u4dbf\u4e00-\u9fff]+",
        " ",
        plain_latex_text(heading).casefold(),
    ).strip()


def section_types_for_heading(heading: str) -> tuple[str, ...]:
    normalized = normalized_heading(heading)
    if normalized in COMBINED_SECTION_ALIASES:
        return COMBINED_SECTION_ALIASES[normalized]
    for section_type, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return (section_type,)
    return ()


def section_type_for_heading(heading: str) -> str | None:
    types = section_types_for_heading(heading)
    return types[0] if types else None


def remove_float_environments(text: str) -> str:
    return re.sub(
        r"\\begin\{(?:figure|table)\*?\}.*?\\end\{(?:figure|table)\*?\}",
        " ", text, flags=re.S,
    )


def extract_manuscript_structure(tex: str) -> dict:
    document_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", tex, flags=re.S)
    document = document_match.group(1) if document_match else tex
    abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", document, flags=re.S)
    abstract = abstract_match.group(1) if abstract_match else ""
    abstract_found = abstract_match is not None
    if not abstract_found:
        abstract_commands = command_arguments(document, "abstract")
        if abstract_commands:
            abstract = abstract_commands[0][2]
            abstract_found = True
    figure_blocks = re.findall(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", document, flags=re.S)
    legends = [argument for block in figure_blocks for _, _, argument in command_arguments(block, "caption")]
    body = remove_float_environments(document)
    sections: list[dict] = []
    section_commands = command_arguments(body, "section")
    abstract_section_start: int | None = None
    if not abstract_found:
        for index, (start, end, heading) in enumerate(section_commands):
            if normalized_heading(heading) not in ABSTRACT_ALIASES:
                continue
            stop = section_commands[index + 1][0] if index + 1 < len(section_commands) else len(body)
            abstract = body[end:stop]
            abstract_found = True
            abstract_section_start = start
            break
    for index, (start, end, heading) in enumerate(section_commands):
        stop = section_commands[index + 1][0] if index + 1 < len(section_commands) else len(body)
        content = body[end:stop]
        subsections: list[dict] = []
        subsection_commands = command_arguments(content, "subsection")
        for sub_index, (sub_start, sub_end, sub_heading) in enumerate(subsection_commands):
            sub_stop = subsection_commands[sub_index + 1][0] if sub_index + 1 < len(subsection_commands) else len(content)
            subsections.append({
                "heading": plain_latex_text(sub_heading),
                "word_equivalents": word_equivalents(content[sub_end:sub_stop]),
            })
        section_types = () if start == abstract_section_start else section_types_for_heading(heading)
        sections.append({
            "heading": plain_latex_text(heading),
            "section_type": section_types[0] if section_types else None,
            "section_types": list(section_types),
            "word_equivalents": word_equivalents(content),
            "subsections": subsections,
        })
    return {
        "abstract_found": abstract_found,
        "abstract_word_equivalents": word_equivalents(abstract),
        "sections": sections,
        "figure_legends": [word_equivalents(item) for item in legends],
    }


def validate_manuscript_lengths(tex: str, plan: dict, figure_count: int) -> tuple[list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    minimums, policy_errors = length_policy_minimums(plan)
    errors.extend(policy_errors)
    enforcement = length_enforcement(plan)
    strict = enforcement == "strict"

    def length_issue(message: str) -> None:
        (errors if strict else warnings).append(message)

    structure = extract_manuscript_structure(tex)
    abstract_count = structure["abstract_word_equivalents"]
    if not structure.get("abstract_found"):
        errors.append("manuscript missing recognizable abstract")
    elif abstract_count < minimums["abstract"]:
        length_issue(
            f"abstract too short: {abstract_count} word-equivalents; required {minimums['abstract']:g}"
        )

    totals: Counter[str] = Counter()
    recognized: Counter[str] = Counter()
    main_text = 0
    main_types = {"introduction", "methods", "results", "discussion", "conclusion"}
    for section in structure["sections"]:
        section_types = tuple(section.get("section_types") or ())
        for section_type in section_types:
            totals[section_type] += section["word_equivalents"]
            recognized[section_type] += 1
        if main_types.intersection(section_types):
            main_text += section["word_equivalents"]
        scoped_type = "results" if "results" in section_types else (
            "methods" if "methods" in section_types else None
        )
        if scoped_type is None:
            continue
        required = minimums[f"{scoped_type}_subsection"]
        for subsection in section["subsections"]:
            normalized = subsection["heading"].strip().casefold()
            if normalized in ADMINISTRATIVE_SUBSECTIONS:
                continue
            actual = subsection["word_equivalents"]
            if actual < required:
                length_issue(
                    f"{scoped_type} subsection too short: {subsection['heading']!r} has "
                    f"{actual} word-equivalents; required {required:g}"
                )

    for section_type in ("introduction", "methods", "results", "discussion", "conclusion"):
        actual = totals[section_type]
        required = minimums[section_type]
        if not recognized[section_type]:
            errors.append(f"manuscript missing recognizable {section_type} section")
        elif actual < required:
            length_issue(
                f"{section_type} section too short: {actual} word-equivalents; required {required:g}"
            )
    if main_text < minimums["main_text"]:
        length_issue(
            f"main text too short: {main_text} word-equivalents; required {minimums['main_text']:g}"
        )

    legends = structure["figure_legends"]
    if figure_count and len(legends) < figure_count:
        errors.append(f"manuscript contains {len(legends)} figure legend(s) for {figure_count} major figure(s)")
    for index, actual in enumerate(legends[:figure_count] if figure_count else legends, start=1):
        if actual < minimums["figure_legend"]:
            length_issue(
                f"Figure {index} legend too short: {actual} word-equivalents; required {minimums['figure_legend']:g}"
            )
    structure["length_enforcement"] = enforcement
    structure["length_warnings"] = warnings
    structure["section_totals"] = dict(totals)
    structure["main_text_word_equivalents"] = main_text
    return errors, structure


def validate_bibliography_mode(tex: str, bib_text: str, plan: dict) -> list[str]:
    errors: list[str] = []
    if re.search(
        r"\\begin\{thebibliography\}|\\bibitem\b|"
        r"\\(?:section|section\*)\s*\{\s*(?:参考文献|References)\s*\}",
        tex,
        re.IGNORECASE,
    ):
        errors.append(
            "inline manual bibliography is forbidden; use references.bib and "
            "the selected citation export mode"
        )

    export_mode = str(plan.get("citation_export_mode", "")).strip().lower()
    cited = citation_keys(tex)
    available_bib_keys = bib_keys(bib_text)
    if export_mode == "strict_linked" and not cited:
        errors.append("strict_linked manuscript contains no citation commands")
    elif export_mode == "bibliography_compatibility" and not available_bib_keys:
        errors.append("bibliography_compatibility requires a non-empty references.bib")
    elif export_mode not in {"strict_linked", "bibliography_compatibility"}:
        errors.append("unknown citation_export_mode")

    missing_keys = sorted(cited - available_bib_keys)
    if missing_keys:
        errors.append("citation keys missing from BibTeX: " + ", ".join(missing_keys))
    if re.search(r"\[\s*\?+\s*\]|citation\s+needed|TODO_CITATION", tex, re.IGNORECASE):
        errors.append("manuscript contains unresolved citation placeholders")
    return errors


def validate_source(root: Path, source: Path, bib: Path, figure_count: int, plan: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    try:
        tex = source.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"manuscript source not found: {source}"], {}
    try:
        bib_text = bib.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"bibliography not found: {bib}"], {}

    errors.extend(validate_bibliography_mode(tex, bib_text, plan))

    images = [item.strip() for item in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)]
    if figure_count and len(images) < figure_count:
        errors.append(f"manuscript embeds {len(images)} image(s) for {figure_count} planned major figure(s)")
    for raw in images:
        path = Path(raw).expanduser()
        if path.is_absolute():
            errors.append(f"absolute image path is not portable: {raw}")
            continue
        if not (source.parent / path).resolve().is_file():
            errors.append(f"embedded image missing: {raw}")
    length_errors, length_report = validate_manuscript_lengths(tex, plan, figure_count)
    errors.extend(length_errors)
    return errors, length_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--results-map", required=True)
    parser.add_argument("--figure-blueprint", required=True)
    parser.add_argument("--evidence-inventory", required=True)
    parser.add_argument("--manuscript-plan", required=True)
    parser.add_argument("--manuscript-prd", required=True)
    parser.add_argument("--citation-preference", required=True)
    parser.add_argument("--approval-receipt", required=True)
    parser.add_argument("--source")
    parser.add_argument("--bib")
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    errors: list[str] = []
    length_report: dict = {}
    try:
        results_map = load_json(resolve(root, args.results_map), "results map")
        figure_blueprint = load_json(resolve(root, args.figure_blueprint), "figure blueprint")
        evidence_inventory = load_json(resolve(root, args.evidence_inventory), "evidence inventory")
        plan_path = resolve(root, args.manuscript_plan)
        plan = load_json(plan_path, "manuscript plan")
        errors.extend(validate_plan(root, plan, results_map, figure_blueprint, evidence_inventory, args.require_approved))
        errors.extend(validate_prd(resolve(root, args.manuscript_prd), args.require_approved))
        errors.extend(
            validate_citation_preference(
                resolve(root, args.citation_preference), plan, args.require_approved
            )
        )
        if args.require_approved:
            errors.extend(validate_approval_receipt(resolve(root, args.approval_receipt), plan_path))
        if bool(args.source) != bool(args.bib):
            errors.append("--source and --bib must be supplied together")
        elif args.source and args.bib:
            figures = figure_blueprint.get("figures", [])
            figure_count = len(figures) if isinstance(figures, list) else 0
            source_errors, length_report = validate_source(
                root, resolve(root, args.source), resolve(root, args.bib), figure_count, plan
            )
            errors.extend(source_errors)
    except ValueError as exc:
        errors.append(str(exc))

    if length_report:
        totals = length_report.get("section_totals", {})
        print(
            "MANUSCRIPT_LENGTH "
            + " ".join(
                [
                    f"enforcement={length_report.get('length_enforcement', 'advisory')}",
                    f"main_text={length_report.get('main_text_word_equivalents', 0)}",
                ]
                + [f"{key}={totals.get(key, 0)}" for key in ("introduction", "methods", "results", "discussion", "conclusion")]
            )
        )
        for warning in length_report.get("length_warnings", []):
            print(f"WARNING {warning}")
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("MANUSCRIPT_PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
