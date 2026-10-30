#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import math
import sys
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("forecast_timesfm.py")
spec = importlib.util.spec_from_file_location("forecast_timesfm", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_inspection() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "series.csv"
        with source.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time", "marker"])
            writer.writerows([("2026-01", 1.0), ("2026-02", 1.5), ("2026-03", ""), ("2026-04", 2.0)])
        values, plans = module.inspect_csv(source, "time", ["marker"])
        assert len(values) == 1
        assert plans[0].observations == 3
        assert plans[0].missing == 1
        assert math.isnan(values[0][2])


def test_duplicate_time_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "duplicate.csv"
        source.write_text("time,value\n1,1\n1,2\n2,3\n", encoding="utf-8")
        try:
            module.inspect_csv(source, "time", ["value"])
        except ValueError as exc:
            assert "重复" in str(exc)
        else:
            raise AssertionError("重复时间应被拒绝")


if __name__ == "__main__":
    test_inspection()
    test_duplicate_time_rejected()
    print("ok: TimesFM input and dry-run tests")
