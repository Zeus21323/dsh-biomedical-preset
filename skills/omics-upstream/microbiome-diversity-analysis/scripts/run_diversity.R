#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4 || length(args) > 6) {
  stop("usage: run_diversity.R abundance.tsv metadata.tsv group_column output_dir [permutations] [seed]")
}

suppressPackageStartupMessages(library(vegan))

abundance_path <- args[[1]]
metadata_path <- args[[2]]
group_column <- args[[3]]
output_dir <- args[[4]]
permutations <- if (length(args) >= 5) as.integer(args[[5]]) else 999L
seed <- if (length(args) >= 6) as.integer(args[[6]]) else 42L

if (!file.exists(abundance_path) || !file.exists(metadata_path)) stop("input file missing")
if (is.na(permutations) || permutations < 99) stop("permutations must be at least 99")
if (is.na(seed)) stop("seed must be an integer")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

abundance <- as.matrix(read.delim(abundance_path, row.names = 1, check.names = FALSE, comment.char = "#"))
metadata <- read.delim(metadata_path, row.names = 1, check.names = FALSE)
if (!(group_column %in% colnames(metadata))) stop("group column not found in metadata")

row_overlap <- sum(rownames(abundance) %in% rownames(metadata))
column_overlap <- sum(colnames(abundance) %in% rownames(metadata))
if (row_overlap > column_overlap) {
  sample_by_feature <- abundance
} else if (column_overlap > row_overlap) {
  sample_by_feature <- t(abundance)
} else {
  stop("cannot determine table orientation from sample IDs")
}

samples <- intersect(rownames(sample_by_feature), rownames(metadata))
if (length(samples) < 4) stop("fewer than four shared samples")
sample_by_feature <- sample_by_feature[samples, , drop = FALSE]
metadata <- metadata[samples, , drop = FALSE]
storage.mode(sample_by_feature) <- "numeric"
if (any(!is.finite(sample_by_feature)) || any(sample_by_feature < 0)) stop("abundance values must be finite and non-negative")
if (any(rowSums(sample_by_feature) == 0)) stop("all-zero sample found")

alpha <- data.frame(
  sample_id = rownames(sample_by_feature),
  observed = specnumber(sample_by_feature),
  shannon = diversity(sample_by_feature, index = "shannon"),
  simpson = diversity(sample_by_feature, index = "simpson"),
  group = metadata[[group_column]],
  check.names = FALSE
)
write.table(alpha, file.path(output_dir, "alpha_diversity.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

relative <- decostand(sample_by_feature, method = "total")
bray <- vegdist(relative, method = "bray")
write.table(as.matrix(bray), file.path(output_dir, "bray_curtis_distance.tsv"), sep = "\t", quote = FALSE, col.names = NA)

set.seed(seed)
design <- data.frame(group = factor(metadata[[group_column]]), row.names = rownames(metadata))
permanova <- adonis2(bray ~ group, data = design, permutations = permutations)
write.table(as.data.frame(permanova), file.path(output_dir, "permanova.tsv"), sep = "\t", quote = FALSE, col.names = NA)

dispersion <- betadisper(bray, design$group, sqrt.dist = TRUE)
write.table(as.data.frame(anova(dispersion)), file.path(output_dir, "dispersion_test.tsv"), sep = "\t", quote = FALSE, col.names = NA)

pcoa <- cmdscale(bray, k = 2, eig = TRUE)
positive_eigenvalues <- pcoa$eig[pcoa$eig > 0]
explained <- pcoa$eig[1:2] / sum(positive_eigenvalues)
coordinates <- data.frame(
  sample_id = rownames(pcoa$points),
  PC1 = pcoa$points[, 1], PC2 = pcoa$points[, 2],
  group = design[rownames(pcoa$points), "group"]
)
write.table(coordinates, file.path(output_dir, "pcoa_coordinates.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(data.frame(axis = c("PC1", "PC2"), explained_fraction = explained), file.path(output_dir, "pcoa_explained.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

metadata_lines <- c(
  paste("abundance", normalizePath(abundance_path), sep = "\t"),
  paste("metadata", normalizePath(metadata_path), sep = "\t"),
  paste("group_column", group_column, sep = "\t"),
  paste("permutations", permutations, sep = "\t"),
  paste("seed", seed, sep = "\t"),
  paste("R", R.version.string, sep = "\t"),
  paste("vegan", as.character(packageVersion("vegan")), sep = "\t")
)
writeLines(metadata_lines, file.path(output_dir, "diversity_run.tsv"))
