#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "contracts" / "dallas-electrician-contract-summary-v1"

DATASETS = [
    {
        "dataset_id": "dallas-electrician-sample-v1",
        "label": "Synthetic sample v1",
        "kind": "synthetic",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-sample-v1",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-sequences-v1",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-sample-v1",
    },
    {
        "dataset_id": "dallas-electrician-import-sample-v1",
        "label": "Imported sample v1",
        "kind": "imported",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v1",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-import-sequences-v1",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v1",
    },
    {
        "dataset_id": "dallas-electrician-import-sample-v2",
        "label": "Imported sample v2",
        "kind": "imported",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v2",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-import-sequences-v2",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v2",
    },
]

COMMON_NORMALIZED_FILES = [
    "projects.json",
    "properties.jsonl",
    "permits.jsonl",
    "inspections.jsonl",
    "contractors.jsonl",
]

EXPECTED_TASK_TYPES = [
    "failure_reason_classification",
    "next_inspection_outcome",
    "pattern_extraction",
    "recommended_next_action",
]


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


def collect_dataset_summary(config):
    normalized_dir = config["normalized_dir"]
    fixture_dir = config["fixture_dir"]
    eval_dir = config["eval_dir"]

    common_files_present = {
        name: (normalized_dir / name).exists() for name in COMMON_NORMALIZED_FILES
    }
    source_records_present = (normalized_dir / "source_records.jsonl").exists()
    rule_documents_present = (normalized_dir / "rule_documents.jsonl").exists()

    properties = load_jsonl(normalized_dir / "properties.jsonl")
    permits = load_jsonl(normalized_dir / "permits.jsonl")
    inspections = load_jsonl(normalized_dir / "inspections.jsonl")
    contractors = load_jsonl(normalized_dir / "contractors.jsonl")
    rule_documents = load_jsonl(normalized_dir / "rule_documents.jsonl") if rule_documents_present else []
    source_records = load_jsonl(normalized_dir / "source_records.jsonl") if source_records_present else []
    project = load_json(normalized_dir / "projects.json")

    sequence_payload = load_json(fixture_dir / "permit-inspection-sequences.json")
    pattern_payload = load_json(fixture_dir / "pattern-slices.json")
    tasks = load_jsonl(eval_dir / "tasks.jsonl")
    split_manifest = load_json(eval_dir / "task_splits.json")
    label_reviews = load_json(eval_dir / "label_reviews.json")
    repeated_pattern_slices = [
        pattern_slice
        for pattern_slice in pattern_payload["pattern_slices"]
        if pattern_slice.get("support_summary", {}).get("permit_count", 0) >= 2
    ]

    next_action_support = {}
    for review in label_reviews:
        if review.get("task_type") != "recommended_next_action":
            continue
        actions = tuple(review.get("label_payload", {}).get("reference_actions", []))
        if not actions:
            continue
        support = next_action_support.setdefault(actions, set())
        support.add(review["permit_id"])

    repeated_next_action_groups = {
        "|".join(actions): sorted(permit_ids)
        for actions, permit_ids in next_action_support.items()
        if len(permit_ids) >= 2
    }

    task_counts = {}
    for task in tasks:
        task_type = task["task_type"]
        task_counts[task_type] = task_counts.get(task_type, 0) + 1

    result_vocab = sorted({row.get("result_normalized", "unknown") for row in inspections})
    sequence_coverage_union = sorted(
        {
            task_type
            for sequence in sequence_payload["sequences"]
            for task_type in sequence.get("eval_task_coverage", [])
        }
    )

    return {
        "dataset_id": config["dataset_id"],
        "label": config["label"],
        "kind": config["kind"],
        "project_name": project["name"],
        "normalized_files_present": common_files_present,
        "has_source_records": source_records_present,
        "has_rule_documents": rule_documents_present,
        "counts": {
            "properties": len(properties),
            "permits": len(permits),
            "inspections": len(inspections),
            "contractors": len(contractors),
            "rule_documents": len(rule_documents),
            "source_records": len(source_records),
            "sequences": len(sequence_payload["sequences"]),
            "pattern_slices": len(pattern_payload["pattern_slices"]),
            "tasks": len(tasks),
            "label_reviews": len(label_reviews),
            "dev_tasks": split_manifest["counts"]["dev"],
            "test_tasks": split_manifest["counts"]["test"],
            "repeated_pattern_slices": len(repeated_pattern_slices),
            "max_pattern_permit_support": max(
                (
                    pattern_slice.get("support_summary", {}).get("permit_count", 0)
                    for pattern_slice in pattern_payload["pattern_slices"]
                ),
                default=0,
            ),
            "repeated_next_action_groups": len(repeated_next_action_groups),
        },
        "inspection_result_vocabulary": result_vocab,
        "task_types": sorted(task_counts),
        "task_family_counts": task_counts,
        "sequence_coverage_union": sequence_coverage_union,
        "label_review_fields": sorted(label_reviews[0].keys()) if label_reviews else [],
        "repeated_next_action_groups": repeated_next_action_groups,
        "paths": {
            "normalized_dir": str(normalized_dir.relative_to(ROOT)),
            "fixture_dir": str(fixture_dir.relative_to(ROOT)),
            "eval_dir": str(eval_dir.relative_to(ROOT)),
        },
    }


