#!/usr/bin/env python3

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "generated" / "raw" / "dallas-electrician-import-sample-v1"
DEFAULT_OUTPUT_DIR = ROOT / "generated" / "normalized" / "dallas-electrician-import-sample-v1"

PERMIT_TYPE_MAP = {
    "residential electrical remodel": "electrical_remodel",
    "electrical remodel": "electrical_remodel",
    "residential electrical repair": "electrical_repair",
    "electrical repair": "electrical_repair",
    "electrical service upgrade": "electrical_service_upgrade",
    "residential service upgrade": "electrical_service_upgrade",
    "new electrical install": "electrical_new",
    "residential new electrical": "electrical_new",
}

STATUS_MAP = {
    "filed": "filed",
    "issued": "issued",
    "active": "active",
    "finaled": "finaled",
    "expired": "expired",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}

INSPECTION_TYPE_MAP = {
    "rough-in": "rough_in",
    "rough in": "rough_in",
    "service release": "service_release",
    "final": "final",
    "temporary service": "temporary_service",
    "correction follow-up": "correction_followup",
    "correction follow up": "correction_followup",
}

RESULT_MAP = {
    "pass": "pass",
    "approved": "pass",
    "fail": "fail",
    "failed": "fail",
    "partial": "partial",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "not ready": "not_ready",
}

