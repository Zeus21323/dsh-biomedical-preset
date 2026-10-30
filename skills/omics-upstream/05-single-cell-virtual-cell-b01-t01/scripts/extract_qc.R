#!/usr/bin/env Rscript
# 从Seurat元数据提取已有QC；不重算、不过滤、不修改原对象。
a <- commandArgs(trailingOnly=TRUE)
arg <- function(k) { i<-which(a==k); if(length(i)!=1 || i==length(a)) stop(paste("缺少参数",k)); a[i+1] }
tryCatch({
  if(!requireNamespace("jsonlite",quietly=TRUE)||!requireNamespace("SeuratObject",quietly=TRUE)) stop("需要jsonlite和SeuratObject")
  conf<-normalizePath(arg("--config"),mustWork=TRUE);cfg<-jsonlite::fromJSON(conf,simplifyVector=FALSE)
  allowed<-c("input","sample_column","stage","columns","units")
  if(length(setdiff(names(cfg),allowed)))stop("未知QC提取配置字段")
  out<-arg("--out-dir");if(file.exists(out)||dir.exists(out))stop("输出已存在，拒绝覆盖")
  input<-if(grepl("^/",cfg$input))cfg$input else file.path(dirname(conf),cfg$input)
  obj<-readRDS(input);if(!inherits(obj,"Seurat"))stop("输入不是Seurat对象")
  d<-obj[[]]
  if(!nrow(d)||anyDuplicated(rownames(d))||!identical(rownames(d),colnames(obj)))stop("细胞身份无效或元数据错位")
  if(is.null(cfg$stage)||!nzchar(cfg$stage)||!cfg$sample_column%in%names(d))stop("阶段或实际样本字段缺失")
  if(anyNA(d[[cfg$sample_column]])||any(!nzchar(as.character(d[[cfg$sample_column]]))))stop("样本身份缺失")
  units<-c(detected_genes="genes",total_counts="counts",mitochondrial_percent="%")
  if(!length(cfg$columns)||length(setdiff(names(cfg$columns),names(units))))stop("无效指标映射")
  rows<-list()
  for(metric in names(cfg$columns)) {
    col<-cfg$columns[[metric]];u<-cfg$units[[metric]]
    if(!col%in%names(d)||is.null(u))stop("缺少指标或已验证单位")
    v<-suppressWarnings(as.numeric(as.character(d[[col]])))
    if(any(!is.finite(v)|v<0))stop("指标缺失、非有限或负值")
    if(metric=="mitochondrial_percent"&&u=="fraction") {if(any(v>1))stop("比例超过1");v<-v*100}
    else if(u!=units[[metric]])stop("单位不匹配")
    if(metric=="mitochondrial_percent") {if(any(v>100))stop("百分比超过100")}
    else if(any(v!=floor(v)))stop("计数指标不是整数")
    rows[[metric]]<-data.frame(cell_id=rownames(d),sample_id=as.character(d[[cfg$sample_column]]),stage=cfg$stage,metric=metric,value=v,unit=units[[metric]])
  }
  dir.create(dirname(out),recursive=TRUE,showWarnings=FALSE)
  tmp<-tempfile(".qc-",tmpdir=dirname(out));dir.create(tmp)
  write.table(do.call(rbind,rows),file.path(tmp,"qc.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  jsonlite::write_json(list(status="complete",input_md5=unname(tools::md5sum(input)),config=cfg,R=R.version.string,SeuratObject=as.character(packageVersion("SeuratObject")),session=capture.output(sessionInfo())),file.path(tmp,"extraction.json"),auto_unbox=TRUE,pretty=TRUE)
  if(file.exists(out)||dir.exists(out)||!file.rename(tmp,out))stop("输出确认失败")
  cat("已提取真实QC表：",out,"\n")
},error=function(e){cat("QC提取未完成：",conditionMessage(e),"\n",file=stderr());quit(status=2)})
