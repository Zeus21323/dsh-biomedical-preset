#!/usr/bin/env Rscript

fail <- function(message, status = 2) {
  message(paste0("错误：", message))
  quit(status = status)
}

usage <- function() {
  cat(paste(
    "用法：Rscript cell_deconvolution.R --beta BETA.csv --reference REF.csv --output OUT.csv [--method RPC]",
    "      Rscript cell_deconvolution.R --self-test",
    "BETA.csv 和 REF.csv 的首列必须名为 cpg，其余列分别是样本和参考细胞。",
    sep = "\n"
  ))
  cat("\n")
}

parse_args <- function(args) {
  values <- list(method = "RPC")
  i <- 1
  while (i <= length(args)) {
    key <- args[[i]]
    if (key %in% c("--help", "-h")) {
      usage()
      quit(status = 0)
    } else if (key == "--self-test") {
      values$self_test <- TRUE
      i <- i + 1
    } else {
      if (!startsWith(key, "--")) fail(paste("未知参数", key))
      if (i == length(args)) fail(paste("参数缺少值", key))
      values[[gsub("-", "_", sub("^--", "", key))]] <- args[[i + 1]]
      i <- i + 2
    }
  }
  values
}

simplex_check <- function(matrix_value, tolerance = 0.05) {
  all(is.finite(matrix_value)) && all(matrix_value >= -1e-8) &&
    all(abs(rowSums(matrix_value) - 1) <= tolerance)
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
if (isTRUE(args$self_test)) {
  example <- matrix(c(0.2, 0.8, 0.45, 0.55), nrow = 2, byrow = TRUE)
  stopifnot(simplex_check(example))
  cat("ok: cell fraction simplex self-test\n")
  quit(status = 0)
}

required <- c("beta", "reference", "output")
missing <- required[!vapply(required, function(key) !is.null(args[[key]]), logical(1))]
if (length(missing)) fail(paste("缺少参数", paste(missing, collapse = ", ")))
if (!requireNamespace("EpiDISH", quietly = TRUE)) fail("需要安装 Bioconductor 包 EpiDISH")
if (file.exists(args$output)) fail(paste("输出已存在，拒绝覆盖", args$output))

read_cpg_matrix <- function(path) {
  if (!file.exists(path)) fail(paste("文件不存在", path))
  frame <- read.csv(path, check.names = FALSE, stringsAsFactors = FALSE)
  if (!"cpg" %in% names(frame)) fail(paste(path, "缺少 cpg 列"))
  if (anyDuplicated(frame$cpg)) fail(paste(path, "存在重复 CpG"))
  rownames(frame) <- frame$cpg
  frame$cpg <- NULL
  matrix_value <- as.matrix(frame)
  storage.mode(matrix_value) <- "double"
  if (any(!is.finite(matrix_value)) || any(matrix_value < 0 | matrix_value > 1)) {
    fail(paste(path, "必须是 0 到 1 的有限 beta 值"))
  }
  matrix_value
}

beta <- read_cpg_matrix(args$beta)
reference <- read_cpg_matrix(args$reference)
common <- intersect(rownames(beta), rownames(reference))
if (length(common) < 50) fail("beta 与参考共有 CpG 少于 50 个")
result <- EpiDISH::epidish(beta.m = beta[common, , drop = FALSE],
                           ref.m = reference[common, , drop = FALSE],
                           method = args$method)
fractions <- result$estF
if (!simplex_check(fractions)) fail("估计比例未通过非负与和为1检查")
output <- data.frame(sample_id = rownames(fractions), fractions, check.names = FALSE)
dir.create(dirname(args$output), recursive = TRUE, showWarnings = FALSE)
write.csv(output, args$output, row.names = FALSE)
cat(sprintf("完成：%d 个样本、%d 种细胞、%d 个共有 CpG\n",
            nrow(fractions), ncol(fractions), length(common)))
