#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["spatialdm==0.3.1", "setuptools==80.9.0", "anndata==0.13.3.post0", "numpy==2.2.6", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""SpatialDM native global/local spatial association, with complete-complex checks."""
import argparse
import importlib.resources
import json
from pathlib import Path
import pickle
import sys
sys.dont_write_bytecode=True
import numpy as np
from communication_contract import new_output,write_json,add_table,digest
from communication_inputs import read_expression,require_version


def run(config,output):
    import pandas as pd
    import spatialdm as sd
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version("spatialdm","0.3.1")
    data,keys,provenance=read_expression(cfg,config.parent)
    if not cfg.get("coordinate_provenance") or cfg.get("coordinate_unit")!="um":
        raise ValueError("必须提供实际 μm 坐标来源；UMAP 不可作空间坐标")
    skey=cfg.get("spatial_key","spatial")
    if skey not in data.obsm or data.obsm[skey].shape[1]!=2 or not np.isfinite(data.obsm[skey]).all():raise ValueError("空间坐标缺失或无效")
    if cfg.get("bandwidth_um",0)<=0:raise ValueError("必须根据组织与测量分辨率设定 bandwidth_um")
    data.obsm['spatial']=np.asarray(data.obsm[skey]).copy()
    out=new_output(output);write_json(out/"run_config.json",cfg)
    resource=Path(sd.__file__).parent/'datasets/LR_data'
    fp=resource/f"{cfg['species']}-interaction_input_CellChatDB.csv.gz"
    cp=resource/f"{cfg['species']}-complex_input_CellChatDB.csv"
    db=pd.read_csv(fp,index_col=0);complexes=pd.read_csv(cp,index_col=0)
    complete=set()
    for interaction,row in db.iterrows():
        genes=[]
        for molecule in (row['ligand'],row['receptor']):
            genes.extend(complexes.loc[molecule].dropna().astype(str).tolist() if molecule in complexes.index else [molecule])
        if set(genes)<=set(data.var_names):complete.add(interaction)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='SpatialDM',method_version=version,implementation='native',
        provenance={**provenance,'parameters':cfg,'database_files':{fp.name:digest(fp),cp.name:digest(cp)},
                    'complex_policy':'排除缺失任何亚基的原生候选；不以仅检测到的部分亚基替代完整复合物'},tables=[])
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique())):
        subset=data[data.obs[keys['sample']]==sample].copy()
        # Native local statistic reads raw.to_adata(); preserve exactly the declared
        # normalized input before native global standardization modifies X.
        subset.raw=subset.copy()
        if subset.n_obs<20:raise ValueError("该样本不足20个空间位置，需重新核验空间空模型适用性")
        np.random.seed(cfg.get('seed',1))
        sd.extract_lr(subset,species=cfg['species'],min_cell=cfg.get('min_cells',10),datahost='package')
        keep=subset.uns['geneInter'].index.intersection(sorted(complete))
        for key in ('ligand','receptor','geneInter'):subset.uns[key]=subset.uns[key].loc[keep]
        subset.uns['num_pairs']=len(keep)
        if not len(keep):raise ValueError("完整复合物过滤后没有可检验 LR")
        sd.weight_matrix(subset,l=cfg['bandwidth_um'],cutoff=cfg.get('weight_cutoff',.1),single_cell=cfg.get('single_cell',False))
        method=cfg.get('null_method','z-score')
        if method not in ('z-score','permutation'):raise ValueError("null_method 必须为 z-score 或 permutation")
        sd.spatialdm_global(subset,n_perm=cfg.get('n_perms',1000),method=method,nproc=1)
        sd.sig_pairs(subset,method=method,fdr=True,threshold=cfg.get('alpha',.05))
        native=subset.uns['global_res'];native.to_csv(out/f"native_global_{si+1}.tsv",sep='\t')
        add_table(bundle,out,f"global_fdr_{si+1}",'matrix',[dict(row=str(i),column=str(sample),value=float(r['fdr'])) for i,r in native.iterrows()],
            'SpatialDM 原生全局空间关联 FDR；不是分子流量或供体条件效应',axis_label='Global spatial FDR',value_kind='p_value',display_top_rows=30,direction='lower')
        selected=native[native['selected']].sort_values('fdr').index[:cfg.get('top_lr',6)]
        if len(selected):
            sd.spatialdm_local(subset,n_perm=cfg.get('n_perms',1000),method=method,specified_ind=selected,nproc=1)
            sd.sig_spots(subset,method=method,fdr=True,threshold=cfg.get('alpha',.05))
            q=subset.uns['local_stat']['local_fdr']
            q.to_csv(out/f"native_local_fdr_{si+1}.tsv",sep='\t')
            for li,interaction in enumerate(selected):
                values=q.loc[interaction].to_numpy()
                points=[dict(sample=str(sample),cell=str(cell),x=float(xy[0]),y=float(xy[1]),value=float(v))
                        for cell,xy,v in zip(subset.obs_names,subset.obsm['spatial'],values)]
                add_table(bundle,out,f"hotspot_{si+1}_{li+1}",'spatial_points',points,
                    f'{interaction}: 原生局部空间关联 FDR；全局选取前{cfg.get("top_lr",6)}项后进行局部检验，校正范围为本次全部局部检验位置与所选LR',
                    coordinate_unit='um',axis_label='Local spatial FDR',value_kind='p_value',y_down=cfg.get('y_down',False))
        with (out/f"spatialdm_{si+1}.pkl").open('wb') as stream:pickle.dump(subset,stream)
    write_json(out/'bundle.json',bundle)
    from render_result_bundle import run as render
    return render(out/'bundle.json',out/'figures')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
