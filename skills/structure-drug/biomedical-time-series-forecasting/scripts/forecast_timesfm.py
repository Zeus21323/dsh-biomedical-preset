#!/usr/bin/env python3
"""验证时间序列 CSV，并在明确执行时调用 TimesFM 2.5。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_MODEL = "google/timesfm-2.5-200m-pytorch"


@dataclass(frozen=True)
class SeriesPlan:
    column: str
    observations: int
    missing: int
    minimum: float
    maximum: float


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="检查 CSV 并使用 TimesFM 2.5 生成点预测和分位数区间。默认只做 dry-run。"
    )
    parser.add_argument("input", type=Path, help="输入 CSV")
    parser.add_argument("--horizon", type=positive_int, required=True, help="预测步数")
    parser.add_argument("--time-col", help="可选时间列；用于排序检查，不自动推断未来日期")
    parser.add_argument("--value-cols", required=True, help="逗号分隔的数值列")
    parser.add_argument("--output", type=Path, default=Path("timesfm_forecast.csv"))
    parser.add_argument("--plan-output", type=Path, help="可选 dry-run JSON 输出")
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--max-context", type=positive_int, default=1024)
    parser.add_argument("--batch-size", type=positive_int, default=32)
    parser.add_argument(
        "--allow-negative", action="store_true",
        help="序列允许负值；关闭 TimesFM 的非负自动约束",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="实际加载模型并推理；未指定时只检查输入和输出计划",
    )
    return parser.parse_args()


def inspect_csv(path: Path, time_col: str | None, value_cols: list[str]) -> tuple[list[list[float]], list[SeriesPlan]]:
    if not path.is_file():
        raise ValueError(f"输入文件不存在：{path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing_fields = [name for name in ([time_col] if time_col else []) + value_cols if name not in fields]
        if missing_fields:
            raise ValueError(f"输入缺少字段：{', '.join(missing_fields)}")
        raw_rows = list(reader)
    if not raw_rows:
        raise ValueError("输入 CSV 没有数据行")

    if time_col:
        times = [(row.get(time_col) or "").strip() for row in raw_rows]
        if any(not value for value in times):
            raise ValueError("时间列存在空值")
        if len(set(times)) != len(times):
            raise ValueError("时间列存在重复值；请先按研究规则聚合")
        if times != sorted(times):
            raise ValueError("时间列不是升序；请先按真实时间排序")

    series_values: list[list[float]] = []
    plans: list[SeriesPlan] = []
    for column in value_cols:
        parsed: list[float] = []
        missing = 0
        for row_number, row in enumerate(raw_rows, start=2):
            raw = (row.get(column) or "").strip()
            if not raw or raw.upper() in {"NA", "NAN", "NULL"}:
                parsed.append(math.nan)
                missing += 1
                continue
            try:
                value = float(raw)
            except ValueError as exc:
                raise ValueError(f"第 {row_number} 行的 {column} 不是数值") from exc
            if not math.isfinite(value):
                parsed.append(math.nan)
                missing += 1
            else:
                parsed.append(value)
        finite = [value for value in parsed if math.isfinite(value)]
        if len(finite) < 3:
            raise ValueError(f"序列 {column} 的有效观测少于 3 个")
        first_valid = next(index for index, value in enumerate(parsed) if math.isfinite(value))
        trimmed = parsed[first_valid:]
        if not math.isfinite(trimmed[-1]):
            raise ValueError(f"序列 {column} 末端存在缺失，无法确定预测起点")
        series_values.append(trimmed)
        plans.append(SeriesPlan(column, len(finite), missing, min(finite), max(finite)))
    return series_values, plans


def write_plan(args: argparse.Namespace, plans: list[SeriesPlan]) -> dict[str, object]:
    plan = {
        "mode": "execute" if args.execute else "dry-run",
        "model_id": args.model_id,
        "horizon": args.horizon,
        "max_context": args.max_context,
        "batch_size": args.batch_size,
        "infer_is_positive": not args.allow_negative,
        "series": [asdict(item) for item in plans],
        "output": str(args.output),
        "warning": "推理不等于临床告警；必须进行时间回测和基线比较。",
    }
    rendered = json.dumps(plan, ensure_ascii=False, indent=2)
    print(rendered)
    if args.plan_output:
        if args.plan_output.exists():
            raise ValueError(f"计划输出已存在，拒绝覆盖：{args.plan_output}")
        args.plan_output.parent.mkdir(parents=True, exist_ok=True)
        args.plan_output.write_text(rendered + "\n", encoding="utf-8")
    return plan


def run_timesfm(args: argparse.Namespace, values: list[list[float]], plans: list[SeriesPlan]) -> None:
    try:
        import numpy as np
        import timesfm
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "实际推理需要 numpy、torch 和 TimesFM 2.5；请在隔离环境安装后重试。"
        ) from exc

    if args.output.exists():
        raise ValueError(f"输出已存在，拒绝覆盖：{args.output}")
    torch.set_float32_matmul_precision("high")
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(args.model_id)
    model.compile(
        timesfm.ForecastConfig(
            max_context=args.max_context,
            max_horizon=args.horizon,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=not args.allow_negative,
            fix_quantile_crossing=True,
            per_core_batch_size=args.batch_size,
        )
    )
    inputs = [np.asarray(item, dtype=np.float32) for item in values]
    point, quantiles = model.forecast(horizon=args.horizon, inputs=inputs)
    rows: list[dict[str, object]] = []
    for series_index, item in enumerate(plans):
        for step in range(args.horizon):
            rows.append(
                {
                    "series": item.column,
                    "step": step + 1,
                    "forecast": float(point[series_index, step]),
                    "mean": float(quantiles[series_index, step, 0]),
                    "q10": float(quantiles[series_index, step, 1]),
                    "q20": float(quantiles[series_index, step, 2]),
                    "q50": float(quantiles[series_index, step, 5]),
                    "q80": float(quantiles[series_index, step, 8]),
                    "q90": float(quantiles[series_index, step, 9]),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"完成：写入 {len(rows)} 行预测到 {args.output}")


def main() -> int:
    args = parse_args()
    value_cols = [item.strip() for item in args.value_cols.split(",") if item.strip()]
    if not value_cols:
        raise SystemExit("错误：--value-cols 不能为空")
    try:
        values, plans = inspect_csv(args.input, args.time_col, value_cols)
        write_plan(args, plans)
        if args.execute:
            run_timesfm(args, values, plans)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"错误：{exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
