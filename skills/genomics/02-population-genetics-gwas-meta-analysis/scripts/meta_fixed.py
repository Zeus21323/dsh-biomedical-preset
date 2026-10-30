#!/usr/bin/env python3
"""已协调独立研究的固定效应逆方差meta；小规模内存型入口。"""
import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import sys

def combine(rows):
    if len(rows)<2: return None
    w=[1/r[1]**2 for r in rows]
    sw=math.fsum(w); beta=math.fsum(a*r[0] for a,r in zip(w,rows))/sw
    se=math.sqrt(1/sw)
    q=math.fsum(a*(r[0]-beta)**2 for a,r in zip(w,rows))
    df=len(rows)-1
    return [beta,se,beta-1.96*se,beta+1.96*se,math.erfc(abs(beta/se)/math.sqrt(2)),q,df,max(0,(q-df)/q)*100 if q else 0]

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--input",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    a.add_argument("--independent-reviewed",action="store_true")
    a.add_argument("--scale",choices=["beta","log_odds"],required=True)
    x=a.parse_args()
    if not x.independent_reviewed: raise ValueError("先审查研究独立性")
    groups=defaultdict(list);alleles={};seen=set()
    with x.input.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t")
        req={"study","SNP","EA","NEA","beta","se"}
        if not req<=set(r.fieldnames or []): raise ValueError("缺少必需列")
        if len(r.fieldnames)!=len(set(r.fieldnames)): raise ValueError("表头重复")
        for row in r:
            if None in row or any(v is None for v in row.values()): raise ValueError("列数不一致")
            if any(not (row.get(k) or "").strip() for k in req): raise ValueError("必需值缺失")
            key=(row["study"],row["SNP"])
            if key in seen: raise ValueError("重复study/SNP")
            seen.add(key); snp=row["SNP"]; pair=(row["EA"],row["NEA"])
            if pair[0]==pair[1]: raise ValueError("相同等位基因")
            if snp in alleles and alleles[snp]!=pair: raise ValueError("等位基因未协调")
            alleles[snp]=pair
            b,s=float(row["beta"]),float(row["se"])
            if not all(math.isfinite(v) for v in (b,s)) or s<=0: raise ValueError("beta/se非法")
            groups[snp].append((b,s))
    if not groups: raise ValueError("输入为空")
    out=x.out.resolve()
    if out.exists(): raise ValueError("输出已存在")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("结果不能写入仓库")
            break
    out.mkdir(parents=True,exist_ok=False)
    with (out/"meta.tsv").open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f,delimiter="\t")
        w.writerow(["SNP","EA","NEA","studies","status","beta","se","ci_low","ci_high","p_normal","Q","Q_df","I2_percent"])
        for snp,rows in groups.items():
            v=combine(rows)
            w.writerow([snp,*alleles[snp],len(rows),"completed" if v else "not_meta",*(v if v else ["NA"]*8)])
    (out/"methods.json").write_text(json.dumps({"model":"fixed_inverse_variance","scale":x.scale,
      "ci":"95_percent_normal","Q_p":"not_computed","overlap_correction":False,
      "warning":"independent-reviewed仅记录操作者确认，不自动验证独立性"},ensure_ascii=False,indent=2),encoding="utf-8")
    print("完成固定效应合并，异质性与独立性仍需解释")

if __name__=="__main__":
    try: main()
    except (OSError,ValueError,KeyError,OverflowError) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)
