"""Registered method dispatch; no arbitrary shell or fabricated algorithm fallback."""
from __future__ import annotations
import html
import base64
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from communication_contract import lookup_method,new_output,write_json,digest,load_bundle

RUNNERS={"spacenet":"run_spacenet.py","liana":"run_liana.py","cellphonedb":"run_cellphonedb.py","tensor-cell2cell":"run_tensor.py","cell2cell":"run_cell2cell.py","disir":"run_disir.py","sctenifoldxct":"run_sctenifoldxct.py",
         "fastccc":"run_fastccc.py","spatialdm":"run_spatialdm.py","commot":"run_commot.py","mebocost":"run_mebocost.py","flowsig":"run_flowsig.py","scconnect":"run_scconnect.py","natmi":"run_natmi.py","squidpy":"run_squidpy.py","spaotsc":"run_spaotsc.py","trasig":"run_trasig.py","stlearn":"run_stlearn.py","scotia":"run_scotia.py","svca":"run_svca.py","ncem":"run_ncem.py","nichecompass":"run_nichecompass.py","holonet":"run_holonet.py","spacia":"run_spacia.py","cellnest":"run_cellnest.py","renoir":"run_renoir.py","spaci":"run_spaci.py","cscp":"run_cscp.py","mdic3":"run_mdic3.py","deepcolor":"run_deepcolor.py","cellagentchat":"run_cellagentchat.py"}


def shared_plot_config(bundle_path,out,state,cfg):
    """Keep an entity's color unchanged as later methods add their observations."""
    bundle,tables=load_bundle(bundle_path)
    palette=state.setdefault('colors',dict(cfg.get('colors',{})))
    specified=bundle.get('colors',bundle['provenance'].get('parameters',{}).get('colors',{}))
    for name,value in specified.items():palette.setdefault(name,value)
    names=sorted({r[k] for spec,rows,_ in tables for r in rows for k in ('source','target','condition')
                  if r.get(k) and (k=='condition' or spec['type'] in ('lr_edges','metabolite_edges','network'))})
    colors=['#4477AA','#EE6677','#228833','#CCBB44','#66CCEE','#AA3377','#BBBBBB','#332288','#44AA99','#999933','#882255','#661100','#6699CC','#DDCC77','#117733','#CC6677','#88CCEE','#AA4499','#DDDDDD','#000000']
    for name in names:
        if name not in palette:
            unused=[color for color in colors if color not in palette.values()]
            palette[name]=unused[0] if unused else colors[len(palette)%len(colors)]
    plot={key:cfg[key] for key in ('top_lr','top_factor_features','focus') if key in cfg};plot['colors']=palette
    path=out/'shared_plot_config.json';write_json(path,plot)
    return str(path)


def peer_script(cfg, skill_id, name):
    supplied=cfg.get("skill_roots",{}).get(skill_id)
    candidates=[Path(supplied)] if supplied else list(Path(__file__).resolve().parents[2].iterdir())
    for root in candidates:
        definition=root/"SKILL.md"
        front=definition.read_text().split("---",2) if definition.is_file() else []
        if len(front)==3 and f"name: {skill_id}" in front[1]:
            script=root/"scripts"/name
            if script.is_file():return script
    raise ValueError(f"未安装依赖 skill {skill_id} 或其脚本；用 skill_roots 提供实际安装目录")


