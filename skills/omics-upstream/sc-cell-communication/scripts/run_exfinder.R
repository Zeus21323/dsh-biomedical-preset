#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
a<-commandArgs(TRUE);f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1]);source(file.path(dirname(normalizePath(f)),'native_expression_context.R'))
c<-native_expression_context(a,'exFINDER','exFINDER','1.0.0',species=c('human','mouse','zebrafish'))
suppressPackageStartupMessages(library(exFINDER));suppressPackageStartupMessages(library(igraph))
for(k in c('targets','target_provenance','receiving_groups','receptor_tf_cutoffs','cutoff_provenance'))if(is.null(c$cfg[[k]]))stop('缺少：',k)
targets<-c$cfg$targets;groups<-c$cfg$receiving_groups;cuts<-as.numeric(c$cfg$receptor_tf_cutoffs)
if(!is.character(targets)||!length(targets)||anyDuplicated(targets)||any(!targets%in%rownames(c$expr)))stop('targets须为事先定义且输入实际测量的唯一基因，不能用结果反选')
if(!is.character(groups)||!length(groups)||anyDuplicated(groups))stop('需要明确接收群')
if(length(cuts)!=2||any(!is.finite(cuts)))stop('receptor_tf_cutoffs须为两个有限的原生表达阈值')
ligands<-c$cfg$ligands;ligand_cutoff<-c$cfg$ligand_cutoff
if(is.null(ligands)==is.null(ligand_cutoff))stop('需明确提供ligands或使用原生ligand_cutoff推断，两者不能同时提供')
if(!is.null(ligands)&&(!is.character(ligands)||!length(ligands)||anyDuplicated(ligands)))stop('ligands须非空唯一列表')
if(!is.null(ligand_cutoff)&&(length(ligand_cutoff)!=1||!is.finite(ligand_cutoff)))stop('原生配体筛选阈值须有限，负数指最大群均值低于绝对阈值')
kh<-as.numeric(c$cfg$kh %||% 2);aci<-as.numeric(c$cfg$aci_parameters %||% rep(2,4));if(length(kh)!=1||!is.finite(kh)||kh<=0||length(aci)!=4||any(!is.finite(aci))||any(aci<=0))stop('Kh与四个AcI饱和参数必须为正')
db<-lapply(c('LR_layer1_','RTF_layer2_','TFT_layer3_'),function(prefix){name<-paste0(prefix,c$cfg$species);e<-new.env();data(list=name,package='exFINDER',envir=e);e[[name]]})
if(any(vapply(db,function(d)!is.data.frame(d)||!all(c('from','to')%in%names(d))||!nrow(d),logical(1))))stop('三层原生先验资源缺失')
external<-NULL
if(!is.null(c$cfg$external_input)){
 for(k in c('external_provenance','external_pooling_definition','external_expression_scale'))if(is.null(c$cfg[[k]]))stop('外部参考缺少：',k)
 if(c$cfg$external_expression_scale!=c$cfg$expression_scale)stop('外部与内部表达尺度须一致并有归一化依据')
 external<-readRDS(c$resolve(c$cfg$external_input));v<-external$expression;m<-external$metadata
 if(is.null(v)||is.null(m)||is.null(rownames(v))||is.null(colnames(v))||is.null(rownames(m))||!all(c('sample','donor','condition','cell_type')%in%names(m))||anyDuplicated(rownames(v))||anyDuplicated(colnames(v))||anyDuplicated(rownames(m))||!setequal(colnames(v),rownames(m)))stop('外部参考的expression/metadata身份无效')
 if(anyNA(m[,c('sample','donor','condition','cell_type')])||any(trimws(as.matrix(m[,c('sample','donor','condition','cell_type')]))==''))stop('外部参考元数据存在空身份')
 external$metadata<-m[colnames(v),,drop=FALSE];external$metadata$Type<-factor(external$metadata$cell_type)
 vv<-if(inherits(v,'sparseMatrix'))v@x else as.vector(as.matrix(v));if(any(!is.finite(vv))||any(vv<0)||any(table(external$metadata$Type)<2))stop('外部参考存在无效数值或细胞不足')
}
params<-list(targets=targets,groups=groups,cuts=cuts,ligands=ligands,ligand_cutoff=ligand_cutoff,ligand_groups=c$cfg$ligand_groups,kh=kh,aci=aci,minimum=c$minimum,external_sha256=if(is.null(external))NULL else c$hash(c$resolve(c$cfg$external_input)),external_groups=c$cfg$external_groups,overlap_rule='native fix_OverLap before numeric scoring')
c$start_cache(digest::digest(db,algo='sha256'),params)
c$bundle$provenance$upstream<-list(url='https://github.com/ChanghanGitHub/exFINDER',commit='516bcb946272ab313e3e3d802fef44d1fa51f80e',license='GPL-3.0')
c$bundle$provenance$molecule_identity_schema<-paste0(c$cfg$species,'-native-gene-role-v1')
c$bundle$provenance$semantics<-'原生三层先验、表达筛选与角色重叠裁剪构建外部配体→受体→原生TF角色层→靶基因图；原生TF角色可能包含非转录因子信号中介，图中以signaling展示并保留原角色；节点为指定接收群最大均值，边为乘积/(Kh+乘积)，最大流和AcI是模型量。没有外部表达时配体节点固定1；不是实测配体浓度、统计显著性或因果机制。'
for(j in 1:3)c$wt(db[[j]],paste0('resource_layer_',j,'.tsv'))
matrows<-function(m){d<-expand.grid(row=rownames(m),column=colnames(m));d$value<-as.vector(m);d}
for(i in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[i];m<-c$sample_meta(sample);m$Type<-factor(m$cell_type)
 if(any(!groups%in%levels(m$Type)))stop('样本缺少指定接收群：',sample)
 lg<-c$cfg$ligand_groups %||% groups;if(any(!lg%in%levels(m$Type)))stop('配体筛选群不存在')
 if(nrow(c$expr)*nrow(m)*8>(c$cfg$max_dense_bytes %||% 2^31))stop('原生get_AveExp需要稠密矩阵，超过内存契约')
 expr<-as.matrix(c$expr[,rownames(m),drop=FALSE])
 obj<-c$native(i,sample,function(){
  prior<-exFINDER::get_ltGRN(targets,db)
  if(!is.list(prior)||!nrow(prior$Graph.Edge))return(list(status='no_prior_path',prior=prior))
  selected<-if(is.null(ligands))exFINDER::get_potentialex(prior,expr,m,ligand_cutoff,lg) else ligands
  if(!length(selected))return(list(status='no_ligand_passes',prior=prior,selected=selected))
  graph<-exFINDER::get_exSigNet(prior,selected,expr,m,cuts,groups,groups)
  if(!is.list(graph)||!nrow(graph$Graph.Edge))return(list(status='no_expression_supported_graph',prior=prior,selected=selected))
  original<-graph;graph<-exFINDER::fix_OverLap(graph)
  if(anyDuplicated(graph$Graph.Node$Gene))stop('原生角色裁剪后基因身份仍不唯一，不能用match误配节点')
  if(!all(c('Ligand','Receptor','TF','Target')%in%graph$Graph.Node$Role))return(list(status='no_complete_role_graph',prior=prior,selected=selected,original=original,graph=graph))
  if(!is.null(external)&&prod(dim(external$expression))*8>(c$cfg$max_dense_bytes %||% 2^31))stop('外部参考超过原生稠密矩阵内存契约')
  graph<-exFINDER::get_NodeValue(graph,expr,m,groups,groups,groups,if(is.null(external))NULL else as.matrix(external$expression),if(is.null(external))NULL else external$metadata,c$cfg$external_groups)
  graph<-exFINDER::get_EdgeWeight(graph,kh)
  if(any(!is.finite(graph$Graph.Node$Size))||any(graph$Graph.Node$Size<0)||any(!is.finite(graph$Graph.Edge$Weight)))stop('原生节点/边评分无效')
  flow<-exFINDER::get_LRMaxFlow(graph);activity<-exFINDER::get_AcI(graph,aci)
  if(any(!is.finite(flow$MaxFlow))||!is.finite(activity))stop('原生最大流或AcI无效')
  list(status='scored',prior=prior,selected=selected,original=original,graph=graph,flow=flow,activity=activity,metadata=m)
 })
 c$wj(list(sample=sample,status=obj$status),paste0('scope_',i,'.json'))
 if(obj$status!='scored'){
  c$add(paste0('negative_',i),'matrix',data.frame(row=sample,column='Scored complete network',value=0),'原生先验或表达筛选未形成完整可评分网络；具体阶段见scope，不伪造边或P',value_kind='count',axis_label='Complete scored network count');next
 }
 c$wt(obj$prior$Graph.Edge,paste0('prior_edges_',i,'.tsv'));c$wt(obj$original$Graph.Edge,paste0('before_overlap_edges_',i,'.tsv'));c$wt(obj$graph$Graph.Node,paste0('nodes_',i,'.tsv'));c$wt(obj$graph$Graph.Edge,paste0('native_edges_',i,'.tsv'))
 edge<-obj$graph$Graph.Edge
 # The native TF layer also includes signaling intermediates (e.g. CAV1).
 # Keep its original role explicitly, without asserting TF identity in plots.
 display_role<-function(role)ifelse(role=='TF','signaling',tolower(role))
 er<-data.frame(source=edge$from,target=edge$to,source_type=display_role(edge$from.Role),target_type=display_role(edge$to.Role),source_native_role=edge$from.Role,target_native_role=edge$to.Role,value=edge$Weight)
 c$add(paste0('signal_layers_',i),'molecular_links',er,'原生四层先验和表达饱和边权；箭头是先验方向，不是守恒流量。原生TF层含信号中介，展示为signaling，未经独立转录因子身份确认；原角色另列保留。配体缺外部表达时固定1；完整网络及裁剪前对象另存',additive=FALSE,axis_label='Native modeled edge capacity',title=sample)
 c$add(paste0('ligand_target_flow_',i),'matrix',data.frame(row=obj$flow$Source,column=obj$flow$Sink,value=obj$flow$MaxFlow),'原生逐配体–靶基因子图最大流；这是容量图模型量，不是实测物质流或独立关联P',axis_label='Native ligand–target maximum flow',display_top_rows=20,display_top_columns=20,title=sample)
 nodes<-obj$graph$Graph.Node
 c$add(paste0('node_values_',i),'matrix',data.frame(row=paste(display_role(nodes$Role),nodes$Gene),column='Native node value',value=nodes$Size),'接收端基因在指定群的最大平均表达；原生TF层用signaling描述，不保证每个节点为TF。外部数据缺省时配体值固定1，此常数是模型假设，不称表达测量',axis_label='Native node value',display_top_rows=30,figure_role='intracellular_response',display_style='lollipop',title=sample)
 c$add(paste0('network_activity_',i),'matrix',data.frame(row=sample,column='Native AcI',value=obj$activity),'原生节点×边数和三层边权和的四个饱和项乘积，范围0–1不代表概率或统计置信度',axis_label='Native network AcI',title=sample)
}
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
