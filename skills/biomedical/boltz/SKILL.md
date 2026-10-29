---
name: boltz
description: "使用 Boltz-2 预测蛋白质、核酸和小分子复合物结构（Passaro、Wohlwend 等，2025）。适用于针对靶标验证设计的结合蛋白、将蛋白质与 SMILES 或 CCD 配体共同折叠，或使用可选的结合亲和力预测功能获得开源 AlphaFold3 替代方案。"
metadata: {"source": "upstream-biomedical-science@0.1.1", "origin": "upstream-plugin", "license": "Apache-2.0"}
---

# Boltz-2

Boltz-2 是在使用方式上最接近 AlphaFold3 的开放权重扩散式共折叠模型：输入描述蛋白质、DNA、RNA 和配体链的 YAML，输出 mmCIF 结构以及 pTM、ipTM 和 pLDDT 置信度，并可选择使用小分子亲和力预测头。在我们的四个共折叠技能中，它是结合蛋白验证任务的默认选择——权重完全开放并采用 MIT 许可证，而且采样速度最快；需要使用第二个独立模型取得共识时选择 `chai1`，重视忠实于 AF3 的设置时选择 `openfold3`，可以不使用 MSA 时选择 `esmfold2`。代码和权重均采用 MIT 许可证（PyPI `boltz`，[github.com/jwohlwend/boltz](https://github.com/jwohlwend/boltz)）。

## 运行方法

```yaml
# complex.yaml
version: 1
sequences:
  - protein:
      id: A
      sequence: MVTPEGNVSLVDESLLVGVTDEDRAVRS...   # 靶标
  - protein:
      id: B
      sequence: AIQRTPKIQVYSRHPAENG...            # 结合蛋白
  - ligand:
      id: L
      smiles: 'N[C@@H](Cc1ccc(O)cc1)C(=O)O'      # 或使用 ccd: SAH
```

```bash
boltz predict complex.yaml \
    --use_msa_server --out_dir out/ --recycling_steps 3 --diffusion_samples 5
```

每条蛋白质链都需要一个 MSA；如果没有 MSA，程序会在模型加载前退出。`--use_msa_server` 会查询 `api.colabfold.com`（预计每条链会暂停 30–90 秒），除非已经有一个 `.a3m` 文件可在 YAML 的 `msa:` 下指定，否则这是正确的默认选择。设置 `msa: empty` 会强制使用单序列模式——这会牺牲准确度，并不能提高速度或节省内存，因为 MSA 搜索在 GPU 阶段开始前运行于 CPU。

每个输入的输出位于 `out/boltz_results_complex/predictions/complex/`。首先读取 `confidence_complex_model_0.json`：界面的社区通用通过线为 `iptm` > 0.5，折叠本身的通过线为 `complex_plddt` > 0.7；`confidence_score` 是结构排序所依据的加权综合分数。结构文件为 `complex_model_{0..N-1}.cif`（使用 `--output_format pdb` 时则为 `.pdb`）。

## 亲和力预测头

添加一个 `properties:` 块，将一条配体链指定为结合物，Boltz-2 就会在预测结构的同时预测蛋白质–小分子结合亲和力：

```yaml
properties:
  - affinity:
      binder: L            # 配体链 ID，而不是蛋白质链 ID
```

输出中会在置信度文件旁新增 `affinity_complex.json`：`affinity_pred_value` 是 log10(IC50，单位为 μM)——数值越低，结合越紧密（约 0 → 1 μM，−3 → 1 nM）；`affinity_probability_binary` 是范围为 0–1 的结合物与非结合物分类分数，应使用该分数对命中结果进行排序。每个输入只能指定一个亲和力配体；结合物必须是配体链（不支持蛋白质–蛋白质亲和力），而且 Boltz v2.2.x 将亲和力配体限制为最多 128 个原子。FASTA 输入完全无法请求亲和力预测。

## `msa: empty` 会损失准确度，而不能节省内存

其他地方曾建议使用单序列模式来适配显存较小的 GPU，但这并没有帮助：MSA 搜索运行于 CPU，因此使用 `--use_msa_server` 还是 `msa: empty` 不会改变峰值显存。如果出现 OOM，请降低 `--diffusion_samples` 或 `--max_parallel_samples`，或者改用 80 GB 显存规格；不要为此放弃 MSA、牺牲准确度。

## 缺少快速内核只会变慢，并非致命错误

如果 `cuequivariance_ops_torch` 或其 `libcue_ops.so` 出现 `ImportError`，说明编译后的三角形内核包不在加载器路径中。`--no_kernels` 会回退到参考 PyTorch 路径——速度大约慢 2 倍，但数值结果相同。因此，它适合用来解除一次性任务的阻塞，却不适合批量任务。

## 值得识别的错误

| 你看到的现象 | 含义／处理方法 |
| --- | --- |
| `Missing MSA's in input and --use_msa_server flag not set` | 某条蛋白质链没有 MSA——添加 `--use_msa_server`，或在 YAML 中将 `msa:` 设置为一个 `.a3m` 文件路径。 |
| `ImportError: ... cuequivariance_ops_torch`／`libcue_ops.so` | 快速内核 wheel 不可见——添加 `--no_kernels`（更慢，但结果正确），或修复环境的 `LD_LIBRARY_PATH`。 |
| 读取置信度 JSON 时出现 `KeyError: 'iptm'` | 输入只有一条链——ipTM 仅用于界面；请改为读取 `ptm`。 |
| 输出中没有 `affinity_*.json` | 使用了 FASTA 输入，或者 YAML 缺少 `properties:` 块——参见上面的“亲和力预测头”。 |

---

**下一步：** 对通过筛选的复合物计算空间冲突和界面指标，或者将它们重新交给 `proteinmpnn`，开始下一轮设计。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** Boltz-2（MIT）— [条款](https://github.com/jwohlwend/boltz/blob/main/LICENSE)
- **数据发送至：** ColabFold MSA 服务器（`api.colabfold.com`）· Steinegger Lab — [信息](https://github.com/sokrypton/ColabFold/wiki)
