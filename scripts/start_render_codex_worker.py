#!/usr/bin/env python3
"""Run the real Autom oat Codex loop inside Render and publish cockpit snapshots."""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_REPO = "https://github.com/matthoffner/tuner-landing.git"
WORKDIR = Path(os.environ.get("AUTOMOAT_WORKDIR", "/work/automoat"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "/tmp/codex-home"))
GIT_ASKPASS = Path("/tmp/automoat-git-askpass.sh")
GITHUB_TOKEN_FILE = Path("/tmp/automoat-github-token")
RESERVED_RUNTIME_FILE_PATHS = (GIT_ASKPASS, GITHUB_TOKEN_FILE)

CHILDREN: list[subprocess.Popen[object]] = []
STOP_REQUESTED = False
STARTUP_CHILD_GRACE_SECONDS = 0.5
PUBLISHER_PREFLIGHT_TIMEOUT_SECONDS = 15.0
PUBLISHER_PREFLIGHT_MAX_OUTPUT_BYTES = 64 * 1024
PUBLISHER_PREFLIGHT_DIAGNOSTIC_TOKEN_LIMIT = 12
CHILD_POLL_FAILURE_EXIT_STATUS = 1
CODEX_AUTH_ENV_NAMES = ("CODEX_AUTH_JSON_B64", "CODEX_ACCESS_TOKEN", "OPENAI_API_KEY")
GIT_AUTH_ENV_NAMES = ("GITHUB_TOKEN", "GH_TOKEN")
SECRET_ENV_NAMES = ("AUTOMOAT_RELAY_TOKEN", *GIT_AUTH_ENV_NAMES, *CODEX_AUTH_ENV_NAMES)
GIT_CONFIG_ENV_NAMES = ("AUTOMOAT_GIT_REPO", "AUTOMOAT_GIT_BRANCH")
URL_TEXT_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
BEARER_SECRET_PATTERN = re.compile(
    r"\b(authorization\s*[:=]\s*bearer)\s+[^\s,;]+",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|relay_token|access_token|api_key|x-automoat-relay-token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
URL_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
REQUIRED_COMMANDS = ("git", "codex")
CODEX_CONFIG_ENV_DEFAULTS = {
    "AUTOMOAT_CODEX_MODEL": "gpt-5.5",
    "AUTOMOAT_CODEX_REASONING_EFFORT": "high",
}
MAX_CODEX_CONFIG_VALUE_CHARS = 120
MAX_SECRET_VALUE_CHARS = 8192
MAX_RUNTIME_CONFIG_VALUE_CHARS = 64
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
    "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS": 3600,
}
WORKER_PATH_ENV_NAMES = ("AUTOMOAT_WORKDIR", "CODEX_HOME")
DEFAULT_STATUS_FILE = ".automoat/state/mvp-loop-status.json"
DEFAULT_PID_FILE = ".automoat/state/mvp-loop.pid"
DEFAULT_LOG_FILE = ".automoat/logs/mvp-loop.log"
DEFAULT_PUBLISHER_LOG = ".automoat/logs/cockpit-relay-publisher.log"
DEFAULT_BRIDGE_STATUS_FILE = ".automoat/state/mvp-bridge-status.json"
PUBLISHER_FILE_ENV_ARGS = (
    ("AUTOMOAT_LOOP_STATUS_FILE", "--status-file", DEFAULT_STATUS_FILE),
    ("AUTOMOAT_LOOP_PID_FILE", "--pid-file", DEFAULT_PID_FILE),
    ("AUTOMOAT_LOOP_LOG_FILE", "--log-file", DEFAULT_LOG_FILE),
    ("AUTOMOAT_PUBLISHER_LOG_FILE", "--publisher-log", DEFAULT_PUBLISHER_LOG),
    ("AUTOMOAT_BRIDGE_STATUS_FILE", "--bridge-status-file", DEFAULT_BRIDGE_STATUS_FILE),
)
PUBLISHER_FILE_PATH_ENV_NAMES = tuple(
    env_name for env_name, _option, _default in PUBLISHER_FILE_ENV_ARGS
)
MAX_GIT_BRANCH_CHARS = 240
PORTABLE_GIT_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")
GIT_PSEUDO_REF_NAMES = {
    "AUTO_MERGE",
    "BISECT_HEAD",
    "CHERRY_PICK_HEAD",
    "FETCH_HEAD",
    "HEAD",
    "MERGE_HEAD",
    "ORIG_HEAD",
    "REVERT_HEAD",
}
GIT_IDENTITY_ENV_DEFAULTS = {
    "GIT_AUTHOR_NAME": "automoat-render-agent",
    "GIT_AUTHOR_EMAIL": "automoat-render-agent@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "automoat-render-agent",
    "GIT_COMMITTER_EMAIL": "automoat-render-agent@users.noreply.github.com",
}
GIT_IDENTITY_CONFIG_KEYS = ("user.name", "user.email")
MAX_GIT_IDENTITY_VALUE_CHARS = 120
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
    (
        "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
        "--bridge-status-stale-after-seconds",
        "660",
    ),
)
MAX_WORKER_URL_CHARS = 500
MAX_WORKER_PATH_CHARS = 500
BUSINESS_HOURS_ENV_DEFAULTS = {
    "AUTOMOAT_BUSINESS_HOURS_ENABLED": "1",
    "AUTOMOAT_BUSINESS_HOURS_TIMEZONE": "America/Chicago",
    "AUTOMOAT_BUSINESS_HOURS_START": "09:00",
    "AUTOMOAT_BUSINESS_HOURS_END": "17:00",
    "AUTOMOAT_BUSINESS_HOURS_DAYS": "mon-fri",
    "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP": "300",
}
MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS = 120
BUSINESS_HOURS_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
BUSINESS_HOURS_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
BUSINESS_HOURS_ENV_NAMES = tuple(BUSINESS_HOURS_ENV_DEFAULTS)
BUSINESS_DAY_NAMES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}
BUSINESS_HOURS_CLOSED = "business_hours_closed"
LOOP_EXITED = "loop_exited"
PUBLISHER_EXITED = "publisher_exited"
RELAY_PUBLISHER_UNAVAILABLE = "relay_publisher_unavailable"
ENVIRONMENT_PREFLIGHT_FAILED = "environment_preflight_failed"
RENDER_WORKER_FAILURE_ROUTE_HINTS = {
    ENVIRONMENT_PREFLIGHT_FAILED,
    "relay_publisher_preflight_failed",
    "relay_publisher_start_failed",
    "relay_publisher_startup_exit",
    PUBLISHER_EXITED,
}


