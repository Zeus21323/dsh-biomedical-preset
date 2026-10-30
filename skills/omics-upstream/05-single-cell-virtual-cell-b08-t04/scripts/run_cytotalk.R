#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
if(length(args)!=2) stop('需要配置JSON与新的仓库外输出目录')
if(!requireNamespace('jsonlite',quietly=TRUE)) stop('缺少jsonlite')
pre_cfg<-jsonlite::read_json(args[1],simplifyVector=TRUE)
if(is.null(pre_cfg$pcst_python)) stop('缺少：pcst_python')
python_path<-if(startsWith(pre_cfg$pcst_python,'/'))pre_cfg$pcst_python else file.path(dirname(normalizePath(args[1])),pre_cfg$pcst_python)
if(!file.exists(python_path)) stop('pcst_python不存在')
python_path<-file.path(normalizePath(dirname(python_path)),basename(python_path))
venv_root<-normalizePath(dirname(dirname(python_path)))
Sys.setenv(RETICULATE_PYTHON=python_path,VIRTUAL_ENV=venv_root)
if(!requireNamespace('reticulate',quietly=TRUE)) stop('缺少reticulate')
reticulate::use_virtualenv(venv_root,required=TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg))
source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'CytoTalk','Matrix','1.7.6',counts_input=FALSE,species=c('human','mouse'));cfg<-c$cfg
for(key in c('native_root','pcst_root','input_provenance','resource_provenance','threshold_provenance')) if(is.null(cfg[[key]])) stop('缺少：',key)
if(!requireNamespace('CytoTalk',quietly=TRUE)||as.character(packageVersion('CytoTalk'))!='0.99.9') stop('需要固定CytoTalk 0.99.9')
for(pkg in c('reticulate','digest','infotheo','parmigene')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)

root<-c$resolve(cfg$native_root);pcst_root<-c$resolve(cfg$pcst_root)
expected_files<-c(
  'R/analysis.R'='45ef62292c78c71b2ad7d4a680b02564ba433db3a8579ecde9921d722638a395',
  'R/cytotalk.R'='04fbda18ebb9c4042546e06d2161170d583338ed58850b9a7684e92f1b90be4e',
  'R/integrated.R'='64800e0fb1f63c3ceaa08730239e5c43a1f2dad71b71cee104c5a8d2374be575',
  'R/matrix.R'='378ddf8b1fec2db6d8627fd9dea82f5c11fea5bf57cf14a6ad318fcd9effb19a',
  'R/mutinfo.R'='3c3cc920bc02deb1651cefa6e2de0a4b7241ad5fc83de692a450efc67bad57d6',
  'R/pcst.R'='8170c2117de7306234ff73b1cb01ffa6c0bcbeb5c9e5dc4a8a4290c38b580fcc',
  'R/pem.R'='3fe467568dccee5a7af51210827384ab7d0d3b6c5b5935985e5fd980dc0c5ef1')
for(path in names(expected_files)) if(c$hash(file.path(root,path))!=expected_files[[path]]) stop('CytoTalk源码摘要不符：',path)
expected_bodies<-c(run_cytotalk='b3f937e2b90c7668929f500e705e4dfdbbd441d32e43f0c17b9403636331ed25',
  pem='54ebddedf20147eda08061e7e97f44bf0a3a03f4d2e7f05a1c3e2337a1df4ad2',nonselftalk='2de96360d6a8b2b82d5ff25b72635853c3f796b89e82ef681ccc6a4597045957',
  mi_mat_parallel='4cddbcc49d184ba39289f338ecec1acc2ddf29ca61ed50161fcf87bcca98b51b',integrate_network='fbb212ea521fe5c4102c55c897ff1f6e5b1b0430abf6d858e2e0017827cc7a93',
  run_pcst='4844c2b8c3b7a1102f707dff18d5529a1a22bc704528fa03bbc0dd443361c157',ks_test_pcst='4c6fe51e5277380aa373338a3d167f953e5810124be145dd9a93879cf785b5e7',
  extract_network='bb16045a36a17bc5b694d6fecc932220d725d5cb0c9f0fb2e7785fb874a819e3',extract_pathways='b3ec4d6c169139e4aaedd7412d389528e9f0a8e5adb6cbbd895d5d2c9b65dd2a',
  analyze_pathway='a0f219b2816683254c6870924dd7390fd2acc4646d58eacc4f220aebdbf2e961')
