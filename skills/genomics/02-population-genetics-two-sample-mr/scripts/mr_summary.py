#!/usr/bin/env python3
"""对已经协调且相互独立的工具变量执行基础汇总数据 MR。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


REQUIRED = ("snp", "beta_exposure", "se_exposure", "beta_outcome", "se_outcome")


def normal_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def weighted_median(values: list[float], weights: list[float]) -> float:
    if not values or len(values) != len(weights):
        raise ValueError("比值和权重必须非空且等长")
    if any(not math.isfinite(v) for v in values + weights) or any(w <= 0 for w in weights):
        raise ValueError("比值须有限，权重须为有限正数")
    ordered = sorted(zip(values, weights), key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    cumulative = 0.0
    positions = []
    for _, weight in ordered:
        positions.append((cumulative + weight / 2.0) / total)
        cumulative += weight
    if len(ordered) == 1:
        return ordered[0][0]
    for i in range(len(ordered) - 1):
        if positions[i] <= 0.5 <= positions[i + 1]:
            fraction = (0.5 - positions[i]) / (positions[i + 1] - positions[i])
            return ordered[i][0] + fraction * (ordered[i + 1][0] - ordered[i][0])
    raise ValueError("无法确定加权中位数")


def analyze(rows: list[dict[str, float | str]]) -> dict[str, object]:
    if len(rows) < 2:
        raise ValueError("至少需要 2 个工具变量")
    x = [float(row["beta_exposure"]) for row in rows]
    sx = [float(row["se_exposure"]) for row in rows]
    y = [float(row["beta_outcome"]) for row in rows]
    sy = [float(row["se_outcome"]) for row in rows]
    if any(not math.isfinite(v) for v in x + sx + y + sy):
        raise ValueError("效应和标准误须为有限数值")
    ids = [str(row["snp"]).strip() for row in rows]
    if any(not s for s in ids) or len(set(ids)) != len(ids):
        raise ValueError("SNP须非空且唯一")
    if any(value == 0 for value in x):
        raise ValueError("beta_exposure 不能为零")
    if any(value <= 0 for value in sx + sy):
        raise ValueError("标准误必须大于零")

    weights = [1.0 / value**2 for value in sy]
    denominator = sum(weight * bx**2 for weight, bx in zip(weights, x))
    ivw_beta = sum(weight * bx * by for weight, bx, by in zip(weights, x, y)) / denominator
    ivw_se = math.sqrt(1.0 / denominator)
    ivw_q = sum(weight * (by - ivw_beta * bx) ** 2 for weight, bx, by in zip(weights, x, y))
    f_values = [(bx / se) ** 2 for bx, se in zip(x, sx)]

    ratios = [by / bx for bx, by in zip(x, y)]
    ratio_variances = [
        (sey**2 / bx**2) + (by**2 * sex**2 / bx**4)
        for bx, sex, by, sey in zip(x, sx, y, sy)
    ]
    median_beta = weighted_median(ratios, [1.0 / value for value in ratio_variances])

    result: dict[str, object] = {
        "n_instruments": len(rows),
        "mean_f_statistic": sum(f_values) / len(f_values),
        "minimum_f_statistic": min(f_values),
        "ivw": {
            "model": "fixed_effect_first_order",
            "beta": ivw_beta,
            "se": ivw_se,
            "z": ivw_beta / ivw_se,
            "p_normal_approx": normal_p(ivw_beta / ivw_se),
            "cochran_q": ivw_q,
            "q_df": len(rows) - 1,
        },
        "weighted_median": {"beta": median_beta, "se": None, "p": None},
        "warnings": [
            "输入必须已经完成等位基因协调和LD去相关。",
            "加权中位数脚本不提供bootstrap标准误；正式报告应使用成熟统计包复核。",
            "MR-Egger按暴露增加等位基因定向；P值与区间使用正态近似，非小样本t推断。",
        ],
    }

    if len(rows) >= 3:
        # Harmonising two traits alone does not orient variants to exposure-increasing alleles.
        y = [by if bx > 0 else -by for bx, by in zip(x, y)]
        x = [abs(bx) for bx in x]
        total_weight = sum(weights)
        xbar = sum(weight * bx for weight, bx in zip(weights, x)) / total_weight
        ybar = sum(weight * by for weight, by in zip(weights, y)) / total_weight
        sxx = sum(weight * (bx - xbar) ** 2 for weight, bx in zip(weights, x))
        if len(set(x)) < 2 or sxx == 0:
            result["mr_egger"] = None
            result["warnings"].append("暴露增加方向下工具效应无变化，Egger不可估计；其他结果保留。")
            return result
        egger_beta = sum(
            weight * (bx - xbar) * (by - ybar)
            for weight, bx, by in zip(weights, x, y)
        ) / sxx
        intercept = ybar - egger_beta * xbar
        q_egger = sum(
            weight * (by - intercept - egger_beta * bx) ** 2
            for weight, bx, by in zip(weights, x, y)
        )
        dispersion = max(1.0, q_egger / (len(rows) - 2))
        beta_se = math.sqrt(dispersion / sxx)
        intercept_se = math.sqrt(dispersion * (1.0 / total_weight + xbar**2 / sxx))
        result["mr_egger"] = {
            "beta": egger_beta,
            "se": beta_se,
            "p_normal_approx": normal_p(egger_beta / beta_se),
            "intercept": intercept,
            "intercept_se": intercept_se,
            "intercept_p_normal_approx": normal_p(intercept / intercept_se),
            "residual_q": q_egger,
            "q_df": len(rows) - 2,
        }
    else:
        result["mr_egger"] = None
    return result


def load_rows(path: Path) -> list[dict[str, float | str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"输入缺少字段：{', '.join(sorted(missing))}")
        rows: list[dict[str, float | str]] = []
        for line_number, row in enumerate(reader, start=2):
            parsed: dict[str, float | str] = {"snp": (row.get("snp") or "").strip()}
            if not parsed["snp"]:
                raise ValueError(f"第 {line_number} 行缺少 SNP")
            for field in REQUIRED[1:]:
                try:
                    value = float(row[field])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"第 {line_number} 行 {field} 无法解析") from exc
                if not math.isfinite(value):
                    raise ValueError(f"第 {line_number} 行 {field} 不是有限数值")
                parsed[field] = value
            rows.append(parsed)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="基础汇总数据 MR：IVW、MR-Egger 和加权中位数。")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.output.exists():
        raise SystemExit(f"错误：输出已存在，拒绝覆盖：{args.output}")
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / ".speedskills").exists():
            if args.output == parent or parent in args.output.parents:
                raise SystemExit("错误：运行结果不能写入源码仓库")
            break
    try:
        result = analyze(load_rows(args.input))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"错误：{exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"完成：{result['n_instruments']} 个工具变量，输出 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
