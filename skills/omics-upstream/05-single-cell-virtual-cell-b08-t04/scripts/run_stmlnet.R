#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg));source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'stMLnet','Matrix','1.6.5',counts_input=FALSE,species=c('human','mouse'));cfg<-c$cfg
for(key in c('native_root','candidate_table','input_provenance','resource_provenance','resource_version','candidate_provenance','candidate_selection_definition','coordinate_provenance','coordinate_unit')) if(is.null(cfg[[key]])) stop('缺少：',key)
for(pkg in c('dplyr','stringr','tibble','ranger','caret','digest')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
suppressPackageStartupMessages({library(dplyr);library(stringr);library(tibble);library(ranger);library(caret)})

root<-c$resolve(cfg$native_root);candidate_path<-c$resolve(cfg$candidate_table)
expected<-c(
  'DESCRIPTION.txt'='36d3ba6b4ed66b2b126a2abff4289991dad7c77c694010b79f1f8708da0c7e47',
  'NAMESPACE.txt'='898026846522c869d31d5b9461b3289333df2f1f17fab65462b91443c2fa79a0',
  'stMLnet_0.1.2.tar.gz'='b10452dfee0257b6455a00434e28573b4fca23c96d5e511ab4efc5d34f78264b',
  'data/ex_databases.rda'='c4d9a6cf28eaa7361ed1d4682f705561f2cab388efb5b56600af8d06cc2c93d5',
  'R/create_multilayer_network.R'='02baf6a46ff99980ac3db2e96ede5d78bd88d803449f0098b5a5a7eaffd6d1e3',
  'R/calculate_signal_activity.R'='c3b7afe4c2353556826f8c2857fd12db8ff3073c9303e43da3735b812a5872ca',
  'R/calculate_signal_importance.R'='54322d29cf157b854bdc994ed5b3cafeec78e669c6bc79b7ec72dc308e4b8aaa',
  'R/check_feedback_loop.R'='08581e459b5b0092725f0eea68252b97ec127e63d6014e07d6e3f54d676da959',
  'R/run_cell_communication.R'='e83a739477cf232055b9953216429b9755d982e8b3ced07ba3d9b3904bf02f5b')
for(path in names(expected)) if(c$hash(file.path(root,path))!=expected[[path]]) stop('stMLnet源码或资源摘要不符：',path)
desc<-read.dcf(file.path(root,'DESCRIPTION.txt'))
if(desc[1,'Version']!='0.1.2'||desc[1,'License']!='GPL-2') stop('stMLnet版本或许可字段不符')
for(path in c('R/create_multilayer_network.R','R/calculate_signal_activity.R','R/calculate_signal_importance.R','R/check_feedback_loop.R')) source(file.path(root,path),local=.GlobalEnv)

x<-readRDS(c$input);coordinates<-x$coordinates
if(is.null(coordinates)||is.null(rownames(coordinates))||ncol(coordinates)<2||anyDuplicated(rownames(coordinates))||!setequal(rownames(coordinates),colnames(c$expr))) stop('stMLnet需要与expression细胞严格对齐的二维coordinates')
coordinates<-as.matrix(coordinates[colnames(c$expr),1:2,drop=FALSE]);storage.mode(coordinates)<-'double'
if(any(!is.finite(coordinates))) stop('空间坐标必须有限')
if(!cfg$coordinate_unit%in%c('um','pixel','native')) stop('coordinate_unit必须为um/pixel/native')
if(cfg$coordinate_unit=='native'&&!isTRUE(cfg$physical_scale_unavailable)) stop('native坐标必须明确physical_scale_unavailable=true')
if(any(grepl('_',rownames(c$expr),fixed=TRUE))) stop('固定源码用下划线拼接并拆分LR；基因身份含下划线时无法无损执行')

candidates<-read.delim(candidate_path,check.names=FALSE)
if(!all(c('cell_type','role','gene')%in%names(candidates))) stop('candidate_table必须包含cell_type、role、gene')
candidates<-unique(candidates[,c('cell_type','role','gene')]);candidates[]<-lapply(candidates,as.character)
if(anyNA(candidates)||any(trimws(as.matrix(candidates))=='')||!all(candidates$role%in%c('ligand','receptor','target'))) stop('候选表含空身份或未知role')
if(any(!candidates$gene%in%rownames(c$expr))) stop('候选表含输入表达矩阵不存在的基因；不自动改写身份')
if(any(!candidates$cell_type%in%c$meta$cell_type)) stop('候选表含元数据不存在的细胞类型')

db_env<-new.env(parent=emptyenv());load(file.path(root,'data/ex_databases.rda'),envir=db_env)
if(!exists('ex_databases',envir=db_env,inherits=FALSE)) stop('作者资源没有ex_databases对象')
databases<-db_env$ex_databases;cutoff<-as.numeric(quantile(databases$RecTF.DB$score,.98))
databases$RecTF.DB<-databases$RecTF.DB[databases$RecTF.DB$score>cutoff,] %>% dplyr::distinct(source,target)
databases$LigRec.DB<-databases$LigRec.DB %>% dplyr::distinct(source,target) %>% dplyr::filter(target%in%databases$RecTF.DB$source)
databases$TFTG.DB<-databases$TFTG.DB %>% dplyr::distinct(source,target) %>% dplyr::filter(source%in%databases$RecTF.DB$target)
if(!identical(vapply(databases,nrow,integer(1)),c(LigRec.DB=3659L,RecTF.DB=17450L,TFTG.DB=373501L))) stop('作者默认98% RecTF资源筛选范围改变')

rec_tf_method<-cfg$rec_tf_method%||%'Search';tf_tg_method<-cfg$tf_tg_method%||%'Fisher'
if(!rec_tf_method%in%c('Search','Fisher')||!tf_tg_method%in%c('Search','Fisher')) stop('RecTF/TFTG筛选只能为Search或Fisher')
auto_para<-isTRUE(cfg$auto_parameter_tuning%||%TRUE);n_trees<-as.integer(cfg$n_trees%||%500L);n_trys<-as.integer(cfg$n_trys%||%10L)
split_rule<-cfg$tree_method%||%'variance';node_size<-as.integer(cfg$node_size%||%5L);n_pert<-as.integer(cfg$n_perturbations%||%10L);seed<-as.integer(cfg$seed%||%20260910L)
max_models<-as.integer(cfg$max_models%||%500L);max_activity_rows<-as.numeric(cfg$max_activity_rows%||%5e6);max_spatial_lr<-as.integer(cfg$display_spatial_lr%||%6L)
scale_factors<-as.numeric(cfg$distance_scale_factors%||%c(.5,1,2))
if(is.na(n_trees)||n_trees<100||is.na(n_trys)||n_trys<1||is.na(node_size)||node_size<1||is.na(n_pert)||n_pert<1||is.na(seed)||is.na(max_models)||max_models<1||!is.finite(max_activity_rows)||max_activity_rows<1e5||is.na(max_spatial_lr)||max_spatial_lr<1||any(!is.finite(scale_factors))||any(scale_factors<=0)||!1%in%scale_factors) stop('stMLnet参数无效')
params<-list(commit='bfffc8fce73459946df119923470cc9bcd167ea0',version='0.1.2',rec_tf_method=rec_tf_method,tf_tg_method=tf_tg_method,auto_parameter_tuning=auto_para,n_trees=n_trees,n_trys=n_trys,tree_method=split_rule,node_size=node_size,n_perturbations=n_pert,seed=seed,resource_quantile=.98,distance_scale_factors=scale_factors,resource_version=cfg$resource_version)
c$start_cache(c(unname(expected),c$hash(candidate_path)),params)
c$bundle$method_version<-'stMLnet 0.1.2'
c$bundle$implementation<-'native_runMLnet_getSiganlActivity_runRFModel_with_audited_component_orchestration'
c$bundle$provenance$upstream<-list(url='https://github.com/SunXQlab/stMLnet',commit=params$commit,version='0.1.2',license='GPL-2')
c$bundle$provenance$paper<-list(doi='10.1101/gr.279857.124',pmcid='PMC12129024',published='Genome Research 2025')
c$bundle$provenance$resource_hash<-c$hash(file.path(root,'data/ex_databases.rda'));c$bundle$provenance$candidate_hash<-c$hash(candidate_path)
c$bundle$provenance$coordinate_provenance<-cfg$coordinate_provenance
c$bundle$provenance$semantics<-paste('stMLnet对每个接收细胞计算 receptor expression × sum(sender ligand expression / max(distance,1))。',
  '每个靶基因分别以其相关LR活性训练ranger随机森林；LR-TG IM为原生permutation importance，pIM为将含某个配体或受体的全部LR列共同打乱后OOB MSE增量。',
  '网络资源为作者ex_databases在RecTF score严格高于98%分位后得到的3659 LR、17450 RecTF和373501 TFTG边。')

all_lr<-list();all_counts<-list();all_strength<-list();all_paths<-list();all_path_rows<-list();all_importance<-list();all_partial<-list();all_quality<-list();all_sensitivity<-list();all_feedback<-list();all_positions<-list();all_activity_cells<-list();all_excluded<-list();all_distance<-list();sample_diag<-list();spatial_tables<-list()
samples<-unique(c$meta$sample)
for(si in seq_along(samples)){
  sample<-samples[[si]];meta<-c$sample_meta(sample);ids<-rownames(meta);expr<-as.matrix(c$expr[,ids,drop=FALSE]);coords<-coordinates[ids,,drop=FALSE]
  types<-sort(unique(as.character(meta$cell_type)));codes<-sprintf('ct%03d',seq_along(types));names(codes)<-types;decode<-setNames(types,codes)
  anno<-data.frame(Barcode=ids,Cluster=unname(codes[meta$cell_type]))
  candidates_sample<-candidates[candidates$cell_type%in%types,,drop=FALSE]
  lists<-function(role){z<-split(candidates_sample$gene[candidates_sample$role==role],candidates_sample$cell_type[candidates_sample$role==role]);setNames(lapply(types,function(t)unique(z[[t]]%||%character())),unname(codes[types]))}
  ligands<-lists('ligand');receptors<-lists('receptor');targets<-lists('target')
  if(any(lengths(ligands)==0)||any(lengths(receptors)==0)||any(lengths(targets)==0)) stop('样本',sample,'至少一个合格细胞类型缺少显式ligand/receptor/target候选')
  dist_mat<-as.matrix(dist(coords));rownames(dist_mat)<-colnames(dist_mat)<-ids
  native<-c$native(si,sample,function(){
    ml<-runMLnet(expr,anno,LigClus=unname(codes[types]),RecClus=unname(codes[types]),Normalize=FALSE,OutputDir=c$out,Databases=databases,RecTF.method=rec_tf_method,TFTG.method=tf_tg_method,TGList=targets,LigList=ligands,RecList=receptors)
    nets<-list();for(group in ml$mlnets)for(nm in names(group))nets[[nm]]<-group[[nm]]
    nets<-nets[vapply(nets,function(z)nrow(z$LigRec)>0&&nrow(z$RecTF)>0&&nrow(z$TFTar)>0,logical(1))]
    activities<-list();models<-list();excluded<-list()
    for(cp in names(nets)){
      parts<-strsplit(cp,'-',fixed=TRUE)[[1]];act<-getSiganlActivity(expr,dist_mat,anno,list(setNames(list(nets[[cp]]),cp))[[1]],Receiver=parts[2],Sender=parts[1],OutputDir=c$out)
      # getSiganlActivity returns a named list even for a single supplied network.
      if(length(act)&&length(act[[1]]$LRs_score)) activities[[cp]]<-act[[1]]
    }
    model_count<-0L
    for(cp in names(activities)) for(tg in names(activities[[cp]]$LRs_score)){
      xx<-as.matrix(activities[[cp]]$LRs_score[[tg]]);yy<-as.numeric(activities[[cp]]$TGs_expr[[tg]])
      reason<-NULL
      if(ncol(xx)<2) reason<-'fewer_than_two_lr_predictors'
      else if(nrow(xx)<10) reason<-'fewer_than_ten_receiver_cells'
      else if(any(!is.finite(xx))||any(!is.finite(yy))) reason<-'nonfinite_input'
      else if(sd(yy)==0) reason<-'constant_target'
      else if(any(apply(xx,2,sd)==0)) reason<-'constant_lr_predictor'
      else if(model_count>=max_models) stop('样本',sample,'可建模target超过max_models；不静默截断')
      key<-paste(cp,tg,sep='|')
      if(!is.null(reason)){excluded[[key]]<-reason;next}
      set.seed(seed+si+model_count);models[[key]]<-runRFModel(xx,yy,auto_para=auto_para,n.trees=n_trees,n.trys=min(n_trys,ncol(xx)),tree.method=split_rule,node.size=node_size,nPert=n_pert);model_count<-model_count+1L
    }
    list(multilayer=ml,networks=nets,activities=activities,models=models,excluded_models=excluded,type_map=data.frame(code=unname(codes),cell_type=types),distance=dist_mat,candidates=list(ligands=ligands,receptors=receptors,targets=targets))
  })
  if(!length(native$networks)||!length(native$activities)) stop('样本',sample,'没有形成可计算活性的L-R-TF-TG网络；保留日志并检查候选表')
  pos<-data.frame(sample=sample,cell=ids,x=coords[,1],y=coords[,2],value=0,label=as.character(meta$cell_type));all_positions[[sample]]<-pos
  activity_seen<-list();activity_cell_rows<-list();sensitivity_rows<-list();path_rows<-list()
  for(cp in names(native$networks)){
    parts<-strsplit(cp,'-',fixed=TRUE)[[1]];sender<-decode[[parts[1]]];receiver<-decode[[parts[2]]];net<-native$networks[[cp]]
    paths<-merge(data.frame(ligand=net$LigRec$source,receptor=net$LigRec$target),data.frame(receptor=net$RecTF$source,tf=net$RecTF$target),by='receptor') %>% merge(data.frame(tf=net$TFTar$source,target_gene=net$TFTar$target),by='tf')
    if(nrow(paths)){paths$sample<-sample;paths$source_group<-sender;paths$target_group<-receiver;path_rows[[cp]]<-paths}
    if(!cp%in%names(native$activities)) next
    act<-native$activities[[cp]];receiver_ids<-ids[meta$cell_type==receiver];sender_ids<-ids[meta$cell_type==sender]
    for(tg in names(act$LRs_score)){
      mat<-as.matrix(act$LRs_score[[tg]])
      for(j in seq_len(ncol(mat))){
        lr<-colnames(mat)[j];key<-paste(cp,lr,sep='|');values<-mat[,j]
        if(!is.null(activity_seen[[key]])){
          if(!isTRUE(all.equal(activity_seen[[key]],values,tolerance=1e-12,check.attributes=FALSE))) stop('同一细胞群对/LR因target不同产生不一致活性')
        }else{
          activity_seen[[key]]<-values;split<-strsplit(lr,'_',fixed=TRUE)[[1]]
          if(length(split)!=2) stop('原生LR身份无法无损拆分')
          activity_cell_rows[[key]]<-data.frame(sample=sample,source=sender,target=receiver,ligand=split[1],receptor=split[2],cell=names(values),activity=as.numeric(values))
          for(factor in scale_factors){
            d<-dist_mat[sender_ids,receiver_ids,drop=FALSE]*factor;d[d<1]<-1
            score<-expr[split[2],receiver_ids]*as.numeric(expr[split[1],sender_ids,drop=FALSE]%*%(1/d))
            sensitivity_rows[[paste(key,factor)]]<-data.frame(row=paste(sample,paste(sender,receiver,sep='→'),paste(split,collapse='→'),sep=' | '),column=paste0('coordinate × ',format(factor,trim=TRUE)),value=mean(score))
          }
        }
      }
    }
  }
  activity_cells<-do.call(rbind,activity_cell_rows);if(nrow(activity_cells)>max_activity_rows) stop('样本',sample,'完整receiver-cell LR活性超过max_activity_rows；不静默抽样')
  all_activity_cells[[sample]]<-activity_cells;all_sensitivity[[sample]]<-do.call(rbind,sensitivity_rows);all_path_rows[[sample]]<-do.call(rbind,path_rows);all_paths[[sample]]<-all_path_rows[[sample]]
  group_lr<-aggregate(activity~sample+source+target+ligand+receptor,activity_cells,function(v)c(mean=mean(v),median=median(v),maximum=max(v),nonzero=sum(v>0)))
  unpack<-group_lr$activity;if(!is.matrix(unpack))unpack<-do.call(rbind,unpack);group_lr$score<-unpack[,'mean'];group_lr$median_activity<-unpack[,'median'];group_lr$max_activity<-unpack[,'maximum'];group_lr$nonzero_receiver_cells<-unpack[,'nonzero'];group_lr$interaction<-paste(group_lr$ligand,group_lr$receptor,sep='→');group_lr$tested<-TRUE;group_lr$supported<-group_lr$score>0
  sender_n<-table(meta$cell_type);group_lr$sender_cells<-unname(sender_n[group_lr$source]);group_lr$score_per_sender_cell<-group_lr$score/group_lr$sender_cells
  all_lr[[sample]]<-group_lr[,c('sample','source','target','ligand','receptor','interaction','score','tested','supported','median_activity','max_activity','nonzero_receiver_cells','sender_cells','score_per_sender_cell')]
  counts<-aggregate(interaction~source+target,group_lr[group_lr$supported,],function(v)length(unique(v)));names(counts)[3]<-'value';counts$sample<-sample;all_counts[[sample]]<-counts[,c('sample','source','target','value')]
  strength<-aggregate(score~source+target,group_lr[group_lr$supported,],sum);names(strength)[3]<-'value';strength$sample<-sample;all_strength[[sample]]<-strength[,c('sample','source','target','value')]
  paths<-all_paths[[sample]]
  molecular<-rbind(data.frame(source=paths$ligand,target=paths$receptor,source_type='ligand',target_type='receptor'),data.frame(source=paths$receptor,target=paths$tf,source_type='receptor',target_type='TF'),data.frame(source=paths$tf,target=paths$target_gene,source_type='TF',target_type='target'))
  molecular<-aggregate(rep(1,nrow(molecular)),molecular,sum);names(molecular)[5]<-'value';all_paths[[sample]]<-molecular
  importance_rows<-list();partial_rows<-list();quality_rows<-list()
  for(key in names(native$models)){
    pieces<-strsplit(key,'|',fixed=TRUE)[[1]];cp<-pieces[1];tg<-pieces[2];groups<-strsplit(cp,'-',fixed=TRUE)[[1]];label<-paste(sample,paste(decode[groups],collapse='→'),tg,sep=' | ');model<-native$models[[key]]
    im<-model$df_IM;importance_rows[[key]]<-data.frame(row=label,column=im$LRpair,value=im$IM)
    pim<-model$df_pIM;partial_rows[[key]]<-data.frame(row=label,column=sub('^shuffle_','',rownames(pim)),value=pim$pIM)
    quality_rows[[key]]<-data.frame(row=label,column=c('Receiver cells','LR predictors','OOB MSE','OOB R-squared'),value=c(model$model$num.samples,length(model$model$variable.importance),model$model$prediction.error,model$model$r.squared))
  }
  if(length(importance_rows)){all_importance[[sample]]<-do.call(rbind,importance_rows);all_partial[[sample]]<-do.call(rbind,partial_rows);all_quality[[sample]]<-do.call(rbind,quality_rows)}
  if(length(native$excluded_models)) all_excluded[[sample]]<-do.call(rbind,lapply(names(native$excluded_models),function(key){pieces<-strsplit(key,'|',fixed=TRUE)[[1]];groups<-strsplit(pieces[1],'-',fixed=TRUE)[[1]];data.frame(sample=sample,source=decode[[groups[1]]],target=decode[[groups[2]]],target_gene=pieces[2],reason=native$excluded_models[[key]])}))
  # Exact paper loop rule: A ligand becomes the reverse path target and vice versa.
  feedback<-list();network_names<-names(native$networks)
  for(i in seq_len(length(types)-1L)) for(j in (i+1L):length(types)){
    ab<-paste(codes[[types[i]]],codes[[types[j]]],sep='-');ba<-paste(codes[[types[j]]],codes[[types[i]]],sep='-')
    if(!all(c(ab,ba)%in%network_names)) next
    p1<-process_ml_net(native$networks[[ab]]);p2<-process_ml_net(native$networks[[ba]])
    if(!nrow(p1)||!nrow(p2)) next
    names(p1)<-paste0(names(p1),'1');names(p2)<-paste0(names(p2),'2')
    loops<-merge(p1,p2,by.x=c('Ligand1','Target1'),by.y=c('Target2','Ligand2'))
    if(nrow(loops)){loops$Ligand2<-loops$Target1;loops$Target2<-loops$Ligand1;loops$cell_type_1<-types[i];loops$cell_type_2<-types[j];feedback[[paste(i,j)]]<-loops}
  }
  if(length(feedback)) all_feedback[[sample]]<-do.call(rbind,feedback)
  dd<-dist_mat[upper.tri(dist_mat)];all_distance[[sample]]<-data.frame(sample=sample,cells=nrow(meta),cell_types=length(types),minimum=min(dd),median=median(dd),maximum=max(dd),pairs_below_native_floor=sum(dd<1),coordinate_unit=cfg$coordinate_unit)
  sample_diag[[sample]]<-data.frame(sample=sample,cells=nrow(meta),cell_types=length(types),multilayer_cell_pairs=length(native$networks),active_cell_pairs=length(native$activities),unique_group_lr=nrow(group_lr),modeled_targets=length(native$models),excluded_targets=length(native$excluded_models),feedback_loops=if(length(feedback))nrow(do.call(rbind,feedback))else 0)
  top<-head(group_lr[order(-group_lr$score,group_lr$interaction),],max_spatial_lr)
  for(k in seq_len(nrow(top))){z<-activity_cells[activity_cells$source==top$source[k]&activity_cells$target==top$target[k]&activity_cells$ligand==top$ligand[k]&activity_cells$receptor==top$receptor[k],];spatial_tables[[paste(sample,k,sep='|')]]<-data.frame(sample=sample,cell=z$cell,x=coords[z$cell,1],y=coords[z$cell,2],value=z$activity,title=paste(top$source[k],top$interaction[k],top$target[k],sep=' → '))}
}

lr_rows<-do.call(rbind,all_lr);count_rows<-do.call(rbind,all_counts);strength_rows<-do.call(rbind,all_strength)
c$add('stmlnet_lr_activity','lr_edges',lr_rows,'每条进入L-R-TF-TG网络的LR在接收群细胞上的原生距离加权活性均值；score = mean_receiver[receptor × sum_sender(ligand/max(distance,1))]。supported只表示正的模型活性，没有P值或供体检验。score_per_sender_cell仅作群大小诊断。',direction='higher',additive=FALSE,value_kind='native_score',axis_label='Mean distance-weighted LR activity',statistical_unit='receiver cells pooled within each sample',test_definition='No inferential test; supported means positive model-defined activity',display_top_lr=20,display_top_cell_pairs=16)
c$add('stmlnet_lr_count_network','network',count_rows,'每个有向细胞群对中具有正原生活性的唯一LR数量；这是候选计数，不是显著相互作用数。',direction='higher',additive=TRUE,value_kind='count',axis_label='Positive LR count',directed=TRUE)
c$add('stmlnet_activity_network','network',strength_rows,'每个有向细胞群对中不同LR原生活性均值之和；仅用于同一运行内总览，受发送细胞数、密度和坐标单位影响。',direction='higher',additive=TRUE,value_kind='nonnegative_strength',axis_label='Summed native LR activity',directed=TRUE)
c$add('stmlnet_multilayer_membership','molecular_links',do.call(rbind,all_paths),'进入原生多层网络的Ligand→Receptor→TF→Target成员；value为该分子边跨实际细胞群路径的出现次数，不是效应量或因果强度。',direction='higher',additive=TRUE,value_kind='count',axis_label='Path membership count',directed=TRUE)
if(length(all_importance)) c$add('stmlnet_lrtg_importance','matrix',do.call(rbind,all_importance),'原生ranger随机森林对每个接收群靶基因的LR permutation importance；可为负，没有P值。',figure_role='stmlnet_lrtg_importance',direction='higher',additive=FALSE,value_kind='native_score',axis_label='LR–target permutation importance',display_top_rows=24,display_top_columns=20)
if(length(all_partial)) c$add('stmlnet_regulator_importance','matrix',do.call(rbind,all_partial),'原生stMLnet把含某一配体或受体的所有LR预测列同时打乱后，逐树OOB MSE增加的重复均值；可为负，没有P值。',figure_role='stmlnet_regulator_importance',direction='higher',additive=FALSE,value_kind='native_score',axis_label='Partial regulator OOB importance',display_top_rows=24,display_top_columns=20)
if(length(all_quality)) c$add('stmlnet_model_quality','matrix',do.call(rbind,all_quality),'每个原生靶基因随机森林的接收细胞数、LR预测变量数、OOB MSE和ranger OOB R-squared；负R-squared保留。',figure_role='stmlnet_model_quality',direction='higher',additive=FALSE,value_kind='native_score',axis_label='Native model diagnostic',column_order=c('Receiver cells','LR predictors','OOB MSE','OOB R-squared'),display_top_rows=30)
c$add('stmlnet_distance_sensitivity','matrix',do.call(rbind,all_sensitivity),'保持表达、细胞和多层候选固定，仅将全部坐标乘以预声明因子并按原公式重算LR均值；coordinate × 1是原生结果，其余仅诊断距离单位敏感性。',figure_role='stmlnet_distance_sensitivity',direction='higher',additive=FALSE,value_kind='native_score',axis_label='Mean LR activity',column_order=vapply(scale_factors,function(factor)paste0('coordinate × ',format(factor,trim=TRUE,scientific=FALSE)),character(1)),display_top_rows=30)
c$add('stmlnet_spatial_celltypes','spatial_points',do.call(rbind,all_positions),'进入stMLnet的全部实际细胞/spot坐标与原始细胞类型；value=0只是类型图占位，颜色使用label。',coordinate_unit=cfg$coordinate_unit,physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable),coordinate_provenance=cfg$coordinate_provenance,y_down=isTRUE(cfg$y_down))
for(i in seq_along(spatial_tables)){z<-spatial_tables[[i]];title<-unique(z$title);z$title<-NULL;c$add(paste0('stmlnet_spatial_lr_',sprintf('%03d',i)),'spatial_points',z,'接收细胞上的原生距离加权LR活性空间分布；仅选择全表均值靠前的LR用于展示，完整细胞级值在stmlnet_receiver_cell_activity.tsv和原生RDS。',title=title,axis_label='Native LR activity',coordinate_unit=cfg$coordinate_unit,physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable),coordinate_provenance=cfg$coordinate_provenance,y_down=isTRUE(cfg$y_down))}
if(length(all_feedback)){
  fb<-do.call(rbind,all_feedback);links<-rbind(data.frame(source=fb$Ligand1,target=fb$Receptor1,source_type=paste0(fb$cell_type_1,' ligand'),target_type=paste0(fb$cell_type_2,' receptor')),data.frame(source=fb$Receptor1,target=fb$TF1,source_type=paste0(fb$cell_type_2,' receptor'),target_type=paste0(fb$cell_type_2,' TF')),data.frame(source=fb$TF1,target=fb$Target1,source_type=paste0(fb$cell_type_2,' TF'),target_type=paste0(fb$cell_type_2,' reciprocal ligand')),data.frame(source=fb$Ligand2,target=fb$Receptor2,source_type=paste0(fb$cell_type_2,' ligand'),target_type=paste0(fb$cell_type_1,' receptor')),data.frame(source=fb$Receptor2,target=fb$TF2,source_type=paste0(fb$cell_type_1,' receptor'),target_type=paste0(fb$cell_type_1,' TF')),data.frame(source=fb$TF2,target=fb$Target2,source_type=paste0(fb$cell_type_1,' TF'),target_type=paste0(fb$cell_type_1,' reciprocal ligand')));links<-aggregate(rep(1,nrow(links)),links,sum);names(links)[5]<-'value';c$add('stmlnet_feedback_loops','molecular_links',links,'论文定义的双向反馈路径：A的ligand经B的receptor/TF成为B的target，同时B的ligand经A的receptor/TF成为A的target，且两端target恰为对向ligand。value为路径出现次数。',direction='higher',additive=TRUE,value_kind='count',axis_label='Feedback path count',directed=TRUE);c$wt(fb,'stmlnet_feedback_loop_paths.tsv')
}
c$wt(do.call(rbind,all_activity_cells),'stmlnet_receiver_cell_activity.tsv');c$wt(do.call(rbind,all_path_rows),'stmlnet_lrtg_paths.tsv');if(length(all_excluded))c$wt(do.call(rbind,all_excluded),'stmlnet_excluded_target_models.tsv');c$wt(do.call(rbind,all_distance),'distance_diagnostics.tsv');c$wt(do.call(rbind,sample_diag),'sample_diagnostics.tsv');c$wt(candidates,'candidate_table.tsv')
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$complete_receiver_cell_activity<-list(path='stmlnet_receiver_cell_activity.tsv',sha256=c$hash(file.path(c$out,'stmlnet_receiver_cell_activity.tsv')))
c$bundle$provenance$complete_lrtg_paths<-list(path='stmlnet_lrtg_paths.tsv',sha256=c$hash(file.path(c$out,'stmlnet_lrtg_paths.tsv')))
c$bundle$provenance$limitations<-c('官方runstMLnet在固定提交中错误读取未定义的全局ex_inputs；入口按官方教程顺序直接编排runMLnet、getSiganlActivity和runRFModel。','固定runMLnet的自动候选分支混用RecClu/RecClus与LigClu/LigClus，getHighExpGene还读取未定义pct.ct/expr.ct；入口要求带来源的显式候选表，不声称运行这些损坏分支。','作者仓库把DESCRIPTION和NAMESPACE命名为.txt，README所述install_github不能直接形成标准R包；入口同时校验源码、可安装tar.gz及函数文件。','runMLnet固定排除同群发送与接收，当前分支不输出自分泌。','原生LR活性没有距离截止，distance<1统一置1；绝对值随坐标尺度、细胞密度和发送群大小变化，不能跨数据集直接比较。','随机森林以同一切片接收细胞为训练观察，OOB表现不等于独立供体泛化；IM/pIM没有P值或多重校正。','反馈环来自先验路径与表达筛选网络的结构匹配，不能证明受体激活、时间顺序或实验因果。','没有独立样本设计时，不生成条件特异性、疾病效应或供体统计图。')
c$bundle$figure_inapplicability<-list(condition_effects='stMLnet原生分支不拟合供体条件效应；需多个独立供体在固定候选和坐标尺度下另做供体层比较。',cellchat_patterns='stMLnet没有CellChat NMF模式。',factors='stMLnet没有张量、MOFA或NMF分解。',enrichment='当前原生分支没有带背景定义的富集检验。',embedding='stMLnet没有细胞或分子潜在嵌入。',spatial_direction='stMLnet的1/d活性是标量，没有原生方向向量。',relay_dynamic='stMLnet反馈环是静态结构匹配，不是时间轨迹或多跳动态。',special_molecules='固定stMLnetDB没有经核验的代谢物或递质身份层。',functional_clinical='stMLnet原生分支不计算功能、临床或药敏关联；需要另有真实结局和供体层模型。')
c$wj(c$bundle,'bundle.json');c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',seed=seed,source_commit=params$commit),'run_metadata.json')
