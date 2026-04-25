#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT/.automoat/state"
LOG_DIR="$ROOT/.automoat/logs"
RUNS_DIR="$ROOT/.automoat/runs"
LOCK_DIR="$STATE_DIR/loop.lock"
SESSION_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION_DIR="$RUNS_DIR/session-$SESSION_STAMP"
SESSION_LOG="$SESSION_DIR/session.log"
SESSION_META="$SESSION_DIR/meta.txt"
LOOP_LOG="$LOG_DIR/loop.log"
LAST_RUN_FILE="$STATE_DIR/last-run.txt"
DEFAULT_MINUTES=30

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUNS_DIR" "$SESSION_DIR"

MINUTES="${1:-$DEFAULT_MINUTES}"
if [[ ! "$MINUTES" =~ ^[0-9]+$ ]] || [[ "$MINUTES" -le 0 ]]; then
  echo "usage: scripts/codex-session.sh [minutes]" >&2
  exit 64
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "loop lock already held: $LOCK_DIR" >&2
  if [[ -f "$LOCK_DIR/meta.txt" ]]; then
    cat "$LOCK_DIR/meta.txt" >&2
  fi
  exit 3
fi

cleanup() {
  rm -rf "$LOCK_DIR"
}

trap cleanup EXIT INT TERM

START_EPOCH="$(date +%s)"
END_EPOCH="$((START_EPOCH + MINUTES * 60))"

{
  echo "mode=session"
  echo "started_at_utc=$SESSION_STAMP"
  echo "pid=$$"
  echo "host=$(hostname)"
  echo "cwd=$ROOT"
  echo "duration_minutes=$MINUTES"
  echo "session_dir=$SESSION_DIR"
} > "$LOCK_DIR/meta.txt"

cp "$LOCK_DIR/meta.txt" "$SESSION_META"

{
  printf '[%s] SESSION START minutes=%s dir=%s\n' "$SESSION_STAMP" "$MINUTES" "$SESSION_DIR"
} >> "$LOOP_LOG"

ITERATION=0

while [[ "$(date +%s)" -lt "$END_EPOCH" ]]; do
  ITERATION="$((ITERATION + 1))"
  ITER_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  ITER_DIR="$SESSION_DIR/iter-$ITERATION-$ITER_STAMP"
  ITER_LOG="$ITER_DIR/output.log"
  ITER_META="$ITER_DIR/meta.txt"
  mkdir -p "$ITER_DIR"

  PROMPT="Read LOOP.md, HEARTBEAT.md, NEXT_TASK.md, vision.md, mvp.md, implementation-spec.md, and .pixelbox/handoff.md. Make one bounded improvement focused on the Dallas electricians MVP. If schema.md does not exist, prioritize creating it. Otherwise prioritize evals.md, then discovery-artifacts.md. Leave durable repo artifacts. Update .automoat/logs/agent-journal.md, .pixelbox/handoff.md, and generated/landing.html if the project state changes."

  {
    echo "iteration=$ITERATION"
    echo "started_at_utc=$ITER_STAMP"
    echo "prompt=$PROMPT"
  } > "$ITER_META"

  {
    printf '[%s] ITERATION %s START\n' "$ITER_STAMP" "$ITERATION"
  } >> "$LOOP_LOG"

  set +e
  (
    cd "$ROOT"
    codex exec "$PROMPT"
  ) 2>&1 | tee "$ITER_LOG"
  STATUS=${PIPESTATUS[0]}
  set -e

  END_ITER_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  {
    echo "ended_at_utc=$END_ITER_STAMP"
    echo "exit_status=$STATUS"
  } >> "$ITER_META"

  {
    printf '[%s] ITERATION %s END status=%s dir=%s\n' "$END_ITER_STAMP" "$ITERATION" "$STATUS" "$ITER_DIR"
  } >> "$LOOP_LOG"

  {
    echo "last_run_dir=$ITER_DIR"
    echo "ended_at_utc=$END_ITER_STAMP"
    echo "exit_status=$STATUS"
  } > "$LAST_RUN_FILE"

  if [[ "$STATUS" -ne 0 ]]; then
    echo "iteration $ITERATION failed with status $STATUS" | tee -a "$SESSION_LOG"
    break
  fi

  if [[ "$(date +%s)" -ge "$END_EPOCH" ]]; then
    break
  fi

  sleep 2
done

SESSION_END_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
{
  echo "ended_at_utc=$SESSION_END_STAMP"
  echo "iterations=$ITERATION"
} >> "$SESSION_META"

{
  printf '[%s] SESSION END iterations=%s dir=%s\n' "$SESSION_END_STAMP" "$ITERATION" "$SESSION_DIR"
} >> "$LOOP_LOG"
