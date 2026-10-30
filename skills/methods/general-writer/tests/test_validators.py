import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_manuscript import MANUAL_BIBLIOGRAPHY_RE, audit, find_manual_author_year_citations
from validate_claim_evidence_map import validate
from validate_manuscript_approval import validate_approval


def claim(evidence_type="data", status="verified", source="evidence.txt"):
    return {
        "id": "C1",
        "text": "A bounded claim.",
        "evidence_type": evidence_type,
        "verification_status": status,
        "source_files": [source],
        "locator": "line 1",
        "statistics": [],
        "allowed_wording": "supports the bounded claim",
        "prohibited_wording": ["proves universally"],
        "caveats": ["bounded evidence"],
        "section": "sec:results",
        "table_or_figure": None,
    }


def evidence_map(study_type, item):
    return {
        "paper_goal": "Answer a bounded research question.",
        "study_type": study_type,
        "discipline_profiles": ["generic"],
        "research_questions": [
            {
                "id": "RQ1",
                "question": "What does the evidence support?",
                "answer_scope": "The supplied materials",
                "claims": [item],
            }
        ],
    }


class EvidenceValidatorTests(unittest.TestCase):
    def run_validation(self, study_type, evidence_type, status="verified"):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "evidence.txt").write_text("evidence\n", encoding="utf-8")
            return validate(
                evidence_map(study_type, claim(evidence_type, status)), root
            )

    def test_experimental_requires_and_accepts_primary_evidence(self):
        errors, _ = self.run_validation("experimental", "experiment")
        self.assertEqual([], errors)

        errors, _ = self.run_validation("experimental", "literature")
        self.assertIn(
            "study_type=experimental requires at least one primary-evidence claim",
            errors,
        )

    def test_review_accepts_literature_evidence(self):
        errors, _ = self.run_validation("review", "literature")
        self.assertEqual([], errors)

    def test_theoretical_requires_theory_or_artifact(self):
        errors, _ = self.run_validation("theoretical", "theory")
        self.assertEqual([], errors)

        errors, _ = self.run_validation("theoretical", "literature")
        self.assertIn(
            "study_type=theoretical requires theory, artifact, or mixed evidence",
            errors,
        )

    def test_unsupported_claim_blocks_delivery(self):
        errors, _ = self.run_validation("empirical", "data", "unsupported")
        self.assertTrue(any("unsupported" in item for item in errors))


class ManuscriptAuditTests(unittest.TestCase):
    def test_manual_author_year_citations_are_detected(self):
        tex = (
            "批判性思维是一种可训练能力（Facione, 1990; Kamysheva, 2021）。 "
            "Sweller 等人（2011）提出了另一模型。"
        )
        matches = find_manual_author_year_citations(tex)
        self.assertEqual(2, len(matches), matches)

    def test_manual_bibliography_list_is_detected(self):
        tex = r"""
\section*{参考文献}
\begin{description}
\item[Facione (1990)] Facione, P. Critical Thinking.
\end{description}
"""
        self.assertIsNotNone(MANUAL_BIBLIOGRAPHY_RE.search(tex))

    def test_complete_experimental_manuscript_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manuscript = root / "manuscript"
            manuscript.mkdir()
            (root / "evidence.txt").write_text("evidence\n", encoding="utf-8")
            evidence_path = root / "claim_evidence_map.json"
            evidence_path.write_text(
                json.dumps(evidence_map("experimental", claim("experiment"))),
                encoding="utf-8",
            )
            plan_path = root / "manuscript_plan.json"
            plan_path.write_text(
                json.dumps({"status": "approved", "scope": "bounded test"}),
                encoding="utf-8",
            )
            approval_path = root / "manuscript_approval.json"
            approval_path.write_text(
                json.dumps(
                    {
                        "approval_scope": "full_manuscript_plan",
                        "approval_decision": "approved",
                        "approval_text": "Approve the manuscript plan",
                        "approval_method": "request_user_input",
                        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                        "approved_in_current_conversation": True,
                    }
                ),
                encoding="utf-8",
            )
            tex = manuscript / "mainbody.tex"
            tex.write_text(
                r"""
\begin{abstract}A bounded abstract.\end{abstract}
\section{Introduction}Prior work motivates the study \cite{real2026}.
\section{Methods}The supplied protocol defines the method.
\section{Results}The result answers the question.
\section{Limitations}The evidence has bounded scope.
\section{Conclusion}The conclusion stays within that scope.
""",
                encoding="utf-8",
            )
            bib = manuscript / "references.bib"
            bib.write_text(
                "@article{real2026, title={Real source}, author={Author, A}, year={2026}}\n",
                encoding="utf-8",
            )

            report = audit(tex, bib, evidence_path, plan_path, approval_path, root)
            self.assertEqual("pass", report["status"], report)


class ApprovalValidatorTests(unittest.TestCase):
    def make_files(self, root, plan_status="approved"):
        plan = root / "manuscript_plan.json"
        plan.write_text(json.dumps({"status": plan_status, "scope": "test"}), encoding="utf-8")
        receipt = root / "manuscript_approval.json"
        receipt.write_text(
            json.dumps(
                {
                    "approval_scope": "full_manuscript_plan",
                    "approval_decision": "approved",
                    "approval_text": "Approved",
                    "approval_method": "ask_user",
                    "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
                    "approved_in_current_conversation": True,
                }
            ),
            encoding="utf-8",
        )
        return plan, receipt

    def test_matching_structured_approval_passes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan, receipt = self.make_files(Path(temp_dir))
            errors, warnings = validate_approval(plan, receipt)
            self.assertEqual([], errors)
            self.assertEqual([], warnings)

    def test_changed_plan_invalidates_approval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan, receipt = self.make_files(Path(temp_dir))
            plan.write_text(json.dumps({"status": "approved", "scope": "changed"}), encoding="utf-8")
            errors, _ = validate_approval(plan, receipt)
            self.assertTrue(any("mismatch" in item for item in errors))

    def test_pending_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan, receipt = self.make_files(Path(temp_dir), plan_status="pending")
            errors, _ = validate_approval(plan, receipt)
            self.assertIn("manuscript plan status must be approved", errors)


if __name__ == "__main__":
    unittest.main()
