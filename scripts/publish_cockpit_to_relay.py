#!/usr/bin/env python3
"""Publish local Autom oat cockpit status snapshots to the Render relay."""

from __future__ import annotations

import argparse
import json
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
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_MAX_CONSECUTIVE_STALE_STATUSES = 0
DEFAULT_STATUS_STALE_AFTER_SECONDS = 660
PUBLISHER_CONFIG_LIMITS = {
    "interval": 60,
    "timeout": 60,
    "tail_lines": 2000,
    "max_log_bytes": 1024 * 1024,
    "max_consecutive_failures": 100,
    "max_consecutive_stale_statuses": 100,
    "status_stale_after_seconds": 3600,
}
URL_TEXT_PATTERN = re.compile(r"https?://[^\s'\"<>]+")
BEARER_SECRET_PATTERN = re.compile(
    r"\b(authorization\s*[:=]\s*bearer)\s+[^\s,;]+",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(token|access_token|api_key|x-automoat-relay-token)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
SOURCE_HEALTH_LABELS = {
    "source_status_unavailable": "Source status is unavailable",
    "source_status_stale": "Source status is stale",
    "source_loop_not_running": "Source loop is not running",
    "source_status_failing": "Source status is failing",
}
OPERATOR_ATTENTION_LABELS = {
    "loop_not_running": "Loop is not running",
    "status_failing": "Loop status is failing",
    "autonomy_policy_failed": "Autonomy policy failed",
    "status_stale": "Status is stale",
    "artifact_health_not_loaded": "Artifact health is not loaded",
    "import_readiness_not_ready": "Import readiness is not ready",
    "import_readiness_blocked": "Import readiness is blocked",
    "coverage_thin_groups_present": "Coverage has thin groups",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


PUBLISHER_STARTED_AT = utc_now()
PUBLISHER_SNAPSHOT_SEQUENCE = 0


def emit(message: str, *, log_path: Path) -> None:
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def repo_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json_with_status(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "source_status_file": repo_relative(path),
        "source_status_file_status": "loaded",
    }
    if not path.exists():
        metadata["source_status_file_status"] = "missing"
        return None, metadata
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        metadata["source_status_file_status"] = "read_failed"
        metadata["source_status_file_error"] = str(exc)
        return None, metadata
    except json.JSONDecodeError as exc:
        metadata["source_status_file_status"] = "invalid_json"
        metadata["source_status_file_error"] = (
            f"line {exc.lineno} column {exc.colno}: {exc.msg}"
        )
        return None, metadata
    if not isinstance(payload, dict):
        metadata["source_status_file_status"] = "not_object"
        metadata["source_status_file_error"] = type(payload).__name__
        return None, metadata
    return payload, metadata


def read_json(path: Path) -> dict[str, Any] | None:
    payload, _metadata = read_json_with_status(path)
    return payload


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
    updated_at = parse_utc_timestamp(status.get("updated_at"))
    current_time = parse_utc_timestamp(utc_now())
    if updated_at is None or current_time is None:
        return {
            "source_status_age_seconds": None,
            "source_status_stale_after_seconds": stale_after_seconds,
            "source_status_stale": True,
        }
    age_seconds = max(0, int((current_time - updated_at).total_seconds()))
    return {
        "source_status_age_seconds": age_seconds,
        "source_status_stale_after_seconds": stale_after_seconds,
        "source_status_stale": age_seconds > stale_after_seconds,
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def operator_attention_label(reason: str | None) -> str:
    if reason is None:
        return "Clear"
    return OPERATOR_ATTENTION_LABELS.get(reason, reason.replace("_", " "))


def failed_autonomy_policy_step(status: dict[str, Any]) -> dict[str, Any] | None:
    steps = status.get("steps")
    if not isinstance(steps, list):
        return None
    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        if step.get("name") != "autonomy policy check":
            continue
        if step.get("exit_status") != 0:
            return step
    return None


def publisher_cockpit_summary(status: dict[str, Any]) -> dict[str, Any]:
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

    status_value = status.get("status") or "waiting"
    loop_running = bool(status.get("loop_running"))
    artifact_health_status = artifact_health.get("status") or "unknown"
    import_readiness = readiness.get("status") or "unknown"
    readiness_blockers = as_string_list(readiness.get("blockers"))
    policy_failure = failed_autonomy_policy_step(status)
    policy_failure_reason = (
        str(policy_failure.get("failure_reason"))
        if policy_failure and policy_failure.get("failure_reason")
        else None
    )
    policy_raw_csv_paths = (
        as_string_list(policy_failure.get("raw_dallas_csv_changed_paths"))
        if policy_failure
        else []
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
    if status.get("source_status_stale") is True:
        attention_reasons.append("status_stale")
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
        "mode": status.get("mode") or "unknown",
        "loop_running": loop_running,
        "loop_pid": status.get("loop_pid"),
        "iteration": status.get("iteration") or 0,
        "updated_at": status.get("updated_at"),
        "status_age_seconds": status.get("source_status_age_seconds"),
        "status_stale_after_seconds": status.get("source_status_stale_after_seconds"),
        "status_stale": status.get("source_status_stale"),
        "operator_attention": bool(attention_reasons),
        "operator_attention_reasons": attention_reasons,
        "operator_attention_primary_reason": primary_attention_reason,
        "operator_attention_label": operator_attention_label(primary_attention_reason),
        "artifact_health": artifact_health_status,
        "import_readiness": import_readiness,
        "readiness_blockers": readiness_blockers,
        "ready_for_next_import_records": readiness.get("ready_for_next_import_records"),
        "current_focus": autonomy_policy.get("current_focus") or "mvp_loop",
        "policy_reason": autonomy_policy.get("decision_reason"),
        "policy_failure_reason": policy_failure_reason,
        "policy_raw_dallas_csv_changed_paths": policy_raw_csv_paths,
        "dallas_pipeline_ready": autonomy_policy.get("dallas_pipeline_ready"),
        "thin_group_count": thin_group_count,
        "thin_group_categories": thin_group_categories,
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
) -> dict[str, Any]:
    loaded_status, source_file_metadata = read_json_with_status(status_file)
    status = loaded_status or {
        "status": "waiting",
        "updated_at": None,
    }
    status = dict(status)
    status.update(source_file_metadata)
    status.update(status_freshness(status, status_stale_after_seconds))
    pid = local_loop_pid(pid_file)
    status["loop_running"] = pid is not None
    status["loop_pid"] = pid
    status["publisher_updated_at"] = utc_now()
    status["cockpit_summary"] = publisher_cockpit_summary(status)
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


def next_publisher_snapshot_sequence() -> int:
    global PUBLISHER_SNAPSHOT_SEQUENCE
    PUBLISHER_SNAPSHOT_SEQUENCE += 1
    return PUBLISHER_SNAPSHOT_SEQUENCE


def source_health_label(reason: str | None) -> str:
    if reason is None:
        return "Live"
    return SOURCE_HEALTH_LABELS.get(reason, reason.replace("_", " "))


def publisher_source_health(status: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
    }:
        reasons.append("source_status_unavailable")
    if status.get("source_status_stale") is True:
        reasons.append("source_status_stale")
    if status.get("loop_running") is False:
        reasons.append("source_loop_not_running")
    if status.get("status") in {"error", "failing"}:
        reasons.append("source_status_failing")

    primary_reason = reasons[0] if reasons else None
    health_status = "degraded" if reasons else "live"
    return {
        "status": health_status,
        "ok": health_status == "live",
        "reasons": reasons,
        "primary_reason": primary_reason,
        "label": source_health_label(primary_reason),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    status = read_status(
        args.status_file,
        args.pid_file,
        args.status_stale_after_seconds,
    )
    return {
        "pushed_at": utc_now(),
        "status": status,
        "log_tail": tail_text(args.log_file, args.tail_lines, args.max_log_bytes),
        "publisher": {
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "publisher_started_at": PUBLISHER_STARTED_AT,
            "snapshot_sequence": next_publisher_snapshot_sequence(),
            "repo": str(ROOT),
            "status_file": repo_relative(args.status_file),
            "pid_file": repo_relative(args.pid_file),
            "log_file": repo_relative(args.log_file),
            "source_health": publisher_source_health(status),
            "git": git_snapshot(),
        },
    }


def post_payload(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    relay_url = args.relay_url.rstrip("/")
    data = json.dumps(payload).encode("utf-8")
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
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    return parsed if isinstance(parsed, dict) else {"ok": False, "body": body}


def source_status_log_fields(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status")
    if not isinstance(status, dict):
        status = {}
    publisher = payload.get("publisher")
    if not isinstance(publisher, dict):
        publisher = {}
    source_health = publisher.get("source_health")
    if not isinstance(source_health, dict):
        source_health = {}
    git = publisher.get("git")
    if not isinstance(git, dict):
        git = {}
    return {
        "source_status": status.get("status", "unknown"),
        "source_loop_running": status.get("loop_running"),
        "source_status_stale": status.get("source_status_stale"),
        "source_status_age_seconds": status.get("source_status_age_seconds"),
        "source_status_file_status": status.get("source_status_file_status"),
        "source_health_status": source_health.get("status"),
        "source_health_primary_reason": source_health.get("primary_reason"),
        "source_health_label": source_health.get("label"),
        "publisher_host": publisher.get("host"),
        "publisher_pid": publisher.get("pid"),
        "publisher_started_at": publisher.get("publisher_started_at"),
        "publisher_snapshot_sequence": publisher.get("snapshot_sequence"),
        "publisher_git_head": git.get("head"),
        "publisher_git_dirty_path_count": git.get("dirty_path_count"),
    }


def relay_response_failure_reason(response: dict[str, Any]) -> str:
    reason = response.get("error") or response.get("message") or "relay_response_not_ok"
    return sanitize_error_for_log(RuntimeError(str(reason)))[:200]


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
    return {
        "http_status": exc.code,
        "http_reason": reason.replace("\r", " ").replace("\n", " ")[:80],
        "http_body_bytes": body_bytes,
    }


def sanitize_url_for_log(match: re.Match[str]) -> str:
    value = match.group(0)
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


def sanitize_error_for_log(exc: BaseException) -> str:
    message = str(exc)
    message = URL_TEXT_PATTERN.sub(sanitize_url_for_log, message)
    message = BEARER_SECRET_PATTERN.sub(r"\1 [redacted]", message)
    message = SECRET_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[redacted]",
        message,
    )
    message = message.replace("\r", " ").replace("\n", " ")
    return message[:300]


def publish_once_result(args: argparse.Namespace) -> dict[str, Any]:
    source_fields: dict[str, Any] = {}
    try:
        payload = build_payload(args)
        source_fields = source_status_log_fields(payload)
        response = post_payload(args, payload)
    except HTTPError as exc:
        http_fields = http_error_summary(exc)
        emit(
            "publish failed "
            f"http_status={http_fields['http_status']} "
            f"http_reason={http_fields['http_reason']} "
            f"http_body_bytes={http_fields['http_body_bytes']} "
            f"source_status={source_fields.get('source_status', 'unknown')} "
            f"source_loop_running={source_fields.get('source_loop_running')} "
            f"source_status_stale={source_fields.get('source_status_stale')} "
            f"source_status_age_seconds={source_fields.get('source_status_age_seconds')} "
            f"source_status_file_status={source_fields.get('source_status_file_status')} "
            f"source_health_status={source_fields.get('source_health_status')} "
            f"source_health_primary_reason={source_fields.get('source_health_primary_reason')} "
            f"source_health_label={source_fields.get('source_health_label')} "
            f"publisher_host={source_fields.get('publisher_host')} "
            f"publisher_pid={source_fields.get('publisher_pid')} "
            f"publisher_started_at={source_fields.get('publisher_started_at')} "
            f"publisher_snapshot_sequence={source_fields.get('publisher_snapshot_sequence')} "
            f"publisher_git_head={source_fields.get('publisher_git_head')} "
            f"publisher_git_dirty_path_count={source_fields.get('publisher_git_dirty_path_count')}",
            log_path=args.publisher_log,
        )
        return {
            "published": False,
            "source_status_stale": source_fields.get("source_status_stale"),
        }
    except (OSError, URLError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        emit(
            "publish failed "
            f"error={sanitize_error_for_log(exc)} "
            f"source_status={source_fields.get('source_status', 'unknown')} "
            f"source_loop_running={source_fields.get('source_loop_running')} "
            f"source_status_stale={source_fields.get('source_status_stale')} "
            f"source_status_age_seconds={source_fields.get('source_status_age_seconds')} "
            f"source_status_file_status={source_fields.get('source_status_file_status')} "
            f"source_health_status={source_fields.get('source_health_status')} "
            f"source_health_primary_reason={source_fields.get('source_health_primary_reason')} "
            f"source_health_label={source_fields.get('source_health_label')} "
            f"publisher_host={source_fields.get('publisher_host')} "
            f"publisher_pid={source_fields.get('publisher_pid')} "
            f"publisher_started_at={source_fields.get('publisher_started_at')} "
            f"publisher_snapshot_sequence={source_fields.get('publisher_snapshot_sequence')} "
            f"publisher_git_head={source_fields.get('publisher_git_head')} "
            f"publisher_git_dirty_path_count={source_fields.get('publisher_git_dirty_path_count')}",
            log_path=args.publisher_log,
        )
        return {
            "published": False,
            "source_status_stale": source_fields.get("source_status_stale"),
        }
    if not response.get("ok"):
        emit(
            "publish failed relay_ok=False "
            f"reason={relay_response_failure_reason(response)} "
            f"source_status={source_fields['source_status']} "
            f"source_loop_running={source_fields['source_loop_running']} "
            f"source_status_stale={source_fields['source_status_stale']} "
            f"source_status_age_seconds={source_fields['source_status_age_seconds']} "
            f"source_status_file_status={source_fields['source_status_file_status']} "
            f"source_health_status={source_fields['source_health_status']} "
            f"source_health_primary_reason={source_fields['source_health_primary_reason']} "
            f"source_health_label={source_fields['source_health_label']} "
            f"publisher_host={source_fields['publisher_host']} "
            f"publisher_pid={source_fields['publisher_pid']} "
            f"publisher_started_at={source_fields['publisher_started_at']} "
            f"publisher_snapshot_sequence={source_fields['publisher_snapshot_sequence']} "
            f"publisher_git_head={source_fields['publisher_git_head']} "
            f"publisher_git_dirty_path_count={source_fields['publisher_git_dirty_path_count']}",
            log_path=args.publisher_log,
        )
        return {
            "published": False,
            "source_status_stale": source_fields["source_status_stale"],
        }
    emit(
        f"published relay snapshot ok={response.get('ok')} "
        f"received_at={response.get('received_at')} "
        f"source_status={source_fields['source_status']} "
        f"source_loop_running={source_fields['source_loop_running']} "
        f"source_status_stale={source_fields['source_status_stale']} "
        f"source_status_age_seconds={source_fields['source_status_age_seconds']} "
        f"source_status_file_status={source_fields['source_status_file_status']} "
        f"source_health_status={source_fields['source_health_status']} "
        f"source_health_primary_reason={source_fields['source_health_primary_reason']} "
        f"source_health_label={source_fields['source_health_label']} "
        f"publisher_host={source_fields['publisher_host']} "
        f"publisher_pid={source_fields['publisher_pid']} "
        f"publisher_started_at={source_fields['publisher_started_at']} "
        f"publisher_snapshot_sequence={source_fields['publisher_snapshot_sequence']} "
        f"publisher_git_head={source_fields['publisher_git_head']} "
        f"publisher_git_dirty_path_count={source_fields['publisher_git_dirty_path_count']}",
        log_path=args.publisher_log,
    )
    return {
        "published": True,
        "source_status_stale": source_fields["source_status_stale"],
    }


def publish_once(args: argparse.Namespace) -> bool:
    return bool(publish_once_result(args)["published"])


def run_publish_loop(args: argparse.Namespace) -> int:
    consecutive_failures = 0
    consecutive_stale_statuses = 0
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
                    emit(
                        "exiting after consecutive stale source statuses "
                        f"count={consecutive_stale_statuses} "
                        f"limit={args.max_consecutive_stale_statuses}",
                        log_path=args.publisher_log,
                    )
                    return 1
            else:
                consecutive_stale_statuses = 0
        else:
            consecutive_failures += 1
            if (
                args.max_consecutive_failures > 0
                and consecutive_failures >= args.max_consecutive_failures
            ):
                emit(
                    "exiting after consecutive publish failures "
                    f"count={consecutive_failures} "
                    f"limit={args.max_consecutive_failures}",
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

    token_value = str(args.token)
    token = token_value.strip()
    if not token:
        errors.append("AUTOMOAT_RELAY_TOKEN or --token is required")
    elif any(
        character in "\r\n" or ord(character) < 32 or ord(character) == 127
        for character in token_value
    ):
        errors.append("--token must be a single-line value without control characters")
    elif token_value != token:
        errors.append("--token must not include leading or trailing whitespace")
    if args.interval <= 0:
        errors.append("--interval must be greater than 0")
    elif args.interval > PUBLISHER_CONFIG_LIMITS["interval"]:
        errors.append(
            "--interval must be less than or equal to "
            f"{format_number(PUBLISHER_CONFIG_LIMITS['interval'])}"
        )
    if args.timeout <= 0:
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

    configured_file_args = {
        "--status-file": args.status_file,
        "--pid-file": args.pid_file,
        "--log-file": args.log_file,
        "--publisher-log": args.publisher_log,
    }
    for label, path in configured_file_args.items():
        if path.exists() and path.is_dir():
            errors.append(f"{label} must be a file path, not a directory")
    publisher_log_parent = args.publisher_log.parent
    if publisher_log_parent.exists() and not publisher_log_parent.is_dir():
        errors.append("--publisher-log parent must be a directory")
    return errors


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
            "--status-stale-after-seconds",
        )
    ):
        return "invalid_runtime_config"
    if error.startswith(("--status-file", "--pid-file", "--log-file", "--publisher-log")):
        return "invalid_file_path"
    return "invalid_configuration"


def publisher_preflight_error_categories(errors: list[str]) -> list[str]:
    return sorted({publisher_preflight_error_category(error) for error in errors})


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
            "relay_url_configured": bool(str(args.relay_url).strip()),
            "relay_token_configured": bool(str(args.token).strip()),
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
        "max_consecutive_failures": int(args.max_consecutive_failures),
        "max_consecutive_stale_statuses": int(
            args.max_consecutive_stale_statuses
        ),
        "status_file": str(args.status_file),
        "pid_file": str(args.pid_file),
        "log_file": str(args.log_file),
        "publisher_log": str(args.publisher_log),
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
        f"max_consecutive_failures={args.max_consecutive_failures} "
        f"max_consecutive_stale_statuses={args.max_consecutive_stale_statuses} "
        f"runtime_limits={json.dumps(PUBLISHER_CONFIG_LIMITS, sort_keys=True)}"
    )
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relay-url", default=os.environ.get("AUTOMOAT_RELAY_URL", ""))
    parser.add_argument("--token", default=os.environ.get("AUTOMOAT_RELAY_TOKEN", ""))
    parser.add_argument("--interval", type=float, default=os.environ.get("AUTOMOAT_RELAY_INTERVAL", "3"))
    parser.add_argument("--timeout", type=float, default=os.environ.get("AUTOMOAT_RELAY_TIMEOUT", "8"))
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
    parser.add_argument("--tail-lines", type=int, default=os.environ.get("AUTOMOAT_RELAY_TAIL_LINES", "180"))
    parser.add_argument(
        "--max-log-bytes",
        type=int,
        default=os.environ.get("AUTOMOAT_RELAY_MAX_LOG_BYTES", str(256 * 1024)),
    )
    parser.add_argument("--status-file", type=Path, default=STATUS_FILE)
    parser.add_argument("--pid-file", type=Path, default=PID_FILE)
    parser.add_argument("--log-file", type=Path, default=LOG_FILE)
    parser.add_argument("--publisher-log", type=Path, default=PUBLISHER_LOG)
    parser.add_argument(
        "--status-stale-after-seconds",
        type=int,
        default=os.environ.get(
            "AUTOMOAT_STATUS_STALE_AFTER_SECONDS",
            str(DEFAULT_STATUS_STALE_AFTER_SECONDS),
        ),
        help="mark the source loop status stale when updated_at is older than this many seconds",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_FAILURES",
            str(DEFAULT_MAX_CONSECUTIVE_FAILURES),
        ),
        help=(
            "exit nonzero after this many consecutive publish failures; "
            "set 0 to retry forever"
        ),
    )
    parser.add_argument(
        "--max-consecutive-stale-statuses",
        type=int,
        default=os.environ.get(
            "AUTOMOAT_RELAY_MAX_CONSECUTIVE_STALE_STATUSES",
            str(DEFAULT_MAX_CONSECUTIVE_STALE_STATUSES),
        ),
        help=(
            "exit nonzero after this many consecutive successful publishes whose "
            "source status is stale; set 0 to keep relaying stale status"
        ),
    )
    return parser.parse_args()


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    args.status_file = args.status_file.expanduser().resolve()
    args.pid_file = args.pid_file.expanduser().resolve()
    args.log_file = args.log_file.expanduser().resolve()
    args.publisher_log = args.publisher_log.expanduser().resolve()
    return args


def main() -> int:
    args = normalize_args(parse_args())
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
