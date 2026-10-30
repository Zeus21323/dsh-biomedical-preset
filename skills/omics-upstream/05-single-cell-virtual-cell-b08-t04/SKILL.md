---
name: 05-single-cell-virtual-cell-b08-t04
description: "当用户问哪些细胞在互相影响、某基因是否参与细胞间传话、疾病或治疗前后通讯有何变化，或已有单细胞/细胞通讯结果却只有矩阵、缺网络弦图、图太乱或不同数据总出现相同分子时使用；涵盖配体–受体推断、条件比较、结果复用和适用图集。只有疾病、发表或毕业愿望时先识别问题与数据，不直接运行。"
---

# 单细胞细胞通讯分析

## 默认完成范围

用户要求“做细胞通讯分析”即包含分析、重点候选解释和适用图集的生成与检查，不等用户再说“画图”。表达矩阵、RDS/h5ad 和候选表是中间产物。已有通讯对象或候选表时优先复用，经版本、分组和参数核验后直接进入出图；不要无故重新生成表达矩阵。用户明确只要表格、方案或某一种图时遵从其范围。

默认用户不了解生信软件与skill。智能体先检查已有文件和元数据，依据课题选择方法并填写脚本参数；只用普通语言补问文件无法核实且会改变设计的事实，例如“这些样本是否来自同一批患者的治疗前后”。不要求用户指定算法、数据库、表达层或专业参数；只有宽泛发表目标且尚无可用数据时先澄清问题，不编造结果，也不将其视为上传或大规模下载的授权。

执行分析或补图前读取[分析、特异性与图集规范](references/分析与图集规范.md)。使用通用出图程序时再读取[绘图输入契约](references/绘图输入契约.md)。

论文风格出图或用户认为现有图不可用时，读取[期刊图形验收](references/期刊图形验收.md)。绘图程序默认加载 [communication-nature.mplstyle](assets/communication-nature.mplstyle) 并执行物理尺寸与排版配置；已安装外部期刊可视化 skill 时先发现并加载相应指导。出图成功、技术验收通过和实际视觉审查是三个独立状态，不能以测试通过或使用样式名称代替论文图验收。

## 数据与方法

确认物种、问题、细胞类型/亚群、样本与供体、条件/配对关系、每群细胞数、表达层和配体–受体数据库版本。先检查是否有足够细胞和完整受体复合体；原始计数与合适标准化表达按所选工具要求使用，不直接套整合后含负值的矩阵。

- 单数据集常规网络可用 CellChat；多方法排序可用 LIANA；受体复合体与细胞类型特异性检验可用 CellPhoneDB。分数不可互换，记录具体方法、版本和含义。
- 条件比较先在样本内推断，再按供体进行符合设计的比较；有接收端响应程序时可增加 NicheNet/MultiNicheNet 证据。池化对象只能提供描述性网络，不能冒充供体重复。
- 方法、数据库、细胞标签或参数不一致的历史结果先分别展示，未协调前不画定量差异图。保留未检验、未检测和检验不支持的区别。
- 空间位置、蛋白或扰动数据用于增强证据。共表达支持候选假设，不能证明分泌、结合或下游激活。

## 多方法执行与已有结果复用

用户指定其他通讯算法、多方法一致性、模式分解或历史对话中的方法时，读取[方法与执行契约](references/方法与执行契约.json)及[多方法执行与结果包](references/多方法执行与结果包.md)。方法注册覆盖历史、常规、响应、差异、模式、动态、代谢、神经与空间分支；按实际 runner 判断能否原生执行，不能把已收录当作已实现。

当用户点名 DLRP/autocrine-loop、Community Molecular Network、CCCExplorer、CCCvelo、FineST、PyMINEr、DeepCCI 或 GraphComm 时，再读取[待执行方法核验](references/待执行方法核验.json)。这些方法的算法步骤和预期图型已经收录，但仍缺软件发布、许可、作者输入、外部服务或完整 capsule 中的一项；用 [audit_communication_method.py](scripts/audit_communication_method.py) 在 Git 外生成当前源码与就绪报告。报告返回“尚不可执行”不能算分析失败后自动换算法，也不能把 SpatialDM、scVelo、任意 GNN 或通用网络图换标签交付。若后续材料解除全部登记条件，先完成真实数据数值、复跑和逐图验收，再同时增加专用 runner 和修改注册状态。

有适用数据时由 [run_method_workflow.py](scripts/run_method_workflow.py) 连续调用 [LIANA+](scripts/run_liana.py)、[CellPhoneDB](scripts/run_cellphonedb.py)、[FastCCC](scripts/run_fastccc.py)、[Tensor-cell2cell](scripts/run_tensor.py)、[SpatialDM](scripts/run_spatialdm.py) 、[MEBOCOST](scripts/run_mebocost.py)、[NeuronChat](scripts/run_neuronchat.R) 或 [COMMOT](scripts/run_commot.py)，相关领域解释仍交给对应 skill；这些分支通过 `run_communication.py` 的 methods 配置统一进入。R NicheNet 按已安装的分泌蛋白活性 skill 定位，不能假定其必然存在。

表达输入由 [communication_inputs.py](scripts/communication_inputs.py) 验证，结果表由 [communication_contract.py](scripts/communication_contract.py) 验证；[communication_figure_plan.py](scripts/communication_figure_plan.py) 在绘图开始建立22图族覆盖记录，逐图挂接实际结果与生成状态；没有结果不能直接认定数据不适用，图族已有一张图也不代表全部子类型完成。结果包直接调用 [render_result_bundle.py](scripts/render_result_bundle.py) 生成所有类型适用图、PDF 图集与 manifest。已有结果包使用 bundle 复用分支，直接重绘。不要因当前运行时缺依赖无声跳过方法；准备对应版本环境，仍无法执行时保留具体失败。

接收端信号模型由 [run_flowsig.py](scripts/run_flowsig.py) 执行原生 FlowSig、[flow_numerics.py](scripts/flow_numerics.py) 检查模型变异资格；原生 CellCall 使用 [run_cellcall.R](scripts/run_cellcall.R)，递质/肽信号使用 [run_scconnect.py](scripts/run_scconnect.py)。先核对方法契约中的实际验证状态，不能把尚未验证的分支写成已验收。CellCall 的 extended 数据库选项不能冒充独立 CellCallEXT；两端特异性检验不能冒充 LR 联合检验。SpaTalk 通过空间 skill 的稳定 ID 定位其脚本，缺坐标不运行空间模型。

有真实通路身份和可加分数时，结果绘图器调用 [communication_sankey.py](scripts/communication_sankey.py) 自动生成三层桑基图和细胞/通路分组双环 Circos，记录显示子图及所占总分。缺少通路映射不能用参考图中的通路补齐。

独立 CellCallEXT 使用 [run_cellcallext.R](scripts/run_cellcallext.R)，核实真实 case/control 条件、表达层和原生细胞池化的适用范围。需要建立专用运行环境时，[install_cellcallext.py](scripts/install_cellcallext.py) 仅接受固定上游归档，为已失效的绘图导入提供审计补丁，保留原生评分源码；环境、源码和安装记录都写入 Git 外指定目录。不能随机赋予病例对照标签，也不能把该原生池化模型冒充供体条件检验。

## 连续生成图集

