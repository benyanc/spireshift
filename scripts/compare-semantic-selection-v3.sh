#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
printf '%s\n' \
  'Comparing both unchanged players on two new worlds, up to 128 choices per host.' \
  'Close STS2. One fixed app is reused. At most 15 minutes per launch.' \
  'Run this same command after a clean pause; completed pairs are reused.' \
  'No training, optimizer updates, promotion or automatic follow-up.'
exec bash "$repo_root/scripts/check-semantic-selection-v2.sh" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-semantic-selection-canary-v1.json"
