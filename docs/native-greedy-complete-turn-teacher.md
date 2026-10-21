# Fresh-training-world complete-turn teacher with greedy continuation

This bounded teacher tests whether alternative complete turns produce useful
full-run lessons when later combat follows the existing policy greedily. It builds
on the [fresh-game behavior result](native-combat-behavior-result.md), where greedy
combat modestly improved average progress for both saved players. That result did
not establish useful teaching labels, wins or additional search benefit.

Both exact round-60 models, all Adam moments and counters **5,658 / 6,045** remain
unchanged. This collector never fits a model, promotes a checkpoint or starts
another experiment. The original objective remains complete-run victory within
**128 CPU seconds**; the existing auxiliary bootstrap score is unchanged.

## Fresh source games

Freeze **eight new TRAIN game seeds**, alternating the two saved players: four
distinct worlds per player. They exclude all 28 previously registered native seed
manifests, including the inspected development comparison. Two separate control
seeds are also excluded. Both source schedules and all parameters are frozen before
the native control; only its passed report/audit references are filled afterward.

Play each natural source game with greedy combat and temperature-0.8 sampled
noncombat decisions using the qualified native engine, full benchmark unlocks and
fixed Ironclad/A8 rules. Source sampling captures the first eligible public position:

- Within the first 512 decisions, floor at least five and combat round at least two.
- A current native player play phase, with 3–12 advertised legal actions, including
  one end-turn choice and at least two play/use choices.
- Displayed enemy attack exceeds current block, with explicit public attack amounts.

This is a sampling proxy, not an exact damage forecast or a handwritten reward.
The root, compact public prefix, full current menu, greedy first action and selection
evidence are sealed immediately, **before later source outcomes exist**. The source
then finishes normally and its delivery and choices are audited. One source game
supplies at most one position; there is no final-score ranking or replacement seed.

Sources that fail or never reach an eligible position remain in the original
eight-world denominator with their reason. They provide no comparison lesson.
This is a small conditional combat curriculum, not representative whole-game
win-rate evidence or an exhaustive mechanics sweep.

## Generate turns, then compare them

At every usable root, generate one complete greedy reference turn and one sampled
turn for **every legal first move**, including end turn and offered potion controls.
Force that first move and sample the rest of the turn at the predeclared temperature
of 1.2. No action is filtered by its estimated quality or distance from the parent.

The native engine applies changing costs, targets, draws, relic hooks and card
effects. Include nested card/subset/generated-card selections, including those
triggered by ending the turn. Stop at an observed public next-round/postcombat/room
boundary or genuine ending. A kill needs no invented end-turn action. Unknown
ownership, changed targets/costs or a missing boundary fails that attempt. Turn plans
have the existing 64-decision / 1 MB limits; incomplete plans are never lessons.

Seal each plan before its first later decision. Proposal games finish only to close
and audit their native workers. **All source games and all proposed turns are
resolved before scored comparisons start.** Deduplicate exact public traces in
fixed proposal order, retaining aliases and the greedy reference first. Candidate
selection accepts plan identities and actual measured CPU, not final floors, wins,
HP rankings or bootstrap returns. A failed proposal blocks its entire root rather
than selecting convenient surviving alternatives.

Replay each frozen turn from its exact natural source prefix, checking every public
observation, current action/target and turn boundary. Afterward, use **greedy combat,
including combat-owned nested selections**, and the same sampled noncombat policy
at temperature 0.8. There is no additional fight search or HP-based selector.

Continuation draws are keyed by root, repeat, public room, family and visit.
Candidate identity, proposed-turn length and extra combat actions cannot shift
matched noncombat slots. Identical effective inputs at the same slot must yield
identical choices/probabilities; changed health or resources can legitimately change
the policy's noncombat choice. Forced prefixes and turn generation consume none of
these future draws. The source and proposal streams remain separately recorded.

## Costs and evidence

Budget proposal generation cumulatively at **64 CPU seconds per root**, with at most
32 seconds for each proposal game. Those are conservative full episode costs,
including prefix replay and closure, not just the proposed turn. An exhausted budget
does not restart for the next first move and cannot silently force a partial plan.

The greedy reference is the cheap no-search comparison and is charged no proposal
overhead. Each alternative comparison is charged **all of that root's proposal
episode CPU**, without amortization, plus its own episode CPU, under the unchanged
128-second whole-run ceiling. Preserve execution CPU and charged CPU separately.
Physical resource totals charge collection work once; per-comparison accounting
intentionally recharges reused proposals. The teacher is not a deployed search
player or a measurement of search's full-run benefit.

