#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python scripts/compare-coordinated-teacher-v1.py "$@"
