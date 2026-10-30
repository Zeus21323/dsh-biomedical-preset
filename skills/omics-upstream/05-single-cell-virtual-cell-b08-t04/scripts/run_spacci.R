#!/usr/bin/env Rscript
options(stringsAsFactors = FALSE, warn = 1)
args <- commandArgs(TRUE)
file_arg <- sub("^--file=", "", commandArgs()[grepl("^--file=", commandArgs())][1])
script_dir <- dirname(normalizePath(file_arg))
source(file.path(script_dir, "native_expression_context.R"))
c <- native_expression_context(args, "SpaCCI", "SpaCCI", "1.0.3",
                               counts_input = FALSE, species = c("human", "mouse"))
cfg <- c$cfg
for (key in c("native_root", "input_provenance", "coordinate_provenance", "coordinate_unit")) {
  if (is.null(cfg[[key]])) stop("缺少：", key)
}
if (!cfg$coordinate_unit %in% c("um", "pixel", "native")) stop("coordinate_unit必须为um、pixel或native")
if (cfg$coordinate_unit == "native" && !isTRUE(cfg$physical_scale_unavailable)) {
  stop("原生坐标单位必须明确physical_scale_unavailable=true")
}
needed <- c("nnls", "FNN", "Rcpp", "RcppArmadillo", "digest")
missing <- needed[!vapply(needed, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("缺少SpaCCI原生依赖：", paste(missing, collapse = ", "))
# Upstream C++ resolves nnls through package:nnls, although SpaCCI only imports it.
# Attaching the package is therefore required for the fixed native implementation.
suppressPackageStartupMessages({library(nnls); library(SpaCCI); library(Matrix)})

root <- c$resolve(cfg$native_root)
expected <- c(
  "DESCRIPTION" = "da0235e480ab477cbf0b54ed5624200aafd3a6d7fa789d511075cf97836a8abe",
  "NAMESPACE" = "1363dcf6b5667b8683b47ff4a7f35c0634ea0c76b76c68feef405210af409858",
  "R/run_SpaCCI.R" = "20f6c3f9653d912999cb90cc653fd9e9800b6dea12e2588a55f2a836caa9b443",
  "R/modeling.R" = "c2405609e7bb4081c582b03f54b3a4de3efe63d3edf18778a19adbcdbf31c6ab",
  "R/database.R" = "62848c4ab8fe41aed876edb6992e822adc1f071d78efe6367871e3475d7c9287",
  "R/visiualization.R" = "1cb65e1f3728829c4ab863cc3f654cfe1adbeee8fb2a0e651a6197bd469813e6",
  "src/permutation_func.cpp" = "8c2004d66d03202fcc33f5cab79268be1c8007931d661c0e416ee0e86a7a0570",
  "src/RcppExports.cpp" = "746a9e7a347f8c09726a8cb32e96271b2900aa0bd57f8d127482ad24e1977171"
)
for (path in names(expected)) if (c$hash(file.path(root, path)) != expected[[path]]) stop("SpaCCI固定源码摘要不符：", path)
body_expected <- c(
  run_SpaCCI = "f181186c022162a9795231f6fdbbb30b1051ad5fdc17669578ef80ba6c539262",
  SpaCCI_global = "6a2477e1e11f665ae94ce85fe591dea6143c3a50786b7af81bd32e8ddca3a9c9",
  SpaCCI_region = "7912627db0d02ace1c8dbef20a767c37f04c0ea4931e67e1b89bccd2e02c4606",
  SpaCCI_local = "31c3df9eeb77589d7a2fc654e0c707a899a49db42760d7ad77432eba25e1d36e",
  Find_regional_IDs = "96d01f7900668c650e7878ec91d3d51607468d5df060bc214fed8de124c20059",
  GetShuffledCT = "a304db7b925429b5b5801404d3ce5e025ca0fcecc10d136f2d32880244b7fcbb",
  random_region = "e716066a413fe60c1865119d1b535aefdd3eb78f63c5c9020cada4674caea6b5",
  LR_database = "c0a8ccbc343daa1da777dd10bc2d76c769e5b60ec54c39713ea5cab1c08b7375"
)
for (fn in names(body_expected)) {
  actual <- digest::digest(body(get(fn, envir = asNamespace("SpaCCI"))), algo = "sha256")
  if (actual != body_expected[[fn]]) stop("已安装SpaCCI函数体摘要不符：", fn)
}

resource_hashes <- c(
  "CellChatDB.rda" = "81d2e64e2517333f2d675255d80408d975a24727eda9a88b0e8031e27bec66ca",
  "Cellinker_Human_interactions.txt" = "c41d8fe7677feab96ba444fd96e4e005700ebbd51031bb38b71c32e1786974d4",
  "Cellinker_Mouse_interactions.txt" = "5dbd6e670155f8bf11e9c53e027dae2b4883c53623db70996f64584b41a4e175",
  "cellphoneDB_interactions.csv" = "3cf0ceace45dcb42478f0e6a7be9a50104794eac68d731f7c82d4c13325175ab",
  "ConnectomeDB_2020_Human_interactions.RData" = "574a0d5ff16f8ada9f8e5f38e1a01b2d94fe5bcb3e329e9b5e9f287c3160eb9f",
  "ICELLNET_Human_interactions.csv" = "37c7aae0787db9bd203aba8cd4df02cfa503648064b4f04d6a0bd138ca77c50c"
)
database <- cfg$database %||% "CellChat"
if (!database %in% c("CellChat", "CellPhoneDB", "Cellinker", "ICELLNET", "ConnectomeDB")) {
  stop("database只接受CellChat、CellPhoneDB、Cellinker、ICELLNET或ConnectomeDB")
}
if (cfg$species == "mouse" && database %in% c("CellPhoneDB", "ICELLNET", "ConnectomeDB")) {
  stop(database, "在SpaCCI固定分支中仅有人类资源；不自动作同源替换")
}
resource_name <- switch(database,
  CellChat = "CellChatDB.rda",
  CellPhoneDB = "cellphoneDB_interactions.csv",
  Cellinker = if (cfg$species == "mouse") "Cellinker_Mouse_interactions.txt" else "Cellinker_Human_interactions.txt",
  ICELLNET = "ICELLNET_Human_interactions.csv",
  ConnectomeDB = "ConnectomeDB_2020_Human_interactions.RData")
installed_resource <- system.file("extdata", resource_name, package = "SpaCCI")
if (!nzchar(installed_resource) || c$hash(installed_resource) != resource_hashes[[resource_name]]) {
  stop("SpaCCI内置LR资源缺失或摘要不符：", resource_name)
}
source_resource <- file.path(root, "inst", "extdata", resource_name)
if (c$hash(source_resource) != resource_hashes[[resource_name]]) stop("固定源码中LR资源摘要不符")

input_object <- readRDS(c$input)
coordinates <- input_object$coordinates
proportions <- input_object$cell_proportions
if (is.null(coordinates) || is.null(rownames(coordinates)) || anyDuplicated(rownames(coordinates)) ||
    !setequal(rownames(coordinates), colnames(c$expr))) stop("需要与空间位置唯一对齐的coordinates")
if (is.null(proportions) || is.null(rownames(proportions)) || is.null(colnames(proportions)) ||
    anyDuplicated(rownames(proportions)) || anyDuplicated(colnames(proportions)) ||
    !setequal(rownames(proportions), colnames(c$expr))) stop("需要与空间位置唯一对齐的cell_proportions")
x_column <- cfg$x_column %||% "imagecol"
y_column <- cfg$y_column %||% "imagerow"
if (!all(c(x_column, y_column) %in% colnames(coordinates)) || x_column == y_column) {
  stop("coordinates必须含配置的两个不同坐标列")
}
coordinates <- as.data.frame(coordinates[colnames(c$expr), c(x_column, y_column), drop = FALSE], check.names = FALSE)
colnames(coordinates) <- c("imagecol", "imagerow")
coordinates$Spot_ID <- rownames(coordinates)
if (any(!is.finite(as.matrix(coordinates[, c("imagecol", "imagerow")]))) ) stop("空间坐标必须有限")
proportions <- as.data.frame(proportions[colnames(c$expr), , drop = FALSE], check.names = FALSE)
pv <- as.matrix(proportions)
if (!is.numeric(pv) || any(!is.finite(pv)) || any(pv < 0) || any(rowSums(pv) <= 0)) {
  stop("cell_proportions必须为有限非负数，且每个位置的总比例大于0")
}
sum_tolerance <- as.numeric(cfg$proportion_sum_tolerance %||% 0.02)
if (!is.finite(sum_tolerance) || sum_tolerance < 0 || any(abs(rowSums(pv) - 1) > sum_tolerance)) {
  stop("cell_proportions行和必须在1附近；运行器不自动重标准化观测比例")
}
maximum_dense <- as.numeric(cfg$maximum_dense_elements %||% 5e7)
if (!is.finite(maximum_dense) || maximum_dense < 1 || nrow(c$expr) * ncol(c$expr) > maximum_dense) {
  stop("SpaCCI原生实现会稠密化表达矩阵；输入超过maximum_dense_elements声明的上限")
}

alpha <- as.numeric(cfg$alpha %||% 0.05)
percentage <- as.numeric(cfg$expression_percentage %||% 10)
seed <- as.integer(cfg$seed %||% 1234L)
local_prop <- as.numeric(cfg$local_scale_proportion %||% 1)
local_radius <- as.numeric(cfg$neighborhood_radius %||% 2.5)
if (!is.finite(alpha) || alpha <= 0 || alpha >= 1 || !is.finite(percentage) || percentage < 0 || percentage > 100 ||
    is.na(seed) || !is.finite(local_prop) || local_prop <= 0 || local_prop > 1 ||
    !is.finite(local_radius) || local_radius <= 0) stop("SpaCCI科学参数无效")
support_metric <- cfg$support_metric %||% "bh_within_sample_scale"
if (!support_metric %in% c("raw_p", "bh_within_lr", "bh_within_sample_scale")) {
  stop("support_metric只接受raw_p、bh_within_lr或bh_within_sample_scale")
}
run_regional <- isTRUE(cfg$run_regional)
region_key <- cfg$region_key
if (run_regional && (is.null(region_key) || !region_key %in% colnames(c$meta))) {
  stop("run_regional=true时必须提供metadata中的region_key")
}
requested_regions <- as.character(cfg$regional_values %||% character())
requested_local <- as.character(cfg$local_lr_pairs %||% character())
run_local <- length(requested_local) > 0

params <- list(commit = "87ce16eb75a901440f4744594b7eae247cd6fead", database = database,
  database_resource = resource_name, database_sha256 = resource_hashes[[resource_name]],
  expression_percentage = percentage, alpha = alpha, support_metric = support_metric,
  seed = seed, run_regional = run_regional, regional_values = requested_regions,
  local_lr_pairs = requested_local, local_scale_proportion = local_prop,
  neighborhood_radius = local_radius, global_permutations = 500L,
  regional_permutations = 1000L)
c$start_cache(c(unname(expected), resource_hashes[[resource_name]]), params)
c$bundle$implementation <- "native_SpaCCI_1.0.3_with_explicit_BH_recalculation"
c$bundle$provenance$input_provenance <- cfg$input_provenance
c$bundle$provenance$coordinate_provenance <- cfg$coordinate_provenance
c$bundle$provenance$coordinate_unit <- cfg$coordinate_unit
c$bundle$provenance$upstream <- list(url = "https://github.com/LitingKu/SpaCCI",
  commit = params$commit, version = "1.0.3", tag = NULL, license = "GPL (>= 2)")
c$bundle$provenance$source_sha256 <- as.list(expected)
c$bundle$provenance$database <- list(name = database, bundled_resource = resource_name,
  sha256 = resource_hashes[[resource_name]], fixed_commit = params$commit,
  expression_percentage = percentage)
c$bundle$provenance$statistical_semantics <- list(
  score = "NNLS estimates a cell-type coefficient for each ligand/receptor component; complex components use a geometric mean. Their outer product is transformed as t/(0.5+t) and multiplied by the outer product of mean cell-type proportions.",
  spatial_filter = "Global and regional candidates are retained only where a directed 15-nearest-neighbor cell-proportion cross-product is nonzero. That cross-product filters candidates but is not multiplied into the reported strength.",
  permutation = "Global uses 500 permutations of proportion rows and cell-type columns. Regional uses 1000 equally sized regions drawn without replacement from outside the observed region plus deranged cell-type columns. Local uses floor(n_spots/500)*100 permutations, clamped to 1..1000, with spatially contiguous regions centered outside the observed neighborhood and deranged cell-type columns. P=count(null strength strictly greater than observed)/nboot, without pseudocount.",
  multiple_testing = "SpaCCI 1.0.3 computes BH and immediately overwrites adjusted.PValue with raw P in global, regional and local code. The adapter preserves this native field as native_adjusted_p_value and separately adds BH within each LR and BH across the complete sample/scale candidate family; support_metric states which value defines support.",
  statistical_unit = "spots pooled within a sample or a user-defined spatial region; permutations are not independent-donor condition tests")

empty_edges <- function() data.frame(sample=character(), donor=character(), condition=character(),
  source=character(), target=character(), ligand=character(), receptor=character(),
  interaction=character(), score=numeric(), tested=logical(), supported=logical(),
  scale=character(), region=character(), p_value=numeric(), q_value=numeric(),
  q_within_lr=numeric(), native_adjusted_p_value=numeric(), pathway=character(),
  center_spot=character())
edge_blocks <- list(global = list(), regional = list(), local = list())
spatial_tables <- list()
diagnostics <- list()
local_detail_artifacts <- list()
cell_types_by_sample <- list()
native_index <- 0L

prepare_lr <- function(expression) {
  db <- SpaCCI::LR_database(if (cfg$species == "human") "Human" else "Mouse", database, expression, percentage)
  pairs <- db$possible_LR_pairs
  info <- db$possible_LR_pairs_info
  if (!nrow(pairs)) stop("按固定数据库与表达比例过滤后没有可检验LR")
  ligand <- vapply(pairs$ligand_vector, paste, character(1), collapse = "+")
  receptor <- vapply(pairs$receptor_vector, paste, character(1), collapse = "+")
  interaction <- if ("interaction_name" %in% names(info)) as.character(info$interaction_name) else paste(ligand, receptor, sep = "_")
  pathway <- if ("pathway_name" %in% names(info)) as.character(info$pathway_name) else rep("unannotated", length(interaction))
  if (anyNA(interaction) || any(!nzchar(interaction)) || anyDuplicated(interaction)) {
    stop("SpaCCI资源过滤后interaction_name缺失或重复，无法无歧义连接分子组成")
  }
  info$.codex_ligand <- ligand
  info$.codex_receptor <- receptor
  info$.codex_interaction <- interaction
  info$.codex_pathway <- pathway
  keep <- seq_along(interaction)
  requested <- as.character(cfg$lr_interactions %||% character())
  if (length(requested)) {
    absent <- setdiff(requested, interaction)
    if (length(absent)) stop("请求的LR未通过原生数据库/表达过滤：", paste(absent, collapse = ", "))
    keep <- match(requested, interaction)
  }
  list(possible_LR_pairs = pairs[keep, , drop = FALSE],
       possible_LR_pairs_info = info[keep, , drop = FALSE])
}

standardize <- function(z, sample, donor, condition, scale, region = "whole_slide") {
  if (is.null(z) || !nrow(z)) return(empty_edges())
  required <- c("Cell_type_Ligand", "Cell_type_Receptor", "strength", "PValue",
                "adjusted.PValue", ".codex_ligand", ".codex_receptor", ".codex_interaction", ".codex_pathway")
  if (!all(required %in% names(z))) stop("SpaCCI原生结果缺少结构化输出列")
  if (any(!is.finite(z$strength)) || any(!is.finite(z$PValue)) ||
      any(z$PValue < 0 | z$PValue > 1) || any(abs(z$adjusted.PValue - z$PValue) > 1e-15)) {
    stop("SpaCCI原生强度/P值无效，或上游覆盖BH的已知行为发生变化")
  }
  q_lr <- ave(z$PValue, z$.codex_interaction, FUN = function(v) p.adjust(v, method = "BH"))
  q_scope <- p.adjust(z$PValue, method = "BH")
  support_value <- switch(support_metric, raw_p = z$PValue,
                          bh_within_lr = q_lr, bh_within_sample_scale = q_scope)
  data.frame(sample=sample, donor=donor, condition=condition,
    source=as.character(z$Cell_type_Ligand), target=as.character(z$Cell_type_Receptor),
    ligand=as.character(z$.codex_ligand), receptor=as.character(z$.codex_receptor),
    interaction=as.character(z$.codex_interaction), score=as.numeric(z$strength),
    tested=TRUE, supported=support_value <= alpha, scale=scale, region=region,
    p_value=as.numeric(z$PValue), q_value=as.numeric(q_scope), q_within_lr=as.numeric(q_lr),
    native_adjusted_p_value=as.numeric(z$adjusted.PValue), pathway=as.character(z$.codex_pathway),
    stringsAsFactors=FALSE)
}

samples <- unique(as.character(c$meta$sample))
for (si in seq_along(samples)) {
  sample <- samples[[si]]
  ids <- rownames(c$meta)[as.character(c$meta$sample) == sample]
  if (length(ids) < 16L) stop("样本", sample, "少于16个空间位置，无法构建原生15近邻")
  metadata <- c$meta[ids, , drop = FALSE]
  donor <- unique(as.character(metadata$donor)); condition <- unique(as.character(metadata$condition))
  expression <- as.data.frame(as.matrix(c$expr[, ids, drop = FALSE]), check.names = FALSE)
  props <- proportions[ids, , drop = FALSE]
  cell_types_by_sample[[sample]] <- colnames(props)
  coords <- coordinates[ids, , drop = FALSE]
  lr <- prepare_lr(expression)
  set.seed(seed + si - 1L)
  native_index <- native_index + 1L
  global <- c$native(native_index, paste(sample, "global", sep = "::"), function() {
    SpaCCI::run_SpaCCI(expression, props, coords, lr, analysis_scale = "global")
  })
  global_edges <- standardize(global$pvalue_df, sample, donor, condition, "global")
  if (!nrow(global_edges)) stop("样本", sample, "的SpaCCI global没有可交付候选")
  edge_blocks$global[[sample]] <- global_edges

  region_values <- character()
  if (run_regional) {
    region_values <- if (length(requested_regions)) requested_regions else unique(as.character(metadata[[region_key]]))
    if (anyNA(metadata[[region_key]]) || any(!nzchar(trimws(as.character(metadata[[region_key]]))))) stop("region_key含缺失或空标签")
    absent <- setdiff(region_values, unique(as.character(metadata[[region_key]])))
    if (length(absent)) stop("样本", sample, "缺少请求区域：", paste(absent, collapse = ", "))
    for (ri in seq_along(region_values)) {
      region <- region_values[[ri]]
      region_ids <- rownames(metadata)[as.character(metadata[[region_key]]) == region]
      if (length(region_ids) < 16L) stop("区域", region, "少于16个位置，无法构建15近邻")
      if (length(ids) - length(region_ids) < length(region_ids)) {
        stop("区域", region, "大于全样本一半；原生置换需从区域外无放回抽取同样数量的位置")
      }
      set.seed(seed + si * 1000L + ri)
      native_index <- native_index + 1L
      regional <- c$native(native_index, paste(sample, "regional", region, sep = "::"), function() {
        SpaCCI::run_SpaCCI(expression, props, coords, lr, analysis_scale = "regional", region_spot_IDs = region_ids)
      })
      edge_blocks$regional[[paste(sample, region, sep="::")]] <- standardize(
        regional$pvalue_df, sample, donor, condition, "regional", region)
      map <- data.frame(sample=sample, cell=ids, x=coords$imagecol, y=coords$imagerow,
        value=ifelse(ids %in% region_ids, 1, 0), stringsAsFactors=FALSE)
      spatial_tables[[paste0("region_", si, "_", ri)]] <- list(rows=map,
        id=sprintf("spacci_region_membership_%03d", length(spatial_tables)+1L),
        title=paste(sample, region, "region membership"), axis="Selected region (1=yes)",
        definition=paste0("区域", region, "的实际位置成员；1表示进入regional分析，0表示作为区域外置换候选。"))
    }
  }

  local_center_count <- 0L
  if (run_local) {
    if (length(ids) < 500L) stop("SpaCCI local原生nboot在少于500个位置时只有1次；论文级入口拒绝执行")
    available <- as.character(lr$possible_LR_pairs_info$.codex_interaction)
    absent <- setdiff(requested_local, available)
    if (length(absent)) stop("请求的local LR未通过当前样本的数据库/表达过滤：", paste(absent, collapse=", "))
    local_lr <- list(possible_LR_pairs=lr$possible_LR_pairs[match(requested_local, available), , drop=FALSE],
      possible_LR_pairs_info=lr$possible_LR_pairs_info[match(requested_local, available), , drop=FALSE])
    set.seed(seed + si * 100000L)
    native_index <- native_index + 1L
    local <- c$native(native_index, paste(sample, "local", sep = "::"), function() {
      SpaCCI::run_SpaCCI(expression, props, coords, local_lr, specific_LR_pair=requested_local,
        analysis_scale="local", local_scale_proportion=local_prop, neighborhood_radius=local_radius)
    })
    center_names <- names(local$dataframelist)
    if (!length(center_names)) stop("样本", sample, "没有至少6个位置的合格SpaCCI local邻域")
    local_center_count <- length(center_names)
    local_rows <- lapply(center_names, function(center) {
      z <- standardize(local$dataframelist[[center]], sample, donor, condition, "local", center)
      if (nrow(z)) z$center_spot <- center
      z
    })
    local_edges <- do.call(rbind, local_rows)
    detail_name <- sprintf("local_center_results_%03d.tsv", si)
    c$wt(local_edges, detail_name)
    local_detail_artifacts[[sample]] <- list(path=detail_name,
      sha256=c$hash(file.path(c$out, detail_name)), rows=nrow(local_edges),
      definition="每个合格局部中心的完整原生强度、P值和重算BH；网络摘要不替代此细节表。")
    if (nrow(local_edges)) {
      local_key <- paste(local_edges$interaction, local_edges$source, local_edges$target, sep="\r")
      local_summary <- do.call(rbind, lapply(split(seq_len(nrow(local_edges)), local_key), function(index) {
        z <- local_edges[index, , drop=FALSE]
        first <- z[1, , drop=FALSE]
        data.frame(sample=first$sample, donor=first$donor, condition=first$condition,
          source=first$source, target=first$target, ligand=first$ligand, receptor=first$receptor,
          interaction=first$interaction, score=sum(z$supported), tested=TRUE,
          supported=any(z$supported), scale="local", region="whole_slide",
          p_value=NA_real_, q_value=NA_real_, q_within_lr=NA_real_,
          native_adjusted_p_value=NA_real_, pathway=first$pathway, center_spot="summary",
          tested_centers=nrow(z), supported_centers=sum(z$supported),
          support_fraction=sum(z$supported)/nrow(z), maximum_native_strength=max(z$score),
          stringsAsFactors=FALSE)
      }))
    } else local_summary <- empty_edges()
    edge_blocks$local[[sample]] <- local_summary
    neighborhood_rows <- do.call(rbind, lapply(center_names, function(center) {
      members <- local$RegionIDs_matrix[[center]]
      dx <- coords[members, "imagecol"] - coords[center, "imagecol"]
      dy <- coords[members, "imagerow"] - coords[center, "imagerow"]
      data.frame(sample=sample, center_spot=center, neighborhood_spots=length(members),
        maximum_included_distance=max(sqrt(dx^2+dy^2)), stringsAsFactors=FALSE)
    }))
    c$wt(neighborhood_rows, sprintf("local_neighborhoods_%03d.tsv", si))
    for (li in seq_along(requested_local)) {
      interaction <- requested_local[[li]]
      subset <- local_edges[local_edges$interaction == interaction, , drop=FALSE]
      if (!nrow(subset)) next
      pair_summary <- merge(
        aggregate(q_value ~ source + target, subset, FUN=function(v) min(v, na.rm=TRUE)),
        aggregate(score ~ source + target, subset, FUN=function(v) max(v, na.rm=TRUE)),
        by=c("source", "target"), sort=FALSE)
      pair_summary <- pair_summary[order(pair_summary$q_value, -pair_summary$score,
        pair_summary$source, pair_summary$target), , drop=FALSE]
      focus_source <- pair_summary$source[[1]]; focus_target <- pair_summary$target[[1]]
      focus <- subset[subset$source == focus_source & subset$target == focus_target, , drop=FALSE]
      if (anyDuplicated(focus$center_spot)) stop("SpaCCI local同一中心的分子与细胞对不唯一")
      idx <- match(ids, focus$center_spot)
      strength_map <- data.frame(sample=sample, cell=ids, x=coords$imagecol, y=coords$imagerow,
        value=focus$score[idx], stringsAsFactors=FALSE)
      q_floor <- 1 / min(1000L, max(1L, floor(length(ids)/500L)*100L))
      evidence <- -log10(pmax(focus$q_value, q_floor))
      evidence[!focus$supported] <- 0
      evidence_map <- data.frame(sample=sample, cell=ids, x=coords$imagecol, y=coords$imagerow,
        value=evidence[idx], stringsAsFactors=FALSE)
      base_title <- paste(interaction, focus_source, "to", focus_target)
      spatial_tables[[paste0("local_strength_", si, "_", li)]] <- list(rows=strength_map,
        id=sprintf("spacci_local_strength_%03d", length(spatial_tables)+1L),
        title=paste(base_title, "local strength"), axis="SpaCCI local strength",
        definition=paste0("原生SpaCCI local强度；展示", focus_source, "→", focus_target,
          "的", interaction, "。灰色位置未进入合格邻域或原生结果未保留该候选，不解释为0。"))
      spatial_tables[[paste0("local_evidence_", si, "_", li)]] <- list(rows=evidence_map,
        id=sprintf("spacci_local_evidence_%03d", length(spatial_tables)+1L),
        title=paste(base_title, "local BH evidence"), axis="Supported -log10(q), floored",
        definition=paste0("仅对support_metric支持的局部中心显示-log10(q)；q=0按原生置换分辨率", signif(q_floor,3),
          "作图下限截断，不改写源表P/q。不支持中心置0，灰色位置未检验或未保留候选。"))
      center_counts <- aggregate(supported ~ center_spot, subset, FUN=sum)
      count_idx <- match(ids, center_counts$center_spot)
      count_map <- data.frame(sample=sample, cell=ids, x=coords$imagecol, y=coords$imagerow,
        value=center_counts$supported[count_idx], stringsAsFactors=FALSE)
      spatial_tables[[paste0("local_count_", si, "_", li)]] <- list(rows=count_map,
        id=sprintf("spacci_local_supported_count_%03d", length(spatial_tables)+1L),
        title=paste(interaction, "local supported cell-pair count"), axis="BH-supported cell pairs",
        definition=paste0("每个合格局部中心中", interaction,
          "通过声明support_metric的有向细胞类型对数；灰色位置未进入邻域检验。"))
    }
  }
  diagnostics[[sample]] <- data.frame(sample=sample, donor=donor, condition=condition,
    spots=length(ids), cell_types=ncol(props), tested_lr=nrow(lr$possible_LR_pairs),
    global_candidates=nrow(global_edges), global_raw_p_supported=sum(global_edges$p_value<=alpha),
    global_bh_supported=sum(global_edges$q_value<=alpha), regions=length(region_values),
    local_lr=length(requested_local), local_centers=local_center_count, stringsAsFactors=FALSE)
}

add_edges <- function(blocks, id, label) {
  rows <- if (length(blocks)) do.call(rbind, blocks) else empty_edges()
  c$add(id, "lr_edges", rows,
    paste0("SpaCCI 1.0.3 ", label, " NNLS–几何均值–饱和转换强度；原始P、重算BH与上游被覆盖的adjusted.PValue并列保留。"),
    direction="higher", additive=FALSE, value_kind="nonnegative_strength",
    axis_label="SpaCCI native strength", statistical_unit="spots pooled within sample/region",
    test_definition=paste0(label, " native spatial/cell-type permutation; not a donor-level condition test"),
    directed=TRUE, display_top_rows=30L, display_top_columns=20L)
  rows
}
global_all <- add_edges(edge_blocks$global, "spacci_global_lr", "global")
regional_all <- if (run_regional) add_edges(edge_blocks$regional, "spacci_regional_lr", "regional") else NULL
local_all <- if (run_local) {
  rows <- if (length(edge_blocks$local)) do.call(rbind, edge_blocks$local) else empty_edges()
  c$add("spacci_local_lr", "lr_edges", rows,
    "SpaCCI local网络摘要；score为通过声明support_metric的局部中心数，tested_centers、support_fraction与maximum_native_strength并列保留。完整中心级P/q在local_center_results表中。",
    direction="higher", additive=FALSE, value_kind="count",
    axis_label="BH-supported local centers", statistical_unit="spatial centers pooled within sample",
    test_definition="Network summary of center-level native local permutations; no additional summary-level P value and no donor-level condition test",
    directed=TRUE, display_top_rows=30L, display_top_columns=20L)
  rows
} else NULL
add_count_matrix <- function(rows, id, scale) {
  if (is.null(rows) || !nrow(rows)) return(NULL)
  contexts <- if (scale == "regional") unique(rows[,c("sample","region"),drop=FALSE]) else
    unique(data.frame(sample=rows$sample, region="whole_slide", stringsAsFactors=FALSE))
  matrix_rows <- do.call(rbind, lapply(seq_len(nrow(contexts)), function(i) {
    sample <- contexts$sample[[i]]; region <- contexts$region[[i]]
    types <- cell_types_by_sample[[sample]]
    selected <- rows[rows$sample==sample & (scale!="regional" | rows$region==region),,drop=FALSE]
    grid <- expand.grid(source=types,target=types,stringsAsFactors=FALSE)
    supported <- selected[selected$supported,,drop=FALSE]
    counts <- if (nrow(supported)) aggregate(score ~ source + target, supported,
      FUN=function(v) if (scale=="local") sum(v) else length(v)) else
      data.frame(source=character(),target=character(),score=numeric())
    grid <- merge(grid,counts,by=c("source","target"),all.x=TRUE,sort=FALSE)
    grid$score[is.na(grid$score)] <- 0
    prefix <- if (scale=="regional") paste(sample,region,sep=" | ") else sample
    data.frame(row=paste(prefix,grid$source,sep=" | "),column=grid$target,value=grid$score,
      stringsAsFactors=FALSE)
  }))
  c$add(id,"matrix",matrix_rows,
    paste0("SpaCCI ",scale," 声明support_metric的有向细胞对计数热图；行为发送细胞类型，列为接收细胞类型，零值是完整组合中的真实无支持。"),
    direction="higher",additive=FALSE,value_kind="count",axis_label="Supported candidates",
    title=paste("SpaCCI",scale,"supported interaction count"),
    row_order=unique(matrix_rows$row),column_order=unique(matrix_rows$column))
}
add_count_matrix(global_all,"spacci_global_supported_count","global")
if (run_regional) add_count_matrix(regional_all,"spacci_regional_supported_count","regional")
if (run_local) add_count_matrix(local_all,"spacci_local_supported_count","local")
for (item in spatial_tables) c$add(item$id, "spatial_points", item$rows, item$definition,
  direction="higher", additive=FALSE, value_kind="nonnegative_strength", axis_label=item$axis,
  title=item$title, coordinate_unit=cfg$coordinate_unit,
  coordinate_provenance=cfg$coordinate_provenance,
  physical_scale_unavailable=isTRUE(cfg$physical_scale_unavailable), y_down=isTRUE(cfg$y_down))
c$wt(do.call(rbind, diagnostics), "sample_diagnostics.tsv")
c$bundle$provenance$native_objects <- c$objects
c$bundle$provenance$local_center_result_tables <- local_detail_artifacts
c$bundle$provenance$limitations <- c(
  "SpaCCI 1.0.3在三个尺度均先计算BH，随后用原始P覆盖adjusted.PValue；适配器不更改原生对象，另行重算并标注校正作用域。",
  "SpaCCI C++从package:nnls查找函数，上游NAMESPACE不保证附加该包；适配器显式附加nnls 1.6。",
  "global与regional的15近邻比例矩阵只用于排除不可能细胞对，报告的strength未乘该邻近量，不是通讯通量。",
  "local的单位距离每个中心由随机5个位置的最近邻均值估计；固定seed可重现邻域，但radius=2.5只能在特定Visium标定有依据时解释为约200–250 μm。",
  "regional置换从区域外抽取同等数量位置，因此区域不得超过样本一半；它检验的是该区域相对空间背景，不是患者间差异。",
  "local位置、15近邻边和置换中心共享同一张切片，不是独立生物学重复；跨数据集特异性必须由多供体统计单元的后续对比验证。",
  "所有通用热图、气泡图、网络图、弦图和局部空间图都从同一完整结果包直接生成；展示排序不改写原生分数或统计支持。")
c$wj(c$bundle, "bundle.json")
capture.output(sessionInfo(), file = file.path(c$out, "sessionInfo.txt"))
