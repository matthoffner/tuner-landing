# Dallas Inspection Workflow V1

This artifact turns reviewed Dallas electrician inspection labels into a concrete action queue. It is still generated from fixture data, but it shows the product shape: after a failed, partial, or not-ready inspection, surface the address, failure context, recommended actions, and observed follow-up.

## Summary

- Queue items: `442`
- Priority counts: `{"high": 6, "medium": 436}`
- Trigger result counts: `{"fail": 6, "not_ready": 4, "partial": 432}`
- Operator correction events: `442`
- Operator correction ledger: `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`
- Accepted correction patterns: `6`

## Accepted Operator Correction Patterns

### operator-pattern:accepted:0001

- Queue items: `417`
- Actions: `Complete remaining work, Schedule reinspection`
- Action IDs: `complete_remaining_work, schedule_reinspection`
- Trigger results: `{"partial": 417}`
- Failure reasons: `{"incomplete_work": 417}`
- Inspection types: `{"rough_in": 417}`
- Follow-up results: `{"pass": 417}`
- Example permits: `ELP-2026-0203, ELZ-2026-0215, ELZ-2026-0216, ELZ-2026-0225, ELZ-2026-0226, ELZ-2026-0227, ELZ-2026-0228, ELZ-2026-0231, ELZ-2026-0232, ELZ-2026-0233, ELZ-2026-0234, ELZ-2026-0235, ELZ-2026-0236, ELZ-2026-0237, ELZ-2026-0238, ELZ-2026-0239, ELZ-2026-0240, ELZ-2026-0241, ELZ-2026-0242, ELZ-2026-0243, ELZ-2026-0244, ELZ-2026-0245, ELZ-2026-0246, ELZ-2026-0248, ELZ-2026-0249, ELZ-2026-0250, ELZ-2026-0251, ELZ-2026-0252, ELZ-2026-0253, ELZ-2026-0255, ELZ-2026-0256, ELZ-2026-0257, ELZ-2026-0258, ELZ-2026-0259, ELZ-2026-0260, ELZ-2026-0261, ELZ-2026-0262, ELZ-2026-0263, ELZ-2026-0264, ELZ-2026-0265, ELZ-2026-0266, ELZ-2026-0267, ELZ-2026-0268, ELZ-2026-0270, ELZ-2026-0271, ELZ-2026-0272, ELZ-2026-0273, ELZ-2026-0274, ELZ-2026-0275, ELZ-2026-0276, ELZ-2026-0277, ELZ-2026-0278, ELZ-2026-0279, ELZ-2026-0280, ELZ-2026-0281, ELZ-2026-0282, ELZ-2026-0283, ELZ-2026-0284, ELZ-2026-0285, ELZ-2026-0286, ELZ-2026-0287, ELZ-2026-0288, ELZ-2026-0289, ELZ-2026-0290, ELZ-2026-0291, ELZ-2026-0292, ELZ-2026-0293, ELZ-2026-0294, ELZ-2026-0295, ELZ-2026-0296, ELZ-2026-0297, ELZ-2026-0298, ELZ-2026-0299, ELZ-2026-0300, ELZ-2026-0301, ELZ-2026-0302, ELZ-2026-0303, ELZ-2026-0304, ELZ-2026-0305, ELZ-2026-0306, ELZ-2026-0307, ELZ-2026-0308, ELZ-2026-0309, ELZ-2026-0310, ELZ-2026-0311, ELZ-2026-0312, ELZ-2026-0313, ELZ-2026-0314, ELZ-2026-0315, ELZ-2026-0316, ELZ-2026-0317, ELZ-2026-0318, ELZ-2026-0319, ELZ-2026-0320, ELZ-2026-0321, ELZ-2026-0322, ELZ-2026-0323, ELZ-2026-0324, ELZ-2026-0325, ELZ-2026-0326, ELZ-2026-0327, ELZ-2026-0328, ELZ-2026-0329, ELZ-2026-0330, ELZ-2026-0331, ELZ-2026-0332, ELZ-2026-0333, ELZ-2026-0334, ELZ-2026-0335, ELZ-2026-0336, ELZ-2026-0337, ELZ-2026-0338, ELZ-2026-0339, ELZ-2026-0340, ELZ-2026-0341, ELZ-2026-0342, ELZ-2026-0343, ELZ-2026-0344, ELZ-2026-0345, ELZ-2026-0346, ELZ-2026-0347, ELZ-2026-0348, ELZ-2026-0349, ELZ-2026-0350, ELZ-2026-0351, ELZ-2026-0352, ELZ-2026-0353, ELZ-2026-0354, ELZ-2026-0355, ELZ-2026-0356, ELZ-2026-0357, ELZ-2026-0358, ELZ-2026-0359, ELZ-2026-0360, ELZ-2026-0361, ELZ-2026-0362, ELZ-2026-0363, ELZ-2026-0364, ELZ-2026-0365, ELZ-2026-0366, ELZ-2026-0367, ELZ-2026-0368, ELZ-2026-0369, ELZ-2026-0370, ELZ-2026-0371, ELZ-2026-0372, ELZ-2026-0373, ELZ-2026-0374, ELZ-2026-0375, ELZ-2026-0376, ELZ-2026-0377, ELZ-2026-0378, ELZ-2026-0379, ELZ-2026-0380, ELZ-2026-0381, ELZ-2026-0382, ELZ-2026-0383, ELZ-2026-0384, ELZ-2026-0385, ELZ-2026-0386, ELZ-2026-0387, ELZ-2026-0388, ELZ-2026-0389, ELZ-2026-0390, ELZ-2026-0391, ELZ-2026-0392, ELZ-2026-0393, ELZ-2026-0394, ELZ-2026-0395, ELZ-2026-0396, ELZ-2026-0397, ELZ-2026-0398, ELZ-2026-0399, ELZ-2026-0400, ELZ-2026-0401, ELZ-2026-0402, ELZ-2026-0403, ELZ-2026-0404, ELZ-2026-0405, ELZ-2026-0406, ELZ-2026-0407, ELZ-2026-0408, ELZ-2026-0409, ELZ-2026-0410, ELZ-2026-0411, ELZ-2026-0412, ELZ-2026-0413, ELZ-2026-0414, ELZ-2026-0415, ELZ-2026-0416, ELZ-2026-0417, ELZ-2026-0418, ELZ-2026-0419, ELZ-2026-0420, ELZ-2026-0421, ELZ-2026-0422, ELZ-2026-0423, ELZ-2026-0424, ELZ-2026-0425, ELZ-2026-0426, ELZ-2026-0427, ELZ-2026-0428, ELZ-2026-0429, ELZ-2026-0430, ELZ-2026-0431, ELZ-2026-0432, ELZ-2026-0433, ELZ-2026-0434, ELZ-2026-0435, ELZ-2026-0436, ELZ-2026-0437, ELZ-2026-0438, ELZ-2026-0439, ELZ-2026-0440, ELZ-2026-0441, ELZ-2026-0442, ELZ-2026-0443, ELZ-2026-0444, ELZ-2026-0445, ELZ-2026-0446, ELZ-2026-0447, ELZ-2026-0448, ELZ-2026-0449, ELZ-2026-0450, ELZ-2026-0451, ELZ-2026-0452, ELZ-2026-0453, ELZ-2026-0454, ELZ-2026-0455, ELZ-2026-0456, ELZ-2026-0457, ELZ-2026-0458, ELZ-2026-0459, ELZ-2026-0460, ELZ-2026-0461, ELZ-2026-0462, ELZ-2026-0463, ELZ-2026-0464, ELZ-2026-0465, ELZ-2026-0466, ELZ-2026-0467, ELZ-2026-0468, ELZ-2026-0469, ELZ-2026-0470, ELZ-2026-0471, ELZ-2026-0472, ELZ-2026-0473, ELZ-2026-0474, ELZ-2026-0475, ELZ-2026-0476, ELZ-2026-0477, ELZ-2026-0478, ELZ-2026-0479, ELZ-2026-0480, ELZ-2026-0481, ELZ-2026-0482, ELZ-2026-0483, ELZ-2026-0484, ELZ-2026-0485, ELZ-2026-0486, ELZ-2026-0487, ELZ-2026-0488, ELZ-2026-0489, ELZ-2026-0490, ELZ-2026-0491, ELZ-2026-0492, ELZ-2026-0493, ELZ-2026-0494, ELZ-2026-0495, ELZ-2026-0496, ELZ-2026-0497, ELZ-2026-0498, ELZ-2026-0499, ELZ-2026-0500, ELZ-2026-0501, ELZ-2026-0502, ELZ-2026-0503, ELZ-2026-0504, ELZ-2026-0505, ELZ-2026-0506, ELZ-2026-0507, ELZ-2026-0508, ELZ-2026-0509, ELZ-2026-0510, ELZ-2026-0511, ELZ-2026-0512, ELZ-2026-0513, ELZ-2026-0514, ELZ-2026-0515, ELZ-2026-0516, ELZ-2026-0517, ELZ-2026-0518, ELZ-2026-0519, ELZ-2026-0520, ELZ-2026-0521, ELZ-2026-0522, ELZ-2026-0523, ELZ-2026-0524, ELZ-2026-0525, ELZ-2026-0526, ELZ-2026-0527, ELZ-2026-0528, ELZ-2026-0529, ELZ-2026-0530, ELZ-2026-0531, ELZ-2026-0532, ELZ-2026-0533, ELZ-2026-0534, ELZ-2026-0535, ELZ-2026-0536, ELZ-2026-0537, ELZ-2026-0538, ELZ-2026-0539, ELZ-2026-0540, ELZ-2026-0541, ELZ-2026-0542, ELZ-2026-0543, ELZ-2026-0544, ELZ-2026-0545, ELZ-2026-0546, ELZ-2026-0547, ELZ-2026-0548, ELZ-2026-0549, ELZ-2026-0550, ELZ-2026-0551, ELZ-2026-0552, ELZ-2026-0553, ELZ-2026-0554, ELZ-2026-0555, ELZ-2026-0556, ELZ-2026-0557, ELZ-2026-0558, ELZ-2026-0559, ELZ-2026-0560, ELZ-2026-0561, ELZ-2026-0562, ELZ-2026-0563, ELZ-2026-0564, ELZ-2026-0565, ELZ-2026-0566, ELZ-2026-0567, ELZ-2026-0568, ELZ-2026-0569, ELZ-2026-0570, ELZ-2026-0571, ELZ-2026-0572, ELZ-2026-0573, ELZ-2026-0574, ELZ-2026-0575, ELZ-2026-0576, ELZ-2026-0577, ELZ-2026-0578, ELZ-2026-0579, ELZ-2026-0580, ELZ-2026-0581, ELZ-2026-0582, ELZ-2026-0583, ELZ-2026-0584, ELZ-2026-0585, ELZ-2026-0586, ELZ-2026-0587, ELZ-2026-0588, ELZ-2026-0589, ELZ-2026-0590, ELZ-2026-0591, ELZ-2026-0592, ELZ-2026-0593, ELZ-2026-0594, ELZ-2026-0595, ELZ-2026-0596, ELZ-2026-0597, ELZ-2026-0598, ELZ-2026-0599, ELZ-2026-0600, ELZ-2026-0601, ELZ-2026-0602, ELZ-2026-0603, ELZ-2026-0604, ELZ-2026-0605, ELZ-2026-0606, ELZ-2026-0607, ELZ-2026-0608, ELZ-2026-0609, ELZ-2026-0610, ELZ-2026-0611, ELZ-2026-0612, ELZ-2026-0613, ELZ-2026-0614, ELZ-2026-0615, ELZ-2026-0616, ELZ-2026-0617, ELZ-2026-0618, ELZ-2026-0619, ELZ-2026-0620, ELZ-2026-0621, ELZ-2026-0622, ELZ-2026-0623, ELZ-2026-0624, ELZ-2026-0625, ELZ-2026-0626, ELZ-2026-0627, ELZ-2026-0628, ELZ-2026-0629, ELZ-2026-0630, ELZ-2026-0631, ELZ-2026-0632, ELZ-2026-0633, ELZ-2026-0634, ELZ-2026-0635, ELZ-2026-0636, ELZ-2026-0637, ELZ-2026-0638, ELZ-2026-0639, ELZ-2026-0640, ELZ-2026-0641, ELZ-2026-0642, ELZ-2026-0643`

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

