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
- Next raw import scope counts: see Follow-Up
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
- Raw CSV import scope counts:
- `permits.csv` import scope: `14/15` importable, excluded: `1`, reasons: `{"excluded_by_city": 0, "excluded_by_trade": 1, "excluded_by_work_class": 0}`
- `inspections.csv` import scope: `40/41` importable, excluded: `1`, reasons: `{"excluded_by_unimported_permit": 1}`
- `contractors.csv` import scope: `5/6` importable, excluded: `1`, reasons: `{"excluded_by_license_type": 1}`
- `rule_documents.csv` import scope: `3/3` importable, excluded: `0`, reasons: `{"excluded_by_missing_title": 0}`
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
