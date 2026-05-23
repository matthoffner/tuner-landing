#!/usr/bin/env python3
"""Shared helpers for Dallas operator-correction capture."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE_PATH = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1" / "action-queue.json"
DEFAULT_LEDGER_PATH = (
    ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1" / "operator-corrections.jsonl"
)
VALID_CORRECTION_DECISIONS = {"accepted", "rejected", "edited"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_captured_at(value: str | None = None) -> datetime:
    if not value:
        return utc_now()
    normalized = value.strip().replace("Z", "+00:00")
    captured_at = datetime.fromisoformat(normalized)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return captured_at.astimezone(timezone.utc)


def format_captured_at(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_correction_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_correction_events(ledger_path: Path = DEFAULT_LEDGER_PATH) -> tuple[list[dict[str, Any]], int]:
    if not ledger_path.exists():
        return [], 0

    events = []
    invalid_lines = 0
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                invalid_lines += 1
    return events, invalid_lines


def correction_summary(ledger_path: Path = DEFAULT_LEDGER_PATH) -> dict[str, Any]:
    events, invalid_lines = read_correction_events(ledger_path)
    decision_counts = Counter(str(event.get("decision", "unknown")) for event in events)
    latest_by_queue_item: dict[str, dict[str, Any]] = {}
    for event in events:
        queue_item_id = event.get("queue_item_id")
        if isinstance(queue_item_id, str) and queue_item_id:
            latest_by_queue_item[queue_item_id] = event
    return {
        "ledger_path": "generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl",
        "total_events": len(events),
        "queue_items_with_corrections": len(latest_by_queue_item),
        "decision_counts": dict(sorted(decision_counts.items())),
        "invalid_lines": invalid_lines,
        "latest_by_queue_item": latest_by_queue_item,
    }


def queue_item_index(queue_path: Path = DEFAULT_QUEUE_PATH) -> dict[str, dict[str, Any]]:
    queue_payload = read_json(queue_path)
    queue = queue_payload.get("queue", [])
    if not isinstance(queue, list):
        return {}
    return {
        item["queue_item_id"]: item
        for item in queue
        if isinstance(item, dict) and isinstance(item.get("queue_item_id"), str)
    }


def normalize_action_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, list):
        candidates = value
    else:
        raise ValueError("corrected_actions must be a list or comma-separated string")

    actions = []
    for candidate in candidates:
        action = str(candidate).strip()
        if action:
            actions.append(action)
    return actions


def build_operator_correction_event(
    payload: object,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    captured_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("correction payload must be a JSON object")

    queue_item_id = str(payload.get("queue_item_id", "")).strip()
    if not queue_item_id:
        raise ValueError("queue_item_id is required")

    items = queue_item_index(queue_path)
    if queue_item_id not in items:
        raise ValueError(f"unknown queue_item_id: {queue_item_id}")
    item = items[queue_item_id]

    decision = str(payload.get("decision", "")).strip().lower()
    if decision not in VALID_CORRECTION_DECISIONS:
        raise ValueError("decision must be accepted, rejected, or edited")

    recommended_actions = normalize_action_list(item.get("recommended_actions"))
    corrected_actions = normalize_action_list(payload.get("corrected_actions"))
    if decision == "accepted":
        outcome_actions = recommended_actions
    elif decision == "rejected":
        outcome_actions = []
    else:
        if not corrected_actions:
            raise ValueError("edited corrections require corrected_actions")
        outcome_actions = corrected_actions

    operator_note = str(payload.get("operator_note", "")).strip()
    if len(operator_note) > 800:
        operator_note = operator_note[:800]

    trigger = item.get("trigger_inspection", {})
    if not isinstance(trigger, dict):
        trigger = {}

    timestamp = parse_captured_at(captured_at)
    item_suffix = queue_item_id.rsplit(":", 1)[-1]
    return {
        "correction_id": f"operator-correction:{format_correction_stamp(timestamp)}:{item_suffix}",
        "captured_at": format_captured_at(timestamp),
        "queue_item_id": queue_item_id,
        "permit_id": item.get("permit_id"),
        "inspection_id": trigger.get("inspection_id"),
        "source_permit_number": item.get("source_permit_number"),
        "decision": decision,
        "reference_actions": recommended_actions,
        "corrected_actions": outcome_actions,
        "operator_note": operator_note,
        "source": str(payload.get("source") or "mvp-cockpit"),
    }


def append_operator_correction(
    payload: object,
    queue_path: Path = DEFAULT_QUEUE_PATH,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    captured_at: str | None = None,
) -> dict[str, Any]:
    event = build_operator_correction_event(payload, queue_path, captured_at)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event
