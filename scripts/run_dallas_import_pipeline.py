#!/usr/bin/env python3

import argparse
import csv
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
REQUIRE_READY_COMMAND = "python3 scripts/run_dallas_import_pipeline.py --require-ready"
SUMMARY_ONLY_REQUIRE_READY_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready"
)
SUMMARY_ONLY_REQUIRE_READY_JSON_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json"
)
RAW_IMPORT_FILE_NAMES = (
    "permits.csv",
    "inspections.csv",
    "contractors.csv",
    "rule_documents.csv",
)
RAW_IMPORT_REQUIRED_FIELDS = {
    "permits.csv": [
        "permit_number",
        "address",
        "city",
        "trade",
        "work_class",
    ],
    "inspections.csv": [
        "permit_number",
        "inspection_date",
        "inspection_type",
        "result",
    ],
    "contractors.csv": [
        "registration_id",
        "name",
        "license_type",
    ],
    "rule_documents.csv": [
        "title",
    ],
}


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
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero if the generated execution_readiness gate is blocked.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help=(
            "Skip artifact regeneration and rebuild the durable pipeline summary from "
            "current generated outputs; still runs the correction gate unless "
            "--skip-correction-gate is set."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help=(
            "stdout format for the final pipeline summary; JSON mode sends step logs "
            "and child command output to stderr so stdout stays machine-readable"
        ),
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


def csv_data_row_count(path):
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for row in reader if any(cell.strip() for cell in row))


def csv_header(path):
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return []
        return [cell.strip() for cell in header if cell.strip()]


