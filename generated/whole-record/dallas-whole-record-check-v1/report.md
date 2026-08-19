# Automoat Whole-Record Check

This release adds a backend-neutral verification pass over immutable, bounded Dallas case snapshots. A matching candidate earns a Coverage Receipt. A material action or evidence mismatch becomes an Evidence Conflict card for an operator.

Release date: `2026-08-19`

## Validation result

- Cases checked: `30`
- Coverage Receipts: `20`
- Evidence Conflict cards: `10`
- Planted retrieval omissions: `10`
- Planted omissions detected: `10`
- Unexpected conflicts: `0`

> This is a deterministic regression harness over versioned scaffold records, not a claim about production model accuracy.

## Case outcomes

| Case | Outcome | Queue item | Stable mismatch source IDs |
| --- | --- | --- | --- |
| `dallas-whole-record-case-01` | Coverage Receipt | `workflow-item:dallas:next-action:0001` | — |
| `dallas-whole-record-case-02` | Coverage Receipt | `workflow-item:dallas:next-action:0019` | — |
| `dallas-whole-record-case-03` | Evidence Conflict | `workflow-item:dallas:next-action:0037` | `source:inspection:elz-2026-0238:2026-05-22:rough_in` |
| `dallas-whole-record-case-04` | Coverage Receipt | `workflow-item:dallas:next-action:0056` | — |
| `dallas-whole-record-case-05` | Coverage Receipt | `workflow-item:dallas:next-action:0074` | — |
| `dallas-whole-record-case-06` | Evidence Conflict | `workflow-item:dallas:next-action:0093` | `source:inspection:elz-2026-0294:2026-05-22:rough_in` |
| `dallas-whole-record-case-07` | Coverage Receipt | `workflow-item:dallas:next-action:0111` | — |
| `dallas-whole-record-case-08` | Coverage Receipt | `workflow-item:dallas:next-action:0129` | — |
| `dallas-whole-record-case-09` | Evidence Conflict | `workflow-item:dallas:next-action:0148` | `source:inspection:elz-2026-0349:2026-05-24:rough_in` |
| `dallas-whole-record-case-10` | Coverage Receipt | `workflow-item:dallas:next-action:0166` | — |
| `dallas-whole-record-case-11` | Coverage Receipt | `workflow-item:dallas:next-action:0185` | — |
| `dallas-whole-record-case-12` | Evidence Conflict | `workflow-item:dallas:next-action:0203` | `source:inspection:elz-2026-0404:2026-05-24:rough_in` |
| `dallas-whole-record-case-13` | Coverage Receipt | `workflow-item:dallas:next-action:0221` | — |
| `dallas-whole-record-case-14` | Coverage Receipt | `workflow-item:dallas:next-action:0240` | — |
| `dallas-whole-record-case-15` | Evidence Conflict | `workflow-item:dallas:next-action:0258` | `source:inspection:elz-2026-0459:2026-05-24:rough_in` |
| `dallas-whole-record-case-16` | Coverage Receipt | `workflow-item:dallas:next-action:0277` | — |
| `dallas-whole-record-case-17` | Coverage Receipt | `workflow-item:dallas:next-action:0295` | — |
| `dallas-whole-record-case-18` | Evidence Conflict | `workflow-item:dallas:next-action:0314` | `source:inspection:elz-2026-0515:2026-05-24:rough_in` |
| `dallas-whole-record-case-19` | Coverage Receipt | `workflow-item:dallas:next-action:0332` | — |
| `dallas-whole-record-case-20` | Coverage Receipt | `workflow-item:dallas:next-action:0350` | — |
| `dallas-whole-record-case-21` | Evidence Conflict | `workflow-item:dallas:next-action:0369` | `source:inspection:elz-2026-0570:2026-05-24:rough_in` |
| `dallas-whole-record-case-22` | Coverage Receipt | `workflow-item:dallas:next-action:0387` | — |
| `dallas-whole-record-case-23` | Coverage Receipt | `workflow-item:dallas:next-action:0406` | — |
| `dallas-whole-record-case-24` | Evidence Conflict | `workflow-item:dallas:next-action:0424` | `source:inspection:elz-2026-0625:2026-05-24:rough_in` |
| `dallas-whole-record-case-25` | Coverage Receipt | `workflow-item:dallas:next-action:0442` | — |
| `dallas-whole-record-case-26` | Coverage Receipt | `workflow-item:dallas:next-action:0461` | — |
| `dallas-whole-record-case-27` | Evidence Conflict | `workflow-item:dallas:next-action:0479` | `source:inspection:elz-2026-0680:2026-05-24:rough_in` |
| `dallas-whole-record-case-28` | Coverage Receipt | `workflow-item:dallas:next-action:0498` | — |
| `dallas-whole-record-case-29` | Coverage Receipt | `workflow-item:dallas:next-action:0516` | — |
| `dallas-whole-record-case-30` | Evidence Conflict | `workflow-item:dallas:next-action:0535` | `source:inspection:elz-2026-0736:2026-05-24:rough_in` |

Each case file is content-addressed by its SHA-256 fingerprint. Conflict and receipt artifacts carry the existing queue item ID and an operator-correction payload template, but this check never writes to the correction ledger.
