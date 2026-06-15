#!/usr/bin/env python3
"""Run bounded autonomous Codex iterations for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


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
.pixelbox/handoff.md first. Use NEXT_TASK.md for context, but choose the highest
leverage improvement for the autonomous product.

Task policy:
- If the Dallas import pipeline is already ready and coverage has no thin groups,
  do not append another synthetic `ELZ-*` row to the example.local Dallas CSV
  fixtures. That work is low-leverage and will be rejected by the supervisor.
- Updating README, NEXT_TASK, the landing page, the journal, or the handoff to
  describe that fixture append does not make it higher-leverage work.
- Prefer autonomy, cockpit visibility, Render worker reliability, policy/checking,
  product clarity, real-data ingestion mechanics, or tests that make the agent
  more useful and inspectable.
- Only edit raw Dallas CSV rows when fixing a broken readiness gate, adding a new
  documented edge case/source type, or wiring a real import path. Explain why the
  data change is not just another hidden fixture row.

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

PRODUCTIVE_CHANGE_PREFIXES = (
    "api/",
    "scripts/",
    "tests/",
)
PRODUCTIVE_CHANGE_FILES = {
    "AGENTS.md",
    "Dockerfile",
    "implementation-spec.md",
    "schema.md",
    "evals.md",
    "discovery-artifacts.md",
    "vision.md",
    "use-cases.md",
    "mvp.md",
    "render.yaml",
}
DALLAS_RAW_CSV_PREFIX = "generated/raw/dallas-electrician-import-sample-"
DALLAS_RAW_CSV_DIFF_PATHSPEC = (
    ":(glob)generated/raw/dallas-electrician-import-sample-*/*.csv"
)
MAX_POLICY_DETAIL_SAMPLES = 5
MAX_POLICY_DETAIL_CHARS = 240
MAX_POLICY_LIST_ITEMS = 8
MAX_ARTIFACT_HEALTH_DETAILS = 8
MAX_ARTIFACT_HEALTH_DETAIL_CHARS = 240
URL_TOKEN_PATTERN = re.compile(r"https?://[^\s,]+", re.IGNORECASE)
TOKEN_ASSIGNMENT_PATTERN = re.compile(
    r"\b([A-Za-z0-9_-]*(?:token|secret|password|api[_-]?key|access[_-]?key)"
    r"[A-Za-z0-9_-]*)=([^,\s;]+)",
    re.IGNORECASE,
)


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
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.write("\n")


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_json_constant)


def artifact_error(status: str, path: Path, error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_status": status,
        "artifact_path": repo_path(path),
    }
    if error:
        payload["artifact_error"] = error
    return payload


def read_json_artifact(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        payload = read_json(path)
    except FileNotFoundError:
        return {}, artifact_error("missing", path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, artifact_error("invalid", path, str(exc))
    if not isinstance(payload, dict):
        return {}, artifact_error("invalid", path, "artifact JSON must be an object")
    return payload, artifact_error("loaded", path)


def bounded_artifact_health_detail(value: Any) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    if len(text) > MAX_ARTIFACT_HEALTH_DETAIL_CHARS:
        return text[: MAX_ARTIFACT_HEALTH_DETAIL_CHARS - 3] + "..."
    return text


def artifact_degradation_details(
    artifact_statuses: dict[str, Any],
    artifact_details: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    for name, status in artifact_statuses.items():
        if status == "loaded":
            continue
        detail = {
            "name": bounded_artifact_health_detail(name),
            "status": bounded_artifact_health_detail(status or "unknown"),
        }
        source = artifact_details.get(name, {})
        reason = source.get("artifact_error")
        if name == "import_pipeline":
            reason = source.get("error")
            if not reason and status == "missing":
                reason = "pipeline_summary_missing"
            elif not reason and status == "invalid":
                reason = "pipeline_summary_invalid"
            elif not reason:
                reason = "pipeline_status_unavailable"
        elif not reason and status == "missing":
            reason = f"{name}_artifact_missing"
        elif not reason and status == "invalid":
            reason = f"{name}_artifact_invalid"
        if reason:
            detail["reason"] = bounded_artifact_health_detail(reason)
        details.append(detail)
    return details[:MAX_ARTIFACT_HEALTH_DETAILS]


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
    except (OSError, ValueError, json.JSONDecodeError) as exc:
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
    contract, contract_artifact = read_json_artifact(CONTRACT_PATH)
    coverage, coverage_artifact = read_json_artifact(COVERAGE_PATH)
    queue, queue_artifact = read_json_artifact(QUEUE_PATH)
    checks = contract.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    passed_checks = sum(
        1 for check in checks if isinstance(check, dict) and check.get("passed") is True
    )
    queue_summary = queue.get("summary", {})
    if not isinstance(queue_summary, dict):
        queue_summary = {}
    coverage_summary = coverage.get("summary", {})
    if not isinstance(coverage_summary, dict):
        coverage_summary = {}
    import_pipeline = import_pipeline_snapshot()
    artifact_statuses = {
        "contract": contract_artifact["artifact_status"],
        "coverage": coverage_artifact["artifact_status"],
        "workflow": queue_artifact["artifact_status"],
        "import_pipeline": import_pipeline.get("status"),
    }
    artifact_details = {
        "contract": contract_artifact,
        "coverage": coverage_artifact,
        "workflow": queue_artifact,
        "import_pipeline": import_pipeline,
    }
    degraded_artifacts = [
        name for name, status in artifact_statuses.items() if status != "loaded"
    ]
    degradation_details = artifact_degradation_details(
        artifact_statuses,
        artifact_details,
    )
    return {
        "artifact_health": {
            "status": (
                "loaded"
                if all(status == "loaded" for status in artifact_statuses.values())
                else "degraded"
            ),
            "statuses": artifact_statuses,
            "degraded_artifacts": degraded_artifacts,
            "degraded_artifact_count": len(degraded_artifacts),
            "degradation_details": degradation_details,
        },
        "contract": {
            **contract_artifact,
            "overall_passed": bool(contract.get("overall_passed")),
            "passed_checks": passed_checks,
            "total_checks": len(checks),
            "next_gap": contract.get("next_gap"),
        },
        "coverage": {
            **coverage_artifact,
            "latest_dataset_id": coverage_summary.get("latest_dataset_id"),
            "repeated_counts": coverage_summary.get("latest_repeated_counts", {}),
            "thin_counts": coverage_summary.get("latest_thin_counts", {}),
            "recommended_next_step": coverage_summary.get("recommended_next_step"),
        },
        "workflow": {
            **queue_artifact,
            "queue_items": queue_summary.get("queue_items"),
            "priority_counts": queue_summary.get("priority_counts", {}),
            "recommended_action_counts": queue_summary.get("recommended_action_counts", {}),
        },
        "import_pipeline": import_pipeline,
    }


def artifact_health_loaded(artifacts: dict[str, Any]) -> bool:
    artifact_health = artifacts.get("artifact_health", {})
    return (
        isinstance(artifact_health, dict)
        and artifact_health.get("status") == "loaded"
    )


def git_status_lines() -> list[str]:
    return shell(["git", "status", "--porcelain=v1"]).stdout.splitlines()


def dirty_paths() -> list[str]:
    paths: list[str] = []
    for line in git_status_lines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            paths.append(path)
    return paths


def dirty_paths_excluding_preview() -> list[str]:
    return [path for path in dirty_paths() if path != PREVIEW_PATH]


def preview_json_changed(paths: list[str] | None = None) -> bool:
    """Return whether the Pixelbox preview file is dirty in the current diff."""
    return PREVIEW_PATH in (dirty_paths() if paths is None else paths)


def changed_paths_include_productive_work(paths: list[str]) -> bool:
    """Return whether a synthetic row append is paired with durable product work."""
    return bool(productive_changed_paths(paths))


def productive_changed_paths(paths: list[str]) -> list[str]:
    """Return changed paths that count as durable product companion work."""
    productive_paths: list[str] = []
    for path in paths:
        if path in PRODUCTIVE_CHANGE_FILES:
            productive_paths.append(path)
        elif path.startswith(PRODUCTIVE_CHANGE_PREFIXES):
            productive_paths.append(path)
    return sorted(set(productive_paths))


def changed_dallas_raw_csv_paths(paths: list[str]) -> list[str]:
    """Return raw Dallas CSV fixture paths changed in the current diff."""
    return sorted(
        {
            path
            for path in paths
            if path.startswith(DALLAS_RAW_CSV_PREFIX) and path.endswith(".csv")
        }
    )


def synthetic_dallas_csv_row(row: str) -> bool:
    """Return whether a raw CSV row is hidden Dallas example.local fixture growth."""
    return "example.local/dallas/" in row and (
        "ELZ-2026-" in row or ",ELZ-2026-" not in row
    )


def sanitized_policy_detail(text: str) -> str:
    """Return a bounded, secret-safe detail string for policy status payloads."""

    def sanitize_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        try:
            parsed = urlsplit(raw_url)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            return "<redacted-url>"
        if not host:
            return "<redacted-url>"
        netloc = host
        if port is not None:
            netloc += f":{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

    sanitized = URL_TOKEN_PATTERN.sub(sanitize_url, text)
    sanitized = TOKEN_ASSIGNMENT_PATTERN.sub(r"\1=<redacted>", sanitized)
    sanitized = sanitized.replace("\r", " ").replace("\n", " ")
    if len(sanitized) > MAX_POLICY_DETAIL_CHARS:
        return sanitized[: MAX_POLICY_DETAIL_CHARS - 3] + "..."
    return sanitized


def bounded_sanitized_policy_list(values: list[Any]) -> list[str]:
    """Return a bounded list of secret-safe policy detail values."""
    return [
        sanitized_policy_detail(str(value))
        for value in values[:MAX_POLICY_LIST_ITEMS]
    ]


def sanitized_policy_scalar(value: Any) -> Any:
    """Return a secret-safe scalar policy value while preserving missing values."""
    if value is None:
        return None
    return sanitized_policy_detail(str(value))


def synthetic_dallas_row_samples(rows: list[str]) -> list[str]:
    """Return bounded, sanitized synthetic row examples for cockpit diagnostics."""
    return [
        sanitized_policy_detail(row)
        for row in rows[:MAX_POLICY_DETAIL_SAMPLES]
    ]


def untracked_dallas_raw_csv_paths() -> list[str]:
    """Return untracked raw Dallas CSV fixture paths that policy checks must scan."""
    result = shell(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            DALLAS_RAW_CSV_DIFF_PATHSPEC,
        ]
    )
    return sorted(path for path in result.stdout.splitlines() if path.strip())


def added_synthetic_rows_from_diff(diff_output: str) -> list[str]:
    rows: list[str] = []
    for line in diff_output.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        row = line[1:]
        if synthetic_dallas_csv_row(row):
            rows.append(row)
    return rows


def added_synthetic_dallas_rows() -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()

    def append_row(row: str) -> None:
        if row not in seen:
            rows.append(row)
            seen.add(row)

    for command in (
        ["git", "diff", "--", DALLAS_RAW_CSV_DIFF_PATHSPEC],
        ["git", "diff", "--cached", "--", DALLAS_RAW_CSV_DIFF_PATHSPEC],
    ):
        result = shell(command)
        for row in added_synthetic_rows_from_diff(result.stdout):
            append_row(row)

    for relative_path in untracked_dallas_raw_csv_paths():
        path = ROOT / relative_path
        try:
            file_rows = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_number, row in enumerate(file_rows, start=1):
            if synthetic_dallas_csv_row(row):
                append_row(f"{relative_path}:{line_number}: {row}")
    return rows


def synthetic_dallas_appends_allowed_by_policy() -> bool:
    snapshot = autonomy_policy_snapshot()
    return snapshot.get("synthetic_example_local_dallas_appends_allowed") is True


def autonomy_policy_snapshot() -> dict[str, Any]:
    import_pipeline = import_pipeline_snapshot()
    readiness = import_pipeline.get("execution_readiness", {})
    coverage = import_pipeline.get("coverage", {})
    thin_groups = coverage.get("thin_groups", {})
    if not isinstance(readiness, dict):
        readiness = {}
    if not isinstance(thin_groups, dict):
        thin_groups = {}
    raw_blockers = readiness.get("blockers", [])
    blockers = raw_blockers if isinstance(raw_blockers, list) else []
    thin_group_count = sum(
        len(value) for value in thin_groups.values() if isinstance(value, list)
    )
    raw_thin_group_categories = sorted(
        key for key, value in thin_groups.items() if isinstance(value, list) and value
    )
    ready = (
        readiness.get("ready_for_next_import_records") is True
        and readiness.get("status") == "ready"
        and thin_group_count == 0
    )
    if ready:
        decision_reason = "dallas_ready_no_thin_groups"
    elif thin_group_count:
        decision_reason = "coverage_thin_groups_present"
    else:
        decision_reason = "import_readiness_not_ready"
    return {
        "current_focus": (
            "autonomy_visibility_or_real_ingest"
            if ready
            else "fix_import_readiness_blockers"
        ),
        "decision_reason": decision_reason,
        "dallas_pipeline_ready": ready,
        "readiness_status": sanitized_policy_scalar(readiness.get("status")),
        "ready_for_next_import_records": readiness.get("ready_for_next_import_records"),
        "readiness_blocker_count": len(blockers),
        "readiness_blockers": bounded_sanitized_policy_list(blockers),
        "synthetic_example_local_dallas_appends_allowed": False,
        "thin_group_count": thin_group_count,
        "thin_group_category_count": len(raw_thin_group_categories),
        "thin_group_categories": bounded_sanitized_policy_list(raw_thin_group_categories),
        "policy": (
            "When Dallas readiness is already green, do not append another "
            "synthetic ELZ fixture row unless paired with a real product, "
            "ingestion, autonomy, reliability, test, or durable spec "
            "improvement. Routine README, NEXT_TASK, landing, journal, or "
            "handoff refreshes do not count as that companion work."
        ),
    }


def build_iteration_prompt(base_prompt: str) -> str:
    policy = json.dumps(autonomy_policy_snapshot(), indent=2, sort_keys=True)
    return (
        base_prompt.rstrip()
        + "\n\nCurrent supervisor policy snapshot:\n"
        + policy
        + "\n\nChoose work that satisfies this policy snapshot.\n"
    )


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
        "autonomy_policy": autonomy_policy_snapshot(),
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
        handle.write(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")
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


def run_autonomy_policy_check(log_file: Path) -> dict[str, Any]:
    started = time.monotonic()
    name = "autonomy policy check"
    emit(log_file, f"step start: {name}")
    all_paths = dirty_paths()
    paths = dirty_paths_excluding_preview()
    preview_changed = preview_json_changed(all_paths)
    raw_csv_paths = changed_dallas_raw_csv_paths(paths)
    synthetic_rows = added_synthetic_dallas_rows()
    synthetic_row_samples = synthetic_dallas_row_samples(synthetic_rows)
    productive_paths = productive_changed_paths(paths)
    productive_change = bool(productive_paths)
    policy_snapshot = autonomy_policy_snapshot()
    policy_allows_synthetic_append = (
        policy_snapshot.get("synthetic_example_local_dallas_appends_allowed") is True
    )
    allow_override = os.environ.get("AUTOMOAT_ALLOW_SYNTHETIC_DALLAS_APPEND") == "1"
    exit_status = 0
    failure_reason = None
    if preview_changed:
        exit_status = 1
        failure_reason = "preview_json_changed"
        emit(
            log_file,
            "policy violation: .pxcode/preview.json is dirty; autonomous "
            "iterations must not edit Pixelbox preview metadata",
        )
    elif synthetic_rows and not policy_allows_synthetic_append and not allow_override:
        exit_status = 1
        failure_reason = "synthetic_append_disallowed_by_snapshot"
        emit(
            log_file,
            "policy violation: supervisor snapshot disallows synthetic Dallas "
            "example.local row appends for the current readiness state",
        )
        for row in synthetic_row_samples:
            emit(log_file, "  synthetic row: " + row)
    elif raw_csv_paths and not productive_change and not (
        synthetic_rows and allow_override
    ):
        exit_status = 1
        failure_reason = "raw_dallas_csv_without_productive_work"
        emit(
            log_file,
            "policy violation: raw Dallas CSV edits require code, ingest, infra, "
            "test, or durable spec companion work when the Dallas readiness gate "
            "is already green",
        )
        for path in raw_csv_paths[:8]:
            emit(log_file, "  raw csv path: " + path)
    elif synthetic_rows and not productive_change and not allow_override:
        exit_status = 1
        failure_reason = "synthetic_append_without_productive_work"
        emit(
            log_file,
            "policy violation: synthetic Dallas example.local row append without "
            "code, ingest, infra, test, or durable spec companion work",
        )
        for row in synthetic_row_samples:
            emit(log_file, "  synthetic row: " + row)
    else:
        emit(
            log_file,
            "policy ok: "
            f"synthetic_rows={len(synthetic_rows)} "
            f"raw_dallas_csv_paths={len(raw_csv_paths)} "
            f"productive_change={productive_change} "
            f"productive_paths={len(productive_paths)} "
            f"policy_allows_synthetic_append={policy_allows_synthetic_append} "
            f"override={allow_override}",
        )
    elapsed = round(time.monotonic() - started, 3)
    emit(log_file, f"step end: {name} status={exit_status} seconds={elapsed}")
    policy_diagnostics = autonomy_policy_diagnostics(
        exit_status=exit_status,
        failure_reason=failure_reason,
        preview_changed=preview_changed,
        synthetic_row_count=len(synthetic_rows),
        raw_csv_path_count=len(raw_csv_paths),
        productive_path_count=len(productive_paths),
        policy_allows_synthetic_append=policy_allows_synthetic_append,
        allow_override=allow_override,
        policy_snapshot=policy_snapshot,
        dirty_paths_excluding_preview=paths,
        raw_csv_paths=raw_csv_paths,
        productive_paths=productive_paths,
        synthetic_row_samples=synthetic_row_samples,
    )
    return {
        "name": name,
        "command": ["internal", "autonomy_policy_check"],
        "exit_status": exit_status,
        "seconds": elapsed,
        "dirty_paths": all_paths,
        "dirty_paths_excluding_preview": paths,
        "preview_json_changed": preview_changed,
        "synthetic_row_count": len(synthetic_rows),
        "synthetic_row_samples": synthetic_row_samples,
        "raw_dallas_csv_changed_paths": raw_csv_paths,
        "productive_change": productive_change,
        "productive_changed_paths": productive_paths,
        "policy_allows_synthetic_append": policy_allows_synthetic_append,
        "policy_override": allow_override,
        "policy_snapshot": policy_snapshot,
        "policy_diagnostics": policy_diagnostics,
        "failure_reason": failure_reason,
    }


def autonomy_policy_diagnostics(
    *,
    exit_status: int,
    failure_reason: str | None,
    preview_changed: bool,
    synthetic_row_count: int,
    raw_csv_path_count: int,
    productive_path_count: int,
    policy_allows_synthetic_append: bool,
    allow_override: bool,
    policy_snapshot: dict[str, Any],
    dirty_paths_excluding_preview: list[str] | None = None,
    raw_csv_paths: list[str] | None = None,
    productive_paths: list[str] | None = None,
    synthetic_row_samples: list[str] | None = None,
) -> dict[str, Any]:
    """Return compact routeable details for the policy step status payload."""
    return {
        "status": "passed" if exit_status == 0 else "failed",
        "failure_reason": failure_reason,
        "route_hint": autonomy_policy_route_hint(failure_reason),
        "decision_reason": sanitized_policy_scalar(
            policy_snapshot.get("decision_reason")
        ),
        "current_focus": sanitized_policy_scalar(policy_snapshot.get("current_focus")),
        "preview_json_changed": preview_changed,
        "synthetic_row_count": synthetic_row_count,
        "raw_dallas_csv_changed_path_count": raw_csv_path_count,
        "productive_changed_path_count": productive_path_count,
        "policy_allows_synthetic_append": policy_allows_synthetic_append,
        "policy_override": allow_override,
        "dirty_path_samples": bounded_sanitized_policy_list(
            dirty_paths_excluding_preview or []
        ),
        "raw_dallas_csv_changed_path_samples": bounded_sanitized_policy_list(
            raw_csv_paths or []
        ),
        "productive_changed_path_samples": bounded_sanitized_policy_list(
            productive_paths or []
        ),
        "synthetic_row_samples": bounded_sanitized_policy_list(
            synthetic_row_samples or []
        ),
    }


def autonomy_policy_route_hint(failure_reason: str | None) -> str:
    if failure_reason == "preview_json_changed":
        return "pixelbox_preview_metadata"
    if failure_reason == "synthetic_append_disallowed_by_snapshot":
        return "dallas_synthetic_fixture_growth_disallowed"
    if failure_reason == "raw_dallas_csv_without_productive_work":
        return "dallas_raw_fixture_without_productive_companion"
    if failure_reason == "synthetic_append_without_productive_work":
        return "dallas_synthetic_fixture_without_productive_companion"
    if failure_reason:
        return "policy_failure"
    return "ok"


def autonomy_policy_error_message(policy_step: dict[str, Any]) -> str:
    reason = policy_step.get("failure_reason")
    synthetic_count = int(policy_step.get("synthetic_row_count") or 0)
    raw_paths = policy_step.get("raw_dallas_csv_changed_paths")
    if not isinstance(raw_paths, list):
        raw_paths = []
    raw_path_summary = ", ".join(str(path) for path in raw_paths[:5])
    if len(raw_paths) > 5:
        raw_path_summary += f", +{len(raw_paths) - 5} more"

    if reason == "synthetic_append_disallowed_by_snapshot":
        return (
            "Autonomy policy rejected "
            f"{synthetic_count} synthetic Dallas example.local row append(s): "
            "the supervisor snapshot disallows hidden fixture growth while "
            "Dallas readiness is already green."
        )
    if reason == "raw_dallas_csv_without_productive_work":
        suffix = f": {raw_path_summary}" if raw_path_summary else "."
        return (
            "Autonomy policy rejected raw Dallas CSV edits without code, ingest, "
            "infra, test, or durable spec companion work"
            + suffix
        )
    if reason == "synthetic_append_without_productive_work":
        return (
            "Autonomy policy rejected a synthetic Dallas example.local row append "
            "without code, ingest, infra, test, or durable spec companion work."
        )
    if reason == "preview_json_changed":
        return (
            "Autonomy policy rejected changes to .pxcode/preview.json; Pixelbox "
            "preview metadata must stay untouched by autonomous iterations."
        )
    return "Autonomy policy rejected the current diff."


def run_artifact_health_check(log_file: Path) -> dict[str, Any]:
    started = time.monotonic()
    name = "cockpit artifact health check"
    emit(log_file, f"step start: {name}")
    artifacts = inspect_artifacts()
    artifact_health = artifacts.get("artifact_health", {})
    if not isinstance(artifact_health, dict):
        artifact_health = {}
    health_status = artifact_health.get("status")
    statuses = artifact_health.get("statuses", {})
    if not isinstance(statuses, dict):
        statuses = {}
    degraded_artifacts = artifact_health.get("degraded_artifacts", [])
    if not isinstance(degraded_artifacts, list):
        degraded_artifacts = []
    if not degraded_artifacts:
        degraded_artifacts = [
            name for name, status in statuses.items() if status != "loaded"
        ]
    degradation_details = artifact_health.get("degradation_details", [])
    if not isinstance(degradation_details, list):
        degradation_details = []
    exit_status = 0 if artifact_health_loaded(artifacts) else 1
    emit(
        log_file,
        "artifact health: "
        f"status={health_status} "
        f"statuses={json.dumps(statuses, sort_keys=True)} "
        f"degraded_artifacts={json.dumps(degraded_artifacts)} "
        f"degradation_details={json.dumps(degradation_details, sort_keys=True)}",
    )
    elapsed = round(time.monotonic() - started, 3)
    emit(log_file, f"step end: {name} status={exit_status} seconds={elapsed}")
    return {
        "name": name,
        "command": ["internal", "cockpit_artifact_health_check"],
        "exit_status": exit_status,
        "seconds": elapsed,
        "artifact_health_status": health_status,
        "artifact_statuses": statuses,
        "degraded_artifacts": degraded_artifacts,
        "degradation_details": degradation_details,
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
    iteration_prompt = build_iteration_prompt(prompt)
    codex_step = stream_command(log_file, "codex autonomous bounded improvement", codex_command(iteration_prompt), codex_timeout, env)
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

    landing_step = sync_landing(log_file)
    steps.append(landing_step)
    if landing_step["exit_status"] != 0:
        payload = write_status(
            event_file,
            run_id,
            iteration,
            "failing",
            "landing_sync_failed",
            started_at,
            steps,
            "Landing page sync failed",
        )
        emit(
            log_file,
            "iteration "
            f"{iteration} end status=failing phase=landing_sync_failed "
            f"dirty_paths_excluding_preview={payload['git']['dirty_count_excluding_preview']}",
        )
        return payload

    policy_step = run_autonomy_policy_check(log_file)
    steps.append(policy_step)
    if policy_step["exit_status"] != 0:
        payload = write_status(
            event_file,
            run_id,
            iteration,
            "failing",
            "autonomy_policy_failed",
            started_at,
            steps,
            autonomy_policy_error_message(policy_step),
        )
        emit(
            log_file,
            "iteration "
            f"{iteration} end status=failing phase=autonomy_policy_failed "
            f"dirty_paths_excluding_preview={payload['git']['dirty_count_excluding_preview']}",
        )
        return payload

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
    artifact_step = run_artifact_health_check(log_file)
    steps.append(artifact_step)
    if artifact_step["exit_status"] != 0:
        payload = write_status(
            event_file,
            run_id,
            iteration,
            "failing",
            "artifact_health_failed",
            started_at,
            steps,
            "Cockpit artifact health is degraded after readiness refresh",
        )
        emit(
            log_file,
            "iteration "
            f"{iteration} end status=failing phase=artifact_health_failed "
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
