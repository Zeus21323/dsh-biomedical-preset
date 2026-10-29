###############################################################################
# scMetabolism 单细胞代谢通路活性分析
# 输入：
#   01_SingleCell_Analysis_Complete.RData  — 含Seurat对象（需有umap reduction）
#   03_Cell_ID_to_CellType_Mapping.csv     — 细胞注释映射表
# 输出：
#   代谢通路活性矩阵 + 热图 + 点图 + 箱线图 + 差异分析 + UMAP
###############################################################################

options(stringsAsFactors = FALSE, encoding = "UTF-8")
set.seed(123)

library(Seurat)
library(SeuratObject)
library(scMetabolism)
library(dplyr)
library(tidyr)
library(tibble)
library(ggplot2)
library(pheatmap)
library(RColorBrewer)
library(Matrix)
library(patchwork)

# ====================== 1. 参数设置 ======================
workDir <- normalizePath(
  "",  # ← 填写工作目录路径
  winslash = "/",
  mustWork = TRUE
)
setwd(workDir)

input_rdata <- file.path(workDir, "01_SingleCell_Analysis_Complete.RData")
cell_mapping_file <- file.path(workDir, "03_Cell_ID_to_CellType_Mapping.csv")
output_dir <- file.path(workDir, "01.scMetabolism_Analysis")
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

metabolism_method <- "AUCell"   # scMetabolism 评分方法
metabolism_type <- "KEGG"       # 代谢通路数据库类型
run_imputation <- FALSE
ncores_use <- 2
top_pathway_n <- 20             # 展示方差最大的前N条通路

# ====================== 2. 自定义函数 ======================

save_plot_pdf <- function(plot, filename, width = 8, height = 6) {
  ggplot2::ggsave(
    filename = file.path(output_dir, filename),
    plot = plot,
    width = width,
    height = height,
    device = grDevices::cairo_pdf,
    family = "Arial"
  )
}

write_utf8_csv <- function(x, filename, row.names = FALSE) {
  utils::write.csv(
    x,
    file = file.path(output_dir, filename),
    row.names = row.names,
    fileEncoding = "UTF-8"
  )
}

sanitize_filename <- function(x) {
  x <- gsub("[\\\\/:*?\"<>|]", "_", x)
  x <- gsub("\\s+", "_", x)
  x
}

matrix_nonzero_count <- function(x) {
  if (inherits(x, "sparseMatrix")) {
    return(length(x@x))
  }
  sum(x != 0, na.rm = TRUE)
}

join_assay_layers_if_needed <- function(object, assay = "RNA") {
  if (!assay %in% names(object@assays)) {
    stop("Seurat 对象中没有 assay：", assay)
  }
  assay_obj <- object[[assay]]
  if (!inherits(assay_obj, "Assay5")) {
    return(object)
  }
  layer_names <- SeuratObject::Layers(assay_obj)
  counts_layers <- grep("^counts", layer_names, value = TRUE)
  data_layers <- grep("^data", layer_names, value = TRUE)
  if (length(counts_layers) > 1 || length(data_layers) > 1) {
    message("检测到 Seurat v5 多 layer assay，执行 JoinLayers 合并：", assay)
    object <- SeuratObject::JoinLayers(object, assay = assay)
  }
  object
}

get_assay_layer_compat <- function(object, assay = "RNA", layer = "counts") {
  if (!assay %in% names(object@assays)) {
    stop("Seurat 对象中没有 assay：", assay)
  }
  assay_obj <- object[[assay]]
  if (inherits(assay_obj, "Assay5")) {
    layer_names <- SeuratObject::Layers(assay_obj)
    matched_layer <- layer_names[layer_names == layer]
    if (length(matched_layer) == 0) {
      matched_layer <- grep(paste0("^", layer), layer_names, value = TRUE)
    }
    if (length(matched_layer) > 0) {
      return(SeuratObject::LayerData(object = object, assay = assay, layer = matched_layer[1]))
    }
  }
  Seurat::GetAssayData(object = object, assay = assay, slot = layer)
}

zscore_rows <- function(mat) {
  scaled <- t(scale(t(as.matrix(mat))))
  scaled[is.na(scaled)] <- 0
  scaled
}

