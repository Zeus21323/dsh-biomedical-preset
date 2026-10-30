#!/usr/bin/env python3
"""原生cell2cell单细胞通讯与细胞对整体相似度；不代替Tensor分解。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse
import hashlib
import json
from pathlib import Path
import pickle
from communication_contract import add_table,digest,new_output,write_json,write_table
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,gene_identity


def run(config,output):
    import numpy as np
    import pandas as pd
    import cell2cell as c2c
    from cell2cell.stats import multitest
    require_version('cell2cell','0.9.0')
    cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    for k in ('dataset','research_question','resource_file','resource_version','resource_provenance','resource_species'):
        if not cfg.get(k):raise ValueError('缺少：'+k)
    data,keys,provenance=read_expression(cfg,cp.parent)
    if cfg['resource_species']!=cfg['species']:raise ValueError('资源和表达物种不一致')
    rp=(cp.parent/cfg['resource_file']).resolve();resource=pd.read_csv(rp,sep='\t',dtype=str)
    if not {'ligand','receptor'}<=set(resource) or resource[['ligand','receptor']].isna().any().any():raise ValueError('资源需要完整ligand/receptor列')
    resource=resource[['ligand','receptor']].drop_duplicates().reset_index(drop=True)
    sep=cfg.get('complex_separator')
    if sep not in (None,'&'):raise ValueError('复合体需显式使用&分隔，单基因使用null；不按基因名连字符猜亚基')
    if sep is None and resource.map(lambda v:'&' in v).any().any():raise ValueError('存在复合体时需明确complex_separator')
    def subunits(v):
        parts=v.split(sep) if sep else [v]
        if any(not p.strip() for p in parts) or len(parts)!=len(set(parts)):raise ValueError('复合体含空或重复亚基')
        return parts
    resource['complete']=resource.apply(lambda r:all(g in data.var_names for v in (r.ligand,r.receptor) for g in subunits(v)),axis=1)
    measured=resource[resource.complete].copy()
    if measured.empty:raise ValueError('没有全部亚基可测的LR')
    # Native constructor removes reverse duplicates even for directed analyses.
    # Reject an ambiguous resource rather than silently erase ligand orientation.
    pairs=set(zip(measured.ligand,measured.receptor))
    reverse_policy=cfg.get('reverse_policy','reject')
    if reverse_policy not in ('reject','native_first'):raise ValueError('反向重复处理仅支持reject/native_first')
    if any((b,a) in pairs and a!=b for a,b in pairs):
        if reverse_policy!='native_first' or not cfg.get('reverse_policy_provenance'):raise ValueError('原生cell2cell会删除互为反向的资源行；需明确原生去重的分析范围与依据，不能静默选择一个方向')
    threshold=float(cfg.get('detection_fraction',.2));permutations=int(cfg.get('permutations',1000));minimum=int(cfg.get('min_cells',10));alpha=float(cfg.get('fdr',.05))
    if not 0<=threshold<1 or permutations<1000 or minimum<2 or not 0<alpha<1:raise ValueError('阈值需在[0,1)，正式置换至少1000次，每群至少2细胞，FDR需在(0,1)')
    measured_genes=sorted({g for a,b in pairs for v in (a,b) for g in subunits(v)})
    data=data[:,measured_genes].copy()
    out=new_output(output);write_json(out/'run_config.json',cfg);write_table(out/'resource_mapping.tsv',resource.to_dict('records'))
    signature=hashlib.sha256(json.dumps(dict(input=provenance,resource=digest(rp),version='0.9.0',threshold=threshold,permutations=permutations,min_cells=minimum,seed=cfg.get('seed',42),complex_separator=sep,samples=cfg.get('samples'),reverse_policy=reverse_policy),sort_keys=True).encode()).hexdigest()
    old=None;reuse=None
    if cfg.get('reuse_directory'):
        reuse=(cp.parent/cfg['reuse_directory']).resolve();old=json.loads((reuse/'run_metadata.json').read_text())
        if old['signature']!=signature:raise ValueError('原生复用的输入、资源或科学参数不一致')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='cell2cell',method_version='0.9.0',implementation='native',tables=[],
        provenance={**provenance,'parameters':cfg,'database_sha256':digest(rp),'molecule_identity_schema':SCHEMA,
        'upstream':'https://github.com/earmingol/cell2cell','license':'BSD-3-Clause',
        'semantics':'逐实际样本：原生nn_cell_fraction聚合、严格大于比例阈值的二元CCC；复合体取全部已测亚基比例最小值。Bray-Curtis-like CCI单列，不能当LR数量或概率。',
        'test':'原生细胞类型标签置换；P为加入观测值的经验分布percentileofscore双尾，保留并列值规则与零概率下界；原生非对称矩阵BH覆盖每样本全部LR×细胞对。不是供体条件检验。',
        'feature_scope':'仅移除LR资源未涉及的基因；非零细胞比例逐基因计算，不归一化或重新生成表达矩阵。',
        'direction':'默认拒绝互为反向行；明确native_first及依据时保留原生去重顺序，并记录被去掉的方向。原生结果按完整LR二元组回映，不拆分分子名字。'})
    allrows=[];objects={}
    ppi=measured.rename(columns={'ligand':'A','receptor':'B'})[['A','B']]
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique()),1):
        sub=data[data.obs[keys['sample']]==sample].copy();sizes=sub.obs[keys['cell_type']].value_counts()
        sub=sub[sub.obs[keys['cell_type']].isin(sizes[sizes>=minimum].index)].copy()
        types=sorted(sub.obs[keys['cell_type']].unique())
        if len(types)<2:raise ValueError('样本合格细胞类型不足2：'+sample)
        safe={v:f'CT{i:03d}' for i,v in enumerate(types)};back={v:k for k,v in safe.items()}
        meta=pd.DataFrame({'barcode':list(sub.obs_names),'cell_type':[safe[v] for v in sub.obs[keys['cell_type']]]})
        filename=f'native_{si}.pkl';path=out/filename
        if reuse:
            record=old['objects'].get(filename)
            if not record or record['sample']!=sample or digest(reuse/filename)!=record['sha256']:raise ValueError('原生缓存对象或样本摘要不一致')
            # Only read a locally generated object whose saved manifest and hash
            # have been verified. Do not accept arbitrary external pickle input.
            with (reuse/filename).open('rb') as stream:native=pickle.load(stream)
        else:
            if sub.n_obs*sub.n_vars*8>cfg.get('max_dense_bytes',2*1024**3):raise ValueError('原生DataFrame输入超过内存上限；需按实际样本划分或明确配置可用内存')
            # The fixed native aggregation API expects a DataFrame. This is an
            # in-memory orientation conversion of existing values, no normalization.
            native_expression=sub.to_df().T
            analysis=c2c.analysis.SingleCellInteractions(native_expression,ppi,meta,interaction_columns=('A','B'),communication_score='expression_thresholding',cci_score='bray_curtis',cci_type='directed',expression_threshold=threshold,aggregation_method='nn_cell_fraction',barcode_col='barcode',celltype_col='cell_type',complex_sep=sep,complex_agg_method='min',verbose=False)
            analysis.compute_pairwise_cci_scores(verbose=False)
            analysis.compute_pairwise_communication_scores(cci_type='directed',verbose=False)
            pvalues=analysis.permute_cell_labels(permutations=permutations,evaluation='communication',fdr_correction=False,random_state=cfg.get('seed',42),verbose=False)
            # Rectangular LR-by-cell-pair testing is not a symmetric adjacency test.
            qvalues=multitest.compute_fdrcorrection_asymmetric_matrix(pvalues,alpha=alpha)
            native=dict(analysis=analysis,p_values=pvalues,q_values=qvalues,metadata=sub.obs.copy(),cell_type_map=safe)
        with path.open('wb') as stream:pickle.dump(native,stream,protocol=pickle.HIGHEST_PROTOCOL)
        objects[filename]=dict(sample=str(sample),sha256=digest(path));write_json(out/'run_metadata.json',dict(signature=signature,objects=objects))
        analysis=native['analysis'];ccc=analysis.interaction_elements['communication_matrix'];cci=analysis.interaction_elements['cci_matrix'];pv=native['p_values'];qv=native['q_values']
        retained=set(ccc.index)
        if not retained<=pairs or not pv.index.equals(ccc.index) or not pv.columns.equals(ccc.columns):raise ValueError('原生LR身份或P矩阵轴不一致')
        if reverse_policy=='reject' and retained!=pairs:raise ValueError('原生执行意外丢失LR身份')
        write_table(out/f'native_direction_scope_{si}.tsv',[dict(ligand=a,receptor=b,retained=(a,b) in retained,reason='native_retained' if (a,b) in retained else 'native_reverse_duplicate_removed') for a,b in sorted(pairs)])
        ccc.to_csv(out/f'native_ccc_{si}.tsv',sep='\t');cci.to_csv(out/f'native_cci_{si}.tsv',sep='\t');analysis.aggregated_expression.to_csv(out/f'native_detection_fraction_{si}.tsv',sep='\t')
        for i,(ligand,receptor) in enumerate(ccc.index):
            for j,pair in enumerate(ccc.columns):
                a,b=pair.split(';');score=float(ccc.iloc[i,j]);p=float(pv.iloc[i,j]);q=float(qv.iloc[i,j]);tested=bool(np.isfinite([score,p,q]).all())
                allrows.append(dict(sample=str(sample),donor=str(sub.obs.iloc[0][keys['donor']]),condition=str(sub.obs.iloc[0][keys['condition']]),source=back[a],target=back[b],ligand=ligand,receptor=receptor,interaction=ligand+' -> '+receptor,ligand_identity=gene_identity(subunits(ligand)),receptor_identity=gene_identity(subunits(receptor)),score=score if tested else None,p_value=p if tested else None,q_value=q if tested else None,tested=tested,supported=bool(tested and score>0 and q<alpha)))
        rows=[dict(row=back[a],column=back[b],value=float(cci.loc[a,b])) for a in cci.index for b in cci.columns]
        add_table(bundle,out,f'cci_{si}','matrix',rows,'原生有向Bray-Curtis-like CCI=2ΣLR/(ΣL²+ΣR²)，二元端点来自检测比例阈值；分母零原生返回0，不是LR数量或P值',value_kind='native_score',axis_label='Native Bray-Curtis-like CCI',sample=str(sample),title=str(sample)+': overall interaction similarity')
    add_table(bundle,out,'lr_edges','lr_edges',allrows,'原生二元CCC，双端点检测比例均严格超过阈值才为1；支持还需原生双尾置换及非对称矩阵BH<阈值。零分、未支持与缺测分开保留',value_kind='count',additive=True,axis_label='Native binary CCC')
    bundle['provenance']['native_objects']=objects;write_json(out/'bundle.json',bundle)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();sys.exit(run(a.config,a.out))
