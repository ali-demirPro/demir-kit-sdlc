#!/usr/bin/env bash
# OPTIONAL wrapper — canonical install is scripts/install-orca-user-skills.sh at product repo root.
# Copy to product root only if you want ./install.sh; otherwise use scripts/ only.
#
# Usage (if copied to product root):
#   ./install.sh                 # owner skills via scripts/install-orca-user-skills.sh
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
  npx skills add https://github.com/stablyai/orca --skill orchestration --global
  npx skills add https://github.com/stablyai/orca --skill orca-cli --global
fi

exec "${ROOT}/scripts/install-orca-user-skills.sh"
