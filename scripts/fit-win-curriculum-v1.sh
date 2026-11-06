#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-sync python -m spireshift.native_a8_bank_fit_session "$@"
