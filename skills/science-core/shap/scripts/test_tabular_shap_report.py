#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("tabular_shap_report.py")
spec = importlib.util.spec_from_file_location("tabular_shap_report", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def build_table(path: Path, rows: int = 24) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["marker_a", "marker_b", "outcome"])
        for index in range(rows):
            writer.writerow([index / 10, (index % 5) / 5, "case" if index % 2 else "control"])


def test_validation_and_task_inference() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.csv"
        build_table(path)
        features, targets, rows = module.validate_csv(path, "outcome")
        assert features == ["marker_a", "marker_b"]
        assert rows == 24
        assert module.infer_task("auto", targets) == "classification"


def test_missing_target_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "synthetic.csv"
        build_table(path)
        try:
            module.validate_csv(path, "missing")
        except ValueError as exc:
            assert "目标列不存在" in str(exc)
        else:
            raise AssertionError("缺失目标列应被拒绝")


if __name__ == "__main__":
    test_validation_and_task_inference()
    test_missing_target_rejected()
    print("ok: SHAP input validation tests")
