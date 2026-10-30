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
            "radii",
            "bootstraps",
            "seed",
            "coordinate_unit",
            "labels",
            "table",
            "max_edges",
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
                    "radii",
                    "bootstraps",
                    "seed",
                    "coordinate_unit",
                    "labels",
                    "table",
                    "max_edges",
                }
            )
        ),
    )
    from scipy.spatial import cKDTree

    cfg = c.cfg
    radii = numeric(cfg.get("radii", []))
    need(
        len(radii) > 1
        and len(radii) <= 30
        and (radii > 0).all()
        and len(set(radii)) == len(radii),
        "需2至30个不同正半径",
    )
    radii = np.sort(radii)
    B = integer(cfg, "bootstraps", 100, 10000)
    seed = integer(cfg, "seed", 0, 2**32 - 1)
    need(
        isinstance(cfg.get("coordinate_unit"), str) and cfg["coordinate_unit"].strip(),
        "必须说明坐标单位",
    )
    labels = cfg.get("labels")
    need(
        isinstance(labels, list) and len(labels) == 2 and len(set(labels)) == 2,
        "需两个不同目标细胞标签",
    )
    df = c.table(cfg["table"], ["donor", "slice", "cell", "x", "y", "label"])
    ids(df, ["donor", "slice", "cell"])
    df["x"] = numeric(df.x)
    df["y"] = numeric(df.y)
    results = []
    first = None
    max_edges = integer(cfg, "max_edges", 1, 2000000)
    for (donor, slice_id), g in df.groupby(["donor", "slice"], sort=True):
        coords = g[["x", "y"]].to_numpy()
        tree = cKDTree(coords)
        # count_neighbors包括自配对和双向边；先限制规模，再生成边集合。
        count = (int(tree.count_neighbors(tree, float(max(radii)))) - len(g)) // 2
        need(count <= max_edges, "邻接图超max_edges，需调整预先确定的尺度/采用分块算法")
        edges = tree.query_pairs(float(max(radii)), output_type="ndarray")
        dist = (
            np.linalg.norm(coords[edges[:, 0]] - coords[edges[:, 1]], axis=1)
            if len(edges)
            else np.array([])
        )
        lab = g.label.to_numpy()
        for r in radii:
            e = edges[dist <= r]
            a = lab[e[:, 0]]
            b = lab[e[:, 1]]
            eligible = np.isin(a, labels) & np.isin(b, labels)
            denom = int(eligible.sum())
            cross = int(((a != b) & eligible).sum())
            present = set(labels) <= set(lab)
            results.append(
                dict(
                    donor=donor,
                    slice=slice_id,
                    radius=r,
                    pairs_all=len(e),
                    pairs_target=denom,
                    cross_pairs=cross,
                    cross_fraction=cross / denom if denom and present else None,
                    status="ok" if denom and present else "target_absent_or_no_pairs",
                )
            )
        if first is None:
            first = g
    res = pd.DataFrame(results)
    # 先在供体内对切片等权，再在供体间等权；非池化细胞检验。
    per = res.groupby(["donor", "radius"], as_index=False).cross_fraction.mean()
    rng = np.random.default_rng(seed)
    summary = []
    for r, g in per.groupby("radius", sort=True):
        vals = g.cross_fraction.dropna().to_numpy()
        lo = hi = None
        if len(vals) >= 3:
            need(
                B * len(vals) <= 10_000_000, "bootstrap工作量超本地保护上限，需分块适配"
            )
            means = np.mean(rng.choice(vals, size=(B, len(vals)), replace=True), axis=1)
            lo, hi = np.quantile(means, [0.025, 0.975])
        summary.append(
            dict(
                radius=r,
                donors_available=len(vals),
                mean_cross_fraction=float(vals.mean()) if len(vals) else None,
                ci_low=lo,
                ci_high=hi,
            )
        )
    summ = pd.DataFrame(summary)
    c.save_table("slice_sensitivity.tsv", res)
    c.save_table("donor_sensitivity.tsv", per)
    c.save_table("radius_summary.tsv", summ)
    c.save_table("spatial_coordinates.tsv", df)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for donor, g in per.groupby("donor"):
        axes[0].plot(g.radius, g.cross_fraction, color="#AAAAAA", alpha=0.5, lw=1)
    axes[0].plot(summ.radius, summ.mean_cross_fraction, color="#337EA5", marker="o")
    low = pd.to_numeric(summ.ci_low, errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(summ.ci_high, errors="coerce").to_numpy(dtype=float)
    axes[0].fill_between(summ.radius.to_numpy(), low, high, color="#337EA5", alpha=0.2)
    axes[0].set(
        xlabel="Neighborhood radius (" + cfg["coordinate_unit"] + ")",
        ylabel="A–B / all target-label pairs",
        ylim=(0, 1),
    )
    for label, g in first.groupby("label", sort=True):
        axes[1].scatter(g.x, g.y, label=label, s=8, alpha=0.6)
    span = max(float(np.ptp(first.x)), float(np.ptp(first.y)), 1e-6) * 1.15
    cx = (first.x.min() + first.x.max()) / 2
    cy = (first.y.min() + first.y.max()) / 2
    axes[1].set(
        xlim=(cx - span / 2, cx + span / 2), ylim=(cy - span / 2, cy + span / 2)
    )
    axes[1].set_aspect("equal")
    axes[1].legend(fontsize=8, loc="upper left", bbox_to_anchor=(1, 1))
    axes[1].set(
        xlabel="x (" + cfg["coordinate_unit"] + ")",
        ylabel="y (" + cfg["coordinate_unit"] + ")",
        title="First donor / slice",
    )
    c.figure(
        fig,
        "spatial_sensitivity",
        "灰线为供体内切片等权的邻接比例，蓝线为供体等权均值；至少3位可用供体时给出供体bootstrap百分位区间。不同半径可用供体可能不同，需查表；右图为首张切片，不构成全队列代表性保证。",
    )
    return {
        "radii": radii,
        "donors": df.donor.nunique(),
        "coordinate_unit": cfg["coordinate_unit"],
        "interpretation": [
            f"纳入{df.donor.nunique()}位供体、{df[['donor', 'slice']].drop_duplicates().shape[0]}张切片，重算{len(radii)}种半径；{int(res.cross_fraction.notna().sum())}/{len(res)}个切片×尺度可估计，缺失项保留。",
            "实际重算不同半径下两目标标签的无向邻接边比例，未对细胞标签做破坏空间自相关的随机置换。",
            "比例受细胞丰度、组织边界和切片覆盖影响，不是相互作用富集或通讯因果证据；缺失目标细胞不填零。",
            "此适配器检验邻域尺度稳健性，不重做分割/去卷积。其他分割版本须独立运行并在匹配供体、覆盖区域后比较，不得混同为已执行。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
