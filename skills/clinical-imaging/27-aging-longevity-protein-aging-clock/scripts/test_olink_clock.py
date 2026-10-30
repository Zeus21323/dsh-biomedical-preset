#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("olink_clock.py")
spec = importlib.util.spec_from_file_location("olink_clock", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_linear_clock() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        coefficients = root / "coefficients.csv"
        coefficients.write_text(
            "organ,protein,coefficient,intercept,training_mean\nHeart,P1,2,10,1\nHeart,P2,-1,10,3\n",
            encoding="utf-8",
        )
        npx = root / "npx.csv"
        npx.write_text("sample_id,age,P1,P2\nSYN001,40,5,4\nSYN002,30,2,\n", encoding="utf-8")
        models = module.load_coefficients(coefficients)
        predictions, contributions = module.compute(npx, models, "sample_id", "age", 0.5)
        assert predictions[0]["predicted_age"] == 16.0
        assert predictions[0]["raw_age_difference"] == -24.0
        assert predictions[1]["predicted_age"] == 11.0
        assert any(row["imputed_training_mean"] for row in contributions)


if __name__ == "__main__":
    test_frozen_linear_clock()
    print("ok: Olink frozen clock tests")
