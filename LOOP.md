# Loop

This file defines the unattended or semi-attended Codex work loop for `automoat`.

The loop is intentionally bounded. It should make progress through small, reviewable artifacts. It should not wander.

## Purpose

The loop exists to keep moving the project forward between direct user interventions.

The current mission is:

- define the Dallas electricians MVP clearly enough to implement
- keep the project docs and generated landing page in sync
- leave a legible trail of what each run did

## Current Focus

Read [NEXT_TASK.md](./NEXT_TASK.md) at the start of every run.

Do not infer a new mission if `NEXT_TASK.md` is clear.

## Required Inputs Per Run

Every loop run should read these files before making decisions:

- [vision.md](./vision.md)
- [use-cases.md](./use-cases.md)
- [mvp.md](./mvp.md)
- [NEXT_TASK.md](./NEXT_TASK.md)
- [.pixelbox/handoff.md](./.pixelbox/handoff.md)
- [generated/landing.html](./generated/landing.html)

## Locking

All automated runs must go through [scripts/codex-loop.sh](./scripts/codex-loop.sh).

For multi-iteration unattended work sessions, use:

- [scripts/codex-session.sh](./scripts/codex-session.sh)

For a one-command 24-hour supervisor run, use:

- [scripts/codex-day.sh](./scripts/codex-day.sh)

That script creates a repo-local lock at:

- `.automoat/state/loop.lock`

If the lock exists, do not start another run. Exit cleanly.

The point is to serialize all agents and loop invocations that agree to this contract.

`scripts/codex-session.sh` holds the same lock for the full session, so no other participating agent should start while that session is active.

The loop runners now recover stale locks automatically by checking the recorded PID. If the owning process is gone, the old lock is archived under `.automoat/state/loop.lock.stale-<timestamp>/` and the new run continues.

## Required Outputs Per Run

Every successful run must leave at least one of these behind:

- a doc improvement
- a spec refinement
- a code change
- a new artifact
- a concrete decision recorded in the repo

Every run must also:

- append a concise human-readable note to [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md)
- append or update [.pixelbox/handoff.md](./.pixelbox/handoff.md)
- keep [generated/landing.html](./generated/landing.html) aligned with the high-level project state when needed
- sync [generated/landing.html](./generated/landing.html) to [index.html](./index.html) before publish

For unattended sessions and day runs:

- run a narrow reporter pass after the main worker pass to keep the landing page current
- publish material changes to `main` automatically

## Logging

Automated runner logs live under:

- `.automoat/logs/loop.log`
- `.automoat/runs/<timestamp>/`
- `.automoat/runs/day-<timestamp>/`

Human-readable agent notes live in:

- [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md)

Use the machine logs for execution history and the journal for useful summaries.

## Scope Rules

Stay inside this repository.

Prefer the current project direction:

- local-first product
- Dallas electricians MVP
- business-first discovery plus dataset-first build/eval

Do not widen scope unless the user explicitly changes direction or a necessary prerequisite is discovered.

## Stop Conditions

Stop the current run if:

- the lock is held by another run
- the task is blocked on missing user intent
- the next step requires destructive action
- the next step requires credentials, access, or network work not already approved
- you hit the edge of the current task and the next step would be speculative

When stopping, log the blocker clearly.

## Run Cadence

Suggested cadence for a long session:

- every 20 to 60 minutes

Do not invoke runs so frequently that they overlap or thrash.

If you want a single button-like experience, use a session run instead of manual cadence.

## Success Condition

The loop is successful if, after many small runs, the repo becomes steadily more concrete:

- better-defined specs
- more executable artifacts
- more accurate landing page
- cleaner handoffs
- less ambiguity about the next engineering step
