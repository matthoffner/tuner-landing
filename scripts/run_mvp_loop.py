#!/usr/bin/env python3
"""Run a visible, deterministic MVP loop for the Autom oat cockpit."""

from __future__ import annotations

import argparse
import json
import os
import re
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


STOP_REQUESTED = False
MAX_ARTIFACT_HEALTH_DETAILS = 8
MAX_ARTIFACT_HEALTH_DETAIL_CHARS = 240
MAX_COORDINATION_DETAIL_CHARS = 240
MAX_HANDOFF_BYTES = 128 * 1024
MAX_HANDOFF_LATEST_SCAN_LINES = 24
PIPELINE_SUMMARY_OBJECT_SECTIONS = (
    "execution_readiness",
    "contract",
    "workflow",
    "coverage",
    "latest_import",
)
URL_TOKEN_PATTERN = re.compile(r"https?://[^\s,'\"<>\]\)]+", re.IGNORECASE)
TOKEN_ASSIGNMENT_PATTERN = re.compile(
    r"\b([A-Za-z0-9_-]*(?:token|secret|password|api[_-]?key|access[_-]?key)"
    r"[A-Za-z0-9_-]*)=([^,\s;]+)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_stop(signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, parse_constant=reject_json_constant)


def reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


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


def artifact_health_summary(
    health_status: str,
    artifact_statuses: dict[str, Any],
    degraded_artifacts: list[str],
) -> str:
    loaded_count = sum(1 for status in artifact_statuses.values() if status == "loaded")
    artifact_count = len(artifact_statuses)
    parts = [
        f"status={bounded_artifact_health_detail(health_status)}",
        f"loaded={loaded_count}/{artifact_count}",
        f"degraded={len(degraded_artifacts)}",
    ]
    if degraded_artifacts:
        problem_names = ",".join(degraded_artifacts[:MAX_ARTIFACT_HEALTH_DETAILS])
        parts.append(f"problems={bounded_artifact_health_detail(problem_names)}")
    return bounded_artifact_health_detail(" ".join(parts))


def emit(log_file: Path, message: str) -> None:
    line = f"[{utc_now()}] {message}"
    print(line, flush=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def shell(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def import_readiness_command() -> list[str]:
    return [
        sys.executable,
        "scripts/run_dallas_import_pipeline.py",
        "--summary-only",
        "--require-ready",
    ]


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
    return str(handoff_line_snapshot(HANDOFF_PATH).get("latest_handoff_status"))


def sanitize_coordination_detail(
    text: str,
    max_chars: int = MAX_COORDINATION_DETAIL_CHARS,
) -> str:
    """Return a bounded, secret-safe detail string for status coordination."""

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
    if len(sanitized) > max_chars:
        return sanitized[: max_chars - 3] + "..."
    return sanitized


def sanitize_coordination_scalar(value: Any) -> Any:
    if value is None:
        return None
    return sanitize_coordination_detail(str(value))


def handoff_read_error(exc: BaseException, path: Path) -> str:
    """Return a bounded handoff read error without leaking absolute paths."""
    message = str(exc)
    safe_label = repo_path(path)
    path_strings = {str(path)}
    try:
        path_strings.add(str(path.resolve()))
    except OSError:
        pass
    for path_string in sorted(path_strings, key=len, reverse=True):
        if path_string:
            message = message.replace(path_string, safe_label)
    return sanitize_coordination_detail(message) or type(exc).__name__


def handoff_age_seconds(path: Path) -> int | None:
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        return None
    return max(0, int(datetime.now(timezone.utc).timestamp() - modified_at))


def read_handoff_lines_limited(path: Path) -> tuple[list[str] | None, dict[str, Any]]:
    if not path.exists():
        return None, {
            "handoff_file_status": "missing",
            "latest_section_found": False,
            "latest_status_found": False,
            "latest_handoff_status": "handoff missing",
        }
    try:
        with path.open("rb") as handle:
            payload_bytes = handle.read(MAX_HANDOFF_BYTES + 1)
    except OSError as exc:
        return None, {
            "handoff_file_status": "read_failed",
            "latest_section_found": False,
            "latest_status_found": False,
            "latest_handoff_status": "handoff unreadable",
            "handoff_error": handoff_read_error(exc, path),
        }

    too_large = len(payload_bytes) > MAX_HANDOFF_BYTES
    if too_large:
        payload_bytes = payload_bytes[:MAX_HANDOFF_BYTES]
    try:
        text = payload_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, {
            "handoff_file_status": "invalid_encoding",
            "latest_section_found": False,
            "latest_status_found": False,
            "latest_handoff_status": "handoff unreadable",
            "handoff_error": sanitize_coordination_detail(
                f"invalid UTF-8 at byte {exc.start}"
            ),
        }

    metadata: dict[str, Any] = {
        "handoff_file_status": "too_large" if too_large else "loaded",
    }
    if too_large:
        metadata["handoff_error"] = (
            f"file exceeds max handoff bytes ({MAX_HANDOFF_BYTES + 1} > "
            f"{MAX_HANDOFF_BYTES})"
        )
    return text.splitlines(), metadata


def handoff_line_snapshot(path: Path) -> dict[str, Any]:
    lines, metadata = read_handoff_lines_limited(path)
    if lines is None:
        return metadata

    latest_section_found = False
    latest_fields: dict[str, Any] = {}
    latest_section_line_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "## Latest":
            latest_section_found = True
            latest_fields = {}
            latest_section_line_count = 0
            continue
        if not latest_section_found:
            continue
        if stripped.startswith("## ") and latest_section_found:
            break
        if latest_section_found and stripped == "" and latest_fields:
            break
        latest_section_line_count += 1
        if latest_section_line_count > MAX_HANDOFF_LATEST_SCAN_LINES:
            break
        if line.startswith("- timestamp:"):
            latest_fields["latest_handoff_timestamp"] = sanitize_coordination_scalar(
                line.replace("- timestamp:", "", 1).strip()
            )
        elif line.startswith("- lane:"):
            latest_fields["latest_handoff_lane"] = sanitize_coordination_scalar(
                line.replace("- lane:", "", 1).strip()
            )
        elif line.startswith("- status:"):
            latest_fields["latest_handoff_status"] = sanitize_coordination_scalar(
                line.replace("- status:", "", 1).strip()
            )
    latest_handoff_status = (
        latest_fields.get("latest_handoff_status")
        or (
            "handoff too large"
            if metadata["handoff_file_status"] == "too_large"
            else "handoff present"
        )
    )
    return {
        **metadata,
        **latest_fields,
        "latest_section_found": latest_section_found,
        "latest_status_found": "latest_handoff_status" in latest_fields,
        "latest_handoff_status": latest_handoff_status,
        "handoff_age_seconds": handoff_age_seconds(path),
    }


def coordination_snapshot() -> dict[str, Any]:
    """Return compact shared-lane context for cockpit status consumers."""
    return {
        "handoff_path": repo_path(HANDOFF_PATH),
        **handoff_line_snapshot(HANDOFF_PATH),
    }


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
    structure_error = pipeline_summary_structure_error(summary)
    if structure_error:
        return {
            "status": "invalid",
            "summary_path": repo_path(PIPELINE_SUMMARY_PATH),
            "error": structure_error,
            "execution_readiness": {
                "status": "blocked",
                "ready_for_next_import_records": False,
                "blockers": [structure_error],
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


def pipeline_summary_structure_error(summary: Any) -> str | None:
    if not isinstance(summary, dict):
        return "pipeline_summary_not_object"
    for section in PIPELINE_SUMMARY_OBJECT_SECTIONS:
        if not isinstance(summary.get(section), dict):
            return f"pipeline_summary_{section}_invalid"
    coverage = summary.get("coverage", {})
    if not isinstance(coverage.get("thin_groups"), dict):
        return "pipeline_summary_coverage_thin_groups_invalid"
    return None


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
    health_status = (
        "loaded"
        if all(status == "loaded" for status in artifact_statuses.values())
        else "degraded"
    )
    loaded_artifact_count = sum(
        1 for status in artifact_statuses.values() if status == "loaded"
    )
    return {
        "artifact_health": {
            "status": health_status,
            "statuses": artifact_statuses,
            "artifact_count": len(artifact_statuses),
            "loaded_artifact_count": loaded_artifact_count,
            "degraded_artifacts": degraded_artifacts,
            "degraded_artifact_count": len(degraded_artifacts),
            "degradation_details": degradation_details,
            "summary": artifact_health_summary(
                health_status,
                artifact_statuses,
                degraded_artifacts,
            ),
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
            "operator_corrections": queue.get("operator_correction_summary", {}),
        },
        "import_pipeline": import_pipeline,
    }


def artifact_health_loaded(artifacts: dict[str, Any]) -> bool:
    artifact_health = artifacts.get("artifact_health", {})
    return (
        isinstance(artifact_health, dict)
        and artifact_health.get("status") == "loaded"
    )


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
        handle.write(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")


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
        run_step(
            log_file,
            "refresh Dallas import readiness summary",
            import_readiness_command(),
        ),
    ]
    artifacts = inspect_artifacts()
    git = git_state()
    failed_steps = [step for step in steps if step["exit_status"] != 0]
    contract_ok = artifacts["contract"]["overall_passed"] is True
    artifact_ok = artifact_health_loaded(artifacts)
    status = "passing" if not failed_steps and contract_ok and artifact_ok else "failing"
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
        "coordination": coordination_snapshot(),
    }
    write_json(STATUS_FILE, payload)
    append_event(event_file, payload)
    emit(
        log_file,
        "iteration "
        f"{iteration} end status={status} "
        f"artifact_health={artifacts['artifact_health']['status']} "
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
