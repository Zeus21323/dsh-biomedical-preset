#!/usr/bin/env Rscript
# scarHRD 0.1.1+ 参考脚本；运行前以 packageVersion 和 ?scar_score 核对接口。

usage <- function() {
  cat(paste(
    "用法：Rscript compute_hrd.R 输入文件 grch37|grch38 [是否为seqz: TRUE|FALSE]",
    "      Rscript compute_hrd.R --self-test",
    sep = "\n"
  ))
  cat("\n")
}

parse_bool <- function(value) {
  normalized <- toupper(value)
  if (!normalized %in% c("TRUE", "FALSE")) {
    stop("是否为seqz 只能是 TRUE 或 FALSE", call. = FALSE)
  }
  normalized == "TRUE"
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 1 && args[[1]] %in% c("--help", "-h")) {
  usage()
  quit(status = 0)
}
if (length(args) == 1 && args[[1]] == "--self-test") {
  stopifnot(parse_bool("TRUE"), !parse_bool("false"))
  cat("ok: HRD argument self-test\n")
  quit(status = 0)
}
if (length(args) < 2) {
  usage()
  stop("缺少必需参数", call. = FALSE)
}

input <- args[[1]]
reference <- tolower(args[[2]])
is_seqz <- if (length(args) >= 3) parse_bool(args[[3]]) else TRUE
if (!file.exists(input)) stop(paste("输入文件不存在", input), call. = FALSE)
if (!reference %in% c("grch37", "grch38")) {
  stop("参考基因组只能是 grch37 或 grch38", call. = FALSE)
}
if (!requireNamespace("scarHRD", quietly = TRUE)) {
  stop("需要安装 scarHRD，并在运行前核对 scar_score 接口", call. = FALSE)
}

# 输入必须是Sequenza .seqz或包含A/B等位拷贝数和倍性的分段表，不能使用相对log2比值。
result <- scarHRD::scar_score(input, reference = reference, seqz = is_seqz)
print(result)

loh <- result[["HRD"]]
tai <- result[["Telomeric AI"]]
lst <- result[["LST"]]
total <- result[["HRD-sum"]]
cat(sprintf("LOH=%d\tTAI=%d\tLST=%d\tHRD-sum=%d\n", loh, tai, lst, total))

if (lst > loh + tai) {
  message("LST占主导：请核对倍性、肿瘤全基因组加倍和分段质量，防止HRD假高。")
}
message("HRD瘢痕反映既往同源重组缺陷；请联合当前HR通路状态并使用平台验证阈值。")
