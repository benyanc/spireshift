#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Open the existing Steam client; the owner explicitly pastes the download command.
# No credentials, downloads, beta changes, game launches or monitoring happen here.
spireshift_game_download=$(uv run spireshift engine download-command \
  configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json)
printf 'Opening Steam console. Paste this one command there to start the exact macOS download:\n\n%s\n\n' "$spireshift_game_download"
printf 'This downloads a separate depot copy. Keep this terminal output and wait for Steam to say Depot download complete.\n'
printf 'Send that completion line back; do not switch beta branches, replace the installed game or start training.\n'
open 'steam://open/console'
