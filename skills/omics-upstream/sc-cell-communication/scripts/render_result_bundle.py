#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["numpy==2.2.6", "scipy==1.17.0", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""按真实结果类型连续生成领域图集；不从结果表补造统计或分子路径。"""
from __future__ import annotations

from pathlib import Path as _DeliveryPath
from runpy import run_path as _delivery_run_path
save_figure = _delivery_run_path(str(_DeliveryPath(__file__).with_name("figure_delivery.py")))["save_figure"]

import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import sys
import textwrap
sys.dont_write_bytecode = True
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from communication_contract import load_bundle, new_output, write_json, write_table, digest
from render_communication import check_figure_quality
from communication_figure_plan import build_plan, finish_plan, figure_families, table_families


def pages(values, size):
    return [values[i:i+size] for i in range(0, len(values), size)]


def order_lr_rows(rows, spec):
    """Display-only ordering; never replace native scores or infer significance."""
    lower = spec.get('direction') == 'lower'
    endpoint = spec.get('display_priority') == 'minimum_endpoint_mean'
    if endpoint and any(r.get(k) is None for r in rows for k in ('ligand_mean','receptor_mean')):
        raise ValueError('端点展示排序需要每个候选的两个实际均值')
    def key(r):
        primary = -min(r['ligand_mean'],r['receptor_mean']) if endpoint else (r['score'] if lower else -r['score'])
        from prioritize_communication import edge_key
        rank=spec.get('_evidence_rank',{}).get((r.get('condition','unspecified'),edge_key(r)),float('inf'))
        return (rank,primary,r['ligand'],r['receptor'],r.get('interaction',''),r['source'],r['target'])
    return sorted(rows,key=key)


def lr_selection_rule(spec):
    if spec.get('_evidence_rank'):
        return '先按本条件的研究对象匹配、独立供体支持及合格比例、样本支持排序，再按声明的原生分数或双端点均值中位数排序；选择证据另表保留。仅作描述性展示，不据此宣称条件特异或机制'
    if spec.get('display_priority') == 'minimum_endpoint_mean':
        return '按两个实际端点均值的较小值降序选择；这是明确声明的探索性展示规则，不是原生LR分数或条件特异性；点色仍保留原生存在标记'
    return '原生分数排序，仅为探索性绘图选择，不代表条件特异性'


def frame(title, projection=None):
    fig = plt.figure(figsize=(183/25.4, 150/25.4), layout="constrained")
    ax = fig.add_subplot(projection=projection)
    ax.set_title(title)
    return fig, ax


def spatial_frame(title, xy):
    import textwrap
    fig,ax=frame(title)
    span=np.ptp(np.asarray(xy),axis=0)
    if span[0]>0 and span[1]>0 and span[0]/span[1]<.65:
        fig.set_size_inches(89/25.4,150/25.4)
        ax.set_title('\n'.join(textwrap.wrap(title,width=40)))
    return fig,ax


def matrix_figure(rows, row_key, col_key, value_key, row_order, col_order, title, label, limits):
    values = np.full((len(row_order), len(col_order)), np.nan)
    seen = set()
    for row in rows:
        key = (row[row_key], row[col_key])
        if key in seen:
            raise ValueError("矩阵单元重复；需在上游定义聚合方式，绘图不自动取均值")
        seen.add(key)
        if key[0] in row_order and key[1] in col_order:
            values[row_order.index(key[0]), col_order.index(key[1])] = np.nan if row[value_key] is None else row[value_key]
    fig, ax = frame(title)
    # Small results should remain compact and numerically readable at print size.
    # More pixels cannot make a one-cell heatmap scientifically informative.
    width = 89 if len(col_order) <= 6 and max(map(len, row_order), default=0) < 24 else 183
    height = max(50, min(150, 28 + 5 * len(row_order) + min(25, max(map(len, col_order), default=0) * .5)))
    fig.set_size_inches(width/25.4, height/25.4)
    cmap = plt.get_cmap("RdBu_r" if limits[0] < 0 else "cividis").copy()
    cmap.set_bad("#dddddd")
    image = ax.pcolormesh(np.ma.masked_invalid(values), cmap=cmap, vmin=limits[0], vmax=limits[1])
    if values.size <= 36:
        for ri, ci in np.ndindex(values.shape):
            value = values[ri, ci]
            if np.isfinite(value):
                rgba = cmap(image.norm(value))
                ink = 'black' if sum(c*w for c, w in zip(rgba[:3], (.2126,.7152,.0722))) > .5 else 'white'
                ax.text(ci+.5, ri+.5, f'{value:.3g}', ha='center', va='center', color=ink, fontsize=6)
    ax.set_xticks(np.arange(len(col_order))+.5, col_order, rotation=55, ha="right")
    ax.set_yticks(np.arange(len(row_order))+.5, [x.replace(' | ','\n',1) for x in row_order])
    ax.invert_yaxis()
    fig.colorbar(image, ax=ax, label=label, shrink=.65)
    return fig


