---
name: chai1
description: "使用 Chai-1 基础模型（Chai Discovery，2024，github.com/chaidiscovery/chai-lab）预测蛋白质、核酸和小分子复合物结构。适用于从单个 FASTA 预测抗体—抗原或蛋白质—配体复合物、将设计的结合蛋白重新折叠并作为 AlphaFold-Multimer 的替代方案，或通过 Python 在 GPU 上执行批量共折叠任务。"
metadata: {"source": "upstream-biomedical-science@0.1.1", "origin": "upstream-plugin", "license": "Apache-2.0"}
---

# Chai-1

Chai-1 是与 Boltz-2 和 AlphaFold3 同属一类的全原子扩散共折叠模型：输入包含多个实体的 FASTA，输出 mmCIF 以及 pTM、ipTM 和 pLDDT 置信度；蛋白质、RNA、DNA 和 SMILES 配体链都是一等输入类型。它与 `boltz` 覆盖相同的应用范围；同时运行二者并保留通过任一模型的设计，是一种常见的共识筛选方式。Chai 的 Python 入口使它比二者中的另一个更容易嵌入循环。代码和权重均采用 Apache-2.0 许可证，并明确允许包括药物发现程序在内的商业用途（[github.com/chaidiscovery/chai-lab](https://github.com/chaidiscovery/chai-lab)）。

## 运行方法

```python
from pathlib import Path
from chai_lab.chai1 import run_inference

Path("complex.fasta").write_text("""
>protein|name=target
MVTPEGNVSLVDESLLVGVTDEDRAVRS...
>protein|name=binder
AIQRTPKIQVYSRHPAENG...
>ligand|name=cofactor
CCCCCCCCCCCCCC(=O)O
""".strip())

candidates = run_inference(
    fasta_file=Path("complex.fasta"),
    output_dir=Path("out/"),
    num_trunk_recycles=3,
    num_diffn_timesteps=200,
    seed=42,
    device="cuda:0",
    use_esm_embeddings=True,
)
print([rd.aggregate_score.item() for rd in candidates.ranking_data])
```

FASTA 标题格式为 `>{entity_type}|name={id}`，其中 `entity_type` ∈ {`protein`, `rna`, `dna`, `ligand`}；配体记录以 SMILES 字符串作为序列正文，修饰残基以内联形式表示，例如 `...AAK(SEP)AAG...`。在命令行中，同一任务可写为 `chai-lab fold complex.fasta out/ --use-msa-server`。如果没有启用 `--use-msa-server`（Python 中对应 `use_msa_server=True`），模型将仅依赖 ESM 嵌入运行；这种方式更快，但其 ipTM 通常比使用 MSA 的运行低几个点。

`output_dir` 中会生成 `pred.model_idx_{0..4}.cif`，并为每个样本生成相应的 `scores.model_idx_{N}.npz`，其中包含 `aggregate_score`、`ptm`、`iptm`、`per_chain_ptm` 和碰撞标志。按 `aggregate_score` 排序；可将 `iptm > 0.5` 视为界面通过的宽松标准。函数会拒绝非空的 `output_dir`，因此每次调用之间必须清空该目录或将其轮换到新路径。

## 未设置 `CHAI_DOWNLOADS_DIR` 时，只读镜像会在运行中途因 PermissionError 失败

Chai 会在第一次推理调用时下载约 5 GB 内容，而不是在安装时下载；其中包括嵌入路径所需、由 Chai 自己提供的跟踪版 ESM2-3B。如果没有设置 `CHAI_DOWNLOADS_DIR`，默认路径位于 `site-packages` 内：在只读镜像中，会在运行中途因令人困惑的 `PermissionError` 失败；在可写镜像中，则会在每次冷启动时静默地把约 5 GB 内容重新下载到容器。应将该变量导出到持久化卷，使下载只发生一次。

## 无 MSA 模式仍会加载 30 亿参数 ESM——显存相同，并不会更少

在不使用 MSA 的情况下设置 `use_esm_embeddings=True`，仍会把一个 30 亿参数的语言模型与主干模型一同加载到 GPU 显存中；它消除的是往返 MSA 服务器的过程，而不是显存成本。如果出现 OOM，应降低 `num_diffn_timesteps`，或在每次调用中折叠更少的链，不要期望无 MSA 模式能够适配显存更小的 GPU。

## 值得识别的错误

| 看到的错误 | 含义及处理方法 |
| --- | --- |
| `site-packages/chai_lab/...` 下出现 `PermissionError` | 在只读镜像上没有设置 `CHAI_DOWNLOADS_DIR`——将其导出到可写路径或预填充的挂载点。 |
| ESM 嵌入阶段出现 `RuntimeError: CUDA out of memory` | 跟踪版 ESM2-3B 正与主干模型一同加载——使用 80 GB 级 GPU，或把不同链拆分到多次调用中。 |

---

**下一步：** 根据置信度和碰撞指标筛选通过的结构，或将其送回 `proteinmpnn` 开始下一轮设计。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

权重——Chai-1 · Chai Discovery（Apache-2.0）——[条款](https://github.com/chaidiscovery/chai-lab/blob/main/LICENSE)

向以下服务发送数据——ColabFold MSA server（`api.colabfold.com`）· Steinegger Lab——[信息](https://github.com/sokrypton/ColabFold/wiki)
