#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1]);source(file.path(dirname(normalizePath(f)),'native_expression_context.R'))
c<-native_expression_context(commandArgs(TRUE),'Domino (dominoSignal)','dominoSignal','1.7.0',counts_input=TRUE)
for(k in c('tf_activity_provenance','z_score_provenance','database','database_provenance')) if(is.null(c$cfg[[k]])) stop('缺少：',k)
x<-readRDS(c$input);z<-x$z_scores;features<-x$features;regulons<-x$regulons
if(!is.matrix(z)||!identical(dimnames(z),dimnames(c$expr))||any(!is.finite(z))) stop('z_scores须与counts基因和细胞逐一同序且有限；先记录缩放方法和零方差基因排除')
if(!is.matrix(features)||is.null(rownames(features))||anyDuplicated(rownames(features))||!identical(colnames(features),colnames(c$expr))||any(!is.finite(features))||any(features<0)) stop('features须为真实TF×细胞非负活性，与counts逐一同序，不从TF表达直接冒充活性')
if(!is.list(regulons)||!all(rownames(features) %in% names(regulons))||anyDuplicated(names(regulons))) stop('需要与TF活性匹配的真实regulons，用于原生剔除TF→受体靶基因反向关联')
if(any(vapply(regulons,function(g)!is.character(g)||anyNA(g)||any(!nzchar(g)),logical(1)))) stop('regulons须为有效基因名称向量')
rp<-c$resolve(c$cfg$database);rl<-readRDS(rp);need<-c('gene_A','gene_B','type_A','type_B','name_A','name_B')
if(!is.data.frame(rl)||!all(need %in% names(rl))||!nrow(rl)||anyNA(rl[,need])||any(trimws(as.matrix(rl[,need]))=='')) stop('资源RDS须完整原生rl_map，含分子身份和明确复合物成员')
if(any(!((rl$type_A=='R'&rl$type_B=='L')|(rl$type_A=='L'&rl$type_B=='R')))) stop('只接受明确方向的受体–配体行；双受体/双配体身份需在资源准备阶段记录排除')
for(side in c('A','B')) for(name in unique(rl[[paste0('name_',side)]])){
 sets<-unique(rl[[paste0('gene_',side)]][rl[[paste0('name_',side)]]==name]);if(length(sets)!=1) stop('同一资源分子身份对应不同亚基：',name)
}
create_args<-list(use_clusters=TRUE,use_complexes=TRUE,remove_rec_dropout=isTRUE(c$cfg$remove_rec_dropout),rec_min_thresh=c$cfg$rec_min_thresh %||% .025,tf_selection_method='clusters',verbose=FALSE)
build_args<-list(min_tf_pval=c$cfg$min_tf_pval %||% .001,max_tf_per_clust=c$cfg$max_tf_per_clust %||% 25,max_rec_per_tf=c$cfg$max_rec_per_tf %||% 25,rec_tf_cor_threshold=c$cfg$rec_tf_cor_threshold %||% .25,min_rec_percentage=c$cfg$min_rec_percentage %||% .1)
for(k in c('max_tf_per_clust','max_rec_per_tf')){
 v<-build_args[[k]];if(identical(v,'all')) build_args[[k]]<-Inf else if(!is.numeric(v)||length(v)!=1||!is.finite(v)||v<1||v!=as.integer(v)) stop('最大个数需要正整数或all：',k)
}
for(k in c('min_tf_pval','min_rec_percentage')) if(!is.finite(build_args[[k]])||build_args[[k]]<=0||build_args[[k]]>1) stop('无效阈值：',k)
if(!is.finite(build_args$rec_tf_cor_threshold)||build_args$rec_tf_cor_threshold<0||build_args$rec_tf_cor_threshold>1) stop('受体–TF相关阈值需在[0,1]')
c$start_cache(c$hash(rp),list(create=create_args,build=build_args,min_cells=c$minimum))
c$bundle$provenance$upstream<-list(url='https://github.com/FertigLab/dominoSignal',commit='86b9188b10ac19d264e3329178eeb0521a6a3d2c',license='GPL-3',implementation_branch='dominoSignal continuation of Domino')
c$bundle$provenance$semantics<-'原生Domino续作dominoSignal：TF活性按细胞类型对其余细胞单侧Wilcoxon未校正P筛选；受体–TF Spearman系数经靶基因剪枝，复合物采用全亚基相关中位数。不是供体病例对照检验，不产生LR联合P/FDR。'
matrows<-function(m){d<-expand.grid(row=rownames(m),column=colnames(m));d$value<-as.vector(m);d$value[!is.finite(d$value)]<-NA_real_;d}
for(i in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[i];meta<-c$sample_meta(sample);cells<-rownames(meta)
 if(prod(dim(z[,cells,drop=FALSE]))*8>(c$cfg$max_dense_bytes %||% 2^31)) stop('稠密z分数矩阵超过内存契约')
 obj<-c$native(i,sample,function(){
  clusters<-factor(meta$cell_type);names(clusters)<-cells
  dom<-do.call(dominoSignal::create_domino,c(list(rl_map=rl,features=features[,cells,drop=FALSE],counts=as(c$expr[,cells,drop=FALSE],'dgCMatrix'),z_scores=z[,cells,drop=FALSE],clusters=clusters,tf_targets=regulons),create_args))
  do.call(dominoSignal::build_domino,c(list(dom=dom),build_args))
 })
 c$wt(matrows(obj@misc$rec_cor),paste0('native_gene_tf_cor_',i,'.tsv'));c$wt(matrows(obj@cor),paste0('native_receptor_tf_cor_',i,'.tsv'))
 c$add(paste0('tf_cluster_p_',i),'matrix',matrows(obj@clust_de),'原生TF活性簇内相对其余细胞的单侧Wilcoxon未校正P；细胞层级筛选，不作供体差异推断',value_kind='p_value',axis_label='Unadjusted TF-activity P',direction='lower',display_top_rows=20L,title=sample)
 active<-unique(unlist(obj@linkages$clust_tf));recs<-unique(unlist(obj@linkages$clust_rec))
 if(length(active)&&length(recs)) c$add(paste0('receptor_tf_',i),'matrix',matrows(obj@cor[intersect(recs,rownames(obj@cor)),intersect(active,colnames(obj@cor)),drop=FALSE]),'仅已被原生簇内门槛选中的受体和TF相关矩阵；完整原生候选另外保留。靶基因剪枝/资格不足可被原生设为0，不等于实测相关为0',axis_label='Native pruned Spearman rho',display_top_rows=20L,display_top_columns=20L,title=sample)
 signal<-obj@signaling;rownames(signal)<-sub('^R_','',rownames(signal));colnames(signal)<-sub('^L_','',colnames(signal))
 c$add(paste0('cell_signaling_',i),'matrix',matrows(signal),'行接收细胞，列发送细胞；原生合格入向配体的非负截断平均z分数总和。原生对只有0或1个配体行的接收群将总分设0，逐配体矩阵另存，不改写这一版本行为',value_kind='native_score',axis_label='Native signaling summary',title=sample)
 for(j in seq_along(obj@cl_signaling_matrices)){
  target<-names(obj@cl_signaling_matrices)[j];m<-obj@cl_signaling_matrices[[j]]
  if(nrow(m)) c$add(paste0('incoming_ligands_',i,'_',j),'matrix',matrows(m),'原生逐配体入向贡献；负平均z分数被原生截断为0，复合物取亚基均值；受体选择来自TF证据，但数值不是配体×受体概率',axis_label='Native nonnegative mean z-score',display_top_rows=20L,title=paste(sample,'→',target))
  links<-list();tfs<-obj@linkages$clust_tf_rec[[target]]
  for(tf in names(tfs)) for(rec in tfs[[tf]]) links[[length(links)+1]]<-data.frame(source=rec,target=tf,source_type='receptor',target_type='tf',value=obj@cor[rec,tf])
  if(length(links)) c$add(paste0('receptor_tf_links_',i,'_',j),'molecular_links',unique(do.call(rbind,links)),'原生受体–TF模型相关连接；上游调控剪枝后保留，不表示受体直接调控TF或因果路径',axis_label='Native receptor–TF rho',title=paste(sample,target))
 }
 c$wt(data.frame(sample=sample,donor=unique(meta$donor),condition=unique(meta$condition),cells=nrow(meta),cell_types=length(unique(meta$cell_type))),paste0('sample_scope_',i,'.tsv'))
}
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
