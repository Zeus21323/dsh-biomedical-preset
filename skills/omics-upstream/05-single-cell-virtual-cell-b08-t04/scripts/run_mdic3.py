#!/usr/bin/env python3
# /// script
# requires-python = "==3.9.18"
# dependencies = ["numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "scikit-learn==1.4.1.post1", "statsmodels==0.14.1"]
# ///
"""Run fixed MDIC3 source and package its native matrices and LR diagnostics."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from communication_contract import add_table, digest, new_output, write_json, write_table

COMMIT = "94f1a2a6de4fa5bb6b714b28c0778212ee3c82f3"
HASHES = {
    "README.md": "df1079a19f6918ce42be59c36b713ab2c75308b9b4d41c29cc4a79c965393f8e",
    "MDIC3.py": "9f61ccfbd38ac8a8826b49c07c8e655567bfde1eb72a3d5406ba774e66e5e64c",
    "MDIC3_LR.py": "7f385a4708076b5f9bf2f082465df6439c9c6bbf3109bb7fcc6a4b840d675a53",
    "MDIC3-env.yml": "881401ee9ea62c4e23eb4612500c896bc492fa848b1a52bd892817de05fad8e9",
}
VERSIONS = {"numpy": "1.26.4", "pandas": "2.2.1", "scipy": "1.12.0", "scikit-learn": "1.4.1.post1", "statsmodels": "0.14.1"}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def verify_source(root: Path) -> dict:
    for name, expected in HASHES.items():
        path = root / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"MDIC3固定源码缺失或摘要不符: {name}")
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if commit != COMMIT:
        raise ValueError(f"MDIC3源码提交不符: {commit}")
    if sys.version_info[:3] != (3, 9, 18):
        raise ValueError("MDIC3固定环境需要Python 3.9.18")
    observed = {name: importlib.metadata.version(name) for name in VERSIONS}
    if observed != VERSIONS:
        raise ValueError(f"MDIC3依赖版本不符: {observed}")
    return observed


def read_inputs(expression_path: Path, metadata_path: Path, grn_path: Path):
    expression = pd.read_csv(expression_path, sep=r"\s+", header=0, index_col=0).astype(float)
    metadata = pd.read_csv(metadata_path, sep="\t", header=None, names=["cell", "cell_type"], dtype=str)
    if expression.empty or expression.index.has_duplicates or expression.columns.has_duplicates:
        raise ValueError("MDIC3表达矩阵为空或基因/细胞身份重复")
    values = expression.to_numpy()
    if not np.isfinite(values).all() or (values < 0).any() or expression.shape[1] < 10:
        raise ValueError("MDIC3表达必须有限、非负且至少10个细胞")
    if metadata.isna().any().any() or metadata.cell.duplicated().any() or metadata.cell_type.str.strip().eq("").any():
        raise ValueError("MDIC3元数据身份重复或缺失")
    if metadata.cell.tolist() != expression.columns.astype(str).tolist():
        raise ValueError("MDIC3表达列与元数据细胞必须同序且完全一致")
    if metadata.cell_type.str.contains(r"\s").any():
        raise ValueError("固定MDIC3入口不支持含空白字符的细胞类型名")
    with grn_path.open() as handle:
        rows = sum(1 for line in handle if line.strip())
    first = np.fromstring(grn_path.open().readline(), sep=" ")
    if rows != expression.shape[0] or len(first) != expression.shape[0]:
        raise ValueError(f"GRN必须是与{expression.shape[0]}个表达基因同序的方阵")
    return expression, metadata


def run_native(script: Path, arguments: list[str], target: Path, log: Path, threads: int) -> None:
    env = dict(os.environ)
    env.update(PYTHONHASHSEED="0", OPENBLAS_NUM_THREADS=str(threads), OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads))
    command = [sys.executable, str(script), *arguments, f"-out={target}"]
    result = subprocess.run(command, cwd=script.parent, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"MDIC3原生入口失败，见 {log.name}")


def parse_lr_resource(path: Path):
    pairs = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 2:
            raise ValueError(f"MDIC3 LR第{line_number}行不是两个空白分隔字段")
        ligand, receptor_text = fields
        receptors = receptor_text[1:-1].split("+") if receptor_text.startswith("(") and receptor_text.endswith(")") else [receptor_text]
        if not ligand or not receptors or any(not item for item in receptors):
            raise ValueError(f"MDIC3 LR第{line_number}行身份无效")
        pairs.append((ligand, receptor_text, receptors))
    if not pairs:
        raise ValueError("MDIC3 LR资源为空")
    return pairs


def source_gene_filter(expression: pd.DataFrame, metadata: pd.DataFrame, genes: set[str]) -> set[str]:
    """Reproduce the fixed source's cumulative detection filter exactly."""
    cell_types = list(dict.fromkeys(metadata.cell_type))
    indices = {name: np.flatnonzero(metadata.cell_type.to_numpy() == name) for name in cell_types}
    retained = set()
    for gene in genes & set(expression.index):
        cumulative = []
        passes = 0
        values = expression.loc[gene].to_numpy()
        for cell_type in cell_types:
            cumulative.extend(values[indices[cell_type]])
            if np.count_nonzero(np.asarray(cumulative) > 0) > len(cumulative) / 2:
                passes += 1
        if passes < len(cell_types) / 2:
            retained.add(gene)
    return retained


