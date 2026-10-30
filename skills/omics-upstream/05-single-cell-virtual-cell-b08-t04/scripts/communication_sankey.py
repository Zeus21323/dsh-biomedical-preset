"""Conserved sender–pathway–receiver ribbons from explicitly additive LR weights."""
from collections import defaultdict
import math
import textwrap


def pathway_flows(rows, limit=6):
    candidates = [r for r in rows if r['supported'] and r['tested'] and r['score'] is not None and r['score']>0]
    if not candidates:
        return [], {}
    if any(not str(r.get('pathway','')).strip() for r in candidates):
        raise ValueError('部分支持LR缺少通路身份；不能把缺失默认为某条通路')
    totals = {key:defaultdict(float) for key in ('source','pathway','target')}
    for r in candidates:
        for key in totals: totals[key][r[key]] += r['score']
    chosen = {key:sorted(values,key=lambda x:(-values[x],x))[:limit] for key,values in totals.items()}
    flows = defaultdict(float)
    for r in candidates:
        if all(r[key] in chosen[key] for key in chosen):
            flows[(r['source'],r['pathway'],r['target'])] += r['score']
    result = [dict(source=a,pathway=p,target=b,value=v) for (a,p,b),v in sorted(flows.items())]
    return result, dict(selected=chosen,total_supported_score=sum(r['score'] for r in candidates),
                        displayed_score=sum(flows.values()),rule='各层总分前6项的共同子图；每条输入LR只归入其显式pathway标签一次')


def layout(flows):
    keys = ('source','pathway','target');totals={k:defaultdict(float) for k in keys}
    for r in flows:
        if not math.isfinite(r['value']) or r['value']<=0:raise ValueError('桑基图需要有限正权重')
        for key in keys:totals[key][r[key]] += r['value']
    grand=sum(r['value'] for r in flows)
    if not grand:raise ValueError('没有可展示流量')
    gap=.045;scale=min(1-gap*(len(v)-1) for v in totals.values())/grand
    if scale<=0:raise ValueError('节点过多，需先定义展示子图')
    nodes={}
    for key in keys:
        ordered=sorted(totals[key],key=lambda n:(-totals[key][n],n))
        y=(1-(grand*scale+gap*(len(ordered)-1)))/2
        for name in ordered:
            height=totals[key][name]*scale;nodes[(key,name)]=(y,height);y+=height+gap
    ribbons=[]
    for a,b in zip(keys,keys[1:]):
        links=defaultdict(float)
        for r in flows:links[(r[a],r[b])]+=r['value']
        left={n:nodes[(a,n)][0] for n in totals[a]};right={n:nodes[(b,n)][0] for n in totals[b]}
        for (s,t),v in sorted(links.items(),key=lambda item:(nodes[(a,item[0][0])][0],nodes[(b,item[0][1])][0])):
            h=v*scale;ribbons.append(dict(left=(a,s),right=(b,t),left_y=left[s],right_y=right[t],height=h,value=v))
            left[s]+=h;right[t]+=h
    return nodes,ribbons


def draw(flows, color):
    import matplotlib.pyplot as plt
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch,Rectangle
    nodes,ribbons=layout(flows);xs={'source':.12,'pathway':.5,'target':.88};width=.015
    fig,ax=plt.subplots(figsize=(183/25.4,120/25.4),layout='constrained')
    for edge in ribbons:
        a,b=edge['left'],edge['right'];x0,x1=xs[a[0]]+width,xs[b[0]]-width
        y0,y1,h=edge['left_y'],edge['right_y'],edge['height'];middle=(x0+x1)/2
        verts=[(x0,y0),(middle,y0),(middle,y1),(x1,y1),(x1,y1+h),(middle,y1+h),(middle,y0+h),(x0,y0+h),(x0,y0)]
        codes=[Path.MOVETO,Path.CURVE4,Path.CURVE4,Path.CURVE4,Path.LINETO,Path.CURVE4,Path.CURVE4,Path.CURVE4,Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts,codes),facecolor=color(a[1]),edgecolor='none',alpha=.35))
    for (kind,name),(y,h) in nodes.items():
        ax.add_patch(Rectangle((xs[kind]-width,y),2*width,h,facecolor=color(name),edgecolor='white',lw=.3))
        ax.text(xs[kind],y+h/2,textwrap.fill(name,20),ha='center',va='center',fontsize=6,
                bbox=dict(facecolor='white',alpha=.9,edgecolor='none',pad=.8))
    for kind,title in [('source','Sender'),('pathway','Pathway'),('target','Receiver')]:ax.text(xs[kind],1.04,title,ha='center',fontsize=7)
    ax.set(xlim=(-.04,1.04),ylim=(-.03,1.1));ax.set_axis_off()
    return fig


def grouped_circos(rows,color):
    """Outer cell/role ring, inner pathway ring, native additive directed chords."""
    from pycirclize import Circos
    from matplotlib.patches import Patch
    flows,selection=pathway_flows(rows,limit=3)
    sources=selection.get('selected',{}).get('source',[])[:2]
    targets=selection.get('selected',{}).get('target',[])[:2]
    flows=[r for r in flows if r['source'] in sources and r['target'] in targets]
    if not flows:return None,[],selection
    totals=defaultdict(float)
    for r in flows:
        totals[('Sender',r['source'],r['pathway'])]+=r['value']
        totals[('Receiver',r['target'],r['pathway'])]+=r['value']
    ordered=sorted(totals,key=lambda k:(k[0]=='Receiver',k[1],k[2]))
    names={key:f'sector_{i}' for i,key in enumerate(ordered)}
    spaces=[8 if i==len(ordered)-1 or ordered[i][:2]!=ordered[i+1][:2] else 1 for i in range(len(ordered))]
    circos=Circos({names[k]:totals[k] for k in ordered},space=spaces)
    groups=defaultdict(list)
    for key in ordered:
        sector=circos.get_sector(names[key]);groups[key[:2]].append(sector)
        track=sector.add_track((89,96));track.axis(fc=color(key[2]),ec='white',lw=.4)
    for (role,cell),sectors in groups.items():
        start,end=sectors[0].deg_lim[0],sectors[-1].deg_lim[1]
        circos.rect((99,103),deg_lim=(start,end),fc=color(cell),ec='none')
        circos.text(textwrap.fill(cell,22)+'\n'+role,r=111,deg=(start+end)/2,adjust_rotation=True,fontsize=6)
    offset={key:0. for key in ordered}
    for r in flows:
        a=('Sender',r['source'],r['pathway']);b=('Receiver',r['target'],r['pathway']);v=r['value']
        circos.link((names[a],offset[a],offset[a]+v),(names[b],offset[b],offset[b]+v),r1=88,r2=88,
                    color=color(r['pathway']),alpha=.4,direction=1,arrow_length_ratio=.03)
        offset[a]+=v;offset[b]+=v
    fig=circos.plotfig(figsize=(183/25.4,150/25.4));circos.ax.set_ylim(0,123)
    pathways=sorted({r['pathway'] for r in flows})
    fig.legend(handles=[Patch(facecolor=color(p),label=p) for p in pathways],loc='lower center',ncol=3,frameon=False,fontsize=6)
    selection['grouped_circos']=dict(sources=sources,targets=targets,pathways=pathways,displayed_score=sum(r['value'] for r in flows),
                                     rule='发送/接收各前2群、前3通路的共同子图；外环细胞角色、内环通路，扇区长度和带宽同一原生分数尺度')
    return fig,flows,selection
