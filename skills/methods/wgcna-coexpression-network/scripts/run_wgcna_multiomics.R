#!/usr/bin/env Rscript
# 输入是由代理按reference建立的RDS数据与参数；不安装依赖、不连接LLM。
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) stop("用法：run_wgcna_multiomics.R data.rds settings.rds new_output_dir")
if (file.exists(args[3])) stop("输出已存在，拒绝覆盖")
for (pkg in c("WGCNAplus", "lasagna", "ggplot2", "svglite")) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop(paste("缺少依赖：", pkg))
}
if (as.character(utils::packageVersion("WGCNAplus")) != "0.1.0") stop("WGCNAplus版本未适配")
if (!identical(utils::packageDescription("WGCNAplus")$RemoteSha,
               "c162dc4ef6c3cef880568f40b32b260755246848")) stop("请安装reference指定commit以核实接口")
d <- readRDS(args[1]); s <- readRDS(args[2])
need <- c("seed", "power", "ngenes", "minmodsize", "mergeCutHeight", "minKME", "deepsplit", "parameter_reason", "license_confirmed")
if (!is.list(s) || !all(need %in% names(s))) stop("参数缺少必需字段")
if (!isTRUE(s$license_confirmed)) stop("WGCNAplus许可尚未确认，不执行")
if (!is.character(s$parameter_reason) || !nzchar(s$parameter_reason)) stop("必须记录参数依据")
if (!is.list(d$dataX) || length(d$dataX) < 2 || is.null(names(d$dataX)) ||
    anyDuplicated(names(d$dataX)) || any(!nzchar(names(d$dataX)))) stop("需要命名的多层矩阵列表")
if (!is.data.frame(d$samples) || is.null(rownames(d$samples)) || anyDuplicated(rownames(d$samples))) stop("样本表必须有唯一行名")
for (x in d$dataX) {
  if (!is.matrix(x) || !is.numeric(x) || any(!is.finite(x)) ||
      is.null(rownames(x)) || anyDuplicated(rownames(x)) || is.null(colnames(x)) || anyDuplicated(colnames(x))) stop("矩阵必须为有限数值、特征×样本且ID唯一")
  if (!identical(colnames(x), rownames(d$samples))) stop("每层列顺序必须与样本表完全一致；不自动取交集")
  # 此固定实现内部fast TOM使用40维近似；这是包装器保守运行边界，不是WGCNA的普适样本量要求。
  if (ncol(x) < 50 || nrow(x) < 50) stop("本适配器需至少50样本和每层50特征；小数据请评估经典WGCNA路线")
  if (any(apply(x, 1, stats::sd) == 0)) stop("有常量特征，需先显式过滤并记录")
}
if (length(s$power) != 1 && length(s$power) != length(d$dataX)) stop("power需为单值或逐层向量")
if (any(!is.finite(s$power)) || any(s$power <= 0)) stop("power必须为已选定正数，不隐式调参")
for (k in c("seed", "ngenes", "minmodsize", "deepsplit")) {
  if (length(s[[k]]) != 1 || !is.numeric(s[[k]]) || !is.finite(s[[k]]) || s[[k]] != as.integer(s[[k]]) || s[[k]] < 0) stop(paste("无效整数参数", k))
}
if (s$ngenes < 50 || s$minmodsize < 2 || s$deepsplit > 4 ||
    length(s$mergeCutHeight) != 1 || !is.finite(s$mergeCutHeight) || s$mergeCutHeight < 0 || s$mergeCutHeight > 1 ||
    length(s$minKME) != 1 || !is.finite(s$minKME) || s$minKME < 0 || s$minKME > 1) stop("参数范围无效")
set.seed(s$seed)
dir.create(args[3], recursive = TRUE)
if (!dir.exists(args[3])) stop("不能创建输出目录")
out <- normalizePath(args[3])
writeLines("running", file.path(out, "status.txt"))
tryCatch({
  options(WGCNAplus.default_llm = NULL)
  res <- WGCNAplus::computeWGCNA_multiomics(dataX = d$dataX, samples = d$samples,
    power = s$power, ngenes = s$ngenes, minmodsize = s$minmodsize,
    minKME = s$minKME, deepsplit = s$deepsplit, mergeCutHeight = s$mergeCutHeight,
    compute.enrichment = FALSE, add.pheno = FALSE, add.gsets = FALSE,
    do.consensus = FALSE, report = FALSE, ai_model = NULL)
  saveRDS(res, file.path(out, "wgcna_result.rds"))
  rows <- list()
  for (layer in names(res$layers)) {
    for (module in names(res$layers[[layer]]$me.genes)) {
      genes <- res$layers[[layer]]$me.genes[[module]]
      if (length(genes)) rows[[length(rows) + 1L]] <- data.frame(layer = layer, module = module, feature = genes)
    }
  }
  if (!length(rows)) stop("未获得模块成员；保留RDS用于排错，不报告模块识别成功")
  members <- do.call(rbind, rows)
  write.table(members, file.path(out, "module_members.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  sizes <- aggregate(feature ~ layer + module, members, length)
  names(sizes)[3] <- "n_features"
  write.table(sizes, file.path(out, "module_sizes.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  g <- ggplot2::ggplot(sizes, ggplot2::aes(x = module, y = n_features)) +
    ggplot2::geom_point(color = "#0072B2") + ggplot2::facet_wrap(~layer, scales = "free_x") +
    ggplot2::theme_classic(base_size = 9) + ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)) +
    ggplot2::labs(title = "Module sizes (descriptive)", y = "Features", x = "Module")
  for (ext in c("pdf", "svg", "png")) ggplot2::ggsave(file.path(out, paste0("module_sizes.", ext)), g + ggplot2::theme(panel.grid.major=ggplot2::element_blank(), panel.grid.minor=ggplot2::element_blank()), width = 180, height = 110, units = "mm", dpi = 400)
  saveRDS(list(settings = s, input_md5 = tools::md5sum(args[1:2]), session = utils::sessionInfo()), file.path(out, "run_record.rds"))
  writeLines(c("# WGCNA+运行摘要", "", "已运行多层模块识别；图为模块大小描述，不是模块–性状显著性。",
    "上游同时构建LASAGNA模型/图并保存在RDS；本包装器只核验导出的模块成员，不认证图的生物学有效性。",
    "本适配器未运行共识、富集、保留性、协变量调整的性状检验或外部AI解读。",
    "请根据研究设计另行完成这些分析，保留阴性和不稳定模块。", "", "![模块大小](module_sizes.png)"), file.path(out, "report.md"), useBytes = TRUE)
  writeLines("completed_visual_and_scientific_review_required", file.path(out, "status.txt"))
}, error = function(e) {
  writeLines(paste("failed:", conditionMessage(e)), file.path(out, "status.txt"), useBytes = TRUE)
  stop(e)
})
