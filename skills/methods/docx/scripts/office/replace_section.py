"""Inspect or replace a section body in the current DOCX, with an undo receipt.

Input is JSON content, never a new program. Headings and all other package parts
are retained. LaTeX uses the installed equation skill's tested converter.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile
from lxml import etree as ET
import edit_guard as guard

W = guard.W
M = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
NS = {'w': W, 'm': M}


def text(node):
    return ''.join(node.xpath('.//w:t/text() | .//m:t/text()', namespaces=NS))


def inspect(source):
    parts = guard.package(Path(source).read_bytes())
    _, body = guard.body(parts)
    # Compact output avoids dumping thousands of inherited namespace declarations.
    return {'source': str(Path(source).resolve()), 'sha256': guard.digest(Path(source).read_bytes()),
            'blocks': [{'index': i, 'kind': ET.QName(n).localname,
                        'text': text(n),
                        'style': n.xpath('string(w:pPr/w:pStyle/@w:val)', namespaces=NS),
                        'math_count': len(n.findall('.//m:oMath', NS)),
                        'display_template': bool(n.findall('m:oMath', NS) or n.findall('m:oMathPara', NS)) and not ''.join(n.xpath('.//w:t/text()', namespaces=NS)).strip('0123456789()（）. \t')}
                       for i, n in enumerate(body)]}


def boundary(body, heading):
    if not isinstance(heading, str) or not heading:
        raise ValueError('Use an exact heading text from inspect')
    hits = [i for i, n in enumerate(body) if n.tag == f'{{{W}}}p' and text(n) == heading]
    if len(hits) != 1:
        raise ValueError(f'Heading must match exactly once: {heading!r}')
    return hits[0]


def converter(path):
    if not path:
        raise ValueError('Formula input needs --equation-skill pointing to the installed equation skill')
    script = Path(path).resolve() / 'scripts' / 'latex_omml_converter.py'
    spec = importlib.util.spec_from_file_location('section_equation_converter', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.latex_to_omml


def paragraph(template):
    p = ET.Element(f'{{{W}}}p')
    props = template.find('w:pPr', NS)
    if props is not None:
        p.append(copy.deepcopy(props))
    return p


def body_run(template, value):
    if not isinstance(value, str) or any(c in value for c in '\r\n\t'):
        raise ValueError('Text must be a string without paragraph breaks/tabs; use separate blocks')
    r = ET.Element(f'{{{W}}}r')
    # Reuse the selected paragraph's first ordinary text-run formatting.
    original = next((n for n in template.findall('w:r', NS) if n.find('w:t', NS) is not None), None)
    if original is not None and original.find('w:rPr', NS) is not None:
        r.append(copy.deepcopy(original.find('w:rPr', NS)))
    t = ET.SubElement(r, f'{{{W}}}t')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = value
    return r


def structured_paragraph(node, parts):
    """Reject inherited heading/list properties as well as direct properties."""
    props = [node.find('w:pPr', NS)]
    styles = guard.xml(parts['word/styles.xml']) if 'word/styles.xml' in parts else None
    by_id = {} if styles is None else {n.get(f'{{{W}}}styleId'): n for n in styles.findall('w:style', NS)}
    style_id = node.xpath('string(w:pPr/w:pStyle/@w:val)', namespaces=NS)
    if not style_id and styles is not None:
        defaults = styles.xpath('w:style[@w:type="paragraph" and @w:default="1"]/@w:styleId', namespaces=NS)
        style_id = defaults[0] if defaults else ''
    seen = set()
    while style_id in by_id and style_id not in seen:
        seen.add(style_id)
        style = by_id[style_id]
        props.append(style.find('w:pPr', NS))
        style_id = style.xpath('string(w:basedOn/@w:val)', namespaces=NS)
    for prop in props:
        if prop is None:
            continue
        if prop.find('w:sectPr', NS) is not None:
            return True
        outline = prop.find('w:outlineLvl', NS)
        if outline is not None and outline.get(f'{{{W}}}val') != '9':
            return True
        number = prop.find('w:numPr', NS)
        if number is not None:
            num_id = number.find('w:numId', NS)
            if num_id is None or num_id.get(f'{{{W}}}val') != '0':
                return True
    return False


def build(before, spec, equation_skill=None):
    if not isinstance(spec, dict) or set(spec) - {'heading', 'next_heading', 'body_template', 'equation_template', 'blocks'}:
        raise ValueError('Unknown section specification fields')
    parts = guard.package(before)
    root, body = guard.body(parts)
    start = boundary(body, spec.get('heading')) + 1
    end = boundary(body, spec.get('next_heading'))
    if start >= end:
        raise ValueError('Section body must be nonempty and end after its heading')
    old = list(body[start:end])
    if any(n.tag != f'{{{W}}}p' for n in old):
        raise ValueError('Section contains tables or non-paragraph blocks; use a separately scoped workflow')
    # Removing anchors/fields/revisions may invalidate references elsewhere.
    if any(n.xpath('.//w:bookmarkStart | .//w:bookmarkEnd | .//w:fldChar | .//w:fldSimple | .//w:hyperlink | .//w:ins | .//w:del | .//w:commentRangeStart | .//w:commentRangeEnd | .//w:commentReference | .//w:sectPr | .//w:drawing | .//w:object | .//w:footnoteReference | .//w:endnoteReference', namespaces=NS) for n in old):
        raise ValueError('Scope contains anchored/linked content; preserve it with a separately scoped edit')
    if any(structured_paragraph(n, parts) for n in old):
        raise ValueError('Scope contains heading/list/section properties; do not erase nested structure')
    index = spec.get('body_template', start)
    if type(index) is not int or not start <= index < end:
        raise ValueError('body_template must be a paragraph index inside the replaced body')
    template = body[index]
    if template.find('w:pPr/w:numPr', NS) is not None:
        raise ValueError('Body template is numbered; refusing to replicate list numbering')
    blocks = spec.get('blocks')
    if not isinstance(blocks, list) or not blocks:
        raise ValueError('blocks must be a nonempty list')
    convert = None

    def math(latex):
        nonlocal convert
        if not isinstance(latex, str) or not latex.strip():
            raise ValueError('latex must be a nonempty string')
        if convert is None:
            convert = converter(equation_skill)
        result = guard.xml(convert(latex, display=False).encode())
        if result.tag != f'{{{M}}}oMath':
            raise ValueError('Converter did not return native OMML')
        return result

    generated = []
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError('Each block must be an object')
        if set(block) == {'latex'}:
            eq = spec.get('equation_template')
            if type(eq) is not int or not 0 <= eq < len(body):
                raise ValueError('Display formula requires equation_template from inspect')
            source = body[eq]
            if source.tag != f'{{{W}}}p' or not (source.findall('m:oMath', NS) or source.findall('m:oMathPara', NS)):
                raise ValueError('equation_template must contain a direct native equation')
            if structured_paragraph(source, parts):
                raise ValueError('Equation template has heading/list/section properties')
            ordinary = ''.join(source.xpath('.//w:t/text()', namespaces=NS))
            if ordinary.strip('0123456789()（）. \t'):
                raise ValueError('Equation template must be a standalone formula paragraph')
            p = paragraph(source)
            p.append(math(block['latex']))  # No old equation number or text copied.
        else:
            if set(block) == {'text'}:
                runs = [{'text': block['text']}]
            elif set(block) == {'runs'} and isinstance(block['runs'], list) and block['runs']:
                runs = block['runs']
            else:
                raise ValueError('Block must contain text, runs, or latex')
            p = paragraph(template)
            for run in runs:
                if isinstance(run, dict) and set(run) == {'text'}:
                    p.append(body_run(template, run['text']))
                elif isinstance(run, dict) and set(run) == {'latex'}:
                    p.append(math(run['latex']))
                else:
                    raise ValueError('Run must contain text or latex')
        generated.append(p)
    for n in old:
        body.remove(n)
    for i, n in enumerate(generated):
        body.insert(start + i, n)
    return root, start, end, generated


def replace(source, spec_path, output, transaction, equation_skill=None):
    started = time.perf_counter()
    source, output, transaction = Path(source).resolve(), Path(output).resolve(), Path(transaction).resolve()
    if output == source:
        raise ValueError('Section replacement requires a new output path; original stays untouched')
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    guard.prepare(source, transaction)
    _, before = guard.load(transaction)
    root, start, end, generated = build(before, spec, equation_skill)
    candidate = transaction / 'candidate.docx'
    with zipfile.ZipFile(transaction / 'before.docx') as src, zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, ET.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True) if item.filename == guard.DOC else src.read(item.filename))
    guard.verify(transaction, candidate, start, end, True, replacement=generated)
    validation = subprocess.run([sys.executable, str(Path(__file__).with_name('validate.py')), str(candidate)],
                                capture_output=True, text=True, timeout=120)
    (transaction / 'validation.log').write_text(validation.stdout + validation.stderr, encoding='utf-8')
    if validation.returncode:
        raise ValueError(f'DOCX validation failed; original/output untouched. See {transaction / "validation.log"}')
    report = guard.commit(transaction, candidate, start, end, output, True, replacement=generated)
    (transaction / 'request.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    return {**report, 'output': str(output), 'transaction': str(transaction),
            'backup': str(transaction / 'before.docx'), 'receipt': str(transaction / 'record.json'),
            'restore_command': [sys.executable, str(Path(guard.__file__).resolve()), 'restore', str(transaction)],
            'elapsed_seconds': round(time.perf_counter() - started, 3)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('inspect'); p.add_argument('source')
    p = sub.add_parser('replace'); p.add_argument('source'); p.add_argument('spec_path'); p.add_argument('output'); p.add_argument('transaction'); p.add_argument('--equation-skill')
    args = vars(parser.parse_args()); command = args.pop('command')
    try:
        print(json.dumps(globals()[command](**args), ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError, ImportError, ET.XMLSyntaxError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Replacement blocked: {exc}\n')


if __name__ == '__main__':
    main()
