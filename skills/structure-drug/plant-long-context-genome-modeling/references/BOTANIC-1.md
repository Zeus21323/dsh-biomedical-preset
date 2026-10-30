# BOTANIC-1：植物序列与模型就绪性

## 来源与边界

论文：[BOTANIC-1](https://doi.org/10.64898/2026.09.04.749355)；作者提供的[模型集合地址](https://huggingface.co/collections/living-models/botanic1-6a97f4e3c33f3d109a75057d)。2026-09-08本次检查未成功取得可验证的公开checkpoint、tokenizer与推理契约，不能据标题猜HuggingFace模型ID或API。集合访问失败不等于模型永久不存在；需要使用时重新核查官方状态。

论文声称的128-kbp上下文不意味着任意序列长度、tokenizer开销、窗口模式或任务头都可直接通用。当前只提供植物FASTA与资源文件存在性检查，不生成embedding、变异效应或调控预测。不用其他DNA模型结果冒充BOTANIC-1。

## 当前可执行检查

```bash
python scripts/check_plant_sequences.py --fasta regions.fa --species "Arabidopsis thaliana" --assembly TAIR10 --out-dir sequence-check
```

需要Python 3.12+，无需GPU。物种、assembly由代理从可靠来源核实；脚本只能记录，不能验证物种真实性。FASTA需唯一标识、非空ACGTN序列；接受大小写但检查时统一大写，保存原文件与标准化序列哈希。内部空白、其他模糊字符、重复ID报错，不擅自替换或丢弃。

只有确认具体模型的有效碱基限制后才传 `--max-bases`；超过限制记录over_limit，绝不静默裁剪。可传 `--model-dir` 检查config/tokenizer_config文件是否存在；存在不等于权重有效或兼容。

输出 `sequence_qc.tsv` 与 `readiness.json`：长度、N比例、超限、来源、输入哈希和仍需核实的资源；`prediction_executed` 必须为false。只检查输入时可以交付长度/N比例QC图，不交付虚构的功能分数。

## 可执行模型适配前的门槛

核实具体checkpoint、版本、权重摘要与许可、tokenizer与有效长度、返回任务/分数量纲、上下文窗口和设备内存。阅读官方最小示例并做小样本前向检查；未经审查不打开任意remote code。失败时停止，不降级到随机权重。长序列窗口策略记录坐标、链向、边界和合并规则；变异比较必须使用匹配参考/替代背景，避免分数来自长度或窗口差异。

下游评测按物种/染色体/同源关系分割，防止近重复训练泄漏；预训练表征不自动等于新物种可靠功能预测。用户只有植物基因或表型时先核实序列和证据问题，不因“发文章”就启动大模型训练。

正式有结果后输出真实坐标轨迹、参考/替代差异和独立评测图；说明不确定性、训练覆盖和外推限制。PDF/SVG、高清PNG、作图数据、图注和Markdown解读一起交付，不把预测写成已验证调控机制。
