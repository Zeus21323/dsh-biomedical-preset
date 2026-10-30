#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
a<-commandArgs(TRUE);if(length(a)!=2) stop("需要配置JSON和新输出目录")
mode<-jsonlite::read_json(a[1],simplifyVector=TRUE)$mode %||% "within_sample"
if(!mode %in% c("within_sample","differential")) stop("mode必须为within_sample或differential")
c<-native_expression_context(a,if(mode=="differential") "scSeqCommDiff" else "scSeqComm","scSeqComm","2.0.0");cfg<-c$cfg
resources<-list(LR_pairs_DB=scSeqComm::LR_pairs_ConnectomeDB_2020,TF_reg_DB=scSeqComm::TF_TG_TRRUSTv2_HTRIdb_RegNetwork_High,R_TF_association=scSeqComm::TF_PPR_KEGG_human)
saveRDS(resources,file.path(c$out,"native_resources.rds"))
threshold<-cfg$inter_score_threshold %||% .5
if(!is.numeric(threshold)||length(threshold)!=1||!is.finite(threshold)||threshold<0||threshold>=1) stop("inter_score_threshold需在[0,1)")
native_args<-list(N_cores=1L,backend="doParallel",inter_signaling=TRUE,intra_signaling=TRUE,inter_scores="scSeqComm",only.pos=FALSE,aggregation_method="mean",min_cells=c$minimum,count_thr=cfg$count_threshold %||% 1)
c$start_cache(c$hash(file.path(c$out,"native_resources.rds")),list(mode=mode,args=native_args,threshold=threshold,seed=cfg$seed %||% 42,reference=cfg$reference,comparison=cfg$comparison))
c$bundle$provenance$upstream<-list(commit="b2c41e82e41410758c5805650761c7cae1fb6f14",url="https://gitlab.com/sysbiobig/scseqcomm",license="GPL-3")
c$bundle$provenance$resource_sha256<-c$hash(file.path(c$out,"native_resources.rds"))
c$bundle$provenance$evidence<-"原生scSeqComm S_inter为L/R端点特异性分数最小值；S_intra是受体对应TF证据按PPR权重的加权均值。两者分别保留，不相乘或求和为新算法。分数阈值是探索性支持规则，不是联合LR显著性"
ident<-function(v) vapply(strsplit(v,",",fixed=TRUE),function(g){g<-sort(unique(g));paste0(if(length(g)==1) "gene:" else "complex:",paste(g,collapse="&"))},character(1))
edge_rows<-function(d,sample,condition,donor,score){
  tested<-is.finite(score)
  data.frame(sample=sample,condition=condition,donor=donor,source=d$cluster_L,target=d$cluster_R,ligand=gsub(",","_",d$ligand,fixed=TRUE),receptor=gsub(",","_",d$receptor,fixed=TRUE),
    ligand_identity=ident(d$ligand),receptor_identity=ident(d$receptor),interaction=d$LR_pair,score=ifelse(tested,score,NA_real_),tested=tested,supported=tested&score>threshold)
}
unique_lr<-function(d,cols){
  v<-unique(d[,cols,drop=FALSE]);key<-paste(v$cluster_L,v$cluster_R,v$ligand,v$receptor,sep="\r")
  if(anyDuplicated(key)) stop("同一LR/细胞对的原生分数冲突，不能通过均值消歧")
  v
}
intracellular<-function(d,tag){
  intr<-unique(d[,c("receptor","cluster_R","pathway","S_intra"),drop=FALSE]);intr<-intr[!is.na(intr$pathway),,drop=FALSE]
  if(nrow(intr)) c$add(paste0("intracellular_",tag),"matrix",data.frame(row=paste(intr$receptor,intr$pathway,sep=" | "),column=intr$cluster_R,value=ifelse(is.finite(intr$S_intra),intr$S_intra,NA_real_)),
    "原生受体-通路S_intra，按PPR加权的TF响应证据；保留零和未估计值，不作LR联合P值",value_kind="native_score",axis_label="scSeqComm S_intra",figure_role="intracellular_response",display_top_rows=20L)
  # Only use the returned target-gene list and exact measured TF-regulon links.
  # PPR edges are prior reachability, not measured direct receptor–TF binding.
  candidate_score<-if("S_inter" %in% names(d)) d$S_inter else pmax(d[[paste0("S_inter_",cfg$comparison)]],d[[paste0("S_inter_",cfg$reference)]])
  candidates<-d[is.finite(d$S_intra)&d$S_intra>0&is.finite(candidate_score)&candidate_score>threshold&!is.na(d$genes),,drop=FALSE]
  if(!nrow(candidates)) return(invisible(NULL))
  candidates<-candidates[order(-candidates$S_intra,candidates$cluster_R,candidates$receptor),,drop=FALSE]
  candidates<-head(unique(candidates[,c("ligand","receptor","cluster_L","cluster_R","pathway","tfactors","genes","S_intra"),drop=FALSE]),3)
  for(i in seq_len(nrow(candidates))){
    row<-candidates[i,];ppr<-resources$R_TF_association
    ppr<-ppr[ppr$receptor==row$receptor&ppr$pathway==row$pathway,,drop=FALSE]
    ppr<-ppr[order(-ppr$tf_PPR),,drop=FALSE];tfs<-head(intersect(ppr$tf,strsplit(row$tfactors,",",fixed=TRUE)[[1]]),5)
    targets<-strsplit(row$genes,",",fixed=TRUE)[[1]];links<-list()
    for(tf in tfs){
      tg<-sort(intersect(resources$TF_reg_DB[[tf]],targets));tg<-head(tg,5)
      if(length(tg)) links[[length(links)+1]]<-data.frame(source=tf,target=tg,source_type="TF",target_type="target",value=1)
    }
    if(!length(links)) next
    links<-unique(do.call(rbind,links));tfs<-unique(links$source)
    links<-rbind(data.frame(source=row$ligand,target=row$receptor,source_type="ligand",target_type="receptor",value=1),
      data.frame(source=row$receptor,target=tfs,source_type="receptor",target_type="TF",value=1),links)
    c$add(paste0("mechanism_",tag,"_",i),"molecular_links",links,
      paste0(row$cluster_L,"→",row$cluster_R,"; ",row$pathway,"：原生正S_intra前三候选，PPR前5TF、每TF最多5个原生响应且有调控先验的靶基因；等宽为关系存在。受体→TF是PPR关联，不是实测直连或因果链"),value_kind="count")
  }
}
allrows<-list()
if(mode=="within_sample"){
  for(si in seq_along(unique(c$meta$sample))){
    sample<-unique(c$meta$sample)[si];m<-c$sample_meta(sample)
    meta<-data.frame(Cell_ID=rownames(m),Cluster_ID=m$cell_type,Sample_ID=m$sample,Condition_ID=m$condition)
    native<-c$native(si,sample,function(){set.seed(cfg$seed %||% 42);do.call(scSeqComm::scSeqComm_analyze,c(list(gene_expr=as.matrix(c$expr[,rownames(m),drop=FALSE]),cell_metadata=meta,DEmethod="wilcoxon"),native_args,resources))})
    d<-native$comm_results;c$wt(d,paste0("native_candidates_",si,".tsv"))
    lr<-unique_lr(d,c("ligand","receptor","LR_pair","cluster_L","cluster_R","S_inter","L_score_S_lr","R_score_S_lr"))
    if(any(abs(lr$S_inter-pmin(lr$L_score_S_lr,lr$R_score_S_lr))>1e-12,na.rm=TRUE)) stop("导出S_inter与原生端点分数不一致")
    allrows[[length(allrows)+1]]<-edge_rows(lr,sample,m$condition[1],m$donor[1],lr$S_inter)
    intracellular(d,as.character(si))
  }
}else{
  for(k in c("reference","comparison","design_provenance","statistical_unit")) if(is.null(cfg[[k]])) stop("差异分支缺少：",k)
  if(cfg$statistical_unit!="sample"||!isTRUE(cfg$independent_samples)||isTRUE(cfg$paired)||!is.null(cfg$covariates)) stop("原生multi-sample为独立样本Wilcoxon，无配对/协变量模型；需已核实独立样本设计")
  conditions<-c(cfg$comparison,cfg$reference)
  if(length(unique(conditions))!=2||!setequal(unique(c$meta$condition),conditions)) stop("需两个真实条件；原生方向为comparison相对reference")
  meta<-data.frame(Cell_ID=rownames(c$meta),Cluster_ID=c$meta$cell_type,Sample_ID=c$meta$sample,Condition_ID=c$meta$condition)
  sample_info<-unique(c$meta[,c("sample","donor","condition")]);known<-sample_info$donor[!tolower(sample_info$donor) %in% c("unknown","unavailable")]
  if(anyDuplicated(known)) stop("存在重复供体，不能把技术样本当独立生物重复")
  if(any(table(sample_info$condition)<4)) stop("原生多样本分支至少每条件4个样本；每LR仍按有限样本数量判定")
  native<-c$native(1L,"differential",function(){set.seed(cfg$seed %||% 42);do.call(scSeqComm::scSeqComm_differential,c(list(gene_expr=as.matrix(c$expr),cell_metadata=meta,
      scenario="multi-sample",cond_names=conditions,DEmethod="pseudo.wilcoxon",padj_method="BH",alternative_inter="two.sided"),native_args,resources))})
  d<-native$differential_comm;c$wt(d,"native_differential.tsv")
  c$bundle$provenance$native_limitation<-"固定版本receptor_DEpval的代码错误地复用ligand字段；两列仅保留于原生表，不输出为规范受体检验证据。胞内分支pseudo.wilcoxon比较样本平均归一化表达，不是edgeR原始计数模型"
  c$bundle$provenance$test_unit<-"原生multi-sample：独立样本S_inter分布Wilcoxon；原生全部LR×细胞对BH，胞内样本平均表达Wilcoxon；没有协变量/配对推断"
  count_by_condition<-list()
  for(cond in conditions){
    distribution<-native$intercellular_signaling[[cond]]$distribution_results
    c$wt(distribution,paste0("native_distribution_",match(cond,conditions),".tsv"))
    cols<-grep("^S_inter_",names(distribution),value=TRUE)
    if(!length(cols)) stop("缺少原生样本分布列")
    # The fixed native implementation iterates unique(Sample_ID) in metadata
    # encounter order and foreach .inorder=TRUE, then names columns by index.
    native_samples<-unique(meta$Sample_ID[meta$Condition_ID==cond])
    if(!identical(cols,paste0("S_inter_",seq_along(native_samples)))) stop("原生分布列与固定版本样本顺序契约不符")
    c$wt(data.frame(native_column=cols,sample=native_samples),paste0("sample_column_map_",match(cond,conditions),".tsv"))
    count_by_condition[[cond]]<-rowSums(is.finite(as.matrix(distribution[,cols,drop=FALSE])))
    for(j in seq_along(cols)){
      sm<-sample_info[sample_info$sample==native_samples[j],,drop=FALSE]
      allrows[[length(allrows)+1]]<-edge_rows(distribution,native_samples[j],cond,sm$donor[1],distribution[[cols[j]]])
    }
  }
  lr<-unique_lr(d,c("ligand","receptor","LR_pair","cluster_L","cluster_R","logFC_S_inter","pvalue_S_inter","pvalue_adj_S_inter","effsize_S_inter"))
  q<-p.adjust(lr$pvalue_S_inter,method="BH")
  if(any(abs(q-lr$pvalue_adj_S_inter)>1e-12,na.rm=TRUE)) stop("原生BH不符合完整LR×细胞对校正族")
  # Join by molecular and cell-pair identity; native table orders are not assumed.
  key<-function(z) paste(z$ligand,z$receptor,z$cluster_L,z$cluster_R,sep="\r")
  ns<-lapply(conditions,function(cond){z<-native$intercellular_signaling[[cond]]$distribution_results;count_by_condition[[cond]][match(key(lr),key(z))]})
  distributions<-lapply(conditions,function(cond){z<-native$intercellular_signaling[[cond]]$distribution_results;as.matrix(z[match(key(lr),key(z)),grep('^S_inter_',names(z)),drop=FALSE])})
  # Diagnose sensitivity of rank inference to near-saturated native CDF scores.
  # This is a separate, predeclared 1e-12 perturbation check, not replacement P.
  rounded_p<-vapply(seq_len(nrow(lr)),function(i){
    aa<-distributions[[1]][i,];bb<-distributions[[2]][i,];aa<-aa[is.finite(aa)];bb<-bb[is.finite(bb)]
    if(length(aa)<4||length(bb)<4) return(NA_real_)
    scSeqComm:::fasterWilcox(round(aa,12),round(bb,12),alternative="two.sided")
  },numeric(1))
  rounded_q<-p.adjust(rounded_p,"BH")
  dynamic_range<-apply(cbind(distributions[[1]],distributions[[2]]),1,function(v){v<-v[is.finite(v)];if(!length(v)) NA_real_ else diff(range(v))})
  unstable<-is.finite(dynamic_range)&dynamic_range<=1e-12
  c$wt(data.frame(lr[,c("ligand","receptor","cluster_L","cluster_R")],native_p=lr$pvalue_S_inter,native_q=lr$pvalue_adj_S_inter,
    rounded_12_decimal_p=rounded_p,rounded_12_decimal_q=rounded_q,score_dynamic_range=dynamic_range,near_constant=unstable),"rank_stability_diagnostics.tsv")
  c$bundle$provenance$rank_stability<-list(perturbation="原生S_inter固定保留12位小数后重算相同原生秩检验，仅用于诊断；主表P/q不替换",
    near_constant_candidates=sum(unstable),native_significant_near_constant=sum(unstable&lr$pvalue_adj_S_inter<.05,na.rm=TRUE),
    interpretation="接近0/1饱和或近常数分数的末位浮点差异可能改变秩检验；不能仅凭其P值作生物学差异结论，须联合效应和敏感性复核")
  features<-paste(lr$cluster_L,lr$cluster_R,lr$LR_pair,sep=" | ")
  c$add("rank_stability","matrix",rbind(data.frame(row=features,column="Native BH",value=lr$pvalue_adj_S_inter),data.frame(row=features,column="Rounded-score BH",value=rounded_q)),
    "同一原生检验在完整双精度S_inter与固定12位小数扰动下的BH；后者仅为浮点稳定性诊断，不替换主分析，不按结果调整精度",value_kind="p_value",axis_label="Adjusted P",display_top_rows=20L,direction="lower",figure_role="sensitivity")
  summary<-data.frame(feature=paste(lr$cluster_L,lr$cluster_R,lr$LR_pair,sep=" | "),value=ifelse(is.finite(lr$logFC_S_inter),lr$logFC_S_inter,NA_real_),p_value=lr$pvalue_S_inter,q_value=lr$pvalue_adj_S_inter,
    n_reference=ns[[2]],n_comparison=ns[[1]],hedges_g=ifelse(is.finite(lr$effsize_S_inter),lr$effsize_S_inter,NA_real_),native_effect_status=ifelse(is.finite(lr$logFC_S_inter),"finite","native_infinite_or_missing"),numerically_near_constant=unstable)
  c$add("condition_effects","effect_summary",summary,"原生样本S_inter均值log2比值与独立样本Wilcoxon/BH；原生无穷效应另保留，不加伪计数",contrast=paste(cfg$comparison,"vs",cfg$reference),statistical_unit="independent biological samples",test_definition="scSeqCommDiff multi-sample fasterWilcox, native BH over full LR×cell-pair family",axis_label="Native log2 fold change",alpha=.05)
  intracellular(d,"differential")
}
c$add("lr_edges","lr_edges",do.call(rbind,allrows),"原生S_inter；有限值为可评分，支持为严格分数阈值而非LR联合显著性；不同通路重复行折回唯一LR身份，S_intra单独呈现",value_kind="native_score",additive=FALSE,axis_label="scSeqComm S_inter")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
