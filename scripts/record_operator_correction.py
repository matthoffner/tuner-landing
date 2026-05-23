#!/usr/bin/env python3
"""Record one Dallas inspection operator correction without running the cockpit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shlex
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from operator_corrections import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_QUEUE_PATH,
    ROOT,
    VALID_CORRECTION_DECISIONS,
    append_operator_correction,
    build_operator_correction_event,
    correction_id_exists,
    correction_summary,
    duplicate_queue_item_ids,
    normalize_action_list,
    parse_captured_at,
    read_json,
    read_correction_events,
)


IMPORT_READINESS_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready"
)
IMPORT_READINESS_JSON_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json"
)
IMPORT_RAW_HANDOFF_VERIFY_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --verify-raw-handoff"
)
IMPORT_RAW_HANDOFF_VERIFY_JSON_COMMAND = (
    "python3 scripts/run_dallas_import_pipeline.py --verify-raw-handoff --format json"
)
IMPORT_REFRESH_COMMAND = "python3 scripts/run_dallas_import_pipeline.py --require-ready"
IMPORT_READINESS_SUMMARY_PATH = (
    ROOT / "generated" / "pipeline" / "dallas-import-pipeline-summary-v1" / "summary.json"
)
DEFAULT_IMPORT_RAW_DIR = ROOT / "generated" / "raw" / "dallas-electrician-import-sample-v2"
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
RAW_IMPORT_APPEND_PREFLIGHT_CHECKS = (
    "raw_files_present",
    "required_fields_complete",
    "identity_keys_present_and_unique",
    "date_values_parse",
    "relationships_resolve",
)
RAW_IMPORT_SCOPE_EXCLUSION_FIELDS = {
    "permits.csv": (
        "excluded_by_city",
        "excluded_by_trade",
        "excluded_by_work_class",
    ),
    "inspections.csv": ("excluded_by_unimported_permit",),
    "contractors.csv": ("excluded_by_license_type",),
    "rule_documents.csv": ("excluded_by_missing_title",),
}
IMPORT_COUNT_FIELDS = (
    "permits",
    "inspections",
    "tasks",
    "label_reviews",
    "source_records",
)
COVERAGE_THIN_COUNT_FIELDS = (
    "result_states",
    "failure_reasons",
    "pattern_slices",
    "next_action_groups",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument(
        "--list-queue-items",
        action="store_true",
        help="print queue item IDs, recommended actions, and correction status without appending corrections",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="with --list-queue-items, print only queue items that do not have a captured correction",
    )
    parser.add_argument(
        "--next-missing",
        action="store_true",
        help="print the next queue item missing a correction plus accept/reject commands and edit templates",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print correction ledger progress without appending corrections",
    )
    parser.add_argument(
        "--list-patterns",
        action="store_true",
        help="print accepted operator-correction patterns from the generated action queue",
    )
    parser.add_argument(
        "--validate-ledger",
        action="store_true",
        help="validate captured correction events against the current queue and action catalog",
    )
    parser.add_argument(
        "--smoke-check",
        action="store_true",
        help=(
            "run a non-mutating readiness check for the next-missing correction path, "
            "including dry-run event construction"
        ),
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="with --validate-ledger, fail if any current queue item is missing a correction",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help=(
            "output format for read-only modes and correction dry-runs/appends; "
            "JSON remains the default automation contract"
        ),
    )
    parser.add_argument("--queue-item-id")
    parser.add_argument(
        "--use-next-missing",
        action="store_true",
        help="with --decision, record against the first queue item missing a correction",
    )
    parser.add_argument(
        "--expected-next-missing-id",
        help="with --use-next-missing, fail if the current first missing queue item has changed",
    )
    parser.add_argument("--decision", choices=("accepted", "rejected", "edited"))
    parser.add_argument(
        "--corrected-actions",
        default="",
        help="comma-separated action IDs; required for edited corrections",
    )
    parser.add_argument("--operator-note", default="")
    parser.add_argument("--source", default="operator-correction-cli")
    parser.add_argument(
        "--require-missing",
        action="store_true",
        help="refuse to dry-run or append if the selected queue item already has a captured correction",
    )
    parser.add_argument(
        "--captured-at",
        default=None,
        help="optional ISO timestamp for deterministic replay, for example 2026-05-23T00:00:00Z",
    )
    parser.add_argument("--dry-run", action="store_true", help="validate and print the event without appending")
    args = parser.parse_args()
    read_only_mode = (
        args.list_queue_items
        or args.next_missing
        or args.summary
        or args.list_patterns
        or args.validate_ledger
        or args.smoke_check
    )
    if args.missing_only and not args.list_queue_items:
        parser.error("--missing-only requires --list-queue-items")
    if args.require_complete and not args.validate_ledger:
        parser.error("--require-complete requires --validate-ledger")
    if args.use_next_missing and read_only_mode:
        parser.error("--use-next-missing records a decision and cannot be combined with read-only modes")
    if args.use_next_missing and args.queue_item_id:
        parser.error("--use-next-missing cannot be combined with --queue-item-id")
    if args.expected_next_missing_id and not args.use_next_missing:
        parser.error("--expected-next-missing-id requires --use-next-missing")
    if not read_only_mode:
        if not args.queue_item_id and not args.use_next_missing:
            parser.error(
                "--queue-item-id or --use-next-missing is required unless --list-queue-items, "
                "--next-missing, --summary, --validate-ledger, or --smoke-check is used"
            )
        if not args.decision:
            parser.error(
                "--decision is required unless --list-queue-items, --next-missing, --summary, "
                "--validate-ledger, or --smoke-check is used"
            )
    return args


def queue_item_has_correction(ledger_path: Path, queue_item_id: str) -> bool:
    summary = correction_summary(ledger_path)
    latest_by_queue_item = summary.get("latest_by_queue_item", {})
    return isinstance(latest_by_queue_item, dict) and queue_item_id in latest_by_queue_item


def require_queue_item_missing(ledger_path: Path, queue_item_id: str) -> None:
    if queue_item_has_correction(ledger_path, queue_item_id):
        raise ValueError(
            f"queue_item_id already has a captured correction: {queue_item_id}; "
            "omit --require-missing to append an intentional update"
        )


def correction_progress(
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> dict[str, Any]:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("queue file must contain a queue list")

    summary = correction_summary(ledger_path)
    latest_by_queue_item = summary.get("latest_by_queue_item", {})
    if not isinstance(latest_by_queue_item, dict):
        latest_by_queue_item = {}

    queue_item_ids = [
        item.get("queue_item_id")
        for item in queue
        if isinstance(item, dict) and isinstance(item.get("queue_item_id"), str)
    ]
    corrected_ids = {queue_item_id for queue_item_id in queue_item_ids if queue_item_id in latest_by_queue_item}
    missing_ids = [queue_item_id for queue_item_id in queue_item_ids if queue_item_id not in corrected_ids]

    return {
        "workflow_id": payload.get("workflow_id"),
        "queue_items": len(queue_item_ids),
        "queue_items_with_corrections": len(corrected_ids),
        "queue_items_missing_corrections": len(missing_ids),
        "missing_queue_item_ids": missing_ids,
        "operator_correction_summary": summary,
        "next_missing_command": (
            read_only_command("--next-missing", queue_path, ledger_path, output_format=output_format)
            if missing_ids
            else None
        ),
        "validation_command": validate_ledger_command(
            queue_path,
            ledger_path,
            output_format=output_format,
        ),
        "completion_validation_command": validate_ledger_command(
            queue_path,
            ledger_path,
            output_format=output_format,
            require_complete=True,
        ),
        "patterns_command": read_only_command(
            "--list-patterns",
            queue_path,
            ledger_path,
            output_format=output_format,
        ),
        "import_readiness_command": IMPORT_READINESS_COMMAND if not missing_ids else None,
        "import_readiness_json_command": IMPORT_READINESS_JSON_COMMAND if not missing_ids else None,
        "last_import_readiness_summary": (
            import_readiness_snapshot() if not missing_ids else None
        ),
    }


def operator_correction_patterns(
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> dict[str, Any]:
    payload = read_json(queue_path)
    patterns = payload.get("operator_correction_patterns")
    if not isinstance(patterns, dict):
        patterns = {
            "source": "generated action queue",
            "accepted_latest_corrections": 0,
            "accepted_pattern_count": 0,
            "patterns": [],
        }

    progress = correction_progress(queue_path, ledger_path)
    return {
        "workflow_id": payload.get("workflow_id"),
        "queue_items": progress["queue_items"],
        "queue_items_with_corrections": progress["queue_items_with_corrections"],
        "queue_items_missing_corrections": progress["queue_items_missing_corrections"],
        "source": patterns.get("source"),
        "accepted_latest_corrections": patterns.get("accepted_latest_corrections", 0),
        "accepted_pattern_count": patterns.get("accepted_pattern_count", 0),
        "patterns": patterns.get("patterns", []),
        "completion_validation_command": validate_ledger_command(
            queue_path,
            ledger_path,
            output_format=output_format,
            require_complete=True,
        ),
    }


def action_catalog(queue_path: Path) -> dict[str, Any]:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("queue file must contain a queue list")

    actions: dict[str, dict[str, Any]] = {}
    for item in queue:
        if not isinstance(item, dict):
            continue
        queue_item_id = item.get("queue_item_id")
        if not isinstance(queue_item_id, str):
            continue
        for action_id in item.get("recommended_actions", []):
            if not isinstance(action_id, str):
                continue
            action = actions.setdefault(
                action_id,
                {"action_id": action_id, "queue_item_count": 0, "queue_item_ids": []},
            )
            action["queue_item_count"] += 1
            action["queue_item_ids"].append(queue_item_id)

    return {
        "workflow_id": payload.get("workflow_id"),
        "action_ids": sorted(actions),
        "actions": [actions[action_id] for action_id in sorted(actions)],
    }


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def repo_path(path: Path | str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def csv_data_row_count(path: Path | str) -> int | None:
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for row in reader if any(cell.strip() for cell in row))


def csv_header(path: Path | str) -> list[str] | None:
    resolved = repo_path(path)
    if not resolved.exists():
        return None
    with resolved.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return []
        return [cell.strip() for cell in header if cell.strip()]


def csv_dict_data_rows(path: Path | str) -> list[dict[str, str]] | None:
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


def csv_dict_data_rows_with_numbers(
    path: Path | str,
) -> list[tuple[int, dict[str, str]]] | None:
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


def raw_cell(row: dict[str, Any], field: str) -> str:
    return str(row.get(field) or "").strip()


def raw_cell_lower(row: dict[str, Any], field: str) -> str:
    return raw_cell(row, field).lower()


def raw_import_file_row_counts(raw_dir: str) -> dict[str, int | None]:
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: csv_data_row_count(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def file_fingerprint(path: Path | str) -> dict[str, Any] | None:
    resolved = repo_path(path)
    if not resolved.exists():
        return None

    digest = hashlib.sha256()
    byte_count = 0
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return {
        "algorithm": "sha256",
        "byte_count": byte_count,
        "sha256": digest.hexdigest(),
    }


def raw_import_file_fingerprints(raw_dir: str) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: file_fingerprint(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_import_file_next_append_rows(
    row_counts: dict[str, int | None],
) -> dict[str, int | None]:
    return {
        file_name: row_counts[file_name] + 2
        if isinstance(row_counts.get(file_name), int)
        else None
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_import_file_headers(raw_dir: str) -> dict[str, list[str] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    return {
        file_name: csv_header(resolved_raw_dir / file_name)
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_import_file_required_fields() -> dict[str, list[str]]:
    return {
        file_name: list(RAW_IMPORT_REQUIRED_FIELDS[file_name])
        for file_name in RAW_IMPORT_FILE_NAMES
    }


def raw_import_file_identity_key_checks(raw_dir: str) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    checks: dict[str, dict[str, Any] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / file_name)
        identity_fields = RAW_IMPORT_IDENTITY_FIELDS[file_name]
        if rows is None:
            checks[file_name] = None
            continue

        row_numbers_by_key: dict[tuple[str, ...], list[int]] = {}
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


def raw_import_file_value_profiles(raw_dir: str) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    profiles: dict[str, dict[str, Any] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows(resolved_raw_dir / file_name)
        if rows is None:
            profiles[file_name] = None
            continue

        field_profiles: dict[str, dict[str, Any]] = {}
        for field in RAW_IMPORT_VALUE_PROFILE_FIELDS[file_name]:
            counts: dict[str, int] = {}
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


def parse_raw_import_date(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def raw_import_file_date_profiles(raw_dir: str) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    profiles: dict[str, dict[str, Any] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        path = resolved_raw_dir / file_name
        rows = csv_dict_data_rows_with_numbers(path)
        headers = csv_header(path)
        if rows is None or headers is None:
            profiles[file_name] = None
            continue

        field_profiles: dict[str, dict[str, Any]] = {}
        for field in RAW_IMPORT_DATE_FIELDS[file_name]:
            blank_count = 0
            valid_date_count = 0
            invalid_examples: list[dict[str, Any]] = []
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


def add_raw_import_relationship_example(
    examples: list[dict[str, Any]],
    row_number: int,
    row: dict[str, Any],
    file_name: str,
) -> None:
    if len(examples) >= RAW_IMPORT_RELATIONSHIP_EXAMPLE_LIMIT:
        return
    examples.append(
        {
            "csv_row_number": row_number,
            "row": raw_import_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def raw_import_file_relationship_checks(
    raw_dir: str,
) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "inspections.csv"
    )
    contractor_rows = csv_dict_data_rows_with_numbers(
        resolved_raw_dir / "contractors.csv"
    )

    checks: dict[str, dict[str, Any] | None] = {}
    importable_permit_numbers: set[str] = set()
    all_permit_numbers: set[str] = set()
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

    importable_contractor_names: set[str] = set()
    all_contractor_names: set[str] = set()
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
        relationship: dict[str, Any] = {
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
                add_raw_import_relationship_example(
                    relationship["excluded_target_examples"],
                    row_number,
                    row,
                    "inspections.csv",
                )
            else:
                relationship["unmatched_target_rows"] += 1
                add_raw_import_relationship_example(
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
                add_raw_import_relationship_example(
                    relationship["excluded_target_examples"],
                    row_number,
                    row,
                    "permits.csv",
                )
            else:
                relationship["unmatched_target_rows"] += 1
                add_raw_import_relationship_example(
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


def raw_import_file_import_scope_counts(
    raw_dir: str,
) -> dict[str, dict[str, int] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    permit_rows = csv_dict_data_rows(resolved_raw_dir / "permits.csv")
    inspection_rows = csv_dict_data_rows(resolved_raw_dir / "inspections.csv")
    contractor_rows = csv_dict_data_rows(resolved_raw_dir / "contractors.csv")
    rule_document_rows = csv_dict_data_rows(resolved_raw_dir / "rule_documents.csv")

    counts: dict[str, dict[str, int] | None] = {}
    in_scope_permit_numbers: set[str] = set()
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


def raw_import_row_snapshot(
    row: dict[str, Any],
    fields: tuple[str, ...],
) -> dict[str, str]:
    return {field: raw_cell(row, field) for field in fields}


def add_raw_importable_example(
    examples: dict[str, list[dict[str, Any]] | None],
    file_name: str,
    row_number: int,
    row: dict[str, Any],
) -> None:
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
            "row": raw_import_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def add_raw_import_exclusion_example(
    examples: dict[str, list[dict[str, Any]] | None],
    file_name: str,
    row_number: int,
    reason: str,
    row: dict[str, Any],
) -> None:
    file_examples = examples.get(file_name)
    if file_examples is None or len(file_examples) >= RAW_IMPORT_EXCLUSION_EXAMPLE_LIMIT:
        return
    file_examples.append(
        {
            "csv_row_number": row_number,
            "reason": reason,
            "row": raw_import_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    )


def raw_import_file_importable_examples(
    raw_dir: str,
) -> dict[str, list[dict[str, Any]] | None]:
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
    examples: dict[str, list[dict[str, Any]] | None] = {
        file_name: None if rows_by_file[file_name] is None else []
        for file_name in RAW_IMPORT_FILE_NAMES
    }

    in_scope_permit_numbers: set[str] = set()
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
                add_raw_importable_example(
                    examples,
                    "permits.csv",
                    row_number,
                    row,
                )

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


def raw_import_file_exclusion_examples(
    raw_dir: str,
) -> dict[str, list[dict[str, Any]] | None]:
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
    examples: dict[str, list[dict[str, Any]] | None] = {
        file_name: None if rows_by_file[file_name] is None else []
        for file_name in RAW_IMPORT_FILE_NAMES
    }

    in_scope_permit_numbers: set[str] = set()
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
                add_raw_import_exclusion_example(
                    examples,
                    "permits.csv",
                    row_number,
                    reason,
                    row,
                )

    if inspection_rows is not None:
        for row_number, row in inspection_rows:
            if raw_cell(row, "permit_number") not in in_scope_permit_numbers:
                add_raw_import_exclusion_example(
                    examples,
                    "inspections.csv",
                    row_number,
                    "excluded_by_unimported_permit",
                    row,
                )

    if contractor_rows is not None:
        for row_number, row in contractor_rows:
            if "electrical" not in raw_cell_lower(row, "license_type"):
                add_raw_import_exclusion_example(
                    examples,
                    "contractors.csv",
                    row_number,
                    "excluded_by_license_type",
                    row,
                )

    if rule_document_rows is not None:
        for row_number, row in rule_document_rows:
            if not raw_cell(row, "title"):
                add_raw_import_exclusion_example(
                    examples,
                    "rule_documents.csv",
                    row_number,
                    "excluded_by_missing_title",
                    row,
                )

    return examples


def raw_import_file_optional_fields(
    headers_by_file: dict[str, list[str] | None],
    required_fields_by_file: dict[str, list[str]],
) -> dict[str, list[str] | None]:
    optional_fields: dict[str, list[str] | None] = {}
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


def raw_import_file_append_templates(
    headers_by_file: dict[str, list[str] | None],
    required_fields_by_file: dict[str, list[str]],
) -> dict[str, dict[str, str] | None]:
    append_templates: dict[str, dict[str, str] | None] = {}
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


def csv_line(values: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="")
    writer.writerow(values)
    return buffer.getvalue()


def raw_import_file_append_csv_templates(
    headers_by_file: dict[str, list[str] | None],
    required_fields_by_file: dict[str, list[str]],
) -> dict[str, dict[str, str] | None]:
    append_templates: dict[str, dict[str, str] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        headers = headers_by_file.get(file_name)
        required_fields = set(required_fields_by_file.get(file_name, []))
        if not isinstance(headers, list):
            append_templates[file_name] = None
            continue
        append_templates[file_name] = {
            "header_line": csv_line(headers),
            "template_line": csv_line(
                ["<required>" if header in required_fields else "" for header in headers]
            ),
        }
    return append_templates


def raw_import_file_append_work_order(
    raw_dir: str,
    next_append_rows: dict[str, int | None],
    append_csv_templates: dict[str, dict[str, str] | None],
) -> dict[str, dict[str, Any] | None]:
    raw_dir = raw_dir.rstrip("/")
    work_order: dict[str, dict[str, Any] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        row_number = next_append_rows.get(file_name)
        csv_template = append_csv_templates.get(file_name)
        if not isinstance(row_number, int) or not isinstance(csv_template, dict):
            work_order[file_name] = None
            continue
        header_line = csv_template.get("header_line")
        template_line = csv_template.get("template_line")
        if not isinstance(header_line, str) or not isinstance(template_line, str):
            work_order[file_name] = None
            continue
        work_order[file_name] = {
            "file_path": f"{raw_dir}/{file_name}",
            "csv_row_number": row_number,
            "header_line": header_line,
            "template_line": template_line,
        }
    return work_order


def raw_import_file_append_sequence(
    append_work_order: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    if not isinstance(append_work_order, dict):
        return []

    sequence: list[dict[str, Any]] = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        item = append_work_order.get(file_name)
        if not isinstance(item, dict):
            sequence.append(
                {
                    "file_name": file_name,
                    "status": "missing",
                }
            )
            continue
        sequence.append(
            {
                "file_name": file_name,
                "status": "ready",
                "file_path": item.get("file_path"),
                "csv_row_number": item.get("csv_row_number"),
                "header_line": item.get("header_line"),
                "template_line": item.get("template_line"),
            }
        )
    return sequence


def raw_import_file_required_field_gaps(
    raw_dir: str,
    required_fields_by_file: dict[str, list[str]],
) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    gaps: dict[str, dict[str, Any] | None] = {}
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


def raw_import_file_last_data_rows(
    raw_dir: str,
) -> dict[str, dict[str, Any] | None]:
    resolved_raw_dir = repo_path(raw_dir)
    last_rows: dict[str, dict[str, Any] | None] = {}
    for file_name in RAW_IMPORT_FILE_NAMES:
        rows = csv_dict_data_rows_with_numbers(resolved_raw_dir / file_name)
        if not rows:
            last_rows[file_name] = None
            continue
        row_number, row = rows[-1]
        last_rows[file_name] = {
            "csv_row_number": row_number,
            "row": raw_import_row_snapshot(
                row,
                RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name],
            ),
        }
    return last_rows


def raw_import_file_append_preflight(
    row_counts: dict[str, int | None],
    fingerprints: dict[str, dict[str, Any] | None],
    required_field_gaps: dict[str, dict[str, Any] | None],
    identity_key_checks: dict[str, dict[str, Any] | None],
    date_profiles: dict[str, dict[str, Any] | None],
    relationship_checks: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    checks = {check_name: True for check_name in RAW_IMPORT_APPEND_PREFLIGHT_CHECKS}
    blockers: list[dict[str, Any]] = []

    def add_blocker(check_name: str, message: str, **details: Any) -> None:
        checks[check_name] = False
        blocker = {"check": check_name, "message": message}
        blocker.update(details)
        blockers.append(blocker)

    for file_name in RAW_IMPORT_FILE_NAMES:
        if not isinstance(row_counts.get(file_name), int) or not isinstance(
            fingerprints.get(file_name),
            dict,
        ):
            add_blocker(
                "raw_files_present",
                f"{file_name} is missing or unreadable",
                file_name=file_name,
            )

        required_gap = required_field_gaps.get(file_name)
        if not isinstance(required_gap, dict):
            add_blocker(
                "required_fields_complete",
                f"{file_name} required-field gap check is unavailable",
                file_name=file_name,
            )
        else:
            missing_headers = required_gap.get("missing_required_headers", [])
            rows_with_gaps = required_gap.get("rows_with_missing_required_fields")
            if missing_headers or rows_with_gaps:
                add_blocker(
                    "required_fields_complete",
                    f"{file_name} has missing importer-required fields",
                    file_name=file_name,
                    missing_required_headers=missing_headers,
                    rows_with_missing_required_fields=rows_with_gaps,
                )

        identity_check = identity_key_checks.get(file_name)
        if not isinstance(identity_check, dict):
            add_blocker(
                "identity_keys_present_and_unique",
                f"{file_name} identity-key check is unavailable",
                file_name=file_name,
            )
        else:
            duplicate_count = identity_check.get("duplicate_identity_key_count")
            missing_identity_rows = identity_check.get("rows_missing_identity")
            if duplicate_count or missing_identity_rows:
                add_blocker(
                    "identity_keys_present_and_unique",
                    f"{file_name} has missing or duplicated identity keys",
                    file_name=file_name,
                    duplicate_identity_key_count=duplicate_count,
                    rows_missing_identity=missing_identity_rows,
                )

        date_profile = date_profiles.get(file_name)
        if not isinstance(date_profile, dict):
            add_blocker(
                "date_values_parse",
                f"{file_name} date profile is unavailable",
                file_name=file_name,
            )
        else:
            fields = date_profile.get("fields")
            if not isinstance(fields, dict):
                fields = {}
            for field_name, field_profile in fields.items():
                invalid_count = (
                    field_profile.get("invalid_date_count")
                    if isinstance(field_profile, dict)
                    else None
                )
                if invalid_count:
                    add_blocker(
                        "date_values_parse",
                        f"{file_name}.{field_name} has invalid dates",
                        file_name=file_name,
                        field_name=field_name,
                        invalid_date_count=invalid_count,
                    )

    for relationship_name in RAW_IMPORT_RELATIONSHIP_CHECKS:
        relationship = relationship_checks.get(relationship_name)
        if not isinstance(relationship, dict):
            add_blocker(
                "relationships_resolve",
                f"{relationship_name} relationship check is unavailable",
                relationship_name=relationship_name,
            )
            continue
        unresolved_rows = relationship.get("unresolved_rows")
        if unresolved_rows:
            add_blocker(
                "relationships_resolve",
                f"{relationship_name} has unresolved raw rows",
                relationship_name=relationship_name,
                unresolved_rows=unresolved_rows,
                unmatched_target_rows=relationship.get("unmatched_target_rows"),
                missing_source_value_rows=relationship.get("missing_source_value_rows"),
            )

    if blockers:
        next_step = (
            "Resolve raw CSV append preflight blockers before adding more Dallas "
            "permit rows, then rerun the summary-only readiness check."
        )
    else:
        next_step = (
            "Raw CSV append preflight is clear; append new Dallas rows at "
            "`raw_file_next_append_rows`, then run `after_edit_command`."
        )

    return {
        "status": "passed" if not blockers else "blocked",
        "ready_for_append": not blockers,
        "checks": checks,
        "blockers": blockers,
        "next_step": next_step,
    }


def raw_import_file_row_counts_are_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), int) and value[file_name] >= 0
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_fingerprints_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        fingerprint = value.get(file_name)
        if not isinstance(fingerprint, dict):
            return False
        sha256 = fingerprint.get("sha256")
        byte_count = fingerprint.get("byte_count")
        if (
            fingerprint.get("algorithm") != "sha256"
            or not isinstance(byte_count, int)
            or byte_count < 0
            or not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            return False
    return True


def raw_import_file_next_append_rows_are_valid(
    value: Any,
    row_counts: Any,
) -> bool:
    if not raw_import_file_row_counts_are_valid(row_counts):
        return False
    expected_rows = raw_import_file_next_append_rows(row_counts)
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), int)
            and value[file_name] == expected_rows[file_name]
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_headers_are_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), list)
            and all(
                isinstance(header, str) and header.strip()
                for header in value[file_name]
            )
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_required_fields_are_valid(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), list)
            and value[file_name] == RAW_IMPORT_REQUIRED_FIELDS[file_name]
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_identity_key_checks_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        check = value.get(file_name)
        if not isinstance(check, dict):
            return False
        identity_fields = check.get("identity_fields")
        rows_checked = check.get("rows_checked")
        rows_with_identity = check.get("rows_with_identity")
        rows_missing_identity = check.get("rows_missing_identity")
        duplicate_key_count = check.get("duplicate_identity_key_count")
        duplicate_rows = check.get("rows_with_duplicate_identity")
        duplicate_examples = check.get("duplicate_identity_key_examples")
        if (
            identity_fields != RAW_IMPORT_IDENTITY_FIELDS[file_name]
            or not isinstance(rows_checked, int)
            or rows_checked < 0
            or not isinstance(rows_with_identity, int)
            or rows_with_identity < 0
            or rows_with_identity > rows_checked
            or not isinstance(rows_missing_identity, int)
            or rows_missing_identity < 0
            or rows_missing_identity > rows_checked
            or rows_with_identity + rows_missing_identity != rows_checked
            or not isinstance(duplicate_key_count, int)
            or duplicate_key_count < 0
            or not isinstance(duplicate_rows, int)
            or duplicate_rows < 0
            or duplicate_rows > rows_with_identity
            or not isinstance(duplicate_examples, list)
            or len(duplicate_examples) > RAW_IMPORT_IDENTITY_EXAMPLE_LIMIT
        ):
            return False

        expected_fields = set(RAW_IMPORT_IDENTITY_FIELDS[file_name])
        for example in duplicate_examples:
            if not isinstance(example, dict):
                return False
            identity_key = example.get("identity_key")
            row_numbers = example.get("csv_row_numbers")
            if (
                not isinstance(identity_key, dict)
                or set(identity_key) != expected_fields
                or any(not isinstance(key_value, str) for key_value in identity_key.values())
                or not isinstance(row_numbers, list)
                or len(row_numbers) < 2
                or any(not isinstance(row_number, int) or row_number < 2 for row_number in row_numbers)
            ):
                return False
    return True


def raw_import_file_value_profiles_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        profile = value.get(file_name)
        if not isinstance(profile, dict):
            return False
        rows_checked = profile.get("rows_checked")
        fields = profile.get("fields")
        if not isinstance(rows_checked, int) or rows_checked < 0:
            return False
        if not isinstance(fields, dict):
            return False
        if set(fields) != set(RAW_IMPORT_VALUE_PROFILE_FIELDS[file_name]):
            return False
        for field_profile in fields.values():
            if not isinstance(field_profile, dict):
                return False
            distinct_count = field_profile.get("distinct_value_count")
            blank_count = field_profile.get("blank_count")
            top_values = field_profile.get("top_values")
            if (
                not isinstance(distinct_count, int)
                or distinct_count < 0
                or not isinstance(blank_count, int)
                or blank_count < 0
                or blank_count > rows_checked
                or not isinstance(top_values, list)
                or len(top_values) > RAW_IMPORT_VALUE_PROFILE_LIMIT
                or len(top_values) > distinct_count
            ):
                return False
            for item in top_values:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"value", "count"}
                    or not isinstance(item.get("value"), str)
                    or not item["value"]
                    or not isinstance(item.get("count"), int)
                    or item["count"] <= 0
                    or item["count"] > rows_checked
                ):
                    return False
    return True


def raw_import_file_date_profiles_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        profile = value.get(file_name)
        if not isinstance(profile, dict):
            return False
        rows_checked = profile.get("rows_checked")
        fields = profile.get("fields")
        if not isinstance(rows_checked, int) or rows_checked < 0:
            return False
        if not isinstance(fields, dict):
            return False
        if set(fields) != set(RAW_IMPORT_DATE_FIELDS[file_name]):
            return False
        for field_profile in fields.values():
            if not isinstance(field_profile, dict):
                return False
            field_present = field_profile.get("field_present")
            date_format = field_profile.get("date_format")
            blank_count = field_profile.get("blank_count")
            valid_date_count = field_profile.get("valid_date_count")
            invalid_date_count = field_profile.get("invalid_date_count")
            earliest_date = field_profile.get("earliest_date")
            earliest_row = field_profile.get("earliest_csv_row_number")
            latest_date = field_profile.get("latest_date")
            latest_row = field_profile.get("latest_csv_row_number")
            invalid_examples = field_profile.get("invalid_examples")
            if (
                not isinstance(field_present, bool)
                or date_format != "YYYY-MM-DD"
                or not isinstance(blank_count, int)
                or blank_count < 0
                or not isinstance(valid_date_count, int)
                or valid_date_count < 0
                or not isinstance(invalid_date_count, int)
                or invalid_date_count < 0
                or blank_count + valid_date_count + invalid_date_count != rows_checked
                or not isinstance(invalid_examples, list)
                or len(invalid_examples) > RAW_IMPORT_DATE_EXAMPLE_LIMIT
            ):
                return False
            if valid_date_count == 0:
                if (
                    earliest_date is not None
                    or earliest_row is not None
                    or latest_date is not None
                    or latest_row is not None
                ):
                    return False
            elif (
                not isinstance(earliest_date, str)
                or parse_raw_import_date(earliest_date) is None
                or not isinstance(earliest_row, int)
                or earliest_row < 2
                or not isinstance(latest_date, str)
                or parse_raw_import_date(latest_date) is None
                or not isinstance(latest_row, int)
                or latest_row < 2
                or earliest_date > latest_date
            ):
                return False
            for example in invalid_examples:
                if (
                    not isinstance(example, dict)
                    or set(example) != {"csv_row_number", "value"}
                    or not isinstance(example.get("csv_row_number"), int)
                    or example["csv_row_number"] < 2
                    or not isinstance(example.get("value"), str)
                    or not example["value"]
                ):
                    return False
    return True


def raw_import_file_relationship_checks_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    expected_names = set(RAW_IMPORT_RELATIONSHIP_CHECKS)
    if set(value) != expected_names:
        return False

    expected_numeric_fields = (
        "rows_checked",
        "matched_importable_target_rows",
        "matched_excluded_target_rows",
        "unmatched_target_rows",
        "missing_source_value_rows",
        "unresolved_rows",
    )
    for relationship_name, expected_metadata in RAW_IMPORT_RELATIONSHIP_CHECKS.items():
        check = value.get(relationship_name)
        if not isinstance(check, dict):
            return False
        for field, expected_value in expected_metadata.items():
            if check.get(field) != expected_value:
                return False

        rows_checked = check.get("rows_checked")
        if not isinstance(rows_checked, int) or rows_checked < 0:
            return False
        for field in expected_numeric_fields[1:]:
            count = check.get(field)
            if not isinstance(count, int) or count < 0 or count > rows_checked:
                return False
        if (
            check["unresolved_rows"]
            != check["missing_source_value_rows"] + check["unmatched_target_rows"]
        ):
            return False
        if (
            check["matched_importable_target_rows"]
            + check["matched_excluded_target_rows"]
            + check["unmatched_target_rows"]
            + check["missing_source_value_rows"]
            != rows_checked
        ):
            return False

        source_file = expected_metadata["source_file"]
        expected_row_fields = set(RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[source_file])
        for examples_field in ("unmatched_examples", "excluded_target_examples"):
            examples = check.get(examples_field)
            if (
                not isinstance(examples, list)
                or len(examples) > RAW_IMPORT_RELATIONSHIP_EXAMPLE_LIMIT
            ):
                return False
            for example in examples:
                if not isinstance(example, dict):
                    return False
                row_number = example.get("csv_row_number")
                row = example.get("row")
                if (
                    not isinstance(row_number, int)
                    or row_number < 2
                    or not isinstance(row, dict)
                    or set(row) != expected_row_fields
                    or any(not isinstance(value, str) for value in row.values())
                ):
                    return False

        expected_keys = {
            *expected_metadata.keys(),
            *expected_numeric_fields,
            "unmatched_examples",
            "excluded_target_examples",
        }
        if set(check) != expected_keys:
            return False
    return True


def raw_import_file_import_scope_counts_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        scope = value.get(file_name)
        if not isinstance(scope, dict):
            return False
        rows_checked = scope.get("rows_checked")
        importable_rows = scope.get("importable_rows")
        excluded_rows = scope.get("excluded_rows")
        if (
            not isinstance(rows_checked, int)
            or rows_checked < 0
            or not isinstance(importable_rows, int)
            or importable_rows < 0
            or importable_rows > rows_checked
            or not isinstance(excluded_rows, int)
            or excluded_rows < 0
            or excluded_rows != rows_checked - importable_rows
        ):
            return False
        for field in RAW_IMPORT_SCOPE_EXCLUSION_FIELDS[file_name]:
            count = scope.get(field)
            if not isinstance(count, int) or count < 0 or count > rows_checked:
                return False
        expected_keys = {
            "rows_checked",
            "importable_rows",
            "excluded_rows",
            *RAW_IMPORT_SCOPE_EXCLUSION_FIELDS[file_name],
        }
        if set(scope) != expected_keys:
            return False
    return True


def raw_import_file_importable_examples_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        examples = value.get(file_name)
        if (
            not isinstance(examples, list)
            or len(examples) > RAW_IMPORT_IMPORTABLE_EXAMPLE_LIMIT
        ):
            return False
        expected_reason = RAW_IMPORT_IMPORTABLE_EXAMPLE_REASONS[file_name]
        expected_fields = set(RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name])
        for example in examples:
            if not isinstance(example, dict):
                return False
            row_number = example.get("csv_row_number")
            reason = example.get("reason")
            row = example.get("row")
            if (
                not isinstance(row_number, int)
                or row_number < 2
                or reason != expected_reason
                or not isinstance(row, dict)
                or set(row) != expected_fields
                or any(not isinstance(value, str) for value in row.values())
            ):
                return False
    return True


def raw_import_file_exclusion_examples_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        examples = value.get(file_name)
        if not isinstance(examples, list) or len(examples) > RAW_IMPORT_EXCLUSION_EXAMPLE_LIMIT:
            return False
        expected_reasons = set(RAW_IMPORT_SCOPE_EXCLUSION_FIELDS[file_name])
        expected_fields = set(RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name])
        for example in examples:
            if not isinstance(example, dict):
                return False
            row_number = example.get("csv_row_number")
            reason = example.get("reason")
            row = example.get("row")
            if (
                not isinstance(row_number, int)
                or row_number < 2
                or reason not in expected_reasons
                or not isinstance(row, dict)
                or set(row) != expected_fields
                or any(not isinstance(value, str) for value in row.values())
            ):
                return False
    return True


def raw_import_file_optional_fields_are_valid(
    value: Any,
    headers_by_file: Any,
    required_fields_by_file: Any,
) -> bool:
    if not isinstance(headers_by_file, dict) or not isinstance(
        required_fields_by_file,
        dict,
    ):
        return False
    expected_fields = raw_import_file_optional_fields(
        headers_by_file,
        required_fields_by_file,
    )
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), list)
            and value[file_name] == expected_fields[file_name]
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_append_templates_are_valid(
    value: Any,
    headers_by_file: Any,
    required_fields_by_file: Any,
) -> bool:
    if not isinstance(headers_by_file, dict) or not isinstance(
        required_fields_by_file,
        dict,
    ):
        return False
    expected_templates = raw_import_file_append_templates(
        headers_by_file,
        required_fields_by_file,
    )
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), dict)
            and value[file_name] == expected_templates[file_name]
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_append_csv_templates_are_valid(
    value: Any,
    headers_by_file: Any,
    required_fields_by_file: Any,
) -> bool:
    if not isinstance(headers_by_file, dict) or not isinstance(
        required_fields_by_file,
        dict,
    ):
        return False
    expected_templates = raw_import_file_append_csv_templates(
        headers_by_file,
        required_fields_by_file,
    )
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), dict)
            and value[file_name] == expected_templates[file_name]
            and isinstance(value[file_name].get("header_line"), str)
            and isinstance(value[file_name].get("template_line"), str)
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_append_work_order_is_valid(
    value: Any,
    raw_dir: Any,
    next_append_rows: Any,
    append_csv_templates: Any,
) -> bool:
    if (
        not isinstance(raw_dir, str)
        or not raw_dir.strip()
        or not isinstance(next_append_rows, dict)
        or not isinstance(append_csv_templates, dict)
    ):
        return False
    if not all(
        isinstance(next_append_rows.get(file_name), int)
        and next_append_rows[file_name] >= 2
        for file_name in RAW_IMPORT_FILE_NAMES
    ):
        return False
    expected_work_order = raw_import_file_append_work_order(
        raw_dir,
        next_append_rows,
        append_csv_templates,
    )
    return (
        isinstance(value, dict)
        and all(
            isinstance(value.get(file_name), dict)
            and value[file_name] == expected_work_order[file_name]
            and isinstance(value[file_name].get("file_path"), str)
            and isinstance(value[file_name].get("csv_row_number"), int)
            and isinstance(value[file_name].get("header_line"), str)
            and isinstance(value[file_name].get("template_line"), str)
            for file_name in RAW_IMPORT_FILE_NAMES
        )
    )


def raw_import_file_append_sequence_is_valid(value: Any, append_work_order: Any) -> bool:
    if not isinstance(append_work_order, dict):
        return False
    expected_sequence = raw_import_file_append_sequence(append_work_order)
    return (
        isinstance(value, list)
        and value == expected_sequence
        and len(value) == len(RAW_IMPORT_FILE_NAMES)
        and all(
            isinstance(item, dict)
            and item.get("file_name") in RAW_IMPORT_FILE_NAMES
            and item.get("status") in {"ready", "missing"}
            for item in value
        )
    )


def raw_import_file_required_field_gaps_are_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        gap = value.get(file_name)
        required_fields = RAW_IMPORT_REQUIRED_FIELDS[file_name]
        if not isinstance(gap, dict):
            return False
        rows_checked = gap.get("rows_checked")
        rows_with_gaps = gap.get("rows_with_missing_required_fields")
        missing_headers = gap.get("missing_required_headers")
        missing_counts = gap.get("missing_field_counts")
        if (
            not isinstance(rows_checked, int)
            or rows_checked < 0
            or not isinstance(rows_with_gaps, int)
            or rows_with_gaps < 0
            or rows_with_gaps > rows_checked
            or not isinstance(missing_headers, list)
            or any(not isinstance(field, str) for field in missing_headers)
            or not isinstance(missing_counts, dict)
        ):
            return False
        for field in required_fields:
            count = missing_counts.get(field)
            if not isinstance(count, int) or count < 0 or count > rows_checked:
                return False
        if set(missing_counts) != set(required_fields):
            return False
    return True


def raw_import_file_last_data_rows_are_valid(value: Any, row_counts: Any) -> bool:
    if not raw_import_file_row_counts_are_valid(row_counts):
        return False
    if not isinstance(value, dict):
        return False

    for file_name in RAW_IMPORT_FILE_NAMES:
        expected_count = row_counts[file_name]
        last_row = value.get(file_name)
        if expected_count == 0:
            if last_row is not None:
                return False
            continue
        expected_fields = set(RAW_IMPORT_EXCLUSION_EXAMPLE_FIELDS[file_name])
        if not isinstance(last_row, dict):
            return False
        row_number = last_row.get("csv_row_number")
        row = last_row.get("row")
        if (
            row_number != expected_count + 1
            or not isinstance(row, dict)
            or set(row) != expected_fields
            or any(not isinstance(value, str) for value in row.values())
        ):
            return False
    return True


def raw_import_file_append_preflight_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    status = value.get("status")
    ready = value.get("ready_for_append")
    checks = value.get("checks")
    blockers = value.get("blockers")
    next_step = value.get("next_step")
    if (
        status not in {"passed", "blocked"}
        or not isinstance(ready, bool)
        or ready != (status == "passed")
        or not isinstance(checks, dict)
        or set(checks) != set(RAW_IMPORT_APPEND_PREFLIGHT_CHECKS)
        or any(not isinstance(checks.get(check_name), bool) for check_name in checks)
        or not isinstance(blockers, list)
        or not isinstance(next_step, str)
        or not next_step.strip()
    ):
        return False

    for blocker in blockers:
        if not isinstance(blocker, dict):
            return False
        check_name = blocker.get("check")
        message = blocker.get("message")
        if (
            check_name not in RAW_IMPORT_APPEND_PREFLIGHT_CHECKS
            or not isinstance(message, str)
            or not message.strip()
        ):
            return False
        file_name = blocker.get("file_name")
        if file_name is not None and file_name not in RAW_IMPORT_FILE_NAMES:
            return False
        relationship_name = blocker.get("relationship_name")
        if (
            relationship_name is not None
            and relationship_name not in RAW_IMPORT_RELATIONSHIP_CHECKS
        ):
            return False

    failed_checks = {check_name for check_name, passed in checks.items() if not passed}
    blocker_checks = {blocker.get("check") for blocker in blockers}
    return bool(blockers) == (status == "blocked") and failed_checks == blocker_checks


def count_snapshot(value: Any, fields: tuple[str, ...]) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        field: raw_value
        for field in fields
        if isinstance((raw_value := value.get(field)), int)
    }


def list_snapshot(value: Any, fields: tuple[str, ...]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    snapshot: dict[str, list[str]] = {}
    for field in fields:
        raw_values = value.get(field)
        if isinstance(raw_values, list):
            snapshot[field] = [
                raw_value
                for raw_value in raw_values
                if isinstance(raw_value, str)
            ]
    return snapshot


def import_readiness_snapshot_context(summary: dict[str, Any]) -> dict[str, Any]:
    latest_import = summary.get("latest_import")
    if not isinstance(latest_import, dict):
        latest_import = {}
    coverage = summary.get("coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    workflow = summary.get("workflow")
    if not isinstance(workflow, dict):
        workflow = {}

    return {
        "latest_import_counts": count_snapshot(
            latest_import.get("counts"),
            IMPORT_COUNT_FIELDS,
        ),
        "coverage_thin_counts": count_snapshot(
            coverage.get("latest_thin_counts"),
            COVERAGE_THIN_COUNT_FIELDS,
        ),
        "coverage_thin_groups": list_snapshot(
            coverage.get("thin_groups"),
            COVERAGE_THIN_COUNT_FIELDS,
        ),
        "accepted_pattern_count": workflow.get("accepted_pattern_count"),
    }


def next_import_record_handoff(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = summary.get("inputs") if isinstance(summary, dict) else {}
    if not isinstance(inputs, dict):
        inputs = {}
    summary_handoff = (
        summary.get("next_import_record_handoff") if isinstance(summary, dict) else {}
    )
    if not isinstance(summary_handoff, dict):
        summary_handoff = {}
    raw_dir = inputs.get("raw_dir")
    if not isinstance(raw_dir, str) or not raw_dir.strip():
        raw_dir = display_path(DEFAULT_IMPORT_RAW_DIR)
    raw_dir = raw_dir.rstrip("/")
    raw_row_counts = summary_handoff.get("raw_file_row_counts")
    if not raw_import_file_row_counts_are_valid(raw_row_counts):
        raw_row_counts = raw_import_file_row_counts(raw_dir)
    raw_fingerprints = summary_handoff.get("raw_file_fingerprints")
    if not raw_import_file_fingerprints_are_valid(raw_fingerprints):
        raw_fingerprints = raw_import_file_fingerprints(raw_dir)
    raw_next_append_rows = summary_handoff.get("raw_file_next_append_rows")
    if not raw_import_file_next_append_rows_are_valid(
        raw_next_append_rows,
        raw_row_counts,
    ):
        raw_next_append_rows = raw_import_file_next_append_rows(raw_row_counts)
    raw_last_data_rows = summary_handoff.get("raw_file_last_data_rows")
    if not raw_import_file_last_data_rows_are_valid(
        raw_last_data_rows,
        raw_row_counts,
    ):
        raw_last_data_rows = raw_import_file_last_data_rows(raw_dir)
    raw_identity_key_checks = summary_handoff.get("raw_file_identity_key_checks")
    if not raw_import_file_identity_key_checks_are_valid(raw_identity_key_checks):
        raw_identity_key_checks = raw_import_file_identity_key_checks(raw_dir)
    raw_value_profiles = summary_handoff.get("raw_file_value_profiles")
    if not raw_import_file_value_profiles_are_valid(raw_value_profiles):
        raw_value_profiles = raw_import_file_value_profiles(raw_dir)
    raw_date_profiles = summary_handoff.get("raw_file_date_profiles")
    if not raw_import_file_date_profiles_are_valid(raw_date_profiles):
        raw_date_profiles = raw_import_file_date_profiles(raw_dir)
    raw_relationship_checks = summary_handoff.get("raw_file_relationship_checks")
    if not raw_import_file_relationship_checks_are_valid(raw_relationship_checks):
        raw_relationship_checks = raw_import_file_relationship_checks(raw_dir)
    raw_import_scope_counts = summary_handoff.get("raw_file_import_scope_counts")
    if not raw_import_file_import_scope_counts_are_valid(raw_import_scope_counts):
        raw_import_scope_counts = raw_import_file_import_scope_counts(raw_dir)
    raw_importable_examples = summary_handoff.get("raw_file_importable_examples")
    if not raw_import_file_importable_examples_are_valid(raw_importable_examples):
        raw_importable_examples = raw_import_file_importable_examples(raw_dir)
    raw_exclusion_examples = summary_handoff.get("raw_file_exclusion_examples")
    if not raw_import_file_exclusion_examples_are_valid(raw_exclusion_examples):
        raw_exclusion_examples = raw_import_file_exclusion_examples(raw_dir)
    raw_headers = summary_handoff.get("raw_file_headers")
    if not raw_import_file_headers_are_valid(raw_headers):
        raw_headers = raw_import_file_headers(raw_dir)
    raw_required_fields = summary_handoff.get("raw_file_required_fields")
    if not raw_import_file_required_fields_are_valid(raw_required_fields):
        raw_required_fields = raw_import_file_required_fields()
    raw_optional_fields = summary_handoff.get("raw_file_optional_fields")
    if not raw_import_file_optional_fields_are_valid(
        raw_optional_fields,
        raw_headers,
        raw_required_fields,
    ):
        raw_optional_fields = raw_import_file_optional_fields(
            raw_headers,
            raw_required_fields,
        )
    raw_append_templates = summary_handoff.get("raw_file_append_templates")
    if not raw_import_file_append_templates_are_valid(
        raw_append_templates,
        raw_headers,
        raw_required_fields,
    ):
        raw_append_templates = raw_import_file_append_templates(
            raw_headers,
            raw_required_fields,
        )
    raw_append_csv_templates = summary_handoff.get("raw_file_append_csv_templates")
    if not raw_import_file_append_csv_templates_are_valid(
        raw_append_csv_templates,
        raw_headers,
        raw_required_fields,
    ):
        raw_append_csv_templates = raw_import_file_append_csv_templates(
            raw_headers,
            raw_required_fields,
        )
    raw_append_work_order = summary_handoff.get("raw_file_append_work_order")
    if not raw_import_file_append_work_order_is_valid(
        raw_append_work_order,
        raw_dir,
        raw_next_append_rows,
        raw_append_csv_templates,
    ):
        raw_append_work_order = raw_import_file_append_work_order(
            raw_dir,
            raw_next_append_rows,
            raw_append_csv_templates,
        )
    raw_append_sequence = summary_handoff.get("raw_file_append_sequence")
    if not raw_import_file_append_sequence_is_valid(
        raw_append_sequence,
        raw_append_work_order,
    ):
        raw_append_sequence = raw_import_file_append_sequence(raw_append_work_order)
    raw_required_field_gaps = summary_handoff.get("raw_file_required_field_gaps")
    if not raw_import_file_required_field_gaps_are_valid(raw_required_field_gaps):
        raw_required_field_gaps = raw_import_file_required_field_gaps(
            raw_dir,
            raw_required_fields,
        )
    raw_append_preflight = summary_handoff.get("raw_file_append_preflight")
    if not raw_import_file_append_preflight_is_valid(raw_append_preflight):
        raw_append_preflight = raw_import_file_append_preflight(
            raw_row_counts,
            raw_fingerprints,
            raw_required_field_gaps,
            raw_identity_key_checks,
            raw_date_profiles,
            raw_relationship_checks,
        )
    return {
        "raw_dir": raw_dir,
        "raw_files": [f"{raw_dir}/{file_name}" for file_name in RAW_IMPORT_FILE_NAMES],
        "raw_file_row_counts": raw_row_counts,
        "raw_file_fingerprints": raw_fingerprints,
        "raw_file_next_append_rows": raw_next_append_rows,
        "raw_file_last_data_rows": raw_last_data_rows,
        "raw_file_identity_key_checks": raw_identity_key_checks,
        "raw_file_value_profiles": raw_value_profiles,
        "raw_file_date_profiles": raw_date_profiles,
        "raw_file_relationship_checks": raw_relationship_checks,
        "raw_file_import_scope_counts": raw_import_scope_counts,
        "raw_file_importable_examples": raw_importable_examples,
        "raw_file_exclusion_examples": raw_exclusion_examples,
        "raw_file_headers": raw_headers,
        "raw_file_required_fields": raw_required_fields,
        "raw_file_optional_fields": raw_optional_fields,
        "raw_file_append_templates": raw_append_templates,
        "raw_file_append_csv_templates": raw_append_csv_templates,
        "raw_file_append_work_order": raw_append_work_order,
        "raw_file_append_sequence": raw_append_sequence,
        "raw_file_required_field_gaps": raw_required_field_gaps,
        "raw_file_append_preflight": raw_append_preflight,
        "after_edit_command": IMPORT_REFRESH_COMMAND,
        "readiness_check_command": IMPORT_READINESS_JSON_COMMAND,
        "raw_handoff_verification_command": IMPORT_RAW_HANDOFF_VERIFY_COMMAND,
        "raw_handoff_verification_json_command": IMPORT_RAW_HANDOFF_VERIFY_JSON_COMMAND,
    }


def next_import_record_handoff_is_valid(handoff: Any) -> bool:
    if not isinstance(handoff, dict):
        return False
    raw_dir = handoff.get("raw_dir")
    raw_files = handoff.get("raw_files")
    return (
        isinstance(raw_dir, str)
        and bool(raw_dir.strip())
        and isinstance(raw_files, list)
        and len(raw_files) == len(RAW_IMPORT_FILE_NAMES)
        and all(isinstance(raw_file, str) and raw_file.endswith(".csv") for raw_file in raw_files)
        and raw_import_file_row_counts_are_valid(handoff.get("raw_file_row_counts"))
        and raw_import_file_fingerprints_are_valid(
            handoff.get("raw_file_fingerprints"),
        )
        and raw_import_file_next_append_rows_are_valid(
            handoff.get("raw_file_next_append_rows"),
            handoff.get("raw_file_row_counts"),
        )
        and raw_import_file_last_data_rows_are_valid(
            handoff.get("raw_file_last_data_rows"),
            handoff.get("raw_file_row_counts"),
        )
        and raw_import_file_identity_key_checks_are_valid(
            handoff.get("raw_file_identity_key_checks"),
        )
        and raw_import_file_value_profiles_are_valid(
            handoff.get("raw_file_value_profiles"),
        )
        and raw_import_file_date_profiles_are_valid(
            handoff.get("raw_file_date_profiles"),
        )
        and raw_import_file_relationship_checks_are_valid(
            handoff.get("raw_file_relationship_checks"),
        )
        and raw_import_file_import_scope_counts_are_valid(
            handoff.get("raw_file_import_scope_counts"),
        )
        and raw_import_file_importable_examples_are_valid(
            handoff.get("raw_file_importable_examples"),
        )
        and raw_import_file_exclusion_examples_are_valid(
            handoff.get("raw_file_exclusion_examples"),
        )
        and raw_import_file_headers_are_valid(handoff.get("raw_file_headers"))
        and raw_import_file_required_fields_are_valid(handoff.get("raw_file_required_fields"))
        and raw_import_file_optional_fields_are_valid(
            handoff.get("raw_file_optional_fields"),
            handoff.get("raw_file_headers"),
            handoff.get("raw_file_required_fields"),
        )
        and raw_import_file_append_templates_are_valid(
            handoff.get("raw_file_append_templates"),
            handoff.get("raw_file_headers"),
            handoff.get("raw_file_required_fields"),
        )
        and raw_import_file_append_csv_templates_are_valid(
            handoff.get("raw_file_append_csv_templates"),
            handoff.get("raw_file_headers"),
            handoff.get("raw_file_required_fields"),
        )
        and raw_import_file_append_work_order_is_valid(
            handoff.get("raw_file_append_work_order"),
            handoff.get("raw_dir"),
            handoff.get("raw_file_next_append_rows"),
            handoff.get("raw_file_append_csv_templates"),
        )
        and raw_import_file_append_sequence_is_valid(
            handoff.get("raw_file_append_sequence"),
            handoff.get("raw_file_append_work_order"),
        )
        and raw_import_file_required_field_gaps_are_valid(
            handoff.get("raw_file_required_field_gaps"),
        )
        and raw_import_file_append_preflight_is_valid(
            handoff.get("raw_file_append_preflight"),
        )
        and handoff.get("after_edit_command") == IMPORT_REFRESH_COMMAND
        and handoff.get("readiness_check_command") == IMPORT_READINESS_JSON_COMMAND
        and (
            handoff.get("raw_handoff_verification_command")
            == IMPORT_RAW_HANDOFF_VERIFY_COMMAND
        )
        and (
            handoff.get("raw_handoff_verification_json_command")
            == IMPORT_RAW_HANDOFF_VERIFY_JSON_COMMAND
        )
    )


def import_readiness_snapshot(path: Path = IMPORT_READINESS_SUMMARY_PATH) -> dict[str, Any]:
    summary_path = display_path(path)
    report_path = display_path(path.with_name("summary.md"))
    if not path.exists():
        return {
            "status": "missing",
            "ready_for_next_import_records": None,
            "blockers": [],
            "next_step": None,
            "dataset_id": None,
            "summary_json_path": summary_path,
            "summary_report_path": report_path,
            "refresh_command": IMPORT_READINESS_COMMAND,
            "refresh_json_command": IMPORT_READINESS_JSON_COMMAND,
            "latest_import_counts": {},
            "coverage_thin_counts": {},
            "coverage_thin_groups": {},
            "accepted_pattern_count": None,
            "next_import_record_handoff": next_import_record_handoff(),
        }

    try:
        summary = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "unreadable",
            "ready_for_next_import_records": None,
            "blockers": ["pipeline_summary_unreadable"],
            "error": str(exc),
            "next_step": None,
            "dataset_id": None,
            "summary_json_path": summary_path,
            "summary_report_path": report_path,
            "refresh_command": IMPORT_READINESS_COMMAND,
            "refresh_json_command": IMPORT_READINESS_JSON_COMMAND,
            "latest_import_counts": {},
            "coverage_thin_counts": {},
            "coverage_thin_groups": {},
            "accepted_pattern_count": None,
            "next_import_record_handoff": next_import_record_handoff(),
        }

    snapshot_context = import_readiness_snapshot_context(summary)
    readiness = summary.get("execution_readiness")
    if not isinstance(readiness, dict):
        return {
            "status": "unavailable",
            "ready_for_next_import_records": None,
            "blockers": ["execution_readiness_missing"],
            "next_step": None,
            "dataset_id": summary.get("dataset_id"),
            "summary_json_path": summary_path,
            "summary_report_path": report_path,
            "refresh_command": IMPORT_READINESS_COMMAND,
            "refresh_json_command": IMPORT_READINESS_JSON_COMMAND,
            "next_import_record_handoff": next_import_record_handoff(summary),
            **snapshot_context,
        }

    blockers = readiness.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = []
    return {
        "status": readiness.get("status"),
        "ready_for_next_import_records": readiness.get("ready_for_next_import_records"),
        "blockers": blockers,
        "next_step": readiness.get("next_step"),
        "dataset_id": summary.get("dataset_id"),
        "summary_json_path": summary_path,
        "summary_report_path": report_path,
        "refresh_command": readiness.get("summary_only_require_ready_command")
        or IMPORT_READINESS_COMMAND,
        "refresh_json_command": readiness.get("summary_only_require_ready_json_command")
        or IMPORT_READINESS_JSON_COMMAND,
        "next_import_record_handoff": next_import_record_handoff(summary),
        **snapshot_context,
    }


def read_only_command(
    flag: str,
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> str:
    args = [
        "python3",
        "scripts/record_operator_correction.py",
        *command_path_args(queue_path, ledger_path),
        flag,
    ]
    if output_format == "text":
        args.extend(["--format", "text"])
    return shlex.join(args)


def ledger_validation(
    queue_path: Path,
    ledger_path: Path,
    require_complete: bool = False,
    output_format: str = "json",
) -> dict[str, Any]:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("queue file must contain a queue list")

    queue_item_ids = [
        item.get("queue_item_id")
        for item in queue
        if isinstance(item, dict) and isinstance(item.get("queue_item_id"), str)
    ]
    duplicate_queue_ids = duplicate_queue_item_ids(queue)
    queue_items = {
        item.get("queue_item_id"): item
        for item in queue
        if isinstance(item, dict) and isinstance(item.get("queue_item_id"), str)
    }
    catalog = action_catalog(queue_path)
    known_action_ids = {
        action_id for action_id in catalog.get("action_ids", []) if isinstance(action_id, str)
    }
    events, invalid_lines = read_correction_events(ledger_path)
    issues: list[dict[str, Any]] = []

    def add_issue(event_number: int, event: dict[str, Any], field: str, message: str) -> None:
        correction_id = event.get("correction_id")
        issues.append(
            {
                "event_number": event_number,
                "correction_id": correction_id if isinstance(correction_id, str) else None,
                "queue_item_id": event.get("queue_item_id"),
                "field": field,
                "message": message,
            }
        )

    seen_correction_ids: dict[str, int] = {}
    for queue_item_id in duplicate_queue_ids:
        issues.append(
            {
                "event_number": None,
                "correction_id": None,
                "queue_item_id": queue_item_id,
                "field": "queue_item_id",
                "message": (
                    "queue file contains a duplicate queue_item_id; correction capture "
                    "requires unique queue item IDs"
                ),
            }
        )

    for event_number, event in enumerate(events, start=1):
        correction_id = event.get("correction_id")
        if not isinstance(correction_id, str) or not correction_id.strip():
            add_issue(event_number, event, "correction_id", "correction_id must be a non-empty string")
        elif correction_id in seen_correction_ids:
            add_issue(
                event_number,
                event,
                "correction_id",
                f"correction_id duplicates event {seen_correction_ids[correction_id]}",
            )
        else:
            seen_correction_ids[correction_id] = event_number

        queue_item_id = event.get("queue_item_id")
        item = queue_items.get(queue_item_id) if isinstance(queue_item_id, str) else None
        if not isinstance(queue_item_id, str) or not queue_item_id:
            add_issue(event_number, event, "queue_item_id", "queue_item_id must be a non-empty string")
        elif item is None:
            add_issue(event_number, event, "queue_item_id", "queue_item_id is not in the current queue")

        decision = event.get("decision")
        if decision not in VALID_CORRECTION_DECISIONS:
            add_issue(event_number, event, "decision", "decision must be accepted, rejected, or edited")

        captured_at = event.get("captured_at")
        if not isinstance(captured_at, str) or not captured_at.strip():
            add_issue(event_number, event, "captured_at", "captured_at must be a non-empty ISO timestamp")
        else:
            try:
                parse_captured_at(captured_at)
            except ValueError:
                add_issue(event_number, event, "captured_at", "captured_at must be parseable as an ISO timestamp")

        raw_reference_actions = event.get("reference_actions")
        raw_corrected_actions = event.get("corrected_actions")
        try:
            reference_actions = normalize_action_list(raw_reference_actions)
        except ValueError:
            reference_actions = []
            add_issue(event_number, event, "reference_actions", "reference_actions must be a list")
        try:
            corrected_actions = normalize_action_list(raw_corrected_actions)
        except ValueError:
            corrected_actions = []
            add_issue(event_number, event, "corrected_actions", "corrected_actions must be a list")

        if not isinstance(raw_reference_actions, list):
            add_issue(event_number, event, "reference_actions", "reference_actions must be stored as a list")
        if not isinstance(raw_corrected_actions, list):
            add_issue(event_number, event, "corrected_actions", "corrected_actions must be stored as a list")

        recommended_actions = normalize_action_list(item.get("recommended_actions")) if item else []
        if item and reference_actions != recommended_actions:
            add_issue(
                event_number,
                event,
                "reference_actions",
                "reference_actions do not match the current queue recommendation",
            )
        if item:
            trigger = item.get("trigger_inspection")
            if not isinstance(trigger, dict):
                trigger = {}
            expected_context = {
                "permit_id": item.get("permit_id"),
                "inspection_id": trigger.get("inspection_id"),
                "source_permit_number": item.get("source_permit_number"),
            }
            for field, expected_value in expected_context.items():
                if isinstance(expected_value, str) and event.get(field) != expected_value:
                    add_issue(
                        event_number,
                        event,
                        field,
                        f"{field} does not match the current queue item",
                    )

        unknown_actions = sorted(action for action in corrected_actions if action not in known_action_ids)
        if unknown_actions:
            add_issue(
                event_number,
                event,
                "corrected_actions",
                f"corrected_actions include unknown action IDs: {', '.join(unknown_actions)}",
            )

        if decision == "accepted" and item and corrected_actions != recommended_actions:
            add_issue(
                event_number,
                event,
                "corrected_actions",
                "accepted corrections must keep the current recommended actions",
            )
        elif decision == "rejected" and corrected_actions:
            add_issue(event_number, event, "corrected_actions", "rejected corrections must not keep actions")
        elif decision == "edited" and not corrected_actions:
            add_issue(event_number, event, "corrected_actions", "edited corrections require corrected actions")

    corrected_queue_item_ids = set()
    for event in events:
        queue_item_id = event.get("queue_item_id")
        if isinstance(queue_item_id, str) and queue_item_id in queue_items:
            corrected_queue_item_ids.add(queue_item_id)
    missing_queue_item_ids = [
        queue_item_id for queue_item_id in queue_item_ids if queue_item_id not in corrected_queue_item_ids
    ]
    if require_complete and missing_queue_item_ids:
        issues.append(
            {
                "event_number": None,
                "correction_id": None,
                "queue_item_id": "current queue",
                "field": "queue_correction_coverage",
                "message": (
                    f"{len(missing_queue_item_ids)} current queue items are missing required corrections"
                ),
            }
        )

    issue_count = invalid_lines + len(issues)
    return {
        "workflow_id": payload.get("workflow_id"),
        "ledger_path": display_path(ledger_path),
        "require_complete": require_complete,
        "queue_items": len(queue_items),
        "queue_items_with_corrections": len(corrected_queue_item_ids),
        "queue_items_missing_corrections": len(missing_queue_item_ids),
        "missing_queue_item_ids": missing_queue_item_ids,
        "duplicate_queue_item_ids": duplicate_queue_ids,
        "known_action_ids": sorted(known_action_ids),
        "events_checked": len(events),
        "invalid_lines": invalid_lines,
        "issue_count": issue_count,
        "status": "pass" if issue_count == 0 else "fail",
        "issues": issues,
        "next_missing_command": (
            read_only_command("--next-missing", queue_path, ledger_path, output_format=output_format)
            if missing_queue_item_ids
            else None
        ),
    }


def queue_listing(queue_path: Path, ledger_path: Path, missing_only: bool = False) -> dict[str, Any]:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("queue file must contain a queue list")

    progress = correction_progress(queue_path, ledger_path)
    summary = progress["operator_correction_summary"]
    latest_by_queue_item = summary.get("latest_by_queue_item", {})
    if not isinstance(latest_by_queue_item, dict):
        latest_by_queue_item = {}

    items = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        queue_item_id = item.get("queue_item_id")
        trigger = item.get("trigger_inspection")
        if not isinstance(trigger, dict):
            trigger = {}
        property_record = item.get("property")
        if not isinstance(property_record, dict):
            property_record = {}
        contractor = item.get("contractor")
        if not isinstance(contractor, dict):
            contractor = {}
        expected_followup = item.get("expected_followup")
        if not isinstance(expected_followup, dict):
            expected_followup = {}
        raw_evidence = item.get("evidence")
        evidence = [str(value) for value in raw_evidence] if isinstance(raw_evidence, list) else []
        latest_correction = latest_by_queue_item.get(queue_item_id)
        if isinstance(latest_correction, dict):
            correction = {
                "status": "captured",
                "decision": latest_correction.get("decision"),
                "correction_id": latest_correction.get("correction_id"),
                "captured_at": latest_correction.get("captured_at"),
                "corrected_actions": latest_correction.get("corrected_actions", []),
            }
        else:
            correction = {"status": "missing"}
        if missing_only and correction["status"] != "missing":
            continue
        items.append(
            {
                "queue_item_id": queue_item_id,
                "source_permit_number": item.get("source_permit_number"),
                "priority": item.get("priority"),
                "address": property_record.get("normalized_address"),
                "contractor": contractor.get("name"),
                "trigger_date": trigger.get("inspection_date"),
                "trigger_type": trigger.get("inspection_type_normalized"),
                "trigger_result": trigger.get("result_normalized"),
                "failure_reason": trigger.get("failure_reason_normalized"),
                "trigger_notes": trigger.get("notes_raw"),
                "expected_followup": {
                    "inspection_date": expected_followup.get("inspection_date"),
                    "inspection_type": expected_followup.get("inspection_type_normalized"),
                    "result": expected_followup.get("result_normalized"),
                    "notes": expected_followup.get("notes_raw"),
                },
                "evidence": evidence,
                "recommended_actions": item.get("recommended_actions", []),
                "correction": correction,
            }
        )

    return {
        "action_catalog": action_catalog(queue_path),
        "filter": "missing" if missing_only else "all",
        "workflow_id": progress["workflow_id"],
        "queue_items": progress["queue_items"],
        "listed_queue_items": len(items),
        "queue_items_with_corrections": progress["queue_items_with_corrections"],
        "queue_items_missing_corrections": progress["queue_items_missing_corrections"],
        "items": items,
    }


def command_path_args(queue_path: Path, ledger_path: Path) -> list[str]:
    args = []
    if queue_path != DEFAULT_QUEUE_PATH:
        args.extend(["--queue-path", str(queue_path)])
    if ledger_path != DEFAULT_LEDGER_PATH:
        args.extend(["--ledger-path", str(ledger_path)])
    return args


def record_command(
    queue_item_id: str | None,
    decision: str,
    queue_path: Path,
    ledger_path: Path,
    dry_run: bool = False,
    corrected_actions: str | None = None,
    operator_note: str | None = None,
    use_next_missing: bool = False,
    expected_next_missing_id: str | None = None,
    require_missing: bool = False,
    output_format: str = "json",
) -> str:
    args = [
        "python3",
        "scripts/record_operator_correction.py",
        *command_path_args(queue_path, ledger_path),
    ]
    if use_next_missing:
        args.append("--use-next-missing")
        if expected_next_missing_id:
            args.extend(["--expected-next-missing-id", expected_next_missing_id])
    else:
        if not queue_item_id:
            raise ValueError("queue_item_id is required unless use_next_missing is true")
        args.extend(["--queue-item-id", queue_item_id])
    args.extend(["--decision", decision])
    if corrected_actions is not None:
        args.extend(["--corrected-actions", corrected_actions])
    if operator_note is not None:
        args.extend(["--operator-note", operator_note])
    if require_missing:
        args.append("--require-missing")
    if output_format == "text":
        args.extend(["--format", "text"])
    if dry_run:
        args.append("--dry-run")
    return shlex.join(args)


def validate_ledger_command(
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
    require_complete: bool = False,
) -> str:
    args = [
        "python3",
        "scripts/record_operator_correction.py",
        *command_path_args(queue_path, ledger_path),
        "--validate-ledger",
    ]
    if require_complete:
        args.append("--require-complete")
    if output_format == "text":
        args.extend(["--format", "text"])
    return shlex.join(args)


def guarded_record_command_group(
    queue_item_id: str | None,
    queue_path: Path,
    ledger_path: Path,
    dry_run: bool = False,
    operator_note: str | None = None,
    use_next_missing: bool = False,
    expected_next_missing_id: str | None = None,
    output_format: str = "json",
) -> dict[str, str]:
    return {
        "accepted": record_command(
            queue_item_id,
            "accepted",
            queue_path,
            ledger_path,
            dry_run=dry_run,
            operator_note=operator_note,
            use_next_missing=use_next_missing,
            expected_next_missing_id=expected_next_missing_id,
            require_missing=True,
            output_format=output_format,
        ),
        "rejected": record_command(
            queue_item_id,
            "rejected",
            queue_path,
            ledger_path,
            dry_run=dry_run,
            operator_note=operator_note,
            use_next_missing=use_next_missing,
            expected_next_missing_id=expected_next_missing_id,
            require_missing=True,
            output_format=output_format,
        ),
        "edited_template": record_command(
            queue_item_id,
            "edited",
            queue_path,
            ledger_path,
            dry_run=dry_run,
            corrected_actions="<comma-separated-action-ids>",
            operator_note=operator_note,
            use_next_missing=use_next_missing,
            expected_next_missing_id=expected_next_missing_id,
            require_missing=True,
            output_format=output_format,
        ),
    }


def suggested_record_commands(
    item: dict[str, Any],
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> dict[str, Any]:
    queue_item_id = str(item.get("queue_item_id", ""))
    operator_note = "<operator-note>"
    return {
        "dry_run_next_missing": guarded_record_command_group(
            None,
            queue_path,
            ledger_path,
            dry_run=True,
            use_next_missing=True,
            expected_next_missing_id=queue_item_id,
            output_format=output_format,
        ),
        "dry_run_next_missing_with_note": guarded_record_command_group(
            None,
            queue_path,
            ledger_path,
            dry_run=True,
            operator_note=operator_note,
            use_next_missing=True,
            expected_next_missing_id=queue_item_id,
            output_format=output_format,
        ),
        "append_next_missing": guarded_record_command_group(
            None,
            queue_path,
            ledger_path,
            use_next_missing=True,
            expected_next_missing_id=queue_item_id,
            output_format=output_format,
        ),
        "append_next_missing_with_note": guarded_record_command_group(
            None,
            queue_path,
            ledger_path,
            operator_note=operator_note,
            use_next_missing=True,
            expected_next_missing_id=queue_item_id,
            output_format=output_format,
        ),
        "dry_run": guarded_record_command_group(
            queue_item_id,
            queue_path,
            ledger_path,
            dry_run=True,
            output_format=output_format,
        ),
        "dry_run_with_note": guarded_record_command_group(
            queue_item_id,
            queue_path,
            ledger_path,
            dry_run=True,
            operator_note=operator_note,
            output_format=output_format,
        ),
        "append": guarded_record_command_group(
            queue_item_id,
            queue_path,
            ledger_path,
            output_format=output_format,
        ),
        "append_with_note": guarded_record_command_group(
            queue_item_id,
            queue_path,
            ledger_path,
            operator_note=operator_note,
            output_format=output_format,
        ),
    }


def format_action_list(actions: Any) -> str:
    if not isinstance(actions, list) or not actions:
        return "(none)"
    return ", ".join(str(action) for action in actions)


def format_coverage_thin_groups(groups: Any) -> str:
    if not isinstance(groups, dict) or not groups:
        return "(none)"

    labels = []
    for field in COVERAGE_THIN_COUNT_FIELDS:
        values = groups.get(field)
        if isinstance(values, list) and values:
            labels.append(f"{field}={format_action_list(values)}")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_files(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    raw_files = handoff.get("raw_files")
    if not isinstance(raw_files, list):
        return "(none)"
    files = [raw_file for raw_file in raw_files if isinstance(raw_file, str) and raw_file]
    return ", ".join(files) if files else "(none)"


def format_raw_import_row_counts(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    counts = handoff.get("raw_file_row_counts")
    if not isinstance(counts, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        count = counts.get(file_name)
        labels.append(f"{file_name}={count if isinstance(count, int) else 'missing'}")
    return ", ".join(labels) if labels else "(none)"


def format_raw_import_append_preflight(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    preflight = handoff.get("raw_file_append_preflight")
    if not isinstance(preflight, dict):
        return "(none)"
    blockers = preflight.get("blockers", [])
    blocker_label = json.dumps(blockers, sort_keys=False) if blockers else "none"
    return (
        f"status={preflight.get('status')} "
        f"ready={str(preflight.get('ready_for_append')).lower()} "
        f"checks={json.dumps(preflight.get('checks', {}), sort_keys=True)} "
        f"blockers={blocker_label}"
    )


def format_raw_import_handoff_verification(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    command = handoff.get("raw_handoff_verification_command")
    json_command = handoff.get("raw_handoff_verification_json_command")
    if not isinstance(command, str) or not isinstance(json_command, str):
        return "(none)"
    return f"text={command}; json={json_command}"


def format_raw_import_fingerprints(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    fingerprints = handoff.get("raw_file_fingerprints")
    if not isinstance(fingerprints, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        fingerprint = fingerprints.get(file_name)
        if isinstance(fingerprint, dict):
            labels.append(
                f"{file_name}={fingerprint.get('algorithm')}:"
                f"{fingerprint.get('sha256')}"
                f" ({fingerprint.get('byte_count')} bytes)"
            )
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_next_append_rows(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    rows_by_file = handoff.get("raw_file_next_append_rows")
    if not isinstance(rows_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        row_number = rows_by_file.get(file_name)
        labels.append(
            f"{file_name}=row {row_number if isinstance(row_number, int) else 'missing'}"
        )
    return ", ".join(labels) if labels else "(none)"


def format_raw_import_last_data_rows(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    rows_by_file = handoff.get("raw_file_last_data_rows")
    if not isinstance(rows_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        last_row = rows_by_file.get(file_name)
        if isinstance(last_row, dict):
            labels.append(f"{file_name}={json.dumps(last_row, sort_keys=False)}")
        elif last_row is None:
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_identity_key_checks(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    checks_by_file = handoff.get("raw_file_identity_key_checks")
    if not isinstance(checks_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        check = checks_by_file.get(file_name)
        if not isinstance(check, dict):
            labels.append(f"{file_name}=missing")
            continue
        fields = check.get("identity_fields", [])
        examples = check.get("duplicate_identity_key_examples", [])
        labels.append(
            f"{file_name}=fields:{'|'.join(str(field) for field in fields) if fields else 'none'} "
            f"duplicates={check.get('duplicate_identity_key_count')} "
            f"duplicate_rows={check.get('rows_with_duplicate_identity')} "
            f"missing_identity_rows={check.get('rows_missing_identity')} "
            f"examples={json.dumps(examples, sort_keys=False)}"
        )
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_value_profiles(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    profiles_by_file = handoff.get("raw_file_value_profiles")
    if not isinstance(profiles_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        profile = profiles_by_file.get(file_name)
        if isinstance(profile, dict):
            labels.append(f"{file_name}={json.dumps(profile, sort_keys=False)}")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_date_profiles(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    profiles_by_file = handoff.get("raw_file_date_profiles")
    if not isinstance(profiles_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        profile = profiles_by_file.get(file_name)
        if isinstance(profile, dict):
            labels.append(f"{file_name}={json.dumps(profile, sort_keys=False)}")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_relationship_checks(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    checks_by_relationship = handoff.get("raw_file_relationship_checks")
    if not isinstance(checks_by_relationship, dict):
        return "(none)"
    labels = []
    for relationship_name in RAW_IMPORT_RELATIONSHIP_CHECKS:
        check = checks_by_relationship.get(relationship_name)
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
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_scope_counts(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    counts_by_file = handoff.get("raw_file_import_scope_counts")
    if not isinstance(counts_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        scope = counts_by_file.get(file_name)
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
    return "; ".join(labels) if labels else "(none)"


def format_raw_importable_examples(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    examples_by_file = handoff.get("raw_file_importable_examples")
    if not isinstance(examples_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        examples = examples_by_file.get(file_name)
        if isinstance(examples, list) and examples:
            labels.append(f"{file_name}={json.dumps(examples, sort_keys=False)}")
        elif isinstance(examples, list):
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_exclusion_examples(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    examples_by_file = handoff.get("raw_file_exclusion_examples")
    if not isinstance(examples_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        examples = examples_by_file.get(file_name)
        if isinstance(examples, list) and examples:
            labels.append(f"{file_name}={json.dumps(examples, sort_keys=False)}")
        elif isinstance(examples, list):
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_headers(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    headers_by_file = handoff.get("raw_file_headers")
    if not isinstance(headers_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        headers = headers_by_file.get(file_name)
        if isinstance(headers, list) and headers:
            labels.append(
                f"{file_name}={'|'.join(str(header) for header in headers)}"
            )
        elif isinstance(headers, list):
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_required_fields(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    fields_by_file = handoff.get("raw_file_required_fields")
    if not isinstance(fields_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        fields = fields_by_file.get(file_name)
        if isinstance(fields, list) and fields:
            labels.append(f"{file_name}={'|'.join(str(field) for field in fields)}")
        elif isinstance(fields, list):
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_optional_fields(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    fields_by_file = handoff.get("raw_file_optional_fields")
    if not isinstance(fields_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        fields = fields_by_file.get(file_name)
        if isinstance(fields, list) and fields:
            labels.append(f"{file_name}={'|'.join(str(field) for field in fields)}")
        elif isinstance(fields, list):
            labels.append(f"{file_name}=none")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_append_templates(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    templates_by_file = handoff.get("raw_file_append_templates")
    if not isinstance(templates_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        template = templates_by_file.get(file_name)
        if isinstance(template, dict):
            labels.append(f"{file_name}={json.dumps(template, sort_keys=False)}")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_append_csv_templates(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    templates_by_file = handoff.get("raw_file_append_csv_templates")
    if not isinstance(templates_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        template = templates_by_file.get(file_name)
        if isinstance(template, dict):
            labels.append(f"{file_name}={json.dumps(template, sort_keys=False)}")
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_append_work_order(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    work_order_by_file = handoff.get("raw_file_append_work_order")
    if not isinstance(work_order_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        item = work_order_by_file.get(file_name)
        if isinstance(item, dict):
            labels.append(
                f"{file_name}=file:{item.get('file_path')} "
                f"row:{item.get('csv_row_number')} "
                f"header:{item.get('header_line')} "
                f"template:{item.get('template_line')}"
            )
        else:
            labels.append(f"{file_name}=missing")
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_append_sequence(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    sequence = handoff.get("raw_file_append_sequence")
    if not isinstance(sequence, list):
        return "(none)"
    labels = []
    for item in sequence:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file_name")
        if item.get("status") != "ready":
            labels.append(f"{file_name}={item.get('status')}")
            continue
        labels.append(
            f"{file_name}=file:{item.get('file_path')} "
            f"row:{item.get('csv_row_number')} "
            f"header:{item.get('header_line')} "
            f"template:{item.get('template_line')}"
        )
    return "; ".join(labels) if labels else "(none)"


def format_raw_import_required_field_gaps(handoff: Any) -> str:
    if not isinstance(handoff, dict):
        return "(none)"
    gaps_by_file = handoff.get("raw_file_required_field_gaps")
    if not isinstance(gaps_by_file, dict):
        return "(none)"
    labels = []
    for file_name in RAW_IMPORT_FILE_NAMES:
        gap = gaps_by_file.get(file_name)
        if not isinstance(gap, dict):
            labels.append(f"{file_name}=missing")
            continue
        rows_checked = gap.get("rows_checked")
        rows_with_gaps = gap.get("rows_with_missing_required_fields")
        missing_headers = gap.get("missing_required_headers", [])
        missing_counts = gap.get("missing_field_counts", {})
        labels.append(
            f"{file_name}={rows_with_gaps}/{rows_checked} rows "
            f"(missing_headers={format_action_list(missing_headers)}, "
            f"field_counts={json.dumps(missing_counts, sort_keys=True)})"
        )
    return "; ".join(labels) if labels else "(none)"


def format_decision_counts(counts: Any) -> str:
    if not isinstance(counts, dict) or not counts:
        return "(none)"
    return ", ".join(f"{decision}={count}" for decision, count in sorted(counts.items()))


def command_parts(command: Any) -> list[str]:
    if not isinstance(command, str):
        return []
    try:
        return shlex.split(command)
    except ValueError:
        return []


def command_has_arg(command: Any, arg: str) -> bool:
    return arg in command_parts(command)


def command_arg_value(command: Any, arg: str) -> str | None:
    parts = command_parts(command)
    try:
        index = parts.index(arg)
    except ValueError:
        return None
    value_index = index + 1
    if value_index >= len(parts):
        return None
    return parts[value_index]


def command_group_failures(
    commands: Any,
    expected_next_missing_id: str | None,
    should_be_dry_run: bool,
    require_note: bool = False,
    expected_queue_item_id: str | None = None,
    expected_output_format: str | None = None,
) -> list[str]:
    if not isinstance(commands, dict):
        return ["command group is missing"]

    failures: list[str] = []
    command_fields = {
        "accepted": "accepted",
        "rejected": "rejected",
        "edited": "edited_template",
    }
    for decision, field in command_fields.items():
        command = commands.get(field)
        if not isinstance(command, str):
            failures.append(f"{decision} command is missing")
            continue
        uses_next_missing = command_has_arg(command, "--use-next-missing")
        fixed_queue_item_id = command_arg_value(command, "--queue-item-id")
        if (
            expected_next_missing_id
            and command_arg_value(command, "--expected-next-missing-id") != expected_next_missing_id
        ):
            failures.append(f"{decision} command missing expected next-missing ID")
        if expected_next_missing_id and not uses_next_missing:
            failures.append(f"{decision} shortcut command missing --use-next-missing")
        if expected_next_missing_id and fixed_queue_item_id is not None:
            failures.append(f"{decision} shortcut command should not include fixed queue item ID")
        if expected_queue_item_id and fixed_queue_item_id != expected_queue_item_id:
            failures.append(f"{decision} command missing fixed queue item ID")
        if expected_queue_item_id and uses_next_missing:
            failures.append(f"{decision} fixed-item command should not use --use-next-missing")
        if not command_has_arg(command, "--require-missing"):
            failures.append(f"{decision} command missing --require-missing")
        actual_output_format = command_arg_value(command, "--format")
        if expected_output_format == "text" and actual_output_format != "text":
            failures.append(f"{decision} command missing --format text")
        elif expected_output_format == "json" and actual_output_format is not None:
            failures.append(f"{decision} command should keep the default JSON output format")
        has_dry_run = command_has_arg(command, "--dry-run")
        if should_be_dry_run and not has_dry_run:
            failures.append(f"{decision} command missing --dry-run")
        if not should_be_dry_run and has_dry_run:
            failures.append(f"{decision} append command should not include --dry-run")
        if require_note and command_arg_value(command, "--operator-note") != "<operator-note>":
            failures.append(f"{decision} command missing operator-note placeholder")
        if decision == "edited" and command_arg_value(command, "--corrected-actions") != "<comma-separated-action-ids>":
            failures.append("edited command missing corrected-actions template")
    return failures


def pluralize(value: Any, singular: str, plural: str) -> str:
    return singular if value == 1 else plural


def format_progress_text(progress: dict[str, Any]) -> str:
    summary = progress.get("operator_correction_summary", {})
    if not isinstance(summary, dict):
        summary = {}
    missing_ids = progress.get("missing_queue_item_ids", [])
    if not isinstance(missing_ids, list):
        missing_ids = []

    lines = [
        "Dallas operator-correction progress",
        f"Workflow: {progress.get('workflow_id')}",
        (
            "Queue items: "
            f"{progress.get('queue_items')} total, "
            f"{progress.get('queue_items_with_corrections')} captured, "
            f"{progress.get('queue_items_missing_corrections')} missing"
        ),
        f"Ledger: {summary.get('ledger_path')}",
        f"Events: {summary.get('total_events', 0)}",
        f"Decisions: {format_decision_counts(summary.get('decision_counts'))}",
        f"Invalid ledger lines: {summary.get('invalid_lines', 0)}",
    ]
    if missing_ids:
        lines.append("Missing queue items:")
        lines.extend(f"- {queue_item_id}" for queue_item_id in missing_ids)
        if progress.get("next_missing_command"):
            lines.append(f"Next missing work order: {progress.get('next_missing_command')}")
    else:
        lines.append("Missing queue items: (none)")
        lines.append(f"Pattern review: {progress.get('patterns_command')}")
        if progress.get("import_readiness_command"):
            lines.append(f"Import readiness gate: {progress.get('import_readiness_command')}")
        if progress.get("import_readiness_json_command"):
            lines.append(
                f"Import readiness JSON gate: {progress.get('import_readiness_json_command')}"
            )
        readiness = progress.get("last_import_readiness_summary")
        if isinstance(readiness, dict):
            lines.append(
                "Last import readiness summary: "
                f"{readiness.get('status')} "
                f"({readiness.get('summary_json_path')})"
            )
            lines.append(
                "Ready for next import records: "
                f"{str(readiness.get('ready_for_next_import_records')).lower()}"
            )
            latest_counts = readiness.get("latest_import_counts", {})
            if isinstance(latest_counts, dict) and latest_counts:
                lines.append(
                    "Last import counts: "
                    f"permits={latest_counts.get('permits', 0)}, "
                    f"inspections={latest_counts.get('inspections', 0)}, "
                    f"tasks={latest_counts.get('tasks', 0)}, "
                    f"label_reviews={latest_counts.get('label_reviews', 0)}, "
                    f"source_records={latest_counts.get('source_records', 0)}"
                )
            accepted_pattern_count = readiness.get("accepted_pattern_count")
            if accepted_pattern_count is not None:
                lines.append(f"Last accepted patterns: {accepted_pattern_count}")
            coverage_thin_counts = readiness.get("coverage_thin_counts", {})
            if isinstance(coverage_thin_counts, dict) and coverage_thin_counts:
                lines.append(
                    "Last coverage thin counts: "
                    f"result_states={coverage_thin_counts.get('result_states', 0)}, "
                    f"failure_reasons={coverage_thin_counts.get('failure_reasons', 0)}, "
                    f"pattern_slices={coverage_thin_counts.get('pattern_slices', 0)}, "
                    f"next_action_groups={coverage_thin_counts.get('next_action_groups', 0)}"
                )
                lines.append(
                    "Last coverage thin groups: "
                    f"{format_coverage_thin_groups(readiness.get('coverage_thin_groups'))}"
                )
            blockers = readiness.get("blockers", [])
            if isinstance(blockers, list) and blockers:
                lines.append(f"Readiness blockers: {format_action_list(blockers)}")
            next_step = readiness.get("next_step")
            if isinstance(next_step, str) and next_step.strip():
                lines.append(f"Last import readiness next step: {next_step}")
            next_import_handoff = readiness.get("next_import_record_handoff")
            if isinstance(next_import_handoff, dict):
                lines.append(
                    "Next import raw files: "
                    f"{format_raw_import_files(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw row counts: "
                    f"{format_raw_import_row_counts(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append preflight: "
                    f"{format_raw_import_append_preflight(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw handoff verification: "
                    f"{format_raw_import_handoff_verification(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw fingerprints: "
                    f"{format_raw_import_fingerprints(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append rows: "
                    f"{format_raw_import_next_append_rows(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw last data rows: "
                    f"{format_raw_import_last_data_rows(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw identity key checks: "
                    f"{format_raw_import_identity_key_checks(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw value profiles: "
                    f"{format_raw_import_value_profiles(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw date profiles: "
                    f"{format_raw_import_date_profiles(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw relationship checks: "
                    f"{format_raw_import_relationship_checks(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw scope counts: "
                    f"{format_raw_import_scope_counts(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw importable examples: "
                    f"{format_raw_importable_examples(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw exclusion examples: "
                    f"{format_raw_import_exclusion_examples(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw headers: "
                    f"{format_raw_import_headers(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw required fields: "
                    f"{format_raw_import_required_fields(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw optional fields: "
                    f"{format_raw_import_optional_fields(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append templates: "
                    f"{format_raw_import_append_templates(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append CSV templates: "
                    f"{format_raw_import_append_csv_templates(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append work order: "
                    f"{format_raw_import_append_work_order(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw append sequence: "
                    f"{format_raw_import_append_sequence(next_import_handoff)}"
                )
                lines.append(
                    "Next import raw required-field gaps: "
                    f"{format_raw_import_required_field_gaps(next_import_handoff)}"
                )
                after_edit_command = next_import_handoff.get("after_edit_command")
                if isinstance(after_edit_command, str) and after_edit_command.strip():
                    lines.append(f"After raw CSV edits: {after_edit_command}")
    lines.append(f"Validate ledger: {progress.get('validation_command')}")
    lines.append(f"Completion gate: {progress.get('completion_validation_command')}")
    return "\n".join(lines)


def format_action_catalog_text(catalog: Any) -> list[str]:
    if not isinstance(catalog, dict):
        return ["Known action IDs: (none)"]

    actions = catalog.get("actions", [])
    if not isinstance(actions, list) or not actions:
        return ["Known action IDs: (none)"]

    lines = ["Known action IDs for edited decisions:"]
    for action in actions:
        if not isinstance(action, dict):
            continue
        count = action.get("queue_item_count")
        lines.append(f"- {action.get('action_id')} ({count} {pluralize(count, 'queue item', 'queue items')})")
    return lines


def format_count_map(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return "{}"
    return json.dumps(value, sort_keys=True)


def format_operator_patterns_text(payload: dict[str, Any]) -> str:
    lines = [
        "Dallas accepted operator-correction patterns",
        f"Workflow: {payload.get('workflow_id')}",
        (
            "Queue corrections: "
            f"{payload.get('queue_items_with_corrections')} captured, "
            f"{payload.get('queue_items_missing_corrections')} missing, "
            f"{payload.get('queue_items')} total"
        ),
        f"Accepted latest corrections: {payload.get('accepted_latest_corrections')}",
        f"Accepted patterns: {payload.get('accepted_pattern_count')}",
        f"Source: {payload.get('source')}",
        "",
        "Patterns:",
    ]
    patterns = payload.get("patterns", [])
    if not isinstance(patterns, list) or not patterns:
        lines.append("- (none)")
        lines.append(f"Completion gate: {payload.get('completion_validation_command')}")
        return "\n".join(lines)

    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        lines.extend(
            [
                f"- {pattern.get('pattern_id')} ({pattern.get('queue_item_count')} queue items)",
                f"  Actions: {format_action_list(pattern.get('corrected_actions'))}",
                f"  Labels: {format_action_list(pattern.get('corrected_action_labels'))}",
                f"  Trigger results: {format_count_map(pattern.get('trigger_result_counts'))}",
                f"  Failure reasons: {format_count_map(pattern.get('failure_reason_counts'))}",
                f"  Inspection types: {format_count_map(pattern.get('inspection_type_counts'))}",
                f"  Follow-up results: {format_count_map(pattern.get('observed_followup_result_counts'))}",
                f"  Queue items: {format_action_list(pattern.get('queue_item_ids'))}",
                f"  Example permits: {format_action_list(pattern.get('source_permit_numbers'))}",
            ]
        )
        note_examples = pattern.get("operator_note_examples")
        if isinstance(note_examples, list) and note_examples:
            lines.append("  Operator note examples:")
            lines.extend(f"  - {note}" for note in note_examples)
    lines.append("")
    lines.append(f"Completion gate: {payload.get('completion_validation_command')}")
    return "\n".join(lines)


def format_queue_listing_text(listing: dict[str, Any]) -> str:
    lines = [
        f"Dallas correction queue ({listing.get('filter')})",
        f"Workflow: {listing.get('workflow_id')}",
        (
            "Queue items: "
            f"{listing.get('queue_items')} total, "
            f"{listing.get('queue_items_with_corrections')} captured, "
            f"{listing.get('queue_items_missing_corrections')} missing, "
            f"{listing.get('listed_queue_items')} listed"
        ),
        "",
        *format_action_catalog_text(listing.get("action_catalog")),
        "",
        "Queue items:",
    ]

    items = listing.get("items", [])
    if not isinstance(items, list) or not items:
        lines.append("- (none)")
        return "\n".join(lines)

    for item in items:
        if not isinstance(item, dict):
            continue
        correction = item.get("correction", {})
        if not isinstance(correction, dict):
            correction = {}
        correction_status = correction.get("status")
        correction_detail = correction_status
        if correction_status == "captured":
            correction_detail = (
                f"captured {correction.get('decision')} "
                f"at {correction.get('captured_at')} "
                f"as {format_action_list(correction.get('corrected_actions'))}"
            )
        expected_followup = item.get("expected_followup", {})
        if not isinstance(expected_followup, dict):
            expected_followup = {}
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        lines.extend(
            [
                f"- {item.get('queue_item_id')} [{item.get('priority')}]",
                f"  Permit: {item.get('source_permit_number')}",
                f"  Address: {item.get('address')}",
                f"  Contractor: {item.get('contractor')}",
                (
                    "  Trigger: "
                    f"{item.get('trigger_date')} "
                    f"{item.get('trigger_type')} "
                    f"{item.get('trigger_result')} / "
                    f"{item.get('failure_reason')}"
                ),
                (
                    "  Follow-up observed: "
                    f"{expected_followup.get('inspection_date')} "
                    f"{expected_followup.get('inspection_type')} -> "
                    f"{expected_followup.get('result')}"
                ),
                f"  Recommended actions: {format_action_list(item.get('recommended_actions'))}",
                f"  Correction: {correction_detail}",
            ]
        )
        if evidence:
            lines.append("  Evidence:")
            lines.extend(f"  - {value}" for value in evidence)
    return "\n".join(lines)


def format_command_group(commands: Any, group_name: str) -> list[str]:
    if not isinstance(commands, dict):
        return [f"{group_name}: (none)"]
    return [
        f"{group_name}:",
        f"- accepted: {commands.get('accepted')}",
        f"- rejected: {commands.get('rejected')}",
        f"- edited: {commands.get('edited_template')}",
    ]


def format_next_missing_text(next_missing: dict[str, Any]) -> str:
    item = next_missing.get("item")
    lines = [
        "Dallas next missing operator correction",
        f"Workflow: {next_missing.get('workflow_id')}",
        (
            "Queue items: "
            f"{next_missing.get('queue_items')} total, "
            f"{next_missing.get('queue_items_with_corrections')} captured, "
            f"{next_missing.get('queue_items_missing_corrections')} missing"
        ),
    ]
    if not isinstance(item, dict):
        lines.append("Next queue item: (none)")
        lines.append(f"Validate ledger: {next_missing.get('validation_command')}")
        lines.append(f"Completion gate: {next_missing.get('completion_validation_command')}")
        return "\n".join(lines)

    lines.extend(
        [
            f"Queue item: {item.get('queue_item_id')} [{item.get('priority')}]",
            f"Permit: {item.get('source_permit_number')}",
            f"Address: {item.get('address')}",
            f"Contractor: {item.get('contractor')}",
            (
                "Trigger: "
                f"{item.get('trigger_date')} "
                f"{item.get('trigger_type')} "
                f"{item.get('trigger_result')} / "
                f"{item.get('failure_reason')}"
            ),
            f"Recommended actions: {format_action_list(item.get('recommended_actions'))}",
        ]
    )
    expected_followup = item.get("expected_followup", {})
    if not isinstance(expected_followup, dict):
        expected_followup = {}
    lines.append(
        "Follow-up observed: "
        f"{expected_followup.get('inspection_date')} "
        f"{expected_followup.get('inspection_type')} -> "
        f"{expected_followup.get('result')}"
    )
    evidence = item.get("evidence", [])
    if isinstance(evidence, list) and evidence:
        lines.append("Evidence:")
        lines.extend(f"- {value}" for value in evidence)
    lines.extend(
        [
            "",
            *format_action_catalog_text(next_missing.get("action_catalog")),
            "",
        ]
    )

    commands = next_missing.get("suggested_commands", {})
    if not isinstance(commands, dict):
        commands = {}
    lines.extend(format_command_group(commands.get("dry_run_next_missing"), "Dry-run next-missing shortcut"))
    lines.append("")
    lines.extend(
        format_command_group(
            commands.get("dry_run_next_missing_with_note"),
            "Dry-run next-missing shortcut with note",
        )
    )
    lines.append("")
    lines.extend(format_command_group(commands.get("append_next_missing"), "Append next-missing shortcut"))
    lines.append("")
    lines.extend(format_command_group(commands.get("append_next_missing_with_note"), "Append next-missing shortcut with note"))
    lines.append("")
    lines.extend(format_command_group(commands.get("dry_run"), "Dry-run fixed-item commands"))
    lines.append("")
    lines.extend(format_command_group(commands.get("dry_run_with_note"), "Dry-run fixed-item commands with note"))
    lines.append("")
    lines.extend(format_command_group(commands.get("append"), "Append fixed-item commands"))
    lines.append("")
    lines.extend(format_command_group(commands.get("append_with_note"), "Append fixed-item commands with note"))
    lines.append("")
    lines.append(f"Validate ledger after capture: {next_missing.get('validation_command')}")
    lines.append(
        "Completion gate after all corrections: "
        f"{next_missing.get('completion_validation_command')}"
    )
    return "\n".join(lines)


def format_ledger_validation_text(validation: dict[str, Any]) -> str:
    lines = [
        "Dallas operator-correction ledger validation",
        f"Status: {str(validation.get('status', 'fail')).upper()}",
        f"Workflow: {validation.get('workflow_id')}",
        f"Ledger: {validation.get('ledger_path')}",
        f"Completion required: {'yes' if validation.get('require_complete') else 'no'}",
        f"Queue items: {validation.get('queue_items')}",
        (
            "Queue corrections: "
            f"{validation.get('queue_items_with_corrections')} captured, "
            f"{validation.get('queue_items_missing_corrections')} missing"
        ),
        f"Events checked: {validation.get('events_checked')}",
        f"Invalid ledger lines: {validation.get('invalid_lines')}",
        f"Issues: {validation.get('issue_count')}",
    ]

    missing_ids = validation.get("missing_queue_item_ids", [])
    if isinstance(missing_ids, list) and missing_ids:
        lines.append("Missing queue items:")
        lines.extend(f"- {queue_item_id}" for queue_item_id in missing_ids)
        if validation.get("next_missing_command"):
            lines.append(f"Next missing work order: {validation.get('next_missing_command')}")
    else:
        lines.append("Missing queue items: (none)")

    duplicate_queue_ids = validation.get("duplicate_queue_item_ids", [])
    if isinstance(duplicate_queue_ids, list) and duplicate_queue_ids:
        lines.append("Duplicate queue item IDs:")
        lines.extend(f"- {queue_item_id}" for queue_item_id in duplicate_queue_ids)
    else:
        lines.append("Duplicate queue item IDs: (none)")

    issues = validation.get("issues", [])
    if not isinstance(issues, list) or not issues:
        lines.append("Issue detail: (none)")
        return "\n".join(lines)

    lines.append("Issue detail:")
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        event_number = issue.get("event_number")
        event_label = f"event {event_number}" if event_number else "coverage"
        lines.append(
            "- "
            f"{event_label} "
            f"{issue.get('field')}: {issue.get('message')} "
            f"({issue.get('queue_item_id') or issue.get('correction_id') or 'unknown event'})"
        )
    return "\n".join(lines)


def format_correction_event_text(
    event: dict[str, Any],
    queue_path: Path,
    ledger_path: Path,
    dry_run: bool,
) -> str:
    title = "Dallas operator correction dry run" if dry_run else "Dallas operator correction recorded"
    ledger_line = "Ledger: not written (--dry-run)" if dry_run else f"Ledger: {display_path(ledger_path)}"
    note = str(event.get("operator_note") or "").strip()
    lines = [
        title,
        f"Correction: {event.get('correction_id')}",
        f"Captured at: {event.get('captured_at')}",
        f"Queue item: {event.get('queue_item_id')}",
        f"Permit: {event.get('source_permit_number')}",
        f"Inspection: {event.get('inspection_id')}",
        f"Decision: {event.get('decision')}",
        f"Reference actions: {format_action_list(event.get('reference_actions'))}",
        f"Corrected actions: {format_action_list(event.get('corrected_actions'))}",
        f"Operator note: {note if note else '(none)'}",
        f"Source: {event.get('source')}",
        ledger_line,
        f"Validate ledger: {validate_ledger_command(queue_path, ledger_path, output_format='text')}",
        f"Next missing work order: {read_only_command('--next-missing', queue_path, ledger_path, output_format='text')}",
        (
            "Completion gate: "
            f"{validate_ledger_command(queue_path, ledger_path, output_format='text', require_complete=True)}"
        ),
    ]
    return "\n".join(lines)


def next_missing_correction(
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> dict[str, Any]:
    listing = queue_listing(queue_path, ledger_path, missing_only=True)
    items = listing["items"]
    item = items[0] if items else None
    return {
        "action_catalog": listing["action_catalog"],
        "filter": "next_missing",
        "workflow_id": listing["workflow_id"],
        "queue_items": listing["queue_items"],
        "queue_items_with_corrections": listing["queue_items_with_corrections"],
        "queue_items_missing_corrections": listing["queue_items_missing_corrections"],
        "item": item,
        "suggested_commands": (
            suggested_record_commands(item, queue_path, ledger_path, output_format=output_format)
            if item
            else {}
        ),
        "validation_command": validate_ledger_command(queue_path, ledger_path, output_format=output_format),
        "completion_validation_command": validate_ledger_command(
            queue_path,
            ledger_path,
            output_format=output_format,
            require_complete=True,
        ),
    }


def resolve_next_missing_queue_item_id(
    queue_path: Path,
    ledger_path: Path,
    expected_next_missing_id: str | None = None,
) -> str:
    next_missing = next_missing_correction(queue_path, ledger_path)
    item = next_missing.get("item")
    if not isinstance(item, dict) or not isinstance(item.get("queue_item_id"), str):
        raise ValueError("No queue items are missing corrections")

    queue_item_id = item["queue_item_id"]
    expected_queue_item_id = str(expected_next_missing_id or "").strip()
    if expected_queue_item_id and queue_item_id != expected_queue_item_id:
        raise ValueError(
            "next missing queue item changed; "
            f"expected {expected_queue_item_id}, found {queue_item_id}. "
            "Regenerate the work order before recording a correction."
        )
    return queue_item_id


def add_smoke_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


def output_format_label(output_format: str) -> str:
    return "text output" if output_format == "text" else "default JSON output"


def command_preserves_output_format(command: Any, output_format: str) -> bool:
    if not isinstance(command, str):
        return False
    actual_output_format = command_arg_value(command, "--format")
    if output_format == "text":
        return actual_output_format == "text"
    return actual_output_format is None


def temporary_incomplete_ledger(
    queue_path: Path,
    ledger_path: Path,
) -> tuple[tempfile.TemporaryDirectory[str], Path, str] | None:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        return None

    queue_item_id = None
    for item in queue:
        if isinstance(item, dict) and isinstance(item.get("queue_item_id"), str):
            queue_item_id = item["queue_item_id"]
            break
    if queue_item_id is None:
        return None

    events, _invalid_lines = read_correction_events(ledger_path)
    temp_dir = tempfile.TemporaryDirectory(prefix="automoat-incomplete-correction-smoke-")
    temp_ledger_path = Path(temp_dir.name) / "operator-corrections.jsonl"
    with temp_ledger_path.open("w", encoding="utf-8") as handle:
        for event in events:
            if event.get("queue_item_id") == queue_item_id:
                continue
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    return temp_dir, temp_ledger_path, queue_item_id


def operator_correction_smoke_check(
    queue_path: Path,
    ledger_path: Path,
    output_format: str = "json",
) -> dict[str, Any]:
    progress = correction_progress(queue_path, ledger_path, output_format=output_format)
    validation = ledger_validation(queue_path, ledger_path, output_format=output_format)
    completion_validation = ledger_validation(
        queue_path,
        ledger_path,
        require_complete=True,
        output_format=output_format,
    )
    next_missing = next_missing_correction(queue_path, ledger_path, output_format=output_format)
    checks: list[dict[str, Any]] = []
    expected_format_label = output_format_label(output_format)

    queue_items = progress.get("queue_items")
    missing_count = progress.get("queue_items_missing_corrections")
    add_smoke_check(
        checks,
        "queue_loaded",
        isinstance(queue_items, int) and queue_items > 0,
        f"{queue_items} queue items found",
    )
    add_smoke_check(
        checks,
        "ledger_validation",
        validation.get("status") == "pass",
        f"{validation.get('issue_count')} issues, {validation.get('invalid_lines')} invalid lines",
    )
    completion_issues = completion_validation.get("issues", [])
    completion_issue_fields = (
        [issue.get("field") for issue in completion_issues if isinstance(issue, dict)]
        if isinstance(completion_issues, list)
        else []
    )
    if isinstance(missing_count, int) and missing_count > 0:
        completion_gate_passed = (
            completion_validation.get("status") == "fail"
            and "queue_correction_coverage" in completion_issue_fields
        )
        completion_gate_detail = (
            f"completion gate rejects {missing_count} missing queue items"
            if completion_gate_passed
            else (
                "completion gate did not reject incomplete coverage: "
                f"{completion_validation.get('status')} with fields {completion_issue_fields}"
            )
        )
    else:
        completion_gate_passed = completion_validation.get("status") == "pass"
        completion_gate_detail = (
            "completion gate passes with complete correction coverage"
            if completion_gate_passed
            else f"completion gate failed unexpectedly: {completion_validation.get('issue_count')} issues"
        )
    add_smoke_check(
        checks,
        "completion_gate",
        completion_gate_passed,
        completion_gate_detail,
    )

    catalog = action_catalog(queue_path)
    action_ids = catalog.get("action_ids", [])
    add_smoke_check(
        checks,
        "action_catalog",
        isinstance(action_ids, list) and bool(action_ids),
        f"{len(action_ids) if isinstance(action_ids, list) else 0} known action IDs",
    )
    pattern_payload = operator_correction_patterns(
        queue_path,
        ledger_path,
        output_format=output_format,
    )
    accepted_pattern_count = pattern_payload.get("accepted_pattern_count")
    accepted_latest_corrections = pattern_payload.get("accepted_latest_corrections")
    add_smoke_check(
        checks,
        "operator_correction_patterns",
        isinstance(accepted_pattern_count, int) and isinstance(accepted_latest_corrections, int),
        (
            f"{accepted_pattern_count} accepted patterns from "
            f"{accepted_latest_corrections} latest accepted corrections"
        ),
    )
    pattern_completion_command = pattern_payload.get("completion_validation_command")
    pattern_command_passed = command_preserves_output_format(
        pattern_completion_command,
        output_format,
    )
    add_smoke_check(
        checks,
        "pattern_completion_command_output_format",
        pattern_command_passed,
        (
            f"pattern completion command keeps {expected_format_label}"
            if pattern_command_passed
            else (
                "pattern completion command changed output mode: "
                f"{pattern_completion_command}"
            )
        ),
    )

    item = next_missing.get("item")
    queue_item_id = item.get("queue_item_id") if isinstance(item, dict) else None
    if isinstance(missing_count, int) and missing_count > 0:
        add_smoke_check(
            checks,
            "next_missing_item",
            isinstance(queue_item_id, str) and bool(queue_item_id),
            str(queue_item_id or "no next missing item"),
        )
        validation_next_missing_command = validation.get("next_missing_command")
        validation_command_passed = command_preserves_output_format(
            validation_next_missing_command,
            output_format,
        )
        add_smoke_check(
            checks,
            "validation_next_missing_command",
            validation_command_passed,
            (
                f"ledger validation next-missing command keeps {expected_format_label}"
                if validation_command_passed
                else (
                    "ledger validation next-missing command changed output mode: "
                    f"{validation_next_missing_command}"
                )
            ),
        )
    else:
        add_smoke_check(
            checks,
            "next_missing_item",
            item is None,
            "all current queue items have captured corrections",
        )
        add_smoke_check(
            checks,
            "validation_next_missing_command",
            validation.get("next_missing_command") is None,
            "no next-missing command needed when every queue item is captured",
        )

    progress_commands = {
        "next_missing_command": progress.get("next_missing_command"),
        "validation_command": progress.get("validation_command"),
        "completion_validation_command": progress.get("completion_validation_command"),
        "patterns_command": progress.get("patterns_command"),
    }
    progress_command_failures = [
        name
        for name, command in progress_commands.items()
        if command is not None and not command_preserves_output_format(command, output_format)
    ]
    add_smoke_check(
        checks,
        "progress_command_output_format",
        not progress_command_failures,
        (
            f"summary/progress commands keep {expected_format_label}"
            if not progress_command_failures
            else (
                "summary/progress commands changed output mode: "
                f"{', '.join(progress_command_failures)}"
            )
        ),
    )
    add_smoke_check(
        checks,
        "progress_import_readiness_command",
        (
            progress.get("import_readiness_command") == IMPORT_READINESS_COMMAND
            and progress.get("import_readiness_json_command") == IMPORT_READINESS_JSON_COMMAND
            if missing_count == 0
            else (
                progress.get("import_readiness_command") is None
                and progress.get("import_readiness_json_command") is None
            )
        ),
        (
            "summary points to text and JSON import-readiness gates after complete correction capture"
            if missing_count == 0
            else "summary with missing corrections does not advertise import-readiness gates"
        ),
    )
    readiness_snapshot = progress.get("last_import_readiness_summary")
    readiness_snapshot_counts_passed = False
    if isinstance(readiness_snapshot, dict):
        readiness_status = readiness_snapshot.get("status")
        latest_import_counts = readiness_snapshot.get("latest_import_counts", {})
        coverage_thin_counts = readiness_snapshot.get("coverage_thin_counts", {})
        coverage_thin_groups = readiness_snapshot.get("coverage_thin_groups", {})
        import_record_handoff = readiness_snapshot.get("next_import_record_handoff")
        import_record_handoff_passed = next_import_record_handoff_is_valid(import_record_handoff)
        if readiness_status in {"missing", "unreadable", "unavailable"}:
            readiness_snapshot_counts_passed = import_record_handoff_passed
        else:
            readiness_snapshot_counts_passed = (
                isinstance(latest_import_counts, dict)
                and isinstance(latest_import_counts.get("permits"), int)
                and isinstance(latest_import_counts.get("inspections"), int)
                and isinstance(latest_import_counts.get("tasks"), int)
                and isinstance(coverage_thin_counts, dict)
                and isinstance(coverage_thin_counts.get("result_states"), int)
                and isinstance(coverage_thin_counts.get("next_action_groups"), int)
                and isinstance(coverage_thin_groups, dict)
                and all(
                    isinstance(values, list)
                    and all(isinstance(value, str) for value in values)
                    for values in coverage_thin_groups.values()
                )
                and isinstance(readiness_snapshot.get("accepted_pattern_count"), int)
                and isinstance(readiness_snapshot.get("next_step"), str)
                and bool(readiness_snapshot.get("next_step", "").strip())
                and import_record_handoff_passed
            )
    readiness_snapshot_passed = (
        isinstance(readiness_snapshot, dict)
        and isinstance(readiness_snapshot.get("summary_json_path"), str)
        and readiness_snapshot.get("refresh_command") == IMPORT_READINESS_COMMAND
        and readiness_snapshot.get("refresh_json_command") == IMPORT_READINESS_JSON_COMMAND
        and readiness_snapshot_counts_passed
        if missing_count == 0
        else readiness_snapshot is None
    )
    add_smoke_check(
        checks,
        "progress_import_readiness_snapshot",
        readiness_snapshot_passed,
        (
            "summary includes the last durable import-readiness snapshot, import "
            "counts, thin coverage groups, next step, and raw CSV handoff with "
            "row counts, next append rows, last data rows, identity key checks, "
            "value profiles, date profiles, relationship checks, import scope "
            "counts, importable examples, exclusion examples, headers, required "
            "fields, optional fields, append templates, append CSV templates, "
            "append work order, append sequence, required-field gaps, append "
            "preflight, handoff verification commands, and file fingerprints after complete "
            "correction capture"
            if missing_count == 0
            else "summary with missing corrections does not expose the last import-readiness snapshot"
        ),
    )

    next_missing_followup_commands = {
        "validation_command": next_missing.get("validation_command"),
        "completion_validation_command": next_missing.get("completion_validation_command"),
    }
    next_missing_followup_failures = [
        name
        for name, command in next_missing_followup_commands.items()
        if command is not None and not command_preserves_output_format(command, output_format)
    ]
    add_smoke_check(
        checks,
        "next_missing_followup_command_output_format",
        not next_missing_followup_failures,
        (
            f"next-missing validation commands keep {expected_format_label}"
            if not next_missing_followup_failures
            else (
                "next-missing validation commands changed output mode: "
                f"{', '.join(next_missing_followup_failures)}"
            )
        ),
    )

    dry_run_events: list[dict[str, Any]] = []
    next_missing_for_checks = next_missing
    ledger_path_for_checks = ledger_path
    temp_smoke_dir: tempfile.TemporaryDirectory[str] | None = None
    if not (isinstance(item, dict) and isinstance(queue_item_id, str)):
        incomplete_fixture = temporary_incomplete_ledger(queue_path, ledger_path)
        if incomplete_fixture is None:
            add_smoke_check(
                checks,
                "temporary_next_missing_fixture",
                False,
                "could not build a temporary incomplete correction ledger",
            )
        else:
            temp_smoke_dir, ledger_path_for_checks, expected_missing_id = incomplete_fixture
            next_missing_for_checks = next_missing_correction(
                queue_path,
                ledger_path_for_checks,
                output_format=output_format,
            )
            fixture_item = next_missing_for_checks.get("item")
            fixture_queue_item_id = (
                fixture_item.get("queue_item_id") if isinstance(fixture_item, dict) else None
            )
            fixture_completion = ledger_validation(
                queue_path,
                ledger_path_for_checks,
                require_complete=True,
                output_format=output_format,
            )
            fixture_progress = correction_progress(
                queue_path,
                ledger_path_for_checks,
                output_format=output_format,
            )
            fixture_issues = fixture_completion.get("issues", [])
            fixture_issue_fields = (
                [issue.get("field") for issue in fixture_issues if isinstance(issue, dict)]
                if isinstance(fixture_issues, list)
                else []
            )
            add_smoke_check(
                checks,
                "temporary_next_missing_fixture",
                fixture_queue_item_id == expected_missing_id,
                (
                    f"temporary ledger exposes {expected_missing_id} as a next-missing work item"
                    if fixture_queue_item_id == expected_missing_id
                    else f"temporary ledger exposed {fixture_queue_item_id}, expected {expected_missing_id}"
                ),
            )
            add_smoke_check(
                checks,
                "temporary_completion_gate",
                (
                    fixture_completion.get("status") == "fail"
                    and "queue_correction_coverage" in fixture_issue_fields
                ),
                (
                    "temporary incomplete ledger is rejected by the completion gate"
                    if (
                        fixture_completion.get("status") == "fail"
                        and "queue_correction_coverage" in fixture_issue_fields
                    )
                    else (
                        "temporary incomplete ledger was not rejected by the completion gate: "
                        f"{fixture_completion.get('status')} with fields {fixture_issue_fields}"
                    )
                ),
            )
            fixture_hides_readiness = (
                fixture_progress.get("import_readiness_command") is None
                and fixture_progress.get("import_readiness_json_command") is None
                and fixture_progress.get("last_import_readiness_summary") is None
            )
            add_smoke_check(
                checks,
                "temporary_progress_import_readiness_command",
                fixture_hides_readiness,
                (
                    "temporary incomplete ledger does not advertise import-readiness gates"
                    if fixture_hides_readiness
                    else "temporary incomplete ledger advertised an import-readiness gate"
                ),
            )

    item_for_checks = next_missing_for_checks.get("item")
    queue_item_id_for_checks = (
        item_for_checks.get("queue_item_id") if isinstance(item_for_checks, dict) else None
    )
    if isinstance(item_for_checks, dict) and isinstance(queue_item_id_for_checks, str):
        commands = next_missing_for_checks.get("suggested_commands", {})
        if not isinstance(commands, dict):
            commands = {}
        dry_run_shortcut = commands.get("dry_run_next_missing", {})
        dry_run_with_note = commands.get("dry_run_next_missing_with_note", {})
        append_shortcut = commands.get("append_next_missing", {})
        append_shortcut_with_note = commands.get("append_next_missing_with_note", {})

        dry_run_failures = command_group_failures(
            dry_run_shortcut,
            queue_item_id_for_checks,
            should_be_dry_run=True,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "guarded_dry_run_shortcut",
            not dry_run_failures,
            (
                "accepted/rejected/edited dry-run shortcuts use --use-next-missing and include expected-ID, require-missing, "
                f"{expected_format_label}, dry-run guards, and edited action template"
                if not dry_run_failures
                else "; ".join(dry_run_failures)
            ),
        )

        note_dry_run_failures = command_group_failures(
            dry_run_with_note,
            queue_item_id_for_checks,
            should_be_dry_run=True,
            require_note=True,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "note_dry_run_shortcut",
            not note_dry_run_failures,
            (
                "accepted/rejected/edited note dry-runs keep "
                f"--use-next-missing, {expected_format_label}, operator-note, and dry-run flags"
                if not note_dry_run_failures
                else "; ".join(note_dry_run_failures)
            ),
        )

        append_failures = command_group_failures(
            append_shortcut,
            queue_item_id_for_checks,
            should_be_dry_run=False,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "guarded_append_shortcut",
            not append_failures,
            (
                "accepted/rejected/edited append shortcuts use --use-next-missing and include expected-ID, require-missing guards, "
                f"{expected_format_label}, and edited action template"
                if not append_failures
                else "; ".join(append_failures)
            ),
        )

        note_append_failures = command_group_failures(
            append_shortcut_with_note,
            queue_item_id_for_checks,
            should_be_dry_run=False,
            require_note=True,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "note_append_shortcut",
            not note_append_failures,
            (
                "accepted/rejected/edited note appends keep "
                f"--use-next-missing, {expected_format_label}, and operator-note placeholders"
                if not note_append_failures
                else "; ".join(note_append_failures)
            ),
        )

        dry_run_fixed = commands.get("dry_run", {})
        dry_run_fixed_with_note = commands.get("dry_run_with_note", {})
        append_fixed = commands.get("append", {})
        append_fixed_with_note = commands.get("append_with_note", {})

        fixed_dry_run_failures = command_group_failures(
            dry_run_fixed,
            None,
            should_be_dry_run=True,
            expected_queue_item_id=queue_item_id_for_checks,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "guarded_dry_run_fixed_item",
            not fixed_dry_run_failures,
            (
                "accepted/rejected/edited fixed-item dry-runs include queue item ID, "
                f"avoid shortcut mode, require-missing, {expected_format_label}, dry-run guards, and edited action template"
                if not fixed_dry_run_failures
                else "; ".join(fixed_dry_run_failures)
            ),
        )

        note_fixed_failures = command_group_failures(
            dry_run_fixed_with_note,
            None,
            should_be_dry_run=True,
            require_note=True,
            expected_queue_item_id=queue_item_id_for_checks,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "note_dry_run_fixed_item",
            not note_fixed_failures,
            (
                "accepted/rejected/edited fixed-item note dry-runs keep queue item ID, "
                f"avoid shortcut mode, {expected_format_label}, operator-note, and dry-run flags"
                if not note_fixed_failures
                else "; ".join(note_fixed_failures)
            ),
        )

        fixed_append_failures = command_group_failures(
            append_fixed,
            None,
            should_be_dry_run=False,
            expected_queue_item_id=queue_item_id_for_checks,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "guarded_append_fixed_item",
            not fixed_append_failures,
            (
                "accepted/rejected/edited fixed-item appends include queue item ID, "
                f"avoid shortcut mode, require-missing guards, {expected_format_label}, and edited action template"
                if not fixed_append_failures
                else "; ".join(fixed_append_failures)
            ),
        )

        note_fixed_append_failures = command_group_failures(
            append_fixed_with_note,
            None,
            should_be_dry_run=False,
            require_note=True,
            expected_queue_item_id=queue_item_id_for_checks,
            expected_output_format=output_format,
        )
        add_smoke_check(
            checks,
            "note_append_fixed_item",
            not note_fixed_append_failures,
            (
                "accepted/rejected/edited fixed-item note appends keep queue item ID, "
                f"avoid shortcut mode, {expected_format_label}, and operator-note placeholders"
                if not note_fixed_append_failures
                else "; ".join(note_fixed_append_failures)
            ),
        )

        recommended_actions: list[str] = []
        try:
            recommended_actions = normalize_action_list(item_for_checks.get("recommended_actions"))
        except ValueError:
            pass
        add_smoke_check(
            checks,
            "next_missing_actions",
            bool(recommended_actions),
            format_action_list(recommended_actions),
        )

        event_specs = [
            ("accepted", "", ["corrected_actions", recommended_actions]),
            ("rejected", "", ["corrected_actions", []]),
            ("edited", ",".join(recommended_actions), ["corrected_actions", recommended_actions]),
        ]
        event_failures = []
        for offset, (decision, corrected_actions, expected_field) in enumerate(event_specs, start=1):
            try:
                event = build_operator_correction_event(
                    {
                        "queue_item_id": queue_item_id_for_checks,
                        "decision": decision,
                        "corrected_actions": corrected_actions,
                        "operator_note": "smoke check only",
                        "source": "operator-correction-smoke-check",
                    },
                    queue_path,
                    captured_at=f"2026-01-01T00:00:0{offset}Z",
                )
                dry_run_events.append(
                    {
                        "decision": decision,
                        "correction_id": event.get("correction_id"),
                        "corrected_actions": event.get("corrected_actions"),
                    }
                )
                field_name, expected_value = expected_field
                if event.get(field_name) != expected_value:
                    event_failures.append(f"{decision} produced unexpected {field_name}")
            except ValueError as exc:
                event_failures.append(f"{decision}: {exc}")
        add_smoke_check(
            checks,
            "dry_run_event_construction",
            not event_failures,
            "; ".join(event_failures) if event_failures else "accepted/rejected/edited events build",
        )

        expected_guard_passed = False
        expected_guard_detail = "stale expected-ID guard rejected a changed next-missing item"
        stale_expected_id = f"{queue_item_id_for_checks}:stale"
        try:
            resolve_next_missing_queue_item_id(queue_path, ledger_path_for_checks, stale_expected_id)
            expected_guard_detail = "stale expected-ID guard allowed a changed next-missing item"
        except ValueError as exc:
            expected_guard_passed = "next missing queue item changed" in str(exc)
            if not expected_guard_passed:
                expected_guard_detail = str(exc)
        add_smoke_check(
            checks,
            "expected_next_missing_guard",
            expected_guard_passed,
            expected_guard_detail,
        )

        stale_guard_detail = "stale capture guard rejected a captured queue item"
        stale_guard_passed = False
        stale_guard_event = build_operator_correction_event(
            {
                "queue_item_id": queue_item_id_for_checks,
                "decision": "accepted",
                "operator_note": "smoke check stale guard",
                "source": "operator-correction-smoke-check",
            },
            queue_path,
            captured_at="2026-01-01T00:00:09Z",
        )
        with tempfile.TemporaryDirectory(prefix="automoat-correction-smoke-") as tmpdir:
            temp_ledger_path = Path(tmpdir) / "operator-corrections.jsonl"
            temp_ledger_path.write_text(json.dumps(stale_guard_event, sort_keys=True) + "\n", encoding="utf-8")
            try:
                require_queue_item_missing(temp_ledger_path, queue_item_id_for_checks)
                stale_guard_detail = "stale capture guard allowed a captured queue item"
            except ValueError as exc:
                stale_guard_passed = "already has a captured correction" in str(exc)
                if not stale_guard_passed:
                    stale_guard_detail = str(exc)
        add_smoke_check(
            checks,
            "stale_capture_guard",
            stale_guard_passed,
            stale_guard_detail,
        )

        context_guard_detail = "ledger validation rejected stale permit/inspection context"
        context_guard_passed = False
        stale_context_event = build_operator_correction_event(
            {
                "queue_item_id": queue_item_id_for_checks,
                "decision": "accepted",
                "operator_note": "smoke check stale context",
                "source": "operator-correction-smoke-check",
            },
            queue_path,
            captured_at="2026-01-01T00:00:10Z",
        )
        stale_context_event["inspection_id"] = "inspection:dallas:stale-context"
        with tempfile.TemporaryDirectory(prefix="automoat-correction-context-smoke-") as tmpdir:
            temp_ledger_path = Path(tmpdir) / "operator-corrections.jsonl"
            temp_ledger_path.write_text(json.dumps(stale_context_event, sort_keys=True) + "\n", encoding="utf-8")
            context_validation = ledger_validation(
                queue_path,
                temp_ledger_path,
                output_format=output_format,
            )
            context_issues = context_validation.get("issues", [])
            context_issue_fields = (
                [issue.get("field") for issue in context_issues if isinstance(issue, dict)]
                if isinstance(context_issues, list)
                else []
            )
            context_guard_passed = (
                context_validation.get("status") == "fail"
                and "inspection_id" in context_issue_fields
            )
            if not context_guard_passed:
                context_guard_detail = (
                    "ledger validation allowed stale permit/inspection context: "
                    f"{context_validation.get('status')} with fields {context_issue_fields}"
                )
        add_smoke_check(
            checks,
            "queue_context_guard",
            context_guard_passed,
            context_guard_detail,
        )

    failed_checks = [check for check in checks if check.get("status") != "pass"]
    result = {
        "workflow_id": progress.get("workflow_id"),
        "status": "fail" if failed_checks else "pass",
        "output_format": output_format,
        "queue_items": progress.get("queue_items"),
        "queue_items_with_corrections": progress.get("queue_items_with_corrections"),
        "queue_items_missing_corrections": progress.get("queue_items_missing_corrections"),
        "next_missing_queue_item_id": queue_item_id,
        "smoke_next_missing_queue_item_id": queue_item_id_for_checks,
        "completion_gate_status": completion_validation.get("status"),
        "completion_gate_issue_count": completion_validation.get("issue_count"),
        "checks": checks,
        "dry_run_events": dry_run_events,
        "next_missing_command": progress.get("next_missing_command"),
        "validation_command": progress.get("validation_command"),
        "completion_validation_command": progress.get("completion_validation_command"),
        "patterns_command": progress.get("patterns_command"),
        "import_readiness_command": progress.get("import_readiness_command"),
        "import_readiness_json_command": progress.get("import_readiness_json_command"),
        "last_import_readiness_summary": progress.get("last_import_readiness_summary"),
    }
    if temp_smoke_dir is not None:
        temp_smoke_dir.cleanup()
    return result


def format_smoke_check_text(smoke_check: dict[str, Any]) -> str:
    lines = [
        "Dallas operator-correction smoke check",
        f"Status: {str(smoke_check.get('status', 'fail')).upper()}",
        f"Workflow: {smoke_check.get('workflow_id')}",
        f"Output format checked: {smoke_check.get('output_format')}",
        (
            "Queue corrections: "
            f"{smoke_check.get('queue_items_with_corrections')} captured, "
            f"{smoke_check.get('queue_items_missing_corrections')} missing, "
            f"{smoke_check.get('queue_items')} total"
        ),
    ]
    next_missing_queue_item_id = smoke_check.get("next_missing_queue_item_id")
    if next_missing_queue_item_id:
        lines.append(f"Next missing queue item: {next_missing_queue_item_id}")
    else:
        lines.append("Next missing queue item: (none)")

    checks = smoke_check.get("checks", [])
    lines.append("Checks:")
    if isinstance(checks, list) and checks:
        for check in checks:
            if not isinstance(check, dict):
                continue
            lines.append(
                "- "
                f"{str(check.get('status', 'fail')).upper()}: "
                f"{check.get('name')} - {check.get('detail')}"
            )
    else:
        lines.append("- FAIL: no checks ran")

    dry_run_events = smoke_check.get("dry_run_events", [])
    if isinstance(dry_run_events, list) and dry_run_events:
        lines.append("Dry-run event shapes:")
        for event in dry_run_events:
            if not isinstance(event, dict):
                continue
            lines.append(
                "- "
                f"{event.get('decision')}: "
                f"{format_action_list(event.get('corrected_actions'))}"
            )

    if smoke_check.get("next_missing_command"):
        lines.append(f"Next missing work order: {smoke_check.get('next_missing_command')}")
    if smoke_check.get("patterns_command"):
        lines.append(f"Pattern review: {smoke_check.get('patterns_command')}")
    if smoke_check.get("import_readiness_command"):
        lines.append(f"Import readiness gate: {smoke_check.get('import_readiness_command')}")
    if smoke_check.get("import_readiness_json_command"):
        lines.append(
            f"Import readiness JSON gate: {smoke_check.get('import_readiness_json_command')}"
        )
    readiness = smoke_check.get("last_import_readiness_summary")
    if isinstance(readiness, dict):
        lines.append(
            "Last import readiness summary: "
            f"{readiness.get('status')} "
            f"({readiness.get('summary_json_path')})"
        )
        lines.append(
            "Last coverage thin groups: "
            f"{format_coverage_thin_groups(readiness.get('coverage_thin_groups'))}"
        )
        lines.append(
            "Next import raw files: "
            f"{format_raw_import_files(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw row counts: "
            f"{format_raw_import_row_counts(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append preflight: "
            f"{format_raw_import_append_preflight(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw handoff verification: "
            f"{format_raw_import_handoff_verification(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw fingerprints: "
            f"{format_raw_import_fingerprints(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append rows: "
            f"{format_raw_import_next_append_rows(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw last data rows: "
            f"{format_raw_import_last_data_rows(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw identity key checks: "
            f"{format_raw_import_identity_key_checks(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw value profiles: "
            f"{format_raw_import_value_profiles(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw date profiles: "
            f"{format_raw_import_date_profiles(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw relationship checks: "
            f"{format_raw_import_relationship_checks(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw scope counts: "
            f"{format_raw_import_scope_counts(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw importable examples: "
            f"{format_raw_importable_examples(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw exclusion examples: "
            f"{format_raw_import_exclusion_examples(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw headers: "
            f"{format_raw_import_headers(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw required fields: "
            f"{format_raw_import_required_fields(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw optional fields: "
            f"{format_raw_import_optional_fields(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append templates: "
            f"{format_raw_import_append_templates(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append CSV templates: "
            f"{format_raw_import_append_csv_templates(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append work order: "
            f"{format_raw_import_append_work_order(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw append sequence: "
            f"{format_raw_import_append_sequence(readiness.get('next_import_record_handoff'))}"
        )
        lines.append(
            "Next import raw required-field gaps: "
            f"{format_raw_import_required_field_gaps(readiness.get('next_import_record_handoff'))}"
        )
    lines.append(f"Validate ledger: {smoke_check.get('validation_command')}")
    lines.append(f"Completion gate: {smoke_check.get('completion_validation_command')}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    if args.list_queue_items:
        listing = queue_listing(args.queue_path, args.ledger_path, args.missing_only)
        if args.format == "text":
            print(format_queue_listing_text(listing))
        else:
            print(json.dumps(listing, indent=2, sort_keys=True))
        return 0
    if args.next_missing:
        next_missing = next_missing_correction(
            args.queue_path,
            args.ledger_path,
            output_format=args.format,
        )
        if args.format == "text":
            print(format_next_missing_text(next_missing))
        else:
            print(json.dumps(next_missing, indent=2, sort_keys=True))
        return 0
    if args.summary:
        progress = correction_progress(args.queue_path, args.ledger_path, output_format=args.format)
        if args.format == "text":
            print(format_progress_text(progress))
        else:
            print(json.dumps(progress, indent=2, sort_keys=True))
        return 0
    if args.list_patterns:
        pattern_payload = operator_correction_patterns(
            args.queue_path,
            args.ledger_path,
            output_format=args.format,
        )
        if args.format == "text":
            print(format_operator_patterns_text(pattern_payload))
        else:
            print(json.dumps(pattern_payload, indent=2, sort_keys=True))
        return 0
    if args.validate_ledger:
        validation = ledger_validation(
            args.queue_path,
            args.ledger_path,
            args.require_complete,
            output_format=args.format,
        )
        if args.format == "text":
            print(format_ledger_validation_text(validation))
        else:
            print(json.dumps(validation, indent=2, sort_keys=True))
        return 0 if validation["status"] == "pass" else 1
    if args.smoke_check:
        smoke_check = operator_correction_smoke_check(
            args.queue_path,
            args.ledger_path,
            output_format=args.format,
        )
        if args.format == "text":
            print(format_smoke_check_text(smoke_check))
        else:
            print(json.dumps(smoke_check, indent=2, sort_keys=True))
        return 0 if smoke_check["status"] == "pass" else 1

    queue_item_id = args.queue_item_id
    if args.use_next_missing:
        try:
            queue_item_id = resolve_next_missing_queue_item_id(
                args.queue_path,
                args.ledger_path,
                args.expected_next_missing_id,
            )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("No queue items"):
                raise SystemExit(message) from exc
            raise SystemExit(f"error: {message}") from exc

    if args.require_missing and queue_item_id:
        try:
            require_queue_item_missing(args.ledger_path, queue_item_id)
        except ValueError as exc:
            raise SystemExit(f"error: {exc}") from exc

    payload = {
        "queue_item_id": queue_item_id,
        "decision": args.decision,
        "corrected_actions": args.corrected_actions,
        "operator_note": args.operator_note,
        "source": args.source,
    }
    try:
        if args.dry_run:
            event = build_operator_correction_event(payload, args.queue_path, args.captured_at)
            correction_id = event.get("correction_id")
            if isinstance(correction_id, str) and correction_id_exists(correction_id, args.ledger_path):
                raise ValueError(f"duplicate correction_id: {correction_id}")
        else:
            event = append_operator_correction(payload, args.queue_path, args.ledger_path, args.captured_at)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    if args.format == "text":
        print(format_correction_event_text(event, args.queue_path, args.ledger_path, args.dry_run))
    else:
        print(json.dumps(event, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
