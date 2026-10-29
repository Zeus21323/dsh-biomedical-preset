#!/usr/bin/env python3
"""代理准备配置后执行；输入只读，输出必须在仓库外的新目录。"""

from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import scipy
from scipy import stats
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, ft2font
from matplotlib.text import Text

VERSION = "1.0.0"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def unique_json(pairs):
    out = {}
    for k, v in pairs:
        need(k not in out, "JSON字段重复：" + k)
        out[k] = v
    return out


def load_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=unique_json,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("JSON非有限数值")),
    )


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def dump(path, value):
    path.write_text(
        json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def numeric(values):
    a = np.asarray(values, dtype=float)
    need(np.isfinite(a).all(), "数值有缺失或非有限值；不能静默补零")
    return a


def integer(cfg, key, low, high):
    v = cfg.get(key)
    need(type(v) is int and low <= v <= high, f"{key}需要{low}到{high}的整数")
    return v


def ids(df, keys):
    need(not df.duplicated(keys).any(), "标识组合重复：" + ",".join(keys))
    for k in keys:
        need(
            all(isinstance(x, str) and x.strip() == x and x for x in df[k]),
            "标识空或含首尾空白：" + k,
        )


def bh(p):
    p = numeric(p)
    need(((p >= 0) & (p <= 1)).all(), "p值超范围")
    order = np.argsort(p, kind="stable")
    q = np.empty(len(p))
    q[order] = np.minimum.accumulate(
        (p[order] * len(p) / np.arange(1, len(p) + 1))[::-1]
    )[::-1].clip(0, 1)
    return q


class Context:
    def __init__(self, config, out):
        self.config = Path(config).resolve()
        self.cfg = load_json(self.config)
        need(isinstance(self.cfg, dict), "配置需为JSON对象")
        for key in ("question", "parameter_reason", "evidence_notes"):
            need(
                isinstance(self.cfg.get(key), str) and self.cfg[key].strip(),
                "缺少研究说明：" + key,
            )
        path = Path(out)
        need(not path.exists() and not path.is_symlink(), "输出已存在，拒绝覆盖")
        self.out = path.resolve()
        for parent in Path(__file__).resolve().parents:
            if (parent / ".speedskills").is_dir() and (parent / "plugins").is_dir():
                need(
                    self.out != parent and parent not in self.out.parents,
                    "数据与结果必须保存在仓库外",
                )
        self.hashes = {"config": sha(self.config), "script": sha(__file__)}
        self.figures = []
        self.out.mkdir(parents=True)
        self.record = {
            "status": "running",
            "version": VERSION,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": self.cfg,
            "input_sha256": self.hashes,
            "environment": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scipy": scipy.__version__,
                "matplotlib": matplotlib.__version__,
            },
        }
        dump(self.out / "run_record.json", self.record)

    def path(self, name):
        need(isinstance(name, str) and name, "文件路径为空")
        path = (self.config.parent / name).resolve()
        need(path.is_file(), "文件不存在：" + name)
        need(
            path.stat().st_size <= 1_000_000_000,
            "输入超过本地适配器1GB保护上限；需另行分块适配",
        )
        self.hashes[str(path)] = sha(path)
        return path

    def table(self, name, required):
        path = self.path(name)
        sep = "\t" if path.suffix == ".tsv" else ","
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=sep)
            header = reader.fieldnames or []
            need(header and len(header) == len(set(header)), "表头为空或重复")
            rows = list(reader)
        need(
            rows and set(required) <= set(header), "表为空或缺列：" + ",".join(required)
        )
        need(
            all(None not in r and all(v is not None for v in r.values()) for r in rows),
            "记录列数不一致",
        )
        return pd.DataFrame(rows, columns=header)

    def save_table(self, name, table):
        pd.DataFrame(table).to_csv(self.out / name, sep="\t", index=False, na_rep="")

    def figure(self, fig, name, caption):
        texts = [t for t in fig.findobj(Text) if t.get_text()]
        required = set("".join(t.get_text() for t in texts))
        requested = self.cfg.get("font")
        fonts = (
            [requested]
            if requested
            else ["DejaVu Sans", "Arial Unicode MS", "PingFang SC", "Noto Sans CJK SC"]
        )
        selected = None
        for font in fonts:
            try:
                p = font_manager.findfont(
                    font_manager.FontProperties(family=font), fallback_to_default=False
                )
                chars = ft2font.FT2Font(p).get_charmap()
                if all(ord(c) in chars or c.isspace() for c in required):
                    selected = font
                    break
            except ValueError:
                continue
        need(selected, "没有覆盖图中文字的字体；代理需安装/指定可用字体，不能丢字")
        for t in texts:
            t.set_fontfamily(selected)
        matplotlib.rcParams.update({"pdf.fonttype": 42, "svg.fonttype": "none"})
        fig.canvas.draw()
        for ext in ("pdf", "svg", "png"):
            save_figure(fig, self.out / f"{name}.{ext}", dpi=400)
        plt.close(fig)
        self.figures.append({"name": name, "caption": caption, "font": selected})

    def finish(self, summary):
        dump(self.out / "summary.json", summary)
        text = [
            "# " + self.cfg["question"],
            "",
            self.cfg["evidence_notes"],
            "",
            "## 本次实际结果",
            "",
            "详见 [结构化结果](summary.json) 与运行记录；下列结论仅对应实际执行模式。",
            "",
        ]
        text += [str(x) + "\n" for x in summary.get("interpretation", [])]
        text += ["## 图件与限制", ""]
        for f in self.figures:
            n = f["name"]
            text += [
                f"![{n}]({n}.png)",
                "",
                f["caption"],
                "",
                f"[PDF]({n}.pdf) · [SVG]({n}.svg)",
                "",
            ]
        text += [
            "参数依据：" + self.cfg["parameter_reason"],
            "",
            "交付前需核对统计单位、数值、阴性与冲突、替代解释及最终尺寸下的字体和布局。自动摘要不是完整机制论证。",
        ]
        (self.out / "report.md").write_text("\n".join(text) + "\n", encoding="utf-8")
        self.record.update(
            status="completed_visual_and_scientific_review_required",
            completed_at=datetime.now(timezone.utc).isoformat(),
            figures=self.figures,
            output_sha256={
                p.name: sha(p)
                for p in self.out.iterdir()
                if p.is_file() and p.name != "run_record.json"
            },
        )
        dump(self.out / "run_record.json", self.record)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    context = None
    try:
        context = Context(args.config, args.out_dir)
        context.finish(analyze(context))
        print("完成：" + str(context.out) + "；需按Skill继续科学解读和图件检查")
        return 0
    except Exception as error:
        if context:
            context.record.update(status="failed", error=str(error))
            dump(context.out / "run_record.json", context.record)
        print("分析失败：" + str(error), file=sys.stderr)
        return 2


