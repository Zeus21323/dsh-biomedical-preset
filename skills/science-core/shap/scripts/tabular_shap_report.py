#!/usr/bin/env python3
"""从数值型 CSV 训练可复现基线树模型并生成经过加和性检查的 SHAP 报告。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成表格基线模型的 SHAP 审计报告。")
    parser.add_argument("input", type=Path, help="输入 CSV；特征必须为数值")
    parser.add_argument("--target", required=True, help="目标列")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--task", choices=("auto", "classification", "regression"), default="auto")
    parser.add_argument("--class-index", type=int, default=1, help="分类时解释的编码类别下标")
    parser.add_argument("--background-size", type=positive_int, default=100)
    parser.add_argument("--explain-size", type=positive_int, default=100)
    parser.add_argument("--max-display", type=positive_int, default=15)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--feature-perturbation",
        choices=("tree_path_dependent", "interventional"),
        default="tree_path_dependent",
        help="默认 tree_path_dependent 可精确重构本脚本的随机森林输出",
    )
    parser.add_argument(
        "--max-additivity-error", type=float, default=0.02,
        help="超过该最大绝对误差时停止输出，默认 0.02",
    )
    parser.add_argument("--validate-only", action="store_true", help="只校验 CSV，不导入建模依赖")
    return parser.parse_args()


def validate_csv(path: Path, target: str) -> tuple[list[str], list[str], int]:
    if not path.is_file():
        raise ValueError(f"输入文件不存在：{path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if target not in fields:
            raise ValueError(f"目标列不存在：{target}")
        features = [name for name in fields if name != target]
        if not features:
            raise ValueError("没有特征列")
        target_values: list[str] = []
        rows = 0
        for row_number, row in enumerate(reader, start=2):
            rows += 1
            raw_target = (row.get(target) or "").strip()
            if not raw_target:
                raise ValueError(f"第 {row_number} 行目标为空")
            target_values.append(raw_target)
            for feature in features:
                raw = (row.get(feature) or "").strip()
                if not raw:
                    raise ValueError(f"第 {row_number} 行特征 {feature} 为空")
                try:
                    value = float(raw)
                except ValueError as exc:
                    raise ValueError(f"第 {row_number} 行特征 {feature} 不是数值") from exc
                if not math.isfinite(value):
                    raise ValueError(f"第 {row_number} 行特征 {feature} 不是有限数值")
    if rows < 20:
        raise ValueError("至少需要 20 行，避免把演示结果误作稳定解释")
    return features, target_values, rows


def infer_task(requested: str, target_values: list[str]) -> str:
    if requested != "auto":
        return requested
    numeric = True
    parsed: list[float] = []
    for value in target_values:
        try:
            parsed.append(float(value))
        except ValueError:
            numeric = False
            break
    unique = len(set(target_values))
    return "classification" if not numeric or unique <= 20 else "regression"


def select_class_explanation(explanation, class_index: int):
    import numpy as np

    values = np.asarray(explanation.values)
    if values.ndim == 2:
        if class_index != 0:
            raise ValueError("解释器只返回一个输出，--class-index 必须为 0")
        return explanation
    if values.ndim != 3 or class_index < 0 or class_index >= values.shape[-1]:
        raise ValueError(f"类别下标 {class_index} 与 SHAP 输出形状 {values.shape} 不兼容")
    return explanation[..., class_index]


def save_plot(plot_function, path: Path) -> None:
    import matplotlib.pyplot as plt
    from runpy import run_path
    export = run_path(str(Path(__file__).with_name("figure_delivery.py")))["save_figure"]
    before = set(plt.get_fignums())
    base = plt.figure()
    try:
        result = plot_function()
        if hasattr(result, "figure"):
            fig = result.figure
        else:
            candidates = [plt.figure(n) for n in set(plt.get_fignums()) - before]
            candidates = [f for f in candidates if f.axes and any(a.has_data() for a in f.axes)]
            if len(candidates) != 1:
                raise ValueError("无法唯一确认SHAP数据图形对象")
            fig = candidates[0]
        fig.tight_layout()
        export(fig, path, dpi=400)
    finally:
        for n in set(plt.get_fignums()) - before:
            plt.close(n)


def run_report(args: argparse.Namespace, task: str, features: list[str]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import numpy as np
        import pandas as pd
        import shap
        import sklearn
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.metrics import accuracy_score, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import LabelEncoder
    except ImportError as exc:
        raise RuntimeError("需要 numpy、pandas、matplotlib、scikit-learn 和 shap") from exc

    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"输出目录非空，拒绝覆盖：{args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(args.input)
    x = frame[features].astype(float)
    labels: list[str] | None = None

    if task == "classification":
        encoder = LabelEncoder()
        y = encoder.fit_transform(frame[args.target].astype(str))
        labels = encoder.classes_.astype(str).tolist()
        if len(labels) < 2:
            raise ValueError("分类目标只有一个类别")
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=args.seed, stratify=y
        )
        model = RandomForestClassifier(n_estimators=300, random_state=args.seed, n_jobs=-1)
        model.fit(x_train, y_train)
        metric_name = "accuracy"
        metric_value = float(accuracy_score(y_test, model.predict(x_test)))
    else:
        y = pd.to_numeric(frame[args.target], errors="raise").astype(float)
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=args.seed
        )
        model = RandomForestRegressor(n_estimators=300, random_state=args.seed, n_jobs=-1)
        model.fit(x_train, y_train)
        metric_name = "r2"
        metric_value = float(r2_score(y_test, model.predict(x_test)))

    explained = x_test.iloc[: min(args.explain_size, len(x_test))]
    if args.feature_perturbation == "interventional":
        background = x_train.sample(min(args.background_size, len(x_train)), random_state=args.seed)
        model_output = "probability" if task == "classification" else "raw"
        explainer = shap.TreeExplainer(
            model, background, feature_perturbation="interventional", model_output=model_output
        )
    else:
        background = None
        model_output = "raw"
        explainer = shap.TreeExplainer(
            model, feature_perturbation="tree_path_dependent", model_output="raw"
        )
    explanation = explainer(explained)

    if task == "classification":
        selected = select_class_explanation(explanation, args.class_index)
        predicted = model.predict_proba(explained)[:, args.class_index]
        selected_label = labels[args.class_index]
    else:
        selected = explanation
        predicted = model.predict(explained)
        selected_label = None

    base_values = np.asarray(selected.base_values, dtype=float)
    if base_values.ndim == 0:
        base_values = np.repeat(base_values, len(explained))
    reconstructed = base_values.reshape(-1) + np.asarray(selected.values).sum(axis=1)
    max_additivity_error = float(np.max(np.abs(reconstructed - predicted)))
    if max_additivity_error > args.max_additivity_error:
        raise ValueError(f"SHAP 加和性检查失败，最大误差 {max_additivity_error:.6g}")

    pd.DataFrame(np.asarray(selected.values), columns=features, index=explained.index).to_csv(args.output_dir / "shap_values.csv", index_label="observation")
    explained.to_csv(args.output_dir / "feature_values.csv", index_label="observation")
    pd.DataFrame({"base_value":base_values.reshape(-1),"prediction":predicted},index=explained.index).to_csv(args.output_dir / "prediction_values.csv",index_label="observation")
    global_table = pd.DataFrame(
        {
            "feature": features,
            "mean_abs_shap": np.abs(np.asarray(selected.values)).mean(axis=0),
            "mean_shap": np.asarray(selected.values).mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)
    global_table.to_csv(args.output_dir / "global_importance.csv", index=False)
    save_plot(
        lambda: shap.plots.bar(selected, max_display=args.max_display, show=False),
        args.output_dir / "global_bar.png",
    )
    save_plot(
        lambda: shap.plots.beeswarm(selected, max_display=args.max_display, show=False),
        args.output_dir / "beeswarm.png",
    )

    summary = {
        "task": task,
        "target": args.target,
        "class_index": args.class_index if task == "classification" else None,
        "class_label": selected_label,
        "model_output": model_output,
        "metric": {metric_name: metric_value},
        "rows": len(frame),
        "features": len(features),
        "feature_perturbation": args.feature_perturbation,
        "background_rows": len(background) if background is not None else 0,
        "explained_rows": len(explained),
        "max_additivity_error": max_additivity_error,
        "versions": {"shap": shap.__version__, "scikit_learn": sklearn.__version__},
        "warning": "SHAP 解释模型预测，不证明生物学或临床因果。",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "figure_report.md").write_text(
        "# SHAP解释图\n\n解释模型预测，不证明生物学因果；模型、目标、输出尺度见summary.json。\n\n"
        + "\n".join(f"![{name}]({name}.png)\n[PDF]({name}.pdf) · [SVG]({name}.svg)" for name in ("global_bar", "beeswarm"))
        + "\n作图数值见shap_values.csv及global_importance.csv；目视审图待完成。\n", encoding="utf-8")
    print(f"完成：报告写入 {args.output_dir}")


def main() -> int:
    args = parse_args()
    try:
        features, target_values, rows = validate_csv(args.input, args.target)
        task = infer_task(args.task, target_values)
        print(json.dumps({"rows": rows, "features": features, "task": task}, ensure_ascii=False))
        if not args.validate_only:
            run_report(args, task, features)
    except (OSError, RuntimeError, ValueError, IndexError) as exc:
        raise SystemExit(f"错误：{exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
