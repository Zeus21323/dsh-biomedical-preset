---
name: openfold3
description: 使用 OpenFold3 进行结构预测。OpenFold3 是 AlQuraishi 实验室开发的 AlphaFold3 开放权重 PyTorch 复现。适用于使用 Apache-2.0 许可的 AF3 复现模型预测蛋白质、核酸和配体复合物结构。
license: Apache-2.0
---

# OpenFold3 结构预测

## 先决条件

| 要求 | 最低配置 | 推荐配置 |
| --- | --- | --- |
| Python | 3.10+ | 3.11 |
| CUDA | 12.1+ | 12.4+ |
| GPU 显存 | 24 GB | 80 GB（H100） |
| 内存 | 32 GB | 64 GB |
| 磁盘空间（权重） | 3 GB | — |

## 运行方法

### 安装

```bash
pip install 'openfold3[cuequivariance]==0.4.1'
```

默认注意力内核为 DeepSpeed `DS4Sci_EvoformerAttention`。如果 DeepSpeed 不可用，可在 `model_config.py` 中覆盖评估阶段的内存设置，切换到 cuEquivariance 三角内核（无需从源码构建）：将 `use_deepspeed_evo_attention` 设为 `False`，并将 `use_cueq_triangle_kernels` 设为 `True`。某些预构建环境已经包含该覆盖设置；再次修改前先检查。

### 权重

权重采用 Apache-2.0 许可证，大小约 2.3 GB，来自 Hugging Face 上的 `OpenFold/OpenFold3`。该仓库设有访问门槛，但会自动批准——下载前应在 Hugging Face 模型页面接受访问表单并完成身份验证（`huggingface-cli login` 或设置 `HF_TOKEN`）：

```bash
export OPENFOLD_CACHE=~/.openfold3
huggingface-cli download OpenFold/OpenFold3 checkpoints/of3-p2-155k.pt \
  --local-dir "$OPENFOLD_CACHE"
```

如果网络出口开放、Hugging Face 凭据可用（设置了 `HF_TOKEN` 或此前执行过 `huggingface-cli login`），并且已获该仓库访问权限，`run_openfold` 也会在第一次运行时自动将权重下载到 `$OPENFOLD_CACHE`。交互式辅助程序 `setup_openfold` 也可用于设置，但会在标准输入上发出提示；对于非交互式运行，优先使用上面的显式下载方式。

### 运行

```bash
export OPENFOLD_CACHE=/path/to/cache
run_openfold predict \
  --query_json=queries.json \
  --output-dir out/ \
  --use-msa-server false \
  --use-templates false
```

`run_openfold` 会自动发现 `$OPENFOLD_CACHE` 下的检查点。只有当目录布局并非标准形式，或存在多个检查点且需要明确固定其中一个时，才传入 `--inference-ckpt-path <file.pt>`。

若要使用 MSA 和模板（速度更慢，但准确度更高），去掉两个值为 `false` 的参数。MSA 服务器是 `api.colabfold.com`；模板链 ID 的重新映射会访问 `data.rcsb.org`（GraphQL）——两者都必须能够访问。

## 查询 JSON 格式

OpenFold3 不读取 FASTA。查询必须是一个由 `InferenceQuerySet` 验证的 JSON 对象（Pydantic，`extra: forbid`——出现未知键时会拒绝输入）：

```json
{
  "queries": {
    "my_complex": {
      "chains": [
        {"molecule_type": "protein", "chain_ids": ["A"], "sequence": "MQIFVK…"},
        {"molecule_type": "protein", "chain_ids": ["B", "C"], "sequence": "MVLSPA…"},
        {"molecule_type": "ligand",  "chain_ids": ["L"], "smiles": "CC(=O)Oc1ccccc1C(=O)O"}
      ],
      "use_msas": true
    }
  },
  "seeds": [42]
}
```

| `molecule_type` | 必填字段 |
| --- | --- |
| `protein` / `dna` / `rna` | `sequence` |
| `ligand` | `smiles` 或 `ccd_codes: ["HEM"]` |

`chain_ids` 是一个列表——对于同源寡聚体，应在多个链 ID 上重复使用同一条序列。每条链的 `paired_msa_file_paths` / `main_msa_file_paths` 可用于提供自己的 A3M 文件，从而不使用服务器。

