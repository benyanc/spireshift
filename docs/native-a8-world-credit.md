# A8 world-relative learning comparison

**Completed.** Both initializers qualified for fitting. The
[saved evaluation](native-a8-world-credit-result.md) verified
zero wins across the three arms.

The [action-credit pilot](native-a8-action-credit-result.md) verified
legal alternatives and their effects. Nine pairs changed the training
return, below the twelve needed to fit. The next experiment asks whether
complete model-owned trajectories provide a stronger comparison within
each world.

## Training

For each of eight new training worlds and both initializers, the frozen
original plays three independent normal-start Ironclad/A8 games. The
game seed stays fixed within a world. Each draw has a separate policy
random stream, and the model samples every choice from the full legal
menu, including any factors of an ordered answer. The recipe uses
only these new training trajectories.

The existing full-run training score ranks native wins first. Act and
floor progress distinguish completed losses. The study requires all
48 training games to end naturally within their guards and at least
four worlds with different returns for each initializer before fitting.

For each initializer, both copies start from the exact same original
model and Adam and fit on the same delivered decisions. They share
the critic target, one pass, shuffled order, optimizer settings, and
policy-change guard. The actor credit subtracts a different baseline
from the run return.

| Copy | Baseline |
| --- | --- |
| Pooled | Mean return of runs on the other training worlds |
| Within-world | Mean return of the other two policy draws on this world |

Matching on the world holds the initial map and starting state fixed.
The two copies test whether comparing against peers on that world
gives a better policy update. The fitting score is an auxiliary
training target. Binary native victory remains the evaluation target.

## Short checks

The two control worlds produced twelve native losses and 2,653
verified choices. Player 2 saw different returns on both worlds.
Player 3 saw different returns on one. The pooled and within-world
copies sealed nine updates each for player 2 and twelve each for
player 3. Final value weights matched within each pair.

The combined short check reached its time boundary before the first
reload delivered a choice. The worker closed cleanly. The stopped
prefix and three unstarted reloads remain in the original record.
The first separate check sealed one reload and stopped on a case ID
with an underscore. The current launcher uses journal-safe IDs in
the reload and owner evaluation plans. It verified four choices for
each of the four sealed copies on a fresh seed. The short copies
remain separate from the owner study.
[Short-check evidence](evidence/native-a8-world-credit-control-v3.json).

## Evaluation and launch

If the training gate passes, both fitted copies and the frozen original
play the same eight fresh development worlds for each initializer.
The 48 evaluation games use the standard full-menu sampler with matched
seeds. The report keeps every planned game in the denominator and
reports native wins first, with act and floor progress as diagnostics.
The reserved final-test worlds stay separate.

Close STS2 and allow roughly 25–40 minutes for collection, fitting on
copies, and evaluation.

```bash
bash scripts/train-a8-world-credit-v3.sh
```

Clean sealed work can resume. An uncertain delivery preserves its
marker and stops that attempt. The frozen game, original weights and
full Adam, and earlier studies remain exact.
