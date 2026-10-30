# STRiker 执行与质量控制

STRiker 用于从已比对的 Nanopore BAM 分析预定义 STR 位点，产生参考与样本 motif 统计、逐读段重复模式、覆盖报告和读段长度 KDE 图。它不是通用 VNTR 分型器，也不是全基因组串联重复发现器。

## 许可与安装边界

上游仓库为 [BaeLab/STRiker](https://github.com/BaeLab/STRiker)，声明使用 CC BY-NC-SA 4.0 且商业使用需另行授权。本 Skill 不分发 STRiker 源码或环境；执行前确认当前用途符合[上游许可证](https://github.com/BaeLab/STRiker/blob/main/LICENSE)。

使用用户已安装且固定到明确 commit 的 STRiker 工作副本。不从浮动 `main` 在无记录的情况下运行，也不在共享工作副本中直接改配置。

## 输入契约

1. BAM 必须是坐标排序、已建立 `.bai` 索引的 Nanopore 比对结果。
2. 参考 FASTA 必须建立 `.fai` 索引，并与 BAM 使用同一参考构建和 contig 长度。
3. 位点 CSV 必须恰好包含六列，且顺序为 `gene,chr,start,end,known_motif,pathogenic_expansion_number`。`gene` 必须唯一；多 motif 用 `/` 分隔；字段中不使用逗号或 CSV 引号。
4. 数值 `start`/`end` 传入 pysam 时按 0-based、half-open 解释。若用户输入为 1-based、inclusive，必须显式转换，不根据来源自动猜测。
5. `pathogenic_expansion_number` 是用户提供的绘图参考线，不是 STRiker 自动确立的临床分类。

`scripts/run_striker.py` 会把 1-based、inclusive 输入转为 STRiker 使用的 0-based、half-open CSV，检查重复 gene、motif字符、区间边界、FASTA/BAM contig 一致性、索引和跨越读段，不会猜测坐标体系。

## 运行

先在 STRiker 的 Python 环境中执行脚本自检：

```bash
python scripts/run_striker.py --self-test
```

然后运行一个样本：

```bash
python scripts/run_striker.py \
  --striker-script /path/to/STRiker.py \
  --loci /path/to/loci.csv \
  --coordinate-system 0-based-half-open \
  --reference /path/to/reference.fa \
  --bam /path/to/sample.bam \
  --output-dir /path/to/striker-output \
  --processes 4
```

输出目录必须不存在或为空。先用 `--dry-run` 可只完成预检、坐标规范化和运行清单生成。

## 运行时质控

当前 STRiker 默认配置会影响参考窗口、motif长度、连续重复次数、最小 motif 支持和覆盖判定。执行脚本从 `config/__init__.py` 读取并记录这些常量，不把上游默认值当作通用科学或临床阈值。

STRiker 的主要内置读段过滤是排除 unmapped、secondary 和 supplementary reads，并要求读段跨越目标区间。它不替代额外的 mapping quality、链偏倚、读长和局部比对审核。

## 停止与降级处理

参考构建或坐标不明、位点越界、索引缺失、染色体长度不一致时直接停止，不尝试自动更换参考或平移位点。单个位点没有跨越读段时可继续处理其他位点，但该位点只报“证据不足”，不根据覆盖内的局部读段推测完整长度。

进程退出码为零但预期结果缺失或为空时，将本次运行标记为不完整；保留日志、运行清单和已产生文件，但不将它们交付为成功分析。修正输入或环境后使用新的空输出目录重跑，避免新旧产物混合。

## 输出与解释

成功运行应产生：

- `motif_results/<sample>_motif_ref_denovo.xlsx`；
- `motif_results/<sample>_coverage.txt`；
- `gene_panel_output/<sample>.bam_gene_panel_output.pdf`；
- 执行适配器生成的 `striker_run.json`、`striker.log` 和规范化位点表。

将 KDE 结果称为“候选等位长度峰”。它不自动等于带有单倍型、置信区间和质量字段的正式二倍体基因型。低覆盖、宽峰、重叠峰、少数离群长读段或复杂 motif 中断时，保留原图和读段证据，并使用第二种调用方法或正交实验复核。
