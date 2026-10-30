#!/usr/bin/env python3
"""仅审查标准FID/IID样本表与表型/协变量，不计算基因型QC。"""
import argparse
import csv
import json
import math
from pathlib import Path
import sys

def load(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t")
        fields=r.fieldnames or []
        if not {"FID","IID"} <= set(fields) or len(fields)!=len(set(fields)):
            raise ValueError("需唯一FID IID表头：" + str(path))
        result={}
        for row in r:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("列数不一致")
            key=(row["FID"].strip(),row["IID"].strip())
            if not all(key) or key in result:
                raise ValueError("ID空白或重复：" + str(path))
            result[key]=row
        if not result:
            raise ValueError("样本表为空")
    return result,fields

def main():
    a=argparse.ArgumentParser(description=__doc__)
    for k in ("samples","phenotypes","covariates","out"):
        a.add_argument("--"+k,type=Path,required=True)
    a.add_argument("--trait",required=True)
    a.add_argument("--trait-type",choices=["binary","quantitative"],required=True)
    x=a.parse_args()
    samples,_=load(x.samples); pheno,pfields=load(x.phenotypes); cov,cfields=load(x.covariates)
    if x.trait not in pfields:
        raise ValueError("表型列不存在")
    for row in pheno.values():
        v=row[x.trait].strip()
        if v in ("","NA"): continue
        n=float(v)
        if not math.isfinite(n) or (x.trait_type=="binary" and n not in (0,1)):
            raise ValueError("表型编码非法")
    out=x.out.resolve()
    if out.exists(): raise ValueError("输出已存在")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("输出不能写入仓库")
            break
    rows=[]
    for key in sorted(set(samples)|set(pheno)|set(cov)):
        reasons=[]
        for name,data in (("genotype",samples),("phenotype",pheno),("covariate",cov)):
            if key not in data: reasons.append("missing_"+name)
        if key in pheno and pheno[key][x.trait].strip() in ("","NA"): reasons.append("missing_trait_value")
        if key in cov and any(cov[key][k].strip() in ("","NA") for k in cfields if k not in ("FID","IID")):
            reasons.append("missing_covariate_value")
        rows.append([*key,";".join(reasons) or "matched_requires_scientific_qc"])
    out.mkdir(parents=True,exist_ok=False)
    with (out/"sample_review.tsv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,delimiter="\t");w.writerow(["FID","IID","status"]);w.writerows(rows)
    summary={"genotype_rows":len(samples),"phenotype_rows":len(pheno),"covariate_rows":len(cov),
             "matched_complete":sum(r[2]=="matched_requires_scientific_qc" for r in rows),
             "genotype_qc":"not_performed","automatic_exclusion":False}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("元数据审查完成；不是基因型QC通过")

if __name__=="__main__":
    try: main()
    except (OSError,ValueError,KeyError) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)
