#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
spireshift_config=configs/engine-qualification/sts2-v0.111.0-mechanics-followups-v1.json
spireshift_qualification=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
IFS=$'\t' read -r spireshift_workspace spireshift_sequences spireshift_progression spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run python - "$spireshift_config" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["resource_limits"]
with open(recipe["sequence_config"]) as stream:
    sequences = json.load(stream)
with open(recipe["progression_config"]) as stream:
    progression = json.load(stream)
print("\t".join(str(v) for v in (recipe["workspace"], sequences["workspace"],
    progression["workspace"], limits["wall_seconds"],
    limits["cpu_seconds"], limits["storage_bytes"], limits["resident_memory_bytes"])))
PY
)
if [[ -f "$spireshift_workspace/summary.json" ]]; then
  printf 'Verifying the saved follow-up result; no new game attempts follow.\n'
  uv run spireshift engine verify-mechanics-followups "$spireshift_qualification" "$spireshift_config"
  exit 0
fi
spireshift_attempt=1
while [[ -e "artifacts/resources/native-mechanics-followups-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-mechanics-followups-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'The current full mechanics sweep must finish successfully first. Its code and results are read-only.\n'
printf 'Then check nine random legal prefixes and native act/ending transitions on the same frozen engine.\n'
printf 'Four independent game seeds, two independent action RNG seeds and one exact repeat; at most 256 decisions each.\n'
printf 'Bounded prefixes are not completed games or evidence of player strength. Skip remains selectable.\n'
printf 'One isolated worker at a time; hard cap four minutes, 4 GB memory and 1.5 GB generated evidence.\n'
printf 'The game must be closed and the previous sweep finished. No app copies, training or automatic next stage follow.\n'
uv run spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-mechanics-followups-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --artifact-root "$spireshift_sequences" \
  --artifact-root "$spireshift_progression" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- \
  uv run spireshift engine check-mechanics-followups \
    "$spireshift_qualification" "$spireshift_config" --node "$spireshift_node"
