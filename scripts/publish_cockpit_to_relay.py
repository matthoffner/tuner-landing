#!/usr/bin/env python3
"""Publish local Autom oat cockpit status snapshots to the Render relay."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-loop-status.json"
PID_FILE = ROOT / ".automoat" / "state" / "mvp-loop.pid"
LOG_FILE = ROOT / ".automoat" / "logs" / "mvp-loop.log"
PUBLISHER_LOG = ROOT / ".automoat" / "logs" / "cockpit-relay-publisher.log"
BRIDGE_STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-bridge-status.json"
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_MAX_CONSECUTIVE_STALE_STATUSES = 0
DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES = 0
DEFAULT_STATUS_STALE_AFTER_SECONDS = 660
DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS = 660
MAX_RELAY_URL_CHARS = 500
MAX_RELAY_TOKEN_CHARS = 8192
MAX_RELAY_RESPONSE_BYTES = 64 * 1024
MAX_LOCAL_STATUS_JSON_BYTES = 128 * 1024
MAX_LOCAL_BRIDGE_STATUS_JSON_BYTES = 128 * 1024
PUBLISHER_RUNTIME_DEFAULTS = {
    "interval": 3.0,
    "timeout": 8.0,
    "tail_lines": 180,
    "max_log_bytes": 256 * 1024,
    "max_consecutive_failures": DEFAULT_MAX_CONSECUTIVE_FAILURES,
    "max_consecutive_stale_statuses": DEFAULT_MAX_CONSECUTIVE_STALE_STATUSES,
    "max_consecutive_stale_bridge_statuses": DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES,
    "status_stale_after_seconds": DEFAULT_STATUS_STALE_AFTER_SECONDS,
    "bridge_status_stale_after_seconds": DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
}
PUBLISHER_RUNTIME_CONFIG_KEYS = (
    ("interval", "AUTOMOAT_RELAY_INTERVAL", "--interval"),
    ("timeout", "AUTOMOAT_RELAY_TIMEOUT", "--timeout"),
    ("tail_lines", "AUTOMOAT_RELAY_TAIL_LINES", "--tail-lines"),
    ("max_log_bytes", "AUTOMOAT_RELAY_MAX_LOG_BYTES", "--max-log-bytes"),
    (
        "max_consecutive_failures",
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
        "--max-consecutive-failures",
    ),
    (
        "max_consecutive_stale_statuses",
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
        "--max-consecutive-stale-statuses",
    ),
    (
        "max_consecutive_stale_bridge_statuses",
        "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES",
        "--max-consecutive-stale-bridge-statuses",
    ),
    (
        "status_stale_after_seconds",
        "AUTOMOAT_STATUS_STALE_AFTER_SECONDS",
        "--status-stale-after-seconds",
    ),
    (
        "bridge_status_stale_after_seconds",
        "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
        "--bridge-status-stale-after-seconds",
    ),
)
PUBLISHER_FILE_CONFIG_KEYS = (
    ("status_file", None, "--status-file", STATUS_FILE),
    ("pid_file", None, "--pid-file", PID_FILE),
    ("log_file", None, "--log-file", LOG_FILE),
    ("publisher_log", None, "--publisher-log", PUBLISHER_LOG),
    (
        "bridge_status_file",
        "AUTOMOAT_BRIDGE_STATUS_FILE",
        "AUTOMOAT_BRIDGE_STATUS_FILE|--bridge-status-file",
        BRIDGE_STATUS_FILE,
    ),
)
PUBLISHER_CONFIG_LIMITS = {
    "interval": 60,
    "timeout": 60,
    "tail_lines": 2000,
    "max_log_bytes": 1024 * 1024,
    "max_consecutive_failures": 100,
    "max_consecutive_stale_statuses": 100,
    "max_consecutive_stale_bridge_statuses": 100,
    "status_stale_after_seconds": 3600,
    "bridge_status_stale_after_seconds": 3600,
}
URL_TEXT_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
PUBLISHER_LOG_URL_TEXT_PATTERN = re.compile(r"https?://[^\s'\"<>,;]+")
PATH_TEXT_PATTERN = re.compile(r"(?<![\w:/])(?:~|/)[^\s,;|'\"\])}]+")
BEARER_SECRET_PATTERN = re.compile(
    r"\b(authorization\s*[:=]\s*bearer)\s+[^\s,;]+",
    re.IGNORECASE,
)
SENSITIVE_KEY_PATTERN = (
    r"(?:[A-Za-z0-9]+[_-])*"
    r"(?:access[_-]?token|api[_-]?key|codex[_-]?access[_-]?token|gh[_-]?token|"
    r"github[_-]?token|password|passwd|relay[_-]?token|secret|token|key|"
    r"x-automoat-relay-token)"
    r"(?:[_-][A-Za-z0-9]+)*"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    rf"\b({SENSITIVE_KEY_PATTERN})\s*[:=]\s*[^\s,;|]+",
    re.IGNORECASE,
)
PUBLISHER_LOG_SECRET_ASSIGNMENT_PATTERN = re.compile(
    rf"\b({SENSITIVE_KEY_PATTERN})\s*[:=]\s*(?!\[redacted\])[^\s,;|]+",
    re.IGNORECASE,
)
SENSITIVE_DOUBLE_QUOTED_FIELD_PATTERN = re.compile(
    rf'"{SENSITIVE_KEY_PATTERN}"\s*:\s*"(?:\\.|[^"\\\r\n])*"',
    re.IGNORECASE,
)
SENSITIVE_SINGLE_QUOTED_FIELD_PATTERN = re.compile(
    rf"'{SENSITIVE_KEY_PATTERN}'\s*:\s*'(?:\\.|[^'\\\r\n])*'",
    re.IGNORECASE,
)
SOURCE_HEALTH_LABELS = {
    "source_render_worker_failure": "Render worker failed",
    "source_autonomy_policy_failed": "Autonomy policy failed",
    "source_bridge_degraded": "Source bridge is degraded",
    "source_bridge_status_failing": "Source bridge status is failing",
    "source_bridge_status_stale": "Source bridge status is stale",
    "source_bridge_status_timestamp_future": "Source bridge status is in the future",
    "source_bridge_status_timestamp_invalid": "Source bridge status timestamp is invalid",
    "source_bridge_status_unavailable": "Source bridge status is unavailable",
    "source_cockpit_attention": "Source cockpit needs attention",
    "source_handoff_coordination_unavailable": "Source coordination handoff is unavailable",
    "source_handoff_coordination_incomplete": "Source coordination handoff is incomplete",
    "source_status_unavailable": "Source status is unavailable",
    "source_status_timestamp_invalid": "Source status timestamp is invalid",
    "source_status_timestamp_future": "Source status timestamp is in the future",
    "source_status_stale": "Source status is stale",
    "source_loop_not_running": "Source loop is not running",
    "source_status_failing": "Source status is failing",
}
OPERATOR_ATTENTION_LABELS = {
    "loop_not_running": "Loop is not running",
    "status_unavailable": "Status file is unavailable",
    "status_failing": "Loop status is failing",
    "autonomy_policy_failed": "Autonomy policy failed",
    "status_stale": "Status is stale",
    "status_timestamp_invalid": "Status timestamp is invalid",
    "status_timestamp_future": "Status timestamp is in the future",
    "handoff_coordination_unavailable": "Coordination handoff is unavailable",
    "handoff_coordination_incomplete": "Coordination handoff is incomplete",
    "artifact_health_not_loaded": "Artifact health is not loaded",
    "import_readiness_not_ready": "Import readiness is not ready",
    "import_readiness_blocked": "Import readiness is blocked",
    "coverage_thin_groups_present": "Coverage has thin groups",
}
POLICY_RAW_PATH_SAMPLE_LIMIT = 8
POLICY_ROW_SAMPLE_LIMIT = 5
IMPORT_APPEND_SEQUENCE_SAMPLE_LIMIT = 4


class PublisherArgumentError(Exception):
    """Raised when argparse rejects publisher CLI/env configuration."""


class PublisherArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise PublisherArgumentError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PUBLISHER_STARTED_AT = utc_now()
PUBLISHER_SNAPSHOT_SEQUENCE = 0


def emit(message: str, *, log_path: Path) -> None:
    safe_message = sanitize_publisher_log_message(message)
    line = f"[{utc_now()}] {safe_message}"
    print(line, flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def repo_relative(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        relative_path = resolved_path.relative_to(ROOT)
    except ValueError:
        return f"<external>/{resolved_path.name}" if resolved_path.name else "<external>"
    relative_text = relative_path.as_posix()
    return relative_text if relative_text else "."


def read_json_limited(path: Path, max_bytes: int) -> tuple[Any | None, str | None, str | None]:
    try:
        with path.open("rb") as handle:
            payload_bytes = handle.read(max_bytes + 1)
    except OSError as exc:
        return None, "read_failed", compact_path_error(exc, path)
    if len(payload_bytes) > max_bytes:
        return (
            None,
            "too_large",
            f"file exceeds max JSON bytes ({len(payload_bytes)} > {max_bytes})",
        )
    try:
        payload_text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, "invalid_json", f"invalid UTF-8 at byte {exc.start}"
    try:
        payload = json.loads(payload_text, parse_constant=reject_json_constant)
    except json.JSONDecodeError as exc:
        return None, "invalid_json", f"line {exc.lineno} column {exc.colno}: {exc.msg}"
    except ValueError as exc:
        return None, "invalid_json", compact_text(str(exc)) or type(exc).__name__

    non_finite_path = first_non_finite_json_number_path(payload)
    if non_finite_path is not None:
        return None, "invalid_json", f"non-finite JSON number at {non_finite_path}"
    return payload, None, None


def read_json_with_status(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "source_status_file": repo_relative(path),
        "source_status_file_status": "loaded",
    }
    if not path.exists():
        metadata["source_status_file_status"] = "missing"
        return None, metadata
    payload, status, error = read_json_limited(path, MAX_LOCAL_STATUS_JSON_BYTES)
    if status is not None:
        metadata["source_status_file_status"] = status
        metadata["source_status_file_error"] = error or status
        return None, metadata
    if not isinstance(payload, dict):
        metadata["source_status_file_status"] = "not_object"
        metadata["source_status_file_error"] = type(payload).__name__
        return None, metadata
    return payload, metadata


def read_json(path: Path) -> dict[str, Any] | None:
    payload, _metadata = read_json_with_status(path)
    return payload


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def json_path_component(value: Any) -> str:
    key = compact_policy_detail(value, max_length=80)
    if key is None:
        return "<?>"
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return f".{key}"
    return f"[{json.dumps(key)}]"


def first_non_finite_json_number_path(value: Any, path: str = "$") -> str | None:
    if isinstance(value, float) and not math.isfinite(value):
        return path
    if isinstance(value, dict):
        for key, item in value.items():
            nested_path = first_non_finite_json_number_path(
                item,
                f"{path}{json_path_component(key)}",
            )
            if nested_path is not None:
                return nested_path
    if isinstance(value, list):
        for index, item in enumerate(value):
            nested_path = first_non_finite_json_number_path(item, f"{path}[{index}]")
            if nested_path is not None:
                return nested_path
    return None


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def status_freshness(status: dict[str, Any], stale_after_seconds: int) -> dict[str, Any]:
    updated_at_value = status.get("updated_at")
    updated_at = parse_utc_timestamp(updated_at_value)
    current_time = parse_utc_timestamp(utc_now())
    timestamp_invalid = compact_text(updated_at_value) is not None and updated_at is None
    if updated_at is None or current_time is None:
        return {
            "source_status_age_seconds": None,
            "source_status_stale_after_seconds": stale_after_seconds,
            "source_status_stale": True,
            "source_status_timestamp_invalid": timestamp_invalid,
            "source_status_timestamp_future": False,
        }
    if updated_at > current_time:
        return {
            "source_status_age_seconds": None,
            "source_status_stale_after_seconds": stale_after_seconds,
            "source_status_stale": True,
            "source_status_timestamp_invalid": False,
            "source_status_timestamp_future": True,
        }
    age_seconds = max(0, int((current_time - updated_at).total_seconds()))
    return {
        "source_status_age_seconds": age_seconds,
        "source_status_stale_after_seconds": stale_after_seconds,
        "source_status_stale": age_seconds > stale_after_seconds,
        "source_status_timestamp_invalid": False,
        "source_status_timestamp_future": False,
    }


def bridge_status_freshness(
    status: dict[str, Any],
    stale_after_seconds: int,
) -> dict[str, Any]:
    updated_at_value = status.get("updated_at")
    updated_at = parse_utc_timestamp(updated_at_value)
    current_time = parse_utc_timestamp(utc_now())
    timestamp_invalid = compact_text(updated_at_value) is not None and updated_at is None
    if updated_at is None or current_time is None:
        return {
            "bridge_status_age_seconds": None,
            "bridge_status_stale_after_seconds": stale_after_seconds,
            "bridge_status_stale": True,
            "bridge_status_timestamp_invalid": timestamp_invalid,
            "bridge_status_timestamp_future": False,
        }
    if updated_at > current_time:
        return {
            "bridge_status_age_seconds": None,
            "bridge_status_stale_after_seconds": stale_after_seconds,
            "bridge_status_stale": True,
            "bridge_status_timestamp_invalid": False,
            "bridge_status_timestamp_future": True,
        }
    age_seconds = max(0, int((current_time - updated_at).total_seconds()))
    return {
        "bridge_status_age_seconds": age_seconds,
        "bridge_status_stale_after_seconds": stale_after_seconds,
        "bridge_status_stale": age_seconds > stale_after_seconds,
        "bridge_status_timestamp_invalid": False,
        "bridge_status_timestamp_future": False,
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def first_string_list(*values: Any) -> list[str]:
    """Return the first non-empty compact string list from candidate payload fields."""
    for value in values:
        items = as_string_list(value)
        if items:
            return items
    return []


def compact_text(value: Any, *, max_length: int = 180) -> str | None:
    if not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = "".join(
        " "
        if character in "\r\n" or ord(character) < 32 or ord(character) == 127
        else character
        for character in text
    )
    text = " ".join(text.split())
    return text[:max_length] if text else None


def compact_path_error(exc: BaseException, path: Path, *, max_length: int = 180) -> str:
    message = str(exc)
    safe_label = repo_relative(path)
    path_strings = {str(path)}
    try:
        path_strings.add(str(path.resolve()))
    except OSError:
        pass
    for path_string in sorted(path_strings, key=len, reverse=True):
        if path_string:
            message = message.replace(path_string, safe_label)
    return compact_text(message, max_length=max_length) or type(exc).__name__


def sanitize_url_value(value: str) -> str:
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


def compact_url(value: Any, *, max_length: int = 180) -> str | None:
    text = compact_text(value, max_length=max_length)
    if text is None:
        return None
    return sanitize_url_value(text)


def compact_path_label(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_text(value, max_length=max_length)
    if text is None:
        return None
    if text.startswith(("/", "~")):
        return repo_relative(Path(text))[:max_length]
    return text


def compact_policy_detail(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_text(value, max_length=max_length * 2)
    if text is None:
        return None
    text = URL_TEXT_PATTERN.sub(lambda match: sanitize_url_value(match.group(0)), text)
    text = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", text)
    text = sanitize_sensitive_quoted_fields(text)
    text = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )
    return text[:max_length] if text else None


def sanitize_sensitive_quoted_fields(text: str) -> str:
    text = SENSITIVE_DOUBLE_QUOTED_FIELD_PATTERN.sub(
        lambda match: re.sub(
            r'"\s*:\s*"(?:\\.|[^"\\\r\n])*"$',
            '":"[redacted]"',
            match.group(0),
        ),
        text,
    )
    return SENSITIVE_SINGLE_QUOTED_FIELD_PATTERN.sub(
        lambda match: re.sub(
            r"'\s*:\s*'(?:\\.|[^'\\\r\n])*'$",
            "':'[redacted]'",
            match.group(0),
        ),
        text,
    )


def compact_path_diagnostic(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_policy_detail(value, max_length=max_length * 2)
    if text is None:
        return None
    text = PATH_TEXT_PATTERN.sub(
        lambda match: repo_relative(Path(match.group(0))),
        text,
    )
    return compact_text(text, max_length=max_length)


def compact_policy_detail_list(
    value: Any,
    *,
    max_items: int = POLICY_RAW_PATH_SAMPLE_LIMIT,
    max_length: int = 160,
) -> list[str]:
    if not isinstance(value, list):
        return []
    compacted: list[str] = []
    for item in value:
        compacted_item = compact_policy_detail(item, max_length=max_length)
        if compacted_item is not None:
            compacted.append(compacted_item)
        if len(compacted) >= max_items:
            break
    return compacted


def compact_log_detail_list(
    value: Any,
    *,
    max_items: int = 5,
    max_length: int = 80,
) -> str | None:
    compacted = compact_policy_detail_list(
        value,
        max_items=max_items,
        max_length=max_length,
    )
    return ",".join(compacted) if compacted else None


def compact_log_count_map(value: Any, *, max_items: int = 8) -> str | None:
    compacted = compact_count_map(value, max_items=max_items)
    if not compacted:
        return None
    return ",".join(f"{key}:{count}" for key, count in compacted.items())


def compact_path_detail_list(
    value: Any,
    *,
    max_items: int = POLICY_RAW_PATH_SAMPLE_LIMIT,
    max_length: int = 160,
) -> list[str]:
    if not isinstance(value, list):
        return []
    compacted: list[str] = []
    for item in value:
        path_label = compact_path_label(item, max_length=max_length)
        compacted_item = compact_policy_detail(path_label, max_length=max_length)
        if compacted_item is not None:
            compacted.append(compacted_item)
        if len(compacted) >= max_items:
            break
    return compacted


def compact_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def compact_exit_status(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def first_compact_int(*values: Any) -> int | None:
    for value in values:
        parsed = compact_int(value)
        if parsed is not None:
            return parsed
    return None


def first_bool(*values: Any) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def compact_count_map(value: Any, *, max_items: int = 8) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    compacted: dict[str, int] = {}
    for raw_key, raw_value in sorted(value.items(), key=lambda item: str(item[0])):
        key = compact_policy_detail(raw_key, max_length=80)
        count = compact_int(raw_value)
        if key is None or count is None:
            continue
        compacted[key] = count
        if len(compacted) >= max_items:
            break
    return compacted


def compact_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def bridge_health_summary(value: Any) -> dict[str, Any]:
    health = value if isinstance(value, dict) else {}
    reasons = compact_policy_detail_list(
        health.get("reasons"),
        max_items=5,
        max_length=160,
    )
    primary_reason = compact_policy_detail(health.get("primary_reason"), max_length=160)
    if primary_reason is None and reasons:
        primary_reason = reasons[0]
    status = compact_policy_detail(health.get("status"), max_length=80) or (
        "degraded" if reasons else "unknown"
    )
    ok = health.get("ok")
    if not isinstance(ok, bool):
        ok = status == "live"
    label = compact_policy_detail(health.get("label"), max_length=160) or (
        "Live" if primary_reason is None else primary_reason.replace("_", " ")
    )
    return {
        "status": status,
        "ok": ok,
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": label,
    }


def read_bridge_summary(
    path: Path | None = None,
    stale_after_seconds: int = DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
) -> dict[str, Any]:
    if path is None:
        path = BRIDGE_STATUS_FILE
    status_file = repo_relative(path)
    if not path.exists():
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "missing",
        }
    payload, status, error = read_json_limited(path, MAX_LOCAL_BRIDGE_STATUS_JSON_BYTES)
    if status is not None:
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": status,
            "status_file_error": error or status,
        }
    if not isinstance(payload, dict):
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "not_object",
            "status_file_error": type(payload).__name__,
        }

    summary: dict[str, Any] = {
        "available": True,
        "status_file": status_file,
        "status_file_status": "loaded",
        "bridge_health": bridge_health_summary(payload.get("bridge_health")),
        **bridge_status_freshness(payload, stale_after_seconds),
    }
    bridge_status_value, bridge_status_value_invalid = normalize_source_status_value(
        payload.get("status")
    )
    summary["bridge_status_value_invalid"] = bridge_status_value_invalid
    if payload.get("status") is not None or bridge_status_value_invalid:
        summary["status"] = bridge_status_value

    text_fields = {
        "updated_at": payload.get("updated_at"),
        "bridge_started_at": payload.get("bridge_started_at"),
        "mode": payload.get("mode"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value)
        if compact_value is not None:
            summary[key] = compact_value

    url_fields = {
        "public_url": payload.get("public_url"),
        "local_read_only_url": payload.get("local_read_only_url"),
        "ngrok_api_url": payload.get("ngrok_api_url"),
    }
    for key, value in url_fields.items():
        compact_value = compact_url(value)
        if compact_value is not None:
            summary[key] = compact_value

    int_fields = {
        "bridge_pid": payload.get("bridge_pid"),
        "bridge_status_sequence": payload.get("bridge_status_sequence"),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    interval = compact_float(payload.get("interval"))
    if interval is not None:
        summary["interval"] = interval
    return summary


def operator_attention_label(reason: str | None) -> str:
    if reason is None:
        return "Clear"
    return OPERATOR_ATTENTION_LABELS.get(reason, reason.replace("_", " "))


def normalize_source_status_value(value: Any) -> tuple[str, bool]:
    if value is None:
        return "waiting", False
    if not isinstance(value, str):
        return "invalid-status-value", True
    compact_value = compact_policy_detail(value, max_length=80)
    if compact_value is None:
        return "waiting", True
    return compact_value, False


def failed_autonomy_policy_step(status: dict[str, Any]) -> dict[str, Any] | None:
    step = latest_autonomy_policy_step(status)
    if step is not None and step.get("exit_status") != 0:
        return step
    return None


def latest_autonomy_policy_step(status: dict[str, Any]) -> dict[str, Any] | None:
    steps = status.get("steps")
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        if step.get("name") != "autonomy policy check":
            continue
        return step
    return None


def import_handoff_summary(import_pipeline: dict[str, Any]) -> dict[str, Any]:
    handoff = as_dict(import_pipeline.get("next_import_record_handoff"))
    if not handoff:
        return {"available": False}

    preflight = as_dict(handoff.get("raw_file_append_preflight"))
    preflight_checks = {
        str(name): passed
        for name, passed in as_dict(preflight.get("checks")).items()
        if isinstance(passed, bool)
    }
    next_append_rows = {
        str(name): row_number
        for name, value in as_dict(handoff.get("raw_file_next_append_rows")).items()
        if (row_number := compact_int(value)) is not None
    }
    append_sequence_source = handoff.get("raw_file_append_sequence")
    append_sequence: list[dict[str, Any]] = []
    if isinstance(append_sequence_source, list):
        for item in append_sequence_source:
            if not isinstance(item, dict):
                continue
            sequence_item: dict[str, Any] = {}
            for key in ("file_name", "status", "template_line"):
                compact_value = compact_policy_detail(item.get(key), max_length=240)
                if compact_value is not None:
                    sequence_item[key] = compact_value
            file_path = compact_path_label(item.get("file_path"), max_length=240)
            if file_path is not None:
                file_path = compact_policy_detail(file_path, max_length=240)
            if file_path is not None:
                sequence_item["file_path"] = file_path
            row_number = compact_int(item.get("csv_row_number"))
            if row_number is not None:
                sequence_item["csv_row_number"] = row_number
            if sequence_item:
                append_sequence.append(sequence_item)
            if len(append_sequence) >= IMPORT_APPEND_SEQUENCE_SAMPLE_LIMIT:
                break
    summary: dict[str, Any] = {
        "available": True,
        "next_append_rows": next_append_rows,
        "append_preflight_status": compact_text(preflight.get("status")) or "unknown",
        "append_preflight_checks": preflight_checks,
        "append_preflight_blockers": as_string_list(preflight.get("blockers")),
        "append_sequence": append_sequence,
    }
    if isinstance(append_sequence_source, list):
        summary["append_sequence_count"] = len(
            [item for item in append_sequence_source if isinstance(item, dict)]
        )

    ready_for_append = preflight.get("ready_for_append")
    if isinstance(ready_for_append, bool):
        summary["ready_for_append"] = ready_for_append

    raw_dir = compact_path_label(handoff.get("raw_dir"), max_length=240)
    if raw_dir is not None:
        raw_dir = compact_policy_detail(raw_dir, max_length=240)
    if raw_dir is not None:
        summary["raw_dir"] = raw_dir

    text_fields = {
        "after_edit_command": handoff.get("after_edit_command"),
        "readiness_check_command": handoff.get("readiness_check_command"),
        "raw_handoff_verification_json_command": handoff.get(
            "raw_handoff_verification_json_command"
        ),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value)
        if compact_value is not None:
            summary[key] = compact_value
    return summary


def coordination_summary(status: dict[str, Any]) -> dict[str, Any]:
    coordination = as_dict(status.get("coordination"))
    if not coordination:
        return {"available": False}

    summary: dict[str, Any] = {"available": True}
    fields = {
        "handoff_path": coordination.get("handoff_path"),
        "handoff_file_status": coordination.get("handoff_file_status"),
        "latest_handoff_timestamp": coordination.get("latest_handoff_timestamp"),
        "latest_handoff_lane": coordination.get("latest_handoff_lane"),
        "latest_handoff_status": coordination.get("latest_handoff_status"),
        "handoff_error": coordination.get("handoff_error"),
    }
    for key, value in fields.items():
        compact_value = compact_policy_detail(value)
        if compact_value is not None:
            summary[key] = compact_value
    for key in ("latest_section_found", "latest_status_found"):
        value = coordination.get(key)
        if isinstance(value, bool):
            summary[key] = value
    age_seconds = compact_int(coordination.get("handoff_age_seconds"))
    if age_seconds is not None:
        summary["handoff_age_seconds"] = age_seconds
    return summary


def business_hours_summary(value: Any) -> dict[str, Any]:
    business_hours = as_dict(value)
    if not business_hours:
        return {"available": False}

    summary: dict[str, Any] = {"available": True}
    for key in ("enabled", "in_business_hours", "active_pause"):
        field_value = business_hours.get(key)
        if isinstance(field_value, bool):
            summary[key] = field_value
    for key in (
        "timezone",
        "start",
        "end",
        "days",
        "local_time",
        "local_weekday",
        "next_start_at",
    ):
        compact_value = compact_policy_detail(business_hours.get(key), max_length=120)
        if compact_value is not None:
            summary[key] = compact_value
    if "active_pause" not in summary:
        summary["active_pause"] = summary.get("in_business_hours") is False
    return summary


def business_hours_pause_active(status: dict[str, Any]) -> bool:
    status_value = compact_policy_detail(status.get("status"), max_length=80)
    phase_value = compact_policy_detail(status.get("phase"), max_length=120)
    business_hours = as_dict(status.get("business_hours"))
    if not business_hours:
        cockpit_summary = as_dict(status.get("cockpit_summary"))
        business_hours = as_dict(cockpit_summary.get("business_hours"))
    active_pause = (
        business_hours.get("active_pause") is True
        or business_hours.get("in_business_hours") is False
    )
    return (
        status_value == "paused"
        and phase_value == "outside_business_hours"
        and active_pause
    )


def failure_summary(status: dict[str, Any]) -> dict[str, Any]:
    failure = as_dict(status.get("failure"))
    if not failure:
        return {"available": False}

    summary: dict[str, Any] = {"available": True}
    text_fields = {
        "phase": failure.get("phase"),
        "category": failure.get("category"),
        "route_hint": failure.get("route_hint"),
        "message": failure.get("message"),
        "failure_reason": failure.get("failure_reason"),
        "summary": failure.get("summary"),
        "decision_reason": failure.get("decision_reason"),
        "current_focus": failure.get("current_focus"),
        "import_pipeline_status": failure.get("import_pipeline_status"),
        "readiness_status": failure.get("readiness_status"),
        "artifact_health_status": failure.get("artifact_health_status"),
        "command": failure.get("command"),
        "termination_reason": failure.get("termination_reason"),
        "failed_step": failure.get("failed_step"),
        "failed_substep": failure.get("failed_substep"),
        "setup_stage": failure.get("setup_stage"),
        "child_label": failure.get("child_label"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value)
        if compact_value is not None:
            summary[key] = compact_value

    path_fields = {
        "import_pipeline_summary_path": failure.get("import_pipeline_summary_path"),
        "source_path": failure.get("source_path"),
        "target_path": failure.get("target_path"),
    }
    for key, value in path_fields.items():
        compact_value = compact_path_diagnostic(value)
        if compact_value is not None:
            summary[key] = compact_value

    list_fields = {
        "readiness_blockers": failure.get("readiness_blockers"),
        "degraded_artifacts": failure.get("degraded_artifacts"),
    }
    for key, value in list_fields.items():
        compact_value = compact_policy_detail_list(value)
        if compact_value:
            summary[key] = compact_value

    sample_fields = {
        "synthetic_row_samples": (
            failure.get("synthetic_row_samples"),
            POLICY_ROW_SAMPLE_LIMIT,
            240,
        ),
        "raw_dallas_csv_changed_path_samples": (
            failure.get("raw_dallas_csv_changed_path_samples"),
            POLICY_RAW_PATH_SAMPLE_LIMIT,
            160,
        ),
        "productive_changed_path_samples": (
            failure.get("productive_changed_path_samples"),
            POLICY_RAW_PATH_SAMPLE_LIMIT,
            160,
        ),
        "non_productive_companion_path_samples": (
            failure.get("non_productive_companion_path_samples"),
            POLICY_RAW_PATH_SAMPLE_LIMIT,
            160,
        ),
    }
    for key, (value, max_items, max_length) in sample_fields.items():
        compact_value = compact_policy_detail_list(
            value,
            max_items=max_items,
            max_length=max_length,
        )
        if compact_value:
            summary[key] = compact_value

    count_fields = {
        "synthetic_row_count": failure.get("synthetic_row_count"),
        "raw_dallas_csv_changed_path_count": failure.get(
            "raw_dallas_csv_changed_path_count"
        ),
        "productive_changed_path_count": failure.get("productive_changed_path_count"),
        "non_productive_companion_path_count": failure.get(
            "non_productive_companion_path_count"
        ),
        "readiness_blocker_count": failure.get("readiness_blocker_count"),
        "degraded_artifact_count": failure.get("degraded_artifact_count"),
        "sync_exit_status": failure.get("sync_exit_status"),
        "child_pid": failure.get("child_pid"),
    }
    for key, value in count_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    exit_status_fields = {
        "codex_exit_status": failure.get("codex_exit_status"),
        "failed_step_exit_status": failure.get("failed_step_exit_status"),
        "failed_substep_exit_status": failure.get("failed_substep_exit_status"),
        "worker_exit_status": failure.get("worker_exit_status"),
        "publisher_exit_status": failure.get("publisher_exit_status"),
        "child_exit_status": failure.get("child_exit_status"),
    }
    for key, value in exit_status_fields.items():
        compact_value = compact_exit_status(value)
        if compact_value is not None:
            summary[key] = compact_value

    for key in ("timed_out", "killed_after_terminate"):
        value = failure.get(key)
        if isinstance(value, bool):
            summary[key] = value
    child_status_available = failure.get("child_status_available")
    if isinstance(child_status_available, bool):
        summary["child_status_available"] = child_status_available

    ready_for_next_import_records = failure.get("ready_for_next_import_records")
    if isinstance(ready_for_next_import_records, bool):
        summary["ready_for_next_import_records"] = ready_for_next_import_records

    raw_artifact_statuses = as_dict(failure.get("artifact_statuses"))
    artifact_statuses: dict[str, str] = {}
    for key, value in sorted(
        raw_artifact_statuses.items(),
        key=lambda item: str(item[0]),
    ):
        compact_key = compact_policy_detail(key, max_length=80)
        compact_value = compact_policy_detail(value, max_length=80)
        if compact_key is None or compact_value is None:
            continue
        artifact_statuses[compact_key] = compact_value
        if len(artifact_statuses) >= 8:
            break
    if artifact_statuses:
        summary["artifact_statuses"] = artifact_statuses

    environment_preflight = as_dict(failure.get("environment_preflight"))
    if environment_preflight:
        compact_preflight: dict[str, Any] = {}
        status_value = compact_policy_detail(environment_preflight.get("status"), max_length=80)
        if status_value is not None:
            compact_preflight["status"] = status_value
        error_count = compact_int(environment_preflight.get("error_count"))
        if error_count is not None:
            compact_preflight["error_count"] = error_count
        error_categories = compact_policy_detail_list(
            environment_preflight.get("error_categories"),
            max_items=12,
            max_length=80,
        )
        if error_categories:
            compact_preflight["error_categories"] = error_categories
        failed_keys = compact_policy_detail_list(
            environment_preflight.get("failed_configuration_keys"),
            max_items=12,
            max_length=120,
        )
        if failed_keys:
            compact_preflight["failed_configuration_keys"] = failed_keys
        if compact_preflight:
            summary["environment_preflight"] = compact_preflight

    publisher_preflight = as_dict(failure.get("publisher_preflight"))
    if publisher_preflight:
        compact_preflight: dict[str, Any] = {}
        status_value = compact_policy_detail(publisher_preflight.get("status"), max_length=80)
        if status_value is not None:
            compact_preflight["status"] = status_value
        exit_status = compact_exit_status(publisher_preflight.get("exit_status"))
        if exit_status is not None:
            compact_preflight["exit_status"] = exit_status
        error_count = compact_int(publisher_preflight.get("error_count"))
        if error_count is not None:
            compact_preflight["error_count"] = error_count
        error_categories = compact_policy_detail_list(
            publisher_preflight.get("error_categories"),
            max_items=12,
            max_length=80,
        )
        if error_categories:
            compact_preflight["error_categories"] = error_categories
        failed_keys = compact_policy_detail_list(
            publisher_preflight.get("failed_configuration_keys"),
            max_items=12,
            max_length=120,
        )
        if failed_keys:
            compact_preflight["failed_configuration_keys"] = failed_keys
        if compact_preflight:
            summary["publisher_preflight"] = compact_preflight

    return summary


def artifact_status_summary(value: object) -> dict[str, str]:
    statuses = value if isinstance(value, dict) else {}
    summary: dict[str, str] = {}
    for key, status in sorted(statuses.items()):
        artifact_name = compact_policy_detail(key, max_length=80)
        artifact_status = compact_policy_detail(status, max_length=80)
        if artifact_name is not None and artifact_status is not None:
            summary[artifact_name] = artifact_status
    return summary


def artifact_problem_summary(value: object, statuses: dict[str, str]) -> list[str]:
    explicit = as_string_list(value)
    derived = [
        name for name, artifact_status in statuses.items() if artifact_status != "loaded"
    ]
    if not explicit:
        return derived
    return explicit + [name for name in derived if name not in explicit]


def artifact_health_counts(
    health: dict[str, Any],
    statuses: dict[str, str],
) -> dict[str, int]:
    artifact_count = first_compact_int(health.get("artifact_count"), len(statuses))
    if artifact_count is None:
        artifact_count = len(statuses)
    loaded_count = first_compact_int(
        health.get("loaded_artifact_count"),
        sum(1 for status in statuses.values() if status == "loaded"),
    )
    if loaded_count is None:
        loaded_count = 0
    return {
        "artifact_count": artifact_count,
        "loaded_artifact_count": min(loaded_count, artifact_count),
    }


def publisher_cockpit_summary(status: dict[str, Any]) -> dict[str, Any]:
    artifacts = as_dict(status.get("artifacts"))
    artifact_health = as_dict(artifacts.get("artifact_health"))
    contract = as_dict(artifacts.get("contract"))
    workflow = as_dict(artifacts.get("workflow"))
    import_pipeline = as_dict(artifacts.get("import_pipeline"))
    readiness = as_dict(import_pipeline.get("execution_readiness"))
    pipeline_coverage = as_dict(import_pipeline.get("coverage"))
    autonomy_policy = as_dict(status.get("autonomy_policy"))

    passed_checks = contract.get("passed_checks")
    total_checks = contract.get("total_checks")
    contract_checks = None
    if passed_checks is not None and total_checks is not None:
        contract_checks = f"{passed_checks}/{total_checks}"

    status_value, status_value_invalid = normalize_source_status_value(
        status.get("status")
    )
    status_value_invalid = (
        status_value_invalid or status.get("source_status_value_invalid") is True
    )
    phase_value = compact_policy_detail(status.get("phase"), max_length=120)
    loop_running = bool(status.get("loop_running"))
    coordination = coordination_summary(status)
    business_hours = business_hours_summary(status.get("business_hours"))
    business_hours_pause = (
        status_value == "paused"
        and phase_value == "outside_business_hours"
        and business_hours.get("active_pause") is True
    )
    artifact_health_status = artifact_health.get("status") or "unknown"
    artifact_statuses = artifact_status_summary(artifact_health.get("statuses"))
    artifact_problem_artifacts = artifact_problem_summary(
        artifact_health.get("degraded_artifacts"),
        artifact_statuses,
    )
    artifact_counts = artifact_health_counts(artifact_health, artifact_statuses)
    artifact_health_text = compact_policy_detail(
        artifact_health.get("summary"),
        max_length=240,
    )
    import_readiness = (
        compact_policy_detail(readiness.get("status"), max_length=80) or "unknown"
    )
    raw_readiness_blockers = as_string_list(readiness.get("blockers"))
    readiness_blockers = compact_policy_detail_list(
        raw_readiness_blockers,
        max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
        max_length=160,
    )
    readiness_blocker_count = first_compact_int(
        autonomy_policy.get("readiness_blocker_count"),
        len(raw_readiness_blockers),
    )
    if readiness_blocker_count is None:
        readiness_blocker_count = len(raw_readiness_blockers)
    policy_step = latest_autonomy_policy_step(status)
    policy_failure = (
        policy_step
        if policy_step is not None and policy_step.get("exit_status") != 0
        else None
    )
    policy_diagnostics = (
        as_dict(policy_step.get("policy_diagnostics")) if policy_step else {}
    )
    policy_failure_reason = (
        compact_policy_detail(
            policy_diagnostics.get("failure_reason")
            or policy_failure.get("failure_reason")
        )
        if policy_failure
        else None
    )
    policy_diagnostics_status = (
        compact_policy_detail(policy_diagnostics.get("status"), max_length=80)
        if policy_step
        else None
    )
    policy_route_hint = (
        compact_policy_detail(policy_diagnostics.get("route_hint"), max_length=120)
        if policy_step
        else None
    )
    policy_diagnostics_decision_reason = (
        compact_policy_detail(policy_diagnostics.get("decision_reason"))
        if policy_step
        else None
    )
    policy_diagnostics_current_focus = (
        compact_policy_detail(policy_diagnostics.get("current_focus"))
        if policy_step
        else None
    )
    policy_summary = (
        compact_policy_detail(policy_step.get("policy_summary"), max_length=480)
        if policy_step
        else None
    )
    policy_raw_csv_paths = (
        compact_path_detail_list(
            first_string_list(
                policy_step.get("raw_dallas_csv_changed_paths"),
                policy_diagnostics.get("raw_dallas_csv_changed_path_samples"),
            )
        )
        if policy_step
        else []
    )
    policy_raw_csv_path_count = (
        first_compact_int(
            policy_diagnostics.get("raw_dallas_csv_changed_path_count"),
            len(as_string_list(policy_step.get("raw_dallas_csv_changed_paths"))),
        )
        if policy_step
        else 0
    )
    policy_productive_paths = (
        compact_path_detail_list(
            first_string_list(
                policy_step.get("productive_changed_paths"),
                policy_diagnostics.get("productive_changed_path_samples"),
            )
        )
        if policy_step
        else []
    )
    policy_productive_path_count = (
        first_compact_int(
            policy_diagnostics.get("productive_changed_path_count"),
            len(as_string_list(policy_step.get("productive_changed_paths"))),
        )
        if policy_step
        else 0
    )
    policy_ignored_companion_paths = (
        compact_path_detail_list(
            first_string_list(
                policy_step.get("non_productive_companion_paths"),
                policy_diagnostics.get("non_productive_companion_path_samples"),
            )
        )
        if policy_step
        else []
    )
    policy_ignored_companion_path_count = (
        first_compact_int(
            policy_diagnostics.get("non_productive_companion_path_count"),
            len(as_string_list(policy_step.get("non_productive_companion_paths"))),
        )
        if policy_step
        else 0
    )
    policy_synthetic_row_samples = (
        compact_policy_detail_list(
            first_string_list(
                policy_step.get("synthetic_row_samples"),
                policy_diagnostics.get("synthetic_row_samples"),
            ),
            max_items=POLICY_ROW_SAMPLE_LIMIT,
            max_length=240,
        )
        if policy_step
        else []
    )
    policy_synthetic_row_count = (
        first_compact_int(
            policy_diagnostics.get("synthetic_row_count"),
            policy_step.get("synthetic_row_count"),
        )
        if policy_step
        else None
    )
    if policy_synthetic_row_count is None:
        policy_synthetic_row_count = len(policy_synthetic_row_samples)
    policy_preview_changed = (
        first_bool(
            policy_diagnostics.get("preview_json_changed"),
            policy_step.get("preview_json_changed"),
        )
        if policy_step
        else None
    )
    policy_allows_synthetic_append = (
        first_bool(
            policy_diagnostics.get("policy_allows_synthetic_append"),
            policy_step.get("policy_allows_synthetic_append"),
        )
        if policy_step
        else None
    )
    policy_override = (
        first_bool(
            policy_diagnostics.get("policy_override"),
            policy_step.get("policy_override"),
        )
        if policy_step
        else None
    )
    raw_thin_group_categories = as_string_list(
        autonomy_policy.get("thin_group_categories")
    )
    thin_group_categories = compact_policy_detail_list(
        raw_thin_group_categories,
        max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
        max_length=120,
    )
    thin_group_count = autonomy_policy.get("thin_group_count")
    if not isinstance(thin_group_count, int):
        thin_group_count = len(raw_thin_group_categories)
    thin_group_category_count = first_compact_int(
        autonomy_policy.get("thin_group_category_count"),
        len(raw_thin_group_categories),
    )
    if thin_group_category_count is None:
        thin_group_category_count = len(raw_thin_group_categories)
    coverage_latest_thin_counts = compact_count_map(
        pipeline_coverage.get("latest_thin_counts")
    )

    attention_reasons: list[str] = []
    source_status_unavailable = status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }
    if not loop_running and not business_hours_pause:
        attention_reasons.append("loop_not_running")
    if source_status_unavailable:
        attention_reasons.append("status_unavailable")
    if policy_failure:
        attention_reasons.append("autonomy_policy_failed")
    if status_value in {
        "error",
        "failing",
        "invalid-status-json",
        "invalid-status-value",
    }:
        attention_reasons.append("status_failing")
    source_status_timestamp_invalid = status.get("source_status_timestamp_invalid") is True
    source_status_timestamp_future = status.get("source_status_timestamp_future") is True
    if (
        status.get("source_status_stale") is True
        and not source_status_timestamp_invalid
        and not source_status_timestamp_future
        and not source_status_unavailable
    ):
        attention_reasons.append("status_stale")
    if source_status_timestamp_invalid:
        attention_reasons.append("status_timestamp_invalid")
    if source_status_timestamp_future:
        attention_reasons.append("status_timestamp_future")
    if artifact_health_status != "loaded" and not business_hours_pause:
        attention_reasons.append("artifact_health_not_loaded")
    if import_readiness != "ready" and not business_hours_pause:
        attention_reasons.append("import_readiness_not_ready")
    if readiness_blockers:
        attention_reasons.append("import_readiness_blocked")
    if thin_group_count > 0:
        attention_reasons.append("coverage_thin_groups_present")
    if (
        coordination.get("available") is True
        and coordination.get("handoff_file_status")
        in {"missing", "read_failed", "invalid_encoding", "too_large"}
    ):
        attention_reasons.append("handoff_coordination_unavailable")
    elif coordination.get("available") is True and (
        coordination.get("latest_section_found") is False
        or coordination.get("latest_status_found") is False
    ):
        attention_reasons.append("handoff_coordination_incomplete")
    primary_attention_reason = attention_reasons[0] if attention_reasons else None

    return {
        "status": status_value,
        "phase": phase_value,
        "mode": compact_policy_detail(status.get("mode"), max_length=120)
        or "unknown",
        "loop_running": loop_running,
        "loop_pid": status.get("loop_pid"),
        "iteration": status.get("iteration") or 0,
        "updated_at": compact_policy_detail(status.get("updated_at"), max_length=120),
        "status_age_seconds": status.get("source_status_age_seconds"),
        "status_stale_after_seconds": status.get("source_status_stale_after_seconds"),
        "status_stale": status.get("source_status_stale"),
        "status_timestamp_invalid": source_status_timestamp_invalid,
        "status_timestamp_future": source_status_timestamp_future,
        "status_value_invalid": status_value_invalid,
        "operator_attention": bool(attention_reasons),
        "operator_attention_reasons": attention_reasons,
        "operator_attention_primary_reason": primary_attention_reason,
        "operator_attention_label": operator_attention_label(primary_attention_reason),
        "business_hours": business_hours,
        "business_hours_pause": business_hours_pause,
        "artifact_health": artifact_health_status,
        "artifact_health_summary": artifact_health_text,
        "artifact_count": artifact_counts["artifact_count"],
        "loaded_artifact_count": artifact_counts["loaded_artifact_count"],
        "artifact_statuses": artifact_statuses,
        "artifact_problem_artifacts": artifact_problem_artifacts,
        "import_readiness": import_readiness,
        "readiness_blockers": readiness_blockers,
        "readiness_blocker_count": readiness_blocker_count,
        "ready_for_next_import_records": readiness.get("ready_for_next_import_records"),
        "import_handoff": import_handoff_summary(import_pipeline),
        "coordination": coordination,
        "failure_summary": failure_summary(status),
        "current_focus": compact_policy_detail(
            autonomy_policy.get("current_focus"),
            max_length=120,
        )
        or "mvp_loop",
        "policy_reason": compact_policy_detail(
            autonomy_policy.get("decision_reason"),
            max_length=160,
        ),
        "policy_failure_reason": policy_failure_reason,
        "policy_diagnostics_status": policy_diagnostics_status,
        "policy_summary": policy_summary,
        "policy_route_hint": policy_route_hint,
        "policy_diagnostics_decision_reason": policy_diagnostics_decision_reason,
        "policy_diagnostics_current_focus": policy_diagnostics_current_focus,
        "policy_preview_json_changed": policy_preview_changed,
        "policy_raw_dallas_csv_changed_paths": policy_raw_csv_paths,
        "policy_raw_dallas_csv_changed_path_count": policy_raw_csv_path_count,
        "policy_productive_changed_paths": policy_productive_paths,
        "policy_productive_changed_path_count": policy_productive_path_count,
        "policy_non_productive_companion_paths": policy_ignored_companion_paths,
        "policy_non_productive_companion_path_count": (
            policy_ignored_companion_path_count
        ),
        "policy_synthetic_row_samples": policy_synthetic_row_samples,
        "policy_synthetic_row_count": policy_synthetic_row_count,
        "policy_allows_synthetic_append": policy_allows_synthetic_append,
        "policy_override": policy_override,
        "dallas_pipeline_ready": autonomy_policy.get("dallas_pipeline_ready"),
        "thin_group_count": thin_group_count,
        "thin_group_category_count": thin_group_category_count,
        "thin_group_categories": thin_group_categories,
        "coverage_latest_thin_counts": coverage_latest_thin_counts,
        "contract_checks": contract_checks,
        "queue_items": workflow.get("queue_items"),
    }


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


def read_status(
    status_file: Path = STATUS_FILE,
    pid_file: Path = PID_FILE,
    status_stale_after_seconds: int = DEFAULT_STATUS_STALE_AFTER_SECONDS,
    bridge_status_file: Path = BRIDGE_STATUS_FILE,
    bridge_status_stale_after_seconds: int = DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
) -> dict[str, Any]:
    loaded_status, source_file_metadata = read_json_with_status(status_file)
    if loaded_status is not None:
        status = loaded_status
    else:
        status_file_status = source_file_metadata.get("source_status_file_status")
        status = {
            "status": (
                "waiting"
                if status_file_status == "missing"
                else "invalid-status-json"
            ),
            "updated_at": None,
        }
    status = dict(status)
    normalized_status_value, status_value_invalid = normalize_source_status_value(
        status.get("status")
    )
    status["status"] = normalized_status_value
    status["source_status_value_invalid"] = status_value_invalid
    status.update(source_file_metadata)
    status.update(status_freshness(status, status_stale_after_seconds))
    pid = local_loop_pid(pid_file)
    status["loop_running"] = pid is not None
    status["loop_pid"] = pid
    status["publisher_updated_at"] = utc_now()
    status["cockpit_summary"] = publisher_cockpit_summary(status)
    status["bridge_summary"] = read_bridge_summary(
        bridge_status_file,
        bridge_status_stale_after_seconds,
    )
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


def sanitize_log_tail_for_relay(text: str, *, max_line_length: int = 1200) -> str:
    sanitized_lines: list[str] = []
    for line in text.splitlines():
        sanitized = "".join(
            " " if ord(character) < 32 or ord(character) == 127 else character
            for character in line
        )
        sanitized = URL_TEXT_PATTERN.sub(sanitize_url_for_log, sanitized)
        sanitized = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", sanitized)
        sanitized = sanitize_sensitive_quoted_fields(sanitized)
        sanitized = SECRET_ASSIGNMENT_PATTERN.sub(
            lambda match: f"{match.group(1)}=[redacted]",
            sanitized,
        )
        sanitized_lines.append(sanitized[:max_line_length])
    return "\n".join(sanitized_lines).rstrip() + "\n"


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


def publisher_git_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("head", "branch"):
        compact_value = compact_policy_detail(snapshot.get(key), max_length=160)
        if compact_value is not None:
            summary[key] = compact_value

    dirty_path_count = compact_int(snapshot.get("dirty_path_count"))
    if dirty_path_count is None and isinstance(snapshot.get("dirty_paths"), list):
        dirty_path_count = len(snapshot["dirty_paths"])
    if dirty_path_count is not None:
        summary["dirty_path_count"] = dirty_path_count
    return summary


def next_publisher_snapshot_sequence() -> int:
    global PUBLISHER_SNAPSHOT_SEQUENCE
    PUBLISHER_SNAPSHOT_SEQUENCE += 1
    return PUBLISHER_SNAPSHOT_SEQUENCE


def source_health_label(reason: str | None) -> str:
    if reason is None:
        return "Live"
    return SOURCE_HEALTH_LABELS.get(reason, reason.replace("_", " "))


def source_health_diagnostics(status: dict[str, Any]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    cockpit_summary = as_dict(status.get("cockpit_summary"))
    failure = as_dict(cockpit_summary.get("failure_summary"))
    coordination = as_dict(cockpit_summary.get("coordination"))
    if not coordination:
        coordination = coordination_summary(status)
    source_status_unavailable = status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }
    bridge_summary = as_dict(status.get("bridge_summary"))
    bridge_status_unavailable = bridge_summary.get("status_file_status") in {
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }
    coordination_unavailable = coordination.get("handoff_file_status") in {
        "missing",
        "read_failed",
        "invalid_encoding",
        "too_large",
    }
    coordination_incomplete = coordination.get("available") is True and (
        coordination.get("latest_section_found") is False
        or coordination.get("latest_status_found") is False
    )
    source_freshness_attention = (
        status.get("source_status_stale") is True
        or status.get("source_status_timestamp_invalid") is True
        or status.get("source_status_timestamp_future") is True
    )
    status_value, status_value_invalid = normalize_source_status_value(
        status.get("status")
    )
    source_status_value_invalid = (
        status.get("source_status_value_invalid") is True or status_value_invalid
    )
    bridge_freshness_attention = (
        bridge_summary.get("available") is True
        and (
            bridge_summary.get("bridge_status_stale") is True
            or bridge_summary.get("bridge_status_timestamp_invalid") is True
            or bridge_summary.get("bridge_status_timestamp_future") is True
        )
    )
    bridge_status_value, bridge_status_value_invalid = normalize_source_status_value(
        bridge_summary.get("status")
    )
    source_bridge_status_value_invalid = (
        bridge_summary.get("bridge_status_value_invalid") is True
        or bridge_status_value_invalid
    )

    if source_freshness_attention and not source_status_unavailable:
        for key in (
            "source_status_age_seconds",
            "source_status_stale_after_seconds",
        ):
            compact_value = compact_int(status.get(key))
            if compact_value is not None:
                diagnostics[key] = compact_value
        for key in (
            "source_status_stale",
            "source_status_timestamp_invalid",
            "source_status_timestamp_future",
        ):
            value = status.get(key)
            if isinstance(value, bool):
                diagnostics[key] = value

    if source_status_value_invalid:
        compact_status = compact_policy_detail(status_value, max_length=120)
        if compact_status is not None:
            diagnostics["source_status"] = compact_status
        diagnostics["source_status_value_invalid"] = True

    if source_status_unavailable:
        text_fields = {
            "source_status_file_status": status.get("source_status_file_status"),
        }
        for key, value in text_fields.items():
            compact_value = compact_policy_detail(value, max_length=120)
            if compact_value is not None:
                diagnostics[key] = compact_value

        path_value = compact_path_label(status.get("source_status_file"), max_length=240)
        if path_value is not None:
            diagnostics["source_status_file"] = compact_policy_detail(
                path_value,
                max_length=240,
            )

        error_value = compact_path_diagnostic(
            status.get("source_status_file_error"),
            max_length=240,
        )
        if error_value is not None:
            diagnostics["source_status_file_error"] = error_value

    if bridge_status_unavailable:
        compact_status = compact_policy_detail(
            bridge_summary.get("status_file_status"),
            max_length=120,
        )
        if compact_status is not None:
            diagnostics["source_bridge_status_file_status"] = compact_status

        bridge_path = compact_path_label(bridge_summary.get("status_file"), max_length=240)
        if bridge_path is not None:
            diagnostics["source_bridge_status_file"] = compact_policy_detail(
                bridge_path,
                max_length=240,
            )

        bridge_error = compact_path_diagnostic(
            bridge_summary.get("status_file_error"),
            max_length=240,
        )
        if bridge_error is not None:
            diagnostics["source_bridge_status_file_error"] = bridge_error

    if source_bridge_status_value_invalid:
        compact_status = compact_policy_detail(bridge_status_value, max_length=120)
        if compact_status is not None:
            diagnostics["source_bridge_status"] = compact_status
        diagnostics["source_bridge_status_value_invalid"] = True

    if bridge_freshness_attention and not bridge_status_unavailable:
        for key, diagnostic_key in (
            ("bridge_status_age_seconds", "source_bridge_status_age_seconds"),
            (
                "bridge_status_stale_after_seconds",
                "source_bridge_status_stale_after_seconds",
            ),
        ):
            compact_value = compact_int(bridge_summary.get(key))
            if compact_value is not None:
                diagnostics[diagnostic_key] = compact_value
        for key, diagnostic_key in (
            ("bridge_status_stale", "source_bridge_status_stale"),
            (
                "bridge_status_timestamp_invalid",
                "source_bridge_status_timestamp_invalid",
            ),
            ("bridge_status_timestamp_future", "source_bridge_status_timestamp_future"),
        ):
            value = bridge_summary.get(key)
            if isinstance(value, bool):
                diagnostics[diagnostic_key] = value

    if coordination_unavailable or coordination_incomplete:
        handoff_status = compact_policy_detail(
            coordination.get("handoff_file_status"),
            max_length=120,
        )
        if handoff_status is not None:
            diagnostics["source_handoff_file_status"] = handoff_status

        handoff_path = compact_path_label(coordination.get("handoff_path"), max_length=240)
        if handoff_path is not None:
            diagnostics["source_handoff_path"] = compact_policy_detail(
                handoff_path,
                max_length=240,
            )

        handoff_error = compact_path_diagnostic(
            coordination.get("handoff_error"),
            max_length=240,
        )
        if handoff_error is not None:
            diagnostics["source_handoff_error"] = handoff_error

        for key, diagnostic_key in (
            ("latest_section_found", "source_handoff_latest_section_found"),
            ("latest_status_found", "source_handoff_latest_status_found"),
        ):
            value = coordination.get(key)
            if isinstance(value, bool):
                diagnostics[diagnostic_key] = value
        handoff_status = compact_policy_detail(
            coordination.get("latest_handoff_status"),
            max_length=160,
        )
        if handoff_status is not None:
            diagnostics["source_handoff_status"] = handoff_status
        handoff_timestamp = compact_policy_detail(
            coordination.get("latest_handoff_timestamp"),
            max_length=120,
        )
        if handoff_timestamp is not None:
            diagnostics["source_handoff_timestamp"] = handoff_timestamp
        handoff_lane = compact_policy_detail(
            coordination.get("latest_handoff_lane"),
            max_length=80,
        )
        if handoff_lane is not None:
            diagnostics["source_handoff_lane"] = handoff_lane
        handoff_age_seconds = compact_int(coordination.get("handoff_age_seconds"))
        if handoff_age_seconds is not None:
            diagnostics["source_handoff_age_seconds"] = handoff_age_seconds

    cockpit_attention_primary_reason = compact_policy_detail(
        cockpit_summary.get("operator_attention_primary_reason"),
        max_length=120,
    )
    cockpit_attention_reasons = as_string_list(
        cockpit_summary.get("operator_attention_reasons")
    )
    if cockpit_attention_primary_reason is None and cockpit_attention_reasons:
        cockpit_attention_primary_reason = compact_policy_detail(
            cockpit_attention_reasons[0],
            max_length=120,
        )
    if (
        cockpit_summary.get("operator_attention") is True
        and failure.get("available") is not True
        and cockpit_attention_primary_reason
        in {
            "artifact_health_not_loaded",
            "import_readiness_not_ready",
            "import_readiness_blocked",
            "coverage_thin_groups_present",
        }
    ):
        if cockpit_attention_primary_reason is not None:
            diagnostics["source_cockpit_attention_primary_reason"] = (
                cockpit_attention_primary_reason
            )
        cockpit_attention_label = compact_policy_detail(
            cockpit_summary.get("operator_attention_label"),
            max_length=160,
        )
        if cockpit_attention_label is not None:
            diagnostics["source_cockpit_attention_label"] = cockpit_attention_label
        cockpit_attention_reason_count = first_compact_int(
            cockpit_summary.get("operator_attention_reasons_count"),
            len(cockpit_attention_reasons),
        )
        if cockpit_attention_reason_count is not None:
            diagnostics["source_cockpit_attention_reason_count"] = (
                cockpit_attention_reason_count
            )

        if cockpit_attention_primary_reason in {
            "import_readiness_not_ready",
            "import_readiness_blocked",
        }:
            import_readiness = compact_policy_detail(
                cockpit_summary.get("import_readiness"),
                max_length=80,
            )
            if import_readiness is not None:
                diagnostics["source_import_readiness"] = import_readiness
            readiness_blocker_count = compact_int(
                cockpit_summary.get("readiness_blocker_count")
            )
            if readiness_blocker_count is not None:
                diagnostics["source_readiness_blocker_count"] = readiness_blocker_count
            readiness_blockers = compact_policy_detail_list(
                cockpit_summary.get("readiness_blockers"),
                max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
                max_length=160,
            )
            if readiness_blockers:
                diagnostics["source_readiness_blockers"] = readiness_blockers
            ready_for_next_import_records = cockpit_summary.get(
                "ready_for_next_import_records"
            )
            if isinstance(ready_for_next_import_records, bool):
                diagnostics["source_ready_for_next_import_records"] = (
                    ready_for_next_import_records
                )
        if cockpit_attention_primary_reason == "artifact_health_not_loaded":
            artifact_health = compact_policy_detail(
                cockpit_summary.get("artifact_health"),
                max_length=80,
            )
            if artifact_health is not None:
                diagnostics["source_artifact_health"] = artifact_health
            artifact_health_summary = compact_policy_detail(
                cockpit_summary.get("artifact_health_summary"),
                max_length=240,
            )
            if artifact_health_summary is not None:
                diagnostics["source_artifact_health_summary"] = (
                    artifact_health_summary
                )
            for key, diagnostic_key in (
                ("artifact_count", "source_artifact_count"),
                ("loaded_artifact_count", "source_loaded_artifact_count"),
            ):
                compact_value = compact_int(cockpit_summary.get(key))
                if compact_value is not None:
                    diagnostics[diagnostic_key] = compact_value
            artifact_statuses: dict[str, str] = {}
            raw_artifact_statuses = as_dict(cockpit_summary.get("artifact_statuses"))
            for raw_key, raw_value in sorted(
                raw_artifact_statuses.items(),
                key=lambda item: str(item[0]),
            ):
                artifact_name = compact_policy_detail(raw_key, max_length=80)
                artifact_status = compact_policy_detail(raw_value, max_length=80)
                if artifact_name is None or artifact_status is None:
                    continue
                artifact_statuses[artifact_name] = artifact_status
                if len(artifact_statuses) >= POLICY_RAW_PATH_SAMPLE_LIMIT:
                    break
            if artifact_statuses:
                diagnostics["source_artifact_statuses"] = artifact_statuses
            artifact_problem_artifacts = compact_policy_detail_list(
                cockpit_summary.get("artifact_problem_artifacts"),
                max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
                max_length=120,
            )
            if artifact_problem_artifacts:
                diagnostics["source_artifact_problem_artifacts"] = list(
                    dict.fromkeys(artifact_problem_artifacts)
                )
        if cockpit_attention_primary_reason == "coverage_thin_groups_present":
            for key, diagnostic_key in (
                ("thin_group_count", "source_thin_group_count"),
                ("thin_group_category_count", "source_thin_group_category_count"),
            ):
                compact_value = compact_int(cockpit_summary.get(key))
                if compact_value is not None:
                    diagnostics[diagnostic_key] = compact_value
            thin_group_categories = compact_policy_detail_list(
                cockpit_summary.get("thin_group_categories"),
                max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
                max_length=120,
            )
            if thin_group_categories:
                diagnostics["source_thin_group_categories"] = thin_group_categories
            coverage_latest_thin_counts = compact_count_map(
                cockpit_summary.get("coverage_latest_thin_counts")
            )
            if coverage_latest_thin_counts:
                diagnostics["source_coverage_latest_thin_counts"] = (
                    coverage_latest_thin_counts
                )

    if "autonomy_policy_failed" in cockpit_attention_reasons:
        for key, max_length in (
            ("policy_failure_reason", 160),
            ("policy_diagnostics_status", 80),
            ("policy_route_hint", 120),
            ("policy_diagnostics_decision_reason", 160),
            ("policy_diagnostics_current_focus", 120),
        ):
            compact_value = compact_policy_detail(
                cockpit_summary.get(key),
                max_length=max_length,
            )
            if compact_value is not None:
                diagnostics[f"source_{key}"] = compact_value
        for key, diagnostic_key in (
            ("policy_raw_dallas_csv_changed_path_count", "source_policy_raw_path_count"),
            ("policy_productive_changed_path_count", "source_policy_productive_path_count"),
            (
                "policy_non_productive_companion_path_count",
                "source_policy_non_productive_path_count",
            ),
            ("policy_synthetic_row_count", "source_policy_synthetic_row_count"),
        ):
            compact_value = compact_int(cockpit_summary.get(key))
            if compact_value is not None:
                diagnostics[diagnostic_key] = compact_value
        for key, diagnostic_key in (
            ("policy_preview_json_changed", "source_policy_preview_json_changed"),
            (
                "policy_allows_synthetic_append",
                "source_policy_allows_synthetic_append",
            ),
            ("policy_override", "source_policy_override"),
        ):
            value = cockpit_summary.get(key)
            if isinstance(value, bool):
                diagnostics[diagnostic_key] = value
        for key, diagnostic_key, max_items, max_length in (
            (
                "policy_raw_dallas_csv_changed_paths",
                "source_policy_raw_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "policy_productive_changed_paths",
                "source_policy_productive_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "policy_non_productive_companion_paths",
                "source_policy_non_productive_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "policy_synthetic_row_samples",
                "source_policy_synthetic_row_samples",
                POLICY_ROW_SAMPLE_LIMIT,
                240,
            ),
        ):
            compact_value = compact_policy_detail_list(
                cockpit_summary.get(key),
                max_items=max_items,
                max_length=max_length,
            )
            if compact_value:
                diagnostics[diagnostic_key] = compact_value

    if failure.get("available") is True:
        for key, max_length in (
            ("source_failure_phase", 120),
            ("source_failure_category", 120),
            ("source_failure_route_hint", 120),
            ("source_failure_failure_reason", 160),
            ("source_failure_message", 160),
            ("source_failure_decision_reason", 160),
            ("source_failure_current_focus", 120),
            ("source_failure_termination_reason", 120),
            ("source_failure_failed_step", 120),
            ("source_failure_failed_substep", 120),
            ("source_failure_setup_stage", 120),
            ("source_failure_child_label", 120),
            ("source_failure_import_pipeline_status", 80),
            ("source_failure_readiness_status", 80),
            ("source_failure_artifact_health_status", 80),
        ):
            source_key = key.removeprefix("source_failure_")
            compact_value = compact_policy_detail(
                failure.get(source_key),
                max_length=max_length,
            )
            if compact_value is not None:
                diagnostics[key] = compact_value
        for key, source_key in (
            (
                "source_failure_import_pipeline_summary_path",
                "import_pipeline_summary_path",
            ),
            ("source_failure_source_path", "source_path"),
            ("source_failure_target_path", "target_path"),
        ):
            compact_value = compact_path_diagnostic(
                failure.get(source_key),
                max_length=160,
            )
            if compact_value is not None:
                diagnostics[key] = compact_value
        for key, source_key in (
            ("source_failure_synthetic_row_count", "synthetic_row_count"),
            (
                "source_failure_raw_path_count",
                "raw_dallas_csv_changed_path_count",
            ),
            ("source_failure_productive_path_count", "productive_changed_path_count"),
            (
                "source_failure_non_productive_path_count",
                "non_productive_companion_path_count",
            ),
            ("source_failure_readiness_blocker_count", "readiness_blocker_count"),
            ("source_failure_degraded_artifact_count", "degraded_artifact_count"),
            ("source_failure_sync_exit_status", "sync_exit_status"),
            ("source_failure_child_pid", "child_pid"),
        ):
            compact_value = compact_int(failure.get(source_key))
            if compact_value is not None:
                diagnostics[key] = compact_value
        for key, source_key, max_items, max_length in (
            (
                "source_failure_raw_path_samples",
                "raw_dallas_csv_changed_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "source_failure_productive_path_samples",
                "productive_changed_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "source_failure_non_productive_path_samples",
                "non_productive_companion_path_samples",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "source_failure_synthetic_row_samples",
                "synthetic_row_samples",
                POLICY_ROW_SAMPLE_LIMIT,
                240,
            ),
            (
                "source_failure_readiness_blockers",
                "readiness_blockers",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                160,
            ),
            (
                "source_failure_degraded_artifacts",
                "degraded_artifacts",
                POLICY_RAW_PATH_SAMPLE_LIMIT,
                120,
            ),
        ):
            compact_value = compact_policy_detail_list(
                failure.get(source_key),
                max_items=max_items,
                max_length=max_length,
            )
            if compact_value:
                diagnostics[key] = compact_value
        for key, source_key in (
            ("source_failure_codex_exit_status", "codex_exit_status"),
            ("source_failure_worker_exit_status", "worker_exit_status"),
            ("source_failure_publisher_exit_status", "publisher_exit_status"),
            ("source_failure_child_exit_status", "child_exit_status"),
            ("source_failure_failed_step_exit_status", "failed_step_exit_status"),
            ("source_failure_failed_substep_exit_status", "failed_substep_exit_status"),
        ):
            compact_value = compact_exit_status(failure.get(source_key))
            if compact_value is not None:
                diagnostics[key] = compact_value
        for key, source_key in (
            ("source_failure_timed_out", "timed_out"),
            ("source_failure_killed_after_terminate", "killed_after_terminate"),
            ("source_failure_child_status_available", "child_status_available"),
        ):
            value = failure.get(source_key)
            if isinstance(value, bool):
                diagnostics[key] = value
        ready_for_next_import_records = failure.get("ready_for_next_import_records")
        if isinstance(ready_for_next_import_records, bool):
            diagnostics["source_failure_ready_for_next_import_records"] = (
                ready_for_next_import_records
            )
        for preflight_key, prefix, include_exit_status in (
            ("environment_preflight", "source_failure_environment_preflight", False),
            ("publisher_preflight", "source_failure_publisher_preflight", True),
        ):
            preflight = as_dict(failure.get(preflight_key))
            status_value = compact_policy_detail(preflight.get("status"), max_length=80)
            if status_value is not None:
                diagnostics[f"{prefix}_status"] = status_value
            if include_exit_status:
                exit_status = compact_exit_status(preflight.get("exit_status"))
                if exit_status is not None:
                    diagnostics[f"{prefix}_exit_status"] = exit_status
            error_count = compact_int(preflight.get("error_count"))
            if error_count is not None:
                diagnostics[f"{prefix}_error_count"] = error_count
            error_categories = compact_policy_detail_list(
                preflight.get("error_categories"),
                max_items=12,
                max_length=80,
            )
            if error_categories:
                diagnostics[f"{prefix}_error_categories"] = error_categories
            failed_keys = compact_policy_detail_list(
                preflight.get("failed_configuration_keys"),
                max_items=12,
                max_length=120,
            )
            if failed_keys:
                diagnostics[f"{prefix}_failed_keys"] = failed_keys

    omitted_field_count = compact_int(
        status.get("source_status_remote_omitted_field_count")
    )
    if omitted_field_count is not None:
        diagnostics["source_status_remote_omitted_field_count"] = omitted_field_count

    return diagnostics


def publisher_source_health(status: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    cockpit_summary = as_dict(status.get("cockpit_summary"))
    failure = as_dict(cockpit_summary.get("failure_summary"))
    bridge_summary = as_dict(status.get("bridge_summary"))
    bridge_health = as_dict(bridge_summary.get("bridge_health"))
    coordination = as_dict(cockpit_summary.get("coordination"))
    if not coordination:
        coordination = coordination_summary(status)
    business_hours_pause = business_hours_pause_active(status)
    status_value, status_value_invalid = normalize_source_status_value(
        status.get("status")
    )
    bridge_status_value, bridge_status_value_invalid = normalize_source_status_value(
        bridge_summary.get("status")
    )
    cockpit_attention_reasons = as_string_list(
        cockpit_summary.get("operator_attention_reasons")
    )
    source_status_unavailable = status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }
    if source_status_unavailable:
        reasons.append("source_status_unavailable")
    if failure.get("available") is True and failure.get("category") == "render_worker":
        reasons.append("source_render_worker_failure")
    source_timestamp_invalid = status.get("source_status_timestamp_invalid") is True
    source_timestamp_future = status.get("source_status_timestamp_future") is True
    if source_timestamp_invalid:
        reasons.append("source_status_timestamp_invalid")
    if source_timestamp_future:
        reasons.append("source_status_timestamp_future")
    if (
        status.get("source_status_stale") is True
        and not source_timestamp_invalid
        and not source_timestamp_future
        and not source_status_unavailable
    ):
        reasons.append("source_status_stale")
    if status.get("loop_running") is False and not business_hours_pause:
        reasons.append("source_loop_not_running")
    if "autonomy_policy_failed" in cockpit_attention_reasons:
        reasons.append("source_autonomy_policy_failed")
    if (
        status_value in {"error", "failing", "invalid-status-value"}
        or status.get("source_status_value_invalid") is True
        or status_value_invalid
        or status.get("status") == "invalid-status-json"
    ):
        reasons.append("source_status_failing")
    if (
        coordination.get("available") is True
        and coordination.get("handoff_file_status")
        in {"missing", "read_failed", "invalid_encoding", "too_large"}
    ):
        reasons.append("source_handoff_coordination_unavailable")
    elif coordination.get("available") is True and (
        coordination.get("latest_section_found") is False
        or coordination.get("latest_status_found") is False
    ):
        reasons.append("source_handoff_coordination_incomplete")
    bridge_timestamp_invalid = (
        bridge_summary.get("available") is True
        and bridge_summary.get("bridge_status_timestamp_invalid") is True
    )
    bridge_timestamp_future = (
        bridge_summary.get("available") is True
        and bridge_summary.get("bridge_status_timestamp_future") is True
    )
    if bridge_timestamp_invalid:
        reasons.append("source_bridge_status_timestamp_invalid")
    elif bridge_timestamp_future:
        reasons.append("source_bridge_status_timestamp_future")
    elif (
        bridge_summary.get("available") is True
        and bridge_summary.get("bridge_status_stale") is True
        and not bridge_timestamp_invalid
        and not bridge_timestamp_future
    ):
        reasons.append("source_bridge_status_stale")
    if bridge_summary.get("status_file_status") in {
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }:
        reasons.append("source_bridge_status_unavailable")
    if (
        bridge_summary.get("available") is True
        and (
            bridge_status_value in {"error", "failing", "invalid-status-value"}
            or bridge_summary.get("bridge_status_value_invalid") is True
            or bridge_status_value_invalid
        )
    ):
        reasons.append("source_bridge_status_failing")
    if (
        bridge_summary.get("available") is True
        and bridge_health.get("ok") is False
    ):
        reasons.append("source_bridge_degraded")
    if (
        cockpit_summary.get("operator_attention") is True
        and "source_autonomy_policy_failed" not in reasons
    ):
        reasons.append("source_cockpit_attention")

    primary_reason = reasons[0] if reasons else None
    health_status = "degraded" if reasons else "live"
    label = source_health_label(primary_reason)
    if primary_reason is None and business_hours_pause:
        label = "Scheduled pause"
    cockpit_attention_label = compact_text(cockpit_summary.get("operator_attention_label"))
    if primary_reason == "source_cockpit_attention" and cockpit_attention_label is not None:
        label = cockpit_attention_label
    health = {
        "status": health_status,
        "ok": health_status == "live",
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": label,
    }
    diagnostics = source_health_diagnostics(status)
    if diagnostics:
        health["diagnostics"] = diagnostics
    return health


def publisher_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "interval": float(args.interval),
        "timeout": float(args.timeout),
        "tail_lines": int(args.tail_lines),
        "max_log_bytes": int(args.max_log_bytes),
        "status_stale_after_seconds": int(args.status_stale_after_seconds),
        "bridge_status_stale_after_seconds": int(
            getattr(
                args,
                "bridge_status_stale_after_seconds",
                DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
            )
        ),
        "max_consecutive_failures": int(args.max_consecutive_failures),
        "max_consecutive_stale_statuses": int(
            args.max_consecutive_stale_statuses
        ),
        "max_consecutive_stale_bridge_statuses": int(
            getattr(
                args,
                "max_consecutive_stale_bridge_statuses",
                DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES,
            )
        ),
    }


REMOTE_STATUS_ALLOWED_KEYS = {
    "status",
    "phase",
    "mode",
    "updated_at",
    "iteration",
    "loop_running",
    "loop_pid",
    "publisher_updated_at",
    "source_status_value_invalid",
    "source_status_file",
    "source_status_file_status",
    "source_status_file_error",
    "source_status_age_seconds",
    "source_status_stale_after_seconds",
    "source_status_stale",
    "source_status_timestamp_invalid",
    "source_status_timestamp_future",
    "cockpit_summary",
    "bridge_summary",
}


def source_status_for_relay(status: dict[str, Any]) -> dict[str, Any]:
    remote_status: dict[str, Any] = {}
    text_fields = {
        "status",
        "phase",
        "mode",
        "updated_at",
        "publisher_updated_at",
        "source_status_file",
        "source_status_file_status",
        "source_status_file_error",
    }
    for key in text_fields:
        if key.endswith("_error"):
            compact_value = compact_path_diagnostic(status.get(key))
        else:
            compact_value = compact_policy_detail(status.get(key))
        if compact_value is not None:
            remote_status[key] = compact_value

    int_fields = {
        "iteration",
        "loop_pid",
        "source_status_age_seconds",
        "source_status_stale_after_seconds",
    }
    for key in int_fields:
        value = status.get(key)
        if value is None and key in status:
            remote_status[key] = None
            continue
        compact_value = compact_int(value)
        if compact_value is not None:
            remote_status[key] = compact_value

    bool_fields = {
        "loop_running",
        "source_status_value_invalid",
        "source_status_stale",
        "source_status_timestamp_invalid",
        "source_status_timestamp_future",
    }
    for key in bool_fields:
        value = status.get(key)
        if isinstance(value, bool):
            remote_status[key] = value

    cockpit_summary = status.get("cockpit_summary")
    if isinstance(cockpit_summary, dict):
        remote_status["cockpit_summary"] = cockpit_summary

    bridge_summary = status.get("bridge_summary")
    if isinstance(bridge_summary, dict):
        remote_status["bridge_summary"] = bridge_summary

    omitted_count = sum(1 for key in status if key not in REMOTE_STATUS_ALLOWED_KEYS)
    if omitted_count:
        remote_status["source_status_remote_omitted_field_count"] = omitted_count
    return remote_status


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    status = read_status(
        args.status_file,
        args.pid_file,
        args.status_stale_after_seconds,
        getattr(args, "bridge_status_file", BRIDGE_STATUS_FILE),
        getattr(
            args,
            "bridge_status_stale_after_seconds",
            DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
        ),
    )
    remote_status = source_status_for_relay(status)
    source_health = publisher_source_health(remote_status)
    source_health["reason_count"] = len(source_health.get("reasons", []))
    return {
        "pushed_at": utc_now(),
        "status": remote_status,
        "log_tail": sanitize_log_tail_for_relay(
            tail_text(args.log_file, args.tail_lines, args.max_log_bytes)
        ),
        "publisher": {
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "publisher_started_at": PUBLISHER_STARTED_AT,
            "snapshot_sequence": next_publisher_snapshot_sequence(),
            "repo": repo_relative(ROOT),
            "status_file": repo_relative(args.status_file),
            "pid_file": repo_relative(args.pid_file),
            "log_file": repo_relative(args.log_file),
            "bridge_status_file": repo_relative(
                getattr(args, "bridge_status_file", BRIDGE_STATUS_FILE)
            ),
            "source_health": source_health,
            "runtime_config": publisher_runtime_config(args),
            "git": publisher_git_summary(git_snapshot()),
        },
    }


def post_payload(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    relay_url = args.relay_url.rstrip("/")
    data = json.dumps(payload, allow_nan=False).encode("utf-8")
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
        body_bytes = response.read(MAX_RELAY_RESPONSE_BYTES + 1)
    if len(body_bytes) > MAX_RELAY_RESPONSE_BYTES:
        return {
            "ok": False,
            "error": "relay_response_body_too_large",
            "body_bytes": len(body_bytes),
        }
    body = body_bytes.decode("utf-8", errors="replace")
    parsed = json.loads(body, parse_constant=reject_json_constant)
    return parsed if isinstance(parsed, dict) else {"ok": False, "body": body}


def source_status_log_fields(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status")
    if not isinstance(status, dict):
        status = {}
    cockpit_summary = status.get("cockpit_summary")
    if not isinstance(cockpit_summary, dict):
        cockpit_summary = {}
    cockpit_attention_reasons = cockpit_summary.get("operator_attention_reasons")
    cockpit_attention_reason_count = compact_int(
        cockpit_summary.get("operator_attention_reasons_count")
    )
    if cockpit_attention_reason_count is None and isinstance(
        cockpit_attention_reasons,
        list,
    ):
        cockpit_attention_reason_count = len(cockpit_attention_reasons)
    cockpit_attention_primary_reason = compact_policy_detail(
        cockpit_summary.get("operator_attention_primary_reason"),
        max_length=120,
    )
    if cockpit_attention_primary_reason is None and isinstance(
        cockpit_attention_reasons,
        list,
    ):
        for reason in cockpit_attention_reasons:
            cockpit_attention_primary_reason = compact_policy_detail(
                reason,
                max_length=120,
            )
            if cockpit_attention_primary_reason is not None:
                break
    business_hours = cockpit_summary.get("business_hours")
    if not isinstance(business_hours, dict):
        business_hours = {}
    bridge_summary = status.get("bridge_summary")
    if not isinstance(bridge_summary, dict):
        bridge_summary = {}
    bridge_health = bridge_summary.get("bridge_health")
    if not isinstance(bridge_health, dict):
        bridge_health = {}
    coordination = cockpit_summary.get("coordination")
    if not isinstance(coordination, dict):
        coordination = status.get("coordination")
    if not isinstance(coordination, dict):
        coordination = {}
    failure = cockpit_summary.get("failure_summary")
    if not isinstance(failure, dict):
        failure = {}
    publisher_preflight = failure.get("publisher_preflight")
    if not isinstance(publisher_preflight, dict):
        publisher_preflight = {}
    environment_preflight = failure.get("environment_preflight")
    if not isinstance(environment_preflight, dict):
        environment_preflight = {}
    publisher = payload.get("publisher")
    if not isinstance(publisher, dict):
        publisher = {}
    source_health = publisher.get("source_health")
    if not isinstance(source_health, dict):
        source_health = {}
    source_health_reasons = source_health.get("reasons")
    source_health_reason_count = compact_int(source_health.get("reason_count"))
    if source_health_reason_count is None and isinstance(source_health_reasons, list):
        source_health_reason_count = len(source_health_reasons)
    git = publisher.get("git")
    if not isinstance(git, dict):
        git = {}
    return {
        "source_status": compact_policy_detail(status.get("status"), max_length=80)
        or "unknown",
        "source_loop_running": status.get("loop_running")
        if isinstance(status.get("loop_running"), bool)
        else None,
        "source_status_stale": status.get("source_status_stale")
        if isinstance(status.get("source_status_stale"), bool)
        else None,
        "source_status_timestamp_invalid": status.get(
            "source_status_timestamp_invalid"
        )
        if isinstance(status.get("source_status_timestamp_invalid"), bool)
        else None,
        "source_status_timestamp_future": status.get("source_status_timestamp_future")
        if isinstance(status.get("source_status_timestamp_future"), bool)
        else None,
        "source_status_value_invalid": status.get("source_status_value_invalid")
        if isinstance(status.get("source_status_value_invalid"), bool)
        else None,
        "source_status_age_seconds": compact_int(status.get("source_status_age_seconds")),
        "source_status_stale_after_seconds": compact_int(
            status.get("source_status_stale_after_seconds")
        ),
        "source_status_file_status": compact_policy_detail(
            status.get("source_status_file_status"),
            max_length=80,
        ),
        "source_status_file_error": compact_path_diagnostic(
            status.get("source_status_file_error"),
            max_length=180,
        ),
        "source_status_remote_omitted_field_count": compact_int(
            status.get("source_status_remote_omitted_field_count")
        ),
        "source_business_hours_paused": cockpit_summary.get("business_hours_pause")
        if isinstance(cockpit_summary.get("business_hours_pause"), bool)
        else None,
        "source_business_hours_timezone": compact_policy_detail(
            business_hours.get("timezone"),
            max_length=120,
        ),
        "source_business_hours_next_start_at": compact_policy_detail(
            business_hours.get("next_start_at"),
            max_length=120,
        ),
        "source_health_status": compact_policy_detail(
            source_health.get("status"),
            max_length=80,
        ),
        "source_health_primary_reason": compact_policy_detail(
            source_health.get("primary_reason"),
            max_length=120,
        ),
        "source_health_reason_count": source_health_reason_count,
        "source_health_label": compact_policy_detail(source_health.get("label"), max_length=160),
        "source_cockpit_attention": cockpit_summary.get("operator_attention")
        if isinstance(cockpit_summary.get("operator_attention"), bool)
        else None,
        "source_cockpit_attention_primary_reason": cockpit_attention_primary_reason,
        "source_cockpit_attention_label": compact_policy_detail(
            cockpit_summary.get("operator_attention_label"),
            max_length=160,
        ),
        "source_cockpit_attention_reason_count": cockpit_attention_reason_count,
        "source_artifact_health": compact_policy_detail(
            cockpit_summary.get("artifact_health"),
            max_length=80,
        ),
        "source_artifact_health_summary": compact_policy_detail(
            cockpit_summary.get("artifact_health_summary"),
            max_length=160,
        ),
        "source_artifact_count": compact_int(cockpit_summary.get("artifact_count")),
        "source_loaded_artifact_count": compact_int(
            cockpit_summary.get("loaded_artifact_count")
        ),
        "source_artifact_problem_artifacts": compact_log_detail_list(
            cockpit_summary.get("artifact_problem_artifacts"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=120,
        ),
        "source_thin_group_count": compact_int(cockpit_summary.get("thin_group_count")),
        "source_thin_group_category_count": compact_int(
            cockpit_summary.get("thin_group_category_count")
        ),
        "source_thin_group_categories": compact_log_detail_list(
            cockpit_summary.get("thin_group_categories"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=120,
        ),
        "source_coverage_latest_thin_counts": compact_log_count_map(
            cockpit_summary.get("coverage_latest_thin_counts")
        ),
        "source_import_readiness": compact_policy_detail(
            cockpit_summary.get("import_readiness"),
            max_length=80,
        ),
        "source_readiness_blocker_count": compact_int(
            cockpit_summary.get("readiness_blocker_count")
        ),
        "source_readiness_blockers": compact_log_detail_list(
            cockpit_summary.get("readiness_blockers"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=160,
        ),
        "source_ready_for_next_import_records": cockpit_summary.get(
            "ready_for_next_import_records"
        )
        if isinstance(cockpit_summary.get("ready_for_next_import_records"), bool)
        else None,
        "bridge_available": bridge_summary.get("available")
        if isinstance(bridge_summary.get("available"), bool)
        else None,
        "bridge_status": compact_policy_detail(bridge_summary.get("status"), max_length=80),
        "bridge_status_file_status": compact_policy_detail(
            bridge_summary.get("status_file_status"),
            max_length=80,
        ),
        "bridge_status_file_error": compact_path_diagnostic(
            bridge_summary.get("status_file_error"),
            max_length=180,
        ),
        "bridge_status_stale": bridge_summary.get("bridge_status_stale")
        if isinstance(bridge_summary.get("bridge_status_stale"), bool)
        else None,
        "bridge_status_timestamp_invalid": bridge_summary.get(
            "bridge_status_timestamp_invalid"
        )
        if isinstance(bridge_summary.get("bridge_status_timestamp_invalid"), bool)
        else None,
        "bridge_status_timestamp_future": bridge_summary.get(
            "bridge_status_timestamp_future"
        )
        if isinstance(bridge_summary.get("bridge_status_timestamp_future"), bool)
        else None,
        "bridge_status_value_invalid": bridge_summary.get("bridge_status_value_invalid")
        if isinstance(bridge_summary.get("bridge_status_value_invalid"), bool)
        else None,
        "bridge_status_age_seconds": compact_int(
            bridge_summary.get("bridge_status_age_seconds")
        ),
        "bridge_status_stale_after_seconds": compact_int(
            bridge_summary.get("bridge_status_stale_after_seconds")
        ),
        "bridge_health_status": compact_policy_detail(
            bridge_health.get("status"),
            max_length=80,
        ),
        "bridge_health_primary_reason": compact_policy_detail(
            bridge_health.get("primary_reason"),
            max_length=120,
        ),
        "bridge_health_label": compact_policy_detail(
            bridge_health.get("label"),
            max_length=160,
        ),
        "source_policy_failure_reason": compact_policy_detail(
            cockpit_summary.get("policy_failure_reason"),
            max_length=160,
        ),
        "source_policy_diagnostics_status": compact_policy_detail(
            cockpit_summary.get("policy_diagnostics_status"),
            max_length=80,
        ),
        "source_policy_route_hint": compact_policy_detail(
            cockpit_summary.get("policy_route_hint"),
            max_length=120,
        ),
        "source_policy_diagnostics_decision_reason": compact_policy_detail(
            cockpit_summary.get("policy_diagnostics_decision_reason"),
            max_length=160,
        ),
        "source_policy_diagnostics_current_focus": compact_policy_detail(
            cockpit_summary.get("policy_diagnostics_current_focus"),
            max_length=120,
        ),
        "source_policy_preview_json_changed": cockpit_summary.get(
            "policy_preview_json_changed"
        )
        if isinstance(cockpit_summary.get("policy_preview_json_changed"), bool)
        else None,
        "source_policy_allows_synthetic_append": cockpit_summary.get(
            "policy_allows_synthetic_append"
        )
        if isinstance(cockpit_summary.get("policy_allows_synthetic_append"), bool)
        else None,
        "source_policy_override": cockpit_summary.get("policy_override")
        if isinstance(cockpit_summary.get("policy_override"), bool)
        else None,
        "source_policy_raw_path_count": compact_int(
            cockpit_summary.get("policy_raw_dallas_csv_changed_path_count")
        ),
        "source_policy_productive_path_count": compact_int(
            cockpit_summary.get("policy_productive_changed_path_count")
        ),
        "source_policy_non_productive_path_count": compact_int(
            cockpit_summary.get("policy_non_productive_companion_path_count")
        ),
        "source_policy_synthetic_row_count": compact_int(
            cockpit_summary.get("policy_synthetic_row_count")
        ),
        "source_coordination_handoff_path": compact_policy_detail(
            coordination.get("handoff_path"),
            max_length=160,
        ),
        "source_coordination_handoff_file_status": compact_policy_detail(
            coordination.get("handoff_file_status"),
            max_length=80,
        ),
        "source_coordination_handoff_status": compact_policy_detail(
            coordination.get("latest_handoff_status"),
            max_length=240,
        ),
        "source_coordination_handoff_timestamp": compact_policy_detail(
            coordination.get("latest_handoff_timestamp"),
            max_length=120,
        ),
        "source_coordination_handoff_lane": compact_policy_detail(
            coordination.get("latest_handoff_lane"),
            max_length=80,
        ),
        "source_coordination_latest_section_found": coordination.get(
            "latest_section_found"
        )
        if isinstance(coordination.get("latest_section_found"), bool)
        else None,
        "source_coordination_latest_status_found": coordination.get(
            "latest_status_found"
        )
        if isinstance(coordination.get("latest_status_found"), bool)
        else None,
        "source_coordination_handoff_age_seconds": compact_int(
            coordination.get("handoff_age_seconds")
        ),
        "source_coordination_handoff_error": compact_path_diagnostic(
            coordination.get("handoff_error"),
            max_length=180,
        ),
        "source_failure_category": compact_policy_detail(
            failure.get("category"),
            max_length=120,
        ),
        "source_failure_route_hint": compact_policy_detail(
            failure.get("route_hint"),
            max_length=120,
        ),
        "source_failure_phase": compact_policy_detail(
            failure.get("phase"),
            max_length=120,
        ),
        "source_failure_message": compact_policy_detail(
            failure.get("message"),
            max_length=160,
        ),
        "source_failure_failure_reason": compact_policy_detail(
            failure.get("failure_reason"),
            max_length=160,
        ),
        "source_failure_decision_reason": compact_policy_detail(
            failure.get("decision_reason"),
            max_length=160,
        ),
        "source_failure_current_focus": compact_policy_detail(
            failure.get("current_focus"),
            max_length=120,
        ),
        "source_failure_termination_reason": compact_policy_detail(
            failure.get("termination_reason"),
            max_length=120,
        ),
        "source_failure_failed_step": compact_policy_detail(
            failure.get("failed_step"),
            max_length=120,
        ),
        "source_failure_failed_substep": compact_policy_detail(
            failure.get("failed_substep"),
            max_length=120,
        ),
        "source_failure_setup_stage": compact_policy_detail(
            failure.get("setup_stage"),
            max_length=120,
        ),
        "source_failure_child_label": compact_policy_detail(
            failure.get("child_label"),
            max_length=120,
        ),
        "source_failure_child_pid": compact_int(failure.get("child_pid")),
        "source_failure_codex_exit_status": compact_exit_status(
            failure.get("codex_exit_status")
        ),
        "source_failure_worker_exit_status": compact_exit_status(
            failure.get("worker_exit_status")
        ),
        "source_failure_publisher_exit_status": compact_exit_status(
            failure.get("publisher_exit_status")
        ),
        "source_failure_child_exit_status": compact_exit_status(
            failure.get("child_exit_status")
        ),
        "source_failure_child_status_available": failure.get("child_status_available")
        if isinstance(failure.get("child_status_available"), bool)
        else None,
        "source_failure_environment_preflight_status": compact_policy_detail(
            environment_preflight.get("status"),
            max_length=80,
        ),
        "source_failure_environment_preflight_error_count": compact_int(
            environment_preflight.get("error_count")
        ),
        "source_failure_environment_preflight_error_categories": compact_log_detail_list(
            environment_preflight.get("error_categories"),
            max_items=5,
            max_length=80,
        ),
        "source_failure_environment_preflight_failed_keys": compact_log_detail_list(
            environment_preflight.get("failed_configuration_keys"),
            max_items=5,
            max_length=120,
        ),
        "source_failure_publisher_preflight_status": compact_policy_detail(
            publisher_preflight.get("status"),
            max_length=80,
        ),
        "source_failure_publisher_preflight_exit_status": compact_exit_status(
            publisher_preflight.get("exit_status")
        ),
        "source_failure_publisher_preflight_error_count": compact_int(
            publisher_preflight.get("error_count")
        ),
        "source_failure_publisher_preflight_error_categories": compact_log_detail_list(
            publisher_preflight.get("error_categories"),
            max_items=5,
            max_length=80,
        ),
        "source_failure_publisher_preflight_failed_keys": compact_log_detail_list(
            publisher_preflight.get("failed_configuration_keys"),
            max_items=5,
            max_length=120,
        ),
        "source_failure_timed_out": failure.get("timed_out")
        if isinstance(failure.get("timed_out"), bool)
        else None,
        "source_failure_killed_after_terminate": failure.get("killed_after_terminate")
        if isinstance(failure.get("killed_after_terminate"), bool)
        else None,
        "source_failure_failed_step_exit_status": compact_exit_status(
            failure.get("failed_step_exit_status")
        ),
        "source_failure_failed_substep_exit_status": compact_exit_status(
            failure.get("failed_substep_exit_status")
        ),
        "source_failure_synthetic_row_count": compact_int(
            failure.get("synthetic_row_count")
        ),
        "source_failure_raw_path_count": compact_int(
            failure.get("raw_dallas_csv_changed_path_count")
        ),
        "source_failure_productive_path_count": compact_int(
            failure.get("productive_changed_path_count")
        ),
        "source_failure_non_productive_path_count": compact_int(
            failure.get("non_productive_companion_path_count")
        ),
        "source_failure_synthetic_row_samples": compact_log_detail_list(
            failure.get("synthetic_row_samples"),
            max_items=POLICY_ROW_SAMPLE_LIMIT,
            max_length=240,
        ),
        "source_failure_raw_path_samples": compact_log_detail_list(
            failure.get("raw_dallas_csv_changed_path_samples"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=160,
        ),
        "source_failure_productive_path_samples": compact_log_detail_list(
            failure.get("productive_changed_path_samples"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=160,
        ),
        "source_failure_non_productive_path_samples": compact_log_detail_list(
            failure.get("non_productive_companion_path_samples"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=160,
        ),
        "source_failure_import_pipeline_status": compact_policy_detail(
            failure.get("import_pipeline_status"),
            max_length=80,
        ),
        "source_failure_readiness_status": compact_policy_detail(
            failure.get("readiness_status"),
            max_length=80,
        ),
        "source_failure_readiness_blocker_count": compact_int(
            failure.get("readiness_blocker_count")
        ),
        "source_failure_readiness_blockers": compact_log_detail_list(
            failure.get("readiness_blockers"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=160,
        ),
        "source_failure_ready_for_next_import_records": failure.get(
            "ready_for_next_import_records"
        )
        if isinstance(failure.get("ready_for_next_import_records"), bool)
        else None,
        "source_failure_artifact_health_status": compact_policy_detail(
            failure.get("artifact_health_status"),
            max_length=80,
        ),
        "source_failure_degraded_artifact_count": compact_int(
            failure.get("degraded_artifact_count")
        ),
        "source_failure_degraded_artifacts": compact_log_detail_list(
            failure.get("degraded_artifacts"),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
            max_length=120,
        ),
        "source_failure_import_pipeline_summary_path": compact_path_diagnostic(
            failure.get("import_pipeline_summary_path"),
            max_length=160,
        ),
        "source_failure_source_path": compact_path_diagnostic(
            failure.get("source_path"),
            max_length=160,
        ),
        "source_failure_target_path": compact_path_diagnostic(
            failure.get("target_path"),
            max_length=160,
        ),
        "source_failure_sync_exit_status": compact_int(
            failure.get("sync_exit_status")
        ),
        "publisher_host": compact_policy_detail(publisher.get("host"), max_length=120),
        "publisher_pid": compact_int(publisher.get("pid")),
        "publisher_started_at": compact_policy_detail(
            publisher.get("publisher_started_at"),
            max_length=80,
        ),
        "publisher_snapshot_sequence": compact_int(publisher.get("snapshot_sequence")),
        "publisher_git_head": compact_policy_detail(git.get("head"), max_length=80),
        "publisher_git_dirty_path_count": compact_int(git.get("dirty_path_count")),
    }


SOURCE_STATUS_LOG_FIELD_NAMES = (
    "source_status",
    "source_loop_running",
    "source_status_stale",
    "source_status_timestamp_invalid",
    "source_status_timestamp_future",
    "source_status_value_invalid",
    "source_status_age_seconds",
    "source_status_stale_after_seconds",
    "source_status_file_status",
    "source_status_file_error",
    "source_status_remote_omitted_field_count",
    "source_business_hours_paused",
    "source_business_hours_timezone",
    "source_business_hours_next_start_at",
    "source_health_status",
    "source_health_primary_reason",
    "source_health_reason_count",
    "source_health_label",
    "source_cockpit_attention",
    "source_cockpit_attention_primary_reason",
    "source_cockpit_attention_label",
    "source_cockpit_attention_reason_count",
    "source_artifact_health",
    "source_artifact_health_summary",
    "source_artifact_count",
    "source_loaded_artifact_count",
    "source_artifact_problem_artifacts",
    "source_thin_group_count",
    "source_thin_group_category_count",
    "source_thin_group_categories",
    "source_coverage_latest_thin_counts",
    "source_import_readiness",
    "source_readiness_blocker_count",
    "source_readiness_blockers",
    "source_ready_for_next_import_records",
    "bridge_available",
    "bridge_status",
    "bridge_status_file_status",
    "bridge_status_file_error",
    "bridge_status_stale",
    "bridge_status_timestamp_invalid",
    "bridge_status_timestamp_future",
    "bridge_status_value_invalid",
    "bridge_status_age_seconds",
    "bridge_status_stale_after_seconds",
    "bridge_health_status",
    "bridge_health_primary_reason",
    "bridge_health_label",
    "source_policy_failure_reason",
    "source_policy_diagnostics_status",
    "source_policy_route_hint",
    "source_policy_diagnostics_decision_reason",
    "source_policy_diagnostics_current_focus",
    "source_policy_preview_json_changed",
    "source_policy_allows_synthetic_append",
    "source_policy_override",
    "source_policy_raw_path_count",
    "source_policy_productive_path_count",
    "source_policy_non_productive_path_count",
    "source_policy_synthetic_row_count",
    "source_coordination_handoff_path",
    "source_coordination_handoff_file_status",
    "source_coordination_handoff_status",
    "source_coordination_handoff_timestamp",
    "source_coordination_handoff_lane",
    "source_coordination_latest_section_found",
    "source_coordination_latest_status_found",
    "source_coordination_handoff_age_seconds",
    "source_coordination_handoff_error",
    "source_failure_category",
    "source_failure_route_hint",
    "source_failure_phase",
    "source_failure_message",
    "source_failure_failure_reason",
    "source_failure_decision_reason",
    "source_failure_current_focus",
    "source_failure_termination_reason",
    "source_failure_failed_step",
    "source_failure_failed_substep",
    "source_failure_setup_stage",
    "source_failure_child_label",
    "source_failure_child_pid",
    "source_failure_codex_exit_status",
    "source_failure_worker_exit_status",
    "source_failure_publisher_exit_status",
    "source_failure_child_exit_status",
    "source_failure_child_status_available",
    "source_failure_environment_preflight_status",
    "source_failure_environment_preflight_error_count",
    "source_failure_environment_preflight_error_categories",
    "source_failure_environment_preflight_failed_keys",
    "source_failure_publisher_preflight_status",
    "source_failure_publisher_preflight_exit_status",
    "source_failure_publisher_preflight_error_count",
    "source_failure_publisher_preflight_error_categories",
    "source_failure_publisher_preflight_failed_keys",
    "source_failure_timed_out",
    "source_failure_killed_after_terminate",
    "source_failure_failed_step_exit_status",
    "source_failure_failed_substep_exit_status",
    "source_failure_synthetic_row_count",
    "source_failure_raw_path_count",
    "source_failure_productive_path_count",
    "source_failure_non_productive_path_count",
    "source_failure_synthetic_row_samples",
    "source_failure_raw_path_samples",
    "source_failure_productive_path_samples",
    "source_failure_non_productive_path_samples",
    "source_failure_import_pipeline_status",
    "source_failure_readiness_status",
    "source_failure_readiness_blocker_count",
    "source_failure_readiness_blockers",
    "source_failure_ready_for_next_import_records",
    "source_failure_artifact_health_status",
    "source_failure_degraded_artifact_count",
    "source_failure_degraded_artifacts",
    "source_failure_import_pipeline_summary_path",
    "source_failure_source_path",
    "source_failure_target_path",
    "source_failure_sync_exit_status",
    "publisher_host",
    "publisher_pid",
    "publisher_started_at",
    "publisher_snapshot_sequence",
    "publisher_git_head",
    "publisher_git_dirty_path_count",
)


def source_status_log_suffix(source_fields: dict[str, Any]) -> str:
    field_defaults = {"source_status": "unknown"}
    return " ".join(
        f"{field_name}={source_fields.get(field_name, field_defaults.get(field_name))}"
        for field_name in SOURCE_STATUS_LOG_FIELD_NAMES
    )


def fallback_source_status_log_fields(args: argparse.Namespace) -> dict[str, Any]:
    """Build compact source fields when payload construction fails before POST."""
    try:
        status = read_status(
            getattr(args, "status_file", STATUS_FILE),
            getattr(args, "pid_file", PID_FILE),
            int(
                getattr(
                    args,
                    "status_stale_after_seconds",
                    DEFAULT_STATUS_STALE_AFTER_SECONDS,
                )
            ),
            getattr(args, "bridge_status_file", BRIDGE_STATUS_FILE),
            int(
                getattr(
                    args,
                    "bridge_status_stale_after_seconds",
                    DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
                )
            ),
        )
        remote_status = source_status_for_relay(status)
        return source_status_log_fields(
            {
                "status": remote_status,
                "publisher": {
                    "source_health": publisher_source_health(remote_status),
                },
            }
        )
    except Exception:
        return {}


def publish_exit_source_status_log_suffix(args: argparse.Namespace) -> str:
    """Return compact source context for terminal publisher loop exit lines."""
    required_fields = (
        "status_file",
        "pid_file",
        "bridge_status_file",
        "status_stale_after_seconds",
        "bridge_status_stale_after_seconds",
    )
    if any(not hasattr(args, field_name) for field_name in required_fields):
        return ""
    source_fields = fallback_source_status_log_fields(args)
    return f" {source_status_log_suffix(source_fields)}" if source_fields else ""


def relay_response_failure_reason(response: Any) -> str:
    if not isinstance(response, dict):
        return "relay_response_not_object"
    for key in ("error", "message"):
        reason = response.get(key)
        if reason is None:
            continue
        if isinstance(reason, str | int | float | bool):
            sanitized = sanitize_error_for_log(RuntimeError(str(reason)))[:200]
            return sanitized or f"relay_response_{key}_empty"
        return f"relay_response_{key}_not_scalar"
    return "relay_response_not_ok"


def relay_response_ok(response: Any) -> bool:
    return isinstance(response, dict) and response.get("ok") is True


def publish_once_loop_result(
    *,
    published: bool,
    source_fields: dict[str, Any],
    failure_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "published": published,
        "source_status_stale": source_fields.get("source_status_stale"),
        "source_status_age_seconds": source_fields.get("source_status_age_seconds"),
        "source_status_stale_after_seconds": source_fields.get(
            "source_status_stale_after_seconds"
        ),
    }
    for field_name in (
        "bridge_status_stale",
        "bridge_status_age_seconds",
        "bridge_status_stale_after_seconds",
    ):
        if source_fields.get(field_name) is not None:
            result[field_name] = source_fields.get(field_name)
    if failure_fields:
        result.update(failure_fields)
    return result


def latest_publish_failure_log_suffix(result: dict[str, Any]) -> str:
    """Return compact metadata for the latest failed publish attempt."""
    fields: list[str] = []
    failure_kind = compact_policy_detail(result.get("failure_kind"), max_length=120)
    if failure_kind is not None:
        fields.append(f"last_failure_kind={failure_kind}")
    http_status = compact_int(result.get("http_status"))
    if http_status is not None:
        fields.append(f"http_status={http_status}")
    http_reason = compact_policy_detail(result.get("http_reason"), max_length=80)
    if http_reason is not None:
        fields.append(f"http_reason={http_reason}")
    http_body_bytes = compact_int(result.get("http_body_bytes"))
    if http_body_bytes is not None:
        fields.append(f"http_body_bytes={http_body_bytes}")
    http_retry_after = compact_policy_detail(
        result.get("http_retry_after"),
        max_length=80,
    )
    if http_retry_after is not None:
        fields.append(f"retry_after={http_retry_after}")
    failure_reason = compact_policy_detail(result.get("failure_reason"), max_length=200)
    if failure_reason is not None:
        fields.append(f"last_failure_reason={failure_reason}")
    return f" {' '.join(fields)}" if fields else ""


def relay_http_error_failure_kind(status_code: int) -> str:
    if status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        return "relay_auth_failed"
    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return "relay_rate_limited"
    if status_code == HTTPStatus.SERVICE_UNAVAILABLE:
        return "relay_unavailable"
    return "http_error"


def publish_error_kind(exc: BaseException) -> str:
    if isinstance(exc, URLError):
        return "url_error"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_relay_json"
    if isinstance(exc, ValueError) and str(exc).startswith("invalid JSON constant "):
        return "invalid_relay_json"
    if isinstance(exc, ValueError):
        return "invalid_relay_response"
    if isinstance(exc, subprocess.SubprocessError):
        return "local_command_error"
    if isinstance(exc, OSError):
        return "transport_error"
    return type(exc).__name__


def format_number(value: float | int) -> str:
    parsed = float(value)
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def http_error_summary(exc: HTTPError) -> dict[str, Any]:
    try:
        body_bytes = len(exc.read())
    except OSError:
        body_bytes = None
    try:
        reason = HTTPStatus(exc.code).phrase
    except ValueError:
        reason = "HTTP error"
    summary: dict[str, Any] = {
        "http_status": exc.code,
        "http_reason": reason.replace("\r", " ").replace("\n", " ")[:80],
        "http_body_bytes": body_bytes,
    }
    headers = getattr(exc, "headers", None) or {}
    retry_after = compact_policy_detail(headers.get("Retry-After"), max_length=80)
    if retry_after is not None:
        summary["http_retry_after"] = retry_after
    return summary


def sanitize_url_for_log(match: re.Match[str]) -> str:
    return sanitize_url_value(match.group(0))


def sanitize_error_for_log(exc: BaseException) -> str:
    return sanitize_error_text_for_log(str(exc))


def sanitize_url_for_publisher_log(match: re.Match[str]) -> str:
    value = match.group(0)
    trailing = ""
    while value.endswith((",", ";")):
        trailing = value[-1] + trailing
        value = value[:-1]
    return sanitize_url_value(value) + trailing


def sanitize_publisher_log_message(message: str) -> str:
    message = "".join(
        " " if character in "\r\n" or ord(character) < 32 or ord(character) == 127
        else character
        for character in message
    )
    message = PUBLISHER_LOG_URL_TEXT_PATTERN.sub(sanitize_url_for_publisher_log, message)
    message = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", message)
    message = sanitize_sensitive_quoted_fields(message)
    return PUBLISHER_LOG_SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        message,
    )


def sanitize_error_text_for_log(message: str) -> str:
    return sanitize_publisher_log_message(message)[:300]


def sanitize_exception_for_log(exc: BaseException, args: argparse.Namespace) -> str:
    message = str(exc)
    for attr_name, default_path in (
        ("status_file", STATUS_FILE),
        ("pid_file", PID_FILE),
        ("log_file", LOG_FILE),
        ("publisher_log", PUBLISHER_LOG),
        ("bridge_status_file", BRIDGE_STATUS_FILE),
    ):
        path = getattr(args, attr_name, default_path)
        if not isinstance(path, Path):
            continue
        safe_label = repo_relative(path)
        path_strings = {str(path)}
        try:
            path_strings.add(str(path.resolve(strict=False)))
        except OSError:
            pass
        for path_string in sorted(path_strings, key=len, reverse=True):
            if path_string:
                message = message.replace(path_string, safe_label)
    return sanitize_error_text_for_log(message)


def publish_once_result(args: argparse.Namespace) -> dict[str, Any]:
    source_fields: dict[str, Any] = {}
    try:
        payload = build_payload(args)
        source_fields = source_status_log_fields(payload)
        response = post_payload(args, payload)
    except HTTPError as exc:
        if not source_fields:
            source_fields = fallback_source_status_log_fields(args)
        http_fields = http_error_summary(exc)
        failure_kind = relay_http_error_failure_kind(http_fields["http_status"])
        emit(
            "publish failed "
            f"failure_kind={failure_kind} "
            f"http_status={http_fields['http_status']} "
            f"http_reason={http_fields['http_reason']} "
            f"http_body_bytes={http_fields['http_body_bytes']} "
            f"retry_after={http_fields.get('http_retry_after', 'unknown')} "
            f"{source_status_log_suffix(source_fields)}",
            log_path=args.publisher_log,
        )
        failure_fields = {
            "failure_kind": failure_kind,
            "http_status": http_fields["http_status"],
            "http_reason": http_fields["http_reason"],
            "http_body_bytes": http_fields["http_body_bytes"],
        }
        if "http_retry_after" in http_fields:
            failure_fields["http_retry_after"] = http_fields["http_retry_after"]
        return publish_once_loop_result(
            published=False,
            source_fields=source_fields,
            failure_fields=failure_fields,
        )
    except (
        OSError,
        URLError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        if not source_fields:
            source_fields = fallback_source_status_log_fields(args)
        failure_kind = publish_error_kind(exc)
        emit(
            "publish failed "
            f"failure_kind={failure_kind} "
            f"error={sanitize_exception_for_log(exc, args)} "
            f"{source_status_log_suffix(source_fields)}",
            log_path=args.publisher_log,
        )
        return publish_once_loop_result(
            published=False,
            source_fields=source_fields,
            failure_fields={"failure_kind": failure_kind},
        )
    if not relay_response_ok(response):
        failure_reason = relay_response_failure_reason(response)
        emit(
            "publish failed relay_ok=False "
            "failure_kind=relay_response_not_ok "
            f"reason={failure_reason} "
            f"{source_status_log_suffix(source_fields)}",
            log_path=args.publisher_log,
        )
        return publish_once_loop_result(
            published=False,
            source_fields=source_fields,
            failure_fields={
                "failure_kind": "relay_response_not_ok",
                "failure_reason": failure_reason,
            },
        )
    emit(
        "published relay snapshot ok=True "
        f"received_at={compact_policy_detail(response.get('received_at'), max_length=240)} "
        f"{source_status_log_suffix(source_fields)}",
        log_path=args.publisher_log,
    )
    return publish_once_loop_result(
        published=True,
        source_fields=source_fields,
    )


def publish_once(args: argparse.Namespace) -> bool:
    return bool(publish_once_result(args)["published"])


def run_publish_loop(args: argparse.Namespace) -> int:
    consecutive_failures = 0
    consecutive_stale_statuses = 0
    consecutive_stale_bridge_statuses = 0
    while True:
        result = publish_once_result(args)
        if result["published"]:
            consecutive_failures = 0
            if result["source_status_stale"] is True:
                consecutive_stale_statuses += 1
                if (
                    args.max_consecutive_stale_statuses > 0
                    and consecutive_stale_statuses >= args.max_consecutive_stale_statuses
                ):
                    source_status_suffix = publish_exit_source_status_log_suffix(args)
                    stale_age_seconds = compact_int(
                        result.get("source_status_age_seconds")
                    )
                    stale_after_seconds = compact_int(
                        result.get("source_status_stale_after_seconds")
                    )
                    freshness_fields = ""
                    if not source_status_suffix and stale_age_seconds is not None:
                        freshness_fields += f" source_status_age_seconds={stale_age_seconds}"
                    if not source_status_suffix and stale_after_seconds is not None:
                        freshness_fields += (
                            " source_status_stale_after_seconds="
                            f"{stale_after_seconds}"
                        )
                    emit(
                        "exiting after consecutive stale source statuses "
                        "failure_kind=consecutive_stale_source_statuses "
                        f"count={consecutive_stale_statuses} "
                        f"limit={args.max_consecutive_stale_statuses}"
                        f"{source_status_suffix}"
                        f"{freshness_fields}",
                        log_path=args.publisher_log,
                    )
                    return 1
            else:
                consecutive_stale_statuses = 0
            if result.get("bridge_status_stale") is True:
                consecutive_stale_bridge_statuses += 1
                if (
                    getattr(args, "max_consecutive_stale_bridge_statuses", 0) > 0
                    and consecutive_stale_bridge_statuses
                    >= args.max_consecutive_stale_bridge_statuses
                ):
                    source_status_suffix = publish_exit_source_status_log_suffix(args)
                    stale_age_seconds = compact_int(
                        result.get("bridge_status_age_seconds")
                    )
                    stale_after_seconds = compact_int(
                        result.get("bridge_status_stale_after_seconds")
                    )
                    freshness_fields = ""
                    if not source_status_suffix and stale_age_seconds is not None:
                        freshness_fields += f" bridge_status_age_seconds={stale_age_seconds}"
                    if not source_status_suffix and stale_after_seconds is not None:
                        freshness_fields += (
                            " bridge_status_stale_after_seconds="
                            f"{stale_after_seconds}"
                        )
                    emit(
                        "exiting after consecutive stale bridge statuses "
                        "failure_kind=consecutive_stale_bridge_statuses "
                        f"count={consecutive_stale_bridge_statuses} "
                        f"limit={args.max_consecutive_stale_bridge_statuses}"
                        f"{source_status_suffix}"
                        f"{freshness_fields}",
                        log_path=args.publisher_log,
                    )
                    return 1
            else:
                consecutive_stale_bridge_statuses = 0
        else:
            consecutive_stale_statuses = 0
            consecutive_stale_bridge_statuses = 0
            terminal_failure_kind = compact_policy_detail(
                result.get("failure_kind"),
                max_length=120,
            )
            if terminal_failure_kind in {
                "relay_auth_failed",
                "relay_rate_limited",
                "relay_unavailable",
            }:
                http_status = compact_int(result.get("http_status"))
                http_reason = compact_policy_detail(
                    result.get("http_reason"),
                    max_length=80,
                )
                http_body_bytes = compact_int(result.get("http_body_bytes"))
                http_retry_after = compact_policy_detail(
                    result.get("http_retry_after"),
                    max_length=80,
                )
                http_fields = ""
                if http_status is not None:
                    http_fields += f" http_status={http_status}"
                if http_reason is not None:
                    http_fields += f" http_reason={http_reason}"
                if http_body_bytes is not None:
                    http_fields += f" http_body_bytes={http_body_bytes}"
                if http_retry_after is not None:
                    http_fields += f" retry_after={http_retry_after}"
                emit(
                    "exiting after terminal publish failure "
                    f"failure_kind={terminal_failure_kind}"
                    f"{http_fields}"
                    f"{publish_exit_source_status_log_suffix(args)}",
                    log_path=args.publisher_log,
                )
                return 1
            consecutive_failures += 1
            if (
                args.max_consecutive_failures > 0
                and consecutive_failures >= args.max_consecutive_failures
            ):
                emit(
                    "exiting after consecutive publish failures "
                    "failure_kind=consecutive_publish_failures "
                    f"count={consecutive_failures} "
                    f"limit={args.max_consecutive_failures}"
                    f"{latest_publish_failure_log_suffix(result)}"
                    f"{publish_exit_source_status_log_suffix(args)}",
                    log_path=args.publisher_log,
                )
                return 1
        time.sleep(args.interval)


def validate_publisher_configuration(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    relay_url_value = str(args.relay_url)
    relay_url = relay_url_value.strip()
    if not relay_url:
        errors.append("AUTOMOAT_RELAY_URL or --relay-url is required")
    elif relay_url_value != relay_url:
        errors.append("--relay-url must not include leading or trailing whitespace")
    elif any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in relay_url_value
    ):
        errors.append("--relay-url must be a single-line URL without control characters")
    elif any(character.isspace() for character in relay_url):
        errors.append("--relay-url must not contain whitespace")
    elif len(relay_url_value) > MAX_RELAY_URL_CHARS:
        errors.append(f"--relay-url must be {MAX_RELAY_URL_CHARS} characters or fewer")
    elif not relay_url.startswith(("http://", "https://")):
        errors.append("--relay-url must start with http:// or https://")
    else:
        try:
            parsed_relay_url = urlparse(relay_url)
        except ValueError:
            errors.append("--relay-url must be a valid URL")
            parsed_relay_url = None
        if parsed_relay_url is None:
            pass
        elif not parsed_relay_url.netloc or not parsed_relay_url.hostname:
            errors.append("--relay-url must include a host")
        elif not is_valid_url_hostname(parsed_relay_url.hostname):
            errors.append("--relay-url must include a valid host")
        elif parsed_relay_url.username or parsed_relay_url.password:
            errors.append("--relay-url must not include embedded credentials")
        elif parsed_relay_url.params:
            errors.append("--relay-url must not include path parameters")
        elif parsed_relay_url.query or parsed_relay_url.fragment:
            errors.append("--relay-url must not include query strings or fragments")
        elif parsed_relay_url.path.strip("/"):
            errors.append("--relay-url must be a relay base URL without a path")
        elif (
            parsed_relay_url.scheme == "http"
            and not local_http_host(parsed_relay_url.hostname)
        ):
            errors.append(
                "--relay-url must use https:// unless the host is localhost or 127.0.0.1"
            )
        else:
            host_port = parsed_relay_url.netloc.rsplit("@", 1)[-1]
            try:
                port = parsed_relay_url.port
            except ValueError:
                errors.append("--relay-url must include a valid port when a port is specified")
            else:
                if host_port.endswith(":") or port == 0:
                    errors.append("--relay-url must include a valid port when a port is specified")

    token_value = str(args.token)
    token = token_value.strip()
    if not token:
        errors.append("AUTOMOAT_RELAY_TOKEN or --token is required")
    elif len(token_value) > MAX_RELAY_TOKEN_CHARS:
        errors.append(f"--token must be {MAX_RELAY_TOKEN_CHARS} characters or fewer")
    elif any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in token_value
    ):
        errors.append("--token must be a single-line value without control characters")
    elif token_value != token:
        errors.append("--token must not include leading or trailing whitespace")
    if not math.isfinite(args.interval):
        errors.append("--interval must be finite")
    elif args.interval <= 0:
        errors.append("--interval must be greater than 0")
    elif args.interval > PUBLISHER_CONFIG_LIMITS["interval"]:
        errors.append(
            "--interval must be less than or equal to "
            f"{format_number(PUBLISHER_CONFIG_LIMITS['interval'])}"
        )
    if not math.isfinite(args.timeout):
        errors.append("--timeout must be finite")
    elif args.timeout <= 0:
        errors.append("--timeout must be greater than 0")
    elif args.timeout > PUBLISHER_CONFIG_LIMITS["timeout"]:
        errors.append(
            "--timeout must be less than or equal to "
            f"{format_number(PUBLISHER_CONFIG_LIMITS['timeout'])}"
        )
    if args.tail_lines <= 0:
        errors.append("--tail-lines must be greater than 0")
    elif args.tail_lines > PUBLISHER_CONFIG_LIMITS["tail_lines"]:
        errors.append(
            f"--tail-lines must be less than or equal to {PUBLISHER_CONFIG_LIMITS['tail_lines']}"
        )
    if args.max_log_bytes <= 0:
        errors.append("--max-log-bytes must be greater than 0")
    elif args.max_log_bytes > PUBLISHER_CONFIG_LIMITS["max_log_bytes"]:
        errors.append(
            "--max-log-bytes must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['max_log_bytes']}"
        )
    if args.max_consecutive_failures < 0:
        errors.append("--max-consecutive-failures must be greater than or equal to 0")
    elif (
        args.max_consecutive_failures
        > PUBLISHER_CONFIG_LIMITS["max_consecutive_failures"]
    ):
        errors.append(
            "--max-consecutive-failures must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['max_consecutive_failures']}"
        )
    if args.max_consecutive_stale_statuses < 0:
        errors.append(
            "--max-consecutive-stale-statuses must be greater than or equal to 0"
        )
    elif (
        args.max_consecutive_stale_statuses
        > PUBLISHER_CONFIG_LIMITS["max_consecutive_stale_statuses"]
    ):
        errors.append(
            "--max-consecutive-stale-statuses must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['max_consecutive_stale_statuses']}"
        )
    max_consecutive_stale_bridge_statuses = getattr(
        args,
        "max_consecutive_stale_bridge_statuses",
        DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES,
    )
    if max_consecutive_stale_bridge_statuses < 0:
        errors.append(
            "--max-consecutive-stale-bridge-statuses must be greater than or equal to 0"
        )
    elif (
        max_consecutive_stale_bridge_statuses
        > PUBLISHER_CONFIG_LIMITS["max_consecutive_stale_bridge_statuses"]
    ):
        errors.append(
            "--max-consecutive-stale-bridge-statuses must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['max_consecutive_stale_bridge_statuses']}"
        )
    if args.status_stale_after_seconds <= 0:
        errors.append("--status-stale-after-seconds must be greater than 0")
    elif (
        args.status_stale_after_seconds
        > PUBLISHER_CONFIG_LIMITS["status_stale_after_seconds"]
    ):
        errors.append(
            "--status-stale-after-seconds must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['status_stale_after_seconds']}"
        )
    bridge_status_stale_after_seconds = getattr(
        args,
        "bridge_status_stale_after_seconds",
        DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
    )
    if bridge_status_stale_after_seconds <= 0:
        errors.append("--bridge-status-stale-after-seconds must be greater than 0")
    elif (
        bridge_status_stale_after_seconds
        > PUBLISHER_CONFIG_LIMITS["bridge_status_stale_after_seconds"]
    ):
        errors.append(
            "--bridge-status-stale-after-seconds must be less than or equal to "
            f"{PUBLISHER_CONFIG_LIMITS['bridge_status_stale_after_seconds']}"
        )

    configured_file_args = {
        "--status-file": args.status_file,
        "--pid-file": args.pid_file,
        "--log-file": args.log_file,
        "--publisher-log": args.publisher_log,
        "--bridge-status-file": getattr(args, "bridge_status_file", BRIDGE_STATUS_FILE),
    }
    for label, path in configured_file_args.items():
        if path.exists() and path.is_dir():
            errors.append(f"{label} must be a file path, not a directory")
            continue
        blocking_path = blocking_parent_path_component(path)
        if blocking_path is not None:
            errors.append(
                f"{label} parent path {repo_relative(blocking_path)} must be a directory"
            )
    return errors


def local_http_host(hostname: str) -> bool:
    normalized = hostname.lower().strip("[]")
    return normalized in {"localhost", "127.0.0.1", "::1"}


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


def blocking_parent_path_component(path: Path) -> Path | None:
    current_path = path.parent
    while True:
        if current_path.exists():
            return None if current_path.is_dir() else current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent


def publisher_preflight_error_category(error: str) -> str:
    if error.endswith("is required"):
        return "missing_required"
    if error.startswith("--relay-url"):
        return "invalid_relay_url"
    if error.startswith("--token"):
        return "invalid_secret"
    if error.startswith(
        (
            "--interval",
            "--timeout",
            "--tail-lines",
            "--max-log-bytes",
            "--max-consecutive-failures",
            "--max-consecutive-stale-statuses",
            "--max-consecutive-stale-bridge-statuses",
            "--status-stale-after-seconds",
            "--bridge-status-stale-after-seconds",
        )
    ):
        return "invalid_runtime_config"
    if error.startswith(
        (
            "--status-file",
            "--pid-file",
            "--log-file",
            "--publisher-log",
            "--bridge-status-file",
        )
    ):
        return "invalid_file_path"
    return "invalid_configuration"


def publisher_preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({publisher_preflight_error_category(error) for error in errors})


def publisher_preflight_error_key(error: str) -> str:
    if error == "AUTOMOAT_RELAY_URL or --relay-url is required":
        return "AUTOMOAT_RELAY_URL|--relay-url"
    if error == "AUTOMOAT_RELAY_TOKEN or --token is required":
        return "AUTOMOAT_RELAY_TOKEN|--token"
    error_key_prefixes = {
        "--relay-url": "AUTOMOAT_RELAY_URL|--relay-url",
        "--token": "AUTOMOAT_RELAY_TOKEN|--token",
        "--interval": "AUTOMOAT_RELAY_INTERVAL|--interval",
        "--timeout": "AUTOMOAT_RELAY_TIMEOUT|--timeout",
        "--tail-lines": "AUTOMOAT_RELAY_TAIL_LINES|--tail-lines",
        "--max-log-bytes": "AUTOMOAT_RELAY_MAX_LOG_BYTES|--max-log-bytes",
        "--max-consecutive-failures": (
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES|"
            "--max-consecutive-failures"
        ),
        "--max-consecutive-stale-statuses": (
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES|"
            "--max-consecutive-stale-statuses"
        ),
        "--max-consecutive-stale-bridge-statuses": (
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES|"
            "--max-consecutive-stale-bridge-statuses"
        ),
        "--status-stale-after-seconds": (
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS|--status-stale-after-seconds"
        ),
        "--bridge-status-stale-after-seconds": (
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS|"
            "--bridge-status-stale-after-seconds"
        ),
        "--status-file": "--status-file",
        "--pid-file": "--pid-file",
        "--log-file": "--log-file",
        "--publisher-log": "--publisher-log",
        "--bridge-status-file": "AUTOMOAT_BRIDGE_STATUS_FILE|--bridge-status-file",
    }
    for prefix, key in error_key_prefixes.items():
        if error.startswith(prefix):
            return key
    return "publisher_configuration"


def publisher_preflight_error_keys(errors: list[str]) -> list[str]:
    return sorted({publisher_preflight_error_key(error) for error in errors})


def parse_float_argument(value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc


def parse_int_argument(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc


def publisher_argument_error_to_config_error(message: str) -> str:
    argument_prefixes = {
        "argument --interval:": "--interval must be a number",
        "argument --timeout:": "--timeout must be a number",
        "argument --tail-lines:": "--tail-lines must be an integer",
        "argument --max-log-bytes:": "--max-log-bytes must be an integer",
        "argument --max-consecutive-failures:": (
            "--max-consecutive-failures must be an integer"
        ),
        "argument --max-consecutive-stale-statuses:": (
            "--max-consecutive-stale-statuses must be an integer"
        ),
        "argument --max-consecutive-stale-bridge-statuses:": (
            "--max-consecutive-stale-bridge-statuses must be an integer"
        ),
        "argument --status-stale-after-seconds:": (
            "--status-stale-after-seconds must be an integer"
        ),
        "argument --bridge-status-stale-after-seconds:": (
            "--bridge-status-stale-after-seconds must be an integer"
        ),
    }
    for prefix, error in argument_prefixes.items():
        if message.startswith(prefix):
            return error
    return "publisher arguments could not be parsed"


def publisher_argument_error_summary(message: str) -> dict[str, Any]:
    errors = [publisher_argument_error_to_config_error(message)]
    failed_keys = publisher_preflight_error_keys(errors)
    runtime_keys = [
        key
        for key in failed_keys
        if key.startswith("AUTOMOAT_")
        and key
        not in {
            "AUTOMOAT_RELAY_URL|--relay-url",
            "AUTOMOAT_RELAY_TOKEN|--token",
            "AUTOMOAT_BRIDGE_STATUS_FILE|--bridge-status-file",
        }
    ]
    return {
        "status": "failed",
        "errors": errors,
        "diagnostics": {
            "error_count": len(errors),
            "error_categories": publisher_preflight_error_categories(errors),
            "failed_configuration_keys": failed_keys,
            "relay_url_configured": bool(os.environ.get("AUTOMOAT_RELAY_URL", "").strip()),
            "relay_token_configured": bool(
                os.environ.get("AUTOMOAT_RELAY_TOKEN", "").strip()
            ),
            "runtime_configured_keys": runtime_keys,
            "file_configured_keys": [],
            "runtime_limits": PUBLISHER_CONFIG_LIMITS,
        },
    }


def argv_requests_json_check_env(argv: list[str]) -> bool:
    if "--check-env" not in argv:
        return False
    for index, value in enumerate(argv):
        if value == "--format" and index + 1 < len(argv) and argv[index + 1] == "json":
            return True
        if value == "--format=json":
            return True
    return False


def paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve(strict=False) == right.expanduser().resolve(
            strict=False
        )
    except OSError:
        return left.expanduser() == right.expanduser()


def publisher_runtime_configured_keys(
    args: argparse.Namespace,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> list[str]:
    env = env if env is not None else os.environ
    configured_keys: list[str] = []
    for attr, env_name, option in PUBLISHER_RUNTIME_CONFIG_KEYS:
        value = getattr(args, attr)
        default = PUBLISHER_RUNTIME_DEFAULTS[attr]
        if env.get(env_name, "").strip() or value != default:
            configured_keys.append(f"{env_name}|{option}")
    return configured_keys


def publisher_file_configured_keys(
    args: argparse.Namespace,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> list[str]:
    env = env if env is not None else os.environ
    configured_keys: list[str] = []
    for attr, env_name, key, default_path in PUBLISHER_FILE_CONFIG_KEYS:
        value = getattr(args, attr, default_path)
        if (env_name and env.get(env_name, "").strip()) or not paths_equal(
            Path(value),
            default_path,
        ):
            configured_keys.append(key)
    return configured_keys


def publisher_preflight_summary(
    args: argparse.Namespace,
    errors: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": publisher_preflight_error_categories(errors),
            "failed_configuration_keys": publisher_preflight_error_keys(errors),
            "relay_url_configured": bool(str(args.relay_url).strip()),
            "relay_token_configured": bool(str(args.token).strip()),
            "runtime_configured_keys": publisher_runtime_configured_keys(args),
            "file_configured_keys": publisher_file_configured_keys(args),
            "runtime_limits": PUBLISHER_CONFIG_LIMITS,
        }
        return payload

    payload["config"] = {
        "relay_url": str(args.relay_url).strip().rstrip("/"),
        "relay_token_configured": bool(str(args.token).strip()),
        "interval": float(args.interval),
        "timeout": float(args.timeout),
        "tail_lines": int(args.tail_lines),
        "max_log_bytes": int(args.max_log_bytes),
        "status_stale_after_seconds": int(args.status_stale_after_seconds),
        "bridge_status_stale_after_seconds": int(
            getattr(
                args,
                "bridge_status_stale_after_seconds",
                DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS,
            )
        ),
        "max_consecutive_failures": int(args.max_consecutive_failures),
        "max_consecutive_stale_statuses": int(
            args.max_consecutive_stale_statuses
        ),
        "max_consecutive_stale_bridge_statuses": int(
            getattr(
                args,
                "max_consecutive_stale_bridge_statuses",
                DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES,
            )
        ),
        "runtime_configured_keys": publisher_runtime_configured_keys(args),
        "file_configured_keys": publisher_file_configured_keys(args),
        "status_file": repo_relative(args.status_file),
        "pid_file": repo_relative(args.pid_file),
        "log_file": repo_relative(args.log_file),
        "publisher_log": repo_relative(args.publisher_log),
        "bridge_status_file": repo_relative(
            getattr(args, "bridge_status_file", BRIDGE_STATUS_FILE)
        ),
        "runtime_limits": PUBLISHER_CONFIG_LIMITS,
    }
    return payload


def emit_publisher_preflight(
    args: argparse.Namespace,
    *,
    output_format: str = "text",
) -> list[str]:
    errors = validate_publisher_configuration(args)
    if output_format == "json":
        print(
            json.dumps(
                publisher_preflight_summary(args, errors),
                sort_keys=True,
            ),
            flush=True,
        )
        return errors

    if errors:
        print("publisher environment preflight failed")
        for error in errors:
            print(f"  - {error}")
        return errors

    print(
        "publisher environment preflight passed: "
        f"relay_url={str(args.relay_url).strip()} "
        f"interval={args.interval} "
        f"timeout={args.timeout} "
        f"tail_lines={args.tail_lines} "
        f"max_log_bytes={args.max_log_bytes} "
        f"status_stale_after_seconds={args.status_stale_after_seconds} "
        f"bridge_status_stale_after_seconds={getattr(args, 'bridge_status_stale_after_seconds', DEFAULT_BRIDGE_STATUS_STALE_AFTER_SECONDS)} "
        f"max_consecutive_failures={args.max_consecutive_failures} "
        f"max_consecutive_stale_statuses={args.max_consecutive_stale_statuses} "
        f"max_consecutive_stale_bridge_statuses={getattr(args, 'max_consecutive_stale_bridge_statuses', DEFAULT_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES)} "
        f"runtime_configured_keys={json.dumps(publisher_runtime_configured_keys(args), sort_keys=True)} "
        f"file_configured_keys={json.dumps(publisher_file_configured_keys(args), sort_keys=True)} "
        f"status_file={repo_relative(args.status_file)} "
        f"pid_file={repo_relative(args.pid_file)} "
        f"log_file={repo_relative(args.log_file)} "
        f"publisher_log={repo_relative(args.publisher_log)} "
        f"bridge_status_file={repo_relative(getattr(args, 'bridge_status_file', BRIDGE_STATUS_FILE))} "
        f"runtime_limits={json.dumps(PUBLISHER_CONFIG_LIMITS, sort_keys=True)}"
    )
    return []


def parse_args() -> argparse.Namespace:
    parser = PublisherArgumentParser(description=__doc__)
    parser.add_argument("--relay-url", default=os.environ.get("AUTOMOAT_RELAY_URL", ""))
    parser.add_argument("--token", default=os.environ.get("AUTOMOAT_RELAY_TOKEN", ""))
    parser.add_argument(
        "--interval",
        type=parse_float_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_INTERVAL",
            str(PUBLISHER_RUNTIME_DEFAULTS["interval"]),
        ),
    )
    parser.add_argument(
        "--timeout",
        type=parse_float_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_TIMEOUT",
            str(PUBLISHER_RUNTIME_DEFAULTS["timeout"]),
        ),
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate publisher configuration without posting to the relay",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for --check-env preflight results",
    )
    parser.add_argument(
        "--tail-lines",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_TAIL_LINES",
            str(PUBLISHER_RUNTIME_DEFAULTS["tail_lines"]),
        ),
    )
    parser.add_argument(
        "--max-log-bytes",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_LOG_BYTES",
            str(PUBLISHER_RUNTIME_DEFAULTS["max_log_bytes"]),
        ),
    )
    parser.add_argument("--status-file", type=Path, default=STATUS_FILE)
    parser.add_argument("--pid-file", type=Path, default=PID_FILE)
    parser.add_argument("--log-file", type=Path, default=LOG_FILE)
    parser.add_argument("--publisher-log", type=Path, default=PUBLISHER_LOG)
    parser.add_argument(
        "--bridge-status-file",
        type=Path,
        default=Path(
            os.environ.get("AUTOMOAT_BRIDGE_STATUS_FILE", str(BRIDGE_STATUS_FILE))
        ),
        help="read local bridge status from this file when building relay snapshots",
    )
    parser.add_argument(
        "--status-stale-after-seconds",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS",
            str(PUBLISHER_RUNTIME_DEFAULTS["status_stale_after_seconds"]),
        ),
        help="mark the source loop status stale when updated_at is older than this many seconds",
    )
    parser.add_argument(
        "--bridge-status-stale-after-seconds",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_BRIDGE_STATUS_STALE_AFTER_SECONDS",
            str(PUBLISHER_RUNTIME_DEFAULTS["bridge_status_stale_after_seconds"]),
        ),
        help=(
            "mark the bridge status stale when updated_at is older than this many seconds"
        ),
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
            str(PUBLISHER_RUNTIME_DEFAULTS["max_consecutive_failures"]),
        ),
        help=(
            "exit nonzero after this many consecutive publish failures; "
            "set 0 to retry forever"
        ),
    )
    parser.add_argument(
        "--max-consecutive-stale-statuses",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
            str(PUBLISHER_RUNTIME_DEFAULTS["max_consecutive_stale_statuses"]),
        ),
        help=(
            "exit nonzero after this many consecutive successful publishes whose "
            "source status is stale; set 0 to keep relaying stale status"
        ),
    )
    parser.add_argument(
        "--max-consecutive-stale-bridge-statuses",
        type=parse_int_argument,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_BRIDGE_STATUSES",
            str(PUBLISHER_RUNTIME_DEFAULTS["max_consecutive_stale_bridge_statuses"]),
        ),
        help=(
            "exit nonzero after this many consecutive successful publishes whose "
            "bridge status is stale; set 0 to keep relaying stale bridge status"
        ),
    )
    return parser.parse_args()


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    args.status_file = args.status_file.expanduser().resolve()
    args.pid_file = args.pid_file.expanduser().resolve()
    args.log_file = args.log_file.expanduser().resolve()
    args.publisher_log = args.publisher_log.expanduser().resolve()
    args.bridge_status_file = args.bridge_status_file.expanduser().resolve()
    return args


def main() -> int:
    try:
        args = normalize_args(parse_args())
    except PublisherArgumentError as exc:
        if argv_requests_json_check_env(sys.argv):
            print(
                json.dumps(
                    publisher_argument_error_summary(str(exc)),
                    sort_keys=True,
                ),
                flush=True,
            )
        else:
            print(
                publisher_argument_error_to_config_error(str(exc)),
                file=sys.stderr,
            )
        return 2
    if args.format == "json" and not args.check_env:
        print("--format json is only supported with --check-env", file=sys.stderr)
        return 2

    errors = validate_publisher_configuration(args)
    if args.check_env:
        return 0 if not emit_publisher_preflight(args, output_format=args.format) else 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    if args.once:
        return 0 if publish_once(args) else 1

    return run_publish_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
