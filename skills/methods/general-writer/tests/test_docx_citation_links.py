from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_docx_citation_links import validate_links  # noqa: E402


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(path: Path, body: str) -> None:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml.encode())


class DocxCitationLinkTests(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        source = root / "mainbody.tex"
        source.write_text(
            r"Evidence supports the claim \parencite{facione1990,kamysheva2021}.",
            encoding="utf-8",
        )
        return source

    def test_author_year_hyperlinks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = self.make_source(root)
            docx = root / "linked.docx"
            make_docx(
                docx,
                '<w:p><w:hyperlink w:anchor="ref-facione1990"><w:r><w:t>Facione, 1990</w:t></w:r></w:hyperlink>'
                '<w:hyperlink w:anchor="ref-kamysheva2021"><w:r><w:t>Kamysheva, 2021</w:t></w:r></w:hyperlink></w:p>'
                '<w:p><w:bookmarkStart w:id="1" w:name="ref-facione1990"/><w:r><w:t>Facione</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>'
                '<w:p><w:bookmarkStart w:id="2" w:name="ref-kamysheva2021"/><w:r><w:t>Kamysheva</w:t></w:r><w:bookmarkEnd w:id="2"/></w:p>',
            )
            report = validate_links(source, docx)
            self.assertEqual("passed", report["status"], report)
            self.assertEqual("citation-hyperlink", report["mode"])

    def test_plain_author_year_text_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = self.make_source(root)
            docx = root / "unlinked.docx"
            make_docx(docx, '<w:p><w:r><w:t>(Facione, 1990; Kamysheva, 2021)</w:t></w:r></w:p>')
            report = validate_links(source, docx)
            self.assertEqual("failed", report["status"])
            self.assertTrue(any("docx_citation_crosslinks_missing" in x for x in report["errors"]))

    def test_numeric_word_ref_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = self.make_source(root)
            docx = root / "numeric.docx"
            make_docx(
                docx,
                '<w:p><w:r><w:instrText> REF _Ref1 \\h \\* MERGEFORMAT </w:instrText></w:r></w:p>'
                '<w:p><w:bookmarkStart w:id="1" w:name="_Ref1"/><w:r><w:t>1. Reference</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>',
            )
            report = validate_links(source, docx)
            self.assertEqual("passed", report["status"], report)
            self.assertEqual("word-ref", report["mode"])


if __name__ == "__main__":
    unittest.main()
