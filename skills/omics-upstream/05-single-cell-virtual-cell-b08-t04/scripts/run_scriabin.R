#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
args<-commandArgs(TRUE)
file_arg<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
script_dir<-dirname(normalizePath(file_arg));source(file.path(script_dir,'native_expression_context.R'))
if(length(args)!=2) stop('需要配置JSON与新的仓库外输出目录')
raw_cfg<-jsonlite::read_json(normalizePath(args[1]),simplifyVector=TRUE);mode<-raw_cfg$mode%||%'ccim_graph'
if(!mode%in%c('ccim_graph','programs')) stop('mode必须为ccim_graph或programs；两个模块需要不同Seurat主版本，须分别执行')
seurat_version<-if(mode=='ccim_graph')'4.4.0'else'5.5.1'
c<-native_expression_context(args,'scriabin','Seurat',seurat_version,counts_input=FALSE,species=c('human','mouse','rat'));cfg<-c$cfg
for(key in c('native_root','scriabin_library','input_provenance','resource_provenance','resource_version','parameter_provenance')) if(is.null(cfg[[key]])) stop('缺少：',key)
scriabin_lib<-c$resolve(cfg$scriabin_library);.libPaths(c(scriabin_lib,.libPaths()))
for(pkg in c('scriabin','dplyr','pbapply','tibble','stringr','reshape2','digest')) if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
if(as.character(packageVersion('scriabin'))!='0.0.0.9000') stop('需要固定scriabin 0.0.0.9000')
if(mode=='programs') for(pkg in c('tidyr','purrr','WGCNA','qlcMatrix','flashClust','dynamicTreeCut')) if(!requireNamespace(pkg,quietly=TRUE)) stop('交互程序分支缺少原生依赖：',pkg)
suppressPackageStartupMessages({library(Seurat);library(scriabin);library(Matrix);library(dplyr)})
if(mode=='programs') suppressPackageStartupMessages({library(tidyr);library(purrr)}) # 固定源码漏掉未限定的nest/map2/unnest导入。

root<-c$resolve(cfg$native_root)
expected<-c('DESCRIPTION'='8b6dd651df24d667e82ff005030942ea93adbc71ec3d3641600b45a28306c3a5','LICENSE'='c79d3586beb739a852f4199e6ce868aa8d5fc85e076485bdd23ae7c089220fe6','R/interaction_graph.R'='ad99fa5c8c59e42c89aa737a0c4ec96afc47f1bf115336ad4b03f45ca5cd5dac','R/interaction_programs.R'='127488d66ab3401e5e6b7f357878a85d4a4c6a6a30dfca995425b9e5ba5c1607','R/utils.R'='c93dbf493ed9e77f1cee6d47b674ccd65f453d7989ac4c16ef7860b87fc0414e','inst/lr_resources.rds'='fc92d0b5d793cd821013fbd18f4ae37e0085802a0b57a53972446c90685422ba')
for(path in names(expected)) if(c$hash(file.path(root,path))!=expected[[path]]) stop('scriabin源码或资源摘要不符：',path)
body_expected<-c(LoadLR='7e844f13fa97e4ad959cf8a0fa72bfa3a874145017907c8224382de19ff2618d',GenerateCCIM='10e33af0729e47147f7e1643a7b1d7450e0a68bd7ad4a371052b095e6ca60795',BuildPriorInteraction='cddfaeed15517b91d435ad955d0431a48748cd902a874a3ca2be3d33468acb07',InteractionPrograms='a6b1a0d7f185370b2fedf7325e3839ef0733e77a94fe26178775a1d80e83959c',InteractionProgramSignificance='ae454b048e213d4891ab20a8ed2ad39aed1d13dfeef474542a62cc55308e3ba2',ScoreInteractionPrograms='3a1d2d00058fffee5dc7a54659f21661f8d29ced9a625ac10cd89d3d0468ff9e',IPCellTypeSummary='bcb940324b39234fd152596888cb06fbc1dffcae88c9ef6de602599fb69fe64e')
for(fn in names(body_expected)) if(digest::digest(body(getExportedValue('scriabin',fn)),algo='sha256')!=body_expected[[fn]]) stop('已安装scriabin函数体摘要不符：',fn)

