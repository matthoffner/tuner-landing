# Heartbeat

This file defines how unattended `automoat` work sessions should behave.

Treat this as the per-session execution policy for repeated bounded runs.

## Purpose

If a work session is active, keep making concrete progress on the current mission until the session budget expires.

The current mission is:

- make the Dallas electricians MVP more executable
- reduce ambiguity in schema, evals, and discovery outputs
- keep the landing page and logs aligned with the real project state

## Primary Priority Order

When deciding what to do next during a work session, prefer this order:

1. `schema.md`
2. `evals.md`
3. `discovery-artifacts.md`
4. implementation-facing scaffolding
5. landing page and documentation alignment

## Session Behavior

If one bounded task finishes early, immediately start the next highest-value bounded task.

Do not wait for the full session window unless blocked.

Keep working until one of these happens:

- the session time budget expires
- you hit a real blocker
- the next step requires user input or credentials
- the next useful task would be too speculative

## Required Per Iteration

Each iteration should:

- read [NEXT_TASK.md](./NEXT_TASK.md)
- read [.pixelbox/handoff.md](./.pixelbox/handoff.md)
- leave at least one artifact, decision, or refinement
- update [.automoat/logs/agent-journal.md](./.automoat/logs/agent-journal.md) when meaningful progress happens
- update [generated/landing.html](./generated/landing.html) if the high-level status changes

## Avoid

- broadening scope past Dallas electricians
- redoing completed planning work unless it is clearly wrong
- acting like a generic research assistant
- producing vague brainstorming without repo artifacts

## Good Iteration Size

One iteration should usually complete one of:

- one new doc
- one major section in an existing doc
- one clear implementation scaffold
- one concrete refinement of the schema or eval plan

## Output Style

Prefer durable repo artifacts over transient notes.

Every iteration should leave the repo slightly more buildable than it was before.
