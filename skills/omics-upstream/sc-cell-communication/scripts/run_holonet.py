#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["torch==2.8.0", "numpy==2.2.6", "scipy==1.15.3", "pandas==2.3.3", "anndata==0.11.4", "scanpy==1.11.5", "scikit-learn==1.7.2", "networkx==3.4.2", "matplotlib==3.10.9", "seaborn==0.13.2", "umap-learn==0.5.12", "nvidia-ml-py==13.580.82"]
# ///
"""Run fixed HoloNet CE and target-specific FCE analysis on one spatial section."""
from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.spatial.distance import pdist, squareform
from scipy.stats import spearmanr
import torch

from communication_contract import add_table, digest, new_output, write_json, write_table


UPSTREAM_COMMIT = "920da6a9e63e51c8146da70264a4c0db2222310c"
UPSTREAM_VERSION = "0.1.dev215"
SOURCE_HASHES = {
    "LICENSE": "3491c00defad4da7199394fe9f4b8e1793d01f2e1d73dedaf707dcb258724212",
    "pyproject.toml": "d515e89dbcaef4a721d24c16ec4bd17831099ef28da492ad3340c552bdb414c9",
    "HoloNet/preprocessing/lr_database_preprocessing.py": "067cc925d44e7c0c4680676563bb3c29d9787d0584e80b0cc7510493f227916e",
    "HoloNet/tools/CE_network_edge_weighting.py": "05a34d125016774c5d398c9d0910ca84fcd052eeb00c865056994d8db431e5e9",
    "HoloNet/tools/CE_network_edge_filtering.py": "7d575c4a420d6183e695ec069c5d93cf622b86690ad11a81686fc99fe5c4d25c",
    "HoloNet/tools/CE_network_centrality.py": "8136064cf84cd62ed4458dbb7d2b61957ed899b3dff0445060b08bded540e70c",
    "HoloNet/tools/lr_clustering_based_on_CE_network.py": "e41c71cc84edc1c4c57761f1094f049b3bb1509a2c8cec10b5099a7d9666c28e",
    "HoloNet/tools/hyperparameter_selecting.py": "f1453409a756474550d476a88bbeeaa8fd283df3de99b4fdad20b09bd455174b",
    "HoloNet/predicting/input_preprocessing.py": "0da98e088a112dda7e544e2ed3da7b2434114772872fdc35e29dae2f8ef622a3",
    "HoloNet/predicting/target_preprocessing.py": "d1cc3ff2b38e0eb099b6ac5b3c4bb26b40662b86ee52a56cbd116050e1304627",
    "HoloNet/predicting/MGC_model.py": "8aeff26f84f15d75eabd407de4b0bb468bd288e38c5fc938a6976c9bb8a92a9d",
    "HoloNet/predicting/MGC_training.py": "192e8342f617c471caaed054d853d3c8898fba878a512e4748fa0f6fc23c2dde",
    "HoloNet/predicting/MGC_for_multi_target.py": "d84a72c6961f8972c2385948aa85d9897c0cc2d38bbc7be11ed0f2d5e6609dfa",
    "HoloNet/predicting/model_saving_loading.py": "d21ee39bbfb246152ce121dceb0c9677471abde92ee6d42ffe7cb02e1e1ba163",
    "HoloNet/plotting/CE_plotting.py": "a45c3f0dbcfe075eade21b4d7c0a81ff388ae56cf57dbf051728ef68fe50ff85",
    "HoloNet/plotting/base_plot.py": "015ddae3b1f5c5a3bfbf21f0a621bece3cb9d2db331b76bbcee1d207c8959564",
    "HoloNet/plotting/lr_clustering_plotting.py": "bdc96a91c7b0ab6300cc4af3f2d1e51df7f556e054f70d62bbdcbda9b3401283",
    "HoloNet/plotting/MGC_interpretation_plotting.py": "34cb14f171be492586c6d68979b64e2cf3009ae11575e9351286dfa05065b507",
    "HoloNet/plotting/MGC_performance_plotting.py": "65023a5738337a32eaa43913b0d0d8add89ec33d3e16b8649a8f837c71d51a4f",
    "HoloNet/plotting/MGC_for_multi_target_interpretation_plotting.py": "6e4ff80f3ac93c28b6d8b1735c86981f95bf0b606efdcc64fc9f4a21364ee321",
}
VERSIONS = {
    "torch": "2.8.0", "numpy": "2.2.6", "scipy": "1.15.3", "pandas": "2.3.3",
    "anndata": "0.11.4", "scanpy": "1.11.5", "scikit-learn": "1.7.2",
    "networkx": "3.4.2", "matplotlib": "3.10.9", "seaborn": "0.13.2",
    "umap-learn": "0.5.12", "nvidia-ml-py": "13.580.82",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def integer(cfg, key, default, minimum, maximum=None):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{key} 必须是不小于 {minimum}" + (f"且不超过 {maximum}" if maximum is not None else "") + " 的整数")
    return value


def finite(cfg, key, default, minimum=None, maximum=None):
    value = float(cfg.get(key, default))
    if not np.isfinite(value) or minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{key} 必须是有效有限数")
    return value


def verify_native(root: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"HoloNet 固定源码缺失或摘要不符: {relative}")
    versions = {}
    for package, expected in VERSIONS.items():
        actual = importlib.metadata.version(package)
        if actual != expected:
            raise ValueError(f"HoloNet 固定环境要求 {package}=={expected}，当前为 {actual}")
        versions[package] = actual
    sys.path.insert(0, str(root))
    import HoloNet as hn
    if hn.__version__ != UPSTREAM_VERSION:
        raise ValueError(f"HoloNet 源码版本标识应为 {UPSTREAM_VERSION}，当前为 {hn.__version__}")
    from HoloNet.preprocessing.lr_database_preprocessing import get_expressed_lr_df_connectomeDB
    from HoloNet.tools.CE_network_edge_weighting import compute_ce_tensor_connectomeDB, dist_factor_calculate
    from HoloNet.tools.CE_network_edge_filtering import filter_ce_tensor_connectomeDB
    from HoloNet.predicting.MGC_training import seed_torch, mgc_training, get_mgc_result
    return hn, get_expressed_lr_df_connectomeDB, compute_ce_tensor_connectomeDB, filter_ce_tensor_connectomeDB, dist_factor_calculate, seed_torch, mgc_training, get_mgc_result, versions


def dense(matrix):
    return matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)


