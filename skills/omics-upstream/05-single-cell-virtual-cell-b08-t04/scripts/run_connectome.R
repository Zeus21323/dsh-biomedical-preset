#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"Connectome","Connectome","1.0.1");cfg<-c$cfg
if(as.character(packageVersion("Seurat"))!="4.4.0"||as.character(packageVersion("SeuratObject"))!="4.1.4") stop("此原生版本需要隔离的Seurat4.4.0/SeuratObject4.1.4环境")
suppressPackageStartupMessages(library(Seurat))
if(cfg$expression_scale!="log_normalized") stop("原生AverageExpression假设自然log1p归一化data；不能直接输入TPM或其他尺度")
raw<-readRDS(c$input)$counts
if(is.null(raw)||!identical(dimnames(raw),dimnames(c$expr))) stop("需要真实counts与expression完全对齐以计算表达比例")
v<-if(inherits(raw,"sparseMatrix")) raw@x else as.vector(as.matrix(raw))
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("counts必须真实非负整数")
pct<-cfg$min_expression_fraction %||% .1;z<-cfg$min_endpoint_z %||% .25
if(!is.numeric(pct)||length(pct)!=1||!is.finite(pct)||pct<0||pct>=1||!is.numeric(z)||length(z)!=1||!is.finite(z)) stop("表达比例阈值应在[0,1)，端点z阈值应有限")
putative<-cfg$include_putative %||% TRUE
if(!is.logical(putative)||length(putative)!=1||is.na(putative)) stop("include_putative必须JSON布尔值")
db<-Connectome::ncomms8866_human;saveRDS(db,file.path(c$out,"native_database.rds"))
db_use<-db[db$Pair.Evidence %in% if(putative) c("literature supported","putative") else "literature supported",]
if(anyDuplicated(paste(db_use$Ligand.ApprovedSymbol,db_use$Receptor.ApprovedSymbol,sep="\r"))) stop("原生资源存在重复LR身份")
genes<-union(db_use$Ligand.ApprovedSymbol,db_use$Receptor.ApprovedSymbol)
c$start_cache(c$hash(file.path(c$out,"native_database.rds")),list(min_cells=c$minimum,min_expression_fraction=pct,min_endpoint_z=z,include_putative=putative,Seurat="4.4.0",SeuratObject="4.1.4",norm_weight="product",scale_weight="mean"))
c$bundle$provenance$upstream<-list(commit="57c44b1a2cde4521c6192da3570cb215370eb0b5",url="https://github.com/msraredon/Connectome",license="GPL-3")
c$bundle$provenance$database_sha256<-c$hash(file.path(c$out,"native_database.rds"))
c$bundle$provenance$inference<-"每实际样本用原生ScaleData在完整细胞背景内缩放LR基因，再CreateConnectome。weight_norm为两端log1p(平均expm1表达)的乘积；weight_sc为两端平均z的均值，可能有负值，另列保留。未开启端点marker P，不存在LR联合P"
c$bundle$provenance$support<-"原生FilterConnectome要求两端表达细胞比例严格大于min_expression_fraction、两端z严格大于min_endpoint_z并移除缺测；另要求weight_norm>0。支持是表达与相对特异性筛选，不是FDR显著"
allrows<-list()
for(si in seq_along(unique(c$meta$sample))){
  sample<-unique(c$meta$sample)[si];m<-c$sample_meta(sample);types<-unique(m$cell_type);ids<-sprintf("CT%03d",seq_along(types));inverse<-setNames(types,ids)
  native<-c$native(si,sample,function(){
    counts<-as(raw[,rownames(m),drop=FALSE],"dgCMatrix");data<-as(c$expr[,rownames(m),drop=FALSE],"dgCMatrix")
    features<-gsub("[_|]","-",rownames(data))
    if(anyDuplicated(features)||any(rownames(data)[features!=rownames(data)] %in% genes)) stop("Seurat特征转换产生冲突或改变LR身份")
    feature_map<-data.frame(original=rownames(data),native=features);rownames(counts)<-rownames(data)<-features
    assay<-SeuratObject::CreateAssayObject(counts=counts);assay<-SeuratObject::SetAssayData(assay,slot="data",new.data=data)
    meta<-m;meta$cell_type<-ids[match(meta$cell_type,types)]
    object<-SeuratObject::CreateSeuratObject(counts=assay,meta.data=meta);Idents(object)<-meta$cell_type
    object<-Seurat::ScaleData(object,features=intersect(genes,rownames(object)),verbose=FALSE)
    result<-Connectome::CreateConnectome(object,LR.database="fantom5",species="human",include.putative=putative,include.rejected=FALSE,p.values=FALSE,max.cells.per.ident=NULL,min.cells.per.ident=NULL,weight.definition.norm="product",weight.definition.scale="mean",calculate.DOR=FALSE)
    filtered<-Connectome::FilterConnectome(result,min.pct=pct,min.z=z,remove.na=TRUE)
    list(result=result,filtered=filtered,metadata=m,identity_map=data.frame(native=ids,cell_type=types),feature_map=feature_map)
  })
  d<-native$result;c$wt(d,paste0("native_candidates_",si,".tsv"));c$wt(native$filtered,paste0("native_filtered_",si,".tsv"));c$wt(native$identity_map,paste0("identity_map_",si,".tsv"))
  if(!nrow(d)) next
  if(!all(d$source %in% ids)||!all(d$target %in% ids)||anyDuplicated(d$edge)) stop("原生细胞群或LR身份不唯一")
  tested<-is.finite(d$weight_norm)&is.finite(d$percent.source)&is.finite(d$percent.target)
  supported<-tested&d$edge %in% native$filtered$edge&!is.na(d$weight_norm)&d$weight_norm>0
  allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=unname(inverse[d$source]),target=unname(inverse[d$target]),ligand=d$ligand,receptor=d$receptor,interaction=d$pair,pathway=d$mode,ligand_identity=paste0("gene:",d$ligand),receptor_identity=paste0("gene:",d$receptor),score=ifelse(tested,d$weight_norm,NA_real_),tested=tested,supported=supported,ligand_mean=d$ligand.expression,receptor_mean=d$recept.expression,ligand_fraction=d$percent.source,receptor_fraction=d$percent.target,native_weight_sc=d$weight_sc,ligand_z=d$ligand.scale,receptor_z=d$recept.scale)
}
rows<-if(length(allrows)) do.call(rbind,allrows) else data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),tested=logical(),supported=logical())
c$add("lr_edges","lr_edges",rows,"Connectome原生weight_norm；原生表达比例/z过滤保留的正权为支持。缺测不补零，无LR联合P。可加权图只汇总同一原生非负表达权重",value_kind="nonnegative_strength",additive=TRUE,axis_label="Connectome normalized expression weight",pathway_semantics="FANTOM5 curated signaling family")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