def run(config,output,rscript="Rscript"):
    config=Path(config).resolve();cfg=json.loads(config.read_text());out=new_output(output)
    if not cfg.get("dataset") or not cfg.get("research_question") or not cfg.get("methods"):
        raise ValueError("多方法任务需要 dataset/research_question/methods")
    state=dict(schema_version=2,status="running",methods=[],contexts=[],figures=[],config_sha256=digest(config))
    write_json(out/"run_config.json",cfg)
    for index,request in enumerate(cfg["methods"]):
        entry=dict(method=request.get("method"),status="failed")
        state["methods"].append(entry)
        folder=out/f"method_{index+1:03d}"
        try:
            plot_cfg={**cfg}
            if 'focus' in request:plot_cfg['focus']=request['focus']
            method=lookup_method(request["method"])
            entry['adapter_status']=method['execution_status']
            reuse=request.get("bundle")
            if method["runner"] is None and not reuse:
                audit=[sys.executable,str(Path(__file__).with_name('audit_communication_method.py')),
                       '--method',method['id'],'--out',str(folder)]
                source=request.get('config',{}).get('source_root') or request.get('config',{}).get('native_root')
                if source:
                    source=Path(source)
                    source=(config.parent/source).resolve() if not source.is_absolute() else source.resolve()
                    audit.extend(['--source-root',str(source)])
                result=subprocess.run(audit,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=False)
                entry.update(directory=folder.name,audit_returncode=result.returncode,
                             readiness=str((folder/'readiness.json').relative_to(out)) if (folder/'readiness.json').is_file() else None)
                raise ValueError(f"{method['name']} 当前仅有方法定位资料，没有原生适配器；这是实现缺口，不能以其他方法代替。就绪核验见 {entry.get('readiness') or result.stdout.strip()}")
            local_cfg={**cfg.get("defaults",{}),**request.get("config",{}),"dataset":cfg["dataset"],"research_question":cfg["research_question"]}
            if method['runner']=='cellchat' and not reuse and request.get('comparison'):
                local_cfg['comparison']=request['comparison']
            if method['runner']=='scseqcomm':
                local_cfg['mode']='differential' if method['name']=='scSeqCommDiff' else 'within_sample'
            for key in ("input","object","expression","metadata","grn","database","database_config","resource_file","gene_programs","bundle","reuse_bundle","reuse_directory","r_library","scriabin_library","native_root","pcst_root","embedding_file","external_input","sender_expression","receiver_expression","single_cell_input","lr_database","lr_resource","conversion_rate_file","candidate_table","cell_mixtures","ligand_receptor","ligand_receptor_resource","ligand_target_resource","celltype_proportions","spatial_input","reference_input","receptor_target","tf_database","lr_resources","microenvs_file_path","active_tfs_file_path","seurat","cds","mra","rscript"):
                if key in local_cfg:
                    value=Path(local_cfg[key])
                    # Some adapters use `database` as a registered resource name
                    # (for example OmniPath), while others use it as a path.
                    if key=='database' and not value.is_absolute() and not (config.parent/value).exists():
                        continue
                    local_cfg[key]=str((config.parent/value).resolve())
            if "r_libraries" in local_cfg:
                local_cfg["r_libraries"]=[str((config.parent/path).resolve()) for path in local_cfg["r_libraries"]]
            for python_key in ('magic_python','contrast_python','pcst_python'):
                if python_key not in local_cfg:continue
                # Preserve the venv executable symlink rather than resolving it
                # to the base interpreter outside that environment.
                local_cfg[python_key]=str((config.parent/local_cfg[python_key]).absolute())
            if "samples" in local_cfg and local_cfg["samples"] and isinstance(local_cfg["samples"][0],dict):
                for sample in local_cfg["samples"]:
                    for key in ("input","object"):
                        if key in sample:sample[key]=str((config.parent/sample[key]).resolve())
            path=out/f"method_{index+1:03d}.json";write_json(path,local_cfg)
            runner=method["runner"]
            python=request.get("python",cfg.get("python",sys.executable))
            if not Path(python).is_absolute():python=str((config.parent/python).absolute())
            if reuse:
                bundle_path=(config.parent/reuse).resolve()
                bundle,_=load_bundle(bundle_path)
                actual=lookup_method(bundle['method'])
                if actual.get('equivalent_execution',actual['id'])!=method.get('equivalent_execution',method['id']):
                    raise ValueError('既有结果包的方法与所请求方法不一致')
                if bundle['dataset']!=cfg['dataset']:
                    raise ValueError('既有结果包的数据集与本任务不一致')
                new_output(folder)
                command=[cfg.get('renderer_python',sys.executable),str(Path(__file__).with_name('render_result_bundle.py')),
                         '--bundle',str(bundle_path),'--out',str(folder/'figures'),'--plot-config',shared_plot_config(bundle_path,out,state,plot_cfg)]
                entry['reused_bundle_sha256']=digest(bundle_path)
            elif runner in ("nichenet","multinichenet"):
                for key in (("lr_network","ligand_target_matrix","gene_set") if runner=='nichenet' else ("lr_network","ligand_target_matrix")):
                    local_cfg[key]=str((config.parent/local_cfg[key]).resolve())
                write_json(path,local_cfg)
                script=peer_script(cfg,"single-cell-virtual-cell-workflow","run_"+runner+".R")
                command=[rscript,str(script),str(path),str(folder)]
            elif runner in ("neuronchat","cellcall","cellcallext","singlecellsignalr","scdiffcom","italk","icellnet","scseqcomm","connectome","celltalker","commpath","sclr","comunet","crosstalker","domino","sctensor","rnamagnet","exfinder","nichede","sccomm","timetalk","scmlnet","cytotalk","cellcomm","soptsc","scriabin","giotto","spacci","stmlnet","remi"):
                command=[rscript,str(Path(__file__).with_name("run_"+runner+".R")),str(path),str(folder)]
            elif runner in ('spatalk','misty'):
                script=peer_script(cfg,'06-spatial-omics-spatial-microenvironment','run_'+runner+'.R')
                command=[rscript,str(script),str(path),str(folder)]
            elif runner=="cellchat":
                command=[python,str(Path(__file__).with_name("run_communication.py")),"--config",str(path),"--out",str(folder),"--rscript",rscript]
            else:
                if runner not in RUNNERS:raise ValueError("执行器未在代码白名单中注册")
                command=[python,str(Path(__file__).with_name(RUNNERS[runner])),"--config",str(path),"--out",str(folder)]
            with (out/f"method_{index+1:03d}.log").open("w") as log:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=request.get("timeout_seconds",86400),check=False)
                evidence_bundle=bundle_path if reuse else folder/'bundle.json'
                if result.returncode==0 and evidence_bundle.is_file():
                    from prioritize_communication import run as prioritize
                    try:
                        prioritize(evidence_bundle,folder/'prioritization',request.get('focus',cfg.get('focus')))
                        entry['prioritization']=str((folder/'prioritization/prioritization.json').relative_to(out))
                    except Exception as error:
                        entry['prioritization_error']=str(error)
                if result.returncode==0 and (folder/"bundle.json").exists() and not (folder/"figures/figure_manifest.json").exists():
                    result=subprocess.run([cfg.get("renderer_python",sys.executable),str(Path(__file__).with_name("render_result_bundle.py")),
                        "--bundle",str(folder/"bundle.json"),"--out",str(folder/"figures"),'--plot-config',shared_plot_config(folder/'bundle.json',out,state,plot_cfg)],stdout=log,stderr=subprocess.STDOUT,check=False,timeout=request.get("timeout_seconds",86400))
                if result.returncode==0 and request.get('comparison') and (runner!='cellchat' or reuse):
                    comparison={**request['comparison'],'bundle':str(bundle_path if reuse else folder/'bundle.json')}
                    comparison_path=out/f'method_{index+1:03d}_comparison.json';write_json(comparison_path,comparison)
                    result=subprocess.run([cfg.get('renderer_python',sys.executable),str(Path(__file__).with_name('run_bundle_contrasts.py')),
                        '--config',str(comparison_path),'--out',str(folder/'comparison')],stdout=log,stderr=subprocess.STDOUT,check=False,
                        timeout=request.get('timeout_seconds',86400))
            entry.update(directory=folder.name,returncode=result.returncode,
                         status="generated_pending_visual_review" if result.returncode==0 and not entry.get('prioritization_error') else "failed_or_partial")
            for manifest_path in (folder/"figure_manifest.json",folder/"figures/figure_manifest.json",folder/'comparison/figures/figure_manifest.json'):
                if manifest_path.is_file():
                    manifest=json.loads(manifest_path.read_text());entry["delivery_status"]=manifest.get("status")
                    for figure in manifest.get("figures",[]):
                        figure={**figure,"method":method["name"]}
                        figure["files"]=[str((manifest_path.parent/p).relative_to(out)) for p in figure.get("files",[])]
                        if figure.get('preview'):figure['preview']=str((manifest_path.parent/figure['preview']).relative_to(out))
                        if figure.get("source_data"):figure["source_data"]=str((manifest_path.parent/figure["source_data"]).relative_to(out))
                        state["figures"].append(figure)
        except Exception as error:
            entry["error"]=str(error)
            if entry.get('adapter_status')=='documented' and entry.get('readiness'):
                entry['status']='documented_not_executable'
        write_json(out/"figure_manifest.json",state)
    if cfg.get('functional_scores'):
        entry=dict(method='UCell functional context',status='failed')
        state['contexts'].append(entry)
        folder=out/'functional_scores'
        try:
            context={**cfg['functional_scores'],'dataset':cfg['dataset'],'research_question':cfg['research_question']}
            for key in ('input','gmt','reuse_directory'):
                if key in context:context[key]=str((config.parent/context[key]).resolve())
            context_path=out/'functional_scores.json';write_json(context_path,context)
            with (out/'functional_scores.log').open('w') as log:
                result=subprocess.run([rscript,str(Path(__file__).with_name('run_functional_scores.R')),str(context_path),str(folder)],
                    stdout=log,stderr=subprocess.STDOUT,check=False,timeout=context.get('timeout_seconds',86400))
                if result.returncode==0:
                    result=subprocess.run([cfg.get('renderer_python',sys.executable),str(Path(__file__).with_name('render_result_bundle.py')),
                        '--bundle',str(folder/'bundle.json'),'--out',str(folder/'figures'),'--plot-config',shared_plot_config(folder/'bundle.json',out,state,cfg)],
                        stdout=log,stderr=subprocess.STDOUT,check=False,timeout=context.get('timeout_seconds',86400))
            entry.update(directory=folder.name,returncode=result.returncode,status='generated_pending_visual_review' if result.returncode==0 else 'failed_or_partial')
            manifest_path=folder/'figures/figure_manifest.json'
            if manifest_path.is_file():
                manifest=json.loads(manifest_path.read_text())
                entry['delivery_status']=manifest.get('status')
                for figure in manifest.get('figures',[]):
                    figure={**figure,'method':'UCell functional context'}
                    figure['files']=[str((manifest_path.parent/p).relative_to(out)) for p in figure.get('files',[])]
                    if figure.get('preview'):figure['preview']=str((manifest_path.parent/figure['preview']).relative_to(out))
                    if figure.get('source_data'):figure['source_data']=str((manifest_path.parent/figure['source_data']).relative_to(out))
                    state['figures'].append(figure)
        except Exception as error:
            entry['error']=str(error)
    state["status"]="generated_pending_visual_review" if all(m["status"]=="generated_pending_visual_review" for m in state["methods"]+state['contexts']) else "partial"
    write_json(out/"figure_manifest.json",state)
    write_gallery(out,cfg,state)
    return 0 if state["status"]=="generated_pending_visual_review" else 2


