#!/usr/bin/env python3
"""整理研究对象与供体支持证据，保留原生分数，不创建机制总分或新P值。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median
from communication_contract import load_bundle,new_output,write_json,write_table

FOCUS_FIELDS=('source','target','ligand','receptor','pathway')
UNKNOWN={'unknown','unavailable','na','none',''}


def validate_focus(focus, rows):
    if not isinstance(focus,dict) or set(focus)-set(FOCUS_FIELDS):raise ValueError('focus只接受发送群、接收群、配体、受体、通路的实际标签')
    for key,values in focus.items():
        if not isinstance(values,list) or not values or not all(isinstance(v,str) and v for v in values):raise ValueError('研究对象须为非空标签列表')
        absent=set(values)-{r.get(key) for r in rows}
        if absent:raise ValueError(f'研究对象在当前结果表中没有记录: {key}={sorted(absent)}；不猜同义群或补造信号')


def edge_key(row):
    return tuple(row.get(k,'') for k in ('source','target','ligand','receptor','interaction'))


def summarize(rows, spec, focus=None):
    focus=focus or {};validate_focus(focus,rows)
    groups=defaultdict(list)
    for r in rows:groups[(r.get('condition','unspecified'),edge_key(r))].append(r)
    summaries=[]
    for (condition,key),values in groups.items():
        if len({v['sample'] for v in values})!=len(values):raise ValueError('同一条件/样本/细胞对/LR重复，不能重复计供体支持')
        tested=[r for r in values if r['tested'] and r['score'] is not None]
        known=defaultdict(list)
        for r in tested:
            donor=r.get('donor','').strip()
            if donor.casefold() not in UNKNOWN:known[donor].append(r)
        # Repeated technical samples never increase independent donor counts.
        # A donor is supported only if every eligible sample supports the edge.
        donor_supported=sum(all(r['supported'] for r in rs) for rs in known.values())
        donor_fraction=donor_supported/len(known) if known else None
        native=median([median([r['score'] for r in rs]) for rs in known.values()]) if known else median([r['score'] for r in tested]) if tested else None
        endpoint=None
        if spec.get('display_priority')=='minimum_endpoint_mean' and tested:
            if any(r.get(k) is None for r in tested for k in ('ligand_mean','receptor_mean')):raise ValueError('端点展示排序缺少实际均值')
            endpoint=median([median([min(r['ligand_mean'],r['receptor_mean']) for r in rs]) for rs in known.values()]) if known else median([min(r['ligand_mean'],r['receptor_mean']) for r in tested])
        row=dict(zip(('source','target','ligand','receptor','interaction'),key))
        row.update(condition=condition,n_candidate_samples=len(values),n_tested_samples=len(tested),n_supported_samples=sum(r['supported'] for r in tested),
                   n_eligible_donors=len(known),n_supported_donors=donor_supported,donor_support_fraction=donor_fraction,
                   median_native_score=native,median_display_endpoint=endpoint,statistical_unit='donor_descriptive' if known else 'sample_descriptive_donor_unavailable',
                   focus_match=all(any(r.get(k) in targets for r in values) for k,targets in focus.items()),
                   candidate_scope=spec.get('candidate_scope','declared_result_table'),native_direction=spec.get('direction','higher'))
        summaries.append(row)
    def rank_key(r):
        score=r['median_display_endpoint'] if spec.get('display_priority')=='minimum_endpoint_mean' else r['median_native_score'];score_key=float('inf') if score is None else score if spec.get('direction')=='lower' else -score
        # Rank within method/condition only. Do not compare score scales between methods.
        return (r['condition'],not r['focus_match'],-r['n_supported_donors'],-(r['donor_support_fraction'] or 0),-r['n_supported_samples'],score_key,edge_key(r))
    summaries.sort(key=rank_key)
    ranks=defaultdict(int)
    for r in summaries:ranks[r['condition']]+=1;r['display_rank_within_condition']=ranks[r['condition']]
    return summaries


def run(bundle_path,output,focus=None):
    bundle,tables=load_bundle(bundle_path);out=new_output(output);records=[]
    for spec,rows,_ in tables:
        if spec['type']!='lr_edges':continue
        summary=summarize(rows,spec,focus)
        if not summary:continue
        filename=spec['id']+'_evidence.tsv';write_table(out/filename,summary)
        records.append(dict(table=spec['id'],file=filename,rows=len(summary)))
    write_json(out/'prioritization.json',dict(method=bundle['method'],dataset=bundle['dataset'],focus=focus or {},tables=records,
        rule='逐方法/条件按研究对象、支持供体数、合格供体支持比例、支持样本数及原生中位分数逐项排序；无加权机制总分。一个供体多个合格样本须全部支持才计供体支持。未知供体不冒充独立重复。',
        limitations='描述性候选整理；缺测候选不补0。无条件检验时不宣称条件特异；不替代配对/协变量模型、接收端响应和空间证据、留一供体重跑或外部验证。'))
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);p.add_argument('--out',required=True);p.add_argument('--focus-json');a=p.parse_args()
    run(a.bundle,a.out,json.loads(Path(a.focus_json).read_text()) if a.focus_json else None)
