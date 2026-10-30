---
name: 05-single-cell-virtual-cell-b01-t02
description: "当用户需要把 scATAC-seq FASTQ 或 fragments 转成经过条形码、片段质量和可及性检查的 tile/peak 矩阵时使用。"
---

# scATAC-seq预处理

## 输入核对

需要 FASTQ 或 fragments、条形码白名单、参考基因组、TSS 与 blacklist 版本、样本和批次。确认坐标体系、染色体命名和 fragments 是否已去重复。

## 处理流程

1. 从 FASTQ 开始时检查比对、有效条形码、唯一片段和 PCR 重复；已有 fragments 时验证排序和索引。
2. 按样本计算片段数、TSS enrichment、FRiP、blacklist ratio 和核小体周期性，阈值依据各样本分布制定。
3. 检测双细胞；高片段数或混合谱系 marker 不能仅凭一个指标判断。
4. 先用 tile 矩阵建立初步细胞群，再按样本或主要谱系做伪 bulk peak calling，合并为共识峰。
5. 重新生成 peak 矩阵并保留 fragments、tile 和 peak 三个层级的对应关系。

## 质控重点

检查低复杂度细胞、TSS 与 FRiP 冲突、blacklist 富集、样本阈值差异和批次驱动的峰。共识峰若只由单一样本贡献要标记。

## 交付

交付保留细胞、每细胞 QC、fragments 索引、tile/peak 矩阵、共识峰和参数；可及性峰不能直接称为转录因子结合位点。
