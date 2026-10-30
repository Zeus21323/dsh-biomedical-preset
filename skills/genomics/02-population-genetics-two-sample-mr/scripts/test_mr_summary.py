#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
from pathlib import Path


SCRIPT = Path(__file__).with_name("mr_summary.py")
spec = importlib.util.spec_from_file_location("mr_summary", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_linear_effect() -> None:
    rows = []
    for index, exposure in enumerate((0.1, 0.2, 0.3, 0.4), start=1):
        rows.append(
            {
                "snp": f"rs{index}",
                "beta_exposure": exposure,
                "se_exposure": 0.02,
                "beta_outcome": exposure * 0.5,
                "se_outcome": 0.03,
            }
        )
    result = module.analyze(rows)
    assert math.isclose(result["ivw"]["beta"], 0.5, rel_tol=1e-12)
    assert math.isclose(result["weighted_median"]["beta"], 0.5, rel_tol=1e-12)
    assert math.isclose(result["mr_egger"]["intercept"], 0.0, abs_tol=1e-12)


def test_zero_exposure_rejected() -> None:
    rows = [
        {"snp": "rs1", "beta_exposure": 0.0, "se_exposure": 0.1, "beta_outcome": 0.2, "se_outcome": 0.1},
        {"snp": "rs2", "beta_exposure": 0.2, "se_exposure": 0.1, "beta_outcome": 0.3, "se_outcome": 0.1},
    ]
    try:
        module.analyze(rows)
    except ValueError as exc:
        assert "不能为零" in str(exc)
    else:
        raise AssertionError("零暴露效应应被拒绝")


if __name__ == "__main__":
    test_exact_linear_effect()
    test_zero_exposure_rejected()
    print("ok: MR deterministic tests")
