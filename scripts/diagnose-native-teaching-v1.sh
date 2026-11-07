#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python scripts/diagnose-native-teaching-v1.py "$@"
