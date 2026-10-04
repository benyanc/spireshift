# Anchored trajectory policy training

Issue #124 adds a policy-only update from the verified multi-run trajectory collection. It starts
from accepted base-v2 and keeps its terminal-value, tactical-risk, and floor heads byte-for-byte
unchanged. Accepted base-v2 stays in production until a later frozen full-run comparison supports
promotion. This implementation does not train an adaptive thinking controller.

The owner-run base-v6 experiment has completed with a rejected candidate. Epoch 2 exceeded the
frozen development-validation regret limit. Keep base-v2 accepted; the next owner-run command is
the [saved policy diagnosis](trajectory-policy-diagnosis.md), rather than repeating this training
recipe or evaluating the rejected candidate through new game runs.

## Frozen experiment

The recipe is `configs/trajectory-policy/sts2-v0.107.1-base-v2-frontier-preferences-v1.json`, identified
by `sha256:e774e71b33497e74ea759c36884e2b065a82c66745d164640a73f3a47a545055`. It binds every input,
including parent checkpoint/report, collection, original base-v2 anchor and validation curricula,
source-search report/config, complete-run split, ruleset, and terminal-victory objective.

The collection is verified against saved source-search cases and frozen ranks without opening an
engine or replaying games. Both source schemas are reconstructed through the same document builder
used by exact replay, with strict equality and content hashes. Public input construction verifies
observation hashes, rejects privileged fields, and preserves ordered legal actions. Ties and
regressions remain accounted for. Duplicate or conflicting public state/action comparisons, missing
cases, changed provenance, or non-train ownership fail closed.

The 25 floor/boss improvements receive unit weight. The 43 damage/health improvements receive 0.25
weight. The 11 distinct-state-count-only comparisons receive zero weight, leaving 68 usable pairs.
These are directional comparisons from selected, fixed-seed continuations. A binary pairwise target
is a classification direction, not an empirical or calibrated probability of winning.

One complete-run assignment covers both old anchor data and new preferences: 60 fitting runs and
20 selection runs. There are 50 eligible fitting preferences (20 floor/boss) and 18 selection
preferences (five floor/boss). No run is used for gradients and selection in this update. The parent
previously trained on its complete anchor corpus; the selection subfold is held out from this update,
not from the parent's pretraining. Contributions are normalized by complete run so longer lineages
and more captured states do not automatically dominate.

The update uses 40 deterministic full-batch AdaGrad steps with learning rate 0.0005, parent-policy
cross-entropy anchoring strength 2.0, preference strength 1.0, and a parameter-drift penalty of 0.1.
It updates only policy weights. Candidate weights are quantized before assessment. There is no
all-run refit after checkpoint selection, no hidden-world sampling, and no new trajectory generation.

## Frozen checks

An epoch qualifies only if its eligible preference loss and its separate floor/boss preference
loss both improve by at least 0.001 on complete-run selection data. It must also pass the existing
auxiliary-policy checks and, relative to the parent on selection anchor data:

- increase pairwise loss by no more than 0.01;
- reduce decisive-pair accuracy by no more than 0.02;
- increase mean progress regret by no more than 0.0002;
- keep mean policy-distribution total variation at or below 0.05.

The smallest qualifying selection preference loss chooses the checkpoint; ties keep the earlier
epoch. The same non-regression limits are then checked once on the parent's original development
validation curriculum. Validation never contributes gradients or chooses epochs. This reused
curriculum is development evidence, not an untouched final test.

If no epoch qualifies, the saved policy matches the parent and the report records selected epoch
zero. If the selected epoch fails validation, it is rejected without trying another validation blend
or selecting a different checkpoint against validation. Either rejection is preserved as a normal
completed experiment. A rejected or unchanged candidate cannot be loaded into the production
playing policy. A passing candidate still needs a separate, frozen complete-run evaluation before
promotion; improved fit to a small preference collection is insufficient.

Reports preserve rank-component and per-run diagnostics, all exclusions, parent comparisons,
policy drift, selection history, immutable non-policy head identities, and a short inference audit
on saved public validation inputs. Inference timing is diagnostic and depends on hardware. Existing
checkpoint formats stay supported; the new checkpoint/report formats are v6.

All source continuations lose. The new report contains zero positive terminal-victory labels, and
the terminal-value head stays blocked. This experiment cannot authorize terminal-value readiness,
learned-PUCT readiness, or adaptive-controller training.

## One owner-run command

From the repository directory, run only:

```bash
bash scripts/train-trajectory-policy-v1.sh
```

The script performs input verification, policy training, and the saved-data validation audit under
one resource cap: one worker, at most one wall hour, two CPU hours, 4 GB memory, and 1 GB output.
There is no automatic follow-up job. Existing outputs are refused rather than overwritten. The
coding agent must not launch or monitor this job.

The terminal prints selected epoch, candidate eligibility, validation checks, policy metrics, and
artifact identities. The checkpoint/report are written under `artifacts/models/sts2-v0.107.1-base-v6`;
the resource report is `artifacts/resources/trajectory-policy-base-v6-train-v1.json`. Share that
terminal summary after it finishes. The result determines whether a full-run comparison is justified.
