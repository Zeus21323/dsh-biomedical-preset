#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["anndata==0.12.19", "numba==0.67.0", "numpy==2.3.5", "pandas==2.3.3", "scipy==1.18.1", "scikit-learn==1.9.0", "statsmodels==0.15.0", "tqdm==4.70.0", "matplotlib==3.11.1", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""stLearn SCTP spot-level LR testing and cell-type permutation CCI counting."""
from __future__ import annotations

import argparse
import importlib
import importlib.machinery
import json
from pathlib import Path
import pickle
import sys
import types

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
from scipy import sparse

from communication_contract import add_table, digest, new_output, write_json
from communication_inputs import read_expression


UPSTREAM_COMMIT = "03e38844a599ef4f3df8235e3f57bd74a9e96fcf"
UPSTREAM_TAG = "V1.4.1"
SOURCE_HASHES = {
    "LICENSE": "a757932fa2e32e05050046775e8722d2b12f106ba844d927a8edc82a66d10c55",
    "stlearn/__init__.py": "0224fc0aa8277e1b537cee7994793f46ffd56b16cb13d3133b45bfccc9fd7b8d",
    "stlearn/tl/cci/__init__.py": "e67054b7f502c849266a94f0999aa0977e67da758cab4548e4ba0489d8df241c",
    "stlearn/tl/cci/analysis.py": "9380c584e51d2ad2c8e0cfe52c76af58b38675f2771726d5f78c89352bf9dcd7",
    "stlearn/tl/cci/base.py": "fdb21182298b97354da1f7313d7d909ef74d7bf3e7f621c9cda2e0a38f6131f3",
    "stlearn/tl/cci/permutation.py": "86bc107853e8852c5bfe3ee0df19c72e79cfc1c8779681f970d1eb3d84c1670f",
    "stlearn/tl/cci/perm_utils.py": "7c436817c0b9f970b07fa862bfec893e6f224e869fadc425b187e817bc046bbc",
    "stlearn/tl/cci/het.py": "76a28024d6454c61f9d7aba8f2c9b36094b2b386185fa5bb7e1c2d8298fa0b26",
    "stlearn/tl/cci/het_helpers.py": "355a86f7f04a018f3581ca784f142b8fe509424eee8239c0de3ac55184f508ab",
    "stlearn/tl/cci/go.py": "37b49c928571570101d1bcafc915874ff8c699a68bb47a678046d5a7f50e8f2e",
    "stlearn/tl/cci/databases/connectomeDB2020_lit.txt": "2d9061d83e22ab3290dbb67abb42218e0c9a703e4e07021e8aee9c2e57699ae1",
    "stlearn/tl/cci/databases/connectomeDB2020_put.txt": "337c89de25850009ec58bd9b48af65200520771ab78f3a8423eec7f97eb38004",
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
            raise ValueError(f"stLearn {UPSTREAM_TAG} 固定源码缺失或摘要不符: {relative}")
    # Load only the fixed upstream CCI package. This avoids importing unrelated
    # image, deep-learning and SpatialData modules from stlearn/__init__.py.
    for name, directory in (
        ("stlearn", root / "stlearn"),
        ("stlearn.tl", root / "stlearn" / "tl"),
        ("stlearn.tl.cci", root / "stlearn" / "tl" / "cci"),
    ):
        _package(name, directory)
    analysis = importlib.import_module("stlearn.tl.cci.analysis")
    het = importlib.import_module("stlearn.tl.cci.het")
    return analysis, het


def _cfg_int(cfg, key, default, minimum):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum:
        raise ValueError(f"{key} 必须为不小于 {minimum} 的整数")
    return value


def _load_mixtures(cfg, base: Path, data, cell_type_key: str):
    if not cfg.get("spot_mixtures", False):
        return None, None
    value = cfg.get("cell_mixtures")
    if not value:
        raise ValueError("spot_mixtures=true 时必须提供 cell_mixtures 表及其来源")
    path = (base / value).resolve()
    frame = pd.read_csv(path, sep=None, engine="python", index_col=0)
    if not frame.index.is_unique or not frame.columns.is_unique:
        raise ValueError("cell_mixtures 行列名必须唯一")
    if set(frame.index) != set(data.obs_names) or list(frame.index) != list(data.obs_names):
        raise ValueError("cell_mixtures 必须与输入空间位置逐行严格对齐；不自动重排")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("cell_mixtures 必须为有限非负值")
    dominant = data.obs[cell_type_key].astype(str)
    if not set(dominant) <= set(map(str, frame.columns)):
        raise ValueError("主细胞类型标签不在 cell_mixtures 列中")
    return frame.astype(float), dict(path=str(path), sha256=digest(path), columns=list(frame.columns))


def _read_lrs(cfg, analysis, native_root: Path):
    species = cfg["species"]
    requested = cfg.get("lr_pairs")
    if requested is not None:
        if not isinstance(requested, list) or not requested or not all(isinstance(x, str) and x.count("_") == 1 for x in requested):
            raise ValueError("lr_pairs 必须为非空的 LIGAND_RECEPTOR 字符串列表")
        if len(set(requested)) != len(requested):
            raise ValueError("lr_pairs 不能重复")
        return np.array(requested, dtype=str), dict(kind="explicit_config", pairs=len(requested))
    database = cfg.get("database", "connectomeDB2020_lit")
    if database not in ("connectomeDB2020_lit", "connectomeDB2020_put"):
        raise ValueError("stLearn 原生内置资源仅接受 connectomeDB2020_lit 或 connectomeDB2020_put")
    lrs = analysis.load_lrs(database, species=species)
    resource = native_root / "stlearn" / "tl" / "cci" / "databases" / f"{database}.txt"
    return lrs, dict(kind="bundled_stlearn", name=database, pairs=len(lrs), path=str(resource), sha256=digest(resource))


def _spatial_kwargs(cfg):
    unit = cfg.get("coordinate_unit")
    if unit not in ("um", "pixel", "native") or not cfg.get("coordinate_provenance"):
        raise ValueError("必须声明真实空间 coordinate_unit 与 coordinate_provenance；UMAP 不可替代组织坐标")
    if unit == "native" and cfg.get("physical_scale_unavailable") is not True:
        raise ValueError("native 坐标必须显式设置 physical_scale_unavailable=true")
    return dict(coordinate_unit=unit, coordinate_provenance=cfg["coordinate_provenance"],
                physical_scale_unavailable=cfg.get("physical_scale_unavailable", False),
                y_down=cfg.get("y_down", False))


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    required = ("dataset", "research_question", "input", "native_root", "distance", "distance_provenance")
    for key in required:
        if key not in cfg or cfg[key] in (None, ""):
            raise ValueError("缺少: " + key)
    if cfg.get("expression_scale") not in ("normalized", "log_normalized"):
        raise ValueError("stLearn SCTP 入口只接受明确声明的 normalized 或 log_normalized 非负表达")
    if not cfg.get("normalization_definition"):
        raise ValueError("必须给出 normalization_definition；当前教程推荐未 log1p，总量归一化，作者发布对象则可核实为 log1p")
    if not isinstance(cfg["distance"], (int, float)) or not np.isfinite(cfg["distance"]) or cfg["distance"] < 0:
        raise ValueError("distance 必须是在已声明坐标单位中的非负有限距离；0 表示同 spot")
    alpha = float(cfg.get("alpha", 0.05))
    cci_alpha = float(cfg.get("cci_alpha", 0.05))
    if not 0 < alpha < 1 or not 0 < cci_alpha < 1:
        raise ValueError("alpha 与 cci_alpha 必须在 0 和 1 之间")
    n_pairs = _cfg_int(cfg, "n_pairs", 1000, 100)
    n_perms = _cfg_int(cfg, "n_perms", 1000, 1)
    cci_stability_repeats = _cfg_int(cfg, "cci_stability_repeats", 3, 2)
    cci_stability_min_fraction = float(cfg.get("cci_stability_min_fraction", 0.8))
    if not 0 < cci_stability_min_fraction <= 1:
        raise ValueError("cci_stability_min_fraction 必须在 0 和 1 之间")
    min_spots = _cfg_int(cfg, "min_spots", 20, 0)
    cci_min_spots = _cfg_int(cfg, "cci_min_spots", 3, 0)
    top_spatial_lrs = _cfg_int(cfg, "top_spatial_lrs", 6, 1)
    threads = _cfg_int(cfg, "threads", 1, 1)
    if threads > 8:
        raise ValueError("threads 不得超过 8")

    data, keys, provenance = read_expression(cfg, config.parent)
    if "_" in "".join(map(str, data.var_names)):
        bad = [str(x) for x in data.var_names if "_" in str(x)]
        raise ValueError(f"stLearn 以 '_' 分隔 LR，基因名不能含下划线；发现 {len(bad)} 个")
    coord_key = cfg.get("spatial_key", "spatial")
    if coord_key not in data.obsm:
        raise ValueError("输入缺少声明的真实空间坐标")
    coordinates = np.asarray(data.obsm[coord_key], dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("stLearn 当前入口要求与位置逐行对齐的有限二维坐标")
    mixture, mixture_provenance = _load_mixtures(cfg, config.parent, data, keys["cell_type"])
    native_root = (config.parent / cfg["native_root"]).resolve()
    analysis, het = load_native(native_root)
    lrs, lr_provenance = _read_lrs(cfg, analysis, native_root)
    spatial_meta = _spatial_kwargs(cfg)

    out = new_output(output)
    write_json(out / "run_config.json", cfg)
    bundle = dict(
        schema_version=2,
        dataset=cfg["dataset"],
        method="stLearn",
        method_version="1.4.1",
        implementation="native",
        provenance={
            **provenance,
            "parameters": cfg,
            "coordinate_provenance": cfg["coordinate_provenance"],
            "cell_mixtures": mixture_provenance,
            "lr_resource": lr_provenance,
            "source_sha256": SOURCE_HASHES,
            "upstream": {"url": "https://github.com/BiomedicalMachineLearning/stLearn", "tag": UPSTREAM_TAG,
                         "commit": UPSTREAM_COMMIT, "license": "BSD-3-Clause"},
            "statistical_semantics": {
                "spot_lr": "SCTP empirical background from expression-distribution-matched random gene pairs; BH is applied across tested LRs within each spot",
                "cell_type_cci": "cell information permutation with fixed LR scores, hotspots and expression; empirical p=count(permuted>=observed)/n_perms, no pseudocount and no multiple-testing correction",
                "direction": "cell-type matrices count an unordered spatial edge when either L-to-R or R-to-L expression orientation is present; matrix row/column is not molecular sender/receiver direction",
                "expression_scale_caveat": "current stLearn V1.4.1 tutorials explicitly recommend total normalization without log1p; the separately released breast-cancer LR result object numerically matches log1p input and must be treated as a distinct compatibility provenance",
            },
        },
        tables=[],
    )
    cell_type_rows = []
    lr_edge_rows = []
    aggregate_raw_rows = []
    aggregate_sig_rows = []
    stability_rows = []
    diagnostics = []

    samples = list(dict.fromkeys(data.obs[keys["sample"]].astype(str)))
    for sample_index, sample in enumerate(samples, 1):
        mask = data.obs[keys["sample"]].astype(str).to_numpy() == sample
        sub = data[mask].copy()
        if sub.n_obs < 20:
            raise ValueError(f"样本 {sample} 少于 20 个空间位置，无法审查邻域置换")
        sub.obsm["spatial"] = coordinates[mask].copy()
        sub.obs["imagecol"] = sub.obsm["spatial"][:, 0]
        sub.obs["imagerow"] = sub.obsm["spatial"][:, 1]
        label = "_stlearn_cell_type"
        sub.obs[label] = data.obs.loc[sub.obs_names, keys["cell_type"]].astype(str).astype("category")
        if mixture is not None:
            sub.uns[label] = mixture.loc[sub.obs_names].copy()
        np.random.seed(int(cfg.get("seed", 0)) + sample_index - 1)
        analysis.run(
            sub, lrs,
            min_spots=min_spots,
            distance=float(cfg["distance"]),
            n_pairs=n_pairs,
            n_cpus=threads,
            use_label=None,
            adj_method="fdr_bh",
            pval_adj_cutoff=alpha,
            min_expr=float(cfg.get("min_expr", 0.0)),
            save_bg=bool(cfg.get("save_background", False)),
            neg_binom=False,
            random_state=int(cfg.get("seed", 0)) + sample_index - 1,
            verbose=bool(cfg.get("verbose", True)),
        )
        if "lr_summary" not in sub.uns or "p_adjs" not in sub.obsm:
            raise ValueError(f"样本 {sample} 在原生 LR 过滤或背景生成后没有可交付检验结果")
        analysis.run_cci(
            sub, label,
            spot_mixtures=mixture is not None,
            min_spots=cci_min_spots,
            sig_spots=True,
            cell_prop_cutoff=float(cfg.get("cell_prop_cutoff", 0.2)),
            p_cutoff=cci_alpha,
            n_perms=n_perms,
            n_cpus=threads,
            random_state=int(cfg.get("seed", 0)) + sample_index - 1,
            verbose=bool(cfg.get("verbose", True)),
        )
        native_name = f"native_stlearn_{sample_index}.pkl"
        with (out / native_name).open("wb") as stream:
            pickle.dump(sub, stream, protocol=pickle.HIGHEST_PROTOCOL)

        summary = sub.uns["lr_summary"].copy()
        summary.to_csv(out / f"native_lr_summary_{sample_index}.tsv", sep="\t")
        count_columns = [x for x in ("n_spots", "n_spots_sig", "n_spots_sig_pval") if x in summary]
        add_table(bundle, out, f"lr_spot_counts_{sample_index}", "matrix",
                  [dict(row=str(lr), column=column, value=int(summary.loc[lr, column]))
                   for lr in summary.index for column in count_columns],
                  "stLearn 原生每 LR 有分数位置数、按位置内跨 LR BH 后显著位置数及未校正 P<alpha 位置数；三列均为位置计数",
                  axis_label="Spatial positions", value_kind="count", nonnegative=True,
                  display_top_rows=min(30, len(summary)), row_order=list(map(str, summary.index)), column_order=count_columns,
                  title=f"{sample}: LR spot evidence")

        all_types = list(map(str, sub.uns[f"lr_cci_raw_{label}"].index))
        raw_aggregate = sub.uns[f"lr_cci_raw_{label}"]
        sig_aggregate = sub.uns[f"lr_cci_{label}"]
        for source in all_types:
            for target in all_types:
                aggregate_raw_rows.append(dict(row=f"{sample} | {source}", column=target,
                                               value=int(raw_aggregate.loc[source, target])))
                aggregate_sig_rows.append(dict(row=f"{sample} | {source}", column=target,
                                               value=int(sig_aggregate.loc[source, target])))
        add_table(bundle, out, f"native_supported_network_{sample_index}", "network",
                  [dict(source=source, target=target, value=int(sig_aggregate.loc[source, target]))
                   for source in all_types for target in all_types if int(sig_aggregate.loc[source, target]) > 0],
                  "stLearn 原生 lr_cci 矩阵：跨入选 LR 相加的显著 CCI 空间边计数；行列由热点中心与邻居角色形成，不解析配体发送方向",
                  axis_label="Supported spatial edge count", value_kind="count", additive=True,
                  nonnegative=True, directed=False, title=f"{sample}: native supported CCI counts")
        expression = sub.to_df()
        per_raw = sub.uns[f"per_lr_cci_raw_{label}"]
        per_sig = sub.uns[f"per_lr_cci_{label}"]
        per_p = sub.uns[f"per_lr_cci_pvals_{label}"]
        helpers = importlib.import_module("stlearn.tl.cci.het_helpers")
        all_set = np.array(all_types, dtype=str)
        cell_data = helpers.get_data_for_counting(sub, label, mixture is not None, all_set)
        _, neighbourhood_indices = het.get_neighbourhoods(sub)
        maximum_p_range = 0.0
        unstable_tested_pairs = 0
        for lr_offset, lr in enumerate(per_raw):
            ligand, receptor = lr.split("_")
            lr_index = int(np.where(summary.index.to_numpy(dtype=str) == lr)[0][0])
            significant_spots = np.asarray(sub.obsm["lr_sig_scores"])[:, lr_index] > 0
            ligand_bool = expression[ligand].to_numpy() > float(cfg.get("min_expr", 0.0))
            receptor_bool = expression[receptor].to_numpy() > float(cfg.get("min_expr", 0.0))
            observed_matrix = per_raw[lr].loc[all_types, all_types].to_numpy(dtype=int)
            replicate_p = [per_p[lr].loc[all_types, all_types].to_numpy(dtype=float)]
            for repeat in range(1, cci_stability_repeats):
                replicate_p.append(het.get_interaction_pvals(
                    observed_matrix, n_perms, cell_data, neighbourhood_indices, all_set,
                    significant_spots, ligand_bool, receptor_bool,
                    float(cfg.get("cell_prop_cutoff", 0.2)),
                    int(cfg.get("seed", 0)) + sample_index * 100000 + lr_offset * 100 + repeat,
                ))
            replicate_p = np.stack(replicate_p)
            p_min = replicate_p.min(axis=0)
            p_max = replicate_p.max(axis=0)
            support_fraction = (replicate_p <= cci_alpha).mean(axis=0)
            maximum_p_range = max(maximum_p_range, float(np.max(p_max - p_min)))
            for source in all_types:
                for target in all_types:
                    source_index, target_index = all_types.index(source), all_types.index(target)
                    raw_count = int(per_raw[lr].loc[source, target])
                    p_value = float(per_p[lr].loc[source, target])
                    sig_count = int(per_sig[lr].loc[source, target])
                    stability = float(support_fraction[source_index, target_index])
                    stable_supported = bool(sig_count > 0 and stability >= cci_stability_min_fraction)
                    if raw_count > 0 and 0 < stability < 1:
                        unstable_tested_pairs += 1
                    lr_edge_rows.append(dict(sample=str(sample), source=source, target=target,
                                             ligand=ligand, receptor=receptor, score=raw_count,
                                             p_value=p_value, tested=True, supported=stable_supported,
                                             significant_count=sig_count, p_adjusted=False,
                                             cci_p_min=float(p_min[source_index, target_index]),
                                             cci_p_max=float(p_max[source_index, target_index]),
                                             cci_support_fraction=stability,
                                             orientation="native matrix row/column; molecular direction unresolved"))
                    stability_rows.append(dict(row=f"{sample} | {lr} | {source}", column=target, value=stability))

        for cell, xy, value in zip(sub.obs_names, sub.obsm["spatial"], sub.obs[label].astype(str)):
            cell_type_rows.append(dict(sample=str(sample), cell=str(cell), x=float(xy[0]), y=float(xy[1]),
                                       value=all_types.index(value) + 1, label=value))

        top_lrs = list(map(str, summary.index[summary["n_spots_sig"] > 0][:top_spatial_lrs]))
        for rank, lr in enumerate(top_lrs, 1):
            lr_index = int(np.where(summary.index.to_numpy(dtype=str) == lr)[0][0])
            scores = np.asarray(sub.obsm["lr_scores"])[:, lr_index]
            q_values = np.asarray(sub.obsm["p_adjs"])[:, lr_index]
            points = [dict(sample=str(sample), cell=str(cell), x=float(xy[0]), y=float(xy[1]), value=float(value))
                      for cell, xy, value in zip(sub.obs_names, sub.obsm["spatial"], scores)]
            add_table(bundle, out, f"lr_hotspot_score_{sample_index}_{rank}", "spatial_points", points,
                      f"{lr} 的 stLearn 原生对称邻域 LR score；同时平均 L→R 与 R→L 两个表达方向，不是分子流量",
                      axis_label=f"{lr} native LR score", value_kind="nonnegative_strength", nonnegative=True,
                      figure_role="spatial_hotspot", title=f"{sample}: {lr} LR score", **spatial_meta)
            qpoints = [dict(sample=str(sample), cell=str(cell), x=float(xy[0]), y=float(xy[1]), value=float(value))
                       for cell, xy, value in zip(sub.obs_names, sub.obsm["spatial"], q_values)]
            add_table(bundle, out, f"lr_hotspot_q_{sample_index}_{rank}", "spatial_points", qpoints,
                      f"{lr} 在每个位置的原生 BH q 值；校正范围是该位置有正 LR score 的候选 LR",
                      axis_label=f"{lr} spot-wise BH q", value_kind="p_value", direction="lower",
                      figure_role="spatial_hotspot", title=f"{sample}: {lr} adjusted P", **spatial_meta)

            ligand, receptor = lr.split("_")
            l_expr = expression[ligand].to_numpy()
            r_expr = expression[receptor].to_numpy()
            significant = np.asarray(sub.obsm["lr_sig_scores"])[:, lr_index] > 0
            forward, reverse = het.get_edges(sub, l_expr > float(cfg.get("min_expr", 0.0)),
                                             r_expr > float(cfg.get("min_expr", 0.0)), significant)
            arrow_rows = []
            index = {str(cell): i for i, cell in enumerate(sub.obs_names)}
            for orientation, edges in (("forward", forward), ("reverse", reverse)):
                for first, second in edges:
                    source_cell, target_cell = (str(first), str(second)) if orientation == "forward" else (str(second), str(first))
                    si, ti = index[source_cell], index[target_cell]
                    value = float(np.mean([l_expr[si], l_expr[ti], r_expr[si], r_expr[ti]]))
                    arrow_rows.append(dict(sample=str(sample), source_cell=source_cell, target_cell=target_cell,
                                           value=value, ligand=ligand, receptor=receptor, orientation=orientation))
            add_table(bundle, out, f"lr_spatial_arrows_{sample_index}_{rank}", "spatial_edges", arrow_rows,
                      f"{lr} 原生 get_edges 在显著 LR 位置与相邻表达位置间的 L→R 箭头；数值为原生绘图定义的两端 L/R 四值均值，只控制箭头显示色/宽，不是检验统计量",
                      axis_label="Mean endpoint LR expression", value_kind="nonnegative_strength", directed=True,
                      title=f"{sample}: {lr} spatial L-to-R links", **spatial_meta)

        n_lr = len(summary)
        n_cci_lr = len(per_raw)
        zero_cci_p = sum(float(per_p[lr].to_numpy().min()) == 0 for lr in per_p)
        asymmetry = max(float(np.abs(per_raw[lr].to_numpy() - per_raw[lr].to_numpy().T).max()) for lr in per_raw)
        diagnostics.append(dict(sample=str(sample), spots=sub.n_obs, genes=sub.n_vars, tested_lrs=n_lr,
                                cci_tested_lrs=n_cci_lr, n_pairs=n_pairs, n_perms=n_perms,
                                cci_stability_repeats=cci_stability_repeats,
                                cci_stability_min_fraction=cci_stability_min_fraction,
                                maximum_cci_p_range_across_repeats=maximum_p_range,
                                unstable_tested_cell_type_pairs=unstable_tested_pairs,
                                zero_minimum_cci_p_lrs=zero_cci_p, maximum_raw_cci_asymmetry=asymmetry,
                                native_object=native_name, native_object_sha256=digest(out / native_name)))

    add_table(bundle, out, "cell_type_locations", "spatial_points", cell_type_rows,
              "输入的主细胞类型标签，仅用于空间定位；mixture 模式的 CCI 检验另使用完整比例表",
              axis_label="Cell type", value_kind="category_code", title="Dominant cell-type locations", **spatial_meta)
    add_table(bundle, out, "cell_type_lr_counts", "lr_edges", lr_edge_rows,
              "stLearn 原生每 LR 的细胞类型行/列空间边计数；单次原生 P、显著计数和重复 P 范围均保留，supported 还要求原生重复达到声明稳定率。CCI 经验 P 无伪计数、未经多重校正，且矩阵不解析分子发送方向",
              axis_label="Spatial edge count", value_kind="count", additive=True, nonnegative=True, directed=False,
              support_rule=f"raw count>0, primary native CCI permutation p<={cci_alpha}, and support in at least {cci_stability_min_fraction:.3g} of {cci_stability_repeats} native repetitions; every p is unadjusted",
              statistical_unit="within-sample spatial edges; cell information permutation, not donors")
    add_table(bundle, out, "cci_permutation_stability", "matrix", stability_rows,
              "每个 LR 与细胞类型矩阵单元在原生 CCI 重复置换中 P<=cci_alpha 的比例；用于显示 Numba 并行随机过程的不稳定性，不是校正后概率",
              axis_label="Fraction of native repeats with P≤alpha", value_kind="proportion",
              figure_role="sensitivity", display_top_rows=30, title="stLearn CCI permutation stability")
    add_table(bundle, out, "aggregate_raw_cci", "matrix", aggregate_raw_rows,
              "stLearn 原生跨入选 LR 相加的全部细胞类型行/列空间边计数；行列不代表配体发送方向",
              axis_label="Raw spatial edge count", value_kind="count", nonnegative=True,
              title="All tested LR cell-type edge counts")
    add_table(bundle, out, "aggregate_supported_cci", "matrix", aggregate_sig_rows,
              "stLearn 原生跨 LR 相加的显著 CCI 空间边计数；每 LR 的筛选使用未校正置换 P，行列不代表配体发送方向",
              axis_label="Supported spatial edge count", value_kind="count", nonnegative=True,
              title="Permutation-supported LR cell-type edge counts")
    write_json(out / "diagnostics.json", diagnostics)
    write_json(out / "bundle.json", bundle)
    from render_result_bundle import run as render
    return render(out / "bundle.json", out / "figures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.exit(run(args.config, args.out))
