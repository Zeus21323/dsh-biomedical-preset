#!/usr/bin/env python3
"""Build and validate a Simplified-Chinese Gemini slide-image prompt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict


PROMPT_TEMPLATE = """你是一名资深 PPT 版面设计师。请直接生成一张可放入演示文稿的 16:9 横版整页幻灯片图片。

【输出语言硬约束】
画面中所有可见文字必须使用简体中文。输入中如有英文说明，先理解其含义，再改写成简体中文后排版；不要照抄英文标题、英文句子、英文项目符号或英文段落。只有无法翻译的产品名、品牌名、模型名、标准缩写和技术专有名词可以保留英文，并且要与中文解释共同出现。

【本页标题】
{slide_title}

【本页要传达的核心结论】
{slide_brief}

【证据与内容要点】
{key_evidence}

【整套 PPT 的颜色与设计方向】
{writer_prompt}

【版式要求】
根据本页内容选择最合适的版式，例如双栏对比、三栏并列、时间线、流程图、数据可视化、大图配短文、居中引文或自由编排。标题、正文和强调信息层级分明。用图表、图标、色块、线条或模块化区域表达信息，不要堆砌长段文字，也不要所有页面重复使用同一种卡片网格。

【画面要求】
严格使用 16:9 横版，没有白边、相框、设备外壳、纸张拟物或水印。配色只使用给定方案中的主色和强调色。使用思源黑体或苹方；专有产品名称和品牌可保留英文，但解释、结论、标签和正文必须为简体中文。

【禁止】
禁止输出全英文页面。禁止英文标题、英文句子、英文项目符号和英文段落。禁止背景纹理、水彩光斑、粒子、无意义装饰、发光玻璃拟态、过度 3D、emoji、卡通插画、低清噪点、草书、艺术字和变形字体。
"""

FIELD_RULES = {
    "slide_title": {"min_cjk": 2, "min_ratio": 0.25},
    "slide_brief": {"min_cjk": 4, "min_ratio": 0.35},
    "key_evidence": {"min_cjk": 6, "min_ratio": 0.30},
    "writer_prompt": {"min_cjk": 4, "min_ratio": 0.20},
}

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
LONG_ENGLISH_RUN_RE = re.compile(
    r"(?:\b[A-Za-z][A-Za-z0-9+./-]*\b[\s,:;()\-]+){5,}"
    r"\b[A-Za-z][A-Za-z0-9+./-]*\b"
)


def language_stats(text: str) -> Dict[str, Any]:
    cjk = len(CJK_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    lexical = cjk + latin
    return {
        "cjk_characters": cjk,
        "latin_characters": latin,
        "cjk_ratio": round(cjk / lexical, 4) if lexical else 0.0,
        "long_english_run": bool(LONG_ENGLISH_RUN_RE.search(text)),
    }


def validate_fields(fields: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    errors = []
    stats: Dict[str, Dict[str, Any]] = {}
    for name, rule in FIELD_RULES.items():
        value = fields.get(name, "").strip()
        if not value:
            errors.append(f"{name}: value is required")
            continue
        field_stats = language_stats(value)
        stats[name] = field_stats
        if field_stats["cjk_characters"] < rule["min_cjk"]:
            errors.append(
                f"{name}: requires at least {rule['min_cjk']} Chinese characters; "
                f"got {field_stats['cjk_characters']}"
            )
        if field_stats["cjk_ratio"] < rule["min_ratio"]:
            errors.append(
                f"{name}: Chinese-character ratio must be >= {rule['min_ratio']:.2f}; "
                f"got {field_stats['cjk_ratio']:.4f}"
            )
        if field_stats["long_english_run"]:
            errors.append(
                f"{name}: contains a long English sentence; translate the semantic content "
                "into Simplified Chinese before image generation"
            )

    if errors:
        raise ValueError("language_gate_failed:\n  - " + "\n  - ".join(errors))
    return stats


def build_prompt(fields: Dict[str, str]) -> Dict[str, Any]:
    normalized = {name: str(fields.get(name, "")).strip() for name in FIELD_RULES}
    stats = validate_fields(normalized)
    prompt = PROMPT_TEMPLATE.format(**normalized).strip() + "\n"
    return {
        "output_language": "zh-CN",
        "language_gate_passed": True,
        "fields": normalized,
        "field_language_stats": stats,
        "prompt": prompt,
        "prompt_language_stats": language_stats(prompt),
    }


def load_fields(args: argparse.Namespace) -> Dict[str, str]:
    if args.input_json:
        raw = sys.stdin.read() if args.input_json == "-" else Path(args.input_json).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("input JSON must be an object")
        return {name: str(data.get(name, "")) for name in FIELD_RULES}
    return {
        "slide_title": args.slide_title or "",
        "slide_brief": args.slide_brief or "",
        "key_evidence": args.key_evidence or "",
        "writer_prompt": args.writer_prompt or "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", help="JSON object path, or '-' to read stdin.")
    parser.add_argument("--slide-title")
    parser.add_argument("--slide-brief")
    parser.add_argument("--key-evidence")
    parser.add_argument("--writer-prompt")
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit prompt plus validation metadata as JSON instead of prompt text only.",
    )
    args = parser.parse_args()

    try:
        result = build_prompt(load_fields(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["prompt"], end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
