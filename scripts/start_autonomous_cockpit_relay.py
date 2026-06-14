#!/usr/bin/env python3
"""Start the autonomous cockpit and Render relay publisher as detached local processes."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
STATE_DIR = ROOT / ".automoat" / "state"
COCKPIT_PID = STATE_DIR / "mvp-cockpit-server.pid"
PUBLISHER_PID = STATE_DIR / "cockpit-relay-publisher.pid"
BRIDGE_RUNNER_PID = STATE_DIR / "mvp-bridge-runner.pid"


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


def start_detached(command: list[str], log_path: Path, pid_path: Path, env: dict[str, str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    output = open(log_path, "ab", buffering=0)
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
        env=env,
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


def publish_once(relay_url: str, token: str) -> None:
    env = os.environ.copy()
    env["AUTOMOAT_RELAY_URL"] = relay_url
    env["AUTOMOAT_RELAY_TOKEN"] = token
    result = subprocess.run(
        [sys.executable, "scripts/publish_cockpit_to_relay.py", "--once"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError("initial relay publish failed:\n" + result.stdout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=300.0, help="seconds between autonomous Codex iterations")
    parser.add_argument("--publish-interval", type=float, default=3.0, help="seconds between relay publishes")
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("--relay-url", default=os.environ.get("AUTOMOAT_RELAY_URL", ""))
    parser.add_argument("--token", default=os.environ.get("AUTOMOAT_RELAY_TOKEN", ""))
    parser.add_argument("--no-stop-existing", action="store_true")
    parser.add_argument("--keep-legacy-bridge", action="store_true")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate local relay launcher configuration without starting processes",
    )
    return parser.parse_args()


def normalized_relay_url(value: str) -> str:
    stripped = value.strip()
    parsed = urlparse(stripped)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return stripped.rstrip("/")
    return stripped


def validate_startup_configuration(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    relay_url = normalized_relay_url(str(args.relay_url))
    if not relay_url:
        errors.append("AUTOMOAT_RELAY_URL or --relay-url is required")
    elif not relay_url.startswith(("http://", "https://")):
        errors.append("--relay-url must start with http:// or https://")
    else:
        parsed_relay_url = urlparse(relay_url)
        if not parsed_relay_url.netloc:
            errors.append("--relay-url must include a host")
        elif parsed_relay_url.username or parsed_relay_url.password:
            errors.append("--relay-url must not include embedded credentials")
        elif parsed_relay_url.query or parsed_relay_url.fragment:
            errors.append("--relay-url must not include query strings or fragments")

    if not str(args.token).strip():
        errors.append("AUTOMOAT_RELAY_TOKEN or --token is required")
    if args.interval <= 0:
        errors.append("--interval must be greater than 0")
    if args.publish_interval <= 0:
        errors.append("--publish-interval must be greater than 0")
    if args.port <= 0:
        errors.append("--port must be greater than 0")
    elif args.port > 65535:
        errors.append("--port must be less than or equal to 65535")
    return errors


def emit_startup_preflight(args: argparse.Namespace) -> list[str]:
    errors = validate_startup_configuration(args)
    if errors:
        print("autonomous relay startup preflight failed")
        for error in errors:
            print(f"  - {error}")
        return errors

    print(
        "autonomous relay startup preflight passed: "
        f"relay_url={normalized_relay_url(str(args.relay_url))} "
        f"local_port={args.port} "
        f"agent_interval={args.interval} "
        f"publish_interval={args.publish_interval} "
        f"keep_legacy_bridge={args.keep_legacy_bridge}"
    )
    return []


def main() -> int:
    args = parse_args()
    errors = validate_startup_configuration(args)
    if args.check_env:
        return 0 if not emit_startup_preflight(args) else 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2
    relay_url = normalized_relay_url(str(args.relay_url))
    token = str(args.token).strip()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_stop_existing:
        stop_process_group(PUBLISHER_PID)
        stop_process_group(COCKPIT_PID)
        if not args.keep_legacy_bridge:
            stop_process_group(BRIDGE_RUNNER_PID)

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
    local_url = f"http://127.0.0.1:{args.port}"
    wait_http(f"{local_url}/api/status", 30)
    publish_once(relay_url, token)

    env = os.environ.copy()
    env["AUTOMOAT_RELAY_URL"] = relay_url
    env["AUTOMOAT_RELAY_TOKEN"] = token
    publisher_pid = start_detached(
        [
            sys.executable,
            "scripts/publish_cockpit_to_relay.py",
            "--interval",
            str(args.publish_interval),
        ],
        LOG_DIR / "cockpit-relay-publisher.log",
        PUBLISHER_PID,
        env=env,
    )

    print(f"cockpit_pid={cockpit_pid}")
    print(f"relay_publisher_pid={publisher_pid}")
    print(local_url)
    print(relay_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
