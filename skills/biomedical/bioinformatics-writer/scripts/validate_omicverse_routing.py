#!/usr/bin/env python3
"""Require a per-module OmicVerse MCP routing decision before Stage 3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


VALID_DECISIONS = {"omicverse_mcp", "fallback", "not_mcp_candidate", "blocked"}
VALID_DISCOVERY = {"live_catalog", "capability_map"}


def fail(message: str) -> None:
    print(f"OMICVERSE_ROUTING: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path}: {exc}")


def inventory_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("analysis_inventory", payload.get("analyses", payload.get("modules")))
    else:
        items = None
    if not isinstance(items, list) or not items:
        fail("inventory must contain a non-empty analysis_inventory, analyses, or modules list")
    if not all(isinstance(item, dict) for item in items):
        fail("every inventory item must be an object")
    return items


def module_name(item: dict) -> str | None:
    for key in ("analysis_name", "name", "module"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--routing", required=True, type=Path)
    args = parser.parse_args()

    inventory = inventory_items(load_json(args.inventory))
    required_names = [module_name(item) for item in inventory]
    if any(name is None for name in required_names):
        fail("every inventory item needs analysis_name, name, or module")

    routing = load_json(args.routing)
    if not isinstance(routing, dict) or not isinstance(routing.get("module_routes"), list):
        fail("routing must contain a module_routes list")
    routes = routing["module_routes"]
    by_name: dict[str, dict] = {}
    for route in routes:
        if not isinstance(route, dict):
            fail("every module_routes item must be an object")
        name = module_name(route)
        if not name:
            fail("every module route needs analysis_name, name, or module")
        if name in by_name:
            fail(f"duplicate route for module: {name}")
        by_name[name] = route

    missing = [name for name in required_names if name not in by_name]
    if missing:
        fail("missing module routes: " + ", ".join(missing))

    for name in required_names:
        route = by_name[name]
        if route.get("discovery") not in VALID_DISCOVERY:
            fail(f"{name}: discovery must be live_catalog or capability_map")
        decision = route.get("decision")
        if decision not in VALID_DECISIONS:
            fail(f"{name}: invalid decision")
        if not isinstance(route.get("reason"), str) or not route["reason"].strip():
            fail(f"{name}: a concrete reason is required")
        if decision == "omicverse_mcp" and not isinstance(route.get("tool_name"), str):
            fail(f"{name}: omicverse_mcp decision requires tool_name")
        if decision in {"fallback", "not_mcp_candidate"} and not isinstance(route.get("actual_backend"), str):
            fail(f"{name}: fallback decision requires actual_backend")

    print(f"OMICVERSE_ROUTING: pass ({len(required_names)} approved modules routed)")


if __name__ == "__main__":
    main()
