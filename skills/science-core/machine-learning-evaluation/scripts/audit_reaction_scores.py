#!/usr/bin/env python3
"""审计已有患者×反应数组，输出负面对照诊断；不训练MetaGNN。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def auc(y, score):
    import numpy as np
    y, s = np.asarray(y).ravel(), np.asarray(score).ravel()
    positive = y == 1
    n1, n0 = int(positive.sum()), int((~positive).sum())
    if not n1 or not n0:
        return None
    order = np.argsort(s, kind="stable")
    ranks = np.empty(len(s), dtype=float)
    start = 0
    while start < len(s):
        stop = start + 1
        while stop < len(s) and s[order[stop]] == s[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2
        start = stop
    return float((ranks[positive].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def inspect(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as z:
        data = {k: z[k] for k in z.files}
    for key in ("patients", "reactions", "features", "labels", "predictions"):
        require(key in data, f"缺少数组：{key}")
    for key in ("patients", "reactions"):
        a = data[key]
        require(a.ndim == 1 and a.dtype.kind in "US" and len(a) == len(set(a.tolist())) and len(a) >= 2,
                f"{key}必须为至少2个唯一字符串ID")
        require(all(str(x).strip() for x in a), f"{key}含空标识")
    shape = (len(data["patients"]), len(data["reactions"]))
    for key in ("features", "labels", "predictions", "zero_predictions", "permuted_predictions"):
        if key not in data:
            continue
        a = data[key]
        require(a.shape == shape and a.dtype.kind in "biuf" and np.isfinite(a).all(), f"{key}形状/实数/有限性错误")
    x, y, pred = (data[k].astype(float) for k in ("features", "labels", "predictions"))
    require(np.isin(y, [0, 1]).all(), "labels必须为0/1；缺失标签不能强行补零")
    flags = []
    if np.all(x == 0):
        flags.append("actual_features_all_zero")
    if np.all(np.ptp(x, axis=0) == 0):
        flags.append("features_patient_invariant")
    invariant_labels = np.ptp(y, axis=0) == 0
    if invariant_labels.any():
        flags.append("patient_split_may_not_prevent_reaction_identity_memory")
    scale = max(float(np.std(pred)), 1e-12)
    spread = float(np.mean(np.std(pred, axis=0)))
    if spread <= 1e-8 * scale:
        flags.append("predictions_patient_invariant")
    checks = []
    for key in ("zero_predictions", "permuted_predictions"):
        if key not in data:
            checks.append({"check": key, "status": "not_provided", "mean_absolute_change": None})
        else:
            delta = float(np.mean(np.abs(pred - data[key])))
            checks.append({"check": key, "status": "observed", "mean_absolute_change": delta})
            if delta <= 1e-8 * scale:
                flags.append(key + "_nearly_unchanged")
    if "thresholds" in data:
        threshold = data["thresholds"]
        require(threshold.shape == (shape[1],) and np.isfinite(threshold).all(), "thresholds应为每反应一个有限阈值")
        agreement = float(np.mean((x >= threshold[None, :]) == y))
        checks.append({"check": "declared_input_threshold_ge", "status": "observed", "agreement": agreement})
        if agreement == 1:
            flags.append("labels_exactly_reproduced_by_declared_input_threshold")
    metrics = [{"comparison": "model", "estimate": auc(y, pred)},
               {"comparison": "raw_input", "estimate": auc(y, x)}]
    for key in ("zero_predictions", "permuted_predictions"):
        if key in data:
            metrics.append({"comparison": key, "estimate": auc(y, data[key])})
    return {"status": "diagnostic_only", "shape": list(shape), "flags": flags, "checks": checks,
            "invariant_label_fraction": float(invariant_labels.mean()), "mean_patient_output_sd": spread,
            "metrics": metrics, "metric_unit": "pooled_patient_reaction_descriptive_AUROC",
            "not_checked": ["label_provenance_without_source_code", "training_split_integrity",
                            "independent_biological_ground_truth", "retrained_label_shuffle", "patient_level_confidence_intervals"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        require(not a.out_dir.exists() and not a.out_dir.is_symlink(), "输出目录已存在")
        result = inspect(a.input)
        with a.input.open("rb") as f:
            result["input_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
        a.out_dir.mkdir(parents=True)
        (a.out_dir / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (a.out_dir / "metrics.tsv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["comparison", "estimate"], delimiter="\t")
            w.writeheader()
            w.writerows(result["metrics"])
        (a.out_dir / "report.md").write_text("# 模型有效性诊断\n\n" +
            "此检查不认证模型有效，不提供患者层置信区间；AUROC以患者×反应合并计算，仅用于描述性比较。\n\n" +
            "发现的警告：" + ("、".join(result["flags"]) or "未触发已实现规则；不表示其他风险已排除") +
            "\n\n未完成检查：" + "、".join(result["not_checked"]) +
            "\n\n[审计详情](audit.json) · [描述性指标](metrics.tsv)\n", encoding="utf-8")
        print(f"诊断完成：{a.out_dir}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, ImportError) as e:
        print(f"审计失败：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
