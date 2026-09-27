# Combat-resolution rescue diagnostic

The short-horizon terminal-rescue preflight changed seven trajectories without improving a single
run. Every executed search branch was censored and bootstrapped after eight transitions, so its lack
of a sampled defeat showed only temporary survival. Combat-advancement v4 addresses that exact
failure without changing the completed v1-v3 identities.

Each candidate/world branch now has one explicit outcome:

- `run_victory`: the complete run won inside the search budget;
- `run_defeat`: the complete run lost inside the search budget;
- `combat_clear`: play left combat at a nonterminal public decision;
- `censored`: the branch remained in combat when its hard transition horizon ended.

The `combat_clear_rescue` rule is eligible only when every paired base branch ends in run defeat and
every paired search branch either clears combat or wins the run. Censored branches cannot qualify.
The rule also retains the 0.20 minimum search advantage, but this train diagnostic runs it in shadow
mode and never changes the base trajectory.

Every retained recommendation records the complete source public observation and each branch's
complete resolved public observation, plus per-world outcome, transition count, floor, and HP.
Verification recomputes every public-state hash, the outcome aggregates, the transition budget, and
the eligibility decision, and rejects any resolution-boundary, count, or identity mismatch.

The frozen specification uses 24 train runs beginning at offset 112, disjoint from the original
intervention and terminal-rescue preflight windows. It retains at most two eligible recommendations
per seed. The content identities are:

- search configuration: `sha256:4d568d5ac6d2e6b90ca29cfa1e537824b5f394e43e965ecfa97445a15ee6f816`;
- intervention specification: `sha256:b59252c63ced6f83f5e4e182da99f5c85f1a7d5fb34d7631fc08fa62b4410452`.

A later full-run train preflight is authorized only if all cases and counterfactuals complete, at
least eight qualifying interventions span at least four seeds, at least one is beneficial, and none
is harmful. The report always emits `validation_allowed=false`. If this gate fails, tactical rescue
stops; neither another horizon nor another scalar threshold is justified.

## Next operator command

Run this one resource-capped command and return its final output. It is sustained exact-engine work
and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/combat-resolution-intervention-v2.json \
  --metrics artifacts/resources/combat-resolution-intervention-v2-metrics.json \
  --artifact-root artifacts/evaluations/combat-resolution-intervention-v2 \
  --workers 1 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 14400 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model evaluate-combat-search-interventions \
    configs/combat-search-intervention/sts2-v0.107.1-base-v3-combat-resolution-train-v2.json \
    artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/evaluations/combat-resolution-intervention-v2
```
