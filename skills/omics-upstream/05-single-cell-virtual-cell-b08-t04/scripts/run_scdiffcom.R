#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE, warn=1)
`%||%` <- function(x,y) if(is.null(x)) y else x
a <- commandArgs(TRUE)
if(length(a)!=2) stop("用法：Rscript run_scdiffcom.R 配置.json 新输出目录")
for(p in c("Seurat", "scDiffCom", "jsonlite", "digest", "Matrix"))
  if(!requireNamespace(p,quietly=TRUE)) stop("缺少原生依赖：",p)
suppressPackageStartupMessages(library(Seurat))
suppressPackageStartupMessages(library(scDiffCom))
if(as.character(packageVersion("scDiffCom"))!="1.2.0") stop("仅核验scDiffCom 1.2.0原生接口")
cp <- normalizePath(a[1]); cfg <- jsonlite::read_json(cp,simplifyVector=TRUE)
for(k in c("dataset","research_question","input","species","normalization_definition","condition_key","reference","comparison","analysis_unit"))
  if(is.null(cfg[[k]])) stop("缺少配置：",k)
if(!cfg$species %in% c("human","mouse","rat")) stop("原生数据库仅支持human/mouse/rat")
if(cfg$analysis_unit!="pooled_cells") stop("此原生scDiffCom接口使用细胞置换，不支持供体混合模型；须明确pooled_cells")
if(!is.null(cfg$covariates)||isTRUE(cfg$paired)) stop("原生scDiffCom此分支没有供体配对/协变量接口，不能忽略研究设计")
resolve <- function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
input <- resolve(cfg$input); x <- readRDS(input)
if(!inherits(x,"Seurat")) stop("需要已有且表达语义明确的Seurat对象，不自动重建或归一化矩阵")
assay <- cfg$assay %||% "RNA"; layer <- cfg$layer %||% "data"; ct <- cfg$cell_type_key %||% "cell_type"
if(layer!="data"||cfg$expression_scale!="log_normalized") stop("此分支要求data层为自然log1p归一化表达；原生按log_scale=FALSE还原线性表达")
meta <- x@meta.data
if(!all(c(ct,cfg$condition_key) %in% names(meta))||anyNA(meta[,c(ct,cfg$condition_key)])||any(trimws(as.matrix(meta[,c(ct,cfg$condition_key)]))=="")) stop("真实细胞类型和条件元数据不完整")
conditions <- c(cfg$reference,cfg$comparison)
if(length(unique(conditions))!=2||!setequal(unique(meta[[cfg$condition_key]]),conditions)) stop("需恰好两个实际条件，明确reference→comparison")
expr <- SeuratObject::GetAssayData(x,assay=assay,layer=layer)
v <- if(inherits(expr,"sparseMatrix")) expr@x else as.vector(expr)
if(any(!is.finite(v))||any(v<0)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))) stop("表达值或身份无效")
iterations <- as.integer(cfg$iterations %||% 1000L)
if(is.na(iterations)||iterations<100) stop("至少100次原生置换；正式分析按精度需要增加")
hash <- function(p) digest::digest(file=p,algo="sha256")
if(file.exists(a[2])) stop("拒绝覆盖已有结果")
parent <- normalizePath(dirname(a[2]),mustWork=FALSE)
while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("真实输出必须在Git外");parent<-dirname(parent)}
dir.create(a[2],recursive=TRUE); out<-normalizePath(a[2])
wj <- function(v,n) jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt <- function(v,n) write.table(as.data.frame(v),file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
db <- get(paste0("LRI_",cfg$species),asNamespace("scDiffCom"));saveRDS(db,file.path(out,"native_database.rds"))
args <- list(LRI_species=cfg$species,seurat_celltype_id=ct,
  seurat_condition_id=list(column_name=cfg$condition_key,cond1_name=cfg$reference,cond2_name=cfg$comparison),
  iterations=iterations,seurat_assay=assay,seurat_layer=layer,log_scale=FALSE,score_type="geometric_mean",
  threshold_min_cells=as.integer(cfg$min_cells %||% 5L),threshold_pct=cfg$detection_threshold %||% .1,
  threshold_quantile_score=cfg$score_quantile %||% .2,threshold_p_value_specificity=cfg$specificity_fdr %||% .05,
  threshold_p_value_de=cfg$differential_fdr %||% .05,threshold_logfc=cfg$logfc_threshold %||% log(1.5),
  return_distributions=cfg$return_distributions %||% TRUE,seed=as.integer(cfg$seed %||% 42L),verbose=TRUE)
signature <- digest::digest(list(input=hash(input),database=hash(file.path(out,"native_database.rds")),version="1.2.0",args=args),algo="sha256")
wj(cfg,"run_config.json")
if(!is.null(cfg$reuse_directory)){
  previous<-resolve(cfg$reuse_directory);info<-jsonlite::read_json(file.path(previous,"run_metadata.json"),simplifyVector=TRUE)
  if(!identical(info$signature,signature)||!identical(info$native_sha256,hash(file.path(previous,"native.rds")))) stop("输入、数据库、参数或原生对象摘要变化，不能复用")
  native<-readRDS(file.path(previous,"native.rds"))
  if(!inherits(native,"scDiffCom")) stop("复用对象类型不符")
  file.copy(file.path(previous,"native.rds"),file.path(out,"native.rds"))
}else{
  native<-do.call(scDiffCom::run_interaction_analysis,c(list(seurat_object=x),args))
  saveRDS(native,file.path(out,"native.rds"))
}
wj(list(signature=signature,native_sha256=hash(file.path(out,"native.rds"))),"run_metadata.json")
raw <- as.data.frame(scDiffCom::GetTableCCI(native,type="raw",simplified=FALSE))
det <- as.data.frame(scDiffCom::GetTableCCI(native,type="detected",simplified=FALSE))
wt(raw,"native_raw.tsv");if(ncol(det)) wt(det,"native_detected.tsv")
key <- function(d) paste(d$EMITTER_CELLTYPE,d$RECEIVER_CELLTYPE,d$LRI,sep="\r")
if(anyDuplicated(key(raw))) stop("原生候选身份重复")
index <- if(nrow(det)) match(key(raw),key(det)) else rep(NA_integer_,nrow(raw))
eligible <- raw[[paste0("IS_CCI_EXPRESSED_",conditions[1])]]|raw[[paste0("IS_CCI_EXPRESSED_",conditions[2])]]
# The native filtering function adjusts the full expressed union before score
# and significance selection. Retain that same family for raw-table export,
# and verify equality against every retained native BH value.
qs <- list()
for(suffix in c(conditions,"DE")){
  q<-rep(NA_real_,nrow(raw));q[eligible]<-p.adjust(raw[[paste0("P_VALUE_",suffix)]][eligible],method="BH")
  if(nrow(det)){
    j<-match(key(det),key(raw));expected<-det[[paste0("BH_P_VALUE_",suffix)]]
    if(any(abs(q[j]-expected)>1e-12,na.rm=TRUE)) stop("全候选BH导出与原生保留表不一致")
  }
  qs[[suffix]]<-q
}
complex_name <- function(prefix) apply(raw[,grep(paste0("^",prefix,"_[0-9]+$"),names(raw)),drop=FALSE],1,function(v) paste(v[!is.na(v)&nzchar(v)],collapse="_"))
lr <- lapply(conditions,function(cond){
  supported<-rep(FALSE,nrow(raw));matched<-which(!is.na(index))
  supported[matched]<-det[[paste0("IS_CCI_DETECTED_",cond)]][index[matched]]
  data.frame(sample=paste0("pooled_cells:",cond),condition=cond,analysis_unit="pooled_cells",
    source=raw$EMITTER_CELLTYPE,target=raw$RECEIVER_CELLTYPE,ligand=complex_name("LIGAND"),receptor=complex_name("RECEPTOR"),interaction=raw$LRI,
    score=raw[[paste0("CCI_SCORE_",cond)]],p_value=ifelse(eligible,raw[[paste0("P_VALUE_",cond)]],NA_real_),q_value=qs[[cond]],
    tested=eligible,condition_expressed=raw[[paste0("IS_CCI_EXPRESSED_",cond)]],supported=supported)
})
bundle <- list(schema_version=2,dataset=cfg$dataset,method="scDiffCom",method_version="1.2.0",implementation="native",
  provenance=list(input_sha256=hash(input),database_sha256=hash(file.path(out,"native_database.rds")),native_sha256=hash(file.path(out,"native.rds")),
    parameters=cfg,native_parameters=scDiffCom::GetParameters(native),test_unit="细胞条件/群标签置换；没有独立供体推断，原生示例若缺供体ID不能补造",
    score_definition="原生geometric_mean，data层expm1还原后在非log尺度推断；异源复合物使用原生全部亚基处理",
    multiplicity="原生IS_CCI_EXPRESSED两条件并集，BH先于score/specification筛选；保留表逐值校验",
    raw_scope="所有原生潜在候选与未检验P=1哨兵保存在native_raw.tsv；规范表外部未检验P/q记缺失"),tables=list())
add <- function(id,type,rows,definition,...){
  wt(rows,paste0(id,".tsv"));bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=paste0(id,".tsv"),sha256=hash(file.path(out,paste0(id,".tsv"))),value_definition=definition),list(...))
}
add("lr_edges","lr_edges",do.call(rbind,lr),"scDiffCom原生CCI得分；支持严格复用原生IS_CCI_DETECTED，包含表达资格、分数分位和特异性FDR；细胞池化不等于供体样本",value_kind="native_score",additive=FALSE,axis_label="scDiffCom CCI score")
counts<-table(meta[[cfg$condition_key]])
regulation<-rep("NOT_DETECTED",nrow(raw));matched<-which(!is.na(index));if(length(matched)) regulation[matched]<-det$REGULATION[index[matched]]
effect<-data.frame(feature=paste(raw$EMITTER_CELLTYPE,raw$RECEIVER_CELLTYPE,raw$LRI,sep=" | "),value=ifelse(is.finite(raw$LOGFC),raw$LOGFC,NA_real_),
  p_value=ifelse(eligible,raw$P_VALUE_DE,NA_real_),q_value=qs$DE,n_reference=as.integer(counts[conditions[1]]),n_comparison=as.integer(counts[conditions[2]]),
  native_effect_status=ifelse(is.finite(raw$LOGFC),"finite",ifelse(raw$LOGFC>0,"positive_infinite","negative_infinite")),
  native_detected=!is.na(index),native_regulation=regulation)
