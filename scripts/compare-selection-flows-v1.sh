#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
printf '%s\n' 'Checking four matched pairs on new worlds. One fixed app; unchanged players and Adam.' \
  'Close STS2. This launch allows 30 minutes for the whole batch, with six minutes per pair.' \
  'Repository checks have a separate 10-minute allowance; successful checks are cached for these exact files.' \
  'Completed pairs are saved and reused after an interruption. No training follows.'
cd "$repo_root"
exec uv run --no-sync python "$repo_root/scripts/selection-flows-session-v1.py" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-selection-flows-canary-v1.json" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-selection-flows-launch-v1.json"
