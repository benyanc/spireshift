#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$repo_root/scripts/check-input-layout-v3.sh" \
  "$repo_root/configs/native-compatibility/sts2-v0.111.0-a8-input-layout-canary-v3.json"
