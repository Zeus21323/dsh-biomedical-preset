#!/usr/bin/env Rscript
a<-commandArgs(trailingOnly=TRUE)
if(!length(a)||"--help"%in%a){cat("Rscript run_coloc.R --config coloc.config.json；单信号ABF，非SuSiE分支\n");quit(status=0)}
arg<-function(k){i<-which(a==k);if(length(i)!=1||i==length(a))stop(paste("缺少",k));a[i+1]}
tryCatch({
  if(!requireNamespace("svglite",quietly=TRUE))stop("缺少svglite，不能交付可编辑SVG")
  for(pkg in c("jsonlite","coloc"))if(!requireNamespace(pkg,quietly=TRUE))stop(paste("缺少",pkg))
  cp<-normalizePath(arg("--config"),mustWork=TRUE);c<-jsonlite::fromJSON(cp)
  for(k in c("aligned_reviewed","region_complete_reviewed","single_signal_reviewed"))if(!isTRUE(c[[k]]))stop(paste("先核验",k))
  for(k in c("build","ancestry","region","assumption_evidence","sample_overlap","output"))if(!is.character(c[[k]])||length(c[[k]])!=1||!nzchar(c[[k]]))stop(paste("缺少",k))
  resolve<-function(p){if(!is.character(p)||length(p)!=1||!nzchar(p))stop("缺少文件");if(!grepl("^(/|[A-Za-z]:)",p))p<-file.path(dirname(cp),p);normalizePath(p,mustWork=TRUE)}
  loadside<-function(s){
    p<-resolve(s$file);d<-read.delim(p,check.names=FALSE)
    if(!all(c("SNP","POS","BETA","SE","EAF")%in%names(d))||!nrow(d)||anyDuplicated(d$SNP))stop("区域表缺列/空/重复")
    for(k in c("POS","BETA","SE","EAF"))if(!is.numeric(d[[k]])||any(!is.finite(d[[k]])))stop(paste("非法",k))
    if(any(d$POS<=0|d$POS!=floor(d$POS)|d$SE<=0|d$EAF<=0|d$EAF>=1))stop("位置/SE/EAF非法")
    if(length(s$N)!=1||!is.finite(s$N)||s$N<=2||!s$type%in%c("quant","cc"))stop("类型/N非法")
    if(s$type=="quant"&&(length(s$sdY)!=1||!is.finite(s$sdY)||s$sdY<=0))stop("quant需要可靠sdY")
    if(s$type=="cc"&&(length(s$s)!=1||!is.finite(s$s)||s$s<=0||s$s>=1))stop("cc需要病例比例")
    list(data=d,path=p,spec=s)
  }
  x<-loadside(c$first);y<-loadside(c$second)
  ids<-intersect(x$data$SNP,y$data$SNP)
  if(!length(ids))stop("区域无共同变异")
  coverage<-data.frame(side=c("first","second"),available=c(nrow(x$data),nrow(y$data)),overlap=length(ids))
  x$data<-x$data[match(ids,x$data$SNP),];y$data<-y$data[match(ids,y$data$SNP),]
  if(any(x$data$POS!=y$data$POS))stop("共同变异坐标不一致")
  dataset<-function(z){
    d<-z$data;s<-z$spec
    out<-list(beta=d$BETA,varbeta=d$SE^2,snp=d$SNP,position=d$POS,MAF=pmin(d$EAF,1-d$EAF),N=s$N,type=s$type)
    if(s$type=="quant")out$sdY<-s$sdY else out$s<-s$s
    out
  }
  for(k in c("p1","p2"))if(length(c[[k]])!=1||!is.finite(c[[k]])||c[[k]]<=0||c[[k]]>=1)stop("先验非法")
  if(!length(c$p12)||any(!is.finite(c$p12)|c$p12<=0|c$p12>min(c$p1,c$p2)))stop("p12非法")
  out<-c$output;if(!grepl("^(/|[A-Za-z]:)",out))out<-file.path(dirname(cp),out)
  if(file.exists(out)||dir.exists(out))stop("输出已存在")
  if(!dir.exists(dirname(out)))stop("请先准备仓库外输出父目录")
  out<-file.path(normalizePath(dirname(out)),basename(out))
  self<-sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[1]);parent<-dirname(normalizePath(self))
  repeat{
    if(dir.exists(file.path(parent,".git"))||dir.exists(file.path(parent,".speedskills"))){
      if(out==parent||startsWith(out,paste0(parent,"/")))stop("不能写入仓库");break
    }
    nxt<-dirname(parent);if(nxt==parent)break;parent<-nxt
  }
  results<-lapply(c$p12,function(p)coloc::coloc.abf(dataset(x),dataset(y),p1=c$p1,p2=c$p2,p12=p))
  summary<-do.call(rbind,lapply(seq_along(results),function(i)data.frame(p12=c$p12[i],as.list(results[[i]]$summary),check.names=FALSE)))
  dir.create(out)
  write.table(summary,file.path(out,"posterior.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  write.table(coverage,file.path(out,"coverage.tsv"),sep="\t",quote=FALSE,row.names=FALSE)
  for(i in seq_along(results))write.table(results[[i]]$results,file.path(out,paste0("variants_",i,".tsv")),sep="\t",quote=FALSE,row.names=FALSE)
  jsonlite::write_json(c,file.path(out,"config.used.json"),pretty=TRUE,auto_unbox=TRUE)
  draw<-function(){
    par(mfrow=c(2,2),mar=c(4,4,3,1),cex=.75)
    z1<-x$data$BETA/x$data$SE;z2<-y$data$BETA/y$data$SE
    m1<--(log(2)+pnorm(-abs(z1),log.p=TRUE))/log(10)
    m2<--(log(2)+pnorm(-abs(z2),log.p=TRUE))/log(10)
    yr<-range(c(m1,m2),finite=TRUE)
    plot(x$data$POS,m1,pch=16,col="#0072B2",xlab="Position",ylab="-log10 P (normal approximation)",main="Trait 1",ylim=yr)
    plot(y$data$POS,m2,pch=16,col="#D55E00",xlab="Position",ylab="-log10 P (normal approximation)",main="Trait 2",ylim=yr)
    pp<-grep("^PP.H",names(summary),value=TRUE)
    barplot(as.numeric(unlist(summary[1,pp])),names.arg=paste0("H",0:4),ylim=c(0,1),col="#009E73",main=paste("ABF, p12 =",c$p12[1]),ylab="Posterior")
    plot(summary$p12,summary[["PP.H4.abf"]],type="b",log="x",ylim=c(0,1),col="#CC79A7",xlab="p12 prior",ylab="H4 posterior",main="Prior sensitivity")
  }
  pdf(file.path(out,"coloc.pdf"),width=180/25.4,height=160/25.4,useDingbats=FALSE);draw();dev.off()
  svglite::svglite(file.path(out,"coloc.svg"),width=180/25.4,height=160/25.4);draw();dev.off()
  png(file.path(out,"coloc.png"),width=180,height=160,units="mm",res=600);draw();dev.off()
  writeLines(c("ABF assumes at most one causal signal per trait in the region.",
    "All p12 settings are retained. Region plots use normal-approximation association P for display only.",
    paste("Build",c$build,"Ancestry",c$ancestry,"Region",c$region,"Overlap",c$sample_overlap),
    "H4 supports shared signal conditional on assumptions, not direction or mediation."),
    file.path(out,"captions.txt"))
  capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
},error=function(e){message("错误：",conditionMessage(e));quit(status=2)})
