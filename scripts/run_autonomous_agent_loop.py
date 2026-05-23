#!/usr/bin/env python3
"""Run bounded autonomous Codex iterations for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".automoat" / "logs"
RUNS_DIR = ROOT / ".automoat" / "runs"
STATE_DIR = ROOT / ".automoat" / "state"
DEFAULT_LOG_FILE = LOG_DIR / "mvp-loop.log"
STATUS_FILE = STATE_DIR / "mvp-loop-status.json"
PID_FILE = STATE_DIR / "mvp-loop.pid"

CONTRACT_PATH = ROOT / "generated/contracts/dallas-electrician-contract-summary-v1/summary.json"
COVERAGE_PATH = ROOT / "generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.json"
QUEUE_PATH = ROOT / "generated/workflows/dallas-inspection-workflow-v1/action-queue.json"
PIPELINE_SUMMARY_PATH = ROOT / "generated/pipeline/dallas-import-pipeline-summary-v1/summary.json"
HANDOFF_PATH = ROOT / ".pixelbox/handoff.md"
PREVIEW_PATH = ".pxcode/preview.json"

STOP_REQUESTED = False

AUTONOMOUS_PROMPT = """\
You are running inside the Autom oat autonomous loop.

Do exactly one bounded improvement for this repo, then stop. Read AGENTS.md and
.pixelbox/handoff.md first. Prefer NEXT_TASK.md, with the current priority being
operator-correction capture or the smallest adjacent improvement that makes the
Dallas permit-data MVP more executable.

Constraints:
- Do not ask the user questions.
- Do not run long-lived servers.
- Do not edit .pxcode/preview.json.
- Keep the product vision broad, with Dallas permit data as the MVP wedge.
- Update .automoat/logs/agent-journal.md and .pixelbox/handoff.md for any real change.
- If generated/landing.html changes, sync it to index.html.
- Run relevant deterministic checks.
- Do not commit or push; the autonomous loop supervisor will commit and push after you exit.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def emit(log_file: Path, message: str) -> None:
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def shell(command: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        timeout=timeout,
    )


def import_readiness_command() -> list[str]:
    return [
        sys.executable,
        "scripts/run_dallas_import_pipeline.py",
        "--summary-only",
        "--require-ready",
    ]


def latest_handoff_status() -> str:
    if not HANDOFF_PATH.exists():
        return "handoff missing"
    lines = HANDOFF_PATH.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("- status:"):
            return line.replace("- status:", "", 1).strip()
        if line.strip() == "## Latest":
            continue
        if index > 24:
            break
    return "handoff present"


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def import_pipeline_snapshot() -> dict[str, Any]:
    if not PIPELINE_SUMMARY_PATH.exists():
        return {
            "status": "missing",
            "summary_path": repo_path(PIPELINE_SUMMARY_PATH),
            "execution_readiness": {
                "status": "missing",
                "ready_for_next_import_records": False,
                "blockers": ["pipeline_summary_missing"],
            },
        }

    try:
        summary = read_json(PIPELINE_SUMMARY_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "summary_path": repo_path(PIPELINE_SUMMARY_PATH),
            "error": str(exc),
            "execution_readiness": {
                "status": "blocked",
                "ready_for_next_import_records": False,
                "blockers": ["pipeline_summary_invalid"],
            },
        }

    execution_readiness = summary.get("execution_readiness", {})
    if not isinstance(execution_readiness, dict):
        execution_readiness = {}
    contract = summary.get("contract", {})
    if not isinstance(contract, dict):
        contract = {}
    workflow = summary.get("workflow", {})
    if not isinstance(workflow, dict):
        workflow = {}
    coverage = summary.get("coverage", {})
    if not isinstance(coverage, dict):
        coverage = {}
    latest_import = summary.get("latest_import", {})
    if not isinstance(latest_import, dict):
        latest_import = {}

    return {
        "status": "loaded",
        "summary_id": summary.get("summary_id"),
        "dataset_id": summary.get("dataset_id"),
        "summary_path": repo_path(PIPELINE_SUMMARY_PATH),
        "execution_readiness": {
            "status": execution_readiness.get("status"),
            "ready_for_next_import_records": execution_readiness.get(
                "ready_for_next_import_records"
            ),
            "blockers": execution_readiness.get("blockers", []),
            "gates": execution_readiness.get("gates", {}),
            "next_step": execution_readiness.get("next_step"),
            "summary_only_require_ready_json_command": execution_readiness.get(
                "summary_only_require_ready_json_command"
            ),
        },
        "contract": {
            "overall_passed": contract.get("overall_passed"),
            "checks_passed": contract.get("checks_passed"),
            "checks_total": contract.get("checks_total"),
            "next_gap": contract.get("next_gap"),
        },
        "workflow": {
            "queue_items": workflow.get("queue_items"),
            "operator_corrections_captured": workflow.get(
                "operator_corrections_captured"
            ),
            "accepted_pattern_count": workflow.get("accepted_pattern_count"),
        },
        "coverage": {
            "latest_repeated_counts": coverage.get("latest_repeated_counts", {}),
            "latest_thin_counts": coverage.get("latest_thin_counts", {}),
            "thin_groups": coverage.get("thin_groups", {}),
        },
        "latest_import": {
            "counts": latest_import.get("counts", {}),
            "task_family_counts": latest_import.get("task_family_counts", {}),
        },
    }


