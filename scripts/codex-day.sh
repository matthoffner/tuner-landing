#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT/.automoat/state"
LOG_DIR="$ROOT/.automoat/logs"
RUNS_DIR="$ROOT/.automoat/runs"
DAY_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAY_DIR="$RUNS_DIR/day-$DAY_STAMP"
DAY_LOG="$DAY_DIR/day.log"
LOOP_LOG="$LOG_DIR/loop.log"
DEFAULT_HOURS=24

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUNS_DIR" "$DAY_DIR"

HOURS="${1:-$DEFAULT_HOURS}"
SESSION_MINUTES="${2:-30}"

if [[ ! "$HOURS" =~ ^[0-9]+$ ]] || [[ "$HOURS" -le 0 ]]; then
  echo "usage: scripts/codex-day.sh [hours] [session-minutes]" >&2
  exit 64
fi

if [[ ! "$SESSION_MINUTES" =~ ^[0-9]+$ ]] || [[ "$SESSION_MINUTES" -le 0 ]]; then
  echo "usage: scripts/codex-day.sh [hours] [session-minutes]" >&2
  exit 64
fi

START_EPOCH="$(date +%s)"
END_EPOCH="$((START_EPOCH + HOURS * 3600))"
CYCLE=0

{
  printf '[%s] DAY START hours=%s session_minutes=%s dir=%s\n' "$DAY_STAMP" "$HOURS" "$SESSION_MINUTES" "$DAY_DIR"
} >> "$LOOP_LOG"

while [[ "$(date +%s)" -lt "$END_EPOCH" ]]; do
  CYCLE="$((CYCLE + 1))"
  CYCLE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  {
    printf '[%s] DAY CYCLE %s START\n' "$CYCLE_STAMP" "$CYCLE"
  } >> "$LOOP_LOG"

  set +e
  (
    cd "$ROOT"
    AUTO_REPORT=1 AUTO_PUBLISH=1 ./scripts/codex-session.sh "$SESSION_MINUTES"
  ) 2>&1 | tee -a "$DAY_LOG"
  STATUS=${PIPESTATUS[0]}
  set -e

  END_CYCLE_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  {
    printf '[%s] DAY CYCLE %s END status=%s\n' "$END_CYCLE_STAMP" "$CYCLE" "$STATUS"
  } >> "$LOOP_LOG"

  if [[ "$STATUS" -ne 0 ]]; then
    break
  fi

  if [[ "$(date +%s)" -ge "$END_EPOCH" ]]; then
    break
  fi

  sleep 5
done

DAY_END_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
{
  printf '[%s] DAY END cycles=%s dir=%s\n' "$DAY_END_STAMP" "$CYCLE" "$DAY_DIR"
} >> "$LOOP_LOG"
