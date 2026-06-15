#!/usr/bin/env python3
"""Run the real Autom oat Codex loop inside Render and publish cockpit snapshots."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_REPO = "https://github.com/matthoffner/tuner-landing.git"
WORKDIR = Path(os.environ.get("AUTOMOAT_WORKDIR", "/work/automoat"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "/tmp/codex-home"))
GIT_ASKPASS = Path("/tmp/automoat-git-askpass.sh")
GITHUB_TOKEN_FILE = Path("/tmp/automoat-github-token")
RESERVED_RUNTIME_FILE_PATHS = (GIT_ASKPASS, GITHUB_TOKEN_FILE)

CHILDREN: list[subprocess.Popen[object]] = []
STOP_REQUESTED = False
STARTUP_CHILD_GRACE_SECONDS = 0.5
CODEX_AUTH_ENV_NAMES = ("CODEX_AUTH_JSON_B64", "CODEX_ACCESS_TOKEN", "OPENAI_API_KEY")
GIT_AUTH_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")
REQUIRED_COMMANDS = ("git", "codex")
CODEX_CONFIG_ENV_DEFAULTS = {
    "AUTOMOAT_CODEX_MODEL": "gpt-5.5",
    "AUTOMOAT_CODEX_REASONING_EFFORT": "high",
}
RUNTIME_CONFIG_LIMITS = {
    "AUTOMOAT_AGENT_INTERVAL": 3600,
    "AUTOMOAT_AGENT_ITERATIONS": 1000,
    "AUTOMOAT_RELAY_INTERVAL": 60,
    "AUTOMOAT_RELAY_TIMEOUT": 60,
    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES": 100,
    "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES": 100,
    "AUTOMOAT_RELAY_TAIL_LINES": 2000,
    "AUTOMOAT_RELAY_MAX_LOG_BYTES": 1024 * 1024,
    "AUTOMOAT_STATUS_STALE_AFTER_SECONDS": 3600,
}
GIT_IDENTITY_ENV_DEFAULTS = {
    "GIT_AUTHOR_NAME": "automoat-render-agent",
    "GIT_AUTHOR_EMAIL": "automoat-render-agent@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "automoat-render-agent",
    "GIT_COMMITTER_EMAIL": "automoat-render-agent@users.noreply.github.com",
}
PUBLISHER_RUNTIME_ENV_ARGS = (
    ("AUTOMOAT_RELAY_INTERVAL", "--interval", "3"),
    ("AUTOMOAT_RELAY_TIMEOUT", "--timeout", "8"),
    ("AUTOMOAT_RELAY_TAIL_LINES", "--tail-lines", "180"),
    ("AUTOMOAT_RELAY_MAX_LOG_BYTES", "--max-log-bytes", str(256 * 1024)),
    ("AUTOMOAT_STATUS_STALE_AFTER_SECONDS", "--status-stale-after-seconds", "660"),
    ("AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES", "--max-consecutive-failures", "3"),
    (
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
        "--max-consecutive-stale-statuses",
        "0",
    ),
)


def emit(message: str) -> None:
    print(f"[render-worker] {message}", flush=True)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def relay_publisher_runtime_config(
    env: os._Environ[str] | dict[str, str],
) -> dict[str, str]:
    return {
        option.lstrip("-").replace("-", "_"): env.get(env_name, default).strip() or default
        for env_name, option, default in PUBLISHER_RUNTIME_ENV_ARGS
    }


def relay_publisher_command(
    env: os._Environ[str] | dict[str, str],
) -> list[str]:
    command = [sys.executable, "scripts/publish_cockpit_to_relay.py"]
    for env_name, option, default in PUBLISHER_RUNTIME_ENV_ARGS:
        command.extend([option, env.get(env_name, default).strip() or default])
    return command


def env_has_any(env: os._Environ[str] | dict[str, str], names: tuple[str, ...]) -> bool:
    return any(env.get(name, "").strip() for name in names)


def configured_names(env: os._Environ[str] | dict[str, str], names: tuple[str, ...]) -> list[str]:
    return [name for name in names if env.get(name, "").strip()]


def selected_name(env: os._Environ[str] | dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if env.get(name, "").strip():
            return name
    return None


def configured_worker_paths(env: os._Environ[str] | dict[str, str]) -> tuple[Path, Path]:
    workdir = Path(env["AUTOMOAT_WORKDIR"]) if "AUTOMOAT_WORKDIR" in env else WORKDIR
    codex_home = Path(env["CODEX_HOME"]) if "CODEX_HOME" in env else CODEX_HOME
    return workdir, codex_home


def decode_codex_auth_json_b64(value: str) -> bytes:
    decoded = base64.b64decode(value, validate=True)
    parsed = json.loads(decoded.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("decoded payload must be a JSON object")
    return decoded


def validated_runtime_env_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> str | None:
    if name not in env:
        return None
    value = env.get(name, "")
    if not value.strip():
        errors.append(f"{name} must not be empty")
        return None
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")
        return None
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line runtime value without control characters")
        return None
    return value


def validate_nonnegative_float(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
    *,
    maximum: float | None = None,
) -> None:
    value = validated_runtime_env_value(env, name, errors)
    if value is None:
        return
    try:
        parsed = float(value)
    except ValueError:
        errors.append(f"{name} must be a number of seconds")
        return
    if not math.isfinite(parsed):
        errors.append(f"{name} must be a finite number of seconds")
        return
    if parsed < 0:
        errors.append(f"{name} must be greater than or equal to 0")
        return
    if maximum is not None and parsed > maximum:
        errors.append(f"{name} must be less than or equal to {format_number(maximum)}")


def validate_positive_float(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
    *,
    maximum: float | None = None,
) -> None:
    value = validated_runtime_env_value(env, name, errors)
    if value is None:
        return
    try:
        parsed = float(value)
    except ValueError:
        errors.append(f"{name} must be a positive number of seconds")
        return
    if not math.isfinite(parsed):
        errors.append(f"{name} must be a finite number of seconds")
        return
    if parsed <= 0:
        errors.append(f"{name} must be greater than 0")
        return
    if maximum is not None and parsed > maximum:
        errors.append(f"{name} must be less than or equal to {format_number(maximum)}")


def validate_nonnegative_int(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
    *,
    maximum: int | None = None,
) -> None:
    value = validated_runtime_env_value(env, name, errors)
    if value is None:
        return
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return
    if parsed < 0:
        errors.append(f"{name} must be greater than or equal to 0")
        return
    if maximum is not None and parsed > maximum:
        errors.append(f"{name} must be less than or equal to {maximum}")


def validate_positive_int(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
    *,
    maximum: int | None = None,
) -> None:
    value = validated_runtime_env_value(env, name, errors)
    if value is None:
        return
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{name} must be an integer")
        return
    if parsed <= 0:
        errors.append(f"{name} must be greater than 0")
        return
    if maximum is not None and parsed > maximum:
        errors.append(f"{name} must be less than or equal to {maximum}")


def format_number(value: float | int) -> str:
    parsed = float(value)
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def codex_config_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
) -> str:
    raw_value = env.get(name)
    if raw_value is None:
        return CODEX_CONFIG_ENV_DEFAULTS[name]
    return raw_value.strip()


def validate_codex_config_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    if name not in env:
        return
    value = env.get(name, "")
    if not value.strip():
        errors.append(f"{name} must not be empty")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line value without control characters")
        return
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")


def validate_git_identity_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> None:
    if name not in env:
        return
    value = env.get(name, "")
    if not value.strip():
        errors.append(f"{name} must not be empty")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line value without control characters")
        return
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")
        return
    if name.endswith("_EMAIL") and not is_plain_git_email(value):
        errors.append(f"{name} must be a plain email address with one @")


def is_plain_git_email(value: str) -> bool:
    if value.count("@") != 1:
        return False
    local_part, domain_part = value.split("@", 1)
    if not local_part or not domain_part:
        return False
    if any(character in "<>()[],:;\\\"" for character in value):
        return False
    if domain_part.startswith(".") or domain_part.endswith(".") or ".." in domain_part:
        return False
    return True


def validate_secret_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> bool:
    if name not in env:
        return True
    value = env.get(name, "")
    if not value.strip():
        return True
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line value without control characters")
        return False
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")
        return False
    return True


def toml_basic_string(value: str) -> str:
    return json.dumps(value)


def validate_worker_environment(
    env: os._Environ[str] | dict[str, str] | None = None,
    command_lookup: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Return actionable Render startup configuration errors without exposing secrets."""
    env = env if env is not None else os.environ
    errors: list[str] = []
    command_paths = resolved_required_command_paths(env, command_lookup)

    relay_url = env.get("AUTOMOAT_RELAY_URL", "")
    validate_secret_safe_http_url(
        "AUTOMOAT_RELAY_URL",
        relay_url,
        errors,
        required=True,
    )
    git_repo = env.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO)
    validate_secret_safe_http_url(
        "AUTOMOAT_GIT_REPO",
        git_repo,
        errors,
        required=True,
        require_path=True,
    )
    validate_git_branch_name(env.get("AUTOMOAT_GIT_BRANCH", "main"), errors)
    workdir, codex_home = configured_worker_paths(env)
    validate_workdir_path(workdir, errors, codex_home=codex_home)
    validate_codex_home_path(codex_home, workdir, errors)
    validate_reserved_runtime_file_paths(errors)

    if not env.get("AUTOMOAT_RELAY_TOKEN", "").strip():
        errors.append("AUTOMOAT_RELAY_TOKEN is required")
    if not env_has_any(env, GIT_AUTH_ENV_NAMES):
        errors.append("GITHUB_TOKEN or GH_TOKEN is required")
    if not env_has_any(env, CODEX_AUTH_ENV_NAMES):
        errors.append("CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required")

    invalid_secret_names = {
        name
        for name in ("AUTOMOAT_RELAY_TOKEN", *GIT_AUTH_ENV_NAMES, *CODEX_AUTH_ENV_NAMES)
        if not validate_secret_value(env, name, errors)
    }

    auth_b64 = env.get("CODEX_AUTH_JSON_B64", "").strip()
    if auth_b64 and "CODEX_AUTH_JSON_B64" not in invalid_secret_names:
        try:
            decode_codex_auth_json_b64(auth_b64)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            errors.append("CODEX_AUTH_JSON_B64 must decode to a JSON object")

    validate_positive_float(
        env,
        "AUTOMOAT_RELAY_INTERVAL",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_INTERVAL"],
    )
    validate_positive_float(
        env,
        "AUTOMOAT_RELAY_TIMEOUT",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_TIMEOUT"],
    )
    validate_nonnegative_int(
        env,
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES"],
    )
    validate_nonnegative_int(
        env,
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES"],
    )
    validate_positive_int(
        env,
        "AUTOMOAT_RELAY_TAIL_LINES",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_TAIL_LINES"],
    )
    validate_positive_int(
        env,
        "AUTOMOAT_RELAY_MAX_LOG_BYTES",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_RELAY_MAX_LOG_BYTES"],
    )
    validate_positive_int(
        env,
        "AUTOMOAT_STATUS_STALE_AFTER_SECONDS",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_STATUS_STALE_AFTER_SECONDS"],
    )
    validate_nonnegative_float(
        env,
        "AUTOMOAT_AGENT_INTERVAL",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_AGENT_INTERVAL"],
    )
    validate_nonnegative_int(
        env,
        "AUTOMOAT_AGENT_ITERATIONS",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_AGENT_ITERATIONS"],
    )
    validate_codex_config_value(env, "AUTOMOAT_CODEX_MODEL", errors)
    validate_codex_config_value(env, "AUTOMOAT_CODEX_REASONING_EFFORT", errors)
    for name in GIT_IDENTITY_ENV_DEFAULTS:
        validate_git_identity_value(env, name, errors)

    for command, resolved_path in command_paths.items():
        if not resolved_path:
            errors.append(f"{command} executable is required on PATH")
    return errors


