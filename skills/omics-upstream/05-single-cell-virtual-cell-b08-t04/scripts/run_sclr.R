#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"scLR","scLR","0.9.6",counts_input=TRUE);cfg<-c$cfg
for(k in c("reference","comparison","design_provenance","database","database_provenance")) if(is.null(cfg[[k]])) stop("缺少：",k)
if(!isTRUE(cfg$independent_samples)||isTRUE(cfg$paired)||!is.null(cfg$covariates)) stop("scLR原生两组模型不支持配对、重复供体或协变量；需核实独立样本设计")
conditions<-c(cfg$reference,cfg$comparison)
if(length(unique(conditions))!=2||!setequal(unique(c$meta$condition),conditions)) stop("需明确两个实际条件和差异方向")
sm<-unique(c$meta[,c("sample","donor","condition")]);known<-sm$donor[!tolower(sm$donor) %in% c("unknown","unavailable","na","none")]
if(anyDuplicated(known)||any(table(sm$condition)<2)) stop("至少每条件2个独立样本，已知供体不可重复")
if(anyDuplicated(toupper(rownames(c$expr)))) stop("scLR原生大写转换造成基因身份冲突")
genes<-toupper(rownames(c$expr));c$wt(data.frame(original=rownames(c$expr),native=genes),"gene_identity_map.tsv")
dbfile<-c$resolve(cfg$database);db<-read.delim(dbfile,check.names=FALSE)
if(!all(c("ligand","receptor") %in% names(db))) stop("数据库TSV需ligand/receptor单基因符号列")
db<-unique(data.frame(ligand=toupper(db$ligand),receptor=toupper(db$receptor)))
if(anyNA(db)||any(trimws(as.matrix(db))=="")) stop("数据库包含空分子身份")
db$key<-paste(db$ligand,db$receptor,sep="-")
if(anyDuplicated(db$key)) stop("原生连字符LR键不唯一，不能拆分或猜测含连字符的基因")
db$measured<-db$ligand %in% genes & db$receptor %in% genes
c$wt(db,"resource_mapping.tsv")
if(!any(db$measured)) stop("数据库无完整可测LR")
sizes<-as.data.frame(table(sample=c$meta$sample,cell_type=c$meta$cell_type));sizes$eligible<-sizes$Freq>=c$minimum
sizes$condition<-sm$condition[match(sizes$sample,sm$sample)]
replicates<-aggregate(as.integer(sizes$eligible),sizes[,c("cell_type","condition")],sum);names(replicates)[3]<-"eligible_samples"
qualified<-names(which(tapply(replicates$eligible_samples,replicates$cell_type,min)>=2))
replicates$included<-replicates$cell_type %in% qualified
c$wt(replicates,"cell_type_condition_replication.tsv")
sizes$eligible<-sizes$eligible & sizes$cell_type %in% qualified
c$wt(sizes,"sample_cell_type_eligibility.tsv")
key<-function(s,t) paste(s,t,sep="\r")
keep<-key(c$meta$sample,c$meta$cell_type) %in% key(sizes$sample[sizes$eligible],sizes$cell_type[sizes$eligible])
meta<-c$meta[keep,,drop=FALSE];expr<-c$expr[,rownames(meta),drop=FALSE]
types<-unique(meta$cell_type)
if(length(types)<2||!setequal(unique(meta$sample),sm$sample)) stop("筛除低细胞数群后细胞类型或样本不足")
safe<-setNames(sprintf("CT%03d",seq_along(types)),types);back<-setNames(types,safe)
c$wt(data.frame(cell_type=types,native=unname(safe)),"cell_type_identity_map.tsv")
ci<-data.frame(sampleID=factor(meta$sample,levels=unique(meta$sample)),condition=factor(meta$condition,levels=conditions),cellcluster=unname(safe[meta$cell_type]),row.names=rownames(meta))
native_args<-list(low.filter=cfg$low_filter %||% 1,p.adjust.method="BH",Brep=as.integer(cfg$replicates %||% 1000),Brep0=as.integer(cfg$initial_replicates %||% 200),pv0=.05,p.filter=cfg$expression_quantile %||% .1,
  show.all=TRUE,parallel.use=FALSE,cpucores=1L,zero.impute=cfg$zero_impute %||% TRUE,adjust=3,rhos=0,normalization="ByALL",impute.miss.celltype=NA_real_,bntest=FALSE)
