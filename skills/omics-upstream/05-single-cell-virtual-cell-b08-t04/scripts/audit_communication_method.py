#!/usr/bin/env python3
"""Create a reproducible readiness report for a documented communication method."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

CONTRACT = Path(__file__).resolve().parents[1] / "references" / "待执行方法核验.json"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def git_commit(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="核验尚未开放原生 runner 的细胞通讯方法；不执行算法或下载数据。"
    )
    parser.add_argument("--method", required=True)
    parser.add_argument("--out", required=True, help="必须是尚不存在的 Git 外输出目录")
    parser.add_argument("--source-root", help="可选的只读上游源码目录")
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    if out.exists():
        raise SystemExit(f"拒绝覆盖已有输出目录: {out}")
    contract = json.loads(CONTRACT.read_text())
    if args.method not in contract["methods"]:
        raise SystemExit(f"未登记的方法: {args.method}")

    source = Path(args.source_root).expanduser().resolve() if args.source_root else None
    if source is not None and not source.is_dir():
        raise SystemExit(f"source-root 不是目录: {source}")

    method = contract["methods"][args.method]
    report = {
        "schema_version": 1,
        "method": args.method,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_ready": False,
        "execution_status": "documented",
        "classification": method["classification"],
        "source_version": method["source_version"],
        "license": method["license"],
        "input_contract": method["input_contract"],
        "native_steps": method["native_steps"],
        "expected_figures": method["figures"],
        "blockers": method["blockers"],
        "upgrade_requires": method["upgrade_requires"],
        "source_probe": None,
        "decision": "没有原生执行。必须逐项解除 upgrade_requires 并完成真实数据验收后才能修改注册状态。",
    }
    if source is not None:
        files = sorted(p for p in source.rglob("*") if p.is_file() and ".git" not in p.parts)
        report["source_probe"] = {
            "path": str(source),
            "git_commit": git_commit(source),
            "file_count": len(files),
            "total_bytes": sum(p.stat().st_size for p in files),
            "key_files": [
                {"path": str(p.relative_to(source)), "bytes": p.stat().st_size, "sha256": sha256(p)}
                for p in files
                if p.name.lower() in {"readme.md", "license", "requirements.txt", "description"}
            ][:20],
        }

    out.mkdir(parents=True)
    (out / "readiness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (out / "run.log").write_text(
        f"method={args.method}\nstatus=documented\nexecution_ready=false\n"
        f"contract_sha256={sha256(CONTRACT)}\n"
    )
    print(out / "readiness.json")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
