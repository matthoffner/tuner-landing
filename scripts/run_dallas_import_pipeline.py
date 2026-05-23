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
COVERAGE_JSON_PATH = ROOT / "generated" / "coverage" / "dallas-electrician-edge-case-coverage-v1" / "coverage.json"
COVERAGE_REPORT_PATH = ROOT / "generated" / "coverage" / "dallas-electrician-edge-case-coverage-v1" / "coverage.md"
CONTRACT_REPORT_PATH = ROOT / "generated" / "contracts" / "dallas-electrician-contract-summary-v1" / "summary.md"
WORKFLOW_REPORT_PATH = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1" / "action-queue.md"
SUMMARY_DIR = ROOT / "generated" / "pipeline" / "dallas-import-pipeline-summary-v1"
SUMMARY_JSON_PATH = SUMMARY_DIR / "summary.json"
SUMMARY_REPORT_PATH = SUMMARY_DIR / "summary.md"
PYTHON = sys.executable
PATTERNS_COMMAND = "python3 scripts/record_operator_correction.py --list-patterns --format text"
COMPLETION_GATE_COMMAND = (
    "python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text"
)


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


def section_values(rows):
    return [
        row.get("value") or row.get("slice_id")
        for row in rows
        if row.get("value") or row.get("slice_id")
    ]


def summarize_coverage(coverage, dataset_id):
    coverage_summary = coverage.get("summary", {})
    latest_dataset_id = coverage_summary.get("latest_dataset_id", dataset_id)
    latest_dataset = next(
        (
            dataset
            for dataset in coverage.get("datasets", [])
            if dataset.get("dataset_id") == latest_dataset_id
        ),
        {},
    )
    sections = {
        "result_states": latest_dataset.get("result_states", []),
        "failure_reasons": latest_dataset.get("failure_reasons", []),
        "pattern_slices": latest_dataset.get("pattern_slices", []),
        "next_action_groups": latest_dataset.get("next_action_groups", []),
    }
    thin_groups = {
        section_name: section_values(
            [row for row in rows if not row.get("repeated")]
        )
        for section_name, rows in sections.items()
    }
    return {
        "latest_dataset_id": latest_dataset_id,
        "repeated_support_threshold": coverage_summary.get("repeated_support_threshold"),
        "latest_counts": latest_dataset.get("counts", {}),
        "latest_repeated_counts": coverage_summary.get("latest_repeated_counts", {}),
        "latest_thin_counts": coverage_summary.get("latest_thin_counts", {}),
        "thin_groups": thin_groups,
        "recommended_next_step": coverage_summary.get("recommended_next_step"),
        "json_path": command_path(COVERAGE_JSON_PATH),
        "report_path": command_path(COVERAGE_REPORT_PATH),
    }


def summarize_contract_dataset(contract, dataset_id):
    latest_dataset = next(
        (
            dataset
            for dataset in contract.get("datasets", [])
            if dataset.get("dataset_id") == dataset_id
        ),
        {},
    )
    return {
        "dataset_id": latest_dataset.get("dataset_id", dataset_id),
        "label": latest_dataset.get("label"),
        "kind": latest_dataset.get("kind"),
        "project_name": latest_dataset.get("project_name"),
        "counts": latest_dataset.get("counts", {}),
        "task_family_counts": latest_dataset.get("task_family_counts", {}),
        "inspection_result_vocabulary": latest_dataset.get(
            "inspection_result_vocabulary", []
        ),
        "paths": latest_dataset.get("paths", {}),
    }


