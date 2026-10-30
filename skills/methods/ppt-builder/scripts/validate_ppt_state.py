#!/usr/bin/env python3
"""Validate graph_pptx_agent-style PPT session state JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

from build_gemini_slide_prompt import build_prompt


PHASE_REQUIREMENTS = {
    "outline": [
        "paper_tree",
        "outline",
        "writer_prompt",
        "workspace_output_dir",
        "outline_path",
    ],
    "generate": [
        "messages",
        "export_plans",
        "paper_tree",
        "outline",
        "writer_prompt",
        "workspace_output_dir",
        "outline_path",
        "outline_confirmation_requested",
        "outline_confirmed",
    ],
    "edit": [
        "messages",
        "ppt_presentation_id",
        "ppt_slide_groups",
        "ppt_slide_versions",
    ],
    "export": [
        "ppt_presentation_id",
        "ppt_slide_groups",
        "ppt_slide_versions",
    ],
    "image": [
        "output_language",
        "localized_slide_context",
        "image_prompt",
        "image_prompt_language_validated",
    ],
}


def _load_json(path: str) -> Dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("state JSON must be an object")
    return data


def _missing(state: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    missing = []
    for field in fields:
        if field not in state or state[field] in (None, "", []):
            missing.append(field)
    return missing


def validate(state: Dict[str, Any], phase: str) -> Dict[str, Any]:
    required = PHASE_REQUIREMENTS[phase]
    missing = _missing(state, required)
    warnings: List[str] = []

    if phase in {"outline", "generate"}:
        output_dir = str(state.get("workspace_output_dir") or "")
        outline_path_value = str(state.get("outline_path") or "")
        if output_dir and outline_path_value:
            expected_path = (Path(output_dir) / "outline.md").resolve()
            outline_path = Path(outline_path_value).resolve()
            if outline_path != expected_path:
                missing.append("outline_path=<workspace_output_dir>/outline.md")
            elif not outline_path.is_file():
                missing.append("saved outline.md exists")
            else:
                saved_outline = outline_path.read_text(encoding="utf-8").strip()
                state_outline = str(state.get("outline") or "").strip()
                if saved_outline != state_outline:
                    missing.append("saved outline.md exactly matches state outline")
                    warnings.append("save the complete revised outline before asking for approval")

    agent_params = state.get("agent_params") or {}
    mode = str(agent_params.get("ppt_generation_mode") or "").lower()
    if mode in {"image", "image2", "banana"} and not state.get("ppt_template_selection_done"):
        warnings.append("image mode state has not marked ppt_template_selection_done")

    if phase in {"edit", "export"}:
        groups = state.get("ppt_slide_groups") or []
        versions = state.get("ppt_slide_versions") or {}
        if isinstance(groups, list) and isinstance(versions, dict) and len(versions) < len(groups):
            warnings.append("ppt_slide_versions has fewer entries than ppt_slide_groups")

    if phase == "export":
        if state.get("export_requested") is not True:
            missing.append("export_requested=True")
        if state.get("export_confirmed") is not True:
            missing.append("export_confirmed=True")
            warnings.append("user has not explicitly approved editable PPTX export")

    if phase == "generate":
        if state.get("outline_confirmation_requested") is not True:
            missing.append("outline_confirmation_requested=True")
            warnings.append("the complete saved outline has not been presented through ask-user")
        if state.get("outline_confirmed") is not True:
            missing.append("outline_confirmed=True")
            warnings.append("outline_confirmed is not true; do not start slide writing yet")
        cursor = state.get("writer_parallel_cursor")
        if cursor is not None and not isinstance(cursor, int):
            warnings.append("writer_parallel_cursor should be an int when present")

    if phase == "image":
        if state.get("output_language") != "zh-CN":
            missing.append("output_language=zh-CN")
        if state.get("image_prompt_language_validated") is not True:
            missing.append("image_prompt_language_validated=True")

        context = state.get("localized_slide_context")
        if not isinstance(context, dict):
            missing.append("localized_slide_context object")
        else:
            try:
                expected_prompt = build_prompt(context)["prompt"].strip()
            except Exception as exc:
                missing.append("localized_slide_context passes Chinese language gate")
                warnings.append(str(exc))
            else:
                actual_prompt = str(state.get("image_prompt") or "").strip()
                if actual_prompt != expected_prompt:
                    missing.append("image_prompt equals bundled Chinese prompt-builder output")
                    warnings.append(
                        "do not call the image model with a hand-built prompt, raw user query, "
                        "untranslated outline, or untranslated research evidence"
                    )

    return {
        "ok": not missing,
        "phase": phase,
        "missing": list(dict.fromkeys(missing)),
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state_json", help="Path to state JSON, or '-' for stdin.")
    parser.add_argument("--phase", choices=sorted(PHASE_REQUIREMENTS), default="generate")
    args = parser.parse_args()

    try:
        state = _load_json(args.state_json)
        result = validate(state, args.phase)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
