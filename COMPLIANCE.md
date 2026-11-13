# 合规与质量报告

> 由 `node tools/grade.mjs` 根据仓库内容自动生成，不要手改。规则见 `tools/grade.mjs` 文件头。

## 等级分布

| 等级 | 数量 | 运行时处理 |
|---|---|---|
| 核心 | 27 | 正常列出 |
| 标准 | 551 | 正常列出 |
| 实验 | 2 | 目录描述前加〔实验〕，加载时要求额外核验并在报告中注明 |
| 受限 | 4 | 目录描述前加〔受限〕，加载时要求先告知用户并取得同意 |
| 弃用（已并入） | 13 | 不进目录，原文由主技能的索引引用 |

## 受限：会把内容发送到生成式 AI 服务

- `citation-management`：OpenRouter
- `latex-posters`：OpenRouter
- `image-painter`：OpenAI、SpeedAI
- `hypothesis-generation`：OpenRouter

## 序列外发到公共计算服务（加载时提示，不降级）

- `13-clinical-genomics-intervar`：ESM Forge
- `alphafold2`：ColabFold 公共 MSA 服务器
- `boltz`：ColabFold 公共 MSA 服务器
- `chai1`：ColabFold 公共 MSA 服务器
- `openfold3`：ColabFold 公共 MSA 服务器
- `nfcore-proteinfold`：ColabFold 公共 MSA 服务器

## 需要第三方 API 密钥

- `13-clinical-genomics-intervar`：ESM_API_KEY
- `tooluniverse-metabolomics`：OMIM_API_KEY
- `citation-management`：NCBI_API_KEY、OPENROUTER_API_KEY
- `github-deep-research`：GITHUB_TOKEN
- `paper-lookup`：CORE_API_KEY、NCBI_API_KEY、OPENALEX_API_KEY
- `latex-posters`：OPENROUTER_API_KEY
- `tiledbvcf`：TILEDB_REST_TOKEN
- `image-painter`：OPENAI_API_KEY、SPEEDAI_API_KEY、SPEEDAPI_API_KEY
- `hypothesis-generation`：OPENROUTER_API_KEY

## 涉及患者或受试者数据（加载时提示先去标识化）

共 61 个，按分类与描述关键词自动识别。

## 实验级：质量缺陷

- `cancer-mutation-landscape-oncoplot`：正文只有 181 字
- `cytometry-differential-abundance-analysis`：正文只有 198 字

## 许可证

| 许可证 | 数量 |
|---|---|
| 不明 | 411 |
| MIT | 165 |
| Apache-2.0 | 17 |
| BSD | 3 |
| GPL | 1 |

许可证不明的技能在公开分发前需逐个确认来源许可（见 THIRD_PARTY.md），确认后在 SKILL.md frontmatter 写 `license:` 或在目录放 LICENSE，再运行 `node tools/grade.mjs`。

### copyleft

- `pathml`：再分发需随附源码与许可证文本

### 许可证不明（按分类）

