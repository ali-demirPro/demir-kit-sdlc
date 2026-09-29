#!/usr/bin/env bash
# Wrapper — run from product repo root.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KIT_DIR="${KIT_ROOT:-demir-kit}"
exec "$ROOT/${KIT_DIR}/tools/kit-upgrade.sh" "$@"
