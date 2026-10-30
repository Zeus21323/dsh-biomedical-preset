---
name: scvi-tools
description: 使用 scvi-tools 对单细胞 RNA 测序数据进行概率建模——使用 scVI 获得批次校正的潜在空间，使用 scANVI 进行半监督标签转移，并执行贝叶斯差异表达分析。适用于整合多个 scRNA-seq 批次、生成细胞嵌入以进行聚类、将参考数据的注释转移到查询数据，或按细胞簇评估差异表达基因。空间解卷积或映射应改用 cell2location、DestVI 或 Tangram。
license: Apache-2.0
---

# scvi-tools——scVI / scANVI

scvi-tools（Gayoso 等，2022，[github.com/scverse/scvi-tools](https://github.com/scverse/scvi-tools)，BSD-3-Clause）封装了一系列用于单细胞组学的深度生成模型。其 scRNA-seq 核心是 scVI（无监督、批次校正的潜在嵌入）和 scANVI（scVI 加分类器头，用于半监督细胞类型标签转移）。两者都要求输入原始整数 UMI 计数，并输出低维 `X_scVI` / `X_scANVI`，可直接接入 Scanpy 的 neighbors → leiden → umap 流程。

## 运行方法

### scVI——批次校正的潜在空间

```python
import scanpy as sc
import scvi

adata = sc.read_h5ad("dataset.h5ad")
adata.layers["counts"] = adata.X.copy()          # 在任何 normalize/log1p 之前保存原始计数
sc.pp.normalize_total(adata); sc.pp.log1p(adata) # 可选，仅用于 HVG / 绘图
sc.pp.highly_variable_genes(adata, n_top_genes=2000, batch_key="batch", subset=True)

scvi.model.SCVI.setup_anndata(adata, layer="counts", batch_key="batch")
model = scvi.model.SCVI(adata, n_latent=30)
model.train(max_epochs=200, early_stopping=True, accelerator="gpu", devices=1)

adata.obsm["X_scVI"] = model.get_latent_representation()
adata.layers["scvi_normalized"] = model.get_normalized_expression(library_size=1e4)
```

### scANVI——从部分已注释的参考数据转移标签

```python
lvae = scvi.model.SCANVI.from_scvi_model(
    model, labels_key="cell_type", unlabeled_category="Unknown",
)
lvae.train(max_epochs=20, n_samples_per_label=100, accelerator="gpu", devices=1)

adata.obsm["X_scANVI"] = lvae.get_latent_representation()
adata.obs["pred_cell_type"] = lvae.predict()
```

`accelerator="gpu", devices=1` 是 PyTorch Lightning 的写法；旧版 `use_gpu=` 关键字参数已在 scvi-tools 1.x 中移除，现在会引发 `TypeError`。

硬标签会隐藏不确定性：`lvae.predict(soft=True)` 返回逐细胞类别概率，形式为每种细胞类型一列的 DataFrame。将 `.max(axis=1)` 与标签一同保存，并把低于阈值（例如 0.8）的细胞视为低置信度，而不是接受每一个预测结果。

## 查询到参考的映射（scArches）

若要根据已经训练好的参考图谱注释新数据集，不应从头重新训练——应把查询数据映射到冻结的参考模型上（scArches 风格的迁移学习；参见 [scvi-tools 参考映射指南](https://docs.scvi-tools.org/)）：

```python
adata_query.layers["counts"] = adata_query.X.copy()  # 与参考数据一样使用原始计数
adata_query.obs["cell_type"] = "Unknown"             # 查询数据初始时无标签
scvi.model.SCANVI.prepare_query_anndata(adata_query, lvae)  # 对齐基因；缺失基因 → 补零
query = scvi.model.SCANVI.load_query_data(adata_query, lvae)
query.train(max_epochs=100, plan_kwargs={"weight_decay": 0.0})

adata_query.obsm["X_scANVI"] = query.get_latent_representation()
adata_query.obs["pred_cell_type"] = query.predict()
```

查询数据的 `.obs` 中还必须包含参考数据使用的批次列。`weight_decay: 0.0` 可避免微调侵蚀冻结参考模型的潜在空间。对于无标签参考数据（只需要嵌入，不转移标签），`scvi.model.SCVI` 也提供相同的类方法。

为了支持后续 scArches 映射，在构建参考模型时，应在 `scvi.model.SCVI(...)` 构造函数上设置 `encode_covariates=True`（默认值为 `False`；scANVI 会通过 `from_scvi_model` 继承该设置）——只有启用它，编码器才会以批次或协变量为条件；不以这些变量为条件的编码器会忽略查询数据的批次，因此模型手术无法据此调整潜在空间。缺少该设置时，`load_query_data` 仍然能够运行，但映射质量会下降；[scvi-tools 参考映射教程](https://docs.scvi-tools.org/)展示了完整的推荐 `arches_params`。

## 差异表达

```python
de = model.differential_expression(
    groupby="leiden", group1="3",   # group2=None → 与所有其他细胞比较
    mode="change", delta=0.25,
)
top = de.sort_values("proba_de", ascending=False).head(50)
```

对于 one-vs-rest 比较，应省略 `group2`——`"rest"` 是 Scanpy 的 `rank_genes_groups` 约定，并不是 scvi-tools 的约定；在这里，`group2` 是一个字面类别名称，`"rest"` 将匹配不到任何细胞。

scvi-tools ≥1.4 的默认模式是 `mode="vanilla"`，其结果列恰好为：

```python
['proba_m1', 'proba_m2', 'bayes_factor', 'scale1', 'scale2', 'raw_mean1',
 'raw_mean2', 'non_zeros_proportion1', 'non_zeros_proportion2',
 'raw_normalized_mean1', 'raw_normalized_mean2', 'comparison', 'group1',
 'group2']
```

其中没有 `lfc_*`、`proba_de` 或 `is_de_fdr_*`。传入 `mode="change"` 才会得到 `lfc_mean` / `lfc_median` / `proba_de` / `is_de_fdr_0.05`。应按 `proba_de` 排序；如果有意保留 `vanilla` 模式，则按 `bayes_factor` 排序。

另外还有两个参数（参见 [差异表达用户指南](https://docs.scvi-tools.org/)）：`fdr_target` 设置计算 `is_de_fdr_*` 判定列时使用的后验期望 FDR 水平，默认值为 0.05；`delta=None` 则会用根据数据估计的阈值替代固定的对数倍数变化阈值。

## 输出格式

| 键 | 含义 |
| --- | --- |
| `adata.obsm["X_scVI"]` | `n_cells × n_latent` 的批次校正嵌入 |
| `adata.obsm["X_scANVI"]` | 标签感知嵌入，能够更好地区分已知类别 |
| `adata.obs["pred_cell_type"]` | scANVI 为每个细胞预测的标签 |
| `adata.layers["scvi_normalized"]` | 解码后的表达量，已按文库大小归一化 |
| 差异表达 DataFrame | 每个基因的 `lfc_*` / `proba_de`，要求使用 `mode="change"` |

## 远程计算

对于超过 5 万个细胞的数据，推荐使用 A100 级 GPU。预构建的 `singlecell_gpu` Modal 环境包含 scvi-tools 1.4.2、Scanpy 1.11.5 和 AnnData 0.11.4——读取 `compute_details({provider: 'byoc:modal', mode: 'read'})` 获取当前镜像引用，然后提交任务：

```python
c = host.compute.create('modal', provider_params={
    'image':  '<image ref from compute_details>',   # 例如 im-...
    'gpu':    'A100',
    'cpu':    8,
    'memory': 32768,
    'timeout': 3600,          # 容器运行时限——可选；省略时使用 Settings 默认值
})
job = c.submit_job(
    intent="scVI+scANVI on 80k cells — 1×A100, ~15 min",
    inputs=[
        "dataset.h5ad",
        "pipeline.py",
    ],
    command="python pipeline.py",
    outputs=["out/**"],
    run_timeout_s=2400,
)
# Job 的 repr 已自行打印（id、notes、deadline）——单元格在此结束；内核绝不等待任务
```

`h5ad_safe_obs` 只会自动加载到本地分析内核中——在 Modal 上运行的 `pipeline.py` 里，应把该辅助函数粘贴到脚本顶部，或在调用 `.write_h5ad()` 前内联 `pd.Index(np.asarray(..., dtype=object))` 转换。

然后调用 `wait_for_notification` brain 工具。收到 `compute_done` 后，执行 `save_artifacts(payload["output_files"])`。如需完整记录，重新进入内核，并单独绑定计算句柄，而不是任务对象——`.close()` 位于句柄上，不在任务上：

```python
c = host.compute.create('modal')
res = c.attach_job(job_id).result()   # 读取而非等待：文件、stdout_tail、备注等
c.close(intent="scVI run done — stop the sandbox")
```

编排细节参见 `remote-compute-modal` 技能。

## 易错点

| 易错点 | 结果及解决方法 |
| --- | --- |
| `differential_expression()` 在 scvi-tools ≥1.4 中默认为 `mode="vanilla"` | 排序时出现 `KeyError: 'lfc_mean'` / `'proba_de'`——传入 `mode="change"` 以获得 `lfc_*` / `proba_de` / `is_de_fdr_*`；在 `vanilla` 模式下按 `bayes_factor` 排序。 |
| `adata.obs` 的索引或列为 `string[pyarrow]`（`ArrowStringArray`） | `.write_h5ad()` 会因 `IORegistryError: No method registered for writing <class 'pandas.arrays.ArrowStringArray'>`（anndata #2377）失败。写入前执行 `adata.obs = h5ad_safe_obs(adata.obs)`；该内核辅助函数只存在于本地内核，远程 `pipeline.py` 中应内联转换。单独使用 `.astype(str)` 并不够——对于 pyarrow 支持的 Index/Series，它仍会返回 Arrow 支持的数组；必须经过 `np.asarray(..., dtype=object)`。`anndata.settings.allow_write_nullable_strings = True` 不覆盖 Arrow 支持的字符串。 |
| `use_gpu=` 关键字参数 | 已在 1.x 中移除，会出现 `TypeError: train() got an unexpected keyword argument 'use_gpu'`。改用 `accelerator="gpu", devices=1`。 |
| 把对数归一化数据传给 `setup_anndata` | 会静默产生无意义结果——scVI 的负二项似然需要原始整数计数。必须在 normalize/log1p 之前把计数保存到 `adata.layers["counts"]`，并传入 `layer="counts"`。 |

## 故障排除

| 症状 | 解决方法 |
| --- | --- |
| 差异表达结果出现 `KeyError: 'lfc_mean'`（或 `'proba_de'`、`'is_de_fdr_0.05'`） | 向 `differential_expression()` 添加 `mode="change"`；默认 `vanilla` 模式不包含 LFC 列。 |
| `.write_h5ad()` 出现 `IORegistryError: No method registered for writing <class 'pandas.arrays.ArrowStringArray'>` | 写入前执行 `adata.obs = h5ad_safe_obs(adata.obs)`，必要时也对 `adata.var` 执行。`allow_write_nullable_strings` 标志对此无效。 |
| `TypeError: ... unexpected keyword argument 'use_gpu'` | 替换为 `accelerator="gpu", devices=1`。 |
| `ValueError: ... non-negative integers` / NB 损失爆炸 | `layer="counts"` 指向对数或浮点数据——恢复原始计数。 |
| `MisconfigurationException: No supported gpu backend found` | CUDA 不可见——移除 `accelerator` / `devices` 以回退到 CPU，或通过“远程计算”派发任务。 |
| 写入摘要或打印时出现 `UnicodeEncodeError: 'ascii' codec can't encode character ...` | 容器没有设置 `LANG`，因此 Python 默认使用 ASCII。以 `encoding="utf-8"` 打开文件，和/或在脚本开头运行 `sys.stdout.reconfigure(encoding="utf-8")`。预构建 `singlecell_gpu` 环境设置了 `PYTHONIOENCODING=utf-8`，因此只有用户自建镜像会遇到此问题。 |
| 在任务句柄上出现 `AttributeError: ... object has no attribute 'close'` | 链式调用了 `host.compute.create(...).attach_job(...)`，随后在任务对象上调用 `.close()`。应单独绑定计算句柄并关闭该句柄——参见上面的“远程计算”。 |
| `X_scVI` UMAP 上的批次仍然分离（校正不足） | 加强整合：提高 `n_top_genes`（例如 4000）或训练更长时间；再次检查 `batch_key` 是否确实指向技术批次。 |
| 整合后已知不同的细胞类型发生合并（过度校正） | 使用现有标签训练 scANVI——标签感知嵌入能够保持已知类别分离。（把变量从 `batch_key` 移到 `categorical_covariate_keys` 没有帮助：二者的条件化方式完全相同。） |

---

**下一步：** 使用 Scanpy 在 `X_scVI` 上聚类（`sc.pp.neighbors(use_rep="X_scVI")` → `sc.tl.leiden` → `sc.tl.umap`）；对于空间解卷积，应在 scRNA-seq 参考数据上训练 cell2location / DestVI / Tangram。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
