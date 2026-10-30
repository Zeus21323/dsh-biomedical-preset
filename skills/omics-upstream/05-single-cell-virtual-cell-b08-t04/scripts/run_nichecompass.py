#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["nichecompass==0.3.3", "torch==2.8.0", "torch-geometric==2.8.0.post1", "torch-scatter==2.1.2", "torch-sparse==0.6.18", "numpy==2.2.6", "scipy==1.15.3", "pandas==2.3.3", "anndata==0.11.4", "scanpy==1.11.5", "scikit-learn==1.7.2", "igraph==0.11.9", "leidenalg==0.10.2"]
# ///
"""Run fixed NicheCompass 0.3.3 gene-program spatial representation learning."""
from __future__ import annotations

import argparse
import copy
import contextlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import sys
import types

sys.dont_write_bytecode = True
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score
from sklearn.neighbors import NearestNeighbors

from communication_contract import add_table, digest, new_output, write_json, write_table


UPSTREAM_COMMIT = "5bf7d2a09e70bd490c59e978e37f4df30f812994"
UPSTREAM_VERSION = "0.3.3"
SOURCE_HASHES = {
    "LICENSE": "916041bbfed704086a5cf3aecb7ea030e4c20615e38a60f394c301050aa271ae",
    "src/nichecompass/models/nichecompass.py": "e83f4b96d8b24ab4cecdaa3badd7bf66da8f6c6e7223fd6221622cd354dcfb0a",
    "src/nichecompass/modules/vgpgae.py": "2adc7aa210686a8b7a2a40fdcd9e02512845185116dadfdc7f72a38a017b2771",
    "src/nichecompass/train/trainer.py": "b62a46ad69535a7fd52e8287aa8a8d64b278be2e6a9c3b6aef975df7749aff14",
    "src/nichecompass/utils/gene_programs.py": "664091ca977e08e964ab231a879b78005f7539cd75bf0356545c6f006b5a3aaf",
    "src/nichecompass/utils/analysis.py": "428a848ba64e56297f261b7ae7e6329c42252ff3879e530e970bc742c9e1bbd5",
    "src/nichecompass/data/dataprocessors.py": "f444029af1884fe7ea651d5ffee881a695df32134d3c8612813eb533bb4e63ec",
}
VERSIONS = {
    "nichecompass": "0.3.3", "torch": "2.8.0", "torch-geometric": "2.8.0.post1",
    "torch-scatter": "2.1.2", "torch-sparse": "0.6.18", "numpy": "2.2.6",
    "scipy": "1.15.3", "pandas": "2.3.3", "anndata": "0.11.4",
    "scanpy": "1.11.5", "scikit-learn": "1.7.2", "igraph": "0.11.9",
    "leidenalg": "0.10.2",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def integer(cfg, key, default, minimum, maximum=None):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{key} 必须是不小于 {minimum}" + (f"且不超过 {maximum}" if maximum else "") + " 的整数")
    return value


def finite_number(cfg, key, default, minimum=None):
    value = float(cfg.get(key, default))
    if not np.isfinite(value) or minimum is not None and value < minimum:
        raise ValueError(f"{key} 必须是有限数" + (f"且不小于 {minimum}" if minimum is not None else ""))
    return value


def verify_native(root: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"NicheCompass 固定源码缺失或摘要不符: {relative}")
    versions = {}
    for package, expected in VERSIONS.items():
        actual = importlib.metadata.version(package)
        if actual != expected:
            raise ValueError(f"NicheCompass 固定环境要求 {package}=={expected}，当前为 {actual}")
        versions[package] = actual
    # NicheCompass imports OmniPath at module import time. This runner requires
    # a checksummed, explicit GP resource and never calls the download helpers.
    # A placeholder prevents an undeclared network request without replacing
    # any model, training, GP-mask or communication-network implementation.
    sys.modules.setdefault("omnipath", types.ModuleType("omnipath"))
    from nichecompass.models import NicheCompass
    from nichecompass.utils.gene_programs import add_gps_from_gp_dict_to_adata
    from nichecompass.utils.analysis import compute_communication_gp_network, aggregate_obsp_matrix_per_cell_type
    return NicheCompass, add_gps_from_gp_dict_to_adata, compute_communication_gp_network, aggregate_obsp_matrix_per_cell_type, versions


def load_programs(path: Path, genes):
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or not raw:
        raise ValueError("gene_programs 必须是非空 JSON 对象")
    allowed = set(map(str, genes))
    programs = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(value, dict):
            raise ValueError("每个 gene program 需要唯一非空名称和对象定义")
        sources, targets = value.get("sources"), value.get("targets")
        source_cat = value.get("sources_categories")
        target_cat = value.get("targets_categories")
        if not isinstance(sources, list) or not isinstance(targets, list) or not sources or not targets:
            raise ValueError(f"gene program {name} 必须同时有非空 sources/targets")
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            raise ValueError(f"gene program {name} 含重复 source/target 基因")
        if not set(sources + targets) <= allowed:
            missing = sorted(set(sources + targets) - allowed)
            raise ValueError(f"gene program {name} 的基因不在输入中: {missing[:8]}")
        if not isinstance(source_cat, list) or not isinstance(target_cat, list) or len(source_cat) != len(sources) or len(target_cat) != len(targets):
            raise ValueError(f"gene program {name} 的类别标签须与 source/target 基因逐项对齐")
        if any(not isinstance(x, str) or not x.strip() for x in source_cat + target_cat):
            raise ValueError(f"gene program {name} 含空类别标签")
        programs[name] = {"sources": sources, "targets": targets,
                          "sources_categories": source_cat, "targets_categories": target_cat}
    return programs


def dense_matrix(data, layer):
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError(f"输入中不存在矩阵层 {layer}")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    return np.asarray(matrix, dtype=float)


def load_input(cfg, base):
    required = ("dataset", "research_question", "input", "native_root", "input_provenance",
                "gene_programs", "gene_program_provenance", "counts_layer",
                "coordinate_unit", "coordinate_provenance")
    for key in required:
        if not cfg.get(key):
            raise ValueError("NicheCompass 配置缺少: " + key)
    unit = cfg["coordinate_unit"]
    if unit not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if unit == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
    input_path = resolve(base, cfg["input"])
    gp_path = resolve(base, cfg["gene_programs"])
    data = ad.read_h5ad(input_path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞与基因 ID 必须唯一")
    keys = {name: cfg.get(name + "_key", name) for name in ("sample", "donor", "condition", "cell_type")}
    for key in keys.values():
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
        data.obs[key] = data.obs[key].astype(str)
    for sample, frame in data.obs.groupby(keys["sample"], observed=True):
        if frame[keys["donor"]].nunique() != 1 or frame[keys["condition"]].nunique() != 1:
            raise ValueError(f"样本 {sample} 不唯一对应供体/条件")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("NicheCompass 需要逐细胞对齐的有限二维坐标")
    counts = dense_matrix(data, cfg["counts_layer"])
    expression_layer = cfg.get("communication_expression_layer", "X")
    expression = dense_matrix(data, expression_layer)
    maximum = integer(cfg, "maximum_dense_elements", 50_000_000, 1)
    if data.n_obs * data.n_vars > maximum:
        raise ValueError("输入超过 maximum_dense_elements，不自动抽细胞或基因")
    if counts.shape != data.shape or not np.isfinite(counts).all() or (counts < 0).any() or not np.allclose(counts, np.round(counts)):
        raise ValueError("counts_layer 必须是与输入对齐的非负整数原始计数")
    if expression.shape != data.shape or not np.isfinite(expression).all() or (expression < 0).any():
        raise ValueError("communication_expression_layer 必须是对齐的有限非负矩阵")
    programs = load_programs(gp_path, data.var_names)
    for name, value in programs.items():
        for role in ("sources", "targets"):
            idx = [data.var_names.get_loc(g) for g in value[role]]
            if not np.any(expression[:, idx] > 0):
                raise ValueError(f"gene program {name} 的 {role} 在通讯表达矩阵中全为0")
    # PyTorch modules are float32 by default; keep the validated numeric values
    # while preventing an implicit float64/float32 failure in the native encoder.
    data.X = sparse.csr_matrix(expression.astype(np.float32, copy=False))
    data.layers["nichecompass_counts"] = sparse.csr_matrix(counts.astype(np.float32, copy=False))
    data.obsm["spatial"] = coordinates
    return data, coordinates, keys, programs, input_path, gp_path, expression_layer


def build_graph(data, coordinates, sample_key, neighbors, maximum_edges):
    graph = sparse.lil_matrix((data.n_obs, data.n_obs), dtype=np.float32)
    qc = []
    sample_values = data.obs[sample_key].to_numpy()
    for sample in list(dict.fromkeys(sample_values)):
        indices = np.flatnonzero(sample_values == sample)
        if len(indices) <= neighbors:
            raise ValueError(f"样本 {sample} 只有 {len(indices)} 个细胞，不能建立 {neighbors} 邻居图")
        if len(np.unique(coordinates[indices], axis=0)) != len(indices):
            raise ValueError(f"样本 {sample} 存在重复坐标")
        local = NearestNeighbors(n_neighbors=neighbors + 1).fit(coordinates[indices]).kneighbors(return_distance=False)[:, 1:]
        rows = np.repeat(np.arange(len(indices)), neighbors)
        directed = sparse.csr_matrix((np.ones(rows.size, dtype=np.float32), (rows, local.ravel())), shape=(len(indices), len(indices)))
        symmetric = directed.maximum(directed.T)
        graph[np.ix_(indices, indices)] = symmetric
        degree = np.asarray(symmetric.sum(1)).ravel()
        qc.append(dict(sample=sample, n_cells=len(indices), requested_neighbors=neighbors,
                       undirected_edges=int(symmetric.nnz // 2), mean_degree=float(degree.mean()),
                       median_degree=float(np.median(degree)), zero_neighbor_fraction=float(np.mean(degree == 0))))
    graph = graph.tocsr()
    if graph.nnz > maximum_edges:
        raise ValueError("样本内空间图超过 maximum_graph_edges，不自动删边")
    if any(graph[data.obs[sample_key].to_numpy() != sample][:, data.obs[sample_key].to_numpy() == sample].nnz
           for sample in data.obs[sample_key].unique()):
        raise ValueError("空间图出现跨样本边")
    return graph, qc


def serial_epoch_logs(logs, seed):
    rows = []
    for metric, values in logs.items():
        if not metric.startswith(("train_", "val_")):
            continue
        for epoch, value in enumerate(values, 1):
            if np.isscalar(value) and np.isfinite(value):
                rows.append(dict(row=str(epoch), column=f"seed {seed}: {metric}", value=float(value),
                                 seed=seed, epoch=epoch, metric=metric))
    return rows


def gp_summary_rows(summary, seed):
    rows = []
    for record in summary.to_dict("records"):
        base = {k: (None if pd.isna(record[k]) else record[k]) for k in
                ("gp_name", "all_gp_idx", "gp_active", "active_gp_idx", "n_source_genes",
                 "n_non_zero_source_genes", "n_target_genes", "n_non_zero_target_genes")}
        base["seed"] = seed
        rows.append(base)
    return rows


def gp_weight_rows(summary, seed):
    rows = []
    for record in summary.to_dict("records"):
        for role in ("source", "target"):
            genes = record[f"gp_{role}_genes"]
            weights = record[f"gp_{role}_genes_weights"]
            importances = record[f"gp_{role}_genes_importances"]
            for gene, weight, importance in zip(genes, weights, importances):
                rows.append(dict(factor=record["gp_name"], dimension=role, entity=gene,
                                 value=float(weight), importance=float(importance), seed=seed,
                                 active=bool(record["gp_active"])))
    return rows


def clustering(latent, seed, resolution):
    temp = ad.AnnData(np.zeros((latent.shape[0], 1), dtype=np.float32))
    temp.obsm["latent"] = latent
    k = min(15, max(2, latent.shape[0] - 1))
    sc.pp.neighbors(temp, n_neighbors=k, use_rep="latent", random_state=seed)
    sc.tl.leiden(temp, resolution=resolution, key_added="niche", random_state=seed)
    return temp.obs["niche"].astype(str).to_numpy()


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    base = config.parent
    native_root = resolve(base, cfg.get("native_root", ""))
    NicheCompass, add_gps, compute_network, aggregate_network, versions = verify_native(native_root)
    data, coordinates, keys, programs, input_path, gp_path, expression_layer = load_input(cfg, base)
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("exploratory", "publication"):
        raise ValueError("analysis_tier 只接受 exploratory 或 publication")
    seeds = cfg.get("seeds", [0, 1, 2] if tier == "publication" else [0])
    if not isinstance(seeds, list) or not seeds or any(type(x) is not int or x < 0 for x in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("seeds 必须是唯一非负整数列表")
    n_epochs = integer(cfg, "n_epochs", 100 if tier == "publication" else 25, 1, 5000)
    n_epochs_all = integer(cfg, "n_epochs_all_gps", min(25, n_epochs), 1, n_epochs)
    if tier == "publication" and (len(seeds) < 3 or n_epochs < 100):
        raise ValueError("publication 验收至少需要3个种子和100个 epoch")
    neighbors = integer(cfg, "n_neighbors", 4, 1, 200)
    communication_neighbors = integer(cfg, "communication_neighbors", neighbors, 1, 200)
    maximum_edges = integer(cfg, "maximum_graph_edges", 20_000_000, 1)
    graph, graph_qc = build_graph(data, coordinates, keys["sample"], neighbors, maximum_edges)
    data.obsp["spatial_connectivities"] = graph
    # Upstream uppercases genes in the supplied dictionary in place while
    # matching them case-insensitively. Preserve the checked resource object for
    # later per-sample expression eligibility and provenance.
    add_gps(copy.deepcopy(programs), data, min_genes_per_gp=2, min_source_genes_per_gp=1, min_target_genes_per_gp=1)
    retained = list(map(str, data.uns["nichecompass_gp_names"]))
    if retained != list(programs):
        raise ValueError("NicheCompass GP mask 构建后 program 名称或顺序变化；不静默丢弃")
    output_root = new_output(output)
    native_dir = output_root / "native_results"
    native_dir.mkdir()
    write_json(output_root / "run_config.json", cfg)
    signature = digest(input_path) + ":" + digest(gp_path) + ":" + digest(config) + ":" + UPSTREAM_COMMIT
    state = {"status": "running", "signature": signature, "completed_seeds": [], "failed_seeds": []}
    write_json(output_root / "run_state.json", state)
    latent_by_seed, active_by_seed, labels_by_seed, weight_vectors_by_seed = {}, {}, {}, {}
    epoch_rows, evaluation_rows, summary_rows, weight_rows, artifact_rows = [], [], [], [], []
    primary_model = None
    resolution = finite_number(cfg, "leiden_resolution", 0.4, 0.01)
    for seed in seeds:
        seed_data = data.copy()
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            model = NicheCompass(seed_data, counts_key="nichecompass_counts", adj_key="spatial_connectivities",
                conv_layer_encoder=cfg.get("conv_layer_encoder", "gcnconv"),
                active_gp_thresh_ratio=finite_number(cfg, "active_gp_thresh_ratio", 0.01, 0),
                n_addon_gp=0, include_chrom_access_recon_loss=False,
                use_cuda_if_available=bool(cfg.get("use_cuda_if_available", False)), seed=seed)
            model.train(n_epochs=n_epochs, n_epochs_all_gps=n_epochs_all,
                lr=finite_number(cfg, "learning_rate", 0.001, 0),
                lambda_edge_recon=finite_number(cfg, "lambda_edge_recon", 500000.0, 0),
                lambda_gene_expr_recon=finite_number(cfg, "lambda_gene_expr_recon", 300.0, 0),
                lambda_chrom_access_recon=0.0, lambda_l1_masked=finite_number(cfg, "lambda_l1_masked", 0.0, 0),
                lambda_l1_addon=0.0, edge_batch_size=integer(cfg, "edge_batch_size", 256, 1),
                n_sampled_neighbors=-1, use_cuda_if_available=bool(cfg.get("use_cuda_if_available", False)),
                verbose=False, monitor=bool(cfg.get("monitor_training", False)),
                use_early_stopping=bool(cfg.get("use_early_stopping", False)),
                reload_best_model=bool(cfg.get("reload_best_model", False)))
        native_text = capture.getvalue()
        print(native_text, end="")
        native_log = native_dir / f"seed_{seed}_stdout.log"
        native_log.write_text(native_text)
        labels = {"AUROC": "Edge AUROC", "AUPRC": "Edge AUPRC", "best accuracy": "Best edge accuracy",
                  "best F1": "Best edge F1", "target rna MSE": "Target RNA MSE", "source rna MSE": "Source RNA MSE"}
        found = dict(re.findall(r"^val (AUROC|AUPRC|best accuracy|best F1|target rna MSE|source rna MSE) score: ([0-9.eE+-]+)$",
                                native_text, flags=re.MULTILINE))
        if set(found) != set(labels):
            raise ValueError(f"seed {seed} 的原生最终验证指标不完整")
        evaluation_rows.extend(dict(row=f"seed {seed}", column=labels[key], value=float(found[key]), seed=seed,
                                    metric=labels[key]) for key in labels)
        latent = np.asarray(model.adata.obsm[model.latent_key_], dtype=float)
        active = list(map(str, model.get_active_gps()))
        if latent.shape != (data.n_obs, len(active)) or not np.isfinite(latent).all() or not active:
            raise ValueError(f"seed {seed} 的原生潜在表示无效或没有 active GP")
        summary = model.get_gp_summary()
        model_path = native_dir / f"seed_{seed}"
        model.save(str(model_path), save_adata=True)
        summary_file = native_dir / f"seed_{seed}_gp_summary.tsv"
        summary_serial = summary.copy()
        for column in summary_serial.columns:
            if summary_serial[column].map(lambda x: isinstance(x, (list, tuple, np.ndarray))).any():
                summary_serial[column] = summary_serial[column].map(
                    lambda x: json.dumps(list(x), ensure_ascii=False,
                                         default=lambda value: value.item() if isinstance(value, np.generic) else str(value))
                    if isinstance(x, (list, tuple, np.ndarray)) else x)
        summary_serial.to_csv(summary_file, sep="\t", index=False)
        latent_file = native_dir / f"seed_{seed}_latent.tsv"
        pd.DataFrame(latent, index=data.obs_names, columns=active).to_csv(latent_file, sep="\t", index_label="cell")
        epoch_rows.extend(serial_epoch_logs(model.trainer.epoch_logs, seed))
        summary_rows.extend(gp_summary_rows(summary, seed))
        weight_rows.extend(gp_weight_rows(summary, seed))
        weight_vectors_by_seed[seed] = {
            record["gp_name"]: np.asarray(list(record["gp_source_genes_weights"]) + list(record["gp_target_genes_weights"]), dtype=float)
            for record in summary.to_dict("records")}
        latent_by_seed[seed], active_by_seed[seed] = latent, active
        labels_by_seed[seed] = clustering(latent, seed, resolution)
        artifact_rows.append(dict(seed=seed, model_directory=str(model_path.relative_to(output_root)),
                                  gp_summary=summary_file.name if summary_file.parent == output_root else str(summary_file.relative_to(output_root)),
                                  gp_summary_sha256=digest(summary_file), latent=str(latent_file.relative_to(output_root)),
                                  latent_sha256=digest(latent_file), active_gps=active,
                                  native_stdout=str(native_log.relative_to(output_root)), native_stdout_sha256=digest(native_log),
                                  training_seconds=float(model.trainer.training_time)))
        state["completed_seeds"].append(seed)
        write_json(output_root / "run_state.json", state)
        if seed == seeds[0]:
            primary_model = model
    write_table(output_root / "training_log.tsv", epoch_rows)
    write_table(output_root / "gp_summary.tsv", summary_rows)
    write_table(output_root / "gp_gene_weights.tsv", weight_rows)
    write_json(output_root / "native_artifacts.json", {"signature": signature, "seeds": artifact_rows})
    primary_seed = seeds[0]
    primary_latent = latent_by_seed[primary_seed]
    primary_active = active_by_seed[primary_seed]
    primary_labels = labels_by_seed[primary_seed]
    primary_model.adata.obs["nichecompass_niche"] = primary_labels
    primary_model.adata.obsm[primary_model.latent_key_] = primary_latent
    sc.pp.neighbors(primary_model.adata, n_neighbors=min(15, data.n_obs - 1), use_rep=primary_model.latent_key_, random_state=primary_seed)
    sc.tl.umap(primary_model.adata, random_state=primary_seed)
    umap = np.asarray(primary_model.adata.obsm["X_umap"], dtype=float)
    gp_variance = sorted(zip(np.var(primary_latent, axis=0), primary_active), key=lambda x: (-x[0], x[1]))
    requested_gps = cfg.get("communication_gene_programs")
    if requested_gps is None:
        selected_gps = [name for _, name in gp_variance[:integer(cfg, "top_communication_gene_programs", 6, 1, 20)]]
        selection_rule = "Primary-seed active GPs ranked by latent variance; complete GP scores and weights are retained."
    else:
        if not isinstance(requested_gps, list) or not requested_gps or not set(requested_gps) <= set(primary_active):
            raise ValueError("communication_gene_programs 必须是 primary seed active GP 的非空子集")
        selected_gps = requested_gps
        selection_rule = "Predeclared communication_gene_programs in run config."
    network_by_gp, raw_network_by_gp, score_rows, skipped = {}, {}, [], []
    original_adata = primary_model.adata
    for sample in list(dict.fromkeys(data.obs[keys["sample"]])):
        mask = data.obs[keys["sample"]].to_numpy() == sample
        sample_data = original_adata[mask].copy()
        if sample_data.n_obs <= communication_neighbors:
            raise ValueError(f"样本 {sample} 细胞数不足 communication_neighbors")
        viable = []
        for gp in selected_gps:
            definition = programs[gp]
            source_idx = [sample_data.var_names.get_loc(g) for g in definition["sources"]]
            target_idx = [sample_data.var_names.get_loc(g) for g in definition["targets"]]
            x = sample_data.X.toarray() if sparse.issparse(sample_data.X) else np.asarray(sample_data.X)
            if np.max(x[:, source_idx]) <= 0 or np.max(x[:, target_idx]) <= 0:
                skipped.append(dict(sample=sample, gp=gp, reason="source_or_target_expression_all_zero"))
            else:
                viable.append(gp)
        if not viable:
            continue
        primary_model.adata = sample_data
        network = compute_network(viable, primary_model, group_key=keys["cell_type"], n_neighbors=communication_neighbors)
        for gp in viable:
            part = network[network["edge_type"] == gp]
            raw = aggregate_network(primary_model.adata, f"{gp}_connectivities", keys["cell_type"], agg_rows=True)
            for source in raw.index:
                for target in raw.columns:
                    raw_network_by_gp.setdefault(gp, []).append(
                        dict(row=str(source), column=str(target), value=float(raw.loc[source, target]),
                             sample=sample, gene_program=gp))
            rows = []
            for row in part.itertuples(index=False):
                rows.append(dict(source=str(row.source), target=str(row.target), value=float(row.strength),
                                 strength_unscaled=float(row.strength_unscaled), sample=sample, gene_program=gp))
            network_by_gp.setdefault(gp, []).extend(rows)
            if part.empty:
                skipped.append(dict(sample=sample, gp=gp, reason="no_positive_edge_after_upstream_within_gp_normalization"))
            for role in ("source", "target"):
                column = f"{gp}_{role}_score"
                for cell, value in zip(sample_data.obs_names, primary_model.adata.obs[column]):
                    idx = data.obs_names.get_loc(cell)
                    score_rows.append(dict(sample=sample, cell=str(cell), x=float(coordinates[idx, 0]),
                                           y=float(coordinates[idx, 1]), value=float(value), gene_program=gp, role=role))
    primary_model.adata = original_adata
    write_table(output_root / "communication_skipped.tsv", skipped,
                fields=["sample", "gp", "reason"] if not skipped else None)
    stability_rows, niche_stability_rows = [], []
    for i, left in enumerate(seeds):
        for right in seeds[i + 1:]:
            left_map = {gp: latent_by_seed[left][:, j] for j, gp in enumerate(active_by_seed[left])}
            right_map = {gp: latent_by_seed[right][:, j] for j, gp in enumerate(active_by_seed[right])}
            for gp in retained:
                value = None
                if gp in left_map and gp in right_map:
                    raw = float(spearmanr(left_map[gp], right_map[gp]).statistic)
                    direction = float(np.dot(weight_vectors_by_seed[left][gp], weight_vectors_by_seed[right][gp]))
                    value = raw * (1.0 if direction >= 0 else -1.0)
                else:
                    raw = None
                stability_rows.append(dict(row=gp, column=f"seed {left} vs {right}", value=value,
                                           raw_latent_spearman=raw, left_seed=left, right_seed=right,
                                           active_both=value is not None,
                                           alignment="decoder_weight_dot_product_sign" if value is not None else "not_active_in_both"))
            niche_stability_rows.append(dict(row="Leiden niche ARI", column=f"seed {left} vs {right}",
                                             value=float(adjusted_rand_score(labels_by_seed[left], labels_by_seed[right]))))
    bundle = {
        "schema_version": 2, "dataset": cfg["dataset"], "method": "NicheCompass",
        "method_version": UPSTREAM_VERSION, "implementation": "native",
        "figure_inapplicability": {
            "lr_evidence": "NicheCompass GP masks and learned weights do not provide LR hypothesis P/q values.",
            "roles": "Within-GP min-max strengths are not cross-GP additive centrality scores.",
            "cellchat_patterns": "The latent dimensions are named gene programs, not CellChat NMF patterns.",
            "pathway_sankey": "Within-GP normalized edges are not conserved flow and cannot be added across programs.",
            "ligand_response": "GP scores are representation-learning dimensions, not ligand-to-target response activity.",
            "intracellular": "The model does not infer a directed LR-TF-target causal chain.",
            "enrichment": "No gene-set enrichment test is performed by this runner.",
            "spatial_direction": "Spatial neighborhoods are undirected and do not estimate a physical direction vector.",
            "relay_dynamic": "No time, trajectory, velocity or multi-hop relay model is fit.",
            "special_molecules": "Only molecules explicitly represented by the supplied GP JSON and assay are modeled.",
            "functional_clinical": "No phenotype or clinical outcome association is inferred."
        },
        "provenance": {
            "input_sha256": digest(input_path), "gene_program_sha256": digest(gp_path), "parameters": cfg,
            "input_provenance": cfg["input_provenance"], "gene_program_provenance": cfg["gene_program_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"],
            "upstream": {"url": "https://github.com/Lotfollahi-lab/nichecompass", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "license": "BSD-3-Clause"},
            "source_sha256": SOURCE_HASHES, "versions": versions, "native_artifacts": "native_artifacts.json",
            "network_selection": {"gene_programs": selected_gps, "rule": selection_rule},
            "statistical_semantics": {
                "latent": "Each active named GP is a learned spatial representation dimension; signs and magnitudes are model scores, not probabilities.",
                "network": "For each GP and sample, source and target expression are max-normalized per gene, multiplied by learned signed weights and the GP latent score, averaged, clipped below zero, multiplied over spatial-neighbor cell pairs and aggregated by cell type.",
                "normalization": "The upstream function min-max normalizes each GP network independently and rounds to two decimals. Values are only relative within the same GP and sample.",
                "inference": "Training metrics and seed stability assess optimization/reproducibility. They are not biological P values or donor-level condition tests.",
                "graph": "Training and communication graphs are rebuilt separately within every declared sample; no cross-sample spatial edge is allowed."
            },
            "limitations": [
                "GP results depend on the declared, checksummed resource and measured genes; absence from that resource or assay is not evidence of no communication.",
                "Niche labels and GP scores are descriptive learned representations and do not establish causality.",
                "Independent within-GP min-max values cannot be compared or summed across GPs, datasets or samples.",
                "Seed stability is algorithmic reproducibility; biological specificity requires independent donors and a predeclared replicate-aware comparison.",
                "The runner executes RNA-only GCN NicheCompass with no addon GPs and does not claim ATAC, reference mapping or unmasked addon-GP support."
            ]
        }, "tables": []
    }
    add_table(bundle, output_root, "nichecompass_training", "matrix", epoch_rows,
              "NicheCompass trainer 的全部有限逐 epoch 原生训练/验证记录；不平滑、不补点，收敛不等同生物学验证。",
              value_kind="native_score", figure_role="convergence", axis_label="Native training/evaluation value")
    performance = [r for r in evaluation_rows if r["metric"] in
                   ("Edge AUROC", "Edge AUPRC", "Best edge accuracy", "Best edge F1")]
    reconstruction = [r for r in evaluation_rows if r["metric"] in ("Target RNA MSE", "Source RNA MSE")]
    add_table(bundle, output_root, "nichecompass_validation_performance", "matrix", performance,
              "每个种子训练结束后由 NicheCompass 原生 eval_end 输出的边重建 AUROC/AUPRC/最佳 accuracy/F1；四项均在0–1尺度。",
              value_kind="native_score", axis_label="Native validation metric",
              column_order=["Edge AUROC", "Edge AUPRC", "Best edge accuracy", "Best edge F1"])
    add_table(bundle, output_root, "nichecompass_validation_reconstruction", "matrix", reconstruction,
              "每个种子训练结束后由 NicheCompass 原生 eval_end 输出的 source/target RNA MSE；与0–1边重建指标分图，避免共享色标掩盖差异。",
              value_kind="nonnegative_strength", axis_label="Native RNA MSE",
              column_order=["Target RNA MSE", "Source RNA MSE"])
    embedding_rows = [dict(sample="all cells", cell=str(cell), x=float(x), y=float(y),
                           label=str(label), seed=primary_seed)
                      for cell, (x, y), label in zip(data.obs_names, umap, primary_labels)]
    add_table(bundle, output_root, "nichecompass_latent_umap", "embedding_points", embedding_rows,
              "primary seed 的原生 active-GP latent 经 Scanpy neighbors/UMAP 得到的二维展示，颜色为同一 latent 上的 Leiden niche。",
              value_kind="category", embedding_method="UMAP", embedding_provenance=f"NicheCompass active-GP latent; seed {primary_seed}; Scanpy 1.11.5",
              title="NicheCompass latent niches")
    spatial_rows = [dict(sample=str(data.obs.iloc[i][keys["sample"]]), cell=str(cell), x=float(coordinates[i, 0]),
                         y=float(coordinates[i, 1]), value=0.0, label=str(primary_labels[i]))
                    for i, cell in enumerate(data.obs_names)]
    add_table(bundle, output_root, "nichecompass_niche_spatial", "spatial_points", spatial_rows,
              "primary seed NicheCompass latent 的 Leiden niche 投回真实组织坐标；类别是描述性空间域，不是组织学真值。",
              value_kind="category", coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
              physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")),
              title="NicheCompass niches in physical space")
    activity_rows = []
    for group in sorted(data.obs[keys["cell_type"]].unique()):
        mask = data.obs[keys["cell_type"]].to_numpy() == group
        for j, gp in enumerate(primary_active):
            activity_rows.append(dict(factor=gp, dimension="cell-type mean latent", entity=group,
                                      value=float(primary_latent[mask, j].mean())))
    add_table(bundle, output_root, "nichecompass_gp_activity", "patterns", activity_rows,
              "primary seed 中各细胞类型的原生 GP latent 算术均值；正负号保留，未做显著性检验。",
              value_kind="native_score", axis_label="Mean GP latent score")
    primary_weights = [r for r in weight_rows if r["seed"] == primary_seed]
    add_table(bundle, output_root, "nichecompass_gp_gene_weights", "patterns", primary_weights,
              "primary seed 的完整原生 GP source/target decoder gene weights；图按绝对载荷选择展示，完整表保留权重与 importance。",
              value_kind="native_score", axis_label="Native decoder weight")
    if stability_rows:
        add_table(bundle, output_root, "nichecompass_gp_seed_stability", "matrix", stability_rows,
                  "按同名 active GP 在全部细胞间计算 seed-pair Spearman，并按两次拟合 decoder weight 向量点积符号消除 latent/decoder 同时翻转的等价方向；未经对齐的相关保留在 raw_latent_spearman。任一 seed inactive 时保持 NA，真实负相关保留。",
                  value_kind="native_score", axis_label="Spearman correlation", figure_role="robustness",
                  row_order=retained)
        add_table(bundle, output_root, "nichecompass_niche_seed_stability", "matrix", niche_stability_rows,
                  "每对种子的 Leiden niche 调整 Rand 指数；聚类各自在对应 seed latent 上按同一参数计算。",
                  value_kind="native_score", axis_label="Adjusted Rand index", figure_role="robustness")
    for number, gp in enumerate(selected_gps, 1):
        rows = network_by_gp.get(gp, [])
        raw_rows = raw_network_by_gp.get(gp, [])
        for sample_number, sample in enumerate(list(dict.fromkeys(r["sample"] for r in raw_rows)), 1):
            sample_raw = [r for r in raw_rows if r["sample"] == sample]
            cell_types = sorted({r["row"] for r in sample_raw} | {r["column"] for r in sample_raw})
            add_table(bundle, output_root, f"nichecompass_gp_raw_matrix_{number}_{sample_number}", "matrix", sample_raw,
                      f"NicheCompass {gp} 在样本 {sample} 的完整细胞类型聚合、未缩放 source×target potential；包含真实0。它只在该 GP/样本内有尺度，不是分子流。",
                      value_kind="nonnegative_strength", axis_label="Unscaled aggregated potential",
                      row_order=cell_types, column_order=cell_types, title=f"{gp} — {sample}: unscaled potential")
        for sample_number, sample in enumerate(list(dict.fromkeys(r["sample"] for r in rows)), 1):
            sample_rows = [r for r in rows if r["sample"] == sample]
            add_table(bundle, output_root, f"nichecompass_gp_network_{number}_{sample_number}", "network", sample_rows,
                      f"NicheCompass 原生 {gp} 通讯网络；样本 {sample} 内独立聚合并按该 GP 自身 min-max 后四舍五入至2位。只可在这个 GP/样本内解释相对边强。",
                      value_kind="nonnegative_strength", additive=True, directed=True,
                      axis_label="Within-GP relative strength", title=f"{gp} — {sample}: relative communication network")
        for role in ("source", "target"):
            points = [r for r in score_rows if r["gene_program"] == gp and r["role"] == role]
            add_table(bundle, output_root, f"nichecompass_gp_{number}_{role}_spatial", "spatial_points", points,
                      f"{gp} 的逐细胞原生 {role} potential score；表达×decoder weight×GP latent 后按基因平均并将负值截为0。",
                      value_kind="nonnegative_strength", coordinate_unit=cfg["coordinate_unit"],
                      coordinate_provenance=cfg["coordinate_provenance"], physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")),
                      y_down=bool(cfg.get("y_down")), axis_label=f"{gp} {role} score", title=f"{gp}: {role} potential")
    add_table(bundle, output_root, "nichecompass_graph_qc", "matrix",
              [dict(row=r["sample"], column=metric, value=r[metric]) for r in graph_qc
               for metric in ("n_cells", "undirected_edges", "mean_degree", "zero_neighbor_fraction")],
              "按样本独立构建的对称 KNN 训练图质控；不跨样本连边。", value_kind="nonnegative_strength",
              axis_label="Graph QC value")
    write_json(output_root / "bundle.json", bundle)
    state.update(status="complete", bundle_sha256=digest(output_root / "bundle.json"),
                 selected_gene_programs=selected_gps, skipped_communication=skipped)
    write_json(output_root / "run_state.json", state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.exit(run(args.config, args.out))
