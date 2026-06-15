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


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "pushed_at": utc_now(),
        "status": read_status(
            args.status_file,
            args.pid_file,
            args.status_stale_after_seconds,
        ),
        "log_tail": tail_text(args.log_file, args.tail_lines, args.max_log_bytes),
        "publisher": {
            "host": socket.gethostname(),
            "repo": str(ROOT),
            "status_file": repo_relative(args.status_file),
            "pid_file": repo_relative(args.pid_file),
            "log_file": repo_relative(args.log_file),
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
    return {
        "source_status": status.get("status", "unknown"),
        "source_loop_running": status.get("loop_running"),
        "source_status_stale": status.get("source_status_stale"),
        "source_status_age_seconds": status.get("source_status_age_seconds"),
        "source_status_file_status": status.get("source_status_file_status"),
    }


def relay_response_failure_reason(response: dict[str, Any]) -> str:
    reason = response.get("error") or response.get("message") or "relay_response_not_ok"
    return str(reason).replace("\r", " ").replace("\n", " ")[:200]


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
            f"source_status_file_status={source_fields.get('source_status_file_status')}",
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
            f"source_status_file_status={source_fields.get('source_status_file_status')}",
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
            f"source_status_file_status={source_fields['source_status_file_status']}",
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
        f"source_status_file_status={source_fields['source_status_file_status']}",
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
    relay_url = str(args.relay_url).strip()
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


def emit_publisher_preflight(args: argparse.Namespace) -> list[str]:
    errors = validate_publisher_configuration(args)
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
    errors = validate_publisher_configuration(args)
    if args.check_env:
        return 0 if not emit_publisher_preflight(args) else 2
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 2

    if args.once:
        return 0 if publish_once(args) else 1

    return run_publish_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