for(name in names(expected_bodies)){
  body_hash<-digest::digest(paste(deparse(body(getFromNamespace(name,'CytoTalk')),width.cutoff=500L),collapse='\n'),algo='sha256',serialize=FALSE)
  if(body_hash!=expected_bodies[[name]]) stop('安装的CytoTalk函数与固定源码不一致：',name)
}
pcst_manifest<-file.path(pcst_root,'pyproject.toml')
if(c$hash(pcst_manifest)!='9e4e4d2a9a60f90c48d1a3190e0de74f65dba45c8f76cd6c2929bc40d201f952') stop('pcst_fast源码摘要不符')
actual_python<-normalizePath(reticulate::py_config()$python)
if(actual_python!=normalizePath(python_path)) stop('reticulate未使用配置指定的pcst_python')
pcst_module<-reticulate::import('pcst_fast',convert=TRUE)
pcst_binary<-normalizePath(reticulate::py_to_r(pcst_module$`__file__`))
if(c$hash(pcst_binary)!='ac9890eca8df7e839f863065d7a0cab9d7f0f1d446c7be17d52341984f8da0c4') stop('需要已核验的pcst-fast 25ab31a Python 3.12 arm64构建')
pcst_version<-'1.0.11.dev3+g25ab31a24'

resource_names<-if(cfg$species=='mouse')c(lrp='data/lrp_mouse.rda',pcg='data/pcg_mouse.rda') else c(lrp='data/lrp_human.rda',pcg='data/pcg_human.rda')
expected_resources<-if(cfg$species=='mouse')c(lrp='b564b5b587ec12a16794af60fac67b9504f8822a706ef2b4402d17ae8efe0c14',pcg='2d0c92900ec671cf46917aa6303209847e855ee33e9d021c1d7757d003648c16') else c(lrp='4887eb3f7b0ca7d5d5a6ef2ab0cdbf0b6289e28663164c9aae1ce3ea0be89db7',pcg='f86e0229d0dfcc7766e116d46577f8d04bd993b0fa1c51f6b88fdb36923ffcc7')
resources<-setNames(file.path(root,unname(resource_names)),names(resource_names))
for(name in names(resources)) if(c$hash(resources[[name]])!=expected_resources[[name]]) stop('CytoTalk资源摘要不符：',name)
env<-new.env(parent=emptyenv());load(resources[['lrp']],envir=env);load(resources[['pcg']],envir=env)
lrp<-env[[paste0('lrp_',cfg$species)]];pcg<-env[[paste0('pcg_',cfg$species)]]
if(!all(c('ligand','receptor')%in%names(lrp))||anyNA(lrp)||any(trimws(as.matrix(lrp))=='')||anyDuplicated(lrp)) stop('LR资源身份无效')
if(!length(pcg)||anyNA(pcg)||anyDuplicated(pcg)) stop('protein-coding gene资源无效')

cell_a<-cfg$cell_type_a%||%stop('缺少：cell_type_a');cell_b<-cfg$cell_type_b%||%stop('缺少：cell_type_b')
if(cell_a==cell_b||grepl('_',cell_a,fixed=TRUE)||grepl('_',cell_b,fixed=TRUE)) stop('两个细胞类型须不同且不能含下划线；这是上游节点身份分隔约束')
samples<-unique(c$meta$sample);if(length(samples)!=1L) stop('CytoTalk原生一次只构建一个池化样本的两细胞群网络；多样本须分别执行')
if(!all(c(cell_a,cell_b)%in%c$meta$cell_type)) stop('输入缺少指定的两个细胞类型')
# PEM以同一样本的全部注释群为背景；排除无关群会改变目标两群的
# preferential-expression值和PCST节点prize，因此必须保留完整样本。
ids<-rownames(c$meta)[c$meta$sample==samples[[1]]];meta<-c$meta[ids,,drop=FALSE];expr<-c$expr[,ids,drop=FALSE]
if(sum(meta$cell_type==cell_a)<c$minimum||sum(meta$cell_type==cell_b)<c$minimum) stop('发送或接收群细胞数不足')
cutoff_a<-as.numeric(cfg$cutoff_a%||%.2);cutoff_b<-as.numeric(cfg$cutoff_b%||%.2);beta_max<-as.integer(cfg$beta_max%||%100L)
omega_min<-as.numeric(cfg$omega_min%||%.5);omega_max<-as.numeric(cfg$omega_max%||%.5);depth<-as.integer(cfg$depth%||%3L)
ntrial<-as.integer(cfg$ntrial%||%1000L);cores<-as.integer(cfg$cores%||%1L);seed<-as.integer(cfg$seed%||%20260909L);alpha<-as.numeric(cfg$alpha%||%.05)
if(any(!is.finite(c(cutoff_a,cutoff_b,omega_min,omega_max,alpha)))||any(c(cutoff_a,cutoff_b)<0)||any(c(cutoff_a,cutoff_b)>1)||
   beta_max<2||beta_max>1000||omega_min<=0||omega_max<omega_min||depth<1||depth>10||ntrial<100||cores<1||cores>16||is.na(seed)||alpha<=0||alpha>=1) stop('CytoTalk参数无效')
