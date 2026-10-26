#!/usr/bin/env bash
# Vendor sync wrapper. Implementation: vendor_sync.py
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/vendor_sync.py" "$@"
