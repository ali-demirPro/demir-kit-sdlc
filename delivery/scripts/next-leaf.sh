#!/usr/bin/env bash
# Dependency-aware leaf queue. Implementation: next-leaf.py
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/next-leaf.py" "$@"
