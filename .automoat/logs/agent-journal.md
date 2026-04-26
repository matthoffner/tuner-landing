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
- Added `scripts/generate_dallas_label_reviews.py` and finished the handoff from fixture-backed supervision to row-derived reviewed labels, so `label_reviews.json` is now emitted directly from normalized Dallas permit and inspection rows and consumed by the eval scaffold.
- Added `scripts/codex-day.sh` and `scripts/codex-publish.sh`, plus session/loop upgrades for stale-lock recovery, automatic landing-page sync, automatic publish to `main`, and a dedicated reporter pass during unattended runs.

## 2026-04-26

- Extended `scripts/generate_dallas_discovery_artifacts.py` with batch mode so every intake variant under `generated/intake/` can emit a matching discovery run under `generated/discovery/` without hand-editing output fixtures.
- Added a second Dallas business-first intake at `generated/intake/dallas-electrician-south-dallas-v1/intake.json` focused on older-home South Dallas and Oak Cliff electrical work.
- Generated `generated/discovery/dallas-electrician-south-dallas-v1/` to prove the same Dallas discovery contract works across multiple realistic electrician profiles.
- Narrowed the next implementation gap to widening the normalized Dallas sample toward imported records while preserving the now-stable multi-intake discovery and downstream eval contracts.
- Rewrote `generated/landing.html` into an evidence-based landing page and changelog that reflects the repo's real state, current Dallas MVP scope, concrete generated artifacts, and explicit unbuilt gaps without inventing progress.
- Added `scripts/import_dallas_permit_extracts.py` plus `generated/raw/dallas-electrician-import-sample-v1/` so a small Dallas permit, inspection, and contractor CSV extract can normalize into the repo's stable row contracts.
- Generated `generated/normalized/dallas-electrician-import-sample-v1/`, `generated/fixtures/dallas-electrician-import-sequences-v1/`, and `generated/evals/dallas-electrician-import-sample-v1/` to prove the imported sample keeps the same downstream Dallas fixture, reviewed-label, and eval shapes.
- Parameterized `scripts/generate_dallas_eval_artifacts.py` so imported or widened normalized Dallas datasets can emit their own eval scaffolds without rewriting the script.
- Refreshed `generated/landing.html` again so the public-facing status page now matches the current imported-sample counts, discovery variant count, and remaining gap without stale claims about missing import paths.
