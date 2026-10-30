#!/usr/bin/env python3
"""流式标准化；不做链协调、坐标转换或统计推断。"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

REQUIRED = ("CHR", "POS", "SNP", "EA", "NEA", "BETA", "SE", "P")

def output_guard(path):
    path = path.resolve()
    if path.exists():
        raise ValueError("输出已存在，拒绝覆盖")
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() or (parent / ".speedskills").exists():
            if path == parent or parent in path.parents:
                raise ValueError("输出不能位于源码仓库")
            break
    return path

def finite(value):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("nonfinite")
    return n

def normalize(row, mapping, cfg):
    d = {k: (row[v] or "").strip() for k, v in mapping.items()}
    if any(not d[k] for k in REQUIRED):
        raise ValueError("missing_required")
    d["CHR"] = d["CHR"].removeprefix("chr").upper()
    if d["CHR"] not in {str(i) for i in range(1,23)} | {"X","Y","MT"}:
        raise ValueError("unsupported_chromosome")
    if not d["POS"].isdigit() or int(d["POS"]) <= 0:
        raise ValueError("invalid_position")
    d["POS"] = str(int(d["POS"]))
    if d["EA"] not in ("A","C","G","T") or d["NEA"] not in ("A","C","G","T") or d["EA"] == d["NEA"]:
        raise ValueError("non_normalized_biallelic_snp")
    for key in ("BETA","SE","P"):
        d[key] = finite(d[key])
    if d["SE"] <= 0 or not 0 < d["P"] <= 1:
        raise ValueError("invalid_se_or_p_underflow")
    if cfg["metadata"]["effect_scale"] == "odds_ratio":
        if d["BETA"] <= 0:
            raise ValueError("nonpositive_or")
        d["BETA"] = math.log(d["BETA"])
    for key in ("EAF","N","INFO"):
        if key in d and d[key]:
            d[key] = finite(d[key])
    if "EAF" in d and d["EAF"] != "" and not 0 < d["EAF"] < 1:
        raise ValueError("invalid_eaf")
    if "N" in d and d["N"] != "" and d["N"] <= 0:
        raise ValueError("invalid_n")
    if "INFO" in d and d["INFO"] != "" and not 0 <= d["INFO"] <= 1:
        raise ValueError("invalid_info")
    if cfg.get("min_info") is not None:
        if d.get("INFO","") == "":
            raise ValueError("missing_info_for_filter")
        if d["INFO"] < cfg["min_info"]:
            raise ValueError("low_info")
    if cfg.get("min_maf") is not None:
        if d.get("EAF","") == "":
            raise ValueError("missing_eaf_for_filter")
        if min(d["EAF"],1-d["EAF"]) < cfg["min_maf"]:
            raise ValueError("low_maf")
    return d

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfgpath = args.config.resolve()
    cfg = json.loads(cfgpath.read_text(encoding="utf-8"))
    for key in ("input","output"):
        if not isinstance(cfg.get(key),str) or not cfg[key].strip():
            raise ValueError("配置缺少路径：" + key)
    meta = cfg.get("metadata",{})
    for key in ("build","ancestry","trait","effect_scale","coverage"):
        if not isinstance(meta.get(key),str) or not meta[key].strip():
            raise ValueError("元数据缺少：" + key)
    if meta["build"] not in ("GRCh37","GRCh38"):
        raise ValueError("本入口需明确GRCh37/GRCh38，不推测build")
    if meta["coverage"] not in ("full","region","significant_only"):
        raise ValueError("coverage不合法")
    if meta["effect_scale"] not in ("beta","log_odds","odds_ratio"):
        raise ValueError("effect_scale不合法")
    if meta["effect_scale"] == "odds_ratio" and meta.get("se_scale") != "log_odds":
        raise ValueError("OR转换需确认SE为log_odds尺度")
    mapping = cfg.get("columns",{})
    if not all(isinstance(mapping.get(k),str) and mapping[k] for k in REQUIRED):
        raise ValueError("必需标准列没有映射")
    if set(mapping) - set(REQUIRED) - {"EAF","N","INFO"}:
        raise ValueError("存在不支持的标准列")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("不同标准字段不能映射到同一原始列")
    for key, hi in (("min_info",1),("min_maf",0.5)):
        if cfg.get(key) is not None and not 0 <= finite(cfg[key]) <= hi:
            raise ValueError(key + "超出范围")
    delim = cfg.get("delimiter","\t")
    if delim not in ("\t",","):
        raise ValueError("只支持明确的TAB/逗号分隔")
    src = (cfgpath.parent / cfg["input"]).resolve()
    if not src.is_file():
        raise ValueError("输入文件不存在")
    out = output_guard(cfgpath.parent / cfg["output"])
    if args.dry_run:
        print(json.dumps({"input":str(src),"output":str(out),"metadata":meta,"executed":False},ensure_ascii=False))
        return
    op = gzip.open if src.suffix == ".gz" else open
    with op(src, "rt", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        fields = reader.fieldnames or []
        if len(set(fields)) != len(fields) or not set(mapping.values()) <= set(fields):
            raise ValueError("输入表头重复或缺少映射列")
        out.mkdir(parents=True, exist_ok=False)
        counts = Counter()
        seen = set()
        metadata = dict(meta)
        if metadata["effect_scale"] == "odds_ratio":
            metadata["effect_scale"] = "log_odds"
        try:
            with gzip.open(out/"sumstats.tsv.gz","wt",encoding="utf-8",newline="") as good, (out/"excluded.tsv").open("w",encoding="utf-8",newline="") as bad:
                gw = csv.DictWriter(good,fieldnames=list(mapping),delimiter="\t"); gw.writeheader()
                bw = csv.writer(bad,delimiter="\t"); bw.writerow(["line","SNP","reason"])
                for line, row in enumerate(reader,2):
                    counts["input"] += 1
                    if None in row or any(v is None for v in row.values()):
                        raise ValueError("列数不一致，第" + str(line) + "行")
                    snp = row[mapping["SNP"]].strip()
                    if snp and snp in seen:
                        raise ValueError("重复SNP，需明确去重/多等位策略：" + snp)
                    if snp:
                        seen.add(snp)
                    try:
                        d = normalize(row,mapping,cfg)
                    except (ValueError,TypeError,KeyError,OverflowError) as err:
                        reason = str(err)
                        if reason in {"non_normalized_biallelic_snp", "invalid_se_or_p_underflow", "unsupported_chromosome"}:
                            raise ValueError("表示/尺度不受支持，停止而非丢弃后继续：" + reason + "；先按指南适配，已产生文件为未完成产物") from err
                        counts["excluded:"+reason] += 1
                        bw.writerow([line,snp,reason])
                        continue
                    gw.writerow(d); counts["retained"] += 1
            if not counts["retained"]:
                raise ValueError("没有保留变异")
            with src.open("rb") as handle:
                metadata["input_sha256"] = hashlib.file_digest(handle,"sha256").hexdigest()
            metadata.update({"input":str(src),"config":cfg,"status":"completed_formatting_only",
                             "warning":"未做liftover、链协调、LD或科学有效性验证"})
            (out/"metadata.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            (out/"qc.json").write_text(json.dumps(counts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        except Exception as err:
            (out/"FAILED.json").write_text(json.dumps({"error":str(err),"partial_outputs":True},ensure_ascii=False),encoding="utf-8")
            raise
    print("完成格式化；请检查排除记录和适用范围")

if __name__ == "__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("错误：" + str(exc),file=sys.stderr); sys.exit(2)
