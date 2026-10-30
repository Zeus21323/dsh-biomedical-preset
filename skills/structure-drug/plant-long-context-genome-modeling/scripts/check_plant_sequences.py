#!/usr/bin/env python3
"""检查植物FASTA和资源清单，不执行BOTANIC预测。"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(path, max_bases=None):
    sequences, current, chunks = {}, None, []
    def finish():
        if current is not None:
            sequence = "".join(chunks).upper()
            require(sequence and set(sequence) <= set("ACGTN"), "FASTA含空序列或非ACGTN字符；不得自动替换")
            require(current not in sequences, "FASTA标识重复")
            sequences[current] = sequence
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        if line.startswith(">"):
            finish()
            require(bool(line[1:].strip()), "FASTA标题为空")
            current, chunks = line[1:].split()[0], []
        else:
            require(current is not None and not any(c.isspace() for c in line), "FASTA序列出现在标题前或含内部空白")
            chunks.append(line)
    finish()
    require(sequences, "FASTA为空")
    require(max_bases is None or max_bases > 0, "max-bases必须为正数并来自核实的模型契约")
    return [{"sequence_id": key, "length": len(seq), "n_fraction": seq.count("N") / len(seq),
             "over_limit": max_bases is not None and len(seq) > max_bases,
             "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest()} for key, seq in sequences.items()]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fasta", required=True, type=Path)
    p.add_argument("--species", required=True)
    p.add_argument("--assembly", required=True)
    p.add_argument("--max-bases", type=int)
    p.add_argument("--model-dir", type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        require(not a.out_dir.exists() and not a.out_dir.is_symlink(), "输出已存在")
        require(a.species.strip() and a.assembly.strip(), "物种与参考不能为空")
        rows = check(a.fasta, a.max_bases)
        resource = {}
        if a.model_dir:
            require(a.model_dir.is_dir(), "模型目录不存在")
            resource = {name: (a.model_dir / name).is_file() for name in ("config.json", "tokenizer_config.json")}
        with a.fasta.open("rb") as f:
            fingerprint = hashlib.file_digest(f, "sha256").hexdigest()
        a.out_dir.mkdir(parents=True)
        with (a.out_dir / "sequence_qc.tsv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
        report = {"status": "sequence_checked_model_interface_unverified", "species": a.species, "assembly": a.assembly,
                  "input_sha256": fingerprint, "resource_files_present": resource, "max_bases": a.max_bases,
                  "n_over_limit": sum(r["over_limit"] for r in rows), "prediction_executed": False,
                  "missing_requirements": ["verified_checkpoint_tokenizer_and_inference_contract", "license_and_compute_review"]}
        (a.out_dir / "readiness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("FASTA检查完成；模型接口未验证，未进行预测")
        return 0
    except (OSError, ValueError, TypeError) as e:
        print(f"序列检查失败：{e}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
