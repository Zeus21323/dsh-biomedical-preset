#!/usr/bin/env python3
"""Run the pinned SpaOTsc signaling transport API on measured spatial coordinates."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,collections,collections.abc,hashlib,importlib.metadata,json,pickle,re,warnings
from pathlib import Path
from communication_contract import add_table,digest,new_output,write_json,write_table
from communication_inputs import read_expression,require_version


def native_import():
    # dit 1.2.3 imports ABC aliases removed in Python 3.10. Restore only names;
    # this compatibility step changes no transport or information calculation.
    aliases=[]
    for name in ('Iterable','Sequence','Mapping','MutableMapping','MutableSet','Set'):
        if not hasattr(collections,name):setattr(collections,name,getattr(collections.abc,name));aliases.append(name)
    from spaotsc import SpaOTsc
    if digest(SpaOTsc.__file__)!='2606c43c717904ddab3e726cc5c3e7943ab02eb5d8886620fc63553e6edf3c7b':raise ValueError('需要已核验SpaOTsc源码def2762')
    require_version('spaotsc','0.2')
    return SpaOTsc,aliases


def run(config,output):
    import numpy as np,pandas as pd
    from scipy import sparse
    from scipy.spatial.distance import cdist
    native,aliases=native_import();cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    for key in ('dataset','research_question','queries','resource_provenance','normalization_definition','coordinate_unit','coordinate_provenance','spatial_scale_provenance','resolution'):
        if not cfg.get(key):raise ValueError('缺少：'+key)
    if cfg['resolution'] not in ('single_cell','spot'):raise ValueError('须明确空间分辨率；混合spot结果不是单细胞通讯')
    if cfg['coordinate_unit'] not in ('um','pixel','native'):raise ValueError('坐标单位无效')
    if cfg['coordinate_unit']=='native' and cfg.get('physical_scale_unavailable') is not True:raise ValueError('未知物理标定须显式说明')
    ad,keys,prov=read_expression(cfg,cp.parent);spatial_key=cfg.get('spatial_key','spatial');queries=cfg['queries']
    if spatial_key not in ad.obsm or np.asarray(ad.obsm[spatial_key]).shape!=(ad.n_obs,2) or not np.isfinite(ad.obsm[spatial_key]).all():raise ValueError('需要同单元真实二维空间坐标，不能用UMAP或猜测位置')
    if not isinstance(queries,list) or len(queries)>50:raise ValueError('query列表无效或超过预设规模')
    identifiers=set();gene_keys=('Lgenes','Rgenes','Tgenes','Rbgenes','DSgenes_up','DSgenes_down');features=set()
    for q in queries:
        if set(q)-set(gene_keys)-{'id','gene_bandwidth','effect_range','epsilon','kernel_nu','use_kernel_ligand','use_kernel_receptor'}:raise ValueError('未知参数；此原生API中的rho没有进入sinkhorn计算，不能配置为不平衡传输')
        if not re.fullmatch('[a-z][a-z0-9_]*',q.get('id','')) or q['id'] in identifiers:raise ValueError('query id须唯一安全标识')
        identifiers.add(q['id'])
        for key in gene_keys:
            genes=q.get(key,[])
            if not isinstance(genes,list) or len(set(genes))!=len(genes) or not all(isinstance(g,str) and g in ad.var_names for g in genes):raise ValueError('query基因未实测或身份重复：'+key)
            features.update(genes)
        if not q.get('Lgenes') or not q.get('Rgenes') or set(q.get('DSgenes_up',[]))&set(q.get('DSgenes_down',[])):raise ValueError('缺少LR或同一靶基因上下调角色冲突')
        for key in ('use_kernel_ligand','use_kernel_receptor'):
            if key in q and type(q[key]) is not bool:raise ValueError('核开关须为布尔值')
        for key,default in (('epsilon',.2),('kernel_nu',5)):
            if not isinstance(q.get(key,default),(int,float)) or not np.isfinite(q.get(key,default)) or q.get(key,default)<=0:raise ValueError('熵正则/核幂必须正且有限')
        if q.get('effect_range') is not None and (not np.isfinite(q['effect_range']) or q['effect_range']<=0):raise ValueError('effect_range须为同坐标单位的正距离')
        if any(g not in {gene for key in gene_keys for gene in q.get(key,[])} or not np.isfinite(v) or v<=0 for g,v in q.get('gene_bandwidth',{}).items()):raise ValueError('gene_bandwidth须对应实测角色基因且正有限')
    features=sorted(features);versions={p:importlib.metadata.version(p) for p in ('spaotsc','numpy','pandas','scipy','POT','dit','anndata')}
    params=dict(queries=queries,coordinate_key=spatial_key,samples=cfg.get('samples'),actual_transport='POT balanced sinkhorn, native S/max(S)',marginal_tolerance=cfg.get('marginal_tolerance',1e-5))
    if not isinstance(params['marginal_tolerance'],(int,float)) or not 0<params['marginal_tolerance']<=1e-3:raise ValueError('边缘误差阈值必须预先规定且不大于1e-3')
    signature=hashlib.sha256(json.dumps(dict(input=prov,parameters=params,versions=versions,source=digest(native.__file__)),sort_keys=True).encode()).hexdigest()
    out=new_output(output);write_json(out/'run_config.json',cfg);reuse=(cp.parent/cfg['reuse_directory']).resolve() if cfg.get('reuse_directory') else None;old=json.loads((reuse/'run_metadata.json').read_text()) if reuse else None
    if old and old['signature']!=signature:raise ValueError('原生复用的输入/版本/参数变化')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='SpaOTsc',method_version='0.2',implementation='native',tables=[],provenance={**prov,'parameters':cfg,'versions':versions,'compatibility_abc_aliases':aliases,'upstream':dict(url='https://github.com/zcang/SpaOTsc',commit='def276221e3b636916a812b39f2658737584c212',license='MIT'),'semantics':'使用真实空间位置的原生spatial_signaling_ot；实际是平衡Sinkhorn，rho未使用。多基因L/R列表按均值，不是复合物AND；effect_range外距离乘10而非硬截断，输出S/max(S)是相对分数不是概率/绝对通量。每次用新对象/距离副本防止原生就地距离修改污染下一查询。'})
    records={}
    for i,sample in enumerate(ad.obs[keys['sample']].unique(),1):
        sub=ad[ad.obs[keys['sample']]==sample,features];n=sub.n_obs;xy=np.asarray(sub.obsm[spatial_key]);ids=sub.obs_names.tolist()
        if n<3 or n>cfg.get('max_units',2000) or n*n*8*10>cfg.get('max_working_bytes',2**31):raise ValueError('空间单元规模超出契约，不静默抽样')
        if len(np.unique(xy,axis=0))!=n:raise ValueError('空间坐标重复，请先核验实际单元身份')
        values=sub.X.toarray() if sparse.issparse(sub.X) else np.asarray(sub.X);df=pd.DataFrame(values,index=ids,columns=features);distance=cdist(xy,xy);groups=sub.obs[keys['cell_type']].to_numpy();labels=sorted(set(groups))
        write_table(out/f'identities_{i}.tsv',[dict(cell=c,cell_type=g,x=float(v[0]),y=float(v[1])) for c,g,v in zip(ids,groups,xy)])
        for j,q in enumerate(queries,1):
            fn=f'native_{i}_{j}.pkl';path=out/fn;options={k:v for k,v in q.items() if k!='id'}
            def weights(genes,kernel,p=-1):
                if not genes:return np.ones(n)
                xx=[]
                for gene in genes:
                    v=df[gene].to_numpy()
                    xx.append(native.phi_exp(v,q.get('gene_bandwidth',{}).get(gene,1.),q.get('kernel_nu',5),p) if kernel else v)
                return np.mean(xx,axis=0)
            ws=weights(q['Lgenes'],q.get('use_kernel_ligand',False))*weights(q.get('Tgenes',[]),True)
            up=q.get('DSgenes_up',[]);down=q.get('DSgenes_down',[])
            downstream=(len(up)*weights(up,True)+len(down)*weights(down,True,1))/(len(up)+len(down)) if up or down else np.ones(n)
            wt=weights(q['Rgenes'],q.get('use_kernel_receptor',False))*weights(q.get('Rbgenes',[]),True)*downstream
            if not np.isfinite(ws).all() or not np.isfinite(wt).all():raise ValueError('原生权重变换非有限')
            if ws.sum()==0 or wt.sum()==0:
                add_table(bundle,out,f'no_signal_{i}_{j}','matrix',[dict(row=q['id'],column='Eligible native transports',value=0)],'观测表达下至少一侧总权重为0，原生归一化不可定义；未运行传输，不是全组织无通讯证据',value_kind='count');continue
            if reuse:
                if fn not in old['objects'] or old['objects'][fn]['sample']!=sample or old['objects'][fn]['sha256']!=digest(reuse/fn):raise ValueError('原生对象身份/摘要不符')
                with (reuse/fn).open('rb') as f:obj=pickle.load(f)
            else:
                model=native.spatial_sc(sc_data=df);model.cell_cell_distance(sc_dmat_spatial=distance.copy())
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always');score=model.spatial_signaling_ot(**options)
                obj=dict(model=model,score=score,original_distance=distance,options=options,warnings=[str(w.message) for w in caught])
            with path.open('xb') as f:pickle.dump(obj,f)
            records[fn]=dict(sample=sample,query=q['id'],sha256=digest(path));write_json(out/'run_metadata.json',dict(signature=signature,objects=records))
            s=np.asarray(obj['score']);write_json(out/f'warnings_{i}_{j}.json',obj['warnings'])
            if s.shape!=(n,n) or not np.isfinite(s).all() or np.any(s<0) or s.max()<=0:raise ValueError('原生传输非有限/空，原始对象已保存')
            normalized=s/s.sum();error=max(float(abs(normalized.sum(1)-ws/ws.sum()).max()),float(abs(normalized.sum(0)-wt/wt.sum()).max()))
            write_json(out/f'conservation_{i}_{j}.json',dict(max_marginal_error=error,native_max_score=float(s.max()),definition='Recover unit-mass transport S/sum(S) only to check native balanced marginals; delivered S retains native max normalization'))
            if error>params['marginal_tolerance']:raise ValueError('原生Sinkhorn未满足预设边缘误差要求；保留对象，不交付为收敛成功')
            np.savez_compressed(out/f'full_transport_{i}_{j}.npz',score=s,cell_ids=np.asarray(ids))
            title=f'{sample}: {q["id"]}'
            for role,v in (('outgoing',s.sum(1)),('incoming',s.sum(0))):add_table(bundle,out,f'spatial_{role}_{i}_{j}','spatial_points',[dict(sample=sample,cell=c,x=float(pos[0]),y=float(pos[1]),value=float(val)) for c,pos,val in zip(ids,xy,v)],'原生最大值归一化传输矩阵的行/列和；不是分子浓度、绝对通量或跨查询可比概率',coordinate_unit=cfg['coordinate_unit'],physical_scale_unavailable=cfg.get('physical_scale_unavailable',False),y_down=cfg.get('y_down',False),title=f'{title}: {role}',axis_label='Sum of native relative transport scores')
            # Only the drawing edge list is thinned. Complete matrix and identities
            # are delivered above; this is not a statistical significance cutoff.
            ix=np.flatnonzero(s>0);cap=cfg.get('display_edges',1500)
            if type(cap) is not int or cap<1:raise ValueError('display_edges须为正整数')
            if len(ix)>cap:ix=ix[np.argsort(s.ravel()[ix],kind='stable')[-cap:]]
            add_table(bundle,out,f'spatial_edges_{i}_{j}','spatial_edges',[dict(sample=sample,source_cell=ids[k//n],target_cell=ids[k%n],value=float(s.ravel()[k])) for k in ix],'原生配体发送→受体接收方向；仅显示指定数量的最高分边，完整矩阵单独保留。选择是绘图密度控制，没有P/FDR',coordinate_unit=cfg['coordinate_unit'],physical_scale_unavailable=cfg.get('physical_scale_unavailable',False),y_down=cfg.get('y_down',False),directed=True,title=title)
            rows=[dict(source=g,target=h,value=float(s[np.ix_(groups==g,groups==h)].mean())) for g in labels for h in labels]
            add_table(bundle,out,f'group_network_{i}_{j}','network',rows,'每个真实群对的原生细胞对相对分数均值，包括原生自身边；仅同一查询内可对群对均值作描述性汇总；该查询独立max归一化，不能跨查询相加为绝对通讯强度',directed=True,additive=True,value_kind='nonnegative_strength',title=title,axis_label='Mean native relative transport score')
    write_json(out/'bundle.json',bundle)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.config,a.out)
