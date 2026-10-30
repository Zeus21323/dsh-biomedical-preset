#!/usr/bin/env Rscript
# Native SpaTalk 1.0, ZJUFanLab/SpaTalk@c86829c42008fb059eba75bec1eec523378e8da6.
# Requires SpaTalk, Matrix, jsonlite, digest; install the fixed source, not a moving HEAD.
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
args<-commandArgs(TRUE)
if(length(args)!=2) stop("用法：Rscript run_spatalk.R 配置.json 新输出目录")
for(p in c("SpaTalk","Matrix","jsonlite","digest")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
if(as.character(packageVersion("SpaTalk"))!="1.0") stop("需要已核验的 SpaTalk 1.0")
suppressPackageStartupMessages(library(SpaTalk))
config<-normalizePath(args[1]);cfg<-jsonlite::read_json(config,simplifyVector=TRUE)
for(k in c("dataset","input","species","expression_scale","resolution","coordinate_unit","coordinate_provenance")) if(is.null(cfg[[k]])) stop("缺少配置：",k)
if(cfg$resolution!="single_cell") stop("此执行分支需要真实单细胞空间数据；spot 必须先提供经过核验的原生解卷积对象，不能把 spot 当细胞")
if(!cfg$species %in% c("human","mouse")||cfg$expression_scale!="counts") stop("需要 human/mouse 和原始非负整数 counts")
if(!cfg$coordinate_unit %in% c("um","pixel","native")) stop("空间单位不明确")
if(cfg$coordinate_unit=="native"&&!isTRUE(cfg$physical_scale_unavailable)) stop("未校准坐标必须声明物理比例不可用")
input<-normalizePath(if(startsWith(cfg$input,"/")) cfg$input else file.path(dirname(config),cfg$input))
if(file.exists(args[2])) stop("拒绝覆盖输出")
parent<-normalizePath(dirname(args[2]),mustWork=FALSE)
while(parent!="/") {if(file.exists(file.path(parent,".git"))) stop("分析产物必须在Git外");parent<-dirname(parent)}
dir.create(args[2],recursive=TRUE);out<-normalizePath(args[2])
hash<-function(p) digest::digest(file=p,algo="sha256")
write_json<-function(x,n) jsonlite::write_json(x,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
write_table<-function(x,n) write.table(x,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.data.frame(expr)) expr<-as.matrix(expr)
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))) stop("表达和元数据必须有唯一基因/细胞ID")
if(!setequal(colnames(expr),rownames(meta))) stop("表达与元数据细胞ID不一致")
meta<-meta[colnames(expr),,drop=FALSE]
fields<-c("sample","donor","condition","cell_type","x","y")
if(!all(fields %in% names(meta))||anyNA(meta[,fields])) stop("缺少实际样本/供体/条件/细胞类型/坐标；未提供供体应显式标明未知，不得编造重复")
if(any(!is.finite(as.matrix(meta[,c("x","y")])))) stop("坐标非有限")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(expr)
if(any(!is.finite(v))||any(v<0)||any(abs(v-round(v))>1e-7)) stop("counts必须为有限非负整数")
permutations<-cfg$n_perms %||% 1000L
if(permutations<100) stop("至少100次原生置换，需报告置换分辨率")
write_json(cfg,"run_config.json")
resources<-new.env();data("lrpairs",package="SpaTalk",envir=resources);data("pathways",package="SpaTalk",envir=resources)
saveRDS(as.list(resources),file.path(out,"database.rds"))
bundle<-list(schema_version=2,dataset=cfg$dataset,method="SpaTalk",method_version="1.0",implementation="native",
  provenance=list(input_sha256=hash(input),database_sha256=hash(file.path(out,"database.rds")),parameters=cfg,
    coordinate_provenance=cfg$coordinate_provenance,test_unit="Native spatial-proximity cell permutation, not independent-donor comparison",
    result_scope="Native retained LR/path candidates only; omitted hypotheses and full-family FDR unavailable from this API",
    software_commit="c86829c42008fb059eba75bec1eec523378e8da6"),tables=list())
