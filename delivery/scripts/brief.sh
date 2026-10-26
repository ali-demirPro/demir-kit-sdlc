#!/usr/bin/env bash
# Delivery agent brief. Implementation: brief.py
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/brief.py" "$@"
