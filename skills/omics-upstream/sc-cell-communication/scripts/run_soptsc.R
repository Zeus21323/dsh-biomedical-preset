#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg));source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'SoptSC','Matrix','1.7.6',counts_input=FALSE,species=c('human','mouse'));cfg<-c$cfg
for(key in c('native_root','ligand_receptor','receptor_target','input_provenance','resource_provenance','resource_version','normalization_definition')) if(is.null(cfg[[key]])) stop('缺少：',key)
for(pkg in c('dplyr','reshape2','doParallel','foreach','digest')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
suppressPackageStartupMessages(library(dplyr));suppressPackageStartupMessages(library(doParallel))
root<-c$resolve(cfg$native_root);lr_path<-c$resolve(cfg$ligand_receptor);rt_path<-c$resolve(cfg$receptor_target)
expected<-c(
  'DESCRIPTION'='b8ac5e89767607ad17895fafc9965e89d057390403306bccd446c23b916f51e8',
  'LICENSE'='1dcd24e593a53bcae6705b4475857d104b674000d8800bfe6bf3891837332dab',
  'R/Signaling.R'='31998c9e4032293700e76162d0bd24bd1edae31fccd9d81aa453dbc04ba1353d')
for(path in names(expected)) if(c$hash(file.path(root,path))!=expected[[path]]) stop('RSoptSC源码摘要不符：',path)
desc<-read.dcf(file.path(root,'DESCRIPTION'));if(desc[1,'Version']!='0.0.0.9000'||!grepl('MIT',desc[1,'License'],fixed=TRUE)) stop('RSoptSC版本或许可字段不符')
source(file.path(root,'R/Signaling.R'),local=.GlobalEnv)

lr_resource<-read.delim(lr_path,check.names=FALSE);rt_resource<-read.delim(rt_path,check.names=FALSE)
names(lr_resource)<-tolower(names(lr_resource));names(rt_resource)<-tolower(names(rt_resource))
if(!all(c('ligand','receptor')%in%names(lr_resource))||!all(c('receptor','target','direction')%in%names(rt_resource))) stop('SoptSC资源列必须为Ligand/Receptor与Receptor/Target/Direction')
if(anyNA(lr_resource[,c('ligand','receptor')])||anyNA(rt_resource[,c('receptor','target','direction')])||any(trimws(as.matrix(lr_resource[,c('ligand','receptor')]))=='')||any(trimws(as.matrix(rt_resource[,c('receptor','target','direction')]))=='')) stop('SoptSC资源含空身份')
if(!all(tolower(rt_resource$direction)%in%c('up','down','?'))) stop('受体靶基因方向只能是up/down/?')
if(anyDuplicated(tolower(rownames(c$expr)))||anyDuplicated(tolower(colnames(c$expr)))) stop('SoptSC会转成小写身份，输入在忽略大小写后必须唯一')

cores<-as.integer(cfg$cores%||%1L);max_rows<-as.numeric(cfg$max_cell_pair_rows%||%5e6)
if(is.na(cores)||cores!=1L) stop('固定原生函数会忽略请求核数并调用detectCores；已核验入口只允许cores=1')
if(!is.finite(max_rows)||max_rows<1e5) stop('max_cell_pair_rows至少为100000')
params<-list(commit='052195bb98157e6a35957b71141ef1bf5bb9f024',cores=cores,max_cell_pair_rows=max_rows,resource_version=cfg$resource_version,normalize_aggregate=TRUE,cluster_normalize_rows=TRUE)
c$start_cache(c(unname(expected),c$hash(lr_path),c$hash(rt_path)),params)
c$bundle$method_version<-'RSoptSC 0.0.0.9000 signaling module'
c$bundle$implementation<-'native_ImportPathway_GetSignalingPartners_ClusterSig'
c$bundle$provenance$upstream<-list(url='https://github.com/mkarikom/RSoptSC',commit=params$commit,version='0.0.0.9000',license='MIT')
c$bundle$provenance$resource_hashes<-list(ligand_receptor=c$hash(lr_path),receptor_target=c$hash(rt_path))
c$bundle$provenance$semantics<-paste('SoptSC对每个LR计算细胞对alpha=exp(-1/(ligand*receptor))，再按受体的上调靶基因beta与下调靶基因gamma及kappa/delta修正。',
  '每个有非零总信号的发送细胞，其接收分布先在单个LR内归一化。原生群级LR值只对该LR有正信号的发送细胞求平均；ClusterSig随后等权汇总各LR的群级分布并在每个发送群内再次归一化。',
  '没有原生置换、P值或供体差异；正值只表示模型定义的非零概率份额。')

all_lr<-list();all_network<-list();all_expression<-list();all_pathway<-list();sample_diagnostics<-list()
samples<-unique(c$meta$sample)
for(si in seq_along(samples)){
  sample<-samples[[si]];meta<-c$sample_meta(sample);ids<-rownames(meta);expr<-as.matrix(c$expr[,ids,drop=FALSE])
  identity_map<-setNames(rownames(expr),tolower(rownames(expr)))
  native<-c$native(si,sample,function(){
    pathway<-ImportPathway(lig_table=lr_resource,rec_table=rt_resource,lig_table_path=lr_path,rec_table_path=rt_path,data=expr)
    if(!nrow(pathway$pathway_removed)) stop('样本',sample,'在资源身份过滤后没有完整ligand-receptor-target路径')
    n_lr<-nrow(unique(pathway$pathway_removed[,c('ligand','receptor')]))
    requested_rows<-ncol(expr)^2*n_lr
    if(requested_rows>max_rows) stop('样本',sample,'将生成',requested_rows,'条LR×细胞对原生记录，超过max_cell_pair_rows；不静默抽样细胞或LR')
    old_check<-Sys.getenv('_R_CHECK_LIMIT_CORES_',unset=NA_character_);Sys.setenv('_R_CHECK_LIMIT_CORES_'='TRUE')
    on.exit({doParallel::stopImplicitCluster();if(is.na(old_check))Sys.unsetenv('_R_CHECK_LIMIT_CORES_')else Sys.setenv('_R_CHECK_LIMIT_CORES_'=old_check)},add=TRUE)
    pmats<-GetSignalingPartners(expr,ids,pathway,normalize_aggregate=TRUE)
    cluster<-ClusterSig(pmats,cluster_labels=meta$cell_type,normalize_rows=TRUE)
    list(pathway=pathway,Pmats=pmats,cluster=cluster)
  })
  pmats<-native$Pmats;pathway<-native$pathway
  if(length(pmats$P)!=length(pmats$LR)||!length(pmats$P)) stop('SoptSC原生LR矩阵与身份没有一一对应')
  lr_tables<-list()
  cell_row_errors<-numeric(length(pmats$P))
  for(i in seq_along(pmats$P)){
    p<-pmats$P[[i]];sums<-tapply(p$value,p$Var1,sum);positive<-sums>0
    cell_row_errors[i]<-if(any(positive))max(abs(sums[positive]-1))else 0
    grouped<-ClusterSig_single(p,cluster_labels=meta$cell_type,normalize_rows=TRUE)
    ligand<-unname(identity_map[tolower(pmats$LR[[i]]$lig)]);receptor<-unname(identity_map[tolower(pmats$LR[[i]]$rec)])
    if(is.na(ligand)||is.na(receptor)) stop('SoptSC输出LR无法映射回输入基因身份')
    lr_tables[[i]]<-data.frame(sample=sample,donor=unique(meta$donor),condition=unique(meta$condition),source=as.character(grouped$cluster.Var1),target=as.character(grouped$cluster.Var2),
      ligand=ligand,receptor=receptor,interaction=paste(ligand,receptor,sep='→'),score=as.numeric(grouped$value),tested=TRUE,supported=as.numeric(grouped$value)>0)
  }
  all_lr[[sample]]<-do.call(rbind,lr_tables)
  network<-native$cluster$P_tot
  all_network[[sample]]<-data.frame(sample=sample,source=as.character(network$cluster.Var1),target=as.character(network$cluster.Var2),value=as.numeric(network$value))
  genes<-unique(c(as.character(pathway$pathway_removed$ligand),as.character(pathway$pathway_removed$receptor),as.character(pathway$pathway_removed$target)))
  genes<-unname(identity_map[tolower(genes)]);genes<-genes[!is.na(genes)]
  expression_rows<-do.call(rbind,lapply(unique(meta$cell_type),function(group){data.frame(row=paste(sample,group,sep=' | '),column=genes,value=rowMeans(expr[genes,meta$cell_type==group,drop=FALSE]))}))
  all_expression[[sample]]<-expression_rows
  lr_links<-unique(pathway$pathway_removed[,c('ligand','receptor')]);lr_links<-data.frame(source=unname(identity_map[tolower(lr_links$ligand)]),target=unname(identity_map[tolower(lr_links$receptor)]),source_type='ligand',target_type='receptor',value=1)
  rt_links<-unique(pathway$pathway_removed[,c('receptor','target','direction')]);rt_links<-data.frame(source=unname(identity_map[tolower(rt_links$receptor)]),target=unname(identity_map[tolower(rt_links$target)]),source_type='receptor',target_type=paste0(tolower(rt_links$direction),' target'),value=1)
  links<-rbind(lr_links,rt_links);links$sample<-sample;all_pathway[[sample]]<-links
  total_sums<-tapply(pmats$P_tot$value,pmats$P_tot$Var1,sum);total_positive<-total_sums>0
  group_sums<-tapply(network$value,network$cluster.Var1,sum)
  sample_diagnostics[[sample]]<-data.frame(sample=sample,cells=ncol(expr),cell_types=length(unique(meta$cell_type)),retained_path_rows=nrow(pathway$pathway_removed),lr_pairs=length(pmats$P),
    cell_pair_rows=ncol(expr)^2*length(pmats$P),max_lr_cell_row_sum_error=max(cell_row_errors),max_total_cell_row_sum_error=if(any(total_positive))max(abs(total_sums[total_positive]-1))else 0,max_group_row_sum_error=max(abs(group_sums-1)))
}
lr_rows<-do.call(rbind,all_lr);network_rows<-do.call(rbind,all_network);expression_rows<-do.call(rbind,all_expression);pathway_rows<-do.call(rbind,all_pathway);diagnostics<-do.call(rbind,sample_diagnostics)
c$add('soptsc_lr_group_signaling','lr_edges',lr_rows,'每个LR内先将每个有正总信号的发送细胞对全部接收细胞的原生SoptSC概率归一化，再仅对该发送群内这些活跃发送细胞求平均并按接收群汇总；每个有信号的发送群×LR的target值之和为1。tested表示候选经过模型计算，supported只表示模型正值，没有统计检验',direction='higher',additive=FALSE,value_kind='row_normalized_probability_share',axis_label='Mean receiver probability share',statistical_unit='active sender cells pooled within each sample',test_definition='Model evaluation only, with no inferential test; supported means a positive model-defined probability share.')
c$add('soptsc_group_signaling','network',network_rows,'原生ClusterSig先对每个LR仅在有正信号的发送细胞中计算群级接收份额，再等权汇总各LR并在每个发送群内归一化；每个发送群target之和为1，因此这些互斥接收群的概率份额可相加。该表不是直接对细胞级P_tot求群均值',direction='higher',additive=TRUE,value_kind='row_normalized_probability_share',axis_label='Aggregate receiver probability share',directed=TRUE)
c$add('soptsc_pathway_expression','matrix',expression_rows,'进入SoptSC路径模型的配体、受体及上/下调靶基因在各实测细胞群的输入表达均值；用于核查模型端点，不是第二份通讯检验',direction='higher',additive=FALSE,value_kind='mean_input_expression',axis_label='Mean input expression',display_top_columns=30)
c$add('soptsc_pathway_membership','molecular_links',pathway_rows,'版本化先验中的Ligand→Receptor与Receptor→up/down target成员关系；value=1只表示资源成员，不是推断强度',direction='higher',additive=FALSE,value_kind='membership',axis_label='Prior membership')
c$wt(diagnostics,'sample_diagnostics.tsv')
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$limitations<-c('GetSignalingPartners的ids参数未被固定源码使用；细胞顺序来自严格对齐的表达矩阵与metadata。','normalize_aggregate参数在固定源码中没有控制分支；原生实现始终对单LR和P_tot的发送细胞行归一化。','ClusterSig_single会先丢弃零值细胞对，再按仍有正信号的发送细胞数求平均；LR群值不把无信号发送细胞纳入分母。','受体靶基因按receptor和direction选取，不按ligand进一步区分；同一受体的不同配体共享靶基因集合。','群级概率来自同一样本池化细胞，不是供体统计、条件差异、物理结合概率、分子通量或因果效应。','算法会显式形成LR×细胞×细胞长表；超过max_cell_pair_rows时失败，不抽样后冒充全量。')
c$wj(c$bundle,'bundle.json');c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',cores=cores),'run_metadata.json')
