#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = ROOT / "generated" / "fixtures" / "dallas-electrician-sequences-v1"
OUTPUT_DIR = ROOT / "generated" / "evals" / "dallas-electrician-sample-v1"


RULE_DOCUMENT_IDS = {
    "rough_in": ["rule:dallas:residential-electrical-checklist-2025"],
    "service_release": ["rule:dallas:electric-service-guide-2025"],
    "final": ["rule:dallas:residential-electrical-faq-2025"],
    "correction_followup": ["rule:dallas:residential-electrical-faq-2025"],
    "pattern_extraction": ["rule:dallas:electric-service-guide-2025"],
}


def load_json(path: Path):
    with path.open() as handle:
        return json.load(handle)


def build_next_outcome_tasks(sequences):
    tasks = []
    counter = 1
    for sequence in sequences:
        permit = sequence["permit"]
        property_record = sequence["property"]
        inspections = sequence["inspections"]
        if "next_inspection_outcome" not in sequence.get("eval_task_coverage", []):
            continue
        for target_index in range(1, len(inspections)):
            target = inspections[target_index]
            prior = inspections[:target_index]
            task = {
                "task_id": f"eval:dallas:next-outcome:{counter:04d}",
                "task_type": "next_inspection_outcome",
                "input": {
                    "permit_id": permit["permit_id"],
                    "property_id": property_record["property_id"],
                    "inspection_ids_context": [row["inspection_id"] for row in prior],
                    "rule_document_ids": RULE_DOCUMENT_IDS.get(
                        target["inspection_type_normalized"], RULE_DOCUMENT_IDS["final"]
                    ),
                },
                "target": {
                    "result_normalized": target["result_normalized"],
                },
                "metadata": {
                    "sequence_id": sequence["sequence_id"],
                    "permit_type_normalized": permit["permit_type_normalized"],
                    "inspection_type_normalized": target["inspection_type_normalized"],
                    "zip_code": property_record.get("zip_code"),
                    "task_origin": "fixture_pack_writer",
                    "label_basis": "later inspection result in Dallas synthetic permit sequence",
                },
            }
            tasks.append(task)
            counter += 1
    return tasks


def build_failure_reason_tasks(sequences):
    tasks = []
    counter = 1
    for sequence in sequences:
        permit = sequence["permit"]
        property_record = sequence["property"]
        inspections = sequence["inspections"]
        for index, inspection in enumerate(inspections):
            if inspection.get("result_normalized") != "fail":
                continue
            if not inspection.get("failure_reason_normalized"):
                continue
            task = {
                "task_id": f"eval:dallas:failure-reason:{counter:04d}",
                "task_type": "failure_reason_classification",
                "input": {
                    "permit_id": permit["permit_id"],
                    "property_id": property_record["property_id"],
                    "target_inspection_id": inspection["inspection_id"],
                    "inspection_ids_context": [
                        row["inspection_id"] for row in inspections[:index]
                    ],
                    "notes_raw": inspection.get("notes_raw"),
                    "rule_document_ids": RULE_DOCUMENT_IDS.get(
                        inspection["inspection_type_normalized"], RULE_DOCUMENT_IDS["final"]
                    ),
                },
                "target": {
                    "failure_reason_normalized": inspection["failure_reason_normalized"],
                },
                "metadata": {
                    "sequence_id": sequence["sequence_id"],
                    "permit_type_normalized": permit["permit_type_normalized"],
                    "inspection_type_normalized": inspection["inspection_type_normalized"],
                    "result_normalized": inspection["result_normalized"],
                    "zip_code": property_record.get("zip_code"),
                    "task_origin": "fixture_pack_writer",
                    "reviewer_note": "Generated from fixture-pack inspection note plus normalized failure label.",
                },
            }
            tasks.append(task)
            counter += 1
    return tasks


