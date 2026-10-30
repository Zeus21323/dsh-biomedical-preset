#!/usr/bin/env python3
# /// script
# requires-python = "==3.10.20"
# dependencies = ["numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "scikit-learn==1.4.1.post1", "torch==1.13.1", "scanpy==1.9.8", "anndata==0.10.6", "plotly==5.20.0"]
# ///
"""Run fixed DeepCOLOR mapping, colocalization, pair clustering and ligand activity."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import random
import re
import subprocess
import sys
import warnings
from pathlib import Path

sys.dont_write_bytecode = True
import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
import torch
from scipy import sparse

from communication_contract import add_table, digest, new_output, write_json


COMMIT = "7400a2aefb55045f596446f24d5b1df550474c5d"
SOURCE_HASHES = {
    "src/deepcolor/workflow.py": "fedb7e4c2b430017b9f51b55cbfeb80e528a9a6f2354b98940ceae1d55f6729d",
    "src/deepcolor/commons.py": "4f437451e04cd49cb5e1af0472da69a40aeb11ec72f11da988d22e5bac7af180",
    "src/deepcolor/exp.py": "3310c3ca27090e35605d7874e37af9d4792b907d3809f4d61d63c7e0ff4dc559",
    "src/deepcolor/modules.py": "32e2c199da30f85e9618acde39351ae0451a1a18a0091712f8e789654fe3a9ad",
    "src/deepcolor/dataset.py": "26bce11cbf812dbeea07feb463c8a91fe2e637bc32f4fd1c698ed6eea3dee478",
    "src/deepcolor/funcs.py": "d8aae11aa46ed58e232f18bcdf81b3530eaa933ddebddf8a7db6bf1813623531",
}
VERSIONS = {
    "numpy": "1.26.4", "pandas": "2.2.1", "scipy": "1.12.0",
    "scikit-learn": "1.4.1.post1", "torch": "1.13.1",
    "scanpy": "1.9.8", "anndata": "0.10.6", "plotly": "5.20.0",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def verify_source(root: Path):
    if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != COMMIT:
        raise ValueError("DeepCOLOR固定源码提交不符")
    for name, expected in SOURCE_HASHES.items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"DeepCOLOR固定源码缺失或摘要不符: {name}")
    if sys.version_info[:3] != (3, 10, 20):
        raise ValueError("DeepCOLOR兼容环境固定为Python 3.10.20")
    observed = {name: importlib.metadata.version(name) for name in VERSIONS}
    if observed != VERSIONS:
        raise ValueError(f"DeepCOLOR兼容依赖版本不符: {observed}")
    sys.path.insert(0, str(root / "src"))
    import deepcolor.workflow as workflow
    return workflow, observed


def raw_counts(adata: ad.AnnData, layer: str, label: str) -> np.ndarray:
    if layer not in adata.layers:
        raise ValueError(f"{label}缺少原始计数层: {layer}")
    values = adata.layers[layer].toarray() if sparse.issparse(adata.layers[layer]) else np.asarray(adata.layers[layer])
    if values.ndim != 2 or not np.isfinite(values).all() or (values < 0).any() or not np.all(values == np.floor(values)):
        raise ValueError(f"{label}的{layer}必须是有限、非负整数原始计数；不接受上游仅打印警告后继续")
    if np.any(values.sum(axis=1) <= 0):
        raise ValueError(f"{label}存在零文库单元")
    return values.astype(np.float32, copy=False)


def seed_all(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)


def ordered_group_matrix(values: np.ndarray, groups: np.ndarray, labels: list[str], diagonal: bool = True):
    rows = []
    for source in labels:
        si = np.flatnonzero(groups == source)
        for target in labels:
            ti = np.flatnonzero(groups == target)
            block = values[np.ix_(si, ti)]
            if not diagonal and source == target:
                block = block[~np.eye(len(si), dtype=bool)]
            rows.append(dict(row=source, column=target, value=float(block.mean()) if block.size else 0.0))
    return rows


def run(config_path: str, output_path: str) -> int:
    config_path = Path(config_path).resolve(); cfg = json.loads(config_path.read_text()); base = config_path.parent
    required = ("dataset", "research_question", "single_cell_input", "spatial_input", "native_root",
                "celltype_label", "input_provenance", "coordinate_provenance", "coordinate_unit",
                "resolution", "normalization_definition")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("DeepCOLOR配置缺少: " + key)
    if cfg["resolution"] != "spot":
        raise ValueError("DeepCOLOR空间输入必须明确为spot；输出不能称单细胞原位定位")
    if cfg["coordinate_unit"] not in ("pixel", "um", "native"):
        raise ValueError("DeepCOLOR坐标单位无效")
    if cfg["coordinate_unit"] == "native" and cfg.get("physical_scale_unavailable") is not True:
        raise ValueError("native坐标必须声明物理比例不可用")
    paths = {key: resolve(base, cfg[key]) for key in ("single_cell_input", "spatial_input", "native_root")}
    if any(not path.exists() for path in paths.values()):
        raise FileNotFoundError("DeepCOLOR输入或固定源码不存在")
    workflow, versions = verify_source(paths["native_root"])
    seed = cfg.get("seed", 20260910)
    if type(seed) is not int:
        raise ValueError("seed必须为整数")
    seed_all(seed)
    single = ad.read_h5ad(paths["single_cell_input"]); spatial = ad.read_h5ad(paths["spatial_input"])
    label = cfg["celltype_label"]; layer = cfg.get("count_layer", "count"); coordinate_key = cfg.get("spatial_key", "spatial")
    if label not in single.obs or single.obs[label].isna().any() or single.obs_names.has_duplicates:
        raise ValueError("单细胞类型标签缺失、为空或细胞身份重复")
    if spatial.obs_names.has_duplicates or single.var_names.has_duplicates or spatial.var_names.has_duplicates:
        raise ValueError("DeepCOLOR细胞、spot或基因身份重复")
    if single.var_names.tolist() != spatial.var_names.tolist():
        raise ValueError("DeepCOLOR要求单细胞和空间输入基因完全同序；适配器不静默取交集")
    sc_counts = raw_counts(single, layer, "单细胞输入"); sp_counts = raw_counts(spatial, layer, "空间输入")
    single.X = sc_counts; spatial.X = sp_counts; single.layers[layer] = sc_counts; spatial.layers[layer] = sp_counts
    if coordinate_key not in spatial.obsm or np.asarray(spatial.obsm[coordinate_key]).shape != (spatial.n_obs, 2):
        raise ValueError("空间输入缺少同spot二维真实坐标")
    coordinates = np.asarray(spatial.obsm[coordinate_key], dtype=float)
    if not np.isfinite(coordinates).all():
        raise ValueError("空间坐标含非有限值")
    max_bytes = cfg.get("max_working_bytes", 2**31)
    estimate = 4 * (single.n_obs * single.n_vars + spatial.n_obs * single.n_vars + 4 * single.n_obs * spatial.n_obs + single.n_obs**2)
    if type(max_bytes) is not int or max_bytes < estimate:
        raise ValueError(f"DeepCOLOR预估工作内存{estimate}字节超过显式上限；不静默抽样")
    first_epoch, second_epoch = cfg.get("first_epoch", 500), cfg.get("second_epoch", 500)
    if any(type(x) is not int or x < 1 for x in (first_epoch, second_epoch)):
        raise ValueError("两阶段epoch必须为正整数")
    model_params = cfg.get("model_params", {"x_dim": single.n_vars, "s_dim": single.n_vars, "xz_dim": 10, "sz_dim": 10,
        "enc_z_h_dim": 50, "dec_z_h_dim": 50, "map_h_dim": 50, "num_enc_z_layers": 2, "num_dec_z_layers": 2})
    out = new_output(output_path); write_json(out / "run_config.json", cfg)
    params_path = out / "deepcolor_parameters.pt"
    with (out / "native_training.log").open("x") as native_log, warnings.catch_warnings(record=True) as native_warnings:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(native_log), contextlib.redirect_stderr(native_log):
            single, spatial = workflow.estimate_spatial_distribution(
                single, spatial, str(params_path), layer_name=layer, first_epoch=first_epoch, second_epoch=second_epoch,
                lr=float(cfg.get("learning_rate", .001)), val_ratio=float(cfg.get("validation_ratio", .05)),
                test_ratio=float(cfg.get("test_ratio", .05)), device="cpu", num_workers=0,
                x_batch_size=min(cfg.get("single_cell_batch_size", 128), single.n_obs),
                s_batch_size=min(cfg.get("spatial_batch_size", 64), spatial.n_obs),
                use_poisson=bool(cfg.get("use_poisson", False)), model_params=model_params.copy(), batch_label=None)
    write_json(out / "native_warnings.json", [str(item.message) for item in native_warnings])
    training_rows=[];stage=None
    for line in (out / "native_training.log").read_text().splitlines():
        if line == "Start first opt":stage="Single-cell phase"
        elif line == "Start second opt":stage="Spatial phase"
        else:
            match=re.fullmatch(r"loss at epoch (\d+) is (.+)",line)
            if match and stage:
                value=float(match.group(2))
                if not np.isfinite(value):raise ValueError("DeepCOLOR验证损失非有限")
                training_rows.append(dict(row=match.group(1),column=stage,value=value))
    single = workflow.estimate_colocalization(single)
    mapping = np.asarray(single.obsm["map2sp"], dtype=float); probabilities = np.asarray(single.obsm["p_mat"], dtype=float)
    colocalization = np.asarray(single.obsp["colocalization"], dtype=float)
    if mapping.shape != (single.n_obs, spatial.n_obs) or probabilities.shape != mapping.shape or colocalization.shape != (single.n_obs, single.n_obs):
        raise ValueError("DeepCOLOR原生输出维度错误")
    if not all(np.isfinite(x).all() for x in (mapping, probabilities, colocalization)) or (mapping < 0).any() or (probabilities < 0).any():
        raise ValueError("DeepCOLOR原生映射含负值或非有限值")
    row_error = float(np.max(np.abs(probabilities.sum(axis=1) - 1)))
    if row_error > 1e-6:
        raise ValueError(f"DeepCOLOR归一化单细胞空间分布行和错误: {row_error}")
    spot_cell_weights = mapping.T
    spot_sum_error = float(np.max(np.abs(spot_cell_weights.sum(axis=1) - 1)))
    if spot_sum_error > 1e-5:
        raise ValueError(f"DeepCOLOR原生spot细胞权重和错误: {spot_sum_error}")
    np.savez_compressed(out / "deepcolor_complete_arrays.npz", map2sp=mapping, p_mat=probabilities,
                        colocalization=colocalization, latent=np.asarray(single.obsm["X_zl"]),
                        cell_ids=np.asarray(single.obs_names,dtype=str), spot_ids=np.asarray(spatial.obs_names,dtype=str))
    single.write_h5ad(out / "deepcolor_single_cell_mapped.h5ad"); spatial.write_h5ad(out / "deepcolor_spatial_mapped.h5ad")
    groups = single.obs[label].astype(str).to_numpy(); labels = sorted(set(groups))
    bundle = dict(schema_version=2, dataset=cfg["dataset"], method="DeepCOLOR", method_version="0.0.6 fixed source",
                  implementation="native_mapping_colocalization_and_optional_nichenet_ligand_activity", tables=[],
                  provenance=dict(input_provenance=cfg["input_provenance"], coordinate_provenance=cfg["coordinate_provenance"],
                      normalization_definition=cfg["normalization_definition"], upstream=dict(url="https://github.com/kojikoji/deepcolor", commit=COMMIT, license="MIT"),
                      source_hashes=SOURCE_HASHES, input_hashes={key: digest(path) for key, path in paths.items() if path.is_file()}, versions=versions,
                      parameters=dict(seed=seed, first_epoch=first_epoch, second_epoch=second_epoch, learning_rate=cfg.get("learning_rate", .001),
                          model_params=model_params, device="cpu", deterministic_algorithms=True, count_layer=layer),
                      complete_arrays=dict(path="deepcolor_complete_arrays.npz", sha256=digest(out / "deepcolor_complete_arrays.npz")),
                      mapped_objects={name: digest(out / name) for name in ("deepcolor_single_cell_mapped.h5ad", "deepcolor_spatial_mapped.h5ad")},
                      native_log=dict(path="native_training.log", sha256=digest(out / "native_training.log")),
                      native_warnings=dict(path="native_warnings.json", sha256=digest(out / "native_warnings.json")),
                      limitations=[
                          "DeepCOLOR推断的是单细胞转录组在spot上的概率分布与共定位，不是直接观测的细胞位置、配体结合或因果通讯。",
                          "原生映射每个spot上的细胞权重和为1；单细胞p_mat另按行归一化，两种归一化回答不同问题。",
                          "共定位为log2(p_i·p_j)+log2(n_spots)，阈值1是上游固定描述性阈值，没有P值或FDR。",
                          "配体通讯层使用NicheNet配体—靶基因调控潜力和表达排序，不含受体结合检验；coactivity是布尔顶部分位数的计数。",
                          "单患者单切片没有供体层条件检验，不能证明疾病或数据集特异性。",
                          "作者Linux/CUDA精确环境不能在本机arm64复原；这里使用固定兼容环境，需报告平台敏感性。",
                      ]))
    cluster_weights = {cell_type: spot_cell_weights[:, groups == cell_type].sum(axis=1) for cell_type in labels}
    for cell_type in labels:
        add_table(bundle, out, "spatial_abundance_" + hashlib.sha1(cell_type.encode()).hexdigest()[:10], "spatial_points",
                  [dict(sample=cfg["dataset"], cell=spot, x=float(x), y=float(y), value=float(value))
                   for spot, (x, y), value in zip(spatial.obs_names, coordinates, cluster_weights[cell_type])],
                  f"DeepCOLOR原生spot权重中{cell_type}所含单细胞权重之和；每个spot跨全部类型和为1，不是绝对细胞数。",
                  coordinate_unit=cfg["coordinate_unit"], physical_scale_unavailable=cfg.get("physical_scale_unavailable", False),
                  y_down=bool(cfg.get("y_down", False)), value_kind="row_normalized_probability_share", additive=True,
                  figure_role="deepcolor_spatial_abundance", title=f"{cell_type} inferred abundance", axis_label="DeepCOLOR spot weight")
    group_coloc = ordered_group_matrix(colocalization, groups, labels, diagonal=False)
    add_table(bundle, out, "deepcolor_group_colocalization", "matrix", group_coloc,
              "单细胞原生log2共定位分数按输入细胞类型求均值；同群排除细胞自身项。对称、描述性、非显著性。",
              value_kind="native_score", additive=False, figure_role="deepcolor_colocalization_matrix",
              row_order=labels, column_order=labels, axis_label="Mean native log2 colocalization")
    high=np.triu(colocalization>1,1);group_network=[]
    for i,source in enumerate(labels):
        for target in labels[i:]:
            si=np.flatnonzero(groups==source);ti=np.flatnonzero(groups==target)
            count=int(high[np.ix_(si,ti)].sum() + (high[np.ix_(ti,si)].sum() if source!=target else 0))
            if count:group_network.append(dict(source=source,target=target,value=count))
    add_table(bundle, out, "deepcolor_group_high_colocalization", "network", group_network,
              "原生共定位>1固定阈值下的无向跨细胞类型对数量；每个单细胞对只计一次，可加但没有P值/FDR。",
              value_kind="count", additive=True, directed=False, axis_label="High-colocalization cell-pair count")
    entropy = -(probabilities * np.log2(np.clip(probabilities, 1e-300, None))).sum(axis=1)
    qc_rows = []
    for cell_id, cell_type, mapped, ent in zip(single.obs_names, groups, mapping.sum(axis=1), entropy):
        qc_rows.extend([dict(row=cell_id, column="Total native spot contribution", value=float(mapped), cell_type=cell_type),
                        dict(row=cell_id, column="Spatial entropy (bits)", value=float(ent), cell_type=cell_type)])
    add_table(bundle, out, "deepcolor_cell_mapping_qc", "matrix", qc_rows,
              "每个单细胞的原生map2sp总权重与行归一化空间分布熵；前者受全体细胞竞争影响，后者表示空间分散程度。",
              value_kind="native_score", additive=False, figure_role="deepcolor_mapping_qc", axis_label="Observed value")
    diag = [dict(row="Single cells", column="Value", value=single.n_obs), dict(row="Spatial spots", column="Value", value=spatial.n_obs),
            dict(row="Genes", column="Value", value=single.n_vars), dict(row="p_mat max row-sum error", column="Value", value=row_error),
            dict(row="map2sc max spot-sum error", column="Value", value=spot_sum_error),
            dict(row="High colocalization pairs (>1)", column="Value", value=int(np.count_nonzero(np.triu(colocalization > 1, 1))))]
    add_table(bundle, out, "deepcolor_numeric_diagnostics", "matrix", diag,
              "输入规模、两种概率归一化误差和固定阈值下的细胞对数量；用于数值验收，不是生物学显著性。",
              value_kind="native_score", additive=False, figure_role="deepcolor_diagnostics", axis_label="Observed value")
    if training_rows:
        add_table(bundle,out,"deepcolor_training_trace","matrix",training_rows,
                  "上游每10个epoch记录一次的原生验证ELBO损失；两个阶段目标项不同，分别看趋势，不能比较绝对高低或等同模型有效性。",
                  value_kind="native_score",additive=False,figure_role="deepcolor_training",axis_label="Native validation loss")

    pair_queries = cfg.get("pair_cluster_queries", []); pair_status=[]
    for index, query in enumerate(pair_queries, 1):
        first, second = query.get("cellset1", []), query.get("cellset2", [])
        if not first or not second or not set(first + second) <= set(labels) or set(first) & set(second):
            raise ValueError("DeepCOLOR pair cluster查询必须给出存在且不重叠的两组细胞类型")
        group_values=single.obs[label].astype(str).to_numpy();upper=np.argwhere(np.triu(colocalization>1,1))
        eligible=sum(((group_values[a] in first and group_values[b] in second) or (group_values[a] in second and group_values[b] in first)) for a,b in upper)
        pair_status.append(dict(row=f"query_{index}",column="Eligible high-colocalization pairs",value=int(eligible),cellset1="|".join(first),cellset2="|".join(second)))
        if eligible<3:
            continue
        seed_all(seed + index)
        with warnings.catch_warnings(record=True) as pair_warnings:
            warnings.simplefilter("always")
            dual = workflow.analyze_pair_cluster(single.copy(), spatial, first, second, label, max_pair_num=int(query.get("max_pair_num", 30000)))
        write_json(out / f"pair_cluster_warnings_{index}.json", [str(item.message) for item in pair_warnings])
        embedding = np.asarray(dual.obsm["X_umap"])
        add_table(bundle, out, f"deepcolor_pair_embedding_{index}", "embedding_points",
                  [dict(sample=cfg["dataset"], cell=str(cell_id), x=float(x), y=float(y), label=str(cluster), cluster=str(cluster),
                        cell1=str(a), cell2=str(b), pair_type=str(pair_type))
                   for cell_id, (x, y), cluster, a, b, pair_type in zip(dual.obs_names, embedding, dual.obs["leiden"],
                       dual.obs["cell1_obsname"], dual.obs["cell2_obsname"], dual.obs["dual_celltype"])],
                  "上游固定共定位>1细胞对的原生双细胞潜在向量之和，经Scanpy邻居图、UMAP和Leiden得到；不是组织坐标。",
                  embedding_method="DeepCOLOR pair UMAP",
                  embedding_provenance=f"DeepCOLOR analyze_pair_cluster; seed {seed + index}; upstream function computes product term but returns sum only",
                  figure_role="deepcolor_pair_embedding", axis_label="UMAP")
        counts = dual.obs.groupby(["leiden", "dual_celltype"], observed=True).size()
        add_table(bundle, out, f"deepcolor_pair_clusters_{index}", "matrix",
                  [dict(row=str(cluster), column=str(pair), value=int(value)) for (cluster, pair), value in counts.items()],
                  "每个原生Leiden簇中的双细胞类型组合数量；只描述被固定共定位阈值选中的细胞对。",
                  value_kind="count", additive=True, figure_role="deepcolor_pair_clusters", axis_label="Pair count")
    if pair_status:
        add_table(bundle,out,"deepcolor_pair_cluster_eligibility","matrix",pair_status,
                  "每个预声明双细胞查询在原生共定位>1固定阈值下可进入聚类的跨组细胞对数量；少于3时保留阴性结果且不强制UMAP。",
                  value_kind="count",additive=True,figure_role="deepcolor_pair_eligibility",axis_label="Eligible pair count")

    communications = cfg.get("communication_queries", [])
    if communications:
        if not cfg.get("ligand_target_resource") or not cfg.get("ligand_target_provenance"):
            raise ValueError("DeepCOLOR配体活性层需要ligand_target_resource及来源")
        lt_path = resolve(base, cfg["ligand_target_resource"])
        if not lt_path.is_file():
            raise FileNotFoundError(lt_path)
        lt = pd.read_csv(lt_path, sep="\t", index_col=0)
        lt = lt.loc[~lt.index.duplicated(), ~lt.columns.duplicated()].astype(float)
        if lt.empty or not np.isfinite(lt.to_numpy()).all() or (lt.to_numpy() < 0).any():
            raise ValueError("ligand-target矩阵必须是目标基因×配体的有限非负权重")
        bundle["provenance"]["ligand_target_resource"] = dict(description=cfg["ligand_target_provenance"], sha256=digest(lt_path),
                                                                 semantics="NicheNet regulatory potential; not a receptor-binding database")
        communication_input = single.copy(); sc.pp.normalize_total(communication_input, target_sum=1e4); sc.pp.log1p(communication_input)
        for index, query in enumerate(communications, 1):
            query_id = query.get("id", f"query_{index}")
            target_types = query.get("target_celltypes", [])
            if not target_types or not set(target_types) < set(labels):
                raise ValueError("DeepCOLOR配体查询的target_celltypes必须存在且不能覆盖所有类型")
            role = query.get("role", "sender")
            if role not in ("sender", "receiver"):
                raise ValueError("DeepCOLOR配体查询role仅支持sender或receiver")
            available_targets = lt.index.intersection(communication_input.var_names)
            available_ligands = lt.columns.intersection(communication_input.var_names)
            local_lt = lt.loc[available_targets, available_ligands]
            local_lt = local_lt.loc[:, local_lt.sum(axis=0) > 0]
            if local_lt.shape[0] < 20 or local_lt.shape[1] < 2:
                raise ValueError("实测基因与ligand-target矩阵交集不足")
            seed_all(seed + 1000 + index)
            with (out / f"native_communication_{index}.log").open("x") as communication_log, warnings.catch_warnings(record=True) as communication_warnings:
                warnings.simplefilter("always")
                with contextlib.redirect_stdout(communication_log),contextlib.redirect_stderr(communication_log):
                    _, coactivity = workflow.calculate_proximal_cell_communications(
                        communication_input.copy(), label, local_lt, target_types,
                        celltype_sample_num=int(query.get("celltype_sample_num", min(100, min(np.bincount(pd.Categorical(groups).codes))))),
                        ntop_genes=min(int(query.get("ntop_genes", 4000)), communication_input.n_vars),
                        each_display_num=int(query.get("each_display_num", 3)), role=role,
                        edge_thresh=float(query.get("edge_thresh", 1)))
            write_json(out / f"native_communication_warnings_{index}.json",[str(item.message) for item in communication_warnings])
            coactivity = coactivity.rename(columns={"cell1_type": "source", "cell2_type": "target"})
            matrix_rows = [dict(row=f"{row.source}→{row.target}", column=str(row.ligand), value=float(row.coactivity)) for row in coactivity.itertuples()]
            add_table(bundle, out, f"deepcolor_ligand_coactivity_{index}", "matrix", matrix_rows,
                      "原生DeepCOLOR高共定位细胞对中的配体表达×NicheNet靶活性布尔共现计数；不是LR结合、P值或供体效应。",
                      value_kind="count", additive=True, figure_role="deepcolor_ligand_coactivity", axis_label="Boolean coactivity count",
                      display_top_rows=int(query.get("display_top_pairs", 12)), display_top_columns=int(query.get("display_top_ligands", 12)))
            nonzero = coactivity[coactivity.coactivity > 0]
            links = [dict(source=str(row.ligand), target=str(row.target), source_type=str(row.source), target_type=str(row.target), value=float(row.coactivity)) for row in nonzero.itertuples()]
            add_table(bundle, out, f"deepcolor_ligand_links_{index}", "molecular_links", links,
                      "配体节点经高共定位细胞对中的NicheNet靶活性连接到另一细胞类型；source_type记录原始cell1类型。无受体证据。",
                      value_kind="count", additive=True, figure_role="deepcolor_ligand_links", axis_label="Boolean coactivity count")
            network = nonzero.groupby(["source", "target"], as_index=False, observed=True).coactivity.sum()
            add_table(bundle, out, f"deepcolor_proximal_network_{index}", "network",
                      [dict(source=str(r.source), target=str(r.target), value=float(r.coactivity)) for r in network.itertuples()],
                      "原生DeepCOLOR配体coactivity跨配体求和的方向网络；受抽样细胞数、候选配体数与阈值影响，只能在同一查询内描述。",
                      value_kind="count", additive=True, directed=True, axis_label="Summed ligand coactivity")
    write_json(out / "bundle.json", bundle)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True); parser.add_argument("--out", required=True)
    args = parser.parse_args(); raise SystemExit(run(args.config, args.out))
