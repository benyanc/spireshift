# Saved action rankings and independent outcome prediction

The completed 192-game experiment reduced average floor from 10.84 to 7.97 with
return regression and 8.25 with added combat feedback. Both arms updated the
existing action scorer to fit recorded returns. This follow-up inspects the
resulting rankings and removes that coupling from prediction fitting. It does
not promote a new player or claim improved gameplay.

Both original round-60 model files and every PPO Adam moment/counter remain
read-only: **5,658 for player 2 and 6,045 for player 3**. All four rejected forks,
their earlier recipes and their results remain preserved.

## What is implemented

The saved-menu diagnostic replays each recorded decision through its source
model, including shop navigation, combat-owned nested selections, exact sampling
draws and behavior probabilities. At the same effective current public menu,
it compares all three fixed models: original, return-only and consequence.
The public encoder and numerical scoring kernel match the historical policy.

It records raw action scores, top-choice changes, score gaps, score spread,
strict pair-order reversals, softmax entropy/KL and choices under the same recorded
noncombat random draw. Forced navigation and single-action menus remain counted
but do not dilute strategic-menu rates. Exact ties retain the original first-index
rule; tied pairs do not become fictitious strict inversions.

Reports keep the source policy's trajectories separate. They weight each game
equally within player/source-policy/combat-or-noncombat strata rather than treating
every correlated menu as an independent game. These are counterfactual predictions
on a common menu, not counterfactual game outcomes or labels proving which move
was best. Score scale and sampling changes are measured; statistical calibration
against optimal-action probabilities is not established.

The new outcome predictor owns a separate **512-input / 32-tanh-hidden / seven-output
network, with 16,647 parameters**. It starts with a copy of the original hidden
weights, then trains its own copy and new readout. It shares no trainable parameters
or optimizer with the original player. Its independent Adam starts at zero and
is saved alongside the prediction checkpoint. The original PPO Adam is neither
reset nor advanced. Prediction and policy checkpoints have different schemas.

`PlayerWithPredictions.action_policy` and its stateful chooser delegate directly
to the unchanged player. Neither calls the predictor. `predict` is a separate,
explicit interface returning action-conditional outcome estimates; no caller
automatically ranks actions by them. Fitting predictions cannot modify the original
encoder, action readout, direct action path or critic. This is an intentional
prediction-only control, not a permanent restriction on future policy learning.

All seven targets, missing-label masks and TRAIN-only provenance come from the
previously sealed 442 decisions / 51 plans / seven source worlds. They describe
recorded continuations, not controlled causal action values or victory probabilities.
The predictor is action-dependent and is **not automatically admitted as a
state-only PPO baseline**. Extra validation rejects known provenance/future-label
aliases at prediction input; the historical public encoder stays unchanged.

Nine finite fits comprise seven leave-one-whole-world-out folds, separately for
the two parents, and two all-TRAIN prediction checkpoints. Use the predeclared
initializer 20261022 and 128 epochs, fitting-only target scaling and equal
world/plan/valid-decision weights. The numerical loss is separate from game
rewards: standardized recorded-return MSE plus 0.25/6 times each active
consequence MSE, L2 0.0001, learning rate 0.001 and gradient cap 5. Constant or
missing fitting targets are inactive. Held outcomes choose no epoch, parameters
or checkpoint. Fitting/held curves and constant baselines are saved separately.

## Short check completed; full inspection remains owner-run

Codex completes all **nine prediction fits** and the first **six saved cases /
600 decisions**, covering both fixed players and all three source variants on
one development world. Every fitted prediction leaves the original action scores
and probabilities **exactly identical** on those menus. Source choices, ownership
and probabilities reconstruct correctly. No game is launched, no app is copied
and no original policy or PPO optimizer is updated.

On the unchanged players' saved combat menus in that one-world sample:

| Diagnostic, original → old consequence-trained fork | Player 2 | Player 3 |
| --- | ---: | ---: |
| Mean centered action-score RMS | 2.739 → 0.296 | 1.535 → 0.233 |
| Mean top-two score gap | 1.090 → 0.293 | 0.634 → 0.114 |
| Menus with a changed greedy top action | 36.4% | 52.9% |

Noncombat score gaps shrink too, and the same uniform draw changes the selected
option in 15.2% / 11.5% of eligible original-path noncombat menus in this sample.
This supports the ranking/scale-disruption hypothesis. One world cannot establish
its prevalence or assign final losses to specific changed actions. The full
inspection is still **6/192 cases**, not complete.

The separate predictor's whole-world mean held return MSE is approximately
0.00002229 / 0.00002882 for the two parents; next-public-HP MSE is 0.003678 /
0.001555. These are prediction diagnostics with only four/three TRAIN worlds,
one numerical initializer and a different prediction architecture/optimizer.
They do not establish a matched improvement over older predictors or stronger
play. The new predictor's fitting success cannot grant readiness, action-teacher
admission or search-controller training.

The short real-data check takes **46.77 wall seconds / 26.34 CPU seconds**, with
195.08 MB peak RAM and 28.90 MB cumulative generated output. The six ranking cases
take 9.61 seconds for 600 decisions. Extrapolating to the remaining 22,242 decisions,
plus source checks and clean-session overhead, gives approximately **7–10 minutes**.
Codex therefore leaves the full remaining inspection to the owner.

The repository check passes **2,216 tests (45 new; four skipped)**, strict types
on 443 files, formatting/lint and the C# protocol in **134.42 seconds**. New tests
check predictor derivatives, complete original model/Adam preservation, held-label
poisoning, constant/missing heads, checkpoint separation, exact combat/nested/
noncombat routing and saved-unit restarts. No source/config changes follow the
real-data sample; its sealed work remains reusable by the owner command.

## One owner command

Run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/inspect-action-separation-v1.sh
```

This reads saved records and reuses all nine prediction fits and the six completed
ranking cases. It does not play games or train either original player. It needs no
game closure. The same finite inspection continues across clean four-minute sessions,
with a 30-minute invocation cap, 480 CPU seconds / 2 GB RAM / 1 GB cumulative output
per session. Rerunning reuses completed units and displays the saved final result
after completion. An incomplete or changed unit stops for inspection; it is not
silently deleted or refitted. No next experiment follows automatically.

The output cap covers the new workspace. The read-only earlier teacher, learning
comparison and frozen game files are excluded and remain unchanged. Retain at most
one full episode during decoding. Compact ranking histories and prediction states
stay under ignored `artifacts/`, not Git.

## Next learning boundary

Assess the complete ranking report before designing the next policy update.
Predictor-only fitting now has an explicit isolation control; it does not itself
improve the actor. A future actor update needs its own objective/derivative checks,
appropriate fresh sampled experience or qualified preference labels, and original
player controls on fresh game worlds. These greedy development histories and
privileged teacher continuations remain ineligible for ordinary PPO training.
All legal decision families can remain learnable. Full-run victory under the
existing 128-CPU-second budget remains primary; HP prediction is not a reward.

Exact configuration, protected state seals, sample results and verification
measurements are in [the portable evidence](evidence/native-action-prediction-separation-v1.json).
