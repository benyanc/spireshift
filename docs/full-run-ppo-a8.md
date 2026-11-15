# A8 full-run neural learning

## Completed v2 result and current next stage

The owner completed all 32 rounds: **5,504 attempts, 659,118 public decisions and 14,696 optimizer
steps**, with zero full wins. The selected player is round 24. On the complete independent
128-seed comparison, mean floor changes from **11.6641 to 11.9922**, while first-act clears change
from **three to two**. Paired floor outcomes are 48 improvements, 42 regressions and 38 ties;
the approximate paired 95% floor interval is **−0.65 to +1.31**. This auxiliary diagnostic does
not establish useful generalization, victory readiness or a calibrated victory value.

The two explicit owner launches used 5,938.579 wall / 11,625.372 CPU seconds in total. All
development games finish normally. Across the whole experiment, 16 liveness failures and one
unsupported action are retained; there are no worker-crash attempts. Source outcome metadata
and resource identities are reconciled in the
[v2 assessment](evidence/public-a8-ppo-pilot-v2-assessment.json); compressed traces are not
reaudited by that assessment.

The next owner command is in [the A8 neural evolution guide](full-run-a8-evolution.md).
It preserves this completed PPO result and tests broader actor-weight changes on new train
panels, with fresh development comparisons against both PPO and its initializer. There is no
automatic larger PPO launch. The earlier instructions below describe the completed experiment.

## Preserved PPO recipe

This stage trains one player for **Ironclad / Ascension 8** from its own game outcomes.
The first sustained PPO pilot finished without establishing improvement. It stopped after 12
rounds, retained the initializer, and its independent development panel was interrupted by a
native crash. Fifty of 64 development attempts failed when that crash destroyed the shared
process pool. Three sampled training attempts also hit empty card rewards incorrectly offered
as legal choices. All original results remain preserved.

The new v2 recipe uses a separately repaired and admitted simulator, disposable game processes,
and fresh seed panels. An incomplete development panel is marked failed; a player compared
with itself is explicitly identified. A debug journal records the last public action before a
native call, separately from model inputs. A failed game remains in the denominator and is not
automatically retried. The actor, critic, PPO update equations and score formula remain the same.

## Historical launcher for the completed PPO experiment

