#!/usr/bin/env python3
"""Expose the local MVP cockpit through a read-only public ngrok bridge."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
STATE_DIR = ROOT / ".automoat" / "state"
BRIDGE_LOG = LOG_DIR / "mvp-bridge.log"
BRIDGE_STATUS = STATE_DIR / "mvp-bridge-status.json"
BRIDGE_PID = STATE_DIR / "mvp-bridge.pid"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_status(payload: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = utc_now()
    with BRIDGE_STATUS.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def emit(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    with BRIDGE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def http_json(url: str) -> dict[str, object] | None:
    try:
        with urlopen(url, timeout=1.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def wait_for_read_only_server(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def wait_for_ngrok_url(web_port: int, timeout: float = 20.0) -> str | None:
    deadline = time.monotonic() + timeout
    api_url = f"http://127.0.0.1:{web_port}/api/tunnels"
    while time.monotonic() < deadline:
        payload = http_json(api_url)
        if payload:
            for tunnel in payload.get("tunnels", []):
                public_url = tunnel.get("public_url")
                if isinstance(public_url, str) and public_url.startswith("https://"):
                    return public_url
        time.sleep(0.5)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4175, help="local read-only bridge viewer port")
    parser.add_argument("--ngrok-web-port", type=int, default=4040, help="local ngrok inspection API port")
    parser.add_argument("--interval", type=float, default=6.0, help="viewer loop status refresh interval")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ngrok = shutil.which("ngrok")
    if ngrok is None:
        emit("ngrok is not installed; cannot open remote bridge")
        write_status({"status": "error", "error": "ngrok not installed"})
        return 127

    BRIDGE_PID.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    viewer_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "serve_mvp_cockpit.py"),
        "--read-only",
        "--port",
        str(args.port),
        "--interval",
        str(args.interval),
    ]
    emit("$ " + " ".join(viewer_cmd))
    viewer = subprocess.Popen(
        viewer_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if not wait_for_read_only_server(args.port):
        output = viewer.stdout.read() if viewer.stdout else ""
        emit("read-only bridge viewer did not start")
        if output:
            emit(output.strip())
        write_status({"status": "error", "error": "read-only bridge viewer failed"})
        viewer.terminate()
        return 1

    ngrok_cmd = [
        ngrok,
        "http",
        f"http://127.0.0.1:{args.port}",
        "--log",
        "stdout",
        "--log-format",
        "json",
    ]
    emit("$ " + " ".join(ngrok_cmd))
    tunnel = subprocess.Popen(
        ngrok_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    public_url = wait_for_ngrok_url(args.ngrok_web_port)
    if not public_url:
        output = ""
        if tunnel.stdout:
            time.sleep(0.5)
            try:
                output = tunnel.stdout.read(4000)
            except TypeError:
                output = tunnel.stdout.read()
        emit("ngrok did not report a public URL")
        if output:
            emit(output.strip())
        write_status({"status": "error", "error": "ngrok did not report a public URL"})
        tunnel.terminate()
        viewer.terminate()
        return 1

    payload = {
        "status": "running",
        "public_url": public_url,
        "local_read_only_url": f"http://127.0.0.1:{args.port}/",
        "ngrok_api_url": f"http://127.0.0.1:{args.ngrok_web_port}/api/tunnels",
        "viewer_pid": viewer.pid,
        "ngrok_pid": tunnel.pid,
        "mode": "read-only",
    }
    write_status(payload)
    emit(f"remote bridge ready: {public_url}")
    try:
        while True:
            if viewer.poll() is not None:
                emit(f"read-only viewer exited status={viewer.returncode}")
                write_status({**payload, "status": "viewer-exited", "viewer_status": viewer.returncode})
                return int(viewer.returncode or 1)
            if tunnel.poll() is not None:
                emit(f"ngrok exited status={tunnel.returncode}")
                write_status({**payload, "status": "tunnel-exited", "ngrok_status": tunnel.returncode})
                return int(tunnel.returncode or 1)
            time.sleep(2)
    except KeyboardInterrupt:
        emit("remote bridge stopping")
        return 0
    finally:
        tunnel.terminate()
        viewer.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
