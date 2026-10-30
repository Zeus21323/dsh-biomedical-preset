#!/usr/bin/env python3
# /// script
# requires-python = "==3.10.20"
# dependencies = ["anndata==0.10.6", "numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "scikit-learn==1.4.1.post1", "statsmodels==0.15.0", "torch==1.13.1", "Mesa==1.0.0", "POT==0.9.6.post1", "sparselinear==0.0.5"]
# ///
"""Run the fixed CellAgentChat 0.2.0 base ABM and native permutation model."""
from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import random
import subprocess
import sys
import types
import warnings
from pathlib import Path

sys.dont_write_bytecode = True
import anndata as ad
import numpy as np
import pandas as pd
import torch
from scipy import sparse

from communication_contract import add_table, digest, new_output, write_json, write_table


COMMIT = "310cfc03df91c5ec917f110801e0c2ae4ab57800"
SOURCE_HASHES = {
    "src/Communication.py": "0c2b2ad8206832b78dfdf57b66008720e9cf7358c0745fe93d3446a1245af0eb",
    "src/abm.py": "9e694852e55bbd2a0637def9d93172fd5b7062ce3281fbb4c23d9a2810c680ed",
    "src/bckground_distribution.py": "3000512010d34fa69448566685ff22718f5fd64a0496959d088a15a231d74d95",
    "src/model_setup.py": "a5c8227d072bfc58c44b227ae3976b50d322f13715be071a9fb665aaff06e0f5",
    "src/permutations.py": "aa4ab15ca760444e9df5b8e88a17b2531cc3bbaf9d8ccabae543c1c4d52c0e8f",
    "src/preprocessor.py": "63e12a7555d7e484a2c5cbe76a8a13f9bfcaa5aa8f3a9589467e2b9855e3d4c4",
}
VERSIONS = {
    "anndata": "0.10.6", "numpy": "1.26.4", "pandas": "2.2.1", "scipy": "1.12.0",
    "scikit-learn": "1.4.1.post1", "statsmodels": "0.15.0", "torch": "1.13.1",
    "Mesa": "1.0.0", "POT": "0.9.6.post1", "sparselinear": "0.0.5",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def verify_source(root: Path):
    observed_commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if observed_commit != COMMIT:
        raise ValueError("CellAgentChat固定源码提交不符")
    for name, expected in SOURCE_HASHES.items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"CellAgentChat固定源码缺失或摘要不符: {name}")
    if sys.version_info[:3] != (3, 10, 20):
        raise ValueError("CellAgentChat兼容环境固定为Python 3.10.20")
    observed = {name: importlib.metadata.version(name) for name in VERSIONS}
    if observed != VERSIONS:
        raise ValueError(f"CellAgentChat兼容依赖版本不符: {observed}")

    # Upstream imports torch-sparse through sparselinear at module import even though the
    # one-step base ABM never uses that neural layer. Keep it unavailable and fail loudly
    # if a future code path tries to instantiate it; this runner does not claim the neural branch.
    stub = types.ModuleType("sparselinear")
    class UnavailableSparseLinear(torch.nn.Module):
        def __init__(self, *args, **kwargs):
            raise RuntimeError("CellAgentChat neural conversion-rate branch is outside the base-ABM runner")
    stub.SparseLinear = UnavailableSparseLinear
    sys.modules["sparselinear"] = stub
    sys.path.insert(0, str(root / "src"))
    from model_setup import load_db
    from abm import CellModel, get_lr_interactions2
    from permutations import permutation_test
    from bckground_distribution import get_distribution, get_significant_lr_pairs
    return load_db, CellModel, get_lr_interactions2, permutation_test, get_distribution, get_significant_lr_pairs, observed


def dense_expression(adata: ad.AnnData, layer: str | None) -> np.ndarray:
    values = adata.layers[layer] if layer else adata.X
    values = values.toarray() if sparse.issparse(values) else np.asarray(values)
    if values.ndim != 2 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("CellAgentChat表达必须是有限非负细胞×基因矩阵")
    if np.any(values.sum(axis=1) <= 0):
        raise ValueError("CellAgentChat输入存在零表达细胞")
    return values.astype(float, copy=False)


def parse_pair(value: str) -> tuple[str, str]:
    if "-" not in value:
        raise ValueError(f"原生LR身份无法解析: {value}")
    return tuple(value.split("-", 1))


def flatten(scores: dict, pvalues: dict, tested_pairs: set[str], sample: str):
    rows = []
    for cell_pair in sorted(scores):
        if "_" not in cell_pair:
            raise ValueError(f"原生细胞类型对无法解析: {cell_pair}")
        source, target = cell_pair.split("_", 1)
        for pair, score in sorted(scores[cell_pair].items()):
            ligand, receptor = parse_pair(pair)
            q = pvalues.get(cell_pair, {}).get(pair)
            rows.append(dict(sample=sample, source=source, target=target, ligand=ligand, receptor=receptor,
                             score=float(score), tested=pair in tested_pairs, supported=q is not None,
                             q_value="NA" if q is None else float(q)))
    return rows


