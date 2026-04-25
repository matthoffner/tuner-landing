#!/usr/bin/env python3

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "generated" / "normalized" / "dallas-electrician-sample-v1"
DEFAULT_OUTPUT_PATH = (
    ROOT / "generated" / "evals" / "dallas-electrician-sample-v1" / "label_reviews.json"
)


FAILURE_REASON_ACTIONS = {
    "missing_permit_or_scope_mismatch": ["verify_scope_and_permit"],
    "incomplete_work": ["complete_remaining_work"],
    "panel_or_service_issue": ["correct_panel_or_service"],
    "wiring_or_device_issue": ["correct_wiring_or_devices"],
    "grounding_or_bonding_issue": ["correct_grounding_or_bonding"],
    "labeling_or_documentation_issue": ["add_labels_or_documentation"],
    "access_or_scheduling_issue": ["ensure_site_access"],
}

NOTE_ACTION_HINTS = [
    ("label", "add_labels_or_documentation"),
    ("documentation", "add_labels_or_documentation"),
    ("permit", "verify_scope_and_permit"),
    ("scope", "verify_scope_and_permit"),
    ("access", "ensure_site_access"),
    ("schedule", "ensure_site_access"),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate Dallas electrician reviewed label rows from normalized permit and inspection records."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


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


def build_reference_actions(inspections):
    actions = []
    for index, inspection in enumerate(inspections[:-1]):
        if inspection.get("result_normalized") not in {"fail", "partial", "not_ready"}:
            continue
        reason = inspection.get("failure_reason_normalized")
        for action in FAILURE_REASON_ACTIONS.get(reason, []):
            if action not in actions:
                actions.append(action)

        notes = " ".join(
            filter(
                None,
                [
                    inspection.get("notes_raw", ""),
                    inspections[index + 1].get("notes_raw", ""),
                ],
            )
        ).lower()
        for needle, action in NOTE_ACTION_HINTS:
            if needle in notes and action not in actions:
                actions.append(action)

        if inspections[index + 1].get("result_normalized") == "pass":
            if "schedule_reinspection" not in actions:
                actions.append("schedule_reinspection")
    return actions


def build_label_reviews_from_normalized(permits, inspections):
    permits_by_id = {row["permit_id"]: row for row in permits}
    inspections_by_permit = defaultdict(list)
    for inspection in inspections:
        inspections_by_permit[inspection["permit_id"]].append(inspection)

    reviews = []
    failure_counter = 1
    next_action_counter = 1

    for permit_id in sorted(inspections_by_permit):
        permit = permits_by_id.get(permit_id, {})
        permit_inspections = sorted(
            inspections_by_permit[permit_id],
            key=lambda row: (row.get("inspection_date") or "", row["inspection_id"]),
        )

        for index, inspection in enumerate(permit_inspections):
            result = inspection.get("result_normalized")
            if result == "fail" and inspection.get("failure_reason_normalized"):
                reviews.append(
                    {
                        "review_id": f"label-review:dallas:failure-reason:{failure_counter:04d}",
                        "task_id": f"eval:dallas:failure-reason:{failure_counter:04d}",
                        "task_type": "failure_reason_classification",
                        "permit_id": permit_id,
                        "inspection_id": inspection["inspection_id"],
                        "review_status": "normalized_row_generated",
                        "label_source": "normalized_rows",
                        "label_payload": {
                            "failure_reason_normalized": inspection["failure_reason_normalized"],
                        },
                        "evidence": [inspection.get("notes_raw", "")],
                        "metadata": {
                            "permit_type_normalized": permit.get("permit_type_normalized"),
                            "inspection_type_normalized": inspection.get("inspection_type_normalized"),
                        },
                        "reviewer_note": "Derived directly from normalized failed inspection rows and preserved notes.",
                    }
                )
                failure_counter += 1

            if result not in {"fail", "partial", "not_ready"}:
                continue
            if index == len(permit_inspections) - 1:
                continue

            reference_actions = build_reference_actions(permit_inspections[index : index + 2])
            if not reference_actions:
                continue

            followup = permit_inspections[index + 1]
            evidence = [inspection.get("notes_raw", "")]
            evidence.append(
                f"{followup['inspection_date']} {followup['inspection_type_normalized']} -> "
                f"{followup['result_normalized']}: {followup.get('notes_raw', '')}"
            )

            reviews.append(
                {
                    "review_id": f"label-review:dallas:next-action:{next_action_counter:04d}",
                    "task_id": f"eval:dallas:next-action:{next_action_counter:04d}",
                    "task_type": "recommended_next_action",
                    "permit_id": permit_id,
                    "inspection_id": inspection["inspection_id"],
                    "review_status": "normalized_row_generated",
                    "label_source": "normalized_rows",
                    "label_payload": {
                        "reference_actions": reference_actions,
                    },
                    "evidence": evidence,
                    "metadata": {
                        "permit_type_normalized": permit.get("permit_type_normalized"),
                        "latest_result_normalized": result,
                        "followup_result_normalized": followup.get("result_normalized"),
                    },
                    "reviewer_note": "Derived directly from normalized inspection progression and follow-up notes.",
                }
            )
            next_action_counter += 1

    return reviews


def main():
    args = parse_args()
    permits = load_jsonl(args.input_dir / "permits.jsonl")
    inspections = load_jsonl(args.input_dir / "inspections.jsonl")
    reviews = build_label_reviews_from_normalized(permits, inspections)
    write_json(args.output_path, reviews)


if __name__ == "__main__":
    main()