def build_next_action_tasks(sequences):
    tasks = []
    counter = 1
    for sequence in sequences:
        permit = sequence["permit"]
        property_record = sequence["property"]
        contractor = sequence.get("contractor")
        inspections = sequence["inspections"]
        reference_actions = sequence.get("reference_actions", [])
        if not reference_actions:
            continue
        for index, inspection in enumerate(inspections):
            if inspection.get("result_normalized") not in {"fail", "partial", "not_ready"}:
                continue
            if index == len(inspections) - 1:
                continue
            task = {
                "task_id": f"eval:dallas:next-action:{counter:04d}",
                "task_type": "recommended_next_action",
                "input": {
                    "permit_id": permit["permit_id"],
                    "property_id": property_record["property_id"],
                    "inspection_ids_context": [
                        row["inspection_id"] for row in inspections[: index + 1]
                    ],
                    "contractor_id": contractor.get("contractor_id") if contractor else None,
                    "rule_document_ids": RULE_DOCUMENT_IDS.get(
                        inspection["inspection_type_normalized"], RULE_DOCUMENT_IDS["final"]
                    ),
                },
                "target": {
                    "reference_actions": reference_actions,
                },
                "metadata": {
                    "sequence_id": sequence["sequence_id"],
                    "permit_type_normalized": permit["permit_type_normalized"],
                    "latest_result_normalized": inspection["result_normalized"],
                    "zip_code": property_record.get("zip_code"),
                    "task_origin": "fixture_pack_writer",
                    "label_basis": "subsequent successful path in Dallas synthetic permit sequence",
                },
            }
            tasks.append(task)
            counter += 1
    return tasks


def build_pattern_tasks(pattern_slices):
    tasks = []
    for index, pattern_slice in enumerate(pattern_slices, start=1):
        task = {
            "task_id": f"eval:dallas:pattern:{index:04d}",
            "task_type": "pattern_extraction",
            "input": {
                "slice_id": pattern_slice["slice_id"],
                "group_by": pattern_slice["group_by"],
                "filters": pattern_slice["filters"],
                "support_summary": pattern_slice["support_summary"],
                "rule_document_ids": RULE_DOCUMENT_IDS["pattern_extraction"],
            },
            "target": pattern_slice["reference_pattern"],
            "metadata": {
                "task_origin": "fixture_pack_writer",
                "review_standard": "Pattern must stay local, supported by counts, and actionable for a Dallas electrician.",
            },
        }
        tasks.append(task)
    return tasks


def build_label_reviews(tasks, sequences):
    sequence_by_id = {sequence["sequence_id"]: sequence for sequence in sequences}
    reviews = []
    counters = {
        "failure_reason_classification": 1,
        "recommended_next_action": 1,
    }

    for task in tasks:
        task_type = task["task_type"]
        if task_type not in counters:
            continue

        sequence = sequence_by_id[task["metadata"]["sequence_id"]]
        inspections = sequence["inspections"]

        if task_type == "failure_reason_classification":
            target_inspection_id = task["input"]["target_inspection_id"]
            target_inspection = next(
                row for row in inspections if row["inspection_id"] == target_inspection_id
            )
            review = {
                "review_id": f"label-review:dallas:failure-reason:{counters[task_type]:04d}",
                "task_id": task["task_id"],
                "task_type": task_type,
                "permit_id": task["input"]["permit_id"],
                "inspection_id": target_inspection_id,
                "review_status": "fixture_generated",
                "label_source": "fixture_sequence",
                "label_payload": {
                    "failure_reason_normalized": task["target"]["failure_reason_normalized"],
                },
                "evidence": [
                    target_inspection.get("notes_raw", ""),
                ],
                "reviewer_note": "Fixture-backed failure reason derived from the failed inspection note.",
            }
        else:
            context_ids = task["input"]["inspection_ids_context"]
            decision_inspection = next(
                row for row in inspections if row["inspection_id"] == context_ids[-1]
            )
            later_inspections = [
                row for row in inspections if row["inspection_id"] not in context_ids
            ]
            followup = later_inspections[0] if later_inspections else None
            evidence = [decision_inspection.get("notes_raw", "")]
            if followup:
                evidence.append(
                    f"{followup['inspection_date']} {followup['inspection_type_normalized']} -> {followup['result_normalized']}: {followup.get('notes_raw', '')}"
                )
            review = {
                "review_id": f"label-review:dallas:next-action:{counters[task_type]:04d}",
                "task_id": task["task_id"],
                "task_type": task_type,
                "permit_id": task["input"]["permit_id"],
                "inspection_id": decision_inspection["inspection_id"],
                "review_status": "fixture_generated",
                "label_source": "fixture_sequence",
                "label_payload": {
                    "reference_actions": task["target"]["reference_actions"],
                },
                "evidence": evidence,
                "reviewer_note": "Fixture-backed action reference derived from the later successful follow-up path.",
            }

        reviews.append(review)
        counters[task_type] += 1

    return reviews


