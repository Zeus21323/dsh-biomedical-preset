#!/usr/bin/env Rscript
# Project-owned native NicheNet adapter. No model/network data is vendored.
options(stringsAsFactors = FALSE, warn = 1)
`%||%` <- function(x,y) if (is.null(x)) y else x
args <- commandArgs(TRUE)
if (length(args) != 2L) stop("用法: Rscript run_nichenet.R 配置.json 新输出目录")
for (pkg in c("nichenetr","jsonlite","digest","Matrix")) if (!requireNamespace(pkg,quietly=TRUE)) stop("缺少 R 包: ",pkg)
if (as.character(packageVersion("nichenetr")) != "2.2.1.1") stop("需要已核验 nichenetr 2.2.1.1")
cfg_path <- normalizePath(args[1]); cfg <- jsonlite::read_json(cfg_path,simplifyVector=TRUE)
resolve <- function(x) normalizePath(if (startsWith(x,"/")) x else file.path(dirname(cfg_path),x),mustWork=TRUE)
for (key in c("dataset","research_question","input","lr_network","ligand_target_matrix","gene_set","gene_set_definition","receiver","network_version")) if (is.null(cfg[[key]])) stop("缺配置: ",key)
input <- resolve(cfg$input); lr_path <- resolve(cfg$lr_network); lt_path <- resolve(cfg$ligand_target_matrix); gs_path <- resolve(cfg$gene_set)
if (file.exists(args[2])) stop("输出已存在，拒绝覆盖")
candidate_out <- normalizePath(dirname(path.expand(args[2])),mustWork=FALSE)
while (nzchar(candidate_out) && candidate_out!="/") {
  if (file.exists(file.path(candidate_out,".git"))) stop("真实分析输出必须在Git外")
  candidate_out <- dirname(candidate_out)
}
dir.create(args[2],recursive=TRUE);out <- normalizePath(args[2])
write_json <- function(x,name) jsonlite::write_json(x,file.path(out,name),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
write_table <- function(x,name) write.table(x,file.path(out,name),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
hash <- function(p) digest::digest(file=p,algo="sha256")
write_json(cfg,"run_config.json")
x <- readRDS(input);expr <- x$expression;meta <- x$metadata
if (is.null(expr) || is.null(meta) || anyDuplicated(rownames(expr)) || anyDuplicated(colnames(expr)) || anyDuplicated(rownames(meta))) stop("RDS 需有唯一基因/细胞 expression 和 metadata")
if (!setequal(colnames(expr),rownames(meta))) stop("表达与 metadata 细胞不匹配")
meta <- meta[colnames(expr),,drop=FALSE]
if (!all(c("cell_type","sample","donor","condition") %in% colnames(meta)) || anyNA(meta[,c("cell_type","sample","donor","condition")])) stop("缺少样本/供体/条件/细胞类型")
v <- if (inherits(expr,"sparseMatrix")) expr@x else as.vector(expr)
if (any(!is.finite(v)) || any(v<0)) stop("表达必须有限非负")
if (!cfg$expression_scale %in% c("counts","normalized","log_normalized")) stop("需明确表达层语义")
receivers <- which(meta$cell_type==cfg$receiver)
senders <- cfg$senders %||% setdiff(unique(meta$cell_type),cfg$receiver)
if (!length(senders) || !all(senders %in% meta$cell_type) || length(receivers)<(cfg$min_cells %||% 10L)) stop("发送/接收群不适用")
lr <- readRDS(lr_path);lt <- readRDS(lt_path)
if (!all(c("from","to") %in% colnames(lr)) || is.null(rownames(lt)) || is.null(colnames(lt))) stop("原生LR/ligand-target先验格式不符")
fraction <- cfg$expression_fraction %||% .1
expressed <- function(cells) rownames(expr)[Matrix::rowMeans(expr[,cells,drop=FALSE]>0)>=fraction]
receiver_genes <- expressed(receivers)
sender_genes <- unique(unlist(lapply(senders,function(s) expressed(which(meta$cell_type==s)))))
background <- intersect(receiver_genes,rownames(lt))
genes <- unique(scan(gs_path,what=character(),quiet=TRUE))
excluded_genes <- setdiff(genes,background);genes <- intersect(genes,background)
if (length(genes)<5 || length(setdiff(background,genes))<5) stop("响应基因集或合适背景过少；不能生成可信活性排名")
potential <- intersect(unique(lr$from[lr$from %in% sender_genes & lr$to %in% receiver_genes]),colnames(lt))
if (!length(potential)) stop("没有发送端配体和接收端受体共同支持的先验候选")
activities <- nichenetr::predict_ligand_activities(geneset=genes,background_expressed_genes=background,ligand_target_matrix=lt,potential_ligands=potential)
activities <- activities[order(-activities$aupr_corrected,activities$test_ligand),]
selected <- head(activities$test_ligand,cfg$top_ligands %||% 20L)
links <- do.call(rbind,lapply(selected,function(lig) nichenetr::get_weighted_ligand_target_links(ligand=lig,geneset=genes,ligand_target_matrix=lt,n=cfg$top_targets %||% 100L)))
write_table(activities,"native_activities.tsv");write_table(links,"native_target_links.tsv")
write_json(list(selected_ligands=selected,gene_set=genes,background=background,excluded_response_genes=excluded_genes,
  rule="接收端响应相对背景的原生corrected AUPR排序；表达筛选仅支持候选，不等同真实分泌/受体激活"),"selection.json")
bundle <- list(schema_version=2,dataset=cfg$dataset,method="NicheNet",method_version=as.character(packageVersion("nichenetr")),implementation="native",
  provenance=list(parameters=cfg,input_sha256=hash(input),lr_network_sha256=hash(lr_path),ligand_target_sha256=hash(lt_path),gene_set_sha256=hash(gs_path),
    statistical_unit="response_program; no donor condition-difference test",network_version=cfg$network_version),tables=list())
add <- function(id,type,table,definition,...) {
  filename <- paste0(id,".tsv");write_table(table,filename)
  bundle$tables[[length(bundle$tables)+1L]] <<- c(list(id=id,type=type,path=filename,sha256=hash(file.path(out,filename)),value_definition=definition),list(...))
}
add("ligand_activity","activities",data.frame(ligand=activities$test_ligand,value=activities$aupr_corrected),
    "NicheNet 原生 corrected AUPR；允许负值。输入响应程序与表达背景明确，不是通讯概率。",axis_label="Corrected AUPR",direction="higher",value_kind="activity")
add("ligand_target","matrix",data.frame(row=links$target,column=links$ligand,value=links$weight),
    "原生 ligand-target regulatory potential；没有导出的连接为缺失，不补成零",axis_label="Regulatory potential",value_kind="native_score")
add("target_links","molecular_links",data.frame(source=links$ligand,target=links$target,source_type="ligand",target_type="target",value=links$weight),
    "NicheNet ligand-target 预测关联；不意味着完整 receptor-TF-target 路径已观测",value_kind="native_score",additive=FALSE)
lr_selected <- unique(lr[lr$from %in% selected & lr$to %in% receiver_genes,c("from","to")])
add("ligand_receptor_prior","molecular_links",data.frame(source=lr_selected$from,target=lr_selected$to,source_type="ligand",target_type="receptor",value=1),
    "表达相容的原生LR先验；边等宽表示存在先验，不代表活性强度",value_kind="count",additive=FALSE)
saveRDS(list(activities=activities,links=links,selected=selected,lr=lr_selected,config=cfg),file.path(out,"nichenet_results.rds"))
capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
write_json(bundle,"bundle.json")
cat("NicheNet 原生推断完成；bundle.json 可由通讯结果包绘图器直接生成图集。\n")
