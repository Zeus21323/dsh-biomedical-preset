"""Export a finalized SurveyMaster workspace to DOCX, TeX, and optional PDF.

The script keeps shared export concerns in one place: metadata resolution,
filename derivation, citation style lookup, LaTeX assembly, per-format checks,
and structured result reporting.
"""
import argparse
from copy import deepcopy
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


_ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
_KEYWORDS_RE = re.compile(r"\\keywords\{(.*?)\}", re.S)
_BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,]+),", re.S)
_LATEX_BIBLIOGRAPHY_COMMAND_RE = re.compile(
    r"(?m)^[ \t]*\\bibliography(?:style)?\s*\{[^}]*\}[ \t]*(?:%[^\n]*)?\n?"
)
_LATEX_THEBIBLIOGRAPHY_BLOCK_RE = re.compile(
    r"(?ms)^[ \t]*\\begin\{thebibliography\}\s*\{[^}]*\}.*?^[ \t]*\\end\{thebibliography\}[ \t]*(?:%[^\n]*)?\n?"
)
_SPLIT_CHEMICAL_MATH_RE = re.compile(
    r"(?<![\\$])"
    r"("
    r"[A-Za-z][A-Za-z0-9]*"
    r"(?:"
    r"\$(?:[_^](?:\{[^$\n]+\}|[^$\n]))\$"
    r"|[A-Za-z][A-Za-z0-9]*"
    r"|\([A-Za-z0-9]+\)"
    r")+"
    r")"
)
_BBL_BIBITEM_RE = re.compile(r"\\bibitem\s*(?:\[[\s\S]*?\]\s*)?\{\s*(?P<key>[\s\S]*?)\s*\}", re.M)
_BIB_LANGUAGE_RE = re.compile(
    r"(?i)(?:language|langid)\s*=\s*\{([^}]+)\}",
)
_BIB_TITLE_FIELD_RE = re.compile(r"(?i)\btitle\s*=\s*\{([^}]*(?:\}[^,\n}]*)?)\}")
_BIB_VENUE_FIELD_RE = re.compile(r"(?i)\b(?:journal|booktitle|organization)\s*=\s*\{([^}]*)\}")
_GBT_CSL_NAME_RE = re.compile(r"china-national-standard-gb-t-7714-2015", re.I)
_LATIN_AUTHOR_CITATION_ET_AL_RE = re.compile(
    r"(\([A-Z][A-Za-z.'-]+(?:\s+[A-Z][a-z.'-]+)*)\s+等,",
)
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_BIB_AUTHOR_FIELD_RE = re.compile(r"(?i)author\s*=\s*\{([^}]+)\}")
_GBT_PRINT_MEDIUM_RE = re.compile(r"\[(J|C)/OL\]")
_GBT_BIBLIOGRAPHY_LABEL_RE = re.compile(r"^\s*\[\d+\]")
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", _WORD_NS)
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_FIGURE_PLACEHOLDER_RE = re.compile(
    r'^[ \t]*%\s*FIGURE\s+id=(\S+)\s+prompt="((?:[^"\\]|\\.)*)"[ \t]*$',
    re.MULTILINE | re.IGNORECASE,
)
_FIGURE_COMMENT_RE = re.compile(
    r"^[ \t]*%\s*FIGURE\b.*$",
    re.MULTILINE | re.IGNORECASE,
)
# Matches a full figure block: the % FIGURE comment line + its \begin{figure}...\end{figure}
_FIGURE_BLOCK_RE = re.compile(
    r'([ \t]*%\s*FIGURE\s+id=(\S+)[^\n]*\n[ \t]*\\begin\{figure\}.*?\\end\{figure\})',
    re.DOTALL | re.IGNORECASE,
)
_FIGURE_ENV_RE = re.compile(r"\\begin\{figure\}(.*?)\\end\{figure\}", re.DOTALL)
_FLOAT_ENV_RE = re.compile(
    r"\\begin\{(?P<env>figure|table)\}(?P<body>.*?)\\end\{(?P=env)\}",
    re.DOTALL,
)
_CAPTION_RE = re.compile(r"\\caption(\{(?:[^{}]|\{[^{}]*\})*\})", re.DOTALL)
_LABEL_RE = re.compile(r"\\label\{(?P<label>(?:fig|tab):[^{}]+)\}")
_XREF_RE = re.compile(r"\\(?:auto)?ref\{(?P<label>(?:fig|tab):[^{}]+)\}")
_INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^{}]+)\}")
_TABLE_CAPTION_LINE_RE = re.compile(r"^(?:图|表|Figure|Table)\s+\d+\s*[.．。]")
_TABULAR_BEGIN_RE = re.compile(r"\\begin\{tabular\*?\}(?:\{[^{}]*\})?\{[^{}]*\}", re.DOTALL)
_SIMPLE_TABULAR_ENV_RE = re.compile(
    r"\\begin\{tabular\}\{(?P<cols>[lcr| \t]+)\}(?P<body>.*?)\\end\{tabular\}",
    re.DOTALL,
)
# Matches a URL ending with a bare query parameter (no value), indicating truncation.
# e.g. "...&ssr" or "...&ssr=" or "...&ssr." — the value was cut off.
_TRUNCATED_BIB_URL_RE = re.compile(r"[&][a-zA-Z0-9_%-]+=?\s*\.?\s*$")
_DOCX_RAW_TABLE_LEAK_RE = re.compile(r"\|[LCRlcr|]{3,}\||\\(?:toprule|midrule|bottomrule)\b|tabularx")
_DOCX_RAW_LABEL_LEAK_RE = re.compile(r"\[(?:tab|fig):[^\]]+\]")
_RAW_HTML_METADATA_TAG_LEAK_RE = re.compile(
    r"(?:<|&lt;)\s*/?\s*(?:scp|sup|sub|i|italic|em|b|strong|span)\b",
    re.I,
)
_DOCX_NUMERIC_REFERENCE_RE = re.compile(r"^\s*(?:\[(?P<bracketed>\d+)\]|(?P<plain>\d+)[.)])")
_DOCX_NUMERIC_CITATION_RE = re.compile(r"\[(?P<body>\d+(?:\s*(?:,|;|-|–|—)\s*\d+)*)\]")
_DOCX_NUMERIC_CITATION_TOKEN_RE = re.compile(r"\d+|\s*[,;\-–—]\s*")
_DOCX_SETTINGS_UPDATE_FIELDS_FOLLOWING_TAGS = {
    "hdrShapeDefaults",
    "footnotePr",
    "endnotePr",
    "compat",
    "docVars",
    "rsids",
    "mathPr",
    "attachedSchema",
    "themeFontLang",
    "clrSchemeMapping",
    "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures",
    "forceUpgrade",
    "captions",
    "readModeInkLockDown",
    "smartTagType",
    "schemaLibrary",
    "shapeDefaults",
    "doNotEmbedSmartTags",
    "decimalSymbol",
    "listSeparator",
}
_DOCX_TBL_PR_CHILD_ORDER = {
    "tblStyle": 0,
    "tblpPr": 1,
    "tblOverlap": 2,
    "bidiVisual": 3,
    "tblStyleRowBandSize": 4,
    "tblStyleColBandSize": 5,
    "tblW": 6,
    "jc": 7,
    "tblCellSpacing": 8,
    "tblInd": 9,
    "tblBorders": 10,
    "shd": 11,
    "tblLayout": 12,
    "tblCellMar": 13,
    "tblLook": 14,
    "tblCaption": 15,
    "tblDescription": 16,
    "tblPrChange": 17,
}
_DOCX_TBL_BORDERS_CHILD_ORDER = {
    "top": 0,
    "left": 1,
    "bottom": 2,
    "right": 3,
    "insideH": 4,
    "insideV": 5,
    "tl2br": 6,
    "tr2bl": 7,
}
_DOCX_STYLE_CHILD_ORDER = {
    "name": 0,
    "aliases": 1,
    "basedOn": 2,
    "next": 3,
    "link": 4,
    "autoRedefine": 5,
    "hidden": 6,
    "uiPriority": 7,
    "semiHidden": 8,
    "unhideWhenUsed": 9,
    "qFormat": 10,
    "locked": 11,
    "personal": 12,
    "personalCompose": 13,
    "personalReply": 14,
    "rsid": 15,
    "pPr": 16,
    "rPr": 17,
    "tblPr": 18,
    "trPr": 19,
    "tcPr": 20,
}
_DOCX_SETTINGS_CHILD_ORDER = {
    "writeProtection": 0,
    "view": 1,
    "zoom": 2,
    "removePersonalInformation": 3,
    "removeDateAndTime": 4,
    "doNotDisplayPageBoundaries": 5,
    "displayBackgroundShape": 6,
    "printPostScriptOverText": 7,
    "printFractionalCharacterWidth": 8,
    "printFormsData": 9,
    "embedTrueTypeFonts": 10,
    "embedSystemFonts": 11,
    "saveSubsetFonts": 12,
    "saveFormsData": 13,
    "mirrorMargins": 14,
    "alignBordersAndEdges": 15,
    "bordersDoNotSurroundHeader": 16,
    "bordersDoNotSurroundFooter": 17,
    "gutterAtTop": 18,
    "hideSpellingErrors": 19,
    "hideGrammaticalErrors": 20,
    "activeWritingStyle": 21,
    "proofState": 22,
    "formsDesign": 23,
    "attachedTemplate": 24,
    "linkStyles": 25,
    "stylePaneFormatFilter": 26,
    "stylePaneSortMethod": 27,
    "documentType": 28,
    "mailMerge": 29,
    "revisionView": 30,
    "trackRevisions": 31,
    "doNotTrackMoves": 32,
    "doNotTrackFormatting": 33,
    "documentProtection": 34,
    "autoFormatOverride": 35,
    "styleLockTheme": 36,
    "styleLockQFSet": 37,
    "defaultTabStop": 38,
    "autoHyphenation": 39,
    "consecutiveHyphenLimit": 40,
    "hyphenationZone": 41,
    "doNotHyphenateCaps": 42,
    "showEnvelope": 43,
    "summaryLength": 44,
    "clickAndTypeStyle": 45,
    "defaultTableStyle": 46,
    "evenAndOddHeaders": 47,
    "bookFoldRevPrinting": 48,
    "bookFoldPrinting": 49,
    "bookFoldPrintingSheets": 50,
    "drawingGridHorizontalSpacing": 51,
    "drawingGridVerticalSpacing": 52,
    "displayHorizontalDrawingGridEvery": 53,
    "displayVerticalDrawingGridEvery": 54,
    "doNotUseMarginsForDrawingGridOrigin": 55,
    "drawingGridHorizontalOrigin": 56,
    "drawingGridVerticalOrigin": 57,
    "doNotShadeFormData": 58,
    "noPunctuationKerning": 59,
    "characterSpacingControl": 60,
    "printTwoOnOne": 61,
    "strictFirstAndLastChars": 62,
    "noLineBreaksAfter": 63,
    "noLineBreaksBefore": 64,
    "savePreviewPicture": 65,
    "doNotValidateAgainstSchema": 66,
    "saveInvalidXml": 67,
    "ignoreMixedContent": 68,
    "alwaysShowPlaceholderText": 69,
    "doNotDemarcateInvalidXml": 70,
    "saveXmlDataOnly": 71,
    "useXSLTWhenSaving": 72,
    "saveThroughXslt": 73,
    "showXMLTags": 74,
    "alwaysMergeEmptyNamespace": 75,
    "updateFields": 76,
    "hdrShapeDefaults": 77,
    "footnotePr": 78,
    "endnotePr": 79,
    "compat": 80,
    "docVars": 81,
    "rsids": 82,
    "mathPr": 83,
    "attachedSchema": 84,
    "themeFontLang": 85,
    "clrSchemeMapping": 86,
    "doNotIncludeSubdocsInStats": 87,
    "doNotAutoCompressPictures": 88,
    "forceUpgrade": 89,
    "captions": 90,
    "readModeInkLockDown": 91,
    "smartTagType": 92,
    "schemaLibrary": 93,
    "shapeDefaults": 94,
    "doNotEmbedSmartTags": 95,
    "decimalSymbol": 96,
    "listSeparator": 97,
}
_DOCX_STYLE_SIZE_OVERRIDES = {
    "1": "24",
    "2": "28",
    "3": "24",
    "4": "24",
    "5": "28",
    "6": "20",
    "7": "24",
    "10": "32",
    "14": "32",
    "15": "28",
    "16": "24",
    "17": "24",
    "18": "28",
    "21": "24",
    "56": "20",
    "57": "20",
    "59": "21",
    "61": "24",
    "CaptionedFigure": "20",
}
_MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_MC_IGNORABLE = f"{{{_MC_NS}}}Ignorable"

CSL_BUNDLED_MAP: dict[str, str] = {
    "gb-t-7714-2015-author-date": "china-national-standard-gb-t-7714-2015-author-date.csl",
    "gb-t-7714-2015-numeric": "china-national-standard-gb-t-7714-2015-numeric.csl",
    "ama": "american-medical-association.csl",
    "apa": "apa.csl",
    "ieee": "ieee.csl",
    "nature": "nature.csl",
    "acs": "american-chemical-society.csl",
    "cell": "cell.csl",
    "science": "science.csl",
    "elsevier-with-titles": "elsevier-with-titles.csl",
    "rsc": "royal-society-of-chemistry.csl",
}

BUNDLED_CITATION_STYLES: tuple[str, ...] = tuple(CSL_BUNDLED_MAP.keys())

BIB_STYLE_MAP: dict[str, tuple[str, str]] = {
    "gb-t-7714-2015-author-date": ("gbt7714-author-year", "authoryear"),
    "gb-t-7714-2015-numeric": ("gbt7714-numerical", "numbers,sort&compress,super"),
    "ama": ("vancouver", "numbers,sort&compress,super"),
    "apa": ("apacite", "apaciteclassic"),
    "ieee": ("IEEEtran", "numbers,sort&compress"),
    "nature": ("naturemag", "numbers,sort&compress"),
    "acs": ("achemso", "numbers,sort&compress"),
    "cell": ("cell", "numbers,sort&compress"),
    "science": ("sciencemag", "numbers,sort&compress"),
    "elsevier-with-titles": ("elsarticle-num", "numbers,sort&compress"),
    "rsc": ("rsc", "numbers,sort&compress"),
}


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass
class ExportResult:
    format: str
    status: str
    path: Path | None = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export SurveyMaster deliverables")
    parser.add_argument("--survey-dir", required=True, help="Work dir containing mainbody.tex")
    parser.add_argument("--title", default="", help="Override title")
    parser.add_argument("--outline", default="", help="Outline JSON path")
    parser.add_argument("--bib", default="", help="Optional .bib file")
    parser.add_argument(
        "--citation-style",
        default="",
        help=(
            "Bundled citation style for all formats when --csl/--bib-style are unset "
            f"(supported: {', '.join(BUNDLED_CITATION_STYLES)}). "
            "Overrides writing_constraints.json when set."
        ),
    )
    parser.add_argument(
        "--csl",
        default="",
        help="Optional CSL override for DOCX (bundled style name or .csl path)",
    )
    parser.add_argument(
        "--bib-style",
        default="",
        help="Optional BibTeX override for PDF (bundled style name or .bst base name)",
    )
    parser.add_argument("--skill-dir", default="", help="Path to this skill directory")
    parser.add_argument("--language", required=True, choices=("zh", "en"), help="Output language resolved from the current user request")
    parser.add_argument("--formats", default=None, help="Comma-separated formats")
    parser.add_argument(
        "--optional-formats",
        default=None,
        help=(
            "Comma-separated requested formats whose failure should not make the "
            "export command fail. By default, PDF is optional only for the default "
            "format set."
        ),
    )
    return parser.parse_args(argv)


class JsonConfigError(RuntimeError):
    """Raised when a JSON config file is malformed and cannot be repaired."""


def read_json_with_warnings(path: Path, *, write_repaired: bool = False) -> tuple[dict, list[str]]:
    if not path.exists():
        return {}, []
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        return (data if isinstance(data, dict) else {}), []
    except json.JSONDecodeError as exc:
        parse_error = exc

    try:
        import json_repair  # type: ignore[import]

        repaired = json_repair.repair_json(raw, return_objects=True)
    except ImportError:
        raise JsonConfigError(
            f"{path.name} is invalid JSON and json_repair is not installed: {parse_error}"
        ) from parse_error
    except Exception as exc:
        raise JsonConfigError(f"{path.name} is invalid JSON and json_repair failed: {exc}") from exc

    if not isinstance(repaired, dict):
        raise JsonConfigError(f"{path.name} is invalid JSON and json_repair did not return an object")

    if write_repaired:
        path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return repaired, [f"{path.name}_repaired: invalid JSON was repaired by json_repair and written back"]

    return repaired, [f"{path.name}_repaired: invalid JSON was repaired by json_repair"]


