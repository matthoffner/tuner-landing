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
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
STATE_DIR = ROOT / ".automoat" / "state"
BRIDGE_LOG = LOG_DIR / "mvp-bridge.log"
BRIDGE_STATUS = STATE_DIR / "mvp-bridge-status.json"
BRIDGE_PID = STATE_DIR / "mvp-bridge.pid"
BRIDGE_HEALTH_LABELS = {
    "bridge_status_unknown": "Bridge status is unknown",
    "viewer_start_failed": "Read-only viewer failed to start",
    "tunnel_url_unavailable": "Ngrok tunnel URL is unavailable",
    "viewer_exited": "Read-only viewer exited",
    "tunnel_exited": "Ngrok tunnel exited",
    "bridge_error": "Bridge failed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bridge_health_label(reason: str | None) -> str:
    if reason is None:
        return "Live"
    return BRIDGE_HEALTH_LABELS.get(reason, reason.replace("_", " "))


def bridge_health(payload: dict[str, object]) -> dict[str, object]:
    status = payload.get("status")
    error = payload.get("error")
    reasons: list[str] = []
    if status == "running":
        pass
    elif status == "viewer-exited":
        reasons.append("viewer_exited")
    elif status == "tunnel-exited":
        reasons.append("tunnel_exited")
    elif status == "error" and error == "read-only bridge viewer failed":
        reasons.append("viewer_start_failed")
    elif status == "error" and error == "ngrok did not report a public URL":
        reasons.append("tunnel_url_unavailable")
    elif status == "error":
        reasons.append("bridge_error")
    else:
        reasons.append("bridge_status_unknown")

    primary_reason = reasons[0] if reasons else None
    health_status = "degraded" if reasons else "live"
    return {
        "status": health_status,
        "ok": health_status == "live",
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": bridge_health_label(primary_reason),
    }


def write_status(payload: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload["bridge_health"] = bridge_health(payload)
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
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate bridge configuration without starting the viewer or ngrok",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for --check-env preflight results",
    )
    return parser.parse_args()


def validate_port(name: str, value: int) -> list[str]:
    if value <= 0:
        return [f"{name} must be greater than 0"]
    if value > 65535:
        return [f"{name} must be less than or equal to 65535"]
    return []


def validate_bridge_configuration(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_port("--port", int(args.port)))
    errors.extend(validate_port("--ngrok-web-port", int(args.ngrok_web_port)))
    if args.interval <= 0:
        errors.append("--interval must be greater than 0")
    if args.port == args.ngrok_web_port:
        errors.append("--port must not equal --ngrok-web-port")
    if shutil.which("ngrok") is None:
        errors.append("ngrok is required")
    return errors


def bridge_preflight_error_category(error: str) -> str:
    if error.startswith("ngrok "):
        return "missing_command"
    if error.startswith("--"):
        return "invalid_runtime_config"
    return "invalid_configuration"


def bridge_preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({bridge_preflight_error_category(error) for error in errors})


def bridge_preflight_summary(args: argparse.Namespace, errors: list[str]) -> dict[str, Any]:
    ngrok_path = shutil.which("ngrok")
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": bridge_preflight_error_categories(errors),
            "ngrok_available": ngrok_path is not None,
        }
        return payload

    payload["config"] = {
        "local_read_only_url": f"http://127.0.0.1:{args.port}/",
        "ngrok_api_url": f"http://127.0.0.1:{args.ngrok_web_port}/api/tunnels",
        "interval": float(args.interval),
        "ngrok_available": ngrok_path is not None,
    }
    return payload


def emit_bridge_preflight(args: argparse.Namespace, *, output_format: str = "text") -> list[str]:
    errors = validate_bridge_configuration(args)
    if output_format == "json":
        print(json.dumps(bridge_preflight_summary(args, errors), sort_keys=True), flush=True)
        return errors

    if errors:
        print("mvp cockpit bridge preflight failed")
        for error in errors:
            print(f"  - {error}")
        return errors

    print(
        "mvp cockpit bridge preflight passed: "
        f"local_read_only_url=http://127.0.0.1:{args.port}/ "
        f"ngrok_api_url=http://127.0.0.1:{args.ngrok_web_port}/api/tunnels "
        f"interval={args.interval}"
    )
    return []


def main() -> int:
    args = parse_args()
    if args.format == "json" and not args.check_env:
        print("--format json is only supported with --check-env", file=sys.stderr)
        return 2

    errors = validate_bridge_configuration(args)
    if args.check_env:
        return 0 if not emit_bridge_preflight(args, output_format=args.format) else 2
    if errors:
        for error in errors:
            emit(error)
        write_status({"status": "error", "error": errors[0]})
        return 2

    ngrok = shutil.which("ngrok")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
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
        "--web-addr",
        f"127.0.0.1:{args.ngrok_web_port}",
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