def write_gallery(out,cfg,state):
    sections=["<!doctype html><meta charset='utf-8'><title>细胞通讯图集</title>","<style>body{font:16px sans-serif;max-width:1100px;margin:40px auto}img{width:100%;max-width:760px}article{margin:40px 0}</style>",
              "<h1>"+html.escape(cfg["dataset"])+"</h1><p>"+html.escape(cfg["research_question"])+"</p>",
              "<p>预览图片已包含在本文件中。可编辑 PDF/SVG 与源表保存在对应方法目录，可从文件面板打开。</p>"]
    statuses={'generated_pending_visual_review':'图件已生成，待逐图审阅','failed':'未完成','failed_or_partial':'部分完成或运行失败',
              'documented_not_executable':'方法已核验，当前不具备原生执行条件'}
    for entry in state['methods']+state.get('contexts',[]):
        detail=entry.get('error','')
        sections.append('<p><strong>'+html.escape(entry['method'])+'</strong>：'+html.escape(statuses.get(entry['status'],entry['status']))+('；'+html.escape(detail) if detail else '')+'</p>')
    for fig in state["figures"]:
        if fig["status"]!="generated":continue
        labels=[('bubble','分子与细胞对证据点图'),('chord','焦点通讯弦图'),('hierarchy','发送与接收关联网络'),('ranking','候选活性排序'),('vectors','空间通讯方向'),('hotspot','局部空间关联'),('pattern','通讯模式'),('heatmap','通讯热图')]
        label=next((title for key,title in labels if key in fig['id']),'通讯结果图')
        sections.append('<article><h2>'+html.escape(fig.get('method','')+' · '+label)+'</h2>')
        for path in fig["files"]:
            if path.endswith(".png"):
                encoded=base64.b64encode((out/fig.get('preview',path)).read_bytes()).decode('ascii')
                sections.append('<img loading="lazy" alt="'+html.escape(fig['id'],quote=True)+'" src="data:image/png;base64,'+encoded+'">')
            else:sections.append('<a href="'+html.escape(path,quote=True)+'">'+html.escape(Path(path).suffix)+'</a> ')
        sections.append("<p>"+html.escape(fig.get("caption",""))+"</p></article>")
    (out/"index.html").write_text("\n".join(sections))
