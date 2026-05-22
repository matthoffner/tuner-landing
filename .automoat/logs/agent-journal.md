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

- Widened `generated/raw/dallas-electrician-import-sample-v2/` with three more Dallas electrician permit sequences so the imported fixture now repeats the existing `75208` remodel-final, `75214` new-install rough-in/correction-followup, and `75216` repair rough-in slices instead of leaving them as one-off examples.
- Regenerated `generated/normalized/dallas-electrician-import-sample-v2/`, `generated/fixtures/dallas-electrician-import-sequences-v2/`, and `generated/evals/dallas-electrician-import-sample-v2/`; imported `v2` now carries `8` permits, `22` inspections, `31` eval tasks, `13` reviewed label rows, and `38` source-lineage rows.
- Extended `scripts/generate_dallas_contract_summary.py` to report repeated pattern-slice and repeated next-action support directly, then regenerated `generated/contracts/dallas-electrician-contract-summary-v1/`; the summary now passes `10/10` checks and shows imported `v2` with `4` repeated pattern slices and `3` repeated next-action groups.
- Refreshed `NEXT_TASK.md` and `generated/landing.html` so the repo now points at the narrower remaining gap: repeated imported support for service-release and access-related edge cases rather than generic pattern-repeat scarcity.
- Re-read `generated/landing.html`, `NEXT_TASK.md`, `.automoat/logs/agent-journal.md`, `.pixelbox/handoff.md`, `README.md`, and the freshest generated artifacts before updating the landing page again.
- Refreshed `generated/landing.html` so it now acts as a higher-signal status page and changelog for the real current repo state: broad framing intact, contract summary centered, stale counts removed, imported `v2` corrected to `27` source records and `3` rule documents, and the remaining gap kept focused on repeat support for recurring patterns.
- Extended `scripts/import_dallas_permit_extracts.py` so imported Dallas samples can optionally ingest `rule_documents.csv`, emitting `rule_documents.jsonl` plus matching `rule_document` source-lineage rows in `source_records.jsonl`.
- Added Dallas electrical rule fixtures at `generated/raw/dallas-electrician-import-sample-v1/rule_documents.csv` and `generated/raw/dallas-electrician-import-sample-v2/rule_documents.csv`, then regenerated the imported normalized outputs so `v1` now carries `2` rule documents and `21` source records while `v2` carries `3` rule documents and `27` source records.
- Regenerated `generated/contracts/dallas-electrician-contract-summary-v1/summary.json` and `summary.md`; the contract summary now checks the imported rules workflow explicitly and passes `9/9` checks across the synthetic and imported Dallas scaffolds.
- Updated `NEXT_TASK.md` and `generated/landing.html` to retire the old normalization gap and point the repo at the next real Dallas MVP need: broader imported fixture support for repeated pattern slices and reviewed next-action examples.
- Reworked `generated/landing.html` into a higher-signal product/status page centered on the latest contract summary, exact Dallas scaffold counts, intentionally broad product framing, and the current normalization gap without claiming unbuilt progress.
- Added `scripts/generate_dallas_contract_summary.py` and generated `generated/contracts/dallas-electrician-contract-summary-v1/summary.json` plus `summary.md` to compare the synthetic Dallas scaffold against imported `v1` and `v2`.
- Made the contract summary validate stable normalized file presence, stable eval task families, stable label-review fields, and monotonic widening of permits, inspections, tasks, and source-lineage counts across imported samples.
- Updated `NEXT_TASK.md` and `generated/landing.html` so the repo no longer claims the cross-sample check is missing; the remaining Dallas MVP gap is now the repeatable normalization path for `source_records.jsonl` and optional `rule_documents.jsonl`.
- Extended `scripts/generate_dallas_discovery_artifacts.py` with batch mode so every intake variant under `generated/intake/` can emit a matching discovery run under `generated/discovery/` without hand-editing output fixtures.
- Added a second Dallas business-first intake at `generated/intake/dallas-electrician-south-dallas-v1/intake.json` focused on older-home South Dallas and Oak Cliff electrical work.
- Generated `generated/discovery/dallas-electrician-south-dallas-v1/` to prove the same Dallas discovery contract works across multiple realistic electrician profiles.
- Narrowed the next implementation gap to widening the normalized Dallas sample toward imported records while preserving the now-stable multi-intake discovery and downstream eval contracts.
- Rewrote `generated/landing.html` into an evidence-based landing page and changelog that reflects the repo's real state, current Dallas MVP scope, concrete generated artifacts, and explicit unbuilt gaps without inventing progress.
- Added `scripts/import_dallas_permit_extracts.py` plus `generated/raw/dallas-electrician-import-sample-v1/` so a small Dallas permit, inspection, and contractor CSV extract can normalize into the repo's stable row contracts.
- Generated `generated/normalized/dallas-electrician-import-sample-v1/`, `generated/fixtures/dallas-electrician-import-sequences-v1/`, and `generated/evals/dallas-electrician-import-sample-v1/` to prove the imported sample keeps the same downstream Dallas fixture, reviewed-label, and eval shapes.
- Parameterized `scripts/generate_dallas_eval_artifacts.py` so imported or widened normalized Dallas datasets can emit their own eval scaffolds without rewriting the script.
- Refreshed `generated/landing.html` again so the public-facing status page now matches the current imported-sample counts, discovery variant count, and remaining gap without stale claims about missing import paths.
- Added `generated/raw/dallas-electrician-import-sample-v2/` as a wider Dallas electrician import fixture with `pass`, `fail`, `partial`, `cancelled`, `not_ready`, and `unknown` inspection outcomes.
- Generated `generated/normalized/dallas-electrician-import-sample-v2/`, `generated/fixtures/dallas-electrician-import-sequences-v2/`, and `generated/evals/dallas-electrician-import-sample-v2/` to prove the importer and downstream Dallas contracts still hold across the broader result mix.
- Updated `NEXT_TASK.md` and `generated/landing.html` so the repo now points at the next real gap: cross-sample contract checks and a repeatable normalization path for source lineage plus optional rule documents.
- Refreshed `generated/landing.html` once more against the current repo artifacts so the page now reports three normalized dataset paths, three eval scaffolds, `52` total generated tasks, `19` reviewed label rows, and the imported `v2` sample as the latest concrete build signal.
- The 24-hour supervisor produced those artifacts, then exposed a bug in `scripts/codex-session.sh`: failed iterations were breaking the inner loop but still returning `0`, which let `scripts/codex-day.sh` spin through broken short cycles instead of stopping cleanly.

