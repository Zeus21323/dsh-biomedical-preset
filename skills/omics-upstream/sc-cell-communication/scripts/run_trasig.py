#!/usr/bin/env python3
"""Run TraSig trajectory scores with an audited, non-mutating permutation adapter."""
from __future__ import annotations
import argparse,hashlib,importlib.metadata,json,re,sys
from pathlib import Path
import numpy as np
from communication_contract import add_table,digest,new_output,write_json
from communication_inputs import read_expression


SOURCE_COMMIT='465cffc10a77502aaee0b60f4d73940ca2e32379'
TRASIG_HASH='59b5636aac7dd577c146e12f8bbd89d5dc177f9a24a82355b45ce5cd7d44e50c'


def bh(values):
    values=np.asarray(values,float);order=np.argsort(values,kind='stable');ranked=values[order]
    adjusted=np.minimum.accumulate((ranked*len(values)/np.arange(1,len(values)+1))[::-1])[::-1]
    out=np.empty(len(values));out[order]=np.minimum(adjusted,1);return out


def read_lr(path):
    import pandas as pd
    frame=pd.read_csv(path,sep='\t',dtype=str,keep_default_na=False)
    if not {'ligand','receptor'}<=set(frame):raise ValueError('LR资源须含ligand/receptor列')
    if frame.empty or frame[['ligand','receptor']].apply(lambda x:x.str.strip().eq('')).any().any():raise ValueError('LR资源为空或有空端点')
    frame['interaction']=frame['interaction'] if 'interaction' in frame else frame['ligand']+'_'+frame['receptor']
    if frame['interaction'].duplicated().any():raise ValueError('interaction身份必须唯一；不要静默合并重复LR')
    return frame


