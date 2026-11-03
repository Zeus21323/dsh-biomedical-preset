#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%` <- function(x,y) if(is.null(x)) y else x
args<-commandArgs(TRUE)
if(length(args)!=2) stop("用法：Rscript run_cellcall.R 配置.json 新输出目录")
for(p in c("cellcall","jsonlite","digest","Matrix")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
if(as.character(packageVersion("cellcall"))!="1.0.7") stop("需要已核验 CellCall 1.0.7")
cfgpath<-normalizePath(args[1]);cfg<-jsonlite::read_json(cfgpath,simplifyVector=TRUE)
for(k in c("dataset","research_question","input","species","expression_scale","source")) if(is.null(cfg[[k]])) stop("缺少：",k)
if(!cfg$species %in% c("human","mouse")) stop("物种不支持")
if(!cfg$source %in% c("UMI","TPM","CPM")) stop("显式提供 UMI counts、TPM 或 CPM；不自动把普通归一化值冒充TPM")
if((cfg$source=="UMI" && cfg$expression_scale!="counts") || (cfg$source!="UMI" && cfg$expression_scale!="normalized")) stop("表达层与source不一致")
input<-normalizePath(if(startsWith(cfg$input,"/")) cfg$input else file.path(dirname(cfgpath),cfg$input))
if(file.exists(args[2])) stop("拒绝覆盖已有输出")
parent<-normalizePath(dirname(args[2]),mustWork=FALSE)
while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("运行结果必须在Git外");parent<-dirname(parent)}
dir.create(args[2],recursive=TRUE);out<-normalizePath(args[2])
wj<-function(x,n) jsonlite::write_json(x,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(x,n) write.table(x,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
hash<-function(p) digest::digest(file=p,algo="sha256")
x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))) stop("需要唯一基因/细胞的expression和metadata")
if(!setequal(colnames(expr),rownames(meta))) stop("细胞ID不匹配")
meta<-meta[colnames(expr),,drop=FALSE];required<-c("sample","donor","condition","cell_type")
if(!all(required %in% names(meta))||anyNA(meta[,required])||any(trimws(as.matrix(meta[,required]))=="")) stop("样本、供体、条件、类型不完整")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(as.matrix(expr))
if(any(!is.finite(v))||any(v<0)||!any(v>0)) stop("表达必须有限非负且有信号")
if(cfg$source=="UMI" && any(abs(v-round(v))>1e-7)) stop("UMI输入必须为整数counts")
core<-!(cfg$extended %||% FALSE);org<-if(cfg$species=="human") "Homo sapiens" else "Mus musculus"
suffix<-if(cfg$species=="mouse") "_homology" else ""
resources<-c(paste0("new_ligand_receptor_TFs",suffix,".txt"),paste0("tf_target",suffix,".txt"))
if(!core) resources<-c(resources,paste0("new_ligand_receptor_TFs",suffix,"_extended.txt"))
dbhash<-setNames(lapply(resources,function(n) hash(system.file("extdata",n,package="cellcall"))),resources)
wj(cfg,"run_config.json")
scientific_cfg<-cfg[setdiff(names(cfg),c("input","reuse_directory","top_cell_pairs","colors"))]
signature<-list(input_sha256=hash(input),database_sha256=dbhash,parameters=scientific_cfg,method_version="1.0.7")
run_metadata<-list(signature=signature,native_objects=list());wj(run_metadata,"run_metadata.json")
reuse<-NULL
if(!is.null(cfg$reuse_directory)){
 reuse<-normalizePath(if(startsWith(cfg$reuse_directory,"/")) cfg$reuse_directory else file.path(dirname(cfgpath),cfg$reuse_directory))
 old<-jsonlite::read_json(file.path(reuse,"run_metadata.json"),simplifyVector=FALSE)
 if(!identical(jsonlite::toJSON(old$signature,auto_unbox=TRUE),jsonlite::toJSON(signature,auto_unbox=TRUE))) stop("复用对象的输入、数据库、版本或科学参数不同")
}
bundle<-list(schema_version=2,dataset=cfg$dataset,method="CellCall",method_version="1.0.7",implementation="native",
 provenance=list(parameters=cfg,input_sha256=hash(input),database_sha256=dbhash,
 evidence="原生LR表达与受体下游TF regulon富集整合；extended仅选择CellCall扩展数据库，不能冒称独立CellCallEXT软件",
 zero_semantics="原生内部GSEA错误可被软件归零；零分不等同无通讯，不给LR分数添加P/FDR；原生warning和对象保留"),tables=list())
