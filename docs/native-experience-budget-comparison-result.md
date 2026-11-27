# Completed experience-budget comparison

All **832 attempts / 283 sealed units** are complete, with **zero technical failures
or missing games**. This includes 640 sampled training attempts and 192 frozen
evaluation attempts. Four times the experience per round has **not demonstrated
stronger full-run play**. No new training or model promotion follows this result.

## Fresh-game results

Each version is evaluated on 32 new native worlds for each of two fixed parent
players. The table pools those 64 attempts equally; the worlds are shared across
versions and players.

| Version | Training games per player | Full wins | Average floor | Games clearing an act | Best floor |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 0 new | 0/64 | 11.1875 | 0 | 17 |
| 32 games per round | 64 | 0/64 | 11.640625 | 3 | 23 |
| 128 games per round | 256 | 0/64 | 11.15625 | 0 | 17 |

The smaller batch's three act-clearing games and higher average floor are a weak
auxiliary signal, not a successful full-run player. No policy has observed wins in
this evaluation; that does not establish a zero underlying win probability.

| Paired comparison | Mean floor difference | 95% paired interval |
| --- | ---: | ---: |
| Larger minus smaller, primary | -0.484375 | [-1.171875, +0.171875] |
| Smaller minus original | +0.453125 | [-0.328125, +1.1875] |
| Larger minus original | -0.03125 | [-0.75, +0.625] |

All floor intervals include zero. The original, smaller and larger versions reach
mean floors 11.90625 / 12.53125 / 11.96875 for parent 2, and 10.46875 / 10.75 /
10.34375 for parent 3. Both parents have a positive smaller-minus-original point
estimate, but the pooled floor gain remains uncertain.

The separately declared bootstrap training-return difference is +0.00347256 for
smaller minus original, interval [+0.00039119, +0.00717985]; larger minus smaller
is -0.00353278, interval [-0.00722624, -0.00053240]. A positive interval on this
auxiliary score does not establish terminal wins or statistically clear floor
improvement. These related outcomes/comparisons are not multiple independent
confirmations or grounds to select a production checkpoint.

Intervals resample the **32 evaluation worlds jointly across two fixed parents**.
They do not generalize over a population of initializers. The all-zero empirical
victory-difference intervals are degenerate because there are no observed wins;
they do not prove identical true win rates. The three versions use matched greedy
combat / sampled noncombat behavior and a 128 CPU-second budget per game.

## What the saved checks establish

The independent saved-only audit verifies **66,324 source files**, all 283 task /
predecessor receipts, exact imported numerical weights and complete Adam states,
all four frozen final IDs, 832 terminal outcomes, and 2,175 recorded optimizer
steps. The paired summary and clustered intervals reproduce from the saved units.
Frozen environment/account checks and sealed native delivery / behavior probability
checks pass. The audit does not replay native effects, refit a baseline, rerun PPO
or claim exhaustive game-mechanics correctness.

Both original full states remain unchanged at Adam counters **5,658 / 6,045**.
Every experimental checkpoint retains its complete optimizer state. All final
players were fixed before evaluation, with no checkpoint selection from those
outcomes. The network, coarse whole-game value predictor, objective, bootstrap
score and PPO settings were unchanged. All currently legal decision families
remained learnable. There were zero app copies and no readiness/controller pass.

The smaller arm used **423 updates / 128 training attempts** across both parents;
the larger used **1,752 updates / 512 attempts**. All training games lost the full
run. The smaller arm has 0/128 act-clearing games; the larger has 10/512. More
card/relic definitions and later floors were encountered, but genuinely useful
later-game learning remains sparse. Training-round averages use different fresh
worlds and sampled actions; they are not evidence of better frozen fresh play.

Mean evaluation CPU time is 2.974 / 3.073 / 2.905 seconds per original / smaller /
larger game. Every recorded game stays under 10.831 measured CPU seconds. These
timings reflect mostly short losing trajectories, not full-length wins or a
headroom claim for an adaptive planner. The final wrapper's 508.84 seconds is
only its last session, and its 1.387 GB is cumulative workspace size; neither is
the whole experiment's total elapsed time or a per-session storage increment.

The saved-only audit takes **49.38 wall seconds**, peaks at 159.04 MB and retains
8,807 bytes of assessment metadata. It launches zero games and changes zero
weights/optimizer states. See [portable evidence](evidence/native-experience-budget-comparison-result-v1.json).

Repository verification passes **2,414 tests (five skipped)**, strict types on
511 source files, formatting/lint and the C# protocol in 137.36 wall seconds.
Receipt: `artifacts/resources/native-experience-result-repository-check-v1.json`,
`sha256:c05d80584fe8463b4a9eadd301cfb24063f2411c8c8576e70fa761eabb7fcd82`.
The assessment changes no pinned runtime, collector, predictor or training recipe.

## Interpretation and next work

This is evidence against **automatically enlarging this same short PPO recipe**.
It does not prove that more data can never help: there are only two update rounds,
two fixed parents and 32 fresh evaluation worlds. Experience quantity, critic
fitting support, batch size and training compute change together; this is not a
causal test of data variety alone. The result does not identify one cause of
stalled learning or prove that every update/reward/encoding path is correct.

Finish the separately prepared [saved-training feedback diagnosis](native-experience-training-diagnostics.md)
to compare support and feedback on identical first-round choices. Original
forecasts can reproduce perfectly while supplying strategically poor credit;
changed action probabilities also do not prove a change was beneficial. The
remaining three cohorts / 288 saved games are owner-run analysis, not more game
attempts. Keep all evaluation outcomes out of fitting.

The next gameplay intervention should be a **qualified stronger teacher or
curriculum on TRAIN-only varied situations**, with trustworthy consequences of
alternative choices. First establish useful teacher lessons, exact public/menu
boundaries and held-world student learning; then assess a bounded student fork
on fresh full games from both preserved parents. Do not simply reuse every old
teacher preference: earlier fixed-world evidence remains privileged and rejected
or uncertain lessons stay excluded. The old situation bank also requires native
replay qualification under its exact observation version; missing public counters
cannot be silently filled in.

Keep original parents and all new finals, avoid tuning on these evaluation worlds,
and make any reward, predictor, capacity or GA change a separate declared test.
There is no automatic scale-up, model promotion, readiness pass or adaptive budget
controller. The completed owner command does not need to be run again.