- 测序质控与比对（10）：`01-genome-alignment`、`01-genome-bam`、`01-genome-fastqc`、`01-genome-long-read-sequencing`、`01-genome-multiqc`、`01-genome-reads-trimming`、`genome-contamination-detection`、`long-read-alignment`、`nanopore-basecalling`、`sequencing-coverage-capture-efficiency`
- 基因组组装与比较基因组（8）：`01-genome-gene-annotation`、`02-population-genetics-phylogenetic-analysis`、`cross-species-annotation-projection`、`genome-assembly-qc`、`long-read-de-novo-assembly`、`nfcore-denovohybrid`、`nfcore-neutronstar`、`pangenome-synteny-analysis`
- 变异检测与过滤（12）：`01-genome-mtdna-variant-calling`、`01-genome-snp-calling`、`01-genome-target-sequencing`、`01-genome-variant-filtering`、`01-genome-wes`、`01-genome-wgs`、`long-read-variant-calling`、`nfcore-deepvariant`、`nfcore-exoseq`、`vcf-normalization-curation`、`vcf-qc-sample-consistency`、`variant-calling-wes-wgs`
- 拷贝数变异与结构变异（8）：`01-genome-germline-cnv`、`01-genome-loh-analysis`、`01-genome-repeat-expansion-analysis`、`01-genome-sv-detection`、`focal-amplification-ecdna-analysis`、`tumor-cnv-driver-event-analysis`、`01-genome-single-cell-cnv`、`cnv-sv-detection`
- 变异解读与罕见病诊断（9）：`13-clinical-genomics-hpo-matching`、`13-clinical-genomics-intervar`、`13-clinical-genomics-rare-disease-diagnosis`、`13-clinical-genomics-spliceai`、`13-clinical-genomics-trio-analysis`、`13-clinical-genomics-varsome`、`acmg-clingen-germline-cnv-classification`、`variant-annotation-gene-consequence`、`variant-pathogenicity-acmg`
- 群体遗传与 GWAS（21）：`02-population-genetics-admixture-ancestry-estimation`、`02-population-genetics-allele-frequency-analysis`、`02-population-genetics-genotype-phenotype-qc`、`02-population-genetics-gwas-association-analysis`、`02-population-genetics-gwas-meta-analysis`、`02-population-genetics-gwas-sumstats-qc`、`02-population-genetics-haplotype-analysis`、`02-population-genetics-ldsc-analysis`、`02-population-genetics-population-stratification`、`02-population-genetics-prs-polygenic-risk-score`、`02-population-genetics-qtl-target-prioritization`、`02-population-genetics-rare-variant-analysis`、`02-population-genetics-selection-analysis`、`02-population-genetics-two-sample-mr`、`colocalization-analysis`、`gwas-fine-mapping`、`genotype-imputation-phasing`、`gwas-locus-gene-prioritization`、`phewas-phenome-wide-association`、`twas-transcriptome-association`、`omics-causal-driver-inference`
- 肿瘤基因组与液体活检（21）：`14-cancer-genomics-clonal-evolution`、`14-cancer-genomics-driver-gene-analysis`、`14-cancer-genomics-hrd`、`14-cancer-genomics-intratumor-heterogeneity`、`14-cancer-genomics-msi`、`14-cancer-genomics-mutation-signature`、`14-cancer-genomics-somatic-mutation`、`14-cancer-genomics-subclone-analysis`、`14-cancer-genomics-tmb`、`15-liquid-biopsy-cancer-origin-prediction`、`15-liquid-biopsy-exosome-rna-analysis`、`15-liquid-biopsy-mrd-detection`、`cancer-gene-dependency-analysis`、`cancer-mutation-landscape-oncoplot`、`cfdna-fragmentomics-analysis`、`cfdna-preprocessing-umi-consensus`、`ctdna-mutation-detection`、`liquid-biopsy-assay-validation`、`public-cancer-cohort-analysis`、`tumor-fraction-estimation`、`tumor-only-somatic-variant-calling`
- 法医与身份鉴定（10）：`19-forensic-genomics-ancestry-snp`、`19-forensic-genomics-ibd-analysis`、`19-forensic-genomics-identity-snp`、`19-forensic-genomics-kinship-analysis`、`19-forensic-genomics-mixture-analysis`、`19-forensic-genomics-mtdna-haplogroup`、`19-forensic-genomics-str-genotyping`、`19-forensic-genomics-vntr-profiling`、`19-forensic-genomics-y-snp`、`19-forensic-genomics-y-str`
- 临床精准医学与结局分析（10）：`18-precision-medicine-diagnostic-biomarker`、`18-precision-medicine-patient-stratification`、`18-precision-medicine-predictive-biomarker`、`18-precision-medicine-prognostic-biomarker`、`clinical-decision-support`、`clinical-multimodal-llm-evaluation`、`clinical-prediction-model-validation`、`molecular-trial-matching`、`prognostic-biomarker-survival-analysis`、`clinical-statistics-survival`
- 医学影像与放射组学（11）：`20-ai-medical-imaging-ai-cnn-imaging`、`20-ai-medical-imaging-ai-feature-extraction`、`20-ai-medical-imaging-ai-image-omics-fusion`、`bids-neuroimaging-data-organization`、`cancer-imaging-data-retrieval`、`dicom-processing-deidentification`、`medical-image-analysis`、`medical-image-registration-resampling`、`medical-imaging-model-trustworthiness`、`neuroimaging-electrophysiology-analysis`、`nnu-net-medical-image-segmentation`
- 显微成像与细胞表型（13）：`20-ai-medical-imaging-ai-whole-slide-image-analysis`、`27-aging-longevity-sasp-analysis`、`cellpose-cell-nucleus-segmentation`、`scratch-wound-analysis`、`microscopy-data-management`、`microscopy-image-quantification`、`single-particle-tracking-diffusion`、`cytof-bead-normalization`、`flow-cytometry-clustering`、`cytometry-differential-abundance-analysis`、`fcs-qc-transformation`、`flow-cytometry-gating-analysis`、`nfcore-imcyto`
- 转录组上游与定量（12）：`04-transcriptomics-5-utr`、`04-transcriptomics-alternative-splicing`、`04-transcriptomics-fusion-transcript-detection`、`04-transcriptomics-m6a`、`04-transcriptomics-mirna-analysis`、`04-transcriptomics-rbp-regulation`、`04-transcriptomics-ribo-seq`、`04-transcriptomics-rna-editing`、`04-transcriptomics-rna-quantification`、`04-transcriptomics-transcript-assembly`、`nfcore-slamseq`、`rna-modification-clip`
- 差异表达与功能富集（7）：`gwas-functional-interpretation`、`gsea-gsva-scoring`、`04-transcriptomics-deseq2`、`metabolomics-differential-multivariate-stats`、`microbiome-differential-abundance`、`metabolite-pathway-mapping`、`single-cell-differential-abundance`
- 单细胞基础分析（14）：`scrna-qc-filtering`、`scatac-fragment-matrix`、`sc-multiome-integration`、`sc-batch-integration`、`sc-doublet-detection`、`sc-ambient-rna-correction`、`scrna-mito-diagnosis`、`sc-clustering-umap`、`sc-cell-type-annotation`、`nfcore-hadge`、`nfcore-smartseq2`、`single-cell-format-io`、`single-cell-staged-workflow`、`sc-rna-seq-analysis`
- 单细胞高级与虚拟细胞（18）：`sc-program-scoring`、`sc-rna-velocity`、`sc-trajectory-inference`、`sc-cell-communication`、`sc-perturb-seq`、`sc-virtual-perturbation`、`sc-drug-response-prediction`、`cite-seq-integration`、`sc-dna-rna-joint`、`metabolite-mediated-cell-communication`、`scvi-single-cell-probabilistic-modeling`、`secreted-protein-activity-inference`、`single-cell-alternative-splicing`、`single-cell-cohort-integration-meta-analysis`、`single-cell-genetic-variant-detection`、`single-cell-transposon-expression`、`transcriptomic-reverse-perturbation`、`scgpt-embedding`
- 空间组学分析（9）：`he-virtual-spatial-transcriptomics`、`spatial-atac-analysis`、`06-spatial-omics-cell2location`、`06-spatial-omics-spatial-domain-identification`、`06-spatial-omics-spatial-metabolomics`、`06-spatial-omics-spatial-microenvironment`、`spatial-proteomics`、`spatial-transcriptomics`、`21-biological-foundation-models-nicheformer`
- 蛋白质组学（12）：`27-aging-longevity-protein-aging-clock`、`07-proteomics-dia-proteomics`、`07-proteomics-lc-ms-ms`、`07-proteomics-phosphorylation`、`07-proteomics-protein-quantification`、`protein-function-annotation`、`07-proteomics-tmt-proteomics`、`affinity-proteomics-analysis`、`nfcore-ddamsproteomics`、`peptide-identification-protein-inference`、`proteomics-quality-control`、`proteomics-quantification`
- 代谢组与脂质糖组（17）：`tooluniverse-metabolomics`、`08-metabolomics-exposomics`、`08-metabolomics-exposure-biomarker-discovery`、`08-metabolomics-flux-analysis`、`08-metabolomics-icp-ms-analysis`、`08-metabolomics-metabolite-identification`、`08-metabolomics-targeted-metabolomics`、`08-metabolomics-untargeted-metabolomics`、`ce-ms-metabolomics`、`dda-dia-acquisition-design`、`ion-mobility-ccs-analysis`、`lipidomics-analysis`、`metabolomics-normalization-batch-correction`、`nmr-metabolomics`、`glycomics`、`lipidomics-annotation`、`metabolomics-profiling`
- 表观遗传与 DNA 甲基化（19）：`27-aging-longevity-dna-methylation-clock`、`03-epigenomics-atac-seq-analysis`、`03-epigenomics-chip-seq-histone-analysis`、`03-epigenomics-chromatin-loop-detection`、`03-epigenomics-cut-run`、`03-epigenomics-dmr-identification`、`03-epigenomics-dnase-seq-analysis`、`03-epigenomics-enhancer-gene-association`、`03-epigenomics-enhancer-identification`、`03-epigenomics-footprinting-analysis`、`03-epigenomics-hi-c-analysis`、`03-epigenomics-wgbs-analysis`、`chromatin-compartment-tad-analysis`、`chromatin-state-allele-specific-analysis`、`methylation-array-qc-deconvolution`、`nfcore-mnaseseq`、`epigenetics-drug-response-integration`、`dna-methylation-wgbs`、`epigenomics-peak-calling`
- 调控网络与序列模型（13）：`differential-regulatory-network`、`grn-inference`、`network-pharmacology-analysis`、`network-topology-community-analysis`、`sbml-network-modeling`、`string`、`temporal-gene-regulatory-network`、`wgcna-coexpression-network`、`03-epigenomics-basenji`、`04-transcriptomics-tf-activity-inference`、`single-cell-regulatory-network`、`evo2-sequence-scoring`、`plant-long-context-genome-modeling`
- 微生物组与宏基因组（15）：`microbial-community-metabolic-network`、`09-metagenomics-16s-analysis`、`09-metagenomics-amr-gene-analysis`、`09-metagenomics-host-microbiome-interaction`、`09-metagenomics-humann`、`09-metagenomics-kraken2`、`09-metagenomics-mag-reconstruction`、`09-metagenomics-pathway-prediction`、`bgc-identification-classification`、`edna-metabarcoding-analysis`、`metagenomics-analysis`、`nfcore-vipr`、`strain-tracking-transmission-analysis`、`mgm-microbiome-foundation-model`、`microbiome-diversity-analysis`
- 结构预测与建模（12）：`12-structural-biology-alphafold2`、`12-structural-biology-alphafold3`、`all-atom-design`、`12-structural-biology-protein-mutation-enhancement`、`cryo-em-structure-data-retrieval`、`molecular-dynamics`、`protein-rna-interaction-prediction-design`、`protein-structure-database-search`、`protein-structure-preparation`、`protein-structure-quality-assessment`、`protein-structure-similarity-search`、`structure-geometry-interface-analysis`
- 化学信息学与药物设计（25）：`12-structural-biology-molecular-docking`、`22-ai-ai-drug-discovery-docking-ai`、`22-ai-ai-drug-discovery-dti-prediction`、`22-ai-ai-drug-discovery-molecular-generation`、`22-ai-ai-drug-discovery-retrosynthesis-planning`、`27-aging-longevity-drug-repurposing`、`admet-prediction`、`binding-free-energy-pose-validation`、`candidate-toxicity-risk-assessment`、`chemical-scaffold-sar-analysis`、`compound-commercial-availability`、`compound-identity-lookup`、`conformer-shape-similarity`、`covalent-inhibitor-design`、`drug-target-evidence-validation`、`gpcr-ligand-pharmacology`、`molecular-descriptors-fingerprints`、`molecular-drug-discovery`、`molecular-similarity-substructure-search`、`molecule-standardization-format-conversion`、`pharmacophore-modeling-screening`、`protein-binding-pocket-detection`、`qsar-modeling`、`targeted-protein-degradation-design`、`virtual-screening`
- 蛋白工程与合成生物学（10）：`antibody-engineering-developability`、`inverse-folding-design`、`aggregation-risk-design`、`26-synthetic-biology-metabolic-engineering`、`26-synthetic-biology-self-driving-lab`、`antimicrobial-peptide-mic-prediction`、`cell-free-protein-expression-optimization`、`esm`、`esm3-protein-generation-structure-modeling`、`rfdiffusion`
- 基因编辑与分子克隆（12）：`26-synthetic-biology-gene-design`、`base-editing-design`、`construct-motif-scanning-logo`、`crispr-screen-hit-analysis`、`crispr-screen-library-design`、`crispr-screen-quality-control`、`grna-design`、`hdr-donor-template-design`、`nfcore-crisprvar`、`crispr-off-target-prediction`、`pcr-qpcr-primer-design`、`restriction-enzyme-digest-map`
- 药物基因组学与用药（10）：`17-pharmacogenomics-adverse-drug-reaction-prediction`、`17-pharmacogenomics-cyp450-analysis`、`17-pharmacogenomics-drug-response-prediction`、`17-pharmacogenomics-tacrolimus-dosing`、`17-pharmacogenomics-warfarin-dosing`、`cpic-dpwg-guideline-interpretation`、`drug-interaction-pk-pd-modeling`、`noncompartmental-pk-analysis`、`pharmacogenomics-clinical-report`、`pharmacogenomics-evidence-retrieval`
- 免疫组学与免疫治疗（12）：`16-immunomics-antibody-lineage`、`16-immunomics-clonotype-analysis`、`16-immunomics-epic`、`16-immunomics-hla-hd`、`16-immunomics-ssgsea-immune-score`、`16-immunomics-tcr-repertoire`、`16-immunomics-tide`、`16-immunomics-tumor-antigen-prediction`、`mhc-binding-prediction`、`tcr-bcr-antigen-specificity-prediction`、`vaccine-epitope-hla-coverage-design`、`immunogenomics`
- 文献检索与证据合成（7）：`biomedical-knowledge-graph-rag`、`evidence-validation`、`github-deep-research`、`literature-evidence-writing`、`paper-lookup`、`paper-review`、`surveymaster`
- 写作与文档交付（10）：`bioinformatics-writer`、`clinical-research-reporting`、`docx-equation-processor`、`general-writer`、`grant-writing-agent`、`latex-posters`、`md-to-docx`、`ppt-builder`、`ppt-reader`、`tex-to-docx`
- 数据工程与统计方法（19）：`cdisc-clinical-data-standardization`、`fhir-ehr-interoperability`、`bioinformatics-format-conversion-integrity`、`data-processing-tables`、`exploratory-data-analysis-statistical-tests`、`instrument-data-standardization`、`machine-learning-evaluation`、`omics-negative-control-calibration`、`output-fidelity-lock`、`research-data-privacy-deidentification`、`shap`、`software-engineering-testing`、`10-multi-omics-integration-diablo`、`10-multi-omics-integration-early-integration`、`10-multi-omics-integration-late-integration`、`10-multi-omics-integration-mofa`、`10-multi-omics-integration-omics-network-fusion`、`biomedical-time-series-forecasting`、`gtars`
- 计算流程与可复现性（5）：`bioinformatics-agent-reliability-evaluation`、`biomedical-result-drift-audit`、`infrastructure-workflows`、`nfcore-catalog`、`standardization`
- 数据库与接口对接（7）：`api-external-integration`、`mcp-tool-operations`、`scientific-database-access`、`metabolomics-database-search`、`microbiome-data-retrieval`、`proteomics-data-retrieval`、`single-cell-data-retrieval`
- 可视化与图件（8）：`genome-browser-track-creation`、`biological-network-visualization`、`drawio`、`excalidraw-diagram-generator`、`image-painter`、`matplotlib`、`scientific-visualization-reporting`、`protein-structure-visualization`
- 研究设计与假设生成（5）：`clinical-trial-workflows`、`experiment-protocol-design`、`public-omics-study-design-report`、`scientific-problem-hypothesis`、`multi-omics-integration-design`
