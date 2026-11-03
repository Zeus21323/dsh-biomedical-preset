#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg))
source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'scMLnet','Matrix','1.7.6',counts_input=TRUE,species=c('human','mouse'));cfg<-c$cfg
for(key in c('native_root','input_provenance','resource_provenance')) if(is.null(cfg[[key]])) stop('缺少：',key)
for(pkg in c('Seurat','SeuratObject','parallel')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
if(as.character(packageVersion('Seurat'))!='4.4.0'||as.character(packageVersion('SeuratObject'))!='4.1.4')
  stop('需要已核验Seurat 4.4.0 / SeuratObject 4.1.4；上游调用Seurat内部C接口')
suppressPackageStartupMessages({library(Seurat);library(parallel)})
root<-c$resolve(cfg$native_root);source_file<-file.path(root,'R/Run_scMLnet.R')
expected_source<-'26c3d0526f104b7d3df297463fbe9bb5ad8e8b7dc894f7fdf3f70f95ab7cdd71'
if(c$hash(source_file)!=expected_source) stop('需要已核验scMLnet源码 ef2c245e2ce4c08839dd471fc67b37b65a8de3d1')
source(source_file)

resources<-list(
  lr=if(is.null(cfg$lr_database))file.path(root,'database/LigRec.txt')else c$resolve(cfg$lr_database),
  receptor_tf=if(is.null(cfg$receptor_tf_database))file.path(root,'database/RecTF.txt')else c$resolve(cfg$receptor_tf_database),
  tf_target=if(is.null(cfg$tf_target_database))file.path(root,'database/TFTargetGene.txt')else c$resolve(cfg$tf_target_database))
expected_hash<-c(lr='b51d4b4643adb35630cd52f0d76a0e36e00c25e2458cbffac84a54088df58395',
  receptor_tf='4ebea31a111f0d2af0132a10e3577f542ca73e73775487d905691d5d461ea13a',
  tf_target='f5f891102b3190c6aca4c921c80661503fb06feac8ce04e2fefb4aec5eba2faf')
if(is.null(cfg$resource_version)) stop('缺少：resource_version')
if(is.null(cfg$lr_database)&&is.null(cfg$receptor_tf_database)&&is.null(cfg$tf_target_database))
  for(key in names(resources)) if(c$hash(resources[[key]])!=expected_hash[[key]]) stop('作者数据库摘要不符：',key)
lrdb<-read.delim(resources$lr,check.names=FALSE);rtdb<-read.delim(resources$receptor_tf,check.names=FALSE);ttdb<-read.delim(resources$tf_target,check.names=FALSE)
if(!all(c('Key','Ligand','Receptor')%in%names(lrdb))||!all(c('Receptor','TF','Key')%in%names(rtdb))||
   !all(c('TF','Key')%in%names(ttdb))||!any(c('Target','Targets')%in%names(ttdb))) stop('scMLnet三层数据库字段无效')
target_col<-if('Target'%in%names(ttdb))'Target' else 'Targets'
checks<-list(cbind(lrdb$Ligand,lrdb$Receptor,lrdb$Key),cbind(rtdb$Receptor,rtdb$TF,rtdb$Key),cbind(ttdb$TF,ttdb[[target_col]],ttdb$Key))
for(x in checks) if(anyNA(x)||any(trimws(x)=='')||anyDuplicated(x[,3])||any(grepl('_',x[,1],fixed=TRUE))||
                    any(grepl('_',x[,2],fixed=TRUE))||any(x[,3]!=paste(x[,1],x[,2],sep='_')))
  stop('数据库端点/Key必须完整唯一且兼容原生下划线分隔')

sender<-cfg$sender%||%stop('缺少：sender');receiver<-cfg$receiver%||%stop('缺少：receiver')
pval<-cfg$high_expression_p%||%.05;logfc<-cfg$high_expression_logfc%||%.15;cores<-as.integer(cfg$cores%||%1L)
if(!is.numeric(pval)||pval<=0||pval>=1||!is.numeric(logfc)||!is.finite(logfc)||is.na(cores)||cores<1||cores>16)
  stop('high_expression_p/logfc/cores无效')
if(pval!=.05||logfc!=.15) if(is.null(cfg$threshold_provenance)) stop('非作者默认阈值须提供threshold_provenance，不能按网络密度调参')
params<-list(commit='ef2c245e2ce4c08839dd471fc67b37b65a8de3d1',sender=sender,receiver=receiver,
  high_expression_p=pval,high_expression_logfc=logfc,cores=cores,resource_version=cfg$resource_version,
  versions=list(Matrix=as.character(packageVersion('Matrix')),Seurat=as.character(packageVersion('Seurat')),SeuratObject=as.character(packageVersion('SeuratObject'))))
c$start_cache(c(vapply(resources,c$hash,''),expected_source),params)
c$bundle$method_version<-'0.1.0'
c$bundle$implementation<-'native_RunMLnet_with_observation_only_instrumentation'
c$bundle$provenance$upstream<-list(url='https://github.com/SunXQlab/scMLnet',commit=params$commit,license='GPL-2')
c$bundle$provenance$resource_hashes<-as.list(vapply(resources,c$hash,''))
c$bundle$provenance$resource_version<-cfg$resource_version
c$bundle$provenance$semantics<-paste(
  '原生结果是层级网络成员，不含边强度。高表达筛选先在输入counts上执行expm1后求均值对数，再对Seurat列归一化值做未校正t检验；这不是标准count logFC。',
  'TF和受体筛选使用组合数给出的单个重叠概率，而不是Fisher右尾富集P；上游先把概率与名称拼成字符矩阵，再以字符比较硬编码0.05，因此科学计数法的极小概率可能被漏掉。适配器保留原生选择并输出独立数值诊断。细胞内边再以接收群细胞的Kendall相关、正相关和三位有效数字raw P<0.05筛选，没有多重校正。',
  '所有细胞检验均为池化细胞层描述，不是供体重复或条件差异。')

# RunMLnet hard-codes detectCores()-1. Shadowing only controls worker count;
# every native statistic and threshold remains unchanged.
detectCores<-function(...) cores+1L
original_high<-getHighExpGene;original_lr<-getLigRec;original_tf<-TFTargetFisher;original_rt<-RecTFFisher;original_cor<-getCorR
capture<-new.env(parent=emptyenv())
getHighExpGene<-function(GCMat,barCluTable,CluNum.1,CluNum.2,pval,logfc,cores){
  value<-original_high(GCMat,barCluTable,CluNum.1,CluNum.2,pval,logfc,cores);capture$high[[CluNum.1]]<-value;value}
getLigRec<-function(LigRecTable,LigCluGene,RecCluGene){value<-original_lr(LigRecTable,LigCluGene,RecCluGene);capture$lr_candidates<-value;value}
TFTargetFisher<-function(TFTableFile,Tup,TotalGene){value<-original_tf(TFTableFile,Tup,TotalGene);capture$tf_stage<-value;value}
RecTFFisher<-function(RecTFTableFile,TFP){value<-original_rt(RecTFTableFile,TFP);capture$rt_stage<-value;value}
getCorR<-function(GCMat,keys,cells){value<-original_cor(GCMat,keys,cells);capture$cor_calls[[length(capture$cor_calls)+1]]<-list(keys=keys,selected=value);value}

parse_pairs<-function(keys,left,right){
  if(!length(keys)) return(setNames(as.data.frame(matrix(nrow=0,ncol=3)),c(left,right,'key')))
  split<-strsplit(as.character(keys),'_',fixed=TRUE)
  if(any(lengths(split)!=2)) stop('原生边身份不能唯一拆成两个节点')
  data.frame(setNames(list(vapply(split,`[[`,'',1),vapply(split,`[[`,'',2),as.character(keys)),c(left,right,'key')),check.names=FALSE)
}
point_probability<-function(focus,reference,universe){
  a<-base::intersect(focus,reference);b<-base::setdiff(focus,a);cc<-base::setdiff(reference,a)
  d<-base::setdiff(universe,base::union(base::union(a,b),cc))
  (choose(length(base::union(a,b)),length(a))*choose(length(base::union(cc,d)),length(cc)))/choose(length(universe),length(base::union(a,cc)))
}
all_lr<-list();all_links<-list();all_stage<-list();all_final_cor<-list();all_cor<-list();native_details<-list()
samples<-unique(c$meta$sample)
if(length(samples)!=1L)
  stop('scMLnet原生RunMLnet一次只分析一个池化样本；多样本须分别运行，再用统一比较层汇总，不能把样本身份折叠进同一网络')
for(i in seq_along(samples)){
  sample<-samples[i];meta<-c$meta[c$meta$sample==sample,,drop=FALSE]
  if(!all(c(sender,receiver)%in%meta$cell_type)) stop('样本',sample,'缺发送或接收群：',sender,' / ',receiver)
  ids<-rownames(meta)[meta$cell_type%in%c(sender,receiver)];meta<-meta[ids,,drop=FALSE]
  if(sum(meta$cell_type==sender)<c$minimum||sum(meta$cell_type==receiver)<c$minimum) stop('样本',sample,'发送或接收群细胞数不足')
  # Column-wise normalization is unchanged by excluding unrelated cell types;
  # this avoids the upstream function normalizing the full atlas twice.
  counts<-c$expr[,ids,drop=FALSE]
  if(nrow(counts)*ncol(counts)>(cfg$max_dense_elements%||%5e8)) stop('原生基因检验规模超出显式上限，不静默抽样')
  work<-file.path(c$out,paste0('native_work_',i));dir.create(work)
  ann<-data.frame(Barcode=ids,Cluster=meta$cell_type);ann_file<-file.path(work,'barcodetype.tsv');write.table(ann,ann_file,sep='\t',quote=FALSE,row.names=FALSE)
  capture$high<-list();capture$lr_candidates<-character();capture$tf_stage<-NULL;capture$rt_stage<-NULL;capture$cor_calls<-list()
  obj<-c$native(i,sample,function(){
    result<-RunMLnet(counts,ann_file,RecClu=receiver,LigClu=sender,pval=pval,logfc=logfc,
      LigRecLib=resources$lr,TFTarLib=resources$tf_target,RecTFLib=resources$receptor_tf)
    list(result=result,capture=as.list(capture))
  })
  result<-obj$result;cap<-obj$capture
  if(!identical(names(result),c('LigRec','RecTF','TFTar'))) stop('原生结果层身份无效')
  lr_edges<-parse_pairs(result$LigRec,'ligand','receptor')
  rt_edges<-parse_pairs(result$RecTF,'receptor','tf')
  tt_edges<-parse_pairs(result$TFTar,'tf','target')
  if(anyDuplicated(lr_edges$key)||anyDuplicated(rt_edges$key)||anyDuplicated(tt_edges$key)) stop('原生结果含重复边')
  tf_names<-unique(ttdb$TF)
  tf_probability<-vapply(tf_names,function(tf) point_probability(cap$high[[receiver]],ttdb[[target_col]][ttdb$TF==tf],rownames(counts)),0.0)
  tf_probability_table<-data.frame(feature=tf_names,point_probability=tf_probability,native_character=as.character(tf_probability),
    numeric_below_0.05=is.finite(tf_probability)&tf_probability<.05,native_string_below_0.05=as.character(tf_probability)<.05)
  if(!setequal(tf_probability_table$feature[tf_probability_table$native_string_below_0.05],cap$tf_stage[[2]]$TF))
    stop('TF点概率复算与原生字符阈值选择不一致')
  tf_pool<-cap$tf_stage[[2]]$TF;receptors<-unique(rtdb$Receptor);tf_universe<-unique(rtdb$TF)
  rt_probability<-vapply(receptors,function(rec) point_probability(tf_pool,unique(rtdb$TF[rtdb$Receptor==rec]),tf_universe),0.0)
  rt_probability_table<-data.frame(feature=receptors,point_probability=rt_probability,native_character=as.character(rt_probability),
    numeric_below_0.05=is.finite(rt_probability)&rt_probability<.05,native_string_below_0.05=as.character(rt_probability)<.05)
  if(!setequal(rt_probability_table$feature[rt_probability_table$native_string_below_0.05],cap$rt_stage[[1]]$Receptor))
    stop('受体点概率复算与原生字符阈值选择不一致')
  sender_ids<-ids[meta$cell_type==sender];receiver_ids<-ids[meta$cell_type==receiver]
  if(nrow(lr_edges)){
    ligand_mean<-Matrix::rowMeans(counts[lr_edges$ligand,sender_ids,drop=FALSE]);receptor_mean<-Matrix::rowMeans(counts[lr_edges$receptor,receiver_ids,drop=FALSE])
    ligand_fraction<-Matrix::rowMeans(counts[lr_edges$ligand,sender_ids,drop=FALSE]>0);receptor_fraction<-Matrix::rowMeans(counts[lr_edges$receptor,receiver_ids,drop=FALSE]>0)
    all_lr[[length(all_lr)+1]]<-data.frame(sample=sample,source=sender,target=receiver,ligand=lr_edges$ligand,receptor=lr_edges$receptor,
      interaction=lr_edges$key,score=1,tested=TRUE,supported=TRUE,ligand_mean=ligand_mean,receptor_mean=receptor_mean,
      ligand_fraction=ligand_fraction,receptor_fraction=receptor_fraction,n_sender=length(sender_ids),n_receiver=length(receiver_ids))
  }
  links<-rbind(
    if(nrow(lr_edges))data.frame(source=lr_edges$ligand,target=lr_edges$receptor,source_type='ligand',target_type='receptor',value=1,sample=sample) else NULL,
    if(nrow(rt_edges))data.frame(source=rt_edges$receptor,target=rt_edges$tf,source_type='receptor',target_type='TF',value=1,sample=sample) else NULL,
    if(nrow(tt_edges))data.frame(source=tt_edges$tf,target=tt_edges$target,source_type='TF',target_type='target',value=1,sample=sample) else NULL)
  if(nrow(links)) all_links[[length(all_links)+1]]<-links
  # Recalculate every correlation candidate captured at the native call boundary.
  # The exact rounded native rule is audited; BH is diagnostic and never replaces
  # the returned network membership.
  cor_tables<-list()
  for(j in seq_along(cap$cor_calls)){
    call<-cap$cor_calls[[j]];layer<-if(j==1)'receptor_TF' else 'TF_target'
    candidates<-unique(call$keys);parts<-strsplit(candidates,'_',fixed=TRUE);valid<-lengths(parts)==2
    candidates<-candidates[valid];parts<-parts[valid]
    left<-vapply(parts,`[[`,'',1);right<-vapply(parts,`[[`,'',2)
    measured<-left%in%rownames(counts)&right%in%rownames(counts)
    positive<-rep(FALSE,length(candidates));positive[measured]<-Matrix::rowMeans(counts[left[measured],receiver_ids,drop=FALSE])>0&Matrix::rowMeans(counts[right[measured],receiver_ids,drop=FALSE])>0
    tau<-p_raw<-rep(NA_real_,length(candidates))
    for(k in which(measured&positive)){
      test<-suppressWarnings(cor.test(as.numeric(counts[left[k],receiver_ids]),as.numeric(counts[right[k],receiver_ids]),method='kendall'))
      tau[k]<-unname(test$estimate);p_raw[k]<-test$p.value
    }
    tau_native<-signif(tau,2);p_native<-signif(p_raw,3);selected<-is.finite(tau_native)&is.finite(p_native)&tau_native>0&p_native<.05
    if(!setequal(candidates[selected],call$selected)) stop('独立相关复算与原生',layer,'选择不一致')
    q<-rep(NA_real_,length(candidates));q[is.finite(p_raw)]<-p.adjust(p_raw[is.finite(p_raw)],'BH')
    cor_tables[[j]]<-data.frame(sample=sample,layer=layer,key=candidates,left=left,right=right,measured=measured,positive_expression=positive,
      kendall_tau=tau,p_value=p_raw,q_value=q,native_tau_rounded=tau_native,native_p_rounded=p_native,native_selected=selected)
  }
  cor_full<-do.call(rbind,cor_tables)
  final_keys<-list(receptor_TF=rt_edges$key,TF_target=tt_edges$key)
  cor_full$final_network_member<-mapply(function(layer,key) key%in%final_keys[[layer]],cor_full$layer,cor_full$key)
  if(any(cor_full$final_network_member&!cor_full$native_selected)) stop('最终层级网络包含未通过原生相关筛选的边')
  native_details[[sample]]<-list(capture=cap,correlations=cor_full)
  all_cor[[length(all_cor)+1]]<-cor_full
  selected_cor<-cor_full[cor_full$final_network_member,]
  if(nrow(selected_cor)) all_final_cor[[length(all_final_cor)+1]]<-data.frame(row=selected_cor$key,column=paste(sample,selected_cor$layer,sep=' | '),value=selected_cor$native_tau_rounded)
  stage<-c(sender_high=length(cap$high[[sender]]),receiver_high=length(cap$high[[receiver]]),candidate_lr=length(cap$lr_candidates),
    native_tf_point_probability=nrow(cap$tf_stage[[2]]),native_receptor_point_probability=nrow(cap$rt_stage[[1]]),
    tf_numeric_below_0.05=sum(tf_probability_table$numeric_below_0.05),
    tf_numeric_hits_excluded_by_native_string=sum(tf_probability_table$numeric_below_0.05&!tf_probability_table$native_string_below_0.05),
    receptor_numeric_below_0.05=sum(rt_probability_table$numeric_below_0.05),
    receptor_numeric_hits_excluded_by_native_string=sum(rt_probability_table$numeric_below_0.05&!rt_probability_table$native_string_below_0.05),
    final_lr=nrow(lr_edges),final_receptor_tf=nrow(rt_edges),final_tf_target=nrow(tt_edges))
  all_stage[[length(all_stage)+1]]<-data.frame(row=names(stage),column=sample,value=as.numeric(stage))
  c$wt(cor_full,paste0('correlation_candidates_',i,'.tsv'))
  c$wt(data.frame(cluster=rep(names(cap$high),lengths(cap$high)),gene=unlist(cap$high,use.names=FALSE)),paste0('high_expression_genes_',i,'.tsv'))
  c$wt(cap$tf_stage[[2]],paste0('native_tf_point_probability_selected_',i,'.tsv'))
  c$wt(cap$rt_stage[[1]],paste0('native_receptor_point_probability_selected_',i,'.tsv'))
  c$wt(tf_probability_table,paste0('point_probability_audit_tf_',i,'.tsv'))
  c$wt(rt_probability_table,paste0('point_probability_audit_receptor_',i,'.tsv'))
}
lr_rows<-if(length(all_lr))do.call(rbind,all_lr)else data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),tested=logical(),supported=logical())
link_rows<-if(length(all_links))do.call(rbind,all_links)else data.frame(source=character(),target=character(),source_type=character(),target_type=character(),value=numeric())
stage_rows<-if(length(all_stage))do.call(rbind,all_stage)else data.frame(row=character(),column=character(),value=numeric())
correlation_rows<-if(length(all_final_cor))do.call(rbind,all_final_cor)else data.frame(row=character(),column=character(),value=numeric())
receptor_tf_rows<-correlation_rows[grepl('receptor_TF$',correlation_rows$column),,drop=FALSE]
tf_target_rows<-correlation_rows[grepl('TF_target$',correlation_rows$column),,drop=FALSE]
receptor_tf_rows$column<-sub(' \\| receptor_TF$','',receptor_tf_rows$column)
tf_target_rows$column<-sub(' \\| TF_target$','',tf_target_rows$column)
c$add('final_ligand_receptor','lr_edges',lr_rows,'scMLnet原生最终多层网络中的LR成员；score=1仅表示入选，不是强度、概率或FDR。双端点均值/检测比例来自同一原始counts，supported表示原生网络成员。',direction='higher',additive=FALSE,value_kind='membership',axis_label='Native network membership',statistical_unit='pooled cells within each input sample')
c$add('multilayer_membership','molecular_links',link_rows,'scMLnet原生最终Ligand→Receptor→TF→Target层级边；value=1为成员标记，不可按宽度解释为表达强度或因果效应。',direction='higher',additive=FALSE,value_kind='membership',axis_label='Native network membership')
c$add('native_stage_counts','matrix',stage_rows,'作者原生筛选各阶段的成员数，并列显示按数值P<0.05本应入选、但被原生字符比较漏掉的诊断计数。计数描述算法流程，不是效应量。',direction='higher',additive=FALSE,value_kind='count',axis_label='Features or edges at native stage',display_top_rows=20)
c$add('receptor_tf_kendall','matrix',receptor_tf_rows,'仅显示最终层级网络中Receptor→TF边的原生两位有效数字Kendall tau；完整候选、未舍入P、BH诊断、原生相关入选和最终成员身份另存correlation_candidates_1.tsv。',direction='higher',additive=FALSE,value_kind='correlation',axis_label='Receptor–TF Kendall tau (native rounded)',display_top_rows=40)
c$add('tf_target_kendall','matrix',tf_target_rows,'仅显示最终层级网络中TF→Target边的原生两位有效数字Kendall tau；完整候选、未舍入P、BH诊断、原生相关入选和最终成员身份另存correlation_candidates_1.tsv。',direction='higher',additive=FALSE,value_kind='correlation',axis_label='TF–target Kendall tau (native rounded)',display_top_rows=40)
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$limitations<-c('高表达t检验、组合数点概率和Kendall相关均把池化细胞当观测；没有供体层级模型。','作者TF数据库列名为Targets，而源码以$Target部分匹配；适配器验证并记录该固定资源行为。','点概率原生阈值实际是字符比较；数值上更小但以科学计数法表示的概率可能被排除，完整差异写入point_probability_audit文件。','最终网络只返回边身份；统一图的线宽仅为成员标记，不能解释为分子通量。')
c$wj(c$bundle,'bundle.json')
c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',samples=length(samples),sender=sender,receiver=receiver),'run_metadata.json')
