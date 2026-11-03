#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
a<-commandArgs(TRUE);if(length(a)!=2) stop("需要配置JSON和新的Git外输出目录")
library(jsonlite);cp<-normalizePath(a[1]);cfg<-read_json(cp,simplifyVector=FALSE)
resolve<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
if(!is.null(cfg$r_library)) .libPaths(c(resolve(cfg$r_library),.libPaths()))
for(p in c("CrossTalkeR","digest","igraph")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少：",p)
if(as.character(packageVersion("CrossTalkeR"))!="2.0.0") stop("需要CrossTalkeR 2.0.0")
for(k in c("dataset","research_question","input","input_provenance","species","upstream_method","score_definition","resource_version")) if(is.null(cfg[[k]])) stop("缺少：",k)
if(!cfg$species %in% c("human","mouse")) stop("物种只核验human/mouse")
inp<-resolve(cfg$input);x<-readRDS(inp);tables<-x$tables
if(!is.list(tables)||!length(tables)||is.null(names(tables))||anyDuplicated(names(tables))||any(grepl("_x_",names(tables)))) stop("RDS需命名tables列表，名称唯一且不含原生比较分隔符_x_")
cols<-c("source","target","gene_A","gene_B","type_gene_A","type_gene_B","MeanLR")
for(name in names(tables)){
 d<-tables[[name]]
 if(!is.data.frame(d)||!all(cols %in% names(d))||!nrow(d)||anyNA(d[,cols])) stop("通讯表缺少完整原生输入列：",name)
 if(!is.numeric(d$MeanLR)||any(!is.finite(d$MeanLR))||any(d$MeanLR<=0)) stop("输入边需正的可加原生权重；缺测与零值不能作为存在的边输入")
 if(any(grepl("[@/|]",as.character(unlist(d[,c("source","target","gene_A","gene_B")]))))) stop("身份包含原生分隔符；先提供可追溯且唯一的原生身份映射")
 if(any(d$type_gene_A!="Ligand")||any(d$type_gene_B!="Receptor")) stop("当前入口为真实LR网络，不补造TF连接")
 if(anyDuplicated(d[,c("source","target","gene_A","gene_B")])) stop("重复LR边会影响计数与权重，需先明确合并依据")
}
if(length(tables)>1&&is.null(cfg$absent_edge_semantics)) stop("原生差异把输入未出现的边当0；必须说明这是已过滤图的约定，不是表达未检测或生物学消失")
if(file.exists(a[2])) stop("拒绝覆盖已有目录")
parent<-normalizePath(dirname(a[2]));while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("输出必须在Git外");parent<-dirname(parent)}
dir.create(a[2]);out<-normalizePath(a[2]);hash<-function(p) digest::digest(file=p,algo="sha256")
wj<-function(v,n) write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(v,n){v<-as.data.frame(v,check.names=FALSE);for(k in names(v)) if(is.numeric(v[[k]])) v[[k]]<-format(v[[k]],digits=17,scientific=TRUE,trim=TRUE);write.table(v,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")}
b<-list(schema_version=2,dataset=cfg$dataset,method="CrossTalkeR",method_version="2.0.0",implementation="native",tables=list(),provenance=list(input_sha256=hash(inp),parameters=cfg,upstream=list(url="https://github.com/CostaLab/CrossTalkeR",commit="8bca82e13fd099e9d731832d3e2f7ef841876c0a",license="MIT"),
  semantics="原生细胞/细胞-基因图、Listener/Influencer/Mediator/PageRank及PCA；原生Mediator将绝对通讯权重直接作为路径距离，不替换成倒数。差异图是图权重相减；Fisher比较两图中细胞对的LR条目比例，非供体病例对照检验，且原生没有多重校正。"))
add<-function(id,type,rows,definition,...){fn<-paste0(id,".tsv");wt(rows,fn);b$tables[[length(b$tables)+1]]<<-c(list(id=id,type=type,path=fn,sha256=hash(file.path(out,fn)),value_definition=definition),list(...))}
matrixrows<-function(m){d<-expand.grid(row=rownames(m),column=colnames(m));d$value<-as.vector(m);d$value[!is.finite(d$value)]<-NA_real_;d}
comparison<-if(!is.null(cfg$comparison)) lapply(cfg$comparison,unlist) else NULL
if(!is.null(comparison)&&any(vapply(comparison,function(z)length(z)!=2||anyDuplicated(z)||!all(z %in% names(tables)),logical(1)))) stop("比较需两两真实表名，方向为第一项减第二项")
annotation<-isTRUE(cfg$native_annotation);signature<-digest::digest(list(input=hash(inp),version="2.0.0",igraph=as.character(packageVersion("igraph")),comparison=comparison,annotation=annotation,seed=cfg$seed %||% 42),algo="sha256")
wj(cfg,"run_config.json")
if(!is.null(cfg$reuse_directory)){
 olddir<-resolve(cfg$reuse_directory);old<-read_json(file.path(olddir,"run_metadata.json"));if(old$signature!=signature||old$native_sha256!=hash(file.path(olddir,"native_result.rds"))) stop("原生缓存输入、科学参数或对象摘要不符")
 native<-readRDS(file.path(olddir,"native_result.rds"));file.copy(file.path(olddir,"native_result.rds"),file.path(out,"native_result.rds"))
}else{
 set.seed(cfg$seed %||% 42)
 native<-CrossTalkeR:::read_lr_single_condition(tables,cols,out,sep=",")
 if(length(tables)>1){native<-CrossTalkeR:::create_diff_table(native,out,comparison,"LRScore");native<-CrossTalkeR:::fisher_test_cci(native,"LRScore",out,comparison)}
 native<-CrossTalkeR:::ranking(native,out,cols,slot="graphs")
 native<-CrossTalkeR:::ranking(native,out,cols,slot="graphs_ggi")
 if(annotation){
  db<-if(cfg$species=="human") org.Hs.eg.db::org.Hs.eg.db else org.Mm.eg.db::org.Mm.eg.db
  native<-CrossTalkeR:::kegg_annotation(native,"rankings",out,db,if(cfg$species=="human") "hsa" else "mmu")
 }
 saveRDS(native,file.path(out,"native_result.rds"))
}
wj(list(signature=signature,native_sha256=hash(file.path(out,"native_result.rds"))),"run_metadata.json")
for(i in seq_along(native@graphs)){
 name<-names(native@graphs)[i];g<-native@graphs[[i]];edges<-igraph::as_data_frame(g,what="edges");wt(edges,paste0("native_graph_",i,".tsv"))
 m<-as.matrix(igraph::as_adjacency_matrix(g,attr="weight",sparse=FALSE));add(paste0("cell_network_",i),"matrix",matrixrows(m),"原生有向细胞图权重；比较图为输入图差值。原生新增孤立节点与未列边为图中的零，不代表缺测补零",value_kind="native_score",axis_label="Native summed LR weight",title=name)
 if(!grepl("_x_",name)) add(paste0("cell_graph_",i),"network",data.frame(source=edges$from,target=edges$to,value=edges$weight),"原生细胞对可加LR权重之和；不是新推断的通讯概率",value_kind="nonnegative_strength",additive=TRUE,directed=TRUE)
}
for(i in seq_along(native@rankings)){
 name<-names(native@rankings)[i];d<-as.data.frame(native@rankings[[i]]);wt(d,paste0("native_rankings_",i,".tsv"));m<-as.matrix(d[,setdiff(names(d),"nodes"),drop=FALSE]);rownames(m)<-d$nodes
 # Metrics have different units; each receives its own scale and source table.
 for(j in seq_len(ncol(m))) add(paste0("centrality_",i,"_",j),"matrix",matrixrows(m[,j,drop=FALSE]),"原生节点中心性，保留每个指标的原生定义和独立尺度，不混成机制总分",value_kind="native_score",axis_label=colnames(m)[j],figure_role="centrality",display_top_rows=20L,title=paste(name,colnames(m)[j]))
}
for(i in seq_along(native@pca)){
 name<-names(native@pca)[i];p<-native@pca[[i]];if(!is.null(p$rotation)) add(paste0("pca_loadings_",i),"matrix",matrixrows(p$rotation),"原生中心性指标PCA载荷；正负号任意，不是通讯激活方向",value_kind="signed_score",axis_label="PCA loading",title=name)
}
for(i in seq_along(native@stats)){
 d<-as.data.frame(native@stats[[i]]);wt(d,paste0("native_fisher_",i,".tsv"))
 if(all(c("columns_name","p") %in% names(d))) add(paste0("graph_fisher_",i),"matrix",data.frame(row=d$columns_name,column="Native Fisher P",value=d$p),"原生Fisher检验比较图中LR条目比例，仅涉及两个输入均出现的细胞对；无多重校正，不作为患者/供体差异显著性",value_kind="p_value",axis_label="Unadjusted graph-composition P",display_top_rows=20L,direction="lower")
}
if(annotation) for(i in seq_along(native@annot)) wt(native@annot[[i]],paste0("native_annotation_",i,".tsv"))
b$provenance$annotation_scope<-if(annotation) "原生KEGG在线注释；背景为原生内置LR库，不是输入可检测全背景。结果仅保留原生表供背景复核，不能替代有适当背景的富集验收。" else "未请求原生在线KEGG注释；网络核心分析已单独执行。"
wj(b,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
