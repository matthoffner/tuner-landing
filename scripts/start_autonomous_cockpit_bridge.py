#!/usr/bin/env python3
"""Start the autonomous cockpit and read-only bridge as detached local processes."""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
STATE_DIR = ROOT / ".automoat" / "state"
COCKPIT_PID = STATE_DIR / "mvp-cockpit-server.pid"
BRIDGE_RUNNER_PID = STATE_DIR / "mvp-bridge-runner.pid"
BRIDGE_STATUS = STATE_DIR / "mvp-bridge-status.json"


def repo_relative(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(ROOT)
    except ValueError:
        return f"<external>/{resolved_path.name}" if resolved_path.name else "<external>"
    relative_text = relative_path.as_posix()
    return relative_text if relative_text else "."


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
    with log_path.open("ab", buffering=0) as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=output,
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
    parser.add_argument("--bridge-port", type=int, default=4175, help="local read-only bridge viewer port")
    parser.add_argument("--ngrok-web-port", type=int, default=4040, help="local ngrok inspection API port")
    parser.add_argument("--bridge-interval", type=float, default=6.0, help="read-only bridge viewer refresh interval")
    parser.add_argument("--no-stop-existing", action="store_true")
    parser.add_argument("--keep-bridge", action="store_true", help="restart only the local cockpit and reuse the existing bridge")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate local bridge launcher configuration without starting processes",
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


def validate_positive_float(name: str, value: float) -> list[str]:
    if not math.isfinite(value):
        return [f"{name} must be a finite number of seconds"]
    if value <= 0:
        return [f"{name} must be greater than 0"]
    return []


def blocking_parent_path_component(path: Path) -> Path | None:
    current_path = path.parent
    while True:
        if current_path.exists():
            return None if current_path.is_dir() else current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent


def validate_directory_path(label: str, path: Path) -> list[str]:
    if path.exists() and not path.is_dir():
        return [f"{label} path {repo_relative(path)} must be a directory"]
    blocking_path = blocking_parent_path_component(path)
    if blocking_path is not None:
        return [f"{label} parent path {repo_relative(blocking_path)} must be a directory"]
    return []


def validate_file_path(label: str, path: Path) -> list[str]:
    if path.exists() and path.is_dir():
        return [f"{label} path {repo_relative(path)} must be a file path, not a directory"]
    blocking_path = blocking_parent_path_component(path)
    if blocking_path is not None:
        return [f"{label} parent path {repo_relative(blocking_path)} must be a directory"]
    return []


def validate_startup_file_paths() -> list[str]:
    errors: list[str] = []
    for label, path in {
        "LOG_DIR": LOG_DIR,
        "STATE_DIR": STATE_DIR,
    }.items():
        errors.extend(validate_directory_path(label, path))
    for label, path in {
        "COCKPIT_PID": COCKPIT_PID,
        "BRIDGE_RUNNER_PID": BRIDGE_RUNNER_PID,
        "BRIDGE_STATUS": BRIDGE_STATUS,
        "COCKPIT_LOG": LOG_DIR / "mvp-cockpit-server.log",
        "BRIDGE_RUNNER_LOG": LOG_DIR / "mvp-bridge-runner.log",
    }.items():
        errors.extend(validate_file_path(label, path))
    return errors


def validate_startup_configuration(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_port("--port", int(args.port)))
    errors.extend(validate_port("--bridge-port", int(args.bridge_port)))
    errors.extend(validate_port("--ngrok-web-port", int(args.ngrok_web_port)))
    errors.extend(validate_positive_float("--interval", float(args.interval)))
    errors.extend(validate_positive_float("--bridge-interval", float(args.bridge_interval)))
    if args.port == args.bridge_port:
        errors.append("--port must not equal --bridge-port")
    if args.port == args.ngrok_web_port:
        errors.append("--port must not equal --ngrok-web-port")
    if args.bridge_port == args.ngrok_web_port:
        errors.append("--bridge-port must not equal --ngrok-web-port")
    if not args.keep_bridge and shutil.which("ngrok") is None:
        errors.append("ngrok is required unless --keep-bridge is set")
    errors.extend(validate_startup_file_paths())
    return errors


def startup_preflight_error_category(error: str) -> str:
    if error.startswith("ngrok "):
        return "missing_command"
    if any(
        error.startswith(prefix)
        for prefix in (
            "LOG_DIR",
            "STATE_DIR",
            "COCKPIT_PID",
            "BRIDGE_RUNNER_PID",
            "BRIDGE_STATUS",
            "COCKPIT_LOG",
            "BRIDGE_RUNNER_LOG",
        )
    ):
        return "invalid_file_path"
    if error.startswith("--"):
        return "invalid_runtime_config"
    return "invalid_configuration"


def startup_preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({startup_preflight_error_category(error) for error in errors})


def startup_preflight_error_key(error: str) -> str:
    file_path_keys = (
        "BRIDGE_RUNNER_LOG",
        "BRIDGE_RUNNER_PID",
        "BRIDGE_STATUS",
        "COCKPIT_LOG",
        "COCKPIT_PID",
        "LOG_DIR",
        "STATE_DIR",
    )
    for key in file_path_keys:
        if error.startswith(key):
            return key
    if error.startswith("ngrok "):
        return "PATH:ngrok"
    if error == "--port must not equal --bridge-port":
        return "--bridge-port|--port"
    if error == "--port must not equal --ngrok-web-port":
        return "--ngrok-web-port|--port"
    if error == "--bridge-port must not equal --ngrok-web-port":
        return "--bridge-port|--ngrok-web-port"
    if error.startswith("--bridge-interval"):
        return "--bridge-interval"
    if error.startswith("--ngrok-web-port"):
        return "--ngrok-web-port"
    if error.startswith("--bridge-port"):
        return "--bridge-port"
    if error.startswith("--interval"):
        return "--interval"
    if error.startswith("--port"):
        return "--port"
    return "startup_configuration"


def startup_preflight_error_keys(errors: list[str]) -> list[str]:
    return sorted({startup_preflight_error_key(error) for error in errors})


def startup_preflight_summary(args: argparse.Namespace, errors: list[str]) -> dict[str, Any]:
    ngrok_path = shutil.which("ngrok")
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": startup_preflight_error_categories(errors),
            "failed_configuration_keys": startup_preflight_error_keys(errors),
            "ngrok_required": not bool(args.keep_bridge),
            "ngrok_available": ngrok_path is not None,
        }
        return payload

    payload["config"] = {
        "local_cockpit_url": f"http://127.0.0.1:{args.port}",
        "local_bridge_url": f"http://127.0.0.1:{args.bridge_port}/",
        "ngrok_api_url": f"http://127.0.0.1:{args.ngrok_web_port}/api/tunnels",
        "agent_interval": float(args.interval),
        "bridge_interval": float(args.bridge_interval),
        "keep_bridge": bool(args.keep_bridge),
        "stop_existing": not bool(args.no_stop_existing),
        "ngrok_required": not bool(args.keep_bridge),
        "ngrok_available": ngrok_path is not None,
    }
    return payload


