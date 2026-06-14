#!/usr/bin/env python3
"""Run the real Autom oat Codex loop inside Render and publish cockpit snapshots."""

from __future__ import annotations

import base64
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_REPO = "https://github.com/matthoffner/tuner-landing.git"
WORKDIR = Path(os.environ.get("AUTOMOAT_WORKDIR", "/work/automoat"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "/tmp/codex-home"))
GIT_ASKPASS = Path("/tmp/automoat-git-askpass.sh")
GITHUB_TOKEN_FILE = Path("/tmp/automoat-github-token")

CHILDREN: list[subprocess.Popen[object]] = []
STOP_REQUESTED = False


def emit(message: str) -> None:
    print(f"[render-worker] {message}", flush=True)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


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
        auth_path.write_bytes(base64.b64decode(auth_b64))
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


def run_loop() -> int:
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
    return process.wait()


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
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    configure_git_auth()
    configure_codex_auth()
    sync_repo()
    start_publisher()
    status = run_loop()
    if STOP_REQUESTED:
        return 0
    emit(f"autonomous loop exited status={status}")
    return status


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - make Render logs immediately actionable.
        emit(f"fatal: {exc}")
        stop_children()
        raise
