# RevPert：方法、资源与执行契约

## 使用范围与出处

RevPert 将观测或期望的转录组变化作为查询，在给定遗传扰动响应 gallery 中检索候选扰动。本入口归属于“单细胞与虚拟细胞”，以逆向任务组织，而不以论文名建立独立 Plugin；bulk 来源的兼容查询也可使用。给定基因预测表达变化是正向任务，不是本入口的默认职责。

方法出处为 [RevPert 作者仓库](https://github.com/gityuling/RevPert)，对应题名“RevPert: predicting candidate drivers of transcriptomic state transitions via gallery-native reverse perturbation”的[预印本记录](https://doi.org/10.64898/2026.08.19.745674)。当前接口核验以作者代码为准，不声称已复现论文生物学结果。

包装器固定支持 commit `0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca` 的 Gallery-Dual Essential 实现：位于[上游脚本目录](https://github.com/gityuling/RevPert/tree/0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca/reverse/scripts)的 `run_gallery_dual_g2.py`。PCA 与基础模型见 [reverse_model.py](https://github.com/gityuling/RevPert/blob/0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca/reverse/src/reverse_model.py)，Pearson 定义见 [score.py](https://github.com/gityuling/RevPert/blob/0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca/reverse/src/score.py)。上游代码为 MIT；数据、模型与第三方资源的权限需另查，不随本 Skill 分发。

## 三种模式及边界

| 模式 | 必需资源 | 实际执行 |
| --- | --- | --- |
| `check` | 查询、gallery、背景配置 | 检查特征覆盖、数据完整性；若提供模型配置则核验版本和资源指纹，不加载模型 |
| `pearson` | 同上 | 在共同表达特征上计算有符号 Pearson，分别对正反查询排序；不是完整 RevPert |
| `revpert` | 同上，加固定版本源码、Essential checkpoint 和训练资源 metadata | 独立编码正反查询，计算学习评分，按 checkpoint 的 `alpha_star` 与 Pearson 融合 |

模型模式不会自动下载权重、训练模型、改变上游文件或退回基线。没有匹配的权重与训练资源时，说明缺口；只有用户同意基线分析才执行 `pearson`。脚本不负责从原始 FASTQ/AnnData 自动完成差异分析，不负责供体重采样、富集、药物推荐或实验验证。

## 输入与科学前提

明确 A、B、物种、组织/细胞系、细胞类型、处理、时间点、独立生物学重复和对比模型。查询统一为 `B − A`：plus 匹配这一方向的扰动响应；minus 匹配其反方向。gallery 每行必须定义为“扰动后 − 匹配对照”。方向声明依赖数据准备记录，脚本无法从数值证明方向正确。

单细胞查询应在目标细胞类型内进行供体层比较或适当的重复测量建模，避免把细胞数量当成独立样本量。bulk 查询需说明组成混杂。不强制任何研究都从单细胞开始：优先选择能表达待回答问题且与 gallery 尺度匹配的签名。

查询与 gallery 的归一化、基因标识及表达尺度需一致。例如，规范化表达均值差不能仅改标签就当作 log2 fold change；P 值、排名和仅含显著基因的列表不是完整表达响应。重复标识或物种映射必须在准备阶段制定明确规则，脚本不自动平均、推断同源关系或补造响应。

`query.tsv` 为 UTF-8、制表符分隔，严格两列表头 `gene`、`value`；每个基因一次，数值有限。行顺序可不同，脚本按 gallery 基因轴重排。

`gallery.npz` 是不含 pickle/object 的 NumPy 压缩包：

| 字段 | 类型与形状 | 含义 |
| --- | --- | --- |
| `genes` | Unicode/bytes 字符串一维数组，长度 G | 表达特征轴，不是候选扰动轴 |
| `kos` | 字符串一维数组，长度 K | 候选基因扰动目录及原始顺序 |
| `deltas` | 有限数值矩阵，K × G | 每个候选扰动相对对照的表达响应 |

使用已核实的数据保存，例如 `np.savez_compressed("gallery.npz", genes=np.asarray(gene_names, dtype=str), kos=np.asarray(ko_names, dtype=str), deltas=delta_matrix)`。这些变量必须来自实际资源，不能用差异基因列表代替候选目录。预测 gallery 要记录正向模型、训练数据与版本；实测 gallery 要记录实验来源。不得混用不同模型的响应矩阵。

## 运行配置

以下是结构示例，所有生物学描述须替换为实际记录。文件路径相对配置文件所在目录解释；输出目录相对命令工作目录解释。

```json
{
  "query": "query.tsv",
  "gallery": "gallery.npz",
  "state_a": "敏感状态",
  "state_b": "耐药状态",
  "direction": "B-A",
  "species": "Homo sapiens",
  "query_context": "同一细胞系与培养条件",
  "gallery_context": "同一细胞系与培养条件",
  "expression_scale": "normalized_expression_mean_difference",
  "gallery_scale": "normalized_expression_mean_difference",
  "gallery_kind": "observed",
  "gallery_source": "替换为数据编号、版本及扰动和对照定义",
  "contrast_notes": "替换为独立样本数、对比模型、归一化和签名生成记录",
  "min_genes": 10,
  "min_coverage": 0.8,
  "top_k": 20,
  "focus_genes": [],
  "device": "cpu"
}
```

`gallery_kind` 为 `observed` 或 `predicted`。背景标签不同时须增加 `extrapolation_reason`，例如细胞类型差异对可迁移性的限制；不能为了通过校验把不同背景写成相同名称。

覆盖率定义为“查询覆盖的 gallery 特征数 / gallery 特征总数”。默认最低 10 个共同基因、80% 覆盖仅为包装器工程门槛，不是论文验证的生物学充分性标准；通过门槛不表示结果可靠。降低覆盖阈值须说明理由，不能为了获得期望候选调节。Pearson 只使用共同特征；学习模型按上游约定将缺失查询位置填 0，需单独评估该假设。常量查询、常量 gallery 行和非有限响应被拒绝。

`focus_genes` 仅用于检查关注基因是否在候选目录，不过滤评分集合。模型融合标准化依赖整个候选目录，不能先只保留目标基因或随意删除“排名不理想”的扰动。

## 环境与已有模型

基础模式需要 Python 3.12+ 和 NumPy。模型模式另外需要 Git、PyTorch（支持 `weights_only=True` 与 `safe_globals`，2.6+）、pandas、SciPy、anndata；上游模块导入会使用这些库。按项目建立独立环境，并记录实际安装版本；不在使用者已有环境中自动升级依赖。

源码准备示例：

```bash
git clone https://github.com/gityuling/RevPert.git vendor/RevPert
git -C vendor/RevPert checkout 0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca
```

已有模型模式在上述配置增加以下字段：

```json
{
  "upstream_repo": "vendor/RevPert",
  "checkpoint": "model/gallery_dual_best.pt",
  "model_metadata": "model/model_metadata.json"
}
```

仅加载来源可信的源码与模型。固定 commit 和指纹用于可追溯性，不替代来源审查。脚本要求上游已跟踪文件无改动；只通过限制类型的 `weights_only=True` 读取 checkpoint，不回退至任意 pickle。未知序列化类型应停止核查，不以关闭安全加载解决。

支持的 checkpoint 必须包含 `model`、`pca`、`args`、`gal_kos`、`alpha_star`，其中 `args` 含 `emb_dim`、`hidden`、`dropout`、`shared`。按上游结构重建 GalleryDual，并严格加载模型参数。仅维度相同并不意味着模型与输入兼容。

上游 Essential checkpoint **未保存完整的基因名称轴**。因此必须由原训练资源生成 sidecar `model_metadata.json`，至少包含：

```json
{
  "upstream_commit": "0fe09328cc8d42bbcfa2b200c40ba6a0e6ea89ca",
  "genes": ["按原训练数据顺序填写全部基因，不能保留本示例文字"],
  "gallery_sha256": "实际 gallery.npz 的 SHA256",
  "checkpoint_sha256": "实际 checkpoint 的 SHA256",
  "gallery_context": "与训练 gallery 及运行配置一致",
  "gallery_scale": "与训练 gallery 及运行配置一致",
  "gallery_kind": "observed",
  "species": "Homo sapiens"
}
```

`genes` 必须核对原训练 `gene_names` 和 PCA 特征轴，`kos` 必须核对 checkpoint 的 `gal_kos`，gallery 必须是同一训练关联资源。推荐 sidecar 额外记录训练数据编号、split、预处理版本与创建人。**不能根据待分析文件临时编一个 sidecar 来“通过”校验**。若没有原训练记录，就不能确认模型可用。SHA256 可用 `shasum -a 256` 获取；脚本核对的是具体文件字节。

## 评分与结果解读

脚本导入固定上游的 `score_learned_np` 和 `fuse_scores`，而非另写一个“类似 RevPert”的学习模型。正查询与负查询分别编码。`alpha_star=0` 时最终分数等于 Pearson；一般有限正权重按查询行分别标准化后融合；上游将大于 `1e6` 的权重视为仅学习评分。脚本使用保存的 `alpha_star`，不自动改用 `alpha_retune` 或在测试查询上调参。

评分输出：

- `ranking.tsv`：全目录的 `pearson_plus/minus`、`learned_plus/minus`、最终 `score_plus/minus`、各臂名次及 Pearson 名次。基线模式的学习评分为空。`n_genes_scored` 指共同表达特征数；模型仍使用完整特征轴和缺失填零。
- `shortlist.tsv`：两臂分别截取前 `top_k`，保留 `arm`；目录较小时两臂可出现同一个候选。
- `coverage.json`：表达特征覆盖、查询多余基因、缺失基因、无法评价的关注基因及外推警告。
- `run_manifest.json`：方法标签、实际配置、输入指纹、上游版本、Python/NumPy/PyTorch 版本、权重与运行状态。
- `report.md`：机器生成的运行摘要及证据链接；不是自动完成的文献综述或机制论证。

同分按候选目录原始顺序稳定排列，不能将微小名次差异当作显著性。Pearson 基线两臂互为反号；学习及融合分数不保证如此。plus 不等于“激活该基因”，minus 不等于“治疗有效”。输入是 KO 响应时，候选指 KO 扰动；不能将负 KO 直接当成真实过表达。

交付时进一步说明：哪些候选跨合理签名构建或独立数据稳定；哪些仅有单次检索支持；是否有细胞背景外推；是否存在训练、PCA、正向库或评估泄漏。没有重复数据就不虚构置信区间，没有实验就不宣称已证明因果驱动。高排名应形成下一步验证优先级，而非确定性机制结论。

## 超出当前脚本范围的请求

重训练先检查原始数据、正向 gallery、训练/验证/测试划分、计算预算和依赖。上游 `run_gallery_dual_g2.py` 是带特定数据与疾病查询的训练流程，不是传任意 query 即可运行的通用 CLI；其 `--skip_gwps` 也不能先验保证不再加载相关资源。未经适配和验证，不把直接运行它写成已支持的训练能力。

GWPS checkpoint 的字段和训练背景不同，当前包装器明确拒绝；其他模型版本、药物响应库或多基因组合也需另行适配。用户只要求解释论文时提供方法说明，不启动计算。用户只有公共数据研究需求时不自动加入本分析；本 Skill 已产出的文件可在用户需要时交给公共数据研究报告使用，无需复制本方法到其主流程。