def resolved_required_command_paths(
    env: os._Environ[str] | dict[str, str],
    command_lookup: Callable[[str], str | None] | None = None,
) -> dict[str, str | None]:
    if command_lookup is None:
        path = env.get("PATH")

        def command_lookup(command: str) -> str | None:
            return shutil.which(command, path=path)

    return {
        command: command_lookup(command) or None
        for command in REQUIRED_COMMANDS
    }


def validate_secret_safe_http_url(
    name: str,
    value: str,
    errors: list[str],
    *,
    required: bool,
    require_path: bool = False,
) -> None:
    if not value:
        if required:
            errors.append(f"{name} is required")
        return
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line URL without control characters")
        return
    if any(character.isspace() for character in value):
        errors.append(f"{name} must not contain whitespace")
        return
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        errors.append(f"{name} must start with http:// or https://")
        return
    try:
        parsed_value = urlparse(value)
    except ValueError:
        errors.append(f"{name} must be a valid URL")
        return

    if not parsed_value.netloc or not parsed_value.hostname:
        errors.append(f"{name} must include a host")
    elif parsed_value.username or parsed_value.password:
        errors.append(f"{name} must not include embedded credentials")
    elif parsed_value.query or parsed_value.fragment:
        errors.append(f"{name} must not include query strings or fragments")
    elif require_path and not parsed_value.path.strip("/"):
        errors.append(f"{name} must include a repository path")
    else:
        if require_path and parsed_value.hostname == "github.com":
            path_parts = [part for part in parsed_value.path.split("/") if part]
            if len(path_parts) < 2:
                errors.append(f"{name} must include owner and repository path")
            elif len(path_parts) > 2:
                errors.append(f"{name} must not include path components after the repository")
            elif path_parts[1] == ".git":
                errors.append(f"{name} repository name must not be empty")
        host_port = parsed_value.netloc.rsplit("@", 1)[-1]
        try:
            port = parsed_value.port
        except ValueError:
            errors.append(f"{name} must include a valid port when a port is specified")
            return
        if host_port.endswith(":") or port == 0:
            errors.append(f"{name} must include a valid port when a port is specified")


