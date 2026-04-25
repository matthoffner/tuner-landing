# Discovery Artifacts

This document defines the first business-first discovery outputs for the Dallas electricians MVP.

It is the companion to [schema.md](./schema.md) and [evals.md](./evals.md). Those files define the dataset and benchmark contracts. This file defines what `automoat` should produce before or alongside dataset ingestion when the user starts from the business problem instead of raw records.

## Scope

These artifacts only apply to:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`

The first pass is for a small Dallas residential electrical business or operator, not a generic contractor platform.

## Discovery Goal

The business-first flow should answer one practical question:

`If I run an electrical business in Dallas, what local operating knowledge could become a moat, and what should I collect or test first?`

The output should be concrete enough that the next step is obvious:

- collect a specific dataset
- run a specific eval
- build a specific retrieval or rules layer
- reject a weak moat hypothesis early

## Required Output Artifacts

A future discovery run should materialize a compact set of durable files under a generated project directory such as `generated/discovery/<run_id>/`:

- `business-profile.json`
- `workflow-map.md`
- `moat-hypotheses.json`
- `data-gap-plan.md`
- `eval-opportunities.json`
- `discovery-summary.md`

The MVP does not need a large report generator. It needs a small set of inspectable artifacts that can feed directly into schema, eval, and implementation work.

## Artifact Contracts

### `business-profile.json`

This is the normalized snapshot of the business context.

Required fields:

- `business_name`
- `service_area`: must include `Dallas, Texas`
- `trade`: must be `electrical`
- `customer_focus`: such as `homeowner`, `residential builder`, or `mixed_residential`
- `job_types`: array of recurring work types
- `pain_points`: array of current workflow problems
- `systems_of_record`: array of current tools or files
- `available_data_assets`: array of known record sources

Optional fields:

- `crew_size`
- `license_context`
- `target_zip_codes`
- `after_hours_or_emergency_work`
- `permit_handling_style`

### `workflow-map.md`

This is the first human-readable map of how work moves today.

It should include:

- lead or job intake
- estimating or scoping
- permit filing
- work execution
- inspection scheduling
- failed inspection handling
- reinspection or closeout

For each step, capture:

- who does it
- what system or artifact is used
- where delays happen
- what judgment calls are repeated
- what data is produced and whether it is currently saved

### `moat-hypotheses.json`

This is the business-first equivalent of the model-facing hypothesis set.

Each hypothesis row should include:

- `hypothesis_id`
- `title`
- `hypothesis_type`
- `business_problem`
- `local_signal`
- `evidence_we_expect`
- `why_generic_models_miss_it`
- `value_if_true`
- `test_plan`
- `confidence`

Allowed `hypothesis_type` values:

- `approval-pattern`
- `failure-pattern`
- `correction-heuristic`
- `local-code-interpretation`
- `property-or-neighborhood-pattern`
- `operational-routing`

### `data-gap-plan.md`

This turns discovery into a collection plan instead of a vague recommendation list.

For each proposed data source, capture:

- source name
- why it matters
- whether it already exists internally, publicly, or not yet collected
- collection difficulty: `low`, `medium`, or `high`
- privacy sensitivity: `low`, `medium`, or `high`
- expected lift for eval quality: `low`, `medium`, or `high`
- recommended collection order

The first pass should prioritize source types like:

- permit logs
- inspection results and notes
- reinspection outcomes
- estimator or field correction notes
- office scheduling messages tied to failed inspections
- locally used checklists or code reminders

### `eval-opportunities.json`

This is the bridge from business discovery to [evals.md](./evals.md).

Each row should define:

- `opportunity_id`
- `task_type`
- `business_question`
- `minimum_required_data`
- `label_source`
- `expected_output`
- `business_value`
- `readiness`: `ready_now`, `needs_review`, or `blocked`

The first flow should only emit opportunities that map to the current Dallas electricians eval suite:

- `next_inspection_outcome`
- `failure_reason_classification`
- `recommended_next_action`
- `pattern_extraction`

### `discovery-summary.md`

This is the short operator-facing memo.

It should contain five sections:

1. business snapshot
2. likely moat candidates
3. best first eval to run
4. most important missing data
5. recommendation for the next 1 to 2 weeks

The summary should be short enough to read in a few minutes and specific enough to justify the next implementation move.

## Interview / Intake Contract

The first business-first flow should work from a compact intake, not a long consulting questionnaire.

Required intake questions:

- What kinds of residential electrical jobs do you do most often in Dallas?
- What part of permits or inspections slows you down the most?
- What records do you already keep after failed inspections or callbacks?
- Which neighborhoods, ZIP codes, or property types matter most to your business?
- What would be most valuable: fewer failed inspections, faster approvals, fewer truck rolls, or better estimating?

Optional intake questions:

- Do you already save inspector notes or text messages about corrections?
- Do you have repeat issue categories your crew already knows by memory?
- Do certain permit types or service upgrades create outsized friction?

## First Output Heuristics

The MVP should prefer discovery outputs that are operationally legible.

Good examples:

- “Service upgrade jobs in a narrow Dallas ZIP cluster appear to have repeat panel and grounding failure patterns.”
- “The business is losing time because failed inspection corrections live in crew memory and text threads instead of a reusable checklist.”
- “The best first eval is recommended next action because the business already has enough failed-to-passed inspection sequences to score it.”

Bad examples:

- “AI could optimize contractor workflows.”
- “There may be an opportunity to leverage proprietary data.”

## Stop / Go Rules

The business-first flow should recommend `go` only when at least one of these is true:

- there is a clear repetitive inspection failure or correction loop
- local records exist that could label at least one current eval task
- the business has a specific operating pain point tied to Dallas permitting or inspections

It should recommend `stop` or `narrow scope` when:

- the business does mostly non-residential work
- records are too sparse to support even one eval task
- the pain point is generic dispatching with no permitting or inspection signal
- the likely value comes from a general CRM workflow rather than Dallas-local knowledge

## Minimum Success Criteria

The discovery flow is successful when it produces all of the following:

- at least 2 plausible moat hypotheses
- at least 1 `ready_now` eval opportunity
- a prioritized list of missing data sources
- a short summary that clearly recommends the next build step

## Hand-Off To Implementation

If discovery succeeds, the next implementation-facing work should be one of:

1. scaffold the JSON and Markdown output files for a sample Dallas electrician profile
2. define example rows that connect `business-profile.json` to `moat-hypotheses.json`
3. create a thin local CLI or script that writes discovery artifacts from a structured input

That keeps the loop moving from concept documents toward executable local scaffolding without widening scope.
