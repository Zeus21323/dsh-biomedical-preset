#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["anndata==0.10.9", "numpy==1.23.5", "pandas==1.5.3", "scipy==1.10.1", "scikit-learn==1.3.2", "h5py==3.8.0", "matplotlib==3.7.5", "Cython==0.29.36"]
# ///
"""Run the fixed native SVCA 0.0.1/limix 0.8.5 variance-component model."""
from __future__ import annotations

import argparse
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

from communication_contract import add_table, digest, new_output, write_json, write_table


UPSTREAM_COMMIT = "1454c908b360a6118c2384c675aecdb9de7fca2e"
UPSTREAM_VERSION = "0.0.1"
LIMIX_VERSION = "0.8.5"
SOURCE_HASHES = {
    "README.md": "97296a5d58ebfcf5358762417289667fbee89757f6ce7127d0613dd9e5b1b04d",
    "LICENSE": "a32c3460da632aa26397df5f5cc24e2f8cc05efad34d23e808a80984237cf1ed",
    "SVCA/setup.py": "c9ebc6d64a87e40e6704f463e95518d00d67d252a9006f7d21273ad2aa3a821d",
    "SVCA/svca/models/model1.py": "3ac5b85346cac3e08a5d50e949d399f0fdcd1e4b95f411907b06a877b8078dd2",
    "SVCA/svca/models/model_base.py": "792b883d7e688006e754d768c6db015b675115aef5506f6c695b25416f017fc2",
    "SVCA/svca/models/io.py": "89bc446823d391f7f9d3f7b6e3faf53977545ba1b107f77ef892ea27110fa980",
    "SVCA/svca/models/utils_loc.py": "723e9fb2e1f4ed9d5f8695090f8fecdaea5f17424d2fd7062436ebf9ef753bc4",
    "SVCA/svca/util_functions/utils.py": "86846659d6b87ea7092b0fa08ebbc658d4aadf5c151b5b32552946063547b4e8",
    "SVCA/svca/run/run_indiv.py": "c7e2218873875d13d1168c7f77698af64b69a67f4fe07c72d8a79e72a3afe42a",
    "SVCA/svca/run/run_cv.py": "003187fe039ba03e62a539c383ede8438fe33870cd02c3e14a6fca0097281af6",
    "SVCA/svca/plot_scripts/visu_signatures_functions.R": "0891f92c758a2b3584ac3e92b3dfc79672341b30ae5b875f0587375fbed89b3b",
    "SVCA/svca/plot_scripts/plot_r2_cross_validation.R": "979ba52f5b6a864836895398e65d3a2a594c608863080ab278fe53265cf314a5",
    "svca_limix/setup.py": "878ea714fe76f886dceef7ca0c232267658fff22242e7da9b40718ea089e56a2",
}
COMPONENTS = ("Residual noise", "Intrinsic effect", "Environmental effect", "Cell-cell interactions")
NATIVE_COMPONENTS = {
    "noise": "Residual noise",
    "intrinsic": "Intrinsic effect",
    "environmental": "Environmental effect",
    "interactions": "Cell-cell interactions",
}


def require_version(package: str, expected: str) -> str:
    actual = importlib.metadata.version(package)
    if actual != expected:
        raise ValueError(f"SVCA 固定环境要求 {package}=={expected}，当前为 {actual}")
    return actual


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def verify_native(root: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"SVCA 固定源码缺失或摘要不符: {relative}")
    versions = {
        "svca": require_version("svca", UPSTREAM_VERSION),
        "limix": require_version("limix", LIMIX_VERSION),
        "numpy": require_version("numpy", "1.23.5"),
        "scipy": require_version("scipy", "1.10.1"),
        "pandas": require_version("pandas", "1.5.3"),
        "anndata": require_version("anndata", "0.10.9"),
        "scikit-learn": require_version("scikit-learn", "1.3.2"),
        "h5py": require_version("h5py", "3.8.0"),
    }
    from svca.models.model1 import Model1
    from svca.models.io import write_variance_explained
    from limix.utils.preprocess import covar_rescaling_factor

    installed = {
        Path(inspect.getsourcefile(Model1)).resolve(): root / "SVCA/svca/models/model1.py",
        Path(inspect.getsourcefile(write_variance_explained)).resolve(): root / "SVCA/svca/models/io.py",
    }
    for actual, source in installed.items():
        if digest(actual) != digest(source):
            raise ValueError(f"已安装 SVCA 源码与固定提交不一致: {actual.name}")
    return Model1, write_variance_explained, covar_rescaling_factor, versions


