#!/usr/bin/env bash
# Root entrypoint. Implementation lives in delivery/scripts/install.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "${ROOT}/delivery/scripts/install.sh" "$@"
