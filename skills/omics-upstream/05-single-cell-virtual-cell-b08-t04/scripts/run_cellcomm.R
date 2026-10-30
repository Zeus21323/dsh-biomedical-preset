#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg));source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'CellComm','Matrix','1.7.6',counts_input=FALSE,species='human');cfg<-c$cfg
for(key in c('native_root','lr_resource','input_provenance','resource_provenance','resource_version','threshold_provenance')) if(is.null(cfg[[key]])) stop('缺少：',key)
for(pkg in c('dplyr','digest')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
root<-c$resolve(cfg$native_root);resource<-c$resolve(cfg$lr_resource)
expected<-c(
  'DESCRIPTION'='e50129dda3a17d5bdda9b700ae21aa9bff7c5235e9111a8f69c94adcf824660f',
  'LICENSE.txt'='f3adb52430407b7fbe485b7c2c24894642034c4bce850c07eacd584d9f1ec3a6',
  'R/population.pairing_CellComm.R'='c19fe0b3182b5f39e26bfb02c8aac5e25313a9b2f2044203cb2aa48b2ebeac07',
  'R/calculateObservedMean_CellComm.R'='b4681af3b7b16d5f44f76b2556572012a313203024b403cecb6169b0dddf0662',
  'R/calculatePvalue_CellComm.R'='9e4ad9bd6a8cc90f3d464be503b2cf2e2bb58d3e4f68209180c6f0233e7292b0',
  'R/clusterPermutation_CellComm.R'='9b5537eb4b7a98cc406bcf55908e1d344b5a1558d9479f12d22dee45014c2e3b',
  'R/interactionmatrix_CellComm.R'='bc250a4686189ad26aa5c8f79f7116721d8e749edd97dbd214b793b13172e64a',
  'R/cellnetwork3_CellComm.R'='59bb52f880a8d9b4e30ebb3fff89b53a441b34a90db7a550bf27c7c2b4db78c1')
for(path in names(expected)) if(c$hash(file.path(root,path))!=expected[[path]]) stop('FUSCA/CellComm源码摘要不符：',path)
desc<-read.dcf(file.path(root,'DESCRIPTION'));if(desc[1,'Version']!='1.3.1'||desc[1,'License']!='MIT') stop('FUSCA版本或许可字段不符')
for(path in names(expected)[grepl('^R/',names(expected))]) source(file.path(root,path),local=.GlobalEnv)

lr0<-readRDS(resource)
if(all(c('from','to')%in%names(lr0))) lr<-data.frame(ligand=as.character(lr0$from),receptor=as.character(lr0$to)) else if(all(c('ligand','receptor')%in%names(lr0))) lr<-data.frame(ligand=as.character(lr0$ligand),receptor=as.character(lr0$receptor)) else stop('LR RDS需要from/to或ligand/receptor列')
if(anyNA(lr)||any(trimws(as.matrix(lr))=='')) stop('LR资源含缺失或空身份')
unparseable_lr<-grepl('_',lr$ligand,fixed=TRUE)|grepl('_',lr$receptor,fixed=TRUE)
# 上游把Pair.Name以下划线拆成两个基因，无法无损表示基因本身含下划线的资源行。
lr<-unique(lr[!unparseable_lr,,drop=FALSE]);lr<-lr[lr$ligand%in%rownames(c$expr)&lr$receptor%in%rownames(c$expr),,drop=FALSE]
if(!nrow(lr)) stop('LR资源与输入基因无双端交集')
lr$Pair.Name<-paste(lr$ligand,lr$receptor,sep='_');ligands<-unique(lr$ligand);receptors<-unique(lr$receptor);genes<-unique(c(ligands,receptors))

threshold<-as.numeric(cfg$expression_threshold%||%.25);nperm<-as.integer(cfg$n_permutations%||%1000L);seed<-as.integer(cfg$seed%||%20260909L);alpha<-as.numeric(cfg$alpha%||%.05)
mode<-cfg$permutation_mode%||%'documented_intent_deterministic';max_rows<-as.numeric(cfg$max_permutation_rows%||%1e7)
if(!is.finite(threshold)||threshold<0||!is.finite(alpha)||alpha<=0||alpha>=1||is.na(nperm)||nperm<100||nperm>10000||is.na(seed)||!is.finite(max_rows)||max_rows<1e5) stop('CellComm参数无效')
if(mode!='documented_intent_deterministic') stop('只执行可复现的documented_intent_deterministic置换；上游PSOCK worker未设种子')
params<-list(commit='348d653184928d430bb8db7489f80947f25cc93e',expression_threshold=threshold,n_permutations=nperm,seed=seed,alpha=alpha,
  permutation_mode=mode,lr_measured_rows=nrow(lr),unparseable_resource_rows=sum(unparseable_lr),resource_version=cfg$resource_version)
c$start_cache(c(unname(expected),c$hash(resource)),params)
c$bundle$method_version<-'1.3.1 + deterministic documented-intent permutation adapter'
c$bundle$implementation<-'native_population_pairing_observed_mean_calculate_pvalue_with_audited_deterministic_label_permutation'
c$bundle$provenance$upstream<-list(url='https://github.com/edroaldo/fusca',commit=params$commit,version='1.3.1',license='MIT')
c$bundle$provenance$resource_hash<-c$hash(resource)
c$bundle$provenance$semantics<-paste('CellComm先以细胞群平均表达过阈值筛出发送配体与接收受体，原生分数是两端群平均表达的算术均值。',
  '细胞类型标签置换保留群大小，P=(1+置换分数不低于观测值的次数)/(1+B)。作者实现在自建PSOCK worker上没有设置随机流，因此适配器以显式seed串行生成同一标签置换，再调用原生calculatePvalue。',
  '原生P未多重校正；另列全部候选BH仅作诊断。这是池化细胞标签置换，不是供体差异或因果证据。')

all_lr<-list();all_counts<-list();all_resolution<-list();sample_diagnostics<-list()
samples<-unique(c$meta$sample)
for(si in seq_along(samples)){
  sample<-samples[[si]];meta<-c$sample_meta(sample);ids<-rownames(meta);expr<-as.matrix(c$expr[genes,ids,drop=FALSE])
  original_types<-sort(unique(meta$cell_type));codes<-sprintf('ct%03d',seq_along(original_types));names(codes)<-original_types
  encoded<-unname(codes[meta$cell_type]);decode<-setNames(names(codes),codes)
  group_mean<-function(labels){
    ans<-lapply(unique(labels),function(g){p<-rowMeans(expr[,labels==g,drop=FALSE]);np<-rowMeans(expr[,labels!=g,drop=FALSE]);data.frame(np=np,p=p,row.names=genes)})
    names(ans)<-unique(labels);ans
  }
  observed_means<-group_mean(encoded)
  candidates<-population.pairing(observed_means,ligands,receptors,threshold,lr)
  if(!nrow(candidates)){
    sample_diagnostics[[sample]]<-data.frame(sample=sample,cells=ncol(expr),cell_types=length(original_types),measured_lr=nrow(lr),threshold_candidates=0,n_permutations=nperm)
    next
  }
  observed<-calculateObservedMean(candidates,observed_means)
  if(nrow(observed)*nperm>max_rows) stop('样本',sample,'的置换长表将有',nrow(observed)*nperm,'行，超过max_permutation_rows；不抽样候选或减少置换伪装完整分析')
  native<-c$native(si,sample,function(){
    set.seed(seed+si-1L);permutations<-vector('list',nperm);label_hashes<-character(nperm)
    for(j in seq_len(nperm)){
      shuffled<-sample(encoded,length(encoded),replace=FALSE);label_hashes[j]<-digest::digest(shuffled,algo='sha256')
      permutations[[j]]<-calculateObservedMean(observed,group_mean(shuffled))
    }
    names(permutations)<-paste0('perm',seq_len(nperm))
    result<-calculatePvalue(permutations,nPerm=nperm,interactions2=observed)
    list(observed_means=observed_means,candidates=candidates,observed=observed,permutations=permutations,permutation_label_hashes=label_hashes,result=result,type_map=data.frame(code=codes,cell_type=names(codes)))
  })
  result<-native$result;result$q_value<-p.adjust(result$pvalue,'BH')
  result$celltype1<-unname(decode[result$celltype1]);result$celltype2<-unname(decode[result$celltype2])
  lr_rows<-data.frame(sample=sample,source=result$celltype1,target=result$celltype2,ligand=result$ligand,receptor=result$receptor,
    interaction=paste(result$ligand,result$receptor,sep='→'),score=result$mean,tested=TRUE,supported=result$pvalue<=alpha,p_value=result$pvalue,q_value=result$q_value,
    ligand_mean=result$mean.ligand,receptor_mean=result$mean.receptor,native_raw_p_supported=result$pvalue<=alpha,bh_diagnostic_supported=result$q_value<=alpha)
  all_lr[[sample]]<-lr_rows
  supported<-lr_rows[lr_rows$supported,,drop=FALSE]
  if(nrow(supported)){
    z<-aggregate(interaction~source+target,supported,function(v)length(unique(v)));names(z)[3]<-'value';z$sample<-sample;all_counts[[sample]]<-z[,c('sample','source','target','value')]
  }
  exceedances<-round(result$pvalue*(nperm+1)-1)
  rv<-as.data.frame(table(exceedances));names(rv)<-c('exceedances','value');rv$row<-sample;rv$column<-paste0('null≥observed=',rv$exceedances);all_resolution[[sample]]<-rv[,c('row','column','value')]
  sample_diagnostics[[sample]]<-data.frame(sample=sample,cells=ncol(expr),cell_types=length(original_types),measured_lr=nrow(lr),threshold_candidates=nrow(result),raw_p_supported=sum(result$pvalue<=alpha),bh_diagnostic_supported=sum(result$q_value<=alpha),n_permutations=nperm,min_p=min(result$pvalue))
}
lr_rows<-if(length(all_lr))do.call(rbind,all_lr) else data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),interaction=character(),score=numeric(),tested=logical(),supported=logical(),p_value=numeric(),q_value=numeric(),ligand_mean=numeric(),receptor_mean=numeric())
count_rows<-if(length(all_counts))do.call(rbind,all_counts) else data.frame(sample=character(),source=character(),target=character(),value=numeric())
resolution_rows<-if(length(all_resolution))do.call(rbind,all_resolution) else data.frame(row=character(),column=character(),value=numeric())
diagnostics<-do.call(rbind,sample_diagnostics)
c$add('cellcomm_ligand_receptor','lr_edges',lr_rows,'CellComm阈值后全部LR候选；score=(发送群配体平均表达+接收群受体平均表达)/2。supported保留作者raw empirical P≤alpha规则；q_value为全候选BH诊断，不改写原生成员。',direction='higher',additive=FALSE,value_kind='mean_endpoint_expression',axis_label='Mean endpoint expression',statistical_unit='pooled cells within each sample',test_definition='Cell-type label permutation preserving group sizes; +1 empirical tail correction; native raw-P support and separate BH diagnostic')
c$add('cellcomm_supported_counts','network',count_rows,'每个样本中通过CellComm原生raw-P规则的唯一LR数量；这是计数，不是分数之和或分子通量。',direction='higher',additive=TRUE,value_kind='count',axis_label='Supported LR count',directed=TRUE)
c$add('cellcomm_permutation_resolution','matrix',resolution_rows,'每个样本的候选数按“置换分数不低于观测值的次数”分布；原生P=(1+该次数)/(1+B)。用于检查置换分辨率与大量并列，不是效应量。',direction='higher',additive=TRUE,value_kind='count',axis_label='Candidate count',display_top_columns=30)
c$wt(diagnostics,'sample_diagnostics.tsv')
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$limitations<-c('作者clusterPermutation在新建PSOCK worker中调用sample，但没有clusterSetRNGStream或等价种子管理；本入口以标记的文档意图修正保证复现。','raw-P阈值未校正；BH仅作诊断。','细胞标签置换检验池化细胞，不是供体统计。',paste0('固定LR资源中有',sum(unparseable_lr),'行含下划线基因身份，上游Pair.Name分隔符无法无损解析，已在测量基因交集前排除并记录。'),'当前入口验收CellComm的群间LR核心分支；PPI→TF的Java flow需额外物种匹配PPI/GRN与marker，未提供时不补造胞内路径。','表达端点均值及LR计数不是结合通量、因果方向或跨数据集可直接比强度。')
c$wj(c$bundle,'bundle.json');c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',seed=seed,n_permutations=nperm),'run_metadata.json')
