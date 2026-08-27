# Repository Guidelines

## Project Structure & Module Organization
The root product is a static Automoat landing surface plus Python harnesses:

- `index.html` and `generated/landing.html`: exact-mirror public product surface.
- `scripts/`: local inference, moat-eval, Dallas artifact, and runtime/cockpit harnesses.
- `tests/`: deterministic Python contract tests.
- `generated/`: committed Dallas and Whole-Record proof artifacts.
- `AGENTS.md`: contributor and agent workflow guide.
- `.pixelbox/`: coordination files, including `.pixelbox/handoff.md`.
- `.pxcode/`: local Pixelbox metadata.

Automoat is local AI on consumer hardware plus a harness for building a proprietary moat. Token economics and privacy are core gates. Whole-Record Check is one subordinate released capability.

## Build, Test, and Development Commands
Use these non-interactive checks:

- `rg --files`: list tracked project files quickly.
- `python3 -m unittest discover -s tests -v`: run the full contract suite.
- `python3 scripts/generate_dallas_whole_record_check.py --check`: verify the subordinate Whole-Record artifact.
- `python3 scripts/run_dallas_import_pipeline.py --summary-only --require-ready --format json`: verify the Dallas task pack.
- `cmp -s generated/landing.html index.html`: verify public-surface parity.

## Coding Style & Naming Conventions
Keep changes small, readable, and consistent with the surrounding Python, JavaScript, and static HTML. Use descriptive file names, 4-space Python indentation, and secret-safe errors. Keep runtime adapters replaceable and product claims bound to a receipt.

## Testing Guidelines
Add tests alongside new logic. Favor deterministic tests and avoid commands that require prompts, network access, model downloads, or manual setup. Local-inference tests must fail on silent remote egress, raw-content receipts, mismatched task-pack comparisons, or unsupported cost claims.

## Commit & Pull Request Guidelines
Recent history favors Conventional Commit prefixes like `feat:`, `fix:`, and `docs:`. Continue that style and keep subjects imperative and concise, for example `feat: add mojo entrypoint`. Pull requests should include a short summary, testing notes, linked issues when relevant, and screenshots for UI changes.

## Pixelbox Agent Notes
Read the latest entry in `.pixelbox/handoff.md` before starting work. Lane A handles edits and refactors; lane B handles servers and runtime checks. After finishing, append a brief handoff with status, changed files, and next steps. When starting a dev server, prefer `localhost` or `127.0.0.1` and print the exact URL on its own line.

<!-- PIXELBOX_CONTEXT_START -->
# Pixelbox Project Context

This project is being edited and run inside Pixelbox.

## Working Rules
- Keep the main app visually clean and full-bleed where possible.
- Prefer deterministic local dev servers and print the live URL on its own line when ready.
- Use localhost/127.0.0.1 URLs that can be embedded in an Electron webview.
- Avoid interactive shell prompts in automation flows; prefer explicit non-interactive commands.
- If adding scripts, ensure Python commands run without extra manual steps.

## Fast Output Contract
- After completing a task, summarize changed files and exact run commands.
- If a server is started, include the exact URL and port in plain text.

## Dual-Agent Coordination
- Agent lane A (editor): code changes, refactors, UI updates.
- Agent lane B (runtime): start/stop servers, logs, runtime health.
- Write concise handoffs to `.pixelbox/handoff.md` so both lanes stay synced.
- Before acting, read latest handoff entry to avoid stepping on active work.
<!-- PIXELBOX_CONTEXT_END -->
