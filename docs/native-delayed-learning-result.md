# Completed delayed-decision comparison

The production learner learns both controlled delayed tasks using either its
existing learned baseline or the exact diagnostic baseline. Both players pass
the fitting and held-out criteria. This makes a general inability to learn
two- or three-action consequences less plausible as the explanation for stalled
full-game performance. It does not establish good full-run credit or strategic play.

## What the owner completed

The fixed recipe completes **94 / 94 sealed units, 24 trees / 12 native worlds,
204 native branches, 16,384 sampled diagnostic sequences and 868 optimizer steps**.
Eight worlds supply fitting situations; four different worlds are held out.
All four final players are frozen before held-out evaluation. Both arms begin
with identical numerical weights, full Adam state and sampled first batches.

The tasks require Thunderclap then Bludgeon to finish an encounter, or Footwork
then Defend then End Turn to survive the enemy attack. No immediate action
achieves either goal. Upgrade and native hand-order variants remain included,
and every legal continuation has an observed native transition. Intermediate
actions receive no extra reward: the goal boundary supplies binary success/failure.

Both arms use the production encoder, sampler, ridge implementation and PPO
update/settings. The exact baseline is the current policy's expected success,
not the best action's value. Privileged fixture setup, recorded finite trees and
diagnostic terminal rewards remain separate from ordinary full-game experience.
Repeated tree samples are not 16,384 independent native games.

## Fitting and held-out results

Probabilities below are exact expectations over each frozen policy's possible
paths in the native diagnostic trees. They are not full-run victory probabilities.

| Player / baseline | Initial mean fitting success | Final mean fitting success | Mean held-out success | Lowest held-out success | First fitting pass round | New optimizer steps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 / learned | 34.34% | 99.980% | 99.982% | 99.950% | 4 | 42 |
| 2 / exact | 34.34% | 99.992% | 99.991% | 99.987% | 4 | 382 |
| 3 / learned | 34.85% | 99.910% | 99.920% | 99.815% | 8 | 60 |
| 3 / exact | 34.85% | 99.977% | 99.979% | 99.955% | 7 | 384 |

Every final copy succeeds greedily on all **16 fitting / eight held-out cases**.
The frozen fitting rule is minimum success probability at least 80% plus complete
greedy success; held-out minimum is 75% plus complete greedy success. All pass.
No fitting criterion fails again after the first passing round in this study.
The four-round integration control's earlier player 3 learned failure is preserved;
it is not erased or reclassified by this longer fixed schedule.

The eight held-out public roots are distinct from all 16 fitting roots. They
still reuse the same two task patterns, fixed encounter and limited upgrade/order
variants. Four held-out worlds and two fixed parents do not establish broad
mechanics coverage, long-horizon generalization or baseline superiority. Tiny
differences near the ceiling are not grounds for selecting a winning method.

## Why some rounds say zero updates

The learned arms skip **114 / 108 rounds**, respectively. In every skipped batch,
all 32 sampled sequences succeed. The fitted baseline is also effectively one,
so raw credit `success - predicted_success` is essentially constant. Its centered
variance is below the existing `1e-16` guard, which skips the entire update.
This prevents old Adam momentum from moving the model without a varying signal.

The exact baseline can retain small differences between states even when all
sampled sequences succeed, so its update count is larger. The guard/settings are
identical in both arms. A skipped round does not prove perfect play: the weakest
learned-arm held-out case still has approximately a 0.185% failure probability.
The study has reached its fixed limit; more identical easy samples are not the
next priority.

## Preservation, resources and audit

Both original players retain every numerical weight and Adam moment/counter
**5,658 / 6,045**. All historical forks, four experience-comparison finals, control
results and four new diagnostic finals are preserved separately. These specialized
copies are not promoted or used as ordinary full-game parents.

The owner's one launch takes **695.73 wall seconds / 444.96 CPU seconds**, peaks
at **356.94 MB RAM** and retains **244.30 MB**. There are no full-run attempts,
app copies, new readiness passes or adaptive-controller permissions. This assessment
does not launch any native branch, refit a baseline or advance any optimizer.
Exact source identities and saved-only verification are recorded in
[the result evidence](evidence/native-delayed-learning-result-v1.json).

The independent saved-only audit passes in **59.88 seconds / 308.43 MB peak**.
It verifies **75,658 source files, all 94 receipts, 204 native branch paths and
372 goal-path deliveries**, clean worker shutdown, exact imports and every
checkpoint's Adam counter lineage. It inspects all 512 saved rounds, reconstructs
eight initial/final-chunk boundary batches using saved coefficients without
refitting, and reproduces all four final fitting and held-out evaluations.
All 17 wholly zero-step chunks preserve numerical weights and every Adam moment
exactly. Other skipped rounds are inspected through their sealed records; their
updates are not rerun. This audit reuses original native delivery evidence and
does not constitute another engine replay or new test of the task mechanics.

Repository verification passes **2,428 tests (five skipped)**, strict types on
520 files, formatting/lint on 709 files and the C# protocol in **133.69 seconds**.
No production source, experiment recipe or stored player is modified for this
assessment. The backlog and GitHub #35 / #143 / #146 reflect the completed result.

## Next work

Close this diagnostic and keep both original players as the parents. The useful
next step is a finite native teacher/curriculum test on natural multi-turn TRAIN
situations with different decks, relics, health and later encounters. It should
show reliable alternative-action consequences and learning on withheld worlds,
then test one declared student intervention in fresh full games. The existing
varied bank supplies provenance and sampling coverage, not optimal-action labels;
historical roots require explicit replay qualification under the repaired public
counter contract.

Longer-horizon credit, useful experience coverage, rare strategic choices and
the transfer of local skills into full runs remain open. Do not assume any one
is the confirmed cause, silently adopt a rejected rich predictor, repeat unchanged
bulk PPO, select a diagnostic fork or start another experiment automatically.
