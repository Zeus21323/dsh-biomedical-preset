#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["torch==1.13.1", "numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "anndata==0.10.6", "scikit-learn==1.4.1.post1"]
# ///
"""Run fixed spaCI adaptive spatial gene-embedding analysis and its paper-defined summaries."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
import torch
from torch.utils.data import DataLoader, TensorDataset

from communication_contract import add_table, digest, new_output, write_json


UPSTREAM_COMMIT = "5bf1470ccfcf45e01f11621c58d884b0dd9cfc80"
UPSTREAM_VERSION = "1.0.0"
SOURCE_HASHES = {
    "README.md": "2e52cecc1457a8b79ae7a54be65cbad34b6466fb0eddf1187a6cf58bd181279a",
    "LICENCE": "8ff66665133f3821ed514a7f514e891491770877c7330e7334aeebb84e8bdeed",
    "requirements.txt": "77da8640a5c8e0718e47957855679b1563f46e11132b53320ec8021c2fbd2ad9",
    "configuration.py": "fda788989ee4c23100596e8a92a39e75bd00a78af3e260636df1885ae9add030",
    "configure.yml": "1ee1b18a9138f7eec8d6d685d7748128a545b3d1b368f2d25fd29a894a0699d3",
    "model/dataloader.py": "b2e68f92ed13154e6159d93f7dd2cb8e15527667cee82d3ef6fca33bd5a4a236",
    "model/model.py": "dde4eaf538ff90416ab58d2676a26c184b32ef635baa60a6f87e22e52486ff55",
    "main_yaml.py": "db723f59b02541b5c59e0832caa37ec15d70e16a74903b054c4d20195bab3393",
    "src/spaCI_utils.R": "86fa26f63dd7f30955fbd03bfe52daa2b4deea22c7d1879cd40ece9f42580609",
    "src/spaCI_preprocess.R": "a34c8c37b047a5092c08b2ca9e28f2b582c7cfc88352f309dcf90cc9e6164e6d",
    "src/spaCI_database.RDS": "94b1ed68e41f5295e7252f31a0fb6622b94926e43be1e714601685224cb7e684",
}
VERSIONS = {"torch": "1.13.1", "numpy": "1.26.4", "pandas": "2.2.1", "scipy": "1.12.0",
            "anndata": "0.10.6", "scikit-learn": "1.4.1.post1"}


def resolve(base, value):
    return (Path(base) / value).resolve()


def integer(value, name, low=1, high=None):
    if type(value) is not int or value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是不小于 {low}" + (f"且不超过 {high}" if high is not None else "") + " 的整数")
    return value


def finite(value, name, low=None, high=None):
    value = float(value)
    if not np.isfinite(value) or low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是范围内有限数")
    return value


def safe_id(value):
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_") or "item"


def verify_native(root):
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"spaCI 固定源码缺失或摘要不符: {relative}")
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError(f"spaCI 固定源码提交应为 {UPSTREAM_COMMIT}，当前为 {commit}")
    if sys.version_info[:2] != (3, 10):
        raise ValueError("spaCI 审计兼容环境需要 Python 3.10")
    observed = {}
    for package, expected in VERSIONS.items():
        actual = importlib.metadata.version(package)
        observed[package] = actual
        if actual != expected:
            raise ValueError(f"spaCI 审计兼容环境要求 {package}=={expected}，当前为 {actual}")
    # Fixed source imports torchvision but never references it. Its declared
    # torchvision 0.11.1 cannot coexist with torch 1.6 and is unavailable on
    # the validation platform, so a deliberately empty import shim is used.
    sys.modules.setdefault("torchvision", types.ModuleType("torchvision"))
    sys.path.insert(0, str(root))
    from model.model import TripletGraphModel
    return TripletGraphModel, observed


def dense(data, layer):
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError(f"表达层不存在: {layer}")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.shape != data.shape or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("spaCI 表达矩阵必须有限、非负且与 AnnData 对齐")
    return matrix


def input_contract(cfg, base):
    required = ("dataset", "research_question", "input", "input_provenance", "native_root",
                "ligand_receptor_resource", "ligand_receptor_sha256", "ligand_receptor_provenance",
                "expression_layer", "expression_scale", "normalization_definition", "coordinate_unit",
                "coordinate_provenance", "celltype_key")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("spaCI 配置缺少: " + key)
    paths = {key: resolve(base, cfg[key]) for key in ("input", "native_root", "ligand_receptor_resource")}
    for key, path in paths.items():
        if not path.exists():
            raise ValueError(f"spaCI 路径不存在: {key}")
    if digest(paths["ligand_receptor_resource"]) != cfg["ligand_receptor_sha256"]:
        raise ValueError("spaCI 配体受体资源 SHA-256 与配置不符")
    data = ad.read_h5ad(paths["input"])
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("spaCI 需要唯一细胞和基因 ID")
    if data.n_obs < 50 or data.n_obs > integer(cfg.get("maximum_cells", 10000), "maximum_cells", 50):
        raise ValueError("spaCI 细胞数不在允许范围")
    matrix = dense(data, cfg["expression_layer"])
    if any(str(g) != str(g).upper() for g in data.var_names):
        raise ValueError("spaCI 输入基因必须预先统一为大写；执行器不静默改名")
    key = cfg["celltype_key"]
    if key not in data.obs or data.obs[key].isna().any() or (data.obs[key].astype(str).str.strip() == "").any():
        raise ValueError("spaCI 需要完整细胞类型注释")
    coordinates = np.asarray(data.obsm.get(cfg.get("spatial_key", "spatial")), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("spaCI 需要与细胞同序的有限二维坐标")
    if cfg["coordinate_unit"] not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if cfg["coordinate_unit"] == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标必须明确 physical_scale_unavailable=true")
    lr = pd.read_csv(paths["ligand_receptor_resource"], sep=None, engine="python")
    if not {"ligand", "receptor"} <= set(lr):
        raise ValueError("spaCI 配体受体资源需要 ligand/receptor 列")
    lr = lr[["ligand", "receptor"]]
    if lr.isna().any().any() or (lr.astype(str).apply(lambda x: x.str.strip()) == "").any().any():
        raise ValueError("spaCI 资源含空分子名")
    # The bundled human-symbol table itself contains five mixed-case symbols
    # and 12 duplicated rows. Canonicalization is explicit and deterministic,
    # while the unmodified resource and its hash remain in native_results.
    lr = lr.astype(str).apply(lambda x: x.str.upper()).drop_duplicates().reset_index(drop=True)
    k = integer(cfg.get("neighbors", 5), "neighbors", 2, data.n_obs)
    cutoff = finite(cfg.get("correlation_cutoff_fraction", 0.01), "correlation_cutoff_fraction", np.finfo(float).eps, 0.1)
    threshold = finite(cfg.get("prediction_threshold", 0.5), "prediction_threshold", 0, 1)
    epochs = integer(cfg.get("epochs", 10), "epochs", 1, 10000)
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("publication", "exploratory"):
        raise ValueError("analysis_tier 只接受 publication 或 exploratory")
    if tier == "publication" and epochs < 10:
        raise ValueError("spaCI publication 模式至少使用作者示例的10轮训练")
    return paths, data, matrix, coordinates, lr, k, cutoff, threshold, epochs, tier


def r_round(value):
    return int(np.rint(value))


def preprocess_exact(matrix, genes, coordinates, lr, k, fraction):
    # Exact spaCI R semantics: keep genes with zeros in fewer than half cells,
    # correlate raw supplied values, use R column-major matrix ordering, retain
    # directed pairs, and use the first half for three-negative triplets.
    keep = (matrix == 0).sum(axis=0) < matrix.shape[0] / 2
    kept = matrix[:, keep].T.astype(np.float64)
    kept_genes = np.asarray(genes)[keep]
    if len(kept_genes) < 20:
        raise ValueError("spaCI 零比例过滤后基因不足20")
    corr = np.corrcoef(kept)
    if not np.isfinite(corr).all():
        raise ValueError("spaCI 相关矩阵含非有限值；过滤后存在零方差基因")
    np.fill_diagonal(corr, 0)
    flat = corr.ravel(order="F")
    high_index = max(1, r_round(len(flat) * fraction)) - 1
    high = np.sort(flat)[::-1][high_index]
    if not high > 0.5:
        raise ValueError(f"spaCI 上游规则未检出强相关结构: cutoff={high:.6g}")
    pos_i, pos_j = np.where(corr > high)
    order = np.argsort(pos_j * len(kept_genes) + pos_i, kind="stable")
    pos_i, pos_j = pos_i[order], pos_j[order]
    split = r_round(len(pos_i) / 2)
    triplets = []
    for i, j in zip(pos_i[:split], pos_j[:split]):
        for negative in np.argsort(corr[i], kind="stable")[:3]:
            triplets.append((kept_genes[i], kept_genes[j], kept_genes[negative]))
    unique_abs = np.unique(np.abs(flat))
    low_index = max(1, r_round(len(unique_abs) * fraction)) - 1
    low = np.sort(unique_abs)[low_index]
    neg_i, neg_j = np.where((np.abs(corr) <= low) & (np.abs(corr) > 0))
    neg_order = np.argsort(neg_j * len(kept_genes) + neg_i, kind="stable")
    validation = [(kept_genes[i], kept_genes[j], 1) for i, j in zip(pos_i[split:], pos_j[split:])]
    validation += [(kept_genes[i], kept_genes[j], 0) for i, j in zip(neg_i[neg_order], neg_j[neg_order])]
    measured = set(genes)
    candidates = [(a, b) for a, b in lr.itertuples(index=False, name=None) if a in measured and b in measured]
    if not candidates:
        raise ValueError("spaCI 资源与表达矩阵没有可评分配体受体对")
    distances = cdist(coordinates, coordinates)
    nearest = np.argsort(distances, axis=1, kind="stable")[:, :k]
    adjacency = np.zeros((matrix.shape[0], matrix.shape[0]), dtype=np.float32)
    for i in range(matrix.shape[0]):
        adjacency[i, nearest[i]] = 1
        adjacency[nearest[i], i] = 1
    return kept_genes, corr, high, low, triplets, validation, candidates, adjacency


def seed_all(seed=10):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if hasattr(torch, "cuda"): torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def metrics(scores, labels, threshold):
    labels = np.asarray(labels, dtype=int); predicted = np.asarray(scores) > threshold
    tp = int(((predicted == 1) & (labels == 1)).sum()); tn = int(((predicted == 0) & (labels == 0)).sum())
    fp = int(((predicted == 1) & (labels == 0)).sum()); fn = int(((predicted == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.; recall = tp / (tp + fn) if tp + fn else 0.
    return {"TP": tp, "TN": tn, "FP": fp, "FN": fn, "Accuracy": (tp + tn) / len(labels),
            "Precision": precision, "Recall": recall, "Specificity": tn / (tn + fp) if tn + fp else 0.,
            "F1": 2 * precision * recall / (precision + recall) if precision + recall else 0.}


def run(config, output):
    started = time.time(); config = Path(config).resolve(); base = config.parent
    cfg = json.loads(config.read_text()); out = new_output(output)
    write_json(out / "run_config.json", cfg); write_json(out / "run_state.json", {"schema_version": 2, "status": "running", "config_sha256": digest(config)})
    paths, data, matrix, coordinates, lr, k, fraction, threshold, epochs, tier = input_contract(cfg, base)
    Model, versions = verify_native(paths["native_root"])
    kept_genes, corr, high, low, triplets, validation, candidates, adjacency = preprocess_exact(
        matrix, np.asarray(data.var_names, dtype=str), coordinates, lr, k, fraction)
    native = out / "native_results"; native.mkdir()
    shutil.copy2(paths["input"], native / "input.h5ad"); shutil.copy2(paths["ligand_receptor_resource"], native / "ligand_receptor_resource.tsv")
    pd.DataFrame(triplets, columns=["key", "pos", "neg"]).to_csv(native / "triplet.csv", index=True)
    pd.DataFrame(validation, columns=["ligand", "receptor", "label"]).to_csv(native / "validation_pairs.csv", index=True)
    pd.DataFrame(candidates, columns=["ligand", "receptor"]).assign(trueLabel=0).to_csv(native / "test_lr_pairs.csv", index=True)
    pd.DataFrame(matrix.T, index=data.var_names, columns=data.obs_names).to_csv(native / "exp_data_LR.csv")
    pd.DataFrame(adjacency, index=data.obs_names, columns=data.obs_names).to_csv(native / "spatial_graph.csv")
    gene_index = {gene: i for i, gene in enumerate(data.var_names)}
    def features(names): return torch.from_numpy(np.stack([matrix[:, gene_index[x]] for x in names]).astype(np.float32))
    adj = torch.from_numpy(adjacency); device = "cpu"; seed_all(10)
    model = Model(input_dim=data.n_obs, graph_dim=data.n_obs,
                  mlp_channels=cfg.get("mlp_hidden", [200, 50, 20]), graph_channels=cfg.get("graph_hidden", [200, 50, 20]),
                  lr=finite(cfg.get("learning_rate", 1e-4), "learning_rate", np.finfo(float).eps), save_path=str(native), device=device)
    train_data = TensorDataset(features([x[0] for x in triplets]), features([x[1] for x in triplets]), features([x[2] for x in triplets]))
    validation_a = features([x[0] for x in validation]); validation_b = features([x[1] for x in validation]); validation_y = np.asarray([x[2] for x in validation])
    batch_size = integer(cfg.get("batch_size", 2048), "batch_size", 2, 100000)
    train_loader = DataLoader(train_data, batch_size=batch_size, shuffle=True)
    history = []; best_f1 = -1.; best_epoch = -1; best_state = None
    for epoch in range(epochs):
        losses = []
        for anchor, positive, negative in train_loader:
            model.set_input({"A": anchor, "P": positive, "N": negative, "adj": adj}, istrain=1)
            model.single_update(); losses.append(float(model.loss.detach()))
        with torch.no_grad():
            model.set_input({"x1": validation_a, "x2": validation_b, "adj": adj}, istrain=0)
            val_scores = model.inference().detach().numpy()
        observed = metrics(val_scores, validation_y, threshold)
        history.append({"epoch": epoch + 1, "loss": float(np.mean(losses)), **observed})
        if observed["F1"] > best_f1:
            best_f1 = observed["F1"]; best_epoch = epoch + 1
            best_state = {name: value.detach().cpu().clone() for name, value in model.model.state_dict().items()}
    if best_state is None: raise ValueError("spaCI 未产生可保存模型")
    torch.save(model.model.state_dict(), native / "final.pth")
    model.model.load_state_dict(best_state); torch.save(best_state, native / "best_f1.pth")
    pd.DataFrame(history).to_csv(native / "training_history.tsv", sep="\t", index=False)
    with torch.no_grad():
        model.set_input({"x1": validation_a, "x2": validation_b, "adj": adj}, istrain=0)
        val_scores = model.inference().detach().numpy()
    unique_genes = sorted(set(x for pair in candidates for x in pair))
    with torch.no_grad():
        model.model.eval(); embeddings = []
        for start in range(0, len(unique_genes), batch_size):
            embeddings.append(model.model(features(unique_genes[start:start + batch_size]), adj).detach().numpy())
    embedding = np.vstack(embeddings); embedding_map = dict(zip(unique_genes, embedding))
    pair_scores = np.asarray([np.dot(embedding_map[a], embedding_map[b]) /
                              max(np.linalg.norm(embedding_map[a]) * np.linalg.norm(embedding_map[b]), 1e-6) for a, b in candidates])
    predicted = pair_scores > threshold
    prediction_frame = pd.DataFrame(candidates, columns=["ligand", "receptor"])
    prediction_frame["score"] = pair_scores; prediction_frame["predicted"] = predicted.astype(int)
    prediction_frame.to_csv(native / "predict.csv", index=False)
    pd.DataFrame(embedding, index=unique_genes).to_csv(native / "gene_embeddings.csv")
    final_metrics = metrics(val_scores, validation_y, threshold)
    pd.DataFrame([final_metrics]).assign(best_epoch=best_epoch).to_csv(native / "validation_metrics.tsv", sep="\t", index=False)
    celltypes = data.obs[cfg["celltype_key"]].astype(str); type_order = sorted(celltypes.unique())
    def trimmed(values):
        values = np.sort(np.asarray(values, dtype=float)); trim = int(math.floor(len(values) * .1))
        return float(values[trim:len(values)-trim].mean()) if trim and 2 * trim < len(values) else float(values.mean())
    expression_means = {(kind, gene): trimmed(matrix[celltypes.to_numpy() == kind, gene_index[gene]]) for kind in type_order for gene in unique_genes}
    sample = str(cfg.get("sample", data.obs[cfg.get("sample_key", "sample")].astype(str).iloc[0] if cfg.get("sample_key", "sample") in data.obs else cfg["dataset"]))
    spatial_meta = dict(coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                        physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    bundle = {"schema_version": 2, "dataset": cfg["dataset"], "method": "spaCI", "method_version": UPSTREAM_VERSION,
        "implementation": "Fixed spaCI TripletGraphModel with audited Python reconstruction of fixed R preprocessing and paper-defined cell-type interaction strength",
        "research_question": cfg["research_question"], "figure_inapplicability": {
            "condition_effects": "One tissue section and no donor-level condition contrast were supplied.",
            "cellchat_patterns": "spaCI does not fit CellChat NMF communication patterns.",
            "pathway_sankey": "The supplied LR resource has no single pathway labels and spaCI does not estimate conserved molecular flow.",
            "ligand_response": "spaCI predicts LR embedding similarity and does not fit ligand-to-target response activity.",
            "intracellular": "No species-matched TF-target resource was supplied; receptor-to-TF links are therefore not inferred.",
            "factors": "spaCI produces gene embeddings rather than tensor, MOFA or NMF communication factors.",
            "enrichment": "No gene-set test with a declared universe was performed.",
            "spatial_direction": "The K-nearest-neighbor graph is symmetric and has no inferred signaling direction field.",
            "neighborhood_response": "spaCI embeds expression over a spatial graph but does not estimate target response in each neighborhood.",
            "relay_dynamic": "spaCI fits neither temporal dynamics nor multi-hop relay chains.",
            "special_molecules": "The supplied resource contains gene ligand-receptor pairs only.",
            "functional_clinical": "No donor-level functional or clinical outcome was supplied."},
        "provenance": {"input_sha256": digest(paths["input"]), "input_provenance": cfg["input_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"], "parameters": cfg,
            "ligand_receptor_sha256": digest(paths["ligand_receptor_resource"]), "ligand_receptor_provenance": cfg["ligand_receptor_provenance"],
            "upstream": {"url": "https://github.com/QSong-github/spaCI", "commit": UPSTREAM_COMMIT, "version": UPSTREAM_VERSION,
                         "paper_doi": "10.1093/bib/bbac563", "license": "MIT (upstream file name: LICENCE)"},
            "source_sha256": SOURCE_HASHES, "python_versions": versions,
            "statistical_semantics": {"lr_score": "Cosine similarity of fixed-upstream nonnegative latent gene embeddings; thresholded globally, without a P value.",
                "celltype_strength": "For each globally predicted LR pair, product of source ligand and target receptor cell-type trimmed means after dropping floor(10%) observations from each tail; sums are additive descriptive strengths as defined in the paper.",
                "validation": "Held-out high-correlation and near-zero-absolute-correlation gene pairs generated by fixed upstream preprocessing; labels are expression-derived and are not independent biochemical LR truth."},
            "limitations": ["The released requirements are internally incompatible: numpy 1.13.3 cannot support pandas 1.5.1, torch 1.6.0 does not match torchvision 0.11.1, and these builds are unavailable on current Apple ARM; the fixed source is run in a version-pinned audited compatibility environment.",
                "The source imports torchvision but never uses it; an empty import shim avoids introducing an unused incompatible dependency.",
                "The fixed source hard-codes seed 10 and ignores the configurable SEED field, so this runner preserves seed 10 and does not claim multi-seed stability.",
                "The repository example configuration points to missing test_pairs.csv and spatial_graph.csv files; this runner reconstructs both from declared inputs using fixed upstream rules.",
                "The paper describes an attentive graph encoder, while the released model code uses two unnormalized graph linear layers without an attention operation.",
                "The released R preprocessing computes a normalized matrix but writes raw supplied expression to model input; this runner preserves that behavior.",
                "spaCI candidate score has no permutation P value, FDR, donor uncertainty or condition-specific effect estimate.",
                "Cell-type strength is a post-prediction expression summary and does not localize individual sender-receiver cell events.",
                "A predicted association and spatial co-pattern do not establish ligand secretion, receptor activation, causality or therapeutic mechanism."]}, "tables": []}
    add_table(bundle, out, "spaci_cell_types", "spatial_points",
              [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=None, label=str(label)) for cell, (x, y), label in zip(data.obs_names, coordinates, celltypes)],
              "Supplied cell-type annotation for every spatial cell.", value_kind="category", title="spaCI spatial cell types", **spatial_meta)
    edge_rows = []
    upper = np.transpose(np.nonzero(np.triu(adjacency, 1)))
    for i, j in upper: edge_rows.append(dict(sample=sample, source_cell=str(data.obs_names[i]), target_cell=str(data.obs_names[j]), value=1.0))
    add_table(bundle, out, "spaci_spatial_graph", "spatial_edges", edge_rows,
              "Complete symmetric fixed-upstream K-nearest-neighbor union graph; value 1 denotes adjacency and not communication strength.",
              value_kind="count", directed=False, title="spaCI spatial graph", **spatial_meta)
    score_rows = []
    for (ligand, receptor), score, call in zip(candidates, pair_scores, predicted):
        raw_corr = float(np.corrcoef(matrix[:, gene_index[ligand]], matrix[:, gene_index[receptor]])[0, 1])
        for column, value in (("Latent cosine similarity", score), ("Predicted at configured threshold", float(call)), ("Raw expression correlation", raw_corr)):
            score_rows.append(dict(row=f"{ligand}→{receptor}", column=column, value=float(value)))
    add_table(bundle, out, "spaci_lr_scores", "matrix", score_rows,
              "Complete candidate LR latent cosine, binary configured-threshold call and raw expression Pearson correlation.",
              value_kind="native_score", figure_role="spaci_lr_scores", column_order=["Latent cosine similarity", "Predicted at configured threshold", "Raw expression correlation"], title="spaCI LR predictions")
    history_rows = [dict(row=str(x["epoch"]), column=column, value=float(x[column])) for x in history for column in ("loss", "F1")]
    add_table(bundle, out, "spaci_training_history", "matrix", history_rows,
              "Observed mean native triplet loss and expression-derived validation F1 at every training epoch.", value_kind="native_score",
              figure_role="spaci_training_history", column_order=["loss", "F1"], title="spaCI training history")
    add_table(bundle, out, "spaci_validation_metrics", "matrix",
              [dict(row="best checkpoint", column=name, value=float(value)) for name, value in final_metrics.items()],
              "Confusion counts and metrics at the best validation-F1 checkpoint and configured threshold; validation labels are expression-derived.",
              value_kind="native_score", figure_role="spaci_validation", row_order=["best checkpoint"], column_order=list(final_metrics), title="spaCI expression-derived validation")
    sensitivity_rows = []
    for cut in np.linspace(0.1, 0.9, 9):
        sensitivity_rows.append(dict(row=f"{cut:.1f}", column="Predicted LR pairs", value=float((pair_scores > cut).sum())))
    add_table(bundle, out, "spaci_threshold_sensitivity", "matrix", sensitivity_rows,
              "Number of complete candidate LR pairs exceeding each display-only cosine threshold; configured inference is unchanged.",
              value_kind="count", figure_role="spaci_threshold_sensitivity", column_order=["Predicted LR pairs"], title="spaCI threshold sensitivity")
    components = PCA(n_components=min(3, embedding.shape[0], embedding.shape[1]), svd_solver="full").fit_transform(embedding)
    if components.shape[1] < 3: components = np.pad(components, ((0, 0), (0, 3-components.shape[1])))
    ligand_set = {x[0] for x in candidates}; receptor_set = {x[1] for x in candidates}
    add_table(bundle, out, "spaci_gene_latent_space", "latent_points",
              [dict(entity=gene, domain="Ligand and receptor" if gene in ligand_set and gene in receptor_set else "Ligand" if gene in ligand_set else "Receptor", x=float(x), y=float(y), z=float(z)) for gene, (x, y, z) in zip(unique_genes, components)],
              "PCA projection of all fixed-upstream candidate-gene embeddings from the best checkpoint.", value_kind="native_score",
              figure_role="spaci_embedding", coordinate_unit="latent", space_definition="Post hoc PCA of complete fixed-upstream spaCI gene embeddings", title="spaCI candidate-gene latent space")
    lr_rows = []
    for (ligand, receptor), native_score, call in zip(candidates, pair_scores, predicted):
        for source in type_order:
            for target in type_order:
                strength = expression_means[(source, ligand)] * expression_means[(target, receptor)]
                lr_rows.append(dict(sample=sample, source=source, target=target, ligand=ligand, receptor=receptor,
                                    score=float(strength), tested=True, supported=bool(call and strength > 0), native_lr_score=float(native_score), pathway=""))
    add_table(bundle, out, "spaci_celltype_lr_strength", "lr_edges", lr_rows,
              "Paper-defined nonnegative cell-type LR strength for every globally scored candidate; supported requires the configured global spaCI call and positive endpoint product.",
              value_kind="nonnegative_strength", additive=True, directed=True, display_top_lr=12, display_top_cell_pairs=12,
              axis_label="Trimmed-mean ligand × receptor expression", title="spaCI cell-type communication strength")
    predicted_pairs = [(pair, score) for pair, score, call in zip(candidates, pair_scores, predicted) if call]
    predicted_pairs.sort(key=lambda x: (-x[1], x[0]))
    for (ligand, receptor), score in predicted_pairs[:integer(cfg.get("top_spatial_pairs", 3), "top_spatial_pairs", 1, 10)]:
        for gene, endpoint in ((ligand, "ligand"), (receptor, "receptor")):
            add_table(bundle, out, f"spaci_{safe_id(ligand)}_{safe_id(receptor)}_{endpoint}", "spatial_points",
                      [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=float(value)) for cell, (x, y), value in zip(data.obs_names, coordinates, matrix[:, gene_index[gene]])],
                      f"Complete supplied {endpoint} expression for globally predicted {ligand}–{receptor} (latent cosine {score:.6g}).",
                      value_kind="native_score", figure_role="spatial_hotspot", axis_label=f"{gene} ({cfg['expression_scale']})", title=f"{ligand}–{receptor}: {gene} {endpoint} expression", **spatial_meta)
    artifacts = {"prepared_input": "input.h5ad", "resource": "ligand_receptor_resource.tsv", "triplets": len(triplets),
                 "validation_pairs": len(validation), "candidate_lr_pairs": len(candidates), "predicted_lr_pairs": int(predicted.sum()),
                 "kept_correlation_genes": len(kept_genes), "correlation_high_cutoff": high, "absolute_correlation_low_cutoff": low,
                 "neighbors_including_self": k, "graph_undirected_edges_excluding_self": len(upper), "epochs": epochs,
                 "best_epoch": best_epoch, "best_validation_f1": best_f1, "seed": 10,
                 "compatibility": "fixed source, unused torchvision import shim, version-pinned modern ARM-compatible dependencies"}
    write_json(native / "native_artifacts.json", artifacts); write_json(out / "bundle.json", bundle)
    write_json(out / "run_state.json", {"schema_version": 2, "status": "complete", "bundle_sha256": digest(out / "bundle.json"),
               "runtime_seconds": time.time()-started, "analysis_tier": tier, **{k: artifacts[k] for k in ("triplets", "validation_pairs", "candidate_lr_pairs", "predicted_lr_pairs", "best_epoch", "best_validation_f1")}})
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--config", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try: return run(args.config, args.out)
    except Exception as error:
        out = Path(args.out).expanduser().resolve()
        if out.is_dir():
            state = json.loads((out / "run_state.json").read_text()) if (out / "run_state.json").is_file() else {"schema_version": 2}
            state.update(status="failed", error=str(error)); write_json(out / "run_state.json", state)
        raise


if __name__ == "__main__": sys.exit(main())
