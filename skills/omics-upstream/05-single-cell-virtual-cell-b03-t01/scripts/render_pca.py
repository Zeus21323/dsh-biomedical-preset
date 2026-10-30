#!/usr/bin/env python3
"""绘制已计算PCA，不重新计算PCA或聚类。"""
from pathlib import Path
import runpy
import math
delivery=runpy.run_path(str(Path(__file__).with_name("figure_delivery.py")))
require=delivery["require"]


def render(cfg,base,out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    allowed={"table","question","caption","denominator","feature_space","cumulative","selected_pcs","selection_reason","font","width_mm","height_mm","dpi"}
    require(not set(cfg)-allowed,"未知PCA配置字段")
    require(all(isinstance(cfg.get(k),str) and cfg[k].strip() for k in ('table','question','caption','denominator','feature_space')),"缺少PCA表、图注、分母或特征空间说明")
    source=(base/cfg['table']).resolve();rows=delivery['read_table'](source)
    require({'pc_index','statistic_type','value','unit'}<=rows[0].keys(),"PCA表缺列")
    kind=rows[0]['statistic_type'];units={'stdev':'standard_deviation','variance_ratio':'fraction','retained_ratio':'fraction'}
    require(kind in units,"不支持的PCA指标")
    require(cfg['denominator'] in {'not_applicable','total_input_variance','stored_components_variance'},"分母必须明确")
    expected={'stdev':'not_applicable','variance_ratio':'total_input_variance','retained_ratio':'stored_components_variance'}
    require(cfg['denominator']==expected[kind],"PCA指标与分母口径冲突")
    for r in rows:
        require(r['statistic_type']==kind and r['unit']==units[kind],"PCA单位或指标混合")
        r['pc_index']=int(r['pc_index']);r['value']=float(r['value'])
        require(r['pc_index']>0 and math.isfinite(r['value']) and r['value']>=0,"无效PC索引或数值")
    rows.sort(key=lambda r:r['pc_index']);xs=[r['pc_index'] for r in rows];values=[r['value'] for r in rows]
    require(xs==list(range(1,len(xs)+1)),"PC必须从1连续且不能重复")
    if kind!='stdev':require(sum(values)<=1+1e-6,"解释比例之和超过1")
    cumulative=cfg.get('cumulative',False)
    require(type(cumulative) is bool and not (cumulative and kind=='stdev'),"标准差不能直接累积成解释率")
    selected=cfg.get('selected_pcs')
    if selected is not None:require(type(selected) is int and selected in xs and bool(cfg.get('selection_reason')),"选维参考线需有效PC数及依据")
    width=float(cfg.get('width_mm',183 if cumulative else 120));height=float(cfg.get('height_mm',90))
    require(89<=width<=300 and 60<=height<=300,"图尺寸不适合PCA")
    with plt.rc_context({'axes.grid':False,'font.family':cfg.get('font','DejaVu Sans'),'font.size':8,'axes.spines.top':False,'axes.spines.right':False}):
        fig,axes=plt.subplots(1,2 if cumulative else 1,squeeze=False,figsize=(width/25.4,height/25.4),layout='constrained')
        ys=values if kind=='stdev' else [v*100 for v in values]
        axes[0,0].plot(xs,ys,'o-',color='#0072B2',ms=3,lw=.8)
        label={'stdev':'Standard deviation','variance_ratio':'Total input variance explained (%)','retained_ratio':'Stored-component variance (%)'}[kind]
        axes[0,0].set_ylabel(label);axes[0,0].set_title('PCA scree')
        if cumulative:
            import numpy as np
            axes[0,1].plot(xs,np.cumsum(ys),color='#0072B2')
            axes[0,1].set_ylabel('Cumulative '+label.lower());axes[0,1].set_title('Cumulative proportion')
        from matplotlib.ticker import MaxNLocator
        proposed=[int(x) for x in MaxNLocator(nbins=6,integer=True).tick_values(1,len(xs)) if 1<int(x)<=len(xs)]
        ticks=[1]+proposed
        if len(xs)>1 and ticks[-1]!=len(xs):
            if len(ticks)>1 and len(xs)-ticks[-1] < max(1,len(xs)/12):ticks.pop()
            ticks.append(len(xs))
        for ax in axes[0]:
            ax.set_xlabel('Principal component');ax.set_xticks(ticks);ax.set_xlim(.5,len(xs)+.5)
            ax.set_ylim(bottom=0)
            if selected is not None:ax.axvline(selected,color='#666666',ls='--',lw=.6)
        try:record=delivery['save_figure'](fig,out/'pca.png',dpi=cfg.get('dpi',400))
        finally:plt.close(fig)
    records=[record]
    if cumulative:
        for name,ysingle,ylabel in [('scree',ys,label),('cumulative',list(__import__('numpy').cumsum(ys)),'Cumulative '+label.lower())]:
            with plt.rc_context({'axes.grid':False,'font.family':cfg.get('font','DejaVu Sans'),'font.size':8,'axes.spines.top':False,'axes.spines.right':False}):
                single,ax=plt.subplots(figsize=(max(89,width/2)/25.4,height/25.4),layout='constrained')
                ax.plot(xs,ysingle,'o-',color='#0072B2',ms=3,lw=.8)
                ax.set(xlabel='Principal component',ylabel=ylabel,title=name.capitalize(),xticks=ticks,xlim=(.5,len(xs)+.5))
                ax.set_ylim(bottom=0)
                if selected is not None:ax.axvline(selected,color='#666666',ls='--',lw=.6)
                try:records.append(delivery['save_figure'](single,out/('pca_'+name+'.png'),dpi=cfg.get('dpi',400)))
                finally:plt.close(single)
    delivery['write_table'](out/'plot_data.tsv',rows)
    delivery['dump'](out/'figure_manifest.json',dict(status='generated',figures=records,source_sha256=delivery['digest'](source),generated_statistics=False,visual_review='pending',denominator=cfg['denominator']))
    (out/'caption.md').write_text(cfg['question']+'\n\n'+cfg['caption']+'\n\n分母：'+cfg['denominator']+'；特征空间：'+cfg['feature_space']+'。曲线拐点不证明后续PC全为噪声。\n\n[PNG](pca.png) · [SVG](pca.svg) · [PDF](pca.pdf)\n',encoding='utf-8')
    return dict(pcs=len(rows),denominator=cfg['denominator'])


if __name__=='__main__':raise SystemExit(delivery['run_cli'](render))
