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


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_state(path: Path | None) -> dict[str, Any]:
    if path is None:
        return empty_state()
    payload = read_json(path)
    if payload is None:
        return empty_state()
    state = empty_state()
    state.update(payload)
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
        STATE.clear()
        STATE.update(next_state)
        save_state(CONFIG.get("state_file"), STATE)
        return json.loads(json.dumps(STATE))


def relay_status_payload() -> dict[str, Any]:
    state = snapshot()
    status = state.get("status")
    if not isinstance(status, dict):
        status = {"status": "relay_waiting", "loop_running": False}
    status = dict(status)
    status["relay"] = {
        "status": state.get("relay_status", "waiting"),
        "received_at": state.get("received_at"),
        "updated_at": state.get("updated_at"),
        "publisher": state.get("publisher", {}),
    }
    return status


def health_payload() -> dict[str, Any]:
    state = snapshot()
    return {
        "ok": True,
        "service": "automoat-cockpit-relay",
        "relay_status": state.get("relay_status", "waiting"),
        "has_snapshot": bool(state.get("received_at")),
        "received_at": state.get("received_at"),
    }


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "AutomoatRelay/0.1"

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
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
        token = str(CONFIG.get("token") or "")
        if not token:
            return False, "AUTOMOAT_RELAY_TOKEN is not configured on the relay"
        header_token = self.headers.get("X-Automoat-Relay-Token", "").strip()
        auth = self.headers.get("Authorization", "").strip()
        bearer = ""
        if auth.lower().startswith("bearer "):
            bearer = auth[7:].strip()
        if token in {header_token, bearer}:
            return True, ""
        return False, "invalid relay token"

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
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "4180")))
    parser.add_argument(
        "--state-file",
        default=os.environ.get("AUTOMOAT_RELAY_STATE_FILE", "/tmp/automoat-relay-state.json"),
        help="path for the latest snapshot; use an empty string for memory-only",
    )
    parser.add_argument(
        "--max-ingest-bytes",
        type=int,
        default=int(os.environ.get("AUTOMOAT_RELAY_MAX_BYTES", str(1024 * 1024))),
    )
    parser.add_argument(
        "--max-log-chars",
        type=int,
        default=int(os.environ.get("AUTOMOAT_RELAY_MAX_LOG_CHARS", str(160 * 1024))),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_file = Path(args.state_file).expanduser() if args.state_file else None
    CONFIG.update(
        {
            "token": os.environ.get("AUTOMOAT_RELAY_TOKEN", ""),
            "state_file": state_file,
            "max_ingest_bytes": args.max_ingest_bytes,
            "max_log_chars": args.max_log_chars,
        }
    )
    with STATE_LOCK:
        STATE.clear()
        STATE.update(load_state(state_file))

    server = ThreadingHTTPServer((args.host, args.port), RelayHandler)
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
