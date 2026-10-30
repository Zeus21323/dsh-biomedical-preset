# WGCNA+ 方法分支

## 版本、许可与实际能力

[论文](https://doi.org/10.64898/2026.09.02.748772)；[作者仓库](https://github.com/bigomics/WGCNAplus)，固定commit `c162dc4ef6c3cef880568f40b32b260755246848`，R包0.1.0。论文摘要的无限制使用表述与当前DESCRIPTION中的Dual Commercial and Non-Commercial不一致；执行者需确认适用许可，不自动安装、上传数据或复制上游代码。

已核验接口 `computeWGCNA_multiomics`：输入命名的特征×样本矩阵列表，返回layers、me.genes、settings等。该原生接口还会构建LASAGNA模型/图，不能通过关闭report跳过，因此lasagna是此路径的必需依赖。完整返回对象保存在RDS；包装脚本只核验模块成员导出及模块大小图，不认证图的生物学有效性。共识、保留性、跨层富集、协变量性状模型和AI解读需按对应原生接口另外验证后执行，不能声称一次包装运行包含全部论文功能。

## 数据与参数

代理准备data.rds：list(dataX=命名矩阵列表,samples=行名为样本ID的数据框)。各矩阵列必须与samples行完全同序；有限值、唯一特征ID、无常量行。分层保留RNA/蛋白/其他实体身份。不配对队列不能伪造列对应；这类任务使用共识/保留性路线而非本包装器。

settings.rds是列表，字段为seed、power、ngenes、minmodsize、mergeCutHeight、minKME、deepsplit、parameter_reason、license_confirmed。由代理根据真实数据形成参数依据，许可确认不能机械设TRUE。power需预先确定的正数（单值或逐层值），不能为目标基因进模块反复调整。内部fast TOM使用40维近似，因此首版包装器保守要求至少50样本和每层50特征；这是适配边界，不是所有WGCNA研究的统一样本量标准。

```bash
Rscript scripts/run_wgcna_multiomics.R data.rds settings.rds wgcna-01
```

需要固定commit安装的WGCNAplus及其依赖、lasagna、ggplot2、svglite；通过remotes从该commit安装才能记录RemoteSha，安装前核查许可。无R或包不可用时交付数据检查和命令，不声称运行。现阶段未在本机R环境做生物学实跑。

默认关闭外部AI、网络报告、富集与共识，避免无授权的数据发送和未经核实的分析扩展。失败保留status.txt，使用新输出目录。RDS只读取可信来源，结果保留成员表、完整对象、配置、输入MD5和sessionInfo。

## 完整任务中的进一步分析

比较软阈值/模块切分合理性、模块–性状关联的供体与批次混杂、跨层共同变化和独立队列保留性。模块成员度不等于因果驱动，网络hub和差异基因是不同概念。跨层实体映射需来源，不能仅按名字强行一一匹配。

LASAGNA构建多部图，需要核实实际版本、输入、参数和许可；图上的边不自动是调控边。其当前原生调用有内部参数（例如nc=20），小模块数量时需检查可运行性，不能以包装器样本数检查代替。AI文本若启用，只接收经授权的最小结果摘要，逐条引用实际模块成员和分析证据，不引用模型臆造的文献。

## 图件与解释

包装器直接输出模块大小的PDF/SVG/400 DPI PNG和图源表；这是描述性QC，不是模块–性状热图。真实完成其他分析后才生成相应效应/区间、跨层热图和保留性图，保留全结果、过滤和多重检验记录。打开预览检查模块数量较多时的标签，不把颜色本身解释为生物功能。

最终报告写清当前实际运行的范围、参数依据、稳定与不稳定模块、阴性和外部验证缺口，关联结果文件，不承诺文章创新性或录用。
