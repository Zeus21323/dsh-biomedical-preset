# TWAS从输入到图件

## 分支与前置

个体基因型+已训练表达权重用于PrediXcan；GWAS摘要+模型权重及SNP协方差用于S-PrediXcan/MetaXcan；FUSION使用对应权重和LD。先核验组织、训练祖源、预测性能、build、等位基因和每基因有效SNP。用户只给表达差异表不具备TWAS输入，不能通过改列名运行。

## 工具操作

- [MetaXcan官方](https://github.com/hakyimlab/MetaXcan)：按安装版SPrediXcan.py --help，传模型数据库、covariance文件、GWAS目录/匹配模式、SNP与效应列映射、输出路径；多组织使用相应联合模型，不能简单合并P当独立检验。
- [FUSION官方源码](https://github.com/gusevlab/fusion_twas)：准备SNP A1 A2 Z摘要及权重清单，使用FUSION.assoc_test.R，按--sumstats、--weights、--weights_dir、--ref_ld_chr、--chr、--out组织每染色体运行。权重路径相对于用户资源目录，仓库不放权重。
- 显著基因再按官方post-process进行条件/联合分析，或共定位/精细定位，保留多组织和邻近预测表达相关。

保存全量基因-组织结果、权重版本、覆盖比例/实际SNP、预测性能和校正范围。若工具只输出Z/P而不输出可解释效应，不伪造表达单位beta。整合SMR时转其专门输入，不能把TWAS P当作MR效应。

## 可视化与分析

自动画全量基因关联图、组织热图（标明Z/校正P）、权重覆盖和区域条件前后对照；缺失组织显示NA，不填零；多组织校正明确。输出PDF/SVG、600dpi PNG、图表TSV与图注，核对基因/组织标签。结论是遗传预测表达关联；表达相关、LD牵连和共享调控均为替代解释。源头：[Gusev等2016](https://doi.org/10.1038/ng.3506)、[Gamazon等2015](https://doi.org/10.1038/ng.3367)。
