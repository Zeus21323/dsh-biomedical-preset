# PCA指标口径与绘图
Python需要numpy、matplotlib、Pillow；h5ad提取加anndata。R提取需jsonlite/SeuratObject。由代理根据实际对象生成配置，不要求用户知道PC或JSON。
## 提取
`python scripts/extract_pca.py --config input.json --out-dir extracted`：input指h5ad，pca_key默认pca，feature_space说明标准化/缩放与特征集，denominator必须经运行记录确认为total_input_variance。仅提取存储variance_ratio，不将部分特征值重新归一化。
`Rscript scripts/extract_pca.R --config input.json --out-dir extracted`：input指Seurat RDS，reduction默认pca，feature_space必填；输出stdev，分母not_applicable。不能将LSI奇异值冒充PCA比例；代理先核验reduction实际方法。
## 绘图
`python scripts/render_pca.py --config figure.json --out-dir figures_new`。必填table/question/caption/denominator/feature_space；可选cumulative（布尔）、selected_pcs/selection_reason、font、width_mm、height_mm、dpi。
表列pc_index/statistic_type/value/unit。索引从1连续唯一。stdev单位standard_deviation、分母not_applicable；variance_ratio单位fraction、分母total_input_variance；retained_ratio单位fraction、分母stored_components_variance。输入单位明确，绘图比例乘100后标%。不能从只有前K个标准差推断总解释率。cumulative仅对比例有效，不对标准差累计；不得因只显示部分PC而改变分母。
点线保留所有计划数据，横轴稀疏刻度，无逐点标签；选维参考线有实际依据才添加。默认无网格。拐点结合技术因素、marker和稳定性判断，不证明之后PC都是噪声。
三格式及源表/图注/manifest由本目录scripts/figure_delivery.py交付，拒绝覆盖，目视审查单独完成。
来源：[Scanpy PCA图](https://scanpy.readthedocs.io/en/stable/api/generated/scanpy.pl.pca_variance_ratio.html)、[Seurat ElbowPlot](https://satijalab.org/seurat/reference/elbowplot)，2026-09-08核查；匹配实际安装版本。

## 指标选择与结果解释
用户希望“把挤在一起的标签整理清楚”时，代理先检查是否已经有可复用的降维结果。此时任务是重绘，不能为了获得更漂亮的曲线重新选择特征、调整标准化或删除供体。只有实际研究问题要求重新分析，才进入相应分析阶段，并记录与原结果的差别。
主成分图反映特定输入特征空间中的变化结构。输入是高变基因、全部基因，还是某个校正后的表达层，会影响曲线含义。代理须在图注写出实际使用的特征和处理阶段，不能把不同特征空间的解释比例直接比较，也不能将累计比例理解为解释了同等比例的疾病机制。
标准差可以如实展示各分量大小，但平方后的部分分量之和并不自动等于全部输入总方差。若对象仅保存若干主成分，继续将这些数值归一化会让最后一个累计点达到百分之百，这只可能表示所存分量内部的比例。没有总分母时应明确使用标准差或内部比例，而不是用百分号制造全量解释率。
所有计划展示的分量都保留为点和线，减少的是重复文字。稀疏刻度仅帮助读数，不改变数据数量。特别关心某个维数时，可依据已有分析决定添加参考线，并在图注说明选择理由。没有决定时无需添加装饰性“最佳维数”。
拐点只是一条诊断线索。分量可能反映文库深度、技术批次、细胞状态或真实群体变化，也可能混合这些来源。应结合协变量关联、标记基因和群体稳定性判断，不把尾部平缓直接称为噪声。若相关验证无法执行，明确限制，不用图形替代证据。
导出前后核对纵轴名称、单位、分母、分量数量和参考线。累计面板与单分量面板应有一致横轴和清楚的独立纵轴，不能把两种指标混为同一曲线。最终预览要能在预定尺寸阅读，三格式数值和排版应一致。
