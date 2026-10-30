#!/usr/bin/env python3
"""真实QC长表到三格式图件；不做过滤或显著性检验。"""
from pathlib import Path
import runpy
import math

delivery=runpy.run_path(str(Path(__file__).with_name("figure_delivery.py")))
require=delivery["require"]


def render(cfg, base, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    allowed={"table","question","caption","font","width_mm","height_mm","dpi","metrics","sample_order","stage_order","thresholds"}
    require(not set(cfg)-allowed,"未知QC配置字段："+str(set(cfg)-allowed))
    require(all(isinstance(cfg.get(k),str) and cfg[k].strip() for k in ("table","question","caption")),"需要table、question、caption")
    source=(base/cfg["table"]).resolve();rows=delivery["read_table"](source)
    required={"cell_id","sample_id","stage","metric","value","unit"}
    require(required<=rows[0].keys(),"QC长表缺少身份、指标或单位列")
    units={"detected_genes":"genes","total_counts":"counts","mitochondrial_percent":"%"}
    labels={"detected_genes":"Detected genes","total_counts":"Total counts","mitochondrial_percent":"Mitochondrial counts (%)"}
    seen=set()
    for row in rows:
        require(all(row[k].strip() for k in required),"QC必需值缺失")
        key=tuple(row[k] for k in ("sample_id","cell_id","stage","metric"))
        require(key not in seen,"重复细胞/阶段/指标；不能静默聚合");seen.add(key)
        metric=row["metric"];require(metric in units,"不支持的QC指标")
        require(row["unit"]==units[metric],"QC单位不明确或不匹配；不能猜测比例换算")
        v=float(row["value"]);require(math.isfinite(v) and v>=0,"QC数值非有限或小于0")
        if metric=="mitochondrial_percent":require(v<=100,"线粒体百分比超过100")
        else:require(v.is_integer(),"计数指标必须来自实际整数计数")
        row["value"]=v
    available=list(dict.fromkeys(r["metric"] for r in rows))
    metrics=cfg.get("metrics",list(units))
    require(metrics and len(set(metrics))==len(metrics) and set(metrics)<=set(available),"请求的QC面板缺少数据；可显式选择已有指标并说明缺项")
    samples=cfg.get("sample_order",list(dict.fromkeys(r["sample_id"] for r in rows)))
    stages=cfg.get("stage_order",list(dict.fromkeys(r["stage"] for r in rows)))
    require(len(set(samples))==len(samples) and set(samples)=={r['sample_id'] for r in rows},"样本顺序不覆盖实际样本")
    require(len(set(stages))==len(stages) and set(stages)=={r['stage'] for r in rows},"阶段顺序不覆盖实际阶段")
    require(len(stages)<=4,"阶段过多，请按真实阶段分图")
    thresholds=cfg.get("thresholds",[])
    for line in thresholds:
        require(set(line)=={"metric","value","reason"} and line['metric'] in metrics and line['reason'],"阈值需指标、数值和实际依据")
        require(math.isfinite(float(line['value'])),"阈值不是有限值")
    palette=["#0072B2","#D55E00","#009E73","#CC79A7"]
    records=[]
    width=float(cfg.get("width_mm",183));height=float(cfg.get("height_mm",100))
    require(89<=width<=300 and 70<=height<=300,"图尺寸不适合QC面板")
    with plt.rc_context({"axes.grid":False,"font.family":cfg.get("font","DejaVu Sans"),"font.size":8,"axes.spines.top":False,"axes.spines.right":False}):
        for page,start in enumerate(range(0,len(samples),5),1):
            subset=samples[start:start+5]
            fig,axes=plt.subplots(1,len(metrics),figsize=(width/25.4,height/25.4),squeeze=False,layout="constrained")
            def draw(ax,metric):
                ticks=[];ticklabels=[];index=0
                for sample in subset:
                    for stage in stages:
                        values=[r['value'] for r in rows if r['metric']==metric and r['sample_id']==sample and r['stage']==stage]
                        if not values: continue
                        # 常数/小样本不估计密度。箱线展示全数据，点层最多200个固定抽样。
                        ax.boxplot(values,positions=[index],widths=.5,showfliers=False,patch_artist=True,
                                   boxprops=dict(facecolor=palette[stages.index(stage)],alpha=.3),medianprops=dict(color="#333333",linewidth=.8))
                        selected=np.random.default_rng(0).choice(values,min(200,len(values)),replace=False)
                        jitter=np.random.default_rng(1).uniform(-.15,.15,len(selected))
                        ax.scatter(index+jitter,selected,s=3,color=palette[stages.index(stage)],alpha=.55,rasterized=len(values)>200)
                        ticks.append(index);ticklabels.append(f"{sample}\n{stage}\nn={len(values)}");index+=1
                require(index>0,"QC面板没有实际数据")
                ax.set_xticks(ticks,ticklabels,rotation=45,ha="right")
                ax.set_title(labels[metric]);ax.set_ylabel(units[metric])
                all_values=[r['value'] for r in rows if r['metric']==metric]
                top=max(all_values) or 1
                relevant=[x for x in thresholds if x['metric']==metric]
                top=max([top]+[float(x['value']) for x in relevant])
                ax.set_ylim(-.02*top,1.08*top)
                for line in relevant:ax.axhline(float(line['value']),color="#666666",ls="--",lw=.6)
                require(all(ax.get_ylim()[0]<=v<=ax.get_ylim()[1] for v in all_values),"QC数据超出轴域")
            for ax,metric in zip(axes[0],metrics):
                draw(ax,metric)
            name=f"qc_{page:02d}"
            try:records.append(delivery["save_figure"](fig,out/(name+".png"),dpi=cfg.get('dpi',400)))
            finally:plt.close(fig)
            if len(metrics)>1:
                for metric in metrics:
                    single,ax=plt.subplots(figsize=(max(89,width/len(metrics))/25.4,height/25.4),layout="constrained")
                    draw(ax,metric)
                    try:records.append(delivery["save_figure"](single,out/(name+"_"+metric+".png"),dpi=cfg.get('dpi',400)))
                    finally:plt.close(single)
    delivery["write_table"](out/"plot_data.tsv",rows)
    delivery["dump"](out/"figure_manifest.json",dict(status="generated",figures=records,source_sha256=delivery['digest'](source),
        visual_review="pending",display_sampling="fixed seed, at most 200 points/group; boxplots use all values",generated_statistics=False))
    (out/"caption.md").write_text(cfg['question']+"\n\n"+cfg['caption']+"\n\nQC为细胞级描述，不构成供体层面差异推断。\n"+"\n".join(f"[PNG]({f['files'][0]}) · [SVG]({f['files'][1]}) · [PDF]({f['files'][2]})" for f in records),encoding="utf-8")
    return dict(figures=len(records),rows=len(rows))


if __name__=="__main__":raise SystemExit(delivery["run_cli"](render))
