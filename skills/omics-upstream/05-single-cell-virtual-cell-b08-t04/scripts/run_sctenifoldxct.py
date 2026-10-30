#!/usr/bin/env python3
"""原生scTenifoldXct：逐样本GRN、流形对齐及显式背景检验。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,importlib.metadata,json,pickle,warnings
from pathlib import Path
from communication_contract import add_table,digest,new_output,write_json,write_table
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,gene_identity


def run(config,output):
    import numpy as np,pandas as pd,torch
    from scipy import sparse
    import scTenifoldXct as st
    require_version('scTenifoldXct','0.2.2')
    cp=Path(config).resolve();cfg=json.loads(cp.read_text())
    for k in ('dataset','research_question','source_celltype','target_celltype','normalization_definition','input_provenance'):
        if not cfg.get(k):raise ValueError('缺少：'+k)
    if cfg.get('expression_scale')!='log_normalized':raise ValueError('原生流形要求真实log归一化表达，不能凭浮点类型推断归一化')
    data,keys,provenance=read_expression(cfg,cp.parent)
    if cfg['species']!='human':raise ValueError('此入口仅核验原生人类资源，不把大小写转换当同源映射')
    original=list(data.var_names);upper=[g.upper() for g in original]
    if len(set(upper))!=len(upper) or any('_' in g for g in upper):raise ValueError('原生大写/下划线配对身份不唯一；需要先处理有版本的基因映射，不能直接拆字符串')
    data.var_names=upper
    source,target=cfg['source_celltype'],cfg['target_celltype']
    if any('/' in v or '\\' in v or '\x00' in v for v in (source,target)):raise ValueError('细胞类型含原生文件路径分隔符，需先提供可追溯的安全标签映射')
    if source==target:raise ValueError('此双图原生API需要不同细胞类型；不伪装成自分泌检验')
    steps=int(cfg.get('training_steps',1000));minimum=int(cfg.get('min_cells',10));alpha=float(cfg.get('alpha',.05));test=cfg.get('test','empirical_null')
    if steps<1000 or minimum<6 or not 0<alpha<1 or test not in ('empirical_null','chi2'):raise ValueError('正式训练至少1000步；每群至少6细胞；阈值在(0,1)，test为empirical_null/chi2')
    if cfg.get('seed',0)!=0:raise ValueError('此原生版本构造网络时固定重置seed=0；不声称支持未生效的随机种子')
    if data.n_vars<8 or data.n_vars**2>cfg.get('max_gene_pairs',10_000_000):raise ValueError('特征数须至少8且基因对数不能超过内存契约；原生生成稠密双图和全部跨图距离')
    root=Path(st.__file__).parent;resources={name:digest(root/'database'/name) for name in ('LR.csv','TF.csv')}
    source_hashes={name:digest(root/name) for name in ('core.py','pcNet.py','nn.py','stat.py','stiefel.py')}
    versions={p:importlib.metadata.version(p) for p in ('scTenifoldXct','numpy','scipy','torch','statsmodels','anndata','scanpy')}
    params=dict(source=source,target=target,minimum=minimum,steps=steps,learning_rate=float(cfg.get('learning_rate',.01)),seed=0,query_DB=None,alpha=.5,mu=1.,scale_w=True,n_dim=3,n_cpus=1,grn_nComp=5,test=test,chi2_df=1,threads=int(cfg.get('threads',2)))
    if not 1<=params['threads']<=8 or not 0<params['learning_rate']<1:raise ValueError('线程须1–8且学习率在(0,1)')
    signature=hashlib.sha256(json.dumps(dict(input=provenance,resources=resources,source_hashes=source_hashes,versions=versions,params=params,samples=cfg.get('samples')),sort_keys=True).encode()).hexdigest()
    out=new_output(output);write_json(out/'run_config.json',cfg);write_table(out/'gene_identity.tsv',[dict(input_gene=a,native_gene=b) for a,b in zip(original,upper)])
    reuse=(cp.parent/cfg['reuse_directory']).resolve() if cfg.get('reuse_directory') else None;old=json.loads((reuse/'run_metadata.json').read_text()) if reuse else None
    if old and old['signature']!=signature:raise ValueError('缓存输入、资源、实现、版本或科学参数变化')
    bundle=dict(schema_version=2,dataset=cfg['dataset'],method='scTenifoldXct',method_version='0.2.2',implementation='native',tables=[],provenance={**provenance,'parameters':cfg,'native_parameters':params,'versions':versions,'database_sha256':resources,'source_sha256':source_hashes,'molecule_identity_schema':SCHEMA,'upstream':dict(url='https://github.com/cailab-tamu/scTenifoldXct',commit='01f6666238e135e473039707025583447039444c',license='MIT'),'semantics':'逐样本双细胞群原生GRN和Stiefel流形；原生图内权重为GRN+1，跨图对应权重基于表达均值/方差并缩放；不是组织空间。经验P来自非候选且对应权重非零的跨基因距离背景，不是细胞标签置换；chi2分支的BH覆盖全部跨基因对。无供体条件差异或实验因果解释。'})
    objects={};allrows=[];scope=[];torch.set_num_threads(params['threads'])
    for i,sample in enumerate(sorted(data.obs[keys['sample']].unique()),1):
        sub=data[(data.obs[keys['sample']]==sample)&data.obs[keys['cell_type']].isin([source,target])].copy();sizes=sub.obs[keys['cell_type']].value_counts();eligible=all(sizes.get(ct,0)>=minimum for ct in (source,target))
        scope.append(dict(sample=sample,source_cells=int(sizes.get(source,0)),target_cells=int(sizes.get(target,0)),eligible=eligible,reason='' if eligible else 'A requested cell type has fewer than min_cells'))
        write_table(out/'sample_eligibility.tsv',scope)
        if not eligible:continue
        folder=out/f'native_{i}';folder.mkdir();fn=f'native_{i}.pkl';path=out/fn
        if reuse:
            record=old['objects'].get(fn)
            if not record or record['sample']!=sample or record['sha256']!=digest(reuse/fn):raise ValueError('原生对象/样本摘要不符')
            with (reuse/fn).open('rb') as f:obj=pickle.load(f)
        else:
            st.set_seed(0)
            obj=st.scTenifoldXct(sub,source,target,keys['cell_type'],GRN_file_dir=folder/'grns',rebuild_GRN=True,n_cpus=1,random_state=0,verbose=True)
            if any(not np.isfinite(net.net.data).all() for net in (obj.net_A,obj.net_B)) or not np.isfinite(obj.w.data).all():raise ValueError('原生GRN或对应图包含非有限值，不能进入训练')
            emb=obj.get_embeds(train=True,n_steps=steps,lr=params['learning_rate'],verbose=True)
            if not np.isfinite(emb).all() or not np.isfinite(obj.trainer.losses).all():raise ValueError('原生训练返回非有限结果')
        with path.open('wb') as f:pickle.dump(obj,f,protocol=pickle.HIGHEST_PROTOCOL)
        objects[fn]=dict(sample=sample,sha256=digest(path));write_json(out/'run_metadata.json',dict(signature=signature,objects=objects))
        # Retain returned pre-final-update projections. Reloading only model weights
        # recomputes a different projection in this native version.
        obj.trainer.save_model_states(folder/'model_states')
        # Native GRN.save writes its original path even when a new dir is supplied.
        # Export its unchanged arrays explicitly to preserve previous runs.
        grn_dir=folder/'grns';grn_dir.mkdir(exist_ok=True)
        for role,net in [('sender',obj.net_A),('receiver',obj.net_B)]:
            sparse.save_npz(grn_dir/(role+'.npz'),net.net)
            write_table(grn_dir/(role+'_genes.tsv'),[dict(gene=str(g)) for g in net.gene_names])
        df=obj.aligned_dist
        if not np.isfinite(df['dist']).all():raise ValueError('原生距离无效')
        null=df[(~df.index.isin(obj.candidates))&(df['correspondence']!=0)]
        if test=='empirical_null' and null.empty:raise ValueError('原生经验距离背景为空，不返回伪P')
        # The >1 cutoff is for exporting the entire native candidate table only;
        # support below uses the configured alpha and is never relaxed.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            full=obj.null_test(pval=np.nextafter(1.,2.),filter_zeros=True) if test=='empirical_null' else obj.chi2_test(pval=np.nextafter(1.,2.),dof=1,cal_FDR=True)
        write_json(folder/'export_warnings.json',[str(w.message) for w in caught]);full.to_csv(folder/'native_candidate_test.tsv',sep='\t')
        if set(full.index)!=set(obj.candidates):raise ValueError('原生检验未覆盖全部候选，需要检查非有限P或身份冲突')
        donor=sub.obs[keys['donor']].iloc[0];condition=sub.obs[keys['condition']].iloc[0]
        for _,row in full.iterrows():
            criterion=row['q_val'] if test=='chi2' else row['p_val']
            d=dict(sample=sample,donor=donor,condition=condition,source=source,target=target,ligand=row['ligand'],receptor=row['receptor'],score=float(row['dist']),tested=True,supported=bool(criterion<alpha),p_value=float(row['p_val']),ligand_identity=gene_identity([row['ligand']]),receptor_identity=gene_identity([row['receptor']]))
            if test=='chi2':d['q_value']=float(row['q_val'])
            allrows.append(d)
        embeddings=obj.trainer.projections;gene_rows=[]
        for domain,genes,offset in [('sender',obj.genes[source],0),('receiver',obj.genes[target],len(obj.genes[source]))]:
            for j,gene in enumerate(genes):gene_rows.append(dict(entity=gene,domain=(source if domain=='sender' else target)+' ('+domain+')',x=float(embeddings[offset+j,0]),y=float(embeddings[offset+j,1]),z=float(embeddings[offset+j,2])))
        add_table(bundle,out,f'gene_manifold_{i}','latent_points',gene_rows,'原生Stiefel流形上的两个细胞群基因坐标；同一基因在发送/接收群是两个不同实体',coordinate_unit='latent',space_definition='Native scTenifoldXct 3D gene manifold; arbitrary latent coordinates, not tissue positions',title=f'{sample}: native gene manifold')
        losses=[dict(row=str(j+1),column='Native training loss',value=float(value)) for j,value in enumerate(obj.trainer.losses)]
        add_table(bundle,out,f'training_loss_{i}','matrix',losses,'原生训练目标每步原值；原生目标除以固定3000，不能直接跨不同特征集合解释为可比拟合优度',axis_label='Native training objective',figure_role='convergence',title=f'{sample}: model optimization')
        write_json(folder/'scope.json',dict(sample=sample,donor=donor,condition=condition,native_candidates=len(full),background_pairs=len(null),all_gene_pairs=len(df),minimum_distance=float(df['dist'].min()),final_returned_loss=float(obj.trainer.losses[-1]),interpretation='Descriptive within-sample model; no donor condition test'))
    write_table(out/'sample_eligibility.tsv',scope)
    if not objects:raise ValueError('没有样本同时具备足够的两个细胞群，保留资格记录')
    add_table(bundle,out,'lr_edges','lr_edges',allrows,'原生跨图基因距离，越小越靠近；支持规则来自所选原生经验P或全跨基因对BH。仅原生实测正端点候选，不补造缺失候选为0',value_kind='native_score',direction='lower',additive=False,axis_label='Native manifold distance',candidate_scope='native_positive_endpoint_candidates')
    write_json(out/'bundle.json',bundle)
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();sys.exit(run(a.config,a.out))
