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
AUTO_REPORT="${AUTO_REPORT:-1}"
AUTO_PUBLISH="${AUTO_PUBLISH:-1}"

WORKER_PROMPT="Read LOOP.md, HEARTBEAT.md, NEXT_TASK.md, vision.md, mvp.md, implementation-spec.md, and .pixelbox/handoff.md. Make one bounded improvement focused on the Dallas electricians MVP. Prefer the next unfinished item in NEXT_TASK.md. Leave durable repo artifacts. Update .automoat/logs/agent-journal.md, .pixelbox/handoff.md, and generated/landing.html if the project state changes."
REPORTER_PROMPT="Read generated/landing.html, NEXT_TASK.md, .automoat/logs/agent-journal.md, .pixelbox/handoff.md, README.md, and the most recent generated artifacts. Update generated/landing.html so it acts as a high-signal landing page and changelog for the real current state of automoat. Do not invent progress. Keep the product framing broad and the build log current."

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUNS_DIR" "$SESSION_DIR"

MINUTES="${1:-$DEFAULT_MINUTES}"
if [[ ! "$MINUTES" =~ ^[0-9]+$ ]] || [[ "$MINUTES" -le 0 ]]; then
  echo "usage: scripts/codex-session.sh [minutes]" >&2
  exit 64
fi

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    return 0
  fi

  local meta_file="$LOCK_DIR/meta.txt"
  local stale_stamp
  stale_stamp="$(date -u +%Y%m%dT%H%M%SZ)"

  if [[ -f "$meta_file" ]]; then
    local lock_pid=""
    lock_pid="$(awk -F= '/^pid=/{print $2}' "$meta_file" | tail -n 1)"
    if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
      echo "loop lock already held: $LOCK_DIR" >&2
      cat "$meta_file" >&2
      return 1
    fi
  fi

  mv "$LOCK_DIR" "$STATE_DIR/loop.lock.stale-$stale_stamp"
  mkdir "$LOCK_DIR"
}

run_codex_prompt() {
  local prompt="$1"
  local log_path="$2"
  set +e
  (
    cd "$ROOT"
    codex exec "$prompt"
  ) 2>&1 | tee "$log_path"
  local status=${PIPESTATUS[0]}
  set -e
  return "$status"
}

cleanup() {
  rm -rf "$LOCK_DIR"
}

trap cleanup EXIT INT TERM

if ! acquire_lock; then
  exit 3
fi

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
SESSION_STATUS=0

while [[ "$(date +%s)" -lt "$END_EPOCH" ]]; do
  ITERATION="$((ITERATION + 1))"
  ITER_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  ITER_DIR="$SESSION_DIR/iter-$ITERATION-$ITER_STAMP"
  ITER_LOG="$ITER_DIR/worker.log"
  REPORT_LOG="$ITER_DIR/reporter.log"
  PUBLISH_LOG="$ITER_DIR/publish.log"
  ITER_META="$ITER_DIR/meta.txt"
  mkdir -p "$ITER_DIR"

  {
    echo "iteration=$ITERATION"
    echo "started_at_utc=$ITER_STAMP"
    echo "worker_prompt=$WORKER_PROMPT"
    echo "reporter_enabled=$AUTO_REPORT"
    echo "publish_enabled=$AUTO_PUBLISH"
  } > "$ITER_META"

  {
    printf '[%s] ITERATION %s START\n' "$ITER_STAMP" "$ITERATION"
  } >> "$LOOP_LOG"

  if run_codex_prompt "$WORKER_PROMPT" "$ITER_LOG"; then
    STATUS=0
  else
    STATUS=$?
  fi

  if [[ "$STATUS" -eq 0 ]] && [[ "$AUTO_REPORT" == "1" ]]; then
    if run_codex_prompt "$REPORTER_PROMPT" "$REPORT_LOG"; then
      STATUS=0
    else
      STATUS=$?
    fi
  fi

  if [[ -f "$ROOT/generated/landing.html" ]]; then
    cp "$ROOT/generated/landing.html" "$ROOT/index.html"
  fi

  if [[ "$STATUS" -eq 0 ]] && [[ "$AUTO_PUBLISH" == "1" ]]; then
    set +e
    (
      cd "$ROOT"
      ./scripts/codex-publish.sh "chore: automated loop update $ITER_STAMP"
    ) 2>&1 | tee "$PUBLISH_LOG"
    STATUS=${PIPESTATUS[0]}
    set -e
  fi

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
    SESSION_STATUS="$STATUS"
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

exit "$SESSION_STATUS"
