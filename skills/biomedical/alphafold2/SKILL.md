---
name: alphafold2
description: "使用 ColabFold 运行器和 AlphaFold2/AlphaFold2-Multimer 预测蛋白质单体、多聚体与复合物结构，并通过 pLDDT、ipTM 和 RMSD 评估预测与设计质量。"
metadata: {"source": "upstream-biomedical-science@0.1.1", "origin": "upstream-plugin", "license": "Apache-2.0"}
---

**AlphaFold2**

# **AlphaFold2**

**精选**

更新于 2 周前

通过 ColabFold 运行器使用 AlphaFold2 预测蛋白质单体和多聚体结构（ColabFold：Mirdita 等，2022，github.com/sokrypton/ColabFold；AlphaFold2：Jumper 等，2021）。当需要使用 AF2/AF2-Multimer Evoformer 折叠序列或复合物、通过自洽性 pLDDT、ipTM 和 RMSD 验证设计序列，或使用公共 MMseqs2 服务器快速运行基于 MSA 的预测时，请使用此技能。

**文件**

# **AlphaFold2（ColabFold 运行器）**

此技能通过 `colabfold_batch` 封装 AlphaFold2 和 AlphaFold2-Multimer。该工具使用公共 MMseqs2 服务器调用替代 DeepMind 基于本地数据库的 MSA 流程，因此一次预测只需一条命令和一个 FASTA 文件，而无须挂载 2 TB 的数据库。AF2 仍是单体结构预测的基准模型，多聚体模型也仍是强有力的蛋白质–蛋白质验证工具，但它不能处理配体或核酸；对于这些对象，请转用 `boltz`、`chai1` 或 `openfold3`。ColabFold 代码采用 MIT 许可证（github.com/sokrypton/ColabFold），AlphaFold2 代码采用 Apache-2.0 许可证（github.com/google-deepmind/alphafold）；AF2 模型参数采用 CC-BY-4.0 许可证，并受 DeepMind 使用条款约束。

## **运行方法**

```bash
colabfold_batch input.fasta out \
  --num-recycle 3 \
  --model-type alphafold2_multimer_v3
```

输入是普通 FASTA 文件。对于复合物，将每条链放在同一序列行中，并用 `:` 分隔——`colabfold_batch` 会为每个片段构建配对 MSA，并在检测到冒号时运行多聚体模型（因此，上面显式指定 `--model-type alphafold2_multimer_v3` 是为了双重保险）。对于单体，请省略 `--model-type` 和冒号。`--templates` 和 `--amber` 分别用于添加 PDB 模板和执行 OpenMM 松弛；两者默认均关闭，并且都会使每个模型的运行时间增加数分钟。

默认情况下，ColabFold 会运行全部五组 AF2 模型权重，并按 pLDDT 排名（对于多聚体，则按 pTM/ipTM 排名）。因此，每个查询的输出都会写入 `out/`，包括五个已排序的 PDB 文件 `<name>_unrelaxed_rank_00{1..5}_*.pdb`（B-factor 列存放 pLDDT），以及对应的 `<name>_scores_rank_00{N}_*.json` 文件，其中包含 `plddt`、`ptm`，对于多聚体还包含 `iptm` 和 `pae` 矩阵。应首先查看排名第 1 的模型；通常将 ipTM > 0.5 作为界面通过的宽松标准。

## **统一内存的默认设置会在 gVisor 下无限循环——环境补丁会将其移除**

导入时，`colabfold/batch.py` 会强制设置 `TF_FORCE_UNIFIED_MEMORY=1` 和 `XLA_PYTHON_CLIENT_MEM_FRACTION=4.0`。在 gVisor 沙箱下，统一内存不受支持，因此 JAX 的 `device_put` 会在加载 AF2 参数期间陷入无限循环，不断分配主机内存——作业看起来像是卡住了，但始终不会报错。请在导入前覆盖这两个设置（`TF_FORCE_UNIFIED_MEMORY=0`，内存比例设为 `0.95`），或者在构建镜像时使用 `sed` 从 `batch.py` 中移除这两处赋值，否则第一次折叠预测永远不会开始。

## **MSA 服务器是实际耗时的瓶颈，而且属于共享资源**

`colabfold_batch` 默认使用 `--msa-mode mmseqs2_uniref_env`，它会将序列提交到 `api.colabfold.com`。该服务器是受速率限制的公共资源：对于耗时较短的折叠任务，等待时间占据主要部分，并且在负载较高时偶尔会超时。对于批量任务，请先使用 `--msa-only` 运行一次 MSA 阶段，保留生成的 `.a3m` 文件，然后在后续运行中将该目录作为输入——这样 GPU 阶段会立即开始，并且不会再次访问该服务器。

## **值得识别的错误**

| **你看到的现象** | **含义／处理方法** |
| --- | --- |
| 作业在 `Running model_1` 阶段无提示地卡住，同时主机内存持续增长 | gVisor 下的统一内存循环——参见上文注意事项；覆盖相关设置或修补 `batch.py`。 |
| XLA 编译期间出现 `RESOURCE_EXHAUSTED`／OOM | `XLA_PYTHON_CLIENT_MEM_FRACTION` 对 GPU 而言设置过高——将其从默认的 `0.95` 下调至 `0.9` 左右。 |
| MSA 阶段卡在 `Submitting job` | 公共 MMseqs2 服务器正在限流——请等待，或使用 `--msa-only` 预先计算，然后从缓存的 `.a3m` 文件重新运行。 |

---

**下一步：** 对于设计序列验证，请使用 US-align 将排名第 1 的模型叠合到设计骨架上，并根据 pLDDT/ipTM 阈值决定是否通过；对于含配体的复合物，请将相同的链交给 `boltz` 或 `chai1`。

### **详细信息**

#### **作者**

Anthropic

#### **许可证**

Apache-2.0

#### **第三方软件、内容、条款和信息**

权重 — AlphaFold2 · Google DeepMind（CC-BY-4.0）— [条款（在新标签页中打开）](https://github.com/google-deepmind/alphafold#model-parameters-license)发送数据至 — ColabFold MSA 服务器（api.colabfold.com）· Steinegger Lab — [信息](https://github.com/sokrypton/ColabFold/wiki)

\
