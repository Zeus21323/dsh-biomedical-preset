#!/usr/bin/env python3
"""Extract journal DOCX requirements and export TeX/Markdown manuscripts to DOCX."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from docx_reference_fields import add_numeric_reference_fields, validate_numeric_reference_fields
from pandoc_runtime import resolve_pandoc


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = SKILL_DIR / "assets"
DOCX_DIR = ASSETS_DIR / "docx"
CSL_DIR = ASSETS_DIR / "csl"
JOURNAL_PROFILE_DIR = ASSETS_DIR / "journal_profiles"

CSL_MAP = {
    "ama": "american-medical-association.csl",
    "vancouver": "american-medical-association.csl",
    "apa": "apa.csl",
    "nature": "nature.csl",
    "science": "science.csl",
    "cell": "cell.csl",
    "ieee": "ieee.csl",
    "acs": "american-chemical-society.csl",
    "rsc": "royal-society-of-chemistry.csl",
    "elsevier": "elsevier-with-titles.csl",
    "gb/t 7714": "china-national-standard-gb-t-7714-2015-numeric.csl",
    "gb-t-7714": "china-national-standard-gb-t-7714-2015-numeric.csl",
}

LATEX_IMAGE_PATTERN = re.compile(
    r"\\includegraphics\s*(?:\[[^\]]*\]\s*)?\{([^{}]+)\}",
    flags=re.S,
)
LATEX_GRAPHICSPATH_PATTERN = re.compile(
    r"\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}",
    flags=re.S,
)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".pdf", ".svg", ".tif", ".tiff", ".eps")
LATEX_CITATION_PATTERN = re.compile(
    r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}"
)
MANUAL_BIBLIOGRAPHY_PATTERN = re.compile(
    r"\\begin\{thebibliography\}|\\bibitem\b|"
    r"\\(?:section|section\*)\s*\{\s*(?:参考文献|References)\s*\}",
    re.IGNORECASE,
)
BIB_KEY_PATTERN = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
ElementTree.register_namespace("w", WORD_NS)
ElementTree.register_namespace("m", MATH_NS)


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge dictionaries without mutating either input."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def normalize_profile_key(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", Path(str(value)).name.casefold()).strip()


def load_journal_profiles() -> list[dict]:
    index_path = JOURNAL_PROFILE_DIR / "index.json"
    if not index_path.is_file():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    profiles: list[dict] = []
    for filename in index.get("profiles", []):
        path = JOURNAL_PROFILE_DIR / filename
        if not path.is_file():
            raise SystemExit(f"journal_profile_missing: {path}")
        profile = json.loads(path.read_text(encoding="utf-8"))
        profile["_path"] = str(path)
        profiles.append(profile)
    return profiles


def find_journal_profile(
    identifier: str | None = None,
    *,
    journal: str | None = None,
    csl: str | None = None,
) -> dict | None:
    profiles = load_journal_profiles()
    candidates = [identifier, csl, journal]
    for position, candidate in enumerate(candidates):
        key = normalize_profile_key(candidate)
        if not key:
            continue
        for profile in profiles:
            names = [profile.get("profile_id", ""), *profile.get("aliases", []), *profile.get("csl_files", [])]
            if key in {normalize_profile_key(name) for name in names}:
                return profile
        if position == 0:
            available = ", ".join(profile.get("profile_id", "") for profile in profiles)
            raise SystemExit(f"journal_profile_unknown: {candidate}. available={available}")
    return None


def list_journal_profiles(args: argparse.Namespace) -> None:
    for profile in load_journal_profiles():
        csl_files = ",".join(profile.get("csl_files", []))
        fallback = any(item.get("status") in {"fallback", "not-applicable"} for item in profile.get("evidence", {}).values())
        print(
            f"{profile['profile_id']}\t{profile['display_name']}\t"
            f"scope={profile['scope']}\tcsl={csl_files}\tcontains_fallbacks={'yes' if fallback else 'no'}"
        )


def read_guidelines(url: str | None, file_path: str | None) -> tuple[str, str]:
    if file_path:
        path = Path(file_path)
        return path.read_text(encoding="utf-8", errors="replace"), str(path)
    if not url:
        raise SystemExit("Either --guidelines-url or --guidelines-file is required")
    headers = {
        "User-Agent": "Mozilla/5.0 tex-to-docx skill guideline extractor",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else urlparse(url).netloc
    text = soup.get_text("\n", strip=True)
    return f"{title}\n\n{text}", url


def find_number_before(text: str, unit_pattern: str, default: int | None = None) -> int | None:
    match = re.search(rf"(\d{{2,5}})\s*(?:-|to)?\s*{unit_pattern}", text, flags=re.I)
    return int(match.group(1)) if match else default


def infer_abstract_word_limit(text: str, default: int = 300) -> int:
    patterns = [
        r"abstract.{0,80}?(\d{2,5})\s*words?",
        r"(\d{2,5})\s*words?.{0,80}?abstract",
        r"summary.{0,80}?(\d{2,5})\s*words?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return int(match.group(1))
    return default


def infer_citation_style(text: str) -> tuple[str, str]:
    lower = text.lower()
    for key, csl in CSL_MAP.items():
        if key in lower:
            return key, csl
    if "wiley" in lower or "medical" in lower or "medicine" in lower:
        return "ama", CSL_MAP["ama"]
    return "science", CSL_MAP["science"]


def infer_line_spacing(text: str) -> str:
    lower = text.lower()
    if "double-spac" in lower or "double spac" in lower:
        return "double"
    if "1.5" in lower or "one-and-a-half" in lower:
        return "1.5"
    return "1.5"


def infer_font(text: str) -> tuple[str, int]:
    lower = text.lower()
    font = "Times New Roman" if "times new roman" in lower else "Times New Roman"
    size_match = re.search(r"(\d{1,2})\s*(?:pt|point|points)", lower)
    size = int(size_match.group(1)) if size_match else 12
    return font, size


def extract_config(args: argparse.Namespace) -> Path:
    profile = find_journal_profile(
        getattr(args, "journal_profile", None),
        journal=getattr(args, "journal", None),
        csl=getattr(args, "csl", None),
    )
    if args.guidelines_url or args.guidelines_file:
        text, source = read_guidelines(args.guidelines_url, args.guidelines_file)
    elif profile:
        text = ""
        source = profile.get("sources", [{}])[0].get("url", profile.get("_path", "bundled journal profile"))
    else:
        raise SystemExit("Either --guidelines-url, --guidelines-file, or a recognized --journal-profile/--journal/--csl is required")
    font, font_size = infer_font(text)
    citation_style, csl_file = infer_citation_style(text)
    lower = text.lower()
    language = getattr(args, "language", None) or (profile.get("language") if profile else None) or "en"
    explicit_csl = getattr(args, "csl", None)

    config = {
        "journal": args.journal or (profile.get("display_name") if profile else None) or infer_journal_name(text, source),
        "source": source,
        "language": language,
        "article_type": args.article_type or "Original Research",
        "body": {
            "font": font,
            "font_size_pt": font_size,
            "line_spacing": getattr(args, "line_spacing", None) or infer_line_spacing(text),
            "margin_inches": 1.0,
        },
        "title": {"font": font, "font_size_pt": 16, "bold": True, "alignment": "center"},
        "headings": {
            "heading_1": {"font": font, "font_size_pt": 14, "bold": True},
            "heading_2": {"font": font, "font_size_pt": 13, "bold": True},
        },
        "abstract": {
            "word_limit": infer_abstract_word_limit(text, 300),
            "structured": any(term in lower for term in ["structured abstract", "background", "methods", "results", "conclusion"]),
            "recommended_headings": ["Background", "Methods", "Results", "Conclusion"],
        },
        "references": {
            "style": citation_style,
            "csl_file": csl_file,
        },
        "figures": {
            "min_dpi": 300 if "300" in lower and "dpi" in lower else None,
            "preferred_formats": [fmt for fmt in ["TIFF", "EPS", "PDF", "PNG", "JPEG"] if fmt.lower() in lower],
        },
        "required_statements": infer_required_statements(lower),
        "notes": [
            "This JSON is a heuristic extraction. Verify against the journal Author Guidelines before submission.",
            "reference_docx controls Word styles only; content rules still need manuscript-level checks.",
        ],
    }
    if profile:
        config = deep_merge(config, profile.get("template", {}))
        config["journal_profile"] = profile["profile_id"]
        config["journal_profile_file"] = profile["_path"]
        config["journal_profile_scope"] = profile.get("scope")
        config["journal_profile_verified_on"] = profile.get("verified_on")
        config["journal_profile_sources"] = profile.get("sources", [])
        config["journal_profile_evidence"] = profile.get("evidence", {})
        if profile.get("csl_files"):
            config["references"]["csl_file"] = profile.get("default_csl_file") or profile["csl_files"][0]
            config["references"]["style"] = profile["profile_id"]
        if any(item.get("status") in {"fallback", "not-applicable"} for item in profile.get("evidence", {}).values()):
            config["notes"].append(
                "The selected profile contains fallback or not-applicable typography fields; consult the target journal/institution before submission."
            )
    if explicit_csl:
        config["references"]["csl_file"] = explicit_csl
    if getattr(args, "line_spacing", None):
        config["body"]["line_spacing"] = args.line_spacing
    output = Path(args.output or "journal_config.json")
    output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def infer_journal_name(text: str, source: str) -> str:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if first:
        first = re.sub(r"\s+", " ", first)
        first = re.sub(r"\s*\|\s*.*$", "", first)
        return first[:120]
    return urlparse(source).netloc or "Target journal"


def infer_required_statements(lower: str) -> list[str]:
    candidates = [
        ("data availability", "Data Availability Statement"),
        ("code availability", "Code Availability Statement"),
        ("ethics", "Ethics Statement"),
        ("informed consent", "Patient Consent Statement"),
        ("conflict of interest", "Conflict of Interest Statement"),
        ("competing interest", "Conflict of Interest Statement"),
        ("funding", "Funding Statement"),
        ("author contribution", "Author Contributions"),
        ("orcid", "ORCID IDs"),
        ("reporting guideline", "Reporting Guideline Checklist"),
    ]
    result: list[str] = []
    for needle, label in candidates:
        if needle in lower and label not in result:
            result.append(label)
    defaults = ["Data Availability Statement", "Conflict of Interest Statement", "Funding Statement"]
    for item in defaults:
        if item not in result:
            result.append(item)
    return result


def line_spacing_value(value: str):
    normalized = str(value).lower()
    if normalized in {"double", "2", "2.0"}:
        return 2.0
    if normalized in {"1.5", "one-half", "one_and_half"}:
        return 1.5
    return 1.0


def set_style(
    doc: Document,
    style_name: str,
    font: str,
    size_pt: float,
    *,
    east_asia_font: str | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    spacing: str | float | None = None,
    alignment: str | None = None,
    hanging_indent_inches: float | None = None,
    required: bool = False,
) -> None:
    if style_name not in doc.styles:
        if required:
            raise SystemExit(f"required_word_style_missing: {style_name}")
        return
    style = doc.styles[style_name]
    style.font.name = font
    style.font.size = Pt(float(size_pt))
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)
    rfonts.set(qn("w:cs"), font)
    rfonts.set(qn("w:eastAsia"), east_asia_font or font)
    if bold is not None:
        style.font.bold = bold
    if italic is not None:
        style.font.italic = italic
    paragraph_format = getattr(style, "paragraph_format", None)
    if paragraph_format is not None:
        if spacing is not None:
            paragraph_format.line_spacing = line_spacing_value(spacing)
            paragraph_format.space_after = Pt(6)
        if alignment:
            alignments = {
                "left": WD_ALIGN_PARAGRAPH.LEFT,
                "center": WD_ALIGN_PARAGRAPH.CENTER,
                "right": WD_ALIGN_PARAGRAPH.RIGHT,
                "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
            }
            if alignment.casefold() not in alignments:
                raise SystemExit(f"word_style_alignment_invalid: {style_name}={alignment}")
            paragraph_format.alignment = alignments[alignment.casefold()]
        if hanging_indent_inches is not None:
            paragraph_format.first_line_indent = Inches(-float(hanging_indent_inches))
            paragraph_format.left_indent = Inches(float(hanging_indent_inches))


def apply_style_block(
    doc: Document,
    style_name: str,
    block: dict,
    body: dict,
    *,
    required: bool = True,
) -> None:
    set_style(
        doc,
        style_name,
        block.get("font", body.get("font", "Times New Roman")),
        float(block.get("font_size_pt", body.get("font_size_pt", 12))),
        east_asia_font=block.get("font_east_asia", body.get("font_east_asia")),
        bold=block.get("bold"),
        italic=block.get("italic"),
        spacing=block.get("line_spacing", body.get("line_spacing")),
        alignment=block.get("alignment"),
        hanging_indent_inches=block.get("hanging_indent_inches"),
        required=required,
    )


def validate_generated_template(docx_path: Path, effective: dict) -> None:
    """Fail if the generated reference DOCX does not contain the requested core styles."""
    doc = Document(str(docx_path))
    body = effective.get("body", {})
    style_blocks = {
        "Normal": body,
        "Body Text": body,
        "First Paragraph": body,
        "Title": effective.get("title", {}),
        "Heading 1": effective.get("headings", {}).get("heading_1", {}),
        "Heading 2": effective.get("headings", {}).get("heading_2", {}),
        "Heading 3": effective.get("headings", {}).get("heading_3", {}),
        "Caption": effective.get("caption", {}),
        "Bibliography": effective.get("bibliography", {}),
    }
    errors: list[str] = []
    for style_name, block in style_blocks.items():
        if style_name not in doc.styles:
            errors.append(f"{style_name}:missing")
            continue
        style = doc.styles[style_name]
        expected_font = block.get("font", body.get("font", "Times New Roman"))
        expected_east_asia = block.get("font_east_asia", body.get("font_east_asia")) or expected_font
        expected_size = float(block.get("font_size_pt", body.get("font_size_pt", 12)))
        actual_size = style.font.size.pt if style.font.size else None
        rpr = style.element.rPr
        rfonts = rpr.rFonts if rpr is not None else None
        actual_east_asia = rfonts.get(qn("w:eastAsia")) if rfonts is not None else None
        if style.font.name != expected_font:
            errors.append(f"{style_name}:font={style.font.name!r},expected={expected_font!r}")
        if actual_east_asia != expected_east_asia:
            errors.append(f"{style_name}:eastAsia={actual_east_asia!r},expected={expected_east_asia!r}")
        if actual_size is None or abs(actual_size - expected_size) > 0.01:
            errors.append(f"{style_name}:size={actual_size!r},expected={expected_size:g}")
        expected_spacing = line_spacing_value(block.get("line_spacing", body.get("line_spacing", "1.0")))
        actual_spacing = style.paragraph_format.line_spacing
        if not isinstance(actual_spacing, (int, float)) or abs(float(actual_spacing) - expected_spacing) > 0.01:
            errors.append(f"{style_name}:line_spacing={actual_spacing!r},expected={expected_spacing:g}")
    if errors:
        raise SystemExit("journal_template_style_invalid:\n  " + "\n  ".join(errors))


def make_template(args: argparse.Namespace) -> Path:
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    profile = find_journal_profile(
        getattr(args, "journal_profile", None) or config.get("journal_profile"),
        journal=config.get("journal"),
        csl=config.get("references", {}).get("csl_file"),
    )
    effective = deep_merge(profile.get("template", {}) if profile else {}, config)
    language = args.language or effective.get("language") or (profile.get("language") if profile else None) or "en"
    base = Path(args.base_template) if args.base_template else DOCX_DIR / f"template-{language}.docx"
    if not base.exists():
        base = DOCX_DIR / "template-en.docx"
    if not base.exists():
        raise SystemExit(f"Base template not found: {base}")

    output = Path(args.output or "journal_template.docx")
    doc = Document(str(base))
    body = effective.get("body", {})
    font = body.get("font", "Times New Roman")
    size = float(body.get("font_size_pt", 12))
    spacing = body.get("line_spacing", "single")

    body_block = {
        "font": font,
        "font_east_asia": body.get("font_east_asia"),
        "font_size_pt": size,
        "line_spacing": spacing,
    }
    for style_name in ("Normal", "Body Text", "First Paragraph"):
        apply_style_block(doc, style_name, body_block, body)
    apply_style_block(doc, "Title", effective.get("title", {"font_size_pt": 16, "bold": True}), body)
    headings = effective.get("headings", {})
    apply_style_block(doc, "Heading 1", headings.get("heading_1", {"font_size_pt": 14, "bold": True}), body)
    apply_style_block(doc, "Heading 2", headings.get("heading_2", {"font_size_pt": 13, "bold": True}), body)
    apply_style_block(doc, "Heading 3", headings.get("heading_3", {"font_size_pt": 12, "bold": True, "italic": True}), body)
    apply_style_block(doc, "Caption", effective.get("caption", {"font_size_pt": 10, "italic": False}), body)
    apply_style_block(doc, "Bibliography", effective.get("bibliography", {}), body)

    margin = float(body.get("margin_inches", 1.0))
    for section in doc.sections:
        section.top_margin = Inches(margin)
        section.bottom_margin = Inches(margin)
        section.left_margin = Inches(margin)
        section.right_margin = Inches(margin)

    doc.save(str(output))
    validate_generated_template(output, effective)
    if profile:
        print(f"JOURNAL_PROFILE {profile['profile_id']} source={profile['_path']}")
    return output


def resolve_csl(config: dict, override: str | None) -> Path | None:
    if override:
        csl = Path(override)
        return csl if csl.exists() else CSL_DIR / override
    csl_name = config.get("references", {}).get("csl_file")
    if not csl_name:
        return None
    csl = CSL_DIR / csl_name
    return csl if csl.exists() else None


def csl_is_numeric(csl: Path | None) -> bool:
    if csl is None or not csl.is_file():
        return False
    text = csl.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r'<category\s+citation-format="numeric"', text))


def csl_uses_superscript(csl: Path | None) -> bool:
    if csl is None or not csl.is_file():
        return False
    text = csl.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r'<layout\b[^>]*\bvertical-align="sup"', text))


def validate_bibliography_source(source: Path, bib: Path, require_numbered: bool) -> set[str]:
    if not bib.is_file():
        raise SystemExit(f"bibliography_not_found: {bib}")
    if source.suffix.lower() not in {".tex", ".latex"}:
        return set()
    text = _strip_latex_comments(source.read_text(encoding="utf-8", errors="replace"))
    if MANUAL_BIBLIOGRAPHY_PATTERN.search(text):
        raise SystemExit(
            "manual_bibliography_forbidden: remove thebibliography, bibitem, and hand-written "
            "References sections; pass the .bib file with --bib"
        )
    cited: set[str] = set()
    for group in LATEX_CITATION_PATTERN.findall(text):
        cited.update(key.strip() for key in group.split(",") if key.strip())
    if require_numbered and not cited:
        raise SystemExit("citation_commands_missing: numbered-reference export requires at least one \\cite{key}")
    available = set(BIB_KEY_PATTERN.findall(bib.read_text(encoding="utf-8", errors="replace")))
    missing = sorted(cited - available)
    if missing:
        raise SystemExit("citation_keys_missing_from_bib: " + ", ".join(missing))
    return cited


def _strip_latex_comments(text: str) -> str:
    """Remove unescaped LaTeX comments before scanning image commands."""
    cleaned: list[str] = []
    for line in text.splitlines():
        comment_at = None
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                comment_at = index
                break
        cleaned.append(line if comment_at is None else line[:comment_at])
    return "\n".join(cleaned)


def _latex_resource_roots(source: Path, text: str, invocation_dir: Path) -> list[Path]:
    roots = [source.parent, invocation_dir]
    for match in LATEX_GRAPHICSPATH_PATTERN.finditer(text):
        for raw in re.findall(r"\{([^{}]+)\}", match.group(1)):
            raw = raw.strip()
            if not raw or "\\" in raw or "#" in raw:
                continue
            path = Path(raw).expanduser()
            roots.append(path if path.is_absolute() else source.parent / path)

    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _resolve_latex_image(reference: str, roots: list[Path]) -> Path | None:
    """Resolve a literal includegraphics reference against the resource roots."""
    path = Path(reference).expanduser()
    candidates = [path] if path.is_absolute() else [root / path for root in roots]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
        if not candidate.suffix:
            for suffix in IMAGE_EXTENSIONS:
                with_suffix = candidate.with_suffix(suffix)
                if with_suffix.is_file():
                    return with_suffix.resolve()
    return None


def prepare_latex_images(source: Path, invocation_dir: Path) -> tuple[list[Path], list[Path]]:
    """Validate literal LaTeX image paths and return images plus Pandoc resource roots."""
    if source.suffix.lower() not in {".tex", ".latex"}:
        return [], [source.parent, invocation_dir]

    text = _strip_latex_comments(source.read_text(encoding="utf-8", errors="replace"))
    roots = _latex_resource_roots(source, text, invocation_dir)
    references = [match.group(1).strip() for match in LATEX_IMAGE_PATTERN.finditer(text)]
    resolved_images: list[Path] = []
    missing: list[str] = []
    for reference in references:
        if any(token in reference for token in ("\\", "#", "{", "}")):
            continue
        resolved = _resolve_latex_image(reference, roots)
        if resolved is None:
            missing.append(reference)
        else:
            resolved_images.append(resolved)

    if missing:
        searched = os.pathsep.join(str(root) for root in roots)
        details = "\n".join(f"  - {reference}" for reference in missing)
        raise SystemExit(
            f"image_not_found: unresolved \\includegraphics path(s):\n{details}\n"
            f"resource_paths: {searched}"
        )
    return list(dict.fromkeys(resolved_images)), roots


def validate_docx_images(output: Path, expected_images: list[Path]) -> None:
    """Require LaTeX images to appear in the DOCX main-document relationships."""
    if not expected_images:
        return
    try:
        with zipfile.ZipFile(output) as archive:
            media_files = {
                name
                for name in archive.namelist()
                if name.startswith("word/media/") and not name.endswith("/")
            }
            rels = ElementTree.fromstring(archive.read("word/_rels/document.xml.rels"))
    except (FileNotFoundError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise SystemExit(f"docx_validation_failed: {exc}") from exc

    document_images = {
        relation.attrib.get("Target", "")
        for relation in rels
        if relation.attrib.get("Type", "").endswith("/image")
    }
    if not media_files or len(document_images) < len(expected_images):
        raise SystemExit(
            "docx_media_missing: source declares "
            f"{len(expected_images)} distinct literal image(s), but the DOCX main document "
            f"contains {len(document_images)} image relationship(s) and {len(media_files)} media file(s)"
        )


def rewrite_docx_member(docx_path: Path, member: str, data: bytes) -> None:
    temp = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(docx_path) as source, zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            target.writestr(item, data if item.filename == member else source.read(item.filename))
    shutil.move(str(temp), str(docx_path))


def normalize_docx_line_spacing(docx_path: Path, multiplier: float = 1.5) -> int:
    with zipfile.ZipFile(docx_path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    line_value = str(round(multiplier * 240))
    count = 0
    for paragraph in root.iter(f"{{{WORD_NS}}}p"):
        ppr = paragraph.find(f"{{{WORD_NS}}}pPr")
        if ppr is None:
            ppr = ElementTree.Element(f"{{{WORD_NS}}}pPr")
            paragraph.insert(0, ppr)
        spacing = ppr.find(f"{{{WORD_NS}}}spacing")
        if spacing is None:
            spacing = ElementTree.SubElement(ppr, f"{{{WORD_NS}}}spacing")
        spacing.set(f"{{{WORD_NS}}}line", line_value)
        spacing.set(f"{{{WORD_NS}}}lineRule", "auto")
        count += 1
    rewrite_docx_member(docx_path, "word/document.xml", ElementTree.tostring(root, encoding="utf-8", xml_declaration=True))
    return count


def validate_docx_line_spacing(docx_path: Path, multiplier: float = 1.5) -> int:
    with zipfile.ZipFile(docx_path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    expected = str(round(multiplier * 240))
    paragraphs = list(root.iter(f"{{{WORD_NS}}}p"))
    invalid = 0
    for paragraph in paragraphs:
        spacing = paragraph.find(f"{{{WORD_NS}}}pPr/{{{WORD_NS}}}spacing")
        if spacing is None or spacing.get(f"{{{WORD_NS}}}line") != expected or spacing.get(f"{{{WORD_NS}}}lineRule") != "auto":
            invalid += 1
    if invalid:
        raise SystemExit(f"docx_line_spacing_invalid: expected={expected}, invalid_paragraphs={invalid}")
    return len(paragraphs)


def latex_math_marker_count(source: Path) -> int:
    """Return a conservative count of LaTeX math starts for delivery validation."""
    if source.suffix.casefold() not in {".tex", ".latex", ".md", ".markdown"}:
        return 0
    text = source.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?<!\\)%.*", "", text)
    environments = re.findall(
        r"\\begin\s*\{(?:equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|"
        r"flalign\*?|displaymath|math)\}",
        text,
    )
    delimited = re.findall(r"\\\(|\\\[", text)
    unescaped_dollars = re.findall(r"(?<!\\)\$", text)
    return len(environments) + len(delimited) + len(unescaped_dollars) // 2


def audit_docx_delivery(docx_path: Path, source: Path) -> dict:
    """Validate final DOCX structure and native OMML equations before delivery."""
    docx_path = docx_path.expanduser().resolve()
    source = source.expanduser().resolve()
    if not docx_path.is_file():
        raise SystemExit(f"docx_not_found: {docx_path}")
    if not source.is_file():
        raise SystemExit(f"source_not_found: {source}")
    try:
        with zipfile.ZipFile(docx_path) as archive:
            members = set(archive.namelist())
            required = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
            missing = sorted(required - members)
            if missing:
                raise SystemExit(f"docx_structure_invalid: missing={','.join(missing)}")
            document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
    except (zipfile.BadZipFile, ElementTree.ParseError, OSError) as exc:
        raise SystemExit(f"docx_structure_invalid: {exc}") from exc

    math_markers = latex_math_marker_count(source)
    equations = len(list(root.iter(f"{{{MATH_NS}}}oMath")))
    equation_paragraphs = len(list(root.iter(f"{{{MATH_NS}}}oMathPara")))
    text_nodes = [node.text for node in root.iter(f"{{{WORD_NS}}}t") if (node.text or "").strip()]
    paragraphs = len(list(root.iter(f"{{{WORD_NS}}}p")))
    tables = len(list(root.iter(f"{{{WORD_NS}}}tbl")))
    if not text_nodes or not paragraphs:
        raise SystemExit("docx_content_empty: no non-empty Word text paragraphs")
    if math_markers and equations == 0:
        raise SystemExit(
            f"docx_omml_missing: source_math_markers={math_markers}, omml_equations=0"
        )
    if equations and (b"xmlns:m=" not in document_xml or b"<m:oMath" not in document_xml):
        raise SystemExit(
            "docx_omml_prefix_invalid: native equations exist but the canonical m: prefix was not preserved"
        )

    expected_images, _ = prepare_latex_images(source, Path.cwd().resolve())
    validate_docx_images(docx_path, expected_images)
    return {
        "status": "passed",
        "docx": str(docx_path),
        "source": str(source),
        "bytes": docx_path.stat().st_size,
        "paragraphs": paragraphs,
        "tables": tables,
        "text_nodes": len(text_nodes),
        "source_math_markers": math_markers,
        "omml_equations": equations,
        "omml_equation_paragraphs": equation_paragraphs,
        "omml_prefix": "m" if equations else "not-applicable",
        "expected_images": len(expected_images),
    }


def validate_docx_command(args: argparse.Namespace) -> Path:
    report = audit_docx_delivery(Path(args.docx), Path(args.source))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")
        print(f"DOCX_DELIVERY_AUDIT {report_path}")
    print(payload, end="")
    return Path(args.docx).expanduser().resolve()


def export_docx(args: argparse.Namespace) -> Path:
    try:
        pandoc = resolve_pandoc()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    invocation_dir = Path.cwd().resolve()
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"source_not_found: {source}")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    language = str(config.get("language") or "en").lower()
    template = Path(args.reference_docx).expanduser().resolve()
    if not template.is_file():
        raise SystemExit(f"reference_docx_not_found: {template}")

    from_format = args.from_format or ("latex" if source.suffix.lower() in {".tex", ".latex"} else "markdown")
    expected_images, resource_roots = prepare_latex_images(source, invocation_dir)
    if getattr(args, "require_media", False) and not expected_images:
        raise SystemExit(
            "image_commands_missing: --require-media requires at least one resolvable literal "
            "\\includegraphics{...} command in the LaTeX source"
        )
    cmd = [
        str(pandoc),
        str(source),
        "--from",
        from_format,
        "--to",
        "docx",
        "--reference-doc",
        str(template),
        "--resource-path",
        os.pathsep.join(str(root) for root in resource_roots),
        "-o",
        str(output),
    ]
    if args.toc:
        cmd.append("--toc")
    cmd.extend(["--metadata", f"reference-section-title:{'参考文献' if language == 'zh' else 'References'}"])
    compatibility_metadata: tempfile.TemporaryDirectory[str] | None = None
    if args.bib:
        bib_path = Path(args.bib).expanduser().resolve()
        csl = resolve_csl(config, args.csl)
        numeric_references = csl_is_numeric(csl)
        require_numbered = getattr(args, "require_numbered_references", False)
        cited_keys = validate_bibliography_source(source, bib_path, require_numbered)
        cmd.extend(["--bibliography", str(bib_path), "--citeproc"])
        if csl:
            cmd.extend(["--csl", str(csl.resolve())])
        if require_numbered and not numeric_references:
            raise SystemExit("numeric_csl_required: --require-numbered-references needs a numeric CSL style")
        if not cited_keys:
            compatibility_metadata = tempfile.TemporaryDirectory(prefix="tex-to-docx-nocite-")
            metadata_path = Path(compatibility_metadata.name) / "nocite.yaml"
            metadata_path.write_text("nocite: |\n  @*\n", encoding="utf-8")
            cmd.extend(["--metadata-file", str(metadata_path)])
            print(
                "CITATION_MODE fallback_nocite_all reason=no_latex_citation_commands "
                "word_ref_fields=skipped"
            )
        citation_superscript = numeric_references and csl_uses_superscript(csl)
    else:
        cited_keys = set()
        numeric_references = False
        citation_superscript = False

    try:
        completed = subprocess.run(
            cmd,
            cwd=source.parent,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        if compatibility_metadata is not None:
            compatibility_metadata.cleanup()
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or f"pandoc_exit_{completed.returncode}")
    if "could not fetch resource" in completed.stderr.casefold():
        raise SystemExit(f"pandoc_resource_error: {completed.stderr.strip()}")
    if re.search(r"(?:warning|unresolved).*(?:citation|citeproc|bibliograph|reference)", completed.stderr, re.I):
        raise SystemExit(f"pandoc_citation_warning: {completed.stderr.strip()}")
    if numeric_references and cited_keys:
        try:
            references, fields = add_numeric_reference_fields(output, superscript=citation_superscript)
            validate_numeric_reference_fields(output, require_superscript=citation_superscript)
        except (ValueError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            raise SystemExit(f"docx_reference_crosslink_failed: {exc}") from exc
        print(f"REFERENCE_FIELDS references={references} fields={fields}")
    elif numeric_references:
        print("REFERENCE_FIELDS skipped=no_structured_citations")
    explicit_spacing = getattr(args, "line_spacing", None)
    if explicit_spacing or not config.get("journal_profile"):
        requested_spacing = explicit_spacing or config.get("body", {}).get("line_spacing") or "1.5"
        multiplier = float(line_spacing_value(requested_spacing))
        paragraphs = normalize_docx_line_spacing(output, multiplier)
        validate_docx_line_spacing(output, multiplier)
        print(f"LINE_SPACING mode=global-override multiplier={multiplier:g} paragraphs={paragraphs}")
    else:
        print(f"LINE_SPACING mode=journal-profile profile={config['journal_profile']}")
    validate_docx_images(output, expected_images)
    report = audit_docx_delivery(output, source)
    print(
        "DOCX_AUDIT "
        f"status={report['status']} omml_equations={report['omml_equations']} "
        f"paragraphs={report['paragraphs']} tables={report['tables']}"
    )
    return output


def run_all(args: argparse.Namespace) -> None:
    work = Path(args.work_dir or ".").resolve()
    work.mkdir(parents=True, exist_ok=True)
    config_path = work / (args.config_name or "journal_config.json")
    template_path = work / (args.template_name or "journal_template.docx")
    output_path = Path(args.output).resolve()

    extract_args = argparse.Namespace(
        guidelines_url=args.guidelines_url,
        guidelines_file=args.guidelines_file,
        journal=args.journal,
        article_type=args.article_type,
        language=args.language,
        journal_profile=args.journal_profile,
        csl=args.csl,
        line_spacing=args.line_spacing,
        output=str(config_path),
    )
    config = extract_config(extract_args)
    template = make_template(
        argparse.Namespace(
            config=str(config),
            base_template=args.base_template,
            language=args.language,
            journal_profile=args.journal_profile,
            output=str(template_path),
        )
    )
    export = export_docx(
        argparse.Namespace(
            source=args.source,
            output=str(output_path),
            config=str(config),
            reference_docx=str(template),
            from_format=args.from_format,
            bib=args.bib,
            csl=args.csl,
            toc=args.toc,
            require_media=args.require_media,
            require_numbered_references=args.require_numbered_references,
            line_spacing=args.line_spacing,
        )
    )
    print(f"CONFIG {config}")
    print(f"TEMPLATE {template}")
    print(f"DOCX {export}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_profiles = sub.add_parser("list-profiles", help="List bundled journal/style profiles and their CSL mappings")
    p_profiles.set_defaults(func=list_journal_profiles)

    p_extract = sub.add_parser("extract-config", help="Extract journal requirements JSON from a guidelines URL or saved text/html file")
    p_extract.add_argument("--guidelines-url")
    p_extract.add_argument("--guidelines-file")
    p_extract.add_argument("--journal")
    p_extract.add_argument("--journal-profile", help="Bundled profile id, such as nature, cell, ieee, or apa")
    p_extract.add_argument("--csl", help="CSL filename or path; also used to auto-select a bundled profile")
    p_extract.add_argument("--article-type")
    p_extract.add_argument("--language", choices=["en", "zh"])
    p_extract.add_argument("--line-spacing", choices=["1.0", "1.5", "2.0"])
    p_extract.add_argument("--output", required=True)
    p_extract.set_defaults(func=extract_config)

    p_template = sub.add_parser("make-template", help="Generate a journal reference DOCX from a config and bundled base template")
    p_template.add_argument("--config", required=True)
    p_template.add_argument("--journal-profile", help="Bundled profile id; overrides profile inference from config")
    p_template.add_argument("--base-template")
    p_template.add_argument("--language", choices=["en", "zh"])
    p_template.add_argument("--output", required=True)
    p_template.set_defaults(func=make_template)

    p_validate = sub.add_parser(
        "validate-docx", help="Run the final namespace-aware DOCX delivery audit"
    )
    p_validate.add_argument("--docx", required=True)
    p_validate.add_argument("--source", required=True, help="Canonical LaTeX/Markdown source")
    p_validate.add_argument("--report", help="Optional JSON audit report path")
    p_validate.set_defaults(func=validate_docx_command)

    p_export = sub.add_parser("export", help="Export TeX/Markdown to DOCX using Pandoc and a reference DOCX")
    p_export.add_argument("--source", required=True)
    p_export.add_argument("--output", required=True)
    p_export.add_argument("--config")
    p_export.add_argument("--reference-docx", required=True)
    p_export.add_argument("--from-format", choices=["latex", "markdown", "gfm", "commonmark"])
    p_export.add_argument("--bib")
    p_export.add_argument("--csl")
    p_export.add_argument("--toc", action="store_true")
    p_export.add_argument("--line-spacing", choices=["1.0", "1.5", "2.0"])
    p_export.add_argument(
        "--require-media",
        action="store_true",
        help="Fail unless the LaTeX source embeds at least one resolvable literal image",
    )
    p_export.add_argument(
        "--require-numbered-references",
        action="store_true",
        help="Require numeric CSL references and clickable Word REF fields for every numeric citation",
    )
    p_export.set_defaults(func=export_docx)

    p_all = sub.add_parser("all", help="Extract config, make template, then export DOCX")
    p_all.add_argument("--source", required=True)
    p_all.add_argument("--output", required=True)
    p_all.add_argument("--guidelines-url")
    p_all.add_argument("--guidelines-file")
    p_all.add_argument("--journal")
    p_all.add_argument("--journal-profile", help="Bundled profile id, such as nature, cell, ieee, or apa")
    p_all.add_argument("--article-type")
    p_all.add_argument("--language", choices=["en", "zh"])
    p_all.add_argument("--work-dir")
    p_all.add_argument("--config-name")
    p_all.add_argument("--template-name")
    p_all.add_argument("--base-template")
    p_all.add_argument("--from-format", choices=["latex", "markdown", "gfm", "commonmark"])
    p_all.add_argument("--bib")
    p_all.add_argument("--csl")
    p_all.add_argument("--toc", action="store_true")
    p_all.add_argument("--line-spacing", choices=["1.0", "1.5", "2.0"])
    p_all.add_argument(
        "--require-media",
        action="store_true",
        help="Fail unless the LaTeX source embeds at least one resolvable literal image",
    )
    p_all.add_argument(
        "--require-numbered-references",
        action="store_true",
        help="Require numeric CSL references and clickable Word REF fields for every numeric citation",
    )
    p_all.set_defaults(func=run_all)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.func(args)
    if isinstance(result, Path):
        print(result)


if __name__ == "__main__":
    main()
