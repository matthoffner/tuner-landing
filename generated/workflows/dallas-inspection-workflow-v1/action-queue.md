# Dallas Inspection Workflow V1

This artifact turns reviewed Dallas electrician inspection labels into a concrete action queue. It is still generated from fixture data, but it shows the product shape: after a failed, partial, or not-ready inspection, surface the address, failure context, recommended actions, and observed follow-up.

## Summary

- Queue items: `130`
- Priority counts: `{"high": 6, "medium": 124}`
- Trigger result counts: `{"fail": 6, "not_ready": 4, "partial": 120}`
- Operator correction events: `130`
- Operator correction ledger: `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`
- Accepted correction patterns: `6`

## Accepted Operator Correction Patterns

### operator-pattern:accepted:0001

- Queue items: `105`
- Actions: `Complete remaining work, Schedule reinspection`
- Action IDs: `complete_remaining_work, schedule_reinspection`
- Trigger results: `{"partial": 105}`
- Failure reasons: `{"incomplete_work": 105}`
- Inspection types: `{"rough_in": 105}`
- Follow-up results: `{"pass": 105}`
- Example permits: `ELP-2026-0203, ELZ-2026-0215, ELZ-2026-0216, ELZ-2026-0225, ELZ-2026-0226, ELZ-2026-0227, ELZ-2026-0228, ELZ-2026-0231, ELZ-2026-0232, ELZ-2026-0233, ELZ-2026-0234, ELZ-2026-0235, ELZ-2026-0236, ELZ-2026-0237, ELZ-2026-0238, ELZ-2026-0239, ELZ-2026-0240, ELZ-2026-0241, ELZ-2026-0242, ELZ-2026-0243, ELZ-2026-0244, ELZ-2026-0245, ELZ-2026-0246, ELZ-2026-0248, ELZ-2026-0249, ELZ-2026-0250, ELZ-2026-0251, ELZ-2026-0252, ELZ-2026-0253, ELZ-2026-0255, ELZ-2026-0256, ELZ-2026-0257, ELZ-2026-0258, ELZ-2026-0259, ELZ-2026-0260, ELZ-2026-0261, ELZ-2026-0262, ELZ-2026-0263, ELZ-2026-0264, ELZ-2026-0265, ELZ-2026-0266, ELZ-2026-0267, ELZ-2026-0268, ELZ-2026-0270, ELZ-2026-0271, ELZ-2026-0272, ELZ-2026-0273, ELZ-2026-0274, ELZ-2026-0275, ELZ-2026-0276, ELZ-2026-0277, ELZ-2026-0278, ELZ-2026-0279, ELZ-2026-0280, ELZ-2026-0281, ELZ-2026-0282, ELZ-2026-0283, ELZ-2026-0284, ELZ-2026-0285, ELZ-2026-0286, ELZ-2026-0287, ELZ-2026-0288, ELZ-2026-0289, ELZ-2026-0290, ELZ-2026-0291, ELZ-2026-0292, ELZ-2026-0293, ELZ-2026-0294, ELZ-2026-0295, ELZ-2026-0296, ELZ-2026-0297, ELZ-2026-0298, ELZ-2026-0299, ELZ-2026-0300, ELZ-2026-0301, ELZ-2026-0302, ELZ-2026-0303, ELZ-2026-0304, ELZ-2026-0305, ELZ-2026-0306, ELZ-2026-0307, ELZ-2026-0308, ELZ-2026-0309, ELZ-2026-0310, ELZ-2026-0311, ELZ-2026-0312, ELZ-2026-0313, ELZ-2026-0314, ELZ-2026-0315, ELZ-2026-0316, ELZ-2026-0317, ELZ-2026-0318, ELZ-2026-0319, ELZ-2026-0320, ELZ-2026-0321, ELZ-2026-0322, ELZ-2026-0323, ELZ-2026-0324, ELZ-2026-0325, ELZ-2026-0326, ELZ-2026-0327, ELZ-2026-0328, ELZ-2026-0329, ELZ-2026-0330, ELZ-2026-0331`

### operator-pattern:accepted:0002

