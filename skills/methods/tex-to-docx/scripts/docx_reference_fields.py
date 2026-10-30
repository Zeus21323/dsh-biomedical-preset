"""Add and validate clickable Word REF fields for numeric citations."""

from __future__ import annotations

from copy import deepcopy
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
ET.register_namespace("w", WORD_NS)
ET.register_namespace("m", MATH_NS)
NUMERIC_REFERENCE_RE = re.compile(
    r"^\s*(?:\[(?P<bracketed>\d+)\]|\((?P<parenthesized>\d+)\)|(?P<plain>\d+)(?:[.)])?)(?=\s|$)"
)
NUMERIC_CITATION_RE = re.compile(
    r"(?P<open>[\[(])(?P<body>\d+(?:\s*(?:,|;|-|–|—)\s*\d+)*)(?P<close>[\])])"
)
NUMERIC_CITATION_TOKEN_RE = re.compile(r"\d+|\s*[,;\-–—]\s*")


def word_tag(name: str) -> str:
    return f"{{{WORD_NS}}}{name}"


def element_text(element: ET.Element) -> str:
    return "".join(element.itertext())


def is_field_run(run: ET.Element) -> bool:
    return any(node.tag in {word_tag("fldChar"), word_tag("instrText")} for node in run.iter())


def paragraph_has_field(paragraph: ET.Element) -> bool:
    return any(is_field_run(run) for run in paragraph.findall(word_tag("r")))


def paragraph_has_simple_text(paragraph: ET.Element) -> bool:
    for run in paragraph.findall(word_tag("r")):
        if is_field_run(run):
            return False
        children = [child for child in list(run) if child.tag != word_tag("rPr")]
        if children and any(child.tag != word_tag("t") for child in children):
            return False
    return True


def apply_superscript(run: ET.Element, enabled: bool) -> None:
    props = run.find(word_tag("rPr"))
    if props is None:
        props = ET.Element(word_tag("rPr"))
        run.insert(0, props)
    for node in list(props.findall(word_tag("vertAlign"))):
        props.remove(node)
    if enabled:
        node = ET.SubElement(props, word_tag("vertAlign"))
        node.set(word_tag("val"), "superscript")


def make_text_run(text: str, template: ET.Element | None = None, *, superscript: bool = False) -> ET.Element:
    run = ET.Element(word_tag("r"))
    if template is not None:
        props = template.find(word_tag("rPr"))
        if props is not None:
            run.append(deepcopy(props))
    apply_superscript(run, superscript)
    node = ET.SubElement(run, word_tag("t"))
    if text[:1].isspace() or text[-1:].isspace():
        node.set(XML_SPACE, "preserve")
    node.text = text
    return run


def make_ref_field_runs(number: int, template: ET.Element | None = None, *, superscript: bool = False) -> list[ET.Element]:
    result: list[ET.Element] = []
    for kind in ("begin", "instruction", "separate", "display", "end"):
        run = ET.Element(word_tag("r"))
        if template is not None:
            props = template.find(word_tag("rPr"))
            if props is not None:
                run.append(deepcopy(props))
        apply_superscript(run, superscript)
        if kind in {"begin", "separate", "end"}:
            node = ET.SubElement(run, word_tag("fldChar"))
            node.set(word_tag("fldCharType"), kind)
        elif kind == "instruction":
            node = ET.SubElement(run, word_tag("instrText"))
            node.set(XML_SPACE, "preserve")
            node.text = f" REF _Ref{number} \\h \\* MERGEFORMAT "
        else:
            node = ET.SubElement(run, word_tag("t"))
            node.text = str(number)
        result.append(run)
    return result


def next_bookmark_id(root: ET.Element) -> int:
    ids = [
        int(raw) for node in root.iter(word_tag("bookmarkStart"))
        if (raw := node.attrib.get(word_tag("id"), "")).isdigit()
    ]
    return max(ids, default=0) + 1


