# Completed A8 policy-capacity comparison

The owner finished the fixed 64-round comparison on November 25, 2026. Extra
width did not improve full-run A8 results under this initialization and learner.
No candidate is promoted.

| Frozen evaluation policy | Full wins / games | Act 1 clears | Act 2 clears | Mean terminal floor |
| --- | --- | --- | --- | --- |
| Reference finals | 0 / 256 | 15 / 256 | 0 | 12.29 |
| Continued 32 units | 0 / 256 | 13 / 256 | 0 | 11.71 |
| Expanded 128 units | 0 / 256 | 7 / 256 | 0 | 10.64 |

Each policy used the same 128 fresh worlds and both fixed numerical initializers.
For initializer 2, Act 1 clears were 8 / 6 / 6 (reference / continued / expanded).
For initializer 3 they were 7 / 7 / 1. These are development observations, not
independent population replications or reserved final-test evidence.

The world-clustered 95% descriptive interval for the continued policy's Act 1
change versus reference spans −3.91 to +2.34 percentage points. The expanded
change spans −6.64 to 0.00 points. This experiment supplies no evidence of a win
gain from either treatment. It does not establish that every larger model is
worse. All-zero empirical win intervals do not imply the true win probability
or uncertainty is zero.

Training retained all 4,096 planned cells: 4,092 complete losses, three capped
games and the previously preserved failed potion cell. There were 256 complete
actor/critic/full-Adam fits and 16,517 copy updates: 9,231 for continued policies
and 7,286 for expanded policies. Matched optimizer work was never claimed. The
failed prefix and capped games supplied no fitting experience. Evaluation
finished all 768 games as native losses, with no capped or missing cases.

The game v0.111.0 / 41cef1ea, host60, original checkpoints, source finals and full
original Adam remain frozen. New final states remain immutable experimental
artifacts. Their training adapters and legacy evidence are unchanged. The
known Connector queue-eligibility and broader mechanics obligations remain open.
The completed evaluation reveals no new runtime failure; it does not prove
every game mechanism is covered.

The saved assessment rechecks linked unit seals, exact behavior requests,
native endings, reset evidence, all optimizer lineages and the final selection.
The full raw-public act/floor recount is a separate read-only phase in the next
owner command. The first exhaustive recount reached its short-check boundary;
its resource receipt is preserved. Raw delivery reconstruction proofs remain
bound by the original complete episode seals and evidence hashes.

## Next learning priority

The next stage measures why valid model-owned experience is not producing
stronger play. It uses saved **training** cohorts from rounds 1, 16, 32 and 64,
both initializers and both widths: 16 cohorts and 256 original games. No new
game, teacher policy, fight-specific rule, reward definition or candidate
architecture is introduced by this diagnostic.

It reconstructs each actual PPO behavior state, compound-answer likelihood and
cross-fitted credit. For each cohort it measures distinct episode returns,
single-choice frequency, credit variance, critic and cross-fitted baseline
explained variance, hidden saturation, candidate input/activation differences,
and entropy. A balanced bounded sample gives every source world equal probe
ownership. No evaluation outcome supplies a fitting label.

Synthetic positive/negative advantage probes and directional finite differences
check the policy-gradient kernel. One disposable inherited-Adam step and one
reset-Adam step use the same weights, gradients and saved minibatch. These local
steps measure optimizer behavior, not playing strength; no probe checkpoint is
saved. Source weights, optimizer clocks and every full Adam array must remain
exact. The complete diagnostic performs 32 discarded copy steps and then stops.

The short phase exercises two source games, credit reconstruction, numerical
probes, both optimizer paths and immutability. The full phase first completes
the raw-public outcome recount, then audits all 16 training cohorts. Clean sealed
diagnostic units can resume; incomplete units and all old failures are preserved.

The short phase passed in 24.21 seconds. It reconstructed 312 native decisions,
including 57 single-choice decisions, and tested 16 balanced probe decisions.
Four directional finite differences had relative error below 10⁻⁹ and both
advantage signs moved likelihood in the expected direction. Both disposable Adam
paths completed one step; no source optimizer advanced and no checkpoint was
saved. Credit/value measurements from these two games are preliminary and do
not choose the next treatment. All frozen-input checks pass.

Use the resulting evidence to choose the next broadly applicable change to
representation, credit, optimizer initialization or practice difficulty. Qualify
that change on copies, then measure sustained learning on fresh normal-start A8
worlds. More width alone has not passed the current test. There is no automatic
next training job, promotion, official-game qualification or A10 experiment.

## Owner command

```bash
bash scripts/audit-a8-learning-signal-v1.sh
```

Allow about **20–60 minutes**, with a three-hour outer cap. This reads existing
training data; it does not launch STS2 or new games. The game can remain open.
Outputs are compact diagnostics under `artifacts/native-learning-health/v1` and
the saved outcome recount under `artifacts/native-policy-capacity`. Existing
source data is excluded from the new-output cap. See the linked
[evidence](evidence/native-policy-capacity-result-v1.json) for exact reports.
