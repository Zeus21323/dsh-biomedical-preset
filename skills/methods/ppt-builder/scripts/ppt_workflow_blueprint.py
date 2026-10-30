#!/usr/bin/env python3
"""Emit a graph_pptx_agent-style PPT workflow blueprint.

This helper is dependency-free and does not call the live Researcher service.
It gives future agents a deterministic skeleton for state fields, graph nodes,
transitions, and generation checkpoints.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List

from build_gemini_slide_prompt import FIELD_RULES, PROMPT_TEMPLATE


GRAPH_NODES = [
    "coordinator",
    "ask_user_for_details",
    "planner",
    "ask_user_for_plan",
    "research_supervisor",
    "web_searcher_node",
    "academic_searcher_node",
    "outliner",
    "ask_user_for_outline",
    "ask_user_for_ppt_template",
    "writer_supervisor",
    "ensure_writer_parallel_batch_balance",
    "writer_parallel_batch",
    "assemble_workspace_pptx",
    "ask_user_for_export",
    "export_editable_pptx",
    "ask_user_for_next_query",
    "edit",
]


GRAPH_EDGES = [
    ["coordinator", "ask_user_for_details"],
    ["coordinator", "ask_user_for_next_query"],
    ["ask_user_for_details", "planner"],
    ["planner", "ask_user_for_plan"],
    ["planner", "research_supervisor"],
    ["ask_user_for_plan", "research_supervisor"],
    ["research_supervisor", "web_searcher_node"],
    ["research_supervisor", "academic_searcher_node"],
    ["research_supervisor", "outliner"],
    ["web_searcher_node", "research_supervisor"],
    ["academic_searcher_node", "research_supervisor"],
    ["outliner", "ask_user_for_outline"],
    ["ask_user_for_ppt_template", "writer_supervisor"],
    ["writer_supervisor", "ensure_writer_parallel_batch_balance"],
    ["ensure_writer_parallel_batch_balance", "writer_parallel_batch"],
    ["writer_parallel_batch", "ensure_writer_parallel_batch_balance"],
    ["writer_parallel_batch", "assemble_workspace_pptx"],
    ["assemble_workspace_pptx", "ask_user_for_export"],
    ["export_editable_pptx", "ask_user_for_next_query"],
    ["ask_user_for_next_query", "edit"],
    ["edit", "ask_user_for_next_query"],
]


STATE_FIELDS = {
    "session": [
        "messages",
        "username",
        "project_id",
        "conversation_id",
        "session_id",
        "agent_params",
        "memory_inputs",
    ],
    "requirements": [
        "export_plans",
        "current_export_plan_index",
        "max_research_task_nums",
        "plans",
        "current_plan_index",
    ],
    "research": [
        "search_results",
        "url2cnt",
        "key2cnt",
        "reference_obj",
        "references",
        "simple_references",
    ],
    "writing": [
        "outline",
        "paper_tree",
        "paper_trees",
        "current_node",
        "writer_prompt",
        "outline_path",
        "outline_confirmation_requested",
        "outline_confirmed",
        "user_outline_suggestion",
        "export_datas",
    ],
    "ppt_versioning": [
        "ppt_presentation_id",
        "ppt_presentation_title",
        "ppt_slide_groups",
        "ppt_slide_versions",
    ],
    "resume": [
        "writer_parallel_cursor",
        "writer_parallel_batch_end",
        "pptx_billed_keys",
        "parallel_written",
    ],
    "delivery": [
        "workspace_output_dir",
        "workspace_presentation",
        "presentation_pptx_path",
        "preview_html_path",
        "export_requested",
        "export_confirmed",
        "editable_pptx_path",
    ],
    "language": [
        "output_language",
        "localized_slide_context",
        "image_prompt",
        "image_prompt_language_validated",
    ],
}


CONDITIONAL_EDGES = {
    "ask_user_for_outline": {
        "later_user_explicitly_approves": "ask_user_for_ppt_template",
        "later_user_requests_changes": "outliner",
        "no_user_response_yet": "interrupt_and_wait",
    },
    "ask_user_for_export": {
        "user_confirms_editable_pptx_export": "export_editable_pptx",
        "user_declines_or_requests_edits": "ask_user_for_next_query",
    },
}


def build_blueprint(args: argparse.Namespace) -> Dict[str, Any]:
    image_model = args.image_model or (
        "gpt-image-2.5" if args.mode == "image" else "gemini-nano-banana-2.1"
    )
    is_gpt_image = image_model.startswith("gpt-")
    generation_mode = args.mode if args.mode == "html" else ("image" if is_gpt_image else "banana")
    requirements: List[Dict[str, Any]] = [
        {
            "name": "Presentation title",
            "type": "single",
            "choice": [args.title or args.request[:40] or "Untitled presentation"],
        },
        {
            "name": "Page count",
            "type": "single",
            "choice": [f"{args.pages} pages"],
        },
        {
            "name": "Generation mode",
            "type": "single",
            "choice": [generation_mode],
        },
        {
            "name": "Visible slide language",
            "type": "single",
            "choice": ["Simplified Chinese (zh-CN)"],
        },
        {
            "name": "Other requirements",
            "type": "input",
            "choice": [args.request],
        },
    ]

    return {
        "source_workflow": "researcher/graph_pptx_agent",
        "request": args.request,
        "recommended_entrypoint": "coordinator",
        "outline_generator": {
            "node": "outliner",
            "model": "doubao2_0_pro_20260215",
            "outputs": ["outline", "paper_tree", "writer_prompt"],
            "output_language": "zh-CN",
            "translate_source_evidence_before_output": True,
        },
        "outline_approval_gate": {
            "save_script": "scripts/save_outline.py",
            "output": "ppt-output/{session_id}/outline.md",
            "ask_user_node": "ask_user_for_outline",
            "question": (
                "PPT 大纲已生成并保存到 ppt-output/{session_id}/outline.md。"
                "是否接受这个大纲并继续生成幻灯片？请回复“确认大纲”，"
                "或直接告诉我需要修改的内容。"
            ),
            "interrupt_after_question": True,
            "same_run_slide_generation_forbidden": True,
            "explicit_later_approval_required": True,
        },
        "generation_mode": generation_mode,
        "image_generator": (
            {
                "provider": "gpt" if is_gpt_image else "gemini",
                "model": image_model,
                "prompt_language": "zh-CN",
                "visible_text_language": "zh-CN",
                "prompt_builder": None if is_gpt_image else "scripts/build_gemini_slide_prompt.py",
                "prompt_template": PROMPT_TEMPLATE,
                "required_localized_fields": list(FIELD_RULES),
                "field_language_rules": FIELD_RULES,
                "pre_call_gate": "prompt builder must exit 0 and set image_prompt_language_validated=true",
                "post_generation_gate": "reject slides dominated by English visible text before assembly",
                "allow_english_only_for": [
                    "product names",
                    "brand names",
                    "model names",
                    "standard abbreviations",
                    "untranslatable technical proper nouns",
                ],
                "source_mode": "image" if is_gpt_image else "banana",
            }
            if generation_mode in {"banana", "image"}
            else None
        ),
        "batch_size": args.batch_size,
        "preview_layout": {
            "builder": "scripts/build_preview_html.py",
            "output": "ppt-output/{session_id}/preview.html",
            "sidebar_order": ["slide_title", "slide_thumbnail"],
            "title_thumbnail_gap_px": 6,
            "slide_item_gap_px": 28,
            "thumbnail_aspect_ratio": "16:9",
            "sidebar_default_width_px": 280,
            "sidebar_min_width_px": 220,
            "sidebar_max_width_px": 480,
            "sidebar_resizable": True,
            "resizer_width_px": 6,
            "sidebar_padding_left_px": 4,
            "sidebar_padding_right_px": 6,
            "slide_number_column_px": 20,
            "drag_handle_column_px": 12,
            "sidebar_utility_column_gap_px": 3,
        },
        "nodes": GRAPH_NODES,
        "edges": GRAPH_EDGES,
        "conditional_edges": CONDITIONAL_EDGES,
        "state_fields": STATE_FIELDS,
        "initial_state_patch": {
            "messages": [{"role": "user", "content": args.request}],
            "use_deep_research": not args.shallow_research,
            "use_web_search": not args.no_web,
            "use_academic_search": not args.no_academic,
            "max_research_task_nums": {
                "web_searcher": 0 if args.no_web else args.web_searches,
                "academic_searcher": 0 if args.no_academic else args.academic_searches,
            },
            "workspace_output_dir": "ppt-output/{session_id}",
            "workspace_presentation": {
                "local_path": "ppt-output/{session_id}/presentation.pptx",
                "editable": False,
                "source": "generated_full_slide_images",
            },
            "preview_html_path": "ppt-output/{session_id}/preview.html",
            "outline_path": "ppt-output/{session_id}/outline.md",
            "outline_confirmation_requested": False,
            "export_requested": False,
            "export_confirmed": False,
            "output_language": "zh-CN",
            "localized_slide_context": None,
            "image_prompt": None,
            "image_prompt_language_validated": False,
            "agent_params": {
                "auto": args.auto,
                "bs": args.batch_size,
                "max_page": f"{args.pages} pages",
                "ppt_generation_mode": generation_mode,
                "require_outline_confirmation": True,
                "output_language": "zh-CN",
                "require_simplified_chinese_slide_text": True,
                "allow_english_proper_nouns_only": True,
            },
            "outline_confirmed": False,
            "export_plans": [
                {
                    "requirements": requirements,
                    "max_length": args.pages,
                }
            ],
        },
        "checkpoints": [
            "requirements confirmed",
            "research plan produced",
            "research results collected",
            "outline tree and global color/design direction generated",
            "exact markdown outline saved to workspace_output_dir/outline.md",
            "complete outline shown through ask_user_for_outline; current run interrupted",
            "outline explicitly confirmed by user",
            "template resolved for image modes",
            "slide title, brief, evidence, and writer prompt localized into Simplified Chinese",
            "bundled prompt builder passes before every image-model call",
            "slides generated in resumable batches under workspace_output_dir",
            "visible slide language inspected; English-dominant slides rejected before assembly",
            "full-slide images assembled as workspace_presentation",
            "slide groups and versions recorded",
            "compact title-above-thumbnail preview.html generated from the slide manifest",
            "ask user whether to create a separate editable PPTX from workspace_presentation",
            "create the editable PPTX only after explicit confirmation",
            "edit loop available",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", help="User PPT request.")
    parser.add_argument("--title", default="", help="Optional presentation title.")
    parser.add_argument("--pages", type=int, default=8, help="Target page count.")
    parser.add_argument(
        "--mode",
        choices=("html", "image", "banana"),
        default="banana",
        help="Slide generation mode; banana defaults to Nano Banana 2.1, image to GPT Image 2.5.",
    )
    parser.add_argument(
        "--image-model",
        choices=("gemini-nano-banana-2.1", "gpt-image-2.5", "gpt-image-2", "gemini-3-pro-image", "gemini-3-pro-image-preview"),
        help="Explicit image model; otherwise banana uses Nano Banana 2.1 and image uses GPT Image 2.5.",
    )
    parser.add_argument("--batch-size", type=int, default=5, help="Parallel batch size.")
    parser.add_argument(
        "--web-searches",
        type=int,
        default=8,
        help="Maximum diversified web research tasks before outlining.",
    )
    parser.add_argument(
        "--academic-searches",
        type=int,
        default=3,
        help="Maximum academic research tasks before outlining.",
    )
    parser.add_argument("--auto", action="store_true", help="Use auto mode defaults.")
    parser.add_argument("--shallow-research", action="store_true", help="Reduce research depth.")
    parser.add_argument("--no-web", action="store_true", help="Disable web research.")
    parser.add_argument("--no-academic", action="store_true", help="Disable academic research.")
    args = parser.parse_args()

    if args.pages < 1:
        parser.error("--pages must be >= 1")
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    if args.web_searches < 0 or args.academic_searches < 0:
        parser.error("research task limits must be >= 0")

    print(json.dumps(build_blueprint(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
