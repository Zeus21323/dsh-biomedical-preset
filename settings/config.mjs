/** 由 _gen_settings_config.mjs 生成：设置页的 34 个分类开关。 */
/** 注意：字段必须带 .volatile()，否则 dsh-settings 的 volatileForm() 会把整行过滤掉。 */
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { profileDirCandidates } from '../shared/profile.mjs';

/**
 * schemastery 不在本包依赖里，要从宿主那边借。依次尝试：本包所在位置（装在
 * profile/node_modules 下时可向上解析）、profile 目录、Host 入口脚本所在的 DSH 安装。
 * 不写死任何一台机器的路径。
 */
function loadSchemastery() {
  const bases = [
    import.meta.url,
    ...profileDirCandidates().filter(Boolean).map((dir) => join(dir, 'package.json')),
    process.argv[1],
  ];
  const errors = [];
  for (const base of bases) {
    if (!base) continue;
    try {
      return createRequire(base)('@deepseek-ai/schemastery');
    } catch (e) {
      errors.push(`${base}: ${e?.code ?? e?.message ?? e}`);
    }
  }
  throw new Error(`biomedical-skill-settings: 找不到 @deepseek-ai/schemastery（${errors.join('; ')}）`);
}

const z = loadSchemastery();

export const Config = z.object({
  "sequencing-qc-alignment": z.boolean().default(true).volatile().description("测序质控与比对（10 个技能，另有 9 个 nf-core 流程经入口加载）"),
  "genome-assembly-comparative": z.boolean().default(true).volatile().description("基因组组装与比较基因组（6 个技能，另有 14 个 nf-core 流程经入口加载）"),
  "variant-calling-filtering": z.boolean().default(true).volatile().description("变异检测与过滤（10 个技能，另有 6 个 nf-core 流程经入口加载）"),
  "copy-number-structural-variation": z.boolean().default(true).volatile().description("拷贝数变异与结构变异（8 个技能，另有 2 个 nf-core 流程经入口加载）"),
  "variant-interpretation-clinical": z.boolean().default(true).volatile().description("变异解读与罕见病诊断（9 个技能，另有 2 个 nf-core 流程经入口加载）"),
  "population-genetics-gwas": z.boolean().default(true).volatile().description("群体遗传与 GWAS（21 个技能，另有 7 个 nf-core 流程经入口加载）"),
  "cancer-genomics-liquid-biopsy": z.boolean().default(true).volatile().description("肿瘤基因组与液体活检（21 个技能，另有 7 个 nf-core 流程经入口加载）"),
  "forensic-identity-genetics": z.boolean().default(true).volatile().description("法医与身份鉴定（10 个技能）"),
  "clinical-precision-medicine": z.boolean().default(true).volatile().description("临床精准医学与结局分析（10 个技能）"),
  "medical-imaging-radiomics": z.boolean().default(true).volatile().description("医学影像与放射组学（11 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "microscopy-cell-phenotyping": z.boolean().default(true).volatile().description("显微成像与细胞表型（13 个技能，另有 4 个 nf-core 流程经入口加载）"),
  "transcriptomics-quantification": z.boolean().default(true).volatile().description("转录组上游与定量（12 个技能，另有 20 个 nf-core 流程经入口加载）"),
  "differential-expression-enrichment": z.boolean().default(true).volatile().description("差异表达与功能富集（9 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "single-cell-core": z.boolean().default(true).volatile().description("单细胞基础分析（13 个技能，另有 7 个 nf-core 流程经入口加载）"),
  "single-cell-advanced-virtual-cell": z.boolean().default(true).volatile().description("单细胞高级与虚拟细胞（20 个技能）"),
  "spatial-omics": z.boolean().default(true).volatile().description("空间组学分析（9 个技能，另有 6 个 nf-core 流程经入口加载）"),
  "proteomics": z.boolean().default(true).volatile().description("蛋白质组学（12 个技能，另有 9 个 nf-core 流程经入口加载）"),
  "metabolomics-lipidomics": z.boolean().default(true).volatile().description("代谢组与脂质糖组（17 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "epigenomics-methylation": z.boolean().default(true).volatile().description("表观遗传与 DNA 甲基化（19 个技能，另有 12 个 nf-core 流程经入口加载）"),
  "regulatory-network-sequence-models": z.boolean().default(true).volatile().description("调控网络与序列模型（16 个技能，另有 2 个 nf-core 流程经入口加载）"),
  "microbiome-metagenomics": z.boolean().default(true).volatile().description("微生物组与宏基因组（15 个技能，另有 23 个 nf-core 流程经入口加载）"),
  "structural-biology-modeling": z.boolean().default(true).volatile().description("结构预测与建模（17 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "chemoinformatics-drug-design": z.boolean().default(true).volatile().description("化学信息学与药物设计（26 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "protein-engineering-synbio": z.boolean().default(true).volatile().description("蛋白工程与合成生物学（14 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "gene-editing-cloning": z.boolean().default(true).volatile().description("基因编辑与分子克隆（11 个技能，另有 2 个 nf-core 流程经入口加载）"),
  "pharmacogenomics-dosing": z.boolean().default(true).volatile().description("药物基因组学与用药（10 个技能）"),
  "immunology-immuno-oncology": z.boolean().default(true).volatile().description("免疫组学与免疫治疗（12 个技能，另有 5 个 nf-core 流程经入口加载）"),
  "literature-evidence-synthesis": z.boolean().default(true).volatile().description("文献检索与证据合成（12 个技能）"),
  "writing-document-delivery": z.boolean().default(true).volatile().description("写作与文档交付（17 个技能）"),
  "data-engineering-statistics": z.boolean().default(true).volatile().description("数据工程与统计方法（22 个技能，另有 2 个 nf-core 流程经入口加载）"),
  "workflow-reproducibility": z.boolean().default(true).volatile().description("计算流程与可复现性（5 个技能，另有 5 个 nf-core 流程经入口加载）"),
  "database-api-access": z.boolean().default(true).volatile().description("数据库与接口对接（10 个技能，另有 1 个 nf-core 流程经入口加载）"),
  "visualization-figures": z.boolean().default(true).volatile().description("可视化与图件（9 个技能）"),
  "research-design-hypothesis": z.boolean().default(true).volatile().description("研究设计与假设生成（9 个技能，另有 1 个 nf-core 流程经入口加载）"),
});
