---
name: ppt-builder
description: 对齐 researcher/graph_pptx_agent 的状态化 PPT/PPTX 生成流程，覆盖需求澄清、研究规划、outline 确认、简体中文生图语言门禁、批量生成、版本记录、编辑循环和导出。
metadata:
  version: "0.2.2"
---

# PPT Generator

Use the parent ReAct loop for the entire user-facing process. Do not start or resume a `researcher-ppt` workflow for ordinary PPT creation or revision. The only fixed production segment is the existing image-task tool chain:

```text
image_gen (submit all pages) -> await_tool_tasks (wait in Go) -> assemble_image_pptx
```

This keeps the Researcher sequence—requirements, research, outline approval, image-template selection, page writing, generation, review, edits—in the conversation while avoiding model-mediated polling. ReAct owns the decisions; do not recreate the old state graph.

Before producing or revising slide images, read [references/image_workflow.md](references/image_workflow.md) for the page-prompt and image-editing contract.

## ReAct-led preparation

1. Reuse information the user already supplied. Ask only for missing requirements that materially change the deck (audience, scenario, page count, language, depth, visual preference). Use native `ask_user` with AI-generated, topic-specific questions and choices; never use generic process labels such as only “确认/修改”.
2. Plan and perform research with normal ReAct tools in proportion to the topic's stakes and freshness. Discuss a proposed research scope when source choice or breadth materially matters. Keep a compact evidence trail for consequential claims.
3. Build and show a complete Researcher-style outline: one leaf per page, with distinct cover, optional contents, substantive content, and appropriate closing roles. Develop one deck-level visual direction, not a new palette per page. Save the exact shown outline in the deck workspace.
4. Ask whether the user accepts this particular outline and what should change. Treat asking as a pause, not approval; do not submit paid image tasks until a later affirmative answer, unless the user explicitly requested to skip outline review.
5. **After outline approval and before page writing, let the user browse the full template gallery.** Directly call native `ask_user` with a topic-specific `question` and `option_source: "ppt_templates"`. Omit `options` to use the built-in no-template and user-reference alternatives, or supply at most two text-only alternatives. Upstream reads the official and signed-in user's catalog, presents scrolling/search/load-more and enlarged previews, and returns the chosen `template_id` and full `image_url`. Do not call `list_ppt_templates`, search for style keywords, curate a 3–6-item shortlist, or call `understand_image` on candidate templates before opening this gallery. A visual preference such as “dark tech” is guidance for the deck, not a request to hide other templates. Only perform template filtering or comparison if the user explicitly asks the assistant to do that. Do not reproduce the catalog as Markdown or tool arguments. If the user already supplied an explicit valid reference image, selected an exact template, or declined templates, reuse that choice. Save the selected ID and full image URL/local path; this is a style reference, not a page-content source. If the gallery reports an error or the tool schema lacks `option_source`, explain the limitation and offer user-image/no-template choices; do not silently revert to the old shortlist flow. For the exact call and answer-handling contract, see [references/image_workflow.md](references/image_workflow.md).
6. Reuse an image model the user already explicitly selected for this deck. Otherwise, **after template selection and before page-prompt writing or paid generation, ask which image model to use.** Put `Nano Banana 2.1（推荐）` → `gemini-nano-banana-2.1` first, followed by `GPT Image 2.5` → `gpt-image-2.5`. Nano Banana 2.1 is the default for a non-interactive run; briefly disclose that assumption. If the user requests the GPT family without a version, prefer GPT Image 2.5. Retain `gpt-image-2`, `gemini-3-pro-image`, and `gemini-3-pro-image-preview` for explicit requests. Offer and submit only identifiers exposed by the current `image_gen` model enum. If a requested model is unavailable, explain the limitation and keep the choice open; never guess an identifier or silently substitute another model. Always pass the selected `model` explicitly and reuse it for the whole deck and revisions unless the user asks to switch.
7. Before generation, state the approved page count, selected template/no-template, chosen image model, and cost if current tool/backend metadata provides it. Do not quote stale fixed per-page prices or invent a price when metadata is unavailable.

Do not force these stages into JSON or a secondary workflow. Do not call `llm_task` merely to produce slide prompts. In the current ReAct turn, prepare a concise, page-specific on-screen content script from the outline and evidence, then compose its image prompt and pass it directly as an `image_gen` argument. Do not paste the whole outline, raw research snippets, or speaker notes into every page prompt. Tool arguments need not be repeated as prose in the transcript.

## Image production

