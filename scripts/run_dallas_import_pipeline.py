#!/usr/bin/env python3

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
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
RAW_IMPORT_IMPORTABLE_EXAMPLE_LIMIT = 5
RAW_IMPORT_IMPORTABLE_EXAMPLE_REASONS = {
    "permits.csv": "importable_dallas_residential_electrical_permit",
    "inspections.csv": "linked_to_importable_permit",
    "contractors.csv": "electrical_license_type",
    "rule_documents.csv": "has_title",
}
RAW_IMPORT_EXCLUSION_EXAMPLE_LIMIT = 5
RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS = {
    "permits.csv": (
        "permit_number",
        "address",
        "city",
        "trade",
        "work_class",
    ),
    "inspections.csv": (
        "permit_number",
        "inspection_date",
        "inspection_type",
        "result",
    ),
    "contractors.csv": (
        "registration_id",
        "name",
        "license_type",
    ),
    "rule_documents.csv": (
        "title",
        "document_type",
        "effective_date",
    ),
}
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
RAW_IMPORT_IDENTITY_FIELDS = {
    "permits.csv": [
        "permit_number",
    ],
    "inspections.csv": [
        "permit_number",
        "inspection_date",
        "inspection_type",
    ],
    "contractors.csv": [
        "registration_id",
    ],
    "rule_documents.csv": [
        "title",
    ],
}
RAW_IMPORT_IDENTITY_EXAMPLE_LIMIT = 5
RAW_IMPORT_VALUE_PROFILE_FIELDS = {
    "permits.csv": [
        "city",
        "trade",
        "work_class",
        "permit_type",
        "status",
        "property_type",
        "zip_code",
    ],
    "inspections.csv": [
        "inspection_type",
        "result",
        "reinspection_flag",
    ],
    "contractors.csv": [
        "license_type",
        "registration_status",
        "city",
        "state",
    ],
    "rule_documents.csv": [
        "document_type",
        "effective_date",
    ],
}
RAW_IMPORT_VALUE_PROFILE_LIMIT = 10
RAW_IMPORT_DATE_FIELDS = {
    "permits.csv": [
        "file_date",
        "issue_date",
        "final_date",
    ],
    "inspections.csv": [
        "inspection_date",
    ],
    "contractors.csv": [],
    "rule_documents.csv": [
        "effective_date",
    ],
}
RAW_IMPORT_DATE_EXAMPLE_LIMIT = 5
RAW_IMPORT_RELATIONSHIP_EXAMPLE_LIMIT = 5
RAW_IMPORT_RELATIONSHIP_CHECKS = {
    "inspections_to_permits": {
        "source_file": "inspections.csv",
        "source_field": "permit_number",
        "target_file": "permits.csv",
        "target_field": "permit_number",
        "target_import_scope": "dallas_residential_electrical_permits",
    },
    "permits_to_contractors": {
        "source_file": "permits.csv",
        "source_field": "contractor_name",
        "target_file": "contractors.csv",
        "target_field": "name",
        "target_import_scope": "electrical_contractors",
    },
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


def csv_dict_data_rows(path):
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            row
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]


def csv_dict_data_rows_with_numbers(path):
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            (line_number, row)
            for line_number, row in enumerate(reader, start=2)
            if any((value or "").strip() for value in row.values())
        ]


def raw_cell(row, field):
    return (row.get(field) or "").strip()


def raw_cell_lower(row, field):
    return raw_cell(row, field).lower()


