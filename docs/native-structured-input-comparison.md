# Structured public-input comparison

The finite Ironclad/A8 comparison is **complete and assessed**: 640/640 attempts,
zero failures, no demonstrated advantage for named inputs and no full-run wins.
The restart preserved saved work and both original full states/Adam. **No owner
rerun is needed.** See the [completed result](native-structured-input-comparison-result.md).
The design, qualification measurements and launch instructions below document the
original preparation; its zero-main-game statements describe that earlier stage.

## Question and controlled change

Does giving selected public facts their own stable input columns improve learning
and fresh full-game play compared with compressing those same facts into shared
columns? This follows the [small tactical control](native-tactical-learning-result.md)
and the earlier [negative full-game comparison](native-policy-update-comparison-result.md).
It uses natural full runs, without artificial fixture rewards or an oracle baseline.

Each original saved player starts three experimental copies:

| Training arm | Actor inputs | Hidden units | Total actor/critic parameters | Added public facts |
| --- | ---: | ---: | ---: | --- |
| Unchanged | 512 | 32 | 17,473 | none |
| Hashed supplement | 1,536 | 32 | 52,289 | 1,024 named facts mapped into 1,024 signed hash buckets |
| Named supplement | 1,536 | 32 | 52,289 | the same facts, each with its own column |

The primary comparison is **named versus hashed**, at exactly equal parameter count
and hidden width. Unchanged-input PPO controls for adding a second feature block and
its parameters. That secondary comparison does not isolate generic network capacity:
the added projection also changes conditioning and redundancy. A larger hidden
network remains a separate experiment.

The original 512-input encoder is retained in all arms. Its weights, hidden biases,
readout, direct path and critic parameters keep their exact meanings. The two wider
actors receive zero-valued new input weights; their old first/second Adam moments
and global step counters are copied exactly, and new moments start at zero. Their
starting action scores and values therefore match the original, within floating-point
roundoff. The new weights are trainable; no actor layer or strategic action family
is permanently frozen. New critic input positions stay zero, retaining the existing
critic inputs instead of silently testing a richer value predictor as well.

Both original full states remain read-only at counters **5,658 / 6,045**. Control fits
and the main experiment use separate copies; the main does not inherit control-trained
weights. Every completed fit saves all weights, both Adam moments and the counter.

## Varied situations and the bounded layout

The input vocabulary is fit without outcome labels from the **128 saved TRAIN games**
in the previous completed comparison: 64 source worlds, **18,736 distinct public
inputs and 14 decision families**. It covers combat, shops, rest sites, map decisions,
events, card rewards, card selections, bundles, generated card choices and treasure.
The previous development games and tactical fixtures do not fit this layout.

Public owner/property paths and ordered card copies stay attached to amounts,
current costs, definition identities, intents, target arguments and counters. Numeric
values use the existing scaling. Public categorical identities stay categorical.
Numeric zero-valued fields still qualify for a column; a later nonzero numeric
value is not unfamiliar simply because its original value was zero. Categorical
costs retain their native supplied type, with unfamiliar categories using the base encoder.
Private RNG/future fields and opaque runtime handles are rejected.

The source contains **35,971 eligible fact names**. Family-balanced, equal-game
document frequency selects **1,024**; combat's much larger decision count does not
consume every column. Both supplemental arms use exactly the same selected facts,
values and normalization before projection. The selected hashed control occupies
667 buckets: 357 column collisions. That is a property of this supplemental map,
not a claim that 357 whole game situations become identical.

This is a **bounded named-input supplement**, not a lossless replacement for the
whole game state. Free text, unselected fields and unfamiliar identities continue
through the original encoder. Evaluation reports separately:

- selected fact occurrences;
- source-observed facts outside the supplement;
- genuinely unfamiliar fact names;
- reached decision families.

The vocabulary never expands from later training or evaluation observations. The
source players were weak, so their varied data still does not cover every late-game
mechanic or rare combination. A negative result concerns this particular layout,
width, training budget and two fixed parents, not every structured architecture.

## Fresh full-game experiment

The main plan has **640 attempts**, not 640 independent game worlds:

- **384 training attempts:** two rounds of 32 worlds, shared across three arms and
  both fixed parent initializers. Every arm executes its own sampled policy and
  verifies its own saved probabilities; no old or greedy traces become PPO data.