def build_checks(dataset_summaries):
    checks = []

    checks.append(
        {
            "check_id": "normalized-common-files-present",
            "description": "All datasets keep the shared normalized MVP files.",
            "passed": all(
                all(summary["normalized_files_present"].values()) for summary in dataset_summaries
            ),
        }
    )

    checks.append(
        {
            "check_id": "source-records-optional-shape",
            "description": "Imported datasets include source lineage rows while the synthetic scaffold does not require them.",
            "passed": all(
                summary["has_source_records"] if summary["kind"] == "imported" else not summary["has_source_records"]
                for summary in dataset_summaries
            ),
        }
    )

    checks.append(
        {
            "check_id": "rule-documents-imported-workflow",
            "description": "Imported datasets include optional rule_documents.jsonl while the synthetic scaffold can stay minimal.",
            "passed": all(
                summary["has_rule_documents"] if summary["kind"] == "imported" else not summary["has_rule_documents"]
                for summary in dataset_summaries
            ),
        }
    )

    checks.append(
        {
            "check_id": "fixture-sequences-present",
            "description": "Every scaffold emits at least one permit-inspection sequence for downstream task generation.",
            "passed": all(summary["counts"]["sequences"] >= 1 for summary in dataset_summaries),
        }
    )

    checks.append(
        {
            "check_id": "fixture-pattern-slices-present",
            "description": "Every scaffold emits pattern slices for the pattern-extraction eval family.",
            "passed": all(summary["counts"]["pattern_slices"] >= 1 for summary in dataset_summaries),
        }
    )

    expected_task_type_set = set(EXPECTED_TASK_TYPES)
    checks.append(
        {
            "check_id": "eval-task-families-stable",
            "description": "Every eval scaffold exposes the same four Dallas task families.",
            "passed": all(set(summary["task_types"]) == expected_task_type_set for summary in dataset_summaries),
        }
    )

    checks.append(
        {
            "check_id": "eval-test-split-matches-pattern-slices",
            "description": "Every eval scaffold keeps pattern extraction isolated in test, with one test row per pattern slice.",
            "passed": all(
                summary["counts"]["test_tasks"] == summary["counts"]["pattern_slices"]
                for summary in dataset_summaries
            ),
        }
    )

    checks.append(
        {
            "check_id": "label-review-schema-stable",
            "description": "Reviewed label rows keep one shared field contract across synthetic and imported scaffolds.",
            "passed": len({tuple(summary["label_review_fields"]) for summary in dataset_summaries}) == 1,
        }
    )

    imported_summaries = [summary for summary in dataset_summaries if summary["kind"] == "imported"]
    checks.append(
        {
            "check_id": "latest-import-repeats-pattern-support",
            "description": "The latest imported sample moves recurring pattern slices beyond one-off support.",
            "passed": bool(imported_summaries)
            and imported_summaries[-1]["counts"]["repeated_pattern_slices"] >= 3
            and imported_summaries[-1]["counts"]["max_pattern_permit_support"] >= 2,
        }
    )

    widening_pairs = zip(dataset_summaries, dataset_summaries[1:])
    checks.append(
        {
            "check_id": "widening-counts-monotonic",
            "description": "Imported samples widen the scaffold monotonically for permits, inspections, tasks, and source lineage.",
            "passed": all(
                later["counts"]["permits"] >= earlier["counts"]["permits"]
                and later["counts"]["inspections"] >= earlier["counts"]["inspections"]
                and later["counts"]["tasks"] >= earlier["counts"]["tasks"]
                and later["counts"]["source_records"] >= earlier["counts"]["source_records"]
                for earlier, later in widening_pairs
            ),
        }
    )

    return checks


