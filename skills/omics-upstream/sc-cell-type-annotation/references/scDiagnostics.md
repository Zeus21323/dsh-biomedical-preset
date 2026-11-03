# scDiagnostics：注释后复核

[论文](https://doi.org/10.1093/bib/bbag496)；[Bioconductor](https://bioconductor.org/packages/scDiagnostics/)；[作者源码](https://github.com/ccb-hms/scDiagnostics)。包装器适配commit `7e9343ca78eaa714213a5cfa013034098cb4a9db` 的1.7.2版本返回结构，许可Artistic-2.0；不能把任意release当相同API。

## 用户语言与检查目标

“这些细胞名字对不对”“不同软件不一致”“疾病细胞被都标成正常”应引导到参考适配、marker证据和异常诊断，而不是让用户选择R函数。只给标签名而无表达/reference，先说明需找回原对象，不根据名字断言误标。

## 首版可执行范围

包装器调用真实 `calculateWassersteinDistance`，比较共享标签内reference–reference与reference–query距离分布。不是重新注释器，也不自动运行所有scDiagnostics方法。

输入reference.rds与query.rds均为可信SingleCellExperiment，包含已明确的表达层、唯一基因/细胞ID和标签列；基因轴完全一致。不自动将缺失基因补零，不隐式删除未知标签。settings.rds为列表，必含ref_label、query_label、assay、seed、pc_subset、n_resamples、max_cells、parameter_reason。pc_subset为正整数向量，其他数值由代理按数据和计算预算选择；抽样记录用于描述性诊断，不是供体重复。

reference必须已有与指定表达层匹配的PCA、带基因行名的rotation载荷和有效varExplained属性；固定方法会用后者加权。缺少时先按原生 `processPCA(sce_object=ref, assay_name=..., n_hvgs=..., max_cells=...)` 明确处理并保存新的reference与参数，不能从UMAP或任意Seurat降维对象猜载荷/权重。n_hvgs及抽样依据数据和预算决定，记录处理前后细胞数；不要把调用中局部重算PCA误认为原对象已更新。query投影到reference空间，无需强行独立拟合再对齐。

```bash
Rscript scripts/run_scdiagnostics.R reference.rds query.rds settings.rds diagnostics-01
```

依赖固定commit安装的scDiagnostics（R>=4.4及包依赖）、ggplot2、svglite；RemoteSha必须匹配。当前环境无R实跑证据，不能据静态核验宣称诊断结果复现。输入RDS只从可信本地分析产生。

输出alignment.rds、alignment_distances.tsv、run_record.rds、状态、Markdown摘要和原生图的PDF/SVG/400 DPI PNG。保留query中reference没有的标签，不能将它们当作已通过诊断。原标签不改、不自动删细胞，失败退出并保留诊断文件。

## 扩展诊断的选择

有进一步需求时核对固定版本的compareMarkers、calculateGeneShifts、detectAnomaly等原生参数与返回结构。检测异常时记录阈值由reference估计还是绝对阈值、所用PC/HVG、抽样种子、参考标签和每类细胞数。不能把另一版本字段名直接套用。细胞ID必须从返回对象验证，不按输出顺序猜回原始对象。

异常可来自技术质量、疾病状态偏移、reference缺少类型或标注失败；靠marker、QC、跨供体复现和其他注释证据区分。reference–query差异本身不能证明误标，健康图谱也不能强行解释所有疾病状态。

## 图和报告

原生距离图只是分布比较；供体层差异需要另行计算。marker对照图保留所用表达层与标准化；异常热图记录选择/抽样与未知群。每张图交付原表、可编辑矢量、高清预览和含样本/细胞数的图注，打开检查布局，不靠UMAP颜色论证正确率。

结果解读给出可靠标签、冲突类型、可能新状态、技术疑点和需人工复核项。无外部金标准时不宣称误标率/准确率已被证实。