def analyze(c):
    need(
        not set(c.cfg)
        - {
            "question",
            "parameter_reason",
            "evidence_notes",
            "font",
            "permutations",
            "seed",
            "design",
            "groups",
            "table",
            "alpha",
            "known_null_features",
            "known_null_reason",
        },
        "配置有未知字段，拒绝静默忽略："
        + str(
            sorted(
                set(c.cfg)
                - {
                    "question",
                    "parameter_reason",
                    "evidence_notes",
                    "font",
                    "permutations",
                    "seed",
                    "design",
                    "groups",
                    "table",
                    "alpha",
                    "known_null_features",
                    "known_null_reason",
                }
            )
        ),
    )
    cfg = c.cfg
    B = integer(cfg, "permutations", 99, 100000)
    seed = integer(cfg, "seed", 0, 2**32 - 1)
    mode = cfg.get("design")
    need(
        mode in ("independent", "blocked", "paired"),
        "design需independent/blocked/paired",
    )
    groups = cfg.get("groups")
    need(
        isinstance(groups, list) and len(groups) == 2 and len(set(groups)) == 2,
        "需按对照、病例顺序指定两组",
    )
    df = c.table(
        cfg["table"],
        ["unit", "group", "feature", "value"]
        + (["block"] if mode != "independent" else []),
    )
    ids(df, ["unit", "feature"])
    df["value"] = numeric(df.value)
    need(set(df.group) == set(groups), "实际分组不等于预设分组")
    need(
        (df.groupby("unit").group.nunique() == 1).all(),
        "同一独立单位被放入两组；配对数据需不同unit并共享block",
    )
    if mode != "independent":
        need((df.groupby("unit").block.nunique() == 1).all(), "同一unit的block不一致")
    meta = df.drop_duplicates("unit").set_index("unit")
    mat = df.pivot(index="unit", columns="feature", values="value").reindex(meta.index)
    need(not mat.isna().any().any(), "每个unit须有完整预先定义特征；不能默默删行或补零")
    x = numeric(mat.to_numpy())
    labels = (meta.group == groups[1]).to_numpy()
    need(min(labels.sum(), (~labels).sum()) >= 2, "每组至少两个独立单位")
    need(
        B * x.size <= 200_000_000, "置换工作量超本地保护上限；需有依据地分块或改变方案"
    )
    rng = np.random.default_rng(seed)
    blocks = (
        [np.arange(len(meta))]
        if mode == "independent"
        else [np.flatnonzero(meta.block.to_numpy() == b) for b in meta.block.unique()]
    )
    need(
        all(labels[ix].any() and (~labels[ix]).any() for ix in blocks),
        "每个交换块须同时含两组；完全混杂不能靠置换修复",
    )
    if mode == "paired":
        need(all(len(ix) == 2 for ix in blocks), "配对设计每块恰好两个独立unit")

    def effect(y):
        if mode == "paired":
            return np.mean(
                [x[ix[y[ix]]][0] - x[ix[~y[ix]]][0] for ix in blocks], axis=0
            )
        return x[y].mean(axis=0) - x[~y].mean(axis=0)

    observed = effect(labels)
    exceed = np.zeros(x.shape[1], dtype=int)
    globalnull = []
    for _ in range(B):
        shuffled = labels.copy()
        for ix in blocks:
            shuffled[ix] = rng.permutation(labels[ix])
        effect_null = effect(shuffled)
        tolerance = 100 * np.finfo(float).eps * np.abs(observed)
        exceed += np.abs(effect_null) >= np.abs(observed) - tolerance
        globalnull.append(float(np.max(np.abs(effect_null))))
    p = (exceed + 1) / (B + 1)
    q = bh(p)
    result = pd.DataFrame(
        {
            "feature": mat.columns,
            "effect_group2_minus_group1": observed,
            "pvalue": p,
            "padj": q,
        }
    )
    c.save_table("permutation_results.tsv", result)
    c.save_table(
        "null_max_abs_effect.tsv",
        {"permutation": range(1, B + 1), "max_abs_effect": globalnull},
    )
    alpha = float(cfg.get("alpha", 0.05))
    need(0 < alpha < 1, "alpha超范围")
    known = cfg.get("known_null_features", [])
    need(
        isinstance(known, list)
        and len(set(known)) == len(known)
        and set(known) <= set(mat.columns),
        "known_null_features需唯一且在数据中",
    )
    if known:
        need(
            cfg.get("known_null_reason"),
            "已知零假设特征须有外部依据，不能按不显著结果挑选",
        )
    nullrows = result[result.feature.isin(known)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    axes[0].hist(p, bins=np.linspace(0, 1, 11), color="#337EA5", edgecolor="white")
    axes[0].set(
        xlabel="Permutation P (all prespecified features)", ylabel="Feature count"
    )
    axes[1].hist(globalnull, bins=30, color="#AAAAAA")
    axes[1].axvline(np.max(np.abs(observed)), color="#B54E46")
    axes[1].set(xlabel="Max absolute mean difference", ylabel="Permutation count")
    c.figure(
        fig,
        "null_calibration",
        "以独立单位在允许的块内置换标签；红线为原始最大绝对均值差。所有特征p值混合分布不能直接诊断假阳性率；已知零假设集合单独统计。最大值图要求特征量纲可比，否则只作运行诊断。",
    )
    return {
        "design": mode,
        "units": len(meta),
        "features": len(mat.columns),
        "permutations": B,
        "minimum_p": 1 / (B + 1),
        "known_null_count": len(nullrows),
        "known_null_raw_p_rejection_fraction": float((nullrows.pvalue < alpha).mean())
        if len(nullrows)
        else None,
        "interpretation": [
            f"实际使用{len(meta)}个独立单位、{len(mat.columns)}个特征、{B}次置换；预设alpha={alpha:g}下{int((q < alpha).sum())}项BH校正后低于阈值，结果是否可信仍取决于交换性及独立性。",
            "已实际执行两侧均值差置换及BH校正，保留全部特征；小p值精度受置换次数限制。",
            "一次已知零集合的拒绝比例不是总体FDR估计。配对/分块交换性需设计支持；本脚本不替代含混杂调整的模型。",
            "这不是机器学习全流程标签泄漏审计：如模型含筛选、调参或训练，必须在每次置换内重做相应步骤并使用现有模型评估分支。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
