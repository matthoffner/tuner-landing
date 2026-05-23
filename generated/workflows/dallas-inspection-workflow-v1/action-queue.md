# Dallas Inspection Workflow V1

This artifact turns reviewed Dallas electrician inspection labels into a concrete action queue. It is still generated from fixture data, but it shows the product shape: after a failed, partial, or not-ready inspection, surface the address, failure context, recommended actions, and observed follow-up.

## Summary

- Queue items: `14`
- Priority counts: `{"high": 6, "medium": 8}`
- Trigger result counts: `{"fail": 6, "not_ready": 3, "partial": 5}`
- Operator correction events: `14`
- Operator correction ledger: `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`
- Accepted correction patterns: `6`

## Accepted Operator Correction Patterns

### operator-pattern:accepted:0001

- Queue items: `3`
- Actions: `Correct wiring or devices, Schedule reinspection`
- Action IDs: `correct_wiring_or_devices, schedule_reinspection`
- Trigger results: `{"fail": 2, "partial": 1}`
- Failure reasons: `{"wiring_or_device_issue": 3}`
- Inspection types: `{"final": 2, "rough_in": 1}`
- Follow-up results: `{"pass": 3}`
- Example permits: `ELP-2026-0209, ELR-2026-0201, ELR-2026-0207`

### operator-pattern:accepted:0002

- Queue items: `3`
- Actions: `Ensure site access, Schedule reinspection`
- Action IDs: `ensure_site_access, schedule_reinspection`
- Trigger results: `{"not_ready": 3}`
- Failure reasons: `{"access_or_scheduling_issue": 3}`
- Inspection types: `{"final": 1, "service_release": 2}`
- Follow-up results: `{"pass": 3}`
- Example permits: `ELM-2026-0211, ELS-2026-0202, ELS-2026-0210`

### operator-pattern:accepted:0003

- Queue items: `2`
- Actions: `Complete remaining work, Schedule reinspection`
- Action IDs: `complete_remaining_work, schedule_reinspection`
- Trigger results: `{"partial": 2}`
- Failure reasons: `{"incomplete_work": 2}`
- Inspection types: `{"rough_in": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELP-2026-0203, ELZ-2026-0215`

### operator-pattern:accepted:0004

