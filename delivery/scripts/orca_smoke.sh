#!/usr/bin/env bash
# Orca readiness smoke. Never starts a worker by default.
#
# Usage:
#   ./delivery/scripts/orca_smoke.sh
#   ./delivery/scripts/orca_smoke.sh --plan 17
#   ./delivery/scripts/orca_smoke.sh --create-run --objective "demir-kit #17"
#   ./delivery/scripts/orca_smoke.sh --dry-run --create-run --objective "demo"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
ORCA_BIN="${ORCA_BIN:-orca}"
DRY_RUN=false
CREATE_RUN=false
OBJECTIVE="demir-kit smoke"
PLAN_ISSUE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan) PLAN_ISSUE="$2"; shift 2 ;;
    --create-run) CREATE_RUN=true; shift ;;
    --objective) OBJECTIVE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *) echo "orca_smoke.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
done

run() {
  if [[ "$DRY_RUN" == true ]]; then
    printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

if [[ "$DRY_RUN" == false ]]; then
  if ! command -v "$ORCA_BIN" >/dev/null 2>&1; then
    echo "orca_smoke: orca not found (set ORCA_BIN or install Orca)." >&2
    exit 1
  fi
  STATUS="$("$ORCA_BIN" status --json)"
  python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("ok") else "orca_smoke: orca status not ok")' <<<"$STATUS"
  echo "orca status: ok"
  "$ORCA_BIN" skills get orchestration --full >/dev/null
  echo "orchestration skill: ok"
fi

if [[ -n "$PLAN_ISSUE" ]]; then
  python3 delivery/scripts/orca_plan.py "$PLAN_ISSUE" --json
fi

if [[ "$CREATE_RUN" == true ]]; then
  run "$ORCA_BIN" orchestration run-create --objective "$OBJECTIVE" --json
fi

echo "orca smoke: done (no worker started)"
