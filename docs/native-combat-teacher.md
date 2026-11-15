# Native combat comparison teacher

The completed saved-game audit found connected numerical updates, but no confirmed
improvement in fresh play. This teacher adds more direct lessons: replay a known combat
position, try every legal choice, and measure what happens by the end of the game.
There are no hand-written health, damage or upgrade rewards and no model updates here.

## Completed result and next work

The owner finished **384/384 genuine terminal branches**, zero failed/skipped branches,
zero full wins and **zero admitted preferences**. The saved-result audit verifies all
384 branch receipts and rebuilds every action table from the sealed outcomes. Native
journal bytes are verified; their delivery semantics are not reaudited in that result
audit. Source/player/Adam bytes are unchanged.

Of 320 paired alternatives against the reference, **37 improve, 33 worsen and 250 tie**.
The smallest one-sided improvement sign p-value is **0.1875**. Six positions have some
variation in mean returns; two are entirely flat. All eight selected roots occur at
fight entry, so a single early card often has a small signal through the weak fixed
continuation. The original confidence rule remains unchanged.

These are **eight original hidden worlds**, not 384 independent new starting seeds.
Thirty-three branches complete an act and the best reaches floor 23, but these dependent
teacher results are not policy evaluation. No model has been trained from them.
Total resource-session time is **1,160.37 wall seconds / 940.52 CPU seconds**, peak RAM
**411.37 MB**, final cumulative output **639.71 MB**. No game app copies occur.

The next work is [richer public-state value prediction](native-public-value.md), then
a declared action-credit comparison. A future teacher should predeclare more diverse
later-turn roots, coherent turn plans or a stronger continuation. Soft value fitting
need not discard every uncertain mean, but must retain uncertainty and independent
evaluation; it cannot relabel these data as reliable optimal-action labels or fresh PPO.
See [portable result](evidence/native-combat-teacher-result-v1.json). The prior preparation
text below remains historical; there is no outstanding owner collection task for v1.

## Frozen pilot

Eight public positions come from eight distinct natural TRAIN seeds in the final
standard round-60 batches. Each of the two players contributes two ordinary fights,
one elite and one boss. Selection uses a fixed source order and the first eligible
combat menu at floor five or later, before any branch outcomes are available.
Every offered action is compared, including end turn and any potion controls.
The complete menus contain 48 actions across eight roots; the main plan therefore
has **384 full-run branches: eight continuation streams per action**.

The source games used their own recorded behavior models; no historical record is
relabeled as having come from the final player. Each root uses its own player's
unchanged round-60 standard model for the new continuation,
temperature 0.8 and zero extra rest exploration. Both full model/Adam states are sealed
and read only; original round-56 states and rest-exploration forks remain untouched.
The reference is the frozen continuation player's greedy root choice, selected before
seeing outcomes. No evaluation histories select roots, actions, weights or thresholds.

## Native replay and information limits

The host's ordinary save is a room/run save, not an exact mid-combat snapshot.
Each branch therefore starts a fresh isolated native worker and replays the source
action prefix. Every public observation and legal candidate order must match exactly
before the forced choice. Current public temporary IDs are rebound through the existing
native adapter. Continuation then uses only the current public observation and qualified
shop navigation, with every strategic decision family available.

Each root retains its **original native seed and replayed hidden world**. Matched policy
streams vary the continuation player's choices; they do not independently resample
unknown draw orders or engine RNG. Different actions may subsequently consume randomness
differently. The information scope is explicitly
`public_student_inputs_original_fixed_hidden_world_teacher`, with
`privileged_fixed_world_teacher: true`. A public-input student can learn from these
experimental hindsight labels, but they may reward knowledge unavailable to the player.
No claim about a public-belief optimum, generalization or calibrated victory probability
follows. Independent public-consistent hidden-world sampling remains a separate backlog item.

## Numerical output

