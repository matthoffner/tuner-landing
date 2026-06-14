#!/usr/bin/env python3
"""Publish local Autom oat cockpit status snapshots to the Render relay."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-loop-status.json"
PID_FILE = ROOT / ".automoat" / "state" / "mvp-loop.pid"
LOG_FILE = ROOT / ".automoat" / "logs" / "mvp-loop.log"
PUBLISHER_LOG = ROOT / ".automoat" / "logs" / "cockpit-relay-publisher.log"
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit(message: str, *, log_path: Path) -> None:
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def local_loop_pid(pid_file: Path = PID_FILE) -> int | None:
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if pid_alive(pid) else None


def read_status(status_file: Path = STATUS_FILE, pid_file: Path = PID_FILE) -> dict[str, Any]:
    status = read_json(status_file) or {
        "status": "waiting",
        "updated_at": None,
    }
    status = dict(status)
    pid = local_loop_pid(pid_file)
    status["loop_running"] = pid is not None
    status["loop_pid"] = pid
    status["publisher_updated_at"] = utc_now()
    return status


def tail_text(path: Path, line_count: int, max_bytes: int) -> str:
    if not path.exists():
        return "waiting for local cockpit log...\n"
    chunk_size = 8192
    data = b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and data.count(b"\n") <= line_count and len(data) < max_bytes:
            read_size = min(chunk_size, position, max_bytes - len(data))
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size) + data
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return "\n".join(lines[-line_count:]).rstrip() + "\n"


def shell(command: list[str], timeout: float = 5.0) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout,
    )
    return result.stdout.strip()


def git_snapshot() -> dict[str, Any]:
    status_lines = shell(["git", "status", "--porcelain=v1"]).splitlines()
    dirty_paths = []
    for line in status_lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and path != ".pxcode/preview.json":
            dirty_paths.append(path)
    return {
        "head": shell(["git", "rev-parse", "--short", "HEAD"]),
        "branch": shell(["git", "branch", "--show-current"]),
        "dirty_paths": dirty_paths,
        "dirty_path_count": len(dirty_paths),
    }


def repo_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "pushed_at": utc_now(),
        "status": read_status(args.status_file, args.pid_file),
        "log_tail": tail_text(args.log_file, args.tail_lines, args.max_log_bytes),
        "publisher": {
            "host": socket.gethostname(),
            "repo": str(ROOT),
            "status_file": repo_relative(args.status_file),
            "pid_file": repo_relative(args.pid_file),
            "log_file": repo_relative(args.log_file),
            "git": git_snapshot(),
        },
    }


def post_payload(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    relay_url = args.relay_url.rstrip("/")
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{relay_url}/ingest",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {args.token}",
            "X-Automoat-Relay-Token": args.token,
            "Content-Type": "application/json",
            "User-Agent": "automoat-cockpit-publisher/0.1",
        },
    )
    with urlopen(request, timeout=args.timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else {"ok": False, "body": body}


def publish_once(args: argparse.Namespace) -> bool:
    try:
        response = post_payload(args, build_payload(args))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        emit(f"publish failed http_status={exc.code} body={detail.strip()}", log_path=args.publisher_log)
        return False
    except (OSError, URLError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        emit(f"publish failed error={exc}", log_path=args.publisher_log)
        return False
    emit(
        f"published relay snapshot ok={response.get('ok')} received_at={response.get('received_at')}",
        log_path=args.publisher_log,
    )
    return bool(response.get("ok"))


def run_publish_loop(args: argparse.Namespace) -> int:
    consecutive_failures = 0
    while True:
        if publish_once(args):
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if (
                args.max_consecutive_failures > 0
                and consecutive_failures >= args.max_consecutive_failures
            ):
                emit(
                    "exiting after consecutive publish failures "
                    f"count={consecutive_failures} "
                    f"limit={args.max_consecutive_failures}",
                    log_path=args.publisher_log,
                )
                return 1
        time.sleep(args.interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relay-url", default=os.environ.get("AUTOMOAT_RELAY_URL", ""))
    parser.add_argument("--token", default=os.environ.get("AUTOMOAT_RELAY_TOKEN", ""))
    parser.add_argument("--interval", type=float, default=float(os.environ.get("AUTOMOAT_RELAY_INTERVAL", "3")))
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--tail-lines", type=int, default=180)
    parser.add_argument("--max-log-bytes", type=int, default=256 * 1024)
    parser.add_argument("--status-file", type=Path, default=STATUS_FILE)
    parser.add_argument("--pid-file", type=Path, default=PID_FILE)
    parser.add_argument("--log-file", type=Path, default=LOG_FILE)
    parser.add_argument("--publisher-log", type=Path, default=PUBLISHER_LOG)
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=int(
            os.environ.get(
                "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
                str(DEFAULT_MAX_CONSECUTIVE_FAILURES),
            )
        ),
        help=(
            "exit nonzero after this many consecutive publish failures; "
            "set 0 to retry forever"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.status_file = args.status_file.expanduser().resolve()
    args.pid_file = args.pid_file.expanduser().resolve()
    args.log_file = args.log_file.expanduser().resolve()
    args.publisher_log = args.publisher_log.expanduser().resolve()
    if not args.relay_url:
        print("AUTOMOAT_RELAY_URL or --relay-url is required", file=sys.stderr)
        return 2
    if not args.token:
        print("AUTOMOAT_RELAY_TOKEN or --token is required", file=sys.stderr)
        return 2
    if args.interval <= 0:
        print("--interval must be greater than 0", file=sys.stderr)
        return 2
    if args.max_consecutive_failures < 0:
        print("--max-consecutive-failures must be greater than or equal to 0", file=sys.stderr)
        return 2

    if args.once:
        return 0 if publish_once(args) else 1

    return run_publish_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
