import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_figure_blueprint.py"
SPEC = importlib.util.spec_from_file_location("validate_figure_blueprint", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def valid_blueprint() -> dict:
    return {
        "figures": [
            {
                "figure_id": "Figure 1",
                "title": "Example",
                "result_question": "Do groups differ?",
                "claim": "Groups differ reproducibly.",
                "contract": {
                    "core_conclusion": "Groups differ reproducibly.",
                    "archetype": "asymmetric_mixed_modality",
                    "evidence_hierarchy": {
                        "hero_panel": "A",
                        "primary_evidence": ["B"],
                        "validation_evidence": [],
                        "controls_robustness": [],
                    },
                    "reviewer_risks": ["Sample-size reporting must be explicit."],
                    "image_integrity_notes": [],
                },
                "panels": [
                    {
                        "label": "A",
                        "experiment": "transcriptomic_structure",
                        "evidence_tier": "hero",
                        "plot_type": "PCA",
                        "input": "results/pca.csv",
                        "evidence": "Global separation",
                        "statistical_message": "Unsupervised projection",
                        "output": "figures/experiments/transcriptomic_structure/panels/Figure1A.png",
                    },
                    {
                        "label": "B",
                        "experiment": "differential_expression",
                        "evidence_tier": "primary",
                        "plot_type": "volcano",
                        "input": "results/deg.csv",
                        "evidence": "Differential genes",
                        "statistical_message": "FDR controlled",
                        "output": "figures/experiments/differential_expression/panels/Figure1B.png",
                    },
                ],
                "layout": {
                    "render_backend": "python",
                    "backend_reason": "Both panels are reproducible from CSV with matplotlib.",
                    "figure_source": "figures/combined/sources/Figure1.py",
                    "final_width_mm": 183,
                    "final_height_mm": 120,
                    "shared_legend": True,
                    "panel_slots": [
                        {"label": "A", "row": 1, "column": 1, "rowspan": 2, "colspan": 2},
                        {"label": "B", "row": 1, "column": 3, "rowspan": 2, "colspan": 1},
                    ],
                    "preview_output": "figures/combined/Figure1_preview.png",
                    "publication_outputs": [
                        "figures/combined/Figure1.svg",
                        "figures/combined/Figure1.pdf",
                        "figures/combined/Figure1_600dpi.tiff",
                    ],
                    "qa_output": "figures/combined/Figure1_qa.json",
                },
            }
        ]
    }


class FigureBlueprintValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "results").mkdir()
        (self.root / "results" / "pca.csv").write_text("x,y\n1,2\n", encoding="utf-8")
        (self.root / "results" / "deg.csv").write_text("gene,logfc\nA,1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self, data: dict, **kwargs) -> list[str]:
        return MODULE.validate(data, self.root, True, False, **kwargs)

    def test_valid_unified_figure_contract(self) -> None:
        self.assertEqual(self.validate(valid_blueprint()), [])

    def test_quantitative_grid_may_have_no_hero(self) -> None:
        data = valid_blueprint()
        figure = data["figures"][0]
        figure["contract"]["archetype"] = "quantitative_grid"
        figure["contract"]["evidence_hierarchy"]["hero_panel"] = None
        figure["contract"]["evidence_hierarchy"]["primary_evidence"] = ["A", "B"]
        figure["panels"][0]["evidence_tier"] = "primary"
        self.assertEqual(self.validate(data), [])

    def test_experiment_is_required_and_scoped(self) -> None:
        data = valid_blueprint()
        del data["figures"][0]["panels"][0]["experiment"]
        errors = self.validate(data)
        self.assertTrue(any("missing key experiment" in error for error in errors))
        self.assertTrue(any("stable lowercase experiment slug" in error for error in errors))

    def test_overlapping_slots_are_rejected(self) -> None:
        data = valid_blueprint()
        data["figures"][0]["layout"]["panel_slots"][1].update(
            {"row": 2, "column": 2, "rowspan": 1, "colspan": 1}
        )
        errors = self.validate(data)
        self.assertTrue(any("overlap" in error for error in errors))

    def test_backend_must_match_complete_figure_source(self) -> None:
        data = valid_blueprint()
        data["figures"][0]["layout"]["render_backend"] = "r"
        errors = self.validate(data)
        self.assertTrue(any("must end in .R" in error for error in errors))

    def test_complete_bundle_can_be_required(self) -> None:
        data = valid_blueprint()
        errors = self.validate(
            data,
            require_figure_source=True,
            require_publication_outputs=True,
        )
        self.assertTrue(any("figure_source missing" in error for error in errors))
        self.assertTrue(any("required figure output missing" in error for error in errors))

    def test_complete_unified_bundle_passes(self) -> None:
        data = valid_blueprint()
        paths = [
            "figures/combined/sources/Figure1.py",
            "figures/combined/Figure1_preview.png",
            "figures/combined/Figure1.svg",
            "figures/combined/Figure1.pdf",
            "figures/combined/Figure1_600dpi.tiff",
            "figures/combined/Figure1_qa.json",
            "figures/experiments/transcriptomic_structure/panels/Figure1A.png",
            "figures/experiments/differential_expression/panels/Figure1B.png",
        ]
        for raw in paths:
            path = self.root / raw
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder", encoding="utf-8")
        errors = MODULE.validate(data, self.root, True, True, True, True)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