CellChat 完整任务或补图先读[原生执行契约](references/原生执行契约.md)，运行 [run_communication.py](scripts/run_communication.py)。它连续调用 [run_cellchat.R](scripts/run_cellchat.R) 完成逐样本推断/对象复用及原生图集；需要供体比较时使用 [compare_communication.py](scripts/compare_communication.py)，有现成坐标、功能评分或临床数据时使用 [render_context.py](scripts/render_context.py)。这些是确定性生产实现，不能用临时表达热图替代。R依赖缺失时按契约准备环境；确实无法执行则保留失败记录，不宣称已运行。

分析结束后直接生成：总体数量/强度网络、发送–接收热图、LR 气泡图、数据驱动的重点发送者网络、重点通路网络与弦图、发送/接收角色图、LR 数量汇总图。细胞或通路过多时按重点分面并保留完整表，不能用一张表达热图代替通讯图集。

优先用已安装并核验版本的原生方法绘图函数。需要稳定的通用图集时，将真实推断结果和每样本可检验的细胞对按输入契约导出，运行 [render_communication.py](scripts/render_communication.py)。它一次生成上述描述性图集的 PNG、PDF、SVG、源表、选择记录及 manifest；它不从表达矩阵推断通讯，也不计算条件差异显著性。缺少程序依赖时按项目环境安装并继续，无法运行则报告具体失败和已有产物，不声称完成。

不要把所有数据集的 COL(L)AGEN、THBS、MK 等常见通路作为固定重点。围绕本次研究问题保留亚群标签，分别给出本数据的候选、跨样本支持及证据限制；相同候选可以是真实共性，不能强造特异性。无用户指定焦点时程序的自动焦点仅是探索性起点，需按规范复核并解释。

## 条件图与交付验收

通用结果包内有实际供体/条件和相同原生推断参数时，调用 [run_bundle_contrasts.py](scripts/run_bundle_contrasts.py)；多方法配置在对应 method 项设置 comparison 后会自动接续，无需用户再发出图指令。它对完整可检验候选进行供体置换及BH，输出效应与全候选火山图、供体分布和删一供体效应敏感性；少于3供体不检验，配对仅用完整供体对，协变量设计转到适用的原生模型。排名比较明确使用1−rank，不解释为概率或物理强度。

有事先定义的候选/接收端响应基因、可检测背景与版本化GMT基因集时，运行 [run_gene_set_enrichment.py](scripts/run_gene_set_enrichment.py) 生成过度代表分析点图和热图。配置显式声明选择与背景来源；背景外候选拒绝执行，BH涵盖全部组×合格集合，包括零重叠。不能用全基因组自动替代接收端表达背景，也不把已有富集结果再次计算成另一种P值。

多个方法已分析同一实际输入时，运行 [compare_method_support.py](scripts/compare_method_support.py)，配置 bundles 指向真实结果包，逐样本自动生成共同可检验覆盖、支持集合 Jaccard 与秩相关图。它保留各方法支持定义，不混加分数；没有共同支持或分数为常数时明确不可估计。缺少实际输入摘要或 LR 身份存在歧义时先协调来源，不编造方法一致性。

CellPhoneDB/FastCCC 原生身份通过 [communication_identities.py](scripts/communication_identities.py) 按实际数据库映射基因与完整复合物，保留原始名字、方向及代理类型；不按连字符猜亚基，不让同名但成分不同的受体参与一致性计算。

有条件/亚群比较时继续生成相同尺度的分面网络、供体级点图及有有效统计结果的效应图；有现成 embedding 时增加 UMAP 定位，有定义明确的基因集时运行 [run_functional_scores.R](scripts/run_functional_scores.R) 的原生UCell分支（匹配物种的GMT、expression/metadata RDS、覆盖门槛与max_rank；把这些配置放入总任务的 `functional_scores` 字段，即可同次执行、汇总和出图），由真实细胞分数生成样本和供体汇总图，有药敏/临床资料时才增加相应关联图。缺少其中一种输入不阻塞其余适用图，不虚构评分、药敏标签、P 值或参考图中的分子结论。

交付前实际打开最终图片检查重叠、裁切、图例、箭头、跨图颜色和尺度；检查图与源表数值一致。保留完整候选表、参数/数据库版本、代码、源对象、筛选记录、图注和矢量图。逐类记录 `generated`、`not_applicable` 或 `failed` 及原因；缺输入不算成功生成，绘图失败必须修复或明确报告部分完成。零候选时输出真实空结果与过滤统计，不降阈值凑图。

审图使用宿主当前已提供的工具，先核验实际参数和本地文件读取能力；不要把本地路径塞入仅接收HTTP地址的image_url，也不依赖新增宿主接口。实现范围限于plugin仓库，不修改SpeedClaw代码、工具协议或已安装程序。宿主无法读取本地图片时继续交付图件、源表和技术检查结果，并明确视觉审查尚未完成；不为绕过限制自动上传图片，不以技术检查替代目视确认。结果manifest记录实际应用的样式摘要；外部Nature相关skill是否加载以编排日志为准，不能仅从样式文件名推断。

## 默认图件交付
所有正式单图、组合图和补充图默认PNG、SVG、PDF同时输出；图集不能替代每图PDF。关闭背景主次网格，保留通讯边、区间和科学参照线。每图导出记录三格式哈希和尺寸；任一失败明确partial，不以已有PNG宣称完成。组图重新检查字体、布局、裁切和页框，回复展示PNG并直接链接PDF/SVG、源表及图注。

单细胞细胞通讯分析的现有绘图入口调用[图件交付内核](scripts/figure_delivery.py)，为实际结果保存PNG、SVG、PDF，关闭背景主次网格，保留该分析的数据线与科学参照；逐图查看交付记录和最终预览，失败不得报告成功。

原生 NATMI 使用 [run_natmi.py](scripts/run_natmi.py)，原生 SingleCellSignalR v1 使用 [run_singlecellsignalr.R](scripts/run_singlecellsignalr.R)，均由统一入口自动接续图集。前者核验固定源码并分开导出表达权重与特异性权重，后者保留自分泌/旁分泌分类和原生LRscore。方法契约决定当前可执行/验证状态，不能用LIANA内部重实现冒称这些原生完整执行。

有真实组织坐标时，[run_squidpy.py](scripts/run_squidpy.py) 分别执行原生LR置换和邻域富集，统一入口自动出图；需要固定的物种匹配单基因LR资源、表达归一化说明与坐标来源。LR模块不使用坐标，邻域Z不转成P值，无向邻接边不画通讯箭头。缺少完整复合物支持时不能使用最小可见亚基冒充完整受体。

需要比较“只看表达”与“加入空间邻接后”的候选秩时，使用 [run_giotto.R](scripts/run_giotto.R) 的固定 Giotto v1.1.0 分支。输入必须同时含真实整数 counts、逐细胞 sample/donor/condition/cell_type 和对齐的二维或三维坐标；每个样本独立归一化、建 Delaunay 邻域并运行表达标签置换与空间同群组成抽样。自动交付两套完整 LR 表、空间细胞类型图、无向邻域图、配对秩图和恢复曲线。Giotto 的 P 是差值正负号比例，并会把约 1e-16 的名义并列当正差；原生值必须照实保留，但不能仅凭其 P/q 声称空间特异通讯或供体层显著。