def preflight_error_category(error: str) -> str:
    if error.endswith(" is required"):
        return "missing_required"
    if error.startswith("AUTOMOAT_RELAY_URL") or error.startswith("AUTOMOAT_GIT_REPO"):
        return "invalid_url"
    if error.startswith("AUTOMOAT_GIT_BRANCH"):
        return "invalid_git_branch"
    if error.startswith("AUTOMOAT_WORKDIR") or error.startswith("CODEX_HOME"):
        return "invalid_path"
    if error.startswith("reserved runtime file "):
        return "invalid_path"
    if error.startswith("CODEX_AUTH_JSON_B64 must decode"):
        return "invalid_codex_auth_payload"
    if error.startswith("AUTOMOAT_CODEX_"):
        return "invalid_codex_config"
    if any(error.startswith(name) for name in RUNTIME_CONFIG_LIMITS):
        return "invalid_runtime_config"
    if error.startswith("GIT_AUTHOR_") or error.startswith("GIT_COMMITTER_"):
        return "invalid_git_identity"
    if (
        "single-line value without control characters" in error
        or "must not include leading or trailing whitespace" in error
    ):
        return "invalid_secret_or_identity"
    if error.endswith(" executable is required on PATH"):
        return "missing_command"
    if error.startswith("AUTOMOAT_"):
        return "invalid_runtime_config"
    return "invalid_configuration"


def preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({preflight_error_category(error) for error in errors})


def validate_git_branch_name(value: str, errors: list[str]) -> None:
    if value != value.strip():
        errors.append("AUTOMOAT_GIT_BRANCH must not include leading or trailing whitespace")
        return
    branch = value.strip()
    if not branch:
        errors.append("AUTOMOAT_GIT_BRANCH must not be empty")
        return
    if branch.startswith("-"):
        errors.append("AUTOMOAT_GIT_BRANCH must not start with -")
        return
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in branch
    ):
        errors.append("AUTOMOAT_GIT_BRANCH must not contain whitespace or control characters")
        return

    branch_components = branch.split("/")
    invalid_fragments = ("..", "//", "@{", "\\")
    invalid_characters = set("~^:?*[")
    if (
        branch == "@"
        or branch.startswith("/")
        or branch.endswith("/")
        or branch.endswith(".")
        or any(component.startswith(".") for component in branch_components)
        or any(component.endswith(".lock") for component in branch_components)
        or any(fragment in branch for fragment in invalid_fragments)
        or any(character in invalid_characters for character in branch)
    ):
        errors.append("AUTOMOAT_GIT_BRANCH must be a valid git branch name")


def validate_workdir_path(path: Path, errors: list[str], *, codex_home: Path | None = None) -> None:
    path_text = str(path)
    if path_text != path_text.strip():
        errors.append("AUTOMOAT_WORKDIR must not include leading or trailing whitespace")
        return

    raw_path = path_text.strip()
    if not raw_path:
        errors.append("AUTOMOAT_WORKDIR must not be empty")
        return

    expanded_path = path.expanduser()
    if not expanded_path.is_absolute():
        errors.append("AUTOMOAT_WORKDIR must be an absolute path")
        return

    try:
        resolved_path = expanded_path.resolve(strict=False)
        codex_home_path = codex_home if codex_home is not None else CODEX_HOME
        resolved_codex_home = codex_home_path.expanduser().resolve(strict=False)
    except OSError as exc:
        errors.append(f"AUTOMOAT_WORKDIR could not be resolved: {exc}")
        return

    named_parts = [part for part in resolved_path.parts if part != resolved_path.anchor]
    if len(named_parts) < 2:
        errors.append("AUTOMOAT_WORKDIR must not be filesystem root or a top-level directory")
        return

    if resolved_path == resolved_codex_home:
        errors.append("AUTOMOAT_WORKDIR must not equal CODEX_HOME")
        return

    conflicting_runtime_file = reserved_runtime_file_conflict(resolved_path)
    if conflicting_runtime_file is not None:
        errors.append(
            "AUTOMOAT_WORKDIR must not be equal to or inside reserved runtime file "
            f"{conflicting_runtime_file}"
        )
        return

    blocking_path = blocking_directory_path_component(resolved_path)
    if blocking_path is not None:
        errors.append(f"AUTOMOAT_WORKDIR path component {blocking_path} must be a directory")
        return


