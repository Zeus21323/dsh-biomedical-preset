---
name: focal-amplification-ecdna-analysis
description: 用于从肿瘤WGS识别焦点扩增并用AmpliconArchitect/AmpliconClassifier区分ecDNA、BFB、HSR和线性扩增；当高拷贝致癌基因需要结构解析时使用。
---
# 焦点扩增与 ecDNA 分析

1. 确认输入是足够覆盖的肿瘤WGS BAM、参考基因组一致，并具备可靠的拷贝数与纯度结果；面板或WES通常不足以重建扩增子。
2. 从经过审核的高拷贝、局灶性CNV中生成种子，排除臂级增益和无正常对照造成的噪声种子。
3. 用AmpliconSuite重建断点图，再由AmpliconClassifier区分ecDNA、BFB、HSR和线性结构；优先运行 `scripts/run_ampliconsuite.sh --dry-run ...` 复核命令，执行前核对当前版本参数。
4. ecDNA结论同时要求闭合循环图、平衡流和分类证据；检查覆盖、分裂读段、重复区域与亚克隆比例。
5. 输出种子、断点图、循环、分类、致癌基因和不确定性；高风险结果建议FISH、长读长、光学图谱或单细胞CNV验证。

高幅度扩增本身不是ecDNA证据；短读长复杂扩增子的结构通常只是候选解。

维护脚本时运行 `scripts/test_run_ampliconsuite.sh`；脚本拒绝写入已有内容的输出目录。
