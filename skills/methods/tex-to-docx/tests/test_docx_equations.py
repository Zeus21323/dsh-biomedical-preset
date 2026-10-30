from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from tex_to_docx import audit_docx_delivery, normalize_docx_line_spacing  # noqa: E402


CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
</Types>
"""

DOCUMENT_WITH_MATH = b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
 <w:body>
  <w:p><w:r><w:t>Equation:</w:t></w:r><m:oMath><m:r><m:t>x=1</m:t></m:r></m:oMath></w:p>
 </w:body>
</w:document>
"""

DOCUMENT_WITHOUT_MATH = b"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:body><w:p><w:r><w:t>Equation missing</w:t></w:r></w:p></w:body>
</w:document>
"""


def make_docx(path: Path, document_xml: bytes) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/styles.xml", b"<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'/>")


class DocxEquationAuditTests(unittest.TestCase):
    def test_line_spacing_rewrite_preserves_m_prefix_and_omml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "mainbody.tex"
            source.write_text(r"Equation \(x=1\).", encoding="utf-8")
            docx = root / "manuscript.docx"
            make_docx(docx, DOCUMENT_WITH_MATH)

            normalize_docx_line_spacing(docx, 1.5)
            report = audit_docx_delivery(docx, source)

            with zipfile.ZipFile(docx) as archive:
                rewritten = archive.read("word/document.xml")
            self.assertIn(b"xmlns:m=", rewritten)
            self.assertIn(b"<m:oMath", rewritten)
            self.assertNotIn(b"<ns0:oMath", rewritten)
            self.assertEqual(report["omml_equations"], 1)
            self.assertEqual(report["omml_prefix"], "m")

    def test_source_math_without_omml_blocks_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "mainbody.tex"
            source.write_text(r"Equation \(x=1\).", encoding="utf-8")
            docx = root / "manuscript.docx"
            make_docx(docx, DOCUMENT_WITHOUT_MATH)

            with self.assertRaisesRegex(SystemExit, "docx_omml_missing"):
                audit_docx_delivery(docx, source)


if __name__ == "__main__":
    unittest.main()
