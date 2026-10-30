---
name: bioinformatics-format-conversion-integrity
description: 当用户需要在 FASTA、FASTQ、SAM、BAM、CRAM、BIOM、TSV 或常见丰度表布局之间转换，并核对转换前后记录、配对关系和校验值时使用；分子结构格式转换不使用本 Skill。
---

# 生物信息文件格式转换与完整性校验

## 转换前

识别真实文件格式、压缩方式、序列布局、参考基因组、表格方向和目标工具要求。扩展名只能作为线索；BAM/CRAM、BIOM HDF5 和压缩文件应使用能够读取其内容的工具确认。默认创建新文件，不覆盖输入。

## 路线

- FASTQ 转 FASTA 会丢失质量值；FASTA 不能无损恢复原始 FASTQ，除非用户明确接受人工质量值，否则拒绝逆向伪造。
- SAM/BAM/CRAM 使用 samtools；CRAM 转换必须记录参考 FASTA 及其校验值。
- BAM 转成双端 FASTQ 前按 read name 整理，并单独处理未配对、secondary 和 supplementary reads。
- BIOM 与 TSV/JSON 使用 biom-format，记录 table type 和 taxonomy/metadata 是否保留。
- 丰度宽表与长表转换必须指定特征 ID、样本 ID 和数值列，拒绝猜测含义不清的第一列。

可运行 `scripts/convert_bioformats.py` 执行受支持的确定性转换。脚本在输出旁生成 `.conversion.json`，记录命令、输入输出 SHA-256、文件大小和工具版本。

## 完整性检查

检查输入输出记录数、序列 ID 集合、双端 read 名称、alignment header、BIOM shape 和丰度表行列数量。格式转换允许的预期损失必须提前说明；发现非预期记录丢失、重复 ID 或工具失败时停止，不交付不完整结果。

## 输出

交付转换后的新文件及转换记录。运行路径由用户指定，不在 Skill 目录中保存数据、日志或生成结果。
