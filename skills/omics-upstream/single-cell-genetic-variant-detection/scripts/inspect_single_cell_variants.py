#!/usr/bin/env python3
"""检查带细胞标签BAM或汇总已有VCF；不进行新的Indel检出。"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def vcf_summary(path):
    opener = gzip.open if path.suffix == ".gz" else open
    rows, samples, seen, header = [], [], set(), False
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM\t"):
                require(not header, "VCF表头重复")
                fields = line.rstrip("\n\r").split("\t")
                require(fields[:8] == ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"], "VCF固定表头不正确")
                require(len(fields) == 8 or (len(fields) >= 10 and fields[8] == "FORMAT"), "VCF样本表头不完整")
                samples = fields[9:]; header = True
                require(len(samples) == len(set(samples)) and all(s.strip() == s and s for s in samples), "VCF样本名空、重复或含首尾空白")
                continue
            if not line.strip():
                continue
            require(header, "VCF缺少#CHROM表头")
            fields = line.rstrip("\n").split("\t")
            require(len(fields) >= 8 and len(fields) == (9 + len(samples) if samples else 8), "VCF记录列数错误")
            chrom, pos, _, ref, alts, qual, filt = fields[:7]
            require(int(pos) > 0 and ref and set(ref.upper()) <= set("ACGTN"), "VCF位置或REF无效")
            alt_list = alts.split(",")
            for index, alt in enumerate(alt_list, 1):
                if not alt or alt == "*" or set(alt.upper()) - set("ACGTN") or len(ref) == len(alt):
                    continue
                key = chrom, pos, ref, alt
                require(key not in seen, "VCF含重复等位记录")
                seen.add(key)
                called, missing, carriers = 0, 0, 0
                fmt = fields[8].split(":") if samples else []
                for sample in fields[9:]:
                    parts = sample.split(":")
                    gt = parts[fmt.index("GT")] if "GT" in fmt and fmt.index("GT") < len(parts) else "."
                    alleles = gt.replace("|", "/").split("/")
                    require(all(a == "." or (a.isdigit() and int(a) <= len(alt_list)) for a in alleles), "GT等位索引无效")
                    if "." in alleles:
                        missing += 1
                        continue
                    called += 1; carriers += str(index) in alleles
                rows.append({"chrom": chrom, "pos_1based": int(pos), "ref": ref, "alt": alt,
                             "length_change": len(alt) - len(ref), "filter": filt, "qual": qual,
                             "called_samples": called, "missing_samples": missing, "carrier_samples": carriers})
    require(header, "VCF为空或没有表头")
    return rows, samples


def bam_check(path, cell_tag="CB"):
    require(path.suffix == ".bam", "首版bam-check仅接受BAM；CRAM需另核对参考资源")
    require(len(cell_tag) == 2 and cell_tag.isalnum(), "细胞标签必须为两个字母数字字符")
    indexes = [Path(str(path) + ".bai"), path.with_suffix(".bai"), Path(str(path) + ".csi")]
    require(any(p.is_file() for p in indexes), "缺少BAM索引")
    subprocess.run(["samtools", "quickcheck", "-v", str(path)], check=True, capture_output=True, text=True)
    header = subprocess.check_output(["samtools", "view", "-H", str(path)], text=True)
    require("@SQ\t" in header, "BAM缺少参考序列字典")
    # 仅读前1000条做标签检查，不将抽样结论写成全文件保证。
    process = subprocess.Popen(["samtools", "view", str(path)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    total, tagged = 0, 0
    try:
        for line in process.stdout:
            total += 1
            tagged += any(x.startswith(cell_tag + ":") for x in line.rstrip().split("\t")[11:])
            if total >= 1000:
                break
    finally:
        process.stdout.close()
        process.terminate()
        process.wait()
    require(total > 0 and tagged > 0, "抽样没有读段或指定细胞标签，不能判为细胞级数据就绪")
    return {"sampled_reads": total, "tagged_reads": tagged, "cell_tag": cell_tag, "header": header,
            "limitation": "仅检查完整性/索引存在与标签抽样，未验证索引新鲜度、参考一致、覆盖或模型资源"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True, choices=["bam-check", "vcf-summary"])
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--cell-tag", default="CB")
    p.add_argument("--out-dir", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        require(not a.out_dir.exists() and not a.out_dir.is_symlink(), "输出目录已存在")
        rows = None
        if a.mode == "vcf-summary":
            rows, samples = vcf_summary(a.input)
            data = {"n_indel_alleles": len(rows), "samples": samples,
                    "limitations": ["不判断生殖系/体细胞", "不重建谱系", "不含等长替换或符号结构变异", "VCF样本不默认等于细胞"]}
        else:
            data = bam_check(a.input, a.cell_tag)
        with a.input.open("rb") as f:
            data["input_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
        data.update(status="input_evidence_checked", new_variant_calling=False, mode=a.mode)
        a.out_dir.mkdir(parents=True)
        (a.out_dir / "inspection.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if rows is not None:
            fields = ["chrom", "pos_1based", "ref", "alt", "length_change", "filter", "qual", "called_samples", "missing_samples", "carrier_samples"]
            with (a.out_dir / "indels.tsv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, delimiter="\t"); w.writeheader(); w.writerows(rows)
        print("检查/汇总完成；未进行新变异检出")
        return 0
    except (OSError, ValueError, TypeError, IndexError, subprocess.SubprocessError) as e:
        print(f"变异检查失败：{e}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
