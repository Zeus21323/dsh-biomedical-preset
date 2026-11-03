#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)

`%||%` <- function(x,y) if(is.null(x)) y else x
args <- commandArgs(TRUE)
if(length(args)!=2) stop('需要配置JSON与新的Git外输出目录')
if(!requireNamespace('jsonlite',quietly=TRUE)) stop('缺少jsonlite')
cp <- normalizePath(args[1])
cfg <- jsonlite::read_json(cp,simplifyVector=TRUE)
resolve <- function(path) normalizePath(if(startsWith(path,'/')) path else file.path(dirname(cp),path))
if(!is.null(cfg$r_libraries)) {
  for(lib in rev(cfg$r_libraries)) .libPaths(c(resolve(lib),.libPaths()))
} else if(!is.null(cfg$r_library)) {
  .libPaths(c(resolve(cfg$r_library),.libPaths()))
}
for(pkg in c('Seurat','cellAlign','lmtest','future','future.apply','dplyr','tibble','digest'))
  if(!requireNamespace(pkg,quietly=TRUE)) stop('缺少原生依赖：',pkg)
if(as.character(packageVersion('cellAlign'))!='0.1.0') stop('需要已核验cellAlign 0.1.0')
if(as.character(packageVersion('Seurat'))!='4.4.0') stop('需要已核验Seurat 4.4.0；上游slot接口在Seurat 5已失效')
suppressPackageStartupMessages({
  library(Seurat);library(cellAlign);library(lmtest);library(future)
  library(future.apply);library(dplyr);library(tibble)
})

required <- c('dataset','research_question','seurat','cds','mra','lr_resource','species',
  'expression_scale','normalization_definition','input_provenance','trajectory_provenance',
  'mra_provenance','resource_provenance','native_root','donor','condition')
for(key in required) if(is.null(cfg[[key]])||identical(cfg[[key]],'')) stop('缺少：',key)
if(!cfg$species %in% c('human','mouse')) stop('当前只接受human/mouse的原样基因身份；不自动同源转换')
if(!cfg$expression_scale %in% c('normalized','log_normalized')) stop('TimeTalk需要RNA data槽的非负归一化表达')
winsz <- cfg$winsz %||% .1
if(!is.numeric(winsz)||length(winsz)!=1||winsz<=0||winsz>1) stop('winsz须在(0,1]')
lags <- as.integer(cfg$lags %||% 1L);num_pts <- as.integer(cfg$num_points %||% 200L)
cores <- as.integer(cfg$cores %||% 2L);scc_cutoff <- cfg$scc_cutoff %||% .2
native_cutoff <- cfg$native_granger_cutoff %||% 1e-2;alpha <- cfg$alpha %||% .05
if(is.na(lags)||lags<1||lags>20||is.na(num_pts)||num_pts<30||num_pts>1000||
   is.na(cores)||cores<1||cores>16||!is.numeric(scc_cutoff)||scc_cutoff<0||scc_cutoff>=1||
   !is.numeric(native_cutoff)||native_cutoff<=0||native_cutoff>=1||!is.numeric(alpha)||alpha<=0||alpha>=1)
  stop('lags/num_points/cores/SCC/native P/alpha参数无效')
sample_name <- cfg$sample %||% cfg$condition
sender <- cfg$sender %||% stop('缺少：sender')
receiver <- cfg$receiver %||% stop('缺少：receiver')
if(any(trimws(c(sample_name,sender,receiver,cfg$donor,cfg$condition))=='')) stop('样本、细胞类型、供体和条件不得为空')

native_root <- resolve(cfg$native_root)
analysis_file <- file.path(native_root,'R/analysis.R');utils_file <- file.path(native_root,'R/utils.R')
sha <- function(path) digest::digest(file=path,algo='sha256')
expected <- c(analysis='de0947bda178e9528bb48cddc1c4d0ded33b84162ffecfe3d5e9e4265f7db840',
              utils='d71587a5c082639dcf653dd073588b4a45c81a63920b84bfe26fadc08f4faac4')
if(!file.exists(analysis_file)||!file.exists(utils_file)||sha(analysis_file)!=expected[['analysis']]||sha(utils_file)!=expected[['utils']])
  stop('需要已核验TimeTalk源码 efcf887d285d7c8dafa5e2df7b17aa8280ae9c37')