## 2026-05-10

- Widened `generated/raw/dallas-electrician-import-sample-v2/` with one more Dallas service-upgrade sequence and one more access-blocked remodel-final sequence so imported `v2` now repeats service-release and access-heavy next-action paths instead of leaving them as one-offs.
- Tightened `scripts/import_dallas_permit_extracts.py`, `scripts/generate_dallas_fixture_pack.py`, and `scripts/generate_dallas_label_reviews.py` so access-related labels no longer come from accidental `panel schedule` matches and access-blocked service-release rows normalize consistently.
- Regenerated `generated/normalized/dallas-electrician-import-sample-v2/`, `generated/fixtures/dallas-electrician-import-sequences-v2/`, `generated/evals/dallas-electrician-import-sample-v2/`, and `generated/contracts/dallas-electrician-contract-summary-v1/`; imported `v2` now carries `10` permits, `28` inspections, `37` eval tasks, `15` reviewed label rows, `46` source-lineage rows, and `4` repeated next-action groups while the contract stays at `10/10`.
- Refreshed `NEXT_TASK.md` and `generated/landing.html` so the repo now points at the narrower remaining gap: repeated cancelled, unknown, and panel-service examples rather than missing service-release or access support.

## 2026-05-17

- Widened `generated/raw/dallas-electrician-import-sample-v2/` with three more Dallas electrician permit sequences: one repeated cancelled/unknown remodel-final path and two repeated panel/service release failures.
- Regenerated `generated/normalized/dallas-electrician-import-sample-v2/`, `generated/fixtures/dallas-electrician-import-sequences-v2/`, `generated/evals/dallas-electrician-import-sample-v2/`, and `generated/contracts/dallas-electrician-contract-summary-v1/`; imported `v2` now carries `13` permits, `38` inspections, `49` eval tasks, `19` reviewed label rows, and `59` source-lineage rows.
- Confirmed the shared contract remains at `10/10`; imported `v2` now reports `5` repeated pattern slices and `5` repeated next-action groups, including repeated `correct_panel_or_service|add_labels_or_documentation|schedule_reinspection` support.
- Refreshed `NEXT_TASK.md` and `generated/landing.html` so the next real artifact is an explicit edge-case coverage report rather than more hidden fixture widening.
- Added `scripts/generate_dallas_edge_case_coverage.py` and generated `generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.json` plus `coverage.md`.
- The coverage report shows imported `v2` has repeated support for `6/6` result states, `4/5` failure reasons, `5/5` pattern slices, and `5/6` next-action groups; the remaining thin support is `incomplete_work` and `complete_remaining_work|schedule_reinspection`.
- Updated `README.md`, `NEXT_TASK.md`, `generated/landing.html`, and `index.html` so the next real step is promoting coverage expectations into contract checks rather than adding another hidden fixture expansion.
- Promoted the main edge-case coverage expectations into `scripts/generate_dallas_contract_summary.py`; `generated/contracts/dallas-electrician-contract-summary-v1/` now passes `13/13` checks, including repeated current result-state support, repeated core failure-reason support, and repeated key next-action support.
- Updated `NEXT_TASK.md`, `generated/landing.html`, and `index.html` so the next choice is either widening the remaining thin incomplete-work support or starting a small runnable local inspection workflow.
- Added `scripts/generate_dallas_inspection_workflow.py` and generated `generated/workflows/dallas-inspection-workflow-v1/action-queue.json` plus `action-queue.md`.
- The generated inspection workflow queue has `13` action items with priority, address, contractor, trigger inspection, recommended actions, and observed follow-up fields; this is the first product-shaped output beyond reports and contract summaries.
- Extended the workflow writer to emit `generated/workflows/dallas-inspection-workflow-v1/index.html`, a static browser-readable queue page with the same `13` action items.

