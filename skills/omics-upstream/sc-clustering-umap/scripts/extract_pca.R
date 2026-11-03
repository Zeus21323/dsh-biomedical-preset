#!/usr/bin/env Rscript
# Seurat存储标准差；不以截断PC分母伪造总方差解释率。
a<-commandArgs(trailingOnly=TRUE)
arg<-function(k){i<-which(a==k);if(length(i)!=1||i==length(a))stop(paste("缺少参数",k));a[i+1]}
tryCatch({
  if(!requireNamespace("jsonlite",quietly=TRUE)||!requireNamespace("SeuratObject",quietly=TRUE))stop("需要jsonlite和SeuratObject")
  conf<-normalizePath(arg("--config"),mustWork=TRUE);cfg<-jsonlite::fromJSON(conf)
  if(length(setdiff(names(cfg),c("input","reduction","feature_space"))))stop("未知PCA提取字段")
  if(is.null(cfg$feature_space)||!nzchar(cfg$feature_space))stop("缺少实际特征空间")
  out<-arg("--out-dir");if(file.exists(out)||dir.exists(out))stop("输出已存在，拒绝覆盖")
  input<-if(grepl("^/",cfg$input))cfg$input else file.path(dirname(conf),cfg$input)
  obj<-readRDS(input);if(!inherits(obj,"Seurat"))stop("输入不是Seurat对象")
  key<-if(is.null(cfg$reduction))"pca" else cfg$reduction
  reduction<-obj[[key]]
  if(is.null(reduction)||!inherits(reduction,"DimReduc"))stop("缺少降维对象")
  values<-methods::slot(reduction,"stdev")
  if(!length(values)||any(!is.finite(values)|values<0))stop("存储标准差无效")
  dir.create(dirname(out),recursive=TRUE,showWarnings=FALSE);tmp<-tempfile(".pca-",tmpdir=dirname(out));dir.create(tmp)
  write.table(data.frame(pc_index=seq_along(values),statistic_type="stdev",value=values,unit="standard_deviation"),file.path(tmp,"pca.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  jsonlite::write_json(list(status="complete",input_md5=unname(tools::md5sum(input)),config=cfg,denominator="not_applicable",R=R.version.string,SeuratObject=as.character(packageVersion("SeuratObject")),session=capture.output(sessionInfo())),file.path(tmp,"extraction.json"),auto_unbox=TRUE,pretty=TRUE)
  if(file.exists(out)||dir.exists(out)||!file.rename(tmp,out))stop("输出确认失败")
  cat("已提取存储标准差：",out,"\n")
},error=function(e){cat("PCA提取未完成：",conditionMessage(e),"\n",file=stderr());quit(status=2)})
