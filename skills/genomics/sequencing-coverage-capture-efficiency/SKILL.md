---
name: sequencing-coverage-capture-efficiency
description: 当用户需要评估 WGS、WES 或面板测序的覆盖深度、均一性、可调用区域和捕获效率时使用。
---

# 测序覆盖度与捕获效率评估

确认 BAM/CRAM 的参考、目标 BED、是否计入重复/低质量读段，以及 10×、20×、30× 等阈值的业务含义。

WGS 报告全基因组或高可信区域的深度分布与均一性；WES/面板同时报告 on-target、近靶、离靶、fold-80、目标碱基阈值覆盖和每个关键区域的最低覆盖。平均深度不能说明是否存在大片盲区。

用 mosdepth、samtools depth 或 Picard 时固定 mapQ、baseQ 和重叠读段处理。检查 BED 是否排序、合并、与参考 contig 匹配，并随机核对若干低覆盖区域。

交付逐样本汇总、逐区域/碱基结果、低覆盖 BED、计算口径及补测或正交检测建议。
