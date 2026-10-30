#!/usr/bin/env python3
"""验证已计算带符号LD矩阵及SNP顺序；不修复或推断等位基因方向。"""
import argparse
import csv
import json
from pathlib import Path
import sys

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--matrix",type=Path,required=True);a.add_argument("--stats",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    x=a.parse_args()
    import numpy as np
    with x.matrix.open(encoding="utf-8-sig",newline="") as f:
        reader=csv.reader(f,delimiter="\t");header=next(reader);rows=list(reader)
    ids=header[1:]
    if not ids or len(ids)!=len(set(ids)) or any(not i for i in ids): raise ValueError("矩阵ID为空/重复")
    if any(len(r)!=len(header) for r in rows): raise ValueError("矩阵列数错误")
    if [r[0] for r in rows]!=ids: raise ValueError("矩阵行列ID/顺序不一致")
    m=np.array([[float(v) for v in r[1:]] for r in rows])
    with x.stats.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t")
        if "SNP" not in (r.fieldnames or []): raise ValueError("stats缺少SNP")
        si=[row["SNP"] for row in r]
    if si!=ids: raise ValueError("统计与LD的SNP/顺序不一致")
    if not np.isfinite(m).all() or np.max(np.abs(m))>1+1e-8: raise ValueError("LD非有限或超范围")
    if not np.allclose(m,m.T,rtol=0,atol=1e-8) or not np.allclose(m.diagonal(),1,rtol=0,atol=1e-8): raise ValueError("LD不对称或对角非1")
    eig=np.linalg.eigvalsh(m)
    if eig[0]<-1e-6: raise ValueError("LD非半正定；禁止静默修复")
    out=x.out.resolve()
    if out.exists(): raise ValueError("输出已存在")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("输出不能位于仓库")
            break
    out.mkdir(parents=True,exist_ok=False)
    (out/"ld_diagnostics.json").write_text(json.dumps({"n_snps":len(ids),"min_eigenvalue":float(eig[0]),"singular":bool(eig[0]<=1e-8),"allele_orientation_verified":False,"warning":"结构检查不证明祖源/样本/等位基因适配"},ensure_ascii=False,indent=2),encoding="utf-8")
    print("结构检查完成；仍需参考和等位基因审计")

if __name__=="__main__":
    try: main()
    except (OSError,ValueError,KeyError,ImportError,StopIteration) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)
