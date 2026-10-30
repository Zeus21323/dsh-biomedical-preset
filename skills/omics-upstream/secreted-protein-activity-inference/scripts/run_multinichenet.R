#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
args<-commandArgs(TRUE)
if(length(args)!=2) stop("用法：Rscript run_multinichenet.R 配置.json 新输出目录")
for(p in c("multinichenetr","SingleCellExperiment","jsonlite","digest","Matrix","dplyr")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少依赖：",p)
if(as.character(packageVersion("multinichenetr"))!="2.1.0") stop("需要 multinichenetr 2.1.0")
suppressPackageStartupMessages(library(multinichenetr));suppressPackageStartupMessages(library(dplyr))
cp<-normalizePath(args[1]);cfg<-jsonlite::read_json(cp,simplifyVector=TRUE)
for(k in c("dataset","research_question","input","sample_key","donor_key","condition_key","cell_type_key","contrasts","lr_network","ligand_target_matrix","network_version")) if(is.null(cfg[[k]])) stop("缺配置：",k)
resolve<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
input<-resolve(cfg$input);lrpath<-resolve(cfg$lr_network);ltpath<-resolve(cfg$ligand_target_matrix)
sce<-readRDS(input)
if(!inherits(sce,"SingleCellExperiment")) stop("输入必须为原生SingleCellExperiment")
assay<-cfg$count_assay %||% "counts"
if(!assay %in% SummarizedExperiment::assayNames(sce)) stop("缺少真实count assay，不从标准化表达反推计数")
counts<-SummarizedExperiment::assay(sce,assay);v<-if(inherits(counts,"sparseMatrix")) counts@x else as.vector(counts)
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("计数必须为有限非负整数")
if(anyDuplicated(rownames(sce))||anyDuplicated(colnames(sce))) stop("基因/细胞ID必须唯一")
meta<-as.data.frame(SummarizedExperiment::colData(sce));keys<-unique(c(cfg$sample_key,cfg$donor_key,cfg$condition_key,cfg$cell_type_key,cfg$covariates,cfg$batches))
if(!all(keys %in% names(meta))||anyNA(meta[,keys,drop=FALSE])) stop("样本设计字段缺失")
design<-unique(meta[,c(cfg$sample_key,cfg$donor_key,cfg$condition_key),drop=FALSE])
if(anyDuplicated(design[[cfg$sample_key]])) stop("一个样本不能对应多个供体或条件")
if(anyDuplicated(design[,c(cfg$donor_key,cfg$condition_key),drop=FALSE])) stop("同一供体条件有多个样本，先按设计合并技术重复")
groups<-unique(as.character(meta[[cfg$condition_key]]))
if(any(make.names(groups)!=groups)||any(make.names(keys)!=keys)) stop("原生模型需有效R名称；在输入准备中建立显式名称映射，不能静默改组名")
if(any(table(design[[cfg$condition_key]])<3)) stop("每条件至少3个独立供体；较少重复不能以细胞数替代")
repeated<-anyDuplicated(design[[cfg$donor_key]])>0
covariates<-cfg$covariates %||% NA_character_
if(repeated && !cfg$donor_key %in% covariates) stop("重复供体须在原生设计covariates中建模，不能当独立样本")
design_keys<-unique(c(cfg$sample_key,cfg$donor_key,cfg$condition_key,cfg$covariates,cfg$batches))
model_design<-unique(meta[,design_keys,drop=FALSE])
if(anyDuplicated(model_design[[cfg$sample_key]])) stop("样本内的协变量/批次不恒定；先核验实际实验设计")
model_fields<-unique(c(cfg$condition_key,cfg$covariates,cfg$batches))
model_matrix<-model.matrix(reformulate(model_fields,intercept=FALSE),model_design)
if(qr(model_matrix)$rank<ncol(model_matrix)||nrow(model_matrix)<=ncol(model_matrix)) stop("样本模型设计不满秩或无残差自由度；不能执行不可辨识的条件比较")
contrast_rows<-jsonlite::read_json(cp,simplifyVector=FALSE)$contrasts
if(!length(contrast_rows)||!all(vapply(contrast_rows,function(r) all(c('group','reference') %in% names(r)),logical(1)))) stop("contrasts需为包含group与reference的记录列表")
terms<-character()
for(i in seq_along(contrast_rows)) {
  g<-contrast_rows[[i]]$group;refs<-unlist(contrast_rows[[i]]$reference)
  if(!length(refs)||g %in% refs||!all(c(g,refs) %in% groups)||anyDuplicated(refs)) stop("无效条件对比")
  terms[i]<-paste0(g,'-(',paste(refs,collapse='+'),')/',length(refs))
}
ct<-tibble::tibble(contrast=terms,group=vapply(contrast_rows,function(r) r$group,character(1)))
lr<-readRDS(lrpath);lt<-readRDS(ltpath)
if(!all(c('ligand','receptor') %in% names(lr))) stop("MultiNicheNet需要ligand/receptor资源表")
if(file.exists(args[2])) stop("拒绝覆盖既有输出")
parent<-normalizePath(dirname(args[2]),mustWork=FALSE)
while(parent!='/') {if(file.exists(file.path(parent,'.git'))) stop("输出必须在Git外");parent<-dirname(parent)}
dir.create(args[2],recursive=TRUE);out<-normalizePath(args[2])
write_json<-function(x,n) jsonlite::write_json(x,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na='null',null='null')
write_table<-function(x,n) write.table(x,file.path(out,n),sep='\t',quote=FALSE,row.names=FALSE,na='NA')
hash<-function(p) digest::digest(file=p,algo='sha256')
write_json(cfg,'run_config.json');write_table(model_design,'biological_design.tsv');write_table(ct,'contrasts.tsv')
set.seed(cfg$seed %||% 1)
if(!is.null(cfg$reuse_bundle)) {
  source_path<-resolve(cfg$reuse_bundle);source_bundle<-jsonlite::read_json(source_path,simplifyVector=TRUE)
  native_path<-file.path(dirname(source_path),'multinichenet_results.rds')
  p<-source_bundle$provenance
  if(source_bundle$method!='MultiNicheNet'||source_bundle$method_version!='2.1.0'||is.null(p$native_result_sha256)||hash(native_path)!=p$native_result_sha256) stop('原生对象摘要或方法版本不符，不能复用')
  if(hash(input)!=p$input_sha256||hash(lrpath)!=p$lr_network_sha256||hash(ltpath)!=p$ligand_target_sha256) stop('输入或先验与原生结果不一致')
  science_keys<-c('sample_key','donor_key','condition_key','cell_type_key','count_assay','covariates','batches','contrasts','senders','receivers','expression_fraction','min_sample_prop','scenario','min_cells','logfc_threshold','alpha','top_targets','top_lr','seed')
  for(k in science_keys) if(!isTRUE(all.equal(cfg[[k]],p$parameters[[k]],check.attributes=FALSE))) stop('复用参数不一致：',k)
  res<-readRDS(native_path)
} else res<-multinichenetr::multi_nichenet_analysis(sce=sce,celltype_id=cfg$cell_type_key,sample_id=cfg$sample_key,group_id=cfg$condition_key,
  batches=cfg$batches %||% NA_character_,covariates=covariates,lr_network=lr,ligand_target_matrix=lt,
  contrasts_oi=paste0("'",paste(terms,collapse="','"),"'"),contrast_tbl=ct,
  senders_oi=cfg$senders %||% NULL,receivers_oi=cfg$receivers %||% NULL,
  fraction_cutoff=as.numeric(cfg$expression_fraction %||% .05),min_sample_prop=as.numeric(cfg$min_sample_prop %||% .5),
  scenario=cfg$scenario %||% 'regular',assay_oi_pb=assay,fun_oi_pb='sum',de_method_oi='edgeR',
  min_cells=as.numeric(cfg$min_cells %||% 10),logFC_threshold=as.numeric(cfg$logfc_threshold %||% .5),
  p_val_threshold=as.numeric(cfg$alpha %||% .05),p_val_adj=TRUE,empirical_pval=TRUE,
  top_n_target=as.numeric(cfg$top_targets %||% 250),n.cores=1,top_n_LR=as.numeric(cfg$top_lr %||% 2500))
saveRDS(res,file.path(out,'multinichenet_results.rds'));capture.output(sessionInfo(),file=file.path(out,'sessionInfo.txt'))
bundle<-list(schema_version=2,dataset=cfg$dataset,method='MultiNicheNet',method_version='2.1.0',implementation='native',
  provenance=list(parameters=cfg,input_sha256=hash(input),lr_network_sha256=hash(lrpath),ligand_target_sha256=hash(ltpath),
    statistical_unit='sample pseudobulk; donor structure explicitly checked',network_version=cfg$network_version,
    native_result_sha256=hash(file.path(out,'multinichenet_results.rds'))),tables=list())
add<-function(id,type,table,definition,...) {
  name<-paste0(id,'.tsv');write_table(table,name)
  bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=name,sha256=hash(file.path(out,name)),value_definition=definition),list(...))
}
prior<-res$prioritization_tables$group_prioritization_tbl
write_table(prior,'native_group_prioritization.tsv')
if(!all(c('sender','receiver','ligand','receptor','group','prioritization_score') %in% names(prior))) stop("原生优先级表API与契约不符")
mat<-unique(data.frame(row=paste(prior$sender,prior$ligand,prior$receptor,prior$receiver,sep=' | '),column=prior$group,value=prior$prioritization_score))
add('group_prioritization','matrix',mat,'MultiNicheNet原生多准则优先级；不是P值或通讯概率，包含供体表达与接收端响应证据',axis_label='Prioritization score',value_kind='rank_score',display_top_rows=30,direction='higher')
for(i in seq_along(unique(prior$group))) {
  group<-unique(prior$group)[i];r<-prior[prior$group==group,];r<-r[order(-r$prioritization_score),];r<-head(r,30)
  add(paste0('condition_links_',i),'molecular_links',data.frame(source=paste(r$sender,r$ligand,sep=': '),target=paste(r$receiver,r$receptor,sep=': '),source_type='sender_ligand',target_type='receiver_receptor',value=r$prioritization_score),
      paste(group,'原生排名前30条件候选关联；边表示优先级，不表示运输流量；完整表保留'),value_kind='native_score',additive=FALSE)
}
activities<-res$prioritization_tables$ligand_activities_target_de_tbl
write_table(activities,'native_activity_target_de.tsv')
if(all(c('contrast','receiver','ligand','activity','target','ligand_target_weight') %in% names(activities))) {
  activity_matrix<-unique(data.frame(row=activities$ligand,column=paste(activities$contrast,activities$receiver,activities$direction_regulation,sep=' | '),value=activities$activity))
  add('ligand_activity','matrix',activity_matrix,'原生条件/接收群配体活性；同一ligand-target重复记录去重，不平均冲突活性值',
      axis_label='Native ligand activity',title='Ligand activity by contrast and receiver',display_top_rows=20,direction='higher')
  contexts<-unique(activities[,c('contrast','receiver','direction_regulation')])
  for(i in seq_len(nrow(contexts))) {
    r<-activities[activities$contrast==contexts$contrast[i] & activities$receiver==contexts$receiver[i] & activities$direction_regulation==contexts$direction_regulation[i],]
    ligands<-unique(r[order(-r$activity),]$ligand);ligands<-head(ligands,8)
    r<-r[r$ligand %in% ligands,]
    targets<-head(unique(r[order(-r$ligand_target_weight),]$target),20)
    r<-r[r$target %in% targets,]
    add(paste0('ligand_targets_',i),'matrix',unique(data.frame(row=r$target,column=r$ligand,value=r$ligand_target_weight)),
        '原生目标关联权重；每接收群/条件按活性前8配体、关联权重前20靶基因显示，完整表保留；不是TF路径或因果效应',
        axis_label='Ligand–target prior weight',title=paste(contexts$contrast[i],contexts$receiver[i],contexts$direction_regulation[i]))
  }
}
sample_prior<-res$prioritization_tables$sample_prioritization_tbl
write_table(sample_prior,'native_sample_prioritization.tsv')
if(all(c('sample','id','sender','receiver','ligand','receptor','ligand_receptor_pb_prod','keep_sender_receiver') %in% names(sample_prior))) {
  selected_ids<-head(unique(prior[order(-prior$prioritization_score),]$id),6)
  r<-sample_prior[sample_prior$id %in% selected_ids & sample_prior$keep_sender_receiver %in% TRUE,]
  ix<-match(r$sample,design[[cfg$sample_key]])
  if(anyNA(ix)) stop('原生样本结果缺少供体映射')
  add('donor_expression_support','effects',data.frame(sample=r$sample,donor=design[[cfg$donor_key]][ix],condition=design[[cfg$condition_key]][ix],
      feature=paste(r$sender,r$ligand,r$receptor,r$receiver,sep=' | '),value=r$ligand_receptor_pb_prod),
      '原生LR pseudobulk表达乘积，前6条件优先级候选；点为实际供体，仅为表达支持，不等同条件优先级、靶基因响应或独立验证',axis_label='Native LR pseudobulk expression product')
}
write_json(bundle,'bundle.json')
