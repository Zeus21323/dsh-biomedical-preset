# EISCA：按已完成阶段继续

## 来源与实现状态

论文：[EISCA and EISTA](https://doi.org/10.64898/2026.09.02.748851)。核验来源为 [EarlhamInst/eisca](https://github.com/EarlhamInst/eisca)，commit `e6953759e8153c31a92202e3f452f1bcbf0f9d08`（2026-09-08）。代码采用 nf-core/Nextflow 组织方式，不因为样本模式中的旧标题就宣称属于正式 nf-core 发布目录。README 的 trajectory 仍列为尚未实现，不能作为可交付能力。

本地包装器检查固定版本、原生参数模式、样本表与路径，生成可审计计划；加 `--execute` 后才调用 Nextflow。当前没有完成真实数据端到端运行认证。计划通过不代表建库协议、参考、H5AD内容或科学比较已经合格。

## 由代理准备输入，不要求新手配参数

先检查实际交付物与建库记录、物种、供体/样本、组别、批次和已完成阶段。原始 reads、计数矩阵和已注释对象不能互换；不要靠文件名猜建库化学版本。组织/供体是比较单位，细胞不是独立患者。

包装器使用 Python 3.12+、jsonschema、git；真正执行还需要匹配上游要求的 Nextflow、Java、容器或环境、CPU/内存/磁盘，并检查下载许可。安装和执行前核实实际源码及 LICENSE。源码外置，不将上游项目或数据打包入 Skill。

配置示例仅演示原生接口，路径与数值须由代理根据真实数据替换：

```json
{
  "repo": "eisca-source",
  "question": "病例与对照的细胞组成是否不同",
  "design_notes": "供体为重复单位；先完成质控，不把聚类当作疾病证据",
  "profile": "docker",
  "params": {
    "input": "samples.csv",
    "analyses": "primary,secondary",
    "protocol": "10XV3",
    "aligner": "star",
    "fasta": "reference.fa",
    "gtf": "annotation.gtf",
    "max_cpus": 8,
    "max_memory": "32.GB"
  }
}
```

`params` 按固定仓库的 `nextflow_schema.json` 校验，未知参数拒绝；不用想象中的统一接口。原始样本CSV使用上游 `assets/schema_input.json` 字段，例如 `sample,fastq_1,fastq_2,group`；多lane是否合并依据真实来源核实。路径相对于配置或原CSV解析。FASTA、GTF和reads的物种/参考一致性另做内容检查。

包装器支持 primary、secondary、tertiary 的显式有序组合。从已有对象继续时设置 `analyses: "secondary"` 或 `"tertiary"` 和 `h5ad`，仍提供真实 `sample` 元数据；不捏造FASTQ。必须另读对象确认层、细胞/基因ID与元数据，再核实本阶段实际模块和模型资源。tertiary含多个分析，不能因存在这一阶段就默认全部适用；必要时按上游 `skip` 和各分析参数排除不适合模块。未适配的细粒度模式需明确核验后再扩展，不绕过检查。

## 计划、执行与恢复

以下命令相对于 Skill 根目录，分析输出应放到用户分析项目：

```bash
python scripts/run_eisca.py --config study.json --out-dir run-plan
python scripts/run_eisca.py --config study.json --out-dir run-actual --execute
python scripts/run_eisca.py --config study.json --out-dir run-actual --execute --resume
```

输出 `plan.json`、规范化 `samplesheet.csv` 和 `params.json`。执行另存引擎日志、trace、时间线与HTML执行报告。恢复必须保持源码、参数、输入指纹一致；目录输入记录路径/大小/修改时间，不等同完整内容哈希。源文件变动时新建输出，不能强行复用缓存。计划不自动下载或计算。

状态 `engine_completed_outputs_unverified` 只表示引擎正常退出，必须继续核对各模块预期文件、样本数、细胞数、跳过/失败节点、参考映射和资源版本。空对象、全零计数、异常过滤、批次与疾病重合应停止相应解释。

## 图件与解读

基于实际数据交付样本级保留率、QC分布、批次/供体/细胞类型着色嵌入图和适用的效应图。嵌入距离不代表发生机制；差异/组成分析记录供体重复、协变量、效应、不确定性和多重检验。保存真实坐标和作图数据，PDF/SVG与高清PNG均需检查字体和布局。流程自带HTML不替代最终Markdown证据解读，也不保证所有原生图达到投稿要求。
