---
name: antimicrobial-peptide-mic-prediction
description: 当用户需要使用 APEX 对不超过 50 个氨基酸的肽序列预测内置病原体特异性抗菌活性或 MIC 时使用；新肽生成、分子对接和内置病原体以外的外推不使用本 Skill。
---

# 抗菌肽活性与 MIC 预测

## 输入门槛

输入为氨基酸 FASTA，序列长度不超过 50 aa。验证 ID 唯一、字符属于模型支持的氨基酸集合，并报告空序列、重复序列、非标准残基和超长序列。超长序列默认拒绝或单独列出，除非用户明确要求并理解截断会改变分子含义。

运行需要 APEX 代码和完整 ensemble checkpoint。模型文件不随本 Skill 分发；使用前记录来源、版本、文件哈希、内置病原体及其训练顺序。

## 预测

可使用 `scripts/predict_apex.py` 运行本地 APEX 模型。脚本验证输入和 checkpoint，按批次执行全部 base learners 并平均预测。CPU/GPU 模式必须与实际设备一致，不能在 CUDA 不可用时伪报 GPU。

模型和输出要求见[模型适用域与输出](references/模型适用域与输出.md)。

## 输出与边界

交付以 peptide ID 为主键的病原体特异性预测表，保留原始序列、预测 MIC 单位、ensemble 数量、模型哈希、批量大小、设备、软件版本和运行状态。预测 MIC 是模型估计，不是实验 MIC；排序候选时同时考虑适用域、溶解性、毒性、稳定性和后续实验验证。
