# Next Task

Current priority: make the Dallas electricians MVP executable, not just conceptual.

## Immediate Objectives

1. Define the minimal ingestion schema for Dallas residential electrical permits and inspections.
2. Define the first eval task set.
3. Define the business-first discovery artifacts for a Dallas electrical business user.

## Good Outputs

Useful artifacts for the next few runs:

- `implementation-spec.md`
- `schema.md`
- `evals.md`
- `discovery-artifacts.md`
- improvements to `generated/landing.html`

## Current Status

- `implementation-spec.md` now exists
- `schema.md` now exists
- `evals.md` now exists
- `discovery-artifacts.md` now exists

Next best artifacts:

- thin local writers that can emit the discovery artifact contracts from structured input
- sample dataset-first task rows grounded in the schema and eval contracts
- reusable fixture-pack writers and row generators grounded in the Dallas sequence examples

Recent progress:

- `generated/discovery/dallas-electrician-sample-v1/` now demonstrates the business-first output contracts
- `generated/evals/dallas-electrician-sample-v1/` now demonstrates the dataset-first task row and split contracts
- `generated/fixtures/dallas-electrician-sequences-v1/` now provides reusable Dallas permit and inspection sequences plus pattern slices for all current eval families
- `scripts/generate_dallas_eval_artifacts.py` now emits `generated/evals/dallas-electrician-sample-v1/` deterministically from the Dallas fixture pack

Updated next best artifacts:

- a thin local writer that emits `generated/discovery/...` artifacts from structured intake
- a thin local writer that emits the Dallas fixture pack shape directly from normalized permit and inspection rows
- a thin local writer that can emit the new reusable discovery artifact shape from structured Dallas intake

## Constraints

- Stay focused on Dallas, Texas.
- Stay focused on electricians.
- Prefer clarity over breadth.
- Prefer documents and simple scaffolding before heavier code.

## Avoid

- expanding to many cities
- expanding to many trades
- building broad ingestion infrastructure before the schema is defined
- generic AI platform ideas that are no longer tied to the MVP

## If Blocked

If implementation details are blocked, do the highest-value adjacent work:

- tighten the schema
- tighten eval definitions
- refine business-first outputs
- improve the landing page and project docs

Do not idle.
