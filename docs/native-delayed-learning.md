# Delayed native decisions: production learned versus exact baseline

**The main comparison is complete. Both baselines pass for both players.**
See the [saved-result assessment](native-delayed-learning-result.md) for the
measured results, limitations and next work item. No further run is needed.
The implementation and original qualification below remain preserved.

This diagnostic tests a gap left by the immediate-action controls: can the current
learning machinery learn sequences whose useful consequence arrives after several
actions? It uses both preserved original players and their entire Adam state.
The completed full-game comparison and all its experimental finals remain intact.

## Two native goals

| Family | Useful sequence | Terminal diagnostic success |
| --- | --- | --- |
| Vulnerable then attack | Thunderclap, then Bludgeon | Native combat-to-reward transition with the player alive |
| Dexterity then block | Footwork, then Defend, then End Turn | Player alive after the advertised native enemy turn |

All single-action outcomes fail the goal. The native engine executes every legal
continuation and validates the useful first move; outcomes are not inferred from
card text or hand-assigned HP estimates. Survival fixture HP is prepared from
advertised attack/base block amounts, but native action effects determine success.
Unupgraded, upgraded-setup and reversed-native-hand-order variants are declared in
advance. Thunderclap uses the funded coverage fixture; this is deliberately an
artificial short task, not a naturally reached full-game encounter.

Each native branch starts in its own isolated managed process/profile and exactly
replays its prefix. Public observations must match the original prefix at every
step. All native legal choices, including End Turn, remain available. No planner
prunes an inconvenient action. The horizon is three actions / the first enemy-turn
boundary. A diagnostic ending is never a full-run loss or victory.

## Production machinery and explicit differences

The diagnostic reuses:

- v11 native public projection, action binding/delivery and shutdown;
- the production `native_structured_policy.Chooser` and public encoder;
- production `public_value_features`, ridge fitting, fold assignment and predictions;
- production `native_policy_updates.update`, PPO loss, advantage normalization,
  Adam continuation, temperature, entropy, clipping, KL stop, three epochs and
  128-decision minibatches, including the existing separate value-head loss/rate.

The original full numerical weights and every optimizer moment/counter **5,658 /
6,045** are imported exactly. Only the already qualified environment metadata
migration is retained. Four diagnostic copies are stored in a separate workspace;
none is promoted or used as a new ordinary-game parent automatically.

The differences from ordinary gameplay are deliberate: privileged fixture setup,
a finite tree of actual observed native transitions, and a binary terminal subgoal.
The separate diagnostic collector/adapter is necessary because the production
ordinary-episode admission correctly rejects privileged fixtures. No record is
relabeled to bypass that boundary. Sampling a recorded transition is not a new
native game attempt. This qualifies shared learning machinery, not the full-run
collector/score/task, broad card strategy or public-belief search.

## The sole learning treatment

Both arms receive only the same kind of terminal subgoal outcome, `R = 0 or 1`.
Intermediate decisions have no extra reward. Every sampled decision has raw credit
`A = R - V(state)`; discount and trace lambda are one.

- **Learned:** the current 20-feature public ridge is fitted to other whole native
  worlds. All repeats and both task families from one world belong to the same
  fold. A trajectory's own world cannot fit its baseline. The ridge implementation
  and regularization are unchanged; world grouping extends the production ownership
  rule to correlated repeated diagnostic episodes.
- **Exact:** recursively sum terminal native outcomes weighted by the **current
  policy's** action probabilities at every future node. This is `V^policy`, not
  optimal/max-action value or a correctness label for the selected action. Its
  fixed-world future information makes it a privileged diagnostic baseline,
  unsuitable for ordinary partially observed gameplay without separate qualification.

Each copy samples its own 32 complete diagnostic sequences per round. Private
draw schedules match across arms, and the first actual histories must be identical
because their starting policies match. After learning diverges, one arm never
trains on the other's trajectories. No chosen action, future outcome, fixture goal,
seed, path or baseline answer is added to student features.

## Fixed design and interpretation

The main study uses **eight fitting and four held-out native worlds**, two families
per world: 24 trees / expected 204 native branches. These are not 204 independent
worlds. All related branches and repeated samples remain grouped by native world.
Two fixed parents × two baselines receive **128 fixed rounds**, with checkpoints
every eight rounds. Maximum sampled diagnostic sequences are **16,384** and maximum
optimizer steps are **1,536**; actual counts reflect production zero-signal skips
and KL stops. Main copies start from the original players, not control-trained forks.