source(utils_file);source(analysis_file)

paths <- lapply(c('seurat','cds','mra','lr_resource'),function(key) resolve(cfg[[key]]));names(paths)<-c('seurat','cds','mra','lr')
seu <- readRDS(paths$seurat);cds <- readRDS(paths$cds);mra <- readRDS(paths$mra);lr <- read.delim(paths$lr,check.names=FALSE)
if(!inherits(seu,'Seurat')) stop('seurat输入不是Seurat对象')
if(!all(c('CellType','orig.ident')%in%names(seu[[]]))) stop('Seurat元数据须含上游固定字段CellType与orig.ident')
if(anyDuplicated(colnames(seu))||anyDuplicated(rownames(seu))) stop('Seurat细胞或基因身份重复')
if(!all(c('Regulon','group')%in%names(mra))||anyNA(mra[,c('Regulon','group')])) stop('MRA须含完整Regulon/group')
lr_fields <- c('lr_pair','ligand_gene_symbol','receptor_gene_symbol')
if(!all(lr_fields%in%names(lr))||anyNA(lr[,lr_fields])||any(trimws(as.matrix(lr[,lr_fields]))=='')||
   any(grepl('-',lr$ligand_gene_symbol,fixed=TRUE))||any(grepl('-',lr$receptor_gene_symbol,fixed=TRUE)))
  stop('LR资源缺固定字段/身份为空，或基因名含上游不可区分的连字符')
pair_identity <- paste0(lr$ligand_gene_symbol,'-',lr$receptor_gene_symbol)
if(anyDuplicated(pair_identity)) stop('LR配体-受体身份重复，不能依赖上游行名静默合并')

# Monocle3 accessor returns pseudotime only for cells in the current CDS. Reading
# the stored vector directly avoids rerunning trajectory inference and preserves
# the author's already-generated demo trajectory.
cds_attr <- attributes(cds);cds_cells <- rownames(cds_attr$colData)
pt_all <- cds_attr$principal_graph_aux[['UMAP']]$pseudotime
if(is.null(cds_cells)||is.null(pt_all)||is.null(names(pt_all))||!all(cds_cells%in%names(pt_all)))
  stop('CDS缺少带细胞身份的UMAP pseudotime')
pt <- pt_all[cds_cells]
if(!identical(cds_cells,colnames(seu))||any(!is.finite(pt))) stop('CDS与Seurat细胞顺序不完全一致或伪时间非有限')
pseudotime <- function(x,reduction_method='UMAP') {
  a <- attributes(x);cells <- rownames(a$colData);p <- a$principal_graph_aux[[reduction_method]]$pseudotime
  if(is.null(p)||is.null(names(p))||!all(cells%in%names(p))) stop('无法按细胞身份读取伪时间')
  p[cells]
}

meta <- seu[[]]
keep_sender <- meta$orig.ident==sample_name & as.character(meta$CellType)==sender
keep_receiver <- meta$orig.ident==sample_name & as.character(meta$CellType)==receiver
minimum <- as.integer(cfg$min_cells_per_trajectory %||% 3L)
if(is.na(minimum)||minimum<3||sum(keep_sender)<minimum||sum(keep_receiver)<minimum)
  stop('发送与接收轨迹各须至少min_cells_per_trajectory个真实细胞（最低3）')
support_minimum <- as.integer(cfg$minimum_real_cells_for_support %||% 20L)
if(is.na(support_minimum)||support_minimum<3) stop('minimum_real_cells_for_support须至少3')
support_gate <- sum(keep_sender)>=support_minimum && sum(keep_receiver)>=support_minimum
if(length(unique(pt[keep_sender]))<2||length(unique(pt[keep_receiver]))<2) stop('发送或接收轨迹没有可缩放的伪时间变化')

