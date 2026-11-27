#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if [[ $# -ne 0 ]]; then printf '%s\n' 'This saved-only check takes no arguments.'; exit 1; fi
node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then node_runtime="$(command -v node || true)"; fi
if [[ ! -x "$node_runtime" ]]; then printf '%s\n' 'Set SPIRESHIFT_NODE to the local Node runtime.'; exit 1; fi
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
printf '%s\n' 'Auditing saved act transitions and the privileged victory fixture. No games or training follow.'
uv run spireshift engine verify-native-progression "$qualification" \
  configs/engine-qualification/sts2-v0.111.0-native-run-progression-v6.json
uv run spireshift engine verify-progression-bridges "$qualification" \
  configs/engine-qualification/sts2-v0.111.0-progression-bridges-v4.json --node "$node_runtime"
uv run spireshift engine audit-saved-progression "$qualification" \
  configs/engine-qualification/sts2-v0.111.0-progression-saved-audit-v1.json --node "$node_runtime"
printf '%s\n' 'All three targeted transitions verify. Forced fixture wins are excluded from player wins and learning data.'
