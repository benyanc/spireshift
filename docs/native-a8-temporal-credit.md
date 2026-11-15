# A8 temporal credit comparison

The [world-credit comparison](native-a8-world-credit-result.md)
qualified for fitting and produced modest floor gains with within-world
credit. All evaluation games ended in Act 1. The next experiment tests
whether estimating progress sooner makes each decision's training
signal more useful.

## Saved qualification

For each initializer, a public-state forecast fits twelve older
normal-start training runs and predicts the final training return on
24 newer runs across eight separate worlds. A constant fitted on the
same older data supplies the forecast baseline. Both actor credit
calculations use the same forecasts. They differ only in the length
of the credit trace.

| Initializer | Held-world squared error reduction vs constant | Full-trace median gradient agreement | Short-trace median gradient agreement |
| --- | ---: | ---: | ---: |
| Player 2 | 22.6% | −0.055 | +0.178 |
| Player 3 | 34.9% | +0.109 | +0.178 |

The direction check compares the actor update across all 35 distinct
four-world splits. The shorter trace reduced opposing directions from
26 to two for player 2 and from six to zero for player 3. These splits
describe the saved training batch. Fresh gameplay will determine
whether the update improves wins. [Screen evidence](evidence/native-a8-temporal-credit-screen-v1.json).

## Fitting and evaluation

Both fits start with exact copies of the original weights and Adam
for each initializer. They share the same 48 verified model-owned
training runs, value targets, update order and optimizer settings.
The full trace uses lambda 1.0 and reconstructs the original
return-minus-value advantage. The short trace uses lambda 0.95 and
bootstraps from the public forecast, giving earlier observed
transitions more influence. The progress components telescope to
the declared whole-run training score after the fixed initial term.
The game and terminal victory objective stay frozen.

The full and short copies sealed 29 updates each for player 2 and
28 each for player 3. The value weights matched exactly in both
pairs. All four copies reloaded on a separate seed and delivered
their four declared native choices. The build, original full states,
and Adam passed verification.
[Preparation evidence](evidence/native-a8-temporal-credit-preparation-v1.json).

The longer comparison uses 64 normal-start Ironclad/A8 games on
eight fresh worlds. Each world uses both initializers and all four
arms, covering the original, the prior within-world fit, and the
two new copies. Every action comes from the model's full legal menu.
Full-run wins remain primary, and every planned game is counted.

Close STS2 and allow roughly 15–25 minutes. The comparison makes
zero optimizer updates.

```bash
bash scripts/compare-a8-temporal-credit-v1.sh
```
