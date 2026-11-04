#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
printf '%s\n' 'Checking reward guidance, enchantment previews, distinct card copies and matching public inputs on four matched pairs. Both players and Adam remain unchanged.' \
  'Close STS2. Up to 30 minutes for the comparison, six minutes per pair; full checks have a separate 10-minute cap.' \
  'The previous interrupted attempt stays preserved. Completed pairs from this new plan are reused.' \
  'One fixed app, isolated profiles and no training or automatic follow-up.'
cd "$repo_root"
exec uv run --no-sync python "$repo_root/scripts/selection-flows-session-v4.py" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-enchantment-preview-canary-v1.json" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-enchantment-preview-launch-v1.json"
