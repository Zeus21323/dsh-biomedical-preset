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
            "mode",
            "table",
            "permutations",
            "seed",
            "axis_reason",
            "min_units_per_side",
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
                    "mode",
                    "table",
                    "permutations",
                    "seed",
                    "axis_reason",
                    "min_units_per_side",
                }
            )
        ),
    )
    cfg = c.cfg
    mode = cfg.get("mode")
    need(mode in ("meta", "ordered_shift"), "mode需meta或ordered_shift")
    if mode == "meta":
        df = c.table(
            cfg["table"], ["study", "feature", "effect", "se", "independence_source"]
        )
        ids(df, ["study", "feature"])
        need(df.independence_source.str.strip().ne("").all(), "需独立性来源")
        df["effect"] = numeric(df.effect)
        df["se"] = numeric(df.se)
        need((df.se > 0).all(), "标准误须大于零")

        def pool(g):
            y = g.effect.to_numpy()
            v = g.se.to_numpy() ** 2
            w = 1 / v
            fixed = np.sum(w * y) / sum(w)
            Q = np.sum(w * (y - fixed) ** 2)
            k = len(y)
            denom = sum(w) - sum(w * w) / sum(w)
            tau = max(0, (Q - (k - 1)) / denom)
            wr = 1 / (v + tau)
            pooled = sum(wr * y) / sum(wr)
            se = np.sqrt(1 / sum(wr))
            return {
                "effect": pooled,
                "se": se,
                "ci_low": pooled - 1.96 * se,
                "ci_high": pooled + 1.96 * se,
                "tau2": tau,
                "Q": Q,
                "I2": max(0, (Q - k + 1) / Q) * 100 if Q > 0 else 0,
                "studies": k,
            }

        results = []
        loo = []
        for feature, g in df.groupby("feature", sort=True):
            need(len(g) >= 3, "每个特征随机效应汇总至少3个独立研究；更少时改描述性报告")
            results.append({"feature": feature, **pool(g)})
            for excluded in g.study:
                loo.append(
                    {
                        "feature": feature,
                        "excluded_study": excluded,
                        **pool(g[g.study != excluded]),
                    }
                )
        res = pd.DataFrame(results)
        c.save_table("meta_results.tsv", res)
        c.save_table("leave_one_out.tsv", loo)
        c.save_table("study_effects.tsv", df)
        plot = res.head(30)
        fig, ax = plt.subplots(
            figsize=(8, max(3, len(plot) * 0.45 + 1.5)), layout="constrained"
        )
        ax.errorbar(
            plot.effect,
            np.arange(len(plot)),
            xerr=[plot.effect - plot.ci_low, plot.ci_high - plot.effect],
            fmt="o",
            color="#337EA5",
        )
        ax.axvline(0, color="#888888", ls="--")
        ax.set_yticks(range(len(plot)), plot.feature)
        ax.set(
            xlabel="Random-effects pooled effect (normal 95% CI)",
            ylabel="Prespecified feature",
        )
        c.figure(
            fig,
            "state_meta",
            "DerSimonian–Laird随机效应与正态近似95%区间；研究少时区间可能过窄，需进一步稳健方法复核。主图最多显示按ID排序的前30项，完整结果与逐研究剔除分析均保留。",
        )
        return {
            "mode": mode,
            "features": len(res),
            "interpretation": [
                "仅合并同一对比方向、效应量纲和可比较状态的独立研究；独立性出处由代理核验，不由字符串自动证明。",
                "报告异质性及逐研究剔除影响；不以合并显著掩盖方向冲突，不将状态关联称为时间转变或因果。",
            ],
        }
    B = integer(cfg, "permutations", 99, 10000)
    seed = integer(cfg, "seed", 0, 2**32 - 1)
    need(
        isinstance(cfg.get("axis_reason"), str) and cfg["axis_reason"].strip(),
        "有序轴需真实时间/分期等依据",
    )
    minimum = integer(cfg, "min_units_per_side", 2, 10000)
    df = c.table(cfg["table"], ["study", "unit", "feature", "axis", "value"])
    ids(df, ["study", "unit", "feature"])
    df["value"] = numeric(df.value)
    df["axis"] = numeric(df.axis)
    need(
        (df.groupby(["study", "unit"]).axis.nunique() == 1).all(),
        "同一供体轴坐标不一致",
    )
    need(B * len(df) <= 50_000_000, "扫描置换工作量超过本地上限")
    rng = np.random.default_rng(seed)
    result = []
    for (study, feature), g in df.groupby(["study", "feature"], sort=True):
        g = g.sort_values("axis", kind="stable")
        a = g.axis.to_numpy()
        y = g.value.to_numpy()
        candidates = [
            i for i in range(minimum, len(y) - minimum + 1) if a[i - 1] < a[i]
        ]
        need(candidates, "没有满足独立单位数的候选分界")
        positions = np.asarray(candidates)

        def scan(values):
            # 中心化前缀和以线性代价计算与SSE差等价的组间平方和。
            prefix = np.cumsum(values - values.mean())
            left = prefix[positions - 1]
            right = prefix[-1] - left
            gains = (
                positions
                * (len(values) - positions)
                / len(values)
                * (left / positions - right / (len(values) - positions)) ** 2
            )
            j = int(np.argmax(gains))
            return max(0, float(gains[j])), candidates[j]

        gain, cut = scan(y)
        tolerance = 100 * np.finfo(float).eps * abs(gain)
        exceed = sum(scan(rng.permutation(y))[0] >= gain - tolerance for _ in range(B))
        informative = np.ptp(y) > 0 and gain > 0
        result.append(
            {
                "study": study,
                "feature": feature,
                "units": len(g),
                "cut_low": a[cut - 1] if informative else None,
                "cut_high": a[cut] if informative else None,
                "effect_after_minus_before": float(y[cut:].mean() - y[:cut].mean())
                if informative
                else 0,
                "sse_gain": gain,
                "pvalue": (exceed + 1) / (B + 1),
                "status": "exploratory_cut_interval" if informative else "no_variation",
            }
        )
    res = pd.DataFrame(result)
    res["padj"] = bh(res.pvalue)
    c.save_table("state_shift.tsv", res)
    c.save_table("ordered_input.tsv", df)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout="constrained")
    first = df[["study", "feature"]].drop_duplicates().iloc[0]
    g = df[(df.study == first.study) & (df.feature == first.feature)]
    ax.scatter(g.axis, g.value, color="#337EA5")
    ax.set(
        xlabel="Prespecified ordered axis",
        ylabel="State score",
        title=str(first.study) + " / " + str(first.feature),
    )
    c.figure(
        fig,
        "ordered_state",
        "展示按输入次序首个研究和特征的供体级观测；所有研究的扫描结果均在表内。分界区间是相邻观测轴值范围，不是置信区间。",
    )
    return {
        "mode": mode,
        "comparisons": len(res),
        "interpretation": [
            "已执行单阶跃SSE扫描，并在每次置换中重做整个分界搜索，BH覆盖本次全部研究×特征。",
            "这是探索性横断面有序轴关联，不是完整StateShiftAtlas算法、真实轨迹或因果转变。轴若由同一响应数据学习，当前置换不适用；需独立定义轴。",
            "跨队列复现需在独立研究固定发现阈值验证；本模式的每研究独立扫描不能声称外部验证。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
