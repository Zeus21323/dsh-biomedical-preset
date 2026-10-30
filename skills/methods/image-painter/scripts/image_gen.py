#!/usr/bin/env python3
"""SpeedAI image generation CLI for the image_painter skill."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, List, Optional

try:
    import requests
except ImportError as exc:  # pragma: no cover - import-time environment guard
    raise SystemExit(
        "Error: requests is not installed. Activate fzc_researcher and install requests."
    ) from exc


ENDPOINT = "https://api.claw.speedai.com/v1/images/generations"
DEFAULT_MODEL = "gemini-nano-banana-2.1"
DEFAULT_SIZE = "16:9"
DEFAULT_GPT_IMAGE_QUALITY = "medium"
DEFAULT_GPT_IMAGE_RESOLUTION = "2K"
DEFAULT_GEMINI_QUALITY = "2K"
DEFAULT_OUTPUT_PATH = "output/image_painter/output.png"
GPT_IMAGE_MODELS = ("gpt-image-2.5", "gpt-image-2")
GEMINI_IMAGE_MODELS = (DEFAULT_MODEL, "gemini-3-pro-image", "gemini-3-pro-image-preview")
ALLOWED_MODELS = {*GEMINI_IMAGE_MODELS, *GPT_IMAGE_MODELS}
ALLOWED_RESPONSE_FORMATS = {"url", "b64_json"}
FINAL_STATUSES = {"succeeded", "success", "completed"}


def _die(message: str, code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _read_prompt(prompt: Optional[str], prompt_file: Optional[str]) -> str:
    if prompt and prompt_file:
        _die("Use --prompt or --prompt-file, not both.")
    if prompt_file:
        path = Path(prompt_file)
        if not path.exists():
            _die(f"Prompt file not found: {path}")
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = (prompt or "").strip()
    if not value:
        _die("Missing prompt. Use --prompt or --prompt-file.")
    return value


def _read_api_key(cli_api_key: Optional[str], dry_run: bool) -> Optional[str]:
    key = (
        cli_api_key
        or os.getenv("SPEEDAI_API_KEY")
        or os.getenv("SPEEDAPI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if key:
        return key
    if dry_run:
        return None
    _die("Missing API key. Set SPEEDAI_API_KEY or pass --api-key.")
    return None


def _validate_model(model: str) -> None:
    if model not in ALLOWED_MODELS:
        allowed = ", ".join(sorted(ALLOWED_MODELS))
        _die(f"model must be one of: {allowed}")


def _validate_response_format(response_format: Optional[str]) -> None:
    if response_format is not None and response_format not in ALLOWED_RESPONSE_FORMATS:
        allowed = ", ".join(sorted(ALLOWED_RESPONSE_FORMATS))
        _die(f"response-format must be one of: {allowed}")


def _augment_prompt(args: argparse.Namespace, prompt: str) -> str:
    if not args.augment:
        return prompt

    sections: List[str] = []
    if args.use_case:
        sections.append(f"Use case: {args.use_case}")
    if args.asset_type:
        sections.append(f"Asset type: {args.asset_type}")
    sections.append(f"Primary request: {prompt}")
    if args.image_url:
        refs = "; ".join(args.image_url)
        sections.append(f"Reference images: {refs}")
    if args.scene:
        sections.append(f"Scene/backdrop: {args.scene}")
    if args.subject:
        sections.append(f"Subject: {args.subject}")
    if args.style:
        sections.append(f"Style/medium: {args.style}")
    if args.composition:
        sections.append(f"Composition/framing: {args.composition}")
    if args.lighting:
        sections.append(f"Lighting/mood: {args.lighting}")
    if args.palette:
        sections.append(f"Color palette: {args.palette}")
    if args.text:
        sections.append(f'Text (verbatim): "{args.text}"')
    if args.constraints:
        sections.append(f"Constraints: {args.constraints}")
    if args.negative:
        sections.append(f"Avoid: {args.negative}")
    return "\n".join(sections)


def _build_payload(args: argparse.Namespace, prompt: str) -> Dict[str, Any]:
    is_gpt_image = args.model in GPT_IMAGE_MODELS
    quality = args.quality
    if quality is None:
        quality = (
            DEFAULT_GPT_IMAGE_QUALITY
            if is_gpt_image
            else args.resolution or DEFAULT_GEMINI_QUALITY
        )

    payload: Dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "replyType": "json",
    }

    if args.size:
        payload["size"] = args.size
    if quality:
        payload["quality"] = quality

    if is_gpt_image:
        resolution = args.resolution or DEFAULT_GPT_IMAGE_RESOLUTION
        if resolution:
            payload["resolution"] = resolution
        if args.mask_url:
            payload["mask"] = args.mask_url

    if args.response_format:
        payload["response_format"] = args.response_format

    if args.n != 1:
        payload["n"] = args.n
    if args.image_url:
        payload["image_urls"] = args.image_url
    if args.extra:
        for item in args.extra:
            key, value = _parse_extra(item)
            payload[key] = value
    return {key: value for key, value in payload.items() if value is not None}


def _parse_extra(raw: str) -> tuple[str, Any]:
    if "=" not in raw:
        _die(f"--extra must be KEY=VALUE, got: {raw}")
    key, value = raw.split("=", 1)
    key = key.strip()
    if not key:
        _die(f"--extra has empty key: {raw}")
    value = value.strip()
    try:
        return key, json.loads(value)
    except json.JSONDecodeError:
        return key, value


def _extract_items(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("data", "results", "images"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _first_image_url(data: Dict[str, Any]) -> Optional[str]:
    for item in _extract_items(data):
        value = item.get("url") or item.get("image_url")
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, str) and value:
            return value
    for key in ("url", "image_url"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_b64_json(data: Dict[str, Any]) -> Optional[str]:
    for item in _extract_items(data):
        value = item.get("b64_json") or item.get("base64") or item.get("image")
        if isinstance(value, str) and value:
            return value
    for key in ("b64_json", "base64", "image"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _decode_base64_image(value: str) -> bytes:
    raw = value.strip()
    if "," in raw and raw.lower().startswith("data:image/"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _write_bytes(path: Path, data: bytes, force: bool) -> None:
    if path.exists() and not force:
        _die(f"Output already exists: {path} (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"Wrote {path}")


def _download_image(url: str, out_path: Path, *, timeout: int, force: bool) -> None:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    _write_bytes(out_path, response.content, force)


def _post_generation(payload: Dict[str, Any], api_key: str, timeout: int) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(ENDPOINT, headers=headers, json=payload, timeout=timeout)
    try:
        response.raise_for_status()
    except Exception as exc:
        body = getattr(response, "text", "")
        if body:
            print(f"Response body: {body[:2000]}", file=sys.stderr)
        raise exc
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Image generation returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Image generation returned unexpected JSON: {data!r}")
    return data


def _handle_response(data: Dict[str, Any], out_path: Path, args: argparse.Namespace) -> None:
    status = str(data.get("status", "")).lower()
    if status and status not in FINAL_STATUSES:
        raise RuntimeError(f"speedai image generation failed: {data.get('error') or data}")

    url = _first_image_url(data)
    if url:
        _download_image(url, out_path, timeout=args.download_timeout, force=args.force)
        return

    b64 = _first_b64_json(data)
    if b64:
        _write_bytes(out_path, _decode_base64_image(b64), args.force)
        return

    raise RuntimeError(f"Image generation response missing url/base64 image: {data}")


def _print_dry_run(payload: Dict[str, Any], out_path: Path) -> None:
    print(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "method": "POST",
                "output": str(out_path),
                "request": payload,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _run_generate(args: argparse.Namespace) -> int:
    _validate_model(args.model)
    _validate_response_format(args.response_format)
    if args.n < 1 or args.n > 10:
        _die("n must be between 1 and 10.")
    prompt = _augment_prompt(args, _read_prompt(args.prompt, args.prompt_file))
    payload = _build_payload(args, prompt)
    out_path = Path(args.out)

    api_key = _read_api_key(args.api_key, args.dry_run)
    if args.dry_run:
        _print_dry_run(payload, out_path)
        return 0

    assert api_key is not None
    data = _post_generation(payload, api_key, args.timeout)
    _handle_response(data, out_path, args)
    return 0


def _add_prompt_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--use-case")
    parser.add_argument("--asset-type")
    parser.add_argument("--scene")
    parser.add_argument("--subject")
    parser.add_argument("--style")
    parser.add_argument("--composition")
    parser.add_argument("--lighting")
    parser.add_argument("--palette")
    parser.add_argument("--text")
    parser.add_argument("--constraints")
    parser.add_argument("--negative")
    parser.add_argument("--no-augment", dest="augment", action="store_false")
    parser.set_defaults(augment=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images with SpeedAI /v1/images/generations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    gen = subparsers.add_parser("generate", help="generate a new image")
    _add_prompt_args(gen)
    gen.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "Image model (default: gemini-nano-banana-2.1). "
            "For GPT images prefer gpt-image-2.5; use gpt-image-2 when explicitly requested. "
            "Also supports gemini-3-pro-image and gemini-3-pro-image-preview."
        ),
    )
    gen.add_argument("--size", default=DEFAULT_SIZE)
    gen.add_argument("--quality")
    gen.add_argument("--resolution")
    gen.add_argument("--response-format")
    gen.add_argument("--image-url", action="append", default=[])
    gen.add_argument("--mask-url")
    gen.add_argument("--n", type=int, default=1)
    gen.add_argument("--out", default=DEFAULT_OUTPUT_PATH)
    gen.add_argument("--api-key")
    gen.add_argument("--timeout", type=int, default=300)
    gen.add_argument("--download-timeout", type=int, default=60)
    gen.add_argument("--extra", action="append", default=[])
    gen.add_argument("--force", action="store_true")
    gen.add_argument("--dry-run", action="store_true")
    gen.set_defaults(func=_run_generate)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
