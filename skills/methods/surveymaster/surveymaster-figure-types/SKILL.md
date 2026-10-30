---
name: surveymaster-figure-types
version: 0.2.0
description: Reference skill for academic figure type constraints and prompt templates. Loaded by write-section and finalize when generating or inserting figures to select the correct figure type and build a compliant prompt.
---

## Role

Passive reference only. This skill does not execute steps — it provides figure
type definitions, constraints, and prompt templates that the calling skill uses
to construct the `% FIGURE id=… prompt="…"` annotation and call the agent's
`image_gen` tool. The calling skill is responsible for saving the generated
bitmap to `$WORK/figures/<id>.png`.

## Global Figure Style Constraints

Apply the following global constraints to all figure prompts unless the calling
skill explicitly overrides them.

### 1. Overall Style

All generated figures should follow a formal, concise, academic visual style.
Prefer clean scientific illustration, vector-style graphics, simple geometric
composition, and clear visual hierarchy.

Avoid:
- photorealistic rendering
- cinematic lighting
- decorative backgrounds
- cartoon style
- excessive 3D effects
- unnecessary icons or ornamental elements
- visually crowded layouts

### 2. Color Palette

Use a clean, low-saturation academic color palette.
Maintain visual consistency across figures within the same paper while ensuring different categories remain easy to distinguish.

The source of truth is `writing_constraints.json` field
`figure_color_policy`:

- `low_saturation_color`: use low-saturation academic color. This is the
  default for biomedical, bioinformatics, materials, engineering, computer
  science, and other non-economics empirical-style surveys.
- `black_and_grayscale`: use black-and-white / grayscale academic figures.

Do not infer black-and-grayscale output from broad topic or subject keywords,
from the mere presence of economics-related files in context, or from generic
"formal academic" wording.

### Economics Empirical-Style Override

Apply this override only when `writing_constraints.json` explicitly has
`"figure_color_policy": "black_and_grayscale"`. Stage 1 may set that value after
the user chooses black-and-grayscale for an economics empirical-style survey, or
when the user/venue explicitly requests black-and-white figures.

Do not trigger this override merely because the survey uses the economics
empirical-style template. If an economics empirical-style survey has
`"figure_color_policy": "low_saturation_color"`, use the normal low-saturation
academic color palette instead.

When the override applies, use a plain economics-journal style:

- White background only.
- Black and grayscale lines, boxes, arrows, axes, and text.
- No gradients, no saturated colors, no decorative icons, no pictorial
  illustrations, no 3D effects, no shadows, no texture.
- Prefer simple rectangular boxes, thin arrows, braces, axes, and basic line
  charts or mechanism diagrams.
- Use restrained line weights and plenty of whitespace.
- The result should look like a clean black-and-white mechanism figure from an
  economics journal, not a colorful review infographic.

### 3. Cross-Figure Consistency

When generating multiple figures for the same paper, maintain consistency in:
- primary color tone
- line weight
- arrow style
- label style
- font style
- background color
- spacing and layout density
- overall academic visual language

Figures in the same paper should look like they belong to the same visual
system, even when they represent different figure types.

### 4. Text Density

Reduce text in generated images, but keep necessary labels or key phrases.
Avoid paragraph-style explanations inside the image.

Recommended:
- concise node labels
- short component names
- brief process-step labels
- no figure title inside the image

Avoid:
- long descriptive sentences
- dense annotations
- repeated explanatory text
- full paragraphs
- excessive labels on every element

## Figure Type Catalogue

### 1. `concept_illustration` — 概念示意图

**Use when:** explaining what a concept, structure, or material looks like;
introducing a domain object for the first time; visualizing internal composition
or spatial arrangement.

**Typical examples:** MXene 材料结构示意图；DNA 双螺旋示意图；神经元结构示意图

**Constraints:**
- Must show named structural components with labels
- No time axis; no comparative axis between multiple objects
- Background: white; layout: centered; style: scientific illustration
Use this type to show what an object, material, concept, or structure looks like.

**Layout guidance:**

- Prefer a centered composition.
- Place the main object in the visual center.
- Use callout labels only for key components.
- Use simplified scientific illustration rather than realistic rendering.
- Highlight the most important structure or component visually.
- Avoid showing process arrows unless the concept itself requires internal relationships.
- Avoid comparing multiple objects unless the figure is explicitly a comparison visual.