Run from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-full-run-ppo-a8-v2.sh
```

Allow roughly **30–60 minutes** on the inspected M4 Pro, based on the 12-minute first pilot and
the disposable-process check. Games can take longer as the player survives further. Each launch
has hard caps of 60 elapsed minutes, 20,000 CPU seconds, 12 GB memory and 4 GB artifacts.
The owner launches and monitors this stage. Paste its final summary, or an error/cap result,
back into the chat. No other discovery, collection or training command is required first.

This is the completed PPO recipe's launcher, not the current next experiment. The simulator
build, admission and short check are already done.
The script checks existing results, gives each launch a separate resource report and explicitly
resumes the identical recipe. Completed games and optimizer checkpoints are reused. A prior
interrupted attempt with no complete result is retained as a failure with unknown cost, rather
than rerun as free data. A changed learner/configuration requires a separate experiment; it
cannot silently resume this one. A completed experiment displays its saved result without playing.

## What it does

1. Check the starting player's greedy play on 128 separate training confirmation seeds.
2. Play 128 fresh sampled training games and update the network from their results.
3. Repeat for at most 32 rounds. Every four rounds, compare greedy play on the frozen confirmation
   panel and keep the best confirmed player, ranking full wins first. The learning player can keep
   exploring even when an intermediate checkpoint loses that comparison.
4. Stop after six unsuccessful confirmation checks once at least 24 rounds have completed,
   or at a resource cap. The first pilot's sampled play was still changing at round 12; its
   short plateau was insufficient evidence that longer learning would fail.
5. Freeze the selected player, then compare it with the initializer on 128 independent paired
   development seeds. No further fitting or selection uses those development outcomes.

There are at most **5,504 planned game attempts**, including confirmations and development,
using eight disposable game processes. The fresh split covers seeds 300000–307999. The two
development seeds used by the implementation check are excluded from this comparison.
Final-test seeds remain sealed. Progress prints after each eight-game batch. At the end of
each sampled round, the launcher adds its best finished game, average floor across all attempts,
wins and failures/caps, and the best sampled game so far. Full wins rank first, then completed
acts and floor reached. Failed or capped games remain in the counts and cannot become the best
game. On an explicit resume, saved rounds rebuild the same progress display without replaying.

For example (illustrative numbers, not measured results):

```text
Round 4/32 summary: wins 0/128 | best game: floor 22, 1 act (loss) | average floor 12.40 | failures/caps 0.
Best sampled game so far: floor 25, 1 act (loss), round 3, seed 300472.
```

Sampled games include exploration; one lucky result is not evidence of consistent improvement.
The existing confirmed-player checks show wins and average floor on the same fixed seeds every
four rounds. The display reads saved outcome metadata and changes no learning settings,
experiment identities or artifacts. An already running process keeps its original display;
this feature applies to future launches. A cap preserves partial artifacts.

## How the model learns

The policy scores **every supplied legal action**, including combat and card menus, potions,
rewards, deck choices, routes, rest, shops, events and starting choices. Its network has 256
features per candidate, 16 hidden tanh units, a scalar score and a learnable direct linear path:
**4,384 actor parameters**. All are mutable. A separate 257-parameter public-state critic estimates
the current bootstrap return and reduces noise in the policy updates.

Training samples from the policy's action probabilities. Each saved decision records the selected
action, its actual behavior probability, the public observation and the legal candidate bindings.
Before optimization, these are recomputed and verified. Historical greedy traces cannot be fed to
PPO as if they had been sampled.

Each recorded action receives its episode's undiscounted return. A complete win returns 1;
a normal loss receives the existing bounded act/floor bootstrap score. Errors, stalls and caps
receive zero. Native rewards stay binary. PPO compares each update with the player that collected
that round, clips unstable changes, fits the critic and allows exploration. It applies no permanent
closeness penalty to base-v2, and no decision family is frozen. These update controls permit
substantial cumulative change over successive rounds.

The bootstrap critic is **not** a victory-probability or risk head. Learning from a whole-run
return can still be noisy and struggle with credit for early choices. This pilot tests whether
the method improves independent play; more games are not assumed to guarantee success.

## What is verified so far

The repaired native engine passes **247 targeted and 4,949 full-suite tests** (one existing
diagnostic skip), **31 original Python interface tests**, **420 original game-fixture checks**
(six recorded legacy skips), and ten public contract checks. The crash was independently
reproduced at seed 200192: Regret's HP loss triggers Centennial Puzzle's draw during turn end.
The fix preserves hook ordering, newly drawn cards and retention. That seed now finishes without
an error. All three saved empty-reward prefixes replay exactly; only Skip is offered and works.

The new isolated pipeline check completed **14 attempts, 1,974 decisions and 16 optimizer steps
in 16.909 seconds**, with zero errors. Mean floor on its two development seeds was 11.5 initially
and 17.0 updated; neither player won. This is implementation compatibility, not evidence of
useful learning. The earlier checks and failed build/setup checks remain preserved.

Repository verification covers formatting, types and the C# protocol build. Numerical
derivative tests cover all actor layers and the critic; sampled-probability, seed separation,
failure retention and exact optimizer-resume checks also pass.

[ADR 0004](decisions/0004-scoped-a8-simulator-learning.md) and
[admission evidence](evidence/public-a8-policy-admission-v2.json) declare the simulator's
real-game coverage limits. Later-act boundaries have native regressions and a frozen-game source
audit, not captured UI parity. A winning simulator policy will still require relevant live-game
validation. A8 difficulty switching, evolutionary comparisons and adaptive thinking remain later
work. No checkpoint is promoted by this pilot.

Recipe: `configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v2.json`.
Results: `artifacts/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v2/ppo-report.json`.
Resource reports: `artifacts/resources/full-run-ppo-a8-v2-attempt-*.json`.
[First-pilot assessment and repair evidence](evidence/public-a8-ppo-pilot-v1-assessment.json)
preserves the negative owner result and new check lineage. The
[earlier pipeline evidence](evidence/public-a8-ppo-pipeline-v1.json) is historical.

The next result must show a distinct updated player's independent outcomes, with all failures
reported. Wins remain primary. A reproducible floor/act gain would support further development;
it would not satisfy the strong-foundation gate. If the complete v2 pilot still shows no useful
gain, revise the score/credit assignment or compare evolution under matched budgets instead of
automatically scheduling a larger PPO run.
