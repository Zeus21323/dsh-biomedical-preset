"""Snapshot, inspect and verify a scoped DOCX edit; no document regeneration.

Uses body-child indices (including tables), not paragraph numbers or visible numbering.
Only word/document.xml may change. Rich edits requiring new package parts need a
separate reviewed workflow; this guard deliberately refuses them.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
from lxml import etree as ET

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
DOC = 'word/document.xml'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate ZIP entries')
        return {n: z.read(n) for n in z.namelist()}


def xml(data):
    return ET.fromstring(data, ET.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False))


def canonical(node):
    return b'' if node is None else ET.tostring(node, method='c14n')


def body(parts):
    root = xml(parts[DOC])
    b = root.find('w:body', NS)
    if b is None:
        raise ValueError('Missing document body')
    return root, b


def inventory(parts):
    _, b = body(parts)
    styles = xml(parts['word/styles.xml']) if 'word/styles.xml' in parts else None
    style_map = {} if styles is None else {
        s.get('{%s}styleId' % W): s for s in styles.findall('w:style', NS)
    }
    result = []
    for i, node in enumerate(b):
        ppr = node.find('w:pPr', NS)
        sid = node.find('w:pPr/w:pStyle', NS)
        sid = None if sid is None else sid.get('{%s}val' % W)
        chain, seen = [], set()
        current = sid
        while current in style_map and current not in seen:
            seen.add(current)
            s = style_map[current]
            chain.append(ET.tostring(s, encoding='unicode'))
            parent = s.find('w:basedOn', NS)
            current = None if parent is None else parent.get('{%s}val' % W)
        result.append({'index': i, 'tag': ET.QName(node).localname,
                       'text': ''.join(node.itertext()) if ET.QName(node).localname == 'sectPr' else ''.join(node.xpath('.//w:t/text()', namespaces=NS)),
                       'paragraph_properties': '' if ppr is None else ET.tostring(ppr, encoding='unicode'),
                       'style_id': sid, 'style_chain': chain})
    return result


def prepare(source, transaction):
    source, transaction = Path(source).resolve(), Path(transaction).resolve()
    data = source.read_bytes()
    parts = package(data)
    inv = inventory(parts)
    transaction.mkdir(parents=True, exist_ok=False)
    (transaction / 'before.docx').write_bytes(data)
    record = {'source': str(source), 'before_sha256': digest(data)}
    (transaction / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    (transaction / 'inventory.json').write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding='utf-8')
    # Preserve numbering definitions for inspection, including overrides/restarts.
    (transaction / 'numbering.xml').write_bytes(parts.get('word/numbering.xml', b'<numbering/>'))
    return record


def load(transaction):
    transaction = Path(transaction)
    record = json.loads((transaction / 'record.json').read_text(encoding='utf-8'))
    before = (transaction / 'before.docx').read_bytes()
    if digest(before) != record['before_sha256']:
        raise ValueError('Snapshot changed')
    return record, before


def verify(transaction, candidate, start, end, allow_paragraph_count_change=False, *, replacement=None):
    record, before = load(transaction)
    if digest(Path(record['source']).read_bytes()) != record['before_sha256']:
        raise ValueError('Source changed since snapshot; read the current document and prepare again')
    candidate_data = Path(candidate).read_bytes()
    original, changed = package(before), package(candidate_data)
    if original.keys() != changed.keys():
        raise ValueError('Package parts added or removed')
    for name in original:
        if name != DOC and original[name] != changed[name]:
            raise ValueError('Protected package part changed: ' + name)
    root_a, a = body(original)
    root_b, b = body(changed)
    if not 0 <= start < end <= len(a):
        raise ValueError('Invalid half-open body-child range')
    if any(n.tag != '{%s}p' % W for n in a[start:end]):
        raise ValueError('Scope must contain only top-level paragraphs; tables/sections require another workflow')
    new_end = len(b) - (len(a) - end)
    if new_end < start:
        raise ValueError('Candidate deleted content outside scope')
    if [canonical(n) for n in a[:start]] != [canonical(n) for n in b[:start]] or \
       [canonical(n) for n in a[end:]] != [canonical(n) for n in b[new_end:]]:
        raise ValueError('Content or formatting outside scope changed')
    old_scope, new_scope = list(a[start:end]), list(b[start:new_end])
    if any(n.tag != '{%s}p' % W for n in new_scope):
        raise ValueError('Candidate scope contains non-paragraph blocks')
    if replacement is not None:
        # Only the deterministic section builder supplies these nodes. This is
        # not a CLI override or a relaxation of outside-scope preservation.
        if [canonical(n) for n in new_scope] != [canonical(n) for n in replacement]:
            raise ValueError('Candidate differs from the requested replacement')
    else:
        props = lambda nodes: [canonical(n.find('w:pPr', NS)) for n in nodes]
        if len(old_scope) == len(new_scope):
            if props(old_scope) != props(new_scope):
                raise ValueError('Target paragraph formatting/numbering changed')
        elif not allow_paragraph_count_change:
            raise ValueError('Paragraph count changed; explicitly review scope and paragraph formatting')
        elif not set(props(new_scope)).issubset(set(props(old_scope))):
            raise ValueError('New paragraphs must reuse original scope paragraph formatting')
        # A content-only edit cannot introduce a new character-formatting recipe.
        old_runs = {canonical(r.find('w:rPr', NS)) for n in old_scope for r in n.findall('.//w:r', NS)}
        for n in new_scope:
            for r in n.findall('.//w:r', NS):
                if canonical(r.find('w:rPr', NS)) not in old_runs:
                    raise ValueError('New character formatting introduced in scope')
    # Compare document root metadata and any non-body siblings as well.
    for r, target in [(root_a, a), (root_b, b)]:
        for n in list(target):
            target.remove(n)
    if canonical(root_a) != canonical(root_b):
        raise ValueError('Document envelope changed')
    return {'verified': True, 'start': start, 'end': end, 'candidate_end': new_end,
            'before_sha256': record['before_sha256'], 'after_sha256': digest(candidate_data),
            'scope': 'paragraph content; outside scope and all other package parts preserved'}


def replace_text(transaction, output, index, old, new):
    """Small text edits preserve every node/property except the selected w:t value."""
    _, before = load(transaction)
    parts = package(before)
    root, b = body(parts)
    if not 0 <= index < len(b) or b[index].tag != '{%s}p' % W:
        raise ValueError('Select a top-level paragraph from inventory.json')
    if not old or any(c in new for c in '\n\r\t'):
        raise ValueError('Use a rich XML edit for paragraph breaks or tabs')
    matches = [(n, n.text.count(old)) for n in b[index].findall('.//w:t', NS) if n.text and old in n.text]
    if sum(count for _, count in matches) != 1:
        raise ValueError('Text must match exactly once in one text node; inspect split runs before editing')
    node = matches[0][0]
    node.text = node.text.replace(old, new, 1)
    node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    with Path(output).open('xb') as f, zipfile.ZipFile(io.BytesIO(before)) as source, zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as dest:
        for item in source.infolist():
            dest.writestr(item, ET.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True) if item.filename == DOC else parts[item.filename])


def atomic_write(path, data):
    fd, temp = tempfile.mkstemp(prefix='.docx-edit-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def commit(transaction, candidate, start, end, output=None, allow_paragraph_count_change=False, *, replacement=None):
    transaction = Path(transaction)
    record, _ = load(transaction)
    if record.get('status') in ('committed', 'restored'):
        raise ValueError('Transaction already committed')
    report = verify(transaction, candidate, start, end, allow_paragraph_count_change, replacement=replacement)
    data = Path(candidate).read_bytes()
    if digest(data) != report['after_sha256']:
        raise ValueError('Candidate changed during verification')
    target = Path(output).resolve() if output else Path(record['source'])
    if target != Path(record['source']) and target.exists():
        raise FileExistsError(f'Output already exists: {target}')
    if target == transaction.resolve() or transaction.resolve() in target.parents:
        raise ValueError('Output must be outside the transaction directory')
    # Store the verified candidate and receipt before touching the destination.
    (transaction / 'after.docx').write_bytes(data)
    record.update({'target': str(target), 'committed_sha256': digest(data), 'status': 'prepared', 'verification': report})
    (transaction / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    if digest(Path(record['source']).read_bytes()) != record['before_sha256']:
        raise ValueError('Source changed before commit')
    if target == Path(record['source']):
        atomic_write(target, data)
    else:
        with target.open('xb') as f:
            f.write(data)
    record['status'] = 'committed'
    (transaction / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return report


def restore(transaction):
    transaction = Path(transaction)
    record, before = load(transaction)
    if record.get('status') not in ('committed', 'prepared'):
        raise ValueError('No completed commit to restore')
    target = Path(record['target'])
    if digest(target.read_bytes()) != record['committed_sha256']:
        raise ValueError('Document changed after commit; do not overwrite newer edits')
    atomic_write(target, before)
    record['status'] = 'restored'
    (transaction / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    return {'restored': str(target), 'sha256': digest(before)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare'); p.add_argument('source'); p.add_argument('transaction')
    p = commands.add_parser('replace-text'); p.add_argument('transaction'); p.add_argument('output'); p.add_argument('--index', type=int, required=True); p.add_argument('--old', required=True); p.add_argument('--new', required=True)
    for command in ['verify', 'commit']:
        p = commands.add_parser(command); p.add_argument('transaction'); p.add_argument('candidate'); p.add_argument('--start', type=int, required=True); p.add_argument('--end', type=int, required=True); p.add_argument('--allow-paragraph-count-change', action='store_true')
        if command == 'commit':
            p.add_argument('--output', help='New output path; omitted means replace original after verification')
    p = commands.add_parser('restore'); p.add_argument('transaction')
    args = vars(parser.parse_args()); command = args.pop('command').replace('-', '_')
    try:
        result = globals()[command](**args)
        print(json.dumps(result or {'ok': True}, ensure_ascii=False, indent=2))
    except (ValueError, OSError, zipfile.BadZipFile, ET.XMLSyntaxError) as exc:
        parser.exit(1, f'Edit blocked: {exc}\n')


if __name__ == '__main__':
    main()
