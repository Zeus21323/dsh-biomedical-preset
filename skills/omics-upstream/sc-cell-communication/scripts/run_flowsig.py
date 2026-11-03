#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["flowsig==0.5.5", "numpy==2.1.3", "anndata==0.13.3.post0"]
# ///
"""Native FlowSig construction and bootstrap graph learning for two conditions.

Use a separate environment. macOS XGBoost requires an available OpenMP runtime.
This exports model association frequencies, never donor-level causal P values.
"""
import argparse
import json
from pathlib import Path
import random
import sys
import warnings
sys.dont_write_bytecode=True
from communication_contract import new_output,write_json,add_table,digest
from communication_inputs import read_expression,require_version


def run(config,output):
    import numpy as np
    import pandas as pd
    import anndata as ad
    import flowsig as fs
    # Upstream import suppresses all warnings globally. Preserve actual warnings
    # in the execution log instead of inheriting that global suppression.
    warnings.simplefilter('default')
    cfgpath=Path(config).resolve();cfg=json.loads(cfgpath.read_text())
    version=require_version('flowsig','0.5.5')
    data,keys,provenance=read_expression(cfg,cfgpath.parent)
    if cfg['expression_scale']!='log_normalized':raise ValueError('FlowSig v1 flow construction requires explicit log_normalized expression')
    conditions=sorted(data.obs[keys['condition']].unique())
    if len(conditions)!=2 or cfg.get('control') not in conditions:raise ValueError('此分支需要恰好两个真实条件及明确 control，避免原生 rest 对比冒充指定对照')
    if not cfg.get('upstream_communication_provenance'):raise ValueError('缺少实际 CellChat 上游推断来源与版本')
    ccc_key=cfg.get('cellchat_output_key','cellchat_output')
    if ccc_key not in data.uns:raise ValueError('缺少原生 CellChat 上游结果')
    mapping=cfg.get('cellchat_condition_map',{k:k for k in data.uns[ccc_key]})
    if set(mapping)!=set(data.uns[ccc_key]) or set(mapping.values())!=set(conditions) or len(mapping)!=2:raise ValueError('原生 CellChat 结果必须与两个真实条件一一对应，名称差异须显式映射')
    for frame in data.uns[ccc_key].values():
        if not isinstance(frame,pd.DataFrame) or not {'ligand','receptor','interaction_name_2'}<=set(frame):raise ValueError('缺少原生 CellChat 输入字段')
    out=new_output(output);write_json(out/'run_config.json',cfg)
    # Start from actual expression and declared upstream inputs. Historical flow
    # matrices/networks in an example H5AD must never masquerade as this run.
    fresh=ad.AnnData(X=data.X.copy(),obs=data.obs.copy(),var=data.var.copy())
    fresh.uns[ccc_key]={mapping[k]:v.copy() for k,v in data.uns[ccc_key].items()}
    fresh.uns['log1p']={'base':None}
    gem_mode=cfg.get('gem_mode','native_nmf')
    seed=cfg.get('seed',0);np.random.seed(seed);random.seed(seed)
    if gem_mode=='reuse':
        if not cfg.get('upstream_gem_provenance'):raise ValueError('复用 GEM 需要实际算法、来源与拟合参数说明')
        gem_key=cfg.get('gem_key','X_gem')
        if gem_key not in data.obsm:raise ValueError('指定 GEM 不存在')
        gem=np.asarray(data.obsm[gem_key])
        if gem.ndim!=2 or gem.shape[0]!=fresh.n_obs or not np.isfinite(gem).all() or (gem<0).any() or (gem.sum(1)<=0).any():raise ValueError('GEM必须为对齐细胞的有限非负载荷，不能有全零细胞')
        fresh.obsm['X_gem']=gem.copy()
    elif gem_mode=='native_nmf':
        count_key=cfg.get('counts_layer','counts')
        if count_key not in data.layers:raise ValueError('原生NMF需要实际counts层')
        counts=data.layers[count_key]
        values=counts.data if hasattr(counts,'tocsr') else np.asarray(counts)
        if not np.isfinite(values).all() or (values<0).any() or not np.allclose(values,np.round(values),atol=1e-7):raise ValueError('NMF输入counts无效')
        keep=np.asarray(counts.sum(axis=0)).ravel()>0
        fresh=fresh[:,keep].copy();fresh.layers['counts']=counts[:,keep].copy()
        n_gems=cfg.get('n_gems',10)
        if not 2<=n_gems<min(fresh.shape):raise ValueError('NMF模块数超出矩阵秩范围')
        fs.pp.construct_gems_using_nmf(fresh,n_gems=n_gems,layer_key='counts',random_state=seed,max_iter=cfg.get('nmf_max_iter',1000))
        if not np.isfinite(fresh.obsm['X_gem']).all():raise ValueError('原生NMF产生非有限载荷')
    else:raise ValueError('未核验GEM构建分支；不能将NMF冒称iNMF/NSF')
    flow_config=fs.pp.FlowSigConfig(scale_gem_expr=cfg.get('scale_gem_expr',False))
    fs.pp.construct_flow_expressions(fresh,spatial=False,method='cellchat',cellchat_output_key=ccc_key,
        model_organism=cfg['species'],construction='v1',config=flow_config)
    if not np.isfinite(fresh.obsm['X_flow']).all():raise ValueError('原生flow构建出现非有限值')
    info=fresh.uns['flowsig_network']['flow_var_info']
    if not info.index.is_unique:raise ValueError('原生flow变量身份不唯一')
    info.to_csv(out/'native_full_variable_info.tsv',sep='\t')
    fs.pp.determine_informative_variables(fresh,spatial=False,condition_key=keys['condition'],control=cfg['control'],
        qval_threshold=cfg.get('selection_q',.05),logfc_threshold=cfg.get('selection_logfc',.5),construction='v1')
    info=fresh.uns['flowsig_network']['flow_var_info']
    if len(info)<3 or not {'inflow','module','outflow'}<=set(info.Type):raise ValueError('原生筛选后缺少完整inflow/module/outflow变量；不能人为补边')
    native_values=np.asarray(fresh.obsm['X_flow'],dtype=float)
    from flow_numerics import variance_eligibility,shared_scale
    eligible,variance_rows=variance_eligibility(native_values,fresh.obs[keys['condition']],info.index,
        floor=cfg.get('min_condition_relative_sd',1e-4),min_variable_cells=cfg.get('min_variable_cells',10))
    write_json(out/'variable_variance_eligibility.json',variance_rows)
    excluded=info.index[~eligible].tolist()
    if excluded:fs.pp.filter_flow_vars(fresh,info.index[eligible].tolist())
    info=fresh.uns['flowsig_network']['flow_var_info']
    if len(info)<3 or not {'inflow','module','outflow'}<=set(info.Type):raise ValueError('条件内变异资格检查后缺少模型必要变量类型；不降低门槛补图')
    # One positive scale per variable, shared across all conditions, preserves
    # Gaussian CI/invariance hypotheses. It prevents covariance pseudo-inverses
    # from truncating tiny upstream GEM units next to log-expression units.
    unscaled=np.asarray(fresh.obsm['X_flow'],dtype=float);scaled,scale=shared_scale(unscaled)
    fresh.obsm['X_flow_native_unscaled']=unscaled.copy()
    fresh.obsm['X_flow']=scaled
    fresh.uns['numerical_preconditioning']={'type':'one pooled standard deviation per variable; no condition-wise normalization','variables':info.index.tolist(),'scale':scale}
    pd.DataFrame({'variable':info.index,'pooled_standard_deviation':scale}).to_csv(out/'numerical_scaling.tsv',sep='\t',index=False)
    diagnostics=[]
    for condition in conditions:
        values=np.asarray(fresh.obsm['X_flow'])[fresh.obs[keys['condition']].eq(condition)]
        if values.shape[0]<=values.shape[1]+2 or np.any(values.std(0)==0):raise ValueError('条件内样本数不足或flow变量零方差，不能进行条件独立检验')
        correlation=np.corrcoef(values.T);rank=int(np.linalg.matrix_rank(correlation));condition_number=float(np.linalg.cond(correlation))
        diagnostics.append(dict(condition=condition,n_cells=values.shape[0],n_variables=values.shape[1],rank=rank,condition_number=condition_number))
        if rank<values.shape[1] or condition_number>1e10:
            write_json(out/'numerical_preflight.json',diagnostics)
            raise ValueError('flow变量存在确定性依赖/病态协方差；模块总和归一化可造成闭合约束。停止而不是给不稳定网络贴上通过标签')
    write_json(out/'numerical_preflight.json',diagnostics)
    n_boot=cfg.get('n_bootstraps',100)
    if n_boot<100:raise ValueError('至少100次原生bootstrap并报告频率分辨率')
    fresh.write_h5ad(out/'prepared_flows.h5ad')
    with warnings.catch_warnings():
        warnings.simplefilter('error',RuntimeWarning)
        fs.tl.learn_intercellular_flows(fresh,condition_key=keys['condition'],control=cfg['control'],
            use_spatial=False,n_jobs=1,n_bootstraps=n_boot,alpha_ci=cfg.get('alpha_ci',.001),alpha_inv=cfg.get('alpha_inv',.001))
    fs.tl.apply_biological_flow(fresh)
    fs.tl.filter_low_confidence_edges(fresh,edge_threshold=cfg.get('edge_threshold',.7),adjacency_key='adjacency_validated')
    fresh.write_h5ad(out/'flowsig_native.h5ad')
    net=fresh.uns['flowsig_network']['network'];names=list(net['flow_vars'])
    if names!=info.index.tolist():raise ValueError('原生网络与变量顺序不一致')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='FlowSig',method_version=version,implementation='native',
        provenance={**provenance,'parameters':cfg,'native_result_sha256':digest(out/'flowsig_native.h5ad'),
            'upstream_communication_provenance':cfg['upstream_communication_provenance'],
            'upstream_gem_provenance':cfg.get('upstream_gem_provenance', 'Native FlowSig NMF from declared counts'),
            'test_unit':'Native cell bootstrap and conditional-independence/invariance model; not donor-level effect inference',
            'bootstrap_seed':'Native root RNG fixed at 0; global NumPy/Python seeds recorded in config',
            'scale_gem_expr':flow_config.scale_gem_expr,'numerical_preflight':diagnostics,
            'variance_eligibility':dict(min_condition_relative_sd=floor,min_variable_cells=min_variable_cells,excluded_variables=excluded,meaning='Insufficient condition-wise variation for Gaussian CI; does not mean no biological response'),
            'numerical_preconditioning':'Each flow variable divided by one global standard deviation shared across conditions; original flow matrix and exact scales retained, selection done before scaling',
            'direction_evidence':'Model CPDAG plus biological type constraints; remaining reciprocal module edges are unresolved, not a demonstrated feedback loop'},tables=[])
    for key in ('adjacency','adjacency_validated','adjacency_validated_filtered'):
        matrix=np.asarray(net[key]);rows=[dict(row=names[i],column=names[j],value=float(matrix[i,j])) for i in range(len(names)) for j in range(len(names))]
        if not np.isfinite(matrix).all() or (matrix<0).any() or (matrix>1).any():raise ValueError('原生bootstrap边频率异常')
        add_table(bundle,out,key,'matrix',rows,'FlowSig原生bootstrap边频率；0表示本次模型未保留该边，不是无生物信号；频率不是P值。',value_kind='native_score',axis_label='Bootstrap edge frequency')
    matrix=np.asarray(net['adjacency_validated_filtered']);links=[]
    for i,j in zip(*matrix.nonzero()):
        links.append(dict(source=names[i],target=names[j],source_type=info.iloc[i].Type,target_type=info.iloc[j].Type,value=float(matrix[i,j]),
            direction_status='unresolved_reciprocal' if matrix[j,i]>0 else 'model_or_biological_constraint'))
    add_table(bundle,out,'flow_links','molecular_links',links,'经过原生生物学顺序约束与bootstrap筛选的模型关联；双向module边表示未定向，不画成已证明的双向作用。',
        value_kind='native_score',axis_label='Bootstrap edge frequency',additive=False)
    gem=np.asarray(fresh.obsm['X_gem']);rows=[]
    for sample in sorted(fresh.obs[keys['sample']].unique()):
        mask=fresh.obs[keys['sample']].eq(sample).to_numpy();meta=fresh.obs.loc[mask].iloc[0]
        for i,value in enumerate(gem[mask].mean(0)):
            rows.append(dict(sample=sample,donor=str(meta[keys['donor']]),condition=str(meta[keys['condition']]),feature=f'GEM-{i+1}',value=float(value)))
    add_table(bundle,out,'gem_sample_loadings','effects',rows,'每个实际样本的GEM细胞载荷均值，显示真实供体；不把细胞bootstrap频率当成供体差异显著性。',value_kind='native_score',axis_label='Mean native GEM loading')
    info.to_csv(out/'native_selected_variable_info.tsv',sep='\t');write_json(out/'bundle.json',bundle)
    import importlib.metadata as metadata
    write_json(out/'environment.json',{d.metadata['Name']:d.version for d in metadata.distributions()})
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();sys.exit(run(args.config,args.out))
