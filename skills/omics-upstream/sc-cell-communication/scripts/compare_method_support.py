#!/usr/bin/env python3
"""Compare observed method support on common tested candidates without mixing scores."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np
from scipy.stats import spearmanr,rankdata
from communication_contract import load_bundle,new_output,write_json,add_table,digest
from communication_identities import SCHEMA


def align_candidates(bundle,tables,table_id=None):
    if bundle['provenance'].get('molecule_identity_schema')!=SCHEMA:
        raise ValueError('缺少经资源核验的分子身份契约；需用更新的原生适配器重新导出，不能直接匹配显示标签')
    lr_tables=[t for t in tables if t[0]['type']=='lr_edges']
    if table_id is not None:
        lr_tables=[t for t in lr_tables if t[0]['id']==table_id]
        if len(lr_tables)!=1:raise ValueError('指定的LR评分表不存在或不唯一')
    elif len(lr_tables)>1:
        raise ValueError('同一方法有多个LR评分表，必须显式指定table_id，不能混合表达与特异性权重')
    candidates={};excluded=[]
    for spec,rs,_ in lr_tables:
        if spec['type']!='lr_edges':continue
        for r in rs:
            if not r.get('ligand_identity') or not r.get('receptor_identity'):
                raise ValueError('分子身份列不完整')
            key=tuple(r[k] for k in ['sample','source','target','ligand_identity','receptor_identity'])
            candidates.setdefault(key,[]).append((spec,r))
    rows={}
    for key,items in candidates.items():
        if len(items)>1:
            excluded.append(dict(candidate=list(key),native_interactions=[r.get('interaction') for _,r in items],
                reason='multiple native interactions map to one molecular identity; no arbitrary aggregation'))
            continue
        spec,r=items[0]
        if r['tested'] and r['score'] is not None:
            rows[key]=dict(supported=r['supported'],rank_score=(-r['score'] if spec.get('direction')=='lower' else r['score']))
    return rows,excluded


def comparison(tables):
    """Return coverage, support Jaccard, rank correlation; no missing=zero imputation."""
    coverage=[];jaccard=[];correlation=[];details=[]
    for a in tables:
        for b in tables:
            x,y=tables[a],tables[b]
            common=set(x)&set(y)
            sx={k for k in common if x[k]['supported']};sy={k for k in common if y[k]['supported']}
            union=sx|sy
            j=len(sx&sy)/len(union) if union else None
            scores=[(x[k]['rank_score'],y[k]['rank_score']) for k in sorted(common)]
            rho=None
            if len(scores)>=3:
                values=np.array(scores)
                if np.ptp(values[:,0])>0 and np.ptp(values[:,1])>0:
                    rho=float(spearmanr(values[:,0],values[:,1]).statistic)
            coverage.append(dict(row=a,column=b,value=len(common)))
            jaccard.append(dict(row=a,column=b,value=j))
            correlation.append(dict(row=a,column=b,value=rho))
            details.append(dict(method_a=a,method_b=b,common_tested=len(common),supported_a=len(sx),supported_b=len(sy),
                supported_intersection=len(sx&sy),supported_union=len(union),jaccard=j,spearman=rho))
    return coverage,jaccard,correlation,details


def run(config,output):
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    if len(cfg.get('bundles',[]))<2:raise ValueError('至少两个实际方法结果包')
    methods={};input_hashes=set();sources=[];datasets=set();alignment_exclusions={};input_layers=set()
    for value in cfg['bundles']:
        table_id=value.get('table_id') if isinstance(value,dict) else None
        path=(config.parent/(value['bundle'] if isinstance(value,dict) else value)).resolve();bundle,tables=load_bundle(path)
        label=bundle['method'];datasets.add(bundle['dataset'])
        if label in methods:raise ValueError('方法名称重复；敏感性实验应另行明确参数变化，不能冒充方法比较')
        h=bundle['provenance'].get('input_sha256')
        if not h:raise ValueError('缺少实际输入摘要，无法确认比较同一数据')
        input_hashes.add(h);sources.append(dict(path=str(path),sha256=digest(path),table_id=table_id,provenance=bundle['provenance']))
        input_layers.add(json.dumps({k:bundle['provenance'].get(k) for k in ('layer','expression_scale','species','sample_columns')},sort_keys=True))
        rows,excluded=align_candidates(bundle,tables,table_id);alignment_exclusions[label]=excluded
        if not rows:raise ValueError('没有可对齐的已检验LR候选')
        methods[label]=rows
    if len(input_hashes)!=1 or len(datasets)!=1 or len(input_layers)!=1:raise ValueError('输入数据或表达层/物种/细胞分组不一致，不能解释为方法一致性')
    # Each biological sample is shown separately; donor multiplicity does not weight
    # one pooled score or manufacture a significance test.
    samples=sorted({k[0] for rows in methods.values() for k in rows})
    out=new_output(output)
    result=dict(schema_version=2,dataset=next(iter(datasets)),method='Method evidence comparison',method_version='1',implementation='descriptive',
        provenance=dict(parameters=cfg,sources=sources,input_sha256=next(iter(input_hashes)),statistical_unit='sample; descriptive comparison, no inferential P'),tables=[])
    details=[]
    for si,sample in enumerate(samples):
        subset={name:{k:r for k,r in rows.items() if k[0]==sample} for name,rows in methods.items()}
        c,j,r,d=comparison(subset);details.extend(dict(row,sample=sample) for row in d)
        for name,rows,label,definition in [('coverage',c,'Common tested candidates','共同可检验候选数量，不在共同支持集中补零'),
            ('support',j,'Support Jaccard','各方法自身支持规则下的集合Jaccard；双方均无支持时为缺失，不当作完全一致'),
            ('ranking',r,'Spearman rank correlation','同一可检验集合的分数秩相关；排序方向统一，原生分数不相加，常数或不足3项时缺失')]:
            add_table(result,out,f'{name}_{si+1}','matrix',rows,f'{sample}: {definition}',axis_label=label,value_kind='descriptive',figure_role='method_agreement')
    write_json(out/'alignment_exclusions.json',alignment_exclusions)
    write_json(out/'comparison_details.json',details);write_json(out/'bundle.json',result)
    from render_result_bundle import run as render
    return render(out/'bundle.json',out/'figures')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