params<-list(commit='451adfa50e6af4c38d29cbb9fc0c0139a5d3c3c5',pcst_commit='25ab31a245b2278848b5a8814924cdb3039b4279',
  cell_type_a=cell_a,cell_type_b=cell_b,cutoff_a=cutoff_a,cutoff_b=cutoff_b,beta_max=beta_max,omega_min=omega_min,omega_max=omega_max,
  depth=depth,ntrial=ntrial,cores=cores,seed=seed,alpha=alpha,pem_context_cell_types=sort(unique(meta$cell_type)),versions=list(CytoTalk=as.character(packageVersion('CytoTalk')),Matrix=as.character(packageVersion('Matrix')),infotheo=as.character(packageVersion('infotheo')),parmigene=as.character(packageVersion('parmigene'))))
c$start_cache(c(vapply(resources,c$hash,''),unname(expected_files),c$hash(pcst_manifest)),params)
c$bundle$method_version<-'0.99.9'
c$bundle$implementation<-'native_run_cytotalk_pinned_rng_and_pcst'
c$bundle$provenance$upstream<-list(url='https://github.com/tanlabcode/CytoTalk',commit=params$commit,license='MIT')
c$bundle$provenance$pcst_fast<-list(url='https://github.com/fraenkel-lab/pcst_fast',commit=params$pcst_commit,version=pcst_version,binary_sha256=c$hash(pcst_binary),license='GPL-3.0')
c$bundle$provenance$resource_hashes<-as.list(vapply(resources,c$hash,''))
c$bundle$provenance$semantics<-paste('CytoTalk以同一样本全部注释细胞群计算PEM背景，再按检测比例过滤目标两群的蛋白编码基因，对两群分别离散化并以互信息/ARACNE形成胞内网络；节点prize结合PEM与LR随机游走相关性，跨细胞边结合PEM与non-self-talk。',
  'pcst_fast在beta/omega网格上求prize-collecting Steiner forest，作者以节点出现分布KS检验最小P选择最终网络。路径P值不是直接经验尾概率：随机抽取节点prize和边cost后拟合平移Gamma分布，再求参数化尾概率。',
  '随机零值微扰和路径模拟由显式seed固定；结果仍是池化细胞网络，不是供体差异或因果方向。')

set.seed(seed)
native<-c$native(1,samples[[1]],function(){
  lst<-list(mat=expr,cell_types=meta$cell_type)
  CytoTalk::run_cytotalk(lst,cell_a,cell_b,cutoff_a=cutoff_a,cutoff_b=cutoff_b,pcg=pcg,lrp=lrp,beta_max=beta_max,
    omega_min=omega_min,omega_max=omega_max,depth=depth,ntrial=ntrial,cores=cores,echo=TRUE,dir_out=NULL)
})
if(!all(c('params','pem','integrated_net','pcst','pathways')%in%names(native))) stop('原生返回结构不完整')
nodes<-native$integrated_net$nodes;integrated_edges<-native$integrated_net$edges;final<-native$pcst$final_network;pcst_scores<-native$pcst$ks_test_pval
if(!all(c('node','prize','pem','gene_relevance')%in%names(nodes))||!all(c('node1','node2','cost')%in%names(integrated_edges))||
   !all(c('node1','node2','node1_type','node2_type','node1_prize','node2_prize','node1_pem','node2_pem','is_ct_edge','cost')%in%names(final))) stop('原生网络字段不完整')
for(x in list(nodes[,c('prize','pem','gene_relevance')],integrated_edges['cost'],final[,c('node1_prize','node2_prize','node1_pem','node2_pem','cost')])) if(any(!is.finite(as.matrix(x)))) stop('原生入网数值含非有限值')
if(any(final$cost<0|final$cost>1)) stop('原生最终边cost超出[0,1]')