def build_summary(args):
    contract = load_json(CONTRACT_PATH)
    workflow = load_json(WORKFLOW_PATH)
    coverage = load_json(COVERAGE_JSON_PATH)
    contract_checks = contract.get("checks", [])
    workflow_summary = workflow.get("summary", {})
    correction_summary = workflow.get("operator_correction_summary", {})
    pattern_summary = workflow.get("operator_correction_patterns", {})
    checks_passed = sum(1 for check in contract_checks if check.get("passed"))
    queue_items = workflow_summary.get("queue_items")
    correction_count = correction_summary.get("queue_items_with_corrections")

    return {
        "summary_id": "dallas-import-pipeline-summary-v1",
        "dataset_id": args.dataset_id,
        "inputs": {
            "raw_dir": command_path(args.raw_dir),
            "normalized_dir": command_path(args.normalized_dir),
            "fixture_dir": command_path(args.fixture_dir),
            "eval_dir": command_path(args.eval_dir),
        },
        "contract": {
            "overall_passed": contract.get("overall_passed"),
            "checks_passed": checks_passed,
            "checks_total": len(contract_checks),
            "next_gap": contract.get("next_gap"),
            "json_path": command_path(CONTRACT_PATH),
            "report_path": command_path(CONTRACT_REPORT_PATH),
        },
        "workflow": {
            "queue_items": queue_items,
            "operator_corrections_captured": correction_count,
            "accepted_pattern_count": pattern_summary.get("accepted_pattern_count"),
            "json_path": command_path(WORKFLOW_PATH),
            "report_path": command_path(WORKFLOW_REPORT_PATH),
        },
        "coverage": summarize_coverage(coverage, args.dataset_id),
        "correction_gate": {
            "required": not args.skip_correction_gate,
            "status": "skipped" if args.skip_correction_gate else "passed",
            "command": COMPLETION_GATE_COMMAND,
        },
        "follow_up": {
            "patterns_command": PATTERNS_COMMAND,
            "completion_gate": COMPLETION_GATE_COMMAND,
            "coverage_report": command_path(COVERAGE_REPORT_PATH),
            "contract_report": command_path(CONTRACT_REPORT_PATH),
            "workflow_report": command_path(WORKFLOW_REPORT_PATH),
            "summary_json": command_path(SUMMARY_JSON_PATH),
            "summary_report": command_path(SUMMARY_REPORT_PATH),
        },
        "latest_import": summarize_contract_dataset(contract, args.dataset_id),
    }


