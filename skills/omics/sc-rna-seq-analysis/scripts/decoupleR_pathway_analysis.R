###############################################################################
# decoupleR 单细胞通路活性推断分析
# 输入：
#   01_SingleCell_Analysis_Complete.RData  — 含Seurat对象（需有umap reduction）
#   03_Cell_ID_to_CellType_Mapping.csv     — 细胞注释映射表
# 输出：
#   PROGENy通路活性矩阵 + 热图 + 箱线图 + 差异检验 + UMAP
###############################################################################

options(stringsAsFactors = FALSE)
set.seed(123)

library(Seurat)
library(decoupleR)
library(OmnipathR)
library(dplyr)
library(tidyr)
library(tibble)
library(ggplot2)
library(pheatmap)
library(RColorBrewer)
library(Matrix)
library(patchwork)

# ====================== 1. 路径设置 ======================
workDir <- normalizePath(
  "",  # ← 填写工作目录路径
  winslash = "/",
  mustWork = TRUE
)
setwd(workDir)

input_rdata <- file.path(workDir, "01_SingleCell_Analysis_Complete.RData")
cell_mapping_file <- file.path(workDir, "03_Cell_ID_to_CellType_Mapping.csv")
output_dir <- file.path(workDir, "01.decoupleR_Activity_Inference")
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

# ====================== 2. 自定义函数 ======================

save_plot_pdf <- function(plot, filename, width = 8, height = 6) {
  ggplot2::ggsave(
    filename = file.path(output_dir, filename),
    plot = plot,
    width = width,
    height = height,
    device = cairo_pdf,
    family = "Arial"
  )
}

get_assay_data_compat <- function(object, assay = "RNA", layer = "data") {
  if ("LayerData" %in% getNamespaceExports("SeuratObject")) {
    return(SeuratObject::LayerData(object = object, assay = assay, layer = layer))
  }
  Seurat::GetAssayData(object = object, assay = assay, slot = layer)
}

# ====================== 3. 加载数据 ======================
message("加载 Seurat 对象：", input_rdata)
loaded_names <- load(input_rdata)
seurat_names <- loaded_names[vapply(loaded_names, function(x) inherits(get(x), "Seurat"), logical(1))]
if (length(seurat_names) < 1) stop("RData 中未找到 Seurat 对象！")
seurat_obj <- get(seurat_names[1])
message("成功加载 Seurat 对象：", seurat_names[1])

message("加载细胞注释表...")
cell_mapping <- read.csv(cell_mapping_file, check.names = FALSE, fileEncoding = "UTF-8-BOM")
required_cols <- c("Cell_ID", "Cell_Type", "Group", "Cluster_ID")
missing_cols <- setdiff(required_cols, colnames(cell_mapping))
if (length(missing_cols) > 0) stop("缺少列：", paste(missing_cols, collapse = ", "))

cell_mapping <- cell_mapping[!duplicated(cell_mapping$Cell_ID), ]
matched_cells <- intersect(colnames(seurat_obj), cell_mapping$Cell_ID)
if (length(matched_cells) == 0) stop("细胞ID无匹配！")
message("匹配有效细胞：", length(matched_cells), "个")
seurat_obj <- subset(seurat_obj, cells = matched_cells)
cell_mapping <- cell_mapping[match(colnames(seurat_obj), cell_mapping$Cell_ID), ]

seurat_obj$cell_type <- cell_mapping$Cell_Type
seurat_obj$group <- cell_mapping$Group
seurat_obj$cluster <- as.character(cell_mapping$Cluster_ID)
Idents(seurat_obj) <- seurat_obj$cell_type

# ====================== 4. 数据预处理 ======================
DefaultAssay(seurat_obj) <- "RNA"
rna_data <- get_assay_data_compat(seurat_obj, layer = "data")

if (length(rna_data@x) == 0) {
  message("执行数据标准化...")
  seurat_obj <- NormalizeData(seurat_obj, verbose = FALSE)
  rna_data <- get_assay_data_compat(seurat_obj, layer = "data")
}

# ====================== 5. 获取PROGENy通路网络 ======================
message("下载PROGENy人类通路网络...")
progeny_net <- get_progeny(organism = "human", top = 500)
write.csv(progeny_net, file.path(output_dir, "01_PROGENy_Network.csv"), row.names = FALSE)

common_genes <- intersect(rownames(rna_data), unique(progeny_net$target))
message("共用基因数：", length(common_genes))
if (length(common_genes) < 50) stop("基因数量过少，分析失败！")
mat <- as.matrix(rna_data[common_genes, ])

# ====================== 6. 运行decoupleR计算通路活性 ======================
message("开始计算通路活性...")
acts <- run_mlm(
  mat = mat,
  net = progeny_net,
  .source = "source",
  .target = "target",
  .mor = "weight",
  minsize = 5
)

activity_mat <- acts %>%
  select(source, condition, score) %>%
  pivot_wider(id_cols = "source", names_from = "condition", values_from = "score") %>%
  column_to_rownames("source") %>%
  as.matrix()

seurat_obj[["pathways"]] <- CreateAssayObject(data = activity_mat)
DefaultAssay(seurat_obj) <- "pathways"
seurat_obj <- ScaleData(seurat_obj, verbose = FALSE)