def checked_integer(cfg, key, default, minimum, maximum=None):
    value = cfg.get(key, default)
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        suffix = f"且不超过 {maximum}" if maximum is not None else ""
        raise ValueError(f"{key} 必须为不小于 {minimum} 的整数{suffix}")
    return value


def load_input(cfg, base: Path):
    for key in ("dataset", "research_question", "input", "native_root", "input_provenance",
                "coordinate_provenance", "coordinate_unit", "expression_scale", "normalization_definition"):
        if not cfg.get(key):
            raise ValueError("缺少: " + key)
    if cfg["coordinate_unit"] not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if cfg["coordinate_unit"] == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
    if cfg["expression_scale"] not in ("normalized", "log_normalized", "transformed_continuous"):
        raise ValueError("SVCA 接受有限连续表达/蛋白丰度；必须声明实际归一化或变换定义")
    if "layer" not in cfg:
        raise ValueError("须明确 layer=X 或实际层名，不自动读取 raw/整合层")
    path = resolve(base, cfg["input"])
    data = ad.read_h5ad(path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞和特征 ID 必须唯一")
    keys = {name: cfg.get(name + "_key", name) for name in ("sample", "donor", "condition")}
    for key in keys.values():
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
        data.obs[key] = data.obs[key].astype(str)
    for sample, frame in data.obs.groupby(keys["sample"], observed=True):
        if frame[keys["donor"]].nunique() != 1 or frame[keys["condition"]].nunique() != 1:
            raise ValueError(f"样本 {sample} 不唯一对应供体/条件")
    layer = cfg["layer"]
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError("配置表达层不存在")
    maximum_dense = checked_integer(cfg, "maximum_dense_elements", 50_000_000, 1)
    if data.n_obs * data.n_vars > maximum_dense:
        raise ValueError("SVCA 原生模型需要稠密矩阵，输入超过声明的 maximum_dense_elements")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != (data.n_obs, data.n_vars) or not np.isfinite(matrix).all():
        raise ValueError("表达/蛋白丰度矩阵必须有限且与细胞、特征严格对齐")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("输入必须有与细胞逐行对齐的有限二维真实空间坐标")
    if cfg.get("samples"):
        wanted = list(cfg["samples"])
        absent = set(wanted) - set(data.obs[keys["sample"]])
        if absent:
            raise ValueError(f"指定样本不存在: {sorted(absent)}")
        keep = data.obs[keys["sample"]].isin(wanted).to_numpy()
        data, matrix, coordinates = data[keep].copy(), matrix[keep], coordinates[keep]
    return data, matrix, coordinates, keys, path


def native_effects(model, rescale):
    effects = {}
    for name, covariance in model.covar_terms.items():
        try:
            value = 1.0 / float(rescale(covariance.K()))
        except Exception:
            value = 0.0
        effects[name] = value
    if set(effects) != set(NATIVE_COMPONENTS):
        raise ValueError(f"SVCA 原生协方差分量变化: {sorted(effects)}")
    if any(not np.isfinite(value) or value < 0 for value in effects.values()) or sum(effects.values()) <= 0:
        raise ValueError("SVCA 返回无效方差分量")
    return effects


def fit_signature(Model1, native_write, rescale, matrix, coordinates, feature_index, normalisation,
                  native_dir: Path, sample_index: int, feature_order: int):
    others = [index for index in range(matrix.shape[1]) if index != feature_index]
    if not others:
        raise ValueError("SVCA 至少需要两个分子特征，才能用其余特征构造内在状态核")
    kin_from = matrix[:, others].copy()
    kin_from -= kin_from.mean(axis=0)
    if not np.any(np.abs(kin_from) > 0):
        raise ValueError("除目标外的特征没有变异，无法构造内在状态核")
    model = Model1(matrix[:, feature_index].copy(), coordinates.copy(), norm=normalisation,
                   oos_predictions=0.0, cov_terms=["intrinsic", "environmental", "interactions"],
                   kin_from=matrix[:, others].copy(), cv_ix=0)
    model.reset_params()
    try:
        model.train_gp(grid_size=10)
    except SystemExit as error:
        raise RuntimeError("SVCA 原生长度尺度网格没有可用拟合") from error
    effects = native_effects(model, rescale)
    prefix = f"sample_{sample_index:03d}_feature_{feature_order:04d}_interactions"
    native_write(model, str(native_dir), prefix)
    native_path = native_dir / (prefix + "_effects.txt")
    native = pd.read_csv(native_path, sep=r"\s+")
    if len(native) != 1 or set(native.columns) != set(effects):
        raise ValueError("SVCA 原生输出结构变化")
    if max(abs(float(native.iloc[0][key]) - value) for key, value in effects.items()) > 1e-12:
        raise ValueError("SVCA 原生输出与内存方差分量不一致")
    l_grid = np.asarray(model.l_grid, dtype=float)
    objectives = np.asarray(model.LMLs, dtype=float)
    if l_grid.shape != objectives.shape or not np.isfinite(l_grid).all() or not np.isfinite(objectives).any():
        raise ValueError("SVCA 长度尺度网格或目标函数无有效记录")
    best_length = float(math.sqrt(model.interactions_cov.length))
    state_path = native_dir / (prefix + "_state.npz")
    gp_parameters = model.gp.getParams()
    if not isinstance(gp_parameters, dict) or set(gp_parameters) != {"covar"}:
        raise ValueError("SVCA/limix 原生 GP 参数结构变化")
    gp_parameters = np.asarray(gp_parameters["covar"], dtype=float)
    np.savez_compressed(state_path, effects=np.array([effects[key] for key in NATIVE_COMPONENTS]),
                        component_names=np.array(list(NATIVE_COMPONENTS)), length_grid=l_grid,
                        objective=objectives, chosen_length=best_length,
                        gp_parameters=gp_parameters)
    return effects, l_grid, objectives, best_length, native_path, state_path


def fit_cv(Model1, matrix, coordinates, feature_index, normalisation, folds, cell_ids):
    others = [index for index in range(matrix.shape[1]) if index != feature_index]
    records = []
    for fold in range(folds):
        model = Model1(matrix[:, feature_index].copy(), coordinates.copy(), norm=normalisation,
                       oos_predictions=1.0 / folds, cov_terms=["intrinsic"],
                       kin_from=matrix[:, others].copy(), cv_ix=fold)
        stages = (("Intrinsic effect", None), ("+ Environmental effect", "environmental"),
                  ("+ Cell-cell interactions", "interactions"))
        for stage, addition in stages:
            if addition:
                model.add_cov([addition])
            model.reset_params()
            try:
                model.train_gp(grid_size=10)
            except SystemExit as error:
                raise RuntimeError(f"SVCA 交叉验证在 {stage} / fold {fold} 无可用拟合") from error
            prediction = np.asarray(model.predict())[:, 0]
            truth = np.asarray(model.Y)[:, 0][~model.train_set]
            indices = np.flatnonzero(~model.train_set)
            if len(prediction) != len(indices) or not np.isfinite(prediction).all() or not np.isfinite(truth).all():
                raise ValueError("SVCA 交叉验证预测长度或数值无效")
            records.extend(dict(fold=fold, cell=cell_ids[index], model=stage,
                                truth=float(y), prediction=float(p))
                           for index, y, p in zip(indices, truth, prediction))
    return records


def r2(rows):
    truth = np.array([row["truth"] for row in rows], dtype=float)
    prediction = np.array([row["prediction"] for row in rows], dtype=float)
    denominator = np.sum((truth - truth.mean()) ** 2)
    return None if denominator <= 0 else float(1 - np.sum((truth - prediction) ** 2) / denominator)


def run(config, output):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text())
    base = config.parent
    root = resolve(base, cfg.get("native_root", ""))
    Model1, native_write, rescale, versions = verify_native(root)
    data, matrix, coordinates, keys, input_path = load_input(cfg, base)
    normalisation = cfg.get("target_normalisation", "quantile")
    if normalisation not in ("quantile", "std"):
        raise ValueError("target_normalisation 只接受作者实现的 quantile 或 std")
    minimum_cells = checked_integer(cfg, "minimum_cells", 30, 10)
    maximum_cells = checked_integer(cfg, "maximum_cells", 2500, minimum_cells)
    maximum_features = checked_integer(cfg, "maximum_features", 100, 1)
    requested = cfg.get("features") or list(map(str, data.var_names))
    if not isinstance(requested, list) or not requested or not all(isinstance(value, str) and value for value in requested):
        raise ValueError("features 必须是实际非空特征名列表")
    if len(set(requested)) != len(requested) or not set(requested) <= set(data.var_names):
        raise ValueError("features 含重复或输入中不存在的特征")
    if len(requested) > maximum_features:
        raise ValueError("待拟合特征超过 maximum_features；SVCA 逐特征做三次方复杂度模型，需先按有依据的检测面板/研究问题声明范围")
    folds = cfg.get("cross_validation_folds", 0)
    if type(folds) is not int or folds not in (0, *range(3, 11)):
        raise ValueError("cross_validation_folds 只接受 0（关闭）或 3–10")
    cv_features = cfg.get("cross_validation_features", requested if folds else [])
    if folds and (not isinstance(cv_features, list) or not cv_features or not set(cv_features) <= set(requested)):
        raise ValueError("cross_validation_features 必须是已拟合特征的非空子集")
    output_root = new_output(output)
    native_dir = output_root / "native_results"
    native_dir.mkdir()
    write_json(output_root / "run_config.json", cfg)
    signature = digest(input_path) + ":" + digest(config) + ":" + UPSTREAM_COMMIT
    state = {"status": "running", "signature": signature, "completed": [], "failed": []}
    write_json(output_root / "run_state.json", state)
    raw_rows, fraction_rows, objective_rows, length_rows, effect_rows = [], [], [], [], []
    cv_rows, prediction_manifest, native_manifest, eligibility = [], [], [], []
    samples = list(dict.fromkeys(data.obs[keys["sample"]].tolist()))
    for sample_index, sample in enumerate(samples, 1):
        selected = np.flatnonzero(data.obs[keys["sample"]].to_numpy() == sample)
        if not minimum_cells <= len(selected) <= maximum_cells:
            raise ValueError(f"样本 {sample} 有 {len(selected)} 个细胞，不在 [{minimum_cells}, {maximum_cells}] 的固定原生计算范围")
        sample_coordinates = coordinates[selected]
        if len(np.unique(sample_coordinates, axis=0)) != len(sample_coordinates):
            raise ValueError(f"样本 {sample} 含重复坐标，需核实细胞分割和空间身份")
        sample_matrix = matrix[selected]
        donor = data.obs.iloc[selected[0]][keys["donor"]]
        condition = data.obs.iloc[selected[0]][keys["condition"]]
        for feature_order, feature in enumerate(requested, 1):
            index = int(data.var_names.get_loc(feature))
            values = sample_matrix[:, index]
            unique = np.unique(values)
            if len(unique) < 3 or np.std(values) == 0:
                eligibility.append(dict(sample=sample, feature=feature, eligible=False,
                                        reason="target_has_fewer_than_three_unique_values"))
                continue
            try:
                effects, grid, objectives, length, native_path, state_path = fit_signature(
                    Model1, native_write, rescale, sample_matrix, sample_coordinates, index,
                    normalisation, native_dir, sample_index, feature_order)
                total = sum(effects.values())
                row_name = f"{sample} | {feature}"
                for native_name, label in NATIVE_COMPONENTS.items():
                    raw_rows.append(dict(row=row_name, column=label, value=effects[native_name],
                                         sample=sample, donor=donor, condition=condition, feature=feature))
                    fraction_rows.append(dict(row=row_name, column=label, value=effects[native_name] / total,
                                              sample=sample, donor=donor, condition=condition, feature=feature))
                interaction_fraction = effects["interactions"] / total
                effect_rows.append(dict(sample=sample, donor=donor, condition=condition,
                                        feature=feature, value=interaction_fraction))
                for scale, objective in zip(grid, objectives):
                    objective_rows.append(dict(row=f"{scale:.17g}", column=row_name,
                                               value=None if not np.isfinite(objective) else float(objective)))
                length_rows.append(dict(row=row_name, column="Selected spatial length", value=length,
                                        sample=sample, feature=feature))
                native_manifest.append(dict(sample=sample, feature=feature,
                                            effects_file=str(native_path.relative_to(output_root)),
                                            effects_sha256=digest(native_path),
                                            state_file=str(state_path.relative_to(output_root)),
                                            state_sha256=digest(state_path)))
                eligibility.append(dict(sample=sample, feature=feature, eligible=True, reason="estimated"))
                state["completed"].append({"sample": sample, "feature": feature})
                write_json(output_root / "run_state.json", state)
            except Exception as error:
                eligibility.append(dict(sample=sample, feature=feature, eligible=False,
                                        reason="native_fit_failed", message=str(error)))
                state["failed"].append({"sample": sample, "feature": feature, "error": str(error)})
                write_json(output_root / "run_state.json", state)
        if folds:
            for feature in cv_features:
                if not any(row["sample"] == sample and row["feature"] == feature and row["eligible"] for row in eligibility):
                    continue
                index = int(data.var_names.get_loc(feature))
                predictions = fit_cv(Model1, sample_matrix, sample_coordinates, index, normalisation,
                                     folds, list(map(str, data.obs_names[selected])))
                prediction_file = output_root / f"cv_predictions_{sample_index:03d}_{requested.index(feature)+1:04d}.tsv"
                write_table(prediction_file, predictions)
                prediction_manifest.append(dict(sample=sample, feature=feature,
                                                path=prediction_file.name, sha256=digest(prediction_file)))
                for model in ("Intrinsic effect", "+ Environmental effect", "+ Cell-cell interactions"):
                    chosen = [row for row in predictions if row["model"] == model]
                    cv_rows.append(dict(row=f"{sample} | {feature}", column=model, value=r2(chosen),
                                        sample=sample, donor=donor, condition=condition, feature=feature))
    write_table(output_root / "feature_eligibility.tsv", eligibility)
    write_json(output_root / "native_artifacts.json", {"signature": signature, "models": native_manifest,
                                                       "cross_validation_predictions": prediction_manifest})
    if not fraction_rows:
        state["status"] = "failed"
        write_json(output_root / "run_state.json", state)
        raise RuntimeError("SVCA 没有任何可交付拟合；见 feature_eligibility.tsv 与 run_state.json")
    bundle = {
        "schema_version": 2,
        "dataset": cfg["dataset"],
        "method": "SVCA",
        "method_version": UPSTREAM_VERSION,
        "implementation": "native",
        "figure_inapplicability": {
            "overview": "SVCA没有有向通讯网络；主结果由方差签名图承载。",
            "circos": "SVCA没有发送者、接收者或可加分子边，弦宽没有定义。",
            "lr_evidence": "SVCA不估计配体–受体候选。",
            "hierarchy": "SVCA不估计有向细胞群层级网络。",
            "roles": "SVCA不估计发送/接收角色或中心性。",
            "cellchat_patterns": "SVCA不执行CellChat NMF模式。",
            "pathway_sankey": "SVCA没有通路身份或可加流权。",
            "ligand_response": "SVCA不估计配体活性或靶基因响应。",
            "intracellular": "SVCA不重建LR–TF–target机制链。",
            "factors": "SVCA不做张量/NMF因子分解。",
            "enrichment": "SVCA原生模型不提供基因集富集。",
            "embedding": "SVCA不生成细胞或分子降维坐标。",
            "spatial_hotspots": "SVCA只给图像级方差分量，不给逐细胞局部交互效应。",
            "spatial_direction": "SVCA不估计空间传播方向或速度向量。",
            "relay_dynamic": "SVCA不建模时间、轨迹或多跳传递。",
            "special_molecules": "SVCA没有代谢物或递质专用分子模型。",
            "functional_clinical": "SVCA原生模型不计算临床、药敏或功能评分关联。"
        },
        "provenance": {
            "input_sha256": digest(input_path),
            "parameters": cfg,
            "coordinate_provenance": cfg["coordinate_provenance"],
            "upstream": {"url": "https://github.com/damienArnol/svca", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "limix_version": LIMIX_VERSION, "license": "Apache-2.0"},
            "source_sha256": SOURCE_HASHES,
            "versions": versions,
            "statistical_semantics": {
                "components": "Each target feature is quantile-normalized or standardized, then decomposed by the native Gaussian-process model into intrinsic molecular-state, non-specific spatial environmental, cell-cell interaction and residual-noise covariance components.",
                "interaction": "The interaction kernel is a spatially localized version of molecular-state similarity constructed from all measured features except the target; it is not a ligand-receptor edge, molecular flux, named sender-receiver pair or causal mechanism.",
                "fraction": "Each reported signature divides four nonnegative native variance components by their within-sample/feature sum, matching the upstream visualization logic.",
                "statistical_unit": "One independently fitted image/sample; cells within an image are correlated observations, not donor replicates.",
                "inference": "The signature fit returns no native P value. Cross-validation, when requested, assesses nested predictive models and is not a significance test.",
            },
            "native_artifacts": "native_artifacts.json",
            "feature_eligibility": "feature_eligibility.tsv",
            "limitations": [
                "SVCA 0.0.1 is an archived-era Python/limix stack; the adapter pins Python 3.10 and exact numerical dependencies and verifies the fixed source files.",
                "The upstream cross-validation script calls remove on a Python 3 range. The adapter applies the intended list-of-other-features selection while preserving Model1, its fixed fold seed, nested covariance additions and prediction formula.",
                "The upstream plots normalize each feature signature to sum to one. Raw components and normalized fractions are both retained; fractions cannot be compared as absolute biological signal strength across platforms without design-matched validation.",
                "No ligand, receptor, pathway, sender or receiver identity is estimated, so LR bubbles, directed hierarchy networks and chord diagrams are scientifically not applicable.",
            ],
        },
        "tables": [],
    }
    add_table(bundle, output_root, "svca_variance_signature", "matrix", fraction_rows,
              "原生四分量方差除以同一样本/特征四分量总和；每行和为1。Cell-cell interactions是空间局部化的分子状态相似性核，不是LR边或分子通量。",
              value_kind="row_normalized_probability_share", additive=True,
              axis_label="Fraction of modeled variance", figure_role="variance_signature",
              row_order=list(dict.fromkeys(row["row"] for row in sorted(
                  fraction_rows, key=lambda row: (row["column"] != "Cell-cell interactions", -row["value"])))),
              column_order=list(COMPONENTS), display_top_rows=min(50, len(effect_rows)))
    add_table(bundle, output_root, "svca_raw_variance_components", "matrix", raw_rows,
              "原生write_variance_explained使用各协方差矩阵Gower重标度倒数得到的未归一化分量；只在同一样本/目标模型内解释。",
              value_kind="nonnegative_strength", additive=False, axis_label="Native variance component",
              column_order=list(COMPONENTS), display_top_rows=min(30, len(effect_rows)))
    donor_effects = []
    effect_frame = pd.DataFrame(effect_rows)
    for (donor, condition, feature), frame in effect_frame.groupby(["donor", "condition", "feature"], sort=True):
        donor_effects.append(dict(sample=";".join(sorted(frame["sample"].unique())), donor=donor,
                                  condition=condition, feature=feature, value=float(frame["value"].mean()),
                                  n_images=int(len(frame))))
    add_table(bundle, output_root, "svca_interaction_fraction_by_donor", "effects", donor_effects,
              "每个点为供体内图像Cell-cell interactions方差份额的算术均值；单图像供体保持原值。图像不冒充独立供体，绘图不新增显著性。",
              value_kind="row_normalized_probability_share", nonnegative=True,
              axis_label="Cell-cell interaction variance fraction")
    add_table(bundle, output_root, "svca_selected_length", "matrix", length_rows,
              "原生10点距离网格中最小负对数边际似然对应的空间长度；环境与交互核共享该长度。其物理意义取决于坐标单位和标定。",
              value_kind="nonnegative_strength", axis_label=f"Selected spatial length ({cfg['coordinate_unit']})",
              display_style="lollipop", display_top_rows=min(30, len(length_rows)))
    add_table(bundle, output_root, "svca_length_objective", "matrix", objective_rows,
              "每个样本/特征在原生10点空间长度网格上的负对数边际似然；NA表示该网格点原生优化失败，不插值。",
              value_kind="native_score", direction="lower", axis_label="Native negative log marginal likelihood",
              coordinate_unit=cfg["coordinate_unit"], figure_role="spatial_scale_profile",
              display_top_columns=min(14, len(effect_rows)))
    if cv_rows:
        add_table(bundle, output_root, "svca_nested_cross_validation", "matrix", cv_rows,
                  "按作者固定种子0的空间细胞随机折叠，汇总全部折外Truth/Prediction后的原始R²；负值保留，不截为0。三个模型逐次增加环境和细胞交互核。",
                  value_kind="native_score", axis_label="Out-of-fold R²", figure_role="nested_cross_validation",
                  column_order=["Intrinsic effect", "+ Environmental effect", "+ Cell-cell interactions"])
    # Expression maps are context only. They never pretend that SVCA estimates a
    # per-cell interaction contribution.
    top_spatial = checked_integer(cfg, "top_spatial_features", 3, 0, 12)
    ranked = sorted(effect_rows, key=lambda row: (-row["value"], row["sample"], row["feature"]))
    chosen = {(row["sample"], row["feature"]) for row in ranked[:top_spatial]}
    for number, (sample, feature) in enumerate(sorted(chosen), 1):
        selected = np.flatnonzero(data.obs[keys["sample"]].to_numpy() == sample)
        index = int(data.var_names.get_loc(feature))
        points = [dict(sample=sample, cell=str(data.obs_names[cell]), x=float(coordinates[cell, 0]),
                       y=float(coordinates[cell, 1]), value=float(matrix[cell, index])) for cell in selected]
        add_table(bundle, output_root, f"svca_input_feature_map_{number}", "spatial_points", points,
                  "按SVCA交互方差份额排序后选出的原始输入特征空间分布，仅提供组织背景；颜色不是局部交互效应。",
                  value_kind="native_score", axis_label=f"Input {feature}", title=f"{sample}: {feature} input",
                  coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                  physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    write_json(output_root / "bundle.json", bundle)
    state["status"] = "complete_with_failures" if state["failed"] else "complete"
    state["bundle_sha256"] = digest(output_root / "bundle.json")
    write_json(output_root / "run_state.json", state)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.exit(run(args.config, args.out))
