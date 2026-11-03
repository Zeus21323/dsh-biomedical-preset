#!/usr/bin/env python3
"""SpaCeNet原生空间高斯条件模型、正则化选择和收敛证据。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse, hashlib, importlib.metadata, json, pickle
from pathlib import Path
from communication_contract import add_table, digest, new_output, write_json, write_table
from communication_inputs import read_expression, require_version


def run(config, output):
    import numpy as np
    import torch
    from scipy import sparse
    import SpaCeNet
    from SpaCeNet.model import SpaCeNet as Model, SpaCeNetGridSearch
    from SpaCeNet.utils import Theta
    require_version('SpaCeNet', '0.0.1')
    cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    for key in ('dataset','research_question','features','feature_provenance','normalization_definition','coordinate_unit','coordinate_provenance','spatial_scale_provenance','penalty_provenance','resolution'):
        if not cfg.get(key):raise ValueError('缺少：'+key)
    if cfg['resolution'] not in ('single_cell','spot'):raise ValueError('须说明single_cell/spot')
    if cfg['coordinate_unit'] not in ('um','pixel','native'):raise ValueError('坐标单位须明确um/pixel/native')
    if cfg['coordinate_unit']=='native' and cfg.get('physical_scale_unavailable') is not True:raise ValueError('未知物理标定须显式记录')
    data,keys,provenance=read_expression(cfg,cp.parent)
    if cfg['expression_scale']=='counts':raise ValueError('先按输入特点确定变换；此高斯模型入口不默认将稀疏原始计数视为连续高斯测量')
    features=cfg['features']
    if not isinstance(features,list) or len(features)<2 or len(set(features))!=len(features) or not set(features)<=set(data.var_names):raise ValueError('features需要至少两个事先定义的唯一实测特征')
    if len(features)>cfg.get('max_features',100):raise ValueError('特征数超过空间模型参数规模契约，不能自动挑选结果相关特征')
    data=data[:,features].copy();coord_key=cfg.get('spatial_key','spatial')
    if coord_key not in data.obsm:raise ValueError('缺少真实空间坐标')
    coords=np.asarray(data.obsm[coord_key])
    if coords.shape!=(data.n_obs,2) or not np.isfinite(coords).all():raise ValueError('当前入口要求同细胞的真实二维坐标，不能用UMAP替代')
    theta_cfg={**dict(base='smoothed_potential',L=3,scale_correction='min',standardize=False,dist_method='euclidean'),**cfg.get('theta',{})}
    if set(theta_cfg)-{'base','L','scale_correction','standardize','dist_method','k','quantile'}:raise ValueError('未知Theta参数')
    if type(theta_cfg['L']) is not int or not 1<=theta_cfg['L']<=10:raise ValueError('L须为1–10的整数')
    if type(theta_cfg['standardize']) is not bool:raise ValueError('standardize须为布尔值')
    if theta_cfg['scale_correction']=='knn' and (type(theta_cfg.get('k')) is not int or theta_cfg['k']<1 or not 0<=theta_cfg.get('quantile',-1)<=1):raise ValueError('kNN尺度需明确k与分位数')
    options={**dict(step_size=1e-6,momentum=.9,eps=1e-5,max_iter=10000,max_step_size_reductions=3,step_size_reduction_factor=10.,verbose=True),**cfg.get('optimizer',{})}
    if set(options)-{'step_size','momentum','eps','max_iter','max_step_size_reductions','step_size_reduction_factor','verbose'}:raise ValueError('未知原生优化参数')
    if not 0<options['step_size']<1 or not 0<options['eps']<.1 or not 0<=options['momentum']<1 or type(options['max_iter']) is not int or options['max_iter']<100:raise ValueError('优化步长、精度、动量或最大步数无效')
    if type(options['max_step_size_reductions']) is not int or options['max_step_size_reductions']<0 or options['step_size_reduction_factor']<=1:raise ValueError('原生重试参数无效')
    grid=cfg.get('grid');penalty=cfg.get('penalty')
    if (grid is None)==(penalty is None):raise ValueError('须明确penalty或原生grid之一')
    if penalty is not None and (set(penalty)!= {'alpha','beta'} or any(not np.isfinite(v) or v<0 for v in penalty.values())):raise ValueError('alpha/beta须为非负有限数')
    if grid is not None:
        allowed={'min_alpha','max_alpha','n_alpha','min_beta','max_beta','n_beta','n_refinements','refinement_criterion'}
        if set(grid)!=allowed or grid['refinement_criterion'] not in ('AIC','BIC'):raise ValueError('原生网格需完整边界/数量/精化次数及AIC或BIC；不虚构测试集')
        if any(type(grid[k]) is not int or grid[k]<(1 if k=='n_refinements' else 2) for k in ('n_alpha','n_beta','n_refinements')):raise ValueError('网格每轴至少2点，精化至少1次')
        if not 0<grid['min_alpha']<grid['max_alpha'] or not 0<grid['min_beta']<grid['max_beta']:raise ValueError('网格正则范围无效')
        if grid['n_alpha']*grid['n_beta']*grid['n_refinements']>cfg.get('max_grid_fits',100):raise ValueError('网格规模超过执行契约')
    threads=cfg.get('threads',2)
    if type(threads) is not int or not 1<=threads<=8:raise ValueError('threads须为1–8')
    torch.set_num_threads(threads)
    versions={p:importlib.metadata.version(p) for p in ('SpaCeNet','numpy','torch','pandas','anndata')}
    native_root=Path(SpaCeNet.__file__).parent
    source_hashes={n:digest(native_root/n) for n in ('model.py','optimizer.py','utils.py')}
    parameters=dict(features=features,theta=theta_cfg,optimizer=options,grid=grid,penalty=penalty,penalize_diag=False,device='cpu',threads=threads,samples=cfg.get('samples'))
    signature=hashlib.sha256(json.dumps(dict(input=provenance,parameters=parameters,versions=versions,source=source_hashes),sort_keys=True).encode()).hexdigest()
    out=new_output(output);write_json(out/'run_config.json',cfg)
    reuse=(cp.parent/cfg['reuse_directory']).resolve() if cfg.get('reuse_directory') else None
    old=json.loads((reuse/'run_metadata.json').read_text()) if reuse else None
    if old and old['signature']!=signature:raise ValueError('缓存输入、原生实现、运行版本或科学参数变化')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='SpaCeNet',method_version='0.0.1',implementation='native',tables=[],provenance={**provenance,'parameters':cfg,'native_parameters':parameters,'versions':versions,'source_sha256':source_hashes,'coordinate_provenance':cfg['coordinate_provenance'],'upstream':dict(url='https://github.com/sschrod/SpaCeNet',commit='22923caeecc4f24b1696715146ae815b0e064aa0',license='MIT'),'semantics':'原生空间高斯伪似然加LASSO/group-LASSO。Omega与各阶Drho为对称条件关联参数，不是LR分数、方向性通讯或因果。AIC/BIC是训练数据的原生伪似然准则，不是外部验证。'})
    objects={}
    for i,sample in enumerate(data.obs[keys['sample']].unique(),1):
        sub=data[data.obs[keys['sample']]==sample];xy=np.asarray(sub.obsm[coord_key]);n=sub.n_obs
        if n<30 or n>cfg.get('max_units',5000) or theta_cfg['L']*n*n*8>cfg.get('max_theta_bytes',2**31):raise ValueError('样本单元数不足或Theta超过内存契约；不能自动抽样')
        if len(np.unique(xy,axis=0))!=n:raise ValueError('重复空间位置产生无穷距离势；需要实际分割或spot身份核验')
        if theta_cfg.get('k',1)>=n:raise ValueError('k不能达到样本单元数')
        values=sub.X.toarray() if sparse.issparse(sub.X) else np.asarray(sub.X)
        if np.any(np.std(values,axis=0,ddof=1)==0):raise ValueError('存在零方差特征，需在建模前按有记录的规则排除')
        fn=f'native_{i}.pkl';path=out/fn
        if reuse:
            if fn not in old['objects'] or old['objects'][fn]['sample']!=sample or old['objects'][fn]['sha256']!=digest(reuse/fn):raise ValueError('原生对象身份或摘要不一致')
            with (reuse/fn).open('rb') as f:obj=pickle.load(f)
            model=obj['model'];search=obj['search']
        else:
            theta=Theta(xy,**theta_cfg)
            if not np.isfinite(theta).all():raise ValueError('原生空间势非有限')
            X=torch.as_tensor(values,dtype=torch.float64);T=torch.as_tensor(theta,dtype=torch.float64)
            search=None;chosen=penalty
            if grid:
                search=SpaCeNetGridSearch(**grid,penalize_diag=False,warm_start=False,verbose=1,device='cpu',optimizer_options=dict(options))
                result=search.fit(X,T);result.to_csv(out/f'grid_{i}.tsv',sep='\t',index=False)
                write_json(out/f'grid_errors_{i}.json',search.errors)
                index=result[grid['refinement_criterion']].idxmin();best=result.loc[index]
                if not np.isfinite(best['eps_final']) or best['eps_final']>=options['eps']:raise ValueError('原生网格最优项未达到收敛要求；保留搜索结果，不能改选有利边')
                chosen={k:float(best[k]) for k in ('alpha','beta')}
            model=Model(**chosen,penalize_diag=False,device='cpu',optimizer_options=dict(options));model.fit(X,T)
            obj=dict(model=model,search=search,features=features,cells=list(sub.obs_names),sample=sample,coordinates=xy)
        with path.open('wb') as f:pickle.dump(obj,f,protocol=pickle.HIGHEST_PROTOCOL)
        objects[fn]=dict(sample=sample,sha256=digest(path));write_json(out/'run_metadata.json',dict(signature=signature,objects=objects))
        losses=model.losses.detach().numpy();params=model._params.detach().numpy()
        write_table(out/f'convergence_{i}.tsv',[dict(iteration=j+1,value=float(v)) for j,v in enumerate(losses)])
        converged=bool(np.isfinite(losses).all() and np.isfinite(params).all() and float(model.final_eps)<options['eps'])
        write_json(out/f'optimizer_status_{i}.json',dict(sample=sample,converged=converged,iterations=model.n_iter,final_eps=float(model.final_eps) if np.isfinite(float(model.final_eps)) else None,criterion='native relative projected pseudo-likelihood change',outputs=model.outputs))
        if not converged:raise ValueError('原生模型未收敛，已保留对象和轨迹；不能将最大迭代退出称为成功')
        omega=model.Omega_mat.detach().numpy();drho=model.Drho_tens.detach().numpy()
        if np.any(np.diag(omega)<=0):raise ValueError('原生条件方差参数无效')
        score,aic,bic=[float(v) for v in model.information_criterion(['AIC','BIC'])]
        if not np.isfinite([score,aic,bic]).all():raise ValueError('原生伪似然或准则无效')
        diagnostics=dict(sample=sample,units=n,features=len(features),alpha=model.alpha,beta=model.beta,pseudo_log_likelihood=score,AIC=aic,BIC=bic,omega_min_eigenvalue=float(np.linalg.eigvalsh(omega).min()),joint_precision_positive_definite='not_verified',statistical_unit='within-sample spatial units; no donor condition inference')
        write_json(out/f'diagnostics_{i}.json',diagnostics)
        add_table(bundle,out,f'optimizer_loss_{i}','matrix',[dict(row=str(j+1),column='Native projected loss',value=float(v)) for j,v in enumerate(losses)],'原生优化器每步投影点负伪对数似然，不含正则项；并非最终参数点的目标值，也不是跨数据可比性能',axis_label='Native projected negative pseudo-log-likelihood',figure_role='convergence',title=str(sample))
        for name,mat in [('omega',omega)]+[(f'drho_order_{j+1}',m) for j,m in enumerate(drho)]:
            add_table(bundle,out,f'{name}_{i}','matrix',[dict(row=a,column=b,value=float(mat[ri,ci])) for ri,a in enumerate(features) for ci,b in enumerate(features)],'原生对称空间高斯条件关联参数；Omega是单元内参数，Drho是距离势展开系数。符号不能直接解释为激活/抑制或配体受体，未验证完整空间精度矩阵正定性',axis_label='Native '+name,title=f'{sample}: {name}',row_order=features,column_order=features)
        if search is not None:
            search.results.to_csv(out/f'grid_{i}.tsv',sep='\t',index=False);write_json(out/f'grid_errors_{i}.json',search.errors)
            for metric in ('AIC','BIC'):
                rs=[dict(row=f'{a:.8g}',column=f'{b:.8g}',value=float(v) if np.isfinite(v) else None) for a,b,v in search.results[['alpha','beta',metric]].itertuples(index=False,name=None)]
                add_table(bundle,out,f'grid_{metric.lower()}_{i}','matrix',rs,'原生网格每次实际拟合的伪似然准则；行alpha、列beta，未拟合或失败为空，未完成边界外搜索',axis_label='Native pseudo-likelihood '+metric,title=f'{sample}: penalty search')
        spatial_kw=dict(coordinate_unit=cfg['coordinate_unit'],physical_scale_unavailable=cfg.get('physical_scale_unavailable',False),y_down=cfg.get('y_down',False))
        # Variable-conditional predictions use measured neighbors and other genes.
        # They are in-sample fitted values, never presented as independent accuracy.
        prediction=model.predict(model.X_train*model._X_std+model._X_mean,model.Theta_train,density='variable').detach().numpy()[0]
        if not np.isfinite(prediction).all():raise ValueError('原生条件预测非有限')
        for j,g in enumerate(features):
            for label,vs in [('observed',values[:,j]),('conditional_fitted',prediction[:,j])]:
                add_table(bundle,out,f'{label}_{i}_{j+1}','spatial_points',[dict(sample=sample,cell=cell,x=float(x),y=float(y),value=float(v)) for cell,(x,y),v in zip(sub.obs_names,xy,vs)],'实测输入或原生逐变量条件拟合值；拟合使用同样本的其他表达和邻域，不是外部验证、通讯强度或因果预测',axis_label=f'{g}: {label}',title=f'{sample}: {g} {label}',**spatial_kw)
    write_json(out/'bundle.json',bundle)
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--out',required=True);args=parser.parse_args();sys.exit(run(args.config,args.out))
