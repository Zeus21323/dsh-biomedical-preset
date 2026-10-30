#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["numpy==1.26.4", "pandas==1.5.3", "anndata==0.9.2", "openpyxl==3.1.5", "xlsxwriter==3.2.9"]
# ///
"""Execute the pinned NATMI ExtractEdges CLI, preserving expression and specificity separately."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
from communication_contract import new_output,write_json,add_table,digest
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,gene_identity

COMMIT='c7ad5a953ff85a9a69f6c397fae26747a0f13e01'
SCRIPT_SHA256='d6d92b3480577b6f990d91fb607c4b21ccf24a8706734b3b17529abaee9552e8'


def run(config,output):
    import pandas as pd
    import numpy as np
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    require_version('pandas','1.5.3');require_version('numpy','1.26.4')
    require_version('openpyxl','3.1.5');require_version('xlsxwriter','3.2.9')
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg['species']!='human':raise ValueError('此原生适配分支仅核验human；不默默进行一对多同源映射')
    if cfg['expression_scale'] not in ('normalized','log_normalized'):raise ValueError('需要明确的归一化表达；原始counts先使用合适的归一化步骤')
    if not cfg.get('normalization_definition'):raise ValueError('需要实际归一化方法与尺度说明')
    native_root=(config.parent/cfg['native_root']).resolve();script=native_root/'ExtractEdges.py'
    if digest(script)!=SCRIPT_SHA256:raise ValueError('NATMI原生脚本不符合已核验固定提交')
    resource=native_root/'lrdbs/lrc2p.csv'
    if not resource.is_file():raise ValueError('缺少原生connectomeDB2020 literature-supported资源')
    out=new_output(output);write_json(out/'run_config.json',cfg)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='NATMI',method_version='git:'+COMMIT,implementation='native',
        provenance={**provenance,'parameters':cfg,'native_script_sha256':digest(script),'database_sha256':{'lrc2p.csv':digest(resource)},
          'molecule_identity_schema':SCHEMA,'scope':'原生gene-symbol LR资源，不能声称完整异源复合物模型；无置换或联合P/FDR',
          'support_definition':'原生检测比例、两端表达与specificity展示阈值的显式筛选；是探索性保留规则，不是显著性'},tables=[])
    all_expression=[];all_specificity=[]
    detection=cfg.get('detection_threshold',.2);specificity=cfg.get('specificity_threshold',0);expression=cfg.get('expression_threshold',0)
    if not 0<=detection<=1 or not 0<=specificity<=1 or expression<0:raise ValueError('探索性筛选阈值无效')
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique()),1):
        sub=data[data.obs[keys['sample']]==sample].copy();sizes=sub.obs[keys['cell_type']].value_counts()
        sub=sub[sub.obs[keys['cell_type']].isin(sizes[sizes>=cfg.get('min_cells',10)].index)].copy()
        if sub.obs[keys['cell_type']].nunique()<2:raise ValueError('合格细胞群少于2')
        matrix=sub.X.toarray() if hasattr(sub.X,'toarray') else np.asarray(sub.X)
        if cfg['expression_scale']=='log_normalized':matrix=np.expm1(matrix)
        if not np.isfinite(matrix).all():raise ValueError('还原线性表达产生非有限值')
        em=out/f'expression_{si}.tsv';ann=out/f'annotation_{si}.tsv'
        pd.DataFrame(matrix.T,index=sub.var_names,columns=sub.obs_names).to_csv(em,sep='\t')
        pd.DataFrame({'cluster':sub.obs[keys['cell_type']]},index=sub.obs_names).to_csv(ann,sep='\t')
        folder=out/f'native_{si}'
        command=[sys.executable,str(script),'--species','human','--interSpecies','human','--idType','symbol','--interDB','lrc2p',
                 '--emFile',str(em),'--annFile',str(ann),'--coreNum','1','--out',str(folder)]
        with (out/f'native_{si}.log').open('w') as log:
            result=subprocess.run(command,cwd=native_root,stdout=log,stderr=subprocess.STDOUT,check=False,timeout=cfg.get('timeout_seconds',7200))
        if result.returncode:raise RuntimeError('原生NATMI执行失败，保留日志；不使用其他方法代替')
        path=folder/'Edges_lrc2p.csv'
        if not path.is_file():raise ValueError('原生NATMI未产生候选表，不能按成功网络交付')
        rows=pd.read_csv(path)
        for _,r in rows.iterrows():
            source,target=str(r['Sending cluster']),str(r['Target cluster']);ligand,receptor=str(r['Ligand symbol']),str(r['Receptor symbol'])
            weight=float(r['Edge average expression weight']);specific=float(r['Edge average expression derived specificity'])
            if not np.isfinite(weight) or not np.isfinite(specific):raise ValueError('原生权重非有限')
            supported=(r['Ligand detection rate']>detection and r['Receptor detection rate']>detection and
                       r['Ligand average expression value']>expression and r['Receptor average expression value']>expression and specific>specificity)
            row=dict(sample=str(sample),donor=str(sub.obs.iloc[0][keys['donor']]),condition=str(sub.obs.iloc[0][keys['condition']]),source=source,target=target,
                ligand=ligand,receptor=receptor,interaction=ligand+' -> '+receptor,ligand_identity=gene_identity([ligand]),receptor_identity=gene_identity([receptor]),
                tested=True,supported=bool(supported),ligand_detection_fraction=float(r['Ligand detection rate']),receptor_detection_fraction=float(r['Receptor detection rate']))
            all_expression.append(dict(row,score=weight));all_specificity.append(dict(row,score=specific))
    add_table(bundle,out,'expression_edges','lr_edges',all_expression,'NATMI原生两端平均线性表达乘积；支持标记为声明的检测/表达/特异性阈值，不是P/FDR',
              value_kind='nonnegative_strength',additive=True,axis_label='NATMI mean-expression weight',candidate_scope='native_positive_only')
    add_table(bundle,out,'specificity_edges','lr_edges',all_specificity,'NATMI原生平均表达特异性乘积；两端各群平均表达占比相乘，不是概率或P值；与表达权重分开展示',
              value_kind='nonnegative_strength',additive=True,axis_label='NATMI specificity weight',candidate_scope='native_positive_only')
    write_json(out/'bundle.json',bundle)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();sys.exit(run(a.config,a.out))
