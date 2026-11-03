#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["renoir-spatial==1.0.0", "numpy==2.2.6", "scipy==1.15.3", "pandas==2.2.3", "scikit-learn==1.6.0", "scanpy==1.10.4", "anndata==0.11.4", "hdbscan==0.8.40", "plotly==5.24.1", "harmonypy==0.0.10", "zarr==2.18.7", "numcodecs==0.15.1", "spatialdata==0.8.0", "squidpy==1.8.3", "distinctipy==1.3.4", "dynamicTreeCut==0.1.1"]
# ///
"""Run fixed Renoir ligand-to-target spatial-neighborhood activity analysis."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.stats import spearmanr
from sklearn.decomposition import TruncatedSVD

from communication_contract import add_table, digest, new_output, write_json


UPSTREAM_COMMIT = "2ea1c987ae5217ced16f2884050678ff3832fbf7"
UPSTREAM_VERSION = "1.0.0"
SOURCE_HASHES = {
    "README.md": "494db01aaca4277d3f8864d29d2c92be984c988aff071326f07687b210384500",
    "setup.py": "b856b88d2bd35025ed8dc4052c5ad0a3d90226b80c342d431ac981b3f913fd59",
    "renoir.yml": "2b34254c69401fad437107b1bb25c9888f9539bf5d2fdb2420afa0670074a4a2",
    "Renoir/renoir.py": "a75a579bd0c2a0978368b706807baf9511dc4b5cde6edce4475b57032960851f",
    "Renoir/downstream.py": "51429682963bd2943ce990793d8ddda37ca052c8bb1d02d768f3090bb02a4ec4",
    "Renoir/__init__.py": "7e62684d657e888069a497fd6d286bac322a46b2e22cd6b771240e49f4153fac",
}
PYTHON_VERSIONS = {
    "renoir-spatial": "1.0.0", "numpy": "2.2.6", "scipy": "1.15.3", "pandas": "2.2.3",
    "scikit-learn": "1.6.0", "scanpy": "1.10.4", "anndata": "0.11.4", "hdbscan": "0.8.40",
    "plotly": "5.24.1", "harmonypy": "0.0.10", "zarr": "2.18.7", "numcodecs": "0.15.1",
    "spatialdata": "0.8.0", "squidpy": "1.8.3", "distinctipy": "1.3.4", "dynamicTreeCut": "0.1.1",
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
            raise ValueError(f"Renoir 固定源码缺 lingering、缺失或摘要不符: {relative}")
    commit = subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError(f"Renoir 固定源码提交应为 {UPSTREAM_COMMIT}，当前为 {commit}")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Renoir 固定环境需要 Python 3.12")
    observed = {}
    for package, expected in PYTHON_VERSIONS.items():
        actual = importlib.metadata.version(package)
        observed[package] = actual
        if actual != expected:
            raise ValueError(f"Renoir 固定环境要求 {package}=={expected}，当前为 {actual}")
    sys.path.insert(0, str(source_root))
    import Renoir
    if Renoir.__version__ != "unknown":
        raise ValueError("Renoir __version__ 上游缺陷状态发生变化，需重新审计")
    observed["Renoir.__version__"] = Renoir.__version__
    return observed


def dense(data: ad.AnnData, layer: str):
    matrix = data.X if layer == "X" else data.layers.get(layer)
    if matrix is None:
        raise ValueError(f"表达层不存在: {layer}")
    matrix = matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)
    matrix = np.asarray(matrix, dtype=float)
    if matrix.shape != data.shape or not np.isfinite(matrix).all() or (matrix < 0).any():
        raise ValueError("表达矩阵必须有限、非负并与 AnnData 对齐")
    return matrix


def input_contract(cfg, base: Path):
    required = ("dataset", "research_question", "spatial_input", "spatial_input_provenance",
                "reference_input", "reference_input_provenance", "native_root",
                "ligand_target_resource", "ligand_target_sha256", "ligand_target_provenance",
                "ligand_receptor_resource", "ligand_receptor_sha256", "ligand_receptor_provenance",
                "celltype_proportions", "celltype_proportions_sha256", "celltype_proportions_provenance",
                "expression_layer", "expression_scale", "normalization_definition",
                "coordinate_unit", "coordinate_provenance", "graph_mode")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("Renoir 配置缺少: " + key)
    paths = {key: resolve(base, cfg[key]) for key in ("spatial_input", "reference_input", "native_root",
             "ligand_target_resource", "ligand_receptor_resource", "celltype_proportions")}
    for key, path in paths.items():
        if not path.exists():
            raise ValueError(f"Renoir 路径不存在: {key}")
    for key, sha_key in (("ligand_target_resource", "ligand_target_sha256"),
                         ("ligand_receptor_resource", "ligand_receptor_sha256"),
                         ("celltype_proportions", "celltype_proportions_sha256")):
        if digest(paths[key]) != cfg[sha_key]:
            raise ValueError(f"{key} SHA-256 与配置不符")
    spatial_data = ad.read_h5ad(paths["spatial_input"])
    reference = ad.read_h5ad(paths["reference_input"])
    for name, data in (("spatial", spatial_data), ("reference", reference)):
        if not data.obs_names.is_unique or not data.var_names.is_unique:
            raise ValueError(f"Renoir {name} 需要唯一细胞/spot 与基因 ID")
        if data.n_obs < 20 or data.n_obs > integer(cfg.get("maximum_observations", 10000), "maximum_observations", 20):
            raise ValueError(f"Renoir {name} 观察数不在允许范围")
        dense(data, cfg["expression_layer"])
        if any(str(g).upper() != str(g) for g in data.var_names):
            raise ValueError("Renoir 输入基因必须预先统一为大写；执行器不静默改名")
    sample_key = cfg.get("sample_key", "sample")
    if sample_key not in spatial_data.obs or spatial_data.obs[sample_key].isna().any():
        raise ValueError("Renoir spatial 输入缺少完整样本字段")
    samples = list(dict.fromkeys(spatial_data.obs[sample_key].astype(str)))
    if len(samples) != 1:
        raise ValueError("Renoir 当前原生入口一次只分析一个空间样本；多样本必须分别运行")
    celltype_key = cfg.get("celltype_key", "celltype")
    if celltype_key not in reference.obs or reference.obs[celltype_key].isna().any():
        raise ValueError("Renoir reference 输入缺少完整 celltype")
    if celltype_key != "celltype":
        raise ValueError("固定原生 Renoir 要求 reference.obs['celltype']；请在输入准备时显式复制")
    counts = reference.obs[celltype_key].astype(str).value_counts()
    if (counts < integer(cfg.get("minimum_reference_cells_per_type", 2), "minimum_reference_cells_per_type", 2)).any():
        raise ValueError("Renoir 每个参考细胞类型的细胞数不足以估计熵")
    proportions = pd.read_csv(paths["celltype_proportions"], index_col=0)
    proportions.index = proportions.index.astype(str)
    if not proportions.index.is_unique or list(proportions.index) != list(map(str, spatial_data.obs_names)):
        raise ValueError("细胞类型比例必须与 spatial obs_names 同序精确对齐")
    proportions = proportions.apply(pd.to_numeric, errors="raise")
    if not np.isfinite(proportions.to_numpy()).all() or (proportions.to_numpy() < 0).any():
        raise ValueError("细胞类型比例必须是有限非负数")
    if not np.allclose(proportions.sum(axis=1), 1, atol=1e-6):
        raise ValueError("每个 spatial 观察的细胞类型比例和必须为1")
    if set(proportions.columns) != set(counts.index):
        raise ValueError("比例表细胞类型必须与 reference.obs.celltype 精确一致")
    lt = pd.read_csv(paths["ligand_target_resource"])
    lr = pd.read_csv(paths["ligand_receptor_resource"])
    if not {"ligand", "target"} <= set(lt) or not {"ligand", "receptor"} <= set(lr):
        raise ValueError("Renoir 分子资源缺少小写 ligand/target 或 ligand/receptor 列")
    for frame, columns, name in ((lt, ["ligand", "target"], "ligand-target"), (lr, ["ligand", "receptor"], "ligand-receptor")):
        if frame[columns].isna().any().any() or frame.duplicated(columns).any():
            raise ValueError(f"Renoir {name} 资源含缺失或重复分子对")
        if any(frame[col].astype(str).str.upper().ne(frame[col].astype(str)).any() for col in columns):
            raise ValueError(f"Renoir {name} 资源必须预先统一为大写")
    if len(lt) > integer(cfg.get("maximum_ligand_target_pairs", 2000), "maximum_ligand_target_pairs", 1):
        raise ValueError("Renoir ligand-target 候选数超过配置上限")
    coordinates = np.asarray(spatial_data.obsm.get(cfg.get("spatial_key", "spatial")), dtype=float)
    if coordinates.shape != (spatial_data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("Renoir 需要逐观察对齐的有限二维坐标")
    if cfg["coordinate_unit"] not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if cfg["coordinate_unit"] == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标必须明确 physical_scale_unavailable=true")
    graph_mode = cfg["graph_mode"]
    if graph_mode == "radius_single_cell":
        radius = finite(cfg.get("radius"), "radius", np.finfo(float).eps)
        single_cell, use_radius = True, True
    elif graph_mode == "visium_hex":
        for key in ("array_row", "array_col"):
            if key not in spatial_data.obs or not np.isfinite(pd.to_numeric(spatial_data.obs[key], errors="coerce")).all():
                raise ValueError("Visium hex 图需要有限 array_row/array_col")
        radius, single_cell, use_radius = 0.0, False, False
    else:
        raise ValueError("graph_mode 只接受 radius_single_cell 或 visium_hex")
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("publication", "exploratory"):
        raise ValueError("analysis_tier 只接受 publication 或 exploratory")
    seeds = cfg.get("seeds", [101, 202, 303])
    if not isinstance(seeds, list) or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("seeds 必须是互不重复的整数列表")
    if tier == "publication" and len(seeds) < 3:
        raise ValueError("publication 模式至少需要3个种子核查零表达扰动稳定性")
    return paths, spatial_data, reference, proportions, lt, lr, coordinates, samples[0], radius, single_cell, use_radius, tier, seeds


def copy_native_inputs(paths, native_dir: Path):
    copied = {}
    for key in ("spatial_input", "reference_input", "ligand_target_resource", "ligand_receptor_resource", "celltype_proportions"):
        target = native_dir / Path(paths[key]).name
        shutil.copy2(paths[key], target)
        copied[key] = target.name
    return copied


def run(config, output):
    started = time.time()
    config = Path(config).resolve(); base = config.parent
    cfg = json.loads(config.read_text())
    output_root = new_output(output)
    write_json(output_root / "run_config.json", cfg)
    state = {"schema_version": 2, "status": "running", "config_sha256": digest(config)}
    write_json(output_root / "run_state.json", state)
    paths, spatial_data, reference, proportions, lt, lr, coordinates, sample, radius, single_cell, use_radius, tier, seeds = input_contract(cfg, base)
    versions = verify_native(paths["native_root"])
    from Renoir.renoir import compute_neighborhood_scores, neighborhood
    from Renoir.downstream import create_cluster, downstream_analysis

    native_dir = output_root / "native_results"; native_dir.mkdir()
    copied_inputs = copy_native_inputs(paths, native_dir)
    scores = []
    with (native_dir / "renoir_native.log").open("w") as log, redirect_stdout(log), redirect_stderr(log):
        for seed in seeds:
            np.random.seed(seed)
            result = compute_neighborhood_scores(
                str(paths["reference_input"]), str(paths["spatial_input"]), str(paths["ligand_target_resource"]),
                str(paths["ligand_receptor_resource"]), str(paths["celltype_proportions"]), expins_path=None,
                single_cell=single_cell, use_radius=use_radius, radius=radius, return_adata=True)
            matrix = np.asarray(result.X, dtype=float)
            if result.n_obs != spatial_data.n_obs or result.n_vars < integer(cfg.get("minimum_effective_pairs", 10), "minimum_effective_pairs", 1):
                raise ValueError("Renoir 原生输出观察数或有效 ligand-target 数不足")
            if not np.isfinite(matrix).all() or (matrix < 0).any():
                raise ValueError("Renoir 原生 neighborhood score 含非有限值或负值")
            result.write_h5ad(native_dir / f"neighborhood_scores_seed_{seed}.h5ad")
            scores.append(result)
        if any(list(item.var_names) != list(scores[0].var_names) or list(item.obs_names) != list(scores[0].obs_names) for item in scores[1:]):
            raise ValueError("Renoir 不同种子输出身份不一致")
        empty_msig = pd.DataFrame({"gs_name": pd.Series(dtype=str), "gene_symbol": pd.Series(dtype=str)})
        cluster_method = cfg.get("program_clustering", "dhc")
        if cluster_method not in ("dhc", "hdbscan"):
            raise ValueError("program_clustering 只接受 dhc 或 hdbscan")
        np.random.seed(seeds[0])
        programs = create_cluster(scores[0], empty_msig, method=cluster_method,
                                  minpts=integer(cfg.get("program_minpts", 3), "program_minpts", 2),
                                  ltclust_thresh=integer(cfg.get("program_minimum_pairs_exclusive", 2), "program_minimum_pairs_exclusive", 0))
        if not programs:
            raise ValueError("Renoir 原生 de novo 聚类没有保留任何 ligand-target 程序")
        # Capture the exact upstream pre-scaling program values explicitly. The
        # fixed downstream function assigns .raw to the same object and later
        # scales in place, so its returned .raw is not an unscaled checkpoint.
        primary_frame = scores[0].to_df()
        program_values = {}
        np.random.seed(seeds[0])
        for name, members in programs.items():
            program_values[name] = np.abs(TruncatedSVD().fit_transform(primary_frame.loc[:, members])[:, 0])
        domain_scaled, program_scaled = downstream_analysis(
            scores[0], programs, resolution=finite(cfg.get("domain_resolution", 0.8), "domain_resolution", 0.01, 10),
            return_cluster=True, return_pcs=True)
    domain = scores[0].copy(); domain.obs = domain_scaled.obs.copy(); domain.obsm = domain_scaled.obsm.copy()
    program = ad.AnnData(pd.DataFrame(program_values, index=scores[0].obs_names),
                         obs=program_scaled.obs.copy(), obsm=program_scaled.obsm.copy())
    if "leiden" not in domain.obs or domain.obs.leiden.nunique() < 2:
        raise ValueError("Renoir downstream 没有产生至少两个空间活性域")
    if not np.isfinite(np.asarray(domain.X)).all() or not np.isfinite(np.asarray(program.X)).all():
        raise ValueError("Renoir downstream 原始分数含非有限值")
    domain.write_h5ad(native_dir / "renoir_domains_unscaled.h5ad")
    program.write_h5ad(native_dir / "renoir_programs_unscaled.h5ad")
    write_json(native_dir / "ligand_target_programs.json", programs)

    sc.tl.rank_genes_groups(domain, "leiden", method="wilcoxon", use_raw=False, pts=True)
    marker_frame = sc.get.rank_genes_groups_df(domain, group=None)
    marker_frame.to_csv(native_dir / "domain_pair_markers.tsv", sep="\t", index=False)
    graph = neighborhood(spatial_data.obs["array_row"].tolist(), spatial_data.obs["array_col"].tolist(),
                         technology=use_radius, radius=radius)
    valid_degree = (np.asarray(graph) >= 0).sum(axis=1)
    if valid_degree.max(initial=0) > integer(cfg.get("maximum_neighbors", 1000), "maximum_neighbors", 1):
        raise ValueError("Renoir neighborhood 图超过配置的单点邻居上限")

    primary = scores[0]; score_df = primary.to_df(); domain_labels = domain.obs.leiden.astype(str)
    program_df = program.to_df()
    spatial_meta = dict(coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                        physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    bundle = {
        "schema_version": 2, "dataset": cfg["dataset"], "method": "Renoir", "method_version": UPSTREAM_VERSION,
        "implementation": "Fixed upstream Renoir ISM×PEM spatial ligand-to-target neighborhood scoring with native de novo programs and Leiden activity domains",
        "research_question": cfg["research_question"],
        "figure_inapplicability": {
            "overview": "Renoir does not estimate an additive sender-to-receiver overview network; its complete ligand-to-target summaries and spatial domains are delivered in applicable families.",
            "circos": "Renoir scores ligand-to-target activity over spatial observations and does not estimate sender-to-receiver cell-type edges or additive flows suitable for a chord diagram.",
            "cellchat_patterns": "Renoir de novo ligand-target programs are correlation clusters, not CellChat NMF patterns.",
            "pathway_sankey": "Neighborhood scores and absolute SVD activities are not conserved or additive molecular flow shares.",
            "condition_effects": "One spatial section is analyzed and no donor-level condition contrast is estimated.",
            "hierarchy": "Renoir has ligand-to-target associations but no identified sender and receiver cell populations for a sender/receiver hierarchy.",
            "roles": "Renoir does not estimate sender or receiver cell-type centrality.",
            "intracellular": "Ligand-target priors are scored as endpoints; Renoir does not reconstruct a receptor-to-TF-to-target intracellular path.",
            "factors": "The de novo program SVD is delivered as neighborhood response; it is not a tensor, MOFA or NMF communication factor model.",
            "enrichment": "No pathway over-representation test with a declared gene universe is performed.",
            "spatial_direction": "Renoir uses symmetric neighborhoods and does not fit a continuous direction field.",
            "relay_dynamic": "Renoir fits neither temporal trajectories nor multi-hop relay chains.",
            "special_molecules": "The supplied resources contain gene ligands, receptors and targets; no metabolite or neurotransmitter-specific model is fitted.",
            "functional_clinical": "No donor-level functional or clinical association is estimated."
        },
        "provenance": {
            "input_sha256": digest(paths["spatial_input"]), "input_provenance": cfg["spatial_input_provenance"],
            "reference_sha256": digest(paths["reference_input"]), "reference_provenance": cfg["reference_input_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"], "parameters": cfg,
            "ligand_target_sha256": digest(paths["ligand_target_resource"]), "ligand_target_provenance": cfg["ligand_target_provenance"],
            "ligand_receptor_sha256": digest(paths["ligand_receptor_resource"]), "ligand_receptor_provenance": cfg["ligand_receptor_provenance"],
            "celltype_proportions_sha256": digest(paths["celltype_proportions"]), "celltype_proportions_provenance": cfg["celltype_proportions_provenance"],
            "upstream": {"url": "https://github.com/Zafar-Lab/Renoir", "commit": UPSTREAM_COMMIT, "version": UPSTREAM_VERSION,
                         "paper_doi": "10.1038/s41467-026-72388-7", "license_status": "README/setup classify MIT, but fixed commit contains no LICENSE file"},
            "source_sha256": SOURCE_HASHES, "python_versions": versions, "native_artifacts": "native_results/native_artifacts.json",
            "statistical_semantics": {
                "neighborhood_score": "The upstream product of graph-summed min-max-scaled PEM cell-type expression enrichment and ISM ligand-target mutual-information terms after receptor eligibility gating; it is a within-run activity score, not a probability.",
                "receptor_gate": "A ligand is eligible for a reference cell type when at least one measured receptor has reference mean expression >=0.1, exactly as fixed upstream.",
                "domain": "Leiden community in the ligand-target score space computed by fixed upstream downstream_analysis.",
                "program": "A fixed-upstream dynamic-tree or HDBSCAN cluster of correlated ligand-target score profiles; activity is the absolute first TruncatedSVD component, so sign is intentionally discarded upstream.",
                "domain_marker": "Scanpy cell/spot-level Wilcoxon ranking on neighborhood scores; descriptive within-section evidence only, not donor-level inference."
            },
            "limitations": [
                "Renoir activity is scaled from extrema within the analyzed graph and cannot be compared as an absolute effect size across datasets.",
                "Different gene panels, ligand-target priors, ligand-receptor priors, reference composition and graph radius alter eligible molecules and score ranges.",
                "The core method reports no permutation P value or donor-level uncertainty for neighborhood scores.",
                "The upstream zero-expression entropy safeguard inserts 1e-20 at a random reference cell; multi-seed score concordance is therefore reported.",
                "The upstream de novo DHC implementation passes a square distance matrix to scipy linkage and emits a ClusterWarning; its exact result is retained and disclosed.",
                "The upstream program activity takes the absolute first SVD component and then scales returned objects; its .raw assignment is also changed in place, so this adapter captures the same pre-scaling formula before calling downstream_analysis.",
                "Leiden domains and Wilcoxon rankings use spatial cells/spots as observations and do not establish condition specificity or population-level significance.",
                "Ligand-to-target association, receptor eligibility and spatial co-occurrence do not establish secretion, receptor activation, transcriptional causality or therapeutic mechanism.",
                "The fixed upstream commit declares MIT in README/setup metadata but does not include a LICENSE file."
            ]
        }, "tables": []
    }
    celltypes = spatial_data.obs.get(cfg.get("spatial_celltype_key", "celltype"))
    if celltypes is not None and not celltypes.isna().any():
        add_table(bundle, output_root, "renoir_cell_types", "spatial_points",
                  [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=None, label=str(label))
                   for cell, (x, y), label in zip(spatial_data.obs_names, coordinates, celltypes)],
                  "Supplied spatial cell annotation, independent of Renoir scores.", value_kind="category",
                  title="Renoir spatial input contexts", **spatial_meta)
    qc = {"Spatial observations": spatial_data.n_obs, "Measured genes": spatial_data.n_vars,
          "Reference observations": reference.n_obs, "Reference cell types": reference.obs.celltype.nunique(),
          "Candidate ligand-target pairs": len(lt), "Effective ligand-target scores": primary.n_vars,
          "Graph directed entries including self": int(valid_degree.sum()), "Median neighbors including self": float(np.median(valid_degree)),
          "Activity domains": domain.obs.leiden.nunique(), "De novo programs": program.n_vars}
    add_table(bundle, output_root, "renoir_graph_qc", "matrix",
              [dict(row="Renoir run", column=key, value=float(value)) for key, value in qc.items()],
              "Observed input, eligibility, graph and downstream output counts from the fixed native workflow.",
              value_kind="count", figure_role="renoir_graph_qc", row_order=["Renoir run"], column_order=list(qc), title="Renoir eligibility and graph QC")
    summary_columns = ["Nonzero observations", "Mean neighborhood score", "Median neighborhood score", "Maximum neighborhood score"]
    summary_rows = []
    for pair in score_df:
        values = score_df[pair].to_numpy()
        for column, value in zip(summary_columns, [(values > 0).sum(), values.mean(), np.median(values), values.max()]):
            summary_rows.append(dict(row=pair.replace(":", "→"), column=column, value=float(value)))
    add_table(bundle, output_root, "renoir_pair_summary", "matrix", summary_rows,
              "Complete per-pair prevalence and descriptive neighborhood-score summaries; no P values are inferred.",
              value_kind="native_score", figure_role="renoir_pair_summary", column_order=summary_columns, title="Renoir ligand-to-target activity")
    ordered_pairs = sorted(score_df, key=lambda pair: (-float(score_df[pair].mean()), pair))
    for pair in ordered_pairs[:integer(cfg.get("top_spatial_pairs", 4), "top_spatial_pairs", 1, 12)]:
        add_table(bundle, output_root, f"renoir_pair_{safe_id(pair)}", "spatial_points",
                  [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=float(value))
                   for cell, (x, y), value in zip(primary.obs_names, coordinates, score_df[pair])],
                  f"Complete fixed-upstream Renoir neighborhood score for {pair}; selection for display used mean score only after all candidates were retained in the summary table.",
                  value_kind="native_score", figure_role="spatial_hotspot", axis_label="Renoir neighborhood score",
                  title=pair.replace(":", "→") + " spatial activity", **spatial_meta)
    add_table(bundle, output_root, "renoir_domains", "spatial_points",
              [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=None, label="Domain " + label)
               for cell, (x, y), label in zip(domain.obs_names, coordinates, domain_labels)],
              "Fixed-upstream Leiden domain in ligand-target neighborhood-score space.", value_kind="category",
              title="Renoir spatial activity domains", **spatial_meta)
    domain_order = sorted(domain_labels.unique(), key=lambda x: (int(x) if x.isdigit() else x))
    domain_pair = score_df.assign(domain=domain_labels.to_numpy()).groupby("domain", observed=True).mean()
    shown_pairs = ordered_pairs[:integer(cfg.get("top_domain_pairs", 20), "top_domain_pairs", 3, 50)]
    add_table(bundle, output_root, "renoir_domain_pair_activity", "matrix",
              [dict(row="Domain " + domain_id, column=pair.replace(":", "→"), value=float(domain_pair.loc[domain_id, pair]))
               for domain_id in domain_order for pair in shown_pairs],
              "Mean unscaled Renoir neighborhood score per native activity domain for predeclared display-ranked ligand-target pairs.",
              value_kind="native_score", figure_role="renoir_domain_pair_activity",
              row_order=["Domain " + x for x in domain_order], column_order=[x.replace(":", "→") for x in shown_pairs], title="Renoir domain activity profiles")
    evidence_columns = ["Wilcoxon score", "Log fold change", "P value", "BH adjusted P", "Within-domain nonzero fraction", "Outside-domain nonzero fraction"]
    evidence_rows = []
    marker_frame["group"] = marker_frame["group"].astype(str)
    for domain_id in domain_order:
        subset = marker_frame.loc[marker_frame.group == domain_id].sort_values(["pvals_adj", "scores", "names"], ascending=[True, False, True]).head(8)
        inside = domain_labels == domain_id
        for row in subset.itertuples(index=False):
            values = [row.scores, row.logfoldchanges, row.pvals, row.pvals_adj,
                      (score_df.loc[inside, row.names] > 0).mean(), (score_df.loc[~inside, row.names] > 0).mean()]
            label = f"Domain {domain_id} | {str(row.names).replace(':', '→')}"
            evidence_rows.extend(dict(row=label, column=column, value=float(value)) for column, value in zip(evidence_columns, values))
    add_table(bundle, output_root, "renoir_domain_pair_evidence", "matrix", evidence_rows,
              "Cell/spot-level Scanpy Wilcoxon ranking plus observed score prevalence; P and BH values describe this one section and are not donor-level evidence.",
              value_kind="native_score", figure_role="renoir_domain_evidence", column_order=evidence_columns, title="Renoir domain-defining ligand-target scores")
    program_mean = program_df.assign(domain=domain_labels.to_numpy()).groupby("domain", observed=True).mean()
    add_table(bundle, output_root, "renoir_program_domain_activity", "matrix",
              [dict(row=str(name), column="Domain " + domain_id, value=float(program_mean.loc[domain_id, name]))
               for name in program_df.columns for domain_id in domain_order],
              "Mean pre-scaling absolute first-SVD activity of each fixed-upstream de novo ligand-target program in each native domain.",
              value_kind="native_score", figure_role="renoir_program_activity",
              row_order=list(map(str, program_df.columns)), column_order=["Domain " + x for x in domain_order], title="Renoir de novo program activity")
    for name in program_df.columns:
        add_table(bundle, output_root, f"renoir_program_{safe_id(name)}", "spatial_points",
                  [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), value=float(value))
                   for cell, (x, y), value in zip(program.obs_names, coordinates, program_df[name])],
                  f"Complete pre-scaling absolute first-SVD activity for Renoir de novo program {name}.",
                  value_kind="native_score", figure_role="spatial_hotspot", axis_label="Absolute first-SVD activity",
                  title=f"Renoir {name} spatial activity", **spatial_meta)
    embedding = np.asarray(domain_scaled.obsm["X_umap"], dtype=float)
    add_table(bundle, output_root, "renoir_score_umap_domains", "embedding_points",
              [dict(sample=sample, cell=str(cell), x=float(x), y=float(y), label="Domain " + label)
               for cell, (x, y), label in zip(domain.obs_names, embedding, domain_labels)],
              "Fixed-upstream UMAP of scaled ligand-target neighborhood-score profiles, colored by the fixed-upstream Leiden domain.",
              value_kind="category", title="Renoir score-space domains", axis_label="UMAP",
              embedding_method="UMAP", embedding_provenance="Renoir downstream_analysis on scaled neighborhood scores")
    stability_rows = []
    for first, seed_a in enumerate(seeds):
        for second, seed_b in enumerate(seeds):
            value = float(spearmanr(np.asarray(scores[first].X).ravel(), np.asarray(scores[second].X).ravel()).statistic)
            stability_rows.append(dict(row=f"seed {seed_a}", column=f"seed {seed_b}", value=value))
    add_table(bundle, output_root, "renoir_seed_stability", "matrix", stability_rows,
              "Pairwise Spearman correlation of the complete fixed-upstream neighborhood-score matrix across entropy safeguard seeds.",
              value_kind="native_score", figure_role="renoir_stability", row_order=[f"seed {x}" for x in seeds],
              column_order=[f"seed {x}" for x in seeds], title="Renoir score stability")
    native_artifacts = {"copied_inputs": copied_inputs, "score_files": [f"neighborhood_scores_seed_{seed}.h5ad" for seed in seeds],
                        "domain_file": "renoir_domains_unscaled.h5ad", "program_file": "renoir_programs_unscaled.h5ad",
                        "program_membership": "ligand_target_programs.json", "domain_markers": "domain_pair_markers.tsv",
                        "native_log": "renoir_native.log", "graph": {"mode": cfg["graph_mode"], "radius": radius,
                        "entries_including_self": int(valid_degree.sum()), "degree_min": int(valid_degree.min()),
                        "degree_median": float(np.median(valid_degree)), "degree_max": int(valid_degree.max())},
                        "effective_pairs": int(primary.n_vars), "domains": int(domain.obs.leiden.nunique()),
                        "programs": int(program.n_vars), "seeds": seeds}
    write_json(native_dir / "native_artifacts.json", native_artifacts)
    write_json(output_root / "bundle.json", bundle)
    state.update(status="complete", bundle_sha256=digest(output_root / "bundle.json"), runtime_seconds=time.time() - started,
                 analysis_tier=tier, effective_pairs=int(primary.n_vars), domains=int(domain.obs.leiden.nunique()),
                 programs=int(program.n_vars), graph_entries=int(valid_degree.sum()))
    write_json(output_root / "run_state.json", state)
    return 0


def main():
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
