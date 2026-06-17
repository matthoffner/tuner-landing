#!/usr/bin/env python3
"""Render-hosted read relay for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import re
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


ROOT = Path(__file__).resolve().parents[1]
STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {}
CONFIG: dict[str, Any] = {}
DEFAULT_MAX_INGEST_BYTES = 1024 * 1024
DEFAULT_MAX_LOG_CHARS = 160 * 1024
DEFAULT_MAX_STATUS_BYTES = 128 * 1024
DEFAULT_MAX_PUBLISHER_BYTES = 64 * 1024
DEFAULT_STALE_AFTER_SECONDS = 120
IMPORT_APPEND_SEQUENCE_SAMPLE_LIMIT = 4
MAX_RELAY_TOKEN_CHARS = 8192
MAX_RELAY_HOST_CHARS = 253
MAX_RUNTIME_CONFIG_VALUE_CHARS = 64
RELAY_CONFIG_LIMITS = {
    "max_ingest_bytes": 4 * 1024 * 1024,
    "max_log_chars": 1024 * 1024,
    "max_status_bytes": 512 * 1024,
    "max_publisher_bytes": 256 * 1024,
    "stale_after_seconds": 3600,
}
HTTP_REQUEST_METHODS = {
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
}
COCKPIT_HEALTH_LABELS = {
    "relay_state_load_failed": "Relay state failed to load",
    "relay_snapshot_missing": "Relay snapshot is missing",
    "relay_snapshot_stale": "Relay snapshot is stale",
    "relay_snapshot_timestamp_future": "Relay snapshot timestamp is in the future",
    "relay_snapshot_timestamp_invalid": "Relay snapshot timestamp is invalid",
    "source_bridge_degraded": "Source bridge is degraded",
    "source_bridge_status_failing": "Source bridge status is failing",
    "source_status_timestamp_invalid": "Source status timestamp is invalid",
    "source_status_stale": "Source status is stale",
    "source_status_unavailable": "Source status is unavailable",
    "source_loop_not_running": "Source loop is not running",
    "source_status_failing": "Source status is failing",
    "source_status_timestamp_future": "Source status timestamp is in the future",
    "source_autonomy_policy_failed": "Autonomy policy failed",
    "source_cockpit_attention": "Source cockpit needs attention",
    "source_handoff_coordination_unavailable": "Source coordination handoff is unavailable",
    "source_handoff_coordination_incomplete": "Source coordination handoff is incomplete",
    "source_bridge_status_unavailable": "Source bridge status is unavailable",
    "source_bridge_status_stale": "Source bridge status is stale",
    "source_bridge_status_timestamp_invalid": "Source bridge status timestamp is invalid",
    "source_bridge_status_timestamp_future": "Source bridge status timestamp is in the future",
}
EMBEDDED_URL_RE = re.compile(r"https?://[^\s,;|]+")
PATH_TOKEN_RE = re.compile(r"(?<![\w:/])(?:~|/)[^\s,;|'\"\])}]+")
SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"access_token|api_key|codex_access_token|gh_token|github_token|password|"
    r"passwd|relay_token|secret|token|key"
    r")=([^\s,;|]+)"
)
BEARER_SECRET_RE = re.compile(
    r"\b(authorization\s*[:=]\s*bearer)\s+[^\s,;|]+",
    re.IGNORECASE,
)


class RelayPersistenceError(RuntimeError):
    """Raised when a validated snapshot cannot be written to relay storage."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def sanitize_request_line_for_log(value: object) -> object:
    if not isinstance(value, str):
        return value
    parts = value.split()
    if (
        len(parts) < 3
        or parts[0] not in HTTP_REQUEST_METHODS
        or not parts[-1].startswith("HTTP/")
    ):
        return value

    parsed = urlparse(parts[1])
    if not parsed.query and not parsed.fragment:
        return value

    safe_target = parsed.path or "/"
    if parsed.params:
        safe_target = f"{safe_target};{parsed.params}"
    if parsed.query:
        safe_target = f"{safe_target}?[redacted]"
    if parsed.fragment:
        safe_target = f"{safe_target}#[redacted]"
    return " ".join([parts[0], safe_target, *parts[2:]])


def snapshot_freshness(state: dict[str, Any]) -> dict[str, Any]:
    stale_after = int(CONFIG.get("stale_after_seconds", 120))
    received_at_value = state.get("received_at")
    received_at = parse_utc_timestamp(received_at_value)
    current_time = parse_utc_timestamp(utc_now())
    timestamp_invalid = compact_text(received_at_value) is not None and received_at is None
    if received_at is None or current_time is None:
        return {
            "snapshot_age_seconds": None,
            "snapshot_stale_after_seconds": stale_after,
            "snapshot_stale": True,
            "snapshot_timestamp_invalid": timestamp_invalid,
            "snapshot_timestamp_future": False,
        }
    if received_at > current_time:
        return {
            "snapshot_age_seconds": None,
            "snapshot_stale_after_seconds": stale_after,
            "snapshot_stale": True,
            "snapshot_timestamp_invalid": False,
            "snapshot_timestamp_future": True,
        }
    age_seconds = max(0, int((current_time - received_at).total_seconds()))
    return {
        "snapshot_age_seconds": age_seconds,
        "snapshot_stale_after_seconds": stale_after,
        "snapshot_stale": age_seconds > stale_after,
        "snapshot_timestamp_invalid": False,
        "snapshot_timestamp_future": False,
    }


def cockpit_health_label(reason: str | None, source_attention_label: str | None = None) -> str:
    if reason is None:
        return "Live"
    if reason == "source_cockpit_attention" and source_attention_label:
        return source_attention_label
    return COCKPIT_HEALTH_LABELS.get(reason, reason.replace("_", " "))


def publisher_source_health(state: dict[str, Any]) -> dict[str, Any]:
    publisher = state.get("publisher")
    if not isinstance(publisher, dict):
        return {}
    source_health = publisher.get("source_health")
    if not isinstance(source_health, dict):
        return {}

    normalized_reasons = compact_health_reasons(source_health.get("reasons"))
    primary_reason = compact_policy_detail(
        source_health.get("primary_reason"),
        max_length=160,
    )
    if primary_reason is None:
        primary_reason = normalized_reasons[0] if normalized_reasons else None

    status = source_health.get("status")
    if status not in {"live", "degraded"}:
        status = "degraded" if normalized_reasons else "live"
    ok = source_health.get("ok")
    if not isinstance(ok, bool):
        ok = status == "live"
    label = compact_policy_detail(source_health.get("label"), max_length=160)
    if label is None:
        label = cockpit_health_label(primary_reason)

    summary = {
        "status": status,
        "ok": ok,
        "reasons": normalized_reasons,
        "primary_reason": primary_reason,
        "label": label,
    }
    raw_diagnostics = source_health.get("diagnostics")
    if isinstance(raw_diagnostics, dict):
        diagnostics: dict[str, Any] = {}
        status_fields = (
            ("source_status_file_status", "source_status_file", "source_status_file_error"),
            (
                "source_bridge_status_file_status",
                "source_bridge_status_file",
                "source_bridge_status_file_error",
            ),
            (
                "source_handoff_file_status",
                "source_handoff_path",
                "source_handoff_error",
            ),
        )
        for status_key, path_key, error_key in status_fields:
            status_file_status = compact_policy_detail(
                raw_diagnostics.get(status_key),
                max_length=120,
            )
            if status_file_status is not None:
                diagnostics[status_key] = status_file_status
            status_file = compact_path_label(
                raw_diagnostics.get(path_key),
                max_length=240,
            )
            if status_file is not None:
                diagnostics[path_key] = compact_policy_detail(
                    status_file,
                    max_length=240,
                )
            status_file_error = compact_path_diagnostic(
                raw_diagnostics.get(error_key),
                max_length=240,
            )
            if status_file_error is not None:
                diagnostics[error_key] = status_file_error
        for key in (
            "source_handoff_latest_section_found",
            "source_handoff_latest_status_found",
        ):
            value = raw_diagnostics.get(key)
            if isinstance(value, bool):
                diagnostics[key] = value
        if diagnostics:
            summary["diagnostics"] = diagnostics
    return summary


def compact_text(value: Any, *, max_length: int = 160) -> str | None:
    if not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = "".join(
        " " if character in "\r\n" or ord(character) < 32 or ord(character) == 127 else character
        for character in text
    )
    text = " ".join(text.split())
    return text[:max_length] if text else None


