# EISTA：空间数据阶段化处理

## 来源及适用边界

论文：[EISCA and EISTA](https://doi.org/10.64898/2026.09.02.748851)。适配 [EarlhamInst/eista](https://github.com/EarlhamInst/eista) commit `f419485a7ec788e86ae4e499ccdc7fe68a064d30`，2026-09-08核验。它使用 nf-core/Nextflow 结构，不能据此替换成未经核实的 `nf-core/eista` 远程执行名。

当前包装器只接受上游已核实的 `vizgen`、`xenium` 技术。其他平台留在空间分析主流程按各自接口处理，不强行转换。没有空间坐标的普通单细胞数据不能生成“组织原位”证据。平台面板覆盖、分割边界、坐标单位和切片来源决定可比较问题。

## 输入契约与执行

Python 3.12+、jsonschema和git用于计划检查；真正运行需匹配的Nextflow/Java/容器及资源。固定源码必须无已跟踪修改，安装前检查LICENSE。参数遵照本地上游 `nextflow_schema.json`，样本CSV遵照 `assets/schema_input.json`。

```json
{
  "repo": "eista-source",
  "question": "目标细胞是否富集于组织边缘",
  "design_notes": "分别保留供体和切片；不将所有空间点作为独立生物学重复",
  "profile": "docker",
  "params": {
    "input": "samples.csv",
    "technology": "xenium",
    "analyses": "primary,secondary",
    "max_cpus": 8,
    "max_memory": "32.GB"
  }
}
```

原始阶段CSV含 `sample,data`，可有 `merge,group`；data是平台原始导出目录。代理要检查目录内部是否真的包含平台要求的计数、细胞、坐标/分割等文件；路径存在并不足以通过科学验收。上述资源限额是示例，不是默认适合值。

已有h5ad时选择secondary/tertiary、提供 `h5ad` 与真实sample表，再核验表达层、空间坐标、图像变换、单位、细胞ID和上游模块要求。包装器不会重新创造丢失的空间信息。

```bash
python scripts/run_eista.py --config study.json --out-dir run-plan
python scripts/run_eista.py --config study.json --out-dir run-actual --execute
python scripts/run_eista.py --config study.json --out-dir run-actual --execute --resume
```

输出规范化参数/样本表、版本与输入指纹、执行命令；执行时有日志、trace和结果目录。阶段必须显式有序选择，输出不覆盖；恢复要求指纹不变。目录按路径/大小/mtime记录，需要高保障时另做逐文件内容校验。源码版本改变必须重新适配。

本适配尚未通过真实空间数据端到端验证。引擎成功只是 `engine_completed_outputs_unverified`：继续检查样本、坐标、分割与所有预期产物；没有结果就报告阻断，不以流程图代替结果图。

## 直接交付而非只教用户画图

按实际问题生成细胞/区域空间图、样本级QC和效应图，保留真实坐标、等比例坐标轴、单位/比例尺、切片方向、缺失区域与来源；不能为了好看拉伸空间位置或翻转未记录图像。采用PDF/SVG和高清PNG并输出作图表、图注、Markdown解读。

空间邻接不等于通讯，定位共现不等于功能因果。面板未覆盖不能判定基因不表达；控制组织区室、分割误差、样本/切片伪重复。统计不确定性必须针对真实重复单位；不足时仅描述、不编造p值。
