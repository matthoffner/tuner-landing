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
        action_labels = [ACTION_LABELS.get(action, action.replace("_", " ")) for action in actions]

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
                "recommended_action_labels": action_labels,
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
    latest_by_queue_item = {}
    for event in events:
        queue_item_id = event.get("queue_item_id")
        if not queue_item_id:
            continue
        latest_by_queue_item[queue_item_id] = {
            "correction_id": event.get("correction_id"),
            "captured_at": event.get("captured_at"),
            "decision": event.get("decision"),
            "corrected_actions": event.get("corrected_actions", []),
        }
    return {
        "ledger_path": "generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl",
        "total_events": len(events),
        "queue_items_with_corrections": len(latest_by_queue_item),
        "decision_counts": dict(sorted(decision_counts.items())),
        "invalid_lines": invalid_lines,
        "latest_by_queue_item": latest_by_queue_item,
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
        "queue": items,
    }


def build_markdown(payload):
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
        "",
        "## Action Queue",
        "",
    ]

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
        grid-template-columns: repeat(4, minmax(120px, 1fr));
        gap: 10px;
        min-width: min(540px, 100%);
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
        </div>
      </header>
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
