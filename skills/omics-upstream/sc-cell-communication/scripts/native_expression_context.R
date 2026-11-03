# Shared input/provenance contract for the native R expression-based adapters.
`%||%` <- function(x,y) if(is.null(x)) y else x
native_expression_context <- function(args, method, package, version, counts_input=FALSE, species="human") {
  if(length(args)!=2) stop("需要配置JSON与新的仓库外输出目录")
  if(!requireNamespace("jsonlite",quietly=TRUE)) stop("缺少jsonlite")
  c<-new.env(parent=parent.frame());c$cp<-normalizePath(args[1]);c$cfg<-jsonlite::read_json(c$cp,simplifyVector=TRUE)
  if(!is.null(c$cfg$r_library)){
    lib<-normalizePath(if(startsWith(c$cfg$r_library,"/")) c$cfg$r_library else file.path(dirname(c$cp),c$cfg$r_library))
    .libPaths(c(lib,.libPaths()))
  }
  for(p in c(package,"Matrix","digest")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少原生依赖：",p)
  if(as.character(packageVersion(package))!=version) stop("需要已核验版本：",package," ",version)
  for(k in c("dataset","research_question","input","species","expression_scale","normalization_definition")) if(is.null(c$cfg[[k]])) stop("缺少：",k)
  if(!c$cfg$species %in% species) stop("此原生数据库分支只核验",paste(species,collapse="/"),"；不自动作同源替换")
  scales<-if(counts_input) "counts" else c("normalized","log_normalized")
  if(!c$cfg$expression_scale %in% scales) stop("输入尺度与原生方法不符：需要",paste(scales,collapse="/"))
  c$resolve<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(c$cp),p))
  c$input<-c$resolve(c$cfg$input);x<-readRDS(c$input);c$expr<-if(counts_input) x$counts else x$expression;c$meta<-x$metadata
  if(is.null(c$expr)||is.null(c$meta)||is.null(rownames(c$expr))||is.null(colnames(c$expr))||anyDuplicated(rownames(c$expr))||anyDuplicated(colnames(c$expr))||anyDuplicated(rownames(c$meta))||!setequal(colnames(c$expr),rownames(c$meta))) stop("需要身份唯一且对齐的基因×细胞expression与metadata")
  c$meta<-c$meta[colnames(c$expr),,drop=FALSE];need<-c("sample","donor","condition","cell_type")
  if(!all(need %in% names(c$meta))||anyNA(c$meta[,need])||any(trimws(as.matrix(c$meta[,need]))=="")) stop("元数据字段不完整；未知供体须显式记录unknown，不补造独立供体")
  for(s in unique(c$meta$sample)) if(length(unique(c$meta$donor[c$meta$sample==s]))!=1||length(unique(c$meta$condition[c$meta$sample==s]))!=1) stop("一个样本必须唯一对应供体和条件")
  v<-if(inherits(c$expr,"sparseMatrix")) c$expr@x else as.vector(as.matrix(c$expr))
  if(any(!is.finite(v))||any(v<0)||!any(v>0)) stop("表达必须有限非负且含信号")
  if(counts_input&&any(v!=round(v))) stop("原生计数分支要求未归一化的整数计数")
  c$minimum<-as.integer(c$cfg$min_cells %||% 10L)
  if(is.na(c$minimum)||c$minimum<2) stop("min_cells须至少2")
  if(file.exists(args[2])) stop("拒绝覆盖已有输出")
  parent<-normalizePath(dirname(args[2]),mustWork=FALSE)
  while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("真实分析输出必须位于Git外");parent<-dirname(parent)}
  dir.create(args[2],recursive=TRUE);c$out<-normalizePath(args[2])
  c$hash<-function(p) digest::digest(file=p,algo="sha256")
  c$wj<-function(v,n) jsonlite::write_json(v,file.path(c$out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
  c$wt<-function(v,n){
    v<-as.data.frame(v,check.names=FALSE)
    # write.table uses 15 significant digits internally. Formatting explicitly
    # retains near-saturated native doubles whose ranks can change on rounding.
    for(k in names(v)) if(is.numeric(v[[k]])) v[[k]]<-format(v[[k]],digits=17,scientific=TRUE,trim=TRUE)
    write.table(v,file.path(c$out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
  }
  c$bundle<-list(schema_version=2,dataset=c$cfg$dataset,method=method,method_version=version,implementation="native",
    provenance=list(input_sha256=c$hash(c$input),parameters=c$cfg,species=c$cfg$species,expression_scale=c$cfg$expression_scale,
      molecule_identity_schema="hgnc-complete-complex-v1"),tables=list())
  c$add<-function(id,type,rows,definition,...){
    fn<-paste0(id,".tsv");c$wt(rows,fn)
    c$bundle$tables[[length(c$bundle$tables)+1]]<-c(list(id=id,type=type,path=fn,sha256=c$hash(file.path(c$out,fn)),value_definition=definition),list(...))
  }
  c$sample_meta<-function(s){
    m<-c$meta[c$meta$sample==s,,drop=FALSE];sizes<-table(m$cell_type)
    m<-m[m$cell_type %in% names(sizes[sizes>=c$minimum]),,drop=FALSE]
    if(length(unique(m$cell_type))<2) stop("样本",s,"合格细胞类型不足2")
    m
  }
  c$start_cache<-function(resource_hash,parameters){
    c$signature<-digest::digest(list(input=c$hash(c$input),resource=resource_hash,method=method,version=version,parameters=parameters),algo="sha256")
    c$reuse<-NULL;c$objects<-list()
    if(!is.null(c$cfg$reuse_directory)){
      c$reuse<-c$resolve(c$cfg$reuse_directory);c$old<-jsonlite::read_json(file.path(c$reuse,"run_metadata.json"),simplifyVector=FALSE)
      if(!identical(c$signature,c$old$signature)) stop("原生复用的输入、资源或科学参数变化")
    }
  }
  c$native<-function(index,sample,compute){
    fn<-paste0("native_",index,".rds")
    if(is.null(c$reuse)) { obj<-compute();saveRDS(obj,file.path(c$out,fn)) } else {
      record<-c$old$objects[[as.character(index)]]
      if(is.null(record)||record$sample!=sample||record$sha256!=c$hash(file.path(c$reuse,fn))) stop("原生对象摘要或样本不符")
      obj<-readRDS(file.path(c$reuse,fn));file.copy(file.path(c$reuse,fn),file.path(c$out,fn))
    }
    c$objects[[as.character(index)]]<-list(sample=sample,path=fn,sha256=c$hash(file.path(c$out,fn)))
    c$wj(list(signature=c$signature,objects=c$objects),"run_metadata.json")
    obj
  }
  c$wj(c$cfg,"run_config.json")
  c
}
