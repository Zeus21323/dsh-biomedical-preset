# 阶段 1——元数据初始化

**何时执行：** 第一个阶段，或 `waypoints/meta.json` 不存在时。

## 目标

解析适应症身份并收集基本背景。这是所有后续阶段的基础。

## 操作

### 步骤 1：设置

```bash
mkdir -p "<workdir>/waypoints"
```

### 步骤 2：解析适应症身份

通过 `WebSearch` 检索适应症名称并确认：

- 标准临床定义（如有）；
- ICD-10 编码（如适用）；
- 常用别名和替代名称；
- 它是公认的诊断实体，还是一种生物学状态／概念。

注意：有些适应症不是标准诊断，例如“免疫衰老”“衰老”“GLP-1 诱导的肌少症”；必须明确记录这一点。

### 步骤 3：建立层级

- 根据输入识别父级适应症，`additional_context` 中可能包含该信息；
- 理解它在临床分类体系中的位置，例如治疗领域、疾病类别；
- 如适用，记录跨领域分类。

### 步骤 4：快速扫描试验格局

- 使用 `clinical-trials` MCP 检索试验：`search_trials(condition="[indication name]")`；
- 记录试验总数、阶段分布和状态分布；
- 由此粗略判断该适应症的临床成熟度。

### 步骤 5：写入输出

- 将适应症身份写入 `waypoints/meta.json`；
- 初始化 `waypoints/sources_evaluated.json`。

## 指南

- 本阶段应在一次迭代中完成；
- 如果适应症没有 ICD 编码或标准定义，必须明确说明；这会影响所有下游章节，因为流行病学数据可能稀缺，监管路径也可能是全新的；
- 输出格式参见 [references/waypoint-schemas.md](waypoint-schemas.md) 中的 `meta.json` schema。

### 详细信息

#### 作者

Anthropic

#### 许可证

Apache-2.0
