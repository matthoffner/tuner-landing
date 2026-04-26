# automoat

Created from Pixelbox.

## Docs

- [Vision](./vision.md)
- [Use Cases](./use-cases.md)
- [MVP](./mvp.md)
- [Generated Status Page](./generated/landing.html)
- [Loop Instructions](./LOOP.md)
- [Next Task](./NEXT_TASK.md)

## Automation

- Loop runner: `./scripts/codex-loop.sh -- <command>`
- Work session runner: `./scripts/codex-session.sh [minutes]`
- 24-hour supervisor runner: `./scripts/codex-day.sh [hours] [session-minutes]`
- Auto-publish helper: `./scripts/codex-publish.sh ["commit message"]`
- Dallas eval artifact writer: `python3 scripts/generate_dallas_eval_artifacts.py`
- Dallas label review writer: `python3 scripts/generate_dallas_label_reviews.py`
- Dallas discovery artifact writer: `python3 scripts/generate_dallas_discovery_artifacts.py`
- Dallas discovery batch mode: `python3 scripts/generate_dallas_discovery_artifacts.py --batch-input-dir generated/intake --batch-output-dir generated/discovery`
- Dallas extract importer: `python3 scripts/import_dallas_permit_extracts.py`
- Imported-sample fixture pack: `python3 scripts/generate_dallas_fixture_pack.py --input-dir generated/normalized/dallas-electrician-import-sample-v1 --output-dir generated/fixtures/dallas-electrician-import-sequences-v1`
- Imported-sample eval scaffold: `python3 scripts/generate_dallas_eval_artifacts.py --fixture-dir generated/fixtures/dallas-electrician-import-sequences-v1 --normalized-dir generated/normalized/dallas-electrician-import-sample-v1 --output-dir generated/evals/dallas-electrician-import-sample-v1 --dataset-id dallas-electrician-import-sample-v1`
- Shared lock: `.automoat/state/loop.lock`
- Human journal: [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md)
- Session policy: [HEARTBEAT.md](./HEARTBEAT.md)
- Day/session runs now auto-sync `generated/landing.html` to `index.html`, auto-publish to `main`, and archive stale locks before continuing.

## Deploy

- Vercel should rebuild from pushes to `main`.
