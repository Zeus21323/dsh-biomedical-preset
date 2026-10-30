---
name: ligandmpnn
description: 使用 LigandMPNN（Dauparas 等，2023）在配体、核酸和金属环境下对蛋白质骨架进行逆折叠。适用于重新设计结合口袋中围绕已结合小分子或辅因子的残基、设计必须保持几何构型的金属配位位点，或从任意 MPNN 运行中获得穿线了设计序列的 PDB。
license: Apache-2.0
---

# LigandMPNN

LigandMPNN 在 ProteinMPNN 图结构中加入了非蛋白质原子——小分子、核酸和金属对网络可见——因此，只要设计表面包含普通 `proteinmpnn` 会忽略的已结合配体或辅因子，它就是合适的逆折叠工具。同一个 `run.py` 也是运行其他 MPNN 系列最方便的入口，因为它不同于原始 ProteinMPNN 脚本，会将设计序列重新穿线到输入结构上，并在 FASTA 旁同时写出 PDB。代码和权重均采用 MIT 许可证（[github.com/dauparas/LigandMPNN](https://github.com/dauparas/LigandMPNN)）。该模型足够小，可以在 CPU 上运行——针对一个结构生成少量设计通常只需数秒，并且一般比调度远程任务更快。因此，常规路径是在本地安装 `torch numpy biopython ProDy ml_collections dm-tree`；GPU 则有助于批量任务。

## 运行方法

```bash
pip install torch numpy biopython ProDy ml_collections dm-tree
git clone --depth 1 https://github.com/dauparas/LigandMPNN.git ligandmpnn
cd ligandmpnn
sed -i 's/np\.int\b/np.int64/g' openfold/np/residue_constants.py   # 仓库固定使用 numpy 1.23；>=1.24 已移除此别名
bash get_model_params.sh ./model_params
python run.py \
  --model_type ligand_mpnn \
  --checkpoint_ligand_mpnn ./model_params/ligandmpnn_v_32_010_25.pt \
  --pdb_path complex.pdb \
  --out_folder out \
  --batch_size 8 --number_of_batches 4 \
  --temperature 0.1 \
  --fixed_residues "A45 A46 A47 A48"
```

残基选择使用一个带引号字符串，其中包含以空格分隔的 `{chain}{resnum}` token，例如 `"A45 A46 B10"`；插入码直接追加，例如 `"B82A"`。`--fixed_residues` 和 `--redesigned_residues` 都采用此格式。`--bias_AA_per_residue` 和 `--omit_AA_per_residue` 则接收 JSON 文件路径，其中的键使用相同的 `{chain}{resnum}` 格式；`--chains_to_design` 使用逗号分隔，例如 `"A,B"`。如果只想重新设计结合口袋，通常在 `--redesigned_residues` 中列出口袋残基，比固定其余所有残基更简洁。

在 `--out_folder` 下会生成 `seqs/<stem>.fa`，其标头包含 `overall_confidence` 和 `ligand_confidence`；还会生成 `backbones/<stem>_{1..N}.pdb`，其中设计序列已经穿线到输入坐标上。启用 `--pack_side_chains 1` 时，`packed/` 中还会生成全原子侧链打包模型。即使是仅蛋白质任务，穿线 PDB 也是优先使用此运行器的原因。

## 模型类型——如何选择

| `--model_type` | 可见信息 | 用途 |
| --- | --- | --- |
| `ligand_mpnn` | 骨架 + 配体／核酸／金属原子 | 结合口袋或活性位点设计 |
| `protein_mpnn` | 仅骨架 | 蛋白质–蛋白质；权重与 `proteinmpnn` 相同 |
| `soluble_mpnn` | 仅骨架，使用可溶蛋白训练 | 偏向表达的先验；参见 `solublempnn` |
| `*_membrane_mpnn` | 骨架 + 膜标签 | 跨膜蛋白设计 |

每种模型类型都有各自的 `--checkpoint_<type>` 参数；错误配对会在加载时被发现，但默认检查点路径是相对于仓库的。因此，应从克隆目录内部运行，或者传入绝对路径。

## ProDy 在 Python 3.11 上从源码编译——没有 C 编译器时 `pip install` 会失败

`run.py` 会无条件导入 ProDy 以解析配体原子。在 Python 3.11 上，PyPI 缺少预编译 wheel，因此 `pip install ProDy` 会从源码编译，并需要可用的 C／C++ 编译器。在 Modal 的 `add_python` 基础环境中，默认 `CXX=clang++` 指向不存在的二进制文件——请执行 `apt_install("build-essential")`，并在安装前导出 `CC=gcc CXX=g++`。在大多数本地 CPU Python 发行版中，如果没有适用于当前 Python 的 wheel，sdist 通常约 10 秒即可完成构建。

## 关闭配体环境会改变答案，而不会改变模型

`--ligand_mpnn_use_atom_context 0` 会保留配体感知权重，但在推理时遮盖配体原子。该选项适用于消融实验：比较开启和关闭环境时的差异，可以判断配体在多大程度上影响设计。但它**不等同于**运行 `protein_mpnn`，后者使用的是在没有这些特征的条件下训练的另一个检查点。如需公平的仅蛋白质基线，请切换 `--model_type`。

## 移除 HETATM 或使用链过滤器会静默丢弃配体——设计结果将无法感知口袋

如果没有找到配体原子，LigandMPNN 不会发出警告；它只会像选择了 `--model_type protein_mpnn` 一样继续运行。常见原因有两个：上游清理步骤移除了输入 PDB 中的 HETATM 记录；或者 `--parse_these_chains_only` 只列出了蛋白质链，没有包含配体链。如果 FASTA 标头中的 `ligand_confidence` 缺失，或者所有设计的该值都为零，则说明模型从未看到配体——应修复输入，不要信任这些序列。

## 值得识别的错误

| 你看到的现象 | 含义／处理方法 |
| --- | --- |
| `ModuleNotFoundError: No module named 'tree'` | 执行 `pip install dm-tree`——内置的 OpenFold 会无条件导入它。 |
| `module 'numpy' has no attribute 'int'` | 对 `openfold/np/residue_constants.py` 执行上面的 `sed` 补丁，或固定 `numpy<1.24`；后者仅适用于 Python≤3.11。 |
| 执行 `pip install ProDy` 时出现 `error: command 'clang' failed` | 参见上面的 ProDy 注意事项——执行 `apt_install("build-essential")` 和 `env({"CC":"gcc","CXX":"g++"})`。 |
| `model_params/...` 出现 `FileNotFoundError` | 尚未获取检查点——从克隆目录内部执行 `bash get_model_params.sh ./model_params`。 |

---

**下一步：** 使用 `boltz` 或 `chai1` 将设计序列与配体共同折叠；二者都接受 SMILES／CCD 输入。然后根据 ipTM 和配体放置结果进行筛选。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** LigandMPNN（MIT）— [条款](https://github.com/dauparas/LigandMPNN/blob/main/LICENSE)
