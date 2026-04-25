# Implementation Spec

This document defines the first executable implementation slice for `automoat`.

It is intentionally narrow.

The goal is not to build a general platform first. The goal is to make the Dallas electricians MVP specific enough that repeated loop runs can implement it without re-deciding the product every time.

## Scope

Current implementation slice:

- locality: `Dallas, Texas`
- trade: `electricians`
- workflow: `residential electrical permits and inspections`
- mode support:
  - business-first discovery
  - dataset-first build/eval

## Primary User Questions

The first version should answer questions like:

- What usually happens next after this kind of residential electrical permit event?
- What kinds of electrical jobs are more likely to fail inspection?
- What corrections or next actions are most likely to improve approval odds?
- What local records could become a moat for a Dallas electrical business?

## Product Modes In This Slice

### 1. Business-First Discovery

Input:

- business description
- service area
- work types
- current workflow pain points
- available systems and records

Output:

- moat hypotheses
- data collection recommendations
- likely eval targets
- monetization or operational leverage ideas
- practical next-step plan

### 2. Dataset-First Build / Eval

Input:

- Dallas permit records
- Dallas inspection records
- optional violation data
- optional contractor and rules/guidance data

Output:

- normalized dataset
- candidate moat hypotheses
- eval suite
- benchmark comparison plan
- recommendation for next technical path

## Minimal Data Model

The first implementation should normalize all imported records into a small shared schema.

### Core Entities

#### `Project`

- `project_id`
- `name`
- `locality`
- `trade`
- `created_at`
- `source_summary`

#### `Property`

- `property_id`
- `normalized_address`
- `zip_code`
- `parcel_id` if available
- `property_type` if inferable

#### `Permit`

- `permit_id`
- `source_permit_number`
- `permit_type`
- `permit_subtype`
- `work_description`
- `status`
- `file_date`
- `issue_date`
- `final_date`
- `declared_valuation` if available
- `property_id`
- `contractor_id` if available

#### `Inspection`

- `inspection_id`
- `permit_id`
- `inspection_type`
- `inspection_date`
- `inspection_result`
- `result_normalized`
- `inspector_name` if available
- `notes_raw`
- `failure_reason_normalized` if inferable

#### `Contractor`

- `contractor_id`
- `name`
- `license_type`
- `registration_status`
- `city`

#### `RuleDocument`

- `document_id`
- `title`
- `document_type`
- `source_url`
- `text_content`
- `effective_date` if available

#### `MoatHypothesis`

- `hypothesis_id`
- `title`
- `description`
- `evidence_summary`
- `hypothesis_type`
- `confidence`

#### `EvalTask`

- `eval_id`
- `task_type`
- `task_prompt`
- `expected_output_shape`
- `scoring_method`
- `source_basis`

## Normalization Rules

The first implementation should normalize only what is needed for the MVP.

Required normalizations:

- addresses into one comparable text format
- permit/inspection date fields into ISO dates
- electrical-related records filtered into the working dataset
- inspection outcomes mapped into a small normalized result set:
  - `pass`
  - `fail`
  - `partial`
  - `cancelled`
  - `unknown`

- repeated permit and inspection labels mapped to a smaller internal vocabulary when practical

Do not over-design the normalization layer. The MVP only needs enough structure to support useful evals and hypotheses.

## First Ingestion Sources

The first implementation only needs enough ingestion to prove the loop.

Preferred source order:

1. Dallas permit reports
2. Dallas public online permit/inspection records
3. Dallas contractor registration records
4. Dallas electrical guidance or rules pages

The product should treat completeness as incremental. Partial but usable local signal is enough for the first proof.

## First Moat Hypothesis Types

The MVP should only generate a small set of hypothesis types:

- `approval-pattern`
- `failure-pattern`
- `correction-heuristic`
- `local-code-interpretation`
- `property-or-neighborhood-pattern`

Each hypothesis should include:

- short title
- one-paragraph explanation
- evidence pulled from the imported data
- confidence level
- recommendation for how to test it

## First Eval Task Set

The MVP should support 4 initial eval types.

### 1. Next Inspection Outcome Prediction

Question:

- given permit and inspection history so far, what is the likely next inspection outcome

Useful output shape:

- predicted outcome
- confidence
- brief explanation

### 2. Failure Reason Summarization

Question:

- given a permit and failed inspection history, what are the likely main issues

Useful output shape:

- concise summary
- likely issue categories
- supporting evidence

### 3. Recommended Next Action

Question:

- what should the electrician do next to improve approval odds

Useful output shape:

- ranked next actions
- rationale
- optional rule/reference pointers

### 4. Pattern Extraction

Question:

- what repeated patterns exist by permit type, area, or contractor segment

Useful output shape:

- top patterns
- frequency or support
- why they might matter

## First Scoring Strategy

The MVP does not need perfect evaluation science.

Use simple scoring methods first:

- exact or label match for normalized outcome tasks
- rubric-based scoring for summary and recommendation tasks
- reviewer-readable evidence alignment

The point is to make the comparison legible, not academically complete.

## Comparison Matrix

The first benchmark view should compare:

- generic model without local context
- generic model with retrieved local records
- moat-enhanced local approach using normalized history and local references

If a later run adds adaptation or fine-tune preparation, that can become a fourth comparison.

## Business-First Discovery Artifacts

When a user starts from the business, the first implementation should generate these artifacts:

### `Moat Map`

- likely moat candidates
- why they may matter
- what local data supports them

### `Data Collection Plan`

- what records to gather
- what fields matter most
- what historical depth is useful

### `Eval Plan`

- what business questions to test
- what success would look like
- what baseline to compare against

### `Action Memo`

- likely immediate next step
- likely medium-term moat build path
- whether the user is closer to a retrieval product, workflow tool, or adaptation/fine-tune path

## UI Requirements For This Slice

The first UI only needs these views:

- project setup
- source import status
- normalized dataset summary
- moat hypotheses
- eval definitions
- benchmark results
- recommendation summary

The UI should bias toward legibility over visual complexity.

## Implementation Order

The recommended order for repeated loop runs is:

1. finalize schema and normalization vocabulary
2. define evals in more detail
3. define business-first artifact templates
4. sketch file/module structure for implementation
5. build the first ingestion scaffolding
6. build the first eval scaffolding
7. update generated landing page as milestones land

## Done Definition For This Spec Phase

This phase is complete when the repo has:

- this implementation spec
- a separate schema document or equivalent refinement
- a separate evals document or equivalent refinement
- a separate discovery artifact document or equivalent refinement
- a clear next engineering slice that can be implemented without more product debate