**Prompt guidance:**

- Specify the target object clearly.
- Specify the structural components that must be visible.
- Specify whether labels should be used.
- Keep labels short and limited to essential component names.
- Emphasize spatial structure, composition, and visual clarity.

**Prompt example — zh:**
```
生成一张学术论文级别的概念示意图，展示Ti3C2Tx MXene纳米片的结构。
图中以MXene二维层状结构为主体，清晰展示钛层、碳层以及表面终端基团（-O、-OH、-F）。
采用简洁的科学图示风格，不追求原子级精确绘制，而是突出结构组成和空间关系。
仅保留必要的结构标注，突出层状结构与表面官能团之间的关系。
白色背景，矢量图风格，低饱和度学术配色，视觉层次清晰，适用于材料科学综述论文。
避免写实风格、装饰元素、大段文字说明、密集标注和图片内部标题。
```

**Prompt example — en:**
```
Create a publication-quality scientific concept illustration showing the structure of a Ti3C2Tx MXene nanosheet.
The MXene sheet should be displayed at the center of the figure, clearly showing its layered two-dimensional structure. Highlight the titanium and carbon atomic layers as well as the surface termination groups (-O, -OH, -F).
Use a clean scientific illustration style with simplified structural representation rather than atomically precise rendering.
Include concise labels for the key structural components. Emphasize the relationship between the layered structure and surface functional groups.
White background, vector-style graphics, low-saturation academic color palette, clear visual hierarchy, suitable for a materials science review article.
Avoid photorealistic rendering, decorative elements, long text annotations, dense labels, and title text inside the figure.
```

---

### 2. `architecture_diagram` — 架构图

**Use when:** showing the high-level organisation of a system, framework, or
taxonomy; mapping categories, components, and their relationships at a
structural (non-temporal, non-sequential) level.

**Typical examples:** MXene 的类型和应用方向；深度学习架构分类图；多智能体系统结构

**Layout guidance:**

- Prefer hierarchical, modular, radial, or layered layouts.
- Group related modules visually.
- Use clear boundaries between categories.
- Use arrows or connectors only to show relationships, not process sequence.
- Avoid dense connection networks.
- Avoid crossing arrows where possible.
- Make the top-level structure understandable at a glance.

**Prompt guidance:**

- Specify the system, framework, or taxonomy name.
- List the major modules or categories.
- Describe the relationship between modules.
- Indicate whether the layout should be hierarchical, radial, layered, or modular.
- Keep module labels short.

**Constraints:**
- Must include named boxes/nodes and labelled connective arrows or groupings
- No sequential flow arrows that imply a process order
- May use hierarchical or radial layouts

**Prompt example — zh:**
```
生成一张学术论文级别的系统架构图，展示多Agent科研写作系统。
采用层级式布局，以Writing Agent作为中心模块。
Writing Agent负责协调以下子模块：
- Literature Review Agent
- Citation Agent
- Figure Generation Agent
- Quality Review Agent
使用清晰的连接关系展示模块之间的信息流和协作关系，并对相关功能进行合理分组。
白色背景，矢量图风格，低饱和度学术配色，模块化设计清晰，适用于综述论文。
避免流程图式布局、写实风格、过多文字、装饰性图标以及图片内部标题。
```

**Prompt example — en:**
```
Create a publication-quality scientific architecture diagram illustrating a multi-agent academic writing system.
Use a hierarchical layout centered around a Writing Agent.
The Writing Agent coordinates four specialized modules:
- Literature Review Agent
- Citation Agent
- Figure Generation Agent
- Quality Review Agent
Show the interaction and information flow between modules using clear connectors. Group related functions visually while keeping the architecture easy to understand at a glance.
White background, vector-style graphics, low-saturation academic color palette, clean modular design, suitable for a scientific review article.
Avoid sequential workflow layouts, photorealistic rendering, excessive text, decorative icons, and title text inside the figure.
```

---

### 3. `workflow_diagram` — 流程图

**Use when:** depicting a sequential process, pipeline, or protocol with
defined stages and decision points; PRISMA literature screening flows also
belong here.

**Typical examples:** MXene 合成过程流程图；文献筛选流程图（PRISMA）；实验处理流程

**Constraints:**
- Must use directional arrows to show sequence
- Include all major stages; label decision branches if present
- Avoid more than 8 steps to maintain readability

