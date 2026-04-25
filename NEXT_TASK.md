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

- a thin local writer that can turn real Dallas business intake variants into multiple generated discovery runs without hand-editing fixtures
- a sample normalized Dallas dataset directory that can widen from synthetic rows to imported Dallas records without changing downstream contracts
- a wider normalized Dallas sample that can preserve the same eval and review contracts while moving from synthetic rows toward imported records

Latest bounded improvement completed:

- `generated/normalized/dallas-electrician-sample-v1/` now provides row-shaped Dallas sample records
- `scripts/generate_dallas_fixture_pack.py` now emits the Dallas fixture pack deterministically from normalized permit and inspection rows
- `scripts/generate_dallas_label_reviews.py` now emits reviewed label rows directly from normalized Dallas permit and inspection records, and `scripts/generate_dallas_eval_artifacts.py` now uses that row-derived supervision path

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
