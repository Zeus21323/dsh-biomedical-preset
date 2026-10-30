#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""同一原生结果包的供体条件比较；完整候选检验、供体点及删一供体敏感性。"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
from communication_contract import load_bundle, new_output, add_table, write_json, write_table, digest
from compare_communication import compare_candidates


def prepare_samples(bundle, tables, cfg):
    if cfg.get('statistical_unit') != 'donor' or not cfg.get('design_provenance'):
        raise ValueError('须明确供体统计单位及实际设计来源，不能把细胞/池化对象当重复')
    if cfg.get('covariates'):
        raise ValueError('置换比较不支持协变量；使用原生适用模型，不能静默忽略')
    matching=[(s,r) for s,r,_ in tables if s['id']==cfg.get('table','lr_edges')]
    if len(matching)!=1 or matching[0][0]['type'] not in ('lr_edges','metabolite_edges'):
        raise ValueError('指定唯一LR/代谢物候选表')
    spec,rows=matching[0]
    provenance=bundle['provenance']
    database=provenance.get('database_sha256')
    if not database or not provenance.get('parameters'):
        raise ValueError('原生推断缺少数据库摘要或参数，无法核验跨样本可比性')
    database=json.dumps(database,sort_keys=True) if isinstance(database,dict) else database
    # One bundle from one native run fixes method/resource/settings for every sample.
    # Ranks may be compared as ranks, with explicit orientation, never as probabilities.
    if spec.get('value_kind')=='rank' and spec.get('direction')!='lower':
        raise ValueError('当前排名比较仅支持[0,1]且越低越优的原生排名')
    groups=defaultdict(list);metadata={}
    for r in rows:
        if not r.get('donor') or not r.get('condition'):
            raise ValueError('候选表缺少逐样本实际 donor/condition')
        identity=(r['donor'],r['condition'])
        if r['sample'] in metadata and metadata[r['sample']]!=identity:
            raise ValueError('样本的供体或条件不唯一')
        metadata[r['sample']]=identity
        score=r['score']
        if spec.get('value_kind')=='rank' and score is not None:
            if not 0<=score<=1:raise ValueError('排名值不在[0,1]，不猜测归一化')
            score=1-score
        ligand=r.get('ligand',r.get('metabolite'));receptor=r.get('receptor',r.get('sensor'))
        groups[r['sample']].append(dict(r,ligand=ligand,receptor=receptor,score=score,
            interaction=r.get('interaction') or json.dumps([ligand,receptor],ensure_ascii=False),pathway=r.get('pathway','unannotated')))
    signature=json.dumps(dict(method=bundle['method'],version=bundle['method_version'],database=database,
                              parameters=provenance['parameters']),sort_keys=True)
    samples=[]
    for sample,rs in sorted(groups.items()):
        donor,condition=metadata[sample]
        samples.append(dict(candidates=rs,provenance=dict(config=dict(sample=sample,donor=donor,condition=condition),
            statistical_unit='donor',comparison_signature=signature,comparison_parameters=provenance['parameters'],
            database_sha256=database,method_version=bundle['method_version'])))
    return samples,spec


def run(config,output):
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    bundle_path=(config.parent/cfg['bundle']).resolve();native,tables=load_bundle(bundle_path)
    samples,spec=prepare_samples(native,tables,cfg)
    results,observations=compare_candidates(samples,cfg,allow_signed_scores=spec.get('value_kind')=='native_score')
    out=new_output(output);write_json(out/'run_config.json',cfg)
    write_table(out/'all_condition_candidates.tsv',results)
    outbundle=dict(schema_version=2,dataset=native['dataset'],method=native['method']+' donor contrasts',method_version='1',
        implementation='donor_permutation_postprocessing',provenance=dict(input_bundle_sha256=digest(bundle_path),
        native_method=native['method'],native_version=native['method_version'],parameters=cfg,
        statistical_unit='donor',design_provenance=cfg['design_provenance']),tables=[])
    names={}
    for r in results:
        key=(r['source'],r['target'],r['interaction'])
        names[key]=f"{r['source']} → {r['target']} | {r['ligand']} — {r['receptor']}"
        if r['interaction']!=json.dumps([r['ligand'],r['receptor']],ensure_ascii=False):names[key]+=' ['+r['interaction']+']'
    axis='Difference in (1 − native rank)' if spec.get('value_kind')=='rank' else 'Difference in native score'
    summary=[dict(feature=names[(r['source'],r['target'],r['interaction'])],value=r['effect'],p_value=r['p_value'],q_value=r['fdr'],
                  n_reference=r['n_reference'],n_comparison=r['n_comparison']) for r in results]
    add_table(outbundle,out,'condition_effects','effect_summary',summary,
        '供体均值差，比较条件减参考条件；按可检验供体数过滤后对完整候选进行双侧置换检验及BH；无协变量调整',
        contrast=cfg['conditions'][1]+' − '+cfg['conditions'][0],statistical_unit='donor',
        test_definition='paired donor sign permutation' if cfg.get('paired') else 'unpaired donor label permutation',
        alpha=cfg.get('fdr',.05),axis_label=axis)
    selected=sorted((r for r in results if r['effect'] is not None),key=lambda r:(r['fdr'] if r['fdr'] is not None else 2,-abs(r['effect'])))[:int(cfg.get('top_lr',12))]
    donors=[];sensitivity=[]
    for r in selected:
        key=(r['source'],r['target'],r['interaction']);obs=observations[key];feature=names[key]
        available=[{d for d,c in obs if c==condition} for condition in cfg['conditions']]
        complete=available[0]&available[1] if cfg.get('paired') else available[0]|available[1]
        for (donor,condition),(value,supported) in sorted(obs.items()):
            if cfg.get('paired') and donor not in complete:continue
            donors.append(dict(sample=next(s['provenance']['config']['sample'] for s in samples if s['provenance']['config']['donor']==donor and s['provenance']['config']['condition']==condition),
                               donor=donor,condition=condition,feature=feature,value=value))
        for omitted in sorted(complete):
            values=[[v[0] for (d,c),v in obs.items() if c==condition and d!=omitted and (not cfg.get('paired') or d in complete)] for condition in cfg['conditions']]
            effect=float(np.mean(values[1])-np.mean(values[0])) if all(values) else None
            sensitivity.append(dict(row=feature,column=omitted,value=effect))
    if donors:
        add_table(outbundle,out,'candidate_donors','effects',donors,'按完整检验后的q值和绝对效应选前12候选；每点为供体；配对比较仅显示完整供体对',axis_label='1 − native rank' if spec.get('value_kind')=='rank' else 'Native score')
    if sensitivity:
        add_table(outbundle,out,'leave_one_donor_out','matrix',sensitivity,
            '逐次删除一个供体后重新计算候选均值差；配对设计同时删除两条件；仅效应敏感性，未重做筛选或BH，不是独立验证',axis_label=axis,title='Leave-one-donor-out effects (column: omitted donor)')
    write_json(out/'selection.json',dict(rule='完整候选BH后选择显示；候选内删一供体，不代表选择稳定性',selected=selected))
    write_json(out/'bundle.json',outbundle)
    from render_result_bundle import run as render
    return render(out/'bundle.json',out/'figures')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