add("condition_effects","effect_summary",effect,"原生CCI自然对数fold change，comparison相对reference；P为细胞条件置换，BH为完整表达并集；显著差异还须满足原生检测及效应阈值，见native_regulation",
  contrast=paste(conditions[2],"vs",conditions[1]),statistical_unit="pooled cells; n为条件内细胞总数，不是供体数",test_definition="原生scDiffCom细胞条件置换及表达并集BH；原生无穷效应保留状态与原始表，有限图不加伪计数",axis_label="Native log fold change (cell pools)",alpha=args$threshold_p_value_de,q_plot_floor=1/iterations)
# Native ORA uses detected CCIs as its universe, not a gene-set background.
# Preserve all raw category statistics including infinite odds ratios; finite
# canonical matrices separately display odds ratio and corrected evidence.
ora <- scDiffCom::GetTableORA(native,categories="all",simplified=FALSE)
saveRDS(ora,file.path(out,"native_ora.rds"))
for(category in intersect(c("GO_TERMS","KEGG_PWS"),names(ora))){
  d<-as.data.frame(ora[[category]]);if(!nrow(d)) next
  wt(d,paste0("native_ora_",tolower(category),".tsv"))
  names_row<-as.character(d[[1]])
  for(metric in c("OR","BH_P_VALUE")){
    values<-lapply(c("UP","DOWN","FLAT","DIFF"),function(direction){v<-d[[paste0(metric,"_",direction)]];data.frame(row=names_row,column=direction,value=ifelse(is.finite(v),v,NA_real_))})
    add(paste0("ora_",tolower(category),"_",tolower(metric)),"matrix",do.call(rbind,values),
      paste0("原生scDiffCom ",category," ",metric,"；背景为检测到的CCI，非基因富集；无穷原生比值在原始表保留、此有限绘图表记缺失；不二次计算P"),
      axis_label=if(metric=="OR") "Native CCI odds ratio" else "Native adjusted P",value_kind=if(metric=="OR") "native_score" else "p_value",
      display_top_rows=20L,direction=if(metric=="OR") "higher" else "lower",figure_role="interaction_enrichment")
  }
}
wj(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