**Deferred tools:** loading this skill activates `assemble_image_pptx` and the optional catalog-search tool `list_ppt_templates`. If assembly is unavailable, activate `assemble_image_pptx` through `find_tools`. Full-gallery selection uses `ask_user` with `option_source: "ppt_templates"` directly; it does not require `list_ppt_templates` or a discovery call. `image_gen` and `await_tool_tasks` are not deferred.

1. The local assembler accepts at most 60 slides per deck; settle a smaller deck or explicit split before paid generation if the outline exceeds that limit. Create one prompt per approved page using its page role, on-screen content script, and the selected template or shared visual direction. Keep Researcher's modular, information-rich "atlas" look for substantive pages without forcing cards onto every role. Save the outline, template choice, page scripts, and prompts in a deck-specific workspace directory before submission; use the task-record contract in the reference.
2. Submit the `image_gen` calls together in the same assistant tool-call batch when supported. Use the approved model, `size: "16:9"`, and `resolution: "2K"`. Put the **one selected template image first** in `image_urls` on every initial page call; add only page-relevant user content images after it. Pass a real URL/path, not a template ID or a prose mention. If no template was selected, do not add a fabricated reference image.
3. Before waiting, persist every returned `task_id` with its page index and prompt in the revision's task-record file. Map responses by tool-call identity, not completion order. Do not poll with `get_tool_task_result` after every page.
4. Call `await_tool_tasks` once with those recorded IDs in page order, then save all returned statuses, URLs, and errors back to the record. This is an in-process tool wait without extra LLM polling turns, not a detached background job or a restart-recovery service. On timeout or interruption, read the saved record and wait for the same unresolved IDs again; never resubmit charged generation merely because waiting stopped.
5. If every page succeeded, pass the ordered result URLs to `assemble_image_pptx`. This downloads the images into the current workspace, writes a manifest, and creates a local image-only PPTX visible in the file area.
6. If only some pages failed, preserve all successful results. Identify the failed page numbers and error. Do not retry a failed paid generation until the user explicitly approves the additional spend.

The assembled image-only PPTX is the default deliverable. Run the visible-text check below before providing its local path as a clickable file link, briefly summarizing what was produced, and using native `ask_user` to offer deck-specific choices such as keeping it, revising named pages, or requesting an editable conversion. Do not automatically call `img2pptx`.

## Page-scoped revision

Resolve the request to exact 1-based page numbers before generating. “首页” means page 1; “最后一页” means the final page in the latest manifest.

For each requested page only:

1. Use that page's current `local_path` from the latest `assemble_image_pptx` manifest as the sole `image_urls` reference.
2. Tell `image_gen` exactly what to change and explicitly preserve all unrequested text, facts, composition, positions, colors, typography, spacing, and decoration.
3. Create a new revision task record that retains the prior ordered slide list. Submit only target-page calls, save their IDs before waiting, await them once, replace only those positions, and call `assemble_image_pptx` again.

Never regenerate the whole deck for a page-scoped request. Keep earlier output directories so the user can compare or roll back.

## Editable conversion

Call `img2pptx` only after the user explicitly requests an editable deck. Pass the latest ordered local slide paths, save the returned task ID as an editable-conversion operation before waiting, then pass it to `await_tool_tasks`. Editable conversion is optional, paid, and may alter visual fidelity; it is not part of initial generation. Run the visible-text check below before presenting the converted file as editable.

## Final text check

After assembling or converting the finished deck, inspect every rendered slide against its approved page script and source material. Check visible titles, labels, numbers, units, scientific symbols, and Chinese characters for omissions, substitutions, gibberish, or duplicated text. For an editable PPTX, also read its text objects; passing the text-object check alone is insufficient because stray text can remain in images. Record affected page numbers and correct them before declaring the deck complete. Do not restart a paid image or conversion task without the user's approval.

## Recovery rules

- Explain tool errors in the current ReAct loop instead of ending at a workflow failure card.
- Invalid prompt or argument errors may be corrected before any accepted paid task and retried once.
- For an accepted task, unknown outcome, timeout, or remote failure, reuse the same task ID first. Never create a replacement paid task without clear evidence that it is necessary and user approval when another charge is possible.
- Preserve the approved outline, prompts, successful page URLs, and local manifests across recovery. Do not repeat the interview or redraw unaffected pages.
- If interruption happened before a returned task ID was saved, recover it from the original tool result. If acceptance cannot be determined, report the uncertainty instead of assuming no task was created. Local records enable explicit continuation; do not promise automatic completion notifications or automatic restart recovery.