SUFFIX_MAP = {
    " STREET": " ST",
    " AVENUE": " AVE",
    " ROAD": " RD",
    " DRIVE": " DR",
    " BOULEVARD": " BLVD",
    " PLACE": " PL",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Normalize Dallas permit, inspection, and contractor extracts into the MVP row contract."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_csv(path: Path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def slugify(value: str):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_whitespace(value: str):
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_address(street_address: str, city: str, state: str, zip_code: str):
    value = " ".join(
        part for part in [street_address, city, state, zip_code] if normalize_whitespace(part)
    ).upper()
    value = normalize_whitespace(value)
    for raw_suffix, normalized_suffix in SUFFIX_MAP.items():
        if raw_suffix in value:
            value = value.replace(raw_suffix, normalized_suffix)
    return value


def normalize_date(value: str):
    value = normalize_whitespace(value)
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def normalize_permit_type(value: str):
    normalized = PERMIT_TYPE_MAP.get(normalize_whitespace(value).lower())
    return normalized or "unknown"


def normalize_status(value: str):
    normalized = STATUS_MAP.get(normalize_whitespace(value).lower())
    return normalized or "unknown"


def normalize_inspection_type(value: str):
    normalized = INSPECTION_TYPE_MAP.get(normalize_whitespace(value).lower())
    return normalized or "unknown"


def normalize_result(value: str):
    normalized = RESULT_MAP.get(normalize_whitespace(value).lower())
    return normalized or "unknown"


def infer_failure_reason(notes: str):
    lowered = normalize_whitespace(notes).lower()
    if not lowered:
        return None
    if "scope" in lowered or "permit" in lowered:
        return "missing_permit_or_scope_mismatch"
    if "ground" in lowered or "bond" in lowered:
        return "grounding_or_bonding_issue"
    if "panel" in lowered or "disconnect" in lowered or "service" in lowered:
        return "panel_or_service_issue"
    if "label" in lowered or "document" in lowered:
        return "labeling_or_documentation_issue"
    if "access" in lowered or "schedule" in lowered:
        return "access_or_scheduling_issue"
    if "wire" in lowered or "device" in lowered or "gfci" in lowered or "afci" in lowered:
        return "wiring_or_device_issue"
    if "trim" in lowered or "incomplete" in lowered or "missing" in lowered:
        return "incomplete_work"
    return "other"


def is_truthy(value: str):
    return normalize_whitespace(value).lower() in {"1", "true", "yes", "y"}


def build_property_records(permit_rows):
    properties = []
    property_id_by_key = {}

    for row in permit_rows:
        street_address = normalize_whitespace(row["address"])
        city = normalize_whitespace(row.get("city", "Dallas")) or "Dallas"
        state = normalize_whitespace(row.get("state", "TX")) or "TX"
        zip_code = normalize_whitespace(row.get("zip_code", ""))
        property_key = normalize_address(street_address, city, state, zip_code)
        if property_key in property_id_by_key:
            continue
        property_id = f"property:{slugify(property_key)}"
        property_id_by_key[property_key] = property_id
        properties.append(
            {
                "property_id": property_id,
                "normalized_address": property_key,
                "street_address": street_address,
                "city": city,
                "state": state,
                "zip_code": zip_code or None,
                "property_type": normalize_whitespace(row.get("property_type", "")) or None,
                "address_confidence": "high",
            }
        )
    return properties, property_id_by_key


def build_contractor_records(contractor_rows):
    contractors = []
    contractor_id_by_name = {}
    source_records = []

    for row in contractor_rows:
        license_type = normalize_whitespace(row.get("license_type", "")).lower()
        if "electrical" not in license_type:
            continue
        name = normalize_whitespace(row["name"])
        contractor_id = f"contractor:dallas:{slugify(name)}"
        contractor_id_by_name[name.lower()] = contractor_id
        source_record_id = f"source:contractor:{slugify(row['registration_id'])}"
        contractors.append(
            {
                "contractor_id": contractor_id,
                "source_record_id": source_record_id,
                "name": name,
                "license_type": normalize_whitespace(row.get("license_type", "")) or None,
                "registration_status": normalize_whitespace(row.get("registration_status", "")) or None,
                "city": normalize_whitespace(row.get("city", "")) or None,
                "state": normalize_whitespace(row.get("state", "")) or None,
            }
        )
        source_records.append(
            {
                "source_record_id": source_record_id,
                "source_system": "contractor_csv_extract",
                "source_path_or_url": "contractors.csv",
                "record_type": "contractor",
                "captured_at": "2026-04-26T00:00:00Z",
                "raw_payload": row,
            }
        )

    return contractors, contractor_id_by_name, source_records


def filter_permit_rows(permit_rows):
    kept = []
    for row in permit_rows:
        city = normalize_whitespace(row.get("city", ""))
        if city.lower() != "dallas":
            continue
        if normalize_whitespace(row.get("trade", "")).lower() != "electrical":
            continue
        if normalize_whitespace(row.get("work_class", "")).lower() != "residential":
            continue
        kept.append(row)
    return kept


def build_permit_records(permit_rows, property_id_by_key, contractor_id_by_name):
    permits = []
    source_records = []

    for row in permit_rows:
        permit_number = normalize_whitespace(row["permit_number"])
        property_key = normalize_address(
            normalize_whitespace(row["address"]),
            normalize_whitespace(row.get("city", "Dallas")) or "Dallas",
            normalize_whitespace(row.get("state", "TX")) or "TX",
            normalize_whitespace(row.get("zip_code", "")),
        )
        permit_id = f"permit:dallas:{slugify(permit_number)}"
        source_record_id = f"source:permit:{slugify(permit_number)}"
        contractor_name = normalize_whitespace(row.get("contractor_name", ""))
        permits.append(
            {
                "permit_id": permit_id,
                "source_record_id": source_record_id,
                "source_system": "permit_csv_extract",
                "source_permit_number": permit_number,
                "property_id": property_id_by_key[property_key],
                "permit_type_raw": normalize_whitespace(row.get("permit_type", "")),
                "permit_type_normalized": normalize_permit_type(row.get("permit_type", "")),
                "work_class": "residential",
                "trade": "electrical",
                "status_raw": normalize_whitespace(row.get("status", "")),
                "status_normalized": normalize_status(row.get("status", "")),
                "file_date": normalize_date(row.get("file_date", "")),
                "issue_date": normalize_date(row.get("issue_date", "")),
                "final_date": normalize_date(row.get("final_date", "")),
                "work_description": normalize_whitespace(row.get("work_description", "")) or None,
                "declared_valuation": int(row["declared_valuation"]) if row.get("declared_valuation") else None,
                "contractor_id": contractor_id_by_name.get(contractor_name.lower()),
                "is_residential_inferred": False,
                "source_url": normalize_whitespace(row.get("source_url", "")) or None,
            }
        )
        source_records.append(
            {
                "source_record_id": source_record_id,
                "source_system": "permit_csv_extract",
                "source_path_or_url": "permits.csv",
                "record_type": "permit",
                "captured_at": "2026-04-26T00:00:00Z",
                "raw_payload": row,
            }
        )

    return permits, source_records


def build_inspection_records(inspection_rows, permit_ids_by_number):
    inspections = []
    source_records = []

    for row in inspection_rows:
        permit_number = normalize_whitespace(row["permit_number"])
        permit_id = permit_ids_by_number.get(permit_number)
        if not permit_id:
            continue
        inspection_type_normalized = normalize_inspection_type(row.get("inspection_type", ""))
        inspection_date = normalize_date(row.get("inspection_date", ""))
        result_normalized = normalize_result(row.get("result", ""))
        inspection_id = (
            f"inspection:dallas:{slugify(permit_number)}:{inspection_date}:{inspection_type_normalized}"
        )
        source_record_id = f"source:inspection:{slugify(permit_number)}:{slugify(row['inspection_date'])}:{inspection_type_normalized}"
        notes_raw = normalize_whitespace(row.get("notes", "")) or None
        inspection = {
            "inspection_id": inspection_id,
            "source_record_id": source_record_id,
            "permit_id": permit_id,
            "inspection_type_raw": normalize_whitespace(row.get("inspection_type", "")),
            "inspection_type_normalized": inspection_type_normalized,
            "inspection_date": inspection_date,
            "result_raw": normalize_whitespace(row.get("result", "")),
            "result_normalized": result_normalized,
            "notes_raw": notes_raw,
            "inspector_name": normalize_whitespace(row.get("inspector_name", "")) or None,
            "reinspection_flag": is_truthy(row.get("reinspection_flag", "")),
            "source_url": normalize_whitespace(row.get("source_url", "")) or None,
        }
        if result_normalized in {"fail", "partial", "not_ready"}:
            inspection["failure_reason_normalized"] = infer_failure_reason(notes_raw or "")
        inspections.append(inspection)
        source_records.append(
            {
                "source_record_id": source_record_id,
                "source_system": "inspection_csv_extract",
                "source_path_or_url": "inspections.csv",
                "record_type": "inspection",
                "captured_at": "2026-04-26T00:00:00Z",
                "raw_payload": row,
            }
        )

    inspections.sort(key=lambda row: (row["permit_id"], row["inspection_date"], row["inspection_id"]))
    return inspections, source_records


def build_project(output_dir: Path, permit_count: int, inspection_count: int):
    dataset_name = output_dir.name.replace("-", " ").title()
    return {
        "project_id": f"project:{output_dir.name}",
        "name": dataset_name,
        "locality": "Dallas, Texas",
        "trade": "electricians",
        "workflow": "residential electrical permits and inspections",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_summary": (
            f"Imported Dallas residential electrical extract with {permit_count} permits "
            f"and {inspection_count} inspections normalized from CSV fixtures."
        ),
    }


