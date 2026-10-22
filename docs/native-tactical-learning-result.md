# Native tactical learning result

The finite diagnostic is **complete and passes for both players and both methods**.
The existing actor can learn these simple native-backed decisions when feedback is
immediate and unambiguous. This does not demonstrate stronger full-game play, identify
the cause of the earlier stalled comparison, or qualify the production credit baseline.

## What completed

The owner collected 64 roots on 32 fresh worlds: 24 fitting worlds and eight held-out
worlds, with two fixtures per world. Each root has three observed native branches,
for **192 branches, zero full-run attempts**. All 66 collection/fitting units complete.
Both copies start from the original saved players, including their complete Adam state.
Original state files and counters **5,658 / 6,045** remain unchanged.

The two goals are finishing an injected combat with the first move and surviving one
advertised enemy turn. All candidate effects were executed in the frozen native engine;
the public actor never receives the fixture goal, answer, seed or hidden RNG state.
These deliberately artificial, privileged fixtures are not ordinary full-run experience.
See the [original design](native-tactical-learning.md) for exact setup and boundaries.

## Held-out results

The probabilities below are the model's probability of selecting the native-verified
successful action. They are not estimated full-game win probabilities.

| Player | Initial greedy correctness | PPO greedy correctness | Teaching greedy correctness | Lowest held-out PPO / teaching probability |
| --- | ---: | ---: | ---: | ---: |
| 2 | 8/16 | 16/16 | 16/16 | 99.9888% / 99.9720% |
| 3 | 6/16 | 16/16 | 16/16 | 99.9776% / 99.9639% |

All four copies pass the predeclared criterion: minimum fitting probability at least
80%, minimum held-out probability at least 75%, and 100% held-out greedy correctness.
Player 2's methods each make 761 optimizer updates; player 3's each make 766. Actual
optimizer work is matched within each player, not assumed from the planned maximum.
The minimum fitting probability first exceeds 80% at PPO/teaching rounds 5/4 for
player 2 and 3/3 for player 3. All 256 declared rounds still run; no held-out answer
selects an epoch or changes the schedule.

**Fresh seeds provide limited public-state novelty.** There are 31 distinct fitting
public inputs and 13 distinct held-out inputs; 11 held-out inputs also occur in fitting.
Only two held-out case rows are genuinely new public inputs, both survival fixtures.
Those two also have 100% greedy correctness in all four copies; their lowest successful
action probability is 99.9646%. This is narrow evidence of transfer, not broad
generalization across cards, decks, targets, costs, encounters or strategic choices.
The study does not qualify target selection or discount/setup sequences.

## What this establishes

- Native fixture delivery, public feature construction and sampled-reward policy
  updates can jointly produce a large, reproducible change on these tasks. A universal
  inability to update or fit even simple native cases is not supported by this result.
- Both direct teaching and PPO can fit these cases. The result does not establish that
  either will solve natural combat or that one is the better full-game learner.
- Diagnostic PPO uses an **exact action-independent oracle baseline** from the
  observed branches. Production full-run PPO still uses its separately qualified
  20-feature cross-fitted baseline and much longer outcomes. Their credit quality is
  not tested here. Repeated draws from saved branch outcomes are not new native games.
- The artificial goals do not address coordinated card sequences, long-term health
  preservation, deck building, route selection, exploration or terminal victory.

The earlier [256-attempt full-game comparison](native-policy-update-comparison-result.md)
therefore remains negative for demonstrated improvement. Do not promote these diagnostic
forks or replace the original players with them. No scale-up, controller or subsequent
training is automatically authorized by a diagnostic pass.

## Verification and next work

The saved-only audit verifies all **66 sealed units / 6,763 source files**, reconstructs
the labels from the saved native branch outcomes, recomputes held-out probabilities
from all four final states, separates genuinely new public inputs, and verifies both
original full states and Adam counters. It takes **4.61 seconds**, launches no games
and makes no optimizer updates. It checks saved evidence; it does not replay native effects.

The owner also completed the previously pending full repository check successfully in
**132.70 seconds**, with a receipt matching the exact pre-assessment repository snapshot.
The diagnostic takes **575.63 seconds**, uses **304.91 MB** peak resident memory and
retains **67.06 MB**. There are no app copies, caps, production updates or promotions.
The former owner command now only verifies/displays its completed result.

Next in the agreed backlog is a **structured public-input comparison**, keeping capacity,
initialization, information available, action families and computation explicit. Use
the same saved situations for representation/fitting controls, report duplicates and
unfamiliar inputs, then use fresh own-policy games for actual PPO comparisons. Test a
larger network separately. This is a testable next intervention, not a conclusion that
hashing caused the full-game failure. A richer state-only value predictor, more varied
bounded experience and stronger teachers follow separately.

See [portable result evidence](evidence/native-tactical-learning-result-v1.json) and
the [ordered backlog](backlog.md). Private roots, states and detailed curves remain
under `artifacts/native-tactical/sts2-v0.111.0-a8-comparison-v1`; the saved audit is
`artifacts/native-tactical/assessment-v1/report.json`.
