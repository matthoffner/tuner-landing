#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT_MESSAGE="${1:-chore: automated loop update $(date -u +%Y%m%dT%H%M%SZ)}"

cd "$ROOT"

if [[ -f "generated/landing.html" ]]; then
  cp "generated/landing.html" "index.html"
fi

if [[ -n "$(git status --short)" ]]; then
  git add -A
  git commit -m "$COMMIT_MESSAGE"
  git push origin main
fi
