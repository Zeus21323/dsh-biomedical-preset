#!/usr/bin/env python3
"""Validate journal-profile JSON files and ensure every bundled CSL is mapped."""

from __future__ import annotations

import json
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PROFILE_DIR = SKILL_DIR / "assets" / "journal_profiles"
CSL_DIR = SKILL_DIR / "assets" / "csl"
REQUIRED_STYLES = ("body", "title", "headings", "caption", "bibliography")


def main() -> None:
    index = json.loads((PROFILE_DIR / "index.json").read_text(encoding="utf-8"))
    profiles: list[dict] = []
    errors: list[str] = []
    ids: set[str] = set()
    mapped_csl: set[str] = set()
    for filename in index.get("profiles", []):
        path = PROFILE_DIR / filename
        if not path.is_file():
            errors.append(f"missing profile: {filename}")
            continue
        profile = json.loads(path.read_text(encoding="utf-8"))
        profiles.append(profile)
        profile_id = profile.get("profile_id")
        if not profile_id or profile_id in ids:
            errors.append(f"invalid or duplicate profile_id in {filename}: {profile_id!r}")
        ids.add(profile_id)
        for key in REQUIRED_STYLES:
            if key not in profile.get("template", {}):
                errors.append(f"{profile_id}: missing template.{key}")
        if not profile.get("sources"):
            errors.append(f"{profile_id}: no sources")
        if not profile.get("evidence"):
            errors.append(f"{profile_id}: no evidence map")
        for csl in profile.get("csl_files", []):
            mapped_csl.add(csl)
            if not (CSL_DIR / csl).is_file():
                errors.append(f"{profile_id}: mapped CSL missing: {csl}")
        default_csl = profile.get("default_csl_file")
        if default_csl and default_csl not in profile.get("csl_files", []):
            errors.append(f"{profile_id}: default_csl_file is not listed in csl_files: {default_csl}")

    bundled_csl = {path.name for path in CSL_DIR.glob("*.csl")}
    for csl in sorted(bundled_csl - mapped_csl):
        errors.append(f"unmapped CSL: {csl}")
    for csl in sorted(mapped_csl - bundled_csl):
        errors.append(f"profile references unbundled CSL: {csl}")

    if errors:
        raise SystemExit("journal_profile_validation_failed:\n  " + "\n  ".join(errors))
    print(f"journal_profiles_valid profiles={len(profiles)} csl_files={len(bundled_csl)}")


if __name__ == "__main__":
    main()