**Layout guidance:**

- Prefer a left-to-right layout for standard processes.
- Use top-to-bottom layout only when the process is long or hierarchical.
- Use directional arrows to indicate sequence.
- Keep the number of visible steps manageable, ideally no more than 8.
- Group related steps when the process is complex.
- Highlight major transformation points.
- Avoid crossing arrows.
- Use decision diamonds only when actual decision branches exist.

**Prompt guidance:**

- Specify the process name.
- Provide the ordered step list.
- Identify key transformation stages.
- Mention whether the output should emphasize mechanism, procedure, or final product.
- Keep step labels short.

**Prompt example — zh:**
```
生成一张学术论文级别的流程图，展示MXene材料从MAX相到单层MXene纳米片的典型制备流程。
采用从左到右的流程布局，包含以下步骤：
1. MAX相前驱体
2. 选择性刻蚀
3. 洗涤与中和
4. 插层与剥离
5. 单层MXene纳米片
使用有向箭头展示材料转化过程，重点突出MAX相、多层MXene和单层MXene之间的结构演变。
对白色背景、矢量图风格、低饱和度学术配色进行统一设计，适用于综述论文配图。
避免大段文字、实验室场景、装饰元素以及图片内部标题。
```

**Prompt example — en:**
```
Create a publication-quality scientific workflow diagram showing the synthesis process of MXene materials from MAX phases.
Use a left-to-right process layout with five stages:
1. MAX Phase
2. Selective Etching
3. Washing and Neutralization
4. Delamination
5. Single-Layer MXene
Use directional arrows to show material transformation. Visually emphasize the structural evolution from MAX phase to multilayer MXene and finally to single-layer MXene nanosheets.
Group related processing stages and keep the workflow easy to follow.
White background, vector-style graphics, low-saturation academic color palette, suitable for a Nature Reviews style figure.
Avoid excessive text, photorealistic laboratory scenes, decorative elements, and title text inside the figure.
```

---

### 4. `comparison_visual` — 对比图

**Use when:** Use this type to visually compare a small number of entities, usually two, across a limited number of conceptual dimensions.

**Typical examples:** MXene 与石墨烯的对比；不同算法在精度-速度上的对比；有无预训练的效果对比

**Layout guidance:**

- Prefer side-by-side layout.
- Use two-column or split-panel structure for two entities.
- Use simple visual markers, icons, or blocks to show differences.
- Keep comparison dimensions limited, usually 2–3.
- Use visually distinguishable colors for compared entities.
- Avoid presenting detailed data, metrics, units, or benchmark results.
- If there are more than 2 entities, more than 3 dimensions, or specific numerical indicators, use a table instead.

**Prompt guidance:**

- Specify the compared entities.
- Specify the comparison dimensions.
- Describe the intended contrast.
- Avoid asking the model to fabricate quantitative values.
- Keep labels concise and conceptual.

**Constraints:**
- Must show at least two distinct entities being compared
- Label each entity and each comparison dimension explicitly
- Do not use quantitative axes with fabricated data points

**Prompt example — zh:**
```
生成一张学术论文级别的对比图，对比MXene与石墨烯两种二维材料。
采用左右并排布局。
从以下三个维度进行对比：
- 电导率
- 表面功能化能力
- 储能潜力
使用结构示意图和简洁视觉符号表达差异，而非具体数值。
确保读者能够快速理解两种材料的主要区别，同时保持统一的学术视觉风格。
白色背景，矢量图风格，低饱和度学术配色，适用于综述论文。
避免定量图表、虚构数据、过多文字、写实风格以及图片内部标题。
```

**Prompt example — en:**
```
Create a publication-quality scientific comparison visual comparing MXene and graphene.
Use a side-by-side layout.
Compare the two materials across three dimensions:
- Electrical conductivity
- Surface functionalization
- Energy storage capability
Use simplified structural illustrations and concise visual indicators rather than numerical values.
Ensure that differences are immediately recognizable while maintaining a consistent visual style.
White background, vector-style graphics, low-saturation academic color palette, suitable for a review article.
Avoid quantitative charts, fabricated metrics, excessive labels, photorealistic rendering, and title text inside the figure.
```

---

### 5. `timeline_visual` — 时间线图

