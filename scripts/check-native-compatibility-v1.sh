#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe=configs/native-compatibility/sts2-v0.111.0-a8-recorded-v1.json
workspace="$(uv run --no-sync python -c 'import json, sys; print(json.load(open(sys.argv[1]))["workspace"])' "$recipe")"
printf '%s\n' \
  'Checking exact checkpoints against saved official-game/CLI observations.' \
  'No games, fitting, app copies, checkpoint promotion or automatic follow-up.' \
  'A completed audit can report BLOCKED; it does not certify current live-game compatibility.'
attempt=1
while [[ -e "artifacts/resources/native-compatibility-recorded-v1-attempt-${attempt}.json" ]]; do
  attempt=$((attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-compatibility-recorded-v1-attempt-${attempt}.json" \
  --artifact-root "$workspace" \
  --workers 1 --max-wall-seconds 240 --max-cpu-seconds 480 \
  --max-storage-bytes 100000000 --max-memory-bytes 2000000000 \
  -- uv run --no-sync python -m spireshift.native_compatibility audit \
    "$recipe" "$@"