Every root records its public input, candidate identity/order, source split/seed/prefix,
frozen native/adapter/model/score identities, resource use and verified delivery evidence.
Each action receives empirical full-run wins, mean bootstrap return, mean floor and a
standard error over continuation-policy samples. Standard errors are conditional on
the one original world; zero sampled variance does not imply certainty.

Terminal full-run victory remains the primary goal. The existing declared whole-run
floor/act bootstrap score is an auxiliary learner target and is never renamed a victory
probability. The native whole-run budget remains 128 CPU seconds; collection also has
an explicit 60-second per-branch wall cap and 4,096-decision limit. Capped, failed,
recovered or unverified continuations cannot supply lessons.

For an exploratory preference, an alternative must have at least eight complete matched
streams, positive mean bootstrap gain, no fewer full wins, and pass a one-sided paired
sign test against the frozen reference at `0.05 / (actions - 1)`. Ties are excluded.
This tests paired outperformance frequency, not expected return. The correction applies
within each root only. With eight samples this is deliberately demanding; the pilot may
produce no admitted preferences. Do not retune the rule to force a positive result.
Complete action-value tables can still support a separately declared experimental
value-supervision study. A preference supported only by floor/act gain is labeled
`auxiliary_bootstrap_only`.

Teacher records use an explicit non-PPO policy contract and panel purpose. Existing
behavior reconstruction rejects them as ordinary on-policy PPO. A later study must use
a separate supervised value/ranking loss and fresh native PPO data, retaining full Adam
state in separate forks and testing fresh complete games at matched compute. Teacher
collection itself performs zero optimizer steps and cannot promote a checkpoint.

## Qualification, resumption and storage

The short control checks two roots, one per player, all their actions, two streams each,
and an extra duplicate reference branch per root: 24 planned branches. The duplicate
must reproduce the entire public action trace and ending exactly. The control is capped
at four minutes; no value/preference labels from its two samples are training eligible.
Main collection requires this matching source-bound control to pass.

The control passed: **24/24 terminal branches**, no failures, skips, full wins or app
copies, and both duplicate public traces identical. It used **75.04 wall seconds**,
**59.16 CPU seconds**, **373.26 MB** peak RAM and **34.01 MB** private output. Action
tables differ in eventual floors, but two samples cannot establish action quality or
admit training preferences. Reopening the result with native launches disabled reuses
its evidence. The eight-root, 384-branch pilot passes preparation checks without games.

One fresh process/profile per branch shares the unchanged frozen game, runtime, SDK and
support-code cache. **Zero app copies** are created. Compressed journals are audited as
ordered streams, retaining at most one raw episode. Every completed branch is sealed
separately; rerunning reuses it. Partial/uncommitted branches remain preserved and stop
for inspection rather than being replayed automatically. Failed workers are retired with
shutdown proof, and the rest of that root's branches are skipped. Independent planned
roots can continue. Prefix drift or evidence corruption stops collection for inspection.

The original main command below now displays/verifies the completed result. There is no
outstanding collection task; use the current [value-study handoff](native-public-value.md).

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/collect-native-combat-teacher-v1.sh
```

Allow roughly **20–30 minutes**, based on the native control. It uses one native worker,
15-minute sessions and 2 GB RAM / 4 GB generated-output caps. The launcher stops starting
sessions after two hours; an already started session retains its own 15-minute cap.
Completed branches resume on a clean rerun. No training, adaptive controller or follow-on
experiment is triggered after the teacher.
See [teacher preparation evidence](evidence/native-combat-teacher-v1.json) for the historical
control and [completed result](evidence/native-combat-teacher-result-v1.json) for the main pilot.

Full repository verification passes **1,830 tests**, strict types on 357 source files,
formatting/lint and C# build/protocol checks. The resource-tracked check takes 107.32
seconds and 413.91 MB peak RAM. Eight new unit tests exercise prefix/root identity,
legal action coverage, public information boundaries, rejection as ordinary PPO,
complete sampling cells, uncertainty/preference gates and corrupted target rejection.
