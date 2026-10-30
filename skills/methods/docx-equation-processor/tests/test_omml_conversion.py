import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_docx_raw import build_docx, verify_docx
from latex_omml_converter import (
    M_NS,
    find_known_omml_schema_issues,
    latex_to_omml,
    normalize_omml_xml,
)


class OmmlConversionTests(unittest.TestCase):
    def test_validator_rejects_lim_as_subscript(self):
        xml = (
            f'<m:oMath xmlns:m="{M_NS}"><m:sSub><m:e/>'
            '<m:lim><m:r><m:t>i</m:t></m:r></m:lim>'
            '</m:sSub></m:oMath>'
        )
        self.assertIn(
            "<m:sSub> contains <m:lim>; expected <m:sub>",
            find_known_omml_schema_issues(xml),
        )

    def test_normalizer_repairs_legacy_subscript(self):
        xml = (
            f'<m:oMath xmlns:m="{M_NS}"><m:sSub><m:e/>'
            '<m:lim><m:r><m:t>i</m:t></m:r></m:lim>'
            '</m:sSub></m:oMath>'
        )
        normalized = normalize_omml_xml(xml)
        self.assertEqual([], find_known_omml_schema_issues(normalized))
        self.assertIn("<m:sub>", normalized)

    def test_latex_scripts_generate_valid_omml(self):
        for latex in ("x_i", "x_i^2", r"\sum_{i=1}^{n} x_i"):
            with self.subTest(latex=latex):
                omml = latex_to_omml(latex)
                self.assertEqual([], find_known_omml_schema_issues(omml))

    def test_raw_builder_and_verifier_accept_valid_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "equations.docx"
            build_docx([("sum", r"\sum_{i=1}^{n} x_i")], output)
            result = verify_docx(output)
            self.assertTrue(result["valid"], result)
            self.assertEqual([], result["schema_issues"])

    def test_verifier_rejects_bad_case_structure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            good = Path(temp_dir) / "good.docx"
            bad = Path(temp_dir) / "bad.docx"
            build_docx([("subscript", "x_i")], good)
            with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, "w") as target:
                for item in source.infolist():
                    data = source.read(item.filename)
                    if item.filename == "word/document.xml":
                        data = data.replace(b"<m:sub>", b"<m:lim>").replace(
                            b"</m:sub>", b"</m:lim>"
                        )
                    target.writestr(item, data)

            result = verify_docx(bad)
            self.assertFalse(result["valid"])
            self.assertIn("<m:sSub> contains <m:lim>", result["error"])


if __name__ == "__main__":
    unittest.main()