- Queue items: `12`
- Actions: `Correct wiring or devices, Schedule reinspection`
- Action IDs: `correct_wiring_or_devices, schedule_reinspection`
- Trigger results: `{"fail": 2, "partial": 10}`
- Failure reasons: `{"wiring_or_device_issue": 12}`
- Inspection types: `{"final": 2, "rough_in": 10}`
- Follow-up results: `{"pass": 12}`
- Example permits: `ELP-2026-0209, ELR-2026-0201, ELR-2026-0207, ELZ-2026-0218, ELZ-2026-0219, ELZ-2026-0220, ELZ-2026-0221, ELZ-2026-0222, ELZ-2026-0223, ELZ-2026-0224, ELZ-2026-0229, ELZ-2026-0230`

### operator-pattern:accepted:0003

- Queue items: `4`
- Actions: `Ensure site access, Schedule reinspection`
- Action IDs: `ensure_site_access, schedule_reinspection`
- Trigger results: `{"not_ready": 4}`
- Failure reasons: `{"access_or_scheduling_issue": 4}`
- Inspection types: `{"final": 2, "service_release": 2}`
- Follow-up results: `{"pass": 4}`
- Example permits: `ELM-2026-0211, ELS-2026-0202, ELS-2026-0210, ELZ-2026-0217`

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

### ELZ-2026-0216 - 2718 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-04-26` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-01` `correction_followup` -> `pass`
- Evidence: Remaining junction cover and hallway trim incomplete before repair rough-in approval.

### ELZ-2026-0217 - 2726 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-04-28` `final` -> `not_ready`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-05-03` `correction_followup` -> `pass`
- Evidence: Locked gate blocked final inspection access for porch circuit trim verification.

### ELZ-2026-0218 - 2740 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-01` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-06` `correction_followup` -> `pass`
- Evidence: Kitchen branch wiring repaired but GFCI device and island receptacle trim remained incomplete.

### ELZ-2026-0219 - 2752 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-03` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-08` `correction_followup` -> `pass`
- Evidence: Bathroom branch wiring repaired but AFCI breaker and receptacle trim remained incomplete before rough-in approval.

### ELZ-2026-0220 - 2764 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-05` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-10` `correction_followup` -> `pass`
- Evidence: Bedroom branch wiring repaired but replacement receptacle devices and wall trim remained incomplete before rough-in approval.

### ELZ-2026-0221 - 2776 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-07` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-12` `correction_followup` -> `pass`
- Evidence: Laundry branch wiring repaired but replacement device boxes and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0222 - 2788 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-09` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-14` `correction_followup` -> `pass`
- Evidence: Pantry branch wiring repaired but replacement junction covers and device trim remained incomplete before rough-in approval.

### ELZ-2026-0223 - 2800 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-11` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-16` `correction_followup` -> `pass`
- Evidence: Closet branch wiring repaired but replacement switch boxes and device trim remained incomplete before rough-in approval.

### ELZ-2026-0224 - 2812 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-13` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-18` `correction_followup` -> `pass`
- Evidence: Dining branch wiring repaired but replacement dimmer devices and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0225 - 2824 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-15` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-20` `correction_followup` -> `pass`
- Evidence: Hallway branch wiring repaired but replacement occupancy sensors and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0226 - 2836 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-17` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-22` `correction_followup` -> `pass`
- Evidence: Stairwell branch wiring repaired but replacement smoke alarms and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0227 - 2848 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-18` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Attic branch wiring repaired but replacement light fixtures and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0228 - 2860 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-19` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Garage branch wiring repaired but replacement weatherproof covers and exterior trim remained incomplete before rough-in approval.

