# Combat-advancement continuation

The terminal-frontier v4 pilot completed 10,926 candidate continuations without one victory. Its
continuations lasted only about 7.45 transitions on average, and 936 of the 985 frozen source states
were combat decisions. More samples from the same policy would therefore spend compute measuring a
near-death continuation rather than create terminal-victory signal.

`combat-advancement-policy-v1` keeps the production checkpoint as the default policy and adds
bounded lookahead only when the current public decision is combat and has multiple legal actions.
Every root action receives the same hidden-world samples and the same horizon. The horizon is
reduced uniformly when needed to remain below the hard per-decision simulated-transition cap.
Hidden worlds are paired across candidates, deterministically seeded, and rejected when resampling
changes the public legal-action set. If no compatible world is found within the declared limit, the
agent uses the checkpoint's public-state action for that decision. The fallback and failed sampling
attempts are recorded separately, so the run stays valid without searching a privileged or
incompatible state.

An exact terminal win reached inside the horizon has value 1 and an exact terminal defeat has value
0. A nonterminal leaf uses the checkpoint's candidate-conditioned maximum-floor distribution and
tactical death-risk heads. Those heads are explicitly an auxiliary combat leaf heuristic. They do
not become terminal reward, they do not unblock the terminal-value head, and floor progress cannot
satisfy the final readiness gate.

The frozen v1 configuration is
`sha256:a8992807c1a1e3a6a9ac81bcc96effcf5bdd9a934cacf6c591df541a77cf68a5`:

- two paired hidden worlds per legal action;
- up to eight simulated transitions per action and world;
- at most 256 simulated transitions per combat decision;
- up to 32 deterministic rejection samples to preserve the public action set;
- a recorded policy-only fallback if those 32 samples are exhausted;
- leaf value weight 0.25 for future-floor reach and 0.75 for tactical survival. Base-v3's held-out
  tactical-risk head has positive Brier skill, while most high-floor thresholds do not, so the
  prespecified mix gives the better-supported head more influence without discarding progress.

The v5 state-set, task, worker-result, and dataset contracts bind the model, training report,
ruleset, split, objective, search configuration, and derived policy identity. Worker evidence also
records hidden-resample attempts and cumulative combat-search usage. Older v1-v4 artifacts retain
their original identities and behavior.

## Next operator command

The first train attempt is retained as failed experiment
`67ebee0e-df27-48f8-bf7d-a968234a9ed0` (report
`sha256:6a2c50a0ee7690ab2a0635b867fcd33ae8966fd52ebb47e5746a4072deaa21ad`). It
stopped after 24.15 wall seconds when a combat decision exhausted its 32 compatible-world samples;
it emitted no state-set artifact.

Run only the retry below. Its new report and artifact paths preserve the failed attempt. It reuses
the v4 train run range so maximum-floor and terminal-run results can be compared on matched seeds.
It is a sustained job and must be started and observed by the operator.

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-combat-advancement-discovery-v5-retry1.json \
  --artifact-root artifacts/bootstrap/discovery-train-combat-advancement-v5-retry1 \
  --workers 1 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap discover-states \
    configs/bootstrap/sts2-v0.107.1-evangambit-train-combat-advancement-frontier-v5.json \
    artifacts/bootstrap/discovery-train-combat-advancement-v5-retry1/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --combat-advancement-config configs/combat-advancement/sts2-v0.107.1-base-v3-v1.json \
    --run-offset 80
```

Before starting validation discovery or teacher generation, compare the emitted
`source_maximum_floor_histogram`, terminal and step-limited run counts, captured frontier coverage,
wall time, CPU time, and failures with the frozen v4 train discovery. Continue only if the policy
reaches materially later floors without a prohibitive compute or failure increase.
