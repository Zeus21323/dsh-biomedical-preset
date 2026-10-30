---
name: image-painter
description: "当需要通过 SpeedAI 图像接口生成位图或参考现有图片修改位图时使用，包括照片、插画、产品图、网站图、游戏素材、PPT 图、论文图、流程图和信息图。不承诺像素级精确编辑；不要用于 SVG/HTML/CSS/canvas 等代码原生图形。"
---

# Image Painter Skill

用于在当前项目中生成 raster image。默认使用图像生成工具。

## 顶层规则

该技能仅有两种顶层运行模式：
- 默认内置工具模式（推荐）： 通过内置的图像生成工具完成常规图像生成与编辑。无需配置 api key。
- 回退 CLI 模式（仅显式请求）：通过 `scripts/image_gen.py` 命令行接口调用。仅在用户明确要求使用 CLI 路径时方可使用。需要提供 api key。
- 不要另写临时 API runner；默认走服务端工具，调试才走 bundled CLI。
- 支持模型：`gemini-nano-banana-2.1`、`gpt-image-2.5`、`gpt-image-2`、`gemini-3-pro-image`、`gemini-3-pro-image-preview`。实际调用前以当前工具的模型枚举为准；所选模型未开放时说明限制，不猜测标识或静默换模型。
- 默认模型使用 Nano Banana 2.1（`gemini-nano-banana-2.1`）。用户要求 GPT 系列但未指定版本时，优先使用 `gpt-image-2.5`；用户明确指定 `gpt-image-2` 或其他支持的模型时，保留该选择。
- 调用时显式传入选定的 `model`，避免直接 API 路由或旧服务端自身的默认值覆盖本 skill 的默认选择。
- 本 skill 主要处理生成新图、参考图辅助生成和服务端支持的 mask URL 编辑；不承诺像素级精确编辑。
- `image_gen` 当前参数为：
  - `prompt`: string，必填。
  - `model`: string，可选，支持上述五个模型；本 skill 默认显式传 `gemini-nano-banana-2.1`，GPT 系列未指定版本时传 `gpt-image-2.5`。
  - `size`: string，可选，默认 `16:9`。
  - `resolution`: string，可选，`1K`、`2K` 或 `4K`，默认 `1K`。
  - `image_urls`: list[string]，可选，HTTP(S) 参考图 URL。
  - `mask_url`: string，可选，HTTP(S) mask URL，仅用于 GPT 图像模型（`gpt-image-2.5` 或 `gpt-image-2`）。
  - `extra_payload`: object，可选，透传额外 provider 参数。
- 不要把 API key 写进 prompt、日志、请求参数或代码。

## 适用任务

- 生成网站、App、游戏、产品、封面、海报、插画、纹理、背景、mockup 等位图素材。
- 生成 PPT 图：章节封面、版式背景、配图、概念图、数据故事图、视觉隐喻图。
- 生成论文的图：方法总览、实验设置图、模型架构示意、结果解释图、teaser 图。
- 生成流程图：业务流程、系统流程、pipeline、agent graph、decision flow。
- 使用参考图 URL 辅助生成或修改位图，但输出仍视为新图，不做像素级局部保留承诺。

## 不适用任务

- 用户需要可编辑 SVG、Mermaid、PPT shape、HTML/CSS/canvas、icon font 或代码原生图形。
- 用户只需要小幅修改已有 SVG/vector/logo 系统。
- 用户要求精确保留局部像素、抠图、透明背景编辑等当前服务端工具不承诺稳定支持的编辑任务。

## 工作流

1. 判断是否确实需要 raster image；如果代码原生图形更合适，不使用本 skill。
2. 根据用户的描述及其提供的图片、文件或其他参考信息理解任务。只有缺失信息会明显改变成品方向或造成大量返工时，才针对关键分歧提问；不要把未经确认的推测当作要求，也不要自行作出重大的、未明确的改变。其余细节可作合理假设并继续。
3. 按任务写 prompt：从零生成时可按需整理主体、构图、风格、文字和约束；参考图修改时优先写清“改动什么、哪些保持不变”。下面的 use case 和模板是可选提示，不是每次调用必须填写的表单或接口字段。
4. 用中文或中英混合清楚表达要求；模型、尺寸、分辨率和参考图 URL 放在工具参数中。调用前检查 prompt 是否冗长，按“Prompt 长度预检与过长错误处理”精简重复或无关内容。
5. 调用服务端 `image_gen` 工具提交异步任务，读取 `data.result` / `data.task_id` 作为任务 ID。
6. 通过 `get_tool_task_result` 工具轮询，直到 `status` 为 `succeeded` 或 `failed`。若明确报 prompt/input/context 过长，精简后创建新任务，禁止原样重试。
7. 成功后读取 `result.url` 并展示图片，报告模型和关键 prompt。此工具只返回图片 URL，不会核对画面内容；仅说明实际验证过的内容，不要把生成成功说成主体、文字或构图已经验收。

