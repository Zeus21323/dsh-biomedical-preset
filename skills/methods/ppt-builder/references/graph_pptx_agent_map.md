> Historical architecture notes only. For current production, follow SKILL.md and image_workflow.md. The graph checkpoints, blueprint, mandatory prompt builder, and auto-mode approval rules below describe an older implementation and are not current execution instructions.

# graph_pptx_agent Map

Use this reference when aligning new PPT generation work with
`researcher/graph_pptx_agent`.

## Source Files

- `graph.py`: LangGraph node wiring and conditional transitions.
- `protocols.py`: shared state fields and limits.
- `nodes/coordinate.py`: requirement options, defaults, counters, initial state.
- `nodes/plan.py`: bounded web/academic research plan generation.
- `nodes/research.py`: research supervisor and search node routing.
- `nodes/write.py`: outline creation, color/design prompt, template selection, slide generation, batch resume, asset upload, version records.
- `nodes/edit.py`: edit intent analysis and page-level regeneration.
- `nodes/export.py`: legacy export notes and current export context.
- `utils.py`: frontend display tools, URL helpers, JSON parser, path helpers.
- `paper_utils.py`: outline/tree traversal helpers.

## Node Sequence

`coordinator` -> `ask_user_for_details` -> `planner` -> `ask_user_for_plan`
-> `research_supervisor` -> search nodes -> `outliner`
-> save `<workspace_output_dir>/outline.md` -> `ask_user_for_outline` -> [pause for user response] -> (`outliner` for revision or `ask_user_for_ppt_template` after explicit approval)
-> `writer_supervisor` -> `ensure_writer_parallel_batch_balance`
-> `writer_parallel_batch` -> `assemble_workspace_pptx` -> `ask_user_for_export` -> [pause for user response] -> (`export_editable_pptx` or `ask_user_for_next_query`) -> `edit`.

## Key Design Choices

- Requirements are structured before research.
- Research is bounded and typed; template search is not a research task.
- `outliner` generates the full deck outline and the deck-level `writer_prompt` color/design direction before page writing starts.
- Save the exact complete markdown outline as `<workspace_output_dir>/outline.md` before presenting it. Persist the path as `outline_path`.
- `ask_user_for_outline` is an interrupt checkpoint, not a pass-through node. Show the complete outline, ask whether the user accepts it, and end the current run. Only a later explicit affirmative reply may persist `outline_confirmed=True`; never bypass it in auto mode.
- One outline leaf equals one slide.
- Color/style direction is generated once and reused across slides.
- Slide generation is per-page, with read-only task state and merge-after-success.
- Batch generation is resumable by cursor and billed idempotently by batch key.
- HTML and image slides share a normalized `slide_asset` return shape.
- HTML uses separate cover, table-of-contents, and content prompts. The original HTML overflow detector exists but is currently commented out at the writer call site; enable it when implementation needs reliable layout validation.
- Image prompts use current-page context only and select among comparison, timeline, flow, data, hero-image, quote, and free layouts. They explicitly prohibit pure text paragraphs, device frames, noisy decoration, and template-content copying.
- The current legacy `banana` branch in `nodes/write.py` interpolates `user_query`, current-section content, extracted evidence, and `writer_prompt` directly into its image prompt. A Chinese outer instruction does not translate those fields, so English inputs can produce an English slide. Treat that branch as language-unsafe until the runtime localizes all visible copy and applies the same validation as `scripts/build_gemini_slide_prompt.py`; do not bypass the bundled builder merely because the provider is already Gemini.
- The source graph transitions straight from generation to the follow-up loop and its old exporter is disabled. This skill deliberately adds `assemble_workspace_pptx`, `ask_user_for_export`, and `export_editable_pptx`: first combine the generated images into a workspace image-based PPT, then pause, and build a separate editable PPTX only on later explicit user confirmation. The blueprint represents the editable conversion as conditional routing, never as a direct edge.
- Version records are created during generation, not only during export.
- Follow-up user messages enter an edit loop instead of starting a new deck by default.
