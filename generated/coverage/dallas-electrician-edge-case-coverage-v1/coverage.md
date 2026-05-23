# Dallas Electrician Edge-Case Coverage V1

This artifact makes edge-case support explicit across the Dallas electrician scaffolds. Repeated support means at least two distinct permits back the state, label, slice, or action group.

## Summary

- Latest dataset: `dallas-electrician-import-sample-v2`
- Repeated support threshold: `2` permits
- Result states with repeated support: `6` of `6`
- Failure reasons with repeated support: `5` of `5`
- Pattern slices with repeated support: `5` of `5`
- Next-action groups with repeated support: `6` of `6`
- Recommended next step: All current latest-import edge-case sections have repeated support; keep this report current as imported Dallas data widens.

## Synthetic sample v1

- Dataset id: `dallas-electrician-sample-v1`
- Result states: `2` repeated of `3`
- Failure reasons: `1` repeated of `2`
- Pattern slices: `0` repeated of `3`
- Next-action groups: `1` repeated of `2`

### Result States

| state | rows | permits | repeated |
| --- | --- | --- | --- |
| fail | 2 | 2 | true |
| partial | 1 | 1 | false |
| pass | 6 | 3 | true |

### Failure Reasons

| reason | rows | permits | repeated |
| --- | --- | --- | --- |
| grounding_or_bonding_issue | 1 | 1 | false |
| incomplete_work | 2 | 2 | true |

### Pattern Slices

| slice | permits | inspections | repeated |
| --- | --- | --- | --- |
| slice:dallas:remodel:final:75214 | 1 | 1 | false |
| slice:dallas:repair:final:75205 | 1 | 1 | false |
| slice:dallas:service-upgrade:service-release:75208 | 1 | 1 | false |

### Next-Action Groups

| actions | rows | permits | repeated |
| --- | --- | --- | --- |
| complete_remaining_work\|schedule_reinspection | 2 | 2 | true |
| correct_grounding_or_bonding\|add_labels_or_documentation\|schedule_reinspection | 1 | 1 | false |

## Imported sample v1

- Dataset id: `dallas-electrician-import-sample-v1`
- Result states: `2` repeated of `3`
- Failure reasons: `1` repeated of `3`
- Pattern slices: `0` repeated of `4`
- Next-action groups: `1` repeated of `3`

### Result States

| state | rows | permits | repeated |
| --- | --- | --- | --- |
| fail | 3 | 3 | true |
| partial | 1 | 1 | false |
| pass | 7 | 4 | true |

### Failure Reasons

| reason | rows | permits | repeated |
| --- | --- | --- | --- |
| grounding_or_bonding_issue | 1 | 1 | false |
| panel_or_service_issue | 1 | 1 | false |
| wiring_or_device_issue | 2 | 2 | true |

### Pattern Slices

| slice | permits | inspections | repeated |
| --- | --- | --- | --- |
| slice:dallas:new:rough-in:75214 | 1 | 1 | false |
| slice:dallas:remodel:final:75214 | 1 | 1 | false |
| slice:dallas:repair:final:75217 | 1 | 1 | false |
| slice:dallas:service-upgrade:service-release:75211 | 1 | 1 | false |

### Next-Action Groups

| actions | rows | permits | repeated |
| --- | --- | --- | --- |
| correct_grounding_or_bonding\|add_labels_or_documentation\|schedule_reinspection | 1 | 1 | false |
| correct_panel_or_service\|add_labels_or_documentation\|ensure_site_access\|schedule_reinspection | 1 | 1 | false |
| correct_wiring_or_devices\|schedule_reinspection | 2 | 2 | true |

## Imported sample v2

- Dataset id: `dallas-electrician-import-sample-v2`
- Result states: `6` repeated of `6`
- Failure reasons: `5` repeated of `5`
- Pattern slices: `5` repeated of `5`
- Next-action groups: `6` repeated of `6`

### Result States

| state | rows | permits | repeated |
| --- | --- | --- | --- |
| cancelled | 2 | 2 | true |
| fail | 6 | 6 | true |
| not_ready | 4 | 4 | true |
| partial | 19 | 19 | true |
| pass | 37 | 29 | true |
| unknown | 2 | 2 | true |

### Failure Reasons

| reason | rows | permits | repeated |
| --- | --- | --- | --- |
| access_or_scheduling_issue | 4 | 4 | true |
| grounding_or_bonding_issue | 4 | 2 | true |
| incomplete_work | 7 | 7 | true |
| panel_or_service_issue | 2 | 2 | true |
| wiring_or_device_issue | 12 | 12 | true |

### Pattern Slices

| slice | permits | inspections | repeated |
| --- | --- | --- | --- |
| slice:dallas:new:correction-followup:75214 | 2 | 2 | true |
| slice:dallas:new:rough-in:75214 | 2 | 2 | true |
| slice:dallas:remodel:final:75208 | 2 | 2 | true |
| slice:dallas:repair:rough-in:75216 | 17 | 17 | true |
| slice:dallas:service-upgrade:service-release:75228 | 2 | 2 | true |

### Next-Action Groups

| actions | rows | permits | repeated |
| --- | --- | --- | --- |
| complete_remaining_work\|schedule_reinspection | 7 | 7 | true |
| correct_grounding_or_bonding\|add_labels_or_documentation | 2 | 2 | true |
| correct_grounding_or_bonding\|add_labels_or_documentation\|schedule_reinspection | 2 | 2 | true |
| correct_panel_or_service\|add_labels_or_documentation\|schedule_reinspection | 2 | 2 | true |
| correct_wiring_or_devices\|schedule_reinspection | 12 | 12 | true |
| ensure_site_access\|schedule_reinspection | 4 | 4 | true |
