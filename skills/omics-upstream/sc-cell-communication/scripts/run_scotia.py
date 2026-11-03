#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = ["anndata==0.10.9", "numpy==1.26.4", "pandas==2.2.3", "scipy==1.13.1", "scikit-learn==1.5.2", "POT==0.9.6.post1", "forest-fire-clustering==0.0.25", "scanpy==1.10.4", "statsmodels==0.14.4", "matplotlib==3.9.4", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""Native SCOTIA clustering, spatially constrained OT and tutorial permutation inference."""
from __future__ import annotations

import argparse
import importlib
import importlib.machinery
import json
from pathlib import Path
import pickle
import random
import sys
import types

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import distance_matrix
from statsmodels.stats.multitest import multipletests

from communication_contract import add_table, digest, new_output, write_json, write_table
from communication_inputs import read_expression, require_version


UPSTREAM_COMMIT = "5c5feef08c1bb0d68e654b2f436be17cef2b36e7"
UPSTREAM_VERSION = "1.0.0"
SOURCE_HASHES = {
    "LICENSE.txt": "74e587e533f4f609a2f9e3c0fedd355c7f7683907a699d3bc8956e3755cd97ee",
    "setup.py": "ce11f0323983e7d5643e57428d428e0fdd67df2c93528cbfc4ebaf27bc36d500",
    "scotia/__init__.py": "e2bfd24fa0a1cd7d350f5c1c3dd40b4ed85f9ffbccba63dcf9b3724acf865698",
    "scotia/dbscan.py": "a075cabfc84cc7be70331c669180e7aca431e24c39dfe157df074e86328ddc06",
    "scotia/ot.py": "a16a446e8791f9d4d166af45d3788663e9454677c26a5a990196ed5438759399",
    "scotia/permutation.py": "b6b315ed30c9d1b16660bb7a24d130552d0904d93857f50172b4c883451058c2",
    "scotia/run_scotia.py": "8a302ddffe772b622503fe99813f743c44e060e1a2fc3610db6602843873474a",
    "scotia/visualization.py": "722cb643d36d98a3aa275cd1c946fdc421eb7245ea748e63ea832c6e9802f5ce",
}


def _package(name: str, directory: Path) -> None:
    module = types.ModuleType(name)
    module.__file__ = str(directory / "__init__.py")
    module.__package__ = name
    module.__path__ = [str(directory)]
    spec = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [str(directory)]
    module.__spec__ = spec
    sys.modules[name] = module


def load_native(root: Path):
    root = root.resolve()
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"SCOTIA 固定源码缺失或摘要不符: {relative}")
    _package("scotia", root / "scotia")
    return (
        importlib.import_module("scotia.dbscan"),
        importlib.import_module("scotia.ot"),
        importlib.import_module("scotia.permutation"),
    )


def _integer(cfg, key, default, minimum):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{key} 必须为不小于 {minimum} 的整数")
    return value


def _number(cfg, key, default, *, positive=False, nonnegative=False):
    value = cfg.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value):
        raise ValueError(f"{key} 必须为有限数值")
    if positive and value <= 0 or nonnegative and value < 0:
        raise ValueError(f"{key} 数值范围无效")
    return float(value)


