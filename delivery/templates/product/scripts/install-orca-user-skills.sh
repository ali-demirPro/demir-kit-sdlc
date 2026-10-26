#!/usr/bin/env bash
# Install v2 runtime skills from the vendored kit.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${ROOT}/demir-kit/install.sh" --with-platform "$@"
