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
- run `python3 scripts/record_operator_correction.py --smoke-check` for the default JSON contract and `python3 scripts/record_operator_correction.py --smoke-check --format text` for the readable operator contract, then verify the completed correction ledger with `python3 scripts/record_operator_correction.py --summary --format text` and `python3 scripts/record_operator_correction.py --validate-ledger --require-complete --format text` before widening fixture coverage
- use `python3 scripts/record_operator_correction.py --list-patterns --format text` after capture to inspect reusable accepted operator patterns without opening generated JSON by hand
- use `python3 scripts/run_dallas_import_pipeline.py --require-ready` to refresh the latest Dallas import sample from CSV through normalized rows, fixture pack, evals, coverage, contract summary, workflow, the strict correction-ledger gate, and a durable generated pipeline summary with embedded execution readiness, coverage counts, and accepted operator-pattern snapshots in one deterministic pass that exits nonzero if readiness is blocked
- use `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready` when generated Dallas artifacts already exist and automation only needs to rebuild the durable summary plus strict readiness result without rerunning every artifact writer
- use `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json` when automation needs the final readiness summary on stdout with command logs kept off stdout
- read `.automoat/state/mvp-loop-status.json` `artifacts.import_pipeline.execution_readiness` when the cockpit or autonomous supervisor needs the current Dallas import readiness gate in the same status payload as contract, coverage, workflow, and git state
- keep `generated/workflows/dallas-inspection-workflow-v1/action-queue.json` `operator_correction_patterns` current as accepted operational patterns widen
- use the now-repeated latest-import coverage to choose the next real Dallas import-readiness gap instead of adding more hidden fixture rows by default

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
- the edge-case coverage report now shows imported `v2` has repeated support for `6/6` result states, `5/5` failure reasons, `5/5` pattern slices, and `6/6` next-action groups
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
- `scripts/record_operator_correction.py --next-missing` shortcut commands now include `--expected-next-missing-id`, and `--use-next-missing` refuses to record if the first missing queue item has changed since the work order was generated
- `scripts/record_operator_correction.py --summary --format text` now prints copyable next-missing, ledger-validation, and completion-gate commands so the non-server Dallas correction pass can start from progress output without switching docs
- `scripts/record_operator_correction.py --next-missing --format text` now prints note-bearing dry-run shortcut and fixed-item command groups, so an operator can validate the exact note-carrying Dallas correction before appending it
- `scripts/record_operator_correction.py --smoke-check --format text` now runs a non-mutating readiness check for the Dallas operator-correction path, including ledger validation, guarded next-missing command checks, and accepted/rejected/edited dry-run event construction
- `scripts/record_operator_correction.py --smoke-check --format text` now verifies accepted/rejected/edited next-missing command guard groups, edited-action templates, and note dry-runs instead of only checking the accepted shortcut path
- `scripts/record_operator_correction.py --smoke-check --format text` now also verifies fixed-item dry-run and append command groups keep the selected queue item ID, stale-capture guards, note placeholders, and edited-action templates
- `scripts/record_operator_correction.py --smoke-check --format text` now verifies text-mode generated dry-run and append commands keep `--format text`, so operator work orders continue producing readable confirmations instead of silently falling back to JSON
- `scripts/record_operator_correction.py --smoke-check --format text` now verifies note-bearing append shortcut and fixed-item command groups keep `--operator-note`, stale-capture guards, text output, and queue identity guards before capture
- `scripts/record_operator_correction.py --smoke-check` now honors the requested output format, so the default JSON smoke check verifies generated commands stay machine-readable while `--format text` still verifies text-mode command preservation
- `scripts/record_operator_correction.py --validate-ledger` now preserves the requested output format in its printed next-missing command, and the smoke check verifies JSON validation stays machine-readable while text validation stays operator-readable
- `scripts/record_operator_correction.py --smoke-check` now also verifies summary/progress commands preserve the requested output format, so `--summary` cannot silently print text-mode follow-up commands in the default JSON automation contract
- `scripts/record_operator_correction.py --smoke-check` now verifies `--next-missing` validation and completion follow-up commands preserve the requested output format, so work orders cannot drift between JSON automation and text operator modes at the final check
- `scripts/record_operator_correction.py --smoke-check` now verifies next-missing shortcut commands actually use `--use-next-missing` and fixed-item commands stay on `--queue-item-id`, so generated Dallas work orders cannot blur shortcut and fixed capture modes
- `scripts/record_operator_correction.py --smoke-check` now verifies stale-capture rejection against a temporary correction ledger, so the non-mutating readiness check proves `--require-missing` behavior before a Dallas operator writes to the real ledger
- `scripts/record_operator_correction.py --smoke-check` now verifies stale expected-ID rejection for `--use-next-missing`, so the non-mutating readiness check proves shortcut work orders fail if the first missing Dallas queue item changed before capture
- `scripts/record_operator_correction.py --smoke-check` now verifies the strict completion gate rejects incomplete Dallas correction coverage, so readiness checks prove `--validate-ledger --require-complete` fails until every queue item has a captured operator decision
- `scripts/record_operator_correction.py --validate-ledger` now rejects stale permit, inspection, or source permit context in captured correction events, and the smoke check verifies that guard with a temporary ledger before an operator records real Dallas corrections
- Captured the first Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0008` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `1` captured correction, and the next missing work order advances to `workflow-item:dallas:next-action:0004`
- Captured the second Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0004` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `2` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0002`
- Captured the third Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0002` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `3` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0009`
- Captured the fourth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0009` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `4` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0012`
- Captured the fifth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0012` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `5` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0013`
- Captured the sixth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0013` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `6` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0006`
- Captured the seventh Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0006` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `7` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0007`
- Captured the eighth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0007` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `8` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0010`
- Captured the ninth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0010` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `9` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0001`
- Captured the tenth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0001` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `10` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0011`
- Captured the eleventh Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0011` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `11` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0003`
- Captured the twelfth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0003` is now accepted in `operator-corrections.jsonl`, the regenerated workflow reports `12` captured corrections, and the next missing work order advances to `workflow-item:dallas:next-action:0005`
- Captured the thirteenth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0005` is now accepted in `operator-corrections.jsonl`, and the regenerated workflow plus completion gate report all `13` current queue items captured
- `scripts/generate_dallas_inspection_workflow.py` now groups the latest accepted operator corrections into `operator_correction_patterns`; regenerated workflow artifacts surface `6` reusable accepted action patterns across all `13` captured Dallas queue items
- `generated/raw/dallas-electrician-import-sample-v2/` now includes one more CSV-backed Dallas electrical repair permit that repeats the incomplete-work rough-in path, and the regenerated imported `v2` artifacts now carry `14` permits, `40` inspections, `51` eval tasks, `20` reviewed label rows, and `62` source-lineage rows
- Captured the fourteenth Dallas operator correction through the non-server CLI: `workflow-item:dallas:next-action:0014` is accepted from fixture follow-up evidence, and the regenerated workflow plus completion gate report all `14` current queue items captured with `complete_remaining_work|schedule_reinspection` backed by two accepted correction examples
- `scripts/record_operator_correction.py --list-patterns --format text` now exposes the generated accepted operator-correction patterns directly from the non-server CLI, and the smoke check verifies the pattern payload is available
- `scripts/record_operator_correction.py --smoke-check` now builds a temporary incomplete correction ledger when the real ledger is already complete, so next-missing command guards, dry-run event construction, and completion-gate rejection stay covered without mutating the real Dallas ledger
- `scripts/run_dallas_import_pipeline.py` now refreshes the latest Dallas import-data MVP artifacts end to end, and `scripts/import_dallas_permit_extracts.py` now writes a deterministic imported project timestamp so repeated pipeline checks avoid timestamp churn
- `scripts/run_dallas_import_pipeline.py` now prints copyable pattern-review and completion-gate commands plus generated coverage, contract, and workflow report paths after the next-gap summary, so the next Dallas import-readiness pass can start from one command output
- `scripts/run_dallas_import_pipeline.py` now writes `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json` and `summary.md`, giving the autonomous loop a durable machine-readable and operator-readable import-run result instead of relying only on terminal output
- `scripts/run_dallas_import_pipeline.py` now embeds the latest coverage counts, thin counts, thin group names, and coverage next step in the durable pipeline summary so the next autonomous pass can choose Dallas import-readiness work without opening the full coverage report first
- `scripts/run_dallas_import_pipeline.py` now embeds the latest imported artifact counts, task-family counts, and inspection result vocabulary in the durable pipeline summary so the next pass can see data volume and eval surface without opening the contract summary first
- `scripts/run_dallas_import_pipeline.py` now embeds accepted operator-pattern details in the durable pipeline summary, so the next pass can see reusable action IDs, support counts, failure reasons, follow-up results, example permits, and queue IDs without running a separate pattern review first
- `scripts/run_dallas_import_pipeline.py` now embeds an `execution_readiness` gate in the durable pipeline summary, combining contract pass state, complete operator corrections, strict correction-gate status, thin coverage groups, and accepted operator-pattern availability into one machine-readable readiness signal for the next Dallas import pass
- `scripts/run_dallas_import_pipeline.py --require-ready` now refreshes the same Dallas import pipeline and exits nonzero if the generated `execution_readiness` gate is blocked, giving automation a strict command while preserving the default summary-only behavior
- `scripts/run_dallas_import_pipeline.py --summary-only --require-ready` now skips artifact regeneration, validates the strict correction gate, rebuilds the durable pipeline summary from current generated Dallas artifacts, and exits nonzero if execution readiness is blocked
- `scripts/run_dallas_import_pipeline.py --format json` now emits the final durable Dallas import summary as machine-readable stdout while routing step logs and child command output to stderr
- `scripts/run_mvp_loop.py` and `scripts/run_autonomous_agent_loop.py` now include the durable Dallas import pipeline summary under `artifacts.import_pipeline` in `.automoat/state/mvp-loop-status.json`, including execution-readiness status, blockers, gates, latest import counts, coverage thin groups, accepted pattern counts, and the JSON readiness command

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
