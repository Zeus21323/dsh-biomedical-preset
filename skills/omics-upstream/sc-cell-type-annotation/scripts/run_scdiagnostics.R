#!/usr/bin/env Rscript
args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L) stop("用法：run_scdiagnostics.R reference.rds query.rds settings.rds new_output_dir")
if (file.exists(args[4])) stop("输出已存在，拒绝覆盖")
for (pkg in c("scDiagnostics", "SingleCellExperiment", "ggplot2", "svglite")) {
  if (!requireNamespace(pkg, quietly = TRUE)) stop(paste("缺少依赖", pkg))
}
if (as.character(utils::packageVersion("scDiagnostics")) != "1.7.2") stop("当前仅适配scDiagnostics 1.7.2的返回字段")
if (!identical(utils::packageDescription("scDiagnostics")$RemoteSha,
               "7e9343ca78eaa714213a5cfa013034098cb4a9db")) stop("请安装reference指定commit")
ref <- readRDS(args[1]); query <- readRDS(args[2]); s <- readRDS(args[3])
need <- c("ref_label", "query_label", "assay", "seed", "pc_subset", "n_resamples", "max_cells", "parameter_reason")
if (!is.list(s) || !all(need %in% names(s)) || !is.character(s$parameter_reason) || !nzchar(s$parameter_reason)) stop("设置缺少字段或参数依据")
for (pair in list(list(ref, s$ref_label), list(query, s$query_label))) {
  x <- pair[[1]]
  if (!methods::is(x, "SingleCellExperiment")) stop("输入必须为SingleCellExperiment")
  if (!s$assay %in% SummarizedExperiment::assayNames(x)) stop("缺少指定表达层")
  expr <- SummarizedExperiment::assay(x, s$assay)
  if (anyNA(expr) || any(!is.finite(expr))) stop("表达层含缺失或非有限值，不自动插补")
  if (is.null(colnames(x)) || anyDuplicated(colnames(x)) || is.null(rownames(x)) || anyDuplicated(rownames(x))) stop("细胞和基因ID必须存在且唯一")
  if (!pair[[2]] %in% colnames(SummarizedExperiment::colData(x))) stop("缺少标签列")
  labels <- as.character(x[[pair[[2]]]])
  if (anyNA(labels) || any(!nzchar(labels))) stop("标签有缺失；先明确unknown类别，不自动移除")
}
if (!identical(rownames(ref), rownames(query))) stop("reference与query需显式对齐相同基因顺序；不得自动取交集")
if (!is.numeric(s$pc_subset) || !length(s$pc_subset) || anyNA(s$pc_subset) || any(s$pc_subset < 1) || any(s$pc_subset != as.integer(s$pc_subset))) stop("PC设置无效")
if (anyDuplicated(s$pc_subset)) stop("PC索引重复")
if (!"PCA" %in% SingleCellExperiment::reducedDimNames(ref)) stop("reference缺少预计算PCA；先按reference方法准备，不能隐式重算")
pca <- SingleCellExperiment::reducedDim(ref, "PCA")
rotation <- attr(pca, "rotation"); variance <- attr(pca, "varExplained")
if (!is.matrix(pca) || nrow(pca) != ncol(ref) || ncol(pca) < max(s$pc_subset) || any(!is.finite(pca))) stop("reference PCA坐标不完整或非有限")
if (!is.matrix(rotation) || ncol(rotation) < max(s$pc_subset) || is.null(rownames(rotation)) ||
    anyDuplicated(rownames(rotation)) || !all(rownames(rotation) %in% rownames(ref)) || any(!is.finite(rotation))) stop("PCA载荷和基因身份无效")
if (!is.numeric(variance) || length(variance) < max(s$pc_subset) || any(!is.finite(variance[s$pc_subset])) ||
    any(variance[s$pc_subset] < 0) || sum(variance[s$pc_subset]) <= 0) stop("PCA缺少有效varExplained，不能编造距离权重")
for (k in c("seed", "n_resamples", "max_cells")) {
  if (length(s[[k]]) != 1 || !is.numeric(s[[k]]) || !is.finite(s[[k]]) || s[[k]] != as.integer(s[[k]]) || s[[k]] < 0) stop(paste("无效设置", k))
}
if (s$n_resamples < 2 || s$max_cells < 10) stop("重采样或细胞上限不足")
common <- intersect(unique(as.character(ref[[s$ref_label]])), unique(as.character(query[[s$query_label]])))
if (!length(common)) stop("参考与查询没有共享标签；不能直接评估标签内对齐")
for (type in common) {
  if (min(sum(ref[[s$ref_label]] == type), sum(query[[s$query_label]] == type)) <= max(s$pc_subset) + 1) stop("某类细胞数量不足以支持所选PC")
}
set.seed(s$seed)
dir.create(args[4], recursive = TRUE)
if (!dir.exists(args[4])) stop("不能创建输出目录")
out <- normalizePath(args[4]); writeLines("running", file.path(out, "status.txt"))
tryCatch({
  res <- scDiagnostics::calculateWassersteinDistance(query_data = query, reference_data = ref,
    ref_cell_type_col = s$ref_label, query_cell_type_col = s$query_label, cell_types = common,
    pc_subset = s$pc_subset, n_resamples = as.numeric(s$n_resamples), assay_name = s$assay,
    max_cells_query = s$max_cells, max_cells_ref = s$max_cells)
  saveRDS(res, file.path(out, "alignment.rds"))
  values <- list()
  for (type in common) for (comparison in c("ref_ref_dist", "ref_query_dist")) {
    v <- res[[comparison]][[type]]
    if (!length(v) || any(!is.finite(v))) stop("距离返回不完整或非有限")
    values[[length(values) + 1L]] <- data.frame(cell_type = type, comparison = comparison, distance = v)
  }
  write.table(do.call(rbind, values), file.path(out, "alignment_distances.tsv"), sep = "\t", row.names = FALSE, quote = FALSE)
  # 使用已保存的原生绘图结果，不重新拟合或伪造细胞层异常分数。
  g <- plot(res)
  for (ext in c("pdf", "svg", "png")) ggplot2::ggsave(file.path(out, paste0("alignment.", ext)), g + ggplot2::theme(panel.grid.major=ggplot2::element_blank(), panel.grid.minor=ggplot2::element_blank()), width = 180, height = 140, units = "mm", dpi = 400)
  saveRDS(list(settings = s, input_md5 = tools::md5sum(args[1:3]), session = utils::sessionInfo(),
    query_only_labels = setdiff(unique(as.character(query[[s$query_label]])), common)), file.path(out, "run_record.rds"))
  writeLines(c("# scDiagnostics参考适配诊断", "", "本次运行标签内参考–查询距离诊断，未修改原标签。",
    "重采样细胞距离不是供体层置信区间，也不能把分布差异自动解释为误标。",
    "未共享的query标签保留在run_record.rds，不能视为已通过诊断。",
    "本包装器未运行detectAnomaly或marker检验；进一步分析按reference分别执行。", "", "![距离诊断](alignment.png)"), file.path(out, "report.md"), useBytes = TRUE)
  writeLines("completed_visual_and_scientific_review_required", file.path(out, "status.txt"))
}, error = function(e) {
  writeLines(paste("failed:", conditionMessage(e)), file.path(out, "status.txt"), useBytes = TRUE)
  stop(e)
})
