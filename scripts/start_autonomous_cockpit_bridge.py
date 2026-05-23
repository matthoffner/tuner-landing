#!/usr/bin/env python3
"""Start the autonomous cockpit and read-only bridge as detached local processes."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
STATE_DIR = ROOT / ".automoat" / "state"
COCKPIT_PID = STATE_DIR / "mvp-cockpit-server.pid"
BRIDGE_RUNNER_PID = STATE_DIR / "mvp-bridge-runner.pid"
BRIDGE_STATUS = STATE_DIR / "mvp-bridge-status.json"


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_process_group(path: Path) -> None:
    pid = read_pid(path)
    if not pid or not pid_alive(pid):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return
        time.sleep(0.2)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def start_detached(command: list[str], log_path: Path, pid_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    out = open(log_path, "ab", buffering=0)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    pid_path.write_text(str(process.pid) + "\n", encoding="utf-8")
    return process.pid


def wait_http(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001 - surface the last startup failure.
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"{url} did not become ready: {last_error}")


def wait_bridge(timeout: float) -> str:
    deadline = time.monotonic() + timeout
    last_status = ""
    while time.monotonic() < deadline:
        try:
            status = json.loads(BRIDGE_STATUS.read_text(encoding="utf-8"))
            public_url = status.get("public_url")
            if status.get("status") == "running" and public_url:
                wait_http(f"{public_url}/api/status", 10)
                return str(public_url)
            last_status = json.dumps(status)
        except Exception as exc:  # noqa: BLE001 - surface the last startup failure.
            last_status = str(exc)
        time.sleep(1)
    raise RuntimeError(f"bridge did not become ready: {last_status}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=300.0, help="seconds between autonomous Codex iterations")
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("--no-stop-existing", action="store_true")
    parser.add_argument("--keep-bridge", action="store_true", help="restart only the local cockpit and reuse the existing bridge")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_stop_existing:
        if not args.keep_bridge:
            stop_process_group(BRIDGE_RUNNER_PID)
        stop_process_group(COCKPIT_PID)

    cockpit_pid = start_detached(
        [
            sys.executable,
            "scripts/serve_mvp_cockpit.py",
            "--auto-start",
            "--loop-mode",
            "agent",
            "--interval",
            str(args.interval),
            "--port",
            str(args.port),
        ],
        LOG_DIR / "mvp-cockpit-server.log",
        COCKPIT_PID,
    )
    wait_http(f"http://127.0.0.1:{args.port}/api/status", 30)

    if args.keep_bridge:
        bridge_pid = read_pid(BRIDGE_RUNNER_PID) or 0
    else:
        bridge_pid = start_detached(
            [sys.executable, "scripts/bridge_mvp_cockpit.py"],
            LOG_DIR / "mvp-bridge-runner.log",
            BRIDGE_RUNNER_PID,
        )
    public_url = wait_bridge(45)
    print(f"cockpit_pid={cockpit_pid}")
    print(f"bridge_runner_pid={bridge_pid}")
    print(public_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
