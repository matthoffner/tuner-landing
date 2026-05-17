#!/usr/bin/env python3

import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "coverage" / "dallas-electrician-edge-case-coverage-v1"

DATASETS = [
    {
        "dataset_id": "dallas-electrician-sample-v1",
        "label": "Synthetic sample v1",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-sample-v1",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-sequences-v1",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-sample-v1",
    },
    {
        "dataset_id": "dallas-electrician-import-sample-v1",
        "label": "Imported sample v1",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v1",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-import-sequences-v1",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v1",
    },
    {
        "dataset_id": "dallas-electrician-import-sample-v2",
        "label": "Imported sample v2",
        "normalized_dir": ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v2",
        "fixture_dir": ROOT / "generated" / "fixtures" / "dallas-electrician-import-sequences-v2",
        "eval_dir": ROOT / "generated" / "evals" / "dallas-electrician-import-sample-v2",
    },
]

REPEATED_SUPPORT_THRESHOLD = 2


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


def display_path(path: Path):
    return str(path.relative_to(ROOT))


def summarize_counter(counter, support):
    rows = []
    for key in sorted(counter):
        permit_ids = sorted(support[key])
        rows.append(
            {
                "value": key,
                "row_count": counter[key],
                "permit_count": len(permit_ids),
                "permit_ids": permit_ids,
                "repeated": len(permit_ids) >= REPEATED_SUPPORT_THRESHOLD,
            }
        )
    return rows


def collect_result_state_coverage(inspections):
    counter = Counter()
    support = defaultdict(set)
    for inspection in inspections:
        result = inspection.get("result_normalized") or "unknown"
        counter[result] += 1
        support[result].add(inspection["permit_id"])
    return summarize_counter(counter, support)


def collect_failure_reason_coverage(inspections):
    counter = Counter()
    support = defaultdict(set)
    for inspection in inspections:
        reason = inspection.get("failure_reason_normalized")
        if not reason:
            continue
        counter[reason] += 1
        support[reason].add(inspection["permit_id"])
    return summarize_counter(counter, support)


def collect_next_action_coverage(label_reviews):
    counter = Counter()
    support = defaultdict(set)
    for review in label_reviews:
        if review.get("task_type") != "recommended_next_action":
            continue
        actions = review.get("label_payload", {}).get("reference_actions", [])
        if not actions:
            continue
        action_key = "|".join(actions)
        counter[action_key] += 1
        support[action_key].add(review["permit_id"])
    return summarize_counter(counter, support)


def collect_pattern_slice_coverage(pattern_slices):
    rows = []
    for pattern_slice in pattern_slices:
        support_summary = pattern_slice.get("support_summary", {})
        permit_count = support_summary.get("permit_count", 0)
        rows.append(
            {
                "slice_id": pattern_slice["slice_id"],
                "filters": pattern_slice["filters"],
                "permit_count": permit_count,
                "inspection_count": support_summary.get("inspection_count", 0),
                "failed_inspection_count": support_summary.get("failed_inspection_count", 0),
                "failed_or_partial_inspection_count": support_summary.get(
                    "failed_or_partial_inspection_count", 0
                ),
                "repeated": permit_count >= REPEATED_SUPPORT_THRESHOLD,
            }
        )
    return sorted(rows, key=lambda row: (not row["repeated"], row["slice_id"]))


def count_repeated(rows):
    return sum(1 for row in rows if row.get("repeated"))


def collect_dataset_coverage(config):
    inspections = load_jsonl(config["normalized_dir"] / "inspections.jsonl")
    pattern_payload = load_json(config["fixture_dir"] / "pattern-slices.json")
    label_reviews = load_json(config["eval_dir"] / "label_reviews.json")

    result_states = collect_result_state_coverage(inspections)
    failure_reasons = collect_failure_reason_coverage(inspections)
    next_action_groups = collect_next_action_coverage(label_reviews)
    pattern_slices = collect_pattern_slice_coverage(pattern_payload["pattern_slices"])

    return {
        "dataset_id": config["dataset_id"],
        "label": config["label"],
        "paths": {
            "normalized_dir": display_path(config["normalized_dir"]),
            "fixture_dir": display_path(config["fixture_dir"]),
            "eval_dir": display_path(config["eval_dir"]),
        },
        "counts": {
            "result_states": len(result_states),
            "repeated_result_states": count_repeated(result_states),
            "failure_reasons": len(failure_reasons),
            "repeated_failure_reasons": count_repeated(failure_reasons),
            "pattern_slices": len(pattern_slices),
            "repeated_pattern_slices": count_repeated(pattern_slices),
            "next_action_groups": len(next_action_groups),
            "repeated_next_action_groups": count_repeated(next_action_groups),
        },
        "result_states": result_states,
        "failure_reasons": failure_reasons,
        "pattern_slices": pattern_slices,
        "next_action_groups": next_action_groups,
    }


