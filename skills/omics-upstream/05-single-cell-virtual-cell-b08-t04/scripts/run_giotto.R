#!/usr/bin/env Rscript
options(stringsAsFactors = FALSE, warn = 1)
args <- commandArgs(TRUE)
file_arg <- sub("^--file=", "", commandArgs()[grepl("^--file=", commandArgs())][1])
script_dir <- dirname(normalizePath(file_arg))
source(file.path(script_dir, "native_expression_context.R"))
c <- native_expression_context(args, "Giotto", "Giotto", "1.1.0",
                               counts_input = TRUE, species = c("human", "mouse"))
cfg <- c$cfg
for (key in c("native_root", "database", "database_version", "database_provenance",
              "input_provenance", "coordinate_provenance", "coordinate_unit")) {
  if (is.null(cfg[[key]])) stop("缺少：", key)
}
if (!cfg$coordinate_unit %in% c("um", "pixel", "native")) stop("coordinate_unit必须为um、pixel或native")
if (cfg$coordinate_unit == "native" && !isTRUE(cfg$physical_scale_unavailable)) {
  stop("原生坐标单位必须明确physical_scale_unavailable=true")
}
if (!requireNamespace("data.table", quietly = TRUE)) stop("缺少原生依赖：data.table")
suppressPackageStartupMessages({library(Matrix); library(Giotto)})

root <- c$resolve(cfg$native_root)
database_path <- c$resolve(cfg$database)
expected <- c(
  "DESCRIPTION" = "4d32960be418daf6ea48fa325d4750478f006387ab0678d62e73abf3e3492ba0",
  "LICENSE" = "961e302d6b3d698e5dda9d2c2deecea60f13f93e74eef09224c26322a4971cff",
  "R/spatial_interaction.R" = "4b900a5485e52fb75b5154fb281dc0824ac7b8d730bad1463519269e1ba01091",
  "R/spatial_interaction_visuals.R" = "bc16a7f7406fb3b6c3cfae6647564e7c8d5d368267b2f3f9b3d0ecc213e68fbe"
)
for (path in names(expected)) if (c$hash(file.path(root, path)) != expected[[path]]) stop("Giotto源码摘要不符：", path)
if (c$hash(database_path) != "0f041a73a43b0857d5c8251edef8c605c109c9fa01e5a8b891f2b05b43131486") {
  stop("Giotto作者LR资源摘要不符")
}
body_expected <- c(
  createGiottoObject = "82df96bc31a69620a3eb842ff3da50761afea2f02c345b5031658b7626f6427b",
  normalizeGiotto = "6781064c4664eda20c90d7cafab97734701e9800b0f7e9aa18f968e5c9e3afda",
  addCellMetadata = "9164dbee2478faaaa7bd800933ec4b1562da868bc9ea0426d00884f4a9fb5200",
  createSpatialNetwork = "d615c99449ff8cc45dbb9844b08265883468fb68547df4805e03b9aac5b1411f",
  average_gene_gene_expression_in_groups = "a4e7e4b02d61b1f63cc373a8e49880e5eb19172726c3886837a9416462b48b4f",
  exprCellCellcom = "6290899adceb38a94f957c18ce552c84aeed3c37230a813a797065ed5c41b00a",
  create_cell_type_random_cell_IDs = "23b384eee9e3a8db3d8df589966fb3b9d1835fc0f6c9fc6fac5ccc5308148673",
  specificCellCellcommunicationScores = "27a8f9e2c6bd771600611eae8477b280d5011adb928197c0d29b987929bf17a6",
  spatCellCellcom = "18f312db8ea3a89f57a0ac8b200cb8af77cf5ee772e138a8661456d948060609",
  combCCcom = "1dfc61bfbbe9808fdb38d1eae326fa90d911b00444c57f5fb259dd98645cc73a"
)
for (fn in names(body_expected)) {
  actual <- digest::digest(body(get(fn, envir = asNamespace("Giotto"))), algo = "sha256")
  if (actual != body_expected[[fn]]) stop("已安装Giotto函数体摘要不符：", fn)
}

x <- readRDS(c$input)
coordinates <- x$coordinates
if (is.null(coordinates) || is.null(rownames(coordinates)) || anyDuplicated(rownames(coordinates)) ||
    !setequal(rownames(coordinates), colnames(c$expr)) || !ncol(coordinates) %in% c(2L, 3L)) {
  stop("需要与counts细胞唯一对齐的二维或三维coordinates")
}
coordinates <- as.data.frame(coordinates[colnames(c$expr), , drop = FALSE], check.names = FALSE)
if (any(!is.finite(as.matrix(coordinates)))) stop("空间坐标必须有限")
if (any(grepl("cluster_", c$meta$cell_type, fixed = TRUE))) {
  stop("Giotto 1.1.0会全局删除cell_type中的cluster_字符串；为防止身份损坏，需先提供不含该字面量的标签")
}

