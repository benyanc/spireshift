# Controlled teaching and fresh-game test

The owner authorized this separate test after the earlier/coordinated teacher
comparison. It uses the useful fitting plans already collected; it starts no new
teacher search and leaves the failed natural-v1 curriculum unchanged. Both original
players and their complete Adam states remain read-only at **5,658 / 6,045** steps.

## The comparison

Each of the two fixed initializers supplies three versions:

| Version | What changes |
| --- | --- |
| Original | Nothing; import exact numerical weights and every Adam moment/counter. |
| Reference copy | Teach the original greedy actions from the two fitting fights. |
| Improved-plan copy | Teach the better verified actions from the same two fights. |

The reference copy controls for the effects of additional training on these
situations. Both trained copies also need comparison with the untouched original;
beating a degraded reference copy alone does not establish improvement.

Fitting-only selection picks the **single-change 23-HP rescue** on world 148 and
the **coordinated 48-HP win versus 31-HP reference** on world 192. It uses the best
confirmed winning plan from either method, with stable single-change preference
on ties. The historical teacher's fixed-world resource guards are retained.
The copied public lesson bank contains:

- Reference plans: **20 / 11** meaningful decisions across the two worlds.
- Improved plans: **20 / eight** meaningful decisions.
- Separate diagnostics for the **one / two** changed choices.

Only exact public menus, public state and legal action indices enter the learner.
Hidden engine state, returns, source outcomes and native debug endings do not
become model inputs. Teacher outcome comparisons remain explicitly privileged
to their fixed source worlds and are not ordinary PPO experience.

Both useful fitting worlds originate from player 2. Both preserved numerical
initializers use this same bank; that does not create additional independent
training worlds. The four held-out worlds supply no fitting labels, epoch choice,
regularization setting or final-player selection. The two unimproved fitting
worlds are not silently converted into successful lessons.

## Fixed teaching work

Each trained copy receives **16 epochs × four updates × 32 sampled choices**:
**64 updates / 2,048 example draws**. The four copies total **256 updates**.
Worlds have equal weight, with independent within-world position draws, so longer
fights do not dominate. This matches work and world contributions, not identical
states or trajectory lengths between reference and improved demonstrations.

The loss is categorical imitation of legal actions. Actor learning rate is
0.001, temperature 0.8 and gradient norm cap 1.0. There is no new HP/floor reward,
action-score return regression, PPO update or proximity-to-original rejection.
The existing categorical gradient, original encoders and inherited Adam update
are reused. Actor parameters may change; critic weights and the credit predictor
stay unchanged. Numerical originals and all their Adam state remain untouched.

Every epoch saves the full copied model and optimizer. Root-balanced example loss,
target probabilities and final changed-choice probabilities/greedy choices are
reported separately. These measure learning of the saved actions; they do not
themselves prove a better player.

All four fixed final epochs and both originals are sealed in a shared final-state
barrier **before any native fitting-fight, held-out-fight or fresh-game evaluation**.
There is no best-epoch selection or fitting after evaluation. Earlier checkpoints
remain available for diagnosis without being selected from evaluation outcomes.

## Native evaluation

The main experiment then runs:

1. **36 natural-fight checks:** two fitting roots and four held-out roots, each
   played by both initializers and all three versions. The original saved opening
   is replayed exactly to the root, after which the evaluated player makes its
   own choices. Improved actions are not forced. These check whether the learner
   can execute useful behavior and whether it transfers between situations.
2. **192 fresh full games:** 32 fresh native seeds × two fixed initializers ×
   three versions. All start from the normal benchmark lobby without a saved
   combat prefix. Combat is greedy and noncombat sampled with the same existing
   public-state/navigation/behavior-stream rules for every version. Shared actor
   changes may affect noncombat choices; decision families remain available.

Order rotates across seeds/initializers. Fresh panels exclude earlier declared
training, development, tactical, teacher and control worlds, including the new
integration-control seed. Terminal victory under the unchanged **128-CPU-second
whole-run budget** remains primary. Floors, act completion and the old bootstrap
return are separate diagnostics. The original reward and score specifications
are not changed by the imitation loss.

