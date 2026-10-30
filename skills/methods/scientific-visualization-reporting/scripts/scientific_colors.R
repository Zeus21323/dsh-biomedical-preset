# 仅定义读取函数；source后显式传入共享TSV路径，不写文件、不更改工作目录。
# 错误使用stop终止；不捕获后静默回退。实际R渲染仍由原分析脚本执行。
figure_palette <- function(palette_file, name, kind) {
  d <- read.delim(palette_file, stringsAsFactors = FALSE, check.names = FALSE,
                  comment.char = "", colClasses = "character")
  if (!all(c("palette", "kind", "position", "color") %in% names(d))) stop("色板字段缺失")
  d <- d[d$palette == name, , drop = FALSE]
  if (!nrow(d) || anyNA(d) || any(d$kind != kind)) stop("色板不存在或用途不符")
  pos <- suppressWarnings(as.integer(d$position))
  if (anyNA(pos) || !identical(sort(pos), seq_len(nrow(d)))) stop("色板位置须连续唯一")
  values <- toupper(d$color[order(pos)])
  if (any(!grepl("^#[0-9A-F]{6}$", values))) stop("颜色须为六位HEX")
  values
}

figure_colors <- function(registry_file, variable, categories) {
  d <- read.delim(registry_file, stringsAsFactors = FALSE, check.names = FALSE,
                  comment.char = "", colClasses = "character")
  if (!all(c("variable", "category", "color") %in% names(d)) || !nrow(d)) stop("颜色映射字段缺失或为空")
  if (anyNA(d) || any(!nzchar(trimws(d$variable))) || any(!nzchar(trimws(d$category))) ||
      any(duplicated(d[c("variable", "category")]))) stop("颜色映射身份缺失或重复")
  d <- d[d$variable == variable, , drop = FALSE]
  d$color <- toupper(d$color)
  if (!nrow(d) || any(!grepl("^#[0-9A-F]{6}$", d$color)) || anyDuplicated(d$color)) stop("颜色无效或重复")
  if (!length(categories) || anyNA(categories) || any(!nzchar(trimws(categories))) || anyDuplicated(categories)) stop("类别须非空唯一")
  idx <- match(categories, d$category)
  if (anyNA(idx)) stop("项目颜色映射未覆盖实际类别；不得按子集重新分配")
  setNames(d$color[idx], categories)
}