add<-function(id,type,rows,definition,...) {
  write_table(rows,paste0(id,".tsv"))
  bundle$tables[[length(bundle$tables)+1]]<<-c(list(id=id,type=type,path=paste0(id,".tsv"),sha256=hash(file.path(out,paste0(id,".tsv"))),value_definition=definition),list(...))
}
spatial<-list(coordinate_unit=cfg$coordinate_unit,coordinate_provenance=cfg$coordinate_provenance,
  physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable),y_down=isTRUE(cfg$y_down))
selections<-list();all_lr<-list()
for(si in seq_along(unique(meta$sample))) {
  sample<-unique(meta$sample)[si];m<-meta[meta$sample==sample,,drop=FALSE]
  if(length(unique(m$donor))!=1||length(unique(m$condition))!=1) stop("每个空间样本应对应一个真实供体/条件或明确未知标签")
  sizes<-table(m$cell_type);m<-m[m$cell_type %in% names(sizes[sizes>=(cfg$min_cells %||% 10)]),,drop=FALSE]
  if(length(unique(m$cell_type))<2) stop("合格细胞群不足两个")
  counts<-expr[,rownames(m),drop=FALSE];set.seed(cfg$seed %||% 1L)
  obj<-SpaTalk::createSpaTalk(counts,data.frame(cell=rownames(m),x=m$x,y=m$y),
    species=if(cfg$species=="human") "Human" else "Mouse",if_st_is_sc=TRUE,spot_max_cell=1,celltype=as.character(m$cell_type))
  # Native label sanitation must not silently change cell identities in exports.
  if(!identical(as.character(obj@meta$rawmeta$celltype),as.character(m$cell_type))) stop("SpaTalk重命名了细胞类型；请提供不触发原生重命名的明确标签映射")
  obj<-SpaTalk::find_lr_path(obj,resources$lrpairs,resources$pathways,max_hop=cfg$max_hop,if_doParallel=FALSE,use_n_cores=1)
  obj<-SpaTalk::dec_cci_all(obj,n_neighbor=cfg$n_neighbor %||% 10,min_pairs=cfg$min_pairs %||% 5,
    min_pairs_ratio=cfg$min_pairs_ratio %||% 0,per_num=permutations,pvalue=cfg$alpha %||% .05,
    co_exp_ratio=cfg$co_exp_ratio %||% .1,if_doParallel=FALSE,use_n_cores=1)
  saveRDS(obj,file.path(out,paste0("spatalk_",si,".rds")))
  lr<-obj@lrpair;write_table(lr,paste0("native_lr_",si,".tsv"));write_table(obj@tf,paste0("native_tf_",si,".tsv"))
  rows<-data.frame(sample=character(),donor=character(),condition=character(),source=character(),target=character(),ligand=character(),receptor=character(),score=numeric(),p_value=numeric(),tested=logical(),supported=logical())
  if(nrow(lr)) rows<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=lr$celltype_sender,target=lr$celltype_receiver,
    ligand=lr$ligand,receptor=lr$receptor,score=lr$score,p_value=lr$lr_co_ratio_pvalue,tested=TRUE,supported=lr$lr_co_ratio_pvalue<(cfg$alpha %||% .05))
  all_lr[[si]]<-rows
  if(nrow(obj@tf)) {
    tf<-obj@tf
    add(paste0("receptor_tf_",si),"matrix",data.frame(row=paste(tf$receptor,tf$tf,sep=" → "),column=paste(tf$celltype_sender,tf$celltype_receiver,sep=" → "),value=tf$score),
      "SpaTalk原生接收端receptor–TF胞内评分，不能与LR联合评分相加。",axis_label="Native intracellular score",value_kind="native_score")
  }
  if(nrow(lr)) {
    selected<-head(lr[order(-lr$score,lr$ligand,lr$receptor),],cfg$top_paths %||% 3)
    for(j in seq_len(nrow(selected))) {
      r<-selected[j,];pair<-obj@cellpair[[paste0(r$celltype_sender," -- ",r$celltype_receiver)]]
      # Retain the actual native neighbourhood pairs and exact gene coexpression.
      saveRDS(pair,file.path(out,paste0("native_cell_pairs_",si,"_",j,".rds")))
      pathway<-tryCatch(SpaTalk::get_lr_path(obj,r$celltype_sender,r$celltype_receiver,r$ligand,r$receptor),error=function(e) list(error=conditionMessage(e)))
      saveRDS(pathway,file.path(out,paste0("native_pathway_",si,"_",j,".rds")))
      selections[[length(selections)+1]]<-list(sample=sample,ligand=r$ligand,receptor=r$receptor,source=r$celltype_sender,target=r$celltype_receiver,pathway_error=pathway$error)
      if(!is.null(pathway$tf_path)&&nrow(pathway$tf_path)) {
        path<-pathway$tf_path
        is_tf<-unique(c(path$src[path$src_tf=="YES"],path$dest[path$dest_tf=="YES"]))
        node_type<-function(g) if(g==r$receptor) "receptor" else if(g %in% is_tf) "TF" else if(g %in% path$src) "signaling" else "target"
        links<-data.frame(source=c(r$ligand,path$src),target=c(r$receptor,path$dest),
          source_type=c("ligand",vapply(path$src,node_type,character(1))),target_type=c("receptor",vapply(path$dest,node_type,character(1))),
          value=1,evidence_type=c("native_LR_candidate",rep("native_pathway_with_expression_support",nrow(path))),
          native_coexpression_fraction=c(NA_real_,path$co_ratio))
        links<-unique(links)
        add(paste0("mechanism_",si,"_",j),"molecular_links",links,
          paste0(sample,": ",r$celltype_sender," → ",r$celltype_receiver,"，SpaTalk原生筛选的LR及下游TF/target关联；线宽统一为存在标记1，不把LR联合评分和胞内共表达比例混合。原生路径/Fisher结果另存，不解释为实验因果。"),
          value_kind="native_score",axis_label="Native association present",additive=FALSE)
      }
      expressed<-as.numeric(counts[r$ligand,pair$cell_sender])>0 & as.numeric(counts[r$receptor,pair$cell_receiver])>0
      spatial_edges<-data.frame(sample=rep(sample,sum(expressed)),source_cell=pair$cell_sender[expressed],target_cell=pair$cell_receiver[expressed],value=rep(1,sum(expressed)))
      do.call(add,c(list(id=paste0("lr_locations_",si,"_",j),type="spatial_edges",rows=spatial_edges,
        definition=paste0(r$ligand," → ",r$receptor,": 原生k近邻细胞对中的配体/受体共同检测；箭头表示所选sender/receiver角色，并非传输方向或边级显著性。"),value_kind="count"),spatial))
      # Plot measured gene detection, not a fabricated spatial flux or edge weight.
      for(gene in unique(c(r$ligand,r$receptor))) {
        points<-data.frame(sample=sample,cell=rownames(m),x=m$x,y=m$y,value=as.numeric(counts[gene,]))
        do.call(add,c(list(id=paste0("location_",si,"_",j,"_",which(unique(c(r$ligand,r$receptor))==gene)),type="spatial_points",rows=points,
          definition=paste0(gene," 的原始空间检测计数，提供所选LR的表达支持；不是局部通讯后验。"),axis_label=paste(gene,"counts"),value_kind="count"),spatial))
      }
    }
  }
}
add("lr_edges","lr_edges",do.call(rbind,all_lr),"SpaTalk原生空间LR联合评分与邻近置换P；仅导出原生保留候选，不从筛后P重算全家族FDR，未保留不代表零。",value_kind="native_score",direction="higher",additive=FALSE,axis_label="SpaTalk combined score",candidate_scope="native_retained_only")
write_json(selections,"path_selection.json");write_json(bundle,"bundle.json")
capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
