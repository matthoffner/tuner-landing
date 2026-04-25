# Schema

This document defines the minimal ingestion schema for the Dallas electricians MVP.

It is the contract for the first usable local dataset, not a general-purpose municipal data model.

## Scope

The schema only needs to support:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`

The first version should be strict about scope. Ignore commercial-only, non-electrical, and non-Dallas records unless they are explicitly needed as reference context.

## Dataset Goal

The normalized dataset should be sufficient to answer:

- what usually happens next on a residential electrical permit
- which inspection paths tend to fail
- what issues likely caused a failure
- what next actions may improve approval odds

## Canonical Output Files

The first ingestion pass should materialize these files under a future generated dataset directory:

- `projects.json`
- `properties.jsonl`
- `permits.jsonl`
- `inspections.jsonl`
- `contractors.jsonl`
- `rule_documents.jsonl`
- `source_records.jsonl`

JSONL is preferred for record tables because it is append-friendly and easy to inspect locally.

## Entity Rules

### `Project`

One project represents one local `automoat` workspace dataset.

Required fields:

- `project_id`: stable local identifier
- `name`: human-readable project name
- `locality`: must be `Dallas, Texas`
- `trade`: must be `electricians`
- `workflow`: must be `residential electrical permits and inspections`
- `created_at`: ISO-8601 timestamp
- `source_summary`: short text summary of included sources

### `Property`

One property record is the normalized location anchor used to join permits and inspections.

Required fields:

- `property_id`: stable local identifier
- `normalized_address`: uppercase comparable address string
- `street_address`: best available street line
- `city`: usually `Dallas`
- `state`: `TX`

Optional fields:

- `zip_code`
- `parcel_id`
- `property_type`
- `address_confidence`: `high`, `medium`, or `low`

### `Permit`

One permit record is the primary work unit for the MVP.

Required fields:

- `permit_id`: stable local identifier
- `source_record_id`: pointer to the raw source record
- `source_system`: source label such as `permit_report` or `online_record`
- `source_permit_number`: source-visible permit number
- `property_id`: foreign key to `Property`
- `permit_type_raw`: unmodified source label
- `permit_type_normalized`: controlled vocabulary value
- `work_class`: `residential` or `unknown`
- `trade`: must normalize to `electrical`
- `status_raw`: unmodified source status
- `status_normalized`: controlled vocabulary value
- `file_date`: ISO date when available

Optional fields:

- `issue_date`
- `final_date`
- `expiration_date`
- `work_description`
- `declared_valuation`
- `contractor_id`
- `is_residential_inferred`: boolean
- `source_url`

### `Inspection`

One inspection record is an inspection event attached to a permit.

Required fields:

- `inspection_id`: stable local identifier
- `source_record_id`: pointer to the raw source record
- `permit_id`: foreign key to `Permit`
- `inspection_type_raw`: unmodified source label
- `inspection_type_normalized`: controlled vocabulary value
- `inspection_date`: ISO date when available
- `result_raw`: unmodified source result
- `result_normalized`: controlled vocabulary value

Optional fields:

- `notes_raw`
- `failure_reason_normalized`
- `inspector_name`
- `reinspection_flag`: boolean
- `source_url`

### `Contractor`

This table is optional for ingestion completeness but should exist when contractor data is available.

Required fields:

- `contractor_id`: stable local identifier
- `name`

Optional fields:

- `license_type`
- `registration_status`
- `city`
- `state`
- `source_record_id`

### `RuleDocument`

These records provide evaluation and recommendation context, not transactional history.

Required fields:

- `document_id`: stable local identifier
- `title`
- `document_type`
- `source_url`
- `text_content`

Optional fields:

- `effective_date`
- `trade`: normally `electrical`
- `jurisdiction`: normally `Dallas`

### `SourceRecord`

Every normalized row should trace back to a captured source record.

Required fields:

- `source_record_id`: stable local identifier
- `source_system`
- `source_path_or_url`
- `record_type`: such as `permit`, `inspection`, `contractor`, or `rule_document`
- `captured_at`: ISO-8601 timestamp
- `raw_payload`: original raw row or extracted object

## Controlled Vocabularies

### `permit_type_normalized`

Use a small internal vocabulary first:

- `electrical_new`
- `electrical_remodel`
- `electrical_repair`
- `electrical_service_upgrade`
- `electrical_misc`
- `unknown`

### `status_normalized`

- `filed`
- `issued`
- `active`
- `finaled`
- `expired`
- `cancelled`
- `unknown`

### `inspection_type_normalized`

- `rough_in`
- `service_release`
- `final`
- `temporary_service`
- `correction_followup`
- `other`
- `unknown`

### `result_normalized`

- `pass`
- `fail`
- `partial`
- `cancelled`
- `not_ready`
- `unknown`

### `failure_reason_normalized`

Do not try to encode the entire codebook yet. Start with a short practical set:

- `missing_permit_or_scope_mismatch`
- `incomplete_work`
- `panel_or_service_issue`
- `wiring_or_device_issue`
- `grounding_or_bonding_issue`
- `labeling_or_documentation_issue`
- `access_or_scheduling_issue`
- `other`
- `unknown`

## Inclusion Rules

A record belongs in the MVP working set if all of the following are true:

- it is tied to Dallas or a Dallas address
- it is electrical or can be confidently normalized to electrical work
- it is residential or reasonably inferable as residential

If residential status is unclear:

- keep the record only when the source strongly suggests residential usage
- set `work_class` to `unknown`
- set `is_residential_inferred` to `true`

## Key Normalization Rules

### Addresses

- uppercase all address text
- collapse repeated whitespace
- standardize common suffixes where safe
- preserve apartment or unit information if present
- keep both `street_address` and `normalized_address` when available

### Dates

- store record dates as `YYYY-MM-DD`
- store capture times as ISO-8601 timestamps
- leave missing dates as null
- do not invent dates from sort order

### Record Identity

- prefer source-native ids when stable
- otherwise derive ids from source system plus permit number plus inspection date or row hash
- ids must be stable across repeated ingests of unchanged source rows

### Raw Preservation

- keep original source labels in `*_raw` fields
- never overwrite the source text with normalized values
- preserve raw notes when available, even if noisy

## Join Expectations

The required join path for the MVP is:

`Property <- Permit <- Inspection`

Additional joins:

- `Permit -> Contractor`
- `Inspection -> SourceRecord`
- `Permit -> SourceRecord`
- `RuleDocument` joins only through retrieval or citation, not direct foreign keys

## Minimum Acceptable Row Shape

The ingestion pass is acceptable if it can produce:

- permit rows with stable ids, normalized type, normalized status, and a property join
- inspection rows with stable ids, permit join, normalized inspection type, and normalized result
- raw source traceability for every normalized permit and inspection row

Contractor and rules data can remain partial in the first pass.

## Example Records

### `Permit`

```json
{
  "permit_id": "permit:dallas:2026-0001234",
  "source_record_id": "source:permit_report:2026:row-1842",
  "source_system": "permit_report",
  "source_permit_number": "2026-0001234",
  "property_id": "property:214-main-st-dallas-tx",
  "permit_type_raw": "Electrical Residential Remodel",
  "permit_type_normalized": "electrical_remodel",
  "work_class": "residential",
  "trade": "electrical",
  "status_raw": "Issued",
  "status_normalized": "issued",
  "file_date": "2026-02-11",
  "issue_date": "2026-02-12",
  "work_description": "Kitchen rewire and panel replacement"
}
```

### `Inspection`

```json
{
  "inspection_id": "inspection:dallas:2026-0001234:2026-02-18:final",
  "source_record_id": "source:online_record:2026:insp-55219",
  "permit_id": "permit:dallas:2026-0001234",
  "inspection_type_raw": "Electrical Final",
  "inspection_type_normalized": "final",
  "inspection_date": "2026-02-18",
  "result_raw": "Failed",
  "result_normalized": "fail",
  "notes_raw": "Panel labeling incomplete and bonding correction required.",
  "failure_reason_normalized": "grounding_or_bonding_issue"
}
```

## Non-Goals

This schema does not need to solve:

- every Dallas permitting edge case
- all trades
- commercial workflow modeling
- generalized municipal ontology design
- full document chunking or embeddings

Those can come later if this slice proves useful.

## Done Definition

The schema phase is done when a future ingestion scaffold can implement this document without product re-interpretation:

- required entities are fixed
- required fields are explicit
- controlled vocabularies are small and usable
- joins and inclusion rules are clear
- example records are concrete enough to test against
