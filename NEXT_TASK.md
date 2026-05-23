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

- keep the real MVP cockpit running with `python3 scripts/serve_mvp_cockpit.py --auto-start --port 4174`
- expose the running cockpit to remote observers with `python3 scripts/bridge_mvp_cockpit.py` and share the read-only URL from `.automoat/state/mvp-bridge-status.json`
- check correction capture progress with `python3 scripts/record_operator_correction.py --summary`, pick the next uncaptured queue item with `python3 scripts/record_operator_correction.py --next-missing --format text`, use its action catalog when an edited decision needs corrected action IDs, dry-run or record the first uncaptured item directly with one of the printed text-mode commands, run the printed ledger-validation command, use `python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text` as the final all-items gate, and summarize useful correction patterns back into the Dallas workflow artifact
- decide whether the remaining thin latest-import labels, `incomplete_work` and `complete_remaining_work|schedule_reinspection`, need another repeated sequence before real data import

Latest bounded improvement completed:

- `generated/normalized/dallas-electrician-sample-v1/` now provides row-shaped Dallas sample records
- `scripts/generate_dallas_fixture_pack.py` now emits the Dallas fixture pack deterministically from normalized permit and inspection rows
- `scripts/generate_dallas_label_reviews.py` now emits reviewed label rows directly from normalized Dallas permit and inspection records, and `scripts/generate_dallas_eval_artifacts.py` now uses that row-derived supervision path
- `scripts/generate_dallas_discovery_artifacts.py` now supports batch generation across multiple intake variants, and `generated/intake/dallas-electrician-south-dallas-v1/` plus `generated/discovery/dallas-electrician-south-dallas-v1/` exercise the Dallas business-first contract on a second realistic electrician profile
- `scripts/import_dallas_permit_extracts.py` now turns raw Dallas permit, inspection, and contractor CSV extracts into `projects.json`, `properties.jsonl`, `permits.jsonl`, `inspections.jsonl`, `contractors.jsonl`, and `source_records.jsonl` under `generated/normalized/dallas-electrician-import-sample-v1/`
- `scripts/generate_dallas_eval_artifacts.py` now accepts input and output arguments, and `generated/fixtures/dallas-electrician-import-sequences-v1/` plus `generated/evals/dallas-electrician-import-sample-v1/` prove the imported sample holds the same downstream Dallas fixture, review, and eval contracts
- `generated/raw/dallas-electrician-import-sample-v2/` now widens the imported Dallas fixture with `pass`, `fail`, `partial`, `cancelled`, `not_ready`, and `unknown` inspection outcomes, and the generated `normalized`, `fixtures`, and `evals` `-v2` directories prove the importer and downstream contracts hold across the broader result mix
- `scripts/generate_dallas_contract_summary.py` now emits `generated/contracts/dallas-electrician-contract-summary-v1/summary.json` and `summary.md`, making the shared downstream contract and intentional synthetic-versus-imported differences explicit across all current Dallas scaffolds
- `scripts/import_dallas_permit_extracts.py` now optionally ingests `rule_documents.csv` into `rule_documents.jsonl` plus source-lineage rows for imported Dallas samples, and the regenerated contract summary proves imported `v1` and `v2` keep that optional rules path without changing downstream eval contracts
- `generated/raw/dallas-electrician-import-sample-v2/` now includes three additional CSV-backed Dallas electrician permits that repeat the existing `75208` remodel-final, `75214` new-install rough-in/correction-followup, and `75216` repair rough-in slices
- regenerated imported `v2` artifacts now widen to `8` permits, `22` inspections, `31` eval tasks, `13` reviewed label rows, and `38` source-lineage rows while keeping the same downstream task families and split contract
- `scripts/generate_dallas_contract_summary.py` now reports repeated-pattern and repeated-next-action support directly, and the refreshed contract summary passes `10/10` checks with imported `v2` carrying `4` repeated pattern slices at `2` permits of support each
- `generated/raw/dallas-electrician-import-sample-v2/` now includes two more CSV-backed Dallas electrician permits that repeat service-release and access-blocked sequences, while `scripts/import_dallas_permit_extracts.py` now prioritizes real access-blocked notes over generic service wording
- regenerated imported `v2` artifacts now widen to `10` permits, `28` inspections, `37` eval tasks, `15` reviewed label rows, and `46` source-lineage rows while keeping the same downstream task families and split contract
- `scripts/generate_dallas_fixture_pack.py`, `scripts/generate_dallas_label_reviews.py`, and the refreshed contract summary now show a real repeated `ensure_site_access|schedule_reinspection` next-action group backed by one remodel-final and two service-release sequences instead of accidental `panel schedule` matches
- `generated/raw/dallas-electrician-import-sample-v2/` now includes three more CSV-backed Dallas electrician permits that repeat cancelled and unknown outcome paths plus panel/service release failures
- regenerated imported `v2` artifacts now widen to `13` permits, `38` inspections, `49` eval tasks, `19` reviewed label rows, and `59` source-lineage rows while keeping the same downstream task families and split contract
- the refreshed contract summary stays at `10/10` checks and now shows `5` repeated pattern slices plus `5` repeated next-action groups, including `correct_panel_or_service|add_labels_or_documentation|schedule_reinspection`
- `scripts/generate_dallas_edge_case_coverage.py` now emits `generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.json` and `coverage.md`, making repeated support visible across result states, failure reasons, pattern slices, and next-action groups
- the edge-case coverage report shows imported `v2` has repeated support for `6/6` result states, `4/5` failure reasons, `5/5` pattern slices, and `5/6` next-action groups; the remaining thin support is `incomplete_work` and `complete_remaining_work|schedule_reinspection`
- `scripts/generate_dallas_contract_summary.py` now promotes the most important edge-case coverage expectations into contract checks, and `generated/contracts/dallas-electrician-contract-summary-v1/` passes `13/13`
- `scripts/generate_dallas_inspection_workflow.py` now emits `generated/workflows/dallas-inspection-workflow-v1/action-queue.json`, `action-queue.md`, and `index.html`, turning reviewed inspection labels into a concrete browser-readable operator queue with `13` items, priority levels, addresses, contractors, recommended actions, and observed follow-ups
- `scripts/run_mvp_loop.py` and `scripts/serve_mvp_cockpit.py` now provide a real local cockpit loop: the server starts a loop process, streams `.automoat/logs/mvp-loop.log`, exposes `.automoat/state/mvp-loop-status.json`, and repeatedly regenerates/verifies the Dallas contract, coverage, and action queue
- `scripts/bridge_mvp_cockpit.py` now opens a read-only ngrok bridge to a whitelisted cockpit viewer so remote observers can see the local loop without controlling it
- `scripts/serve_mvp_cockpit.py` now accepts local `POST /api/operator-corrections` events from the browser-readable action queue, appending accepted/rejected/edited operator decisions to `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl` while keeping remote bridges read-only
- `scripts/operator_corrections.py` now centralizes operator-correction validation and event writing, and `scripts/record_operator_correction.py` can append or dry-run one accepted/rejected/edited Dallas queue decision without starting the cockpit
- `scripts/record_operator_correction.py --list-queue-items` now prints the current Dallas action queue IDs, priorities, trigger context, and recommended action IDs so operators can capture corrections without opening the generated JSON by hand
- `scripts/record_operator_correction.py --summary` now prints operator-correction capture progress, and `--list-queue-items` marks each Dallas queue item as captured or missing so operators can avoid duplicate correction passes
- `scripts/record_operator_correction.py --list-queue-items --missing-only` now filters the Dallas queue listing to only items without captured corrections, making the next operator pass executable without manual JSON filtering
- `scripts/record_operator_correction.py --next-missing` now prints the next uncaptured Dallas queue item plus dry-run and append commands for accepted/rejected decisions, edited-action templates, optional `--operator-note` variants, and a current action ID catalog for edited decisions
- `scripts/record_operator_correction.py --format text` now gives `--summary`, `--list-queue-items`, and `--next-missing` readable operator work orders while keeping JSON as the default for automation
- `scripts/record_operator_correction.py --validate-ledger` now gives the non-server correction path a deterministic check that captured Dallas correction events still reference current queue items, valid decisions, known action IDs, and expected accepted/rejected/edited action shapes
- `scripts/record_operator_correction.py --use-next-missing --decision accepted --dry-run` now validates or records the first uncaptured Dallas queue item directly, so an operator does not need to copy the queue item ID before each accepted/rejected/edited capture
- `scripts/operator_corrections.py` now rejects edited corrections that contain unknown action IDs before dry-run or append, keeping typos out of the Dallas correction ledger instead of only catching them in later validation
- `scripts/record_operator_correction.py --require-missing` now refuses stale fixed-item capture commands when a queue item already has a captured correction, and `--next-missing --format text` includes that guard in its suggested commands
- `scripts/record_operator_correction.py --format text` now also applies to correction dry-runs and appends, giving operators a readable event confirmation while keeping JSON as the default automation output
- `scripts/record_operator_correction.py --next-missing --format text` now includes `--format text` in its copyable dry-run and append commands, so a text work order keeps the operator in readable confirmations while JSON work orders keep the default automation shape
- `scripts/record_operator_correction.py --next-missing --format text` now also prints the matching text-mode ledger-validation command, so a non-server operator pass can finish with the same copyable work order instead of switching back to README instructions
- `scripts/record_operator_correction.py --validate-ledger` now reports captured versus missing Dallas queue item coverage, so the final non-server check shows both ledger shape validity and remaining uncaptured work
- `scripts/record_operator_correction.py --next-missing --format text` and `--list-queue-items --missing-only --format text` now include evidence and observed follow-up context from the Dallas action queue, so an operator can judge accepted/rejected/edited decisions without opening the generated JSON
- `scripts/record_operator_correction.py --validate-ledger --require-complete` now gives the non-server correction path a strict final gate that fails until every current Dallas action-queue item has a captured operator correction
- `scripts/record_operator_correction.py --validate-ledger --format text` now prints the next `--next-missing --format text` work-order command when queue items are still uncaptured, so validation output points directly back to the next operator pass
- `scripts/record_operator_correction.py --validate-ledger` now rejects missing or duplicated `correction_id` values, so deterministic replays cannot silently leave ambiguous Dallas operator-correction events in the ledger
- `scripts/operator_corrections.py` now rejects duplicate `correction_id` values before appending operator-correction events, so deterministic replays fail before mutating the Dallas correction ledger
- `scripts/record_operator_correction.py --validate-ledger` now reports duplicate queue item IDs, and correction dry-runs/appends reject duplicated queue IDs before an operator decision can attach to an ambiguous Dallas queue row
- `scripts/record_operator_correction.py --format text` correction dry-runs and appends now print copyable ledger-validation, next-missing, and completion-gate commands so a non-server operator pass does not lose its next step after confirming a decision
- `scripts/record_operator_correction.py --dry-run` now rejects duplicate `correction_id` values against the selected ledger, so deterministic replay checks catch timestamp collisions before an operator sees a reusable capture command

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
