#!/usr/bin/env bash
# Behavior gate for one checkpoint. Replace with the repo's real checks.
set -euo pipefail
CHECKPOINT="${1:?checkpoint id required, e.g. CP-1}"
echo "gate-behavior: ${CHECKPOINT}"

npm run typecheck
npm run lint