# ====================== 3. 加载数据 ======================
message("加载 Seurat RData：", input_rdata)
loaded_names <- load(input_rdata)
seurat_names <- loaded_names[vapply(loaded_names, function(x) inherits(get(x), "Seurat"), logical(1))]
if (length(seurat_names) < 1) {
  stop("RData 中未找到 Seurat 对象。")
}
seurat_obj_name <- seurat_names[1]
seurat_obj <- get(seurat_obj_name)
message("使用 Seurat 对象：", seurat_obj_name)
message("原始基因数：", nrow(seurat_obj), "；原始细胞数：", ncol(seurat_obj))

if (!file.exists(cell_mapping_file)) {
  stop("找不到细胞注释映射表：", cell_mapping_file)
}
cell_mapping <- read.csv(cell_mapping_file, check.names = FALSE, fileEncoding = "UTF-8-BOM")
required_mapping_cols <- c("Cell_ID", "Cell_Type", "Group", "Cluster_ID")
missing_mapping_cols <- setdiff(required_mapping_cols, colnames(cell_mapping))
if (length(missing_mapping_cols) > 0) {
  stop("细胞注释映射表缺少列：", paste(missing_mapping_cols, collapse = ", "))
}

cell_mapping <- cell_mapping[!duplicated(cell_mapping$Cell_ID), , drop = FALSE]
matched_cells <- intersect(colnames(seurat_obj), cell_mapping$Cell_ID)
if (length(matched_cells) == 0) {
  stop("Seurat 对象细胞名与 Cell_ID 无交集，请检查输入文件。")
}
message("匹配到细胞数：", length(matched_cells), " / ", ncol(seurat_obj))
seurat_obj <- subset(seurat_obj, cells = matched_cells)
cell_mapping <- cell_mapping[match(colnames(seurat_obj), cell_mapping$Cell_ID), , drop = FALSE]

seurat_obj$scMetabolism_cell_type <- cell_mapping$Cell_Type
seurat_obj$scMetabolism_group <- cell_mapping$Group
seurat_obj$scMetabolism_cluster <- as.character(cell_mapping$Cluster_ID)

if (anyNA(seurat_obj$scMetabolism_cell_type)) {
  stop("部分细胞缺少 Cell_Type 注释。")
}
Idents(seurat_obj) <- seurat_obj$scMetabolism_cell_type
write_utf8_csv(cell_mapping, "00_Cell_ID_to_CellType_Mapping_Used.csv")

# ====================== 4. 运行 scMetabolism ======================
DefaultAssay(seurat_obj) <- "RNA"
seurat_obj <- join_assay_layers_if_needed(seurat_obj, assay = "RNA")
counts_mat <- get_assay_layer_compat(seurat_obj, assay = "RNA", layer = "counts")
if (nrow(counts_mat) == 0 || ncol(counts_mat) == 0 || matrix_nonzero_count(counts_mat) == 0) {
  stop("RNA counts layer 为空。scMetabolism 需要 UMI count matrix，请检查 Seurat 对象。")
}
counts_mat <- counts_mat[, colnames(seurat_obj), drop = FALSE]
message("用于 scMetabolism 的 counts 矩阵：", nrow(counts_mat), " genes x ", ncol(counts_mat), " cells")

message(
  "运行 scMetabolism：method = ", metabolism_method,
  "；metabolism.type = ", metabolism_type,
  "；imputation = ", run_imputation,
  "；ncores = ", ncores_use
)
metabolism_score <- scMetabolism::sc.metabolism(
  countexp = as.matrix(counts_mat),
  method = metabolism_method,
  imputation = run_imputation,
  ncores = ncores_use,
  metabolism.type = metabolism_type
)

metabolism_score <- as.matrix(metabolism_score)
metabolism_score <- metabolism_score[, colnames(seurat_obj), drop = FALSE]
rownames(metabolism_score) <- make.unique(rownames(metabolism_score))
if (anyNA(metabolism_score)) {
  message("代谢分数矩阵存在 NA，后续汇总和绘图将按 na.rm = TRUE 处理。")
}

write_utf8_csv(
  as.data.frame(metabolism_score) %>% tibble::rownames_to_column("Pathway"),
  "01_scMetabolism_Score_Matrix.csv"
)

