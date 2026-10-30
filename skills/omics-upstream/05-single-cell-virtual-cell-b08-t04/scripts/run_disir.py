#!/usr/bin/env python3
"""原生DiSiR亚基通讯推断；保留有放回抽样与逐亚基支持语义。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,csv,hashlib,importlib,json,pickle
from pathlib import Path
from communication_contract import add_table,digest,new_output,write_json,write_table
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,gene_identity


def validate_resource(resource):
    if not isinstance(resource,list) or not resource:raise ValueError('资源需为非空相互作用列表')
    ids=set()
    for group in resource:
        if not isinstance(group,dict) or not group.get('id') or group['id'] in ids:raise ValueError('相互作用id必须唯一非空')
        ids.add(group['id']);edges=group.get('subunit_edges')
        if not isinstance(edges,list) or not edges:raise ValueError('每个复合体需显式亚基配对subunit_edges')
        if any(not isinstance(e,list) or len(e)!=2 or any(not isinstance(g,str) or not g.strip() or ' | ' in g or ',' in g for g in e) for e in edges):raise ValueError('每条亚基边需两个明确基因名，不得含原生分隔符')
        if len({tuple(e) for e in edges})!=len(edges):raise ValueError('重复亚基边会改变原生均值权重')
    return resource


def run(config,output):
    import numpy as np
    import pandas as pd
    require_version('disir-package','0.0.1');ds=importlib.import_module('disir_package.disir_package')
    if digest(ds.__file__)!='6cbc6cd6553e60401eee55b427a062d4fdee9230809778c454162540c959d04e':raise ValueError('DiSiR评分源码与核验commit不一致')
    cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    for k in ('dataset','research_question','resource_file','resource_version','resource_provenance','resource_species'):
        if not cfg.get(k):raise ValueError('缺少：'+k)
    data,keys,provenance=read_expression(cfg,cp.parent)
    if cfg['expression_scale']!='counts':raise ValueError('DiSiR需要真实整数counts，原生自身使用log2(counts+1)，不接受已经log归一化矩阵')
    if cfg['species']!=cfg['resource_species']:raise ValueError('资源物种不匹配')
    rp=(cp.parent/cfg['resource_file']).resolve();resource=validate_resource(json.loads(rp.read_text()))
    missing={g['id']:sorted({v for e in g['subunit_edges'] for v in e}-set(data.var_names)) for g in resource}
    if any(missing.values()):raise ValueError('缺失完整亚基，不得取可见部分继续：'+str(missing))
    iterations=int(cfg.get('iterations',1000));tf=float(cfg.get('threshold_fraction',0));te=float(cfg.get('threshold_expression',0));tp=float(cfg.get('threshold_pvalue',.05));minimum=int(cfg.get('min_cells',10))
    if iterations<1000 or not 0<=tf<1 or not 0<=te<1 or not 0<tp<1 or minimum<2:raise ValueError('原生阈值无效或正式模拟不足1000次')
    out=new_output(output);write_json(out/'run_config.json',cfg);write_json(out/'interaction_resource.json',resource)
    # Use the native parser with the exact declared subunit pairs, preserving order.
    rp_native=out/'native_subunit_interactions.csv'
    with rp_native.open('w',newline='') as f:csv.writer(f).writerows([[' | '.join(e) for e in g['subunit_edges']] for g in resource])
    genes=sorted({v for g in resource for e in g['subunit_edges'] for v in e});data=data[:,genes].copy()
    gp=out/'native_gene_names.csv'
    with gp.open('w',newline='') as f:csv.writer(f).writerows([[g] for g in genes])
    signature=hashlib.sha256(json.dumps(dict(input=provenance,resource=digest(rp),source=digest(ds.__file__),iterations=iterations,tf=tf,te=te,tp=tp,minimum=minimum,samples=cfg.get('samples')),sort_keys=True).encode()).hexdigest()
    reuse=None;old=None;objects={}
    if cfg.get('reuse_directory'):
        reuse=(cp.parent/cfg['reuse_directory']).resolve();old=json.loads((reuse/'run_metadata.json').read_text())
        if old['signature']!=signature:raise ValueError('原生复用输入、资源或参数不符')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='DiSiR',method_version='0.0.1',implementation='native',tables=[],provenance={**provenance,'parameters':cfg,'molecule_identity_schema':SCHEMA,'resource_sha256':digest(rp),'software_commit':'3998f7a7fcb2fd3babc9c54da8afd74bf8f608f0','license':'GPL-3.0-or-later',
        'native_test':'原生np.random.choice为每个细胞群独立有放回抽样，保持各群细胞数；并非无放回标签置换。亚基P为null严格大于观测的b/B，未过滤正分外原生P=1。',
        'native_support':'指定复合体的全部亚基边P均<=阈值才支持；原生没有多重检验校正或联合复合体P，不能把最大/均值亚基P当联合P。',
        'score':'每亚基边为发送/接收群平均log2(counts+1)的乘积；完整复合体强度为声明的全部亚基边乘积的算术平均。固定原生seed=0按资源顺序运行。',
        'scope':'仅为声明的亚基机制假设计算；不是全数据库筛查，不表示实测复合体装配或因果激活。'})
    allrows=[]
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique()),1):
        sub=data[data.obs[keys['sample']]==sample].copy();sizes=sub.obs[keys['cell_type']].value_counts();sub=sub[sub.obs[keys['cell_type']].isin(sizes[sizes>=minimum].index)].copy()
        labels=sorted(sub.obs[keys['cell_type']].unique());safe={v:f'CT{i:03d}' for i,v in enumerate(labels)};back={v:k for k,v in safe.items()}
        if len(labels)<2:raise ValueError('样本内合格细胞群不足2')
        if max(len({v for e in g['subunit_edges'] for v in e})**2*len(labels)**2*iterations*8 for g in resource)>cfg.get('max_null_bytes',2*1024**3):raise ValueError('原生null数组超出内存预算，不静默减少迭代')
        fn=f'native_{si}.pkl'
        if reuse:
            rec=old['objects'].get(fn)
            if not rec or rec['sample']!=sample or rec['sha256']!=digest(reuse/fn):raise ValueError('原生缓存对象或样本摘要不符')
            with (reuse/fn).open('rb') as f:native=pickle.load(f)
        else:
            np.random.seed(0);arr=sub.to_df().to_numpy().T
            expression,gene_names,lr_info,subunit_info=ds.gene_expressions_with_selected_genes(arr,str(gp),str(rp_native))
            native=dict(groups=[],metadata=sub.obs.copy(),cell_type_map=safe)
            for gi in lr_info:
                gs=lr_info[gi];expr=expression[[gene_names.index(g) for g in gs],:];selected=subunit_info[gi]
                av,num,fr,cts,ncells,ns,es=ds.calculate_celltype_average_expressions(expr,gs,[safe[v] for v in sub.obs[keys['cell_type']]])
                values,gname,cname=ds.calculate_LR_interactions_matrix_prefiltered(av,gs,cts,ns,es,tf,te)
                p,gn,cn,w,table=ds.calculate_LR_interactions_pvalues(values,gname,cname,expr,ncells,gs,cts,iterations)
                nodes,links=ds.build_interactions_graph_subunit(p,gn,cts,w,selected,tp)
                heat=ds.calculate_celltype_interactions_heatmap(links,cts,av,selected)
                native['groups'].append(dict(id=resource[gi]['id'],selected=selected,genes=gs,average=av,fraction=fr,p_values=p,gene_pairs=gn,cell_pairs=cn,filtered_weights=w,table=table,nodes=nodes,links=links,heatmaps=heat))
        with (out/fn).open('wb') as f:pickle.dump(native,f,protocol=pickle.HIGHEST_PROTOCOL)
        objects[fn]=dict(sample=str(sample),sha256=digest(out/fn));write_json(out/'run_metadata.json',dict(signature=signature,objects=objects))
        for gi,g in enumerate(native['groups'],1):
            group=resource[gi-1];ls=sorted({e[0] for e in group['subunit_edges']});rs=sorted({e[1] for e in group['subunit_edges']});cts=list(g['average'].columns)
            g['table'].to_csv(out/f'native_subunit_candidates_{si}_{gi}.tsv',sep='\t',index=False)
            selected_indices=[g['gene_pairs'][0].tolist().index(e) for e in g['selected']]
            p=g['p_values'].iloc[selected_indices].to_numpy();w=g['filtered_weights'].iloc[selected_indices].to_numpy()
            graph={(int(row[0])-1,int(row[1])-len(cts)-1) for row in g['links'].itertuples(index=False,name=None)}
            prows=[]
            for i,a in enumerate(cts):
                for j,b in enumerate(cts):
                    ci=i*len(cts)+j;tested=bool(np.all(w[:,ci]>0));score=float(g['heatmaps']['heatmap_all_interactions'].loc[a,b])
                    allrows.append(dict(sample=str(sample),donor=str(sub.obs.iloc[0][keys['donor']]),condition=str(sub.obs.iloc[0][keys['condition']]),source=back[a],target=back[b],ligand='&'.join(ls),receptor='&'.join(rs),ligand_identity=gene_identity(ls),receptor_identity=gene_identity(rs),interaction=group['id'],score=score if tested else None,tested=tested,supported=bool(tested and (i,j) in graph)))
                    for k,e in enumerate(g['selected']):prows.append(dict(row=e,column=back[a]+' → '+back[b],value=float(p[k,ci]) if w[k,ci]>0 else None))
            add_table(bundle,out,f'subunit_p_{si}_{gi}','matrix',prows,'原生各指定亚基边独立抽样P，未通过表达预过滤为NA；无多重校正，不作为联合复合体P',value_kind='p_value',axis_label='Native unadjusted subunit P',direction='lower',title=str(sample)+': '+group['id'])
    add_table(bundle,out,'lr_edges','lr_edges',allrows,'原生完整亚基组平均乘积；全部亚基边通过表达预过滤才可评估，全部原生未校正P<=阈值才支持。没有联合LR P或FDR；未评估不补0',value_kind='nonnegative_strength',additive=True,axis_label='Native mean subunit product')
    bundle['provenance']['native_objects']=objects;write_json(out/'bundle.json',bundle);return 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();sys.exit(run(a.config,a.out))
