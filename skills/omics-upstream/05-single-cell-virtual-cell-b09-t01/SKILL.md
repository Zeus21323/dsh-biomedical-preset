---
name: 05-single-cell-virtual-cell-b09-t01
description: "当用户需要分析 CRISPR Perturb-seq、CRISPRi/a 数据，将 guide 可靠分配到细胞并估计扰动的平均效应和状态依赖效应时使用。"
---

# Perturb-seq扰动分析

## 实验信息决定模型

取得表达矩阵、guide 计数、文库和靶标、MOI、非靶与阳性对照、批次、供体、时间和筛选条件。先确认是低 MOI 单 guide 设计还是允许组合扰动。

## 从 guide 到效应

1. 按样本估计 guide 背景并完成 guide assignment，区分无 guide、单 guide 和多 guide 细胞。
2. 联合细胞质量、guide 捕获和靶基因 knockdown/activation 判断有效扰动，不能仅凭一条 guide 计数。
3. 在非靶对照定义的背景下估计表达效应；多供体设计用供体或实验重复建模。
4. 比较同一靶基因不同 guide 的方向和幅度，分离 guide 特异毒性与靶向效应。
5. 需要状态异质性时预先定义细胞类型/状态，再估计交互效应，避免先看结果后挑亚群。

## 质量门槛

报告 MOI、guide 捕获率、多重感染、每 guide 细胞数、对照分离、靶基因效率和 guide 间一致性。

## 交付

输出 guide—细胞映射、有效扰动清单、平均和状态特异效应、不确定性及验证候选；单次转录响应不能直接证明长期表型。
