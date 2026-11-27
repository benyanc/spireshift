# Small native A8 decision-learning controls

**Complete and assessed.** Both players and both methods pass the finite diagnostic.
The full repository check also passed. See the [result and important novelty limits](native-tactical-learning-result.md).
No repeat collection or fitting is needed; the owner command only verifies saved results.
The preparation notes and short-control limitations below remain historical.

The [completed 256-attempt policy comparison](native-policy-update-comparison-result.md)
does not demonstrate improvement. The owner chose to assess it before scaling, then
test understandable decisions before structured-input and value-baseline changes.
This implements that first follow-up without changing the prepared/completed trial.

## What is tested

Two isolated fixtures use the actual frozen v0.111.0 game rules, Ironclad/A8,
the qualified public projection and the unchanged 512-feature / 32-hidden-unit policy:

1. **Finish this combat with the first move.** A native Whirlwind has 20 energy;
   Defend and End Turn remain legal. Only a live native combat-to-reward transition
   earns the diagnostic success. We do not infer X-cost damage from card text.
2. **Survive the next advertised enemy attack.** Native Defend and Strike remain
   legal with End Turn. Fixture setup advances to an attacking turn and sets low HP
   from current public attack/block facts. Every candidate is executed; unless it
   already ends the turn, the fixed continuation is End Turn. Native death or an
   observed next player turn determines the outcome, never an estimated HP penalty.

Each candidate starts in a fresh isolated native process/profile. All counterfactual
branches must reproduce an identical public root, and exactly one action must succeed.
An unexpected/tied/unlabelable case stops and remains preserved; no invented lesson,
silent exclusion, retry of uncertain delivery or new full-run reward follows.
The public actor receives no fixture goal, answer, native seed or hidden RNG state.

These are **privileged short-horizon diagnostics**, not ordinary full-run PPO data,
natural full games, a new victory definition or a public-belief-search benchmark.
20 energy and injected HP/cards are deliberate test setup, not a standard natural
A8 starting position. Target selection and discount/setup sequences remain separate
additional cases; this pair does not establish mastery of all mechanics or interactions.

## How learning is isolated

Both saved original players are copied with every Adam moment/counter intact;
the files remain read-only. Compare two isolated methods with matched actual updates:

- **Sampled-reward PPO on the native-backed diagnostic bandit.** Fresh action draws
  look up their actual collected native outcome. The baseline is the exact expected
  diagnostic return under the current policy, independent of the chosen action.
  This intentionally removes critic-estimation noise; passing it does not qualify
  the production 20-feature baseline or the much longer full-run credit problem.
- **Direct teaching.** Cross-entropy trains the unique verified successful action
  on the same fitting contexts and the same realized PPO minibatch/epoch work.
  Raw action scores are not regressed onto outcome numbers.

Keep original actor rate, entropy, clipping, temperature and all trainable actor
layers. Disable the separate diagnostic value loss/rate; the state-value head stays
unchanged. The batch has 64 sampled choices. A zero-variance credit batch skips the
whole copied optimizer, including matched teaching work, to avoid warm-momentum drift.

Shuffle candidate rows and map rewards/labels back to native actions; verify reversed
menu probabilities. A zero-rate warm-Adam negative control must leave weights intact.
Use disjoint complete seeds for fitting and final held-out evaluation, record fitting
curves separately, and never choose an epoch from held-out answers. Count duplicate
public roots across the splits rather than calling all held-out seeds unseen states.
Predeclared diagnostic criterion: minimum fitting success probability >=80%, minimum
held-out probability >=75%, and 100% held-out greedy accuracy, per method/player.
These thresholds are diagnostic, not the project's base-readiness gate.

## Short control completed

The resumable control finishes **four native roots / 12 candidate branches**, on
one fitting and one held-out world. The first root is sealed in one session and the
other cases/fits resume without replaying it. Both players fit their lessons:

| Player / method | Minimum fitting probability | Minimum held-out probability | Held-out greedy accuracy | Diagnostic criterion |
| --- | ---: | ---: | ---: | --- |
| 2 / PPO | 99.69% | 98.46% | 100% | pass |
| 2 / teaching | 99.59% | 96.94% | 100% | pass |
| 3 / PPO | 99.86% | 64.17% | 100% | not met |
| 3 / teaching | 99.79% | 50.33% | 100% | not met |

Before fitting, mean fitting success is 41.08% / 63.26%; mean held-out success is
50.87% / 46.52%. Parent 3 still has weak confidence on the two held-out roots.
This very small control qualifies execution and shows fitting can work; it is not
a broad generalization result or proof of a particular full-run failure cause.
The four roots are distinct public inputs. There are 76 matched learning updates
across the four copied methods, plus two zero-rate optimizer controls. The originals
and complete Adam states remain unchanged; no production optimizer is advanced.

Total saved session time is **32.82 seconds**, including the earlier first-root
session; the resource-tracked continuation takes **24.57 seconds / 263.09 MB** peak
RAM and retains **9.19 MB**. No app copies or full-run attempts. Earlier failed
prototypes remain private under `artifacts/native-tactical/probe-v1` / `probe-v3`;
the repaired two-family probe v4 passes. Those probe seeds are excluded from this
control and the main study. The main study excludes the control's seeds too.

## Preserved finite owner stage preparation (now complete)

Use 32 new native worlds: 24 fitting and eight held-out. Both fixtures yield
**64 roots / at most 192 native candidate branches**. After collection, both
methods/player copies receive **256 fixed diagnostic rounds**; sampling a saved
outcome is not another native game. At most 3,072 fitting optimizer updates across
the four methods, with realized work reported. Original players remain unchanged.

Expected **10–20 minutes for the diagnostic**, not a training-to-strength estimate.
The short native cases and an offline timing-only check support this estimate:
four fitting rounds at main-sized row counts take 2.40 seconds, extrapolating to
about 154 seconds per player's 256-round fit. That timing check repeats two old
worlds, supplies no new independent evidence and contributes no starting weights.

The new focused tests, formatting and strict types pass. The full repository suite
reaches about 92% before the four-minute agent-run cap, with no reported assertion
failure; **full verification remains pending**. The owner command first runs the
complete repository check with a 15-minute cap. A failed/capped check stops before
any new native fixture or fitting. A passing check is saved against the exact
repository files and reused on unchanged resumptions. No local commit is made
before this full check passes.

Allow **15–25 minutes including checks**. Close STS2, then run only:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-tactical-learning-v1.sh
```

Each session has a 15-minute / 1,800-CPU-second / 2-GB-memory / 1-GB-output cap.
One invocation continues the same finite plan across clean session boundaries,
up to one hour. Completed cases and fits resume; an unfinished unit stops for
inspection and is never silently retried. Workers share the frozen game/runtime/
SDK/support cache, so each fixture creates only its small private profile/evidence.
The wrapper verifies/displays an existing final result without collecting or fitting.

No full-run scale-up, checkpoint promotion, adaptive controller or next experiment
follows. Assess these results before implementing the next queued representation
comparison. The objective, original weights, optimizer states and earlier negative
results remain preserved. See [evidence](evidence/native-tactical-learning-v1.json)
and the [ordered backlog](backlog.md).