def validate_codex_home_path(path: Path, workdir: Path, errors: list[str]) -> None:
    path_text = str(path)
    if path_text != path_text.strip():
        errors.append("CODEX_HOME must not include leading or trailing whitespace")
        return

    raw_path = path_text.strip()
    if not raw_path:
        errors.append("CODEX_HOME must not be empty")
        return

    expanded_path = path.expanduser()
    if not expanded_path.is_absolute():
        errors.append("CODEX_HOME must be an absolute path")
        return

    try:
        resolved_path = expanded_path.resolve(strict=False)
    except OSError as exc:
        errors.append(f"CODEX_HOME could not be resolved: {exc}")
        return

    named_parts = [part for part in resolved_path.parts if part != resolved_path.anchor]
    if len(named_parts) < 2:
        errors.append("CODEX_HOME must not be filesystem root or a top-level directory")
        return

    conflicting_runtime_file = reserved_runtime_file_conflict(resolved_path)
    if conflicting_runtime_file is not None:
        errors.append(
            "CODEX_HOME must not be equal to or inside reserved runtime file "
            f"{conflicting_runtime_file}"
        )
        return

    blocking_path = blocking_directory_path_component(resolved_path)
    if blocking_path is not None:
        errors.append(f"CODEX_HOME path component {blocking_path} must be a directory")
        return

    expanded_workdir = workdir.expanduser()
    workdir_named_parts = [
        part for part in expanded_workdir.parts if part != expanded_workdir.anchor
    ]
    if not expanded_workdir.is_absolute() or len(workdir_named_parts) < 2:
        return

    try:
        resolved_workdir = expanded_workdir.resolve(strict=False)
    except OSError:
        return

    if resolved_path == resolved_workdir:
        return
    if resolved_path.is_relative_to(resolved_workdir):
        errors.append("CODEX_HOME must not be inside AUTOMOAT_WORKDIR")
        return
    if resolved_workdir.is_relative_to(resolved_path):
        errors.append("CODEX_HOME must not contain AUTOMOAT_WORKDIR")


