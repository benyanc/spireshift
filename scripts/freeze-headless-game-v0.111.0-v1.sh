#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# This stage is separate from the download and never launches a game or follow-up.
# An explicit source path may be supplied if Steam downloaded to a different library.
spireshift_freeze_config=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
if [[ $# -gt 1 ]]; then
  printf 'Provide at most one completed depot directory.\n' >&2
  exit 2
fi
if [[ $# -gt 0 ]]; then
  exec uv run spireshift engine freeze "$spireshift_freeze_config" --game-dir "$1"
fi
exec uv run spireshift engine freeze "$spireshift_freeze_config"
