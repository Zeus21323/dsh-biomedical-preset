import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bibliography_library


class BibtexUrlPolicyTest(unittest.TestCase):
    def test_drops_url_that_duplicates_doi(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "jiang2025",
            "title": "Perovskite solar cells",
            "authors": ["Jiang Hao", "Kim Peter"],
            "journal": "Nature Reviews Methods Primers",
            "year": "2025",
            "doi": "10.1038/s43586-024-00373-9",
            "url": "https://doi.org/10.1038/s43586-024-00373-9",
        })

        self.assertIn("doi = {10.1038/s43586-024-00373-9}", entry)
        self.assertNotIn("url =", entry)


class BibtexAuthorPolicyTest(unittest.TestCase):
    def test_writes_family_initial_names_with_comma(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "han2025",
            "title": "Perovskite solar cells",
            "authors": ["Han J", "Park K", "Tan S", "Vaynzof Y", "Xue J"],
            "journal": "Nature Reviews Methods Primers",
            "year": "2025",
        })

        self.assertIn("author = {Han, J and Park, K and Tan, S and Vaynzof, Y and Xue, J}", entry)

    def test_writes_lowercase_particle_family_names_with_comma(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "vandorst2026",
            "title": "Genotoxic pks + E. coli",
            "authors": ["Josie van Dorst", "Nicole Taylor"],
            "journal": "Journal of Cystic Fibrosis",
            "year": "2026",
        })

        self.assertIn("author = {van Dorst, Josie and Nicole Taylor}", entry)


class MetadataRichTextSanitizationTest(unittest.TestCase):
    def test_normalize_paper_fields_strips_jats_title_markup(self) -> None:
        record = bibliography_library.normalize_paper_fields({
            "title": "Gut Microbiota‐Induced <scp>CTLA4</scp> Expression on <scp>CD8</scp> <sup>+</sup> T Cells",
            "authors": ["Meidie Cheng"],
            "journal": "Immunology",
            "year": "2026",
        })

        self.assertEqual(
            record["title"],
            "Gut Microbiota‐Induced CTLA4 Expression on CD8+ T Cells",
        )

    def test_export_bib_strips_html_entity_markup(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "cheng2026",
            "title": "Gut Microbiota-Induced &lt;scp&gt;CD8&lt;/scp&gt; &lt;sup&gt;+&lt;/sup&gt; T Cells",
            "authors": ["Meidie Cheng"],
            "journal": "Immunology",
            "year": "2026",
        })

        self.assertIn("title = {{Gut Microbiota-Induced CD8+ T Cells}}", entry)
        self.assertNotIn("<scp>", entry)
        self.assertNotIn("<sup>", entry)

    def test_export_bib_strips_italic_sup_markup(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "lin2026",
            "title": "Targeting <i>SPP1</i> <sup>+</sup> TAMs associated with liver metastasis",
            "authors": ["Y Lin"],
            "journal": "Journal for ImmunoTherapy of Cancer",
            "year": "2026",
        })

        self.assertIn("title = {{Targeting SPP1+ TAMs associated with liver metastasis}}", entry)

    def test_raw_bibtex_text_fields_are_sanitized(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "raw2026",
            "doi": "10.1111/imm.13999",
            "bibtex": (
                "@article{raw2026,\n"
                "  title = {Targeting <i>SPP1</i> <sup>+</sup> TAMs},\n"
                "  journal = {Immunology},\n"
                "  year = {2026},\n"
                "}\n"
            ),
        })

        self.assertIn("title = {Targeting SPP1+ TAMs}", entry)
        self.assertNotIn("<i>", entry)
        self.assertNotIn("<sup>", entry)


class BibtexPagesPolicyTest(unittest.TestCase):
    def test_drops_article_identifier_pages(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "yun2025",
            "title": "Dimensional engineering of interlayer",
            "authors": ["Yun Y", "Chang Q"],
            "journal": "Science Advances",
            "year": "2025",
            "volume": "11",
            "pages": "eadp3112",
        })

        self.assertIn("volume = {11}", entry)
        self.assertNotIn("pages =", entry)
        self.assertNotIn("eadp3112", entry)

    def test_drops_article_identifier_pages_from_raw_bibtex(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "yun2025",
            "doi": "10.1126/sciadv.adp3112",
            "bibtex": (
                "@article{yun2025,\n"
                "  title = {Dimensional engineering},\n"
                "  pages = {eadp3112},\n"
                "  year = {2025},\n"
                "}\n"
            ),
        })

        self.assertNotIn("pages =", entry)
        self.assertNotIn("eadp3112", entry)


