#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["numpy==1.26.4", "pandas==2.2.1", "scipy==1.12.0", "scikit-learn==1.4.1.post1", "statsmodels==0.14.1"]
# ///
"""Run the fixed CSCP coupled-NMF and consensus-clustering implementation."""
from __future__ import annotations
import argparse, importlib.metadata, importlib.util, json, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from communication_contract import add_table,digest,new_output,write_json,write_table

COMMIT="fc035a97a1caf81f7d416f72dd846489b88dc621"
HASHES={"README.md":"5a13932023ff0164d786a5060faf00f5ae1a4c8a6bbccb3a07d43193899f2077","Code/identify_CSCPs.py":"d73704b128f9381573eb861c57e4affd74dca7d47bc0f0cf1d74eda60db053db"}
VERSIONS={"numpy":"1.26.4","pandas":"2.2.1","scipy":"1.12.0","scikit-learn":"1.4.1.post1","statsmodels":"0.14.1"}

def resolved(base,value):return (base/value).resolve()
def verify(root):
    for name,expected in HASHES.items():
        if not (root/name).is_file() or digest(root/name)!=expected:raise ValueError(f"CSCP固定源码缺失或摘要不符: {name}")
    commit=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if commit!=COMMIT:raise ValueError(f"CSCP源码提交不符: {commit}")
    if sys.version_info[:2]!=(3,10):raise ValueError("CSCP固定环境需要Python 3.10")
    observed={k:importlib.metadata.version(k) for k in VERSIONS}
    if observed!=VERSIONS:raise ValueError(f"CSCP依赖版本不符: {observed}")
    spec=importlib.util.spec_from_file_location("fixed_cscp",root/"Code/identify_CSCPs.py");module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,observed

def matrix(path,separator):
    frame=pd.read_csv(path,sep=separator,index_col=0)
    if frame.index.has_duplicates or frame.columns.has_duplicates or frame.empty:raise ValueError(f"表达矩阵身份重复或为空: {path}")
    try:frame=frame.astype(float)
    except Exception as exc:raise ValueError(f"表达矩阵必须为数值: {path}") from exc
    if not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy()<0).any() or frame.shape[1]<10:raise ValueError("CSCP表达必须有限、非负且每侧至少10个细胞")
    return frame

