#!/usr/bin/env python3

import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NORMALIZED_DIR = ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v2"
DEFAULT_EVAL_DIR = ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v2"
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1"
CORRECTION_LEDGER_PATH = DEFAULT_OUTPUT_DIR / "operator-corrections.jsonl"

PRIORITY_BY_RESULT = {
    "fail": "high",
    "not_ready": "medium",
    "partial": "medium",
}

ACTION_LABELS = {
    "add_labels_or_documentation": "Add missing labels or documentation",
    "complete_remaining_work": "Complete remaining work",
    "correct_grounding_or_bonding": "Correct grounding or bonding",
    "correct_panel_or_service": "Correct panel or service issue",
    "correct_wiring_or_devices": "Correct wiring or devices",
    "ensure_site_access": "Ensure site access",
    "schedule_reinspection": "Schedule reinspection",
    "verify_scope_and_permit": "Verify scope and permit",
}


def action_labels(actions):
    return [ACTION_LABELS.get(action, action.replace("_", " ")) for action in actions]


def load_json(path: Path):
    with path.open() as handle:
        return json.load(handle)


def load_jsonl(path: Path):
    rows = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def ensure_correction_ledger(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("")


def load_correction_events(path: Path):
    if not path.exists():
        return [], 0

    events = []
    invalid_lines = 0
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                invalid_lines += 1
    return events, invalid_lines


def find_next_inspection(inspections, target_inspection_id):
    for index, inspection in enumerate(inspections):
        if inspection["inspection_id"] == target_inspection_id and index + 1 < len(inspections):
            return inspections[index + 1]
    return None


def build_action_queue(normalized_dir, eval_dir):
    properties = {row["property_id"]: row for row in load_jsonl(normalized_dir / "properties.jsonl")}
    permits = {row["permit_id"]: row for row in load_jsonl(normalized_dir / "permits.jsonl")}
    contractors = {row["contractor_id"]: row for row in load_jsonl(normalized_dir / "contractors.jsonl")}
    inspections = load_jsonl(normalized_dir / "inspections.jsonl")
    label_reviews = load_json(eval_dir / "label_reviews.json")

    inspections_by_permit = defaultdict(list)
    inspections_by_id = {}
    for inspection in inspections:
        inspections_by_permit[inspection["permit_id"]].append(inspection)
        inspections_by_id[inspection["inspection_id"]] = inspection

    for permit_inspections in inspections_by_permit.values():
        permit_inspections.sort(key=lambda row: (row.get("inspection_date") or "", row["inspection_id"]))

    items = []
    for review in label_reviews:
        if review.get("task_type") != "recommended_next_action":
            continue

        permit = permits[review["permit_id"]]
        property_record = properties[permit["property_id"]]
        contractor = contractors.get(permit.get("contractor_id"))
        inspection = inspections_by_id[review["inspection_id"]]
        next_inspection = find_next_inspection(
            inspections_by_permit[review["permit_id"]],
            review["inspection_id"],
        )
        actions = review.get("label_payload", {}).get("reference_actions", [])

        items.append(
            {
                "queue_item_id": review["review_id"].replace("label-review", "workflow-item", 1),
                "permit_id": permit["permit_id"],
                "source_permit_number": permit["source_permit_number"],
                "permit_status": permit["status_normalized"],
                "permit_type_normalized": permit["permit_type_normalized"],
                "property": {
                    "property_id": property_record["property_id"],
                    "normalized_address": property_record["normalized_address"],
                    "zip_code": property_record.get("zip_code"),
                },
                "contractor": {
                    "contractor_id": contractor.get("contractor_id") if contractor else None,
                    "name": contractor.get("name") if contractor else None,
                },
                "trigger_inspection": {
                    "inspection_id": inspection["inspection_id"],
                    "inspection_date": inspection["inspection_date"],
                    "inspection_type_normalized": inspection["inspection_type_normalized"],
                    "result_normalized": inspection["result_normalized"],
                    "failure_reason_normalized": inspection.get("failure_reason_normalized"),
                    "notes_raw": inspection.get("notes_raw"),
                },
                "recommended_actions": actions,
                "recommended_action_labels": action_labels(actions),
                "priority": PRIORITY_BY_RESULT.get(inspection["result_normalized"], "low"),
                "expected_followup": {
                    "inspection_date": next_inspection.get("inspection_date") if next_inspection else None,
                    "inspection_type_normalized": (
                        next_inspection.get("inspection_type_normalized") if next_inspection else None
                    ),
                    "result_normalized": next_inspection.get("result_normalized") if next_inspection else None,
                    "notes_raw": next_inspection.get("notes_raw") if next_inspection else None,
                },
                "evidence": review.get("evidence", []),
            }
        )

    return sorted(
        items,
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(row["priority"], 3),
            row["trigger_inspection"]["inspection_date"],
            row["source_permit_number"],
        ),
    )