### ELZ-2026-0229 - 2872 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-20` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Porch branch wiring repaired but replacement exterior GFCI devices and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0230 - 2884 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-21` `rough_in` -> `partial`
- Failure reason: `wiring_or_device_issue`
- Recommended actions: `Correct wiring or devices, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Laundry branch wiring repaired but replacement exhaust fan timer devices and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0231 - 2896 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Pantry branch wiring repaired but replacement under-cabinet lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0232 - 2908 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Sunroom branch wiring repaired but replacement pendant fixtures and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0233 - 2920 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Den branch wiring repaired but replacement recessed lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0234 - 2932 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Bedroom branch wiring repaired but replacement vanity lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0235 - 2944 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Hallway branch wiring repaired but replacement sconce lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0236 - 2956 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Foyer branch wiring repaired but replacement track lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0237 - 2968 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Living room branch wiring repaired but replacement ceiling fan controls and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0238 - 2980 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Dining room branch wiring repaired but replacement chandelier controls and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0239 - 2992 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Porch branch wiring repaired but replacement exterior coach lights and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0240 - 3004 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Back porch branch wiring repaired but replacement motion-sensor lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0241 - 3016 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Side yard branch wiring repaired but replacement security floodlights and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0242 - 3028 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Front walk branch wiring repaired but replacement pathway lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0243 - 3040 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Driveway branch wiring repaired but replacement bollard lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0244 - 3052 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Alley branch wiring repaired but replacement gate lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0245 - 3064 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Detached garage branch wiring repaired but replacement task lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0246 - 3076 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Carport branch wiring repaired but replacement canopy lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0247 - 3088 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Rear entry branch wiring repaired but replacement step lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0248 - 3100 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Laundry room branch wiring repaired but replacement utility lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0249 - 3112 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Mudroom branch wiring repaired but replacement closet lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0250 - 3124 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Storage room branch wiring repaired but replacement recessed closet fixtures and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0251 - 3136 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Pantry branch wiring repaired but replacement under-shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0252 - 3148 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Hall closet branch wiring repaired but replacement shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0253 - 3160 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Linen closet branch wiring repaired but replacement ceiling lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0254 - 3172 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Entry closet branch wiring repaired but replacement pendant lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0255 - 3184 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Bedroom closet branch wiring repaired but replacement cove lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0256 - 3196 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Primary closet branch wiring repaired but replacement mirror lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0257 - 3208 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Guest closet branch wiring repaired but replacement strip lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0258 - 3220 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Utility closet branch wiring repaired but replacement linear lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0259 - 3232 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Laundry closet branch wiring repaired but replacement tape lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0260 - 3244 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Pantry closet branch wiring repaired but replacement puck lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0261 - 3256 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Storage closet branch wiring repaired but replacement rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0262 - 3268 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Rear closet branch wiring repaired but replacement channel lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0263 - 3280 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Hall closet branch wiring repaired but replacement rod lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0264 - 3292 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Front closet branch wiring repaired but replacement track lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0265 - 3304 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Back hall closet branch wiring repaired but replacement bar lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0266 - 3316 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Stair closet branch wiring repaired but replacement bulkhead lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0267 - 3328 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Linen closet branch wiring repaired but replacement shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0268 - 3340 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Foyer closet branch wiring repaired but replacement cove lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0269 - 3352 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `access_or_scheduling_issue`
- Recommended actions: `Ensure site access, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Entry closet branch wiring repaired but replacement valance lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0270 - 3364 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Bedroom closet branch wiring repaired but replacement soffit lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0271 - 3376 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Upstairs closet branch wiring repaired but replacement cabinet lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0272 - 3388 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Downstairs closet branch wiring repaired but replacement niche lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0273 - 3400 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Pantry closet branch wiring repaired but replacement toe-kick lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0274 - 3412 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Rear pantry closet branch wiring repaired but replacement accent lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0275 - 3424 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Side pantry closet branch wiring repaired but replacement task lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0276 - 3436 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: West pantry closet branch wiring repaired but replacement under-cabinet lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0277 - 3448 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: East pantry closet branch wiring repaired but replacement linear lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0278 - 3460 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: North pantry closet branch wiring repaired but replacement display lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0279 - 3472 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: South pantry closet branch wiring repaired but replacement picture lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0280 - 3484 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Center pantry closet branch wiring repaired but replacement rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0281 - 3496 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Upper pantry closet branch wiring repaired but replacement puck lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0282 - 3508 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Lower pantry closet branch wiring repaired but replacement rope lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0283 - 3520 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Corner pantry closet branch wiring repaired but replacement accent-strip lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0284 - 3532 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Rear hall pantry closet branch wiring repaired but replacement cove lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0285 - 3544 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Front hall pantry closet branch wiring repaired but replacement valance lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0286 - 3556 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Side hall pantry closet branch wiring repaired but replacement shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0287 - 3568 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Middle hall pantry closet branch wiring repaired but replacement ceiling-strip lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0288 - 3580 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Rear annex pantry closet branch wiring repaired but replacement under-shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0289 - 3592 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: East annex pantry closet branch wiring repaired but replacement toe-kick lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0290 - 3604 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: West annex pantry closet branch wiring repaired but replacement baseboard lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0291 - 3616 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: North annex pantry closet branch wiring repaired but replacement display lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0292 - 3628 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: South annex pantry closet branch wiring repaired but replacement picture lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0293 - 3640 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: Garden annex pantry closet branch wiring repaired but replacement cove lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0294 - 3652 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: West garden annex pantry closet branch wiring repaired but replacement valance lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0295 - 3664 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: East garden annex pantry closet branch wiring repaired but replacement lantern-strip lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0296 - 3676 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: North garden annex pantry closet branch wiring repaired but replacement shelf lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0297 - 3688 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: South garden annex pantry closet branch wiring repaired but replacement picture-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0298 - 3700 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: East conservatory pantry closet branch wiring repaired but replacement under-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0299 - 3712 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-22` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-23` `correction_followup` -> `pass`
- Evidence: West conservatory pantry closet branch wiring repaired but replacement cove-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0300 - 3724 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-23` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-24` `correction_followup` -> `pass`
- Evidence: South conservatory pantry closet branch wiring repaired but replacement lantern-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0301 - 3736 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-23` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-24` `correction_followup` -> `pass`
- Evidence: North conservatory pantry closet branch wiring repaired but replacement valance-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0302 - 3748 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-23` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-24` `correction_followup` -> `pass`
- Evidence: East mezzanine pantry closet branch wiring repaired but replacement gallery-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0303 - 3760 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-23` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-24` `correction_followup` -> `pass`
- Evidence: West mezzanine pantry closet branch wiring repaired but replacement display-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0304 - 3772 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-23` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-24` `correction_followup` -> `pass`
- Evidence: North mezzanine pantry closet branch wiring repaired but replacement canopy-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0305 - 3784 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South mezzanine pantry closet branch wiring repaired but replacement bulkhead-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0306 - 3796 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East loft pantry closet branch wiring repaired but replacement shelf-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0307 - 3808 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West loft pantry closet branch wiring repaired but replacement track-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0308 - 3820 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South loft pantry closet branch wiring repaired but replacement cove-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0309 - 3832 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: North attic pantry closet branch wiring repaired but replacement cornice-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0310 - 3844 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East attic pantry closet branch wiring repaired but replacement pendant-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0311 - 3856 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West attic pantry closet branch wiring repaired but replacement gallery-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0312 - 3868 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South attic pantry closet branch wiring repaired but replacement transom-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0313 - 3880 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: North annex attic pantry closet branch wiring repaired but replacement soffit-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0314 - 3892 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South annex attic pantry closet branch wiring repaired but replacement lintel-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0315 - 3904 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East annex attic pantry closet branch wiring repaired but replacement clerestory-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0316 - 3916 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West annex attic pantry closet branch wiring repaired but replacement pilaster-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0317 - 3928 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: North wing attic pantry closet branch wiring repaired but replacement mullion-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0318 - 3940 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South wing attic pantry closet branch wiring repaired but replacement stile-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0319 - 3952 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East wing attic pantry closet branch wiring repaired but replacement header-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0320 - 3964 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West wing attic pantry closet branch wiring repaired but replacement cap-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0321 - 3976 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: North porch attic pantry closet branch wiring repaired but replacement jamb-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0322 - 3988 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South porch attic pantry closet branch wiring repaired but replacement sill-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0323 - 4000 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East porch attic pantry closet branch wiring repaired but replacement rail-splice lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0324 - 4012 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West porch attic pantry closet branch wiring repaired but replacement bracket-rail lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0325 - 4024 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Garden porch attic pantry closet branch wiring repaired but replacement transom-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0326 - 4036 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: North garden porch attic pantry closet branch wiring repaired but replacement threshold-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0327 - 4048 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: South garden porch attic pantry closet branch wiring repaired but replacement latch-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0328 - 4060 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: East garden porch attic pantry closet branch wiring repaired but replacement hinge-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0329 - 4072 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: West garden porch attic pantry closet branch wiring repaired but replacement sill-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0330 - 4084 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Northwest garden porch attic pantry closet branch wiring repaired but replacement jamb-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0331 - 4096 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Northeast garden porch attic pantry closet branch wiring repaired but replacement stile-bracket lighting and cover trim remained incomplete before rough-in approval.
