# automoat

Created from Pixelbox.

## What This Is

`automoat` is a local-first scaffold for turning repeated operational judgment into inspectable artifacts before building a product around it. The current proof is deliberately narrow: Dallas residential electrical permits and inspections for electricians. The repo normalizes sample records, generates inspection sequences, creates eval tasks and reviewed labels, checks contract stability, reports edge-case coverage, and now emits a small action queue that shows what an operator would do after failed or not-ready inspections.

## Docs

- [Vision](./vision.md)
- [Use Cases](./use-cases.md)
- [MVP](./mvp.md)
- [Generated Status Page](./generated/landing.html)
- [Dallas Import Pipeline Summary](./generated/pipeline/dallas-import-pipeline-summary-v1/summary.md)
- [Dallas Edge-Case Coverage](./generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md)
- [Dallas Inspection Workflow](./generated/workflows/dallas-inspection-workflow-v1/index.html)
- [Loop Instructions](./LOOP.md)
- [Next Task](./NEXT_TASK.md)

## Automation

- Loop runner: `./scripts/codex-loop.sh -- <command>`
- Work session runner: `./scripts/codex-session.sh [minutes]`
- 24-hour supervisor runner: `./scripts/codex-day.sh [hours] [session-minutes]`
- Auto-publish helper: `./scripts/codex-publish.sh ["commit message"]`
- MVP loop runner: `python3 scripts/run_mvp_loop.py --iterations 3 --interval 5`
- Autonomous Codex loop runner: `python3 scripts/run_autonomous_agent_loop.py --iterations 1 --interval 300`
- Loop status JSON: `.automoat/state/mvp-loop-status.json` includes `artifacts.import_pipeline.execution_readiness` from `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json`, so local cockpit readers can see Dallas import readiness without reparsing the pipeline artifact.
- MVP cockpit server: `python3 scripts/serve_mvp_cockpit.py --auto-start --loop-mode agent --interval 300 --port 4174`
- Detached autonomous cockpit plus bridge: `python3 scripts/start_autonomous_cockpit_bridge.py`
- Read-only remote bridge: `python3 scripts/bridge_mvp_cockpit.py`
- Dallas eval artifact writer: `python3 scripts/generate_dallas_eval_artifacts.py`
- Dallas label review writer: `python3 scripts/generate_dallas_label_reviews.py`
- Dallas discovery artifact writer: `python3 scripts/generate_dallas_discovery_artifacts.py`
- Dallas discovery batch mode: `python3 scripts/generate_dallas_discovery_artifacts.py --batch-input-dir generated/intake --batch-output-dir generated/discovery`
- Dallas extract importer: `python3 scripts/import_dallas_permit_extracts.py`
- Dallas latest import pipeline: `python3 scripts/run_dallas_import_pipeline.py` prints the next-gap summary, raw CSV handoff, copyable follow-up commands, generated report paths, and writes `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json` plus `summary.md`; add `--require-ready` when automation should fail if the generated execution-readiness gate is blocked, use `--summary-only --require-ready` to rebuild the durable summary and strict readiness result from current generated artifacts without rerunning every writer, or add `--format json` when automation needs the final summary on stdout with step logs sent to stderr.
- Dallas edge-case coverage writer: `python3 scripts/generate_dallas_edge_case_coverage.py`
- Dallas inspection workflow writer: `python3 scripts/generate_dallas_inspection_workflow.py`
- Dallas operator-correction queue listing: `python3 scripts/record_operator_correction.py --list-queue-items`
- Dallas missing-correction queue listing: `python3 scripts/record_operator_correction.py --list-queue-items --missing-only`
- Dallas next missing correction: `python3 scripts/record_operator_correction.py --next-missing`
- Dallas next missing correction work order: `python3 scripts/record_operator_correction.py --next-missing --format text`
- Dallas next missing correction text dry-run: `python3 scripts/record_operator_correction.py --use-next-missing --expected-next-missing-id <queue-item-id> --decision accepted --require-missing --dry-run --format text`
- Dallas next missing correction recorder: `python3 scripts/record_operator_correction.py --use-next-missing --expected-next-missing-id <queue-item-id> --decision accepted --require-missing --format text`
- Dallas operator-correction progress summary and next import raw-file handoff: `python3 scripts/record_operator_correction.py --summary --format text`
- Dallas accepted correction patterns: `python3 scripts/record_operator_correction.py --list-patterns --format text`
- Dallas operator-correction JSON smoke check: `python3 scripts/record_operator_correction.py --smoke-check`
- Dallas operator-correction text smoke check: `python3 scripts/record_operator_correction.py --smoke-check --format text`
- Dallas operator-correction ledger validation: `python3 scripts/record_operator_correction.py --validate-ledger`
- Dallas operator-correction completion gate: `python3 scripts/record_operator_correction.py --validate-ledger --require-complete`
- Dallas operator-correction recorder: `python3 scripts/record_operator_correction.py --queue-item-id <queue-item-id> --decision accepted --require-missing`
- Imported-sample fixture pack: `python3 scripts/generate_dallas_fixture_pack.py --input-dir generated/normalized/dallas-electrician-import-sample-v1 --output-dir generated/fixtures/dallas-electrician-import-sequences-v1`
- Imported-sample eval scaffold: `python3 scripts/generate_dallas_eval_artifacts.py --fixture-dir generated/fixtures/dallas-electrician-import-sequences-v1 --normalized-dir generated/normalized/dallas-electrician-import-sample-v1 --output-dir generated/evals/dallas-electrician-import-sample-v1 --dataset-id dallas-electrician-import-sample-v1`
- Shared lock: `.automoat/state/loop.lock`
- Human journal: [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md)
- Session policy: [HEARTBEAT.md](./HEARTBEAT.md)
- Day/session runs now auto-sync `generated/landing.html` to `index.html`, auto-publish to `main`, and archive stale locks before continuing.

