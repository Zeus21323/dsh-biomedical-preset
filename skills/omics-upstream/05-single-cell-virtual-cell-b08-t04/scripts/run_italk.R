#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"iTALK","iTALK","0.1.0")
cfg<-c$cfg
if((cfg$mode %||% "mean")!="mean") stop("此入口核验原生mean-count分支；DEG端点检验不是LR联合显著性，不能改名替代")
top<-cfg$top_genes_percent %||% 50
if(!is.numeric(top)||length(top)!=1||!is.finite(top)||top<=0||top>100) stop("top_genes_percent需在(0,100]")
if("cell_type" %in% rownames(c$expr)) stop("表达基因名与iTALK元数据列冲突")
db<-get("database",asNamespace("iTALK"));saveRDS(db,file.path(c$out,"native_database.rds"))
c$start_cache(c$hash(file.path(c$out,"native_database.rds")),list(top_genes_percent=top,stats="mean",min_cells=c$minimum,expression_scale=cfg$expression_scale))
c$bundle$provenance$database_sha256<-c$hash(file.path(c$out,"native_database.rds"))
c$bundle$provenance$upstream<-list(commit="6d9b3907f00004fcac9514d2726ad68d524a952b",url="https://github.com/Coolgenome/iTALK",license="CC-BY-NC-SA; native package not redistributed")
c$bundle$provenance$inference<-"原生rawParse全实测基因背景内选择各细胞类型高表达百分位，再FindLR映射数据库；无联合LR分数、P值或FDR，不把端点表达乘积冒充原生分数"
allrows<-list();endpoint_rows<-list()
samples<-unique(c$meta$sample)
for(si in seq_along(samples)){
  sample<-samples[si];m<-c$sample_meta(sample)
  native<-c$native(si,sample,function(){
    dat<-as.data.frame(t(as.matrix(c$expr[,rownames(m),drop=FALSE])),check.names=FALSE);dat$cell_type<-m$cell_type
    selected<-iTALK::rawParse(dat,top_genes=top,stats="mean")
    results<-lapply(c("cytokine","checkpoint","growth factor","other"),function(k) iTALK::FindLR(selected,datatype="mean count",comm_type=k,database=db))
    list(selected=selected,result=do.call(rbind,results),metadata=m)
  })
  d<-native$result;c$wt(native$selected,paste0("native_selected_",si,".tsv"));c$wt(d,paste0("native_candidates_",si,".tsv"))
  if(!nrow(d)) next
  if(any(!is.finite(d$cell_from_mean_exprs))||any(!is.finite(d$cell_to_mean_exprs))) stop("原生端点表达非有限")
  positive<-d$cell_from_mean_exprs>0&d$cell_to_mean_exprs>0
  allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=d$cell_from,target=d$cell_to,
    ligand=d$ligand,receptor=d$receptor,interaction=paste(d$ligand,d$receptor,sep=" -> "),pathway=d$comm_type,
    ligand_identity=paste0("gene:",d$ligand),receptor_identity=paste0("gene:",d$receptor),
    score=as.integer(positive),tested=TRUE,supported=positive,ligand_mean=d$cell_from_mean_exprs,receptor_mean=d$cell_to_mean_exprs)
  endpoints<-unique(rbind(data.frame(gene=d$ligand,cell_type=d$cell_from,value=d$cell_from_mean_exprs),data.frame(gene=d$receptor,cell_type=d$cell_to,value=d$cell_to_mean_exprs)))
  c$add(paste0("endpoint_expression_",si),"matrix",data.frame(row=endpoints$gene,column=endpoints$cell_type,value=endpoints$value),
    "iTALK原生候选的端点平均表达；未入选端点保持缺失，不补0，不解释成通讯强度",axis_label=paste("Mean expression:",cfg$expression_scale),value_kind="native_score",display_top_rows=20L)
}
rows<-if(length(allrows)) do.call(rbind,allrows) else data.frame(sample=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),tested=logical(),supported=logical())
c$add("lr_edges","lr_edges",rows,"iTALK原生高表达候选中双端点正表达的存在标记(1)；可加的是候选数量，无连续LR强度或显著性；四类标签为数据库类别，不是机制通路",value_kind="count",additive=TRUE,axis_label="Positive native candidate presence",candidate_scope="native_top_expression_candidates",display_priority="minimum_endpoint_mean",pathway_semantics="database communication category")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