def load_resource(path: Path, expected_sha: str):
    if not path.is_file() or digest(path) != expected_sha:
        raise ValueError("HoloNet LR 资源缺失或 SHA-256 不符")
    resource = pd.read_csv(path, sep="\t")
    required = ["interaction_id", "Ligand_gene_symbol", "Receptor_gene_symbol", "Ligand_location",
                "pathway_name", "annotation", "evidence"]
    if not set(required) <= set(resource.columns) or resource.empty:
        raise ValueError("pairwise LR 资源缺少必需列或为空")
    resource = resource[required].copy()
    if resource.isna().any().any() or any(resource[c].astype(str).str.strip().eq("").any() for c in required):
        raise ValueError("pairwise LR 资源不允许空值")
    if resource["interaction_id"].duplicated().any() or resource[["Ligand_gene_symbol", "Receptor_gene_symbol"]].duplicated().any():
        raise ValueError("pairwise LR 资源的 interaction_id 和基因对都必须唯一")
    if not set(resource["Ligand_location"]) <= {"secreted", "plasma membrane"}:
        raise ValueError("Ligand_location 只接受 secreted 或 plasma membrane")
    return resource


def prepare_input(cfg, base: Path):
    required = ("dataset", "research_question", "input", "native_root", "lr_resource", "lr_resource_sha256",
                "lr_resource_provenance", "input_provenance", "expression_layer", "expression_scale",
                "normalization_definition", "coordinate_unit", "coordinate_provenance", "w_best", "target_genes")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("HoloNet 配置缺少: " + key)
    if cfg["coordinate_unit"] not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if cfg["coordinate_unit"] == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
    input_path = resolve(base, cfg["input"])
    data = ad.read_h5ad(input_path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞和基因 ID 必须唯一")
    sample_key, cell_type_key = cfg.get("sample_key", "sample"), cfg.get("cell_type_key", "cell_type")
    for key in (sample_key, cell_type_key):
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
        data.obs[key] = data.obs[key].astype(str)
    samples = list(dict.fromkeys(data.obs[sample_key]))
    if len(samples) != 1:
        raise ValueError("HoloNet 原生 FCE 的随机细胞拆分不能消除跨切片依赖；每次只允许一个空间切片/样本")
    if data.obs[cell_type_key].nunique() < 3:
        raise ValueError("HoloNet FCE 至少需要3种可解释细胞类型")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("HoloNet 需要逐细胞/spot 对齐的有限二维坐标")
    if len(np.unique(coordinates, axis=0)) != data.n_obs:
        raise ValueError("空间坐标重复；必须先核查分割身份")
    maximum_cells = integer(cfg, "maximum_cells", 5000, 20)
    if data.n_obs > maximum_cells:
        raise ValueError("HoloNet 使用 LR×cell×cell 稠密张量，输入超过 maximum_cells")
    layer = cfg["expression_layer"]
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError("配置的表达层不存在")
    matrix = np.asarray(dense(matrix), dtype=float)
    if matrix.shape != data.shape or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("表达矩阵必须有限、非负并与 AnnData 对齐")
    scale = cfg["expression_scale"]
    if scale == "counts":
        if not np.allclose(matrix, np.rint(matrix), atol=1e-6):
            raise ValueError("expression_scale=counts 时必须是原始整数计数")
        if cfg.get("normalization_method") != "library_size_log1p":
            raise ValueError("counts 输入必须显式选择 normalization_method=library_size_log1p")
        data.X = sparse.csr_matrix(matrix.astype(np.float32))
        target_sum = finite(cfg, "normalization_target_sum", 10000.0, 1)
        sc.pp.normalize_total(data, target_sum=target_sum)
        sc.pp.log1p(data)
    elif scale in ("normalized", "log_normalized"):
        data.X = sparse.csr_matrix(matrix.astype(np.float32))
    else:
        raise ValueError("expression_scale 只接受 counts、normalized 或 log_normalized")
    normalized = np.asarray(dense(data.X), dtype=float)
    if not np.isfinite(normalized).all() or (normalized < 0).any() or not np.any(normalized > 0):
        raise ValueError("HoloNet 分析表达层归一化后无有效非负表达")
    data.obs["holonet_cell_type"] = data.obs[cell_type_key].astype(str)
    targets = cfg["target_genes"]
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets) or not all(isinstance(x, str) and x for x in targets):
        raise ValueError("target_genes 必须是唯一非空基因列表")
    if len(targets) > integer(cfg, "maximum_target_genes", 20, 1, 100):
        raise ValueError("target_genes 超过 maximum_target_genes")
    missing = sorted(set(targets) - set(data.var_names))
    if missing:
        raise ValueError("目标基因不在表达矩阵: " + ", ".join(missing))
    if any(np.count_nonzero(normalized[:, data.var_names.get_loc(g)]) < 10 for g in targets):
        raise ValueError("每个目标基因至少需要10个非零细胞/spot")
    return data, coordinates, sample_key, cell_type_key, targets, input_path


def safe_corr(left, right, indices=None):
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if indices is not None:
        left, right = left[indices], right[indices]
    if len(left) < 3 or np.std(left) == 0 or np.std(right) == 0:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    return value if np.isfinite(value) else None


def linkage_rows(model):
    counts = np.zeros(model.children_.shape[0])
    n = len(model.labels_)
    rows = []
    for i, merge in enumerate(model.children_):
        count = 0
        for child in merge:
            count += 1 if child < n else counts[child - n]
        counts[i] = count
        for column, value in (("left_child", merge[0]), ("right_child", merge[1]),
                              ("distance", model.distances_[i]), ("leaf_count", count)):
            rows.append(dict(row=str(i), column=column, value=float(value)))
    return rows


def network_rows(frame, extra=None):
    extra = extra or {}
    return [dict(source=str(source), target=str(target), value=float(frame.loc[source, target]), **extra)
            for source in frame.index for target in frame.columns]


