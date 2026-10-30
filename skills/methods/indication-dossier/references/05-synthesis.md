# 阶段 5——综合

**何时执行：** `waypoints/regulatory_trials.json` 已存在时。

## 目标

读取所有 waypoint 文件并编写最终 Markdown 报告，同时为下游使用者写入 `research_output.json`。

## 输出结构

**最终输出：** `waypoints/indication_dossier_report.md`

```markdown
# 适应症档案：[名称]

**定义：** [一句话临床定义]
**ICD-10：** [编码，或“不是标准诊断实体”]
**父级适应症：** [父级名称，或“根级”]

## 1. 患者人群定义与流行病学

### 1.1 诊断标准
[如何识别这一人群。共识定义、诊断标准。
说明标准是否仍在演变，或该人群是否属于非标准定义。]

### 1.2 患病率与发病率
[全球和美国患病率。发病率趋势。数据质量说明。]

### 1.3 人口统计学特征与风险因素
[年龄、性别、种族／族裔分布。关键风险因素和合并症。]

### 1.4 自然病程
[疾病病程、进展和分期。死亡率数据。关键转折点。]

## 2. 疾病生物学

### 2.1 病理生理学
[关键生物学通路。已经验证的治疗靶点与新兴靶点。]

### 2.2 生物标志物
[诊断性、预后性、药效学生物标志物。FDA 资格认定与探索性标志物。
联系其临床试验用途。]

## 3. 标准治疗

### 3.1 获批疗法
[获批药物及其机制、批准年份和局限。
或：“目前没有获批用于该适应症的疗法。”]

### 3.2 治疗指南
[当前标准治疗算法。专科协会建议。]

### 3.3 未满足需求
[当前治疗无法解决的问题。疾病修饰缺口。
未被充分覆盖的患者人群。]

## 4. 临床终点与监管路径

### 4.1 已接受的终点
[FDA／EMA 接受的主要终点。替代终点与临床终点。
或：“该适应症不存在 FDA 指南。”]

### 4.2 监管先例
[关键批准、指南文件、咨询委员会讨论。]

### 4.3 试验设计参数
[典型试验规模、持续时间、对照组和单例患者成本。
基于 ClinicalTrials.gov 中的 3 期试验模式。]

## 5. 关键试验

### 5.1 里程碑式试验
[3–5 项最重要试验。每项包括 NCT ID、药物、结果和影响。]

### 5.2 重要失败案例
[重大失败和从机制层面总结的经验教训。]

## 附录：来源

[列出查阅的每一个来源，按来源类型使用粗体子标题分组。
编号在各组之间连续。标题作为超链接，条目末尾注明访问日期。]
```

## 操作

### 步骤 1：加载全部 waypoint 数据

- 读取 `waypoints/meta.json`；
- 读取 `waypoints/epidemiology.json`；
- 读取 `waypoints/biology_soc.json`；
- 读取 `waypoints/regulatory_trials.json`；
- 读取 `waypoints/sources_evaluated.json`；
- 如果写作过程中发现 waypoint 已有字段缺少某个值，可以进行一次有针对性的获取来补齐，并将新来源记录到 `sources_evaluated.json`。不得开启新的研究线程。

### 步骤 2：写入 `waypoints/indication_dossier_report.md`

**关键要求：** 写入 `<workdir>/waypoints/indication_dossier_report.md`，必须位于 `waypoints/` 内。

遵循上面的输出结构。关键指南：

**第 1–3 节：** 使用带行内引用的叙事性文字。对患病率、试验规模和批准年份等数字保持具体。覆盖状态应写入 `research_output.json`，而不是正文。在报告中只说明哪些内容部分覆盖或缺失，绝不把章节标记为“已覆盖”。

**第 4 节：** 混合使用叙事文字和结构化数据。适当使用表格比较终点和试验参数。

**第 5 节：** 为每项试验使用结构化条目，并将其与未来试验设计的经验联系起来。

**全文：** 从患者人群视角构建内容，遵循 `SKILL.md` 中的框架指南。

**图表：** 只有当图表能够展示文字无法表达的关系或分布时才生成。每张图使用一行图注注明数据来源。渲染后使用 `Read` 查看图片，并回答：它是否向读者传达了周围文字没有表达的信息？标题、带单位的坐标轴和图例是否全部存在且清晰可读？坐标轴刻度和图表类型是否与数据匹配，例如年份、计数和类别不能使用小数刻度，比例尺不能产生误导？如果任何答案是否定的，应删除图表，而不是重新生成。

### 步骤 3：写入 `waypoints/research_output.json`

```json
{
  "indication_name": "...",
  "parent_indication": "...",
  "meta": {...},
  "epidemiology": {...},
  "biology_soc": {...},
  "regulatory_trials": {...},
  "sources_evaluated": [...],
  "coverage_summary": {
    "epidemiology": {"covered": [...], "partial": [...], "missing": [...]},
    "biology_soc": {"covered": [...], "partial": [...], "missing": [...]},
    "regulatory_trials": {"covered": [...], "partial": [...], "missing": [...]}
  }
}
```

### 步骤 4：标记完成

**关键要求：** 必须先写入 `waypoints/indication_dossier_report.md`，然后才能执行此步骤。

写入 `waypoints/progress.json`：

```json
{
  "complete": true,
  "output_file": "indication_dossier_report.md",
  "current_phase": "synthesis"
}
```

## 指南

- 最终报告使用带行内引用的叙事性文字；
- 来源归因遵循 [references/06-writing-style.md](06-writing-style.md)；
- 明确说明缺口和数据质量限制；
- 对于新颖或非标准适应症，监管章节可能很短；这是正确结果，而不是必须填补的缺口。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