def run(config_path: str, output_path: str) -> int:
    config_path = Path(config_path).resolve(); cfg = json.loads(config_path.read_text()); base = config_path.parent
    for key in ("dataset", "research_question", "input", "native_root", "lr_resource", "celltype_label",
                "sample_label", "input_provenance", "normalization_definition"):
        if cfg.get(key) in (None, "", []):
            raise ValueError("CellAgentChat配置缺少: " + key)
    paths = {key: resolve(base, cfg[key]) for key in ("input", "native_root", "lr_resource")}
    if any(not value.exists() for value in paths.values()):
        raise FileNotFoundError("CellAgentChat输入、LR资源或固定源码不存在")
    (load_db, CellModel, get_lr_interactions2, permutation_test, get_distribution,
     get_significant_lr_pairs, versions) = verify_source(paths["native_root"])
    seed = cfg.get("seed", 20260910)
    if type(seed) is not int:
        raise ValueError("seed必须为整数")
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(1)
    adata = ad.read_h5ad(paths["input"])
    celltype, sample_label = cfg["celltype_label"], cfg["sample_label"]
    if any(x not in adata.obs for x in (celltype, sample_label)) or adata.obs_names.has_duplicates or adata.var_names.has_duplicates:
        raise ValueError("CellAgentChat缺少细胞类型/样本标签或身份重复")
    if adata.obs[[celltype, sample_label]].isna().any().any():
        raise ValueError("CellAgentChat细胞类型或样本标签含缺失")
    adata.X = dense_expression(adata, cfg.get("expression_layer"))
    adata.obs["cell_type"] = adata.obs[celltype].astype(str)
    adata.obs["Batch"] = adata.obs[sample_label].astype(str)
    if any("_" in value for value in adata.obs["cell_type"].unique()):
        raise ValueError("CellAgentChat上游用下划线拼接群对身份；细胞类型标签不得含下划线")
    use_distance = bool(cfg.get("use_distance", False))
    coordinates = None
    if use_distance:
        key = cfg.get("coordinate_key", "spatial")
        if key not in adata.obsm:
            raise ValueError("距离模式缺少真实空间坐标")
        coordinates = np.asarray(adata.obsm[key], dtype=float)
        if coordinates.shape not in ((adata.n_obs, 2), (adata.n_obs, 3)) or not np.isfinite(coordinates).all():
            raise ValueError("CellAgentChat空间坐标必须是逐细胞有限二维或三维坐标")
        if not cfg.get("coordinate_provenance") or cfg.get("coordinate_unit") not in ("um", "pixel", "native"):
            raise ValueError("距离模式必须声明坐标来源与单位")
        if cfg.get("coordinate_unit") == "native" and cfg.get("physical_scale_unavailable") is not True:
            raise ValueError("native坐标必须声明物理比例不可用")
        for index, axis in enumerate(("x_raw", "y_raw", "z_raw")[:coordinates.shape[1]]):
            adata.obs[axis] = coordinates[:, index]
        # Upstream silently disables distance when display-grid x/y are absent, even if
        # x_raw/y_raw exist. Supply its required 0..100 Mesa grid coordinates while
        # retaining unscaled raw coordinates for the actual distance calculation.
        for index, axis in enumerate(("x", "y")):
            values = coordinates[:, index]
            span = float(values.max() - values.min())
            adata.obs[axis] = 50.0 if span == 0 else (values - values.min()) / span * 100.0
    sep = cfg.get("lr_separator", "\t")
    ligands, receptors, pairs = load_db(adata, str(paths["lr_resource"]), sep)
    if len(pairs) < int(cfg.get("minimum_measured_lr", 2)):
        raise ValueError(f"CellAgentChat实测LR不足: {len(pairs)}")
    rate_mode = cfg.get("rate_mode", "provided")
    if rate_mode == "unit_base_abm":
        if cfg.get("acknowledge_unit_rates") is not True:
            raise ValueError("全1受体转化率仅用于基础ABM验收，必须显式确认")
        rates = {receptor: 1.0 for receptor in receptors}
        rate_source = "unit receptor conversion rates; base ABM only, not neural conversion-rate inference"
    elif rate_mode == "provided":
        rate_path = resolve(base, cfg.get("conversion_rate_file", ""))
        if not rate_path.is_file():
            raise ValueError("provided模式需要conversion_rate_file")
        rate_table = pd.read_csv(rate_path, sep="\t")
        if not {"receptor", "rate"} <= set(rate_table.columns) or rate_table.receptor.duplicated().any():
            raise ValueError("转化率表需要唯一receptor和rate列")
        mapping = dict(zip(rate_table.receptor.astype(str), rate_table.rate.astype(float)))
        missing = sorted(set(receptors) - set(mapping))
        if missing or not np.isfinite(list(mapping.values())).all() or any(mapping[x] < 0 for x in receptors):
            raise ValueError("转化率缺失、非有限或为负")
        rates = {receptor: mapping[receptor] for receptor in receptors}
        rate_source = cfg.get("conversion_rate_provenance")
        if not rate_source:
            raise ValueError("provided模式需要conversion_rate_provenance")
    else:
        raise ValueError("rate_mode仅支持provided或unit_base_abm")
    threshold = cfg.get("background_average_scores_threshold", 1000)
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        raise ValueError("背景平均分数阈值必须为正数")
    alpha = float(cfg.get("alpha", .05))
    if not 0 < alpha < 1:
        raise ValueError("alpha必须在0和1之间")
    tau, delta = float(cfg.get("tau", 2)), float(cfg.get("delta", 1))
    if tau <= 0 or delta <= 0:
        raise ValueError("tau和delta必须为正数")
    out = new_output(output_path); write_json(out / "run_config.json", cfg)
    with (out / "native_execution.log").open("x") as log, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            background, _, avg_distance = permutation_test(threshold, adata.n_obs, adata, ligands, receptors,
                rates, dist=use_distance, tau=tau, rec_block=False, seed=seed)
            distribution = get_distribution(background, dist=avg_distance, scaled=False)
            model = CellModel(adata.n_obs, adata, ligands, receptors, rates, max_steps=1, dist=use_distance,
                              delta=delta, tau=tau, rec_block=False, show_init_progress=False)
            if use_distance and model.dist_param == 0:
                raise ValueError("CellAgentChat上游静默关闭了距离模式")
            model.step(show_agent_progress=False)
            observed = get_lr_interactions2(model)
            significant, qvalues, significant_counts = get_significant_lr_pairs(observed, distribution, alpha)
    write_json(out / "native_warnings.json", [str(item.message) for item in caught])
    if not observed:
        raise ValueError("CellAgentChat原生ABM没有返回细胞类型对")
    tested_pairs = set(distribution)
    edge_rows = flatten(observed, qvalues, tested_pairs, cfg["dataset"])
    if not edge_rows:
        raise ValueError("CellAgentChat原生ABM没有返回LR分数")
    receiving = np.array([agent.num_r for agent in model.schedule.agents], dtype=float)
    if not np.isfinite(receiving).all() or (receiving < 0).any():
        raise ValueError("CellAgentChat接收分数无效")
    background_rows = [dict(row=pair, column=field, value=float(value)) for pair in sorted(distribution)
                       for field, value in zip(("gamma_shape", "gamma_location", "gamma_scale"), distribution[pair])]
    bundle = dict(schema_version=2, dataset=cfg["dataset"], method="CellAgentChat",
                  method_version="0.2.0 fixed source", implementation="native_base_abm_and_permutation_background",
                  tables=[], provenance=dict(input_provenance=cfg["input_provenance"],
                    normalization_definition=cfg["normalization_definition"], coordinate_provenance=cfg.get("coordinate_provenance"),
                    upstream=dict(url="https://github.com/mcgilldinglab/CellAgentChat", commit=COMMIT, license="MIT"),
                    source_hashes=SOURCE_HASHES, input_hashes={k: digest(v) for k, v in paths.items() if v.is_file()}, versions=versions,
                    parameters=dict(seed=seed, tau=tau, delta=delta, alpha=alpha, use_distance=use_distance,
                                    mesa_grid_coordinates="per-axis min-max to 0..100; raw coordinates retained for distance",
                                    background_average_scores_threshold=threshold, rate_mode=rate_mode),
                    receptor_conversion_rate_provenance=rate_source,
                    native_log=dict(path="native_execution.log", sha256=digest(out / "native_execution.log")),
                    limitations=[
                        "基础ABM按发送群平均配体、接收细胞受体表达、转化率和可选距离计算描述性分数。",
                        "unit_base_abm把所有实测受体转化率设为1，只能验收基础ABM，不能声称运行了神经网络conversion-rate模型。",
                        "原生置换打乱细胞类型并用经验分数拟合Gamma，再在全部可拟合候选上Bonferroni；细胞置换不替代供体层条件检验。",
                        "空间距离在每个样本内归一化；不同坐标尺度或切片的原始分数不可直接当共同绝对尺度。",
                        "单样本结果不证明疾病、治疗、时间或数据集特异性，也不证明分子结合或因果调控。",
                    ]))
    add_table(bundle, out, "cellagentchat_lr_scores", "lr_edges", edge_rows,
              "CellAgentChat原生一步ABM的群对LR分数；q_value为原生Gamma背景尾概率后全候选Bonferroni校正。",
              value_kind="nonnegative_strength", additive=True, directed=True, test_definition="native shuffled-cell-type Gamma tail and Bonferroni",
              figure_role="cellagentchat_lr", axis_label="Native ABM score")
    network = pd.DataFrame(edge_rows).groupby(["source", "target"], as_index=False).score.sum()
    add_table(bundle, out, "cellagentchat_total_network", "network",
              [dict(source=str(r.source), target=str(r.target), value=float(r.score)) for r in network.itertuples()],
              "原生群对LR分数求和；只在同一运行和同一参数内描述。", value_kind="nonnegative_strength",
              additive=True, directed=True, figure_role="cellagentchat_network", axis_label="Summed native ABM score")
    labels = sorted(set(adata.obs["cell_type"]))
    add_table(bundle, out, "cellagentchat_supported_count", "matrix",
              [dict(row=s, column=t, value=int(significant_counts.get(f"{s}_{t}", 0))) for s in labels for t in labels],
              "原生Gamma背景及Bonferroni阈值支持的LR数量；零结果完整保留。", value_kind="count", additive=True,
              row_order=labels, column_order=labels, figure_role="cellagentchat_supported", axis_label="Supported LR count")
    add_table(bundle, out, "cellagentchat_background_gamma", "matrix", background_rows,
              "每个可检验LR在原生置换分数上拟合并经上游固定shape/scale调整后的Gamma参数。",
              value_kind="native_parameter", additive=False, figure_role="cellagentchat_background", axis_label="Gamma parameter")
    complete_receiving = [dict(sample=str(sample), cell=str(cell), cell_type=str(cell_type), receiving_score=float(value))
                          for sample, cell, cell_type, value in zip(adata.obs["Batch"], adata.obs_names,
                                                                   adata.obs["cell_type"], receiving)]
    complete_receiving_path = out / "cellagentchat_receiving_scores_complete.tsv"
    write_table(complete_receiving_path, complete_receiving)
    bundle["provenance"]["complete_receiving_scores"] = {
        "path": complete_receiving_path.name, "sha256": digest(complete_receiving_path), "rows": len(complete_receiving)
    }
    receive_rows = []
    for cell_type in labels:
        values = receiving[adata.obs["cell_type"].to_numpy() == cell_type]
        for metric, value in (("mean", np.mean(values)), ("median", np.median(values)),
                              ("q25", np.quantile(values, .25)), ("q75", np.quantile(values, .75)),
                              ("maximum", np.max(values))):
            receive_rows.append(dict(row=str(cell_type), column=metric, value=float(value)))
    add_table(bundle, out, "cellagentchat_receiving_scores", "matrix", receive_rows,
              "每类细胞的原生一步ABM接收分数分布摘要；完整逐细胞值另存并记录摘要。不是接收概率。",
              value_kind="native_score", additive=False, row_order=labels,
              column_order=["mean", "median", "q25", "q75", "maximum"],
              figure_role="cellagentchat_receiving", axis_label="Cell receiving score")
    if coordinates is not None:
        add_table(bundle, out, "cellagentchat_spatial_receiving", "spatial_points",
                  [dict(sample=str(sample), cell=str(cell), x=float(coord[0]), y=float(coord[1]), value=float(value))
                   for sample, cell, coord, value in zip(adata.obs["Batch"], adata.obs_names, coordinates, receiving)],
                  "原始逐细胞坐标上的CellAgentChat原生接收分数；点位是真实输入坐标，分数为模型推断。",
                  coordinate_unit=cfg["coordinate_unit"], physical_scale_unavailable=cfg.get("physical_scale_unavailable", False),
                  y_down=bool(cfg.get("y_down", False)), value_kind="nonnegative_strength", additive=True,
                  figure_role="cellagentchat_spatial_receiving", axis_label="Cell receiving score")
    diagnostics = [
        dict(row="Measured LR pairs", column="count", value=len(pairs)),
        dict(row="Testable LR identities", column="count", value=len(tested_pairs)),
        dict(row="Observed group-pair LR rows", column="count", value=len(edge_rows)),
        dict(row="Supported rows", column="count", value=sum(row["supported"] for row in edge_rows)),
        dict(row="Background mean samples per LR", column="count", value=float(np.mean([len(x) for x in background.values()]))),
    ]
    add_table(bundle, out, "cellagentchat_diagnostics", "matrix", diagnostics,
              "候选覆盖、背景采样和支持数量诊断；background threshold控制每个LR跨群对累计分数样本的平均数，不等于置换次数。",
              value_kind="count", additive=True, figure_role="cellagentchat_diagnostics", axis_label="Count")
    write_json(out / "bundle.json", bundle)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); raise SystemExit(run(args.config, args.out))
