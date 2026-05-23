# Dallas Inspection Workflow V1

This artifact turns reviewed Dallas electrician inspection labels into a concrete action queue. It is still generated from fixture data, but it shows the product shape: after a failed, partial, or not-ready inspection, surface the address, failure context, recommended actions, and observed follow-up.

## Summary

- Queue items: `13`
- Priority counts: `{"high": 6, "medium": 7}`
- Trigger result counts: `{"fail": 6, "not_ready": 3, "partial": 4}`
- Operator correction events: `1`
- Operator correction ledger: `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`

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
