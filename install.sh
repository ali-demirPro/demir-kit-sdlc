#!/usr/bin/env bash
# Install demir-kit owner Orca skills from this kit checkout.
# Run from kit repo root (demir-kit-sdlc or vendored demir-kit/).
#
# Product repos: ./scripts/install-orca-user-skills.sh (from templates/project/scripts/).
# Platform skills: run this script with --with-platform from kit path, e.g. ./demir-kit/install.sh --with-platform
#
# Usage:
#   ./install.sh                 # owner skills only
#   ./install.sh --with-platform # + orchestration, orca-cli (global)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
KIT="file://${ROOT}"

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
  npx skills add https://github.com/stablyai/orca --skill orchestration --global
  npx skills add https://github.com/stablyai/orca --skill orca-cli --global
fi

SKILLS=(kit-feature kit-build kit-build-change kit-upgrade)

for s in "${SKILLS[@]}"; do
  echo "Installing $s ..."
  npx skills add "$KIT" --skill "$s"
done

echo "Done. Verify: orca skills installed"