score_scaled <- zscore_rows(metabolism_score)
write_utf8_csv(
  as.data.frame(score_scaled) %>% tibble::rownames_to_column("Pathway"),
  "02_scMetabolism_Score_Matrix_RowZscore.csv"
)

# 将代谢分数存入 Seurat 对象
seurat_obj[["METABOLISM"]] <- Seurat::CreateAssayObject(data = metabolism_score)
DefaultAssay(seurat_obj) <- "METABOLISM"
seurat_obj <- ScaleData(seurat_obj, verbose = FALSE)

# ====================== 5. 数据整理与统计 ======================
metabolism_long <- as.data.frame(t(metabolism_score), check.names = FALSE) %>%
  tibble::rownames_to_column("Cell_ID") %>%
  dplyr::mutate(
    Cell_Type = seurat_obj$scMetabolism_cell_type[match(Cell_ID, colnames(seurat_obj))],
    Group = seurat_obj$scMetabolism_group[match(Cell_ID, colnames(seurat_obj))],
    Cluster_ID = seurat_obj$scMetabolism_cluster[match(Cell_ID, colnames(seurat_obj))]
  ) %>%
  tidyr::pivot_longer(
    cols = -c(Cell_ID, Cell_Type, Group, Cluster_ID),
    names_to = "Pathway",
    values_to = "Metabolism_Score"
  )

metabolism_scaled_long <- as.data.frame(t(score_scaled), check.names = FALSE) %>%
  tibble::rownames_to_column("Cell_ID") %>%
  tidyr::pivot_longer(
    cols = -Cell_ID,
    names_to = "Pathway",
    values_to = "Metabolism_Zscore"
  )

metabolism_long <- metabolism_long %>%
  dplyr::left_join(metabolism_scaled_long, by = c("Cell_ID", "Pathway"))

saveRDS(metabolism_long, file.path(output_dir, "03_scMetabolism_Long_Table.rds"))

summary_by_cell_type <- metabolism_long %>%
  dplyr::group_by(Cell_Type, Pathway) %>%
  dplyr::summarise(
    n_cells = dplyr::n(),
    mean_score = mean(Metabolism_Score, na.rm = TRUE),
    median_score = median(Metabolism_Score, na.rm = TRUE),
    sd_score = sd(Metabolism_Score, na.rm = TRUE),
    mean_zscore = mean(Metabolism_Zscore, na.rm = TRUE),
    .groups = "drop"
  )
write_utf8_csv(summary_by_cell_type, "04_Pathway_Score_By_CellType.csv")

summary_by_group <- metabolism_long %>%
  dplyr::group_by(Group, Pathway) %>%
  dplyr::summarise(
    n_cells = dplyr::n(),
    mean_score = mean(Metabolism_Score, na.rm = TRUE),
    median_score = median(Metabolism_Score, na.rm = TRUE),
    sd_score = sd(Metabolism_Score, na.rm = TRUE),
    mean_zscore = mean(Metabolism_Zscore, na.rm = TRUE),
    .groups = "drop"
  )
write_utf8_csv(summary_by_group, "05_Pathway_Score_By_Group.csv")

summary_by_cell_type_group <- metabolism_long %>%
  dplyr::group_by(Cell_Type, Group, Pathway) %>%
  dplyr::summarise(
    n_cells = dplyr::n(),
    mean_score = mean(Metabolism_Score, na.rm = TRUE),
    median_score = median(Metabolism_Score, na.rm = TRUE),
    sd_score = sd(Metabolism_Score, na.rm = TRUE),
    mean_zscore = mean(Metabolism_Zscore, na.rm = TRUE),
    .groups = "drop"
  )
write_utf8_csv(summary_by_cell_type_group, "06_Pathway_Score_By_CellType_Group.csv")

# ====================== 6. 可视化 ======================