x<-readRDS(c$input);counts<-x$counts
if(is.null(counts)||is.null(rownames(counts))||is.null(colnames(counts))||!setequal(colnames(counts),colnames(c$expr))||!all(rownames(c$expr)%in%rownames(counts))) stop('scriabin需要与expression细胞一致且覆盖其基因的原始counts以构建Seurat对象和深度诊断')
counts<-counts[,colnames(c$expr),drop=FALSE];cv<-if(inherits(counts,'sparseMatrix'))counts@x else as.vector(counts)
if(any(!is.finite(cv))||any(cv<0)) stop('Seurat RNA测量层必须有限非负')
continuous_depth_layer<-any(cv!=round(cv))
if(continuous_depth_layer&&(!isTRUE(cfg$allow_continuous_depth_layer)||is.null(cfg$depth_layer_definition))) stop('RNA测量层含非整数；只有明确allow_continuous_depth_layer并说明depth_layer_definition时才可复现作者对象，不能称为原始UMI counts')
if(any(grepl('=',c(rownames(c$expr),colnames(c$expr)),fixed=TRUE))) stop('scriabin用等号拼接LR和细胞对身份；基因或细胞名不能含等号')
database<-cfg$database%||%'OmniPath';lit_support<-as.numeric(cfg$lit_support%||%7)
if(cfg$species!='human'&&database!='OmniPath') stop('固定scriabin资源仅为人支持多数据库；鼠/大鼠只能使用OmniPath')
if(!is.finite(lit_support)||lit_support!=7) stop('scriabin高层原生函数未暴露lit_support参数；当前只接受作者默认7，避免资源预筛与实际运行不一致')
lr<-scriabin::LoadLR(species=cfg$species,database=database,lit_support=lit_support)
if(!nrow(lr)||anyDuplicated(paste(lr$source_genesymbol,lr$target_genesymbol,sep='='))) stop('筛后LR为空或存在重复身份；不能让Seurat自动改名后失去资源对应')

params<-list(commit='bce695bd598e2e2d37e51d983dca2a29d5ef61c7',mode=mode,seurat=seurat_version,database=database,lit_support=lit_support,resource_version=cfg$resource_version)
if(mode=='ccim_graph'){
  params$sender_types<-sort(as.character(cfg$sender_types%||%unique(c$meta$cell_type)))
  params$receiver_types<-sort(as.character(cfg$receiver_types%||%unique(c$meta$cell_type)))
  params$max_ccim_cell_pairs<-as.numeric(cfg$max_ccim_cell_pairs%||%1e6)
}else{
  params$iterate_threshold<-as.integer(cfg$iterate_threshold%||%300L);params$n_iterate<-as.integer(cfg$n_iterate%||%round(sqrt(ncol(c$expr)/params$iterate_threshold)))
  params$soft_power<-if(is.null(cfg$soft_power))NULL else as.numeric(cfg$soft_power);params$r2_cutoff<-as.numeric(cfg$r2_cutoff%||%0.6);params$min_program_size<-as.integer(cfg$min_program_size%||%5L)
  params$tree_cut_quantile<-as.numeric(cfg$tree_cut_quantile%||%0.4);params$min_cells_per_type_iteration<-as.integer(cfg$min_cells_per_type_iteration%||%3L);params$n_significance_replicates<-as.integer(cfg$n_significance_replicates%||%10000L);params$min_unique_members<-as.integer(cfg$min_unique_members%||%1L);params$seed<-as.integer(cfg$seed%||%1111L)
  if(params$iterate_threshold<50||params$n_iterate<1||params$min_program_size<2||params$n_significance_replicates<100||params$min_cells_per_type_iteration<1) stop('交互程序参数超出已核验范围')
}
c$start_cache(unname(expected),params)
c$bundle$method_version<-'scriabin 0.0.0.9000'
c$bundle$implementation<-paste0('native_scriabin_',mode)
c$bundle$provenance$upstream<-list(url='https://github.com/BlishLab/scriabin',commit=params$commit,version='0.0.0.9000',license='MIT')
c$bundle$provenance$resource_hash<-c$hash(file.path(root,'inst/lr_resources.rds'))
c$bundle$provenance$resource_selection<-list(database=database,lit_support=lit_support,retained_pairs=nrow(lr))
c$bundle$provenance$depth_layer<-list(continuous=continuous_depth_layer,definition=cfg$depth_layer_definition%||%'nonnegative integer counts')