**Use when:** tracing the historical development or evolution of a technology,
field, or method along a time axis.

**Typical examples:** MXene 合成技术演进路径；Transformer 模型发展历程；法规演进时间线

**Constraints:**
- Must include a horizontal (or vertical) time axis with labeled years or periods
- Each milestone must be labeled with a brief event name
- Avoid fabricating specific years; use only years mentioned or implied in the survey text

**Layout guidance:**

- Prefer horizontal timeline layout.
- Use vertical timeline only when there are many milestones or limited width.
- Place years or periods in chronological order.
- Keep milestone labels short.
- Highlight major breakthroughs or turning points.
- Avoid fabricating years or events.
- Use only dates and milestones supported by the survey content.

**Prompt guidance:**

- Specify the field or technology.
- Provide the start year, end year, and milestone list.
- Keep each milestone concise.
- Make the chronological order visually obvious.
- Avoid overloading the timeline with too many events.

**Prompt example — zh:**
```
生成一张学术论文级别的时间线图，展示2011年至2025年MXene领域的发展历程。
采用横向时间轴布局。
包含以下关键里程碑：
- 2011：首次报道MXene材料
- 2014：LiF/HCl温和刻蚀路线提出
- 2018：储能应用快速发展
- 2021：生物医学应用兴起
- 2025：规模化制备技术突破
重点突出领域发展的关键转折点，同时保持清晰的时间顺序。
白色背景，矢量图风格，低饱和度学术配色，适用于综述论文配图。
避免堆砌事件、密集文字、装饰元素、写实风格以及图片内部标题。
```

**Prompt example — en:**
```
Create a publication-quality scientific timeline visual showing the development of MXene research from 2011 to 2025.
Use a horizontal timeline.
Include major milestones:
- 2011: First MXene reported
- 2014: LiF/HCl etching route introduced
- 2018: Expansion into energy storage applications
- 2021: Biomedical applications emerge
- 2025: Large-scale manufacturing developments
Highlight major breakthroughs while maintaining a clean chronological structure.
White background, vector-style graphics, low-saturation academic color palette, suitable for a scientific review article.
Avoid excessive events, dense annotations, decorative elements, photorealistic rendering, and title text inside the figure.
```

---

## Type Selection Guide

When choosing a figure type for a given section, first identify the section's primary visualization intent. Select the figure type that best supports the section's `core_claim`, rather than selecting the most visually attractive type.

Apply the following decision order:

1. Does the content describe a **step-by-step process, method, protocol, pipeline, or transformation**?
   → `workflow_diagram`

2. Does the content describe **historical development, technical evolution, or milestones over time**?
   → `timeline_visual`

3. Does the content compare **two entities, concepts, methods, structures, or workflows** at a conceptual level?
   → `comparison_visual`

4. Does the content describe **how components, modules, categories, or layers are organized** in a non-sequential structure?
   → `architecture_diagram`

5. Does the content explain **what a concept, object, material, structure, or mechanism looks like or is made of**?
   → `concept_illustration`

### Disambiguation Rules

- If the section describes ordered stages, choose `workflow_diagram`, even if the stages also involve structural changes.
- If the section is organized around years, periods, generations, or historical milestones, choose `timeline_visual`.
- If the section explains a taxonomy, system structure, module relationship, or category map, choose `architecture_diagram`.
- If the section introduces a single object or concept and needs to show its internal composition, choose `concept_illustration`.

### Default Rule

When multiple figure types could apply, choose the type that best supports the section's `core_claim`.

When genuinely ambiguous, prefer:

`workflow_diagram` → `architecture_diagram` → `concept_illustration`

Do not default to `comparison_visual` or `timeline_visual` unless the section clearly requires comparison or chronological structure.

## Language Selection

Default to the **English** prompt template regardless of the survey language.
Switch to the zh template only when the user explicitly requests Chinese figure
labels in the current session (e.g. "图片用中文标注" / "use Chinese labels").

`language: zh` in `writing_constraints.json` alone does **NOT** trigger the zh
template — English is always the default because image generation models produce
significantly better results with English prompts and labels.

## Usage

Select the type using the guide above. Apply the language rule above to choose
zh or en template. Fill the matching template with content from the section's
`core_claim`, and embed the result as the `prompt` value in the
`% FIGURE id=… prompt="…"` comment. The type name itself does not appear in
LaTeX output.
