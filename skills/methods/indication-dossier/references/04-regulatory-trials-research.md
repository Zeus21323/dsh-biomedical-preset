# 阶段 4——监管与临床试验研究

**何时执行：** `waypoints/biology_soc.json` 已存在，而 `waypoints/regulatory_trials.json` 不存在时。

## 目标

了解应如何针对该适应症开展临床试验：监管机构接受哪些终点、哪些试验塑造了该领域，以及哪些试验失败。本阶段覆盖第 4 节“监管路径”和第 5 节“关键试验”。

## 操作

### 步骤 1：FDA／EMA 接受的终点

- 使用 `WebSearch site:fda.gov` 检索该适应症特有的指南文件，例如 `"FDA guidance" "[indication]" clinical trial endpoints`；
- 识别成功注册性试验中使用的主要终点；
- 区分临床终点、替代终点和患者报告结局（PRO）；
- 记录哪些终点“有合理可能预测临床获益”，即加速批准路径；
- 如果该适应症没有 FDA 指南，应记录这一点，因为这意味着它处于新的监管领域。

### 步骤 2：监管先例

- 使用 `WebSearch site:fda.gov` 检索与该适应症相关的批准资料包；
- 哪些终点促成了批准？哪些试验设计得到接受？
- 是否存在突破性疗法认定、快速通道或优先审评先例？
- 是否有相关咨询委员会讨论或完整回复函（Complete Response Letter）？

### 步骤 3：试验设计参数

- 使用 `clinical-trials` MCP 检索该适应症的 3 期试验，以识别模式：`search_trials(condition="[indication]", phase="Phase 3")`；
- 典型试验规模，即目标入组人数；
- 典型试验持续时间，即主要终点评估时间点；
- 常见对照组，例如安慰剂、阳性对照或标准治疗；
- 如果文献中提供相关数据，估计单例患者成本。

### 步骤 4：里程碑式试验

- 识别塑造当前标准治疗的 3–5 项最重要试验；
- 对每项试验记录 NCT ID、药物、申办方、阶段、关键结果和对临床实践的影响；
- 使用 `clinical-trials` MCP 和 `pubmed` MCP 检索这些试验；
- 对于该适应症中的活跃申办方，使用 `WebFetch` 获取其 `/investors/presentations` 或 `/pipeline` 页面，并提取近期会议材料；下载后使用 `Read` 查看图表，因为幻灯片以图为主。

### 步骤 5：重要失败案例

- 识别该适应症中重要的临床试验失败；
- 试验测试了什么机制或方法？为什么失败？
- 哪些经验教训可指导未来试验设计？
- 使用 `pubmed` MCP 检索失败方法的综述。

### 步骤 6：写入 `waypoints/regulatory_trials.json`

遵循 [references/waypoint-schemas.md](waypoint-schemas.md) 中的 schema，并包含 `trial_landscape` 计数。

## 指南

监管路径信息会随适应症成熟度产生巨大差异：

- 成熟领域，例如 IPF、MASH：存在详细 FDA 指南；
- 新兴领域，例如肌少症：正式指南有限或不存在；
- 全新领域，例如衰老：完全没有监管框架。

必须明确说明该适应症属于哪一类。

- 对里程碑试验，优先考虑改变临床实践的试验，而不只是最新试验；
- 对失败案例，重点关注机制层面的教训，而不只是“该药物没有效果”；
- 使用并行子代理：`WebSearch site:fda.gov` 负责指南和批准信息，`clinical-trials` MCP 负责试验模式，`pubmed` MCP 负责试验历史综述。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
