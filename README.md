# automoat

Created from Pixelbox.

## What This Is

`automoat` connects two systems:

1. **Local AI on consumer hardware.** Run supported models on hardware the user controls and measure the real token economics, task quality, and execution boundary across replaceable runtimes and inference techniques.
2. **A harness for building the user's moat.** Turn private workflows, decisions, corrections, outcomes, and datasets into immutable task packs, reusable evals, and approval-aware systems that improve with use.

Neither half is sufficient alone. Faster local inference is useful only when it makes a valuable job cheaper or more private. Proprietary data is a moat only when a fixed evaluation shows it improves that job. Automoat binds both claims into inspectable receipts.

Token cost and privacy are core product gates, not settings added later. A run should disclose prompt, completion, and total tokens; end-to-end time; effective compute cost when a rate is supplied; whether any request left the device; and whether the result improved the chosen task. Raw business inputs and model outputs do not belong in the aggregate run receipt.

## Product Entry Points

- **Hardware-first local run:** pin a model, runtime, hardware profile, and optimization; execute an immutable task pack on a loopback endpoint; and measure tokens, time, effective cost, privacy boundary, and strict task quality.
- **Moat-first business + data:** map recurring work or inspect local proprietary data, formulate the tasks it can improve, compare against a generic baseline, and choose retrieval, adaptation, fine-tuning, or no deployment.

These are two routes into the same product, not separate products. Both should leave the user with evidence for what can run locally and whether the private business context creates a defensible advantage.

## Current Initiative: Local Run Receipt

`scripts/run_local_moat_eval.py` is the first runtime-neutral measurement contract. It runs a bounded JSONL eval pack against an OpenAI-compatible endpoint, allows loopback by default, refuses remote inference without explicit `--allow-remote`, and writes a receipt without raw tasks, targets, prompts, or predictions.

The receipt binds the task-pack digest to model, runtime, hardware, and optimization provenance; aggregates prompt/completion/total tokens, elapsed time, end-to-end output tokens per second, strict exact-match quality, and optional compute-hour cost; and can compare a candidate with a baseline only when both used the same immutable task pack.

