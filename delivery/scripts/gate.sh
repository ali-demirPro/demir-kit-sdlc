#!/usr/bin/env bash
# demir-kit checkpoint gate — doctor + required suites.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/gate.py" "$@"