def raw_file_row_counts(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: csv_data_row_count(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_file_next_append_rows(row_counts):
    return {
        file_name: row_counts[file_name] + 2
        if isinstance(row_counts.get(file_name), int)
        else None
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


def raw_file_identity_key_checks(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    checks = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / file_name)
        identity_fields = RAW_IMPORT_IDENTITY_FIELDS[file_name]
        if rows is None:
            checks[file_name] = None
            continue

        row_numbers_by_key = {}
        rows_missing_identity = 0
        for row_number, row in rows:
            key = tuple(raw_cell(row, field) for field in identity_fields)
            if any(not value for value in key):
                rows_missing_identity += 1
                continue
            row_numbers_by_key.setdefault(key, []).append(row_number)

        duplicate_keys = [
            (key, row_numbers)
            for key, row_numbers in row_numbers_by_key.items()
            if len(row_numbers) > 1
        ]
        duplicate_examples = [
            {
                "identity_key": dict(zip(identity_fields, key)),
                "csv_row_numbers": row_numbers,
            }
            for key, row_numbers in duplicate_keys[:RAW_IMPORT_IDENTITY_EXAMPLE_LIMIT]
        ]
        checks[file_name] = {
            "identity_fields": list(identity_fields),
            "rows_checked": len(rows),
            "rows_with_identity": len(rows) - rows_missing_identity,
            "rows_missing_identity": rows_missing_identity,
            "duplicate_identity_key_count": len(duplicate_keys),
            "rows_with_duplicate_identity": sum(
                len(row_numbers) for _, row_numbers in duplicate_keys
            ),
            "duplicate_identity_key_examples": duplicate_examples,
        }
    return checks


def raw_file_value_profiles(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    profiles = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows(resolved_raw_dir / file_name)
        if rows is None:
            profiles[file_name] = None
            continue

        field_profiles = {}
        for field in RAW_IMPORT_VALUE_PROFILE_FIELDS[file_name]:
            counts = {}
            blank_count = 0
            for row in rows:
                value = raw_cell(row, field)
                if not value:
                    blank_count += 1
                    continue
                counts[value] = counts.get(value, 0) + 1

            top_values = [
                {"value": value, "count": count}
                for value, count in sorted(
                    counts.items(),
                    key=lambda item: (-item[1], item[0].lower()),
                )[:RAW_IMPORT_VALUE_PROFILE_LIMIT]
            ]
            field_profiles[field] = {
                "distinct_value_count": len(counts),
                "blank_count": blank_count,
                "top_values": top_values,
            }

        profiles[file_name] = {
            "rows_checked": len(rows),
            "fields": field_profiles,
        }
    return profiles


def parse_raw_import_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def raw_file_date_profiles(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    profiles = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        path = resolved_raw_dir / file_name
        rows = csv_dict_data_rows_with_numbers(path)
        headers = csv_header(path)
        if rows is None or headers is None:
            profiles[file_name] = None
            continue

        field_profiles = {}
        for field in RAW_IMPORT_DATE_FIELDS[file_name]:
            blank_count = 0
            valid_date_count = 0
            invalid_examples = []
            earliest_date = None
            earliest_csv_row_number = None
            latest_date = None
            latest_csv_row_number = None

            for row_number, row in rows:
                value = raw_cell(row, field)
                if not value:
                    blank_count += 1
                    continue
                parsed_date = parse_raw_import_date(value)
                if parsed_date is None:
                    if len(invalid_examples) < RAW_IMPORT_DATE_EXAMPLE_LIMIT:
                        invalid_examples.append(
                            {
                                "csv_row_number": row_number,
                                "value": value,
                            }
                        )
                    continue
                valid_date_count += 1
                if earliest_date is None or parsed_date < earliest_date:
                    earliest_date = parsed_date
                    earliest_csv_row_number = row_number
                if latest_date is None or parsed_date > latest_date:
                    latest_date = parsed_date
                    latest_csv_row_number = row_number

            field_profiles[field] = {
                "field_present": field in headers,
                "date_format": "YYYY-MM-DD",
                "blank_count": blank_count,
                "valid_date_count": valid_date_count,
                "invalid_date_count": len(rows) - blank_count - valid_date_count,
                "earliest_date": earliest_date,
                "earliest_csv_row_number": earliest_csv_row_number,
                "latest_date": latest_date,
                "latest_csv_row_number": latest_csv_row_number,
                "invalid_examples": invalid_examples,
            }

        profiles[file_name] = {
            "rows_checked": len(rows),
            "fields": field_profiles,
        }
    return profiles


def add_raw_relationship_example(examples, row_number, row, file_name):
    if len(examples) >= RAW_IMPORT_RELATIONSHIP_EXAMPLE_LIMIT:
        return
    examples.append(
        {
            "csv_row_number": row_number,
            "row": raw_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def raw_file_relationship_checks(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "inspections.csv"
    )
    contractor_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "contractors.csv"
    )

    checks = {}
    importable_permit_numbers = set()
    all_permit_numbers = set()
    if permit_rows is not None:
        for _, row in permit_rows:
            permit_number = raw_cell(row, "permit_number")
            if permit_number:
                all_permit_numbers.add(permit_number)
            if (
                permit_number
                and raw_cell_lower(row, "city") == "dallas"
                and raw_cell_lower(row, "trade") == "electrical"
                and raw_cell_lower(row, "work_class") == "residential"
            ):
                importable_permit_numbers.add(permit_number)

    importable_contractor_names = set()
    all_contractor_names = set()
    if contractor_rows is not None:
        for _, row in contractor_rows:
            contractor_name = raw_cell(row, "name").lower()
            if contractor_name:
                all_contractor_names.add(contractor_name)
            if contractor_name and "electrical" in raw_cell_lower(row, "license_type"):
                importable_contractor_names.add(contractor_name)

    if inspection_rows is None or permit_rows is None:
        checks["inspections_to_permits"] = None
    else:
        relationship = {
            **RAW_IMPORT_RELATIONSHIP_CHECKS["inspections_to_permits"],
            "rows_checked": len(inspection_rows),
            "matched_importable_target_rows": 0,
            "matched_excluded_target_rows": 0,
            "unmatched_target_rows": 0,
            "missing_source_value_rows": 0,
            "unresolved_rows": 0,
            "unmatched_examples": [],
            "excluded_target_examples": [],
        }
        for row_number, row in inspection_rows:
            permit_number = raw_cell(row, "permit_number")
            if not permit_number:
                relationship["missing_source_value_rows"] += 1
            elif permit_number in importable_permit_numbers:
                relationship["matched_importable_target_rows"] += 1
            elif permit_number in all_permit_numbers:
                relationship["matched_excluded_target_rows"] += 1
                add_raw_relationship_example(
                    relationship["excluded_target_examples"],
                    row_number,
                    row,
                    "inspections.csv",
                )
            else:
                relationship["unmatched_target_rows"] += 1
                add_raw_relationship_example(
                    relationship["unmatched_examples"],
                    row_number,
                    row,
                    "inspections.csv",
                )
        relationship["unresolved_rows"] = (
            relationship["missing_source_value_rows"]
            + relationship["unmatched_target_rows"]
        )
        checks["inspections_to_permits"] = relationship

    if permit_rows is None or contractor_rows is None:
        checks["permits_to_contractors"] = None
    else:
        relationship = {
            **RAW_IMPORT_RELATIONSHIP_CHECKS["permits_to_contractors"],
            "rows_checked": len(permit_rows),
            "matched_importable_target_rows": 0,
            "matched_excluded_target_rows": 0,
            "unmatched_target_rows": 0,
            "missing_source_value_rows": 0,
            "unresolved_rows": 0,
            "unmatched_examples": [],
            "excluded_target_examples": [],
        }
        for row_number, row in permit_rows:
            contractor_name = raw_cell(row, "contractor_name").lower()
            if not contractor_name:
                relationship["missing_source_value_rows"] += 1
            elif contractor_name in importable_contractor_names:
                relationship["matched_importable_target_rows"] += 1
            elif contractor_name in all_contractor_names:
                relationship["matched_excluded_target_rows"] += 1
                add_raw_relationship_example(
                    relationship["excluded_target_examples"],
                    row_number,
                    row,
                    "permits.csv",
                )
            else:
                relationship["unmatched_target_rows"] += 1
                add_raw_relationship_example(
                    relationship["unmatched_examples"],
                    row_number,
                    row,
                    "permits.csv",
                )
        relationship["unresolved_rows"] = (
            relationship["missing_source_value_rows"]
            + relationship["unmatched_target_rows"]
        )
        checks["permits_to_contractors"] = relationship

    return checks


def raw_file_import_scope_counts(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows(resolved_raw_dir / "inspections.csv")
    contractor_rows = csv_dict_data_rows(resolved_raw_dir / "contractors.csv")
    rule_document_rows = csv_dict_data_rows(resolved_raw_dir / "rule_documents.csv")

    counts = {}
    in_scope_permit_numbers = set()
    if permit_rows is None:
        counts["permits.csv"] = None
    else:
        permit_scope = {
            "rows_checked": len(permit_rows),
            "importable_rows": 0,
            "excluded_rows": 0,
            "excluded_by_city": 0,
            "excluded_by_trade": 0,
            "excluded_by_work_class": 0,
        }
        for row in permit_rows:
            if raw_cell_lower(row, "city") != "dallas":
                permit_scope["excluded_by_city"] += 1
                continue
            if raw_cell_lower(row, "trade") != "electrical":
                permit_scope["excluded_by_trade"] += 1
                continue
            if raw_cell_lower(row, "work_class") != "residential":
                permit_scope["excluded_by_work_class"] += 1
                continue
            permit_scope["importable_rows"] += 1
            permit_number = raw_cell(row, "permit_number")
            if permit_number:
                in_scope_permit_numbers.add(permit_number)
        permit_scope["excluded_rows"] = (
            permit_scope["rows_checked"] - permit_scope["importable_rows"]
        )
        counts["permits.csv"] = permit_scope

    if inspection_rows is None:
        counts["inspections.csv"] = None
    else:
        inspection_scope = {
            "rows_checked": len(inspection_rows),
            "importable_rows": 0,
            "excluded_rows": 0,
            "excluded_by_unimported_permit": 0,
        }
        for row in inspection_rows:
            if raw_cell(row, "permit_number") in in_scope_permit_numbers:
                inspection_scope["importable_rows"] += 1
            else:
                inspection_scope["excluded_by_unimported_permit"] += 1
        inspection_scope["excluded_rows"] = (
            inspection_scope["rows_checked"] - inspection_scope["importable_rows"]
        )
        counts["inspections.csv"] = inspection_scope

    if contractor_rows is None:
        counts["contractors.csv"] = None
    else:
        contractor_scope = {
            "rows_checked": len(contractor_rows),
            "importable_rows": 0,
            "excluded_rows": 0,
            "excluded_by_license_type": 0,
        }
        for row in contractor_rows:
            if "electrical" in raw_cell_lower(row, "license_type"):
                contractor_scope["importable_rows"] += 1
            else:
                contractor_scope["excluded_by_license_type"] += 1
        contractor_scope["excluded_rows"] = (
            contractor_scope["rows_checked"] - contractor_scope["importable_rows"]
        )
        counts["contractors.csv"] = contractor_scope

    if rule_document_rows is None:
        counts["rule_documents.csv"] = None
    else:
        rule_document_scope = {
            "rows_checked": len(rule_document_rows),
            "importable_rows": 0,
            "excluded_rows": 0,
            "excluded_by_missing_title": 0,
        }
        for row in rule_document_rows:
            if raw_cell(row, "title"):
                rule_document_scope["importable_rows"] += 1
            else:
                rule_document_scope["excluded_by_missing_title"] += 1
        rule_document_scope["excluded_rows"] = (
            rule_document_scope["rows_checked"]
            - rule_document_scope["importable_rows"]
        )
        counts["rule_documents.csv"] = rule_document_scope

    return counts


def raw_row_snapshot(row, fields):
    return {field: raw_cell(row, field) for field in fields}


def add_raw_importable_example(examples, file_name, row_number, row):
    file_examples = examples.get(file_name)
    if (
        file_examples is None
        or len(file_examples) >= RAW_IMPORT_IMPORTABLE_EXAMPLE_LIMIT
    ):
        return
    file_examples.append(
        {
            "csv_row_number": row_number,
            "reason": RAW_IMPORT_IMPORTABLE_EXAMPLE_REASONS[file_name],
            "row": raw_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def add_raw_exclusion_example(examples, file_name, row_number, reason, row):
    file_examples = examples.get(file_name)
    if file_examples is None or len(file_examples) >= RAW_IMPORT_EXCLUSION_EXAMPLE_LIMIT:
        return
    file_examples.append(
        {
            "csv_row_number": row_number,
            "reason": reason,
            "row": raw_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def raw_file_importable_examples(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "inspections.csv"
    )
    contractor_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "contractors.csv"
    )
    rule_document_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "rule_documents.csv"
    )

    rows_by_file = {
        "permits.csv": permit_rows,
        "inspections.csv": inspection_rows,
        "contractors.csv": contractor_rows,
        "rule_documents.csv": rule_document_rows,
    }
    examples = {
        file_name: None if rows_by_file[file_name] is None else []
        for file_name in RAW_IMPORT_FILE_NAMES
    }

    in_scope_permit_numbers = set()
    if permit_rows is not None:
        for row_number, row in permit_rows:
            if (
                raw_cell_lower(row, "city") == "dallas"
                and raw_cell_lower(row, "trade") == "electrical"
                and raw_cell_lower(row, "work_class") == "residential"
            ):
                permit_number = raw_cell(row, "permit_number")
                if permit_number:
                    in_scope_permit_numbers.add(permit_number)
                add_raw_importable_example(examples, "permits.csv", row_number, row)

    if inspection_rows is not None:
        for row_number, row in inspection_rows:
            if raw_cell(row, "permit_number") in in_scope_permit_numbers:
                add_raw_importable_example(
                    examples,
                    "inspections.csv",
                    row_number,
                    row,
                )

    if contractor_rows is not None:
        for row_number, row in contractor_rows:
            if "electrical" in raw_cell_lower(row, "license_type"):
                add_raw_importable_example(
                    examples,
                    "contractors.csv",
                    row_number,
                    row,
                )

    if rule_document_rows is not None:
        for row_number, row in rule_document_rows:
            if raw_cell(row, "title"):
                add_raw_importable_example(
                    examples,
                    "rule_documents.csv",
                    row_number,
                    row,
                )

    return examples


def raw_file_exclusion_examples(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "inspections.csv"
    )
    contractor_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "contractors.csv"
    )
    rule_document_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "rule_documents.csv"
    )

    rows_by_file = {
        "permits.csv": permit_rows,
        "inspections.csv": inspection_rows,
        "contractors.csv": contractor_rows,
        "rule_documents.csv": rule_document_rows,
    }
    examples = {
        file_name: None if rows_by_file[file_name] is None else []
        for file_name in RAW_IMPORT_FILE_NAMES
    }

    in_scope_permit_numbers = set()
    if permit_rows is not None:
        for row_number, row in permit_rows:
            reason = None
            if raw_cell_lower(row, "city") != "dallas":
                reason = "excluded_by_city"
            elif raw_cell_lower(row, "trade") != "electrical":
                reason = "excluded_by_trade"
            elif raw_cell_lower(row, "work_class") != "residential":
                reason = "excluded_by_work_class"
            else:
                permit_number = raw_cell(row, "permit_number")
                if permit_number:
                    in_scope_permit_numbers.add(permit_number)
            if reason:
                add_raw_exclusion_example(
                    examples,
                    "permits.csv",
                    row_number,
                    reason,
                    row,
                )

    if inspection_rows is not None:
        for row_number, row in inspection_rows:
            if raw_cell(row, "permit_number") not in in_scope_permit_numbers:
                add_raw_exclusion_example(
                    examples,
                    "inspections.csv",
                    row_number,
                    "excluded_by_unimported_permit",
                    row,
                )

    if contractor_rows is not None:
        for row_number, row in contractor_rows:
            if "electrical" not in raw_cell_lower(row, "license_type"):
                add_raw_exclusion_example(
                    examples,
                    "contractors.csv",
                    row_number,
                    "excluded_by_license_type",
                    row,
                )

    if rule_document_rows is not None:
        for row_number, row in rule_document_rows:
            if not raw_cell(row, "title"):
                add_raw_exclusion_example(
                    examples,
                    "rule_documents.csv",
                    row_number,
                    "excluded_by_missing_title",
                    row,
                )

    return examples


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


def raw_file_append_templates(headers_by_file, required_fields_by_file):
    append_templates = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        headers = headers_by_file.get(file_name)
        required_fields = set(required_fields_by_file.get(file_name, []))
        if not isinstance(headers, list):
            append_templates[file_name] = None
            continue
        append_templates[file_name] = {
            header: "<required>" if header in required_fields else ""
            for header in headers
        }
    return append_templates


def raw_file_required_field_gaps(raw_dir, required_fields_by_file):
    resolved_raw_dir = repo_path(raw_dir)
    gaps = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        path = resolved_raw_dir / file_name
        required_fields = list(required_fields_by_file.get(file_name, []))
        if not path.exists():
            gaps[file_name] = None
            continue

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            missing_field_counts = {field: 0 for field in required_fields}
            rows_checked = 0
            rows_with_missing_required_fields = 0
            for row in reader:
                if not any((value or "").strip() for value in row.values()):
                    continue
                rows_checked += 1
                missing_fields = [
                    field
                    for field in required_fields
                    if not (row.get(field) or "").strip()
                ]
                if missing_fields:
                    rows_with_missing_required_fields += 1
                    for field in missing_fields:
                        missing_field_counts[field] += 1

        gaps[file_name] = {
            "rows_checked": rows_checked,
            "rows_with_missing_required_fields": rows_with_missing_required_fields,
            "missing_required_headers": [
                field for field in required_fields if field not in headers
            ],
            "missing_field_counts": missing_field_counts,
        }
    return gaps


def raw_file_last_data_rows(raw_dir):
    resolved_raw_dir = repo_path(raw_dir)
    last_rows = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / file_name)
        if not rows:
            last_rows[file_name] = None
            continue
        row_number, row = rows[-1]
        last_rows[file_name] = {
            "csv_row_number": row_number,
            "row": raw_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    return last_rows


def next_import_record_handoff(raw_dir):
    display_raw_dir = command_path(raw_dir).rstrip("/")
    raw_row_counts = raw_file_row_counts(raw_dir)
    raw_headers = raw_file_headers(raw_dir)
    raw_required_fields = raw_file_required_fields()
    return {
        "raw_dir": display_raw_dir,
        "raw_files": [
            f"{display_raw_dir}/{file_name}" for file_name in RAW_IMPORT_FILE_NAMES
        ],
        "raw_file_row_counts": raw_row_counts,
        "raw_file_next_append_rows": raw_file_next_append_rows(raw_row_counts),
        "raw_file_last_data_rows": raw_file_last_data_rows(raw_dir),
        "raw_file_identity_key_checks": raw_file_identity_key_checks(raw_dir),
        "raw_file_value_profiles": raw_file_value_profiles(raw_dir),
        "raw_file_date_profiles": raw_file_date_profiles(raw_dir),
        "raw_file_relationship_checks": raw_file_relationship_checks(raw_dir),
        "raw_file_import_scope_counts": raw_file_import_scope_counts(raw_dir),
        "raw_file_importable_examples": raw_file_importable_examples(raw_dir),
        "raw_file_exclusion_examples": raw_file_exclusion_examples(raw_dir),
        "raw_file_headers": raw_headers,
        "raw_file_required_fields": raw_required_fields,
        "raw_file_optional_fields": raw_file_optional_fields(
            raw_headers,
            raw_required_fields,
        ),
        "raw_file_append_templates": raw_file_append_templates(
            raw_headers,
            raw_required_fields,
        ),
        "raw_file_required_field_gaps": raw_file_required_field_gaps(
            raw_dir,
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
    raw_next_append_rows = next_import_handoff.get("raw_file_next_append_rows", {})
    raw_last_data_rows = next_import_handoff.get("raw_file_last_data_rows", {})
    raw_identity_key_checks = next_import_handoff.get(
        "raw_file_identity_key_checks",
        {},
    )
    raw_value_profiles = next_import_handoff.get(
        "raw_file_value_profiles",
        {},
    )
    raw_date_profiles = next_import_handoff.get(
        "raw_file_date_profiles",
        {},
    )
    raw_relationship_checks = next_import_handoff.get(
        "raw_file_relationship_checks",
        {},
    )
    raw_import_scope_counts = next_import_handoff.get(
        "raw_file_import_scope_counts",
        {},
    )
    raw_importable_examples = next_import_handoff.get(
        "raw_file_importable_examples",
        {},
    )
    raw_exclusion_examples = next_import_handoff.get(
        "raw_file_exclusion_examples",
        {},
    )
    raw_headers = next_import_handoff.get("raw_file_headers", {})
    raw_required_fields = next_import_handoff.get("raw_file_required_fields", {})
    raw_optional_fields = next_import_handoff.get("raw_file_optional_fields", {})
    raw_append_templates = next_import_handoff.get("raw_file_append_templates", {})
    raw_required_field_gaps = next_import_handoff.get(
        "raw_file_required_field_gaps",
        {},
    )

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

    def inline_next_append_rows(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            row_number = values.get(file_name)
            labels.append(
                f"`{file_name}` row {row_number if isinstance(row_number, int) else 'missing'}"
            )
        return ", ".join(labels)

    def inline_last_data_rows(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV last data rows: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            last_row = values.get(file_name)
            if isinstance(last_row, dict):
                labels.append(
                    f"- `{file_name}` last data row: "
                    f"`{json.dumps(last_row, sort_keys=False)}`"
                )
            elif last_row is None:
                labels.append(f"- `{file_name}` last data row: none")
            else:
                labels.append(f"- `{file_name}` last data row: missing")
        return labels

    def inline_identity_key_checks(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV identity key checks: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            check = values.get(file_name)
            if not isinstance(check, dict):
                labels.append(f"- `{file_name}` identity keys: missing")
                continue
            labels.append(
                f"- `{file_name}` identity keys: "
                f"fields {inline_list(check.get('identity_fields', []))}, "
                f"duplicates `{check.get('duplicate_identity_key_count')}`, "
                f"rows with duplicate identity "
                f"`{check.get('rows_with_duplicate_identity')}`, "
                f"missing identity rows `{check.get('rows_missing_identity')}`, "
                "examples "
                f"`{json.dumps(check.get('duplicate_identity_key_examples', []), sort_keys=False)}`"
            )
        return labels

    def inline_value_profiles(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV value profiles: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            profile = values.get(file_name)
            if not isinstance(profile, dict):
                labels.append(f"- `{file_name}` value profiles: missing")
                continue
            labels.append(
                f"- `{file_name}` value profiles: "
                f"`{json.dumps(profile, sort_keys=False)}`"
            )
        return labels

    def inline_date_profiles(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV date profiles: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            profile = values.get(file_name)
            if not isinstance(profile, dict):
                labels.append(f"- `{file_name}` date profiles: missing")
                continue
            labels.append(
                f"- `{file_name}` date profiles: "
                f"`{json.dumps(profile, sort_keys=False)}`"
            )
        return labels

    def inline_relationship_checks(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV relationship checks: none"]
        labels = []
        for relationship_name in RAW_IMPORT_RELATIONSHIP_CHECKS:
            check = values.get(relationship_name)
            if not isinstance(check, dict):
                labels.append(f"- `{relationship_name}` relationship: missing")
                continue
            labels.append(
                f"- `{relationship_name}` relationship: "
                f"`{check.get('matched_importable_target_rows')}/{check.get('rows_checked')}` "
                "matched importable target rows, "
                f"excluded target rows `{check.get('matched_excluded_target_rows')}`, "
                f"unresolved rows `{check.get('unresolved_rows')}`, "
                f"unmatched examples "
                f"`{json.dumps(check.get('unmatched_examples', []), sort_keys=False)}`, "
                f"excluded target examples "
                f"`{json.dumps(check.get('excluded_target_examples', []), sort_keys=False)}`"
            )
        return labels

    def inline_import_scope_counts(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV import scope counts: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            scope = values.get(file_name)
            if not isinstance(scope, dict):
                labels.append(f"- `{file_name}` import scope: missing")
                continue
            rows_checked = scope.get("rows_checked")
            importable_rows = scope.get("importable_rows")
            excluded_rows = scope.get("excluded_rows")
            reason_counts = {
                key: value
                for key, value in scope.items()
                if key.startswith("excluded_by_") and isinstance(value, int)
            }
            labels.append(
                f"- `{file_name}` import scope: "
                f"`{importable_rows}/{rows_checked}` importable, "
                f"excluded: `{excluded_rows}`, "
                f"reasons: {inline_counts(reason_counts)}"
            )
        return labels

    def inline_importable_examples(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV importable examples: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            examples = values.get(file_name)
            if isinstance(examples, list) and examples:
                labels.append(
                    f"- `{file_name}` importable examples: "
                    f"`{json.dumps(examples, sort_keys=False)}`"
                )
            elif isinstance(examples, list):
                labels.append(f"- `{file_name}` importable examples: none")
            else:
                labels.append(f"- `{file_name}` importable examples: missing")
        return labels

    def inline_exclusion_examples(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV exclusion examples: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            examples = values.get(file_name)
            if isinstance(examples, list) and examples:
                labels.append(
                    f"- `{file_name}` exclusion examples: "
                    f"`{json.dumps(examples, sort_keys=False)}`"
                )
            elif isinstance(examples, list):
                labels.append(f"- `{file_name}` exclusion examples: none")
            else:
                labels.append(f"- `{file_name}` exclusion examples: missing")
        return labels

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

    def inline_append_templates(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV append templates: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            template = values.get(file_name)
            if isinstance(template, dict):
                labels.append(
                    f"- `{file_name}` append template: "
                    f"`{json.dumps(template, sort_keys=False)}`"
                )
            else:
                labels.append(f"- `{file_name}` append template: missing")
        return labels

    def inline_required_field_gaps(values):
        if not isinstance(values, dict) or not values:
            return ["- Raw CSV required-field gaps: none"]
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            gap = values.get(file_name)
            if not isinstance(gap, dict):
                labels.append(f"- `{file_name}` required-field gaps: missing")
                continue
            rows_checked = gap.get("rows_checked")
            rows_with_gaps = gap.get("rows_with_missing_required_fields")
            missing_headers = gap.get("missing_required_headers", [])
            missing_counts = gap.get("missing_field_counts", {})
            labels.append(
                f"- `{file_name}` required-field gaps: "
                f"`{rows_with_gaps}/{rows_checked}` rows, "
                f"missing headers: {inline_list(missing_headers)}, "
                f"field counts: {inline_counts(missing_counts)}"
            )
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
        f"- Next raw import append rows: {inline_next_append_rows(raw_next_append_rows)}",
        "- Next raw import last data rows: see Follow-Up",
        "- Next raw import identity key checks: see Follow-Up",
        "- Next raw import value profiles: see Follow-Up",
        "- Next raw import date profiles: see Follow-Up",
        "- Next raw import relationship checks: see Follow-Up",
        "- Next raw import scope counts: see Follow-Up",
        "- Next raw importable examples: see Follow-Up",
        "- Next raw import exclusion examples: see Follow-Up",
        "- Next raw import headers: see Follow-Up",
        "- Next raw import required fields: see Follow-Up",
        "- Next raw import optional fields: see Follow-Up",
        "- Next raw import required-field gaps: see Follow-Up",
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
            (
                "- Raw CSV next append rows: "
                f"{inline_next_append_rows(raw_next_append_rows)}"
            ),
            "- Raw CSV last data rows:",
            *inline_last_data_rows(raw_last_data_rows),
            "- Raw CSV identity key checks:",
            *inline_identity_key_checks(raw_identity_key_checks),
            "- Raw CSV value profiles:",
            *inline_value_profiles(raw_value_profiles),
            "- Raw CSV date profiles:",
            *inline_date_profiles(raw_date_profiles),
            "- Raw CSV relationship checks:",
            *inline_relationship_checks(raw_relationship_checks),
            "- Raw CSV import scope counts:",
            *inline_import_scope_counts(raw_import_scope_counts),
            "- Raw CSV importable examples:",
            *inline_importable_examples(raw_importable_examples),
            "- Raw CSV exclusion examples:",
            *inline_exclusion_examples(raw_exclusion_examples),
            "- Raw CSV headers:",
            *inline_headers(raw_headers),
            "- Raw CSV required fields:",
            *inline_required_fields(raw_required_fields),
            "- Raw CSV optional fields:",
            *inline_optional_fields(raw_optional_fields),
            "- Raw CSV append templates:",
            *inline_append_templates(raw_append_templates),
            "- Raw CSV required-field gaps:",
            *inline_required_field_gaps(raw_required_field_gaps),
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
    raw_next_append_rows = next_import_handoff.get("raw_file_next_append_rows", {})
    raw_last_data_rows = next_import_handoff.get("raw_file_last_data_rows", {})
    raw_identity_key_checks = next_import_handoff.get(
        "raw_file_identity_key_checks",
        {},
    )
    raw_value_profiles = next_import_handoff.get(
        "raw_file_value_profiles",
        {},
    )
    raw_date_profiles = next_import_handoff.get(
        "raw_file_date_profiles",
        {},
    )
    raw_relationship_checks = next_import_handoff.get(
        "raw_file_relationship_checks",
        {},
    )
    raw_import_scope_counts = next_import_handoff.get(
        "raw_file_import_scope_counts",
        {},
    )
    raw_importable_examples = next_import_handoff.get(
        "raw_file_importable_examples",
        {},
    )
    raw_exclusion_examples = next_import_handoff.get(
        "raw_file_exclusion_examples",
        {},
    )
    raw_headers = next_import_handoff.get("raw_file_headers", {})
    raw_required_fields = next_import_handoff.get("raw_file_required_fields", {})
    raw_optional_fields = next_import_handoff.get("raw_file_optional_fields", {})
    raw_append_templates = next_import_handoff.get("raw_file_append_templates", {})
    raw_required_field_gaps = next_import_handoff.get(
        "raw_file_required_field_gaps",
        {},
    )

    def format_row_counts(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            count = values.get(file_name)
            labels.append(f"{file_name}={count if isinstance(count, int) else 'missing'}")
        return ", ".join(labels)

    def format_next_append_rows(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            row_number = values.get(file_name)
            labels.append(
                f"{file_name}=row {row_number if isinstance(row_number, int) else 'missing'}"
            )
        return ", ".join(labels)

    def format_last_data_rows(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            last_row = values.get(file_name)
            if isinstance(last_row, dict):
                labels.append(f"{file_name}={json.dumps(last_row, sort_keys=False)}")
            elif last_row is None:
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_identity_key_checks(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            check = values.get(file_name)
            if not isinstance(check, dict):
                labels.append(f"{file_name}=missing")
                continue
            fields = check.get("identity_fields", [])
            duplicate_examples = check.get("duplicate_identity_key_examples", [])
            labels.append(
                f"{file_name}=fields:{'|'.join(fields) if fields else 'none'} "
                f"duplicates={check.get('duplicate_identity_key_count')} "
                f"duplicate_rows={check.get('rows_with_duplicate_identity')} "
                f"missing_identity_rows={check.get('rows_missing_identity')} "
                f"examples={json.dumps(duplicate_examples, sort_keys=False)}"
            )
        return "; ".join(labels)

    def format_value_profiles(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            profile = values.get(file_name)
            if isinstance(profile, dict):
                labels.append(f"{file_name}={json.dumps(profile, sort_keys=False)}")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_date_profiles(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            profile = values.get(file_name)
            if isinstance(profile, dict):
                labels.append(f"{file_name}={json.dumps(profile, sort_keys=False)}")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_relationship_checks(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for relationship_name in RAW_IMPORT_RELATIONSHIP_CHECKS:
            check = values.get(relationship_name)
            if not isinstance(check, dict):
                labels.append(f"{relationship_name}=missing")
                continue
            labels.append(
                f"{relationship_name}="
                f"{check.get('matched_importable_target_rows')}/{check.get('rows_checked')} "
                "matched_importable "
                f"(excluded_target={check.get('matched_excluded_target_rows')}, "
                f"unmatched={check.get('unmatched_target_rows')}, "
                f"missing_source={check.get('missing_source_value_rows')}, "
                f"unresolved={check.get('unresolved_rows')}, "
                f"unmatched_examples={json.dumps(check.get('unmatched_examples', []), sort_keys=False)}, "
                f"excluded_target_examples={json.dumps(check.get('excluded_target_examples', []), sort_keys=False)})"
            )
        return "; ".join(labels)

    def format_import_scope_counts(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            scope = values.get(file_name)
            if not isinstance(scope, dict):
                labels.append(f"{file_name}=missing")
                continue
            reason_counts = {
                key: value
                for key, value in scope.items()
                if key.startswith("excluded_by_") and isinstance(value, int)
            }
            labels.append(
                f"{file_name}={scope.get('importable_rows')}/{scope.get('rows_checked')} "
                f"importable "
                f"(excluded={scope.get('excluded_rows')}, "
                f"reasons={json.dumps(reason_counts, sort_keys=True)})"
            )
        return "; ".join(labels)

    def format_importable_examples(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            examples = values.get(file_name)
            if isinstance(examples, list) and examples:
                labels.append(f"{file_name}={json.dumps(examples, sort_keys=False)}")
            elif isinstance(examples, list):
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_exclusion_examples(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            examples = values.get(file_name)
            if isinstance(examples, list) and examples:
                labels.append(f"{file_name}={json.dumps(examples, sort_keys=False)}")
            elif isinstance(examples, list):
                labels.append(f"{file_name}=none")
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

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

    def format_append_templates(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            template = values.get(file_name)
            if isinstance(template, dict):
                labels.append(
                    f"{file_name}={json.dumps(template, sort_keys=False)}"
                )
            else:
                labels.append(f"{file_name}=missing")
        return "; ".join(labels)

    def format_required_field_gaps(values):
        if not isinstance(values, dict) or not values:
            return "none"
        labels = []
        for file_name in RAW_IMPORT_FILE_NAMES:
            gap = values.get(file_name)
            if not isinstance(gap, dict):
                labels.append(f"{file_name}=missing")
                continue
            rows_checked = gap.get("rows_checked")
            rows_with_gaps = gap.get("rows_with_missing_required_fields")
            missing_headers = gap.get("missing_required_headers", [])
            missing_counts = gap.get("missing_field_counts", {})
            labels.append(
                f"{file_name}={rows_with_gaps}/{rows_checked} rows "
                f"(missing_headers={','.join(missing_headers) if missing_headers else 'none'}, "
                f"field_counts={json.dumps(missing_counts, sort_keys=True)})"
            )
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
    print(f"  raw_import_next_append_rows: {format_next_append_rows(raw_next_append_rows)}")
    print(f"  raw_import_last_data_rows: {format_last_data_rows(raw_last_data_rows)}")
    print(
        "  raw_import_identity_key_checks: "
        f"{format_identity_key_checks(raw_identity_key_checks)}"
    )
    print(
        "  raw_import_value_profiles: "
        f"{format_value_profiles(raw_value_profiles)}"
    )
    print(
        "  raw_import_date_profiles: "
        f"{format_date_profiles(raw_date_profiles)}"
    )
    print(
        "  raw_import_relationship_checks: "
        f"{format_relationship_checks(raw_relationship_checks)}"
    )
    print(
        "  raw_import_scope_counts: "
        f"{format_import_scope_counts(raw_import_scope_counts)}"
    )
    print(
        "  raw_importable_examples: "
        f"{format_importable_examples(raw_importable_examples)}"
    )
    print(
        "  raw_import_exclusion_examples: "
        f"{format_exclusion_examples(raw_exclusion_examples)}"
    )
    print(f"  raw_import_headers: {format_headers(raw_headers)}")
    print(f"  raw_import_required_fields: {format_required_fields(raw_required_fields)}")
    print(f"  raw_import_optional_fields: {format_optional_fields(raw_optional_fields)}")
    print(f"  raw_import_append_templates: {format_append_templates(raw_append_templates)}")
    print(
        "  raw_import_required_field_gaps: "
        f"{format_required_field_gaps(raw_required_field_gaps)}"
    )
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
