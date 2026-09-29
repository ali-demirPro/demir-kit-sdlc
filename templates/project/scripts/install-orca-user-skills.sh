#!/usr/bin/env bash
# Install only product-owner Orca skills (not internal/gate skills).
# Run from product repo root. Set KIT_ROOT if kit.root is not ./demir-kit
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KIT_DIR="${KIT_ROOT:-demir-kit}"
KIT="file://${ROOT}/${KIT_DIR}"

SKILLS=(kit-feature kit-build kit-build-change kit-upgrade)

for s in "${SKILLS[@]}"; do
  echo "Installing $s from ${KIT_DIR} ..."
  npx skills add "$KIT" --skill "$s"
done

echo "Done. Verify: orca skills installed"