pathway_scores<-if(is.null(native$pathways))data.frame() else native$pathways$df_pval
if(nrow(pathway_scores)) pathway_scores$q_value_potential<-p.adjust(pathway_scores$pval_potential,'BH')
cross<-final[final$is_ct_edge,,drop=FALSE]
lr_rows<-data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),interaction=character(),score=numeric(),tested=logical(),supported=logical(),p_value=numeric(),q_value=numeric())
if(nrow(cross)){
  if(any(!mapply(function(lig,rec) any(lrp$ligand==lig&lrp$receptor==rec),cross$node1,cross$node2))) stop('原生跨细胞边不能映射回固定LR资源')
  lr_rows<-data.frame(sample=samples[[1]],source=cross$node1_type,target=cross$node2_type,ligand=cross$node1,receptor=cross$node2,
    interaction=paste(cross$node1,cross$node2,sep='→'),score=1-cross$cost,tested=FALSE,supported=FALSE,p_value=NA_real_,q_value=NA_real_,native_cost=cross$cost,native_network_member=TRUE)
  if(nrow(pathway_scores)) for(i in seq_len(nrow(lr_rows))){
    hit<-which(pathway_scores$ligand==lr_rows$ligand[i]&pathway_scores$receptor==lr_rows$receptor[i]&pathway_scores$ligand_type==lr_rows$source[i]&pathway_scores$receptor_type==lr_rows$target[i])
    if(length(hit)==1){lr_rows$tested[i]<-TRUE;lr_rows$supported[i]<-pathway_scores$q_value_potential[hit]<=alpha;lr_rows$p_value[i]<-pathway_scores$pval_potential[hit];lr_rows$q_value[i]<-pathway_scores$q_value_potential[hit]}
  }
}
links<-if(nrow(final))data.frame(source=final$node1,target=final$node2,
  source_type=final$node1_type,target_type=final$node2_type,value=1-final$cost,native_cost=final$cost,is_cross_cell=final$is_ct_edge,
  source_prize=final$node1_prize,target_prize=final$node2_prize,source_pem=final$node1_pem,target_pem=final$node2_pem) else data.frame(source=character(),target=character(),source_type=character(),target_type=character(),value=numeric())
activities<-data.frame(ligand=paste(sub('__.*$','',nodes$node),sub('^.*__','',nodes$node),sep=' | '),value=nodes$prize,pem=nodes$pem,gene_relevance=nodes$gene_relevance)
floor_p<-as.numeric(cfg$p_plot_floor%||%1e-300);if(!is.finite(floor_p)||floor_p<=0||floor_p>1) stop('p_plot_floor无效')
pcst_nodes<-native$pcst$occurances$nodes;pcst_edges<-native$pcst$occurances$edges
if(!all(c('beta','omega','node')%in%names(pcst_nodes))||!all(c('beta','omega','node1','node2')%in%names(pcst_edges))) stop('PCST occurrence字段不完整')
pcst_size<-do.call(rbind,lapply(seq_len(nrow(pcst_scores)),function(i){
  b<-pcst_scores$beta[i];o<-pcst_scores$omega[i]
  ni<-pcst_nodes$beta==b&pcst_nodes$omega==o&pcst_nodes$node!='ARTI'
  ei<-pcst_edges$beta==b&pcst_edges$omega==o&pcst_edges$node1!='ARTI'&pcst_edges$node2!='ARTI'
  data.frame(row=paste0('beta=',b),column=paste0('omega=',o,' | ',c('nodes','edges')),value=c(length(unique(pcst_nodes$node[ni])),sum(ei)))
}))
zero_p_ties<-sum(pcst_scores$pval==0,na.rm=TRUE);selected_i<-order(as.numeric(pcst_scores$pval))[1]
pcst_selection<-data.frame(selected_beta=pcst_scores$beta[selected_i],selected_omega=pcst_scores$omega[selected_i],selected_ks_p=pcst_scores$pval[selected_i],
  zero_p_underflow_ties=zero_p_ties,tested_grid_rows=nrow(pcst_scores),final_non_artificial_nodes=length(unique(c(final$node1,final$node2))),
  final_non_artificial_edges=nrow(final),final_cross_cell_edges=nrow(cross),selection_ambiguous_due_to_underflow=zero_p_ties>1)
