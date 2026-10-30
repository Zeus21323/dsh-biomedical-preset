#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["ncem==0.1.5", "anndata==0.8.0", "numpy==1.24.4", "scipy==1.9.1", "pandas==1.5.3", "patsy==0.5.6", "diffxpy==0.7.4", "h5py==3.8.0"]
# ///
"""Run the fixed NCEM 0.1.5 linear neighborhood-effect model."""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import sys
import types

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial import cKDTree

from communication_contract import add_table, digest, new_output, write_json, write_table


UPSTREAM_COMMIT = "216fd576d1d1842234ceec300435a1dafcdf8b0c"
UPSTREAM_VERSION = "0.1.5"
SOURCE_HASHES = {
    "LICENSE": "c70b942b3e85ae316f9d457143a36c8b285417fb38ce994f0d0c985cdcf60769",
    "pyproject.toml": "4c695dd592141e636f8ba4b398f1f6d879778725df94dfefdf69c7fc1a0d81ae",
    "ncem/tl/fit/backend/linear_model.py": "7ce51dad0139bff64a9c07b961723f1dd5b13702e736c09ee5407ff3ed55d0d6",
    "ncem/tl/fit/backend/design_matrix.py": "573fec188ed3e5a05e608114a75589167d53de08be642fa6c56a2f6431d5ff8f",
    "ncem/tl/fit/backend/ols_fit.py": "4eefbbabebe2c3584db13729561710371c9e13337d83736342f7783059c610c0",
    "ncem/tl/fit/backend/testing.py": "56dda18fd16df0db0a80278e4aacfb81083266682e011925423374005fdfbe53",
    "ncem/utils/wald_test.py": "45134e3e7d6f156b0023364a3aa427a724f28dcaf0b9dd4cc09d946ae440ffe5",
    "ncem/pl/type_couplings.py": "fd6375b0b8f9c56a465044117f3bd5a5752d3f5e98fea40201e6638bbbba4e69",
    "ncem/tl/fit/backend/ablation.py": "5fa09b30df71ab4321039f8161b0941341e30716cbedb090816be77d1617bc22",
}
VERSIONS = {
    "ncem": UPSTREAM_VERSION,
    "numpy": "1.24.4",
    "scipy": "1.9.1",
    "pandas": "1.5.3",
    "anndata": "0.8.0",
    "patsy": "0.5.6",
    "diffxpy": "0.7.4",
    "h5py": "3.8.0",
}
PAIR = re.compile(r"^index_(.+):neighbor_(.+)$")


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def checked_integer(cfg, key, default, minimum, maximum=None):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        raise ValueError(f"{key} 必须是不小于 {minimum}" + (f"且不超过 {maximum}" if maximum is not None else "") + " 的整数")
    return value


def verify_native(root: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"NCEM 固定源码缺失或摘要不符: {relative}")
    actual_versions = {}
    for package, expected in VERSIONS.items():
        actual = importlib.metadata.version(package)
        if actual != expected:
            raise ValueError(f"NCEM 固定环境要求 {package}=={expected}，当前为 {actual}")
        actual_versions[package] = actual
    # The top-level package imports the historical TensorFlow stack even when
    # only the dependency-light, official GLM API is requested. Registering the
    # fixed source directory as the package namespace avoids that unrelated
    # import while executing the unmodified ncem.tl.fit backend files above.
    for name in list(sys.modules):
        if name == "ncem" or name.startswith("ncem."):
            del sys.modules[name]
    package = types.ModuleType("ncem")
    package.__path__ = [str(root / "ncem")]
    package.__version__ = UPSTREAM_VERSION
    sys.modules["ncem"] = package
    module = importlib.import_module("ncem.tl.fit.backend.linear_model")
    return module.linear_ncem, module.differential_ncem, actual_versions


