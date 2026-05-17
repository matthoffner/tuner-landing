#!/usr/bin/env python3

import json
from collections import Counter, defaultdict
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NORMALIZED_DIR = ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v2"
DEFAULT_EVAL_DIR = ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v2"
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "workflows" / "dallas-inspection-workflow-v1"

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


def build_payload(items):
    return {
        "workflow_id": "dallas-inspection-workflow-v1",
        "generated_by": "scripts/generate_dallas_inspection_workflow.py",
        "source_dataset_dir": "generated/normalized/dallas-electrician-import-sample-v2",
        "source_eval_dir": "generated/evals/dallas-electrician-import-sample-v2",
        "workflow_type": "reviewed-inspection-action-queue",
        "summary": build_summary(items),
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
    rows = []
    for item in payload["queue"]:
        trigger = item["trigger_inspection"]
        followup = item["expected_followup"]
        actions = "".join(
            f"<li>{escape(label)}</li>"
            for label in item["recommended_action_labels"]
        )
        rows.append(
            f"""
            <article class="queue-item priority-{css_class(item['priority'])}">
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
        grid-template-columns: repeat(3, minmax(120px, 1fr));
        gap: 10px;
        min-width: min(420px, 100%);
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
      @media (max-width: 760px) {{
        header {{ grid-template-columns: 1fr; }}
        .summary {{ grid-template-columns: repeat(3, 1fr); }}
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
        </div>
      </header>
      <section class="queue" aria-label="Inspection action queue">
        {''.join(rows)}
      </section>
    </main>
  </body>
</html>
"""


def main():
    items = build_action_queue(DEFAULT_NORMALIZED_DIR, DEFAULT_EVAL_DIR)
    payload = build_payload(items)
    write_json(DEFAULT_OUTPUT_DIR / "action-queue.json", payload)
    write_text(DEFAULT_OUTPUT_DIR / "action-queue.md", build_markdown(payload))
    write_text(DEFAULT_OUTPUT_DIR / "index.html", build_html(payload))


if __name__ == "__main__":
    main()