需要定位组织切片中具体 LR 热点并汇总其细胞类型关联时，使用 [run_stlearn.py](scripts/run_stlearn.py) 的固定 stLearn V1.4.1 SCTP/CCI 分支。输入必须含逐位置 sample/donor/condition/cell_type、真实二维空间坐标、坐标单位与来源、距离及依据，并明确表达是总量归一化还是总量归一化后 log1p；当前 V1.4.1 教程推荐不做 log1p，只有复核旧发布对象时才按其可核实来源使用 log1p。可使用离散标签或与位置逐行严格对齐的细胞混合比例。运行后自动交付完整 LR 汇总、spot 分数/q 值地图、配体到受体的空间边、细胞类型行列计数与稳定性、热图、网络、弦图和论文概览。spot 层 BH 只在每个位置的受检 LR 内校正；CCI 经验 P 无伪计数且不做多重校正。上游 Numba 并行置换在固定 seed 下仍可能变化，所以默认重复至少三次并以稳定支持率筛选；细胞类型矩阵的行列是热点位置与邻域角色，不能画成分子发送者→接收者，也不能替代供体条件统计。

需要在单细胞分辨率空间数据中寻找具体细胞间的 LR 最优传输边时，使用 [run_scotia.py](scripts/run_scotia.py) 的固定 SCOTIA 1.0.0 分支。输入必须是整数 counts、真实微米坐标、sample/FOV/donor/condition/cell_type 和固定版本的同物种 LR；像素坐标先按可核实比例换算，不能直接套用 50 μm 默认距离。入口自动运行原生 DBSCAN/forest-fire 聚类一致性、邻近簇筛选、非平衡 OT、post_ot 和教程的坐标抖动加表达行置换，直接交付细胞类型/聚类空间图、eps 与聚类资格热图、LR 气泡/网络/弦图、观测-null 图、逐轮置换图和细胞级有向 OT 边。原生一键函数只含聚类和 OT，置换必须由适配器按作者教程衔接；P 是 `null>observed` 的比例，无伪计数，某轮少于 8 条保留细胞边而缺失的候选按作者逻辑记 0。默认另在每个样本与有向细胞类型对内跨 LR 做 BH；所有结论仍是样本/FOV 内细胞模式，不是供体条件差异。

需要对含混合细胞比例的空间转录组切片同时做全局、指定区域和具体 LR 局部热点时，使用 [run_spacci.R](scripts/run_spacci.R) 的固定 SpaCCI 1.0.3 分支。输入 RDS 需含归一化 `expression`、spot 级 `metadata`、真实 `coordinates` 和行和接近 1 的 `cell_proportions`；区域分析需有已定义的区域标签，局部分析需从课题或先验中明确 LR，不根据出图效果临时挑分子。入口运行原生 NNLS、复合物几何均值、15近邻空间过滤和三种置换，一次生成完整结果表、气泡图、热图、网络图、弦图、论文概览、区域成员图以及局部强度与 BH 证据图。SpaCCI 上游在三个分支中都把已计算的 BH 覆盖成原始 P，适配器保留原生字段并另行重算每 LR 和每样本/尺度的 BH，默认用后者判定支持。局部少于 500 个 spot 时原生只做 1 次置换，论文级入口直接失败。这些置换都是切片内统计，不会产生供体条件特异性。

已有空间单细胞 RNA、seqFISH 或成像蛋白数据，问题是“哪些分子变化主要与周围细胞状态有关”而没有明确 LR 假设时，使用 [run_svca.py](scripts/run_svca.py) 的固定 SVCA 0.0.1 + limix 0.8.5 分支。输入 h5ad 需有逐细胞连续表达/蛋白丰度、sample/donor/condition、真实二维坐标及其单位和来源；每个图像独立拟合，特征过多时按检测面板或事先研究问题限定，不能为了得到想要的分子临时筛选。入口自动交付原始四方差分量、行和为1的方差签名、交互分量供体点图、原生长度尺度网格和选择尺度、按交互份额排序的输入空间背景图，以及堆叠图、小提琴/箱线图、分子分组图和热图；显式开启作者的嵌套折外预测后，再生成保留负值的 R² 汇总和热图。这里的 Cell-cell interactions 是空间局部化的分子状态相似性核，不会给出配体、受体、发送群、接收群、局部作用位置或 P 值，因此不生成 LR 气泡、弦图和显著性结论。

已有空间单细胞、成像蛋白或分割细胞数据，问题是“某类细胞周围出现另一类细胞时，接收细胞的哪些基因或蛋白会改变”，使用 [run_ncem.py](scripts/run_ncem.py) 的固定 NCEM 0.1.5 线性细胞分辨率分支。输入 h5ad 需有逐细胞分子值、sample/donor/condition、细胞类型、真实二维坐标及单位和来源；每个 sample 内按有依据的固定半径建图，绝不跨图像连边。入口自动交付全部接收类型×邻域发送类型×基因/蛋白系数及原生 Wald P、对齐的全候选 BH q、每个重点接收群的有符号系数热图/BH 证据热图/发送类型相似性图、支持特征数网络和弦图、供体图度数质控与输入细胞类型空间图。NCEM 检验的是邻域细胞类型与接收细胞分子状态的统计关联，不识别具体配体–受体，也不把弦宽解释成分子流。上游 0.1.5 的校正值重排与标签错位时，`native_q_value` 原样保留，正式支持判定使用完整原生 P 表上重新对齐的全局 BH。`differential` 只能在每条件至少两个真实供体且显式承认原生检验仍以细胞为观察单位时运行；结果不能冒充供体层疾病或治疗特异性。当前入口不声称执行 neural、deconvoluted spot 或 spline NCEM。

已有空间单细胞或高分辨率空间 RNA 数据，问题是“哪些已知基因程序共同定义空间 niche、这些程序在什么位置活跃、哪些细胞类型之间出现该程序的相对通讯潜力”，使用 [run_nichecompass.py](scripts/run_nichecompass.py) 的固定 NicheCompass 0.3.3 RNA-only GCN 分支。智能体先检查原始整数 counts、用于通讯解释的非负表达层、sample/donor/condition/cell_type、真实二维坐标和有来源及摘要的 gene-program JSON；不在运行时下载不明版本数据库。训练图和通讯图均在每个 sample 内独立建立，publication 层至少运行3个固定种子和100个 epoch。一次运行自动交付逐 epoch 损失、边重建与 RNA 重建验证指标、可重载原生模型、全部 GP decoder 权重、细胞类型平均 GP 活性、latent UMAP、物理空间 niche、逐 GP source/target potential 图、逐 GP 网络/弦图、GP 跨种子相关和 niche ARI。网络值由作者函数在每个 GP 与 sample 内单独 min-max 至0–1并四舍五入为2位，只表示同一图内相对强弱，不能跨 GP、样本或数据集比较或相加；GP latent、niche 和边没有 P/FDR，也不等于分子流、供体条件特异或因果机制。负的种子相关、无正边的 GP 和单样本限制必须保留。当前入口不声称执行 ATAC、reference mapping、addon GP 或自动构建全量 OmniPath/NicheNet/MEBOCOST 资源。