lr <- data.table::fread(database_path)
ligand_column <- cfg$ligand_column %||% if (cfg$species == "mouse") "mouseLigand" else "humanLigand"
receptor_column <- cfg$receptor_column %||% if (cfg$species == "mouse") "mouseReceptor" else "humanReceptor"
if (!all(c(ligand_column, receptor_column) %in% names(lr))) stop("LR资源缺少配置的物种列")
lr <- unique(lr[, .(ligand = get(ligand_column), receptor = get(receptor_column))])
if (!nrow(lr) || anyNA(lr) || anyDuplicated(paste(lr$ligand, lr$receptor, sep = "\r"))) stop("LR资源为空、缺失或身份重复")

params <- list(
  commit = "eaccf736f431bdf80633bd05feb975c5b276b7df", random_iter = as.integer(cfg$random_iter %||% 1000L),
  seed = as.integer(cfg$seed %||% 1234L), scale_factor = as.numeric(cfg$scale_factor %||% 6000),
  log2fc_addendum = as.numeric(cfg$log2fc_addendum %||% 0.1), min_observations = as.integer(cfg$min_observations %||% 2L),
  adjust_method = cfg$adjust_method %||% "fdr", adjust_target = cfg$adjust_target %||% "genes",
  minimum_k = as.integer(cfg$minimum_k %||% 2L), maximum_distance_delaunay = cfg$maximum_distance_delaunay %||% "auto",
  database_version = cfg$database_version
)
if (is.na(params$random_iter) || params$random_iter < 100L || is.na(params$seed) ||
    !is.finite(params$scale_factor) || params$scale_factor <= 0 ||
    !is.finite(params$log2fc_addendum) || params$log2fc_addendum <= 0 ||
    is.na(params$min_observations) || params$min_observations < 0L ||
    is.na(params$minimum_k) || params$minimum_k < 0L) stop("Giotto科学参数无效；random_iter至少100")
if (!params$adjust_method %in% c("fdr", "bonferroni", "BH", "holm", "hochberg", "hommel", "BY", "none") ||
    !params$adjust_target %in% c("genes", "cells")) stop("多重校正配置无效")
if (!identical(params$maximum_distance_delaunay, "auto")) {
  params$maximum_distance_delaunay <- as.numeric(params$maximum_distance_delaunay)
  if (!is.finite(params$maximum_distance_delaunay) || params$maximum_distance_delaunay <= 0) stop("maximum_distance_delaunay无效")
}
c$start_cache(c(unname(expected), c$hash(database_path)), params)
c$bundle$implementation <- "native_Giotto_expression_and_spatial_communication"
c$bundle$provenance$upstream <- list(url = "https://github.com/RubD/Giotto", tag = "v1.1.0",
                                     commit = params$commit, license = "MIT")
c$bundle$provenance$database <- list(path = basename(database_path), sha256 = c$hash(database_path),
                                     version = cfg$database_version, provenance = cfg$database_provenance,
                                     ligand_column = ligand_column, receptor_column = receptor_column)
c$bundle$provenance$coordinate_provenance <- cfg$coordinate_provenance
c$bundle$provenance$coordinate_unit <- cfg$coordinate_unit
c$bundle$provenance$semantics <- paste(
  "expression分支置换全部细胞的群标签；spatial分支先取Delaunay相邻细胞，再在相同群组成内从全样本抽细胞。",
  "两者的LR_expr都是发送群配体平均归一化表达与接收群受体平均归一化表达之和。",
  "原生pvalue是观测减随机的正负号累计比例经方向变换所得；adjust_target决定在细胞对或LR内校正。"
)