pathway_evidence<-if(nrow(pathway_scores))do.call(rbind,lapply(seq_len(nrow(pathway_scores)),function(i)data.frame(row=paste(pathway_scores$ligand[i],pathway_scores$receptor[i],sep='→'),
  column=c('node prize','inverse edge cost','network potential'),value=-log10(pmax(c(pathway_scores$pval_prize[i],pathway_scores$pval_cost[i],pathway_scores$pval_potential[i]),floor_p))))) else data.frame(row=character(),column=character(),value=numeric())

c$add('cross_cell_ligand_receptor','lr_edges',lr_rows,'原生最终PCST网络中的跨细胞LR边；score=1−原生cost，仅在同一网络内表示较低代价。tested表示作者路径Gamma拟合已返回，supported表示该次全部路径的potential P经BH后不超过alpha；网络成员、统计支持与因果证据不可混称。',direction='higher',additive=FALSE,value_kind='nonnegative_affinity',axis_label='1 − native PCST edge cost',statistical_unit='pooled cells in one sample',test_definition='Random node-prize/edge-cost subsets followed by shifted-Gamma tail fit; BH across returned LR pathways')
c$add('final_signaling_network','molecular_links',links,'原生最优PCST最终网络，包括两细胞群内边和跨细胞LR边；value=1−cost，节点标签保留细胞类型身份。线宽只表示同一拟合网络的相对代价，不是表达通量或因果效应。',direction='higher',additive=FALSE,value_kind='nonnegative_affinity',axis_label='1 − native PCST edge cost')
c$add('final_node_prizes','activities',activities,'进入整合网络的节点prize；标签为细胞类型与基因。prize由PEM和相对LR的随机游走相关性共同形成，只用于该次PCST目标。',direction='higher',additive=FALSE,value_kind='native_node_prize',axis_label='Native PCST node prize')
c$add('pcst_network_size','matrix',pcst_size,'每个beta/omega候选PCST的非人工节点数和非人工边数。这个图用于检查网络随beta的增长和复杂度；它不是通讯强度。KS原始P和选择摘要另存，避免把浮点下溢的零P绘成饱和热图。',direction='higher',additive=FALSE,value_kind='count',axis_label='Non-artificial PCST members',display_top_rows=30)
c$add('pathway_gamma_evidence','matrix',pathway_evidence,'每条原生LR邻域对节点prize、逆向edge cost和network potential的平移Gamma拟合尾概率，显示−log10(P)；这是参数化拟合证据，不是供体检验或直接经验P。',direction='higher',additive=FALSE,value_kind='minus_log10_p',axis_label='−log10(shifted-Gamma tail P)',display_top_rows=30)

pem<-native$pem;pem[!is.finite(pem)]<-NA_real_;c$wt(data.frame(gene=rownames(pem),pem,check.names=FALSE),'pem_all_genes.tsv')
c$wt(nodes,'integrated_nodes.tsv');c$wt(integrated_edges,'integrated_edges.tsv');c$wt(pcst_nodes,'pcst_node_occurrences.tsv');c$wt(pcst_edges,'pcst_edge_occurrences.tsv');c$wt(pcst_scores,'pcst_scores_raw.tsv');c$wt(pcst_selection,'pcst_selection_summary.tsv');c$wt(final,'final_network_raw.tsv')
if(nrow(pathway_scores))c$wt(pathway_scores,'pathway_scores_raw.tsv') else c$wt(data.frame(ligand=character(),receptor=character()),'pathway_scores_raw.tsv')
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$limitations<-c('作者内置示例的矩阵尺度没有在数据文档中定义；必须以author-distributed transformed matrix记录，不能称原始counts。','零表达LR行会加入1e-20随机微扰；入口固定seed保证可复现，但微扰仍是作者数值策略。','beta选择KS P未校正；路径P来自随机子网分数的平移Gamma拟合，不是独立供体或直接经验尾概率。',paste0('KS P中有',zero_p_ties,'个值浮点下溢为0；作者的首个最小值规则返回beta=',pcst_scores$beta[selected_i],'，但该选择在数值上存在并列歧义，不得解释为唯一最优beta。'),'一次运行只有一个池化样本和两个细胞群，多条件研究必须逐样本运行并在供体层比较。')
c$wj(c$bundle,'bundle.json')
c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',sample=samples[[1]],cell_type_a=cell_a,cell_type_b=cell_b,seed=seed),'run_metadata.json')