if(native_args$Brep<1000||native_args$Brep0<200||native_args$Brep0>native_args$Brep||native_args$p.filter<0||native_args$p.filter>=1||native_args$low.filter<0) stop("无效原生参数；正式推断至少1000次模拟、首阶段至少200次")
c$start_cache(c$hash(dbfile),list(args=native_args,reference=cfg$reference,comparison=cfg$comparison,min_cells=c$minimum,DESeq2=as.character(packageVersion("DESeq2")),limma=as.character(packageVersion("limma"))))
c$bundle$provenance$upstream<-list(commit="7e2d5eedb713b867414f563c24b2dce40cb07e70",url="https://github.com/cyhsuTN/scLR",paper="https://doi.org/10.1093/bioinformatics/btac294",license="GPL-2 | GPL-3")
c$bundle$provenance$native_semantics<-list(statistical_unit="independent sample",normalization="原始计数按样本×细胞类型求和；DESeq2 ByALL size factors，log2(normalized counts+1)",
  effect="comparison−reference：样本内L×R乘积均值差，非log fold change",inference="原生两阶段乘积分布Monte Carlo，rho=0，BH；保留原生4位效应和12位P/q精度，不重写零P",
  zero_imputation=if(native_args$zero.impute) "原生scXY对某条件全部样本为零的基因，在log2归一化后用Uniform(0,该样本细胞类型最小正值/4)替换；固定原生seed=2021；不是测量表达" else "disabled",
  sample_table="原生sumRawData是零值插补前的归一化端点；样本LR乘积仅作描述，不冒充插补后检验值",
  missing="低细胞数或缺失细胞类型保留NA；原生预过滤外的LR不补成零或不显著",
  secondary_tests="原生Welch/WRS缺失P可能被替换为1，仅保留在原生结果中，不作为规范推断")
native<-c$native(1L,"differential",function() do.call(scLR::scLR,c(list(countmatrix=expr,cellinfo=ci,lrpairs.sample=db[,c("ligand","receptor")]),native_args)))
d<-native$Rs;c$wt(d,"native_differential.tsv");c$wt(native$sumRawData,"native_pre_imputation_endpoints.tsv")
cells<-strsplit(d$lr.cell.name,"-",fixed=TRUE)
if(any(lengths(cells)!=2)||any(!unlist(cells) %in% names(back))) stop("原生细胞类型键无法精确回映")
di<-match(d$lr.gene.name,db$key);if(anyNA(di)) stop("原生LR身份不属于精确数据库键")
source<-unname(back[vapply(cells,`[`,character(1),1)]);target<-unname(back[vapply(cells,`[`,character(1),2)])
number<-function(z) suppressWarnings(as.numeric(as.character(z)))
p<-number(d$pvalue);q<-number(d$adj.p);effect<-number(d$obs.xy.diff);tested<-is.finite(p)&is.finite(q)&is.finite(effect)
expected_q<-round(p.adjust(p,"BH"),12)
if(!identical(is.na(q),is.na(expected_q))||any(abs(q-expected_q)>1e-12,na.rm=TRUE)) stop("原生BH与完整返回检验族不一致")
ids<-data.frame(source=source,target=target,ligand=db$ligand[di],receptor=db$receptor[di],ligand_identity=paste0("gene:",db$ligand[di]),receptor_identity=paste0("gene:",db$receptor[di]),interaction=d$lr.gene.name)
c$wt(data.frame(ids,tested=tested,native_reason=ifelse(tested,"tested",d$obs.xy.diff),p_value=p,q_value=q,value=effect),"differential_identity_map.tsv")
sample_order<-unname(unlist(native$sample.group));endpoints<-native$sumRawData
if(nrow(endpoints)!=nrow(ids)||ncol(endpoints)!=2*length(sample_order)) stop("原生样本端点维度不符")
expected_names<-make.names(c(paste0(sample_order,".L"),paste0(sample_order,".R")),unique=TRUE)
if(!identical(names(endpoints),expected_names)) stop("原生样本列顺序契约变化")
scores<-as.matrix(endpoints[,seq_along(sample_order),drop=FALSE])*as.matrix(endpoints[,length(sample_order)+seq_along(sample_order),drop=FALSE])
counts<-lapply(conditions,function(cond) rowSums(is.finite(scores[,sample_order %in% native$sample.group[[cond]],drop=FALSE])))
rows<-lapply(seq_along(sample_order),function(i){info<-sm[match(sample_order[i],sm$sample),];v<-scores[,i];data.frame(sample=info$sample,condition=info$condition,donor=info$donor,ids,score=ifelse(is.finite(v),v,NA_real_),tested=is.finite(v),supported=is.finite(v)&v>0)})
c$add("pre_imputation_lr","lr_edges",do.call(rbind,rows),"原生sumRawData中插补前log2归一化端点乘积；支持仅表示两个端点为正，不是差异显著；与插补后Monte Carlo推断分开",value_kind="nonnegative_strength",additive=TRUE,axis_label="Pre-imputation endpoint product")
effects<-data.frame(feature=paste(source,target,d$lr.gene.name,sep=" | "),value=ifelse(tested,effect,NA_real_),p_value=ifelse(tested,p,NA_real_),q_value=ifelse(tested,q,NA_real_),n_reference=counts[[1]],n_comparison=counts[[2]])
c$add("condition_effects","effect_summary",effects,"原生scLR两阶段模拟及BH；条件间乘积均值差，原生零值插补设置见溯源；不是log fold change。缺失检验仍为NA",contrast=paste(cfg$comparison,"vs",cfg$reference),statistical_unit="independent biological samples",test_definition="scLR native two-stage Monte Carlo with BH across returned candidate family",axis_label="Native mean product difference",alpha=.05)
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
