---
name: fair-esm2
description: 使用 Meta AI 的 ESM-2（`fair-esm` 软件包）生成蛋白质嵌入。适用于提取残基级或序列级嵌入供下游机器学习使用、进行掩码语言模型似然或突变效应评分，以及根据序列预测接触图。
license: Apache-2.0
---

# fair-esm2 — ESM-2（Meta AI）

ESM-2 代码和权重均采用 MIT 许可证（Meta AI，[github.com/facebookresearch/esm](https://github.com/facebookresearch/esm)）。

> **软件包消歧。** `pip install fair-esm` 提供的是 `import esm` 和 `esm.pretrained.*`（ESM-1/2）。Biohub 的 [github.com/Biohub/esm](https://github.com/Biohub/esm) 分支（MIT）提供的是 `from esm.models.esmfold2 import ESMFold2InputBuilder`——请参见 `esmfold2` skill。两者共享 `esm` 命名空间，但属于不同的库。本技能介绍的是 **fair-esm**（Meta 软件包）。

## 前置条件

| 要求 | 最低配置 | 推荐配置 |
| --- | --- | --- |
| Python | 3.8+ | 3.11 |
| CUDA | 11.7+ | 12.x |
| GPU 显存 | 8 GB（8M）、16 GB（650M） | 24 GB+（650M／3B） |

## 运行方法

### 嵌入

```python
import torch, esm

model, alphabet = esm.pretrained.esm2_t33_650M_UR50D()
model = model.eval().cuda()
bc = alphabet.get_batch_converter()

_, _, toks = bc([("ubq", "MQIFVKTLTGKTITLEVEPSDTIENVK")])
with torch.no_grad():
    out = model(toks.cuda(), repr_layers=[33])
emb = out["representations"][33]      # (1, L+2, 1280)——包含 BOS/EOS
seq_emb = emb[0, 1:-1].mean(0)        # 序列级均值
```

### 掩码语言模型评分

```python
with torch.no_grad():
    out = model(toks.cuda(), repr_layers=[33])
logits = out["logits"][0, 1:-1]       # (L, |vocab|)
# WT 边际对数似然；进行突变评分时，遮盖相应位置，
# 然后比较 logit[mut] − logit[wt]。
```

### 接触预测

```python
with torch.no_grad():
    out = model(toks.cuda(), repr_layers=[33], return_contacts=True)
contacts = out["contacts"][0]         # (L, L)
```

## 模型

| 名称 | 层数 | 维度 | 参数量 | 用途 |
| --- | ---: | ---: | ---: | --- |
| `esm2_t6_8M_UR50D` | 6 | 320 | 8 M | 快速冒烟测试／小型嵌入 |
| `esm2_t33_650M_UR50D` | 33 | 1280 | 650 M | 默认嵌入模型 |
| `esm2_t36_3B_UR50D` | 36 | 2560 | 3 B | 最佳嵌入，需 24 GB+ |

## 输出格式

`out["representations"][layer]` 的形状为 `(B, L+2, D)`；使用 `[:, 1:-1, :]` 去除 BOS/EOS。启用 `return_contacts=True` 时，`out["contacts"]` 的形状为 `(B, L, L)`。

## 远程计算

650M 模型需要至少 16 GB GPU 显存，并且需要预先缓存的 `.pt` 检查点，或者能够访问 `dl.fbaipublicfiles.com`。调用 `compute_details({provider, mode:'read'})`，查找包含 `fair-esm` 和 torch-hub 权重缓存的运行环境，然后执行：

```python
c = host.compute.create(provider)
job = c.submit_job(
    intent="ESM-2 650M embeddings for 200 sequences — 1×GPU, ~2 min",
    inputs=[
        "seqs.fasta",
        "embed_esm2.py",
    ],
    # 环境激活因主机而异——请将其写在 command 字符串中
    #（例如 "conda run -n <env> python3 embed_esm2.py"；参见 compute_details）
    command="python3 embed_esm2.py",
    outputs=["embeddings.pt"],
    run_timeout_s=1800,
)
# 刚才只打印了 Job 的 repr（id、notes）——单元格到此结束；内核绝不会在作业上等待
```

随后调用 `wait_for_notification` brain-tool。收到 `compute_done` 通知后，根据其 payload 执行：

```python
save_artifacts(payload["output_files"])   # 位于 hpc/<job_id>/ 下的路径
```

如需获取完整记录（文件、`stdout_tail`、notes 等），请重新进入内核：`res = c.attach_job(job_id).result()`，然后调用 `c.close(intent=...)`。编排细节参见 `remote-compute-ssh`／`remote-compute-modal` skill。

在 `embed_esm2.py` 中，将 `TORCH_HOME` 设置为提供商的 torch-hub 缓存挂载位置；具体路径位于 `compute_details` 中。这样 `esm.pretrained.*` 就能在本地解析权重。

## 故障排查

| 现象 | 原因 | 解决方法 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'esm.models'` | 需要的是 Biohub 的 `esm` 分支，而不是 `fair-esm` | 参见 `esmfold2` skill；本技能使用 `esm.pretrained.*`。 |
| 首次调用缓慢 | 正在通过 torch.hub 下载权重 | 将 `TORCH_HOME` 设置为缓存位置。 |

---

**下一步：** 将嵌入输入分类器。对于结构预测，请使用 `esmfold2`。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** ESM-2 · Meta AI（MIT）— [条款](https://github.com/facebookresearch/esm/blob/main/LICENSE)
