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
            "requirements",
            "datasets",
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
                    "requirements",
                    "datasets",
                }
            )
        ),
    )
    cfg = c.cfg
    requirements = cfg.get("requirements")
    cards = cfg.get("datasets")
    need(
        isinstance(requirements, list)
        and requirements
        and isinstance(cards, list)
        and cards,
        "缺少requirements/datasets",
    )
    names = [r.get("field") for r in requirements]
    need(
        all(isinstance(x, str) and x for x in names) and len(set(names)) == len(names),
        "条件字段需非空且唯一",
    )
    for r in requirements:
        need(
            r.get("op") in ("eq", "in", "ge")
            and type(r.get("hard")) is bool
            and "value" in r,
            "条件需op/value/hard",
        )
        if r["op"] == "in":
            need(isinstance(r["value"], list) and r["value"], "in条件需非空列表")
    seen = set()
    checks = []
    totals = []
    for card in cards:
        key = card.get("id")
        need(isinstance(key, str) and key and key not in seen, "数据集ID缺失或重复")
        seen.add(key)
        need(
            card.get("role")
            in ("discovery", "training", "validation", "localization", "extension"),
            "数据角色无效",
        )
        facts = card.get("facts", {})
        statuses = []
        for r in requirements:
            fact = facts.get(r["field"])
            status = "unknown"
            value = None
            source = ""
            if fact is not None:
                need(
                    isinstance(fact, dict)
                    and isinstance(fact.get("source"), str)
                    and fact["source"].strip(),
                    "已知事实必须有出处",
                )
                value = fact.get("value")
                source = fact["source"]
                if value is not None:
                    if r["op"] == "ge":
                        need(
                            type(value) in (int, float)
                            and type(r["value"]) in (int, float),
                            "ge仅接受数值",
                        )
                        numeric([value, r["value"]])
                        passed = value >= r["value"]
                    elif r["op"] == "in":
                        passed = value in r["value"]
                    else:
                        passed = value == r["value"]
                    status = "pass" if passed else "fail"
            statuses.append((status, r["hard"]))
            checks.append(
                dict(
                    dataset_id=key,
                    field=r["field"],
                    hard=r["hard"],
                    status=status,
                    value=value,
                    source=source,
                )
            )
        eligibility = (
            "exclude"
            if any(s == "fail" and h for s, h in statuses)
            else "pending"
            if any(s == "unknown" and h for s, h in statuses)
            else "eligible_for_review"
        )
        overlap = card.get("overlap_status", "unknown")
        need(
            overlap in ("independent_verified", "overlap", "unknown"),
            "overlap_status无效",
        )
        if overlap != "unknown":
            need(card.get("overlap_source"), "独立性或重叠判断需出处")
        if (
            card["role"] == "validation"
            and overlap != "independent_verified"
            and eligibility != "exclude"
        ):
            eligibility = "pending_independence"
        totals.append(
            dict(
                dataset_id=key,
                role=card["role"],
                eligibility=eligibility,
                overlap_status=overlap,
            )
        )
    c.save_table("eligibility.tsv", totals)
    c.save_table("criteria.tsv", checks)
    matrix = (
        pd.DataFrame(checks)
        .pivot(index="dataset_id", columns="field", values="status")
        .reindex(columns=names)
    )
    matrix = matrix.iloc[:50, :20]
    values = matrix.replace({"fail": 0, "unknown": 1, "pass": 2}).to_numpy(dtype=float)
    fig, ax = plt.subplots(
        figsize=(max(6, len(matrix.columns) * 1.3), max(3, len(matrix) * 0.5 + 1.7)),
        layout="constrained",
    )
    from matplotlib.colors import ListedColormap

    ax.imshow(
        values,
        cmap=ListedColormap(["#CA6B60", "#DDDDDD", "#62A58B"]),
        vmin=-0.5,
        vmax=2.5,
        aspect="auto",
    )
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(matrix)), matrix.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(
                j, i, ["fail", "?", "pass"][int(values[i, j])], ha="center", va="center"
            )
    c.figure(
        fig,
        "dataset_fit",
        "逐条件核验，灰色表示未知而非不满足；硬条件失败不可被其他条件抵消。图中仅展示元数据适配性，不证明科学质量或独立验证。",
    )
    return {
        "datasets": totals,
        "interpretation": [
            f"已审查{len(totals)}个候选、{len(requirements)}项条件；排除{sum(x['eligibility'] == 'exclude' for x in totals)}个。主图最多展示按ID排序前50个候选和前20项条件，完整表不截断。",
            "已输出全部入选审查、排除与待核验候选；不生成统一总分，也不因数量不足降低纳入标准。",
            "验证角色只有在队列/供体独立性有出处时才可进入人工确认；数据库编号不同不等于独立。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
