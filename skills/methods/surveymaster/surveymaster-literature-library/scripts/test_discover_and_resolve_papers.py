import unittest
from unittest.mock import patch
import urllib.error
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discover_and_resolve_papers as resolver


class OpenAlexFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        resolver.OPENALEX_DISABLED = False

    def tearDown(self) -> None:
        resolver.OPENALEX_DISABLED = False

    def test_openalex_429_disables_openalex_for_run(self) -> None:
        error = urllib.error.HTTPError(
            f"{resolver.OPENALEX_BASE}/works/doi:10.1000/test",
            429,
            "Too Many Requests",
            hdrs=None,
            fp=None,
        )

        with patch("urllib.request.urlopen", side_effect=error):
            data = resolver.get_json(f"{resolver.OPENALEX_BASE}/works/doi:10.1000/test")

        self.assertIsNone(data)
        self.assertTrue(resolver.OPENALEX_DISABLED)

    def test_complete_pubmed_candidate_skips_title_lookup(self) -> None:
        candidate = {
            "title": "Gut microbiome and colorectal cancer",
            "authors_text": "Alice Smith, Bob Chen",
            "year_hint": "2026",
            "venue_hint": "Gut Microbes",
            "doi": "10.1000/gutmicrobes.2026.1",
            "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
            "abstract_hint": "This PubMed abstract is already explicit and useful.",
            "source": "PubMed",
        }

        with (
            patch.object(resolver, "resolve_crossref_by_doi", return_value=None) as crossref_doi,
            patch.object(resolver, "resolve_openalex_by_doi", return_value=None) as openalex_doi,
            patch.object(resolver, "resolve_crossref_by_title") as crossref_title,
            patch.object(resolver, "resolve_openalex_by_title") as openalex_title,
        ):
            record = resolver.resolve_candidate(candidate)

        self.assertIsNotNone(record)
        self.assertEqual(record["title"], candidate["title"])
        self.assertEqual(record["journal"], "Gut Microbes")
        crossref_doi.assert_called_once()
        openalex_doi.assert_not_called()
        crossref_title.assert_not_called()
        openalex_title.assert_not_called()

    def test_incomplete_candidate_tries_crossref_before_openalex(self) -> None:
        calls: list[str] = []

        def crossref_by_title(title: str) -> dict:
            calls.append("crossref_title")
            return {
                "title": title,
                "authors": ["Alice Smith"],
                "year": "2026",
                "journal": "Gut Microbes",
                "entry_type": "article",
                "abstract": "Resolved abstract.",
            }

        def openalex_by_title(title: str) -> None:
            calls.append("openalex_title")
            return None

        candidate = {"title": "Gut microbiome and colorectal cancer"}
        with (
            patch.object(resolver, "resolve_crossref_by_title", side_effect=crossref_by_title),
            patch.object(resolver, "resolve_openalex_by_title", side_effect=openalex_by_title),
        ):
            record = resolver.resolve_candidate(candidate)

        self.assertIsNotNone(record)
        self.assertEqual(calls, ["crossref_title"])


if __name__ == "__main__":
    unittest.main()