make_object<-function(ids){
  object<-CreateSeuratObject(counts=counts[,ids,drop=FALSE],meta.data=c$meta[ids,,drop=FALSE],assay='RNA')
  if(mode=='ccim_graph') object[['INPUT']]<-CreateAssayObject(data=c$expr[,ids,drop=FALSE]) else object[['INPUT']]<-CreateAssay5Object(data=c$expr[,ids,drop=FALSE])
  DefaultAssay(object)<-'INPUT';object
}

if(mode=='ccim_graph'){
  all_lr<-list();all_raw<-list();all_raw_mean<-list();all_corrected<-list();diagnostics<-list()
  for(si in seq_along(unique(c$meta$sample))){
    sample<-unique(c$meta$sample)[[si]];ids<-rownames(c$meta)[c$meta$sample==sample];meta<-c$meta[ids,,drop=FALSE]
    senders<-ids[meta$cell_type%in%params$sender_types];receivers<-ids[meta$cell_type%in%params$receiver_types]
    if(!length(senders)||!length(receivers)) stop('样本',sample,'没有配置要求的发送或接收细胞')
    if(length(senders)*length(receivers)>params$max_ccim_cell_pairs) stop('样本',sample,'的发送×接收细胞对超过max_ccim_cell_pairs；不静默抽样')
    native<-c$native(si,sample,function(){
      object<-make_object(ids)
      ccim<-scriabin::GenerateCCIM(object,assay='INPUT',slot='data',species=cfg$species,database=database,senders=senders,receivers=receivers,weighted=FALSE)
      object<-scriabin::BuildPriorInteraction(object,assay='INPUT',slot='data',species=cfg$species,database=database,specific=FALSE,correct.depth=FALSE,graph_name='prior_raw')
      object<-scriabin::BuildPriorInteraction(object,assay='INPUT',slot='data',species=cfg$species,database=database,specific=FALSE,correct.depth=TRUE,graph_name='prior_depth_corrected')
      list(ccim=ccim,raw=object@graphs$prior_raw,depth_corrected=object@graphs$prior_depth_corrected)
    })
    mat<-native$ccim[['CCIM']]@counts;features<-rownames(mat);parts<-strsplit(features,'=',fixed=TRUE)
    if(any(lengths(parts)!=2)) stop('原生CCIM的LR身份无法无损拆分')
    pair_meta<-native$ccim@meta.data;groups<-unique(pair_meta[,c('sender_cell_type','receiver_cell_type')]);rows<-list()
    for(gi in seq_len(nrow(groups))){
      idx<-which(pair_meta$sender_cell_type==groups$sender_cell_type[gi]&pair_meta$receiver_cell_type==groups$receiver_cell_type[gi]);score<-Matrix::rowMeans(mat[,idx,drop=FALSE])
      rows[[gi]]<-data.frame(sample=sample,donor=unique(meta$donor),condition=unique(meta$condition),source=groups$sender_cell_type[gi],target=groups$receiver_cell_type[gi],ligand=vapply(parts,`[[`,'',1),receptor=vapply(parts,`[[`,'',2),interaction=features,score=as.numeric(score),tested=TRUE,supported=score>0)
    }
    all_lr[[sample]]<-do.call(rbind,rows)
    aggregate_graph<-function(graph){
      z<-expand.grid(source=unique(meta$cell_type),target=unique(meta$cell_type),stringsAsFactors=FALSE)
      z$value<-vapply(seq_len(nrow(z)),function(i)sum(graph[meta$cell_type==z$source[i],meta$cell_type==z$target[i]]),numeric(1))
      z$mean_value<-vapply(seq_len(nrow(z)),function(i)mean(graph[meta$cell_type==z$source[i],meta$cell_type==z$target[i]]),numeric(1));z$sample<-sample;z
    }
    raw<-aggregate_graph(native$raw);all_raw[[sample]]<-raw[,c('source','target','value','sample')]
    all_raw_mean[[sample]]<-data.frame(row=paste(sample,raw$source,sep=' | '),column=raw$target,value=raw$mean_value)
    corrected<-aggregate_graph(native$depth_corrected);all_corrected[[sample]]<-data.frame(row=paste(sample,corrected$source,sep=' | '),column=corrected$target,value=corrected$mean_value)
    diagnostics[[sample]]<-data.frame(sample=sample,cells=length(ids),senders=length(senders),receivers=length(receivers),cell_pairs=length(senders)*length(receivers),retained_lr=nrow(mat),ccim_nonzero=length(mat@x),raw_min=min(native$raw),raw_max=max(native$raw),corrected_min=min(native$depth_corrected),corrected_max=max(native$depth_corrected))
  }
  c$add('scriabin_ccim_group_lr','lr_edges',do.call(rbind,all_lr),'原生CCIM的每个细胞对LR值为sqrt(sender ligand expression × receiver receptor expression)；此表在实测发送–接收细胞对内按注释群取均值，零值仍保留',direction='higher',additive=FALSE,value_kind='geometric_mean_expression',axis_label='Mean cell-pair geometric expression',statistical_unit='cell pairs pooled within each sample',test_definition='No inferential test; supported means positive mean model input')
  c$add('scriabin_prior_group_network','network',do.call(rbind,all_raw),'原生BuildPriorInteraction对每个细胞对累加全部LR的sqrt(ligand)×sqrt(receptor)，再对互斥发送–接收注释群内的全部细胞对求总和；该网络可加但强烈受群大小影响，均值另表交付',direction='higher',additive=TRUE,value_kind='nonnegative_strength',axis_label='Total prior interaction score',directed=TRUE)
  c$add('scriabin_prior_group_mean','matrix',do.call(rbind,all_raw_mean),'未深度校正的原生细胞对汇总交互分数按发送–接收注释群取均值；用于查看群对平均，不能跨接收群相加',direction='higher',additive=FALSE,value_kind='mean_summed_geometric_expression',axis_label='Mean prior interaction score')
  c$add('scriabin_depth_corrected_group_matrix','matrix',do.call(rbind,all_corrected),'作者线性模型以两个细胞的RNA测量层列和解释汇总交互分数；表值为残差按发送–接收群的均值，可为负。只有输入确为原始整数时才能把列和称为UMI总数',direction='higher',additive=FALSE,value_kind='depth_regression_residual',axis_label='Mean depth-corrected residual')
  c$wt(do.call(rbind,diagnostics),'sample_diagnostics.tsv')
  c$bundle$provenance$semantics<-'CCIM保留单细胞对的LR几何表达；prior graph对资源中每条保留LR等权求和。两者都没有原生P值，细胞对不是独立供体。'
}else{
  all_members<-list();all_fraction<-list();all_scores<-list();all_pairs<-list();diagnostics<-list()
  for(si in seq_along(unique(c$meta$sample))){
    sample<-unique(c$meta$sample)[[si]];ids<-rownames(c$meta)[c$meta$sample==sample];meta<-c$meta[ids,,drop=FALSE]
    sizes<-table(meta$cell_type);if(any(sizes<params$min_cells_per_type_iteration)) stop('样本',sample,'含少于min_cells_per_type_iteration的细胞类型；作者比例抽样会越界，不能静默有放回抽样')
    native<-c$native(si,sample,function(){
      object<-make_object(ids)
      programs<-scriabin::InteractionPrograms(object,assay='INPUT',slot='data',species=cfg$species,database=database,iterate.threshold=params$iterate_threshold,n.iterate=params$n_iterate,specific=FALSE,return.mat=TRUE,softPower=params$soft_power,r2_cutoff=params$r2_cutoff,min.size=params$min_program_size,plot.mods=FALSE,tree.cut.quantile=params$tree_cut_quantile,threads=NULL,cell_types='cell_type',min.cell=params$min_cells_per_type_iteration,seed=params$seed)
      set.seed(params$seed);significance<-scriabin::InteractionProgramSignificance(programs,n.replicate=params$n_significance_replicates,min.members=params$min_unique_members)
      scored<-NULL;pairs<-NULL
      if(nrow(significance)){set.seed(params$seed);scored<-scriabin::ScoreInteractionPrograms(object,significance,return.assay=TRUE);pairs<-scriabin::IPCellTypeSummary(scored,'cell_type')}
      list(programs=programs,significance=significance,scored=scored,pairs=pairs)
    })
    conn<-native$programs$connectivity
    member_rows<-do.call(rbind,lapply(names(native$programs$modules),function(program){interactions<-native$programs$modules[[program]];parts<-strsplit(interactions,'=',fixed=TRUE);data.frame(sample=sample,program=program,source=vapply(parts,`[[`,'',1),target=vapply(parts,`[[`,'',2),source_type='ligand',target_type='receptor',value=conn[interactions,'kWithin'])}))
    all_members[[sample]]<-member_rows
    sig<-native$significance
    if(nrow(sig)){
      pcol<-grep('_pval$',names(sig),value=TRUE);fractions<-unique(sig[,c('name',pcol),drop=FALSE]);all_fraction[[sample]]<-data.frame(row=paste(sample,fractions$name,sep=' | '),column='fraction of random Wilcoxon tests with p > 0.05',value=fractions[[pcol]])
      lig<-as.matrix(GetAssayData(native$scored[['IPligands']],layer='data'));rec<-as.matrix(GetAssayData(native$scored[['IPreceptors']],layer='data'))
      group_scores<-do.call(rbind,lapply(unique(meta$cell_type),function(group)rbind(data.frame(row=paste(sample,'ligand',group,sep=' | '),column=rownames(lig),value=rowMeans(lig[,meta$cell_type==group,drop=FALSE])),data.frame(row=paste(sample,'receptor',group,sep=' | '),column=rownames(rec),value=rowMeans(rec[,meta$cell_type==group,drop=FALSE])))))
      all_scores[[sample]]<-group_scores;pairs<-native$pairs;all_pairs[[sample]]<-data.frame(row=paste(sample,pairs$program,pairs$sender,sep=' | '),column=pairs$receiver,value=pairs$additive.score)
    }
    diagnostics[[sample]]<-data.frame(sample=sample,cells=length(ids),lr_similarity=nrow(native$programs$cor_mat),modules=length(native$programs$modules),retained_significance_rows=nrow(sig),significance_replicates=params$n_significance_replicates)
  }
  c$add('scriabin_program_membership','molecular_links',do.call(rbind,all_members),'作者WGCNA样LR共变程序中的Ligand→Receptor成员；value为该LR在程序划分中的原生kWithin，不是通讯强度或因果边',direction='higher',additive=FALSE,value_kind='intramodular_connectivity',axis_label='Intramodular connectivity')
  if(length(all_fraction)) c$add('scriabin_program_random_test_fraction','matrix',do.call(rbind,all_fraction),'InteractionProgramSignificance重复抽取同大小随机LR集合并执行单侧Wilcoxon；值是这些Wilcoxon raw P大于0.05的比例，不是单个P值',direction='lower',additive=FALSE,value_kind='algorithm_defined_fraction',axis_label='Fraction with Wilcoxon P > 0.05')
  if(length(all_scores)) c$add('scriabin_program_group_scores','matrix',do.call(rbind,all_scores),'原生ScoreInteractionPrograms分别对程序的唯一配体和受体调用Seurat AddModuleScore，再按实测细胞群取均值',direction='higher',additive=FALSE,value_kind='module_score',axis_label='Mean AddModuleScore')
  if(length(all_pairs)) c$add('scriabin_program_pair_scores','matrix',do.call(rbind,all_pairs),'原生IPCellTypeSummary把发送群的配体程序均值与接收群的受体程序均值相加；仅保留正值，不能解释为LR通量',direction='higher',additive=FALSE,value_kind='additive_module_score',axis_label='Ligand + receptor program score')
  c$wt(do.call(rbind,diagnostics),'sample_diagnostics.tsv')
  c$bundle$provenance$semantics<-'交互程序由LR细胞对共变相似度、soft power、TOM和动态树切割形成。所谓program pval是重复Wilcoxon结果中P>0.05的比例；它不是常规定义的一次检验P值，也没有供体模型或多重校正。'
}
c$bundle$provenance$native_objects<-c$objects
c$bundle$provenance$limitations<-c('当前上游提交的CCIM/汇总图使用Seurat slot接口，只能在Seurat 4.4.0执行；交互程序使用layer接口，只能在Seurat 5.5.1执行，两个mode必须分别运行。','InteractionPrograms固定源码漏掉tidyr::nest/unnest和purrr::map2的命名空间导入；入口只显式附加这些声明依赖，不改算法。','细胞类型少于min_cells_per_type_iteration时作者比例抽样会请求超过现有细胞数；入口失败，不改成有放回抽样。','BuildPriorInteraction把RNA测量层列和命名为测序深度；输入为连续作者层时只可称测量总量，不能倒推出UMI。','深度校正残差、程序AddModuleScore和相加分数都不是概率、分子通量或供体效应。','原生方法没有在CCIM或prior graph层提供P值；程序随机检验比例也不等于供体条件检验。')
c$wj(c$bundle,'bundle.json');c$wj(list(signature=c$signature,objects=c$objects,status='completed_native',mode=mode,seurat=seurat_version),'run_metadata.json')
