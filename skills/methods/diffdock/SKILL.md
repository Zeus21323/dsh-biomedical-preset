---
name: diffdock
description: 使用 DiffDock-L（Corso 等，2023/2024）预测小分子结合姿势。它通过盲扩散对接，在无需预定义搜索框的情况下将配体放入蛋白质口袋，并使用学习得到的置信度模型对样本排序。适用于将 SMILES 或 SDF 对接至 PDB、为小型片段库生成排序后的三维姿势，或为后续重打分生成起始姿势。DiffDock 预测几何构象，而非亲和力。
license: Apache-2.0
---

# DiffDock-L

DiffDock-L 是一种盲结合姿势预测器：给定蛋白质结构和配体后，它使用扩散模型在整个蛋白质表面采样配体放置方式，再使用单独训练的置信度预测头进行排序。置信度分数与姿势正确性相关，而不是与结合自由能相关——DiffDock 不预测配体是否结合，也不预测结合强度。因此，在筛选命中化合物时，仍需将它与打分器（GNINA、MM-GBSA）或 `boltz` 的亲和力预测头配合使用。对于蛋白质–蛋白质和核酸共折叠，请转用 `boltz` 或 `chai1`。代码和权重均采用 MIT 许可证（[github.com/gcorso/DiffDock](https://github.com/gcorso/DiffDock)）。

## 运行方法

```bash
cd $DIFFDOCK_REPO   # github.com/gcorso/DiffDock 的克隆目录
python3 -m inference \
  --config default_inference_args.yaml \
  --protein_path target.pdb \
  --ligand_description "COc1ccc(C#N)cc1" \
  --out_dir out
```

对于多个复合物，使用 `--protein_ligand_csv batch.csv` 代替两个单复合物参数。CSV 包含四列：`complex_name`、`protein_path`、`ligand_description`（SMILES 或 `.sdf`／`.mol2` 文件路径）和 `protein_sequence`。如果希望 DiffDock 先使用 ESMFold 折叠受体，请将 `protein_path` 留空并填写 `protein_sequence`；该流程和较大化合物库的筛选方法位于 [references/workflows.md](references/workflows.md)。

在 `--out_dir/<complex_name>/` 下，每个样本写为 `rank{N}_confidence{score}.sdf`，并额外复制一份 `rank1.sdf` 以便使用。文件名中的置信度值是 logit，因此没有上下界，也可能为负数；对于同一个复合物的不同样本，数值越高越好，但该数值不能在不同复合物或配体之间比较。

## YAML 配置会覆盖命令行参数

`inference.py` 会在 argparse 处理完成后加载 `--config default_inference_args.yaml`，并替换配置文件中出现的每个键。因此，如果 YAML 中存在相同的键，那么在命令行中传入 `--samples_per_complex 40` 或 `--model_dir ...` 会被静默忽略。如需更改采样深度或 YAML 中定义的任何其他键，请复制该 YAML、编辑副本，然后通过 `--config` 指向它。

## 首次运行会静默约 11 分钟，并且需要至少 32 GB 主机内存

处理第一个复合物之前，DiffDock 会预计算 SO(3) 和环面查找表。该步骤不会向 stderr 输出信息，耗时约 11 分钟；在默认 Modal 规格上，它会耗尽主机内存，并在预计算过程中被 SIGKILL。请设置 `provider_params.modal.memory: 65536`（或当前提供商的等效配置），不要因为没有输出就认定程序已经崩溃。

## README 中的 `--ligand` 只是在 CLI 上偶然可用——请使用 `--ligand_description`

上游 README 使用了 `--ligand`；它之所以有效，只是因为 argparse 会将该前缀匹配到真正的参数 `--ligand_description`。这个缩写只适用于 CLI：如果将 `ligand` 用作 CSV 列标题或 YAML 键，它不会匹配任何内容，并且该行会被静默视为没有配体。请始终完整写出参数和列标题。

## 值得识别的错误

| 你看到的现象 | 含义／处理方法 |
| --- | --- |
| 启动时出现 `ValueError: not allowed to raise maximum limit` | `setrlimit(NOFILE, 64000)` 超出了沙箱的硬限制——使用 `sed` 将 `inference.py` 中的常量改为 `min(64000, rlimit[1])`。 |
| SO(3) 预计算开始几分钟后无提示地被 SIGKILL | 主机内存耗尽——参见上面的注意事项。 |
| `python3: not found` | 当前使用的是上游 `rbgcsail/diffdock` 镜像——该镜像通过 `micromamba` 从 `/home/appuser/DiffDock` 运行。 |

---

**下一步：** 在跨配体排序之前，对 `rank1.sdf` 姿势重新打分——项目内可使用 `boltz` 的亲和力预测头——因为仅凭 DiffDock 置信度预测头不能预测亲和力。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** DiffDock-L（MIT）— [条款](https://github.com/gcorso/DiffDock/blob/main/LICENSE)
