#!/usr/bin/env bash
# Install only product-owner Orca skills (not internal/gate skills).
# Run from product repo root. Set KIT_ROOT if kit.root is not ./demir-kit
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KIT_DIR="${KIT_ROOT:-demir-kit}"
RESOLVER="${ROOT}/${KIT_DIR}/tools/resolve-skills-source.sh"

if [[ ! -f "$RESOLVER" ]]; then
  echo "install-orca-user-skills: missing ${RESOLVER}"
  exit 1
fi

# shellcheck source=/dev/null
source "$RESOLVER"
KIT="$(resolve_skills_source "$ROOT")"

SKILLS=(kit-feature kit-build kit-build-change kit-upgrade)

echo "Skills source: ${KIT}"
for s in "${SKILLS[@]}"; do
  echo "Installing $s ..."
  npx skills add "$KIT" --skill "$s" -y
done

echo "Done. Verify: orca skills installed"