def blocking_directory_path_component(path: Path) -> Path | None:
    current_path = path
    while True:
        if current_path.exists():
            return None if current_path.is_dir() else current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent


def reserved_runtime_file_conflict(path: Path) -> Path | None:
    for runtime_file in RESERVED_RUNTIME_FILE_PATHS:
        try:
            resolved_runtime_file = runtime_file.expanduser().resolve(strict=False)
        except OSError:
            resolved_runtime_file = runtime_file.expanduser().absolute()
        if path == resolved_runtime_file or path.is_relative_to(resolved_runtime_file):
            return resolved_runtime_file
    return None


def validate_reserved_runtime_file_paths(errors: list[str]) -> None:
    for runtime_file in RESERVED_RUNTIME_FILE_PATHS:
        expanded_path = runtime_file.expanduser()
        try:
            resolved_path = expanded_path.resolve(strict=False)
        except OSError as exc:
            errors.append(f"reserved runtime file {runtime_file} could not be resolved: {exc}")
            continue

        if resolved_path.exists() and not resolved_path.is_file():
            errors.append(f"reserved runtime file {runtime_file} must be a regular file")
            continue

        parent = resolved_path.parent
        if not parent.exists():
            errors.append(f"reserved runtime file {runtime_file} parent directory must exist")
        elif not parent.is_dir():
            errors.append(f"reserved runtime file {runtime_file} parent path must be a directory")


