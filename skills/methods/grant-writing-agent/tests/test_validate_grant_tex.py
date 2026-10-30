from pathlib import Path
import tempfile
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from scripts.validate_grant_tex import audit


class GrantTexAuditTest(unittest.TestCase):
    def audit_text(self, text: str, heading_text: str | None = None) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grant-application.tex"
            path.write_text(text, encoding="utf-8")
            if heading_text is None:
                return audit(path)
            docx_path = Path(tmp) / "grant-application.docx"
            document = Document()
            style = document.styles["Heading 1"]
            p_pr = style.element.get_or_add_pPr()
            num_pr = OxmlElement("w:numPr")
            level = OxmlElement("w:ilvl")
            level.set(qn("w:val"), "0")
            num_id = OxmlElement("w:numId")
            num_id.set(qn("w:val"), "1")
            num_pr.extend((level, num_id))
            p_pr.append(num_pr)
            document.add_heading(heading_text, level=1)
            document.save(docx_path)
            return audit(path, docx_path)

    def test_accepts_starred_real_headings_and_body_metadata(self) -> None:
        result = self.audit_text(
            r"""\documentclass{ctexart}
\begin{document}
\textbf{项目类别：}青年科学基金项目\par
\section*{摘要}
\subsection*{研究意义}
\end{document}
"""
        )
        self.assertEqual("passed", result["status"])

    def test_rejects_metadata_heading(self) -> None:
        result = self.audit_text(
            r"""\documentclass{ctexart}
\section*{项目类别：青年科学基金项目}
"""
        )
        self.assertIn("metadata_used_as_heading", {item["code"] for item in result["errors"]})

    def test_rejects_unstarred_and_manual_heading_number(self) -> None:
        result = self.audit_text(
            r"""\documentclass{ctexart}
\section{1.3. 一、摘要}
"""
        )
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("automatic_heading_numbering_forbidden", codes)
        self.assertIn("manual_heading_number", codes)

    def test_rejects_chinese_manual_heading_number(self) -> None:
        result = self.audit_text(
            r"""\documentclass{ctexart}
\section*{一、立项依据}
"""
        )
        self.assertIn("manual_heading_number", {item["code"] for item in result["errors"]})

    def test_rejects_markdown_heading(self) -> None:
        result = self.audit_text("\\documentclass{ctexart}\n# 一、摘要\n")
        self.assertIn("markdown_heading_found", {item["code"] for item in result["errors"]})

    def test_accepts_plain_docx_heading_with_style_numbering(self) -> None:
        result = self.audit_text(
            "\\documentclass{ctexart}\n\\section*{立项依据}\n",
            heading_text="立项依据",
        )
        self.assertEqual("passed", result["status"])

    def test_rejects_manual_docx_heading_with_style_numbering(self) -> None:
        result = self.audit_text(
            "\\documentclass{ctexart}\n\\section*{立项依据}\n",
            heading_text="一、立项依据",
        )
        self.assertIn("docx_heading_double_number", {item["code"] for item in result["errors"]})


if __name__ == "__main__":
    unittest.main()
