---
name: bids-neuroimaging-data-organization
description: 当用户需要组织、检查或转换符合BIDS规范的MRI、PET、EEG、MEG或其他神经影像研究数据时使用。
---

# BIDS神经影像数据整理

先盘点受试者、session、任务、模态、运行次数和原始文件，确定采用的 BIDS 版本与扩展。原始 DICOM 去标识属于前置工作，转换后仍需检查侧车 JSON 是否含敏感字段。

建立 subject/session/run 映射，生成 dataset_description、participants、模态侧车和任务 events。命名实体只在有真实含义时使用；不能为通过验证器虚构 TaskName、相位编码或扫描参数。

运行 BIDS Validator 后按错误原因修正，并抽查 NIfTI 方向、体素、扫描数量和事件时间是否与原始记录一致。遗失的元数据列入缺口，不用默认值掩盖。

交付符合规范的目录、参与者/扫描映射、验证报告和未解决警告。映射表若能连接研究 ID 与身份，必须与可共享数据分开保管。
