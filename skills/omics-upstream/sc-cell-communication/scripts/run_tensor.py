#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["cell2cell==0.9.0", "numpy==2.2.6", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""Native Tensor-cell2cell factorization with explicit missing-observation masks."""
import argparse
import csv
import json
import pickle
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from communication_contract import new_output,write_json,add_table,digest,truth
from communication_inputs import require_version


def run(config,output):
    import cell2cell as c2c
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version("cell2cell","0.9.0")
    path=(config.parent/cfg["input"]).resolve()
    if not cfg.get("score_definition") or cfg.get("score_transform","identity") not in ("identity","one_minus_rank"):
        raise ValueError("张量必须声明同义输入分数与 identity/one_minus_rank 转换")
    if not cfg.get("provenance_files"):
        raise ValueError("须提供每样本机器可读的 provenance_files，不能只凭手写声明比较")
    upstream=[]
    for value in cfg["provenance_files"]:
        fp=(config.parent/value).resolve();p=json.loads(fp.read_text())
        if any(not p.get(k) for k in ("method_version","database_sha256","comparison_parameters")):
            raise ValueError("上游来源缺版本、数据库指纹或实际推断参数")
        upstream.append(p)
    signatures={(p.get("method"),p["method_version"],p["database_sha256"],json.dumps(p["comparison_parameters"],sort_keys=True)) for p in upstream}
    if len(signatures)!=1:raise ValueError("张量输入方法、数据库或实际参数不一致")
    with path.open() as f:
        reader=csv.DictReader(f,delimiter="\t")
        required={"sample","donor","condition","source","target","ligand","receptor","score","tested"}
        if not required<=set(reader.fieldnames or []):raise ValueError("输入缺少张量、供体或可检验字段")
        rows=list(reader)
    samples=sorted({r["sample"] for r in rows});lrs=sorted({(r["ligand"],r["receptor"]) for r in rows})
    provenance_samples=[p.get("config",{}).get("sample") for p in upstream]
    if len(provenance_samples)!=len(set(provenance_samples)) or set(provenance_samples)!=set(samples):
        raise ValueError("上游来源没有逐一样本覆盖张量输入")
    senders=sorted({r["source"] for r in rows});receivers=sorted({r["target"] for r in rows})
    if len(samples)<3:raise ValueError("跨样本模式至少需要3个样本；不将细胞随机分组当独立样本")
    metadata={}
    for r in rows:
        value=(r["donor"],r["condition"])
        if r["sample"] in metadata and metadata[r["sample"]]!=value:raise ValueError("样本供体/条件映射冲突")
        metadata[r["sample"]]=value
    shape=(len(samples),len(lrs),len(senders),len(receivers))
    if np.prod(shape)>cfg.get("max_tensor_elements",20_000_000):raise ValueError("张量超出内存契约；需预先定义科学子集或更大资源")
    indices=[{key:i for i,key in enumerate(values)} for values in (samples,lrs,senders,receivers)]
    tensor=np.full(shape,np.nan,dtype=float);seen=set()
    for r in rows:
        key=tuple(mapping[value] for mapping,value in zip(indices,(r["sample"],(r["ligand"],r["receptor"]),r["source"],r["target"])))
        if key in seen:raise ValueError("张量位置重复；不静默聚合")
        seen.add(key)
        if truth(r["tested"]) and r["score"] not in ("","NA","None"):
            score=float(r["score"])
            if not np.isfinite(score) or score<0:raise ValueError("张量需要有限非负输入")
            if cfg.get("score_transform")=="one_minus_rank":
                if score>1:raise ValueError("one_minus_rank 需要 [0,1] 原生排名")
                score=1-score
            tensor[key]=score
    mask=np.isfinite(tensor).astype(int)
    if not np.any(np.nan_to_num(tensor)>0):raise ValueError("无非零可观测张量，不能拟合模式")
    for axis in range(4):
        axes=tuple(i for i in range(4) if i!=axis)
        if np.any(mask.sum(axis=axes)==0):raise ValueError("某张量实体从未可检验，先明确排除该实体及其原因")
    out=new_output(output);write_json(out/"run_config.json",cfg)
    np.savez_compressed(out/"tensor_input.npz",tensor=tensor,mask=mask)
    labels=[samples,[a+" — "+b for a,b in lrs],senders,receivers]
    obj=c2c.tensor.PreBuiltTensor(tensor,order_names=labels,order_labels=["sample","ligand_receptor","sender","receiver"],mask=mask)
    upper=min(cfg.get("upper_rank",5),max(2,len(samples)-1))
    rank=cfg.get("rank")
    _,loss=obj.elbow_rank_selection(upper_rank=upper,runs=cfg.get("diagnostic_runs",3),random_state=cfg.get("seed",1),
        n_iter_max=cfg.get("max_iter",200),output_fig=False,automatic_elbow=rank is None,manual_elbow=rank)
    rank=obj.rank if rank is None else rank
    if not isinstance(rank,(int,np.integer)) or not 1<=rank<=upper:raise ValueError("原生 elbow 未确定合法模式数；检查诊断，不默默选择")
    obj.compute_tensor_factorization(rank=rank,tf_type="non_negative_cp",init="random",random_state=cfg.get("seed",1),
        runs=cfg.get("runs",5),n_iter_max=cfg.get("max_iter",200),tol=1e-7)
    with (out/"tensor_cell2cell.pkl").open("wb") as f:pickle.dump(obj,f)
    bundle=dict(schema_version=2,dataset=cfg["dataset"],method="Tensor-cell2cell",method_version=version,implementation="native",
        provenance=dict(input_sha256=digest(path),parameters=cfg,missing_policy="native mask; missing values never treated as measured zero",
                        tensor_shape=shape,observed=int(mask.sum()),rank=int(rank)),tables=[])
    add_table(bundle,out,"rank_diagnostic","matrix",[dict(row="normalized_error",column=str(k),value=float(v)) for k,v in loss],
              "原生重复拟合的秩诊断误差；模式数不是唯一生物学真值",axis_label="Normalized error")
    factor_rows=[];sample_rows=[]
    for dim,frame in obj.factors.items():
        frame.to_csv(out/(dim+"_native_factors.tsv"),sep="\t")
        for entity,values in frame.iterrows():
            for factor,value in values.items():
                factor_rows.append(dict(dimension=dim,entity=str(entity),factor=str(factor),value=float(value)))
                if dim=="sample":
                    donor,condition=metadata[entity]
                    sample_rows.append(dict(sample=entity,donor=donor,condition=condition,feature=factor,value=float(value)))
    add_table(bundle,out,"factor_loadings","patterns",factor_rows,"原生非负CP归一化载荷；只比较同一因子同一维度",axis_label="Factor loading")
    if len({(r['donor'],r['condition'],r['feature']) for r in sample_rows})==len(sample_rows):
        add_table(bundle,out,"sample_factors","effects",sample_rows,"供体样本因子载荷；此处不执行条件显著性检验",axis_label="Sample factor loading")
    write_json(out/"bundle.json",bundle)
    from render_result_bundle import run as render
    return render(out/"bundle.json",out/"figures")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