def build_summary(items):
    priority_counts = Counter(item["priority"] for item in items)
    action_counts = Counter(action for item in items for action in item["recommended_actions"])
    result_counts = Counter(item["trigger_inspection"]["result_normalized"] for item in items)
    return {
        "queue_items": len(items),
        "priority_counts": dict(sorted(priority_counts.items())),
        "trigger_result_counts": dict(sorted(result_counts.items())),
        "recommended_action_counts": dict(sorted(action_counts.items())),
    }


def build_correction_summary(events, invalid_lines):
    decision_counts = Counter(event.get("decision", "unknown") for event in events)
    latest_by_queue_item = latest_correction_events_by_queue_item(events)
    latest_summary_by_queue_item = {}
    for queue_item_id, event in latest_by_queue_item.items():
        latest_summary_by_queue_item[queue_item_id] = {
            "correction_id": event.get("correction_id"),
            "captured_at": event.get("captured_at"),
            "decision": event.get("decision"),
            "corrected_actions": event.get("corrected_actions", []),
        }
    return {
        "ledger_path": "generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl",
        "total_events": len(events),
        "queue_items_with_corrections": len(latest_summary_by_queue_item),
        "decision_counts": dict(sorted(decision_counts.items())),
        "invalid_lines": invalid_lines,
        "latest_by_queue_item": latest_summary_by_queue_item,
    }


def latest_correction_events_by_queue_item(events):
    latest_by_queue_item = {}
    for event in events:
        queue_item_id = event.get("queue_item_id")
        if not queue_item_id:
            continue
        latest_by_queue_item[queue_item_id] = event
    return latest_by_queue_item


def count_if_present(counter, value):
    if value is None:
        return
    text = str(value).strip()
    if text:
        counter[text] += 1


def counter_payload(counter):
    return dict(sorted(counter.items()))


