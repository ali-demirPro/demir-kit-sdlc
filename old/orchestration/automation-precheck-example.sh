#!/usr/bin/env bash
# Orca automation --precheck example: run only if an agent-approved issue exists.
# Usage in: orca automations create ... --precheck "$(pwd)/orchestration/automation-precheck-example.sh" ...
set -euo pipefail
REPO="${DEMIR_GH_REPO:-}" # optional: owner/repo for gh -R
ARGS=()
[[ -n "$REPO" ]] && ARGS=(-R "$REPO")
count="$(gh issue list "${ARGS[@]}" --label agent-approved --state open --json number -q 'length')"
[[ "$count" -gt 0 ]]
