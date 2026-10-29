# ESMFold2-Experimental*——设计钩子

四个 `biohub/ESMFold2-Experimental*` 仓库会加载为 `ESMFold2ExperimentalModel`，这是一个独立类，位于 `modeling_esmfold2_experimental.py`。与 `ESMFold2Model` 不同，它的 `forward()` 没有使用 `@torch.inference_mode()` 装饰，并公开 `res_type_soft` 关键字参数（“在设计中用于提供软序列输入”）：

```python
out = model(**features, res_type_soft=soft_oh,  # [1,L,NUM_RES_TYPES]，requires_grad
            num_loops=1, num_sampling_steps=1, num_diffusion_samples=1)
D = out['distogram_logits']  # 保留梯度；trunk 在以下设置下运行
                             # torch.set_grad_enabled(res_type_soft is not None)
```

扩散和置信度预测头在 `torch.no_grad()` 下运行，因此只有 `distogram_logits` 携带计算图。**设计流程（算法 11）必须使用 Experimental 变体**——正式发布的 `ESMFold2`／`ESMFold2-Fast` 的 `forward()` 使用了 `@torch.inference_mode()`，无法通过它进行反向传播。

## 注意：Experimental 模型上的 `set_kernel_backend("fused")`

**不要在 Experimental 模型上调用 `set_kernel_backend`。** 置信度预测头在 bf16 autocast 块之外运行，因此 fused 矩阵乘法会接收到 fp32 输入并抛出：

```text
RuntimeError: self and mat2 must have the same dtype, but got BFloat16 and Float
```

参考路径才是正确选择；论文中的设计循环从未调用 fused 后端。fused 后端只在正式发布的 `ESMFold2Model`／`ESMFold2-Fast` 通过 `builder.fold()` 运行时得到验证。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** ESMFold2／ESMC · Biohub（MIT）— [条款](https://github.com/Biohub/esm/blob/main/LICENSE.md)
