/**
 * Client half: 设置 → 生物医学技能。
 *
 * 34 个功能分类上卷成 6 个大组，按组分节；每个分类是一张横向卡片
 * （组色图标块 + 标题 + 技能数胶囊 + 一句话说明 + 开关 + 详情），
 * 「详情」把卡片展开成整行，列出该类下全部技能与各自的一句话作用。
 *
 * 数据来自 remote.settings.describe()：
 *   { ok, value: { namespaces: [ { ns, schema, value, revision } ] } }
 * 该行 schema 是 schemastery 的 { uid, refs }，没有 properties，
 * 所以显示名/说明/技能清单全部来自构建时生成的 LABELS / GROUPS / SKILLS 常量。
 */
window.__ModuleLoader__.load({
  id: 'dsh-biomedical-skill-settings',
  factory(require) {
    const React = require('react');
    const h = React.createElement;

    const NS_MATCH = 'biomedical-skill-settings';
    const LABELS = {
        "sequencing-qc-alignment": {
            "label": "测序质控与比对",
            "desc": "把原始测序读段变成可信的比对结果，并回答数据质量、覆盖与污染能不能用。",
            "count": 19
        },
        "genome-assembly-comparative": {
            "label": "基因组组装与比较基因组",
            "desc": "从长读长或混合数据组装并注释基因组，再比较多个基因组的共线性、泛基因组与进化关系。",
            "count": 20
        },
        "variant-calling-filtering": {
            "label": "变异检测与过滤",
            "desc": "从比对结果或读段得到胚系、体细胞或靶向 SNV/Indel，并完成规范化与质控过滤。",
            "count": 16
        },
        "copy-number-structural-variation": {
            "label": "拷贝数变异与结构变异",
            "desc": "检测缺失、重复、倒位、易位、重复扩增与等位失衡，并解释拷贝数与结构层面的改变。",
            "count": 10
        },
        "variant-interpretation-clinical": {
            "label": "变异解读与罕见病诊断",
            "desc": "把变异注释到基因与后果，按 ACMG/AMP 证据分级并支撑罕见病与家系诊断结论。",
            "count": 11
        },
        "population-genetics-gwas": {
            "label": "群体遗传与 GWAS",
            "desc": "在人群层面找疾病关联位点、构建遗传评分并推断因果、共定位、精细定位与祖源结构。",
            "count": 28
        },
        "cancer-genomics-liquid-biopsy": {
            "label": "肿瘤基因组与液体活检",
            "desc": "刻画肿瘤体细胞突变、克隆演化与可用标志物，并用 cfDNA/ctDNA 做早筛、监测与残留病判断。",
            "count": 28
        },
        "forensic-identity-genetics": {
            "label": "法医与身份鉴定",
            "desc": "用 SNP、STR、Y 染色体与线粒体标记完成身份、亲缘、混合样本与祖先来源判定。",
            "count": 10
        },
        "clinical-precision-medicine": {
            "label": "临床精准医学与结局分析",
            "desc": "评估生物标志物与预测模型，划分患者亚组，并把证据与结局分析整理成可交接的临床材料。",
            "count": 10
        },
        "medical-imaging-radiomics": {
            "label": "医学影像与放射组学",
            "desc": "处理 CT/MRI/病理等影像数据，做分割、配准、特征提取、模型训练与可信度评估。",
            "count": 12
        },
        "microscopy-cell-phenotyping": {
            "label": "显微成像与细胞表型",
            "desc": "从显微、流式与空间蛋白图像定量细胞形态、分割、计数、追踪并比较组间表型。",
            "count": 17
        },
        "transcriptomics-quantification": {
            "label": "转录组上游与定量",
            "desc": "从 RNA 读段得到表达矩阵，处理链特异性、异构体组装、融合、剪接与 RNA 修饰证据。",
            "count": 32
        },
        "differential-expression-enrichment": {
            "label": "差异表达与功能富集",
            "desc": "在组学矩阵上做组间差异与统计建模，并把结果落到通路、基因集与功能解释。",
            "count": 11
        },
        "single-cell-core": {
            "label": "单细胞基础分析",
            "desc": "完成单细胞数据的质控、双细胞与环境 RNA 清理、降维聚类、注释与对象格式管理。",
            "count": 20
        },
        "single-cell-advanced-virtual-cell": {
            "label": "单细胞高级与虚拟细胞",
            "desc": "在单细胞数据上做轨迹、通讯、扰动预测、多模态与队列复现等机制性推断。",
            "count": 20
        },
        "spatial-omics": {
            "label": "空间组学分析",
            "desc": "利用空间坐标回答组织里谁在哪里、谁挨着谁，并识别空间域、邻域与细胞组成。",
            "count": 15
        },
        "proteomics": {
            "label": "蛋白质组学",
            "desc": "从质谱原始数据到肽段鉴定与蛋白定量，并处理修饰、亲和平台与定量质量。",
            "count": 21
        },
        "metabolomics-lipidomics": {
            "label": "代谢组与脂质糖组",
            "desc": "把质谱、NMR 或电泳信号转成可信的代谢物、脂质与聚糖注释和定量结果。",
            "count": 18
        },
        "epigenomics-methylation": {
            "label": "表观遗传与 DNA 甲基化",
            "desc": "处理 ChIP/ATAC/CUT&RUN、Hi-C 与亚硫酸氢盐数据，识别 peak、染色质状态、三维结构与甲基化差异。",
            "count": 31
        },
        "regulatory-network-sequence-models": {
            "label": "调控网络与序列模型",
            "desc": "推断转录因子调控网络与模块，或用基因组基础模型评估序列变异的调控效应。",
            "count": 18
        },
        "microbiome-metagenomics": {
            "label": "微生物组与宏基因组",
            "desc": "从扩增子或 shotgun 数据得到物种、功能、耐药与菌株结果，并做群落比较与传播分析。",
            "count": 38
        },
        "structural-biology-modeling": {
            "label": "结构预测与建模",
            "desc": "预测或准备蛋白与复合物结构，评估质量、相似性与界面几何并做动力学分析。",
            "count": 18
        },
        "chemoinformatics-drug-design": {
            "label": "化学信息学与药物设计",
            "desc": "围绕小分子做结构标准化、描述符、相似性、对接与筛选、成药性与毒性排序。",
            "count": 27
        },
        "protein-engineering-synbio": {
            "label": "蛋白工程与合成生物学",
            "desc": "设计蛋白序列与骨架、优化表达与可开发性，并把构建放进代谢与自动化实验方案。",
            "count": 15
        },
        "gene-editing-cloning": {
            "label": "基因编辑与分子克隆",
            "desc": "设计 gRNA、供体与筛选文库，评估脱靶与编辑结果，并完成克隆相关的序列层面设计。",
            "count": 13
        },
        "pharmacogenomics-dosing": {
            "label": "药物基因组学与用药",
            "desc": "把基因型转成星等位基因与表型，落到具体药物的剂量、疗效与安全性建议。",
            "count": 10
        },
        "immunology-immuno-oncology": {
            "label": "免疫组学与免疫治疗",
            "desc": "分析受体库、HLA、新抗原与免疫浸润，评估免疫治疗获益与疫苗表位覆盖。",
            "count": 17
        },
        "literature-evidence-synthesis": {
            "label": "文献检索与证据合成",
            "desc": "检索、核验并综合文献与数据库证据，形成可核查的综述、评审与证据强度判断。",
            "count": 13
        },
        "writing-document-delivery": {
            "label": "写作与文档交付",
            "desc": "把分析与文献写成论文、基金、海报或报告，并导出合规的 Word/PDF/PPT 交付件。",
            "count": 20
        },
        "data-engineering-statistics": {
            "label": "数据工程与统计方法",
            "desc": "整理表格与格式、建立统计与机器学习评估、管理隐私与数据交换的工程性任务。",
            "count": 24
        },
        "workflow-reproducibility": {
            "label": "计算流程与可复现性",
            "desc": "搭可复现的分析环境与流程，追溯输入与版本，并审计结果漂移与助手可靠性。",
            "count": 10
        },
        "database-api-access": {
            "label": "数据库与接口对接",
            "desc": "通过 API 或公共库取回基因、变异、结构、组学与文献数据，并核对版本与可用性。",
            "count": 11
        },
        "visualization-figures": {
            "label": "可视化与图件",
            "desc": "把数据与结构做成清晰可发表的图表、轨道、示意图或渲染好的图形交付件。",
            "count": 10
        },
        "research-design-hypothesis": {
            "label": "研究设计与假设生成",
            "desc": "把宽泛兴趣收束成可检验问题，规划数据、对照、样本量与验证路线。",
            "count": 10
        }
    };
    const GROUPS = [
        {
            "id": "variants",
            "label": "测序与变异",
            "emoji": "🧬",
            "color": "#3b82f6",
            "cats": [
                "sequencing-qc-alignment",
                "genome-assembly-comparative",
                "variant-calling-filtering",
                "copy-number-structural-variation",
                "variant-interpretation-clinical",
                "population-genetics-gwas",
                "cancer-genomics-liquid-biopsy",
                "forensic-identity-genetics"
            ]
        },
        {
            "id": "omics",
            "label": "组学与单细胞",
            "emoji": "🧪",
            "color": "#8b5cf6",
            "cats": [
                "transcriptomics-quantification",
                "differential-expression-enrichment",
                "single-cell-core",
                "single-cell-advanced-virtual-cell",
                "spatial-omics",
                "epigenomics-methylation",
                "regulatory-network-sequence-models",
                "proteomics",
                "metabolomics-lipidomics",
                "microbiome-metagenomics"
            ]
        },
        {
            "id": "structure",
            "label": "结构与药物",
            "emoji": "💊",
            "color": "#06b6d4",
            "cats": [
                "structural-biology-modeling",
                "chemoinformatics-drug-design",
                "protein-engineering-synbio",
                "gene-editing-cloning",
                "pharmacogenomics-dosing"
            ]
        },
        {
            "id": "clinical",
            "label": "临床与影像",
            "emoji": "🩺",
            "color": "#10b981",
            "cats": [
                "clinical-precision-medicine",
                "medical-imaging-radiomics",
                "microscopy-cell-phenotyping",
                "immunology-immuno-oncology"
            ]
        },
        {
            "id": "methods",
            "label": "方法与工程",
            "emoji": "⚙️",
            "color": "#f59e0b",
            "cats": [
                "data-engineering-statistics",
                "workflow-reproducibility",
                "database-api-access",
                "visualization-figures",
                "research-design-hypothesis"
            ]
        },
        {
            "id": "writing",
            "label": "文献与写作",
            "emoji": "📝",
            "color": "#f43f5e",
            "cats": [
                "literature-evidence-synthesis",
                "writing-document-delivery"
            ]
        }
    ];
    const SKILLS = {
        "sequencing-qc-alignment": [
            {
                "name": "01-genome-alignment",
                "desc": "当用户需要把短读长或常规 DNA 测序读段比对到参考基因组并得到可追溯比对文件时使用。"
            },
            {
                "name": "01-genome-bam",
                "desc": "当用户需要查看、转换、排序、索引、合并、切片或验证 SAM、BAM、CRAM 文件时使用。"
            },
            {
                "name": "01-genome-fastqc",
                "desc": "当用户需要检查 FASTQ 原始读段质量、接头、碱基组成和过度代表序列，并决定后续处理时使用。"
            },
            {
                "name": "01-genome-long-read-sequencing",
                "desc": "当用户需要评估 Nanopore 或 PacBio 长读长的长度、质量、产量、污染和平台特征时使用。"
            },
            {
                "name": "01-genome-multiqc",
                "desc": "当用户需要把 FastQC、比对、覆盖度和变异检测等多样本质控结果汇总并发现批次异常时使用。"
            },
            {
                "name": "01-genome-reads-trimming",
                "desc": "当用户需要去除已确认的接头或低质量尾部，并尽量避免无理由丢失有效读段时使用。"
            },
            {
                "name": "genome-contamination-detection",
                "desc": "当用户需要识别测序数据或组装中的物种污染、样本混合、接头与外源序列时使用。"
            },
            {
                "name": "long-read-alignment",
                "desc": "当用户需要把 Nanopore 或 PacBio 长读长比对到参考基因组并支持变异、异构体或甲基化分析时使用。"
            },
            {
                "name": "nanopore-basecalling",
                "desc": "当用户需要把 Nanopore POD5/FAST5 转为碱基序列，并选择模型、条码拆分和修饰检测设置时使用。"
            },
            {
                "name": "nfcore-bamtofastq",
                "desc": "当收到 BAM 或 CRAM，比对前的测序读段缺失且后续任务确实需要恢复读段时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/bamtofastq。"
            },
            {
                "name": "nfcore-demultiplex",
                "desc": "当收到未拆分的测序文件、索引读段或上机目录，需要按样本恢复数据时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/demultiplex。"
            },
            {
                "name": "nfcore-fastqrepair",
                "desc": "当测序文件打不开、FASTQ 记录异常或成对读段错位，需要定位并修复文件问题时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/fastqrepair。"
            },
            {
                "name": "nfcore-fastquorum",
                "desc": "当测序建库含 UMI，研究需要降低错误或形成分子共识读段时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/fastquorum。"
            },
            {
                "name": "nfcore-genomeskim",
                "desc": "当浅测序数据需要读段质量评估，或需辨明浅测序能否支持目标组装时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genomeskim。"
            },
            {
                "name": "nfcore-mitodetect",
                "desc": "当需要评估线粒体分析所需数据或进行原始读段质控时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mitodetect。"
            },
            {
                "name": "nfcore-nanoseq",
                "desc": "当收到 Nanopore 数据，需要识别信号或读段阶段并进行拆样、质控与比对时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/nanoseq。"
            },
            {
                "name": "nfcore-seqinspector",
                "desc": "当收到测序文件或比对结果，需要了解数据质量和异常样本时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/seqinspector。"
            },
            {
                "name": "sequencing-coverage-capture-efficiency",
                "desc": "当用户需要评估 WGS、WES 或面板测序的覆盖深度、均一性、可调用区域和捕获效率时使用。"
            },
            {
                "name": "nfcore-ssds",
                "desc": "当历史单链 DNA 富集实验数据需要复核专用信号处理时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/ssds。"
            }
        ],
        "genome-assembly-comparative": [
            {
                "name": "01-genome-gene-annotation",
                "desc": "当用户需要为新组装基因组识别重复序列、基因结构、非编码 RNA 和功能，并形成可发布注释集时使用。"
            },
            {
                "name": "02-population-genetics-phylogenetic-analysis",
                "desc": "当用户需要从序列或基因组构建系统发育树、选择模型并评估分支支持时使用。"
            },
            {
                "name": "cross-species-annotation-projection",
                "desc": "当用户需要把已注释参考物种的基因模型投影到近缘新组装基因组时使用。"
            },
            {
                "name": "genome-assembly-qc",
                "desc": "当用户需要为细菌、真菌、动植物或其他物种选择从头组装策略并系统评价成品质量时使用。"
            },
            {
                "name": "long-read-de-novo-assembly",
                "desc": "当用户需要使用 Nanopore、PacBio HiFi 或混合数据进行从头基因组组装与抛光时使用。"
            },
            {
                "name": "nfcore-denovohybrid",
                "desc": "当同一样本有长读和短读数据，希望重建基因组并评估历史混合组装路径时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/denovohybrid。"
            },
            {
                "name": "nfcore-eager",
                "desc": "当古代或降解 DNA 测序数据需要处理，并评估损伤、污染或分型证据时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/eager。"
            },
            {
                "name": "nfcore-genephylomodeler",
                "desc": "当同源序列和系统树用于检验进化模型或自然选择时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genephylomodeler。"
            },
            {
                "name": "nfcore-genomeannotator",
                "desc": "当只有基因组组装或不完整注释，需要识别编码基因结构时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genomeannotator。"
            },
            {
                "name": "nfcore-genomeassembler",
                "desc": "当已有 ONT 或 PacBio HiFi 长读数据，希望获得基因组组装时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genomeassembler。"
            },
            {
                "name": "nfcore-genomeqc",
                "desc": "当有一个或多个组装及注释，需要判断完整性、质量或比较候选版本时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genomeqc。"
            },
            {
                "name": "nfcore-kmermaid",
                "desc": "当需要比较序列集合或样本相似性，已有读段或组装时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/kmermaid。"
            },
            {
                "name": "nfcore-multiplesequencealign",
                "desc": "当已有多条同源 DNA 或蛋白序列，需要比对或比较比对方案时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/multiplesequencealign。"
            },
            {
                "name": "nfcore-ncrnannotator",
                "desc": "当已有基因组序列，需要识别非编码 RNA 家族时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/ncrnannotator。"
            },
            {
                "name": "nfcore-neutronstar",
                "desc": "当数据和项目记录表明使用历史 10x linked-read 技术，需要评估或复现组装时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/neutronstar。"
            },
            {
                "name": "nfcore-pairgenomealign",
                "desc": "当已有两个或多套基因组组装，需要研究同源区域与共线性时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pairgenomealign。"
            },
            {
                "name": "nfcore-pangenome",
                "desc": "当已有同源组装或单倍型序列集合，希望建立泛基因组图时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pangenome。"
            },
            {
                "name": "nfcore-phyloplace",
                "desc": "当已有未知来源或新增序列，需要定位到参考系统树时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/phyloplace。"
            },
            {
                "name": "nfcore-reportho",
                "desc": "当多个直系同源预测结果需要统一标识并比较一致性时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/reportho。"
            },
            {
                "name": "pangenome-synteny-analysis",
                "desc": "当用户需要比较多个基因组的核心/可变序列、结构差异、基因家族和共线性时使用。"
            }
        ],
        "variant-calling-filtering": [
            {
                "name": "01-genome-mtdna-variant-calling",
                "desc": "当用户需要检测线粒体 DNA 变异、低频异质性并避免 NUMT 和污染造成误报时使用。"
            },
            {
                "name": "01-genome-snp-calling",
                "desc": "当用户需要从生殖系 DNA 的分析就绪 BAM/CRAM 检测 SNV 和短 Indel，并进行单样本或队列联合分型时使用。"
            },
            {
                "name": "01-genome-target-sequencing",
                "desc": "当用户需要分析基因面板、扩增子或捕获式靶向测序，并处理 UMI、低频变异和目标区覆盖时使用。"
            },
            {
                "name": "01-genome-variant-filtering",
                "desc": "当用户需要对 SNV、Indel 或队列 VCF 做硬过滤、VQSR 或模型校准并解释保留规则时使用。"
            },
            {
                "name": "01-genome-wes",
                "desc": "当用户需要从外显子组测序数据获得胚系小变异，并评估捕获效率和可解释缺口时使用。"
            },
            {
                "name": "01-genome-wgs",
                "desc": "当用户需要设计或执行从短读长全基因组 FASTQ 到分析就绪比对和胚系小变异结果的流程时使用。"
            },
            {
                "name": "long-read-variant-calling",
                "desc": "用于从PacBio HiFi或Oxford Nanopore比对数据检测SNV、Indel和结构变异，并进行分相与复杂区域复核；当短读长难以解析或用户提供长读长时使用。"
            },
            {
                "name": "nfcore-deepvariant",
                "desc": "当已确认胚系小变异任务，需要评估历史 DeepVariant 流程与现有测序平台是否兼容时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/deepvariant。"
            },
            {
                "name": "nfcore-exoseq",
                "desc": "当已有外显子捕获测序数据，需要复核历史变异分析或恢复原项目设置时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/exoseq。"
            },
            {
                "name": "nfcore-pacvar",
                "desc": "当已有 PacBio HiFi 全基因组或 PureTarget 数据，需要变异分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pacvar。"
            },
            {
                "name": "nfcore-sarek",
                "desc": "当DNA 测序文件或比对结果需要检测胚系或肿瘤体细胞变异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/sarek。"
            },
            {
                "name": "nfcore-variantbenchmarking",
                "desc": "当已有变异检测结果和真值，需要衡量准确性或比较分析设置时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/variantbenchmarking。"
            },
            {
                "name": "vcf-normalization-curation",
                "desc": "用于VCF拆分、左对齐、参考等位基因核对、排序、合并和索引；当变异文件需要注释、比较或交付前整理时使用。"
            },
            {
                "name": "vcf-qc-sample-consistency",
                "desc": "用于检查VCF位点质量、基因型质量、样本身份、亲缘和异常值；当需要判断变异集能否进入关联、注释或临床解释时使用。"
            },
            {
                "name": "nfcore-rnavar",
                "desc": "当只有 RNA 测序或需补充 RNA 层证据，希望识别表达区域变异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnavar。"
            },
            {
                "name": "variant-calling-wes-wgs",
                "desc": "| Germline short-variant discovery mainline for human whole-exome (WES) and whole-genome (WGS) resequencing: r…"
            }
        ],
        "copy-number-structural-variation": [
            {
                "name": "01-genome-germline-cnv",
                "desc": "当用户需要从 WGS、WES 或靶向数据检测生殖系拷贝数变异并评估质量时使用。"
            },
            {
                "name": "01-genome-loh-analysis",
                "desc": "当用户需要从基因型、测序深度或等位基因失衡识别LOH和拷贝中性LOH，并区分缺失、UPD与肿瘤事件时使用。"
            },
            {
                "name": "01-genome-repeat-expansion-analysis",
                "desc": "当用户需要从Nanopore或PacBio长读长比对数据分析STR、VNTR等串联重复位点的等位长度、motif组成、中断结构、分相或扩增证据时使用。"
            },
            {
                "name": "01-genome-sv-detection",
                "desc": "当用户需要检测缺失、重复、倒位、易位及其他结构变异，并整合多种信号时使用。"
            },
            {
                "name": "focal-amplification-ecdna-analysis",
                "desc": "用于从肿瘤WGS识别焦点扩增并用AmpliconArchitect/AmpliconClassifier区分ecDNA、BFB、HSR和线性扩增；当高拷贝致癌基因需要结构解析时使用。"
            },
            {
                "name": "nfcore-circdna",
                "desc": "当已有 Circle-seq、WGS 或 ATAC 相关数据，希望寻找环状 DNA时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/circdna。"
            },
            {
                "name": "nfcore-createpanelrefs",
                "desc": "当要为变异或拷贝数分析建立正常样本背景，已有多个正常样本数据时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/createpanelrefs。"
            },
            {
                "name": "tumor-cnv-driver-event-analysis",
                "desc": "用于肿瘤CNV检测、纯度倍性校正、复发性区域和候选驱动基因分析；当用户有WGS/WES、芯片或面板深度数据时使用。"
            },
            {
                "name": "01-genome-single-cell-cnv",
                "desc": "当用户需要从 scRNA-seq 或 scDNA-seq 推断细胞拷贝数轮廓与克隆结构，并评估恶性细胞判定对正常参考的依赖时使用。"
            },
            {
                "name": "cnv-sv-detection",
                "desc": "| Copy-number variation (CNV) and structural variation (SV) detection and annotation for WGS/WES/panel data. C…"
            }
        ],
        "variant-interpretation-clinical": [
            {
                "name": "13-clinical-genomics-hpo-matching",
                "desc": "用于把自由文本临床表现标准化为HPO并进行疾病或基因相似度排序；当罕见病分析需要表型驱动优先级时使用。"
            },
            {
                "name": "13-clinical-genomics-intervar",
                "desc": "系统化的ACMG/AMP胚系变异分类，覆盖全部28条证据标准（PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-7），产出五级分类（致病/可能致病/意义不明/可能良性/良性）并附逐条证…"
            },
            {
                "name": "13-clinical-genomics-rare-disease-diagnosis",
                "desc": "用于整合表型、家系、小变异、CNV/SV和证据评级形成罕见病诊断候选；当用户需要端到端病例解释时使用。"
            },
            {
                "name": "13-clinical-genomics-spliceai",
                "desc": "用于综合CADD、REVEL、AlphaMissense、SpliceAI等评估错义与潜在剪接变异；当用户需要计算证据而非最终临床分类时使用。"
            },
            {
                "name": "13-clinical-genomics-trio-analysis",
                "desc": "用于三联体或扩展家系中的新发、隐性、显性、X连锁和复合杂合变异排序；当用户提供家系VCF和表型时使用。"
            },
            {
                "name": "13-clinical-genomics-varsome",
                "desc": "用于检索ClinVar、VarSome及其链接的原始证据并处理分类冲突；当用户需要某一变异的临床记录、提交者和更新时间时使用。"
            },
            {
                "name": "acmg-clingen-germline-cnv-classification",
                "desc": "用于按ACMG/ClinGen技术标准解释胚系缺失和重复；当用户提供CNV坐标、基因内容与表型并需要临床分级时使用。"
            },
            {
                "name": "nfcore-longraredisease",
                "desc": "当患者长读长数据和表型需要罕见病变异分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/longraredisease。"
            },
            {
                "name": "nfcore-raredisease",
                "desc": "当患者 WGS 或 WES 与家系和症状需要寻找罕见病候选变异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/raredisease。"
            },
            {
                "name": "variant-annotation-gene-consequence",
                "desc": "当用户需要把 VCF 变异映射到基因、转录本、蛋白后果和群体数据库时使用。"
            },
            {
                "name": "variant-pathogenicity-acmg",
                "desc": "| Germline variant pathogenicity interpretation under the ACMG/AMP 2015 framework, with ClinGen SVI refinement…"
            }
        ],
        "population-genetics-gwas": [
            {
                "name": "02-population-genetics-admixture-ancestry-estimation",
                "desc": "当用户需要检测群体间基因流、渗入或历史混合，并区分不完全谱系排序时使用。"
            },
            {
                "name": "02-population-genetics-allele-frequency-analysis",
                "desc": "当用户问某变异在患者/对照或不同人群中常不常见、数据库没查到是否罕见、如何计算携带频率或比较AF/AC/AN时使用；只提供百分比时先核查分母和质控。"
            },
            {
                "name": "02-population-genetics-genotype-phenotype-qc",
                "desc": "当用户交付芯片、测序基因型与病例对照/体征表，想知道能否分析、样本为何对不上、数据是否可靠，或准备寻找疾病遗传因素和基因风险评分时使用；自主识别样本和编码，不要求用户知道QC或文件格式。"
            },
            {
                "name": "02-population-genetics-gwas-association-analysis",
                "desc": "当用户有芯片/测序基因型和疾病、体征或随访信息，想找易感位点、解释遗传风险、比较病例对照，或已有GWAS结果需要排查QQ膨胀、补图或回应审稿意见时使用；不要求用户知道GWAS、PLINK、REGENIE或SAIGE。"
            },
            {
                "name": "02-population-genetics-gwas-meta-analysis",
                "desc": "当用户有多个队列或公开遗传关联结果想合并、增加证据、比较中国与其他人群、解释方向不一致或补外部复现时使用，包括GWAS meta-analysis与跨祖源分析；只有基因清单时先说明缺少效应数据。"
            },
            {
                "name": "02-population-genetics-gwas-sumstats-qc",
                "desc": "当用户拿到遗传关联结果表不知道能否用于论文、两份结果合不上、字段/OR/坐标/等位基因不一致，或准备MR、共定位、遗传相关、PRS和荟萃分析的输入时使用；先识别文件，无需用户知道汇总统计或harmonization。"
            },
            {
                "name": "02-population-genetics-haplotype-analysis",
                "desc": "当用户看到同一区域很多相似遗传信号、想去除重复工具、寻找代理位点、给精细定位/共定位准备参考或需要LD和单倍型时使用；先区分r、r²、D′及是否需要相位。"
            },
            {
                "name": "02-population-genetics-ldsc-analysis",
                "desc": "当用户问某病受遗传影响多大、两种疾病是否共享遗传背景、多个性状能否构成共同因素，或遇到GWAS整体膨胀、需要LDSC/Genomic SEM时使用；不要求知道遗传协方差术语。"
            },
            {
                "name": "02-population-genetics-population-stratification",
                "desc": "当用户的遗传样本混在人群/批次中、PCA出现离群、担心病例对照来源不同或需要祖源和亲缘校正时使用，包括PCA/ADMIXTURE；不用于判定个人民族或文化身份。"
            },
            {
                "name": "02-population-genetics-prs-polygenic-risk-score",
                "desc": "当用户想用遗传数据预测谁更容易患病、比较人群风险、评价已有遗传评分，或需要PRS、LDpred2、PRS-CS及校准图时使用；临床个体诊断与单个致病变异解释不是本任务。"
            },
            {
                "name": "02-population-genetics-qtl-target-prioritization",
                "desc": "当用户只知道疾病与候选基因/蛋白，想找作用机制、药物靶点、值得做实验的对象或问改变表达是否影响患病风险时使用；也处理cis-MR、eQTL/pQTL整合和靶点审稿补证据，不把任意基因名直接认定为有效靶点。"
            },
            {
                "name": "02-population-genetics-rare-variant-analysis",
                "desc": "当用户有外显子/全基因组变异，想研究某病的罕见有害突变、基因负担、病例携带者或单SNP分析没信号，或提出burden、SKAT、SKAT-O时使用；先判定注释、携带者和队列条件。"
            },
            {
                "name": "02-population-genetics-selection-analysis",
                "desc": "当用户需要检测近期或长期自然选择信号并整合频率谱、单倍型和群体分化证据时使用。"
            },
            {
                "name": "02-population-genetics-two-sample-mr",
                "desc": "当用户问某因素、基因表达或蛋白是否会导致某疾病、因果方向是否相反、相关关系能否支持病因，或交付暴露/结局遗传关联表、提出MR及多效性审稿意见时使用；先识别研究与数据，不要求用户认识孟德尔随机化。"
            },
            {
                "name": "colocalization-analysis-scaffold-replace",
                "desc": "当用户问同一区域的疾病与表达/蛋白信号是不是一回事、两个性状是否共享变异、MR或TWAS是否受连锁牵连，或需要coloc及多信号共定位时使用；只给两个lead SNP需先获取完整区域数据。"
            },
            {
                "name": "fine-mapping-scaffold-replace",
                "desc": "当用户已有某疾病的遗传关联峰却不知道哪个变异最值得验证、显著SNP太多、想缩小候选范围，或要求可信集、PIP、SuSiE/FINEMAP时使用；没有区域关联数据时先识别证据缺口。"
            },
            {
                "name": "genotype-imputation-phasing",
                "desc": "当用户拿到芯片/低深度基因型发现位点不足、数据缺失、想对齐参考或为遗传关联和评分补位点，或需要Beagle/SHAPEIT、相位和填充时使用；先区别填充与从测序数据检测变异。"
            },
            {
                "name": "gwas-locus-gene-prioritization",
                "desc": "当用户问疾病关联位点对应哪个基因、最近基因是否可信、该选哪个基因做实验，或想联合QTL、染色质互作和精细定位解释GWAS时使用；不要求知道L2G或增强子术语。"
            },
            {
                "name": "nfcore-genomicrelatedness",
                "desc": "当低覆盖基因组数据需要判断样本亲缘关系或重复身份时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/genomicrelatedness。"
            },
            {
                "name": "nfcore-gwas",
                "desc": "当已有基因型与样本性状，希望寻找遗传关联时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/gwas。"
            },
            {
                "name": "nfcore-phaseimpute",
                "desc": "当基因型缺失或密度不足，需要分相并补充可预测位点时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/phaseimpute。"
            },
            {
                "name": "nfcore-radseq",
                "desc": "当限制性酶切相关测序数据需要构建可比较位点并做群体变异分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/radseq。"
            },
            {
                "name": "nfcore-rarevariantburden",
                "desc": "当已有病例变异汇总计数和外部对照，需要检验基因稀有变异负荷时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rarevariantburden。"
            },
            {
                "name": "nfcore-variantcatalogue",
                "desc": "当多样本基因组变异需要整理成群体频率目录时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/variantcatalogue。"
            },
            {
                "name": "phewas-phenome-wide-association",
                "desc": "当用户想知道一个变异、基因或遗传评分还关联哪些疾病、寻找潜在副作用、在大量病历表型中筛关联，或需要PheWAS图时使用；区分查询已有门户与对自己的队列重新建模。"
            },
            {
                "name": "twas-transcriptome-association",
                "desc": "当用户有疾病GWAS想找相关组织/表达基因、问遗传预测表达与疾病是否有关，或需要TWAS、FUSION、PrediXcan、MetaXcan及显著邻近基因解释时使用；普通差异表达问题不直接做TWAS。"
            },
            {
                "name": "mendelian-randomization",
                "desc": "当用户需要从观察性转录组或多组学数据寻找候选因果驱动因子，并区分预测、干预效应与相关性时使用。"
            },
            {
                "name": "nfcore-abotyper",
                "desc": "当长读长测序需要研究血型或红细胞抗原相关等位基因时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/abotyper。"
            }
        ],
        "cancer-genomics-liquid-biopsy": [
            {
                "name": "14-cancer-genomics-clonal-evolution",
                "desc": "用于单样本、多区域或纵向肿瘤样本的克隆聚类、系统发育和治疗前后演化分析；当用户研究亚克隆结构时使用。"
            },
            {
                "name": "14-cancer-genomics-driver-gene-analysis",
                "desc": "用于肿瘤体细胞变异的驱动性、诊断、预后和治疗证据分级；当用户需要从突变表形成可审计临床解释时使用。"
            },
            {
                "name": "14-cancer-genomics-hrd",
                "desc": "用于计算并解释LOH、LST、TAI等HRD基因组瘢痕，联合HR通路变异和突变特征；当用户研究BRCA通路或PARP抑制剂生物标志物时使用。"
            },
            {
                "name": "14-cancer-genomics-intratumor-heterogeneity",
                "desc": "用于估计肿瘤纯度、癌细胞分数和总体瘤内异质性；当VAF需要纯度校正或用户希望量化异质性时使用。"
            },
            {
                "name": "14-cancer-genomics-msi",
                "desc": "用于WES、WGS或靶向测序的微卫星不稳定性检测及MSI-H解释；当用户需要免疫治疗相关MSI标志物时使用。"
            },
            {
                "name": "14-cancer-genomics-mutation-signature",
                "desc": "用于从SNV、双碱基、Indel或SV谱分解COSMIC突变特征；当用户研究致突变过程、DNA修复或暴露来源时使用。"
            },
            {
                "name": "14-cancer-genomics-somatic-mutation",
                "desc": "用于肿瘤—正常配对WES/WGS或靶向测序的体细胞SNV/Indel检测；当用户从BAM或FASTQ开展肿瘤突变分析时使用。"
            },
            {
                "name": "14-cancer-genomics-subclone-analysis",
                "desc": "用于从等位特异拷贝数估计亚克隆CNV、倍性和肿瘤全基因组加倍；当用户需要解释拷贝数异质性、WGD或HRD中的倍性混淆时使用。"
            },
            {
                "name": "14-cancer-genomics-tmb",
                "desc": "用于计算肿瘤突变负荷、定义可计数区域并比较WES与靶向面板结果；当用户需要TMB数值或阈值解释时使用。"
            },
            {
                "name": "15-liquid-biopsy-cancer-origin-prediction",
                "desc": "用于cfDNA甲基化信号的癌症早筛、组织来源分类和模型验证；当用户提供亚硫酸氢盐或富集型甲基化数据时使用。"
            },
            {
                "name": "15-liquid-biopsy-exosome-rna-analysis",
                "desc": "用于细胞外囊泡RNA测序的质控、定量、差异和标志物分析；当样本来自血浆、尿液等低输入体液时使用。"
            },
            {
                "name": "15-liquid-biopsy-mrd-detection",
                "desc": "用于纵向ctDNA变化、分子残留病和复发预警分析；当用户有治疗前后多个时间点或肿瘤知情面板时使用。"
            },
            {
                "name": "cancer-gene-dependency-analysis",
                "desc": "用于分析DepMap基因效应、药物反应、表达和基因组特征以发现癌细胞依赖；当用户需要靶点或合成致死候选时使用。"
            },
            {
                "name": "cancer-mutation-landscape-oncoplot",
                "desc": "用于制作oncoplot、突变景观、共现互斥和样本临床注释图；当用户需要队列级肿瘤变异展示时使用。"
            },
            {
                "name": "cfdna-fragmentomics-analysis",
                "desc": "用于cfDNA片段长度、末端基序、覆盖波动、核小体足迹和断裂位点分析；当用户研究肿瘤早筛或组织来源时使用。"
            },
            {
                "name": "cfdna-preprocessing-umi-consensus",
                "desc": "用于cfDNA靶向测序的读段质控、UMI家族构建、单双链共识和背景错误控制；当用户从原始液体活检数据开始时使用。"
            },
            {
                "name": "ctdna-mutation-detection-scaffold-replace",
                "desc": "用于cfDNA/ctDNA中的超低频SNV和Indel检测、技术噪声建模与候选复核；当预期VAF接近测序错误率时使用。"
            },
            {
                "name": "liquid-biopsy-assay-validation",
                "desc": "用于评估液体活检试验的检测限、精密度、准确性、特异度和真实世界适用性；当用户设计分析验证或审查模型性能时使用。"
            },
            {
                "name": "nfcore-evexplorer",
                "desc": "当细胞外囊泡来源的低输入 RNA 数据需要质控或表达分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/evexplorer。"
            },
            {
                "name": "nfcore-oncoanalyser",
                "desc": "当同一患者有肿瘤与正常 DNA 或可用 RNA，需要综合肿瘤基因组分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/oncoanalyser。"
            },
            {
                "name": "nfcore-pacsomatic",
                "desc": "当配对肿瘤与正常 PacBio HiFi 数据需要检测体细胞变异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pacsomatic。"
            },
            {
                "name": "nfcore-rnadnavar",
                "desc": "当同一患者 DNA 和 RNA 数据需要联合评估体细胞变异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnadnavar。"
            },
            {
                "name": "nfcore-tumourevo",
                "desc": "当肿瘤变异、拷贝数与时间或多区域样本需要研究克隆演化时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/tumourevo。"
            },
            {
                "name": "nfcore-variantprioritization",
                "desc": "当已有癌症相关 VCF，需要注释与排序体细胞或遗传易感候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/variantprioritization。"
            },
            {
                "name": "nfcore-viralintegration",
                "desc": "当宿主与病毒相关测序需要寻找整合断点时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/viralintegration。"
            },
            {
                "name": "public-cancer-cohort-analysis",
                "desc": "用于检索和分析TCGA或cBioPortal中的癌症分子与临床队列；当用户需要外部频率、共变或生存验证时使用。"
            },
            {
                "name": "tumor-fraction-estimation",
                "desc": "用于依据体细胞变异、拷贝数或甲基化信号估计血浆肿瘤分数；当用户需要量化ctDNA占比或评估样本可用性时使用。"
            },
            {
                "name": "tumor-only-somatic-variant-calling",
                "desc": "当用户只有肿瘤样本而缺少匹配正常样本，需要检测体细胞SNV和Indel并控制胚系与技术伪阳性时使用。"
            }
        ],
        "forensic-identity-genetics": [
            {
                "name": "19-forensic-genomics-ancestry-snp",
                "desc": "在法医基因组学领域开展“祖先SNP”任务时使用；根据输入、科学假设和运行环境，在SNP分析下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-ibd-analysis",
                "desc": "在法医基因组学领域开展“IBD分析”任务时使用；根据输入、科学假设和运行环境，在亲缘关系下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-identity-snp",
                "desc": "在法医基因组学领域开展“身份SNP”任务时使用；根据输入、科学假设和运行环境，在SNP分析下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-kinship-analysis",
                "desc": "在法医基因组学领域开展“亲缘关系分析”任务时使用；根据输入、科学假设和运行环境，在亲缘关系下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-mixture-analysis",
                "desc": "在法医基因组学领域开展“混合分析”任务时使用；根据输入、科学假设和运行环境，在STR分析下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-mtdna-haplogroup",
                "desc": "在法医基因组学领域开展“线粒体单倍群”任务时使用；根据输入、科学假设和运行环境，在Y染色体与mtDNA下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-str-genotyping",
                "desc": "在法医基因组学领域开展“STR分型”任务时使用；根据输入、科学假设和运行环境，在STR分析下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-vntr-profiling",
                "desc": "在法医基因组学领域开展“VNTR谱型”任务时使用；根据输入、科学假设和运行环境，在VNTR分析下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-y-snp",
                "desc": "在法医基因组学领域开展“Y染色体与mtDNA”任务时使用；根据输入、科学假设和运行环境，在Y染色体与mtDNA下已保留的方法实现之间路由。"
            },
            {
                "name": "19-forensic-genomics-y-str",
                "desc": "在法医基因组学领域开展“Y染色体与mtDNA”任务时使用；根据输入、科学假设和运行环境，在Y染色体与mtDNA下已保留的方法实现之间路由。"
            }
        ],
        "clinical-precision-medicine": [
            {
                "name": "18-precision-medicine-diagnostic-biomarker",
                "desc": "当用户需要评估诊断试验或诊断生物标志物的灵敏度、特异度、预测值、似然比、ROC/AUC或阈值时使用。"
            },
            {
                "name": "18-precision-medicine-patient-stratification",
                "desc": "当用户需要整合分子、临床和治疗信息划分患者亚组、风险层级或治疗决策组时使用。"
            },
            {
                "name": "18-precision-medicine-predictive-biomarker",
                "desc": "当用户需要评估亚组治疗效应、交互作用或异质性治疗效应并识别可能的反应人群时使用。"
            },
            {
                "name": "18-precision-medicine-prognostic-biomarker",
                "desc": "当用户需要从高维组学或多组学数据中筛选稳定、可复现的候选生物标志物时使用。"
            },
            {
                "name": "clinical-decision-support",
                "desc": "当用户需要把已经确认的临床证据和决策逻辑整理为可审计、可交接的决策支持材料时使用。"
            },
            {
                "name": "clinical-multimodal-llm-evaluation",
                "desc": "当用户需要评估放射报告生成、医学视觉问答或临床多模态LLM的正确性、忠实度和安全性时使用。"
            },
            {
                "name": "clinical-prediction-model-validation",
                "desc": "当用户需要审核或验证生物医学预测模型的数据泄漏、区分度、校准、临床净获益和可迁移性时使用。"
            },
            {
                "name": "molecular-trial-matching",
                "desc": "当用户需要依据疾病、分子变异、生物标志物和临床状态检索并排序适合的临床试验时使用。"
            },
            {
                "name": "prognostic-biomarker-survival-analysis",
                "desc": "当用户需要用生物标志物预测生存、复发或其他时间结局，并评估其独立预后价值时使用。"
            },
            {
                "name": "clinical-statistics-survival",
                "desc": "当用户需要设计或检查临床数据的描述统计、生存分析、回归模型和敏感性分析时使用。"
            }
        ],
        "medical-imaging-radiomics": [
            {
                "name": "20-ai-medical-imaging-ai-cnn-imaging",
                "desc": "当用户需要构建可复现的医学影像分类、分割、检测或迁移学习训练流程时使用。"
            },
            {
                "name": "20-ai-medical-imaging-ai-feature-extraction",
                "desc": "当用户需要设计或审核从影像ROI提取放射组学特征并建立临床预测模型的流程时使用。"
            },
            {
                "name": "20-ai-medical-imaging-ai-image-omics-fusion",
                "desc": "当用户需要整合放射影像、数字病理、组学和临床信息开展多模态研究时使用。"
            },
            {
                "name": "bids-neuroimaging-data-organization",
                "desc": "当用户需要组织、检查或转换符合BIDS规范的MRI、PET、EEG、MEG或其他神经影像研究数据时使用。"
            },
            {
                "name": "cancer-imaging-data-retrieval",
                "desc": "当用户需要按癌种、影像模态、临床或病理条件检索并下载可公开使用的癌症影像队列时使用。"
            },
            {
                "name": "dicom-processing-deidentification",
                "desc": "当用户需要读取、检查、转换或安全去标识DICOM影像与元数据时使用。"
            },
            {
                "name": "medical-image-analysis",
                "desc": "当用户需要在建模前检查医学影像采集网格、方向、强度、标签、重采样、归一化、增强和数据泄漏风险时使用。"
            },
            {
                "name": "medical-image-registration-resampling",
                "desc": "当用户需要用SimpleITK对CT、MRI或显微体数据进行刚体、仿射或形变配准，并安全重采样影像与标签时使用。"
            },
            {
                "name": "medical-imaging-model-trustworthiness",
                "desc": "当用户需要审核医学影像模型的数据泄漏、外部验证、校准、不确定性、OOD、可解释性或模型文档时使用。"
            },
            {
                "name": "neuroimaging-electrophysiology-analysis",
                "desc": "当用户需要分析fMRI、EEG或其他神经电生理数据，完成预处理、事件建模、连接性和受试者层统计时使用。"
            },
            {
                "name": "nfcore-liverctanalysis",
                "desc": "当肝脏 CT 数据需要分割或定量，而候选流程包含尚未实现该能力的历史模板时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/liverctanalysis。"
            },
            {
                "name": "nnu-net-medical-image-segmentation",
                "desc": "当用户拥有标注医学影像并需要规划、训练或评估nnU-Net分割流程时使用。"
            }
        ],
        "microscopy-cell-phenotyping": [
            {
                "name": "20-ai-medical-imaging-ai-whole-slide-image-analysis",
                "desc": "当用户需要对H&E或IHC全切片图像进行组织检测、切块、染色归一化、质量控制和特征提取时使用。"
            },
            {
                "name": "27-aging-longevity-sasp-analysis",
                "desc": "当用户需要综合生长停滞、损伤、SA-β-gal、p16/p21和SASP等正交证据判断细胞衰老时使用。"
            },
            {
                "name": "cellpose-cell-nucleus-segmentation",
                "desc": "当用户需要在荧光或明场显微图像中使用Cellpose分割细胞或细胞核并提取形态指标时使用。"
            },
            {
                "name": "scratch-wound-analysis",
                "desc": "当用户提供细胞划痕实验图片、ImageJ/Fiji测量结果或已有分割，希望测算划痕空白面积、看伤口还剩多少、比较不同时间点愈合情况、计算闭合率或批量处理图片时使用；也用于划痕分析反复报错、耗时异常、识别区域不对和结果复核…"
            },
            {
                "name": "microscopy-data-management",
                "desc": "当用户需要整理、入库、检索、标注、共享或导出显微影像及其元数据时使用。"
            },
            {
                "name": "microscopy-image-quantification",
                "desc": "当用户需要对显微图像或ImageJ、CellProfiler输出进行强度、形态、细胞计数和组间统计分析时使用。"
            },
            {
                "name": "nfcore-cellpainting",
                "desc": "当多通道细胞成像及处理条件需要生成形态特征用于比较时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/cellpainting。"
            },
            {
                "name": "nfcore-lsmquant",
                "desc": "当光片显微三维图像需要校正、对象识别或定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/lsmquant。"
            },
            {
                "name": "single-particle-tracking-diffusion",
                "desc": "当用户需要从视频显微图像定位颗粒、连接轨迹并计算MSD或扩散系数时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b11-t01",
                "desc": "用于质谱流式CyTOF数据的微球归一化、去条码、双联体和异常事件过滤；当原始FCS需要批次可比化时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b11-t02",
                "desc": "用于高参数流式或CyTOF数据的降维、无监督聚类、亚群注释和可视化；当传统门控无法覆盖复杂细胞状态时使用。"
            },
            {
                "name": "cytometry-differential-abundance-analysis",
                "desc": "用于比较流式/CyTOF细胞亚群丰度和标记状态的组间、纵向或配对差异；当聚类或门控结果已完成时使用。"
            },
            {
                "name": "fcs-qc-transformation",
                "desc": "用于读取FCS文件、审核通道与补偿信息、评估采集质量并完成合理变换；当流式或质谱流式数据进入分析前使用。"
            },
            {
                "name": "flow-cytometry-gating-analysis",
                "desc": "用于传统流式细胞术的层级门控、群体统计和跨样本模板应用；当用户提供FCS和实验面板并需要细胞群比例时使用。"
            },
            {
                "name": "nfcore-imcyto",
                "desc": "当成像质谱细胞术数据需要按标记通道分割细胞并提取特征时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/imcyto。"
            },
            {
                "name": "nfcore-mcmicro",
                "desc": "当多轮或多通道组织图像需要拼接、配准与细胞定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mcmicro。"
            },
            {
                "name": "pathml",
                "desc": "Comprehensive computational pathology toolkit. Covers both lightweight H&E tile extraction (tissue detection…"
            }
        ],
        "transcriptomics-quantification": [
            {
                "name": "nfcore-drop",
                "desc": "当患者 RNA 数据及适配参考队列需要寻找异常表达或剪接时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/drop。"
            },
            {
                "name": "nfcore-isoseq",
                "desc": "当已有 PacBio 全长 RNA 数据，希望整理转录本或辅助基因组注释时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/isoseq。"
            },
            {
                "name": "bulk-rnaseq",
                "desc": "End-to-end bulk RNA-seq orchestrator — takes raw FASTQ reads through QC and trimming (FastQC, fastp/Trim Galor…"
            },
            {
                "name": "04-transcriptomics-5-utr",
                "desc": "用于分析UTR、Kozak、IRES、uORF、poly(A)位点、密码子偏好和tRNA适配等转录后与翻译调控元件。"
            },
            {
                "name": "04-transcriptomics-alternative-splicing",
                "desc": "当用户问表达没变是否剪接变了、同一基因在不同细胞为何不同、长短读长结果矛盾，或需剪接和异构体状态证据整合（IsoformStateDB方向）时使用；先查读段、覆盖和注释，不要求用户选择算法或懂PSI。"
            },
            {
                "name": "04-transcriptomics-fusion-transcript-detection",
                "desc": "用于从RNA-seq检测基因融合或嵌合转录本，整理断点、分裂读段、跨越读段、阅读框和假阳性证据。"
            },
            {
                "name": "04-transcriptomics-m6a",
                "desc": "用于分析m6A、m5C等RNA修饰的富集区或候选位点；支持抗体富集、化学转换、交联和Nanopore直接RNA等不同证据。"
            },
            {
                "name": "04-transcriptomics-mirna-analysis",
                "desc": "用于按文库类型分析miRNA、lncRNA或circRNA的表达、注释、差异和候选调控关系。"
            },
            {
                "name": "04-transcriptomics-rbp-regulation",
                "desc": "用于从eCLIP、iCLIP及其他CLIP-seq协议定位RNA结合蛋白位点，并评估交联事件、背景、基序和重复一致性。"
            },
            {
                "name": "04-transcriptomics-ribo-seq",
                "desc": "用于从Ribo-seq读段校准P-site、评估三核苷酸周期性、识别翻译ORF，并与匹配RNA-seq联合估计翻译效率。"
            },
            {
                "name": "04-transcriptomics-rna-editing",
                "desc": "用于从RNA-seq识别A-to-I等RNA编辑候选，并排除胚系或体细胞DNA变异、链方向错误和比对伪影。"
            },
            {
                "name": "04-transcriptomics-rna-quantification",
                "desc": "当用户已有bulk RNA-seq测序文件、FASTQ或比对结果，想得到各样本基因表达量或后续分析用的矩阵，或遇到链特异性、片段偏倚、基因编号和参考注释不一致时使用；已有可用矩阵则转入适当下游，不重复定量。"
            },
            {
                "name": "04-transcriptomics-transcript-assembly",
                "desc": "用于从短读RNA-seq或长读RNA数据重建转录本、发现异构体、合并样本注释并控制组装膨胀。"
            },
            {
                "name": "nfcore-alleleexpression",
                "desc": "当RNA 数据及匹配基因型可用于研究等位基因表达不平衡时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/alleleexpression。"
            },
            {
                "name": "nfcore-cageseq",
                "desc": "当转录起始相关 CAGE 测序需要提取标签和起始位点时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/cageseq。"
            },
            {
                "name": "nfcore-circrna",
                "desc": "当RNA 测序需要识别环状 RNA 或比较反向剪接信号时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/circrna。"
            },
            {
                "name": "nfcore-clipseq",
                "desc": "当RNA 蛋白结合实验的 CLIP、iCLIP 或 eCLIP 数据需要处理时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/clipseq。"
            },
            {
                "name": "nfcore-dartseq",
                "desc": "当带编辑标记的 RNA 数据需要分析修饰相关位点时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/dartseq。"
            },
            {
                "name": "nfcore-denovotranscript",
                "desc": "当没有合适参考基因组，已有双端 RNA 测序并希望重建转录本时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/denovotranscript。"
            },
            {
                "name": "nfcore-dualrnaseq",
                "desc": "当共测定 RNA 数据来自宿主与病原，需要分别定量或研究感染反应时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/dualrnaseq。"
            },
            {
                "name": "nfcore-lncpipe",
                "desc": "当RNA 数据需要发现或整理长非编码 RNA 候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/lncpipe。"
            },
            {
                "name": "nfcore-nanostring",
                "desc": "当已有 nCounter 计数、探针 panel 或 RCC 交付数据，需要表达比较时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/nanostring。"
            },
            {
                "name": "nfcore-nascent",
                "desc": "当新生转录实验的 PRO、GRO 或 NET 类测序需要信号分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/nascent。"
            },
            {
                "name": "nfcore-riboseq",
                "desc": "当核糖体足迹测序需要定位翻译区域或估计翻译效率时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/riboseq。"
            },
            {
                "name": "nfcore-rnafusion",
                "desc": "当RNA 测序需要寻找融合转录本或复核融合候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnafusion。"
            },
            {
                "name": "nfcore-rnaseq",
                "desc": "当测序报告或建库证据表明是普通整体 RNA 测序，需要整理表达或比较样本时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnaseq。"
            },
            {
                "name": "nfcore-rnasplice",
                "desc": "当RNA 测序及样本分组用于研究可变剪接或转录本使用变化时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnasplice。"
            },
            {
                "name": "nfcore-rnastructurome",
                "desc": "当DMS 或 SHAPE 等 RNA 化学探测数据需要反应性或结构相关分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/rnastructurome。"
            },
            {
                "name": "nfcore-slamseq",
                "desc": "当代谢标记 SLAM-seq 数据需要估计新生 RNA 比例或动力学时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/slamseq。"
            },
            {
                "name": "nfcore-smrnaseq",
                "desc": "当小 RNA 建库数据需要识别 miRNA 或其他短 RNA 并定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/smrnaseq。"
            },
            {
                "name": "nfcore-stableexpression",
                "desc": "当多个表达数据集需要筛选在指定条件下稳定的参考基因时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/stableexpression。"
            },
            {
                "name": "rna-modification-clip",
                "desc": "| Peak analysis for RNA modification and RNA-protein interaction sequencing: MeRIP-seq/m6A (exomePeak2 peak ca…"
            }
        ],
        "differential-expression-enrichment": [
            {
                "name": "gwas-functional-interpretation",
                "desc": "当用户有疾病遗传关联结果，不知道涉及什么通路、组织或细胞类型、想补机制解释和富集图，或提出MAGMA/分层LDSC时使用；区分遗传信号富集与普通基因列表富集。"
            },
            {
                "name": "04-transcriptomics-b05-t03",
                "desc": "用于全量排序特征的GSEA以及GSVA、ssGSEA样本级基因集评分；当用户需要通路方向、leading-edge基因或每个样本的通路分数时使用。"
            },
            {
                "name": "pathway-enrichment",
                "desc": "Run pathway and gene-set enrichment analysis on gene lists or ranked gene data, then interpret the results. Us…"
            },
            {
                "name": "pathway-enrichment-analysis",
                "desc": "用于基因、蛋白或代谢物列表的GO、KEGG、Reactome等过度富集分析；当用户已有候选特征集合和明确背景集时使用。"
            },
            {
                "name": "pydeseq2",
                "desc": "Differential gene expression analysis for bulk RNA-seq with PyDESeq2, including formulaic designs, Wald tests…"
            },
            {
                "name": "04-transcriptomics-deseq2",
                "desc": "当用户已有bulk RNA-seq基因计数或差异分析结果，想知道两组哪些基因不同、制作差异基因热图，或遇到低表达、批次、配对、重复测量和结果冲突时使用；核查数据与设计后选择DESeq2、edgeR或limma-voom…"
            },
            {
                "name": "metabolomics-differential-multivariate-stats",
                "desc": "当用户需要对质控后的代谢矩阵进行样本级差异、PCA 和监督建模，并用正确验证识别批次驱动或过拟合结果时使用。"
            },
            {
                "name": "microbiome-differential-abundance",
                "desc": "用于微生物特征表的组成型差异丰度建模、协变量校正和结果解释；当用户询问哪些菌或通路在组间变化时使用。"
            },
            {
                "name": "nfcore-differentialabundance",
                "desc": "当已有表达或特征矩阵和样本背景，希望比较处理条件时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/differentialabundance。"
            },
            {
                "name": "pathway-enrichment-scaffold-replace",
                "desc": "当用户需要把带证据等级的代谢物及效应映射到物种匹配的通路，并控制 ID 歧义、检测背景和重复特征造成的偏倚时使用。"
            },
            {
                "name": "single-cell-differential-abundance",
                "desc": "当用户需要比较条件间离散细胞群或连续邻域的丰度变化，以供体为重复并处理组成数据的相互依赖时使用。"
            }
        ],
        "single-cell-core": [
            {
                "name": "scanpy",
                "desc": "Standard single-cell RNA-seq analysis pipeline. For quality control (QC), normalization, dimensionality reduct…"
            },
            {
                "name": "05-single-cell-virtual-cell-b01-t01",
                "desc": "当用户拿到单细胞表达文件不知道质量是否可用，想清理低质量细胞、查看过滤前后变化，或发现QC图空白、质量指标缺失、过滤后细胞骤减时使用；涵盖10x及其他scRNA-seq计数数据的预处理与质量控制。已有对象先核查当前阶段…"
            },
            {
                "name": "05-single-cell-virtual-cell-b01-t02",
                "desc": "当用户需要把 scATAC-seq FASTQ 或 fragments 转成经过条形码、片段质量和可及性检查的 tile/peak 矩阵时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b01-t03",
                "desc": "当用户需要处理 10x Multiome 等同细胞多模态数据，保持条形码配对，分别质控各模态后再建立联合表示时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b01-t04",
                "desc": "当用户需要整合多样本、平台或队列的单细胞数据，在减少技术差异的同时检测过校正和真实条件信号丢失时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b02-t01",
                "desc": "当用户需要按样本识别液滴单细胞数据中的异型和同型双细胞，并区分技术混合与真实过渡或活化状态时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b02-t02",
                "desc": "当用户需要估计 droplet scRNA-seq 空液滴中的环境 RNA，并在保留原始计数的前提下校正受污染细胞时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b02-t03",
                "desc": "当用户发现单细胞线粒体比例很高、全为零或缺失，想判断细胞质量、解释线粒体比例图，或担心过滤删掉真实细胞群时使用；结合组织、物种、基因标识和其他质量指标核验计算与过滤规则，不要求用户选择统一百分比阈值。"
            },
            {
                "name": "05-single-cell-virtual-cell-b03-t01",
                "desc": "当用户想把单细胞分成可靠群体、不知道该保留多少维或分多少群，已有PCA图看不懂、标签挤在一起，或UMAP结果不稳定时使用；涵盖PCA/LSI、邻居图与聚类，先检查质控对象和已有结果，不要求用户知道算法、软件或技术参数。"
            },
            {
                "name": "05-single-cell-virtual-cell-b04-t04",
                "desc": "当用户问这些细胞是什么、细胞名字是否正确、两种注释结果冲突、疾病细胞是否被误标，或需要细胞注释、参考映射、scDiagnostics诊断时使用；从对象、marker和参考主动识别注释及复核需要，保留未知、新状态和低置信标…"
            },
            {
                "name": "nfcore-hadge",
                "desc": "当单细胞混样数据需要借助基因型或样本标签恢复供者身份时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/hadge。"
            },
            {
                "name": "nfcore-marsseq",
                "desc": "当已确认板式 MARS-seq 数据，需要按孔位和分子标签整理表达时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/marsseq。"
            },
            {
                "name": "nfcore-scdownstream",
                "desc": "当收到单细胞表达矩阵、H5AD 或分析对象，需要细胞质控、注释与组间研究时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/scdownstream。"
            },
            {
                "name": "nfcore-scflow",
                "desc": "当已有历史单细胞表达对象，需要评估归档分析路径或复现处理时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/scflow。"
            },
            {
                "name": "nfcore-scnanoseq",
                "desc": "当单细胞长读 RNA 数据需要恢复细胞身份并分析转录本时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/scnanoseq。"
            },
            {
                "name": "nfcore-scrnaseq",
                "desc": "当建库或交付证据表明是单细胞 RNA 原始读段，需要生成细胞表达矩阵时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/scrnaseq。"
            },
            {
                "name": "nfcore-smartseq2",
                "desc": "当已确认板式 Smart-seq2 测序，需要按细胞或孔位整理表达时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/smartseq2。"
            },
            {
                "name": "single-cell-format-io",
                "desc": "当用户需要在 h5ad、Seurat、loom、10x HDF5/MTX 等格式间转换单细胞对象，并验证矩阵层、元数据和稀疏结构没有静默丢失时使用。"
            },
            {
                "name": "single-cell-staged-workflow",
                "desc": "当用户收到单细胞测序文件不知道从何开始、希望把数据分析成课题结果、需要从已有AnnData继续或恢复失败流程，或指定EISCA时使用；根据实际文件、建库和已完成阶段安排可复现的分阶段工作流，不要求用户认识Nextflow…"
            },
            {
                "name": "sc-rna-seq-analysis",
                "desc": "| Single-cell RNA-seq comprehensive analysis pipeline. Covers 17+ analysis modules: QC, decontX, doublet detec…"
            }
        ],
        "single-cell-advanced-virtual-cell": [
            {
                "name": "scgpt",
                "desc": "使用单细胞生物学基础模型 scGPT 对单细胞表达数据进行嵌入和注释。适用于：从 AnnData 生成细胞嵌入以进行聚类或整合；执行零样本或微调后的细胞类型注释；为扰动或基因调控网络任务生成基因级表示。对于 scVI 等…"
            },
            {
                "name": "scvi-tools",
                "desc": "使用 scvi-tools 对单细胞 RNA 测序数据进行概率建模——使用 scVI 获得批次校正的潜在空间，使用 scANVI 进行半监督标签转移，并执行贝叶斯差异表达分析。适用于整合多个 scRNA-seq 批次、生…"
            },
            {
                "name": "05-single-cell-virtual-cell-b05-t02",
                "desc": "当用户需要为细胞周期、应激、干扰素、耗竭等连续程序评分，并区分状态变化与细胞类型组成变化时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b06-t03",
                "desc": "当用户需要使用剪接动力学估计细胞状态变化方向，并结合转移模型评估潜在起始、终末状态和命运概率时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b06-t05",
                "desc": "当用户需要在有生物学连通依据的细胞谱系内重建分支和伪时间，并检验根节点、批次和供体对轨迹的影响时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b08-t04",
                "desc": "当用户问哪些细胞在互相影响、某基因是否参与细胞间传话、疾病或治疗前后通讯有何变化，或已有单细胞/细胞通讯结果却只有矩阵、缺网络弦图、图太乱或不同数据总出现相同分子时使用；涵盖配体–受体推断、条件比较、结果复用和适用图集。…"
            },
            {
                "name": "05-single-cell-virtual-cell-b09-t01",
                "desc": "当用户需要分析 CRISPR Perturb-seq、CRISPRi/a 数据，将 guide 可靠分配到细胞并估计扰动的平均效应和状态依赖效应时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b09-t04",
                "desc": "当用户需要使用已训练单细胞模型预测基因敲除、过表达或其他扰动后的表达状态，并评估训练域和校准限制时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b09-t05",
                "desc": "当用户需要利用单细胞基线和扰动图谱预测药物在不同细胞状态中的响应，并明确剂量、时间和训练域外推风险时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b10-t01",
                "desc": "当用户需要联合分析 CITE-seq 的 RNA 与抗体衍生标签，校正 ADT 背景并为每个细胞选择合理的模态权重时使用。"
            },
            {
                "name": "05-single-cell-virtual-cell-b10-t03",
                "desc": "当用户需要联合分析同一单细胞的基因组DNA与转录组数据，并关联变异、拷贝数、等位基因和表达状态时使用。"
            },
            {
                "name": "metabolite-mediated-cell-communication",
                "desc": "当用户问细胞释放的代谢物是否影响其他细胞、某代谢物或转运体与疾病微环境有什么关系，或已有MEBOCOST/代谢通讯结果却缺三层网络和证据图时使用；从单细胞及可用代谢数据推断通讯潜力。只有疾病或发表愿望时先检查问题与数据…"
            },
            {
                "name": "scvi-single-cell-probabilistic-modeling",
                "desc": "当用户需要使用 scVI、scANVI 或 totalVI 对单细胞计数进行概率表征、半监督标签迁移或 RNA-蛋白联合建模时使用。"
            },
            {
                "name": "secreted-protein-activity-inference",
                "desc": "当用户问哪种细胞因子可能让另一群细胞发生变化、某分泌蛋白是否解释接收细胞的基因变化，或已有NicheNet/MultiNicheNet活性结果却缺配体排名和靶基因图时使用；结合发送表达、受体与接收响应推断候选。只有疾病或…"
            },
            {
                "name": "single-cell-alternative-splicing",
                "desc": "当用户需要从单细胞或单核RNA测序研究外显子、剪接位点、内含子保留和细胞状态相关的可变剪接时使用。"
            },
            {
                "name": "single-cell-cohort-integration-meta-analysis",
                "desc": "当用户问换个队列还成立吗、细胞在什么阶段开始变、整合后结论相反，或需多队列单细胞状态复现与元分析（StateShiftAtlas方向）时使用；核验供体、状态和有序轴，自主选择可比较分析，不要求用户认识算法。"
            },
            {
                "name": "single-cell-genetic-variant-detection",
                "desc": "当用户想从单细胞数据找突变、判断不同部位细胞是否可能来自同一克隆、寻找遗传差异或祖源证据，或提到Monopogen-Indel时使用；先检查是否有带细胞标识的读段与参考，表达矩阵或伪时间不能替代遗传变异证据。"
            },
            {
                "name": "single-cell-transposon-expression",
                "desc": "当用户需要在单细胞 RNA 数据中估计转座元件家族或位点表达，并显式处理重复序列多重比对和基因重叠时使用。"
            },
            {
                "name": "transcriptomic-reverse-perturbation",
                "desc": "当用户已有或希望构建两个转录组状态的差异签名，需要利用遗传扰动响应参考库筛选可能模拟或逆转该变化的候选基因扰动，或明确要求用 RevPert 排序并解释候选驱动因子时使用。"
            },
            {
                "name": "21-biological-foundation-models-b04-t01",
                "desc": "当用户需要用scGPT为单细胞表达数据生成嵌入、辅助细胞类型注释或构建基因表示时使用。"
            }
        ],
        "spatial-omics": [
            {
                "name": "he-virtual-spatial-transcriptomics",
                "desc": "当用户需要用DeepSpot-M从H&E切片切块预测空间基因表达并评估适用性时使用。"
            },
            {
                "name": "06-spatial-omics-b05-t01",
                "desc": "当用户需要分析带空间坐标的染色质可及性或空间表观组数据，并识别空间调控区域、细胞状态和区域差异时使用。"
            },
            {
                "name": "06-spatial-omics-cell2location",
                "desc": "当用户需要利用匹配的单细胞参考估计空间 spot/bin 的细胞组成，或把细胞状态映射到组织位置，并量化参考缺失与映射不确定性时使用。"
            },
            {
                "name": "06-spatial-omics-spatial-domain-identification",
                "desc": "当用户需要根据表达、形态和物理邻接识别组织域与边界，并评估域在样本、尺度和算法之间是否稳定时使用。"
            },
            {
                "name": "06-spatial-omics-spatial-metabolomics",
                "desc": "当用户需要处理 MALDI、DESI 等质谱成像数据，建立可信离子图、空间代谢物注释和组织区域比较；适用于保留像素坐标的 MSI 任务时使用。"
            },
            {
                "name": "06-spatial-omics-spatial-microenvironment",
                "desc": "当用户问组织里谁挨着谁、肿瘤边缘哪些细胞可能互相影响、某分子信号是否集中在特定位置，或已有空间通讯结果却缺组织定位/邻域网络、图中连线过密，以及需要MISTy空间邻域贡献分析时使用；结合真实空间坐标、细胞组成与配体–受体…"
            },
            {
                "name": "nfcore-molkart",
                "desc": "当Resolve Molecular Cartography 交付数据需要整理分子坐标与细胞表达时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/molkart。"
            },
            {
                "name": "nfcore-panoramaseq",
                "desc": "当已确认原位阵列空间转录测序，需要将读段与空间位置关联时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/panoramaseq。"
            },
            {
                "name": "nfcore-pixelator",
                "desc": "当分子邻近测定的 PNA 或 MPX 数据需要分子图和细胞相关分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pixelator。"
            },
            {
                "name": "nfcore-sopa",
                "desc": "当空间图像与分子坐标需要联合分割、聚合和分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/sopa。"
            },
            {
                "name": "nfcore-spatialaxe",
                "desc": "当Xenium 或 Artera 交付数据需要检查空间细胞、分子与特征质量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/spatialaxe。"
            },
            {
                "name": "nfcore-spatialvi",
                "desc": "当Visium 计数与组织图像需要联合分析空间表达时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/spatialvi。"
            },
            {
                "name": "spatial-proteomics",
                "desc": "当用户需要分析 CODEX、IMC、MIBI 等多通道空间蛋白数据，完成通道校正、细胞分割、表型和组织邻域定量时使用。"
            },
            {
                "name": "spatial-transcriptomics",
                "desc": "当用户想知道组织中基因或细胞在哪里、哪些细胞相邻、换半径或分割后结论是否可靠，或交付Visium、Xenium、MERFISH文件及EISTA/SpatialRobust请求时使用；自主识别平台、坐标和阶段，保留spot…"
            },
            {
                "name": "21-biological-foundation-models-nicheformer",
                "desc": "当用户需要用Nicheformer分析空间转录组细胞表征、组织微环境或空间邻域时使用。"
            }
        ],
        "proteomics": [
            {
                "name": "27-aging-longevity-protein-aging-clock",
                "desc": "当用户需要把冻结的器官特异蛋白质衰老时钟应用到匹配面板的Olink NPX数据并解释年龄加速时使用。"
            },
            {
                "name": "07-proteomics-dia-proteomics",
                "desc": "当用户需要处理 DIA-PASEF、SWATH 等数据，选择谱图库或无库搜索，并获得带分层 FDR 和运行质量证据的肽段、蛋白定量时使用。"
            },
            {
                "name": "07-proteomics-lc-ms-ms",
                "desc": "当用户需要读取和整理蛋白质组 raw/mzML 数据，完成格式核验、质心与校准检查、谱图或色谱特征处理，为搜索和定量准备输入时使用。"
            },
            {
                "name": "07-proteomics-phosphorylation",
                "desc": "当用户需要分析磷酸化、乙酰化、泛素化等翻译后修饰的鉴定、位点定位、丰度变化及其与总蛋白变化的关系时使用。"
            },
            {
                "name": "07-proteomics-protein-quantification",
                "desc": "当用户需要把肽段强度、谱图计数或 label-free 信号汇总为可比较的蛋白丰度，并处理跨运行匹配、归一化和缺失时使用。"
            },
            {
                "name": "07-proteomics-skill-002",
                "desc": "当用户需要根据蛋白序列及可靠同源证据注释结构域、家族、GO 和功能，同时保留冲突、低覆盖与未知项时使用。"
            },
            {
                "name": "07-proteomics-tmt-proteomics",
                "desc": "当用户需要分析 TMT/iTRAQ 等等重标签蛋白质组，处理通道映射、同位素杂质、隔离干扰和跨批次桥接时使用。"
            },
            {
                "name": "affinity-proteomics-analysis",
                "desc": "当用户需要分析 Olink、SomaScan 等亲和试剂平台的 NPX/RFU 数据，正确处理板效应、检测限、探针版本和一蛋白多探针时使用。"
            },
            {
                "name": "nfcore-ddamsproteomics",
                "desc": "当已有历史 DDA 质谱交付数据，需要评估或复现肽段鉴定与蛋白定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/ddamsproteomics。"
            },
            {
                "name": "nfcore-diaproteomics",
                "desc": "当已确认 DIA 质谱与谱图库，需要色谱对齐及蛋白定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/diaproteomics。"
            },
            {
                "name": "nfcore-mspepid",
                "desc": "当已有 MS2 谱图，需要搜索肽段并评估鉴定可靠性时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mspepid。"
            },
            {
                "name": "nfcore-proteinannotator",
                "desc": "当蛋白 FASTA 需要识别结构域或功能特征时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/proteinannotator。"
            },
            {
                "name": "nfcore-proteinfamilies",
                "desc": "当多条蛋白序列需要聚类成家族，或向既有家族添加成员时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/proteinfamilies。"
            },
            {
                "name": "nfcore-proteogenomicsdb",
                "desc": "当有基因组、转录本或变异材料，需要构建适合质谱搜索的序列库时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/proteogenomicsdb。"
            },
            {
                "name": "nfcore-proteomicslfq",
                "desc": "当已有非标记蛋白质组质谱或历史结果，需要评估归档定量流程时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/proteomicslfq。"
            },
            {
                "name": "nfcore-quantms",
                "desc": "当定量质谱数据需要区分 DIA、非标记或同位素标签模式并核查历史处理时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/quantms。"
            },
            {
                "name": "nfcore-ribomsqc",
                "desc": "当核糖核苷质谱 QC 数据需要检查仪器或批次性能时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/ribomsqc。"
            },
            {
                "name": "peptide-identification-protein-inference",
                "desc": "当用户需要从 DDA/DIA MS/MS 谱图完成数据库搜索、分层 FDR 控制和透明的肽段到蛋白群推断时使用。"
            },
            {
                "name": "proteomics-quality-control",
                "desc": "当用户需要从仪器、鉴定和定量三个层次定位蛋白质组异常，并给出保留、重跑或剔除样本的证据时使用。"
            },
            {
                "name": "proteomics-quantification",
                "desc": "蛋白质组定量下游分析——把 MaxQuant / DIA-NN / Spectronaut / FragPipe 的输出转成可统计的蛋白矩阵，做过滤、归一化、缺失值处理、limma/DEqMS 差异分析、富集与交付。当用…"
            },
            {
                "name": "pyopenms",
                "desc": "Comprehensive mass spectrometry analysis platform covering both proteomics and metabolomics. PyOpenMS handles…"
            }
        ],
        "metabolomics-lipidomics": [
            {
                "name": "tooluniverse-metabolomics",
                "desc": "Comprehensive metabolomics research skill for identifying metabolites, analyzing studies, and searching metabo…"
            },
            {
                "name": "08-metabolomics-exposomics",
                "desc": "当用户需要整合环境化学物、外源代谢物和多来源暴露测量，完成证据分级、单暴露扫描和混合暴露分析时使用。"
            },
            {
                "name": "08-metabolomics-exposure-biomarker-discovery",
                "desc": "当用户需要从代谢组数据发现并验证诊断、预后或暴露标志物，重点防止预处理泄漏和只在单一队列有效的过拟合时使用。"
            },
            {
                "name": "08-metabolomics-flux-analysis",
                "desc": "当用户需要设计和分析 13C、15N 等示踪实验，校正天然丰度并从同位素体分布推断可识别的代谢流时使用。"
            },
            {
                "name": "08-metabolomics-icp-ms-analysis",
                "desc": "当用户需要对 ICP-MS 或 ICP-MS/MS 元素数据进行校准、内标和干扰校正，输出带检测限、回收率与单位的离子组/金属组结果时使用。"
            },
            {
                "name": "08-metabolomics-metabolite-identification",
                "desc": "当用户需要整合加合物、同位素、精确质量、MS/MS、保留时间和标准品，为代谢特征给出分级而非过度确定的身份时使用。"
            },
            {
                "name": "08-metabolomics-targeted-metabolomics",
                "desc": "当用户需要对 MRM、PRM 或其他标准曲线靶向数据完成峰积分、内标校正和浓度计算，并正确处理定量范围外结果时使用。"
            },
            {
                "name": "08-metabolomics-untargeted-metabolomics",
                "desc": "当用户需要将非靶向 LC-MS 或 GC-MS 原始数据转为可追溯的特征矩阵，并用空白、QC 和峰形证据限制假特征时使用。"
            },
            {
                "name": "ce-ms-metabolomics",
                "desc": "当用户需要处理毛细管电泳-质谱数据，校正迁移时间并可靠匹配极性和带电代谢物；适用于 CE 特有漂移与毛细管状态问题时使用。"
            },
            {
                "name": "dda-dia-acquisition-design",
                "desc": "当用户需要为代谢组和小分子 LC-MS/MS 选择 DDA 或 DIA，并依据色谱峰宽设计循环时间、TopN、窗口与碰撞能时使用。"
            },
            {
                "name": "ion-mobility-ccs-analysis",
                "desc": "当用户需要校准 DTIMS、TWIMS 或 TIMS 漂移数据，计算带不确定性的碰撞截面 CCS，并按一致实验条件辅助候选鉴别时使用。"
            },
            {
                "name": "lipidomics-analysis",
                "desc": "当用户需要对 LC-MS/MS 脂质数据进行类别感知的鉴定、命名和定量，并明确脂质分子种、sn 位点及双键位置的证据边界时使用。"
            },
            {
                "name": "metabolomics-normalization-batch-correction",
                "desc": "当用户需要利用空白、pooled QC、稀释系列和内标清理代谢组特征，校正运行漂移并评估是否保留真实生物变化时使用。"
            },
            {
                "name": "nfcore-metaboigniter",
                "desc": "当非靶向代谢组质谱数据需要提峰、对齐与特征注释时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/metaboigniter。"
            },
            {
                "name": "nmr-metabolomics",
                "desc": "当用户需要处理一维或多维 NMR 代谢谱，完成频域转换、相位和基线校正、对齐、峰拟合及可追溯定量时使用。"
            },
            {
                "name": "glycomics",
                "desc": "| Glycomics data analysis and glycan structure annotation. Covers data-type triage (N-glycan / O-glycan / inta…"
            },
            {
                "name": "lipidomics-annotation",
                "desc": "| Lipidomics annotation and lipid-specific analysis. Covers LIPID MAPS classification and shorthand notation (…"
            },
            {
                "name": "metabolomics-profiling",
                "desc": "代谢组学分析——非靶向 LC/GC-MS 与靶向定量峰表的 QC 过滤、归一化、变换、PCA/PLS-DA/OPLS-DA（含置换验证）、单变量差异、注释置信级、通路富集与交付。当用户给的是峰表（m/z × 样本）、代谢…"
            }
        ],
        "epigenomics-methylation": [
            {
                "name": "27-aging-longevity-dna-methylation-clock",
                "desc": "当用户需要用冻结的DNA甲基化时钟计算预测年龄、年龄加速或DunedinPACE衰老速度并评估适用域时使用。"
            },
            {
                "name": "deeptools",
                "desc": "NGS analysis toolkit. Used for BAM to bigWig conversion, quality control (correlation, PCA, fingerprint plots)…"
            },
            {
                "name": "03-epigenomics-atac-seq-analysis",
                "desc": "用于从bulk ATAC-seq FASTQ生成开放染色质峰、差异可及区域和质量诊断；当用户需要处理Tn5切点、共识峰或重复一致性时使用。"
            },
            {
                "name": "03-epigenomics-chip-seq-histone-analysis",
                "desc": "用于从组蛋白修饰ChIP-seq的IP与匹配input生成峰或宽域、信号轨道和差异富集结果。"
            },
            {
                "name": "03-epigenomics-chromatin-loop-detection",
                "desc": "用于从Hi-C、Micro-C或捕获Hi-C数据检测染色质环，注释增强子—启动子互作并比较互作强度。"
            },
            {
                "name": "03-epigenomics-cut-run",
                "desc": "用于处理CUT&RUN或CUT&Tag数据，并针对低背景、短片段、IgG对照和外源校准选择峰调用与归一化策略。"
            },
            {
                "name": "03-epigenomics-dmr-identification",
                "desc": "用于在组间识别差异甲基化位点与连续区域，并正确处理覆盖深度、生物学重复、空间相关和协变量。"
            },
            {
                "name": "03-epigenomics-dnase-seq-analysis",
                "desc": "用于从DNase-seq数据识别DNase超敏位点、生成切割信号轨道并比较染色质可及性。"
            },
            {
                "name": "03-epigenomics-enhancer-gene-association",
                "desc": "当用户问某基因受哪些区域调控、ATAC/ChIP peaks对应哪些基因、想围绕候选基因找调控区域或回应调控机制审稿意见，或需要peakScout双向映射与增强子靶基因证据整合时使用；从实际peaks和参考判断可做的分析…"
            },
            {
                "name": "03-epigenomics-enhancer-identification",
                "desc": "用于整合开放染色质与活性标记识别候选增强子；当具备H3K27ac、Mediator或BRD4等连续占据信号时，再按stitching和排序定义超级增强子。"
            },
            {
                "name": "03-epigenomics-footprinting-analysis",
                "desc": "用于在开放染色质或ChIP峰中做转录因子基序富集、位点扫描和Tn5/DNase足迹推断。"
            },
            {
                "name": "03-epigenomics-hi-c-analysis",
                "desc": "用于从Hi-C成对FASTQ构建接触矩阵，诊断连接产物、有效配对、距离衰减和可支持分辨率。"
            },
            {
                "name": "03-epigenomics-wgbs-analysis",
                "desc": "用于处理WGBS或RRBS数据，得到CpG及非CpG甲基化计数、覆盖与转换质量；当用户提供亚硫酸氢盐测序FASTQ时使用。"
            },
            {
                "name": "chromatin-compartment-tad-analysis",
                "desc": "用于从经过质控的Hi-C矩阵识别A/B区室、TAD和绝缘边界，并在统一分辨率下比较条件差异。"
            },
            {
                "name": "chromatin-state-allele-specific-analysis",
                "desc": "当用户需要用多种组蛋白或可及性信号分割染色质状态，或分析等位基因特异的表观调控差异时使用。"
            },
            {
                "name": "methylation-array-qc-deconvolution",
                "desc": "当用户需要处理Illumina甲基化芯片、完成探针与样本质控、归一化、批次检查和细胞比例去卷积时使用。"
            },
            {
                "name": "nfcore-atacseq",
                "desc": "当已确认 bulk ATAC-seq 数据，需要分析开放染色质与条件差异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/atacseq。"
            },
            {
                "name": "nfcore-callingcards",
                "desc": "当转录调控记录实验的插入位点或 Calling Cards 读段需要分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/callingcards。"
            },
            {
                "name": "nfcore-chipseq",
                "desc": "当已有免疫沉淀测序数据，需要定位蛋白或组蛋白修饰富集区域时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/chipseq。"
            },
            {
                "name": "nfcore-cutandrun",
                "desc": "当已知 CUT&RUN 或 CUT&Tag 实验，希望定位染色质靶标时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/cutandrun。"
            },
            {
                "name": "nfcore-epigenomesegmentation",
                "desc": "当多种表观信号需要整合为染色质状态时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/epigenomesegmentation。"
            },
            {
                "name": "nfcore-hic",
                "desc": "当Hi-C 测序数据需要生成接触矩阵或检查染色质空间结构时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/hic。"
            },
            {
                "name": "nfcore-hicar",
                "desc": "当已确认 HiCAR 共测定数据，需要整理染色质接触及相关信号时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/hicar。"
            },
            {
                "name": "nfcore-methylarray",
                "desc": "当收到甲基化芯片 IDAT 或相关信号，需要质控与差异甲基化分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/methylarray。"
            },
            {
                "name": "nfcore-methylong",
                "desc": "当长读长数据含修饰信号或标签，需要量化 DNA 甲基化时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/methylong。"
            },
            {
                "name": "nfcore-methylseq",
                "desc": "当转化化学相关 DNA 测序需要估计甲基化水平时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/methylseq。"
            },
            {
                "name": "nfcore-mnaseseq",
                "desc": "当MNase 消化测序数据需要分析核小体位置或占据变化时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mnaseseq。"
            },
            {
                "name": "nfcore-sammyseq",
                "desc": "当已有连续提取的染色质组分测序数据，需要分析组分差异或染色质状态时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/sammyseq。"
            },
            {
                "name": "epigenetics-drug-response-integration",
                "desc": "当用户需要联合甲基化、染色质或组蛋白信号与药敏、耐药或剂量反应数据，寻找表观调控型药物响应标志物时使用。"
            },
            {
                "name": "dna-methylation-wgbs",
                "desc": "| DNA methylation analysis skill covering two data tracks: bisulfite sequencing (WGBS / RRBS, single-base reso…"
            },
            {
                "name": "epigenomics-peak-calling",
                "desc": "| Epigenomics peak-calling and QC mainline for ChIP-seq, ATAC-seq and CUT&Tag/CUT&RUN: assay triage, alignment…"
            }
        ],
        "regulatory-network-sequence-models": [
            {
                "name": "borzoi",
                "desc": "使用 Borzoi 根据 DNA 序列预测全基因组功能轨迹（RNA-seq、CAGE、DNase、ChIP）。适用于评估变异对表达或染色质可及性的调控效应、生成某个基因组位点的预测覆盖轨迹，或根据预测轨迹差值确定非编码变…"
            },
            {
                "name": "differential-regulatory-network",
                "desc": "用于比较疾病与对照、处理前后或细胞状态之间的网络重连；当用户关注边或模块如何变化而非单基因差异时使用。"
            },
            {
                "name": "evo2",
                "desc": "使用长上下文基因组基础模型 Evo 2 对 DNA 序列进行评分、嵌入和生成。适用于计算逐核苷酸或逐序列似然以评估变异效应、嵌入基因组窗口供下游分类使用、根据前缀生成 DNA，以及跨物种评估调控区或编码区。"
            },
            {
                "name": "grn-inference-scaffold-replace",
                "desc": "用于从表达、染色质可及性或转录因子先验推断基因调控网络；当用户需要TF—靶基因关系或调控模块时使用。"
            },
            {
                "name": "network-pharmacology-analysis",
                "desc": "用于整合药物、靶点、疾病基因和通路形成可审计的网络药理学假设；当用户需要候选机制或联合靶点优先级时使用。"
            },
            {
                "name": "network-topology-community-analysis",
                "desc": "用于计算生物网络中心性、连通结构、社区和稳健性；当用户已有节点边表并希望寻找模块或关键节点时使用。"
            },
            {
                "name": "nfcore-diseasemodulediscovery",
                "desc": "当疾病相关基因及互作网络需要寻找候选疾病模块时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/diseasemodulediscovery。"
            },
            {
                "name": "sbml-network-modeling",
                "desc": "用于读取、检查、构建或转换SBML格式的反应网络模型；当用户处理动力学模型、代谢模型交换或模型可重复性时使用。"
            },
            {
                "name": "string",
                "desc": "用于从基因或蛋白列表构建、筛选和解释蛋白质互作网络；当用户需要分析PPI、枢纽蛋白或功能模块时使用。"
            },
            {
                "name": "temporal-gene-regulatory-network",
                "desc": "用于带时间点或轨迹顺序的表达数据推断动态调控关系；当用户关心调控先后、状态转换或延迟效应时使用。"
            },
            {
                "name": "wgcna-coexpression-network",
                "desc": "当用户想找疾病相关的一组协同变化基因、筛枢纽、把RNA与蛋白等组学联系起来、比较模块在不同队列是否稳定，或要求WGCNA/WGCNA+时使用；自主核实样本量、矩阵和配对关系，不能从单个基因或少量细胞假造共表达网络。"
            },
            {
                "name": "03-epigenomics-basenji",
                "desc": "用于用Borzoi、Basenji、Enformer、Akita、AlphaGenome等模型预测序列变异对表达、可及性或染色质结构的潜在影响。"
            },
            {
                "name": "04-transcriptomics-tf-activity-inference",
                "desc": "用于从表达数据和TF—靶基因regulon推断转录因子活性；当TF自身表达量不足以代表其调控状态时使用。"
            },
            {
                "name": "nfcore-tfactivity",
                "desc": "当表达和染色质可及性数据希望推断转录因子活动变化时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/tfactivity。"
            },
            {
                "name": "single-cell-regulatory-network",
                "desc": "当用户需要从单细胞 RNA、ATAC 或多组学数据构建带 motif、可及性和扰动支持的 TF-regulon 调控网络时使用。"
            },
            {
                "name": "21-biological-foundation-models-b01-t03",
                "desc": "当用户需要用Evo 2对长DNA序列进行似然评分、嵌入、变异效应比较或条件生成时使用。"
            },
            {
                "name": "plant-long-context-genome-modeling",
                "desc": "当用户研究水稻、拟南芥等植物的候选基因/调控区域，想比较长DNA片段或变异、寻找可辅助课题的序列模型证据，或指定BOTANIC-1时使用；先确定物种、参考、任务和模型资源，不因植物基因名自动生成预测。"
            },
            {
                "name": "arboreto",
                "desc": "Infer gene regulatory networks (GRNs) from gene expression data using scalable algorithms (GRNBoost2, GENIE3).…"
            }
        ],
        "microbiome-metagenomics": [
            {
                "name": "nfcore-detaxizer",
                "desc": "当原始序列可能混有宿主、污染物或其他物种，需要筛查或移除目标序列时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/detaxizer。"
            },
            {
                "name": "microbial-community-metabolic-network",
                "desc": "用于由MAG或菌株模型构建群落代谢互作网络并分析交叉喂养；当用户研究菌群功能分工或代谢依赖时使用。"
            },
            {
                "name": "nfcore-bacmodel",
                "desc": "当细菌基因组及培养背景需要建立代谢网络或预测生长能力时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/bacmodel。"
            },
            {
                "name": "09-metagenomics-16s-analysis",
                "desc": "用于从扩增子原始测序数据完成16S或ITS去噪、特征表构建、物种注释和基础质控；当用户提供FASTQ、样本表或询问扩增子分析流程时使用。"
            },
            {
                "name": "09-metagenomics-amr-gene-analysis",
                "desc": "用于宏基因组或菌株基因组的耐药基因、耐药突变和移动元件检测；当用户开展AMR监测或风险评估时使用。"
            },
            {
                "name": "09-metagenomics-host-microbiome-interaction",
                "desc": "当用户需要把微生物组成或功能与宿主基因、免疫、代谢或临床表型联合分析，并建立可验证互作证据时使用。"
            },
            {
                "name": "09-metagenomics-humann",
                "desc": "用于估计宏基因组的基因家族、反应和通路丰度，并拆分物种贡献；当用户询问微生物群落潜在功能组成时使用。"
            },
            {
                "name": "09-metagenomics-kraken2",
                "desc": "用于从宏基因组读段估计物种组成；当用户需要在Kraken2/Bracken的快速全读段分类与MetaPhlAn的标记基因谱之间选择或比较时使用。"
            },
            {
                "name": "09-metagenomics-mag-reconstruction",
                "desc": "用于宏基因组读段组装、分箱、MAG质量控制、去冗余和分类；当目标是恢复微生物基因组或新物种时使用。"
            },
            {
                "name": "09-metagenomics-pathway-prediction",
                "desc": "用于从16S ASV推测基因家族和通路组成；仅当没有宏基因组数据且用户接受预测性结果时使用。"
            },
            {
                "name": "bgc-identification-classification",
                "desc": "当用户需要从微生物预测蛋白 FASTA 使用 BGC-Prophet 识别并分类生物合成基因簇时使用；原始核酸序列的基因预测和后续代谢产物结构鉴定不属于本 Skill。"
            },
            {
                "name": "edna-metabarcoding-analysis",
                "desc": "用于环境DNA宏条形码数据的物种检出、污染控制和群落比较；当研究对象来自水体、土壤、沉积物或混合环境样本时使用。"
            },
            {
                "name": "metagenomics-analysis",
                "desc": "用于把宏基因组研究从原始读段质控串联到物种、功能、耐药和统计解释；当用户需要完整而非单点流程时使用。"
            },
            {
                "name": "nfcore-ampliseq",
                "desc": "当报告或引物证据表明是 16S、ITS 等扩增子测序，需要研究微生物群落时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/ampliseq。"
            },
            {
                "name": "nfcore-bacass",
                "desc": "当已确认细菌分离株测序，需要组装、修正与基因注释时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/bacass。"
            },
            {
                "name": "nfcore-bactmap",
                "desc": "当细菌菌株测序需要参考比对、变异比较或系统发育时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/bactmap。"
            },
            {
                "name": "nfcore-coproid",
                "desc": "当古粪便测序需要推断宿主来源并评估污染时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/coproid。"
            },
            {
                "name": "nfcore-createtaxdb",
                "desc": "当微生物分析需要适合目标样本与分类工具的数据库时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/createtaxdb。"
            },
            {
                "name": "nfcore-daamicrobiome",
                "desc": "当已有微生物计数或丰度表，需要比较条件间差异时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/daamicrobiome。"
            },
            {
                "name": "nfcore-funcprofiler",
                "desc": "当宏基因组或宏转录组读段需要估计群落功能组成时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/funcprofiler。"
            },
            {
                "name": "nfcore-funcscan",
                "desc": "当微生物组装或 MAG 需要筛查功能基因及天然产物相关候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/funcscan。"
            },
            {
                "name": "nfcore-hgtseq",
                "desc": "当已有可能涉及宿主与供体的序列数据，需要研究水平转移候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/hgtseq。"
            },
            {
                "name": "nfcore-mag",
                "desc": "当已确认混合微生物 shotgun 数据，需要组装并恢复微生物基因组时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mag。"
            },
            {
                "name": "nfcore-magmap",
                "desc": "当宏基因组或宏转录组数据需要映射至基因组集合并定量基因时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/magmap。"
            },
            {
                "name": "nfcore-metatdenovo",
                "desc": "当宏转录组或宏基因组读段缺少合适参考，需要从头组装与注释时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/metatdenovo。"
            },
            {
                "name": "nfcore-pathogenepidemiology",
                "desc": "当已确认特定病原体的测序与采样信息，需要基因组流行病学分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pathogenepidemiology。"
            },
            {
                "name": "nfcore-pathogensurveillance",
                "desc": "当连续采集的病原测序需要群体比较与监测时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/pathogensurveillance。"
            },
            {
                "name": "nfcore-phageannotator",
                "desc": "当基因组或宏基因组序列需要查找噬菌体及前噬菌体区域时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/phageannotator。"
            },
            {
                "name": "nfcore-plasmodiumdrugres",
                "desc": "当已有疟原虫等位基因表或微单倍型数据，需要汇总耐药相关标记时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/plasmodiumdrugres。"
            },
            {
                "name": "nfcore-taxprofiler",
                "desc": "当已确认非扩增子的混合微生物测序，需要识别物种与丰度时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/taxprofiler。"
            },
            {
                "name": "nfcore-tbanalyzer",
                "desc": "当结核分枝杆菌复合群测序需要分型及相关标记分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/tbanalyzer。"
            },
            {
                "name": "nfcore-vipr",
                "desc": "当已有病毒测序或历史结果，需要复核旧版共识和低频变异分析时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/vipr。"
            },
            {
                "name": "nfcore-viralmetagenome",
                "desc": "当非靶向混合样本测序需要发现并重建病毒基因组时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/viralmetagenome。"
            },
            {
                "name": "nfcore-viralrecon",
                "desc": "当已确认病毒测序，需要获得共识序列和变异结果时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/viralrecon。"
            },
            {
                "name": "strain-tracking-transmission-analysis",
                "desc": "用于样本间菌株相似性、定植持续性和潜在传播链分析；当用户有纵向、家庭、医院或暴发队列时使用。"
            },
            {
                "name": "mgm-microbiome-foundation-model",
                "desc": "当用户已有样本×微生物特征丰度表，并需要使用 MGM 构建语料、预训练、微调、预测、生成或重建时使用；原始读段质控、分类和丰度估计使用宏基因组插件。"
            },
            {
                "name": "scikit-bio",
                "desc": "Biological data toolkit. Sequence analysis, alignments, phylogenetic trees, diversity metrics (alpha/beta, Uni…"
            },
            {
                "name": "microbiome-diversity-analysis",
                "desc": "用于扩增子、宏基因组或物种丰度表的α多样性、β多样性及组间群落差异分析；当用户已有特征表和样本元数据时使用。"
            }
        ],
        "structural-biology-modeling": [
            {
                "name": "alphafold2",
                "desc": "使用 ColabFold 运行器和 AlphaFold2/AlphaFold2-Multimer 预测蛋白质单体、多聚体与复合物结构，并通过 pLDDT、ipTM 和 RMSD 评估预测与设计质量。"
            },
            {
                "name": "boltz",
                "desc": "使用 Boltz-2 预测蛋白质、核酸和小分子复合物结构（Passaro、Wohlwend 等，2025）。适用于针对靶标验证设计的结合蛋白、将蛋白质与 SMILES 或 CCD 配体共同折叠，或使用可选的结合亲和力预测…"
            },
            {
                "name": "chai1",
                "desc": "使用 Chai-1 基础模型（Chai Discovery，2024，github.com/chaidiscovery/chai-lab）预测蛋白质、核酸和小分子复合物结构。适用于从单个 FASTA 预测抗体—抗原或蛋白…"
            },
            {
                "name": "esmfold2",
                "desc": "使用 Biohub ESMFold2／ESMFold2-Fast 进行全原子共折叠，支持单序列和 MSA 模式以及蛋白质、DNA、RNA、配体（CCD／SMILES）和修饰残基；FoldBench 抗体–抗原 DockQ…"
            },
            {
                "name": "openfold3",
                "desc": "使用 OpenFold3 进行结构预测。OpenFold3 是 AlQuraishi 实验室开发的 AlphaFold3 开放权重 PyTorch 复现。适用于使用 Apache-2.0 许可的 AF3 复现模型预测蛋白…"
            },
            {
                "name": "12-structural-biology-alphafold2",
                "desc": "用于AlphaFold2或ColabFold的单体、同源多聚体结构预测和置信度解释；当用户提供蛋白序列并需要结构模型时使用。"
            },
            {
                "name": "12-structural-biology-alphafold3",
                "desc": "用于预测蛋白质—蛋白质、蛋白质—核酸等生物大分子复合物；当用户需要提出多链或多实体相互作用结构假设时使用。"
            },
            {
                "name": "12-structural-biology-b01-t04",
                "desc": "用于包含蛋白、配体、核酸或共价环境的全原子条件生成与设计；当传统骨架设计无法表达复杂化学约束时使用。"
            },
            {
                "name": "12-structural-biology-protein-mutation-enhancement",
                "desc": "用于评估突变对稳定性、界面、活性位点和构象的可能影响并排序候选；当用户提出定点突变或变体解释时使用。"
            },
            {
                "name": "cryo-em-structure-data-retrieval",
                "desc": "用于检索EMDB、PDB中的冷冻电镜密度图、原子模型和实验元数据；当用户需要复用或评估cryo-EM结构时使用。"
            },
            {
                "name": "molecular-dynamics",
                "desc": "用于蛋白或复合物分子动力学轨迹的稳定性、构象、相互作用和收敛分析；当用户提供轨迹、拓扑或模拟结果时使用。"
            },
            {
                "name": "nfcore-proteinfold",
                "desc": "当只有蛋白序列或链组成，希望预测三维结构时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/proteinfold。"
            },
            {
                "name": "protein-rna-interaction-prediction-design",
                "desc": "当用户问某蛋白是否结合某RNA、结合位置在哪里、如何比较候选RNA或设计能结合目标蛋白的RNA，或指定ProRB时使用；从分子身份、序列、约束和可用权重判断预测/设计模式，不要求结构文件或用户理解模型接口。"
            },
            {
                "name": "protein-structure-database-search",
                "desc": "用于按蛋白、基因、序列或结构域检索PDB与AlphaFold DB并选择合适结构；当后续需要对接、界面分析或结构解释时使用。"
            },
            {
                "name": "protein-structure-preparation",
                "desc": "用于对接、模拟或结构分析前修复PDB/mmCIF结构、确定质子化和处理缺失成分；当原始结构不能直接计算时使用。"
            },
            {
                "name": "protein-structure-quality-assessment",
                "desc": "用于实验或预测蛋白结构的几何、立体化学、模型—数据一致性和局部置信度检查；当模型要进入下游分析时使用。"
            },
            {
                "name": "protein-structure-similarity-search",
                "desc": "用于Foldseek快速搜索结构同源、远缘折叠和候选模板；当序列相似度不足或需要大规模结构比对时使用。"
            },
            {
                "name": "structure-geometry-interface-analysis",
                "desc": "用于测量残基距离、角度、接触、氢键、盐桥和蛋白界面；当用户需要解释突变、复合物或活性位点几何时使用。"
            }
        ],
        "chemoinformatics-drug-design": [
            {
                "name": "diffdock",
                "desc": "使用 DiffDock-L（Corso 等，2023/2024）预测小分子结合姿势。它通过盲扩散对接，在无需预定义搜索框的情况下将配体放入蛋白质口袋，并使用学习得到的置信度模型对样本排序。适用于将 SMILES 或 SD…"
            },
            {
                "name": "12-structural-biology-molecular-docking",
                "desc": "用于Vina等经典方法的蛋白质—小分子对接、姿势筛选和相互作用复核；当用户有受体结构、配体和候选结合位点时使用。"
            },
            {
                "name": "22-ai-ai-drug-discovery-docking-ai",
                "desc": "当用户需要用DiffDock、Boltz、Chai、EquiBind等AI模型预测蛋白质—配体结合姿势、共折叠结构或进行AI重评分时使用。"
            },
            {
                "name": "22-ai-ai-drug-discovery-dti-prediction",
                "desc": "当用户需要检索化合物与靶点之间的Ki、Kd、IC50、EC50等活性数值，并核对实验体系、单位和文献时使用。"
            },
            {
                "name": "22-ai-ai-drug-discovery-molecular-generation",
                "desc": "当用户需要进行从头分子生成、骨架或连接子改造，并在活性、选择性、ADMET、可合成性和多样性之间做多目标优化时使用。"
            },
            {
                "name": "22-ai-ai-drug-discovery-retrosynthesis-planning",
                "desc": "当用户需要为明确结构和立体化学的目标分子生成、比较并初步验证多步逆合成路线时使用。"
            },
            {
                "name": "27-aging-longevity-drug-repurposing",
                "desc": "当用户需要依据疾病机制、靶点、转录特征、现有药理和临床可行性，为已知药物寻找新适应证并排序时使用。"
            },
            {
                "name": "admet-prediction-scaffold-replace",
                "desc": "当用户需要用规则或计算模型预测吸收、分布、代谢、排泄、毒性、药物相似性和结构警报，并为早期化合物排序时使用。"
            },
            {
                "name": "binding-free-energy-pose-validation",
                "desc": "当用户需要检查对接或生成姿势的几何与物理有效性，或用RBFE/ABFE对类似物亲和力进行定量排序时使用。"
            },
            {
                "name": "candidate-toxicity-risk-assessment",
                "desc": "当用户需要在药物发现阶段整合结构警报、体外实验、动物毒理、毒理组学和暴露数据，判断候选化合物的器官与机制风险时使用。"
            },
            {
                "name": "chemical-scaffold-sar-analysis",
                "desc": "当用户需要用Bemis–Murcko骨架、匹配分子对、R基团分解或Free–Wilson模型分析化学系列、构效关系与活性悬崖时使用。"
            },
            {
                "name": "compound-commercial-availability",
                "desc": "当用户需要查找化合物供应商、货号、实时库存与价格，寻找可购买类似物，或构建可采购虚拟化合物库时使用。"
            },
            {
                "name": "compound-identity-lookup",
                "desc": "当用户按名称、CAS、CID、ChEMBL ID、SMILES或InChI查找化合物，并需要确认准确结构、盐型、立体化学或基础属性时使用。"
            },
            {
                "name": "conformer-shape-similarity",
                "desc": "当用户需要生成分子三维构象集合、进行能量优化，或开展三维形状与静电相似性搜索时使用。"
            },
            {
                "name": "covalent-inhibitor-design",
                "desc": "当用户需要围绕可反应残基设计可逆或不可逆共价抑制剂，并联合优化非共价定位、反应动力学和蛋白组选择性时使用。"
            },
            {
                "name": "drug-target-evidence-validation",
                "desc": "当用户需要综合疾病关联、人类遗传、功能实验、可成药性、安全性、结构和临床先例，对候选药物靶点作GO/NO-GO判断时使用。"
            },
            {
                "name": "gpcr-ligand-pharmacology",
                "desc": "当用户需要分析GPCR配体的激动、拮抗、反向激动、偏向信号、亚型选择性或正构/变构机制时使用。"
            },
            {
                "name": "molecular-descriptors-fingerprints",
                "desc": "当用户需要为QSAR、相似性检索或虚拟筛选计算理化描述符、Morgan/ECFP、MACCS及其他分子指纹时使用。"
            },
            {
                "name": "molecular-drug-discovery",
                "desc": "当用户需要从已验证靶点出发，整合口袋、已知配体、虚拟筛选、ADMET与合成可行性，形成苗头或先导化合物方案时使用。"
            },
            {
                "name": "molecular-similarity-substructure-search",
                "desc": "当用户需要用Tanimoto、Tversky、Dice或SMARTS，从化合物库中查找类似物、包含特定子结构的分子、结构警报或活性悬崖时使用。"
            },
            {
                "name": "molecule-standardization-format-conversion",
                "desc": "当用户需要清洗盐、溶剂、价态、互变异构体和立体化学，或在SMILES、InChI、SDF、MOL2、PDB等分子格式间转换时使用。"
            },
            {
                "name": "nfcore-drugresponseeval",
                "desc": "当药物反应和特征数据需要评估模型对新样本或新药的预测能力时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/drugresponseeval。"
            },
            {
                "name": "pharmacophore-modeling-screening",
                "desc": "当用户需要从活性配体或受体结合口袋建立三维药效团，并筛选满足关键空间特征的骨架跃迁候选物时使用。"
            },
            {
                "name": "protein-binding-pocket-detection",
                "desc": "用于识别和比较蛋白小分子结合口袋、评估可成药性并准备对接区域；当靶点缺少已知配体位点时使用。"
            },
            {
                "name": "qsar-modeling-scaffold-replace",
                "desc": "当用户需要从分子结构和实验标签建立活性、理化性质或ADMET预测模型，并评估外部性能、不确定性与适用域时使用。"
            },
            {
                "name": "targeted-protein-degradation-design",
                "desc": "当用户需要设计PROTAC、分子胶或其他靶向蛋白降解剂，并评估E3连接酶、连接子、三元复合物和细胞降解证据时使用。"
            },
            {
                "name": "virtual-screening-scaffold-replace",
                "desc": "当用户需要围绕蛋白质口袋，对化合物库执行受体准备、分阶段对接/重评分、富集验证和实验命中选择时使用。"
            }
        ],
        "protein-engineering-synbio": [
            {
                "name": "antibody-engineering-developability",
                "desc": "当用户需要开展抗体人源化、亲和力成熟、序列风险检查和聚集、稳定性等可开发性综合评估时使用。"
            },
            {
                "name": "fair-esm2",
                "desc": "使用 Meta AI 的 ESM-2（`fair-esm` 软件包）生成蛋白质嵌入。适用于提取残基级或序列级嵌入供下游机器学习使用、进行掩码语言模型似然或突变效应评分，以及根据序列预测接触图。"
            },
            {
                "name": "ligandmpnn",
                "desc": "使用 LigandMPNN（Dauparas 等，2023）在配体、核酸和金属环境下对蛋白质骨架进行逆折叠。适用于重新设计结合口袋中围绕已结合小分子或辅因子的残基、设计必须保持几何构型的金属配位位点，或从任意 MPNN…"
            },
            {
                "name": "proteinmpnn",
                "desc": "使用 ProteinMPNN（Dauparas 等，2022，github.com/dauparas/ProteinMPNN）将蛋白质骨架（PDB 结构）逆折叠为氨基酸序列。适用于对 RFdiffusion 骨架进行序列…"
            },
            {
                "name": "solublempnn",
                "desc": "使用 SolubleMPNN 对骨架进行逆折叠。SolubleMPNN 是在可溶性 PDB 子集上重新训练的 ProteinMPNN（Dauparas 等，2022），生成偏向胞质表达并减少聚集的序列。适用于普通 Pro…"
            },
            {
                "name": "12-structural-biology-b03-t05",
                "desc": "用于固定或部分固定蛋白骨架上的序列反向折叠，并结合LigandMPNN或约束保护功能位点；当用户需要骨架序列设计时使用。"
            },
            {
                "name": "12-structural-biology-b03-t07",
                "desc": "用于基于序列和结构识别聚集风险、设计表面突变并兼顾稳定性与功能；当用户遇到表达、沉淀或可溶性问题时使用。"
            },
            {
                "name": "26-synthetic-biology-metabolic-engineering",
                "desc": "当用户需要用基因组尺度代谢模型评估培养基、反应通量、基因扰动或产物优化策略时使用。"
            },
            {
                "name": "26-synthetic-biology-self-driving-lab",
                "desc": "当用户需要把液体处理实验转成可审查的板位、移液和设备操作方案并在执行前模拟时使用。"
            },
            {
                "name": "antimicrobial-peptide-mic-prediction",
                "desc": "当用户需要使用 APEX 对不超过 50 个氨基酸的肽序列预测内置病原体特异性抗菌活性或 MIC 时使用；新肽生成、分子对接和内置病原体以外的外推不使用本 Skill。"
            },
            {
                "name": "cell-free-protein-expression-optimization",
                "desc": "当用户需要选择无细胞蛋白质合成体系并区分模板、表达、可溶性或活性导致的低产问题时使用。"
            },
            {
                "name": "esm",
                "desc": "当用户需要用ESM-2生成蛋白质序列或残基嵌入、掩码语言模型分数、突变效应分数或接触预测时使用。"
            },
            {
                "name": "esm3-protein-generation-structure-modeling",
                "desc": "当用户需要用ESM3或ESM C进行蛋白质序列生成、逆折叠、结构条件设计或通用蛋白质表示时使用。"
            },
            {
                "name": "nfcore-deepmutscan",
                "desc": "当突变文库的选择前后或时间序列测序需要估计变异适应度时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/deepmutscan。"
            },
            {
                "name": "rfdiffusion",
                "desc": "用于围绕靶表面生成蛋白骨架、序列化并筛选结合蛋白；当用户要设计新的蛋白结合剂或界面时使用。"
            }
        ],
        "gene-editing-cloning": [
            {
                "name": "26-synthetic-biology-gene-design",
                "desc": "当用户需要在Gibson、Golden Gate等组装方式之间选择并设计片段连接和构建验证时使用。"
            },
            {
                "name": "base-editing-design-scaffold-replace",
                "desc": "当用户需要设计CBE或ABE碱基编辑并比较目标产物、旁观者编辑和脱靶风险时使用。"
            },
            {
                "name": "construct-motif-scanning-logo",
                "desc": "当用户需要检查合成启动子、UTR、载体或其他设计构建中的固定、IUPAC或PWM/PSSM基序，并输出位点坐标或序列Logo时使用。"
            },
            {
                "name": "crispr-screen-hit-analysis",
                "desc": "当用户需要从已通过质控的混合CRISPR筛选计数中选择合适统计模型并获得可复验命中基因时使用。"
            },
            {
                "name": "crispr-screen-library-design",
                "desc": "当用户需要为全基因组或聚焦CRISPR筛选设计可合成、可克隆且覆盖充分的混合导向RNA文库时使用。"
            },
            {
                "name": "crispr-screen-quality-control",
                "desc": "当用户需要在命中分析前判断CRISPR筛选文库是否经历覆盖损失、重复失真或生物学信号不足时使用。"
            },
            {
                "name": "grna-design-scaffold-replace",
                "desc": "当用户需要为单基因CRISPR敲除、CRISPRi或CRISPRa选择少量高质量导向RNA并安排实验验证时使用。"
            },
            {
                "name": "hdr-donor-template-design",
                "desc": "当用户需要为CRISPR点突变、标签或片段敲入选择供体形式并设计同源臂与鉴定方案时使用。"
            },
            {
                "name": "nfcore-crisprseq",
                "desc": "当CRISPR 编辑扩增子或混池筛选数据需要评估编辑或筛选命中时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/crisprseq。"
            },
            {
                "name": "nfcore-crisprvar",
                "desc": "当CRISPR 靶向编辑数据需要复核历史 NHEJ 或 HDR 评估时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/crisprvar。"
            },
            {
                "name": "off-target-prediction-off-target-scaffold",
                "desc": "当用户需要枚举CRISPR导向RNA的潜在全基因组脱靶位点、排序风险并规划验证实验时使用。"
            },
            {
                "name": "pcr-qpcr-primer-design",
                "desc": "当用户需要为常规扩增、基因编辑鉴定或qPCR生成并筛选具有合适特异性和扩增性能的引物时使用。"
            },
            {
                "name": "restriction-enzyme-digest-map",
                "desc": "当用户需要根据DNA拓扑和序列选择克隆或鉴定用限制酶、计算片段并绘制酶切图时使用。"
            }
        ],
        "pharmacogenomics-dosing": [
            {
                "name": "17-pharmacogenomics-adverse-drug-reaction-prediction",
                "desc": "当用户需要综合药品标签、临床试验、自发不良事件、药物基因组和文献证据，评估已进入临床使用药物的安全性信号时使用。"
            },
            {
                "name": "17-pharmacogenomics-cyp450-analysis",
                "desc": "用于从基因型、VCF或拷贝数结果推断CYP2D6、CYP2C19等药物代谢基因星等位基因和表型；当用户需要PGx单倍型解释时使用。"
            },
            {
                "name": "17-pharmacogenomics-drug-response-prediction",
                "desc": "用于综合PGx基因型及HLA分型与药物疗效、毒性和超敏反应证据；当用户需要区分可行动和研究性基因—药物关系时使用。"
            },
            {
                "name": "17-pharmacogenomics-tacrolimus-dosing",
                "desc": "用于结合CYP3A5等基因型和移植临床因素解释他克莫司起始剂量；当用户明确询问他克莫司PGx剂量时使用。"
            },
            {
                "name": "17-pharmacogenomics-warfarin-dosing",
                "desc": "用于结合VKORC1、CYP2C9、CYP4F2和临床因素解释华法林起始剂量模型；当用户明确询问华法林药物基因组剂量时使用。"
            },
            {
                "name": "cpic-dpwg-guideline-interpretation",
                "desc": "用于将CPIC或DPWG药物基因组指南映射到患者基因型、表型和具体药物；当用户需要解释而非自行发明剂量规则时使用。"
            },
            {
                "name": "drug-interaction-pk-pd-modeling",
                "desc": "当用户需要评估多药CYP与转运体相互作用，或联合暴露和药效终点建立PK-PD模型时使用。"
            },
            {
                "name": "noncompartmental-pk-analysis",
                "desc": "当用户需要从给药后的浓度-时间数据计算Cmax、Tmax、AUC、半衰期、清除率和表观分布容积时使用。"
            },
            {
                "name": "pharmacogenomics-clinical-report",
                "desc": "用于把PGx检测结果整理成面向临床的基因型、表型、证据和行动提示报告；当分析已完成并需要结构化交付时使用。"
            },
            {
                "name": "pharmacogenomics-evidence-retrieval",
                "desc": "用于检索基因—药物关系、变异注释、药品标签和指南证据；当用户询问某基因型与药物的已知关联时使用。"
            }
        ],
        "immunology-immuno-oncology": [
            {
                "name": "16-immunomics-antibody-lineage",
                "desc": "用于BCR克隆家族划分、体细胞高突变、胚系推断和抗体谱系树重建；当用户研究亲和成熟或抗体进化时使用。"
            },
            {
                "name": "16-immunomics-clonotype-analysis",
                "desc": "用于比较TCR/BCR克隆多样性、扩增、共享和纵向持续性；当用户已有标准化克隆型表和样本元数据时使用。"
            },
            {
                "name": "16-immunomics-epic",
                "desc": "用于从批量表达数据估计免疫和基质细胞组成；当用户需要比较CIBERSORTx、xCell、EPIC、TIMER等方法，或需要高分辨率去卷积时使用。"
            },
            {
                "name": "16-immunomics-hla-hd",
                "desc": "用于WGS、WES或RNA-seq的HLA与KIR等位基因分型及质量复核；当用户需要免疫遗传背景、新抗原或药物关联输入时使用。"
            },
            {
                "name": "16-immunomics-ssgsea-immune-score",
                "desc": "用于ssGSEA免疫评分、免疫检查点表达及其与细胞浸润或临床特征的关联；当用户需要描述免疫状态而非直接预测疗效时使用。"
            },
            {
                "name": "16-immunomics-tcr-repertoire",
                "desc": "用于TCR或BCR测序数据的V(D)J比对、克隆型构建和受体库质控；当用户提供AIRR-seq、单细胞VDJ或受体序列时使用。"
            },
            {
                "name": "16-immunomics-tide",
                "desc": "用于TIDE、IPS、SubMap等免疫治疗反应评分的计算、比较和外部验证；当用户研究检查点抑制剂获益预测时使用。"
            },
            {
                "name": "16-immunomics-tumor-antigen-prediction",
                "desc": "用于从体细胞变异、融合、异常剪接或肿瘤抗原生成并筛选候选表位；当用户需要个体化新抗原或疫苗候选时使用。"
            },
            {
                "name": "mhc-binding-prediction-scaffold-replace",
                "desc": "用于预测肽段与MHC-I/II结合、加工和呈递优先级；当用户给出蛋白序列、突变或HLA等位基因并需要筛选候选肽时使用。"
            },
            {
                "name": "nfcore-airrflow",
                "desc": "当BCR 或 TCR 受体库测序需要重排注释、克隆识别及比较时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/airrflow。"
            },
            {
                "name": "nfcore-epitopeprediction",
                "desc": "当抗原序列或变异需要预测可能的 MHC 呈递表位时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/epitopeprediction。"
            },
            {
                "name": "nfcore-hlatyping",
                "desc": "当WGS、WES 或 RNA 数据需要推断 HLA 等位基因时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/hlatyping。"
            },
            {
                "name": "nfcore-metapep",
                "desc": "当微生物蛋白或组装需要生成并筛选 MHC 肽候选时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/metapep。"
            },
            {
                "name": "nfcore-mhcquant",
                "desc": "当MHC 洗脱肽质谱需要免疫肽鉴定与定量时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/mhcquant。"
            },
            {
                "name": "tcr-bcr-antigen-specificity-prediction",
                "desc": "用于根据受体序列、配对链和已知数据库预测TCR或BCR潜在抗原特异性；当用户要筛选候选受体—抗原关系时使用。"
            },
            {
                "name": "vaccine-epitope-hla-coverage-design",
                "desc": "当用户需要联合T细胞或B细胞表位、抗原保守性和目标人群HLA频率设计候选疫苗并评估覆盖时使用。"
            },
            {
                "name": "immunogenomics",
                "desc": "| Immunogenomics workflow reference: TCR/BCR immune repertoire reconstruction (MiXCR, TRUST4), MHC class I/II…"
            }
        ],
        "literature-evidence-synthesis": [
            {
                "name": "bibliography",
                "desc": "Classifies and organizes literature by theme, method, and conclusion; use when you need to batch-read a folder…"
            },
            {
                "name": "biomedical-knowledge-graph-rag",
                "desc": "当用户需要把论文、数据库和内部资料组织成可检索的生物医学知识图谱或 RAG 问答系统时使用。"
            },
            {
                "name": "citation-management",
                "desc": "Comprehensive citation management for academic research. Search Google Scholar and PubMed for papers, extract…"
            },
            {
                "name": "evidence-validation",
                "desc": "当用户需要评价论文、数据库结果或实验发现的证据强度、偏倚和可复现性时使用。"
            },
            {
                "name": "github-deep-research",
                "desc": "Conduct multi-round deep research on any GitHub Repo. Use when users request comprehensive analysis, timeline…"
            },
            {
                "name": "literature-evidence-writing",
                "desc": "当用户需要系统检索生物医学文献、整理证据并撰写带准确引用的科研文本时使用。"
            },
            {
                "name": "literature-review",
                "desc": "查找、核验并综合科学文献——从“X 领域的奠基性论文是哪篇”到完整的多来源综述。涵盖以真实检索到的来源支撑论断、避免伪造引文、处理撤稿，以及根据证据强度校准置信程度。"
            },
            {
                "name": "literature-statistics",
                "desc": "Generate statistics for publication-year and journal distributions from local references or PDFs; use when you…"
            },
            {
                "name": "medical-research-literature-reader-pro",
                "desc": "A medical-research-native literature reading skill for users with clinical, bioinformatics, translational, and…"
            },
            {
                "name": "paper-lookup",
                "desc": "Search 10 academic paper databases via REST APIs for research papers, preprints, and scholarly articles. Cover…"
            },
            {
                "name": "paper-review",
                "desc": "Use this skill for \\\"review this paper\\\", \\\"review this manuscript\\\", \\\"peer review\\\", \\\"review my paper\\\", \\\"…"
            },
            {
                "name": "review-paper",
                "desc": "当需要审稿、论文评审、paper review、manuscript review、reference verification、fact checking、逐章评审、参考文献核验、评分或给出审稿意见时使用。"
            },
            {
                "name": "surveymaster",
                "desc": "Produce, revise, or export an academic literature survey through an end-to-end workflow: intake constraints, b…"
            }
        ],
        "writing-document-delivery": [
            {
                "name": "academic-poster-generator",
                "desc": "Complete workflow for generating academic research posters from PDF literature; use when you need to extract p…"
            },
            {
                "name": "article-format-adjustment",
                "desc": "Adjust academic paper formatting and convert between DOCX/LaTeX/Markdown when you need to meet a journal or sc…"
            },
            {
                "name": "arxiv-preflight",
                "desc": "Run a submission-readiness preflight on a manuscript before arXiv upload. Use when the user is preparing an ar…"
            },
            {
                "name": "bioinformatics-writer",
                "desc": "Triage and execute bioinformatics requests by first asking whether the user wants manuscript writing, data/exp…"
            },
            {
                "name": "blind-review-sanitizer",
                "desc": "Use blind-review-sanitizer for academic writing workflows that need structured anonymization, explicit assumpt…"
            },
            {
                "name": "clinical-research-reporting",
                "desc": "当用户需要把临床研究数据和统计结果整理成结构清楚、可复核的研究报告、摘要或结果章节时使用。"
            },
            {
                "name": "docx",
                "desc": "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Trig…"
            },
            {
                "name": "docx-equation-processor",
                "desc": "Use this skill when Word .docx work involves math formulas, equations, LaTeX, MathML, OMML, MathType, equation…"
            },
            {
                "name": "general-writer",
                "desc": "Write, revise, structure, or audit evidence-grounded academic papers across disciplines from supplied literatu…"
            },
            {
                "name": "grant-writing-agent",
                "desc": "面向中文科研基金申报书的少打断式写作、评审和自动 Word 交付 Skill。用于国家自然科学基金等中文基金申请中的选题梳理、立项依据、研究现状、研究内容、研究目标、关键科学问题、技术路线和创新点写作，也用于诊断申报书逻…"
            },
            {
                "name": "html-to-pdf",
                "desc": "Convert HTML files or URLs to high-fidelity PDFs using Puppeteer; auto-detects or forces RTL for Hebrew/Arabic…"
            },
            {
                "name": "latex-posters",
                "desc": "Create professional research posters in LaTeX using beamerposter, tikzposter, or baposter. Support for confere…"
            },
            {
                "name": "md-to-docx",
                "desc": "Convert Markdown files to professionally formatted Word (.docx) documents with embedded PNG images — pure Java…"
            },
            {
                "name": "methods-section-writer",
                "desc": "Turns your protocol and analysis workflow into publication-ready Methods text. Use when writing or revising th…"
            },
            {
                "name": "pdf",
                "desc": "Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text…"
            },
            {
                "name": "ppt-builder",
                "desc": "对齐 researcher/graph_pptx_agent 的状态化 PPT/PPTX 生成流程，覆盖需求澄清、研究规划、outline 确认、简体中文生图语言门禁、批量生成、版本记录、编辑循环和导出。"
            },
            {
                "name": "ppt-reader",
                "desc": "Read and analyze local PowerPoint PPTX/POTX presentations, extracting slide text, tables, and speaker notes. O…"
            },
            {
                "name": "reporting-guideline-compliance-checker",
                "desc": "Checks biomedical manuscripts against reporting guidelines such as CONSORT, STROBE, PRISMA, and TRIPOD to iden…"
            },
            {
                "name": "tex-to-docx",
                "desc": "Convert LaTeX or Markdown manuscripts into validated journal-ready DOCX files, with journal configuration, CSL…"
            },
            {
                "name": "xlsx",
                "desc": ">- Use whenever an Excel workbook (.xlsx, .xlsm, .xls, .xlsb) must be read, inspected, extracted, converted, c…"
            }
        ],
        "data-engineering-statistics": [
            {
                "name": "cdisc-clinical-data-standardization",
                "desc": "当用户需要把临床研究数据映射、检查或准备为SDTM、ADaM等CDISC结构，并形成可追踪的数据交付时使用。"
            },
            {
                "name": "fhir-ehr-interoperability",
                "desc": "当用户需要把电子病历映射为FHIR资源、设计查询或交换流程，并处理术语、版本、患者匹配和隐私边界时使用。"
            },
            {
                "name": "bioinformatics-format-conversion-integrity",
                "desc": "当用户需要在 FASTA、FASTQ、SAM、BAM、CRAM、BIOM、TSV 或常见丰度表布局之间转换，并核对转换前后记录、配对关系和校验值时使用；分子结构格式转换不使用本 Skill。"
            },
            {
                "name": "data-processing-tables",
                "desc": "当用户需要清理、合并、核对或汇总 CSV、TSV、Excel 等科研表格数据时使用。"
            },
            {
                "name": "exploratory-data-analysis-statistical-tests",
                "desc": "当用户需要检查科研表格的数据质量、分布、关联和异常值，或为连续、分类、配对及多组数据选择并执行通用统计检验时使用；生存结局和专门组学模型使用对应领域 Skill。"
            },
            {
                "name": "instrument-data-standardization",
                "desc": "当用户需要把不同实验仪器的原始导出转成统一、可交换且保留元数据的数据结构时使用。"
            },
            {
                "name": "machine-learning-evaluation",
                "desc": "当用户想用疾病或基因数据做预测、筛标志物、比较模型、检查论文里的高准确率，或发现换样本结果不变、验证失败、怀疑泄漏时使用；根据特征、标签和实际切分主动检查有效性，不要求用户知道AUROC、图神经网络或审计方法。"
            },
            {
                "name": "nfcore-deepmodeloptim",
                "desc": "当已有生物医学训练数据和模型，希望改善预测效果或评估数据增强时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/deepmodeloptim。"
            },
            {
                "name": "omics-negative-control-calibration",
                "desc": "当用户担心碰巧显著、随机分组也有差异、需要回应负对照质疑，或有供体级数值需置换校准（NullOmics）时使用；自主识别独立、分块和配对设计，模型泄漏转模型评估，不因发文章或阴性结果随意重跑。"
            },
            {
                "name": "output-fidelity-lock",
                "desc": "当代理的任何输出（翻译、转写、改写、报告、表格、图注、JSON 或传给下游脚本的参数）需要复述输入中的基因、编号、样本名、数值、单位、日期、金额、序列或表格时使用；用户反映“名字被翻译了”“版本号没了”“两个基因的数值换…"
            },
            {
                "name": "research-data-privacy-deidentification",
                "desc": "当用户需要识别、移除或降低科研数据中的个人身份、基因组再识别和敏感元数据风险时使用。"
            },
            {
                "name": "shap",
                "desc": "当用户需要用SHAP解释生物医学表格模型、检查加和性与相关特征影响，并生成全局和个体级解释报告时使用。"
            },
            {
                "name": "software-engineering-testing",
                "desc": "当用户需要编写、重构或验证用于生物医学分析的科研软件、命令行工具或数据处理代码时使用。"
            },
            {
                "name": "10-multi-omics-integration-diablo",
                "desc": "用于DIABLO/mixOmics的监督式多组学分类、特征选择和跨组学相关模块发现；当用户有明确类别标签和配对样本时使用。"
            },
            {
                "name": "10-multi-omics-integration-early-integration",
                "desc": "用于多组学整合前的样本映射、特征统一、尺度变换、批次处理和缺失审计；当不同平台数据无法直接对齐时使用。"
            },
            {
                "name": "10-multi-omics-integration-late-integration",
                "desc": "用于把多组学模型结果整理为可解释的通路、模块、标志物和验证计划；当整合模型已产生因子、网络或特征集时使用。"
            },
            {
                "name": "10-multi-omics-integration-mofa",
                "desc": "用于通过MOFA/MOFA+提取跨组学潜在因子、解释变异来源和处理部分缺失；当任务以无监督结构发现为主时使用。"
            },
            {
                "name": "10-multi-omics-integration-omics-network-fusion",
                "desc": "用于Similarity Network Fusion融合多组学样本相似性并发现分型；当各数据层尺度不同但样本配对完整时使用。"
            },
            {
                "name": "nfcore-omicsgenetraitassociation",
                "desc": "当多组学数据与性状希望建立基因或特征层关联时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/omicsgenetraitassociation。"
            },
            {
                "name": "biomedical-time-series-forecasting",
                "desc": "当用户需要使用TimesFM等基础模型预测生命体征、组学纵向指标或实验监测序列，并评估泄漏、区间和异常时使用。"
            },
            {
                "name": "gtars",
                "desc": "High-performance toolkit for genomic interval analysis in Rust with Python bindings. Use when working with gen…"
            },
            {
                "name": "polars-bio",
                "desc": "High-performance genomic interval operations and bioinformatics file I/O on Polars DataFrames. Overlap, neares…"
            },
            {
                "name": "pysam",
                "desc": "Genomic file toolkit. Read/write SAM/BAM/CRAM alignments, VCF/BCF variants, FASTA/FASTQ sequences, extract reg…"
            },
            {
                "name": "tiledbvcf",
                "desc": "Efficient storage and retrieval of genomic variant data using TileDB. Scalable VCF/BCF ingestion, incremental…"
            }
        ],
        "workflow-reproducibility": [
            {
                "name": "bioinformatics-agent-reliability-evaluation",
                "desc": "当用户明确要比较生信助手、检查自动分析是否编造、评估升级回归或建立失败基准（BioAgent Failure Atlas），且有案例或记录时使用；组织冻结判据及产物审计，普通分析失败先回原流程，不要求科研新手设计测试。"
            },
            {
                "name": "biomedical-result-drift-audit",
                "desc": "当用户说更新数据库后结果变了、以前显著现在没有、注释或排名不一致，或需比较两版资源影响（BioDataDrift）时使用；核验运行条件，已有结果比较漂移、有两版映射可固定背景重算，不要求用户理解哈希或参数。"
            },
            {
                "name": "infrastructure-workflows",
                "desc": "当用户需要建立可复现的科研计算环境、容器、工作流编排和运行记录时使用。"
            },
            {
                "name": "nfcore-catalog",
                "desc": "当用户只有测序公司或科研平台交付的文件、仅知道样本来源，不清楚数据类型、能研究什么或如何分析时使用；先识别数据与处理阶段，再根据研究问题自主匹配分析流程、输入与参数，也支持已有明确方法的请求。"
            },
            {
                "name": "nfcore-datasync",
                "desc": "当科研数据需要在存储位置间复制、同步或整理，且能核对源文件与目标位置时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/datasync。"
            },
            {
                "name": "nfcore-demo",
                "desc": "当需要用小型公开示例认识分析步骤或检查科研计算环境时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/demo。"
            },
            {
                "name": "nfcore-provenancereport",
                "desc": "当已有分析结果但不清楚用了哪些输入、软件版本和参数，需要核查可复现性时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/provenancereport。"
            },
            {
                "name": "nfcore-references",
                "desc": "当分析已经需要特定物种的参考基因组、注释或索引，但交付包没有兼容资源时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/references。"
            },
            {
                "name": "nfcore-seqsubmit",
                "desc": "当研究数据需要整理成公开测序数据库的提交材料时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/seqsubmit。"
            },
            {
                "name": "standardization",
                "desc": "Mandatory entry-point router for standardized browser-based research workflows. Use when the user asks for bro…"
            }
        ],
        "database-api-access": [
            {
                "name": "api-external-integration",
                "desc": "当用户需要把科研数据库、实验平台或院内系统通过 API 连接起来，设计认证、分页、限流、重试和数据映射时使用。"
            },
            {
                "name": "bioservices",
                "desc": "Unified Python access to 40+ bioinformatics web services; use when you need to query multiple databases (e.g.…"
            },
            {
                "name": "gget",
                "desc": "Unified CLI/Python interface for querying genomic, proteomic, structure, and expression data across 20+ bioinf…"
            },
            {
                "name": "mcp-tool-operations",
                "desc": "当用户需要发现本插件已配置的 MCP 工具、选择合适工具或排查连接与调用错误时使用。"
            },
            {
                "name": "nfcore-fetchngs",
                "desc": "当只有公共数据库编号或论文中的数据编号，需要取得测序文件与样本信息时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/fetchngs。"
            },
            {
                "name": "scientific-database-access",
                "desc": "当用户需要查询基因、变异、表达、药物、通路、结构或临床研究数据库并解释结果时使用。"
            },
            {
                "name": "metabolomics-database-search",
                "desc": "当用户需要在 HMDB、MetaboLights、Metabolomics Workbench、GNPS 等资源中查找代谢物、参考谱图或可复用研究，并核对版本与许可时使用。"
            },
            {
                "name": "microbiome-data-retrieval",
                "desc": "用于检索公开微生物组研究、样本、原始测序、组装和分析结果；当用户需要复用公共数据或建立外部验证队列时使用。"
            },
            {
                "name": "proteomics-data-retrieval",
                "desc": "当用户需要在 PRIDE/ProteomeXchange 中定位适合复用的蛋白质组项目，并核实样本、原始文件、许可和再分析可行性时使用。"
            },
            {
                "name": "single-cell-data-retrieval",
                "desc": "当用户需要在 CELLxGENE 等公共图谱中查找符合组织、疾病、细胞类型和供体条件的数据，并判断其能否用于再分析或参考映射时使用。"
            },
            {
                "name": "cellxgene-census",
                "desc": "Query the CZ CELLxGENE Census programmatically for versioned public single-cell and spatial transcriptomics da…"
            }
        ],
        "visualization-figures": [
            {
                "name": "genome-browser-track-creation",
                "desc": "当用户需要把比对、变异、覆盖、注释或调控信号制作成可在 IGV/UCSC 等浏览器查看的轨道时使用。"
            },
            {
                "name": "biological-network-visualization",
                "desc": "用于把PPI、调控、代谢或多组学网络整理为可读的Cytoscape或图形结果；当网络需要布局、注释和发布级展示时使用。"
            },
            {
                "name": "drawio",
                "desc": "Generate draw.io diagrams as .drawio files and export to PNG/SVG/PDF with embedded XML"
            },
            {
                "name": "excalidraw-diagram-generator",
                "desc": "Generate Excalidraw diagrams from natural language descriptions. Use when asked to \"create a diagram\", \"make a…"
            },
            {
                "name": "image-painter",
                "desc": "当需要通过 SpeedAI 图像接口生成位图或参考现有图片修改位图时使用，包括照片、插画、产品图、网站图、游戏素材、PPT 图、论文图、流程图和信息图。不承诺像素级精确编辑；不要用于 SVG/HTML/CSS/canva…"
            },
            {
                "name": "matplotlib",
                "desc": "Low-level plotting library for full customization. Use when you need fine-grained control over every plot elem…"
            },
            {
                "name": "morning",
                "desc": "将用户的晨间简报渲染为有样式的 HTML 产物，或将其设置为工作日循环任务。仅当用户明确要求运行、查看或设置晨间简报，或明确调用 /morning 时使用；仅询问当天安排、日程或日历并不构成晨间简报请求，应直接回答。"
            },
            {
                "name": "scientific-visualization",
                "desc": "Meta-skill for publication-ready figures. Use when creating journal submission figures requiring multi-panel l…"
            },
            {
                "name": "scientific-visualization-reporting",
                "desc": "当用户已有科研数据、分析结果或图件，需要把结果画清楚、制作文章图或报告，或遇到表达不清、图表与文字矛盾、标签/颜色/单位混乱、导出不完整时使用；分析完成后的图件交付也适用。先识别研究问题、数据状态与实际出图路径，不要求用…"
            },
            {
                "name": "protein-structure-visualization",
                "desc": "用于制作蛋白结构、复合物、口袋、突变位点和轨迹的可解释图像或会话；当用户需要PyMOL/ChimeraX展示时使用。"
            }
        ],
        "research-design-hypothesis": [
            {
                "name": "nfcore-readsimulator",
                "desc": "当需要为测序方法评估构建带真值的模拟数据时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/readsimulator。"
            },
            {
                "name": "clinical-trial-workflows",
                "desc": "当用户需要检索相关临床试验、评估可行性或起草研究方案框架时使用。"
            },
            {
                "name": "conventional-oncology-hub-gene-research-planner",
                "desc": "Generates complete conventional oncology bulk-transcriptome biomarker and hub-gene research designs from a use…"
            },
            {
                "name": "experiment-protocol-design",
                "desc": "当用户只给疾病、基因或“想做课题、写论文、毕业、不知道从哪开始”等研究目标，或需要设计对照、重复、样本量与验证实验时使用；先识别问题与已有资源，再按数据引导到合适分析，不要求用户认识方法或 Skill。"
            },
            {
                "name": "hypothesis-generation",
                "desc": "Structured hypothesis formulation from observations. Use when you have experimental observations or data and n…"
            },
            {
                "name": "indication-dossier",
                "desc": "生成治疗适应症档案，覆盖患者人群、流行病学、疾病生物学、标准治疗、监管先例和里程碑式临床试验。"
            },
            {
                "name": "public-omics-study-design-report",
                "desc": "当用户只知道疾病或基因，希望用公共数据做课题、发文章、毕业、找数据或不知道下一步，或需要选择多组数据、设计发现与验证路线、解释已有结果和撰写可追溯报告时使用；自主识别数据角色和所需专业分析，不要求用户知道数据库、算法或…"
            },
            {
                "name": "qtl-colocalization-study-planner",
                "desc": "Designs QTL colocalization studies that connect eQTL, pQTL, sQTL, or related molecular QTL signals with GWAS l…"
            },
            {
                "name": "scientific-problem-hypothesis",
                "desc": "当用户需要把宽泛研究兴趣收束成可检验、可证伪且有现实价值的科研问题与假设时使用。"
            },
            {
                "name": "multi-omics-integration-design",
                "desc": "用于根据科研问题、样本配对情况和终点选择多组学整合策略；当用户尚未确定早期、潜变量、网络或决策级融合方法时使用。"
            }
        ]
    };
    const PREVIEW = 4;

    const tint = (color, alpha) => {
      const hex = color.replace('#', '');
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    };

    const S = {
      wrap: { display: 'flex', flexDirection: 'column', gap: '26px', padding: '6px 2px 10px' },
      intro: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        flexWrap: 'wrap',
        padding: '12px 14px',
        borderRadius: '10px',
        background: 'var(--dsh-surface-subtle, rgba(128,128,128,0.06))',
      },
      introText: { fontSize: '12.5px', lineHeight: 1.6, opacity: 0.72, margin: 0 },
      group: { display: 'flex', flexDirection: 'column', gap: '12px' },
      groupHead: { display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' },
      groupTitle: { fontSize: '15px', fontWeight: 700, margin: 0, letterSpacing: '0.01em' },
      groupMeta: { fontSize: '12px', opacity: 0.55, margin: 0 },
      groupActions: { marginLeft: 'auto', display: 'flex', gap: '6px' },
      card: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: '10px' },
      item: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: '12px',
        padding: '13px 14px',
        border: '1px solid var(--dsh-border, rgba(128,128,128,0.16))',
        borderRadius: '12px',
        background: 'var(--dsh-surface, transparent)',
        transition: 'background 120ms ease, border-color 120ms ease',
      },
      itemOff: { opacity: 0.5 },
      itemOpen: { gridColumn: '1 / -1', flexDirection: 'column', alignItems: 'stretch', gap: '12px' },
      icon: {
        width: '36px',
        height: '36px',
        borderRadius: '10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '17px',
        flexShrink: 0,
      },
      body: { flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' },
      titleRow: { display: 'flex', alignItems: 'center', gap: '7px', flexWrap: 'wrap' },
      title: { fontSize: '13.5px', fontWeight: 600, lineHeight: 1.3 },
      chip: {
        fontSize: '10.5px',
        padding: '1px 6px',
        borderRadius: '5px',
        background: 'var(--dsh-surface-subtle, rgba(128,128,128,0.12))',
        opacity: 0.75,
        whiteSpace: 'nowrap',
      },
      chipOn: { fontSize: '10.5px', padding: '1px 6px', borderRadius: '5px', color: '#0f8a63', background: 'rgba(16,185,129,0.13)', whiteSpace: 'nowrap' },
      desc: {
        fontSize: '12px',
        lineHeight: 1.55,
        opacity: 0.6,
        margin: 0,
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
      },
      right: { display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 },
      switch: (on, color) => ({
        width: '34px',
        height: '20px',
        borderRadius: '999px',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        position: 'relative',
        background: on ? color : 'rgba(128,128,128,0.28)',
        transition: 'background 140ms ease',
      }),
      knob: (on) => ({
        position: 'absolute',
        top: '2px',
        left: on ? '16px' : '2px',
        width: '16px',
        height: '16px',
        borderRadius: '999px',
        background: '#fff',
        boxShadow: '0 1px 2px rgba(0,0,0,0.22)',
        transition: 'left 140ms ease',
      }),
      moreBtn: {
        fontSize: '11px',
        padding: '2px 7px',
        borderRadius: '6px',
        border: '1px solid var(--dsh-border, rgba(128,128,128,0.3))',
        background: 'transparent',
        color: 'inherit',
        cursor: 'pointer',
        opacity: 0.8,
        whiteSpace: 'nowrap',
      },
      btn: {
        fontSize: '12px',
        padding: '4px 11px',
        borderRadius: '7px',
        border: '1px solid var(--dsh-border, rgba(128,128,128,0.3))',
        background: 'transparent',
        color: 'inherit',
        cursor: 'pointer',
      },
      moreRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', paddingTop: '2px' },
      moreText: { fontSize: '12px', opacity: 0.5, margin: 0 },
      skillList: {
        margin: 0,
        padding: '10px 0 0',
        listStyle: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: '7px',
        borderTop: '1px dashed var(--dsh-border, rgba(128,128,128,0.2))',
      },
      skillItem: { fontSize: '12px', lineHeight: 1.5, display: 'flex', gap: '10px', alignItems: 'baseline' },
      skillName: {
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: '11px',
        opacity: 0.92,
        whiteSpace: 'nowrap',
        minWidth: '168px',
        flexShrink: 0,
      },
      skillDesc: { flex: 1, opacity: 0.66 },
      divider: { height: 1, background: 'var(--dsh-border, rgba(128,128,128,0.14))', margin: 0 },
      hint: { fontSize: '12px', opacity: 0.7, margin: 0 },
      err: { fontSize: '12px', color: '#d9534f', margin: 0, whiteSpace: 'pre-wrap' },
    };

    function unwrap(response, what) {
      if (response && typeof response === 'object' && typeof response.ok === 'boolean') {
        if (response.ok) return { value: response.value };
        const msg = response.error && response.error.message ? response.error.message : '调用失败';
        return { error: `${what}失败：${msg}` };
      }
      if (Array.isArray(response)) return { value: response };
      const keys = response && typeof response === 'object' ? Object.keys(response).join(',') : String(response);
      return { error: `${what}返回了非预期形状（keys: ${keys}）` };
    }

    function pickRow(rows) {
      if (!Array.isArray(rows)) return undefined;
      return rows.find((d) => d && typeof d.ns === 'string' && d.ns.includes(NS_MATCH));
    }

    /** 把 value 的键按 GROUPS 分组（纯函数）。 */
    function buildGroups(value) {
      const v = value && typeof value === 'object' ? value : {};
      const byId = new Map();
      for (const id of Object.keys(v)) {
        const meta = LABELS[id] ?? {};
        byId.set(id, { id, label: meta.label ?? id, desc: meta.desc ?? '', count: meta.count, on: v[id] !== false });
      }
      const groups = [];
      const used = new Set();
      for (const g of GROUPS) {
        const items = g.cats.map((id) => byId.get(id)).filter(Boolean);
        if (items.length === 0) continue;
        items.forEach((i) => used.add(i.id));
        groups.push({
          id: g.id,
          label: g.label,
          emoji: g.emoji,
          color: g.color,
          items,
          cats: items.length,
          skills: items.reduce((a, i) => a + (i.count || 0), 0),
        });
      }
      const rest = [...byId.values()].filter((i) => !used.has(i.id));
      if (rest.length > 0) {
        groups.push({
          id: 'other',
          label: '其他',
          emoji: '📦',
          color: '#64748b',
          items: rest,
          cats: rest.length,
          skills: rest.reduce((a, i) => a + (i.count || 0), 0),
        });
      }
      return groups;
    }

    function Section() {
      const [state, setState] = React.useState({ phase: 'loading' });
      const [expanded, setExpanded] = React.useState({});
      const [detail, setDetail] = React.useState({});

      const load = React.useCallback(async () => {
        let raw;
        try {
          raw = await remote().describe();
        } catch (e) {
          setState({ phase: 'error', message: e && e.message ? e.message : String(e) });
          return;
        }
        const un = unwrap(raw, '读取设置');
        if (un.error) {
          setState({ phase: 'error', message: un.error });
          return;
        }
        const view = un.value;
        const rows = Array.isArray(view) ? view : view && Array.isArray(view.namespaces) ? view.namespaces : [];
        if (rows.length === 0) {
          const shape = view && typeof view === 'object' ? Object.keys(view).join(',') : String(view);
          setState({ phase: 'empty', message: `没有读到任何命名空间（返回形状的 keys: ${shape}）。` });
          return;
        }
        const me = pickRow(rows);
        if (!me) {
          const sample = rows.slice(0, 8).map((d) => d.ns).join(' / ');
          setState({ phase: 'empty', message: `共读到 ${rows.length} 个命名空间，未匹配到 ${NS_MATCH}。前几个：${sample}` });
          return;
        }
        const groups = buildGroups(me.value);
        if (groups.length === 0) {
          setState({ phase: 'empty', message: `已匹配到 ${me.ns}，但它的 value 里没有任何开关字段。` });
          return;
        }
        setState({ phase: 'ready', groups, ns: me.ns, revision: me.revision });
      }, []);

      React.useEffect(() => {
        load().catch((e) => setState({ phase: 'error', message: String(e && e.message ? e.message : e) }));
      }, [load]);

      const apply = async (ops) => {
        const un = unwrap(await remote().mutate(state.ns, ops, state.revision), '保存开关');
        if (un.error) setState((s) => ({ ...s, message: un.error }));
        await load();
      };

      const toggle = async (id, next) => {
        setState((s) => ({
          ...s,
          groups: s.groups.map((g) => ({ ...g, items: g.items.map((it) => (it.id === id ? { ...it, on: next } : it)) })),
        }));
        try {
          await apply([{ op: 'set', path: [id], value: next }]);
        } catch (e) {
          setState((s) => ({ ...s, message: String(e && e.message ? e.message : e) }));
        }
      };

      const setGroup = async (group, next) => {
        try {
          await apply(group.items.map((it) => ({ op: 'set', path: [it.id], value: next })));
        } catch (e) {
          setState((s) => ({ ...s, message: String(e && e.message ? e.message : e) }));
        }
      };

      const setAll = async (next) => {
        const ops = (state.groups || []).flatMap((g) => g.items.map((it) => ({ op: 'set', path: [it.id], value: next })));
        try {
          await apply(ops);
        } catch (e) {
          setState((s) => ({ ...s, message: String(e && e.message ? e.message : e) }));
        }
      };

      if (state.phase === 'loading') return h('p', { style: S.hint }, '正在读取技能开关…');
      if (state.phase === 'error') return h('p', { style: S.err }, `读取失败：${state.message}`);
      if (state.phase === 'empty') return h('p', { style: S.hint }, state.message ?? '没有找到本插件的配置行。');

      const groups = state.groups ?? [];
      const all = groups.flatMap((g) => g.items);
      const onCount = all.filter((i) => i.on).length;
      const totalSkills = groups.reduce((a, g) => a + g.skills, 0);

      const renderItem = (g, it) => {
        const isOpen = detail[it.id] === true;
        const skills = SKILLS[it.id] ?? [];
        return h(
          'div',
          {
            key: it.id,
            style: {
              ...S.item,
              ...(it.on ? {} : S.itemOff),
              ...(isOpen ? S.itemOpen : {}),
            },
          },
          h(
            'div',
            { style: { display: 'flex', alignItems: 'flex-start', gap: '12px', width: '100%' } },
            h('div', { style: { ...S.icon, background: tint(g.color, 0.14) } }, g.emoji),
            h(
              'div',
              { style: S.body },
              h(
                'div',
                { style: S.titleRow },
                h('span', { style: S.title }, it.label),
                it.count ? h('span', { style: S.chip }, `${it.count} 个技能`) : null,
                it.on ? h('span', { style: S.chipOn }, '已启用') : null,
              ),
              it.desc ? h('p', { style: S.desc, title: it.desc }, it.desc) : null,
            ),
            h(
              'div',
              { style: S.right },
              skills.length > 0
                ? h(
                    'button',
                    {
                      type: 'button',
                      style: S.moreBtn,
                      title: `${it.label} 下的 ${skills.length} 个技能`,
                      onClick: () => setDetail((d) => ({ ...d, [it.id]: !isOpen })),
                    },
                    isOpen ? '收起' : '详情',
                  )
                : null,
              h(
                'button',
                {
                  type: 'button',
                  role: 'switch',
                  'aria-checked': it.on,
                  'aria-label': `${it.label} 开关`,
                  style: S.switch(it.on, g.color),
                  onClick: () => toggle(it.id, !it.on),
                },
                h('span', { style: S.knob(it.on) }),
              ),
            ),
          ),
          isOpen
            ? h(
                'ul',
                { style: S.skillList },
                ...skills.map((s) =>
                  h(
                    'li',
                    { key: s.name, style: S.skillItem },
                    h('code', { style: S.skillName }, s.name),
                    h('span', { style: S.skillDesc }, s.desc),
                  ),
                ),
              )
            : null,
        );
      };

      return h(
        'div',
        { style: S.wrap },
        h(
          'div',
          { style: S.intro },
          h(
            'p',
            { style: S.introText },
            `${groups.length} 个大组 · ${all.length} 个功能分类 · ${totalSkills} 个技能，当前启用 ${onCount} 类。` +
              '关闭的分类不会进入新会话的技能目录，已开启的会话不受影响。',
          ),
          h(
            'div',
            { style: { display: 'flex', gap: '6px' } },
            h('button', { type: 'button', style: S.btn, onClick: () => setAll(true) }, '全部开启'),
            h('button', { type: 'button', style: S.btn, onClick: () => setAll(false) }, '全部关闭'),
          ),
        ),
        state.message ? h('p', { style: S.err }, state.message) : null,
        ...groups.flatMap((g, gi) => {
          const open = expanded[g.id] === true;
          const shown = open ? g.items : g.items.slice(0, PREVIEW);
          const hidden = g.items.length - shown.length;
          const onInGroup = g.items.filter((i) => i.on).length;
          const parts = [
            h(
              'div',
              { key: `h-${g.id}`, style: S.groupHead },
              h('div', { style: { ...S.icon, background: tint(g.color, 0.14), fontSize: '18px' } }, g.emoji),
              h(
                'div',
                null,
                h('h3', { style: S.groupTitle }, g.label),
                h('p', { style: S.groupMeta }, `${g.cats} 个分类 · ${g.skills} 个技能 · 已启用 ${onInGroup}`),
              ),
              h(
                'div',
                { style: S.groupActions },
                h('button', { type: 'button', style: S.moreBtn, onClick: () => setGroup(g, true) }, '全开'),
                h('button', { type: 'button', style: S.moreBtn, onClick: () => setGroup(g, false) }, '全关'),
              ),
            ),
            h('div', { key: `c-${g.id}`, style: S.card }, ...shown.map((it) => renderItem(g, it))),
          ];
          if (hidden > 0 || g.items.length > PREVIEW) {
            parts.push(
              h(
                'div',
                { key: `m-${g.id}`, style: S.moreRow },
                h('p', { style: S.moreText }, hidden > 0 ? `还有 ${hidden} 个分类` : `已列出全部 ${g.items.length} 个分类`),
                h(
                  'button',
                  {
                    type: 'button',
                    style: S.moreBtn,
                    onClick: () => setExpanded((e) => ({ ...e, [g.id]: !open })),
                  },
                  hidden > 0 ? '列举剩余全部' : '收起',
                ),
              ),
            );
          }
          const nodes = [h('div', { key: `g-${g.id}`, style: S.group }, ...parts)];
          if (gi < groups.length - 1) nodes.push(h('div', { key: `d-${g.id}`, style: S.divider }));
          return nodes;
        }),
      );
    }

    let ctxRef;
    const remote = () => ctxRef.remote.settings;

    return {
      inject: ['slots', 'locale', 'remote', 'remote.settings'],
      apply(ctx) {
        ctxRef = ctx;
        ctx.slots.inject('settings.section', () =>
          ctx.slots.register(
            { name: 'settings.section', id: 'biomedical-skills', order: 60, label: '生物医学技能' },
            Section,
          ),
        );
      },
    };
  },
});
