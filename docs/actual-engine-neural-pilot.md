# Actual-engine Ironclad/A8 neural pilot

Use the frozen v0.111.0 / `41cef1ea` game and the declared full benchmark profile.
The first pilot stopped during its starting measurement: fourteen normal losses, one stuck
Dense Vegetation event, one unattempted confirmation seed, and zero learning updates. Its
results remain unchanged. The repaired **v2 pilot** uses a separately pinned host/environment
and a bounded failed-game continuation policy. The next long experiment belongs to the owner.

## One next command

Close the game, then run this from any directory:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-native-a8-ppo-v2.sh
```

Expect roughly **10–20 minutes** from the four-game control, with a **30-minute** hard cap.
The wrapper checks the frozen inputs and saved admission before launching. It prints the best
game, average floor, wins and failures for each batch. Share its final summary for assessment.
One failed/unsupported/capped game is recorded and isolated while remaining planned games
continue. More than two failures in a panel, missing games, an unverified shutdown or broken
experience evidence stop the pilot before another update. No next experiment follows.
An interrupted workspace is preserved for inspection, rather than overwritten or silently restarted.
Re-running a completed experiment displays its saved result without training.
The old v1 command still displays its original failed result. Use the v2 command above to
start the repaired experiment; it has a new workspace and does not overwrite or resume v1.

## The event repair and failure handling

Dense Vegetation's native Rest method called missing sound/camera services after applying its
heal. The wrapper swallowed the exception and presented the old menu again. Host v26 skips
exactly two sound-play calls, one sound-stop call and one camera-rumble call in that method's
async body. It verifies their signatures and count. Native healing, event state changes,
choice creation and combat/RNG logic still execute. Host v27 also waits for the native
player turn number/phase after End Turn: that queued action only marks the player ready,
and the native asynchronous turn loop owns the subsequent enemy actions. An intermediate
enemy turn is never exported as a player decision. Native option exceptions now reach the
worker with their cause, rather than appearing to be successful unchanged decisions.

Both natural-seed branches are checked: Rest heals 60→80 HP and offers Fight!, which enters
combat; Trudge On changes 60→52 HP and 273→338 gold, then Proceed reaches the map. The
original failing seed also completes normally through the event fight to a floor-7 loss. A short
injected collector failure verifies shutdown, preservation/audit of a clean earlier episode,
and a different native process for the next planned seed. It supplies no learning examples.

On failure, keep the affected worker's profile, diagnostics, partial trace and active marker.
Prove that its native and controller processes have stopped, seal an explicit retirement, and
audit the earlier complete games before starting a fresh worker for the next original seed.
Never retry the failed seed, reuse the failed workspace or retry uncertain action delivery.
Only verified complete games supply PPO targets; failed games stay in the planned evaluation
denominator and receive zero ranking return. Floor reached remains a diagnostic, including
partial progress explicitly identified in failed-case details. Each panel prints the failed
seed, cause and floor as it continues. Completed pilots with failures are labeled accordingly.

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

The repaired host/worker learning control completes four games, verifies 209 sampled decisions, performs six
PPO updates, changes actor and critic weights, reloads the checkpoint, and completes two greedy
control games. The control's best game reaches floor 17; **all four games are losses**. The sampled
and greedy games use different seeds and behaviors, so their floor averages are not an improvement
comparison. This establishes a working training connection, not a useful player or readiness pass.

The repaired host also repeats the twelve-game serial/parallel/reset control with no failures
and unchanged shared inputs. These short regressions do not expand the bounded finish line.
The current identities and preserved failed attempts are recorded in
[the event and failure-isolation evidence](evidence/actual-engine-dense-vegetation-repair-v1.json).

Assess the pilot's frozen paired development results next. If the player stalls, diagnose the
learning signal, representation and exploration before scaling. Strong-base evaluation,
adaptive thinking, GA experiments and cross-patch work remain later milestones.
