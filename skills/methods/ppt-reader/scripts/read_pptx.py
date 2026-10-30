#!/usr/bin/env python3
"""Dependency-free OOXML text reader for PPTX/POTX presentations."""

import posixpath
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def local_name(value: str) -> str:
    return value.rsplit("}", 1)[-1]


def relationship_target(source: str, target: str) -> str:
    if target.startswith("/") or ":" in target:
        raise ValueError(f"unsafe OOXML relationship target: {target!r}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    if resolved.startswith("../"):
        raise ValueError(f"unsafe OOXML relationship target: {target!r}")
    return resolved


def relationships(archive: zipfile.ZipFile, source: str) -> dict[str, tuple[str, str]]:
    rel_path = posixpath.join(posixpath.dirname(source), "_rels", posixpath.basename(source) + ".rels")
    try:
        root = ET.fromstring(archive.read(rel_path))
    except KeyError:
        return {}
    result = {}
    for element in root:
        if local_name(element.tag) != "Relationship":
            continue
        rel_id = element.attrib.get("Id")
        target = element.attrib.get("Target")
        if rel_id and target:
            result[rel_id] = (element.attrib.get("Type", ""), target)
    return result


def slide_parts(archive: zipfile.ZipFile) -> list[str]:
    names = set(archive.namelist())
    try:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = relationships(archive, "ppt/presentation.xml")
        result = []
        for element in presentation.iter():
            if local_name(element.tag) != "sldId":
                continue
            rel_id = next((value for key, value in element.attrib.items() if local_name(key) == "id" and key.startswith("{")), None)
            if not rel_id or rel_id not in rels:
                continue
            rel_type, target = rels[rel_id]
            if not rel_type.endswith("/slide"):
                continue
            part = relationship_target("ppt/presentation.xml", target)
            if part in names:
                result.append(part)
        if result:
            return result
    except KeyError:
        pass
    return sorted((name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")), key=slide_number)


def slide_number(name: str) -> int:
    stem = Path(name).stem.removeprefix("slide")
    return int(stem) if stem.isdigit() else 0


def paragraph_text(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter() if local_name(node.tag) == "t").strip()


def table_rows(element: ET.Element) -> list[list[str]]:
    rows = []
    for row in element:
        if local_name(row.tag) != "tr":
            continue
        cells = []
        for cell in row:
            if local_name(cell.tag) != "tc":
                continue
            paragraphs = [paragraph_text(item) for item in cell.iter() if local_name(item.tag) == "p"]
            cells.append(" ".join(text for text in paragraphs if text))
        if cells:
            rows.append(cells)
    return rows


def content(root: ET.Element) -> tuple[list[str], list[list[list[str]]]]:
    text, tables = [], []

    def walk(element: ET.Element) -> None:
        name = local_name(element.tag)
        if name == "tbl":
            rows = table_rows(element)
            if rows:
                tables.append(rows)
            return
        if name == "p":
            value = paragraph_text(element)
            if value:
                text.append(value)
            return
        for child in element:
            walk(child)

    walk(root)
    return text, tables


def notes(archive: zipfile.ZipFile, slide_part: str) -> list[str]:
    for rel_type, target in relationships(archive, slide_part).values():
        if not rel_type.endswith("/notesSlide"):
            continue
        root = ET.fromstring(archive.read(relationship_target(slide_part, target)))
        return [paragraph_text(item) for item in root.iter() if local_name(item.tag) == "p" and paragraph_text(item)]
    return []


def main(filename: str) -> None:
    with zipfile.ZipFile(filename) as archive:
        if "[Content_Types].xml" not in archive.namelist():
            raise ValueError("not an OOXML presentation")
        parts = slide_parts(archive)
        if not parts:
            raise ValueError("presentation contains no slides")
        print(f"# Presentation content ({len(parts)} slides)")
        for index, part in enumerate(parts, 1):
            root = ET.fromstring(archive.read(part))
            text, tables = content(root)
            print(f"\n## Slide {index}")
            if not text and not tables:
                print("(No extractable slide text.)")
            for value in text:
                print(f"- {value}")
            for table_index, table in enumerate(tables, 1):
                print(f"\n### Table {table_index}")
                for row in table:
                    print("| " + " | ".join(row) + " |")
            speaker_notes = notes(archive, part)
            if speaker_notes:
                print("\n### Speaker notes")
                for value in speaker_notes:
                    print(f"- {value}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: read_pptx.py PRESENTATION.pptx")
    main(sys.argv[1])
