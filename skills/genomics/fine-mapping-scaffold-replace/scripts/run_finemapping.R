#!/usr/bin/env Rscript
a<-commandArgs(trailingOnly=TRUE)
if(!length(a)||"--help"%in%a){cat("Rscript run_finemapping.R --stats locus.tsv --ld ld.tsv --n N --signals L --coverage 0.95 --ld-source description --out new_directory\n");quit(status=0)}
arg<-function(k){i<-which(a==k);if(length(i)!=1||i==length(a))stop(paste("缺少",k));a[i+1]}
tryCatch({
  if(!requireNamespace("svglite",quietly=TRUE))stop("缺少svglite，不能交付可编辑SVG")
  if(!requireNamespace("susieR",quietly=TRUE))stop("缺少susieR；未运行")
  sp<-normalizePath(arg("--stats"),mustWork=TRUE);lp<-normalizePath(arg("--ld"),mustWork=TRUE)
  d<-read.delim(sp,check.names=FALSE);r<-as.matrix(read.delim(lp,row.names=1,check.names=FALSE))
  if(!all(c("SNP","Z")%in%names(d))||!nrow(d)||anyDuplicated(d$SNP))stop("需要唯一SNP和Z")
  if(!identical(as.character(d$SNP),rownames(r))||!identical(rownames(r),colnames(r)))stop("SNP顺序不一致")
  storage.mode(r)<-"double"
  if(any(!is.finite(r))||any(!is.finite(d$Z))||max(abs(r))>1+1e-8||max(abs(diag(r)-1))>1e-8||max(abs(r-t(r)))>1e-8)stop("LD/Z非法")
  if(min(eigen(r,symmetric=TRUE,only.values=TRUE)$values)< -1e-6)stop("LD非半正定")
  n<-as.numeric(arg("--n"));L<-as.numeric(arg("--signals"));coverage<-as.numeric(arg("--coverage"))
  if(!is.finite(n)||n<=2||!is.finite(L)||L<1||L!=floor(L)||L>nrow(d)||!is.finite(coverage)||coverage<=0||coverage>=1)stop("N/L/coverage非法")
  ldsource<-arg("--ld-source")
  if(!nzchar(ldsource))stop("需要参考来源说明")
  out<-arg("--out")
  if(file.exists(out)||dir.exists(out))stop("输出已存在")
  if(!dir.exists(dirname(out)))stop("先准备仓库外输出父目录")
  out<-file.path(normalizePath(dirname(out)),basename(out))
  self<-sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[1]);parent<-dirname(normalizePath(self))
  repeat{
    if(dir.exists(file.path(parent,".git"))||dir.exists(file.path(parent,".speedskills"))){
      if(out==parent||startsWith(out,paste0(parent,"/")))stop("不能写入仓库");break
    }
    nxt<-dirname(parent);if(nxt==parent)break;parent<-nxt
  }
  fit<-susieR::susie_rss(z=d$Z,R=r,n=n,L=L,coverage=coverage,estimate_residual_variance=FALSE)
  dir.create(out)
  saveRDS(fit,file.path(out,"fit.rds"))
  if(!isTRUE(fit$converged)){writeLines("not_converged",file.path(out,"FAILED.txt"));stop("未收敛，不能交付为成功结果")}
  pip<-data.frame(SNP=d$SNP,Z=d$Z,PIP=fit$pip)
  write.table(pip,file.path(out,"pip.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  cs<-fit$sets$cs
  members<-data.frame(set=character(),SNP=character(),PIP=numeric())
  if(length(cs))for(i in seq_along(cs)){
    ix<-cs[[i]];members<-rbind(members,data.frame(set=names(cs)[i],SNP=d$SNP[ix],PIP=fit$pip[ix]))
  }
  write.table(members,file.path(out,"credible_sets.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  if(!is.null(fit$sets$purity))write.table(fit$sets$purity,file.path(out,"purity.tsv"),sep="\t",quote=FALSE)
  draw<-function(){
    par(mar=c(4,4,2,1),cex=.8)
    plot(seq_len(nrow(d)),fit$pip,pch=16,col="#0072B2",ylim=c(0,1),xlab="Variant order (see pip.tsv)",ylab="Posterior inclusion probability",main="Fine-mapping conditional on model and LD")
    if(length(cs)){
      colors<-c("#D55E00","#009E73","#CC79A7","#E69F00")
      for(i in seq_along(cs))points(cs[[i]],fit$pip[cs[[i]]],pch=1,col=colors[(i-1)%%length(colors)+1],cex=1.6)
    }
  }
  grDevices::pdf(file.path(out,"pip.pdf"),width=180/25.4,height=105/25.4,useDingbats=FALSE);draw();dev.off()
  svglite::svglite(file.path(out,"pip.svg"),width=180/25.4,height=105/25.4);draw();dev.off()
  grDevices::png(file.path(out,"pip.png"),width=180,height=105,units="mm",res=600);draw();dev.off()
  writeLines(c(paste("N",n,"max signals",L,"coverage",coverage),paste("LD:",ldsource),
    "External reference residual variance was not estimated. Order corresponds to pip.tsv.",
    "PIP and credible sets are conditional on input variants, priors and LD; not experimental causality.",
    "No credible set is a valid outcome; do not reduce standards to manufacture candidates."),
    file.path(out,"captions.txt"))
  capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
  write.table(data.frame(file=c(sp,lp),md5=unname(tools::md5sum(c(sp,lp)))),file.path(out,"inputs.tsv"),sep="\t",row.names=FALSE,quote=FALSE)
},error=function(e){message("错误：",conditionMessage(e));quit(status=2)})
