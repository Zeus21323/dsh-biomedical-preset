---
name: borzoi
description: "使用 Borzoi 根据 DNA 序列预测全基因组功能轨迹（RNA-seq、CAGE、DNase、ChIP）。适用于评估变异对表达或染色质可及性的调控效应、生成某个基因组位点的预测覆盖轨迹，或根据预测轨迹差值确定非编码变异的优先级。"
metadata: {"source": "upstream-biomedical-science@0.1.1", "origin": "upstream-plugin", "license": "Apache-2.0"}
---

# Borzoi — DNA → 功能轨迹预测

## 前置条件

| 要求 | 最低配置 | 推荐配置 |
| --- | --- | --- |
| Python | 3.10+ | 3.11 |
| CUDA | 12.1+ | 12.4+ |
| GPU 显存 | 16 GB | 24 GB+ |

## 运行方法

```python
from borzoi_pytorch import Borzoi

model = Borzoi.from_pretrained("johahi/borzoi-replicate-0").cuda().eval()
# 输入：(batch, 4, 524288) one-hot DNA → 输出：(batch, tracks, 6144) 个分箱
```

Borzoi 接收约 524 kb 的 one-hot 编码窗口，并针对 7,611 条人类轨迹输出分箱预测结果（独立的 2,608 轨迹小鼠预测头默认关闭；通过 `enable_mouse_head=True` 启用，并使用 `forward(..., is_human=False)` 选择）。进行变异评分时，以变异为中心分别运行参考和替代等位基因窗口，然后比较每条轨迹的输出。

## 输出格式

输出为 `(B, T, L)` 张量——`T` 条轨迹 × `L` 个 32 bp 分箱。轨迹元数据（实验类型、生物样本）位于 `borzoi_pytorch.pytorch_borzoi_model.TRACKS_DF`；使用 `AnnotatedBorzoi` 子类时也可通过 `model.tracks_df` 获取。基础 `Borzoi` 模型没有 `targets` 属性。

## 远程计算

需要至少 24 GB GPU 显存，并且需要预先缓存的 HF 权重，或者能够访问 `huggingface.co`。调用 `compute_details({provider, mode:'read'})`，查找包含 `borzoi-pytorch` 的运行环境，然后执行：

```python
c = host.compute.create(provider)
job = c.submit_job(
    intent="Borzoi track prediction for 1 locus — 1×GPU, ~2 min",
    inputs=["borzoi_run.py"],
    command="python3 borzoi_run.py",   # 环境选择因主机而异——请查看当前提供商的 compute_details
    outputs=["tracks.npz"],
    run_timeout_s=1800,
)
# 刚才只打印了 Job 的 repr（id、notes）——单元格到此结束；内核绝不会在作业上等待
```

随后调用 `wait_for_notification` brain-tool。收到 `compute_done` 通知后，根据其 payload 执行：

```python
save_artifacts(payload["output_files"])   # 位于 hpc/<job_id>/ 下的路径
```

如需获取完整记录（文件、`stdout_tail`、notes 等），请重新进入内核：`res = c.attach_job(job_id).result()`，然后调用 `c.close(intent=...)`。编排细节参见 `remote-compute-ssh`／`remote-compute-modal` skill。

如果提供商提供权重缓存挂载，请在 `borzoi_run.py` 中将 `HF_HOME` 指向该挂载位置；具体路径位于 `compute_details` 中。

## 故障排查

| 现象 | 原因 | 解决方法 |
| --- | --- | --- |
| `module has no __version__` | 软件包未公开该属性 | 使用 `importlib.metadata.version("borzoi-pytorch")`。 |
| 输入形状不匹配 | 窗口长度错误 | 填充或裁剪至 524288 bp；该长度固定，未作为模型属性公开。 |

---

**下一步：** 将轨迹差值与 `evo2` 似然差值结合，进行双轴变异优先级排序。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** Borzoi（PyTorch 移植版）· Calico Life Sciences（CC-BY-4.0）— [信息](https://huggingface.co/johahi/borzoi-replicate-0)