def main():
    args = parse_args()
    permit_rows = filter_permit_rows(load_csv(args.input_dir / "permits.csv"))
    inspection_rows = load_csv(args.input_dir / "inspections.csv")
    contractor_rows = load_csv(args.input_dir / "contractors.csv")

    properties, property_id_by_key = build_property_records(permit_rows)
    contractors, contractor_id_by_name, contractor_sources = build_contractor_records(contractor_rows)
    permits, permit_sources = build_permit_records(
        permit_rows, property_id_by_key, contractor_id_by_name
    )
    permit_ids_by_number = {row["source_permit_number"]: row["permit_id"] for row in permits}
    inspections, inspection_sources = build_inspection_records(inspection_rows, permit_ids_by_number)
    source_records = contractor_sources + permit_sources + inspection_sources
    project = build_project(args.output_dir, len(permits), len(inspections))

    write_json(args.output_dir / "projects.json", project)
    write_jsonl(args.output_dir / "properties.jsonl", properties)
    write_jsonl(args.output_dir / "permits.jsonl", permits)
    write_jsonl(args.output_dir / "inspections.jsonl", inspections)
    write_jsonl(args.output_dir / "contractors.jsonl", contractors)
    write_jsonl(args.output_dir / "source_records.jsonl", source_records)


if __name__ == "__main__":
    main()
