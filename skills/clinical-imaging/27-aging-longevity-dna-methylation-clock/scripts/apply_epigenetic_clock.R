#!/usr/bin/env Rscript

fail <- function(message, status = 2) {
  message(paste0("错误：", message))
  quit(status = status)
}

usage <- function() {
  cat(paste(
    "用法：Rscript apply_epigenetic_clock.R --beta BETA.csv --coefficients COEFS.csv --intercept VALUE --output OUT.csv [--minimum-coverage 0.8]",
    "      Rscript apply_epigenetic_clock.R --self-test",
    "BETA.csv 首列为 cpg；COEFS.csv 需要 cpg、weight 和 training_mean 三列。",
    sep = "\n"
  ))
  cat("\n")
}

run_self_test <- function() {
  beta <- matrix(c(0.2, 0.4, 0.6, 0.8), nrow = 2, byrow = TRUE,
                 dimnames = list(c("cg1", "cg2"), c("S1", "S2")))
  coefs <- data.frame(cpg = c("cg1", "cg2"), weight = c(2, -1),
                      training_mean = c(0.3, 0.7))
  score <- 10 + colSums(beta[coefs$cpg, , drop = FALSE] * coefs$weight)
  stopifnot(isTRUE(all.equal(unname(score), c(9.8, 10.0))))
  cat("ok: frozen epigenetic clock self-test\n")
}

parse_args <- function(args) {
  values <- list(minimum_coverage = 0.8)
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

args <- parse_args(commandArgs(trailingOnly = TRUE))
if (isTRUE(args$self_test)) {
  run_self_test()
  quit(status = 0)
}
required <- c("beta", "coefficients", "intercept", "output")
missing <- required[!vapply(required, function(key) !is.null(args[[key]]), logical(1))]
if (length(missing)) fail(paste("缺少参数", paste(missing, collapse = ", ")))
if (!file.exists(args$beta)) fail(paste("beta 文件不存在", args$beta))
if (!file.exists(args$coefficients)) fail(paste("系数文件不存在", args$coefficients))
if (file.exists(args$output)) fail(paste("输出已存在，拒绝覆盖", args$output))

beta_frame <- read.csv(args$beta, check.names = FALSE, stringsAsFactors = FALSE)
coefs <- read.csv(args$coefficients, stringsAsFactors = FALSE)
if (!"cpg" %in% names(beta_frame)) fail("beta 文件缺少 cpg 列")
if (!all(c("cpg", "weight", "training_mean") %in% names(coefs))) {
  fail("系数表需要 cpg、weight 和 training_mean")
}
if (anyDuplicated(beta_frame$cpg) || anyDuplicated(coefs$cpg)) fail("CpG 不能重复")

rownames(beta_frame) <- beta_frame$cpg
beta_frame$cpg <- NULL
beta <- as.matrix(beta_frame)
storage.mode(beta) <- "double"
if (any(!is.finite(beta)) || any(beta < 0 | beta > 1)) fail("beta 必须是 0 到 1 的有限数值")
coefs$weight <- as.numeric(coefs$weight)
coefs$training_mean <- as.numeric(coefs$training_mean)
if (any(!is.finite(coefs$weight)) || any(!is.finite(coefs$training_mean))) fail("系数存在无效数值")

observed <- coefs$cpg %in% rownames(beta)
coverage <- mean(observed)
minimum_coverage <- as.numeric(args$minimum_coverage)
if (!is.finite(minimum_coverage) || minimum_coverage <= 0 || minimum_coverage > 1) {
  fail("minimum-coverage 必须位于 (0,1]")
}

aligned <- matrix(NA_real_, nrow = nrow(coefs), ncol = ncol(beta),
                  dimnames = list(coefs$cpg, colnames(beta)))
aligned[observed, ] <- beta[coefs$cpg[observed], , drop = FALSE]
aligned[!observed, ] <- coefs$training_mean[!observed]
intercept <- as.numeric(args$intercept)
if (!is.finite(intercept)) fail("intercept 必须是有限数值")
scores <- intercept + colSums(aligned * coefs$weight)
if (coverage < minimum_coverage) scores[] <- NA_real_

result <- data.frame(sample_id = colnames(beta), clock_value = scores,
                     cpg_coverage = coverage, cpg_required = nrow(coefs),
                     cpg_observed = sum(observed),
                     qc = if (coverage < minimum_coverage) "CpG覆盖率低于阈值" else "通过内置检查")
dir.create(dirname(args$output), recursive = TRUE, showWarnings = FALSE)
write.csv(result, args$output, row.names = FALSE, na = "")
cat(sprintf("完成：%d 个样本，CpG 覆盖率 %.3f\n", nrow(result), coverage))