def smooth_profiles(values,paths,times,path_ids,n_lap,starting_treatment,nan2zero):
    import bottleneck as bn
    import pandas as pd
    all_times=np.round(np.arange(0,1.01,.01),2);exp=[];count=[]
    for path in path_ids:
        keep=paths==path;cur=pd.DataFrame(values[keep]);cur['time']=times[keep]
        sums=cur.groupby('time').sum().reindex(all_times)
        counts=cur.iloc[:,[0]].groupby(cur['time']).count().reindex(all_times).iloc[:,0]
        exp.append(sums.to_numpy()[:,None,:]);count.append(counts.to_numpy()[:,None])
    exp=np.concatenate(exp,axis=1);count=np.concatenate(count,axis=1)
    if starting_treatment=='smallerWindow':
        smaller=max(1,n_lap//2)
        small=bn.move_sum(exp,window=smaller,min_count=1,axis=0)/bn.move_sum(count,window=smaller,min_count=1,axis=0)[:,:,None]
        if nan2zero:small=np.nan_to_num(small)
    full=bn.move_sum(exp,window=n_lap,min_count=1,axis=0)/bn.move_sum(count,window=n_lap,min_count=1,axis=0)[:,:,None]
    if nan2zero:full=np.nan_to_num(full)
    if starting_treatment=='discard':return all_times[n_lap:],full[n_lap:]
    if starting_treatment=='smallerWindow':return all_times[smaller:],np.concatenate([small[smaller:n_lap],full[n_lap:]],axis=0)
    return all_times,full


def corrected_permutation(paths,times,path_ids,index):
    """Implement the upstream docstring while avoiding its cell_times_o alias mutation."""
    rng=np.random.RandomState(index);permuted_paths=rng.permutation(paths);permuted_times=times.copy()
    for path in path_ids:
        original=times[paths==path]
        if int((permuted_paths==path).sum())!=len(original):raise ValueError('置换后轨迹大小未保持')
        permuted_times[permuted_paths==path]=rng.permutation(original)
    return permuted_paths,permuted_times


def native_scores(model,profiles,ligand_idx,receptor_idx,path_ids):
    send={path:profiles[:,i,ligand_idx] for i,path in enumerate(path_ids)}
    receive={path:profiles[:,i,receptor_idx] for i,path in enumerate(path_ids)}
    result={}
    for path in path_ids:result.update(model.process_per_path(path,send,receive))
    return result


def run(config,output):
    import pandas as pd
    cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    required=('dataset','research_question','input','species','expression_scale','layer','normalization_definition','input_provenance','trajectory_provenance','resource_provenance','sampling_time_provenance','native_root','lr_resource','path_key','pseudotime_key')
    for key in required:
        if not cfg.get(key):raise ValueError('缺少：'+key)
    if cfg.get('align_type','unaligned')!='unaligned':raise ValueError('当前已验收入口仅支持原生unaligned评分；DTW分支尚未验收，不能静默替代')
    if cfg.get('permutation_mode','documented_intent_copy')!='documented_intent_copy':raise ValueError('上游精确置换会原地污染伪时间，拒绝生成其P值')
    n_lap=cfg.get('n_lap',20);n_perm=cfg.get('n_permutations',1000);alpha=cfg.get('alpha',.05)
    if type(n_lap) is not int or not 1<=n_lap<=50:raise ValueError('n_lap须为1..50整数')
    if type(n_perm) is not int or not 100<=n_perm<=100000:raise ValueError('校正置换次数须为100..100000整数')
    if not isinstance(alpha,(int,float)) or not 0<alpha<1:raise ValueError('alpha无效')
    metrics=cfg.get('metrics',['dot'])
    if not isinstance(metrics,list) or not metrics or not set(metrics)<={'dot','cov'}:raise ValueError('metrics仅支持dot/cov')
    starting=cfg.get('starting_treatment','smallerWindow')
    if starting not in ('smallerWindow','discard','None'):raise ValueError('starting_treatment当前支持smallerWindow/discard/None')
    native_root=(cp.parent/cfg['native_root']).resolve();source=native_root/'trasig/trasig.py'
    if digest(source)!=TRASIG_HASH:raise ValueError('需要已核验TraSig源码 '+SOURCE_COMMIT)
    sys.path.insert(0,str(native_root));from trasig.trasig import trasig as TraSig
    ad,keys,provenance=read_expression(cfg,cp.parent);path_key=cfg['path_key'];time_key=cfg['pseudotime_key']
    for key in (path_key,time_key):
        if key not in ad.obs or ad.obs[key].isna().any():raise ValueError('缺失轨迹字段：'+key)
    times_all=pd.to_numeric(ad.obs[time_key],errors='raise').to_numpy(float)
    if not np.isfinite(times_all).all() or (times_all<0).any() or (times_all>1).any():raise ValueError('伪时间必须有限且缩放到[0,1]')
    lr_path=(cp.parent/cfg['lr_resource']).resolve();lr=read_lr(lr_path)
    measured=lr['ligand'].isin(ad.var_names)&lr['receptor'].isin(ad.var_names);lr=lr.loc[measured].reset_index(drop=True)
    if lr.empty:raise ValueError('没有两端均实测的LR候选')
    if len(lr)>cfg.get('max_lr_pairs',10000):raise ValueError('LR规模超出契约，不静默截断')
    genes=list(dict.fromkeys(lr['ligand'].tolist()+lr['receptor'].tolist()));gene_index={g:i for i,g in enumerate(genes)}
    ligand_idx=np.array([gene_index[g] for g in lr['ligand']]);receptor_idx=np.array([gene_index[g] for g in lr['receptor']])
    params=dict(n_lap=n_lap,n_permutations=n_perm,metrics=metrics,starting_treatment=starting,nan2zero=cfg.get('nan2zero',True),alpha=alpha,align_type='unaligned',permutation_mode='documented_intent_copy')
    versions={p:importlib.metadata.version(p) for p in ('trasig','numpy','pandas','Bottleneck','anndata')}
    signature=hashlib.sha256(json.dumps(dict(input=provenance,trajectory=cfg['trajectory_provenance'],lr_sha256=digest(lr_path),parameters=params,source=digest(source),versions=versions),sort_keys=True).encode()).hexdigest()
    out=new_output(output);write_json(out/'run_config.json',cfg)
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='TraSig',method_version='1.0.0',implementation='native_unaligned_score_with_audited_permutation_adapter',tables=[],provenance={**provenance,'parameters':cfg,'versions':versions,'lr_resource_sha256':digest(lr_path),'upstream':dict(url='https://github.com/doraadong/TraSig',commit=SOURCE_COMMIT,license='MIT'),'upstream_defect':'generate_permutation assigns permutated_times=self.cell_times_o and mutates the observed array. Exact upstream permutation P values are disabled; documented_intent_copy preserves the stated conditional-time and path-size distributions without mutation.','inference_scope':'Cell-label/pseudotime permutation within one expression dataset; not donor-level inference and not independent validation of the fitted trajectory.'})
    all_edge_rows=[];all_profile_rows=[];objects={}
    for sample_index,sample in enumerate(ad.obs[keys['sample']].unique(),1):
        obs_mask=ad.obs[keys['sample']].to_numpy()==sample;sub=ad[obs_mask,genes];values=sub.X.toarray() if hasattr(sub.X,'toarray') else np.asarray(sub.X)
        raw_paths=sub.obs[path_key].astype(str).to_numpy();raw_times=np.round(pd.to_numeric(sub.obs[time_key]).to_numpy(float),2)
        unique_raw=sorted(set(raw_paths));code={name:i for i,name in enumerate(unique_raw)};paths=np.array([code[x] for x in raw_paths]);path_ids=np.arange(len(unique_raw))
        counts=np.bincount(paths,minlength=len(path_ids));minimum=cfg.get('min_cells_per_path',max(20,n_lap))
        if len(path_ids)<2 or np.any(counts<minimum):raise ValueError(f'样本{sample}轨迹少于2条或有轨迹细胞数不足{minimum}')
        times_cfg=cfg.get('path_sampling_time',{});sample_times=times_cfg.get(sample,times_cfg) if isinstance(times_cfg,dict) else {}
        if not sample_times:
            if cfg.get('sampling_time_unavailable') is not True:raise ValueError('缺少path_sampling_time；未知时须显式sampling_time_unavailable=true')
            sample_times={name:0 for name in unique_raw}
        if set(sample_times)!=set(unique_raw):raise ValueError('path_sampling_time必须精确覆盖样本全部轨迹')
        time2path={}
        for name in unique_raw:time2path.setdefault(str(sample_times[name]),[]).append(code[name])
        path2time={path:t for t,ps in time2path.items() for path in ps};rounded_times=raw_times.copy()
        model=TraSig(metrics,time2path,path2time,rounded_times.copy(),paths.copy(),path_ids)
        grid,observed_profiles=smooth_profiles(values,paths,rounded_times,path_ids,n_lap,starting,cfg.get('nan2zero',True))
        observed=native_scores(model,observed_profiles,ligand_idx,receptor_idx,path_ids)
        count_extreme={pair:{m:np.zeros(len(lr),dtype=int) for m in metrics} for pair in observed}
        for permutation in range(1,n_perm+1):
            perm_paths,perm_times=corrected_permutation(paths,rounded_times,path_ids,permutation)
            _,profiles=smooth_profiles(values,perm_paths,perm_times,path_ids,n_lap,starting,cfg.get('nan2zero',True))
            perm=native_scores(model,profiles,ligand_idx,receptor_idx,path_ids)
            for pair in observed:
                for metric in metrics:count_extreme[pair][metric]+=np.asarray(perm[pair][metric])>=np.asarray(observed[pair][metric])
        native_file=out/f'native_scores_{sample_index}.npz'
        arrays={f'{pair}__{metric}':np.asarray(vals[metric]) for pair,vals in observed.items() for metric in metrics}
        arrays.update(profile_grid=grid,profiles=observed_profiles,path_labels=np.asarray(unique_raw),genes=np.asarray(genes));np.savez_compressed(native_file,**arrays)
        objects[native_file.name]=dict(sha256=digest(native_file),sample=sample,paths=len(path_ids),cells=sub.n_obs)
        path_label={code[name]:f'path {name}: '+sub.obs.loc[raw_paths==name,keys['cell_type']].value_counts().index[0] for name in unique_raw}
        sample_rows=[]
        for pair,score_set in observed.items():
            left,right=(int(x) for x in pair.split('_'))
            for metric in metrics:
                scores=np.asarray(score_set[metric],float);p=(count_extreme[pair][metric]+1)/(n_perm+1);q=bh(p)
                for i,row in lr.iterrows():
                    sample_rows.append(dict(sample=sample,source=path_label[left],target=path_label[right],ligand=row.ligand,receptor=row.receptor,interaction=row.interaction+' | '+metric,score=float(scores[i]),tested=True,supported=bool(q[i]<alpha),p_value=float(p[i]),q_value=float(q[i]),permutation_mode='documented_intent_copy',permutations=n_perm,correction_scope=f'BH within sample/path pair/{metric}'))
        all_edge_rows.extend(sample_rows)
        chosen=sorted(sample_rows,key=lambda r:(r['q_value'],-r['score'],r['interaction']))[:cfg.get('trajectory_display',6)]
        seen=set()
        donor=str(sub.obs[keys['donor']].iloc[0])
        for row in chosen:
            pair_metric=row['interaction'].rsplit(' | ',1);metric=pair_metric[1]
            left=next(k for k,v in path_label.items() if v==row['source']);right=next(k for k,v in path_label.items() if v==row['target'])
            for role,path,gene,gidx in (('sender',left,row['ligand'],gene_index[row['ligand']]),('receiver',right,row['receptor'],gene_index[row['receptor']])):
                feature=f'{row["ligand"]}–{row["receptor"]} {metric} | {role} {path_label[path]}'
                if feature in seen:continue
                seen.add(feature)
                for t,value in zip(grid,observed_profiles[:,path,gidx]):all_profile_rows.append(dict(sample=sample,donor=donor,feature=feature,time=float(t),value=float(value)))
    add_table(bundle,out,'trajectory_lr_scores','lr_edges',all_edge_rows,'TraSig原生unaligned滑窗dot/cov评分；P为修复数组别名缺陷后按上游文档意图进行的细胞轨迹标签/条件伪时间置换，q在每个样本、轨迹对和指标内BH。不是供体检验；不交付上游已证实污染的精确置换P',direction='higher',additive=False,value_kind='native_trajectory_score',axis_label='Native TraSig trajectory score',alpha=alpha,statistical_unit='cells under a fixed, already inferred trajectory')
    add_table(bundle,out,'selected_trajectory_profiles','time_series',all_profile_rows,'按完整校正q和原生评分预先选定的展示候选之原生滑窗平均表达轨迹；完整LR评分和全部路径×基因轨迹保存在NPZ，不把曲线当独立重复',time_kind='pseudotime',time_unit='rounded 0..1 trajectory position',selection=f'Per sample first {cfg.get("trajectory_display",6)} rows ordered by corrected q, score and identity; duplicated displayed profiles removed')
    write_json(out/'run_metadata.json',dict(signature=signature,objects=objects,status='completed_with_corrected_permutation',upstream_exact_permutation_status='disabled_invalid'))
    write_json(out/'bundle.json',bundle)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--out',required=True);args=parser.parse_args();run(args.config,args.out)
