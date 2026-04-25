#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT/.automoat/state"
LOG_DIR="$ROOT/.automoat/logs"
RUNS_DIR="$ROOT/.automoat/runs"
LOCK_DIR="$STATE_DIR/loop.lock"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$RUNS_DIR/$STAMP"
RUN_LOG="$RUN_DIR/output.log"
META_FILE="$RUN_DIR/meta.txt"
LOOP_LOG="$LOG_DIR/loop.log"
LAST_RUN_FILE="$STATE_DIR/last-run.txt"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUNS_DIR"

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

mkdir -p "$RUN_DIR"

{
  echo "started_at_utc=$STAMP"
  echo "pid=$$"
  echo "host=$(hostname)"
  echo "cwd=$ROOT"
} > "$LOCK_DIR/meta.txt"

{
  echo "run_dir=$RUN_DIR"
  echo "started_at_utc=$STAMP"
  echo "pid=$$"
  echo "host=$(hostname)"
} > "$META_FILE"

if [[ $# -eq 0 ]]; then
  cat >&2 <<'EOF'
usage: scripts/codex-loop.sh -- <command> [args...]

example:
  scripts/codex-loop.sh -- codex exec "Read LOOP.md and NEXT_TASK.md, then make one bounded improvement."
EOF
  exit 64
fi

if [[ "$1" == "--" ]]; then
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "no command provided after --" >&2
  exit 64
fi

printf 'command=' >> "$META_FILE"
printf '%q ' "$@" >> "$META_FILE"
printf '\n' >> "$META_FILE"

{
  printf '[%s] START ' "$STAMP"
  printf '%q ' "$@"
  printf '\n'
} >> "$LOOP_LOG"

set +e
(
  cd "$ROOT"
  "$@"
) 2>&1 | tee "$RUN_LOG"
CMD_STATUS=${PIPESTATUS[0]}
set -e

END_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

{
  echo "ended_at_utc=$END_STAMP"
  echo "exit_status=$CMD_STATUS"
} >> "$META_FILE"

{
  printf '[%s] END status=%s dir=%s\n' "$END_STAMP" "$CMD_STATUS" "$RUN_DIR"
} >> "$LOOP_LOG"

{
  echo "last_run_dir=$RUN_DIR"
  echo "ended_at_utc=$END_STAMP"
  echo "exit_status=$CMD_STATUS"
} > "$LAST_RUN_FILE"

exit "$CMD_STATUS"
