#!/usr/bin/env python3
"""验证ProRB配对序列与已有评分身份；不加载或运行模型。"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_table(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        require(r.fieldnames and len(r.fieldnames) == len(set(r.fieldnames)), "CSV缺表头或重复列")
        rows = list(r)
    require(rows and all(None not in x and all(v is not None for v in x.values()) for x in rows), "CSV为空或列数错误")
    return rows


def check(pairs, scores=None):
    rows = read_table(pairs)
    ids, sequences, output = set(), set(), []
    for r in rows:
        require(all(r.get(k) for k in ("pair_id", "prot_seq", "rna_seq")), "需要pair_id/prot_seq/rna_seq")
        require(r["pair_id"].strip() == r["pair_id"] and r["pair_id"].strip() and r["pair_id"] not in ids, "pair_id空、首尾有空白或重复")
        prot, rna = r["prot_seq"], r["rna_seq"]
        require(set(prot) <= set("ACDEFGHIKLMNPQRSTVWY"), "蛋白含非标准/小写字符；需明确转换，不静默处理")
        require(set(rna) <= set("ACGU"), "RNA必须为ACGU；不自动将T替换U或移除修饰")
        key = prot, rna
        output.append({"pair_id": r["pair_id"], "protein_length": len(prot), "rna_length": len(rna),
                       "duplicate_sequence_pair": key in sequences,
                       "protein_sha256": hashlib.sha256(prot.encode()).hexdigest(),
                       "rna_sha256": hashlib.sha256(rna.encode()).hexdigest()})
        ids.add(r["pair_id"]); sequences.add(key)
    if scores:
        existing = read_table(scores)
        require(all("pair_id" in r and "score" in r for r in existing), "已有评分需要pair_id/score")
        require(len(existing) == len(ids) and len({r["pair_id"] for r in existing}) == len(ids) and {r["pair_id"] for r in existing} == ids,
                "评分ID缺失、重复或与序列不匹配")
        mapping = {r["pair_id"]: float(r["score"]) for r in existing}
        require(all(math.isfinite(v) for v in mapping.values()), "评分含非有限值")
        for row in output:
            row["provided_score"] = mapping[row["pair_id"]]
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs", required=True, type=Path)
    p.add_argument("--scores", type=Path)
    p.add_argument("--score-source", help="已有评分的模型/版本/单位与运行记录")
    p.add_argument("--out-dir", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        require(not a.out_dir.exists() and not a.out_dir.is_symlink(), "输出目录已存在")
        require(not a.scores or (a.score_source and a.score_source.strip()), "导入已有评分必须说明来源与单位")
        rows = check(a.pairs, a.scores)
        hashes = {}
        for key, path in (("pairs", a.pairs), ("scores", a.scores)):
            if path:
                with path.open("rb") as f:
                    hashes[key] = hashlib.file_digest(f, "sha256").hexdigest()
        a.out_dir.mkdir(parents=True)
        with (a.out_dir / "pair_qc.tsv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t"); w.writeheader(); w.writerows(rows)
        record = {"status": "existing_scores_linked" if a.scores else "inputs_checked", "input_sha256": hashes,
                  "score_source": a.score_source, "prediction_executed": False,
                  "upstream_status": "v2.2_requires_verified_adapter_and_weights", "pair_count": len(rows)}
        (a.out_dir / "readiness.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("配对身份检查完成，未执行ProRB推理")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"配对检查失败：{e}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
