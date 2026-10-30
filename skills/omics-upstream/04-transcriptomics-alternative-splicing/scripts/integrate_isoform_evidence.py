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
            "bootstraps",
            "seed",
            "groups",
            "entity_kind",
            "table",
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
                    "bootstraps",
                    "seed",
                    "groups",
                    "entity_kind",
                    "table",
                }
            )
        ),
    )
    cfg = c.cfg
    B = integer(cfg, "bootstraps", 100, 10000)
    seed = integer(cfg, "seed", 0, 2**32 - 1)
    groups = cfg.get("groups")
    need(
        isinstance(groups, list) and len(groups) == 2 and len(set(groups)) == 2,
        "groups为对照、病例",
    )
    entity = cfg.get("entity_kind")
    need(
        entity in ("junction_event", "full_length_isoform"),
        "entity_kind需junction_event/full_length_isoform",
    )
    df = c.table(
        cfg["table"],
        [
            "study",
            "donor",
            "cell_type",
            "group",
            "gene",
            "entity",
            "support",
            "total",
            "annotation",
            "source",
        ],
    )
    ids(df, ["study", "donor", "cell_type", "entity"])
    need(set(df.group) <= set(groups) and set(df.group) == set(groups), "分组不匹配")
    need(
        (df.groupby(["study", "donor"]).group.nunique() == 1).all(),
        "一个供体跨组需配对模型，不适用独立组适配器",
    )
    need(
        df.annotation.nunique() == 1 and df.annotation.str.strip().ne("").all(),
        "注释版本不同需先经明确实体映射，不自动删版本后缀",
    )
    need(df.source.str.strip().ne("").all(), "证据缺少出处")
    need((df.groupby("entity").gene.nunique() == 1).all(), "同一实体映射多个基因")
    df["support"] = numeric(df.support)
    df["total"] = numeric(df.total)
    need(
        ((df.support >= 0) & (df.total >= df.support)).all(),
        "支持量需满足0<=support<=total",
    )
    if entity == "junction_event":
        need(
            (df[["support", "total"]].to_numpy() % 1 == 0).all(),
            "junction_event需整数计数，不能传标准化表达",
        )
    else:
        need(
            (
                df.groupby(["study", "donor", "cell_type", "gene"]).total.nunique() == 1
            ).all(),
            "同基因异构体分母不一致",
        )
    need(B * len(df) <= 10_000_000, "bootstrap工作量超本地保护上限，需分块适配")
    # total=0不可测，绝不视作PSI=0。
    df["fraction"] = np.divide(
        df.support,
        df.total,
        out=np.full(len(df), np.nan),
        where=df.total.to_numpy() > 0,
    )
    rng = np.random.default_rng(seed)
    rows = []
    for (study, cell, gene, event), g in df.groupby(
        ["study", "cell_type", "gene", "entity"], sort=True
    ):
        samples = [
            g[(g.group == label) & g.fraction.notna()].fraction.to_numpy()
            for label in groups
        ]
        n0, n1 = map(len, samples)
        effect = lo = hi = None
        status = "insufficient_independent_donors"
        if min(n0, n1) >= 3:
            effect = samples[1].mean() - samples[0].mean()
            boots = np.mean(rng.choice(samples[1], (B, n1)), axis=1) - np.mean(
                rng.choice(samples[0], (B, n0)), axis=1
            )
            lo, hi = np.quantile(boots, [0.025, 0.975])
            status = "descriptive_donor_bootstrap"
        rows.append(
            dict(
                study=study,
                cell_type=cell,
                gene=gene,
                entity=event,
                n_control=n0,
                n_case=n1,
                unmeasurable=int(g.fraction.isna().sum()),
                effect=effect,
                ci_low=lo,
                ci_high=hi,
                status=status,
            )
        )
    res = pd.DataFrame(rows)
    c.save_table("donor_support.tsv", df)
    c.save_table("isoform_evidence.tsv", res)
    fig, ax = plt.subplots(
        figsize=(9, max(3, min(len(res), 30) * 0.45 + 1.5)), layout="constrained"
    )
    plot = res.head(30)
    for i, row in enumerate(plot.itertuples()):
        if pd.notna(row.effect):
            ax.plot([row.ci_low, row.ci_high], [i, i], color="#337EA5")
            ax.scatter([row.effect], [i], color="#337EA5")
        else:
            ax.text(0, i, "not estimable", ha="center", va="center", fontsize=8)
    ax.set_yticks(
        range(len(plot)),
        [f"{r.study} / {r.cell_type} / {r.entity}" for r in plot.itertuples()],
    )
    ax.axvline(0, color="#888888", ls="--")
    ax.set(xlabel="Case − control fraction (donor bootstrap 95% CI)", xlim=(-1, 1))
    c.figure(
        fig,
        "isoform_evidence",
        "独立供体比例差及未经多重比较校正的bootstrap百分位区间，不能按区间逐项宣称显著。支持量为零且总量正与总量为零区分；展示按ID排序前30项，其余保留完整表。",
    )
    return {
        "entity_kind": entity,
        "annotation": str(df.annotation.iloc[0]),
        "comparisons": len(res),
        "interpretation": [
            f"共整理{len(df)}条供体级记录、{len(res)}个比较；{int(res.effect.notna().sum())}个可估计组差，{int(df.fraction.isna().sum())}条记录不可测。",
            "已计算供体级事件/异构体比例、组间描述性差异和区间；不足3位可测供体/组的比较保留但不估计。",
            "短读长junction支持不能证明完整异构体。full_length_isoform要求同基因的可比异构体定量分母，来源需外部核实。",
            "本脚本整合已定量证据，不执行原始reads比对、异构体组装或蛋白功能验证，也不自动消除平台、覆盖及细胞组成混杂。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
