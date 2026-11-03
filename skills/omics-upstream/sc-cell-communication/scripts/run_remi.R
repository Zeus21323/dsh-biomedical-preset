#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg));source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(args,'REMI','qgraph','1.10.1',counts_input=FALSE,species='human');cfg<-c$cfg

for(key in c('native_root','input_provenance','resource_provenance','resource_version','independent_unit_definition')) if(is.null(cfg[[key]])) stop('缺少：',key)
for(pkg in c('dplyr','data.table','igraph','glasso','OneR','magrittr','Matrix','digest')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
suppressPackageStartupMessages({library(dplyr);library(magrittr)})
if(as.character(packageVersion('igraph'))!='2.0.3') stop('REMI固定源码需要仍支持inc()的igraph 2.0.3')

root<-c$resolve(cfg$native_root)
commit<-'704b11b4f66e59c7683ad544cf9c0aa41751d83a'
expected<-c(
  'DESCRIPTION'='03e6d6c9155107a0a5100ffe39d7917fd2e4d963acccb81308318f5d86e8fdc1',
  'R/load_functions.R'='ae822d793b304fb09a3306c50945efce70791e620a7c9f30ec6153ab8b494ffb',
  'R/load_subfunctions.R'='783c3d16dccf9246427f00dee4470f87244a4868c3548a27b725bbc35e46af54',
  'data/curr.lr.filt.rda'='ca2285fcdef25334cf3b5e3849cbbd0247f45d4f35112c2fc584b06551fccd62',
  'data/g.biogrid.rda'='ca986bd2d1c1d52f7c05373234f118a5775db61bcc7e1df8aa162d9995ffebad',
  'data/pathway.genelist.rda'='9359d5cc176021474b20385c0020dfcc0dff916053c2ab99617d49cca9db04c4')
for(path in names(expected)) if(!file.exists(file.path(root,path))||c$hash(file.path(root,path))!=expected[[path]]) stop('REMI固定源码或资源摘要不符：',path)
observed_commit<-system2('git',c('-C',root,'rev-parse','HEAD'),stdout=TRUE)
if(length(observed_commit)!=1||observed_commit!=commit) stop('REMI源码提交不符：',paste(observed_commit,collapse=' '))
desc<-read.dcf(file.path(root,'DESCRIPTION'))
if(desc[1,'Version']!='0.0.0.9000') stop('REMI源码版本改变')
if(!grepl('use_mit_license',desc[1,'License'],fixed=TRUE)) stop('REMI源码许可占位字段改变；须重新核验')

# The upstream top-level file installs and loads many plotting/enrichment packages
# that the REMI core never calls. Evaluate every function definition from the
# fixed files without rewriting its body or triggering network installation.
load_fixed_functions<-function(path){
  for(expr in parse(path)){
    if(is.call(expr)&&as.character(expr[[1]])%in%c('<-','=')&&is.call(expr[[3]])&&as.character(expr[[3]][[1]])=='function') eval(expr,envir=.GlobalEnv)
  }
}
load_fixed_functions(file.path(root,'R/load_subfunctions.R'))
load_fixed_functions(file.path(root,'R/load_functions.R'))
resource_env<-new.env(parent=emptyenv())
for(path in c('data/curr.lr.filt.rda','data/g.biogrid.rda','data/pathway.genelist.rda')) load(file.path(root,path),envir=resource_env)
curr.lr.filt<-resource_env$curr.lr.filt;g.biogrid<-resource_env$g.biogrid;pathway.genelist<-resource_env$pathway.genelist
if(!identical(names(curr.lr.filt),c('Pair.Name','Ligand','Receptor'))||nrow(curr.lr.filt)!=1909) stop('REMI作者LR资源结构改变')

input_level<-cfg$input_level%||%'cell_level'
if(!input_level%in%c('cell_level','profile_level')) stop('input_level只能是cell_level或profile_level')
condition_filter<-cfg$condition_filter%||%NULL
if(!is.null(condition_filter)){
  keep<-as.character(c$meta$condition)==as.character(condition_filter)
  if(!any(keep)) stop('condition_filter没有匹配输入')
  c$expr<-c$expr[,keep,drop=FALSE];c$meta<-c$meta[keep,,drop=FALSE]
}
conditions<-unique(as.character(c$meta$condition))
if(length(conditions)!=1) stop('REMI一次只拟合一个条件；多条件输入必须提供condition_filter，条件比较须另做供体层模型')
incompatible_gene_ids<-rownames(c$expr)[grepl('_',rownames(c$expr),fixed=TRUE)]
if(any(grepl('_',unique(c(curr.lr.filt$Ligand,curr.lr.filt$Receptor)),fixed=TRUE))) stop('REMI作者LR资源端点含下划线，固定节点解析不再安全')
celltypes<-as.character(cfg$cell_types%||%sort(unique(c$meta$cell_type)))
if(length(celltypes)<2||anyDuplicated(celltypes)||any(!celltypes%in%c$meta$cell_type)||any(grepl('_',celltypes,fixed=TRUE))) stop('至少需要两个身份唯一且不含下划线的真实细胞类型')
if(length(celltypes)>8&&!isTRUE(cfg$acknowledge_quadratic_runtime)) stop('超过8类会平方扩张LR组合；须显式设置acknowledge_quadratic_runtime=true')

minimum_cells<-as.integer(cfg$min_cells_per_profile%||%10L)
minimum_units<-as.integer(cfg$min_independent_units%||%8L)
if(is.na(minimum_cells)||minimum_cells<1||is.na(minimum_units)||minimum_units<6) stop('min_cells_per_profile须至少1，min_independent_units须至少6')
donor_condition<-tapply(as.character(c$meta$condition),as.character(c$meta$donor),function(x)length(unique(x)))
if(any(donor_condition!=1)) stop('同一独立供体不能跨多个条件进入同一次REMI拟合')

groups<-interaction(as.character(c$meta$donor),as.character(c$meta$cell_type),drop=TRUE,lex.order=TRUE)
group_indices<-split(seq_len(ncol(c$expr)),groups)
records<-lapply(group_indices,function(ix){
  data.frame(donor=as.character(c$meta$donor[ix[1]]),cell_type=as.character(c$meta$cell_type[ix[1]]),n_profiles=length(ix),stringsAsFactors=FALSE)
})
profile_info<-do.call(rbind,records);rownames(profile_info)<-names(group_indices)
if(input_level=='profile_level'&&any(profile_info$n_profiles!=1)) stop('profile_level要求每个供体×细胞类型恰有一个表达谱')
if(input_level=='cell_level') profile_info$eligible<-profile_info$n_profiles>=minimum_cells else profile_info$eligible<-TRUE
profile_info<-profile_info[profile_info$cell_type%in%celltypes,,drop=FALSE]
complete_donors<-Reduce(intersect,lapply(celltypes,function(ct)profile_info$donor[profile_info$cell_type==ct&profile_info$eligible]))
complete_donors<-sort(unique(complete_donors))
if(length(complete_donors)<minimum_units) stop('完整且合格的独立供体只有',length(complete_donors),'，少于预声明阈值',minimum_units)
if(any(grepl('_',complete_donors,fixed=TRUE))) stop('REMI固定源码用下划线拆分样本；独立供体身份不能含下划线')

expr_dense<-as.matrix(c$expr);storage.mode(expr_dense)<-'double'
if(length(incompatible_gene_ids)) expr_dense<-expr_dense[!rownames(expr_dense)%in%incompatible_gene_ids,,drop=FALSE]
pseudo<-matrix(NA_real_,nrow=nrow(expr_dense),ncol=length(complete_donors)*length(celltypes),dimnames=list(rownames(expr_dense),rep('',length(complete_donors)*length(celltypes))))
profile_rows<-list();k<-0L
for(donor in complete_donors) for(ct in celltypes){
  ix<-which(as.character(c$meta$donor)==donor&as.character(c$meta$cell_type)==ct)
  k<-k+1L;pseudo[,k]<-if(length(ix)==1) expr_dense[,ix] else rowMeans(expr_dense[,ix,drop=FALSE])
  colnames(pseudo)[k]<-paste0(donor,'_',ct)
  profile_rows[[k]]<-data.frame(donor=donor,cell_type=ct,input_profiles=length(ix),profile_column=colnames(pseudo)[k],stringsAsFactors=FALSE)
}
profile_rows<-do.call(rbind,profile_rows)
variable<-apply(pseudo,1,function(x)all(is.finite(x))&&all(x>=0)&&var(x)>0)
pseudo<-pseudo[variable,,drop=FALSE]
if(nrow(pseudo)<100) stop('供体×细胞类型聚合后只有',nrow(pseudo),'个有限且有变化的基因')

filter_low<-isTRUE(cfg$filter_low_expression%||%TRUE)
expression_bins<-as.integer(cfg$expression_bins%||%4L)
seed<-as.integer(cfg$seed%||%30L)
lambda<-cfg$lambda%||%NULL
if(!is.null(lambda)) lambda<-as.numeric(lambda)
if(is.na(expression_bins)||expression_bins<2||expression_bins>10||is.na(seed)||(!is.null(lambda)&&(!is.finite(lambda)||lambda<=0))) stop('REMI参数无效')
params<-list(commit=commit,version='0.0.0.9000',condition=conditions[[1]],input_level=input_level,cell_types=celltypes,
  independent_units=complete_donors,min_independent_units=minimum_units,min_cells_per_profile=minimum_cells,
  filter_low_expression=filter_low,expression_bins=expression_bins,seed=seed,lambda=lambda,community_detection='Louvain',resource_version=cfg$resource_version)
c$start_cache(c(unname(expected),vapply(c('qgraph','dplyr','data.table','igraph','glasso','OneR','magrittr'),function(p)as.character(packageVersion(p)),character(1))),params)
obj<-c$native(1,paste0(conditions[[1]],':',length(complete_donors),' donors'),function(){
  prepared<-setupData(pseudo,celltypes,filter=filter_low,var=expression_bins)
  result<-remi(prepared,seed=seed,lambda=lambda,cd='Louvain')
  list(result=result,prepared=prepared,pseudobulk=pseudo,profiles=profile_rows)
})

result<-obj$result
if(is.null(result)){
  interactome<-data.frame(ligand=character(),receptor=character(),sending=character(),receiving=character(),weight=numeric(),cor=numeric(),commnum=character(),lambda=numeric())
  unfiltered<-interactome;membership<-integer()
} else {
  interactome<-as.data.frame(result$interactome);unfiltered<-as.data.frame(result$unfilteredinteractome);membership<-result$communities$membership
}
for(n in intersect(c('weight','cor','commsize','deg','numgenes','lambda'),names(interactome))) interactome[[n]]<-as.numeric(interactome[[n]])
for(n in intersect(c('weight','cor','commsize','deg','numgenes','lambda'),names(unfiltered))) unfiltered[[n]]<-as.numeric(unfiltered[[n]])
c$wt(unfiltered,'remi_unfiltered_interactome.tsv');c$wt(profile_rows,'remi_profiles.tsv')

lr_rows<-if(nrow(interactome)) lapply(seq_len(nrow(interactome)),function(i){
  r<-interactome[i,];w<-as.numeric(r$weight)
  list(sample=cfg$dataset,condition=conditions[[1]],source=as.character(r$sending),target=as.character(r$receiving),ligand=as.character(r$ligand),receptor=as.character(r$receptor),
    interaction=paste0(r$ligand,'→',r$receptor,' | community ',r$commnum),score=w,tested=TRUE,supported=is.finite(w)&&abs(w)>0,
    raw_correlation=as.numeric(r$cor),community=as.character(r$commnum),lambda=as.numeric(r$lambda))
}) else list()

network_rows<-list();role_strength_rows<-list();role_count_rows<-list()
if(nrow(interactome)){
  interactome$abs_weight<-abs(interactome$weight)
  pairs<-split(seq_len(nrow(interactome)),interaction(interactome$sending,interactome$receiving,drop=TRUE,lex.order=TRUE))
  network_rows<-lapply(pairs,function(ix) list(source=as.character(interactome$sending[ix[1]]),target=as.character(interactome$receiving[ix[1]]),
    value=sum(interactome$abs_weight[ix]),edge_count=length(ix),positive_edges=sum(interactome$weight[ix]>0),negative_edges=sum(interactome$weight[ix]<0)))
  for(ct in celltypes){
    outgoing<-interactome[interactome$sending==ct,,drop=FALSE];incoming<-interactome[interactome$receiving==ct,,drop=FALSE]
    role_strength_rows[[length(role_strength_rows)+1]]<-list(row=ct,column='Outgoing',value=sum(abs(outgoing$weight)))
    role_strength_rows[[length(role_strength_rows)+1]]<-list(row=ct,column='Incoming',value=sum(abs(incoming$weight)))
    role_count_rows[[length(role_count_rows)+1]]<-list(row=ct,column='Outgoing',value=nrow(outgoing))
    role_count_rows[[length(role_count_rows)+1]]<-list(row=ct,column='Incoming',value=nrow(incoming))
  }
}
membership_rows<-if(length(membership)) data.frame(node=names(membership),cell_type=sub('_.*$','',names(membership)),community=as.integer(membership),stringsAsFactors=FALSE) else data.frame(node=character(),cell_type=character(),community=integer())
c$wt(membership_rows,'remi_community_membership.tsv')
community_rows<-if(nrow(membership_rows)) lapply(split(seq_len(nrow(membership_rows)),paste(membership_rows$cell_type,membership_rows$community,sep='|')),function(ix) list(row=membership_rows$cell_type[ix[1]],column=paste0('Community ',membership_rows$community[ix[1]]),value=length(ix))) else list()
diagnostic_rows<-list(
  list(row='Input',column='Independent donors retained',value=length(complete_donors)),
  list(row='Input',column='Cell types retained',value=length(celltypes)),
  list(row='Input',column='Genes entering setupData',value=nrow(pseudo)),
  list(row='Input',column='Incompatible gene IDs removed',value=length(incompatible_gene_ids)),
  list(row='Model',column='Expanded LR candidates',value=if(is.null(result))0 else nrow(result$lrnet$mat)),
  list(row='Model',column='Detected communities',value=if(is.null(result))0 else length(result$communities$names)),
  list(row='Model',column='Nonzero REMI edges',value=nrow(interactome)),
  list(row='Model',column='Positive edges',value=if(nrow(interactome))sum(interactome$weight>0) else 0),
  list(row='Model',column='Negative edges',value=if(nrow(interactome))sum(interactome$weight<0) else 0))
lr_rows<-if(length(lr_rows)) dplyr::bind_rows(lr_rows) else data.frame(sample=character(),condition=character(),source=character(),target=character(),ligand=character(),receptor=character(),interaction=character(),score=numeric(),tested=logical(),supported=logical(),raw_correlation=numeric(),community=character(),lambda=numeric())
network_rows<-if(length(network_rows)) dplyr::bind_rows(network_rows) else data.frame(source=character(),target=character(),value=numeric(),edge_count=integer(),positive_edges=integer(),negative_edges=integer())
role_strength_rows<-if(length(role_strength_rows)) dplyr::bind_rows(role_strength_rows) else data.frame(row=character(),column=character(),value=numeric())
role_count_rows<-if(length(role_count_rows)) dplyr::bind_rows(role_count_rows) else data.frame(row=character(),column=character(),value=numeric())
community_rows<-if(length(community_rows)) dplyr::bind_rows(community_rows) else data.frame(row=character(),column=character(),value=numeric())
diagnostic_rows<-dplyr::bind_rows(diagnostic_rows)

c$bundle$method_version<-'fixed source 0.0.0.9000'
c$bundle$implementation<-'native_REMI_setupData_Louvain_constrained_graphical_lasso'
c$bundle$provenance$upstream<-list(url='https://github.com/plevritis-lab/REMI',commit=commit,version='0.0.0.9000',license='unresolved placeholder in fixed DESCRIPTION')
c$bundle$provenance$paper<-list(doi='10.1126/sciadv.abi4757',journal='Science Advances',year=2022)
c$bundle$provenance$source_hashes<-as.list(expected);c$bundle$provenance$parameters<-params
c$bundle$provenance$input_provenance<-cfg$input_provenance;c$bundle$provenance$resource_provenance<-cfg$resource_provenance
c$bundle$provenance$prepared_profiles<-list(path='remi_profiles.tsv',sha256=c$hash(file.path(c$out,'remi_profiles.tsv')))
c$bundle$provenance$identifier_filter<-list(rule='Remove expression row names containing underscore because fixed REMI parses celltype_gene on underscore; no identifier rewriting.',removed_count=length(incompatible_gene_ids),removed_examples=head(incompatible_gene_ids,20))
c$bundle$provenance$unfiltered_interactome<-list(path='remi_unfiltered_interactome.tsv',sha256=c$hash(file.path(c$out,'remi_unfiltered_interactome.tsv')))
c$bundle$provenance$complete_community_membership<-list(path='remi_community_membership.tsv',sha256=c$hash(file.path(c$out,'remi_community_membership.tsv')),rows=nrow(membership_rows))
c$bundle$provenance$limitations<-c(
  'REMI在同一条件的独立供体表达谱间估计LR网络；它不直接检验条件差异，也不应把单一队列网络称为疾病特异性。',
  '有符号weight来自LR先验约束的图形Lasso精度矩阵转换，表示条件相关方向；不是配体流量、结合概率或因果激活。',
  '原生主流程不为全部边提供P值或多重校正。supported仅表示固定原生清理步骤保留且abs(weight)>0。',
  '源码DESCRIPTION仍是许可模板占位，未形成有效软件许可证；Plugin只调用用户提供的固定外部源码，不复制REMI代码或数据。',
  '源码文档把expression_bins同时描述为标准差数与分箱数；实际固定实现调用OneR::bin，入口按实际分箱行为记录。')
c$add('remi_interactome','lr_edges',lr_rows,'固定REMI的Louvain社区与LR先验约束图形Lasso保留边；score为有符号部分相关权重，supported仅为非零原生保留边，不是统计显著性。',
  value_kind='native_score',additive=FALSE,direction='two_sided',axis_label='Signed REMI partial association',statistical_unit='independent donor expression profiles within one condition',test_definition='No global inferential test',display_top_lr=24,display_top_cell_pairs=min(8,nrow(network_rows)))
c$add('remi_network','network',network_rows,'细胞类型对所有原生非零边绝对权重之和；绝对值可加只用于网络宽度，同时在源表保留正负边数量。',
  figure_role='remi_network',value_kind='nonnegative_strength',additive=TRUE,directed=TRUE,title='REMI cell-type interactome')
c$add('remi_role_strength','matrix',role_strength_rows,'按细胞类型汇总的发送/接收绝对REMI权重；正负方向仍在完整LR表中保留。',
  figure_role='remi_roles',value_kind='nonnegative_strength',additive=FALSE,axis_label='Sum of absolute REMI weights',row_order=celltypes,column_order=c('Outgoing','Incoming'))
c$add('remi_role_counts','matrix',role_count_rows,'按细胞类型汇总的发送/接收原生非零边数。',
  figure_role='remi_roles',value_kind='count',additive=FALSE,axis_label='Nonzero REMI edges',row_order=celltypes,column_order=c('Outgoing','Incoming'))
c$add('remi_communities','matrix',community_rows,'固定Louvain社区内各细胞类型前缀LR基因节点数；完整逐节点社区归属另存，主图按节点总数展示前24个社区。',
  figure_role='remi_communities',value_kind='count',additive=FALSE,axis_label='LR gene nodes',row_order=celltypes,display_top_columns=24)
c$add('remi_diagnostics','matrix',diagnostic_rows,'输入独立单位、候选扩张、社区与正负非零边数量的透明诊断。',
  figure_role='remi_diagnostics',value_kind='count',additive=FALSE,axis_label='Count')
c$bundle$figure_inapplicability<-list(
  condition_effects='REMI主流程一次拟合一个条件，不提供供体层差异检验；条件特异性需分别拟合后另做独立供体比较。',
  cellchat_patterns='REMI社区不是CellChat NMF发送/接收模式。',pathway_sankey='固定REMI LR资源没有单一可核验通路标签。',
  ligand_response='REMI不预测配体靶基因响应。',intracellular='REMI固定主流程没有LR–TF–target路径输出。',
  enrichment='REMI主流程没有定义检验背景的通路富集。',embedding='REMI不输出细胞或分子连续嵌入。',
  spatial_location='REMI不使用组织坐标。',spatial_hotspots='REMI不计算局部空间热点。',spatial_direction='REMI不计算空间方向。',
  neighborhood_response='REMI不拟合组织邻域响应。',relay_dynamic='REMI是静态相关网络，没有时间或多跳动态。',
  special_molecules='固定作者资源只有基因编码配体与受体。',functional_clinical='REMI主流程不计算功能、临床或药敏关联。')
c$wj(c$bundle,'bundle.json')
c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',source_commit=commit,condition=conditions[[1]],independent_donors=length(complete_donors),nonzero_edges=nrow(interactome)),'run_metadata.json')
quit(status=0)
