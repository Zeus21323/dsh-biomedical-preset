#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
`%||%`<-function(x,y) if(is.null(x)) y else x
a<-commandArgs(TRUE);if(length(a)!=2) stop("用法：Rscript run_functional_scores.R 配置.json 新输出目录")
for(p in c("UCell","Matrix","BiocParallel","jsonlite","digest")) if(!requireNamespace(p,quietly=TRUE)) stop("缺少包：",p)
if(as.character(packageVersion("UCell"))!="2.10.1") stop("需要已核验的原生UCell 2.10.1")
cp<-normalizePath(a[1]);cfg<-jsonlite::read_json(cp,simplifyVector=TRUE)
for(k in c("dataset","research_question","input","gmt","species","gene_set_species","gene_set_version","gene_set_provenance","expression_scale")) if(is.null(cfg[[k]])) stop("缺少：",k)
if(cfg$species!=cfg$gene_set_species) stop("表达和签名物种不一致")
if(!cfg$expression_scale %in% c("counts","normalized","log_normalized")) stop("需明确非负表达层语义，不使用整合残差")
resolve<-function(p) normalizePath(if(startsWith(p,"/")) p else file.path(dirname(cp),p))
input<-resolve(cfg$input);gmt<-resolve(cfg$gmt);x<-readRDS(input);expr<-x$expression;meta<-x$metadata
if(is.null(expr)||is.null(meta)||anyDuplicated(rownames(expr))||anyDuplicated(colnames(expr))||anyDuplicated(rownames(meta))||!setequal(colnames(expr),rownames(meta))) stop("需要基因×细胞expression与逐细胞metadata，身份唯一且对齐")
meta<-meta[colnames(expr),,drop=FALSE];need<-c("sample","donor","condition","cell_type")
if(!all(need %in% names(meta))||anyNA(meta[,need])||any(trimws(as.matrix(meta[,need]))=="")) stop("供体/样本/条件/细胞类型不完整；未知供体不能假造编号")
for(s in unique(meta$sample)) if(length(unique(meta$donor[meta$sample==s]))!=1||length(unique(meta$condition[meta$sample==s]))!=1) stop("样本不唯一对应供体/条件")
v<-if(inherits(expr,"sparseMatrix")) expr@x else as.vector(as.matrix(expr))
if(any(!is.finite(v))||any(v<0)) stop("表达必须有限非负")
if(cfg$expression_scale=="counts"&&any(abs(v-round(v))>1e-7)) stop("counts含非整数")
lines<-strsplit(readLines(gmt,warn=FALSE),"\t",fixed=TRUE)
if(!length(lines)||any(lengths(lines)<3)) stop("GMT为空或条目不足")
labels<-vapply(lines,`[`,character(1),1L);if(anyDuplicated(labels)||any(!nzchar(labels))) stop("签名名称为空或重复")
genes<-lapply(lines,function(v) unique(v[seq.int(3,length(v))]))
if(any(!nzchar(unlist(genes)))||any(grepl("[-+]$",unlist(genes)))) stop("此分支为事先定义的正向基因集；带正负后缀的签名需另行明确语义")
names(genes)<-sprintf("S%03d",seq_along(genes));coverage<-vapply(genes,function(g) mean(g %in% rownames(expr)),numeric(1))
minimum<-cfg$min_coverage %||% .7
if(!is.numeric(minimum)||length(minimum)!=1||minimum<=0||minimum>1) stop("min_coverage需在(0,1]")
if(any(coverage<minimum)) stop("基因集测量覆盖不足；不能静默删去缺失基因抬高评分：",paste(labels[coverage<minimum],collapse=", "))
rank<-as.integer(cfg$max_rank %||% min(1500L,nrow(expr)))
if(is.na(rank)||rank<2||rank>nrow(expr)||any(lengths(genes)>rank)) stop("max_rank须在实测基因范围内且不小于签名长度")
if(file.exists(a[2])) stop("拒绝覆盖输出")
parent<-normalizePath(dirname(a[2]),mustWork=FALSE);while(parent!="/"){if(file.exists(file.path(parent,".git"))) stop("真实分析输出必须位于Git外");parent<-dirname(parent)}
dir.create(a[2],recursive=TRUE);out<-normalizePath(a[2]);hash<-function(p) digest::digest(file=p,algo="sha256")
wj<-function(v,n) jsonlite::write_json(v,file.path(out,n),auto_unbox=TRUE,pretty=TRUE,na="null",null="null")
wt<-function(v,n) write.table(v,file.path(out,n),sep="\t",quote=FALSE,row.names=FALSE,na="NA")
wj(cfg,"run_config.json");warning_messages<-character()
# Native missing-gene handling is retained. Missing genes get the original
# matrix minimum; require that minimum to be zero to avoid inflated ranks.
if(any(!unlist(genes) %in% rownames(expr))&&min(expr)!=0) stop("签名有缺失基因但输入最小表达非零；原生缺失填充值不等于0，不能隐瞒")
signature<-digest::digest(list(input=hash(input),gmt=hash(gmt),version="2.10.1",max_rank=rank,ties="average"),algo="sha256")
if(!is.null(cfg$reuse_directory)){
  previous<-resolve(cfg$reuse_directory);info<-jsonlite::read_json(file.path(previous,"run_metadata.json"),simplifyVector=TRUE)
  if(!identical(info$signature,signature)||!identical(info$native_sha256,hash(file.path(previous,"native_scores.rds")))) stop("输入、签名、评分设置或原生分数摘要变化，不能复用")
  scores<-readRDS(file.path(previous,"native_scores.rds"));file.copy(file.path(previous,"native_scores.rds"),file.path(out,"native_scores.rds"))
}else{
  scores<-withCallingHandlers(UCell::ScoreSignatures_UCell(matrix=expr,features=genes,maxRank=rank,name="",ncores=1,
    BPPARAM=BiocParallel::SerialParam(),ties.method="average"),warning=function(w){warning_messages<<-c(warning_messages,conditionMessage(w));invokeRestart("muffleWarning")})
  saveRDS(scores,file.path(out,"native_scores.rds"))
}
if(!setequal(rownames(scores),rownames(meta))||!setequal(colnames(scores),names(genes))) stop("原生评分改变了细胞或签名身份")
scores<-as.matrix(scores[rownames(meta),names(genes),drop=FALSE]);if(any(!is.finite(scores))||any(scores<0|scores>1)) stop("原生UCell分数不是有限[0,1]值")
wt(data.frame(cell=rownames(scores),scores,check.names=FALSE),"cell_scores.tsv")
mapping<-data.frame(native_signature=names(genes),gene_set=labels,total_genes=lengths(genes),measured_fraction=coverage,
  missing_genes=vapply(genes,function(g) paste(setdiff(g,rownames(expr)),collapse=";"),character(1)))
