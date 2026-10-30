# Image-first PPT production contract

Read this reference only when producing or revising slide images.

## Researcher-style template and page contract

The template choice happens **after the outline is accepted and before any page prompts or paid images**. Open the complete catalog directly through `ask_user`; the normal path has no preliminary catalog search, candidate ranking, or image-understanding calls. Example (adapt the question to the user's deck):

```json
{"questions":[{"question":"请选择这份知识图谱 PPT 的视觉模板","option_source":"ppt_templates"}]}
```

Do not include catalog templates in `options`. Omit it for the built-in “不用模板” and “使用我的参考图” alternatives, or pass at most two text-only alternatives. The tool fetches catalog pages internally, handles duplicate names, and presents a gallery with eight initial images, scrolling, search across the fetched catalog, load-more, and enlarged previews. Catalog browsing currently supports up to 1000 templates; a limit or service error must be explained, not treated as an empty catalog or permission to invent options. Only the chosen template ID and full image URL need enter the model context. Use the `template_id` and `image_url` in the returned selected-template result directly; do not infer the ID from a name or search again to recover it.

A style preference does not authorize narrowing the gallery. Do not select 3–6 candidates or inspect them with `understand_image` before showing it. `list_ppt_templates` and template comparison are optional only when the user explicitly asks the assistant to search, filter, or recommend templates. Do not duplicate gallery images in Markdown.

Record the chosen ID, full image URL, and source, or the user's actual image URL/local path. Wait for the answer; opening the gallery is not selecting a template. If “使用我的参考图” is chosen but no image was supplied, ask the user to attach it and pause before generation. If an exact template/reference image or no-template choice was already supplied, reuse it without another gallery. For no template, retain the shared deck-level visual direction. This step does not create a Researcher presentation or persist a backend template selection.

Researcher uses the selected template as the **first image reference on every initial page**. Only copy its palette, typographic feel, spacing, layout rhythm, and decoration language—not its sample text, page numbers, logos, or watermarks unless the user explicitly needs their own brand asset. For a page with source/content images supplied by the user, append only those relevant to that page after the style template and explain their semantic role in the prompt. If no template is selected, define one deck-wide palette/background/type hierarchy/density direction and repeat it consistently without inventing a template image. Do not place color names or hex values as visible slide copy.

Before constructing image prompts, prepare a concise on-screen `slide_detail` for each page from the approved outline and research. Keep the content layer separate from appearance, as Researcher's outliner/slide-details stages do. Use exact visible copy and data only where verified; never fabricate metrics to fill space.

- Cover: title, optional subtitle/slogan, user-supplied organization/author/date, strong topic visual; no content-page bullet list.
- Contents: actual section names in deck order, readable navigation; choose a layout that fits the count rather than inventing sections merely for symmetry.
- Substantive content: a clear conclusion plus, when evidence supports them, about 3–5 compact, specific units (facts, comparisons, cases, steps, implications), and the chart/diagram meaning. Favor Researcher's information-structure/atlas feel over a sparse concept poster. Cards/modules are useful for genuinely parallel units, but do not repeat the same grid on every page.
- Closing: a genuine takeaway, next steps or call to action when appropriate; do not invent contact details or generic “Thanks” copy as filler.

The `slide_detail` is content the image should communicate, not a raw full-deck outline or speaker note. Localize it to the user's chosen slide language before prompt construction. Never send raw English source paragraphs under a Chinese outer instruction; preserve English proper nouns only when appropriate.

## Page prompt contract

Compose the approved page scripts and prompts in the parent ReAct loop. Do not put a JSON-only `llm_task` or a Workflow node between the outline and `image_gen`. The legacy `build_gemini_slide_prompt.py` is a fixed Chinese template/validator from an older online Skill; the current Researcher banana branch does **not** run it. Do not force its output as the canonical image prompt. A deterministic language check may be useful for Chinese decks, but it cannot write the page script or judge the rendered image.

Every page prompt must contain:

- page index, page role, title, and the page-specific `slide_detail` with its visible text and evidence;
- a concrete composition suited to the role and semantics, such as hero visual, timeline, comparison, process, diagram, data view, modular atlas, or restrained editorial layout;
- the selected template as style reference, or the deck-wide palette, typography, spacing, graphic language, density, and continuity rules;
- exact output language and a requirement that visible copy be concise and legible;
- “16:9 full-bleed presentation slide, edge to edge”;
- prohibitions on white canvas borders, paper/device mockups, watermarks, emoji, meaningless decoration, fabricated charts, and unreadable artistic lettering.

The visual system should remain consistent, but compositions should vary with page semantics. Researcher's banana prompt is relatively short and emphasizes readable title/content hierarchy, modular regions for parallel points, highlighted facts, and an information-rich atlas feel. Its image2/GPT prompt uses more explicit layout and negative constraints. Match the **selected model's** direction instead of pasting the same exhaustive template into both. Give only the current page's `slide_detail` to the image model; the original user query, full outline, raw citations, speaker notes, and style-analysis hex codes are not on-screen copy.

## Direct asynchronous tool chain

After outline and template approval, reuse the user’s explicit model selection; otherwise ask with native `ask_user` before writing page prompts or submitting paid work. Put `Nano Banana 2.1（推荐）` first and map it to `gemini-nano-banana-2.1`; next offer `GPT Image 2.5` as `gpt-image-2.5`. Use Nano Banana 2.1 as the disclosed default only for a non-interactive run. An unversioned GPT request prefers Image 2.5. Preserve an explicit request for Image 2 (`gpt-image-2`) or another supported legacy model. Only offer identifiers present in the current `image_gen` enum; if unavailable, explain the limitation without guessing or silently substituting. Explicitly send the selected `model` on every call and reuse it for revisions. Costs come from current tool/backend metadata. Do not reuse historical fixed per-page prices.

1. Call `image_gen` once per page, preferably as parallel tool calls in the same assistant response. Use `size: "16:9"` and `resolution: "2K"` by default.
2. Put the one selected style-template image URL/local path first in `image_urls` on every initial page call. Append only that page's approved content assets; no template means no style image in the array. A template ID or path mentioned only in prompt prose is not a real reference image.
3. Match each returned task ID to its page via the original tool call, save it in the task record before waiting, and call `await_tool_tasks` once in page order. Its result array follows the supplied task-ID order, not page numbers inferred from completion order.
4. Persist every returned status, URL, and error. On timeout or interruption, read the record and continue waiting for the same unresolved IDs. Do not resubmit `image_gen`.
5. Pass successful URLs in page order to `assemble_image_pptx`. Use its generated `manifest.json` and per-page `local_path` values as the durable local source of truth.

If the provider limits a very large parallel tool-call batch, use the largest safe chunks, but never fall back to one model-mediated poll per task.

## Local task record and continuation

Use one deck-specific workspace directory and a separate `tasks-rNNN.json` file for each initial-generation or revision batch. This is an ordinary local artifact, not a new Workflow engine.

- Before submission, save the approved outline, selected template ID/source/image path or explicit no-template choice, one deck-level visual direction, each page's role and `slide_detail`, revision number, model/size/resolution, and planned page prompts.
- After submission and before `await_tool_tasks`, save each page's `index`, original `tool_call_id`, `prompt`, ordered `reference_images` (if any), `task_id`, and `status`.
- After every wait result, update `status`, `url`, and `error` while retaining already successful pages. After assembly, record its manifest path and latest ordered local slide paths.
- A revision record must also retain the prior ordered slide list and explicit target indices. Never overwrite the earlier revision's record.
- Record an `img2pptx` task as a separate editable-conversion operation with its task ID and source slide list before waiting.

The remote image task is asynchronous, but `await_tool_tasks` occupies the current tool call and may stop when the conversation is interrupted or the app exits. It does not schedule an automatic wake or recover itself after restart. On explicit continuation, read the latest record, keep completed results, and wait for the recorded unresolved IDs. If an accepted ID is missing locally, recover it from the original tool result before considering another paid submission.

## Review and revision

Deliver the assembled image-only PPTX before any editable conversion. It and its `slides/` directory must be visible in the workspace file area.

For a scoped edit, the original rendered page is mandatory visual input. Call `image_gen` only for requested page numbers with:

- `image_urls: ["<that page's current local_path>"]`;
- a narrowly scoped edit instruction;
- an explicit instruction to keep everything else unchanged.

Do not add a deck template as a second revision reference; the current page already carries the established visual system. Merge the replacement result into the prior ordered local-path list and reassemble. All non-target page paths must be reused unchanged.

## Quality and failure handling

Before delivery, verify slide count and ordering, that every image exists and decodes, and that no result is duplicated. Check visible text on every page as required by the final text check in `SKILL.md`. Review a compact montage or a few representative pages for obvious content and visual-system drift when visual inspection is available; do not create a separate vision-model turn per page by default. Show the assembled deck to the user before offering editable conversion.

Successful pages are durable assets. A remote failure or unknown task state must not cause a full-deck restart. Report the exact affected pages, retain every successful page, and ask before any potentially charged retry.
