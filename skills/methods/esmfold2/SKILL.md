---
name: esmfold2
description: 使用 Biohub ESMFold2／ESMFold2-Fast 进行全原子共折叠，支持单序列和 MSA 模式以及蛋白质、DNA、RNA、配体（CCD／SMILES）和修饰残基；FoldBench 抗体–抗原 DockQ 通过率为 50–55%，PPI 为 70–77%。也覆盖同一版本的 ESMC-{300M,600M,6B} 蛋白质语言模型，包括掩码语言模型 logits、隐藏状态、突变评分、接触预测和 SAE 可解释性预测头。适用于预测单序列输入的复合物结构、使用 ESMFold2-Fast 验证设计结合蛋白、运行 MSA 输入、获取 ESMC 嵌入或逐残基突变分数，以及选择符合论文吞吐设置的内核后端和采样步数。
license: Apache-2.0
---

# ESMFold2（Biohub）

Biohub ESM 2026 版本中的全原子扩散共折叠模型。ESMFold2 包含 48 个成对表示层并支持 MSA；ESMFold2-Fast 包含 24 层，仅支持单序列，速度约快 1.7 倍。

**许可证：** MIT（代码：[github.com/Biohub/esm](https://github.com/Biohub/esm)；权重：HF `biohub/*`）。

**论文：** “Language Modeling Materializes a World Model of Protein Biology”（2026）。

## 安装

需要 CUDA 12.x GPU（H100／A100 级别），并且仅支持 Python **3.12**。请使用全新虚拟环境；安装过程需要访问 HF Hub、GitHub 和 PyPI：

```bash
pip install --no-cache-dir uv
uv venv --python 3.12 /work/venv && source /work/venv/bin/activate
uv pip install \
  "torch>=2.5,<2.8" einops "biotite>=1.0" rdkit msgpack-numpy biopython \
  scikit-learn brotli attrs pandas cloudpathlib httpx tenacity zstd pydssp \
  pygtrie accelerate huggingface_hub safetensors "numpy<3" networkx \
  sentencepiece tokenizers regex packaging filelock pyyaml typing_extensions \
  "transformers @ git+https://github.com/Biohub/transformers.git@3a8956fb4d4ea16b0ec8e71deef2c2909b6a5cbf"
uv pip install --no-deps "esm @ git+https://github.com/Biohub/esm.git@f652b471"
# 可选——只影响 ESMC attention；trunk 加速来自 set_kernel_backend("fused")
uv pip install ninja packaging wheel setuptools
MAX_JOBS=8 uv pip install --no-deps --no-build-isolation "flash-attn<3"
# 不要安装 transformer-engine——导入时的 RuntimeError（而不是 ImportError）
# 会绕过 ESMC 的保护逻辑，并导致 ESMFold2Model 导入失败。
```

`remote-compute-modal` skill 中捆绑的 `esmfold2_gpu` Modal 环境是规范的、版本固定的安装方案。

**注意事项：**

- **默认内核后端为 `None`**（参考 PyTorch 路径，约比论文设置慢 12 倍）。在 `from_pretrained()` 后调用 `model.set_kernel_backend('fused')`。参见下文。
- 使 PyTorch CUDA 构建版本与驱动程序匹配；`<2.8` 的版本限制针对 CUDA 12.2。
- 权重通过 Xet bridge 以约 300 MB/s 下载：ESMFold2 为 1.36 GB，ESMFold2-Fast 为 0.76 GB。设置 `HF_HOME=/work/hf_cache`。

## 用法——本地模型

```python
from esm.models.esmfold2 import (
    ESMFold2InputBuilder, StructurePredictionInput,
    ProteinInput, DNAInput, RNAInput, LigandInput, Modification,
)
from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()
# 或 "biohub/ESMFold2-Fast"（24 层、不支持 MSA、约快 1.7 倍）
# 或 "biohub/ESMFold2-Experimental{,-Fast}{,-Cutoff2025}"（4 个设计 critic 模型）

spi = StructurePredictionInput(sequences=[
    ProteinInput(id="A", sequence=target_seq),
    ProteinInput(id="B", sequence=binder_seq),
    # DNAInput(id="C", sequence="ACGT", modifications=[Modification(position=5, ccd="C36")]),
    # RNAInput(id="D", sequence="ACGU"),
    # LigandInput(id="L", ccd=["SAH"]),  # 或 smiles="..."
])
# 同源二聚体：ProteinInput(id=["A","B"], sequence=seq)

results = ESMFold2InputBuilder().fold(
    model, spi,
    num_loops=10,             # 论文 FoldBench 评估：10；20-loop 变体：20
    num_sampling_steps=68,    # 论文评估：68（截断 EDM）
    num_diffusion_samples=5,  # 论文评估：每个 seed 5 个
    seed=0,
)
# fold() 返回 list[Prediction]，每个扩散样本对应一个 Prediction。每个对象包含
# .plddt [L]、.ptm、.iptm、.pae [L,L]、.pair_chains_iptm、.complex.to_mmcif()。
# 复合物按 ipTM 排名，单体按平均 pLDDT 排名：
best = max(results, key=lambda r: float(r.iptm if r.iptm is not None
                                        else r.plddt.mean()))
open("pred.cif", "w").write(best.complex.to_mmcif())
```

**忠实于论文的 FoldBench 设置：** 10 次循环、68 个采样步骤、25 个 seed × 5 个扩散样本；复合物按 ipTM 排名，单体按 pLDDT 排名；MSA 模式还使用 `msa_depth=1024`、10% 列遮盖和 0.3 的 ESMC dropout。

## HF `biohub/` 上的模型变体

| 仓库 | 大小 | 成对表示层 | MSA | 用途 |
| --- | --- | ---: | --- | --- |
| `ESMFold2` | 0.94 GB + `ccd.pkl` 0.42 GB | 48 | 是 | 完整评估 |
| `ESMFold2-Fast` | 0.76 GB | 24 | 否 | 快速单序列 |
| `ESMFold2-Experimental{,-Fast}` | 0.90／0.72 GB | 48／24 | — | 设计搜索（算法 11） |
| `ESMFold2-Experimental{,-Fast}-Cutoff2025` | 0.90／0.72 GB | — | — | 设计搜索 + critic |
| `ESMFold2-Experimental-Fast-base{300M,600M,6B}-step{250k..1500k}` | — | — | — | 15 个 critic 集成 |

## 吞吐量：必须使用 `set_kernel_backend("fused")`

**默认使用慢速路径。** `ESMFold2Model.from_pretrained(...)` 加载后 `_kernel_backend=None`（参考 PyTorch），`chunk_size=64`。必须调用：

```python
model = ESMFold2Model.from_pretrained("biohub/ESMFold2").cuda().eval()
model.set_kernel_backend("fused")   # 内置 Triton TriMul/LN+SwiGLU/pair-bias 内核
model.set_chunk_size(None)           # L<=1024 时最优且不会 OOM；更长序列使用 256
```

`"fused"` 相比参考后端可使 trunk 加速约 1.5–6 倍，并且序列越长，加速越明显；短序列的端到端 `fold()` 受扩散阶段限制，因此 fused 大约在 L≈300–400 时才开始产生净收益。fused 与参考路径的输出在数值上一致，pLDDT 差异处于噪声范围内。`"fused"` 使用 PyTorch GPU wheel 自带的 Triton，仅适用于推理——在反向传播时会自动禁用。L 超过约 1400 且 `chunk_size=128` 时会触发非法内存访问；此时回退到 `set_kernel_backend(None)` + `set_chunk_size(64)`。该组合已验证至 L=1024。

**不要使用** `set_kernel_backend("cuequivariance")`：`cuequivariance-torch==0.10.0` wheel 缺少编译后的操作，并会**静默回退**到参考路径。`apply_torch_compile()` 是另一种选择，但不能与 fused 叠加；应先调用 `set_kernel_backend(None)`。

## ESMFold2-Experimental*——设计钩子

Experimental 变体公开 `res_type_soft`，可用于梯度引导设计——需要时读取 [references/design-hook.md](references/design-hook.md)。不要对 Experimental 变体使用 fused 后端，否则会发生 fp32／bf16 dtype 崩溃；参考路径才是正确选择。

## 注意：cuSOLVER SVD 污染与 structseq 构造函数

`modeling_esmfold2_common.py` 中的 Kabsch 对齐会对批量 3×3 矩阵调用 `torch.linalg.svd(H32, driver="gesvd")`。NaN／Inf 输入（退化扩散样本）会破坏 cuSOLVER 工作区，导致**此后的所有 CUDA 调用都以“illegal memory access”失败**。可通过 monkeypatch 将小型批量 SVD 转移到 CPU：

```python
_orig_svd = torch.linalg.svd
def _safe_svd(A, full_matrices=True, driver=None):
    if A.is_cuda and A.shape[-1] <= 4 and A.shape[-2] <= 4:
        Acpu = A.detach().float().cpu()
        if not torch.isfinite(Acpu).all():
            Acpu = torch.nan_to_num(Acpu, nan=0.0, posinf=1e6, neginf=-1e6)
        out = _orig_svd(Acpu, full_matrices=full_matrices)
        # torch.return_types.linalg_svd 是 C structseq，其构造函数接收一个元组。
        return type(out)(tuple(t.to(A.device, A.dtype) for t in out))
    return _orig_svd(A, full_matrices=full_matrices, driver=driver)
torch.linalg.svd = _safe_svd
```

注意应使用 `type(out)(tuple(...))`，而不是 `type(out)(*(...))`——`torch.return_types.*` 是 C structseq，其构造函数只接收一个元组参数。

## MSA 模式

ESMFold2 通过 `ProteinInput(id, sequence, msa=MSA)` 支持逐链 MSA 输入。`MSA` 对象位于 `esm.utils.msa.msa.MSA`：

```python
from esm.utils.msa.msa import MSA
# ProteinInput、StructurePredictionInput 已在上面导入

msa_A = MSA.from_a3m("/path/chain_A.a3m", max_sequences=2048)
msa_B = MSA.from_a3m("/path/chain_B.a3m", max_sequences=2048)
inp = StructurePredictionInput(sequences=[
    ProteinInput(id="A", sequence=seq_A, msa=msa_A),
    ProteinInput(id="B", sequence=seq_B, msa=msa_B),
])
```

**注意事项：**

- `MSA.from_a3m(remove_insertions=True)` 会在移除插入后断言所有行长度相等。ColabFold A3M 文件经常带有尾随**空字节**，并且部分行与查询序列相差一个位置——使用 `tr -d '\000'`，并强制第 0 行与查询序列完全一致；也可以清洗出与查询等长的行后使用 `MSA.from_sequences`。
- **ESMFold2-Fast 不支持 MSA**，只能使用单序列。
- 根据论文评估，MSA 模式可提高抗体–抗原界面的通过率。

## 与论文一致的推理配置

论文 FoldBench 协议（A.2.11 节）：

| 参数 | 论文默认值 | 论文“20lp” | 说明 |
| --- | ---: | ---: | --- |
| `num_loops`（folding-trunk 循环） | **10** | 20 | 抗体–抗原提高约 2 个百分点 |
| `num_sampling_steps`（扩散） | **68** | 68 | 针对 EDM 调优；**不要使用 200** |
| seed × 扩散样本 | 25 × 5 | 25 × 5 | 图 S6／S7 oracle = 125 个样本中的最佳结果 |

## 训练数据截止时间

ESMFold2 和 ESMFold2-Fast 都使用 **2021 年 9 月**的 PDB 训练数据截止时间，来源为 HF `biohub/ESMFold2` README。

## ESMC 语言模型

ESMC 是 Biohub 的 ESM-2 后继模型，共有三种规模：300M（30 层）、600M（36 层）和 6B（80 层，d=2560）。HF 加载路径为 `AutoModelForMaskedLM.from_pretrained("biohub/ESMC-6B")`。

**掩码标记是 `<mask>`**（ID 32），应使用 `tok.mask_token`。原生 SDK 的 `_` 约定不适用于 HF tokenizer：`_` 不在词表中，会被编码为 `<unk>`，从而静默破坏突变评分。

需要 ESMC 完整 API、突变评分、SAE 特征或接触预测时，读取 [references/esmc.md](references/esmc.md)。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** ESMFold2／ESMC · Biohub（MIT）— [条款](https://github.com/Biohub/esm/blob/main/LICENSE.md)
