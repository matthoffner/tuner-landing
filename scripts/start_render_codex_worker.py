#!/usr/bin/env python3
"""Run the real Autom oat Codex loop inside Render and publish cockpit snapshots."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_REPO = "https://github.com/matthoffner/tuner-landing.git"
WORKDIR = Path(os.environ.get("AUTOMOAT_WORKDIR", "/work/automoat"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "/tmp/codex-home"))
GIT_ASKPASS = Path("/tmp/automoat-git-askpass.sh")
GITHUB_TOKEN_FILE = Path("/tmp/automoat-github-token")

CHILDREN: list[subprocess.Popen[object]] = []
STOP_REQUESTED = False
CODEX_AUTH_ENV_NAMES = ("CODEX_AUTH_JSON_B64", "CODEX_ACCESS_TOKEN", "OPENAI_API_KEY")
GIT_AUTH_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")
REQUIRED_COMMANDS = ("git", "codex")


def emit(message: str) -> None:
    print(f"[render-worker] {message}", flush=True)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def env_has_any(env: os._Environ[str] | dict[str, str], names: tuple[str, ...]) -> bool:
    return any(env.get(name, "").strip() for name in names)


def configured_names(env: os._Environ[str] | dict[str, str], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if env.get(name, "").strip()]


def decode_codex_auth_json_b64(value: str) -> bytes:
    decoded = base64.b64decode(value, validate=True)
    parsed = json.loads(decoded.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("decoded payload must be a JSON object")
    return decoded


def validate_nonnegative_float(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    value = env.get(name, "").strip()
    if not value:
        return
    try:
        parsed = float(value)
    except ValueError:
        errors.append(f"{name} must be a number of seconds")
        return
    if parsed < 0:
        errors.append(f"{name} must be greater than or equal to 0")


def validate_positive_float(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    value = env.get(name, "").strip()
    if not value:
        return
    try:
        parsed = float(value)
    except ValueError:
        errors.append(f"{name} must be a positive number of seconds")
        return
    if parsed <= 0:
        errors.append(f"{name} must be greater than 0")


def validate_nonnegative_int(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    value = env.get(name, "").strip()
    if not value:
        return
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return
    if parsed < 0:
        errors.append(f"{name} must be greater than or equal to 0")


def validate_positive_int(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    value = env.get(name, "").strip()
    if not value:
        return
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return
    if parsed <= 0:
        errors.append(f"{name} must be greater than 0")


def validate_worker_environment(
    env: os._Environ[str] | dict[str, str] | None = None,
    command_lookup: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Return actionable Render startup configuration errors without exposing secrets."""
    env = env if env is not None else os.environ
    errors: list[str] = []
    if command_lookup is None:
        path = env.get("PATH")

        def command_lookup(command: str) -> str | None:
            return shutil.which(command, path=path)

    relay_url = env.get("AUTOMOAT_RELAY_URL", "").strip()
    if not relay_url:
        errors.append("AUTOMOAT_RELAY_URL is required")
    elif not relay_url.startswith(("http://", "https://")):
        errors.append("AUTOMOAT_RELAY_URL must start with http:// or https://")
    else:
        parsed_relay_url = urlparse(relay_url)
        if not parsed_relay_url.netloc:
            errors.append("AUTOMOAT_RELAY_URL must include a host")
        elif parsed_relay_url.username or parsed_relay_url.password:
            errors.append("AUTOMOAT_RELAY_URL must not include embedded credentials")

    if not env.get("AUTOMOAT_RELAY_TOKEN", "").strip():
        errors.append("AUTOMOAT_RELAY_TOKEN is required")
    if not env_has_any(env, GIT_AUTH_ENV_NAMES):
        errors.append("GITHUB_TOKEN or GH_TOKEN is required")
    if not env_has_any(env, CODEX_AUTH_ENV_NAMES):
        errors.append("CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required")

    auth_b64 = env.get("CODEX_AUTH_JSON_B64", "").strip()
    if auth_b64:
        try:
            decode_codex_auth_json_b64(auth_b64)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            errors.append("CODEX_AUTH_JSON_B64 must decode to a JSON object")

    validate_positive_float(env, "AUTOMOAT_RELAY_INTERVAL", errors)
    validate_positive_float(env, "AUTOMOAT_RELAY_TIMEOUT", errors)
    validate_nonnegative_int(env, "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES", errors)
    validate_nonnegative_int(env, "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES", errors)
    validate_positive_int(env, "AUTOMOAT_RELAY_TAIL_LINES", errors)
    validate_positive_int(env, "AUTOMOAT_RELAY_MAX_LOG_BYTES", errors)
    validate_positive_int(env, "AUTOMOAT_STATUS_STALE_AFTER_SECONDS", errors)
    validate_nonnegative_float(env, "AUTOMOAT_AGENT_INTERVAL", errors)
    validate_nonnegative_int(env, "AUTOMOAT_AGENT_ITERATIONS", errors)

    for command in REQUIRED_COMMANDS:
        if not command_lookup(command):
            errors.append(f"{command} executable is required on PATH")
    return errors