def correlation_rows(expression: pd.DataFrame, metadata: pd.DataFrame, pairs, focus_pairs, alpha: float):
    all_genes = {ligand for ligand, _, _ in pairs} | {gene for _, _, receptors in pairs for gene in receptors}
    retained = source_gene_filter(expression, metadata, all_genes)
    rows = []
    native_expected = {}
    for focus in focus_pairs:
        source, target = focus["source"], focus["target"]
        source_cells = metadata.loc[metadata.cell_type == source, "cell"].tolist()
        target_cells = metadata.loc[metadata.cell_type == target, "cell"].tolist()
        if not source_cells or not target_cells:
            raise ValueError(f"MDIC3 LR焦点细胞类型不存在: {source}→{target}")
        candidates = []
        for ligand, receptor_text, receptors in pairs:
            if ligand not in retained or any(gene not in retained for gene in receptors):
                continue
            ligand_values = expression.loc[ligand].to_numpy()
            if len(receptors) == 1:
                native_receptor = corrected_receptor = expression.loc[receptors[0]].to_numpy()
            else:
                # Fixed source concatenates two vectors and later indexes only
                # the first cell-count positions, so it effectively uses R1/2.
                native_receptor = expression.loc[receptors[0]].to_numpy() / 2
                corrected_receptor = expression.loc[receptors].mean(axis=0).to_numpy()
            sender = np.sort(ligand_values[[expression.columns.get_loc(c) for c in source_cells]])[::-1]
            native_receiver = np.sort(native_receptor[[expression.columns.get_loc(c) for c in target_cells]])[::-1]
            corrected_receiver = np.sort(corrected_receptor[[expression.columns.get_loc(c) for c in target_cells]])[::-1]
            if np.count_nonzero(sender == 0) > len(sender) * .7 or np.count_nonzero(native_receiver == 0) > len(native_receiver) * .7:
                continue
            n = min(len(sender), len(native_receiver))
            if np.std(sender[:n]) == 0 or np.std(native_receiver[:n]) == 0:
                continue
            native_r, native_p = pearsonr(sender[:n], native_receiver[:n])
            n2 = min(len(sender), len(corrected_receiver))
            corrected_r, corrected_p = pearsonr(sender[:n2], corrected_receiver[:n2])
            candidates.append(dict(source=source, target=target, ligand=ligand, receptor=receptor_text,
                                   interaction=f"{ligand}→{receptor_text}", native_correlation=float(native_r),
                                   native_p=float(native_p), corrected_complex_correlation=float(corrected_r),
                                   corrected_complex_p=float(corrected_p), complex_receptor=len(receptors) > 1,
                                   compared_order_statistics=n2))
        native_subset = [row for row in candidates if row["native_p"] <= .05]
        for row in candidates:
            row["native_subset_bonferroni_p"] = min(1., row["native_p"] * len(native_subset)) if row["native_p"] <= .05 else None
            row["valid_all_candidate_bonferroni_p"] = min(1., row["corrected_complex_p"] * len(candidates))
            row["native_reported"] = row["native_subset_bonferroni_p"] is not None and row["native_subset_bonferroni_p"] <= .01
            row.update(sample="MDIC3 LR focus", score=row["corrected_complex_correlation"], p_value=row["corrected_complex_p"],
                       q_value=row["valid_all_candidate_bonferroni_p"], tested=True,
                       supported=row["valid_all_candidate_bonferroni_p"] <= alpha)
            rows.append(row)
        native_expected[(source, target)] = {f'{row["ligand"]} - {row["receptor"]}': row["native_subset_bonferroni_p"] for row in candidates if row["native_reported"]}
    return rows, native_expected, sorted(retained)


