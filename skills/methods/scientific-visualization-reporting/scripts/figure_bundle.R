# 将已经确定布局的grid grob导出为一套图；不接受绘图函数/每格式样式。
# 依赖R Cairo设备、svglite及已安装图件依赖的Python；不重新执行统计或聚类。
figure_export_bundle <- function(grob, out_dir, width_mm, height_mm,
                                python, verifier, source_files,
                                dpi = 400, family = "sans", background = "white") {
  if (!grid::is.grob(grob)) stop("需要最终grid grob；先构建ggplotGrob或捕获已绘制热图，不能传绘图函数")
  if (length(width_mm)!=1L || length(height_mm)!=1L || length(dpi)!=1L ||
      any(!is.finite(c(width_mm,height_mm,dpi))) || width_mm<=0 || height_mm<=0 || dpi<300) stop("共同画布尺寸或DPI无效")
  if (!is.character(family) || length(family)!=1L || !nzchar(family)) stop("须指定共同字体")
  if (!requireNamespace("svglite", quietly=TRUE)) stop("需要svglite以保留SVG文字，不能静默转轮廓")
  if (!isTRUE(capabilities("cairo"))) stop("需要Cairo设备，不能静默更换渲染器")
  if (!file.exists(python) || !file.exists(verifier)) stop("须提供可用Python和成套校验器绝对路径")
  if (!length(source_files) || any(!file.exists(source_files)) || any(dir.exists(source_files))) stop("须提供真实作图数据/配置来源文件")
  if (file.exists(out_dir) || dir.exists(out_dir)) stop("输出已存在，拒绝覆盖")
  dir.create(dirname(out_dir), recursive=TRUE, showWarnings=FALSE)
  parent <- normalizePath(dirname(out_dir),mustWork=TRUE)
  out_dir <- file.path(parent,basename(out_dir))
  stage <- tempfile(".figure-bundle-",tmpdir=parent)
  dir.create(stage)
  on.exit(unlink(stage,recursive=TRUE),add=TRUE)
  rng_exists <- exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)
  old_rng <- if (rng_exists) get(".Random.seed",envir=.GlobalEnv) else NULL
  on.exit({if(rng_exists) assign(".Random.seed",old_rng,envir=.GlobalEnv)
           else if(exists(".Random.seed",envir=.GlobalEnv,inherits=FALSE)) rm(".Random.seed",envir=.GlobalEnv)},add=TRUE)
  source_hashes <- unname(tools::md5sum(source_files))
  frozen <- serialize(grob,NULL)
  tryCatch({
    for (ext in c("png","pdf","svg")) {
      target <- file.path(stage,paste0("figure.",ext))
      if (ext=="png") grDevices::png(target,width=width_mm/25.4,height=height_mm/25.4,
                                     units="in",res=dpi,type="cairo",bg=background)
      if (ext=="pdf") grDevices::cairo_pdf(target,width=width_mm/25.4,height=height_mm/25.4,
                                           family=family,bg=background)
      if (ext=="svg") svglite::svglite(target,width=width_mm/25.4,height=height_mm/25.4,
                                     bg=background,fix_text_size=TRUE)
      device <- grDevices::dev.cur()
      tryCatch({
        # 固定重绘中的随机状态；主要布局/聚类仍必须在grob创建前确定。
        set.seed(1L)
        grid::grid.newpage()
        grid::pushViewport(grid::viewport(gp=grid::gpar(fontfamily=family)))
        grid::grid.draw(grob)
        grid::popViewport()
      },finally=grDevices::dev.off(device))
      if (!identical(frozen,serialize(grob,NULL))) stop("绘制时图形对象发生改变")
    }
    log <- file.path(stage,"verification.log")
    status <- system2(python, args=c(shQuote(verifier),"--stem",shQuote(file.path(stage,"figure")),
                    "--width-mm",as.character(width_mm),"--height-mm",as.character(height_mm),
                    "--dpi",as.character(dpi),"--record",shQuote(file.path(stage,"bundle_consistency.json"))),
                    stdout=log,stderr=log)
    if (status!=0L) stop(paste("三格式校验失败：",paste(readLines(log,warn=FALSE),collapse=" ")))
    if (!identical(source_hashes,unname(tools::md5sum(source_files)))) stop("源数据在绘制期间改变")
    saveRDS(grob,file.path(stage,"figure_object.rds"))
    saveRDS(list(width_mm=width_mm,height_mm=height_mm,dpi=dpi,family=family,background=background),
            file.path(stage,"shared_config.rds"))
    write.table(data.frame(source=normalizePath(source_files),md5=source_hashes),file.path(stage,"sources.tsv"),
                sep="\t",quote=TRUE,row.names=FALSE)
    writeLines(capture.output(sessionInfo()),file.path(stage,"session.txt"))
    writeLines(c("export_status=complete", "style_policy=one frozen grob; one shared configuration",
                 "visual_review=pending", "semantic_review=pending",
                 "svg_text_policy=svglite editable text; matching fonts required in viewer",
                 "color_policy=caller must apply validated project mapping before constructing grob"),
               file.path(stage,"delivery_status.txt"))
    if (file.exists(out_dir) || dir.exists(out_dir) || !file.rename(stage,out_dir)) stop("输出目录确认失败")
    invisible(out_dir)
  },error=function(e) {
    failure <- tempfile(paste0(basename(out_dir),"-failure-"),tmpdir=parent,fileext=".txt")
    writeLines(c("status=failed",conditionMessage(e)),failure)
    stop(conditionMessage(e),call.=FALSE)
  })
}