def matrix_rows(frame, extra=None):
    extra = extra or {}
    return [dict(row=str(row), column=str(column), value=float(frame.loc[row, column]), **extra)
            for row in frame.index for column in frame.columns]


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    base = config.parent
    native_root = resolve(base, cfg.get("native_root", ""))
    (hn, native_lr_filter, compute_ce, filter_ce, dist_factor_calculate, seed_torch,
     mgc_training, get_mgc_result, versions) = verify_native(native_root)
    data, coordinates, sample_key, cell_type_key, target_genes, input_path = prepare_input(cfg, base)
    lr_path = resolve(base, cfg["lr_resource"])
    resource = load_resource(lr_path, cfg["lr_resource_sha256"])
    expressed_prop = finite(cfg, "expressed_proportion", 0.05, 0, 1)
    used_lr = native_lr_filter(resource.copy(), data, expressed_proportion=expressed_prop).copy()
    if len(used_lr) < 2 or used_lr["LR_Pair"].duplicated().any():
        raise ValueError("表达过滤后至少需要2个唯一 LR pair")
    lr_genes = set(used_lr["Ligand_gene_symbol"]) | set(used_lr["Receptor_gene_symbol"])
    overlap = sorted(lr_genes & set(target_genes))
    if overlap:
        raise ValueError("目标基因不能同时作为已用配体/受体，以避免直接信息泄漏: " + ", ".join(overlap))
    maximum_lr = integer(cfg, "maximum_lr_pairs", 200, 2, 2000)
    if len(used_lr) > maximum_lr:
        raise ValueError("表达通过的 LR 数超过 maximum_lr_pairs；需预先定义资源或阈值，不能按结果静默截断")
    tensor_elements = len(used_lr) * data.n_obs * data.n_obs
    if tensor_elements > integer(cfg, "maximum_tensor_elements", 100_000_000, 1):
        raise ValueError("LR×cell×cell 张量超过 maximum_tensor_elements")
    w_best = finite(cfg, "w_best", 0, np.finfo(float).eps)
    distinguish = cfg.get("distinguish_ligand_range", True)
    if type(distinguish) is not bool:
        raise ValueError("distinguish_ligand_range 必须是 JSON 布尔值")
    distances = squareform(pdist(coordinates))
    local_threshold = float(distances[distances > 0].min() * 1.05)
    local_mask = (distances > 0) & (distances < local_threshold)
    local_cell_fraction = float(local_mask.any(axis=1).mean())
    if distinguish and local_cell_fraction < finite(cfg, "minimum_local_cell_fraction", 0.5, 0, 1):
        raise ValueError("HoloNet 的接触信号使用全局最短距离定义邻接；当前不规则坐标覆盖细胞过少，请核实单位或显式关闭距离分类")
    n_pairs = integer(cfg, "background_pairs", 50, 10, 500)
    if data.n_vars - 2 < 2 * n_pairs:
        raise ValueError("背景基因不足以形成 HoloNet 要求的两组 n_pairs；请降低 background_pairs 并记录敏感性")
    filter_threshold = finite(cfg, "filter_threshold", 0.1, 0, 1)
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("exploratory", "publication"):
        raise ValueError("analysis_tier 只接受 exploratory 或 publication")
    repeats = integer(cfg, "repeat_num", 50 if tier == "publication" else 5, 1, 200)
    epochs = integer(cfg, "max_epoch", 300 if tier == "publication" else 100, 10, 3000)
    if tier == "publication" and (repeats < 50 or epochs < 300):
        raise ValueError("publication 层按作者教程至少需要50次初始化和300个 epoch")
    train_ratio = finite(cfg, "train_set_ratio", 0.6, 0.1, 0.8)
    val_ratio = finite(cfg, "val_set_ratio", 0.2, 0.1, 0.4)
    if train_ratio + val_ratio >= 0.9:
        raise ValueError("训练+验证比例必须小于0.9，为独立细胞测试集保留至少10%")
    output_root = new_output(output)
    native_dir = output_root / "native_results"
    native_dir.mkdir()
    write_json(output_root / "run_config.json", cfg)
    signature = digest(input_path) + ":" + digest(lr_path) + ":" + digest(config) + ":" + UPSTREAM_COMMIT
    state = {"status": "running", "signature": signature, "completed_targets": []}
    write_json(output_root / "run_state.json", state)
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        ce_tensor = compute_ce(data, used_lr, w_best, distinguish=distinguish)
        filtered_ce = filter_ce(ce_tensor, data, used_lr, w_best, n_pairs=n_pairs,
                                thres=filter_threshold, distinguish=distinguish, copy=True)
        degree_total = hn.tl.compute_ce_network_degree_centrality(filtered_ce, "sender_receiver")
        degree_sender = hn.tl.compute_ce_network_degree_centrality(filtered_ce, "sender")
        degree_receiver = hn.tl.compute_ce_network_degree_centrality(filtered_ce, "receiver")
        eigen = hn.tl.compute_ce_network_eigenvector_centrality(
            filtered_ce, max_iter=integer(cfg, "eigen_max_iter", 500, 10, 10000),
            tol=finite(cfg, "eigen_tol", 0.01, 0, 1), diff_thres=finite(cfg, "eigen_diff_threshold", 0.01, 0, 1))
    native_log = capture.getvalue()
    (native_dir / "ce_stdout.log").write_text(native_log)
    for name, tensor in (("ce_tensor", ce_tensor), ("filtered_ce_tensor", filtered_ce),
                         ("degree_total", degree_total), ("degree_sender", degree_sender),
                         ("degree_receiver", degree_receiver), ("eigenvector", eigen)):
        if not torch.isfinite(tensor).all():
            raise ValueError(f"HoloNet 原生 {name} 含非有限值；不进行插补或替换")
    if int((filtered_ce > 0).sum()) == 0:
        raise ValueError("HoloNet 背景过滤后没有非零 CE 边")
    np.savez_compressed(native_dir / "ce_tensors.npz", ce=ce_tensor.numpy(), filtered_ce=filtered_ce.numpy(),
                        degree_total=degree_total.numpy(), degree_sender=degree_sender.numpy(),
                        degree_receiver=degree_receiver.numpy(), eigenvector=eigen.numpy())
    lr_totals = filtered_ce.sum((1, 2)).numpy()
    lr_nonzero = (filtered_ce > 0).sum((1, 2)).numpy()
    top_ce_count = integer(cfg, "top_ce_lr", 3, 1, min(20, len(used_lr)))
    top_ce_indices = sorted(range(len(used_lr)), key=lambda i: (-float(lr_totals[i]), str(used_lr.iloc[i].LR_Pair)))[:top_ce_count]
    X, cell_type_names = hn.pr.get_one_hot_cell_type_tensor(data, categorical_cell_type_col="holonet_cell_type")
    cell_type_names = [str(x) for x in cell_type_names]
    if X.shape != (data.n_obs, len(cell_type_names)) or not torch.allclose(X.sum(1), torch.ones(data.n_obs)):
        raise ValueError("HoloNet one-hot 细胞类型矩阵维度异常；二分类 LabelBinarizer 等情况不能静默继续")
    only_between = cfg.get("only_between_cell_type", True)
    if type(only_between) is not bool:
        raise ValueError("only_between_cell_type 必须是 JSON 布尔值")
    adj = hn.pr.adj_normalize(filtered_ce, X, only_between_cell_type=only_between)
    if not torch.isfinite(adj).all():
        raise ValueError("HoloNet 原生归一化邻接矩阵含非有限值")
    np.savez_compressed(native_dir / "mgc_inputs.npz", X=X.numpy(), adjacency=adj.numpy())
    n_clusters = integer(cfg, "lr_clusters", min(3, len(used_lr)), 2, min(8, len(used_lr)))
    clustered_lr, cluster_model = hn.tl.cluster_lr_based_on_ce(
        filtered_ce, data, used_lr.copy(), w_best=w_best, n_clusters=n_clusters,
        cluster_based="node_centrality_euclidean", centrality_measure="Eigenvector", cell_cci_centrality=eigen)
    import umap
    embedding = umap.UMAP(random_state=1).fit_transform(np.asarray(eigen))
    ranges = embedding.max(0) - embedding.min(0)
    embedding = (embedding - embedding.min(0)) / np.where(ranges == 0, 1, ranges)
    if not np.isfinite(embedding).all():
        raise ValueError("LR centrality UMAP 含非有限坐标")
    clustered_lr.to_csv(native_dir / "used_lr.tsv", sep="\t", index=False)
    centrality_rows = []
    for lr_i, lr in enumerate(used_lr["LR_Pair"]):
        for cell_i, cell in enumerate(data.obs_names):
            centrality_rows.append(dict(lr_pair=str(lr), cell=str(cell),
                degree_total=float(degree_total[lr_i, cell_i]), degree_sender=float(degree_sender[lr_i, cell_i]),
                degree_receiver=float(degree_receiver[lr_i, cell_i]), eigenvector=float(eigen[lr_i, cell_i])))
    write_table(native_dir / "ce_cell_centrality.tsv", centrality_rows)
    celltype_matrix_rows = []
    ce_networks = {}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        for lr in list(used_lr["LR_Pair"]) + ["all"]:
            frame = hn.pl.ce_cell_type_network_plot(filtered_ce, X, cell_type_names, used_lr,
                                                     plot_lr=lr, display=False)
            ce_networks[str(lr)] = frame
            celltype_matrix_rows.extend(matrix_rows(frame, {"lr_pair": str(lr)}))
    write_table(native_dir / "ce_cell_type_matrices.tsv", celltype_matrix_rows)
    # The HoloNet tutorial chooses the source spot with the largest total kernel mass.
    distance_factor = dist_factor_calculate(data, w_best=w_best).numpy()
    display_cell = int(np.argmax(distance_factor.sum(1)))
    # Native target preparation still checks Scanpy's HVG columns even for a declared list.
    sc.pp.highly_variable_genes(data, n_top_genes=min(data.n_vars, 2000), flavor="seurat", inplace=True)
    target_matrix, native_target_order = hn.pr.get_gene_expr(data, gene_list_on_interest=target_genes)
    if list(native_target_order) != target_genes or not torch.isfinite(target_matrix).all():
        raise ValueError("HoloNet 原生目标表达预处理改变顺序或产生非有限值")
    split_seed = integer(cfg, "split_seed", 100, 0)
    seed_torch(split_seed)
    train_mask, test_mask, val_mask = hn.pr.train_test_mask(data.n_obs, train_ratio, val_ratio)
    if min(map(len, (train_mask, val_mask, test_mask))) < 3 or set(train_mask) & set(val_mask) or set(train_mask) & set(test_mask) or set(val_mask) & set(test_mask):
        raise ValueError("HoloNet 训练/验证/测试拆分无效")
    membership = {i: "train" for i in train_mask} | {i: "validation" for i in val_mask} | {i: "test" for i in test_mask}
    write_table(native_dir / "cell_split.tsv", [dict(cell=str(cell), split=membership[i]) for i, cell in enumerate(data.obs_names)])
    learning_rate = finite(cfg, "learning_rate", 0.1, np.finfo(float).eps)
    weight_decay = finite(cfg, "weight_decay", 5e-4, 0)
    step_size = integer(cfg, "step_size", 10, 1)
    gamma = finite(cfg, "gamma", 0.9, np.finfo(float).eps, 1)
    models, baseline_models = {}, {}
    predictions, baseline_predictions = {}, {}
    log_rows, repeat_metrics, prediction_rows, native_performance_rows, heldout_rows = [], [], [], [], []
    attention_rows, attention_mean = {}, {}
    fce_networks, delta_frames, impact_frames = {}, {}, {}
    for target_i, target_gene in enumerate(target_genes):
        target = target_matrix[target_i].unsqueeze(1).to(torch.float32)
        target_models, target_baselines = [], []
        for repeat in range(repeats):
            for label, only_cell_type, storage in (("HoloNet CE + cell type", False, target_models),
                                                   ("Cell type only", True, target_baselines)):
                model, loss, test_mse, val_mse = mgc_training(
                    X, adj, target, train_mask, test_mask, val_mask, seed=repeat,
                    only_cell_type=only_cell_type, hidden_num=X.shape[1], max_epoch=epochs,
                    lr=learning_rate, weight_decay=weight_decay, step_size=step_size,
                    gamma=gamma, display=False, device="cpu")
                storage.append(model)
                loss_np, test_np, val_np = (x.detach().cpu().numpy() for x in (loss, test_mse, val_mse))
                best = int(np.argmin(val_np))
                repeat_metrics.append(dict(target=target_gene, model=label, repeat=repeat,
                    selected_epoch=best, validation_mse=float(val_np[best]), test_mse=float(test_np[best])))
                for epoch in range(epochs):
                    log_rows.append(dict(target=target_gene, model=label, repeat=repeat, epoch=epoch,
                        train_mse=float(loss_np[epoch]), validation_mse=float(val_np[epoch]), test_mse=float(test_np[epoch])))
            if (repeat + 1) % max(1, repeats // 10) == 0:
                print(f"HoloNet {target_gene}: {repeat + 1}/{repeats} repeated initializations", flush=True)
        models[target_gene], baseline_models[target_gene] = target_models, target_baselines
        prediction = get_mgc_result(target_models, X, adj, hide_repeat_tqdm=True).detach().numpy().ravel()
        baseline = get_mgc_result(target_baselines, X, adj, hide_repeat_tqdm=True).detach().numpy().ravel()
        observed = target.detach().numpy().ravel()
        predictions[target_gene], baseline_predictions[target_gene] = prediction, baseline
        native_holo, native_base = safe_corr(prediction, observed), safe_corr(baseline, observed)
        held_holo, held_base = safe_corr(prediction, observed, test_mask), safe_corr(baseline, observed, test_mask)
        if None in (native_holo, native_base, held_holo, held_base):
            raise ValueError(f"目标 {target_gene} 的预测相关因常数或非有限结果不可估")
        for column, value in (("Cell type only", native_base), ("HoloNet CE + cell type", native_holo),
                              ("Difference", native_holo - native_base)):
            native_performance_rows.append(dict(row=target_gene, column=column, value=float(value)))
        for column, value in (("Cell type only", held_base), ("HoloNet CE + cell type", held_holo),
                              ("Difference", held_holo - held_base)):
            heldout_rows.append(dict(row=target_gene, column=column, value=float(value)))
        for i, cell in enumerate(data.obs_names):
            prediction_rows.append(dict(cell=str(cell), target=target_gene, observed=float(observed[i]),
                holonet_prediction=float(prediction[i]), cell_type_only_prediction=float(baseline[i]), split=membership[i]))
        native_rank = hn.pl.lr_rank_in_mgc(target_models, used_lr, repeat_filter_num=0,
                                           repeat_attention_scale=True, display=False, plot_cluster=False)
        raw_attention = np.stack([np.abs(m.mgc.layer_attention.detach().numpy()) for m in target_models])
        spread = raw_attention.max(1) - raw_attention.min(1)
        if np.any(spread == 0):
            raise ValueError(f"目标 {target_gene} 有初始化的 LR attention 无方差，作者 min-max 结果不可估")
        scaled_attention = (raw_attention - raw_attention.min(1, keepdims=True)) / spread[:, None]
        calculated = scaled_attention.mean(0)
        native_values = native_rank.set_index("LR_Pair").loc[list(used_lr["LR_Pair"]), "MGC_layer_attention"].to_numpy()
        if not np.allclose(calculated, native_values, atol=1e-7):
            raise ValueError("独立 attention 摘要与 HoloNet 原生 lr_rank_in_mgc 不一致")
        attention_rows[target_gene] = [dict(row=str(lr), column=f"repeat {r + 1}", value=float(scaled_attention[r, i]))
                                       for i, lr in enumerate(used_lr["LR_Pair"]) for r in range(repeats)]
        attention_mean[target_gene] = dict(zip(map(str, used_lr["LR_Pair"]), map(float, calculated)))
        order = sorted(range(len(used_lr)), key=lambda i: (-calculated[i], str(used_lr.iloc[i].LR_Pair)))
        selected_fce = [str(used_lr.iloc[i].LR_Pair) for i in order[:integer(cfg, "top_fce_lr", 2, 1, min(10, len(used_lr)))]]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for lr in ["all", *selected_fce]:
                frame, impact = hn.pl.fce_cell_type_network_plot(target_models, used_lr, X, adj,
                    cell_type_names, plot_lr=lr, hide_repeat_tqdm=True, display=False)
                fce_networks[(target_gene, lr)] = frame
                impact_frames[(target_gene, lr)] = impact
            delta_frames[target_gene] = hn.pl.delta_e_proportion(target_models, X, adj, cell_type_names,
                                                                 display=False)
        state["completed_targets"].append(target_gene)
        write_json(output_root / "run_state.json", state)
    write_table(native_dir / "training_log.tsv", log_rows)
    write_table(native_dir / "repeat_metrics.tsv", repeat_metrics)
    write_table(native_dir / "target_predictions.tsv", prediction_rows)
    # Preserve the authors' model serializer and its exact state dictionaries.
    model_payload = models[target_genes[0]] if len(target_genes) == 1 else [models[g] for g in target_genes]
    baseline_payload = baseline_models[target_genes[0]] if len(target_genes) == 1 else [baseline_models[g] for g in target_genes]
    hn.pr.save_model_list(model_payload, "holonet", target_genes, model_save_folder=str(native_dir / "models"))
    hn.pr.save_model_list(baseline_payload, "cell_type_only", target_genes, model_save_folder=str(native_dir / "models"))
    attention_stability = []
    for target in target_genes:
        array = np.array([[r["value"] for r in attention_rows[target] if r["column"] == f"repeat {j + 1}"] for j in range(repeats)])
        pairwise = [float(spearmanr(array[i], array[j]).statistic) for i in range(repeats) for j in range(i + 1, repeats)]
        for column, value in (("Median repeat Spearman", np.median(pairwise)),
                              ("Minimum repeat Spearman", np.min(pairwise)),
                              ("Maximum repeat Spearman", np.max(pairwise))):
            attention_stability.append(dict(row=target, column=column, value=float(value)))
    primary_target = target_genes[0]
    single_view_repeats = integer(cfg, "single_view_repeats", 5, 1, 50)
    single_view_epochs = integer(cfg, "single_view_epochs", 100, 10, 1000)
    single_view = hn.pr.mgc_training_with_single_view(X, adj, target_matrix[0], device="cpu",
        repeat_num=single_view_repeats, train_set_ratio=train_ratio, val_set_ratio=val_ratio,
        hidden_num=X.shape[1], max_epoch=single_view_epochs, lr=learning_rate,
        weight_decay=weight_decay, step_size=step_size, gamma=gamma)
    if not np.isfinite(single_view).all():
        raise ValueError("HoloNet 单视图 LR 预测相关含非有限值")
    single_view_rows = [dict(row=str(lr), column="Whole-data Pearson correlation", value=float(value))
                        for lr, value in zip(used_lr["LR_Pair"], single_view)]
    pathway_tables = []
    for pathway in cfg.get("pathways", []):
        pathway_lrs = [str(r.LR_Pair) for r in used_lr.itertuples() if pathway in str(r.pathway_name).split("|")]
        if not pathway_lrs:
            raise ValueError(f"预声明 pathway {pathway} 没有通过表达过滤的 LR")
        totals, lr_target, sources = [], [], []
        for target in target_genes:
            totals.append(dict(row=target, column=pathway, value=float(sum(attention_mean[target][lr] for lr in pathway_lrs))))
            for lr in pathway_lrs:
                lr_target.append(dict(row=target, column=lr, value=float(attention_mean[target][lr])))
            weighted = []
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                for lr in pathway_lrs:
                    frame, _ = hn.pl.fce_cell_type_network_plot(models[target], used_lr, X, adj,
                        cell_type_names, plot_lr=lr, hide_repeat_tqdm=True, display=False)
                    weighted.append(frame.sum(1) * attention_mean[target][lr])
            average = pd.concat(weighted, axis=1).mean(1)
            for cell_type, value in average.items():
                sources.append(dict(row=target, column=str(cell_type), value=float(value)))
        pathway_tables.append((pathway, totals, lr_target, sources))
    # Raw CE cell edges are kept as a compressed native tensor; selected LR edges are also tabular and drawable.
    bundle = {
        "schema_version": 2, "dataset": cfg["dataset"], "method": "HoloNet",
        "method_version": UPSTREAM_VERSION, "implementation": "native",
        "figure_inapplicability": {
            "lr_evidence": "HoloNet CE/FCE scores and permutation-like edge filtering do not return LR hypothesis P/q values.",
            "cellchat_patterns": "LR centrality clusters are agglomerative clusters, not CellChat NMF communication patterns.",
            "pathway_sankey": "HoloNet attention and independently normalized networks are not conserved flow.",
            "ligand_response": "Target prediction improvement is an association under a cell-level split, not a perturbational ligand-response test.",
            "intracellular": "The MGC predicts target expression but does not identify a receptor-TF-target causal chain.",
            "enrichment": "No enrichment test is performed by this runner.",
            "spatial_direction": "The Gaussian CE kernel does not estimate a physical vector field.",
            "relay_dynamic": "No time, velocity or multi-hop relay model is fit.",
            "special_molecules": "Only single-gene pairs in the supplied resource are modeled.",
            "functional_clinical": "No donor-level phenotype or clinical association is inferred."
        },
        "provenance": {
            "input_sha256": digest(input_path), "lr_resource_sha256": digest(lr_path),
            "input_provenance": cfg["input_provenance"], "lr_resource_provenance": cfg["lr_resource_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"], "parameters": cfg,
            "upstream": {"url": "https://github.com/lhc17/HoloNet", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "license": "MIT"},
            "source_sha256": SOURCE_HASHES, "versions": versions,
            "native_artifacts": "native_results/native_artifacts.json",
            "statistical_semantics": {
                "ce": "Each single-gene LR view is ligand expression × Gaussian distance factor × receptor expression, normalized by its view mean before background edge filtering.",
                "fce": "The MGC symmetrizes CE adjacency, optionally removes same-cell-type edges, and predicts scaled target expression from cell type plus attention-weighted LR graph views.",
                "validation": "The author-style repeated fits reuse one random cell-level train/validation/test split; repeats vary model initialization, not donors or sections.",
                "attention": "Absolute LR attention is independently min-max scaled within each repeated fit before averaging; it is a relative model-interpretation score.",
                "cell_type_network": "Each CE/FCE cell-type matrix is min-max normalized independently by the upstream plotting function and cannot be compared as an absolute cross-LR or cross-dataset effect."
            },
            "limitations": [
                "This adapter executes HoloNet's pairwise Connectome-style branch. It does not claim multisubunit complexes, agonists, antagonists or co-receptors.",
                "The fixed upstream full CellChat branch can produce NaN when a cofactor named in the resource is absent from a targeted panel; the adapter fails rather than imputes it.",
                "The native edge filter is expression-matched but does not expose edge-wise P values or multiple-testing-adjusted q values.",
                "Random cell splits do not remove spatial autocorrelation or establish biological replication; target prediction and attention cannot establish causality.",
                "All CE/FCE results depend on expression normalization, w_best, LR resource coverage and measured genes; absence is not evidence of no communication.",
                "One spatial section is allowed per run. Cross-condition conclusions require independently replicated sections and a separate predeclared comparison."
            ]
        }, "tables": []
    }
    sample = str(data.obs[sample_key].iloc[0])
    distance_rows = [dict(sample=sample, cell=str(cell), x=float(coordinates[i, 0]), y=float(coordinates[i, 1]),
                          value=float(distance_factor[display_cell, i]), anchor_cell=str(data.obs_names[display_cell]))
                     for i, cell in enumerate(data.obs_names)]
    spatial_meta = dict(coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                        physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    add_table(bundle, output_root, "holonet_distance_kernel", "spatial_points", distance_rows,
              "HoloNet Gaussian distance factor around the cell with the greatest total kernel mass; this visualizes the declared w_best rather than a fitted biological diffusion distance.",
              value_kind="nonnegative_strength", axis_label="Gaussian distance factor", title="HoloNet ligand coverage kernel", **spatial_meta)
    eligibility = []
    for i, row in used_lr.reset_index(drop=True).iterrows():
        lr = str(row.LR_Pair)
        ligand = np.asarray(dense(data[:, row.Ligand_gene_symbol].X)).ravel()
        receptor = np.asarray(dense(data[:, row.Receptor_gene_symbol].X)).ravel()
        for column, value in (("Ligand detected fraction", np.mean(ligand > 0)),
                              ("Receptor detected fraction", np.mean(receptor > 0)),
                              ("Filtered nonzero cell edges", lr_nonzero[i]), ("Filtered CE total", lr_totals[i])):
            eligibility.append(dict(row=lr, column=column, value=float(value), ligand=str(row.Ligand_gene_symbol),
                receptor=str(row.Receptor_gene_symbol), pathway=str(row.pathway_name), cluster=int(clustered_lr.iloc[i].cluster)))
    add_table(bundle, output_root, "holonet_lr_qc", "matrix", eligibility,
              "All expression-eligible pairwise LR views with measured ligand/receptor fractions, retained nonzero cell edges and filtered CE total; scales differ and are shown for QC, not joint biological ranking.",
              value_kind="nonnegative_strength", figure_role="holonet_lr_qc", axis_label="Native/QC value",
              display_top_rows=min(20, len(used_lr)), title="HoloNet LR eligibility and CE QC")
    for order, lr_i in enumerate(top_ce_indices, 1):
        lr = str(used_lr.iloc[lr_i].LR_Pair)
        for role, tensor in (("total", degree_total), ("sender", degree_sender),
                             ("receiver", degree_receiver), ("eigenvector", eigen)):
            points = [dict(sample=sample, cell=str(cell), x=float(coordinates[i, 0]), y=float(coordinates[i, 1]),
                           value=float(tensor[lr_i, i]), lr_pair=lr, centrality=role)
                      for i, cell in enumerate(data.obs_names)]
            add_table(bundle, output_root, f"holonet_ce_{order}_{role}_hotspot", "spatial_points", points,
                      f"HoloNet {lr} filtered CE network {role} centrality at each measured cell/spot; values are native graph summaries without P/q.",
                      value_kind="nonnegative_strength", axis_label=f"{role} centrality", title=f"{lr}: {role} CE hotspot", **spatial_meta)
        frame = ce_networks[lr]
        add_table(bundle, output_root, f"holonet_ce_{order}_celltype_network", "network", network_rows(frame),
                  f"HoloNet {lr} cell-type CE matrix after the upstream per-matrix min-max normalization and diagonal removal; only relative edges within this matrix are interpretable.",
                  value_kind="nonnegative_strength", additive=True, directed=True,
                  axis_label="Within-network relative CE", title=f"{lr}: cell-type CE network")
        edge_rows = []
        array = filtered_ce[lr_i].numpy()
        receivers, senders = np.nonzero(array)
        for receiver, sender in zip(receivers, senders):
            edge_rows.append(dict(sample=sample, source_cell=str(data.obs_names[sender]),
                                  target_cell=str(data.obs_names[receiver]), value=float(array[receiver, sender]), lr_pair=lr))
        add_table(bundle, output_root, f"holonet_ce_{order}_cell_edges", "spatial_edges", edge_rows,
                  f"All nonzero HoloNet filtered cell-level edges for {lr}; tensor axis is receiver×sender, converted here to source→target.",
                  value_kind="nonnegative_strength", directed=True, title=f"{lr}: strongest spatial CE edges", **spatial_meta)
    add_table(bundle, output_root, "holonet_ce_all_celltype_network", "network", network_rows(ce_networks["all"]),
              "HoloNet cell-type CE matrix averaged over all retained LR views and independently min-max normalized by the upstream function; it is a visual summary, not an additive molecular total.",
              value_kind="nonnegative_strength", additive=True, directed=True,
              axis_label="Within-network relative CE", title="All retained LR views: cell-type CE network")
    embedding_rows = [dict(sample="LR centrality profiles", cell=str(row.LR_Pair), x=float(embedding[i, 0]), y=float(embedding[i, 1]),
                           label=f"cluster {int(clustered_lr.iloc[i].cluster) + 1}")
                      for i, row in used_lr.reset_index(drop=True).iterrows()]
    add_table(bundle, output_root, "holonet_lr_centrality_umap", "embedding_points", embedding_rows,
              "UMAP of complete LR eigenvector-centrality profiles, following the upstream random_state=1 embedding and min-max coordinate display; colors are native agglomerative clusters.",
              value_kind="category", embedding_method="UMAP", embedding_provenance="HoloNet LR eigenvector centrality; umap-learn 0.5.12; random_state=1",
              title="HoloNet LR centrality clusters")
    add_table(bundle, output_root, "holonet_lr_dendrogram", "matrix", linkage_rows(cluster_model),
              "Complete linkage representation of HoloNet agglomerative clustering on LR eigenvector-centrality profiles; leaf order and branch distances come from the fixed native model.",
              value_kind="nonnegative_strength", figure_role="holonet_dendrogram", leaf_labels=list(map(str, used_lr["LR_Pair"])),
              title="HoloNet LR centrality dendrogram", column_order=["left_child", "right_child", "distance", "leaf_count"])
    for cluster in sorted(clustered_lr["cluster"].unique()):
        indices = np.flatnonzero(clustered_lr["cluster"].to_numpy() == cluster)
        values = eigen[indices].sum(0).numpy()
        rows = [dict(sample=sample, cell=str(cell), x=float(coordinates[i, 0]), y=float(coordinates[i, 1]),
                     value=float(values[i]), cluster=int(cluster) + 1) for i, cell in enumerate(data.obs_names)]
        add_table(bundle, output_root, f"holonet_lr_cluster_{int(cluster) + 1}_hotspot", "spatial_points", rows,
                  f"Sum of native eigenvector centralities for every LR assigned to HoloNet agglomerative cluster {int(cluster) + 1}; no significance test is attached.",
                  value_kind="nonnegative_strength", axis_label="Cluster centrality sum",
                  title=f"LR cluster {int(cluster) + 1}: CE hotspot", **spatial_meta)
    # Mean trajectories are drawable; every repeat/epoch remains in native_results/training_log.tsv.
    log_frame = pd.DataFrame(log_rows)
    for target in target_genes:
        rows = []
        part = log_frame[log_frame.target == target]
        for (model, epoch), group in part.groupby(["model", "epoch"], sort=True):
            for metric in ("train_mse", "validation_mse", "test_mse"):
                rows.append(dict(row=str(epoch), column=f"{model}: {metric}", value=float(group[metric].mean()),
                                 repeat_sd=float(group[metric].std(ddof=1))))
        add_table(bundle, output_root, f"holonet_training_{target.lower()}", "matrix", rows,
                  f"Mean HoloNet native per-epoch MSE over {repeats} initializations for target {target}; SD is retained in source rows and complete repeat logs are in native_results/training_log.tsv.",
                  value_kind="nonnegative_strength", figure_role="convergence", axis_label="Mean MSE",
                  title=f"{target}: repeated-fit convergence")
    add_table(bundle, output_root, "holonet_native_target_performance", "matrix", native_performance_rows,
              "Author-style whole-section Pearson correlation between observed scaled target expression and the repeated-model mean prediction, with and without CE views; Difference is HoloNet minus cell-type-only and includes training cells.",
              value_kind="native_score", figure_role="holonet_performance", axis_label="Whole-section Pearson correlation",
              column_order=["Cell type only", "HoloNet CE + cell type", "Difference"], title="Target genes linked to CE")
    add_table(bundle, output_root, "holonet_heldout_target_performance", "matrix", heldout_rows,
              "Pearson correlation on the fixed cell-level test subset only, using the same repeated-model ensembles; negative differences are retained and spatial dependence remains.",
              value_kind="native_score", axis_label="Held-out-cell Pearson correlation",
              column_order=["Cell type only", "HoloNet CE + cell type", "Difference"], title="Held-out target prediction")
    add_table(bundle, output_root, "holonet_attention_stability", "matrix", attention_stability,
              "Pairwise Spearman stability of complete min-max-scaled absolute LR-attention vectors across repeated initializations for each target; negative values are retained.",
              value_kind="native_score", axis_label="Attention-vector Spearman",
              column_order=["Median repeat Spearman", "Minimum repeat Spearman", "Maximum repeat Spearman"], title="LR-attention initialization stability")
    for target_i, target in enumerate(target_genes, 1):
        add_table(bundle, output_root, f"holonet_{target.lower()}_lr_attention", "matrix", attention_rows[target],
                  f"Complete absolute LR attention for target {target}, independently min-max scaled within each of {repeats} native repeated fits exactly as HoloNet lr_rank_in_mgc; no P/q.",
                  value_kind="nonnegative_strength", figure_role="holonet_attention", axis_label="Scaled absolute attention",
                  display_top_rows=min(15, len(used_lr)), title=f"{target}: functional LR attention")
        for label, values, suffix in (("Observed scaled expression", target_matrix[target_i - 1].numpy(), "observed"),
                                      ("HoloNet mean prediction", predictions[target], "predicted")):
            rows = [dict(sample=sample, cell=str(cell), x=float(coordinates[i, 0]), y=float(coordinates[i, 1]), value=float(values[i]))
                    for i, cell in enumerate(data.obs_names)]
            add_table(bundle, output_root, f"holonet_{target.lower()}_{suffix}_spatial", "spatial_points", rows,
                      f"{label} for HoloNet target {target}; observed target is max-scaled by native preprocessing and prediction is the mean of repeated native models.",
                      value_kind="nonnegative_strength", axis_label=label, title=f"{target}: {label}", **spatial_meta)
        delta = delta_frames[target].set_index("cell_type")["delta_e_proportion"]
        add_table(bundle, output_root, f"holonet_{target.lower()}_delta_e", "matrix",
                  [dict(row=str(cell_type), column="ΔE / (|E0| + |ΔE|)", value=float(delta.loc[cell_type])) for cell_type in cell_type_names],
                  f"Native HoloNet delta_e_proportion for target {target}: absolute communication-associated contribution divided by baseline plus communication contribution in each cell type; model decomposition, not causal fraction.",
                  value_kind="nonnegative_strength", figure_role="centrality", axis_label="Native ΔE proportion",
                  title=f"{target}: cell types associated with FCE")
        target_order = sorted(attention_mean[target], key=lambda lr: (-attention_mean[target][lr], lr))
        selected = ["all", *target_order[:integer(cfg, "top_fce_lr", 2, 1, min(10, len(used_lr)))]]
        for network_i, lr in enumerate(selected, 1):
            frame = fce_networks[(target, lr)]
            name = "all LR" if lr == "all" else lr
            add_table(bundle, output_root, f"holonet_{target.lower()}_fce_network_{network_i}", "network", network_rows(frame),
                      f"Native HoloNet target-specific FCE cell-type matrix for {target}, view {name}; each repeated matrix and final average are min-max normalized by the upstream function, so only within-network relative edges are interpretable.",
                      value_kind="nonnegative_strength", additive=True, directed=True,
                      axis_label="Within-network relative FCE", title=f"{target} — {name}: FCE network")
    add_table(bundle, output_root, "holonet_single_view_performance", "matrix", single_view_rows,
              f"Native HoloNet single-view MGC whole-data Pearson correlation for target {primary_target}; each LR view is trained alone with {single_view_repeats} repeated initializations and {single_view_epochs} epochs. This includes training cells and is descriptive.",
              value_kind="native_score", figure_role="centrality", axis_label="Whole-data Pearson correlation",
              display_top_rows=min(20, len(used_lr)), title=f"{primary_target}: single-LR-view prediction")
    for pathway_i, (pathway, totals, lr_target, sources) in enumerate(pathway_tables, 1):
        add_table(bundle, output_root, f"holonet_pathway_{pathway_i}_target_attention", "matrix", totals,
                  f"For declared pathway {pathway}, sum of mean scaled absolute LR attention across its retained LR views for each target; attention is relative within repeated fits and not additive molecular flow.",
                  value_kind="nonnegative_strength", figure_role="centrality", axis_label="Summed relative attention", title=f"{pathway}: target association")
        add_table(bundle, output_root, f"holonet_pathway_{pathway_i}_lr_target", "matrix", lr_target,
                  f"HoloNet {pathway} retained LR attention by target gene; rows are targets and columns are LR views, preserving every retained pathway LR.",
                  value_kind="nonnegative_strength", axis_label="Mean scaled absolute attention", title=f"{pathway}: LR views by target")
        add_table(bundle, output_root, f"holonet_pathway_{pathway_i}_source_target", "matrix", sources,
                  f"HoloNet {pathway} source-cell-type association by target, reproducing the author pathway panel: mean LR-specific FCE source total weighted by that LR's mean scaled attention.",
                  value_kind="nonnegative_strength", axis_label="Attention-weighted relative FCE", title=f"{pathway}: source cell types by target")
    native_artifacts = {
        "signature": signature, "ce_tensors": "ce_tensors.npz", "mgc_inputs": "mgc_inputs.npz",
        "training_log": "training_log.tsv", "repeat_metrics": "repeat_metrics.tsv",
        "target_predictions": "target_predictions.tsv", "cell_split": "cell_split.tsv",
        "used_lr": "used_lr.tsv", "ce_cell_centrality": "ce_cell_centrality.tsv",
        "ce_cell_type_matrices": "ce_cell_type_matrices.tsv", "models": "models",
    }
    write_json(native_dir / "native_artifacts.json", native_artifacts)
    write_json(output_root / "bundle.json", bundle)
    state.update(status="complete", bundle_sha256=digest(output_root / "bundle.json"),
                 retained_lr_pairs=len(used_lr), filtered_nonzero_edges=int((filtered_ce > 0).sum()),
                 top_ce_lr=[str(used_lr.iloc[i].LR_Pair) for i in top_ce_indices])
    write_json(output_root / "run_state.json", state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.exit(run(args.config, args.out))
