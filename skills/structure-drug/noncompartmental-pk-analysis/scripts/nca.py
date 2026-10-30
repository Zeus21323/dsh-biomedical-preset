#!/usr/bin/env python3
"""对标准浓度-时间 CSV 执行单剂量非房室分析。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 3:
        raise argparse.ArgumentTypeError("终末相至少需要 3 个点")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="计算单剂量 NCA 参数并输出 CSV。")
    parser.add_argument("input", type=Path, help="输入 CSV")
    parser.add_argument("--output", type=Path, required=True, help="输出参数 CSV")
    parser.add_argument("--dose", type=float, required=True, help="剂量数值，必须预先统一单位")
    parser.add_argument(
        "--route", choices=("extravascular", "intravenous"), required=True,
        help="给药途径：血管外或静脉",
    )
    parser.add_argument("--subject-col", default="subject")
    parser.add_argument("--time-col", default="time")
    parser.add_argument("--concentration-col", default="concentration")
    parser.add_argument("--occasion-col", default="occasion")
    parser.add_argument("--terminal-points", type=positive_int, default=3)
    parser.add_argument("--metadata", type=Path, help="可选 JSON 元数据输出")
    return parser.parse_args()


def log_trapezoid(t1: float, c1: float, t2: float, c2: float) -> float:
    delta = t2 - t1
    if delta <= 0:
        raise ValueError("时间必须严格递增")
    if c1 > 0 and c2 > 0 and c2 < c1 and not math.isclose(c1, c2):
        return delta * (c1 - c2) / math.log(c1 / c2)
    return delta * (c1 + c2) / 2.0


def linear_regression(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    xs = [p[0] for p in points]
    ys = [math.log(p[1]) for p in points]
    n = len(points)
    xbar = sum(xs) / n
    ybar = sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("终末相时间点不能全部相同")
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    fitted = [intercept + slope * x for x in xs]
    sse = sum((y - f) ** 2 for y, f in zip(ys, fitted))
    sst = sum((y - ybar) ** 2 for y in ys)
    r2 = 1.0 if sst == 0 and sse == 0 else (0.0 if sst == 0 else 1.0 - sse / sst)
    return slope, intercept, r2


def analyze_profile(
    subject: str,
    occasion: str,
    points: list[tuple[float, float]],
    dose: float,
    route: str,
    terminal_points: int,
) -> dict[str, object]:
    ordered = sorted(points)
    if len(ordered) < terminal_points:
        raise ValueError(f"{subject}/{occasion} 可用浓度点少于终末相点数")
    if len({t for t, _ in ordered}) != len(ordered):
        raise ValueError(f"{subject}/{occasion} 存在重复时间点")
    if any(c < 0 for _, c in ordered):
        raise ValueError(f"{subject}/{occasion} 浓度不能为负数")

    cmax = max(c for _, c in ordered)
    tmax = next(t for t, c in ordered if c == cmax)
    auc_last = sum(log_trapezoid(*left, *right) for left, right in zip(ordered, ordered[1:]))

    positive_tail = [(t, c) for t, c in ordered if c > 0][-terminal_points:]
    if len(positive_tail) < terminal_points:
        raise ValueError(f"{subject}/{occasion} 正浓度终末相点不足")
    slope, _, r2 = linear_regression(positive_tail)
    if slope >= 0:
        raise ValueError(f"{subject}/{occasion} 终末相斜率不是负值")
    lambda_z = -slope
    half_life = math.log(2.0) / lambda_z
    last_time, last_concentration = ordered[-1]
    if last_concentration <= 0:
        raise ValueError(f"{subject}/{occasion} 最后可用浓度必须大于零")
    extrapolated = last_concentration / lambda_z
    auc_inf = auc_last + extrapolated
    pct_extrapolated = extrapolated / auc_inf * 100.0
    clearance = dose / auc_inf
    volume = clearance / lambda_z
    qc = []
    if r2 < 0.8:
        qc.append("终末相拟合R2低于0.8")
    if pct_extrapolated > 20:
        qc.append("AUC外推比例超过20%")

    return {
        "subject": subject,
        "occasion": occasion,
        "n_points": len(ordered),
        "cmax": cmax,
        "tmax": tmax,
        "auc_last": auc_last,
        "lambda_z": lambda_z,
        "half_life": half_life,
        "auc_inf": auc_inf,
        "auc_extrapolated_percent": pct_extrapolated,
        "clearance_label": "CL/F" if route == "extravascular" else "CL",
        "clearance": clearance,
        "volume_label": "Vz/F" if route == "extravascular" else "Vz",
        "volume": volume,
        "terminal_r2": r2,
        "terminal_start": positive_tail[0][0],
        "terminal_end": last_time,
        "qc": ";".join(qc) if qc else "通过内置检查",
    }


def load_profiles(args: argparse.Namespace) -> tuple[dict[tuple[str, str], list[tuple[float, float]]], int]:
    profiles: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    omitted = 0
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {args.subject_col, args.time_col, args.concentration_col}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"输入缺少字段：{', '.join(sorted(missing))}")
        has_occasion = args.occasion_col in (reader.fieldnames or [])
        for row_number, row in enumerate(reader, start=2):
            raw_concentration = (row.get(args.concentration_col) or "").strip()
            if not raw_concentration or raw_concentration.upper() == "BLQ":
                omitted += 1
                continue
            try:
                time = float(row[args.time_col])
                concentration = float(raw_concentration)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"第 {row_number} 行时间或浓度无法解析") from exc
            subject = (row.get(args.subject_col) or "").strip()
            if not subject:
                raise ValueError(f"第 {row_number} 行缺少受试者")
            occasion = (row.get(args.occasion_col) or "1").strip() if has_occasion else "1"
            profiles[(subject, occasion)].append((time, concentration))
    return profiles, omitted


def main() -> int:
    args = parse_args()
    if args.dose <= 0:
        raise SystemExit("错误：--dose 必须大于零")
    try:
        profiles, omitted = load_profiles(args)
        if not profiles:
            raise ValueError("没有可分析的浓度记录")
        results = [
            analyze_profile(subject, occasion, points, args.dose, args.route, args.terminal_points)
            for (subject, occasion), points in sorted(profiles.items())
        ]
    except (OSError, ValueError) as exc:
        raise SystemExit(f"错误：{exc}") from exc

    if args.output.exists():
        raise SystemExit(f"错误：输出已存在，拒绝覆盖：{args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    if args.metadata:
        if args.metadata.exists():
            raise SystemExit(f"错误：元数据输出已存在，拒绝覆盖：{args.metadata}")
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(
            json.dumps({"dose": args.dose, "route": args.route, "omitted_blq_or_blank": omitted}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"完成：{len(results)} 个浓度曲线，输出 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
