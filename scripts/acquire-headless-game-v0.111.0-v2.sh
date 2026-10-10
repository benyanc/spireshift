#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -gt 1 ]] || [[ $# -eq 1 && "$1" != "--qr" ]]; then
  printf 'Usage: bash scripts/acquire-headless-game-v0.111.0-v2.sh [--qr]\n' >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then
  exec uv run spireshift engine download-game \
    configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json \
    configs/engine-qualification/sts2-v0.111.0-depotdownloader-v1.json --qr
fi
exec uv run spireshift engine download-game \
  configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json \
  configs/engine-qualification/sts2-v0.111.0-depotdownloader-v1.json
