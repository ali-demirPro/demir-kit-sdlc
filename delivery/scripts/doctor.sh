#!/usr/bin/env bash
# demir-kit doctor — contract enforcement entrypoint.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${DIR}/doctor.py" "$@"