out <- normalizePath(args[2],mustWork=FALSE)
if(file.exists(out)) stop('拒绝覆盖已有输出')
parent <- normalizePath(dirname(out),mustWork=FALSE)
while(parent!='/'){if(file.exists(file.path(parent,'.git'))) stop('真实分析输出必须位于Git仓库外');parent<-dirname(parent)}
dir.create(out,recursive=TRUE)
write_json <- function(value,name) jsonlite::write_json(value,file.path(out,name),auto_unbox=TRUE,pretty=TRUE,na='null',null='null')
write_table <- function(value,name,fields=NULL) {
  value<-as.data.frame(value,check.names=FALSE)
  if(nrow(value)==0&&!is.null(fields)) value<-setNames(as.data.frame(matrix(nrow=0,ncol=length(fields))),fields)
  for(k in names(value)) if(is.numeric(value[[k]])) value[[k]]<-format(value[[k]],digits=17,scientific=TRUE,trim=TRUE)
  write.table(value,file.path(out,name),sep='\t',quote=FALSE,row.names=FALSE,na='NA')
}
add_table <- function(bundle,id,type,rows,definition,...) {
  filename<-paste0(id,'.tsv');write_table(rows,filename)
  bundle$tables[[length(bundle$tables)+1]]<-c(list(id=id,type=type,path=filename,sha256=sha(file.path(out,filename)),value_definition=definition),list(...))
  bundle
}
write_json(cfg,'run_config.json')
write_table(data.frame(cell=cds_cells,pseudotime=as.numeric(pt)),'pseudotime.tsv')

data_mat <- GetAssayData(object=seu,slot='data',assay='RNA')
values <- if(inherits(data_mat,'sparseMatrix')) data_mat@x else as.vector(as.matrix(data_mat))
if(any(!is.finite(values))||any(values<0)||!any(values>0)) stop('RNA data表达须有限、非负且含信号')
measured <- lr$ligand_gene_symbol%in%rownames(data_mat)&lr$receptor_gene_symbol%in%rownames(data_mat)
lr_use <- lr[measured,,drop=FALSE];pair_use <- pair_identity[measured]
if(nrow(lr_use)==0) stop('LR资源中没有两端均实测的候选')
if(nrow(lr_use)>(cfg$max_lr_pairs %||% 10000L)) stop('实测LR超过max_lr_pairs，不静默截断')
tf_genes <- unique(as.character(mra$Regulon[mra$group==receiver]))
if(length(tf_genes)==0||any(!tf_genes%in%rownames(data_mat))) stop('接收细胞MRA没有TF，或部分TF未在表达矩阵中实测')

scale_pt <- function(x) (x-min(x))/(max(x)-min(x))
sender_ids <- rownames(meta)[keep_sender][order(pt[keep_sender])]
receiver_ids <- rownames(meta)[keep_receiver][order(pt[keep_receiver])]
sender_pt <- scale_pt(pt[sender_ids]);names(sender_pt)<-sender_ids
receiver_pt <- scale_pt(pt[receiver_ids]);names(receiver_pt)<-receiver_ids
inter_sender <- cellAlign::scaleInterpolate(cellAlign::interWeights(data_mat[,sender_ids,drop=FALSE],sender_pt,winsz,num_pts))
inter_receiver <- cellAlign::scaleInterpolate(cellAlign::interWeights(data_mat[,receiver_ids,drop=FALSE],receiver_pt,winsz,num_pts))
sender_scaled <- myRemoveNA(inter_sender$scaledData);receiver_scaled <- myRemoveNA(inter_receiver$scaledData)
if(any(!is.finite(sender_scaled))||any(!is.finite(receiver_scaled))) stop('插值缩放产生非有限值，不能补零交付')

actual_pcc <- vapply(seq_len(nrow(lr_use)),function(i) cor(sender_scaled[lr_use$ligand_gene_symbol[i],],receiver_scaled[lr_use$receptor_gene_symbol[i],],method='pearson'),numeric(1))
actual_scc <- vapply(seq_len(nrow(lr_use)),function(i) cor(sender_scaled[lr_use$ligand_gene_symbol[i],],receiver_scaled[lr_use$receptor_gene_symbol[i],],method='spearman'),numeric(1))
actual_pcc[is.na(actual_pcc)]<-0;actual_scc[is.na(actual_scc)]<-0
selection <- order(-actual_scc,seq_along(actual_scc));selected_pairs <- pair_use[selection][abs(actual_scc[selection])>scc_cutoff]
cor_table <- data.frame(sample=sample_name,source=sender,target=receiver,ligand=lr_use$ligand_gene_symbol,
  receptor=lr_use$receptor_gene_symbol,interaction=pair_use,score=actual_scc,tested=TRUE,
  supported=abs(actual_scc)>scc_cutoff,p_value=NA_real_,q_value=NA_real_,pearson_actual=actual_pcc,
  spearman_actual=actual_scc,upstream_PCC_field=actual_scc,upstream_rank=rank(-actual_scc,ties.method='first'))