def build_operator_correction_patterns(events, items):
    items_by_id = {item["queue_item_id"]: item for item in items}
    latest_by_queue_item = latest_correction_events_by_queue_item(events)
    grouped = {}

    for queue_item_id, event in latest_by_queue_item.items():
        if event.get("decision") != "accepted":
            continue
        item = items_by_id.get(queue_item_id)
        if not item:
            continue
        corrected_actions = [
            action for action in event.get("corrected_actions", [])
            if isinstance(action, str) and action
        ]
        if not corrected_actions:
            continue

        key = tuple(corrected_actions)
        group = grouped.setdefault(
            key,
            {
                "corrected_actions": corrected_actions,
                "queue_item_ids": [],
                "source_permit_numbers": set(),
                "trigger_result_counts": Counter(),
                "failure_reason_counts": Counter(),
                "inspection_type_counts": Counter(),
                "observed_followup_result_counts": Counter(),
                "operator_note_examples": [],
            },
        )
        group["queue_item_ids"].append(queue_item_id)
        group["source_permit_numbers"].add(item["source_permit_number"])

        trigger = item.get("trigger_inspection", {})
        followup = item.get("expected_followup", {})
        count_if_present(group["trigger_result_counts"], trigger.get("result_normalized"))
        count_if_present(group["failure_reason_counts"], trigger.get("failure_reason_normalized"))
        count_if_present(group["inspection_type_counts"], trigger.get("inspection_type_normalized"))
        count_if_present(group["observed_followup_result_counts"], followup.get("result_normalized"))

        operator_note = event.get("operator_note")
        if isinstance(operator_note, str) and operator_note.strip():
            group["operator_note_examples"].append(operator_note.strip())

    patterns = []
    for group in grouped.values():
        note_examples = []
        seen_notes = set()
        for note in group["operator_note_examples"]:
            if note in seen_notes:
                continue
            seen_notes.add(note)
            note_examples.append(note)
            if len(note_examples) == 2:
                break

        patterns.append(
            {
                "corrected_actions": group["corrected_actions"],
                "corrected_action_labels": action_labels(group["corrected_actions"]),
                "queue_item_count": len(group["queue_item_ids"]),
                "queue_item_ids": sorted(group["queue_item_ids"]),
                "source_permit_numbers": sorted(group["source_permit_numbers"]),
                "trigger_result_counts": counter_payload(group["trigger_result_counts"]),
                "failure_reason_counts": counter_payload(group["failure_reason_counts"]),
                "inspection_type_counts": counter_payload(group["inspection_type_counts"]),
                "observed_followup_result_counts": counter_payload(
                    group["observed_followup_result_counts"]
                ),
                "operator_note_examples": note_examples,
            }
        )

    patterns.sort(
        key=lambda pattern: (
            -pattern["queue_item_count"],
            pattern["corrected_actions"],
        )
    )
    for index, pattern in enumerate(patterns, start=1):
        pattern["pattern_id"] = f"operator-pattern:accepted:{index:04d}"

    return {
        "source": "latest accepted operator correction per current queue item",
        "accepted_latest_corrections": sum(pattern["queue_item_count"] for pattern in patterns),
        "accepted_pattern_count": len(patterns),
        "patterns": patterns,
    }


def build_payload(items, correction_events=None, invalid_correction_lines=0):
    correction_events = correction_events or []
    return {
        "workflow_id": "dallas-inspection-workflow-v1",
        "generated_by": "scripts/generate_dallas_inspection_workflow.py",
        "source_dataset_dir": "generated/normalized/dallas-electrician-import-sample-v2",
        "source_eval_dir": "generated/evals/dallas-electrician-import-sample-v2",
        "workflow_type": "reviewed-inspection-action-queue",
        "summary": build_summary(items),
        "operator_correction_summary": build_correction_summary(
            correction_events,
            invalid_correction_lines,
        ),
        "operator_correction_patterns": build_operator_correction_patterns(
            correction_events,
            items,
        ),
        "queue": items,
    }


