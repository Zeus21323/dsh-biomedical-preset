#!/usr/bin/env Rscript
# Native mistyR spatial views and models; no inferred ligand/receptor identities.
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y)if(is.null(x))y else x
a<-commandArgs(TRUE)
if(length(a)!=2)stop('需要配置JSON与新的Git仓库外输出目录')
if(!requireNamespace('jsonlite',quietly=TRUE))stop('缺少jsonlite')
cp<-normalizePath(a[1]);cfg<-jsonlite::read_json(cp,simplifyVector=TRUE)
resolve<-function(p)normalizePath(if(startsWith(p,'/'))p else file.path(dirname(cp),p))
if(!is.null(cfg$r_library)).libPaths(c(resolve(cfg$r_library),.libPaths()))
for(p in c('mistyR','digest','Matrix','future'))if(!requireNamespace(p,quietly=TRUE))stop('缺少原生依赖：',p)
if(as.character(packageVersion('mistyR'))!='1.18.0')stop('需要核验的mistyR 1.18.0')
for(k in c('dataset','research_question','input','features','feature_provenance','expression_scale','normalization_definition','resolution','coordinate_unit','coordinate_provenance','spatial_scale_provenance'))if(is.null(cfg[[k]])||!length(cfg[[k]]))stop('缺少：',k)
if(!cfg$resolution%in%c('single_cell','spot'))stop('resolution须说明single_cell/spot，不把spot称为细胞')
if(!cfg$coordinate_unit%in%c('um','pixel','native'))stop('坐标单位须为um/pixel/native')
if(cfg$coordinate_unit=='native'&&!isTRUE(cfg$physical_scale_unavailable))stop('未知物理比例须显式标记，不能声明微米传播范围')
input<-resolve(cfg$input);x<-readRDS(input);expr<-x$expression;meta<-x$metadata;pos<-x$coordinates
valid_ids<-function(ids)!is.null(ids)&&length(ids)>0&&!anyNA(ids)&&!anyDuplicated(ids)&&all(nzchar(trimws(ids)))
if(is.null(expr)||length(dim(expr))!=2||!valid_ids(rownames(expr))||!valid_ids(colnames(expr)))stop('expression需要身份唯一的特征×空间单元矩阵')
if(!is.data.frame(meta)||!valid_ids(rownames(meta))||!setequal(rownames(meta),colnames(expr)))stop('metadata须按空间单元ID对齐')
need<-c('sample','donor','condition','cell_type');if(!all(need%in%names(meta))||anyNA(meta[,need])||any(trimws(as.matrix(meta[,need]))==''))stop('metadata需要sample/donor/condition/cell_type；未知字段显式写unknown')
if(is.null(pos)||ncol(pos)!=2||!valid_ids(rownames(pos))||!setequal(rownames(pos),colnames(expr))||any(!is.finite(as.matrix(pos))))stop('coordinates需要同单元ID的真实二维坐标，不能用UMAP替代')
meta<-meta[colnames(expr),,drop=FALSE];pos<-as.matrix(pos[colnames(expr),,drop=FALSE]);colnames(pos)<-c('x','y')
features<-cfg$features;targets<-cfg$targets %||% features
if(!is.character(features)||!valid_ids(features)||any(!features%in%rownames(expr))||length(features)<2)stop('features须为至少两个事先定义且实际测量的特征')
if(!is.character(targets)||!valid_ids(targets)||any(!targets%in%features))stop('targets须属于已定义features')
# Native formulas and filenames use literal feature names. Reject unsafe names
# rather than silently repairing biological identity or allowing path traversal.
if(any(make.names(features)!=features)||any(grepl('[ /\\\\&]',features)))stop('原生公式要求安全R列名；请提供经记录的一对一特征ID映射')
if(length(features)*ncol(expr)*8>(cfg$max_dense_bytes %||% 2^31))stop('特征矩阵超过内存契约；不能自动抽样')
expr<-as.matrix(expr[features,,drop=FALSE]);if(any(!is.finite(expr)))stop('表达包含非有限值')
cv<-cfg$cv_folds %||% 10L;trees<-cfg$num_trees %||% 100L;seed<-cfg$seed %||% 42L
integer_value<-function(v,min)length(v)==1&&is.finite(v)&&v==as.integer(v)&&v>=min
if(!integer_value(cv,3)||!integer_value(trees,20)||!integer_value(seed,0))stop('cv_folds/num_trees/seed需为有效整数')
para<-cfg$paraview;juxta<-cfg$juxtaview
if(is.null(para)&&is.null(juxta)&&is.null(x$custom_views))stop('至少需要一个真实空间或有来源的custom视图')
positive<-function(v)length(v)==1&&is.finite(v)&&v>0
if(!is.null(para)){
 if(!positive(para$l))stop('paraview.l需要有坐标尺度依据的正数')
 para$family<-para$family %||% 'gaussian';if(!para$family%in%c('gaussian','exponential','linear','constant'))stop('未知原生核函数')
 para$zoi<-para$zoi %||% 0;if(!positive(para$zoi+1)||para$zoi<0)stop('zoi须为非负距离')
 if(!is.null(para$nn)&&!integer_value(para$nn,1))stop('nn须为正整数')
 if(!is.null(para$approx)&&para$approx!=1)stop('此入口执行精确或明确kNN视图；不静默启用Nyström近似')
}
if(!is.null(juxta)&&!positive(juxta$neighbor_thr))stop('juxtaview.neighbor_thr需要实际尺度依据')
if(!is.null(x$custom_views)){
 if(!is.list(x$custom_views)||!valid_ids(names(x$custom_views))||is.null(cfg$custom_view_provenance))stop('custom_views需要命名视图与来源')
 for(n in names(x$custom_views)){
  v<-x$custom_views[[n]]
  if(!grepl('^[a-z][a-z0-9_]*$',n)||n%in%c('intraview','misty.uniqueid')||!valid_ids(rownames(v))||!identical(rownames(v),colnames(expr))||!valid_ids(colnames(v))||any(make.names(colnames(v))!=colnames(v))||any(!is.finite(as.matrix(v))))stop('custom视图命名、数值或空间单元顺序无效')
 }
}
if(file.exists(a[2]))stop('拒绝覆盖已有目录')
parent<-normalizePath(dirname(a[2]),mustWork=FALSE);while(parent!='/'){if(file.exists(file.path(parent,'.git')))stop('分析输出必须位于Git外');parent<-dirname(parent)}
dir.create(a[2],recursive=TRUE);out<-normalizePath(a[2]);setwd(out)
hash<-function(p)digest::digest(file=p,algo='sha256')
wj<-function(v,n)jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na='null',null='null',digits=16)
wt<-function(v,n){v<-as.data.frame(v,check.names=FALSE);for(k in names(v))if(is.numeric(v[[k]]))v[[k]]<-format(v[[k]],digits=17,scientific=TRUE,trim=TRUE);write.table(v,file.path(out,n),sep='\t',quote=FALSE,row.names=FALSE,na='NA')}
versions<-setNames(lapply(c('mistyR','ranger','ridge','caret','deldir','distances'),function(p)as.character(packageVersion(p))),c('mistyR','ranger','ridge','caret','deldir','distances'))
signature<-digest::digest(list(versions=versions,input=hash(input),features=features,targets=targets,cv=cv,trees=trees,seed=seed,para=para,juxta=juxta,version='1.18.0'),algo='sha256')
reuse<-if(is.null(cfg$reuse_directory))NULL else resolve(cfg$reuse_directory)
if(!is.null(reuse)){old<-jsonlite::read_json(file.path(reuse,'run_metadata.json'));if(!identical(old$signature,signature))stop('输入、视图或模型参数变化，拒绝复用')}
wj(cfg,'run_config.json');objects<-list()
bundle<-list(schema_version=2,dataset=cfg$dataset,method='MISTy',method_version='1.18.0',implementation='native',provenance=list(input_sha256=hash(input),parameters=cfg,versions=versions,native_view_prefixes=list(juxta='juxta_',para='para_'),coordinate_provenance=cfg$coordinate_provenance,upstream=list(url='https://github.com/saezlab/mistyR',commit='5dcd31fecb52995216db1a589798660da8dc72a3',license='GPL-3.0'),semantics='空间视图的随机森林OOB预测加原生线性/岭元模型。细胞级随机CV不是供体或空间分块外部验证；重要性不代表方向性生物效应、LR边或因果。原生汇总将负R2截零，另存并绘制未截断CV结果。'),tables=list())
add<-function(id,type,rows,definition,...){fn<-paste0(id,'.tsv');wt(rows,fn);bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=fn,sha256=hash(file.path(out,fn)),value_definition=definition),list(...))}
suppressPackageStartupMessages(library(mistyR));future::plan(future::sequential)
for(i in seq_along(unique(meta$sample))){
 sample<-unique(meta$sample)[i];ids<-which(meta$sample==sample);sm<-meta[ids,,drop=FALSE]
 if(length(unique(sm$donor))!=1||length(unique(sm$condition))!=1)stop('每样本须有唯一供体/条件，池化必须明确写unknown并记录来源')
 if(length(ids)<max(30,3*cv)||length(ids)>(cfg$max_units %||% 5000))stop('样本单位数不足CV或超过声明资源上限')
 if(anyDuplicated(data.frame(pos[ids,,drop=FALSE]))||qr(sweep(pos[ids,,drop=FALSE],2,colMeans(pos[ids,,drop=FALSE])))$rank<2)stop('需要互异且非共线的真实二维坐标')
 dat<-as.data.frame(t(expr[,ids,drop=FALSE]),check.names=FALSE);pp<-as.data.frame(pos[ids,,drop=FALSE])
 if(any(vapply(dat,sd,numeric(1))==0))stop('样本含零方差特征；应先按公开规则排除并记录，不在模型内填值')
 if(!is.null(para$nn)&&para$nn>=length(ids))stop('nn不能达到或超过样本单元数')
 fn<-paste0('native_',i,'.rds')
 if(is.null(reuse)){
  views<-mistyR::create_initial_view(dat,unique.id=paste0(signature,'_',i))
  if(!is.null(juxta))views<-mistyR::add_juxtaview(views,pp,neighbor.thr=juxta$neighbor_thr,prefix='juxta_',cached=TRUE,verbose=FALSE)
  if(!is.null(para))views<-mistyR::add_paraview(views,pp,l=para$l,zoi=para$zoi,family=para$family,approx=1,nn=para$nn,prefix='para_',cached=TRUE,verbose=FALSE)
  if(!is.null(x$custom_views))for(n in names(x$custom_views))views<-mistyR::add_views(views,mistyR::create_view(n,as.data.frame(x$custom_views[[n]][ids,,drop=FALSE]),n))
  native_dir<-file.path(out,paste0('native_files_',i))
  mistyR::run_misty(views,results.folder=native_dir,seed=seed,target.subset=targets,cv.folds=cv,cached=TRUE,num.trees=trees)
  # Native run_misty only writes clipped summaries. Rebuild its meta-models
  # from the exact cached native OOB predictions to retain raw fold evidence.
  models<-setNames(lapply(targets,function(target)mistyR:::build_model(views,target,mistyR:::random_forest_model,'random_forest_model',cv,FALSE,seed,TRUE,num.trees=trees)),targets)
  collected<-mistyR::collect_results(native_dir)
  obj<-list(views=views,models=models,collected=collected,raw_files=setNames(lapply(list.files(native_dir,full.names=TRUE),readLines,warn=FALSE),list.files(native_dir)),sample=sample,metadata=sm,coordinates=pp)
  saveRDS(obj,file.path(out,fn))
 }else{
  record<-old$objects[[as.character(i)]];if(is.null(record)||record$sample!=sample||record$sha256!=hash(file.path(reuse,fn)))stop('复用对象身份/摘要不一致')
  obj<-readRDS(file.path(reuse,fn));file.copy(file.path(reuse,fn),file.path(out,fn))
  native_dir<-file.path(out,paste0('native_files_',i));dir.create(native_dir)
  for(n in names(obj$raw_files))writeLines(obj$raw_files[[n]],file.path(native_dir,n))
 }
 objects[[as.character(i)]]<-list(sample=sample,path=fn,sha256=hash(file.path(out,fn)));wj(list(signature=signature,objects=objects),'run_metadata.json')
 for(v in setdiff(names(obj$views),'misty.uniqueid'))wt(data.frame(cell=rownames(sm),obj$views[[v]]$data,check.names=FALSE),paste0('view_',i,'_',v,'.tsv'))
 raw<-do.call(rbind,lapply(names(obj$models),function(target)data.frame(target=target,fold=seq_len(nrow(obj$models[[target]]$performance.estimate)),obj$models[[target]]$performance.estimate)))
 wt(raw,paste0('unclipped_cv_',i,'.tsv'))
 if(any(!is.finite(as.matrix(raw[,c('intra.RMSE','multi.RMSE')]))))stop('原生CV预测存在非有限误差，不能宣称模型运行成功')
 for(metric in c('intra.R2','multi.R2','intra.RMSE','multi.RMSE')){
  val<-raw[[metric]];val[!is.finite(val)]<-NA_real_
  add(paste0('cv_',tolower(gsub('[.]','_',metric)),'_',i),'matrix',data.frame(row=raw$target,column=paste('Fold',raw$fold),value=val),'原生随机CV各折未截断性能；R2以百分数表示可为负。折不是独立供体，缺失不补零',axis_label=if(grepl('R2',metric))'Unclipped CV R² (%)' else 'Native CV RMSE',title=paste(sample,metric),column_order=paste('Fold',seq_len(cv)))
 }
 im<-obj$collected$improvements
 for(metric in c('gain.R2','gain.RMSE')){
  d<-im[im$measure==metric,,drop=FALSE];d$value[!is.finite(d$value)]<-NA_real_
  add(paste0('gain_',tolower(gsub('[.]','_',metric)),'_',i),'matrix',data.frame(row=d$target,column=metric,value=d$value),'原生汇总性能增益；R2先逐折截零再汇总，因此同时提供未截断折数据。负增益保留，非供体差异效应',axis_label=if(metric=='gain.R2')'Native R² gain (percentage points)' else 'Native relative RMSE gain (%)',display_style='lollipop',title=sample)
 }
 view_label<-function(v){z<-v;z[v=='intra']<-'Within unit';if(!is.null(juxta))z[grepl('^juxta[.]',v)]<-paste0('Adjacent (',format(juxta$neighbor_thr,digits=3),')');if(!is.null(para))z[grepl('^para[.]',v)]<-paste0('Broader (',format(para$l,digits=3),')');z}
 d<-obj$collected$contributions;d<-d[!grepl('^p[.]',d$view)&d$view!='intercept',,drop=FALSE]
 add(paste0('view_coefficients_',i),'matrix',data.frame(row=d$target,column=view_label(d$view),native_view=d$view,value=d$value),'原生元模型带符号系数；不是生物激活/抑制方向。原生系数P值保留在原始表，无供体层级显著性解释',axis_label='Native meta-model coefficient',title=sample)
 d<-obj$collected$importances
 for(j in seq_along(unique(d$view))){
  vv<-unique(d$view)[j];dd<-d[d$view==vv,,drop=FALSE];dd$Importance[!is.finite(dd$Importance)]<-NA_real_
  add(paste0('predictor_importance_',i,'_',j),'matrix',data.frame(row=dd$Predictor,column=dd$Target,value=dd$Importance),'原生RF impurity重要性按靶标标准化并乘以(1-元模型视图P)；负值表示相对重要性低，不能解释为抑制。空间视图前缀保留邻近同一标记，避免被原生目标列覆盖',axis_label='Native standardized weighted importance',title=paste(sample,view_label(vv)),display_top_rows=30,display_top_columns=20,figure_role='intracellular_response')
 }
 for(j in seq_along(targets))add(paste0('observed_marker_',i,'_',j),'spatial_points',data.frame(sample=sample,cell=rownames(sm),x=pp$x,y=pp$y,value=dat[[targets[j]]]),'真实空间单元的输入标记值，用于核对空间模型背景；不是通讯强度或模型预测',coordinate_unit=cfg$coordinate_unit,physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable),y_down=isTRUE(cfg$y_down),axis_label=paste(targets[j],cfg$expression_scale),title=paste(sample,targets[j]))
}
wj(bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(out,'sessionInfo.txt'))
