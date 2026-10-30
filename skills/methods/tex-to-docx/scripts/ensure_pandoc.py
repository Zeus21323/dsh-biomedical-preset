#!/usr/bin/env python3
"""Find Pandoc or install a platform-matched, checksum-verified local runtime."""

from __future__ import annotations

import argparse

from pandoc_runtime import install_verified_pandoc, probe_pandoc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mirror-url-template",
        action="append",
        default=[],
        help=(
            "Trusted fallback URL template, repeatable. Use {version} and {asset}; "
            "a base URL is interpreted as BASE/{version}/{asset}."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Per-read download timeout in seconds (default: 45).",
    )
    args = parser.parse_args()
    path, source = install_verified_pandoc(args.mirror_url_template, args.timeout)
    ok, version = probe_pandoc(path)
    if not ok:
        raise SystemExit(f"pandoc_preflight_failed: {version}")
    print(f"PANDOC_PATH={path}")
    print(f"PANDOC_VERSION={version}")
    print(f"PANDOC_SOURCE={source}")


if __name__ == "__main__":
    main()
