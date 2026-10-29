---
name: shap
description: "当用户需要用SHAP解释生物医学表格模型、检查加和性与相关特征影响，并生成全局和个体级解释报告时使用。"
metadata: {"source": "upstream-science-core@0.3.8", "origin": "upstream-plugin"}
---

# 模型可解释性与SHAP分析

先明确模型预测的对象、输出尺度、目标类别、数据切分和解释用途。SHAP 描述模型如何形成预测，不说明特征对真实生物结局具有因果作用；训练数据泄漏、强相关特征和错误背景集会使解释看似合理但实际无效。

根据模型类型选择解释器。树模型优先使用 TreeExplainer；线性模型、深度模型和任意函数应选择相匹配的解释器。背景数据只能来自训练范围并保持代表性；分类模型必须说明解释的是 raw、概率还是损失空间。先验证 SHAP 值与基线值的加和重构，再生成 beeswarm、bar、dependence 和个体 waterfall 等图。

需要运行表格模型解释时读取[解释与审计规范](references/解释与审计规范.md)，然后运行 `scripts/tabular_shap_report.py`。该脚本接受 CSV 和目标列，训练一个可复现的基线随机森林并输出报告；它不是对任意生产模型的序列化加载器。维护时运行 `scripts/test_tabular_shap_report.py`。

交付模型性能、背景集、输出尺度、全局重要性、个体解释、相关特征敏感性和加和性误差。不得把 SHAP 排名直接写成生物标志物或治疗靶点结论。

## 默认图件交付


模型可解释性与SHAP分析的现有绘图入口调用[图件交付内核](scripts/figure_delivery.py)，为实际结果保存PNG、SVG、PDF，关闭背景主次网格，保留该分析的数据线与科学参照；逐图查看交付记录和最终预览，失败不得报告成功。
