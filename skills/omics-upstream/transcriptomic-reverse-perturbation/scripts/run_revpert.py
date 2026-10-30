#!/usr/bin/env python3
"""检查输入、计算 Pearson 基线或调用已有 RevPert Essential 模型进行双方向检索。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import pickle
from pathlib import Path
import subprocess
import sys

SUPPORTED_COMMIT = "0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def texts(obj, keys):
    for key in keys:
        require(isinstance(obj.get(key), str) and obj[key].strip(), f"{key} 必须为非空字符串")


def load_inputs(config_path):
    import numpy as np
    cfg = read_json(config_path)
    require(isinstance(cfg, dict), "配置必须为 JSON 对象")
    texts(cfg, ("query", "gallery", "state_a", "state_b", "direction", "species",
                "query_context", "gallery_context", "expression_scale", "gallery_scale",
                "gallery_kind", "gallery_source", "contrast_notes"))
    require(cfg["direction"] == "B-A", "query 必须显式定义为 B-A")
    require(cfg["state_a"] != cfg["state_b"], "A、B 状态不能相同")
    require(cfg["expression_scale"] == cfg["gallery_scale"], "查询与 gallery 表达尺度不一致")
    require(cfg["gallery_kind"] in {"observed", "predicted"}, "gallery_kind 必须为 observed 或 predicted")
    warnings = []
    if cfg["query_context"] != cfg["gallery_context"]:
        texts(cfg, ("extrapolation_reason",))
        warnings.append("跨背景外推：" + cfg["extrapolation_reason"])
    query_path = (config_path.parent / cfg["query"]).resolve()
    gallery_path = (config_path.parent / cfg["gallery"]).resolve()
    query = {}
    with query_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        require(reader.fieldnames == ["gene", "value"], "query TSV 表头必须为 gene、value（两列）")
        for row in reader:
            require(None not in row and all(isinstance(v, str) for v in row.values()), "query 行必须恰好有两列")
            gene = row["gene"].strip()
            require(bool(gene) and gene not in query, f"query 含空或重复基因：{gene}")
            value = float(row["value"])
            require(math.isfinite(value) and abs(value) <= float(np.finfo(np.float32).max),
                    f"query 含非有限数值或超出 float32 范围：{gene}")
            query[gene] = value
    require(bool(query), "query 不能为空")
    with np.load(gallery_path, allow_pickle=False) as archive:
        genes_arr, kos_arr = archive["genes"], archive["kos"]
        require(genes_arr.ndim == kos_arr.ndim == 1, "genes、kos 必须为一维数组")
        require(genes_arr.dtype.kind in "US" and kos_arr.dtype.kind in "US", "genes、kos 必须为非 object 字符串数组")
        genes, kos = genes_arr.astype(str).tolist(), kos_arr.astype(str).tolist()
        raw = archive["deltas"]
        require(raw.dtype.kind in "iuf", "deltas 必须为实数数值矩阵")
        with np.errstate(over="ignore", invalid="ignore"):
            matrix = np.asarray(raw, dtype=np.float32)
    for name, axis in (("genes", genes), ("kos", kos)):
        require(axis and len(set(axis)) == len(axis), f"{name} 为空或有重复")
        require(all(x and x == x.strip() and not any(c in x for c in "\t\n\r") for x in axis),
                f"{name} 含空白或非法标识")
    require(matrix.shape == (len(kos), len(genes)), "deltas 形状须为候选扰动数 × 基因数")
    require(len(kos) >= 2, "至少需要两个候选扰动")
    require(np.isfinite(matrix).all(), "gallery 含非有限数值；请先核实原始数据")
    q = np.array([query.get(g, np.nan) for g in genes], dtype=np.float32)
    mask = np.isfinite(q)
    min_genes = cfg.get("min_genes", 10)
    min_coverage = cfg.get("min_coverage", 0.8)
    require(type(min_genes) is int and min_genes >= 10, "min_genes 必须为至少10的整数")
    require(type(min_coverage) in (int, float) and 0 < min_coverage <= 1, "min_coverage 必须在 (0,1] 内")
    require(int(mask.sum()) >= min_genes, "可匹配基因数不足")
    require(float(mask.mean()) >= min_coverage, "查询覆盖率低于配置门槛")
    require(np.std(q[mask], dtype=float) > 1e-12, "查询在匹配基因上没有有效变异")
    require(np.all(np.std(matrix[:, mask], axis=1, dtype=float) > 1e-12), "存在常量 gallery 响应，不能可靠排序")
    require(np.isfinite(q[mask]).all(), "query 数值超出支持范围")
    missing = [g for g, present in zip(genes, mask) if not present]
    if missing:
        warnings.append("查询缺失特征：Pearson 仅用共同基因；模型中缺失位置按上游约定填0。")
    focus = cfg.get("focus_genes", [])
    require(isinstance(focus, list) and all(isinstance(g, str) for g in focus), "focus_genes 必须为字符串列表")
    coverage = {"n_query_genes": len(query), "n_gallery_genes": len(genes),
                "n_overlap": int(mask.sum()), "query_feature_coverage": float(mask.mean()),
                "query_genes_not_in_gallery": sorted(set(query) - set(genes)),
                "missing_query_genes": missing, "n_candidate_perturbations": len(kos),
                "focus_not_in_catalog": sorted(set(focus) - set(kos)), "warnings": warnings}
    paths = {"config": config_path.resolve(), "query": query_path, "gallery": gallery_path}
    return cfg, genes, kos, matrix, q, mask, coverage, paths


def pearson_scores(matrix, q, mask):
    import numpy as np
    x = matrix[:, mask].astype(float)
    y = q[mask].astype(float)
    x -= x.mean(axis=1, keepdims=True)
    y -= y.mean()
    return np.clip((x @ y) / (np.linalg.norm(x, axis=1) * np.linalg.norm(y)), -1, 1)


def model_resources(cfg, paths, genes):
    texts(cfg, ("upstream_repo", "checkpoint", "model_metadata"))
    base = paths["config"].parent
    for key in ("upstream_repo", "checkpoint", "model_metadata"):
        paths[key] = (base / cfg[key]).resolve()
    actual = subprocess.check_output(["git", "-C", str(paths["upstream_repo"]), "rev-parse", "HEAD"], text=True).strip()
    require(actual == SUPPORTED_COMMIT, "上游版本未适配，请使用 reference 中固定的 commit")
    dirty = subprocess.check_output(["git", "-C", str(paths["upstream_repo"]), "status", "--porcelain", "--untracked-files=no"], text=True)
    require(not dirty.strip(), "上游工作区有已跟踪文件改动，无法确认实现版本")
    meta = read_json(paths["model_metadata"])
    require(meta["upstream_commit"] == actual, "模型 metadata 的上游版本不匹配")
    require(meta["genes"] == genes, "模型特征顺序与 gallery 不一致")
    for key in ("gallery", "checkpoint"):
        require(meta[key + "_sha256"] == digest(paths[key]), f"{key} 与模型 metadata 指纹不匹配")
    for key in ("gallery_context", "gallery_scale", "gallery_kind", "species"):
        require(meta[key] == cfg[key], f"模型 metadata 的 {key} 不匹配")
    return meta


def load_upstream(repo):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    module = importlib.import_module("reverse.scripts.run_gallery_dual_g2")
    require(Path(module.__file__).resolve().is_relative_to(repo), "导入了非指定目录的 RevPert")
    return module


def learned_scores(cfg, paths, genes, kos, matrix, q):
    import numpy as np
    import torch
    from pathlib import PosixPath, WindowsPath
    upstream = load_upstream(paths["upstream_repo"])
    # 上游 checkpoint 含 NumPy PCA 数组和 Path；仅允许这些已知类型，不回退到任意 pickle。
    namespace = "numpy._core.multiarray" if int(np.__version__.split(".")[0]) >= 2 else "numpy.core.multiarray"
    reconstruct = importlib.import_module(namespace)._reconstruct
    with torch.serialization.safe_globals([
        reconstruct, (reconstruct, "numpy.core.multiarray._reconstruct"),
        np.ndarray, np.dtype, type(np.dtype("float32")),
        type(np.dtype("float64")), PosixPath, WindowsPath,
    ]):
        ckpt = torch.load(paths["checkpoint"], map_location="cpu", weights_only=True)
    require(isinstance(ckpt, dict) and all(k in ckpt for k in ("model", "pca", "args", "gal_kos", "alpha_star")),
            "仅支持 Gallery-Dual Essential checkpoint；GWPS 或其他编码器格式需另行适配")
    require(ckpt["gal_kos"] == kos, "候选目录或顺序与 checkpoint 不一致")
    a = ckpt["args"]
    pca = upstream.PCAProjector()
    pca.load_state_dict(ckpt["pca"])
    require(np.asarray(pca.mean_).shape == (len(genes),), "PCA 均值维度不匹配")
    require(np.asarray(pca.components_).shape == (pca.n_components, len(genes)), "PCA 维度不匹配")
    require(np.isfinite(pca.mean_).all() and np.isfinite(pca.components_).all(), "PCA 含非有限参数")
    alpha = float(ckpt["alpha_star"])
    require(math.isfinite(alpha) and alpha >= 0, "checkpoint 的 alpha_star 无效")
    device = cfg.get("device", "cpu")
    require(device in {"cpu", "cuda"}, "device 只支持 cpu 或 cuda")
    require(device != "cuda" or torch.cuda.is_available(), "请求 CUDA，但当前不可用")
    model = upstream.GalleryDual(pca, emb_dim=a["emb_dim"], hidden=a["hidden"],
                                dropout=a["dropout"], shared=bool(a["shared"]))
    model.load_state_dict(ckpt["model"], strict=True)
    require(np.array_equal(model.mean.detach().numpy(), pca.mean_) and
            np.array_equal(model.components.detach().numpy(), pca.components_), "模型内部 PCA 与独立 PCA 状态不一致")
    model.to(torch.device(device)).eval()
    require(all(torch.isfinite(t).all().item() for t in model.state_dict().values()), "模型含非有限参数")
    queries = np.stack([q, -q])
    result = upstream.score_learned_np(model, queries, matrix, torch.device(device))
    require(np.isfinite(result).all(), "学习评分含非有限数值")
    return result, alpha, upstream


def ranks(scores):
    import numpy as np
    # 与固定上游版本一致：稳定降序，平分时保留 checkpoint 目录顺序。
    order = np.argsort(-scores, kind="mergesort")
    result = np.empty(len(scores), dtype=int)
    result[order] = np.arange(1, len(scores) + 1)
    return result


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_table(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def execute(config_path, out, mode):
    import numpy as np
    require(not out.exists() and not out.is_symlink(), "输出目录已存在，拒绝覆盖")
    cfg, genes, kos, matrix, q, mask, coverage, paths = load_inputs(config_path)
    # 指定任一模型资源，就要求整组资源都可核验；不会忽略半套模型配置。
    has_model = any(key in cfg for key in ("checkpoint", "model_metadata", "upstream_repo"))
    if mode == "revpert" or has_model:
        model_resources(cfg, paths, genes)
    method = {"check": "input_check", "pearson": "pearson_baseline", "revpert": "revpert_essential_fused"}[mode]
    rows, shortlist = [], []
    alpha = None
    if mode != "check":
        plus = pearson_scores(matrix, q, mask)
        pearson = np.stack([plus, -plus])
        learned = None
        scores = pearson
        if mode == "revpert":
            learned, alpha, upstream = learned_scores(cfg, paths, genes, kos, matrix, q)
            scores = upstream.fuse_scores(pearson, learned, alpha)
            if alpha == 0:
                coverage["warnings"].append("checkpoint alpha_star=0，最终分数等同 Pearson 基线。")
        require(np.isfinite(scores).all(), "融合评分含非有限数值")
        pr = [ranks(s) for s in pearson]
        rr = [ranks(s) for s in scores]
        for i, ko in enumerate(kos):
            rows.append({"ko": ko, "pearson_plus": float(pearson[0, i]), "pearson_minus": float(pearson[1, i]),
                         "learned_plus": "" if learned is None else float(learned[0, i]),
                         "learned_minus": "" if learned is None else float(learned[1, i]),
                         "score_plus": float(scores[0, i]), "score_minus": float(scores[1, i]),
                         "rank_plus": int(rr[0][i]), "rank_minus": int(rr[1][i]),
                         "pearson_rank_plus": int(pr[0][i]), "pearson_rank_minus": int(pr[1][i]),
                         "n_genes_scored": int(mask.sum())})
        top_k = cfg.get("top_k", 20)
        require(type(top_k) is int and top_k > 0, "top_k 必须为正整数")
        for arm in ("plus", "minus"):
            for row in sorted(rows, key=lambda r: r["rank_" + arm])[:top_k]:
                shortlist.append({"arm": arm, **row})
    manifest = {"mode": mode, "method": method, "config": cfg, "alpha_star": alpha,
                "upstream_commit": SUPPORTED_COMMIT if mode == "revpert" or has_model else None,
                "input_sha256": {k: digest(v) for k, v in paths.items() if k != "upstream_repo"},
                "python": sys.version.split()[0], "numpy": np.__version__,
                "status": ("checked_model_not_loaded" if has_model else "inputs_checked") if mode == "check" else "completed",
                "rank_ties": "stable_catalog_order"}
    if mode == "revpert":
        import torch
        manifest["torch"] = torch.__version__
    # 计算与校验结束后才创建全新输出目录，拒绝覆盖及跟随已有目录链接。
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "run_manifest.json", manifest)
    write_json(out / "coverage.json", coverage)
    if rows:
        write_table(out / "ranking.tsv", rows)
        write_table(out / "shortlist.tsv", shortlist)
    lines = ["# 逆向扰动运行摘要", "", f"方法：{method}。", "",
             f"状态 A：{cfg['state_a']}；状态 B：{cfg['state_b']}。查询定义：B − A。", "",
             "plus：匹配 B − A 的扰动响应；minus：匹配 A − B 的扰动响应。", "",
             f"特征覆盖：{coverage['n_overlap']}/{len(genes)}；候选扰动：{len(kos)}。", "",
             "本输出提供候选方向和排序，不代表因果概率、真实过表达效应或治疗结论。", ""]
    if mode == "check":
        lines.extend(["已检查输入及已提供模型资源的关联；未加载模型、未评分。", ""])
    else:
        lines.extend(["完整结果：[双方向排序](ranking.tsv)；[两臂短名单](shortlist.tsv)。", "",
                      "同分时按原始目录顺序排列；名次差异不一定代表证据强弱。", ""])
    for warning in coverage["warnings"]:
        lines.extend(["- " + warning, ""])
    if coverage["focus_not_in_catalog"]:
        lines.extend(["无法评价的关注基因：" + "、".join(coverage["focus_not_in_catalog"]), ""])
    lines.extend(["覆盖详情：[coverage.json](coverage.json)；运行与资源记录：[run_manifest.json](run_manifest.json)。", ""])
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("check", "pearson", "revpert"))
    parser.add_argument("--config", required=True, type=Path, help="输入与背景 JSON 配置")
    parser.add_argument("--out-dir", required=True, type=Path, help="尚不存在的输出目录")
    args = parser.parse_args(argv)
    try:
        execute(args.config, args.out_dir, args.mode)
        print(f"已完成 {args.mode}：{args.out_dir}")
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, ImportError, RuntimeError,
            pickle.UnpicklingError, EOFError, subprocess.SubprocessError) as exc:
        print(f"逆向扰动执行失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
