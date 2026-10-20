# Public-state value prediction

This separately versioned step addresses the current credit predictor's representation
limit. Twenty scalar measurements can distinguish health/progress but cannot distinguish
two equal-sized decks or two relic sets. A bad forecast adds noise to action credit; it
does not prove PPO is mathematically invalid or that delayed outcomes cannot teach early
actions. Existing full-return credit uses discount and trace factors of one.

The implementation adds an offline experimental critic. It does **not** change either
saved player, its diagnostic critic, actual action-credit baseline or Adam state. Native
full-run victory at fixed Ironclad/A8 and 128 CPU seconds remains the binding objective.
The prediction target is the declared auxiliary bootstrap return, never a calibrated
win probability. This is not an action recommendation or policy training experiment.

## Inputs and limitations

`native_public_state.py` consumes the existing qualified public graph, including all
offered candidates. Public identities and current numerical values stay bound to their
owner paths: card copies/costs/upgrades/modifiers, relics/counters, potion targets,
enemy health/intents/statuses, player resources, public progress/map, shop/reward/rest
and selection menus, requirements and recorded navigation history. Native rules still
calculate effects. We neither reimplement every card nor assert that every mechanic
is already projected or understood.

Local entity slots resolve to visible owner records, without their numeric handles.
Dangling references and conflicting native identities fail. Candidate/lookup order and
declared unordered piles are pooled; other visible sequence order remains. This critic
does not choose an action, so the candidate menu is an unordered multiset. The shared
feature extractor could be reused by a future actor with separate candidate scoring.

The vocabulary is fitted **only on fitting-game public states**, and is capped at
1,024 entries. The active balanced treatment drops fitting-constant columns, then
allocates space across public sources and field names, using whole-game frequency
and deterministic lexical ties within each bucket. It uses
distinct dictionary coordinates rather than feature hashes. Rare or unseen facts can
still be omitted; counts are reported separately for fitting and held games. Owner/path
pooling, the finite dictionary, numerical transformations and network compression are
not lossless. Coverage of supplied fields differs from learning their strategic effects.
No claim of exhaustive game-state or interaction coverage is made.

Public state is validated before encoding. Additional hidden-state/seed/RNG fields are
rejected; chosen actions, terminal outcomes, rollout seeds and teacher labels never enter
features. True draw order, future rewards and unobserved intentions are unavailable.
Private native teacher branches are not consumed in this comparison.

## Fixed experiment

Each 32-game cohort belongs to one collection policy, numerical player and round. Four
cohorts use both players' ordinary-policy TRAIN rounds 57 and 60: **128 saved games**.
Four whole-game folds fit on 24 games and predict the other eight, so every game's return
is evaluated exactly once under a model that never fitted that game. Cohorts are never
pooled into a false claim about the value of one common current policy. No development or
evaluation histories are decoded. The prior complete TRAIN audit and original source
receipts bind all data, players and optimizer files.

Compare five forecasts on the same held states:

- The actual 20-feature linear residual ridge, regularization 0.001.
- Other-fitting-game constant return and unfitted current-progress references.
- Ridge plus a nonlinear correction using just those 20 features.
- Ridge plus the same-width nonlinear correction using the 20 features and the structured
  public dictionary.

Both nonlinear corrections use 32 tanh hidden units, fixed 24 full-batch Adam updates,
learning rate 0.003, L2 0.0001 and gradient clipping at 5. Their hidden widths and update
counts match; their parameter counts differ because their input sizes differ. This
contrast includes added representational capacity, not an isolated architecture theorem.
The full predictor has at most 33,473 trainable correction parameters, plus its frozen
20-feature ridge. The additional correction starts at zero, so its initial forecast
matches that ridge. Neither a best epoch nor a hyperparameter is selected using held data.

Vocabulary, means and scales use fitting states only. Each complete game has equal mass;
within it, choice-bearing states have equal mass. Administrative forced inventory opening
is excluded using the existing navigation contract. All strategic action families and
optional declining choices remain. Final forecasts are clipped to the target's [0,1]
range. The predictor sees observed full-run results, not handwritten health/upgrade rewards.

