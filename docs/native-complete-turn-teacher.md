# Complete-turn comparison teacher

This separately versioned teacher compares **whole remaining turns**, rather than
changing one card and immediately returning control to the same player. It collects
numerical lessons and tests replay correctness. It does not train or promote a model.
Both original players and their complete Adam states stay unchanged.

## Candidate generation

Reuse the eight frozen later-combat TRAIN positions from the previous teacher: five
normal fights, two elites and one boss, split across both players. Prefixes, roots,
native v0.111.0 rules, Ironclad/A8 profile and original source worlds stay fixed. No new
positions are chosen from their final scores. Reusing development positions is not
independent evidence of generalization or a causal comparison with the earlier method.

At each position, propose:

- One complete **greedy reference turn**, using the unchanged player.
- One complete sampled turn for **every legal first move**, including end turn and
  any offered potion/discard controls. Force that first move, then sample the remaining
  turn from the unchanged player at the predeclared proposal temperature of 1.2.

The native engine applies all card effects, changing costs, targets, card draws, potions
and relic hooks. Nested card/subset/generated-card menus stay in the sequence, including
choices triggered by ending the turn. A proposal stops at the next displayed combat
round, a resolved end-turn return to a combat menu, a public postcombat/changed-room
menu, or a genuine terminal ending. A kill or automatic round change needs no invented
end-turn action. These are observed public boundaries, not exhaustive interaction proof.

Each sequence records the exact public inputs and action indices. There is a cap of
64 decisions and 1 MB per plan. Unknown ownership, missing public round information or
a cap stops that attempt; no partial sequence becomes a complete-turn lesson.

The plan is sealed at its boundary **before its first continuation choice**. Proposal
workers then finish their games to close and audit native delivery normally. Those
full-run returns are diagnostic records, not candidate-selection criteria. A terminal
boundary already ends the game and has no later continuation to hide.

All proposed sequences across all roots are resolved before any scored comparison.
Exact duplicate public action traces are combined in fixed proposal order; the greedy
reference remains first, with aliases retained. Selection accepts only plan references,
never returns, final floors or wins. Failed proposal roots remain explicit incomplete
source comparisons. There is no quality-based rejection or convenient outcome subset.

## Scoring frozen turns

Replay each candidate from its exact saved source prefix in a fresh isolated native
worker. Every public observation, legal action/target and boundary must match. A changed
cost, different drawn card or premature end refuses replay; there is no fallback to
the policy halfway through a frozen sequence.

After the complete sequence, the original player continues at temperature 0.8. Proposal
and continuation randomness use separate streams. Continuation streams depend on root
and repeat, not candidate identity or proposal length. This pairs continuations without
using up their randomness while generating the turn.

The short native control uses one position per player, two streams per unique plan and
an extra exact repeated reference branch per player. The main pilot uses all eight
positions and eight streams per plan. Before deduplication, the main upper bound is
**65 proposal games plus 520 scored games: at most 585 native attempts**. The exact
comparison schedule is frozen after proposal deduplication, with all source roots kept
in the reported denominator.

Use the unchanged terminal-victory objective and the explicit auxiliary full-run score,
with the existing 128-CPU-second whole-run budget. There are no handwritten HP, damage,
block, upgrade or turn-quality rewards. Save full wins, floors, returns, standard errors
and paired differences. The existing one-sided sign rule and within-root Bonferroni
adjustment use the actual unique plan count. Two-stream controls admit no preferences.

## Information and learning boundaries

These are privileged fixed-world counterfactuals with public student inputs. Eight
continuation streams sample future policy actions, **not eight independent hidden draw
orders**. The main source coverage remains eight original worlds. Do not call these
ordinary PPO games, public-belief-optimal plans or an agent win-rate benchmark.

A sequence contains later public observations for replay. They must not be concatenated
into the starting state's student features. A future learner may receive only the
public input at the decision it is learning, with separately declared uncertain teacher
supervision. No such fitting is started by this collector. Full-run gameplay on fresh
seeds must establish any benefit; confidence labels and best sampled returns cannot
substitute for that test.

The current coarse predictor and both players' weights, Adam moments and counters
(5,658 / 6,045) remain intact. All strategic decision families stay learnable in future
full-run training. Foundation readiness still precedes adaptive thinking.

## Isolation, resumption and verification

Workers share the verified frozen game, runtime, SDK and support-code cache, with fresh
profiles and immutable receipts per attempt. **No game app copies** are created.
Completed attempts are verified and reused. Uncommitted or changed evidence is
preserved and refused; uncertain delivery is never replayed automatically.

A failed worker must prove shutdown before another source world is attempted. Its
root is blocked, remaining attempts there are recorded as skipped, and other planned
worlds may continue. A source-prefix mismatch stops the experiment. Failed/incomplete
turns cannot supply complete comparison lessons or a passing native control.

The main recipe requires both the successful matching native control and its saved-only
behavior audit. The audit reconstructs source prefixes, proposal sampling, every forced
turn step, boundaries, continuation probabilities, returns, candidate deduplication and
action tables. It checks native journal bytes; native delivery semantics are audited
during collection. It retains at most one episode and bounded public plans in memory.

The owner-run collector uses 15-minute sessions, one native process, 2 GB memory and
4 GB retained-output limits. It stops starting sessions before a two-hour invocation
limit. At clean pauses, the same command resumes sealed work. Session time is labeled
as session time; total cost must sum resource sessions, while cumulative storage must
not be added. No training, controller, promotion or next experiment follows completion.

The final control evidence, implementation checks and one owner command are recorded
in [the current backlog](backlog.md) and
[portable preparation evidence](evidence/native-complete-turn-teacher-v1.json).

## Verified checks and owner run

The short native control completes **39/39 branches**: 13 proposals become 12 unique
plans (one to five decisions), followed by 26 comparisons including the two repeated
references. Both repeated full public traces match, all boundaries replay exactly,
and there are zero failures, skips, wins, model updates or app copies. Two clean
sessions use **142.37 wall seconds total**, 108.72 CPU seconds, 390.59 MB peak RAM and
66.46 MB cumulative output. Its two positions do not exercise native nested selections;
the new unit controls cover those boundaries, alongside the previously qualified bridge.

Saved-only verification reconstructs **all 6,077 public decisions**, proposal choices,
forced sequences, boundaries, continuation probabilities, whole-run returns and tables
in **32.52 seconds** (157.19 MB peak RAM). The main recipe requires this exact audit.
All **1,979 repository tests** pass, including 52 new controls, with strict types on
396 files, formatting/lint and the C# protocol check in **118.44 seconds**. The post-check
audit verifies **30,487 protected original/control files**, with both full player/Adam
byte seals unchanged. Cached control reuse and main preflight also pass with native
host launches explicitly disabled. These are correctness checks, not stronger play.

**The main pilot has not started.** Close any running STS2 game and run this one command
from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-complete-turn-teacher-v1.sh
```

Allow roughly **30–45 minutes**, estimated from the measured control. Exact deduplication
and continuation lengths can change the total. The upper bound is 585 attempts; the
comparison count becomes exact after all 65 proposals are sealed. The wrapper continues
only this finite plan across clean sessions; if it stops at its invocation limit,
re-running the same command resumes completed receipts. No fitting follows. Send back
the final summary so we can assess whether coherent turns provide useful new lessons.
