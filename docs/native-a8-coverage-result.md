# A8 model-owned coverage result

All 72 games reached verified native losses in Act 1. The audit reconstructed
13,229 deliveries and checked 4,392 sealed files. The build, original checkpoints,
full Adam, runtime and shared profile passed verification. The audit used saved
evidence and performed zero optimizer updates.

| Training partition | Games | A8 wins | Act 1 clears | Act 1 bosses reached |
| --- | ---: | ---: | ---: | ---: |
| Fresh normal starts, player 2 | 24 | 0 | 0 | 2 |
| Fresh normal starts, player 3 | 24 | 0 | 0 | 4 |
| Continuations, player 2 | 12 | 0 | 0 | 3 |
| Continuations, player 3 | 12 | 0 | 0 | 6 |

The 48 fresh starts supplied 8,062 verified decisions and nine and eight distinct
floor-based returns for the two initializers. The continuations supplied 796
new decisions after 4,371 regenerated setup deliveries. All three draws matched
their source menu at each of the eight roots. The observed games exercised zero
local ordered-answer factors. The focused native selector controls retain that
coverage. [Preparation and selector scope](native-a8-temporal-credit-result.md).

## Fitting assessment

Seven of the eight roots yielded the same terminal training return on all three
draws. Player 2 had zero varying roots. Player 3 had one, with three losses on
floors 11, 12 and 13. The proposed normal-only versus added-suffix fit needs
variation at multiple distinct roots for both initializers. Fitting for that
comparison remains blocked. The verified normal-start games retain their
training provenance. [Coverage audit](evidence/native-a8-coverage-result-v1.json).

Five of the six fresh boss attempts began at full HP. All six lost. The
continuations from late openings produced nine boss attempts and zero clears.
These observations prioritize improving the behavior that generates outcomes over
another batch at the same sampling settings.

## Paired sampling qualification

The next study tests whether giving the model's higher scores more weight yields
useful Act 1 training outcomes. The earlier greedy-combat study had two clears
versus zero for its sampled arm, with limited scope on the older policy path.
[Earlier comparison](native-combat-behavior-result.md).

The [new recipe](../configs/native-learning/sts2-v0.111.0-a8-sampling-v1.json)
selects two elite and two boss openings per initializer from sealed normal-start
training games. The player has at least half HP at every opening. The selection
orders eligible menus by HP fraction, depth and source order. The eight openings
come from five native worlds, with four distinct worlds per initializer. Two
independent draws per root pair temperature 0.8 with 0.4 after exact replay of the
original model-owned prefix. That makes 32 training-only continuations. Each pair
starts on the same menu with the same actor and draw stream. The model scores the
full legal menu at every step and chooses every action.

The gate requires all 16 pairs to have native terminal outcomes, more Act 1 clears
at temperature 0.4, and a clear unique to that arm for each initializer across
at least two distinct worlds. A pass supports collecting new training outcomes
under that behavior. Fitting and fresh normal-start strength testing require their
own recipes. A flat result shifts priority to improving the score of legal actions
before further sampling changes. The comparison makes zero optimizer updates.

Four short native controls reached verified losses from two matched elite
openings. They verified the sampling change at the exact root, native delivery
and clean reset for both temperatures. The first differing choices occurred on
matched combat menus. Standard and sharper sampling reached floors 17 and 14
for player 2, and floors 13 and 15 for player 3. The controls qualify execution
of the comparison. [Control evidence](evidence/native-a8-coverage-result-v1.json).

Close STS2 and allow about 8–15 minutes.

```bash
bash scripts/compare-a8-sampling-v1.sh
```