- **256 evaluation attempts:** 32 additional worlds, each played by the original
  and the three final trained copies of both parents. All final checkpoints exist
  before the first evaluation. Outcomes never select an epoch or trigger more rounds.

Training samples every strategic family, including optional declines. Evaluation
uses the previously qualified greedy combat / sampled noncombat behavior. World,
room and family keyed draws are shared across variants; extra combat actions do
not shift the next room's noncombat randomness. Arm execution order rotates.
Historical training, development, tactical and separate control worlds are excluded.

PPO settings, the 20-feature whole-game cross-fitted baseline, reward/score definitions,
normalization of the original block and native v0.111.0 engine stay unchanged. No
handwritten HP, card or Smith bonus is added. Terminal full-run victory under
**128 CPU seconds per run** remains primary; acts/floors and the declared bootstrap
return are separate auxiliary measurements. Zero observed wins cannot establish a
zero true win probability.

Report paired named-minus-hashed victory/act/floor/return changes first, then added
block versus unchanged training and each final player versus its original. Bootstrap
intervals cluster by the shared game world jointly across the two fixed parents;
they do not cover the population of training initializations. Count failed attempts
in the original denominator with zero headline win/progress value. Preserve their
raw reached progress and evidence separately. The finite failure allowance is two per player/arm training round or evaluation cell;
an unauditable or uncertain delivery stops without retry. No automatic promotion,
readiness pass or adaptive-controller training follows.

## Completed qualification

Saved-input checks cover **56 distinct TRAIN situations across all 14 families**.
The largest initial score differences are **8.88e-16 / 2.22e-16** for the two parents.
The checks verify candidate permutation, inherited moment/counter restoration,
signed PPO derivatives, no-credit behavior and nonzero gradients into the new columns.

The integration control completes **12 training attempts and eight frozen checks**,
zero failures and 36 optimizer updates across the six disposable copies. It uses
two training worlds and one evaluation world; its outcomes are not playing-strength
evidence. All three initial native public/action traces match within each of the
four player/training-world groups. Both original states and all Adam state remain
unchanged. Workers share frozen game/runtime/SDK/support inputs; **zero app copies**.

The single control evaluation world gives player 2 floors 17 / 15 / 17 / 6
(original / unchanged / hashed / named); player 3 reaches floor 6 in every version.
These limited outcomes are preserved, do not select a treatment or tune the recipe,
and do not support a performance claim. The main fresh-world comparison remains needed.

The saved audit verifies **27 sealed units / 7,999 source files**, all 20 endings and
2,628 recorded decisions, exact imports and paired tables in **4.20 seconds**.
It reuses the verified native/probability audit seals rather than replaying native
effects or rerunning inference. No audit fitting occurs.

The two native control sessions take **118.96 seconds combined**, with **816.38 MB**
peak resident memory and **67.51 MB** retained. The preceding saved-input check/import
stage takes 11.99 seconds; vocabulary preparation takes 25.98 seconds / 132.58 MB
peak memory and creates 4.29 MB. See [qualification evidence](evidence/native-structured-input-comparison-v1.json).

The full repository check passes **2,321 tests (34 new; four skipped)**, strict types
on 476 files, formatting/lint and the C# protocol contract in **135.94 seconds**.
The main saved-only preflight imports all six exact original model/Adam copies in
8.72 seconds, with **zero main games / zero main updates**.

## Historical owner command — complete; no rerun needed

Close any running STS2 game, then run **only**:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-structured-inputs-v1.sh
```

Allow roughly **45–90 minutes**, estimated from the short control; longer trajectories
and 32-game fitting batches can change this. Each session is capped at 15 minutes,
1,800 CPU seconds, 4 GB memory and 4 GB main artifacts, using at most two game workers.
One invocation continues the same finite experiment across clean boundaries, up to
one hour. If it announces a clean pause, run the **same command** again. Completed
games and full model/Adam states resume; uncertain work is preserved without retry.
Every training batch shows its average, best floor/acts, wins and failure count.

The shared frozen game/runtime/SDK remain outside the new artifact count and are not
copied. No control repeat, manual data-combining step, second training command, automatic
larger experiment, push or GitHub Actions run is needed. An already complete main command
only verifies and displays its saved result. Send the final summary back for assessment.