add<-function(id,type,df,definition,...){fn<-paste0(id,".tsv");wt(df,fn);bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=fn,sha256=hash(file.path(out,fn)),value_definition=definition),list(...))}
allrows<-list();warnings_seen<-character()
for(si in seq_along(unique(meta$sample))){
 sample<-unique(meta$sample)[si];m<-meta[meta$sample==sample,,drop=FALSE]
 if(length(unique(m$donor))!=1||length(unique(m$condition))!=1) stop("一个sample必须对应一个供体和条件")
 counts<-table(m$cell_type);m<-m[m$cell_type %in% names(counts[counts>=(cfg$min_cells %||% 10L)]),,drop=FALSE]
 types<-unique(m$cell_type);if(length(types)<2) stop("合格细胞群少于2")
 safe<-setNames(sprintf("CT%03d",seq_along(types)),types);inverse<-setNames(types,safe)
 dat<-as.data.frame(as.matrix(expr[,rownames(m),drop=FALSE]));colnames(dat)<-paste0("cell",seq_len(ncol(dat)),"_",safe[m$cell_type])
 wt(data.frame(original_cell=rownames(m),native_cell=colnames(dat),cell_type=m$cell_type,native_group=safe[m$cell_type]),paste0("identity_map_",si,".tsv"))
 if(!is.null(reuse)){
   record<-old$native_objects[[as.character(si)]]
   if(is.null(record)||record$sample!=sample) stop("缺少匹配的原生样本对象")
   native_path<-file.path(reuse,record$path)
   if(hash(native_path)!=record$sha256) stop("原生对象哈希不匹配")
   obj<-readRDS(native_path)
   if(!identical(obj@data$count,dat)) stop("原生对象的表达与细胞映射不匹配")
 }else{
  set.seed(cfg$seed %||% 1L)
  obj<-cellcall::CreateNichConObject(dat,names.field=2,names.delim="_",source=cfg$source,Org=org,project=cfg$dataset)
  obj<-withCallingHandlers(cellcall::TransCommuProfile(obj,pValueCor=cfg$pValueCor %||% .05,CorValue=cfg$CorValue %||% .1,
   topTargetCor=cfg$topTargetCor %||% 1,p.adjust=cfg$alpha %||% .05,use.type=cfg$use_type %||% "median",
   probs=cfg$probs %||% .75,method=cfg$regulon_method %||% "weighted",Org=org,IS_core=core),
   warning=function(w){warnings_seen<<-c(warnings_seen,conditionMessage(w))})
 }
 saveRDS(obj,file.path(out,paste0("cellcall_",si,".rds")))
 run_metadata$native_objects[[as.character(si)]]<-list(sample=sample,path=paste0("cellcall_",si,".rds"),sha256=hash(file.path(out,paste0("cellcall_",si,".rds"))))
 wj(run_metadata,"run_metadata.json")
 mat<-obj@data$expr_l_r
 if(!nrow(mat)||any(!is.finite(as.matrix(mat)))) stop("原生结果为空或非有限；保留日志，不生成假网络")
 # Native names contain '-' inside valid HGNC symbols; reconstruct identity from its exact resource mapping.
 triples<-do.call(rbind,lapply(resources[grepl("new_ligand",resources)],function(n) read.delim(system.file("extdata",n,package="cellcall"),check.names=FALSE)))
 pairs<-unique(triples[,c("Ligand_Symbol","Receptor_Symbol")]);pairid<-paste(pairs$Ligand_Symbol,pairs$Receptor_Symbol,sep="-")
 if(anyDuplicated(pairid)||!all(rownames(mat) %in% pairid)) stop("原生LR拼接身份存在歧义")
 rows<-list()
 for(j in seq_len(nrow(mat))) for(k in seq_len(ncol(mat))){
   p<-pairs[match(rownames(mat)[j],pairid),];ab<-strsplit(colnames(mat)[k],"-",fixed=TRUE)[[1]]
   rows[[length(rows)+1]]<-data.frame(sample=sample,donor=unique(m$donor),condition=unique(m$condition),source=inverse[ab[1]],target=inverse[ab[2]],
      ligand=p$Ligand_Symbol,receptor=p$Receptor_Symbol,interaction=rownames(mat)[j],score=mat[j,k],tested=TRUE,supported=mat[j,k]>0)
 }
 allrows[[si]]<-do.call(rbind,rows)
 tf<-obj@data$regulons_matrix;grid<-expand.grid(row=rownames(tf),column=colnames(tf));grid$value<-as.vector(as.matrix(tf));grid$column<-inverse[grid$column]
 add(paste0("regulons_",si),"matrix",grid,"CellCall原生筛选后的TF regulon正向NES；零包括未过筛选和无法估计，不是TF无活性",axis_label="Retained regulon NES",value_kind="native_score")
 for(g in names(obj@data$gsea.list)){
   gs<-obj@data$gsea.list[[g]]
   if(isS4(gs)&&"result" %in% slotNames(gs)) wt(gs@result,paste0("native_gsea_",si,"_",g,".tsv"))
 }
 totals<-colSums(mat);chosen<-names(sort(totals,decreasing=TRUE))[seq_len(min(cfg$top_cell_pairs %||% 3L,sum(totals>0)))]
 for(pi in seq_along(chosen)){
   ab<-strsplit(chosen[pi],"-",fixed=TRUE)[[1]]
   mechanism<-cellcall::LR2TF(obj,sender_cell=ab[1],recevier_cell=ab[2],slot="expr_l_r",org=org,IS_core=core)@reductions$sankey
   if(!all(paste(mechanism$Ligand,mechanism$Receptor,sep="-") %in% rownames(mat))) stop("原生LR2TF存在分子身份解析歧义，禁止绘制错误机制图")
   wt(mechanism,paste0("native_lr_tf_",si,"_",pi,".tsv"))
   # LR score and distance-weighted TF NES have different units; equal-width topology preserves both as separate attributes.
   edges<-unique(rbind(data.frame(source=mechanism$Ligand,target=mechanism$Receptor,source_type="ligand",target_type="receptor",value=1),
     data.frame(source=mechanism$Receptor,target=mechanism$TF,source_type="receptor",target_type="TF",value=1)))
   add(paste0("mechanism_",si,"_",pi),"molecular_links",edges,paste0(inverse[ab[1]]," → ",inverse[ab[2]],"：CellCall原生LR2TF去重关系；等宽表示存在关系，两类不同单位的原生权重保存在native_lr_tf表，不声称流量守恒"),value_kind="count")
 }
}
add("ligand_receptor","lr_edges",do.call(rbind,allrows),"CellCall原生表达权重×下游regulon整合分数；supported表示原生正分数筛选，不是LR检验显著；tested仅表示原生评分范围",value_kind="nonnegative_strength",additive=TRUE,direction="higher",axis_label="CellCall score",candidate_scope="native_retained_only")
wj(unique(warnings_seen),"native_warnings.json");wj(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