def inspect_artifacts() -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    coverage = read_json(COVERAGE_PATH)
    queue = read_json(QUEUE_PATH)
    checks = contract.get("checks", [])
    passed_checks = sum(1 for check in checks if check.get("passed") is True)
    queue_summary = queue.get("summary", {})
    coverage_summary = coverage.get("summary", {})
    return {
        "contract": {
            "overall_passed": bool(contract.get("overall_passed")),
            "passed_checks": passed_checks,
            "total_checks": len(checks),
            "next_gap": contract.get("next_gap"),
        },
        "coverage": {
            "latest_dataset_id": coverage_summary.get("latest_dataset_id"),
            "repeated_counts": coverage_summary.get("latest_repeated_counts", {}),
            "thin_counts": coverage_summary.get("latest_thin_counts", {}),
            "recommended_next_step": coverage_summary.get("recommended_next_step"),
        },
        "workflow": {
            "queue_items": queue_summary.get("queue_items"),
            "priority_counts": queue_summary.get("priority_counts", {}),
            "recommended_action_counts": queue_summary.get("recommended_action_counts", {}),
        },
        "import_pipeline": import_pipeline_snapshot(),
    }


def git_status_lines() -> list[str]:
    return shell(["git", "status", "--short"]).stdout.splitlines()


def dirty_paths_excluding_preview() -> list[str]:
    paths: list[str] = []
    for line in git_status_lines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path and path != PREVIEW_PATH:
            paths.append(path)
    return paths


