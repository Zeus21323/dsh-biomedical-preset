#!/usr/bin/env python3
"""Audit a general academic LaTeX manuscript and its evidence map."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from validate_claim_evidence_map import load_json, validate
from validate_manuscript_approval import validate_approval


CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^]]*\]){0,2}\{([^}]+)\}"
)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(r"\\(?:ref|autoref|cref|Cref|eqref|pageref)\{([^}]+)\}")
IMAGE_RE = re.compile(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}")
SECTION_RE = re.compile(r"\\(?:section|section\*|chapter)\{([^}]+)\}", re.IGNORECASE)
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|FIXME|CITATION NEEDED)\b|\?\?|@@(?:CAPTION|AUTOREF|REF|EQUATION):",
    re.IGNORECASE,
)
MANUAL_PARENTHETICAL_CITATION_RE = re.compile(
    r"[（(]\s*[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+(?:et\s+al\.?|and|&|等人|和)"
    r"\s*[A-ZÀ-ÖØ-Þ]?[A-Za-zÀ-ÖØ-öø-ÿ'’.-]*)?\s*[,，]\s*(?:19|20)\d{2}[a-z]?"
    r"(?:\s*[;；]\s*[A-ZÀ-ÖØ-Þ][^）)]*?\s*[,，]\s*(?:19|20)\d{2}[a-z]?)*\s*[）)]"
)
MANUAL_NARRATIVE_CITATION_RE = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+(?:et\s+al\.?|and|&|等人|和)"
    r"\s*[A-ZÀ-ÖØ-Þ]?[A-Za-zÀ-ÖØ-öø-ÿ'’.-]*)?\s*[（(]\s*(?:19|20)\d{2}[a-z]?\s*[）)]"
)
MANUAL_BIBLIOGRAPHY_RE = re.compile(
    r"\\begin\{thebibliography\}|\\bibitem\b|"
    r"\\(?:section|chapter)\*?\s*\{\s*(?:参考文献|References|Bibliography)\s*\}"
    r"[\s\S]{0,1200}?\\begin\{(?:description|enumerate|itemize)\}",
    re.IGNORECASE,
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def strip_comments(tex: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", tex)


def find_manual_author_year_citations(tex: str) -> list[str]:
    matches = MANUAL_PARENTHETICAL_CITATION_RE.findall(tex)
    matches.extend(MANUAL_NARRATIVE_CITATION_RE.findall(tex))
    return sorted(set(re.sub(r"\s+", " ", item).strip() for item in matches))


def resolve_image(manuscript_dir: Path, raw: str) -> Path | None:
    candidate = manuscript_dir / raw
    if candidate.suffix:
        return candidate if candidate.exists() else None
    for suffix in (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps"):
        with_suffix = candidate.with_suffix(suffix)
        if with_suffix.exists():
            return with_suffix
    return None


def family_present(sections: list[str], alternatives: tuple[str, ...]) -> bool:
    combined = " | ".join(sections).lower()
    return any(re.search(pattern, combined) for pattern in alternatives)


def required_section_families(study_type: str) -> dict[str, tuple[str, ...]]:
    common = {
        "introduction": (r"introduction", r"引言", r"绪论"),
        "evidence body": (
            r"result", r"finding", r"evaluation", r"analysis", r"synthesis", r"proof",
            r"结果", r"发现", r"评估", r"分析", r"综合", r"证明",
        ),
        "limitations": (r"limitation", r"threat", r"局限", r"有效性", r"反思"),
        "conclusion": (r"conclusion", r"总结", r"结论"),
    }
    if study_type == "review":
        common["review methods"] = (r"method", r"search", r"selection", r"方法", r"检索", r"筛选")
    elif study_type == "theoretical":
        common["theory or model"] = (r"theory", r"model", r"definition", r"理论", r"模型", r"定义")
    else:
        common["methods or design"] = (
            r"method", r"material", r"design", r"system", r"方法", r"材料", r"研究设计", r"系统",
        )
    return common


def audit(
    tex_path: Path,
    bib_path: Path,
    evidence_path: Path,
    plan_path: Path,
    approval_path: Path,
    project_root: Path,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    tex_raw = read_text(tex_path)
    bib_raw = read_text(bib_path)
    tex = strip_comments(tex_raw)
    manual_citations = find_manual_author_year_citations(tex)

    evidence = load_json(evidence_path)
    evidence_errors, evidence_warnings = validate(evidence, project_root, require_sources=True)
    errors.extend(f"evidence: {item}" for item in evidence_errors)
    warnings.extend(f"evidence: {item}" for item in evidence_warnings)

    approval_errors, approval_warnings = validate_approval(plan_path, approval_path)
    errors.extend(f"approval: {item}" for item in approval_errors)
    warnings.extend(f"approval: {item}" for item in approval_warnings)

    bib_keys = set(BIB_ENTRY_RE.findall(bib_raw))
    cited_keys: set[str] = set()
    for group in CITE_RE.findall(tex):
        cited_keys.update(key.strip() for key in group.split(",") if key.strip())
    for key in sorted(cited_keys - bib_keys):
        errors.append(f"citation key missing from bibliography: {key}")
    for key in sorted(bib_keys - cited_keys):
        warnings.append(f"bibliography entry is not cited: {key}")
    if manual_citations:
        examples = " | ".join(manual_citations[:3])
        errors.append(
            "manual author-year citation text is forbidden; use citation commands with BibTeX keys: "
            f"count={len(manual_citations)}, examples={examples}"
        )
    if MANUAL_BIBLIOGRAPHY_RE.search(tex):
        errors.append(
            "manual bibliography block is forbidden; keep entries in references.bib and let citeproc render the bibliography"
        )

    labels = LABEL_RE.findall(tex)
    label_set = set(labels)
    for label in sorted({x for x in labels if labels.count(x) > 1}):
        errors.append(f"duplicate LaTeX label: {label}")
    referenced = set(REF_RE.findall(tex))
    for label in sorted(referenced - label_set):
        errors.append(f"reference target is undefined: {label}")
    for label in sorted(label_set - referenced):
        if label.startswith(("tab:", "fig:", "eq:", "alg:", "sec:")):
            warnings.append(f"labeled object is not referenced in prose: {label}")

    for raw in sorted(set(IMAGE_RE.findall(tex))):
        if resolve_image(tex_path.parent, raw) is None:
            errors.append(f"image path does not resolve relative to manuscript: {raw}")

    for marker in sorted(set(x.group(0) for x in PLACEHOLDER_RE.finditer(tex))):
        errors.append(f"unresolved authoring marker: {marker}")

    sections = SECTION_RE.findall(tex)
    study_type = evidence.get("study_type", "")
    for family, alternatives in required_section_families(study_type).items():
        if not family_present(sections, alternatives):
            errors.append(f"required section family not found: {family}")

    if not re.search(r"\\begin\{abstract\}|\\abstract\{", tex, re.IGNORECASE):
        errors.append("abstract environment or command not found")
    if not cited_keys:
        errors.append("manuscript contains no recognized citation commands")
    if not bib_keys:
        errors.append("bibliography contains no BibTeX entries")

    return {
        "status": "pass" if not errors else "fail",
        "study_type": study_type,
        "inputs": {
            "tex": str(tex_path), "bib": str(bib_path), "evidence_map": str(evidence_path),
            "manuscript_plan": str(plan_path), "approval_receipt": str(approval_path),
        },
        "counts": {
            "sections": len(sections), "citation_keys": len(cited_keys),
            "bibliography_entries": len(bib_keys), "labels": len(labels),
            "references": len(referenced), "figures": len(IMAGE_RE.findall(tex)),
            "manual_author_year_citations": len(manual_citations),
        },
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, required=True)
    parser.add_argument("--bib", type=Path, required=True)
    parser.add_argument("--evidence-map", type=Path, required=True)
    parser.add_argument("--manuscript-plan", type=Path, required=True)
    parser.add_argument("--approval-receipt", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    try:
        report = audit(
            args.tex.resolve(), args.bib.resolve(), args.evidence_map.resolve(),
            args.manuscript_plan.resolve(), args.approval_receipt.resolve(),
            args.project_root.resolve(),
        )
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.report}: {exc}", file=sys.stderr)
            return 2
    else:
        print(rendered, end="")

    for warning in report["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)
    for error in report["errors"]:
        print(f"error: {error}", file=sys.stderr)
    if report["status"] == "pass":
        print("MANUSCRIPT_AUDIT_OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