def add_reference_bookmark(paragraph: ET.Element, number: int, bookmark_id: int) -> bool:
    if paragraph_has_field(paragraph) or not paragraph_has_simple_text(paragraph):
        return False
    text = element_text(paragraph)
    match = NUMERIC_REFERENCE_RE.match(text)
    if not match:
        return False
    group_name = next(name for name in ("bracketed", "parenthesized", "plain") if match.group(name))
    parsed = int(match.group(group_name))
    if parsed != number:
        return False
    start = match.start(group_name)
    end = match.end(group_name)
    template = next(iter(paragraph.findall(word_tag("r"))), None)
    props = paragraph.find(word_tag("pPr"))
    props_copy = deepcopy(props) if props is not None else None
    paragraph.clear()
    if props_copy is not None:
        paragraph.append(props_copy)
    if text[:start]:
        paragraph.append(make_text_run(text[:start], template))
    begin = ET.Element(word_tag("bookmarkStart"))
    begin.set(word_tag("id"), str(bookmark_id))
    begin.set(word_tag("name"), f"_Ref{number}")
    paragraph.append(begin)
    paragraph.append(make_text_run(text[start:end], template))
    finish = ET.Element(word_tag("bookmarkEnd"))
    finish.set(word_tag("id"), str(bookmark_id))
    paragraph.append(finish)
    if text[end:]:
        paragraph.append(make_text_run(text[end:], template))
    return True


def citation_parts(text: str) -> list[tuple[str, int | str]]:
    parts: list[tuple[str, int | str]] = []
    cursor = 0
    for match in NUMERIC_CITATION_TOKEN_RE.finditer(text):
        if match.start() != cursor:
            return []
        token = match.group(0)
        parts.append(("ref", int(token)) if token.isdigit() else ("text", token))
        cursor = match.end()
    return parts if cursor == len(text) else []


def replace_citations(paragraph: ET.Element, available: set[int], *, superscript: bool = False) -> int:
    if paragraph_has_field(paragraph):
        return 0
    fields = 0
    rebuilt: list[ET.Element] = []
    group: list[ET.Element] = []
    superscript_group: list[ET.Element] = []

    def is_plain_run(node: ET.Element) -> bool:
        if node.tag != word_tag("r") or is_field_run(node):
            return False
        children = [child for child in list(node) if child.tag != word_tag("rPr")]
        return len(children) == 1 and children[0].tag == word_tag("t")

    def is_superscript_run(node: ET.Element) -> bool:
        align = node.find(f".//{word_tag('vertAlign')}")
        return align is not None and align.attrib.get(word_tag("val")) == "superscript"

    def flush() -> None:
        nonlocal fields, group
        if not group:
            return
        text = "".join(element_text(run) for run in group)
        matches: list[tuple[int, int, list[tuple[str, int | str]], str, str]] = []
        for match in NUMERIC_CITATION_RE.finditer(text):
            if (match.group("open"), match.group("close")) not in {("[", "]"), ("(", ")")}:
                continue
            parts = citation_parts(match.group("body"))
            numbers = [int(value) for kind, value in parts if kind == "ref"]
            if numbers and all(number in available for number in numbers):
                matches.append((match.start(), match.end(), parts, match.group("open"), match.group("close")))
        if not matches:
            rebuilt.extend(group)
            group = []
            return
        template = group[0]
        cursor = 0
        for start, end, parts, opening, closing in matches:
            if start > cursor:
                rebuilt.append(make_text_run(text[cursor:start], template))
            rebuilt.append(make_text_run(opening, template, superscript=superscript))
            for kind, value in parts:
                if kind == "ref":
                    rebuilt.extend(make_ref_field_runs(int(value), template, superscript=superscript))
                    fields += 1
                else:
                    rebuilt.append(make_text_run(str(value), template, superscript=superscript))
            rebuilt.append(make_text_run(closing, template, superscript=superscript))
            cursor = end
        if cursor < len(text):
            rebuilt.append(make_text_run(text[cursor:], template))
        group = []

    def flush_superscript() -> None:
        nonlocal fields, superscript_group
        if not superscript_group:
            return
        text = "".join(element_text(run) for run in superscript_group)
        citation_match = NUMERIC_CITATION_RE.fullmatch(text)
        if citation_match and (citation_match.group("open"), citation_match.group("close")) in {("[", "]"), ("(", ")")}:
            opening = citation_match.group("open")
            closing = citation_match.group("close")
            parts = citation_parts(citation_match.group("body"))
        else:
            opening = closing = ""
            parts = citation_parts(text)
        numbers = [int(value) for kind, value in parts if kind == "ref"]
        if not numbers or not all(number in available for number in numbers):
            rebuilt.extend(superscript_group)
            superscript_group = []
            return
        template = superscript_group[0]
        if opening:
            rebuilt.append(make_text_run(opening, template, superscript=True))
        for kind, value in parts:
            if kind == "ref":
                rebuilt.extend(make_ref_field_runs(int(value), template, superscript=True))
                fields += 1
            else:
                rebuilt.append(make_text_run(str(value), template, superscript=True))
        if closing:
            rebuilt.append(make_text_run(closing, template, superscript=True))
        superscript_group = []

    for child in list(paragraph):
        if superscript and is_plain_run(child) and is_superscript_run(child):
            flush()
            superscript_group.append(child)
        elif is_plain_run(child):
            flush_superscript()
            group.append(child)
        else:
            flush()
            flush_superscript()
            rebuilt.append(child)
    flush()
    flush_superscript()
    if fields:
        paragraph[:] = rebuilt
    return fields


