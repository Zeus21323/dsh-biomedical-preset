# QIIME 2工件与参数

## 输入

- 双端 FASTQ manifest 使用绝对文件路径，但不得把个人电脑路径写入 Skill 源码。
- manifest 的样本 ID 必须与 metadata 一致。
- 16S 分类器必须与扩增区域和参考版本匹配；ITS 使用适合真菌的参考和处理策略。
- 先用 `qiime demux summarize` 查看质量，再决定 trim 与 truncation。

## DADA2 参数判断

- `trim-left` 用于移除引物或固定低质量头部，不能与上游引物去除重复执行。
- `trunc-len` 应保留足够的双端重叠，且不能只追求保留更多低质量碱基。
- 报告输入、过滤、去噪、合并和去嵌合体各步读段数。
- 双端无法可靠合并时，应重新评估截断、扩增区和是否使用单端流程。

## 关键工件

- `demux.qza`：导入的样本序列；
- `table.qza`：ASV 特征表；
- `representative-sequences.qza`：代表序列；
- `denoising-stats.qza`：去噪统计；
- `taxonomy.qza`：分类结果。

QIIME 2 官方流程概览：<https://docs.qiime2.org/2024.10/tutorials/overview/>
