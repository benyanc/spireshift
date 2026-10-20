# Matched-input value comparison and separate fitting curves

## Why this follows the completed result

The prior 128-saved-TRAIN-game comparison is complete. Its current 20-feature ridge has
equal-game held MSE **5.5128e-5**, the coarse neural correction **5.8746e-5**, and the rich
correction **7.3666e-5**. Rich error is 33.6% higher than ridge, in the same direction in
all four cohorts. This is a negative forecast result, not a player regression: both
players, their complete Adam states and the real learning pipeline remain unchanged.
See [completed evidence](evidence/native-public-value-result-v2.json).

The old neural arms have 705 versus 33,473 parameters and different initialization
scales. Same hidden width and epochs did not isolate information content. Neither
parameter count nor the outcome alone proves overfitting. The new study isolates one
operational treatment: enable or mask the extra public inputs in the same network.

## Fixed matched treatment

Reuse the balanced public dictionary, exact saved games, policy-specific cohorts and
whole-game assignment. The full scope remains both numerical players' standard-policy
rounds 57 and 60: four cohorts of 32 games, four folds each, 24 fitting and eight held
games per fold. No new games or confirmation/evaluation histories are consumed.

Each fold's vocabulary and normalization are fitted only on its fitting public states.
Encode the full `[20 coarse measurements, up to 1,024 public dictionary fields]` once.
Both arms use the same input shape, 32 hidden units, bit-identical starting parameter
arrays, zero optimizer moments, ridge starting forecasts, normalization, targets and
equal-game/state weights. **After normalization**, set only the extra columns to zero
in the `coarse_masked` arm. Enable them in `rich`. Both receive the same learning rate
0.003, L2 coefficient 0.0001, gradient clipping 5 and fixed update schedule. Both include
the same nominal weights in the regularizer, including inactive input weights.

This controls nominal architecture and initialization differences. Extra active inputs
still change effective capacity and optimization; it is not a theorem separating
information from every possible capacity effect. The finite dictionary still omits
some facts. No complete mechanics or strategic-understanding claim follows.

Repeat each pair with three predeclared network initializers, separately from the two
saved policy players. Same starting arrays are checked by exact numerical digests and
the initial forecasts must agree exactly. These are numerical repeats on the **same
128 games**, never 384 independent games. Report each initializer and cohort separately.
Cross-fitting folds share fitting games; do not treat them as independent replications.

## Prediction errors and fitting curves

Freeze snapshots at updates **0, 1, 4, 8, 16, 24, 48 and 96**. The primary comparison is
always **update 24**, matching the preceding study's update count. Later snapshots are
diagnostic. No best epoch is selected with the held targets.

At every snapshot, separately report:

- Equal-game prediction MSE on fitting games and held games, without weight penalties.
- The same errors after clipping predictions into the target range [0,1].
- The neural weight penalty alone, and raw fitting MSE plus that penalty.
- Exact parameter digest for the snapshot.

Use the same raw-error definition on both fitting and held curves. A shrinking weight
penalty alone is not improving predictions. Good fitting with poor held results suggests
generalization trouble; poor fitting also leaves optimization/representation unresolved.
The curves diagnose hypotheses; they do not automatically choose a replacement model.

Save the primary weights, final weights and experimental optimizer moments separately
from all production models. Save held forecasts at every snapshot, fitting/held game IDs,
fitting-only vocabulary, normalization and the frozen ridge reference. The primary weights
and sealed matrices reconstruct predictions and the separate loss terms in regression tests.
CSV files preserve individual fold/initializer measurements. Standard matplotlib PNGs show
fitting MSE, held MSE, weight penalty and their combined fitting objective, with a fixed
step-24 marker and current-ridge prediction references.

The existing 128 games are now development evidence. Tuning based on these curves needs
untouched confirmation games after settings are frozen. Prediction gains would justify
a separate bounded on-policy credit/gameplay comparison, preserving both saved players
and full Adam states. They are not evidence of better play or calibrated win probability.
The current target remains the versioned auxiliary bootstrap return; terminal full-run
victory at Ironclad/A8 and the frozen 128-CPU-second budget remains the binding objective.

## Bounded, restartable execution

