#!/usr/bin/env python3
"""校验研究清单并渲染 Markdown；仅使用 Python 标准库，不执行分析或网络请求。"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit


ROLES = {"cell_localization": "细胞定位", "discovery": "发现", "training": "训练",
         "external_validation": "外部验证", "mechanism_support": "机制扩展"}
DECISIONS = {"selected": "入选", "pending": "待核验", "excluded": "排除"}
STATES = {"planned": "计划", "completed": "已完成", "failed": "失败", "not_run": "未运行"}
LEVELS = {"hypothesis": "假设", "association": "统计关联", "localization": "表达定位",
          "prediction": "计算预测", "replication": "复现", "functional": "功能实验"}
INDEPENDENCE = {"confirmed": "已核实独立", "unknown": "独立性未知",
                "overlap": "存在重叠", "not_applicable": "不适用"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def strings(value: object, label: str, nonempty: bool = False) -> list[str]:
    require(isinstance(value, list), f"{label} 必须是列表")
    require(all(isinstance(x, str) and x.strip() for x in value), f"{label} 必须包含非空字符串")
    require(not nonempty or bool(value), f"{label} 不能为空")
    return value


def fields(record: dict, names: tuple[str, ...], label: str) -> None:
    for name in names:
        require(isinstance(record.get(name), str) and bool(record[name].strip()),
                f"{label}.{name} 必须是非空字符串")


def records(value: object, label: str) -> dict[str, dict]:
    require(isinstance(value, list), f"{label} 必须是列表")
    result = {}
    for item in value:
        require(isinstance(item, dict), f"{label} 条目必须是对象")
        fields(item, ("id",), label)
        require(item["id"] not in result, f"{label} ID 重复：{item['id']}")
        result[item["id"]] = item
    return result


def is_web(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def validate(data: dict, base: Path) -> list[str]:
    require(isinstance(data, dict), "清单必须是 JSON 对象")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "schema_version 必须为 1")
    require(data.get("mode") in {"plan", "results"}, "mode 必须为 plan 或 results")
    fields(data, ("title", "question", "as_of", "route", "conclusion"), "清单")
    require(date.fromisoformat(data["as_of"]).isoformat() == data["as_of"], "as_of 必须为 YYYY-MM-DD")
    for name in ("criteria", "search_notes", "limitations", "next_steps"):
        strings(data.get(name), name, nonempty=True)
    count = data.get("requested_count")
    require(count is None or (type(count) is int and count > 0), "requested_count 必须为正整数或 null")
    datasets = records(data.get("datasets"), "datasets")
    evidence = records(data.get("evidence"), "evidence")
    sections = records(data.get("sections"), "sections")
    warnings = []
    for key, ds in datasets.items():
        fields(ds, ("accession", "source_url", "species", "system", "tissue", "assay", "platform",
                    "groups", "data_layer", "version", "access", "reason", "limitations"), key)
        require(is_web(ds["source_url"]), f"{key}.source_url 必须是 HTTP(S) 来源地址")
        require(ds.get("decision") in DECISIONS, f"{key}.decision 无效")
        roles = strings(ds.get("roles"), f"{key}.roles")
        require(set(roles) <= ROLES.keys(), f"{key}.roles 无效")
        require(ds["decision"] != "selected" or bool(roles), f"{key} 入选后必须分配角色")
        for name in ("n_donors", "n_samples", "n_cells"):
            n = ds.get(name)
            require(n is None or (type(n) is int and n >= 0), f"{key}.{name} 必须为非负整数或 null")
        require(ds.get("independence") in INDEPENDENCE, f"{key}.independence 无效")
        overlaps = strings(ds.get("overlap_with"), f"{key}.overlap_with")
        require(set(overlaps) <= datasets.keys() and key not in overlaps, f"{key} 重叠引用无效")
        require(not overlaps or ds["independence"] == "overlap", f"{key} 存在重叠却未标为 overlap")
        if ds["decision"] == "selected" and "external_validation" in roles:
            require(not {"training", "discovery"}.intersection(roles), f"{key} 不能同时用于发现/训练及外部验证")
            require(ds["independence"] in {"confirmed", "unknown"}, f"{key} 不满足外部独立验证条件")
            require(not any(key in other.get("overlap_with", []) for other in datasets.values()),
                    f"{key} 被其他数据集标为重叠，不能作为独立外部验证")
            if ds["independence"] == "unknown":
                warnings.append(f"{key} 的外部验证独立性尚未核实，不可宣称已获独立验证。")
        if ds["decision"] == "selected" and "cell_localization" in roles and ds.get("n_donors") is None:
            warnings.append(f"{key} 缺少独立供体数，细胞定位与疾病组间推断的适用性需分别评估。")
    selected = sum(ds["decision"] == "selected" for ds in datasets.values())
    if count is not None and selected != count:
        warnings.append(f"目标选择 {count} 个数据集，实际入选 {selected} 个；按条件报告数量差异，不自动补足。")
    for key, ev in evidence.items():
        fields(ev, ("label", "locator"), key)
        require(ev.get("kind") in {"metadata", "literature", "result"}, f"{key}.kind 无效")
        ids = strings(ev.get("dataset_ids"), f"{key}.dataset_ids", nonempty=ev["kind"] == "result")
        require(set(ids) <= datasets.keys(), f"{key} 引用了未知数据集")
        loc = ev["locator"]
        if not is_web(loc):
            require(not urlsplit(loc).scheme, f"{key} 不支持此来源协议")
            require(not Path(loc).is_absolute(), f"{key} 本地出处须相对于清单目录")
            require((base / loc).is_file(), f"{key} 本地出处不存在：{loc}")
    require(bool(sections), "sections 不能为空")
    completed = 0
    for key, section in sections.items():
        fields(section, ("title", "text"), key)
        require(section.get("status") in STATES, f"{key}.status 无效")
        require(section.get("level") in LEVELS, f"{key}.level 无效")
        ids = strings(section.get("dataset_ids"), f"{key}.dataset_ids")
        refs = strings(section.get("evidence_ids"), f"{key}.evidence_ids")
        require(set(ids) <= datasets.keys(), f"{key} 引用了未知数据集")
        require(set(refs) <= evidence.keys(), f"{key} 引用了未知证据")
        if section["status"] == "completed":
            completed += 1
            require(data["mode"] == "results", "plan 模式不能包含已完成分析，请使用 results 或改为计划")
            result_ids = set()
            for ref in refs:
                if evidence[ref]["kind"] == "result":
                    result_ids.update(evidence[ref]["dataset_ids"])
            require(bool(ids) and set(ids) <= result_ids, f"{key} 已完成结果缺少对应数据集的 result 出处")
        if section["status"] in {"failed", "not_run"}:
            warnings.append(f"{section['title']}：{STATES[section['status']]}，结论需保留此缺口。")
    require(data["mode"] != "results" or completed > 0, "results 模式至少需要一项有出处的已完成结果")
    return warnings


def cell(value: object) -> str:
    """将表格中的元数据作为文本显示，保留分隔符与换行。"""
    value = "未知" if value is None else str(value)
    return (html.escape(value).replace("\\", "&#92;").replace("|", "&#124;")
            .replace("[", "&#91;").replace("]", "&#93;").replace("`", "&#96;")
            .replace("*", "&#42;").replace("_", "&#95;").replace("\r", "").replace("\n", "<br>"))


def target(locator: str, base: Path, output: Path) -> str:
    if is_web(locator):
        return quote(locator, safe="/:?=&%+#@,;~!$")
    import os
    return quote(os.path.relpath((base / locator).resolve(), output.parent.resolve()), safe="/.-_~")


def render(data: dict, warnings: list[str], base: Path, output: Path) -> str:
    mode = "研究设计与数据遴选" if data["mode"] == "plan" else "实际结果解读"
    lines = [f"# {cell(data['title'])}", "", f"报告阶段：{mode}；资料截止日期：{data['as_of']}。", "",
             "## 研究问题", "", data["question"], "", "## 结论或方案建议", "", data["conclusion"], "",
             "## 证据路线", "", data["route"], ""]

    def bullets(title: str, items: list[str]) -> None:
        lines.extend([f"## {title}", ""])
        for item in items:
            lines.extend(["- " + item.replace("\n", "\n  "), ""])

    bullets("纳排条件", data["criteria"])
    bullets("检索记录", data["search_notes"])
    if warnings:
        bullets("需核验事项与完成状态", warnings)
    lines.extend(["## 数据集选择与角色", "",
                  "| 数据集 | 决定 | 角色 | 供体/样本/细胞数 | 独立性 |",
                  "| --- | --- | --- | --- | --- |"])
    for ds in data["datasets"]:
        nums = "/".join(cell(ds.get(n)) for n in ("n_donors", "n_samples", "n_cells"))
        lines.append(f"| {cell(ds['id'])} · {cell(ds['accession'])} | {DECISIONS[ds['decision']]} | "
                     f"{'、'.join(ROLES[r] for r in ds['roles']) or '无'} | {nums} | {INDEPENDENCE[ds['independence']]} |")
    for ds in data["datasets"]:
        lines.extend(["", f"### {cell(ds['id'])} · {cell(ds['accession'])}", "",
                      f"[数据库来源]({target(ds['source_url'], base, output)})", ""])
        for label, key in (("物种", "species"), ("实验系统", "system"), ("组织", "tissue"),
                           ("assay", "assay"), ("平台", "platform"), ("分组与数量口径", "groups"),
                           ("可用数据层", "data_layer"), ("版本", "version"), ("访问及许可", "access"),
                           ("选择理由", "reason"), ("限制", "limitations")):
            lines.extend([f"- {label}：{cell(ds[key])}", ""])
        lines.extend([f"- 重叠数据集：{cell('、'.join(ds['overlap_with']) or '清单未记录重叠；不等于已证实独立')}", ""])
    lines.extend(["## 分阶段论证与解读", ""])
    for section in data["sections"]:
        lines.extend([f"### {cell(section['title'])}", "",
                      f"状态：{STATES[section['status']]}；证据性质：{LEVELS[section['level']]}。", "",
                      section["text"], "",
                      f"数据集：{cell('、'.join(section['dataset_ids']) or '尚未落实')}；"
                      f"证据编号：{cell('、'.join(section['evidence_ids']) or '暂无')}。", ""])
    bullets("局限性与替代解释", data["limitations"])
    bullets("下一步与验证缺口", data["next_steps"])
    lines.extend(["## 证据来源", ""])
    for ev in data["evidence"]:
        lines.extend([f"- {cell(ev['id'])} · {cell(ev['kind'])} · "
                      f"[{cell(ev['label'])}]({target(ev['locator'], base, output)})；"
                      f"数据集：{cell('、'.join(ev['dataset_ids']) or '背景文献')}。", ""])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="研究清单 JSON")
    parser.add_argument("--output", required=True, type=Path, help="Markdown 输出路径")
    parser.add_argument("--overwrite", action="store_true", help="允许替换已有报告")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        warnings = validate(data, args.input.parent)
        protected = {args.input.resolve()}
        protected.update((args.input.parent / ev["locator"]).resolve()
                         for ev in data["evidence"] if not is_web(ev["locator"]))
        require(args.output.resolve() not in protected, "输出不能覆盖输入清单或证据文件")
        report = render(data, warnings, args.input.parent, args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w" if args.overwrite else "x", encoding="utf-8") as handle:
            handle.write(report)
        print(f"已生成：{args.output}（需核验事项 {len(warnings)} 项）")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"报告生成失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
