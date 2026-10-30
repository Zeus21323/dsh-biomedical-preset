import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export_all


class NormalizeBibUrlsTest(unittest.TestCase):
    def test_default_formats_are_resolved_by_main(self) -> None:
        args = export_all.parse_args(["--survey-dir", "/tmp/work", "--language", "en"])

        self.assertIsNone(args.formats)
        self.assertIsNone(args.optional_formats)

    def test_default_pdf_failure_is_nonblocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work = Path(tmpdir)
            (work / "mainbody.tex").write_text(
                "\\begin{abstract}\nA short abstract.\n\\end{abstract}\n"
                "\\keywords{test}\n\\maketitle\n\\tableofcontents\n"
                "\\section{Intro}\nHello world.\n",
                encoding="utf-8",
            )

            def ok_result(format_name: str):
                return export_all.ExportResult(format_name, "OK", work / f"Survey.{format_name}")

            with mock.patch.object(export_all, "export_docx", return_value=ok_result("docx")):
                with mock.patch.object(export_all, "export_tex", return_value=ok_result("tex")):
                    with mock.patch.object(export_all, "export_pdf", return_value=export_all.ExportResult("pdf", "ERROR", message="dependency_not_found: latexmk")):
                        with mock.patch.object(export_all, "resolve_docx_template", return_value=(work / "template.docx", None)):
                            rc = export_all.main([
                                "--survey-dir",
                                str(work),
                                "--language",
                                "en",
                            ])

        self.assertEqual(rc, 0)

    def test_explicit_pdf_failure_is_blocking_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work = Path(tmpdir)
            (work / "mainbody.tex").write_text(
                "\\begin{abstract}\nA short abstract.\n\\end{abstract}\n"
                "\\keywords{test}\n\\maketitle\n\\tableofcontents\n"
                "\\section{Intro}\nHello world.\n",
                encoding="utf-8",
            )

            with mock.patch.object(export_all, "export_pdf", return_value=export_all.ExportResult("pdf", "ERROR", message="dependency_not_found: latexmk")):
                rc = export_all.main([
                    "--survey-dir",
                    str(work),
                    "--language",
                    "en",
                    "--formats",
                    "pdf",
                ])

        self.assertEqual(rc, 1)

    def test_markdown_format_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work = Path(tmpdir)
            (work / "mainbody.tex").write_text(
                "\\begin{abstract}\nA short abstract.\n\\end{abstract}\n"
                "\\keywords{test}\n\\maketitle\n\\tableofcontents\n"
                "\\section{Intro}\nHello world.\n",
                encoding="utf-8",
            )
            rc = export_all.main([
                "--survey-dir",
                str(work),
                "--language",
                "en",
                "--formats",
                "markdown",
            ])

        self.assertEqual(rc, 1)

    def test_relative_survey_dir_is_resolved_before_export_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            work = root / "relative_work"
            work.mkdir()
            (work / "mainbody.tex").write_text(
                "\\begin{abstract}\nA short abstract.\n\\end{abstract}\n"
                "\\keywords{test}\n\\maketitle\n\\tableofcontents\n"
                "\\section{Intro}\nHello world.\n",
                encoding="utf-8",
            )
            seen: list[Path] = []

            def fake_export_tex(survey_dir, *_args, **_kwargs):
                seen.append(survey_dir)
                return export_all.ExportResult("tex", "OK", survey_dir / "Survey.tex")

            with mock.patch.object(export_all, "export_tex", side_effect=fake_export_tex):
                with mock.patch.object(sys, "argv", [
                    "export_all.py",
                    "--survey-dir",
                    "relative_work",
                    "--language",
                    "en",
                    "--formats",
                    "tex",
                ]):
                    cwd = Path.cwd()
                    try:
                        import os
                        os.chdir(root)
                        rc = export_all.main()
                    finally:
                        os.chdir(cwd)

        self.assertEqual(rc, 0)
        self.assertEqual(seen, [work.resolve()])

    def test_removes_url_that_duplicates_doi(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bib = Path(tmpdir) / "refs.bib"
            bib.write_text(
                "\n".join([
                    "@article{jiang2025,",
                    "  title = {Perovskite solar cells},",
                    "  doi = {10.1038/s43586-024-00373-9},",
                    "  url = {https://doi.org/10.1038/s43586-024-00373-9},",
                    "}",
                    "",
                ]),
                encoding="utf-8",
            )

            warnings = export_all.normalize_bib_urls(bib)
            text = bib.read_text(encoding="utf-8")

        self.assertEqual(warnings, ["bib_url_removed_duplicate_doi: 1 entries"])
        self.assertIn("doi = {10.1038/s43586-024-00373-9}", text)
        self.assertNotIn("url =", text)
if __name__ == "__main__":
    unittest.main()