wt(mapping,"gene_set_coverage.tsv");wt(data.frame(cell=rownames(meta),meta),"cell_metadata.tsv")
sample_rows<-list();excluded<-list()
for(s in unique(meta$sample)) for(ct in unique(meta$cell_type)){
  cells<-which(meta$sample==s&meta$cell_type==ct)
  if(length(cells)<(cfg$min_cells %||% 10L)){
    excluded[[length(excluded)+1]]<-data.frame(sample=s,cell_type=ct,n_cells=length(cells),reason="低于声明的每样本/细胞类型最小细胞数")
    next
  }
  for(i in seq_along(genes)) sample_rows[[length(sample_rows)+1]]<-data.frame(sample=s,donor=meta$donor[cells[1]],condition=meta$condition[cells[1]],cell_type=ct,
    feature=paste(labels[i],ct,sep=" | "),gene_set=labels[i],value=median(scores[cells,i]),n_cells=length(cells))
}
if(length(excluded)) wt(do.call(rbind,excluded),"excluded_sample_celltypes.tsv")
if(!length(sample_rows)) stop("没有合格样本/细胞类型，保留原生分数和排除原因")
samples<-do.call(rbind,sample_rows);wt(samples,"sample_scores.tsv")
groups<-split(seq_len(nrow(samples)),interaction(samples$donor,samples$condition,samples$feature,drop=TRUE,lex.order=TRUE))
donors<-do.call(rbind,lapply(groups,function(index){d<-samples[index,,drop=FALSE];data.frame(sample=paste(sort(d$sample),collapse=";"),donor=d$donor[1],condition=d$condition[1],
  feature=d$feature[1],gene_set=d$gene_set[1],cell_type=d$cell_type[1],value=mean(d$value),n_samples=nrow(d),n_cells=sum(d$n_cells))}))
wt(donors,"donor_scores.tsv");wj(list(signature=signature,native_sha256=hash(file.path(out,"native_scores.rds"))),"run_metadata.json")
bundle<-list(schema_version=2,dataset=cfg$dataset,method="UCell functional context",method_version="2.10.1",implementation="native",
  provenance=list(input_sha256=hash(input),gmt_sha256=hash(gmt),parameters=cfg,max_rank=rank,warnings=warning_messages,
    interpretation="事先定义签名在单细胞表达排名中的富集评分；不是测得的通路通量、LR结合、药敏或因果证据",
    aggregation="每样本/细胞类型先取细胞UCell中位数，再对同供体同条件的多个样本等权平均；不把细胞当供体重复"),
  tables=list(list(id="functional_scores",type="effects",path="donor_scores.tsv",sha256=hash(file.path(out,"donor_scores.tsv")),
    value_definition="原生UCell签名分数，先样本内中位数再供体内等权样本均值；点为供体，不自动添加细胞层P值",
    value_kind="native_score",axis_label="Donor UCell score",figure_role="functional_score",scale_group_field="gene_set",nonnegative=TRUE)))
wj(bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(out,"sessionInfo.txt"))