## Cockpit Architecture

The eventual app shell can be React Server Components instead of an iframe. Use RSC for the initial cockpit snapshot from `/api/status` and whitelisted artifacts, then use a small client component with `EventSource('/events')` for the live terminal/log stream. Keep mutation endpoints local-only; remote bridges should stay read-only.

Local operator corrections from the Dallas action queue post to `/api/operator-corrections` and append `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`. The read-only bridge can expose the ledger, but it rejects mutation requests.
Use `python3 scripts/record_operator_correction.py --smoke-check` to run a non-mutating readiness check before an automation pass, or add `--format text` for the operator-readable command contract; the smoke check honors the requested output mode and verifies ledger health, strict completion-gate behavior, accepted operator-pattern availability, accepted/rejected/edited next-missing command guards with `--use-next-missing` when queue items are still missing, stale expected-ID rejection, fixed-item queue ID guards that avoid shortcut mode, generated command output-format preservation, ledger-validation next-missing command format, summary/progress command output-format preservation, next-missing validation and completion command output-format preservation, edited-action templates, note dry-runs and appends, accepted/rejected/edited dry-run event construction, stale-capture rejection against a temporary ledger, and stale permit/inspection context rejection. Use `python3 scripts/record_operator_correction.py --summary --format text` to check capture progress and get validation plus completion-gate commands, `python3 scripts/record_operator_correction.py --list-patterns --format text` to inspect the reusable accepted correction patterns after capture, `python3 scripts/record_operator_correction.py --list-queue-items` to review all current queue item IDs, `python3 scripts/record_operator_correction.py --list-queue-items --missing-only` to list uncaptured Dallas queue items with evidence and observed follow-up context, `python3 scripts/record_operator_correction.py --next-missing --format text` to print a readable work order when any queue item remains uncaptured, and `python3 scripts/record_operator_correction.py --validate-ledger` to verify captured events still match the current queue and action catalog while reporting captured versus missing queue item coverage. Add `--require-complete` to validation when the pass should fail until every current queue item has a captured correction; text validation output with missing queue items prints the next `--next-missing --format text` work-order command, while default JSON validation keeps the machine-readable next-missing command without `--format text`. The current generated Dallas workflow has `85/85` queue items captured, including `82` accepted decisions and `3` edited decisions, so the completion gate should pass before the next real import-readiness pass. Suggested next-missing shortcut commands include `--expected-next-missing-id` so stale work orders fail if another correction changes the first missing queue item before capture. Suggested capture commands include `--require-missing` so stale fixed-item work orders refuse accidental duplicate captures; omit that flag only when intentionally appending an updated operator correction. Text work orders and text dry-run/record confirmations include `--format text` in copyable validation and next-missing commands, while JSON work orders keep the default machine-readable command shape. Edited corrections reject unknown action IDs before appending, deterministic dry-runs and appends reject duplicate correction IDs before writing, ledger validation rejects missing or duplicated correction IDs plus stale permit/inspection context, and duplicate queue item IDs now fail validation and capture before a correction can attach to an ambiguous queue row. Omit `--format text` when a machine-readable JSON response is needed.
When the current Dallas correction ledger is already complete, the smoke check creates a temporary incomplete ledger so next-missing commands, dry-run event construction, and completion-gate rejection still get exercised without mutating the real operator-correction ledger.

## Deploy

- Vercel should rebuild from pushes to `main`.