def assign_splits(tasks):
    for task in tasks:
        task["split"] = "test" if task["task_type"] == "pattern_extraction" else "dev"


def build_split_manifest(tasks):
    counts = {"dev": 0, "test": 0}
    group_keys = {"dev": [], "test": []}

    for task in tasks:
        split = task["split"]
        counts[split] += 1
        metadata = task.get("metadata", {})
        group_key = metadata.get("sequence_id") or task["input"].get("slice_id")
        if group_key and group_key not in group_keys[split]:
            group_keys[split].append(group_key)

    return {
        "dataset_id": "dallas-electrician-sample-v1",
        "generated_by": "scripts/generate_dallas_eval_artifacts.py",
        "split_strategy": "all permit-sequence tasks in dev, all pattern slices in test",
        "counts": counts,
        "group_keys": group_keys,
        "notes": [
            "This dataset is generated deterministically from the Dallas electrician fixture pack.",
            "All rows from the same synthetic permit sequence stay in the same split.",
            "Pattern extraction rows use slice identifiers as the split grouping key.",
        ],
    }


def build_report(tasks, split_manifest, label_reviews):
    counts_by_type = {}
    for task in tasks:
        counts_by_type[task["task_type"]] = counts_by_type.get(task["task_type"], 0) + 1

    lines = [
        "# Dallas Electrician Eval Sample v1",
        "",
        "This sample eval scaffold is generated from the reusable Dallas electrician fixture pack.",
        "",
        "## Summary",
        "",
        f"- Generated by: `scripts/generate_dallas_eval_artifacts.py`",
        f"- Total tasks: `{len(tasks)}`",
        f"- Dev tasks: `{split_manifest['counts']['dev']}`",
        f"- Test tasks: `{split_manifest['counts']['test']}`",
        f"- Reviewed label rows: `{len(label_reviews)}`",
        "",
        "## Task Family Counts",
        "",
    ]

    for task_type in sorted(counts_by_type):
        lines.append(f"- `{task_type}`: `{counts_by_type[task_type]}`")

    lines.extend(
        [
            "",
            "## Source Inputs",
            "",
            "- `generated/fixtures/dallas-electrician-sequences-v1/permit-inspection-sequences.json`",
            "- `generated/fixtures/dallas-electrician-sequences-v1/pattern-slices.json`",
            "- `label_reviews.json` generated from fixture-backed failure labels and next-action references",
            "",
            "## Notes",
            "",
            "- This is implementation scaffolding for the Dallas electricians MVP, not a production benchmark dataset.",
            "- Sequence-backed tasks stay grouped by synthetic permit sequence.",
            "- Pattern extraction stays isolated in the test split to keep slice-style tasks separated from sequence-style tasks.",
            "- Reviewed label rows make failure-reason and next-action supervision explicit instead of leaving them implicit in task targets alone.",
        ]
    )

    return "\n".join(lines) + "\n"


def write_jsonl(path: Path, rows):
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def write_json(path: Path, payload):
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def main():
    sequence_payload = load_json(FIXTURE_DIR / "permit-inspection-sequences.json")
    pattern_payload = load_json(FIXTURE_DIR / "pattern-slices.json")

    tasks = []
    tasks.extend(build_next_outcome_tasks(sequence_payload["sequences"]))
    tasks.extend(build_failure_reason_tasks(sequence_payload["sequences"]))
    tasks.extend(build_next_action_tasks(sequence_payload["sequences"]))
    tasks.extend(build_pattern_tasks(pattern_payload["pattern_slices"]))
    assign_splits(tasks)
    label_reviews = build_label_reviews(tasks, sequence_payload["sequences"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "reports").mkdir(parents=True, exist_ok=True)

    split_manifest = build_split_manifest(tasks)
    report = build_report(tasks, split_manifest, label_reviews)

    write_jsonl(OUTPUT_DIR / "tasks.jsonl", tasks)
    write_json(OUTPUT_DIR / "task_splits.json", split_manifest)
    write_json(OUTPUT_DIR / "label_reviews.json", label_reviews)
    (OUTPUT_DIR / "reports" / "sample-contract.md").write_text(report)


if __name__ == "__main__":
    main()
