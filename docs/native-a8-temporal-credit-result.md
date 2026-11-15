# A8 temporal credit result

All 64 games reached verified native losses. Every arm finished with zero full-run
wins and zero Act 1 clears. The eight normal-start worlds paired both initializers
and all four checkpoints. There were zero caps, failures or unattempted games.

| Arm | Full-run wins | Act 1 clears | Act 1 bosses reached | Mean maximum floor |
| --- | ---: | ---: | ---: | ---: |
| Original | 0/16 | 0/16 | 1/16 | 7.88 |
| Within-world | 0/16 | 0/16 | 1/16 | 7.94 |
| Full trace | 0/16 | 0/16 | 2/16 | 8.50 |
| Short trace | 0/16 | 0/16 | 1/16 | 8.00 |

Against each reference, the short trace finished higher in two pairs, tied in
13 and finished lower in one. Its mean floor difference was +0.125 against the
original, +0.0625 against within-world and −0.50 against the full trace. The
descriptive seed-clustered intervals include zero in all three comparisons.
The earlier training direction improvements have no demonstrated benefit on
fresh A8 starts. [Preparation](native-a8-temporal-credit.md).

An independent saved-only audit checked 3,904 sealed files and reconstructed
8,647 actual deliveries, all public menus, model draws, successors and genuine
endings. The frozen game, original checkpoints and full Adam, evaluated copies,
runtime and shared profile passed the exact checks. The 64 games exercised zero
local ordered-answer factors. The earlier native controls supply the evidence for
those factors and selector potion ownership. [Ordered selections](native-win-curriculum-large-selection.md),
[potion selector controls](native-a8-practice-continuation.md).

## Decision coverage and shared updates

The separate screen used the 48 saved world-credit training games only. All
5,447 decisions with more than one legal choice came from Act 1. They include
3,745 combat and 1,702 noncombat decisions, with 265 card-reward, 163 map and
104 event choices. Three runs reached Act 1 bosses and all three lost.
[Training study](native-a8-world-credit-result.md).

For each initializer and trace, the screen reconstructed the behavior actor's
policy gradient with the same global advantage normalization. It compared
combat and noncombat directions within worlds and across complementary halves
of the eight worlds. The screen required at least six of eight opposing
within-world directions and 47 of 70 opposing cross-half directions for both
initializers under the same trace. The half comparisons reuse the same eight
worlds and serve as descriptive diagnostics.

| Initializer | Trace | Opposing within-world directions | Opposing cross-half directions | Median cross-half cosine |
| --- | --- | ---: | ---: | ---: |
| 2 | Full | 3/8 | 34/70 | +0.001 |
| 2 | Short | 5/8 | 18/70 | +0.011 |
| 3 | Full | 3/8 | 45/70 | −0.021 |
| 3 | Short | 3/8 | 36/70 | −0.001 |

Neither trace qualified a split of the scoring heads. This is a check of update
directions at the original weights. Broader outcome coverage is the next learning
priority. [Audit and screen evidence](evidence/native-a8-temporal-credit-result-v1.json).

## Model-owned coverage collection

The separate [collection recipe](../configs/native-learning/sts2-v0.111.0-a8-model-owned-coverage-v1.json)
uses the shared scorer and the original policies for both initializers. It declares
48 fresh Ironclad/A8 training games across 24 new normal-start worlds, plus three
independent continuations from each of eight naturally reached training roots.
Each initializer has separate middle and late Act 1 map and combat-opening roots
on four distinct source worlds. Selection uses depth and menu ownership from
sealed training journals.

Each continuation starts a clean native worker at the original game seed. The
original model and sampling stream regenerate the exact source prefix. Every
prefix menu, sampled action and successor is verified against the source. At
the exact public root, the sampler switches to a separate draw stream. The model
continues to score the full legal menu, including skips, targets and compound
choices. The reconstructed prefix serves as setup. Future fitting may use only
verified suffix decisions from continuations, separately from fresh games.

The saved replay reconstructed 1,457 prefix decisions across all eight roots.
Four short native controls used two independent draws from the same middle-Act 1
root for each initializer. They verified 396 prefix deliveries and 16 new
deliveries at the declared four-choice stop, with clean shutdowns. The frozen
game, original full checkpoints, Adam and shared profile passed verification.
[Preparation evidence](evidence/native-a8-temporal-credit-result-v1.json).

The launcher collects evidence with zero optimizer updates. It preserves incomplete
runs, resumes only from sealed chunks and stops on an uncertain action. Assess
distinct-world coverage, genuine clears and suffix outcomes before admitting any
fitting. Development and final-test worlds stay reserved for evaluation.

Close STS2 and allow about 15–25 minutes.

```bash
bash scripts/collect-a8-model-owned-coverage-v1.sh
```
