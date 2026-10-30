---
name: genome-browser-track-creation
description: 当用户需要把比对、变异、覆盖、注释或调控信号制作成可在 IGV/UCSC 等浏览器查看的轨道时使用。
---

# 基因组浏览器与轨道制作

所有轨道必须使用同一参考构建和 contig 命名。先确认输入是 BAM/CRAM、VCF、BED/GFF、bedGraph 还是连续信号，再选择浏览器支持的排序、压缩和索引格式。

BAM/CRAM 与 VCF 保留索引；连续信号转 bigWig 前处理未排序、重叠区间和染色体长度；注释转 bigBed 时明确 BED 坐标为 0 基半开。样本名、条件、单位和归一化方式写入轨道标签或说明。

抽查已知阳性、阴性和染色体端点，排除 0/1 基偏移、chr 前缀、错误缩放和参考错配。交付轨道文件、索引或 hub/session、颜色/单位说明及用于验收的位点。
