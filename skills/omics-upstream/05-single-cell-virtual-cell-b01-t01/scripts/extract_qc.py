#!/usr/bin/env python3
"""按显式来源提取QC指标；不覆盖对象、不猜测样本或百分比单位。"""
from pathlib import Path
import runpy
import math
delivery=runpy.run_path(str(Path(__file__).with_name('figure_delivery.py')))
require=delivery['require']


def extract(cfg,base,out):
    import pandas as pd
    allowed={'input','cell_id','sample_column','stage','columns','units','counts_layer','mitochondrial_gene_ids','annotation_source'}
    require(not set(cfg)-allowed,'未知提取配置字段')
    source=(base/cfg['input']).resolve()
    require(isinstance(cfg.get('stage'),str) and cfg['stage'].strip(),'必须声明源对象真实过滤阶段')
    adata=None
    if source.suffix=='.h5ad':
        import anndata
        adata=anndata.read_h5ad(source)
        frame=adata.obs.copy();frame['_cell_id']=adata.obs_names
        cellcol=cfg.get('cell_id','_cell_id')
        require(adata.obs_names.is_unique and adata.var_names.is_unique,'细胞或基因ID重复')
    else:
        frame=pd.DataFrame(delivery['read_table'](source));cellcol=cfg.get('cell_id','cell_id')
    samplecol=cfg['sample_column']
    require(cellcol in frame and samplecol in frame,'缺少实际细胞或样本身份')
    require(not frame[[cellcol,samplecol]].isna().any().any(),'身份缺失')
    require(not frame.duplicated([samplecol,cellcol]).any(),'重复样本/细胞ID')
    columns=cfg.get('columns',{})
    require(columns or 'counts_layer' in cfg,'需要已验证字段映射或明确计数层')
    if 'counts_layer' in cfg:
        import numpy as np
        from scipy import sparse
        require(adata is not None,'补算QC只支持明确AnnData计数层')
        layer=cfg['counts_layer'];require(layer=='X' or layer in adata.layers,'计数层不存在')
        x=adata.X if layer=='X' else adata.layers[layer]
        x=x.copy()
        if sparse.issparse(x):x.sum_duplicates();x.eliminate_zeros()
        vals=x.data if sparse.issparse(x) else np.asarray(x)
        require(np.isfinite(vals).all() and (vals>=0).all() and np.equal(vals,np.floor(vals)).all(),'指定层不是非负整数计数')
        totals=np.asarray(x.sum(axis=1)).ravel();require((totals>0).all(),'存在零分母细胞；先报告并核查')
        frame['_total']=totals;frame['_genes']=np.asarray((x>0).sum(axis=1)).ravel()
        columns=dict(columns,total_counts='_total',detected_genes='_genes')
        genes=cfg.get('mitochondrial_gene_ids')
        if genes is not None:
            require(genes and cfg.get('annotation_source'),'线粒体集合需要实际ID和注释来源')
            mask=adata.var_names.isin(genes);require(mask.any(),'线粒体注释零匹配，不能当作真实零比例')
            frame['_mt']=np.asarray(x[:,mask].sum(axis=1)).ravel()/totals*100
            columns['mitochondrial_percent']='_mt'
    units=cfg.get('units',{})
    rows=[]
    for metric,col in columns.items():
        require(metric in {'total_counts','detected_genes','mitochondrial_percent'} and col in frame,'无效QC指标或缺列')
        unit=units.get(metric)
        if col in {'_total','_genes','_mt'}:unit={'_total':'counts','_genes':'genes','_mt':'%'}[col]
        expected={'total_counts':'counts','detected_genes':'genes','mitochondrial_percent':'%'}[metric]
        require(unit==expected or (metric=='mitochondrial_percent' and unit=='fraction'),'必须确认实际字段单位')
        for _,r in frame.iterrows():
            v=float(r[col]);require(math.isfinite(v) and v>=0,'QC字段存在缺失/非有限/负值')
            if unit=='fraction':require(v<=1,'比例超过1');v*=100
            if metric=='mitochondrial_percent':require(v<=100,'百分比超过100')
            else:require(v.is_integer(),'计数字段不是整数')
            rows.append(dict(cell_id=str(r[cellcol]),sample_id=str(r[samplecol]),stage=cfg['stage'],metric=metric,value=v,unit=expected))
    delivery['write_table'](out/'qc.tsv',rows)
    state=dict(input_sha256=delivery['digest'](source),rows=len(rows),columns=columns,stage=cfg['stage'],counts_layer=cfg.get('counts_layer'),annotation_source=cfg.get('annotation_source'),pandas=pd.__version__)
    delivery['dump'](out/'extraction.json',state);return state


if __name__=='__main__':raise SystemExit(delivery['run_cli'](extract))
