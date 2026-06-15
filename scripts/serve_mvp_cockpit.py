#!/usr/bin/env python3
"""Serve a local cockpit that starts and streams the MVP loop."""

from __future__ import annotations

import argparse
import html
import json
import math
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, urlunparse

from operator_corrections import append_operator_correction, correction_summary


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / ".automoat" / "logs" / "mvp-loop.log"
STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-loop-status.json"
PID_FILE = ROOT / ".automoat" / "state" / "mvp-loop.pid"
BRIDGE_STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-bridge-status.json"
MAX_CORRECTION_BYTES = 8192
STATUS_STALE_AFTER_SECONDS = 120
POLICY_RAW_PATH_SAMPLE_LIMIT = 8
POLICY_ROW_SAMPLE_LIMIT = 5
BRIDGE_HEALTH_REASON_SAMPLE_LIMIT = 5
URL_TEXT_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
BEARER_SECRET_PATTERN = re.compile(
    r"\b(authorization\s*[:=]\s*bearer)\s+[^\s,;]+",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|relay_token|access_token|api_key|x-automoat-relay-token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
OPERATOR_ATTENTION_LABELS = {
    "loop_not_running": "Loop is not running",
    "status_failing": "Loop status is failing",
    "autonomy_policy_failed": "Autonomy policy failed",
    "status_stale": "Status is stale",
    "status_timestamp_invalid": "Status timestamp is invalid",
    "artifact_health_not_loaded": "Artifact health is not loaded",
    "import_readiness_not_ready": "Import readiness is not ready",
    "import_readiness_blocked": "Import readiness is blocked",
    "coverage_thin_groups_present": "Coverage has thin groups",
}

LOOP_PROCESS: subprocess.Popen[str] | None = None
LOOP_LOCK = threading.Lock()
SERVER_CONFIG: dict[str, float | int | str] = {"iterations": 0, "interval": 8.0, "loop_mode": "mvp"}
SERVER_CONFIG["read_only"] = 0
HTTP_REQUEST_METHODS = {
    "DELETE",
    "GET",
    "HEAD",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tail_lines(path: Path, limit: int = 160) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def first_string_list(*values: object) -> list[str]:
    """Return the first non-empty compact string list from candidate payload fields."""
    for value in values:
        items = as_string_list(value)
        if items:
            return items
    return []


def compact_text(value: object, *, max_length: int = 180) -> str | None:
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
    resolved_path = path.resolve()
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


def compact_url(value: object, *, max_length: int = 180) -> str | None:
    text = compact_text(value, max_length=max_length)
    if text is None:
        return None
    return sanitize_url_value(text)


def compact_policy_detail(value: object, *, max_length: int = 240) -> str | None:
    text = compact_text(value, max_length=max_length * 2)
    if text is None:
        return None
    text = URL_TEXT_PATTERN.sub(lambda match: sanitize_url_value(match.group(0)), text)
    text = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", text)
    text = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        text,
    )
    return text[:max_length] if text else None


def compact_policy_detail_list(
    value: object,
    *,
    max_items: int,
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


def compact_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def first_compact_int(*values: object) -> int | None:
    for value in values:
        parsed = compact_int(value)
        if parsed is not None:
            return parsed
    return None


def first_bool(*values: object) -> bool | None:
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def compact_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def operator_attention_label(reason: str | None) -> str:
    if reason is None:
        return "Clear"
    return OPERATOR_ATTENTION_LABELS.get(reason, reason.replace("_", " "))


def failed_autonomy_policy_step(status: dict[str, object]) -> dict[str, object] | None:
    step = latest_autonomy_policy_step(status)
    if step is not None and step.get("exit_status") != 0:
        return step
    return None


def latest_autonomy_policy_step(status: dict[str, object]) -> dict[str, object] | None:
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


def utc_timestamp_age_seconds(value: object, now: datetime | None = None) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    age = int((current - timestamp.astimezone(timezone.utc)).total_seconds())
    return max(age, 0)


def bridge_health_summary(value: object) -> dict[str, object]:
    health = value if isinstance(value, dict) else {}
    reason_values = as_string_list(health.get("reasons"))
    reasons = compact_policy_detail_list(
        reason_values,
        max_items=BRIDGE_HEALTH_REASON_SAMPLE_LIMIT,
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
    summary: dict[str, object] = {
        "status": status,
        "ok": ok,
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": label,
    }
    if len(reason_values) > len(reasons):
        summary["reasons_count"] = len(reason_values)
    return summary


def artifact_status_summary(value: object) -> dict[str, str]:
    statuses = value if isinstance(value, dict) else {}
    summary: dict[str, str] = {}
    for key, status in sorted(statuses.items()):
        artifact_name = compact_text(key, max_length=80)
        artifact_status = compact_text(status, max_length=80)
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


def read_bridge_summary() -> dict[str, object]:
    status_file = repo_relative(BRIDGE_STATUS_FILE)
    if not BRIDGE_STATUS_FILE.exists():
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "missing",
        }
    try:
        payload = json.loads(
            BRIDGE_STATUS_FILE.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
        )
    except OSError as exc:
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "read_failed",
            "status_file_error": compact_path_error(exc, BRIDGE_STATUS_FILE),
        }
    except json.JSONDecodeError as exc:
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "invalid_json",
            "status_file_error": f"line {exc.lineno} column {exc.colno}: {exc.msg}",
        }
    except ValueError as exc:
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "invalid_json",
            "status_file_error": compact_text(str(exc)) or type(exc).__name__,
        }
    if not isinstance(payload, dict):
        return {
            "available": False,
            "status_file": status_file,
            "status_file_status": "not_object",
            "status_file_error": type(payload).__name__,
        }

    summary: dict[str, object] = {
        "available": True,
        "status_file": status_file,
        "status_file_status": "loaded",
        "bridge_health": bridge_health_summary(payload.get("bridge_health")),
    }
    text_fields = {
        "status": payload.get("status"),
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


def import_handoff_summary(import_pipeline: dict[str, object]) -> dict[str, object]:
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
    summary: dict[str, object] = {
        "available": True,
        "next_append_rows": next_append_rows,
        "append_preflight_status": compact_text(preflight.get("status")) or "unknown",
        "append_preflight_checks": preflight_checks,
        "append_preflight_blockers": as_string_list(preflight.get("blockers")),
    }

    ready_for_append = preflight.get("ready_for_append")
    if isinstance(ready_for_append, bool):
        summary["ready_for_append"] = ready_for_append

    text_fields = {
        "raw_dir": handoff.get("raw_dir"),
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


def cockpit_summary(status: dict[str, object]) -> dict[str, object]:
    artifacts = as_dict(status.get("artifacts"))
    artifact_health = as_dict(artifacts.get("artifact_health"))
    contract = as_dict(artifacts.get("contract"))
    workflow = as_dict(artifacts.get("workflow"))
    import_pipeline = as_dict(artifacts.get("import_pipeline"))
    readiness = as_dict(import_pipeline.get("execution_readiness"))
    autonomy_policy = as_dict(status.get("autonomy_policy"))

    passed_checks = contract.get("passed_checks")
    total_checks = contract.get("total_checks")
    contract_checks = None
    if passed_checks is not None and total_checks is not None:
        contract_checks = f"{passed_checks}/{total_checks}"

    updated_at = status.get("updated_at")
    status_age_seconds = utc_timestamp_age_seconds(updated_at)
    status_stale = None
    if status_age_seconds is not None:
        status_stale = status_age_seconds > STATUS_STALE_AFTER_SECONDS
    status_timestamp_invalid = updated_at is not None and status_age_seconds is None

    status_value = status.get("status") or "waiting"
    loop_running = bool(status.get("loop_running"))
    artifact_health_status = artifact_health.get("status") or "unknown"
    artifact_statuses = artifact_status_summary(artifact_health.get("statuses"))
    artifact_problem_artifacts = artifact_problem_summary(
        artifact_health.get("degraded_artifacts"),
        artifact_statuses,
    )
    import_readiness = readiness.get("status") or "unknown"
    readiness_blockers = as_string_list(readiness.get("blockers"))
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
    policy_diagnostics_status = compact_policy_detail(
        policy_diagnostics.get("status"),
        max_length=80,
    )
    policy_route_hint = compact_policy_detail(
        policy_diagnostics.get("route_hint"),
        max_length=120,
    )
    policy_diagnostics_decision_reason = compact_policy_detail(
        policy_diagnostics.get("decision_reason")
    )
    policy_diagnostics_current_focus = compact_policy_detail(
        policy_diagnostics.get("current_focus")
    )
    policy_raw_csv_paths = (
        compact_policy_detail_list(
            first_string_list(
                policy_step.get("raw_dallas_csv_changed_paths"),
                policy_diagnostics.get("raw_dallas_csv_changed_path_samples"),
            ),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
        )
        if policy_step
        else []
    )
    policy_raw_csv_path_count = (
        len(as_string_list(policy_step.get("raw_dallas_csv_changed_paths")))
        if policy_step
        else 0
    )
    policy_productive_paths = (
        compact_policy_detail_list(
            first_string_list(
                policy_step.get("productive_changed_paths"),
                policy_diagnostics.get("productive_changed_path_samples"),
            ),
            max_items=POLICY_RAW_PATH_SAMPLE_LIMIT,
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
        else None
    )
    if policy_productive_path_count is None:
        policy_productive_path_count = 0
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
    policy_raw_csv_path_count = (
        first_compact_int(
            policy_diagnostics.get("raw_dallas_csv_changed_path_count"),
            policy_raw_csv_path_count,
        )
        if policy_step
        else 0
    )
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
    thin_group_categories = as_string_list(autonomy_policy.get("thin_group_categories"))
    thin_group_count = autonomy_policy.get("thin_group_count")
    if not isinstance(thin_group_count, int):
        thin_group_count = len(thin_group_categories)

    attention_reasons: list[str] = []
    if not loop_running:
        attention_reasons.append("loop_not_running")
    if policy_failure:
        attention_reasons.append("autonomy_policy_failed")
    if status_value in {"error", "failing", "invalid-status-json"}:
        attention_reasons.append("status_failing")
    if status_stale is True:
        attention_reasons.append("status_stale")
    if status_timestamp_invalid:
        attention_reasons.append("status_timestamp_invalid")
    if artifact_health_status != "loaded":
        attention_reasons.append("artifact_health_not_loaded")
    if import_readiness != "ready":
        attention_reasons.append("import_readiness_not_ready")
    if readiness_blockers:
        attention_reasons.append("import_readiness_blocked")
    if thin_group_count > 0:
        attention_reasons.append("coverage_thin_groups_present")
    primary_attention_reason = attention_reasons[0] if attention_reasons else None

    return {
        "status": status_value,
        "phase": status.get("phase"),
        "mode": status.get("mode") or SERVER_CONFIG.get("loop_mode", "mvp"),
        "loop_running": loop_running,
        "loop_pid": status.get("loop_pid"),
        "iteration": status.get("iteration") or 0,
        "updated_at": updated_at,
        "status_age_seconds": status_age_seconds,
        "status_stale_after_seconds": STATUS_STALE_AFTER_SECONDS,
        "status_stale": status_stale,
        "status_timestamp_invalid": status_timestamp_invalid,
        "operator_attention": bool(attention_reasons),
        "operator_attention_reasons": attention_reasons,
        "operator_attention_primary_reason": primary_attention_reason,
        "operator_attention_label": operator_attention_label(primary_attention_reason),
        "artifact_health": artifact_health_status,
        "artifact_statuses": artifact_statuses,
        "artifact_problem_artifacts": artifact_problem_artifacts,
        "import_readiness": import_readiness,
        "readiness_blockers": readiness_blockers,
        "ready_for_next_import_records": readiness.get("ready_for_next_import_records"),
        "import_handoff": import_handoff_summary(import_pipeline),
        "current_focus": autonomy_policy.get("current_focus") or "mvp_loop",
        "policy_reason": autonomy_policy.get("decision_reason"),
        "policy_failure_reason": policy_failure_reason,
        "policy_diagnostics_status": policy_diagnostics_status,
        "policy_route_hint": policy_route_hint,
        "policy_diagnostics_decision_reason": policy_diagnostics_decision_reason,
        "policy_diagnostics_current_focus": policy_diagnostics_current_focus,
        "policy_preview_json_changed": policy_preview_changed,
        "policy_raw_dallas_csv_changed_paths": policy_raw_csv_paths,
        "policy_raw_dallas_csv_changed_path_count": policy_raw_csv_path_count,
        "policy_productive_changed_paths": policy_productive_paths,
        "policy_productive_changed_path_count": policy_productive_path_count,
        "policy_synthetic_row_samples": policy_synthetic_row_samples,
        "policy_synthetic_row_count": policy_synthetic_row_count,
        "policy_allows_synthetic_append": policy_allows_synthetic_append,
        "policy_override": policy_override,
        "dallas_pipeline_ready": autonomy_policy.get("dallas_pipeline_ready"),
        "thin_group_count": thin_group_count,
        "thin_group_categories": thin_group_categories,
        "contract_checks": contract_checks,
        "queue_items": workflow.get("queue_items"),
    }


def read_status() -> dict[str, object]:
    status_file = repo_relative(STATUS_FILE)
    if STATUS_FILE.exists():
        try:
            payload = json.loads(
                STATUS_FILE.read_text(encoding="utf-8"),
                parse_constant=reject_json_constant,
            )
        except OSError as exc:
            status = {
                "status": "invalid-status-json",
                "source_status_file": status_file,
                "source_status_file_status": "read_failed",
                "source_status_file_error": compact_path_error(exc, STATUS_FILE),
            }
        except json.JSONDecodeError as exc:
            status = {
                "status": "invalid-status-json",
                "source_status_file": status_file,
                "source_status_file_status": "invalid_json",
                "source_status_file_error": f"line {exc.lineno} column {exc.colno}: {exc.msg}",
            }
        except ValueError as exc:
            status = {
                "status": "invalid-status-json",
                "source_status_file": status_file,
                "source_status_file_status": "invalid_json",
                "source_status_file_error": compact_text(str(exc)) or type(exc).__name__,
            }
        else:
            if isinstance(payload, dict):
                status = payload
                status["source_status_file"] = status_file
                status["source_status_file_status"] = "loaded"
            else:
                status = {
                    "status": "invalid-status-json",
                    "source_status_file": status_file,
                    "source_status_file_status": "not_object",
                    "source_status_file_error": type(payload).__name__,
                }
    else:
        status = {
            "status": "waiting",
            "updated_at": None,
            "source_status_file": status_file,
            "source_status_file_status": "missing",
        }
    with LOOP_LOCK:
        running = LOOP_PROCESS is not None and LOOP_PROCESS.poll() is None
        pid = LOOP_PROCESS.pid if running and LOOP_PROCESS is not None else None
    if not running and PID_FILE.exists():
        try:
            pid_candidate = int(PID_FILE.read_text(encoding="utf-8").strip())
            os.kill(pid_candidate, 0)
            running = True
            pid = pid_candidate
        except (ValueError, OSError):
            pid = None
    status["loop_running"] = running
    status["loop_pid"] = pid
    status["cockpit_summary"] = cockpit_summary(status)
    status["bridge_summary"] = read_bridge_summary()
    return status


def start_loop() -> tuple[bool, str]:
    global LOOP_PROCESS
    with LOOP_LOCK:
        if LOOP_PROCESS is not None and LOOP_PROCESS.poll() is None:
            return False, f"loop already running pid={LOOP_PROCESS.pid}"
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        loop_mode = str(SERVER_CONFIG.get("loop_mode", "mvp"))
        script_name = "run_autonomous_agent_loop.py" if loop_mode == "agent" else "run_mvp_loop.py"
        command = [
            sys.executable,
            str(ROOT / "scripts" / script_name),
            "--iterations",
            str(int(SERVER_CONFIG["iterations"])),
            "--interval",
            str(float(SERVER_CONFIG["interval"])),
        ]
        LOOP_PROCESS = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            text=True,
        )
        PID_FILE.write_text(str(LOOP_PROCESS.pid) + "\n", encoding="utf-8")
        return True, f"loop started pid={LOOP_PROCESS.pid}"


def stop_loop() -> tuple[bool, str]:
    global LOOP_PROCESS
    with LOOP_LOCK:
        if LOOP_PROCESS is None or LOOP_PROCESS.poll() is not None:
            return False, "loop is not running"
        LOOP_PROCESS.terminate()
        return True, f"sent terminate to pid={LOOP_PROCESS.pid}"


def safe_file_path(raw_path: str) -> Path | None:
    parsed = unquote(urlparse(raw_path).path).lstrip("/")
    if not parsed:
        return None
    candidate = (ROOT / parsed).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    if candidate.is_file():
        if int(SERVER_CONFIG.get("read_only", 0)):
            relative = candidate.relative_to(ROOT).as_posix()
            allowed_exact = {
                ".automoat/logs/mvp-loop.log",
                ".automoat/state/mvp-loop-status.json",
                "assets/automoat-icon.svg",
                "generated/landing.html",
                "index.html",
            }
            allowed_prefixes = (
                "generated/contracts/dallas-electrician-contract-summary-v1/",
                "generated/coverage/dallas-electrician-edge-case-coverage-v1/",
                "generated/workflows/dallas-inspection-workflow-v1/",
            )
            if relative not in allowed_exact and not relative.startswith(allowed_prefixes):
                return None
        return candidate
    return None


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


def cockpit_html() -> str:
    status = read_status()
    current_status = html.escape(str(status.get("status", "waiting")))
    read_only = bool(int(SERVER_CONFIG.get("read_only", 0)))
    status_mode = str(status.get("mode") or SERVER_CONFIG.get("loop_mode", "mvp"))
    agent_mode = status_mode == "autonomous_codex" or str(SERVER_CONFIG.get("loop_mode")) == "agent"
    badge = "Read-Only Remote Bridge" if read_only else ("Autonomous Codex Agent" if agent_mode else "Real MVP Loop")
    title = (
        "Remote view of the local Autom oat agent."
        if read_only and agent_mode
        else "Remote view of the local Autom oat loop."
        if read_only
        else "Watch Codex make bounded autonomous improvements."
        if agent_mode
        else "Watch Autom oat build the permit-data moat loop."
    )
    explainer = (
        "This bridge exposes only the live agent status, log stream, and whitelisted MVP artifacts. "
        "Start/stop controls stay on the local cockpit."
        if read_only and agent_mode
        else "This bridge exposes only the live loop status, log stream, and whitelisted MVP artifacts. "
        "Start/stop controls stay on the local cockpit."
        if read_only
        else "This page starts a real Codex process. Each iteration asks Codex to make one bounded repo improvement, "
        "then the supervisor syncs, verifies, commits, and pushes to main before sleeping."
        if agent_mode
        else "This page starts a real local process that regenerates the Dallas MVP contract, "
        "coverage, and action queue, then streams the loop log as it runs."
    )
    controls = (
        '<a class="button secondary" href="/">Refresh bridge</a>'
        if read_only
        else '<button id="start">Start loop</button><button id="stop" class="secondary">Stop loop</button>'
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>automoat cockpit</title>
    <style>
      :root {{
        --bg: #f5f1e8;
        --paper: rgba(255, 252, 246, 0.92);
        --ink: #1d2430;
        --muted: #5f6773;
        --line: rgba(29, 36, 48, 0.12);
        --accent: #b6542d;
        --accent-soft: #f0d8c8;
        --blue: #284d68;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        background:
          radial-gradient(circle at 18% 10%, rgba(182, 84, 45, 0.16), transparent 26%),
          linear-gradient(180deg, #fbf8f1 0%, var(--bg) 100%);
        font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      }}
      main {{ max-width: 1180px; margin: 0 auto; padding: 22px 16px 56px; }}
      .shell {{
        border: 1px solid var(--line);
        border-radius: 30px;
        background: var(--paper);
        box-shadow: 0 24px 70px rgba(29, 36, 48, 0.12);
        overflow: hidden;
      }}
      header, section {{ padding: 24px; }}
      header {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        border-bottom: 1px solid var(--line);
      }}
      h1, h2 {{ margin: 0; letter-spacing: -0.03em; }}
      h1 {{ max-width: 760px; font-size: 3.6rem; line-height: 0.96; }}
      h2 {{ font-size: 1.4rem; }}
      p {{ color: var(--muted); line-height: 1.65; margin: 12px 0 0; }}
      .badge {{
        display: inline-flex;
        align-items: center;
        height: 34px;
        padding: 0 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font: 700 0.78rem "Helvetica Neue", Arial, sans-serif;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      .controls {{
        display: flex;
        align-items: flex-start;
        justify-content: flex-end;
        gap: 10px;
        flex-wrap: wrap;
      }}
      button, a.button {{
        border: 1px solid transparent;
        border-radius: 14px;
        min-height: 42px;
        padding: 0 14px;
        background: var(--accent);
        color: #fff8f3;
        cursor: pointer;
        text-decoration: none;
        font: 700 0.9rem "Helvetica Neue", Arial, sans-serif;
      }}
      button.secondary, a.button.secondary {{
        border-color: var(--line);
        background: rgba(255, 255, 255, 0.62);
        color: var(--ink);
      }}
      .grid {{
        display: grid;
        grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.35fr);
        gap: 16px;
      }}
      .card {{
        border: 1px solid var(--line);
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.62);
        padding: 18px;
      }}
      .metric-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 16px;
      }}
      .metric {{
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 12px;
        background: rgba(240, 216, 200, 0.25);
      }}
      .metric strong {{
        display: block;
        font: 700 1.35rem "Helvetica Neue", Arial, sans-serif;
      }}
      .metric span {{
        color: var(--muted);
        font: 0.82rem "Helvetica Neue", Arial, sans-serif;
      }}
      .detail-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        margin-top: 14px;
      }}
      .detail {{
        border-top: 1px solid var(--line);
        padding-top: 10px;
        min-width: 0;
      }}
      .detail span {{
        display: block;
        color: var(--muted);
        font: 0.72rem "Helvetica Neue", Arial, sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .detail strong {{
        display: block;
        margin-top: 4px;
        overflow-wrap: anywhere;
        font: 700 0.92rem "Helvetica Neue", Arial, sans-serif;
      }}
      pre {{
        height: 590px;
        margin: 0;
        overflow: auto;
        white-space: pre-wrap;
        border-radius: 22px;
        background: #151b24;
        color: #fff8f3;
        padding: 18px;
        font: 0.84rem/1.65 "SFMono-Regular", Menlo, Consolas, monospace;
      }}
      .links {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 14px;
      }}
      .links a {{
        border: 1px solid var(--line);
        border-radius: 999px;
        padding: 8px 10px;
        color: var(--blue);
        text-decoration: none;
        background: rgba(240, 216, 200, 0.24);
        font: 700 0.82rem "Helvetica Neue", Arial, sans-serif;
      }}
      @media (max-width: 820px) {{
        main {{ padding: 0 0 34px; }}
        .shell {{ border-radius: 0; border-left: 0; border-right: 0; }}
        header {{ flex-direction: column; }}
        h1 {{ font-size: 2.5rem; }}
        .grid {{ grid-template-columns: 1fr; }}
        pre {{ height: 520px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <div class="shell">
        <header>
          <div>
            <div class="badge">{badge}</div>
            <h1>{title}</h1>
            <p>{explainer}</p>
          </div>
          <div class="controls">
            {controls}
            <a class="button secondary" href="/generated/landing.html">Landing</a>
          </div>
        </header>
        <section class="grid">
          <div class="card">
            <h2>Status</h2>
            <p id="summary">Current status: {current_status}</p>
            <div class="metric-grid">
              <div class="metric"><strong id="loop">...</strong><span>loop</span></div>
              <div class="metric"><strong id="iteration">...</strong><span>iteration</span></div>
              <div class="metric"><strong id="contract">...</strong><span>contract checks</span></div>
              <div class="metric"><strong id="queue">...</strong><span>queue items</span></div>
            </div>
            <div class="detail-grid">
              <div class="detail"><span>import readiness</span><strong id="readiness">...</strong></div>
              <div class="detail"><span>policy focus</span><strong id="focus">...</strong></div>
              <div class="detail"><span>phase</span><strong id="phase">...</strong></div>
              <div class="detail"><span>artifact health</span><strong id="artifactHealth">...</strong></div>
              <div class="detail"><span>status freshness</span><strong id="freshness">...</strong></div>
              <div class="detail"><span>operator attention</span><strong id="attention">...</strong></div>
              <div class="detail"><span>next import rows</span><strong id="importHandoff">...</strong></div>
              <div class="detail"><span>bridge health</span><strong id="bridgeHealth">...</strong></div>
            </div>
            <div class="links">
              <a href="/.automoat/logs/mvp-loop.log">raw loop log</a>
              <a href="/.automoat/state/mvp-loop-status.json">status json</a>
              <a href="/generated/contracts/dallas-electrician-contract-summary-v1/summary.md">contract summary</a>
              <a href="/generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md">coverage report</a>
              <a href="/generated/workflows/dallas-inspection-workflow-v1/index.html">action queue</a>
              <a href="/generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl">correction ledger</a>
            </div>
          </div>
          <pre id="log">connecting to loop stream...</pre>
        </section>
      </div>
    </main>
    <script>
      const log = document.getElementById("log");
      const summary = document.getElementById("summary");
      const loop = document.getElementById("loop");
      const iteration = document.getElementById("iteration");
      const contract = document.getElementById("contract");
      const queue = document.getElementById("queue");
      const readiness = document.getElementById("readiness");
      const focus = document.getElementById("focus");
      const phase = document.getElementById("phase");
      const artifactHealth = document.getElementById("artifactHealth");
      const freshness = document.getElementById("freshness");
      const attention = document.getElementById("attention");
      const importHandoff = document.getElementById("importHandoff");
      const bridgeHealth = document.getElementById("bridgeHealth");

      async function post(path) {{
        const response = await fetch(path, {{ method: "POST" }});
        await refreshStatus();
        return response.text();
      }}

      async function refreshStatus() {{
        const response = await fetch("/api/status", {{ cache: "no-store" }});
        const status = await response.json();
        const cockpit = status.cockpit_summary || {{}};
        const bridge = status.bridge_summary || {{}};
        const bridgeCompact = bridge.bridge_health || {{}};
        const bridgeReasons = Array.isArray(bridgeCompact.reasons) ? bridgeCompact.reasons : [];
        summary.textContent = `Current status: ${{cockpit.status || status.status || "waiting"}}`;
        loop.textContent = cockpit.loop_running ? `running #${{cockpit.loop_pid}}` : "stopped";
        iteration.textContent = cockpit.iteration || status.iteration || "0";
        const checks = status.artifacts?.contract;
        contract.textContent = cockpit.contract_checks || (checks ? `${{checks.passed_checks}}/${{checks.total_checks}}` : "...");
        queue.textContent = cockpit.queue_items ?? status.artifacts?.workflow?.queue_items ?? "...";
        readiness.textContent = cockpit.import_readiness || "unknown";
        focus.textContent = cockpit.current_focus || "mvp_loop";
        phase.textContent = cockpit.phase || "...";
        const artifactStatuses = cockpit.artifact_statuses || {{}};
        const artifactProblems = Array.isArray(cockpit.artifact_problem_artifacts)
          ? cockpit.artifact_problem_artifacts
          : [];
        const artifactBase = cockpit.artifact_health || "unknown";
        artifactHealth.textContent = artifactProblems.length
          ? `${{artifactBase}}: ${{artifactProblems.join(", ")}}`
          : artifactBase;
        artifactHealth.title = Object.entries(artifactStatuses)
          .map(([name, value]) => `${{name}}: ${{value}}`)
          .join(", ");
        const age = cockpit.status_age_seconds;
        if (typeof age === "number") {{
          freshness.textContent = cockpit.status_stale ? `stale ${{age}}s` : `fresh ${{age}}s`;
        }} else {{
          freshness.textContent = "unknown";
        }}
        const reasons = Array.isArray(cockpit.operator_attention_reasons) ? cockpit.operator_attention_reasons : [];
        attention.textContent = cockpit.operator_attention
          ? cockpit.operator_attention_label || reasons.join(", ") || "Required"
          : cockpit.operator_attention_label || "Clear";
        const policySamples = Array.isArray(cockpit.policy_synthetic_row_samples)
          ? cockpit.policy_synthetic_row_samples
          : [];
        const policyRawPaths = Array.isArray(cockpit.policy_raw_dallas_csv_changed_paths)
          ? cockpit.policy_raw_dallas_csv_changed_paths
          : [];
        const policyRawPathCount = typeof cockpit.policy_raw_dallas_csv_changed_path_count === "number"
          ? cockpit.policy_raw_dallas_csv_changed_path_count
          : policyRawPaths.length;
        const policySyntheticRowCount = typeof cockpit.policy_synthetic_row_count === "number"
          ? cockpit.policy_synthetic_row_count
          : policySamples.length;
        const policyProductivePaths = Array.isArray(cockpit.policy_productive_changed_paths)
          ? cockpit.policy_productive_changed_paths
          : [];
        const policyProductivePathCount = typeof cockpit.policy_productive_changed_path_count === "number"
          ? cockpit.policy_productive_changed_path_count
          : policyProductivePaths.length;
        attention.title = [
          reasons.join(", "),
          cockpit.policy_failure_reason ? `policy: ${{cockpit.policy_failure_reason}}` : "",
          cockpit.policy_route_hint ? `route: ${{cockpit.policy_route_hint}}` : "",
          cockpit.policy_diagnostics_status ? `policy status: ${{cockpit.policy_diagnostics_status}}` : "",
          typeof cockpit.policy_preview_json_changed === "boolean" ? `preview changed: ${{cockpit.policy_preview_json_changed}}` : "",
          typeof cockpit.policy_allows_synthetic_append === "boolean" ? `synthetic allowed: ${{cockpit.policy_allows_synthetic_append}}` : "",
          typeof cockpit.policy_override === "boolean" ? `override: ${{cockpit.policy_override}}` : "",
          policyRawPaths.length ? `raw csv (${{policyRawPathCount}}): ${{policyRawPaths.join(", ")}}` : "",
          policyProductivePaths.length ? `productive (${{policyProductivePathCount}}): ${{policyProductivePaths.join(", ")}}` : "",
          policySamples.length ? `synthetic rows (${{policySyntheticRowCount}}): ${{policySamples.join(" | ")}}` : "",
        ].filter(Boolean).join(" | ");
        const handoff = cockpit.import_handoff || {{}};
        const nextRows = handoff.next_append_rows || {{}};
        const preferredNextRows = ["permits.csv", "inspections.csv"]
          .filter((name) => typeof nextRows[name] === "number")
          .map((name) => `${{name.replace(".csv", "")}} ${{nextRows[name]}}`);
        const fallbackNextRows = Object.entries(nextRows)
          .slice(0, 2)
          .map(([name, row]) => `${{name.replace(".csv", "")}} ${{row}}`);
        const visibleNextRows = preferredNextRows.length ? preferredNextRows : fallbackNextRows;
        importHandoff.textContent = handoff.available
          ? visibleNextRows.join(", ") || handoff.append_preflight_status || "available"
          : "unavailable";
        const preflightChecks = handoff.append_preflight_checks || {{}};
        importHandoff.title = [
          handoff.raw_dir,
          handoff.append_preflight_status ? `preflight: ${{handoff.append_preflight_status}}` : "",
          Array.isArray(handoff.append_preflight_blockers) && handoff.append_preflight_blockers.length
            ? `blockers: ${{handoff.append_preflight_blockers.join(", ")}}`
            : "",
          Object.entries(preflightChecks).length
            ? `checks: ${{Object.entries(preflightChecks).map(([name, passed]) => `${{name}}=${{passed}}`).join(", ")}}`
            : "",
          handoff.readiness_check_command,
        ].filter(Boolean).join(" | ");
        bridgeHealth.textContent = bridge.available
          ? bridgeCompact.label || bridgeCompact.status || bridge.status || "Live"
          : bridge.status_file_status || "missing";
        bridgeHealth.title = bridge.available
          ? [bridge.public_url, bridgeReasons.join(", ")].filter(Boolean).join(" | ")
          : bridge.status_file || "";
      }}

      const startButton = document.getElementById("start");
      const stopButton = document.getElementById("stop");
      if (startButton) startButton.addEventListener("click", () => post("/api/start"));
      if (stopButton) stopButton.addEventListener("click", () => post("/api/stop"));

      const events = new EventSource("/events");
      events.onmessage = (event) => {{
        if (log.textContent === "connecting to loop stream...") log.textContent = "";
        log.textContent += event.data + "\\n";
        log.scrollTop = log.scrollHeight;
      }};
      events.addEventListener("status", refreshStatus);
      refreshStatus();
      setInterval(refreshStatus, 2000);
    </script>
  </body>
</html>
"""


class CockpitHandler(BaseHTTPRequestHandler):
    server_version = "AutomoatCockpit/0.1"

    def log_message(self, format: str, *args: object) -> None:
        safe_args = tuple(sanitize_request_line_for_log(arg) for arg in args)
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % safe_args)
        )

    def send_cors_headers(self) -> None:
        if int(SERVER_CONFIG.get("read_only", 0)):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "ngrok-skip-browser-warning, content-type")
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")

    def send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_text(
        self,
        text: str,
        content_type: str = "text/plain; charset=utf-8",
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_bytes(text.encode("utf-8"), content_type, status)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/cockpit", "/cockpit/"}:
            self.send_text(cockpit_html(), "text/html; charset=utf-8")
            return
        if path == "/api/status":
            self.send_text(json.dumps(read_status(), indent=2) + "\n", "application/json; charset=utf-8")
            return
        if path == "/api/operator-corrections":
            self.send_text(json.dumps(correction_summary(), indent=2) + "\n", "application/json; charset=utf-8")
            return
        if path == "/events":
            self.stream_events()
            return
        file_path = safe_file_path(self.path)
        if file_path is not None:
            content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
            self.send_bytes(file_path.read_bytes(), content_type)
            return
        self.send_text("not found\n", status=HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/cockpit", "/cockpit/"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_cors_headers()
            self.end_headers()
            return
        if path == "/api/status":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_cors_headers()
            self.end_headers()
            return
        if path == "/api/operator-corrections":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_cors_headers()
            self.end_headers()
            return
        file_path = safe_file_path(self.path)
        if file_path is not None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.send_cors_headers()
            self.end_headers()
            return
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_cors_headers()
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Cache-Control", "no-store")
        self.send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        if int(SERVER_CONFIG.get("read_only", 0)):
            self.send_text("read-only bridge\n", status=HTTPStatus.FORBIDDEN)
            return
        path = urlparse(self.path).path
        if path == "/api/start":
            _started, message = start_loop()
            self.send_text(message + "\n")
            return
        if path == "/api/stop":
            _stopped, message = stop_loop()
            self.send_text(message + "\n")
            return
        if path == "/api/operator-corrections":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_text("invalid content length\n", status=HTTPStatus.BAD_REQUEST)
                return
            if length <= 0:
                self.send_text("missing correction payload\n", status=HTTPStatus.BAD_REQUEST)
                return
            if length > MAX_CORRECTION_BYTES:
                self.send_text("correction payload too large\n", status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                event = append_operator_correction(payload)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_text("invalid correction json\n", status=HTTPStatus.BAD_REQUEST)
                return
            except ValueError as exc:
                self.send_text(str(exc) + "\n", status=HTTPStatus.BAD_REQUEST)
                return
            self.send_text(
                json.dumps(event, indent=2) + "\n",
                "application/json; charset=utf-8",
                status=HTTPStatus.CREATED,
            )
            return
        self.send_text("not found\n", status=HTTPStatus.NOT_FOUND)

    def stream_events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        sent = 0
        for line in tail_lines(LOG_FILE, 140):
            self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
            sent += 1
        self.wfile.flush()
        last_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        while True:
            time.sleep(0.7)
            try:
                status_line = "event: status\ndata: tick\n\n"
                self.wfile.write(status_line.encode("utf-8"))
                if LOG_FILE.exists():
                    current_size = LOG_FILE.stat().st_size
                    if current_size < last_size:
                        last_size = 0
                    if current_size > last_size:
                        with LOG_FILE.open("r", encoding="utf-8", errors="replace") as handle:
                            handle.seek(last_size)
                            chunk = handle.read()
                        last_size = current_size
                        for line in chunk.splitlines():
                            self.wfile.write(f"data: {line}\n\n".encode("utf-8"))
                            sent += 1
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request: object, client_address: object) -> None:
        exc_type, exc, _traceback = sys.exc_info()
        if exc_type in {BrokenPipeError, ConnectionResetError}:
            return
        super().handle_error(request, client_address)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4174)
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--iterations", type=int, default=0)
    parser.add_argument("--interval", type=float, default=8.0)
    parser.add_argument("--read-only", action="store_true")
    parser.add_argument("--loop-mode", choices=("mvp", "agent"), default="mvp")
    parser.add_argument("--agent-loop", action="store_true", help="alias for --loop-mode agent")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    SERVER_CONFIG["iterations"] = args.iterations
    SERVER_CONFIG["interval"] = args.interval
    SERVER_CONFIG["loop_mode"] = "agent" if args.agent_loop else args.loop_mode
    SERVER_CONFIG["read_only"] = 1 if args.read_only else 0
    if args.auto_start:
        started, message = start_loop()
        print(message, flush=True)
    server = QuietThreadingHTTPServer((args.host, args.port), CockpitHandler)
    url = f"http://{args.host}:{args.port}/"
    print(url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_loop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