expression_rows <- list(); spatial_rows <- list(); comparison_rows <- list()
point_rows <- list(); edge_rows <- list(); diagnostics <- list()
samples <- unique(c$meta$sample)
for (si in seq_along(samples)) {
  sample <- samples[[si]]
  metadata <- c$sample_meta(sample)
  ids <- rownames(metadata)
  if (any(table(metadata$cell_type) < 2L)) stop("样本", sample, "存在少于2个细胞的合格群")
  sample_lr <- lr[ligand %in% rownames(c$expr) & receptor %in% rownames(c$expr)]
  if (!nrow(sample_lr)) stop("样本", sample, "没有同时测得的作者LR")
  native <- c$native(si, sample, function() {
    coords <- coordinates[ids, , drop = FALSE]
    object <- Giotto::createGiottoObject(raw_exprs = c$expr[, ids, drop = FALSE], spatial_locs = coords)
    object <- Giotto::normalizeGiotto(object, scalefactor = params$scale_factor, verbose = FALSE)
    md <- data.frame(cell_ID = ids, cell_types = metadata$cell_type, check.names = FALSE)
    object <- Giotto::addCellMetadata(object, new_metadata = md, by_column = TRUE, column_cell_ID = "cell_ID")
    object <- Giotto::createSpatialNetwork(object, method = "Delaunay", delaunay_method = "deldir",
      minimum_k = params$minimum_k, maximum_distance_delaunay = params$maximum_distance_delaunay,
      name = "Delaunay_network", verbose = FALSE)
    expression <- Giotto::exprCellCellcom(object, cluster_column = "cell_types",
      random_iter = params$random_iter, gene_set_1 = sample_lr$ligand, gene_set_2 = sample_lr$receptor,
      log2FC_addendum = params$log2fc_addendum, detailed = TRUE,
      adjust_method = params$adjust_method, adjust_target = params$adjust_target,
      set_seed = TRUE, seed_number = params$seed, verbose = FALSE)
    spatial <- Giotto::spatCellCellcom(object, spatial_network_name = "Delaunay_network",
      cluster_column = "cell_types", random_iter = params$random_iter,
      gene_set_1 = sample_lr$ligand, gene_set_2 = sample_lr$receptor,
      log2FC_addendum = params$log2fc_addendum, min_observations = params$min_observations,
      detailed = TRUE, adjust_method = params$adjust_method, adjust_target = params$adjust_target,
      do_parallel = FALSE, set_seed = TRUE, seed_number = params$seed, verbose = "none")
    combined <- if (nrow(spatial)) Giotto::combCCcom(spatial, expression, min_lig_nr = 0,
      min_rec_nr = 0, min_padj_value = 1, min_log2fc = 0, min_av_diff = 0, detailed = TRUE) else NULL
    list(object = object, expression = expression, spatial = spatial, combined = combined,
         network = object@spatial_network[["Delaunay_network"]]$networkDT)
  })
  for (name in c("expression", "spatial")) {
    z <- native[[name]]
    if (!nrow(z)) next
    if (any(!is.finite(z$LR_expr)) || any(!is.finite(z$log2fc)) || any(!is.finite(z$pvalue)) ||
        any(!is.finite(z$p.adj)) || any(!is.finite(z$PI))) {
      stop("Giotto ", name, "结果含无穷或缺失；常见原因是该置换分支全部调整P为0，不能静默替换原生PI")
    }
    out <- data.frame(sample = sample, donor = metadata$donor[1], condition = metadata$condition[1],
      source = as.character(z$lig_cell_type), target = as.character(z$rec_cell_type),
      ligand = z$ligand, receptor = z$receptor, interaction = z$LR_comb,
      score = z$PI, tested = TRUE, supported = z$p.adj <= as.numeric(cfg$alpha %||% 0.05) & z$log2fc > 0,
      ligand_mean = z$lig_expr, receptor_mean = z$rec_expr, lr_expression_sum = z$LR_expr,
      random_mean = z$rand_expr, mean_difference = z$av_diff, difference_sd = z$sd_diff,
      z_score = z$z_score, log2fc = z$log2fc, p_value = z$pvalue, q_value = z$p.adj,
      ligand_cells = z$lig_nr, receptor_cells = z$rec_nr, stringsAsFactors = FALSE)
    if (name == "expression") expression_rows[[sample]] <- out else spatial_rows[[sample]] <- out
  }
  if (!is.null(native$combined) && nrow(native$combined)) {
    z <- native$combined
    comparison_rows[[sample]] <- do.call(rbind, lapply(seq_len(nrow(z)), function(i) rbind(
      data.frame(row = paste(sample, z$LR_comb[i], z$LR_cell_comb[i], sep = " | "), column = "expression_PI_rank", value = z$exprPI_rnk[i]),
      data.frame(row = paste(sample, z$LR_comb[i], z$LR_cell_comb[i], sep = " | "), column = "spatial_PI_rank", value = z$spatPI_rnk[i])
    )))
  }
  coords <- coordinates[ids, , drop = FALSE]
  group_codes <- setNames(seq_along(sort(unique(metadata$cell_type))), sort(unique(metadata$cell_type)))
  point_rows[[sample]] <- data.frame(sample = sample, cell = ids, x = coords[[1]], y = coords[[2]],
    value = unname(group_codes[metadata$cell_type]), label = metadata$cell_type)
  network <- native$network
  edge_rows[[sample]] <- data.frame(sample = sample, source_cell = network$from,
    target_cell = network$to, value = 1)
  diagnostics[[sample]] <- data.frame(sample = sample, cells = length(ids), cell_types = length(unique(metadata$cell_type)),
    measured_lr = nrow(sample_lr), delaunay_edges = nrow(network), expression_rows = nrow(native$expression),
    spatial_rows = nrow(native$spatial), permutations_per_branch = params$random_iter)
}

