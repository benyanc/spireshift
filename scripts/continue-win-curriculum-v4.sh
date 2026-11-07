#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python scripts/win-curriculum-session-v4.py