## Prompt 长度预检与过长错误处理（强制）

- 每次调用 `image_gen` 前先检查 prompt，不得把用户长文、检索结果、PPT 大纲、论文段落或内部分析直接整段拼入图像 prompt。
- prompt 出现多个长段落、重复表达同一画面、堆叠大量风格形容词、复制原始材料，或整体明显超过约 `2000` 个字符时，视为过长风险，必须在首次调用前自行精简。不要等服务端返回长度错误后才处理。
- 内容复杂的从零生成请求可参考约 `500-1500` 个字符，用紧凑表达保留核心请求、主体、构图、风格、必须文字和硬约束；简短的修改请求可远短于此，不要为了达到长度或填满模板而补充背景。复杂流程图或论文图可以适度增加，但仍须先去重和摘要。
- 主动精简时，将背景资料提炼成画面结论或元素关系，不保留解释过程；合并同义风格词和重复限制，每类要求只表达一次。
- 如果 prompt 因用户要求逐字呈现的文本而超过建议长度，不得静默截断或改写该文本；应建议缩短文本、拆分图片，或改用更适合长文本的代码原生图形。

- 仅当错误信息明确包含 prompt/input/context 过长含义时触发，例如 `prompt too long`、`input too long`、`maximum context length`、`context_length_exceeded`、`max input tokens`、`token limit exceeded`、`提示词过长`、`输入过长` 或 `超出上下文长度`。
- 同时检查首次 `image_gen` 调用的错误响应和异步任务 `status=failed` 时的 `error` 字段；不要只检查其中一个阶段。
- 触发后先构造精简版 prompt，再创建一个新的生成任务。禁止把完全相同的 prompt 原样重发，也不要仅通过换模型或提高超时时间规避长度错误。
- 第一轮精简到原 prompt 的约 `40%-60%`。删除原始资料全文、长篇背景解释、推理过程、示例堆叠、重复约束、同义风格形容词和与画面无关的 `Avoid` 项。
- 必须保留：核心画面请求、主体与关键布局、目标比例、用户要求逐字出现的短文本、不可违反的限制和最重要的避免项。模型、尺寸、分辨率和参考图 URL 应放在工具参数中，不要在 prompt 内重复。
- 如果精简后仍然触发同类长度错误，再压缩一次，只保留“核心请求 + 构图 + 必须文字 + 硬约束”。同一图片最多进行两次长度精简重试。
- 两次精简后仍失败，停止重试并向用户说明 prompt 长度限制。若用户要求逐字生成的文本本身过长，不得静默截断或改写；应说明该文本需要缩短或拆分成多张图。
- 不要把鉴权、安全限制、用户硬性要求或必须逐字出现的短文本当作普通冗余内容删除。

## Use case 分类

从零生成新图时，可参考这些 slug 判断用途；不要求把 slug 写进 prompt：

- `photorealistic-natural`：真实照片、自然场景、生活方式图。
- `product-mockup`：产品、包装、商品、周边图。
- `ui-mockup`：App/Web 界面 mockup 或线框图。
- `infographic-diagram`：信息图、解释性图表。
- `ppt-visual`：PPT 封面图、章节图、配图、版式背景、演示用概念视觉。
- `paper-figure`：论文方法图、模型架构图、实验图、teaser figure。
- `flowchart-diagram`：流程图、pipeline、系统流程、决策图。
- `logo-brand`：logo/品牌探索，输出是位图草案，不承诺可编辑 vector。
- `illustration-story`：叙事插画、漫画、儿童书风格。
- `stylized-concept`：风格化概念图、3D/stylized render。
- `historical-scene`：历史场景、时代风格图。

## Prompt 模板

仅在从零生成时需要梳理较多要求，可参考以下结构；不必逐项填写，也不要求保留英文标签。工具接收的是普通 `prompt` 字符串：

```text
Use case: <taxonomy slug>
Asset type: <用途和落点>
Primary request: <用户的核心要求>
Reference images: <参考图的作用，URL 放在 image_urls 参数中>
Scene/backdrop: <环境和背景>
Subject: <主体>
Style/medium: <photo/illustration/3D/diagram/etc>
Composition/framing: <画幅、视角、元素布局>
Lighting/mood: <光照和情绪>
Color palette: <颜色>
Text (verbatim): "<必须出现的文字>"
Constraints: <必须保留、必须包含>
Avoid: <不要出现的内容>
```

对参考图作修改时，优先简短描述改动和保留项，例如：“将参考图左上角的蓝色圆形改为绿色，其他布局和文字尽量保持不变。”不要为局部修改重新描述整张图；生成模型不承诺像素级保留，要求精确局部不变的任务不适用本 skill。

