#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
a<-commandArgs(TRUE);if(length(a)!=2) stop("用法：Rscript run_cellcallext.R 配置.json 新输出目录")
for(p in c("jsonlite","digest","Matrix")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
cp<-normalizePath(a[1]);cfg<-jsonlite::read_json(cp,simplifyVector=TRUE)
path<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
if(!is.null(cfg$r_library)) .libPaths(c(path(cfg$r_library),.libPaths()))
if(!requireNamespace("cellcallEXT",quietly=TRUE)) stop("缺少独立原生cellcallEXT；不能改用cellcall")
if(as.character(packageVersion("cellcallEXT"))!="0.0.0.9000") stop("版本未核验")
pd<-packageDescription("cellcallEXT")
if(pd[["Config/CommunicationAdapter/SourceCommit"]]!="8ce584ac27ebf2f709a1e1b640f8834dbbac27e6"||pd[["Config/CommunicationAdapter/Patch"]]!="plot-grid-import-only") stop("需要固定原生源码及已审计导入兼容补丁")
for(k in c("dataset","research_question","input","species","expression_scale","case","control","analysis_unit")) if(is.null(cfg[[k]])) stop("缺少配置：",k)
if(cfg$species!="human"||cfg$expression_scale!="counts") stop("此已核验分支需要human实际UMI counts")
if(cfg$analysis_unit!="pooled_cells") stop("原生方法按细胞群池化，不支持供体协变量；必须明确pooled_cells并保留真实供体身份")
direction<-cfg$expression_direction %||% "UP";if(!direction %in% c("UP","DOWN","BOTH")) stop("响应方向无效")
input<-path(cfg$input);x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))||!setequal(colnames(expr),rownames(meta))) stop("表达、元数据身份无效")
meta<-meta[colnames(expr),,drop=FALSE];required<-c("sample","donor","condition","cell_type")
if(!all(required %in% names(meta))||anyNA(meta[,required])||any(trimws(as.matrix(meta[,required]))=="")) stop("元数据不完整")
for(s in unique(meta$sample)){m<-meta[meta$sample==s,,drop=FALSE];if(length(unique(m$donor))!=1||length(unique(m$condition))!=1) stop("sample与donor/condition不唯一对应")}
if(cfg$case==cfg$control||!setequal(unique(meta$condition),c(cfg$case,cfg$control))) stop("需要恰好两个真实条件，不随机构造case/control")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(as.matrix(expr))
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("输入必须为真实整数counts")
counts<-table(meta$cell_type,meta$condition);keep<-rownames(counts)[apply(counts>= (cfg$min_cells %||% 10L),1,all)]
if(length(keep)<2) stop("两条件均达到细胞数要求的细胞类型少于2")
meta<-meta[meta$cell_type %in% keep,,drop=FALSE];expr<-expr[,rownames(meta),drop=FALSE]
if(file.exists(a[2])) stop("拒绝覆盖已有目录")
parent<-normalizePath(dirname(a[2]),mustWork=FALSE);while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("结果必须在Git外");parent<-dirname(parent)}
dir.create(a[2],recursive=TRUE);out<-normalizePath(a[2]);hash<-function(p) digest::digest(file=p,algo="sha256")
wj<-function(v,n) jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(v,n) write.table(v,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
safe<-setNames(sprintf("CT%03d",seq_along(keep)),keep);inverse<-setNames(keep,safe)
dat<-as.data.frame(as.matrix(expr));colnames(dat)<-paste0("cell",seq_len(ncol(dat)),"_",safe[meta$cell_type])
wt(data.frame(original_cell=rownames(meta),native_cell=colnames(dat),meta,native_group=safe[meta$cell_type]),"identity_map.tsv")
resources<-c("rectome_ligand_receptor_TFs_withReactome.txt","tf_target.txt")
dbhash<-setNames(lapply(resources,function(n)hash(system.file("extdata",n,package="cellcallEXT"))),resources)
provenance<-list(input_sha256=hash(input),parameters=cfg,database_sha256=dbhash,source_commit="8ce584ac27ebf2f709a1e1b640f8834dbbac27e6",
 compatibility_patch="仅将plot_grid导入改为实际提供者cowplot；原生评分R源码未改",analysis_unit="pooled_cells",
 donors=unique(meta$donor),samples=unique(meta$sample),condition_counts=as.list(table(meta$condition)),
 evidence="真实case/control条件内细胞群响应程序；不是供体层级差异检验，相关/富集不是因果",
 mechanism_export="按本次实际Reactome LR–TF资源与原生正分数/TF载荷导出；不调用错误读取cellcall资源的上游LR2TF辅助函数")
wj(cfg,"run_config.json");wj(provenance,"provenance.json")
set.seed(cfg$seed %||% 1L)
obj<-cellcallEXT::CreateNichConObject(dat,names.field=2,names.delim="_",source="UMI",Org="Homo sapiens",
  status=ifelse(meta$condition==cfg$case,"CASE","CONTROL"),expDirection=direction,project=cfg$dataset)
obj<-cellcallEXT::TransCommuProfile(obj,pValueCor=cfg$pValueCor %||% .05,CorValue=cfg$CorValue %||% .1,topTargetCor=cfg$topTargetCor %||% 1,
  p.adjust=cfg$alpha %||% .05,use.type=cfg$use_type %||% "median",probs=cfg$probs %||% .75,method="weighted",IS_core=TRUE,Org="Homo sapiens")
saveRDS(obj,file.path(out,"cellcallext.rds"));provenance$native_object_sha256<-hash(file.path(out,"cellcallext.rds"))
bundle<-list(schema_version=2,dataset=cfg$dataset,method="CellCallEXT",method_version="0.0.0.9000",implementation="native",provenance=provenance,tables=list())
add<-function(id,type,df,definition,...){fn<-paste0(id,".tsv");wt(df,fn);bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=fn,sha256=hash(file.path(out,fn)),value_definition=definition),list(...))}
mat<-as.data.frame(obj@data$expr_l_r);if(any(!is.finite(as.matrix(mat)))) stop("原生LR分数非有限")
triple<-read.delim(system.file("extdata",resources[1],package="cellcallEXT"),check.names=FALSE)
pairs<-unique(triple[,c("Ligand_Symbol","Receptor_Symbol")]);pid<-paste(pairs$Ligand_Symbol,pairs$Receptor_Symbol,sep="-")
if(anyDuplicated(pid)||!all(rownames(mat) %in% pid)) stop("原生LR身份有歧义")
rows<-list();label<-paste0("pooled: ",cfg$case," vs ",cfg$control)
for(j in seq_len(nrow(mat))) for(k in seq_len(ncol(mat))){
 p<-pairs[match(rownames(mat)[j],pid),];ab<-strsplit(colnames(mat)[k],"-",fixed=TRUE)[[1]]
 rows[[length(rows)+1]]<-data.frame(sample=label,donor=paste0("pooled cells; ",length(unique(meta$donor))," actual donors"),condition=label,
 source=inverse[ab[1]],target=inverse[ab[2]],ligand=p$Ligand_Symbol,receptor=p$Receptor_Symbol,interaction=rownames(mat)[j],score=mat[j,k],tested=TRUE,supported=mat[j,k]>0)
}
if(length(rows)) add("lr_edges","lr_edges",do.call(rbind,rows),paste0("CellCallEXT原生LR分数，响应方向",direction,"；正分为原生候选保留，不是LR联合显著性"),value_kind="nonnegative_strength",additive=TRUE,axis_label="CellCallEXT score",candidate_scope="native_retained_only")
tf<-obj@data$regulons_matrix;g<-expand.grid(row=rownames(tf),column=colnames(tf));g$value<-as.vector(as.matrix(tf));g$column<-inverse[g$column]
add("regulons","matrix",g,paste0("原生",direction,"响应regulon载荷；DOWN/BOTH在原生算法内取绝对值，不据此丢失原始GSEA方向，带符号NES另存"),value_kind="nonnegative_strength",axis_label="Retained regulon loading")
for(k in names(obj@data$gsea.list)){s<-obj@data$gsea.list[[k]];if(isS4(s)&&"result" %in% slotNames(s)) wt(s@result,paste0("native_gsea_",k,".tsv"))}
for(k in names(obj@data$fc.list)) wt(obj@data$fc.list[[k]],paste0("native_condition_logfc_",k,".tsv"))
if(nrow(mat)){
 totals<-colSums(mat);chosen<-head(names(sort(totals[totals>0],decreasing=TRUE)),cfg$top_cell_pairs %||% 3L)
 for(i in seq_along(chosen)){
   ab<-strsplit(chosen[i],"-",fixed=TRUE)[[1]];selected<-rownames(mat)[mat[,chosen[i]]>0]
   tri<-triple[paste(triple$Ligand_Symbol,triple$Receptor_Symbol,sep="-") %in% selected,,drop=FALSE]
   tri<-tri[tri$TF_Symbol %in% rownames(tf),,drop=FALSE];tri<-tri[tf[tri$TF_Symbol,ab[2]]>0,,drop=FALSE]
   wt(tri,paste0("native_resource_mechanism_",i,".tsv"))
   if(nrow(tri)){
     edges<-unique(rbind(data.frame(source=tri$Ligand_Symbol,target=tri$Receptor_Symbol,source_type="ligand",target_type="receptor",value=1),
                        data.frame(source=tri$Receptor_Symbol,target=tri$TF_Symbol,source_type="receptor",target_type="TF",value=1)))
     add(paste0("mechanism_",i),"molecular_links",edges,paste0(inverse[ab[1]]," → ",inverse[ab[2]],"：本次原生保留LR、TF与实际资源中的关联；等宽表示关联存在，不是流量"),value_kind="count")
   }
 }
}
wj(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