def run(config,output):
    config=Path(config).resolve();cfg=json.loads(config.read_text());base=config.parent
    required=("dataset","research_question","sender_expression","receiver_expression","ligand_receptor_resource","native_root","sender_label","receiver_label","input_provenance","resource_provenance","expression_scale","normalization_definition")
    for key in required:
        if cfg.get(key) in (None,"",[]):raise ValueError("CSCP配置缺少: "+key)
    paths={key:resolved(base,cfg[key]) for key in ("sender_expression","receiver_expression","ligand_receptor_resource","native_root")}
    if any(not p.exists() for p in paths.values()):raise ValueError("CSCP输入或固定源码路径不存在")
    module,versions=verify(paths["native_root"]);sep=cfg.get("expression_separator",",")
    sender=matrix(paths["sender_expression"],sep);receiver=matrix(paths["receiver_expression"],sep)
    if set(sender.columns)&set(receiver.columns):raise ValueError("发送与接收细胞ID必须互斥")
    lr=pd.read_csv(paths["ligand_receptor_resource"],sep=cfg.get("resource_separator","\t"))
    if not {"Ligand","Receptor"}<=set(lr):raise ValueError("LR资源必须包含Ligand/Receptor")
    lr=lr[["Ligand","Receptor"]].dropna().astype(str).drop_duplicates()
    if (lr.apply(lambda x:x.str.strip())=="").any().any():raise ValueError("LR资源含空身份")
    k=cfg.get("sub_crosstalk_pairs",2)
    if type(k) is not int or not 2<=k<=6 or k>min(sender.shape[1],receiver.shape[1]):raise ValueError("sub_crosstalk_pairs必须为2–6且不超过任一侧细胞数")
    out=new_output(output);write_json(out/"run_config.json",cfg)
    XR,XL,GL,GR,CL,CR,covered=module.preprocessing_expression_matrix(lr,sender,receiver)
    if min(len(GL),len(GR))<k or covered.empty:raise ValueError("实测表达与LR资源交集不足以拟合CSCP")
    # The fixed upstream functions read these four names from module globals,
    # matching the authors' command-line entry point.
    module.XR=XR;module.XL=XL;module.GL=GL;module.GR=GR
    A=module.construct_ligand_receptor_matrix(covered,GL,GR)
    runs_l,runs_r=module.identifying_cellSubCrossTalkPairs_candidates(XL,XR,A,k)
    if len(runs_l)!=5 or len(runs_r)!=5:raise ValueError(f"CSCP原生5次初始化只有{len(runs_l)}次成功；不静默接受")
    consensus=module.construct_coupled_concensus_matrix(runs_l,runs_r);cluster=module.hierarchical_clustering(consensus,k)
    cells=list(CL)+list(CR);domains=["sender"]*len(CL)+["receiver"]*len(CR);labels=cluster.astype(int)+1
    native_arrays=out/"cscp_native_arrays.npz"
    np.savez_compressed(native_arrays,A=np.asarray(A,dtype=float),sender_restart_labels=np.asarray(runs_l,dtype=int),receiver_restart_labels=np.asarray(runs_r,dtype=int),consensus_counts=np.asarray(consensus,dtype=float),final_cluster_zero_based=np.asarray(cluster,dtype=int),sender_cells=np.asarray(CL,dtype=str),receiver_cells=np.asarray(CR,dtype=str),ligand_genes=np.asarray(GL,dtype=str),receptor_genes=np.asarray(GR,dtype=str))
    assignments=[dict(cell=cell,domain=domain,sub_crosstalk_pair=int(label)) for cell,domain,label in zip(cells,domains,labels)]
    write_table(out/"cscp_cell_assignments.tsv",assignments)
    complete=pd.DataFrame(consensus/5,index=[f"{d} | {c}" for d,c in zip(domains,cells)],columns=[f"{d} | {c}" for d,c in zip(domains,cells)])
    complete.to_csv(out/"cscp_complete_consensus.tsv.gz",sep="\t",compression="gzip")
    chosen=[]
    for domain in ("sender","receiver"):
        for pair in range(1,k+1):
            chosen.extend([i for i,(d,z) in enumerate(zip(domains,labels)) if d==domain and z==pair][:20])
    shown=[f"{domains[i]} | pair {labels[i]} | {cells[i]}" for i in chosen]
    consensus_rows=[dict(row=shown[i],column=shown[j],value=float(consensus[a,b]/5)) for i,a in enumerate(chosen) for j,b in enumerate(chosen)]
    size_rows=[]
    for pair in range(1,k+1):
        for domain in ("sender","receiver"):size_rows.append(dict(row=f"Pair {pair}",column=f"{domain.title()} cells",value=int(sum((labels==pair)&(np.asarray(domains)==domain)))))
    combined=[np.r_[a,b] for a,b in zip(runs_l,runs_r)];restart_rows=[]
    for i in range(5):
        for j in range(5):restart_rows.append(dict(row=f"Restart {i+1}",column=f"Restart {j+1}",value=float(adjusted_rand_score(combined[i],combined[j]))))
    lr_rows=[]
    covered=covered.drop_duplicates(["Ligand","Receptor"])
    for pair in range(1,k+1):
        smask=labels[:len(CL)]==pair;rmask=labels[len(CL):]==pair
        for row in covered.itertuples(index=False):
            ligand_mean=float(XL.loc[row.Ligand].to_numpy()[smask].mean());receptor_mean=float(XR.loc[row.Receptor].to_numpy()[rmask].mean());score=ligand_mean*receptor_mean
            lr_rows.append(dict(sample=cfg["dataset"],source=f'{cfg["sender_label"]} subgroup {pair}',target=f'{cfg["receiver_label"]} subgroup {pair}',ligand=row.Ligand,receptor=row.Receptor,interaction=f"{row.Ligand}→{row.Receptor}",score=score,tested=True,supported=score>0,ligand_mean=ligand_mean,receptor_mean=receptor_mean))
    bundle=dict(schema_version=2,dataset=cfg["dataset"],method="CSCP",method_version="fixed source commit fc035a9",implementation="native_coupled_nmf_five_restart_consensus",provenance=dict(input_provenance=cfg["input_provenance"],resource_provenance=cfg["resource_provenance"],expression_scale=cfg["expression_scale"],normalization_definition=cfg["normalization_definition"],upstream=dict(url="https://github.com/GaoLabXDU/cell-sub-crosstalk-pair",commit=COMMIT,license="not declared in fixed repository"),source_hashes=HASHES,input_hashes={k:digest(v) for k,v in paths.items() if v.is_file()},versions=versions,parameters=dict(sub_crosstalk_pairs=k,native_restarts=5,nmf_initializations_per_restart=50,nmf_initial_max_iter=50,final_nmf_max_iter=1000,coupled_nmf_max_iter=500),native_arrays=dict(path=native_arrays.name,sha256=digest(native_arrays),contents=["normalized LR Laplacian","five sender restart label vectors","five receiver restart label vectors","consensus counts","final cluster","ordered identities"]),complete_consensus=dict(path="cscp_complete_consensus.tsv.gz",sha256=digest(out/"cscp_complete_consensus.tsv.gz")),complete_assignments=dict(path="cscp_cell_assignments.tsv",sha256=digest(out/"cscp_cell_assignments.tsv")),limitations=["CSCP发现的是两个预先指定细胞类型之间配对的细胞亚群，不是全部细胞类型通讯网络。","最终AgglomerativeClustering按固定源码把1-consensus矩阵当作特征而非预计算距离；入口保留这一行为。","亚群LR分数是原生按细胞最大值归一化后两端群均值乘积，用于解释配对亚群，不是coupled-NMF目标值、P值或结合概率。","固定源码未声明软件许可；plugin只编排用户提供的外部固定源码，不复制上游代码或数据。"]),tables=[])
    add_table(bundle,out,"cscp_consensus","matrix",consensus_rows,"从5次原生coupled-NMF分群得到的共同聚类比例；仅按每个domain×pair原始顺序前20个细胞显示，完整细胞×细胞矩阵另存。",figure_role="cscp_consensus",value_kind="native_score",additive=False,row_order=shown,column_order=shown)
    add_table(bundle,out,"cscp_pair_sizes","matrix",size_rows,"最终共识层次聚类中每个配对CSCP的发送与接收细胞数。",figure_role="cscp_pair_sizes",value_kind="count",additive=False,row_order=[f"Pair {i}" for i in range(1,k+1)],column_order=["Sender cells","Receiver cells"])
    add_table(bundle,out,"cscp_restart_agreement","matrix",restart_rows,"5次原生coupled-NMF联合发送/接收标签之间的adjusted Rand index；这是适配器透明质量诊断。",figure_role="cscp_restart_agreement",value_kind="native_score",additive=False,row_order=[f"Restart {i}" for i in range(1,6)],column_order=[f"Restart {i}" for i in range(1,6)])
    add_table(bundle,out,"cscp_lr_profiles","lr_edges",lr_rows,"每个配对亚群中，固定源码按每个细胞最大值归一化后的ligand发送均值×receptor接收均值；supported只表示乘积大于0，不是显著性。",value_kind="native_score",additive=False,direction="higher",axis_label="Normalized endpoint mean product",statistical_unit="paired sender/receiver subgroups",test_definition="No inferential test",display_top_lr=20,display_top_cell_pairs=k)
    bundle["figure_inapplicability"]={"condition_effects":"CSCP固定算法不拟合供体条件效应。","cellchat_patterns":"CSCP不是CellChat NMF。","ligand_response":"CSCP不预测靶基因响应。","intracellular":"CSCP没有TF或靶基因层。","enrichment":"CSCP没有背景定义的富集检验。","embedding":"固定源码不输出低维潜在坐标。","spatial_location":"CSCP不使用组织坐标。","spatial_hotspots":"CSCP不计算空间热点。","spatial_direction":"CSCP不计算空间方向。","neighborhood_response":"CSCP不计算空间邻域响应。","relay_dynamic":"CSCP没有时间或多跳动态。","special_molecules":"当前LR资源只有基因端点。","functional_clinical":"CSCP不计算功能、临床或药敏关联。"}
    write_json(out/"bundle.json",bundle);write_json(out/"run_metadata.json",dict(status="completed_native",source_commit=COMMIT,successful_restarts=5,cells=len(cells),covered_lr=len(covered)));return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--config",required=True);p.add_argument("--out",required=True);a=p.parse_args();raise SystemExit(run(a.config,a.out))
