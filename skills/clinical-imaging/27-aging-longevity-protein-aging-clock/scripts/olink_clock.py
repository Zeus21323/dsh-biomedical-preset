#!/usr/bin/env python3
"""使用用户提供的冻结系数计算 Olink 器官蛋白质时钟。"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


def probability(value: str) -> float:
    parsed = float(value)
    if not 0 < parsed <= 1:
        raise argparse.ArgumentTypeError("必须位于 (0, 1]")
    return parsed


def load_coefficients(path: Path) -> dict[str, dict[str, object]]:
    models: dict[str, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"organ", "protein", "coefficient", "intercept"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"系数表缺少字段：{', '.join(sorted(missing))}")
        has_mean = "training_mean" in (reader.fieldnames or [])
        for line_number, row in enumerate(reader, start=2):
            organ = (row.get("organ") or "").strip()
            protein = (row.get("protein") or "").strip()
            if not organ or not protein:
                raise ValueError(f"系数表第 {line_number} 行缺少 organ 或 protein")
            try:
                coefficient = float(row["coefficient"])
                intercept = float(row["intercept"])
                raw_mean = (row.get("training_mean") or "").strip() if has_mean else ""
                training_mean = float(raw_mean) if raw_mean else None
            except ValueError as exc:
                raise ValueError(f"系数表第 {line_number} 行数值无法解析") from exc
            if not all(math.isfinite(value) for value in (coefficient, intercept)):
                raise ValueError(f"系数表第 {line_number} 行包含非有限数值")
            model = models.setdefault(organ, {"intercept": intercept, "proteins": {}})
            if not math.isclose(float(model["intercept"]), intercept):
                raise ValueError(f"器官 {organ} 的 intercept 不一致")
            proteins = model["proteins"]
            assert isinstance(proteins, dict)
            if protein in proteins:
                raise ValueError(f"器官 {organ} 的蛋白 {protein} 重复")
            proteins[protein] = (coefficient, training_mean)
    if not models:
        raise ValueError("系数表为空")
    return models


def compute(
    npx_path: Path,
    models: dict[str, dict[str, object]],
    sample_col: str,
    age_col: str | None,
    minimum_coverage: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    predictions: list[dict[str, object]] = []
    contributions: list[dict[str, object]] = []
    with npx_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        if sample_col not in fields:
            raise ValueError(f"NPX 表缺少样本列：{sample_col}")
        if age_col and age_col not in fields:
            raise ValueError(f"NPX 表缺少年龄列：{age_col}")
        for line_number, row in enumerate(reader, start=2):
            sample = (row.get(sample_col) or "").strip()
            if not sample:
                raise ValueError(f"NPX 表第 {line_number} 行缺少样本标识")
            chronological_age = None
            if age_col and (row.get(age_col) or "").strip():
                chronological_age = float(row[age_col])
            for organ, model in sorted(models.items()):
                proteins = model["proteins"]
                assert isinstance(proteins, dict)
                available = sum(1 for protein in proteins if (row.get(protein) or "").strip())
                coverage = available / len(proteins)
                qc: list[str] = []
                score = float(model["intercept"])
                usable = coverage >= minimum_coverage
                if not usable:
                    qc.append("蛋白覆盖率低于阈值")
                for protein, pair in proteins.items():
                    coefficient, training_mean = pair
                    raw = (row.get(protein) or "").strip()
                    imputed = False
                    if raw:
                        try:
                            value = float(raw)
                        except ValueError as exc:
                            raise ValueError(f"样本 {sample} 的 {protein} 不是数值") from exc
                    elif training_mean is not None:
                        value = float(training_mean)
                        imputed = True
                    else:
                        usable = False
                        qc.append(f"缺失{protein}且无训练均值")
                        continue
                    if not math.isfinite(value):
                        raise ValueError(f"样本 {sample} 的 {protein} 不是有限数值")
                    contribution = value * float(coefficient)
                    score += contribution
                    contributions.append(
                        {
                            "sample_id": sample,
                            "organ": organ,
                            "protein": protein,
                            "npx": value,
                            "coefficient": coefficient,
                            "contribution": contribution,
                            "imputed_training_mean": imputed,
                        }
                    )
                prediction = score if usable else ""
                predictions.append(
                    {
                        "sample_id": sample,
                        "organ": organ,
                        "predicted_age": prediction,
                        "chronological_age": chronological_age if chronological_age is not None else "",
                        "raw_age_difference": score - chronological_age if usable and chronological_age is not None else "",
                        "protein_coverage": coverage,
                        "proteins_required": len(proteins),
                        "proteins_observed": available,
                        "qc": ";".join(dict.fromkeys(qc)) if qc else "通过内置检查",
                    }
                )
    return predictions, contributions


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists():
        raise ValueError(f"输出已存在，拒绝覆盖：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="应用用户提供的冻结 Olink 器官衰老时钟系数。")
    parser.add_argument("npx", type=Path, help="样本×Assay NPX CSV")
    parser.add_argument("--coefficients", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--contributions", type=Path)
    parser.add_argument("--sample-col", default="sample_id")
    parser.add_argument("--age-col", default="age")
    parser.add_argument("--minimum-coverage", type=probability, default=0.8)
    args = parser.parse_args()
    try:
        models = load_coefficients(args.coefficients)
        predictions, contributions = compute(
            args.npx, models, args.sample_col, args.age_col or None, args.minimum_coverage
        )
        if not predictions:
            raise ValueError("NPX 表没有样本")
        write_csv(args.output, predictions)
        if args.contributions:
            write_csv(args.contributions, contributions)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"错误：{exc}") from exc
    print(f"完成：输出 {len(predictions)} 个样本-器官结果")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
