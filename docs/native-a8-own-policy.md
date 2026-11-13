# Model-owned decisions on the frozen A8 game

The owner run is complete. The [saved result](native-a8-own-training-result.md)
verifies all 72 games and four PPO rounds. Use the result and current
backlog for the next learning stage.

The engine supplies the public state, current legal actions, delivered
effects and terminal outcome. The model scores the entire advertised
menu and samples its action. The transport verifies the exact binding
and refreshes the menu after delivery. A failed or capped episode retains
its evidence and status.

The saved audit checked 6,948 menus from 48 sealed normal-start games.
Every advertised native binding reached the shared input. The previous
policy's shop navigation forced 53 choices and omitted 111 advertised
options across 107 menus. The new model-only path scores all the options
on those menus, including leaving before opening and reopening after an
inspection. Public shop history remains available as a feature.

Two fresh normal starts ended in verified native losses. The model
sampled every one of the 299 delivered decisions from the full current
menu. Raw replay verified the actions, their behavior probabilities and
both terminal outcomes. Frozen game, runtime, SDK, localization,
checkpoints, Adam states and the shared profile passed verification.
These controls made zero optimizer updates. Their scope is the advertised
menus observed in these cases.

## Full-run learning

The [separate native admission](../configs/native-learning/sts2-v0.111.0-a8-own-training-v1.json)
starts from full copies of original players 2 and 3, including their Adam
moments and counters. Each initializer has two PPO rounds of 12 new
Ironclad/A8 normal starts. Every round collects from its own current
checkpoint before updating. Each clean game needs an explicit native
ending and exact reconstruction of its public menus, model draws, bound
actions and successors. Each round needs at least eight clean terminal games.

An ordered selection contributes one PPO probability ratio and one value
target at the initial menu. The learner adds the conditional log
probabilities, then clips the ratio for the entire delivered answer. Local
selection factors never add environment steps. The existing return gives a
genuine terminal win a score of one and bounded progress credit to terminal
losses. A public value baseline fits on other games in the round to assign
credit. The training schedule uses only the model's own fresh games.

After both round-two copies seal, the launcher plays 24 games on six
separate normal-start worlds. Each world pairs each fixed final with its
original under the same model-only sampling rules. The comparison reports
wins first and retains caps, failures and unstarted games in the denominator.
The development panel measures early progress. The final-test worlds
remain reserved for confirmation.

## Verified preparation

Four fresh terminal losses supplied 1,073 native training decisions and
27 optimizer updates on disposable copies. Player 2 advanced from 5,658 to
5,676 Adam steps and player 3 from 6,045 to 6,054. Both actors changed and
the restored copies each delivered six choices from a fresh start. The
live short games exercised ordinary decisions. A saved ordered selector
with seven local picks and one commit verified one joint ratio and the
actor and critic derivatives separately. The saved diagnostic supplied
zero training games. The game, native support build, runtime, SDK,
localization, shared profile and all four reference checkpoints passed
verification. [Preparation evidence](evidence/native-a8-own-training-v1.json).

The historical owner command launched 48 training games followed by
the fixed development comparison. Its outer cap was 90 minutes.

```bash
bash scripts/train-a8-own-policy-v1.sh
```

The launcher verifies the short receipts before gameplay. It resumes at
sealed game and update boundaries and stops for an unsealed or uncertain
unit. It keeps the frozen terminal-victory objective and 128 native CPU
seconds per game, plus the existing operational guards. The status of the
normal-start Architect endpoint will be evaluated if reached. The prior
save-enabled [Architect diagnostic](native-a8-paired-finals.md) reached
verified victory through the native event. Official-game validation remains
a separate milestone.

Keep Phrog and other named fights as saved diagnostics. The fresh tempo
comparison verified three Act 1 clears and nine losses for each arm, with
identical choices. That rule supplies no new evidence of general
improvement. [Completed tempo comparison](native-a8-act1-status-tempo.md).
The [earlier own-policy result](native-policy-confirmation-result.md)
improved floor progress with zero full wins.
