# Dallas Import Pipeline Summary

- Dataset: `dallas-electrician-import-sample-v2`
- Contract: PASS (`13/13` checks)
- Queue items: `14`
- Operator corrections: `14/14`
- Accepted patterns: `6`
- Import artifacts: `14` permits, `40` inspections, `51` eval tasks, `20` reviewed labels
- Execution readiness: READY
- Correction gate: PASSED
- Next gap: All current latest-import result states, failure reasons, pattern slices, and expected next-action groups have repeated support; keep the action queue and coverage report current as real Dallas import records widen.
- Next raw import files: `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`
- Next raw import row counts: `permits.csv`=15, `inspections.csv`=41, `contractors.csv`=6, `rule_documents.csv`=3
- Next raw import fingerprints: see Follow-Up
- Next raw import append rows: `permits.csv` row 17, `inspections.csv` row 43, `contractors.csv` row 8, `rule_documents.csv` row 5
- Next raw import last data rows: see Follow-Up
- Next raw import identity key checks: see Follow-Up
- Next raw import value profiles: see Follow-Up
- Next raw import date profiles: see Follow-Up
- Next raw import relationship checks: see Follow-Up
- Next raw import scope counts: see Follow-Up
- Next raw importable examples: see Follow-Up
- Next raw import exclusion examples: see Follow-Up
- Next raw import headers: see Follow-Up
- Next raw import required fields: see Follow-Up
- Next raw import optional fields: see Follow-Up
- Next raw import required-field gaps: see Follow-Up

## Execution Readiness

- Status: `ready`
- Ready for next import records: `true`
- Passing gates: `contract_passed`, `operator_corrections_complete`, `correction_gate_passed`, `coverage_has_no_thin_groups`, `accepted_operator_patterns_present`
- Blockers: none
- Next step: Current Dallas permit-data MVP artifacts are executable; after adding or importing new Dallas rows, rerun the pipeline and inspect `workflow.accepted_patterns` plus `coverage.thin_groups` for new gaps.
- Run command: `python3 scripts/run_dallas_import_pipeline.py`
- Require-ready command: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Summary-only require-ready command: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready`
- Summary-only require-ready JSON command: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`

## Import Artifact Snapshot

- Normalized rows: `14` properties, `14` permits, `40` inspections, `5` contractors
- Source support: `62` source records, `3` rule documents
- Eval rows: `51` tasks, `20` reviewed labels, `46` dev tasks, `5` test tasks
- Task families: `26` next-outcome, `6` failure-reason, `14` next-action, `5` pattern-extraction
- Result vocabulary: `cancelled`, `fail`, `not_ready`, `partial`, `pass`, `unknown`

## Accepted Operator Pattern Snapshot

These are the reusable accepted correction patterns currently embedded in the Dallas action queue.

### operator-pattern:accepted:0001

- Queue items: `3`
- Action IDs: `correct_wiring_or_devices`, `schedule_reinspection`
- Actions: `Correct wiring or devices`, `Schedule reinspection`
- Trigger results: `{"fail": 2, "partial": 1}`
- Failure reasons: `{"wiring_or_device_issue": 3}`
- Inspection types: `{"final": 2, "rough_in": 1}`
- Follow-up results: `{"pass": 3}`
- Example permits: `ELP-2026-0209`, `ELR-2026-0201`, `ELR-2026-0207`
- Queue IDs: `workflow-item:dallas:next-action:0007`, `workflow-item:dallas:next-action:0008`, `workflow-item:dallas:next-action:0009`

### operator-pattern:accepted:0002

- Queue items: `3`
- Action IDs: `ensure_site_access`, `schedule_reinspection`
- Actions: `Ensure site access`, `Schedule reinspection`
- Trigger results: `{"not_ready": 3}`
- Failure reasons: `{"access_or_scheduling_issue": 3}`
- Inspection types: `{"final": 1, "service_release": 2}`
- Follow-up results: `{"pass": 3}`
- Example permits: `ELM-2026-0211`, `ELS-2026-0202`, `ELS-2026-0210`
- Queue IDs: `workflow-item:dallas:next-action:0001`, `workflow-item:dallas:next-action:0010`, `workflow-item:dallas:next-action:0011`

### operator-pattern:accepted:0003

- Queue items: `2`
- Action IDs: `complete_remaining_work`, `schedule_reinspection`
- Actions: `Complete remaining work`, `Schedule reinspection`
- Trigger results: `{"partial": 2}`
- Failure reasons: `{"incomplete_work": 2}`
- Inspection types: `{"rough_in": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELP-2026-0203`, `ELZ-2026-0215`
- Queue IDs: `workflow-item:dallas:next-action:0006`, `workflow-item:dallas:next-action:0014`

