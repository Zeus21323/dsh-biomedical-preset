#!/usr/bin/env python3
"""Build a compact static PPT preview page from a slide manifest."""

from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from urllib.parse import quote


def _slide_url(value: str, manifest_dir: Path, output_dir: Path) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value

    source = Path(value).expanduser()
    if not source.is_absolute():
        source = (manifest_dir / source).resolve()
    try:
        relative = os.path.relpath(source, output_dir)
        return quote(Path(relative).as_posix(), safe="/.:@")
    except ValueError:
        return source.as_uri()


def _normalize_slides(payload: object, manifest_dir: Path, output_dir: Path) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        raw_slides = payload.get("slides", [])
    elif isinstance(payload, list):
        raw_slides = payload
    else:
        raise ValueError("manifest must be a slide list or an object containing a 'slides' list")

    if not isinstance(raw_slides, list) or not raw_slides:
        raise ValueError("manifest contains no slides")

    slides: list[dict[str, str]] = []
    for index, raw in enumerate(raw_slides, start=1):
        if isinstance(raw, str):
            title, path = f"第 {index} 页", raw
        elif isinstance(raw, dict):
            title = str(raw.get("title") or raw.get("name") or f"第 {index} 页")
            path = str(
                raw.get("local_path")
                or raw.get("preview_path")
                or raw.get("path")
                or raw.get("url")
                or ""
            )
        else:
            raise ValueError(f"slide {index} must be a string or object")
        slides.append({"title": title, "url": _slide_url(path, manifest_dir, output_dir)})
    return slides


