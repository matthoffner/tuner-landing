#!/usr/bin/env python3
"""Serve a local cockpit that starts and streams the MVP loop."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = ROOT / ".automoat" / "logs" / "mvp-loop.log"
STATUS_FILE = ROOT / ".automoat" / "state" / "mvp-loop-status.json"
PID_FILE = ROOT / ".automoat" / "state" / "mvp-loop.pid"

LOOP_PROCESS: subprocess.Popen[str] | None = None
LOOP_LOCK = threading.Lock()
SERVER_CONFIG: dict[str, float | int | str] = {"iterations": 0, "interval": 8.0, "loop_mode": "mvp"}
SERVER_CONFIG["read_only"] = 0


def tail_lines(path: Path, limit: int = 160) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-limit:]


def read_status() -> dict[str, object]:
    if STATUS_FILE.exists():
        try:
            status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = {"status": "invalid-status-json"}
    else:
        status = {"status": "waiting", "updated_at": None}
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
            <div class="links">
              <a href="/.automoat/logs/mvp-loop.log">raw loop log</a>
              <a href="/.automoat/state/mvp-loop-status.json">status json</a>
              <a href="/generated/contracts/dallas-electrician-contract-summary-v1/summary.md">contract summary</a>
              <a href="/generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md">coverage report</a>
              <a href="/generated/workflows/dallas-inspection-workflow-v1/index.html">action queue</a>
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

      async function post(path) {{
        const response = await fetch(path, {{ method: "POST" }});
        await refreshStatus();
        return response.text();
      }}

      async function refreshStatus() {{
        const response = await fetch("/api/status", {{ cache: "no-store" }});
        const status = await response.json();
        summary.textContent = `Current status: ${{status.status || "waiting"}}`;
        loop.textContent = status.loop_running ? `running #${{status.loop_pid}}` : "stopped";
        iteration.textContent = status.iteration || "0";
        const checks = status.artifacts?.contract;
        contract.textContent = checks ? `${{checks.passed_checks}}/${{checks.total_checks}}` : "...";
        queue.textContent = status.artifacts?.workflow?.queue_items || "...";
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
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

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
