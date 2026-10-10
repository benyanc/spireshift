#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

attempt=1
while [[ -e "artifacts/resources/actual-engine-source-v1-attempt-${attempt}.json" ||
         -e "artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/source-inspection-v1-attempt-${attempt}.json" ]]; do
  attempt=$((attempt + 1))
done

printf '%s\n' \
  'Extracting the exact frozen game for a private source audit: one worker, 20-minute tool cap.' \
  'This first full extraction is unmeasured; allow roughly 5–15 minutes.' \
  'No game attempts, training, file publication or automatic follow-up.' \
  'Each explicit rerun preserves earlier results and starts a fresh source attempt.'

uv run spireshift resources run \
  --kind other \
  --report "artifacts/resources/actual-engine-source-v1-attempt-${attempt}.json" \
  --artifact-root artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/private-source-v1 \
  --workers 1 \
  --max-wall-seconds 1320 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run spireshift engine inspect-game-source \
    configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json \
    configs/engine-qualification/sts2-v0.111.0-source-inspection-v1.json \
    --output "artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/source-inspection-v1-attempt-${attempt}.json"

printf '%s\n' 'Private extraction finished. Share the summary above; no next stage follows.'
