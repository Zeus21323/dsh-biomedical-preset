#!/usr/bin/env python3
"""Block delivery when a DOCX lacks working links from citations to bibliography entries."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|parencite|textcite|autocite)\*?(?:\[[^]]*\]){0,2}\{([^}]+)\}"
)
REF_FIELD_RE = re.compile(r"\bREF\s+(_Ref\d+)\s+\\h\b")


def word_tag(name: str) -> str:
    return f"{{{WORD_NS}}}{name}"


def citation_keys(tex_path: Path) -> set[str]:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    keys: set[str] = set()
    for group in CITE_RE.findall(text):
        keys.update(key.strip() for key in group.split(",") if key.strip())
    return keys


def validate_links(tex_path: Path, docx_path: Path) -> dict:
    if not tex_path.is_file():
        raise ValueError(f"tex_not_found: {tex_path}")
    if not docx_path.is_file():
        raise ValueError(f"docx_not_found: {docx_path}")
    keys = citation_keys(tex_path)
    if not keys:
        raise ValueError("citation_commands_missing: canonical TeX has no recognized citation keys")
    try:
        with zipfile.ZipFile(docx_path) as archive:
            root = ET.fromstring(archive.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError) as exc:
        raise ValueError(f"docx_structure_invalid: {exc}") from exc

    bookmarks = {
        node.attrib.get(word_tag("name"), "")
        for node in root.iter(word_tag("bookmarkStart"))
        if node.attrib.get(word_tag("name"))
    }
    hyperlink_anchors = [
        node.attrib.get(word_tag("anchor"), "")
        for node in root.iter(word_tag("hyperlink"))
        if node.attrib.get(word_tag("anchor"), "").startswith("ref-")
    ]
    field_targets: list[str] = []
    for node in root.iter(word_tag("instrText")):
        field_targets.extend(REF_FIELD_RE.findall(node.text or ""))

    errors: list[str] = []
    broken_hyperlinks = sorted(set(hyperlink_anchors) - bookmarks)
    broken_fields = sorted(set(field_targets) - bookmarks)
    if broken_hyperlinks:
        errors.append("citation hyperlinks target missing bookmarks: " + ", ".join(broken_hyperlinks))
    if broken_fields:
        errors.append("citation REF fields target missing bookmarks: " + ", ".join(broken_fields))

    mode = "none"
    if field_targets:
        mode = "word-ref"
    elif hyperlink_anchors:
        mode = "citation-hyperlink"
        expected = {f"ref-{key}" for key in keys}
        missing_links = sorted(expected - set(hyperlink_anchors))
        missing_bookmarks = sorted(expected - bookmarks)
        if missing_links:
            errors.append("citation keys lack body hyperlinks: " + ", ".join(missing_links))
        if missing_bookmarks:
            errors.append("citation keys lack bibliography bookmarks: " + ", ".join(missing_bookmarks))
    else:
        errors.append(
            "docx_citation_crosslinks_missing: no citation hyperlinks or Word REF fields were found"
        )

    return {
        "status": "passed" if not errors else "failed",
        "tex": str(tex_path.resolve()),
        "docx": str(docx_path.resolve()),
        "mode": mode,
        "citation_keys": len(keys),
        "citation_hyperlinks": len(hyperlink_anchors),
        "citation_ref_fields": len(field_targets),
        "bibliography_bookmarks": len([name for name in bookmarks if name.startswith(("ref-", "_Ref"))]),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, required=True)
    parser.add_argument("--docx", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = validate_links(args.tex.resolve(), args.docx.resolve())
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if report["status"] != "passed":
        for error in report["errors"]:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("DOCX_CITATION_LINKS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
