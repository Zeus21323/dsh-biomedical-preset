#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"CommPath","CommPath","1.1.0");cfg<-c$cfg
suppressPackageStartupMessages(library(CommPath))
if(cfg$expression_scale!="log_normalized") stop("原生端点logFC要求自然log1p归一化表达")
if(!requireNamespace("GSVA",quietly=TRUE)||!requireNamespace("BiocParallel",quietly=TRUE)) stop("缺少GSVA或BiocParallel")
if(as.character(packageVersion("GSVA"))!="2.0.7") stop("此原生接口需要已核验GSVA2.0.7")
if((cfg$pathway_scoring %||% "gsva")!="gsva") stop("此分支已固定原生GSVA路径，不以平均表达替代")
category<-cfg$pathway_category %||% "kegg"
if(!category %in% c("kegg","wiki","reactome","go","all")) stop("未知原生通路库")
fc<-cfg$logfc_threshold %||% 0;q<-cfg$endpoint_q_threshold %||% .01;minsize<-as.integer(cfg$min_pathway_size %||% 10L)
if(!is.numeric(fc)||length(fc)!=1||!is.finite(fc)||fc<0||!is.numeric(q)||length(q)!=1||!is.finite(q)||q<=0||q>.05||is.na(minsize)||minsize<2) stop("端点正logFC、q及基因集大小阈值无效")
resources<-CommPath::CommPathData;saveRDS(resources,file.path(c$out,"native_resources.rds"))
c$start_cache(c$hash(file.path(c$out,"native_resources.rds")),list(min_cells=c$minimum,logfc_threshold=fc,endpoint_q_threshold=q,pathway_category=category,pathway_scoring="gsva",GSVA=as.character(packageVersion("GSVA")),min_pathway_size=minsize))
c$bundle$provenance$upstream<-list(commit="f40286445f9bd74d0f5370667d7d12735ba8d3cf",url="https://github.com/yingyonghui/CommPath",license="GPL-3")
c$bundle$provenance$resource_sha256<-c$hash(file.path(c$out,"native_resources.rds"))
c$bundle$provenance$statistics<-"原生findLRmarker在每细胞群内对其余细胞做Wilcoxon并对实际表达LR基因BH；findLRpairs先筛端点，再用1-(1-qL)(1-qR)组合并在筛后LR族BH，原生只返回q<0.05的LR。该筛后q不是全候选独立检验FDR，细胞不是供体重复，不作条件因果推断。保留全部端点与原生对象"
c$bundle$provenance$pathway<-"findLRpath为基因集重叠筛选，不是超几何富集；原生GSVA在已有表达背景上评分，diffAllPath对细胞群与其余细胞做Welch检验及群内通路BH；filterLR使用受体所在正向通路。路径表示先验成员关系与响应关联，不证明直接因果链"
allrows<-list()
for(si in seq_along(unique(c$meta$sample))){
 sample<-unique(c$meta$sample)[si];m<-c$sample_meta(sample);types<-unique(m$cell_type);ids<-sprintf("CT%03d",seq_along(types));inverse<-setNames(types,ids)
 native<-c$native(si,sample,function(){
  info<-data.frame(Cluster=ids[match(m$cell_type,types)],row.names=rownames(m))
  object<-CommPath::createCommPath(c$expr[,rownames(m),drop=FALSE],info,species="hsapiens")
  object<-CommPath::findLRmarker(object,method="wilcox.test",p.adjust="BH")
  saveRDS(object,file.path(c$out,paste0("native_marker_checkpoint_",si,".rds")))
  object<-CommPath::findLRpairs(object,logFC.thre=fc,p.thre=q)
  object<-CommPath::findLRpath(object,category=category)
  object<-CommPath::scorePath(object,method="gsva",min.size=minsize,kcdf="Gaussian")
  pathways<-CommPath::diffAllPath(object,method="t.test",only.posi=FALSE,only.sig=FALSE)
  # Native filter functions need non-empty activated receptor pathways.
  # Preserve a valid negative response stage instead of lowering thresholds.
  active<-pathways[which(pathways$mean.diff>0&pathways$P.val.adj<.05&!is.na(pathways$receptor.in.path)),,drop=FALSE]
  if(nrow(active)){
    object<-CommPath::filterLR(object,pathways)
    filtered_pathways<-CommPath::filterPath(object,pathways)
    if(nrow(object@interact.filter$InteractGene)&&nrow(filtered_pathways)) object<-CommPath::pathNet(object,filtered_pathways)
  }else filtered_pathways<-pathways[FALSE,,drop=FALSE]
  list(object=object,pathways=pathways,filtered_pathways=filtered_pathways,metadata=m,identity_map=data.frame(native=ids,cell_type=types))
 })
 object<-native$object;d<-object@interact$InteractGene;filtered<-object@interact.filter$InteractGene
 c$wt(object@LR.marker,paste0("native_markers_",si,".tsv"));c$wt(d,paste0("native_lr_",si,".tsv"));c$wt(native$pathways,paste0("native_pathways_",si,".tsv"));c$wt(native$identity_map,paste0("identity_map_",si,".tsv"))
 if(!is.null(filtered)) c$wt(filtered,paste0("native_filtered_lr_",si,".tsv"))
 key<-function(v) paste(v$cell.from,v$cell.to,v$ligand,v$receptor,sep="\r")
 if(anyDuplicated(key(d))||!all(c(d$cell.from,d$cell.to) %in% ids)) stop("原生LR或细胞群身份歧义")
 support<-if(is.null(filtered)) rep(FALSE,nrow(d)) else key(d) %in% key(filtered)
 allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=unname(inverse[d$cell.from]),target=unname(inverse[d$cell.to]),ligand=d$ligand,receptor=d$receptor,interaction=paste(d$ligand,d$receptor,sep=" -> "),ligand_identity=paste0("gene:",d$ligand),receptor_identity=paste0("gene:",d$receptor),score=d$log2FC.LR,p_value=d$P.val.LR,q_value=d$P.val.adj.LR,tested=is.finite(d$log2FC.LR),supported=support,native_lr_stage_supported=TRUE)
 score<-object@pathway$acti.score
 c$wt(data.frame(pathway=rownames(score),score,check.names=FALSE),paste0("native_pathway_scores_",si,".tsv"))
 means<-vapply(ids,function(id) rowMeans(score[,object@cell.info$Cluster==id,drop=FALSE]),numeric(nrow(score)));rownames(means)<-rownames(score);colnames(means)<-unname(inverse[ids])
 c$add(paste0("pathway_activity_",si),"matrix",data.frame(row=rep(rownames(means),ncol(means)),column=rep(colnames(means),each=nrow(means)),value=as.numeric(means)),"原生GSVA分数按实际细胞群取均值用于描述性展示；输入基因背景与全部逐细胞分数保留，不将该均值当供体重复",axis_label="Mean GSVA activity",value_kind="native_score",figure_role="intracellular_response",display_top_rows=20L)
 if(nrow(native$pathways)){
  p<-native$pathways
  c$add(paste0("pathway_response_",si),"matrix",data.frame(row=p$description,column=unname(inverse[p$cluster]),value=p$mean.diff),"原生群内细胞对其余细胞的GSVA均值差；统计原表另存，不是疾病条件差异",axis_label="GSVA mean difference",value_kind="native_score",figure_role="intracellular_response",display_top_rows=20L)
 }
 if(!is.null(filtered)&&nrow(filtered)){
  selected<-head(filtered[order(-filtered$log2FC.LR),,drop=FALSE],3)
  for(j in seq_len(nrow(selected))){
   row<-selected[j,];paths<-head(strsplit(row$path.contain.rep,";",fixed=TRUE)[[1]],5)
   links<-rbind(data.frame(source=row$ligand,target=row$receptor,source_type="ligand",target_type="receptor",value=1),data.frame(source=row$receptor,target=paths,source_type="receptor",target_type="pathway",value=1))
   c$add(paste0("pathway_links_",si,"_",j),"molecular_links",links,paste0(inverse[row$cell.from],"→",inverse[row$cell.to],": 原生通路筛选后LR权重前三候选、每个至多5个已激活且含该受体的原生通路；等宽表示成员关系，无TF或直接靶基因边时不补造"),value_kind="count")
  }
 }
}
c$add("lr_edges","lr_edges",do.call(rbind,allrows),"CommPath原生两端正向marker log2FC乘积；tested范围仅原生筛后LR，supported再要求原生接收端通路筛选。P/q保留筛后原生定义，不冒充全部数据库候选FDR",value_kind="nonnegative_strength",additive=TRUE,axis_label="CommPath marker log2FC product",candidate_scope="native_postselection_lr_only")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
