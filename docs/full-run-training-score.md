# Full-run training score

**Historical difficulty-label correction:** the first unified pilot revealed that the pinned
engine has fixed higher-Ascension rules while this profile declares Ascension 0. The original
profile and IDs remain preserved, but it is not valid A0 evidence. Resolve
[#141](https://github.com/benyanc/spireshift/issues/141) and declare the actual verified backend
difficulty in a new profile before further learning. The score formula itself is unchanged;
see [the pilot diagnosis](full-run-pilot-v1-diagnosis.md).

Implemented under [#136](https://github.com/benyanc/spireshift/issues/136). This gives future
full-run evolution and neural training a useful way to distinguish losing players. It does not
train a player or run games. Next: [#137](https://github.com/benyanc/spireshift/issues/137), the
unified compact policy.

## Plain-language rule

- A complete game victory scores **1**.
- An ordinary complete loss gets a small score for completed acts and the furthest total floor.
  The score stays below **0.25**. Completing an act outweighs reaching more floors at the prior
  act count.
- Crashes, unsupported states, stalled runs, time/compute caps, truncations and missing runs get
  **zero**, including zero progress credit. They stay in the planned denominator.
- Extra actions, turns, HP, gold or repeated rooms earn nothing. It is one whole-episode score,
  not a reward paid each time the same state appears.
- When ranking evolutionary players, compare **win rate first**, then auxiliary progress, then
  completion rate. A mixed average score is reported for training diagnostics, never used to
  override a higher measured win rate.

The pinned profile is `configs/training-objective/sts2-v0.107.1-full-run-bootstrap-v1.json`:
Ironclad, Ascension 0, admitted v0.107.1 ruleset, three acts, 128 CPU seconds per run. Its learner
objective is `full-run-progress-bootstrap-v1`; the real game's binary environment/evaluation
objective remains `terminal-victory-v1`.

## Exact formula and examples

With completed acts `A` and maximum public **total run floor** `F`:

```text
ordinary loss return = 0.25 * (A + F / (F + 16)) / 4
victory return = 1
failure return = 0
```

| Recorded outcome | Learner score | True terminal reward |
| --- | ---: | ---: |
| Loss at total floor 7, no act cleared | 0.01902 | 0 |
| Loss at total floor 17, no act cleared | 0.03220 | 0 |
| Loss after one act clear, total floor 17 | 0.09470 | 0 |
| Full-run victory within the compute allowance | 1 | 1 |
| Floor 40 followed by a crash, stall or cap | 0 | 0 |

The floor scale 16 is a normalization constant, not a full-run floor limit. Health/resource
preservation remains observable input and diagnostics rather than a competing reward.

Gradient learning on this temporary score can still prefer a progress strategy that does not
maximize eventual wins. The score is deliberately labeled a proxy; separate win evaluation and
a later terminal-only training stage address that risk. It is not a win-probability value target.

## Reusable interface

`TrainingScoreSpec` loads and validates the configuration and computes its SHA-256 identity.
`TrainingOutcome` contains only seed metadata, terminal/failure status, normalized public act/floor
progress, decisions and CPU time. `TrainingPanel` declares the original planned seeds and stores
one outcome per seed. Duplicates, unplanned seeds, unknown fields, nonfinite/invalid numbers,
scope/configuration mismatches and final-test panels are rejected. Missing outcomes are inserted
as zero-scored failures, not dropped. Reports include separate true wins, auxiliary/mixed returns,
failure counts, recorded work and an immutable report identity.

The seed is record metadata, never a policy input. The scorer checks normalized data; the future
collector must verify public progress, terminal outcomes and run/split ownership. It must use
actual observable act transitions or confirmed clears, not infer clears from floor thresholds or
assume that every first act is Underdocks. The admitted engine's floor counter carries across
acts. Do not feed privileged engine or RNG state into the policy.

The saved-input commands are `objective inspect`, `objective score` and `objective graduation`.
They never create an environment, fit weights or follow up with another task. Inspection only
needs the score config. Scoring/graduation require new normalized panel files from the collector;
legacy teacher/evaluation JSON files do not silently become these panels. An output path is
exclusive: an existing result is preserved and the command reports an error.

**There is no long-running command for the owner at this stage.** Inspection and synthetic scoring
are covered by local checks. The next implementation builds the player that consumes the score.

## Switching to terminal-only training

The frozen initial trigger requires three distinct train victory seeds, three distinct development
victory seeds, at least 64 planned development runs, disjoint panels and no failed/missing cases.
`assess_training_graduation` returns a recommendation only. A later declared recipe uses
`full-run-terminal-training-v1`, stage `terminal_only`, and loss progress weight zero. Thus loss
returns become zero and population ranking ceases to prefer floor progress.

This trigger is an experimental staging rule, not evidence that the foundation scorecard passes
or that the player is significantly better than a baseline. Exact campaign panels, resource caps,
statistical comparisons and elite confirmation are frozen separately under
[#140](https://github.com/benyanc/spireshift/issues/140).

See [ADR 0002](decisions/0002-full-run-bootstrap-training.md) and the [backlog](backlog.md).
