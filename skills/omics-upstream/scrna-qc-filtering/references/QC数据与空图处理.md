# QC数据与空图处理
使用Python 3.12+、numpy、pandas、matplotlib、Pillow；h5ad提取加anndata/scipy。R提取需要jsonlite/SeuratObject。由代理检查对象并填写配置，输出必须是新目录。
## 提取
运行 `python scripts/extract_qc.py --config config.json --out-dir extracted`；RDS用 `Rscript scripts/extract_qc.R --config config.json --out-dir extracted`。路径相对配置所在目录解析。
配置：input、sample_column、stage、columns、units；表输入另有cell_id（默认cell_id），h5ad默认obs_names。columns将detected_genes/total_counts/mitochondrial_percent映射到核验后的实际列。units分别genes/counts/%；只有明确fraction才乘100。不得仅凭最大值推测单位。
Python如需补算可指定counts_layer（X或实际layers键），必须非负整数并且分母非零；mitochondrial_gene_ids是核验后的实际ID集合，annotation_source说明物种、版本和来源。零匹配停止，不把核编码线粒体功能基因加入。R适配器仅提取既有元数据，不重算；缺指标先按分析流程核验补齐，不静默填零。
输出qc.tsv和extraction.json。必需身份/值不可缺；重复样本-细胞身份失败。before/after只能标实际对象阶段；拼接阶段时保留来源，过滤后0细胞单独报告，不伪造分布。
## 绘图
`python scripts/render_qc.py --config figure.json --out-dir figures_new`。
配置必需table、question、caption；可选metrics、sample_order、stage_order、thresholds、font、width_mm、height_mm、dpi。table为QC长表：cell_id/sample_id/stage/metric/value/unit。默认三个指标，缺面板停止；只有部分指标时显式选择metrics并说明缺项。thresholds每项metric/value/reason，必须来自真实规则。
每页最多5样本，阶段最多4；多阶段按样本并列，保持同指标跨阶段/页尺度。箱线使用全数据，散点最多每组200固定种子展示，保留完整源表。少数/常数仍用点与箱线，不强制核密度。每组n为细胞数，不是供体检验。
每页输出PNG/SVG/PDF、完整plot_data.tsv、caption和manifest。无网格但保留依据明确的阈值。所有输出通过scripts/figure_delivery.py，运行记录明确pending目视审查。空表/全缺失、错误对象失败；真实零值有效；不通过调过滤阈值解决空图。

## 代理如何完成输入判断
用户只说“图为什么没有内容”时，先找到这次运行的源对象、绘图脚本和输出文件，核对是否为同一次运行。截图可以判断空框和标签问题，但不能证明某一列必然缺失，也不能恢复隐藏的数值。如果只有截图，先说明已观察到的问题和需要的源文件；不要为演示完整而补造细胞。
输入配置中的文件路径由代理解析，细胞标识和样本字段从文件核验。样本不是供体的同义词；同一供体可有多个样本，不能据不同文件名制造独立重复。过滤阶段必须对应真实源对象，不能把同一张表复制两份并分别命名前后。提取器仅保证已提供字段的技术一致性，样本实际设计仍要核对研究记录。
计数层的指定必须有依据。原始计数通常是非负整数，但整数检查通过并不证明所选层就是本项目所需计数；还需核对对象创建过程。归一化、对数和缩放的结果不能被改名为原始计数。补算只产生新的表和运行记录，不改变原对象，不自动过滤，也不替代空液滴和双细胞等独立质量证据。
指标表可先按阶段分别提取，再依据完整身份和来源合并。必需字段缺失时脚本失败；若研究只需要一种已有指标，代理明确选择单面板并在图注解释缺项，不静默丢弃用户原本要求的其他面板。线粒体列出现零值时核查基因注释匹配；注释正确而计数为零可是真实观察，不能为了画出分布而加伪计数。
图注说明数据来源、实际阶段、每组细胞数、显示抽样和过滤线依据。细胞数变化和指标分布共同用于检查过滤影响，不根据图形是否好看决定保留细胞。输出成功后仍需检查最终字号、组别、百分比刻度、箱线范围和图例；技术检查记录不是人工审图结论。
