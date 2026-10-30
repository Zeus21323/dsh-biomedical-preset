#!/usr/bin/env python3
"""校验并调用固定版本peakScout；默认只出执行计划。"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

COMMIT = "20f4aafbc1599c3790dc0ae271c6a72f35a5b2f7"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def run(config, out, execute=False):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    require(not out.exists() and not out.is_symlink(), "输出目录已存在")
    for key in ("repo", "peaks", "gtf", "assembly", "annotation_assembly", "question", "mode"):
        require(isinstance(cfg.get(key), str) and cfg[key].strip(), f"缺少配置：{key}")
    require(cfg["assembly"] == cfg["annotation_assembly"], "peaks与注释参考版本不一致")
    require(cfg["mode"] in {"peak2gene", "gene2peak"}, "无效映射方向")
    # 首版只适配明确BED6，不推测MACS2/SEACR不同列布局。
    require(cfg.get("peak_type", "BED6") == "BED6", "本包装器要求规范BED6；其他格式按原生契约显式转换")
    k = cfg.get("k", 3)
    require(type(k) is int and 1 <= k <= 20, "k需为1–20整数，更多候选先评估版式与任务")
    paths = {key: (config.parent / cfg[key]).resolve() for key in ("repo", "peaks", "gtf")}
    head = subprocess.check_output(["git", "-C", str(paths["repo"]), "rev-parse", "HEAD"], text=True).strip()
    require(head == COMMIT, "上游版本不匹配")
    dirty = subprocess.check_output(["git", "-C", str(paths["repo"]), "status", "--porcelain", "--untracked-files=no"], text=True)
    require(not dirty.strip(), "上游已跟踪文件被修改")
    chroms, ids, n = set(), set(), 0
    with paths["peaks"].open(encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            require(len(fields) == 6, "peaks必须为BED6")
            chrom, start, end, name, score, strand = fields
            require(int(start) >= 0 and int(end) > int(start), "BED坐标必须为0-based半开且非空")
            require(name and name not in ids, "peak名称空或重复")
            require(strand in {"+", "-", "."}, "BED链字段无效")
            require(chrom and math.isfinite(float(score)), "染色体为空或分数非有限")
            ids.add(name)
            chroms.add(chrom)
            n += 1
    require(n > 0, "peaks为空")
    annotations = set()
    with paths["gtf"].open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            require(len(fields) == 9, "GTF必须有9列")
            require(int(fields[3]) >= 1 and int(fields[4]) >= int(fields[3]), "GTF坐标无效")
            annotations.add(fields[0])
    require(chroms <= annotations, "部分peak染色体不在GTF中；不得自动改名或丢弃")
    if cfg["mode"] == "gene2peak":
        require(bool(cfg.get("genes")), "gene2peak需要基因名单")
        paths["genes"] = (config.parent / cfg["genes"]).resolve()
        genes = paths["genes"].read_text(encoding="utf-8").splitlines()
        require(genes and len(genes) == len(set(genes)) and all(g.strip() == g and g and "\t" not in g and "," not in g for g in genes), "基因文件需为无表头单列唯一标识")
    if cfg.get("cre"):
        require(cfg.get("cre_assembly") == cfg["assembly"], "cCRE参考版本必须显式匹配")
        paths["cre"] = (config.parent / cfg["cre"]).resolve()
        with paths["cre"].open(encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                fields = line.rstrip("\n").split("\t")
                require(len(fields) >= 3 and fields[0] in annotations and int(fields[1]) >= 0 and int(fields[2]) > int(fields[1]), "cCRE BED坐标或染色体无效")
    out = out.resolve()
    ref = out / "reference"
    result = out / "results"
    cli = [sys.executable, "-B", str(paths["repo"] / "src/peakScout")]
    # 固定上游skip_rows=5；副本统一成五行注释，避免无表头GTF丢失真实记录。
    staged_gtf = out / "input.gtf"
    decompose = cli + ["decompose", "--ref_dir", str(ref), "--gtf_ref", str(staged_gtf)]
    command = cli + [cfg["mode"], "--peak_file", str(paths["peaks"]), "--peak_type", "BED6",
                     "--ref_dir", str(ref), "--species_genome", cfg["assembly"], "--k", str(k),
                     "--output_name", "mapping", "--o", str(result), "--output_type", "csv"]
    if "genes" in paths:
        command += ["--gene_file", str(paths["genes"])]
    if "cre" in paths:
        command += ["--cre_file", str(paths["cre"])]
    for key in ("up_bound", "down_bound"):
        if key in cfg:
            require(type(cfg[key]) is int and cfg[key] >= 0, f"{key}需为非负整数距离")
            command += ["--" + key, str(cfg[key])]
    manifest = {"status": "planned", "method": "peakScout", "commit": head, "config": cfg,
                "input_sha256": {k: sha(v) for k, v in paths.items() if k != "repo"}, "n_peaks": n,
                "commands": [decompose, command], "evidence": "positional_association_only"}
    out.mkdir(parents=True)
    with staged_gtf.open("w", encoding="utf-8") as dst, paths["gtf"].open(encoding="utf-8") as src:
        dst.write("# peakScout adapter: normalized comment header\n" * 5)
        for line in src:
            if line.strip() and not line.startswith("#"):
                dst.write(line.rstrip("\n") + "\n")
    manifest["staged_gtf_sha256"] = sha(staged_gtf)
    manifest["gtf_transform"] = "保留全部非注释记录及原生坐标，副本统一五行注释以适配上游skip_rows=5"
    def save():
        (out / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save()
    if execute:
        manifest["status"] = "running"
        save()
        try:
            with (out / "run.log").open("w", encoding="utf-8") as log:
                for cmd in (decompose, command):
                    subprocess.run(cmd, cwd=paths["repo"], check=True, stdout=log, stderr=subprocess.STDOUT)
            files = list(result.glob("*.csv"))
            require(files, "上游未产出CSV，不得报告映射完成")
            for file in files:
                with file.open(encoding="utf-8-sig", newline="") as f:
                    require(len(list(csv.reader(f))) > 1, "映射结果为空，需要核对基因标识与距离范围")
            manifest["status"] = "completed_output_review_required"
            manifest["output_sha256"] = {str(f.relative_to(out)): sha(f) for f in files}
        except Exception:
            manifest["status"] = "failed"
            raise
        finally:
            save()
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--execute", action="store_true")
    a = p.parse_args(argv)
    try:
        print(run(a.config, a.out_dir, a.execute)["status"])
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as e:
        print(f"peakScout失败：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
