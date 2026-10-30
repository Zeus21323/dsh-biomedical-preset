#!/usr/bin/env Rscript
# Plot saved estimates, not invented observations.
a <- commandArgs(trailingOnly=TRUE)
if (!length(a) || "--help" %in% a) {
  cat("Rscript plot_mr.R --input mr_output --out figures_new --exposure-label 'Exposure (unit)' --outcome-label 'Outcome (unit)'\n")
  quit(status=0)
}
arg <- function(k) { i<-which(a==k); if(length(i)!=1 || i==length(a)) stop(paste("缺少参数",k)); a[i+1] }
tryCatch({
  if(!requireNamespace("svglite",quietly=TRUE))stop("缺少svglite，不能交付可编辑SVG")
  if(!requireNamespace("ggplot2",quietly=TRUE)) stop("缺少ggplot2")
  src<-normalizePath(arg("--input"),mustWork=TRUE)
  out<-arg("--out")
  if(file.exists(out)||dir.exists(out)) stop("输出已存在")
  if(!dir.exists(dirname(out))) stop("请先准备仓库外的输出父目录")
  out<-file.path(normalizePath(dirname(out)),basename(out))
  self<-sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[1])
  for(parent in c(dirname(normalizePath(self)), character())) {
    repeat {
      if(dir.exists(file.path(parent,".git"))||dir.exists(file.path(parent,".speedskills"))) {
        if(out==parent||startsWith(out,paste0(parent,"/"))) stop("不能输出到源码仓库")
        break
      }
      nxt<-dirname(parent);if(nxt==parent)break;parent<-nxt
    }
  }
  xl<-arg("--exposure-label");yl<-arg("--outcome-label")
  readtab<-function(name) read.delim(file.path(src,paste0(name,".tsv")),check.names=FALSE)
  e<-readtab("estimates");d<-readtab("harmonized")
  if(!all(c("method","b","se","ci_low","ci_high")%in%names(e))||!nrow(e))stop("估计表不完整")
  if(any(!is.finite(e$b)|!is.finite(e$se)|e$se<=0|!is.finite(e$ci_low)|!is.finite(e$ci_high)))stop("不能用非有限估计作图")
  d<-d[d$mr_keep %in% TRUE,,drop=FALSE]
  if(!nrow(d))stop("无保留工具")
  dir.create(out,recursive=FALSE)
  theme<-ggplot2::theme_classic(base_size=9)+ggplot2::theme(plot.title=ggplot2::element_text(size=10),legend.position="bottom")
  saveplot<-function(g,name,dat,width=180,height=110) {
    g <- g + ggplot2::theme(panel.grid.major=ggplot2::element_blank(), panel.grid.minor=ggplot2::element_blank())
    saveRDS(g,file.path(out,paste0(name,".ggplot.rds")))
    write.table(dat,file.path(out,paste0(name,".tsv")),sep="\t",quote=FALSE,row.names=FALSE)
    grDevices::pdf(file.path(out,paste0(name,".pdf")),width=width/25.4,height=height/25.4,useDingbats=FALSE);print(g);grDevices::dev.off()
    svglite::svglite(file.path(out,paste0(name,".svg")),width=width/25.4,height=height/25.4);print(g);grDevices::dev.off()
    grDevices::png(file.path(out,paste0(name,".png")),width=width,height=height,units="mm",res=600);print(g);grDevices::dev.off()
  }
  e$method<-factor(e$method,levels=rev(unique(e$method)))
  forest<-ggplot2::ggplot(e,ggplot2::aes(x=method,y=b))+
    ggplot2::geom_hline(yintercept=0,linetype=2,color="grey50")+
    ggplot2::geom_errorbar(ggplot2::aes(ymin=ci_low,ymax=ci_high),width=.2,color="#0072B2")+
    ggplot2::geom_point(color="#0072B2",size=2)+ggplot2::coord_flip()+
    ggplot2::labs(x=NULL,y=paste("MR beta:",yl,"per",xl),title="MR estimates (method-specific 95% intervals)")+theme
  saveplot(forest,"method_forest",e,height=max(90,50+8*nrow(e)))
  scatter<-ggplot2::ggplot(d,ggplot2::aes(x=beta.exposure,y=beta.outcome))+
    ggplot2::geom_segment(ggplot2::aes(x=beta.exposure-1.96*se.exposure,xend=beta.exposure+1.96*se.exposure,yend=beta.outcome),color="grey70")+
    ggplot2::geom_errorbar(ggplot2::aes(ymin=beta.outcome-1.96*se.outcome,ymax=beta.outcome+1.96*se.outcome),width=0,color="grey70")+
    ggplot2::geom_point(color="#0072B2",size=1.6)+ggplot2::labs(x=xl,y=yl,title="Harmonized SNP associations (not a causal proof)")+theme
  # No misleading zero-intercept line for Egger; each method remains in forest.
  saveplot(scatter,"snp_scatter",d)
  strength<-ggplot2::ggplot(d,ggplot2::aes(x=reorder(SNP,F_exposure),y=F_exposure))+
    ggplot2::geom_point(color="#009E73")+ggplot2::coord_flip()+ggplot2::labs(x=NULL,y="Approximate per-SNP F",title="Instrument strength")+theme
  if(nrow(d)<=50)saveplot(strength,"instrument_strength",d,height=max(90,40+4*nrow(d)))
  if(file.exists(file.path(src,"leave_one_out.tsv"))) {
    l<-readtab("leave_one_out")
    if(all(c("SNP","b","se")%in%names(l))&&nrow(l)&&all(is.finite(l$b)&is.finite(l$se))) {
      l$ci_low<-l$b-1.96*l$se;l$ci_high<-l$b+1.96*l$se
      # Paginate to keep labels readable, preserving the complete data.
      groups<-split(seq_len(nrow(l)),ceiling(seq_len(nrow(l))/35))
      for(i in seq_along(groups)) {
        z<-l[groups[[i]],,drop=FALSE];z$SNP<-factor(z$SNP,levels=rev(unique(z$SNP)))
        g<-ggplot2::ggplot(z,ggplot2::aes(x=SNP,y=b))+ggplot2::geom_hline(yintercept=0,linetype=2,color="grey50")+
          ggplot2::geom_errorbar(ggplot2::aes(ymin=ci_low,ymax=ci_high),width=.2,color="#D55E00")+
          ggplot2::geom_point(color="#D55E00",size=1.8)+ggplot2::coord_flip()+theme+
          ggplot2::labs(x="Omitted SNP",y="MR beta",title="Leave-one-out sensitivity (95% normal intervals)")
        saveplot(g,paste0("leave_one_out_",i),z,height=max(90,45+4*nrow(z)))
      }
    }
  }
  writeLines(c("# 图注与核对","图来自保存的真实MR结果；效应为beta，非OR。主效应区间沿用estimates.tsv；Egger和weighted mode使用与后端检验一致的t分布，分别为n-2和n-1自由度，其余本入口方法为正态近似95%。weighted mode的区间在本入口显式计算，不冒充原包默认正态区间。留一图为正态近似。",
    paste("暴露：",xl,"；结局：",yl),paste("保留工具：",nrow(d)),
    "补充实际队列、祖源、N、单位、工具阈值、LD参考与重叠信息；不得编造缺失元数据。",
    "打开所有图片检查字体、误差线和裁切；图件不证明工具假设成立。",
    "工具强度图超过50工具时未生成，按需要分面；其他不可用图参考status.tsv。"),
    file.path(out,"captions.md"),useBytes=TRUE)
  capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
},error=function(e){message("错误：",conditionMessage(e));quit(status=2)})
