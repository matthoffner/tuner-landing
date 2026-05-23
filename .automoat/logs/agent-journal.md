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
- Restored the bridge after the previous ngrok endpoint went offline: restarted `scripts/serve_mvp_cockpit.py --auto-start --interval 6 --port 4174`, restarted `scripts/bridge_mvp_cockpit.py`, and updated the landing page plus Vercel API fallbacks to `https://7597-140-186-106-90.ngrok-free.app`.
- Tightened the Vercel proxy handlers so stale upstream bridge URLs return explicit `502` bridge errors instead of passing ngrok's offline HTML through as cockpit JSON/text.
- Fixed the repeated bridge failure by restarting the cockpit and bridge as detached OS-session processes instead of foreground tool sessions; the new processes are parented to PID 1 and should survive after this Codex turn ends.
- Updated the Vercel cockpit bridge fallback to `https://5694-140-186-106-90.ngrok-free.app` and ignored the detached-process pid/log files under `.automoat/`.
- Added `scripts/run_autonomous_agent_loop.py`, which writes the same cockpit status/log files but runs a real bounded `codex exec` iteration, then syncs landing output, checks the diff, commits changed paths except `.pxcode/preview.json`, and pushes to `main`.
- Updated `scripts/serve_mvp_cockpit.py` with `--loop-mode agent` / `--agent-loop`, and added `scripts/start_autonomous_cockpit_bridge.py` so the autonomous cockpit plus read-only bridge can be restarted as detached processes with one command.
- Refreshed the landing page and README copy so the cockpit is described as an autonomous Codex agent loop rather than only a deterministic Dallas artifact heartbeat.

## 2026-05-23