def build_markdown(payload):
    pattern_summary = payload["operator_correction_patterns"]
    lines = [
        "# Dallas Inspection Workflow V1",
        "",
        "This artifact turns reviewed Dallas electrician inspection labels into a concrete action queue. It is still generated from fixture data, but it shows the product shape: after a failed, partial, or not-ready inspection, surface the address, failure context, recommended actions, and observed follow-up.",
        "",
        "## Summary",
        "",
        f"- Queue items: `{payload['summary']['queue_items']}`",
        f"- Priority counts: `{json.dumps(payload['summary']['priority_counts'], sort_keys=True)}`",
        f"- Trigger result counts: `{json.dumps(payload['summary']['trigger_result_counts'], sort_keys=True)}`",
        f"- Operator correction events: `{payload['operator_correction_summary']['total_events']}`",
        f"- Operator correction ledger: `{payload['operator_correction_summary']['ledger_path']}`",
        f"- Accepted correction patterns: `{pattern_summary['accepted_pattern_count']}`",
        "",
        "## Accepted Operator Correction Patterns",
        "",
    ]

    if not pattern_summary["patterns"]:
        lines.extend(["No accepted operator correction patterns have been captured yet.", ""])
    for pattern in pattern_summary["patterns"]:
        lines.extend(
            [
                f"### {pattern['pattern_id']}",
                "",
                f"- Queue items: `{pattern['queue_item_count']}`",
                f"- Actions: `{', '.join(pattern['corrected_action_labels'])}`",
                f"- Action IDs: `{', '.join(pattern['corrected_actions'])}`",
                f"- Trigger results: `{json.dumps(pattern['trigger_result_counts'], sort_keys=True)}`",
                f"- Failure reasons: `{json.dumps(pattern['failure_reason_counts'], sort_keys=True)}`",
                f"- Inspection types: `{json.dumps(pattern['inspection_type_counts'], sort_keys=True)}`",
                f"- Follow-up results: `{json.dumps(pattern['observed_followup_result_counts'], sort_keys=True)}`",
                f"- Example permits: `{', '.join(pattern['source_permit_numbers'])}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Action Queue",
            "",
        ]
    )

    for item in payload["queue"]:
        trigger = item["trigger_inspection"]
        followup = item["expected_followup"]
        lines.extend(
            [
                f"### {item['source_permit_number']} - {item['property']['normalized_address']}",
                "",
                f"- Priority: `{item['priority']}`",
                f"- Contractor: `{item['contractor']['name']}`",
                f"- Trigger: `{trigger['inspection_date']}` `{trigger['inspection_type_normalized']}` -> `{trigger['result_normalized']}`",
                f"- Failure reason: `{trigger.get('failure_reason_normalized') or 'none'}`",
                f"- Recommended actions: `{', '.join(item['recommended_action_labels'])}`",
                f"- Follow-up observed: `{followup.get('inspection_date')}` `{followup.get('inspection_type_normalized')}` -> `{followup.get('result_normalized')}`",
                f"- Evidence: {trigger.get('notes_raw')}",
                "",
            ]
        )

    return "\n".join(lines)


def css_class(value):
    return escape(value.replace("_", "-"))