Techniques such as speculative decoding, quantization, prompt caching, and KV-cache optimization remain replaceable. [DFlash2](https://inco.ai/blog/dflash2/) is a current example of how the local-inference floor can move; it is not bundled here, it does not reduce token count by itself, and Automoat makes no speed claim until a specific model/runtime/hardware/task combination has its own receipt.

## Released Moat Builder Capability: Whole-Record Check

Whole-Record Check is one released application of that core loop. It provides a backend-neutral check for the moment before a recommendation becomes an operator action. It compares the candidate answer with one immutable, bounded case snapshot. Agreement produces a Coverage Receipt; a material action or evidence mismatch produces an Evidence Conflict card with stable source IDs and existing correction-ledger context.

The current validation is deliberately narrow: 30 versioned Dallas residential-electrician scaffold cases with exactly 10 planted retrieval omissions. The deterministic harness produces 20 Coverage Receipts, detects all 10 omissions as conflicts, and produces no unexpected conflicts. Dallas is the bounded validation case for this initiative, not Automoat's product identity, and the result is a regression proof rather than a production model-accuracy benchmark.

## Docs

- [Vision](./vision.md)
- [Use Cases](./use-cases.md)
- [MVP](./mvp.md)
- [Generated Status Page](./generated/landing.html)
- [Dallas Import Pipeline Summary](./generated/pipeline/dallas-import-pipeline-summary-v1/summary.md)
- [Dallas Edge-Case Coverage](./generated/coverage/dallas-electrician-edge-case-coverage-v1/coverage.md)
- [Dallas Inspection Workflow](./generated/workflows/dallas-inspection-workflow-v1/index.html)
- [Dallas Whole-Record Check](./generated/whole-record/dallas-whole-record-check-v1/index.html)
- [Dallas Whole-Record Check Report](./generated/whole-record/dallas-whole-record-check-v1/report.md)
- [Loop Instructions](./LOOP.md)
- [Next Task](./NEXT_TASK.md)

## Automation

- Loop runner: `./scripts/codex-loop.sh -- <command>`
- Work session runner: `./scripts/codex-session.sh [minutes]`
- 24-hour supervisor runner: `./scripts/codex-day.sh [hours] [session-minutes]`
- Auto-publish helper: `./scripts/codex-publish.sh ["commit message"]`
- MVP loop runner: `python3 scripts/run_mvp_loop.py --iterations 3 --interval 5`
- Local AI eval receipt: `python3 scripts/run_local_moat_eval.py --url http://127.0.0.1:8080 --tasks <tasks.jsonl> --receipt <receipt.json> --runtime <runtime> --hardware <hardware> --model <model>`
- Autonomous Codex loop runner: `python3 scripts/run_autonomous_agent_loop.py --iterations 1 --interval 300`
- Loop status JSON: `.automoat/state/mvp-loop-status.json` includes `artifacts.import_pipeline.execution_readiness` from `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json`, so local cockpit readers can see Dallas import readiness without reparsing the pipeline artifact.
- MVP cockpit server: `python3 scripts/serve_mvp_cockpit.py --auto-start --loop-mode agent --interval 300 --port 4174`
- Render cockpit relay service: `python3 scripts/render_cockpit_relay.py --host 0.0.0.0 --port ${PORT:-4180}`
- Render relay publisher: `AUTOMOAT_RELAY_URL=https://<render-service>.onrender.com AUTOMOAT_RELAY_TOKEN=<secret> python3 scripts/publish_cockpit_to_relay.py`
- Detached autonomous cockpit plus Render relay publisher: `AUTOMOAT_RELAY_URL=https://<render-service>.onrender.com AUTOMOAT_RELAY_TOKEN=<secret> python3 scripts/start_autonomous_cockpit_relay.py`
- Render Codex worker entrypoint: `python3 scripts/start_render_codex_worker.py`; this is intended for the Docker-backed `automoat-codex-worker` Render service from the root `Dockerfile` and requires `GITHUB_TOKEN`, `CODEX_AUTH_JSON_B64` or another Codex login secret, `AUTOMOAT_RELAY_URL`, and `AUTOMOAT_RELAY_TOKEN`.
- Legacy detached autonomous cockpit plus ngrok bridge: `python3 scripts/start_autonomous_cockpit_bridge.py`
- Legacy read-only ngrok bridge: `python3 scripts/bridge_mvp_cockpit.py`
- Dallas eval artifact writer: `python3 scripts/generate_dallas_eval_artifacts.py`
- Optional Modal SLM deploy: `modal deploy modal_slm.py`; this serves a GPU-backed llama.cpp model at `/v1/chat/completions` while keeping the Render worker and cockpit relay unchanged.
- Bounded SLM eval sample: `AUTOMOAT_SLM_URL=https://<modal-app>.modal.run AUTOMOAT_SLM_TOKEN=<secret> python3 scripts/slm_inference_client.py --tasks generated/evals/dallas-electrician-import-sample-v2/tasks.jsonl --output generated/evals/dallas-electrician-import-sample-v2/predictions/slm-smoke.jsonl --limit 10`
- Dallas label review writer: `python3 scripts/generate_dallas_label_reviews.py`
- Dallas discovery artifact writer: `python3 scripts/generate_dallas_discovery_artifacts.py`
- Dallas discovery batch mode: `python3 scripts/generate_dallas_discovery_artifacts.py --batch-input-dir generated/intake --batch-output-dir generated/discovery`
- Dallas extract importer: `python3 scripts/import_dallas_permit_extracts.py`
- Dallas latest import pipeline: `python3 scripts/run_dallas_import_pipeline.py` prints the next-gap summary, raw CSV handoff, copyable follow-up commands, generated report paths, and writes `generated/pipeline/dallas-import-pipeline-summary-v1/summary.json` plus `summary.md`; add `--require-ready` when automation should fail if the generated execution-readiness gate is blocked, use `--summary-only --require-ready` to rebuild the durable summary and strict readiness result from current generated artifacts without rerunning every writer, or add `--format json` when automation needs the final summary on stdout with step logs sent to stderr.
- Dallas edge-case coverage writer: `python3 scripts/generate_dallas_edge_case_coverage.py`
- Dallas inspection workflow writer: `python3 scripts/generate_dallas_inspection_workflow.py`
- Dallas Whole-Record Check writer: `python3 scripts/generate_dallas_whole_record_check.py`
- Dallas Whole-Record Check verification: `python3 scripts/generate_dallas_whole_record_check.py --check`
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

The deployed cockpit should use the Render relay path instead of ngrok. The stable public surface is `automoat-cockpit-relay`, which stores the latest status and log tail and serves `/api/status` plus `/api/log`; Vercel reads that stable public relay through `/api/cockpit-status` and `/api/cockpit-log`. This avoids exposing inbound access to a developer machine and avoids tunnel bandwidth/session failures.

The real cloud worker is `automoat-codex-worker`. It runs from the root `Dockerfile`, clones `main` at runtime with a GitHub token, authenticates Codex from a Render secret, starts `scripts/run_autonomous_agent_loop.py`, and runs `scripts/publish_cockpit_to_relay.py` beside it so the landing page can show the agent working. Only one writer should run against `main` at a time: stop the local cockpit loop before enabling the Render worker.

The autonomous loop is now policy-gated against low-leverage synthetic fixture churn. When Dallas import readiness is already `ready` and coverage has no thin groups, the prompt directs Codex toward autonomy, visibility, Render reliability, real ingest mechanics, product clarity, and tests. The supervisor rejects a synthetic `example.local` Dallas raw-row append when it is not paired with code, ingest, infra, test, or durable spec work; routine README, NEXT_TASK, landing-page, journal, or handoff refreshes do not count as that companion work.

### Optional Modal SLM experiment

Render remains the durable CPU orchestrator; it does not host model weights. `modal_slm.py` adds an independent, scale-to-zero L4 service using a CUDA build of `llama-cpp-python`, a persistent model volume, and an authenticated OpenAI-compatible chat-completions route. The default is a Qwen 2.5 3B Q4 GGUF, and `AUTOMOAT_SLM_MODEL_REPO` plus `AUTOMOAT_SLM_MODEL_FILE` can select another compatible Hugging Face GGUF before deployment.

Install the Modal CLI, authenticate it, and create the shared secret without committing its value:

```bash
python3 -m pip install modal
modal setup
modal secret create automoat-slm AUTOMOAT_SLM_TOKEN=<random-secret> HF_TOKEN=<optional-hugging-face-token>
modal deploy modal_slm.py
```

Set `AUTOMOAT_SLM_URL` to the deployed `api` function URL and use `scripts/slm_inference_client.py` for a single prompt or a bounded JSONL eval. The client enforces deterministic temperature, requests JSON output, excludes target labels from prompts, bounds response size and timeout, and writes predictions beside the existing eval artifacts. Start with `--limit 10`; compare correctness, latency, token use, cold starts, and cost before routing production work. The Modal service is optional, and Codex/OpenAI remains the repository-editing agent and baseline fallback.

The eventual app shell can be React Server Components instead of an iframe. Use RSC for the initial cockpit snapshot from `/api/status` and whitelisted artifacts, then use a small client component or polling client for the live terminal/log stream. Keep mutation endpoints local-only; remote relays should stay read-only.

Local operator corrections from the Dallas action queue post to `/api/operator-corrections` and append `generated/workflows/dallas-inspection-workflow-v1/operator-corrections.jsonl`. The read-only bridge can expose the ledger, but it rejects mutation requests.
Use `python3 scripts/record_operator_correction.py --smoke-check` to run a non-mutating readiness check before an automation pass, or add `--format text` for the operator-readable command contract; the smoke check honors the requested output mode and verifies ledger health, strict completion-gate behavior, accepted operator-pattern availability, accepted/rejected/edited next-missing command guards with `--use-next-missing` when queue items are still missing, stale expected-ID rejection, fixed-item queue ID guards that avoid shortcut mode, generated command output-format preservation, ledger-validation next-missing command format, summary/progress command output-format preservation, next-missing validation and completion command output-format preservation, edited-action templates, note dry-runs and appends, accepted/rejected/edited dry-run event construction, stale-capture rejection against a temporary ledger, and stale permit/inspection context rejection. Use `python3 scripts/record_operator_correction.py --summary --format text` to check capture progress and get validation plus completion-gate commands, `python3 scripts/record_operator_correction.py --list-patterns --format text` to inspect the reusable accepted correction patterns after capture, `python3 scripts/record_operator_correction.py --list-queue-items` to review all current queue item IDs, `python3 scripts/record_operator_correction.py --list-queue-items --missing-only` to list uncaptured Dallas queue items with evidence and observed follow-up context, `python3 scripts/record_operator_correction.py --next-missing --format text` to print a readable work order when any queue item remains uncaptured, and `python3 scripts/record_operator_correction.py --validate-ledger` to verify captured events still match the current queue and action catalog while reporting captured versus missing queue item coverage. Add `--require-complete` to validation when the pass should fail until every current queue item has a captured correction; text validation output with missing queue items prints the next `--next-missing --format text` work-order command, while default JSON validation keeps the machine-readable next-missing command without `--format text`. The current generated Dallas workflow has `535/535` queue items captured, including `532` accepted decisions and `3` edited decisions, so the completion gate should pass before the next real import-readiness pass. Suggested next-missing shortcut commands include `--expected-next-missing-id` so stale work orders fail if another correction changes the first missing queue item before capture. Suggested capture commands include `--require-missing` so stale fixed-item work orders refuse accidental duplicate captures; omit that flag only when intentionally appending an updated operator correction. Text work orders and text dry-run/record confirmations include `--format text` in copyable validation and next-missing commands, while JSON work orders keep the default machine-readable command shape. Edited corrections reject unknown action IDs before appending, deterministic dry-runs and appends reject duplicate correction IDs before writing, ledger validation rejects missing or duplicated correction IDs plus stale permit/inspection context, and duplicate queue item IDs now fail validation and capture before a correction can attach to an ambiguous queue row. Omit `--format text` when a machine-readable JSON response is needed.
When the current Dallas correction ledger is already complete, the smoke check creates a temporary incomplete ledger so next-missing commands, dry-run event construction, and completion-gate rejection still get exercised without mutating the real operator-correction ledger.

Latest Dallas import status: the generated workflow now has `535/535` queue items captured, including `532` accepted decisions and `3` edited decisions. The latest import summary reports `535` permits, `1082` inspections, `1093` eval tasks, `541` reviewed labels, and `1625` source records, with the next raw append rows at `permits.csv` row `538` and `inspections.csv` row `1085`.


## Deploy

- Vercel should rebuild from pushes to `main`.
- Render should use the root `render.yaml` Blueprint to create `automoat-cockpit-relay`; set `AUTOMOAT_RELAY_TOKEN` as a secret when applying the Blueprint.
- Render should also run `automoat-codex-worker` from the root `Dockerfile`; set `GITHUB_TOKEN`, `CODEX_AUTH_JSON_B64` or `OPENAI_API_KEY`, `AUTOMOAT_RELAY_TOKEN`, and `AUTOMOAT_RELAY_URL`.
- Vercel should set `AUTOMOAT_RELAY_URL=https://<render-service>.onrender.com`; only set `AUTOMOAT_BRIDGE_URL` when intentionally using the legacy ngrok bridge.
- Local publishing should run with the same `AUTOMOAT_RELAY_URL` and `AUTOMOAT_RELAY_TOKEN`, then `python3 scripts/start_autonomous_cockpit_relay.py` starts the local autonomous cockpit and the outbound publisher together.
