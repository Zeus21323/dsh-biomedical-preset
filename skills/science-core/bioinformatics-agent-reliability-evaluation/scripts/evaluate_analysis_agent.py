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
            "cases",
            "observations",
            "artifact_root",
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
                    "cases",
                    "observations",
                    "artifact_root",
                }
            )
        ),
    )
    cfg = c.cfg
    cases = cfg.get("cases")
    need(isinstance(cases, list) and cases, "需冻结的cases")
    root = c.path(cfg["observations"])
    observations = load_json(root)
    need(isinstance(observations, list), "observations应为JSON数组")
    lookup = {}
    for obs in observations:
        key = obs.get("case_id")
        need(
            isinstance(key, str) and key and key not in lookup, "观测case_id缺失或重复"
        )
        need(
            obs.get("outcome") in ("completed", "stopped", "failed"), "观测outcome无效"
        )
        lookup[key] = obs
    artifact_root = (c.config.parent / cfg["artifact_root"]).resolve()
    need(artifact_root.is_dir(), "artifact_root不是目录")
    rows = []
    seen = set()
    for case in cases:
        key = case.get("case_id")
        need(isinstance(key, str) and key and key not in seen, "用例ID缺失或重复")
        seen.add(key)
        need(
            case.get("expected_outcome") in ("completed", "stopped", "failed"),
            "期望状态无效",
        )
        checks = case.get("checks", [])
        need(
            isinstance(checks, list) and checks, "每例需具体判据；不能只按状态宣称正确"
        )
        obs = lookup.get(key)
        rows.append(
            dict(
                case_id=key,
                check="outcome",
                status="missing"
                if obs is None
                else "pass"
                if obs["outcome"] == case["expected_outcome"]
                else "fail",
                detail="expected=" + case["expected_outcome"],
            )
        )
        for index, check in enumerate(checks):
            kind = check.get("kind")
            need(kind in ("trace_equals", "artifact_sha256", "json_number"), "未知判据")
            passed = False
            status = "missing"
            detail = ""
            if obs is not None:
                if kind == "trace_equals":
                    field = check.get("field")
                    need(
                        isinstance(field, str) and field and "value" in check,
                        "trace_equals需field/value",
                    )
                    if field in obs:
                        passed = obs[field] == check["value"]
                        status = "pass" if passed else "fail"
                    detail = (
                        "recorded field "
                        + field
                        + "; trace assertions are not independent proof"
                    )
                else:
                    relative = check.get("path")
                    need(isinstance(relative, str) and relative, "需artifact path")
                    path = (artifact_root / relative).resolve()
                    need(
                        path != artifact_root and artifact_root in path.parents,
                        "产物路径越界或符号链接逃逸",
                    )
                    if path.is_file():
                        need(
                            path.stat().st_size <= 1_000_000_000, "产物超过1GB保护上限"
                        )
                        c.hashes[str(path)] = sha(path)
                        if kind == "artifact_sha256":
                            expected = check.get("sha256")
                            need(
                                isinstance(expected, str)
                                and len(expected) == 64
                                and all(x in "0123456789abcdef" for x in expected),
                                "sha256格式无效",
                            )
                            passed = sha(path) == expected
                        else:
                            data = load_json(path)
                            pointer = check.get("keys")
                            need(
                                isinstance(pointer, list) and pointer,
                                "json_number需keys路径",
                            )
                            try:
                                for part in pointer:
                                    data = data[part]
                            except (KeyError, IndexError, TypeError):
                                data = None
                            expected = check.get("expected")
                            tolerance = check.get("atol")
                            need(
                                type(expected) in (int, float)
                                and type(tolerance) in (int, float),
                                "expected/atol需数值",
                            )
                            numeric([expected, tolerance])
                            need(tolerance >= 0, "atol不能负")
                            passed = (
                                type(data) in (int, float)
                                and math.isfinite(data)
                                and abs(data - expected) <= tolerance
                            )
                        status = "pass" if passed else "fail"
                    detail = relative
            rows.append(
                dict(
                    case_id=key,
                    check=f"{index + 1}:{kind}",
                    status=status,
                    detail=detail,
                )
            )
    need(set(lookup) <= seen, "观测包含未注册用例；需明确纳入或排除，不能静默忽略")
    result = pd.DataFrame(rows)
    c.save_table("check_results.tsv", result)
    summary = []
    for case, g in result.groupby("case_id", sort=True):
        status = (
            "fail"
            if (g.status == "fail").any()
            else "incomplete"
            if (g.status == "missing").any()
            else "pass"
        )
        summary.append(dict(case_id=case, status=status))
    c.save_table("case_results.tsv", summary)
    counts = (
        pd.Series([s["status"] for s in summary])
        .value_counts()
        .reindex(["pass", "fail", "incomplete"], fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
    ax.bar(counts.index, counts.values, color=["#62A58B", "#CA6B60", "#AAAAAA"])
    ax.set(
        xlabel="Frozen benchmark outcome",
        ylabel="Case count",
        ylim=(0, max(1, counts.max()) * 1.2),
    )
    for i, v in enumerate(counts):
        ax.text(i, v, str(v), ha="center", va="bottom")
    c.figure(
        fig,
        "agent_reliability",
        "每例必须同时满足冻结期望状态和所有明确判据。缺少观测或产物为未完成，不计通过；正确停止可通过错误输入类用例。记录字段相等不等于独立验证操作行为。",
    )
    return {
        "cases": len(cases),
        "passed": int(counts["pass"]),
        "failed": int(counts["fail"]),
        "incomplete": int(counts["incomplete"]),
        "interpretation": [
            f"冻结案例{len(cases)}个：通过{int(counts['pass'])}、失败{int(counts['fail'])}、未完成{int(counts['incomplete'])}；所有案例均保留在分母内。",
            "已审计提供的真实运行记录及产物；未执行或调用任何在线代理，也没有证明跨任务泛化可靠性。",
            "预期值、容差和案例划分须先冻结，评测集不可用于提示调优；轨迹中的安全、泄漏等声明仍需独立日志或人工复核。",
            "不将正常失败、正确停止、科学错误与基础设施故障合并成一个成功率；逐例说明失败类型及其修复范围。",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
