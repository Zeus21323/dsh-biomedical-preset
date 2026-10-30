#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "scipy==1.16.1", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""有定义的通讯候选/响应基因集合的过度代表分析，不将全基因组自动当背景。"""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from collections import defaultdict
from communication_contract import new_output,add_table,write_json,digest
from compare_communication import bh_adjust


def enrichment(groups,background,gene_sets,min_size=10,max_size=500):
    from scipy.stats import hypergeom
    if not background:raise ValueError('背景为空')
    sets={term:set(genes)&background for term,genes in gene_sets.items()}
    sets={term:genes for term,genes in sets.items() if min_size<=len(genes)<=max_size}
    if not sets:raise ValueError('没有满足事先声明大小范围的背景内基因集')
    rows=[]
    for group,genes in sorted(groups.items()):
        if not genes or not genes<=background:raise ValueError('候选必须是背景的非空子集；不能静默删除背景外基因')
        for term,members in sorted(sets.items()):
            overlap=genes&members
            p=float(hypergeom.sf(len(overlap)-1,len(background),len(members),len(genes)))
            rows.append(dict(term=term,group=group,value=(len(overlap)/len(genes))/(len(members)/len(background)),
                p_value=p,q_value=None,overlap=len(overlap),set_size=len(members),background_size=len(background),
                selected_size=len(genes),overlap_genes=';'.join(sorted(overlap))))
    for row,q in zip(rows,bh_adjust([r['p_value'] for r in rows])):row['q_value']=float(q)
    return rows


def run(config,output):
    path=Path(config).resolve();cfg=json.loads(path.read_text())
    for key in ('dataset','selected_genes','background','gmt','species','gene_set_version','selection_provenance','background_provenance'):
        if not cfg.get(key):raise ValueError('缺少富集输入及来源: '+key)
    paths={k:(path.parent/cfg[k]).resolve() for k in ('selected_genes','background','gmt')}
    groups=defaultdict(set)
    with paths['selected_genes'].open() as stream:
        reader=csv.DictReader(stream,delimiter='\t')
        if not {'group','gene'}<=set(reader.fieldnames or []):raise ValueError('selected_genes必须有group/gene列')
        for row in reader:
            if not row['group'].strip() or not row['gene'].strip():raise ValueError('group/gene不能空')
            groups[row['group']].add(row['gene'])
    background={g.strip() for g in paths['background'].read_text().splitlines() if g.strip()}
    sets={}
    for line in paths['gmt'].read_text().splitlines():
        if not line.strip():continue
        fields=line.split('\t')
        if len(fields)<3 or not fields[0] or fields[0] in sets:raise ValueError('GMT条目不足或重名')
        sets[fields[0]]=set(fields[2:])
    if not groups:raise ValueError('没有候选分组')
    minimum=int(cfg.get('min_size',10));maximum=int(cfg.get('max_size',500))
    if not 1<=minimum<=maximum:raise ValueError('基因集大小范围无效')
    rows=enrichment(groups,background,sets,minimum,maximum)
    out=new_output(output)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='Communication gene-set overrepresentation',method_version='1',
        implementation='hypergeometric_BH',provenance=dict(parameters=cfg,source_sha256={k:digest(p) for k,p in paths.items()}),tables=[])
    add_table(bundle,out,'response_enrichment','enrichment',rows,
        '超几何右尾检验；fold enrichment为观测候选比例/背景比例；BH覆盖所有组×合格基因集，含零重叠。背景内集合大小过滤先于检验。',
        axis_label='Fold enrichment',background_definition=cfg['background_provenance'],
        gene_set_provenance=dict(species=cfg['species'],version=cfg['gene_set_version'],sha256=digest(paths['gmt'])))
    write_json(out/'bundle.json',bundle)
    from render_result_bundle import run as render
    return render(out/'bundle.json',out/'figures')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))
