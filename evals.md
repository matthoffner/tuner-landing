# Evals

This document defines the first evaluation contract for the Dallas electricians MVP.

It is intentionally narrow. The goal is to make the first benchmark loop executable against the schema in [schema.md](./schema.md), not to create a full research framework.

## Scope

These evals only apply to:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`

The eval suite should only use records that satisfy the schema inclusion rules and controlled vocabularies.

## Eval Goal

The first eval suite should answer one practical question:

`Does structured Dallas residential electrical history improve task performance over a generic baseline on narrow contractor-facing tasks?`

That means the suite should prefer:

- tasks grounded in permit and inspection history
- labels that can be derived from normalized fields
- scoring that is cheap to run locally
- outputs that map to a real business action

## Comparison Matrix

Every task should be runnable against the same three system modes when possible:

1. `baseline`
   - generic model or heuristic
   - no Dallas local retrieval
   - no structured local history features
2. `retrieval`
   - generic model with retrieved local records or rule snippets
   - no task-specific adaptation
3. `moat`
   - local structured-history approach using normalized permit and inspection records
   - may combine retrieval with explicit local features, pattern summaries, or deterministic context assembly

The MVP does not require fine-tuning in the first pass. The `moat` condition only needs to prove that structured local history adds measurable value.

## Required Eval Artifacts

A future eval scaffold should be able to materialize these files under a generated eval directory:

- `tasks.jsonl`
- `task_splits.json`
- `label_reviews.json`
- `predictions/<run_id>.jsonl`
- `scores/<run_id>.json`
- `reports/<run_id>.md`

For reusable synthetic examples that match this contract, use:

- `generated/fixtures/dallas-electrician-sequences-v1/permit-inspection-sequences.json`
- `generated/fixtures/dallas-electrician-sequences-v1/pattern-slices.json`

## Core Task Set

The first suite should contain exactly four task families.

### 1. Next Inspection Outcome

Question:

- given the permit row and prior inspection history so far, what is the likely next inspection result

Use when:

- a permit has at least one inspection
- a later inspection result is known

Input contract:

- `permit`
- `property`
- ordered prior `inspection` rows before the target event
- optional retrieved `rule_document` excerpts

Target label:

- `result_normalized`

Allowed labels:

- `pass`
- `fail`
- `partial`
- `cancelled`
- `not_ready`
- `unknown`

Primary metric:

- accuracy on `result_normalized`

Secondary metrics:

- macro F1
- fail-vs-nonfail accuracy

Why it matters:

- this is the cleanest test of whether local history improves practical inspection forecasting

### 2. Failure Reason Classification

Question:

- given a failed inspection and available notes, what is the most likely normalized failure reason

Use when:

- `result_normalized = fail`
- `notes_raw` exists or another source note exists
- `failure_reason_normalized` is available as a label or can be reviewed into one

Input contract:

- `permit`
- target `inspection`
- prior `inspection` history for the same permit
- optional retrieved `rule_document` excerpts

Target label:

- `failure_reason_normalized`

Allowed labels:

- `missing_permit_or_scope_mismatch`
- `incomplete_work`
- `panel_or_service_issue`
- `wiring_or_device_issue`
- `grounding_or_bonding_issue`
- `labeling_or_documentation_issue`
- `access_or_scheduling_issue`
- `other`
- `unknown`

Primary metric:

- macro F1 on `failure_reason_normalized`

Secondary metrics:

- top-1 accuracy
- grouped accuracy on:
  - documentation and scheduling issues
  - electrical workmanship issues

Why it matters:

- this is the first test of whether the local dataset can turn noisy notes into actionable structured categories

### 3. Recommended Next Action

Question:

- what should the electrician do next to improve approval odds after the current permit or inspection state

Use when:

- a permit has at least one failed, partial, or not-ready inspection
- a follow-up inspection or final outcome exists

Input contract:

- `permit`
- ordered inspection history up to the decision point
- optional contractor context
- optional retrieved rules or FAQ excerpts

Expected output shape:

- ranked list of 1 to 3 next actions
- short rationale for each

Reference label shape:

- `reference_actions`: reviewed action list derived from the subsequent successful path when available

Action vocabulary for the first pass:

- `schedule_reinspection`
- `complete_remaining_work`
- `correct_panel_or_service`
- `correct_grounding_or_bonding`
- `correct_wiring_or_devices`
- `add_labels_or_documentation`
- `verify_scope_and_permit`
- `ensure_site_access`
- `consult_rule_or_inspector_guidance`

Primary metric:

- top-3 action hit rate against `reference_actions`

Secondary metrics:

- top-1 hit rate
- exact match on first ranked action when the reference set has one dominant action

Why it matters:

- this is the most business-legible task because it maps directly to what a Dallas electrician would do next

### 4. Pattern Extraction

Question:

- what repeated pattern is present in this local slice of permits and inspections

Use when:

- the input is a grouped subset such as:
  - one permit type
  - one ZIP code
  - one contractor segment
  - one inspection type

Input contract:

- grouped normalized records
- support counts
- optional rule snippets for context

Expected output shape:

- `pattern_summary`
- `support_count`
- `why_it_matters`

Reference label shape:

- reviewed pattern memo for the slice

Primary metric:

- rubric score from 1 to 5 on factual grounding, usefulness, and non-generic locality

Secondary metrics:

- support-count agreement within acceptable tolerance
- citation coverage when the system cites rows or rules

Why it matters:

- this is the business-first bridge task that turns raw records into moat hypotheses and sales-language evidence

## Task Row Shape

Each row in `tasks.jsonl` should follow this minimum contract:

```json
{
  "task_id": "eval:dallas:next-outcome:0001",
  "task_type": "next_inspection_outcome",
  "split": "dev",
  "input": {
    "permit_id": "permit:dallas:2026-0001234",
    "property_id": "property:214-main-st-dallas-tx",
    "inspection_ids_context": [
      "inspection:dallas:2026-0001234:2026-02-12:rough_in"
    ],
    "rule_document_ids": [
      "rule:dallas:electric-service-guide-2025"
    ]
  },
  "target": {
    "result_normalized": "fail"
  },
  "metadata": {
    "permit_type_normalized": "electrical_remodel",
    "inspection_type_normalized": "final",
    "zip_code": "75214"
  }
}
```

## Split Strategy

The MVP does not need a complex experimental design.

Use this split order:

1. `dev`
   - for prompt shaping, deterministic pipeline shaping, and schema sanity checks
2. `test`
   - held back until the task contract stabilizes

Recommended starting ratio:

- `80% dev`
- `20% test`

Split rules:

- keep all rows from the same `permit_id` in the same split
- avoid mixing earlier and later events from one permit across splits
- if contractor history is dense, try not to let one contractor dominate both splits

## Labeling Rules

Prefer labels already available from normalized schema fields.

For reviewed labels:

- keep a small reviewer note beside any manually assigned `failure_reason_normalized`
- prefer one label over multilabel in the first pass
- if the note does not justify a confident label, use `unknown`

For next-action references:

- derive the reference action from the next successful step when obvious
- if multiple actions were clearly required, include up to 3 ranked actions

### Row-Backed Derivation

When a sample or real Dallas dataset is already normalized:

- derive `reference_actions` from the failed or partial inspection plus the first later corrective pass when available
- map `failure_reason_normalized` into the current action vocabulary before appending `schedule_reinspection`
- keep the derivation deterministic so regenerated eval artifacts do not drift across runs

## Label Review Artifact

`label_reviews.json` is the durable bridge between normalized rows and reviewed eval labels.

It should contain one row per reviewed label decision for the current eval dataset.

Required fields per row:

- `review_id`
- `task_id`
- `task_type`
- `permit_id`
- `inspection_id` when the target is tied to one inspection event
- `review_status`: `fixture_generated`, `reviewed`, or `needs_review`
- `label_source`: `schema_field`, `fixture_sequence`, or `human_review`
- `label_payload`: reviewed label object such as `failure_reason_normalized` or `reference_actions`
- `evidence`: short supporting snippets pulled from normalized notes, later outcomes, or grouped counts
- `reviewer_note`

This artifact should be emitted even for synthetic fixture-backed rows so the implementation path stays consistent when real Dallas records replace the fixtures.

### Failure Reason Review Rules

For `failure_reason_classification` rows:

- emit one label review row per task
- include the failed inspection as `inspection_id`
- copy the reviewed `failure_reason_normalized` into `label_payload`
- include `notes_raw` or another short justification excerpt in `evidence`
- mark synthetic labels as `fixture_generated`
- mark uncertain real-world labels as `needs_review` instead of guessing

### Next Action Reference Rules

For `recommended_next_action` rows:

- emit one label review row per task
- use the latest failing, partial, or not-ready inspection in context as `inspection_id`
- store ranked `reference_actions` in `label_payload`
- include the later passing or successful follow-up event summary in `evidence`
- keep the ranked action list short and practical
- if the later path does not clearly imply what changed, mark the row `needs_review`
- do not invent an action that is not supported by later history or rule text

For pattern extraction:

- require a minimum support count before creating a reviewed pattern memo
- reject generic summaries that would be true in any city

## Baseline Definitions

The MVP should start with simple baselines.

### `baseline`

- generic prompt only
- no local retrieved records
- no explicit use of structured Dallas history beyond the row shown in the prompt

### `retrieval`

- generic prompt
- retrieved Dallas permit, inspection, FAQ, or rule snippets
- no engineered aggregation over the normalized history beyond retrieval assembly

### `moat`

- deterministic local context built from normalized schema rows
- may include:
  - counts of prior failures
  - latest failure categories
  - permit-type history for similar jobs
  - ZIP-level or neighborhood aggregates
  - retrieved rule or FAQ excerpts

The `moat` system should stay interpretable. If a feature cannot be explained to a user, it is probably out of scope for this first pass.

## Scoring Output Contract

Each score report should include:

- task counts by split
- metric values by system mode
- error slices by:
  - permit type
  - inspection type
  - ZIP code when sample size is large enough
- 5 to 10 concrete misses worth reviewing
- recommendation:
  - `retrieval_enough`
  - `structured_moat_helpful`
  - `needs_more_data`
  - `task_not_viable`

## Minimum Viable Success Criteria

The first eval loop is useful if all of the following are true:

- the task rows can be generated from the schema without re-deciding field meaning
- at least 2 task families have enough examples to score
- score reports clearly separate `baseline`, `retrieval`, and `moat`
- the `moat` condition beats `baseline` on at least 1 practical task
- errors are legible enough to inform the next artifact or ingestion improvement

## Stop Conditions

Stop expanding the eval suite if:

- labels depend on too much human interpretation
- the local data is too sparse to support the task
- the task cannot produce a business-legible recommendation
- the task only shows generic model ability rather than Dallas-specific lift

If that happens, tighten the task set instead of broadening scope.

## Done Definition

The eval phase is ready for implementation when:

- task families are fixed
- row shapes are explicit
- split rules are explicit
- baseline conditions are explicit
- scoring outputs and success criteria are explicit
- a future scaffold could generate `tasks.jsonl` and score reports without product re-interpretation

The current repo now also has a reusable synthetic fixture pack that covers all four task families, so future writers can validate row generation against a shared Dallas-specific example set before touching real source data.

The next step for eval execution is to preserve reviewed label decisions as first-class generated artifacts instead of leaving failure-reason and next-action supervision implicit inside task rows.
