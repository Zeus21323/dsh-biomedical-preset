# ESMC 语言模型（Biohub）

ESMC 是 Biohub 的 ESM-2 后继模型：它采用 pre-norm Transformer、RoPE、SwiGLU、QK-LayerNorm 和无偏置结构，在 28 亿条序列（UniRef、MGnify 和 JGI）上以 15% MLM 训练。模型有三种规模：300M（30 层，d=960）、600M（36 层，d=1152）和 6B（80 层，d=2560）。接触预测 P@L-LR：ESMC-6B 为 0.725（±0.002），ESM2-15B 为 0.593。ESMC-6B 权重由 6 个 safetensors 分片组成，总计 25.41 GB。

## MLM logits 与隐藏状态

```python
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

model = AutoModelForMaskedLM.from_pretrained(
    "biohub/ESMC-6B", dtype=torch.bfloat16, device_map="auto"
).eval()
tok = AutoTokenizer.from_pretrained("biohub/ESMC-6B")

inp = tok([seq], return_tensors="pt", padding=True)
inp = {k: v.to(model.device) for k, v in inp.items()}
with torch.inference_mode():
    out = model(**inp, output_hidden_states=True)
# out.logits：[B, L+2, 64]（词表大小为 64；BOS/EOS 位于两端）
# out.hidden_states：由 81 个 [B, L+2, 2560] 张量组成的元组
#（6B 有 80 层，加上输入嵌入）
```

掩码标记是 `<mask>`（ID 32），应使用 `tok.mask_token`。原生 SDK 的 `_` 约定不适用于 HF tokenizer：`_` 不在词表中，会被编码为 `<unk>`，从而静默破坏突变评分。下游任务的最佳层：功能任务使用第 50–60 层（论文 A.1.4.2–3 节）；接触预测头读取最后一层。

## 突变评分（零样本 LLR／伪 PPL）

论文算法 14 将该方法用作结合蛋白设计中的语言模型正则项：进行 M 次前向计算，每次遮盖 15% 的可变位置，计算真实 token 相对于 ESMC logits 的交叉熵，然后取平均值。零样本单突变 LLR 等于被遮盖位置上的 `logp(mut) - logp(wt)`，参见 Biohub cookbook `esmc_mutation_scoring.ipynb`。

## SAE 特征（第 60 层，k=64，codebook 16384）

```python
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained("biohub/ESMC-6B", device_map="auto").eval()
tok   = AutoTokenizer.from_pretrained("biohub/ESMC-6B")
sae   = AutoModel.from_pretrained(
    "biohub/ESMC-6B-sae-k64-codebook16384",
    allow_patterns=["config.json","layer_60.safetensors"],
    device=model.device,
)
sae.initialize_layers([60])
model.add_sae_models([sae.layers["60"]])

inp = tok(seq, return_tensors="pt"); inp = {k:v.to(model.device) for k,v in inp.items()}
with torch.inference_mode():
    out = model(**inp)
feat = out["sae_outputs"]["layer60"].to_dense()[0, 1:-1]   # [L, 16384]，去除 BOS/EOS
```

示例输出（Src，536 aa）：形状为 `[536,16384]`，`nnz=34432`（每个残基约 64 个非零特征）。论文中的 atlas SAE 位于第 60 层。特征元数据 API 仍为 alpha 版本，端点可能变化；请检查 [biohub.ai/esm 文档](https://biohub.ai/esm)。`https://biohub.ai/esm/protein/api/v1alpha1/features/{idx}` 返回 `{description, top_100_uniref_ids, ...}`。论文中有 5,382 个特征被分类为 `"functional_site"`。

## 接触预测

论文 A.1.4.1 节：20,775 条链，使用 40% MMseqs 聚类，`sep>=24`，`Cbeta<8A`。P@L-LR（95% CI，bootstrap n=5000）：ESMC-6B 为 0.725（±0.002），ESMC-600M 为 0.589，ESM2-15B 为 0.593。接触预测头读取最后一层 attention／logits；回归预测头参见 `esm.models.esmc` 模块。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** ESMFold2／ESMC · Biohub（MIT）— [条款](https://github.com/Biohub/esm/blob/main/LICENSE.md)
