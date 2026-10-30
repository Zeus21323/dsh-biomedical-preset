# peakScout 双向映射执行契约

## 资源与适配范围

[论文](https://doi.org/10.1093/bioinformatics/btag653)；[作者源码](https://github.com/vandydata/peakScout)，固定commit `20f4aafbc1599c3790dc0ae271c6a72f35a5b2f7`。代码许可为AGPL-3.0，本Skill不复制或分发上游代码；部署与再分发前核查适用许可。

作者支持多种peak格式，本包装器首版仅支持明确的BED6、非压缩GTF，以及可选无表头基因名单/本地cCRE BED。不调用网页，不上传数据；原生其他格式先按对应规则显式转换并保留原文件。

## 配置与执行

由代理从文件及研究问题生成JSON，相对输入路径以JSON目录为基准。示例配置：
```json
{
  "repo": "vendor/peakScout",
  "peaks": "peaks.bed",
  "gtf": "annotation.gtf",
  "assembly": "hg38",
  "annotation_assembly": "hg38",
  "question": "从实际研究问题填写本次位置映射目的",
  "mode": "peak2gene",
  "peak_type": "BED6",
  "k": 3
}
```

gene2peak另加 `genes` 路径；可选 `cre`（必须同时提供与assembly一致的 `cre_assembly`）、`up_bound`、`down_bound`。k默认3是展示候选的工程默认而非真实靶基因数量；距离与方向按固定原生实现解释。BED为0-based半开，GTF为1-based闭区间；脚本不猜参考版本、不自动改染色体名称。

固定上游GTF解析会跳过前五行。包装器在输出目录生成 `input.gtf` 副本，统一五行注释并保留全部非注释记录和原生坐标，记录变换与哈希，防止无表头文件丢失真实记录。原生程序从源码根目录运行，以正确读取物种配置。合成输入已验证双向映射；不等于真实全基因组性能验证。涉及单碱基边界时额外核对上游BED/GTF坐标语义，不把位置距离作为精确结合位点。

```bash
python scripts/run_peakscout.py --config run.json --out-dir plan-01
python scripts/run_peakscout.py --config run.json --out-dir run-01 --execute
```

Python 3.12+；执行环境安装上游requirements中的运行依赖。源码需固定commit且跟踪文件无修改。包装器调用原生decompose、peak2gene/gene2peak，保留原始CSV、run.log和run_manifest.json；失败保留日志，不覆盖旧输出、不自动下载参考。检查完成不表示依赖或科学结果已经验证；正式执行后还需逐条核对输出列、未匹配基因、同距候选和空结果。

## 科学结果与作图

最近位置只提供候选，不区分激活/抑制，不证明调控。所有peaks不一定是增强子。cCRE重叠也不是功能实验。添加表达共变、ABC、eQTL、接触或扰动证据时保留来源和组织背景。

先按固定输出列构建长表，画全部映射距离与重点位点，说明使用的是区域边界还是其他距离定义；不要把dist2peak直接改称TSS距离。完整CSV保留，重点位点选择规则写入图注。使用可用“科研可视化与报告”中的证据图脚本或项目作图代码，导出PDF/SVG、400 DPI PNG、原始作图表和图注，打开预览。解释“观察到的位置关系—支持的候选—不足以证明的调控—需要的独立证据”。没有实际映射不出结果图。