对 PPT 图、论文的图、流程图，要特别写清：
- 目标画幅，例如 `16:9`、`4:3`、`1:1`。
- 元素层级和布局关系。
- 文本尽量短；关键文字需要逐字 quoted。
- 生成 PPT 页面预览图时，画面必须只有 slide/page 内容本身；`Avoid` 中明确排除 Microsoft PowerPoint、WPS、Keynote、浏览器或操作系统窗口的菜单栏、工具栏、标题栏、状态栏、缩略图侧栏和应用边框。
- 如果需要后续可编辑，优先建议用 PPT/SVG/Mermaid/native shapes，而不是生成位图。

## 服务端工具用法

直接路由：

```json
POST /v1/research/tools/image_gen
{
  "username": "test_user",
  "prompt": "Use case: ppt-visual\nPrimary request: A clean PPT title visual about autonomous research agents\nConstraints: no watermark, no logos\nAvoid: Microsoft PowerPoint menus, WPS/Keynote/browser chrome, window title bars, toolbars, thumbnail sidebars",
  "model": "gemini-nano-banana-2.1",
  "size": "16:9",
  "resolution": "1K"
}
```

Generic tool call：

```json
POST /v1/research/tools/call
{
  "username": "test_user",
  "tool_name": "image_gen",
  "arguments": {
    "prompt": "Use case: paper-figure\nPrimary request: Create a paper method overview figure matching the reference color tone",
    "model": "gemini-nano-banana-2.1",
    "size": "16:9",
    "image_urls": ["https://example.com/reference.png"],
    "extra_payload": {
      "response_format": "url"
    }
  }
}
```

`image_gen` 返回的是任务 ID，不是图片 URL：

```json
{
  "code": 200,
  "data": {
    "tool_name": "image_gen",
    "result": "task-id",
    "task_id": "task-id",
    "status": "queued"
  }
}
```

随后通过 generic tool call 轮询：

```json
POST /v1/research/tools/call
{
  "username": "test_user",
  "tool_name": "get_tool_task_result",
  "arguments": {
    "task_id": "task-id"
  }
}
```

轮询返回：

```json
{
  "code": 200,
  "data": {
    "tool_name": "get_tool_task_result",
    "result": {
      "status": "succeeded",
      "url": "https://..."
    }
  }
}
```

轮询约定：

- `status=queued` 或 `running`：等待 30 秒后继续查询；服务端也会对未完成任务强制等待后再返回。
- 轮询期间不要每次都向用户输出“还在生成”“继续等待”等中间状态；图像生成可能很慢，耐心在后台轮询即可。
- `status=succeeded`：使用 `url` 作为最终图片 URL。
- `status=failed`：读取 `error`；若属于 prompt 过长，按强制精简规则重新创建任务，否则向用户说明失败原因。不要把 task_id 当图片 URL。

常用工具参数：

- `username`: 必填，用于鉴权和计费。
- `prompt`: 必填，完整图像生成提示词。
- `model`: 本 skill 默认 `gemini-nano-banana-2.1`；GPT 系列优先 `gpt-image-2.5`，明确指定时仍可使用 `gpt-image-2`；也支持显式选择 `gemini-3-pro-image` 或 `gemini-3-pro-image-preview`。
- `size`: 默认 `16:9`，也可传接口支持的尺寸/比例。
- `resolution`: `1K`、`2K` 或 `4K`，默认 `1K`。
- `image_urls`: HTTP(S) 参考图 URL 列表。
- `mask_url`: HTTP(S) mask URL，仅用于 GPT 图像模型（`gpt-image-2.5` 或 `gpt-image-2`）。
- `extra_payload`: 透传额外 API 参数，常用于 Gemini 图像模型。

## CLI 调试模式

仅当用户明确要求本地脚本调试时，使用：

```bash
export SPEEDAI_API_KEY="sk-..."
python3 skills/image-painter/scripts/image_gen.py generate \
  --prompt "A clean PPT title visual about autonomous research agents" \
  --model gemini-nano-banana-2.1 \
  --size 16:9 \
  --resolution 1K \
  --out output/image_painter/research-agent-title.png
```

CLI 省略 `--model` 时同样默认 Nano Banana 2.1。使用 GPT 系列时优先指定 `--model gpt-image-2.5`；用户明确要求旧版时才指定 `--model gpt-image-2`。

## 输出约定

- 临时文件放 `temp/image_painter/`。
- 服务端 `image_gen` 默认返回 task_id；必须通过 `get_tool_task_result` 获取最终 SpeedAPI 图片 URL。
- 获取图片 URL 只代表生成任务完成；服务端不提供视觉核对结果。不要声称已检查中文字、构图或画质，除非另有可用能力且确实完成了检查。
- CLI 调试输出默认放 `output/image_painter/` 或用户指定路径。
- 不覆盖已有文件，除非用户明确要求；需要覆盖时传 `--force`。
- 远程服务获得的url渲染成图片呈现给用户，而不只是给一个url。