class PublisherPreflightError(RuntimeError):
    """A bounded, secret-safe relay publisher preflight failure."""

    def __init__(
        self,
        message: str,
        *,
        status_label: str | None = None,
        exit_status: int | None = None,
        error_count: int | None = None,
        error_categories: list[str] | None = None,
        failed_configuration_keys: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_label = status_label
        self.exit_status = exit_status
        self.error_count = error_count
        self.error_categories = error_categories or []
        self.failed_configuration_keys = failed_configuration_keys or []


def emit(message: str) -> None:
    print(f"[render-worker] {message}", flush=True)


def sanitize_url_for_worker_log(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    netloc = hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = parsed.path or ""
    if parsed.params:
        path = f"{path};{parsed.params}"
    query = "[redacted]" if parsed.query else ""
    fragment = "[redacted]" if parsed.fragment else ""
    return urlunparse((parsed.scheme, netloc, path, "", query, fragment))


def sanitize_worker_log_text(
    text: str,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> str:
    """Redact copied secrets from Render-visible worker command output."""
    env = env if env is not None else os.environ
    sanitized = "".join(
        " " if character in "\r\n" or ord(character) < 32 or ord(character) == 127
        else character
        for character in text
    )
    sanitized = URL_TEXT_PATTERN.sub(
        lambda match: sanitize_url_for_worker_log(match.group(0)),
        sanitized,
    )
    sanitized = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", sanitized)
    sanitized = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        sanitized,
    )
    secret_values = sorted(
        {
            value.strip()
            for name in SECRET_ENV_NAMES
            if len(value := env.get(name, "")) >= 4 and value.strip()
        },
        key=len,
        reverse=True,
    )
    for secret_value in secret_values:
        sanitized = sanitized.replace(secret_value, "[redacted]")
    identity_values = sorted(
        {
            value.strip()
            for name in GIT_IDENTITY_ENV_DEFAULTS
            if len(value := env.get(name, "")) >= 4 and value.strip()
        },
        key=len,
        reverse=True,
    )
    for identity_value in identity_values:
        sanitized = sanitized.replace(identity_value, "[redacted]")
    return sanitized


def sanitize_worker_config_text(
    value: str,
    env: os._Environ[str] | dict[str, str],
) -> str:
    """Redact copied secrets from otherwise nonsecret preflight config fields."""
    return sanitize_worker_log_text(value, env)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def relay_publisher_runtime_config(
    env: os._Environ[str] | dict[str, str],
) -> dict[str, str]:
    config = {
        option.lstrip("-").replace("-", "_"): env.get(env_name, default).strip() or default
        for env_name, option, default in PUBLISHER_RUNTIME_ENV_ARGS
    }
    for env_name, option, default in PUBLISHER_FILE_ENV_ARGS:
        config[option.lstrip("-").replace("-", "_")] = worker_file_label(
            env.get(env_name, default).strip() or default,
            env,
        )
    return config


def relay_publisher_command(
    env: os._Environ[str] | dict[str, str],
) -> list[str]:
    command = [sys.executable, "scripts/publish_cockpit_to_relay.py"]
    for env_name, option, default in PUBLISHER_RUNTIME_ENV_ARGS:
        command.extend([option, env.get(env_name, default).strip() or default])
    for env_name, option, default in PUBLISHER_FILE_ENV_ARGS:
        command.extend([option, env.get(env_name, default).strip() or default])
    return command


def relay_publisher_preflight_command(
    env: os._Environ[str] | dict[str, str],
) -> list[str]:
    return [*relay_publisher_command(env), "--check-env", "--format", "json"]


def relay_publisher_file_labels(
    env: os._Environ[str] | dict[str, str],
) -> dict[str, str]:
    return {
        option.lstrip("-").replace("-", "_"): worker_file_label(
            env.get(env_name, default).strip() or default,
            env,
        )
        for env_name, option, default in PUBLISHER_FILE_ENV_ARGS
    }


def autonomous_loop_runtime_config(
    env: os._Environ[str] | dict[str, str],
) -> dict[str, str]:
    iterations = env.get("AUTOMOAT_AGENT_ITERATIONS", "0")
    return {
        "interval": env.get("AUTOMOAT_AGENT_INTERVAL", "300"),
        "iterations": iterations,
        "mode": autonomous_loop_mode(iterations),
    }


def autonomous_loop_mode(iterations: str) -> str:
    try:
        iteration_count = int(iterations)
    except ValueError:
        return "unknown"
    return "bounded" if iteration_count > 0 else "continuous"


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


def worker_file_label(
    value: str,
    env: os._Environ[str] | dict[str, str],
) -> str:
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    workdir, _codex_home = configured_worker_paths(env)
    try:
        resolved_path = path.expanduser().resolve(strict=False)
        resolved_workdir = workdir.expanduser().resolve(strict=False)
    except OSError:
        return f"<external>/{path.name}" if path.name else "<external>"
    try:
        relative_path = resolved_path.relative_to(resolved_workdir)
    except ValueError:
        return f"<external>/{resolved_path.name}" if resolved_path.name else "<external>"
    relative_text = relative_path.as_posix()
    return relative_text if relative_text else "."


def worker_config_path_label(value: Path | str) -> str:
    path = Path(value)
    path_text = path.as_posix()
    if not path.is_absolute():
        return path_text
    try:
        resolved_path = path.expanduser().resolve(strict=False)
    except OSError:
        return f"<external>/{path.name}" if path.name else "<external>"
    return f"<external>/{resolved_path.name}" if resolved_path.name else "<external>"


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
    if len(value) > MAX_RUNTIME_CONFIG_VALUE_CHARS:
        errors.append(f"{name} must be {MAX_RUNTIME_CONFIG_VALUE_CHARS} characters or fewer")
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


def business_hours_env_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
) -> str:
    return env.get(name, BUSINESS_HOURS_ENV_DEFAULTS[name]).strip()


def validate_business_hours_env_value(
    env: os._Environ[str] | dict[str, str],
    name: str,
    errors: list[str],
) -> str | None:
    value = env.get(name)
    if value is None:
        return BUSINESS_HOURS_ENV_DEFAULTS[name]
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
        errors.append(
            f"{name} must be a single-line business-hours value without control characters"
        )
        return None
    if len(value) > MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS:
        errors.append(
            f"{name} must be {MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS} characters or fewer"
        )
        return None
    return value


def business_hours_enabled(env: os._Environ[str] | dict[str, str]) -> bool:
    raw_value = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_ENABLED").lower()
    return raw_value not in BUSINESS_HOURS_FALSE_VALUES


def parse_business_time(value: str, name: str) -> datetime_time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"{name} must use HH:MM 24-hour time")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"{name} must use HH:MM 24-hour time") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"{name} must use HH:MM 24-hour time")
    return datetime_time(hour=hour, minute=minute)


def parse_business_day_token(token: str) -> int:
    normalized = token.strip().lower()
    if not normalized:
        raise ValueError("AUTOMOAT_BUSINESS_HOURS_DAYS must not contain empty day values")
    try:
        return BUSINESS_DAY_NAMES[normalized]
    except KeyError as exc:
        raise ValueError(
            "AUTOMOAT_BUSINESS_HOURS_DAYS must use day names like mon-fri or mon,wed,fri"
        ) from exc


def parse_business_days(value: str) -> tuple[int, ...]:
    days: set[int] = set()
    for item in value.strip().split(","):
        part = item.strip().lower()
        if not part:
            raise ValueError("AUTOMOAT_BUSINESS_HOURS_DAYS must not contain empty day values")
        if "-" in part:
            start_text, end_text = (piece.strip() for piece in part.split("-", 1))
            start_day = parse_business_day_token(start_text)
            end_day = parse_business_day_token(end_text)
            if start_day <= end_day:
                days.update(range(start_day, end_day + 1))
            else:
                days.update(range(start_day, 7))
                days.update(range(0, end_day + 1))
        else:
            days.add(parse_business_day_token(part))
    if not days:
        raise ValueError("AUTOMOAT_BUSINESS_HOURS_DAYS must include at least one day")
    return tuple(sorted(days))


def business_hours_settings(
    env: os._Environ[str] | dict[str, str] | None = None,
) -> dict[str, object]:
    env = env if env is not None else os.environ
    enabled = business_hours_enabled(env)
    if enabled:
        timezone_name = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_TIMEZONE")
        start_text = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_START")
        end_text = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_END")
        days_text = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_DAYS")
        idle_sleep_text = business_hours_env_value(env, "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP")
    else:
        timezone_name = BUSINESS_HOURS_ENV_DEFAULTS["AUTOMOAT_BUSINESS_HOURS_TIMEZONE"]
        start_text = BUSINESS_HOURS_ENV_DEFAULTS["AUTOMOAT_BUSINESS_HOURS_START"]
        end_text = BUSINESS_HOURS_ENV_DEFAULTS["AUTOMOAT_BUSINESS_HOURS_END"]
        days_text = BUSINESS_HOURS_ENV_DEFAULTS["AUTOMOAT_BUSINESS_HOURS_DAYS"]
        idle_sleep_text = BUSINESS_HOURS_ENV_DEFAULTS["AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP"]
    idle_sleep = float(idle_sleep_text)
    zone = ZoneInfo(timezone_name)
    start = parse_business_time(start_text, "AUTOMOAT_BUSINESS_HOURS_START")
    end = parse_business_time(end_text, "AUTOMOAT_BUSINESS_HOURS_END")
    days = parse_business_days(days_text)
    return {
        "enabled": enabled,
        "timezone_name": timezone_name,
        "zone": zone,
        "start": start,
        "start_text": start_text,
        "end": end,
        "end_text": end_text,
        "days": days,
        "days_text": days_text,
        "idle_sleep": idle_sleep,
    }


def validate_business_hours_environment(
    env: os._Environ[str] | dict[str, str],
    errors: list[str],
) -> None:
    business_values: dict[str, str] = {}
    initial_error_count = len(errors)
    for name in BUSINESS_HOURS_ENV_NAMES:
        value = validate_business_hours_env_value(env, name, errors)
        if value is not None:
            business_values[name] = value
    if len(errors) > initial_error_count:
        return

    enabled_value = business_values["AUTOMOAT_BUSINESS_HOURS_ENABLED"].lower()
    if enabled_value not in BUSINESS_HOURS_TRUE_VALUES | BUSINESS_HOURS_FALSE_VALUES:
        errors.append(
            "AUTOMOAT_BUSINESS_HOURS_ENABLED must be true/false, yes/no, on/off, or 1/0"
        )
    if enabled_value in BUSINESS_HOURS_FALSE_VALUES:
        return

    try:
        timezone_name = business_values["AUTOMOAT_BUSINESS_HOURS_TIMEZONE"]
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        errors.append("AUTOMOAT_BUSINESS_HOURS_TIMEZONE must be a valid IANA timezone")

    try:
        start = parse_business_time(
            business_values["AUTOMOAT_BUSINESS_HOURS_START"],
            "AUTOMOAT_BUSINESS_HOURS_START",
        )
    except ValueError as exc:
        errors.append(str(exc))
        start = None

    try:
        end = parse_business_time(
            business_values["AUTOMOAT_BUSINESS_HOURS_END"],
            "AUTOMOAT_BUSINESS_HOURS_END",
        )
    except ValueError as exc:
        errors.append(str(exc))
        end = None

    if start is not None and end is not None and start >= end:
        errors.append("AUTOMOAT_BUSINESS_HOURS_START must be before AUTOMOAT_BUSINESS_HOURS_END")

    try:
        parse_business_days(business_values["AUTOMOAT_BUSINESS_HOURS_DAYS"])
    except ValueError as exc:
        errors.append(str(exc))

    validate_positive_float(env, "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP", errors)


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
        return
    if len(value) > MAX_CODEX_CONFIG_VALUE_CHARS:
        errors.append(f"{name} must be {MAX_CODEX_CONFIG_VALUE_CHARS} characters or fewer")


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
    if len(value) > MAX_GIT_IDENTITY_VALUE_CHARS:
        errors.append(f"{name} must be {MAX_GIT_IDENTITY_VALUE_CHARS} characters or fewer")
        return
    if name.endswith("_EMAIL") and not is_plain_git_email(value):
        errors.append(f"{name} must be a plain email address with one @")
    if name.endswith("_NAME") and not is_plain_git_display_name(value):
        errors.append(f"{name} must be a plain display name without email punctuation")


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


