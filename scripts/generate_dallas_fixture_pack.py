#!/usr/bin/env python3

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "generated" / "normalized" / "dallas-electrician-sample-v1"
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "fixtures" / "dallas-electrician-sequences-v1"


PERMIT_TYPE_LABELS = {
    "electrical_new": "new residential electrical",
    "electrical_remodel": "residential electrical remodel",
    "electrical_repair": "residential electrical repair",
    "electrical_service_upgrade": "residential electrical service upgrade",
    "electrical_misc": "residential electrical",
    "unknown": "residential electrical",
}

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

FAILURE_REASON_SUMMARIES = {
    "missing_permit_or_scope_mismatch": "scope and permit mismatch",
    "incomplete_work": "incomplete work before final approval",
    "panel_or_service_issue": "panel and service corrections",
    "wiring_or_device_issue": "wiring and device corrections",
    "grounding_or_bonding_issue": "grounding and bonding corrections",
    "labeling_or_documentation_issue": "labeling and documentation corrections",
    "access_or_scheduling_issue": "site access and scheduling problems",
    "other": "repeat local correction issues",
    "unknown": "unclear local correction issues",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate the Dallas electrician fixture pack from normalized permit and inspection rows."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


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
        next_result = inspections[index + 1].get("result_normalized")
        if next_result == "pass" and "schedule_reinspection" not in actions:
            actions.append("schedule_reinspection")
    return actions


def build_sequence_summary(permit, inspections):
    permit_label = PERMIT_TYPE_LABELS.get(
        permit.get("permit_type_normalized"), "residential electrical"
    )
    result_path = ", ".join(inspection["result_normalized"] for inspection in inspections)
    failed_reasons = [
        inspection.get("failure_reason_normalized")
        for inspection in inspections
        if inspection.get("failure_reason_normalized")
    ]
    if failed_reasons:
        dominant_reason = Counter(failed_reasons).most_common(1)[0][0]
        reason_summary = FAILURE_REASON_SUMMARIES.get(dominant_reason, "repeat local correction issues")
        return (
            f"{permit_label.capitalize()} permit with a {result_path} inspection path "
            f"and {reason_summary}."
        )
    return f"{permit_label.capitalize()} permit with a {result_path} inspection path."


def build_sequences(properties, permits, inspections, contractors):
    properties_by_id = {row["property_id"]: row for row in properties}
    contractors_by_id = {row["contractor_id"]: row for row in contractors}
    inspections_by_permit = defaultdict(list)
    for inspection in inspections:
        inspections_by_permit[inspection["permit_id"]].append(inspection)

    sequences = []
    for permit in sorted(permits, key=lambda row: row["permit_id"]):
        permit_inspections = sorted(
            inspections_by_permit[permit["permit_id"]],
            key=lambda row: (row.get("inspection_date") or "", row["inspection_id"]),
        )
        if not permit_inspections:
            continue

        property_record = properties_by_id[permit["property_id"]]
        contractor = contractors_by_id.get(permit.get("contractor_id"))
        eval_task_coverage = []
        if len(permit_inspections) > 1:
            eval_task_coverage.append("next_inspection_outcome")
        if any(
            row.get("result_normalized") == "fail"
            and row.get("failure_reason_normalized")
            for row in permit_inspections
        ):
            eval_task_coverage.append("failure_reason_classification")
        if any(
            row.get("result_normalized") in {"fail", "partial", "not_ready"}
            for row in permit_inspections[:-1]
        ):
            eval_task_coverage.append("recommended_next_action")

        sequence = {
            "sequence_id": permit["permit_id"].replace("permit:", "sequence:", 1),
            "sequence_summary": build_sequence_summary(permit, permit_inspections),
            "property": property_record,
            "permit": permit,
            "inspections": permit_inspections,
            "eval_task_coverage": eval_task_coverage,
            "reference_actions": build_reference_actions(permit_inspections),
        }
        if contractor:
            sequence["contractor"] = contractor
        sequences.append(sequence)

    return sequences


def build_pattern_summary(group):
    failed_reasons = []
    for inspection in group["inspections"]:
        reason = inspection.get("failure_reason_normalized")
        if reason:
            failed_reasons.append(reason)

    dominant_reason = Counter(failed_reasons).most_common(1)[0][0] if failed_reasons else "other"
    reason_summary = FAILURE_REASON_SUMMARIES.get(dominant_reason, "repeat local correction issues")
    permit_type = group["permit_type_normalized"].replace("_", " ")
    zip_code = group["zip_code"]
    inspection_type = group["inspection_type_normalized"].replace("_", " ")
    return {
        "pattern_summary": (
            f"{permit_type.capitalize()} inspections in {zip_code} show a repeated pattern around "
            f"{reason_summary}."
        ),
        "support_count": group["issue_count"],
        "why_it_matters": (
            f"This slice can drive Dallas-specific {inspection_type} prep and next-action guidance "
            f"for electricians working similar jobs."
        ),
    }


def build_pattern_slices(sequences):
    groups = {}
    for sequence in sequences:
        permit = sequence["permit"]
        zip_code = sequence["property"].get("zip_code")
        if not zip_code:
            continue
        for inspection in sequence["inspections"]:
            result = inspection.get("result_normalized")
            if result not in {"fail", "partial"}:
                continue
            key = (
                permit["permit_type_normalized"],
                zip_code,
                inspection["inspection_type_normalized"],
            )
            group = groups.setdefault(
                key,
                {
                    "permit_type_normalized": permit["permit_type_normalized"],
                    "zip_code": zip_code,
                    "inspection_type_normalized": inspection["inspection_type_normalized"],
                    "permit_ids": set(),
                    "inspections": [],
                    "failed_inspection_count": 0,
                    "failed_or_partial_inspection_count": 0,
                },
            )
            group["permit_ids"].add(permit["permit_id"])
            group["inspections"].append(inspection)
            group["failed_or_partial_inspection_count"] += 1
            if result == "fail":
                group["failed_inspection_count"] += 1

    slices = []
    sorted_keys = sorted(
        groups,
        key=lambda key: (
            -groups[key]["failed_or_partial_inspection_count"],
            key[1],
            key[0],
            key[2],
        ),
    )
    for permit_type_normalized, zip_code, inspection_type_normalized in sorted_keys:
        group = groups[(permit_type_normalized, zip_code, inspection_type_normalized)]
        issue_key = (
            "failed_inspection_count"
            if group["failed_inspection_count"] == group["failed_or_partial_inspection_count"]
            else "failed_or_partial_inspection_count"
        )
        group["issue_count"] = group[issue_key]
        slice_id = (
            f"slice:dallas:{permit_type_normalized.replace('electrical_', '').replace('_', '-')}:"
            f"{inspection_type_normalized.replace('_', '-')}:"
            f"{zip_code}"
        )
        slices.append(
            {
                "slice_id": slice_id,
                "group_by": "zip_code",
                "filters": {
                    "permit_type_normalized": permit_type_normalized,
                    "zip_code": zip_code,
                    "inspection_type_normalized": inspection_type_normalized,
                },
                "support_summary": {
                    "permit_count": len(group["permit_ids"]),
                    "inspection_count": len(group["inspections"]),
                    issue_key: group["issue_count"],
                },
                "reference_pattern": build_pattern_summary(group),
                "task_type": "pattern_extraction",
            }
        )

    return slices


def main():
    args = parse_args()
    properties = load_jsonl(args.input_dir / "properties.jsonl")
    permits = load_jsonl(args.input_dir / "permits.jsonl")
    inspections = load_jsonl(args.input_dir / "inspections.jsonl")
    contractors_path = args.input_dir / "contractors.jsonl"
    contractors = load_jsonl(contractors_path) if contractors_path.exists() else []

    sequences = build_sequences(properties, permits, inspections, contractors)
    pattern_slices = build_pattern_slices(sequences)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        args.output_dir / "permit-inspection-sequences.json",
        {
            "fixture_pack_id": "dallas-electrician-sequences-v1",
            "generated_for": {
                "locality": "Dallas, Texas",
                "trade": "electricians",
                "workflow": "residential electrical permits and inspections",
            },
            "generated_by": "scripts/generate_dallas_fixture_pack.py",
            "source_dataset_dir": str(args.input_dir.relative_to(ROOT)),
            "sequences": sequences,
        },
    )
    write_json(
        args.output_dir / "pattern-slices.json",
        {
            "fixture_pack_id": "dallas-electrician-sequences-v1",
            "generated_by": "scripts/generate_dallas_fixture_pack.py",
            "source_dataset_dir": str(args.input_dir.relative_to(ROOT)),
            "pattern_slices": pattern_slices,
        },
    )


if __name__ == "__main__":
    main()
