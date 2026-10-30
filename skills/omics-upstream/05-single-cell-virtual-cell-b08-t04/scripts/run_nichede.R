#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
a<-commandArgs(TRUE);if(length(a)!=2)stop('需要配置JSON与新的Git外输出目录')
if(!requireNamespace('jsonlite',quietly=TRUE))stop('缺少jsonlite')
pre<-jsonlite::read_json(a[1]);f<-sub('^--file=','',commandArgs()[grepl('^--file=',commandArgs())][1]);source(file.path(dirname(normalizePath(f)),'native_expression_context.R'))
c<-native_expression_context(a,'NicheDE','nicheDE','0.0.0.9000',counts_input=identical(pre$expression_scale,'counts'),species=c('human','mouse'))
suppressPackageStartupMessages(library(Matrix));suppressPackageStartupMessages(library(nicheDE))
cfg<-c$cfg;x<-readRDS(c$input);pos<-x$coordinates;ref<-x$library_expression;fractions<-x$cell_fractions
for(k in c('resolution','coordinate_unit','coordinate_provenance','sigma','spatial_scale_provenance','reference_provenance','composition_provenance','gene_universe_provenance'))if(is.null(cfg[[k]])||!length(cfg[[k]]))stop('缺少：',k)
if(!cfg$resolution%in%c('single_cell','spot')||!cfg$coordinate_unit%in%c('um','pixel','native'))stop('分辨率或坐标单位不明确')
if(cfg$coordinate_unit=='native'&&!isTRUE(cfg$physical_scale_unavailable))stop('未知物理标定须显式声明')
ids<-colnames(c$expr);valid_names<-function(z)!is.null(z)&&!anyNA(z)&&!anyDuplicated(z)&&all(nzchar(trimws(z)))
if(is.null(pos)||ncol(pos)!=2||!valid_names(rownames(pos))||!setequal(rownames(pos),ids)||any(!is.finite(as.matrix(pos))))stop('coordinates需同单元身份的真实二维坐标')
if(is.null(ref)||is.null(fractions)||!valid_names(rownames(ref))||!valid_names(colnames(ref))||!valid_names(rownames(fractions))||!valid_names(colnames(fractions))||!setequal(rownames(fractions),ids)||!setequal(rownames(ref),colnames(fractions)))stop('library_expression或cell_fractions身份不完整')
ref<-as.matrix(ref);fractions<-as.matrix(fractions[ids,rownames(ref),drop=FALSE]);pos<-as.matrix(pos[ids,,drop=FALSE])
if(any(!is.finite(ref))||any(ref<0)||any(!is.finite(fractions))||any(fractions<0)||any(abs(rowSums(fractions)-1)>1e-6)||any(rowSums(ref)<=0))stop('参考均值/细胞比例无效，比例必须由实际注释或解卷积得到且行和为1')
if(nrow(ref)<2||length(intersect(colnames(ref),rownames(c$expr)))<2)stop('至少需要两个细胞类型及共享基因')
if(cfg$resolution=='single_cell'&&any(!fractions%in%c(0,1)))stop('单细胞分支要求真实标签one-hot，不能把混合spot叫单细胞')
sigma<-as.numeric(cfg$sigma);cutoff<-cfg$kernel_cutoff %||% .05;C<-cfg$minimum_gene_counts %||% 150;M<-cfg$minimum_colocalized_units %||% 10;gamma<-cfg$reference_quantile %||% .8;alpha<-cfg$alpha %||% .05;self<-cfg$self_niche %||% FALSE
if(!length(sigma)||any(!is.finite(sigma))||any(sigma<=0)||anyDuplicated(sigma)||length(sigma)>10||!is.finite(C)||C<0||M<2||M!=as.integer(M)||!0<gamma||gamma>=1||!0<cutoff||cutoff>=1||!0<alpha||alpha>=1||!is.logical(self)||length(self)!=1)stop('核尺度/筛选/显著性参数无效')
queries<-cfg$niche_lr_queries;if(is.data.frame(queries))queries<-lapply(seq_len(nrow(queries)),function(i)as.list(queries[i,,drop=FALSE]))
resources<-NULL
if(length(queries)){
 if(!identical(cfg$expression_scale,'counts'))stop('原生Niche-LR表达检验需要counts，不能对连续值套泊松分支')
 if(!is.null(cfg$lr_resources)){
  if(is.null(cfg$lr_resource_provenance)||!identical(cfg$lr_resource_species,cfg$species))stop('LR资源需要来源与匹配物种')
  resources<-readRDS(c$resolve(cfg$lr_resources))
 }else{
  if(cfg$species!='human')stop('包内NicheNet/Ramilowski资源为人类；其他物种须明确提供已核验资源')
  e<-new.env();data('niche_net_ligand_target_matrix',package='nicheDE',envir=e);data('ramilowski_ligand_receptor_list',package='nicheDE',envir=e)
  resources<-list(ligand_target=e$niche_net_ligand_target_matrix,lr=e$ramilowski_ligand_receptor_list)
 }
 lt<-resources$ligand_target;lr<-as.matrix(resources$lr)
 if(is.null(lt)||!valid_names(rownames(lt))||!valid_names(colnames(lt))||any(!is.finite(lt))||any(lt<0)||ncol(lr)!=2||anyNA(lr)||any(!nzchar(lr)))stop('LR资源形状、身份或值无效')
 for(q in queries)if(is.null(q$ligand_cell)||is.null(q$receptor_cell)||!all(c(q$ligand_cell,q$receptor_cell)%in%rownames(ref)))stop('Niche-LR需真实发送与接收群')
 saveRDS(resources,file.path(c$out,'native_lr_resources.rds'))
}
versions<-setNames(lapply(c('nicheDE','Matrix','poolr'),function(p)as.character(packageVersion(p))),c('nicheDE','Matrix','poolr'))
params<-list(sigma=sigma,cutoff=cutoff,C=C,M=M,gamma=gamma,alpha=alpha,self=self,Int=cfg$expression_scale=='counts',queries=queries,versions=versions)
c$start_cache(digest::digest(resources,algo='sha256'),params)
c$bundle$provenance$upstream<-list(url='https://github.com/kaishumason/NicheDE',commit='87e0e89bb066702a54fa47638965b61dc6f24d05',license='MIT; upstream LICENSE file; DESCRIPTION retains a template placeholder')
c$bundle$provenance$coordinate_provenance<-cfg$coordinate_provenance
c$bundle$provenance$native_missingness<-'某一核的log_likelihood缺失可经权重传播，使interaction层在其他核存在有效估计时仍整体缺失；保持原生值，不能填零或冒称未见关联。poolr需要nearPD时保留运行警告，不视为协方差已通过独立验证。'
c$bundle$provenance$semantics<-'原生NicheDE逐样本执行；counts分支用Poisson均值拟合、优化负二项离散度并估计协方差，不冒称标准联合NB-GLM。多核按原生似然权重/Cauchy组合并分层BH；统计单位是空间单元，不是独立供体。原生内部捕获部分拟合错误，valid=0可能为筛除或拟合不可用，不能全部叫阴性。'
all_lr<-list();lr_failed<-FALSE
for(i in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[i];sm<-c$meta[c$meta$sample==sample,,drop=FALSE];cid<-rownames(sm);pp<-pos[cid,,drop=FALSE];n<-length(cid)
 if(n<30||n>=10000||n>(cfg$max_units %||% 5000)||n*n*8>(cfg$max_distance_bytes %||% 2^31))stop('样本空间规模不合契约；仅核验<10000单元的原生确定性尺度分支')
 if(anyDuplicated(data.frame(pp)))stop('重复空间坐标需核实，不能产生零距离尺度')
 if(n*nrow(c$expr)*8>(cfg$max_dense_bytes %||% 2^31))stop('表达矩阵超过原生对象创建内存契约')
 obj<-c$native(i,sample,function(){
  nde<-nicheDE::CreateNicheDEObject(t(c$expr[,cid,drop=FALSE]),as.data.frame(pp),ref,fractions[cid,,drop=FALSE],sigma=sigma,Int=params$Int)
  if(any(!is.finite(nde@num_cells))||any(nde@num_cells<0)||any(!is.finite(as.matrix(nde@coord))))stop('原生细胞数估计/缩放非有限')
  nde<-nicheDE::CalculateEffectiveNiche(nde,cutoff=cutoff)
  before<-nde;saveRDS(before,file.path(c$out,paste0('prepared_niche_',i,'.rds')))
  nde<-nicheDE::niche_DE_no_parallel(nde,C=C,M=M,gamma=gamma,print=TRUE,Int=params$Int,batch=TRUE,self_EN=self)
  results<-list()
  for(j in seq_along(queries)){
   q<-queries[[j]];K<-q$K %||% 25L;topM<-q$M %||% 50L;trunc<-q$truncation_value %||% 3
   if(K<5||K!=as.integer(K)||topM<1||topM!=as.integer(topM)||!is.finite(trunc)||trunc<=0)stop('Niche-LR K/M/截断参数无效')
   result<-tryCatch({
    if(cfg$resolution=='single_cell'&&any(!nde@num_cells%in%c(0,1)))stop('原生niche_LR_cell使用num_cells==1；当前表达尺度估计的num_cells并非one-hot，不能擅改为1后声称复现')
    if(cfg$resolution=='single_cell')ans<-nicheDE::niche_LR_cell(nde,q$ligand_cell,q$receptor_cell,lt,lr,K=K,M=topM,alpha=alpha,alpha_2=q$alpha_2 %||% .5,truncation_value=trunc) else ans<-nicheDE::niche_LR_spot(nde,q$ligand_cell,q$receptor_cell,lt,lr,K=K,M=topM,alpha=alpha,truncation_value=trunc)
    list(status='returned',table=as.data.frame(ans),query=q)
   },error=function(e)list(status=if(conditionMessage(e)%in%c('no ligand-receptor pairs to report','No candidate ligands'))'native_no_pairs' else 'native_failure',message=conditionMessage(e),query=q))
   results[[j]]<-result
  }
  list(nde=nde,before=before,lr=results,metadata=sm,coordinates=pp)
 })
 nde<-obj$nde;nc<-length(nde@cell_types);c$wt(data.frame(cell=cid,nde@num_cells,check.names=FALSE),paste0('estimated_cell_counts_',i,'.tsv'))
 c$wj(list(sample=sample,native_scale=nde@scale,scale_definition='For <10000 units: 100 divided by mean of each point second-nearest distance, including zero self in sorted distances; not the median-nearest claimed by vignette',genes=length(nde@gene_names),original_genes=nrow(c$expr),cells=n),paste0('scope_',i,'.json'))
 eligibility<-list()
 for(k in seq_along(sigma)){
  raw<-list()
  for(g in seq_along(nde@gene_names)){
   z<-nde@niche_DE[[k]][[g]];eligibility[[length(eligibility)+1]]<-data.frame(gene=nde@gene_names[g],sigma=sigma[k],native_valid=z$valid,interpretation=if(z$valid==1)'estimated' else 'filtered_or_native_fit_unavailable')
   if(z$valid==1){d<-expand.grid(index=nde@cell_types,niche=nde@cell_types);d$gene<-nde@gene_names[g];d$beta<-as.vector(as.matrix(z$betas));d$T_stat<-as.vector(as.matrix(z$T_stat));raw[[length(raw)+1]]<-d}
  }
  if(length(raw)){
   d<-do.call(rbind,raw);if(any(is.infinite(d$beta))||any(is.infinite(d$T_stat)))stop('原生回归系数或统计量无穷，需核验后再交付')
   c$wt(d,paste0('regression_',i,'_',k,'.tsv'))
   for(metric in c('beta','T_stat'))c$add(paste0('niche_',tolower(metric),'_',i,'_',k),'matrix',data.frame(row=d$gene,column=paste(d$index,d$niche,sep=' <- '),value=d[[metric]]),'原生index细胞类型对niche邻域的回归量；NA是未估计，符号是模型条件关联，非细胞因果或跨条件差异',axis_label=paste('Native niche',metric),title=paste(sample,'sigma',sigma[k]),display_top_rows=25L,display_top_columns=20L)
  }
  en<-nde@effective_niche[[k]]
  for(j in seq_len(nc))c$add(paste0('effective_niche_',i,'_',k,'_',j),'spatial_points',data.frame(sample=sample,cell=cid,x=pp[,1],y=pp[,2],value=en[,j]),'原生含自位置的截断Gaussian核×估计细胞数，再逐类型z标准化；空间图保留原始坐标，不把内部100单位归一化当微米',coordinate_unit=cfg$coordinate_unit,physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable),y_down=isTRUE(cfg$y_down),axis_label='Native effective niche z-score',title=paste(sample,nde@cell_types[j],sigma[k]))
 }
 el<-do.call(rbind,eligibility);c$wt(el,paste0('gene_fit_eligibility_',i,'.tsv'))
 for(sign in c('pos','neg')){
  pv<-if(sign=='pos')nde@niche_DE_pval_pos else nde@niche_DE_pval_neg
  q<-as.numeric(pv$gene_level);q[!is.finite(q)]<-NA_real_
  c$add(paste0('gene_q_',sign,'_',i),'matrix',data.frame(row=nde@gene_names,column=sign,value=-log10(pmax(q,1e-300)),native_q=q),'原生多核组合后gene层BH；正/负各为原生独立检验分支；仅显示-log10(q)，q=0的数值下溢显示封顶300，原值保留，无有效拟合为NA',axis_label='−log10 native gene adjusted P (cap 300)',display_top_rows=25L,display_style='lollipop',title=sample)
  c$wt(data.frame(gene=nde@gene_names,pv$cell_type_level,check.names=FALSE),paste0('native_celltype_q_',sign,'_',i,'.tsv'))
  arr<-pv$interaction_level;d<-expand.grid(index=nde@cell_types,niche=nde@cell_types,gene=nde@gene_names);d$native_q<-as.vector(arr);c$wt(d,paste0('native_interaction_q_',sign,'_',i,'.tsv'))
 }
 c$add(paste0('fit_status_',i),'matrix',data.frame(row=paste('sigma',sigma),column='Native valid genes',value=vapply(nde@niche_DE,function(z)sum(vapply(z,function(g)g$valid==1,logical(1))),numeric(1))),'原生有效拟合基因数；未拟合/技术不可估计与阴性分开，完整资格表另存',axis_label='Native fitted gene count',value_kind='count',display_style='lollipop')
 for(j in seq_along(obj$lr)){
  z<-obj$lr[[j]];q<-z$query;c$wj(z,paste0('niche_lr_status_',i,'_',j,'.json'))
  if(z$status=='native_failure'){lr_failed<-TRUE;next}
  if(z$status!='returned'||!nrow(z$table)){c$add(paste0('niche_lr_empty_',i,'_',j),'matrix',data.frame(row=paste(q$ligand_cell,q$receptor_cell,sep=' -> '),column='Returned pairs',value=0),'原生Niche-LR没有返回候选；不是全数据库已检验且无通讯',value_kind='count');next}
  d<-z$table;c$wt(d,paste0('native_niche_lr_',i,'_',j,'.tsv'))
  all_lr[[length(all_lr)+1]]<-data.frame(sample=sample,donor=sm$donor[1],condition=sm$condition[1],source=q$ligand_cell,target=q$receptor_cell,ligand=d$ligand,receptor=d$receptor,ligand_identity=paste0('gene:',d$ligand),receptor_identity=paste0('gene:',d$receptor),score=1,tested=TRUE,supported=TRUE,top_downstream_niche_DE_genes=d$top_downstream_niche_DE_genes)
 }
}
if(length(all_lr))c$add('lr_edges','lr_edges',do.call(rbind,all_lr),'原生Niche-LR仅返回筛后LR和下游基因字符串，未返回完整活动分数/P；1仅为原生入选标记，不是强度或全候选FDR。原生受体验证使用配体的参考表达索引，保留其实现并明确不能视为独立受体验证',value_kind='native_score',additive=FALSE,axis_label='Native returned-pair indicator',candidate_scope='native_postselection_lr_only')
c$wj(c$bundle,'bundle.json');capture.output(sessionInfo(),file=file.path(c$out,'sessionInfo.txt'))
if(lr_failed)stop('NicheDE对象已保存，但至少一个Niche-LR分支失败；见niche_lr_status，不报告全部成功')
