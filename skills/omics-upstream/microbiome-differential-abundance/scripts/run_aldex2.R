#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4 || length(args) > 7) {
  stop("usage: run_aldex2.R abundance.tsv metadata.tsv group_column output_dir [mc_samples] [seed] [denom]")
}

suppressPackageStartupMessages(library(ALDEx2))

abundance_path <- args[[1]]
metadata_path <- args[[2]]
group_column <- args[[3]]
output_dir <- args[[4]]
mc_samples <- if (length(args) >= 5) as.integer(args[[5]]) else 128L
seed <- if (length(args) >= 6) as.integer(args[[6]]) else 42L
denom <- if (length(args) >= 7) args[[7]] else "all"

if (!file.exists(abundance_path) || !file.exists(metadata_path)) stop("input file missing")
if (is.na(mc_samples) || mc_samples < 16) stop("mc_samples must be at least 16")
if (is.na(seed)) stop("seed must be an integer")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

abundance <- as.matrix(read.delim(abundance_path, row.names = 1, check.names = FALSE, comment.char = "#"))
metadata <- read.delim(metadata_path, row.names = 1, check.names = FALSE)
if (!(group_column %in% colnames(metadata))) stop("group column not found in metadata")

column_overlap <- sum(colnames(abundance) %in% rownames(metadata))
row_overlap <- sum(rownames(abundance) %in% rownames(metadata))
if (column_overlap > row_overlap) {
  counts <- abundance
} else if (row_overlap > column_overlap) {
  counts <- t(abundance)
} else {
  stop("cannot determine table orientation from sample IDs")
}

samples <- intersect(colnames(counts), rownames(metadata))
if (length(samples) < 4) stop("fewer than four shared samples")
counts <- counts[, samples, drop = FALSE]
metadata <- metadata[samples, , drop = FALSE]
storage.mode(counts) <- "numeric"
if (any(!is.finite(counts)) || any(counts < 0) || any(counts != floor(counts))) {
  stop("ALDEx2 requires finite non-negative integer counts")
}
sample_totals <- colSums(counts)
if (all(abs(sample_totals - 100) < 5) || all(abs(sample_totals - 1) < 0.05)) {
  stop("sample totals resemble relative abundance rather than counts")
}

groups <- factor(metadata[[group_column]])
if (nlevels(groups) != 2) stop("this runner requires exactly two groups")
if (any(table(groups) < 2)) stop("each group needs at least two samples")

set.seed(seed)
fit <- aldex(
  as.data.frame(counts), as.character(groups), mc.samples = mc_samples,
  test = "welch", effect = TRUE, include.sample.summary = FALSE, denom = denom
)
fit$feature_id <- rownames(fit)
fit <- fit[, c("feature_id", setdiff(colnames(fit), "feature_id")), drop = FALSE]
write.table(fit, file.path(output_dir, "aldex2_results.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

metadata_lines <- c(
  paste("abundance", normalizePath(abundance_path), sep = "\t"),
  paste("metadata", normalizePath(metadata_path), sep = "\t"),
  paste("group_column", group_column, sep = "\t"),
  paste("group_levels", paste(levels(groups), collapse = "|"), sep = "\t"),
  paste("mc_samples", mc_samples, sep = "\t"),
  paste("denom", denom, sep = "\t"),
  paste("seed", seed, sep = "\t"),
  paste("R", R.version.string, sep = "\t"),
  paste("ALDEx2", as.character(packageVersion("ALDEx2")), sep = "\t")
)
writeLines(metadata_lines, file.path(output_dir, "aldex2_run.tsv"))