已有一个细胞或 spot 分辨率的空间切片，问题是“哪些配体—受体空间网络与某个目标基因的组织内表达相关、通信信息能否比细胞类型基线提供额外预测”，使用 [run_holonet.py](scripts/run_holonet.py) 的固定 HoloNet 原生 CE/FCE 分支。智能体先核实唯一细胞和基因、一个空间切片、非负表达层、细胞类型、真实二维坐标、预先声明的目标基因、距离尺度和带来源及 SHA-256 的单基因 pairwise LR 表；目标基因不能与已用 LR 基因重叠。入口在构建稠密 LR×cell×cell 张量前检查规模，发现不规则坐标使上游接触邻接仅覆盖少量细胞时失败并要求明确关闭距离分类。publication 层至少运行50次初始化和300个 epoch，一次运行自动交付距离核、全部 LR 资格与 CE 质控、重点 LR 的发送/接收/总度数和特征向量中心性空间图、细胞级边、细胞类型 CE 网络、LR UMAP/树状图/簇热点、逐目标实测与预测空间图、细胞类型基线对照、留出细胞表现、完整 attention 重复稳定性、目标特异 FCE 网络、delta-E、单 LR 视图及预声明 pathway 面板。随机拆分发生在同一切片细胞层，不能消除空间相关或替代供体复制；原生过滤不提供逐 LR 或逐边 P/q；attention、CE 与 FCE 各自在上游函数中缩放，不能跨 LR、目标、样本或数据集解释为共同尺度。当前入口只执行单基因 pairwise 分支，不把资源目录中的复合物、激动/拮抗或共受体条目包装成已支持结果。

已有一个细胞分辨率空间切片，问题是“某类发送细胞中预先关注的信号基因或基因集，是否与附近某类接收细胞的响应状态相关，以及具体哪些发送—接收细胞对更可能承担这种关系”，使用 [run_spacia.py](scripts/run_spacia.py) 的固定 Spacia Bayesian multiple-instance learning 分支。智能体先检查唯一细胞/基因、一个切片、非负表达、完整细胞类型、真实二维坐标、发送群、接收群、明确的 signal/response 特征和有生物依据的距离阈值；没有物理标定时只保留 native 单位。默认使用显式单基因或显式多基因集合，不自动把相关基因扩入特征；如确需相关聚合，必须说明它会改变跨数据集可比性。同一发送/接收群会让上游把自身细胞纳入距离0候选，只有明确的自分泌问题才允许；合格 receiver bag 超过上限时不得静默随机抽样。publication 层至少采用作者默认的50000总迭代、25000 warmup、10倍 thinning 和3条链。一次运行自动交付细胞类型空间底图、每个实际建模接收 bag 的发送细胞覆盖、逐 response 全部 primary-instance 空间边和接收热点、response×signal 有符号 beta 与 posterior quantiles、距离 b.2 posterior 图、0.1–0.9 Bayesian FDR 曲线、beta PSRF 和逐链 trace，并保留完整上游输出、标准化输入和运行日志。primary-instance score 对 response 特异但不是某个 signal 的细胞边分数；上游多链汇总存在 initializer 边界错位且 P/q 把 posterior draws 当作观察值，因此 P/q 只保留于原生文件，不进入图或支持判断；零选择对象时的 FDR 保持缺失。单切片结果不能证明条件、疾病或数据集特异性，也不能当作配体结合或因果机制。

已有一个细胞分辨率空间切片，问题是“哪些相邻细胞之间的配体—受体边在图注意力模型中稳定靠前、哪些细胞类型更偏发送或接收、是否存在反复出现的两跳分子接力”，使用 [run_cellnest.py](scripts/run_cellnest.py) 的固定 CellNEST 分支；无100模式下限的同定义 relay 枚举由 [cellnest_relay.py](scripts/cellnest_relay.py) 提供。智能体先检查唯一细胞和基因、原始整数 counts、完整细胞类型、一个切片、真实二维坐标、明确坐标单位与固定 LR 数据库摘要；运行器将身份转为不泄露原始标签的内部编号，并保留可追溯映射。当前只开放经核实的 kNN 图并强制阻断自环，因为固定上游的 radius 分支实际调用 kNN，而 GAT 会移除 LR 自环特征后加入普通自环。publication 层至少运行5个独立种子、每次60,000 epoch，并采用作者 top 20% 与跨种子/跨层 rank-product。一次运行自动交付空间细胞类型图、图资格审计、全部入选细胞级空间边、接收热点、细胞类型网络和收发角色、逐 LR 候选/入选证据、最常见 LR 空间边、强通讯空间连通分量、跨种子 attention 稳定性、截至各次实际保存 checkpoint 的训练 loss、完整 attention 分布与选择边界、全部两跳 relay 计数、前列 relay 的三位置细胞类型构成与空间两跳边，以及可用时的固定 PPI×GRN 先验置信。attention 是当前图内缩放的模型分数，不是概率或跨数据集效应量；relay 是图结构假设，不证明时间顺序、受体激活或第二个配体由中继细胞分泌。固定提交的可选 P 值和置信区间脚本存在执行缺陷，不进入结果；单切片也不能证明条件、疾病、供体或数据集特异性。

已有空间单细胞或空间 spot 数据、匹配参考细胞类型、spot 细胞组成以及有版本来源的 ligand–target 和 ligand–receptor 资源，问题是“哪些配体到靶基因的关联在空间邻域中活跃、形成什么组织域和分子程序”，使用 [run_renoir.py](scripts/run_renoir.py) 的固定 Renoir 1.0.0 分支。智能体核实表达尺度、参考组成、资源摘要、真实坐标与预先确定的 radius 或 Visium 六边形邻域；每次只处理一个切片。一次运行自动交付输入与图资格审计、全部 ligand→target 分数汇总、前列空间热点、原生 Leiden 活性域、域×分子矩阵、域内 Wilcoxon/非零比例证据、de novo 程序域热图和空间图、score-space UMAP 以及零表达保护的多种子稳定性。Renoir 输出是 ISM×PEM 的空间邻域活性，不是发送细胞→接收细胞概率；分数按当前图极值缩放，没有原生边级 P/FDR 或供体条件检验，跨数据集不能直接相减。正式条件特异性需要相同平台、基因与资源范围、独立供体、预设分子集合和供体层复现。

已有细胞分辨率空间转录组，问题是“稀疏表达中哪些已知配体—受体在空间图平滑后的基因表征中仍然接近，以及这些候选在什么细胞类型和位置表达”，使用 [run_spaci.py](scripts/run_spaci.py) 的固定 spaCI 1.0.0 分支。智能体先核实唯一细胞/基因、非负表达、完整细胞类型、真实二维坐标、表达尺度和固定 LR 资源摘要；原始资源中的大小写和重复项按明确规则规范化，原文件和摘要仍保留。入口按发布版规则构建高相关/低相关基因三元组与含自身的对称5近邻图，运行原生 TripletGraphModel，一次交付全部候选 LR 余弦与原始相关、阈值调用、逐轮 loss/F1、表达衍生验证混淆指标、阈值敏感性、候选基因潜在空间、空间邻接、前列 LR 两端表达图，以及论文定义的细胞类型 LR 强度、热图、网络、弦图、角色和概览。该强度是去掉各细胞类型中配体和受体两端各10%极值后的平均表达乘积，再对已调用 LR 求和；它不是逐细胞边概率。发布源码把 seed 固定为10、没有 P/FDR、依赖声明内部冲突，且论文称 attention 但代码只有无归一化图线性层；这些缺口随结果保留。大量候选在低阈值同时入选、单切片或不同平台各自出现不同分子时，只能报告低区分度和候选空间差异，不能调阈值凑特异性或声称疾病机制；正式跨数据集比较需固定 LR 交集、表达处理、邻域规则和阈值，在独立供体上比较预设候选的复现方向。

