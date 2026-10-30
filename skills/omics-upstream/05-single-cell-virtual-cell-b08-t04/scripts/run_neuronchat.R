#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%` <- function(x,y) if(is.null(x)) y else x
args <- commandArgs(TRUE)
if(length(args)!=2) stop("用法：Rscript run_neuronchat.R 配置.json 新输出目录")
for(p in c("NeuronChat","jsonlite","digest","Matrix")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
if(as.character(packageVersion("NeuronChat"))!="1.0.0") stop("需要核验的 NeuronChat 1.0.0")
suppressPackageStartupMessages(library(NeuronChat))
cfg_path<-normalizePath(args[1]);cfg<-jsonlite::read_json(cfg_path,simplifyVector=TRUE)
for(k in c("dataset","research_question","input","species","expression_scale")) if(is.null(cfg[[k]])) stop("缺少配置：",k)
if(!cfg$species %in% c("mouse","human") || !cfg$expression_scale %in% c("normalized","log_normalized")) stop("物种或表达层不适用")
input<-normalizePath(if(startsWith(cfg$input,"/")) cfg$input else file.path(dirname(cfg_path),cfg$input))
if(file.exists(args[2])) stop("拒绝覆盖已有输出")
parent<-normalizePath(dirname(args[2]),mustWork=FALSE)
while(parent!="/") {if(file.exists(file.path(parent,".git"))) stop("输出必须在Git外");parent<-dirname(parent)}
dir.create(args[2],recursive=TRUE);out<-normalizePath(args[2])
write_json<-function(x,n) jsonlite::write_json(x,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
write_table<-function(x,n) write.table(x,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
hash<-function(p) digest::digest(file=p,algo="sha256")
x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))) stop("需要唯一基因/细胞的expression和metadata")
if(!setequal(colnames(expr),rownames(meta))) stop("细胞ID不匹配")
meta<-meta[colnames(expr),,drop=FALSE]
if(!all(c("sample","donor","condition","cell_type") %in% names(meta))||anyNA(meta[,c("sample","donor","condition","cell_type")])) stop("样本/供体/条件/细胞类型不完整")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(expr)
if(any(!is.finite(v))||any(v<0)||!any(v>0)) stop("表达必须有限非负且有信号")
write_json(cfg,"run_config.json")
db_hash<-NULL;all_rows<-list();selection<-list()
for(si in seq_along(unique(meta$sample))) {
  sample<-unique(meta$sample)[si];m<-meta[meta$sample==sample,,drop=FALSE]
  if(length(unique(m$donor))!=1||length(unique(m$condition))!=1) stop("一个样本必须对应一个供体/条件；池化必须显式标为池化")
  counts<-table(m$cell_type);m<-m[m$cell_type %in% names(counts[counts>=(cfg$min_cells %||% 10L)]),,drop=FALSE]
  if(length(unique(m$cell_type))<2) stop("合格细胞群不足2")
  set.seed(cfg$seed %||% 1L)
  obj<-NeuronChat::createNeuronChat(expr[,rownames(m),drop=FALSE],DB=cfg$species,meta=m,group.by=m$cell_type)
  if(is.null(db_hash)) {saveRDS(obj@DB,file.path(out,"database.rds"));db_hash<-hash(file.path(out,"database.rds"))}
  testable<-vapply(obj@DB,function(r) {
    lig<-r$lig_contributor_group[r$lig_contributor %in% names(obj@data.signaling)]
    rec<-r$receptor_subunit_group[r$receptor_subunit %in% names(obj@data.signaling)]
    all(unique(r$lig_contributor_group) %in% lig)&&all(unique(r$receptor_subunit_group) %in% rec)
  },logical(1))
  if(!any(testable)) stop("神经递质合成/释放贡献组或接收亚基组均不完整")
  permutations<-cfg$n_perms %||% 1000L
  if(permutations<100) stop("正式推断至少100次置换，并报告P值分辨率")
  obj<-NeuronChat::run_NeuronChat(obj,M=permutations,fdr=cfg$alpha %||% .05,strict=1)
  saveRDS(obj,file.path(out,paste0("neuronchat_",si,".rds")))
  rows<-list()
  for(j in seq_along(obj@net0)) {
    name<-names(obj@net0)[j];mat<-obj@net0[[j]];pv<-obj@pvalue[[j]]
    for(a in seq_len(nrow(mat))) for(b in seq_len(ncol(mat))) {
      tested<-testable[j]&&is.finite(pv[a,b]);r<-obj@DB[[j]]
      rows[[length(rows)+1]]<-data.frame(sample=sample,source=rownames(mat)[a],target=colnames(mat)[b],
        ligand=sub("_.*$","",name),receptor=paste(r$receptor_subunit,collapse="_"),interaction=name,
        contributors=paste(r$lig_contributor,collapse=";"),score=if(testable[j]) mat[a,b] else NA_real_,
        p_value=if(tested) pv[a,b] else NA_real_,tested=tested,supported=tested&&obj@net[[j]][a,b]>0)
    }
  }
  rows<-do.call(rbind,rows);write_table(rows,paste0("native_candidates_",si,".tsv"));all_rows[[si]]<-rows
  selection[[si]]<-list(sample=sample,untestable_interactions=names(testable)[!testable],cell_counts=as.list(counts))
}
rows<-do.call(rbind,all_rows);write_table(rows,"neural_edges.tsv");write_json(selection,"selection.json")
bundle<-list(schema_version=2,dataset=cfg$dataset,method="NeuronChat",method_version="1.0.0",implementation="native",
  provenance=list(parameters=cfg,input_sha256=hash(input),database_sha256=db_hash,
    evidence="递质合成/释放贡献组与受体组表达代理；不是实测突触连接；保留原生置换与筛选语义"),
  tables=list(list(id="neural_edges",type="lr_edges",path="neural_edges.tsv",sha256=hash(file.path(out,"neural_edges.tsv")),
    value_definition="NeuronChat原生神经递质/配体–受体分数；支持标记来自原生net，P来自原生pvalue。缺必要贡献组或未置换者不算检验。",value_kind="nonnegative_strength",additive=TRUE,direction="higher",axis_label="NeuronChat score")))
write_json(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