def run(config_path: str, output_path: str) -> int:
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text())
    base = config_path.parent
    required = ("dataset", "research_question", "expression", "metadata", "grn", "native_root", "input_provenance", "grn_provenance", "expression_scale", "normalization_definition")
    for key in required:
        if cfg.get(key) in (None, "", []):
            raise ValueError("MDIC3配置缺少: " + key)
    paths = {key: resolve(base, cfg[key]) for key in ("expression", "metadata", "grn", "native_root")}
    if any(not path.exists() for path in paths.values()):
        raise ValueError("MDIC3输入或固定源码路径不存在")
    versions = verify_source(paths["native_root"])
    expression, metadata = read_inputs(paths["expression"], paths["metadata"], paths["grn"])
    threads = cfg.get("blas_threads", 1)
    if type(threads) is not int or not 1 <= threads <= 16:
        raise ValueError("blas_threads必须为1–16整数")
    display_top_cells = cfg.get("display_top_cells", 24)
    if type(display_top_cells) is not int or not 10 <= display_top_cells <= 80:
        raise ValueError("display_top_cells必须为10–80整数")
    out = new_output(output_path)
    write_json(out / "run_config.json", cfg)
    native = out / "native_communication"
    run_native(paths["native_root"] / "MDIC3.py",
               [f'-exp={paths["expression"]}', f'-label={paths["metadata"]}', "-grnchoose=other", f'-grn={paths["grn"]}'],
               native, out / "native_communication.log", threads)
    native_cell_path = native / "cellular_communication.txt"
    native_type_path = native / "celltype_communication.txt"
    if not native_cell_path.is_file() or not native_type_path.is_file():
        raise RuntimeError("MDIC3原生入口未生成两张规定矩阵")
    cell = pd.read_csv(native_cell_path, sep="\t", index_col=0)
    types = pd.read_csv(native_type_path, sep="\t", index_col=0)
    cells = metadata.cell.tolist()
    cell_types = list(dict.fromkeys(metadata.cell_type))
    if set(cell.index) != set(cells) or set(cell.columns) != set(cells) or set(types.index) != set(cell_types) or set(types.columns) != set(cell_types):
        raise ValueError("MDIC3原生输出身份与输入不一致")
    cell = cell.loc[cells, cells].astype(float)
    types = types.loc[cell_types, cell_types].astype(float)
    if not np.isfinite(cell.to_numpy()).all() or (cell.to_numpy() < 0).any():
        raise ValueError("MDIC3原生细胞矩阵含负值或非有限值")
    grouped = {}
    raw_type = np.zeros((len(cell_types), len(cell_types)))
    for i, source in enumerate(cell_types):
        source_cells = metadata.loc[metadata.cell_type == source, "cell"]
        for j, target in enumerate(cell_types):
            target_cells = metadata.loc[metadata.cell_type == target, "cell"]
            raw_type[i, j] = cell.loc[source_cells, target_cells].to_numpy().sum()
            grouped[(source, target)] = raw_type[i, j]
    expected_log = np.where(raw_type > 1, np.log10(raw_type), 0)
    aggregation_error = float(np.max(np.abs(expected_log - types.to_numpy())))
    if aggregation_error > 1e-10:
        raise ValueError(f"MDIC3细胞类型矩阵不能从细胞矩阵重建: {aggregation_error}")
    complete_cell = out / "mdic3_complete_cellular_communication.tsv.gz"
    cell.to_csv(complete_cell, sep="\t", compression={"method": "gzip", "mtime": 0})
    complete_type = out / "mdic3_complete_celltype_log10.tsv"
    types.to_csv(complete_type, sep="\t")
    type_rows = [dict(row=source, column=target, value=float(types.loc[source, target])) for source in cell_types for target in cell_types]
    network_rows = [dict(source=source, target=target, value=float(grouped[(source, target)])) for source in cell_types for target in cell_types]
    activity = cell.sum(axis=1) + cell.sum(axis=0)
    selected_set = set(activity.sort_values(ascending=False, kind="stable").head(display_top_cells).index)
    type_lookup = dict(zip(metadata.cell, metadata.cell_type))
    selected = sorted(selected_set, key=lambda item: (cell_types.index(type_lookup[item]), -activity[item], item))
    selected_labels = {cell_id: f"{type_lookup[cell_id]} | #{rank+1}" for rank, cell_id in enumerate(selected)}
    selected_rows = [dict(row=selected_labels[source], column=selected_labels[target], value=float(cell.loc[source, target]), row_cell=source, column_cell=target) for source in selected for target in selected]
    role_rows = []
    for cell_type in cell_types:
        role_rows.extend([
            dict(row=cell_type, column="Outgoing raw sum", value=float(sum(grouped[(cell_type, target)] for target in cell_types))),
            dict(row=cell_type, column="Incoming raw sum", value=float(sum(grouped[(source, cell_type)] for source in cell_types))),
        ])
    diagnostic_rows = [
        dict(row="Native cells", column="Value", value=len(cells)),
        dict(row="Native genes", column="Value", value=expression.shape[0]),
        dict(row="Cell matrix nonzero", column="Value", value=int(np.count_nonzero(cell.to_numpy()))),
        dict(row="Cell matrix zero", column="Value", value=int(np.count_nonzero(cell.to_numpy() == 0))),
        dict(row="Type reconstruction max error", column="Value", value=aggregation_error),
    ]
    bundle = dict(schema_version=2, dataset=cfg["dataset"], method="MDIC3", method_version="fixed source commit 94f1a2a",
                  implementation="native_external_grn_matrix_decomposition",
                  provenance=dict(input_provenance=cfg["input_provenance"], grn_provenance=cfg["grn_provenance"],
                                  expression_scale=cfg["expression_scale"], normalization_definition=cfg["normalization_definition"],
                                  upstream=dict(url="https://github.com/LYxiaotai/MDIC3", commit=COMMIT, license="not declared in fixed repository"),
                                  source_hashes=HASHES, input_hashes={key: digest(path) for key, path in paths.items() if path.is_file()},
                                  versions=versions, parameters=dict(grn_choice="other", python_hash_seed=0, blas_threads=threads),
                                  complete_cell_matrix=dict(path=complete_cell.name, sha256=digest(complete_cell)),
                                  complete_type_matrix=dict(path=complete_type.name, sha256=digest(complete_type)),
                                  native_outputs={"directory": native.name, "cellular_sha256": digest(native_cell_path), "celltype_sha256": digest(native_type_path)},
                                  limitations=[
                                      "MDIC3方向矩阵依赖GRN、SVD和伪逆；分数不是配体结合概率、P值或跨数据集共同效应量。",
                                      "固定源码的细胞类型矩阵对原始群间总和仅在大于1时取log10，其余置0。",
                                      "固定源码没有供体条件模型，单样本不能支持疾病或数据集特异性。",
                                      "固定源码未声明软件许可；Plugin只编排用户提供的外部固定源码。",
                                  ]), tables=[])
    add_table(bundle, out, "mdic3_celltype_log10", "matrix", type_rows,
              "固定MDIC3细胞类型通信矩阵：细胞级非负方向分数按群对求和，大于1时取log10，否则置0；不是显著性。",
              value_kind="native_score", additive=False, figure_role="mdic3_celltype_matrix", row_order=cell_types, column_order=cell_types, axis_label="Native log10 grouped score")
    add_table(bundle, out, "mdic3_celltype_raw_network", "network", network_rows,
              "由固定原生细胞矩阵严格按输入细胞类型求和得到的非负方向网络；用于保留log10前的可加总量。",
              value_kind="nonnegative_strength", additive=True, directed=True, axis_label="Raw grouped MDIC3 sum")
    add_table(bundle, out, "mdic3_celltype_roles", "matrix", role_rows,
              "固定原生细胞矩阵按细胞类型汇总的发送与接收总量；受群大小影响。",
              value_kind="nonnegative_strength", additive=False, figure_role="mdic3_roles", axis_label="Raw grouped MDIC3 sum")
    add_table(bundle, out, "mdic3_top_cell_matrix", "matrix", selected_rows,
              f"按完整发送加接收总量预排序的前{len(selected)}个细胞子矩阵，仅控制展示；完整1394×1394矩阵另存。",
              value_kind="nonnegative_strength", additive=False, figure_role="mdic3_cell_matrix", row_order=[selected_labels[x] for x in selected], column_order=[selected_labels[x] for x in selected], axis_label="Native cellular score")
    add_table(bundle, out, "mdic3_numeric_diagnostics", "matrix", diagnostic_rows,
              "原生矩阵规模、稀疏度和从细胞矩阵重建细胞类型矩阵的导出检查。",
              value_kind="native_score", additive=False, figure_role="mdic3_diagnostics", axis_label="Observed value")

    focus_pairs = cfg.get("focus_pairs", [])
    if focus_pairs:
        if not cfg.get("lr_resource") or not cfg.get("lr_resource_provenance"):
            raise ValueError("运行MDIC3 LR后处理需要lr_resource和lr_resource_provenance")
        lr_path = resolve(base, cfg["lr_resource"])
        if not lr_path.is_file():
            raise ValueError("MDIC3 LR资源不存在")
        pairs = parse_lr_resource(lr_path)
        alpha = float(cfg.get("lr_bonferroni_alpha", .01))
        if not 0 < alpha < 1:
            raise ValueError("lr_bonferroni_alpha必须在0和1之间")
        lr_rows, native_expected, retained = correlation_rows(expression, metadata, pairs, focus_pairs, alpha)
        native_comparisons = []
        for index, focus in enumerate(focus_pairs, 1):
            target = out / f"native_lr_{index:02d}"
            run_native(paths["native_root"] / "MDIC3_LR.py",
                       [f'-exp={paths["expression"]}', f'-label={paths["metadata"]}', f'-lrdb={lr_path}', f'-ltype={focus["source"]}', f'-rtype={focus["target"]}'],
                       target, out / f"native_lr_{index:02d}.log", threads)
            native_file = target / "target_LR.txt"
            expected = native_expected[(focus["source"], focus["target"])]
            if native_file.read_text().strip() == "No key L-R pairs found":
                observed = {}
            else:
                frame = pd.read_csv(native_file, sep="\t")
                observed = dict(zip(frame.L_R_pair, frame.P_value.astype(float)))
            if set(observed) != set(expected) or any(abs(observed[key] - expected[key]) > 1e-12 for key in observed):
                raise ValueError(f"MDIC3_LR原生输出与透明回放不一致: {focus['source']}→{focus['target']}")
            native_comparisons.append(dict(row=f"{focus['source']}→{focus['target']}", column="Native reported", value=len(observed)))
            native_comparisons.append(dict(row=f"{focus['source']}→{focus['target']}", column="Valid all-candidate Bonferroni", value=sum(row["supported"] for row in lr_rows if row["source"] == focus["source"] and row["target"] == focus["target"])))
        bundle["provenance"]["lr_resource_provenance"] = cfg["lr_resource_provenance"]
        bundle["provenance"]["lr_resource_sha256"] = digest(lr_path)
        bundle["provenance"]["lr_diagnostic"] = dict(
            source_behavior="Each cell type's expression is sorted independently, then equal-length order statistics are correlated; these are not paired biological observations.",
            fixed_source_complex_behavior="For a two-subunit receptor, list concatenation followed by cell indexing effectively uses the first subunit divided by two.",
            fixed_source_multiplicity="Bonferroni is applied only after raw P<=0.05 filtering.",
            adapter_display_behavior="Complex subunits are averaged elementwise and Bonferroni is applied across every tested LR for that focus pair; still an algorithmic rank screen, not donor-level inference.",
            retained_genes=len(retained), alpha=alpha)
        add_table(bundle, out, "mdic3_lr_diagnostic", "lr_edges", lr_rows,
                  "MDIC3 LR后处理的透明诊断：按作者独立排序后的细胞表达次序做Pearson；展示分数修正复合受体的逐细胞均值，并在全部实测候选上Bonferroni。大点仅表示算法筛选，不是独立供体显著性。",
                  value_kind="signed_association", additive=False, direction="higher", axis_label="Sorted-expression Pearson correlation",
                  statistical_unit="independently sorted cells within one pooled cell-type pair", test_definition="Pearson P on aligned order statistics; Bonferroni across all tested LR", alpha=alpha,
                  display_top_lr=20, display_top_cell_pairs=len(focus_pairs))
        add_table(bundle, out, "mdic3_lr_correction_counts", "matrix", native_comparisons,
                  "固定源码的原始P预筛后Bonferroni入选数，与复合受体逐细胞均值及全候选Bonferroni诊断入选数。",
                  value_kind="count", additive=False, figure_role="sensitivity")
    bundle["figure_inapplicability"] = {
        "condition_effects": "MDIC3固定算法没有供体条件效应模型。",
        "cellchat_patterns": "MDIC3不是CellChat NMF模式分析。",
        "pathway_sankey": "MDIC3不为通信分数分配通路。",
        "ligand_response": "MDIC3不预测配体响应靶基因。",
        "intracellular": "GRN进入矩阵分解，但固定输出不提供可追踪LR-TF-target路径。",
        "factors": "固定输出不导出可解释分解载荷或秩诊断。",
        "enrichment": "MDIC3没有背景定义的富集检验。",
        "embedding": "MDIC3不输出低维坐标。",
        "spatial_location": "MDIC3不使用空间坐标。",
        "spatial_hotspots": "MDIC3不计算空间热点。",
        "spatial_direction": "MDIC3不计算空间方向向量。",
        "neighborhood_response": "MDIC3不计算空间邻域响应。",
        "relay_dynamic": "MDIC3没有时间或多跳动态。",
        "special_molecules": "当前固定分支只处理基因GRN及可选LR。",
        "functional_clinical": "MDIC3不计算功能、临床或药敏关联。",
    }
    write_json(out / "bundle.json", bundle)
    write_json(out / "run_metadata.json", dict(status="completed_native", source_commit=COMMIT, genes=expression.shape[0], cells=expression.shape[1], cell_types=len(cell_types), focus_pairs=len(focus_pairs), type_reconstruction_max_error=aggregation_error))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.out))
