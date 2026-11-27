#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$task_root"
exec uv run --no-sync python scripts/native-greedy-turn-teacher-v1.py "$@"