class BibtexEntryTypePolicyTest(unittest.TestCase):
    def test_arxiv_records_export_as_online(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "lee2024",
            "title": "Multimodal Reasoning with Multimodal Knowledge Graph",
            "authors": ["Lee J", "Wang Y", "Li J"],
            "entry_type": "article",
            "journal": "arXiv",
            "year": "2024",
            "url": "https://arxiv.org/abs/2401.12345",
        })

        self.assertTrue(entry.startswith("@online{lee2024,"))
        self.assertIn("organization = {arXiv}", entry)
        self.assertNotIn("journal = {arXiv}", entry)

    def test_conference_records_export_as_inproceedings(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "mondal2024",
            "title": "KAM-CoT",
            "authors": ["Mondal D", "Modi S", "Panda S"],
            "journal": "Proceedings of the AAAI Conference on Artificial Intelligence",
            "year": "2024",
        })

        self.assertTrue(entry.startswith("@inproceedings{mondal2024,"))
        self.assertIn("booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence}", entry)
        self.assertNotIn("journal =", entry)

    def test_conference_venue_beats_arxiv_url(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "hu2024",
            "title": "GRAG: Graph Retrieval-Augmented Generation",
            "authors": ["Hu Y", "Lei Z", "Zhang Z"],
            "journal": "NAACL",
            "year": "2024",
            "pages": "101-112",
            "url": "https://arxiv.org/abs/2401.12345",
        })

        self.assertTrue(entry.startswith("@inproceedings{hu2024,"))
        self.assertIn("booktitle = {NAACL}", entry)
        self.assertIn("pages = {101-112}", entry)

    def test_acm_computing_surveys_stays_journal(self) -> None:
        entry = bibliography_library.build_minimal_bibtex({
            "bib_key": "liang2024",
            "title": "A Survey of Multi-modal Knowledge Graphs: Technologies and Trends",
            "authors": ["Liang W", "Meo P D", "Tang Y"],
            "journal": "ACM Computing Surveys",
            "year": "2024",
            "volume": "56",
            "number": "11",
            "pages": "1-38",
        })

        self.assertTrue(entry.startswith("@article{liang2024,"))
        self.assertIn("journal = {ACM Computing Surveys}", entry)
        self.assertIn("pages = {1-38}", entry)


class ExportBibMetadataGateTest(unittest.TestCase):
    def _run_export_bib(self, records: list[dict], allow_incomplete: bool = False) -> int:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            library = tmp / "papers.json"
            output = tmp / "references.bib"
            library.write_text(json.dumps(records), encoding="utf-8")
            ns = SimpleNamespace(
                library=str(library),
                output=str(output),
                keys="",
                bbl_file="",
                tex_file="",
                allow_incomplete=allow_incomplete,
                warn_limit=10,
                diagnostics_stdout=True,
            )
            return bibliography_library.cmd_export_bib(ns)

    def test_export_bib_refuses_missing_volume_pages_for_final_export(self) -> None:
        code = self._run_export_bib(
            [
                {
                    "bib_key": "zhang2024",
                    "title": "Supply chain finance",
                    "authors": ["Zhang San"],
                    "journal": "管理世界",
                    "year": "2024",
                    "entry_type": "article",
                }
            ]
        )

        self.assertEqual(code, bibliography_library.E_STRUCTURE)

    def test_export_bib_allows_unresolvable_missing_volume_pages(self) -> None:
        code = self._run_export_bib(
            [
                {
                    "bib_key": "zhang2024",
                    "title": "Supply chain finance",
                    "authors": ["Zhang San"],
                    "journal": "管理世界",
                    "year": "2024",
                    "entry_type": "article",
                    "unresolvable": True,
                }
            ]
        )

        self.assertEqual(code, 0)


class MergeRecordTest(unittest.TestCase):
    def test_keeps_richer_author_list(self) -> None:
        merged = bibliography_library.merge_record(
            {"authors": ["Jiang Hao", "Kim Peter"]},
            {"authors": ["J H", "K P"]},
        )

        self.assertEqual(merged["authors"], ["Jiang Hao", "Kim Peter"])


if __name__ == "__main__":
    unittest.main()
