#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["mebocost @ git+https://github.com/kaifuchenlab/MEBOCOST.git@3e0be6f638b71c0f5bd08cef8b1448ae5230560e", "numpy==2.2.6", "matplotlib==3.10.6", "adjustText==1.3.0", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""MEBOCOST 1.2.2 native metabolite–sensor inference, preserving unfiltered evidence."""
import argparse
import configparser
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from communication_contract import new_output,write_json,add_table,digest
from communication_inputs import read_expression,require_version


def run(config,output):
    from mebocost import mebocost
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version('mebocost','1.2.2')
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg['expression_scale']!='log_normalized':raise ValueError('此适配器需要明确的非负 log_normalized 表达')
    if not cfg.get('database_config') or not cfg.get('database_version'):raise ValueError('必须提供原生数据库配置与版本')
    database=(config.parent/cfg['database_config']).resolve()
    resources=configparser.ConfigParser();resources.read(database)
    paths=[resources['common']['hmdb_info_path'],resources[cfg['species']]['met_enzyme_path'],resources[cfg['species']]['met_sensor_path']]
    if any(not Path(p).is_absolute() or not Path(p).is_file() for p in paths):raise ValueError('原生数据库配置中的实际读取文件必须为存在的绝对路径')
    out=new_output(output);write_json(out/'run_config.json',cfg)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='MEBOCOST',method_version=version,implementation='native',
        provenance={**provenance,'parameters':cfg,'database_sha256':{Path(p).name:digest(p) for p in paths},
                    'metabolite_evidence':'enzyme-expression proxy; no measured metabolite or external flux constraint'},tables=[])
    edges=[]
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique())):
        subset=data[data.obs[keys['sample']]==sample].copy()
        counts=subset.obs[keys['cell_type']].value_counts();minimum=cfg.get('min_cells',50)
        subset=subset[subset.obs[keys['cell_type']].isin(counts[counts>=minimum].index)].copy()
        if subset.obs[keys['cell_type']].nunique()<2:raise ValueError('满足细胞数要求的群少于2')
        obj=mebocost.create_obj(adata=subset,cell_ann=subset.obs.copy(),group_col=keys['cell_type'],
            species=cfg['species'],met_est='mebocost',config_path=str(database),
            cutoff_exp=cfg.get('cutoff_exp','auto'),cutoff_met=cfg.get('cutoff_met','auto'),
            cutoff_prop=cfg.get('expression_fraction',.15),sensor_type=cfg.get('sensor_type','All'),thread=1)
        obj.infer_commu(n_shuffle=cfg.get('n_perms',1000),seed=cfg.get('seed',1),thread=1,Return=True,
            save_permuation=True,pval_method='permutation_test_fdr',pval_cutoff=cfg.get('alpha',.05),min_cell_number=minimum)
        raw=obj.original_result.copy();raw.to_csv(out/f'native_all_{si+1}.tsv',sep='\t',index=False)
        obj.commu_res.to_csv(out/f'native_filtered_{si+1}.tsv',sep='\t',index=False)
        mebocost.save_obj(obj,str(out/f'mebocost_{si+1}.pk'))
        for _,r in raw.iterrows():
            eligible=bool(r['metabolite_prop_in_sender']>obj.cutoff_prop and r['sensor_prop_in_receiver']>obj.cutoff_prop and r['Commu_Score']>=0)
            edges.append(dict(sample=str(sample),donor=str(subset.obs.iloc[0][keys['donor']]),condition=str(subset.obs.iloc[0][keys['condition']]),source=str(r['Sender']),target=str(r['Receiver']),
                metabolite=str(r['Metabolite']),metabolite_name=str(r.get('Metabolite_Name',r['Metabolite'])),sensor=str(r['Sensor']),
                sensor_type=str(r.get('Annotation','unknown')),score=float(r['Commu_Score']),
                p_value=float(r['permutation_test_pval']),q_value=float(r['permutation_test_fdr']),
                tested=True,eligible=eligible,supported=eligible and float(r['permutation_test_fdr'])<cfg.get('alpha',.05)))
    add_table(bundle,out,'metabolite_sensor','metabolite_edges',edges,
        'MEBOCOST 原生酶表达代理–sensor 通讯分数；保留全部已检验结果，支持需通过原生表达比例/非负筛选与FDR；未加入外部通量约束',
        axis_label='MEBOCOST score',value_kind='native_score',additive=False,direction='higher')
    write_json(out/'bundle.json',bundle)
    from render_result_bundle import run as render
    return render(out/'bundle.json',out/'figures')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
