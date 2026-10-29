#!/usr/bin/env python3
"""Run one analysis command with a deadline, log, and atomic status record."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


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


def stop_process_group(process: subprocess.Popen, grace_seconds: float) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--status", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--heartbeat", type=float, default=10.0)
    parser.add_argument("--terminate-grace", type=float, default=5.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("provide a command after --")
    if args.timeout <= 0 or args.heartbeat <= 0 or args.terminate_grace <= 0:
        parser.error("timeout, heartbeat, and terminate-grace must be positive")

    root = Path(args.project_root).expanduser().resolve()
    status_path = resolve(root, args.status)
    log_path = resolve(root, args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    started_wall = utc_now()
    started_mono = time.monotonic()
    state = {
        "status": "starting",
        "command": command,
        "project_root": str(root),
        "log_path": str(log_path),
        "timeout_seconds": args.timeout,
        "started_at": started_wall,
        "last_heartbeat_at": started_wall,
        "elapsed_seconds": 0.0,
        "pid": None,
        "exit_code": None,
        "ended_at": None,
    }
    atomic_write_json(status_path, state)

    try:
        with log_path.open("ab", buffering=0) as log_handle:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            state.update(status="running", pid=process.pid)
            atomic_write_json(status_path, state)

            next_heartbeat = started_mono + args.heartbeat
            while True:
                return_code = process.poll()
                now = time.monotonic()
                elapsed = now - started_mono
                if return_code is not None:
                    state.update(
                        status="completed" if return_code == 0 else "failed",
                        elapsed_seconds=round(elapsed, 3),
                        exit_code=return_code,
                        ended_at=utc_now(),
                        last_heartbeat_at=utc_now(),
                    )
                    atomic_write_json(status_path, state)
                    print(
                        f"ANALYSIS_TASK {state['status']} exit_code={return_code} "
                        f"status={status_path} log={log_path}"
                    )
                    return return_code if return_code >= 0 else 1

                if elapsed >= args.timeout:
                    stop_process_group(process, args.terminate_grace)
                    state.update(
                        status="timed_out",
                        elapsed_seconds=round(elapsed, 3),
                        exit_code=124,
                        ended_at=utc_now(),
                        last_heartbeat_at=utc_now(),
                    )
                    atomic_write_json(status_path, state)
                    print(
                        f"ANALYSIS_TASK timed_out exit_code=124 "
                        f"status={status_path} log={log_path}",
                        file=sys.stderr,
                    )
                    return 124

                if now >= next_heartbeat:
                    state.update(
                        elapsed_seconds=round(elapsed, 3),
                        last_heartbeat_at=utc_now(),
                    )
                    atomic_write_json(status_path, state)
                    next_heartbeat = now + args.heartbeat
                time.sleep(min(0.25, args.heartbeat))
    except KeyboardInterrupt:
        if "process" in locals():
            stop_process_group(process, args.terminate_grace)
        state.update(
            status="cancelled",
            elapsed_seconds=round(time.monotonic() - started_mono, 3),
            exit_code=130,
            ended_at=utc_now(),
            last_heartbeat_at=utc_now(),
        )
        atomic_write_json(status_path, state)
        print(
            f"ANALYSIS_TASK cancelled exit_code=130 "
            f"status={status_path} log={log_path}",
            file=sys.stderr,
        )
        return 130
    except OSError as exc:
        state.update(
            status="failed_to_start",
            elapsed_seconds=round(time.monotonic() - started_mono, 3),
            exit_code=127,
            ended_at=utc_now(),
            last_heartbeat_at=utc_now(),
            error=str(exc),
        )
        atomic_write_json(status_path, state)
        print(f"ANALYSIS_TASK failed_to_start: {exc}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
