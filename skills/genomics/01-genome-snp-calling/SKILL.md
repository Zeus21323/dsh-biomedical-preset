---
name: 01-genome-snp-calling
description: 当用户需要从生殖系 DNA 的分析就绪 BAM/CRAM 检测 SNV 和短 Indel，并进行单样本或队列联合分型时使用。
---

# 胚系小变异检测

输入必须是与参考一致、样本身份已核对的分析就绪 BAM/CRAM。确认样本倍性、目标区域和单样本还是队列任务。

可使用 GATK HaplotypeCaller、DeepVariant 或 bcftools。队列优先生成每样本 gVCF 后联合分型；不能把不同参考或调用配置的 gVCF 无说明混合。性染色体、线粒体和非二倍体物种另设倍性。

检查位点与基因型质量、深度、等位平衡、链/位置偏倚、Ti/Tv、杂合度及家系孟德尔错误。过滤保留标签，关键 Indel 回看局部比对。

输出规范化 VCF/gVCF、调用与过滤参数、样本和位点 QC、可调用区域。研究结果不自动构成致病性解释。