if (length(expression_rows)) c$add("giotto_expression_lr_scores", "lr_edges", do.call(rbind, expression_rows),
  "Giotto原生exprCellCellcom：配体与受体群均值之和相对全细胞群标签置换；score为原生PI=log2fc×−log10(adjusted p)，可为负",
  direction = "higher", additive = FALSE, value_kind = "signed_composite_statistic",
  axis_label = "Giotto expression PI", statistical_unit = "cells pooled within each sample",
  test_definition = "algorithm-defined directional sign proportion across label permutations; not a donor-level test")
if (length(spatial_rows)) c$add("giotto_spatial_lr_scores", "lr_edges", do.call(rbind, spatial_rows),
  "Giotto原生spatCellCellcom：Delaunay相邻细胞子集中的配体与受体群均值之和，相对保持群组成的全样本细胞抽样；score为原生PI，可为负",
  direction = "higher", additive = FALSE, value_kind = "signed_composite_statistic",
  axis_label = "Giotto spatial PI", statistical_unit = "spatially adjacent cells pooled within each sample",
  test_definition = "algorithm-defined directional sign proportion across within-cell-type cell resamples; not a donor-level test")
if (length(comparison_rows)) c$add("giotto_spatial_expression_rank_comparison", "matrix", do.call(rbind, comparison_rows),
  "原生combCCcom在每个LR内部对细胞对的expression PI与spatial PI分别降序排名；同一行的两列是一项实测候选的配对秩",
  direction = "lower", additive = FALSE, value_kind = "rank", axis_label = "Within-LR rank",
  figure_role = "rank_comparison")
c$add("giotto_spatial_cell_types", "spatial_points", do.call(rbind, point_rows),
  "输入空间坐标上的实际细胞类型；value只是为文件兼容保留的确定性类别编码，绘图按label分类着色，不解释编码大小",
  direction = "none", additive = FALSE, value_kind = "category_code", axis_label = "Cell type",
  coordinate_unit = cfg$coordinate_unit, coordinate_provenance = cfg$coordinate_provenance,
  physical_scale_unavailable = isTRUE(cfg$physical_scale_unavailable))
c$add("giotto_delaunay_neighborhood", "spatial_edges", do.call(rbind, edge_rows),
  "Giotto createSpatialNetwork产生的无向Delaunay邻域；value=1表示邻接存在，不是通讯强度",
  direction = "none", additive = FALSE, value_kind = "count", axis_label = "Delaunay adjacency",
  directed = FALSE, coordinate_unit = cfg$coordinate_unit, coordinate_provenance = cfg$coordinate_provenance,
  physical_scale_unavailable = isTRUE(cfg$physical_scale_unavailable))
c$wt(do.call(rbind, diagnostics), "sample_diagnostics.tsv")
c$bundle$provenance$native_objects <- c$objects
c$bundle$provenance$limitations <- c(
  "Giotto 1.1.0把cluster_从平均表达列名中全局删除；入口拒绝含该字面量的细胞类型，避免身份静默损坏。",
  "同型与异型邻域按无序细胞类型组合执行，但LR方向保留为ligand cell type到receptor cell type。",
  "原生置换最小P分辨率受random_iter限制；PI同时混合效应方向和调整P，不能跨数据集当作绝对通讯通量。",
  "Giotto直接按浮点差值的正负计数，不设置数值容差；名义相等的值可能以约1e-16正残差计为正向置换。真实seqFISH验收中，1e-12并列容差会改变93/1075行的原生P，最大变化0.44；原生值照实交付，但不可仅凭其P/q宣称空间特异通讯。",
  "spatial分支在每个细胞类型对重新执行抽样；细胞和空间边不是独立生物学重复。",
  "配套绘图以完整原生表为来源；分类空间图、Delaunay图、LR证据图和表达–空间秩比较不新增显著性。"
)
c$wj(c$bundle, "bundle.json")
capture.output(sessionInfo(), file = file.path(c$out, "sessionInfo.txt"))
