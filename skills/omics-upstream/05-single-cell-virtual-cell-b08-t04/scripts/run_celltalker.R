#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"CellTalker","celltalker","0.0.7.9000");cfg<-c$cfg
if(!requireNamespace("Seurat",quietly=TRUE)) stop("缺少Seurat")
if(as.character(packageVersion("Seurat"))!="4.4.0"||as.character(packageVersion("SeuratObject"))!="4.1.4") stop("此原生版本需要隔离的Seurat4.4.0/SeuratObject4.1.4环境")
suppressPackageStartupMessages(library(Seurat))
raw<-readRDS(c$input)$counts
if(is.null(raw)||!identical(dimnames(raw),dimnames(c$expr))) stop("输入另须真实counts矩阵，与expression基因/细胞次序完全一致")
v<-if(inherits(raw,"sparseMatrix")) raw@x else as.vector(as.matrix(raw))
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("counts必须为真实非负整数，不从log归一化数据反推")
for(k in c("min_total_counts","max_total_counts","count_filter_rationale")) if(is.null(cfg[[k]])) stop("需明确全样本总counts过滤及依据：",k)
lo<-cfg$min_total_counts;hi<-cfg$max_total_counts
if(!is.numeric(lo)||!is.numeric(hi)||length(lo)!=1||length(hi)!=1||!is.finite(lo)||!is.finite(hi)||lo<0||hi<=lo) stop("总counts上下限需有限、非负且递增")
scrambles<-as.integer(cfg$scrambles %||% 1000L)
if(is.na(scrambles)||scrambles<100) stop("原生随机化至少100次，正式任务按精度要求增加")
resource_env<-new.env(parent=emptyenv())
utils::data("ramilowski_pairs",package="celltalker",envir=resource_env)
db<-resource_env$ramilowski_pairs
if(is.null(db)||!all(c("ligand","receptor") %in% names(db))) stop("原生ramilowski_pairs资源缺失或结构不兼容")
saveRDS(db,file.path(c$out,"native_database.rds"))
keys<-paste(db$ligand,db$receptor,sep="_")
if(anyDuplicated(keys)) stop("原生LR资源存在身份歧义")
c$start_cache(c$hash(file.path(c$out,"native_database.rds")),list(min_total_counts=lo,max_total_counts=hi,min_cells=c$minimum,scrambles=scrambles,seed=cfg$seed %||% 42))
c$bundle$provenance$upstream<-list(commit="6edd610bf558bb1777590f8a6b02711ef7d0fc47",url="https://github.com/arc85/celltalker",license="MIT")
c$bundle$provenance$database_sha256<-c$hash(file.path(c$out,"native_database.rds"))
c$bundle$provenance$null_model<-"原生随机打乱同一LR的细胞类型组合、以其均值和标准差计算正态上尾P；不是细胞标签置换或供体条件检验。原生零null均值改为0.1仅影响interact_ratio，原始对象保留"
c$bundle$provenance$multiplicity<-"在每个实际样本全部有限原生P的候选族追加BH，先校正后筛选；支持还要求双端点正表达。原生没有联合BH列，不把新增BH冒充原生字段"
c$bundle$provenance$filtering<-"原生全样本总counts严格大于下限且小于上限；阈值影响资格并依赖细胞数量，必须随数据记录依据；不足群、缺失亚型及退化null不填零"
allrows<-list()
for(si in seq_along(unique(c$meta$sample))){
  sample<-unique(c$meta$sample)[si];m<-c$sample_meta(sample);types<-unique(m$cell_type);ids<-sprintf("CT%03d",seq_along(types));inverse<-setNames(types,ids)
  native<-c$native(si,sample,function(){
    count_matrix<-as(raw[,rownames(m),drop=FALSE],"dgCMatrix")
    data_matrix<-as(c$expr[,rownames(m),drop=FALSE],"dgCMatrix")
    feature_names<-gsub("[_|]","-",rownames(data_matrix))
    if(anyDuplicated(feature_names)||any(rownames(data_matrix)[feature_names!=rownames(data_matrix)] %in% c(db$ligand,db$receptor))) stop("Seurat特征名转换造成冲突或改变LR资源身份")
    feature_map<-data.frame(original=rownames(data_matrix),native=feature_names)
    rownames(count_matrix)<-rownames(data_matrix)<-feature_names
    assay<-SeuratObject::CreateAssayObject(counts=count_matrix);assay<-SeuratObject::SetAssayData(assay,slot="data",new.data=data_matrix)
    meta<-m;meta$cell_type<-ids[match(meta$cell_type,types)]
    object<-SeuratObject::CreateSeuratObject(counts=assay,meta.data=meta)
    set.seed(cfg$seed %||% 42)
    result<-celltalker::celltalk(object,metadata_grouping="cell_type",ligand_receptor_pairs=db,number_cells_required=c$minimum-1L,min_expression=lo,max_expression=hi,scramble_times=scrambles)
    list(result=result,metadata=m,identity_map=data.frame(native=ids,cell_type=types),feature_map=feature_map)
  })
  d<-as.data.frame(native$result);c$wt(d,paste0("native_candidates_",si,".tsv"));c$wt(native$identity_map,paste0("identity_map_",si,".tsv"))
  if(!nrow(d)) next
  index<-match(d$interaction,keys)
  if(anyNA(index)||!all(d$cell_type1 %in% ids)||!all(d$cell_type2 %in% ids)) stop("原生LR/细胞群身份不能从实际资源恢复")
  means<-vapply(types,function(t) Matrix::rowMeans(c$expr[,rownames(m)[m$cell_type==t],drop=FALSE]),numeric(nrow(c$expr)))
  rownames(means)<-rownames(c$expr);colnames(means)<-ids
  l<-means[cbind(match(db$ligand[index],rownames(means)),match(d$cell_type1,ids))]
  re<-means[cbind(match(db$receptor[index],rownames(means)),match(d$cell_type2,ids))]
  if(any(abs(d$value-(l+re)/2)>1e-10,na.rm=TRUE)) stop("原生候选均值与端点不一致")
  tested<-is.finite(d$p_val)&is.finite(d$value)&is.finite(d$scram_sd)&d$scram_sd>0
  q<-rep(NA_real_,nrow(d));q[tested]<-p.adjust(d$p_val[tested],method="BH")
  allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=unname(inverse[d$cell_type1]),target=unname(inverse[d$cell_type2]),
    ligand=db$ligand[index],receptor=db$receptor[index],interaction=d$interaction,ligand_identity=paste0("gene:",db$ligand[index]),receptor_identity=paste0("gene:",db$receptor[index]),
    score=ifelse(is.finite(d$value),d$value,NA_real_),p_value=ifelse(tested,d$p_val,NA_real_),q_value=q,tested=tested,supported=tested&!is.na(q)&q<.05&l>0&re>0,
    ligand_mean=l,receptor_mean=re,native_interact_ratio=ifelse(is.finite(d$interact_ratio),d$interact_ratio,NA_real_))
}
rows<-if(length(allrows)) do.call(rbind,allrows) else data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),tested=logical(),supported=logical())
c$add("lr_edges","lr_edges",rows,"CellTalker原生双端点均值；原生P、追加全有限候选BH与双端点正表达支持分开记录。不是供体条件检验，零方差null未检验",value_kind="native_score",additive=FALSE,axis_label="CellTalker mean expression")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