需要从空间位置和表达继续追踪“哪条配体—受体可能经哪个 TF 关联到接收细胞靶基因”，使用 [run_stmlnet.R](scripts/run_stmlnet.R) 的固定 stMLnet 0.1.2 分支。输入需含归一化非负表达、逐细胞 sample/donor/condition/cell_type、严格对齐的真实二维坐标，以及按细胞类型列出的 ligand、receptor、target 候选及其来源和选择规则。入口固定作者 stMLnetDB，在 RecTF 分数严格高于98%分位后逐步运行原生多层网络、1/d 距离加权 LR 活性和 ranger 随机森林，自动交付接收细胞 LR 活性、细胞群计数/强度网络、弦图、Ligand→Receptor→TF→Target 分层图、LR—靶基因和配体/受体重要性热图与瀑布图、OOB 质量、反馈环、细胞类型空间图、前列 LR 空间活性以及坐标尺度敏感性。发布版总入口和自动候选函数存在未定义变量与字段名错误，因此适配器按官方教程顺序编排已核验组件并要求显式候选，不伪称运行损坏分支。活性没有距离截止且把距离小于1设为1，绝对值会受坐标尺度、发送细胞数和密度影响；随机森林 OOB 仍来自同一切片，重要性没有 P 值，反馈环是先验路径结构匹配。没有独立供体时不得解释为疾病特异通讯、实验因果或跨数据集可直接比较的分子强度。

已有两种明确细胞类型的单细胞表达矩阵，问题是“同一发送类型和接收类型内部是否存在彼此配对的通讯亚群”，使用 [run_cscp.py](scripts/run_cscp.py) 的固定 CSCP 分支。输入是两张基因×细胞、有限非负且细胞身份互斥的矩阵和物种匹配的单基因 ligand–receptor 表；需声明表达尺度、归一化、两类细胞名称以及输入和资源来源。入口核验固定源码提交与依赖，按作者流程运行每侧 NMF 初始化搜索、LR 拉普拉斯约束的 coupled-NMF、5次重启共同聚类和固定层次聚类；5次未全部成功即失败。一次运行自动交付597细胞的完整亚群分配、完整共同聚类矩阵、配对亚群规模、重启 ARI、每个配对亚群的 LR 双端点均值乘积、热图、LR 点图、网络、弦图和论文概览，并保留重算所需的原生数组。LR乘积没有 P/FDR，亚群标签不是全部细胞类型通讯网络；重启不稳定须原样展示，不能挑选较一致的4次结果。作者固定仓库没有声明许可证，因此入口只编排用户另行取得的外部源码，不复制源码或示例数据。单样本不能支持条件、疾病或数据集特异性；正式比较须在相同可测基因和LR交集、相同表达变换及预设亚群数下按独立供体分别运行，再用标签不变的亚群特征或匹配策略比较，不能直接比较任意编号的 Pair 1/2。

已有非负单细胞表达、完全同序的细胞类型标签和与表达基因同序的外部 GRN，问题是“能否不依赖预设 LR、从 GRN 与表达矩阵分解得到细胞到细胞及细胞类型到细胞类型的方向分数”，使用 [run_mdic3.py](scripts/run_mdic3.py) 的固定 MDIC3 外部 GRN 分支。入口核验固定源码和 Python 3.9.18 环境，执行作者 `MDIC3.py`，自动交付完整细胞矩阵、原生 `log10` 群矩阵、可加的群原始总量网络、收发角色、预声明规则选择的细胞子矩阵、数值审计、层级图、弦图和热图。可选的 `MDIC3_LR.py` 后处理只对用户事先指定的细胞类型方向运行，并同时给出原生结果与透明诊断：固定源码分别排序两群细胞的表达后相关，观察并非配对；复合受体错误地列表拼接，等价于只用第一亚基除以2；Bonferroni只在raw-P≤0.05子集内执行。诊断改为复合亚基逐细胞均值并对全部实测候选校正，但仍只称算法筛选，不作为供体统计。作者固定仓库未声明许可，Plugin不复制上游代码或数据；GNIPLR自产GRN分支尚未验收。MDIC3伪逆对数值平台敏感，分数强烈受细胞数和GRN来源影响，不能跨数据集直接比较或据单样本声称疾病特异性。

同时有同一生物样本的原始整数单细胞计数和空间转录组 spot 计数，问题是“这些单细胞可能分布到哪些空间位置、哪些细胞更可能共定位，以及共定位细胞对中哪些配体伴随下游靶活性”，使用 [run_deepcolor.py](scripts/run_deepcolor.py) 的固定 DeepCOLOR 0.0.6 分支。入口要求两种模态基因完全同序、真实 spot 坐标和来源，固定随机种子与兼容环境，执行作者两阶段 VAE 映射、原生 `log2(p_i·p_j)+log2(n_spots)` 共定位、可选高共定位双细胞聚类和 NicheNet 配体—靶基因 coactivity。一次运行自动保留完整映射/共定位/潜在数组、mapped h5ad、训练日志，并生成各细胞类型空间权重、共定位矩阵、固定阈值网络、映射质量分布、训练曲线、双细胞 UMAP/簇组成及配体活动图。DeepCOLOR 推断的是 spot 概率与调控配体活动，不是直接观测的单细胞坐标或配体—受体结合；没有供体重复时不得称疾病、治疗或数据集特异性。作者教程 h5ad 与配体矩阵链接失效时，必须用有来源的替代输入并标明只是适配器验收，不能声称复现作者预处理。

已有非负单细胞或空间单细胞表达、细胞类型、样本身份和物种匹配 LR 表，问题是“考虑发送群配体、接收细胞受体和可选距离后，哪些群对与 LR 的基础 ABM 得分较高、哪些细胞接收总分较高”，使用 [run_cellagentchat.py](scripts/run_cellagentchat.py) 的固定 CellAgentChat 0.2.0 分支。空间模式还要求真实逐细胞二维/三维坐标、单位与来源；入口同时提供上游显示所需的0–100网格坐标和计算所需的未缩放坐标，并在上游静默关闭距离时硬失败。正式机制运行应提供有来源的逐受体 conversion rate；`unit_base_abm` 只有显式确认后才能用于基础链验收，不能称为神经网络 conversion-rate 推断。一次运行自动生成完整LR气泡图、群对强度网络/弦图、Bonferroni支持计数矩阵、Gamma背景参数、逐类型接收分数、空间接收图和诊断，并保留完整逐细胞源表。原生背景打乱细胞类型而不是独立供体，单样本、全1速率或零支持结果都不得包装为疾病特异性或因果机制。当前 runner 不声称执行依赖 torch-sparse 的神经转换率、连续动态和交互动画分支。