def emit_environment_preflight(
    env: os._Environ[str] | dict[str, str] | None = None,
    command_lookup: Callable[[str], str | None] | None = None,
) -> list[str]:
    env = env if env is not None else os.environ
    errors = validate_worker_environment(env, command_lookup)
    if errors:
        emit("environment preflight failed")
        for error in errors:
            emit(f"  - {error}")
        return errors

    emit(
        "environment preflight passed: "
        f"relay_url={env.get('AUTOMOAT_RELAY_URL', '').strip()} "
        f"git_auth={','.join(configured_names(env, GIT_AUTH_ENV_NAMES))} "
        f"codex_auth={','.join(configured_names(env, CODEX_AUTH_ENV_NAMES))} "
        f"agent_interval={env.get('AUTOMOAT_AGENT_INTERVAL', '300')} "
        f"relay_interval={env.get('AUTOMOAT_RELAY_INTERVAL', '3')} "
        f"relay_timeout={env.get('AUTOMOAT_RELAY_TIMEOUT', '8')} "
        f"relay_max_consecutive_failures="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES', '3')} "
        f"relay_max_consecutive_stale_statuses="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES', '0')} "
        f"relay_tail_lines={env.get('AUTOMOAT_RELAY_TAIL_LINES', '180')} "
        f"relay_max_log_bytes={env.get('AUTOMOAT_RELAY_MAX_LOG_BYTES', str(256 * 1024))} "
        f"status_stale_after_seconds={env.get('AUTOMOAT_STATUS_STALE_AFTER_SECONDS', '660')} "
        f"commands={','.join(REQUIRED_COMMANDS)}"
    )
    return []


def run(command: list[str], *, cwd: Path | None = None, input_text: str | None = None) -> None:
    printable = " ".join(command)
    emit(f"$ {printable}")
    result = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    if result.stdout:
        for line in result.stdout.rstrip().splitlines():
            emit(f"  {line}")
    if result.returncode != 0:
        raise RuntimeError(f"{printable} failed with status {result.returncode}")


