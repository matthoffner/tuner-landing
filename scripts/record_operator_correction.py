#!/usr/bin/env python3
"""Record one Dallas inspection operator correction without running the cockpit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from operator_corrections import (
    DEFAULT_LEDGER_PATH,
    DEFAULT_QUEUE_PATH,
    append_operator_correction,
    build_operator_correction_event,
    read_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument(
        "--list-queue-items",
        action="store_true",
        help="print queue item IDs and recommended actions without appending corrections",
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
    if not args.list_queue_items:
        if not args.queue_item_id:
            parser.error("--queue-item-id is required unless --list-queue-items is used")
        if not args.decision:
            parser.error("--decision is required unless --list-queue-items is used")
    return args


def queue_listing(queue_path: Path) -> dict[str, Any]:
    payload = read_json(queue_path)
    queue = payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("queue file must contain a queue list")

    items = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        trigger = item.get("trigger_inspection")
        if not isinstance(trigger, dict):
            trigger = {}
        property_record = item.get("property")
        if not isinstance(property_record, dict):
            property_record = {}
        contractor = item.get("contractor")
        if not isinstance(contractor, dict):
            contractor = {}
        items.append(
            {
                "queue_item_id": item.get("queue_item_id"),
                "source_permit_number": item.get("source_permit_number"),
                "priority": item.get("priority"),
                "address": property_record.get("normalized_address"),
                "contractor": contractor.get("name"),
                "trigger_date": trigger.get("inspection_date"),
                "trigger_type": trigger.get("inspection_type_normalized"),
                "trigger_result": trigger.get("result_normalized"),
                "failure_reason": trigger.get("failure_reason_normalized"),
                "recommended_actions": item.get("recommended_actions", []),
            }
        )

    return {
        "workflow_id": payload.get("workflow_id"),
        "queue_items": len(items),
        "items": items,
    }


def main() -> int:
    args = parse_args()
    if args.list_queue_items:
        print(json.dumps(queue_listing(args.queue_path), indent=2, sort_keys=True))
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