def emit_startup_preflight(
    args: argparse.Namespace,
    *,
    output_format: str = "text",
) -> list[str]:
    errors = validate_startup_configuration(args)
    if output_format == "json":
        print(json.dumps(startup_preflight_summary(args, errors), sort_keys=True), flush=True)
        return errors

    if errors:
        print("autonomous bridge startup preflight failed")
        for error in errors:
            print(f"  - {error}")
        return errors

    print(
        "autonomous bridge startup preflight passed: "
        f"local_cockpit_url=http://127.0.0.1:{args.port} "
        f"local_bridge_url=http://127.0.0.1:{args.bridge_port}/ "
        f"ngrok_api_url=http://127.0.0.1:{args.ngrok_web_port}/api/tunnels "
        f"agent_interval={args.interval} "
        f"bridge_interval={args.bridge_interval} "
        f"keep_bridge={args.keep_bridge}"
    )
    return []


def main() -> int:
    args = parse_args()
    if args.format == "json" and not args.check_env:
        print("--format json is only supported with --check-env", file=sys.stderr)
        return 2

    errors = validate_startup_configuration(args)
    if args.check_env:
        return 0 if not emit_startup_preflight(args, output_format=args.format) else 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

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
            [
                sys.executable,
                "scripts/bridge_mvp_cockpit.py",
                "--port",
                str(args.bridge_port),
                "--ngrok-web-port",
                str(args.ngrok_web_port),
                "--interval",
                str(args.bridge_interval),
            ],
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
