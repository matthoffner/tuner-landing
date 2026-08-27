# Heartbeat

This file defines how unattended `automoat` work sessions should behave.

Treat this as the per-session execution policy for repeated bounded runs.

## Purpose

If a work session is active, keep making concrete progress on the current mission until the session budget expires.

The current mission is:

- make consumer-hardware local inference measurable and private by default
- prove whether private workflow context improves a fixed task per token
- keep Dallas and Whole-Record evidence executable but subordinate
- keep the landing page and logs aligned with the real project state

## Primary Priority Order

When deciding what to do next during a work session, prefer this order:

1. real loopback Local Run Receipts and adapter tests
2. token-economics, task-quality, provenance, and egress guards
3. baseline-versus-moat comparisons on immutable task packs
4. implementation-facing moat capture/eval scaffolding
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
- keep [index.html](./index.html) deploy-aligned with [generated/landing.html](./generated/landing.html)
- publish material changes to `main` when running in unattended session or day mode

## Reporter Pass

Long unattended runs should include a narrow reporter pass after the main worker pass.

The reporter pass should:

- read the latest journal, handoff, next task, and generated artifacts
- update [generated/landing.html](./generated/landing.html) as a high-level landing page and changelog
- avoid speculative claims or broad product rewrites

## Avoid

- claiming an inference technique is integrated before a real receipt proves it
- calling remote Modal execution local
- copying raw tasks, prompts, targets, predictions, or secrets into aggregate receipts
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
