#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "generated" / "intake" / "dallas-electrician-sample-v1" / "intake.json"
DEFAULT_OUTPUT = ROOT / "generated" / "discovery" / "dallas-electrician-sample-v1"


def load_json(path: Path):
    with path.open() as handle:
        return json.load(handle)


def write_json(path: Path, payload):
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def build_business_profile(intake):
    keys = [
        "business_name",
        "service_area",
        "trade",
        "customer_focus",
        "job_types",
        "pain_points",
        "systems_of_record",
        "available_data_assets",
        "crew_size",
        "license_context",
        "target_zip_codes",
        "after_hours_or_emergency_work",
        "permit_handling_style",
    ]
    return {key: intake[key] for key in keys if key in intake}


def build_workflow_map(intake):
    lines = [
        "# Workflow Map",
        "",
        "## Business",
        "",
        f"- Business: {intake['business_name']}",
        "- Scope: Dallas residential electrical permits and inspections",
        f"- Primary service area: {intake['service_area_summary']}",
        "",
        "## Current Workflow",
        "",
    ]

    for index, step in enumerate(intake["workflow_steps"], start=1):
        lines.extend(
            [
                f"### {index}. {step['name']}",
                "",
                f"- Owner: {step['owner']}",
                f"- System: {step['system']}",
                f"- Repeated judgment: {step['repeated_judgment']}",
                f"- Delay point: {step['delay_point']}",
                f"- Data produced: {step['data_produced']}",
                f"- Data saved well: {step['data_saved_well']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Likely Moat-Producing Decisions",
            "",
        ]
    )

    for decision in intake["moat_decisions"]:
        lines.append(f"- {decision}")

    return "\n".join(lines) + "\n"


def build_data_gap_plan(intake):
    recommendation = intake["immediate_recommendation"]
    lines = [
        "# Data Gap Plan",
        "",
        "## Priority Order",
        "",
    ]

    for index, source in enumerate(intake["data_sources"], start=1):
        lines.extend(
            [
                f"### {index}. {source['name']}",
                "",
                f"- Source name: {source['source_name']}",
                f"- Why it matters: {source['why_it_matters']}",
                f"- Availability: {source['availability']}",
                f"- Collection difficulty: {source['collection_difficulty']}",
                f"- Privacy sensitivity: {source['privacy_sensitivity']}",
                f"- Expected lift for eval quality: {source['expected_lift_for_eval_quality']}",
                f"- Recommended collection order: {source['recommended_collection_order']}",
                "",
            ]
        )

    lines.extend(
        [
            "## Immediate Recommendation",
            "",
            recommendation["summary"],
            "",
        ]
    )

    for bullet in recommendation["required_fields"]:
        lines.append(f"- {bullet}")

    if recommendation.get("closing_note"):
        lines.extend(
            [
                "",
                recommendation["closing_note"],
            ]
        )

    return "\n".join(lines) + "\n"


def build_discovery_summary(intake):
    sections = intake["discovery_summary"]
    lines = [
        "# Discovery Summary",
        "",
        "## 1. Business Snapshot",
        "",
        sections["business_snapshot"],
        "",
        "## 2. Likely Moat Candidates",
        "",
    ]

    for bullet in sections["likely_moat_candidates"]:
        lines.append(f"- {bullet}")

    lines.extend(
        [
            "",
            "## 3. Best First Eval To Run",
            "",
            sections["best_first_eval"],
            "",
            "## 4. Most Important Missing Data",
            "",
        ]
    )

    for bullet in sections["most_important_missing_data"]:
        lines.append(f"- {bullet}")

    lines.extend(
        [
            "",
            "## 5. Recommendation For The Next 1 To 2 Weeks",
            "",
        ]
    )

    for index, bullet in enumerate(sections["next_weeks_recommendations"], start=1):
        lines.append(f"{index}. {bullet}")

    return "\n".join(lines) + "\n"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate Dallas electrician discovery artifacts from structured intake."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main():
    args = parse_args()
    intake = load_json(args.input)

    args.output.mkdir(parents=True, exist_ok=True)

    write_json(args.output / "business-profile.json", build_business_profile(intake))
    write_json(args.output / "moat-hypotheses.json", intake["moat_hypotheses"])
    write_json(args.output / "eval-opportunities.json", intake["eval_opportunities"])
    (args.output / "workflow-map.md").write_text(build_workflow_map(intake))
    (args.output / "data-gap-plan.md").write_text(build_data_gap_plan(intake))
    (args.output / "discovery-summary.md").write_text(build_discovery_summary(intake))


if __name__ == "__main__":
    main()
