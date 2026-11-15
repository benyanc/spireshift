#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
attempt=1
while [[ -e "artifacts/resources/native-linear-value-repository-owner-v1-${attempt}.json" ]]; do
  attempt=$((attempt + 1))
done
printf '%s\n' "Running the full repository check only: no training, game attempts or follow-up stage."
printf '%s\n' "The earlier check reached about one-third before its four-minute cap. Allow up to 20 minutes."
exec uv run --no-sync spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-linear-value-repository-owner-v1-${attempt}.json" \
  --artifact-root artifacts/native-linear-value/repository-check-v1 \
  --workers 1 \
  --max-wall-seconds 1200 \
  --max-cpu-seconds 2400 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 4000000000 \
  -- uv run --no-sync spireshift check