def run(bundle_path, output, plot_config=None):
    cfg, tables = load_bundle(bundle_path)
    overrides=json.loads(Path(plot_config).read_text()) if plot_config else {}
    allowed={'colors','top_lr','top_factor_features','focus'}
    if set(overrides)-allowed:raise ValueError('绘图覆盖配置含有非绘图字段，不能改变原生科学参数')
    cfg={**cfg,**overrides}
    out = new_output(output)
    write_json(out/'effective_plot_config.json',overrides)
    style_path=Path(__file__).resolve().parents[1] / "assets/communication-nature.mplstyle"
    plt.style.use(style_path)
    plt.rcParams["savefig.bbox"] = None
    shutil.copyfile(bundle_path, out / "input_bundle.json")
    state = dict(schema_version=2, dataset=cfg["dataset"], method=cfg["method"], figures=[],
                 selection=[], status="running", visual_review="pending", plan=[], figure_plan=build_plan(cfg,tables),
                 style=dict(applied_preset='communication-nature.mplstyle',sha256=digest(style_path),
                            external_skill_execution='not determined by renderer; verify orchestration log'))
    entities=sorted({r[k] for _,rs,_ in tables for r in rs for k in ('source','target','condition') if k in r})
    colors={name:matplotlib.colors.to_hex(plt.get_cmap('tab20')(i%20)) for i,name in enumerate(entities)}
    colors.update(cfg.get('colors',cfg['provenance'].get('parameters',{}).get('colors',{})))
    def color(name):
        for prefix in ('sender_ligand: ','receiver_receptor: ','ligand: ','receptor: ','target: '):
            if name.startswith(prefix) and name[len(prefix):] in colors:return colors[name[len(prefix):]]
        if name not in colors:
            colors[name] = matplotlib.colors.to_hex(plt.get_cmap("tab20")(len(colors)%20))
        return colors[name]
    def persist():
        write_json(out / "figure_manifest.json", state)
    def save(identifier, fig, source, caption):
        width_mm,height_mm=(float(x*25.4) for x in fig.get_size_inches())
        entry = dict(id=identifier, status="failed", source_data=source, files=[], caption=caption,
                     visual_review="pending", width_mm=width_mm, height_mm=height_mm,
                     families=figure_families(spec,identifier))
        try:
            # Matplotlib's constrained layout cannot size projected 3D axis
            # decorations reliably. Preserve the explicit 3D margins instead.
            if not any(ax.name == '3d' for ax in fig.axes):
                fig.set_layout_engine('constrained')
            for artist in fig.findobj():
                if hasattr(artist,'set_rasterized'):artist.set_rasterized(False)
            entry["technical_quality"] = check_figure_quality(fig)
            for ext in ("png", "pdf", "svg"):
                name = identifier+"."+ext
                # Native plot libraries may reset global savefig.bbox to "tight".
                # Keep actual exported dimensions equal to manifest dimensions.
                with plt.rc_context({'savefig.bbox':None,'svg.fonttype':'none','pdf.fonttype':42}):
                    save_figure(fig, out/name, dpi=600)
                entry["files"].append(name)
            preview=identifier+'.preview.png'
            fig.savefig(out/preview,dpi=120,bbox_inches=None)
            entry['preview']=preview
            entry["status"] = "generated"
        except Exception as error:
            entry["error"] = str(error)
        finally:
            plt.close(fig)
        state["figures"].append(entry)
        persist()
    persist()
    for spec, rows, source in tables:
        ident, kind, definition = spec["id"], spec["type"], spec["value_definition"]
        table_name = ident+".tsv"
        shutil.copyfile(source, out / table_name)
        state["plan"].append(dict(table=ident, result_type=kind))
        caption = f"{cfg['method']} {cfg['method_version']}; {definition}。来源和参数见 input_bundle.json；缺失为灰色/空位，不补零，不新增检验。"
        if not rows:
            state["figures"].append(dict(id=ident, status="not_applicable", families=sorted(table_families(spec,rows)),reason="原生结果为空；保留表头，不降低阈值凑图"))
            continue
        try:
            if kind in ("matrix", "patterns"):
                groups = sorted({r["dimension"] for r in rows}) if kind == "patterns" else ["matrix"]
                for gi, group in enumerate(groups):
                    rs = [r for r in rows if kind == "matrix" or r["dimension"] == group]
                    rk, ck = ("entity", "factor") if kind == "patterns" else ("row", "column")
                    rr, cc = sorted({r[rk] for r in rs}), sorted({r[ck] for r in rs})
                    if kind == 'matrix':
                        for key, observed in (('row_order',rr),('column_order',cc)):
                            if key in spec and set(spec[key])!=set(observed):
                                raise ValueError('显式行列顺序必须覆盖全部实测标签；不能静默丢行列')
                        rr,cc=spec.get('row_order',rr),spec.get('column_order',cc)
                    if kind == 'matrix' and spec.get('figure_role') == 'holonet_lr_qc':
                        expected=['Ligand detected fraction','Receptor detected fraction','Filtered nonzero cell edges','Filtered CE total']
                        if set(cc)!=set(expected):raise ValueError('HoloNet LR QC必须包含检测比例、边数和CE总量')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('HoloNet LR QC字段重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None or values[x]<0 for x in expected) for values in indexed.values()):
                            raise ValueError('HoloNet LR QC每个LR必须有完整非负值')
                        ordered=sorted(rr,key=lambda row:(-indexed[row]['Filtered CE total'],row))
                        shown=ordered[:int(spec.get('display_top_rows',min(20,len(ordered))))]
                        state['selection'].append(dict(table=ident,rows=shown,rule='按filtered CE total排序显示前列；检测比例、边数和CE总量使用独立坐标尺度，完整LR表保留'))
                        height=max(80,min(145,35+5.2*len(shown)))
                        fig,(left,middle,right)=plt.subplots(1,3,figsize=(183/25.4,height/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.25,1,1]})
                        fractions=np.array([[indexed[row][expected[0]],indexed[row][expected[1]]] for row in shown])
                        image=left.pcolormesh(fractions,cmap='Blues',vmin=0,vmax=1)
                        left.set_xticks([.5,1.5],['Ligand','Receptor'],rotation=0);left.set_yticks(np.arange(len(shown))+.5,shown)
                        left.set(xlabel='Detected cell fraction',title='Expression eligibility')
                        fig.colorbar(image,ax=left,label='Detected fraction',shrink=.65)
                        y=np.arange(len(shown))
                        edges=np.array([indexed[row]['Filtered nonzero cell edges'] for row in shown])
                        middle.hlines(y,0,edges,color='#4477AA',lw=.8);middle.scatter(edges,y,s=9,color='#4477AA',zorder=3)
                        middle.set_yticks(y,[]);middle.set(xlabel='Nonzero cell edges',title='Background-filtered edges')
                        totals=np.array([indexed[row]['Filtered CE total'] for row in shown])
                        right.hlines(y,0,totals,color='#AA3377',lw=.8);right.scatter(totals,y,s=9,color='#AA3377',zorder=3)
                        right.set_yticks(y,[]);right.set(xlabel='Filtered CE total',title='Within-LR CE total')
                        for ax in (left,middle,right):ax.set_ylim(len(shown)-.5,-.5)
                        save(ident+'_panels',fig,table_name,caption+'三个面板严格共享LR顺序，但检测比例、非零边数和CE总量各用独立坐标尺度，避免万级计数压扁0–1比例；CE仍只用于同一LR视图内描述，不据此跨数据集定量。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'holonet_dendrogram':
                        expected={'left_child','right_child','distance','leaf_count'}
                        if set(cc)!=expected:raise ValueError('HoloNet linkage必须包含左右子节点、距离和叶数')
                        labels=spec.get('leaf_labels')
                        if not isinstance(labels,list) or len(labels)<2 or len(set(labels))!=len(labels) or not all(isinstance(x,str) and x for x in labels):
                            raise ValueError('HoloNet dendrogram需要唯一非空leaf_labels')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('HoloNet linkage字段重复')
                            indexed[r['row']][r['column']]=r['value']
                        steps=sorted(indexed,key=lambda value:int(value))
                        if steps!=[str(i) for i in range(len(labels)-1)]:raise ValueError('HoloNet linkage步数不连续')
                        linkage=[]
                        for step in steps:
                            values=indexed[step]
                            if set(values)!=expected or any(values[x] is None for x in expected):raise ValueError('HoloNet linkage字段缺失')
                            left,right=values['left_child'],values['right_child']
                            i=int(step)
                            if left!=int(left) or right!=int(right) or min(left,right)<0 or max(left,right)>=len(labels)+i:
                                raise ValueError('HoloNet linkage子节点索引无效')
                            if values['distance']<0 or values['leaf_count']<2 or values['leaf_count']!=int(values['leaf_count']):
                                raise ValueError('HoloNet linkage距离或叶数无效')
                            linkage.append([left,right,values['distance'],values['leaf_count']])
                        from scipy.cluster.hierarchy import dendrogram
                        width=183 if len(labels)>10 else 120
                        fig,ax=plt.subplots(figsize=(width/25.4,max(65,min(120,42+2.4*len(labels)))/25.4),layout='constrained')
                        dendrogram(np.asarray(linkage,dtype=float),labels=labels,leaf_rotation=55,leaf_font_size=5,
                                   color_threshold=None,above_threshold_color='#555555',ax=ax)
                        ax.set(ylabel=spec.get('axis_label','Centrality-profile distance'),title=spec.get('title','HoloNet LR dendrogram'))
                        save(ident+'_tree',fig,table_name,caption+'按完整原生linkage重建树状图；枝长为中心性轮廓的聚类距离，叶顺序由层次聚类决定，不代表效应量或显著性。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'holonet_performance':
                        expected=['Cell type only','HoloNet CE + cell type','Difference']
                        if cc!=expected:raise ValueError('HoloNet性能比较必须提供基线、完整模型和差值')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('HoloNet目标性能字段重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None for x in expected) for values in indexed.values()):
                            raise ValueError('HoloNet每个目标必须具有完整的三项性能')
                        values=[v[x] for v in indexed.values() for x in expected[:2]]
                        low=min(values)-.05;high=max(values)+.05
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,76/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.15,1]})
                        for i,row in enumerate(rr):
                            x=indexed[row]['Cell type only'];y=indexed[row]['HoloNet CE + cell type']
                            left.scatter(x,y,s=18,color='#4477AA',edgecolors='white',linewidths=.3,zorder=3)
                            left.annotate(row,(x,y),xytext=(3,3 if i%2==0 else -7),textcoords='offset points',fontsize=5)
                        left.plot([low,high],[low,high],color='#999999',lw=.6,ls='--')
                        left.set(xlim=(low,high),ylim=(low,high),xlabel='Cell type only: Pearson r',ylabel='HoloNet CE + cell type: Pearson r',title='Whole-section prediction')
                        differences=[indexed[row]['Difference'] for row in rr]
                        bar_colors=['#228833' if value>=0 else '#CC6677' for value in differences]
                        right.barh(range(len(rr)),differences,color=bar_colors,height=.65)
                        right.set_yticks(range(len(rr)),rr);right.invert_yaxis();right.axvline(0,color='black',lw=.5)
                        right.set(xlabel='Correlation difference',title='HoloNet minus baseline')
                        save(ident+'_comparison',fig,table_name,caption+'左图复现作者“仅细胞类型 vs 加入CE”的相关散点逻辑；右图显式保留每个目标的正负差值。相关包含训练细胞，不能当作独立外部验证。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'holonet_attention':
                        if not cc or any(not column.startswith('repeat ') for column in cc):raise ValueError('HoloNet attention列必须是repeat编号')
                        repeats=sorted(cc,key=lambda column:int(column.split()[-1]))
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('HoloNet LR/repeat attention重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(repeats) or any(values[x] is None or not 0<=values[x]<=1 for x in repeats) for values in indexed.values()):
                            raise ValueError('HoloNet每个LR必须覆盖全部repeat且attention位于0–1')
                        ordered=sorted(rr,key=lambda row:(-np.mean([indexed[row][x] for x in repeats]),row))
                        shown=ordered[:int(spec.get('display_top_rows',min(15,len(ordered))))]
                        state['selection'].append(dict(table=ident,rows=shown,rule='按全部重复中min-max缩放绝对attention均值取前列；完整LR×重复表保留'))
                        matrix=np.array([[indexed[row][column] for column in repeats] for row in shown])
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,max(70,min(120,28+4.5*len(shown)))/25.4),layout='constrained',gridspec_kw={'width_ratios':[4.2,1.35]})
                        image=left.pcolormesh(matrix,cmap='Oranges',vmin=0,vmax=1)
                        step=max(1,len(repeats)//10);positions=np.arange(0,len(repeats),step)
                        left.set_xticks(positions+.5,[str(i+1) for i in positions],rotation=0);left.set_yticks(np.arange(len(shown))+.5,shown)
                        left.set_ylim(len(shown),0)
                        left.set(xlabel='Repeated initialization',title=spec.get('title','HoloNet LR attention'))
                        fig.colorbar(image,ax=left,label='Scaled absolute attention',shrink=.65)
                        means=matrix.mean(1);sds=matrix.std(1,ddof=1) if len(repeats)>1 else np.zeros(len(shown))
                        right.errorbar(means,range(len(shown)),xerr=sds,fmt='o',ms=3,color='#AA3377',ecolor='#777777',elinewidth=.7,capsize=2)
                        right.set_yticks(range(len(shown)),[]);right.invert_yaxis();right.set(xlim=(0,1),xlabel='Mean ± SD',title='Across repeats')
                        save(ident+'_rank',fig,table_name,caption+'复现作者LR attention热图与汇总排序形式；每次初始化先独立缩放至0–1，右侧为重复间均值±标准差，不是置信区间。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spacia_signal_effects':
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('Spacia response/signal effect重复')
                            if r['value'] is None or r.get('ci_low') is None or r.get('ci_high') is None or r['ci_low']>r['ci_high']:
                                raise ValueError('Spacia beta必须有有限均值和有序posterior quantiles')
                            indexed[r['row']][r['column']]=r
                        if any(set(values)!=set(cc) for values in indexed.values()):raise ValueError('Spacia每个response必须覆盖全部sender features')
                        matrix=np.array([[indexed[row][column]['value'] for column in cc] for row in rr])
                        bound=max(abs(matrix.min()),abs(matrix.max())) or 1
                        ranked=sorted((r for r in rs),key=lambda r:(0 if r['ci_low']>0 or r['ci_high']<0 else 1,-abs(r['value']),r['row'],r['column']))[:min(10,len(rs))]
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,max(72,min(125,42+5*max(len(rr),len(ranked))))/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.15,1.35]})
                        image=left.pcolormesh(matrix,cmap='RdBu_r',vmin=-bound,vmax=bound)
                        left.set_xticks(np.arange(len(cc))+.5,cc,rotation=55,ha='right');left.set_yticks(np.arange(len(rr))+.5,rr);left.invert_yaxis()
                        left.set(xlabel='Sender feature',ylabel='Receiver response',title=spec.get('title','Spacia sender-feature effects'))
                        for ri,row in enumerate(rr):
                            for ci,column in enumerate(cc):
                                result=indexed[row][column]
                                if result['ci_low']>0 or result['ci_high']<0:left.scatter(ci+.5,ri+.5,s=9,facecolors='none',edgecolors='black',linewidths=.55)
                        fig.colorbar(image,ax=left,label=spec.get('axis_label','Posterior mean beta'),shrink=.65)
                        for i,r in enumerate(ranked):
                            ink='#0072B2' if r['ci_low']>0 or r['ci_high']<0 else '#888888'
                            right.plot([r['ci_low'],r['ci_high']],[i,i],color=ink,lw=.8)
                            right.scatter(r['value'],i,s=14,color=ink,zorder=3)
                        right.set_yticks(range(len(ranked)),[r['row']+' ← '+r['column'] for r in ranked]);right.invert_yaxis();right.axvline(0,color='black',lw=.5)
                        right.set(xlabel='Posterior mean and 2.5–97.5% quantiles',title='Top fitted feature effects')
                        save(ident+'_effect_map',fig,table_name,caption+'左图显示全部有符号beta，空心圆表示原始MCMC链的2.5–97.5% posterior quantile区间未跨0；右图按区间是否跨0及绝对效应选择最多10项。该区间不代表跨供体置信区间。')
                        state['selection'].append(dict(table=ident,features=[r['row']+' ← '+r['column'] for r in ranked],rule='完整拟合后先列posterior区间未跨0项，再按绝对beta选择最多10项；完整矩阵保留'))
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spacia_distance_effects':
                        expected=['Mean distance coefficient','2.5% posterior quantile','97.5% posterior quantile','Posterior probability below zero']
                        if cc!=expected:raise ValueError('Spacia distance summary字段或顺序不符')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('Spacia distance summary重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None for x in expected) for values in indexed.values()):raise ValueError('Spacia distance summary不完整')
                        if any(not 0<=values[expected[3]]<=1 or values[expected[1]]>values[expected[2]] for values in indexed.values()):raise ValueError('Spacia distance posterior范围无效')
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,max(62,min(105,35+7*len(rr)))/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.45,.8]})
                        for i,row in enumerate(rr):
                            values=indexed[row];left.plot([values[expected[1]],values[expected[2]]],[i,i],color='#4477AA',lw=1)
                            left.scatter(values[expected[0]],i,s=18,color='#4477AA',zorder=3)
                        left.set_yticks(range(len(rr)),rr);left.invert_yaxis();left.axvline(0,color='black',lw=.5)
                        left.set(xlabel='Normalized-distance coefficient b.2',title='Posterior mean and 95% quantiles')
                        probabilities=[indexed[row][expected[3]] for row in rr]
                        right.barh(range(len(rr)),probabilities,color='#EEAA33',height=.62);right.set_yticks(range(len(rr)),[]);right.invert_yaxis();right.axvline(.5,color='#777777',lw=.5,ls='--')
                        right.set(xlim=(0,1),xlabel='P(b.2 < 0)',title='Closer-sender direction')
                        save(ident+'_forest',fig,table_name,caption+'b.2使用每个候选bag内归一化距离；左图区间为原始MCMC链的posterior quantiles，右图为负系数posterior比例。二者不是跨供体置信区间或因果检验。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spacia_fdr':
                        indexed=defaultdict(dict)
                        for r in rs:
                            threshold=float(r['row'])
                            if not 0<threshold<1 or threshold in indexed[r['column']]:raise ValueError('Spacia FDR阈值无效或重复')
                            if r['value'] is not None and not 0<=r['value']<=1:raise ValueError('Spacia Bayesian FDR不在[0,1]')
                            indexed[r['column']][threshold]=r['value']
                        fig,ax=plt.subplots(figsize=(89/25.4,68/25.4),layout='constrained')
                        curve_colors=plt.get_cmap('tab10')
                        for i,column in enumerate(cc):
                            series=sorted((x,y) for x,y in indexed[column].items() if y is not None)
                            if series:ax.plot([x for x,y in series],[y for x,y in series],marker='o',ms=2.5,lw=.8,color=curve_colors(i%10),label=column)
                        ax.set(xlim=(.08,.92),ylim=(0,1),xlabel='Primary-instance probability threshold',ylabel='Native Bayesian FDR',title=spec.get('title','Spacia primary-instance FDR'))
                        if len(cc)>1:ax.legend(frameon=False,fontsize=5)
                        save(ident+'_curves',fig,table_name,caption+'逐response显示上游0.1–0.9阈值的完整Bayesian FDR；没有入选primary instance而未定义的阈值保持空缺，不补为0或1。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spacia_psrf':
                        pairs=[r for r in rs if r['value'] is not None]
                        if any(r['value']<=0 for r in pairs):raise ValueError('Spacia PSRF必须为正数')
                        if not pairs:
                            fig,ax=frame(spec.get('title','Spacia beta convergence'));ax.set_axis_off();ax.text(.5,.5,'PSRF unavailable\nRun at least two chains',ha='center',va='center',transform=ax.transAxes)
                            save(ident+'_unavailable',fig,table_name,caption+'所有PSRF均缺失；通常表示仅运行一条链，不补造收敛诊断。')
                            continue
                        ordered=sorted(pairs,key=lambda r:(-r['value'],r['row'],r['column']))
                        fig,ax=plt.subplots(figsize=(183/25.4,max(60,min(150,25+5*len(ordered)))/25.4),layout='constrained')
                        values=[r['value'] for r in ordered];labels=[r['row']+' ← '+r['column'] for r in ordered]
                        inks=['#CC6677' if value>1.1 else '#228833' for value in values]
                        ax.hlines(range(len(values)),1,values,color=inks,lw=.8);ax.scatter(values,range(len(values)),s=14,color=inks,zorder=3)
                        ax.set_yticks(range(len(labels)),labels);ax.invert_yaxis()
                        if max(values)>1.1:
                            ax.axvline(1.1,color='#777777',lw=.6,ls='--')
                        else:
                            span=max(values)-min(values) or .002
                            ax.set_xlim(min(.998,min(values)-.15*span),max(values)+.2*span)
                            ax.text(.99,.03,'All fitted beta PSRF < 1.1',ha='right',va='bottom',fontsize=6,transform=ax.transAxes)
                        ax.set(xlabel=spec.get('axis_label','PSRF'),title=spec.get('title','Spacia beta convergence'))
                        save(ident+'_diagnostic',fig,table_name,caption+'显示全部原生beta PSRF；虚线1.1是诊断参考线，超过者保留为红色并视为收敛警报，不因效应显著而忽略。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spacia_mcmc_trace':
                        if any(r['value'] is None for r in rs):raise ValueError('Spacia MCMC trace含缺失值')
                        indexed=defaultdict(dict)
                        for r in rs:
                            draw=int(r['row'])
                            if draw<1 or draw in indexed[r['column']]:raise ValueError('Spacia MCMC trace抽样位置无效或重复')
                            indexed[r['column']][draw]=r['value']
                        fig,ax=plt.subplots(figsize=(89/25.4,65/25.4),layout='constrained')
                        for i,column in enumerate(cc):
                            series=sorted(indexed[column].items())
                            ax.plot([x for x,y in series],[y for x,y in series],lw=.55,alpha=.8,label=column)
                        ax.axhline(0,color='#999999',lw=.5);ax.set(xlabel='Retained post-warmup draw index',ylabel=spec.get('axis_label','Native coefficient'),title=spec.get('title','Spacia MCMC trace'))
                        if len(cc)>1:ax.legend(frameon=False,fontsize=5,ncol=2)
                        save(ident+'_chains',fig,table_name,caption+'每条链独立去除第一个存储初值后按固定步长减绘图密度；不平滑、不拼接链，完整原始链保留在native_results。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spaci_lr_scores':
                        expected=['Latent cosine similarity','Predicted at configured threshold','Raw expression correlation']
                        if cc!=expected:raise ValueError('spaCI LR分数必须包含cosine、调用和原始相关')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('spaCI候选LR字段重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None for x in expected) or values[expected[1]] not in (0,1) for values in indexed.values()):
                            raise ValueError('spaCI候选LR字段缺失或二元调用无效')
                        ordered=sorted(rr,key=lambda row:(-indexed[row][expected[0]],row))
                        cosine=np.array([indexed[row][expected[0]] for row in ordered]);raw=np.array([indexed[row][expected[2]] for row in ordered])
                        called=np.array([bool(indexed[row][expected[1]]) for row in ordered])
                        threshold=float(cfg['provenance']['parameters']['prediction_threshold'])
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,75/25.4),layout='constrained')
                        left.scatter(raw[~called],cosine[~called],s=5,color='#BBBBBB',alpha=.55,label='Not called')
                        left.scatter(raw[called],cosine[called],s=5,color='#4477AA',alpha=.45,label='Called')
                        left.axhline(threshold,color='#CC6677',lw=.7,ls='--');left.axvline(0,color='#999999',lw=.45)
                        left.set(xlabel='Raw expression Pearson r',ylabel='Latent cosine similarity',title='Embedding versus observed correlation')
                        left.legend(frameon=False,fontsize=6)
                        right.plot(np.arange(1,len(cosine)+1),cosine,color='#4477AA',lw=.8)
                        right.axhline(threshold,color='#CC6677',lw=.7,ls='--',label=f'Threshold {threshold:g}')
                        right.set(xlabel='Candidate rank',ylabel='Latent cosine similarity',title=f'{called.sum()}/{len(called)} candidates called')
                        right.legend(frameon=False,fontsize=6)
                        save(ident+'_calibration',fig,table_name,caption+'左图完整显示原始表达相关与模型嵌入cosine；右图显示全部候选排序及预声明阈值。蓝点仅表示超过阈值，没有P值或独立真值；高调用率作为低区分度证据原样保留。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spaci_training_history':
                        if cc!=['loss','F1']:raise ValueError('spaCI训练历史必须包含loss和F1')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[int(r['row'])][r['column']]=r['value']
                        epochs=sorted(indexed)
                        if epochs!=list(range(1,max(epochs)+1)) or any(set(indexed[e])!=set(cc) for e in epochs):raise ValueError('spaCI训练历史不连续或字段缺失')
                        fig,left=plt.subplots(figsize=(89/25.4,68/25.4),layout='constrained');right=left.twinx()
                        a=left.plot(epochs,[indexed[e]['loss'] for e in epochs],marker='o',ms=2.5,lw=.8,color='#4477AA',label='Triplet loss')
                        b=right.plot(epochs,[indexed[e]['F1'] for e in epochs],marker='s',ms=2.5,lw=.8,color='#CC6677',label='Validation F1')
                        best=max(epochs,key=lambda e:(indexed[e]['F1'],-e));left.axvline(best,color='#777777',lw=.55,ls='--')
                        left.set(xlabel='Epoch',ylabel='Mean triplet loss',title='spaCI training and checkpoint selection');right.set_ylabel('Expression-derived validation F1')
                        left.legend(a+b,[x.get_label() for x in a+b],frameon=False,fontsize=6,loc='best')
                        save(ident+'_curves',fig,table_name,caption+f'显示每轮实际训练loss和表达衍生验证F1；虚线为首个最高F1的epoch {best}。验证标签来自同一数据的相关规则，不是独立生化真值。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spaci_validation':
                        if rr!=['best checkpoint']:raise ValueError('spaCI验证指标只接受最佳checkpoint一行')
                        values={r['column']:r['value'] for r in rs}
                        counts=['TP','TN','FP','FN'];rates=['Accuracy','Precision','Recall','Specificity','F1']
                        if set(values)!=set(counts+rates) or any(values[x] is None or values[x]<0 for x in counts) or any(values[x] is None or not 0<=values[x]<=1 for x in rates):raise ValueError('spaCI验证指标缺失或范围无效')
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,70/25.4),layout='constrained')
                        left.bar(counts,[values[x] for x in counts],color=['#4477AA','#228833','#EE6677','#CCBB44']);left.set(ylabel='Gene-pair count',title='Expression-derived confusion counts')
                        right.barh(range(len(rates)),[values[x] for x in rates],color='#4477AA');right.set_yticks(range(len(rates)),rates);right.invert_yaxis();right.set(xlim=(0,1),xlabel='Metric value',title='Best-checkpoint metrics')
                        save(ident+'_summary',fig,table_name,caption+'正负类均由发布版高/低表达相关规则生成；该图检验训练流程一致性，不能当作独立LR数据库准确率。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spaci_threshold_sensitivity':
                        if cc!=['Predicted LR pairs']:raise ValueError('spaCI阈值敏感性字段不符')
                        series=sorted((float(r['row']),r['value']) for r in rs)
                        if any(x<=0 or x>=1 or y is None or y<0 for x,y in series):raise ValueError('spaCI阈值敏感性范围无效')
                        fig,ax=plt.subplots(figsize=(89/25.4,65/25.4),layout='constrained')
                        ax.plot([x for x,y in series],[y for x,y in series],marker='o',ms=3,lw=.8,color='#4477AA')
                        configured=float(cfg['provenance']['parameters']['prediction_threshold']);ax.axvline(configured,color='#CC6677',lw=.7,ls='--')
                        ax.set(xlabel='Cosine threshold',ylabel='Called candidate LR pairs',title='spaCI threshold sensitivity')
                        save(ident+'_curve',fig,table_name,caption+'同一完整候选集在固定0.1–0.9显示阈值下的调用数量；竖线为分析前配置阈值。曲线只诊断阈值敏感性，不据结果选择阈值。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') in ('stmlnet_lrtg_importance','stmlnet_regulator_importance'):
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('stMLnet重要性矩阵单元重复')
                            if r['value'] is None or not np.isfinite(r['value']):raise ValueError('stMLnet重要性必须为有限原生值')
                            indexed[r['row']][r['column']]=r['value']
                        ordered=sorted(rr,key=lambda row:(-max(abs(v) for v in indexed[row].values()),row))
                        shown_rows=ordered[:int(spec.get('display_top_rows',min(24,len(ordered))))]
                        column_scores={column:max((abs(indexed[row][column]) for row in shown_rows if column in indexed[row]),default=-1) for column in cc}
                        shown_columns=sorted(cc,key=lambda column:(-column_scores[column],column))[:int(spec.get('display_top_columns',min(20,len(cc))))]
                        state['selection'].append(dict(table=ident,rows=shown_rows,columns=shown_columns,rule='按每个模型和分子在完整原生矩阵中的最大绝对importance选择展示行列；保留负值，完整矩阵另表交付'))
                        selected=[indexed[row][column] for row in shown_rows for column in shown_columns if column in indexed[row]]
                        limit=max(max(map(abs,selected),default=0),1e-12)
                        heatmap_label='LR–target importance' if spec.get('figure_role')=='stmlnet_lrtg_importance' else 'Regulator importance'
                        fig=matrix_figure(rs,'row','column','value',shown_rows,shown_columns,spec.get('title','stMLnet model importance'),heatmap_label,(-limit,limit))
                        save(ident+'_heatmap',fig,table_name,caption+'热图按绝对原生importance筛选展示，色标以0为中心并保留负值；缺失格表示该LR或调控分子未进入对应靶基因模型。')
                        entries=sorted(((abs(value),value,row,column) for row,values in indexed.items() for column,value in values.items()),key=lambda x:(-x[0],x[2],x[3]))[:20]
                        labels=[f'{column} — {row.replace(" | ", " / ", 1)}' for _,_,row,column in entries]
                        values=[value for _,value,_,_ in entries]
                        fig,ax=plt.subplots(figsize=(183/25.4,max(75,min(155,35+5.3*len(entries)))/25.4),layout='constrained')
                        y=np.arange(len(entries));ax.barh(y,values,color=['#CC6677' if value>=0 else '#4477AA' for value in values],height=.68)
                        ax.set_yticks(y,labels);ax.invert_yaxis();ax.axvline(0,color='black',lw=.55)
                        ax.set(xlabel=spec.get('axis_label','Native importance'),title='Largest absolute stMLnet importances')
                        save(ident+'_waterfall',fig,table_name,caption+'瀑布图显示完整原生表中绝对值最大的20个模型—分子组合；红/蓝只区分正负，负值不被删除，也不代表统计显著。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'stmlnet_model_quality':
                        expected=['Receiver cells','LR predictors','OOB MSE','OOB R-squared']
                        if cc!=expected:raise ValueError('stMLnet模型质量必须包含固定四项指标')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('stMLnet模型质量字段重复')
                            if r['value'] is None or not np.isfinite(r['value']):raise ValueError('stMLnet模型质量含非有限值')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or values['Receiver cells']<10 or values['Receiver cells']!=int(values['Receiver cells']) or values['LR predictors']<2 or values['LR predictors']!=int(values['LR predictors']) or values['OOB MSE']<0 for values in indexed.values()):
                            raise ValueError('stMLnet模型质量字段缺失或范围无效')
                        shown=sorted(rr,key=lambda row:(-indexed[row]['OOB R-squared'],row))[:int(spec.get('display_top_rows',min(30,len(rr))))]
                        state['selection'].append(dict(table=ident,rows=shown,rule='按原生ranger OOB R-squared降序显示；负值完整保留，全部模型质量表另行交付'))
                        height=max(75,min(160,35+5*len(shown)))
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,height/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.35,1]})
                        r2=np.array([indexed[row]['OOB R-squared'] for row in shown]);y=np.arange(len(shown))
                        left.barh(y,r2,color=['#228833' if value>=0 else '#CC6677' for value in r2],height=.68);left.axvline(0,color='black',lw=.55)
                        left.set_yticks(y,[row.replace(' | ','\n',1) for row in shown]);left.invert_yaxis();left.set(xlabel='OOB R-squared',title='Target model performance')
                        predictors=np.array([indexed[row]['LR predictors'] for row in shown]);mse=np.array([indexed[row]['OOB MSE'] for row in shown])
                        points=right.scatter(predictors,r2,c=mse,cmap='viridis_r',s=20,edgecolors='white',linewidths=.35)
                        right.axhline(0,color='#777777',lw=.55,ls='--');right.set(xlabel='LR predictors',ylabel='OOB R-squared',title='Complexity and OOB error')
                        fig.colorbar(points,ax=right,label='OOB MSE',shrink=.65)
                        save(ident+'_diagnostic',fig,table_name,caption+'左图保留每个靶基因模型的正负OOB R-squared；右图同时显示LR预测变量数与OOB MSE。OOB来自同一切片细胞，不等于独立供体验证。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'stmlnet_distance_sensitivity':
                        prefix='coordinate × '
                        if any(not column.startswith(prefix) for column in cc):raise ValueError('stMLnet坐标敏感性列名无效')
                        factors={column:float(column[len(prefix):]) for column in cc}
                        native_columns=[column for column,value in factors.items() if np.isclose(value,1)]
                        if len(native_columns)!=1 or any(not np.isfinite(value) or value<=0 for value in factors.values()):raise ValueError('stMLnet坐标敏感性必须包含唯一factor=1及正有限因子')
                        native_column=native_columns[0];indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('stMLnet坐标敏感性矩阵单元重复')
                            if r['value'] is None or not np.isfinite(r['value']) or r['value']<0:raise ValueError('stMLnet坐标敏感性必须为有限非负值')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(cc) for values in indexed.values()):raise ValueError('stMLnet每个LR必须覆盖全部坐标因子')
                        shown=sorted(rr,key=lambda row:(-indexed[row][native_column],row))[:int(spec.get('display_top_rows',min(30,len(rr))))]
                        ordered_columns=sorted(cc,key=lambda column:factors[column]);ordered_factors=[factors[column] for column in ordered_columns]
                        state['selection'].append(dict(table=ident,rows=shown,columns=ordered_columns,rule='按factor=1的原生LR活性降序显示；因子顺序按数值排列，其他因子不参与候选选择'))
                        width=89 if len(shown)<=8 else 183
                        fig,ax=plt.subplots(figsize=(width/25.4,max(72,min(120,42+2.1*len(shown)))/25.4),layout='constrained')
                        for i,row in enumerate(shown):
                            base=indexed[row][native_column]
                            if base>0:ax.plot(ordered_factors,[indexed[row][column]/base for column in ordered_columns],lw=.65,alpha=.65,label=row if len(shown)<=8 else None)
                        ax.axhline(1,color='#777777',lw=.55,ls='--');ax.axvline(1,color='#CC6677',lw=.55,ls='--');ax.set_xscale('log')
                        ax.set(xlabel='Coordinate scale factor',ylabel='Activity relative to factor 1',title='stMLnet distance-scale sensitivity')
                        if len(shown)<=8:ax.legend(frameon=False,fontsize=5)
                        save(ident+'_curves',fig,table_name,caption+'保持表达、细胞和多层候选不变，仅缩放坐标后重算1/d活性；每条曲线除以自身factor=1值，虚线1表示原生尺度。')
                        relative=[]
                        for row in shown:
                            base=indexed[row][native_column]
                            for column in ordered_columns:relative.append(dict(row=row,column=column,value=None if base<=0 or indexed[row][column]<=0 else np.log2(indexed[row][column]/base)))
                        finite=[r['value'] for r in relative if r['value'] is not None];limit=max(max(map(abs,finite),default=0),1e-12)
                        fig=matrix_figure(relative,'row','column','value',shown,ordered_columns,'Relative activity after coordinate rescaling','log2(activity / native activity)',(-limit,limit))
                        save(ident+'_relative_heatmap',fig,table_name,caption+'相对热图显示log2(缩放后活性/factor=1活性)，以0为中心；它诊断坐标单位依赖，不改变或替代原生结果。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cscp_consensus':
                        if rr!=cc:raise ValueError('CSCP共识矩阵行列细胞必须完全一致')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('CSCP共识矩阵单元重复')
                            if r['value'] is None or not 0<=r['value']<=1:raise ValueError('CSCP共识比例必须在0–1')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(rr) for values in indexed.values()):raise ValueError('CSCP共识矩阵不完整')
                        values=np.array([[indexed[row][column] for column in cc] for row in rr])
                        if not np.allclose(values,values.T,atol=1e-12) or not np.allclose(np.diag(values),1,atol=1e-12):raise ValueError('CSCP共识矩阵必须对称且对角为1')
                        group=lambda label:' '.join(label.split(' | ')[:2]).title()
                        groups=[]
                        for i,label in enumerate(rr):
                            name=group(label)
                            if not groups or groups[-1][0]!=name:groups.append([name,i,i])
                            else:groups[-1][2]=i
                        fig,ax=plt.subplots(figsize=(183/25.4,150/25.4),layout='constrained')
                        image=ax.pcolormesh(values,cmap='cividis',vmin=0,vmax=1,rasterized=False)
                        centers=[(start+end+1)/2 for _,start,end in groups];labels=[name for name,_,_ in groups]
                        ax.set_xticks(centers,labels,rotation=35,ha='right');ax.set_yticks(centers,labels);ax.set_ylim(len(rr),0)
                        for _,start,end in groups[1:]:ax.axhline(start,color='white',lw=.7);ax.axvline(start,color='white',lw=.7)
                        ax.set(xlabel='Selected cells grouped by final paired subgroup',ylabel='Selected cells grouped by final paired subgroup',title='CSCP five-restart consensus')
                        fig.colorbar(image,ax=ax,label='Co-clustering proportion',shrink=.65)
                        save(ident+'_heatmap',fig,table_name,caption+'每个domain×最终pair按原始顺序最多显示20个细胞；粗分隔线标记配对亚群，完整细胞×细胞共识矩阵由结果包provenance定位。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'deepcolor_colocalization_matrix':
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']] or r['value'] is None or not np.isfinite(r['value']):raise ValueError('DeepCOLOR类型共定位矩阵必须唯一、完整且有限')
                            indexed[r['row']][r['column']]=r['value']
                        if rr!=cc or any(set(values)!=set(cc) for values in indexed.values()):raise ValueError('DeepCOLOR类型共定位矩阵行列必须同序且完整')
                        values=np.array([[indexed[row][column] for column in cc] for row in rr])
                        if not np.allclose(values,values.T,atol=1e-10):raise ValueError('DeepCOLOR类型共定位矩阵必须对称')
                        limit=max(float(np.max(np.abs(values))),1e-12)
                        fig,ax=plt.subplots(figsize=(183/25.4,max(78,28+8*len(rr))/25.4),layout='constrained')
                        image=ax.pcolormesh(values,cmap='RdBu_r',vmin=-limit,vmax=limit,rasterized=False)
                        ax.set_xticks(np.arange(len(cc))+.5,cc,rotation=35,ha='right');ax.set_yticks(np.arange(len(rr))+.5,rr);ax.set_ylim(len(rr),0)
                        for i in range(len(rr)):
                            for j in range(len(cc)):
                                ax.text(j+.5,i+.5,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=5,
                                        color='white' if abs(values[i,j])/limit>.62 else 'black')
                        ax.set(xlabel='Cell type',ylabel='Cell type',title='DeepCOLOR inferred colocalization')
                        fig.colorbar(image,ax=ax,label=spec.get('axis_label','Mean native log2 colocalization'),shrink=.72)
                        save(ident+'_heatmap',fig,table_name,caption+'使用以0为中心、按矩阵最大绝对值对称的色标并逐格标注原生群均值；同群均值已排除细胞自身项。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'deepcolor_mapping_qc':
                        expected=['Total native spot contribution','Spatial entropy (bits)'];indexed=defaultdict(dict);celltypes={}
                        for r in rs:
                            if r['column'] in indexed[r['row']] or r['value'] is None or not np.isfinite(r['value']) or r['value']<0:raise ValueError('DeepCOLOR细胞映射QC必须唯一、有限且非负')
                            indexed[r['row']][r['column']]=r['value'];celltypes[r['row']]=r.get('cell_type')
                        if set(cc)!=set(expected) or any(set(values)!=set(expected) for values in indexed.values()) or any(not value for value in celltypes.values()):raise ValueError('DeepCOLOR细胞映射QC字段不完整')
                        groups=sorted(set(celltypes.values()))
                        fig,axes=plt.subplots(1,2,figsize=(183/25.4,max(80,28+7*len(groups))/25.4),layout='constrained')
                        palette=['#4477AA','#EE6677','#228833','#CCBB44','#66CCEE','#AA3377','#BBBBBB','#332288']
                        for ax,metric in zip(axes,expected):
                            values=[[indexed[cell][metric] for cell in rr if celltypes[cell]==group] for group in groups]
                            artists=ax.boxplot(values,orientation='horizontal',tick_labels=groups,patch_artist=True,widths=.58,showfliers=False,
                                               medianprops={'color':'black','linewidth':.8},whiskerprops={'linewidth':.6},capprops={'linewidth':.6})
                            for box,color_value in zip(artists['boxes'],palette):box.set_facecolor(color_value);box.set_alpha(.72)
                            ax.set(xlabel=metric,title='Contribution' if metric.startswith('Total') else 'Spatial dispersion')
                        save(ident+'_distributions',fig,table_name,caption+'按输入细胞类型并列显示全部单细胞的原生spot贡献与行归一化空间熵；箱线图隐藏离群点符号仅为避免遮挡，完整数值保留在源表。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'deepcolor_training':
                        phases=['Single-cell phase','Spatial phase']
                        if set(cc)!=set(phases) or any(r['value'] is None or not np.isfinite(r['value']) or r['value']<0 for r in rs):raise ValueError('DeepCOLOR训练记录必须包含两阶段有限非负损失')
                        fig,axes=plt.subplots(1,2,figsize=(183/25.4,72/25.4),layout='constrained')
                        phase_colors=['#4477AA','#EE6677']
                        for ax,phase,color_value in zip(axes,phases,phase_colors):
                            records=sorted((r for r in rs if r['column']==phase),key=lambda r:float(r['row']))
                            if not records:raise ValueError('DeepCOLOR训练阶段没有记录')
                            x=[float(r['row']) for r in records];y=[r['value'] for r in records]
                            ax.plot(x,y,marker='o',ms=2.8,lw=.9,color=color_value);ax.set(xlabel='Epoch',ylabel='Native validation loss',title=phase)
                            ax.text(.98,.05,f'{y[0]:.3g} → {y[-1]:.3g}',transform=ax.transAxes,ha='right',fontsize=6)
                        save(ident+'_phases',fig,table_name,caption+'两个训练阶段使用各自的原生损失轴，避免空间阶段的较大数值压平单细胞阶段；不跨阶段比较绝对损失。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'deepcolor_diagnostics':
                        if cc!=['Value'] or any(r['value'] is None or not np.isfinite(r['value']) or r['value']<0 for r in rs):raise ValueError('DeepCOLOR数值诊断必须是单列有限非负值')
                        indexed={r['row']:r['value'] for r in rs};counts=['Single cells','Spatial spots','Genes','High colocalization pairs (>1)'];errors=['p_mat max row-sum error','map2sc max spot-sum error']
                        if set(indexed)!=set(counts+errors):raise ValueError('DeepCOLOR数值诊断字段不完整')
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,72/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.55,1]})
                        values=[indexed[name] for name in counts];y=np.arange(len(counts));left.barh(y,values,color=['#4477AA','#66CCEE','#228833','#CCBB44'],height=.62);left.set_yticks(y,counts);left.invert_yaxis();left.set(xlabel='Observed count',title='Input and selected pairs')
                        for yi,value in enumerate(values):left.text(value,yi,f' {value:,.0f}',va='center',fontsize=5)
                        right.set_axis_off();right.text(.5,.78,'Probability conservation',ha='center',fontsize=7)
                        right.text(.5,.54,f"Cell → spots row error\n{indexed[errors[0]]:.3g}",ha='center',va='center',fontsize=6,color='#AA3377')
                        right.text(.5,.24,f"Spot → cells row error\n{indexed[errors[1]]:.3g}",ha='center',va='center',fontsize=6,color='#AA3377')
                        save(ident+'_audit',fig,table_name,caption+'输入和固定阈值细胞对使用线性计数轴；两种概率归一化最大误差单独显示，避免与计数共用色标。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'deepcolor_pair_eligibility':
                        if cc!=['Eligible high-colocalization pairs'] or any(r['value'] is None or r['value']<0 or r['value']!=int(r['value']) for r in rs):raise ValueError('DeepCOLOR双细胞资格必须是非负整数计数')
                        shown=sorted(rs,key=lambda r:(-r['value'],r['row']));fig,ax=plt.subplots(figsize=(89/25.4,max(50,24+7*len(shown))/25.4),layout='constrained')
                        y=np.arange(len(shown));values=[r['value'] for r in shown];ax.barh(y,values,color='#CCBB44',height=.6);ax.set_yticks(y,[r['row'] for r in shown]);ax.invert_yaxis();ax.set(xlabel='Eligible high-colocalization pairs',title='Pair-clustering eligibility')
                        for yi,value in enumerate(values):ax.text(value,yi,f' {value:,.0f}',va='center',fontsize=5)
                        save(ident+'_counts',fig,table_name,caption+'显示每个预声明查询在固定共定位>1阈值下的实际细胞对数量；少于3时不强制UMAP或聚类。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'mdic3_celltype_matrix':
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('MDIC3细胞类型矩阵单元重复')
                            if r['value'] is None or r['value']<0:indexed[r['row']][r['column']]=r['value']
                            else:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(cc) or any(value is None or not np.isfinite(value) or value<0 for value in values.values()) for values in indexed.values()):raise ValueError('MDIC3细胞类型矩阵必须完整、有限且非负')
                        values=np.array([[indexed[row][column] for column in cc] for row in rr])
                        low=float(values.min());high=float(values.max());high=high if high>low else low+1
                        fig,ax=plt.subplots(figsize=(183/25.4,max(76,25+8*len(rr))/25.4),layout='constrained')
                        image=ax.pcolormesh(values,cmap='cividis',vmin=low,vmax=high,rasterized=False)
                        ax.set_xticks(np.arange(len(cc))+.5,cc,rotation=35,ha='right');ax.set_yticks(np.arange(len(rr))+.5,rr);ax.set_ylim(len(rr),0)
                        for i in range(len(rr)):
                            for j in range(len(cc)):
                                midpoint=(values[i,j]-low)/(high-low)
                                ax.text(j+.5,i+.5,f'{values[i,j]:.2f}',ha='center',va='center',fontsize=5,color='white' if midpoint<.42 else 'black')
                        ax.set(xlabel='Receiver cell type',ylabel='Sender cell type',title='MDIC3 cell-type communication')
                        fig.colorbar(image,ax=ax,label=spec.get('axis_label','Native log10 grouped score'),shrink=.72)
                        save(ident+'_heatmap',fig,table_name,caption+'色标按本矩阵实测最小值与最大值展开，并逐格标注原生log10分数；不把细微色差称为显著性。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'mdic3_roles':
                        expected=['Outgoing raw sum','Incoming raw sum'];indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if set(cc)!=set(expected) or any(set(values)!=set(expected) or any(value is None or not np.isfinite(value) or value<0 for value in values.values()) for values in indexed.values()):raise ValueError('MDIC3角色表必须含完整非负收发总量')
                        shown=sorted(rr,key=lambda row:-(indexed[row][expected[0]]+indexed[row][expected[1]]))
                        fig,ax=plt.subplots(figsize=(183/25.4,max(70,28+7*len(shown))/25.4),layout='constrained');y=np.arange(len(shown));height=.34
                        ax.barh(y-height/2,[indexed[row][expected[0]] for row in shown],height,color='#4477AA',label='Outgoing')
                        ax.barh(y+height/2,[indexed[row][expected[1]] for row in shown],height,color='#CC6677',label='Incoming')
                        ax.set_yticks(y,shown);ax.invert_yaxis();ax.set(xlabel=spec.get('axis_label','Raw grouped MDIC3 sum'),title='MDIC3 sender and receiver roles');ax.legend(frameon=False,fontsize=6)
                        ax.ticklabel_format(axis='x',style='sci',scilimits=(0,0))
                        save(ident+'_roles',fig,table_name,caption+'发送和接收总量在同一原生线性尺度并列显示；总量受各细胞类型细胞数影响，不是中心性P值。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'mdic3_cell_matrix':
                        if rr!=cc:raise ValueError('MDIC3展示细胞矩阵行列必须一致')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(cc) or any(value is None or not np.isfinite(value) or value<0 for value in values.values()) for values in indexed.values()):raise ValueError('MDIC3展示细胞矩阵必须完整、有限且非负')
                        values=np.array([[indexed[row][column] for column in cc] for row in rr]);positive=values[values>0]
                        if not len(positive):raise ValueError('MDIC3展示细胞矩阵没有正值')
                        cmap=matplotlib.colormaps['cividis'].with_extremes(bad='#E6E6E6')
                        masked=np.ma.masked_less_equal(values,0);norm=matplotlib.colors.LogNorm(vmin=float(positive.min()),vmax=float(positive.max()))
                        fig,ax=plt.subplots(figsize=(183/25.4,165/25.4),layout='constrained');image=ax.pcolormesh(masked,cmap=cmap,norm=norm,rasterized=False)
                        group=lambda label:label.split(' | ',1)[0];groups=[]
                        for i,label in enumerate(rr):
                            name=group(label)
                            if not groups or groups[-1][0]!=name:groups.append([name,i,i])
                            else:groups[-1][2]=i
                        centers=[(start+end+1)/2 for _,start,end in groups];names=[name for name,_,_ in groups]
                        ax.set_xticks(centers,names,rotation=35,ha='right');ax.set_yticks(centers,names);ax.set_ylim(len(rr),0)
                        for _,start,_ in groups[1:]:ax.axhline(start,color='white',lw=.7);ax.axvline(start,color='white',lw=.7)
                        ax.set(xlabel='Top receiving cells grouped by supplied type',ylabel='Top sending cells grouped by supplied type',title='MDIC3 high-activity cellular submatrix')
                        fig.colorbar(image,ax=ax,label='Native cellular score (log color scale)',shrink=.7)
                        save(ident+'_heatmap',fig,table_name,caption+'从完整矩阵按发送加接收总量预选前列细胞，再按输入细胞类型分组；灰色为原生0，正值仅在颜色上取对数以显示动态范围，源表不变。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'mdic3_diagnostics':
                        if cc!=['Value'] or any(r['value'] is None or not np.isfinite(r['value']) or r['value']<0 for r in rs):raise ValueError('MDIC3数值诊断必须是单列完整非负值')
                        indexed={r['row']:r['value'] for r in rs};counts=['Native cells','Native genes','Cell matrix nonzero','Cell matrix zero'];error='Type reconstruction max error'
                        if set(indexed)!=set(counts+[error]):raise ValueError('MDIC3数值诊断字段不完整')
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,72/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.5,1]})
                        y=np.arange(len(counts));values=[indexed[x] for x in counts];left.barh(y,values,color=['#4477AA','#66CCEE','#228833','#BBBBBB'],height=.65);left.set_yticks(y,counts);left.invert_yaxis();left.set_xscale('log');left.set(xlabel='Observed count (log scale)',title='Input and matrix size')
                        for yi,value in enumerate(values):left.text(value,yi,f' {value:,.0f}',va='center',fontsize=5)
                        right.set_axis_off();right.text(.5,.64,'Cell-type reconstruction',ha='center',fontsize=7);right.text(.5,.44,f"max |error|\n{indexed[error]:.3g}",ha='center',va='center',fontsize=7,color='#AA3377')
                        save(ident+'_audit',fig,table_name,caption+'规模计数使用对数轴；细胞到细胞类型矩阵的重建误差单独显示，避免与百万级计数共用色标。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'variance_signature':
                        components=['Residual noise','Intrinsic effect','Environmental effect','Cell-cell interactions']
                        if cc!=components:raise ValueError('SVCA方差签名必须提供固定四分量及其显式顺序')
                        indexed=defaultdict(dict);metadata={}
                        for r in rs:
                            if r['value'] is None or not 0<=r['value']<=1:raise ValueError('SVCA方差份额必须是[0,1]有限值')
                            if r['column'] in indexed[r['row']]:raise ValueError('SVCA同一行方差分量重复')
                            indexed[r['row']][r['column']]=r['value']
                            metadata.setdefault(r['row'],(r.get('sample',r['row']),r.get('feature',r['row'])))
                        if any(set(values)!=set(components) or not np.isclose(sum(values.values()),1,atol=1e-8) for values in indexed.values()):
                            raise ValueError('SVCA每个样本/特征必须有四分量且总和为1')
                        maximum=int(spec.get('display_top_rows',len(rr)))
                        ordered=sorted(rr,key=lambda row:(-indexed[row]['Cell-cell interactions'],row))
                        shown=ordered[:maximum]
                        state['selection'].append(dict(table=ident,rows=shown,
                            rule='按Cell-cell interactions原生方差份额降序显示前列；完整四分量表保留'))
                        palette={'Residual noise':'#999999','Intrinsic effect':'#4477AA',
                                 'Environmental effect':'#228833','Cell-cell interactions':'#EEAA33'}
                        fig,ax=plt.subplots(figsize=(183/25.4,max(75,min(190,35+4.7*len(shown)))/25.4))
                        fig.subplots_adjust(left=.16,right=.98,bottom=.22,top=.63)
                        left=np.zeros(len(shown))
                        for component in components:
                            values=np.array([indexed[row][component] for row in shown])
                            ax.barh(range(len(shown)),values,left=left,color=palette[component],label=component,height=.72)
                            left+=values
                        ax.set_yticks(range(len(shown)),[row.replace(' | ',' — ',1) for row in shown]);ax.invert_yaxis()
                        ax.set(xlim=(0,1),xlabel='Fraction of modeled variance')
                        fig.suptitle(spec.get('title','SVCA variance signatures'),y=.96,fontsize=7)
                        handles,labels=ax.get_legend_handles_labels()
                        fig.legend(handles,labels,frameon=False,ncol=2,fontsize=6,loc='upper center',bbox_to_anchor=(.5,.84))
                        save(ident+'_stacked',fig,table_name,caption+'复现作者堆叠方差签名逻辑；每行严格和为1，并按交互分量排序显示。')
                        fig,ax=plt.subplots(figsize=(89/25.4,80/25.4),layout='constrained')
                        distributions=[[indexed[row][component] for row in rr] for component in components]
                        violin_positions=[];violin_values=[]
                        for i,values in enumerate(distributions):
                            if len(values)>=3 and len(set(values))>1:violin_positions.append(i);violin_values.append(values)
                        if violin_values:
                            parts=ax.violinplot(violin_values,positions=violin_positions,widths=.75,showextrema=False)
                            for body,i in zip(parts['bodies'],violin_positions):body.set_facecolor(palette[components[i]]);body.set_alpha(.22)
                        for i,values in enumerate(distributions):
                            if len(values)>=5:ax.boxplot([values],positions=[i],widths=.38,showfliers=False,
                                medianprops={'color':'black','linewidth':.8},boxprops={'linewidth':.6},
                                whiskerprops={'linewidth':.6},capprops={'linewidth':.6})
                            else:ax.hlines(float(np.median(values)),i-.18,i+.18,color='black',lw=.8)
                            jitter=np.linspace(-.09,.09,len(values)) if len(values)>1 else np.array([0.0])
                            ax.scatter(i+jitter,values,s=7,color=palette[components[i]],alpha=.65,zorder=3)
                        ax.set_xticks(range(4),['Residual\nnoise','Intrinsic','Environmental','Cell-cell\ninteractions'])
                        ax.set(ylabel='Fraction of modeled variance',ylim=(0,1),title='Distribution across fitted sample–features')
                        save(ident+'_violin',fig,table_name,caption+'复现作者分量分布图；点为实际样本–特征，至少5点显示箱体，至少3个非常数值显示小提琴。')
                        features=sorted({feature for sample,feature in metadata.values()})
                        ranked_features=sorted(features,key=lambda feature:(-max(indexed[row]['Cell-cell interactions'] for row in rr if metadata[row][1]==feature),feature))[:15]
                        fig,ax=plt.subplots(figsize=(183/25.4,95/25.4),layout='constrained')
                        offsets=np.linspace(-.27,.27,4)
                        for ci,component in enumerate(components):
                            for fi,feature in enumerate(ranked_features):
                                values=[indexed[row][component] for row in rr if metadata[row][1]==feature]
                                x=fi+offsets[ci]
                                if len(values)>=2:ax.boxplot([values],positions=[x],widths=.14,showfliers=False,
                                    patch_artist=True,boxprops={'facecolor':palette[component],'alpha':.35,'linewidth':.5},
                                    medianprops={'color':'black','linewidth':.6},whiskerprops={'linewidth':.5},capprops={'linewidth':.5})
                                ax.scatter(x+np.linspace(-.025,.025,len(values)),values,s=5,color=palette[component],zorder=3)
                        ax.set_xticks(range(len(ranked_features)),ranked_features,rotation=45,ha='right')
                        ax.set(ylabel='Fraction of modeled variance',ylim=(0,1),title='Variance signatures by feature')
                        handles=[Line2D([0],[0],marker='s',ls='',color=palette[c],label=c) for c in components]
                        ax.legend(handles=handles,frameon=False,ncol=2,fontsize=6)
                        save(ident+'_feature_box',fig,table_name,caption+'复现作者按分子特征分组的箱线逻辑；前15项按交互份额排序，多样本时箱体汇总图像，单样本时只显示真实点。')
                        bound=1
                        fig=matrix_figure(rs,'row','column','value',shown,components,'SVCA normalized variance signature',
                                          'Fraction of modeled variance',(0,bound))
                        save(ident+'_heatmap',fig,table_name,caption+'补充热图使用与堆叠图相同的完整四分量值和选择顺序。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'spatial_scale_profile':
                        indexed=defaultdict(dict)
                        for r in rs:
                            try:scale=float(r['row'])
                            except ValueError as error:raise ValueError('SVCA长度网格行标必须是正数') from error
                            if not np.isfinite(scale) or scale<=0:raise ValueError('SVCA长度网格必须有限且为正')
                            if scale in indexed[r['column']]:raise ValueError('SVCA同一目标的长度网格点重复')
                            indexed[r['column']][scale]=r['value']
                        fig,ax=plt.subplots(figsize=((183 if len(cc)>4 else 89)/25.4,78/25.4),layout='constrained')
                        curve_cmap=plt.get_cmap('tab10')
                        for i,column in enumerate(cc):
                            series=sorted((scale,value) for scale,value in indexed[column].items() if value is not None)
                            if not series:continue
                            ax.plot([x for x,y in series],[y for x,y in series],marker='o',ms=2,lw=.8,
                                    color=curve_cmap(i%10),label=column.replace(' | ',' — '))
                            best=min(series,key=lambda item:item[1])
                            ax.scatter([best[0]],[best[1]],s=24,facecolors='none',edgecolors=curve_cmap(i%10),lw=.8,zorder=3)
                        ax.set_xscale('log');ax.set(xlabel='Candidate spatial length ('+spec.get('coordinate_unit','declared units')+')',
                            ylabel=spec.get('axis_label','Native objective'),title=spec.get('title','SVCA spatial-length selection'))
                        if len(cc)>1:ax.legend(frameon=False,fontsize=5,ncol=2)
                        save(ident+'_curve',fig,table_name,caption+'按实际正长度使用对数横轴；空心圆为每个目标原生目标函数最小的候选尺度，失败网格点保持缺失。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'nested_cross_validation':
                        models=['Intrinsic effect','+ Environmental effect','+ Cell-cell interactions']
                        if cc!=models:raise ValueError('SVCA嵌套交叉验证必须提供固定三个模型及其显式顺序')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['column'] in indexed[r['row']]:raise ValueError('SVCA同一目标/模型交叉验证R²重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(models) for values in indexed.values()):raise ValueError('SVCA交叉验证每行须包含三个嵌套模型')
                        fig,ax=plt.subplots(figsize=(89/25.4,82/25.4),layout='constrained')
                        model_colors=['#4477AA','#228833','#EEAA33']
                        for i,model in enumerate(models):
                            values=[indexed[row][model] for row in rr if indexed[row][model] is not None]
                            if not values:continue
                            mean=float(np.mean(values));sd=float(np.std(values,ddof=1)) if len(values)>1 else 0
                            ax.bar(i,mean,color=model_colors[i],alpha=.45,width=.65)
                            ax.errorbar(i,mean,yerr=sd,fmt='none',ecolor='black',elinewidth=.7,capsize=2)
                            ax.scatter(i+np.linspace(-.09,.09,len(values)),values,s=8,color=model_colors[i],zorder=3)
                        ax.axhline(0,color='black',lw=.5);ax.set_xticks(range(3),['Intrinsic','+ Environmental','+ Cell-cell\ninteractions'])
                        ax.set(ylabel='Out-of-fold R²',title='SVCA nested predictive performance')
                        save(ident+'_summary',fig,table_name,caption+'复现作者嵌套模型平均R²图并叠加全部实际样本–特征点；误差线为样本–特征间标准差，负R²不截零。')
                        finite=[r['value'] for r in rs if r['value'] is not None]
                        bound=max(map(abs,finite)) if finite else 1
                        fig=matrix_figure(rs,'row','column','value',rr,models,'SVCA nested cross-validation','Out-of-fold R²',(-bound,bound))
                        save(ident+'_heatmap',fig,table_name,caption+'完整样本–特征嵌套模型R²热图；负值表示不如折外均值基线。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'rank_comparison':
                        expected={'expression_PI_rank','spatial_PI_rank'}
                        if set(cc)!=expected:raise ValueError('表达–空间秩比较必须且只能包含两列配对秩')
                        indexed=defaultdict(dict)
                        for r in rs:
                            if r['value'] is None:raise ValueError('配对秩不能缺失')
                            if r['column'] in indexed[r['row']]:raise ValueError('同一候选的配对秩重复')
                            indexed[r['row']][r['column']]=r['value']
                        if any(set(v)!=expected for v in indexed.values()):raise ValueError('每个候选必须同时提供表达秩和空间秩')
                        pairs=[(v['expression_PI_rank'],v['spatial_PI_rank']) for v in indexed.values()]
                        counts=defaultdict(int)
                        for pair in pairs:counts[pair]+=1
                        rank_rows=[dict(expression_rank=x,spatial_rank=y,count=count) for (x,y),count in sorted(counts.items())]
                        rank_source=ident+'_rank_counts.tsv';write_table(out/rank_source,rank_rows)
                        maximum=max(max(x,y) for x,y in pairs);maximum_count=max(counts.values())
                        fig,ax=plt.subplots(figsize=(89/25.4,75/25.4),layout='constrained')
                        points=ax.scatter([x for x,y in counts],[y for x,y in counts],
                            s=[8+42*count/maximum_count for count in counts.values()],c=list(counts.values()),
                            cmap='cividis',vmin=1,vmax=maximum_count,edgecolors='none')
                        ax.plot([1,maximum],[1,maximum],color='#777777',lw=.6,ls='--')
                        ax.set(xlabel='Expression PI rank',ylabel='Spatial PI rank',title='Spatial vs expression rank')
                        ax.invert_xaxis();ax.invert_yaxis();fig.colorbar(points,ax=ax,label='Candidate count',shrink=.65)
                        save(ident+'_rank_map',fig,rank_source,caption+'在每个LR内部比较细胞对的原生PI秩；点面积和颜色为该秩组合的候选数，虚线为相同秩。')
                        spatial_top=[x for x,y in pairs if y==1]
                        if spatial_top:
                            recovery=[]
                            for k in range(1,int(maximum)+1):
                                recovery.append(dict(expression_rank_included=k,
                                    expression_rank_percent=100*k/maximum,
                                    spatial_top_rank_recovered_percent=100*sum(x<=k for x in spatial_top)/len(spatial_top)))
                            recovery_source=ident+'_recovery.tsv';write_table(out/recovery_source,recovery)
                            fig,ax=plt.subplots(figsize=(89/25.4,65/25.4),layout='constrained')
                            ax.plot([r['expression_rank_percent'] for r in recovery],
                                    [r['spatial_top_rank_recovered_percent'] for r in recovery],color='#4477AA',lw=1)
                            ax.plot([0,100],[0,100],color='#999999',lw=.6,ls='--')
                            ax.set(xlim=(0,100),ylim=(0,100),xlabel='% expression rank included',
                                   ylabel='% highest spatial rank recovered',title='Recovery of spatial top ranks')
                            save(ident+'_recovery',fig,recovery_source,caption+'严格复现Giotto plotRecovery的spatial ground-truth定义：仅取每个LR的空间PI秩1，再计算纳入表达秩前k位时的累计恢复率；虚线为对角参考。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_graph_qc':
                        expected=['Spatial observations','Measured genes','Reference observations','Reference cell types',
                                  'Candidate ligand-target pairs','Effective ligand-target scores','Graph directed entries including self',
                                  'Median neighbors including self','Activity domains','De novo programs']
                        if rr!=['Renoir run'] or cc!=expected:raise ValueError('Renoir graph QC字段或顺序不完整')
                        indexed={r['column']:r['value'] for r in rs}
                        if any(indexed.get(key) is None or indexed[key]<0 for key in expected):raise ValueError('Renoir graph QC必须是完整非负值')
                        panels=[('Measured input',expected[:4]),('Molecular eligibility',expected[4:6]),
                                ('Spatial graph',expected[6:8]),('Derived structure',expected[8:])]
                        fig,axes=plt.subplots(1,4,figsize=(183/25.4,82/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.25,1,1,1]})
                        for ax,(title,labels) in zip(axes,panels):
                            values=[indexed[label] for label in labels];y=np.arange(len(labels))
                            ax.barh(y,values,color=['#4477AA','#66CCEE','#228833','#CCBB44'][:len(labels)],height=.62)
                            ax.set_yticks(y,[textwrap.fill(label,18) for label in labels]);ax.invert_yaxis();ax.set_title(title);ax.set_xlabel('Observed value')
                            for yi,value in enumerate(values):ax.text(value,yi,f' {value:,.0f}' if value==int(value) else f' {value:.2f}',va='center',fontsize=5)
                            ax.set_xlim(0,max(values or [1])*1.28 or 1)
                        save(ident+'_eligibility',fig,table_name,caption+'输入、候选资格、空间图和下游结构使用独立坐标尺度；它们是执行审计计数，不表示通讯强度。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_pair_summary':
                        expected=['Nonzero observations','Mean neighborhood score','Median neighborhood score','Maximum neighborhood score']
                        if cc!=expected:raise ValueError('Renoir pair summary字段或顺序不完整')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None or values[x]<0 for x in expected) for values in indexed.values()):raise ValueError('Renoir pair summary必须完整非负')
                        shown=sorted(rr,key=lambda row:(-indexed[row]['Mean neighborhood score'],row))[:20]
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,max(75,min(150,35+5*len(shown)))/25.4),layout='constrained',gridspec_kw={'width_ratios':[.9,1.5]})
                        y=np.arange(len(shown));left.barh(y,[indexed[row]['Nonzero observations'] for row in shown],color='#4477AA',height=.65)
                        left.set_yticks(y,[textwrap.fill(row,25) for row in shown]);left.set(xlabel='Observations with score > 0',title='Spatial prevalence')
                        metrics=expected[1:];offsets=np.linspace(-.24,.24,len(metrics));symbols=['o','s','^'];palette=['#228833','#CCBB44','#AA3377']
                        for offset,metric,symbol,ink in zip(offsets,metrics,symbols,palette):
                            values=[indexed[row][metric] for row in shown];right.scatter(values,y+offset,s=12,marker=symbol,color=ink,label=metric.replace(' neighborhood score',''))
                        right.set_yticks(y,[]);right.set(xlabel='Native neighborhood score',title='Within-run score summaries');right.legend(frameon=False,fontsize=6)
                        for ax in (left,right):ax.set_ylim(len(shown)-.5,-.5)
                        state['selection'].append(dict(table=ident,rows=shown,rule='按完整候选的平均neighborhood score显示前20；完整表保留'))
                        save(ident+'_evidence',fig,table_name,caption+'空间非零观察数与原生分数汇总分轴显示；分数只在本次图和资源内排序，不能跨数据集比较。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_domain_pair_activity':
                        if any(r['value'] is None or r['value']<0 for r in rs):raise ValueError('Renoir domain activity必须完整非负')
                        bound=max(r['value'] for r in rs) or 1
                        fig=matrix_figure(rs,'row','column','value',rr,cc,spec.get('title','Renoir domain activity profiles'),'Mean neighborhood score',(0,bound))
                        save(ident+'_heatmap',fig,table_name,caption+'显示每个原生活性域的未缩放ligand→target平均分数；列按全体观察的平均分数预先排序，不做显著性筛选。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_domain_evidence':
                        expected=['Wilcoxon score','Log fold change','P value','BH adjusted P','Within-domain nonzero fraction','Outside-domain nonzero fraction']
                        if cc!=expected:raise ValueError('Renoir domain evidence字段或顺序不完整')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) for values in indexed.values()):raise ValueError('Renoir domain evidence行不完整')
                        domains=list(dict.fromkeys(row.split(' | ',1)[0] for row in rr))
                        for page,domain_name in enumerate(domains,1):
                            shown=[row for row in rr if row.startswith(domain_name+' | ')]
                            fig,axes=plt.subplots(1,3,figsize=(183/25.4,max(72,35+6*len(shown))/25.4),layout='constrained',gridspec_kw={'width_ratios':[1.1,.8,1.1]})
                            y=np.arange(len(shown));score=[indexed[row]['Wilcoxon score'] for row in shown]
                            axes[0].hlines(y,0,score,color=['#4477AA' if value>=0 else '#CC6677' for value in score],lw=.8);axes[0].scatter(score,y,s=8,color=['#4477AA' if value>=0 else '#CC6677' for value in score])
                            axes[0].axvline(0,color='black',lw=.5);axes[0].set_yticks(y,[textwrap.fill(row.split(' | ',1)[1],25) for row in shown]);axes[0].set(xlabel='Cell/spot-level Wilcoxon score',title=domain_name)
                            q=[indexed[row]['BH adjusted P'] for row in shown];qplot=[-np.log10(max(value,1e-300)) if value is not None else np.nan for value in q]
                            valid=[i for i,value in enumerate(qplot) if np.isfinite(value)];axes[1].barh(valid,[qplot[i] for i in valid],color='#AA3377',height=.58);axes[1].set_yticks(y,[]);axes[1].set_xlabel('−log10(BH adjusted P)')
                            within=[indexed[row]['Within-domain nonzero fraction'] for row in shown];outside=[indexed[row]['Outside-domain nonzero fraction'] for row in shown]
                            axes[2].scatter(within,y-.12,s=9,color='#228833',label='Within domain');axes[2].scatter(outside,y+.12,s=9,color='#BBBBBB',label='Outside domain')
                            for yi,a,b in zip(y,within,outside):axes[2].plot([a,b],[yi-.12,yi+.12],color='#999999',lw=.4)
                            axes[2].set(xlim=(0,1),xlabel='Observations with score > 0');axes[2].set_yticks(y,[]);axes[2].legend(frameon=False,fontsize=6)
                            for ax in axes:ax.set_ylim(len(shown)-.5,-.5)
                            save(f'{ident}_{page}',fig,table_name,caption+f'{domain_name}单独成页；效应秩、同一切片内的BH证据与域内外非零比例分轴保留。这些细胞/spot级P值不是供体层推断，也不证明条件特异性。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_program_activity':
                        if any(r['value'] is None or r['value']<0 for r in rs):raise ValueError('Renoir program activity必须完整非负')
                        bound=max(r['value'] for r in rs) or 1
                        fig=matrix_figure(rs,'row','column','value',rr,cc,spec.get('title','Renoir de novo program activity'),'Absolute first-SVD activity',(0,bound))
                        save(ident+'_heatmap',fig,table_name,caption+'使用原生downstream_analysis缩放前的绝对第一SVD分量并按域取均值；绝对值会丢失符号，程序是相关性簇而非通路富集。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'renoir_stability':
                        if rr!=cc or any(r['value'] is None or not -1<=r['value']<=1 for r in rs):raise ValueError('Renoir stability必须是完整对称相关矩阵')
                        fig=matrix_figure(rs,'row','column','value',rr,cc,spec.get('title','Renoir score stability'),'Spearman correlation',(-1,1))
                        save(ident+'_heatmap',fig,table_name,caption+'每个格子比较全部观察×全部有效ligand→target分数；固定−1到1色标，评估上游零表达随机保护的影响。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_graph_qc':
                        expected=['Measured cells','Measured genes','Database LR overlapping measured genes','Active graph LR pairs',
                                  'Candidate directed cell-LR edges','Selected native top-percent edges','Two-hop relay instances']
                        if rr!=['Input graph'] or cc!=expected:raise ValueError('CellNEST graph QC字段或顺序不完整')
                        indexed={r['column']:r['value'] for r in rs}
                        if any(indexed.get(key) is None or indexed[key]<0 for key in expected):raise ValueError('CellNEST graph QC必须是完整非负计数')
                        panels=[('Measured input',expected[:2]),('Molecular eligibility',expected[2:4]),('Graph and relay output',expected[4:])]
                        fig,axes=plt.subplots(1,3,figsize=(183/25.4,76/25.4),layout='constrained',gridspec_kw={'width_ratios':[1,1,1.35]})
                        for ax,(title,labels) in zip(axes,panels):
                            values=[indexed[label] for label in labels];y=np.arange(len(labels))
                            ax.barh(y,values,color=['#4477AA','#66CCEE','#AA3377'][:len(labels)],height=.65)
                            ax.set_yticks(y,[textwrap.fill(label,22) for label in labels]);ax.invert_yaxis();ax.set_title(title);ax.set_xlabel('Observed count')
                            for yi,value in enumerate(values):ax.text(value,yi,f' {value:,.0f}',va='center',fontsize=5)
                            ax.set_xlim(0,max(values or [1])*1.22 or 1)
                        save(ident+'_eligibility',fig,table_name,caption+'输入规模、分子资格和图输出分面使用各自计数尺度；这是逐步筛选审计，不把较大的候选边数解释为更强通讯。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_celltype_roles':
                        expected=['Outgoing edge count','Incoming edge count','Outgoing attention sum','Incoming attention sum']
                        if set(cc)!=set(expected):raise ValueError('CellNEST角色表必须包含收发计数与attention总和')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) or any(values[x] is None or values[x]<0 for x in expected) for values in indexed.values()):raise ValueError('CellNEST角色表不完整')
                        shown=sorted(rr,key=lambda x:-(indexed[x]['Outgoing edge count']+indexed[x]['Incoming edge count']))[:20]
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,max(65,min(135,35+5*len(shown)))/25.4),layout='constrained')
                        y=np.arange(len(shown));height=.34
                        for ax,columns,title,xlabel in [(left,expected[:2],'Selected edge abundance','Selected cell-LR edges'),(right,expected[2:],'Integrated attention mass','Within-graph attention sum')]:
                            ax.barh(y-height/2,[indexed[row][columns[0]] for row in shown],height,color='#4477AA',label='Outgoing')
                            ax.barh(y+height/2,[indexed[row][columns[1]] for row in shown],height,color='#CC6677',label='Incoming')
                            ax.set_yticks(y,shown if ax is left else []);ax.invert_yaxis();ax.set(xlabel=xlabel,title=title);ax.legend(frameon=False,fontsize=6)
                        save(ident+'_roles',fig,table_name,caption+'发送和接收分别显示；边数与图内缩放的attention总和分面，不混用数值轴，也不把一个切片的角色当作群体效应。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_lr_summary':
                        expected=['Candidate edge count','Selected edge count','Selected attention sum','Selected median attention']
                        if cc!=expected:raise ValueError('CellNEST LR汇总字段或顺序不完整')
                        indexed=defaultdict(dict)
                        for r in rs:indexed[r['row']][r['column']]=r['value']
                        if any(set(values)!=set(expected) for values in indexed.values()):raise ValueError('CellNEST LR汇总行不完整')
                        shown=sorted(rr,key=lambda row:(-(indexed[row]['Selected edge count'] or 0),-(indexed[row]['Selected attention sum'] or 0),row))[:20]
                        fig,axes=plt.subplots(1,3,figsize=(183/25.4,max(70,min(145,38+4.8*len(shown)))/25.4),layout='constrained')
                        y=np.arange(len(shown));height=.34
                        axes[0].barh(y-height/2,[indexed[x]['Candidate edge count'] for x in shown],height,color='#BBBBBB',label='Candidate')
                        axes[0].barh(y+height/2,[indexed[x]['Selected edge count'] for x in shown],height,color='#4477AA',label='Selected')
                        axes[0].set_yticks(y,shown);axes[0].legend(frameon=False,fontsize=6);axes[0].set_xlabel('Cell-edge count')
                        axes[1].barh(y,[indexed[x]['Selected attention sum'] for x in shown],color='#AA3377',height=.65);axes[1].set_xlabel('Selected attention sum');axes[1].set_yticks(y,[])
                        med=[indexed[x]['Selected median attention'] for x in shown];valid=[i for i,v in enumerate(med) if v is not None]
                        axes[2].hlines(valid,0,[med[i] for i in valid],color='#228833',lw=.8);axes[2].scatter([med[i] for i in valid],valid,color='#228833',s=10);axes[2].set_xlabel('Selected median attention');axes[2].set_yticks(y,[])
                        for ax in axes:ax.set_ylim(len(shown)-.5,-.5)
                        state['selection'].append(dict(table=ident,rows=shown,rule='按selected cell-edge count、attention sum与LR名称显示前20；完整LR表保留'))
                        save(ident+'_evidence',fig,table_name,caption+'候选边、入选边、attention总和与中位数保留独立坐标尺度；attention只在本图内排序，不作跨数据集强度比较。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_stability':
                        if cc!=['Layer 1','Layer 2']:raise ValueError('CellNEST稳定性需要两层attention')
                        finite=[r['value'] for r in rs if r['value'] is not None]
                        if not finite:
                            fig,ax=frame(spec.get('title','CellNEST attention stability'));ax.set_axis_off();ax.text(.5,.5,'One run: stability is not estimable',ha='center',va='center')
                            save(ident+'_unavailable',fig,table_name,caption+'只有一次训练时不能估计跨种子稳定性；缺失不补零。');continue
                        fig=matrix_figure(rs,'row','column','value',rr,cc,spec.get('title','CellNEST attention stability'),'Spearman correlation',(-1,1))
                        save(ident+'_heatmap',fig,table_name,caption+'每个格子使用完整未归一化attention向量的跨种子Spearman相关；固定−1到1色标并保留负相关。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_loss':
                        if any(r['value'] is None for r in rs):raise ValueError('CellNEST loss记录缺失')
                        fig,ax=plt.subplots(figsize=(183/25.4,76/25.4),layout='constrained')
                        for column in cc:
                            series=sorted((r for r in rs if r['column']==column),key=lambda r:float(r['row']))
                            ax.plot([float(r['row']) for r in series],[r['value'] for r in series],lw=.75,label=column)
                        ax.set(xlabel='Training epoch',ylabel='Native DGI loss',title=spec.get('title','CellNEST DGI training loss'));ax.legend(frameon=False,fontsize=6,ncol=min(3,len(cc)))
                        save(ident+'_curves',fig,table_name,caption+'绘制每次固定种子训练保存的全部loss检查点；不平滑、不选最佳运行，loss收敛不等于生物学验证。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_attention_distribution':
                        if cc!=['Integrated attention'] or any(r['value'] is None for r in rs):raise ValueError('CellNEST attention分布必须完整')
                        ordered=sorted(rs,key=lambda r:float(r['row']))
                        selected=[str(r.get('selected','')).casefold() in ('true','1') for r in ordered]
                        fig,(left,right)=plt.subplots(1,2,figsize=(183/25.4,72/25.4),layout='constrained')
                        values=np.array([r['value'] for r in ordered]);left.hist(values,bins=min(50,max(10,int(np.sqrt(len(values))))),color='#BBBBBB',edgecolor='white',linewidth=.2)
                        left.set(xlabel='Integrated attention',ylabel='Eligible cell-LR edges',title='Complete graph distribution')
                        ranks=np.array([float(r['row']) for r in ordered]);right.scatter(ranks[~np.array(selected)],values[~np.array(selected)],s=2,color='#BBBBBB',alpha=.55,label='Not selected')
                        right.scatter(ranks[np.array(selected)],values[np.array(selected)],s=3,color='#AA3377',alpha=.75,label='Native top-percent')
                        right.set(xlabel='Native integrated edge rank',ylabel='Integrated attention',title='Selection boundary');right.legend(frameon=False,fontsize=6)
                        save(ident+'_selection',fig,table_name,caption+'左图保留全部合格边分布，右图按原生rank标示精确top-percent成员；不把图内缩放attention解释为概率或跨数据集效应量。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_relay_counts':
                        finite=[r for r in rs if r['value'] is not None]
                        if not finite:
                            fig,ax=frame(spec.get('title','CellNEST two-hop relay abundance'));ax.set_axis_off();ax.text(.5,.5,'No eligible two-hop relay',ha='center',va='center')
                            save(ident+'_unavailable',fig,table_name,caption+'当前原生入选边没有合格i→j→k两跳；保留阴性结果，不降低选择阈值。');continue
                        shown=sorted(finite,key=lambda r:(-r['value'],r['row']))[:20];fig,ax=plt.subplots(figsize=(183/25.4,max(65,min(150,35+5.2*len(shown)))/25.4),layout='constrained')
                        y=np.arange(len(shown));ax.barh(y,[r['value'] for r in shown],color='#4477AA',height=.65);ax.set_yticks(y,[textwrap.fill(r['row'],44) for r in shown]);ax.invert_yaxis();ax.set(xlabel='Two-hop graph instances',title=spec.get('title','CellNEST two-hop relay abundance'))
                        state['selection'].append(dict(table=ident,rows=[r['row'] for r in shown],rule='按两跳实例数显示前20；完整relay表保留'))
                        save(ident+'_ranking',fig,table_name,caption+'计数单位是同一空间图中的两跳实例，不是独立供体；排序仅描述重复图结构。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_relay_roles':
                        if cc!=['Sender','Intermediate','Receiver']:raise ValueError('CellNEST relay角色需要发送、中继、接收三列')
                        if any(r['value'] is None or not 0<=r['value']<=1 for r in rs):raise ValueError('CellNEST relay角色比例必须位于0到1')
                        fig=matrix_figure(rs,'row','column','value',rr,cc,spec.get('title','CellNEST relay cell-type roles'),'Within-position fraction',(0,1))
                        save(ident+'_heatmap',fig,table_name,caption+'每列分别按该relay的全部实例标准化为1，显示细胞类型在发送、中继、接收位置的构成；同一实例并非独立样本。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'cellnest_relay_confidence':
                        finite=[r for r in rs if r['value'] is not None]
                        if not finite:
                            fig,ax=frame(spec.get('title','CellNEST relay prior support'));ax.set_axis_off();ax.text(.5,.5,'No eligible prior path',ha='center',va='center')
                            save(ident+'_unavailable',fig,table_name,caption+'固定PPI/GRN先验中没有可评分路径；缺失不补零。');continue
                        shown=sorted(finite,key=lambda r:(-r['value'],r['row']))[:20];fig,ax=plt.subplots(figsize=(183/25.4,max(65,min(150,35+5.2*len(shown)))/25.4),layout='constrained')
                        y=np.arange(len(shown));values=[r['value'] for r in shown];ax.hlines(y,0,values,color='#AA3377',lw=.9);ax.scatter(values,y,color='#AA3377',s=13);ax.set_yticks(y,[textwrap.fill(r['row'],44) for r in shown]);ax.invert_yaxis();ax.set(xlabel='PPI × GRN prior confidence',title=spec.get('title','CellNEST relay prior support'))
                        save(ident+'_ranking',fig,table_name,caption+f'只显示可评分的前{len(shown)}项；完整表保留缺失路径。该分数是固定先验支持，不是实验验证、P值或因果证据。')
                        continue
                    if kind == 'matrix' and spec.get('figure_role') == 'convergence':
                        if any(r['value'] is None for r in rs):raise ValueError('优化曲线缺失目标值，需先核查原生运行记录')
                        steps=[float(r['row']) for r in rs]
                        if any(not np.isfinite(v) or v<0 or v!=int(v) for v in steps):raise ValueError('优化曲线行标须为实际非负迭代次数')
                        if len({(r['row'],r['column']) for r in rs})!=len(rs):raise ValueError('优化曲线迭代/运行重复')
                        fig,ax=plt.subplots(figsize=(89/25.4,65/25.4),layout='constrained')
                        for column in cc:
                            series=sorted((r for r in rs if r['column']==column),key=lambda r:float(r['row']))
                            ax.plot([float(r['row']) for r in series],[r['value'] for r in series],lw=.9,label=column)
                        ax.set(xlabel='Iteration',ylabel=spec.get('axis_label','Native objective'),title=spec.get('title',ident.replace('_',' ')))
                        if len(cc)>1:ax.legend(frameon=False,fontsize=6)
                        save(ident+'_curve',fig,table_name,caption+'绘制全部已提供的原生迭代记录；记录频率依来源契约，不插补未保存步骤、不平滑，不将优化收敛等同模型或生物学验证。')
                        continue
                    if kind == "matrix" and spec.get("display_top_rows"):
                        ranked=sorted((r for r in rs if r['value'] is not None),key=lambda r:r['value'],reverse=spec.get('direction')!='lower')
                        rr=list(dict.fromkeys(r[rk] for r in ranked))[:int(spec['display_top_rows'])]
                        state['selection'].append(dict(table=ident,rows=rr,rule='按声明数值方向选取显示行；完整表保留'))
                    if kind == 'matrix' and spec.get('display_top_columns'):
                        ranked_columns=sorted(cc,key=lambda col:(-max([abs(r['value']) for r in rs if r[ck]==col and r['value'] is not None] or [0]),col))
                        cc=ranked_columns[:int(spec['display_top_columns'])]
                        state['selection'].append(dict(table=ident,columns=cc,rule='按列最大绝对值选取显示列；完整表保留，不改变原生筛选'))
                    if kind == "patterns" and group != "sample":
                        chosen = set()
                        for factor in cc:
                            fs = sorted([r for r in rs if r[ck] == factor and r["value"] is not None], key=lambda r: -abs(r["value"]))
                            chosen.update(r[rk] for r in fs[:cfg.get("top_factor_features",12)])
                        rr = [r for r in rr if r in chosen]
                        state["selection"].append(dict(table=ident,dimension=group,entities=rr,rule="每因子按绝对载荷选前12项（可配置），完整载荷保留原表"))
                    finite = [r["value"] for r in rs if r["value"] is not None]
                    if not finite:
                        fig,ax=frame(group);ax.set_axis_off()
                        ax.text(.5,.5,'No estimable values\nSee source table and eligibility rules',ha='center',va='center',transform=ax.transAxes)
                        save(f'{ident}_{gi+1}_unavailable',fig,table_name,caption+'全部为缺失；不补零，不计算排序或显著性。')
                        continue
                    bound = max(abs(x) for x in finite) or 1
                    display_detail = ""
                    if spec.get('display_cap') is not None:
                        cap = float(spec['display_cap'])
                        if min(finite) < 0 or not np.isfinite(cap) or cap <= 0:
                            raise ValueError('display_cap只能用于非负矩阵且必须是有限正数')
                        bound = min(bound, cap)
                        display_detail = f'色标显示上限为{cap:g}，超过上限者仅在颜色上饱和，源表数值不变。'
                    lim = (-bound, bound) if min(finite) < 0 else (0, bound)
                    for ri, rp in enumerate(pages(rr, 22)):
                        for ci, cp in enumerate(pages(cc, 14)):
                            if kind == 'matrix' and (spec.get('figure_role') == 'centrality' or spec.get('display_style')=='lollipop') and len(cc) == 1:
                                # A single metric has a common numerical axis; a tall
                                # one-column heatmap wastes space and hides differences.
                                selected={r[rk]:r['value'] for r in rs if r[ck] == cp[0]}
                                fig,ax=plt.subplots(figsize=(183/25.4,max(45,min(150,20+5*len(rp)))/25.4),layout='constrained')
                                values=[selected.get(label) for label in rp]
                                valid=[i for i,value in enumerate(values) if value is not None]
                                ax.hlines(valid,0,[values[i] for i in valid],color='#4477AA',lw=1)
                                ax.scatter([values[i] for i in valid],valid,color='#4477AA',s=12,zorder=3)
                                ax.set_yticks(range(len(rp)),rp);ax.invert_yaxis()
                                ax.set_title(spec.get('title',ident.replace('_',' ')))
                                ax.set_xlabel(spec.get('axis_label','Native centrality'))
                                ax.set_xlim(lim[0]-.03*(lim[1]-lim[0]),lim[1]*1.04)
                                ax.axvline(0,color='black',lw=.5)
                            else:
                                fig = matrix_figure(rs, rk, ck, "value", rp, cp, spec.get('title',ident.replace('_',' ')) if kind=='matrix' else group, spec.get("axis_label", "Native value"), lim)
                            save(f"{ident}_{gi+1}_{ri+1}_{ci+1}", fig, table_name, caption+"分页共享数值尺度。"+display_detail)
            elif kind in ("lr_edges", "metabolite_edges"):
                edge_label='metabolite–sensor' if kind=='metabolite_edges' else 'ligand–receptor'
                directed=spec.get('directed',True)
                if kind=='metabolite_edges':
                    rows=[dict(r,ligand=r['metabolite'],receptor=r['sensor']) for r in rows]
                else:
                    from prioritize_communication import summarize,edge_key
                    evidence=summarize(rows,spec,cfg.get('focus'))
                    evidence_name=ident+'_display_evidence.tsv'
                    if evidence:write_table(out/evidence_name,evidence)
                    spec={**spec,'_evidence_rank':{(r['condition'],edge_key(r)):r['display_rank_within_condition'] for r in evidence}}
                    state['selection'].append(dict(table=ident,evidence_table=evidence_name,focus=cfg.get('focus',{}),rule=lr_selection_rule(spec)))
                all_values=[r['score'] for r in rows if r['tested'] and r['score'] is not None]
                if not all_values:continue
                lower_bound=min(0,min(all_values));upper_bound=max(all_values) or 1
                if lower_bound<0:
                    bound=max(abs(v) for v in all_values) or 1;lower_bound,upper_bound=-bound,bound
                shared_counts=defaultdict(float);shared_weights=defaultdict(float)
                for r in rows:
                    if r['supported']:
                        k=(r['sample'],r['source'],r['target']);shared_counts[k]+=1;shared_weights[k]+=r['score']
                count_max=max(shared_counts.values(),default=1);weight_max=max(shared_weights.values(),default=1)
                state['selection'].append(dict(table=ident,shared_score_limits=[lower_bound,upper_bound],shared_count_max=count_max,shared_weight_max=weight_max,
                    rule='同一方法同一评分表在全部样本/条件间共享点色与层级网络边宽尺度；不同方法分数不共用尺度'))
                for si, sample in enumerate(sorted({r["sample"] for r in rows})):
                    rs = [r for r in rows if r["sample"] == sample]
                    keys = [(r["source"],r["target"],r["ligand"],r["receptor"],r.get("interaction")) for r in rs]
                    if len(set(keys)) != len(keys):
                        raise ValueError("同一样本/细胞对/LR 有重复边，须显式保留唯一 interaction ID 或上游消歧")
                    scored = [r for r in rs if r["tested"] and r["score"] is not None]
                    if not scored:
                        continue
                    lower = spec.get("direction") == "lower"
                    ordered = order_lr_rows(scored,spec)
                    lr_key = lambda r: (r["ligand"],r["receptor"],r.get("interaction", ""))
                    lrs = list(dict.fromkeys(lr_key(r) for r in ordered))[:spec.get('display_top_lr',cfg.get("top_lr",24))]
                    pairs = sorted({(r["source"],r["target"]) for r in rs})
                    if spec.get('display_top_cell_pairs'):
                        pair_weight=defaultdict(float)
                        for r in rs:
                            if r['supported'] and r['score'] is not None:pair_weight[(r['source'],r['target'])]+=r['score']
                        pairs=sorted(pairs,key=lambda pair:(-pair_weight[pair],pair))[:spec['display_top_cell_pairs']]
                        state['selection'].append(dict(table=ident,sample=sample,cell_pairs=pairs,
                            rule='按全部支持LR的论文定义强度总和显示前列细胞类型对；完整细胞对×LR表和全网络保留'))
                    vals = [r["score"] for r in scored]
                    limits = (lower_bound,upper_bound)
                    state["selection"].append(dict(table=ident,sample=sample,ligand_receptor=lrs,
                        rule=lr_selection_rule(spec)))
                    for pi, ps in enumerate(pages(pairs,8)):
                        for li, ls in enumerate(pages(lrs,12)):
                            fig, ax = frame(f"{sample}: {edge_label} evidence")
                            selected = [r for r in scored if (r["source"],r["target"]) in ps and lr_key(r) in ls]
                            if not selected:
                                plt.close(fig)
                                state['figures'].append(dict(id=f'{ident}_bubble_{si+1}_{pi+1}_{li+1}',status='not_applicable',source_data=table_name,
                                    families=['special_molecules' if kind=='metabolite_edges' else 'lr_evidence'],reason='该展示页选定分子与细胞对没有原生可评分候选；不填零，不生成空坐标框',sample=sample,cell_pairs=ps,molecular_pairs=ls))
                                continue
                            if selected:
                                dots = ax.scatter([ps.index((r["source"],r["target"])) for r in selected],
                                    [ls.index(lr_key(r)) for r in selected], c=[r["score"] for r in selected],
                                    s=[32 if r["supported"] else 8 for r in selected], cmap="RdBu_r" if limits[0]<0 else "cividis",vmin=limits[0],vmax=limits[1])
                                fig.colorbar(dots,ax=ax,label=spec.get("axis_label","Native score"),shrink=.6)
                            ax.set_xticks(range(len(ps)),[a+(" → " if directed else " | ")+b for a,b in ps],rotation=45,ha="right")
                            ax.set_yticks(range(len(ls)),[a+" — "+b+(" ["+i+"]" if i else "") for a,b,i in ls]);ax.invert_yaxis()
                            ax.set_xlabel(("Sender → receiver" if directed else "Native matrix row | column")+"; large dot = supported")
                            save(f"{ident}_bubble_{si+1}_{pi+1}_{li+1}",fig,table_name,caption+"点色为原生分数；大点满足该方法声明的支持规则，小点在评分/检验范围内但未满足该规则；不把所有方法的支持标记解释为联合显著性，范围外为空位。"+lr_selection_rule(spec))
                    counts=defaultdict(float)
                    for r in rs:
                        if r["tested"]:
                            counts[(r["source"],r["target"])] += int(r["supported"])
                    if counts and not any(counts.values()):
                        negative_rows=[dict(row=a,column=b,value=v) for (a,b),v in counts.items()]
                        negative_source=f'{ident}_zero_counts_{si+1}.tsv';write_table(out/negative_source,negative_rows)
                        fig=matrix_figure(negative_rows,'row','column','value',sorted({a for a,b in counts}),sorted({b for a,b in counts}),
                            f'{sample}: no candidates meet the support rule','Supported candidates',(0,1))
                        save(f'{ident}_count_heatmap_{si+1}',fig,negative_source,caption+'合格候选中支持数量真实为0；灰色表示该细胞对没有可评分候选，不补0。不绘制不存在的支持网络。')
                    _networks(counts, ident+f"_count_{si+1}", table_name, caption+"边宽为支持 LR 数量，非原生分数之和。", color, save,scale_max=count_max,directed=directed)
                    if spec.get("additive"):
                        weights=defaultdict(float)
                        for r in rs:
                            if r["supported"]: weights[(r["source"],r["target"])] += r["score"]
                        if spec.get('value_kind')!='count':
                            _networks(weights,ident+f"_strength_{si+1}",table_name,caption,color,save,scale_max=weight_max,directed=directed)
                        if any(r.get('pathway') for r in rs):
                            from communication_sankey import pathway_flows,draw,grouped_circos
                            flows,selection=pathway_flows(rs)
                            if flows:
                                flow_source=f'{ident}_pathway_flow_{si+1}.tsv'
                                write_table(out/flow_source,flows)
                                state['selection'].append(dict(table=ident,sample=sample,pathway_sankey=selection))
                                save(f'{ident}_pathway_sankey_{si+1}',draw(flows,color),flow_source,
                                    caption+'发送者→通路→接收者：每条支持LR分数按原生单一通路标签计入一次，两侧使用同一权重总量；这是分数分配图，不是实测分子流量。各层总分前6项的共同子图，完整选择与覆盖率另存。')
                                circos,circos_flows,circos_selection=grouped_circos(rs,color)
                                if circos is not None:
                                    circos_source=f'{ident}_grouped_circos_{si+1}.tsv';write_table(out/circos_source,circos_flows)
                                    state['selection'].append(dict(table=ident,sample=sample,multi_ring=circos_selection))
                                    save(f'{ident}_grouped_circos_{si+1}',circos,circos_source,
                                        caption+'分组双环Circos：外环为发送/接收细胞，内环颜色为通路；带宽与扇区长度使用同一支持LR分数，箭头按发送到接收。发送/接收各前2群与前3通路共同子图，显示总量和完整范围另存。')
                    if any(counts.values()):
                        overview,selection=paper_overview(rs,sample,{**spec,'count_scale_max':count_max,'score_limits':limits},color)
                        state['selection'].append(dict(table=ident,sample=sample,overview=selection))
                        save(f'{ident}_paper_overview_{si+1}',overview,table_name,caption+'四个面板在最终183mm画布上直接绘制，文字不经拼图缩小；有证据排序时按支持候选的最好排序选前6群与前6细胞对，否则使用支持数量；分子对选择：'+lr_selection_rule(spec)+'；全部候选另表保留。')
            elif kind in ("network", "molecular_links"):
                if kind=='molecular_links':
                    _molecular_layers(rows,ident,table_name,caption,color,save)
                    # CPDAG reciprocal edges indicate unresolved direction. The
                    # layered plot draws them without arrows; directed chords
                    # cannot faithfully encode this uncertainty.
                    if any(r.get('direction_status')=='unresolved_reciprocal' for r in rows):continue
                if not spec.get("additive") and kind == "network":
                    raise ValueError("网络汇总需要明确可加语义；有符号/非可加结果请使用矩阵")
                weights=defaultdict(float)
                for r in rows:
                    if r["value"] is None: continue
                    a = r["source"] if kind=="network" else r["source_type"]+": "+r["source"]
                    b = r["target"] if kind=="network" else r["target_type"]+": "+r["target"]
                    if (a,b) in weights and not spec.get("additive"):
                        raise ValueError("非可加分子边重复，不能静默合并")
                    weights[(a,b)] += r["value"]
                if any(v<0 for v in weights.values()):
                    raise ValueError("有符号机制边请使用矩阵，不能用非负弦宽表达")
                _networks(weights,ident,table_name,caption+"机制边表示模型关联，不是分子流量或因果闭环。",color,save,title=spec.get('title'),directed=spec.get('directed',True))
            elif kind == "effect_summary":
                selected=sorted((r for r in rows if r['value'] is not None),key=lambda r:(r['q_value'] if r['q_value'] is not None else 2,-abs(r['value']),r['feature']))[:12]
                if len({r['feature'] for r in rows})!=len(rows):raise ValueError('效应表feature重复，需保留对比身份')
                fig,ax=frame(spec['contrast'])
                for i,r in enumerate(selected):
                    ink='#0072B2' if r['q_value'] is not None and r['q_value']<=spec.get('alpha',.05) else '#888888'
                    if r.get('ci_low') is not None:
                        ax.plot([r['ci_low'],r['ci_high']],[i,i],color=ink,lw=.8)
                    ax.scatter(r['value'],i,s=15,color=ink)
                ax.set_yticks(range(len(selected)),[r['feature'].replace(' | ','\n') for r in selected]);ax.invert_yaxis();ax.axvline(0,color='black',lw=.5)
                ax.set_xlabel(spec.get('axis_label','Difference in native score'))
                tested=sum(r['q_value'] is not None for r in rows)
                significant=sum(r['q_value'] is not None and r['q_value']<=spec.get('alpha',.05) for r in rows)
                ax.text(.99,.99,f"{significant}/{tested} candidates: BH q ≤ {spec.get('alpha',.05)}",ha='right',va='top',fontsize=6,transform=ax.transAxes)
                save(ident+'_effects',fig,table_name,caption+'按完整检验后的q值、绝对效应选前12；蓝色为q阈值内。仅已有区间时绘制区间，不补算。')
                state['selection'].append(dict(table=ident,features=[r['feature'] for r in selected],rule='完整候选检验后按q、绝对效应显示前12'))
                valid=[r for r in rows if r['value'] is not None and r['q_value'] is not None]
                if valid:
                    q_floor=float(spec.get('q_plot_floor',1e-300))
                    if not 0<q_floor<=1:raise ValueError('q_plot_floor必须在(0,1]，只限制显示，不修改源表')
                    fig,ax=frame('Condition effects and adjusted evidence')
                    ax.scatter([r['value'] for r in valid],[-np.log10(max(r['q_value'],q_floor)) for r in valid],s=4,
                               c=['#0072B2' if r['q_value']<=spec.get('alpha',.05) else '#aaaaaa' for r in valid],alpha=.6)
                    ax.axvline(0,color='black',lw=.5);ax.axhline(-np.log10(spec.get('alpha',.05)),color='grey',lw=.5,ls='--')
                    ax.set(xlabel=spec.get('axis_label','Difference in native score'),ylabel='−log10(BH q value)')
                    if any(r['q_value']<q_floor for r in valid):
                        ax.text(.99,.99,f'Display cap: q < {q_floor:.3g}',ha='right',va='top',fontsize=6,transform=ax.transAxes)
                    save(ident+'_volcano',fig,table_name,caption+f'展示全部有限效应和q值；显示下限为{q_floor:.3g}，小于下限者合并至上边界，源表不改；无穷效应另见原生状态，不添加伪计数。')
            elif kind == 'enrichment':
                if len({(r['term'],r['group']) for r in rows})!=len(rows):raise ValueError('富集term/group重复')
                ranked=sorted((r for r in rows if r['q_value'] is not None),key=lambda r:(r['q_value'],r['term']))
                if not ranked:raise ValueError('富集表没有可估计的q值，不能生成看似有效的空富集图')
                terms=list(dict.fromkeys(r['term'] for r in ranked))[:20];groups=sorted({r['group'] for r in rows})
                for pi,gp in enumerate(pages(groups,12)):
                    selected=[r for r in rows if r['term'] in terms and r['group'] in gp and r['q_value'] is not None and r['value'] is not None]
                    fig,ax=frame('Gene-set enrichment')
                    if selected:
                        maximum=max(r['overlap'] for r in rows) or 1
                        points=ax.scatter([gp.index(r['group']) for r in selected],[terms.index(r['term']) for r in selected],
                            s=[10+60*r['overlap']/maximum for r in selected],c=[-np.log10(max(r['q_value'],1e-300)) for r in selected],cmap='cividis',
                            vmin=0,vmax=max([-np.log10(max(r['q_value'],1e-300)) for r in ranked] or [1]) or 1)
                        fig.colorbar(points,ax=ax,label='−log10(adjusted q)',shrink=.6)
                    ax.set_xticks(range(len(gp)),gp,rotation=45,ha='right');ax.set_yticks(range(len(terms)),terms);ax.invert_yaxis()
                    ax.set_xlabel('Dot area: overlap count (shared scale)')
                    save(f'{ident}_dot_{pi+1}',fig,table_name,caption+'以完整检验后的q值选前20条目，缺失不补零；点面积为重叠基因数。')
                    finite=[r['value'] for r in rows if r['value'] is not None]
                    if finite and terms:
                        bound=max(abs(v) for v in finite) or 1
                        fig=matrix_figure(rows,'term','group','value',terms,gp,'Gene-set enrichment',spec.get('axis_label','Native enrichment'),(-bound,bound) if min(finite)<0 else (0,bound))
                        save(f'{ident}_heatmap_{pi+1}',fig,table_name,caption+'同一选集显示原生富集数值，与q值分开展示。')
                state['selection'].append(dict(table=ident,terms=terms,rule='完整检验后按q选前20条目'))
            elif kind == 'embedding_points':
                if len({(r['sample'],r['cell']) for r in rows})!=len(rows):
                    raise ValueError('同样本降维细胞重复')
                quantitative=all('value' in r for r in rows)
                categorical=all(r.get('label') for r in rows)
                if not quantitative and not categorical:
                    raise ValueError('降维着色需要完整label或value列')
                finite=[r['value'] for r in rows if quantitative and r['value'] is not None]
                if quantitative and not finite:raise ValueError('没有可着色的实际数值')
                bound=max(map(abs,finite)) if finite else 1
                limits=(-bound,bound) if finite and min(finite)<0 else (0,max(finite) or 1) if finite else None
                for si,sample in enumerate(sorted({r['sample'] for r in rows})):
                    rs=[r for r in rows if r['sample']==sample]
                    fig,ax=frame(spec.get('title',sample))
                    if quantitative:
                        missing=[r for r in rs if r['value'] is None]
                        if missing:ax.scatter([r['x'] for r in missing],[r['y'] for r in missing],s=7,color='#cccccc',label='Not estimated')
                        visible=[r for r in rs if r['value'] is not None]
                        dots=ax.scatter([r['x'] for r in visible],[r['y'] for r in visible],s=7,c=[r['value'] for r in visible],cmap='RdBu_r' if limits[0]<0 else 'cividis',vmin=limits[0],vmax=limits[1],edgecolors='none')
                        fig.colorbar(dots,ax=ax,label=spec.get('axis_label','Native value'),shrink=.65)
                    else:
                        labels=sorted({r['label'] for r in rs})
                        if len(labels)>20:raise ValueError('类别超过20，需先明确分面设计')
                        for label in labels:
                            group=[r for r in rs if r['label']==label]
                            ax.scatter([r['x'] for r in group],[r['y'] for r in group],s=7,color=color(label),label=label,edgecolors='none')
                        ax.legend(loc='upper left',bbox_to_anchor=(1,1),frameon=False,fontsize=6)
                    ax.set_aspect('equal',adjustable='datalim');method=spec['embedding_method']
                    ax.set_xlabel(method+' 1');ax.set_ylabel(method+' 2');ax.grid(False)
                    save(f'{ident}_{si+1}',fig,table_name,caption+'复用全部原始降维坐标；颜色表示原生数值或真实类别。降维距离不是组织物理距离，缺失数值以灰色保留。坐标来源：'+spec['embedding_provenance'])
            elif kind == 'latent_points':
                if len({(r['domain'],r['entity']) for r in rows})!=len(rows):
                    raise ValueError('潜在空间实体在同一域重复')
                if any(r[k] is None for r in rows for k in ('x','y','z')):
                    raise ValueError('原生潜在空间存在缺失坐标，不能绘制为完整嵌入')
                domains=sorted({r['domain'] for r in rows})
                if len(domains)>8:raise ValueError('潜在空间域超过8类，需先明确分面方案')
                for three in (False,True):
                    fig,ax=frame(spec.get('title','Native latent space'),projection='3d' if three else None)
                    if three:
                        fig.set_layout_engine(None)
                        fig.subplots_adjust(left=.08,right=.88,bottom=.10,top=.88)
                    for di,domain in enumerate(domains):
                        points=[r for r in rows if r['domain']==domain]
                        coordinates=[[r[k] for r in points] for k in ('x','y','z')[:3 if three else 2]]
                        ax.scatter(*coordinates,s=5,alpha=.55,color=['#4477AA','#EE6677','#228833','#CCBB44','#66CCEE','#AA3377','#BBBBBB','#332288'][di],label=domain,edgecolors='none')
                    ax.set_xlabel('Latent dimension 1');ax.set_ylabel('Latent dimension 2')
                    if three:
                        ax.set_zlabel('Latent dimension 3');ax.view_init(elev=23,azim=42)
                        for axis in (ax.xaxis,ax.yaxis,ax.zaxis):axis.pane.fill=False
                    else:ax.set_aspect('equal',adjustable='datalim')
                    ax.grid(False);ax.legend(loc='upper left',frameon=False,fontsize=6)
                    save(ident+('_3d' if three else '_2d'),fig,table_name,caption+'全部实际原生潜在坐标；2D只显示前两维，3D显示前三维。不代表组织物理位置、细胞空间距离或分子轨迹；来源定义：'+spec['space_definition'])
            elif kind == "activities":
                rs=sorted([r for r in rows if r["value"] is not None],key=lambda r:r["value"],reverse=spec.get("direction")!="lower")[:30]
                fig,ax=frame("Ligand activity")
                ax.barh(range(len(rs)),[r["value"] for r in rs],color="#4477AA")
                ax.set_yticks(range(len(rs)),[r["ligand"] for r in rs]);ax.invert_yaxis()
                ax.set_xlabel(spec.get("axis_label","Native activity"));ax.axvline(0,color="black",lw=.5)
                save(ident+"_ranking",fig,table_name,caption+"保留负活性值；显示前30个原生排序候选。")
            elif kind == "spatial_edges":
                coordinates={}
                for point_spec,point_rows,_ in tables:
                    if point_spec["type"]=="spatial_points":
                        if point_spec.get('coordinate_unit')!=spec.get('coordinate_unit'):raise ValueError('空间边与位置单位不一致')
                        for r in point_rows:
                            key=(r["sample"],r["cell"])
                            if key in coordinates and coordinates[key]!=(r["x"],r["y"]):raise ValueError("重复空间表坐标不一致")
                            coordinates[key]=(r["x"],r["y"])
                if not coordinates:raise ValueError("空间边需要同结果包真实空间坐标表")
                for si,sample in enumerate(sorted({r["sample"] for r in rows})):
                    rs=[r for r in rows if r["sample"]==sample and r["value"] is not None]
                    for r in rs:
                        if any((sample,r[k]) not in coordinates for k in ("source_cell","target_cell")):
                            raise ValueError("空间边端点缺失或跨样本")
                    xy=np.array([v for (s,c),v in coordinates.items() if s==sample])
                    directed=spec.get('directed',True)
                    if directed:
                        # Deterministic tie randomization prevents array order
                        # from creating an apparent spatial hotspot at the cutoff.
                        shuffled=[rs[i] for i in np.random.default_rng(0).permutation(len(rs))]
                        selected=sorted(shuffled,key=lambda r:-abs(r['value']))[:100]
                        rule='绝对权重前100边；同权重使用固定种子0打散，避免原始细胞排序偏向'
                    else:
                        selected=rs if len(rs)<=10000 else [rs[i] for i in np.random.default_rng(0).choice(len(rs),10000,replace=False)]
                        rule='无向邻接图展示全部边；超过10000边时固定种子0等概率抽取10000条，仅降低显示密度'
                    state['selection'].append(dict(table=ident,sample=sample,displayed_edges=len(selected),total_edges=len(rs),rule=rule))
                    title=spec.get('title',sample+': spatial edges')
                    if len({r['sample'] for r in rows})>1 and title!=sample:title=f'{title} — {sample}'
                    fig,ax=spatial_frame(title,xy)
                    ax.scatter(xy[:,0],xy[:,1],s=2,color="#cccccc")
                    maximum=max([abs(r["value"]) for r in selected] or [1]) or 1
                    for r in selected:
                        if directed:
                            ax.annotate("",xy=coordinates[(sample,r["target_cell"])],xytext=coordinates[(sample,r["source_cell"])],
                                arrowprops=dict(arrowstyle="-|>",lw=.3+abs(r["value"])/maximum,color="#4477AA",alpha=.5))
                        else:
                            a,b=coordinates[(sample,r['source_cell'])],coordinates[(sample,r['target_cell'])]
                            ax.plot([a[0],b[0]],[a[1],b[1]],lw=.25,color='#4477AA',alpha=.25)
                    unit={'um':'μm','pixel':'pixels','native':'native units'}[spec['coordinate_unit']]
                    ax.set(xlabel=f"x ({unit})",ylabel=f"y ({unit})",aspect="equal")
                    if spec.get("y_down",False):ax.invert_yaxis()
                    save(f"{ident}_{si+1}",fig,table_name,caption+rule+'；完整边在源表；'+('箭头按原生方向。' if directed else '原生无向邻域关系，不加通讯方向。'))
            elif kind in ("spatial_points", "spatial_vectors"):
                for si,sample in enumerate(sorted({r["sample"] for r in rows})):
                    rs=[r for r in rows if r["sample"]==sample]
                    if len({r["cell"] for r in rs})!=len(rs):raise ValueError("空间位置 cell ID 重复")
                    title=spec.get('title',sample)
                    if len({r['sample'] for r in rows})>1 and title!=sample:title=f'{title} — {sample}'
                    fig,ax=spatial_frame(title,[[r['x'],r['y']] for r in rs])
                    if kind=="spatial_points":
                        categorical=all(r.get('label') for r in rs)
                        if categorical:
                            labels=sorted({r['label'] for r in rs})
                            if len(labels)>20:raise ValueError('空间类别超过20，需先明确分面设计')
                            for label in labels:
                                group=[r for r in rs if r['label']==label]
                                ax.scatter([r['x'] for r in group],[r['y'] for r in group],s=5,
                                           color=color(label),label=label,edgecolors='none')
                            ax.legend(loc='upper left',bbox_to_anchor=(1,1),frameon=False,fontsize=6)
                        else:
                            pts=ax.scatter([r["x"] for r in rs],[r["y"] for r in rs],c=[np.nan if r["value"] is None else r["value"] for r in rs],s=3,cmap="cividis")
                            fig.colorbar(pts,ax=ax,label=spec.get("axis_label","Native spatial value"),shrink=.6)
                    else:
                        if not spec.get("direction_definition"):raise ValueError("空间向量缺少原生方向定义")
                        step=max(1,int(np.ceil(len(rs)/1500)))
                        chosen=rs[::step]
                        ax.scatter([r["x"] for r in rs],[r["y"] for r in rs],s=1,color="#dddddd")
                        q=ax.quiver([r["x"] for r in chosen],[r["y"] for r in chosen],[r["dx"] for r in chosen],[r["dy"] for r in chosen],
                                    angles="xy",scale_units="xy",scale=spec.get("vector_scale",1),width=.002,color="#4477AA")
                        length=max(np.hypot(r["dx"],r["dy"]) for r in chosen) or 1
                        ax.quiverkey(q,.75,.98,length,f"Vector = {length:.2g}",coordinates="axes",fontproperties={"size":6})
                        state["selection"].append(dict(table=ident,sample=sample,vector_stride=step,rule="按原始顺序等距抽取箭头，仅减绘图密度"))
                    unit={'um':'μm','pixel':'pixels','native':'native units'}[spec['coordinate_unit']]
                    ax.set(xlabel=f"x ({unit})",ylabel=f"y ({unit})",aspect="equal")
                    xy=np.asarray([[r['x'],r['y']] for r in rs],dtype=float);span=np.ptp(xy,axis=0)
                    if span[0]==0:
                        pad=max(span[1]*.03,.5);ax.set_xlim(xy[0,0]-pad,xy[0,0]+pad)
                    if span[1]==0:
                        pad=max(span[0]*.03,.5);ax.set_ylim(xy[0,1]-pad,xy[0,1]+pad)
                    if spec.get("y_down",False):ax.invert_yaxis()
                    save(f"{ident}_{si+1}",fig,table_name,caption)
            elif kind in ("effects", "time_series"):
                features=sorted({r["feature"] for r in rows})
                for fi,feature in enumerate(features):
                    rs=[r for r in rows if r["feature"]==feature and r["value"] is not None]
                    if not rs:
                        state['figures'].append(dict(id=f'{ident}_{fi+1}',status='not_applicable',families=sorted(table_families(spec,rows)),reason='该特征没有有限估计值；保留来源和缺失原因，不画空坐标框'))
                        continue
                    fig,ax=frame(feature)
                    if kind=="time_series":
                        if spec.get("time_kind") not in ("observed","pseudotime","velocity_model"):
                            raise ValueError("时间图需要声明 observed/pseudotime/velocity_model")
                        for donor in sorted({r["donor"] for r in rs}):
                            ds=sorted([r for r in rs if r["donor"]==donor],key=lambda r:r["time"])
                            if len({r["time"] for r in ds})!=len(ds):raise ValueError("同供体时间点重复，先在上游定义汇总")
                            ax.plot([r["time"] for r in ds],[r["value"] for r in ds],"o-",ms=2,lw=.7,label=donor)
                        ax.set_xlabel(spec["time_kind"]+": "+spec.get("time_unit","specified units"))
                    else:
                        conditions=sorted({r["condition"] for r in rs})
                        fig.set_size_inches(89/25.4,80/25.4)
                        ax.set_title('\n'.join(textwrap.wrap(feature,width=45)))
                        if len({(r["donor"],r["condition"]) for r in rs})!=len(rs):raise ValueError("供体条件重复，不能把细胞当供体点")
                        for ci,cond in enumerate(conditions):
                            ds=[r for r in rs if r["condition"]==cond]
                            ys=[r["value"] for r in ds]
                            if len(ys)>=10 and len(set(ys))>1:
                                violin=ax.violinplot([ys],positions=[ci],widths=.7,showextrema=False)
                                for body in violin['bodies']:body.set_facecolor(color(cond));body.set_alpha(.15)
                            if len(ys)>=5:ax.boxplot([ys],positions=[ci],widths=.45,showfliers=False)
                            elif ys:ax.hlines(float(np.median(ys)),ci-.18,ci+.18,color='black',lw=.8,zorder=4)
                            ax.scatter(ci+np.linspace(-.08,.08,len(ds)),ys,s=12,color=color(cond),zorder=3)
                        ax.set_xticks(range(len(conditions)),[f'{cond}\nn={sum(r["condition"]==cond for r in rs)} donors' for cond in conditions],rotation=0)
                        ax.set_xlim(-.5,len(conditions)-.5)
                        group_field=spec.get('scale_group_field')
                        if group_field:
                            if any(group_field not in r for r in rows):raise ValueError('共享尺度分组字段缺失')
                            groups={r[group_field] for r in rs}
                            if len(groups)!=1:raise ValueError('一个功能特征对应多个尺度分组')
                            values=[r['value'] for r in rows if r[group_field] in groups and r['value'] is not None]
                            low,high=min(values),max(values);span=high-low or .01
                            ax.set_ylim(0 if spec.get('nonnegative') else low-.05*span,high+.05*span)
                        ax.set_ylabel(spec.get("axis_label","Native value"))
                    if kind=='effects' and spec.get('value_kind')=='row_normalized_probability_share':ax.set_ylim(0,1)
                    detail="点为供体；绘图不计算显著性。"
                    if kind=='effects':
                        detail+="不足5个供体时横线为中位数；至少5个供体时箱体为四分位范围、须为1.5×IQR内最远观察值，全部供体点仍显示；小提琴仅在至少10个且非常数时显示。"
                        if spec.get('scale_group_field'):detail+="相同尺度分组共享纵轴范围。"
                    save(f"{ident}_{fi+1}",fig,table_name,caption+detail)
            else:
                raise ValueError("该结果类型尚无对应绘图实现；不能记为数据不适用")
        except Exception as error:
            plt.close("all")
            state["figures"].append(dict(id=ident,status="failed",families=sorted(table_families(spec,rows)),reason=str(error)))
        persist()
    write_json(out/"cell_colors.json",colors)
    generated=[e for e in state["figures"] if e["status"]=="generated"]
    if generated:
        from pypdf import PdfWriter
        writer=PdfWriter()
        for entry in generated:
            writer.append(out/next(p for p in entry["files"] if p.endswith(".pdf")))
        writer.write(out/"figure_atlas.pdf")
        writer.close()
        state["atlas_pdf"]="figure_atlas.pdf"
    from run_communication import validate_delivery
    state['technical_issues']=validate_delivery(out,state['figures'])
    finish_plan(state['figure_plan'],state['figures'])
    write_json(out/'figure_plan.json',state['figure_plan'])
    state["status"]="partial" if any(e["status"]=="failed" for e in state["figures"]) else "generated_pending_visual_review"
    if state['technical_issues'] and state['status']!='partial':state['status']='needs_visual_revision'
    if any(e.get("technical_quality",{}).get("issues") for e in generated) and state["status"]!="partial":
        state["status"]="needs_visual_revision"
    persist()
    (out/"figure_report.md").write_text("\n\n".join([f"# {cfg['dataset']}",state["status"],*[f"{e['id']}: {e['status']} — {e.get('caption',e.get('reason',''))}" for e in state["figures"]]]))
    return 0 if state["status"]=="generated_pending_visual_review" else 2


def _molecular_layers(rows,identifier,source,caption,color,save):
    selected=sorted((r for r in rows if r['value'] is not None and r['value']!=0),key=lambda r:(-abs(r['value']),r['source'],r['target']))[:60]
    if not selected:return
    order=['ligand','receptor','inflow','signaling','TF','tf','module','target','outflow']
    types=sorted({r[k] for r in selected for k in ('source_type','target_type')},key=lambda t:(order.index(t) if t in order else len(order),t))
    maximum=max(abs(r['value']) for r in selected)
    for pi,page in enumerate(pages(selected,20)):
        fig,ax=frame('Molecular evidence layers')
        nmax=max(len({r[k] for r in page for k,tk in [('source','source_type'),('target','target_type')] if r[tk]==kind}) for kind in types)
        fig.set_size_inches(183/25.4,max(55,min(150,25+10*nmax))/25.4)
        positions={}
        for ti,kind in enumerate(types):
            nodes=sorted({r[k] for r in page for k,tk in [('source','source_type'),('target','target_type')] if r[tk]==kind})
            x=ti/max(1,len(types)-1)
            ax.text(x,1.05,kind,ha='center',fontsize=7,fontweight='bold')
            for ni,node in enumerate(nodes):
                y=(ni+.5)/max(1,len(nodes));positions[(kind,node)]=(x,y)
                ax.scatter([x],[y],s=15,color=color(kind),zorder=3)
                ax.text(x+.015,y,node,ha='left',va='center',fontsize=6,zorder=4,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.85,pad=.5))
        drawn=set()
        for r in page:
            a=(r['source_type'],r['source']);b=(r['target_type'],r['target'])
            unresolved=r.get('direction_status')=='unresolved_reciprocal'
            pair=tuple(sorted((a,b))) if unresolved else (a,b)
            if pair in drawn:continue
            drawn.add(pair)
            ax.annotate('',xy=positions[b],xytext=positions[a],arrowprops=dict(
                arrowstyle='-' if unresolved else '-|>',connectionstyle='arc3,rad=.25' if a[0]==b[0] else 'arc3,rad=.03',
                lw=.4+1.8*abs(r['value'])/maximum,color='#777777' if unresolved else color(a[0]),
                linestyle='--' if unresolved or r['value']<0 else '-',alpha=.65,shrinkA=4,shrinkB=4))
        ax.set(xlim=(-.08,1.45),ylim=(-.08,1.12));ax.axis('off')
        ax.text(.5,-.055,f'Native edge maximum = {maximum:.3g}; page {pi+1}/{int(np.ceil(len(selected)/20))}',ha='center',fontsize=6)
        save(f'{identifier}_layers_{pi+1}',fig,source,caption+'按实际分子类型分层，展示绝对原生值前60边并分页；同层曲线保留，未定向CPDAG边用无箭头虚线；不同层边不相加，不暗示流量守恒。')


def _networks(weights, identifier, source, caption, color, save,scale_max=None,title=None,directed=True):
    selected=sorted(((a,b,v) for (a,b),v in weights.items() if v>0),key=lambda x:(-x[2],x[0],x[1]))[:40]
    if not selected:return
    # Readable focus: full candidate table is retained; output caption states truncation.
    left=sorted({a for a,b,v in selected});right=sorted({b for a,b,v in selected})
    vmax=scale_max or max(v for a,b,v in selected)
    if vmax<max(v for a,b,v in selected):raise ValueError('共享边宽上限低于实际边值')
    edge_pages=pages(selected,20) if max(len(left),len(right))>24 else [selected]
    for pi,page in enumerate(edge_pages):
        fig,ax=frame(title or ("Directed interaction network" if directed else "Matrix-role interaction associations"))
        pl=sorted({a for a,b,v in page});pr=sorted({b for a,b,v in page})
        ly={x:i/(max(1,len(pl)-1)) for i,x in enumerate(pl)}
        ry={x:i/(max(1,len(pr)-1)) for i,x in enumerate(pr)}
        for a,b,v in page:
            ax.annotate("",xy=(1,ry[b]),xytext=(0,ly[a]),arrowprops=dict(arrowstyle="-|>" if directed else "-",lw=.3+2.7*v/vmax,color=color(a),alpha=.6))
        for name,y in ly.items():ax.text(-.03,y,name,ha="right",va="center",fontsize=6)
        for name,y in ry.items():ax.text(1.03,y,name,ha="left",va="center",fontsize=6)
        ax.set(xlim=(-.8,1.8),ylim=(-.08,1.12));ax.axis("off")
        ax.text(.5,1.06,f"Edge scale maximum = {vmax:.3g}; page {pi+1}/{len(edge_pages)}",ha="center",fontsize=6)
        save(identifier+"_hierarchy"+(f'_{pi+1}' if len(edge_pages)>1 else ''),fig,source,caption+"展示权重前40边，节点过多时自动分页且共享边宽尺度；左右保留原生矩阵行列角色。"+("箭头仅在方法定义了方向时绘制。" if directed else "无箭头线不推断分子发送方向。"))
    # Separate sender/receiver sectors also retain autocrine edges rather than dropping diagonals.
    from pycirclize import Circos
    import pandas as pd
    totals=defaultdict(float)
    for a,b,v in selected:totals[a]+=v
    focal_sources=sorted(left,key=lambda a:(-totals[a],a))[:2]
    incoming=defaultdict(float)
    for a,b,v in selected:
        if a in focal_sources:incoming[b]+=v
    focal_targets=sorted(incoming,key=lambda b:(-incoming[b],b))[:5]
    source_prefix,target_prefix=("S: ","R: ") if directed else ("Row: ","Column: ")
    mat=pd.DataFrame(0.,index=[source_prefix+a for a in focal_sources],columns=[target_prefix+b for b in focal_targets])
    for a,b,v in selected:
        if a in focal_sources and b in focal_targets:mat.loc[source_prefix+a,target_prefix+b]=v
    palette={prefix+name:color(name) for prefix,names in ((source_prefix,focal_sources),(target_prefix,focal_targets)) for name in names}
    circos=Circos.chord_diagram(mat,space=6,cmap=palette,label_kws={"size":6},link_kws={"direction":1 if directed else 0,"alpha":.5})
    fig=circos.plotfig(figsize=(183/25.4,150/25.4))
    if title:fig.suptitle('\n'.join(textwrap.wrap(title,width=75)),fontsize=7)
    fig.supxlabel(f'Displayed total = {mat.to_numpy().sum():.4g}; widths normalized within circle',fontsize=6)
    save(identifier+"_chord",fig,source,caption+"分矩阵行/列扇区，带宽在本圆内归一化，跨样本比较绝对值需用共享尺度的层级网络和源表；从前40边聚焦总权重前2行实体和其前5列实体，显示总量标于图下。"+("带方向标记沿方法声明方向。" if directed else "弦带无方向标记，不把矩阵行列解释为分子发送者/接收者。"))


def paper_overview(rows,sample,spec,color):
    """Redraw a compact four-panel figure at final size, never shrink page images."""
    directed=spec.get('directed',True)
    counts=defaultdict(int);node_totals=defaultdict(int);tested_pairs=set()
    for r in rows:
        pair=(r['source'],r['target'])
        if r['tested']:tested_pairs.add(pair)
        if r['supported']:
            counts[pair]+=1;node_totals[r['source']]+=1;node_totals[r['target']]+=1
    ranked=order_lr_rows([r for r in rows if r['supported'] and r['score'] is not None],spec)
    pair_ranks={};node_ranks={}
    if spec.get('_evidence_rank'):
        for i,r in enumerate(ranked):
            pair_ranks.setdefault((r['source'],r['target']),i)
            for n in (r['source'],r['target']):node_ranks.setdefault(n,i)
    nodes=sorted(node_totals,key=lambda n:(node_ranks.get(n,0),-node_totals[n],n))[:6]
    pair_order=sorted(counts,key=lambda p:(pair_ranks.get(p,0),-counts[p],p))[:6]
    finite=[r for r in rows if r['tested'] and r['score'] is not None and (r['source'],r['target']) in pair_order]
    lr_key=lambda r:(r['ligand'],r['receptor'],r.get('interaction',''))
    ordered=order_lr_rows(finite,spec)
    lrs=list(dict.fromkeys(lr_key(r) for r in ordered))[:6]
    fig,axes=plt.subplots(2,2,figsize=(183/25.4,150/25.4),layout='constrained')
    for label,ax in zip('abcd',axes.flat):ax.text(-.08,1.05,label,transform=ax.transAxes,fontsize=8,fontweight='bold',gid='panel_letter')
    ax=axes[0,0];theta=np.linspace(0,2*np.pi,len(nodes),endpoint=False);xy=np.c_[np.cos(theta),np.sin(theta)]
    positions=dict(zip(nodes,xy));maximum=spec.get('count_scale_max',max(counts.values()))
    for (a,b),v in counts.items():
        if a not in positions or b not in positions:continue
        start=positions[a];end=positions[b]
        if a==b:
            from matplotlib.path import Path as PlotPath
            from matplotlib.patches import FancyArrowPatch
            tangent=np.array([-start[1],start[0]])
            curve=PlotPath([start+.10*tangent,start+.85*start+.48*tangent,start+.85*start-.48*tangent,start-.10*tangent],
                           [PlotPath.MOVETO,PlotPath.CURVE4,PlotPath.CURVE4,PlotPath.CURVE4])
            loop=FancyArrowPatch(path=curve,arrowstyle='-|>' if directed else '-',mutation_scale=7,lw=.2+1.8*v/maximum,color=color(a),alpha=.6)
            loop.set_gid('autocrine_loop');ax.add_patch(loop)
            continue
        ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='-|>' if directed else '-',connectionstyle='arc3,rad=.12',
            lw=.2+1.8*v/maximum,color=color(a),alpha=.6,shrinkA=5,shrinkB=5))
    for n,p in positions.items():
        ax.scatter(*p,s=20,color=color(n),zorder=3);ax.text(*(p*1.24),n,ha='center',va='center',fontsize=6)
    ax.set(xlim=(-1.9,1.9),ylim=(-1.85,1.85),aspect='equal');ax.axis('off');ax.set_title('Supported candidate '+('network' if directed else 'associations'))
    ax.text(.5,0,f'Maximum edge = {maximum}',transform=ax.transAxes,ha='center',fontsize=6)
    ax=axes[0,1];matrix=np.full((len(nodes),len(nodes)),np.nan)
    for i,a in enumerate(nodes):
        for j,b in enumerate(nodes):
            if (a,b) in tested_pairs:matrix[i,j]=counts[(a,b)]
    cmap=plt.get_cmap('cividis').copy();cmap.set_bad('#dddddd')
    im=ax.pcolormesh(np.ma.masked_invalid(matrix),cmap=cmap,vmin=0,vmax=maximum)
    ax.set_xticks(np.arange(len(nodes))+.5,nodes,rotation=55,ha='right');ax.set_yticks(np.arange(len(nodes))+.5,nodes);ax.invert_yaxis()
    ax.set_title(('Sender–receiver' if directed else 'Native row–column')+' counts');ax.set(xlabel='Receiver' if directed else 'Column role',ylabel='Sender' if directed else 'Row role');fig.colorbar(im,ax=ax,label='Supported candidates',shrink=.65)
    ax=axes[1,0];rs=[r for r in finite if lr_key(r) in lrs];bound=max([abs(r['score']) for r in finite] or [1]) or 1
    signed=any(r['score']<0 for r in finite)
    if rs:
        im=ax.scatter([pair_order.index((r['source'],r['target'])) for r in rs],[lrs.index(lr_key(r)) for r in rs],
            c=[r['score'] for r in rs],s=[22 if r['supported'] else 5 for r in rs],cmap='RdBu_r' if signed else 'cividis',vmin=spec.get('score_limits',(-bound if signed else 0,bound))[0],vmax=spec.get('score_limits',(0,bound))[1])
        fig.colorbar(im,ax=ax,label=spec.get('axis_label','Native score'),shrink=.65)
    ax.set_xticks(range(len(pair_order)),[f'P{i+1}' for i in range(len(pair_order))]);ax.set_yticks(range(len(lrs)),[a+'–'+b for a,b,_ in lrs]);ax.invert_yaxis()
    ax.set_title('Molecular evidence');ax.set_xlabel('Pair IDs in panel d; large dot: supported')
    ax=axes[1,1]
    ax.barh(range(len(pair_order)),[counts[p] for p in pair_order],color=[color(p[0]) for p in pair_order])
    separator='→' if directed else '|'
    ax.set_yticks(range(len(pair_order)),[f'P{i+1}: {a}\n{separator} {b}' for i,(a,b) in enumerate(pair_order)]);ax.invert_yaxis();ax.set_xlabel('Supported candidates');ax.set_title('Selected cell pairs')
    ax.set_xlim(0,maximum*1.05)
    return fig,dict(nodes=nodes,pairs=pair_order,molecular_pairs=lrs,rule=lr_selection_rule(spec))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle",required=True);p.add_argument("--out",required=True)
    p.add_argument('--plot-config')
    args=p.parse_args()
    sys.exit(run(args.bundle,args.out,args.plot_config))
