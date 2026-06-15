#!/usr/bin/env python3
"""Render-hosted read relay for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATE_LOCK = threading.Lock()
STATE: dict[str, Any] = {}
CONFIG: dict[str, Any] = {}
DEFAULT_MAX_INGEST_BYTES = 1024 * 1024
DEFAULT_MAX_LOG_CHARS = 160 * 1024
DEFAULT_MAX_STATUS_BYTES = 128 * 1024
DEFAULT_STALE_AFTER_SECONDS = 120
RELAY_CONFIG_LIMITS = {
    "max_ingest_bytes": 4 * 1024 * 1024,
    "max_log_chars": 1024 * 1024,
    "max_status_bytes": 512 * 1024,
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
    received_at = parse_utc_timestamp(state.get("received_at"))
    current_time = parse_utc_timestamp(utc_now())
    if received_at is None or current_time is None:
        return {
            "snapshot_age_seconds": None,
            "snapshot_stale_after_seconds": stale_after,
            "snapshot_stale": True,
        }
    age_seconds = max(0, int((current_time - received_at).total_seconds()))
    return {
        "snapshot_age_seconds": age_seconds,
        "snapshot_stale_after_seconds": stale_after,
        "snapshot_stale": age_seconds > stale_after,
    }


def cockpit_health(
    state: dict[str, Any],
    status: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    source_summary = status.get("cockpit_summary")
    if not isinstance(source_summary, dict):
        source_summary = {}
    source_attention_reasons = source_summary.get("operator_attention_reasons")
    if not isinstance(source_attention_reasons, list):
        source_attention_reasons = []
    source_attention_primary_reason = source_summary.get(
        "operator_attention_primary_reason"
    )
    if not isinstance(source_attention_primary_reason, str):
        source_attention_primary_reason = None
    source_attention_label = source_summary.get("operator_attention_label")
    if not isinstance(source_attention_label, str):
        source_attention_label = None
    startup = state.get("relay_startup")
    if isinstance(startup, dict) and startup.get("state_load_status") == "failed":
        reasons.append("relay_state_load_failed")
    if not state.get("received_at"):
        reasons.append("relay_snapshot_missing")
    if freshness.get("snapshot_stale") is True:
        reasons.append("relay_snapshot_stale")
    if status.get("source_status_stale") is True:
        reasons.append("source_status_stale")
    if status.get("source_status_file_status") in {
        "missing",
        "read_failed",
        "invalid_json",
        "not_object",
    }:
        reasons.append("source_status_unavailable")
    if status.get("loop_running") is False:
        reasons.append("source_loop_not_running")
    if status.get("status") in {"error", "failing"}:
        reasons.append("source_status_failing")
    if source_summary.get("operator_attention") is True:
        reasons.append("source_cockpit_attention")

    if not state.get("received_at"):
        health_status = "waiting"
    elif reasons:
        health_status = "degraded"
    else:
        health_status = "live"
    return {
        "status": health_status,
        "ok": health_status == "live",
        "reasons": reasons,
        "source_cockpit_attention_reasons": [
            str(reason) for reason in source_attention_reasons if reason
        ],
        "source_cockpit_attention_primary_reason": source_attention_primary_reason,
        "source_cockpit_attention_label": source_attention_label,
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
            payload = json.load(handle)
    except OSError as exc:
        return None, f"failed_to_read_state_file: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"invalid_state_json: line {exc.lineno} column {exc.colno}: {exc.msg}"
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
    if not path.exists():
        state["relay_startup"] = {
            "state_file": str(path),
            "state_load_status": "missing",
        }
        return state
    payload, error = read_json_with_error(path)
    if payload is None:
        state["relay_status"] = "state_load_failed"
        state["relay_startup"] = {
            "state_file": str(path),
            "state_load_status": "failed",
            "state_load_error": error,
        }
        return state
    state.update(payload)
    state["relay_startup"] = {
        "state_file": str(path),
        "state_load_status": "loaded",
    }
    return state


def save_state(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)


def encoded_json_size(payload: Any) -> int:
    return len(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def snapshot() -> dict[str, Any]:
    with STATE_LOCK:
        return json.loads(json.dumps(STATE))


def update_state(payload: dict[str, Any]) -> dict[str, Any]:
    received_at = utc_now()
    status = payload.get("status")
    if not isinstance(status, dict):
        status = {"status": "publisher_missing_status"}
    status = dict(status)
    status.setdefault("status", "unknown")
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
    if len(log_tail) > max_log_chars:
        log_tail = log_tail[-max_log_chars:]

    publisher = payload.get("publisher")
    if not isinstance(publisher, dict):
        publisher = {}
    publisher = dict(publisher)
    if payload.get("pushed_at"):
        publisher["pushed_at"] = payload["pushed_at"]

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
        return json.loads(json.dumps(STATE))


def relay_status_payload() -> dict[str, Any]:
    state = snapshot()
    status = state.get("status")
    if not isinstance(status, dict):
        status = {"status": "relay_waiting", "loop_running": False}
    status = dict(status)
    freshness = snapshot_freshness(state)
    health = cockpit_health(state, status, freshness)
    status["cockpit_health"] = health
    status["cockpit_status"] = health["status"]
    status["cockpit_ok"] = health["ok"]
    status["relay"] = {
        "status": state.get("relay_status", "waiting"),
        "received_at": state.get("received_at"),
        "updated_at": state.get("updated_at"),
        **freshness,
        "startup": state.get("relay_startup", {}),
        "publisher": state.get("publisher", {}),
    }
    return status


def health_payload() -> dict[str, Any]:
    state = snapshot()
    status = state.get("status")
    if not isinstance(status, dict):
        status = {"status": "relay_waiting", "loop_running": False}
    freshness = snapshot_freshness(state)
    health = cockpit_health(state, status, freshness)
    return {
        "ok": True,
        "service": "automoat-cockpit-relay",
        "cockpit_status": health["status"],
        "cockpit_ok": health["ok"],
        "cockpit_health": health,
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
) -> int | None:
    try:
        parsed = int(value)
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


def validate_relay_configuration(
    args: argparse.Namespace,
    env: os._Environ[str] | dict[str, str] | None = None,
) -> list[str]:
    env = env if env is not None else os.environ
    errors: list[str] = []
    if not str(env.get("AUTOMOAT_RELAY_TOKEN", "")).strip():
        errors.append("AUTOMOAT_RELAY_TOKEN is required")
    if not str(args.host).strip():
        errors.append("--host must not be empty")
    state_file = str(args.state_file).strip()
    if state_file:
        state_path = Path(state_file).expanduser()
        if state_path.exists() and state_path.is_dir():
            errors.append("--state-file must be a file path, not a directory")
        elif state_path.parent.exists() and not state_path.parent.is_dir():
            errors.append("--state-file parent must be a directory")

    port = parse_positive_int("--port", args.port, errors)
    if port is not None and port > 65535:
        errors.append("--port must be less than or equal to 65535")
    parse_positive_int(
        "--max-ingest-bytes",
        args.max_ingest_bytes,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_ingest_bytes"],
    )
    parse_positive_int(
        "--max-log-chars",
        args.max_log_chars,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_log_chars"],
    )
    parse_positive_int(
        "--max-status-bytes",
        args.max_status_bytes,
        errors,
        maximum=RELAY_CONFIG_LIMITS["max_status_bytes"],
    )
    parse_positive_int(
        "--stale-after-seconds",
        args.stale_after_seconds,
        errors,
        maximum=RELAY_CONFIG_LIMITS["stale_after_seconds"],
    )
    return errors


def emit_relay_preflight(args: argparse.Namespace) -> list[str]:
    errors = validate_relay_configuration(args)
    if errors:
        print("relay environment preflight failed", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return errors

    state_file = str(args.state_file).strip() or "memory-only"
    print(
        "relay environment preflight passed: "
        f"host={args.host} "
        f"port={int(args.port)} "
        f"state_file={state_file} "
        f"max_ingest_bytes={int(args.max_ingest_bytes)} "
        f"max_log_chars={int(args.max_log_chars)} "
        f"max_status_bytes={int(args.max_status_bytes)} "
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
        body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
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
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
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
        "--stale-after-seconds",
        default=os.environ.get("AUTOMOAT_RELAY_STALE_AFTER_SECONDS", str(DEFAULT_STALE_AFTER_SECONDS)),
        help="mark relay snapshots stale when they are older than this many seconds",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="validate relay startup configuration and exit without serving",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_relay_configuration(args)
    if args.check_env:
        return 2 if emit_relay_preflight(args) else 0
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
