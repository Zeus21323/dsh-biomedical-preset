---
name: long-read-alignment
description: 当用户需要把 Nanopore 或 PacBio 长读长比对到参考基因组并支持变异、异构体或甲基化分析时使用。
---

# 长读长序列比对

确认平台、数据是 DNA 还是 RNA、是否 HiFi，以及下游需要保留哪些标签。参考构建和 alt/decoy 选择需与后续调用器一致。

minimap2 使用与数据匹配的 preset：ONT、HiFi 和剪接 RNA 的设置不同。保留 supplementary alignment 供结构变异分析；RNA 比对保留剪接方向和 junction 信息；修饰分析不能丢失相关 BAM 标签。

检查 primary/supplementary 比例、覆盖、错配与 Indel、超长嵌合读段、同源区域和参考错配。排序索引后抽查复杂位点。

交付 BAM、索引、比对参数和平台分层指标。为追求“唯一比对”而删除补充比对会破坏结构变异证据。