### operator-pattern:accepted:0004

- Queue items: `2`
- Action IDs: `correct_grounding_or_bonding`, `add_labels_or_documentation`
- Actions: `Correct grounding or bonding`, `Add missing labels or documentation`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"rough_in": 2}`
- Follow-up results: `{"partial": 2}`
- Example permits: `ELN-2026-0204`, `ELN-2026-0208`
- Queue IDs: `workflow-item:dallas:next-action:0002`, `workflow-item:dallas:next-action:0004`

### operator-pattern:accepted:0005

- Queue items: `2`
- Action IDs: `correct_grounding_or_bonding`, `add_labels_or_documentation`, `schedule_reinspection`
- Actions: `Correct grounding or bonding`, `Add missing labels or documentation`, `Schedule reinspection`
- Trigger results: `{"partial": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"correction_followup": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELN-2026-0204`, `ELN-2026-0208`
- Queue IDs: `workflow-item:dallas:next-action:0003`, `workflow-item:dallas:next-action:0005`

### operator-pattern:accepted:0006

- Queue items: `2`
- Action IDs: `correct_panel_or_service`, `add_labels_or_documentation`, `schedule_reinspection`
- Actions: `Correct panel or service issue`, `Add missing labels or documentation`, `Schedule reinspection`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"panel_or_service_issue": 2}`
- Inspection types: `{"service_release": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELS-2026-0213`, `ELS-2026-0214`
- Queue IDs: `workflow-item:dallas:next-action:0012`, `workflow-item:dallas:next-action:0013`

## Coverage Snapshot

- Coverage dataset: `dallas-electrician-import-sample-v2`
- Repeated support threshold: `2` permits
- Repeated counts: `6` result states, `5` failure reasons, `5` pattern slices, `6` next-action groups
- Thin counts: `0` result states, `0` failure reasons, `0` pattern slices, `0` next-action groups
- Thin groups: none
- Coverage next step: All current latest-import edge-case sections have repeated support; keep this report current as imported Dallas data widens.

## Follow-Up

- Pattern review: `python3 scripts/record_operator_correction.py --list-patterns --format text`
- Completion gate: `python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text`
- After raw CSV edits: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Raw CSV readiness check: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`
- Raw CSV files: `generated/raw/dallas-electrician-import-sample-v2/permits.csv`, `generated/raw/dallas-electrician-import-sample-v2/inspections.csv`, `generated/raw/dallas-electrician-import-sample-v2/contractors.csv`, `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`
- Raw CSV row counts: `permits.csv`=15, `inspections.csv`=41, `contractors.csv`=6, `rule_documents.csv`=3
- Raw CSV fingerprints:
- `permits.csv` fingerprint: `sha256` `7863d3ac9b55dd4f2a604ea792b4ba5bb9c190bede768b0befe7612f2a24f1c1` (4670 bytes)
- `inspections.csv` fingerprint: `sha256` `292b83542ff6643692214f86e6f53f0c1070587c5a422e86352243f4750b6797` (8290 bytes)
- `contractors.csv` fingerprint: `sha256` `5ecf6f5e062bb09c3920616b1c7ed56e4a2789d3250da10a670b7eb80251f841` (498 bytes)
- `rule_documents.csv` fingerprint: `sha256` `f0d1cbff37f9607f3b319e30d3323e132f70fc3770824ffea6a683ac439fde2f` (932 bytes)
- Raw CSV next append rows: `permits.csv` row 17, `inspections.csv` row 43, `contractors.csv` row 8, `rule_documents.csv` row 5
- Raw CSV last data rows:
- `permits.csv` last data row: `{"csv_row_number": 16, "row": {"permit_number": "PLM-2026-0206", "address": "410 W Jefferson Blvd", "city": "Dallas", "trade": "plumbing", "work_class": "residential"}}`
- `inspections.csv` last data row: `{"csv_row_number": 42, "row": {"permit_number": "PLM-2026-0206", "inspection_date": "2026-04-11", "inspection_type": "Final", "result": "Pass"}}`
- `contractors.csv` last data row: `{"csv_row_number": 7, "row": {"registration_id": "REG-5206", "name": "Oak Lawn Plumbing", "license_type": "plumbing_contractor"}}`
- `rule_documents.csv` last data row: `{"csv_row_number": 4, "row": {"title": "Dallas reinspection access note", "document_type": "faq", "effective_date": "2025-01-01"}}`
- Raw CSV identity key checks:
- `permits.csv` identity keys: fields `permit_number`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `inspections.csv` identity keys: fields `permit_number`, `inspection_date`, `inspection_type`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `contractors.csv` identity keys: fields `registration_id`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- `rule_documents.csv` identity keys: fields `title`, duplicates `0`, rows with duplicate identity `0`, missing identity rows `0`, examples `[]`
- Raw CSV value profiles:
- `permits.csv` value profiles: `{"rows_checked": 15, "fields": {"city": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "Dallas", "count": 15}]}, "trade": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "electrical", "count": 14}, {"value": "plumbing", "count": 1}]}, "work_class": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "residential", "count": 15}]}, "permit_type": {"distinct_value_count": 5, "blank_count": 0, "top_values": [{"value": "Residential electrical remodel", "count": 5}, {"value": "Electrical service upgrade", "count": 4}, {"value": "Electrical repair", "count": 3}, {"value": "New electrical install", "count": 2}, {"value": "Residential plumbing repair", "count": 1}]}, "status": {"distinct_value_count": 3, "blank_count": 0, "top_values": [{"value": "Finaled", "count": 10}, {"value": "Active", "count": 4}, {"value": "Issued", "count": 1}]}, "property_type": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "single_family", "count": 13}, {"value": "duplex", "count": 2}]}, "zip_code": {"distinct_value_count": 5, "blank_count": 0, "top_values": [{"value": "75228", "count": 4}, {"value": "75208", "count": 3}, {"value": "75212", "count": 3}, {"value": "75216", "count": 3}, {"value": "75214", "count": 2}]}}}`
- `inspections.csv` value profiles: `{"rows_checked": 41, "fields": {"inspection_type": {"distinct_value_count": 4, "blank_count": 0, "top_values": [{"value": "Correction follow-up", "count": 14}, {"value": "Rough-in", "count": 13}, {"value": "Final", "count": 10}, {"value": "Service release", "count": 4}]}, "result": {"distinct_value_count": 6, "blank_count": 0, "top_values": [{"value": "Pass", "count": 23}, {"value": "Fail", "count": 6}, {"value": "Partial", "count": 5}, {"value": "Not Ready", "count": 3}, {"value": "Cancelled", "count": 2}, {"value": "Pending", "count": 2}]}, "reinspection_flag": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "false", "count": 23}, {"value": "true", "count": 18}]}}}`
- `contractors.csv` value profiles: `{"rows_checked": 6, "fields": {"license_type": {"distinct_value_count": 2, "blank_count": 0, "top_values": [{"value": "electrical_contractor", "count": 5}, {"value": "plumbing_contractor", "count": 1}]}, "registration_status": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "registered", "count": 6}]}, "city": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "Dallas", "count": 6}]}, "state": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "TX", "count": 6}]}}}`
- `rule_documents.csv` value profiles: `{"rows_checked": 3, "fields": {"document_type": {"distinct_value_count": 3, "blank_count": 0, "top_values": [{"value": "faq", "count": 1}, {"value": "guidance_page", "count": 1}, {"value": "inspection_checklist", "count": 1}]}, "effective_date": {"distinct_value_count": 1, "blank_count": 0, "top_values": [{"value": "2025-01-01", "count": 3}]}}}`
- Raw CSV date profiles:
- `permits.csv` date profiles: `{"rows_checked": 15, "fields": {"file_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 15, "invalid_date_count": 0, "earliest_date": "2026-03-12", "earliest_csv_row_number": 5, "latest_date": "2026-04-18", "latest_csv_row_number": 15, "invalid_examples": []}, "issue_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 15, "invalid_date_count": 0, "earliest_date": "2026-03-13", "earliest_csv_row_number": 5, "latest_date": "2026-04-19", "latest_csv_row_number": 15, "invalid_examples": []}, "final_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 5, "valid_date_count": 10, "invalid_date_count": 0, "earliest_date": "2026-03-22", "earliest_csv_row_number": 5, "latest_date": "2026-04-27", "latest_csv_row_number": 15, "invalid_examples": []}}}`
- `inspections.csv` date profiles: `{"rows_checked": 41, "fields": {"inspection_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 41, "invalid_date_count": 0, "earliest_date": "2026-03-17", "earliest_csv_row_number": 11, "latest_date": "2026-04-27", "latest_csv_row_number": 41, "invalid_examples": []}}}`
- `contractors.csv` date profiles: `{"rows_checked": 6, "fields": {}}`
- `rule_documents.csv` date profiles: `{"rows_checked": 3, "fields": {"effective_date": {"field_present": true, "date_format": "YYYY-MM-DD", "blank_count": 0, "valid_date_count": 3, "invalid_date_count": 0, "earliest_date": "2025-01-01", "earliest_csv_row_number": 2, "latest_date": "2025-01-01", "latest_csv_row_number": 2, "invalid_examples": []}}}`
- Raw CSV relationship checks:
- `inspections_to_permits` relationship: `40/41` matched importable target rows, excluded target rows `1`, unresolved rows `0`, unmatched examples `[]`, excluded target examples `[{"csv_row_number": 42, "row": {"permit_number": "PLM-2026-0206", "inspection_date": "2026-04-11", "inspection_type": "Final", "result": "Pass"}}]`
- `permits_to_contractors` relationship: `14/15` matched importable target rows, excluded target rows `1`, unresolved rows `0`, unmatched examples `[]`, excluded target examples `[{"csv_row_number": 16, "row": {"permit_number": "PLM-2026-0206", "address": "410 W Jefferson Blvd", "city": "Dallas", "trade": "plumbing", "work_class": "residential"}}]`
- Raw CSV import scope counts:
- `permits.csv` import scope: `14/15` importable, excluded: `1`, reasons: `{"excluded_by_city": 0, "excluded_by_trade": 1, "excluded_by_work_class": 0}`
- `inspections.csv` import scope: `40/41` importable, excluded: `1`, reasons: `{"excluded_by_unimported_permit": 1}`
- `contractors.csv` import scope: `5/6` importable, excluded: `1`, reasons: `{"excluded_by_license_type": 1}`
- `rule_documents.csv` import scope: `3/3` importable, excluded: `0`, reasons: `{"excluded_by_missing_title": 0}`
- Raw CSV importable examples:
- `permits.csv` importable examples: `[{"csv_row_number": 2, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELR-2026-0201", "address": "412 N Winnetka Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 3, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELR-2026-0207", "address": "527 N Clinton Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 4, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELS-2026-0202", "address": "9915 Ferguson Rd", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 5, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELP-2026-0203", "address": "2234 S Marsalis Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}, {"csv_row_number": 6, "reason": "importable_dallas_residential_electrical_permit", "row": {"permit_number": "ELP-2026-0209", "address": "2615 S Ewing Ave", "city": "Dallas", "trade": "electrical", "work_class": "residential"}}]`
- `inspections.csv` importable examples: `[{"csv_row_number": 2, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-04", "inspection_type": "Rough-in", "result": "Pass"}}, {"csv_row_number": 3, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-09", "inspection_type": "Final", "result": "Fail"}}, {"csv_row_number": 4, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0201", "inspection_date": "2026-04-12", "inspection_type": "Correction follow-up", "result": "Pass"}}, {"csv_row_number": 5, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0207", "inspection_date": "2026-04-08", "inspection_type": "Rough-in", "result": "Pass"}}, {"csv_row_number": 6, "reason": "linked_to_importable_permit", "row": {"permit_number": "ELR-2026-0207", "inspection_date": "2026-04-13", "inspection_type": "Final", "result": "Fail"}}]`
- `contractors.csv` importable examples: `[{"csv_row_number": 2, "reason": "electrical_license_type", "row": {"registration_id": "REG-5101", "name": "Bishop Arts Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 3, "reason": "electrical_license_type", "row": {"registration_id": "REG-5102", "name": "Casa View Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 4, "reason": "electrical_license_type", "row": {"registration_id": "REG-5103", "name": "Cedars South Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 5, "reason": "electrical_license_type", "row": {"registration_id": "REG-5104", "name": "White Rock Electric", "license_type": "electrical_contractor"}}, {"csv_row_number": 6, "reason": "electrical_license_type", "row": {"registration_id": "REG-5105", "name": "Trinity Grove Electric", "license_type": "electrical_contractor"}}]`
- `rule_documents.csv` importable examples: `[{"csv_row_number": 2, "reason": "has_title", "row": {"title": "Dallas residential electrical final checklist", "document_type": "inspection_checklist", "effective_date": "2025-01-01"}}, {"csv_row_number": 3, "reason": "has_title", "row": {"title": "Dallas service upgrade release guidance", "document_type": "guidance_page", "effective_date": "2025-01-01"}}, {"csv_row_number": 4, "reason": "has_title", "row": {"title": "Dallas reinspection access note", "document_type": "faq", "effective_date": "2025-01-01"}}]`
- Raw CSV exclusion examples:
- `permits.csv` exclusion examples: `[{"csv_row_number": 16, "reason": "excluded_by_trade", "row": {"permit_number": "PLM-2026-0206", "address": "410 W Jefferson Blvd", "city": "Dallas", "trade": "plumbing", "work_class": "residential"}}]`
- `inspections.csv` exclusion examples: `[{"csv_row_number": 42, "reason": "excluded_by_unimported_permit", "row": {"permit_number": "PLM-2026-0206", "inspection_date": "2026-04-11", "inspection_type": "Final", "result": "Pass"}}]`
- `contractors.csv` exclusion examples: `[{"csv_row_number": 7, "reason": "excluded_by_license_type", "row": {"registration_id": "REG-5206", "name": "Oak Lawn Plumbing", "license_type": "plumbing_contractor"}}]`
- `rule_documents.csv` exclusion examples: none
- Raw CSV headers:
- `permits.csv` headers: `permit_number`, `address`, `city`, `state`, `zip_code`, `trade`, `work_class`, `property_type`, `permit_type`, `status`, `file_date`, `issue_date`, `final_date`, `declared_valuation`, `work_description`, `contractor_name`, `source_url`
- `inspections.csv` headers: `permit_number`, `inspection_date`, `inspection_type`, `result`, `notes`, `inspector_name`, `reinspection_flag`, `source_url`
- `contractors.csv` headers: `registration_id`, `name`, `license_type`, `registration_status`, `city`, `state`
- `rule_documents.csv` headers: `title`, `document_type`, `effective_date`, `source_url`, `text_content`
- Raw CSV required fields:
- `permits.csv` required: `permit_number`, `address`, `city`, `trade`, `work_class`
- `inspections.csv` required: `permit_number`, `inspection_date`, `inspection_type`, `result`
- `contractors.csv` required: `registration_id`, `name`, `license_type`
- `rule_documents.csv` required: `title`
- Raw CSV optional fields:
- `permits.csv` optional: `state`, `zip_code`, `property_type`, `permit_type`, `status`, `file_date`, `issue_date`, `final_date`, `declared_valuation`, `work_description`, `contractor_name`, `source_url`
- `inspections.csv` optional: `notes`, `inspector_name`, `reinspection_flag`, `source_url`
- `contractors.csv` optional: `registration_status`, `city`, `state`
- `rule_documents.csv` optional: `document_type`, `effective_date`, `source_url`, `text_content`
- Raw CSV append templates:
- `permits.csv` append template: `{"permit_number": "<required>", "address": "<required>", "city": "<required>", "state": "", "zip_code": "", "trade": "<required>", "work_class": "<required>", "property_type": "", "permit_type": "", "status": "", "file_date": "", "issue_date": "", "final_date": "", "declared_valuation": "", "work_description": "", "contractor_name": "", "source_url": ""}`
- `inspections.csv` append template: `{"permit_number": "<required>", "inspection_date": "<required>", "inspection_type": "<required>", "result": "<required>", "notes": "", "inspector_name": "", "reinspection_flag": "", "source_url": ""}`
- `contractors.csv` append template: `{"registration_id": "<required>", "name": "<required>", "license_type": "<required>", "registration_status": "", "city": "", "state": ""}`
- `rule_documents.csv` append template: `{"title": "<required>", "document_type": "", "effective_date": "", "source_url": "", "text_content": ""}`
- Raw CSV required-field gaps:
- `permits.csv` required-field gaps: `0/15` rows, missing headers: none, field counts: `{"address": 0, "city": 0, "permit_number": 0, "trade": 0, "work_class": 0}`
- `inspections.csv` required-field gaps: `0/41` rows, missing headers: none, field counts: `{"inspection_date": 0, "inspection_type": 0, "permit_number": 0, "result": 0}`
- `contractors.csv` required-field gaps: `0/6` rows, missing headers: none, field counts: `{"license_type": 0, "name": 0, "registration_id": 0}`
- `rule_documents.csv` required-field gaps: `0/3` rows, missing headers: none, field counts: `{"title": 0}`
- Require-ready pipeline: `python3 scripts/run_dallas_import_pipeline.py --require-ready`
- Summary-only require-ready pipeline: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready`
- Summary-only require-ready JSON pipeline: `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`

## Reports

- Coverage: `generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md`
- Contract: `generated/contracts/dallas-electrician-contract-summary-v1/summary.md`
- Workflow: `generated/workflows/dallas-inspection-workflow-v1/action-queue.md`
- Summary JSON: `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json`