## 关键参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--num-diffusion-samples` | 5 | 每个查询和种子组合生成的结构数 |
| `--num-model-seeds` | 1 | 每个查询的模型种子数量；它会与 JSON 中的 `seeds` 数量和扩散样本数共同相乘，决定输出总数 |
| `--use-msa-server` | `true` | 使用 ColabFold MMseqs2 服务器生成 MSA |
| `--use-templates` | `true` | 使用 ColabFold 模板搜索和 RCSB 重新映射 |
| `--inference-ckpt-path` | 自动发现 `$OPENFOLD_CACHE` 下的检查点 | 仅用于覆盖默认行为——适用于非标准目录布局，或固定某个特定检查点文件 |

## 输出格式

```text
out/
├── summary.txt
├── model_config.json / experiment_config.json
├── inference_query_set.json
└── <query_name>/seed_<N>/
    ├── <query>_seed_<N>_sample_<k>_model.cif
    ├── <query>_seed_<N>_sample_<k>_confidences.json           # 完整 PAE/pLDDT
    ├── <query>_seed_<N>_sample_<k>_confidences_aggregated.json
    └── timing.json
```

应首先读取体积较小的 `*_confidences_aggregated.json`：

```json
{
  "avg_plddt": 78.96, "ptm": 0.667, "iptm": 0.0, "gpde": 0.73,
  "has_clash": 0.0, "sample_ranking_score": 0.133,
  "chain_ptm": {"A": 0.667}, "chain_pair_iptm": {}
}
```

## 良好输出的判断标准

- `summary.txt` 中显示的 `Successful Queries: N` 与输入查询数量一致。
- `avg_plddt > 70`（单序列）或 `> 80`（使用 MSA）。
- `ptm > 0.6`；对于复合物，`iptm > 0.5`。
- `has_clash: 0.0`。
- 对于小型蛋白质，每个样本的 `.cif` 文件大小约为 50–150 KB。

## 验证

```bash
grep -E 'Successful|Failed' out/summary.txt
find out -name '*_model.cif' | wc -l   # = queries x json_seeds x num-model-seeds x num-diffusion-samples
```

## 故障排除

| 错误 | 原因 | 解决方法 |
| --- | --- | --- |
| `_deepspeed_evo_attn requires that DeepSpeed be installed` | CUDA 上的默认评估内核是 DS4Sci | 安装 `deepspeed`（需要 nvcc 和 CUTLASS），或者在 `model_config.py` 的评估配置块中设置 `use_deepspeed_evo_attention: False` 和 `use_cueq_triangle_kernels: True`（cuEq 路径，无需构建） |
| `CUTLASS_PATH ... not set ... cutlass_library is not installed` | cuEq 路径仍然需要 Python `cutlass_library` 适配层 | 运行 `pip install nvidia-cutlass` |
| `libXrender.so.1: cannot open shared object file` | rdkit（经由 pdbeccdutils）需要 X11 渲染库 | 运行 `apt-get install libxrender1 libxext6 libsm6` |
| `ModuleNotFoundError: boto3`（或 `awscrt`） | 即使权重位于本地，`openfold3.core.data.io.s3` 也会被立即导入 | 运行 `pip install boto3 awscrt` |
| `ValidationError: queries / Field required` 或 `Input should be an object` | JSON 形状错误 | 顶层必须是 `{"queries": {"<name>": {...}}}`，其中使用字典而不是列表 |
| `ValidationError ... settings / Extra inputs are not permitted` | 尝试通过 `--runner-yaml` 覆盖模型配置 | `--runner-yaml` 只接受 `InferenceExperimentConfig`；内核和内存设置位于 `model_config.py` |
| `Failed to fetch chain ID mappings from RCSB for N entries` | 无法访问 `data.rcsb.org`（允许列表限制或离线） | 使用 `--use-templates false` 运行，或开放对 `data.rcsb.org` 的网络出口 |
| `CUDA out of memory` | 复合物过大或样本过多 | 减少 `--num-diffusion-samples`；`model_setting_presets.yml` 中的 `low_mem` 预设会进行更积极的卸载 |

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

权重——OpenFold3 · OpenFold Consortium（Apache-2.0）——[条款](https://github.com/aqlaboratory/openfold-3/blob/main/LICENSE)

向以下服务发送数据——ColabFold MSA server（`api.colabfold.com`）· Steinegger Lab——[信息](https://github.com/sokrypton/ColabFold/wiki)
