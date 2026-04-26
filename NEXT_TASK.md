# Next Task

Current priority: make the Dallas electricians MVP executable, not just conceptual.

## Immediate Objectives

1. Keep the Dallas electricians MVP executable, not just well-described.
2. Prefer thin local writers that turn normalized rows into reusable Dallas artifacts.
3. Tighten reviewed-label and reference-action generation before widening scope.

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
- `generated/evals/dallas-electrician-sample-v1/label_reviews.json` now makes reviewed failure labels and next-action references explicit as a normalized-row artifact
- `evals.md` now defines the durable `label_reviews.json` contract so reviewed supervision stays stable as the Dallas sample widens toward imported records
- `scripts/generate_dallas_discovery_artifacts.py` now emits `generated/discovery/dallas-electrician-sample-v1/` deterministically from a structured Dallas business intake fixture
- `generated/intake/dallas-electrician-sample-v1/intake.json` now provides the first reusable Dallas business-first intake scaffold

Updated next best artifacts:

- a second or wider raw Dallas extract variant that exercises the importer with more inspection result diversity
- a normalization pass that brings `source_records.jsonl` and optional `rule_documents.jsonl` into the same repeatable imported-sample workflow
- a contract check or summary artifact that compares the synthetic and imported Dallas eval scaffolds without changing downstream shapes

Latest bounded improvement completed:

- `generated/normalized/dallas-electrician-sample-v1/` now provides row-shaped Dallas sample records
- `scripts/generate_dallas_fixture_pack.py` now emits the Dallas fixture pack deterministically from normalized permit and inspection rows
- `scripts/generate_dallas_label_reviews.py` now emits reviewed label rows directly from normalized Dallas permit and inspection records, and `scripts/generate_dallas_eval_artifacts.py` now uses that row-derived supervision path
- `scripts/generate_dallas_discovery_artifacts.py` now supports batch generation across multiple intake variants, and `generated/intake/dallas-electrician-south-dallas-v1/` plus `generated/discovery/dallas-electrician-south-dallas-v1/` exercise the Dallas business-first contract on a second realistic electrician profile
- `scripts/import_dallas_permit_extracts.py` now turns raw Dallas permit, inspection, and contractor CSV extracts into `projects.json`, `properties.jsonl`, `permits.jsonl`, `inspections.jsonl`, `contractors.jsonl`, and `source_records.jsonl` under `generated/normalized/dallas-electrician-import-sample-v1/`
- `scripts/generate_dallas_eval_artifacts.py` now accepts input and output arguments, and `generated/fixtures/dallas-electrician-import-sequences-v1/` plus `generated/evals/dallas-electrician-import-sample-v1/` prove the imported sample holds the same downstream Dallas fixture, review, and eval contracts

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
