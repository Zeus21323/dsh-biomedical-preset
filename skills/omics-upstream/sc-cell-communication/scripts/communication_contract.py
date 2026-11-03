"""Typed, provenance-preserving communication result bundles (standard library only)."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path

FIELDS = {
    "lr_edges": ("sample", "source", "target", "ligand", "receptor", "score", "tested", "supported"),
    "metabolite_edges": ("sample", "source", "target", "metabolite", "sensor", "score", "tested", "supported"),
    "matrix": ("row", "column", "value"),
    "activities": ("ligand", "value"),
    "molecular_links": ("source", "target", "source_type", "target_type", "value"),
    "patterns": ("factor", "dimension", "entity", "value"),
    "latent_points": ("entity", "domain", "x", "y", "z"),
    "embedding_points": ("sample", "cell", "x", "y"),
    "spatial_points": ("sample", "cell", "x", "y", "value"),
    "spatial_vectors": ("sample", "cell", "x", "y", "dx", "dy"),
    "spatial_edges": ("sample", "source_cell", "target_cell", "value"),
    "effects": ("sample", "donor", "condition", "feature", "value"),
    "effect_summary": ("feature", "value", "p_value", "q_value", "n_reference", "n_comparison"),
    "enrichment": ("term", "group", "value", "q_value", "overlap", "set_size", "background_size"),
    "time_series": ("sample", "donor", "feature", "time", "value"),
    "network": ("source", "target", "value"),
}
NUMERIC = {"score", "value", "x", "y", "z", "dx", "dy", "dz", "time", "p_value", "q_value", "ci_low", "ci_high", "n_reference", "n_comparison", "overlap", "set_size", "background_size"}
NUMERIC.update({"ligand_mean", "receptor_mean"})
MISSING = {"", "NA", "NaN", "nan", "null"}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_table(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    if not fields:
        raise ValueError("空表必须声明字段")
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields, delimiter="\t", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def new_output(path):
    path = Path(path).expanduser().resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise ValueError("实际分析输出必须位于 Git 仓库外")
    path.mkdir(parents=True, exist_ok=False)
    return path


def local_path(root, value):
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"结果文件缺失或超出结果包: {value}")
    return path


def truth(value):
    if value in (True, "True", "TRUE", "true", "1", 1):
        return True
    if value in (False, "False", "FALSE", "false", "0", 0):
        return False
    raise ValueError(f"无效布尔值: {value}")


def load_bundle(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text())
    if cfg.get("schema_version") != 2:
        raise ValueError("需要 schema_version=2 的语义结果包")
    for key in ("dataset", "method", "method_version", "implementation", "provenance"):
        if not cfg.get(key):
            raise ValueError(f"结果包缺少 {key}")
    datasets = []
    ids = set()
    for spec in cfg.get("tables", []):
        ident, kind = spec.get("id", ""), spec.get("type")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", ident) or ident in ids:
            raise ValueError("表 ID 必须为唯一安全标识")
        ids.add(ident)
        for flag in ('additive','directed','y_down','nonnegative'):
            if flag in spec and not isinstance(spec[flag],bool):
                raise ValueError(f'表 {ident} 的 {flag} 必须为JSON布尔值，不能用字符串改变绘图语义')
        if kind not in FIELDS or not spec.get("value_definition"):
            raise ValueError(f"表 {ident} 缺少支持的类型或数值定义")
        if spec.get('display_priority') not in (None,'minimum_endpoint_mean'):
            raise ValueError('未知的展示排序规则')
        for limit in ('display_top_rows','display_top_columns','display_top_lr','display_top_cell_pairs'):
            if limit in spec and (type(spec[limit]) is not int or spec[limit]<1):
                raise ValueError('展示行列数量须为正整数')
        for order in ('row_order','column_order'):
            if order in spec and (not isinstance(spec[order],list) or not all(isinstance(v,str) and v for v in spec[order]) or len(set(spec[order]))!=len(spec[order])):
                raise ValueError('矩阵显式行列顺序须为唯一非空字符串列表')
        if kind == 'latent_points' and (not spec.get('space_definition') or spec.get('coordinate_unit')!='latent'):
            raise ValueError('潜在空间须声明原生空间定义与latent单位，不冒充组织坐标')
        if kind == 'embedding_points' and (not spec.get('embedding_method') or not spec.get('embedding_provenance')):
            raise ValueError('细胞降维图需要实际降维方法和坐标来源')
        source = local_path(path.parent, spec["path"])
        if not spec.get("sha256") or digest(source) != spec["sha256"]:
            raise ValueError(f"表 {ident} 哈希不符")
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if not set(FIELDS[kind]) <= set(reader.fieldnames or []):
                raise ValueError(f"表 {ident} 缺字段 {FIELDS[kind]}")
            rows = list(reader)
        for row in rows:
            if None in row:
                raise ValueError(f"表 {ident} 列数不符")
            for key in FIELDS[kind]:
                if key not in NUMERIC and not str(row.get(key, "")).strip():
                    raise ValueError(f"表 {ident} 的 {key} 为空")
            for key in row.keys() & NUMERIC:
                if row[key] in MISSING:
                    row[key] = None
                else:
                    row[key] = float(row[key])
                    if not math.isfinite(row[key]):
                        raise ValueError("数值必须有限，缺失以 NA 表示")
                    if key in ("p_value", "q_value") and not 0 <= row[key] <= 1:
                        raise ValueError("P/q 不在 [0,1]")
            if kind in ("lr_edges", "metabolite_edges"):
                row["tested"], row["supported"] = truth(row["tested"]), truth(row["supported"])
                if row["supported"] and (not row["tested"] or row["score"] is None):
                    raise ValueError("支持的边必须已检验且有分数")
            for key in set(FIELDS[kind]) & {"x", "y", "z", "dx", "dy", "time"}:
                if row[key] is None:
                    raise ValueError(f"{key} 是位置/时间必需值，不能缺失")
        if kind.startswith("spatial") and spec.get("coordinate_unit") not in ("um","pixel","native"):
            raise ValueError("空间绘图需明确 um/pixel/native 坐标单位；未知物理比例不能冒充 μm")
        if kind.startswith("spatial") and spec.get("coordinate_unit")=="native" and not spec.get("physical_scale_unavailable"):
            raise ValueError("原生坐标单位必须显式标明物理比例不可用，不得解释为物理传播距离")
        if kind.startswith("spatial") and not (spec.get("coordinate_provenance") or cfg["provenance"].get("coordinate_provenance") or cfg["provenance"].get("parameters",{}).get("coordinate_provenance")):
            raise ValueError("空间坐标必须记录原始来源与单位转换")
        if spec.get("value_kind") == "p_value" and any(r.get("value") is not None and not 0 <= r["value"] <= 1 for r in rows):
            raise ValueError("P/q 类型数值不在 [0,1]")
        if kind == "effect_summary":
            if not spec.get("contrast") or not spec.get("statistical_unit") or not spec.get("test_definition"):
                raise ValueError("效应汇总必须说明对比方向、统计单位及检验定义")
            for r in rows:
                lo, hi = r.get("ci_low"), r.get("ci_high")
                if (lo is None) != (hi is None) or (lo is not None and lo > hi):
                    raise ValueError("置信区间端点缺失或倒置")
                if lo is not None and not spec.get("interval_definition"):
                    raise ValueError("置信区间需要计算方法与覆盖率定义")
        if kind == "enrichment":
            if not spec.get("background_definition") or not spec.get("gene_set_provenance"):
                raise ValueError("富集结果必须有背景集合定义与基因集来源")
            for r in rows:
                counts = [r[k] for k in ("overlap", "set_size", "background_size")]
                if any(x is None or x < 0 or x != int(x) for x in counts) or not counts[0] <= counts[1] <= counts[2]:
                    raise ValueError("富集集合数量必须为相容的非负整数")
        if spec.get("additive") and spec.get("value_kind") not in ("nonnegative_strength", "count", "row_normalized_probability_share"):
            raise ValueError("仅明确可加的非负强度、数量或互斥概率份额可以求和；排名、P 值和活性不允许")
        if spec.get("value_kind") in ("nonnegative_strength", "count", "row_normalized_probability_share"):
            if any(r.get("value", r.get("score")) is not None and r.get("value", r.get("score")) < 0 for r in rows):
                raise ValueError("非负度量存在负值")
        datasets.append((spec, rows, source))
    if not datasets:
        raise ValueError("结果包没有任何声明的表；空结果也须保留表头")
    return cfg, datasets


def add_table(bundle, root, identifier, kind, rows, definition, **metadata):
    filename = identifier + ".tsv"
    rows = list(rows)
    write_table(Path(root) / filename, rows, None if rows else FIELDS[kind])
    bundle.setdefault("tables", []).append(dict(id=identifier, type=kind, path=filename,
        sha256=digest(Path(root) / filename), value_definition=definition, **metadata))


def registry():
    return json.loads((Path(__file__).resolve().parents[1] / "references/方法与执行契约.json").read_text())


def lookup_method(name):
    matches = [m for m in registry()["methods"] if name.casefold() in
               {str(x).casefold() for x in (m["id"], m["name"], *m.get("aliases", []))}]
    if len(matches) != 1:
        raise ValueError(f"方法未登记或存在歧义: {name}")
    return matches[0]