Report per-game mean squared errors, per-cohort and pooled equal-game errors, coverage,
architecture/work and all source seals. With only 128 games, overlapping cross-fitting
training sets and existing weak policies, this is a forecast feasibility comparison,
not native gameplay generalization or a readiness pass. A result can be negative.

## Execution and preservation

The short integration control uses eight saved TRAIN games and two whole-game folds.
It checks the exact same implementation with a four-minute wall/CPU cap, 2 GB memory
and 500 MB output. Its tiny prediction comparison is not the main study.

The first control exposed a defective allocation: its global frequency/lexical cutoff
spent all 1,024 coordinates on interaction fields and omitted persistent, inventory and
menu facts. That v1 candidate and its negative result are retained and **not selected**.
The separately versioned balanced implementation gives each of the five varying sources
204–205 coordinates on the short control, including durable state, inventories and menus.
Regression tests prohibit the original crowding failure and check end-to-end learning of
an artificial card/relic interaction with identical coarse measurements.

Both balanced folds complete without technical failures. Their small held-game forecast
error is **5.6232e-5**, versus **2.8931e-5** for the current ridge: **worse, not an improvement**.
Only four games fit each fold; this control establishes integration and coverage repair,
not forecast superiority. No settings are tuned to that result. The larger fixed study
fits on 24 games per fold and remains necessary before considering adoption. The finite
dictionary still omits many redundant, constant, rare and unseen path facts; source-group
coverage is reported rather than described as complete mechanical understanding.

The main study has 16 independently sealed folds. Each stores its vocabulary, numerical
critic weights, held predictions and metrics; raw episode histories are released one
game at a time. Completed folds are verified and reused after a clean pause. Uncommitted
or changed evidence is preserved and refused, rather than overwritten. All original
model/Adam bytes, source/runtime/SDK/frozen app and account data remain unchanged.

The owner-run wrapper derives workspace and limits from its pinned recipe. It permits
15-minute launches, one numerical thread, 2 GB memory and 500 MB private output. It cannot
launch the game, update a player or start the next experiment. The main recipe requires
the matching completed short control. No GitHub Actions or app copies are needed.

Use the v2 comparison wrapper. Its final short-control receipt is version 3: it repeats
the balanced treatment after source formatting/import ordering, with identical numerical
results. Earlier results/config-at-launch files and the pre-format source snapshot remain
private and preserved. Active recipes bind the final checked bytes; earlier output is
never overwritten or silently reused with changed sources.

The final control uses **30.83 wall seconds / 25.68 CPU seconds**, **203.62 MB** peak RAM
and **3.44 MB** output. Reopening both the rejected first control and final control with
fitting disabled verifies all their source seals and launches zero numerical fits/games.
Full local verification passes **1,849 tests** (19 new), formatting/lint, strict types and
C# build/protocol contracts in 107.06 resource-tracked seconds. No push or GitHub Actions.

The 128-game comparison is now **complete: 16/16 folds**, with 128 held-game predictions.
The owner completed 15 folds in a cleanly paused session; Codex finished the remaining short
fold in 60.53 resource-tracked seconds, reusing all prior results. Current ridge MSE is
**5.5128e-5**, coarse neural MSE **5.8746e-5**, and rich neural MSE **7.3666e-5**. Rich error
is **33.6% higher** than ridge and worse in all four player/round cohorts. No player or
Adam state changed, no game ran and no candidate was adopted.

This comparison also changed parameter count/initialization scale with input dimension.
Its negative result does not identify one causal mechanism or establish that rich public
information is useless. The next separately versioned work matches full network shape,
starting arrays and normalization, masks extra inputs in one arm, and records fitting
prediction error separately from weight penalties. See
[matched-input comparison](native-matched-value.md) and
[completed result evidence](evidence/native-public-value-result-v2.json).

For this completed result, assess held-game errors against the current ridge in **both** player
cohorts and inspect omitted identities/current fields. Better forecasts justify a new
bounded on-policy credit comparison; they do not authorize silently swapping the baseline
in an old run. If errors worsen, preserve that result and revise a specific measured
input/estimation limitation instead of extending unchanged PPO blindly.