def git_state() -> dict[str, Any]:
    head = shell(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    branch = shell(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    dirty_paths = dirty_paths_excluding_preview()
    return {
        "branch": branch,
        "head": head,
        "dirty_paths": dirty_paths,
        "dirty_count_excluding_preview": len(dirty_paths),
    }


def status_payload(
    run_id: str,
    iteration: int,
    status: str,
    phase: str,
    started_at: str,
    steps: list[dict[str, Any]],
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "iteration": iteration,
        "status": status,
        "mode": "autonomous_codex",
        "phase": phase,
        "started_at": started_at,
        "updated_at": utc_now(),
        "steps": steps,
        "artifacts": inspect_artifacts(),
        "git": git_state(),
    }
    if error:
        payload["error"] = error
    return payload


def write_status(
    event_file: Path,
    run_id: str,
    iteration: int,
    status: str,
    phase: str,
    started_at: str,
    steps: list[dict[str, Any]],
    error: str | None = None,
) -> dict[str, Any]:
    payload = status_payload(run_id, iteration, status, phase, started_at, steps, error)
    write_json(STATUS_FILE, payload)
    with event_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def stream_command(
    log_file: Path,
    name: str,
    command: list[str],
    timeout: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    emit(log_file, f"step start: {name}")
    emit(log_file, "$ " + " ".join(command))
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )
    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    selector.register(process.stdout, selectors.EVENT_READ)
    timed_out = False
    while True:
        if STOP_REQUESTED:
            process.terminate()
        if timeout > 0 and time.monotonic() - started > timeout and process.poll() is None:
            timed_out = True
            process.terminate()
        for key, _events in selector.select(timeout=0.2):
            line = key.fileobj.readline()
            if line:
                emit(log_file, "  " + line.rstrip())
        if process.poll() is not None:
            remainder = process.stdout.read()
            if remainder:
                for line in remainder.splitlines():
                    emit(log_file, "  " + line)
            break
    elapsed = round(time.monotonic() - started, 3)
    exit_status = process.returncode
    if timed_out:
        exit_status = 124
        emit(log_file, f"step timeout: {name} seconds={timeout}")
    emit(log_file, f"step end: {name} status={exit_status} seconds={elapsed}")
    return {
        "name": name,
        "command": command,
        "exit_status": exit_status,
        "seconds": elapsed,
        "timed_out": timed_out,
    }


def run_check(log_file: Path, name: str, command: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    emit(log_file, f"step start: {name}")
    emit(log_file, "$ " + " ".join(command))
    result = shell(command)
    elapsed = round(time.monotonic() - started, 3)
    output = result.stdout.strip()
    if output:
        for line in output.splitlines()[-20:]:
            emit(log_file, "  " + line)
    emit(log_file, f"step end: {name} status={result.returncode} seconds={elapsed}")
    return {
        "name": name,
        "command": command,
        "exit_status": result.returncode,
        "seconds": elapsed,
    }


def sync_landing(log_file: Path) -> dict[str, Any]:
    if not (ROOT / "generated" / "landing.html").exists():
        return {
            "name": "sync landing",
            "command": ["cp", "generated/landing.html", "index.html"],
            "exit_status": 0,
            "seconds": 0,
            "skipped": True,
        }
    return run_check(log_file, "sync landing", ["cp", "generated/landing.html", "index.html"])


def publish_changes(log_file: Path, stamp: str) -> dict[str, Any]:
    paths = dirty_paths_excluding_preview()
    if not paths:
        emit(log_file, "publish skipped: no dirty paths excluding .pxcode/preview.json")
        return {
            "name": "publish changes",
            "command": ["git", "commit", "&&", "git", "push"],
            "exit_status": 0,
            "seconds": 0,
            "skipped": True,
        }
    add_command = ["git", "add", "-A", "--", *paths]
    commit_message = f"chore: autonomous loop update {stamp}"
    steps = [
        run_check(log_file, "stage autonomous changes", add_command),
        run_check(log_file, "commit autonomous changes", ["git", "commit", "-m", commit_message]),
        run_check(log_file, "push autonomous changes", ["git", "push", "origin", "main"]),
    ]
    failed = next((step for step in steps if step["exit_status"] != 0), None)
    return {
        "name": "publish changes",
        "command": ["git", "add/commit/push"],
        "exit_status": failed["exit_status"] if failed else 0,
        "seconds": round(sum(float(step.get("seconds", 0)) for step in steps), 3),
        "substeps": steps,
    }


def codex_command(prompt: str) -> list[str]:
    return [
        "codex",
        "exec",
        "-C",
        str(ROOT),
        "--sandbox",
        "danger-full-access",
        "--dangerously-bypass-approvals-and-sandbox",
        prompt,
    ]


def run_iteration(
    log_file: Path,
    event_file: Path,
    iteration: int,
    run_id: str,
    prompt: str,
    codex_timeout: float,
) -> dict[str, Any]:
    started_at = utc_now()
    stamp = run_stamp()
    steps: list[dict[str, Any]] = []
    emit(log_file, f"iteration {iteration} start run_id={run_id} mode=autonomous_codex")
    emit(log_file, f"handoff: {latest_handoff_status()}")
    write_status(event_file, run_id, iteration, "running", "codex_exec", started_at, steps)

    env = os.environ.copy()
    env["AUTOMOAT_AUTONOMOUS_LOOP"] = "1"
    codex_step = stream_command(log_file, "codex autonomous bounded improvement", codex_command(prompt), codex_timeout, env)
    steps.append(codex_step)
    if codex_step["exit_status"] != 0:
        payload = write_status(
            event_file,
            run_id,
            iteration,
            "failing",
            "codex_exec_failed",
            started_at,
            steps,
            f"codex exited with {codex_step['exit_status']}",
        )
        return payload

    steps.append(sync_landing(log_file))
    readiness_step = run_check(
        log_file,
        "refresh Dallas import readiness summary",
        import_readiness_command(),
    )
    steps.append(readiness_step)
    if readiness_step["exit_status"] != 0:
        payload = write_status(
            event_file,
            run_id,
            iteration,
            "failing",
            "import_readiness_failed",
            started_at,
            steps,
            "Dallas import execution readiness check failed",
        )
        emit(
            log_file,
            "iteration "
            f"{iteration} end status=failing phase=import_readiness_failed "
            f"dirty_paths_excluding_preview={payload['git']['dirty_count_excluding_preview']}",
        )
        return payload
    steps.append(run_check(log_file, "git diff check", ["git", "diff", "--check"]))
    steps.append(publish_changes(log_file, stamp))

    failed = next((step for step in steps if step.get("exit_status") != 0), None)
    status = "failing" if failed else "passing"
    phase = "failed" if failed else "published"
    payload = write_status(event_file, run_id, iteration, status, phase, started_at, steps)
    emit(
        log_file,
        "iteration "
        f"{iteration} end status={status} phase={phase} "
        f"dirty_paths_excluding_preview={payload['git']['dirty_count_excluding_preview']}",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=0, help="0 means run until stopped")
    parser.add_argument("--interval", type=float, default=300.0, help="seconds between autonomous iterations")
    parser.add_argument("--codex-timeout", type=float, default=1800.0, help="seconds before terminating one codex exec")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--prompt-file", type=Path, help="optional file containing the autonomous prompt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"autonomous-codex-{run_stamp()}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    event_file = run_dir / "events.jsonl"
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else AUTONOMOUS_PROMPT
    pid = os.getpid()
    PID_FILE.write_text(str(pid) + "\n", encoding="utf-8")
    emit(args.log_file, f"autonomous loop start run_id={run_id} pid={pid}")
    iteration = 0
    final_status = 0
    while not STOP_REQUESTED:
        iteration += 1
        payload = run_iteration(args.log_file, event_file, iteration, run_id, prompt, args.codex_timeout)
        if payload["status"] != "passing":
            final_status = 1
            if args.iterations == 0:
                emit(args.log_file, "autonomous loop stopping after failing iteration")
                break
        if args.iterations and iteration >= args.iterations:
            break
        sleep_until = time.monotonic() + max(args.interval, 0)
        while not STOP_REQUESTED and time.monotonic() < sleep_until:
            time.sleep(0.5)
    emit(args.log_file, f"autonomous loop stop run_id={run_id} iterations={iteration} status={final_status}")
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(pid):
            PID_FILE.unlink()
    except OSError:
        pass
    return final_status


if __name__ == "__main__":
    raise SystemExit(main())