def write_codex_config() -> None:
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    config = CODEX_HOME / "config.toml"
    model = os.environ.get("AUTOMOAT_CODEX_MODEL", "gpt-5.5")
    reasoning = os.environ.get("AUTOMOAT_CODEX_REASONING_EFFORT", "high")
    config.write_text(
        "\n".join(
            [
                f'model = "{model}"',
                f'model_reasoning_effort = "{reasoning}"',
                'approval_policy = "never"',
                'sandbox_mode = "danger-full-access"',
                "",
                f'[projects."{WORKDIR.as_posix()}"]',
                'trust_level = "trusted"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.environ["CODEX_HOME"] = str(CODEX_HOME)


def configure_codex_auth() -> None:
    write_codex_config()
    auth_b64 = os.environ.get("CODEX_AUTH_JSON_B64", "").strip()
    access_token = os.environ.get("CODEX_ACCESS_TOKEN", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if auth_b64:
        auth_path = CODEX_HOME / "auth.json"
        auth_path.write_bytes(decode_codex_auth_json_b64(auth_b64))
        auth_path.chmod(0o600)
        emit(f"wrote Codex auth file to {auth_path}")
    elif access_token:
        run(["codex", "login", "--with-access-token"], input_text=access_token)
    elif api_key:
        run(["codex", "login", "--with-api-key"], input_text=api_key)
    else:
        raise RuntimeError("CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required")

    run(["codex", "login", "status"])


def configure_git_auth() -> None:
    token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN or GH_TOKEN is required")
    GITHUB_TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    GITHUB_TOKEN_FILE.chmod(0o600)
    GIT_ASKPASS.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "*Username*) echo x-access-token ;;\n"
        "*Password*) cat /tmp/automoat-github-token ;;\n"
        "*) echo ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    GIT_ASKPASS.chmod(0o700)
    os.environ["GIT_ASKPASS"] = str(GIT_ASKPASS)
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ.setdefault("GIT_AUTHOR_NAME", "automoat-render-agent")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "automoat-render-agent@users.noreply.github.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", os.environ["GIT_AUTHOR_NAME"])
    os.environ.setdefault("GIT_COMMITTER_EMAIL", os.environ["GIT_AUTHOR_EMAIL"])
    run(["git", "config", "--global", "user.name", os.environ["GIT_AUTHOR_NAME"]])
    run(["git", "config", "--global", "user.email", os.environ["GIT_AUTHOR_EMAIL"]])


def sync_repo() -> None:
    repo = os.environ.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO)
    branch = os.environ.get("AUTOMOAT_GIT_BRANCH", "main")
    WORKDIR.parent.mkdir(parents=True, exist_ok=True)
    if not (WORKDIR / ".git").exists():
        if WORKDIR.exists():
            shutil.rmtree(WORKDIR)
        run(["git", "clone", "--branch", branch, repo, str(WORKDIR)])
    else:
        run(["git", "fetch", "origin", branch], cwd=WORKDIR)
        run(["git", "checkout", branch], cwd=WORKDIR)
        run(["git", "reset", "--hard", f"origin/{branch}"], cwd=WORKDIR)
    run(["git", "status", "--short", "--branch"], cwd=WORKDIR)


def start_publisher() -> subprocess.Popen[object]:
    require_env("AUTOMOAT_RELAY_URL")
    require_env("AUTOMOAT_RELAY_TOKEN")
    interval = os.environ.get("AUTOMOAT_RELAY_INTERVAL", "3")
    process = subprocess.Popen(
        [sys.executable, "scripts/publish_cockpit_to_relay.py", "--interval", interval],
        cwd=WORKDIR,
        env=os.environ.copy(),
    )
    CHILDREN.append(process)
    emit(f"started relay publisher pid={process.pid}")
    return process


def start_loop() -> subprocess.Popen[object]:
    interval = os.environ.get("AUTOMOAT_AGENT_INTERVAL", "300")
    iterations = os.environ.get("AUTOMOAT_AGENT_ITERATIONS", "0")
    command = [
        sys.executable,
        "scripts/run_autonomous_agent_loop.py",
        "--iterations",
        iterations,
        "--interval",
        interval,
    ]
    process = subprocess.Popen(command, cwd=WORKDIR, env=os.environ.copy())
    CHILDREN.append(process)
    emit(f"started autonomous loop pid={process.pid}")
    return process


def monitor_worker_children(
    loop_process: subprocess.Popen[object],
    publisher_process: subprocess.Popen[object],
    poll_interval: float = 5.0,
) -> int:
    """Return the loop status, or fail fast if cockpit publishing dies first."""
    while True:
        if STOP_REQUESTED:
            stop_children()
            return 0

        loop_status = loop_process.poll()
        if loop_status is not None:
            emit(f"autonomous loop exited status={loop_status}")
            return loop_status

        publisher_status = publisher_process.poll()
        if publisher_status is not None:
            emit(
                "relay publisher exited unexpectedly "
                f"status={publisher_status}; stopping autonomous loop"
            )
            stop_children()
            return publisher_status if publisher_status != 0 else 1

        time.sleep(poll_interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate Render worker environment variables without starting the worker",
    )
    return parser.parse_args()


def stop_children() -> None:
    for child in list(CHILDREN):
        if child.poll() is None:
            child.terminate()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if all(child.poll() is not None for child in CHILDREN):
            return
        time.sleep(0.2)
    for child in list(CHILDREN):
        if child.poll() is None:
            child.kill()


def request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    emit("stop requested")
    stop_children()


def main() -> int:
    args = parse_args()
    env_errors = emit_environment_preflight()
    if args.check_env:
        return 0 if not env_errors else 2
    if env_errors:
        return 2

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    configure_git_auth()
    configure_codex_auth()
    sync_repo()
    publisher = start_publisher()
    loop = start_loop()
    return monitor_worker_children(loop, publisher)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - make Render logs immediately actionable.
        emit(f"fatal: {exc}")
        stop_children()
        raise
