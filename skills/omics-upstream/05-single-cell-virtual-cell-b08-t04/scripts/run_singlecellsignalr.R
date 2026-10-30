#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
a<-commandArgs(TRUE);if(length(a)!=2) stop("用法：Rscript run_singlecellsignalr.R 配置.json 新输出目录")
for(p in c("SingleCellSignalR","jsonlite","digest","Matrix")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
if(as.character(packageVersion("SingleCellSignalR"))!="1.18.0") stop("需要已核验的SingleCellSignalR 1.18.0；v2为另一接口")
suppressPackageStartupMessages(library(SingleCellSignalR))
cp<-normalizePath(a[1]);cfg<-jsonlite::read_json(cp,simplifyVector=TRUE)
for(k in c("input","dataset","research_question","species","expression_scale")) if(is.null(cfg[[k]])) stop("缺少：",k)
if(cfg$species!="human"||cfg$expression_scale!="counts") stop("此分支需要真实human counts；不默默使用可能丢失一对多关系的小鼠同源映射")
input<-normalizePath(if(startsWith(cfg$input,"/")) cfg$input else file.path(dirname(cp),cfg$input))
x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))||!setequal(colnames(expr),rownames(meta))) stop("基因和细胞身份无效")
meta<-meta[colnames(expr),,drop=FALSE];needed<-c("sample","donor","condition","cell_type")
if(!all(needed %in% names(meta))||anyNA(meta[,needed])||any(trimws(as.matrix(meta[,needed]))=="")) stop("元数据不完整")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(as.matrix(expr))
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("输入不是有限非负整数counts")
cutoff<-cfg$s_score %||% .5;tol<-cfg$tol %||% 0
if(cutoff<0||cutoff>=1||tol<0||tol>1) stop("LRscore或表达比例阈值无效")
if(file.exists(a[2])) stop("拒绝覆盖结果")
parent<-normalizePath(dirname(a[2]),mustWork=FALSE);while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("结果必须在Git外");parent<-dirname(parent)}
dir.create(a[2],recursive=TRUE);out<-normalizePath(a[2]);hash<-function(p) digest::digest(file=p,algo="sha256")
wj<-function(v,n) jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(v,n) write.table(v,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
db<-get("LRdb",envir=as.environment("package:SingleCellSignalR"));saveRDS(db,file.path(out,"LRdb.rds"))
bundle<-list(schema_version=2,dataset=cfg$dataset,method="SingleCellSignalR",method_version="1.18.0",implementation="native",
 provenance=list(input_sha256=hash(input),parameters=cfg,database_sha256=hash(file.path(out,"LRdb.rds")),
 normalization="原生data_prepare：每细胞99%分位数相对中位数缩放后log1p；记录实际保留细胞",
 test_unit="原生cluster_analysis仅在单样本内做细胞群marker edgeR检验，不能作供体条件检验；LRscore本身无P/FDR",
 support="原生cell_signaling以s.score=0导出正分候选；支持标记为严格LRscore>配置s_score；保留autocrine/paracrine/specific原生分类"),tables=list())
wj(cfg,"run_config.json");allrows<-list();previous<-getwd()
for(si in seq_along(unique(meta$sample))){
 sample<-unique(meta$sample)[si];m<-meta[meta$sample==sample,,drop=FALSE]
 if(length(unique(m$donor))!=1||length(unique(m$condition))!=1) stop("sample必须唯一对应donor/condition")
 sizes<-table(m$cell_type);m<-m[m$cell_type %in% names(sizes[sizes>=(cfg$min_cells %||% 10L)]),,drop=FALSE]
 if(length(unique(m$cell_type))<2) stop("合格细胞群不足2")
 folder<-file.path(out,paste0("native_",si));dir.create(folder);setwd(folder)
 raw<-as.data.frame(as.matrix(expr[,rownames(m),drop=FALSE]),check.names=FALSE)
 original_cells<-rownames(m);native_cells<-sprintf("C%07d",seq_len(ncol(raw)))
 colnames(raw)<-native_cells;m$original_cell<-original_cells;rownames(m)<-native_cells
 write.table(data.frame(gene=rownames(raw),raw,check.names=FALSE),"input_counts.tsv",sep="\t",quote=FALSE,row.names=FALSE)
 set.seed(cfg$seed %||% 1L)
 normalized<-SingleCellSignalR::data_prepare("input_counts.tsv",most.variables=0,normalize=TRUE,write=TRUE,plot=FALSE)
 # Native preparation can discard low-complexity cells; re-align by identity, never positional truncation.
 if(!all(colnames(normalized) %in% rownames(m))) stop("原生归一化改变了细胞身份")
 m<-m[colnames(normalized),,drop=FALSE];sizes<-table(m$cell_type)
 keep<-m$cell_type %in% names(sizes[sizes>=(cfg$min_cells %||% 10L)]);m<-m[keep,,drop=FALSE];normalized<-normalized[,rownames(m),drop=FALSE]
 types<-sort(unique(m$cell_type));if(length(types)<2) stop("原生准备后合格群不足2")
 ids<-sprintf("CT%03d",seq_along(types));inverse<-setNames(types,ids);cluster<-match(m$cell_type,types)
 raw<-raw[rownames(normalized),rownames(m),drop=FALSE]
 markers<-SingleCellSignalR::cluster_analysis(raw,genes=rownames(raw),cluster=cluster,c.names=ids,dif.exp=TRUE,s.pval=cfg$marker_fdr %||% .01,write=TRUE)
 saveRDS(markers,"native_markers.rds")
 # Empty native marker results need an explicit empty file; otherwise the
 # upstream helper treats a missing historical file as silently unavailable.
 for(id in ids){fn<-paste0("cluster-analysis/table_dge_",id,".txt");if(!file.exists(fn)) write.table(data.frame(genes=character(),logFC=numeric()),fn,sep="\t",quote=FALSE,row.names=FALSE)}
 mapping<-data.frame(native_cell=rownames(m),m,native_group=ids[cluster]);write.table(mapping,"identity_map.tsv",sep="\t",quote=FALSE,row.names=FALSE)
 for(mode in c("autocrine","paracrine")){
   result<-SingleCellSignalR::cell_signaling(normalized,genes=rownames(normalized),cluster=cluster,int.type=mode,c.names=ids,
     s.score=0,logFC=cfg$marker_logfc %||% log2(1.5),species="homo sapiens",tol=tol,write=TRUE)
   saveRDS(result,paste0(mode,".rds"))
   for(name in names(result)){
     f<-result[[name]];ab<-strsplit(name,"-",fixed=TRUE)[[1]]
     if(!nrow(f)) next
     if(length(ab)!=2||!all(ab %in% ids)||any(!is.finite(f$LRscore))) stop("原生候选身份或分数无效")
     allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=unique(m$donor),condition=unique(m$condition),source=inverse[ab[1]],target=inverse[ab[2]],
       ligand=f[[1]],receptor=f[[2]],interaction=paste(f[[1]],f[[2]],sep=" -> "),native_interaction_type=f[[3]],native_branch=mode,
       score=f$LRscore,tested=TRUE,supported=f$LRscore>cutoff)
   }
 }
 setwd(previous)
}
if(length(allrows)){
 rows<-do.call(rbind,allrows);wt(rows,"native_candidates.tsv")
 bundle$provenance$exact_duplicate_rows_removed<-sum(duplicated(rows))
 rows<-unique(rows);wt(rows,"lr_edges.tsv")
 bundle$tables<-list(list(id="lr_edges",type="lr_edges",path="lr_edges.tsv",sha256=hash(file.path(out,"lr_edges.tsv")),
   value_definition="SingleCellSignalR原生LRscore；正分候选完整保留，支持为严格分数阈值筛选，不是显著性；保留原生自分泌/旁分泌分类",
   value_kind="native_score",additive=FALSE,axis_label="SingleCellSignalR LRscore",candidate_scope="native_positive_only"))
}else {
 bundle$provenance$empty_result<-"原生两分支没有正分候选，保留完整原生对象，不补造边"
 wt(data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),tested=logical(),supported=logical()),"lr_edges.tsv")
 bundle$tables<-list(list(id="lr_edges",type="lr_edges",path="lr_edges.tsv",sha256=hash(file.path(out,"lr_edges.tsv")),
   value_definition="原生两分支未返回正分候选；空表保留身份契约，不能绘制假网络",value_kind="native_score",additive=FALSE,candidate_scope="native_positive_only"))
}
wj(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
