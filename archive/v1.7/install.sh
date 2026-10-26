#!/usr/bin/env bash
# Install demir-kit owner Orca skills.
# Run from kit repo root (git clone) OR from vendored demir-kit/ inside a product repo.
#
# Product repos: ./scripts/install-orca-user-skills.sh (from repo root).
#
# Usage:
#   ./install.sh                 # owner skills only
#   ./install.sh --with-platform # + orchestration, orca-cli (global)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

WITH_PLATFORM=false
for arg in "$@"; do
  case "$arg" in
    --with-platform) WITH_PLATFORM=true ;;
    -h|--help)
      echo "Usage: ./install.sh [--with-platform]"
      exit 0
      ;;
  esac
done

if [[ "$WITH_PLATFORM" == true ]]; then
  echo "Installing Orca platform skills (global) ..."
  npx skills add https://github.com/stablyai/orca --skill orchestration --global -y
  npx skills add https://github.com/stablyai/orca --skill orca-cli --global -y
fi

RESOLVER="${ROOT}/tools/resolve-skills-source.sh"
if [[ ! -f "$RESOLVER" ]]; then
  echo "install.sh: missing tools/resolve-skills-source.sh"
  exit 1
fi

# shellcheck source=/dev/null
source "$RESOLVER"

if [[ -d "${ROOT}/.git" ]]; then
  KIT="file://${ROOT}"
elif [[ -f "$(dirname "$ROOT")/kit.config.yaml" ]]; then
  PRODUCT_ROOT="$(cd "$(dirname "$ROOT")" && pwd)"
  KIT="$(resolve_skills_source "$PRODUCT_ROOT")"
else
  KIT="$(resolve_skills_source "$ROOT")"
fi

SKILLS=(kit-feature kit-build kit-build-change kit-upgrade)

echo "Skills source: ${KIT}"
for s in "${SKILLS[@]}"; do
  echo "Installing $s ..."
  npx skills add "$KIT" --skill "$s" -y
done

echo "Done. Verify: orca skills installed"
