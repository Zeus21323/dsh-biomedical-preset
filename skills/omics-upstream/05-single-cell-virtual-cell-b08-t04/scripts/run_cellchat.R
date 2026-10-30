#!/usr/bin/env Rscript
# Project-owned adapter; calls CellChat APIs without vendoring upstream code.
options(stringsAsFactors = FALSE, warn = 1)
`%||%` <- function(x, y) if (is.null(x)) y else x
abort <- function(...) stop(..., call. = FALSE)
args <- commandArgs(TRUE)
if (length(args) != 2L) abort("用法: Rscript run_cellchat.R 配置.json 新输出目录")
required <- c("CellChat", "jsonlite", "digest", "svglite", "ragg", "ComplexHeatmap", "circlize", "ggplot2")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) abort("缺少 R 包: ", paste(missing, collapse = ", "))
if (packageVersion("ggplot2") < "3.5.0") abort("需要 ggplot2 >= 3.5.0，以导出可编辑矢量色条")
suppressPackageStartupMessages(library(CellChat))
cfg_path <- normalizePath(args[1], mustWork = TRUE)
cfg <- jsonlite::read_json(cfg_path, simplifyVector = TRUE)
for (k in c("dataset", "sample", "donor", "condition", "species", "mode", "research_question"))
  if (is.null(cfg[[k]]) || length(cfg[[k]]) != 1L || !nzchar(cfg[[k]])) abort("配置缺少单值字段: ", k)