已有同一条件中多个独立供体、且每个供体都覆盖相同细胞类型的表达数据，问题是“哪些配体—受体在供体间仍保留条件相关，以及它们形成哪些分子社区”，使用 [run_remi.R](scripts/run_remi.R) 的固定 REMI 分支。单细胞输入会先按供体×细胞类型求均值；已聚合 bulk 输入要求每个供体×细胞类型恰有一个表达谱。多条件输入必须先选一个条件，至少保留6个完整独立供体；超过8类细胞会产生平方级 LR 扩张，需明确接受运行规模。入口固定作者 LR/PPI/基因集和兼容 igraph 2.0.3，执行原生低表达分箱、Louvain 社区与 LR 先验约束图形 Lasso，一次交付有符号 LR 点图、细胞类型网络/弦图、收发权重、边数、社区组成和诊断；完整逐节点社区归属和未过滤 interactome 另表保留。`weight` 是有符号条件相关，不是分子流量或因果激活；主流程没有全边 P/FDR，单队列网络也不是疾病或数据集特异性。源码 DESCRIPTION 仍是许可证模板占位，Plugin 只调用用户另行取得的外部固定源码，不复制 REMI 代码或数据。

使用 [run_italk.R](scripts/run_italk.R) 或 [run_icellnet.R](scripts/run_icellnet.R) 时，由共用的 [native_expression_context.R](scripts/native_expression_context.R) 校验 expression/metadata RDS、归一化定义、人类物种和样本身份，并记录原生对象复用摘要。iTALK 输出原生高表达候选及双端点均值，没有联合LR显著性；ICELLNET 需要固定的完整v2数据库，缩放包含全部亚基，缺失亚基不计支持。

使用 [run_scdiffcom.R](scripts/run_scdiffcom.R) 时，需要已有Seurat归一化data层、两个真实条件和明确细胞池化统计单位。原生细胞置换不代替供体配对/协变量模型；输出完整候选、原生差异/调控标签与CCI类别过度代表分析。复用分支核验输入、原生资源、参数与对象摘要；是否已验证以方法契约为准。

使用 [run_scseqcomm.R](scripts/run_scseqcomm.R) 时，`within_sample` 模式分别运行实际样本的LR与胞内响应，`differential` 模式需要已核实的独立样本设计、两条件及至少每组4样本。S_inter、S_intra与下游关系分开解释，不能混为一个分数；差异分支不支持配对和协变量。原生资源、对象、全候选、样本列映射和数值定义均随结果保留。

使用 [run_celltalker.R](scripts/run_celltalker.R) 时，需要同时保留真实counts和已有归一化expression、样本元数据，以及总counts上下限的依据。原生随机化对象是细胞类型组合；输出端点均值、原生P、追加BH和退化null资格，不冒充供体条件差异。

资源下载使用 [fetch_communication_resources.py](scripts/fetch_communication_resources.py)，按九类登记资源的已核实版本、HTTPS文件清单、SHA-256、物种、标识、相互作用类型、复合物语义和许可证保存至Git外。随后 [validate_communication_resources.py](scripts/validate_communication_resources.py) 检查原生表头、归档成员、SQLite结构或二进制摘要；其成功仅表示文件完整性，RDS/权重等仍需固定原生读取器核验。不得把无已知摘要的“最新版”直接交给分析。

[run_connectome.R](scripts/run_connectome.R) 使用原生Connectome计算表达权重与端点z/表达比例筛选。和 [run_celltalker.R](scripts/run_celltalker.R) 一样，需要真实counts与已有log归一化expression对齐，并在配置r_library指定的隔离Seurat4.4.0/SeuratObject4.1.4环境执行；不从归一化矩阵反推counts。

统一执行器在原生结果包生成后自动调用 [prioritize_communication.py](scripts/prioritize_communication.py)，保存逐方法/条件的研究对象、合格供体、支持样本及原生中位分数证据表。通用LR气泡图和四面板主图使用同一证据排序，保留实际选中的细胞、分子和选择理由；iTALK的二元原生分数不变，最后以真实双端点均值排序。focus由智能体从课题和文件中核实，只能使用真实标签，不要求用户填写配置。供体不足时保留描述性结果，不能据此声称条件特异；其他专用图、原生CellChat图和接收端响应尚不能自动继承全部排序，必须逐项核对。高表达或显示优先级不等于疾病机制。

[run_commpath.R](scripts/run_commpath.R) 执行原生CommPath的端点marker、LR筛选、GSVA、接收群通路和成员关系导出；需要固定GSVA版本与自然log归一化表达。原生LR的q来自端点筛选后的候选族，不能解释成全部数据库候选FDR；通路成员边不补造TF或靶基因链。接口的实际就绪状态以方法契约为准。

[run_sclr.R](scripts/run_sclr.R) 使用原生scLR比较两组独立样本，输入RDS包含真实整数counts和metadata，并提供物种匹配的ligand/receptor数据库TSV及样本设计来源。每条件至少2个独立样本；不支持配对或协变量，某细胞群每条件合格样本不足2时记录排除。原生DESeq2伪汇总归一化、两阶段Monte Carlo与BH按原定义保留。差异值是乘积均值之差，不是log fold change；原生零值插补与插补前样本LR证据分别记录，不能将插补值说成实测表达。图集由统一入口自动接续。

[run_cell2cell.py](scripts/run_cell2cell.py) 执行独立的原生cell2cell单细胞流程：按实际样本计算非零细胞比例、二元LR证据、细胞标签置换和有向Bray-Curtis-like整体评分。输入为已有h5ad与版本化ligand/receptor TSV；复合体需明确完整亚基与&分隔。原生反向资源去重必须保留范围记录；整体评分不当成LR数量，原生双尾P与非对称矩阵BH分别保留。此流程与Tensor-cell2cell分解分别选择，统一入口自动出图。

[run_comunet.R](scripts/run_comunet.R) 对已有通讯权重层执行原生COMUNET聚类、可选模式搜索及两输入拓扑比较。RDS的samples每项包含name/condition/donor/nodes/weight_array/ligand_receptor_pair_df；三维权重轴须严格对应细胞与分子身份，零值语义和原推断来源明确。空层留记录后不进入聚类，未分配类保留0；pattern使用真实source/target标签查询，comparison使用两个真实样本名。网络不相似度没有供体显著性含义，某输入独有候选不能直接说成生物学特异消失。原生对象可按摘要复用，图集自动接续。

[run_disir.py](scripts/run_disir.py) 使用原生DiSiR处理明确的多亚基相互作用假设。输入为真实counts的h5ad与物种匹配的JSON资源；资源每项含唯一id及显式subunit_edges基因二元组。它保留原生log2(counts+1)、独立有放回抽样和全部亚基P满足阈值的支持规则；这不是无放回标签置换，也没有联合复合体P或多重检验校正。亚基缺失不取可见部分继续，复合体强度为原生亚基乘积均值。执行就绪状态以方法契约为准。

[run_crosstalker.R](scripts/run_crosstalker.R) 分析已有LR网络的细胞图、细胞–分子图、原生中心性/PCA及图间比较。RDS含命名tables，各表有source/target/gene_A/gene_B/type_gene_A/type_gene_B/MeanLR；提供原推断来源、权重定义和缺边语义。原生Fisher检验的是LR条目比例，不是患者差异；Mediator直接以权重作路径距离，不能暗改为倒数。中心性分别出图，不混为机制总分。原生在线KEGG注释的背景是内置LR库，需单独核查适用性。执行就绪状态以方法契约为准。