def load_input(cfg, base: Path):
    required = (
        "dataset", "research_question", "input", "native_root", "input_provenance", "layer",
        "expression_scale", "normalization_definition", "coordinate_unit", "coordinate_provenance",
    )
    for key in required:
        if not cfg.get(key):
            raise ValueError("NCEM 配置缺少: " + key)
    if cfg["coordinate_unit"] not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if cfg["coordinate_unit"] == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
    if cfg["expression_scale"] not in ("normalized", "log_normalized", "transformed_continuous", "transformed_continuous_nonnegative"):
        raise ValueError("NCEM 需要有限的已规一化或明确变换后的表达/蛋白值")
    formula = cfg.get("formula", "~0")
    if not isinstance(formula, str) or not formula.startswith("~0") or "index_" in formula or "neighbor_" in formula:
        raise ValueError("formula 必须以 ~0 开头，不得手动加入 NCEM 自动生成的 index_/neighbor_ 项")
    path = resolve(base, cfg["input"])
    data = ad.read_h5ad(path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞和特征 ID 必须唯一")
    keys = {name: cfg.get(name + "_key", name) for name in ("sample", "donor", "condition", "cell_type")}
    model_type_key = cfg.get("model_cell_type_key", keys["cell_type"])
    for key in (*keys.values(), model_type_key):
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
        data.obs[key] = data.obs[key].astype(str)
    for sample, frame in data.obs.groupby(keys["sample"], observed=True):
        if frame[keys["donor"]].nunique() != 1 or frame[keys["condition"]].nunique() != 1:
            raise ValueError(f"样本 {sample} 不唯一对应供体/条件")
    mapping = data.obs[[model_type_key, keys["cell_type"]]].drop_duplicates()
    if mapping[model_type_key].duplicated().any() or mapping[keys["cell_type"]].duplicated().any():
        raise ValueError("建模细胞类型与展示名必须一对一")
    if not mapping[model_type_key].str.fullmatch(r"[A-Za-z][A-Za-z0-9_]*").all():
        raise ValueError("建模细胞类型必须是 Patsy 安全名；保留独立展示名列")
    layer = cfg["layer"]
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError("配置的表达层不存在")
    maximum_dense = checked_integer(cfg, "maximum_dense_elements", 25_000_000, 1)
    if data.n_obs * data.n_vars > maximum_dense:
        raise ValueError("NCEM 线性拟合输出是稠密特征矩阵，输入超过 maximum_dense_elements")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != data.shape or not np.isfinite(matrix).all():
        raise ValueError("表达/蛋白矩阵必须有限且与细胞、特征严格对齐")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("NCEM 需要与细胞逐行对齐的有限二维坐标")
    radius = float(cfg.get("radius", 0))
    if not np.isfinite(radius) or radius <= 0:
        raise ValueError("radius 必须是已定义坐标单位下的有限正数")
    data.X = matrix
    return data, coordinates, keys, model_type_key, mapping, formula, radius, path


def build_graph(data, coordinates, sample_key, radius, maximum_edges):
    row_parts, column_parts, degree_rows = [], [], []
    total_pairs = 0
    samples = list(dict.fromkeys(data.obs[sample_key].tolist()))
    for sample in samples:
        indices = np.flatnonzero(data.obs[sample_key].to_numpy() == sample)
        if len(np.unique(coordinates[indices], axis=0)) != len(indices):
            raise ValueError(f"样本 {sample} 存在重复坐标，需核查细胞分割身份")
        pairs = cKDTree(coordinates[indices]).query_pairs(radius, output_type="ndarray")
        total_pairs += len(pairs)
        if total_pairs * 2 > maximum_edges:
            raise ValueError("NCEM 半径图超过 maximum_graph_edges，需核实坐标单位/半径，不自动抽边")
        if len(pairs):
            left, right = indices[pairs[:, 0]], indices[pairs[:, 1]]
            row_parts.extend((left, right)); column_parts.extend((right, left))
            degree = np.bincount(np.r_[pairs[:, 0], pairs[:, 1]], minlength=len(indices))
        else:
            degree = np.zeros(len(indices), dtype=int)
        degree_rows.append(dict(sample=sample, n_cells=len(indices), undirected_edges=len(pairs),
                                mean_degree=float(degree.mean()), median_degree=float(np.median(degree)),
                                zero_neighbor_fraction=float(np.mean(degree == 0))))
    rows = np.concatenate(row_parts) if row_parts else np.array([], dtype=int)
    columns = np.concatenate(column_parts) if column_parts else np.array([], dtype=int)
    graph = sparse.csr_matrix((np.ones(len(rows), dtype=np.float32), (rows, columns)), shape=(data.n_obs, data.n_obs))
    graph.setdiag(0); graph.eliminate_zeros()
    return graph, degree_rows


def bh(values):
    flat = np.asarray(values, dtype=float).ravel()
    order = np.argsort(flat, kind="mergesort")
    ranked = flat[order]
    adjusted = np.minimum.accumulate((ranked * len(flat) / np.arange(1, len(flat) + 1))[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.minimum(adjusted, 1)
    return result.reshape(np.asarray(values).shape)


def parse_pairs(columns, display_by_model):
    pairs = []
    for column in columns:
        match = PAIR.fullmatch(str(column))
        if not match or match.group(1) not in display_by_model or match.group(2) not in display_by_model:
            raise ValueError(f"NCEM 原生系数名变化或无展示映射: {column}")
        pairs.append((display_by_model[match.group(1)], display_by_model[match.group(2)]))
    return pairs


def output_effect_family(bundle, output_root, identifier, genes, pairs, beta, pvals, native_q, qvals,
                         presence_counts, alpha, definition, contrast, differential=False):
    rows = []
    for gene_index, gene in enumerate(genes):
        for pair_index, (receiver, sender) in enumerate(pairs):
            n_reference, n_comparison = presence_counts[(receiver, sender)]
            value = float(beta[gene_index, pair_index])
            rows.append({
                "feature": f"{receiver} ← {sender} | {gene}", "value": value,
                "p_value": float(pvals[gene_index, pair_index]), "q_value": float(qvals[gene_index, pair_index]),
                "native_q_value": float(native_q[gene_index, pair_index]),
                "n_reference": n_reference, "n_comparison": n_comparison,
                "supported": bool(qvals[gene_index, pair_index] <= alpha),
                "receiver": receiver, "sender": sender, "gene": gene,
            })
    add_table(bundle, output_root, identifier, "effect_summary", rows, definition,
              value_kind="native_score", figure_role="neighborhood", contrast=contrast,
              statistical_unit="cells in the fixed spatial graph; donor/image dependence is not removed by the native Wald test",
              test_definition="NCEM 0.1.5 native Wald P values; globally aligned BH across every modeled gene and sender–receiver coefficient",
              alpha=alpha, differential=differential, axis_label="NCEM neighborhood coefficient",
              q_plot_floor=1e-50)
    return rows


def add_receiver_matrices(bundle, output_root, prefix, effect_rows, alpha, limit):
    frame = pd.DataFrame(effect_rows)
    receivers = sorted(frame["receiver"].unique())
    ranking = []
    for receiver in receivers:
        part = frame[frame["receiver"] == receiver]
        ranking.append((int((part["q_value"] <= alpha).sum()), float(part["value"].abs().sum()), receiver))
    chosen = [item[2] for item in sorted(ranking, key=lambda x: (-x[0], -x[1], x[2]))[:limit]]
    selection = []
    for order, receiver in enumerate(chosen, 1):
        part = frame[frame["receiver"] == receiver]
        genes = list(dict.fromkeys(part.sort_values(["q_value", "gene"])["gene"]))
        effects = [dict(row=row.gene, column=row.sender, value=float(row.value)) for row in part.itertuples(index=False)]
        evidence = [dict(row=row.gene, column=row.sender, value=float(-math.log10(max(row.q_value, 1e-300)))) for row in part.itertuples(index=False)]
        add_table(bundle, output_root, f"{prefix}_receiver_{order}_effects", "matrix", effects,
                  f"接收类型 {receiver} 中，某发送类型出现在固定半径邻域时的 NCEM 原生基因/蛋白线性系数；正负号保留。",
                  value_kind="native_score", additive=False, axis_label="NCEM coefficient",
                  title=f"Receiver: {receiver}", row_order=genes, display_top_rows=min(22, len(genes)))
        add_table(bundle, output_root, f"{prefix}_receiver_{order}_evidence", "matrix", evidence,
                  f"接收类型 {receiver} 的全候选全局 BH 证据转为 −log10(q)；只为显示转换，原始 P/q 在完整效应表。",
                  value_kind="nonnegative_strength", additive=False, axis_label="−log10(global BH q)",
                  title=f"Adjusted evidence; receiver: {receiver}", row_order=genes, display_top_rows=min(22, len(genes)),
                  display_cap=50.0)
        senders = sorted(part["sender"].unique())
        vectors = np.vstack([part[part["sender"] == sender].set_index("gene").loc[genes, "value"].to_numpy() for sender in senders])
        correlations = np.corrcoef(vectors)
        correlation_rows = [dict(row=a, column=b, value=None if not np.isfinite(correlations[i, j]) else float(correlations[i, j]))
                            for i, a in enumerate(senders) for j, b in enumerate(senders)]
        add_table(bundle, output_root, f"{prefix}_receiver_{order}_sender_similarity", "matrix", correlation_rows,
                  f"接收类型 {receiver} 下，各发送类型的完整 NCEM 系数向量在全部建模基因/蛋白间的 Pearson 相关；这是作者 sender-similarity 逻辑，不是配体–受体共享。",
                  value_kind="native_score", additive=False, axis_label="Pearson correlation of coefficient vectors",
                  figure_role="sender_similarity", title=f"Sender similarity; receiver: {receiver}",
                  row_order=senders, column_order=senders)
        selection.append(dict(receiver=receiver, significant_gene_pair_coefficients=int((part["q_value"] <= alpha).sum()),
                              total_coefficients=len(part)))
    return selection


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    base = config.parent
    native_root = resolve(base, cfg.get("native_root", ""))
    linear_ncem, differential_ncem, versions = verify_native(native_root)
    data, coordinates, keys, model_type_key, mapping, formula, radius, input_path = load_input(cfg, base)
    mode = cfg.get("mode", "standard")
    if mode not in ("standard", "differential"):
        raise ValueError("mode 只接受 standard 或 differential")
    if mode == "differential":
        counts = data.obs.groupby(keys["condition"], observed=True)[keys["donor"]].nunique()
        if len(counts) < 2 or (counts < 2).any():
            raise ValueError("差异 NCEM 每条件至少需两个真实供体")
        if not cfg.get("acknowledge_cell_level_differential"):
            raise ValueError("原生差异 NCEM 是细胞层 OLS/Wald，不建模供体内相关；只有明确 acknowledge_cell_level_differential=true 才执行")
    maximum_edges = checked_integer(cfg, "maximum_graph_edges", 20_000_000, 1)
    graph, degree_rows = build_graph(data, coordinates, keys["sample"], radius, maximum_edges)
    data.obsp["ncem_graph"] = graph
    types = sorted(data.obs[model_type_key].unique())
    estimated_columns = len(types) ** 2 + len(types) + max(0, data.obs[keys["sample"]].nunique() - (0 if formula.startswith("~0") else 1))
    maximum_design = checked_integer(cfg, "maximum_design_elements", 50_000_000, 1)
    if data.n_obs * estimated_columns > maximum_design:
        raise ValueError("NCEM 预计设计矩阵超过 maximum_design_elements，不自动删除细胞类型或样本协变量")
    output_root = new_output(output)
    write_json(output_root / "run_config.json", cfg)
    state = {"status": "running", "mode": mode, "signature": digest(input_path) + ":" + digest(config) + ":" + UPSTREAM_COMMIT}
    write_json(output_root / "run_state.json", state)
    if mode == "standard":
        result = linear_ncem(data, key_type=model_type_key, key_graph="ncem_graph", formula=formula,
                             type_specific_confounders=cfg.get("type_specific_confounders", []))
    else:
        result = differential_ncem(data, key_differential=keys["condition"], key_graph="ncem_graph",
                                   key_type=model_type_key, formula=formula,
                                   type_specific_confounders=cfg.get("type_specific_confounders", []))
    display_by_model = dict(zip(mapping[model_type_key], mapping[keys["cell_type"]]))
    pvals_frame = result.varm["ncem_pvals"]
    pairs = parse_pairs(pvals_frame.columns, display_by_model)
    beta = np.asarray(result.varm["ncem_tested_params"], dtype=float)
    pvals = np.asarray(pvals_frame, dtype=float)
    native_q = np.asarray(result.varm["ncem_fdr_pvals"], dtype=float)
    qvals = bh(pvals)
    if beta.shape != pvals.shape or native_q.shape != pvals.shape or not np.isfinite(beta).all() or not np.isfinite(pvals).all():
        raise ValueError("NCEM 原生系数/P/q 结构或数值无效")
    onehot = pd.get_dummies(data.obs[model_type_key]).reindex(columns=types).to_numpy(dtype=float)
    presence = np.asarray(graph.dot(onehot) > 0)
    presence_counts = {}
    for receiver_model, receiver in display_by_model.items():
        receiver_mask = data.obs[model_type_key].to_numpy() == receiver_model
        for sender_index, sender_model in enumerate(types):
            values = presence[receiver_mask, sender_index]
            presence_counts[(receiver, display_by_model[sender_model])] = (int((~values).sum()), int(values.sum()))
    alpha = float(cfg.get("alpha", 0.05))
    if not 0 < alpha < 1:
        raise ValueError("alpha 必须在 (0,1)")
    bundle = {
        "schema_version": 2,
        "dataset": cfg["dataset"],
        "method": "NCEM",
        "method_version": UPSTREAM_VERSION,
        "implementation": "native",
        "figure_inapplicability": {
            "lr_evidence": "线性 NCEM 检验邻域细胞类型与接收细胞基因/蛋白的统计依赖，不评分具体配体–受体。",
            "roles": "NCEM 类型耦合是邻域系数汇总，不提供基于可加通讯流的中心性角色。",
            "cellchat_patterns": "NCEM 不执行 CellChat NMF 模式。",
            "pathway_sankey": "NCEM 系数没有单一通路归属或守恒流量。",
            "ligand_response": "本入口的线性 NCEM 不使用配体–受体图核，不给出配体活性。",
            "intracellular": "NCEM 不重建 LR–TF–target 机制链。",
            "factors": "线性 NCEM 不输出张量/NMF 因子。",
            "enrichment": "NCEM 本身不执行有背景集的基因集富集。",
            "embedding": "线性 NCEM 不学习可展示的细胞潜在嵌入。",
            "spatial_hotspots": "NCEM 估计全数据级邻域系数，不输出逐细胞局部作用强度。",
            "spatial_direction": "NCEM 的方向是发送邻域类型→接收类型的模型身份，不是空间速度向量。",
            "relay_dynamic": "NCEM 不建模时间、轨迹或多跳传递。",
            "special_molecules": "线性 NCEM 没有代谢物/递质专用资源与分子模型。",
            "functional_clinical": "NCEM 原生输出不包含功能、药敏或临床结局关联。",
        },
        "provenance": {
            "input_sha256": digest(input_path), "parameters": cfg,
            "coordinate_provenance": cfg["coordinate_provenance"],
            "upstream": {"url": "https://github.com/theislab/ncem", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "license": "BSD-3-Clause"},
            "source_sha256": SOURCE_HASHES, "versions": versions,
            "statistical_semantics": {
                "graph": "Undirected within-sample radius graph with diagonal removed. Sender presence is binary within each receiver cell's niche, exactly as get_obs_niche_from_graph(..., marginalisation='binary').",
                "coefficient": "Directional receiver-specific association: the change in a modeled gene/protein for a receiver cell type when a sender cell type is present in its radius-defined niche, conditional on the declared formula.",
                "native_test": "NCEM 0.1.5 Wald P values use the package Fisher-information approximation and treat cells as observations.",
                "fdr": "The upstream test_standard reshapes its globally corrected vector in an order inconsistent with the labeled P-value matrix. native_q_value preserves that output; q_value is a globally aligned BH recomputation from the complete labeled native P matrix and is used for support.",
                "statistical_unit": "Cells in spatial images. Multiple cells from one donor are not independent donor replicates; standard-mode P/q values do not establish donor-level condition specificity.",
            },
            "limitations": [
                "The fixed NCEM package imports TensorFlow from its top-level namespace even for GLM-only use. The adapter executes the unmodified dependency-light ncem.tl.fit backend from the verified source tree and does not claim to run neural NCEM variants.",
                "Cell-type neighborhood coefficients can reflect co-localization, omitted tissue structure or technical batch effects; they are not direct molecular flux or causal signaling.",
                "Native Wald inference is cell-level. Publication claims about disease or treatment require donor-aware replication outside this test, even when sample/domain terms are present in the mean model.",
            ],
        },
        "tables": [],
    }
    effects = output_effect_family(
        bundle, output_root, "ncem_neighborhood_gene_effects", list(map(str, result.var_names)), pairs,
        beta, pvals, native_q, qvals, presence_counts, alpha,
        "NCEM 0.1.5 原生接收类型×邻域发送类型线性系数和 Wald P；q_value 为在完整已标记 P 矩阵上对齐重算的全局 BH，native_q_value 原样保留上游错位输出。",
        "Sender present versus absent in the receiver niche",
    )
    receiver_selection = add_receiver_matrices(bundle, output_root, "ncem", effects, alpha,
                                                checked_integer(cfg, "top_receiver_heatmaps", len(types), 1, len(types)))
    count_rows = []
    for receiver, sender in pairs:
        selected = [row for row in effects if row["receiver"] == receiver and row["sender"] == sender and row["q_value"] <= alpha]
        count_rows.append(dict(source=sender, target=receiver, value=len(selected)))
    if any(row["value"] > 0 for row in count_rows):
        add_table(bundle, output_root, "ncem_supported_gene_counts", "network", count_rows,
                  "每条有向边为该发送邻域类型→接收类型下全局 BH q≤alpha 的建模基因/蛋白数量；边宽是数量，不是分子流量。",
                  value_kind="count", additive=True, directed=True, axis_label="Supported modeled features")
    else:
        zero_matrix = [dict(row=row["source"], column=row["target"], value=0) for row in count_rows]
        add_table(bundle, output_root, "ncem_supported_gene_counts", "matrix", zero_matrix,
                  "完整候选中没有全局 BH q≤alpha 的邻域系数；0 是真实阴性结果，不生成支持网络。",
                  value_kind="count", additive=True, axis_label="Supported modeled features")
    degree_frame = pd.DataFrame(degree_rows).merge(data.obs[[keys["sample"], keys["donor"], keys["condition"]]].drop_duplicates(),
                                                   left_on="sample", right_on=keys["sample"], how="left", validate="one_to_one")
    degree_effects = []
    for (donor, condition), part in degree_frame.groupby([keys["donor"], keys["condition"]], sort=True):
        degree_effects.append(dict(sample=";".join(part["sample"]), donor=donor, condition=condition,
                                   feature=f"Mean neighbors within {radius:g} {cfg['coordinate_unit']}",
                                   value=float(np.average(part["mean_degree"], weights=part["n_cells"])), n_images=len(part)))
    add_table(bundle, output_root, "ncem_graph_degree_by_donor", "effects", degree_effects,
              "供体内按细胞数加权的固定半径平均邻居数；只是图结构质控，不是通讯强度，不计算条件显著性。",
              value_kind="nonnegative_strength", nonnegative=True, axis_label="Mean graph degree")
    maximum_maps = checked_integer(cfg, "spatial_context_samples", min(4, data.obs[keys["donor"]].nunique()), 0, 12)
    if maximum_maps:
        sample_sizes = data.obs.groupby([keys["donor"], keys["sample"]], observed=True).size().reset_index(name="n")
        chosen_samples = sample_sizes.sort_values([keys["donor"], "n", keys["sample"]], ascending=[True, False, True]).groupby(keys["donor"], sort=True).head(1)[keys["sample"]].tolist()[:maximum_maps]
        spatial_rows = []
        display_types = data.obs[keys["cell_type"]].to_numpy()
        samples_array = data.obs[keys["sample"]].to_numpy()
        for index in np.flatnonzero(np.isin(samples_array, chosen_samples)):
            spatial_rows.append(dict(sample=samples_array[index], cell=str(data.obs_names[index]),
                                     x=float(coordinates[index, 0]), y=float(coordinates[index, 1]), value=None,
                                     label=display_types[index]))
        add_table(bundle, output_root, "ncem_input_cell_type_maps", "spatial_points", spatial_rows,
                  "每个供体选细胞数最多的一个图像，显示原始细胞类型和真实坐标作为 NCEM 输入背景；不是局部系数或显著性图。",
                  value_kind="native_score", coordinate_unit=cfg["coordinate_unit"],
                  physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable", False)),
                  coordinate_provenance=cfg["coordinate_provenance"], y_down=bool(cfg.get("y_down", False)))
    if mode == "differential":
        diff_p_frame = result.varm["differential_ncem_pvals"]
        diff_pairs = parse_pairs(diff_p_frame.columns, display_by_model)
        diff_beta = np.asarray(result.varm["differential_ncem_tested_params"], dtype=float)
        diff_p = np.asarray(diff_p_frame, dtype=float)
        diff_native_q = np.asarray(result.varm["differential_ncem_fdr_pvals"], dtype=float)
        diff_q = bh(diff_p)
        # NCEM stores all fit metadata below .uns["ncem"]. Keep this
        # namespace boundary explicit so a successful native fit cannot be
        # mistaken for a missing condition contrast during export.
        conditions = list(map(str, result.uns["ncem"]["conditions"]))
        reference = sorted(data.obs[keys["condition"]].unique())[0]
        comparison = ",".join(conditions)
        diff_effects = output_effect_family(
            bundle, output_root, "ncem_differential_neighborhood_effects", list(map(str, result.var_names)), diff_pairs,
            diff_beta, diff_p, diff_native_q, diff_q, presence_counts, alpha,
            "原生 differential NCEM 条件×接收类型×邻域发送类型系数和 Wald P；q_value 为在完整已标记 P 矩阵上对齐重算的全局 BH。",
            f"{comparison} versus reference {reference}; native cell-level differential NCEM", differential=True,
        )
        receiver_selection.extend(add_receiver_matrices(bundle, output_root, "ncem_differential", diff_effects, alpha,
                                                         checked_integer(cfg, "top_receiver_heatmaps", len(types), 1, len(types))))
    write_table(output_root / "graph_degree_by_sample.tsv", degree_rows)
    native_object = output_root / "ncem_native_result.h5ad"
    if cfg.get("save_native_object", True):
        # NCEM 0.1.5 stores tested coefficients with integer DataFrame
        # columns although the paired P-value table retains coefficient names.
        # AnnData 0.8 refuses integer column keys on serialization. Restore the
        # one-to-one native names without modifying values.
        result.varm["ncem_tested_params"].columns = list(map(str, result.varm["ncem_pvals"].columns))
        if mode == "differential":
            result.varm["differential_ncem_tested_params"].columns = list(
                map(str, result.varm["differential_ncem_pvals"].columns)
            )
            # The native function stores a pandas Index in .uns, which
            # AnnData 0.8 cannot serialize. Preserve the same ordered labels
            # as a plain string array for the native artifact.
            result.uns["ncem"]["conditions"] = np.asarray(
                list(map(str, result.uns["ncem"]["conditions"])), dtype=str
            )
        result.write_h5ad(native_object)
    native_q_difference = int(np.sum(~np.isclose(native_q, qvals, atol=1e-15, rtol=0)))
    audit = {
        "native_q_alignment_difference_count": native_q_difference,
        "candidate_coefficients": int(pvals.size),
        "supported_coefficients_global_bh": int(np.sum(qvals <= alpha)),
        "directed_graph_edges": int(graph.nnz),
        "receiver_selection": receiver_selection,
        "native_object": native_object.name if native_object.exists() else None,
        "native_object_sha256": digest(native_object) if native_object.exists() else None,
    }
    write_json(output_root / "native_artifacts.json", audit)
    state.update(status="complete", bundle_sha256=None, **audit)
    write_json(output_root / "bundle.json", bundle)
    state["bundle_sha256"] = digest(output_root / "bundle.json")
    write_json(output_root / "run_state.json", state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.config, arguments.out))
