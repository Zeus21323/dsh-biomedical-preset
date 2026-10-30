import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from lxml import etree as ET

OFFICE = Path(__file__).resolve().parents[1] / 'scripts' / 'office'
spec = importlib.util.spec_from_file_location('edit_guard', OFFICE / 'edit_guard.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class EditGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'current.docx'
        d = Document()
        d.styles['Heading 2'].font.size = Pt(19)
        d.styles['Heading 2'].paragraph_format.left_indent = Pt(17)
        d.add_heading('3.1 用户自定义标题', level=2)
        p = d.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(23)
        p.add_run('原始内容').bold = True
        p.add_run(' 需要保留的文字 ')
        d.add_heading('3.2 后续章节', level=2)
        d.add_paragraph('用户刚在 Word 中增加的结论')
        d.add_table(rows=1, cols=1).cell(0, 0).text = '未涉及的表格'
        d.sections[0].header.paragraphs[0].text = '用户页眉'
        # A field and automatic numbering outside the edit must survive exactly.
        p = d.add_paragraph('交叉引用')
        field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'REF user_bookmark')
        p._p.append(field)
        d.add_paragraph('编号项目', style='List Number')
        d.save(self.source)
        self.before = self.source.read_bytes()
        self.tx = self.root / 'transaction'
        g.prepare(self.source, self.tx)
        self.candidate = self.root / 'candidate.docx'
        g.replace_text(self.tx, self.candidate, 1, '原始内容', '更新内容')

    def mutate(self, part, transform):
        data = self.candidate.read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(self.candidate, 'w') as dst:
            for item in src.infolist():
                value = src.read(item.filename)
                dst.writestr(item, transform(value) if item.filename == part else value)

    def test_local_edit_preserves_current_user_changes_and_package(self):
        result = g.verify(self.tx, self.candidate, 1, 2)
        self.assertTrue(result['verified'])
        d = Document(self.candidate)
        self.assertIn('用户刚在 Word 中增加的结论', [p.text for p in d.paragraphs])
        self.assertEqual('更新内容 需要保留的文字 ', d.paragraphs[1].text)
        self.assertEqual(Pt(19), d.styles['Heading 2'].font.size)
        self.assertTrue(d.paragraphs[1].runs[0].bold)
        self.assertEqual(self.before, self.source.read_bytes())

    def test_outside_scope_text_change_is_blocked(self):
        self.mutate(g.DOC, lambda b: b.replace('后续章节'.encode(), '不应修改'.encode()))
        with self.assertRaisesRegex(ValueError, 'outside scope'):
            g.verify(self.tx, self.candidate, 1, 2)

    def test_styles_numbering_header_changes_are_blocked(self):
        for part in ['word/styles.xml', 'word/numbering.xml', 'word/header1.xml']:
            original = self.candidate.read_bytes()
            with self.subTest(part=part):
                self.mutate(part, lambda b: b + b'\n')
                with self.assertRaisesRegex(ValueError, 'Protected package part'):
                    g.verify(self.tx, self.candidate, 1, 2)
            self.candidate.write_bytes(original)

    def test_target_numbering_or_indent_changes_are_blocked(self):
        def change(data):
            root = g.xml(data); p = root.find('w:body', g.NS)[1]
            num = ET.SubElement(p.find('w:pPr', g.NS), qn('w:numPr'))
            ET.SubElement(num, qn('w:numId')).set(qn('w:val'), '1')
            return ET.tostring(root)
        self.mutate(g.DOC, change)
        with self.assertRaisesRegex(ValueError, 'formatting/numbering'):
            g.verify(self.tx, self.candidate, 1, 2)

    def test_user_save_since_read_blocks_commit(self):
        self.source.write_bytes(self.before + b'new user save')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            g.commit(self.tx, self.candidate, 1, 2)
        self.assertEqual(self.before + b'new user save', self.source.read_bytes())

    def test_restore_is_byte_exact(self):
        g.commit(self.tx, self.candidate, 1, 2)
        self.assertNotEqual(self.before, self.source.read_bytes())
        g.restore(self.tx)
        self.assertEqual(self.before, self.source.read_bytes())
        self.assertTrue((self.tx / 'after.docx').exists())

    def test_restore_does_not_overwrite_later_user_edits(self):
        g.commit(self.tx, self.candidate, 1, 2)
        newer = self.source.read_bytes() + b'newer user version'
        self.source.write_bytes(newer)
        with self.assertRaisesRegex(ValueError, 'changed after commit'):
            g.restore(self.tx)
        self.assertEqual(newer, self.source.read_bytes())

    def test_regeneration_from_old_markdown_is_blocked(self):
        d = Document(); d.add_heading('3.1 标题', level=2); d.add_paragraph('更新内容')
        d.add_heading('3.2 后续章节', level=2); d.save(self.candidate)
        with self.assertRaises(ValueError):
            g.verify(self.tx, self.candidate, 1, 2)

    def test_split_run_match_refused_without_output(self):
        output = self.root / 'split.docx'
        with self.assertRaisesRegex(ValueError, 'one text node'):
            g.replace_text(self.tx, output, 1, '原始内容 需要', 'replacement')
        self.assertFalse(output.exists())

    def test_new_output_does_not_overwrite_existing_file(self):
        output = self.root / 'existing.docx'; output.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            g.commit(self.tx, self.candidate, 1, 2, output=output)
        self.assertEqual(b'keep', output.read_bytes())
        self.assertEqual(self.before, self.source.read_bytes())

    def test_added_paragraph_requires_explicit_scope_review(self):
        def change(data):
            root = g.xml(data); b = root.find('w:body', g.NS)
            import copy
            b.insert(2, copy.deepcopy(b[1]))
            return ET.tostring(root)
        self.mutate(g.DOC, change)
        with self.assertRaisesRegex(ValueError, 'Paragraph count'):
            g.verify(self.tx, self.candidate, 1, 2)
        self.assertTrue(g.verify(self.tx, self.candidate, 1, 2, True)['verified'])

    def test_locked_destination_keeps_original_and_snapshots(self):
        with mock.patch.object(g.os, 'replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                g.commit(self.tx, self.candidate, 1, 2)
        self.assertEqual(self.before, self.source.read_bytes())
        self.assertEqual(self.before, (self.tx / 'before.docx').read_bytes())
        self.assertTrue((self.tx / 'after.docx').exists())
        # A failed replacement remains retryable without deleting the original.
        g.commit(self.tx, self.candidate, 1, 2)
        g.restore(self.tx)
        self.assertEqual(self.before, self.source.read_bytes())

    def test_cli_end_to_end(self):
        args = [sys.executable, str(OFFICE / 'edit_guard.py'), 'verify', str(self.tx),
                str(self.candidate), '--start', '1', '--end', '2']
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)['verified'])

    def test_builder_refuses_overwrite(self):
        source = self.root / 'article.json'
        source.write_text(json.dumps({'blocks': [{'type': 'paragraph', 'text': 'old MD'}]}))
        result = subprocess.run([sys.executable, str(OFFICE / 'build_article_docx.py'), str(source), str(self.source)], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Refusing to overwrite', result.stderr)
        self.assertEqual(self.before, self.source.read_bytes())


if __name__ == '__main__':
    unittest.main()
