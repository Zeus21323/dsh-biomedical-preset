---
name: scgpt
description: 使用单细胞生物学基础模型 scGPT 对单细胞表达数据进行嵌入和注释。适用于：从 AnnData 生成细胞嵌入以进行聚类或整合；执行零样本或微调后的细胞类型注释；为扰动或基因调控网络任务生成基因级表示。对于 scVI 等概率单细胞模型，请使用 scvi-tools 库。
license: Apache-2.0
---

# scGPT——单细胞基础模型

## 先决条件

| 要求 | 最低配置 | 推荐配置 |
| --- | --- | --- |
| Python | 3.10+ | 3.11 |
| CUDA | 12.1+ | 12.4+ |
| GPU 显存 | 16 GB | 24 GB+ |

## 运行方法

### 加载词表和检查点

scGPT 检查点是原始目录（`args.json`、`best_model.pt`、`vocab.json`），并非 Hugging Face Hub 仓库。应指向该目录，而不是 Hugging Face 仓库 ID。

```python
from scgpt.tokenizer.gene_tokenizer import GeneVocab
gv = GeneVocab.from_file("/path/to/scgpt-human/vocab.json")
print(len(gv))   # 已发布的人类检查点为 60697
```

### 嵌入 AnnData

```python
import anndata as ad
from scgpt.tasks import embed_data

adata = ad.read_h5ad("dataset.h5ad")        # var 必须包含基因名称列
emb = embed_data(
    adata,
    model_dir="/path/to/scgpt-human",
    gene_col="feature_name",
    use_fast_transformer=False,             # 参见“易错点”
)
# emb 是一个 AnnData，包含 .obsm["X_scGPT"]
```

## 输出格式

`embed_data` 返回一个 `AnnData`，其中 `.obsm["X_scGPT"]` 是逐细胞嵌入，形状为 `n_cells × emb_dim`，默认嵌入维度为 512。下游可将其传入 `scanpy.pp.neighbors` / `scanpy.tl.umap`。

## 远程计算

需要不少于 24 GB GPU 显存，以及已发布的人类检查点（约 200 MB：`args.json`、`best_model.pt`、`vocab.json`）。读取 `compute_details({provider, mode:'read'})`，寻找安装了 `scgpt` 且预缓存了检查点目录的环境，然后提交任务：

```python
c = host.compute.create(provider)
job = c.submit_job(
    intent="scGPT embed 50k cells — 1×GPU, ~5 min",
    inputs=[
        "dataset.h5ad",
        "embed.py",
    ],
    # 环境激活方式由宿主决定——将它写在命令字符串中
    #（例如 "conda run -n <env> python3 embed.py"；参见对应提供商的 compute_details）
    command="python3 embed.py",
    outputs=["embedded.h5ad"],
    run_timeout_s=1800,
)
# Job 的 repr 已自行打印（id、notes）——单元格在此结束；内核绝不等待任务
```

然后调用 `wait_for_notification` brain 工具。当收到 `compute_done` 通知时，处理其载荷：

```python
save_artifacts(payload["output_files"])   # hpc/<job_id>/ 下的路径
```

如需完整记录（文件、`stdout_tail`、备注等），重新进入内核，并单独绑定计算句柄——`.close()` 位于句柄上，而不在任务对象上：

```python
c = host.compute.create(provider)
res = c.attach_job(job_id).result()   # 读取持久化结果，绝不等待
c.close(intent="scGPT embedding done")
```

编排细节参见 `remote-compute-ssh` / `remote-compute-modal` 技能。

在 `embed.py` 中，将 `model_dir=` 设为 `compute_details` 返回的检查点路径。如果该环境中没有 `flash-attn`，设置 `use_fast_transformer=False`。

## 易错点

- `use_fast_transformer` 的默认值是 `True`，但它会解析到并非在每个环境中都能成功导入的 FlashAttention 路径。除非已经确认 `flash_attn` 能够正常加载，否则应传入 `use_fast_transformer=False`。
- 该软件包过去依赖 `torchtext.vocab.Vocab`；在没有 torchtext 的环境中，会由纯 Python 适配层提供 `Vocab`——对于 `GeneVocab` 而言功能完全相同；但如果遇到 `AttributeError: 'Vocab' object has no attribute …`，说明使用的是过时的适配层。
- 基因名称必须与词表匹配；不匹配的基因会被丢弃。应将 `gene_col` 设置为 `adata.var` 中保存基因符号的列。

## 故障排除

| 症状 | 解决方法 |
| --- | --- |
| 导入时出现 `flash_attn is not installed` 警告 | 无害；传入 `use_fast_transformer=False` |
| `'Vocab' object has no attribute 'vocab'` | 环境中使用了旧版 torchtext 适配层——更新环境 |
| 几乎所有基因都被丢弃 | `gene_col` 错误；检查 `adata.var.columns` |
| `"scgpt not in manifest"` / 环境检测未识别 scGPT | 预构建环境清单以 pip 的规范大小写将发行包列为 `scGPT`（以及 `flash_attn`）——查找前应规范化清单键：`name.lower().replace('-', '_')` |

---

**下一步：** 使用 Scanpy 库对嵌入进行聚类或注释（`sc.pp.neighbors` → `sc.tl.leiden` / `sc.tl.umap`），或者在同一数据上与 scvi-tools 潜在空间进行比较。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

权重——scGPT · Wang Lab（University of Toronto）——[信息](https://github.com/bowang-lab/scGPT)
