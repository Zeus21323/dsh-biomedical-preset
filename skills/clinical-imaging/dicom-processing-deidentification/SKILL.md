---
name: dicom-processing-deidentification
description: 当用户需要读取、检查、转换或安全去标识DICOM影像与元数据时使用。
---

# DICOM影像处理与去标识

先区分临床原件、受控中间副本和可共享副本；任何处理都在副本上进行。建立 Patient/Study/Series/SOP UID 关系，确认模态、序列、切片顺序和像素数据可解码。

## 去标识范围

标准患者标签、日期、机构、操作者和 accession 之外，还要审查私有标签、结构化报告、overlay、burned-in annotation 和文件名。UID 重映射应稳定且保持引用关系；若平移日期，同一受试者内保持时间间隔。

头颅影像是否需要 defacing 由共享风险决定。去标识后扫描残留文本，并核对像素、方向、spacing、序列数量和引用对象未损坏。

交付处理后的 DICOM/转换影像、删除或替换的标签规则、UID/日期策略和验证结果。身份映射只在授权位置保存，不随影像包交付。
