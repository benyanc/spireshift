#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python scripts/varied-final-canaries-session-v1.py