if (!cfg$species %in% c("human", "mouse")) abort("species 仅支持 human/mouse")
if (!cfg$mode %in% c("infer", "reuse")) abort("mode 必须为 infer 或 reuse")
version <- as.character(packageVersion("CellChat"))
if (version != (cfg$expected_cellchat_version %||% "2.2.0.9001")) abort("CellChat 版本不匹配: ", version)
resolve <- function(p) {
  if (is.null(p)) abort("缺少输入路径")
  normalizePath(if (grepl("^(/|[A-Za-z]:)", p)) p else file.path(dirname(cfg_path), p), mustWork = TRUE)
}
input <- resolve(if (cfg$mode == "reuse") cfg$object else cfg$input)
if (isTRUE(cfg$inspect_only)) {
  x <- readRDS(input)
  labels <- if (cfg$mode == "reuse") levels(x@idents) else unique(as.character(x$metadata$cell_type))
  if (is.null(labels) || !length(labels) || anyNA(labels)) abort("无法发现细胞标签")
  cat(jsonlite::toJSON(labels, auto_unbox = FALSE)); quit(status = 0L)
}
if (file.exists(args[2])) abort("输出目录已存在；请使用新目录，避免覆盖: ", args[2])
out <- path.expand(args[2]); dir.create(out, recursive = TRUE)
out <- normalizePath(out)
write_json <- function(x, name) jsonlite::write_json(x, file.path(out, name), auto_unbox = TRUE, pretty = TRUE, na = "null", null = "null")
write_table <- function(x, name) write.table(x, file.path(out, name), sep = "\t", quote = FALSE, row.names = FALSE, na = "NA")
manifest <- list(schema_version = 1, status = "running", method = "CellChat", figures = list(), visual_review = "pending")
write_json(manifest, "figure_manifest.json")
tryCatch({
  file.copy(cfg_path, file.path(out, "run_config.json"))
  seed <- cfg$seed %||% 1L
  min_cells <- cfg$min_cells %||% 10L
  alpha <- cfg$alpha %||% 0.05
  if (min_cells < 2 || alpha <= 0 || alpha > 1) abort("min_cells/alpha 无效")
  set.seed(seed)
  future::plan("sequential")
  steps <- character()
  if (cfg$mode == "infer") {
    x <- readRDS(input)
    if (!is.list(x) || is.null(x$expression) || is.null(x$metadata)) abort("input RDS 须含 expression 与 metadata")
    expr <- x$expression; meta <- x$metadata
    if (is.null(rownames(expr)) || is.null(colnames(expr)) || anyDuplicated(rownames(expr)) || anyDuplicated(colnames(expr))) abort("表达矩阵须有唯一基因/细胞名")
    if (anyDuplicated(rownames(meta)) || !setequal(colnames(expr), rownames(meta))) abort("metadata 行名必须与表达细胞一一对应")
    meta <- meta[colnames(expr), , drop = FALSE]
    if (!all(c("cell_type", "sample", "donor", "condition") %in% names(meta))) abort("metadata 缺 cell_type/sample/donor/condition")
    if (anyNA(meta[, c("cell_type", "sample", "donor", "condition")]) || any(!nzchar(as.character(meta$cell_type)))) abort("metadata 不能有缺失标签")
    for (k in c("sample", "donor", "condition")) if (!identical(unique(as.character(meta[[k]])), cfg[[k]])) abort("每次仅分析一个样本，metadata 与配置不符: ", k)
    meta$samples <- factor(meta$sample)
    values <- if (inherits(expr, "sparseMatrix")) expr@x else as.vector(expr)
    if (any(!is.finite(values)) || any(values < 0)) abort("表达值须有限且非负")
    if (!identical(cfg$expression_layer, "log_normalized")) abort("需明确 expression_layer=log_normalized；不自动猜测或重新归一化")
    sizes <- table(meta$cell_type)
    write_table(data.frame(cell_type = names(sizes), n_cells = as.integer(sizes), eligible = sizes >= min_cells), "cell_qc.tsv")
    keep <- meta$cell_type %in% names(sizes)[sizes >= min_cells]
    if (length(unique(meta$cell_type[keep])) < 2) abort("低细胞数过滤后不足两个细胞群")
    cc <- createCellChat(expr[, keep, drop = FALSE], meta = droplevels(meta[keep, , drop = FALSE]), group.by = "cell_type")
    db <- if (cfg$species == "human") CellChatDB.human else CellChatDB.mouse
    categories <- cfg$database_categories %||% c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact")
    if (!all(categories %in% unique(db$interaction$annotation))) abort("数据库类别不存在")
    db$interaction <- db$interaction[db$interaction$annotation %in% categories, , drop = FALSE]
    cc@DB <- db
    cc <- subsetData(cc)
    cc <- identifyOverExpressedGenes(cc, do.fast = FALSE, thresh.pc = cfg$expression_fraction %||% 0, thresh.fc = cfg$overexpression_logfc %||% 0, thresh.p = cfg$overexpression_p %||% 0.05)
    cc <- identifyOverExpressedInteractions(cc)
    if (!nrow(cc@LR$LRsig)) abort("没有可推断的 LR 候选；保留 cell_qc.tsv，不降低阈值凑结果")
    cc <- computeCommunProb(cc, type = cfg$average_method %||% "triMean", trim = cfg$trim %||% 0.1,
                           nboot = cfg$nboot %||% 100L, seed.use = seed, population.size = cfg$population_size %||% FALSE)
    steps <- c(steps, "infer_from_log_normalized_expression")
  } else {
    cc <- readRDS(input)
    if (!inherits(cc, "CellChat")) abort("object 不是 CellChat 对象")
    compatible <- tryCatch({ cc@data.smooth; TRUE }, error = function(e) FALSE)
    if (!compatible) {
      cc <- updateCellChat(cc)
      steps <- c(steps, "native_updateCellChat_on_copy_for_legacy_slots")
    }
    if (is.list(cc@idents)) abort("请将 merged 对象按样本拆开；不能把条件池化对象当供体重复")
    if (length(dim(cc@net$prob)) != 3L || is.null(cc@net$pval)) abort("对象无完整 prob/pval 张量，不能直接补图")
    if (!is.character(cfg$source_provenance) || !nzchar(cfg$source_provenance)) abort("reuse 需说明对象来源和历史分析参数已知程度: source_provenance")
    sizes <- table(cc@idents)
    write_table(data.frame(cell_type = names(sizes), n_cells = as.integer(sizes), eligible = sizes >= min_cells), "cell_qc.tsv")
    steps <- c(steps, "reuse_probabilities_without_expression_recomputation")
  }
  raw_prob <- cc@net$prob; raw_pval <- cc@net$pval
  if (!identical(dimnames(raw_prob), dimnames(raw_pval)) || any(!is.finite(raw_prob)) || any(raw_prob < 0) || any(!is.finite(raw_pval))) abort("prob/pval 张量无效")
  cc <- filterCommunication(cc, min.cells = min_cells)
  cc <- computeCommunProbPathway(cc, thresh = alpha)
  cc <- aggregateNet(cc, thresh = alpha)
  steps <- c(steps, "derive_filtered_networks_from_existing_probabilities")
  groups <- levels(cc@idents)
  sizes <- table(cc@idents)[groups]
  colors <- setNames(grDevices::hcl.colors(length(groups), "Dark 3"), groups)
  if (!is.null(cfg$colors)) {
    if (!all(groups %in% names(cfg$colors))) abort("colors 必须覆盖全部细胞标签")
    colors <- unlist(cfg$colors[groups])
  }
  idx <- expand.grid(source = dimnames(raw_prob)[[1]], target = dimnames(raw_prob)[[2]], interaction = dimnames(raw_prob)[[3]], stringsAsFactors = FALSE)
  annotations <- cc@DB$interaction[match(idx$interaction, cc@DB$interaction$interaction_name), , drop = FALSE]
  if (anyNA(annotations$interaction_name)) abort("LR 张量与数据库注释不匹配")
  candidates <- data.frame(sample = cfg$sample, donor = cfg$donor, condition = cfg$condition, idx,
                           ligand = annotations$ligand, receptor = annotations$receptor, pathway = annotations$pathway_name,
                           score = as.vector(raw_prob), p_value = as.vector(raw_pval),
                           tested = as.integer(sizes[idx$source]) >= min_cells & as.integer(sizes[idx$target]) >= min_cells)
  candidates$supported <- candidates$tested & candidates$score > 0 & candidates$p_value < alpha
  write_table(candidates, "candidates.tsv")
  edges <- candidates[candidates$supported, , drop = FALSE]
  write_table(edges, "edges.tsv")
  pairs <- unique(candidates[candidates$tested, c("sample", "donor", "source", "target")])
  write_table(pairs, "tested_pairs.tsv")
  for (measure in c("count", "weight")) {
    m <- cc@net[[measure]]
    write_table(data.frame(source = rep(rownames(m), times = ncol(m)), target = rep(colnames(m), each = nrow(m)), value = as.vector(m)), paste0("network_", measure, ".tsv"))
  }
  if (nrow(edges)) {
    ranking <- aggregate(score ~ source + target + interaction + ligand + receptor + pathway, edges, sum)
    total <- tapply(ranking$score, ranking$interaction, sum)
    ranking$cell_pair_share <- ranking$score / total[ranking$interaction]
    ranking <- ranking[order(-ranking$cell_pair_share, -ranking$score, ranking$interaction, ranking$source, ranking$target), ]
    ranking$selection_reason <- "探索性细胞对分数占比，其次为原生强度；不代表疾病特异性"
  } else ranking <- data.frame()
  requested_sources <- cfg$focus_sources %||% names(sort(rowSums(cc@net$weight), decreasing = TRUE))[1]
  requested_targets <- cfg$focus_targets %||% groups
  unavailable_focus <- setdiff(c(requested_sources, requested_targets), groups)
  sources <- intersect(requested_sources, groups)
  targets <- intersect(requested_targets, groups)
  focused <- edges[edges$source %in% sources & edges$target %in% targets, , drop = FALSE]
  pathway_ranking <- if (nrow(focused)) aggregate(score ~ pathway, focused, sum) else data.frame(pathway = character(), score = numeric())
  pathway_ranking <- pathway_ranking[order(-pathway_ranking$score, pathway_ranking$pathway), ]
  requested_pathways <- cfg$pathways %||% head(pathway_ranking$pathway, cfg$top_pathways %||% 3L)
  unavailable_pathways <- setdiff(requested_pathways, unique(focused$pathway))
  pathways <- intersect(requested_pathways, unique(focused$pathway))
  selected <- if (nrow(ranking)) unique(ranking$interaction[ranking$source %in% sources & ranking$target %in% targets]) else character()
  selected <- head(selected, cfg$top_lr %||% 20L)
  ranking$selected <- if (nrow(ranking)) ranking$interaction %in% selected & ranking$source %in% sources & ranking$target %in% targets else logical()
  write_table(ranking, "candidate_ranking.tsv"); write_table(pathway_ranking, "pathway_ranking.tsv")
  write_json(list(sources = sources, targets = targets, pathways = pathways, interactions = selected,
                  requested_sources = requested_sources, requested_targets = requested_targets,
                  unavailable_focus = unavailable_focus, unavailable_pathways = unavailable_pathways,
                  focus_reason = if (is.null(cfg$focus_sources)) "探索性起点：原生总发送强度最高；需结合研究问题复核" else "用户/研究设计指定",
                  research_question = cfg$research_question, colors = as.list(colors)), "selection.json")
  # Export the post-filter object even when plotting later fails.
  if (nrow(edges)) cc <- netAnalysis_computeCentrality(cc, slot.name = "netP", thresh = alpha)
  saveRDS(cc, file.path(out, "cellchat.rds"))
  capture.output(sessionInfo(), file = file.path(out, "sessionInfo.txt"))
  provenance <- list(config = cfg, method = "CellChat", method_version = version, input_sha256 = digest::digest(file = input, algo = "sha256"),
                     database_sha256 = digest::digest(cc@DB, algo = "sha256"), steps = steps,
                     parameters = list(min_cells = min_cells, alpha = alpha, seed = seed, inference_options = cc@options),
                     comparison_signature = cfg$comparison_signature %||% NULL,
                     statistical_unit = cfg$analysis_unit %||% "pooled", p_value_meaning = "CellChat cell-group permutation; not condition-difference P")
  provenance$comparison_parameters <- if (cfg$mode == "infer") list(species = cfg$species, expression_layer = cfg$expression_layer,
    average_method = cfg$average_method %||% "triMean", trim = cfg$trim %||% 0.1, nboot = cfg$nboot %||% 100L,
    population_size = cfg$population_size %||% FALSE, expression_fraction = cfg$expression_fraction %||% 0,
    overexpression_logfc = cfg$overexpression_logfc %||% 0, overexpression_p = cfg$overexpression_p %||% 0.05,
    min_cells = min_cells, alpha = alpha) else cfg$historical_comparison_parameters %||% NULL
  if (!is.null(provenance$comparison_parameters)) {
    provenance$comparison_parameters$post_filter_min_cells <- min_cells
    provenance$comparison_parameters$post_filter_alpha <- alpha
  }
  write_json(provenance, "provenance.json")
  theme <- ggplot2::theme_classic(base_size = 7, base_family = "sans") + ggplot2::theme(
    axis.text = ggplot2::element_text(size = 6), plot.title = ggplot2::element_text(size = 7),
    legend.text = ggplot2::element_text(size = 6), legend.title = ggplot2::element_text(size = 7),
    plot.margin = ggplot2::margin(7, 7, 7, 7),
    panel.grid.major = ggplot2::element_blank(), panel.grid.minor = ggplot2::element_blank())
  export <- function(id, draw, caption, width = 183, height = 150, source = "edges.tsv") {
    entry <- list(id = id, status = "failed", source_data = source, caption = caption, files = list(), visual_review = "pending",
                  width_mm = width, height_mm = height)
    warns <- character()
    tryCatch(withCallingHandlers({
      for (ext in c("pdf", "svg", "png")) {
        set.seed(seed)
        path <- file.path(out, paste0(id, ".", ext))
        if (ext == "pdf") grDevices::pdf(path, width = width/25.4, height = height/25.4, pointsize = 7, useDingbats = FALSE)
        if (ext == "svg") svglite::svglite(path, width = width/25.4, height = height/25.4, pointsize = 7)
        if (ext == "png") ragg::agg_png(path, width = width, height = height, units = "mm", res = 600, pointsize = 7)
        tryCatch({
          graphics::par(mar = c(1, 1, 2, 1), cex = 1, family = "sans", xpd = NA)
          circlize::circos.clear()
          p <- draw()
          if (inherits(p, "ggplot")) {
            # Native river plots are patchworks: apply the theme to every panel.
            p <- if (inherits(p, "patchwork")) p & theme else p + theme
            if (grepl("^lr_bubble", id)) p <- p + ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 6))
            if (grepl("^pattern_river", id)) {
              # CellChat's cowplot composition embeds a fixed 10 pt axis theme.
              # Style the native editable grobs before all three exports.
              style_grob <- function(g) {
                if (inherits(g, "text") && !is.null(g$gp$fontsize)) g$gp$fontsize <- pmin(g$gp$fontsize, 7)
                if (length(g$grobs)) g$grobs <- lapply(g$grobs, style_grob)
                if (length(g$children)) g$children <- do.call(grid::gList, lapply(g$children, style_grob))
                g
              }
              grid::grid.newpage(); grid::grid.draw(style_grob(ggplot2::ggplotGrob(p)))
            } else print(p)
          }
          if (inherits(p, c("Heatmap", "HeatmapList"))) ComplexHeatmap::draw(p)
        }, finally = grDevices::dev.off())
        entry$files <- c(entry$files, basename(path))
      }
      entry$status <- "generated"
    }, warning = function(w) { warns <<- c(warns, conditionMessage(w)); invokeRestart("muffleWarning") }),
    error = function(e) entry$error <<- conditionMessage(e))
    entry$warnings <- unique(warns)
    manifest$figures[[length(manifest$figures) + 1L]] <<- entry
    write_json(manifest, "figure_manifest.json")
  }
  skip <- function(id, reason) {
    manifest$figures[[length(manifest$figures) + 1L]] <<- list(id = id, status = "not_applicable", reason = reason)
  }
  if (length(unavailable_focus)) skip("unavailable_focus", paste("指定细胞群在本样本不存在或未通过细胞数过滤：", paste(unavailable_focus, collapse = ", "), "；不改用其他群冒充"))
  if (length(unavailable_pathways)) skip("unsupported_requested_pathways", paste("指定通路在本样本焦点范围内无支持：", paste(unavailable_pathways, collapse = ", ")))
  if (nrow(edges)) {
    circle <- function(mat, title, max_value = max(mat)) {
      netVisual_circle(mat, color.use = colors[rownames(mat)], title.name = NULL, weight.scale = TRUE, edge.weight.max = max_value,
                       vertex.weight = rep(1, nrow(mat)), vertex.size.max = 5, vertex.label.cex = 0.9,
                       edge.width.max = 4, arrow.size = 0.15, margin = 0.35)
      graphics::title(main = title, cex.main = 1, font.main = 1)
      graphics::mtext(sprintf("Maximum edge = %.3g; equal node sizes", max_value), side = 1, line = -0.2, cex = 0.86)
      invisible(NULL)
    }
    for (measure in c("count", "weight")) {
      local({ key <- measure; mat <- cc@net[[key]]
        export(paste0("network_", key), function() circle(mat, if (key == "count") "Number of supported interactions" else "Inferred interaction strength"),
               paste("CellChat", key, "; 边为发送到接收，节点等大；原生过滤结果，非条件差异检验。"), source = paste0("network_", key, ".tsv"))
        export(paste0("heatmap_", key), function() netVisual_heatmap(cc, measure = key, color.use = colors, color.heatmap = "Blues", font.size = 6, font.size.title = 7),
               paste("CellChat", key, "发送行、接收列；灰色或空白解释见源数据。"), source = paste0("network_", key, ".tsv"))
      })
    }
    for (i in seq_along(sources)) local({
      src <- sources[i]; number <- i; mat <- cc@net$count; mat[!rownames(mat) %in% src, ] <- 0; mat[, !colnames(mat) %in% targets] <- 0
      export(sprintf("focus_sender_%02d", number), function() circle(mat, paste(src, "outgoing interactions"), max(cc@net$count)),
             paste("发送者", src, "；与总体 count 图共享边宽尺度。"), source = "network_count.tsv")
    })
    export("sender_receiver_roles", function() netAnalysis_signalingRole_scatter(cc, color.use = colors, font.size = 7, font.size.title = 7,
                 label.size = 2.1, show.legend = FALSE), "CellChat 原生 netP centrality 角色分析；点大小为交互数量。")
    # Fit native patterns once, then reuse the fit for every export format.
    if (!identical(cfg$patterns, FALSE)) for (direction in c("outgoing", "incoming")) local({
      mode <- direction
      tryCatch({
        if (!requireNamespace("NMF", quietly = TRUE) || !requireNamespace("ggalluvial", quietly = TRUE)) abort("模式图需要 NMF 和 ggalluvial")
        suppressPackageStartupMessages(library(NMF))
        suppressPackageStartupMessages(library(ggalluvial))
        signal <- apply(cc@netP$prob, if (mode == "outgoing") c(1, 3) else c(2, 3), sum)
        max_k <- min(5L, sum(rowSums(signal) > 0) - 1L, ncol(signal) - 1L)
        if (max_k < 2L) {
          skip(paste0("patterns_", mode), "非零细胞群/通路不足，不能稳定识别多个模式")
        } else {
          diagnostic <- selectK(cc, pattern = mode, k.range = seq.int(2L, max_k), nrun = cfg$pattern_nrun %||% 10L, seed.use = seed)
          options(warn = 1)
          write_table(diagnostic$data, paste0("pattern_rank_", mode, ".tsv"))
          scores <- diagnostic$data[diagnostic$data$Measure == "Cophenetic" & is.finite(diagnostic$data$score), ]
          if (!nrow(scores)) abort("模式数诊断没有有限 cophenetic 值")
          k <- cfg$pattern_rank %||% scores$k[order(-scores$score, scores$k)][1]
          if (!k %in% seq.int(2L, max_k)) abort("pattern_rank 超出当前可识别范围")
          fit <- identifyCommunicationPatterns(cc, pattern = mode, k = k, heatmap.show = FALSE)
          options(warn = 1)
          saveRDS(fit, file.path(out, paste0("cellchat_patterns_", mode, ".rds")))
          tables <- fit@netP$pattern[[mode]]$pattern
          write_table(tables$cell, paste0("pattern_cell_", mode, ".tsv"))
          write_table(tables$signaling, paste0("pattern_signaling_", mode, ".tsv"))
          write_json(list(k = k, nrun = cfg$pattern_nrun %||% 10L, seed = seed,
            choice = if (is.null(cfg$pattern_rank)) "探索性：测试范围内最高 cophenetic，平分取较小 k；非唯一真实模式数" else "显式指定并记录诊断"), paste0("pattern_choice_", mode, ".json"))
          export(paste0("pattern_rank_", mode), function() diagnostic, "CellChat 原生模式数诊断；不得以单次选择证明模式稳定性。", source = paste0("pattern_rank_", mode, ".tsv"))
          export(paste0("pattern_river_", mode), function() netAnalysis_river(fit, pattern = mode,
            cutoff = cfg$pattern_display_cutoff %||% 0.5, color.use = colors, font.size = 2.1, font.size.title = 7),
            paste("CellChat 原生", mode, "NMF 模式河流；细胞与通路载荷按原生规则阈值显示，不是流量或条件差异。"), source = paste0("pattern_cell_", mode, ".tsv"))
          export(paste0("pattern_dot_", mode), function() netAnalysis_dot(fit, pattern = mode, font.size = 7, font.size.title = 7),
            "CellChat 原生 NMF 模式点图；完整细胞及信号载荷另附。", source = paste0("pattern_signaling_", mode, ".tsv"))
        }
      }, error = function(e) {
        options(warn = 1)
        manifest$figures[[length(manifest$figures) + 1L]] <<- list(id = paste0("patterns_", mode), status = "failed", error = conditionMessage(e))
      })
    })
    if (length(pathways)) export("pathway_chord_overview", function() {
      graphics::par(fig = c(0, .78, 0, 1), mar = c(1, 1, 1, 1))
      netVisual_chord_gene(cc, slot.name = "netP", signaling = pathways, sources.use = sources, targets.use = targets,
                          color.use = colors, lab.cex = .9, show.legend = FALSE, thresh = alpha)
      active <- unique(c(focused$source[focused$pathway %in% pathways], focused$target[focused$pathway %in% pathways]))
      lgd <- ComplexHeatmap::Legend(at = groups[groups %in% active], type = "grid", legend_gp = grid::gpar(fill = colors[groups %in% active]),
        title = "Cell type", labels_gp = grid::gpar(fontsize = 6), title_gp = grid::gpar(fontsize = 7), grid_height = grid::unit(2.5, "mm"))
      ComplexHeatmap::draw(lgd, x = grid::unit(.98, "npc"), y = grid::unit(.9, "npc"), just = c("right", "top"))
      invisible(NULL)
    }, "焦点细胞与优先通路的原生多层弦图；通路位于发送侧，接收细胞由外环颜色和图例标识；带宽为原生推断强度。")
    for (i in seq_along(pathways)) local({
      path <- pathways[i]; number <- i
      export(sprintf("pathway_circle_%02d", number), function() {
        netVisual_aggregate(cc, signaling = path, layout = "circle", sources.use = sources, targets.use = targets,
                            color.use = colors, vertex.label.cex = 0.9, edge.width.max = 4, pt.title = 7, thresh = alpha)
        invisible(NULL)
      }, paste("通路", path, "；边宽为通路内已支持 LR 推断强度之和。"))
      export(sprintf("pathway_chord_%02d", number), function() {
        netVisual_chord_cell(cc, signaling = path, sources.use = sources, targets.use = targets,
                            color.use = colors, lab.cex = 0.9, show.legend = FALSE, thresh = alpha, title.name = path)
        invisible(NULL)
      }, paste("CellChat 原生通路弦图", path, "；每扇区为细胞群，带宽为推断通路强度。"))
      receivers <- match(intersect(targets, groups), groups)
      if (length(receivers) && length(receivers) < length(groups)) {
        export(sprintf("pathway_hierarchy_%02d", number), function() {
          netVisual_aggregate(cc, signaling = path, layout = "hierarchy", vertex.receiver = receivers,
            sources.use = sources, targets.use = targets, color.use = colors, vertex.label.cex = .85,
            edge.width.max = 3, pt.title = 7, thresh = alpha)
          invisible(NULL)
        }, paste("CellChat 原生 hierarchy：", path, "；接收群由研究焦点指定，自分泌和旁分泌按原生布局。"))
      } else skip(sprintf("pathway_hierarchy_%02d", number), "原生层级图需要真子集接收群；未指定时保留网络/弦图，不任意制造接收分组")
      export(sprintf("lr_contribution_%02d", number), function() netAnalysis_contribution(cc, signaling = path, sources.use = sources,
             targets.use = targets, font.size = 7, font.size.title = 7, thresh = alpha), paste("通路", path, "内 LR 相对贡献；不是显著性或因果贡献。"))
    })
    # Split both axes, retaining exact complex names. No biological threshold is changed for layout.
    if (length(selected)) for (s in seq_along(sources)) for (t in seq_along(split(targets, ceiling(seq_along(targets)/8)))) for (b in seq_along(split(selected, ceiling(seq_along(selected)/12)))) local({
      src <- sources[s]; tg <- split(targets, ceiling(seq_along(targets)/8))[[t]]; lr <- split(selected, ceiling(seq_along(selected)/12))[[b]]
      id <- sprintf("lr_bubble_%02d_%02d_%02d", s, t, b)
      if (!any(focused$source == src & focused$target %in% tg & focused$interaction %in% lr)) skip(id, "该分页无已支持联系") else
        export(id, function() {
          p <- netVisual_bubble(cc, sources.use = src, targets.use = tg, pairLR.use = data.frame(interaction_name = lr),
                    font.size = 7, font.size.title = 7, angle.x = 45, remove.isolate = FALSE, thresh = alpha, color.heatmap = "viridis")
          p$data$prob <- p$data$prob.original
          p + ggplot2::scale_color_viridis_c(limits = c(0, max(focused$score)), name = "Native score", na.value = "transparent") +
              ggplot2::guides(colour = ggplot2::guide_colorbar(display = "rectangles", title = "Native score")) +
              ggplot2::labs(x = "Sender → receiver", y = "Ligand–receptor")
        }, "原生 LR 气泡结构；颜色直接映射原始通讯分数，全部分页共享色标，大小为细胞群置换 P 分类，不是条件差异 P。")
    })
    counts <- data.frame(source = groups, count = rowSums(cc@net$count))
    write_table(counts, "sender_counts.tsv")
    export("lr_counts", function() ggplot2::ggplot(counts, ggplot2::aes(x = reorder(source, count), y = count, fill = source)) +
             ggplot2::geom_col(width = .65) + ggplot2::coord_flip() + ggplot2::scale_fill_manual(values = colors, guide = "none") +
             ggplot2::labs(x = "Sender", y = "Supported LR links across receivers"),
           "每发送者的 source-target-LR 联系数量；同一 LR 到不同接收者分别计数。单对象无供体误差线。", source = "sender_counts.tsv")
    # Compact research-focused panels are drawn at final size, never downscaled from full figures.
    if (nrow(focused)) {
      target_weights <- aggregate(score ~ target, focused, sum)
      main_targets <- head(target_weights$target[order(-target_weights$score, target_weights$target)], 3L)
      main_sources <- head(sources, 2L)
      main_groups <- groups[groups %in% union(main_sources, main_targets)]
      main_edges <- focused[focused$source %in% main_sources & focused$target %in% main_targets, , drop = FALSE]
      main_paths <- head(pathways[pathways %in% main_edges$pathway], 3L)
      write_table(main_edges, "main_figure_edges.tsv")
      write_json(list(sources = main_sources, targets = main_targets, pathways = main_paths,
        rule = "主图仅展示前2个指定发送群及焦点内总分最高的3个接收群；通路保持既定选择，完整图/表另保留；无差异显著性声明"), "main_figure_selection.json")
      main_net <- cc@net$count[main_groups, main_groups, drop = FALSE]
      main_net[!rownames(main_net) %in% main_sources, ] <- 0
      main_net[, !colnames(main_net) %in% main_targets] <- 0
      export("main_network", function() {
        graph <- igraph::graph_from_adjacency_matrix(main_net, mode = "directed", weighted = TRUE, diag = TRUE)
        xy <- igraph::layout_in_circle(graph)
        ends <- igraph::ends(graph, igraph::E(graph), names = TRUE)
        plot(graph, layout = xy, rescale = FALSE, xlim = c(-1.6, 1.6), ylim = c(-1.5, 1.5),
          vertex.size = 5, vertex.color = colors[main_groups], vertex.frame.color = NA, vertex.label = NA,
          edge.color = grDevices::adjustcolor(colors[ends[, 1]], alpha.f = .8),
          edge.width = .3 + 4*igraph::E(graph)$weight/max(cc@net$count), edge.arrow.size = .25, edge.curved = .15)
        for (j in seq_along(main_groups)) graphics::text(xy[j,1]*1.22, xy[j,2]*1.22, labels = main_groups[j], cex = .86,
                       adj = c(ifelse(xy[j,1] > .2, 0, ifelse(xy[j,1] < -.2, 1, .5)), .5))
        graphics::title(main = "Focused interactions", cex.main = 1, font.main = 1)
        graphics::mtext(sprintf("Maximum edge = %.3g; equal node sizes", max(cc@net$count)), side = 1, line = -.2, cex = .86)
        invisible(NULL)
      },
             "主图焦点发送→接收网络，边宽与完整count图相同；筛选见main_figure_selection.json。", 89, 78, "main_figure_edges.tsv")
      if (length(main_paths)) export("main_chord", function() {
        graphics::par(fig = c(0, 1, .18, 1), mar = c(0, 0, 0, 0))
        links <- aggregate(score ~ source + target + pathway, main_edges[main_edges$pathway %in% main_paths, ], sum)
        links$from <- paste("sender", links$source, links$pathway, sep = "|")
        links$to <- paste("receiver", links$target, sep = "|")
        labels <- c(setNames(links$pathway, links$from), setNames(links$target, links$to)); labels <- labels[!duplicated(names(labels))]
        sectors <- c(unique(links$from), unique(links$to))
        grids <- c(setNames(colors[links$source], links$from), setNames(colors[links$target], links$to)); grids <- grids[!duplicated(names(grids))]
        circlize::circos.clear()
        circlize::circos.par(start.degree = 90, canvas.xlim = c(-1.25, 1.25), canvas.ylim = c(-1.25, 1.25))
        circlize::chordDiagram(links[, c("from", "to", "score")], order = sectors, grid.col = grids, col = colors[links$source],
          transparency = .4, directional = 1, direction.type = c("diffHeight", "arrows"), link.arr.type = "big.arrow",
          annotationTrack = "grid", preAllocateTracks = list(track.height = .16), annotationTrackHeight = .035, small.gap = 2, big.gap = 8)
        circlize::circos.trackPlotRegion(track.index = 1, bg.border = NA, panel.fun = function(x, y) {
          sector <- circlize::get.cell.meta.data("sector.index")
          circlize::circos.text(mean(circlize::get.cell.meta.data("xlim")), 0, labels[[sector]], facing = "clockwise", niceFacing = TRUE,
                                adj = c(0, .5), cex = .9)
        })
        legend <- ComplexHeatmap::Legend(at = main_groups, type = "grid", ncol = 2, legend_gp = grid::gpar(fill = colors[main_groups]),
             labels_gp = grid::gpar(fontsize = 6), grid_height = grid::unit(2, "mm"))
        ComplexHeatmap::draw(legend, x = grid::unit(.5, "npc"), y = grid::unit(.02, "npc"), just = c("center", "bottom"))
        circlize::circos.clear()
        invisible(NULL)
      }, "主图使用circlize绘制CellChat原生分数；发送扇区为细胞-通路，接收扇区为细胞；带宽为源表分数和，固定轨道预留保证最终尺寸可读。", 89, 78, "main_figure_edges.tsv")
      mc <- aggregate(score ~ source + target, transform(main_edges, score = 1), sum)
      mc$label <- paste(mc$source, mc$target, sep = " → ")
      write_table(mc, "main_counts.tsv")
      export("main_counts", function() ggplot2::ggplot(mc, ggplot2::aes(x = reorder(label, score), y = score, fill = target)) +
               ggplot2::geom_col(width = .65) + ggplot2::coord_flip() + ggplot2::scale_fill_manual(values = colors, guide = "none") +
               ggplot2::labs(x = NULL, y = "Supported LR count"), "焦点细胞对支持LR数量，单对象不添加供体误差线。", 89, 78, "main_counts.tsv")
      ms <- aggregate(score ~ interaction, main_edges, sum)
      ms <- head(ms[order(-ms$score, ms$interaction), ], 5L)
      write_table(ms, "main_lr_scores.tsv")
      export("main_lr_scores", function() ggplot2::ggplot(ms, ggplot2::aes(x = reorder(interaction, score), y = score)) +
               ggplot2::geom_col(width = .65, fill = "#0072B2") + ggplot2::coord_flip() + ggplot2::labs(x = NULL, y = "Summed native score"),
             "焦点范围内原生分数最高的5个LR；完整排名另交付，不代表疾病差异或因果作用。", 89, 78, "main_lr_scores.tsv")
    }
  } else skip("core_networks", "零支持候选；保留完整候选及过滤记录，不降低阈值凑图")
  for (k in c("condition_comparison", "embedding", "functional_scores", "clinical_association")) skip(k, "由 run_communication.py 按配置与实际输入执行；单对象程序不推测额外数据")
  manifest$status <- if (any(vapply(manifest$figures, function(x) x$status == "failed", logical(1)))) "partial" else if (nrow(edges)) "core_figures_generated" else "no_supported_edges"
  write_json(manifest, "figure_manifest.json")
  report <- c(paste0("# ", cfg$dataset, " / ", cfg$sample), "", cfg$research_question,
              "", "结果是通讯候选推断；可编辑图件已输出，实际视觉与科学审查仍需执行。", "")
  for (f in manifest$figures) report <- c(report, paste0("- ", f$id, ": ", f$status, " — ", f$caption %||% f$reason %||% f$error))
  writeLines(report, file.path(out, "figure_report.md"))
  if (manifest$status == "partial") quit(status = 2L)
}, error = function(e) {
  manifest$status <- "failed"; manifest$error <- conditionMessage(e); write_json(manifest, "figure_manifest.json")
  message(conditionMessage(e)); quit(status = 1L)
})
