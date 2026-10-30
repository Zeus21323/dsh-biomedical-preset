---
name: proteinmpnn
description: 使用 ProteinMPNN（Dauparas 等，2022，github.com/dauparas/ProteinMPNN）将蛋白质骨架（PDB 结构）逆折叠为氨基酸序列。适用于对 RFdiffusion 骨架进行序列设计、在固定界面残基的同时重新设计 PDB 中的一条链，或生成跨温度采样的序列集合供下游折叠使用。
license: Apache-2.0
---

# ProteinMPNN

ProteinMPNN 是结合蛋白设计流程中的默认逆折叠步骤：它是一个只读取骨架几何信息的消息传递网络，因此当设计表面是蛋白质—蛋白质界面时，它是正确选择；一旦界面包含配体、核酸或金属，它就不再合适——`ligandmpnn` 通过几乎相同的命令行界面把这些原子加入图中，而 `solublempnn` 则换用在可溶性结构上训练的权重，提供偏向表达性能的先验。代码和权重采用 MIT 许可证（[github.com/dauparas/ProteinMPNN](https://github.com/dauparas/ProteinMPNN)）。模型足够小，可以在 CPU 上运行——若只为一个骨架生成少量序列，通常数秒即可完成，而且往往比派发远程任务更快；对于批量任务，例如数百个骨架或较大的 `--num_seq_per_target`，GPU 会有所帮助。无论使用哪种硬件，仓库都在任务中克隆——没有 PyPI 发行包，检查点随仓库一同提供。

## 运行方法

```bash
pip install torch numpy   # 如尚未安装
git clone --depth 1 https://github.com/dauparas/ProteinMPNN.git proteinmpnn
cd proteinmpnn
python protein_mpnn_run.py \
  --pdb_path backbone.pdb --pdb_path_chains "A" \
  --out_folder out --num_seq_per_target 16 --sampling_temp "0.1"
```

有两个参数几乎会让所有初次使用者踩坑。`--sampling_temp` 会被解析为以空格分隔的字符串，因此一次运行可以扫描多个温度；单个值无需加引号，但包含多个值的扫描必须放在引号中（`"0.1 0.2 0.3"`），而逗号永远不会起分隔作用——`"0.1,0.2"` 会在转换为浮点数时失败。`--pdb_path_chains` 同样是在一个带引号的参数中以空格分隔（`"A B"`）；逗号会被保留为链 ID 的一部分。

设计结果位于 `out/seqs/<pdb_stem>.fa`。第一条记录是输入序列；每条设计序列的标题都包含 `score=`（平均负对数似然——越低表示置信度越高）、`global_score=` 和 `seq_recovery=`。ProteinMPNN 只写出序列——不会把序列重新穿回骨架。如果需要包含设计序列的 PDB，`ligandmpnn` 运行器会自动将其写入 `backbones/`，并且可以使用 `--model_type protein_mpnn` 调用相同的权重。

## `--fixed_positions_jsonl` 中的扁平链映射会静默重新设计所有残基

`--fixed_positions_jsonl` 要求每一行都是一个 JSON 对象，其键依次为 PDB 文件名主干、链，以及从 1 开始编号的残基列表：`{"backbone": {"A": [10, 11, 12], "B": []}}`。如果直接传入内层的 `{"A": [...]}`——这看起来是最自然的猜法——程序会静默地将其视为“没有匹配到 PDB”，从而重新设计所有位置。仓库内置的 `helper_scripts/make_fixed_positions_dict.py` 可以根据链和范围字符串生成正确结构，值得多执行这一步；`--chain_id_jsonl` 和 `--tied_positions_jsonl` 也遵循相同的外层文件名主干规则。

## 检查点——如何选择

| `--model_name` | 训练噪声 | 用途 |
| --- | --- | --- |
| `v_48_002` | 0.02 Å | 最高序列恢复率；适合接近天然结构的重新设计 |
| `v_48_020`（默认） | 0.20 Å | 从头设计骨架——能够容忍 RFdiffusion 骨架的不完美 |
| `v_48_030` | 0.30 Å | 非常粗糙的骨架；序列恢复率最低 |
| `--use_soluble_model` | — | 切换到可溶性结构训练的权重集；参见 `solublempnn` |

## 值得识别的错误

| 看到的错误 | 含义及处理方法 |
| --- | --- |
| `KeyError: 'A'` | PDB 中不存在该链字母——运行 `grep '^ATOM' file.pdb \| cut -c22 \| sort -u` 查看实际存在的链。 |
| `*_jsonl` 参数出现 `JSONDecodeError` | 该参数需要文件路径，而不是行内 JSON；先把 JSON 写入文件。 |
| 使用 `--fixed_positions_jsonl` 后仍重新设计了所有位置 | 缺少外层 PDB 文件名主干键——参见上面的易错点。 |
| 相对导入出现 `ModuleNotFoundError` | 从错误的当前工作目录运行了脚本——先 `cd` 进入克隆的仓库；这些导入使用仓库相对路径。 |

---

**下一步：** 使用 `boltz`、`chai1` 或 `esmfold2` 将设计序列与靶标共同折叠，并根据 ipTM 进行筛选。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

权重——ProteinMPNN（MIT）——[条款](https://github.com/dauparas/ProteinMPNN/blob/main/LICENSE)
