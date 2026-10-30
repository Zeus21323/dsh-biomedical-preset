#!/usr/bin/env python3
"""提取AnnData中已保存的PCA比例；不以截断特征值推造总解释率。"""
from pathlib import Path
import runpy
import math
delivery=runpy.run_path(str(Path(__file__).with_name('figure_delivery.py')))


def extract(cfg,base,out):
    import anndata
    require=delivery['require']
    require(not set(cfg)-{'input','pca_key','feature_space','denominator'},'未知PCA提取字段')
    require(cfg.get('denominator')=='total_input_variance' and cfg.get('feature_space'),'需根据实际运行确认总输入方差口径和特征空间')
    source=(base/cfg['input']).resolve();adata=anndata.read_h5ad(source)
    pca=adata.uns.get(cfg.get('pca_key','pca'),{})
    require('variance_ratio' in pca,'对象缺少原生variance_ratio，不能从部分特征值补造')
    values=list(pca['variance_ratio'])
    require(values and all(math.isfinite(float(v)) and 0<=float(v)<=1 for v in values),'PCA比例无效')
    require(sum(values)<=1+1e-6,'PCA比例合计超过1')
    rows=[dict(pc_index=i+1,statistic_type='variance_ratio',value=float(v),unit='fraction') for i,v in enumerate(values)]
    delivery['write_table'](out/'pca.tsv',rows)
    state=dict(input_sha256=delivery['digest'](source),pca_key=cfg.get('pca_key','pca'),pcs=len(rows),denominator=cfg['denominator'],feature_space=cfg['feature_space'],anndata=anndata.__version__)
    delivery['dump'](out/'extraction.json',state);return state


if __name__=='__main__':raise SystemExit(delivery['run_cli'](extract))
