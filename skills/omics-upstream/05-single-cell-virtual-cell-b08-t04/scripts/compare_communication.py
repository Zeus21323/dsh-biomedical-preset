"""Donor-aware comparison of native CellChat exports; no imputation of untested LR."""
from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from render_communication import read_tsv, write_tsv, write_json


KEY = ("source", "target", "interaction")


def bh_adjust(values):
    values = np.asarray(values, dtype=float)
    if not len(values):
        return values
    order = np.argsort(values)
    ranked = values[order] * len(values) / np.arange(1, len(values) + 1)
    result = np.empty(len(values))
    result[order] = np.minimum(1, np.minimum.accumulate(ranked[::-1])[::-1])
    return result


def permutation_p(a, b, paired, seed=1, iterations=9999):
    """Two-sided difference in means. Exact enumeration when practical."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if not len(a) or not len(b) or (paired and len(a) != len(b)):
        raise ValueError("无效比较样本")
    observed = abs(b.mean() - a.mean())
    rng = np.random.default_rng(seed)
    tolerance = 1e-12 * max(1, observed)
    if paired:
        delta = b - a
        count = 2 ** len(delta)
        exact = count <= iterations
        permutations = itertools.product((-1, 1), repeat=len(delta)) if exact else (
            rng.choice([-1, 1], len(delta)) for _ in range(iterations))
        more = sum(abs(np.mean(delta * s)) >= observed - tolerance for s in permutations)
    else:
        pooled = np.r_[a, b]
        count = math.comb(len(pooled), len(a))
        exact = count <= iterations
        selections = itertools.combinations(range(len(pooled)), len(a)) if exact else (
            rng.choice(len(pooled), len(a), replace=False) for _ in range(iterations))
        more = 0
        for chosen in selections:
            mask = np.zeros(len(pooled), dtype=bool)
            mask[list(chosen)] = True
            more += abs(pooled[~mask].mean() - pooled[mask].mean()) >= observed - tolerance
    return float(more / count if exact else (more + 1) / (iterations + 1))


def compare_candidates(bundles, cfg, *, allow_signed_scores=False):
    """Return all candidate results, not just the displayed top hits."""
    conditions = cfg["conditions"]
    if len(conditions) != 2 or len(set(conditions)) != 2:
        raise ValueError("比较需明确两个不同条件，顺序为参考、比较")
    paired = bool(cfg.get("paired", False))
    minimum = int(cfg.get("min_donors", 3))
    if minimum < 3:
        raise ValueError("本比较脚本要求 min_donors>=3；少于此数量仅能使用描述性图")
    if int(cfg.get("permutations", 9999)) < 99:
        raise ValueError("permutations 必须至少为99")
    sample_ids, donor_conditions, annotations, observations = set(), set(), {}, defaultdict(dict)
    signatures, databases, versions, parameters = set(), set(), set(), set()
    samples = []
    for bundle in bundles:
        p, rows = bundle["provenance"], bundle["candidates"]
        sample = p["config"]
        if sample["condition"] not in conditions:
            continue
        if p["statistical_unit"] != "donor":
            raise ValueError("条件统计要求独立供体，池化对象只能描述性展示")
        identity = (sample["donor"], sample["condition"])
        if sample["sample"] in sample_ids or identity in donor_conditions:
            raise ValueError("重复 sample 或供体-条件记录；技术重复须先按设计合并")
        sample_ids.add(sample["sample"]); donor_conditions.add(identity)
        samples.append(sample)
        signatures.add(p.get("comparison_signature"))
        databases.add(p["database_sha256"]); versions.add(p["method_version"])
        if not p.get("comparison_parameters"):
            raise ValueError("缺少已核实的原始推断参数，不能进行供体比较")
        parameters.add(json.dumps(p["comparison_parameters"], sort_keys=True))
        seen = set()
        for row in rows:
            key = tuple(row[k] for k in KEY)
            if key in seen:
                raise ValueError("同一样本含重复 source-target-LR")
            seen.add(key)
            annotation = tuple(row[k] for k in ("ligand", "receptor", "pathway"))
            if key in annotations and annotations[key] != annotation:
                raise ValueError("样本间 LR 注释不一致")
            annotations[key] = annotation
            if row["tested"] not in ("TRUE", "FALSE", "True", "False", True, False):
                raise ValueError("tested 必须为布尔值")
            if row["tested"] in ("TRUE", "True", True):
                value = float(row["score"])
                if not math.isfinite(value) or (value < 0 and not allow_signed_scores):
                    raise ValueError("原生分数必须有限；非负度量不允许负值")
                observations[key][identity] = (value, row["supported"] in ("TRUE", "True", True))
    if len(signatures) != 1 or not next(iter(signatures), None) or len(databases) != 1 or len(versions) != 1 or len(parameters) != 1:
        raise ValueError("需一致的数据库、方法版本及非空 comparison_signature；先核实并协调表达层、推断及过滤参数")
    donor_sets = [{s["donor"] for s in samples if s["condition"] == condition} for condition in conditions]
    if not paired and donor_sets[0] & donor_sets[1]:
        raise ValueError("两条件存在相同供体，必须使用配对设计或外部适用模型")
    results = []
    for key in sorted(annotations):
        obs = observations[key]
        available = [{d for d, condition in obs if condition == c} for c in conditions]
        donors = [sorted(available[0] & available[1])] * 2 if paired else [sorted(x) for x in available]
        a, b = [[obs[(d, c)][0] for d in ds] for ds, c in zip(donors, conditions)]
        support = [sum(obs[(d, c)][1] for d in ds) / len(ds) if ds else None for ds, c in zip(donors, conditions)]
        row = dict(zip(KEY, key), **dict(zip(("ligand", "receptor", "pathway"), annotations[key])),
                   n_reference=len(a), n_comparison=len(b), mean_reference=float(np.mean(a)) if a else None,
                   mean_comparison=float(np.mean(b)) if b else None, support_reference=support[0], support_comparison=support[1],
                   effect=float(np.mean(b) - np.mean(a)) if a and b else None,
                   p_value=None, fdr=None, status="insufficient_tested_donors")
        if min(len(a), len(b)) >= minimum:
            row["p_value"] = permutation_p(a, b, paired, int(cfg.get("seed", 1)), int(cfg.get("permutations", 9999)))
            row["status"] = "tested"
        results.append(row)
    tested = [r for r in results if r["status"] == "tested"]
    for row, q in zip(tested, bh_adjust([r["p_value"] for r in tested])):
        row["fdr"] = float(q)
    # FDR calculated before any focus/display filter. Never rename ranks as P values.
    return results, observations


def render_comparison(bundles, cfg, out, save):
    import matplotlib.pyplot as plt
    out = Path(out)
    rows, observations = compare_candidates(bundles, cfg)
    fields = [*KEY, "ligand", "receptor", "pathway", "n_reference", "n_comparison", "mean_reference", "mean_comparison",
              "support_reference", "support_comparison", "effect", "p_value", "fdr", "status"]
    write_tsv(out / "condition_candidates.tsv", rows, fields)
    tested = [r for r in rows if r["status"] == "tested"]
    focus = cfg.get("focus_sources", [])
    display = [r for r in rows if r["effect"] is not None and (not focus or r["source"] in focus)]
    display.sort(key=lambda r: (r["fdr"] if r["fdr"] is not None else 2, -abs(r["effect"]), *[r[k] for k in KEY]))
    selected = display[:int(cfg.get("top_lr", 12))]
    write_json(out / "condition_selection.json", dict(conditions=cfg["conditions"], paired=cfg.get("paired", False),
               hypothesis_count=len(tested), selection_rule="全体可检验候选BH后按FDR、绝对效应排序；未检验仅描述", selected=selected,
               limits="原生推断分数的供体级比较；需满足供体独立/配对交换性，无协变量调整，非因果结论"))
    if not selected:
        return dict(status="not_applicable", reason="两个条件没有具有可比较分数的候选", hypothesis_count=len(tested))
    for start in range(0, len(selected), 8):
        page = selected[start:start + 8]
        fig, ax = plt.subplots(figsize=(183/25.4, 130/25.4), layout="constrained")
        labels = [f"{r['source']} → {r['target']}\n{r['ligand']}–{r['receptor']}" for r in page]
        effects = [r["effect"] for r in page]
        colors = ["#0072B2" if r["fdr"] is not None and r["fdr"] <= cfg.get("fdr", .05) else "#999999" for r in page]
        ax.barh(range(len(page)), effects, color=colors)
        ax.set_yticks(range(len(page)), labels); ax.invert_yaxis(); ax.axvline(0, color="black", lw=.5)
        ax.set_xlabel(f"Mean inferred score: {cfg['conditions'][1]} − {cfg['conditions'][0]}")
        ax.set_title("Blue: BH FDR ≤ threshold; grey: descriptive / not significant")
        save(f"condition_effects_{start//8+1:02d}", fig, "condition_candidates.tsv",
             "效应为比较条件减参考条件；BH覆盖全部满足供体数的候选，非仅图示候选。无协变量调整。")
    # Native raw scores, with each donor visible, on a shared y-axis for each candidate.
    for index, row in enumerate(selected[:6]):
        fig, ax = plt.subplots(figsize=(89/25.4, 78/25.4), layout="constrained")
        obs = observations[tuple(row[k] for k in KEY)]
        palette = ["#0072B2", "#D55E00"]
        for i, condition in enumerate(cfg["conditions"]):
            ds = sorted(d for d, c in obs if c == condition)
            values = [obs[(d, condition)][0] for d in ds]
            ax.scatter(np.arange(len(values)) * .02 - len(values)*.01 + i, values, color=palette[i], s=12)
            if values:
                ax.plot([i-.18, i+.18], [np.mean(values)]*2, color="black", lw=.8)
        if cfg.get("paired", False):
            donors = sorted({d for d, c in obs if (d, cfg["conditions"][0]) in obs and (d, cfg["conditions"][1]) in obs})
            for d in donors:
                ax.plot([0, 1], [obs[(d, c)][0] for c in cfg["conditions"]], color="grey", lw=.4, alpha=.4, zorder=0)
        ax.set_xticks([0, 1], cfg["conditions"]); ax.set_ylabel("Native inferred score")
        ax.set_title(f"{row['source']} → {row['target']}\n{row['ligand']}–{row['receptor']}")
        save(f"condition_donors_{index+1:02d}", fig, "condition_candidates.tsv", "每点为独立供体；横线为均值，配对设计连线连接同一供体。")
    return dict(status="generated", hypothesis_count=len(tested), significant_count=sum(r["fdr"] <= cfg.get("fdr", .05) for r in tested))
