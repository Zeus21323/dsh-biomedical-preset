---
name: secreted-protein-activity-inference
description: "当用户问哪种细胞因子可能让另一群细胞发生变化、某分泌蛋白是否解释接收细胞的基因变化，或已有NicheNet/MultiNicheNet活性结果却缺配体排名和靶基因图时使用；结合发送表达、受体与接收响应推断候选。只有疾病或发表愿望时先检查问题与数据，不直接承诺机制。"
---

# 分泌蛋白活性推断

先由智能体检查已有文件并判断是否有接收细胞响应和样本设计，不要求用户认识工具或填写专业参数。缺失且改变设计的事实用普通语言补问；缺少数据时说明需要什么，不编造活性或响应。宽泛研究目标不自动授权上传或大规模下载。

## 定义发送端和接收端

需要细胞类型、供体与条件、发送和接收群、表达矩阵、接收侧差异基因、配体—受体及配体—靶基因网络。先确认比较发生在接收细胞内，而不是由细胞组成变化制造。

## 推断过程

1. 在每个供体或样本内建立接收细胞响应程序，定义合适的表达背景基因。
2. 用 NicheNet 或相似模型按配体解释靶基因程序的能力排序。
3. 过滤发送群不表达的配体、接收群缺少受体或受体复合体不完整的候选。
4. 比较多个供体的方向和排名；有空间数据时增加物理邻近约束。
5. 对高度相关的配体家族保留竞争候选，并列出能区分它们的实验。

## 质量与解释

检查网络版本、每群细胞和供体数、差异基因阈值、组成偏倚和背景选择。活性分数是先验网络与表达的推断，不能代替蛋白分泌量、受体激活或因果实验。

## 交付

已有 NicheNet 结果时，按[绘图输入契约](references/绘图输入契约.md)运行 [render_results.py](scripts/render_results.py)，自动输出活性排名、靶基因潜力热图及可用的表达证据图。该脚本复用原生结果，不执行配体活性推断；从表达开始时仍须按已核验版本运行 NicheNet，不能将绘图成功报告成推断已执行。

输出候选分泌因子、活性分数、支持靶基因、发送/接收群、跨供体一致性和验证优先级。

用户要求完整分析时，完成推断后直接生成配体活性排名图、配体–靶基因热图及发送端配体/接收端受体表达支持图，不停在矩阵或等待第二次绘图指令。已有结果对象先核验并复用。候选按当前响应基因、背景和跨供体支持选择；不能固定复用示例分子，也不能强造不同数据集的差异。有多条件及足够供体时增加供体级效应图，样本不足则保留描述性结果。表达、活性和调控潜力分别标注，不能混称通讯概率。

每图交付 PNG 和 PDF/SVG、源表、绘图代码及图注，实际打开检查。用图集清单记录已生成、不适用或失败及原因；缺少靶基因网络时明确缺失，不以表达热图冒充靶基因推断。没有药敏、临床结局或空间坐标时不仿造相应关联图。

## 原生响应程序执行

多供体多条件且有真实计数时使用 [run_multinichenet.R](scripts/run_multinichenet.R)，要求 multinichenetr 2.1.0 及其完整 Bioconductor 依赖。输入为 SingleCellExperiment，明确 sample_key/donor_key/condition_key/cell_type_key、count_assay、lr_network/ligand_target_matrix 与 network_version；contrasts 的每项为 group 和 reference 条件列表，对比参考均值。重复供体必须进入 covariates 设计；每条件至少3供体，技术重复先按设计处理。它执行原生 sample pseudobulk/edgeR、配体活性和条件优先级并导出结果包；原生优先级不是显著性概率。统一方法入口会接续出图，依赖或设计检查失败时不得改用细胞级检验绕过。

MultiNicheNet还输出分条件/接收群/上调或下调响应的配体活性、靶基因权重及逐供体表达支持；不同响应方向不能合并为同一矩阵单元。已有该脚本产出的原生对象可设置reuse_bundle指向原结果包，核验对象、表达、先验摘要及原生分析参数一致后只重新导出与出图。仅有外部来源未知的RDS不能跳过核验。

有表达矩阵、发送/接收群、明确响应基因集及版本化先验时，运行 [run_nichenet.R](scripts/run_nichenet.R)。它读取基因×细胞 expression 与 metadata 的 RDS、LR 先验和 ligand-target 矩阵，原生执行 NicheNet 活性与靶基因关联，保留对象和来源。配置需包含 dataset/research_question/input/lr_network/ligand_target_matrix/gene_set/gene_set_definition/receiver/network_version/expression_scale；发送群由 senders 指定。依赖 nichenetr 2.2.1.1、jsonlite、digest、Matrix。输出目录必须在 Git 外且不存在。

由主通讯 skill 的多方法入口执行时自动接续结果包绘图；单独执行时发现已安装主通讯组件 `05-single-cell-virtual-cell-b08-t04` 的 render_result_bundle.py 后直接生成配体排序、靶基因热图和机制关联网络，不等用户补绘图指令。未安装时给出明确依赖失败并保留原生对象。方法注册中的 CellCall、MultiNicheNet、FlowSig 等使用各自原生实现与输入要求，不能用 NicheNet 的结果冒充。

FlowSig 分支通过主通讯组件的 run_flowsig.py（固定 flowsig 0.5.5、独立 Python 环境）执行。需要两个真实条件、control、按条件对应的原生 CellChat 结果及实际 GEM；gem_mode=reuse 必须记录上游 GEM 来源，或 gem_mode=native_nmf 从明确 counts 层拟合。它重新构建 inflow/module/outflow 并执行原生 bootstrap、类型约束和边筛选，自动出分层网络、频率热图与逐供体模块载荷。旧 H5AD 中的网络结果不参与本次推断。

FlowSig 使用原生未按细胞总和闭合的 GEM，检查各条件变异和矩阵条件数；默认排除每条件不足10个可辨识变异细胞或相对标准差过低的变量，保存排除记录。进入模型前按全队列每变量一个标准差作数值缩放，绝不逐条件归一化，原始矩阵和缩放值保留。数值警告触发失败，不降低门槛凑图。边频率不是 P，模块间未定向边用无箭头虚线，三供体配对数据也不能把细胞 bootstrap 当成供体层因果验证。macOS 环境需要可用 OpenMP；若 Accelerate 报矩阵运算警告，使用同版本经核验的 OpenBLAS 构建并重跑数值检查，不屏蔽警告。

CellCall 的 LR–TF 原生整合通过主通讯 skill 的稳定 ID `05-single-cell-virtual-cell-b08-t04` 定位该主通讯 Skill 内的 `run_cellcall.R`，由主入口自动执行到图集。具体状态、版本和入口以该 skill 的唯一方法契约为准；CellCallEXT 为独立软件，不能用 CellCall 的 extended 数据库参数代替。LR 分数没有原生联合 P/FDR 时只描述原生正分数筛选；不同单位的 LR 与 TF 权重分开保存，机制图不得混合为统一流量。

## 默认图件交付


分泌蛋白活性推断的现有绘图入口调用[图件交付内核](scripts/figure_delivery.py)，为实际结果保存PNG、SVG、PDF，关闭背景主次网格，保留该分析的数据线与科学参照；逐图查看交付记录和最终预览，失败不得报告成功。
