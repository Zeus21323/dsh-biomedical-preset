"""Regression tests for ZIP/XML batch formula conversion."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import formula_inserter  # noqa: E402


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


DOCUMENT_XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W_NS}" xmlns:m="{M_NS}">
  <w:body>
    <w:p><w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr><w:r><w:t>前缀 </w:t></w:r><w:r><w:t>$x_i$</w:t></w:r><w:r><w:t> 后缀</w:t></w:r></w:p>
    <w:p><w:r><w:t>$$\\frac{{1}}{{x}}$$</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>表格 $y_j$</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    <w:sectPr/>
  </w:body>
</w:document>'''


class BatchConvertTests(unittest.TestCase):
    def test_replaces_inline_display_and_table_markers_without_dropping_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "markers.docx"
            with zipfile.ZipFile(docx_path, "w") as package:
                package.writestr("word/document.xml", DOCUMENT_XML.encode("utf-8"))

            def fake_converter(latex, display=False):
                omml = (
                    "<m:oMath><m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e>"
                    "<m:sub><m:r><m:t>i</m:t></m:r></m:sub>"
                    "</m:sSub></m:oMath>"
                )
                if display:
                    return f"<m:oMathPara>{omml}</m:oMathPara>"
                return omml

            with patch.object(formula_inserter, "latex_to_omml", side_effect=fake_converter):
                converted = formula_inserter._batch_convert_xml_markers(str(docx_path))
            self.assertEqual(converted, 3)

            with zipfile.ZipFile(docx_path) as package:
                root = etree.fromstring(package.read("word/document.xml"))

            text = "".join(node.text or "" for node in root.findall(f".//{{{W_NS}}}t"))
            self.assertIn("前缀 ", text)
            self.assertIn(" 后缀", text)
            self.assertIn("表格 ", text)
            self.assertNotIn("$", text)
            self.assertEqual(len(root.findall(f".//{{{M_NS}}}oMath")), 3)
            self.assertEqual(1, len(root.findall(f".//{{{M_NS}}}oMathPara")))
            self.assertFalse(any(
                item.find(f"{{{M_NS}}}lim") is not None
                for item in root.findall(f".//{{{M_NS}}}sSub")
            ))
            self.assertIsNotNone(root.find(f".//{{{W_NS}}}numPr"))

    def test_rejects_display_marker_mixed_with_prose(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            docx_path = Path(temp_dir) / "mixed-display.docx"
            xml = f'''<w:document xmlns:w="{W_NS}" xmlns:m="{M_NS}">
              <w:body><w:p><w:r><w:t>文字 $$x_i$$ 文字</w:t></w:r></w:p><w:sectPr/></w:body>
            </w:document>'''
            with zipfile.ZipFile(docx_path, "w") as package:
                package.writestr("word/document.xml", xml.encode("utf-8"))

            with self.assertRaisesRegex(RuntimeError, "Display formula markers"):
                formula_inserter._batch_convert_xml_markers(str(docx_path))


if __name__ == "__main__":
    unittest.main()