plot_heatmap <- function(summary_df, row_col, value_col, output_pdf, width = 9, height = 7) {
  heatmap_mat <- summary_df %>%
    dplyr::select(dplyr::all_of(c(row_col, "Pathway", value_col))) %>%
    tidyr::pivot_wider(
      id_cols = dplyr::all_of(row_col),
      names_from = "Pathway",
      values_from = dplyr::all_of(value_col)
    ) %>%
    tibble::column_to_rownames(row_col) %>%
    as.matrix()
  heatmap_mat <- heatmap_mat[stats::complete.cases(heatmap_mat), , drop = FALSE]
  if (nrow(heatmap_mat) < 1 || ncol(heatmap_mat) < 1) {
    return(invisible(NULL))
  }
  colors_use <- grDevices::colorRampPalette(rev(RColorBrewer::brewer.pal(n = 11, name = "RdBu")))(100)
  grDevices::cairo_pdf(file.path(output_dir, output_pdf), width = width, height = height, family = "Arial")
  pheatmap::pheatmap(
    mat = heatmap_mat,
    color = colors_use,
    border_color = "white",
    scale = "none",
    cluster_rows = nrow(heatmap_mat) >= 2,
    cluster_cols = ncol(heatmap_mat) >= 2,
    fontsize = 10,
    fontsize_row = 10,
    fontsize_col = 10,
    main = value_col
  )
  grDevices::dev.off()
}

# 热图：按细胞类型
plot_heatmap(
  summary_by_cell_type, "Cell_Type", "mean_zscore",
  "07_Heatmap_scMetabolism_By_CellType.pdf", width = 11, height = 8
)

# 热图：按细胞类型+分组
summary_by_cell_type_group_plot <- summary_by_cell_type_group %>%
  dplyr::mutate(CellType_Group = paste(Cell_Type, Group, sep = "_"))
plot_heatmap(
  summary_by_cell_type_group_plot, "CellType_Group", "mean_zscore",
  "08_Heatmap_scMetabolism_By_CellType_Group.pdf", width = 12, height = 9
)

# 方差最大的前N条通路
pathway_variance <- apply(metabolism_score, 1, stats::var, na.rm = TRUE)
selected_pathways <- names(sort(pathway_variance, decreasing = TRUE))[seq_len(min(top_pathway_n, length(pathway_variance)))]
write_utf8_csv(
  data.frame(Pathway = names(sort(pathway_variance, decreasing = TRUE)), Variance = sort(pathway_variance, decreasing = TRUE)),
  "09_Pathway_Variance_Rank.csv"
)

# 点图
dot_df <- summary_by_cell_type %>%
  dplyr::filter(Pathway %in% selected_pathways) %>%
  dplyr::mutate(Pathway = factor(Pathway, levels = rev(selected_pathways)))

p_dot <- ggplot(dot_df, aes(x = Cell_Type, y = Pathway)) +
  geom_point(aes(size = mean_score, color = mean_zscore)) +
  scale_color_gradient2(low = "#2166AC", mid = "white", high = "#B2182B") +
  scale_size_continuous(range = c(1.5, 6)) +
  theme_bw(base_family = "Arial", base_size = 10) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
    panel.grid.major = element_line(color = "grey90", linewidth = 0.2),
    panel.grid.minor = element_blank()
  ) +
  labs(x = "Cell type", y = "Metabolic pathway", color = "Mean z-score", size = "Mean score")
save_plot_pdf(p_dot, "10_Dotplot_scMetabolism_TopPathways_By_CellType.pdf", width = 11, height = 8)

# 箱线图：按细胞类型
p_box_cell_type <- metabolism_long %>%
  dplyr::filter(Pathway %in% selected_pathways) %>%
  ggplot(aes(x = Cell_Type, y = Metabolism_Score, fill = Cell_Type)) +
  geom_boxplot(outlier.size = 0.2, linewidth = 0.2) +
  facet_wrap(~Pathway, scales = "free_y", ncol = 4) +
  theme_bw(base_family = "Arial", base_size = 9) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, vjust = 1),
    legend.position = "none"
  ) +
  labs(x = "Cell type", y = "scMetabolism score", title = "Top variable metabolic pathways by cell type")
save_plot_pdf(p_box_cell_type, "11_Boxplot_scMetabolism_TopPathways_By_CellType.pdf", width = 13, height = 9)

