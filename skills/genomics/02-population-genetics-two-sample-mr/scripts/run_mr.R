#!/usr/bin/env Rscript
# Local, pre-clumped two-sample MR. No network calls or package installation.
args <- commandArgs(trailingOnly = TRUE)
usage <- function() cat("用法: Rscript run_mr.R --config project.json --step harmonise|estimate|all [--dry-run]\n或 --check-env；所有结果使用新建的仓库外目录。\n")
if ("--help" %in% args || length(args) == 0) { usage(); quit(status = 0) }
needed <- c("jsonlite", "TwoSampleMR")
if ("--check-env" %in% args) {
  ok <- vapply(needed, requireNamespace, logical(1), quietly = TRUE)
  print(data.frame(package = needed, available = ok))
  quit(status = if (all(ok)) 0 else 2)
}
getarg <- function(key) {
  i <- which(args == key)
  if (length(i) != 1 || i == length(args)) stop(paste("缺少/重复参数", key))
  args[i + 1]
}
tryCatch({
  if (!requireNamespace("jsonlite", quietly = TRUE)) stop("缺少jsonlite；请按操作指南准备环境")
  cfgfile <- normalizePath(getarg("--config"), mustWork = TRUE)
  step <- getarg("--step")
  if (!step %in% c("harmonise", "estimate", "all")) stop("不支持的step")
  allowed <- c("--config", "--step", "--dry-run")
  if (any(startsWith(args, "--") & !args %in% allowed)) stop("未知参数")
  cfg <- jsonlite::fromJSON(cfgfile)
  require_text <- function(key) {
    x <- cfg[[key]]
    if (!is.character(x) || length(x) != 1 || is.na(x) || !nzchar(trimws(x))) stop(paste("配置缺少", key))
    x
  }
  resolve <- function(key, exists = TRUE) {
    x <- require_text(key)
    if (!grepl("^(/|[A-Za-z]:)", x)) x <- file.path(dirname(cfgfile), x)
    normalizePath(x, mustWork = exists)
  }
  for (k in c("exposure_name", "outcome_name", "exposure_unit", "outcome_unit",
              "build_exposure", "build_outcome", "ancestry_exposure", "ancestry_outcome",
              "sample_overlap", "ld_reference")) require_text(k)
  if (!identical(cfg$build_exposure, cfg$build_outcome) ||
      !identical(cfg$ancestry_exposure, cfg$ancestry_outcome)) stop("build/祖源不一致；需专门设计，不能直接运行")
  if (!isTRUE(cfg$independent_instruments_reviewed)) stop("必须先审查独立工具及LD记录")
  if (!cfg$sample_overlap %in% c("none", "known", "unknown")) stop("sample_overlap须为none/known/unknown")
  if (cfg$sample_overlap != "none") require_text("limitations")
  ep <- resolve("exposure"); op <- resolve("outcome"); ip <- resolve("instruments")
  cp <- resolve("clumping_record"); out <- resolve("output", FALSE)
  if (!dir.exists(dirname(out))) stop("请先准备仓库外的输出父目录")
  out <- file.path(normalizePath(dirname(out), mustWork=TRUE), basename(out))
  # Reject existing destinations and any destination inside this skill's repository.
  if (file.exists(out) || dir.exists(out)) stop("输出已存在；请指定新目录")
  self <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])
  ancestor <- dirname(normalizePath(self, mustWork = TRUE))
  repeat {
    if (dir.exists(file.path(ancestor, ".git")) || file.exists(file.path(ancestor, ".speedskills", "marketplace.json"))) {
      if (identical(out, ancestor) || startsWith(out, paste0(ancestor, "/"))) stop("结果不能写入源码仓库")
      break
    }
    parent <- dirname(ancestor); if (parent == ancestor) break; ancestor <- parent
  }
  action <- cfg$harmonise_action
  if (length(action) != 1 || !action %in% c(1, 2, 3)) stop("harmonise_action须为1/2/3")
  if (action == 1) stop("本入口不接受忽略链方向的action=1；明确协调后使用基础计算入口")
  if (length(cfg$seed) != 1 || !is.finite(cfg$seed)) stop("需要有效seed")
  if ("--dry-run" %in% args) {
    print(list(step = step, exposure = ep, outcome = op, instruments = ip, output = out,
               note = "未运行、未写入；正式运行仍需TwoSampleMR及数据检查"))
    quit(status = 0)
  }
  if (!requireNamespace("TwoSampleMR", quietly = TRUE)) stop("缺少TwoSampleMR；未执行")
  ids <- readLines(ip, warn = FALSE); ids <- trimws(ids)
  if (!length(ids) || any(!nzchar(ids)) || anyDuplicated(ids)) stop("工具清单须为非空、无表头、唯一SNP")
  read_side <- function(path, type) {
    d <- read.delim(path, check.names = FALSE, stringsAsFactors = FALSE)
    req <- c("SNP", "BETA", "SE", "EA", "NEA", "P")
    if (!all(req %in% names(d))) stop(paste(type, "缺少标准字段"))
    d <- d[d$SNP %in% ids, , drop = FALSE]
    if (!nrow(d) || anyDuplicated(d$SNP)) stop(paste(type, "工具为空或重复"))
    for (k in c("BETA", "SE", "P")) {
      d[[k]] <- suppressWarnings(as.numeric(d[[k]]))
      if (any(!is.finite(d[[k]]))) stop(paste(type, k, "非有限数值"))
    }
    if (any(d$SE <= 0 | d$P <= 0 | d$P > 1)) stop("SE/P不合法")
    if (any(!d$EA %in% c("A","C","G","T") | !d$NEA %in% c("A","C","G","T") | d$EA == d$NEA)) stop("只接受已规范化双等位SNP")
    for (k in intersect(c("EAF", "N"), names(d))) {
      d[[k]] <- suppressWarnings(as.numeric(d[[k]]))
      if (any(!is.finite(d[[k]]))) stop(paste(k, "不完整；先处理缺失"))
    }
    if ("EAF" %in% names(d) && any(d$EAF <= 0 | d$EAF >= 1)) stop("EAF须在0和1之间")
    if ("N" %in% names(d) && any(d$N <= 0)) stop("N必须为正")
    if (type == "exposure" && any(d$BETA == 0)) stop("暴露效应为0")
    d$Phenotype <- if (type == "exposure") cfg$exposure_name else cfg$outcome_name
    TwoSampleMR::format_data(d, type = type, snp_col = "SNP", beta_col = "BETA",
      se_col = "SE", effect_allele_col = "EA", other_allele_col = "NEA",
      eaf_col = "EAF", pval_col = "P", samplesize_col = "N", phenotype_col = "Phenotype")
  }
  e <- read_side(ep, "exposure"); o <- read_side(op, "outcome")
  d <- TwoSampleMR::harmonise_data(e, o, action = action)
  if (!nrow(d)) stop("无共同工具")
  d$F_exposure <- (d$beta.exposure / d$se.exposure)^2
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  if (!dir.exists(out)) stop("无法创建输出")
  write_table <- function(x, name) write.table(x, file.path(out, paste0(name, ".tsv")), sep="\t", quote=FALSE, row.names=FALSE, na="NA")
  write_table(d, "harmonized")
  write_table(d[!d$mr_keep | is.na(d$mr_keep), , drop=FALSE], "excluded")
  missing <- data.frame(SNP=ids, in_exposure=ids %in% e$SNP, in_outcome=ids %in% o$SNP)
  write_table(missing, "instrument_coverage")
  jsonlite::write_json(cfg, file.path(out, "config.used.json"), auto_unbox=TRUE, pretty=TRUE)
  write_table(data.frame(file=c(ep,op,ip,cp), md5=unname(tools::md5sum(c(ep,op,ip,cp)))), "input_checksums")
  capture.output(sessionInfo(), file=file.path(out, "sessionInfo.txt"))
  set.seed(cfg$seed)
  parameters <- TwoSampleMR::default_parameters()
  jsonlite::write_json(parameters, file.path(out, "backend_parameters.json"), auto_unbox=TRUE, pretty=TRUE)
  status <- data.frame(operation=character(), state=character(), detail=character())
  record <- function(name, state, detail="") {
    status <<- rbind(status, data.frame(operation=name, state=state, detail=gsub("[\r\n\t]", " ", detail)))
    write_table(status, "status")
  }
  attempt <- function(name, expr) {
    tryCatch({
      x <- force(expr)
      if (!is.data.frame(x) || !nrow(x)) { record(name, "not_estimable", "空结果"); return(NULL) }
      write_table(x, name); record(name, "completed")
      x
    }, error=function(err) { record(name, "failed", conditionMessage(err)); NULL })
  }
  n <- sum(d$mr_keep %in% TRUE)
  record("harmonise", if (n > 0) "completed" else "blocked", paste("保留工具", n))
  if (n == 0) stop("协调后没有可用工具；保留排除记录")
  if (step != "harmonise") {
    methods <- cfg$methods
    supported <- c("mr_ivw", "mr_ivw_fe", "mr_ivw_mre", "mr_egger_regression", "mr_weighted_median", "mr_weighted_mode")
    if (!is.character(methods) || !length(methods) || anyDuplicated(methods) || any(!methods %in% supported)) stop("methods重复或包含未封装方法")
    primary <- require_text("primary_method")
    if (!primary %in% methods) stop("主要方法必须包含于预设methods")
    if (n == 1) { methods <- "mr_wald_ratio"; primary <- "mr_wald_ratio" }
    rows <- list()
    for (method in methods) {
      if (n == 2 && !method %in% c("mr_ivw", "mr_ivw_fe", "mr_ivw_mre")) {
        record(method, "not_applicable", "本入口至少3个工具才运行此敏感方法"); next
      }
      x <- attempt(method, TwoSampleMR::mr(d, parameters=parameters, method_list=method))
      if (!is.null(x)) {
        if (!all(c("b","se","pval") %in% names(x)) || any(!is.finite(x$b) | !is.finite(x$se) | x$se <= 0 | !is.finite(x$pval) | x$pval < 0 | x$pval > 1)) {
          record(method, "not_estimable", "后端返回非有限估计/标准误"); next
        }
        # Match the test distribution used for the backend P value. The mode
        # backend exposes a t test even though its standalone CI uses normal.
        df <- if (method == "mr_egger_regression") n-2 else if (method == "mr_weighted_mode") n-1 else NA_real_
        critical <- if (is.finite(df)) qt(0.975, df=df) else qnorm(0.975)
        x$ci_low <- x$b - critical*x$se; x$ci_high <- x$b + critical*x$se
        x$ci_definition <- if (is.finite(df)) "t_95_percent_matching_backend_test" else "normal_approximation_95_percent"
        x$ci_df <- df
        x$analysis_role <- if (method == primary) "prespecified_primary" else "sensitivity"
        rows[[length(rows)+1]] <- x
      }
    }
    if (!length(rows)) stop("没有可估计主效应；查看status.tsv")
    write_table(do.call(rbind, rows), "estimates")
    if (!any(vapply(rows, function(x) any(x$analysis_role == "prespecified_primary"), logical(1)))) {
      record("primary_analysis", "not_estimable", "仅有敏感性结果；不事后改指定主要方法")
    }
    if (step == "all") {
      if (n >= 2) {
        attempt("heterogeneity", TwoSampleMR::mr_heterogeneity(d, method_list="mr_ivw"))
        attempt("single_snp", TwoSampleMR::mr_singlesnp(d, all_method="mr_ivw"))
      }
      if (n >= 3) {
        attempt("pleiotropy", TwoSampleMR::mr_pleiotropy_test(d))
        attempt("leave_one_out", TwoSampleMR::mr_leaveoneout(d))
      } else record("egger_and_leave_one_out", "not_applicable", "工具不足")
      record("directionality", "not_run", "需性状尺度/解释度等信息；按扩展指南单独执行")
    }
  }
  cat("已保存本次可用结果。请检查status.tsv；completed不代表工具假设成立。\n")
}, error=function(err) { message("错误：", conditionMessage(err)); quit(status=2) })
