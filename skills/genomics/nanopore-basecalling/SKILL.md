---
name: nanopore-basecalling
description: 当用户需要把 Nanopore POD5/FAST5 转为碱基序列，并选择模型、条码拆分和修饰检测设置时使用。
---

# Nanopore碱基识别

必须知道 flow cell、测序 kit、chemistry、原始格式和 Dorado 版本；模型与 chemistry 不匹配时不要继续。

## 模型取舍

- fast：快速查看产量或排查运行，不适合作为高精度最终结果。
- hac：速度和准确度折中。
- sup：计算开销大，适合变异、组装等对准确度敏感的任务。
- 修饰碱基：使用与基础模型配套的 modified-base 模型，并保留相应 BAM 标签。

先在一小批 POD5 上验证模型、设备和输出，再做全量 basecalling。条码拆分使用实际 kit，统计未分类比例和跨条码污染；不要用文件名替代条码判定。

交付 FASTQ 或保留 move/修饰信息的 BAM，同时报告模型文件、版本、总碱基、读段数、Q 分布、N50、未分类条码和失败文件。