- 通讯模式需要 scTensor 时使用 [run_sctensor.R](scripts/run_sctensor.R)：输入真实基因×细胞RDS与样本/供体/条件/细胞类型元数据，唯一NCBI Gene ID映射来源、同物种LRBase SQLite及版本；按实际输入尺度构建均值外积并执行原生NTD2。固定秩或原生重复NMF秩诊断、至少两个预设随机种子同时保存，自动交付发送/接收因子、核心模式及LR载荷、重构误差和匹配稳定性图。原生算法不处理复合物、不提供LR或供体差异P；高变基因截断输入只支持相应受限探索。

- 以真实TF活性追踪接收细胞响应时使用 [run_domino.R](scripts/run_domino.R) 的 dominoSignal 原生分支：输入同序counts、z_scores、TF活性、regulons和细胞元数据及版本化rl_map。按样本运行create/build，自动交付受体–TF相关/分层网络、TF筛选P、逐配体与细胞通讯矩阵及原生对象；不把TF表达当活性，不把细胞簇Wilcoxon当供体差异，说明该版本单配体接收群汇总为0的行为。

- 有真实log归一化单细胞数据、需要双细胞群基因网络与潜在通讯时使用 [run_sctenifoldxct.py](scripts/run_sctenifoldxct.py)：原生scTenifoldXct逐实际样本构建GRN、1000步以上流形对齐及经验距离背景或全基因对BH检验；输出完整对象、基因网络、全部LR候选、真实二维/三维基因嵌入和训练记录。潜在维度不是组织坐标，模型敲除不是实验因果；未通过群体数量或非有限值检查者保留原因，不能用表达量代替流形结果。

[run_sctensor.R](scripts/run_sctensor.R) 在物种匹配的LRBase和可追溯NCBI Gene ID输入上运行scTensor原生NTD2。自动秩选择、全部预设种子的重构曲线、发送/接收因子、核心LR载荷及匹配稳定性均进入图集；保留完整结果，不挑选最好看的种子。发送与接收模式独立编号，核心张量才定义两者联系；载荷不是通讯显著性。

[run_sctenifoldxct.py](scripts/run_sctenifoldxct.py) 对真实样本中的两个指定细胞群运行scTenifoldXct原生GRN与流形对齐。使用已确认尺度的log归一化表达，保留未达到细胞数要求的样本。原生经验P是非候选基因对距离背景排名，无FDR；可选chi2分支的BH覆盖全部跨基因对。自动交付完整训练曲线、二维/三维基因潜在坐标及适用通讯图，潜在坐标不代表组织位置；当前入口不执行供体差异或虚拟敲除。详细输入与版本见[原生执行契约](references/原生执行契约.md)。

[run_rnamagnet.R](scripts/run_rnamagnet.R) 对小鼠原始counts及同细胞至少15维真实PCA调用RNA-Magnet信号/黏附分支；执行就绪状态以方法契约为准。RDS的pca矩阵须与counts/metadata精确对齐，另提供pca_provenance、input_provenance及magic_python环境路径；不能将UMAP或随机坐标交给PCA邻域。黏附分支的anchors来自已知组织支架细胞，需要至少两个合格群；缺少真实依据时只运行signaling。固定Seurat4.4/Object4.1.4、Rmagic2.0.3.999、magic-impute3.0.0、数据库1.0.0，其他明确数据库版本需记录范围。原生AND/OR分别取最小/最大，不把替代受体集合称为完整复合物。输出原生interaction、带符号specificity、adhesiveness和群均值LR分数；黏附是表达推断，不等于实际组织接触。展示分数阈值不是P值；非有限输出失败退出，不能自动填零。

[run_exfinder.R](scripts/run_exfinder.R) 按事先确定的靶基因和接收群调用exFINDER原生三层先验、表达筛选、重叠角色处理、节点/边权、配体–靶基因最大流及网络AcI；执行状态以方法契约为准。输入与统计单位沿用RDS表达契约，targets/target_provenance、receiving_groups、receptor_tf_cutoffs/cutoff_provenance由实际研究设计确定。明确给ligands或原生ligand_cutoff之一；低表达筛选只提示可能的外部来源，不能证明配体来自系统外。没有真实外部参考时原生配体节点值固定1，须逐图说明这一模型假设。不同角色同名基因按原生fix_OverLap裁剪并保存裁剪前网络，不伪造多条机制证据。原生TF层可能含CAV1等信号中介，图中使用signaling标签并另列原始角色；自动交付四层网络、最大流热图、节点值点图及AcI，不能把模型容量称为实测分子流。


[run_spacenet.py](scripts/run_spacenet.py) 使用SpaCeNet原生空间高斯伪似然及LASSO/group-LASSO估计单元内Omega与距离展开Drho；执行状态以注册表为准。输入为真实空间h5ad，明确features/feature_provenance、变换尺度与normalization_definition、coordinate_unit/coordinate_provenance、spatial_scale_provenance、resolution及penalty_provenance。固定正则penalty或原生grid二选一，按问题和预先指定的AIC/BIC选择规则执行，不按通讯边数调参。输出对称条件关联参数、真实优化轨迹、网格准则以及实测/同样本条件拟合的空间图；无LR支持与显著性推断。未收敛失败退出并保存诊断，不能将最大迭代退出算成功。详见[原生执行契约](references/原生执行契约.md)。


[run_nichede.R](scripts/run_nichede.R) 根据真实空间表达、细胞组成和参考表达均值调用NicheDE原生对象创建、邻域核、回归与多核分层检验，可按已确认发送/接收群继续Niche-LR。执行状态以方法契约为准。输入RDS包括counts（基因×单元，连续分支用expression）、metadata、coordinates、library_expression（细胞类型×基因）和cell_fractions（单元×细胞类型）；参考、组成、基因背景与空间尺度须记录来源，不为拟合方便只截取靶基因而改变参考背景。原生坐标尺度、Poisson均值加NB离散度、分层BH以及部分内部吞掉的拟合异常需分别解释；不将valid=0全部称为阴性。自动生成有效邻域空间图、回归量、模型资格、基因层检验图及实际返回的LR图。Niche-LR原生实现中受体检测引用配体参考索引，筛后入选标记不等于独立受体验证；单细胞分支对num_cells==1有额外原生要求，不能擅自改对象绕过。


[run_sccomm.R](scripts/run_sccomm.R) 接入 scComm 的原生细胞对/群对评分、群层置换、自定义细胞集合和监督对比学习；同一任务自动调用 [run_sccomm_contrast.py](scripts/run_sccomm_contrast.py) 保存模型、分类及训练曲线。已有带细胞注释的表达矩阵时先检查尺度和样本来源，再按真实样本分开运行；不能因用户希望“更精细通讯”就把供体混为独立细胞。输入 RDS 含 expression、metadata，可选 custom_groups；配置记录 native_root、资源/预处理来源、r_library 和对比学习 Python。原生 LR 校正仅作用于最后一个候选、对比学习标签取自同数据增强，这些限制必须随解释交付。详见[原生执行契约](references/原生执行契约.md)。

[run_spaotsc.py](scripts/run_spaotsc.py) 在真实空间坐标上调用 SpaOTsc 原生最优传输，适合已有空间单细胞或 spot 表达、想查看指定配体到受体可能传播位置的任务。输入 h5ad 需包含可追溯表达、细胞或 spot 类型和二维组织坐标；配体–受体及可选转运、受体结合和下游基因必须来自明确资源或研究假设。自动保存完整细胞对传输矩阵、边缘守恒诊断、空间发送/接收图、稀疏展示边和群对网络。该实现是平衡 Sinkhorn，相对分数按每个查询单独归一化，没有 P/FDR 或供体差异，不能把跨查询分数、群均值或绘图边解释成绝对分子通量或机制证据。详见[原生执行契约](references/原生执行契约.md)。

