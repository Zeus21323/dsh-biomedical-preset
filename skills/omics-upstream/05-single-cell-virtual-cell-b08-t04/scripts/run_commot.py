#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["commot==0.0.3", "numpy==1.22.4", "scipy==1.10.1", "anndata==0.9.2", "scanpy==1.9.8", "pandas==1.3.5", "matplotlib==3.7.5"]
# ///
"""COMMOT native transport and direction; exports typed results for modern plotting runtime."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from communication_contract import new_output,write_json,add_table,digest
from communication_inputs import read_expression,require_version


def run(config,output):
    import pandas as pd
    import commot as ct
    config=Path(config).resolve();cfg=json.loads(config.read_text());version=require_version('commot','0.0.3')
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg.get('coordinate_unit')!='um' or not cfg.get('coordinate_provenance') or cfg.get('distance_um',0)<=0:
        raise ValueError('必须提供 μm 坐标、来源与生物学距离范围；不能使用 UMAP 坐标')
    skey=cfg.get('spatial_key','spatial')
    if skey not in data.obsm or data.obsm[skey].shape[1]!=2 or not np.isfinite(data.obsm[skey]).all():raise ValueError('需要真实二维空间坐标')
    if cfg['expression_scale']!='log_normalized':raise ValueError('此 COMMOT 工作流要求明确 log_normalized 输入')
    data.obsm['spatial']=np.asarray(data.obsm[skey]).copy()
    out=new_output(output);write_json(out/'run_config.json',cfg)
    resource=ct.pp.ligand_receptor_database(database='CellChat',species=cfg['species']) if not cfg.get('resource_file') else pd.read_csv(config.parent/cfg['resource_file'],sep='\t',header=None)
    if resource.shape[1]<3:raise ValueError('COMMOT LR 表必须有 ligand/receptor/pathway 三列')
    if cfg.get('analysis_pathways'):
        if not set(cfg['analysis_pathways'])<=set(resource.iloc[:,2]):raise ValueError('指定通路在资源中不存在')
        resource=resource[resource.iloc[:,2].isin(cfg['analysis_pathways'])].copy()
    resource.to_csv(out/'resource.tsv',sep='\t',index=False,header=False)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='COMMOT',method_version=version,implementation='native',
        provenance={**provenance,'parameters':cfg,'resource_sha256':digest(out/'resource.tsv'),
                    'scope':'仅对实际传入的LR资源联合建模竞争；子集推断不能冒充完整数据库推断'},tables=[])
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique())):
        subset=data[data.obs[keys['sample']]==sample].copy()
        if subset.n_obs>cfg.get('max_spots',5000):raise ValueError('超出当前内存范围，需显式定义组织区域或更大资源')
        complete=resource.apply(lambda r: all(g in subset.var_names for v in r.iloc[:2] for g in str(v).split('_')),axis=1)
        rs=resource[complete].copy()
        rs=ct.pp.filter_lr_database(rs,subset,min_cell_pct=cfg.get('expression_fraction',.05))
        if not len(rs):raise ValueError('完整复合物及表达过滤后无可检验LR')
        rs.to_csv(out/f'tested_resource_{si+1}.tsv',sep='\t',index=False,header=False)
        ct.tl.spatial_communication(subset,database_name='registered',df_ligrec=rs,dis_thr=cfg['distance_um'],
            heteromeric=True,heteromeric_rule='min',pathway_sum=True,cot_nitermax=cfg.get('max_iter',10000))
        pathways=list(dict.fromkeys(rs.iloc[:,2]))
        totals={path:float(subset.obsp['commot-registered-'+path].sum()) for path in pathways}
        selected=sorted(pathways,key=lambda p:(-totals[p],p))[:cfg.get('top_pathways',3)]
        write_json(out/f'selection_{si+1}.json',dict(pathway_totals=totals,selected=selected,rule='实际建模范围内总传输分数前列，探索性选择'))
        for pi,pathway in enumerate(selected):
            ct.tl.communication_direction(subset,database_name='registered',pathway_name=pathway,k=min(cfg.get('direction_k',5),subset.n_obs-1))
            matrix=subset.obsp['commot-registered-'+pathway].tocsr();strength=np.asarray(matrix.sum(axis=1)).ravel()
            points=[dict(sample=str(sample),cell=str(cell),x=float(xy[0]),y=float(xy[1]),value=float(v))
                for cell,xy,v in zip(subset.obs_names,subset.obsm['spatial'],strength)]
            add_table(bundle,out,f'location_{si+1}_{pi+1}','spatial_points',points,f'{pathway}: COMMOT原生发送总传输分数；并非实测分子通量',
                coordinate_unit='um',value_kind='nonnegative_strength',axis_label='Transport score',y_down=cfg.get('y_down',False))
            for direction in ('sender','receiver'):
                vectors=subset.obsm['commot_'+direction+'_vf-registered-'+pathway]
                vector_rows=[dict(sample=str(sample),cell=str(cell),x=float(xy[0]),y=float(xy[1]),dx=float(v[0]),dy=float(v[1]))
                    for cell,xy,v in zip(subset.obs_names,subset.obsm['spatial'],vectors)]
                scale=cfg.get('vector_scale',float(np.linalg.norm(vectors,axis=1).max())/(cfg['distance_um']*.2) or 1)
                add_table(bundle,out,f'vectors_{direction}_{si+1}_{pi+1}','spatial_vectors',vector_rows,f'{pathway}: COMMOT原生{direction}方向向量，箭头缩放仅用于显示',
                    coordinate_unit='um',direction_definition='COMMOT communication_direction: native weighted direction and marginal score',vector_scale=scale,y_down=cfg.get('y_down',False))
            coo=matrix.tocoo()
            edges=[dict(sample=str(sample),source_cell=str(subset.obs_names[a]),target_cell=str(subset.obs_names[b]),value=float(v))
                   for a,b,v in zip(coo.row,coo.col,coo.data) if v>0]
            add_table(bundle,out,f'edges_{si+1}_{pi+1}','spatial_edges',edges,f'{pathway}: 原生非零运输边；距离范围进入模型',coordinate_unit='um',value_kind='nonnegative_strength',y_down=cfg.get('y_down',False))
        subset.write_h5ad(out/f'commot_{si+1}.h5ad')
    write_json(out/'bundle.json',bundle)
    # Rendering is deliberately in the parent modern environment; no inference result
    # is translated into another method when the old scientific dependencies differ.
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