def read_json(path: Path) -> dict:
    data, _ = read_json_with_warnings(path)
    return data


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def resolve_title(survey_dir: Path, explicit: str = "", outline: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    outline_path = Path(outline) if outline else survey_dir / "outline.json"
    title = str(read_json(outline_path).get("survey_title") or "").strip()
    return title or "Survey"


def derive_stem(title: str) -> str:
    stem = re.sub(r'[\\/*?:"<>|]', "", title).strip().replace(" ", "_")
    return stem[:80] or "survey"


def citation_style_from_constraints(survey_dir: Path) -> tuple[str, list[str]]:
    data, warnings = read_json_with_warnings(survey_dir / "writing_constraints.json", write_repaired=True)
    return str(data.get("citation_style") or "").strip(), warnings


def default_citation_style_for_language(lang: str) -> str:
    return "gb-t-7714-2015-numeric" if lang == "zh" else "science"


def resolve_citation_style_name(
    survey_dir: Path,
    lang: str,
    *,
    citation_style_arg: str = "",
) -> tuple[str, str, list[str]]:
    """Return (style_name, source, warnings)."""
    warnings: list[str] = []
    explicit = citation_style_arg.strip()
    if explicit:
        return explicit, "cli", warnings

    from_constraints, constraint_warnings = citation_style_from_constraints(survey_dir)
    warnings.extend(constraint_warnings)
    if from_constraints:
        return from_constraints, "writing_constraints", warnings

    fallback = default_citation_style_for_language(lang)
    warnings.append(
        "citation_style_fallback: writing_constraints.json has no citation_style; "
        f"using language default {fallback} for lang={lang}. "
        "Pass --citation-style <name> to override explicitly."
    )
    return fallback, "fallback", warnings


def style_from_constraints(survey_dir: Path, lang: str) -> str:
    style_name, _, _ = resolve_citation_style_name(survey_dir, lang)
    return style_name


def is_unified_export_dir(path: Path) -> bool:
    legacy_prefixes = (
        "surveymaster-export-docx",
        "surveymaster-export-pdf",
    )
    if path.name.startswith(legacy_prefixes):
        return False
    return path.name == "surveymaster-export" or path.name.startswith("surveymaster-export-")


def find_export_skill_dir(skill_dir: str | Path) -> tuple[Path | None, str | None]:
    if not skill_dir:
        return None, "missing_skill_dir"

    direct = Path(skill_dir)
    if is_unified_export_dir(direct) and ((direct / "SKILL.md").exists() or direct.exists()):
        return direct, None
    return None, f"surveymaster_export_skill_dir_missing: {direct}"


def find_asset_dir(skill_dir: str | Path, name: str) -> tuple[Path | None, str | None]:
    export_dir, err = find_export_skill_dir(skill_dir)
    if err or export_dir is None:
        return None, err

    candidate = export_dir / name
    if candidate.is_dir():
        return candidate, None
    return None, f"asset_dir_missing({name}): {candidate}"


def resolve_docx_template(skill_dir: str | Path, lang: str | None = None) -> tuple[Path | None, str | None]:
    docx_dir, err = find_asset_dir(skill_dir, "docx")
    if err or docx_dir is None:
        return None, err
    if lang in {"zh", "en"}:
        localized_template = docx_dir / f"template-{lang}.docx"
        if localized_template.exists():
            return localized_template, None
    template = docx_dir / "template-zh.docx" # default to zh template
    if template.exists():
        return template, None
    return None, f"docx_template_missing: {template}"


def resolve_csl(
    csl_arg: str,
    survey_dir: Path,
    skill_dir: str | Path,
    lang: str,
    *,
    citation_style_name: str = "",
) -> tuple[Path | None, str | None]:
    style_name = csl_arg.strip() or citation_style_name or style_from_constraints(survey_dir, lang)

    explicit = Path(style_name)
    if explicit.suffix == ".csl":
        if explicit.exists():
            return explicit, None
        return None, f"csl_file_not_found: {explicit}"

    filename = CSL_BUNDLED_MAP.get(style_name)
    if not filename:
        return None, f"unknown_csl_style: {style_name}"

    csl_dir, err = find_asset_dir(skill_dir, "csl")
    if err or csl_dir is None:
        return None, err

    csl_path = csl_dir / filename
    if not csl_path.exists():
        return None, f"bundled_csl_missing: {csl_path}"
    return csl_path, None


def resolve_bib_style(
    style_arg: str,
    survey_dir: Path,
    lang: str,
    *,
    citation_style_name: str = "",
) -> tuple[str, str]:
    style_name = style_arg.strip() or citation_style_name or style_from_constraints(survey_dir, lang)
    return BIB_STYLE_MAP.get(style_name, (style_name, "numbers,sort&compress"))


def citation_package_line(bib_style: str, package_option: str) -> str:
    if bib_style == "apacite" and package_option == "apaciteclassic":
        return "\\usepackage[apaciteclassic]{apacite}"
    return f"\\usepackage[{package_option}]{{natbib}}"


def citation_package_name(bib_style: str, package_option: str) -> str:
    if bib_style == "apacite" and package_option == "apaciteclassic":
        return "apacite"
    return "natbib"


def run_command(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout: int = 120,
) -> CommandResult:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return CommandResult(127, "", f"dependency_not_found: {exc.filename}")
    except subprocess.TimeoutExpired as exc:
        return CommandResult(124, exc.stdout or "", exc.stderr or f"command_timeout: {' '.join(cmd)}")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def bib_keys(bib_path: Path) -> list[str]:
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    return [match.group(1).strip() for match in _BIB_ENTRY_RE.finditer(text) if match.group(1).strip()]


def bib_entry_count(bib_path: Path) -> int:
    if not bib_path.exists():
        return 0
    return len(bib_keys(bib_path))


def bbl_keys(bbl_path: Path) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    text = bbl_path.read_text(encoding="utf-8", errors="replace")
    for match in _BBL_BIBITEM_RE.finditer(text):
        key = re.sub(r"\s+", "", match.group("key").replace("%", "")).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def bib_entries_by_key(bib_path: Path) -> dict[str, str]:
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    matches = list(_BIB_ENTRY_RE.finditer(text))
    entries: dict[str, str] = {}
    for idx, match in enumerate(matches):
        key = match.group(1).strip()
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        if key and key not in entries:
            entries[key] = text[start:end].strip() + "\n"
    return entries


def _normalize_bib_language(raw: str) -> str | None:
    value = raw.strip().lower().replace("_", "-")
    if not value:
        return None
    if value.startswith("en"):
        return "en"
    if value.startswith("zh"):
        return "zh"
    return None


def bib_languages_by_key(bib_path: Path) -> dict[str, str]:
    entries = bib_entries_by_key(bib_path)
    languages: dict[str, str] = {}
    for key, entry in entries.items():
        for match in _BIB_LANGUAGE_RE.finditer(entry):
            normalized = _normalize_bib_language(match.group(1))
            if normalized:
                languages[key] = normalized
                break
    return languages


def _bib_first_author_is_cjk(entry_text: str) -> bool | None:
    """Return True if first author contains CJK chars, False if not, None if no author field."""
    m = _BIB_AUTHOR_FIELD_RE.search(entry_text)
    if not m:
        return None
    first_author = m.group(1).split(" and ")[0]
    return bool(_CJK_RE.search(first_author))


def _bib_text_fields_look_english(entry_text: str) -> bool:
    fields = [m.group(1) for m in _BIB_TITLE_FIELD_RE.finditer(entry_text)]
    fields.extend(m.group(1) for m in _BIB_VENUE_FIELD_RE.finditer(entry_text))
    if not fields:
        return False
    text = re.sub(r"[^A-Za-z\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", "", " ".join(fields))
    if not text:
        return False
    latin = len(re.findall(r"[A-Za-z]", text))
    cjk = len(_CJK_RE.findall(text))
    return latin >= 20 and latin > cjk * 3


def resolve_english_bib_keys(bib_path: Path) -> set[str]:
    """Return bib keys that represent English-language references.

    Priority:
    1. explicit language/langid=en* → English
    2. explicit language/langid=zh* → Chinese (excluded)
    3. no language field + title/venue mostly English → treated as English
    4. no language field + first author non-CJK → treated as English
    5. no language field + first author CJK → treated as Chinese (excluded)
    6. no language field + no author/title signal → ambiguous, skip conservatively
    """
    entries = bib_entries_by_key(bib_path)
    languages = bib_languages_by_key(bib_path)
    english: set[str] = set()
    for key, entry in entries.items():
        explicit_lang = languages.get(key)
        if explicit_lang == "en":
            english.add(key)
        elif explicit_lang == "zh":
            pass
        else:
            is_cjk = _bib_first_author_is_cjk(entry)
            if _bib_text_fields_look_english(entry) or is_cjk is False:
                english.add(key)
    return english


def _author_family_marker(author: str) -> str:
    author = re.sub(r"\s+", " ", author.strip())
    if not author:
        return ""
    if "," in author:
        return author.split(",", 1)[0].strip().upper()
    parts = author.split()
    if len(parts) >= 2:
        return parts[-1].strip().upper()
    return author.upper()


def is_gbt_csl(csl: Path | None) -> bool:
    if csl is None:
        return False
    return bool(_GBT_CSL_NAME_RE.search(csl.name))


def _replace_english_et_al_in_text(text: str) -> str:
    text = re.sub(r",\s*等\s*,", ", et al.,", text)
    text = re.sub(r"\s+等\s*,", " et al.,", text)
    text = re.sub(r"\s+等\s*\.", " et al.", text)
    return text


def _fix_gbt_print_medium_labels(text: str) -> str:
    """Keep journal/conference labels print-only even when CSL includes URL/DOI."""
    return _GBT_PRINT_MEDIUM_RE.sub(r"[\1]", text)


def english_bib_author_markers(bib_path: Path) -> list[str]:
    english_keys = resolve_english_bib_keys(bib_path)
    markers: list[str] = []
    for key, entry in bib_entries_by_key(bib_path).items():
        if key not in english_keys:
            continue
        author_match = _BIB_AUTHOR_FIELD_RE.search(entry)
        if not author_match:
            continue
        first_author = author_match.group(1).split(" and ")[0]
        family = _author_family_marker(first_author)
        if family and family not in markers:
            markers.append(family)
    return markers


def _looks_like_english_bibliography_paragraph(text: str, author_markers: list[str]) -> bool:
    if "等" not in text:
        return False
    upper_text = text.upper()
    if any(marker in upper_text for marker in author_markers):
        return True
    text_without_deng = text.replace("等", "")
    return bool(re.search(r"[A-Za-z]", text_without_deng)) and _CJK_RE.search(text_without_deng) is None


def _fix_gbt_body_citation_text(text: str) -> str:
    return _LATIN_AUTHOR_CITATION_ET_AL_RE.sub(r"\1 et al.,", text)


def _paragraph_text_nodes(paragraph: ET.Element) -> list[ET.Element]:
    return [node for node in paragraph.iter(word_tag("t"))]


def _set_paragraph_text(paragraph: ET.Element, new_text: str) -> None:
    nodes = _paragraph_text_nodes(paragraph)
    if not nodes:
        run = ET.SubElement(paragraph, word_tag("r"))
        text_node = ET.SubElement(run, word_tag("t"))
        text_node.text = new_text
        return
    nodes[0].text = new_text
    for node in nodes[1:]:
        node.text = ""


def _references_heading_labels(lang: str) -> tuple[str, ...]:
    if lang == "zh":
        return ("参考文献", "References")
    return ("References", "参考文献")


def _find_references_start_index(body_children: list[ET.Element], lang: str) -> int | None:
    labels = _references_heading_labels(lang)
    for idx, child in enumerate(body_children):
        if child.tag != word_tag("p"):
            continue
        text = element_text(child).strip()
        if text in labels:
            return idx
    return None


def fix_gbt_bilingual_in_docx(
    docx_path: Path,
    bib_path: Path | None,
    csl: Path | None,
    lang: str,
) -> str | None:
    if not is_gbt_csl(csl) or bib_path is None or not bib_path.exists():
        return None
    author_markers = english_bib_author_markers(bib_path)

    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"

    children = list(body)
    refs_start = _find_references_start_index(children, lang)
    body_end = refs_start if refs_start is not None else len(children)
    refs_begin = (refs_start + 1) if refs_start is not None else len(children)

    for child in children[:body_end]:
        if child.tag != word_tag("p"):
            continue
        text = element_text(child)
        fixed = _fix_gbt_body_citation_text(text)
        if fixed != text:
            _set_paragraph_text(child, fixed)

    for child in children[refs_begin:]:
        if child.tag != word_tag("p"):
            continue
        text = element_text(child)
        fixed = _fix_gbt_print_medium_labels(text) if _GBT_BIBLIOGRAPHY_LABEL_RE.match(text) else text
        if _looks_like_english_bibliography_paragraph(fixed, author_markers):
            fixed = _replace_english_et_al_in_text(fixed)
        if fixed != text:
            _set_paragraph_text(child, fixed)

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def rebuild_references_from_build_bib(
    survey_dir: Path,
    build_dir: Path,
    bbl_path: Path,
) -> tuple[bool, str]:
    build_bib = build_dir / "references.bib"
    if not build_bib.exists():
        return False, f"build_bib_missing: {build_bib}"
    ordered_keys = bbl_keys(bbl_path)
    if not ordered_keys:
        return False, f"bbl_keys_empty: {bbl_path}"
    entries = bib_entries_by_key(build_bib)
    missing = [key for key in ordered_keys if key not in entries]
    if missing:
        return False, f"build_bib_missing_bbl_keys: {missing[:10]}{'...' if len(missing) > 10 else ''}"
    body = "\n".join(entries[key].rstrip() for key in ordered_keys) + "\n"
    if not body.strip():
        return False, f"references_rebuild_empty: {build_bib}"
    bib_final = survey_dir / "references.bib"
    bib_final.write_text(body, encoding="utf-8")
    build_bib.write_text(body, encoding="utf-8")
    return True, ""


def coalesce_split_chemical_math_fragments_for_docx(latex: str) -> str:
    """Merge tokens like M$_n$X$_x$ into one math span for Pandoc DOCX."""

    def repl(match: re.Match) -> str:
        expression = match.group(1)
        if "$" not in expression:
            return expression
        merged = re.sub(r"\$([^$\n]+)\$", r"\1", expression)
        return f"${merged}$"

    return _SPLIT_CHEMICAL_MATH_RE.sub(repl, latex)


def localized_float_name(env_name: str, number: int, lang: str) -> str:
    if lang == "zh":
        prefix = "图" if env_name == "figure" else "表"
    else:
        prefix = "Figure" if env_name == "figure" else "Table"
    return f"{prefix} {number}"


def caption_inner(caption_arg: str) -> str:
    return caption_arg[1:-1] if caption_arg.startswith("{") and caption_arg.endswith("}") else caption_arg


def caption_label(caption_text: str) -> str | None:
    match = _LABEL_RE.search(caption_text)
    return match.group("label") if match else None


def collect_float_label_texts(latex: str, lang: str) -> dict[str, str]:
    counters = {"figure": 0, "table": 0}
    labels: dict[str, str] = {}
    for match in _FLOAT_ENV_RE.finditer(latex):
        caption_match = _CAPTION_RE.search(match.group("body"))
        if caption_match is None:
            continue
        env_name = match.group("env")
        counters[env_name] += 1
        label = caption_label(caption_inner(caption_match.group(1)))
        if label:
            labels[label] = localized_float_name(env_name, counters[env_name], lang)
    return labels


def render_float_refs_for_plain_export(latex: str, lang: str) -> str:
    """Pre-render figure/table labels for Pandoc, which does not resolve LaTeX refs."""
    labels = collect_float_label_texts(latex, lang)
    counters = {"figure": 0, "table": 0}

    def replace_float(match: re.Match) -> str:
        env_name = match.group("env")
        body = match.group("body")
        caption_match = _CAPTION_RE.search(body)
        if caption_match is None:
            return match.group(0)
        counters[env_name] += 1
        number_text = localized_float_name(env_name, counters[env_name], lang)
        original_caption = caption_inner(caption_match.group(1))
        clean_caption = _LABEL_RE.sub("", original_caption).strip()
        caption_text = f"{number_text}. {clean_caption}" if clean_caption else number_text
        replaced_body = body[:caption_match.start()] + f"\\caption{{{caption_text}}}" + body[caption_match.end():]
        return f"\\begin{{{env_name}}}{replaced_body}\\end{{{env_name}}}"

    rendered = _FLOAT_ENV_RE.sub(replace_float, latex)
    rendered = _XREF_RE.sub(lambda match: labels.get(match.group("label"), match.group(0)), rendered)
    return collapse_duplicate_float_ref_prefixes(rendered, lang)


def collapse_duplicate_float_ref_prefixes(text: str, lang: str) -> str:
    """Remove prose prefixes duplicated by pre-rendered float references.

    When source prose says ``表 \autoref{tab:x}``, pre-rendering turns it into
    ``表 表 2`` for Pandoc-based exports. Keep the resolved reference and drop
    the hand-written prefix.
    """
    if lang == "zh":
        text = re.sub(r"(?<![\w\\])图\s+(图\s+\d+)", r"\1", text)
        text = re.sub(r"(?<![\w\\])表\s+(表\s+\d+)", r"\1", text)
    else:
        text = re.sub(r"\bFigure\s+(Figure\s+\d+)", r"\1", text)
        text = re.sub(r"\bTable\s+(Table\s+\d+)", r"\1", text)
    return text


def ensure_float_centering(latex: str) -> str:
    def replace_float(match: re.Match) -> str:
        env_name = match.group("env")
        body = match.group("body")
        if re.search(r"\\centering\b", body):
            return match.group(0)
        return f"\\begin{{{env_name}}}[H]\n  \\centering{body}\\end{{{env_name}}}"

    return _FLOAT_ENV_RE.sub(replace_float, latex)


def move_table_captions_above_tabular(latex: str) -> str:
    def replace_float(match: re.Match) -> str:
        if match.group("env") != "table":
            return match.group(0)
        body = match.group("body")
        caption_match = _CAPTION_RE.search(body)
        tabular_match = _TABULAR_BEGIN_RE.search(body)
        if caption_match is None or tabular_match is None or caption_match.start() < tabular_match.start():
            return match.group(0)
        caption = caption_match.group(0)
        without_caption = body[:caption_match.start()] + body[caption_match.end():]
        tabular_match = _TABULAR_BEGIN_RE.search(without_caption)
        if tabular_match is None:
            return match.group(0)
        new_body = without_caption[:tabular_match.start()] + "  " + caption + "\n" + without_caption[tabular_match.start():]
        return f"\\begin{{table}}[H]{new_body}\\end{{table}}"

    return _FLOAT_ENV_RE.sub(replace_float, latex)


def fix_triple_backslash_before_bottomrule(latex: str) -> str:
    """Fix \\\\\\\n\\bottomrule → \\\\\n\\bottomrule.

    A stray third backslash before \\bottomrule corrupts the row terminator
    and distorts the rule length.  Strip the extra backslash.
    """
    return re.sub(r"\\\\\\([ \t]*\n)([ \t]*\\bottomrule)", r"\\\\\1\2", latex)


def normalize_float_layout_for_export(latex: str) -> str:
    return fix_triple_backslash_before_bottomrule(
        ensure_float_centering(move_table_captions_above_tabular(latex))
    )


def tabularx_columns_from_simple_colspec(colspec: str) -> str | None:
    normalized = re.sub(r"\s+", "", colspec)
    if not normalized or re.search(r"[^lcr|]", normalized):
        return None
    return normalized.translate(str.maketrans({"l": "L", "c": "C", "r": "R"}))


def wrap_simple_pdf_tabulars_with_tabularx(latex: str) -> str:
    def replace(match: re.Match) -> str:
        columns = tabularx_columns_from_simple_colspec(match.group("cols"))
        if columns is None:
            return match.group(0)
        return (
            f"\\begin{{tabularx}}{{\\textwidth}}{{{columns}}}"
            f"{match.group('body')}"
            "\\end{tabularx}"
        )

    return _SIMPLE_TABULAR_ENV_RE.sub(replace, latex)


def assemble_docx_input(survey_dir: Path, stem: str, lang: str) -> tuple[Path | None, list[str]]:
    # mainbody.tex contains abstract, keywords, and all sections.
    # Transform the abstract and keywords in-place so pandoc can render them
    # (pandoc does not know \begin{abstract} or \keywords{} from SciMasterNoBrand.cls).
    body = strip_latex_bibliography_commands((survey_dir / "mainbody.tex").read_text(encoding="utf-8"))
    if re.search(r"\\begin\{tabularx\}", body):
        return None, ["DOCX_INPUT_UNSUPPORTED_TABULARX: use tabular in mainbody.tex; tabularx is reserved for TeX/PDF export"]
    abstract_err = check_abstract_float_refs(body)
    if abstract_err:
        return None, [abstract_err]
    float_err = check_unreferenced_floats(body)
    if float_err:
        return None, [float_err]
    table_err = check_table_has_tabular(body)
    if table_err:
        return None, [table_err]
    body = reposition_figures_after_first_ref(body)
    body, fig_warnings = inject_figure_placeholders(body, survey_dir)
    missing_figs = [w for w in fig_warnings if w.startswith("figure_missing:")]
    if missing_figs:
        return None, missing_figs
    body = normalize_float_layout_for_export(body)
    body = render_float_refs_for_plain_export(body, lang)
    abstract_label = "摘要：" if lang == "zh" else "Abstract: "
    body = _ABSTRACT_RE.sub(
        lambda m: (
            "\\noindent\\textbf{" + abstract_label + "}" + m.group(1).strip() + "\\par\\bigskip"
        ),
        body,
    )
    body = _KEYWORDS_RE.sub(
        lambda m: (
            "\\noindent\\textbf{" + ("关键词：" if lang == "zh" else "Keywords: ") + "}"
            + m.group(1).strip() + "\\par\\bigskip"
        ),
        body,
    )
    # Strip layout commands pandoc cannot meaningfully render
    body = re.sub(r"\\maketitle\b", "", body)
    body = re.sub(r"\\tableofcontents\b", "", body)
    body = re.sub(r"\\newpage\b", "", body)
    body = coalesce_split_chemical_math_fragments_for_docx(body)
    output = survey_dir / f"{stem}_full.tex"
    output.write_text(body, encoding="utf-8")
    return output, fig_warnings


def write_docx_meta(build_dir: Path, title: str, lang: str) -> Path:
    ref_heading = "参考文献" if lang == "zh" else "References"
    toc_heading = "目录" if lang == "zh" else "Table of Contents"
    meta = build_dir / "meta.yaml"
    meta.write_text(
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"toc-title: {json.dumps(toc_heading, ensure_ascii=False)}\n"
        f"reference-section-title: {json.dumps(ref_heading, ensure_ascii=False)}\n"
        "---\n",
        encoding="utf-8",
    )
    return meta


def check_docx(docx_path: Path) -> list[str]:
    issues: list[str] = []
    source_tex_path = docx_path.parent / "mainbody.tex"
    source_tex = source_tex_path.read_text(encoding="utf-8", errors="replace") if source_tex_path.exists() else ""
    bib_exists = (docx_path.parent / "references.bib").exists()
    try:
        with zipfile.ZipFile(docx_path) as archive:
            names = set(archive.namelist())
            if "word/document.xml" not in names:
                issues.append("DOCX_DOCUMENT_XML_MISSING")
            else:
                document_xml = archive.read("word/document.xml")
                xml = document_xml.decode("utf-8", errors="replace")
                text = re.sub(r"<[^>]+>", " ", xml)
                if len(text.split()) < 50:
                    issues.append("DOCX_CONTENT_SUSPICIOUSLY_SHORT")
                issues.extend(check_docx_openxml_member("word/document.xml", document_xml))
                issues.extend(check_docx_document_structure(document_xml, source_tex, bib_exists))
            for member_name in ("word/styles.xml", "word/numbering.xml"):
                if member_name in names:
                    issues.extend(check_docx_openxml_member(member_name, archive.read(member_name)))
            if "docProps/core.xml" in names:
                core = archive.read("docProps/core.xml").decode("utf-8", errors="replace")
                if "<dc:title>" not in core:
                    issues.append("DOCX_TITLE_METADATA_MISSING")
    except zipfile.BadZipFile:
        issues.append("DOCX_ARCHIVE_INVALID")
    return issues


def check_docx_document_structure(document_xml: bytes, source_tex: str = "", bib_exists: bool = False) -> list[str]:
    issues: list[str] = []
    xml_text = document_xml.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        return ["DOCX_STRUCTURE_PARSE_FAILED:word/document.xml"]

    visible_text = element_text(root)
    if _DOCX_RAW_TABLE_LEAK_RE.search(visible_text):
        issues.append("DOCX_RAW_LATEX_TABLE_LEAK")
    if _DOCX_RAW_LABEL_LEAK_RE.search(visible_text):
        issues.append("DOCX_RAW_LABEL_LEAK")
    if _RAW_HTML_METADATA_TAG_LEAK_RE.search(visible_text):
        issues.append("DOCX_RAW_HTML_TAG_LEAK")

    source_has_table = bool(re.search(r"\\begin\{(?:table|tabular|tabularx)\}", source_tex))
    if source_has_table and not any(True for _ in root.iter(word_tag("tbl"))):
        issues.append("DOCX_NO_WORD_TABLES_WHEN_SOURCE_HAS_TABLE")

    if source_tex:
        if "\\begin{abstract}" in source_tex and not re.search(r"(摘要|Abstract)\s*[：:]", visible_text):
            issues.append("DOCX_ABSTRACT_MISSING")
        if "\\keywords{" in source_tex and not re.search(r"(关键词|Keywords)\s*[：:]", visible_text):
            issues.append("DOCX_KEYWORDS_MISSING")
    if bib_exists and "参考文献" not in visible_text and "References" not in visible_text:
        issues.append("DOCX_REFERENCES_HEADING_MISSING")

    if "\\cite{" in source_tex and " REF _Ref" not in xml_text and re.search(r"\[\d+\]", visible_text):
        issues.append("DOCX_REF_FIELDS_MISSING")

    return issues


def issues_are_only_docx_openxml_conformance(issues: list[str]) -> bool:
    return bool(issues) and all(issue.startswith("DOCX_OPENXML_") for issue in issues)


def check_docx_openxml_member(member_name: str, xml: bytes) -> list[str]:
    issues: list[str] = []
    text = xml.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return [f"DOCX_OPENXML_PARSE_FAILED:{member_name}"]

    for run_properties in root.iter(word_tag("rPr")):
        child_names = [docx_local_name(child.tag) for child in list(run_properties)]
        if "bCs" in child_names and "b" in child_names and child_names.index("bCs") < child_names.index("b"):
            issues.append(f"DOCX_OPENXML_RPR_B_ORDER:{member_name}")
            break

    for table_header in root.iter(word_tag("tblHeader")):
        if word_tag("val") in table_header.attrib:
            issues.append(f"DOCX_OPENXML_TBLHEADER_VAL:{member_name}")
            break

    ignorable_attr = f"{{{_MC_NS}}}Ignorable"
    ignorable = root.attrib.get(ignorable_attr)
    if ignorable:
        undefined_tokens = [
            token
            for token in ignorable.split()
            if f"xmlns:{token}=" not in text
        ]
        if undefined_tokens:
            issues.append(f"DOCX_OPENXML_UNDEFINED_IGNORABLE:{member_name}:{','.join(undefined_tokens)}")

    return issues


def word_tag(name: str) -> str:
    return f"{{{_WORD_NS}}}{name}"


def element_text(element: ET.Element) -> str:
    return "".join(element.itertext())


def is_word_field_run(run: ET.Element) -> bool:
    return any(
        node.tag in {word_tag("fldChar"), word_tag("instrText")}
        for node in run.iter()
    )


def paragraph_has_word_field(paragraph: ET.Element) -> bool:
    return any(is_word_field_run(run) for run in paragraph.findall(word_tag("r")))


def paragraph_runs_have_simple_text(paragraph: ET.Element) -> bool:
    for run in paragraph.findall(word_tag("r")):
        if is_word_field_run(run):
            return False
        non_property_children = [child for child in list(run) if child.tag != word_tag("rPr")]
        if not non_property_children:
            continue
        if any(child.tag != word_tag("t") for child in non_property_children):
            return False
    return True


def remove_existing_bookmark(paragraph: ET.Element, bookmark_name: str) -> None:
    bookmark_ids: set[str] = set()
    for node in list(paragraph.iter(word_tag("bookmarkStart"))):
        if node.attrib.get(word_tag("name")) != bookmark_name:
            continue
        bookmark_id = node.attrib.get(word_tag("id"))
        if bookmark_id is not None:
            bookmark_ids.add(bookmark_id)
        parent = _element_parent(paragraph, node)
        if parent is not None:
            parent.remove(node)
    for node in list(paragraph.iter(word_tag("bookmarkEnd"))):
        if node.attrib.get(word_tag("id")) not in bookmark_ids:
            continue
        parent = _element_parent(paragraph, node)
        if parent is not None:
            parent.remove(node)


def _element_parent(root: ET.Element, target: ET.Element) -> ET.Element | None:
    for parent in root.iter():
        if target in list(parent):
            return parent
    return None


def make_docx_bookmark_start(bookmark_id: int, bookmark_name: str) -> ET.Element:
    bookmark_start = ET.Element(word_tag("bookmarkStart"))
    bookmark_start.set(word_tag("id"), str(bookmark_id))
    bookmark_start.set(word_tag("name"), bookmark_name)
    return bookmark_start


def make_docx_bookmark_end(bookmark_id: int) -> ET.Element:
    bookmark_end = ET.Element(word_tag("bookmarkEnd"))
    bookmark_end.set(word_tag("id"), str(bookmark_id))
    return bookmark_end


def apply_run_superscript(run: ET.Element) -> None:
    run_properties = run.find(word_tag("rPr"))
    if run_properties is None:
        run_properties = ET.Element(word_tag("rPr"))
        run.insert(0, run_properties)
    vertical_align = run_properties.find(word_tag("vertAlign"))
    if vertical_align is None:
        vertical_align = ET.Element(word_tag("vertAlign"))
        run_properties.append(vertical_align)
    vertical_align.set(word_tag("val"), "superscript")


def remove_run_vertical_align(run: ET.Element) -> None:
    run_properties = run.find(word_tag("rPr"))
    if run_properties is None:
        return
    vertical_align = run_properties.find(word_tag("vertAlign"))
    if vertical_align is not None:
        run_properties.remove(vertical_align)


def apply_template_run_properties(
    run: ET.Element,
    template_run: ET.Element | None = None,
    *,
    superscript: bool = False,
) -> None:
    if template_run is not None:
        run_properties = template_run.find(word_tag("rPr"))
        if run_properties is not None:
            run.insert(0, deepcopy(run_properties))
    if superscript:
        apply_run_superscript(run)
    else:
        remove_run_vertical_align(run)


def make_text_run(
    text: str,
    template_run: ET.Element | None = None,
    *,
    superscript: bool = False,
) -> ET.Element:
    run = ET.Element(word_tag("r"))
    apply_template_run_properties(run, template_run, superscript=superscript)
    text_node = ET.SubElement(run, word_tag("t"))
    if text[:1].isspace() or text[-1:].isspace():
        text_node.set(_XML_SPACE, "preserve")
    text_node.text = text
    return run


def make_docx_ref_field_runs(
    instruction: str,
    display_text: str,
    template_run: ET.Element | None = None,
    *,
    superscript: bool = False,
) -> list[ET.Element]:
    begin_run = ET.Element(word_tag("r"))
    apply_template_run_properties(begin_run, template_run, superscript=superscript)
    begin = ET.SubElement(begin_run, word_tag("fldChar"))
    begin.set(word_tag("fldCharType"), "begin")

    instr_run = ET.Element(word_tag("r"))
    apply_template_run_properties(instr_run, template_run, superscript=superscript)
    instr = ET.SubElement(instr_run, word_tag("instrText"))
    instr.set(_XML_SPACE, "preserve")
    instr.text = f" {instruction.strip()} \\* MERGEFORMAT "

    separate_run = ET.Element(word_tag("r"))
    apply_template_run_properties(separate_run, template_run, superscript=superscript)
    separate = ET.SubElement(separate_run, word_tag("fldChar"))
    separate.set(word_tag("fldCharType"), "separate")

    result_run = make_text_run(display_text, template_run, superscript=superscript)

    end_run = ET.Element(word_tag("r"))
    apply_template_run_properties(end_run, template_run, superscript=superscript)
    end = ET.SubElement(end_run, word_tag("fldChar"))
    end.set(word_tag("fldCharType"), "end")

    return [begin_run, instr_run, separate_run, result_run, end_run]


def make_docx_field_run(
    instruction: str,
    display_text: str,
    template_run: ET.Element | None = None,
    *,
    superscript: bool = False,
) -> ET.Element:
    runs = make_docx_ref_field_runs(
        instruction,
        display_text,
        template_run,
        superscript=superscript,
    )
    wrapper = ET.Element(word_tag("r"))
    for run in runs:
        for child in list(run):
            wrapper.append(deepcopy(child))
    if superscript:
        apply_run_superscript(wrapper)
    return wrapper


def references_heading_index(body_children: list[ET.Element], lang: str) -> int | None:
    labels = {label.lower() for label in _references_heading_labels(lang)}
    labels.update({"references", "参考文献"})
    for idx, child in enumerate(body_children):
        if child.tag != word_tag("p"):
            continue
        if element_text(child).strip().lower() in labels:
            return idx
    return None


def iter_paragraphs_in_docx_block(element: ET.Element) -> list[ET.Element]:
    return [node for node in element.iter(word_tag("p"))]


def ensure_reference_number_bookmark(paragraph: ET.Element, ref_number: int, bookmark_id: int) -> bool:
    if paragraph_has_word_field(paragraph):
        return False
    match = _DOCX_NUMERIC_REFERENCE_RE.match(element_text(paragraph))
    if not match:
        return False
    if int(match.group("bracketed") or match.group("plain")) != ref_number:
        return False
    if not paragraph_runs_have_simple_text(paragraph):
        return False

    text = element_text(paragraph)
    match = _DOCX_NUMERIC_REFERENCE_RE.match(text)
    if not match:
        return False
    number_start = match.start("bracketed") if match.group("bracketed") else match.start("plain")
    number_end = match.end("bracketed") if match.group("bracketed") else match.end("plain")

    template_run = next((run for run in paragraph.findall(word_tag("r")) if run.find(word_tag("rPr")) is not None), None)
    p_pr = paragraph.find(word_tag("pPr"))
    p_pr_copy = deepcopy(p_pr) if p_pr is not None else None
    paragraph.clear()
    if p_pr_copy is not None:
        paragraph.append(p_pr_copy)

    remove_existing_bookmark(paragraph, f"_Ref{ref_number}")
    if text[:number_start]:
        paragraph.append(make_text_run(text[:number_start], template_run))
    paragraph.append(make_docx_bookmark_start(bookmark_id, f"_Ref{ref_number}"))
    paragraph.append(make_text_run(text[number_start:number_end], template_run))
    paragraph.append(make_docx_bookmark_end(bookmark_id))
    if text[number_end:]:
        paragraph.append(make_text_run(text[number_end:], template_run))
    return True


def _numeric_citation_parts(citation_text: str) -> list[tuple[str, int | str]]:
    parts: list[tuple[str, int | str]] = []
    pos = 0
    for match in _DOCX_NUMERIC_CITATION_TOKEN_RE.finditer(citation_text):
        if match.start() > pos:
            return []
        token = match.group(0)
        if token.isdigit():
            parts.append(("ref", int(token)))
        else:
            parts.append(("text", token))
        pos = match.end()
    if pos != len(citation_text):
        return []
    return parts


def replace_numeric_citations_in_paragraph(
    paragraph: ET.Element,
    available_refs: set[int],
    *,
    superscript: bool = False,
) -> bool:
    if paragraph_has_word_field(paragraph) or not paragraph_runs_have_simple_text(paragraph):
        return False
    text = element_text(paragraph)
    if not text:
        return False

    matches: list[tuple[int, int, list[tuple[str, int | str]]]] = []
    for match in _DOCX_NUMERIC_CITATION_RE.finditer(text):
        parts = _numeric_citation_parts(match.group("body"))
        ref_numbers = [value for kind, value in parts if kind == "ref"]
        if not ref_numbers or any(int(number) not in available_refs for number in ref_numbers):
            continue
        matches.append((match.start(), match.end(), parts))
    if not matches:
        return False

    template_run = next((run for run in paragraph.findall(word_tag("r")) if run.find(word_tag("rPr")) is not None), None)
    p_pr = paragraph.find(word_tag("pPr"))
    p_pr_copy = deepcopy(p_pr) if p_pr is not None else None
    paragraph.clear()
    if p_pr_copy is not None:
        paragraph.append(p_pr_copy)

    cursor = 0
    for start, end, parts in matches:
        if start > cursor:
            paragraph.append(make_text_run(text[cursor:start], template_run))
        paragraph.append(make_text_run("[", template_run, superscript=superscript))
        for kind, value in parts:
            if kind == "ref":
                paragraph.extend(
                    make_docx_ref_field_runs(
                        f"REF _Ref{int(value)} \\h",
                        str(value),
                        template_run,
                        superscript=superscript,
                    )
                )
            else:
                paragraph.append(make_text_run(str(value), template_run, superscript=superscript))
        paragraph.append(make_text_run("]", template_run, superscript=superscript))
        cursor = end
    if cursor < len(text):
        paragraph.append(make_text_run(text[cursor:], template_run))
    return True


def _docx_float_caption_match(text: str) -> tuple[str, int] | None:
    match = re.match(r"^\s*(图|表|Figure|Table)\s+(\d+)\s*[.．]", text, flags=re.I)
    if not match:
        return None
    kind = match.group(1).lower()
    prefix = "Fig" if kind in {"图", "figure"} else "Tab"
    return prefix, int(match.group(2))


def _next_bookmark_id(root: ET.Element) -> int:
    ids: list[int] = []
    for node in root.iter(word_tag("bookmarkStart")):
        raw = node.attrib.get(word_tag("id"))
        if raw and raw.isdigit():
            ids.append(int(raw))
    return (max(ids) + 1) if ids else 1


def ensure_float_caption_bookmark(paragraph: ET.Element, prefix: str, number: int, bookmark_id: int) -> bool:
    bookmark_name = f"_{prefix}{number}"
    if any(node.attrib.get(word_tag("name")) == bookmark_name for node in paragraph.iter(word_tag("bookmarkStart"))):
        return False
    insert_at = 1 if paragraph.find(word_tag("pPr")) is not None else 0
    paragraph.insert(insert_at, make_docx_bookmark_start(bookmark_id, bookmark_name))
    paragraph.append(make_docx_bookmark_end(bookmark_id))
    return True


def replace_float_refs_in_paragraph(paragraph: ET.Element, available: set[tuple[str, int]]) -> bool:
    if is_docx_float_caption_paragraph(paragraph):
        return False

    pattern = re.compile(r"(?<![\w])(?P<label>图|表|Figure|Table)\s+(?P<number>\d+)(?![.．\d])", re.I)
    changed = False

    def is_plain_text_run(node: ET.Element) -> bool:
        if node.tag != word_tag("r") or is_word_field_run(node):
            return False
        non_property_children = [child for child in list(node) if child.tag != word_tag("rPr")]
        return len(non_property_children) == 1 and non_property_children[0].tag == word_tag("t")

    def run_text(node: ET.Element) -> str:
        text_node = next((child for child in list(node) if child.tag == word_tag("t")), None)
        return text_node.text if text_node is not None and text_node.text is not None else ""

    def replacement_runs(text: str, template_run: ET.Element) -> list[ET.Element] | None:
        matches: list[tuple[int, int, str, str, int]] = []
        for match in pattern.finditer(text):
            label = match.group("label")
            kind = label.lower()
            prefix = "Fig" if kind in {"图", "figure"} else "Tab"
            number = int(match.group("number"))
            if (prefix, number) not in available:
                continue
            display = f"{label} {number}"
            matches.append((match.start(), match.end(), prefix, display, number))
        if not matches:
            return None
        cursor = 0
        new_runs: list[ET.Element] = []
        for start, end, prefix, display, number in matches:
            if start > cursor:
                new_runs.append(make_text_run(text[cursor:start], template_run))
            new_runs.append(make_docx_field_run(f"REF _{prefix}{number} \\h", display, template_run))
            cursor = end
        if cursor < len(text):
            new_runs.append(make_text_run(text[cursor:], template_run))
        return new_runs

    original_children = list(paragraph)
    rebuilt_children: list[ET.Element] = []
    group: list[ET.Element] = []

    def flush_group() -> None:
        nonlocal changed, group
        if not group:
            return
        text = "".join(run_text(run) for run in group)
        new_runs = replacement_runs(text, group[0])
        if new_runs is None:
            rebuilt_children.extend(group)
        else:
            rebuilt_children.extend(new_runs)
            changed = True
        group = []

    for child in original_children:
        if is_plain_text_run(child):
            group.append(child)
            continue
        flush_group()
        rebuilt_children.append(child)
    flush_group()

    if changed:
        paragraph[:] = rebuilt_children
    return changed


def add_docx_float_crossrefs(docx_path: Path, lang: str) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"

    changed = False
    available: set[tuple[str, int]] = set()
    next_id = _next_bookmark_id(root)
    body_children = list(body)
    for paragraph in body_children:
        if paragraph.tag != word_tag("p"):
            continue
        parsed = _docx_float_caption_match(element_text(paragraph).strip())
        if parsed is None:
            continue
        prefix, number = parsed
        available.add((prefix, number))
        if ensure_float_caption_bookmark(paragraph, prefix, number, next_id):
            next_id += 1
            changed = True

    if not available:
        return None

    for paragraph in body_children:
        if paragraph.tag != word_tag("p"):
            continue
        if replace_float_refs_in_paragraph(paragraph, available):
            changed = True

    if changed:
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def add_docx_numeric_reference_crossrefs(
    docx_path: Path,
    lang: str,
    *,
    superscript_citations: bool = False,
) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"
    body_children = list(body)
    refs_start = references_heading_index(body_children, lang)
    if refs_start is None:
        return None

    available_refs: set[int] = set()
    next_ref_number = 1
    next_bookmark_id = _next_bookmark_id(root)
    for child in body_children[refs_start + 1:]:
        if child.tag != word_tag("p"):
            continue
        text = element_text(child).strip()
        if not text:
            continue
        match = _DOCX_NUMERIC_REFERENCE_RE.match(text)
        if not match:
            continue
        ref_number = int(match.group("bracketed") or match.group("plain") or next_ref_number)
        if ensure_reference_number_bookmark(child, ref_number, next_bookmark_id):
            available_refs.add(ref_number)
            next_bookmark_id += 1
            next_ref_number = max(next_ref_number, ref_number + 1)

    if not available_refs:
        return None

    changed = bool(available_refs)
    for child in body_children[:refs_start]:
        for paragraph in iter_paragraphs_in_docx_block(child):
            if replace_numeric_citations_in_paragraph(
                paragraph,
                available_refs,
                superscript=superscript_citations,
            ):
                changed = True

    if changed:
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def is_docx_toc(element: ET.Element) -> bool:
    if element.tag != word_tag("sdt"):
        return False
    for gallery in element.iter(word_tag("docPartGallery")):
        if gallery.attrib.get(word_tag("val")) == "Table of Contents":
            return True
    for instr_text in element.iter(word_tag("instrText")):
        if element_text(instr_text).strip().startswith("TOC "):
            return True
    return False


def remove_toc_outline_level_switches(element: ET.Element) -> None:
    """Keep Word TOCs limited to heading styles, not arbitrary outline levels."""
    for instr_text in element.iter(word_tag("instrText")):
        text = instr_text.text or ""
        if text.strip().startswith("TOC "):
            instr_text.text = re.sub(r'(?<!\\)\\u\b\s*', "", text)


def strip_paragraph_outline_level(paragraph: ET.Element) -> None:
    paragraph_properties = paragraph.find(word_tag("pPr"))
    if paragraph_properties is None:
        return
    outline_level = paragraph_properties.find(word_tag("outlineLvl"))
    if outline_level is not None:
        paragraph_properties.remove(outline_level)


def is_docx_float_caption_paragraph(paragraph: ET.Element) -> bool:
    return _TABLE_CAPTION_LINE_RE.match(element_text(paragraph).strip()) is not None


def remove_caption_paragraphs_from_element(element: ET.Element) -> None:
    for child in list(element):
        if child.tag == word_tag("p") and is_docx_float_caption_paragraph(child):
            element.remove(child)
        else:
            remove_caption_paragraphs_from_element(child)


def remove_caption_entries_from_toc(toc: ET.Element) -> None:
    remove_caption_paragraphs_from_element(toc)


def is_caption_style(style: ET.Element) -> bool:
    style_id = style.attrib.get(word_tag("styleId"), "")
    name = style.find(word_tag("name"))
    style_name = name.attrib.get(word_tag("val"), "") if name is not None else ""
    normalized = f"{style_id} {style_name}".lower()
    return "caption" in normalized or "题注" in normalized


def strip_style_outline_level(style: ET.Element) -> bool:
    style_properties = style.find(word_tag("pPr"))
    if style_properties is None:
        return False
    outline_level = style_properties.find(word_tag("outlineLvl"))
    if outline_level is None:
        return False
    style_properties.remove(outline_level)
    return True


def prevent_docx_caption_styles_in_toc(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            try:
                styles_xml = archive.read("word/styles.xml")
            except KeyError:
                return None
    except zipfile.BadZipFile as exc:
        return f"docx_styles_read_failed: {exc}"

    try:
        root = ET.fromstring(styles_xml)
    except ET.ParseError as exc:
        return f"docx_styles_parse_failed: {exc}"

    changed = False
    for style in root.iter(word_tag("style")):
        if is_caption_style(style) and strip_style_outline_level(style):
            changed = True

    if changed:
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_member(docx_path, "word/styles.xml", updated_xml)
    return None


def mark_docx_field_runs_dirty(element: ET.Element) -> bool:
    """Mark dynamic Word fields for recalculation on open."""
    changed = False
    open_fields: list[ET.Element] = []
    for run in element.iter(word_tag("r")):
        for child in list(run):
            if child.tag == word_tag("fldChar"):
                field_type = child.attrib.get(word_tag("fldCharType"))
                if field_type == "begin":
                    open_fields.append(child)
                elif field_type == "end" and open_fields:
                    open_fields.pop()
            elif child.tag == word_tag("instrText"):
                instr_text = (child.text or "").strip()
                if not re.match(r"^(TOC|PAGEREF|REF)\b", instr_text) or not open_fields:
                    continue
                field_char = open_fields[-1]
                if field_char.attrib.get(word_tag("dirty")) != "true":
                    field_char.set(word_tag("dirty"), "true")
                    changed = True
    return changed


def mark_docx_fields_dirty(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    if mark_docx_field_runs_dirty(root):
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def is_keywords_paragraph(element: ET.Element, lang: str) -> bool:
    if element.tag != word_tag("p"):
        return False
    text = element_text(element).strip()
    return text.startswith("关键词") if lang == "zh" else text.lower().startswith("keywords")


def page_break_paragraph() -> ET.Element:
    paragraph = ET.Element(word_tag("p"))
    run = ET.SubElement(paragraph, word_tag("r"))
    ET.SubElement(run, word_tag("br"), {word_tag("type"): "page"})
    return paragraph


def get_or_create_child(parent: ET.Element, tag_name: str) -> ET.Element:
    child = parent.find(word_tag(tag_name))
    if child is None:
        child = ET.Element(word_tag(tag_name))
        parent.insert(0, child)
    return child


def _set_cell_border(tc: ET.Element, side: str, attrs: dict[str, str]) -> None:
    tc_pr = get_or_create_child(tc, "tcPr")
    tc_borders = get_or_create_child(tc_pr, "tcBorders")
    border = tc_borders.find(word_tag(side))
    if border is None:
        border = ET.Element(word_tag(side))
        tc_borders.append(border)
    border.attrib.clear()
    for key, value in attrs.items():
        border.set(word_tag(key), value)


def is_economics_empirical_survey(survey_dir: Path) -> bool:
    constraints_path = survey_dir / "writing_constraints.json"
    if not constraints_path.exists():
        return False
    try:
        data = json.loads(constraints_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    subject = str(data.get("subject", "")).lower()
    topic = str(data.get("topic", "") or data.get("core_topic", "")).lower()
    venue_style_notes = str(data.get("venue_style_notes", "")).lower()
    constraint_source = data.get("constraint_source")
    constraint_source_name = ""
    if isinstance(constraint_source, dict):
        constraint_source_name = str(constraint_source.get("name", "")).lower()
    if (
        constraint_source_name == "bundled economics empirical-style review template"
        or "economics empirical-style review" in venue_style_notes
    ):
        return True

    technical_subject_terms = (
        "computer science",
        "software engineering",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "large language model",
        "multimodal",
        "knowledge graph",
        "retrieval augmented generation",
        "rag",
        "engineering",
        "计算机",
        "软件工程",
        "人工智能",
        "机器学习",
        "深度学习",
        "大模型",
        "知识图谱",
        "检索增强生成",
        "工程",
    )
    if any(term in subject for term in technical_subject_terms):
        return False

    economics_subject_terms = (
        "economics",
        "finance",
        "management",
        "accounting",
        "industrial economics",
        "corporate finance",
        "public finance",
        "经济学",
        "金融学",
        "管理学",
        "会计学",
        "产业经济",
        "公司金融",
        "公共财政",
    )
    if any(term in subject for term in economics_subject_terms):
        return True

    economics_topic_terms = (
        "supply-chain finance",
        "supply chain finance",
        "sme financing",
        "trade credit",
        "financing constraints",
        "供应链金融",
        "中小企业融资",
        "商业信用",
        "融资约束",
    )
    return any(term in topic for term in economics_topic_terms)


def apply_docx_table_borders(docx_path: Path, *, economics_style: bool = False) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    for table in root.iter(word_tag("tbl")):
        # Table-level borders. Generic surveys use a strict three-line table;
        # economics empirical-style surveys keep the journal convention with
        # vertical separators and thin internal horizontal rules.
        table_properties = get_or_create_child(table, "tblPr")
        borders = get_or_create_child(table_properties, "tblBorders")
        thick_rule = {"val": "single", "sz": "12", "space": "0", "color": "000000"}
        thin_rule = {"val": "single", "sz": "4", "space": "0", "color": "000000"}
        if economics_style:
            tbl_border_specs = {
                "top": thick_rule,
                "bottom": thick_rule,
                "insideH": thin_rule,
                "insideV": thin_rule,
                "left": {"val": "nil"},
                "right": {"val": "nil"},
            }
        else:
            tbl_border_specs = {
                "top": thick_rule,
                "bottom": thick_rule,
                "insideH": {"val": "nil"},
                "insideV": {"val": "nil"},
                "left": {"val": "nil"},
                "right": {"val": "nil"},
            }
        for border_name, attrs in tbl_border_specs.items():
            border = borders.find(word_tag(border_name))
            if border is None:
                border = ET.Element(word_tag(border_name))
                borders.append(border)
            border.attrib.clear()
            for key, value in attrs.items():
                border.set(word_tag(key), value)

        # Header row: thin bottom border on each cell to produce \midrule
        rows = table.findall(word_tag("tr"))
        if rows:
            midrule_attrs = {"val": "single", "sz": "6", "space": "0", "color": "000000"}
            for tc in rows[0].findall(word_tag("tc")):
                _set_cell_border(tc, "bottom", midrule_attrs)

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def paragraph_contains_image(paragraph: ET.Element) -> bool:
    return any(node.tag in {word_tag("drawing"), word_tag("pict")} for node in paragraph.iter())


def center_docx_image_paragraphs(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    for paragraph in root.iter(word_tag("p")):
        if not paragraph_contains_image(paragraph):
            continue
        paragraph_properties = get_or_create_child(paragraph, "pPr")
        alignment = paragraph_properties.find(word_tag("jc"))
        if alignment is None:
            alignment = ET.Element(word_tag("jc"))
            paragraph_properties.append(alignment)
        alignment.set(word_tag("val"), "center")

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def set_paragraph_alignment(paragraph: ET.Element, alignment_value: str) -> None:
    paragraph_properties = get_or_create_child(paragraph, "pPr")
    alignment = paragraph_properties.find(word_tag("jc"))
    if alignment is None:
        alignment = ET.Element(word_tag("jc"))
        paragraph_properties.append(alignment)
    alignment.set(word_tag("val"), alignment_value)


def center_docx_caption_paragraphs(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    for paragraph in root.iter(word_tag("p")):
        if is_docx_float_caption_paragraph(paragraph):
            set_paragraph_alignment(paragraph, "center")

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def prevent_docx_captions_in_toc(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"

    for toc in [child for child in body if is_docx_toc(child)]:
        remove_toc_outline_level_switches(toc)
        remove_caption_entries_from_toc(toc)

    for paragraph in root.iter(word_tag("p")):
        if is_docx_float_caption_paragraph(paragraph):
            strip_paragraph_outline_level(paragraph)

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def center_docx_tables(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    for table in root.iter(word_tag("tbl")):
        table_properties = get_or_create_child(table, "tblPr")
        alignment = table_properties.find(word_tag("jc"))
        if alignment is None:
            alignment = ET.Element(word_tag("jc"))
            table_properties.append(alignment)
        alignment.set(word_tag("val"), "center")

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def suppress_first_line_indent(paragraph_properties: ET.Element) -> None:
    indent = paragraph_properties.find(word_tag("ind"))
    if indent is None:
        indent = ET.Element(word_tag("ind"))
        paragraph_properties.append(indent)
    indent.set(word_tag("firstLine"), "0")
    indent.attrib.pop(word_tag("firstLineChars"), None)


def set_paragraph_spacing_after(paragraph: ET.Element, after: str, line: str) -> None:
    paragraph_properties = get_or_create_child(paragraph, "pPr")
    spacing = paragraph_properties.find(word_tag("spacing"))
    if spacing is None:
        spacing = ET.Element(word_tag("spacing"))
        paragraph_properties.append(spacing)
    spacing.set(word_tag("before"), "0")
    spacing.set(word_tag("after"), after)
    spacing.set(word_tag("line"), line)
    spacing.set(word_tag("lineRule"), "auto")
    suppress_first_line_indent(paragraph_properties)


def rewrite_docx_document_xml(docx_path: Path, document_xml: bytes) -> None:
    temp_path = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(docx_path) as source, zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = document_xml if item.filename == "word/document.xml" else source.read(item.filename)
            target.writestr(item, data)
    shutil.move(str(temp_path), str(docx_path))


def rewrite_docx_member(docx_path: Path, member_name: str, member_data: bytes) -> None:
    temp_path = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(docx_path) as source, zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as target:
        wrote_member = False
        for item in source.infolist():
            data = member_data if item.filename == member_name else source.read(item.filename)
            target.writestr(item, data)
            wrote_member = wrote_member or item.filename == member_name
        if not wrote_member:
            target.writestr(member_name, member_data)
    shutil.move(str(temp_path), str(docx_path))


def docx_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def sort_docx_children(parent: ET.Element, order: dict[str, int]) -> bool:
    children = list(parent)
    indexed = list(enumerate(children))
    sorted_children = [
        child
        for _, child in sorted(
            indexed,
            key=lambda item: (order.get(docx_local_name(item[1].tag), len(order)), item[0]),
        )
    ]
    if sorted_children == children:
        return False
    parent[:] = sorted_children
    return True


def normalize_docx_paragraph_child_order(root: ET.Element) -> bool:
    changed = False
    for paragraph in root.iter(word_tag("p")):
        paragraph_properties = paragraph.find(word_tag("pPr"))
        if paragraph_properties is None:
            continue
        children = list(paragraph)
        if children and children[0] is paragraph_properties:
            continue
        paragraph.remove(paragraph_properties)
        paragraph.insert(0, paragraph_properties)
        changed = True
    return changed


def normalize_docx_table_child_order(root: ET.Element) -> bool:
    changed = False
    for table_properties in root.iter(word_tag("tblPr")):
        if sort_docx_children(table_properties, _DOCX_TBL_PR_CHILD_ORDER):
            changed = True
    for borders in root.iter(word_tag("tblBorders")):
        if sort_docx_children(borders, _DOCX_TBL_BORDERS_CHILD_ORDER):
            changed = True
    for borders in root.iter(word_tag("tcBorders")):
        if sort_docx_children(borders, _DOCX_TBL_BORDERS_CHILD_ORDER):
            changed = True
    return changed


_DOCX_RUN_PROPERTIES_CHILD_ORDER = {
    "rStyle": 0,
    "rFonts": 1,
    "b": 2,
    "bCs": 3,
    "i": 4,
    "iCs": 5,
    "caps": 6,
    "smallCaps": 7,
    "strike": 8,
    "dstrike": 9,
    "outline": 10,
    "shadow": 11,
    "emboss": 12,
    "imprint": 13,
    "noProof": 14,
    "snapToGrid": 15,
    "vanish": 16,
    "webHidden": 17,
    "color": 18,
    "spacing": 19,
    "w": 20,
    "kern": 21,
    "position": 22,
    "sz": 23,
    "szCs": 24,
    "highlight": 25,
    "u": 26,
    "effect": 27,
    "bdr": 28,
    "shd": 29,
    "fitText": 30,
    "vertAlign": 31,
    "rtl": 32,
    "cs": 33,
    "em": 34,
    "lang": 35,
    "eastAsianLayout": 36,
    "specVanish": 37,
    "oMath": 38,
}
_CONTENT_TYPES_OVERRIDE_RE = re.compile(
    rb'<(?:(?P<prefix>[A-Za-z_][\w.-]*):)?Override\b'
    rb'(?=[^>]*\bPartName=(?P<quote>["\'])(?P<part>[^"\']+)(?P=quote))'
    rb'[^>]*/\s*>'
)


def normalize_docx_run_properties(root: ET.Element) -> bool:
    return any(
        sort_docx_children(run_properties, _DOCX_RUN_PROPERTIES_CHILD_ORDER)
        for run_properties in root.iter(word_tag("rPr"))
    )


def normalize_docx_table_header_properties(root: ET.Element) -> bool:
    changed = False
    for table_header in root.iter(word_tag("tblHeader")):
        if table_header.attrib.pop(word_tag("val"), None) is not None:
            changed = True
    return changed


def normalize_docx_markup_compatibility(root: ET.Element, xml: bytes) -> bool:
    ignorable_attr = f"{{{_MC_NS}}}Ignorable"
    ignorable = root.attrib.get(ignorable_attr)
    if not ignorable:
        return False

    text = xml.decode("utf-8", errors="ignore")
    keep: list[str] = []
    for token in ignorable.split():
        if f"xmlns:{token}=" in text or f"<{token}:" in text or f"</{token}:" in text or f" {token}:" in text:
            keep.append(token)

    if keep == ignorable.split():
        return False
    if keep:
        root.set(ignorable_attr, " ".join(keep))
    else:
        root.attrib.pop(ignorable_attr, None)
    return True


def normalize_docx_package_integrity(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            infos = archive.infolist()
            had_directory_entry = any(item.is_dir() for item in infos)
            members = [(item, archive.read(item.filename)) for item in infos if not item.is_dir()]
    except zipfile.BadZipFile as exc:
        return f"docx_package_read_failed: {exc}"

    member_data = {item.filename: data for item, data in members}
    updated_members: dict[str, bytes] = {}
    content_types = member_data.get("[Content_Types].xml")
    if content_types is not None:
        try:
            content_types_root = ET.fromstring(content_types)
        except ET.ParseError as exc:
            return f"docx_content_types_parse_failed: {exc}"
        directory_parts = {
            override.attrib["PartName"]
            for override in content_types_root
            if docx_local_name(override.tag) == "Override" and override.attrib.get("PartName", "").endswith("/")
        }
        if directory_parts:
            sanitized = _CONTENT_TYPES_OVERRIDE_RE.sub(
                lambda match: b"" if match.group("part").decode("utf-8") in directory_parts else match.group(0),
                content_types,
            )
            if sanitized == content_types:
                return "docx_content_types_directory_override_remove_failed"
            updated_members["[Content_Types].xml"] = sanitized

    for member_name, transform in (
        ("word/document.xml", "document"),
        ("word/styles.xml", "styles"),
        ("word/numbering.xml", "numbering"),
    ):
        xml = member_data.get(member_name)
        if xml is None:
            continue
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            return f"docx_{transform}_parse_failed: {exc}"
        changed = normalize_docx_run_properties(root)
        if transform == "document":
            changed = normalize_docx_table_header_properties(root) or changed
        elif transform == "numbering":
            changed = normalize_docx_markup_compatibility(root, xml) or changed
            for nsid in root.iter(word_tag("nsid")):
                value = nsid.attrib.get(word_tag("val"), "")
                if re.fullmatch(r"[0-9A-Fa-f]{1,7}", value):
                    nsid.set(word_tag("val"), value.upper().zfill(8))
                    changed = True
        if changed:
            updated_members[member_name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    if not updated_members and not had_directory_entry:
        return None

    temp_path = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as target:
        for item, data in members:
            target.writestr(item, updated_members.get(item.filename, data))
    shutil.move(str(temp_path), str(docx_path))
    return None


def normalize_docx_xml_order(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    changed = normalize_docx_paragraph_child_order(root)
    changed = normalize_docx_table_child_order(root) or changed
    if changed:
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def normalize_docx_styles_xml(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            try:
                styles_xml = archive.read("word/styles.xml")
            except KeyError:
                return None
    except zipfile.BadZipFile as exc:
        return f"docx_styles_read_failed: {exc}"

    try:
        root = ET.fromstring(styles_xml)
    except ET.ParseError as exc:
        return f"docx_styles_parse_failed: {exc}"

    changed = False
    ignorable = root.attrib.get(_MC_IGNORABLE)
    if ignorable:
        declared_prefixes = set(re.findall(rb"\sxmlns:([A-Za-z_][\w.-]*)=", styles_xml[:4096].decode("utf-8", errors="ignore").encode("utf-8")))
        declared_prefixes_text = {
            prefix.decode("utf-8", errors="ignore")
            for prefix in declared_prefixes
        }
        kept = [prefix for prefix in ignorable.split() if prefix in declared_prefixes_text]
        if kept:
            new_value = " ".join(kept)
            if new_value != ignorable:
                root.set(_MC_IGNORABLE, new_value)
                changed = True
        else:
            root.attrib.pop(_MC_IGNORABLE, None)
            changed = True

    for style in root.iter(word_tag("style")):
        style_id = style.attrib.get(word_tag("styleId"), "")
        target_size = _DOCX_STYLE_SIZE_OVERRIDES.get(style_id)
        if target_size:
            run_properties = get_or_create_child(style, "rPr")
            size = run_properties.find(word_tag("sz"))
            if size is None:
                size = ET.Element(word_tag("sz"))
                run_properties.append(size)
            size_cs = run_properties.find(word_tag("szCs"))
            if size_cs is None:
                size_cs = ET.Element(word_tag("szCs"))
                run_properties.append(size_cs)
            if size.attrib.get(word_tag("val")) != target_size:
                size.set(word_tag("val"), target_size)
                changed = True
            if size_cs.attrib.get(word_tag("val")) != target_size:
                size_cs.set(word_tag("val"), target_size)
                changed = True
        if sort_docx_children(style, _DOCX_STYLE_CHILD_ORDER):
            changed = True

    if changed:
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_member(docx_path, "word/styles.xml", updated_xml)
    return None


def normalize_docx_settings_xml(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            try:
                settings_xml = archive.read("word/settings.xml")
            except KeyError:
                return None
    except zipfile.BadZipFile as exc:
        return f"docx_settings_read_failed: {exc}"

    try:
        root = ET.fromstring(settings_xml)
    except ET.ParseError as exc:
        return f"docx_settings_parse_failed: {exc}"

    if sort_docx_children(root, _DOCX_SETTINGS_CHILD_ORDER):
        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        rewrite_docx_member(docx_path, "word/settings.xml", updated_xml)
    return None


def insert_docx_settings_update_fields(root: ET.Element, template: ET.Element | None = None) -> ET.Element:
    update_fields = ET.Element(word_tag("updateFields"))
    if template is not None:
        update_fields.attrib.update(template.attrib)
    for index, child in enumerate(list(root)):
        if docx_local_name(child.tag) in _DOCX_SETTINGS_UPDATE_FIELDS_FOLLOWING_TAGS:
            root.insert(index, update_fields)
            return update_fields
    root.append(update_fields)
    return update_fields


def fix_docx_special_paragraphs(docx_path: Path, lang: str) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"

    abstract_prefix = "摘要：" if lang == "zh" else "abstract:"
    keywords_prefix = "关键词：" if lang == "zh" else "keywords:"
    line_spacing = "360" if lang == "zh" else "480"
    scanned = 0
    for child in list(body):
        if child.tag != word_tag("p"):
            continue
        scanned += 1
        text = element_text(child).strip()
        comparable_text = text if lang == "zh" else text.lower()
        if comparable_text.startswith(abstract_prefix):
            set_paragraph_spacing_after(child, "120", line_spacing)
        elif comparable_text.startswith(keywords_prefix):
            paragraph_properties = get_or_create_child(child, "pPr")
            suppress_first_line_indent(paragraph_properties)
            break
        if scanned >= 15:
            break

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def enable_docx_update_fields_on_open(docx_path: Path) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            try:
                settings_xml = archive.read("word/settings.xml")
            except KeyError:
                settings_xml = f'<w:settings xmlns:w="{_WORD_NS}" />'.encode("utf-8")
    except zipfile.BadZipFile as exc:
        return f"docx_settings_read_failed: {exc}"

    try:
        root = ET.fromstring(settings_xml)
    except ET.ParseError as exc:
        return f"docx_settings_parse_failed: {exc}"

    existing_update_fields = [child for child in list(root) if child.tag == word_tag("updateFields")]
    template_update_fields = existing_update_fields[0] if existing_update_fields else None
    for update_field in existing_update_fields:
        root.remove(update_field)
    update_fields = insert_docx_settings_update_fields(root, template_update_fields)
    update_fields.set(word_tag("val"), "true")

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_member(docx_path, "word/settings.xml", updated_xml)
    return None


def reposition_docx_toc_after_keywords(docx_path: Path, lang: str) -> str | None:
    try:
        with zipfile.ZipFile(docx_path) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"docx_document_xml_read_failed: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return f"docx_document_xml_parse_failed: {exc}"

    body = root.find(word_tag("body"))
    if body is None:
        return "docx_body_missing"

    toc = next((child for child in list(body) if is_docx_toc(child)), None)
    if toc is None:
        return "docx_toc_missing"
    remove_toc_outline_level_switches(toc)
    remove_caption_entries_from_toc(toc)

    body.remove(toc)
    children = list(body)
    keywords_index = next((idx for idx, child in enumerate(children) if is_keywords_paragraph(child, lang)), None)
    if keywords_index is None:
        return "docx_keywords_paragraph_missing"

    insert_at = keywords_index + 1
    body.insert(insert_at, page_break_paragraph())
    body.insert(insert_at + 1, toc)
    body.insert(insert_at + 2, page_break_paragraph())

    updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rewrite_docx_document_xml(docx_path, updated_xml)
    return None


def export_docx(
    survey_dir: Path,
    title: str,
    stem: str,
    lang: str,
    bib: Path | None,
    csl: Path | None,
    reference_doc: Path,
) -> ExportResult:
    if shutil.which("pandoc") is None:
        return ExportResult("docx", "ERROR", message="dependency_not_found: pandoc")

    build_dir = survey_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    input_tex, fig_warnings = assemble_docx_input(survey_dir, stem, lang)
    if input_tex is None:
        return ExportResult("docx", "ERROR", message="; ".join(fig_warnings))
    warnings: list[str] = list(fig_warnings)
    meta = write_docx_meta(build_dir, title, lang)
    output = survey_dir / f"{stem}.docx"

    cmd = [
        "pandoc",
        str(input_tex.resolve()),
        "--from",
        "latex",
        "--to",
        "docx",
        "--toc",
        "--metadata-file",
        str(meta.resolve()),
        "--reference-doc",
        str(reference_doc.resolve()),
        "-o",
        str(output.resolve()),
    ]
    if bib:
        cmd.extend(["--bibliography", str(bib.resolve()), "--citeproc"])
        if csl:
            cmd.extend(["--csl", str(csl.resolve())])

    result = run_command(cmd, cwd=survey_dir, timeout=180)
    if result.returncode != 0:
        return ExportResult("docx", "ERROR", message=result.stderr.strip() or f"pandoc_exit_{result.returncode}")

    gbt_fix_error = fix_gbt_bilingual_in_docx(output, bib, csl, lang)
    if gbt_fix_error:
        return ExportResult("docx", "ERROR", output, gbt_fix_error)

    toc_error = reposition_docx_toc_after_keywords(output, lang)
    if toc_error:
        return ExportResult("docx", "ERROR", output, toc_error)
    caption_toc_error = prevent_docx_captions_in_toc(output)
    if caption_toc_error:
        return ExportResult("docx", "ERROR", output, caption_toc_error)
    caption_style_error = prevent_docx_caption_styles_in_toc(output)
    if caption_style_error:
        return ExportResult("docx", "ERROR", output, caption_style_error)
    special_paragraph_error = fix_docx_special_paragraphs(output, lang)
    if special_paragraph_error:
        return ExportResult("docx", "ERROR", output, special_paragraph_error)
    reference_crossref_error = add_docx_numeric_reference_crossrefs(
        output,
        lang,
        superscript_citations=is_gbt_csl(csl),
    )
    if reference_crossref_error:
        return ExportResult("docx", "ERROR", output, reference_crossref_error)
    float_crossref_error = add_docx_float_crossrefs(output, lang)
    if float_crossref_error:
        return ExportResult("docx", "ERROR", output, float_crossref_error)
    update_fields_error = enable_docx_update_fields_on_open(output)
    if update_fields_error:
        return ExportResult("docx", "ERROR", output, update_fields_error)
    settings_xml_error = normalize_docx_settings_xml(output)
    if settings_xml_error:
        return ExportResult("docx", "ERROR", output, settings_xml_error)
    table_border_error = apply_docx_table_borders(
        output,
        economics_style=is_economics_empirical_survey(survey_dir),
    )
    if table_border_error:
        return ExportResult("docx", "ERROR", output, table_border_error)
    image_center_error = center_docx_image_paragraphs(output)
    if image_center_error:
        return ExportResult("docx", "ERROR", output, image_center_error)
    caption_center_error = center_docx_caption_paragraphs(output)
    if caption_center_error:
        return ExportResult("docx", "ERROR", output, caption_center_error)
    table_center_error = center_docx_tables(output)
    if table_center_error:
        return ExportResult("docx", "ERROR", output, table_center_error)
    dirty_fields_error = mark_docx_fields_dirty(output)
    if dirty_fields_error:
        return ExportResult("docx", "ERROR", output, dirty_fields_error)
    xml_order_error = normalize_docx_xml_order(output)
    if xml_order_error:
        return ExportResult("docx", "ERROR", output, xml_order_error)
    styles_xml_error = normalize_docx_styles_xml(output)
    if styles_xml_error:
        return ExportResult("docx", "ERROR", output, styles_xml_error)
    package_integrity_error = normalize_docx_package_integrity(output)
    if package_integrity_error:
        return ExportResult("docx", "ERROR", output, package_integrity_error)

    issues = check_docx(output)
    if issues_are_only_docx_openxml_conformance(issues):
        for retry_normalize in (
            normalize_docx_xml_order,
            normalize_docx_styles_xml,
            normalize_docx_settings_xml,
            normalize_docx_package_integrity,
        ):
            retry_error = retry_normalize(output)
            if retry_error:
                return ExportResult("docx", "ERROR", output, retry_error)
        issues = check_docx(output)
    if issues:
        return ExportResult("docx", "ERROR", output, ";".join(issues))
    try:
        input_tex.unlink()
    except OSError:
        pass
    return ExportResult("docx", "OK", output, warnings=warnings)


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


_BIB_URL_FIELD_RE = re.compile(r"(?i)\burl\s*=\s*\{([^}]*)\}")
_BIB_DOI_FIELD_RE = re.compile(r"(?i)\bdoi\s*=\s*\{([^}]*)\}")


def _normalize_doi_value(value: str) -> str:
    value = value.strip()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I).lower()


def _url_duplicates_doi(url: str, doi: str) -> bool:
    return bool(
        doi
        and re.match(r"^https?://(dx\.)?doi\.org/", url.strip(), flags=re.I)
        and _normalize_doi_value(url) == _normalize_doi_value(doi)
    )


def normalize_bib_urls(bib_path: Path) -> list[str]:
    """Rewrite url fields in-place so they are safe inside LaTeX ``\\url{}``.

    Strategy per entry (applied in order, stops at first success):
    1. If a ``doi`` field is present and ``url`` is the same DOI resolver URL,
       remove the duplicate URL field.
    2. If url is truncated (bare query param at end) but doi is absent → remove url field.

    Returns a list of warning strings for genuinely problematic cases only
    (truncated URL drops).  Silent DOI rewrites are batched into one INFO line
    so they do not flood EXPORT_WARNING output.
    """
    if not bib_path.exists():
        return []
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    warnings: list[str] = []
    duplicate_doi_url_count = 0
    entry_spans: list[tuple[int, int]] = []
    matches = list(_BIB_ENTRY_RE.finditer(text))
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        entry_spans.append((m.start(), end))

    # Build new text by processing entries from last to first to keep offsets valid.
    changed = False
    for entry_start, entry_end in reversed(entry_spans):
        entry_text = text[entry_start:entry_end]
        key_match = _BIB_ENTRY_RE.match(entry_text)
        key = key_match.group(1).strip() if key_match else "?"

        doi_match = _BIB_DOI_FIELD_RE.search(entry_text)
        doi_value = doi_match.group(1).strip() if doi_match else ""

        url_match = _BIB_URL_FIELD_RE.search(entry_text)
        if url_match is None:
            continue
        url_value = url_match.group(1).strip()

        if doi_value and _url_duplicates_doi(url_value, doi_value):
            field_re = re.compile(
                r"[ \t]*\burl\s*=\s*\{[^}]*\}[ \t]*,?[ \t]*\n?", re.IGNORECASE
            )
            new_entry = field_re.sub("", entry_text, count=1)
            duplicate_doi_url_count += 1
        elif _TRUNCATED_BIB_URL_RE.search(url_value):
            # Remove the entire url = {...} field (including trailing comma/newline).
            field_re = re.compile(
                r"[ \t]*\burl\s*=\s*\{[^}]*\}[ \t]*,?[ \t]*\n?", re.IGNORECASE
            )
            new_entry = field_re.sub("", entry_text, count=1)
            warnings.append(f"bib_url_removed_truncated: {key}")
        else:
            continue

        changed = True
        text = text[:entry_start] + new_entry + text[entry_end:]

    if changed:
        bib_path.write_text(text, encoding="utf-8")
    if duplicate_doi_url_count:
        warnings.append(f"bib_url_removed_duplicate_doi: {duplicate_doi_url_count} entries")
    return warnings


def check_bib_urls(bib_path: Path) -> list[str]:
    """Return error strings for bib entries whose url field is still truncated.

    Call after ``normalize_bib_urls`` has already attempted repairs.
    """
    if not bib_path.exists():
        return []
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    for entry_match in _BIB_ENTRY_RE.finditer(text):
        key = entry_match.group(1).strip()
        next_entry = _BIB_ENTRY_RE.search(text, entry_match.end())
        entry_text = text[entry_match.start(): next_entry.start() if next_entry else len(text)]
        for url_match in _BIB_URL_FIELD_RE.finditer(entry_text):
            url_value = url_match.group(1).strip()
            if _TRUNCATED_BIB_URL_RE.search(url_value):
                errors.append(
                    f"bib_url_truncated: {key} — URL appears truncated: {url_value[:80]}"
                )
    return errors


def check_unreferenced_floats(tex_body: str) -> str | None:
    """Return an error string if any figure or table label has no \\autoref{} in the body.

    Also detects label/xref mismatches caused by case differences (e.g. \\label{fig:Foo}
    referenced as \\autoref{fig:foo}) which LaTeX silently renders as '??'.
    Case-mismatch errors take priority: a label with a case-insensitive match is reported
    as LABEL_XREF_CASE_MISMATCH, not UNREFERENCED_FLOATS.
    """
    fig_label_re = re.compile(r"\\label\{(fig:[^{}]+)\}")
    fig_ref_re = re.compile(r"\\(?:auto)?ref\{(fig:[^{}]+)\}")
    tab_label_re = re.compile(r"\\label\{(tab:[^{}]+)\}")
    tab_ref_re = re.compile(r"\\(?:auto)?ref\{(tab:[^{}]+)\}")
    fig_labels = set(fig_label_re.findall(tex_body))
    fig_refs = set(fig_ref_re.findall(tex_body))
    tab_labels = set(tab_label_re.findall(tex_body))
    tab_refs = set(tab_ref_re.findall(tex_body))

    # Build case-insensitive lookup: lowercase → canonical label
    fig_labels_lower = {lbl.lower(): lbl for lbl in fig_labels}
    tab_labels_lower = {lbl.lower(): lbl for lbl in tab_labels}

    # Detect case-mismatched xref→label pairs first (these would render as '??').
    mismatched = []
    for ref in fig_refs:
        if ref not in fig_labels and ref.lower() in fig_labels_lower:
            mismatched.append(f"\\autoref{{{ref}}} → label is {{{fig_labels_lower[ref.lower()]}}}")
    for ref in tab_refs:
        if ref not in tab_labels and ref.lower() in tab_labels_lower:
            mismatched.append(f"\\autoref{{{ref}}} → label is {{{tab_labels_lower[ref.lower()]}}}")
    if mismatched:
        return (
            "LABEL_XREF_CASE_MISMATCH: the following \\autoref{} keys do not match their "
            f"\\label{{}} exactly (LaTeX would render '??') — fix the case: {mismatched}"
        )

    # Labels with no ref at all (not even case-insensitive) are truly unreferenced.
    fig_refs_lower = {r.lower() for r in fig_refs}
    tab_refs_lower = {r.lower() for r in tab_refs}
    missing = (
        [lbl for lbl in fig_labels if lbl.lower() not in fig_refs_lower]
        + [lbl for lbl in tab_labels if lbl.lower() not in tab_refs_lower]
    )
    if missing:
        return (
            "UNREFERENCED_FLOATS: the following figure/table labels have no "
            f"\\autoref{{}} in the body — add references before exporting: {missing}"
        )

    return None


def check_table_has_tabular(tex_body: str) -> str | None:
    """Return an error string if any \\begin{table} environment contains no tabular/tabularx."""
    table_env_re = re.compile(r"\\begin\{table\}(.*?)\\end\{table\}", re.DOTALL)
    tabular_re = re.compile(r"\\begin\{tabular")
    label_re = re.compile(r"\\label\{(tab:[^{}]+)\}")
    empty_tables = []
    for m in table_env_re.finditer(tex_body):
        body = m.group(1)
        if not tabular_re.search(body):
            label_m = label_re.search(body)
            label = label_m.group(1) if label_m else "<unknown>"
            empty_tables.append(label)
    if empty_tables:
        return (
            "TABLE_MISSING_TABULAR: the following \\begin{table} environments have no "
            f"\\begin{{tabular}} — add table content before exporting: {empty_tables}"
        )
    return None


def check_abstract_float_refs(tex_body: str) -> str | None:
    """Return an error string if \\autoref/\\ref to fig:/tab: appears inside the abstract."""
    abs_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_body, re.S)
    if abs_m and re.search(r"\\(?:auto)?ref\{(?:fig|tab):", abs_m.group(1)):
        return (
            "ABSTRACT_FLOAT_REF: \\autoref{} or \\ref{} to a figure/table found inside "
            "\\begin{abstract} — remove float references from the abstract"
        )
    return None


def check_abstract_environment(tex_body: str) -> str | None:
    """Return an export-blocking error when the abstract environment is missing or unbalanced."""
    begin_count = len(re.findall(r"\\begin\{abstract\}", tex_body))
    end_count = len(re.findall(r"\\end\{abstract\}", tex_body))
    if begin_count == 0:
        return (
            "MISSING_ABSTRACT: mainbody.tex must contain "
            "\\begin{abstract}...\\end{abstract}; rerun survey_checks.py "
            "repair-structure before export"
        )
    if begin_count != 1 or end_count != 1:
        return (
            "ABSTRACT_ENV_MISMATCH: mainbody.tex has "
            f"\\begin{{abstract}} x{begin_count} vs \\end{{abstract}} x{end_count}; "
            "rerun survey_checks.py repair-structure before export"
        )
    abs_m = _ABSTRACT_RE.search(tex_body)
    if not abs_m:
        return (
            "ABSTRACT_NOT_CLOSED: mainbody.tex has a malformed abstract environment; "
            "rerun survey_checks.py repair-structure before export"
        )
    if not abs_m.group(1).strip():
        return "EMPTY_ABSTRACT: mainbody.tex abstract environment is empty"
    first_sec = tex_body.find(r"\section{")
    if first_sec != -1 and tex_body.find(r"\end{abstract}") > first_sec:
        return (
            "ABSTRACT_NOT_CLOSED: \\end{abstract} appears after the first \\section{}; "
            "close the abstract before body sections"
        )
    return None


def reposition_figures_after_first_ref(tex_body: str) -> str:
    r"""Move figure blocks to be adjacent to the paragraph containing their first \autoref{}.

    A "figure block" is the % FIGURE comment line plus the immediately following
    \begin{figure}...\end{figure} environment.

    "Correct position" means the block is immediately adjacent (only whitespace
    between) to the reference paragraph — either directly before it or directly
    after it.  Blocks already in the correct position are left untouched.

    References are matched by the actual \label{fig:...} inside each figure
    block. If a block has no figure label, fall back to the historical
    convention that "% FIGURE id=<id>" is referenced as "fig:<id>".

    Multiple figures referenced in the same paragraph are grouped and inserted
    together in their original document order immediately after that paragraph,
    preserving relative ordering.
    """
    figure_blocks: list[tuple[str, str]] = []
    seen_fig_ids: set[str] = set()
    for match in _FIGURE_BLOCK_RE.finditer(tex_body):
        fig_id = match.group(2)
        if fig_id in seen_fig_ids:
            continue
        figure_blocks.append((fig_id, match.group(1)))
        seen_fig_ids.add(fig_id)
    fig_ids = [fig_id for fig_id, _block_text in figure_blocks]
    if not fig_ids:
        return tex_body

    def _figure_ref_label(fig_id: str, block_text: str) -> str:
        for label_match in _LABEL_RE.finditer(block_text):
            label = label_match.group("label")
            if label.startswith("fig:"):
                return label
        return f"fig:{fig_id}"

    ref_labels = {
        fig_id: _figure_ref_label(fig_id, block_text)
        for fig_id, block_text in figure_blocks
    }

    def _ref_pattern(label: str) -> re.Pattern[str]:
        return re.compile(r"\\(?:auto)?ref\{" + re.escape(label) + r"\}")

    def _find_para_bounds(text: str, ref_start: int, ref_end_pos: int):
        """Return (para_start, insert_at) for the paragraph containing ref_start..ref_end_pos."""
        # paragraph end: first \n\n or section heading after the reference
        para_end_m = re.search(r"\n\s*\n|(?=\s*\\(?:sub)*section\{)", text[ref_end_pos:])
        insert_at = ref_end_pos + (para_end_m.end() if para_end_m else len(text) - ref_end_pos)
        # paragraph start: last \n\n or heading boundary before the reference
        para_start = 0
        for _m in re.finditer(r"\n\s*\n|(?<=\n)(?=\s*\\(?:sub)*section\{)", text[:ref_start]):
            para_start = _m.end()
        return para_start, insert_at

    # Phase 1: for each fig_id, find its first reference and compute its target paragraph.
    # Build a map: insert_at -> list of (fig_id, ref first-occurrence position) in ref order.
    # We work on the original tex_body for this phase so positions are consistent.
    from collections import defaultdict
    insert_groups: dict[int, list[str]] = defaultdict(list)  # insert_at -> [fig_id, ...]
    fig_para_info: dict[str, tuple[int, int, int]] = {}  # fig_id -> (para_start, insert_at, ref_pos)

    for fig_id in fig_ids:
        ref_pattern = _ref_pattern(ref_labels[fig_id])
        ref_match = ref_pattern.search(tex_body)
        if ref_match is None:
            continue
        para_start, insert_at = _find_para_bounds(tex_body, ref_match.start(), ref_match.end())
        fig_para_info[fig_id] = (para_start, insert_at, ref_match.start())

    # Group fig_ids by their insert_at (same paragraph), preserving document order within group.
    for fig_id in fig_ids:
        if fig_id not in fig_para_info:
            continue
        _, insert_at, _ = fig_para_info[fig_id]
        insert_groups[insert_at].append(fig_id)

    # Phase 2: process each group together on the (mutating) result string.
    result = tex_body
    # Sort groups by their insert_at in the *original* text so we process earlier
    # paragraphs first; after each group's removal+insertion we recompute positions.
    for orig_insert_at in sorted(insert_groups.keys()):
        group = insert_groups[orig_insert_at]

        # Re-scan result for current block positions; check adjacency on current state.
        blocks_to_move: list[tuple] = []  # (fig_id, block_text) pairs in document order

        for fig_id in group:
            block_pattern = re.compile(
                r'([ \t]*%\s*FIGURE\s+id=' + re.escape(fig_id) + r'[^\n]*\n'
                r'[ \t]*\\begin\{figure\}.*?\\end\{figure\})',
                re.DOTALL,
            )
            block_match = block_pattern.search(result)
            if block_match is None:
                continue

            ref_pattern = _ref_pattern(ref_labels[fig_id])
            ref_match = ref_pattern.search(result)
            if ref_match is None:
                continue

            para_start, insert_at = _find_para_bounds(result, ref_match.start(), ref_match.end())
            block_start = block_match.start()
            block_end = block_match.end()

            after_gap = result[insert_at:block_start] if block_start >= insert_at else None
            adjacent_after = after_gap is not None and not after_gap.strip()

            before_gap = result[block_end:para_start] if block_end <= para_start else None
            adjacent_before = before_gap is not None and not before_gap.strip()

            if adjacent_after or adjacent_before:
                continue

            blocks_to_move.append((fig_id, block_match.group(1)))

        if not blocks_to_move:
            continue

        # Remove all blocks-to-move from result (from last to first to keep offsets valid).
        # Collect current positions first.
        positions = []
        for fig_id, _block_text in blocks_to_move:
            block_pattern = re.compile(
                r'[ \t]*%\s*FIGURE\s+id=' + re.escape(fig_id) + r'[^\n]*\n'
                r'[ \t]*\\begin\{figure\}.*?\\end\{figure\}',
                re.DOTALL,
            )
            m = block_pattern.search(result)
            if m:
                positions.append((m.start(), m.end(), fig_id))

        # Sort by position descending so removing later blocks first doesn't shift earlier ones.
        positions.sort(key=lambda x: x[0], reverse=True)
        for start, end, _fig_id in positions:
            before = re.sub(r"\n+$", "\n", result[:start])
            result = before + result[end:]

        # Recompute insert_at on the now-trimmed result using any fig in the group.
        anchor_fig_id = blocks_to_move[0][0]
        anchor_ref_pat = _ref_pattern(ref_labels[anchor_fig_id])
        anchor_ref = anchor_ref_pat.search(result)
        if anchor_ref is None:
            continue
        _, insert_at = _find_para_bounds(result, anchor_ref.start(), anchor_ref.end())

        # Insert all blocks in their original document order at insert_at.
        # "Original document order" = order they appeared in tex_body (fig_ids preserves this).
        ordered_blocks = [bt for fid, bt in blocks_to_move]
        insertion = "\n" + "\n".join(ordered_blocks) + "\n"
        result = result[:insert_at] + insertion + result[insert_at:]

    return result


def _check_figures_have_includegraphics(tex: str, survey_dir: Path) -> list[str]:
    """Return figure_missing errors for figure envs without a usable local image."""
    errors = []
    for m in _FIGURE_ENV_RE.finditer(tex):
        env_body = m.group(1)
        graphic_m = _INCLUDEGRAPHICS_RE.search(env_body)
        if graphic_m is None:
            label_m = _LABEL_RE.search(m.group(1))
            label = label_m.group("label") if label_m else "<unknown>"
            errors.append(
                f"figure_missing: {label}"
                r" (figure environment has no \includegraphics — PNG not injected)"
            )
            continue
        graphic_path = Path(graphic_m.group("path"))
        resolved = graphic_path if graphic_path.is_absolute() else survey_dir / graphic_path
        if not resolved.exists():
            label_m = _LABEL_RE.search(env_body)
            label = label_m.group("label") if label_m else "<unknown>"
            errors.append(
                f"figure_missing: {label}"
                f" (includegraphics file not found: {graphic_m.group('path')})"
            )
    return errors


def inject_figure_placeholders(tex_body: str, survey_dir: Path) -> tuple[str, list[str]]:
    r"""Replace % FIGURE placeholder comments with \includegraphics figure environments.

    Returns (modified_tex, warnings). If any referenced PNG is missing, warnings
    contains "figure_missing: <id>" entries and the returned tex is unchanged.
    Also blocks if any \begin{figure} environment has no \includegraphics after injection
    (e.g. a figure block that was never annotated with % FIGURE).
    """
    placeholders = _FIGURE_PLACEHOLDER_RE.findall(tex_body)
    placeholder_lines = _FIGURE_COMMENT_RE.findall(tex_body)
    if len(placeholder_lines) != len(placeholders):
        return tex_body, [
            "figure_missing: malformed % FIGURE placeholder "
            "(expected: % FIGURE id=<id> prompt=\"...\")"
        ]
    if not placeholders:
        # No % FIGURE annotations — still check for bare figure envs without \includegraphics.
        no_graphic = _check_figures_have_includegraphics(tex_body, survey_dir)
        if no_graphic:
            return tex_body, no_graphic
        return tex_body, []

    missing = [
        fig_id
        for fig_id, _prompt in placeholders
        if not (survey_dir / "figures" / f"{fig_id}.png").exists()
    ]
    if missing:
        return tex_body, [f"figure_missing: {fig_id}" for fig_id in missing]

    # Process sequentially: for each placeholder, find and patch the next figure env
    result = tex_body
    for fig_id, _prompt in placeholders:
        comment_pattern = re.compile(
            r'^[ \t]*%\s*FIGURE\s+id=' + re.escape(fig_id) + r'\s+prompt="(?:[^"\\]|\\.)*"[ \t]*\n',
            re.MULTILINE | re.IGNORECASE,
        )
        comment_match = comment_pattern.search(result)
        if comment_match is None:
            # Placeholder comment disappeared (e.g. stripped by a pre-processing step);
            # treat as missing so export fails rather than silently producing a
            # figure environment without \includegraphics.
            return tex_body, [f"figure_missing: {fig_id} (placeholder comment not found)"]
        after_comment = result[comment_match.end():]
        env_match = _FIGURE_ENV_RE.search(after_comment)
        if env_match is None:
            # \begin{figure} environment not found after placeholder comment;
            # returning unchanged tex would produce a figure with no \includegraphics.
            return tex_body, [f"figure_missing: {fig_id} (figure environment not found after placeholder)"]
        env_body = env_match.group(1)
        caption_match = _CAPTION_RE.search(env_body)
        label_match = _LABEL_RE.search(env_body)
        expected_labels = {f"fig:{fig_id}"}
        if fig_id.startswith("fig_"):
            expected_labels.add(f"fig:{fig_id[4:]}")
        if label_match is None:
            return tex_body, [f"figure_missing: {fig_id} (figure label missing)"]
        if label_match.group("label") not in expected_labels:
            return tex_body, [
                f"figure_missing: {fig_id} (placeholder id does not match "
                f"figure label {label_match.group('label')}; expected one of "
                f"{sorted(expected_labels)})"
            ]
        caption_str = f"\\caption{caption_match.group(1)}" if caption_match else "\\caption{}"
        replacement = (
            "\\begin{figure}[H]\n"
            "  \\centering\n"
            f"  \\includegraphics[width=0.85\\textwidth]{{figures/{fig_id}.png}}\n"
            f"  {caption_str}\n"
            "\\end{figure}"
        )
        full_block_start = comment_match.start()
        full_block_end = comment_match.end() + env_match.end()
        result = result[:full_block_start] + replacement + result[full_block_end:]

    # Final pass: any remaining figure env without \includegraphics was not covered
    # by a % FIGURE annotation (mixed document) — block export.
    if _FIGURE_COMMENT_RE.search(result):
        return tex_body, ["figure_missing: unresolved % FIGURE placeholder remains after injection"]

    no_graphic = _check_figures_have_includegraphics(result, survey_dir)
    if no_graphic:
        return tex_body, no_graphic

    return result, []


def strip_latex_bibliography_commands(latex_text: str) -> str:
    without_inline_bib = _LATEX_THEBIBLIOGRAPHY_BLOCK_RE.sub("", latex_text)
    return _LATEX_BIBLIOGRAPHY_COMMAND_RE.sub("", without_inline_bib).rstrip()


def parenthesize_plain_natbib_cites(latex_text: str) -> str:
    """Convert generic natbib author-year citations to parenthetical citations."""
    return re.sub(
        r"\\cite(?![A-Za-z*])((?:\[[^\]\n]*\]){0,2}\{[^{}\n]+\})",
        r"\\citep\1",
        latex_text,
    )


def copy_latex_assets(skill_dir: str | Path, build_dir: Path, bib_style: str, package_option: str = "numbers,sort&compress") -> tuple[bool, str]:
    latex_dir, err = find_asset_dir(skill_dir, "latex")
    if err or latex_dir is None:
        return False, str(err)

    cls = latex_dir / "SciMasterNoBrand.cls"
    if not cls.exists():
        return False, f"class_missing: {cls}"
    shutil.copy2(cls, build_dir / cls.name)

    bundled_bst = latex_dir / f"{bib_style}.bst"
    if bundled_bst.exists():
        shutil.copy2(bundled_bst, build_dir / bundled_bst.name)
    else:
        if shutil.which("kpsewhich") is None:
            return False, f"kpsewhich_not_found_for_bst: {bib_style}.bst"
        check = run_command(["kpsewhich", f"{bib_style}.bst"], timeout=30)
        if check.returncode != 0 or not check.stdout.strip():
            return False, f"bibtex_style_missing: {bib_style}.bst"
    package_name = citation_package_name(bib_style, package_option)
    if shutil.which("kpsewhich") is None:
        return False, f"kpsewhich_not_found_for_package: {package_name}.sty"
    package_check = run_command(["kpsewhich", f"{package_name}.sty"], timeout=30)
    if package_check.returncode != 0 or not package_check.stdout.strip():
        return False, f"latex_package_missing: {package_name}.sty"
    return True, ""


def rebuild_references_from_bbl(
    survey_dir: Path,
    build_dir: Path,
    stem: str,
    _skill_dir: str | Path,
) -> tuple[bool, str]:
    bbl_path = build_dir / f"{stem}.bbl"
    if not bbl_path.exists():
        return False, f"bbl_missing: {bbl_path}"
    return rebuild_references_from_build_bib(survey_dir, build_dir, bbl_path)


def prepare_pdf_bib(bib: Path, build_dir: Path) -> str:
    build_bib = build_dir / "references.bib"
    if bib_entry_count(bib) == 0 and bib_entry_count(build_bib) > 0:
        return "input_bib_empty_used_existing_build_bib"
    shutil.copy2(bib, build_bib)
    return ""


def assemble_latex_source(
    survey_dir: Path,
    build_dir: Path,
    title: str,
    stem: str,
    lang: str,
    bib: Path | None,
    bib_style: str,
    natbib_option: str,
) -> tuple[Path | None, list[str]]:
    # mainbody.tex contains \begin{abstract}, \keywords{}, \maketitle,
    # \tableofcontents, and all sections — do not inject them here.
    language_block = (
        "\\renewcommand{\\abstracttitle}{摘要}\n"
        "\\def\\keywordstitle{关键词}\n"
        "\\addto\\captionsenglish{\\renewcommand{\\refname}{参考文献}}\n"
        "\\addto\\captionsenglish{\\renewcommand{\\contentsname}{目录}}\n"
        # \AtBeginDocument fires after all \addto/\extras hooks (babel + hyperref),
        # guaranteeing zh names override all language-based resets.
        "\\AtBeginDocument{%\n"
        "  \\captionsetup[figure]{name=图}%\n"
        "  \\captionsetup[table]{name=表}%\n"
        "  \\renewcommand{\\figurename}{图}%\n"
        "  \\renewcommand{\\tablename}{表}%\n"
        "  \\renewcommand{\\figureautorefname}{图}%\n"
        "  \\renewcommand{\\tableautorefname}{表}%\n"
        "}\n"
    ) if lang == "zh" else "\\def\\keywordstitle{Keywords}\n"

    citation_package = citation_package_line(bib_style, natbib_option)

    preamble = f"""\\documentclass[11pt, a4paper, nonumbering]{{SciMasterNoBrand}}

{citation_package}
\\bibliographystyle{{{bib_style}}}

% bookmark replaces hyperref's two-pass .out writer with a single-pass mechanism,
% eliminating the rerunfilecheck "Rerun to get outlines right" demand that
% causes latexmk to exit non-zero when iteration is cut short.
\\usepackage{{bookmark}}

\\usepackage{{iftex}}
\\ifPDFTeX
  \\usepackage[utf8]{{inputenc}}
  \\usepackage[T1]{{fontenc}}
\\else
  \\usepackage{{fontspec}}
  \\usepackage{{xeCJK}}
  \\IfFontExistsTF{{Noto Serif CJK SC}}{{\\setCJKmainfont{{Noto Serif CJK SC}}}}{{
    \\IfFontExistsTF{{Source Han Serif SC}}{{\\setCJKmainfont{{Source Han Serif SC}}}}{{
      \\IfFontExistsTF{{Noto Sans CJK SC}}{{\\setCJKmainfont{{Noto Sans CJK SC}}}}{{}}}}}}
  \\XeTeXlinebreaklocale "zh"
  \\XeTeXlinebreakskip=0pt plus 1pt
\\fi

\\usepackage{{float}}
\\usepackage{{amsmath,amssymb,amsfonts,graphicx,booktabs,xcolor}}
\\usepackage{{tabularx,array}}
\\newcolumntype{{L}}{{>{{\\raggedright\\arraybackslash}}X}}
\\newcolumntype{{C}}{{>{{\\centering\\arraybackslash}}X}}
\\newcolumntype{{R}}{{>{{\\raggedleft\\arraybackslash}}X}}
\\captionsetup{{justification=centering,singlelinecheck=off}}

% Float placement: keep figures/tables within their own section.
% placeins provides \\FloatBarrier which is inserted before every \\section{{}}.
\\usepackage[section]{{placeins}}
% Allow up to 85% of a page to be floats; require at least 10% text per page.
% This prevents floats from being deferred excessively far from their source.
\\renewcommand{{\\topfraction}}{{0.85}}
\\renewcommand{{\\bottomfraction}}{{0.70}}
\\renewcommand{{\\textfraction}}{{0.10}}
\\renewcommand{{\\floatpagefraction}}{{0.80}}
\\setcounter{{topnumber}}{{3}}
\\setcounter{{bottomnumber}}{{2}}
\\setcounter{{totalnumber}}{{4}}

{language_block}
\\renewcommand{{\\absfont}}{{\\linespread{{1.5}}\\fontsize{{11}}{{14}}\\selectfont}}
\\renewcommand{{\\keywordstitlefont}}{{\\bfseries\\linespread{{1.5}}\\fontsize{{11}}{{14}}\\selectfont}}
\\renewcommand{{\\keywordsfont}}{{\\itshape\\linespread{{1.5}}\\fontsize{{11}}{{14}}\\selectfont}}

\\title{{{latex_escape(title)}}}

\\begin{{document}}
"""
    bibliography = "\\bibliography{references}\n" if bib else ""
    body = strip_latex_bibliography_commands((survey_dir / "mainbody.tex").read_text(encoding="utf-8"))
    abstract_err = check_abstract_float_refs(body)
    if abstract_err:
        return None, [abstract_err]
    float_err = check_unreferenced_floats(body)
    if float_err:
        return None, [float_err]
    table_err = check_table_has_tabular(body)
    if table_err:
        return None, [table_err]
    body = reposition_figures_after_first_ref(body)
    body, fig_warnings = inject_figure_placeholders(body, survey_dir)
    missing_figs = [w for w in fig_warnings if w.startswith("figure_missing:")]
    if missing_figs:
        return None, missing_figs
    body = normalize_float_layout_for_export(body)
    body = wrap_simple_pdf_tabulars_with_tabularx(body)
    if natbib_option == "authoryear":
        body = parenthesize_plain_natbib_cites(body)
    tex_path = build_dir / f"{stem}.tex"
    tex_path.write_text(
        preamble
        + body
        + "\n\n"
        + bibliography
        + "\\end{document}\n",
        encoding="utf-8",
    )
    return tex_path, fig_warnings


def copy_latex_source_assets(skill_dir: str | Path, build_dir: Path, bib_style: str) -> tuple[bool, str]:
    latex_dir, err = find_asset_dir(skill_dir, "latex")
    if err or latex_dir is None:
        return False, str(err)

    cls = latex_dir / "SciMasterNoBrand.cls"
    if not cls.exists():
        return False, f"class_missing: {cls}"
    shutil.copy2(cls, build_dir / cls.name)

    bundled_bst = latex_dir / f"{bib_style}.bst"
    if bundled_bst.exists():
        shutil.copy2(bundled_bst, build_dir / bundled_bst.name)
    return True, ""


def export_tex(
    survey_dir: Path,
    title: str,
    stem: str,
    lang: str,
    bib: Path | None,
    skill_dir: str | Path,
    bib_style_arg: str,
    *,
    citation_style_name: str = "",
) -> ExportResult:
    build_dir = survey_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    bib_style, natbib_option = resolve_bib_style(
        bib_style_arg,
        survey_dir,
        lang,
        citation_style_name=citation_style_name,
    )
    copied, asset_error = copy_latex_source_assets(skill_dir, build_dir, bib_style)
    if not copied:
        return ExportResult("tex", "ERROR", message=asset_error)
    if bib:
        shutil.copy2(bib, build_dir / "references.bib")

    figures_src = survey_dir / "figures"
    if figures_src.is_dir():
        figures_dst = build_dir / "figures"
        if figures_dst.exists():
            shutil.rmtree(figures_dst)
        shutil.copytree(figures_src, figures_dst)

    tex_path, fig_warnings = assemble_latex_source(
        survey_dir, build_dir, title, stem, lang, bib, bib_style, natbib_option
    )
    if tex_path is None:
        return ExportResult("tex", "ERROR", message="; ".join(fig_warnings))

    output = survey_dir / f"{stem}.tex"
    shutil.copy2(tex_path, output)
    return ExportResult("tex", "OK", output, warnings=fig_warnings)


_LATEX_ERROR_PATTERNS: list[tuple[str, str, str]] = [
    # Fatal errors first — these produce a "! " line and must be caught before
    # citation warnings, which are merely informational and often co-occur.
    (r"I can't find file|LaTeX Error: File.*not found|kpathsea", "FILE_NOT_FOUND",
     "A required .cls/.sty/.bst file is missing. Check that bundled assets in latex/ are present."),
    (r"Runaway argument|File ended while scanning", "RUNAWAY_ARGUMENT",
     "A brace or environment was never closed. Common cause: a \\url{} in references.bib "
     "contains a truncated URL or an anti-bot redirect — check bib entries for malformed URLs."),
    (r"^!.*Font|font.*not found|kpsewhich.*tfm", "FONT_MISSING",
     "Required font missing. Install CTeX/XeCJK packages (e.g. tlmgr install ctex)."),
    (r"^!", "LATEX_ERROR",
     "LaTeX syntax error. Check mainbody.tex for unescaped special characters (& % $ # ^ ~ _)."),
    # Warnings/informational — checked only when no fatal "! " error was found.
    (r"LaTeX Error: \\\\bibstyle|bibtex.*error|Bibliography.*error", "BIB_ERROR",
     "BibTeX error. Check references.bib for duplicate keys or malformed entries."),
    (r"Citation.*undefined|There were undefined references", "CITE_ERROR",
     "\\cite{} keys are undefined. Run survey_checks.py cites, then re-run export-bib."),
]


def latex_log_has_fatal_error(log_path: Path) -> bool:
    """Return True if the log contains a fatal LaTeX error (a '! ' line)."""
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"^! ", text, re.MULTILINE))


def latex_diagnose(log_path: Path) -> str:
    """Return a structured one-call diagnostic string for a LaTeX compile failure."""
    if not log_path.exists():
        return "latex_log_missing"
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Find the first fatal "! " line — context is anchored to it if present.
    error_line_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.startswith("! "):
            error_line_idx = idx
            break

    # Match patterns in priority order. Fatal patterns are listed first so that
    # a runaway-argument or syntax error is never masked by a co-occurring
    # citation warning (which is merely informational when a fatal error exists).
    error_type = "OTHER"
    fix_hint = "Review log context. Run latexmk again if only 'undefined references' warnings remain."
    for pattern, etype, hint in _LATEX_ERROR_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            error_type = etype
            fix_hint = hint
            break

    if error_line_idx is not None:
        ctx_start = max(0, error_line_idx - 3)
        ctx_end = min(len(lines), error_line_idx + 11)
        context = "\n".join(lines[ctx_start:ctx_end])
    else:
        context = "\n".join(lines[-20:])

    return f"ERROR_TYPE={error_type}\nFIX={fix_hint}\nCONTEXT:\n{context}"


def export_pdf(
    survey_dir: Path,
    title: str,
    stem: str,
    lang: str,
    bib: Path | None,
    skill_dir: str | Path,
    bib_style_arg: str,
    *,
    citation_style_name: str = "",
) -> ExportResult:
    pdf_engine = "latexmk-xelatex"
    if shutil.which("latexmk") is None:
        return ExportResult(
            "pdf",
            "ERROR",
            message=(
                f"dependency_not_found: latexmk; engine={pdf_engine}; "
                "HTML-to-PDF fallback is forbidden"
            ),
        )

    build_dir = survey_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    bib_style, natbib_option = resolve_bib_style(
        bib_style_arg,
        survey_dir,
        lang,
        citation_style_name=citation_style_name,
    )
    copied, asset_error = copy_latex_assets(skill_dir, build_dir, bib_style, natbib_option)
    if not copied:
        return ExportResult("pdf", "ERROR", message=asset_error)
    warnings: list[str] = []
    if bib:
        prepare_warning = prepare_pdf_bib(bib, build_dir)
        if prepare_warning:
            warnings.append(prepare_warning)
        build_bib = build_dir / "references.bib"
        normalize_warnings = normalize_bib_urls(build_bib)
        warnings.extend(normalize_warnings)
        bib_url_errors = check_bib_urls(build_bib)
        if bib_url_errors:
            return ExportResult("pdf", "ERROR", message="; ".join(bib_url_errors))

    figures_src = survey_dir / "figures"
    if figures_src.is_dir():
        figures_dst = build_dir / "figures"
        if figures_dst.exists():
            shutil.rmtree(figures_dst)
        shutil.copytree(figures_src, figures_dst)

    tex_path, fig_warnings = assemble_latex_source(survey_dir, build_dir, title, stem, lang, bib, bib_style, natbib_option)
    if tex_path is None:
        return ExportResult("pdf", "ERROR", message="; ".join(fig_warnings))
    warnings.extend(fig_warnings)
    # -f keeps latexmk going through all required passes even when xelatex
    # exits non-zero on non-fatal warnings (undefined refs, "Rerun to get
    # cross-references right", bibtex minor warnings). Without this, the
    # first-pass non-zero exit aborts before the .toc file is read on pass 2
    # and the rendered PDF ends up with an empty table of contents.
    cmd = [
        "latexmk",
        "-xelatex",
        "-interaction=nonstopmode",
        "-file-line-error",
        "-f",
        f"-outdir={build_dir}",
        tex_path.name,
    ]
    if bib:
        cmd.insert(2, "-bibtex")

    result = run_command(cmd, cwd=build_dir, timeout=300)
    warnings.append(f"pdf_engine={pdf_engine}")

    # PDF existence is necessary but not sufficient — latexmk -f continues past
    # fatal errors (e.g. runaway argument from a malformed \url{} in .bbl) and
    # still writes a PDF that is missing the bibliography section entirely.
    # We therefore also check the log for fatal "! " errors even when a PDF exists.
    built_pdf = build_dir / f"{stem}.pdf"
    log_path = build_dir / f"{stem}.log"

    if not built_pdf.exists():
        return ExportResult(
            "pdf",
            "ERROR",
            message=latex_diagnose(log_path) or "latexmk_exit_nonzero_no_pdf",
        )

    if latex_log_has_fatal_error(log_path):
        # Delete the corrupt PDF so that downstream callers and retry logic
        # do not mistake it for a valid artefact.
        built_pdf.unlink(missing_ok=True)
        # Run latexmk -C to clean all auxiliary files for this stem so a
        # subsequent retry starts from a clean state.
        clean_cmd = ["latexmk", "-C", f"-outdir={build_dir}", tex_path.name]
        run_command(clean_cmd, cwd=build_dir, timeout=30)
        return ExportResult(
            "pdf",
            "ERROR",
            message=latex_diagnose(log_path),
        )

    if result.returncode != 0:
        log_tail = latex_diagnose(log_path)
        warnings.append(
            f"latexmk_nonzero_but_pdf_exists: rc={result.returncode}; "
            f"log_tail={log_tail[:200]}"
        )

    if bib and not (build_dir / f"{stem}.bbl").exists():
        return ExportResult("pdf", "ERROR", message=f"bbl_missing: {build_dir / f'{stem}.bbl'}")
    if bib:
        rebuilt, rebuild_error = rebuild_references_from_bbl(survey_dir, build_dir, stem, skill_dir)
        if not rebuilt:
            return ExportResult("pdf", "ERROR", message=f"references_rebuild_failed: {rebuild_error}")
        if rebuild_error:
            warnings.append(rebuild_error)

    output = survey_dir / f"{stem}.pdf"
    shutil.copy2(built_pdf, output)
    return ExportResult("pdf", "OK", output, message=f"engine={pdf_engine}", warnings=warnings)


def print_result(result: ExportResult) -> None:
    path = str(result.path) if result.path else "-"
    message = result.message or "-"
    print(f"EXPORT_RESULT {result.format} {result.status} {path} {message}")
    for warning in result.warnings:
        print(f"EXPORT_WARNING {result.format} {warning}", file=sys.stderr)


def print_shared_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"EXPORT_WARNING shared {warning}", file=sys.stderr)


def clean_export_retry_artifacts(format_name: str, survey_dir: Path, stem: str) -> None:
    if format_name == "docx":
        targets = [survey_dir / f"{stem}.docx", survey_dir / f"{stem}_full.tex"]
    elif format_name == "tex":
        targets = [survey_dir / f"{stem}.tex", survey_dir / "build" / f"{stem}.tex"]
    elif format_name == "pdf":
        build_dir = survey_dir / "build"
        suffixes = ("aux", "bbl", "blg", "fdb_latexmk", "fls", "log", "out", "pdf", "toc", "xdv")
        targets = [build_dir / f"{stem}.{suffix}" for suffix in suffixes]
        targets.append(survey_dir / f"{stem}.pdf")
        figures_dst = build_dir / "figures"
        if figures_dst.exists():
            shutil.rmtree(figures_dst, ignore_errors=True)
    else:
        targets = []
    for target in targets:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


def run_export_step(format_name: str, callback, cleanup_before_retry=None) -> ExportResult:
    try:
        first = callback()
        if first.ok:
            return first
        if cleanup_before_retry is not None:
            cleanup_before_retry()
        second = callback()
        if second.ok:
            second.warnings.insert(0, f"retry_after_error: {first.message or first.status}")
            return second
        second.warnings.insert(0, f"retry_failed_after_error: {first.message or first.status}")
        return second
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return ExportResult(format_name, "ERROR", message=f"unexpected_error: {exc}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    survey_dir = Path(args.survey_dir).expanduser().resolve()
    if not survey_dir.exists():
        print(f"ERROR: survey dir not found: {survey_dir}", file=sys.stderr)
        return 1
    if not (survey_dir / "mainbody.tex").exists():
        print(f"ERROR: mainbody.tex not found: {survey_dir / 'mainbody.tex'}", file=sys.stderr)
        return 1
    mainbody_tex = (survey_dir / "mainbody.tex").read_text(encoding="utf-8", errors="replace")
    abstract_env_err = check_abstract_environment(strip_latex_bibliography_commands(mainbody_tex))
    if abstract_env_err:
        print(f"ERROR: {abstract_env_err}", file=sys.stderr)
        return 1

    bib = Path(args.bib) if args.bib else None
    if bib and not bib.exists():
        print(f"ERROR: --bib not found: {bib}", file=sys.stderr)
        return 1

    lang = args.language.strip().lower()
    try:
        title = resolve_title(survey_dir, args.title, args.outline)
    except JsonConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    stem = derive_stem(title)
    using_default_formats = args.formats is None
    formats_arg = args.formats or "docx,tex,pdf"
    formats = {item.strip().lower() for item in formats_arg.split(",") if item.strip()}
    supported_formats = {"docx", "tex", "pdf"}
    unsupported_formats = formats - supported_formats
    if unsupported_formats:
        print(f"ERROR: unsupported formats requested: {','.join(sorted(unsupported_formats))}", file=sys.stderr)
        return 1
    requested = [fmt for fmt in ("docx", "tex", "pdf") if fmt in formats]
    if not requested:
        print("ERROR: no supported formats requested", file=sys.stderr)
        return 1
    optional_arg = args.optional_formats
    if optional_arg is None:
        optional_formats = {"pdf"} if using_default_formats and "pdf" in requested else set()
    else:
        optional_formats = {item.strip().lower() for item in optional_arg.split(",") if item.strip()}
    optional_requested = optional_formats & set(requested)

    try:
        citation_style_name, citation_style_source, shared_warnings = resolve_citation_style_name(
            survey_dir,
            lang,
            citation_style_arg=args.citation_style,
        )
    except JsonConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if citation_style_source == "writing_constraints":
        print(
            f"EXPORT_INFO citation_style={citation_style_name} source=writing_constraints",
            file=sys.stderr,
        )
    elif citation_style_source == "cli":
        print(
            f"EXPORT_INFO citation_style={citation_style_name} source=cli",
            file=sys.stderr,
        )
    print_shared_warnings(shared_warnings)

    csl: Path | None = None
    csl_err: str | None = None
    if bib and "docx" in requested:
        csl, csl_err = resolve_csl(
            args.csl,
            survey_dir,
            args.skill_dir,
            lang,
            citation_style_name=citation_style_name,
        )

    docx_template: Path | None = None
    docx_template_err: str | None = None
    if "docx" in requested:
        docx_template, docx_template_err = resolve_docx_template(args.skill_dir, lang)

    # Pre-export float count gate: block if referenced figures/tables are fewer than expected.
    # "Actual" counts only labels that also have at least one \autoref{} — consistent with
    # survey_checks.py cmd_figures_tables and check_unreferenced_floats (unreferenced floats
    # are a separate error and must not inflate the count here).
    outline_path = Path(args.outline) if getattr(args, "outline", None) else survey_dir / "outline.json"
    if outline_path.exists():
        try:
            _outline_data = json.loads(outline_path.read_text(encoding="utf-8"))
            _expected_figs = _outline_data.get("expected_figures_total")
            _expected_tabs = _outline_data.get("expected_tables_total")
            _body_tex = (survey_dir / "mainbody.tex").read_text(encoding="utf-8", errors="replace")
            _fig_labels = {m.group("label") for m in _LABEL_RE.finditer(_body_tex) if m.group("label").startswith("fig:")}
            _tab_labels = {m.group("label") for m in _LABEL_RE.finditer(_body_tex) if m.group("label").startswith("tab:")}
            _xrefs = {m.group("label") for m in _XREF_RE.finditer(_body_tex)}
            _actual_figs = len(_fig_labels & _xrefs)
            _actual_tabs = len(_tab_labels & _xrefs)
            _count_errors: list[str] = []
            if isinstance(_expected_figs, int) and _actual_figs < _expected_figs:
                _count_errors.append(
                    f"FIGURE_COUNT_INSUFFICIENT: actual={_actual_figs} expected={_expected_figs}"
                    f" — {_expected_figs - _actual_figs} figure(s) missing; add figures before exporting"
                )
            if isinstance(_expected_tabs, int) and _actual_tabs < _expected_tabs:
                _count_errors.append(
                    f"TABLE_COUNT_INSUFFICIENT: actual={_actual_tabs} expected={_expected_tabs}"
                    f" — {_expected_tabs - _actual_tabs} table(s) missing; add tables before exporting"
                )
            if _count_errors:
                for _err in _count_errors:
                    print(f"ERROR: {_err}", file=sys.stderr)
                return 1
        except (json.JSONDecodeError, OSError):
            pass

    # Export formats sequentially. Required format failures block; optional
    # format failures are reported and cleaned up, then the remaining steps continue.
    format_steps = []
    if "docx" in requested:
        if csl_err:
            format_steps.append(("docx", None, None))
        elif docx_template_err or docx_template is None:
            format_steps.append(("docx", None, None))
        else:
            format_steps.append((
                "docx",
                lambda: export_docx(survey_dir, title, stem, lang, bib, csl, docx_template),
                lambda: clean_export_retry_artifacts("docx", survey_dir, stem),
            ))
    if "tex" in requested:
        format_steps.append((
            "tex",
            lambda: export_tex(
                survey_dir, title, stem, lang, bib,
                args.skill_dir, args.bib_style,
                citation_style_name=citation_style_name,
            ),
            lambda: clean_export_retry_artifacts("tex", survey_dir, stem),
        ))
    if "pdf" in requested:
        format_steps.append((
            "pdf",
            lambda: export_pdf(
                survey_dir, title, stem, lang, bib,
                args.skill_dir, args.bib_style,
                citation_style_name=citation_style_name,
            ),
            lambda: clean_export_retry_artifacts("pdf", survey_dir, stem),
        ))

    for fmt, callback, cleanup in format_steps:
        if callback is None:
            # Pre-failed dependency (CSL or template missing)
            if fmt == "docx" and (docx_template_err or docx_template is None):
                result = ExportResult(fmt, "ERROR", message=f"DOCX template resolution failed ({docx_template_err})")
            else:
                result = ExportResult(fmt, "ERROR", message=f"CSL resolution failed ({csl_err})")
            print_result(result)
            # Clean up any partial artifacts for this format, then block only
            # when the format is required.
            clean_export_retry_artifacts(fmt, survey_dir, stem)
            if fmt in optional_requested:
                print(f"EXPORT_WARNING {fmt} optional_format_failed_nonblocking", file=sys.stderr)
                continue
            return 1

        result = run_export_step(fmt, callback, cleanup_before_retry=cleanup)
        print_result(result)
        if not result.ok:
            # Clean up this format's output artifacts so no partial file lingers
            clean_export_retry_artifacts(fmt, survey_dir, stem)
            if fmt in optional_requested:
                print(f"EXPORT_WARNING {fmt} optional_format_failed_nonblocking", file=sys.stderr)
                continue
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