[run_trasig.py](scripts/run_trasig.py) 在已有、可追溯的分化或状态轨迹上执行 TraSig 原生 unaligned 滑窗 dot/cov 评分，适合用户询问“哪些配体–受体随伪时间共同变化”。输入 h5ad 需要真实表达、样本/供体/条件/细胞类型、轨迹分支和缩放到 0–1 的伪时间，并提供版本化 LR 表、轨迹来源及各分支采样时间；实际采样时间未知必须明说。上游置换函数会原地改写真实伪时间，入口拒绝该错误 P 值，改用明确标记的文档意图修正版，保持各轨迹的时间分布且不改写输入。自动交付完整 LR 评分/P/q、支持数量网络、发送与接收轨迹曲线、原生数组和图注。当前未验收 DTW 对齐，不把细胞标签置换称为供体检验或独立轨迹验证。详见[原生执行契约](references/原生执行契约.md)。

[run_timetalk.R](scripts/run_timetalk.R) 对已有且身份可追溯的 Monocle3 伪时间调用 TimeTalk 原生 cellAlign 插值、LR 轨迹相关和双向 Granger LR–TF 检验，适合发育轨迹中的潜在时间先后关联。输入为配套 Seurat/CDS/MRA RDS 和版本化 LR 表；轨迹、MRA、表达尺度及资源来源必须明确，不能用 UMAP 轴或重新排列的细胞代替伪时间。入口保留作者 raw-P PASS，另列双方向校正和全 LR–TF BH，并要求发送与接收轨迹达到预设真实细胞数才标记 supported；插值点永远不能增加真实样本量。自动交付 LR 相关点图、校正筛选图、LR–TF 层级/弦图、轨迹曲线、完整原生对象和图注。TimeTalk 结果是对平滑伪时间序列的潜在调控关联，不是供体检验、观测真实时间或实验因果。详见[原生执行契约](references/原生执行契约.md)。

[run_scmlnet.R](scripts/run_scmlnet.R) 对原始整数 counts 中预先确定的一组发送细胞与一组接收细胞调用 scMLnet 原生 `RunMLnet`，交付 Ligand→Receptor→TF→Target 多层网络、LR 端点表达、各阶段计数、两类 Kendall 热图、完整候选与原生对象。入口固定作者源码和三张数据库摘要，要求 Seurat 4.4.0/SeuratObject 4.1.4；每次只接受一个池化样本，多样本须分别执行再按独立样本比较。作者高表达流程在 raw counts 上调用 `expm1`，细胞层 t 检验未校正；所谓 Fisher 筛选实际是单个超几何点概率，并因字符比较漏掉部分科学计数法的小 P 值。适配器保留原生边集合，另列数值诊断和 Kendall BH，不把诊断校正伪装成原生输出。最终边的值 1 只表示网络成员，不是通讯强度、通量、概率或因果。详见[原生执行契约](references/原生执行契约.md)。

[run_cytotalk.R](scripts/run_cytotalk.R) 对同一真实样本中预先确定的两个细胞群调用 CytoTalk 原生 `run_cytotalk`，用该样本全部注释群计算 PEM 背景，然后构建 MI/ARACNE 胞内网络、LR 跨群边和固定 `pcst_fast` 的 PCST 网络。输入需已有非负表达矩阵、样本/供体/条件/细胞类型和归一化来源；不从矩阵猜 counts，不排除第三群改变 PEM 背景。自动交付跨群 LR 图、分页胞内信号网络、节点 prize、PCST 网络规模和路径 Gamma 证据及 PDF/SVG/高清 PNG、源表和原生对象。原生 beta 选择的 KS P 可因下溢出现多个 0；入口保留并列和原始值，不画饱和的假显著性热图。路径 P 是随机子网分数的平移 Gamma 拟合尾概率，`1-cost` 只表示同一网络内的相对代价；两者都不是供体检验、分子通量或因果证据。详见[原生执行契约](references/原生执行契约.md)。

[run_cellcomm.R](scripts/run_cellcomm.R) 对已有细胞注释的非负归一化表达执行 FUSCA/CellComm 群间 LR 核心：调用原生 `population.pairing`、`calculateObservedMean` 和 `calculatePvalue`，按细胞群平均表达阈值筛选两端，再用保留群大小的标签置换计算 `(1+零分布不低于观测值的次数)/(1+B)`。作者并行置换没有给 worker 设置随机流，入口以明确标记的串行、显式 seed 实现文档意图并保存每次置换结果和标签摘要；原始 P 成员规则与全部候选 BH 诊断分列。自动交付 LR 分子点图、支持计数网络/弦图、论文概览、置换分辨率、PDF/SVG/高清 PNG、源表和原生对象。默认 B=1000，不因图密度抽样候选；池化细胞置换不等于供体检验。当前已验收 CellComm 群间 LR 核心；没有版本化、物种匹配的 PPI、GRN、marker 和 Java Flow 环境时，不生成或暗示 PPI→TF 胞内路径。详见[原生执行契约](references/原生执行契约.md)。

[run_soptsc.R](scripts/run_soptsc.R) 对已有注释的非负归一化单细胞表达调用 RSoptSC 原生 `ImportPathway`、`GetSignalingPartners`、`ClusterSig_single` 和 `ClusterSig`，自动交付每条 LR 的群级概率份额、等权 LR 汇总网络、路径输入表达、Ligand→Receptor→up/down Target 先验层级/弦图、论文概览、PDF/SVG/高清 PNG、源表和原生对象。单 LR 群值只对有正信号的发送细胞求均值；总群网络先分别计算每条 LR 的群分布，再等权汇总并按发送群归一化，不能用细胞级 `P_tot` 的群均值替代。固定源码不提供置换、P 值、供体模型或条件检验；`supported` 只表示正的模型输出。算法会显式形成 LR×发送细胞×接收细胞长表，超过预设上限时失败，不抽样后冒充全量。详见[原生执行契约](references/原生执行契约.md)。

[run_scriabin.R](scripts/run_scriabin.R) 接入 scriabin 的两套原生模块并要求分别执行。`ccim_graph` 在固定 Seurat 4.4.0 环境生成发送细胞×接收细胞的逐 LR 几何表达、全部 LR 汇总 prior graph、群总和、群均值及作者深度回归残差；`programs` 在固定 Seurat 5.5.1 环境生成迭代 LR 共变矩阵、WGCNA 样交互程序、程序成员 kWithin、随机集合检验比例、配体/受体 AddModuleScore 和正的发送–接收程序相加分数。自动交付 LR 点图、计数/强度网络与弦图、程序分层/层级/弦图、程序群热图、论文概览、PDF/SVG/高清 PNG、源表和原生对象。上游当前提交的两个模块分别依赖互不兼容的 Seurat 接口，不能放进同一 R 环境；所谓 program pval 是随机集合 Wilcoxon raw P 大于 0.05 的比例，不是常规 P 值。所有值均为单样本描述或模型分数，不是供体条件检验、分子通量或因果证据。详见[原生执行契约](references/原生执行契约.md)。