def environment_preflight_summary(
    env: os._Environ[str] | dict[str, str],
    errors: list[str],
    command_paths: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    command_paths = command_paths or resolved_required_command_paths(env)
    workdir, codex_home = configured_worker_paths(env)
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": preflight_error_categories(errors),
            "git_auth": configured_names(env, GIT_AUTH_ENV_NAMES),
            "git_auth_selected": selected_name(env, GIT_AUTH_ENV_NAMES),
            "codex_auth": configured_names(env, CODEX_AUTH_ENV_NAMES),
            "codex_auth_selected": selected_name(env, CODEX_AUTH_ENV_NAMES),
            "commands": list(REQUIRED_COMMANDS),
            "command_paths": command_paths,
            "runtime_limits": RUNTIME_CONFIG_LIMITS,
        }
        return payload

    payload["config"] = {
        "relay_url": env.get("AUTOMOAT_RELAY_URL", "").strip(),
        "git_repo": env.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO).strip(),
        "git_branch": env.get("AUTOMOAT_GIT_BRANCH", "main").strip() or "main",
        "workdir": str(workdir),
        "codex_home": str(codex_home),
        "git_auth": configured_names(env, GIT_AUTH_ENV_NAMES),
        "git_auth_selected": selected_name(env, GIT_AUTH_ENV_NAMES),
        "codex_auth": configured_names(env, CODEX_AUTH_ENV_NAMES),
        "codex_auth_selected": selected_name(env, CODEX_AUTH_ENV_NAMES),
        "agent_interval": env.get("AUTOMOAT_AGENT_INTERVAL", "300"),
        "agent_iterations": env.get("AUTOMOAT_AGENT_ITERATIONS", "0"),
        "relay_interval": env.get("AUTOMOAT_RELAY_INTERVAL", "3"),
        "relay_timeout": env.get("AUTOMOAT_RELAY_TIMEOUT", "8"),
        "relay_max_consecutive_failures": env.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
            "3",
        ),
        "relay_max_consecutive_stale_statuses": env.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
            "0",
        ),
        "relay_tail_lines": env.get("AUTOMOAT_RELAY_TAIL_LINES", "180"),
        "relay_max_log_bytes": env.get("AUTOMOAT_RELAY_MAX_LOG_BYTES", str(256 * 1024)),
        "status_stale_after_seconds": env.get(
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS",
            "660",
        ),
        "codex_model": codex_config_value(env, "AUTOMOAT_CODEX_MODEL"),
        "codex_reasoning_effort": codex_config_value(
            env,
            "AUTOMOAT_CODEX_REASONING_EFFORT",
        ),
        "commands": list(REQUIRED_COMMANDS),
        "command_paths": command_paths,
        "runtime_limits": RUNTIME_CONFIG_LIMITS,
    }
    return payload


