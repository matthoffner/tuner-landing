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
- Dallas eval artifact writer: `./scripts/generate_dallas_eval_artifacts.py`
- Dallas label review writer: `./scripts/generate_dallas_label_reviews.py`
- Dallas discovery artifact writer: `./scripts/generate_dallas_discovery_artifacts.py`
- Shared lock: `.automoat/state/loop.lock`
- Human journal: [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md)
- Session policy: [HEARTBEAT.md](./HEARTBEAT.md)

## Deploy

- Vercel should rebuild from pushes to `main`.
