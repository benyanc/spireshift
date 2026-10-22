# Bounded fresh-experience comparison on the repaired A8 player

**Completed on 2026-10-22:** all 832 attempts / 283 sealed units, zero failures,
and no established full-run improvement from either arm. See the
[verified final result](native-experience-budget-comparison-result.md).
The design and command below are historical; do not repeat or scale this run.

This tests whether a larger fresh on-policy experience budget improves learning
without changing the network, credit predictor, reward, game rules or PPO settings.
Both arms use the repaired owned combat relic-counter observation. The preparation
and qualification details below record the pre-launch state.

## Frozen design

| Property | Smaller batch | Larger batch |
| --- | ---: | ---: |
| Fresh games per round, per player | 32 | 128 |
| Training rounds | 2 | 2 |
| Training games per player | 64 | 256 |
| Fixed parent players | 2 | 2 |
| Actor inputs / hidden units | 512 / 32 | 512 / 32 |

Each round's smaller world pool is the first predeclared 32 of the same 128-world
pool used by the larger arm. Worlds are sampled before seeing outcomes; none are
selected for success, useful decks or survival. Each policy trains on its own
fresh sampled trajectories. Historical episodes are not reused as on-policy data.
Two parent numerical states and all Adam moments/counters **5,658 / 6,045** are
copied exactly; new environment metadata explicitly binds worker v11/counter
contract v1. Original files and the earlier six experimental finals stay read-only.
The original full public graph, all legal action families and current coarse
whole-game cross-fit ridge remain available. There are no HP/upgrade reward bonuses.

This is a test of **four times the experience budget per update round**. It also
changes fitting batch size, critic fitting support and the available optimizer
minibatches/compute. It does **not** isolate data diversity alone or make training
compute equal. Actual updates, early KL stops, CPU and coverage are reported.

All four final states freeze before evaluation. On 32 new development worlds,
evaluate each parent's migrated initial player and both trained arms: **192
attempts**. Behavior is matched: greedy combat, sampled noncombat, same world/room/
family random streams, 128 CPU seconds per full run. Failures remain in their
original denominator with zero wins/progress; they are never silently replaced.

The main plan is **640 training + 192 evaluation = 832 attempts / 283 sealed
units**. There are 256 distinct training worlds and 32 distinct evaluation worlds,
shared across arms/parents; attempts and decisions are not independent worlds.
Intervals resample whole evaluation worlds jointly across the two fixed parents;
they do not cover a population of training initializers. The primary comparison
is larger minus smaller, followed by each final versus its own initial player.

Report terminal wins first, then act completion, paired floor/return differences,
CPU and failed attempts. Record each round's best game, mean floor, wins and failures;
save owned-card/relic coverage, the number of games reaching later floors/clearing
acts and choice-credit statistics by decision family. These diagnostics do not
alter rewards or turn the state baseline into an action-ranking teacher.

## Completed short qualification

The integration control is **complete**: 18/18 clean attempts / 19 sealed units,
zero failures and 42 learning updates on experimental copies. It takes 143.30
seconds (143.62 wrapped), peaks at 693.27 MB and retains 56.23 MB; no app copies.
One evaluation world supplies no performance conclusion or arm selection.

A saved-only audit verifies 33,839 source seals, all 3,180 raw decisions / 1,654
TRAIN decisions, exact full weight/Adam imports, predecessor counters and policy
probabilities, without new games or refitting. It takes 58.24 seconds, peaking at
149.83 MB. Main offline preparation has completed policy checks and two exact
state imports only: **zero main attempts / zero main updates**.

Repository verification passes 2,373 tests (five skipped), strict types on 498
files, formatting/lint on 676 files and the C# contract, in 142.35 seconds. The
new Node counter-projection tests also pass using the bundled runtime. See
[portable qualification evidence](evidence/native-experience-budget-comparison-v1.json).

## Execution and interpretation

A separate **18-attempt short integration control** exercises imports, the repaired
worker, actual policy probabilities, learning and fresh frozen evaluation with
tiny 2/4-game batches. Its worlds are excluded from the main recipe. It qualifies
the wiring, not gameplay strength or full-size batch efficiency. The main runs
always start from the original numerical states, never control-trained forks.

The implementation requires that control and the completed saved-state/native
counter checks before main collection. Eight-game chunks seal complete traces and
predecessor state IDs; fitting saves every weight and full Adam state. A rerun
reuses sealed work. Uncertain/unsealed native or fitting work stops for inspection;
no automatic seed retry or optimizer reset occurs. At most two verified failed
games per training round/evaluation arm are allowed; corruption still stops at once.

Two isolated workers share the frozen game/runtime/SDK/support code. No game app
copies are created. A raw episode is decoded at a time, with compact training
arrays retained. Main session caps are 15 wall minutes / 1,800 CPU seconds / 4 GB
RAM / 4 GB workspace. The wrapper continues only this finite plan through clean
sessions, with a one-hour invocation boundary. Rerun the same command to resume.
Jobs expected to last five minutes or more are owner-run.

A larger batch is not promised to improve the player or create successful decks.
If fresh full-game gains remain absent and later-game experience stays scarce,
the next separate intervention is a qualified stronger teacher/curriculum, not
another automatic enlargement of this same PPO run. A richer state-value model,
wider network, GA and other ascensions remain separate candidates. There is no
automatic promotion, readiness pass or adaptive-controller training.

## Historical owner command

The completed experiment used this command. Re-running verifies/displays the saved
result; it does not start a new experiment:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-experience-v1.sh
```

Close STS2 first. Budget approximately 60–120 minutes based on the prior 640-attempt
comparison; the exact time will depend on learned trajectory lengths. Completed
chunks resume with the same command. No main games have been launched by Codex.
