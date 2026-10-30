---
name: nfcore-scrnaseq
description: "当建库或交付证据表明是单细胞 RNA 原始读段，需要生成细胞表达矩阵时使用。根据文件、实验背景与研究问题判断适配性，选择方法及参数并解释限制；无需用户知道 nf-core/scrnaseq。"
---

# 条形码单细胞RNA测序预处理（nf-core/scrnaseq）

## 识别数据与研究目标

明确 FASTQ、建库协议、barcode/UMI 长度与白名单、参考及预期细胞数；已有矩阵应转入适用的下游分析。

## 方法选择

按本版本支持的 SimpleAF、STARsolo、kallisto/BUStools 或 Cell Ranger 路线准备输入，核对协议支持与商业软件许可。

先核对 [版本约定](references/流程约定.json)。

| 核对项 | 固定范围 |
|---|---|
| 上游版本 | `4.2.0`；`3fc17b4f971a89e47c88337de71d0e777ffad8cc` |
| 上游维护 | 未归档；使用这里固定的源码，不自动跟随新版本 |
| 本地运行 | 未进行真实分析运行；不能据本 Skill 文件声称实跑通过 |
| 引擎声明 | `!>=25.10.4`；还需核验 Java、容器和 profile |

## 根据数据确定参数

由试剂版本与 read structure 确定 barcode、UMI 和白名单，预期细胞数结合上样记录及 barcode rank 评估；这些信息不明时先查报告，不能仅凭 R1/R2 文件名猜测 10x 化学版本。

| 决策与配置 | 处理要求 |
|---|---|
| 事实与缺口 | 先读现有文件和报告；不能据文件名猜实验类型、参考或样本关系；只补问无法核实且会改变分析的背景 |
| 参数来源 | 区分协议必需设置、数据估计、方法默认和研究选择；说明实际取值及理由，不要求用户填写专业参数 |
| 可执行配置 | 仅把已支持的选择映射为当前版本的原生字段；不支持的步骤另行交接，不虚构开关 |
| 阈值复核 | 默认值先评估适用性；依据质控、对照及敏感性检查调整，不能按显著结果数量调参 |

| 资料 | 使用时机 |
|---|---|
| [参数模式.json](references/参数模式.json) | 编写 params.json 时核对字段、类型、枚举及条件约束 |
| [输入模式-1.json](references/输入模式-1.json) | 准备 cellranger_multi_barcodes 对应的样本表或输入文件时读取 |
| [输入模式-2.json](references/输入模式-2.json) | 准备 input 对应的样本表或输入文件时读取 |

仅在已授权且配置齐备时运行。

```bash
nextflow run nf-core/scrnaseq -r 3fc17b4f971a89e47c88337de71d0e777ffad8cc -params-file params.json
```

模式文件的许可见 [LICENSE](LICENSE)。

## 质控与解释

检查 barcode 匹配、UMI、基因检出、空液滴和样本产量；不同方法的 cell calling 结果不能仅凭细胞数比较优劣。

交付实际计数对象、细胞判定和 QC，注明 raw/filtered 语义；聚类、整合或统计只在实际流程包含时报告。
