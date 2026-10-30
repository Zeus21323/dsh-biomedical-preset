---
name: solublempnn
description: 使用 SolubleMPNN 对骨架进行逆折叠。SolubleMPNN 是在可溶性 PDB 子集上重新训练的 ProteinMPNN（Dauparas 等，2022），生成偏向胞质表达并减少聚集的序列。适用于普通 ProteinMPNN 设计发生聚集或形成包涵体、需要为可溶性表达重新设计邻近膜的折叠，或下一步将进行大肠杆菌表达筛选的场景。
license: Apache-2.0
---

# SolubleMPNN

SolubleMPNN 不是一个独立软件包——它是在可溶性 PDB 子集上重新训练的 ProteinMPNN 架构。这会使输出分布远离完整 PDB 模型乐于放置在表面的疏水残基；完整模型之所以会这样做，是因为训练集中的许多此类残基实际埋藏在晶体学界面或膜界面中。当目标是在异源宿主中获得可溶性产量时，应选择 SolubleMPNN；如果近天然序列恢复率更重要，则继续使用 `proteinmpnn`，因为可溶性先验会以牺牲几个百分点的恢复率为代价换取表面偏置。代码和权重采用 MIT 许可证（[github.com/dauparas/ProteinMPNN](https://github.com/dauparas/ProteinMPNN) 中的 `soluble_model_weights`；也可通过 [github.com/dauparas/LigandMPNN](https://github.com/dauparas/LigandMPNN) 使用）。模型足够小，可以在 CPU 上运行——若只为一个骨架生成少量序列，通常数秒即可完成，而且往往比派发任务更快；GPU 对批量任务有所帮助。无论使用哪种硬件，仓库都在任务中克隆（没有 PyPI 发行包；检查点随仓库提供）。

## 运行方法

```bash
pip install torch numpy   # 如尚未安装
git clone --depth 1 https://github.com/dauparas/ProteinMPNN.git proteinmpnn
cd proteinmpnn
python protein_mpnn_run.py \
  --pdb_path backbone.pdb --pdb_path_chains "A" \
  --out_folder out --num_seq_per_target 16 \
  --sampling_temp "0.1" --use_soluble_model
```

运行器使用仓库相对导入，因此 `cd` 这一行不可缺少——从其他目录通过绝对路径调用脚本会导致 `ModuleNotFoundError`。如果还需要把设计序列穿回骨架并生成 PDB，LigandMPNN 运行器接受 `--model_type soluble_mpnn`；该路径参见 `ligandmpnn`，除了 torch 之外还需要 ProDy。除此之外，参数界面与 `proteinmpnn` 完全相同；若采用第二种形式，则与 `ligandmpnn` 相同，其中包括字符串类型的温度参数，以及以 PDB 文件名主干为键的固定位点 JSONL——相关解析易错点参见 `proteinmpnn`。仓库只提供 `v_48_010` 和 `v_48_020` 两种可溶性权重；请求 `--model_name v_48_002 --use_soluble_model` 会因缺少检查点而报错，因此应让 `--model_name` 保持默认值。

输出位于 `out/seqs/<stem>.fa`，每条序列的标题包含 `score=` 和 `seq_recovery=`。与普通 ProteinMPNN 相比，针对天然结构的序列恢复率预计会下降几个百分点——这是可溶性先验正在发挥作用，而不是程序错误。

## 折叠需要时，疏水表面斑块仍会反复出现

可溶性权重会改变输出分布，但不会强制设置疏水性上限。如果某个特定表面斑块反复呈现疏水性，它很可能对结构具有承载作用，而网络正在为保持折叠付出溶解性代价。可以在其上叠加 `--omit_AAs "CW"` 或逐位点偏置，但在假定这项约束没有代价之前，应使用 `boltz` 或 `esmfold2` 检查所得设计是否仍能正确折叠。

## “可结晶”训练集不等于“在你的宿主中可溶”——保留正交筛选

该训练集由“可溶性足以完成结晶的结构”组成；这与“在 37 °C 的大肠杆菌中可溶表达”相关，但并不等价。对于表达产量构成瓶颈的批量设计，应先使用一个正交的序列预测器对 SolubleMPNN 输出进行排序，再投入湿实验名额；应把 MPNN 偏置视为扩大筛选漏斗，而不是取代后续筛选。

---

**下一步：** 使用 `boltz` 或 `esmfold2` 折叠设计序列，确认仍能恢复目标骨架，然后将通过筛选的序列送入表达实验。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

权重——SolubleMPNN（MIT）——[条款](https://github.com/dauparas/ProteinMPNN/blob/main/LICENSE)
