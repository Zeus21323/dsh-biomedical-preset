#!/usr/bin/env python3
"""Generate transparent, non-prescriptive diagnostics for tabular data."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_table(path: Path, delimiter: str | None) -> pd.DataFrame:
    if delimiter is None:
        delimiter = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
    return pd.read_csv(path, sep=delimiter)


def numeric_diagnostics(df: pd.DataFrame, shapiro_max_n: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in df.select_dtypes(include=[np.number]).columns:
        raw = pd.to_numeric(df[column], errors="coerce")
        values = raw.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
        row: dict[str, object] = {
            "variable": column,
            "n_total": int(len(raw)),
            "n_observed": int(len(values)),
            "n_missing_or_nonfinite": int(len(raw) - len(values)),
            "n_unique": int(pd.Series(values).nunique()),
            "mean": float(np.mean(values)) if len(values) else None,
            "sd": float(np.std(values, ddof=1)) if len(values) > 1 else None,
            "median": float(np.median(values)) if len(values) else None,
            "q1": float(np.quantile(values, 0.25)) if len(values) else None,
            "q3": float(np.quantile(values, 0.75)) if len(values) else None,
            "minimum": float(np.min(values)) if len(values) else None,
            "maximum": float(np.max(values)) if len(values) else None,
            "skewness": float(stats.skew(values, bias=False)) if len(values) >= 3 else None,
            "shapiro_w": None,
            "shapiro_p": None,
            "shapiro_note": "not run",
        }
        if 3 <= len(values) <= shapiro_max_n and len(np.unique(values)) > 1:
            result = stats.shapiro(values)
            row.update(
                shapiro_w=float(result.statistic),
                shapiro_p=float(result.pvalue),
                shapiro_note="diagnostic only; do not use as an automatic test selector",
            )
        elif len(values) > shapiro_max_n:
            row["shapiro_note"] = f"not run: n exceeds {shapiro_max_n}"
        rows.append(row)
    return pd.DataFrame(rows)


def variance_diagnostics(df: pd.DataFrame, group: str | None) -> pd.DataFrame:
    if group is None:
        return pd.DataFrame(columns=["variable", "group", "levene_w", "levene_p", "note"])
    if group not in df.columns:
        raise ValueError(f"group column not found: {group}")

    rows: list[dict[str, object]] = []
    groups = [value for value in df[group].dropna().unique()]
    for column in df.select_dtypes(include=[np.number]).columns:
        samples = []
        used_groups = []
        for value in groups:
            sample = pd.to_numeric(
                df.loc[df[group] == value, column], errors="coerce"
            ).replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
            if len(sample) >= 2:
                samples.append(sample)
                used_groups.append(str(value))
        if len(samples) >= 2:
            result = stats.levene(*samples, center="median")
            rows.append(
                {
                    "variable": column,
                    "group": "|".join(used_groups),
                    "levene_w": float(result.statistic),
                    "levene_p": float(result.pvalue),
                    "note": "Brown-Forsythe variant; interpret with plots and design",
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--delimiter", help="Explicit delimiter; defaults from extension")
    parser.add_argument("--group", help="Optional categorical group column")
    parser.add_argument("--shapiro-max-n", type=int, default=5000)
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    if args.shapiro_max_n < 3 or args.shapiro_max_n > 5000:
        parser.error("--shapiro-max-n must be between 3 and 5000")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    df = read_table(args.input, args.delimiter)
    if df.empty:
        parser.error("input table has no rows")

    numeric = numeric_diagnostics(df, args.shapiro_max_n)
    variance = variance_diagnostics(df, args.group)
    numeric.to_csv(args.output_dir / "numeric_diagnostics.tsv", sep="\t", index=False)
    variance.to_csv(args.output_dir / "variance_diagnostics.tsv", sep="\t", index=False)

    metadata = {
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "group_column": args.group,
        "numeric_columns": list(numeric.get("variable", [])),
        "parameters": {"shapiro_max_n": args.shapiro_max_n},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "interpretation": "Diagnostics do not automatically select a statistical test.",
    }
    (args.output_dir / "diagnostics_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