def write_summary(summary):
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    with SUMMARY_JSON_PATH.open("w") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    contract = summary["contract"]
    workflow = summary["workflow"]
    coverage = summary["coverage"]
    follow_up = summary["follow_up"]
    correction_gate = summary["correction_gate"]
    latest_import = summary["latest_import"]
    import_counts = latest_import.get("counts", {})
    task_family_counts = latest_import.get("task_family_counts", {})
    contract_status = "PASS" if contract["overall_passed"] else "FAIL"
    gate_status = correction_gate["status"].upper()
    coverage_repeated = coverage.get("latest_repeated_counts", {})
    coverage_thin = coverage.get("latest_thin_counts", {})
    thin_groups = coverage.get("thin_groups", {})
    thin_labels = [
        f"{section}: {', '.join(values)}"
        for section, values in thin_groups.items()
        if values
    ]
    lines = [
        "# Dallas Import Pipeline Summary",
        "",
        f"- Dataset: `{summary['dataset_id']}`",
        (
            f"- Contract: {contract_status} "
            f"(`{contract['checks_passed']}/{contract['checks_total']}` checks)"
        ),
        f"- Queue items: `{workflow['queue_items']}`",
        (
            "- Operator corrections: "
            f"`{workflow['operator_corrections_captured']}/{workflow['queue_items']}`"
        ),
        f"- Accepted patterns: `{workflow['accepted_pattern_count']}`",
        (
            "- Import artifacts: "
            f"`{import_counts.get('permits', 0)}` permits, "
            f"`{import_counts.get('inspections', 0)}` inspections, "
            f"`{import_counts.get('tasks', 0)}` eval tasks, "
            f"`{import_counts.get('label_reviews', 0)}` reviewed labels"
        ),
        f"- Correction gate: {gate_status}",
        f"- Next gap: {contract['next_gap']}",
        "",
        "## Import Artifact Snapshot",
        "",
        (
            "- Normalized rows: "
            f"`{import_counts.get('properties', 0)}` properties, "
            f"`{import_counts.get('permits', 0)}` permits, "
            f"`{import_counts.get('inspections', 0)}` inspections, "
            f"`{import_counts.get('contractors', 0)}` contractors"
        ),
        (
            "- Source support: "
            f"`{import_counts.get('source_records', 0)}` source records, "
            f"`{import_counts.get('rule_documents', 0)}` rule documents"
        ),
        (
            "- Eval rows: "
            f"`{import_counts.get('tasks', 0)}` tasks, "
            f"`{import_counts.get('label_reviews', 0)}` reviewed labels, "
            f"`{import_counts.get('dev_tasks', 0)}` dev tasks, "
            f"`{import_counts.get('test_tasks', 0)}` test tasks"
        ),
        (
            "- Task families: "
            f"`{task_family_counts.get('next_inspection_outcome', 0)}` next-outcome, "
            f"`{task_family_counts.get('failure_reason_classification', 0)}` failure-reason, "
            f"`{task_family_counts.get('recommended_next_action', 0)}` next-action, "
            f"`{task_family_counts.get('pattern_extraction', 0)}` pattern-extraction"
        ),
        (
            "- Result vocabulary: "
            + ", ".join(
                f"`{value}`"
                for value in latest_import.get("inspection_result_vocabulary", [])
            )
        ),
        "",
        "## Coverage Snapshot",
        "",
        f"- Coverage dataset: `{coverage.get('latest_dataset_id')}`",
        f"- Repeated support threshold: `{coverage.get('repeated_support_threshold')}` permits",
        (
            "- Repeated counts: "
            f"`{coverage_repeated.get('result_states', 0)}` result states, "
            f"`{coverage_repeated.get('failure_reasons', 0)}` failure reasons, "
            f"`{coverage_repeated.get('pattern_slices', 0)}` pattern slices, "
            f"`{coverage_repeated.get('next_action_groups', 0)}` next-action groups"
        ),
        (
            "- Thin counts: "
            f"`{coverage_thin.get('result_states', 0)}` result states, "
            f"`{coverage_thin.get('failure_reasons', 0)}` failure reasons, "
            f"`{coverage_thin.get('pattern_slices', 0)}` pattern slices, "
            f"`{coverage_thin.get('next_action_groups', 0)}` next-action groups"
        ),
        f"- Thin groups: {'; '.join(thin_labels) if thin_labels else 'none'}",
        f"- Coverage next step: {coverage.get('recommended_next_step')}",
        "",
        "## Follow-Up",
        "",
        f"- Pattern review: `{follow_up['patterns_command']}`",
        f"- Completion gate: `{follow_up['completion_gate']}`",
        "",
        "## Reports",
        "",
        f"- Coverage: `{follow_up['coverage_report']}`",
        f"- Contract: `{follow_up['contract_report']}`",
        f"- Workflow: `{follow_up['workflow_report']}`",
        f"- Summary JSON: `{follow_up['summary_json']}`",
    ]
    with SUMMARY_REPORT_PATH.open("w") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def print_summary(summary):
    contract = summary["contract"]
    workflow = summary["workflow"]
    coverage = summary["coverage"]
    follow_up = summary["follow_up"]
    import_counts = summary["latest_import"].get("counts", {})
    coverage_repeated = coverage.get("latest_repeated_counts", {})
    coverage_thin = coverage.get("latest_thin_counts", {})

    print("==> Dallas import pipeline summary")
    print(f"dataset_id: {summary['dataset_id']}")
    print(f"contract_passed: {str(contract.get('overall_passed')).lower()}")
    print(f"contract_checks: {contract.get('checks_passed')}/{contract.get('checks_total')}")
    print(f"queue_items: {workflow.get('queue_items')}")
    print(
        "operator_corrections: "
        f"{workflow.get('operator_corrections_captured')}/{workflow.get('queue_items')}"
    )
    print(f"accepted_patterns: {workflow.get('accepted_pattern_count')}")
    print(
        "import_counts: "
        f"permits={import_counts.get('permits', 0)}, "
        f"inspections={import_counts.get('inspections', 0)}, "
        f"tasks={import_counts.get('tasks', 0)}, "
        f"label_reviews={import_counts.get('label_reviews', 0)}, "
        f"source_records={import_counts.get('source_records', 0)}"
    )
    print(f"next_gap: {contract.get('next_gap')}")
    print(
        "coverage_repeated_counts: "
        f"result_states={coverage_repeated.get('result_states', 0)}, "
        f"failure_reasons={coverage_repeated.get('failure_reasons', 0)}, "
        f"pattern_slices={coverage_repeated.get('pattern_slices', 0)}, "
        f"next_action_groups={coverage_repeated.get('next_action_groups', 0)}"
    )
    print(
        "coverage_thin_counts: "
        f"result_states={coverage_thin.get('result_states', 0)}, "
        f"failure_reasons={coverage_thin.get('failure_reasons', 0)}, "
        f"pattern_slices={coverage_thin.get('pattern_slices', 0)}, "
        f"next_action_groups={coverage_thin.get('next_action_groups', 0)}"
    )
    print(f"coverage_next_step: {coverage.get('recommended_next_step')}")
    print("follow_up:")
    print(f"  patterns_command: {follow_up['patterns_command']}")
    print(f"  completion_gate: {follow_up['completion_gate']}")
    print(f"  coverage_report: {follow_up['coverage_report']}")
    print(f"  contract_report: {follow_up['contract_report']}")
    print(f"  workflow_report: {follow_up['workflow_report']}")
    print(f"  summary_json: {follow_up['summary_json']}")
    print(f"  summary_report: {follow_up['summary_report']}")


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
    summary = build_summary(args)
    write_summary(summary)
    print_summary(summary)


if __name__ == "__main__":
    main()