def is_plain_git_display_name(value: str) -> bool:
    return not any(character in "<>()[],:;\\\"@" for character in value)


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
    if len(value) > MAX_SECRET_VALUE_CHARS:
        errors.append(f"{name} must be {MAX_SECRET_VALUE_CHARS} characters or fewer")
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
        require_no_path=True,
        max_chars=MAX_WORKER_URL_CHARS,
    )
    git_repo = env.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO)
    validate_secret_safe_http_url(
        "AUTOMOAT_GIT_REPO",
        git_repo,
        errors,
        required=True,
        require_path=True,
        max_chars=MAX_WORKER_URL_CHARS,
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
        for name in SECRET_ENV_NAMES
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
    validate_positive_int(
        env,
        "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
        errors,
        maximum=RUNTIME_CONFIG_LIMITS["AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS"],
    )
    validate_positive_float(
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
    validate_business_hours_environment(env, errors)
    validate_codex_config_value(env, "AUTOMOAT_CODEX_MODEL", errors)
    validate_codex_config_value(env, "AUTOMOAT_CODEX_REASONING_EFFORT", errors)
    for name in PUBLISHER_FILE_PATH_ENV_NAMES:
        validate_publisher_file_path_env_value(env, name, errors)
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


def missing_required_commands(command_paths: dict[str, str | None]) -> list[str]:
    return [command for command in REQUIRED_COMMANDS if not command_paths.get(command)]


def safe_command_path_labels(command_paths: dict[str, str | None]) -> dict[str, str | None]:
    return {
        command: "<found>" if command_paths.get(command) else None
        for command in REQUIRED_COMMANDS
    }


def configured_runtime_keys(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return nonsecret runtime override keys present in the worker environment."""
    return sorted(
        name
        for name in (
            *RUNTIME_CONFIG_LIMITS,
            *PUBLISHER_FILE_PATH_ENV_NAMES,
            *BUSINESS_HOURS_ENV_NAMES,
        )
        if name in env
    )


def configured_worker_path_keys(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return configured worker path keys without exposing their path values."""
    return sorted(name for name in WORKER_PATH_ENV_NAMES if name in env)


def configured_codex_config_keys(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return configured Codex config keys without exposing their values."""
    return sorted(name for name in CODEX_CONFIG_ENV_DEFAULTS if name in env)


def configured_git_identity_keys(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return configured Git identity keys without exposing names or emails."""
    return sorted(name for name in GIT_IDENTITY_ENV_DEFAULTS if name in env)


def configured_git_config_keys(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return configured Git repo/branch keys without exposing their values."""
    return sorted(name for name in GIT_CONFIG_ENV_NAMES if name in env)


def ambiguous_auth_groups(env: os._Environ[str] | dict[str, str]) -> list[str]:
    """Return auth groups with multiple configured candidates and no secret values."""
    groups: list[str] = []
    if len(configured_names(env, GIT_AUTH_ENV_NAMES)) > 1:
        groups.append("git_auth")
    if len(configured_names(env, CODEX_AUTH_ENV_NAMES)) > 1:
        groups.append("codex_auth")
    return groups


def validate_secret_safe_http_url(
    name: str,
    value: str,
    errors: list[str],
    *,
    required: bool,
    require_path: bool = False,
    require_no_path: bool = False,
    max_chars: int | None = None,
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
    if max_chars is not None and len(value) > max_chars:
        errors.append(f"{name} must be {max_chars} characters or fewer")
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
    elif not is_valid_url_hostname(parsed_value.hostname):
        errors.append(f"{name} must include a valid host")
    elif parsed_value.username or parsed_value.password:
        errors.append(f"{name} must not include embedded credentials")
    elif parsed_value.params:
        errors.append(f"{name} must not include path parameters")
    elif parsed_value.query or parsed_value.fragment:
        errors.append(f"{name} must not include query strings or fragments")
    elif require_no_path and parsed_value.path.strip("/"):
        errors.append(f"{name} must be a relay base URL without a path")
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
            return
        if parsed_value.scheme == "http" and not local_http_host(parsed_value.hostname):
            errors.append(
                f"{name} must use https:// unless the host is localhost or 127.0.0.1"
            )


def is_valid_url_hostname(hostname: str) -> bool:
    normalized = hostname.strip("[]").rstrip(".").lower()
    if not normalized:
        return False
    if normalized == "localhost":
        return True
    try:
        ip_address = ipaddress.ip_address(normalized)
        return ip_address.is_loopback or (
            ip_address.is_global and not ip_address.is_multicast
        )
    except ValueError:
        pass
    if len(normalized) > 253:
        return False
    labels = normalized.split(".")
    for label in labels:
        if not label or len(label) > 63:
            return False
        if label.startswith("-") or label.endswith("-"):
            return False
        if not all(
            character.isascii() and (character.isalnum() or character == "-")
            for character in label
        ):
            return False
    return True


def local_http_host(hostname: str) -> bool:
    normalized = hostname.lower().strip("[]")
    return normalized in {"localhost", "127.0.0.1", "::1"}


def preflight_error_category(error: str) -> str:
    if error.endswith(" is required"):
        return "missing_required"
    if error.startswith("AUTOMOAT_RELAY_URL") or error.startswith("AUTOMOAT_GIT_REPO"):
        return "invalid_url"
    if error.startswith("AUTOMOAT_GIT_BRANCH"):
        return "invalid_git_branch"
    if error.startswith("AUTOMOAT_WORKDIR") or error.startswith("CODEX_HOME"):
        return "invalid_path"
    if any(error.startswith(name) for name in PUBLISHER_FILE_PATH_ENV_NAMES):
        return "invalid_file_path"
    if error.startswith("reserved runtime file "):
        return "invalid_path"
    if error.startswith("CODEX_AUTH_JSON_B64 must decode"):
        return "invalid_codex_auth_payload"
    if error.startswith("AUTOMOAT_CODEX_"):
        return "invalid_codex_config"
    if any(
        error.startswith(name)
        for name in (*RUNTIME_CONFIG_LIMITS, *BUSINESS_HOURS_ENV_NAMES)
    ):
        return "invalid_runtime_config"
    if error.startswith("GIT_AUTHOR_") or error.startswith("GIT_COMMITTER_"):
        return "invalid_git_identity"
    if (
        "single-line value without control characters" in error
        or "must not include leading or trailing whitespace" in error
    ):
        return "invalid_secret_or_identity"
    if any(error.startswith(name) for name in SECRET_ENV_NAMES):
        return "invalid_secret"
    if error.endswith(" executable is required on PATH"):
        return "missing_command"
    if error.startswith("AUTOMOAT_"):
        return "invalid_runtime_config"
    return "invalid_configuration"


def preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({preflight_error_category(error) for error in errors})


def preflight_error_key(error: str) -> str:
    if error == "GITHUB_TOKEN or GH_TOKEN is required":
        return "GITHUB_TOKEN|GH_TOKEN"
    if error == "CODEX_AUTH_JSON_B64, CODEX_ACCESS_TOKEN, or OPENAI_API_KEY is required":
        return "CODEX_AUTH_JSON_B64|CODEX_ACCESS_TOKEN|OPENAI_API_KEY"
    first_token = error.split(" ", 1)[0]
    if first_token in {
        "AUTOMOAT_RELAY_URL",
        "AUTOMOAT_RELAY_TOKEN",
        "AUTOMOAT_GIT_REPO",
        "AUTOMOAT_GIT_BRANCH",
        "AUTOMOAT_WORKDIR",
        "CODEX_HOME",
        "CODEX_AUTH_JSON_B64",
        "CODEX_ACCESS_TOKEN",
        "OPENAI_API_KEY",
        *GIT_AUTH_ENV_NAMES,
        *CODEX_CONFIG_ENV_DEFAULTS,
        *RUNTIME_CONFIG_LIMITS,
        *BUSINESS_HOURS_ENV_NAMES,
        *PUBLISHER_FILE_PATH_ENV_NAMES,
        *GIT_IDENTITY_ENV_DEFAULTS,
    }:
        return first_token
    for command in REQUIRED_COMMANDS:
        if error == f"{command} executable is required on PATH":
            return f"PATH:{command}"
    if error.startswith("reserved runtime file "):
        return "reserved_runtime_files"
    return "worker_environment"


def preflight_error_keys(errors: list[str]) -> list[str]:
    return sorted({preflight_error_key(error) for error in errors})


def validate_git_branch_name(value: str, errors: list[str]) -> None:
    if value != value.strip():
        errors.append("AUTOMOAT_GIT_BRANCH must not include leading or trailing whitespace")
        return
    branch = value.strip()
    if not branch:
        errors.append("AUTOMOAT_GIT_BRANCH must not be empty")
        return
    if len(branch) > MAX_GIT_BRANCH_CHARS:
        errors.append(
            f"AUTOMOAT_GIT_BRANCH must be {MAX_GIT_BRANCH_CHARS} characters or fewer"
        )
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
    if branch in GIT_PSEUDO_REF_NAMES:
        errors.append("AUTOMOAT_GIT_BRANCH must be a branch name, not a Git pseudo-ref")
        return
    if branch.startswith(("origin/", "remotes/", "refs/")):
        errors.append(
            "AUTOMOAT_GIT_BRANCH must be a short branch name without "
            "origin/, remotes/, or refs/ prefixes"
        )
        return
    branch_components = branch.split("/")
    invalid_fragments = ("..", "//", "@{", "\\")
    invalid_characters = set("~^:?*[")
    if (
        branch == "@"
        or branch.startswith("/")
        or branch.endswith("/")
        or any(component.startswith(".") for component in branch_components)
        or any(component.endswith(".") for component in branch_components)
        or any(component.endswith(".lock") for component in branch_components)
        or any(fragment in branch for fragment in invalid_fragments)
        or any(character in invalid_characters for character in branch)
    ):
        errors.append("AUTOMOAT_GIT_BRANCH must be a valid git branch name")
        return
    if not PORTABLE_GIT_BRANCH_PATTERN.fullmatch(branch):
        errors.append(
            "AUTOMOAT_GIT_BRANCH must contain only letters, numbers, dots, "
            "underscores, hyphens, and slashes"
        )


def validate_workdir_path(path: Path, errors: list[str], *, codex_home: Path | None = None) -> None:
    path_text = str(path)
    if path_text != path_text.strip():
        errors.append("AUTOMOAT_WORKDIR must not include leading or trailing whitespace")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in path_text
    ):
        errors.append("AUTOMOAT_WORKDIR must be a single-line path without control characters")
        return

    raw_path = path_text.strip()
    if not raw_path:
        errors.append("AUTOMOAT_WORKDIR must not be empty")
        return
    if len(path_text) > MAX_WORKER_PATH_CHARS:
        errors.append(f"AUTOMOAT_WORKDIR must be {MAX_WORKER_PATH_CHARS} characters or fewer")
        return

    expanded_path = path.expanduser()
    if not expanded_path.is_absolute():
        errors.append("AUTOMOAT_WORKDIR must be an absolute path")
        return

    try:
        resolved_path = expanded_path.resolve(strict=False)
        codex_home_path = codex_home if codex_home is not None else CODEX_HOME
        resolved_codex_home = codex_home_path.expanduser().resolve(strict=False)
    except OSError:
        errors.append("AUTOMOAT_WORKDIR could not be resolved")
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
        blocking_label = worker_config_path_label(blocking_path)
        errors.append(
            f"AUTOMOAT_WORKDIR path component {blocking_label} must be a directory"
        )
        return


def validate_codex_home_path(path: Path, workdir: Path, errors: list[str]) -> None:
    path_text = str(path)
    if path_text != path_text.strip():
        errors.append("CODEX_HOME must not include leading or trailing whitespace")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in path_text
    ):
        errors.append("CODEX_HOME must be a single-line path without control characters")
        return

    raw_path = path_text.strip()
    if not raw_path:
        errors.append("CODEX_HOME must not be empty")
        return
    if len(path_text) > MAX_WORKER_PATH_CHARS:
        errors.append(f"CODEX_HOME must be {MAX_WORKER_PATH_CHARS} characters or fewer")
        return

    expanded_path = path.expanduser()
    if not expanded_path.is_absolute():
        errors.append("CODEX_HOME must be an absolute path")
        return

    expanded_named_parts = [part for part in expanded_path.parts if part != expanded_path.anchor]
    if len(expanded_named_parts) < 2:
        errors.append("CODEX_HOME must not be filesystem root or a top-level directory")
        return

    try:
        resolved_path = expanded_path.resolve(strict=False)
    except OSError:
        errors.append("CODEX_HOME could not be resolved")
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
        blocking_label = worker_config_path_label(blocking_path)
        errors.append(f"CODEX_HOME path component {blocking_label} must be a directory")
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


def blocking_parent_path_component(path: Path) -> Path | None:
    current_path = path.parent
    while True:
        if current_path.exists():
            return None if current_path.is_dir() else current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent


def validate_publisher_file_path_env_value(
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
    if value != value.strip():
        errors.append(f"{name} must not include leading or trailing whitespace")
        return
    if any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        errors.append(f"{name} must be a single-line path without control characters")
        return
    if URL_SCHEME_PATTERN.match(value):
        errors.append(f"{name} must be a file path, not a URL")
        return
    if ":" in value or ";" in value:
        errors.append(f"{name} must be a single file path, not a path list")
        return
    if len(value) > MAX_WORKER_PATH_CHARS:
        errors.append(f"{name} must be {MAX_WORKER_PATH_CHARS} characters or fewer")
        return

    path = publisher_file_path(env, value)
    try:
        resolved_path = path.expanduser().resolve(strict=False)
    except OSError:
        errors.append(f"{name} could not be resolved")
        return
    conflicting_runtime_file = reserved_runtime_file_conflict(resolved_path)
    if conflicting_runtime_file is not None:
        errors.append(f"{name} must not be equal to or inside a reserved runtime file")
        return
    try:
        workdir, _codex_home = configured_worker_paths(env)
        resolved_workdir = workdir.expanduser().resolve(strict=False)
    except OSError:
        errors.append(f"{name} could not verify AUTOMOAT_WORKDIR containment")
        return
    if (
        resolved_workdir.is_absolute()
        and len([part for part in resolved_workdir.parts if part != resolved_workdir.anchor])
        >= 2
        and not resolved_path.is_relative_to(resolved_workdir)
    ):
        errors.append(f"{name} must stay inside AUTOMOAT_WORKDIR")
        return
    if resolved_path.exists() and resolved_path.is_dir():
        errors.append(f"{name} must be a file path, not a directory")
        return
    if blocking_parent_path_component(resolved_path) is not None:
        errors.append(f"{name} parent path must be a directory")


def publisher_file_path(env: os._Environ[str] | dict[str, str], value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    workdir, _codex_home = configured_worker_paths(env)
    return workdir / path


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
    command_path_labels = safe_command_path_labels(command_paths)
    workdir, codex_home = configured_worker_paths(env)
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": preflight_error_categories(errors),
            "failed_configuration_keys": preflight_error_keys(errors),
            "git_auth": configured_names(env, GIT_AUTH_ENV_NAMES),
            "git_auth_selected": selected_name(env, GIT_AUTH_ENV_NAMES),
            "codex_auth": configured_names(env, CODEX_AUTH_ENV_NAMES),
            "codex_auth_selected": selected_name(env, CODEX_AUTH_ENV_NAMES),
            "auth_ambiguous_groups": ambiguous_auth_groups(env),
            "commands": list(REQUIRED_COMMANDS),
            "command_paths": command_path_labels,
            "missing_commands": missing_required_commands(command_paths),
            "runtime_configured_keys": configured_runtime_keys(env),
            "path_configured_keys": configured_worker_path_keys(env),
            "codex_configured_keys": configured_codex_config_keys(env),
            "git_configured_keys": configured_git_config_keys(env),
            "git_identity_configured_keys": configured_git_identity_keys(env),
            "runtime_limits": RUNTIME_CONFIG_LIMITS,
        }
        return payload

    payload["config"] = {
        "relay_url": sanitize_worker_config_text(
            env.get("AUTOMOAT_RELAY_URL", "").strip(),
            env,
        ),
        "git_repo": sanitize_worker_config_text(
            env.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO).strip(),
            env,
        ),
        "git_branch": sanitize_worker_config_text(
            env.get("AUTOMOAT_GIT_BRANCH", "main").strip() or "main",
            env,
        ),
        "workdir": worker_config_path_label(workdir),
        "codex_home": worker_config_path_label(codex_home),
        "git_auth": configured_names(env, GIT_AUTH_ENV_NAMES),
        "git_auth_selected": selected_name(env, GIT_AUTH_ENV_NAMES),
        "codex_auth": configured_names(env, CODEX_AUTH_ENV_NAMES),
        "codex_auth_selected": selected_name(env, CODEX_AUTH_ENV_NAMES),
        "auth_ambiguous_groups": ambiguous_auth_groups(env),
        "runtime_configured_keys": configured_runtime_keys(env),
        "path_configured_keys": configured_worker_path_keys(env),
        "codex_configured_keys": configured_codex_config_keys(env),
        "git_configured_keys": configured_git_config_keys(env),
        "git_identity_configured_keys": configured_git_identity_keys(env),
        "agent_interval": env.get("AUTOMOAT_AGENT_INTERVAL", "300"),
        "agent_iterations": env.get("AUTOMOAT_AGENT_ITERATIONS", "0"),
        "agent_loop_mode": autonomous_loop_mode(
            env.get("AUTOMOAT_AGENT_ITERATIONS", "0")
        ),
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
        "business_hours_enabled": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_ENABLED",
        ),
        "business_hours_timezone": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_TIMEZONE",
        ),
        "business_hours_start": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_START",
        ),
        "business_hours_end": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_END",
        ),
        "business_hours_days": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_DAYS",
        ),
        "business_hours_idle_sleep": business_hours_env_value(
            env,
            "AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP",
        ),
        **relay_publisher_file_labels(env),
        "bridge_status_stale_after_seconds": env.get(
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
            "660",
        ),
        "codex_model": sanitize_worker_config_text(
            codex_config_value(env, "AUTOMOAT_CODEX_MODEL"),
            env,
        ),
        "codex_reasoning_effort": sanitize_worker_config_text(
            codex_config_value(env, "AUTOMOAT_CODEX_REASONING_EFFORT"),
            env,
        ),
        "commands": list(REQUIRED_COMMANDS),
        "command_paths": command_path_labels,
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
        diagnostics = environment_preflight_summary(
            env,
            errors,
            command_paths,
        )["diagnostics"]
        emit(
            "preflight diagnostics: "
            f"error_categories="
            f"{json.dumps(diagnostics['error_categories'], sort_keys=True)} "
            f"failed_configuration_keys="
            f"{json.dumps(diagnostics['failed_configuration_keys'], sort_keys=True)} "
            f"missing_commands="
            f"{json.dumps(diagnostics['missing_commands'], sort_keys=True)} "
            f"git_auth={','.join(diagnostics['git_auth'])} "
            f"git_auth_selected={diagnostics['git_auth_selected']} "
            f"codex_auth={','.join(diagnostics['codex_auth'])} "
            f"codex_auth_selected={diagnostics['codex_auth_selected']} "
            f"auth_ambiguous_groups="
            f"{json.dumps(diagnostics['auth_ambiguous_groups'], sort_keys=True)} "
            f"runtime_configured_keys="
            f"{json.dumps(diagnostics['runtime_configured_keys'], sort_keys=True)} "
            f"path_configured_keys="
            f"{json.dumps(diagnostics['path_configured_keys'], sort_keys=True)} "
            f"codex_configured_keys="
            f"{json.dumps(diagnostics['codex_configured_keys'], sort_keys=True)} "
            f"git_configured_keys="
            f"{json.dumps(diagnostics['git_configured_keys'], sort_keys=True)} "
            f"git_identity_configured_keys="
            f"{json.dumps(diagnostics['git_identity_configured_keys'], sort_keys=True)} "
            f"command_paths={json.dumps(diagnostics['command_paths'], sort_keys=True)}"
        )
        return errors

    workdir, codex_home = configured_worker_paths(env)
    workdir_label = worker_config_path_label(workdir)
    codex_home_label = worker_config_path_label(codex_home)
    command_path_labels = safe_command_path_labels(command_paths)
    relay_url_label = sanitize_worker_config_text(
        env.get("AUTOMOAT_RELAY_URL", "").strip(),
        env,
    )
    git_repo_label = sanitize_worker_config_text(
        env.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO).strip(),
        env,
    )
    git_branch_label = sanitize_worker_config_text(
        env.get("AUTOMOAT_GIT_BRANCH", "main").strip() or "main",
        env,
    )
    codex_model_label = sanitize_worker_config_text(
        codex_config_value(env, "AUTOMOAT_CODEX_MODEL"),
        env,
    )
    codex_reasoning_effort_label = sanitize_worker_config_text(
        codex_config_value(env, "AUTOMOAT_CODEX_REASONING_EFFORT"),
        env,
    )
    file_labels = relay_publisher_file_labels(env)
    emit(
        "environment preflight passed: "
        f"relay_url={relay_url_label} "
        f"git_repo={git_repo_label} "
        f"git_branch={git_branch_label} "
        f"workdir={workdir_label} "
        f"codex_home={codex_home_label} "
        f"git_auth={','.join(configured_names(env, GIT_AUTH_ENV_NAMES))} "
        f"git_auth_selected={selected_name(env, GIT_AUTH_ENV_NAMES)} "
        f"codex_auth={','.join(configured_names(env, CODEX_AUTH_ENV_NAMES))} "
        f"codex_auth_selected={selected_name(env, CODEX_AUTH_ENV_NAMES)} "
        f"auth_ambiguous_groups={json.dumps(ambiguous_auth_groups(env), sort_keys=True)} "
        f"runtime_configured_keys="
        f"{json.dumps(configured_runtime_keys(env), sort_keys=True)} "
        f"path_configured_keys="
        f"{json.dumps(configured_worker_path_keys(env), sort_keys=True)} "
        f"codex_configured_keys="
        f"{json.dumps(configured_codex_config_keys(env), sort_keys=True)} "
        f"git_configured_keys="
        f"{json.dumps(configured_git_config_keys(env), sort_keys=True)} "
        f"git_identity_configured_keys="
        f"{json.dumps(configured_git_identity_keys(env), sort_keys=True)} "
        f"agent_interval={env.get('AUTOMOAT_AGENT_INTERVAL', '300')} "
        f"agent_iterations={env.get('AUTOMOAT_AGENT_ITERATIONS', '0')} "
        f"agent_loop_mode="
        f"{autonomous_loop_mode(env.get('AUTOMOAT_AGENT_ITERATIONS', '0'))} "
        f"relay_interval={env.get('AUTOMOAT_RELAY_INTERVAL', '3')} "
        f"relay_timeout={env.get('AUTOMOAT_RELAY_TIMEOUT', '8')} "
        f"relay_max_consecutive_failures="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES', '3')} "
        f"relay_max_consecutive_stale_statuses="
        f"{env.get('AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES', '0')} "
        f"relay_tail_lines={env.get('AUTOMOAT_RELAY_TAIL_LINES', '180')} "
        f"relay_max_log_bytes={env.get('AUTOMOAT_RELAY_MAX_LOG_BYTES', str(256 * 1024))} "
        f"status_stale_after_seconds={env.get('AUTOMOAT_STATUS_STALE_AFTER_SECONDS', '660')} "
        f"business_hours_enabled="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_ENABLED')} "
        f"business_hours_timezone="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_TIMEZONE')} "
        f"business_hours_start="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_START')} "
        f"business_hours_end="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_END')} "
        f"business_hours_days="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_DAYS')} "
        f"business_hours_idle_sleep="
        f"{business_hours_env_value(env, 'AUTOMOAT_BUSINESS_HOURS_IDLE_SLEEP')} "
        f"status_file={file_labels['status_file']} "
        f"pid_file={file_labels['pid_file']} "
        f"log_file={file_labels['log_file']} "
        f"publisher_log={file_labels['publisher_log']} "
        f"bridge_status_file={file_labels['bridge_status_file']} "
        f"bridge_status_stale_after_seconds="
        f"{env.get('AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS', '660')} "
        f"codex_model={codex_model_label} "
        f"codex_reasoning_effort={codex_reasoning_effort_label} "
        f"commands={','.join(REQUIRED_COMMANDS)} "
        f"command_paths={json.dumps(command_path_labels, sort_keys=True)} "
        f"runtime_limits={json.dumps(RUNTIME_CONFIG_LIMITS, sort_keys=True)}"
    )
    return []


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout_seconds: float | None = None,
    max_output_bytes: int | None = None,
) -> str:
    printable = worker_command_log_text(command)
    emit(f"$ {printable}")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=os.environ.copy(),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_text = (
            format_number(timeout_seconds) if timeout_seconds is not None else "unknown"
        )
        raise RuntimeError(f"{printable} timed out after {timeout_text}s") from exc
    except OSError as exc:
        raise RuntimeError(
            f"{printable} could not start: {type(exc).__name__}"
        ) from None

    if result.stdout:
        output_size = len(result.stdout.encode("utf-8", errors="replace"))
        if max_output_bytes is not None and output_size > max_output_bytes:
            emit(
                "  <stdout omitted: "
                f"{output_size} bytes exceeds {max_output_bytes} byte limit>"
            )
            raise RuntimeError(
                f"{printable} produced {output_size} bytes of output, "
                f"exceeding limit {max_output_bytes}"
            )
        for line in result.stdout.rstrip().splitlines():
            emit(f"  {sanitize_worker_log_text(line)}")
    if result.returncode != 0:
        raise RuntimeError(f"{printable} failed with status {result.returncode}")
    return result.stdout


def worker_command_log_text(command: list[str]) -> str:
    """Return a Render-visible command line without Git identity values."""
    safe_command = list(command)
    if (
        len(safe_command) >= 5
        and safe_command[:3] == ["git", "config", "--global"]
        and safe_command[3] in GIT_IDENTITY_CONFIG_KEYS
    ):
        safe_command[4] = "[redacted]"
    return sanitize_worker_log_text(" ".join(safe_command))


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def validate_publisher_preflight_output(output: str) -> None:
    try:
        payload = json.loads(output.strip(), parse_constant=reject_json_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PublisherPreflightError(
            "relay publisher preflight did not return valid JSON",
            status_label="invalid_json",
        ) from exc

    if not isinstance(payload, dict):
        raise PublisherPreflightError(
            "relay publisher preflight did not return a JSON object",
            status_label=f"invalid_{type(payload).__name__}",
        )

    status = payload.get("status")
    if status == "passed":
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            raise PublisherPreflightError(
                "relay publisher preflight reported inconsistent status=passed "
                f"error_count={len(errors)}",
                status_label="passed",
                error_count=len(errors),
            )
        return

    if status == "failed":
        diagnostics = payload.get("diagnostics")
        categories = publisher_preflight_diagnostic_tokens(diagnostics, "error_categories")
        failed_keys = publisher_preflight_diagnostic_tokens(
            diagnostics,
            "failed_configuration_keys",
        )
        errors = payload.get("errors")
        error_count = len(errors) if isinstance(errors, list) else "unknown"
        category_text = ",".join(categories)
        failed_key_text = ",".join(failed_keys)
        raise PublisherPreflightError(
            "relay publisher preflight reported status=failed "
            f"error_count={error_count} "
            f"error_categories={category_text or 'unknown'} "
            f"failed_configuration_keys={failed_key_text or 'unknown'}",
            status_label="failed",
            error_count=error_count if isinstance(error_count, int) else None,
            error_categories=categories,
            failed_configuration_keys=failed_keys,
        )

    status_label = publisher_preflight_status_label(status)
    raise PublisherPreflightError(
        "relay publisher preflight reported "
        f"status={status_label}",
        status_label=status_label,
    )


def publisher_preflight_status_label(status: Any) -> str:
    if status is None:
        return "missing"
    if not isinstance(status, str):
        return f"invalid_{type(status).__name__}"
    if not status.strip():
        return "missing"
    if len(status) > 80:
        return "invalid"
    if all(character.isalnum() or character in "_-" for character in status):
        return status
    return "invalid"


def publisher_preflight_diagnostic_tokens(diagnostics: Any, key: str) -> list[str]:
    if not isinstance(diagnostics, dict):
        return []
    values = diagnostics.get(key)
    if not isinstance(values, list):
        return []

    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value or len(value) > 160:
            continue
        if value in seen:
            continue
        if all(character.isalnum() or character in "_-|" for character in value):
            tokens.append(value)
            seen.add(value)
        if len(tokens) >= PUBLISHER_PREFLIGHT_DIAGNOSTIC_TOKEN_LIMIT:
            break
    return tokens


def publisher_preflight_command_log_text(command: list[str]) -> str:
    safe_parts: list[str] = []
    skip_next = False
    file_options = {option for _env_name, option, _default in PUBLISHER_FILE_ENV_ARGS}
    for index, part in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        if part in file_options and index + 1 < len(command):
            safe_parts.extend([part, worker_file_label(command[index + 1], os.environ)])
            skip_next = True
            continue
        if part in {"--token", "--relay-token"} and index + 1 < len(command):
            safe_parts.extend([part, "[redacted]"])
            skip_next = True
            continue
        safe_parts.append(part)
    return " ".join(safe_parts)


def run_relay_publisher_preflight_command(command: list[str], *, cwd: Path) -> str:
    printable = publisher_preflight_command_log_text(command)
    emit(f"$ {printable}")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env=os.environ.copy(),
            timeout=PUBLISHER_PREFLIGHT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{printable} timed out after {format_number(PUBLISHER_PREFLIGHT_TIMEOUT_SECONDS)}s"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"{printable} could not start: {type(exc).__name__}"
        ) from None

    output = result.stdout or ""
    output_size = len(output.encode("utf-8", errors="replace"))
    if output_size > PUBLISHER_PREFLIGHT_MAX_OUTPUT_BYTES:
        emit(
            "  <stdout omitted: "
            f"{output_size} bytes exceeds {PUBLISHER_PREFLIGHT_MAX_OUTPUT_BYTES} byte limit>"
        )
        raise RuntimeError(
            f"{printable} produced {output_size} bytes of output, "
            f"exceeding limit {PUBLISHER_PREFLIGHT_MAX_OUTPUT_BYTES}"
        )
    if output:
        emit(f"  <stdout captured: {output_size} bytes>")

    try:
        validate_publisher_preflight_output(output)
    except RuntimeError as exc:
        if result.returncode != 0:
            if isinstance(exc, PublisherPreflightError):
                raise PublisherPreflightError(
                    f"{printable} failed with status {result.returncode}; "
                    f"{exc}",
                    status_label=exc.status_label,
                    exit_status=result.returncode,
                    error_count=exc.error_count,
                    error_categories=exc.error_categories,
                    failed_configuration_keys=exc.failed_configuration_keys,
                ) from exc
            raise RuntimeError(
                f"{printable} failed with status {result.returncode}; "
                f"{exc}"
            ) from exc
        raise
    if result.returncode != 0:
        raise PublisherPreflightError(
            f"{printable} failed with status {result.returncode}; "
            "relay publisher preflight reported status=passed but exited nonzero",
            status_label="passed",
            exit_status=result.returncode,
        )
    return output


def write_codex_config() -> None:
    workdir, codex_home = configured_worker_paths(os.environ)
    codex_home.mkdir(parents=True, exist_ok=True)
    config = codex_home / "config.toml"
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
                f"[projects.{toml_basic_string(workdir.as_posix())}]",
                'trust_level = "trusted"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    os.environ["CODEX_HOME"] = str(codex_home)


def configure_codex_auth() -> None:
    write_codex_config()
    _workdir, codex_home = configured_worker_paths(os.environ)
    auth_b64 = os.environ.get("CODEX_AUTH_JSON_B64", "").strip()
    access_token = os.environ.get("CODEX_ACCESS_TOKEN", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if auth_b64:
        auth_path = codex_home / "auth.json"
        auth_path.write_bytes(decode_codex_auth_json_b64(auth_b64))
        auth_path.chmod(0o600)
        emit(f"wrote Codex auth file to {worker_config_path_label(auth_path)}")
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
    token_file = shlex.quote(str(GITHUB_TOKEN_FILE))
    GIT_ASKPASS.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "*Username*) echo x-access-token ;;\n"
        f"*Password*) cat {token_file} ;;\n"
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
    workdir, _codex_home = configured_worker_paths(os.environ)
    repo = os.environ.get("AUTOMOAT_GIT_REPO", DEFAULT_REPO)
    branch = os.environ.get("AUTOMOAT_GIT_BRANCH", "main").strip() or "main"
    workdir.parent.mkdir(parents=True, exist_ok=True)
    if not (workdir / ".git").exists():
        if workdir.exists():
            shutil.rmtree(workdir)
        run(["git", "clone", "--branch", branch, repo, str(workdir)])
    else:
        run(["git", "fetch", "origin", branch], cwd=workdir)
        run(["git", "checkout", branch], cwd=workdir)
        run(["git", "reset", "--hard", f"origin/{branch}"], cwd=workdir)
    run(["git", "status", "--short", "--branch"], cwd=workdir)


def check_relay_publisher_preflight() -> None:
    workdir, _codex_home = configured_worker_paths(os.environ)
    emit("checking checked-out relay publisher preflight")
    run_relay_publisher_preflight_command(
        relay_publisher_preflight_command(os.environ),
        cwd=workdir,
    )
    emit("checked-out relay publisher preflight passed")


def git_text(args: list[str]) -> str:
    workdir, _codex_home = configured_worker_paths(os.environ)
    result = subprocess.run(
        ["git", *args],
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def worker_git_snapshot() -> dict[str, object]:
    return {
        "branch": git_text(["branch", "--show-current"]),
        "head": git_text(["rev-parse", "--short", "HEAD"]),
    }


def current_business_hours_state(
    env: os._Environ[str] | dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    env = env if env is not None else os.environ
    settings = business_hours_settings(env)
    enabled = bool(settings["enabled"])
    zone = settings["zone"]
    assert isinstance(zone, ZoneInfo)
    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_now = current.astimezone(zone)
    start = settings["start"]
    end = settings["end"]
    assert isinstance(start, datetime_time)
    assert isinstance(end, datetime_time)
    days = settings["days"]
    assert isinstance(days, tuple)
    in_hours = (
        not enabled
        or (
            local_now.weekday() in days
            and start <= local_now.time().replace(second=0, microsecond=0) < end
        )
    )
    next_start = None if in_hours else next_business_start(local_now, settings)
    return {
        "enabled": enabled,
        "in_business_hours": in_hours,
        "timezone": settings["timezone_name"],
        "start": settings["start_text"],
        "end": settings["end_text"],
        "days": settings["days_text"],
        "local_time": local_now.isoformat(timespec="seconds"),
        "local_weekday": local_now.strftime("%a").lower(),
        "next_start_at": next_start.isoformat(timespec="seconds") if next_start else None,
    }


def next_business_start(
    local_now: datetime,
    settings: dict[str, object],
) -> datetime:
    start = settings["start"]
    days = settings["days"]
    assert isinstance(start, datetime_time)
    assert isinstance(days, tuple)
    for day_offset in range(0, 14):
        candidate_date = local_now.date() + timedelta(days=day_offset)
        if candidate_date.weekday() not in days:
            continue
        candidate = datetime.combine(candidate_date, start, tzinfo=local_now.tzinfo)
        if candidate > local_now:
            return candidate
    return local_now + timedelta(minutes=5)


def seconds_until_next_business_start(state: dict[str, object]) -> float:
    next_start = state.get("next_start_at")
    if not isinstance(next_start, str) or not next_start:
        return 0.0
    try:
        parsed = datetime.fromisoformat(next_start)
    except ValueError:
        return 0.0
    current = datetime.now(parsed.tzinfo or timezone.utc)
    return max(0.0, (parsed - current).total_seconds())


def cockpit_log_file() -> Path:
    workdir, _codex_home = configured_worker_paths(os.environ)
    return workdir / ".automoat" / "logs" / "mvp-loop.log"


def cockpit_status_file() -> Path:
    workdir, _codex_home = configured_worker_paths(os.environ)
    return workdir / ".automoat" / "state" / "mvp-loop-status.json"


def append_cockpit_log(message: str) -> None:
    log_file = cockpit_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] {message}\n")


def write_business_hours_pause_status(state: dict[str, object]) -> None:
    status_path = cockpit_status_file()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": "business-hours-schedule",
        "iteration": 0,
        "status": "paused",
        "mode": "autonomous_codex",
        "phase": "outside_business_hours",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "steps": [],
        "business_hours": state,
        "git": worker_git_snapshot(),
    }
    status_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_cockpit_log(
        "business-hours pause: "
        f"local_time={state.get('local_time')} "
        f"window={state.get('days')} {state.get('start')}-{state.get('end')} "
        f"next_start_at={state.get('next_start_at')}"
    )


def compact_worker_exit_status(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def render_worker_failure_route_hint(reason: str) -> str:
    safe_reason = sanitize_worker_log_text(reason)[:MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS]
    route_candidate = safe_reason.split(maxsplit=1)[0] if safe_reason else ""
    if route_candidate in RENDER_WORKER_FAILURE_ROUTE_HINTS:
        return route_candidate
    return RELAY_PUBLISHER_UNAVAILABLE


def publisher_preflight_failure_details(exc: BaseException) -> dict[str, object]:
    if not isinstance(exc, PublisherPreflightError):
        return {}
    return compact_publisher_preflight_details(
        {
            "status": exc.status_label,
            "exit_status": exc.exit_status,
            "error_count": exc.error_count,
            "error_categories": exc.error_categories,
            "failed_configuration_keys": exc.failed_configuration_keys,
        }
    )


def compact_publisher_preflight_details(details: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {}
    status = details.get("status")
    if isinstance(status, str) and status.strip():
        compact["status"] = publisher_preflight_status_label(status)
    exit_status = compact_worker_exit_status(details.get("exit_status"))
    if exit_status is not None:
        compact["exit_status"] = exit_status
    error_count = compact_worker_exit_status(details.get("error_count"))
    if error_count is not None:
        compact["error_count"] = error_count
    error_categories = publisher_preflight_diagnostic_tokens(details, "error_categories")
    if error_categories:
        compact["error_categories"] = error_categories
    failed_keys = publisher_preflight_diagnostic_tokens(details, "failed_configuration_keys")
    if failed_keys:
        compact["failed_configuration_keys"] = failed_keys
    return compact


def write_render_worker_failure_status(
    *,
    reason: str,
    worker_exit_status: int,
    publisher_exit_status: int | None = None,
    message: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Write a compact cockpit status when the Render supervisor cannot continue."""
    status_path = cockpit_status_file()
    status_path.parent.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    safe_reason = sanitize_worker_log_text(reason)[:MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS]
    route_hint = render_worker_failure_route_hint(reason)
    failure: dict[str, object] = {
        "category": "render_worker",
        "route_hint": route_hint,
        "failure_reason": safe_reason,
        "worker_exit_status": worker_exit_status,
    }
    compact_publisher_status = compact_worker_exit_status(publisher_exit_status)
    if compact_publisher_status is not None:
        failure["publisher_exit_status"] = compact_publisher_status
    if message:
        failure["message"] = sanitize_worker_log_text(message)[
            :MAX_BUSINESS_HOURS_CONFIG_VALUE_CHARS
        ]
    compact_details = compact_publisher_preflight_details(details or {})
    if compact_details:
        failure["publisher_preflight"] = compact_details
    payload = {
        "run_id": "render-worker-supervisor",
        "iteration": 0,
        "status": "failed",
        "mode": "autonomous_codex",
        "phase": route_hint,
        "started_at": now,
        "updated_at": now,
        "steps": [],
        "failure": failure,
        "git": worker_git_snapshot(),
    }
    status_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    append_cockpit_log(
        "render-worker failure: "
        f"reason={safe_reason} "
        f"worker_exit_status={worker_exit_status}"
        + (
            f" publisher_exit_status={compact_publisher_status}"
            if compact_publisher_status is not None
            else ""
        )
    )


def record_render_worker_failure_status(
    *,
    reason: str,
    worker_exit_status: int,
    publisher_exit_status: int | None = None,
    message: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    try:
        write_render_worker_failure_status(
            reason=reason,
            worker_exit_status=worker_exit_status,
            publisher_exit_status=publisher_exit_status,
            message=message,
            details=details,
        )
    except OSError as exc:
        emit(f"could not write render worker failure status: {type(exc).__name__}")


def record_environment_preflight_failure_status(errors: list[str]) -> None:
    """Record startup preflight failures when the configured workdir is safe to touch."""
    failed_keys = preflight_error_keys(errors)
    if "AUTOMOAT_WORKDIR" in failed_keys:
        emit("skipping render worker failure status because AUTOMOAT_WORKDIR is invalid")
        return

    categories = preflight_error_categories(errors)
    message = (
        f"error_count={len(errors)} "
        f"error_categories={','.join(categories) or 'unknown'} "
        f"failed_configuration_keys={','.join(failed_keys) or 'unknown'}"
    )
    record_render_worker_failure_status(
        reason=ENVIRONMENT_PREFLIGHT_FAILED,
        worker_exit_status=2,
        message=message,
    )


def start_publisher() -> subprocess.Popen[object]:
    require_env("AUTOMOAT_RELAY_URL")
    require_env("AUTOMOAT_RELAY_TOKEN")
    workdir, _codex_home = configured_worker_paths(os.environ)
    command = relay_publisher_command(os.environ)
    runtime_config = relay_publisher_runtime_config(os.environ)
    try:
        process = subprocess.Popen(
            command,
            cwd=workdir,
            env=os.environ.copy(),
        )
    except OSError as exc:
        raise RuntimeError(
            f"could not start relay publisher: {type(exc).__name__}"
        ) from None
    CHILDREN.append(process)
    runtime_fields = " ".join(
        f"publisher_{key}={value}" for key, value in runtime_config.items()
    )
    emit(f"started relay publisher pid={process.pid} {runtime_fields}")
    return process


def start_loop() -> subprocess.Popen[object]:
    workdir, _codex_home = configured_worker_paths(os.environ)
    runtime_config = autonomous_loop_runtime_config(os.environ)
    command = [
        sys.executable,
        "scripts/run_autonomous_agent_loop.py",
        "--iterations",
        runtime_config["iterations"],
        "--interval",
        runtime_config["interval"],
    ]
    try:
        process = subprocess.Popen(command, cwd=workdir, env=os.environ.copy())
    except OSError as exc:
        raise RuntimeError(
            f"could not start autonomous loop: {type(exc).__name__}"
        ) from None
    CHILDREN.append(process)
    runtime_fields = " ".join(
        f"loop_{key}={value}" for key, value in runtime_config.items()
    )
    emit(f"started autonomous loop pid={process.pid} {runtime_fields}")
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
    status, poll_ok = safe_child_poll(process, label)
    if status is None:
        return None
    if not poll_ok:
        return CHILD_POLL_FAILURE_EXIT_STATUS

    worker_status = clean_exit_status if status == 0 and clean_exit_status is not None else status
    emit(
        f"{label} exited during startup status={status}; "
        f"worker_exit_status={worker_status}"
    )
    return worker_status


def safe_child_poll(
    process: subprocess.Popen[object],
    label: str,
) -> tuple[int | None, bool]:
    try:
        return process.poll(), True
    except OSError as exc:
        emit(
            f"could not poll {label} pid={process.pid}: {type(exc).__name__}; "
            f"worker_exit_status={CHILD_POLL_FAILURE_EXIT_STATUS}"
        )
        return CHILD_POLL_FAILURE_EXIT_STATUS, False


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

        loop_status, loop_poll_ok = safe_child_poll(loop_process, "autonomous loop")
        if loop_status is not None:
            if loop_poll_ok:
                emit(f"autonomous loop exited status={loop_status}")
            stop_children()
            return loop_status

        publisher_status, publisher_poll_ok = safe_child_poll(
            publisher_process,
            "relay publisher",
        )
        if publisher_status is not None:
            if publisher_poll_ok:
                emit(
                    "relay publisher exited unexpectedly "
                    f"status={publisher_status}; stopping autonomous loop"
                )
            stop_children()
            return publisher_status if publisher_status != 0 else 1

        time.sleep(poll_interval)


def terminate_process(
    process: subprocess.Popen[object],
    *,
    label: str = "child",
    grace_seconds: float = 15.0,
) -> None:
    status, poll_ok = safe_child_poll(process, label)
    if status is not None or not poll_ok:
        return
    try:
        process.terminate()
    except OSError as exc:
        emit(f"could not terminate {label} pid={process.pid}: {type(exc).__name__}")
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        status, poll_ok = safe_child_poll(process, label)
        if status is not None or not poll_ok:
            return
        time.sleep(0.2)
    status, poll_ok = safe_child_poll(process, label)
    if status is None and poll_ok:
        try:
            process.kill()
        except OSError as exc:
            emit(f"could not kill {label} pid={process.pid}: {type(exc).__name__}")


def monitor_scheduled_loop(
    loop_process: subprocess.Popen[object],
    publisher_process: subprocess.Popen[object],
    *,
    env: os._Environ[str] | dict[str, str] | None = None,
    poll_interval: float = 5.0,
) -> tuple[str, int]:
    """Monitor a running loop and stop it when the configured business window closes."""
    while True:
        if STOP_REQUESTED:
            stop_children()
            return LOOP_EXITED, 0

        state = current_business_hours_state(env)
        if not state["in_business_hours"]:
            emit(
                "business hours closed; stopping autonomous loop "
                f"local_time={state.get('local_time')} "
                f"next_start_at={state.get('next_start_at')}"
            )
            terminate_process(loop_process, label="autonomous loop")
            write_business_hours_pause_status(state)
            return BUSINESS_HOURS_CLOSED, 0

        loop_status, loop_poll_ok = safe_child_poll(loop_process, "autonomous loop")
        if loop_status is not None:
            if loop_poll_ok:
                emit(f"autonomous loop exited status={loop_status}")
            else:
                stop_children()
            return LOOP_EXITED, loop_status

        publisher_status, publisher_poll_ok = safe_child_poll(
            publisher_process,
            "relay publisher",
        )
        if publisher_status is not None:
            if publisher_poll_ok:
                emit(
                    "relay publisher exited unexpectedly "
                    f"status={publisher_status}; stopping autonomous loop"
                )
            terminate_process(loop_process, label="autonomous loop")
            record_render_worker_failure_status(
                reason=PUBLISHER_EXITED,
                worker_exit_status=publisher_status if publisher_status != 0 else 1,
                publisher_exit_status=publisher_status if publisher_poll_ok else None,
            )
            if not publisher_poll_ok:
                stop_children()
            return PUBLISHER_EXITED, publisher_status if publisher_status != 0 else 1

        time.sleep(poll_interval)


def sleep_outside_business_hours(
    publisher_process: subprocess.Popen[object],
    state: dict[str, object],
    *,
    env: os._Environ[str] | dict[str, str] | None = None,
    poll_interval: float = 5.0,
) -> tuple[str, int]:
    env = env if env is not None else os.environ
    settings = business_hours_settings(env)
    idle_sleep = float(settings["idle_sleep"])
    wait_seconds = min(max(idle_sleep, 1.0), max(seconds_until_next_business_start(state), 1.0))
    deadline = time.monotonic() + wait_seconds
    while not STOP_REQUESTED and time.monotonic() < deadline:
        publisher_status, publisher_poll_ok = safe_child_poll(
            publisher_process,
            "relay publisher",
        )
        if publisher_status is not None:
            if publisher_poll_ok:
                emit(f"relay publisher exited unexpectedly status={publisher_status}")
            return PUBLISHER_EXITED, publisher_status if publisher_status != 0 else 1
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
    if STOP_REQUESTED:
        stop_children()
        return LOOP_EXITED, 0
    return BUSINESS_HOURS_CLOSED, 0


def run_business_hours_schedule(
    publisher_process: subprocess.Popen[object],
    *,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> int:
    env = env if env is not None else os.environ
    while not STOP_REQUESTED:
        state = current_business_hours_state(env)
        if state["in_business_hours"]:
            emit(
                "business hours open; starting autonomous loop "
                f"local_time={state.get('local_time')}"
            )
            loop_process = start_loop()
            loop_startup_status = child_startup_exit_status(loop_process, "autonomous loop")
            if loop_startup_status is not None:
                stop_children()
                return loop_startup_status
            reason, status = monitor_scheduled_loop(loop_process, publisher_process, env=env)
            if reason == BUSINESS_HOURS_CLOSED:
                continue
            return status

        emit(
            "outside business hours; autonomous loop paused "
            f"local_time={state.get('local_time')} "
            f"next_start_at={state.get('next_start_at')}"
        )
        write_business_hours_pause_status(state)
        reason, status = sleep_outside_business_hours(publisher_process, state, env=env)
        if reason == PUBLISHER_EXITED:
            return status

    stop_children()
    return 0


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
        try:
            child_running = child.poll() is None
        except OSError as exc:
            emit(f"could not poll child pid={child.pid}: {type(exc).__name__}")
            continue
        if child_running:
            try:
                child.terminate()
            except OSError as exc:
                emit(f"could not terminate child pid={child.pid}: {type(exc).__name__}")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if all(child_exited(child) for child in CHILDREN):
            return
        time.sleep(0.2)
    for child in list(CHILDREN):
        try:
            child_running = child.poll() is None
        except OSError as exc:
            emit(f"could not poll child pid={child.pid}: {type(exc).__name__}")
            continue
        if child_running:
            try:
                child.kill()
            except OSError as exc:
                emit(f"could not kill child pid={child.pid}: {type(exc).__name__}")


def child_exited(child: subprocess.Popen[object]) -> bool:
    try:
        return child.poll() is not None
    except OSError as exc:
        emit(f"could not poll child pid={child.pid}: {type(exc).__name__}")
        return True


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
        record_environment_preflight_failure_status(env_errors)
        return 2

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    configure_git_auth()
    configure_codex_auth()
    sync_repo()
    try:
        check_relay_publisher_preflight()
    except RuntimeError as exc:
        failure_kwargs: dict[str, object] = {
            "reason": "relay_publisher_preflight_failed",
            "worker_exit_status": 1,
            "message": str(exc),
        }
        preflight_details = publisher_preflight_failure_details(exc)
        if preflight_details:
            failure_kwargs["details"] = preflight_details
        record_render_worker_failure_status(**failure_kwargs)
        return 1
    try:
        publisher = start_publisher()
    except RuntimeError as exc:
        record_render_worker_failure_status(
            reason="relay_publisher_start_failed",
            worker_exit_status=1,
            message=str(exc),
        )
        return 1
    publisher_startup_status = child_startup_exit_status(
        publisher,
        "relay publisher",
        clean_exit_status=1,
    )
    if publisher_startup_status is not None:
        record_render_worker_failure_status(
            reason="relay_publisher_startup_exit",
            worker_exit_status=publisher_startup_status,
            publisher_exit_status=publisher.returncode,
        )
        stop_children()
        return publisher_startup_status

    return run_business_hours_schedule(publisher)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - make Render logs immediately actionable.
        emit(f"fatal: {exc}")
        stop_children()
        raise
