---
name: 01-genome-bam
description: 当用户需要查看、转换、排序、索引、合并、切片或验证 SAM、BAM、CRAM 文件时使用。
---

# SAM、BAM与CRAM文件处理

先查看 header、排序标记、read group、参考序列和样本名，再决定操作。CRAM 解码和重编码必须使用与文件一致的参考 FASTA。

## 常见操作边界

- 转换格式不应改变比对记录含义；转换前后对账总记录和 mapped/unmapped 数。
- 坐标索引要求坐标排序；按 read name 排序的文件不能直接建立常规区域索引。
- 合并 lane 前统一样本和 read group，合并不同样本时不能抹掉身份。
- 区域提取需说明坐标体系并保留 header。
- 标记重复与删除重复是不同动作，未确认用途时优先保留标记。

使用 samtools quickcheck 或更完整验证检查 EOF、header、排序和索引。交付处理后的文件、索引、采用的参考、操作说明及前后记录对账。
