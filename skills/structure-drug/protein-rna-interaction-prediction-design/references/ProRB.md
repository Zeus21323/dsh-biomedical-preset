# ProRB：配对、位点与设计分别审查

## 核验来源与实际障碍

论文：[ProRB](https://doi.org/10.1093/nar/gkag870)，[作者v2.2源码](https://github.com/ymaa19/ProRB/tree/v2.2)，[归档](https://doi.org/10.5281/zenodo.21447682)。2026-09-08核验commit `6b18f2d144251fc5b8a5ac465528afe07c25da08`：

- `predict_affinity.py` 含硬编码RNA编码器路径，其直接执行入口只打印就绪消息，并不产生预测；
- `predict_bind_site.py` 的权重加载错误可能被捕获而继续，不能用“进程没有退出”证明模型正确加载；
- `generate.py` 含作者机器路径并依赖未初始化的处理函数/模型对象，不能直接作为可复现生成命令。

因此本Skill当前可执行部分为输入检查及已有评分的身份关联，不声称已实现完整ProRB推理/设计。真正运行前还需权重、基础编码器、接口修复与验证、许可及环境核验。不得为满足运行而使用随机参数。

## 配对输入及已有结果

代理从可靠记录获取物种、蛋白isoform和准确RNA序列，不把基因名直接当序列。配对CSV格式：

```csv
pair_id,prot_seq,rna_seq
synthetic_pair_1,ACDEFGHIKLMNPQRSTVWY,ACGUACGU
synthetic_pair_2,ACDEFGHIKLMNPQRSTVWY,GGCAUACG
```

这是合成输入示例，不是生物学候选或论文结果。蛋白仅接受20种标准大写氨基酸；RNA仅ACGU。T、修饰、模糊字符和大小写转换需要先说明处理依据；脚本不自动转换。pair_id唯一；同序列配对保留并标记重复。

```bash
python scripts/check_prorb_inputs.py --pairs pairs.csv --out-dir pair-check
python scripts/check_prorb_inputs.py --pairs pairs.csv --scores scores.csv --score-source "模型版本、运行记录及分数量纲" --out-dir scored-check
```

Python 3.12+，不加载模型。已有scores.csv包含 `pair_id,score`，必须与全部配对一一对应、无重复且有限；按ID关联而非行号。保存 `pair_qc.tsv`、`readiness.json` 与源文件SHA256，记录 `prediction_executed: false`。关联成功不代表原始分数可信，必须另核实运行记录。

## 预测/设计门槛与解释

完整适配必须确保：权重加载失败立即退出、严格检查缺失/额外参数、模型为eval模式、tokenizer及padding正确、序列长度不静默截断、输出ID及残基/核苷酸位置可回溯。用官方可核实示例检查数值和形状，记录checkpoint、依赖、种子、设备与精度。当前检查脚本不执行这些模型验证。

配对分数、位点概率、生成候选是不同任务，不混用指标。没有训练目标及标定证据不能把分数改称Kd/pKd。注意力不等于结合位点。生成记录采样与过滤全部参数；自评分筛出的高分属于选择过程，不是独立实验验证。

有真实结果时，配对用带真实单位的候选点图，位点用真实序列索引曲线，设计用多样性/组成与独立评估图。仅输入QC不能画结合性能。直接交付PDF/SVG、高清PNG、作图表、图注和Markdown报告；报告区分预测、机制假设和实验结果，保留低分/失败候选及适用域限制，不承诺特异性、疗效或安全性。
