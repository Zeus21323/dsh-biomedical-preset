from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from tex_to_docx import validate_bibliography_source  # noqa: E402


class BibliographyCompatibilityTests(unittest.TestCase):
    def make_files(self, source_text: str) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source = root / "mainbody.tex"
        source.write_text(source_text, encoding="utf-8")
        bib = root / "references.bib"
        bib.write_text(
            "@article{verified2026, title={Verified title}, author={Author, A.}, year={2026}}\n",
            encoding="utf-8",
        )
        return temp, source, bib

    def test_allows_traditional_bibliography_commands_in_compatibility_mode(self) -> None:
        temp, source, bib = self.make_files(
            r"""\documentclass{article}
\begin{document}
正文没有结构化引用。
\bibliographystyle{plain}
\bibliography{references}
\end{document}
"""
        )
        with temp:
            self.assertEqual(set(), validate_bibliography_source(source, bib, False))

    def test_strict_numbered_mode_still_requires_citation_commands(self) -> None:
        temp, source, bib = self.make_files(
            r"""\documentclass{article}
\begin{document}
正文没有结构化引用。
\bibliography{references}
\end{document}
"""
        )
        with temp, self.assertRaisesRegex(SystemExit, "citation_commands_missing"):
            validate_bibliography_source(source, bib, True)

    def test_rejects_inline_thebibliography(self) -> None:
        temp, source, bib = self.make_files(
            r"""\documentclass{article}
\begin{document}
\begin{thebibliography}{9}
\bibitem{verified2026} A. Author.
\end{thebibliography}
\end{document}
"""
        )
        with temp, self.assertRaisesRegex(SystemExit, "manual_bibliography_forbidden"):
            validate_bibliography_source(source, bib, False)

    def test_keeps_verified_citation_key_validation(self) -> None:
        temp, source, bib = self.make_files(
            r"""\documentclass{article}
\begin{document}
正文\cite{missing2026}。
\bibliography{references}
\end{document}
"""
        )
        with temp, self.assertRaisesRegex(SystemExit, "citation_keys_missing_from_bib"):
            validate_bibliography_source(source, bib, False)

if __name__ == "__main__":
    unittest.main()
