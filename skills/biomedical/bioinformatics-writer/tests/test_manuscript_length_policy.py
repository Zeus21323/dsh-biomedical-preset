from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_manuscript_preflight import (  # noqa: E402
    DEFAULT_LENGTH_MINIMUMS,
    extract_manuscript_structure,
    length_policy_minimums,
    validate_plan,
    validate_manuscript_lengths,
)


def plan(enforcement: str = "advisory", *, minimum: float | None = None) -> dict:
    minimums = {
        key: float(minimum if minimum is not None else value)
        for key, value in DEFAULT_LENGTH_MINIMUMS.items()
    }
    return {
        "length_policy": {
            "unit": "word_equivalents",
            "enforcement": enforcement,
            "minimums": minimums,
            "journal_override": None,
        }
    }


SHORT_COMPLETE_MANUSCRIPT = r"""
\documentclass{article}
\begin{document}
\section*{Abstract}
Short abstract.
\section{Background}
Short introduction.
\section{Experimental Procedures}
Short methods.
\section{Results and Discussion}
Short combined findings and interpretation.
\section{Summary and Outlook}
Short conclusion.
\end{document}
"""


class ManuscriptLengthPolicyTests(unittest.TestCase):
    def test_advisory_short_manuscript_warns_without_failing(self) -> None:
        errors, report = validate_manuscript_lengths(
            SHORT_COMPLETE_MANUSCRIPT, plan("advisory"), 0
        )
        self.assertEqual([], errors)
        self.assertEqual("advisory", report["length_enforcement"])
        self.assertTrue(report["length_warnings"])
        self.assertGreater(report["section_totals"]["results"], 0)
        self.assertGreater(report["section_totals"]["discussion"], 0)

    def test_strict_short_manuscript_fails(self) -> None:
        errors, report = validate_manuscript_lengths(
            SHORT_COMPLETE_MANUSCRIPT, plan("strict"), 0
        )
        self.assertTrue(any("too short" in error for error in errors))
        self.assertEqual([], report["length_warnings"])

    def test_missing_required_section_remains_error_in_advisory_mode(self) -> None:
        incomplete = SHORT_COMPLETE_MANUSCRIPT.replace(
            "\\section{Experimental Procedures}\nShort methods.\n", ""
        )
        errors, _ = validate_manuscript_lengths(incomplete, plan("advisory"), 0)
        self.assertIn("manuscript missing recognizable methods section", errors)

    def test_abstract_command_is_recognized(self) -> None:
        structure = extract_manuscript_structure(
            r"\begin{document}\abstract{Command-form abstract text.}"
            r"\section{Introduction}Body.\end{document}"
        )
        self.assertTrue(structure["abstract_found"])
        self.assertGreater(structure["abstract_word_equivalents"], 0)

    def test_advisory_lower_targets_do_not_require_journal_override(self) -> None:
        _, advisory_errors = length_policy_minimums(plan("advisory", minimum=1))
        _, strict_errors = length_policy_minimums(plan("strict", minimum=1))
        self.assertEqual([], advisory_errors)
        self.assertTrue(any("journal_override" in error for error in strict_errors))

    def test_advisory_plan_allocations_do_not_block_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "evidence.txt").write_text("verified", encoding="utf-8")
            manuscript_plan = {
                "title": "Test",
                "article_type": "original_research",
                "language": "en",
                "target_journal": "generic_biomedical",
                "guidelines_source": "generic",
                "citation_style": "numeric",
                "citation_mode": "numeric",
                "citation_export_mode": "strict_linked",
                "citation_presentation": "inline_numeric",
                "approval_status": "pending",
                **plan("advisory", minimum=1),
                "sections": [],
            }
            for section_type in (
                "introduction", "methods", "results", "discussion", "conclusion"
            ):
                section = {
                    "section_id": section_type,
                    "section_type": section_type,
                    "heading": section_type.title(),
                    "purpose": "Test purpose",
                    "minimum_word_equivalents": 1,
                    "result_question_ids": [],
                    "figure_ids": [],
                    "evidence_ids": [],
                    "evidence_files": [],
                }
                if section_type == "results":
                    section.update(
                        result_question_ids=["RQ1"],
                        figure_ids=["Figure 1"],
                        evidence_ids=["E1"],
                        evidence_files=["evidence.txt"],
                        claims=["Claim"],
                        statistics=["Statistic"],
                        limitations=["Limitation"],
                    )
                if section_type == "methods":
                    section["subsections"] = [
                        {"heading": "Data processing", "minimum_word_equivalents": 1}
                    ]
                manuscript_plan["sections"].append(section)

            errors = validate_plan(
                root,
                manuscript_plan,
                {"results_questions": [{"id": "RQ1"}]},
                {"figures": [{"figure_id": "Figure 1"}]},
                {
                    "evidence": [
                        {
                            "claim_id": "E1",
                            "source_files": ["evidence.txt"],
                            "status": "verified",
                        }
                    ]
                },
                False,
            )
            self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
