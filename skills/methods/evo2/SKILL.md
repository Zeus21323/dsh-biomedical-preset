---
name: evo2
description: 使用长上下文基因组基础模型 Evo 2 对 DNA 序列进行评分、嵌入和生成。适用于计算逐核苷酸或逐序列似然以评估变异效应、嵌入基因组窗口供下游分类使用、根据前缀生成 DNA，以及跨物种评估调控区或编码区。
license: Apache-2.0
---

# Evo 2 — DNA 语言模型

## 前置条件

| 要求 | 最低配置 | 推荐配置 |
| --- | --- | --- |
| Python | 3.11 | 3.12（<3.13） |
| CUDA | 12.1+ | 12.4+ |
| GPU 显存 | 24 GB（7B bf16） | 80 GB（40B） |
| RAM | 32 GB | 128 GB |

## 运行方法

### 安装

```bash
pip install evo2
# 首次加载模型时从 Hugging Face 下载权重。
```

### 加载与评分

```python
from evo2 import Evo2

model = Evo2("evo2_7b")        # 或 "evo2_40b"——参见模型表
seqs = ["ATCG" * 50, "GGGCTTAA" * 25]
ll = model.score_sequences(seqs)   # → list[float]，逐 token 平均对数似然
print(ll)
```

### 生成

```python
out = model.generate(
    prompt_seqs=["ATGAAAGCT"],
    n_tokens=256,
    temperature=0.7,
)
print(out.sequences[0])
```

## 模型

| 名称 | 参数量 | 上下文 | 显存（bf16） | 说明 |
| --- | ---: | --- | ---: | --- |
| `evo2_7b` | 7 B | 1 M nt | 约 22 GB | 默认模型；可在单张 24 GB+ GPU 上运行 |
| `evo2_40b` | 40 B | 1 M nt | 约 78 GB | H100 80 GB 或多 GPU |
| `evo2_1b_base` | 1 B | 8 K nt | 约 6 GB | FP8 路径需要 sm_89+（H100） |

## 输出格式

`score_sequences` 返回平均对数似然组成的 `list[float]`（或 `np.ndarray`），每条输入序列对应一个值。数值越负，表示模型认为该序列出现的可能性越低。评估变异效应时，在固定窗口上计算 `Δll = ll_alt - ll_ref`。

`generate` 返回 `GenerationOutput`，其中包含 `.sequences`（`list[str]`）、`.logits`（`list[Tensor]`）和 `.logprobs_mean`（`list[float]`）；这些字段始终存在，无需额外标志。

## 决策树

```text
需要 DNA 模型？
│
├─ 逐碱基／逐序列似然、序列生成 → Evo 2 ✓
├─ 预测实验轨迹（表达、可及性） → borzoi
└─ 处理蛋白质而不是 DNA → fair-esm2／esmfold2
```

## 远程计算

7B／40B 推理受 GPU 限制，分别需要至少 24 GB／80 GB 显存。调用 `compute_details({provider, mode:'read'})`，查找包含 `evo2`、`flash-attn` 和预缓存 HF 权重挂载的运行环境，然后提交：

```python
c = host.compute.create(provider)
job = c.submit_job(
    intent="Evo2-7B score 200bp variant window — 1×GPU, ~2 min",
    inputs=["score_evo2.py"],
    command="python3 score_evo2.py",   # 环境选择因主机而异——请查看当前提供商的 compute_details
    outputs=["scores.json"],
    run_timeout_s=1800,
)
# 刚才只打印了 Job 的 repr（id、notes）——单元格到此结束；内核绝不会在作业上等待
```

随后调用 `wait_for_notification` brain-tool。收到 `compute_done` 通知后，根据其 payload 执行：

```python
save_artifacts(payload["output_files"])   # 位于 hpc/<job_id>/ 下的路径
```

如需获取完整记录（文件、`stdout_tail`、notes 等），请重新进入内核：`res = c.attach_job(job_id).result()`，然后调用 `c.close(intent=...)`。编排细节参见 `remote-compute-ssh`／`remote-compute-modal` skill。

在 `score_evo2.py` 中，将 `HF_HOME` 指向提供商的权重缓存挂载位置；具体路径位于 `compute_details` 中。同时设置 `HF_HUB_OFFLINE=1`，避免加载器尝试向只读挂载中的 `refs/` 写入内容。权重占用空间：7B 约 15 GB，40B 约 80 GB。

## 典型性能

| 任务 | H100 上的 7B | 说明 |
| --- | --- | --- |
| 模型加载（已缓存） | 约 5–7 分钟 | 首次调用会加载权重 |
| `score_sequences`，200×200 bp | 约 10–20 秒 | 模型加载完成后 |
| `generate`，1×512 nt | 约 15 秒 |  |

## 故障排查

| 现象 | 原因 | 解决方法 |
| --- | --- | --- |
| `Transformer Engine not installed` | 没有 FP8，回退到 bf16 | 在非 H100 上仅为提示信息，可以忽略。 |
| 加载时 OOM | 在显存小于 80 GB 的 GPU 上加载 40B | 使用 `evo2_7b`，或通过 `device_map` 分片。 |
| HF 尝试写入 `refs/main` | `HF_HOME` 指向只读挂载 | 设置 `HF_HUB_OFFLINE=1`。 |
| `score_sequences` 中出现 dtype 不匹配 | 传入了张量而不是字符串 | 传入 `list[str]`；该 API 会自行分词。 |

---

**下一步：** 与 `borzoi` 配合，预测同一批变异的轨迹级效应。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** Evo 2 · Arc Institute（Apache-2.0）— [条款](https://github.com/ArcInstitute/evo2/blob/main/LICENSE)
