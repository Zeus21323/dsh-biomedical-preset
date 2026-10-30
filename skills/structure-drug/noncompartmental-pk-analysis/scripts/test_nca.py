#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import math
from pathlib import Path


SCRIPT = Path(__file__).with_name("nca.py")
spec = importlib.util.spec_from_file_location("nca", SCRIPT)
assert spec and spec.loader
nca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nca)


def test_exponential_profile() -> None:
    points = [(t, 100.0 * math.exp(-0.2 * t)) for t in (0.0, 1.0, 2.0, 4.0, 6.0)]
    result = nca.analyze_profile("SYN001", "1", points, 100.0, "extravascular", 3)
    assert math.isclose(result["lambda_z"], 0.2, rel_tol=1e-10)
    assert math.isclose(result["half_life"], math.log(2) / 0.2, rel_tol=1e-10)
    assert math.isclose(result["auc_inf"], 500.0, rel_tol=1e-10)
    assert result["clearance_label"] == "CL/F"


def test_duplicate_time_rejected() -> None:
    try:
        nca.analyze_profile("SYN002", "1", [(0, 4), (1, 3), (1, 2), (2, 1)], 10, "intravenous", 3)
    except ValueError as exc:
        assert "重复时间点" in str(exc)
    else:
        raise AssertionError("重复时间点应被拒绝")


if __name__ == "__main__":
    test_exponential_profile()
    test_duplicate_time_rejected()
    print("ok: NCA deterministic tests")