def raw_file_row_counts(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: csv_data_row_count(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_file_headers(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: csv_header(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_file_required_fields():
    return {
        file_name: list(RAW_IMPORT_REQUIRED_FIELDS[file_name])
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_file_optional_fields(headers_by_file, required_fields_by_file):
    optional_fields = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        headers = headers_by_file.get(file_name)
        required_fields = set(required_fields_by_file.get(file_name, []))
        if not isinstance(headers, list):
            optional_fields[file_name] = None
            continue
        optional_fields[file_name] = [
            header for header in headers if header not in required_fields
        ]
    return optional_fields


def next_import_record_handoff(raw_dir):
    display_raw_dir = command_path(raw_dir).rstrip("/")
    raw_headers = raw_file_headers(raw_dir)
    raw_required_fields = raw_file_required_fields()
    return {
        "raw_dir": display_raw_dir,
        "raw_files": [
            f"{display_raw_dir}/{file_name}" for file_name in RAW_IMPORT_FILE_NAMES
        ],
        "raw_file_row_counts": raw_file_row_counts(raw_dir),
        "raw_file_headers": raw_headers,
        "raw_file_required_fields": raw_required_fields,
        "raw_file_optional_fields": raw_file_optional_fields(
            raw_headers,
            raw_required_fields,
        ),
        "after_edit_command": REQUIRE_READY_COMMAND,
        "readiness_check_command": SUMMARY_ONLY_REQUIRE_READY_JSON_COMMAND,
    }


def run_step(label, command, output_format="text"):
    log_stream = sys.stderr if output_format == "json" else sys.stdout
    print(f"==> {label}", flush=True, file=log_stream)
    print(display_command(command), flush=True, file=log_stream)
    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=sys.stderr if output_format == "json" else None,
    )
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


def summarize_operator_patterns(pattern_summary):
    patterns = pattern_summary.get("patterns", [])
    if not isinstance(patterns, list):
        return []

    accepted_patterns = []
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        accepted_patterns.append(
            {
                "pattern_id": pattern.get("pattern_id"),
                "corrected_actions": pattern.get("corrected_actions", []),
                "corrected_action_labels": pattern.get("corrected_action_labels", []),
                "queue_item_count": pattern.get("queue_item_count", 0),
                "queue_item_ids": pattern.get("queue_item_ids", []),
                "source_permit_numbers": pattern.get("source_permit_numbers", []),
                "trigger_result_counts": pattern.get("trigger_result_counts", {}),
                "failure_reason_counts": pattern.get("failure_reason_counts", {}),
                "inspection_type_counts": pattern.get("inspection_type_counts", {}),
                "observed_followup_result_counts": pattern.get(
                    "observed_followup_result_counts", {}
                ),
            }
        )
    return accepted_patterns


def build_execution_readiness(contract, workflow, coverage, correction_gate):
    queue_items = workflow.get("queue_items")
    correction_count = workflow.get("operator_corrections_captured")
    thin_counts = coverage.get("latest_thin_counts", {})

    gates = {
        "contract_passed": bool(contract.get("overall_passed")),
        "operator_corrections_complete": (
            isinstance(queue_items, int)
            and isinstance(correction_count, int)
            and queue_items > 0
            and correction_count == queue_items
        ),
        "correction_gate_passed": correction_gate.get("status") == "passed",
        "coverage_has_no_thin_groups": all(
            count == 0 for count in thin_counts.values()
        ),
        "accepted_operator_patterns_present": (
            (workflow.get("accepted_pattern_count") or 0) > 0
        ),
    }
    blockers = [gate for gate, passed in gates.items() if not passed]
    if blockers:
        next_step = (
            "Resolve the blocked readiness gates, then rerun "
            "`python3 scripts/run_dallas_import_pipeline.py`."
        )
    else:
        next_step = (
            "Current Dallas permit-data MVP artifacts are executable; after adding "
            "or importing new Dallas rows, rerun the pipeline and inspect "
            "`workflow.accepted_patterns` plus `coverage.thin_groups` for new gaps."
        )

    return {
        "status": "ready" if not blockers else "blocked",
        "ready_for_next_import_records": not blockers,
        "gates": gates,
        "blockers": blockers,
        "next_step": next_step,
        "run_command": "python3 scripts/run_dallas_import_pipeline.py",
        "require_ready_command": REQUIRE_READY_COMMAND,
        "summary_only_require_ready_command": SUMMARY_ONLY_REQUIRE_READY_COMMAND,
        "summary_only_require_ready_json_command": SUMMARY_ONLY_REQUIRE_READY_JSON_COMMAND,
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
    contract_summary = {
        "overall_passed": contract.get("overall_passed"),
        "checks_passed": checks_passed,
        "checks_total": len(contract_checks),
        "next_gap": contract.get("next_gap"),
        "json_path": command_path(CONTRACT_PATH),
        "report_path": command_path(CONTRACT_REPORT_PATH),
    }
    workflow_pipeline_summary = {
        "queue_items": queue_items,
        "operator_corrections_captured": correction_count,
        "accepted_latest_corrections": pattern_summary.get(
            "accepted_latest_corrections"
        ),
        "accepted_pattern_count": pattern_summary.get("accepted_pattern_count"),
        "accepted_patterns": summarize_operator_patterns(pattern_summary),
        "json_path": command_path(WORKFLOW_PATH),
        "report_path": command_path(WORKFLOW_REPORT_PATH),
    }
    coverage_summary = summarize_coverage(coverage, args.dataset_id)
    correction_gate = {
        "required": not args.skip_correction_gate,
        "status": "skipped" if args.skip_correction_gate else "passed",
        "command": COMPLETION_GATE_COMMAND,
    }

    return {
        "summary_id": "dallas-import-pipeline-summary-v1",
        "dataset_id": args.dataset_id,
        "inputs": {
            "raw_dir": command_path(args.raw_dir),
            "normalized_dir": command_path(args.normalized_dir),
            "fixture_dir": command_path(args.fixture_dir),
            "eval_dir": command_path(args.eval_dir),
        },
        "next_import_record_handoff": next_import_record_handoff(args.raw_dir),
        "execution_readiness": build_execution_readiness(
            contract_summary,
            workflow_pipeline_summary,
            coverage_summary,
            correction_gate,
        ),
        "contract": contract_summary,
        "workflow": workflow_pipeline_summary,
        "coverage": coverage_summary,
        "correction_gate": correction_gate,
        "follow_up": {
            "patterns_command": PATTERNS_COMMAND,
            "completion_gate": COMPLETION_GATE_COMMAND,
            "coverage_report": command_path(COVERAGE_REPORT_PATH),
            "contract_report": command_path(CONTRACT_REPORT_PATH),
            "workflow_report": command_path(WORKFLOW_REPORT_PATH),
            "summary_json": command_path(SUMMARY_JSON_PATH),
            "summary_report": command_path(SUMMARY_REPORT_PATH),
            "require_ready_pipeline": REQUIRE_READY_COMMAND,
            "summary_only_require_ready_pipeline": SUMMARY_ONLY_REQUIRE_READY_COMMAND,
            "summary_only_require_ready_json_pipeline": SUMMARY_ONLY_REQUIRE_READY_JSON_COMMAND,
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
    next_import_handoff = summary["next_import_record_handoff"]
    correction_gate = summary["correction_gate"]
    latest_import = summary["latest_import"]
    execution_readiness = summary["execution_readiness"]
    accepted_patterns = workflow.get("accepted_patterns", [])
    import_counts = latest_import.get("counts", {})
    task_family_counts = latest_import.get("task_family_counts", {})
    contract_status = "PASS" if contract["overall_passed"] else "FAIL"
    gate_status = correction_gate["status"].upper()
    readiness_status = execution_readiness["status"].upper()
    coverage_repeated = coverage.get("latest_repeated_counts", {})
    coverage_thin = coverage.get("latest_thin_counts", {})
    thin_groups = coverage.get("thin_groups", {})
    thin_labels = [
        f"{section}: {', '.join(values)}"
        for section, values in thin_groups.items()
        if values
    ]
    raw_row_counts = next_import_handoff.get("raw_file_row_counts", {})
    raw_headers = next_import_handoff.get("raw_file_headers", {})
    raw_required_fields = next_import_handoff.get("raw_file_required_fields", {})
    raw_optional_fields = next_import_handoff.get("raw_file_optional_fields", {})

    def inline_list(values):
        return ", ".join(f"`{value}`" for value in values) if values else "none"

    def inline_counts(values):
        return f"`{json.dumps(values, sort_keys=True)}`" if values else "`{}`"

    def inline_row_counts(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            count = values.get(file_name)
            labels.append(
                f"`{file_name}`={count if isinstance(count, int) else 'missing'}"
            )
        return ", ".join(labels)

    def inline_headers(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV headers: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            headers = values.get(file_name)
            if isinstance(headers, list) and headers:
                labels.append(
                    f"- `{file_name}` headers: "
                    + ", ".join(f"`{header}`" for header in headers)
                )
            elif isinstance(headers, list):
                labels.append(f"- `{file_name}` headers: none")
            else:
                labels.append(f"- `{file_name}` headers: missing")
        return labels

    def inline_required_fields(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV required fields: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            fields = values.get(file_name)
            if isinstance(fields, list) and fields:
                labels.append(
                    f"- `{file_name}` required: "
                    + ", ".join(f"`{field}`" for field in fields)
                )
            elif isinstance(fields, list):
                labels.append(f"- `{file_name}` required: none")
            else:
                labels.append(f"- `{file_name}` required: missing")
        return labels

    def inline_optional_fields(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV optional fields: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            fields = values.get(file_name)
            if isinstance(fields, list) and fields:
                labels.append(
                    f"- `{file_name}` optional: "
                    + ", ".join(f"`{field}`" for field in fields)
                )
            elif isinstance(fields, list):
                labels.append(f"- `{file_name}` optional: none")
            else:
                labels.append(f"- `{file_name}` optional: missing")
        return labels

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
        f"- Execution readiness: {readiness_status}",
        f"- Correction gate: {gate_status}",
        f"- Next gap: {contract['next_gap']}",
        f"- Next raw import files: {inline_list(next_import_handoff['raw_files'])}",
        f"- Next raw import row counts: {inline_row_counts(raw_row_counts)}",
        "- Next raw import headers: see Follow-Up",
        "- Next raw import required fields: see Follow-Up",
        "- Next raw import optional fields: see Follow-Up",
        "",
        "## Execution Readiness",
        "",
        f"- Status: `{execution_readiness['status']}`",
        (
            "- Ready for next import records: "
            f"`{str(execution_readiness['ready_for_next_import_records']).lower()}`"
        ),
        (
            "- Passing gates: "
            + ", ".join(
                f"`{gate}`"
                for gate, passed in execution_readiness["gates"].items()
                if passed
            )
        ),
        (
            "- Blockers: "
            + (
                ", ".join(
                    f"`{blocker}`" for blocker in execution_readiness["blockers"]
                )
                if execution_readiness["blockers"]
                else "none"
            )
        ),
        f"- Next step: {execution_readiness['next_step']}",
        f"- Run command: `{execution_readiness['run_command']}`",
        f"- Require-ready command: `{execution_readiness['require_ready_command']}`",
        (
            "- Summary-only require-ready command: "
            f"`{execution_readiness['summary_only_require_ready_command']}`"
        ),
        (
            "- Summary-only require-ready JSON command: "
            f"`{execution_readiness['summary_only_require_ready_json_command']}`"
        ),
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
        "## Accepted Operator Pattern Snapshot",
        "",
        (
            "These are the reusable accepted correction patterns currently embedded in "
            "the Dallas action queue."
        ),
        "",
    ]
    if accepted_patterns:
        for pattern in accepted_patterns:
            lines.extend(
                [
                    f"### {pattern.get('pattern_id')}",
                    "",
                    f"- Queue items: `{pattern.get('queue_item_count', 0)}`",
                    f"- Action IDs: {inline_list(pattern.get('corrected_actions', []))}",
                    (
                        "- Actions: "
                        f"{inline_list(pattern.get('corrected_action_labels', []))}"
                    ),
                    (
                        "- Trigger results: "
                        f"{inline_counts(pattern.get('trigger_result_counts', {}))}"
                    ),
                    (
                        "- Failure reasons: "
                        f"{inline_counts(pattern.get('failure_reason_counts', {}))}"
                    ),
                    (
                        "- Inspection types: "
                        f"{inline_counts(pattern.get('inspection_type_counts', {}))}"
                    ),
                    (
                        "- Follow-up results: "
                        f"{inline_counts(pattern.get('observed_followup_result_counts', {}))}"
                    ),
                    (
                        "- Example permits: "
                        f"{inline_list(pattern.get('source_permit_numbers', []))}"
                    ),
                    (
                        "- Queue IDs: "
                        f"{inline_list(pattern.get('queue_item_ids', []))}"
                    ),
                    "",
                ]
            )
    else:
        lines.extend(["No accepted operator patterns are currently available.", ""])

    lines.extend(
        [
            "## Coverage Snapshot",
            "",
            f"- Coverage dataset: `{coverage.get('latest_dataset_id')}`",
            (
                "- Repeated support threshold: "
                f"`{coverage.get('repeated_support_threshold')}` permits"
            ),
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
            (
                "- After raw CSV edits: "
                f"`{next_import_handoff['after_edit_command']}`"
            ),
            (
                "- Raw CSV readiness check: "
                f"`{next_import_handoff['readiness_check_command']}`"
            ),
            (
                "- Raw CSV files: "
                f"{inline_list(next_import_handoff['raw_files'])}"
            ),
            (
                "- Raw CSV row counts: "
                f"{inline_row_counts(raw_row_counts)}"
            ),
            "- Raw CSV headers:",
            *inline_headers(raw_headers),
            "- Raw CSV required fields:",
            *inline_required_fields(raw_required_fields),
            "- Raw CSV optional fields:",
            *inline_optional_fields(raw_optional_fields),
            f"- Require-ready pipeline: `{follow_up['require_ready_pipeline']}`",
            (
                "- Summary-only require-ready pipeline: "
                f"`{follow_up['summary_only_require_ready_pipeline']}`"
            ),
            (
                "- Summary-only require-ready JSON pipeline: "
                f"`{follow_up['summary_only_require_ready_json_pipeline']}`"
            ),
            "",
            "## Reports",
            "",
            f"- Coverage: `{follow_up['coverage_report']}`",
            f"- Contract: `{follow_up['contract_report']}`",
            f"- Workflow: `{follow_up['workflow_report']}`",
            f"- Summary JSON: `{follow_up['summary_json']}`",
        ]
    )
    with SUMMARY_REPORT_PATH.open("w") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def print_summary(summary, output_format="text"):
    if output_format == "json":
        json.dump(summary, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    contract = summary["contract"]
    workflow = summary["workflow"]
    coverage = summary["coverage"]
    execution_readiness = summary["execution_readiness"]
    follow_up = summary["follow_up"]
    next_import_handoff = summary["next_import_record_handoff"]
    import_counts = summary["latest_import"].get("counts", {})
    accepted_patterns = workflow.get("accepted_patterns", [])
    coverage_repeated = coverage.get("latest_repeated_counts", {})
    coverage_thin = coverage.get("latest_thin_counts", {})
    raw_row_counts = next_import_handoff.get("raw_file_row_counts", {})
    raw_headers = next_import_handoff.get("raw_file_headers", {})
    raw_required_fields = next_import_handoff.get("raw_file_required_fields", {})
    raw_optional_fields = next_import_handoff.get("raw_file_optional_fields", {})

    def format_row_counts(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            count = values.get(file_name)
            labels.append(f"{file_name}={count if isinstance(count, int) else 'missing'}")
        return ", ".join(labels)

    def format_headers(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            headers = values.get(file_name)
            if isinstance(headers, list) and headers:
                labels.append(f"{file_name}={'|'.join(headers)}")
            elif isinstance(headers, list):
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_required_fields(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            fields = values.get(file_name)
            if isinstance(fields, list) and fields:
                labels.append(f"{file_name}={'|'.join(fields)}")
            elif isinstance(fields, list):
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_optional_fields(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            fields = values.get(file_name)
            if isinstance(fields, list) and fields:
                labels.append(f"{file_name}={'|'.join(fields)}")
            elif isinstance(fields, list):
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    print("==> Dallas import pipeline summary")
    print(f"dataset_id: {summary['dataset_id']}")
    print(f"contract_passed: {str(contract.get('overall_passed')).lower()}")
    print(f"contract_checks: {contract.get('checks_passed')}/{contract.get('checks_total')}")
    print(f"execution_readiness: {execution_readiness.get('status')}")
    print(
        "ready_for_next_import_records: "
        f"{str(execution_readiness.get('ready_for_next_import_records')).lower()}"
    )
    if execution_readiness.get("blockers"):
        print(f"readiness_blockers: {', '.join(execution_readiness['blockers'])}")
    print(f"queue_items: {workflow.get('queue_items')}")
    print(
        "operator_corrections: "
        f"{workflow.get('operator_corrections_captured')}/{workflow.get('queue_items')}"
    )
    print(f"accepted_patterns: {workflow.get('accepted_pattern_count')}")
    if accepted_patterns:
        print("accepted_pattern_actions:")
        for pattern in accepted_patterns:
            actions = "|".join(pattern.get("corrected_actions", []))
            print(
                "  "
                f"{pattern.get('pattern_id')}: "
                f"{actions} "
                f"({pattern.get('queue_item_count', 0)} queue items)"
            )
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
    print(f"  raw_import_files: {', '.join(next_import_handoff['raw_files'])}")
    print(f"  raw_import_row_counts: {format_row_counts(raw_row_counts)}")
    print(f"  raw_import_headers: {format_headers(raw_headers)}")
    print(f"  raw_import_required_fields: {format_required_fields(raw_required_fields)}")
    print(f"  raw_import_optional_fields: {format_optional_fields(raw_optional_fields)}")
    print(f"  after_raw_csv_edits: {next_import_handoff['after_edit_command']}")
    print(
        "  raw_csv_readiness_check: "
        f"{next_import_handoff['readiness_check_command']}"
    )
    print(f"  coverage_report: {follow_up['coverage_report']}")
    print(f"  contract_report: {follow_up['contract_report']}")
    print(f"  workflow_report: {follow_up['workflow_report']}")
    print(f"  summary_json: {follow_up['summary_json']}")
    print(f"  summary_report: {follow_up['summary_report']}")
    print(f"  require_ready_pipeline: {follow_up['require_ready_pipeline']}")
    print(
        "  summary_only_require_ready_pipeline: "
        f"{follow_up['summary_only_require_ready_pipeline']}"
    )
    print(
        "  summary_only_require_ready_json_pipeline: "
        f"{follow_up['summary_only_require_ready_json_pipeline']}"
    )


def main():
    args = parse_args()
    artifact_steps = [
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
    steps = [] if args.summary_only else artifact_steps
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

    if args.summary_only:
        print(
            "==> Summary-only mode: using current generated Dallas artifacts",
            flush=True,
            file=sys.stderr if args.format == "json" else sys.stdout,
        )
    for label, command in steps:
        run_step(label, command, output_format=args.format)
    summary = build_summary(args)
    write_summary(summary)
    print_summary(summary, output_format=args.format)
    if args.require_ready and summary["execution_readiness"]["status"] != "ready":
        blockers = ", ".join(summary["execution_readiness"]["blockers"]) or "unknown"
        raise SystemExit(f"Dallas import execution readiness blocked: {blockers}")


if __name__ == "__main__":
    main()