def build_html(payload):
    summary = payload["summary"]
    correction_summary = payload["operator_correction_summary"]
    pattern_summary = payload["operator_correction_patterns"]
    latest_corrections = correction_summary.get("latest_by_queue_item", {})
    queue_state = json.dumps(
        {
            item["queue_item_id"]: {
                "recommended_actions": item["recommended_actions"],
                "source_permit_number": item["source_permit_number"],
            }
            for item in payload["queue"]
        },
        sort_keys=True,
    ).replace("<", "\\u003c")
    pattern_cards = []
    for pattern in pattern_summary.get("patterns", []):
        actions_text = ", ".join(pattern.get("corrected_action_labels", []))
        action_ids_text = ", ".join(pattern.get("corrected_actions", []))
        source_text = ", ".join(pattern.get("source_permit_numbers", []))
        trigger_text = json.dumps(pattern.get("trigger_result_counts", {}), sort_keys=True)
        failure_text = json.dumps(pattern.get("failure_reason_counts", {}), sort_keys=True)
        followup_text = json.dumps(pattern.get("observed_followup_result_counts", {}), sort_keys=True)
        pattern_cards.append(
            "\n".join(
                [
                    '            <article class="pattern-card">',
                    f"              <h2>{escape(str(pattern.get('queue_item_count')))}x accepted</h2>",
                    f"              <p>{escape(actions_text)}</p>",
                    '              <dl class="pattern-details">',
                    f"                <div><dt>Action IDs</dt><dd>{escape(action_ids_text)}</dd></div>",
                    f"                <div><dt>Triggers</dt><dd>{escape(trigger_text)}</dd></div>",
                    f"                <div><dt>Reasons</dt><dd>{escape(failure_text)}</dd></div>",
                    f"                <div><dt>Follow-up</dt><dd>{escape(followup_text)}</dd></div>",
                    "              </dl>",
                    f"              <p class=\"pattern-examples\">{escape(source_text)}</p>",
                    "            </article>",
                ]
            )
        )
    pattern_section = "\n".join(pattern_cards) if pattern_cards else "<p>No accepted patterns captured yet.</p>"
    rows = []
    for item in payload["queue"]:
        trigger = item["trigger_inspection"]
        followup = item["expected_followup"]
        latest_correction = latest_corrections.get(item["queue_item_id"])
        correction_status = (
            "Latest correction: "
            f"{latest_correction.get('decision')} at {latest_correction.get('captured_at')}"
            if latest_correction
            else "No correction captured"
        )
        recommended_actions_text = ", ".join(item["recommended_actions"])
        actions = "".join(
            f"<li>{escape(label)}</li>"
            for label in item["recommended_action_labels"]
        )
        rows.append(
            f"""
            <article class="queue-item priority-{css_class(item['priority'])}" data-queue-item-id="{escape(item['queue_item_id'])}">
              <div class="queue-topline">
                <div>
                  <h2>{escape(item['source_permit_number'])}</h2>
                  <p>{escape(item['property']['normalized_address'])}</p>
                </div>
                <span class="priority">{escape(item['priority'])}</span>
              </div>
              <dl>
                <div><dt>Contractor</dt><dd>{escape(item['contractor']['name'] or 'Unknown')}</dd></div>
                <div><dt>Trigger</dt><dd>{escape(trigger['inspection_date'])} {escape(trigger['inspection_type_normalized'])} -> {escape(trigger['result_normalized'])}</dd></div>
                <div><dt>Reason</dt><dd>{escape(trigger.get('failure_reason_normalized') or 'none')}</dd></div>
                <div><dt>Follow-up</dt><dd>{escape(str(followup.get('inspection_date')))} {escape(str(followup.get('inspection_type_normalized')))} -> {escape(str(followup.get('result_normalized')))}</dd></div>
              </dl>
              <div class="actions">
                <h3>Recommended Actions</h3>
                <ul>{actions}</ul>
              </div>
              <p class="evidence">{escape(trigger.get('notes_raw') or '')}</p>
              <div class="correction">
                <h3>Operator Correction</h3>
                <div class="correction-buttons" aria-label="Correction decision">
                  <button type="button" data-decision="accepted">Accept</button>
                  <button type="button" data-decision="rejected">Reject</button>
                  <button type="button" data-decision="edited">Save Edit</button>
                </div>
                <label>
                  <span>Corrected action IDs</span>
                  <input class="corrected-actions" value="{escape(recommended_actions_text)}">
                </label>
                <label>
                  <span>Operator note</span>
                  <textarea class="operator-note" rows="2"></textarea>
                </label>
                <p class="correction-status">{escape(correction_status)}</p>
              </div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Dallas Inspection Workflow</title>
    <style>
      :root {{
        --ink: #18201c;
        --muted: #627067;
        --line: #d8dfd9;
        --paper: #fbfcf8;
        --panel: #ffffff;
        --high: #b42318;
        --medium: #8a5a00;
        --accent: #1f6f5b;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      main {{
        max-width: 1180px;
        margin: 0 auto;
        padding: 32px 20px 56px;
      }}
      header {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 24px;
        align-items: end;
        border-bottom: 1px solid var(--line);
        padding-bottom: 20px;
        margin-bottom: 24px;
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: clamp(30px, 5vw, 56px);
        line-height: 1;
      }}
      header p {{
        margin: 0;
        max-width: 760px;
        color: var(--muted);
        font-size: 16px;
        line-height: 1.5;
      }}
      .summary {{
        display: grid;
        grid-template-columns: repeat(5, minmax(110px, 1fr));
        gap: 10px;
        min-width: min(640px, 100%);
      }}
      .metric {{
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 14px;
      }}
      .metric strong {{
        display: block;
        font-size: 24px;
      }}
      .metric span {{
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
      }}
      .queue {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 14px;
      }}
      .patterns {{
        margin: 0 0 24px;
      }}
      .section-heading {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: end;
        margin-bottom: 12px;
      }}
      .section-heading h2 {{
        margin: 0;
        font-size: 21px;
      }}
      .section-heading p {{
        margin: 0;
        max-width: 620px;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.45;
      }}
      .pattern-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 12px;
      }}
      .pattern-card {{
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 14px;
      }}
      .pattern-card h2 {{
        margin: 0 0 6px;
        font-size: 17px;
      }}
      .pattern-card p {{
        margin: 0;
      }}
      .pattern-card > p {{
        color: var(--ink);
        line-height: 1.35;
      }}
      .pattern-details {{
        margin: 12px 0;
      }}
      .pattern-details div {{
        grid-template-columns: 82px minmax(0, 1fr);
      }}
      .pattern-examples {{
        color: var(--muted);
        font-size: 12px;
        line-height: 1.4;
      }}
      .queue-item {{
        border: 1px solid var(--line);
        border-left: 5px solid var(--accent);
        background: var(--panel);
        padding: 16px;
      }}
      .priority-high {{ border-left-color: var(--high); }}
      .priority-medium {{ border-left-color: var(--medium); }}
      .queue-topline {{
        display: flex;
        justify-content: space-between;
        gap: 14px;
        align-items: flex-start;
      }}
      h2 {{
        margin: 0 0 4px;
        font-size: 19px;
      }}
      .queue-topline p {{
        margin: 0;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.35;
      }}
      .priority {{
        border: 1px solid var(--line);
        padding: 4px 8px;
        font-size: 12px;
        text-transform: uppercase;
        white-space: nowrap;
      }}
      dl {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        margin: 16px 0;
      }}
      dl div {{
        display: grid;
        grid-template-columns: 86px minmax(0, 1fr);
        gap: 10px;
      }}
      dt {{
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
      }}
      dd {{
        margin: 0;
        font-size: 14px;
      }}
      h3 {{
        margin: 0 0 8px;
        font-size: 13px;
        text-transform: uppercase;
        color: var(--muted);
      }}
      ul {{
        margin: 0;
        padding-left: 18px;
      }}
      li {{ margin: 4px 0; }}
      .evidence {{
        margin: 14px 0 0;
        padding-top: 12px;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 13px;
        line-height: 1.45;
      }}
      .correction {{
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid var(--line);
      }}
      .correction-buttons {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 10px;
      }}
      .correction button {{
        border: 1px solid var(--accent);
        background: var(--accent);
        color: #ffffff;
        min-height: 34px;
        padding: 0 10px;
        font-weight: 700;
        cursor: pointer;
      }}
      .correction button[data-decision="rejected"] {{
        border-color: var(--line);
        background: var(--panel);
        color: var(--ink);
      }}
      .correction label {{
        display: grid;
        gap: 4px;
        margin: 8px 0;
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
      }}
      .correction input,
      .correction textarea {{
        width: 100%;
        border: 1px solid var(--line);
        background: #fbfcf8;
        color: var(--ink);
        padding: 8px;
        font: 13px/1.4 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        text-transform: none;
      }}
      .correction-status {{
        margin: 8px 0 0;
        color: var(--muted);
        font-size: 12px;
      }}
      .correction-status.saved {{ color: var(--accent); }}
      .correction-status.pending {{ color: var(--medium); }}
      .correction-status.error {{ color: var(--high); }}
      @media (max-width: 760px) {{
        header {{ grid-template-columns: 1fr; }}
        .summary {{ grid-template-columns: repeat(2, 1fr); }}
        .section-heading {{ align-items: start; flex-direction: column; }}
      }}
      @media (max-width: 520px) {{
        main {{ padding: 22px 14px 40px; }}
        .summary {{ grid-template-columns: 1fr; }}
        dl div {{ grid-template-columns: 1fr; gap: 2px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>Dallas Inspection Workflow</h1>
          <p>Generated from imported Dallas electrician permit and inspection rows. Each item shows the inspection event that needs operational follow-up, the recommended actions, and the observed next inspection outcome in the fixture.</p>
        </div>
        <div class="summary" aria-label="Queue summary">
          <div class="metric"><strong>{summary['queue_items']}</strong><span>items</span></div>
          <div class="metric"><strong>{summary['priority_counts'].get('high', 0)}</strong><span>high priority</span></div>
          <div class="metric"><strong>{summary['priority_counts'].get('medium', 0)}</strong><span>medium priority</span></div>
          <div class="metric"><strong>{correction_summary['total_events']}</strong><span>corrections</span></div>
          <div class="metric"><strong>{pattern_summary['accepted_pattern_count']}</strong><span>patterns</span></div>
        </div>
      </header>
      <section class="patterns" aria-label="Accepted operator correction patterns">
        <div class="section-heading">
          <h2>Accepted Operator Patterns</h2>
          <p>Grouped from the latest accepted correction captured for each current Dallas queue item. These patterns are the reusable operational memory to carry forward before widening the fixture.</p>
        </div>
        <div class="pattern-grid">
          {pattern_section}
        </div>
      </section>
      <section class="queue" aria-label="Inspection action queue">
        {''.join(rows)}
      </section>
    </main>
    <script>
      const queueItems = {queue_state};
      const pendingKey = "automoat.operator-corrections.pending";

      function parseActions(value) {{
        return value.split(",").map((part) => part.trim()).filter(Boolean);
      }}

      function setStatus(article, text, state) {{
        const status = article.querySelector(".correction-status");
        status.textContent = text;
        status.className = `correction-status ${{state || ""}}`;
      }}

      function pendingCorrections() {{
        try {{
          return JSON.parse(localStorage.getItem(pendingKey) || "[]");
        }} catch (_error) {{
          return [];
        }}
      }}

      async function submitCorrection(button) {{
        const article = button.closest(".queue-item");
        const queueItemId = article.dataset.queueItemId;
        const decision = button.dataset.decision;
        const note = article.querySelector(".operator-note").value.trim();
        const correctedActions = parseActions(article.querySelector(".corrected-actions").value);
        const payload = {{
          queue_item_id: queueItemId,
          decision,
          operator_note: note,
          corrected_actions: decision === "rejected" ? [] : correctedActions,
          source: "workflow-html",
        }};

        if (decision === "accepted" && payload.corrected_actions.length === 0) {{
          payload.corrected_actions = queueItems[queueItemId]?.recommended_actions || [];
        }}

        try {{
          const response = await fetch("/api/operator-corrections", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify(payload),
          }});
          if (!response.ok) {{
            throw new Error((await response.text()).trim() || `HTTP ${{response.status}}`);
          }}
          const event = await response.json();
          setStatus(article, `Saved ${{event.decision}} correction at ${{event.captured_at}}`, "saved");
        }} catch (error) {{
          const pending = pendingCorrections();
          pending.push({{
            ...payload,
            captured_at: new Date().toISOString(),
            pending_reason: String(error.message || error),
          }});
          localStorage.setItem(pendingKey, JSON.stringify(pending));
          setStatus(article, "Saved in browser pending cockpit sync", "pending");
        }}
      }}

      document.querySelectorAll("[data-decision]").forEach((button) => {{
        button.addEventListener("click", () => submitCorrection(button));
      }});
    </script>
  </body>
</html>
"""


def main():
    items = build_action_queue(DEFAULT_NORMALIZED_DIR, DEFAULT_EVAL_DIR)
    ensure_correction_ledger(CORRECTION_LEDGER_PATH)
    correction_events, invalid_correction_lines = load_correction_events(CORRECTION_LEDGER_PATH)
    payload = build_payload(items, correction_events, invalid_correction_lines)
    write_json(DEFAULT_OUTPUT_DIR / "action-queue.json", payload)
    write_text(DEFAULT_OUTPUT_DIR / "action-queue.md", build_markdown(payload))
    write_text(DEFAULT_OUTPUT_DIR / "index.html", build_html(payload))


if __name__ == "__main__":
    main()
