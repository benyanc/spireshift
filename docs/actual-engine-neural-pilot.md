# First actual-engine Ironclad/A8 neural pilot

Use the frozen v0.111.0 / `41cef1ea` game and the declared full benchmark profile.
The temporary-target-ID repair, serial/parallel/reset controls and short learning control
are complete. The next experiment is a finite policy-only pilot, launched by the owner.

## One next command

Close the game, then run this from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-native-a8-ppo-v1.sh
```

Expect roughly **10–20 minutes** from the four-game control, with a **30-minute** hard cap.
The wrapper checks the frozen inputs and saved admission before launching. It prints the best
game, average floor, wins and failures for each batch. Share its final summary for assessment.
It stops when complete or on a failed/unsupported/capped game; no next experiment follows.
An interrupted workspace is preserved for inspection, rather than overwritten or silently restarted.
Re-running a completed experiment displays its saved result without training.

## What runs

- Eight rounds of 32 sampled training games: **256 games**.
- Sixteen fixed training-confirmation seeds before learning and after rounds 4 and 8: **48 games**.
- Freeze the selected checkpoint before opening sixteen independent development seeds.
  Evaluate both the initial and selected player on those same seeds: **32 games**.
- **336 planned attempts** in total. Missing, failed, uncertain and capped attempts remain in
  their original denominator. Development games never select a checkpoint or supply gradients.

Two native processes use separate profiles, SDK ledgers and navigation memory. Each process
resets between its games. They share the existing frozen game/runtime/SDK files; **zero game
app copies** are made. Public observations, private debugging and experience journals are
compressed and separated. Caps: 4 GB retained output, 4 GB process-tree memory, 3,600 CPU seconds
and 1,800 elapsed seconds. Per game: 128 CPU seconds, 60 elapsed seconds and 4,096 decisions.

## Model and learning

The separately versioned encoder resolves public entity references to local occurrences and
retains their visible properties and relationships. Opaque runtime handles, process IDs, seeds,
future acts and hidden RNG do not enter the network. Named amounts stay with their owners;
card copies, current costs/modifiers, relic counters, enemy intents, selection limits and
inspectable deck/map/pile information remain available. The policy also receives public memory
of its own inspected shops and declined offers. All currently legal actions remain selectable.

The actor scores every legal candidate with **512 inputs → 32 tanh units → one score**, plus
a learnable linear connection from the inputs. It has 16,960 parameters. The critic has 513
parameters, for **17,473 total**. These weights and inputs are new actual-engine formats; no old
v0.107.1 actor or emulator observation is silently converted. The existing tested PPO/Adam
numerical routines update every actor layer and the critic. Clipping applies to a single round's
behavior policy; there is no permanent proximity penalty to the weak initializer.

Full-run victory under the fixed whole-run CPU budget remains the evaluation objective. The
explicit bootstrap score gives a smaller auxiliary return for completed acts/floors on a genuine
loss. It pays nothing for repeated actions, HP hoarding or incomplete games. The critic predicts
this declared bootstrap return, **not a calibrated win probability**.

The collector seals and reloads experience, reconstructs sampled action probabilities and checks
the public observation → advertised action → delivered successor chain against each worker's
saved journals. Unknown deliveries are not retried; recovered or privileged fixtures cannot be
PPO data. Frozen/shared inputs are checked after the experiment.

## What the completed controls establish

The public-ID audit checks 783 saved observations under 2,349 consistent renamings. The final
worker panel completes 12/12 games and 1,214 decisions, with matching serial/parallel/reset
semantic traces, separate processes/profiles, verified shutdown and a sibling-access sentinel.
A saved-only feature audit checks 1,226 observations and 5,137 candidates: no distinct candidates
within those menus collapse to the same 512-dimensional vector. This is observed-panel coverage.

The final learning control completes four games, verifies 209 sampled decisions, performs six
PPO updates, changes actor and critic weights, reloads the checkpoint, and completes two greedy
control games. The control's best game reaches floor 17; **all four games are losses**. The sampled
and greedy games use different seeds and behaviors, so their floor averages are not an improvement
comparison. This establishes a working training connection, not a useful player or readiness pass.

Assess the pilot's frozen paired development results next. If the player stalls, diagnose the
learning signal, representation and exploration before scaling. Strong-base evaluation,
adaptive thinking, GA experiments and cross-patch work remain later milestones.
