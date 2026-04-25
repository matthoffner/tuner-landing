# Agent Journal

This is the human-readable journal for repeated `automoat` work loops.

Use short dated entries. Focus on decisions, changes, blockers, and next steps.

## 2026-04-25

- Bootstrapped project direction: vision, use cases, MVP framing, and generated landing page.
- Chosen current wedge: Dallas, Texas residential electrical permits and inspections.
- Added loop scaffolding plan; next step is to define the minimal ingestion schema, eval tasks, and business-first discovery artifacts.
- Added lock-aware loop scaffolding with `LOOP.md`, `NEXT_TASK.md`, `scripts/codex-loop.sh`, repo-local run logs, and a shared agent journal.
- Added `implementation-spec.md` covering the first executable slice: schema targets, eval task types, business-first artifacts, UI requirements, and implementation order.
- Added `HEARTBEAT.md` and `scripts/codex-session.sh` so a single command can hold the shared lock and keep making bounded progress for a fixed session window.
- Added `schema.md` for the Dallas electricians MVP: canonical output files, required entities, field-level contracts, normalization vocabularies, inclusion rules, join expectations, and concrete example permit and inspection records.
- Added `evals.md` for the Dallas electricians MVP: four task families, task row shape, split rules, baseline definitions, scoring outputs, and minimum success criteria.
- Added `discovery-artifacts.md` for the Dallas electricians MVP: business-first output files, intake contract, moat hypothesis schema, data gap plan, eval opportunity bridge, and discovery stop/go rules.
- Added `generated/discovery/dallas-electrician-sample-v1/` as a concrete Dallas business-first scaffold with sample JSON and Markdown outputs for business profile, workflow map, moat hypotheses, data gaps, eval opportunities, and a short operator summary.
- Added `generated/evals/dallas-electrician-sample-v1/` as a concrete dataset-first scaffold with sample `tasks.jsonl`, `task_splits.json`, and a short report showing one row per Dallas electricians eval family.
- Added `generated/fixtures/dallas-electrician-sequences-v1/` as a reusable synthetic fixture pack with normalized permit histories and pattern slices that cover all four Dallas electricians eval families.
- Added `scripts/generate_dallas_eval_artifacts.py` as a deterministic Dallas eval writer and regenerated `generated/evals/dallas-electrician-sample-v1/` from the reusable fixture pack.
- Added `scripts/generate_dallas_discovery_artifacts.py` plus `generated/intake/dallas-electrician-sample-v1/intake.json`, and regenerated the Dallas sample discovery scaffold from structured business intake instead of hand-authored output files.
- Tightened `evals.md` with a first-class `label_reviews.json` contract so reviewed failure labels and ranked next-action references are durable eval artifacts instead of implicit task metadata.
- Extended `scripts/generate_dallas_eval_artifacts.py` to emit `generated/evals/dallas-electrician-sample-v1/label_reviews.json` and updated the sample eval report to count reviewed label rows.
- Added `generated/normalized/dallas-electrician-sample-v1/` plus `scripts/generate_dallas_fixture_pack.py` so the Dallas fixture pack is now generated from row-shaped normalized permit, inspection, property, and contractor records instead of hand-maintained JSON.