def references_heading_index(children: list[ET.Element]) -> int | None:
    for index, child in enumerate(children):
        if child.tag == word_tag("p") and element_text(child).strip().casefold() in {"references", "参考文献"}:
            return index
    return None


def rewrite_document_xml(docx_path: Path, document_xml: bytes) -> None:
    temp = docx_path.with_suffix(docx_path.suffix + ".tmp")
    with zipfile.ZipFile(docx_path) as source, zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            target.writestr(item, document_xml if item.filename == "word/document.xml" else source.read(item.filename))
    shutil.move(str(temp), str(docx_path))


def add_numeric_reference_fields(docx_path: Path, *, superscript: bool = False) -> tuple[int, int]:
    with zipfile.ZipFile(docx_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(word_tag("body"))
    if body is None:
        raise ValueError("docx_body_missing")
    children = list(body)
    heading = references_heading_index(children)
    if heading is None:
        raise ValueError("docx_references_heading_missing")
    available: set[int] = set()
    bookmark_id = next_bookmark_id(root)
    for child in children[heading + 1:]:
        if child.tag != word_tag("p"):
            continue
        match = NUMERIC_REFERENCE_RE.match(element_text(child).strip())
        if not match:
            continue
        number = int(match.group("bracketed") or match.group("parenthesized") or match.group("plain"))
        if add_reference_bookmark(child, number, bookmark_id):
            available.add(number)
            bookmark_id += 1
    if not available:
        raise ValueError("docx_numbered_references_missing")
    fields = 0
    for block in children[:heading]:
        for paragraph in block.iter(word_tag("p")):
            fields += replace_citations(paragraph, available, superscript=superscript)
    if not fields:
        raise ValueError("docx_numeric_citation_fields_missing")
    rewrite_document_xml(docx_path, ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return len(available), fields


def validate_numeric_reference_fields(docx_path: Path, *, require_superscript: bool = False) -> tuple[int, int]:
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    bookmarks = len(re.findall(r'w:name="_Ref\d+"', xml))
    fields = len(re.findall(r"REF _Ref\d+ \\h", xml))
    if not bookmarks or not fields:
        raise ValueError(f"docx_reference_crosslinks_missing: bookmarks={bookmarks}, fields={fields}")
    if require_superscript:
        root = ET.fromstring(xml)
        superscript_runs = 0
        field_instruction_runs = 0
        for run in root.iter(word_tag("r")):
            instruction = "".join(node.text or "" for node in run.iter(word_tag("instrText")))
            align = run.find(f".//{word_tag('vertAlign')}")
            if align is not None and align.attrib.get(word_tag("val")) == "superscript":
                superscript_runs += 1
            if "REF _Ref" in instruction:
                field_instruction_runs += 1
                if align is None or align.attrib.get(word_tag("val")) != "superscript":
                    raise ValueError("docx_reference_field_not_superscript")
        if field_instruction_runs != fields or superscript_runs < fields * 5:
            raise ValueError(
                f"docx_reference_superscript_incomplete: fields={fields}, "
                f"instruction_runs={field_instruction_runs}, superscript_runs={superscript_runs}"
            )
    return bookmarks, fields
