---
name: 01-genome-alignment
description: 当用户需要把短读长或常规 DNA 测序读段比对到参考基因组并得到可追溯比对文件时使用。
---

# 测序读段比对

参考 FASTA、索引、decoy/alt contig 和 contig 命名必须固定。每个 lane 设置正确的 sample、library、platform 和 read group。

常规短读长 DNA 可选 BWA-MEM2；需要非常短的局部读段或特定实验时再考虑 Bowtie2 等。比对后坐标排序并建立索引，重复先标记，不默认删除。

检查总读段、mapped/primary/secondary/supplementary、唯一比对、插入片段、重复和各染色体覆盖。异常高的 chrM、未定位 contig 或补充比对应结合文库解释。

交付 BAM/CRAM、索引、参考资源、比对命令和指标。不能混合不同参考构建产生的文件，也不能在 header 中让多个样本共享一个错误 sample ID。
