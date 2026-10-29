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


def ora(c, mapping, foreground, universe):
    df = c.table(mapping, ["term", "gene"])
    ids(df, ["term", "gene"])
    rows = []
    for term, g in df.groupby("term", sort=True):
        members = set(g.gene) & universe
        if not members:
            continue
        hit = len(members & foreground)
        rows.append(
            dict(
                id=term,
                estimate=hit / len(foreground),
                pvalue=float(
                    stats.hypergeom.sf(
                        hit - 1, len(universe), len(members), len(foreground)
                    )
                ),
                hits=hit,
                term_size=len(members),
                query_size=len(foreground),
                background_size=len(universe),
            )
        )
    need(rows, "映射与固定背景没有交集")
    out = pd.DataFrame(rows)
    out["padj"] = bh(out.pvalue)
    return out


def analyze(c):
    need(
        not set(c.cfg)
        - {
            "question",
            "parameter_reason",
            "evidence_notes",
            "font",
            "mode",
            "versions",
            "alpha",
            "old_results",
            "new_results",
            "foreground",
            "background",
            "old_mapping",
            "new_mapping",
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
                    "versions",
                    "alpha",
                    "old_results",
                    "new_results",
                    "foreground",
                    "background",
                    "old_mapping",
                    "new_mapping",
                }
            )
        ),
    )
    cfg = c.cfg
    mode = cfg.get("mode")
    need(mode in ("compare", "ora"), "mode需compare或ora")
    alpha = float(cfg.get("alpha", 0.05))
    need(0 < alpha < 1, "alpha超范围")
    manifests = cfg.get("versions")
    need(
        isinstance(manifests, dict)
        and all(isinstance(manifests.get(k), dict) for k in ("old", "new")),
        "需versions.old/new",
    )
    for m in manifests.values():
        need(
            isinstance(m.get("reference"), str) and m["reference"].strip(), "需参考版本"
        )
    attribution = False
    if mode == "ora":
        fg = c.table(cfg["foreground"], ["gene"])
        bg = c.table(cfg["background"], ["gene"])
        ids(fg, ["gene"])
        ids(bg, ["gene"])
        foreground = set(fg.gene)
        universe = set(bg.gene)
        need(
            foreground <= universe and 0 < len(foreground) < len(universe),
            "前景须为背景真子集，不能自动截断",
        )
        old = ora(c, cfg["old_mapping"], foreground, universe)
        new = ora(c, cfg["new_mapping"], foreground, universe)
        attribution = True
    else:
        old = c.table(cfg["old_results"], ["id", "estimate", "padj"])
        new = c.table(cfg["new_results"], ["id", "estimate", "padj"])
        keys = (
            "input_sha256",
            "code_sha256",
            "parameters_sha256",
            "environment_sha256",
        )
        # 声明一致只支持“与控制条件一致”，不等于独立核实全部重运行。
        attribution = all(
            isinstance(manifests["old"].get(k), str)
            and len(manifests["old"][k]) == 64
            and all(ch in "0123456789abcdef" for ch in manifests["old"][k])
            and manifests["old"][k] == manifests["new"].get(k)
            for k in keys
        )
    for df in (old, new):
        ids(df, ["id"])
        df["estimate"] = numeric(df.estimate)
        df["padj"] = numeric(df.padj)
        need(df.padj.between(0, 1).all(), "padj超范围")
        df["rank"] = df.padj.rank(method="average")
    c.save_table("old_results.tsv", old)
    c.save_table("new_results.tsv", new)
    merged = old.merge(
        new, on="id", how="outer", suffixes=("_old", "_new"), indicator=True
    )
    common = merged["_merge"] == "both"
    merged["status"] = merged["_merge"].astype(str)
    merged.loc[common, "status"] = "stable"
    sigchange = (merged.padj_old < alpha) != (merged.padj_new < alpha)
    merged.loc[common & sigchange, "status"] = "threshold_crossing"
    merged["estimate_delta"] = merged.estimate_new - merged.estimate_old
    merged["rank_delta"] = merged.rank_new - merged.rank_old
    merged["sign_flip"] = pd.Series([None] * len(merged), dtype=object)
    merged.loc[common, "sign_flip"] = (
        merged.loc[common, "estimate_old"] * merged.loc[common, "estimate_new"] < 0
    ).to_numpy()
    c.save_table("drift.tsv", merged.drop(columns="_merge"))
    both = merged.loc[common]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), layout="constrained")
    for ax, key, label in zip(
        axes,
        ("estimate", "rank"),
        ("Estimate (same scale required)", "Adjusted-P rank (ties averaged)"),
    ):
        ax.scatter(
            both[key + "_old"], both[key + "_new"], s=24, alpha=0.7, color="#337EA5"
        )
        if len(both):
            limits = [
                both[[key + "_old", key + "_new"]].min().min(),
                both[[key + "_old", key + "_new"]].max().max(),
            ]
            ax.plot(limits, limits, color="#888888", ls="--", lw=1)
        ax.set(xlabel="Old: " + label, ylabel="New: " + label)
    c.figure(
        fig,
        "result_drift",
        "共同实体的数值及排名比较；单侧缺失另见完整表，不按零处理。阈值跨越不是生物学反转；ORA比较中的estimate为前景命中比例而非有符号效应。",
    )
    return {
        "mode": mode,
        "shared": len(both),
        "old_only": int((merged._merge == "left_only").sum()),
        "new_only": int((merged._merge == "right_only").sum()),
        "threshold_crossings": int((common & sigchange).sum()),
        "controlled_reference_comparison": attribution,
        "interpretation": [
            (
                "已在本进程固定前景、背景和实现，对两版映射实际重算ORA。"
                if mode == "ora"
                else "已比较实际结果；元数据哈希一致只表示所提交运行记录声称控制了其他条件。"
            ),
            "不能将混合变更归因于数据库版本；未审计实体映射、运行记录真实性或背景变化时只作描述性漂移报告。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