def _load_lrs(cfg, base: Path, genes: set[str]):
    for key in ("lr_resource", "lr_resource_version", "lr_resource_provenance", "lr_resource_species"):
        if not cfg.get(key):
            raise ValueError(f"缺少 {key}；SCOTIA 不内置可替代的通用 LR 来源")
    if cfg["lr_resource_species"] != cfg["species"]:
        raise ValueError("LR 资源物种与输入物种不一致")
    path = (base / cfg["lr_resource"]).resolve()
    header = 0 if cfg.get("lr_resource_header", False) else None
    frame = pd.read_csv(path, sep=None, engine="python", header=header)
    if header == 0 and {"l_gene", "r_gene"} <= set(frame.columns):
        frame = frame[["l_gene", "r_gene"]]
    elif frame.shape[1] == 2:
        frame = frame.iloc[:, :2]
        frame.columns = ["l_gene", "r_gene"]
    else:
        raise ValueError("LR 资源必须恰有 l_gene/r_gene 两列，或声明无表头的两列文件")
    frame = frame.astype(str).apply(lambda column: column.str.strip())
    if frame.eq("").any().any() or frame.duplicated().any():
        raise ValueError("LR 资源含空值或重复分子对")
    if any("|" in value for value in frame.to_numpy().ravel()):
        raise ValueError("SCOTIA 原生标签使用 | 分隔，基因名不能含 |")
    if any("_" in value for value in frame.to_numpy().ravel()):
        raise ValueError("SCOTIA 原生标签使用下划线拼接 LR，当前入口拒绝端点基因名中的下划线以避免分子身份歧义")
    valid = frame[frame.l_gene.isin(genes) & frame.r_gene.isin(genes)].copy()
    dropped = frame.loc[~frame.index.isin(valid.index)].copy()
    if valid.empty:
        raise ValueError("输入表达中没有完整可检验的 LR")
    labels = valid.l_gene + "_" + valid.r_gene
    if labels.duplicated().any():
        raise ValueError("LR 名称经 SCOTIA 下划线拼接后不唯一")
    return valid.reset_index(drop=True), dropped.reset_index(drop=True), {
        "path": str(path), "sha256": digest(path), "version": cfg["lr_resource_version"],
        "provenance": cfg["lr_resource_provenance"], "species": cfg["lr_resource_species"],
        "input_pairs": len(frame), "valid_pairs": len(valid), "missing_gene_pairs": len(dropped),
    }


def _auto_eps_range(coords):
    extent = min(float(np.ptp(coords[:, 0])), float(np.ptp(coords[:, 1])))
    stop = int(extent / 4)
    step = 5 if extent / 4 > 50 else 1
    values = list(range(15, stop, step))
    if not values:
        raise ValueError("FOV 尺寸不足以形成 SCOTIA 一键入口的自动 eps 搜索区间；请给出有依据的 eps_range")
    return values


def _summary(native_ot, edges: pd.DataFrame, label: str, iteration=None):
    if edges.empty:
        return []
    native = native_ot.post_ot(edges, label=label, it_n_label=iteration)
    values = dict(zip(native["label"].astype(str), native["ave_likelihood"].astype(float)))
    structured = {}
    for ligand_receptor, source, target in edges[["ligand_recptor", "source_cell_type", "target_cell_type"]].drop_duplicates().itertuples(index=False):
        suffix = f"|{iteration}" if iteration is not None else ""
        native_label = f"{ligand_receptor}|{label}|{source}_{target}{suffix}"
        key = (str(ligand_receptor), str(source), str(target))
        if native_label in values:
            if native_label in structured and structured[native_label] != key:
                raise ValueError("细胞类型下划线拼接造成 SCOTIA 原生标签碰撞")
            structured[native_label] = key
    if set(values) != set(structured):
        raise ValueError("无法无歧义映射 SCOTIA 原生 post_ot 标签")
    return [dict(interaction=key[0], source=key[1], target=key[2], score=values[label_key])
            for label_key, key in structured.items()]


