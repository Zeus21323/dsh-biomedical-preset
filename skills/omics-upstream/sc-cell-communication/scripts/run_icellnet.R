#!/usr/bin/env Rscript
options(stringsAsFactors=FALSE,warn=1)
script<-sub("^--file=","",grep("^--file=",commandArgs(FALSE),value=TRUE)[1])
source(file.path(dirname(normalizePath(script)),"native_expression_context.R"))
c<-native_expression_context(commandArgs(TRUE),"ICELLNET","icellnet","2.2.1");cfg<-c$cfg
for(k in c("database","database_version","database_provenance")) if(is.null(cfg[[k]])) stop("缺少固定数据库信息：",k)
dbpath<-c$resolve(cfg$database);db<-read.delim(dbpath,check.names=FALSE,na.strings=c("","NA"))
ligand_cols<-paste("Ligand",1:4);receptor_cols<-paste("Receptor",1:5);members<-c(ligand_cols,receptor_cols)
if(!all(c(members,"Family") %in% names(db))||!nrow(db)||anyNA(db[,c("Ligand 1","Receptor 1")])) stop("需要原生v2数据库的完整4配体/5受体亚基列")
for(cols in list(ligand_cols,receptor_cols)) for(i in 2:length(cols)) if(any(!is.na(db[[cols[i]]])&is.na(db[[cols[i-1]]]))) stop("复合物亚基列存在空隙，原生函数无法可靠解释")
collapse<-function(cols) apply(db[,cols,drop=FALSE],1,function(v) paste(v[!is.na(v)],collapse="_"))
ligands<-collapse(ligand_cols);receptors<-collapse(receptor_cols)
identity<-function(cols) apply(db[,cols,drop=FALSE],1,function(v){g<-sort(unique(v[!is.na(v)]));paste0(if(length(g)==1) "gene:" else "complex:",paste(g,collapse="&"))})
if(anyDuplicated(paste(ligands,receptors,sep="\r"))) stop("原生数据库LR身份重复；需明确资源去重规则后再运行")
# Native gene.scaling reads its first five database columns. The v2 resource
# contains nine member columns. Project ALL members into that native selector,
# leaving gene scaling and ligand/receptor geometric means unchanged.
universe<-sort(unique(na.omit(unlist(db[,members],use.names=FALSE))))
scaling_db<-data.frame(member=universe,empty2=NA_character_,empty3=NA_character_,empty4=NA_character_,empty5=NA_character_)
if(!any(universe %in% rownames(c$expr))) stop("没有可测数据库亚基")
n<-as.integer(cfg$scaling_top_profiles %||% 1L)
if(is.na(n)||n<1) stop("scaling_top_profiles需正整数")
c$start_cache(c$hash(dbpath),list(scaling_top_profiles=n,min_cells=c$minimum,expression_scale=cfg$expression_scale,member_projection="all_nine_v2_columns"))
file.copy(dbpath,file.path(c$out,"native_database.tsv"));c$wt(scaling_db,"scaling_gene_universe.tsv")
c$bundle$provenance$upstream<-list(commit="ee1c19169d722f4e7284fd6f3d4f52507941d00a",url="https://github.com/soumelis-lab/ICELLNET",license="GPL-3")
c$bundle$provenance$database_sha256<-c$hash(dbpath)
c$bundle$provenance$scaling<-"每实际样本先按细胞类型平均既有表达，再原生gene.scaling；v2全部9列亚基投影给原生前5列基因选择器。缩放参考是本样本合格细胞类型；跨数据集分数不是绝对强度。原生ligand.average/receptor.average与icellnet.score未修改"
c$bundle$provenance$uncertainty<-"表达组合评分，无原生置换P或FDR；缺失任一亚基的候选标记未测全，保留原生值但不计入支持。正分是表达支持，不是实验结合证据"
allrows<-list();samples<-unique(c$meta$sample)
complete<-apply(db[,members,drop=FALSE],1,function(v) all(v[!is.na(v)] %in% rownames(c$expr)))
for(si in seq_along(samples)){
  sample<-samples[si];m<-c$sample_meta(sample);types<-unique(m$cell_type)
  if(n>length(types)) stop("scaling_top_profiles超过合格细胞类型数")
  ids<-sprintf("CT%03d",seq_along(types));inverse<-setNames(types,ids)
  native<-c$native(si,sample,function(){
    profiles<-vapply(types,function(ct) Matrix::rowMeans(c$expr[,rownames(m)[m$cell_type==ct],drop=FALSE]),numeric(nrow(c$expr)))
    rownames(profiles)<-rownames(c$expr);colnames(profiles)<-ids
    scaled<-icellnet::gene.scaling(data=profiles,n=n,db=scaling_db)
    if(!setequal(rownames(scaled),intersect(universe,rownames(c$expr)))) stop("原生缩放未保留完整已测亚基")
    result<-setNames(lapply(ids,function(id) icellnet::icellnet.score(direction="out",CC.data=scaled[,id,drop=FALSE],PC.data=scaled,PC=ids,CC.type="RNAseq",PC.type="RNAseq",db=db)),ids)
    list(profiles=profiles,scaled=scaled,result=result,metadata=m,identity_map=data.frame(native=ids,cell_type=types))
  })
  c$wt(data.frame(gene=rownames(native$profiles),native$profiles,check.names=FALSE),paste0("native_profiles_",si,".tsv"))
  c$wt(native$scaled,paste0("native_scaled_",si,".tsv"));c$wt(native$identity_map,paste0("identity_map_",si,".tsv"))
  for(id in ids){
    mat<-native$result[[id]][[2]]
    if(nrow(mat)!=nrow(db)||!identical(colnames(mat),ids)) stop("原生LR表次序或群身份变化")
    if(any(is.infinite(mat))||any(mat<0,na.rm=TRUE)) stop("原生分数出现无穷或负值")
    # Verify native global summaries; they can include incomplete complexes.
    if(any(abs(colSums(mat,na.rm=TRUE)-as.numeric(native$result[[id]][[1]][,1]))>1e-8)) stop("原生全局和LR分数不一致")
    c$wt(data.frame(native_interaction=rownames(mat),mat,check.names=FALSE),paste0("native_scores_",si,"_",id,".tsv"))
    for(target in ids){
      score<-as.numeric(mat[,target]);tested<-complete&is.finite(score)
      allrows[[length(allrows)+1]]<-data.frame(sample=sample,donor=m$donor[1],condition=m$condition[1],source=inverse[id],target=inverse[target],
        ligand=ligands,receptor=receptors,interaction=paste(ligands,receptors,sep=" -> "),pathway=ifelse(is.na(db$Family),"Unclassified",db$Family),
        ligand_identity=identity(ligand_cols),receptor_identity=identity(receptor_cols),
        score=ifelse(tested,score,NA_real_),tested=tested,supported=tested&!is.na(score)&score>0,complete_complex=complete,native_database_row=seq_len(nrow(db)))
    }
  }
}
c$add("lr_edges","lr_edges",do.call(rbind,allrows),"ICELLNET原生缩放后配体/受体几何均值乘积；完整亚基且正分为表达支持，无P/FDR；聚合只包含已测全候选，可能不同于原生忽略缺失的全局和",value_kind="nonnegative_strength",additive=TRUE,axis_label="ICELLNET expression score",pathway_semantics="database interaction family")
c$wj(c$bundle,"bundle.json");capture.output(sessionInfo(),file=file.path(c$out,"sessionInfo.txt"))
