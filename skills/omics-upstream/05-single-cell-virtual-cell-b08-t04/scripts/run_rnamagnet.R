#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
a<-commandArgs(TRUE);f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1])
source(file.path(dirname(normalizePath(f)),'native_expression_context.R'))
c<-native_expression_context(a,'RNA-Magnet','RNAMagnet','0.1.0',counts_input=TRUE,species='mouse')
suppressPackageStartupMessages(library(RNAMagnet))
for(p in c('Rmagic','reticulate','Seurat','SeuratObject'))if(!requireNamespace(p,quietly=TRUE))stop('缺少：',p)
if(as.character(packageVersion('Seurat'))!='4.4.0'||as.character(packageVersion('SeuratObject'))!='4.1.4'||as.character(packageVersion('Rmagic'))!='2.0.3.999')stop('此入口核验Seurat 4.4.0/Object 4.1.4、Rmagic 2.0.3.999')
suppressPackageStartupMessages(library(Seurat))
for(k in c('magic_python','pca_provenance','input_provenance'))if(is.null(c$cfg[[k]]))stop('缺少：',k)
python_path<-if(startsWith(c$cfg$magic_python,'/'))c$cfg$magic_python else file.path(dirname(c$cp),c$cfg$magic_python)
if(!file.exists(python_path))stop('MAGIC Python不存在')
# Resolving the final executable symlink would bypass a virtual environment.
python_path<-file.path(normalizePath(dirname(python_path)),basename(python_path))
reticulate::use_python(python_path,required=TRUE)
py<-reticulate::import('importlib.metadata');versions<-setNames(lapply(c('magic-impute','numpy','pandas','scipy','graphtools','scprep'),function(p)py$version(p)),c('magic-impute','numpy','pandas','scipy','graphtools','scprep'))
if(versions[['magic-impute']]!='3.0.0')stop('需要magic-impute 3.0.0')
x<-readRDS(c$input);pca<-as.matrix(x$pca)
if(is.null(rownames(pca))||anyDuplicated(rownames(pca))||!setequal(rownames(pca),colnames(c$expr))||ncol(pca)<15||any(!is.finite(pca)))stop('需要与计数细胞精确对应的至少15维真实PCA及来源，不能用随机坐标或UMAP代替')
pca<-pca[colnames(c$expr),1:15,drop=FALSE]
if(any(apply(pca,1,sd)==0))stop('原生PCA相关距离不能接受单细胞15维全相等')
embedding<-NULL
if(!is.null(c$cfg$embedding_file)){
 if(is.null(c$cfg$embedding_method)||is.null(c$cfg$embedding_provenance))stop('缺少实际降维方法或来源')
 embedding<-as.matrix(readRDS(c$resolve(c$cfg$embedding_file)))
 if(ncol(embedding)!=2||any(!is.finite(embedding))||is.null(rownames(embedding))||anyDuplicated(rownames(embedding))||!setequal(rownames(embedding),colnames(c$expr)))stop('降维文件须为完整细胞×2实际坐标，不能补造缺失坐标')
}
branches<-c$cfg$branches %||% c('signaling','anchors');if(!length(branches)||anyDuplicated(branches)||any(!branches %in% c('signaling','anchors')))stop('branches只允许signaling/anchors且不能重复')
anchors<-c$cfg$anchors
if('anchors'%in%branches&&(is.null(anchors)||length(anchors)<2||anyDuplicated(anchors)))stop('黏附分支需要至少两个有生物学依据的锚定细胞类型；不根据结果挑锚点')
version<-c$cfg$database_version %||% '1.0.0';if(!version %in% c('1.0.0','2.0.0','2.1.0','2.2.0','3.0.0'))stop('数据库版本须显式固定，不接受latest/stable')
threshold<-as.numeric(c$cfg$lr_display_threshold %||% .05);if(!is.finite(threshold)||threshold<0||threshold>=1)stop('LR展示阈值在[0,1)；没有统计显著性')
maxcells<-as.integer(c$cfg$max_cells %||% 5000L);if(is.na(maxcells)||maxcells<20)stop('需要有限的原生稠密细胞距离上限')
params<-list(branches=branches,anchors=anchors,database_version=version,minimum=c$minimum,lr_display_threshold=threshold,seed=48879L,k=10,x0=.5,neighborhood_distance=.7,neighborhood_gradient=3,magic_knn=5,magic_decay=1,magic_t='auto',magic_npca=100,magic_solver='exact',python=versions)
resource<-RNAMagnet::getLigandsReceptors(version,manualAnnotation='Correct');if(!nrow(resource)||anyNA(resource[,c('Ligand.Mouse','Receptor.Mouse')]))stop('原生数据库无效')
if(any(grepl('&',resource$Ligand.Mouse)&grepl('|',resource$Ligand.Mouse,fixed=TRUE))||any(grepl('&',resource$Receptor.Mouse)&grepl('|',resource$Receptor.Mouse,fixed=TRUE)))stop('原生混合AND/OR字符串需要独立解析核验，不能作单一复合物')
c$start_cache(digest::digest(list(resource=resource,source=lapply(c('RNAMagnetBase','resolveData','getRNAMagnetGenes'),function(n)body(get(n,asNamespace('RNAMagnet'))))),algo='sha256'),params)
c$bundle$provenance$molecule_identity_schema<-'mgi-native-and-or-v1';c$bundle$provenance$versions<-versions
c$bundle$provenance$upstream<-list(url='https://github.com/veltenlab/rnamagnet',commit='e4c220d6e5e356d230dc4d0aa6511dfe42d64db3',license='GPL-3.0',Rmagic_commit='3a4ffdbe435716bb3b2fbe78f434c6cdc8dd8d78')
c$bundle$provenance$semantics<-'原生MAGIC插补、复合物AND取最小/OR取最大、逐基因min-max、模糊核与逐细胞相互作用/特异性。黏附为表达及PCA相似邻域预测，不是已测组织接触。无P值、供体比较或实验因果结论。'
c$wt(resource,'resource.tsv');scope<-list();idx<-0L
matrows<-function(m){z<-expand.grid(row=rownames(m),column=colnames(m));z$value<-as.vector(m);z}
identity<-function(g){if(grepl('|',g,fixed=TRUE))paste0('mgi-alternative:',paste(sort(strsplit(g,'|',fixed=TRUE)[[1]]),collapse='|')) else if(grepl('&',g,fixed=TRUE))paste0('mgi-complex:',paste(sort(strsplit(g,'&',fixed=TRUE)[[1]]),collapse='&')) else paste0('mgi-gene:',g)}
for(sample in unique(c$meta$sample)){
 m0<-c$meta[c$meta$sample==sample,,drop=FALSE];sizes<-table(m0$cell_type);keep<-names(sizes[sizes>=c$minimum]);m<-m0[m0$cell_type %in% keep,,drop=FALSE]
 eligible<-length(keep)>=2&&nrow(m)>=20&&(!'anchors'%in%branches||all(anchors%in%keep));scope[[length(scope)+1]]<-data.frame(sample=sample,retained_cells=nrow(m),excluded_cells=nrow(m0)-nrow(m),eligible=eligible,reason=if(eligible)'' else 'Insufficient eligible populations/cells or requested anchor missing')
 c$wt(do.call(rbind,scope),'sample_eligibility.tsv');if(!eligible)next
 if(nrow(m)>maxcells||nrow(c$expr)*nrow(m)*8>(c$cfg$max_dense_bytes %||% 2^31))stop('原生距离或MAGIC矩阵超过内存契约；需先提供有记录的细胞抽样设计，不静默抽样')
 if(any(Matrix::colSums(c$expr[,rownames(m),drop=FALSE])<=0))stop('存在零计数细胞')
 for(branch in branches){
  idx<-idx+1L;obj<-c$native(idx,paste(sample,branch,sep='::'),function(){
   seu<-Seurat::CreateSeuratObject(counts=c$expr[,rownames(m),drop=FALSE],meta.data=m);Seurat::Idents(seu)<-m$cell_type
   seu[['pca']]<-Seurat::CreateDimReducObject(embeddings=pca[rownames(m),,drop=FALSE],key='PC_',assay='RNA')
   z<-if(branch=='signaling')RNAMagnet::RNAMagnetSignaling(seu,.version=version) else RNAMagnet::RNAMagnetAnchors(seu,anchors=anchors,return='rnamagnet-class',.version=version)
   if(any(!is.finite(z@interaction))||any(!is.finite(z@specificity))||any(!is.finite(z@anchors))||any(!is.finite(z@adhesiveness)))stop('原生输出非有限（如恒定基因min-max除零）；保留失败，不将其改为零或偷偷删基因')
   list(result=z,metadata=m,branch=branch)
  });z<-obj$result
  c$wt(z@mylr,paste0('measured_resource_',idx,'.tsv'))
  c$wt(data.frame(cell=rownames(z@interaction),z@interaction,check.names=FALSE),paste0('cell_interaction_',idx,'.tsv'))
  c$wt(data.frame(cell=rownames(z@specificity),z@specificity,check.names=FALSE),paste0('cell_specificity_',idx,'.tsv'))
  c$wt(data.frame(cell=rownames(m),adhesiveness=z@adhesiveness),paste0('cell_adhesiveness_',idx,'.tsv'))
  if(!is.null(embedding)){
   points<-data.frame(sample=sample,cell=rownames(m),x=embedding[rownames(m),1],y=embedding[rownames(m),2])
   for(j in seq_len(ncol(z@specificity))){
    points$value<-z@specificity[points$cell,j]
    c$add(paste0('specificity_embedding_',idx,'_',j),'embedding_points',points,'原生逐细胞specificity，完整保留负值与原始降维位置，不将群间靠近解释为组织接触',embedding_method=c$cfg$embedding_method,embedding_provenance=c$cfg$embedding_provenance,axis_label='Native specificity',title=paste(branch,'from',colnames(z@specificity)[j]))
   }
   points$value<-z@adhesiveness
   c$add(paste0('adhesiveness_embedding_',idx),'embedding_points',points,'原生adhesiveness直接在MAGIC插补输出上求模糊核之和，不是LR数量，也不同于min-max后interaction的计算',embedding_method=c$cfg$embedding_method,embedding_provenance=c$cfg$embedding_provenance,axis_label='Native adhesiveness',title=paste(sample,branch))
   if(branch=='anchors'){
    direction<-colnames(z@specificity)[apply(z@specificity,1,which.max)];points$value<-NULL;points$label<-direction
    c$add(paste0('anchor_preference_',idx),'embedding_points',points,'原生最大specificity对应的锚群；并列使用原生列序中的首群，不标为可靠分类概率',embedding_method=c$cfg$embedding_method,embedding_provenance=c$cfg$embedding_provenance,title='Predicted anchor preference')
   }
  }
  meanmat<-function(v){w<-sapply(colnames(v),function(sender)tapply(v[,sender],z@celltype,mean));matrix(w,nrow=length(levels(z@celltype)),dimnames=list(levels(z@celltype),colnames(v)))}
  volume<-meanmat(z@interaction);specific<-meanmat(z@specificity)
  c$add(paste0('volume_',idx),'matrix',matrows(volume),'接收细胞类型内原生逐细胞interaction均值，列为发送锚群，行为接收群；不是相互作用数量或概率',axis_label='Mean native interaction score',title=paste(sample,branch))
  c$add(paste0('specificity_',idx),'matrix',matrows(specific),'接收细胞类型内原生specificity均值，保留负值。信号分支使用全局背景，黏附分支使用PCA相关邻域；没有统计P',axis_label='Mean native specificity',title=paste(sample,branch))
  e<-expand.grid(target=rownames(volume),source=colnames(volume));e$value<-as.vector(volume)
  c$add(paste0('interaction_network_',idx),'network',e,'原生interaction先对LR贡献相加再在接收群内取均值，发送锚群指向接收群。图中扇区汇总对这些群均值边等权相加，不代表全部细胞总强度；不按P筛选',value_kind='nonnegative_strength',additive=TRUE,directed=TRUE,axis_label='Mean native interaction score',title=paste(sample,branch))
  lr<-list();for(sender in colnames(z@anchors))for(receiver in colnames(z@anchors)){
   native<-RNAMagnet::getRNAMagnetGenes(z,sender,receiver,thresh=-Inf)
   # Native symmetrization retains the same Pair.Name for reversed endpoints.
   # getRNAMagnetGenes preserves its original row index when sorting scores.
   mm<-as.integer(rownames(native))
   if(anyNA(mm)||!setequal(mm,seq_len(nrow(z@mylr)))||!identical(as.character(native$pair),as.character(z@mylr$Pair.Name[mm])))stop('原生行身份未完整保留，不能按重复Pair.Name猜测端点')
   lr[[length(lr)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=sender,target=receiver,interaction=paste0('native_row:',mm,':',native$pair),native_pair=native$pair,ligand=z@mylr$Ligand.Mouse[mm],receptor=z@mylr$Receptor.Mouse[mm],ligand_identity=vapply(z@mylr$Ligand.Mouse[mm],identity,''),receptor_identity=vapply(z@mylr$Receptor.Mouse[mm],identity,''),score=native$score,tested=TRUE,supported=native$score>threshold)
  }
  c$add(paste0('lr_edges_',idx),'lr_edges',do.call(rbind,lr),'原生getRNAMagnetGenes：群平均表达先经过非线性核再相乘；不同于逐细胞interaction的群均值。展示支持仅按预设分数阈值，无P/FDR。黏附分支仅计算锚群之间的此种LR分数',value_kind='native_score',direction='higher',additive=FALSE,axis_label='Native group-mean fuzzy LR score',candidate_scope='native_measured_endpoints')
 }
}
if(idx==0L)stop('没有符合资格的样本，已保存原因')
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
