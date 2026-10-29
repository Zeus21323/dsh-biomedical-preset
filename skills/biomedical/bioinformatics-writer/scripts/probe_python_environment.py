#!/usr/bin/env python3
"""Record Python package versions and verify required module attributes."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def import_record(module_name: str) -> tuple[object | None, dict]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return None, {"available": False, "version": None, "error": str(exc)}
    return module, {
        "available": True,
        "version": str(getattr(module, "__version__", "unknown")),
        "error": None,
    }


def check_capability(raw: str, modules: dict[str, object | None]) -> dict:
    if ":" not in raw:
        return {
            "requirement": raw,
            "available": False,
            "error": "requirement must use module:attribute.path",
        }
    module_name, attribute_path = raw.split(":", 1)
    module_name = module_name.strip()
    attribute_path = attribute_path.strip()
    module = modules.get(module_name)
    if module_name not in modules:
        module, _ = import_record(module_name)
        modules[module_name] = module
    if module is None:
        return {
            "requirement": raw,
            "available": False,
            "error": f"module unavailable: {module_name}",
        }
    value = module
    try:
        for part in attribute_path.split("."):
            value = getattr(value, part)
    except AttributeError:
        return {
            "requirement": raw,
            "available": False,
            "error": f"attribute unavailable: {module_name}:{attribute_path}",
        }
    return {"requirement": raw, "available": True, "error": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="environment/python_environment.json")
    parser.add_argument("--package", action="append", default=[])
    parser.add_argument("--require", action="append", default=[])
    args = parser.parse_args()

    packages = list(dict.fromkeys(item.strip() for item in args.package if item.strip()))
    requirements = list(
        dict.fromkeys(item.strip() for item in args.require if item.strip())
    )
    modules: dict[str, object | None] = {}
    package_records: dict[str, dict] = {}
    for package in packages:
        module, record = import_record(package)
        modules[package] = module
        package_records[package] = record

    capabilities = [check_capability(item, modules) for item in requirements]
    missing_packages = [
        name for name, record in package_records.items() if not record["available"]
    ]
    missing_capabilities = [
        item["requirement"] for item in capabilities if not item["available"]
    ]
    if missing_packages:
        status = "missing_dependency"
    elif missing_capabilities:
        status = "missing_capability"
    else:
        status = "ready"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "packages": package_records,
        "capabilities": capabilities,
        "status": status,
    }
    output = Path(args.output).expanduser()
    atomic_write_json(output, payload)

    missing = [*missing_packages, *missing_capabilities]
    if missing:
        print("PYTHON_ENVIRONMENT MISSING " + ",".join(missing), file=sys.stderr)
        return 1
    print(f"PYTHON_ENVIRONMENT OK output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