def build_overall_summary(datasets):
    latest = datasets[-1]
    repeated_sections = {
        "result_states": latest["counts"]["repeated_result_states"],
        "failure_reasons": latest["counts"]["repeated_failure_reasons"],
        "pattern_slices": latest["counts"]["repeated_pattern_slices"],
        "next_action_groups": latest["counts"]["repeated_next_action_groups"],
    }
    thin_sections = {
        name: latest["counts"][name] - repeated_count
        for name, repeated_count in repeated_sections.items()
    }
    return {
        "latest_dataset_id": latest["dataset_id"],
        "repeated_support_threshold": REPEATED_SUPPORT_THRESHOLD,
        "latest_repeated_counts": repeated_sections,
        "latest_thin_counts": thin_sections,
        "recommended_next_step": (
            "Use this coverage report to choose the next imported fixture widening target, then promote "
            "the most important repeated-support expectations into contract checks."
        ),
    }


def build_report():
    datasets = [collect_dataset_coverage(config) for config in DATASETS]
    return {
        "coverage_report_id": "dallas-electrician-edge-case-coverage-v1",
        "focus": "Dallas electrician edge-case support across result states, failure reasons, pattern slices, and next-action groups.",
        "generated_by": "scripts/generate_dallas_edge_case_coverage.py",
        "summary": build_overall_summary(datasets),
        "datasets": datasets,
    }


def markdown_table(headers, rows):
    escaped_rows = [
        [str(value).replace("|", "\\|") for value in row]
        for row in rows
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in escaped_rows)
    return lines


def build_markdown(report):
    latest = report["datasets"][-1]
    summary = report["summary"]
    lines = [
        "# Dallas Electrician Edge-Case Coverage V1",
        "",
        "This artifact makes edge-case support explicit across the Dallas electrician scaffolds. Repeated support means at least two distinct permits back the state, label, slice, or action group.",
        "",
        "## Summary",
        "",
        f"- Latest dataset: `{summary['latest_dataset_id']}`",
        f"- Repeated support threshold: `{summary['repeated_support_threshold']}` permits",
        f"- Result states with repeated support: `{summary['latest_repeated_counts']['result_states']}` of `{latest['counts']['result_states']}`",
        f"- Failure reasons with repeated support: `{summary['latest_repeated_counts']['failure_reasons']}` of `{latest['counts']['failure_reasons']}`",
        f"- Pattern slices with repeated support: `{summary['latest_repeated_counts']['pattern_slices']}` of `{latest['counts']['pattern_slices']}`",
        f"- Next-action groups with repeated support: `{summary['latest_repeated_counts']['next_action_groups']}` of `{latest['counts']['next_action_groups']}`",
        f"- Recommended next step: {summary['recommended_next_step']}",
        "",
    ]

    for dataset in report["datasets"]:
        counts = dataset["counts"]
        lines.extend(
            [
                f"## {dataset['label']}",
                "",
                f"- Dataset id: `{dataset['dataset_id']}`",
                f"- Result states: `{counts['repeated_result_states']}` repeated of `{counts['result_states']}`",
                f"- Failure reasons: `{counts['repeated_failure_reasons']}` repeated of `{counts['failure_reasons']}`",
                f"- Pattern slices: `{counts['repeated_pattern_slices']}` repeated of `{counts['pattern_slices']}`",
                f"- Next-action groups: `{counts['repeated_next_action_groups']}` repeated of `{counts['next_action_groups']}`",
                "",
                "### Result States",
                "",
            ]
        )
        lines.extend(
            markdown_table(
                ["state", "rows", "permits", "repeated"],
                [
                    [row["value"], row["row_count"], row["permit_count"], str(row["repeated"]).lower()]
                    for row in dataset["result_states"]
                ],
            )
        )
        lines.extend(["", "### Failure Reasons", ""])
        lines.extend(
            markdown_table(
                ["reason", "rows", "permits", "repeated"],
                [
                    [row["value"], row["row_count"], row["permit_count"], str(row["repeated"]).lower()]
                    for row in dataset["failure_reasons"]
                ],
            )
        )
        lines.extend(["", "### Pattern Slices", ""])
        lines.extend(
            markdown_table(
                ["slice", "permits", "inspections", "repeated"],
                [
                    [
                        row["slice_id"],
                        row["permit_count"],
                        row["inspection_count"],
                        str(row["repeated"]).lower(),
                    ]
                    for row in dataset["pattern_slices"]
                ],
            )
        )
        lines.extend(["", "### Next-Action Groups", ""])
        lines.extend(
            markdown_table(
                ["actions", "rows", "permits", "repeated"],
                [
                    [row["value"], row["row_count"], row["permit_count"], str(row["repeated"]).lower()]
                    for row in dataset["next_action_groups"]
                ],
            )
        )
        lines.append("")

    return "\n".join(lines)


def main():
    report = build_report()
    write_json(DEFAULT_OUTPUT_DIR / "coverage.json", report)
    write_text(DEFAULT_OUTPUT_DIR / "coverage.md", build_markdown(report))


if __name__ == "__main__":
    main()