Fitting curves are reported separately. All four final states freeze before any
held-out policy evaluation. The criterion is minimum fitting success probability
at least 80% and 100% greedy success; held-out minimum at least 75% and 100% greedy
success. No held-out result selects an epoch or changes the schedule.

Expected success is computed over all paths under each frozen stochastic policy;
greedy success follows that policy's highest-scored choices. Neither is a full-game
win probability. Record exact duplicate public roots and genuinely unseen held-out
cases separately. There are only two task patterns, a fixed encounter and limited
upgrade/order variation; new worlds alone do not establish broad generalization.

- Exact passes while learned fails: evidence of baseline sensitivity in these tasks,
  not proof that the same issue alone causes full-game failure.
- Both fit but transfer fails: investigate state/coverage/generalization.
- Both pass: establish this narrow production-path delayed-learning bridge; much
  longer strategic horizons and full-run usefulness remain unverified.
- Both fail: investigate actual optimization, representation and exploration; do
  not infer a baseline-only cause or simply enlarge ordinary full-game training.

## Completed short qualification

The separate control completes **16 units / six trees / 51 native branches** on
two fitting worlds and one held-out world. The two held-out public roots are
genuinely new upgraded variants. It samples 512 diagnostic sequences and makes
43 optimizer steps on copies; there are no full runs or app copies.

| Player / baseline | Initial mean fitting success | Final mean fitting success | Lowest fitting success | Held-out mean success | Held-out greedy success |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 / learned | 22.48% | 95.73% | 94.48% | 95.24% | 2/2 |
| 2 / exact | 22.48% | 94.20% | 90.99% | 91.94% | 2/2 |
| 3 / learned | 42.71% | 88.47% | **67.94%** | 96.88% | 2/2 |
| 3 / exact | 42.71% | 94.86% | 89.09% | 97.65% | 2/2 |

Execution and first-batch matching pass. **Player 3 learned does not meet the
80% weakest-fitting-case criterion after four rounds.** All four copies meet
the held-out criterion, but one held-out world does not establish a preferred
baseline or broad transfer. Do not relax the frozen threshold or interpret these
subgoals as successful full runs. The control takes **96.27 seconds**, peaks at
345.55 MB and retains 52.72 MB; originals remain unchanged.

An independent saved-only audit verifies **68,172 source files / 16 receipts /
51 native branch paths / 93 goal-path deliveries**. It checks snapshot/action/
successor ownership, exact imports and Adam counters, restores the saved ridge
coefficients without fitting, reconstructs first sampled histories and reproduces
all four finals' fitting/held-out probabilities. It takes **31.80 seconds**, creates
no games and performs no optimizer updates. This reuses native delivery evidence;
it does not replay the engine or establish exhaustive mechanics correctness.

Repository verification passes **2,428 tests (five skipped)**, strict types on 520
files, formatting/lint and the C# protocol in 135.75 seconds. The 14 new tests include
a finite-difference check of the delayed policy gradient against expected terminal
success, grouped-fold isolation and bit-exact full-state/Adam resumption. Exact
receipts and caveats are in [the evidence record](evidence/native-delayed-learning-v1.json).

## Historical owner command — already completed

The following was the prepared launch instruction. The owner has now completed
all 94 units; do not repeat the experiment. An unchanged invocation verifies and
displays its saved result. Original preparation instructions:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-delayed-learning-v1.sh
```

Allow about **15–25 minutes** based on the measured control, with 15-minute /
2-GB-memory / 1-GB-output sessions. Native processes run serially and share the
frozen game/runtime/SDK/support cache; no app copies are created. The wrapper
continues only this finite plan through clean boundaries, with a 45-minute
invocation boundary. The same command resumes completed trees, weights and all
Adam state. Uncertain or unfinished units stop for inspection without replay.
`--control` addresses the already completed tiny control; `--one` bounds a short
agent check to one new unit. Neither is required for the owner main command.

The report saves fitting curves and final fitting/held-out results, including
public-root overlap. No full-game training, checkpoint promotion, adaptive
controller or subsequent experiment starts afterward.
