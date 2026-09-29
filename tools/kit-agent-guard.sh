#!/usr/bin/env bash
# Enforce agent-phase-gates G1/G8 — run from product repo root before commit or when agent claims "done".
# Usage:
#   ./scripts/kit-agent-guard.sh
#   ./scripts/kit-agent-guard.sh --issue 3
#   ./scripts/kit-agent-guard.sh --staged
set -euo pipefail

PRODUCT_ROOT="$(pwd)"
ISSUE=""
STAGED=false
CONFIG="${PRODUCT_ROOT}/kit.config.yaml"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --issue) ISSUE="$2"; shift 2 ;;
    --staged) STAGED=true; shift ;;
    -h|--help)
      echo "Usage: kit-agent-guard.sh [--issue N] [--staged]"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

APP_PATHS=(src app lib)
if [[ -f "$CONFIG" ]]; then
  # optional future: parse factory.app_paths from yaml
  :
fi

if $STAGED; then
  DIFF_CMD=(git diff --cached --name-only)
else
  DIFF_CMD=(git diff --name-only HEAD)
  if ! git rev-parse HEAD >/dev/null 2>&1; then
    DIFF_CMD=(git diff --name-only)
  fi
fi

CHANGED=$("${DIFF_CMD[@]}" 2>/dev/null || true)
VIOLATIONS=()

for p in "${APP_PATHS[@]}"; do
  if echo "$CHANGED" | grep -q "^${p}/"; then
    VIOLATIONS+=("app path touched: ${p}/")
  fi
done

if [[ ${#VIOLATIONS[@]} -eq 0 ]]; then
  echo "kit-agent-guard: OK (no app path changes in diff)"
  exit 0
fi

if [[ -z "$ISSUE" ]]; then
  echo "kit-agent-guard: BLOCKED — ${VIOLATIONS[*]}"
  echo "  App code changes require kit-build + agent-approved on a leaf issue."
  echo "  Re-run with --issue N after sealing, or revert src/ changes."
  echo "  See: demir-kit/references/agent-phase-gates.md (G1)"
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "kit-agent-guard: WARN — app paths changed, issue #$ISSUE set, but gh missing for label check"
  exit 1
fi

TRACKER_REPO=""
if [[ -f "$CONFIG" ]]; then
  TRACKER_REPO="$(grep -E '^[[:space:]]*repo:' "$CONFIG" | head -1 | sed -E 's/^[^:]*:[[:space:]]*//' | tr -d ' ')"
fi
[[ -z "$TRACKER_REPO" ]] && TRACKER_REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"

if [[ -z "$TRACKER_REPO" ]]; then
  echo "kit-agent-guard: BLOCKED — cannot verify agent-approved (no tracker.repo)"
  exit 1
fi

LABELS="$(gh issue view "$ISSUE" --repo "$TRACKER_REPO" --json labels -q '.labels[].name' 2>/dev/null || true)"
if echo "$LABELS" | grep -qx 'agent-approved'; then
  echo "kit-agent-guard: OK — issue #${ISSUE} has agent-approved; app changes allowed for this seal"
  exit 0
fi

echo "kit-agent-guard: BLOCKED — ${VIOLATIONS[*]}"
echo "  Issue #${ISSUE} lacks label agent-approved (labels: $(echo "$LABELS" | tr '\n' ' '))"
echo "  Run kit-build on this leaf issue first. See agent-phase-gates.md"
exit 1
