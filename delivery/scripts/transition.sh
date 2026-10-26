#!/usr/bin/env bash
# State transition wrapper. Implementation: transition.py
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/transition.py" "$@"