def build_summary(dataset_summaries, checks):
    latest_imported = next(
        (summary for summary in reversed(dataset_summaries) if summary["kind"] == "imported"),
        None,
    )
    if latest_imported and latest_imported["counts"]["repeated_pattern_slices"] >= 3:
        next_gap = (
            "Keep the edge-case coverage report current and promote the most important repeated-support "
            "expectations into contract checks before widening the imported fixture again."
        )
    else:
        next_gap = (
            "Broaden the imported Dallas fixture so pattern slices and reviewed labels are supported by more "
            "than one or two permit sequences per recurring pattern."
        )

    return {
        "summary_id": "dallas-electrician-contract-summary-v1",
        "focus": "Dallas electricians MVP synthetic vs imported scaffold contract comparison",
        "datasets": dataset_summaries,
        "checks": checks,
        "overall_passed": all(check["passed"] for check in checks),
        "intentional_differences": [
            "Imported scaffolds add source lineage through source_records.jsonl while the synthetic sample stays minimal.",
            "Imported scaffolds now also add optional Dallas rule-document context through rule_documents.jsonl while the synthetic sample stays minimal.",
            "Normalized row counts, eval task totals, and reviewed label totals grow across imported samples as the raw CSV fixtures widen.",
            "Inspection result vocabulary broadens in imported v2 to include cancelled, not_ready, and unknown without changing downstream task families or split shapes.",
        ],
        "next_gap": next_gap,
    }


def build_markdown(summary):
    lines = [
        "# Dallas Electrician Contract Summary V1",
        "",
        "This artifact checks that the Dallas electricians MVP keeps one stable downstream contract across the synthetic scaffold and the imported CSV-backed samples.",
        "",
        "## Overall Result",
        "",
        f"- Overall passed: `{str(summary['overall_passed']).lower()}`",
        f"- Datasets compared: `{len(summary['datasets'])}`",
        f"- Next gap: {summary['next_gap']}",
        "",
        "## Contract Checks",
        "",
    ]

    for check in summary["checks"]:
        status = "pass" if check["passed"] else "fail"
        lines.append(f"- `{status}` `{check['check_id']}`: {check['description']}")

    lines.extend(["", "## Dataset Matrix", ""])

    for dataset in summary["datasets"]:
        counts = dataset["counts"]
        lines.extend(
            [
                f"### {dataset['label']}",
                "",
                f"- Dataset id: `{dataset['dataset_id']}`",
                f"- Kind: `{dataset['kind']}`",
                f"- Normalized counts: `{counts['properties']}` properties, `{counts['permits']}` permits, `{counts['inspections']}` inspections, `{counts['contractors']}` contractors, `{counts['rule_documents']}` rule documents, `{counts['source_records']}` source records",
                f"- Fixture counts: `{counts['sequences']}` sequences, `{counts['pattern_slices']}` pattern slices, `{counts['repeated_pattern_slices']}` repeated slices, max permit support `{counts['max_pattern_permit_support']}`",
                f"- Eval counts: `{counts['tasks']}` tasks, `{counts['label_reviews']}` reviewed label rows, `{counts['repeated_next_action_groups']}` repeated next-action groups, `{counts['dev_tasks']}` dev, `{counts['test_tasks']}` test",
                f"- Inspection result vocabulary: `{', '.join(dataset['inspection_result_vocabulary'])}`",
                f"- Task families: `{', '.join(dataset['task_types'])}`",
                f"- Paths: `{dataset['paths']['normalized_dir']}`, `{dataset['paths']['fixture_dir']}`, `{dataset['paths']['eval_dir']}`",
                "",
            ]
        )

    lines.extend(["## Intentional Differences", ""])
    for item in summary["intentional_differences"]:
        lines.append(f"- {item}")

    lines.append("")
    return "\n".join(lines)


def main():
    dataset_summaries = [collect_dataset_summary(config) for config in DATASETS]
    checks = build_checks(dataset_summaries)
    summary = build_summary(dataset_summaries, checks)

    write_json(DEFAULT_OUTPUT_DIR / "summary.json", summary)
    write_text(DEFAULT_OUTPUT_DIR / "summary.md", build_markdown(summary))


if __name__ == "__main__":
    main()