### ELZ-2026-0332 - 4108 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Southeast garden porch attic pantry closet branch wiring repaired but replacement mullion-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0333 - 4120 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper garden porch attic pantry closet branch wiring repaired but replacement sash-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0334 - 4132 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper west garden porch attic pantry closet branch wiring repaired but replacement casing-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0335 - 4144 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper east garden porch attic pantry closet branch wiring repaired but replacement apron-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0336 - 4156 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper south garden porch attic pantry closet branch wiring repaired but replacement lintel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0337 - 4168 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper north garden porch attic pantry closet branch wiring repaired but replacement frieze-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0338 - 4180 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper central garden porch attic pantry closet branch wiring repaired but replacement plinth-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0339 - 4192 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper rear garden porch attic pantry closet branch wiring repaired but replacement cornice-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0340 - 4204 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper front garden porch attic pantry closet branch wiring repaired but replacement keystone-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0341 - 4216 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper side garden porch attic pantry closet branch wiring repaired but replacement pediment-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0342 - 4228 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper landing garden porch attic pantry closet branch wiring repaired but replacement transom-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0343 - 4240 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper stair garden porch attic pantry closet branch wiring repaired but replacement mullion-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0344 - 4252 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hall garden porch attic pantry closet branch wiring repaired but replacement stile-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0345 - 4264 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper den garden porch attic pantry closet branch wiring repaired but replacement lintel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0346 - 4276 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper parlor garden porch attic pantry closet branch wiring repaired but replacement soffit-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0347 - 4288 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper vestibule garden porch attic pantry closet branch wiring repaired but replacement fascia-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0348 - 4300 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper sitting garden porch attic pantry closet branch wiring repaired but replacement jamb-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0349 - 4312 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper library garden porch attic pantry closet branch wiring repaired but replacement stop-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0350 - 4324 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper study garden porch attic pantry closet branch wiring repaired but replacement casing-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0351 - 4336 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper alcove garden porch attic pantry closet branch wiring repaired but replacement apron-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0352 - 4348 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper nook garden porch attic pantry closet branch wiring repaired but replacement threshold-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0353 - 4360 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper foyer garden porch attic pantry closet branch wiring repaired but replacement header-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0354 - 4372 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper bay garden porch attic pantry closet branch wiring repaired but replacement reveal-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0355 - 4384 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper loft garden porch attic pantry closet branch wiring repaired but replacement capstone-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0356 - 4396 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper gallery garden porch attic pantry closet branch wiring repaired but replacement crown-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0357 - 4408 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper conservatory garden porch attic pantry closet branch wiring repaired but replacement gable-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0358 - 4420 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper solarium garden porch attic pantry closet branch wiring repaired but replacement clerestory-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0359 - 4432 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper arcade garden porch attic pantry closet branch wiring repaired but replacement lintel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0360 - 4444 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper passage garden porch attic pantry closet branch wiring repaired but replacement architrave-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0361 - 4456 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper loggia garden porch attic pantry closet branch wiring repaired but replacement spandrel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0362 - 4468 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dormer garden porch attic pantry closet branch wiring repaired but replacement parapet-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0363 - 4480 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper terrace garden porch attic pantry closet branch wiring repaired but replacement cornice-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0364 - 4492 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper portico garden porch attic pantry closet branch wiring repaired but replacement frieze-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0365 - 4504 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper gallery wing garden porch attic pantry closet branch wiring repaired but replacement dentil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0366 - 4516 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper arcade wing garden porch attic pantry closet branch wiring repaired but replacement modillion-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0367 - 4528 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper veranda wing garden porch attic pantry closet branch wiring repaired but replacement soffit-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0368 - 4540 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper balcony wing garden porch attic pantry closet branch wiring repaired but replacement fascia-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0369 - 4552 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper breezeway wing garden porch attic pantry closet branch wiring repaired but replacement gable-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0370 - 4564 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper lanai wing garden porch attic pantry closet branch wiring repaired but replacement eave-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0371 - 4576 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper sunroom wing garden porch attic pantry closet branch wiring repaired but replacement parapet-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0372 - 4588 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper lounge wing garden porch attic pantry closet branch wiring repaired but replacement corbel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0373 - 4600 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper atrium wing garden porch attic pantry closet branch wiring repaired but replacement pilaster-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0374 - 4612 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper solarium wing garden porch attic pantry closet branch wiring repaired but replacement keystone-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0375 - 4624 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper conservatory wing garden porch attic pantry closet branch wiring repaired but replacement voussoir-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0376 - 4636 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper oriel wing garden porch attic pantry closet branch wiring repaired but replacement tracery-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0377 - 4648 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper cupola wing garden porch attic pantry closet branch wiring repaired but replacement finial-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0378 - 4660 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper clerestory wing garden porch attic pantry closet branch wiring repaired but replacement cresting-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0379 - 4672 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper lantern wing garden porch attic pantry closet branch wiring repaired but replacement oculus-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0380 - 4684 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper belvedere wing garden porch attic pantry closet branch wiring repaired but replacement dormer-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0381 - 4696 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper observatory wing garden porch attic pantry closet branch wiring repaired but replacement mansard-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0382 - 4708 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper turret wing garden porch attic pantry closet branch wiring repaired but replacement gambrel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0383 - 4720 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper spire wing garden porch attic pantry closet branch wiring repaired but replacement bargeboard-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0384 - 4732 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper gablet wing garden porch attic pantry closet branch wiring repaired but replacement quoin-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0385 - 4744 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper oriel wing garden porch attic pantry closet branch wiring repaired but replacement fanlight-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0386 - 4756 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper vestibule wing garden porch attic pantry closet branch wiring repaired but replacement lunette-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0387 - 4768 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper transom wing garden porch attic pantry closet branch wiring repaired but replacement rosette-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0388 - 4780 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper gallery wing garden porch attic pantry closet branch wiring repaired but replacement medallion-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0389 - 4792 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper arcade wing garden porch attic pantry closet branch wiring repaired but replacement triforium-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0390 - 4804 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper cloister wing garden porch attic pantry closet branch wiring repaired but replacement archivolt-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0391 - 4816 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper apse wing garden porch attic pantry closet branch wiring repaired but replacement apse-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0392 - 4828 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper nave wing garden porch attic pantry closet branch wiring repaired but replacement nave-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0393 - 4840 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper chancel wing garden porch attic pantry closet branch wiring repaired but replacement chancel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0394 - 4852 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper transept wing garden porch attic pantry closet branch wiring repaired but replacement reredos-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0395 - 4864 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper narthex wing garden porch attic pantry closet branch wiring repaired but replacement narthex-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0396 - 4876 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper choir-loft wing garden porch attic pantry closet branch wiring repaired but replacement choir-loft-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0397 - 4888 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper sacristy wing garden porch attic pantry closet branch wiring repaired but replacement sacristy-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0398 - 4900 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper vestibule wing garden porch attic pantry closet branch wiring repaired but replacement vestibule-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0399 - 4912 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper baptistry wing garden porch attic pantry closet branch wiring repaired but replacement baptistry-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0400 - 4924 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper chapel wing garden porch attic pantry closet branch wiring repaired but replacement chapel-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0401 - 4936 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper vestry wing garden porch attic pantry closet branch wiring repaired but replacement vestry-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0402 - 4948 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper cloister wing garden porch attic pantry closet branch wiring repaired but replacement cloister-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0403 - 4960 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper ambulatory wing garden porch attic pantry closet branch wiring repaired but replacement ambulatory-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0404 - 4972 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tympanum wing garden porch attic pantry closet branch wiring repaired but replacement tympanum-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0405 - 4984 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper quatrefoil wing garden porch attic pantry closet branch wiring repaired but replacement quatrefoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0406 - 4996 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper cinquefoil wing garden porch attic pantry closet branch wiring repaired but replacement cinquefoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0407 - 5008 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper sexfoil wing garden porch attic pantry closet branch wiring repaired but replacement sexfoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0408 - 5020 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptfoil wing garden porch attic pantry closet branch wiring repaired but replacement heptfoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0409 - 5032 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octfoil wing garden porch attic pantry closet branch wiring repaired but replacement octfoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0410 - 5044 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0411 - 5056 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper decafoil wing garden porch attic pantry closet branch wiring repaired but replacement decafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0412 - 5068 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hendecafoil wing garden porch attic pantry closet branch wiring repaired but replacement hendecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0413 - 5080 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dodecafoil wing garden porch attic pantry closet branch wiring repaired but replacement dodecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0414 - 5092 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tridecafoil wing garden porch attic pantry closet branch wiring repaired but replacement tridecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0415 - 5104 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetradecafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetradecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0416 - 5116 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentadecafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentadecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0417 - 5128 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexadecafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexadecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0418 - 5140 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptadecafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptadecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0419 - 5152 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octadecafoil wing garden porch attic pantry closet branch wiring repaired but replacement octadecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0420 - 5164 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneadecafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneadecafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0421 - 5176 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper icosafoil wing garden porch attic pantry closet branch wiring repaired but replacement icosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0422 - 5188 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henicosafoil wing garden porch attic pantry closet branch wiring repaired but replacement henicosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0423 - 5200 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper docosafoil wing garden porch attic pantry closet branch wiring repaired but replacement docosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0424 - 5212 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tricosafoil wing garden porch attic pantry closet branch wiring repaired but replacement tricosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0425 - 5224 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracosafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0426 - 5236 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacosafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0427 - 5248 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacosafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0428 - 5260 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacosafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0429 - 5272 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacosafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0430 - 5284 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneacosafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneacosafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0431 - 5296 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement triacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0432 - 5308 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hentriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hentriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0433 - 5320 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dotriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement dotriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0434 - 5332 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0435 - 5344 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetratriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetratriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0436 - 5356 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentatriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentatriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0437 - 5368 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexatriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexatriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0438 - 5380 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptatriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptatriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0439 - 5392 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octatriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octatriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0440 - 5404 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneatriacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneatriacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0441 - 5416 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0442 - 5428 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement henatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0443 - 5440 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dotetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement dotetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0444 - 5452 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0445 - 5464 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetratetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetratetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0446 - 5476 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0447 - 5488 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0448 - 5500 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0449 - 5512 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0450 - 5524 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneatetracontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneatetracontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0451 - 5536 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0452 - 5548 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement henapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0453 - 5560 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dopentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement dopentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0454 - 5572 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tripentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tripentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0455 - 5584 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetrapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetrapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0456 - 5596 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0457 - 5608 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0458 - 5620 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0459 - 5632 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0460 - 5644 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneapentacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneapentacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0461 - 5656 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0462 - 5668 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henhexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement henhexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0463 - 5680 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dohexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement dohexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0464 - 5692 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper trihexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement trihexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0465 - 5704 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetrahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetrahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0466 - 5716 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0467 - 5728 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0468 - 5740 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0469 - 5752 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0470 - 5764 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneahexacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneahexacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0471 - 5776 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0472 - 5788 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement henaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0473 - 5800 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement doheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0474 - 5812 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement triheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0475 - 5824 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0476 - 5836 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0477 - 5848 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0478 - 5860 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0479 - 5872 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0480 - 5884 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaheptacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaheptacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0481 - 5896 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0482 - 5908 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement henoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0483 - 5920 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper duooctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement duooctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0484 - 5932 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper trioctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement trioctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0485 - 5944 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0486 - 5956 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0487 - 5968 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0488 - 5980 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0489 - 5992 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octaoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement octaoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0490 - 6004 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaoctacontafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaoctacontafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0491 - 6016 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper nonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement nonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0492 - 6028 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hennonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement hennonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0493 - 6040 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper duononagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement duononagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0494 - 6052 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triononagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement triononagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0495 - 6064 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetranonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetranonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0496 - 6076 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentanonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentanonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0497 - 6088 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexanonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexanonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0498 - 6100 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptanonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptanonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0499 - 6112 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octanonagintafoil wing garden porch attic pantry closet branch wiring repaired but replacement octanonagintafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0500 - 6124 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper centafoil wing garden porch attic pantry closet branch wiring repaired but replacement centafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0501 - 6136 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0502 - 6148 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement doacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0503 - 6160 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement triacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0504 - 6172 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0505 - 6184 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0506 - 6196 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0507 - 6208 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0508 - 6220 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0509 - 6232 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0510 - 6244 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper decacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement decacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0511 - 6256 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hendecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hendecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0512 - 6268 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dodecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dodecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0513 - 6280 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tridecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tridecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0514 - 6292 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetradecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetradecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0515 - 6304 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentadecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentadecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0516 - 6316 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexadecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexadecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0517 - 6328 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptadecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptadecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0518 - 6340 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octadecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octadecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0519 - 6352 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneadecacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneadecacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0520 - 6364 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper icosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement icosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0521 - 6376 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henicosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henicosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0522 - 6388 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doicosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement doicosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0523 - 6400 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tricosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tricosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0524 - 6412 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0525 - 6424 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0526 - 6436 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0527 - 6448 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0528 - 6460 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0529 - 6472 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneacosacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneacosacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0530 - 6484 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement triacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0531 - 6496 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hentriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hentriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0532 - 6508 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dotriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dotriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0533 - 6520 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0534 - 6532 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetratriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetratriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0535 - 6544 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentatriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentatriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0536 - 6556 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexatriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexatriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0537 - 6568 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptatriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptatriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0538 - 6580 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octatriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octatriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0539 - 6592 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneatriacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneatriacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0540 - 6604 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0541 - 6616 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hentetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hentetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0542 - 6628 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dotetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dotetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0543 - 6640 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0544 - 6652 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetratetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetratetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0545 - 6664 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentatetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentatetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0546 - 6676 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexatetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexatetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0547 - 6688 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptatetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptatetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0548 - 6700 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octatetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octatetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0549 - 6712 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneatetracontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneatetracontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0550 - 6724 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0551 - 6736 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henpentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henpentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0552 - 6748 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dopentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dopentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0553 - 6760 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tripentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tripentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0554 - 6772 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetrapentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetrapentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0555 - 6784 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentapentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentapentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0556 - 6796 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexapentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexapentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0557 - 6808 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptapentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptapentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0558 - 6820 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octopentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octopentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0559 - 6832 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneapentacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneapentacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0560 - 6844 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0561 - 6856 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henhexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henhexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0562 - 6868 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dohexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dohexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0563 - 6880 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper trihexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement trihexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0564 - 6892 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetrahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetrahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0565 - 6904 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0566 - 6916 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0567 - 6928 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0568 - 6940 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0569 - 6952 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneahexacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneahexacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0570 - 6964 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0571 - 6976 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0572 - 6988 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement doheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0573 - 7000 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement triheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0574 - 7012 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0575 - 7024 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0576 - 7036 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0577 - 7048 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0578 - 7060 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octoheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octoheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0579 - 7072 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaheptacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaheptacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0580 - 7084 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0581 - 7096 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0582 - 7108 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dooctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dooctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0583 - 7120 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper trioctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement trioctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0584 - 7132 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0585 - 7144 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0586 - 7156 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0587 - 7168 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0588 - 7180 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octooctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octooctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0589 - 7192 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaoctacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaoctacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0590 - 7204 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0591 - 7216 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0592 - 7228 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement doenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0593 - 7240 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper trienneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement trienneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0594 - 7252 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0595 - 7264 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0596 - 7276 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0597 - 7288 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0598 - 7300 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octoenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octoenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0599 - 7312 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaenneacontacentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaenneacontacentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0600 - 7324 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper ducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement ducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0601 - 7336 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0602 - 7348 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper doducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement doducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0603 - 7360 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement triducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0604 - 7372 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetraducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetraducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0605 - 7384 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0606 - 7396 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0607 - 7408 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0608 - 7420 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0609 - 7432 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0610 - 7444 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper decaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement decaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0611 - 7456 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hendecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hendecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0612 - 7468 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper dodecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement dodecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0613 - 7480 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tridecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tridecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0614 - 7492 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetradecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetradecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0615 - 7504 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentadecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentadecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0616 - 7516 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexadecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexadecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0617 - 7528 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptadecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptadecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0618 - 7540 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octadecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octadecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0619 - 7552 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneadecaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneadecaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0620 - 7564 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper icosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement icosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0621 - 7576 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henicosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henicosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0622 - 7588 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper docosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement docosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0623 - 7600 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tricosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tricosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0624 - 7612 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0625 - 7624 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentacosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentacosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0626 - 7636 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexacosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexacosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0627 - 7648 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptacosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptacosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0628 - 7660 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octacosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octacosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0629 - 7672 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneacosaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneacosaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0630 - 7684 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper triacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement triacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0631 - 7696 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper henatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement henatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0632 - 7708 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper duotriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement duotriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0633 - 7720 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0634 - 7732 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetratriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetratriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0635 - 7744 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper pentatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement pentatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0636 - 7756 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hexatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hexatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0637 - 7768 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper heptatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement heptatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0638 - 7780 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper octatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement octatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0639 - 7792 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper enneatriacontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement enneatriacontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0640 - 7804 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tetracontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tetracontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0641 - 7816 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper hentetracontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement hentetracontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0642 - 7828 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper duotetracontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement duotetracontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.

### ELZ-2026-0643 - 7840 S EWING AVE DALLAS TX 75216

- Priority: `medium`
- Contractor: `Cedars South Electric`
- Trigger: `2026-05-24` `rough_in` -> `partial`
- Failure reason: `incomplete_work`
- Recommended actions: `Complete remaining work, Schedule reinspection`
- Follow-up observed: `2026-05-25` `correction_followup` -> `pass`
- Evidence: Upper tritetracontaducentafoil wing garden porch attic pantry closet branch wiring repaired but replacement tritetracontaducentafoil-bracket lighting and cover trim remained incomplete before rough-in approval.
