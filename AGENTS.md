# Repository Guidelines

## Project Structure & Module Organization
This checkout is intentionally minimal. Root files are:

- `README.md`: brief project overview.
- `AGENTS.md`: contributor and agent workflow guide.
- `.pixelbox/`: coordination files, including `.pixelbox/handoff.md`.
- `.pxcode/`: local Pixelbox metadata.

When application code is added, keep Mojo source under `src/`, supporting assets under `assets/`, and tests under `tests/`.

## Build, Test, and Development Commands
There is no Mojo scaffold yet, so no build or test commands are wired today. Until that exists, use lightweight inspection commands:

- `rg --files`: list tracked project files quickly.
- `git log --oneline -n 10`: review recent change patterns.
- `sed -n '1,120p' README.md`: inspect short files without opening an editor.

If you add the runtime, prefer explicit Mojo commands or thin wrappers around them, such as `mojo src/main.mojo` for local runs and `mojo test` for tests, and keep them non-interactive for Pixelbox.

## Coding Style & Naming Conventions
Keep changes small, readable, and consistent with the surrounding code. Use descriptive file names and prefer kebab-case for docs and config files. Name Mojo files by responsibility, for example `src/app.mojo` and `tests/app_test.mojo`. Use 4-space indentation and adopt the standard Mojo formatter once added.

## Testing Guidelines
Add tests alongside new logic when a test runner is present. Mirror the source name in test files, such as `tests/feature_name_test.mojo`. Favor deterministic tests and avoid commands that require prompts, network access, or manual setup.

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
- If adding scripts, ensure Mojo commands run without extra manual steps.

## Fast Output Contract
- After completing a task, summarize changed files and exact run commands.
- If a server is started, include the exact URL and port in plain text.

## Dual-Agent Coordination
- Agent lane A (editor): code changes, refactors, UI updates.
- Agent lane B (runtime): start/stop servers, logs, runtime health.
- Write concise handoffs to `.pixelbox/handoff.md` so both lanes stay synced.
- Before acting, read latest handoff entry to avoid stepping on active work.
<!-- PIXELBOX_CONTEXT_END -->