def repo_relative(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        relative_path = resolved_path.relative_to(ROOT)
    except ValueError:
        return f"<external>/{resolved_path.name}" if resolved_path.name else "<external>"
    relative_text = relative_path.as_posix()
    return relative_text if relative_text else "."


def compact_path_error(exc: BaseException, path: Path, *, max_length: int = 180) -> str:
    message = str(exc)
    safe_label = repo_relative(path)
    path_strings = {str(path)}
    try:
        path_strings.add(str(path.resolve(strict=False)))
    except OSError:
        pass
    for path_string in sorted(path_strings, key=len, reverse=True):
        if path_string:
            message = message.replace(path_string, safe_label)
    return compact_text(message, max_length=max_length) or type(exc).__name__


def compact_path_label(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_text(value, max_length=max_length)
    if text is None:
        return None
    if text.startswith(("/", "~")):
        return repo_relative(Path(text))[:max_length]
    return text


def compact_path_detail_list(
    value: Any,
    *,
    max_items: int = 5,
    max_length: int = 240,
) -> list[str]:
    if not isinstance(value, list):
        return []
    compacted: list[str] = []
    for item in value[:max_items]:
        path_label = compact_path_label(item, max_length=max_length)
        compacted_item = compact_policy_detail(path_label, max_length=max_length)
        if compacted_item is not None:
            compacted.append(compacted_item)
    return compacted


def compact_path_diagnostic(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_policy_detail(value, max_length=max_length * 2)
    if text is None:
        return None

    text = PATH_TOKEN_RE.sub(
        lambda match: repo_relative(Path(match.group(0))),
        text,
    )
    return compact_text(text, max_length=max_length)


def compact_policy_detail(value: Any, *, max_length: int = 240) -> str | None:
    text = compact_text(value, max_length=max_length * 2)
    if text is None:
        return None
    text = EMBEDDED_URL_RE.sub(lambda match: sanitize_url_value(match.group(0)), text)
    text = BEARER_SECRET_RE.sub(r"\1 [redacted]", text)
    text = SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )
    return text[:max_length] if text else None


def compact_health_reasons(value: Any, *, max_items: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    compact_reasons: list[str] = []
    for item in value:
        compact_reason = compact_policy_detail(item, max_length=160)
        if compact_reason is not None:
            compact_reasons.append(compact_reason)
        if len(compact_reasons) >= max_items:
            break
    return compact_reasons


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


def compact_url(value: Any, *, max_length: int = 160) -> str | None:
    text = compact_text(value, max_length=max_length)
    if text is None:
        return None
    return sanitize_url_value(text)


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
            nested_path = first_non_finite_json_number_path(
                item,
                f"{path}[{index}]",
            )
            if nested_path is not None:
                return nested_path
    return None


def first_non_finite_ingest_metadata_path(payload: dict[str, Any]) -> str | None:
    for key, value in payload.items():
        if key in {"status", "publisher"} and isinstance(value, dict):
            continue
        nested_path = first_non_finite_json_number_path(
            value,
            f"${json_path_component(key)}",
        )
        if nested_path is not None:
            return nested_path
    return None


def strict_json_clone(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, allow_nan=False))


def compact_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def publisher_identity(state: dict[str, Any]) -> dict[str, Any]:
    publisher = state.get("publisher")
    if not isinstance(publisher, dict) or not publisher:
        return {"available": False}

    git = publisher.get("git")
    if not isinstance(git, dict):
        git = {}

    identity: dict[str, Any] = {"available": True}
    text_fields = {
        "host": publisher.get("host"),
        "publisher_started_at": publisher.get("publisher_started_at"),
        "pushed_at": publisher.get("pushed_at"),
        "git_head": git.get("head"),
        "git_branch": git.get("branch"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=160)
        if compact_value is not None:
            identity[key] = compact_value

    int_fields = {
        "pid": publisher.get("pid"),
        "snapshot_sequence": publisher.get("snapshot_sequence"),
        "git_dirty_path_count": git.get("dirty_path_count"),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            identity[key] = compact_value

    return identity


def publisher_runtime_config(state: dict[str, Any]) -> dict[str, Any]:
    publisher = state.get("publisher")
    if not isinstance(publisher, dict):
        return {"available": False}
    runtime_config = publisher.get("runtime_config")
    if not isinstance(runtime_config, dict) or not runtime_config:
        return {"available": False}

    summary: dict[str, Any] = {"available": False}
    float_fields = {
        "interval": runtime_config.get("interval"),
        "timeout": runtime_config.get("timeout"),
    }
    for key, value in float_fields.items():
        compact_value = compact_float(value)
        if compact_value is not None:
            summary[key] = compact_value

    int_fields = {
        "tail_lines": runtime_config.get("tail_lines"),
        "max_log_bytes": runtime_config.get("max_log_bytes"),
        "status_stale_after_seconds": runtime_config.get(
            "status_stale_after_seconds"
        ),
        "bridge_status_stale_after_seconds": runtime_config.get(
            "bridge_status_stale_after_seconds"
        ),
        "max_consecutive_failures": runtime_config.get("max_consecutive_failures"),
        "max_consecutive_stale_statuses": runtime_config.get(
            "max_consecutive_stale_statuses"
        ),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    summary["available"] = any(key != "available" for key in summary)
    return summary


def publisher_for_relay_response(state: dict[str, Any]) -> dict[str, Any]:
    publisher = state.get("publisher")
    if not isinstance(publisher, dict) or not publisher:
        return {}

    identity = publisher_identity(state)
    summary: dict[str, Any] = {}
    for key in (
        "host",
        "pid",
        "publisher_started_at",
        "pushed_at",
        "snapshot_sequence",
    ):
        if key in identity:
            summary[key] = identity[key]

    path_fields = {
        "repo": publisher.get("repo"),
        "status_file": publisher.get("status_file"),
        "pid_file": publisher.get("pid_file"),
        "log_file": publisher.get("log_file"),
        "bridge_status_file": publisher.get("bridge_status_file"),
    }
    for key, value in path_fields.items():
        compact_value = compact_path_label(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    git: dict[str, Any] = {}
    if "git_head" in identity:
        git["head"] = identity["git_head"]
    if "git_branch" in identity:
        git["branch"] = identity["git_branch"]
    if "git_dirty_path_count" in identity:
        git["dirty_path_count"] = identity["git_dirty_path_count"]
    if git:
        summary["git"] = git

    runtime_config = publisher_runtime_config(state)
    compact_runtime_config = {
        key: value
        for key, value in runtime_config.items()
        if key != "available"
    }
    if compact_runtime_config:
        summary["runtime_config"] = compact_runtime_config

    source_health = publisher_source_health(state)
    if source_health:
        summary["source_health"] = source_health

    return summary


def source_status_diagnostics(status: dict[str, Any]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    text_fields = {
        "source_status": status.get("status"),
        "source_status_file_status": status.get("source_status_file_status"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=240)
        if compact_value is not None:
            diagnostics[key] = compact_value
    path_fields = {
        "source_status_file": status.get("source_status_file"),
    }
    for key, value in path_fields.items():
        compact_value = compact_path_label(value, max_length=240)
        if compact_value is not None:
            diagnostics[key] = compact_value
    path_error_fields = {
        "source_status_file_error": status.get("source_status_file_error"),
    }
    for key, value in path_error_fields.items():
        compact_value = compact_path_diagnostic(value, max_length=240)
        if compact_value is not None:
            diagnostics[key] = compact_value

    int_fields = {
        "source_status_age_seconds": status.get("source_status_age_seconds"),
        "source_status_stale_after_seconds": status.get(
            "source_status_stale_after_seconds"
        ),
        "source_status_remote_omitted_field_count": status.get(
            "source_status_remote_omitted_field_count"
        ),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            diagnostics[key] = compact_value

    stale = status.get("source_status_stale")
    if isinstance(stale, bool):
        diagnostics["source_status_stale"] = stale
    timestamp_invalid = status.get("source_status_timestamp_invalid")
    if isinstance(timestamp_invalid, bool):
        diagnostics["source_status_timestamp_invalid"] = timestamp_invalid
    timestamp_future = status.get("source_status_timestamp_future")
    if isinstance(timestamp_future, bool):
        diagnostics["source_status_timestamp_future"] = timestamp_future
    status_value_invalid = status.get("source_status_value_invalid")
    if isinstance(status_value_invalid, bool):
        diagnostics["source_status_value_invalid"] = status_value_invalid
    return diagnostics


def compact_bridge_health(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    normalized_reasons = compact_health_reasons(value.get("reasons"))
    primary_reason = compact_policy_detail(value.get("primary_reason"), max_length=160)
    if primary_reason is None:
        primary_reason = normalized_reasons[0] if normalized_reasons else None
    health_status = compact_policy_detail(value.get("status"), max_length=80) or (
        "degraded" if normalized_reasons else "unknown"
    )
    ok = value.get("ok")
    if not isinstance(ok, bool):
        ok = health_status == "live"
    label = compact_policy_detail(value.get("label"), max_length=160) or (
        "Live" if primary_reason is None else primary_reason.replace("_", " ")
    )
    return {
        "status": health_status,
        "ok": ok,
        "reasons": normalized_reasons,
        "primary_reason": primary_reason,
        "label": label,
    }


def source_bridge_summary(status: dict[str, Any]) -> dict[str, Any]:
    bridge = status.get("bridge_summary")
    if not isinstance(bridge, dict) or not bridge:
        return {"available": False}

    summary: dict[str, Any] = {"available": bridge.get("available") is True}
    text_fields = {
        "status_file_status": bridge.get("status_file_status"),
        "status": bridge.get("status"),
        "updated_at": bridge.get("updated_at"),
        "bridge_started_at": bridge.get("bridge_started_at"),
        "mode": bridge.get("mode"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    path_fields = {
        "status_file": bridge.get("status_file"),
    }
    for key, value in path_fields.items():
        compact_value = compact_path_label(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    path_error_fields = {
        "status_file_error": bridge.get("status_file_error"),
    }
    for key, value in path_error_fields.items():
        compact_value = compact_path_diagnostic(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    url_fields = {
        "public_url": bridge.get("public_url"),
        "local_read_only_url": bridge.get("local_read_only_url"),
        "ngrok_api_url": bridge.get("ngrok_api_url"),
    }
    for key, value in url_fields.items():
        compact_value = compact_url(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    int_fields = {
        "bridge_pid": bridge.get("bridge_pid"),
        "bridge_status_sequence": bridge.get("bridge_status_sequence"),
        "bridge_status_age_seconds": bridge.get("bridge_status_age_seconds"),
        "bridge_status_stale_after_seconds": bridge.get(
            "bridge_status_stale_after_seconds"
        ),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    interval = compact_float(bridge.get("interval"))
    if interval is not None:
        summary["interval"] = interval

    bridge_status_stale = bridge.get("bridge_status_stale")
    if isinstance(bridge_status_stale, bool):
        summary["bridge_status_stale"] = bridge_status_stale
    bridge_timestamp_invalid = bridge.get("bridge_status_timestamp_invalid")
    if isinstance(bridge_timestamp_invalid, bool):
        summary["bridge_status_timestamp_invalid"] = bridge_timestamp_invalid
    bridge_timestamp_future = bridge.get("bridge_status_timestamp_future")
    if isinstance(bridge_timestamp_future, bool):
        summary["bridge_status_timestamp_future"] = bridge_timestamp_future
    bridge_status_value_invalid = bridge.get("bridge_status_value_invalid")
    if isinstance(bridge_status_value_invalid, bool):
        summary["bridge_status_value_invalid"] = bridge_status_value_invalid

    bridge_health = compact_bridge_health(bridge.get("bridge_health"))
    if bridge_health is not None:
        summary["bridge_health"] = bridge_health
    return summary


def source_business_hours_summary(status: dict[str, Any]) -> dict[str, Any]:
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        source_summary = {}
    pause_flag = source_summary.get("business_hours_pause")
    if not isinstance(pause_flag, bool):
        pause_flag = None

    business_hours = status.get("business_hours")
    if not isinstance(business_hours, dict):
        business_hours = source_summary.get("business_hours")
    if not isinstance(business_hours, dict) or not business_hours:
        if pause_flag is not None:
            return {"available": True, "active_pause": pause_flag}
        return {"available": False}

    summary: dict[str, Any] = {"available": True}
    for key in ("enabled", "in_business_hours", "active_pause"):
        value = business_hours.get(key)
        if isinstance(value, bool):
            summary[key] = value
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
        summary["active_pause"] = (
            pause_flag
            if pause_flag is not None
            else summary.get("in_business_hours") is False
        )
    return summary


def source_business_hours_pause_active(
    status: dict[str, Any],
    source_business_hours: dict[str, Any] | None = None,
) -> bool:
    if source_business_hours is None:
        source_business_hours = source_business_hours_summary(status)
    return (
        status.get("status") == "paused"
        and status.get("phase") == "outside_business_hours"
        and source_business_hours.get("active_pause") is True
    )


def source_policy_summary(status: dict[str, Any]) -> dict[str, Any]:
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        return {"available": False}

    summary: dict[str, Any] = {"available": False}
    text_fields = {
        "policy_failure_reason": source_summary.get("policy_failure_reason"),
        "policy_diagnostics_status": source_summary.get("policy_diagnostics_status"),
        "policy_summary": source_summary.get("policy_summary"),
        "policy_route_hint": source_summary.get("policy_route_hint"),
        "policy_diagnostics_decision_reason": source_summary.get(
            "policy_diagnostics_decision_reason"
        ),
        "policy_diagnostics_current_focus": source_summary.get(
            "policy_diagnostics_current_focus"
        ),
        "operator_attention_primary_reason": source_summary.get(
            "operator_attention_primary_reason"
        ),
        "operator_attention_label": source_summary.get("operator_attention_label"),
    }
    for key, value in text_fields.items():
        max_length = 480 if key == "policy_summary" else 160
        compact_value = compact_policy_detail(value, max_length=max_length)
        if compact_value is not None:
            summary[key] = compact_value

    list_fields = {
        "operator_attention_reasons": source_summary.get("operator_attention_reasons"),
        "synthetic_row_samples": source_summary.get("policy_synthetic_row_samples"),
    }
    for key, value in list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = [
            compact_value
            for compact_value in (
                compact_policy_detail(item, max_length=240)
                for item in value[:5]
            )
            if compact_value is not None
        ]
        if compact_values:
            summary[key] = compact_values
            summary[f"{key}_count"] = len(value)

    path_list_fields = {
        "raw_dallas_csv_changed_paths": source_summary.get(
            "policy_raw_dallas_csv_changed_paths"
        ),
        "productive_changed_paths": source_summary.get(
            "policy_productive_changed_paths"
        ),
        "non_productive_companion_paths": source_summary.get(
            "policy_non_productive_companion_paths"
        ),
    }
    for key, value in path_list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = compact_path_detail_list(value, max_items=5, max_length=240)
        if compact_values:
            summary[key] = compact_values
            summary[f"{key}_count"] = len(value)

    int_count_fields = {
        "raw_dallas_csv_changed_paths_count": source_summary.get(
            "policy_raw_dallas_csv_changed_path_count"
        ),
        "productive_changed_paths_count": source_summary.get(
            "policy_productive_changed_path_count"
        ),
        "non_productive_companion_paths_count": source_summary.get(
            "policy_non_productive_companion_path_count"
        ),
    }
    for key, value in int_count_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    synthetic_row_count = compact_int(source_summary.get("policy_synthetic_row_count"))
    if synthetic_row_count is not None:
        summary["synthetic_row_samples_count"] = synthetic_row_count

    bool_fields = {
        "preview_json_changed": source_summary.get("policy_preview_json_changed"),
        "policy_allows_synthetic_append": source_summary.get(
            "policy_allows_synthetic_append"
        ),
        "policy_override": source_summary.get("policy_override"),
    }
    for key, value in bool_fields.items():
        if isinstance(value, bool):
            summary[key] = value

    summary["available"] = any(key != "available" for key in summary)
    return summary


def source_import_handoff_summary(source_summary: dict[str, Any]) -> dict[str, Any]:
    handoff = source_summary.get("import_handoff")
    if not isinstance(handoff, dict) or not handoff:
        return {"available": False}

    summary: dict[str, Any] = {"available": handoff.get("available") is True}
    text_fields = {
        "append_preflight_status": handoff.get("append_preflight_status"),
        "after_edit_command": handoff.get("after_edit_command"),
        "readiness_check_command": handoff.get("readiness_check_command"),
        "raw_handoff_verification_json_command": handoff.get(
            "raw_handoff_verification_json_command"
        ),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    raw_dir = compact_path_label(handoff.get("raw_dir"), max_length=240)
    if raw_dir is not None:
        raw_dir = compact_policy_detail(raw_dir, max_length=240)
    if raw_dir is not None:
        summary["raw_dir"] = raw_dir

    ready_for_append = handoff.get("ready_for_append")
    if isinstance(ready_for_append, bool):
        summary["ready_for_append"] = ready_for_append

    next_append_rows = handoff.get("next_append_rows")
    if isinstance(next_append_rows, dict):
        compact_rows: dict[str, int] = {}
        for key, value in sorted(next_append_rows.items()):
            compact_key = compact_policy_detail(key, max_length=80)
            compact_value = compact_int(value)
            if compact_key is not None and compact_value is not None:
                compact_rows[compact_key] = compact_value
        if compact_rows:
            summary["next_append_rows"] = compact_rows

    append_preflight_checks = handoff.get("append_preflight_checks")
    if isinstance(append_preflight_checks, dict):
        compact_checks: dict[str, bool] = {}
        for key, value in sorted(append_preflight_checks.items()):
            compact_key = compact_policy_detail(key, max_length=80)
            if compact_key is not None and isinstance(value, bool):
                compact_checks[compact_key] = value
        if compact_checks:
            summary["append_preflight_checks"] = compact_checks

    blockers = handoff.get("append_preflight_blockers")
    if isinstance(blockers, list):
        compact_blockers = [
            compact_value
            for compact_value in (
                compact_policy_detail(item, max_length=200)
                for item in blockers[:5]
            )
            if compact_value is not None
        ]
        summary["append_preflight_blockers"] = compact_blockers
        summary["append_preflight_blockers_count"] = len(blockers)

    append_sequence = handoff.get("append_sequence")
    if isinstance(append_sequence, list):
        compact_sequence: list[dict[str, Any]] = []
        for item in append_sequence:
            if not isinstance(item, dict):
                continue
            compact_item: dict[str, Any] = {}
            for key in ("file_name", "status", "template_line"):
                compact_value = compact_policy_detail(item.get(key), max_length=240)
                if compact_value is not None:
                    compact_item[key] = compact_value
            file_path = compact_path_label(item.get("file_path"), max_length=240)
            if file_path is not None:
                file_path = compact_policy_detail(file_path, max_length=240)
            if file_path is not None:
                compact_item["file_path"] = file_path
            row_number = compact_int(item.get("csv_row_number"))
            if row_number is not None:
                compact_item["csv_row_number"] = row_number
            if compact_item:
                compact_sequence.append(compact_item)
            if len(compact_sequence) >= IMPORT_APPEND_SEQUENCE_SAMPLE_LIMIT:
                break
        if compact_sequence:
            summary["append_sequence"] = compact_sequence
        source_sequence_count = compact_int(handoff.get("append_sequence_count"))
        if source_sequence_count is not None:
            summary["append_sequence_count"] = source_sequence_count
        else:
            summary["append_sequence_count"] = len(
                [item for item in append_sequence if isinstance(item, dict)]
            )

    summary["available"] = any(key != "available" for key in summary)
    return summary


def source_readiness_summary(status: dict[str, Any]) -> dict[str, Any]:
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        return {"available": False}

    summary: dict[str, Any] = {"available": False}
    text_fields = {
        "artifact_health": source_summary.get("artifact_health"),
        "artifact_health_summary": source_summary.get("artifact_health_summary"),
        "import_readiness": source_summary.get("import_readiness"),
        "current_focus": source_summary.get("current_focus"),
        "policy_reason": source_summary.get("policy_reason"),
        "contract_checks": source_summary.get("contract_checks"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=160)
        if compact_value is not None:
            summary[key] = compact_value

    bool_fields = {
        "ready_for_next_import_records": source_summary.get(
            "ready_for_next_import_records"
        ),
        "dallas_pipeline_ready": source_summary.get("dallas_pipeline_ready"),
    }
    for key, value in bool_fields.items():
        if isinstance(value, bool):
            summary[key] = value

    int_fields = {
        "artifact_count": source_summary.get("artifact_count"),
        "loaded_artifact_count": source_summary.get("loaded_artifact_count"),
        "readiness_blocker_count": source_summary.get("readiness_blocker_count"),
        "thin_group_count": source_summary.get("thin_group_count"),
        "thin_group_category_count": source_summary.get("thin_group_category_count"),
        "queue_items": source_summary.get("queue_items"),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            summary[key] = compact_value

    coverage_latest_thin_counts = compact_count_map(
        source_summary.get("coverage_latest_thin_counts")
    )
    if coverage_latest_thin_counts:
        summary["coverage_latest_thin_counts"] = coverage_latest_thin_counts

    list_fields = {
        "readiness_blockers": source_summary.get("readiness_blockers"),
        "thin_group_categories": source_summary.get("thin_group_categories"),
        "artifact_problem_artifacts": source_summary.get("artifact_problem_artifacts"),
    }
    for key, value in list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = [
            compact_value
            for compact_value in (
                compact_policy_detail(item, max_length=200)
                for item in value[:5]
            )
            if compact_value is not None
        ]
        if compact_values:
            summary[key] = compact_values
            summary[f"{key}_count"] = len(value)

    artifact_statuses = source_summary.get("artifact_statuses")
    if isinstance(artifact_statuses, dict):
        compact_statuses: dict[str, str] = {}
        for key, value in sorted(artifact_statuses.items()):
            compact_key = compact_policy_detail(key, max_length=80)
            compact_value = compact_policy_detail(value, max_length=80)
            if compact_key is not None and compact_value is not None:
                compact_statuses[compact_key] = compact_value
        if compact_statuses:
            summary["artifact_statuses"] = compact_statuses

    import_handoff = source_import_handoff_summary(source_summary)
    if import_handoff["available"]:
        summary["import_handoff"] = import_handoff

    summary["available"] = any(key != "available" for key in summary)
    return summary


def source_coordination_summary(status: dict[str, Any]) -> dict[str, Any]:
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        return {"available": False}
    coordination = source_summary.get("coordination")
    if not isinstance(coordination, dict):
        return {"available": False}

    summary: dict[str, Any] = {"available": False}
    text_fields = {
        "handoff_path": coordination.get("handoff_path"),
        "handoff_file_status": coordination.get("handoff_file_status"),
        "latest_handoff_status": coordination.get("latest_handoff_status"),
    }
    for key, value in text_fields.items():
        compact_value = compact_policy_detail(value, max_length=200)
        if compact_value is not None:
            summary[key] = compact_value

    handoff_error = compact_path_diagnostic(coordination.get("handoff_error"))
    if handoff_error is not None:
        while "<external><external>/" in handoff_error:
            handoff_error = handoff_error.replace(
                "<external><external>/",
                "<external>/",
            )
        handoff_error = compact_policy_detail(handoff_error, max_length=240)
    if handoff_error is not None:
        summary["handoff_error"] = handoff_error

    for key in ("latest_section_found", "latest_status_found"):
        value = coordination.get(key)
        if isinstance(value, bool):
            summary[key] = value

    handoff_age_seconds = compact_int(coordination.get("handoff_age_seconds"))
    if handoff_age_seconds is not None:
        summary["handoff_age_seconds"] = handoff_age_seconds

    summary["available"] = any(key != "available" for key in summary)
    return summary


def source_failure_summary(status: dict[str, Any]) -> dict[str, Any]:
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        return {"available": False}
    failure = source_summary.get("failure_summary")
    if not isinstance(failure, dict):
        return {"available": False}

    summary: dict[str, Any] = {"available": failure.get("available") is True}
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
        compact_value = compact_policy_detail(value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    path_fields = {
        "import_pipeline_summary_path": failure.get("import_pipeline_summary_path"),
        "source_path": failure.get("source_path"),
        "target_path": failure.get("target_path"),
    }
    for key, value in path_fields.items():
        compact_value = compact_path_diagnostic(value, max_length=240)
        if compact_value is not None:
            while "<external><external>/" in compact_value:
                compact_value = compact_value.replace(
                    "<external><external>/",
                    "<external>/",
                )
            compact_value = compact_policy_detail(compact_value, max_length=240)
        if compact_value is not None:
            summary[key] = compact_value

    list_fields = {
        "readiness_blockers": failure.get("readiness_blockers"),
        "degraded_artifacts": failure.get("degraded_artifacts"),
    }
    for key, value in list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = [
            compact_value
            for compact_value in (
                compact_policy_detail(item, max_length=200)
                for item in value[:5]
            )
            if compact_value is not None
        ]
        if compact_values:
            summary[key] = compact_values
            summary[f"{key}_count"] = len(value)

    int_fields = {
        "synthetic_row_count": failure.get("synthetic_row_count"),
        "raw_dallas_csv_changed_path_count": failure.get(
            "raw_dallas_csv_changed_path_count"
        ),
        "productive_changed_path_count": failure.get("productive_changed_path_count"),
        "readiness_blocker_count": failure.get("readiness_blocker_count"),
        "degraded_artifact_count": failure.get("degraded_artifact_count"),
        "sync_exit_status": failure.get("sync_exit_status"),
        "child_pid": failure.get("child_pid"),
    }
    for key, value in int_fields.items():
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

    artifact_statuses = failure.get("artifact_statuses")
    if isinstance(artifact_statuses, dict):
        compact_statuses: dict[str, str] = {}
        for key, value in sorted(artifact_statuses.items()):
            compact_key = compact_policy_detail(key, max_length=80)
            compact_value = compact_policy_detail(value, max_length=80)
            if compact_key is not None and compact_value is not None:
                compact_statuses[compact_key] = compact_value
            if len(compact_statuses) >= 8:
                break
        if compact_statuses:
            summary["artifact_statuses"] = compact_statuses

    environment_preflight = failure.get("environment_preflight")
    if isinstance(environment_preflight, dict):
        compact_preflight: dict[str, Any] = {}
        status_value = compact_policy_detail(
            environment_preflight.get("status"),
            max_length=80,
        )
        if status_value is not None:
            compact_preflight["status"] = status_value
        error_count = compact_int(environment_preflight.get("error_count"))
        if error_count is not None:
            compact_preflight["error_count"] = error_count
        error_categories = compact_path_detail_list(
            environment_preflight.get("error_categories"),
            max_items=12,
            max_length=80,
        )
        if error_categories:
            compact_preflight["error_categories"] = error_categories
        failed_keys = compact_path_detail_list(
            environment_preflight.get("failed_configuration_keys"),
            max_items=12,
            max_length=120,
        )
        if failed_keys:
            compact_preflight["failed_configuration_keys"] = failed_keys
        if compact_preflight:
            summary["environment_preflight"] = compact_preflight

    publisher_preflight = failure.get("publisher_preflight")
    if isinstance(publisher_preflight, dict):
        compact_preflight: dict[str, Any] = {}
        status_value = compact_policy_detail(
            publisher_preflight.get("status"),
            max_length=80,
        )
        if status_value is not None:
            compact_preflight["status"] = status_value
        exit_status = compact_exit_status(publisher_preflight.get("exit_status"))
        if exit_status is not None:
            compact_preflight["exit_status"] = exit_status
        error_count = compact_int(publisher_preflight.get("error_count"))
        if error_count is not None:
            compact_preflight["error_count"] = error_count
        error_categories = compact_path_detail_list(
            publisher_preflight.get("error_categories"),
            max_items=12,
            max_length=80,
        )
        if error_categories:
            compact_preflight["error_categories"] = error_categories
        failed_keys = compact_path_detail_list(
            publisher_preflight.get("failed_configuration_keys"),
            max_items=12,
            max_length=120,
        )
        if failed_keys:
            compact_preflight["failed_configuration_keys"] = failed_keys
        if compact_preflight:
            summary["publisher_preflight"] = compact_preflight

    summary["available"] = any(key != "available" for key in summary)
    return summary


def sanitize_cockpit_summary_for_relay_response(summary: Any) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        return None

    sanitized: dict[str, Any] = {}
    text_fields = {
        "status": summary.get("status"),
        "phase": summary.get("phase"),
        "artifact_health": summary.get("artifact_health"),
        "artifact_health_summary": summary.get("artifact_health_summary"),
        "import_readiness": summary.get("import_readiness"),
        "current_focus": summary.get("current_focus"),
        "policy_reason": summary.get("policy_reason"),
        "contract_checks": summary.get("contract_checks"),
        "policy_failure_reason": summary.get("policy_failure_reason"),
        "policy_diagnostics_status": summary.get("policy_diagnostics_status"),
        "policy_summary": summary.get("policy_summary"),
        "policy_route_hint": summary.get("policy_route_hint"),
        "policy_diagnostics_decision_reason": summary.get(
            "policy_diagnostics_decision_reason"
        ),
        "policy_diagnostics_current_focus": summary.get(
            "policy_diagnostics_current_focus"
        ),
        "operator_attention_primary_reason": summary.get(
            "operator_attention_primary_reason"
        ),
        "operator_attention_label": summary.get("operator_attention_label"),
    }
    for key, value in text_fields.items():
        max_length = 480 if key == "policy_summary" else 160
        compact_value = compact_policy_detail(value, max_length=max_length)
        if compact_value is not None:
            sanitized[key] = compact_value

    bool_fields = {
        "operator_attention": summary.get("operator_attention"),
        "status_timestamp_invalid": summary.get("status_timestamp_invalid"),
        "status_timestamp_future": summary.get("status_timestamp_future"),
        "ready_for_next_import_records": summary.get("ready_for_next_import_records"),
        "dallas_pipeline_ready": summary.get("dallas_pipeline_ready"),
        "policy_preview_json_changed": summary.get("policy_preview_json_changed"),
        "policy_allows_synthetic_append": summary.get(
            "policy_allows_synthetic_append"
        ),
        "policy_override": summary.get("policy_override"),
        "business_hours_pause": summary.get("business_hours_pause"),
    }
    for key, value in bool_fields.items():
        if isinstance(value, bool):
            sanitized[key] = value

    int_fields = {
        "iteration": summary.get("iteration"),
        "status_age_seconds": summary.get("status_age_seconds"),
        "artifact_count": summary.get("artifact_count"),
        "loaded_artifact_count": summary.get("loaded_artifact_count"),
        "readiness_blocker_count": summary.get("readiness_blocker_count"),
        "thin_group_count": summary.get("thin_group_count"),
        "thin_group_category_count": summary.get("thin_group_category_count"),
        "queue_items": summary.get("queue_items"),
        "policy_raw_dallas_csv_changed_path_count": summary.get(
            "policy_raw_dallas_csv_changed_path_count"
        ),
        "policy_productive_changed_path_count": summary.get(
            "policy_productive_changed_path_count"
        ),
        "policy_non_productive_companion_path_count": summary.get(
            "policy_non_productive_companion_path_count"
        ),
        "policy_synthetic_row_count": summary.get("policy_synthetic_row_count"),
    }
    for key, value in int_fields.items():
        compact_value = compact_int(value)
        if compact_value is not None:
            sanitized[key] = compact_value

    coverage_latest_thin_counts = compact_count_map(
        summary.get("coverage_latest_thin_counts")
    )
    if coverage_latest_thin_counts:
        sanitized["coverage_latest_thin_counts"] = coverage_latest_thin_counts

    list_fields = {
        "operator_attention_reasons": summary.get("operator_attention_reasons"),
        "readiness_blockers": summary.get("readiness_blockers"),
        "thin_group_categories": summary.get("thin_group_categories"),
        "artifact_problem_artifacts": summary.get("artifact_problem_artifacts"),
        "policy_synthetic_row_samples": summary.get("policy_synthetic_row_samples"),
    }
    for key, value in list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = [
            compact_value
            for compact_value in (
                compact_policy_detail(item, max_length=240)
                for item in value[:5]
            )
            if compact_value is not None
        ]
        if compact_values:
            sanitized[key] = compact_values
        sanitized[f"{key}_count"] = len(value)

    path_list_fields = {
        "policy_raw_dallas_csv_changed_paths": summary.get(
            "policy_raw_dallas_csv_changed_paths"
        ),
        "policy_productive_changed_paths": summary.get(
            "policy_productive_changed_paths"
        ),
        "policy_non_productive_companion_paths": summary.get(
            "policy_non_productive_companion_paths"
        ),
    }
    for key, value in path_list_fields.items():
        if not isinstance(value, list):
            continue
        compact_values = compact_path_detail_list(value, max_items=5, max_length=240)
        if compact_values:
            sanitized[key] = compact_values
        sanitized[f"{key}_count"] = len(value)

    artifact_statuses = summary.get("artifact_statuses")
    if isinstance(artifact_statuses, dict):
        compact_statuses: dict[str, str] = {}
        for key, value in sorted(artifact_statuses.items()):
            compact_key = compact_policy_detail(key, max_length=80)
            compact_value = compact_policy_detail(value, max_length=80)
            if compact_key is not None and compact_value is not None:
                compact_statuses[compact_key] = compact_value
        if compact_statuses:
            sanitized["artifact_statuses"] = compact_statuses

    import_handoff = source_import_handoff_summary(
        {"import_handoff": summary.get("import_handoff")}
    )
    if import_handoff["available"]:
        sanitized["import_handoff"] = import_handoff

    business_hours = source_business_hours_summary({"cockpit_summary": summary})
    if business_hours["available"]:
        sanitized["business_hours"] = business_hours

    coordination = source_coordination_summary({"cockpit_summary": summary})
    if coordination["available"]:
        sanitized["coordination"] = coordination

    failure = source_failure_summary({"cockpit_summary": summary})
    if failure["available"]:
        sanitized["failure_summary"] = failure

    return sanitized


def sanitize_status_for_relay_response(status: dict[str, Any]) -> dict[str, Any]:
    response_status: dict[str, Any] = {}

    text_fields = (
        "status",
        "phase",
        "mode",
        "updated_at",
        "publisher_updated_at",
        "source_status_file_status",
    )
    for key in text_fields:
        if key not in status:
            continue
        compact_value = compact_policy_detail(status.get(key), max_length=240)
        if compact_value is None:
            continue
        else:
            response_status[key] = compact_value

    path_fields = ("source_status_file",)
    for key in path_fields:
        if key not in status:
            continue
        compact_value = compact_path_label(status.get(key), max_length=240)
        if compact_value is None:
            continue
        else:
            response_status[key] = compact_value

    path_error_fields = ("source_status_file_error",)
    for key in path_error_fields:
        if key not in status:
            continue
        compact_value = compact_path_diagnostic(status.get(key), max_length=240)
        if compact_value is None:
            continue
        else:
            response_status[key] = compact_value

    int_fields = (
        "iteration",
        "loop_pid",
        "source_status_age_seconds",
        "source_status_stale_after_seconds",
        "source_status_remote_omitted_field_count",
    )
    for key in int_fields:
        if key not in status:
            continue
        if status.get(key) is None and key != "source_status_remote_omitted_field_count":
            response_status[key] = None
            continue
        compact_value = compact_int(status.get(key))
        if compact_value is None:
            continue
        else:
            response_status[key] = compact_value

    bool_fields = (
        "loop_running",
        "source_status_value_invalid",
        "source_status_stale",
        "source_status_timestamp_invalid",
        "source_status_timestamp_future",
    )
    for key in bool_fields:
        value = status.get(key)
        if isinstance(value, bool):
            response_status[key] = value

    bridge_summary = status.get("bridge_summary")
    if isinstance(bridge_summary, dict):
        response_status["bridge_summary"] = source_bridge_summary(status)

    cockpit_summary = sanitize_cockpit_summary_for_relay_response(
        status.get("cockpit_summary")
    )
    if cockpit_summary is not None:
        response_status["cockpit_summary"] = cockpit_summary

    business_hours_source = dict(status)
    business_hours_source["cockpit_summary"] = response_status.get("cockpit_summary")
    business_hours = source_business_hours_summary(business_hours_source)
    if business_hours["available"]:
        response_status["business_hours"] = business_hours

    return response_status


def cockpit_health(
    state: dict[str, Any],
    status: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    source_health = publisher_source_health(state)
    source_bridge = source_bridge_summary(status)
    source_business_hours = source_business_hours_summary(status)
    business_hours_pause = source_business_hours_pause_active(
        status,
        source_business_hours,
    )
    source_policy = source_policy_summary(status)
    source_readiness = source_readiness_summary(status)
    source_coordination = source_coordination_summary(status)
    source_failure = source_failure_summary(status)
    source_health_reasons = source_health.get("reasons")
    if not isinstance(source_health_reasons, list):
        source_health_reasons = []
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        source_summary = {}
    source_attention_reason_values: list[str] = []
    source_attention_reasons = source_summary.get("operator_attention_reasons")
    if isinstance(source_attention_reasons, list):
        source_attention_reason_values = [
            str(reason) for reason in source_attention_reasons if reason
        ]
    source_attention_reason_count = compact_int(
        source_summary.get("operator_attention_reasons_count")
    )
    if source_attention_reason_count is None:
        source_attention_reason_count = len(source_attention_reason_values)
    source_attention_reason_samples = [
        compact_reason
        for compact_reason in (
            compact_policy_detail(reason, max_length=160)
            for reason in source_attention_reason_values[:5]
        )
        if compact_reason is not None
    ]
    source_attention_primary_reason = compact_policy_detail(
        source_summary.get("operator_attention_primary_reason"),
        max_length=160,
    )
    source_attention_label = compact_policy_detail(
        source_summary.get("operator_attention_label"),
        max_length=160,
    )
    startup = state.get("relay_startup")
    if isinstance(startup, dict) and startup.get("state_load_status") == "failed":
        reasons.append("relay_state_load_failed")
    if not state.get("received_at"):
        reasons.append("relay_snapshot_missing")
    if freshness.get("snapshot_timestamp_invalid") is True:
        reasons.append("relay_snapshot_timestamp_invalid")
    if freshness.get("snapshot_timestamp_future") is True:
        reasons.append("relay_snapshot_timestamp_future")
    if freshness.get("snapshot_stale") is True:
        reasons.append("relay_snapshot_stale")
    if status.get("source_status_timestamp_invalid") is True:
        reasons.append("source_status_timestamp_invalid")
    if status.get("source_status_timestamp_future") is True:
        reasons.append("source_status_timestamp_future")
    source_status_unavailable = status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }
    if source_status_unavailable:
        reasons.append("source_status_unavailable")
    if (
        status.get("source_status_stale") is True
        and status.get("source_status_timestamp_invalid") is not True
        and status.get("source_status_timestamp_future") is not True
        and not source_status_unavailable
    ):
        reasons.append("source_status_stale")
    if status.get("loop_running") is False and not business_hours_pause:
        reasons.append("source_loop_not_running")
    if "autonomy_policy_failed" in source_attention_reason_values:
        reasons.append("source_autonomy_policy_failed")
    if (
        status.get("status")
        in {"error", "failing", "invalid-status-json", "invalid-status-value"}
        or status.get("source_status_value_invalid") is True
    ):
        reasons.append("source_status_failing")
    if source_summary.get("operator_attention") is True:
        reasons.append("source_cockpit_attention")
    if (
        source_coordination.get("available") is True
        and source_coordination.get("handoff_file_status")
        in {"missing", "read_failed", "invalid_encoding", "too_large"}
    ):
        reasons.append("source_handoff_coordination_unavailable")
    elif source_coordination.get("available") is True and (
        source_coordination.get("latest_section_found") is False
        or source_coordination.get("latest_status_found") is False
    ):
        reasons.append("source_handoff_coordination_incomplete")
    source_bridge_health = source_bridge.get("bridge_health")
    if (
        source_bridge.get("available") is True
        and source_bridge.get("bridge_status_timestamp_invalid") is True
    ):
        reasons.append("source_bridge_status_timestamp_invalid")
    elif (
        source_bridge.get("available") is True
        and source_bridge.get("bridge_status_timestamp_future") is True
    ):
        reasons.append("source_bridge_status_timestamp_future")
    elif (
        source_bridge.get("available") is True
        and source_bridge.get("bridge_status_stale") is True
    ):
        reasons.append("source_bridge_status_stale")
    if source_bridge.get("status_file_status") in {
        "read_failed",
        "invalid_json",
        "not_object",
        "too_large",
    }:
        reasons.append("source_bridge_status_unavailable")
    if (
        source_bridge.get("available") is True
        and (
            source_bridge.get("status") in {"error", "failing", "invalid-status-value"}
            or source_bridge.get("bridge_status_value_invalid") is True
        )
    ):
        reasons.append("source_bridge_status_failing")
    if (
        source_bridge.get("available") is True
        and isinstance(source_bridge_health, dict)
        and source_bridge_health.get("ok") is False
    ):
        reasons.append("source_bridge_degraded")
    for source_health_reason in source_health_reasons:
        if source_health_reason not in reasons:
            reasons.append(source_health_reason)

    if not state.get("received_at"):
        health_status = "waiting"
    elif reasons:
        health_status = "degraded"
    else:
        health_status = "live"
    primary_reason = reasons[0] if reasons else None
    label = cockpit_health_label(primary_reason, source_attention_label)
    if primary_reason is None and business_hours_pause:
        label = "Scheduled pause"
    return {
        "status": health_status,
        "ok": health_status == "live",
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": label,
        "source_cockpit_attention_reasons": source_attention_reason_samples,
        "source_cockpit_attention_reasons_count": source_attention_reason_count,
        "source_cockpit_attention_primary_reason": source_attention_primary_reason,
        "source_cockpit_attention_label": source_attention_label,
        "source_status_diagnostics": source_status_diagnostics(status),
        "source_bridge": source_bridge,
        "source_business_hours": source_business_hours,
        "source_business_hours_pause": business_hours_pause,
        "source_policy": source_policy,
        "source_readiness": source_readiness,
        "source_coordination": source_coordination,
        "source_failure": source_failure,
        "source_health": source_health,
        "publisher_identity": publisher_identity(state),
        "publisher_runtime_config": publisher_runtime_config(state),
    }


def empty_state() -> dict[str, Any]:
    return {
        "relay_status": "waiting",
        "received_at": None,
        "updated_at": utc_now(),
        "status": {
            "status": "relay_waiting",
            "loop_running": False,
            "loop_pid": None,
        },
        "log_tail": "waiting for local cockpit publisher...\n",
        "publisher": {},
    }


def read_json_with_error(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle, parse_constant=reject_json_constant)
    except OSError as exc:
        return None, f"failed_to_read_state_file: {compact_path_error(exc, path)}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_state_json: line {exc.lineno} column {exc.colno}: {exc.msg}"
    except ValueError as exc:
        return None, f"invalid_state_json: {compact_text(str(exc)) or type(exc).__name__}"
    if not isinstance(payload, dict):
        return None, f"state_file_must_be_object: {type(payload).__name__}"
    return payload, None


def load_state(path: Path | None) -> dict[str, Any]:
    state = empty_state()
    if path is None:
        state["relay_startup"] = {
            "state_file": None,
            "state_load_status": "memory_only",
        }
        return state
    state_file = repo_relative(path)
    if not path.exists():
        state["relay_startup"] = {
            "state_file": state_file,
            "state_load_status": "missing",
        }
        return state
    payload, error = read_json_with_error(path)
    if payload is None:
        state["relay_status"] = "state_load_failed"
        state["relay_startup"] = {
            "state_file": state_file,
            "state_load_status": "failed",
            "state_load_error": error,
        }
        return state
    state.update(payload)
    state["relay_startup"] = {
        "state_file": state_file,
        "state_load_status": "loaded",
    }
    return state


def save_state(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    temp_path.replace(path)


def encoded_json_size(payload: Any) -> int:
    return len(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    )


def utf8_tail(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[-max_bytes:].decode("utf-8", errors="ignore")


def sanitize_log_tail_for_relay(text: str, *, max_line_length: int = 1200) -> str:
    sanitized_lines: list[str] = []
    for line in text.splitlines():
        sanitized = "".join(
            " " if ord(character) < 32 or ord(character) == 127 else character
            for character in line
        )
        sanitized = EMBEDDED_URL_RE.sub(
            lambda match: sanitize_url_value(match.group(0)),
            sanitized,
        )
        sanitized = BEARER_SECRET_RE.sub(r"\1 [redacted]", sanitized)
        sanitized = SENSITIVE_ASSIGNMENT_RE.sub(
            lambda match: f"{match.group(1)}=[redacted]",
            sanitized,
        )
        sanitized_lines.append(sanitized[:max_line_length])
    sanitized_text = "\n".join(sanitized_lines)
    if text.endswith(("\n", "\r")) and sanitized_text:
        sanitized_text += "\n"
    return sanitized_text


def snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        return strict_json_clone(STATE)


def update_state(payload: dict[str, Any]) -> dict[str, Any]:
    received_at = utc_now()
    non_finite_metadata_path = first_non_finite_ingest_metadata_path(payload)
    if non_finite_metadata_path is not None:
        raise ValueError(
            "ingest metadata includes non-finite JSON number at "
            f"{non_finite_metadata_path}"
        )

    status = payload.get("status")
    if not isinstance(status, dict):
        status = {"status": "publisher_missing_status"}
    status = dict(status)
    status.setdefault("status", "unknown")
    non_finite_status_path = first_non_finite_json_number_path(status, "$.status")
    if non_finite_status_path is not None:
        raise ValueError(
            "status object includes non-finite JSON number at "
            f"{non_finite_status_path}"
        )
    status_size_bytes = encoded_json_size(status)
    max_status_bytes = int(CONFIG["max_status_bytes"])
    if status_size_bytes > max_status_bytes:
        raise ValueError(
            "status object exceeds max status bytes "
            f"({status_size_bytes} > {max_status_bytes})"
        )

    log_tail = payload.get("log_tail", "")
    if not isinstance(log_tail, str):
        raise ValueError("log_tail must be a string")
    max_log_chars = int(CONFIG["max_log_chars"])
    log_tail = utf8_tail(sanitize_log_tail_for_relay(log_tail), max_log_chars)

    publisher = payload.get("publisher")
    if not isinstance(publisher, dict):
        publisher = {}
    publisher = dict(publisher)
    if payload.get("pushed_at"):
        publisher["pushed_at"] = payload["pushed_at"]
    non_finite_publisher_path = first_non_finite_json_number_path(
        publisher,
        "$.publisher",
    )
    if non_finite_publisher_path is not None:
        raise ValueError(
            "publisher metadata includes non-finite JSON number at "
            f"{non_finite_publisher_path}"
        )
    publisher_size_bytes = encoded_json_size(publisher)
    max_publisher_bytes = int(CONFIG["max_publisher_bytes"])
    if publisher_size_bytes > max_publisher_bytes:
        raise ValueError(
            "publisher metadata exceeds max publisher bytes "
            f"({publisher_size_bytes} > {max_publisher_bytes})"
        )

    next_state = {
        "relay_status": "live",
        "received_at": received_at,
        "updated_at": received_at,
        "status": status,
        "log_tail": log_tail,
        "publisher": publisher,
    }
    with STATE_LOCK:
        try:
            save_state(CONFIG.get("state_file"), next_state)
        except OSError as exc:
            raise RelayPersistenceError(f"failed to persist relay state: {exc}") from exc
        STATE.clear()
        STATE.update(next_state)
        return strict_json_clone(STATE)


def relay_status_payload() -> dict[str, Any]:
    state = snapshot()
    status = state.get("status")
    if not isinstance(status, dict):
        status = {"status": "relay_waiting", "loop_running": False}
    status = sanitize_status_for_relay_response(status)
    freshness = snapshot_freshness(state)
    health = cockpit_health(state, status, freshness)
    status["cockpit_health"] = health
    status["cockpit_status"] = health["status"]
    status["cockpit_ok"] = health["ok"]
    status["cockpit_health_primary_reason"] = health["primary_reason"]
    status["cockpit_health_label"] = health["label"]
    status["publisher_identity"] = health["publisher_identity"]
    status["publisher_runtime_config"] = health["publisher_runtime_config"]
    status["relay"] = {
        "status": state.get("relay_status", "waiting"),
        "received_at": state.get("received_at"),
        "updated_at": state.get("updated_at"),
        **freshness,
        "startup": state.get("relay_startup", {}),
        "publisher_identity": health["publisher_identity"],
        "publisher_runtime_config": health["publisher_runtime_config"],
        "publisher": publisher_for_relay_response(state),
    }
    return status


def health_payload() -> dict[str, Any]:
    state = snapshot()
    status = state.get("status")
    if not isinstance(status, dict):
        status = {"status": "relay_waiting", "loop_running": False}
    status = sanitize_status_for_relay_response(status)
    freshness = snapshot_freshness(state)
    health = cockpit_health(state, status, freshness)
    return {
        "ok": True,
        "service": "automoat-cockpit-relay",
        "cockpit_status": health["status"],
        "cockpit_ok": health["ok"],
        "cockpit_health_primary_reason": health["primary_reason"],
        "cockpit_health_label": health["label"],
        "cockpit_health": health,
        "publisher_identity": health["publisher_identity"],
        "publisher_runtime_config": health["publisher_runtime_config"],
        "relay_status": state.get("relay_status", "waiting"),
        "relay_startup": state.get("relay_startup", {}),
        "has_snapshot": bool(state.get("received_at")),
        "received_at": state.get("received_at"),
        **freshness,
    }


def relay_authentication_result(
    configured_token: str,
    header_token: str,
    authorization: str,
) -> tuple[bool, str]:
    token = configured_token.strip()
    if not token:
        return False, "AUTOMOAT_RELAY_TOKEN is not configured on the relay"

    presented_tokens: list[str] = []
    header_token = header_token.strip()
    if header_token:
        presented_tokens.append(header_token)

    authorization = authorization.strip()
    if authorization:
        if not authorization.lower().startswith("bearer "):
            return False, "invalid relay token"
        bearer = authorization[7:].strip()
        if not bearer:
            return False, "invalid relay token"
        presented_tokens.append(bearer)

    if not presented_tokens:
        return False, "invalid relay token"
    if any(presented_token != token for presented_token in presented_tokens):
        return False, "invalid relay token"
    return True, ""


def parse_positive_int(
    name: str,
    value: Any,
    errors: list[str],
    *,
    maximum: int | None = None,
    max_chars: int | None = None,
) -> int | None:
    text_value = str(value)
    if max_chars is not None and len(text_value) > max_chars:
        errors.append(f"{name} must be {max_chars} characters or fewer")
        return None
    try:
        parsed = int(text_value)
    except (TypeError, ValueError):
        errors.append(f"{name} must be an integer")
        return None
    if parsed <= 0:
        errors.append(f"{name} must be greater than 0")
        return None
    if maximum is not None and parsed > maximum:
        errors.append(f"{name} must be less than or equal to {maximum}")
        return None
    return parsed


def blocking_parent_path_component(path: Path) -> Path | None:
    current_path = path.parent
    while True:
        if current_path.exists():
            return None if current_path.is_dir() else current_path
        if current_path.parent == current_path:
            return None
        current_path = current_path.parent


def is_valid_relay_bind_host(host: str) -> bool:
    normalized = host.strip().rstrip(".").lower()
    if not normalized:
        return False
    if normalized == "localhost":
        return True
    try:
        parsed_ip = ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        return parsed_ip.version == 4

    if len(normalized) > MAX_RELAY_HOST_CHARS:
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


def validate_relay_configuration(
    args: argparse.Namespace,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> list[str]:
    env = env if env is not None else os.environ
    errors: list[str] = []
    token_value = str(env.get("AUTOMOAT_RELAY_TOKEN", ""))
    token = token_value.strip()
    if not token:
        errors.append("AUTOMOAT_RELAY_TOKEN is required")
    elif len(token_value) > MAX_RELAY_TOKEN_CHARS:
        errors.append(
            f"AUTOMOAT_RELAY_TOKEN must be {MAX_RELAY_TOKEN_CHARS} characters or fewer"
        )
    elif any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in token_value
    ):
        errors.append(
            "AUTOMOAT_RELAY_TOKEN must be a single-line value without control characters"
        )
    elif token_value != token:
        errors.append(
            "AUTOMOAT_RELAY_TOKEN must not include leading or trailing whitespace"
        )
    host_value = str(args.host)
    host = host_value.strip()
    if not host:
        errors.append("--host must not be empty")
    elif any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in host_value
    ):
        errors.append("--host must be a single-line value without control characters")
    elif host_value != host:
        errors.append("--host must not include leading or trailing whitespace")
    elif any(character.isspace() for character in host_value):
        errors.append("--host must not contain whitespace")
    elif len(host_value) > MAX_RELAY_HOST_CHARS:
        errors.append(f"--host must be {MAX_RELAY_HOST_CHARS} characters or fewer")
    elif "://" in host_value or "/" in host_value or ":" in host_value:
        errors.append(
            "--host must be a hostname or IPv4 bind address without scheme, path, or port"
        )
    elif not is_valid_relay_bind_host(host):
        errors.append("--host must be a valid hostname or IPv4 bind address")

    state_file_value = str(args.state_file)
    state_file = state_file_value.strip()
    if state_file_value:
        if any(
            character in "\r\n" or ord(character) < 32 or ord(character) == 127
            for character in state_file_value
        ):
            errors.append(
                "--state-file must be a single-line path without control characters"
            )
        elif state_file_value != state_file:
            errors.append("--state-file must not include leading or trailing whitespace")
        elif state_file:
            state_path = Path(state_file).expanduser()
            blocking_path = blocking_parent_path_component(state_path)
            if state_path.exists() and state_path.is_dir():
                errors.append("--state-file must be a file path, not a directory")
            elif blocking_path is not None:
                errors.append(
                    "--state-file parent path "
                    f"{repo_relative(blocking_path)} must be a directory"
                )
    port = parse_positive_int("--port", args.port, errors)
    if port is not None and port > 65535:
        errors.append("--port must be less than or equal to 65535")
    parse_positive_int(
        "--max-ingest-bytes",
        args.max_ingest_bytes,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_ingest_bytes"],
        max_chars=MAX_RUNTIME_CONFIG_VALUE_CHARS,
    )
    parse_positive_int(
        "--max-log-chars",
        args.max_log_chars,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_log_chars"],
        max_chars=MAX_RUNTIME_CONFIG_VALUE_CHARS,
    )
    parse_positive_int(
        "--max-status-bytes",
        args.max_status_bytes,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_status_bytes"],
        max_chars=MAX_RUNTIME_CONFIG_VALUE_CHARS,
    )
    parse_positive_int(
        "--max-publisher-bytes",
        args.max_publisher_bytes,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_publisher_bytes"],
        max_chars=MAX_RUNTIME_CONFIG_VALUE_CHARS,
    )
    parse_positive_int(
        "--stale-after-seconds",
        args.stale_after_seconds,
        errors,
        maximum=RELAY_CONFIG_LIMITS["stale_after_seconds"],
        max_chars=MAX_RUNTIME_CONFIG_VALUE_CHARS,
    )
    return errors


def relay_preflight_error_category(error: str) -> str:
    if error == "AUTOMOAT_RELAY_TOKEN is required":
        return "missing_required"
    if error.startswith("AUTOMOAT_RELAY_TOKEN"):
        return "invalid_secret"
    if error.startswith("--port"):
        return "invalid_port"
    if error.startswith("--state-file"):
        return "invalid_state_file"
    if (
        error.startswith("--max-ingest-bytes")
        or error.startswith("--max-log-chars")
        or error.startswith("--max-status-bytes")
        or error.startswith("--max-publisher-bytes")
        or error.startswith("--stale-after-seconds")
    ):
        return "invalid_runtime_config"
    if error.startswith("--host"):
        return "invalid_host"
    return "invalid_configuration"


def relay_preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({relay_preflight_error_category(error) for error in errors})


def relay_preflight_error_key(error: str) -> str:
    error_key_prefixes = {
        "AUTOMOAT_RELAY_TOKEN": "AUTOMOAT_RELAY_TOKEN",
        "--host": "HOST|--host",
        "--port": "PORT|--port",
        "--state-file": "AUTOMOAT_RELAY_STATE_FILE|--state-file",
        "--max-ingest-bytes": "AUTOMOAT_RELAY_MAX_BYTES|--max-ingest-bytes",
        "--max-log-chars": "AUTOMOAT_RELAY_MAX_LOG_CHARS|--max-log-chars",
        "--max-status-bytes": "AUTOMOAT_RELAY_MAX_STATUS_BYTES|--max-status-bytes",
        "--max-publisher-bytes": (
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES|--max-publisher-bytes"
        ),
        "--stale-after-seconds": (
            "AUTOMOAT_RELAY_STALE_AFTER_SECONDS|--stale-after-seconds"
        ),
    }
    for prefix, key in error_key_prefixes.items():
        if error.startswith(prefix):
            return key
    return "relay_configuration"


def relay_preflight_error_keys(errors: list[str]) -> list[str]:
    return sorted({relay_preflight_error_key(error) for error in errors})


def relay_state_file_label(value: Any) -> str:
    state_file = str(value).strip()
    if not state_file:
        return "memory-only"
    return repo_relative(Path(state_file).expanduser())


def relay_preflight_summary(
    args: argparse.Namespace,
    errors: list[str],
    env: os._Environ[str] | dict[str, str] | None = None,
) -> dict[str, Any]:
    env = env if env is not None else os.environ
    payload: dict[str, Any] = {
        "status": "failed" if errors else "passed",
        "errors": errors,
    }
    if errors:
        payload["diagnostics"] = {
            "error_count": len(errors),
            "error_categories": relay_preflight_error_categories(errors),
            "failed_configuration_keys": relay_preflight_error_keys(errors),
            "relay_token_configured": bool(
                str(env.get("AUTOMOAT_RELAY_TOKEN", "")).strip()
            ),
            "runtime_limits": RELAY_CONFIG_LIMITS,
        }
        return payload

    state_file = relay_state_file_label(args.state_file)
    payload["config"] = {
        "host": str(args.host),
        "port": int(args.port),
        "state_file": state_file,
        "max_ingest_bytes": int(args.max_ingest_bytes),
        "max_log_chars": int(args.max_log_chars),
        "max_status_bytes": int(args.max_status_bytes),
        "max_publisher_bytes": int(args.max_publisher_bytes),
        "stale_after_seconds": int(args.stale_after_seconds),
        "relay_token_configured": bool(
            str(env.get("AUTOMOAT_RELAY_TOKEN", "")).strip()
        ),
        "runtime_limits": RELAY_CONFIG_LIMITS,
    }
    return payload


def emit_relay_preflight(
    args: argparse.Namespace,
    *,
    output_format: str = "text",
) -> list[str]:
    errors = validate_relay_configuration(args)
    if output_format == "json":
        print(
            json.dumps(
                relay_preflight_summary(args, errors),
                sort_keys=True,
            ),
            flush=True,
        )
        return errors

    if errors:
        print("relay environment preflight failed", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return errors

    state_file = relay_state_file_label(args.state_file)
    print(
        "relay environment preflight passed: "
        f"host={args.host} "
        f"port={int(args.port)} "
        f"state_file={state_file} "
        f"max_ingest_bytes={int(args.max_ingest_bytes)} "
        f"max_log_chars={int(args.max_log_chars)} "
        f"max_status_bytes={int(args.max_status_bytes)} "
        f"max_publisher_bytes={int(args.max_publisher_bytes)} "
        f"stale_after_seconds={int(args.stale_after_seconds)} "
        f"runtime_limits={json.dumps(RELAY_CONFIG_LIMITS, sort_keys=True)}",
        flush=True,
    )
    return []


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "AutomoatRelay/0.1"

    def log_message(self, format: str, *args: object) -> None:
        safe_args = tuple(sanitize_request_line_for_log(arg) for arg in args)
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % safe_args)
        )

    def send_common_headers(self, content_type: str) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "authorization, x-automoat-relay-token, content-type",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)

    def send_body(
        self,
        body: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        *,
        head_only: bool = False,
    ) -> None:
        self.send_response(status)
        self.send_common_headers(content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        *,
        head_only: bool = False,
    ) -> None:
        body = (
            json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
        ).encode("utf-8")
        self.send_body(body, "application/json; charset=utf-8", status, head_only=head_only)

    def send_text(
        self,
        text: str,
        status: HTTPStatus = HTTPStatus.OK,
        *,
        head_only: bool = False,
    ) -> None:
        self.send_body(text.encode("utf-8"), "text/plain; charset=utf-8", status, head_only=head_only)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_common_headers("text/plain; charset=utf-8")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.route_read(head_only=True)

    def do_GET(self) -> None:
        self.route_read(head_only=False)

    def route_read(self, *, head_only: bool) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(health_payload(), head_only=head_only)
            return
        if path == "/api/status":
            self.send_json(relay_status_payload(), head_only=head_only)
            return
        if path == "/api/log":
            state = snapshot()
            log_tail = state.get("log_tail")
            if not isinstance(log_tail, str) or not log_tail.strip():
                log_tail = "waiting for local cockpit publisher...\n"
            self.send_text(log_tail.rstrip() + "\n", head_only=head_only)
            return
        if path in {"/", "/cockpit", "/cockpit/"}:
            self.send_json(
                {
                    "service": "automoat-cockpit-relay",
                    "health": "/health",
                    "status": "/api/status",
                    "log": "/api/log",
                    "ingest": "/ingest",
                },
                head_only=head_only,
            )
            return
        self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND, head_only=head_only)

    def authenticated(self) -> tuple[bool, str]:
        return relay_authentication_result(
            str(CONFIG.get("token") or ""),
            self.headers.get("X-Automoat-Relay-Token", ""),
            self.headers.get("Authorization", ""),
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/ingest":
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return

        ok, message = self.authenticated()
        if not ok:
            status = HTTPStatus.SERVICE_UNAVAILABLE if "not configured" in message else HTTPStatus.UNAUTHORIZED
            self.send_json({"error": "unauthorized", "message": message}, status)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "invalid_content_length"}, HTTPStatus.BAD_REQUEST)
            return
        if length <= 0:
            self.send_json({"error": "missing_payload"}, HTTPStatus.BAD_REQUEST)
            return
        if length > int(CONFIG["max_ingest_bytes"]):
            self.send_json({"error": "payload_too_large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return

        try:
            payload = json.loads(
                self.rfile.read(length).decode("utf-8"),
                parse_constant=reject_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self.send_json({"error": "invalid_json"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self.send_json({"error": "payload_must_be_object"}, HTTPStatus.BAD_REQUEST)
            return

        try:
            state = update_state(payload)
        except ValueError as exc:
            self.send_json({"error": "invalid_payload", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except RelayPersistenceError as exc:
            self.send_json(
                {"error": "persistence_failed", "message": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self.send_json(
            {
                "ok": True,
                "received_at": state.get("received_at"),
                "status": state.get("status", {}).get("status"),
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", default=os.environ.get("PORT", "4180"))
    parser.add_argument(
        "--state-file",
        default=os.environ.get("AUTOMOAT_RELAY_STATE_FILE", "/tmp/automoat-relay-state.json"),
        help="path for the latest snapshot; use an empty string for memory-only",
    )
    parser.add_argument(
        "--max-ingest-bytes",
        default=os.environ.get("AUTOMOAT_RELAY_MAX_BYTES", str(DEFAULT_MAX_INGEST_BYTES)),
    )
    parser.add_argument(
        "--max-log-chars",
        default=os.environ.get("AUTOMOAT_RELAY_MAX_LOG_CHARS", str(DEFAULT_MAX_LOG_CHARS)),
    )
    parser.add_argument(
        "--max-status-bytes",
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_STATUS_BYTES",
            str(DEFAULT_MAX_STATUS_BYTES),
        ),
        help="reject ingest payloads whose status object exceeds this serialized size",
    )
    parser.add_argument(
        "--max-publisher-bytes",
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_PUBLISHER_BYTES",
            str(DEFAULT_MAX_PUBLISHER_BYTES),
        ),
        help="reject ingest payloads whose publisher metadata exceeds this serialized size",
    )
    parser.add_argument(
        "--stale-after-seconds",
        default=os.environ.get("AUTOMOAT_RELAY_STALE_AFTER_SECONDS", str(DEFAULT_STALE_AFTER_SECONDS)),
        help="mark relay snapshots stale when they are older than this many seconds",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate relay startup configuration and exit without serving",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for --check-env preflight results",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.format == "json" and not args.check_env:
        print("--format json is only supported with --check-env", file=sys.stderr)
        return 2

    errors = validate_relay_configuration(args)
    if args.check_env:
        return 2 if emit_relay_preflight(args, output_format=args.format) else 0
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    state_file = Path(args.state_file).expanduser() if args.state_file else None
    CONFIG.update(
        {
            "token": os.environ.get("AUTOMOAT_RELAY_TOKEN", ""),
            "state_file": state_file,
            "max_ingest_bytes": int(args.max_ingest_bytes),
            "max_log_chars": int(args.max_log_chars),
            "max_status_bytes": int(args.max_status_bytes),
            "max_publisher_bytes": int(args.max_publisher_bytes),
            "stale_after_seconds": int(args.stale_after_seconds),
        }
    )
    with STATE_LOCK:
        STATE.clear()
        STATE.update(load_state(state_file))

    server = ThreadingHTTPServer((args.host, int(args.port)), RelayHandler)
    print(f"automoat cockpit relay listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