write_table(cor_table[,c('interaction','ligand','receptor','pearson_actual','spearman_actual','upstream_PCC_field','upstream_rank','supported')],'lr_interpolation_correlations_full.tsv')

native <- data.frame(LR=character(),L=character(),R=character(),TF=character(),PCC=numeric(),SCC=numeric(),
  LRtoTF=numeric(),TFtoLR=numeric(),cell.L=character(),cell.R=character(),category=character())
if(length(selected_pairs)>0) {
  native <- RunTimeTalk(tmp.cds=cds,tmp.seu=seu,tmp.ident.1=sender,tmp.ident.2=receiver,LRpairs.df=lr,
    tmp.mra.res=mra,tmp.orig.ident=sample_name,tmp.lags=lags,tmp.winsz=winsz,numPts=num_pts,tmp.cores=cores,
    tmp.SCC.cutoff=scc_cutoff,tmp.granger.cutoff=native_cutoff)
  if(!is.data.frame(native)||nrow(native)!=length(selected_pairs)*length(tf_genes)) stop('TimeTalk原生输出规模未通过契约')
  if(!setequal(as.character(unique(native$LR)),as.character(selected_pairs))) stop('TimeTalk原生LR身份未通过契约')
  if(!setequal(as.character(unique(native$TF)),as.character(tf_genes))) stop('TimeTalk原生TF身份未通过契约')
  if(any(!is.finite(as.matrix(native[,c('PCC','SCC','LRtoTF','TFtoLR')])))) stop('TimeTalk原生输出含非有限数值')
}
saveRDS(native,file.path(out,'native_timetalk_result.rds'))

if(nrow(native)>0) {
  native$q_LRtoTF <- p.adjust(native$LRtoTF,method='BH')
  native$q_TFtoLR <- p.adjust(native$TFtoLR,method='BH')
  native$p_any_direction <- pmin(1,2*pmin(native$LRtoTF,native$TFtoLR))
  native$q_any_direction <- p.adjust(native$p_any_direction,method='BH')
  native$adjusted_screen <- native$q_any_direction<alpha
  native$supported_adapter <- native$adjusted_screen & support_gate
  native$support_gate <- if(support_gate) 'passed_minimum_real_cells' else 'exploratory_only_insufficient_real_cells'
  native$correction_scope <- paste0('BH over all ',nrow(native),' tested LR-TF rows after within-row two-direction Bonferroni')
}
write_table(native,'granger_lr_tf_full.tsv')

# Deterministically audit native values against direct calculations on the same
# interpolated profiles. This checks the wrapper without silently changing the algorithm.
audit_n <- min(nrow(native),as.integer(cfg$equivalence_audit_rows %||% 24L));audit_error <- list(rows=audit_n)
if(audit_n>0) {
  idx <- unique(round(seq(1,nrow(native),length.out=audit_n)))
  errors <- lapply(idx,function(i) {
    z<-native[i,];signal<-sqrt(sender_scaled[z$L,]*receiver_scaled[z$R,]);tf<-receiver_scaled[z$TF,]
    p1<-tryCatch(lmtest::grangertest(signal,tf,order=lags)$`Pr(>F)`[2],error=function(e)1)
    p2<-tryCatch(lmtest::grangertest(tf,signal,order=lags)$`Pr(>F)`[2],error=function(e)1)
    c(PCC=abs((ifelse(is.na(cor(signal,tf,method='pearson')),0,cor(signal,tf,method='pearson')))-z$PCC),
      SCC=abs((ifelse(is.na(cor(signal,tf,method='spearman')),0,cor(signal,tf,method='spearman')))-z$SCC),
      LRtoTF=abs(p1-z$LRtoTF),TFtoLR=abs(p2-z$TFtoLR))
  })
  err <- do.call(rbind,errors);audit_error$max_abs_error<-as.list(apply(err,2,max));audit_error$indices<-idx
  if(any(err>1e-12)) stop('原生TimeTalk结果与独立直接复算不一致')
}