- Queue items: `2`
- Actions: `Correct grounding or bonding, Add missing labels or documentation`
- Action IDs: `correct_grounding_or_bonding, add_labels_or_documentation`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"rough_in": 2}`
- Follow-up results: `{"partial": 2}`
- Example permits: `ELN-2026-0204, ELN-2026-0208`

### operator-pattern:accepted:0005

- Queue items: `2`
- Actions: `Correct grounding or bonding, Add missing labels or documentation, Schedule reinspection`
- Action IDs: `correct_grounding_or_bonding, add_labels_or_documentation, schedule_reinspection`
- Trigger results: `{"partial": 2}`
- Failure reasons: `{"grounding_or_bonding_issue": 2}`
- Inspection types: `{"correction_followup": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELN-2026-0204, ELN-2026-0208`

### operator-pattern:accepted:0006

- Queue items: `2`
- Actions: `Correct panel or service issue, Add missing labels or documentation, Schedule reinspection`
- Action IDs: `correct_panel_or_service, add_labels_or_documentation, schedule_reinspection`
- Trigger results: `{"fail": 2}`
- Failure reasons: `{"panel_or_service_issue": 2}`
- Inspection types: `{"service_release": 2}`
- Follow-up results: `{"pass": 2}`
- Example permits: `ELS-2026-0213, ELS-2026-0214`

## Action Queue

### ELR-2026-0201 - 412 N WINNETKA AVE DALLAS TX 75208

- Priority: `high`
- Contractor: `Bishop Arts Electric`
- Trigger: `2026-04-09` `final` -> `fail`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-04-12` `correction_followup` -> `pass`
- Evidence: Kitchen GFCI protection missing and device trim incomplete at backsplash wall.

### ELN-2026-0208 - 7315 LA VISTA DR DALLAS TX 75214

- Priority: `high`
- Contractor: `White Rock Electric`
- Trigger: `2026-04-10` `rough_in` -> `fail`
- Failure reason: `grounding_or_bonding_issue`
- Recommended actions: `Correct grounding or bonding, Add missing labels or documentation`
- Follow-up observed: `2026-04-17` `correction_followup` -> `partial`
- Evidence: Grounding electrode connection incomplete and detached unit panel schedule not posted.

### ELN-2026-0204 - 7347 LA VISTA DR DALLAS TX 75214

- Priority: `high`
- Contractor: `White Rock Electric`
- Trigger: `2026-04-11` `rough_in` -> `fail`
- Failure reason: `grounding_or_bonding_issue`
- Recommended actions: `Correct grounding or bonding, Add missing labels or documentation`
- Follow-up observed: `2026-04-16` `correction_followup` -> `partial`
- Evidence: Subpanel grounding incomplete and panel schedule missing at detached unit.

### ELR-2026-0207 - 527 N CLINTON AVE DALLAS TX 75208

- Priority: `high`
- Contractor: `Bishop Arts Electric`
- Trigger: `2026-04-13` `final` -> `fail`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-04-16` `correction_followup` -> `pass`
- Evidence: Required kitchen GFCI protection missing and two counter receptacle devices not trimmed out.

### ELS-2026-0213 - 10018 FERGUSON RD DALLAS TX 75228

- Priority: `high`
- Contractor: `Casa View Electric`
- Trigger: `2026-04-18` `service_release` -> `fail`
- Failure reason: `panel_or_service_issue`
- Recommended actions: `Correct panel or service issue, Add missing labels or documentation, Schedule reinspection`
- Follow-up observed: `2026-04-23` `correction_followup` -> `pass`
- Evidence: Exterior disconnect not labeled and service panel deadfront missing before utility release.

### ELS-2026-0214 - 10034 FERGUSON RD DALLAS TX 75228

- Priority: `high`
- Contractor: `Casa View Electric`
- Trigger: `2026-04-20` `service_release` -> `fail`
- Failure reason: `panel_or_service_issue`
- Recommended actions: `Correct panel or service issue, Add missing labels or documentation, Schedule reinspection`
- Follow-up observed: `2026-04-25` `correction_followup` -> `pass`
- Evidence: Service panel deadfront incomplete and exterior disconnect labeling missing at release inspection.

### ELP-2026-0203 - 2234 S MARSALIS AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-03-17` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-03-22` `correction_followup` -> `pass`
- Evidence: Most damaged wiring repaired but hallway trim incomplete before closeout.

### ELP-2026-0209 - 2615 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-04-09` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-04-15` `correction_followup` -> `pass`
- Evidence: Bedroom branch wiring repaired but trim-out incomplete and one switch device still missing.

### ELS-2026-0202 - 9915 FERGUSON RD DALLAS TX 75228

- Priority: `medium`
- Contractor: `Casa View Electric`
- Trigger: `2026-04-10` `service_release` -> `not_ready`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-04-15` `correction_followup` -> `pass`
- Evidence: Disconnect area blocked and homeowner unable to provide clear meter access for release inspection.

### ELM-2026-0211 - 1836 NOMAS ST DALLAS TX 75212

- Priority: `medium`
- Contractor: `Trinity Grove Electric`
- Trigger: `2026-04-14` `final` -> `not_ready`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-04-19` `correction_followup` -> `pass`
- Evidence: Locked side gate prevented access to the rear addition devices and no adult was on site for entry.

### ELS-2026-0210 - 10002 FERGUSON RD DALLAS TX 75228

- Priority: `medium`
- Contractor: `Casa View Electric`
- Trigger: `2026-04-14` `service_release` -> `not_ready`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-04-18` `correction_followup` -> `pass`
- Evidence: Meter socket access blocked by fencing and homeowner unavailable for the utility release appointment.

### ELN-2026-0204 - 7347 LA VISTA DR DALLAS TX 75214

- Priority: `medium`
- Contractor: `White Rock Electric`
- Trigger: `2026-04-16` `correction_followup` -> `partial`
- Failure reason: `grounding_or_bonding_issue`
- Recommended actions: `Correct grounding or bonding, Add missing labels or documentation, Schedule reinspection`
- Follow-up observed: `2026-04-20` `final` -> `pass`
- Evidence: Grounding corrected but final trim and breaker labeling still incomplete.

### ELN-2026-0208 - 7315 LA VISTA DR DALLAS TX 75214

- Priority: `medium`
- Contractor: `White Rock Electric`
- Trigger: `2026-04-17` `correction_followup` -> `partial`
- Failure reason: `grounding_or_bonding_issue`
- Recommended actions: `Correct grounding or bonding, Add missing labels or documentation, Schedule reinspection`
- Follow-up observed: `2026-04-21` `final` -> `pass`
- Evidence: Grounding corrected but final trim and breaker labeling still incomplete at garage apartment panel.

### ELZ-2026-0215 - 2702 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-04-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-04-27` `correction_followup` -> `pass`
- Evidence: Ceiling junction cover and hallway trim incomplete before rough-in approval.