## 2026-05-21

- Copied the Autom oat SVG mark from the matthoffner site repo into local static assets and generated assets so both `index.html` and `generated/landing.html` can resolve it.
- Refreshed the landing page header and hero to use the logo instead of the old dot mark, then tightened mobile layout with compact navigation pills, full-width calls to action, single-column content grids, better text wrapping for long code paths, and smaller mobile hero type.
- Synced `generated/landing.html` back to root `index.html` and verified the local static page plus logo asset served successfully from `http://127.0.0.1:4173/`.
- Recolored the Autom oat SVG away from the source site's teal/neon palette and into the landing page's ink, terracotta, cream, and clay colors.
- Rewrote the top-level landing message around a tangible moat candidate: local inspection failure memory, reviewed next-action labels, reusable eval contracts, and a workflow feedback loop from accepted, rejected, or edited recommendations.
- Corrected the landing page back toward the broader product thesis: `automoat` creates data moats automatically from repeated business workflows, while permit and inspection data remains only the first concrete MVP proof wedge.
- Added an Agent Cockpit section to the landing page that frames the product surface as a terminal/log tunnel into a bounded Codex loop, with loop runner, live terminal stream, artifact feed, and moat-memory concepts tied to existing repo artifacts.
- Added a real local MVP cockpit runtime: `scripts/run_mvp_loop.py` runs a visible loop that regenerates and verifies the Dallas contract, coverage, and action queue, while `scripts/serve_mvp_cockpit.py` starts the loop and streams log/status output in a browser.
- Added a read-only remote bridge path: `scripts/serve_mvp_cockpit.py --read-only` limits exposed routes to live status, loop logs, and whitelisted MVP artifacts, while `scripts/bridge_mvp_cockpit.py` opens an ngrok tunnel for remote observers.

## 2026-05-22

- Restarted the live MVP loop/cockpit and read-only ngrok bridge after the previous tunnel went offline.
- Embedded the fresh bridge URL directly into `generated/landing.html` and `index.html` as a non-iframe live panel under Agent Cockpit.
- The landing page now polls the bridge for `/api/status` and `.automoat/logs/mvp-loop.log`, rendering status, iteration, loop state, contract checks, queue count, and a terminal-style log tail inline.
- Verified the bridge URL `https://0626-140-186-106-90.ngrok-free.app` returns CORS preflight headers, live JSON status, and log output from the landing-page origin.
- Moved a live cockpit panel into the above-fold hero area so the Vercel landing page shows the running Codex loop immediately instead of burying it below the product sections.
- Added Vercel serverless proxy handlers at `api/cockpit-status.js` and `api/cockpit-log.js`, with `AUTOMOAT_BRIDGE_URL` support and the current ngrok URL as a fallback.
- Updated the landing-page cockpit script to refresh every cockpit panel, prefer same-origin Vercel proxy endpoints, and fall back to direct read-only bridge fetches when running as a plain static page.