bundle <- list(schema_version=2,dataset=cfg$dataset,method='TimeTalk',method_version='0.0.310.316',
  implementation='native_RunTimeTalk_with_explicit_multiplicity_adapter',tables=list(),
  provenance=list(input_sha256=lapply(paths,sha),pseudotime_sha256=sha(file.path(out,'pseudotime.tsv')),
    parameters=cfg,versions=list(TimeTalk='0.0.310.316',cellAlign=as.character(packageVersion('cellAlign')),
      Seurat=as.character(packageVersion('Seurat')),lmtest=as.character(packageVersion('lmtest'))),
    upstream=list(url='https://github.com/ChengLiLab/TimeTalk',commit='efcf887d285d7c8dafa5e2df7b17aa8280ae9c37',license='GPL (>= 3)'),
    cellAlign_dependency=list(url='https://github.com/shenorrLabTRDF/cellAlign',commit='30fb085bcf45280e1706450e9cfcba3728cda6d8',version='0.1.0',license='Academic and educational use; commercial use requires a separate license. Adapter does not redistribute cellAlign.'),
    upstream_defects=c('RunTimeTalk computes Pearson then Spearman LR lists but writes the Spearman list into both PCC and SCC columns. Native LR selection still uses the actual Spearman list; this adapter preserves the native selection and separately exports actual Pearson.','Native PASS uses either unadjusted directional Granger P below the cutoff. Adapter-supported evidence uses a separately labelled two-direction Bonferroni P followed by BH across all tested LR-TF rows.','Upstream Reduce(rbind, ...) fails when no LR passes the SCC cutoff; adapter returns a valid negative result bundle for that case.'),
    inference_scope='Granger tests are run on smoothed, interpolated pseudotime profiles from one selected sender/receiver trajectory pair. Interpolated points are not independent biological replicates; results are potential temporal regulatory associations, not experimental causality or donor-level inference.',
    support_gate=list(minimum_real_cells_per_trajectory=support_minimum,sender_real_cells=sum(keep_sender),receiver_real_cells=sum(keep_receiver),passed=support_gate,
      meaning='Adjusted P/q values remain available for algorithm reproduction. supported is forced false when either real trajectory has fewer cells than the prespecified gate; interpolated points never replace real cells.'),
    equivalence_audit=audit_error))

bundle <- add_table(bundle,'trajectory_lr_correlations','lr_edges',cor_table,
  'TimeTalk selection-stage Spearman correlation between cellAlign-scaled sender ligand and receiver receptor profiles. The signed coefficient is not additive; supported means the prespecified absolute SCC threshold only, without a P value.',
  direction='two_sided_absolute_threshold',additive=FALSE,value_kind='native_trajectory_correlation',axis_label='Spearman correlation along pseudotime',statistical_unit='one smoothed sender/receiver trajectory pair')

