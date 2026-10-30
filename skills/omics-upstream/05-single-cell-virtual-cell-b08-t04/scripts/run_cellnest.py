#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "scikit-learn==1.4.1.post1", "anndata==0.10.6", "h5py==3.10.0", "scanpy==1.9.8", "qnorm==0.8.1", "torch==1.13.1", "torch-geometric==2.5.2", "matplotlib==3.8.3", "altair==5.2.0", "networkx==3.2.1"]
# ///
"""Run fixed CellNEST GAT-DGI communication and two-hop relay analysis."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import gzip
import importlib.metadata
import json
import math
import os
from pathlib import Path
import pickle
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import types

sys.dont_write_bytecode = True

import anndata as ad
import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr

from communication_contract import add_table, digest, new_output, write_json
from cellnest_relay import relay_instances as enumerate_relays


UPSTREAM_COMMIT = "2fd4f875ec2916ce51f674342aec1f59596c79ed"
UPSTREAM_VERSION = "commit-2fd4f87"
SOURCE_HASHES = {
    "LICENSE": "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
    "data_preprocess_CellNEST.py": "d8a140495478c1ee87efe8e04122dec51c44c8c5814bacd6e7bd1d659f05386a",
    "run_CellNEST.py": "143608579ed032a16809ae1f2ffa487a79db90a3563372f27b537cdcd759acf9",
    "CCC_gat.py": "1bc873fc0584ff6b8e8af837848b601260a3e13f445b8e8c74fb814a967f255e",
    "GATv2Conv_CellNEST.py": "7ae03ef2cb5ba00bc16b631ac53c8bce1e2d3de780e6bd8facaacb1aa52cff49",
    "output_postprocess_CellNEST.py": "5b6fb644c1491b3e1198cf0c9e7097d8abfd1c2f4fc8e1d783b9fb5fdd600688",
    "extract_relay_cellnest.py": "4bd3757b3f73f26293ceed691866f8d7af590ec523d8a532ff44d163d83efb2e",
    "relay_confidence.py": "787ac6c43708dab949fff59c5d22e911b98b85577c6d1191ff2e1e16d831632a",
    "database/human_signaling_ppi.csv": "86e75885d8c5b262161fafebd38551306d4f0a13db7f25e283639613fe9df87b",
    "database/human_tf_target.csv": "ffe02b582ab9c773ced17ded2ce2e15516d550bf5ea09a7141cb3373055fa1b0",
    "database/mouse_signaling_ppi.csv": "661a009fe52e32445cb72a2e97e4ecaf024ba53fd9a0b46a9788ea148600050b",
    "database/mouse_tf_target.csv": "de844b4406b6fd4ce2b51e6b835255aa6534f279b0a52a15f8a4bf265c507c09",
}
PYTHON_VERSIONS = {
    "numpy": "1.26.4", "pandas": "2.2.1", "scipy": "1.12.0",
    "scikit-learn": "1.4.1.post1", "anndata": "0.10.6", "h5py": "3.10.0",
    "scanpy": "1.9.8", "qnorm": "0.8.1", "torch": "1.13.1",
    "torch-geometric": "2.5.2", "matplotlib": "3.8.3", "altair": "5.2.0",
    "networkx": "3.2.1",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def integer(value, name, low=1, high=None):
    if type(value) is not int or value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是不小于 {low}" + (f"且不超过 {high}" if high is not None else "") + " 的整数")
    return value


def finite(value, name, low=None, high=None):
    value = float(value)
    if not np.isfinite(value) or low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是有效有限数")
    return value


def safe_id(value):
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_") or "item"


def verify_native(source_root: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = source_root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"CellNEST 固定源码缺失或摘要不符: {relative}")
    commit = subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError(f"CellNEST 固定源码提交应为 {UPSTREAM_COMMIT}，当前为 {commit}")
    if sys.version_info[:2] != (3, 10):
        raise ValueError("CellNEST 固定环境需要 Python 3.10")
    observed = {}
    for package, expected in PYTHON_VERSIONS.items():
        actual = importlib.metadata.version(package)
        observed[package] = actual
        if actual != expected:
            raise ValueError(f"CellNEST 固定环境要求 {package}=={expected}，当前为 {actual}")
    try:
        import torch_sparse  # noqa: F401
    except ImportError:
        observed["torch-sparse"] = "not installed; audited dense Tensor edge-index compatibility branch"
    else:
        observed["torch-sparse"] = importlib.metadata.version("torch-sparse")
    return observed


def launch_native_train(source_root: Path, argv):
    """Load the exact upstream GAT while bypassing an unused SparseTensor-only import."""
    target = source_root / "GATv2Conv_CellNEST.py"
    code = target.read_text()
    needle = "from torch_sparse import SparseTensor, set_diag"
    if code.count(needle) != 1:
        raise RuntimeError("CellNEST torch_sparse compatibility point no longer matches fixed source")
    replacement = """try:\n    from torch_sparse import SparseTensor, set_diag\nexcept ImportError:\n    class SparseTensor:\n        pass\n    def set_diag(*args, **kwargs):\n        raise RuntimeError('SparseTensor execution is unavailable; dense Tensor edge-index path was required')"""
    module = types.ModuleType("GATv2Conv_CellNEST")
    module.__file__ = str(target)
    exec(compile(code.replace(needle, replacement), str(target), "exec"), module.__dict__)
    sys.modules[module.__name__] = module
    sys.path.insert(0, str(source_root))
    sys.argv = [str(source_root / "run_CellNEST.py"), *argv]
    runpy.run_path(str(source_root / "run_CellNEST.py"), run_name="__main__")


def analysis_parameters(cfg):
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("publication", "exploratory"):
        raise ValueError("analysis_tier 只接受 publication 或 exploratory")
    runs = integer(cfg.get("num_runs", 5), "num_runs", 1, 20)
    epochs = integer(cfg.get("num_epochs", 60000), "num_epochs", 500)
    hidden = integer(cfg.get("hidden", 512), "hidden", 8, 2048)
    top_percent = integer(cfg.get("top_percent", 20), "top_percent", 1, 99)
    seeds = cfg.get("seeds", list(range(1, runs + 1)))
    if not isinstance(seeds, list) or len(seeds) != runs or any(type(x) is not int for x in seeds) or len(set(seeds)) != runs:
        raise ValueError("seeds 必须给出与 num_runs 等长且互不重复的整数")
    if tier == "publication" and (runs < 5 or epochs < 60000 or top_percent != 20):
        raise ValueError("publication 模式至少需要5次独立种子、每次60000 epoch，并保留作者基准的top 20%选择")
    return tier, runs, epochs, hidden, top_percent, seeds


def prepare_input(cfg, base: Path, stage: Path):
    required = ("dataset", "research_question", "input", "input_provenance", "native_root", "lr_database",
                "lr_database_sha256", "lr_database_provenance", "expression_layer", "expression_scale",
                "normalization_definition", "coordinate_unit", "coordinate_provenance")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("CellNEST 配置缺少: " + key)
    input_path, database_path = resolve(base, cfg["input"]), resolve(base, cfg["lr_database"])
    if digest(database_path) != cfg["lr_database_sha256"]:
        raise ValueError("CellNEST LR 数据库 SHA-256 与配置不符")
    data = ad.read_h5ad(input_path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("CellNEST 需要唯一细胞和基因 ID")
    if data.n_obs < 20 or data.n_obs > integer(cfg.get("maximum_cells", 20000), "maximum_cells", 20):
        raise ValueError("CellNEST 输入细胞数不在允许范围")
    sample_key, cell_type_key = cfg.get("sample_key", "sample"), cfg.get("cell_type_key", "cell_type")
    for key in (sample_key, cell_type_key):
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"CellNEST 缺失或空 metadata: {key}")
    samples = list(dict.fromkeys(data.obs[sample_key].astype(str)))
    if len(samples) != 1:
        raise ValueError("CellNEST 当前原生入口一次只处理一个空间切片；多切片需分别训练后作供体层复现")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("CellNEST 当前入口需要逐细胞对齐的有限二维坐标")
    if len(np.unique(coordinates, axis=0)) != data.n_obs:
        raise ValueError("CellNEST 空间坐标重复；必须先核查分割身份")
    unit = cfg["coordinate_unit"]
    if unit not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if unit == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
    layer = cfg["expression_layer"]
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError("CellNEST 配置的表达层不存在")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != data.shape or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("CellNEST 表达矩阵必须有限、非负并与 AnnData 对齐")
    if cfg["expression_scale"] != "counts" or not np.allclose(matrix, np.rint(matrix), atol=1e-6):
        raise ValueError("CellNEST 固定原生预处理只接收未归一化的整数 counts")
    if np.any(matrix.sum(axis=1) <= 0):
        raise ValueError("CellNEST 原始计数含总量为0的细胞")
    genes = [str(x).upper() for x in data.var_names]
    if len(set(genes)) != len(genes):
        raise ValueError("基因转为 CellNEST 大写身份后不唯一")
    database = pd.read_csv(database_path)
    expected = {"Ligand", "Receptor", "Annotation", "Reference"}
    if not expected <= set(database.columns) or database[list(expected)].isna().any().any():
        raise ValueError("CellNEST LR 数据库必须包含完整 Ligand/Receptor/Annotation/Reference")
    database["Ligand"] = database["Ligand"].astype(str).str.upper()
    database["Receptor"] = database["Receptor"].astype(str).str.upper()
    overlap = database.loc[database.Ligand.isin(genes) & database.Receptor.isin(genes), ["Ligand", "Receptor"]].drop_duplicates()
    if len(overlap) < integer(cfg.get("minimum_overlapping_lr", 5), "minimum_overlapping_lr", 1):
        raise ValueError("CellNEST 数据中可用 LR 对不足")
    original_ids = list(map(str, data.obs_names))
    native_ids = [f"cellnest_cell_{i:07d}" for i in range(data.n_obs)]
    id_map = dict(zip(native_ids, original_ids))
    prepared = ad.AnnData(X=sparse.csr_matrix(np.rint(matrix).astype(np.float32)),
                          obs=data.obs.copy(), var=pd.DataFrame(index=genes), obsm={"spatial": coordinates.copy()})
    prepared.obs_names = native_ids
    prepared.obs_names.name = "cell"
    prepared_path = stage / "cellnest_input.h5ad"
    prepared.write_h5ad(prepared_path)
    identity_path = stage / "cell_identity_map.tsv"
    pd.DataFrame({"cellnest_cell": native_ids, "original_cell": original_ids}).to_csv(identity_path, sep="\t", index=False)
    celltype_path = stage / "cell_types.csv"
    pd.DataFrame({"Barcode": native_ids, "Type": data.obs[cell_type_key].astype(str).to_numpy()}).to_csv(celltype_path, index=False)
    display = pd.DataFrame({"X": coordinates[:, 0], "Y": coordinates[:, 1],
                            "cell_type": data.obs[cell_type_key].astype(str).to_numpy()}, index=original_ids)
    return data, input_path, database_path, prepared_path, identity_path, celltype_path, display, id_map, samples[0], len(overlap)


def native_environment(cfg):
    env = dict(os.environ)
    threads = str(integer(cfg.get("threads", 1), "threads", 1, 32))
    env.update({"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": threads, "OPENBLAS_NUM_THREADS": threads,
                "MKL_NUM_THREADS": threads, "VECLIB_MAXIMUM_THREADS": threads})
    return env


def execute(command, cwd: Path, log_path: Path, env, timeout):
    with log_path.open("w") as log:
        result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                env=env, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError(f"CellNEST 原生步骤退出码 {result.returncode}: {log_path.name}")


def load_graph(stage: Path, name: str):
    path = stage / "input_graph" / name / f"{name}_adjacency_records"
    with gzip.open(path, "rb") as stream:
        row_col, edge_weight, lig_rec, cells = pickle.load(stream)
    edges = np.asarray(row_col, dtype=int)
    weights = np.asarray(edge_weight, dtype=float)
    if edges.ndim != 2 or edges.shape[1] != 2 or weights.shape != (len(edges), 3) or len(lig_rec) != len(edges):
        raise ValueError("CellNEST 原生输入图维度不一致")
    if not np.isfinite(weights).all() or np.any(weights[:, :2] < 0):
        raise ValueError("CellNEST 原生输入图含无效边特征")
    if np.any(edges < 0) or np.any(edges >= cells):
        raise ValueError("CellNEST 原生输入图端点越界")
    return path, edges, weights, [tuple(map(str, x)) for x in lig_rec], int(cells)


def load_attention(stage: Path, model_name: str, run_id: int, graph_edges):
    path = stage / "embedding_data" / "cellnest" / f"{model_name}_r{run_id}_attention"
    with gzip.open(path, "rb") as stream:
        bundle = pickle.load(stream)
    if len(bundle) != 5:
        raise ValueError("CellNEST attention bundle 不含固定五个对象")
    indices = np.asarray(bundle[0], dtype=int)
    edge_count = len(graph_edges)
    if indices.shape[0] != 2 or indices.shape[1] < edge_count or not np.array_equal(indices[:, :edge_count].T, graph_edges):
        raise ValueError("CellNEST attention 与原生 LR 边顺序不一致")
    layer1 = np.asarray(bundle[3], dtype=float).reshape(-1)[:edge_count]
    layer2 = np.asarray(bundle[2], dtype=float).reshape(-1)[:edge_count]
    if not np.isfinite(layer1).all() or not np.isfinite(layer2).all():
        raise ValueError("CellNEST attention 含非有限值")
    return path, layer1, layer2


def run(config, output):
    config = Path(config).resolve(); base = config.parent
    cfg = json.loads(config.read_text())
    output_root = new_output(output)
    state = {"schema_version": 2, "status": "running", "config_sha256": digest(config)}
    write_json(output_root / "run_config.json", cfg); write_json(output_root / "run_state.json", state)
    source_root = resolve(base, cfg.get("native_root", ""))
    versions = verify_native(source_root)
    tier, num_runs, epochs, hidden, top_percent, seeds = analysis_parameters(cfg)
    env = native_environment(cfg)
    timeout = integer(cfg.get("timeout_seconds", 172800), "timeout_seconds", 60)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="cellnest_native_") as temp:
        stage = Path(temp)
        try:
            (data, input_path, database_path, prepared_path, identity_path, celltype_path, metadata,
             id_map, sample, overlapping_lr) = prepare_input(cfg, base, stage)
            name, model_name = "cellnest", "CellNEST_cellnest"
            threshold_gene_exp = finite(cfg.get("threshold_gene_exp", 98), "threshold_gene_exp", 0, 100)
            if not 0 < threshold_gene_exp < 100:
                raise ValueError("threshold_gene_exp 必须严格位于 0 和 100 之间")
            preprocess = [sys.executable, str(source_root / "data_preprocess_CellNEST.py"),
                          "--data_name", name, "--data_from", str(prepared_path), "--data_type", "anndata",
                          "--filter_min_cell", str(integer(cfg.get("filter_min_cell", 1), "filter_min_cell", 1)),
                          "--threshold_gene_exp", str(threshold_gene_exp),
                          "--distance_measure", "knn", "--k", str(integer(cfg.get("k_neighbors", 50), "k_neighbors", 2, data.n_obs)),
                          "--block_autocrine", "1", "--block_juxtacrine", "1" if cfg.get("block_juxtacrine", False) else "0",
                          "--database_path", str(database_path)]
            if cfg.get("juxtacrine_distance") is not None:
                preprocess += ["--juxtacrine_distance", str(finite(cfg["juxtacrine_distance"], "juxtacrine_distance", 0))]
            node_mode = cfg.get("node_feature_mode", "cell_identity")
            if node_mode == "cell_type":
                preprocess += ["--use_celltype", "1", "--celltype_path", str(celltype_path)]
            elif node_mode != "cell_identity":
                raise ValueError("node_feature_mode 只接受 cell_identity 或 cell_type")
            execute(preprocess, stage, stage / "preprocess.log", env, timeout)
            graph_path, graph_edges, graph_weights, graph_lr, graph_cells = load_graph(stage, name)
            if graph_cells != data.n_obs or len(graph_edges) < integer(cfg.get("minimum_graph_edges", 100), "minimum_graph_edges", 1):
                raise ValueError("CellNEST 原生预处理产生的节点或 LR 边不足")
            if len(graph_edges) > integer(cfg.get("maximum_graph_edges", 5_000_000), "maximum_graph_edges", 1):
                raise ValueError("CellNEST 原生图超过 maximum_graph_edges")
            if np.any(graph_edges[:, 0] == graph_edges[:, 1]):
                raise ValueError("CellNEST 当前固定分支要求无自环；上游 GAT 会删除 LR 自环特征后另加普通自环")
            node_features = ""
            if node_mode == "cell_type":
                node_features = str(stage / "input_graph" / name / f"{name}_cell_vs_feature")
            training_jobs = []
            for run_id, seed in enumerate(seeds, 1):
                train_args = ["--data_name", name, "--model_name", model_name, "--run_id", str(run_id),
                              "--num_epoch", str(epochs), "--hidden", str(hidden), "--manual_seed", "yes", "--seed", str(seed)]
                if node_features:
                    train_args += ["--node_feature_path", node_features]
                command = [sys.executable, str(Path(__file__).resolve()), "__native_train__", str(source_root), *train_args]
                training_jobs.append((command, stage / f"train_run_{run_id}.log"))
            parallel_runs = integer(cfg.get("parallel_runs", 1), "parallel_runs", 1, num_runs)
            # The fixed upstream checks then creates these shared directories without
            # exist_ok, which races when independent seeded runs start together.
            # Pre-creation changes no model input or output and makes parallel launch safe.
            (stage / "embedding_data" / name).mkdir(parents=True, exist_ok=True)
            (stage / "model" / name).mkdir(parents=True, exist_ok=True)
            with ThreadPoolExecutor(max_workers=parallel_runs) as pool:
                futures = [pool.submit(execute, command, stage, log_path, env, timeout)
                           for command, log_path in training_jobs]
                for future in futures:
                    future.result()
            attention = [load_attention(stage, model_name, run_id, graph_edges) for run_id in range(1, num_runs + 1)]
            postprocess = [sys.executable, str(source_root / "output_postprocess_CellNEST.py"),
                           "--data_name", name, "--model_name", model_name, "--total_runs", str(num_runs),
                           "--top_percent", str(top_percent), "--output_all", "1", "--integrate_layers", "1"]
            execute(postprocess, stage, stage / "postprocess.log", env, timeout)
            native_output = stage / "output" / name
            all_path = native_output / f"{model_name}_allCCC.csv"
            selected_path = native_output / f"{model_name}_top{top_percent}percent.csv"
            all_edges, selected = pd.read_csv(all_path), pd.read_csv(selected_path)
            columns = ["from_cell", "to_cell", "ligand", "receptor", "edge_rank", "component", "from_id", "to_id", "attention_score"]
            if list(all_edges.columns) != columns or list(selected.columns) != columns or len(all_edges) != len(graph_edges):
                raise ValueError("CellNEST 原生 postprocess 输出维度或字段不一致")
            if selected.empty:
                raise ValueError("CellNEST 原生 top-percent 文件没有可交付边；保留失败记录，不降低阈值凑结果")
            if not np.isfinite(all_edges[["edge_rank", "attention_score"]].to_numpy(float)).all():
                raise ValueError("CellNEST 原生 postprocess 输出含非有限值")
            if np.any((all_edges.attention_score < 0) | (all_edges.attention_score > 1)):
                raise ValueError("CellNEST 集成 attention score 不在 [0,1]")
            key_columns = ["from_cell", "to_cell", "ligand", "receptor"]
            all_keys = set(map(tuple, all_edges[key_columns].astype(str).to_numpy()))
            selected_keys = set(map(tuple, selected[key_columns].astype(str).to_numpy()))
            if len(all_keys) != len(all_edges) or not selected_keys <= all_keys:
                raise ValueError("CellNEST 原生结果存在重复边或 top 集合不是 allCCC 子集")
            maximum_relays = integer(cfg.get("maximum_relay_instances", 2_000_000), "maximum_relay_instances", 1)
            relay_counts, relays = enumerate_relays(selected.to_dict("records"), maximum_relays)
            relay_order = sorted(relay_counts, key=lambda x: (-relay_counts[x], x))
            confidence = None
            confidence_patterns = relay_order[:integer(cfg.get("maximum_confidence_patterns", 100), "maximum_confidence_patterns", 1, 1000)]
            organism = cfg.get("organism")
            if organism is not None and confidence_patterns:
                if organism not in ("human", "mouse"):
                    raise ValueError("organism 只接受 human 或 mouse")
                confidence_input = stage / "relay_patterns_for_confidence.csv"
                pd.DataFrame({"Relay Patterns": confidence_patterns}).to_csv(confidence_input, index=False)
                confidence_path = stage / "relay_confidence.csv"
                confidence_command = [sys.executable, str(source_root / "relay_confidence.py"), "--input_path", str(confidence_input),
                                      "--database_dir", str(source_root / "database"), "--organism", organism,
                                      "--output_path", str(confidence_path)]
                execute(confidence_command, stage, stage / "relay_confidence.log", env, timeout)
                confidence = pd.read_csv(confidence_path)
            native_dir = output_root / "native_results"
            native_dir.mkdir()
            for folder in ("input_graph", "metadata", "embedding_data", "model", "output"):
                shutil.copytree(stage / folder, native_dir / folder)
            for file in stage.glob("*.log"):
                shutil.copyfile(file, native_dir / file.name)
            shutil.copyfile(prepared_path, native_dir / prepared_path.name)
            shutil.copyfile(identity_path, native_dir / identity_path.name)
            shutil.copyfile(celltype_path, native_dir / celltype_path.name)
            if confidence is not None:
                shutil.copyfile(stage / "relay_patterns_for_confidence.csv", native_dir / "relay_patterns_for_confidence.csv")
                shutil.copyfile(stage / "relay_confidence.csv", native_dir / "relay_confidence.csv")
        except Exception:
            failed = output_root / "failed_native_results"
            if not failed.exists():
                shutil.copytree(stage, failed)
            raise
    coordinates = metadata[["X", "Y"]]
    cell_types = metadata.cell_type.to_dict()
    spatial_meta = dict(coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                        physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    bundle = {
        "schema_version": 2, "dataset": cfg["dataset"], "method": "CellNEST", "method_version": UPSTREAM_VERSION,
        "implementation": "Fixed upstream CellNEST two-layer GAT-DGI, multi-seed rank-product ensemble and explicit two-hop relay extraction",
        "research_question": cfg["research_question"],
        "figure_inapplicability": {
            "condition_effects": "One spatial section is trained and no donor-level condition contrast is estimated.",
            "cellchat_patterns": "CellNEST does not fit CellChat NMF communication patterns.",
            "pathway_sankey": "Attention-ranked LR edges and relay chains are not additive molecular flow shares.",
            "ligand_response": "No perturbational ligand-to-target activity model is fitted.",
            "factors": "The DGI embedding is not a tensor/MOFA/NMF factor decomposition.",
            "enrichment": "No gene-set over-representation test with a declared background is performed.",
            "spatial_direction": "Directed cell edges are estimated, but CellNEST does not fit a continuous vector field.",
            "special_molecules": "The fixed branch uses a gene ligand-receptor database and no metabolite or neurotransmitter-specific model.",
            "functional_clinical": "No donor-level functional or clinical association is estimated."
        },
        "provenance": {
            "input_sha256": digest(input_path), "input_provenance": cfg["input_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"], "parameters": cfg,
            "lr_database_sha256": digest(database_path), "lr_database_provenance": cfg["lr_database_provenance"],
            "upstream": {"url": "https://github.com/schwartzlab-methods/CellNEST", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "license": "GPL-3.0"},
            "source_sha256": SOURCE_HASHES, "python_versions": versions,
            "native_artifacts": "native_results/native_artifacts.json",
            "statistical_semantics": {
                "candidate_edge": "A directed nearby-cell LR relation whose ligand and receptor exceed the declared per-cell expression percentile after native quantile normalization.",
                "attention_score": "Across-seed and across-layer CellNEST score reconstructed by the fixed upstream rank-product postprocessing; it is scaled within this graph and is not a calibrated probability.",
                "selected_edge": f"The exact fixed-upstream top-{top_percent}% file. Because the author slice counts its header, its row count can be one below the nominal floor.",
                "relay": "A two-hop pattern i→j→k among selected edges, with k distinct from i and j; abundance counts graph instances, not independent donors.",
                "relay_confidence": "Optional fixed-upstream receptor-to-TF-to-next-ligand path score from bundled PPI and TF-target databases; it is prior support, not experimental validation."
            },
            "limitations": [
                "CellNEST attention is a stochastic model score scaled within each dataset; values cannot be directly compared across datasets.",
                "The native graph uses expression thresholding and a declared neighborhood rule, so different panels, normalization or distance choices change eligible molecules and edges.",
                "Current fixed upstream radius mode calls k-nearest-neighbor retrieval and does not enforce the requested radius; this adapter therefore exposes only an explicit k-nearest-neighbor branch.",
                "The upstream GAT removes all self loops and adds feature-averaged graph self loops, which breaks LR identity for autocrine edges; this adapter requires autocrine blocking.",
                "The optional upstream p-value and confidence-interval scripts in this commit contain executable defects and are not promoted into results; rank stability is reported instead.",
                "The upstream loss file is saved only when a new minimum checkpoint also saves model attention; trailing zero allocation is excluded, so each run's curve stops at its selected checkpoint rather than implying observations through the final epoch.",
                "A two-hop path is a recurrent graph motif and does not establish temporal order, receptor activation, transcriptional causality or secretion of the second ligand.",
                "One section cannot establish condition, disease, donor or dataset specificity."
            ]
        },
        "tables": []
    }
    cell_rows = [dict(sample=sample, cell=cell, x=float(coordinates.loc[cell, "X"]), y=float(coordinates.loc[cell, "Y"]),
                      value=None, label=str(cell_types[cell])) for cell in metadata.index]
    add_table(bundle, output_root, "cellnest_cell_types", "spatial_points", cell_rows,
              "All measured cells colored by supplied cell type; no inferred attention is used.", value_kind="category",
              title="CellNEST spatial cell contexts", **spatial_meta)
    qc_values = {
        "Measured cells": data.n_obs, "Measured genes": data.n_vars, "Database LR overlapping measured genes": overlapping_lr,
        "Active graph LR pairs": len(set(graph_lr)), "Candidate directed cell-LR edges": len(graph_edges),
        "Selected native top-percent edges": len(selected), "Two-hop relay instances": len(relays),
    }
    add_table(bundle, output_root, "cellnest_graph_qc", "matrix",
              [dict(row="Input graph", column=key, value=float(value)) for key, value in qc_values.items()],
              "Observed input, eligibility, selected-edge and relay counts from the fixed native workflow.",
              value_kind="count", figure_role="cellnest_graph_qc", row_order=["Input graph"], column_order=list(qc_values),
              title="CellNEST graph eligibility")
    all_edges = all_edges.copy(); selected = selected.copy()
    for frame in (all_edges, selected):
        frame["from_cell"] = frame.from_cell.astype(str); frame["to_cell"] = frame.to_cell.astype(str)
        frame["source_original"] = frame.from_cell.map(id_map); frame["target_original"] = frame.to_cell.map(id_map)
        if frame[["source_original", "target_original"]].isna().any().any():
            raise ValueError("CellNEST 输出含未知细胞身份")
        frame["source_type"] = frame.source_original.map(cell_types); frame["target_type"] = frame.target_original.map(cell_types)
    selected_rows = [dict(sample=sample, source_cell=row.source_original, target_cell=row.target_original,
                          value=float(row.attention_score), ligand=str(row.ligand), receptor=str(row.receptor),
                          edge_rank=int(row.edge_rank), source_type=str(row.source_type), target_type=str(row.target_type))
                     for row in selected.itertuples(index=False)]
    add_table(bundle, output_root, "cellnest_selected_cell_edges", "spatial_edges", selected_rows,
              f"All edges in the fixed-upstream top-{top_percent}% file, weighted by the multi-seed, two-layer integrated attention score.",
              value_kind="native_score", directed=True, title="CellNEST selected cell-level communication", **spatial_meta)
    incoming = selected.groupby("target_original", sort=False).attention_score.max()
    hotspot_rows = [dict(sample=sample, cell=cell, x=float(coordinates.loc[cell, "X"]), y=float(coordinates.loc[cell, "Y"]),
                         value=float(value)) for cell, value in incoming.items()]
    add_table(bundle, output_root, "cellnest_receiver_hotspots", "spatial_points", hotspot_rows,
              "Maximum incoming selected CellNEST attention score for each receiving cell; cells without selected incoming edges remain absent.",
              value_kind="native_score", figure_role="spatial_hotspot", axis_label="Maximum incoming integrated attention",
              title="CellNEST receiver hotspots", **spatial_meta)
    type_network = selected.groupby(["source_type", "target_type"], sort=False).attention_score.agg(["sum", "size"]).reset_index()
    add_table(bundle, output_root, "cellnest_celltype_network", "network",
              [dict(source=row.source_type, target=row.target_type, value=float(row.sum), selected_edge_count=int(row.size))
               for row in type_network.itertuples(index=False)],
              "Sum of within-run integrated CellNEST attention across selected cell-level LR edges for each supplied source-to-target cell-type pair.",
              value_kind="nonnegative_strength", additive=True, directed=True, axis_label="Selected attention sum", title="CellNEST cell-type context network")
    role_rows = []
    for cell_type in sorted(set(cell_types.values())):
        sent = selected.loc[selected.source_type == cell_type]; received = selected.loc[selected.target_type == cell_type]
        for column, value in (("Outgoing edge count", len(sent)), ("Incoming edge count", len(received)),
                              ("Outgoing attention sum", sent.attention_score.sum()), ("Incoming attention sum", received.attention_score.sum())):
            role_rows.append(dict(row=cell_type, column=column, value=float(value)))
    add_table(bundle, output_root, "cellnest_celltype_roles", "matrix", role_rows,
              "Selected outgoing and incoming CellNEST edge counts and integrated attention sums by supplied cell type.",
              value_kind="native_score", figure_role="cellnest_celltype_roles", title="CellNEST sender and receiver roles")
    lr_candidate = all_edges.groupby(["ligand", "receptor"], sort=False).attention_score.agg(candidate_edges="size", candidate_median="median")
    lr_selected = selected.groupby(["ligand", "receptor"], sort=False).attention_score.agg(selected_edges="size", selected_sum="sum", selected_median="median")
    lr_summary = lr_candidate.join(lr_selected, how="left").fillna({"selected_edges": 0, "selected_sum": 0})
    lr_columns = ["Candidate edge count", "Selected edge count", "Selected attention sum", "Selected median attention"]
    lr_rows = []
    for (ligand, receptor), row in lr_summary.iterrows():
        label = f"{ligand}–{receptor}"
        values = [row.candidate_edges, row.selected_edges, row.selected_sum,
                  None if pd.isna(row.selected_median) else row.selected_median]
        lr_rows.extend(dict(row=label, column=column, value=None if value is None else float(value)) for column, value in zip(lr_columns, values))
    add_table(bundle, output_root, "cellnest_lr_summary", "matrix", lr_rows,
              "Candidate and selected cell-edge abundance plus integrated attention summaries for every active ligand-receptor pair.",
              value_kind="native_score", figure_role="cellnest_lr_summary", column_order=lr_columns,
              title="CellNEST ligand-receptor evidence")
    top_lr = sorted(lr_selected.index, key=lambda key: (-lr_selected.loc[key, "selected_edges"], -lr_selected.loc[key, "selected_sum"], key))[:integer(cfg.get("top_lr_spatial", 3), "top_lr_spatial", 1, 10)]
    for ligand, receptor in top_lr:
        frame = selected.loc[(selected.ligand == ligand) & (selected.receptor == receptor)]
        rows = [dict(sample=sample, source_cell=row.source_original, target_cell=row.target_original,
                     value=float(row.attention_score), ligand=ligand, receptor=receptor, edge_rank=int(row.edge_rank))
                for row in frame.itertuples(index=False)]
        add_table(bundle, output_root, f"cellnest_{safe_id(ligand)}_{safe_id(receptor)}_edges", "spatial_edges", rows,
                  f"All selected cell edges for the abundant CellNEST pair {ligand}–{receptor}; selection occurred on the global graph.",
                  value_kind="native_score", directed=True, title=f"{ligand}–{receptor}: selected spatial edges", **spatial_meta)
    component_edge_count = integer(cfg.get("component_top_edges", min(300, len(selected))), "component_top_edges", 1, len(selected))
    component_graph = nx.Graph(); component_graph.add_edges_from(selected.sort_values("edge_rank").head(component_edge_count)[["source_original", "target_original"]].itertuples(index=False, name=None))
    components = sorted(nx.connected_components(component_graph), key=lambda group: (-len(group), sorted(group)[0]))
    component_map = {}
    for index, group in enumerate(components[:8], 1):
        for cell in group: component_map[cell] = f"Component {index} (n={len(group)})"
    for group in components[8:]:
        for cell in group: component_map[cell] = "Other communicating components"
    component_rows = [dict(sample=sample, cell=cell, x=float(coordinates.loc[cell, "X"]), y=float(coordinates.loc[cell, "Y"]), value=None,
                           label=component_map.get(cell, "No displayed top-edge component")) for cell in metadata.index]
    add_table(bundle, output_root, "cellnest_components", "spatial_points", component_rows,
              f"Connected components induced by the globally strongest {component_edge_count} selected edges; the largest eight are shown separately.",
              value_kind="category", title="CellNEST highly communicating spatial components", **spatial_meta)
    stability_rows = []
    for first in range(num_runs):
        for second in range(first + 1, num_runs):
            for layer, index in (("Layer 1", 1), ("Layer 2", 2)):
                value = float(spearmanr(attention[first][index], attention[second][index]).statistic)
                stability_rows.append(dict(row=f"run {first + 1} vs run {second + 1}", column=layer, value=value))
    if not stability_rows:
        stability_rows = [dict(row="single run", column="Layer 1", value=None), dict(row="single run", column="Layer 2", value=None)]
    add_table(bundle, output_root, "cellnest_attention_stability", "matrix", stability_rows,
              "Pairwise Spearman correlation of complete unnormalized native attention vectors across independent seeds, separately for both GAT layers.",
              value_kind="native_score", figure_role="cellnest_stability", column_order=["Layer 1", "Layer 2"],
              title="CellNEST attention stability")
    loss_rows = []
    checkpoint_epochs = list(range(0, epochs, 500))
    for run_id in range(1, num_runs + 1):
        loss = np.loadtxt(output_root / "native_results" / "model" / name / f"DGI_{model_name}_r{run_id}_loss_curve.csv", delimiter=",")
        loss = np.atleast_1d(loss)[:len(checkpoint_epochs)]
        observed = np.flatnonzero(loss > 0)
        if not len(observed) or np.any(loss[:observed[-1] + 1] <= 0):
            raise ValueError(f"CellNEST run {run_id} 的原生 best-checkpoint loss 记录为空或中间断裂")
        loss = loss[:observed[-1] + 1]
        for epoch, value in zip(checkpoint_epochs, loss):
            loss_rows.append(dict(row=str(epoch + 1), column=f"run {run_id}", value=float(value)))
    add_table(bundle, output_root, "cellnest_training_loss", "matrix", loss_rows,
              "Native DGI loss recorded every 500 epochs through the checkpoint at which that run's best model and attention were saved; upstream trailing zero allocation is excluded, with no smoothing or cross-run best selection.",
              value_kind="native_score", figure_role="cellnest_loss", title="CellNEST DGI training loss")
    distribution_rows = [dict(row=str(int(row.edge_rank)), column="Integrated attention", value=float(row.attention_score),
                              selected=tuple(map(str, (row.from_cell, row.to_cell, row.ligand, row.receptor))) in selected_keys)
                         for row in all_edges.itertuples(index=False)]
    add_table(bundle, output_root, "cellnest_attention_distribution", "matrix", distribution_rows,
              "Complete integrated attention distribution for all eligible cell-level LR edges; selected membership comes from the exact native top-percent file.",
              value_kind="native_score", figure_role="cellnest_attention_distribution", column_order=["Integrated attention"],
              title="CellNEST integrated attention distribution")
    relay_count_rows = [dict(row=pattern, column="Two-hop instances", value=float(relay_counts[pattern])) for pattern in relay_order]
    add_table(bundle, output_root, "cellnest_relay_counts", "matrix", relay_count_rows or [dict(row="No two-hop relay", column="Two-hop instances", value=None)],
              "Two-hop i→j→k instance counts for every LR-to-LR relay pattern among selected native CellNEST edges.",
              value_kind="count", figure_role="cellnest_relay_counts", column_order=["Two-hop instances"],
              title="CellNEST two-hop relay abundance")
    relay_top = relay_order[:integer(cfg.get("top_relay_patterns", 3), "top_relay_patterns", 1, 10)]
    for pattern in relay_top:
        matching = [(first, second) for current, first, second in relays if current == pattern]
        role_counts = {role: Counter() for role in ("Sender", "Intermediate", "Receiver")}
        relay_edge_rows = []
        for triplet_id, (first, second) in enumerate(matching, 1):
            cells = [id_map[str(first["from_cell"])], id_map[str(first["to_cell"])], id_map[str(second["to_cell"])]]
            for role, cell in zip(role_counts, cells): role_counts[role][cell_types[cell]] += 1
            relay_edge_rows.extend([
                dict(sample=sample, source_cell=cells[0], target_cell=cells[1], value=float(first["attention_score"]), relay_pattern=pattern, triplet=triplet_id, hop=1),
                dict(sample=sample, source_cell=cells[1], target_cell=cells[2], value=float(second["attention_score"]), relay_pattern=pattern, triplet=triplet_id, hop=2),
            ])
        role_rows = []
        all_types = sorted({key for values in role_counts.values() for key in values})
        for cell_type in all_types:
            for role in role_counts:
                role_rows.append(dict(row=cell_type, column=role, value=role_counts[role][cell_type] / len(matching)))
        ident = safe_id(pattern)
        add_table(bundle, output_root, f"cellnest_relay_{ident}_roles", "matrix", role_rows,
                  f"Supplied cell-type proportions at sender, intermediate and receiver positions across all {len(matching)} instances of relay {pattern}.",
                  value_kind="native_score", figure_role="cellnest_relay_roles", column_order=["Sender", "Intermediate", "Receiver"],
                  title=f"{pattern}: relay cell-type roles")
        add_table(bundle, output_root, f"cellnest_relay_{ident}_edges", "spatial_edges", relay_edge_rows,
                  f"Both directed hops for all {len(matching)} selected-edge instances of relay {pattern}; repeated edges remain repeated by triplet membership.",
                  value_kind="native_score", directed=True, title=f"{pattern}: spatial relay instances", **spatial_meta)
    if confidence is not None and len(confidence):
        confidence_rows = [dict(row=str(row.relay_pattern), column="Combined prior confidence",
                                value=None if pd.isna(row.combined_score) else float(row.combined_score),
                                tf=None if pd.isna(row.tf) else str(row.tf), path=str(row.path))
                           for row in confidence.itertuples(index=False)]
        add_table(bundle, output_root, "cellnest_relay_confidence", "matrix", confidence_rows,
                  "Fixed-upstream PPI×GRN confidence for top relay patterns; missing values mean no eligible receptor-to-TF-to-ligand path in the bundled priors.",
                  value_kind="native_score", figure_role="cellnest_relay_confidence", column_order=["Combined prior confidence"],
                  title="CellNEST relay prior support")
    native_artifacts = {
        "prepared_input": "cellnest_input.h5ad", "cell_identity_map": "cell_identity_map.tsv", "cell_types": "cell_types.csv",
        "input_graph": f"input_graph/{name}/{name}_adjacency_records", "model_name": model_name,
        "all_communication": f"output/{name}/{model_name}_allCCC.csv",
        "selected_communication": f"output/{name}/{model_name}_top{top_percent}percent.csv",
        "preprocess_command": preprocess, "postprocess_command": postprocess,
        "training": {"runs": num_runs, "epochs": epochs, "hidden": hidden, "seeds": seeds,
                     "node_feature_mode": node_mode, "parallel_processes": parallel_runs,
                     "loss_curve_semantics": "observed 500-epoch checkpoints through each run's saved minimum-loss attention checkpoint; trailing preallocated zeros excluded",
                     "dense_edge_index_compatibility": "torch_sparse optional SparseTensor import bypassed; Tensor path unchanged"},
        "graph": {"cells": graph_cells, "edges": len(graph_edges), "active_lr_pairs": len(set(graph_lr)), "overlapping_database_lr": overlapping_lr},
        "selection": {"top_percent": top_percent, "selected_edges": len(selected)},
        "relay": {"instances": len(relays), "patterns": len(relay_counts), "confidence_patterns": len(confidence_patterns) if confidence is not None else 0},
    }
    write_json(output_root / "native_results" / "native_artifacts.json", native_artifacts)
    write_json(output_root / "bundle.json", bundle)
    state.update(status="complete", bundle_sha256=digest(output_root / "bundle.json"), runtime_seconds=time.time() - started,
                 graph_edges=len(graph_edges), active_lr_pairs=len(set(graph_lr)), selected_edges=len(selected),
                 relay_instances=len(relays), relay_patterns=len(relay_counts), analysis_tier=tier)
    write_json(output_root / "run_state.json", state)
    return 0


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "__native_train__":
        launch_native_train(Path(sys.argv[2]).resolve(), sys.argv[3:])
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        return run(args.config, args.out)
    except Exception as error:
        out = Path(args.out).expanduser().resolve()
        if out.is_dir():
            state_path = out / "run_state.json"
            state = json.loads(state_path.read_text()) if state_path.is_file() else {"schema_version": 2}
            state.update(status="failed", error=str(error)); write_json(state_path, state)
        raise


if __name__ == "__main__":
    sys.exit(main())