Use the existing sealed chunk journal. Each fold has one encoding chunk and three matched
fit chunks. A completed encoding is never repeated for another initializer or session.
The main study therefore has **64 units: 16 encodings and 48 paired fits**. All completed
arrays/weights/forecasts/receipts are verified before reuse; changed or uncommitted chunks
are preserved and refused. Source seals cover the original players and all Adam files.

Each clean pause creates a new numbered progress report and its own curve files. It never
overwrites an earlier progress snapshot. A rerun with no new work displays its saved result.
The final report and curves are immutable. No model promotion, new game, app copy, GA run,
adaptive controller or next experiment follows automatically.

The short real-data control has eight saved games, two folds and all three initializers:
eight units / six paired fits, capped at four wall/CPU minutes, 2 GB memory and 500 MB
output. The main comparison requires this exact completed control and matching source
bytes. Main launches have 15-minute wall/CPU caps, the same memory/storage limits and
one numerical thread. It pauses before another unit when less than 90 seconds remain.
The owner launches and monitors the main task; Codex runs short checks only.

The wrapper derives its output workspace and limits from the pinned recipe. The `value-study`
extra supplies NumPy/matplotlib; the lockfile fixes resolved packages. Runtime versions are
recorded. All original experiment source files remain unchanged and readable.

Historical entry point — this study is now complete:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-matched-value-v1.sh
```

The owner completed 61 units in a capped launch; the final three cached fits took
14.16 resource-tracked seconds. All **64/64 units** are now complete: 16 encodings,
48 paired fits and 128 unique held TRAIN games. Both saved players and their Adam
states remain unchanged. Do not rerun this study to tune settings after seeing outcomes.

At the fixed primary update 24, equal-game held MSE is **5.5128e-5** for current ridge,
**5.5841e-5** for masked inputs and **7.1256e-5** for rich inputs. Rich is **29.3% worse**
than ridge; the direction holds across all four cohorts and three numerical initializers.
At update 96 rich fitting MSE falls from **4.5684e-5 to 2.6804e-5**, while held MSE rises
from **5.5128e-5 to 7.3388e-5**. Of the combined fitting-loss decrease, **99.4%** is a
smaller weight penalty. This is a fitting/generalization gap for this recipe, not proof
that richer public facts can never help or that more games alone will solve learning.

No candidate is adopted. The next authorized experiment is the separately versioned
[regularized linear value comparison](native-linear-value.md), with whole-game tuning
and testing using these cached inputs. Its reuse is explicitly development evidence.
[Completed main evidence](evidence/native-matched-value-result-v1.json).

## Completed short checks

All **1,869 repository tests** pass, including 20 new matching, data-boundary, snapshot,
reconstruction, repeat-counting, config, corruption and resumption tests. Formatting/lint,
strict types and the C# protocol contract also pass (104.52 resource-tracked seconds).
The real eight-game control completes all two encodings/six matched pairs in **33.84
wall seconds / 27.97 CPU seconds**, **265.06 MB** peak RAM and **16.66 MB** output.

At fixed step 24, held MSE is **2.8931e-5** for ridge, **2.8686e-5** for masked inputs
and **5.0596e-5** for rich inputs. At step 96, rich fitting MSE falls to **3.3230e-6**
while held MSE rises to **6.2174e-5**. This four-fitting-game control demonstrates
instrumentation and a fitting/generalization gap, not main-study superiority or a
proven causal explanation. No epoch or new settings are selected from the control.

A saved-only audit reconstructs all **12 primary value models**, fitting/held MSE and
weight penalties, with exact stored-forecast agreement. All **11,324 source files**
(including original players and Adam states) verify unchanged. It takes 5.45 seconds,
zero new fits and zero games. The initial independent audit's different floating-point
addition grouping produced at most 6.94e-18 differences; its failed receipt is retained.
The corrected audit uses the declared grouping and matches bit-for-bit, without changing
fitting code/results or loosening tolerances. Main preflight passes in 8.96 seconds.

[Portable evidence, resources and result identities](evidence/native-matched-value-v1.json).
[Local short-control curves](/Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/artifacts/native-matched-value/sts2-v0.111.0-a8-control-v1/curves.png).
