#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
a<-commandArgs(TRUE)
f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
source(file.path(dirname(normalizePath(f)), 'native_expression_context.R'))
if(length(a)!=2) stop('需要配置JSON与新的Git外输出目录')
cfg0<-jsonlite::read_json(a[1]);c<-native_expression_context(a,'scTensor','scTensor','2.18.2',counts_input=identical(cfg0$expression_scale,'counts'))
for(p in c('LRBaseDbi','SingleCellExperiment','S4Vectors','nnTensor','clue')) if(!requireNamespace(p,quietly=TRUE)) stop('缺少原生依赖：',p)
if(any(!grepl('^[0-9]+$',rownames(c$expr)))) stop('scTensor要求唯一NCBI Gene/Entrez ID；先做有版本、保留歧义记录的物种身份转换')
for(k in c('database','database_provenance','gene_id_provenance')) if(is.null(c$cfg[[k]])) stop('缺少：',k)
dbpath<-c$resolve(c$cfg$database);db<-LRBaseDbi::LRBaseDb(dbpath)
if(!identical(as.character(LRBaseDbi::lrNomenclature(db)),'Homo sapiens')) stop('LRBase物种与输入不一致')
evidence<-c$cfg$lr_evidence %||% 'known';if(!length(evidence)||anyNA(evidence)) stop('需要明确LRBase证据范围')
seeds<-as.integer(c$cfg$seeds %||% c(42,43,44));if(length(seeds)<2||anyNA(seeds)||anyDuplicated(seeds)) stop('至少两个不同随机种子，用于保留分解不稳定性')
ranks<-c$cfg$ranks;rank_runs<-as.integer(c$cfg$rank_runs %||% 5L)
if(!is.null(ranks)&&(length(ranks)!=2||any(!is.finite(ranks))||any(ranks!=as.integer(ranks))||any(ranks<1))) stop('NTD2 ranks须两个正整数')
if(is.na(rank_runs)||rank_runs<2) stop('秩诊断至少重复2次')
params<-list(seeds=seeds,ranks=ranks,rank_runs=rank_runs,lr_evidence=evidence,min_cells=c$minimum,algorithm='ntd2',centering=TRUE,mergeas='mean',outerfunc='*',native_iterations=30,nnTensor=as.character(packageVersion('nnTensor')),rTensor=as.character(packageVersion('rTensor')))
c$start_cache(c$hash(dbpath),params)
c$bundle$provenance$molecule_identity_schema<-'ncbi-gene-id-pair-v1'
c$bundle$provenance$upstream<-list(url='https://github.com/rikenbit/scTensor',commit='4cd7e4c92575387edfaa942f4a01bb641aa82d9c',license='Artistic-2.0')
c$bundle$provenance$semantics<-'原生NTD2：当前输入尺度的细胞类型均值外积，不额外归一化或填补基因；不处理多亚基复合物，不生成LR/条件显著性。自动秩选择按当前源码为展开张量NMF的RSS下降80%，并非文档所称PCA；因子可以非唯一。'
matrows<-function(m){d<-expand.grid(row=rownames(m),column=colnames(m));d$value<-as.vector(m);d}
patrows<-function(m,dimension){d<-expand.grid(factor=rownames(m),entity=colnames(m));d$value<-as.vector(m);d$dimension<-dimension;d}
cosine_match<-function(a,b){
 den<-outer(sqrt(rowSums(a*a)),sqrt(rowSums(b*b)));z<-a%*%t(b);z<-ifelse(den>0,z/den,0)
 perm<-as.integer(clue::solve_LSAP(z,maximum=TRUE));data.frame(reference=rownames(a),matched=rownames(b)[perm],cosine=z[cbind(seq_len(nrow(z)),perm)])
}
for(i in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[i];meta<-c$sample_meta(sample);expr<-c$expr[,rownames(meta),drop=FALSE]
 if(prod(dim(expr))*8>(c$cfg$max_dense_bytes %||% 2^31)) stop('原生scTensor转稠密超过内存契约，先按有依据的资源基因做可追溯筛选')
 ct<-unique(meta$cell_type);if(length(ct)>=100) stop('原生NTD2限制细胞类型少于100')
 if(!is.null(ranks)&&any(ranks>length(ct))) stop('秩不能超过当前合格细胞类型数')
 obj<-c$native(i,sample,function(){
  # The upstream S4 API writes the named object into .GlobalEnv.
  assign('sce',SingleCellExperiment::SingleCellExperiment(assays=list(expression=as.matrix(expr))),envir=.GlobalEnv)
  scTensor::cellCellSetting(sce,db,meta$cell_type,lr.evidence=evidence)
  lr<-scTensor:::.extractLR(sce,evidence,c('GENEID_L','GENEID_R'));c$wt(lr,paste0('resource_candidates_',i,'.tsv'))
  measured<-lr[lr$GENEID_L %in% rownames(expr)&lr$GENEID_R %in% rownames(expr),,drop=FALSE]
  if(nrow(measured)<2) stop('至少两个实测配体–受体基因对才能分解；缺失基因不补零')
  if(length(ct)^2*nrow(measured)>(c$cfg$max_tensor_elements %||% 20000000)) stop('张量超过内存契约')
  set.seed(seeds[1]);diagnostic<-NULL;selected<-ranks
  if(is.null(selected)){
   diagnostic<-scTensor::cellCellRanks(sce,assayNames='expression',num.iter1=rank_runs,num.iter2=rank_runs)
   selected<-diagnostic$selected
   if(length(selected)!=2||any(!is.finite(selected))||any(selected<1)) stop('原生秩选择失败，不静默替换秩')
  }
  celltypes<-S4Vectors::metadata(sce)$color;names(celltypes)<-meta$cell_type
  tensor<-scTensor:::.celltypemergedtensor(as.matrix(expr),lr,celltypes,'mean','*')$tnsr
  results<-list()
  for(seed in seeds){set.seed(seed);scTensor::cellCellDecomp(sce,algorithm='ntd2',ranks=selected,assayNames='expression',centering=TRUE,mergeas='mean',outerfunc='*');results[[as.character(seed)]]<-S4Vectors::metadata(sce)$sctensor}
  list(results=results,tensor=tensor,resource=lr,measured=measured,rank_diagnostic=diagnostic,ranks=selected,metadata=meta)
 })
 c$wt(obj$resource,paste0('resource_candidates_',i,'.tsv'))
 c$wt(obj$measured,paste0('measured_lr_',i,'.tsv'))
 diagnostics<-list();stability<-list();convergence<-list();reference<-obj$results[[1]]
 for(j in seq_along(obj$results)){
  fit<-obj$results[[j]];core<-fit$lrpair@data;recon<-array(0,dim(obj$tensor))
  for(k in seq_len(dim(core)[3])) recon[,,k]<-t(fit$ligand)%*%matrix(core[,,k],nrow=dim(core)[1],ncol=dim(core)[2])%*%fit$receptor
  err<-sqrt(sum((obj$tensor-recon)^2)/sum(obj$tensor^2))
  if(!is.finite(err)||any(!is.finite(unlist(fit[c('ligand','receptor')])))) stop('原生因子或重构误差无效')
  diagnostics[[j]]<-data.frame(row=names(obj$results)[j],column='Relative Frobenius reconstruction error',value=err)
  for(dim in c('ligand','receptor')){
   matched<-cosine_match(reference[[dim]],fit[[dim]]);matched$seed<-names(obj$results)[j];matched$dimension<-dim;stability[[length(stability)+1]]<-matched
  }
  # Preserve every native repetition; the first prespecified seed is displayed.
  convergence[[j]]<-data.frame(row=seq_along(fit$recerror)-1L,column=paste0('Seed ',names(obj$results)[j]),value=as.vector(fit$recerror))
  c$wt(data.frame(iteration=seq_along(fit$recerror),native_error=as.vector(fit$recerror)),paste0('convergence_',i,'_',j,'.tsv'))
 }
 c$add(paste0('convergence_',i),'matrix',do.call(rbind,convergence),'原生NTD2初始状态及每次迭代的重构目标，分别保留每个预设种子；不平滑、不据最终目标筛选种子',axis_label='Native reconstruction objective',figure_role='convergence',title=paste(sample,'optimization'))
 c$wt(do.call(rbind,stability),paste0('factor_alignment_',i,'.tsv'))
 c$add(paste0('reconstruction_',i),'matrix',do.call(rbind,diagnostics),'每个预先指定种子的原生分解相对Frobenius误差，全部保留，不按生物学结果挑选种子',axis_label='Relative reconstruction error',title=sample)
 st<-do.call(rbind,stability);c$add(paste0('stability_',i),'matrix',data.frame(row=paste(st$dimension,st$reference),column=st$seed,value=st$cosine),'分别在配体/受体维度用余弦相似度和一一匹配比较种子；零范数因子记0表示不可支持稳定性，不是生物学阴性',axis_label='Aligned factor cosine',title=sample)
 factorrows<-rbind(patrows(reference$ligand,'sender'),patrows(reference$receptor,'receiver'))
 c$add(paste0('factors_',i),'patterns',factorrows,'首个预先指定随机种子的原生NTD2载荷；发送/接收模式独立编号，其联系由核心张量给出，不能把相同编号视为对应模式',axis_label='Native NTD2 loading',title=sample)
 core<-reference$lrpair@data;coretotal<-apply(core,c(1,2),sum)
 c$add(paste0('core_total_',i),'matrix',matrows(coretotal),'核心张量沿实测LR维求和，表示发送模式×接收模式的分解权重；不是LR数量或P值',axis_label='Core weight summed across LR',title=sample)
 lrrows<-list()
 for(l in seq_len(dim(core)[1])) for(r in seq_len(dim(core)[2])) lrrows[[length(lrrows)+1]]<-data.frame(factor=paste0('Sender',l,'_Receiver',r),dimension='ligand_receptor',entity=dimnames(core)[[3]],value=core[l,r,])
 c$add(paste0('core_lr_',i),'patterns',do.call(rbind,lrrows),'原生核心张量每个发送模式×接收模式中的LR载荷，保留NCBI Gene ID对；不重命名为通路活性',axis_label='Core LR weight',title=sample)
 if(!is.null(obj$rank_diagnostic)){
  rows<-lapply(seq_along(obj$rank_diagnostic$RSS),function(k)data.frame(row=paste0('Mode',k),column=seq_along(obj$rank_diagnostic$RSS[[k]]),value=obj$rank_diagnostic$RSS[[k]]))
  c$add(paste0('rank_diagnostic_',i),'matrix',do.call(rbind,rows),'当前原生源码中多次NMF的平均RSS；选择达到可实现RSS降幅80%的最小秩，需结合随机种子稳定性解释',axis_label='Native mean NMF RSS',title=sample)
 }
 c$wt(data.frame(sample=sample,sender_rank=obj$ranks[1],receiver_rank=obj$ranks[2],measured_lr=nrow(obj$measured),retained_cell_types=length(ct),input_cells=nrow(meta)),paste0('sample_scope_',i,'.tsv'))
}
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