def _render(slides: list[dict[str, str]], deck_title: str) -> str:
    items: list[str] = []
    for index, slide in enumerate(slides, start=1):
        title = html.escape(slide["title"])
        url = html.escape(slide["url"], quote=True)
        thumb = (
            f'<img src="{url}" alt="{title} 缩略图" loading="lazy">'
            if url
            else '<span class="placeholder">▧&nbsp; 待生成</span>'
        )
        items.append(
            f"""
            <li class="slide-item{' is-active' if index == 1 else ''}">
              <span class="slide-number">{index}</span>
              <span class="drag-handle" aria-hidden="true">⠿</span>
              <button class="slide-select" type="button" data-index="{index - 1}">
                <span class="slide-title">{title}</span>
                <span class="thumbnail">{thumb}</span>
              </button>
            </li>"""
        )

    first = slides[0]
    first_title = html.escape(first["title"], quote=True)
    first_url = html.escape(first["url"], quote=True)
    main_content = (
        f'<img id="main-image" src="{first_url}" alt="{first_title}">'
        if first_url
        else '<div id="main-placeholder"><span>▧</span><p>当前页面尚未生成预览图。</p></div>'
    )
    slide_json = json.dumps(slides, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(deck_title)} - PPT 预览</title>
  <style>
    :root {{ --sidebar-width: 280px; color-scheme: light; font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif; }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; }}
    body {{ overflow: hidden; color: #435570; background: #eef3f9; }}
    .preview {{ display: grid; grid-template-columns: var(--sidebar-width) 6px minmax(0, 1fr); height: 100%; }}
    .sidebar {{ overflow-y: auto; padding: 16px 6px 24px 4px; background: #fff; }}
    .sidebar-resizer {{ position: relative; z-index: 2; width: 6px; cursor: col-resize; touch-action: none; background: #dbe3ee; transition: background .15s ease; }}
    .sidebar-resizer::after {{ position: absolute; top: 0; bottom: 0; left: -3px; width: 12px; content: ""; }}
    .sidebar-resizer:hover, .sidebar-resizer.is-dragging, .sidebar-resizer:focus-visible {{ background: #6975ff; outline: 0; }}
    .slide-list {{ display: flex; flex-direction: column; gap: 28px; margin: 0; padding: 0; list-style: none; }}
    .slide-item {{ display: grid; grid-template-columns: 20px 12px minmax(0, 1fr); align-items: start; column-gap: 3px; }}
    .slide-number {{ padding-top: 2px; color: #647892; font-size: 13px; line-height: 24px; text-align: center; }}
    .drag-handle {{ padding-top: 31px; color: #94a6bd; font-size: 15px; line-height: 1; text-align: center; }}
    .slide-select {{ display: flex; min-width: 0; margin: 0; padding: 0; flex-direction: column; gap: 6px; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }}
    .slide-title {{ display: block; width: 100%; overflow: hidden; color: #435570; font-size: 16px; line-height: 24px; text-overflow: ellipsis; white-space: nowrap; }}
    .thumbnail {{ position: relative; display: grid; width: 100%; aspect-ratio: 16 / 9; place-items: center; overflow: hidden; border: 1px solid #d8e1ec; border-radius: 7px; background: #f1f5fa; color: #93a7c1; }}
    .thumbnail img {{ display: block; width: 100%; height: 100%; object-fit: cover; }}
    .placeholder {{ font-size: 15px; }}
    .slide-item.is-active .thumbnail {{ border: 2px solid #626cff; box-shadow: 0 0 0 3px rgba(98, 108, 255, .2); }}
    .stage {{ display: grid; min-width: 0; padding: 36px; place-items: center; }}
    .canvas {{ display: grid; width: min(100%, calc((100vh - 72px) * 16 / 9)); aspect-ratio: 16 / 9; place-items: center; overflow: hidden; border-radius: 8px; background: #f3f6fa; box-shadow: 0 12px 36px rgba(55, 72, 96, .12); }}
    .canvas img {{ display: block; width: 100%; height: 100%; object-fit: contain; }}
    #main-placeholder {{ color: #879bb5; text-align: center; }}
    #main-placeholder span {{ font-size: 34px; }}
    #main-placeholder p {{ margin: 12px 0 0; font-size: 16px; }}
    @media (max-width: 760px) {{
      :root {{ --sidebar-width: 220px; }}
      .sidebar {{ padding-right: 4px; padding-left: 2px; }}
      .stage {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <main class="preview">
    <aside class="sidebar" aria-label="幻灯片列表"><ol class="slide-list">{''.join(items)}</ol></aside>
    <div class="sidebar-resizer" role="separator" aria-label="调整侧边栏宽度" aria-orientation="vertical" aria-valuemin="180" aria-valuemax="480" aria-valuenow="280" tabindex="0"></div>
    <section class="stage" aria-label="当前幻灯片"><div class="canvas">{main_content}</div></section>
  </main>
  <script>
    const slides = {slide_json};
    const canvas = document.querySelector('.canvas');
    const resizer = document.querySelector('.sidebar-resizer');
    const root = document.documentElement;
    const storageKey = 'ppt-preview-sidebar-width';

    function readSavedWidth() {{
      try {{ return Number(localStorage.getItem(storageKey)); }} catch {{ return 0; }}
    }}

    function saveWidth(width) {{
      try {{ localStorage.setItem(storageKey, String(width)); }} catch {{ /* File previews may disable storage. */ }}
    }}

    function widthBounds() {{
      const max = Math.max(180, Math.min(480, window.innerWidth - 280));
      return {{ min: Math.min(220, max), max }};
    }}

    function setSidebarWidth(value, persist = true) {{
      const bounds = widthBounds();
      const width = Math.round(Math.min(bounds.max, Math.max(bounds.min, value)));
      root.style.setProperty('--sidebar-width', `${{width}}px`);
      resizer.setAttribute('aria-valuemin', String(bounds.min));
      resizer.setAttribute('aria-valuemax', String(bounds.max));
      resizer.setAttribute('aria-valuenow', String(width));
      if (persist) saveWidth(width);
    }}

    const savedWidth = readSavedWidth();
    setSidebarWidth(Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : 280, false);
    resizer.addEventListener('pointerdown', (event) => {{
      resizer.classList.add('is-dragging');
      resizer.setPointerCapture(event.pointerId);
    }});
    resizer.addEventListener('pointermove', (event) => {{
      if (resizer.hasPointerCapture(event.pointerId)) setSidebarWidth(event.clientX);
    }});
    function finishResize(event) {{
      if (resizer.hasPointerCapture(event.pointerId)) resizer.releasePointerCapture(event.pointerId);
      resizer.classList.remove('is-dragging');
    }}
    resizer.addEventListener('pointerup', finishResize);
    resizer.addEventListener('pointercancel', finishResize);
    resizer.addEventListener('dblclick', () => setSidebarWidth(280));
    resizer.addEventListener('keydown', (event) => {{
      if (!['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) return;
      event.preventDefault();
      const current = Number(resizer.getAttribute('aria-valuenow')) || 280;
      setSidebarWidth(event.key === 'Home' ? 280 : current + (event.key === 'ArrowLeft' ? -12 : 12));
    }});
    window.addEventListener('resize', () => setSidebarWidth(Number(resizer.getAttribute('aria-valuenow')) || 280, false));

    document.querySelectorAll('.slide-select').forEach((button) => {{
      button.addEventListener('click', () => {{
        const index = Number(button.dataset.index);
        document.querySelectorAll('.slide-item').forEach((item, itemIndex) => item.classList.toggle('is-active', itemIndex === index));
        const slide = slides[index];
        canvas.replaceChildren();
        if (slide.url) {{
          const image = document.createElement('img');
          image.id = 'main-image';
          image.src = slide.url;
          image.alt = slide.title;
          canvas.append(image);
        }} else {{
          const placeholder = document.createElement('div');
          placeholder.id = 'main-placeholder';
          const icon = document.createElement('span');
          icon.textContent = '▧';
          const message = document.createElement('p');
          message.textContent = '当前页面尚未生成预览图。';
          placeholder.append(icon, message);
          canvas.append(placeholder);
        }}
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON manifest containing a slides list")
    parser.add_argument("--output", type=Path, default=Path("preview.html"), help="Output HTML path")
    parser.add_argument("--title", default="演示文稿", help="Browser page title")
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    output = args.output.resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    slides = _normalize_slides(payload, manifest.parent, output.parent)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render(slides, args.title), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
