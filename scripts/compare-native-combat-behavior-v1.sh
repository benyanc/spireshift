#!/usr/bin/env bash
set -euo pipefail
SPIRESHIFT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$SPIRESHIFT_ROOT"
exec uv run --no-sync python scripts/native-combat-behavior-v1.py "$@"
