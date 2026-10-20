# Later-turn action comparisons

**Completed:** the owner collected all 456 branches. Receipt/outcome/table assessment
finds 74.0% paired ties and zero admitted preferences. The clearest poor actions
already have very low policy probability. See [result and next work](native-later-combat-teacher-result.md).
No collector rerun is needed. The preparation and command below are retained as history.

The rich correction test produced no useful forecast gain, so the current coarse value
predictor stays in place. This next experiment returns to action learning: compare all
offered actions at positions where a choice might matter more. It prepares numerical
lessons; **it does not change either player or start training**.

The original combat teacher completed 384 branches, but 78.1% of its matched comparisons
tied and none passed its exploratory preference rule. All eight positions were at fight
entry. Here the deliberate change is **public root sampling**. Reuse the same native
branch/replay implementation, original fixed-world information scope, unchanged full-run
score, players, continuation sampling and uncertainty/preference rules. Historical code,
data, negative results, weights and every Adam moment remain unchanged.

## Frozen selection

Use the final ordinary standard round-60 TRAIN batches, with each source game's own
recorded actions and binding. The final round-60 player for that numerical initializer
continues each experimental branch. Root selection never ranks by final floor, return,
win, candidate outcomes or value predictions. No evaluation histories are decoded.

Retain the fixed source-path ordering from v1. Within a source run, choose the earliest
eligible position for the needed encounter type, at prefix index at most 512. It must:

- Be an ordinary public combat play menu at floor five or later, round two or later.
- Offer 3–12 actions, exactly one end-turn control and at least two play/use candidates.
- Show a known displayed enemy attack total exceeding the player's current block.

The attack-minus-block amount is a **sampling proxy**, not an exact HP-loss prediction,
new reward or hand-coded ranking of actions. Native statuses, costs, relics, card effects
and subsequent decisions still determine the real outcome. Every offered action is
compared, including potion/discard controls; filtering roots does not narrow the actor's
legal action space or restrict future learning to combat.

The initial symmetric quota was unavailable: the second player's saved batch has no
qualifying later boss menu. The failed preparation and exact source snapshot remain
private, with zero game attempts. Before any new branch outcomes, freeze the available
eight-root curriculum: player 2 contributes two normal fights, one elite and one boss;
player 3 contributes three normal fights and one elite. No combat criterion, confidence
rule or return definition is relaxed. The result has **five normal / two elite / one
boss**, not two balanced boss examples. It cannot establish broad boss competence.

There are eight distinct source worlds, **57 offered actions**, public rounds 2–4 and
source floors 5–17. This is not a matched same-position comparison against v1. Different
worlds/positions and the asymmetric available curriculum limit causal or population claims.

## Counterfactual collection and lessons

Replay the source prefix in a fresh isolated native process/profile. Every public input
and action order must agree before forcing the chosen action. Then let the unchanged
player finish the run. Use temperature 0.8, zero extra rest exploration and eight matched
continuation-policy streams per action: **456 planned branches**. Preserve the full legal
decision scope, terminal objective, auxiliary bootstrap score, 128-CPU-second whole-run
budget, 60-second per-branch wall limit and 4,096-decision limit.

As in v1, the hidden engine world is the original source world; only continuation-policy
samples vary. Different actions can consume engine randomness differently. These are
conditional fixed-world hindsight experiments, explicitly marked privileged teacher data
with public student inputs. They are **not fresh on-policy PPO games**, independently
resampled hidden worlds, public-belief-optimal labels or policy win-rate evaluation.

Save complete action-return tables, full wins, floors, means and uncertainty. The existing
one-sided sign rule against the frozen reference and within-root Bonferroni adjustment
remain unchanged. Two-sample control tables cannot admit preferences. Do not lower gates
to force positive labels. Conversely, zero admitted preferences need not mean all table
information is unusable: separately declared exploratory value/ranking supervision may
use uncertain means, including evidence of poor actions, while retaining uncertainty and
testing independent gameplay. Such supervision is **not implemented or automatically
started by this collector**. Confidence gates must not be misrepresented as proof of
expected-return optimality or as a permanent actor proximity constraint.

## Short checks completed

The short control uses one qualifying position per player, all their offered actions,
two continuation streams and one repeated reference branch each. **24/24 branches finish
normally**, with no failures, skips, wins, model updates or game app copies. Both repeated
public traces are identical. The resource session takes **99.08 seconds**, 70.15 CPU
seconds, 367.33 MB peak RAM and 42.32 MB private output. Frozen game/runtime/SDK/archive
and the account profile remain unchanged.

Saved-record verification processes one episode at a time. It reconstructs every source
prefix, forced choice, continuation probability/value and whole-run return, rebuilds the
action tables and verifies branch receipts and source seals without starting a host.
It verifies native journal **bytes**; native delivery semantics were audited during each
branch and are not reaudited by this separate saved-policy check. These controls verify
collection correctness, not that the new lessons improve a model.

The final saved-only audit verifies **3,950 public decisions across all 24 branches**,
including continuation probabilities/values and exact task, world and model bindings.
It reproduces all action tables in **25.85 seconds** (131.38 MB peak RAM), with no new
game attempt. Its two-sample paired counts are one higher-return alternative, six lower
and 11 ties against the references. These are overlapping, conditional comparisons;
they do not establish better learning or independent outcome coverage.

All **1,927 repository tests** pass, including 23 new sampling/reconstruction regressions,
with strict types on 387 files, formatting/lint and the C# protocol contract. The full
check takes **129.74 seconds** (101.49 CPU seconds, 268.27 MB peak RAM). The post-check
audit verifies **12,711 protected source files** and both complete player/Adam states.
Reopening the completed control and reading the pilot plan also pass with native host
launches explicitly disabled. At preparation, the pilot workspace did not exist yet.

## Historical owner handoff before collection

At preparation, the 456-branch pilot had not started. The frozen collection command,
run with STS2 closed and from any directory, was:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-later-combat-teacher-v2.sh
```

Allow roughly **30–45 minutes**, estimated from the 99-second 24-branch control. Longer
prefixes and continuation lengths can change the total. The wrapper uses one native
process at a time, 15-minute sessions, 2 GB memory and 4 GB retained-output limits. It
stops starting sessions before the two-hour invocation limit. Shared immutable game,
runtime, SDK and support code are reused; **zero app copies** are planned.

Complete branches are sealed and reused at clean session boundaries or on a later rerun
of the same command. Changed or uncommitted evidence stops for inspection. Uncertain
delivery is never replayed automatically. Failures stay in the original denominator;
verified failed workers are retired, their root is blocked and other planned roots may
continue. A prefix mismatch stops collection. No automatic training, model promotion,
adaptive controller or new experiment follows completion. Send back the final summary.

## Next step after the result

The completed result is assessed in [the result note](native-later-combat-teacher-result.md).
The following was the predeclared decision path:

Reconstruct the saved action tables and assess non-tied outcome differences, uncertainty
and source diversity. Do not select a convenient subset using evaluation results or call
456 branches 456 independent seeds. If useful signal exists, freeze a bounded supervised/
credit intervention in separate forks of **both current players and full Adam states**,
then compare fresh whole-game gameplay at equal compute. Keep all strategic decision
families learnable and full wins primary. If the later roots remain flat, decide on a
coherent-turn or stronger-continuation change before expanding the same collection.
The current predictor remains in use; another critic grid, other ascensions, large GA
batches and adaptive thinking are not prerequisites.

See [backlog](backlog.md) and [portable preparation evidence](evidence/native-later-combat-teacher-v2.json).
