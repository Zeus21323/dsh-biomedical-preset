#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10,<3.11"
# dependencies = ["scConnect @ git+https://github.com/JonETJakobsson/scConnect.git@546053d7a8a18762b90f4a5e4ca2a76be7a2b459", "numpy==1.26.4", "pandas==1.5.3", "scanpy==1.9.8", "anndata==0.9.2", "networkx==2.8.8", "dash==2.18.2", "setuptools==80.9.0"]
# ///
"""Native scConnect peptide/neurotransmitter inference; component tests stay separate."""
import argparse
import ast
import json
from pathlib import Path
import random
import pickle
import sys
sys.dont_write_bytecode = True
from communication_contract import new_output, write_json, add_table, digest
from communication_inputs import read_expression, require_version


def genes(value):
    if not isinstance(value, str):
        return []
    result = ast.literal_eval(value)
    if not isinstance(result, list) or not all(isinstance(x, str) for x in result):
        raise ValueError('原生资源基因字段必须为字符串列表')
    return result


def run(config, output):
    import anndata as ad
    import numpy as np
    import pandas as pd
    import scConnect as cn
    config = Path(config).resolve(); cfg = json.loads(config.read_text())
    version = require_version('scConnect', '1.0.4')
    data, keys, provenance = read_expression(cfg, config.parent)
    permutations = cfg.get('n_perms', 1000)
    if not isinstance(permutations, int) or permutations < 100:
        raise ValueError('至少100次原生置换，并报告分辨率')
    if cn.database.version != '2020-5':
        raise ValueError('需要已核验的 Guide to Pharmacology 2020-5 原生资源')
    organism = {'human':'hsapiens', 'mouse':'mmusculus'}[cfg['species']]
    resource = Path(cn.__file__).parent/'data/Gene_annotation/2020-5'
    files = [resource/organism/'ligands.csv', resource/organism/'receptors.csv', resource/'interactions.csv']
    ligands = pd.read_csv(files[0]).set_index('ligand')
    receptors = pd.read_csv(files[1]).set_index('receptor')
    fields = ('preprogene', 'synthesis', 'transport', 'reuptake', 'excluded')
    ligand_genes = {name:sorted({g for f in fields for g in genes(row[f])}) for name,row in ligands.iterrows()}
    receptor_genes = {name:genes(row['gene']) for name,row in receptors.iterrows()}
    measured = set(data.var_names)
    coverage = {kind:{name:dict(genes=gs, missing=sorted(set(gs)-measured), complete=bool(gs) and set(gs)<=measured)
                      for name,gs in mapping.items()} for kind,mapping in [('ligand',ligand_genes),('receptor',receptor_genes)]}
    selected_genes = sorted(measured & {g for mapping in (ligand_genes,receptor_genes) for gs in mapping.values() for g in gs})
    if not selected_genes:
        raise ValueError('输入与原生资源无基因交集')
    out = new_output(output); write_json(out/'run_config.json',cfg); write_json(out/'gene_coverage.json',coverage)
    bundle = dict(schema_version=2,dataset=cfg['dataset'],method='scConnect',method_version=version,implementation='native',
        provenance={**provenance,'parameters':cfg,'database_version':'GtoPdb 2020-5',
                    'database_sha256':{str(p.relative_to(resource)):digest(p) for p in files},
                    'evidence':'原生肽/递质合成、转运、再摄取及排除基因表达代理；不是实测递质或突触',
                    'support_rule':'双方原生component BH q<alpha且原生置换方差非零、资源列出的所有代理基因已测量；不是LR联合FDR',
                    'empirical_tail':'原生严格大于 observed，保留其并列值规则；零方差者不作支持证据'},tables=[])
    rows = []
    for si,sample in enumerate(sorted(data.obs[keys['sample']].unique()),1):
        subset = data[data.obs[keys['sample']]==sample,selected_genes].copy()
        counts = subset.obs[keys['cell_type']].value_counts()
        subset = subset[subset.obs[keys['cell_type']].isin(counts[counts>=cfg.get('min_cells',10)].index)].copy()
        if subset.obs[keys['cell_type']].nunique()<2:
            raise ValueError('合格细胞群少于2')
        # Only metadata and declared expression enter native inference; no historical uns results.
        subset = ad.AnnData(X=subset.X.copy(),obs=subset.obs.copy(),var=subset.var.copy())
        random.seed(cfg.get('seed',1)); np.random.seed(cfg.get('seed',1))
        subset, ligand_values, receptor_values = cn.connect.specificity(subset,n=permutations,groupby=keys['cell_type'],organism=organism,
            transformation='log1p' if cfg['expression_scale']=='log_normalized' else None,
            emperical=True,merge_dist=False,return_values=True)
        ligand_values.to_csv(out/f'native_ligand_permutations_{si}.tsv',sep='\t')
        receptor_values.to_csv(out/f'native_receptor_permutations_{si}.tsv',sep='\t')
        ligand_sd = cn.connect._std_df(ligand_values)
        receptor_sd = cn.connect._std_df(receptor_values)
        native = cn.connect.interactions(subset,subset,self_reference=True,organism=organism,corr_pval=True)
        # Native molecular names can contain '/', which HDF5 interprets as a
        # hierarchy separator. Preserve the untouched native object in pickle;
        # all its statistical matrices are also exported as readable TSV below.
        with (out/f'scconnect_{si}.pickle').open('wb') as stream:
            pickle.dump(subset,stream,protocol=pickle.HIGHEST_PROTOCOL)
        pd.DataFrame([dict(source=a,target=b,**r) for a,b,r in native]).to_csv(out/f'native_edges_{si}.tsv',sep='\t',index=False)
        # Native statistics and permutation distributions are preserved separately from display masks.
        for key,value in subset.uns.items():
            if isinstance(value,dict) and key != 'specificity_setting':
                try: pd.DataFrame(value).to_csv(out/f'native_{key}_{si}.tsv',sep='\t')
                except ValueError: write_json(out/f'native_{key}_{si}.json',value)
        for source,target,r in native:
            ligand,receptor = r['ligand'],r['receptor']
            complete = coverage['ligand'][ligand]['complete'] and coverage['receptor'][receptor]['complete']
            lstd = float(ligand_sd.loc[ligand,source]); rstd = float(receptor_sd.loc[receptor,target])
            eligible = complete and lstd>0 and rstd>0
            lq,rq = r['ligand_pval'],r['receptor_pval']
            rows.append(dict(sample=str(sample),donor=str(subset.obs.iloc[0][keys['donor']]),condition=str(subset.obs.iloc[0][keys['condition']]),
                source=source,target=target,ligand=ligand,receptor=receptor,interaction=r['interaction'],ligand_type=r['ligandtype'],
                score=r['score'] if complete else None,native_score=r['score'],tested=eligible,
                ligand_q_value=lq,receptor_q_value=rq,native_specificity=r['specificity'],native_importance=r['importance'],
                supported=eligible and lq<cfg.get('alpha',.05) and rq<cfg.get('alpha',.05),
                coverage_complete=complete,ligand_permutation_sd=lstd,receptor_permutation_sd=rstd))
    if not rows: raise ValueError('原生方法未返回正分数边，保留原始统计，不生成虚构网络')
    add_table(bundle,out,'neurotransmitter_peptide_edges','lr_edges',rows,
        'scConnect原生两端代理分数几何均值；支持要求两端分别通过原生BH筛选，不提供虚构的LR联合P/FDR；分子名保留GtoPdb身份',
        value_kind='nonnegative_strength',additive=True,axis_label='scConnect score',direction='higher',candidate_scope='native_positive_only')
    write_json(out/'bundle.json',bundle)
    import importlib.metadata
    write_json(out/'environment.json',{p:importlib.metadata.version(p) for p in ('scConnect','numpy','pandas','anndata','scanpy','scipy','setuptools')})
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();sys.exit(run(args.config,args.out))