- Added local operator-correction capture for the Dallas inspection action queue: the generated workflow page now includes accept/reject/edit controls, preserves a source-controlled `operator-corrections.jsonl` ledger, and carries correction counts in `action-queue.json` plus `action-queue.md`.
- Added local-only `POST /api/operator-corrections` handling to `scripts/serve_mvp_cockpit.py`; read-only bridges can view correction summaries and the ledger but still reject mutations.
- Updated `scripts/run_mvp_loop.py` so cockpit status includes the workflow's operator-correction summary.
- Added a shared `scripts/operator_corrections.py` helper and `scripts/record_operator_correction.py` CLI so an operator can validate or append one accepted/rejected/edited Dallas queue correction without running the cockpit server.
- Added `--list-queue-items` to `scripts/record_operator_correction.py` so the non-server correction path can print current queue item IDs, trigger context, and recommended action IDs before appending or dry-running a decision.
- Added `--summary` to `scripts/record_operator_correction.py` and made `--list-queue-items` correction-aware so the non-server correction path shows total captured queue items, missing queue item IDs, and per-item captured/missing status before an operator records another Dallas decision.
- Added `--missing-only` to `scripts/record_operator_correction.py --list-queue-items` so the next non-server operator pass can print only Dallas queue items without captured corrections.
- Added `--next-missing` to `scripts/record_operator_correction.py` so a non-server operator pass can print one uncaptured Dallas queue item at a time with dry-run and append commands for accepted/rejected decisions plus edited-action templates.
- Extended `scripts/record_operator_correction.py --next-missing` so its suggested commands also include optional `--operator-note` variants for accepted, rejected, and edited corrections, making rationale capture executable without rebuilding the command by hand.
- Added an action ID catalog to `scripts/record_operator_correction.py --list-queue-items` and `--next-missing` so edited Dallas operator corrections can be filled from the CLI output without opening the action queue JSON.
- Added `--format text` to the read-only `scripts/record_operator_correction.py` modes so `--summary`, `--list-queue-items`, and `--next-missing` can print readable non-server operator work orders while keeping JSON as the default automation contract.
- Added `--validate-ledger` to `scripts/record_operator_correction.py` so the non-server operator path can verify captured Dallas correction events against the current queue item IDs, valid decisions, known action IDs, and accepted/rejected/edited action shapes before the next capture pass.
- Added `--use-next-missing` to `scripts/record_operator_correction.py` so the non-server operator path can dry-run or append the first uncaptured Dallas correction directly, without copying the queue item ID out of the work order.
- Tightened edited operator-correction capture so `scripts/operator_corrections.py` rejects unknown corrected action IDs before dry-run or append, keeping simple action-ID typos out of the Dallas correction ledger.
- Added `--require-missing` to `scripts/record_operator_correction.py` and included it in the generated next-missing work-order commands, so stale fixed-item capture commands fail cleanly if another correction has already been recorded for that Dallas queue item.
- Extended `scripts/record_operator_correction.py --format text` to correction dry-runs and appends, so the non-server Dallas operator path can show a readable event confirmation without changing the default JSON automation contract.
- Updated `scripts/record_operator_correction.py --next-missing --format text` so its copyable dry-run and append commands preserve `--format text`, keeping the non-server Dallas operator path readable end to end while JSON work orders remain machine-oriented.
- Updated `scripts/record_operator_correction.py --next-missing --format text` so the same work order now ends with a copyable text-mode `--validate-ledger` command, keeping the non-server Dallas correction pass executable through its final check.
- Updated `scripts/record_operator_correction.py --validate-ledger` so validation output includes captured versus missing queue item coverage and missing queue item IDs, making the final non-server check show both ledger validity and remaining Dallas correction work.
- Updated `scripts/record_operator_correction.py --next-missing` and `--list-queue-items` so read-only operator work orders include evidence and observed follow-up context from the Dallas action queue before asking for accepted/rejected/edited correction capture.
- Added `--require-complete` to `scripts/record_operator_correction.py --validate-ledger`, giving the non-server Dallas correction path a strict final gate that fails until every current queue item has a captured operator correction.
- Updated text-mode ledger validation with missing queue items to print the next `python3 scripts/record_operator_correction.py --next-missing --format text` work-order command, so validation points directly back to the next non-server capture pass.
- Tightened `scripts/record_operator_correction.py --validate-ledger` so it now rejects missing or duplicated `correction_id` values, catching deterministic replay collisions before the Dallas operator-correction ledger is treated as clean.
- Tightened `scripts/operator_corrections.py` so duplicate `correction_id` values are rejected before appending operator-correction events, keeping deterministic replay collisions out of the Dallas ledger instead of relying only on later validation.
- Tightened Dallas correction queue integrity so duplicate `queue_item_id` values now fail ledger validation and correction dry-runs/appends before an operator decision can attach to an ambiguous queue row.
- Updated text-mode Dallas correction dry-run and record confirmations so they now print the copyable ledger-validation, next-missing, and completion-gate commands immediately after the event summary.
- Tightened deterministic Dallas correction dry-runs so `scripts/record_operator_correction.py --dry-run` now rejects duplicate `correction_id` values against the selected ledger, matching append-time replay safety before an operator copies a reusable capture command.
- Added an expected-ID guard to non-server Dallas correction shortcut commands: `--next-missing` now prints `--expected-next-missing-id`, and `--use-next-missing` refuses to record if the first missing queue item changed after the work order was generated.
- Updated `scripts/record_operator_correction.py --summary --format text` so progress output includes copyable next-missing, ledger-validation, and completion-gate commands for the non-server Dallas operator-correction pass.
- Updated `scripts/record_operator_correction.py --next-missing --format text` so note-bearing dry-run shortcut and fixed-item command groups are printed before append commands, letting an operator validate the exact Dallas correction rationale before writing to the ledger.
- Added `scripts/record_operator_correction.py --smoke-check --format text`, a non-mutating readiness check that validates the Dallas correction ledger, confirms guarded next-missing commands are present, and builds accepted/rejected/edited dry-run event shapes before an operator writes to the ledger.
- Tightened `scripts/record_operator_correction.py --smoke-check --format text` so guarded shortcut checks now cover accepted, rejected, and edited command groups, including edited corrected-action templates and note dry-runs instead of only the accepted path.
- Tightened `scripts/record_operator_correction.py --smoke-check --format text` so fixed-item dry-run and append command groups now also have checked queue item IDs, `--require-missing` guards, note placeholders, and edited-action templates before an operator pass.
- Tightened `scripts/record_operator_correction.py --smoke-check --format text` so generated text-mode dry-run and append command groups must keep `--format text`, preserving readable confirmations throughout the non-server Dallas operator pass.
- Tightened `scripts/record_operator_correction.py --smoke-check --format text` so note-bearing append shortcut and fixed-item command groups now also verify `--operator-note`, stale-capture guards, text output, and queue identity guards before an operator writes to the ledger.
- Tightened `scripts/record_operator_correction.py --smoke-check` so it now honors the requested output mode: the default JSON smoke check verifies generated commands stay machine-readable, while `--format text` still verifies readable command preservation.
- Tightened `scripts/record_operator_correction.py --validate-ledger` so its next-missing command preserves the requested output mode, and extended the smoke check to catch JSON validation output that accidentally switches back to text-mode work orders.
- Tightened `scripts/record_operator_correction.py --smoke-check` again so summary/progress commands are checked for the requested output mode, keeping `--summary` JSON automation output from drifting into text-mode follow-up commands.
- Tightened `scripts/record_operator_correction.py --smoke-check` so shortcut command groups must use `--use-next-missing` and fixed-item command groups must stay on `--queue-item-id`, preventing generated Dallas work orders from mixing the two capture modes.
- Tightened `scripts/record_operator_correction.py --smoke-check` so it now verifies stale-capture rejection against a temporary correction ledger, proving `--require-missing` behavior without mutating the real Dallas operator-correction ledger.
- Tightened `scripts/record_operator_correction.py --smoke-check` so it now verifies `--next-missing` validation and completion follow-up commands preserve the requested JSON or text output mode through the final ledger checks.
