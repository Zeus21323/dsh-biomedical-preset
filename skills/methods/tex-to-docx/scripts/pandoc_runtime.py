#!/usr/bin/env python3
"""Resolve or install a verified Pandoc binary for tex-to-docx."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import requests


SKILL_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SKILL_DIR / "assets" / "pandoc_releases.json"


def cache_root() -> Path:
    explicit = os.environ.get("TEX_TO_DOCX_PANDOC_CACHE")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "tex-to-docx" / "pandoc"
    if platform.system().casefold() == "darwin":
        return Path.home() / "Library" / "Caches" / "tex-to-docx" / "pandoc"
    return Path.home() / ".cache" / "tex-to-docx" / "pandoc"


def platform_key() -> str:
    system = platform.system().casefold()
    machine = platform.machine().casefold()
    machine_aliases = {
        "aarch64": "arm64",
        "amd64": "x86_64",
        "x64": "x86_64",
    }
    machine = machine_aliases.get(machine, machine)
    if system not in {"darwin", "linux", "windows"}:
        raise RuntimeError(f"pandoc_platform_unsupported: {system}-{machine}")
    return f"{system}-{machine}"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def executable_name() -> str:
    return "pandoc.exe" if platform.system().casefold() == "windows" else "pandoc"


def probe_pandoc(candidate: str | Path) -> tuple[bool, str]:
    path = str(candidate)
    try:
        completed = subprocess.run(
            [path, "--version"], text=True, capture_output=True, check=False, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    output = (completed.stdout or completed.stderr).strip().splitlines()
    first_line = output[0] if output else "no version output"
    if completed.returncode != 0 or not first_line.casefold().startswith("pandoc "):
        return False, f"exit={completed.returncode}: {first_line}"
    return True, first_line


def _candidate_paths() -> Iterable[tuple[str, str]]:
    explicit = os.environ.get("PANDOC_PATH")
    if explicit:
        yield "PANDOC_PATH", explicit
    on_path = shutil.which("pandoc")
    if on_path:
        yield "PATH", on_path
    try:
        import pypandoc  # type: ignore

        yield "pypandoc", pypandoc.get_pandoc_path()
    except Exception:
        pass
    manifest = load_manifest()
    root = cache_root() / str(manifest["version"]) / platform_key()
    if root.is_dir():
        for path in sorted(root.rglob(executable_name())):
            if path.is_file():
                yield "tex-to-docx cache", str(path)


def resolve_pandoc() -> Path:
    failures: list[str] = []
    for source, candidate in _candidate_paths():
        ok, detail = probe_pandoc(candidate)
        if ok:
            return Path(candidate).expanduser().resolve()
        failures.append(f"{source}={candidate!r} ({detail})")
    suffix = "; rejected candidates: " + " | ".join(failures) if failures else ""
    raise RuntimeError(
        "dependency_not_found: no runnable native Pandoc was found. Run "
        "scripts/ensure_pandoc.py, or set PANDOC_PATH to a working executable" + suffix
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_destination(root: Path, member_name: str) -> Path:
    destination = (root / member_name).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"unsafe_archive_member: {member_name}") from exc
    return destination


def _extract_verified_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                target = _safe_destination(destination, info.filename)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                _safe_destination(destination, member.name)
                if member.issym() or member.islnk():
                    raise RuntimeError(f"archive_links_not_allowed: {member.name}")
            bundle.extractall(destination)
    else:
        raise RuntimeError(f"unsupported_pandoc_archive: {archive.name}")


def _environment_mirrors() -> list[str]:
    raw = os.environ.get("TEX_TO_DOCX_PANDOC_MIRRORS", "")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _render_url(template: str, version: str, asset: str) -> str:
    if "{asset}" not in template:
        template = template.rstrip("/") + "/{version}/{asset}"
    return template.format(version=version, asset=asset)


def _download(url: str, output: Path, timeout: float) -> None:
    with requests.get(url, stream=True, timeout=(10, timeout)) as response:
        response.raise_for_status()
        with output.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def install_verified_pandoc(
    mirror_templates: Iterable[str] = (), timeout: float = 45.0
) -> tuple[Path, str]:
    try:
        return resolve_pandoc(), "existing"
    except RuntimeError:
        pass

    manifest = load_manifest()
    version = str(manifest["version"])
    key = platform_key()
    asset_info = manifest.get("assets", {}).get(key)
    if not asset_info:
        raise RuntimeError(f"pandoc_platform_unsupported: {key}")
    asset = str(asset_info["filename"])
    expected_sha256 = str(asset_info["sha256"]).casefold()
    templates = [str(manifest["official_release_base"])]
    templates.extend(_environment_mirrors())
    templates.extend(str(item) for item in mirror_templates if str(item).strip())

    errors: list[str] = []
    target_root = cache_root() / version / key
    target_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tex-to-docx-pandoc-") as temp_name:
        temp = Path(temp_name)
        archive = temp / asset
        for template in templates:
            url = _render_url(template, version, asset)
            try:
                _download(url, archive, timeout)
                actual_sha256 = _sha256(archive)
                if actual_sha256 != expected_sha256:
                    raise RuntimeError(
                        f"checksum_mismatch: expected={expected_sha256}, actual={actual_sha256}"
                    )
                extract_root = temp / "extracted"
                _extract_verified_archive(archive, extract_root)
                candidates = [p for p in extract_root.rglob(executable_name()) if p.is_file()]
                if not candidates:
                    raise RuntimeError(f"pandoc_not_found_in_archive: {asset}")
                binary = min(candidates, key=lambda path: len(path.parts))
                binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
                ok, detail = probe_pandoc(binary)
                if not ok:
                    raise RuntimeError(f"downloaded_pandoc_not_runnable: {detail}")
                final_root = target_root / "runtime"
                if final_root.exists():
                    shutil.rmtree(final_root)
                shutil.copytree(extract_root, final_root)
                final_binary = final_root / binary.relative_to(extract_root)
                return final_binary.resolve(), url
            except (OSError, requests.RequestException, RuntimeError) as exc:
                errors.append(f"{url}: {type(exc).__name__}: {exc}")
                if archive.exists():
                    archive.unlink()
                extract_root = temp / "extracted"
                if extract_root.exists():
                    shutil.rmtree(extract_root)
    raise RuntimeError("pandoc_download_failed: " + " | ".join(errors))