def _native_edges(native_ot, distances, expression, metadata, lrs, **parameters):
    raw = native_ot.source_target_ot(distances.copy(), expression, metadata, lrs, **parameters)
    columns = ["source_cell_idx", "receptor_cell_idx", "likelihood", "ligand_recptor", "source_cell_type", "target_cell_type"]
    if raw.empty:
        return pd.DataFrame(columns=columns + ["cell_pairs"])
    raw.columns = columns
    raw["cell_pairs"] = raw["source_cell_type"].astype(str) + "_" + raw["target_cell_type"].astype(str)
    return raw


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    for key in ("dataset", "research_question", "input", "native_root", "fov_key",
                "coordinate_provenance", "distance_cutoff_provenance", "random_range_provenance"):
        if not cfg.get(key):
            raise ValueError("缺少: " + key)
    if cfg.get("expression_scale") != "counts":
        raise ValueError("SCOTIA 固定入口按作者流程只接受真实非负整数 counts，再按全输入基因正值 99% 分位缩放并截断到 1")
    if cfg.get("coordinate_unit") != "um":
        raise ValueError("SCOTIA 当前原生契约要求微米坐标；像素必须先用有依据的比例换算")
    n_permutations = _integer(cfg, "n_permutations", 50, 20)
    min_cluster_size = _integer(cfg, "min_cluster_size", 10, 2)
    seed = _integer(cfg, "seed", 123, 0)
    distance_cutoff = _number(cfg, "distance_cutoff", 50, positive=True)
    random_range = _integer(cfg, "random_range", 20, 0)
    reg = _number(cfg, "reg", 1, positive=True)
    reg_m = _number(cfg, "reg_m", 2, positive=True)
    min_likelihood = _number(cfg, "min_likelihood", 0.01, nonnegative=True)
    alpha = _number(cfg, "alpha", 0.05, positive=True)
    if alpha >= 1:
        raise ValueError("alpha 必须小于 1")
    support_metric = cfg.get("support_metric", "bh_within_sample_cell_pair")
    if support_metric not in ("raw_p", "bh_within_sample_cell_pair"):
        raise ValueError("support_metric 只接受 raw_p 或 bh_within_sample_cell_pair")
    top_spatial = _integer(cfg, "top_spatial_interactions", 3, 1)

    require_version("numpy", "1.26.4")
    require_version("POT", "0.9.6.post1")
    require_version("scikit-learn", "1.5.2")
    require_version("forest-fire-clustering", "0.0.25")
    data, keys, input_provenance = read_expression(cfg, config.parent)
    fov_key = cfg["fov_key"]
    if fov_key not in data.obs or data.obs[fov_key].isna().any() or data.obs[fov_key].astype(str).str.strip().eq("").any():
        raise ValueError("缺失或空 FOV metadata")
    data.obs[fov_key] = data.obs[fov_key].astype(str)
    coordinates = np.asarray(data.obsm.get(cfg.get("spatial_key", "spatial")), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("输入必须有与细胞逐行严格对齐的有限二维真实空间坐标")
    maximum_dense = _integer(cfg, "maximum_dense_elements", 50_000_000, 1)
    if data.n_obs * data.n_vars > maximum_dense:
        raise ValueError("SCOTIA 原生实现会稠密化表达矩阵；输入超过声明的 maximum_dense_elements")
    matrix = data.X.toarray() if sparse.issparse(data.X) else np.asarray(data.X)
    if not np.allclose(matrix, np.round(matrix), atol=1e-7):
        raise ValueError("counts 层包含非整数值")
    expression_all = pd.DataFrame(matrix, index=data.obs_names, columns=data.var_names, dtype=float)
    positive = expression_all.where(expression_all > 0)
    quantiles = positive.quantile(q=0.99, axis=0)
    lrs, dropped_lrs, lr_provenance = _load_lrs(cfg, config.parent, set(map(str, data.var_names)))
    usable = {g for g in set(lrs.l_gene) | set(lrs.r_gene) if np.isfinite(quantiles[g]) and quantiles[g] > 0}
    invalid_quantile = lrs[~lrs.l_gene.isin(usable) | ~lrs.r_gene.isin(usable)].copy()
    lrs = lrs[lrs.l_gene.isin(usable) & lrs.r_gene.isin(usable)].reset_index(drop=True)
    if lrs.empty:
        raise ValueError("所有 LR 至少一个端点没有正表达，无法做 99% 分位缩放")
    native_dbscan, native_ot, native_permutation = load_native((config.parent / cfg["native_root"]).resolve())

    output_root = new_output(output)
    write_json(output_root / "run_config.json", cfg)
    bundle = dict(schema_version=2, dataset=cfg["dataset"], method="SCOTIA", method_version=UPSTREAM_VERSION,
                  implementation="native", provenance={**input_provenance,
        "parameters": cfg, "coordinate_provenance": cfg["coordinate_provenance"],
        "upstream": {"url": "https://github.com/Caochris/SCOTIA", "commit": UPSTREAM_COMMIT,
                     "version": UPSTREAM_VERSION, "license": "MIT"},
        "source_sha256": SOURCE_HASHES, "lr_resource": lr_provenance,
        "normalization": "Across the complete input, divide each gene by its positive-value 0.99 quantile and clip values above 1, exactly as the SCOTIA quick-start workflow.",
        "statistical_semantics": {
            "score": "For each FOV, native post_ot takes the maximum retained OT likelihood per source cell and then averages across source cells, requiring at least eight retained cell edges; tutorial multi-FOV summaries sum these FOV values.",
            "permutation": "Native permutation_test jointly shuffles expression row assignment and jitters both coordinates; cluster-pair eligibility remains fixed. P=count(null likelihood strictly greater than observed)/n_permutations, missing null candidates count as zero, with no pseudocount.",
            "multiple_testing": "BH q is added within each sample and directed cell-type pair across native post_ot-eligible LR candidates; support_metric records whether raw P or this q defines support.",
            "statistical_unit": "Within-sample/FOV cell patterns and tutorial permutations, not independent donors.",
        }}, tables=[])

    spatial_points = []
    cluster_points = []
    cluster_membership = []
    dbscan_eps_rows = []
    cluster_coverage_rows = []
    cell_edge_rows = []
    native_edge_artifact = []
    observed_by_sample = {}
    null_by_sample = {}
    diagnostics = []
    native_state = {}
    explicit_eps = cfg.get("eps_range")
    if explicit_eps is not None:
        if not isinstance(explicit_eps, list) or not explicit_eps or not all(type(x) is int and x > 0 for x in explicit_eps) or len(set(explicit_eps)) != len(explicit_eps):
            raise ValueError("eps_range 必须为唯一正整数列表")
        explicit_eps = sorted(explicit_eps)

    sample_order = list(dict.fromkeys(data.obs[keys["sample"]].astype(str)))
    for sample_index, sample in enumerate(sample_order):
        sample_mask = data.obs[keys["sample"]].to_numpy() == sample
        sample_indices = np.flatnonzero(sample_mask)
        sample_observed = {}
        sample_null = [dict() for _ in range(n_permutations)]
        fov_values = list(dict.fromkeys(data.obs.iloc[sample_indices][fov_key].astype(str)))
        sample_native = {}
        for fov_index, fov in enumerate(fov_values):
            global_indices = sample_indices[data.obs.iloc[sample_indices][fov_key].to_numpy() == fov]
            if len(global_indices) < min_cluster_size:
                raise ValueError(f"样本 {sample} FOV {fov} 少于 min_cluster_size 个细胞")
            obs = data.obs.iloc[global_indices].copy()
            coords = coordinates[global_indices].copy()
            plot_sample = f"{sample} | FOV {fov}"
            obs["index"] = np.arange(len(obs))
            obs["annotation"] = obs[keys["cell_type"]].astype(str)
            eps_range = explicit_eps or _auto_eps_range(coords)
            clusters = []
            membership = np.full(len(obs), "not retained", dtype=object)
            eps_by_type = {}
            for cell_type in sorted(obs["annotation"].unique()):
                local = obs.index[obs["annotation"] == cell_type]
                positions = obs.index.get_indexer(local)
                retained = 0
                eps_value = None
                if len(positions) >= min_cluster_size:
                    idx_list, eps_value = native_dbscan.dbscan_ff_cell(
                        coords[positions], positions, min_cluster_size=min_cluster_size,
                        eps_range=eps_range, ff_sed=seed)
                    for cluster_index, cell_ids in enumerate(idx_list, 1):
                        cell_ids = np.asarray(cell_ids, dtype=int)
                        clusters.append(dict(cell_type=str(cell_type), cell_idx=cell_ids))
                        membership[cell_ids] = f"{cell_type} · cluster {cluster_index}"
                        retained += len(cell_ids)
                eps_by_type[str(cell_type)] = eps_value
                dbscan_eps_rows.append(dict(row=plot_sample, column=str(cell_type), value=eps_value))
                cluster_coverage_rows.extend([
                    dict(row=f"{plot_sample} | {cell_type}", column="All cells", value=len(positions)),
                    dict(row=f"{plot_sample} | {cell_type}", column="Retained in clusters", value=retained),
                ])
            cluster_df = pd.DataFrame(clusters, columns=["cell_type", "cell_idx"])
            full_distances = distance_matrix(coords, coords)
            filtered_distances = native_ot.sel_pot_inter_cluster_pairs(full_distances, cluster_df)
            exp_fov = expression_all.iloc[global_indices].copy().reset_index(drop=True)
            exp_fov = exp_fov.divide(quantiles, axis=1).clip(upper=1)
            meta = obs.reset_index(drop=True)
            parameters = dict(reg=reg, reg_m=reg_m, dist_cutoff=distance_cutoff, min_likeli_cutoff=min_likelihood)
            edges = _native_edges(native_ot, filtered_distances, exp_fov, meta, lrs, **parameters)
            observed = _summary(native_ot, edges, sample)
            for row in observed:
                key = (row["interaction"], row["source"], row["target"])
                sample_observed[key] = sample_observed.get(key, 0.0) + row["score"]

            random.seed(seed + sample_index * 10000 + fov_index)
            np.random.seed(seed + sample_index * 10000 + fov_index)
            random_positions, shuffled_expression = native_permutation.permutation_test(
                coords, it_n=n_permutations, random_range=random_range)
            excluded = ~np.isfinite(filtered_distances)
            for iteration in range(n_permutations):
                perm_exp = exp_fov.loc[list(shuffled_expression.iloc[:, iteration])]
                perm_dist = distance_matrix(np.asarray(random_positions.iloc[:, iteration * 2:iteration * 2 + 2]),
                                            np.asarray(random_positions.iloc[:, iteration * 2:iteration * 2 + 2]))
                perm_dist[excluded] = np.inf
                perm_edges = _native_edges(native_ot, perm_dist, perm_exp, meta, lrs, **parameters)
                for row in _summary(native_ot, perm_edges, sample, iteration):
                    key = (row["interaction"], row["source"], row["target"])
                    sample_null[iteration][key] = sample_null[iteration].get(key, 0.0) + row["score"]

            ids = list(map(str, obs.index))
            cell_types = list(map(str, obs["annotation"]))
            for cell_id, xy, cell_type, cluster_label in zip(ids, coords, cell_types, membership):
                spatial_points.append(dict(sample=plot_sample, cell=cell_id, x=float(xy[0]), y=float(xy[1]),
                                           value=0, label=cell_type))
                cluster_membership.append(dict(sample=plot_sample, cell=cell_id, cell_type=cell_type,
                                               cluster=str(cluster_label)))
            display_membership = membership if len(set(membership)) <= 20 else np.where(membership == "not retained", "not retained", "retained cluster")
            label_order = sorted(set(map(str, display_membership)))
            for cell_id, xy, label in zip(ids, coords, display_membership):
                cluster_points.append(dict(sample=plot_sample, cell=cell_id, x=float(xy[0]), y=float(xy[1]),
                                           value=label_order.index(str(label)) + 1, label=str(label)))
            for row in edges.itertuples(index=False):
                source_cell = ids[int(row.source_cell_idx)]
                target_cell = ids[int(row.receptor_cell_idx)]
                ligand, receptor = str(row.ligand_recptor).split("_", 1)
                cell_edge_rows.append(dict(sample=plot_sample, source_cell=source_cell, target_cell=target_cell,
                                           value=float(row.likelihood), ligand=ligand, receptor=receptor,
                                           interaction=str(row.ligand_recptor), source_type=str(row.source_cell_type),
                                           target_type=str(row.target_cell_type)))
                native_edge_artifact.append(dict(sample=sample, fov=fov, source_cell=source_cell, target_cell=target_cell,
                                                 likelihood=float(row.likelihood), ligand=ligand, receptor=receptor,
                                                 source_type=str(row.source_cell_type), target_type=str(row.target_cell_type)))
            sample_native[fov] = dict(cluster_df=cluster_df, eps_by_type=eps_by_type, observed_edges=edges,
                                      permutation_positions=random_positions, permutation_expression_indices=shuffled_expression)
            diagnostics.append(dict(sample=sample, fov=fov, cells=len(obs), cell_types=obs["annotation"].nunique(),
                                    retained_clusters=len(cluster_df), retained_cluster_cells=int(np.sum(membership != "not retained")),
                                    native_cell_edges=len(edges), native_post_ot_candidates=len(observed), eps_range=eps_range))
        observed_by_sample[sample] = sample_observed
        null_by_sample[sample] = sample_null
        native_state[sample] = sample_native

    edge_rows = []
    null_rows = []
    observed_null_rows = []
    donor_by_sample = data.obs.groupby(keys["sample"], observed=True)[keys["donor"]].first().to_dict()
    condition_by_sample = data.obs.groupby(keys["sample"], observed=True)[keys["condition"]].first().to_dict()
    for sample in sample_order:
        candidates = observed_by_sample[sample]
        p_values = {key: sum(null_by_sample[sample][i].get(key, 0.0) > score for i in range(n_permutations)) / n_permutations
                    for key, score in candidates.items()}
        q_values = {}
        pairs = sorted({(key[1], key[2]) for key in candidates})
        for source, target in pairs:
            keys_in_pair = sorted(key for key in candidates if key[1:] == (source, target))
            adjusted = multipletests([p_values[key] for key in keys_in_pair], method="fdr_bh")[1]
            q_values.update(zip(keys_in_pair, map(float, adjusted)))
        for key, score in sorted(candidates.items()):
            interaction, source, target = key
            ligand, receptor = interaction.split("_", 1)
            supported = p_values[key] < alpha if support_metric == "raw_p" else q_values[key] < alpha
            null_values = [null_by_sample[sample][i].get(key, 0.0) for i in range(n_permutations)]
            edge_rows.append(dict(sample=sample, donor=donor_by_sample[sample], condition=condition_by_sample[sample],
                                  source=source, target=target, ligand=ligand, receptor=receptor, interaction=interaction,
                                  score=float(score), p_value=float(p_values[key]), q_value=float(q_values[key]),
                                  tested=True, supported=bool(supported), n_fovs=len({str(x) for x in data.obs.loc[data.obs[keys['sample']] == sample, fov_key]}),
                                  null_median=float(np.median(null_values)), null_q95=float(np.quantile(null_values, .95))))
            candidate_label = f"{sample} | {interaction} | {source} → {target}"
            observed_null_rows.extend([
                dict(row=candidate_label, column="Observed", value=float(score)),
                dict(row=candidate_label, column="Null median", value=float(np.median(null_values))),
                dict(row=candidate_label, column="Null 95% quantile", value=float(np.quantile(null_values, .95))),
            ])
            null_rows.extend(dict(row=candidate_label, column=f"Permutation {i + 1}", value=float(value))
                             for i, value in enumerate(null_values))

    dropped_all = pd.concat([dropped_lrs.assign(reason="missing endpoint gene"),
                             invalid_quantile.assign(reason="endpoint has no positive expression")], ignore_index=True)
    write_table(output_root / "excluded_lr_pairs.tsv", dropped_all.to_dict("records"),
                ["l_gene", "r_gene", "reason"] if dropped_all.empty else None)
    write_table(output_root / "native_cell_edges.tsv", native_edge_artifact,
                ["sample", "fov", "source_cell", "target_cell", "likelihood", "ligand", "receptor", "source_type", "target_type"])
    write_table(output_root / "native_cluster_membership.tsv", cluster_membership,
                ["sample", "cell", "cell_type", "cluster"])
    with (output_root / "native_scotia.pkl").open("wb") as stream:
        pickle.dump(native_state, stream, protocol=pickle.HIGHEST_PROTOCOL)
    bundle["provenance"]["artifacts"] = {
        name: {"path": name, "sha256": digest(output_root / name)} for name in
        ("excluded_lr_pairs.tsv", "native_cell_edges.tsv", "native_cluster_membership.tsv", "native_scotia.pkl")
    }

    spatial_meta = dict(coordinate_unit="um", coordinate_provenance=cfg["coordinate_provenance"],
                        y_down=bool(cfg.get("y_down", False)))
    add_table(bundle, output_root, "cell_type_locations", "spatial_points", spatial_points,
              "输入的真实单细胞类型和微米坐标；每个 sample/FOV 独立分面，不把局部 FOV 坐标叠加",
              axis_label="Cell type", value_kind="category_code", title="SCOTIA input cell types", **spatial_meta)
    add_table(bundle, output_root, "native_cluster_locations", "spatial_points", cluster_points,
              "SCOTIA 原生 DBSCAN/forest-fire 一致性选择保留的细胞簇；not retained 包括噪声、过小细胞类型或未得到合格 eps 的细胞",
              axis_label="Native spatial cluster", value_kind="category_code", title="SCOTIA native spatial clusters", **spatial_meta)
    add_table(bundle, output_root, "dbscan_selected_eps", "matrix", dbscan_eps_rows,
              "每个 sample/FOV/细胞类型由原生 DBSCAN 与 forest-fire 聚类一致性选择的 eps；NA 表示没有合格 eps",
              axis_label="Selected eps (μm)", value_kind="distance", title="SCOTIA selected DBSCAN eps")
    add_table(bundle, output_root, "cluster_coverage", "matrix", cluster_coverage_rows,
              "每个细胞类型的输入细胞数与进入原生空间簇的细胞数；未入簇细胞不会进入后续 OT",
              axis_label="Cells", value_kind="count", nonnegative=True, column_order=["All cells", "Retained in clusters"],
              title="SCOTIA cluster eligibility")
    add_table(bundle, output_root, "cell_type_lr_likelihood", "lr_edges", edge_rows,
              "SCOTIA 原生 post_ot 候选：每 FOV 对每个源细胞取保留 OT 边最大 likelihood 后求源细胞均值，至少需要 8 条保留边，再按作者多 FOV 教程跨 FOV 求和；P 为双随机置换严格大于观测的比例，无伪计数；q 是同一样本与有向细胞类型对内跨 LR 的 BH",
              axis_label="Summed native mean-max OT likelihood", value_kind="nonnegative_strength", additive=True,
              nonnegative=True, directed=True, direction="higher",
              support_rule=(f"raw permutation P < {alpha}" if support_metric == "raw_p" else f"BH q < {alpha} within sample and directed cell-type pair"),
              candidate_scope="native post_ot candidates with at least eight retained cell-level OT edges per contributing FOV",
              statistical_unit="within-sample/FOV cell patterns; no donor-level condition test")
    add_table(bundle, output_root, "observed_vs_permutation", "matrix", observed_null_rows,
              "每个原生 post_ot 候选的观测跨 FOV 汇总 likelihood、置换中位数和置换 95% 分位数；三列单位相同",
              axis_label="Summed native mean-max OT likelihood", value_kind="nonnegative_strength", nonnegative=True,
              column_order=["Observed", "Null median", "Null 95% quantile"], display_top_rows=30,
              title="SCOTIA observed and permutation reference")
    add_table(bundle, output_root, "permutation_null", "matrix", null_rows,
              "SCOTIA 原生坐标抖动加表达行置换得到的逐轮候选 likelihood；某轮不满足 post_ot 至少 8 条边时按作者比较逻辑记 0",
              axis_label="Summed native mean-max OT likelihood", value_kind="nonnegative_strength", nonnegative=True,
              display_top_rows=30, display_top_columns=min(30, n_permutations), figure_role="sensitivity",
              title="SCOTIA permutation null values")

    ordered = sorted(edge_rows, key=lambda row: (not row["supported"], row["q_value"], row["p_value"], -row["score"]))
    selected_interactions = []
    for row in ordered:
        key = (row["interaction"], row["source"], row["target"])
        if key not in selected_interactions:
            selected_interactions.append(key)
        if len(selected_interactions) >= top_spatial:
            break
    for rank, (interaction, source, target) in enumerate(selected_interactions, 1):
        rows = [row for row in cell_edge_rows if row["interaction"] == interaction and row["source_type"] == source and row["target_type"] == target]
        if not rows:
            continue
        add_table(bundle, output_root, f"top_ot_cell_edges_{rank}", "spatial_edges", rows,
                  f"{interaction}、{source}→{target} 的 SCOTIA 原生细胞级非平衡 OT likelihood；展示按全表绝对值前 100 边，完整边保留在源表",
                  axis_label="Native cell-level OT likelihood", value_kind="nonnegative_strength", nonnegative=True,
                  directed=True, title=f"{interaction}: {source} to {target}", **spatial_meta)

    write_json(output_root / "diagnostics.json", diagnostics)
    write_json(output_root / "bundle.json", bundle)
    from render_result_bundle import run as render
    return render(output_root / "bundle.json", output_root / "figures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    sys.exit(run(arguments.config, arguments.out))
