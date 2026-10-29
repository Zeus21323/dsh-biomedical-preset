# DiffDock — 批量和仅序列工作流

主 `SKILL.md` 介绍单复合物流程。下面两个扩展入口使用相同的 `inference` 模块，也同样需要注意 YAML 会覆盖 CLI 参数。

## 批量／小型化合物库对接

为每个复合物准备一行 CSV，并将文件传给 `--protein_ligand_csv`：

```csv
complex_name,protein_path,ligand_description,protein_sequence
6lu7_frag001,6lu7.pdb,CC(=O)Nc1ccc(O)cc1,
6lu7_frag002,6lu7.pdb,COc1ccc(C#N)cc1,
```

```bash
cd $DIFFDOCK_REPO
python3 -m inference \
  --config default_inference_args.yaml \
  --protein_ligand_csv batch.csv \
  --out_dir out/
```

每一行都会在 `--out_dir` 下获得独立的子目录。`complex_name` 可以留空，此时使用索引作为名称。`ligand_description` 接受 SMILES 字符串或 `.sdf`／`.mol2` 文件路径；每行只能包含一个配体，因此必须先拆分含多个配体的 SDF 文件。

对于超过数百个配体的化合物库，只能在复制的 YAML 中提高 `samples_per_complex`（参见 CLI 参数被覆盖的注意事项），并将 CSV 拆分到多个作业中——嵌入阶段会在整个运行期间将 ESM-2 650M 保留在 GPU 内存中。

## 仅序列受体（先运行 ESMFold）

如果没有受体结构，请将 `protein_path` 留空并填写 `protein_sequence`；DiffDock 会先使用 ESMFold 折叠该链，然后再进行对接。此流程需要安装 `fair-esm`；首次使用时会将 `esm2_t33_650M_UR50D` 检查点下载到 `~/.cache/torch/hub/checkpoints`。对于超过约 400 个残基的受体，折叠预计会占据大部分实际运行时间。与针对晶体结构得到的姿势相比，应更加谨慎地对待针对 ESMFold 模型得到的姿势：口袋几何结构会继承折叠模型的 pLDDT 可信度。

## 跨化合物库读取置信度

置信度 logit 是在单个复合物内部校准的，而不是在不同配体之间校准的。如需比较配体，请使用外部打分器对每个 `rank1.sdf` 重新打分；直接使用原始 DiffDock 置信度进行虚拟筛选排序，会混淆“姿势放置合理”和“结合紧密”这两个概念，上游 FAQ 也明确对此发出警告。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0

#### 第三方软件、内容、条款和信息

- **权重：** DiffDock-L（MIT）— [条款](https://github.com/gcorso/DiffDock/blob/main/LICENSE)
