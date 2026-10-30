#!/usr/bin/env python3
"""约束的PLINK2/REGENIE常染色体调用；不执行前置QC或隐式下载。"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

def digest(p):
    with p.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def read_table(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t"); fields=r.fieldnames or []
        if not {"FID","IID"}<=set(fields) or len(fields)!=len(set(fields)): raise ValueError("需要唯一FID IID表头")
        rows={}
        for row in r:
            if None in row or any(v is None for v in row.values()): raise ValueError("表格列数不一致")
            k=(row["FID"],row["IID"])
            if not all(k) or k in rows: raise ValueError("样本ID空/重复")
            rows[k]=row
    if not rows: raise ValueError("表格为空")
    return rows,fields

def prepare(cfg,base,step):
    def txt(k):
        v=cfg.get(k)
        if not isinstance(v,str) or not v.strip(): raise ValueError("配置缺少："+k)
        return v
    def path(k):
        v=(base/txt(k)).resolve()
        if not v.is_file(): raise ValueError("文件不存在："+str(v))
        return v
    engine=txt("engine")
    if engine not in ("plink2","regenie"): raise ValueError("仅封装PLINK2和REGENIE；其他后端按指南")
    if (engine=="plink2" and step!="association") or (engine=="regenie" and step not in ("step1","step2")):
        raise ValueError("后端与step不匹配")
    if cfg.get("qc_reviewed") is not True: raise ValueError("先审查样本/变异QC")
    for k in ("model_rationale","build","ancestry"): txt(k)
    trait=txt("trait")
    tt=txt("trait_type")
    if tt not in ("binary","quantitative"): raise ValueError("只支持binary/quantitative")
    covars=cfg.get("covariate_names")
    if not isinstance(covars,list) or not covars or any(not isinstance(v,str) or not v or "," in v for v in covars) or len(set(covars))!=len(covars):
        raise ValueError("covariate_names需唯一非空列表；分类变量先明确数值编码")
    threads=cfg.get("threads");bsize=cfg.get("bsize")
    if type(threads)!=int or threads<1 or type(bsize)!=int or bsize<1: raise ValueError("threads/bsize须正整数")
    mac=cfg.get("min_mac")
    if isinstance(mac,bool) or not isinstance(mac,(int,float)) or not math.isfinite(mac) or mac<=0: raise ValueError("min_mac須正有限数")
    geno_key="step1_pgen" if step=="step1" else "pgen"
    prefix=(base/txt(geno_key)).resolve()
    gfiles=[Path(str(prefix)+ext) for ext in (".pgen",".pvar",".psam")]
    if any(not f.is_file() for f in gfiles): raise ValueError("需要完整pgen/pvar/psam；压缩pvar请先明确转换")
    ph=path("phenotypes");cv=path("covariates")
    phrows,fields=read_table(ph);cvrows,cfields=read_table(cv)
    if trait not in fields or not set(covars)<=set(cfields): raise ValueError("表型/协变量列缺失")
    with gfiles[2].open(encoding="utf-8-sig") as f:
        header=f.readline().strip().lstrip("#").split()
        if "IID" not in header: raise ValueError("psam需要IID表头")
        gi=header.index("IID");gf=header.index("FID") if "FID" in header else None
        ids=[]
        for line in f:
            if not line.strip(): continue
            parts=line.split()
            if len(parts)!=len(header): raise ValueError("psam列数错误")
            ids.append((parts[gf] if gf is not None else "0",parts[gi]))
    if not ids or len(ids)!=len(set(ids)): raise ValueError("psam为空/重复")
    # Strict prepared-input contract: no silent exclusions across datasets.
    if set(ids)!=set(phrows) or set(ids)!=set(cvrows): raise ValueError("样本集合不同；先审查并显式生成匹配输入")
    vals=[]
    for k in ids:
        try: v=float(phrows[k][trait])
        except ValueError: raise ValueError("本入口要求已明确处理缺失表型")
        if not math.isfinite(v) or (tt=="binary" and v not in (0,1)): raise ValueError("表型编码非法")
        vals.append(v)
        for col in covars:
            try: z=float(cvrows[k][col])
            except ValueError: raise ValueError("协变量需完整数值编码")
            if not math.isfinite(z): raise ValueError("协变量有非有限值")
    if len(set(vals))<2: raise ValueError("表型无变化")
    if engine=="plink2" and tt=="quantitative" and set(vals)<={0,1,2}:
        raise ValueError("PLINK2可能将此连续编码识别为二分类；使用经核验的原生编码分支或REGENIE")
    out=(base/txt("output")).resolve()
    if out.exists(): raise ValueError("输出目录已存在；不覆盖或猜测缓存")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("运行产物不能写入仓库")
            break
    executable=txt("executable")
    if "/" in executable or "\\" in executable:
        executable=str((base/executable).resolve())
    cmd=[executable]
    inputs=gfiles+[ph,cv]
    design={"phenotypes_sha256":digest(ph),"covariates_sha256":digest(cv),"trait":trait,"trait_type":tt,
            "covariate_names":covars,"build":cfg["build"],"ancestry":cfg["ancestry"]}
    if engine=="plink2":
        cmd+=["--pfile",str(prefix),"--autosome","--pheno",str(ph),"--pheno-name",trait,
              "--covar",str(cv),"--covar-name",",".join(covars),"--threads",str(threads),
              "--mac",str(mac),"--glm","hide-covar"]
        if tt=="binary": cmd+=["firth-fallback","--1"]
    else:
        cmd+=["--step","1" if step=="step1" else "2","--pgen",str(prefix),"--phenoFile",str(ph),
              "--phenoCol",trait,"--covarFile",str(cv),"--covarColList",",".join(covars),
              "--bsize",str(bsize),"--threads",str(threads),"--strict"]
        if tt=="binary": cmd+=["--bt"]
        if step=="step1":
            extract=path("step1_extract"); inputs.append(extract)
            # Step1 chromosome restriction must be embodied in the audited variant list.
            with extract.open() as f: selected={line.split()[0] for line in f if line.strip()}
            if not selected: raise ValueError("step1位点清单为空")
            found=set()
            ci=vi=None
            with gfiles[1].open() as f:
                for line in f:
                    if not line.strip(): continue
                    if line.startswith("##"): continue
                    if line.startswith("#"):
                        h=line.lstrip("#").split()
                        if not {"CHROM","ID"}<=set(h): raise ValueError("pvar缺列")
                        ci,vi=h.index("CHROM"),h.index("ID")
                        continue
                    cells=line.split()
                    if ci is None or vi is None or max(ci,vi)>=len(cells): raise ValueError("pvar缺表头或列数错误")
                    if cells[vi] in selected:
                        if cells[ci] not in {str(i) for i in range(1,23)}: raise ValueError("step1清单包含非常染色体")
                        found.add(cells[vi])
            if found!=selected: raise ValueError("step1清单有不在pvar中的位点")
            cmd+=["--extract",str(extract),"--lowmem","--lowmem-prefix",str(out/"ridge_tmp")]
        else:
            pred=path("predictions"); prior=path("step1_run_record")
            previous=json.loads(prior.read_text(encoding="utf-8"))
            if previous.get("status")!="completed" or previous.get("step")!="step1" or previous.get("design")!=design:
                raise ValueError("step1运行记录/研究设计与当前不一致")
            expected=previous.get("outputs",{}).get(str(pred))
            if expected is None or expected!=digest(pred): raise ValueError("预测清单不属于核验的step1产物")
            with pred.open() as f:
                prediction_rows=[line.split() for line in f if line.strip()]
            if any(len(r)!=2 for r in prediction_rows): raise ValueError("pred.list格式错误")
            target=[r for r in prediction_rows if r[0]==trait]
            if len(target)!=1: raise ValueError("预测表型缺失或重复")
            for _,fname in prediction_rows:
                fp=Path(fname)
                if not fp.is_absolute():
                    raise ValueError("预测清单需绝对文件路径；runner step1原生输出应使用绝对前缀")
                if not fp.is_file() or previous.get("outputs",{}).get(str(fp))!=digest(fp): raise ValueError("预测文件缺失或改变")
                inputs.append(fp)
            inputs += [pred,prior]
            cmd+=["--pred",str(pred),"--chrList",",".join(map(str,range(1,23))),"--minMAC",str(mac)]
            if tt=="binary":
                pt=cfg.get("firth_p_threshold")
                if not isinstance(pt,(int,float)) or not 0<pt<=1: raise ValueError("Firth阈值须在0到1")
                cmd+=["--firth","--approx","--pThresh",str(pt)]
    cmd+=["--out",str(out/"association")]
    return cmd,out,inputs,design

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config",type=Path);ap.add_argument("--step",default="association",choices=["association","step1","step2"])
    ap.add_argument("--dry-run",action="store_true");ap.add_argument("--check-env",action="store_true")
    ap.add_argument("--engine",choices=["plink2","regenie"],default="plink2")
    args=ap.parse_args()
    if args.check_env:
        found=shutil.which(args.engine)
        print(json.dumps({"engine":args.engine,"available":bool(found),"path":found},ensure_ascii=False))
        return 0 if found else 2
    if args.config is None: raise ValueError("缺少--config")
    cp=args.config.resolve();cfg=json.loads(cp.read_text(encoding="utf-8"))
    cmd,out,inputs,design=prepare(cfg,cp.parent,args.step)
    if args.dry_run:
        print(json.dumps({"argv":cmd,"output":str(out),"executed":False},ensure_ascii=False,indent=2));return 0
    if not shutil.which(cmd[0]): raise ValueError("软件不存在："+cmd[0])
    # Explicit executable is user-selected code; no shell interpolation.
    out.mkdir(parents=True,exist_ok=False)
    record={"step":args.step,"argv":cmd,"config":cfg,"design":design,"inputs":{str(f):digest(f) for f in inputs},"status":"running"}
    rp=out/"run.json"
    def save(): rp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    save()
    try:
        with (out/"stdout.log").open("w") as stdout,(out/"stderr.log").open("w") as stderr:
            result=subprocess.run(cmd,cwd=out,stdout=stdout,stderr=stderr,check=False)
        record["exit_code"]=result.returncode
        if result.returncode: raise ValueError("后端运行失败；查看stdout/stderr")
        products=[f for f in out.glob("association*") if f.is_file()]
        if not any(f.suffix not in (".log",) for f in products): raise ValueError("后端退出0但缺少分析产物")
        record["outputs"]={str(f):digest(f) for f in products}
        record["status"]="completed";save()
    except BaseException as e:
        record["status"]="failed";record["error"]=str(e);save();raise
    print("后端完成；逐变异模型状态、版本日志和科学校准仍须复核。")
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except (OSError,ValueError,KeyError,TypeError,IndexError) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)
