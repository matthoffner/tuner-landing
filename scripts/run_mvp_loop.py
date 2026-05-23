#!/usr/bin/env python3
"""Run a visible, deterministic MVP loop for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import json
import os
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
HANDOFF_PATH = ROOT / ".pixelbox/handoff.md"


STOP_REQUESTED = False


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_stop(signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def shell(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def run_step(log_file: Path, name: str, command: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    emit(log_file, f"step start: {name}")
    emit(log_file, "$ " + " ".join(command))
    result = shell(command)
    elapsed = round(time.monotonic() - started, 3)
    output = result.stdout.strip()
    if output:
        for line in output.splitlines()[-12:]:
            emit(log_file, "  " + line)
    emit(log_file, f"step end: {name} status={result.returncode} seconds={elapsed}")
    return {
        "name": name,
        "command": command,
        "exit_status": result.returncode,
        "seconds": elapsed,
    }


def latest_handoff_status() -> str:
    if not HANDOFF_PATH.exists():
        return "handoff missing"
    lines = HANDOFF_PATH.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("- status:"):
            return line.replace("- status:", "", 1).strip()
        if line.strip() == "## Latest":
            continue
        if index > 20:
            break
    return "handoff present"


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
            "operator_corrections": queue.get("operator_correction_summary", {}),
        },
    }


def git_state() -> dict[str, Any]:
    head = shell(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    branch = shell(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    status_lines = shell(["git", "status", "--short"]).stdout.splitlines()
    interesting = [
        line
        for line in status_lines
        if not line.strip().endswith(".pxcode/preview.json")
    ]
    return {
        "branch": branch,
        "head": head,
        "dirty_paths": interesting,
        "dirty_count_excluding_preview": len(interesting),
    }


def append_event(event_file: Path, payload: dict[str, Any]) -> None:
    with event_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def run_iteration(
    log_file: Path,
    event_file: Path,
    iteration: int,
    run_id: str,
) -> dict[str, Any]:
    started_at = utc_now()
    emit(log_file, f"iteration {iteration} start run_id={run_id}")
    emit(log_file, f"handoff: {latest_handoff_status()}")
    steps = [
        run_step(
            log_file,
            "regenerate Dallas contract summary",
            [sys.executable, "scripts/generate_dallas_contract_summary.py"],
        ),
        run_step(
            log_file,
            "regenerate Dallas edge-case coverage",
            [sys.executable, "scripts/generate_dallas_edge_case_coverage.py"],
        ),
        run_step(
            log_file,
            "regenerate Dallas inspection workflow",
            [sys.executable, "scripts/generate_dallas_inspection_workflow.py"],
        ),
    ]
    artifacts = inspect_artifacts()
    git = git_state()
    failed_steps = [step for step in steps if step["exit_status"] != 0]
    contract_ok = artifacts["contract"]["overall_passed"] is True
    status = "passing" if not failed_steps and contract_ok else "failing"
    ended_at = utc_now()
    payload = {
        "run_id": run_id,
        "iteration": iteration,
        "status": status,
        "started_at": started_at,
        "updated_at": ended_at,
        "steps": steps,
        "artifacts": artifacts,
        "git": git,
    }
    write_json(STATUS_FILE, payload)
    append_event(event_file, payload)
    emit(
        log_file,
        "iteration "
        f"{iteration} end status={status} "
        f"contract={artifacts['contract']['passed_checks']}/{artifacts['contract']['total_checks']} "
        f"queue_items={artifacts['workflow']['queue_items']} "
        f"dirty_paths_excluding_preview={git['dirty_count_excluding_preview']}",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="number of iterations to run; 0 means run until stopped",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=8.0,
        help="seconds to sleep between iterations",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=DEFAULT_LOG_FILE,
        help="loop log file to append",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"mvp-cockpit-{run_stamp()}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    event_file = run_dir / "events.jsonl"
    pid = os.getpid()
    PID_FILE.write_text(str(pid) + "\n", encoding="utf-8")
    emit(args.log_file, f"mvp loop start run_id={run_id} pid={pid}")
    iteration = 0
    final_status = 0
    while not STOP_REQUESTED:
        iteration += 1
        try:
            payload = run_iteration(args.log_file, event_file, iteration, run_id)
            if payload["status"] != "passing":
                final_status = 1
        except Exception as exc:
            final_status = 1
            payload = {
                "run_id": run_id,
                "iteration": iteration,
                "status": "error",
                "updated_at": utc_now(),
                "error": str(exc),
            }
            write_json(STATUS_FILE, payload)
            append_event(event_file, payload)
            emit(args.log_file, f"iteration {iteration} error: {exc}")
        if args.iterations and iteration >= args.iterations:
            break
        sleep_until = time.monotonic() + max(args.interval, 0)
        while not STOP_REQUESTED and time.monotonic() < sleep_until:
            time.sleep(0.2)
    emit(args.log_file, f"mvp loop stop run_id={run_id} iterations={iteration} status={final_status}")
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(pid):
            PID_FILE.unlink()
    except OSError:
        pass
    return final_status


if __name__ == "__main__":
    raise SystemExit(main())
