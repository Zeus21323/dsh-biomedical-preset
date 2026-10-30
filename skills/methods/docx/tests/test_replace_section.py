import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

OFFICE = Path(__file__).resolve().parents[1] / 'scripts' / 'office'
sys.path.insert(0, str(OFFICE))
import replace_section as section
import edit_guard as guard
from build_article_docx import _normalize_settings_zoom


class SectionReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'original.docx'
        doc = Document()
        doc.add_heading('3.1 Scope', level=2)
        doc.add_paragraph('Original current content')
        doc.add_heading('3.2 Preserve', level=2)
        doc.add_paragraph('Latest user revision')
        p = doc.add_paragraph()
        p.alignment = 1
        equation = OxmlElement('m:oMath')
        r = OxmlElement('m:r'); t = OxmlElement('m:t'); t.text = 'x'
        r.append(t); equation.append(r); p._p.append(equation)
        p.add_run('(7)')
        doc.save(self.source)
        _normalize_settings_zoom(self.source)
        self.original = self.source.read_bytes()
        self.spec = {'heading': '3.1 Scope', 'next_heading': '3.2 Preserve',
                     'equation_template': 4, 'blocks': [{'text': 'New paragraph'}, {'text': 'Another paragraph'}]}
        self.spec_path = self.root / 'request.json'
        self.output = self.root / 'revised.docx'
        self.tx = self.root / 'transaction'

    def replace(self):
        self.spec_path.write_text(json.dumps(self.spec))
        return section.replace(self.source, self.spec_path, self.output, self.tx,
                               os.environ.get('EQUATION_SKILL_DIR'))

    def test_one_call_commits_and_can_restore(self):
        result = self.replace()
        record = json.loads((self.tx / 'record.json').read_text())
        self.assertEqual('committed', record['status'])
        self.assertEqual(str(self.output.resolve()), record['target'])
        self.assertEqual(self.output.read_bytes(), (self.tx / 'after.docx').read_bytes())
        self.assertEqual(self.original, self.source.read_bytes())
        self.assertTrue(result['verified'])
        guard.restore(self.tx)
        self.assertEqual(self.original, self.output.read_bytes())

    @unittest.skipUnless(os.environ.get('EQUATION_SKILL_DIR'), 'Set equation skill path for real converter integration')
    def test_real_latex_display_and_inline_with_receipt(self):
        self.spec['blocks'] = [{'runs': [{'text': 'Symbol '}, {'latex': r'\theta'}]},
                               {'latex': r'\theta(\mathbf z)\approx\sum_{j=1}^{p}\xi_j\phi_j(\mathbf z)=\boldsymbol{\Theta}(\mathbf z)\boldsymbol{\xi}'}]
        self.replace()
        original = guard.package(self.original)
        changed = guard.package(self.output.read_bytes())
        for name in original:
            if name != guard.DOC:
                self.assertEqual(original[name], changed[name], name)
        _, a = guard.body(original); _, b = guard.body(changed)
        self.assertEqual([guard.canonical(n) for n in a[2:]], [guard.canonical(n) for n in b[3:]])
        self.assertEqual(1, len(b[2].findall('.//m:oMath', section.NS)))
        self.assertEqual([], b[2].findall('.//w:t', section.NS))
        guard.restore(self.tx)
        self.assertEqual(self.original, self.output.read_bytes())

    def test_ambiguous_heading_fails_before_output(self):
        doc = Document(self.source); doc.add_heading('3.1 Scope', level=2); doc.save(self.source)
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            self.replace()
        self.assertFalse(self.output.exists())

    def test_bookmark_in_scope_cannot_be_deleted(self):
        doc = Document(self.source)
        mark = OxmlElement('w:bookmarkStart'); mark.set(qn('w:id'), '9'); mark.set(qn('w:name'), 'important')
        doc.paragraphs[1]._p.append(mark); doc.save(self.source)
        with self.assertRaisesRegex(ValueError, 'anchored'):
            self.replace()
        self.assertFalse(self.output.exists())

    def test_inherited_list_format_is_rejected(self):
        doc = Document(self.source); doc.paragraphs[1].style = 'List Number'; doc.save(self.source)
        with self.assertRaisesRegex(ValueError, 'nested structure'):
            self.replace()

    def test_validator_failure_prevents_delivery(self):
        with mock.patch.object(section.subprocess, 'run', return_value=mock.Mock(returncode=1, stdout='Invalid OMML', stderr='')):
            with self.assertRaisesRegex(ValueError, 'validation failed'):
                self.replace()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.original, self.source.read_bytes())
        self.assertFalse((self.tx / 'after.docx').exists())

    def test_candidate_scope_tampering_is_rejected(self):
        root, start, end, generated = section.build(self.original, self.spec)
        guard.prepare(self.source, self.tx)
        candidate = self.root / 'candidate.docx'
        guard.replace_text(self.tx, candidate, 1, 'Original current content', 'Unexpected edit')
        with self.assertRaisesRegex(ValueError, 'requested replacement'):
            guard.commit(self.tx, candidate, start, end, self.output, True, replacement=generated)
        self.assertFalse(self.output.exists())

    def test_missing_converter_fails_without_output(self):
        self.spec['blocks'] = [{'latex': 'x'}]
        self.spec_path.write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError, 'equation-skill'):
            section.replace(self.source, self.spec_path, self.output, self.tx)
        self.assertFalse(self.output.exists())

    def test_later_user_edits_cannot_be_undone(self):
        self.replace()
        self.output.write_bytes(self.output.read_bytes() + b'later edits')
        with self.assertRaisesRegex(ValueError, 'changed after commit'):
            guard.restore(self.tx)


if __name__ == '__main__':
    unittest.main()