Results retain each initializer separately and pool paired differences by native
world, clustering both fixed initializers together. The fixed percentile bootstrap
uses 10,000 resamples and seed 20261020. Thirty-two independent evaluation worlds
are not 192 independent worlds, and uncertainty does not cover a population of
training initializers. This is a small exploratory transfer test, not readiness.
If all observed wins are zero, resampling those zeros can produce a zero-width
win-difference interval. That does not establish equal population win probabilities;
this small panel has limited power for rare full-run victories.

Failed games remain in the original denominator with zero win/progress value.
A verified retired failure can be followed by the next planned game, without
retrying its seed; more than two technical failures stops the finite study.
Corrupted receipts, uncertain delivery or unverified shutdown stop for inspection.
Ordinary combat losses are valid outcomes and do not stop evaluation.

## Storage, resumption and qualification

The frozen app, runtime, SDK and support cache are shared; **no game app copy** is
created. Each native attempt has its own mutable profile and sealed evidence.
The 28,046,877-byte lesson bank and historical source evidence are input artifacts
outside the phase output accounting. The wrapper reads every output/resource path
from the pinned recipe.

Main uses one worker, **15-minute wall / 1,800-CPU-second / 2-GB-memory / 3-GB-phase
output** session caps. Whole-session timing includes input validation. New native
work requires 180 seconds remaining for the bounded attempt, audit and shutdown;
fights retain the qualified 60-second whole-prefix/fight cap, 192 remaining actions
and 12 observed rounds. Full games retain 120 wall seconds and 4,096 decisions.
The wrapper runs at most three sessions per invocation. Clean pauses restore
completed receipts, full weights and Adam exactly. Existing uncommitted directories
or changed checkpoints are never cleared or overwritten automatically.

Fourteen new tests cover exact public label binding, fitting-only selection,
fixed work, disjoint canonical worlds, frozen-final ordering, failed/missing-game
denominators, exact real-gradient resumption with warm Adam, unchanged originals,
one-failure continuation, changed receipts and open-game refusal before activation.

The short native integration control completes **16 units / nine native attempts**
in **107.93 seconds**: one epoch/four updates per trained copy, three fitting-fight
checks on player 2 and six fresh games on one separate seed. All delivery and
fixed-work checks pass, with **zero errors / 495.24 MB peak / 74.67 MB output**.
Its fitting-fight checks still lose and its six full games win zero times; those
are reported, not a basis for tuning or refusing the separately fixed main test.
This is runner qualification, not evidence of stronger play. Main imports the
originals, not these trained control copies.

A separate **41.06-second saved-only assessment** verifies **106,359 sources /
16 sealed units**, reproduces all **16 copied optimizer updates** and the full
weights/Adam exactly, and repeats all **nine native delivery audits**. It
reconstructs all six full-game behavior traces, checks the final-state barrier
and original hashes, and passes main read-only preparation without creating its
workspace. Its v1 verifier incorrectly compared raw action count with the list
excluding forced navigation; that failed audit is preserved. The corrected v2
checks both counts separately. Neither audit replays a game or changes the runner.

Repository verification passes **2,485 tests / five skips**, formatting/lint,
strict types on 544 files and the C# protocol build in **147.13 total wall seconds**.
The main workspace remains absent. The original game, numerical parent states,
Adam states and historical pinned implementations are unchanged.

## Owner next

Close STS2, then run this one command:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/test-native-plan-teaching-v1.sh
```

Allow roughly **30–60 minutes**. Rerun this same command after a clean pause if
needed. Every eight newly recorded full games, output shows wins, average floor,
best floor and failures. This finite invocation fits and evaluates only this
declared test; no further collection, PPO training, promotion or adaptive
controller follows. Share the saved final report for assessment.

See [portable evidence](evidence/native-plan-teaching-test-v1.json) and
[the completed teacher result](native-coordinated-teacher-result.md).
