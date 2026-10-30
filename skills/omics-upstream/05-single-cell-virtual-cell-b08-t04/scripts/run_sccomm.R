#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
a<-commandArgs(TRUE);if(length(a)!=2)stop('需要配置JSON与新的Git外输出目录')
f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1]);script_dir<-dirname(normalizePath(f));source(file.path(script_dir,'native_expression_context.R'))
c<-native_expression_context(a,'scComm','Matrix',as.character(packageVersion('Matrix')),species='human');cfg<-c$cfg
for(k in c('native_root','resource_provenance','input_provenance'))if(is.null(cfg[[k]]))stop('缺少：',k)
root<-c$resolve(cfg$native_root);src<-file.path(root,'scComm.R');expected<-'7e8f52a01dba6b1d569c346b3e8c13dc858eb687c87a4778f4395fc8cab10ee9'
if(c$hash(src)!=expected)stop('需要已核验scComm源码ed0f372；不能混用同名算法')
lrp<-if(is.null(cfg$lr_database))file.path(root,'data/LRpairs.txt')else c$resolve(cfg$lr_database)
tfp<-if(is.null(cfg$tf_database))file.path(root,'data/regulation.rds')else c$resolve(cfg$tf_database)
lr<-read.table(lrp,sep='\t',header=FALSE);tf<-readRDS(tfp)
if(ncol(lr)!=2||anyNA(lr)||any(as.matrix(lr)=='')||anyDuplicated(lr)||any(grepl('---',as.matrix(lr)))||!all(c('is_inhibition')%in%names(tf))||ncol(tf)<4)stop('LR/调控资源格式或原生分隔符身份无效')
if(any(grepl('---',c$meta$cell_type)))stop('细胞标签不能包含原生---分隔符')
seed<-cfg$seed %||% 42L;contrast<-cfg$contrastive %||% TRUE;prop<-cfg$augmentation_top_fraction %||% .05;limit<-cfg$lr_display_limit %||% 2000L
if(!is.logical(contrast)||length(contrast)!=1||!is.finite(seed)||seed<0||!is.finite(prop)||prop<=0||prop>=1||limit<1||limit!=as.integer(limit))stop('随机种子/对比学习/展示参数无效')
if(prop!=.05&&is.null(cfg$augmentation_provenance))stop('非默认增强分位数须有事先的数据规模/设计依据，不按分类结果调参')
if(contrast&&is.null(cfg$contrast_python))stop('对比学习需要具备torch/sklearn的contrast_python；不能只跑基础评分却报告完整分支')
py<-if(contrast)normalizePath(if(startsWith(cfg$contrast_python,'/'))cfg$contrast_python else file.path(dirname(c$cp),cfg$contrast_python),mustWork=TRUE)else NULL
# Python venv executables can be symlinks; retain the environment path.
if(contrast)py<-if(startsWith(cfg$contrast_python,'/'))cfg$contrast_python else file.path(dirname(c$cp),cfg$contrast_python)
versions<-setNames(lapply(c('Matrix','Seurat','entropy','pracma','NMF','RcppML','matrixStats'),function(p)as.character(packageVersion(p))),c('Matrix','Seurat','entropy','pracma','NMF','RcppML','matrixStats'))
params<-list(commit='ed0f372fdc122333afa834150c566948bef68a29',seed=seed,minimum=c$minimum,contrastive=contrast,augmentation_top_fraction=prop,versions=versions,python=py)
c$start_cache(c(c$hash(lrp),c$hash(tfp),c$hash(src)),params)
c$bundle$method_version<-params$commit;c$bundle$provenance$upstream<-list(url='https://github.com/ZijieJin/scComm',commit=params$commit,license='LICENSE: MIT; README separately requests a paid license for non-academic use; deployment must resolve this inconsistency, adapter does not redistribute upstream code')
c$bundle$provenance$semantics<-'原生熵/竞争/调控权重及细胞对截断标准化LR评分。GroupCCC的100次标签置换形成混合正态参考并用Holm，不是独立供体统计；LR原生函数仅对最后一个LR做p.adjust，不能将其返回标记叫全LR FDR。对比学习标签来自同一数据的高分群和增强样本，是模型分类而非实验真值/显著性。'
custom<-readRDS(c$input)$custom_groups
if(!is.null(custom)&&(!all(c('sample','CellName','Tag','Group')%in%names(custom))||anyNA(custom)||anyDuplicated(custom)||any(!custom$Tag%in%c('Sender','Receptor'))||is.null(cfg$custom_group_provenance)))stop('自定义群需要sample/CellName/Tag/Group、唯一完整身份与custom_group_provenance')
if(!is.null(custom)&&any(!custom$sample%in%c$meta$sample))stop('自定义群含不存在的样本，不能静默忽略')
matrows<-function(m){d<-expand.grid(row=rownames(m),column=colnames(m));d$value<-as.vector(m);d}
make_env<-function(){e<-new.env(parent=globalenv());for(k in c('lr_network','tfs','LRpairs_str','cellanno','this_data_groups','anno'))e[[k]]<-NULL;suppressPackageStartupMessages(sys.source(src,envir=e));e}
all_edges<-list()
for(i in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[i];m<-c$sample_meta(sample);ids<-rownames(m);groups<-unique(m$cell_type);ng<-length(groups);n<-length(ids)
 measured<-lr[lr[,1]%in%rownames(c$expr)&lr[,2]%in%rownames(c$expr),,drop=FALSE]
 if(n>(cfg$max_cells %||% 3000)||ng^2*nrow(measured)*8*8+n^2*8*5>(cfg$max_working_bytes %||% 8*2^30)||n*nrow(c$expr)*8>(cfg$max_dense_bytes %||% 2^31))stop('超出原生稠密矩阵/张量内存契约，请按实际样本或研究焦点设计输入，不能静默抽样')
 expr<-as.matrix(c$expr[,ids,drop=FALSE]);e<-make_env();e$anno<-m$cell_type
 work<-file.path(c$out,paste0('native_work_',i));dir.create(file.path(work,'data'),recursive=TRUE);file.copy(tfp,file.path(work,'data/regulation.rds'))
 obj<-c$native(i,sample,function(){
  set.seed(seed+i-1L);fit<-e$scComm(expr,m$cell_type,lr_database=lrp,tf_database=tfp)
  if(any(!is.finite(fit$ccires$cciscore))||any(!is.finite(fit$ccires$lrscore))||any(!is.finite(fit$weights$totalweight)))stop('原生评分出现非有限值，不能补零交付')
  aug<-NULL
  if(contrast){
   if(n<50)stop('原生增强分支每次无放回抽50个细胞，输入不足')
   # Native code drops the matrix dimension with one selected positive group.
   sums<-as.vector(fit$GroupCCC);if(sum(sums>quantile(sums,1-prop))<2)stop('原生增强分支选中的阳性群少于2，触发降维不兼容；不为通过而调整分位数')
   oldwd<-getwd();setwd(work);on.exit(setwd(oldwd),add=TRUE)
   aug<-e$MakeAugmentedData(expr,fit,lr_database=lrp,prop=prop);setwd(oldwd)
   if(any(!is.finite(as.matrix(aug$PositiveData)))||any(!is.finite(as.matrix(aug$NegativeData))))stop('原生增强产生非有限值')
  }
  list(fit=fit,lr_network=e$lr_network,tf=e$tfs,augmentation=aug,metadata=m,rng=.Random.seed)
 })
 fit<-obj$fit;c$wt(data.frame(cell=ids,cell_type=m$cell_type),paste0('cell_identities_',i,'.tsv'))
 for(key in c('GroupCCC_Zscore','GroupCCC_padj')){mm<-fit$GroupCCC_res[[key]];dimnames(mm)<-dimnames(fit$GroupCCC);c$add(paste0(tolower(key),'_',i),'matrix',matrows(mm),'原生100次细胞标签置换的混合正态参考；p.adjust默认Holm，统计单位非供体，非全LR FDR',axis_label=if(key=='GroupCCC_padj')'Native group Holm P' else 'Native group Z',title=sample)}
 c$add(paste0('group_network_',i),'network',data.frame(source=rep(rownames(fit$GroupCCC),times=ng),target=rep(colnames(fit$GroupCCC),each=ng),value=as.vector(fit$GroupCCC)),'原生群内所有细胞对总通讯分数的平均，方向为配体群→受体群；包括自群，不是检验支持的边',directed=TRUE,additive=TRUE,value_kind='nonnegative_strength',axis_label='Native mean cell-pair score')
 celltype_score<-sapply(groups,function(g)rowMeans(fit$ccires$cciscore[,m$cell_type==g,drop=FALSE]));rownames(celltype_score)<-ids
 c$add(paste0('cell_to_group_',i),'matrix',matrows(celltype_score),'真实逐发送细胞到接收群平均分；展示筛选不改变完整原生cell×cell矩阵',axis_label='Native mean cell-pair score',title=sample,display_top_rows=30L,display_top_columns=20L)
 arr<-fit$ccires$lrscore;native_lr<-obj$lr_network;sig<-fit$LR_sig_all;key<-function(a,b,l,r)paste(a,b,l,r,sep='\r');reported<-key(sig$g1,sig$g2,sig$l,sig$r)
 # Retain the complete native tensor in the hashed RDS. Plot data is an explicit
 # ranked subset so large cell-level methods do not fabricate dense zero tables.
 best<-NULL;full_table<-length(arr)<=(cfg$max_lr_table_rows %||% 2000000L)
 for(k in seq_len(dim(arr)[3])){
  v<-as.vector(arr[,,k]);ix<-if(full_table)seq_along(v)else which(v>0)
  le<-expr[native_lr[k,1],];re<-expr[native_lr[k,2],];eligible<-sqrt(sd(le)*sd(re))>=.1&&mean(le>0)*mean(re>0)>.0001
  if(length(ix)){
   dd<-data.frame(source=groups[(ix-1)%%ng+1],target=groups[(ix-1)%/%ng+1],ligand=native_lr[k,1],receptor=native_lr[k,2],score=v[ix],tested=eligible)
   if(full_table){if(is.null(best))best<-list();best[[length(best)+1]]<-dd}else{best<-rbind(best,dd);best<-head(best[order(best$score,decreasing=TRUE),,drop=FALSE],limit)}
  }
 }
 if(length(best)){
  d<-if(full_table)do.call(rbind,best)else best;d$sample<-sample;d$donor<-m$donor[1];d$condition<-m$condition[1];d$supported<-key(d$source,d$target,d$ligand,d$receptor)%in%reported;d$ligand_identity<-paste0('gene:',d$ligand);d$receptor_identity<-paste0('gene:',d$receptor);d$export_scope<-if(full_table)'full_native_measured_lr_tensor'else'explicit_score_ranked_subset';all_edges[[length(all_edges)+1]]<-d
 }else c$add(paste0('empty_lr_',i),'matrix',data.frame(row=sample,column='Positive native LR scores',value=0),'原生有限评分未出现正值；不是因果无通讯证据',value_kind='count')
 c$wt(sig,paste0('native_lr_selected_',i,'.tsv'));c$wt(fit$LR_sig,paste0('native_group_and_lr_selected_',i,'.tsv'))
 c$wj(list(sample=sample,cells=n,groups=ng,measured_lr=nrow(native_lr),full_tensor_entries=length(arr),full_table=full_table,lr_display_limit=limit,full_scores=paste0('native_',i,'.rds'),selection='Full tensor table below configured size guard; otherwise explicit descending positive score subset, full native tensor always preserved. Native supported flag is not uniform FDR'),paste0('scope_',i,'.json'))
 if(!is.null(custom)){
  cc<-custom[custom$sample==sample,c('CellName','Tag','Group'),drop=FALSE];cc$Group<-as.character(cc$Group)
  if(nrow(cc)){
   if(any(!cc$CellName%in%ids)||any(trimws(cc$Group)=='')||length(unique(cc$Group))<2||any(table(cc$Group,cc$Tag)<2))stop('自定义比较群需至少两组，每组真实发送/接收细胞各至少2，不能静默丢失细胞')
   if(length(intersect(cc$CellName[cc$Tag=='Sender'],cc$CellName[cc$Tag=='Receptor'])))stop('原生自定义群分支不支持同一细胞跨发送/接收角色的重复身份；不能错误索引')
   cc<-cc[order(match(cc$CellName,ids),cc$Group),,drop=FALSE]
   oldwd<-getwd();setwd(work);e$anno<-m$cell_type
   ans<-tryCatch(e$FindLRscoreGivenCells(expr,fit,cc,lr_database=lrp),finally=setwd(oldwd))
   saveRDS(ans,file.path(work,'native_custom_groups.rds'))
   if(is.null(ans)||any(is.infinite(ans$lrscore))||any(is.infinite(ans$lrscoresd))||!any(is.finite(ans$lrscore)))stop('原生自定义群评分不可用；原始返回值已保存')
   c$wt(cc,paste0('custom_group_membership_',i,'.tsv'))
   c$wj(list(missing_mean=sum(is.na(ans$lrscore)),missing_sd=sum(is.na(ans$lrscoresd)),definition='Native custom branch may produce NaN for zero-variance positive products; retain missing, never fill zero'),paste0('custom_missingness_',i,'.json'))
   for(metric in c('lrscore','lrscoresd'))c$add(paste0('custom_',metric,'_',i),'matrix',matrows(ans[[metric]]),'原生FindLRscoreGivenCells按明确成员重新计算LR的群内细胞对均值或SD；SD不是供体SE/CI。原生零方差等产生NaN时保留缺失，不填零；输入按真实表达列顺序对齐，避免原生顺序索引错配',axis_label=paste('Native custom-group',metric),title=sample,display_top_rows=30L)
  }
 }
 if(contrast){
  for(nm in c('PositiveData','NegativeData','Fulldata'))write.csv(obj$augmentation[[nm]],file.path(work,paste0(nm,'.csv')),quote=FALSE)
  command<-c(shQuote(file.path(script_dir,'run_sccomm_contrast.py')),'--native',shQuote(file.path(root,'ContrastiveLearning.py')),'--work',shQuote(work),'--seed',as.character(seed+i-1L))
  rc<-system2(py,command,stdout=file.path(work,'contrast_wrapper.log'),stderr=file.path(work,'contrast_stderr.log'),timeout=cfg$contrast_timeout_seconds %||% 3600)
  if(rc!=0)stop('原生对比学习失败/超时，基础原生对象保留；不能报告全部完成')
  pp<-read.csv(file.path(work,'fulldata_prediction.csv'),check.names=FALSE);sp<-strsplit(pp$CCC_pair,'---',fixed=TRUE)
  c$add(paste0('contrast_labels_',i),'matrix',data.frame(row=vapply(sp,`[[`,character(1),1),column=vapply(sp,`[[`,character(1),2),value=pp$prediction),'原生SupCon表示及同数据Logistic分类；增强标签不是实验证据，0/1不是P、概率或供体差异',axis_label='Native contrastive class (0/1)',title=sample)
  history<-read.csv(file.path(work,'native_loss_history.csv'));c$add(paste0('contrast_loss_',i),'matrix',data.frame(row=as.character(history$epoch),column='Native printed SupCon loss',value=history$loss),'原生每10轮打印的四位小数损失；非逐轮原始精度，未做独立外部验证',axis_label='Native printed loss',figure_role='convergence',title=sample)
 }
}
if(length(all_edges))c$add('lr_edges','lr_edges',do.call(rbind,all_edges),'原生LR分数完整表或大规模时明确标注的展示子集，逐行export_scope和scope文件区分；完整张量始终保留。tested遵循原生全局变异/非零资格，supported仅保留原生FindHighCommLR标记，其只校正最后一个LR，不能称全LR FDR或把未显示解释为无通讯',value_kind='nonnegative_strength',additive=TRUE,candidate_scope='see_per_sample_scope_and_row_export_scope',axis_label='Native weighted LR score')
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