# 箱线图：按分组 + 差异检验
group_levels_all <- unique(stats::na.omit(metabolism_long$Group))
if (length(group_levels_all) >= 2) {
  p_box_group <- metabolism_long %>%
    dplyr::filter(Pathway %in% selected_pathways) %>%
    ggplot(aes(x = Group, y = Metabolism_Score, fill = Group)) +
    geom_boxplot(outlier.size = 0.2, linewidth = 0.2) +
    facet_wrap(~Pathway, scales = "free_y", ncol = 4) +
    theme_bw(base_family = "Arial", base_size = 9) +
    theme(axis.text.x = element_text(angle = 30, hjust = 1), legend.position = "none") +
    labs(x = "Group", y = "scMetabolism score", title = "Top variable metabolic pathways by group")
  save_plot_pdf(p_box_group, "12_Boxplot_scMetabolism_TopPathways_By_Group.pdf", width = 12, height = 8)

  if (length(group_levels_all) == 2) {
    group_levels <- group_levels_all
    differential_score <- metabolism_long %>%
      dplyr::group_by(Pathway) %>%
      dplyr::summarise(
        Group_1 = group_levels[1],
        Group_2 = group_levels[2],
        mean_group_1 = mean(Metabolism_Score[Group == group_levels[1]], na.rm = TRUE),
        mean_group_2 = mean(Metabolism_Score[Group == group_levels[2]], na.rm = TRUE),
        difference_group2_minus_group1 = mean_group_2 - mean_group_1,
        p_value = tryCatch(
          stats::wilcox.test(Metabolism_Score ~ Group)$p.value,
          error = function(e) NA_real_
        ),
        .groups = "drop"
      ) %>%
      dplyr::mutate(adj_p_value = p.adjust(p_value, method = "BH")) %>%
      dplyr::arrange(adj_p_value, dplyr::desc(abs(difference_group2_minus_group1)))
    write_utf8_csv(differential_score, "13_Differential_scMetabolism_By_Group.csv")
  }
}

# UMAP 可视化
if ("umap" %in% names(seurat_obj@reductions)) {
  DefaultAssay(seurat_obj) <- "METABOLISM"
  grDevices::cairo_pdf(file.path(output_dir, "14_UMAP_scMetabolism_TopPathways.pdf"), width = 8, height = 6, family = "Arial")
  for (pathway in selected_pathways) {
    p <- FeaturePlot(
      seurat_obj,
      features = pathway,
      reduction = "umap",
      pt.size = 0.25,
      order = TRUE
    ) +
      ggplot2::scale_colour_gradient2(low = "#2166AC", mid = "white", high = "#B2182B") +
      ggplot2::ggtitle(pathway) +
      ggplot2::theme_classic(base_family = "Arial", base_size = 11) +
      ggplot2::theme(
        plot.title = ggplot2::element_text(face = "bold", hjust = 0.5),
        legend.title = ggplot2::element_text(size = 9),
        legend.text = ggplot2::element_text(size = 8)
      )
    print(p)
  }
  grDevices::dev.off()

  p_umap_celltype <- DimPlot(
    seurat_obj,
    reduction = "umap",
    group.by = "scMetabolism_cell_type",
    label = TRUE,
    repel = TRUE,
    pt.size = 0.25
  ) +
    ggplot2::ggtitle("Cell types") +
    ggplot2::theme_classic(base_family = "Arial", base_size = 11) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold", hjust = 0.5),
      legend.title = ggplot2::element_blank(),
      legend.text = ggplot2::element_text(size = 8)
    )
  save_plot_pdf(p_umap_celltype, "15_UMAP_CellType.pdf", width = 8, height = 6)
} else {
  writeLines(
    enc2utf8("Seurat 对象中未找到 umap reduction，已跳过 UMAP 代谢通路可视化。"),
    con = file.path(output_dir, "14_UMAP_scMetabolism_SKIPPED.txt"),
    useBytes = TRUE
  )
}

# ====================== 7. 保存结果 ======================
saveRDS(seurat_obj, file.path(output_dir, "16_Seurat_with_scMetabolism.rds"))
save(
  metabolism_score, score_scaled, metabolism_long,
  summary_by_cell_type, summary_by_group, summary_by_cell_type_group,
  selected_pathways,
  file = file.path(output_dir, "17_scMetabolism_Results.RData")
)

message("scMetabolism 分析完成。输出目录：", output_dir)
