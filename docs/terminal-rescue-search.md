# Terminal-rescue combat search

The exact-state intervention diagnostic rejected scalar search margin as a general override gate.
It found one narrow deterministic signal: when every paired simulation defeated the base action and
none defeated the search action, the intervention was beneficial three times, tied four times, and
harmful zero times across five train seeds. This rule directly represents imminent simulated death
avoidance and does not require fitting a classifier to the insufficient intervention labels.

Combat-advancement configuration v3 adds the `terminal_rescue` override rule. It executes a search
action only when all of these conditions hold:

- search selects a different legal action from the base checkpoint;
- both paired base-action rollouts terminate in defeat;
- the selected search action has zero paired defeats;
- search value exceeds base value by at least 0.20.

Every search trace records the base and search terminal victories, defeats, bootstrapped leaves,
rule eligibility, and execution decision. Legacy v1/v2 configuration and policy identities are
unchanged.

The frozen preflight compares base, shadow, and applied terminal rescue on 16 train seeds beginning
at offset 96. This window is disjoint from the 16 seeds used to derive the rule. An applied rule may
advance only when shadow exactly preserves base, all runs complete, no base victory is lost, mean
maximum floor improves, more seeds improve than regress, progress per CPU-hour is positive, and no
executed override violates the terminal-rescue condition. The specification is
`sha256:f5fde31b9555527a49978aeded257b416c13b55e289b450536ee9abde73f3edb`.

## Next operator command

Run this one resource-capped command and return its final output. It is sustained exact-engine work
and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/combat-search-terminal-rescue-preflight-v2.json \
  --metrics artifacts/resources/combat-search-terminal-rescue-preflight-v2-metrics.json \
  --artifact-root artifacts/evaluations/combat-search-terminal-rescue-preflight-v2 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-combat-search \
    configs/combat-search-diagnostic/sts2-v0.107.1-base-v3-terminal-rescue-train-v2.json \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/combat-search-terminal-rescue-preflight-v2
```
