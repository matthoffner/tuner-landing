#!/usr/bin/env python3
"""Record one Dallas inspection operator correction without running the cockpit."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from operator_corrections import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_QUEUE_PATH,
    append_operator_correction,
    build_operator_correction_event,
    correction_summary,
    read_json,
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
        "--format",
        choices=("json", "text"),
        default="json",
        help="output format for --summary, --list-queue-items, or --next-missing",
    )
    parser.add_argument("--queue-item-id")
    parser.add_argument("--decision", choices=("accepted", "rejected", "edited"))
    parser.add_argument(
        "--corrected-actions",
        default="",
        help="comma-separated action IDs; required for edited corrections",
    )
    parser.add_argument("--operator-note", default="")
    parser.add_argument("--source", default="operator-correction-cli")
    parser.add_argument(
        "--captured-at",
        default=None,
        help="optional ISO timestamp for deterministic replay, for example 2026-05-23T00:00:00Z",
    )
    parser.add_argument("--dry-run", action="store_true", help="validate and print the event without appending")
    args = parser.parse_args()
    if args.missing_only and not args.list_queue_items:
        parser.error("--missing-only requires --list-queue-items")
    if not args.list_queue_items and not args.next_missing and not args.summary:
        if not args.queue_item_id:
            parser.error("--queue-item-id is required unless --list-queue-items, --next-missing, or --summary is used")
        if not args.decision:
            parser.error("--decision is required unless --list-queue-items, --next-missing, or --summary is used")
    return args


def correction_progress(queue_path: Path, ledger_path: Path) -> dict[str, Any]:
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
    queue_item_id: str,
    decision: str,
    queue_path: Path,
    ledger_path: Path,
    dry_run: bool = False,
    corrected_actions: str | None = None,
    operator_note: str | None = None,
) -> str:
    args = [
        "python3",
        "scripts/record_operator_correction.py",
        *command_path_args(queue_path, ledger_path),
        "--queue-item-id",
        queue_item_id,
        "--decision",
        decision,
    ]
    if corrected_actions is not None:
        args.extend(["--corrected-actions", corrected_actions])
    if operator_note is not None:
        args.extend(["--operator-note", operator_note])
    if dry_run:
        args.append("--dry-run")
    return shlex.join(args)


def suggested_record_commands(item: dict[str, Any], queue_path: Path, ledger_path: Path) -> dict[str, Any]:
    queue_item_id = str(item.get("queue_item_id", ""))
    operator_note = "<operator-note>"
    return {
        "dry_run": {
            "accepted": record_command(queue_item_id, "accepted", queue_path, ledger_path, dry_run=True),
            "rejected": record_command(queue_item_id, "rejected", queue_path, ledger_path, dry_run=True),
            "edited_template": record_command(
                queue_item_id,
                "edited",
                queue_path,
                ledger_path,
                dry_run=True,
                corrected_actions="<comma-separated-action-ids>",
            ),
        },
        "dry_run_with_note": {
            "accepted": record_command(
                queue_item_id,
                "accepted",
                queue_path,
                ledger_path,
                dry_run=True,
                operator_note=operator_note,
            ),
            "rejected": record_command(
                queue_item_id,
                "rejected",
                queue_path,
                ledger_path,
                dry_run=True,
                operator_note=operator_note,
            ),
            "edited_template": record_command(
                queue_item_id,
                "edited",
                queue_path,
                ledger_path,
                dry_run=True,
                corrected_actions="<comma-separated-action-ids>",
                operator_note=operator_note,
            ),
        },
        "append": {
            "accepted": record_command(queue_item_id, "accepted", queue_path, ledger_path),
            "rejected": record_command(queue_item_id, "rejected", queue_path, ledger_path),
            "edited_template": record_command(
                queue_item_id,
                "edited",
                queue_path,
                ledger_path,
                corrected_actions="<comma-separated-action-ids>",
            ),
        },
        "append_with_note": {
            "accepted": record_command(
                queue_item_id,
                "accepted",
                queue_path,
                ledger_path,
                operator_note=operator_note,
            ),
            "rejected": record_command(
                queue_item_id,
                "rejected",
                queue_path,
                ledger_path,
                operator_note=operator_note,
            ),
            "edited_template": record_command(
                queue_item_id,
                "edited",
                queue_path,
                ledger_path,
                corrected_actions="<comma-separated-action-ids>",
                operator_note=operator_note,
            ),
        },
    }


def format_action_list(actions: Any) -> str:
    if not isinstance(actions, list) or not actions:
        return "(none)"
    return ", ".join(str(action) for action in actions)


def format_decision_counts(counts: Any) -> str:
    if not isinstance(counts, dict) or not counts:
        return "(none)"
    return ", ".join(f"{decision}={count}" for decision, count in sorted(counts.items()))


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
    else:
        lines.append("Missing queue items: (none)")
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
                f"  Recommended actions: {format_action_list(item.get('recommended_actions'))}",
                f"  Correction: {correction_detail}",
            ]
        )
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
            "",
            *format_action_catalog_text(next_missing.get("action_catalog")),
            "",
        ]
    )

    commands = next_missing.get("suggested_commands", {})
    if not isinstance(commands, dict):
        commands = {}
    lines.extend(format_command_group(commands.get("dry_run"), "Dry-run commands"))
    lines.append("")
    lines.extend(format_command_group(commands.get("append"), "Append commands"))
    lines.append("")
    lines.extend(format_command_group(commands.get("append_with_note"), "Append commands with note"))
    return "\n".join(lines)


def next_missing_correction(queue_path: Path, ledger_path: Path) -> dict[str, Any]:
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
        "suggested_commands": suggested_record_commands(item, queue_path, ledger_path) if item else {},
    }


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
        next_missing = next_missing_correction(args.queue_path, args.ledger_path)
        if args.format == "text":
            print(format_next_missing_text(next_missing))
        else:
            print(json.dumps(next_missing, indent=2, sort_keys=True))
        return 0
    if args.summary:
        progress = correction_progress(args.queue_path, args.ledger_path)
        if args.format == "text":
            print(format_progress_text(progress))
        else:
            print(json.dumps(progress, indent=2, sort_keys=True))
        return 0

    payload = {
        "queue_item_id": args.queue_item_id,
        "decision": args.decision,
        "corrected_actions": args.corrected_actions,
        "operator_note": args.operator_note,
        "source": args.source,
    }
    if args.dry_run:
        event = build_operator_correction_event(payload, args.queue_path, args.captured_at)
    else:
        event = append_operator_correction(payload, args.queue_path, args.ledger_path, args.captured_at)
    print(json.dumps(event, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
