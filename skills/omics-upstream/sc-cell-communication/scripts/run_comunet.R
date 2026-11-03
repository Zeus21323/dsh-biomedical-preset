#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
a<-commandArgs(TRUE);if(length(a)!=2) stop("需要配置JSON和新的Git外输出目录")
for(p in c("jsonlite","digest","COMUNET")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少：",p)
if(as.character(packageVersion("COMUNET"))!="0.1.0") stop("需要已核验COMUNET 0.1.0")
cp<-normalizePath(a[1]);cfg<-jsonlite::read_json(cp,simplifyVector=FALSE)
for(k in c("dataset","research_question","input","input_provenance","upstream_method","resource_version","score_definition","zero_semantics")) if(is.null(cfg[[k]])) stop("缺少：",k)
resolve<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
inp<-resolve(cfg$input);x<-readRDS(inp)
if(is.null(x$samples)||!length(x$samples)) stop("RDS需samples列表，每项含name/condition/donor/nodes/weight_array/ligand_receptor_pair_df")
if(file.exists(a[2])) stop("拒绝覆盖已有目录")
parent<-normalizePath(dirname(a[2]));while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("分析产物必须在Git外");parent<-dirname(parent)}
dir.create(a[2]);out<-normalizePath(a[2]);hash<-function(p) digest::digest(file=p,algo="sha256")
wj<-function(v,n) jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(v,n){v<-as.data.frame(v,check.names=FALSE);for(k in names(v)) if(is.numeric(v[[k]])) v[[k]]<-format(v[[k]],digits=17,scientific=TRUE,trim=TRUE);write.table(v,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")}
b<-list(schema_version=2,dataset=cfg$dataset,method="COMUNET",method_version="0.1.0",implementation="native",tables=list(),
  provenance=list(input_sha256=hash(inp),parameters=cfg,upstream=list(url="https://github.com/ScialdoneLab/COMUNET",commit="4fd4635c196fa597545b14c45ebf241aad252f76",license="GPL-3"),
  semantics="原生多层网络d_normWeightDiff、平均连接聚类及dynamicTreeCut；聚类0是未分配。条件比较是网络不相似度，不是供体差异P值；输入独有候选不等于生物学特异。零必须在上游明确，缺测不补零。"))
add<-function(id,rows,definition,...){fn<-paste0(id,".tsv");wt(rows,fn);b$tables[[length(b$tables)+1]]<<-c(list(id=id,type="matrix",path=fn,sha256=hash(file.path(out,fn)),value_definition=definition),list(...))}
matrows<-function(m){z<-expand.grid(row=rownames(m),column=colnames(m));z$value<-as.vector(m);z}
valid<-function(s){
  for(k in c("name","condition","donor","nodes","weight_array","ligand_receptor_pair_df")) if(is.null(s[[k]])) stop("样本缺少：",k)
  ar<-s$weight_array;lr<-s$ligand_receptor_pair_df;nodes<-s$nodes
  if(!is.numeric(ar)||length(dim(ar))!=3||any(!is.finite(ar))||any(ar<0)) stop("权重必须为有限非负三维数组；不把缺测补零")
  if(length(nodes)<2||anyDuplicated(nodes)||anyNA(nodes)||any(nodes=="")) stop("细胞身份必须唯一非空")
  cols<-c("pair","ligand","receptor","ligand_complex_composition","receptor_complex_composition")
  if(!all(cols %in% names(lr))||anyDuplicated(lr$pair)||anyNA(lr[,c("pair","ligand","receptor")])) stop("LR身份和复合体组成表无效")
  if(!identical(dimnames(ar),list(nodes,nodes,as.character(lr$pair)))) stop("权重三轴必须与nodes及LR表严格同序")
  # Native distance for two entirely empty layers is 1, not zero. Exclude
  # empty layers from clustering and retain the exact exclusion record.
  eligible<-apply(ar,3,function(v) any(v>0));wt(data.frame(pair=lr$pair,eligible=eligible),paste0("layer_eligibility_",match(s$name,vapply(x$samples,`[[`,character(1),"name")),".tsv"))
  if(sum(eligible)<2) stop("非空通讯层不足2，无法原生聚类")
  s$weight_array<-ar[,,eligible,drop=FALSE];s$ligand_receptor_pair_df<-lr[eligible,,drop=FALSE];s
}
names0<-vapply(x$samples,`[[`,character(1),"name");if(anyDuplicated(names0)) stop("样本名重复")
samples<-lapply(x$samples,valid)
params<-list(min_cluster_size=as.integer(cfg$min_cluster_size %||% 6),deep_split=as.integer(cfg$deep_split %||% 0),pattern=cfg$pattern,comparison=cfg$comparison,dynamicTreeCut=as.character(packageVersion("dynamicTreeCut")))
if(params$min_cluster_size<2||!params$deep_split %in% 0:4) stop("聚类参数无效")
signature<-digest::digest(list(input=hash(inp),version="0.1.0",params=params),algo="sha256");reuse<-NULL;old<-NULL;objects<-list()
if(!is.null(cfg$reuse_directory)){reuse<-resolve(cfg$reuse_directory);old<-jsonlite::read_json(file.path(reuse,"run_metadata.json"),simplifyVector=FALSE);if(!identical(signature,old$signature)) stop("原生缓存科学参数或输入改变")}
native<-function(id,compute){fn<-paste0(id,".rds");if(is.null(reuse)){z<-compute();saveRDS(z,file.path(out,fn))}else{rec<-old$objects[[id]];if(is.null(rec)||rec$sha256!=hash(file.path(reuse,fn))) stop("缓存对象摘要不符");z<-readRDS(file.path(reuse,fn));file.copy(file.path(reuse,fn),file.path(out,fn))};objects[[id]]<<-list(path=fn,sha256=hash(file.path(out,fn)));wj(list(signature=signature,objects=objects),"run_metadata.json");z}
wj(cfg,"run_config.json")
for(i in seq_along(samples)){
 s<-samples[[i]]
 z<-native(paste0("native_",i),function(){
  grDevices::pdf(file.path(out,paste0("native_diagnostics_",i,".pdf")));on.exit(grDevices::dev.off())
  COMUNET::lrp_clustering(s$weight_array,s$ligand_receptor_pair_df,s$nodes,deep_split=params$deep_split,min_cluster_size=params$min_cluster_size)
 })
 add(paste0("layer_dissimilarity_",i),matrows(z$dissim_matrix),"原生通讯层不相似度；0表示相同非空模式，1表示最大不相似，不作显著性解释",value_kind="native_score",axis_label="Native layer dissimilarity",display_top_rows=20L,title=paste(s$name,"communication patterns"))
 wt(data.frame(pair=names(z$clusters),cluster=as.integer(z$clusters)),paste0("native_clusters_",i,".tsv"))
 if(is.array(z$weight_array_by_cluster)) for(j in seq_len(dim(z$weight_array_by_cluster)[3])) add(paste0("cluster_",i,"_",j),matrows(z$weight_array_by_cluster[,,j]),"原生聚类内各LR层逐边权重均值；不是新增LR分数或概率",value_kind="nonnegative_strength",axis_label="Mean input edge weight",title=paste(s$name,"cluster",j))
 if(!is.null(cfg$pattern)){
  targets<-cfg$pattern;pm<-matrix(0,length(s$nodes),length(s$nodes),dimnames=list(s$nodes,s$nodes))
  for(edge in targets){if(!all(c(edge$source,edge$target) %in% s$nodes)) stop("指定模式含不存在细胞群");pm[edge$source,edge$target]<-1}
  if(!any(pm)) stop("指定模式需至少一条真实标签间的边")
  pp<-native(paste0("pattern_",i),function() COMUNET::pattern_search(pm,s$weight_array,s$ligand_receptor_pair_df,s$nodes))
  wt(pp,paste0("native_pattern_search_",i,".tsv"));add(paste0("pattern_search_",i),data.frame(row=pp$pair,column="Requested pattern",value=pp$dissimilarity),"原生二元边模式不相似度；指定模式是假设查询，不是实测新边；低值只表示接近查询",value_kind="native_score",axis_label="Pattern dissimilarity",display_top_rows=20L,direction="lower")
 }
}
if(!is.null(cfg$comparison)){
 names1<-unlist(cfg$comparison);if(length(names1)!=2||anyDuplicated(names1)||!all(names1 %in% names0)) stop("comparison需两个实际样本名")
 s1<-samples[[match(names1[1],names0)]];s2<-samples[[match(names1[2],names0)]]
 if(!identical(s1$nodes,s2$nodes)) stop("原生条件比较要求实际相同细胞群及顺序；不补缺失群")
 common<-intersect(s1$ligand_receptor_pair_df$pair,s2$ligand_receptor_pair_df$pair)
 for(k in common){a1<-s1$ligand_receptor_pair_df[match(k,s1$ligand_receptor_pair_df$pair),];a2<-s2$ligand_receptor_pair_df[match(k,s2$ligand_receptor_pair_df$pair),];if(!identical(as.character(unlist(a1)),as.character(unlist(a2)))) stop("同名LR两输入分子身份不一致")}
 z<-native("comparison",function() COMUNET::comparative_analysis(s1$weight_array,s2$weight_array,s1$ligand_receptor_pair_df,s2$ligand_receptor_pair_df,s1$nodes,s2$nodes,s1$name,s2$name))
 wt(z$sorted_LRP_df,"native_comparison.tsv")
 add("comparison_dissimilarity",data.frame(row=z$sorted_LRP_df$pair,column=paste(names1,collapse=" vs "),value=z$sorted_LRP_df$dissimilarity),"原生两输入通讯拓扑差异；仅某输入出现的候选被原生赋值1，应解释为输入范围独有，不能证明生物学消失；无供体检验或P值",value_kind="native_score",axis_label="Native topology dissimilarity",display_top_rows=20L)
}
wj(b,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