granger_rows <- data.frame()
molecular <- data.frame()
profile_rows <- data.frame()
if(nrow(native)>0) {
  split_native <- split(seq_len(nrow(native)),native$LR)
  best_idx <- vapply(split_native,function(ii) ii[order(native$q_any_direction[ii],native$p_any_direction[ii],native$TF[ii])][1],integer(1))
  best <- native[best_idx,,drop=FALSE]
  granger_rows <- data.frame(sample=sample_name,source=sender,target=receiver,ligand=best$L,receptor=best$R,
    interaction=paste0(best$LR,' | TF ',best$TF),score=-log10(pmax(best$q_any_direction,.Machine$double.xmin)),
    tested=TRUE,supported=best$q_any_direction<alpha & support_gate,p_value=best$p_any_direction,q_value=best$q_any_direction,
    best_tf=best$TF,native_pass=best$category=='PASS',adjusted_screen=best$q_any_direction<alpha,support_gate=best$support_gate)
  molecular <- data.frame(source=native$LR,target=native$TF,source_type='ligand-receptor interaction',target_type='TF',
    value=-log10(pmax(native$q_any_direction,.Machine$double.xmin)),p_value=native$p_any_direction,q_value=native$q_any_direction,
    supported=native$supported_adapter,native_pass=native$category=='PASS',adjusted_screen=native$adjusted_screen,support_gate=native$support_gate)
  display_n <- as.integer(cfg$trajectory_display %||% 3L)
  if(is.na(display_n)||display_n<1||display_n>12) stop('trajectory_display须为1..12')
  chosen <- best[order(best$q_any_direction,best$p_any_direction,best$LR,best$TF),,drop=FALSE]
  chosen <- head(chosen,display_n)
  grid <- inter_sender$traj
  append_profile <- function(feature,values) data.frame(sample=sample_name,donor=cfg$donor,feature=feature,time=grid,value=as.numeric(values))
  profiles <- lapply(seq_len(nrow(chosen)),function(i){z<-chosen[i,];list(
    append_profile(paste0(z$LR,' | sender ligand ',z$L),sender_scaled[z$L,]),
    append_profile(paste0(z$LR,' | receiver receptor ',z$R),receiver_scaled[z$R,]),
    append_profile(paste0(z$LR,' | interaction sqrt(L×R)'),sqrt(sender_scaled[z$L,]*receiver_scaled[z$R,])),
    append_profile(paste0(z$LR,' → ',z$TF,' | receiver TF'),receiver_scaled[z$TF,]))})
  profile_rows <- do.call(rbind,unlist(profiles,recursive=FALSE))
}
if(nrow(granger_rows)==0) granger_rows<-data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),interaction=character(),score=numeric(),tested=logical(),supported=logical(),p_value=numeric(),q_value=numeric())
if(nrow(molecular)==0) molecular<-data.frame(source=character(),target=character(),source_type=character(),target_type=character(),value=numeric())
if(nrow(profile_rows)==0) profile_rows<-data.frame(sample=character(),donor=character(),feature=character(),time=numeric(),value=numeric())
bundle <- add_table(bundle,'granger_lr_tf_summary','lr_edges',granger_rows,
  'For each selected LR, the row reports the TF with the smallest adapter q. Score is -log10(q); p_any_direction is Bonferroni across the two tested directions and q is BH across all LR-TF rows. Native PASS remains a separate raw-P field. The supported flag additionally requires the prespecified minimum number of real cells in both trajectories; interpolated positions cannot satisfy that gate.',
  direction='higher',additive=FALSE,value_kind='adjusted_evidence_strength',axis_label='Best TF −log10(q)',alpha=alpha,statistical_unit='one smoothed sender/receiver trajectory pair')
bundle <- add_table(bundle,'granger_molecular_links','molecular_links',molecular,
  'LR-interaction to receiver-TF links weighted by -log10(adapter q). This is adjusted temporal association evidence on interpolated pseudotime profiles and is not an additive communication flux or experimental causal effect.',
  direction='higher',additive=FALSE,value_kind='adjusted_evidence_strength',axis_label='−log10(q)',alpha=alpha)
bundle <- add_table(bundle,'selected_timetalk_profiles','time_series',profile_rows,
  'cellAlign-scaled ligand, receptor, geometric-mean interaction signal and receiver TF profiles for candidates selected only after complete adjusted testing. Curves contain interpolated pseudotime points from the stated real cells; points are not biological replicates.',
  time_kind='pseudotime',time_unit='cellAlign grid on 0..1',selection='First trajectory_display LR-TF rows ordered by complete adapter q, P and stable identity')
write_json(bundle,'bundle.json')
objects <- list(native_timetalk_result.rds=sha(file.path(out,'native_timetalk_result.rds')),
  lr_interpolation_correlations_full.tsv=sha(file.path(out,'lr_interpolation_correlations_full.tsv')),
  granger_lr_tf_full.tsv=sha(file.path(out,'granger_lr_tf_full.tsv')))
signature <- digest::digest(list(inputs=lapply(paths,sha),source=expected,parameters=cfg,versions=bundle$provenance$versions),algo='sha256')
status <- if(!nrow(native)) 'completed_negative_no_lr_above_scc_cutoff' else if(support_gate) 'completed_native_with_separate_multiplicity_adapter' else 'completed_native_exploratory_insufficient_real_cells_for_support'
write_json(list(signature=signature,status=status,objects=objects,equivalence_audit=audit_error),'run_metadata.json')
