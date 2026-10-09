# A8 full-run neural learning

The current next stage trains one player for **Ironclad / Ascension 8** from its own game outcomes.
It uses the repaired simulator and complete public menus. It is a fresh experiment; the old
A0-labelled evolution pilot and teacher-trained checkpoints remain preserved.

## Run this one command

Run from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-full-run-ppo-a8-v1.sh
```

Expect roughly **10–30 minutes** on the inspected M4 Pro as an initial planning estimate, based
on the short native checks. Games can take longer as the player survives further. Each launch
has hard caps of 60 elapsed minutes, 20,000 CPU seconds, 12 GB memory and 4 GB artifacts.
The owner launches and monitors this stage. Paste its final summary, or an error/cap result,
back into the chat. No other discovery, collection or training command is required first.

The script checks existing results, gives each launch a separate resource report and explicitly
resumes the identical recipe. Completed games and optimizer checkpoints are reused. A prior
interrupted attempt with no complete result is retained as a failure with unknown cost, rather
than rerun as free data. A changed learner/configuration requires a separate experiment; it
cannot silently resume this one. A completed experiment displays its saved result without playing.

## What it does

1. Check the starting player's greedy play on 64 separate training confirmation seeds.
2. Play 64 fresh sampled training games and update the network from their results.
3. Repeat for at most 24 rounds. Every four rounds, compare greedy play on the frozen confirmation
   panel and keep the best confirmed player, ranking full wins first. The learning player can keep
   exploring even when an intermediate checkpoint loses that comparison.
4. Stop after a confirmed plateau once at least 12 rounds have completed, or at a resource cap.
5. Freeze the selected player, then compare it with the initializer on 64 independent paired
   development seeds. No further fitting or selection uses those development outcomes.

There are at most **2,112 planned game attempts**, including confirmations and development,
using eight parallel simulator workers. Final-test seeds remain sealed. Progress prints after
each eight-game batch and at checkpoint comparisons. A cap preserves partial artifacts.

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

The small native pipeline check completed 12 attempts and 1,335 decisions in 11.040 seconds,
including four sampled training games, 24 optimizer updates and frozen paired development.
It recorded zero runtime failures/stalls. The initializer reached mean floor 10.5 and the selected
updated player 10.0 on two development seeds; neither won. This checks that the loop works,
not that learning already helps. The earlier 10.226-second check remains preserved separately.

Repository checks pass: 853 tests, formatting, types and the C# protocol build. Numerical
derivative tests cover all actor layers and the critic; sampled-probability, seed separation,
failure retention and exact optimizer-resume checks also pass.

[ADR 0004](decisions/0004-scoped-a8-simulator-learning.md) and
[admission evidence](evidence/public-a8-policy-admission-v1.json) declare the simulator's
real-game coverage limits. Later-act boundaries have native regressions and a frozen-game source
audit, not captured UI parity. A winning simulator policy will still require relevant live-game
validation. A8 difficulty switching, evolutionary comparisons and adaptive thinking remain later
work. No checkpoint is promoted by this pilot.

Recipe: `configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1.json`.
Results: `artifacts/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1/ppo-report.json`.
Resource reports: `artifacts/resources/full-run-ppo-a8-v1-attempt-*.json`.
Short-check lineage: [pipeline evidence](evidence/public-a8-ppo-pipeline-v1.json).
