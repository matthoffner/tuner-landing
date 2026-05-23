#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LATEST_IMPORT_DATASET_ID = "dallas-electrician-import-sample-v2"
DEFAULT_RAW_DIR = ROOT / "generated" / "raw" / LATEST_IMPORT_DATASET_ID
DEFAULT_NORMALIZED_DIR = ROOT / "generated" / "normalized" / LATEST_IMPORT_DATASET_ID
DEFAULT_FIXTURE_DIR = ROOT / "generated" / "fixtures" / "dallas-electrician-import-sequences-v2"
DEFAULT_EVAL_DIR = ROOT / "generated" / "evals" / LATEST_IMPORT_DATASET_ID
WORKFLOW_PATH = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1" / "action-queue.json"
CONTRACT_PATH = ROOT / "generated" / "contracts" / "dallas-electrician-contract-summary-v1" / "summary.json"
COVERAGE_REPORT_PATH = ROOT / "generated" / "coverage" / "dallas-electrician-edge-case-coverage-v1" / "coverage.md"
CONTRACT_REPORT_PATH = ROOT / "generated" / "contracts" / "dallas-electrician-contract-summary-v1" / "summary.md"
WORKFLOW_REPORT_PATH = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1" / "action-queue.md"
PYTHON = sys.executable


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the latest Dallas electrician permit-data MVP artifacts from the "
            "CSV import fixture, then run the strict correction ledger gate."
        )
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--normalized-dir", type=Path, default=DEFAULT_NORMALIZED_DIR)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR)
    parser.add_argument("--dataset-id", default=LATEST_IMPORT_DATASET_ID)
    parser.add_argument(
        "--skip-correction-gate",
        action="store_true",
        help="Refresh artifacts without requiring every generated queue item to have a correction.",
    )
    return parser.parse_args()


def display_command(command):
    return " ".join(str(part) for part in command)


def repo_path(path):
    return path if path.is_absolute() else ROOT / path


def command_path(path):
    resolved = repo_path(path).resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def run_step(label, command):
    print(f"==> {label}", flush=True)
    print(display_command(command), flush=True)
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_json(path):
    with path.open() as handle:
        return json.load(handle)


def print_summary(dataset_id):
    contract = load_json(CONTRACT_PATH)
    workflow = load_json(WORKFLOW_PATH)
    contract_checks = contract.get("checks", [])
    workflow_summary = workflow.get("summary", {})
    correction_summary = workflow.get("operator_correction_summary", {})
    pattern_summary = workflow.get("operator_correction_patterns", {})

    print("==> Dallas import pipeline summary")
    print(f"dataset_id: {dataset_id}")
    print(f"contract_passed: {str(contract.get('overall_passed')).lower()}")
    print(f"contract_checks: {sum(1 for check in contract_checks if check.get('passed'))}/{len(contract_checks)}")
    print(f"queue_items: {workflow_summary.get('queue_items')}")
    print(
        "operator_corrections: "
        f"{correction_summary.get('queue_items_with_corrections')}/{workflow_summary.get('queue_items')}"
    )
    print(f"accepted_patterns: {pattern_summary.get('accepted_pattern_count')}")
    print(f"next_gap: {contract.get('next_gap')}")
    print("follow_up:")
    print("  patterns_command: python3 scripts/record_operator_correction.py --list-patterns --format text")
    print("  completion_gate: python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text")
    print(f"  coverage_report: {command_path(COVERAGE_REPORT_PATH)}")
    print(f"  contract_report: {command_path(CONTRACT_REPORT_PATH)}")
    print(f"  workflow_report: {command_path(WORKFLOW_REPORT_PATH)}")


def main():
    args = parse_args()
    steps = [
        (
            "Normalize Dallas import CSV rows",
            [
                PYTHON,
                "scripts/import_dallas_permit_extracts.py",
                "--input-dir",
                command_path(args.raw_dir),
                "--output-dir",
                command_path(args.normalized_dir),
            ],
        ),
        (
            "Generate Dallas fixture pack",
            [
                PYTHON,
                "scripts/generate_dallas_fixture_pack.py",
                "--input-dir",
                command_path(args.normalized_dir),
                "--output-dir",
                command_path(args.fixture_dir),
            ],
        ),
        (
            "Generate Dallas eval artifacts",
            [
                PYTHON,
                "scripts/generate_dallas_eval_artifacts.py",
                "--fixture-dir",
                command_path(args.fixture_dir),
                "--normalized-dir",
                command_path(args.normalized_dir),
                "--output-dir",
                command_path(args.eval_dir),
                "--dataset-id",
                args.dataset_id,
            ],
        ),
        (
            "Generate Dallas edge-case coverage",
            [PYTHON, "scripts/generate_dallas_edge_case_coverage.py"],
        ),
        (
            "Generate Dallas contract summary",
            [PYTHON, "scripts/generate_dallas_contract_summary.py"],
        ),
        (
            "Generate Dallas inspection workflow",
            [PYTHON, "scripts/generate_dallas_inspection_workflow.py"],
        ),
    ]
    if not args.skip_correction_gate:
        steps.append(
            (
                "Validate Dallas operator-correction completion gate",
                [
                    PYTHON,
                    "scripts/record_operator_correction.py",
                    "--validate-ledger",
                    "--require-complete",
                    "--format",
                    "text",
                ],
            )
        )

    for label, command in steps:
        run_step(label, command)
    print_summary(args.dataset_id)


if __name__ == "__main__":
    main()
