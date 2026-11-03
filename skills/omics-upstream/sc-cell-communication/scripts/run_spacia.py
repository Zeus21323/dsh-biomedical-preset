#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["numpy==1.26.4", "pandas==2.0.3", "scipy==1.10.1", "scikit-learn==1.3.0", "matplotlib==3.7.2", "anndata==0.10.8", "h5py==3.11.0"]
# ///
"""Run a fixed Spacia Bayesian MIL analysis and preserve native MCMC evidence."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.spatial.distance import cdist

from communication_contract import add_table, digest, new_output, write_json, write_table


UPSTREAM_COMMIT = "11809bbe38e9107ab2b4444466958fdf7ab1e369"
UPSTREAM_VERSION = "commit-11809bb"
SOURCE_HASHES = {
    "LICENSE": "94ec0ba2f02d6a428a51b6cbeaaaa7edace6eb04355bf6f9d5e790826a6f03c4",
    "spacia.py": "7668135fd541039562a3c4267522b6733fca12f4cfed4b60a509e64b0f929372",
    "spacia/spacia_job.R": "92a3e43737d8c1dbcb9e084e8ff8b8106a7cb45ad72f42ad68944f1c12d36f86",
    "spacia/Fun_MICProB_C2Cinter.cpp": "191d195c9537aa4bc58dac6c7563e1fe12904d2244a25eaf736b7c7285dff3c5",
    "spacia/MICProB_MIL_C2Cinter.R": "0a6894aaa1c2ab14d511488365762cedcad3cea400bfb6ddc5a5132d7196bb6f",
    "spacia/MIL_wrapper.R": "f5441402308526b56739d1c801b43685dccee41a38c01bcf8d4ed1ae76ecbfb0",
    "spacia/BetaB2MCMCPlots.R": "9a943bb8d6b40136eb0e7967c48ee2a78ace2b4bedcfa9f402942015779d4194",
}
PYTHON_VERSIONS = {
    "numpy": "1.26.4", "pandas": "2.0.3", "scipy": "1.10.1",
    "scikit-learn": "1.3.0", "matplotlib": "3.7.2",
    "anndata": "0.10.8", "h5py": "3.11.0",
}
R_VERSIONS = {
    "R": "4.5.3", "Rcpp": "1.1.2", "RcppArmadillo": "15.6.0.1",
    "RcppProgress": "0.4.2", "rjson": "0.2.23", "coda": "0.19.4.1",
    "ggmcmc": "1.5.1.2",
}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def finite(value, name, low=None, high=None):
    value = float(value)
    if not np.isfinite(value) or low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是有效有限数")
    return value


def integer(value, name, low=1, high=None):
    if type(value) is not int or value < low or high is not None and value > high:
        raise ValueError(f"{name} 必须是不小于 {low}" + (f"且不超过 {high}" if high is not None else "") + " 的整数")
    return value


def dense(value):
    return value.toarray() if sparse.issparse(value) else np.asarray(value)


def verify_native(source_root: Path, rscript: Path):
    for relative, expected in SOURCE_HASHES.items():
        path = source_root / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Spacia 固定源码缺失或摘要不符: {relative}")
    commit = subprocess.run(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True,
                            capture_output=True, check=True).stdout.strip()
    if commit != UPSTREAM_COMMIT:
        raise ValueError(f"Spacia 固定源码提交应为 {UPSTREAM_COMMIT}，当前为 {commit}")
    if sys.version_info[:2] != (3, 10):
        raise ValueError("Spacia 固定 Python 环境需要 Python 3.10")
    python_versions = {}
    for package, expected in PYTHON_VERSIONS.items():
        actual = importlib.metadata.version(package)
        if actual != expected:
            raise ValueError(f"Spacia 固定环境要求 {package}=={expected}，当前为 {actual}")
        python_versions[package] = actual
    if not rscript.is_file():
        raise ValueError("Spacia 配置的 Rscript 不存在")
    expression = (
        'cat(paste0("R\\t",getRversion(),"\\n"));'
        'for(p in c("Rcpp","RcppArmadillo","RcppProgress","rjson","coda","ggmcmc"))'
        'cat(paste0(p,"\\t",as.character(packageVersion(p)),"\\n"))'
    )
    check = subprocess.run([str(rscript), "-e", expression], text=True, capture_output=True, check=False)
    if check.returncode:
        raise ValueError("Spacia R 环境检查失败: " + (check.stderr.strip() or check.stdout.strip()))
    r_versions = dict(line.split("\t", 1) for line in check.stdout.splitlines() if "\t" in line)
    for package, expected in R_VERSIONS.items():
        if r_versions.get(package) != expected:
            raise ValueError(f"Spacia 固定 R 环境要求 {package}=={expected}，当前为 {r_versions.get(package)}")
    return python_versions, r_versions


def feature_argument(features, label, stage: Path, genes):
    if not isinstance(features, list) or not features:
        raise ValueError(f"{label} 必须是非空列表")
    if all(isinstance(item, str) for item in features):
        values = []
        for value in features:
            if not value or any(x in value for x in ",|/\\"):
                raise ValueError(f"{label} 单基因名称无效: {value!r}")
            if value not in genes:
                raise ValueError(f"{label} 基因不在表达矩阵: {value}")
            values.append(value)
        if len(set(values)) != len(values):
            raise ValueError(f"{label} 不能重复")
        return ",".join(values), [{"name": value, "genes": [value]} for value in values], "single_genes"
    if not all(isinstance(item, dict) for item in features):
        raise ValueError(f"{label} 不能混用单基因字符串与基因集对象")
    rows, normalized = [], []
    for item in features:
        name, members = item.get("name"), item.get("genes")
        if not isinstance(name, str) or not name or any(x in name for x in ",/\\"):
            raise ValueError(f"{label} 基因集名称无效")
        if not isinstance(members, list) or len(members) < 2 or len(set(members)) != len(members):
            raise ValueError(f"{label} 的每个显式基因集至少需要2个唯一基因")
        missing = sorted(set(members) - set(genes))
        if missing:
            raise ValueError(f"{label} 基因集 {name} 缺少基因: " + ", ".join(missing))
        rows.append([name, *members]); normalized.append({"name": name, "genes": members})
    if len({item["name"] for item in normalized}) != len(normalized):
        raise ValueError(f"{label} 基因集名称不能重复")
    path = stage / f"{label}.csv"
    pd.DataFrame(rows).to_csv(path, header=False, index=False)
    return str(path), normalized, "gene_sets"


def prepare_input(cfg, base: Path, stage: Path):
    required = ("dataset", "research_question", "input", "input_provenance", "native_root", "rscript",
                "expression_layer", "expression_scale", "normalization_definition", "coordinate_unit",
                "coordinate_provenance", "receiver_cluster", "sender_cluster", "response_features", "sender_features")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("Spacia 配置缺少: " + key)
    input_path = resolve(base, cfg["input"])
    data = ad.read_h5ad(input_path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞和基因 ID 必须唯一")
    if data.n_obs < 20 or data.n_vars < 2:
        raise ValueError("Spacia 至少需要20个细胞和2个基因")
    if data.n_obs > integer(cfg.get("maximum_cells", 20000), "maximum_cells", 20):
        raise ValueError("输入细胞数超过 maximum_cells")
    sample_key, cell_type_key = cfg.get("sample_key", "sample"), cfg.get("cell_type_key", "cell_type")
    for key in (sample_key, cell_type_key):
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
    samples = list(dict.fromkeys(data.obs[sample_key].astype(str)))
    if len(samples) != 1:
        raise ValueError("Spacia 原生模型每次只允许一个空间切片；跨样本需分别拟合后再作供体层比较")
    receiver, sender = str(cfg["receiver_cluster"]), str(cfg["sender_cluster"])
    cell_types = data.obs[cell_type_key].astype(str)
    if receiver not in set(cell_types) or sender not in set(cell_types):
        raise ValueError("receiver_cluster 或 sender_cluster 不在细胞类型注释中")
    if receiver == sender and not cfg.get("allow_self_pairs", False):
        raise ValueError("同一发送/接收群会包含距离0的自身细胞；如确需自分泌分析请显式设置 allow_self_pairs=true")
    spatial_key = cfg.get("spatial_key", "spatial")
    coordinates = np.asarray(data.obsm.get(spatial_key), dtype=float)
    if coordinates.shape != (data.n_obs, 2) or not np.isfinite(coordinates).all():
        raise ValueError("Spacia 需要逐细胞/spot 对齐的有限二维坐标")
    if len(np.unique(coordinates, axis=0)) != data.n_obs:
        raise ValueError("空间坐标重复；必须先核查细胞分割身份")
    unit = cfg["coordinate_unit"]
    if unit not in ("um", "pixel", "native"):
        raise ValueError("coordinate_unit 只接受 um、pixel 或 native")
    if unit == "native" and not cfg.get("physical_scale_unavailable"):
        raise ValueError("原生坐标单位必须明确 physical_scale_unavailable=true")
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
        target = finite(cfg.get("normalization_target_sum", 10000), "normalization_target_sum", 1)
        totals = matrix.sum(axis=1)
        if np.any(totals <= 0):
            raise ValueError("原始计数含总量为0的细胞")
        matrix = np.log1p(matrix / totals[:, None] * target)
    elif scale != "log1p_cpm":
        raise ValueError("expression_scale 只接受 counts 或 log1p_cpm")
    if not np.any(matrix > 0):
        raise ValueError("Spacia 分析表达层没有正表达")
    original_ids = list(map(str, data.obs_names))
    native_ids = [f"spacia_cell_{i:07d}" for i in range(data.n_obs)]
    id_map = dict(zip(native_ids, original_ids))
    expression = pd.DataFrame(matrix, index=native_ids, columns=data.var_names.astype(str))
    expression.index.name = "cell"
    expression_path = stage / "expression_log1p_cpm.tsv"
    expression.to_csv(expression_path, sep="\t")
    metadata = pd.DataFrame({"X": coordinates[:, 0], "Y": coordinates[:, 1], "cell_type": cell_types.values}, index=native_ids)
    metadata.index.name = "cell"
    metadata_path = stage / "spacia_metadata.tsv"
    metadata.to_csv(metadata_path, sep="\t")
    identity_path = stage / "cell_identity_map.tsv"
    pd.DataFrame({"spacia_cell": native_ids, "original_cell": original_ids}).to_csv(identity_path, sep="\t", index=False)
    response_arg, responses, response_mode = feature_argument(cfg["response_features"], "response_features", stage, expression.columns)
    sender_arg, signals, sender_mode = feature_argument(cfg["sender_features"], "sender_features", stage, expression.columns)
    if cfg.get("correlation_aggregation", False) and (response_mode != "single_genes" or sender_mode != "single_genes"):
        raise ValueError("相关聚合只适用于单基因列表；显式基因集不得再作数据驱动扩展")
    corr_method = str(cfg.get("corr_agg_method", "simple"))
    if corr_method not in ("simple", "weighted"):
        raise ValueError("corr_agg_method 只接受 simple 或 weighted")
    response_cutoff = cfg.get("response_exp_cutoff", 0.5)
    if response_cutoff != "auto":
        response_cutoff = finite(response_cutoff, "response_exp_cutoff")
        if not 0 < response_cutoff < 1:
            raise ValueError("response_exp_cutoff 数值必须严格位于0和1之间，或使用 auto")
    r_idx = np.flatnonzero(cell_types.values == receiver)
    s_idx = np.flatnonzero(cell_types.values == sender)
    if len(r_idx) < integer(cfg.get("minimum_receiver_cells", 20), "minimum_receiver_cells", 2):
        raise ValueError("接收细胞数不足")
    if len(s_idx) < integer(cfg.get("minimum_sender_cells", 20), "minimum_sender_cells", 2):
        raise ValueError("发送细胞数不足")
    distances = cdist(coordinates[r_idx], coordinates[s_idx])
    if cfg.get("dist_cutoff") is None:
        neighbors = integer(cfg.get("n_neighbors", 10), "n_neighbors", 1, len(s_idx))
        dist_cutoff = float(np.median(np.partition(distances, neighbors - 1, axis=1)[:, neighbors - 1]))
        distance_rule = f"median distance to each receiver's {neighbors}th nearest declared sender"
    else:
        dist_cutoff = finite(cfg["dist_cutoff"], "dist_cutoff", np.finfo(float).eps)
        distance_rule = "predeclared exact cutoff"
    bag_size = integer(cfg.get("bag_size", 2), "bag_size", 1)
    bag_counts = np.sum(distances <= dist_cutoff, axis=1)
    eligible = bag_counts >= bag_size
    if int(eligible.sum()) < integer(cfg.get("minimum_bags", 20), "minimum_bags", 2):
        raise ValueError("满足邻域最小发送细胞数的接收细胞过少")
    number_bags = integer(cfg.get("number_bags", 5000), "number_bags", 1)
    if int(eligible.sum()) > number_bags and not cfg.get("allow_bag_subsampling", False):
        raise ValueError(
            f"共有 {int(eligible.sum())} 个合格 receiver bag，但 number_bags={number_bags}；"
            "上游会静默随机抽样，请增大 number_bags 或显式设置 allow_bag_subsampling=true"
        )
    maximum_edges = integer(cfg.get("maximum_candidate_edges", 2_000_000), "maximum_candidate_edges", 1)
    if int(bag_counts[eligible].sum()) > maximum_edges:
        raise ValueError("候选细胞对超过 maximum_candidate_edges")
    display_metadata = pd.DataFrame({"X": coordinates[:, 0], "Y": coordinates[:, 1], "cell_type": cell_types.values}, index=original_ids)
    return (data, input_path, expression_path, metadata_path, identity_path, display_metadata, id_map, samples[0], receiver, sender,
            response_arg, sender_arg, responses, signals, dist_cutoff, distance_rule, bag_size, bag_counts, r_idx,
            number_bags, response_cutoff, corr_method)


def mcmc_parameters(cfg):
    values = cfg.get("mcmc", {})
    ntotal = integer(values.get("ntotal", 50000), "mcmc.ntotal", 100)
    nwarm = integer(values.get("nwarm", 25000), "mcmc.nwarm", 0)
    nthin = integer(values.get("nthin", 10), "mcmc.nthin", 1)
    nchain = integer(values.get("nchain", 3), "mcmc.nchain", 1, 16)
    if nwarm >= ntotal or (ntotal - nwarm) % nthin:
        raise ValueError("MCMC 需要 ntotal>nwarm 且 (ntotal-nwarm) 可被 nthin 整除")
    chain_size = (ntotal - nwarm) // nthin
    if chain_size < 51:
        raise ValueError("每条链至少需要51个保留位置，兼容上游去除初值后的50次检验抽样")
    tier = cfg.get("analysis_tier", "publication")
    if tier not in ("publication", "exploratory"):
        raise ValueError("analysis_tier 只接受 publication 或 exploratory")
    if tier == "publication" and (ntotal < 50000 or nwarm < 25000 or nthin > 10 or nchain < 3):
        raise ValueError("publication 模式至少要求作者默认的 50000/25000/10/3 MCMC 设置")
    return ntotal, nwarm, nthin, nchain, chain_size, tier


def nullable(value):
    return None if value is None or not np.isfinite(float(value)) else float(value)


def safe_id(value):
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_") or "response"


def split_chains(frame, nchain, chain_size):
    stored = chain_size + 1
    if len(frame) != nchain * stored:
        raise ValueError(f"Spacia 原始链长度 {len(frame)} 与声明的 {nchain}×({chain_size}+1个初值) 不符")
    return [frame.iloc[i * stored + 1:(i + 1) * stored].reset_index(drop=True) for i in range(nchain)]


def read_native(upstream_out: Path, nchain: int, chain_size: int):
    needed = ["B_and_FDR.csv", "Pathway_betas.csv", "Interactions.csv"]
    for name in needed:
        if not (upstream_out / name).is_file():
            raise ValueError("Spacia 上游汇总缺失: " + name)
    log = (upstream_out / "spacia_log.txt").read_text(errors="replace")
    if "Traceback" in log or "failed without outputs" in log:
        raise ValueError("Spacia 上游日志报告失败")
    with (upstream_out / "model_input" / "receiver_pathways.json").open() as stream:
        response_pathways = json.load(stream)
    with (upstream_out / "model_input" / "sender_pathways.json").open() as stream:
        sender_pathways = json.load(stream)
    response_names, sender_names = list(response_pathways), list(sender_pathways)
    if not response_names or not sender_names:
        raise ValueError("Spacia 没有产生可拟合的 response 或 signal 特征")
    beta_summary = pd.read_csv(upstream_out / "Pathway_betas.csv", index_col=0)
    interactions = pd.read_csv(upstream_out / "Interactions.csv", index_col=0)
    metadata = pd.read_csv(upstream_out / "model_input" / "metadata.txt", sep="\t", index_col=0)
    template = metadata.dropna(subset=["Sender_cells"]).Sender_cells.astype(str).str.split(",").explode().reset_index()
    template.columns = ["Receiver", "Sender"]
    if len(interactions) != len(template) * len(response_names):
        raise ValueError("Spacia 细胞对汇总行数与实际邻域展开不一致")
    response_data = {}
    for response in response_names:
        folder = upstream_out / response
        rlog = folder / f"{response}_log.txt"
        if not rlog.is_file() or "Time difference" not in rlog.read_text(errors="replace"):
            raise ValueError(f"Spacia response {response} 的 R 任务没有完成标记")
        beta = pd.read_csv(folder / f"{response}_beta.txt", sep="\t", index_col=0)
        b = pd.read_csv(folder / f"{response}_b.txt", sep="\t", index_col=0)
        pip = pd.read_csv(folder / f"{response}_pip.txt", sep="\t", index_col=0)
        recal = pd.read_csv(folder / f"{response}_pip_recal.txt", sep="\t", index_col=0)
        fdr = pd.read_csv(folder / f"{response}_FDRs.txt", sep="\t", index_col=0)
        psrf = pd.read_csv(folder / f"{response}_PSRF.txt", sep="\t", index_col=0)
        if beta.shape[1] != len(sender_names) or len(pip) != len(template) or len(recal) != len(template):
            raise ValueError(f"Spacia response {response} 的原始输出维度不一致")
        beta.columns = sender_names
        response_data[response] = dict(beta=beta, b=b, pip=pip, recal=recal, fdr=fdr, psrf=psrf,
                                       beta_chains=split_chains(beta, nchain, chain_size),
                                       b_chains=split_chains(b, nchain, chain_size))
    return response_names, sender_names, response_pathways, sender_pathways, beta_summary, interactions, metadata, template, response_data


def run(config, output):
    config = Path(config).resolve(); base = config.parent
    cfg = json.loads(config.read_text())
    output_root = new_output(output)
    state = {"schema_version": 2, "status": "running", "config_sha256": digest(config)}
    write_json(output_root / "run_config.json", cfg); write_json(output_root / "run_state.json", state)
    source_root = resolve(base, cfg.get("native_root", "")); rscript = resolve(base, cfg.get("rscript", ""))
    python_versions, r_versions = verify_native(source_root, rscript)
    ntotal, nwarm, nthin, nchain, chain_size, tier = mcmc_parameters(cfg)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="spacia_native_") as temp:
        stage = Path(temp)
        (data, input_path, expression_path, metadata_path, identity_path, metadata, id_map, sample, receiver, sender,
         response_arg, sender_arg, requested_responses, requested_signals, dist_cutoff, distance_rule,
         bag_size, bag_counts, receiver_indices, number_bags, response_cutoff, corr_method) = prepare_input(cfg, base, stage)
        upstream_out = stage / "upstream"
        command = [sys.executable, str(source_root / "spacia.py"), str(expression_path), str(metadata_path),
                   "-rc", receiver, "-sc", sender, "-rf", response_arg, "-sf", sender_arg,
                   "-d", str(dist_cutoff), "-b", str(bag_size), "-nb", str(number_bags),
                   "-m", f"{ntotal},{nwarm},{nthin},{nchain}", "-rec", str(response_cutoff),
                   "-o", str(upstream_out)]
        if not cfg.get("correlation_aggregation", False):
            command.append("--corr_agg")
        command += ["-nc", str(integer(cfg.get("num_corr_genes", 100), "num_corr_genes", 1)),
                    "-cm", corr_method]
        environment = dict(os.environ)
        environment["PATH"] = str(rscript.parent) + os.pathsep + environment.get("PATH", "")
        environment.update({"OMP_NUM_THREADS": str(integer(cfg.get("omp_threads", 1), "omp_threads", 1, 16)),
                            "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        result = subprocess.run(command, text=True, capture_output=True, env=environment,
                                timeout=integer(cfg.get("timeout_seconds", 86400), "timeout_seconds", 60))
        (output_root / "native_stdout.log").write_text(result.stdout)
        (output_root / "native_stderr.log").write_text(result.stderr)
        if result.returncode:
            failed = output_root / "failed_native_results"
            failed.mkdir()
            for path in stage.iterdir():
                target = failed / path.name
                shutil.copytree(path, target) if path.is_dir() else shutil.copyfile(path, target)
            raise ValueError(f"Spacia 上游程序退出码 {result.returncode}；见 native_stderr.log 和 native_stdout.log")
        try:
            (response_names, sender_names, response_pathways, sender_pathways, beta_summary, interactions,
             native_metadata, template, response_data) = read_native(upstream_out, nchain, chain_size)
            native_dir = output_root / "native_results"
            shutil.copytree(upstream_out, native_dir / "upstream")
            shutil.copyfile(expression_path, native_dir / "expression_log1p_cpm.tsv")
            shutil.copyfile(metadata_path, native_dir / "spacia_metadata.tsv")
            shutil.copyfile(identity_path, native_dir / "cell_identity_map.tsv")
        except Exception:
            failed = output_root / "failed_native_results"
            failed.mkdir(exist_ok=True)
            for path in stage.iterdir():
                target = failed / path.name
                if target.exists():continue
                shutil.copytree(path, target) if path.is_dir() else shutil.copyfile(path, target)
            raise
    coordinates = metadata[["X", "Y"]]
    spatial_meta = dict(coordinate_unit=cfg["coordinate_unit"], coordinate_provenance=cfg["coordinate_provenance"],
                        physical_scale_unavailable=bool(cfg.get("physical_scale_unavailable")), y_down=bool(cfg.get("y_down")))
    bundle = {
        "schema_version": 2, "dataset": cfg["dataset"], "method": "Spacia", "method_version": UPSTREAM_VERSION,
        "implementation": "Fixed upstream Python/R Spacia Bayesian multiple-instance learning with independent native-chain extraction",
        "research_question": cfg["research_question"],
        "figure_inapplicability": {
            "overview": "A single Spacia run estimates one declared sender-to-receiver cellular context with non-additive signed feature effects; it is not a global communication network.",
            "circos": "Signed non-additive Spacia beta coefficients cannot be encoded as nonnegative chord widths.",
            "lr_evidence": "This run evaluates declared signal and response features without a ligand-receptor database or LR permutation screen.",
            "condition_effects": "One spatial section is fitted and no donor-level condition contrast is estimated.",
            "hierarchy": "One predeclared sender/receiver context does not identify a multi-cell-type hierarchy.",
            "roles": "Spacia primary-instance probabilities are local cell-pair responsibilities, not global sender/receiver centrality.",
            "cellchat_patterns": "Spacia does not fit CellChat NMF communication patterns.",
            "pathway_sankey": "Signal-response beta coefficients are signed and non-additive, so they are not molecular flow through sender-pathway-receiver layers.",
            "ligand_response": "No NicheNet-style ligand-to-target prior or perturbational response test is performed.",
            "intracellular": "No receptor-TF-target intracellular causal chain is inferred.",
            "factors": "No tensor, MOFA or NMF factor model is fitted.",
            "enrichment": "No gene-set over-representation test is performed.",
            "embedding": "Spacia does not compute a cell or molecular embedding.",
            "spatial_direction": "Directed sender-to-receiver cell pairs are estimated, but no continuous vector field is fitted.",
            "relay_dynamic": "No time, velocity or multi-hop relay model is fitted.",
            "special_molecules": "No metabolite, neurotransmitter or sensor-specific model is fitted.",
            "functional_clinical": "No donor-level functional or clinical association is estimated."
        },
        "provenance": {
            "input_sha256": digest(input_path), "input_provenance": cfg["input_provenance"],
            "coordinate_provenance": cfg["coordinate_provenance"], "parameters": cfg,
            "upstream": {"url": "https://github.com/yunguan-wang/Spacia", "commit": UPSTREAM_COMMIT,
                         "version": UPSTREAM_VERSION, "license": "BSD-3-Clause"},
            "source_sha256": SOURCE_HASHES, "python_versions": python_versions, "r_versions": r_versions,
            "prepared_expression": "native_results/expression_log1p_cpm.tsv",
            "native_artifacts": "native_results/native_artifacts.json",
            "statistical_semantics": {
                "bag": "Each modeled receiver cell is a bag; declared sender cells inside the fixed spatial cutoff are its instances.",
                "primary_instance_score": "Posterior mean primary-instance probability from the native pip matrix; it is response-specific but not signal-specific.",
                "distance_effect": "The native probit b.2 coefficient links normalized sender distance to primary-instance responsibility.",
                "signal_effect": "The native beta coefficient links sender feature expression to the binary receiver-response state within the declared cell-type context.",
                "fdr": "Native Bayesian FDR across primary-instance probability thresholds 0.1-0.9; undefined thresholds remain missing.",
                "p_q": "The upstream summaries retain two-sided one-sample t tests on sampled posterior draws, but the author Python code assumes 2500 stored rows per chain while native output stores 2501 including an initializer. Those P/q values remain only in native artifacts and are not used for figures or support calls."
            },
            "limitations": [
                "One Spacia run tests one spatial section and one sender-to-receiver cell-type context; it does not support donor-level condition inference.",
                "Cell-pair primary-instance scores are shared across signal features within a response model and must not be labeled as ligand-specific edge probabilities.",
                "Distance is normalized by the largest candidate distance inside the fitted bags; b is unitless and depends on the declared cutoff.",
                "Receiver response is dichotomized at a declared or estimated expression threshold, so conclusions can change with cutoff and normalization.",
                "Data-driven correlation aggregation changes the biological feature and may reduce cross-dataset comparability; the adapter defaults to explicit features.",
                "Upstream p/q values treat posterior draws as observations and do not represent independent donors; MCMC convergence and biological replication require separate checks.",
                "With multiple chains, the upstream Python P/q post-processing uses an off-by-one chain boundary. The adapter preserves those files but excludes their P/q fields from the semantic result bundle.",
                "Spacia associations do not establish ligand binding, downstream causality or a multi-hop mechanism."
            ]
        }, "tables": []
    }
    cell_rows = [dict(sample=sample, cell=str(cell), x=float(coordinates.loc[cell, "X"]), y=float(coordinates.loc[cell, "Y"]),
                      value=None, label=str(metadata.loc[cell, "cell_type"])) for cell in metadata.index]
    add_table(bundle, output_root, "spacia_cell_types", "spatial_points", cell_rows,
              "All measured cells colored by the supplied cell-type annotation; no inferred communication score is used.",
              value_kind="category", title="Spacia spatial cell contexts", **spatial_meta)
    bag_rows = []
    modeled_bags = native_metadata.dropna(subset=["Sender_cells"])["Sender_cells"]
    for native_cell, native_senders in modeled_bags.items():
        cell = id_map[str(native_cell)]
        count = len(str(native_senders).split(","))
        bag_rows.append(dict(sample=sample, cell=cell, x=float(coordinates.loc[cell, "X"]), y=float(coordinates.loc[cell, "Y"]),
                             value=float(count)))
    add_table(bundle, output_root, "spacia_bag_sizes", "spatial_points", bag_rows,
              "Number of declared sender cells inside the fixed cutoff for every modeled receiver bag; this is neighborhood coverage QC.",
              value_kind="count", figure_role="spatial_hotspot", axis_label="Sender cells per receiver bag",
              title="Spacia receiver-bag coverage", **spatial_meta)
    beta_rows, distance_rows, fdr_rows, psrf_rows = [], [], [], []
    for response in response_names:
        native = response_data[response]
        beta_combined = pd.concat(native["beta_chains"], ignore_index=True)
        b_combined = pd.concat(native["b_chains"], ignore_index=True)
        for signal in sender_names:
            values = beta_combined[signal].to_numpy(float)
            beta_rows.append(dict(row=response, column=signal, value=float(values.mean()),
                                  ci_low=float(np.quantile(values, .025)), ci_high=float(np.quantile(values, .975)),
                                  p_value=None, q_value=None,
                                  posterior_positive=float(np.mean(values > 0))))
        b_values = b_combined.iloc[:, 1].to_numpy(float)
        for column, value in (("Mean distance coefficient", b_values.mean()), ("2.5% posterior quantile", np.quantile(b_values, .025)),
                              ("97.5% posterior quantile", np.quantile(b_values, .975)),
                              ("Posterior probability below zero", np.mean(b_values < 0))):
            distance_rows.append(dict(row=response, column=column, value=float(value)))
        raw_fdr = native["fdr"].iloc[:, 0]
        for i, value in enumerate(raw_fdr, 1):
            threshold = i / 10
            selected = int(np.sum(native["pip"].to_numpy(float) > threshold))
            fdr_rows.append(dict(row=f"{threshold:.1f}", column=response,
                                 value=None if selected == 0 else nullable(value), selected_instances=selected))
        raw_psrf = native["psrf"].iloc[:, 0]
        if len(raw_psrf) != len(sender_names):
            raise ValueError("Spacia PSRF 数量与 sender feature 不一致")
        for signal, value in zip(sender_names, raw_psrf):
            psrf_rows.append(dict(row=response, column=signal, value=nullable(value)))
        response_interactions = interactions.loc[interactions.index.astype(str) == response].copy()
        expected = template.copy()
        if not response_interactions[["Receiver", "Sender"]].reset_index(drop=True).equals(expected.reset_index(drop=True)):
            raise ValueError(f"Spacia response {response} 的细胞对顺序与邻域展开不一致")
        scores = response_interactions["Primary_instance_score"].to_numpy(float)
        if not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
            raise ValueError("Spacia primary-instance score 不在 [0,1]")
        edge_rows = [dict(sample=sample, source_cell=id_map[str(row.Sender)], target_cell=id_map[str(row.Receiver)], value=float(score),
                          response=response) for row, score in zip(expected.itertuples(index=False), scores)]
        ident = safe_id(response)
        add_table(bundle, output_root, f"spacia_{ident}_primary_edges", "spatial_edges", edge_rows,
                  f"All candidate {sender}→{receiver} cell pairs for response {response}, weighted by native posterior mean primary-instance probability; the score is not signal-specific.",
                  value_kind="nonnegative_strength", directed=True, title=f"{response}: primary sender instances", **spatial_meta)
        hotspot = response_interactions.groupby("Receiver", sort=False).Primary_instance_score.max()
        hotspot_rows = [dict(sample=sample, cell=id_map[str(cell)], x=float(coordinates.loc[id_map[str(cell)], "X"]),
                             y=float(coordinates.loc[id_map[str(cell)], "Y"]), value=float(value)) for cell, value in hotspot.items()]
        add_table(bundle, output_root, f"spacia_{ident}_receiver_hotspot", "spatial_points", hotspot_rows,
                  f"Maximum incoming native primary-instance probability for each modeled receiver bag in response {response}; complete cell-pair scores remain in the paired edge table.",
                  value_kind="nonnegative_strength", figure_role="spatial_hotspot", axis_label="Maximum incoming primary-instance score",
                  title=f"{response}: receiver responsibility hotspot", **spatial_meta)
        trace_rows = []
        for chain_i, chain in enumerate(native["b_chains"], 1):
            stride = max(1, math.ceil(len(chain) / integer(cfg.get("maximum_trace_points", 300), "maximum_trace_points", 20, 2000)))
            for draw_i in range(0, len(chain), stride):
                trace_rows.append(dict(row=str(draw_i + 1), column=f"chain {chain_i}", value=float(chain.iloc[draw_i, 1])))
        add_table(bundle, output_root, f"spacia_{ident}_distance_trace", "matrix", trace_rows,
                  f"Post-warmup thinned native b.2 distance-coefficient trace for response {response}; the first stored initializer of each chain is excluded and display thinning is deterministic.",
                  value_kind="native_score", figure_role="spacia_mcmc_trace", axis_label="Distance coefficient b.2",
                  title=f"{response}: distance-coefficient MCMC trace")
    add_table(bundle, output_root, "spacia_signal_effects", "matrix", beta_rows,
              "Native posterior mean beta for every fitted response×sender-feature combination, with 2.5%/97.5% posterior quantiles and posterior sign probability from correctly separated chains; upstream off-by-one P/q values are not promoted into this table.",
              value_kind="native_score", figure_role="spacia_signal_effects", axis_label="Posterior mean beta",
              row_order=response_names, column_order=sender_names, title="Spacia sender-feature effects")
    add_table(bundle, output_root, "spacia_distance_effects", "matrix", distance_rows,
              "Native b.2 distance coefficient posterior summary for each response; distance is normalized within candidate bags, and intervals are posterior quantiles.",
              value_kind="native_score", figure_role="spacia_distance_effects", axis_label="Distance coefficient b.2",
              row_order=response_names, column_order=["Mean distance coefficient", "2.5% posterior quantile", "97.5% posterior quantile", "Posterior probability below zero"],
              title="Spacia distance effects")
    add_table(bundle, output_root, "spacia_primary_instance_fdr", "matrix", fdr_rows,
              "Native Bayesian FDR across primary-instance probability thresholds 0.1 through 0.9 for every fitted response; the adapter restores the upstream sentinel 1 to missing only when the raw pip matrix confirms zero selected instances.",
              value_kind="p_value", figure_role="spacia_fdr", axis_label="Bayesian FDR",
              row_order=[f"{i / 10:.1f}" for i in range(1, 10)], column_order=response_names,
              title="Spacia primary-instance FDR")
    add_table(bundle, output_root, "spacia_beta_psrf", "matrix", psrf_rows,
              "Native potential scale reduction factor (PSRF) for every response×sender-feature beta coefficient; missing values are retained when fewer than two chains were run.",
              value_kind="native_score", figure_role="spacia_psrf", axis_label="PSRF",
              row_order=response_names, column_order=sender_names, title="Spacia beta convergence")
    native_artifacts = {
        "upstream_directory": "upstream", "prepared_expression": "expression_log1p_cpm.tsv",
        "prepared_metadata": "spacia_metadata.tsv", "cell_identity_map": "cell_identity_map.tsv", "response_pathways": response_pathways,
        "sender_pathways": sender_pathways, "requested_response_features": requested_responses,
        "requested_sender_features": requested_signals, "command": command,
        "mcmc": {"ntotal": ntotal, "nwarm": nwarm, "nthin": nthin, "nchain": nchain, "chain_size": chain_size},
        "distance_cutoff": dist_cutoff, "distance_rule": distance_rule, "bag_size": bag_size,
        "eligible_bags_before_native_subsampling": int(np.sum(bag_counts >= bag_size)),
        "number_bags": number_bags, "allow_bag_subsampling": bool(cfg.get("allow_bag_subsampling", False)),
    }
    write_json(output_root / "native_results" / "native_artifacts.json", native_artifacts)
    write_json(output_root / "bundle.json", bundle)
    state.update(status="complete", bundle_sha256=digest(output_root / "bundle.json"), runtime_seconds=time.time() - started,
                 responses=response_names, sender_features=sender_names, modeled_bags=len(bag_rows),
                 candidate_cell_pairs=len(template), distance_cutoff=dist_cutoff, analysis_tier=tier)
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
