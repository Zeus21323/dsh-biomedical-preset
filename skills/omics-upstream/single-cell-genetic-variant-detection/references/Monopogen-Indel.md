# 单细胞Indel：先核实reads证据与真正实现

## 论文与源码状态

来源：[Single-Cell Indel Detection Enhances Genetic Ancestry and Cellular Lineage Analysis](https://doi.org/10.64898/2026.09.02.748725)，[Monopogen官方仓库](https://github.com/KChen-lab/Monopogen)。2026-09-08核验main commit `2c0a4b0868cb86a77f196cba29b4d4dd3ce482f6`，现有命令分为preProcess、germline、somatic，尚未核实该新论文Indel分支对应的可执行接口。不能虚构 `Monopogen indel` 命令，也不能把原有SNV命令或通用caller冒充论文方法。

当前脚本只做BAM基本就绪检查、或已有VCF的真实小Indel汇总；不执行新变异检测、分相、遗传祖源分类或谱系推断。若用户明确要求这些结果，先告知缺失的实现证据，核实官方新版本/资源，或说明可验证替代方法及其差异后再决定。

## 输入与实际可执行功能

仅有表达矩阵、UMAP或细胞类型表不能检测碱基插入缺失。核实测序类型（scRNA/scATAC/scDNA）、BAM来源、参考组装、样本身份、细胞barcode字段及检测设计；表达量不能当作基因型。

```bash
python scripts/inspect_single_cell_variants.py --mode bam-check --input aligned.bam --cell-tag CB --out-dir bam-check
python scripts/inspect_single_cell_variants.py --mode vcf-summary --input calls.vcf.gz --out-dir indel-summary
```

Python 3.12+；BAM检查另需samtools以及bai/csi索引。脚本运行quickcheck、读取参考序列头、抽查最多1000条比对中的指定barcode标签，不修改BAM。通过不证明索引新鲜、覆盖足够、参考正确或barcode全集合格；这些应在正式调用前单独检查。

VCF模式支持普通文本或gzip；保存每个非符号、REF/ALT长度不同的小变异等位基因，正确拆多等位基因GT，缺失基因型单独计数，不当作0/0。重复等位基因、无效GT、字段错误拒绝；符号结构变异、星号、breakend不按小Indel统计。同长替换不会算Indel。复杂等位基因仍需标准化/左对齐核验。

输出 `indels.tsv` 与运行检查记录；样本列不自动称为细胞列，没有barcode映射证据就按“VCF样本”解释。空Indel表是允许的观察，不伪造阳性。输出目录必须是新的。

## 科学质控和图件

正式检测需明确可检测区域、深度、比对/碱基质量、链与读段位置偏倚、重复序列/同聚物、等位基因脱落、批次、barcode混合及对照。scRNA还需考虑剪接和RNA编辑等伪信号；检测到序列差异不直接宣称体细胞DNA突变。

已有真实VCF可以生成Indel长度分布、每样本call/missing/carrier情况和可检测性图；没有truth set不能画灵敏度/准确率，没有独立证据不能画确定谱系树。计数差异可能是测序深度或可检测区域差异。直接交付矢量图、PNG、表、图注和Markdown解释；不得输出未经专业复核的个体遗传/临床结论。
