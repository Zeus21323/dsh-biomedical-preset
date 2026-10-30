---
name: 01-genome-long-read-sequencing
description: 当用户需要评估 Nanopore 或 PacBio 长读长的长度、质量、产量、污染和平台特征时使用。
---

# 长读长测序质控

输入可以是原始信号、basecalled FASTQ 或 BAM；报告要说明处于哪一阶段。确认平台、chemistry、run/flow cell 和预期基因组大小。

至少查看总碱基、读段数、长度 N50/N90、质量分布、按时间/通道的产量和预计覆盖。ONT 关注孔道衰减、短碎片峰和条码串扰；HiFi 关注 CCS passes、读长与准确度。

分类或比对少量读段评估污染和样本身份。只报 N50 会掩盖低质量长读、整体产量不足或后半程运行崩溃。

输出逐 run/样本质控、是否需要过滤/补测、可支持的组装或变异任务，以及任何 basecalling 模型差异。
