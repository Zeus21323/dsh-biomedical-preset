# 两样本MR：从问题到执行

## 先做研究而不是先找显著结果

用户只给疾病或基因时，用普通语言问“您更想知道什么因素可能增加患病风险，还是想预测谁会患病？目前有自己的样本，还是打算用公开数据？”先检查已给文件，已知事实不重复问。明确暴露、结局、祖源、单位、队列与重叠；核查原研究的调整变量、选择过程和发现/复制角色。三个工具假设为相关性、与混杂独立、排除限制；诊断不能证明后两项。

GWAS Catalog关联列表只用于发现研究/线索；完整汇总数据由用户文件或有权限的官方资源取得。API返回截断、仅显著、未知频率时记录缺口；不把缺失当阴性。不自动下载大型资源或把私人SNP上传外部clumping服务。

## 环境与文件

正式入口需要R、jsonlite、TwoSampleMR；绘图还需ggplot2。通过官方安装文档准备独立版本环境，记录R/sessionInfo及包版本；缺失依赖时停止，不自动安装。所有示例命令在本Skill目录执行，配置与输入/输出路径由智能体填写到用户工作区。文件名示例是契约，不是仓库附带数据。

标准TSV两侧均要求 SNP,BETA,SE,EA,NEA,P；建议 EAF,N。每侧SNP唯一，BETA/SE有限、SE>0、0<P<=1，EA/NEA大写且不同；P下溢先保留MLOG10P并由适配工具处理，不伪造P。BETA为相应EA的效应；OR先取log且SE必须是同尺度。此R入口仅接受双等位SNP，不处理indel/liftover；规范化后仍为indel时必须使用明确支持其表示的原生分支，不能喂给此入口。

读取 assets/mr.config.json，复制到用户工作区后根据真实资料填写。build与祖源必须一致；允许重叠/未知重叠时必须填写局限性，脚本不负责校正重叠。输入完整性必须说明为全量或为已按暴露筛选的工具；結局不再按P筛选。

## 操作顺序

1. 按研究设计冻结工具阈值、LD r²、窗口及理由。弱工具筛选不能只检查平均F；不以“F>10”证明可靠。
2. 在匹配祖源/构建参考做本地clumping。先按暴露P筛选；可用PLINK2原生 --clump、--clump-p1、--clump-r2、--clump-kb，实际字段参数以安装版 --help clump 核验。保存独立工具清单、参考版本、排除原因和命令。多个相关cis工具需LD感知估计，不标记为独立后喂给此入口。
3. 将保留SNP写入无表头单列工具清单；从结局提取这些SNP的效应。代理SNP需保存原/代理ID、相位、LD和频率；未完成代理方向审计的结果不能输入。
4. 执行输入检查和协调：
   `Rscript scripts/run_mr.R --config mr.config.json --step harmonise`
   脚本仅选择清单内工具、调用harmonise_data，保存含mr_keep的完整协调表、排除表和F。
5. 正式估计：
   `Rscript scripts/run_mr.R --config mr.config.json --step estimate`
   每次运行使用新的输出目录；estimate重新从配置输入协调，避免误用旧文件。一个工具使用Wald；两个工具只运行明确适用方法；三个以上也不代表Egger有足够精度。
6. 同时主分析与诊断：
   `Rscript scripts/run_mr.R --config mr.config.json --step all`
   依次保存结果、Q、截距、单SNP和留一法。逐方法状态写入status.tsv，不把NA/失败写成0。方向性检验需先准备性状类型、解释度或样本量等必要信息，按扩展说明运行，当前入口不猜测这些参数。
7. 每个实际结果关联输入校验信息、配置和日志；作图按可视化参考操作。缺数据时可以解释下一步，但不能声称“已支持因果”。

## 解释与扩展

配置primary_method预先声明主要方法，并包含于methods；默认mr_ivw使用TwoSampleMR带欠离散保护的乘法随机效应实现。mr_ivw_fe为固定效应，mr_ivw_mre不做相同欠离散保护，不能混称或从中挑最显著。实际默认参数保存backend_parameters.json，版本保存sessionInfo。单工具按设计改为Wald并保留这一分支记录；主要方法不可估计时只交付标注的敏感性结果，不事后替换主要方法。

敏感方法回答不同偏倚；不数显著方法“投票”。二分类结局可报告exp(beta)及区间，同时说明每什么暴露单位；二分类暴露不直接解释为从无病到有病的干预。反向分析重新挑工具；多变量需要条件强度；靶点需要分子QTL、共定位和测量伪影审查。

## 官方接口与方法来源

- [TwoSampleMR操作](https://mrcieu.github.io/TwoSampleMR/articles/perform_mr.html)、[协调](https://mrcieu.github.io/TwoSampleMR/articles/harmonise.html)、[源码](https://github.com/MRCIEU/TwoSampleMR)。
- Burgess等2013：[汇总工具估计](https://doi.org/10.1002/gepi.21758)；Bowden等2015：[MR-Egger](https://doi.org/10.1093/ije/dyv080)；Bowden等2016：[加权中位数](https://doi.org/10.1002/gepi.21965)。
软件接口和统计方法分别记录，不用软件版本替代论文定义。