def emit_environment_preflight(
    env: os._Environ[str] | dict[str, str] | None = None,
    command_lookup: Callable[[str], str | None] | None = None,
    *,
    output_format: str = "text",
) -> list[str]:
    env = env if env is not None else os.environ
    errors = validate_worker_environment(env, command_lookup)
    command_paths = resolved_required_command_paths(env, command_lookup)
    if output_format == "json":
        print(
            json.dumps(
                environment_preflight_summary(env, errors, command_paths),
                sort_keys=True,
            ),
            flush=True,
        )
        return errors

    if errors:
        emit("environment preflight failed")
        for error in errors:
            emit(f"  - {error}")
        return errors

    workdir, codex_home = configured_worker_paths(env)
    emit(
        "environment preflight passed: "
        f"relay_url={env.get('AUTOMOAT_RELAY_URL', '').strip()} "
        f"git_repo={env.get('AUTOMOAT_GIT_REPO', DEFAULT_REPO).strip()} "
        f"git_branch={env.get('AUTOMOAT_GIT_BRANCH', 'main').strip() or 'main'} "
        f"workdir={workdir} "
        f"codex_home={codex_home} "
        f"git_auth={','.join(configured_names(env, GIT_AUTH_ENV_NAMES))} "
        f"git_auth_selected={selected_name(env, GIT_AUTH_ENV_NAMES)} "
        f"codex_auth={','.join(configured_names(env, CODEX_AUTH_ENV_NAMES))} "
        f"codex_auth_selected={selected_name(env, CODEX_AUTH_ENV_NAMES)} "
        f"agent_interval={env.get('AUTOMOAT_AGENT_INTERVAL', '300')} "
        f"agent_iterations={env.get('AUTOMOAT_AGENT_ITERATIONS', '0')} "
        f"relay_interval={env.get('AUTOMOAT_RELAY_INTERVAL', '3')} "
        f"relay_timeout={env.get('AUTOMOAT_RELAY_TIMEOUT', '8')} "
        f"relay_max_consecutive_failures="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES', '3')} "
        f"relay_max_consecutive_stale_statuses="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES', '0')} "
        f"relay_tail_lines={env.get('AUTOMOAT_RELAY_TAIL_LINES', '180')} "
        f"relay_max_log_bytes={env.get('AUTOMOAT_RELAY_MAX_LOG_BYTES', str(256 * 1024))} "
        f"status_stale_after_seconds={env.get('AUTOMOAT_STATUS_STALE_AFTER_SECONDS', '660')} "
        f"codex_model={codex_config_value(env, 'AUTOMOAT_CODEX_MODEL')} "
        f"codex_reasoning_effort="
        f"{codex_config_value(env, 'AUTOMOAT_CODEX_REASONING_EFFORT')} "
        f"commands={','.join(REQUIRED_COMMANDS)} "
        f"command_paths={json.dumps(command_paths, sort_keys=True)} "
        f"runtime_limits={json.dumps(RUNTIME_CONFIG_LIMITS, sort_keys=True)}"
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
    model = codex_config_value(os.environ, "AUTOMOAT_CODEX_MODEL")
    reasoning = codex_config_value(os.environ, "AUTOMOAT_CODEX_REASONING_EFFORT")
    config.write_text(
        "\n".join(
            [
                f"model = {toml_basic_string(model)}",
                f"model_reasoning_effort = {toml_basic_string(reasoning)}",
                'approval_policy = "never"',
                'sandbox_mode = "danger-full-access"',
                "",
                f"[projects.{toml_basic_string(WORKDIR.as_posix())}]",
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
    os.environ.setdefault("GIT_AUTHOR_NAME", GIT_IDENTITY_ENV_DEFAULTS["GIT_AUTHOR_NAME"])
    os.environ.setdefault("GIT_AUTHOR_EMAIL", GIT_IDENTITY_ENV_DEFAULTS["GIT_AUTHOR_EMAIL"])
    os.environ.setdefault("GIT_COMMITTER_NAME", os.environ["GIT_AUTHOR_NAME"])
    os.environ.setdefault("GIT_COMMITTER_EMAIL", os.environ["GIT_AUTHOR_EMAIL"])
    run(["git", "config", "--global", "user.name", os.environ["GIT_AUTHOR_NAME"]])
    run(["git", "config", "--global", "user.email", os.environ["GIT_AUTHOR_EMAIL"]])


def sync_repo() -> None:
    repo = os.environ.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO)
    branch = os.environ.get("AUTOMOAT_GIT_BRANCH", "main").strip() or "main"
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
    command = relay_publisher_command(os.environ)
    runtime_config = relay_publisher_runtime_config(os.environ)
    process = subprocess.Popen(
        command,
        cwd=WORKDIR,
        env=os.environ.copy(),
    )
    CHILDREN.append(process)
    runtime_fields = " ".join(
        f"publisher_{key}={value}" for key, value in runtime_config.items()
    )
    emit(f"started relay publisher pid={process.pid} {runtime_fields}")
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


def child_startup_exit_status(
    process: subprocess.Popen[object],
    label: str,
    *,
    clean_exit_status: int | None = None,
    grace_seconds: float = STARTUP_CHILD_GRACE_SECONDS,
) -> int | None:
    """Return a child exit status if it dies during startup, otherwise None."""
    if grace_seconds > 0:
        time.sleep(grace_seconds)
    status = process.poll()
    if status is None:
        return None

    worker_status = clean_exit_status if status == 0 and clean_exit_status is not None else status
    emit(
        f"{label} exited during startup status={status}; "
        f"worker_exit_status={worker_status}"
    )
    return worker_status


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
            stop_children()
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
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for --check-env preflight results",
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
    if args.format == "json" and not args.check_env:
        emit("--format json is only supported with --check-env")
        return 2

    env_errors = emit_environment_preflight(output_format=args.format)
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
    publisher_startup_status = child_startup_exit_status(
        publisher,
        "relay publisher",
        clean_exit_status=1,
    )
    if publisher_startup_status is not None:
        stop_children()
        return publisher_startup_status

    loop = start_loop()
    loop_startup_status = child_startup_exit_status(loop, "autonomous loop")
    if loop_startup_status is not None:
        stop_children()
        return loop_startup_status

    return monitor_worker_children(loop, publisher)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - make Render logs immediately actionable.
        emit(f"fatal: {exc}")
        stop_children()
        raise
