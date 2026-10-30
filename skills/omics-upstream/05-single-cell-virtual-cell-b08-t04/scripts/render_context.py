"""Conditional panels from measured embeddings, defined scores and sample outcomes."""
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from compare_communication import bh_adjust, permutation_p
from render_communication import read_tsv, write_tsv


def render_context(cfg, base, out, save):
    import matplotlib.pyplot as plt
    results = {}
    out, base = Path(out), Path(base)
    def load(name, fields):
        path = Path(cfg[name]["path"])
        if not path.is_absolute():
            path = base / path
        rows = read_tsv(path, fields)
        if not rows:
            raise ValueError(f"{name}: 空输入")
        return rows
    def numbers(rows, fields):
        for row in rows:
            for field in fields:
                row[field] = float(row[field])
                if not np.isfinite(row[field]):
                    raise ValueError(f"{field} 含非有限值")
    for name in ("embedding", "functional_scores", "clinical_association"):
        if name not in cfg:
            results[name] = dict(status="not_applicable", reason={
                "embedding": "未提供现有降维坐标和状态标签", "functional_scores": "未提供定义明确的样本级功能评分",
                "clinical_association": "未提供按独立供体匹配的特征与结局"}[name])
            continue
        try:
            if name == "embedding":
                definition = cfg[name].get("method")
                if not definition:
                    raise ValueError("须记录坐标方法；不能将未知坐标标成 UMAP")
                rows = load(name, ["cell", "x", "y", "label"]); numbers(rows, ["x", "y"])
                if len({r["cell"] for r in rows}) != len(rows):
                    raise ValueError("重复细胞坐标")
                write_tsv(out / "embedding_source.tsv", rows, ["cell", "x", "y", "label"])
                labels = sorted({r["label"] for r in rows})
                if len(labels) > 16:
                    raise ValueError("超过16种状态；请按研究问题分组或拆面板，不自动合并标签")
                fig, ax = plt.subplots(figsize=(183/25.4, 130/25.4), layout="constrained")
                colors = cfg[name].get("colors", {})
                for i, label in enumerate(labels):
                    subset = [r for r in rows if r["label"] == label]
                    ax.scatter([r["x"] for r in subset], [r["y"] for r in subset], s=1, alpha=.6, label=label,
                               color=colors.get(label, plt.get_cmap("tab20")(i)), linewidths=0)
                ax.set_xlabel(f"{definition} 1"); ax.set_ylabel(f"{definition} 2")
                ax.legend(loc="center left", bbox_to_anchor=(1, .5), markerscale=3, frameon=False)
                save(name, fig, "embedding_source.tsv", f"复用输入的 {definition} 坐标和状态标签；通讯分析不产生或验证这些状态。")
            elif name == "functional_scores":
                if not cfg[name].get("score_definition"):
                    raise ValueError("功能评分须说明基因集、来源、算法及聚合单位 score_definition")
                rows = load(name, ["sample", "donor", "condition", "cell_type", "score_name", "score"])
                numbers(rows, ["score"])
                seen = set(); sample_design = {}
                for row in rows:
                    identity = (row["donor"], row["condition"])
                    if row["sample"] in sample_design and sample_design[row["sample"]] != identity:
                        raise ValueError("同一样本的供体或条件信息矛盾")
                    sample_design[row["sample"]] = identity
                    key = tuple(row[k] for k in ("donor", "condition", "cell_type", "score_name"))
                    if key in seen:
                        raise ValueError("每供体-条件-细胞群-评分只能一个值；不能将细胞当重复")
                    seen.add(key)
                write_tsv(out / "functional_scores_source.tsv", rows, list(rows[0]))
                groups = defaultdict(list)
                for row in rows:
                    groups[(row["cell_type"], row["score_name"])].append(row)
                for i, ((cell, score), group) in enumerate(sorted(groups.items())):
                    conditions = sorted({r["condition"] for r in group})
                    fig, ax = plt.subplots(figsize=(89/25.4, 78/25.4), layout="constrained")
                    for j, c in enumerate(conditions):
                        vals = [r["score"] for r in group if r["condition"] == c]
                        ax.scatter(j + np.linspace(-.08, .08, len(vals)), vals, s=12)
                        ax.plot([j-.15, j+.15], [np.mean(vals)]*2, color="black", lw=.7)
                    ax.set_xticks(range(len(conditions)), conditions, rotation=25); ax.set_ylabel(score); ax.set_title(cell)
                    save(f"functional_scores_{i+1:02d}", fig, "functional_scores_source.tsv",
                         "每点为一个供体在相应条件与细胞群的评分；横线为均值。仅描述，不自动添加显著性。" + cfg[name]["score_definition"])
            else:
                definition = cfg[name].get("outcome_definition")
                if not definition:
                    raise ValueError("须提供结局的测量/预测来源 outcome_definition")
                rows = load(name, ["donor", "feature", "feature_value", "outcome", "outcome_value"])
                numbers(rows, ["feature_value", "outcome_value"])
                grouped = defaultdict(list); seen = set()
                for row in rows:
                    key = (row["donor"], row["feature"], row["outcome"])
                    if key in seen:
                        raise ValueError("同一关联中每供体只能出现一次；重复测量需另用适用模型")
                    seen.add(key); grouped[(row["feature"], row["outcome"])].append(row)
                stats = []
                for (feature, outcome), group in sorted(grouped.items()):
                    x = [r["feature_value"] for r in group]; y = [r["outcome_value"] for r in group]
                    valid = len(x) >= 4 and len(set(x)) > 1 and len(set(y)) > 1
                    r = float(spearmanr(x, y).statistic) if valid else None
                    # Permutation correlation, avoiding the small-n asymptotic P approximation.
                    p = None
                    if valid:
                        rng = np.random.default_rng(int(cfg[name].get("seed", 1)))
                        iterations = int(cfg[name].get("permutations", 9999))
                        if iterations < 99:
                            raise ValueError("关联置换次数至少99")
                        from scipy.stats import rankdata
                        rx, ry = rankdata(x), rankdata(y)
                        more = sum(abs(np.corrcoef(rx, rng.permutation(ry))[0, 1]) >= abs(r)-1e-12 for _ in range(iterations))
                        p = (more+1)/(iterations+1)
                    stats.append(dict(feature=feature, outcome=outcome, n=len(x), rho=r, p_value=p, fdr=None))
                tested = [r for r in stats if r["p_value"] is not None]
                for row, q in zip(tested, bh_adjust([r["p_value"] for r in tested])):
                    row["fdr"] = float(q)
                write_tsv(out / "clinical_statistics.tsv", stats, ["feature", "outcome", "n", "rho", "p_value", "fdr"])
                write_tsv(out / "clinical_source.tsv", rows, list(rows[0]))
                for i, row in enumerate(stats):
                    group = grouped[(row["feature"], row["outcome"])]
                    fig, ax = plt.subplots(figsize=(89/25.4, 78/25.4), layout="constrained")
                    ax.scatter([r["feature_value"] for r in group], [r["outcome_value"] for r in group], s=12, color="#0072B2")
                    ax.set_xlabel(row["feature"]); ax.set_ylabel(row["outcome"])
                    ax.set_title(f"n={row['n']}; rho={row['rho']:.2g}; FDR={row['fdr']:.2g}" if row["fdr"] is not None else f"n={row['n']}; descriptive only")
                    save(f"clinical_association_{i+1:02d}", fig, "clinical_source.tsv", "供体级 Spearman 相关，双侧随机置换 P；BH覆盖本次全部可检验关联，无协变量调整。" + definition)
            results[name] = dict(status="generated")
        except Exception as exc:
            results[name] = dict(status="failed", reason=str(exc))
    return results