# ====================== 7. 数据整理与统计 ======================
scaled_activity <- get_assay_data_compat(seurat_obj, layer = "scale.data")
activity_long <- as.data.frame(t(as.matrix(scaled_activity))) %>%
  rownames_to_column("Cell_ID") %>%
  mutate(
    Cell_Type = seurat_obj$cell_type[match(Cell_ID, colnames(seurat_obj))],
    Group = seurat_obj$group[match(Cell_ID, colnames(seurat_obj))],
    Cluster_ID = seurat_obj$cluster[match(Cell_ID, colnames(seurat_obj))]
  ) %>%
  pivot_longer(cols = -c(Cell_ID, Cell_Type, Group, Cluster_ID),
               names_to = "Pathway", values_to = "Activity_Score")

summary_celltype <- activity_long %>%
  group_by(Cell_Type, Pathway) %>%
  summarise(mean_activity = mean(Activity_Score, na.rm = TRUE), .groups = "drop")

summary_group <- activity_long %>%
  group_by(Group, Pathway) %>%
  summarise(mean_activity = mean(Activity_Score, na.rm = TRUE), .groups = "drop")

summary_cellgroup <- activity_long %>%
  group_by(Cell_Type, Group, Pathway) %>%
  summarise(mean_activity = mean(Activity_Score, na.rm = TRUE), .groups = "drop")

write.csv(summary_celltype, file.path(output_dir, "06_通路活性_细胞类型.csv"), row.names = FALSE)
write.csv(summary_group, file.path(output_dir, "07_通路活性_分组.csv"), row.names = FALSE)
write.csv(summary_cellgroup, file.path(output_dir, "08_通路活性_细胞类型_分组.csv"), row.names = FALSE)

# ====================== 8. 可视化：热图 ======================
plot_heatmap <- function(summary_df, row_name, out_file, w = 9, h = 7) {
  mat <- summary_df %>%
    select(all_of(row_name), Pathway, mean_activity) %>%
    pivot_wider(id_cols = all_of(row_name), names_from = Pathway, values_from = mean_activity) %>%
    column_to_rownames(row_name) %>%
    as.matrix()

  cairo_pdf(file.path(output_dir, out_file), width = w, height = h, family = "Arial")
  pheatmap(mat, scale = "none", border_color = "white",
           color = colorRampPalette(rev(brewer.pal(11, "RdBu")))(100))
  dev.off()
}

plot_heatmap(summary_celltype, "Cell_Type", "09_细胞类型通路活性热图.pdf")
summary_cellgroup$CellType_Group <- paste(summary_cellgroup$Cell_Type, summary_cellgroup$Group, sep = "_")
plot_heatmap(summary_cellgroup, "CellType_Group", "11_细胞类型分组通路热图.pdf", w = 10, h = 8)

# ====================== 9. 可视化：UMAP ======================
if ("umap" %in% names(seurat_obj@reductions)) {
  cairo_pdf(file.path(output_dir, "12_通路活性UMAP.pdf"), width = 8, height = 6)
  for (pwy in rownames(activity_mat)) {
    p <- FeaturePlot(seurat_obj, features = pwy, order = TRUE, pt.size = 0.25) +
      scale_colour_gradient2(low = "blue", mid = "white", high = "red") +
      ggtitle(pwy) + theme_classic()
    print(p)
  }
  dev.off()

  p_celltype <- DimPlot(seurat_obj, group.by = "cell_type", label = TRUE, repel = TRUE, pt.size = 0.25) +
    ggtitle("细胞类型") + theme_classic()
  save_plot_pdf(p_celltype, "13_细胞类型UMAP.pdf")
}

# ====================== 10. 可视化：箱线图 ======================
p_box1 <- ggplot(activity_long, aes(x = Cell_Type, y = Activity_Score, fill = Cell_Type)) +
  geom_boxplot(outlier.size = 0.2) +
  facet_wrap(~Pathway, scales = "free_y", ncol = 4) +
  theme_bw() + theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "none") +
  labs(x = "细胞类型", y = "标准化通路活性")
save_plot_pdf(p_box1, "14_细胞类型通路活性箱线图.pdf", width = 13, height = 9)

group_num <- length(unique(na.omit(activity_long$Group)))
if (group_num >= 2) {
  p_box2 <- ggplot(activity_long, aes(x = Group, y = Activity_Score, fill = Group)) +
    geom_boxplot(outlier.size = 0.2) +
    facet_wrap(~Pathway, scales = "free_y", ncol = 4) +
    theme_bw() + theme(axis.text.x = element_text(angle = 30, hjust = 1), legend.position = "none")
  save_plot_pdf(p_box2, "15_分组通路活性箱线图.pdf", width = 11, height = 8)

  if (group_num == 2) {
    diff_res <- activity_long %>%
      group_by(Pathway) %>%
      summarise(pval = wilcox.test(Activity_Score ~ Group)$p.value, .groups = "drop") %>%
      mutate(adj_pval = p.adjust(pval, "BH")) %>%
      arrange(adj_pval)
    write.csv(diff_res, file.path(output_dir, "16_分组通路差异检验.csv"), row.names = FALSE)
  }
}

# ====================== 11. 保存结果 ======================
saveRDS(seurat_obj, file.path(output_dir, "17_带通路活性的Seurat对象.rds"))
save(acts, activity_mat, summary_celltype, summary_group,
     file = file.path(output_dir, "18_分析结果总文件.RData"))

message("========== 分析完成！所有结果保存在：", output_dir, " ==========")