Use **eight matched noncombat continuation streams per unique turn**. Save wins,
acts, floors, bootstrap returns and paired changes against the greedy reference.
Retain the existing one-sided sign rule, within-root Bonferroni adjustment and
no-observed-win-regression requirement. Two-stream controls admit no preferences.
Do not weaken the rule because results tie or because no useful labels appear.

This is an explicitly **privileged fixed-hidden-world teacher**. Eight streams
vary later noncombat sampling; they are not eight independent draw orders or eight
independent games from the population. Greedy combat may make many streams identical.
Report ties and independent source coverage. Every student observation remains
public; later plan observations may not be added to its starting-state input.
Episodes are marked ineligible for ordinary PPO and public-belief optimality claims.

## Finite execution and short qualification

The main upper bound is **944 native attempts**: eight source games, at most
104 proposal games and 832 scored comparisons before exact-trace deduplication.
Missing sources remain explicit, and actual proposal/menu counts are frozen from
public roots before any scored comparisons. No new source replaces an unavailable
world. The small native control uses one fresh world per player, a greedy turn and
one different-first-move turn, two streams per plan and one exact repeated reference
per world: **16 total native attempts**.

The control must pass exact root/plan replay, genuine endings, repeated public
traces, matched noncombat behavior and a saved audit reconstructing every choice,
probability, root selection, CPU charge and lesson table. A main recipe cannot run
before matching native and saved-choice controls pass. This establishes scoped
implementation correctness, not stronger play or readiness.

Use one isolated native worker at a time, sharing the frozen game, runtime, SDK and
support code. **Zero game-app copies**. Seal each attempt and retain compact paths
and outcomes, loading at most one full episode during audits. A verified failed
worker is retired; block that root and continue other predeclared worlds. More than
two failures stop the pilot. A changed source prefix, uncertain delivery, changed
evidence or an uncommitted attempt stops for inspection and is never retried.

Main sessions are capped at **15 minutes / 1,800 CPU seconds / 2 GB memory / 4 GB
cumulative output**, with a two-hour invocation limit. Each native episode is capped
at 120 wall seconds and 4,096 decisions. The same command resumes only sealed work
at clean session boundaries. Stage progress is shown every eight resolved attempts.
An already complete command verifies and displays saved results.

## Single owner command

The native control completes **16/16 attempts** with zero failures, skipped branches,
app copies or optimizer updates. Both exact reference repeats match. Four paired
candidate/reference streams share **28 matching noncombat slots**, including **12
identical-input choices** with identical probabilities. Runtime is **90.79 seconds**,
52.75 CPU seconds, 396.82 MB peak memory and 37.66 MB cumulative output.

The saved audit reconstructs **all 1,792 decisions**, source selection, plans and
boundaries, continuation draws/probabilities, cost charges and lesson tables in
**53.29 seconds**, with no games or fitting. It verifies journal hashes without a
new independent semantic delivery audit. Four unique turns contain 13 actions and
no nested selections in this short sample; unit checks and preserved earlier native
qualification cover the reused nested boundary behavior. No exhaustive content or
playing-strength claim follows these controls.

Host-disabled main preflight verifies **75,022 protected earlier files** and both
complete model/Adam byte seals. It creates no main workspace and changes only
passed control/audit references from the pre-control main template, in **72.96
seconds**. The repository check passes **2,110 tests (52 new; four skipped)**,
strict types on 424 files, formatting/lint and the C# protocol in **122.76 seconds**.

See [portable qualification evidence](evidence/native-greedy-complete-turn-teacher-v1.json)
for the frozen identities, controls, resource receipts and exact scope.

The long collection has **not started**. Allow roughly **30–90 minutes**, based on
the control's complete-game timings; actual menus, episode lengths and exact-trace
deduplication determine the workload. The invocation limit is two hours; cleanly
paused work continues with the same command.

With STS2 closed, run from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-greedy-turn-teacher-v1.sh
```

Share its final summary. No training or further experiment follows automatically.
Assess reliable better/worse turns and whole-world coverage before preparing a
separate bounded student update. Preserve both parents and their complete optimizer
states; any trained student needs fresh full-game evaluation. Base readiness still
precedes adaptive thinking.
