#!/usr/bin/env python3
"""Generate the deterministic Dallas Whole-Record Check validation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NORMALIZED_DIR = (
    ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v2"
)
DEFAULT_QUEUE_PATH = (
    ROOT
    / "generated"
    / "workflows"
    / "dallas-inspection-workflow-v1"
    / "action-queue.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "generated" / "whole-record" / "dallas-whole-record-check-v1"
)
CASE_COUNT = 30
PLANTED_OMISSION_COUNT = 10
MAX_SOURCE_RECORDS = 12
MAX_SNAPSHOT_BYTES = 64 * 1024
RELEASE_DATE = "2026-08-19"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def with_fingerprint(value: dict[str, Any], field: str) -> dict[str, Any]:
    payload = dict(value)
    payload[field] = f"sha256:{sha256_hex(value)}"
    return payload


def verify_fingerprint(value: dict[str, Any], field: str) -> bool:
    claimed = value.get(field)
    body = {key: item for key, item in value.items() if key != field}
    return claimed == f"sha256:{sha256_hex(body)}"


def evenly_spaced_cases(queue: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if len(queue) < count:
        raise ValueError(f"need at least {count} queue items; found {len(queue)}")
    ordered = sorted(queue, key=lambda item: str(item.get("queue_item_id", "")))
    if count == 1:
        return [ordered[0]]
    indices = [(index * (len(ordered) - 1)) // (count - 1) for index in range(count)]
    if len(set(indices)) != count:
        raise ValueError("case sampling did not produce unique queue items")
    return [ordered[index] for index in indices]


def stable_record(record: dict[str, Any], record_type: str) -> dict[str, Any]:
    source_id = record.get("source_record_id")
    if not isinstance(source_id, str) or not source_id.startswith("source:"):
        raise ValueError(f"{record_type} is missing a stable source_record_id")
    return {
        "source_id": source_id,
        "record_type": record_type,
        "record": record,
    }


def correction_ledger_metadata(queue_item: dict[str, Any]) -> dict[str, Any]:
    trigger = queue_item.get("trigger_inspection") or {}
    return {
        "contract": "operator-correction-event-compatible/v1",
        "ledger_path": (
            "generated/workflows/dallas-inspection-workflow-v1/"
            "operator-corrections.jsonl"
        ),
        "payload_template": {
            "queue_item_id": queue_item["queue_item_id"],
            "source": "dallas-whole-record-check",
        },
        "context": {
            "permit_id": queue_item.get("permit_id"),
            "inspection_id": trigger.get("inspection_id"),
            "source_permit_number": queue_item.get("source_permit_number"),
        },
        "allowed_decisions": ["accepted", "rejected", "edited"],
        "writes_ledger": False,
    }


def build_snapshot(
    case_number: int,
    queue_item: dict[str, Any],
    permits_by_id: dict[str, dict[str, Any]],
    inspections_by_permit: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    permit_id = queue_item.get("permit_id")
    if permit_id not in permits_by_id:
        raise ValueError(f"missing permit for queue item: {queue_item.get('queue_item_id')}")
    permit = permits_by_id[permit_id]
    inspections = sorted(
        inspections_by_permit.get(permit_id, []),
        key=lambda row: (str(row.get("inspection_date", "")), str(row.get("inspection_id", ""))),
    )
    if not inspections:
        raise ValueError(f"missing inspections for permit: {permit_id}")

    source_records = [stable_record(permit, "permit")]
    source_records.extend(stable_record(row, "inspection") for row in inspections)
    if len(source_records) > MAX_SOURCE_RECORDS:
        raise ValueError(
            f"case {case_number} has {len(source_records)} source records; "
            f"limit is {MAX_SOURCE_RECORDS}"
        )

    inspection_by_id = {row.get("inspection_id"): row for row in inspections}
    trigger = queue_item.get("trigger_inspection") or {}
    trigger_record = inspection_by_id.get(trigger.get("inspection_id"))
    if trigger_record is None:
        raise ValueError(f"trigger inspection is outside permit record: {trigger.get('inspection_id')}")

    expected_actions = queue_item.get("recommended_actions")
    if not isinstance(expected_actions, list) or not expected_actions:
        raise ValueError(f"queue item has no recommended actions: {queue_item.get('queue_item_id')}")
    if any(not isinstance(action, str) or not action for action in expected_actions):
        raise ValueError("recommended actions must be non-empty strings")

    material_source_ids = [
        str(permit["source_record_id"]),
        str(trigger_record["source_record_id"]),
    ]
    case_id = f"dallas-whole-record-case-{case_number:02d}"
    snapshot_body = {
        "schema_version": "dallas-whole-record-case/v1",
        "case_id": case_id,
        "dataset_id": "dallas-electrician-import-sample-v2",
        "record_scope": "one permit and its linked inspection history",
        "bounds": {
            "max_source_records": MAX_SOURCE_RECORDS,
            "max_snapshot_bytes": MAX_SNAPSHOT_BYTES,
            "source_record_count": len(source_records),
        },
        "queue_context": {
            "queue_item_id": queue_item["queue_item_id"],
            "permit_id": permit_id,
            "source_permit_number": queue_item.get("source_permit_number"),
            "trigger_inspection_id": trigger.get("inspection_id"),
            "priority": queue_item.get("priority"),
        },
        "expected_outcome": {
            "recommended_actions": list(expected_actions),
            "material_source_ids": material_source_ids,
        },
        "source_records": source_records,
        "correction_ledger": correction_ledger_metadata(queue_item),
    }
    snapshot = with_fingerprint(snapshot_body, "snapshot_fingerprint")
    if len(canonical_bytes(snapshot)) > MAX_SNAPSHOT_BYTES:
        raise ValueError(f"case {case_number} exceeds the snapshot byte limit")
    return snapshot


def build_candidate(snapshot: dict[str, Any], plant_omission: bool) -> dict[str, Any]:
    expected = snapshot["expected_outcome"]
    actions = list(expected["recommended_actions"])
    evidence_source_ids = list(expected["material_source_ids"])
    omission: dict[str, Any] | None = None
    if plant_omission:
        omitted_action_id = actions.pop()
        omitted_source_id = evidence_source_ids.pop()
        omission = {
            "kind": "retrieval_omission",
            "omitted_action_id": omitted_action_id,
            "omitted_source_id": omitted_source_id,
        }
    candidate_body = {
        "schema_version": "whole-record-candidate/v1",
        "case_id": snapshot["case_id"],
        "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "backend": "deterministic-validation-harness",
        "recommended_actions": actions,
        "evidence_source_ids": evidence_source_ids,
        "planted_omission": omission,
    }
    return with_fingerprint(candidate_body, "candidate_fingerprint")


def compare_candidate(
    snapshot: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    expected = snapshot["expected_outcome"]
    expected_actions = set(expected["recommended_actions"])
    candidate_actions = set(candidate["recommended_actions"])
    expected_sources = set(expected["material_source_ids"])
    candidate_sources = set(candidate["evidence_source_ids"])
    all_snapshot_sources = {
        record["source_id"] for record in snapshot["source_records"]
    }
    mismatch = {
        "missing_action_ids": sorted(expected_actions - candidate_actions),
        "unexpected_action_ids": sorted(candidate_actions - expected_actions),
        "missing_material_source_ids": sorted(expected_sources - candidate_sources),
        "unknown_source_ids": sorted(candidate_sources - all_snapshot_sources),
    }
    is_material_mismatch = any(mismatch.values())
    common = {
        "case_id": snapshot["case_id"],
        "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "queue_item_id": snapshot["queue_context"]["queue_item_id"],
        "correction_ledger": snapshot["correction_ledger"],
    }
    if is_material_mismatch:
        body = {
            "schema_version": "evidence-conflict-card/v1",
            "artifact_type": "evidence_conflict_card",
            "status": "material_mismatch",
            **common,
            "whole_record_action_ids": sorted(expected_actions),
            "retrieved_action_ids": sorted(candidate_actions),
            "whole_record_material_source_ids": sorted(expected_sources),
            "retrieved_source_ids": sorted(candidate_sources),
            "mismatch": mismatch,
        }
        return with_fingerprint(body, "artifact_fingerprint")

    body = {
        "schema_version": "coverage-receipt/v1",
        "artifact_type": "coverage_receipt",
        "status": "agreement",
        **common,
        "covered_action_ids": sorted(expected_actions),
        "covered_source_ids": sorted(expected_sources),
        "mismatch": mismatch,
    }
    return with_fingerprint(body, "artifact_fingerprint")


def build_report(
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    queue_path: Path = DEFAULT_QUEUE_PATH,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    queue_payload = load_json(queue_path)
    queue = queue_payload.get("queue")
    if not isinstance(queue, list):
        raise ValueError("action queue must contain a queue list")

    permits = load_jsonl(normalized_dir / "permits.jsonl")
    inspections = load_jsonl(normalized_dir / "inspections.jsonl")
    permits_by_id = {str(row.get("permit_id")): row for row in permits}
    inspections_by_permit: dict[str, list[dict[str, Any]]] = {}
    for inspection in inspections:
        permit_id = str(inspection.get("permit_id"))
        inspections_by_permit.setdefault(permit_id, []).append(inspection)

    snapshots: dict[str, dict[str, Any]] = {}
    cases: list[dict[str, Any]] = []
    selected = evenly_spaced_cases(queue, CASE_COUNT)
    for case_number, queue_item in enumerate(selected, start=1):
        snapshot = build_snapshot(
            case_number,
            queue_item,
            permits_by_id,
            inspections_by_permit,
        )
        plant_omission = case_number % 3 == 0
        candidate = build_candidate(snapshot, plant_omission)
        result = compare_candidate(snapshot, candidate)
        digest = str(snapshot["snapshot_fingerprint"]).split(":", 1)[1]
        snapshot_path = f"cases/{snapshot['case_id']}--{digest[:16]}.json"
        snapshots[snapshot_path] = snapshot
        cases.append(
            {
                "case_id": snapshot["case_id"],
                "queue_item_id": snapshot["queue_context"]["queue_item_id"],
                "snapshot_path": snapshot_path,
                "snapshot_fingerprint": snapshot["snapshot_fingerprint"],
                "candidate": candidate,
                "result": result,
            }
        )

    planted_cases = [case for case in cases if case["candidate"]["planted_omission"]]
    conflict_cases = [
        case for case in cases if case["result"]["artifact_type"] == "evidence_conflict_card"
    ]
    receipt_cases = [
        case for case in cases if case["result"]["artifact_type"] == "coverage_receipt"
    ]
    if len(planted_cases) != PLANTED_OMISSION_COUNT:
        raise ValueError("validation harness must plant exactly 10 omissions")
    if {case["case_id"] for case in planted_cases} != {
        case["case_id"] for case in conflict_cases
    }:
        raise ValueError("each and only planted omissions must produce a conflict card")

    report_body = {
        "schema_version": "dallas-whole-record-check-report/v1",
        "release_date": RELEASE_DATE,
        "product_name": "Automoat Whole-Record Check",
        "validation_scope": (
            "Deterministic validation over versioned Dallas scaffold records; "
            "not a production accuracy benchmark."
        ),
        "source": {
            "dataset_id": "dallas-electrician-import-sample-v2",
            "workflow_id": queue_payload.get("workflow_id"),
            "queue_path": str(DEFAULT_QUEUE_PATH.relative_to(ROOT)),
            "normalized_dir": str(DEFAULT_NORMALIZED_DIR.relative_to(ROOT)),
        },
        "bounds": {
            "case_count": CASE_COUNT,
            "planted_retrieval_omission_count": PLANTED_OMISSION_COUNT,
            "max_source_records_per_case": MAX_SOURCE_RECORDS,
            "max_snapshot_bytes": MAX_SNAPSHOT_BYTES,
        },
        "summary": {
            "cases_checked": len(cases),
            "coverage_receipts": len(receipt_cases),
            "evidence_conflict_cards": len(conflict_cases),
            "planted_retrieval_omissions": len(planted_cases),
            "planted_omissions_detected": len(conflict_cases),
            "unexpected_conflicts": 0,
        },
        "cases": cases,
    }
    report = with_fingerprint(report_body, "report_fingerprint")
    return report, snapshots


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Automoat Whole-Record Check",
        "",
        (
            "This release adds a backend-neutral verification pass over immutable, bounded "
            "Dallas case snapshots. A matching candidate earns a Coverage Receipt. A material "
            "action or evidence mismatch becomes an Evidence Conflict card for an operator."
        ),
        "",
        f"Release date: `{report['release_date']}`",
        "",
        "## Validation result",
        "",
        f"- Cases checked: `{summary['cases_checked']}`",
        f"- Coverage Receipts: `{summary['coverage_receipts']}`",
        f"- Evidence Conflict cards: `{summary['evidence_conflict_cards']}`",
        f"- Planted retrieval omissions: `{summary['planted_retrieval_omissions']}`",
        f"- Planted omissions detected: `{summary['planted_omissions_detected']}`",
        f"- Unexpected conflicts: `{summary['unexpected_conflicts']}`",
        "",
        "> This is a deterministic regression harness over versioned scaffold records, not a claim about production model accuracy.",
        "",
        "## Case outcomes",
        "",
        "| Case | Outcome | Queue item | Stable mismatch source IDs |",
        "| --- | --- | --- | --- |",
    ]
    for case in report["cases"]:
        result = case["result"]
        missing_sources = result["mismatch"]["missing_material_source_ids"]
        lines.append(
            "| `{}` | {} | `{}` | {} |".format(
                case["case_id"],
                "Coverage Receipt" if result["artifact_type"] == "coverage_receipt" else "Evidence Conflict",
                case["queue_item_id"],
                ", ".join(f"`{source_id}`" for source_id in missing_sources) or "—",
            )
        )
    lines.extend(
        [
            "",
            "Each case file is content-addressed by its SHA-256 fingerprint. Conflict and receipt artifacts carry the existing queue item ID and an operator-correction payload template, but this check never writes to the correction ledger.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(report: dict[str, Any]) -> str:
    summary = report["summary"]
    cards = []
    for case in report["cases"]:
        result = case["result"]
        is_conflict = result["artifact_type"] == "evidence_conflict_card"
        mismatch_sources = result["mismatch"]["missing_material_source_ids"]
        mismatch_actions = result["mismatch"]["missing_action_ids"]
        detail = (
            "Missing action: {}<br>Missing evidence: {}".format(
                escape(", ".join(mismatch_actions)),
                escape(", ".join(mismatch_sources)),
            )
            if is_conflict
            else "Expected actions and material source IDs agree."
        )
        cards.append(
            f'''<article class="card {'conflict' if is_conflict else 'receipt'}">
              <div class="status">{'Evidence Conflict' if is_conflict else 'Coverage Receipt'}</div>
              <h3>{escape(case['case_id'])}</h3>
              <p>{detail}</p>
              <code>{escape(case['queue_item_id'])}</code>
            </article>'''
        )
    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Automoat Whole-Record Check</title>
    <style>
      :root {{ color-scheme: light; --ink:#19222d; --muted:#65707e; --paper:#fffdf7; --line:#d9d4c8; --good:#2f6b46; --warn:#a34628; }}
      * {{ box-sizing:border-box; }}
      body {{ margin:0; color:var(--ink); background:#f2eee5; font-family:ui-sans-serif,system-ui,sans-serif; }}
      main {{ width:min(1120px,calc(100% - 32px)); margin:0 auto; padding:56px 0 80px; }}
      .eyebrow {{ color:#8d4428; font-weight:800; letter-spacing:.1em; text-transform:uppercase; font-size:.76rem; }}
      h1 {{ max-width:820px; margin:12px 0; font:700 clamp(2.6rem,7vw,5.8rem)/.95 Georgia,serif; letter-spacing:-.05em; }}
      .lede {{ max-width:760px; color:var(--muted); font-size:1.1rem; line-height:1.7; }}
      .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:30px 0; }}
      .stat,.card {{ border:1px solid var(--line); border-radius:18px; background:var(--paper); }}
      .stat {{ padding:18px; }} .stat strong {{ display:block; font-size:2rem; }} .stat span {{ color:var(--muted); }}
      .notice {{ padding:16px 18px; border-left:4px solid #b77a31; background:#fff8e7; line-height:1.6; }}
      .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:26px; }}
      .card {{ padding:18px; }} .card h3 {{ margin:10px 0 0; font-size:1rem; }} .card p {{ color:var(--muted); line-height:1.55; min-height:48px; }}
      .card code {{ display:block; overflow-wrap:anywhere; font-size:.72rem; }}
      .status {{ font-size:.74rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
      .receipt .status {{ color:var(--good); }} .conflict .status {{ color:var(--warn); }}
      @media (max-width:800px) {{ .stats,.grid {{ grid-template-columns:1fr 1fr; }} }}
      @media (max-width:520px) {{ .stats,.grid {{ grid-template-columns:1fr; }} }}
    </style>
  </head>
  <body>
    <main>
      <div class="eyebrow">Released {RELEASE_DATE}</div>
      <h1>Catch what retrieval left out.</h1>
      <p class="lede">Automoat now checks an answer against one immutable, bounded case record. Agreement earns a Coverage Receipt. Material evidence or action gaps become Evidence Conflict cards with stable source IDs for operator review.</p>
      <section class="stats" aria-label="Deterministic validation results">
        <div class="stat"><strong>{summary['cases_checked']}</strong><span>Dallas scaffold cases</span></div>
        <div class="stat"><strong>{summary['coverage_receipts']}</strong><span>Coverage Receipts</span></div>
        <div class="stat"><strong>{summary['evidence_conflict_cards']}</strong><span>Evidence Conflicts</span></div>
        <div class="stat"><strong>{summary['planted_omissions_detected']}/{summary['planted_retrieval_omissions']}</strong><span>planted omissions detected</span></div>
      </section>
      <p class="notice"><strong>Validation boundary:</strong> deterministic regression harness over versioned Dallas scaffold records. This is not a production model-accuracy claim.</p>
      <section class="grid">{''.join(cards)}</section>
    </main>
  </body>
</html>
'''


def write_immutable(path: Path, payload: dict[str, Any]) -> None:
    content = pretty_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"refusing to overwrite immutable snapshot: {path}")
        return
    path.write_text(content, encoding="utf-8")


def generated_contents(
    report: dict[str, Any], snapshots: dict[str, dict[str, Any]]
) -> dict[str, str]:
    contents = {path: pretty_json(snapshot) for path, snapshot in snapshots.items()}
    contents["report.json"] = pretty_json(report)
    contents["report.md"] = render_markdown(report)
    contents["index.html"] = render_html(report)
    return contents


def generate(output_dir: Path) -> dict[str, Any]:
    report, snapshots = build_report()
    for relative_path, snapshot in snapshots.items():
        write_immutable(output_dir / relative_path, snapshot)
    for relative_path, content in generated_contents(report, {}).items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return report


def verify(output_dir: Path) -> dict[str, Any]:
    report, snapshots = build_report()
    if not verify_fingerprint(report, "report_fingerprint"):
        raise ValueError("generated report fingerprint is invalid")
    for snapshot in snapshots.values():
        if not verify_fingerprint(snapshot, "snapshot_fingerprint"):
            raise ValueError(f"invalid snapshot fingerprint: {snapshot.get('case_id')}")
    for case in report["cases"]:
        if not verify_fingerprint(case["candidate"], "candidate_fingerprint"):
            raise ValueError(f"invalid candidate fingerprint: {case.get('case_id')}")
        if not verify_fingerprint(case["result"], "artifact_fingerprint"):
            raise ValueError(f"invalid result fingerprint: {case.get('case_id')}")
    for relative_path, expected in generated_contents(report, snapshots).items():
        path = output_dir / relative_path
        if not path.exists():
            raise ValueError(f"missing generated artifact: {relative_path}")
        if path.read_text(encoding="utf-8") != expected:
            raise ValueError(f"generated artifact is stale: {relative_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed artifacts against current inputs without rewriting them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify(args.output_dir) if args.check else generate(args.output_dir)
    print(
        json.dumps(
            {
                "status": "verified" if args.check else "generated",
                "output_dir": str(args.output_dir),
                "report_fingerprint": report["report_fingerprint"],
                **report["summary"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
